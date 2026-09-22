"""Orquestrador fail-safe dos 20 experimentos: config, instrumentos, execução."""

from __future__ import annotations

import importlib.util
import json
import logging
import math
import os
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import numpy as np

from ametek_orm import AmetekMX30, CommunicationError, FalhaFatalDeInstrumento
from sinais import ruido_awgn, snr_medida, tempo


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("MestreExperimentos")


# ---------------------------------------------------------------------------
# Helpers de variável de ambiente
# ---------------------------------------------------------------------------

def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} deve ser 0/1, false/true, no/yes ou off/on; recebido {value!r}")


def env_float(name: str, default: float) -> float:
    value = float(os.getenv(name, str(default)))
    if not (value > 0):
        raise ValueError(f"{name} deve ser positivo; recebido {value!r}")
    return value


def optional_env_float(name: str) -> Optional[float]:
    value = os.getenv(name)
    return None if value is None or not value.strip() else float(value)


def env_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} deve ser inteiro positivo; recebido {value!r}")
    return value


def env_float_tuple(name: str, default: Iterable[float]) -> Tuple[float, ...]:
    raw = os.getenv(name)
    values = tuple(default) if raw is None else tuple(float(item.strip()) for item in raw.split(","))
    if not values or any(value <= 0 for value in values):
        raise ValueError(f"{name} deve conter valores positivos separados por vírgula")
    return values


# ---------------------------------------------------------------------------
# Configuração central da bancada (única fonte de verdade)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "resultados"
EXPERIMENT_DIRS = (PROJECT_ROOT / "experimentos_nativos", PROJECT_ROOT / "experimentos_waveform")

# Aquisição e dataset
FS_HZ = 30_000.0
GRID_FREQUENCY_HZ = env_float("GRID_FREQUENCY_HZ", 60.0)
DURATION_S = 0.200
POINTS = 6_000
SNR_LEVELS_DB = env_float_tuple("SNR_LEVELS_DB", (30.0,))
SIM_CAPTURES_PER_CLASS = env_int("SIM_CAPTURES_PER_CLASS", 2_000)
REAL_CAPTURES_PER_CLASS = env_int("REAL_CAPTURES_PER_CLASS", 1)
BASE_SEED = env_int("BASE_SEED", 20_260_827)
# Início do distúrbio dentro da janela de 200 ms para as classes que têm um
# período "normal" antes e depois (SAG/SWELL/INTERRUPTION e a maioria das
# TRACe com início/duração). Usado como pré-trigger do osciloscópio.
DISTURBANCE_START_S = 0.060

# Seleção segura do modo
BENCH_MODE = env_bool("BENCH_MODE", default=False)
SIMULATED_MODE = not BENCH_MODE
OUTPUT_ARMED = os.getenv("ARM_OUTPUT", "").strip().upper() == "YES"
CAPTURE_CURRENT = env_bool("CAPTURE_CURRENT", default=False)

# Estado de sessão da CLI interativa — mutável em runtime (mesmo idioma de
# OUTPUT_ARMED/autorizar_saida()): None/False reproduzem o comportamento de
# hoje sem nenhuma mudança. cli.py é quem escreve nesses globais; qualquer
# outro consumidor (testes, scripts) nunca precisa tocá-los.
SESSION_RESULTS_DIR: Optional[Path] = None
CAPTURAS_OVERRIDE: Optional[int] = None
MARGIN_MODE: bool = False
DIAGNOSTICO_MODE: bool = False

# AMETEK pela USB com porta COM virtual; 115200 foi confirmado no equipamento real.
AMETEK_PORT = os.getenv("AMETEK_PORT", "COM10")
AMETEK_BAUDRATE = env_int("AMETEK_BAUDRATE", 115_200)
AMETEK_TIMEOUT_S = env_float("AMETEK_TIMEOUT_S", 5.0)
AMETEK_QUERY_EOT = env_bool("AMETEK_QUERY_EOT", default=True)
AMETEK_EXPECTED_MODEL = os.getenv("AMETEK_EXPECTED_MODEL", "MX30")
AMETEK_CLEAR_USER_WAVEFORMS = env_bool("AMETEK_CLEAR_USER_WAVEFORMS", default=False)

# Keysight USB/VISA informado para a bancada. Use AUTO apenas para descoberta.
KEYSIGHT_RESOURCE = os.getenv(
    "KEYSIGHT_RESOURCE",
    "USB0::0x0957::0x17A4::MY59240844::0::INSTR",
).strip()
KEYSIGHT_EXPECTED_MODEL = os.getenv("KEYSIGHT_EXPECTED_MODEL", "DSOX4034A")
KEYSIGHT_TIMEOUT_MS = env_int("KEYSIGHT_TIMEOUT_MS", 15_000)

# Limites de comissionamento e operacionais da bancada.
BASE_VOLTAGE_RMS = env_float("BASE_VOLTAGE_RMS", 127.0)
SOURCE_VOLTAGE_RANGE_RMS = env_float("SOURCE_VOLTAGE_RANGE_RMS", 150.0)
EUT_MAX_VOLTAGE_RMS = env_float("EUT_MAX_VOLTAGE_RMS", 140.0)
EUT_MAX_PEAK_V = env_float("EUT_MAX_PEAK_V", 400.0)
CURRENT_LIMIT_A = env_float("CURRENT_LIMIT_A", 0.5)
CURRENT_PROTECTION_DELAY_S = env_float("CURRENT_PROTECTION_DELAY_S", 0.1)

# Estes fatores devem corresponder fisicamente às probes instaladas.
VOLTAGE_PROBE_ATTENUATION = optional_env_float("VOLTAGE_PROBE_ATTENUATION")
CURRENT_PROBE_ATTENUATION = optional_env_float("CURRENT_PROBE_ATTENUATION")
CURRENT_BASE_A = optional_env_float("CURRENT_BASE_A")
EXT_TRIGGER_PROBE_ATTENUATION = env_float("EXT_TRIGGER_PROBE_ATTENUATION", 1.0)
EXT_TRIGGER_RANGE_V = env_float("EXT_TRIGGER_RANGE_V", 8.0)
EXT_TRIGGER_LEVEL_V = env_float("EXT_TRIGGER_LEVEL_V", 1.5)


def validate_bench_configuration(require_output: bool = True) -> None:
    """Rejeita execução física ambígua ou acima dos limites configurados."""
    if not BENCH_MODE:
        return
    if AMETEK_PORT.upper() != "COM10":
        raise RuntimeError(f"A porta solicitada para a bancada é COM10; configurado {AMETEK_PORT!r}")
    if AMETEK_BAUDRATE != 115_200:
        raise RuntimeError("A MX30 da bancada requer AMETEK_BAUDRATE=115200")
    if VOLTAGE_PROBE_ATTENUATION is None or VOLTAGE_PROBE_ATTENUATION <= 0:
        raise RuntimeError("Defina VOLTAGE_PROBE_ATTENUATION conforme a probe física instalada")
    if CAPTURE_CURRENT and (CURRENT_PROBE_ATTENUATION is None or CURRENT_BASE_A is None):
        raise RuntimeError(
            "Com CAPTURE_CURRENT=1, defina CURRENT_PROBE_ATTENUATION e CURRENT_BASE_A"
        )
    if BASE_VOLTAGE_RMS > EUT_MAX_VOLTAGE_RMS:
        raise RuntimeError("BASE_VOLTAGE_RMS excede EUT_MAX_VOLTAGE_RMS")
    if EUT_MAX_VOLTAGE_RMS > SOURCE_VOLTAGE_RANGE_RMS:
        raise RuntimeError("EUT_MAX_VOLTAGE_RMS excede o range da fonte")
    if require_output and not OUTPUT_ARMED:
        raise RuntimeError(
            "Saída física bloqueada. Após o preflight e a inspeção da bancada, defina ARM_OUTPUT=YES"
        )


@dataclass(frozen=True)
class Config:
    """Parâmetros passados para cada experimento — nunca importados por eles."""

    fs_hz: float
    points: int
    duration_s: float
    grid_frequency_hz: float
    base_voltage_rms: float
    snr_levels_db: Tuple[float, ...]
    base_seed: int
    capture_current: bool
    current_base_a: Optional[float]
    results_dir: Path
    sim_captures_per_class: int
    real_captures_per_class: int
    disturbance_start_s: float
    capturas_override: Optional[int] = None
    margin_mode: bool = False
    diagnostico_mode: bool = False

    def capturas(self, simulated: bool) -> int:
        if simulated:
            return self.sim_captures_per_class
        if self.capturas_override is not None:
            return self.capturas_override
        return self.real_captures_per_class


@dataclass
class ResultadoClasse:
    """Resultado de uma classe dentro da bateria — ver ``Bancada.executar_bateria``."""

    id: str
    nome: str
    ok: bool
    motivo: Optional[str] = None

    @property
    def pasta_esperada(self) -> Path:
        return SESSION_RESULTS_DIR or RESULTS_DIR


def _build_config() -> Config:
    return Config(
        fs_hz=FS_HZ,
        points=POINTS,
        duration_s=DURATION_S,
        grid_frequency_hz=GRID_FREQUENCY_HZ,
        base_voltage_rms=BASE_VOLTAGE_RMS,
        snr_levels_db=SNR_LEVELS_DB,
        base_seed=BASE_SEED,
        capture_current=CAPTURE_CURRENT,
        current_base_a=CURRENT_BASE_A,
        results_dir=SESSION_RESULTS_DIR or RESULTS_DIR,
        sim_captures_per_class=SIM_CAPTURES_PER_CLASS,
        real_captures_per_class=REAL_CAPTURES_PER_CLASS,
        disturbance_start_s=DISTURBANCE_START_S,
        capturas_override=CAPTURAS_OVERRIDE,
        margin_mode=MARGIN_MODE,
        diagnostico_mode=DIAGNOSTICO_MODE,
    )


def _discover_keysight_resource(expected_model: str) -> str:
    try:
        import pyvisa
    except ImportError as exc:
        raise ImportError("PyVISA é necessário para descobrir o Keysight") from exc
    manager = pyvisa.ResourceManager()
    matches = []
    try:
        for resource in manager.list_resources("USB?*::0x0957::*::INSTR"):
            instrument = None
            try:
                instrument = manager.open_resource(resource)
                instrument.timeout = KEYSIGHT_TIMEOUT_MS
                idn = instrument.query("*IDN?").strip()
                normalized = "".join(character for character in idn.upper() if character.isalnum())
                expected = "".join(
                    character for character in expected_model.upper() if character.isalnum()
                )
                if expected in normalized:
                    matches.append(resource)
            except Exception:
                logger.debug("Recurso USB não corresponde ao scope: %s", resource, exc_info=True)
            finally:
                if instrument is not None:
                    instrument.close()
    finally:
        manager.close()
    if len(matches) != 1:
        raise RuntimeError(
            f"Descoberta Keysight encontrou {len(matches)} recursos compatíveis: {matches}"
        )
    return matches[0]


# ---------------------------------------------------------------------------
# Bancada: os dois instrumentos + a config, com setup/shutdown fail-safe
# ---------------------------------------------------------------------------

class Bancada:
    """Encapsula ``fonte``, ``osc`` e ``config`` — ponto único de abertura,
    execução da bateria e desligamento fail-safe dos instrumentos físicos.

    Usada como *context manager*: ``Bancada.from_env()`` já energiza (se
    autorizado) e ``with`` garante ``shutdown()`` mesmo se a bateria falhar
    no meio.
    """

    def __init__(self, fonte: AmetekMX30, osc: Optional[object], config: Config):
        self.fonte = fonte
        self.osc = osc
        self.config = config

    def __enter__(self) -> "Bancada":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown()

    def shutdown(self) -> None:
        logger.info("Shutdown fail-safe")
        self.fonte.disconnect()
        if self.osc is not None:
            self.osc.close()

    @classmethod
    def from_env(cls, *, require_output: bool = True) -> "Bancada":
        config = _build_config()
        if SIMULATED_MODE:
            logger.warning("MODO SIMULADO: nenhum instrumento será aberto")
            # Nenhum experimento toca fonte/osc no modo simulado (usam gerar());
            # a instância existe só por consistência de assinatura.
            return cls(AmetekMX30(simulated=True, diagnostico=DIAGNOSTICO_MODE), None, config)

        validate_bench_configuration(require_output=require_output)
        fonte: Optional[AmetekMX30] = None
        osc = None
        try:
            fonte = AmetekMX30(
                AMETEK_PORT,
                baudrate=AMETEK_BAUDRATE,
                timeout_s=AMETEK_TIMEOUT_S,
                query_eot=AMETEK_QUERY_EOT,
                expected_model=AMETEK_EXPECTED_MODEL,
                clear_user_waveforms=AMETEK_CLEAR_USER_WAVEFORMS,
                max_voltage_rms=EUT_MAX_VOLTAGE_RMS,
                max_peak_v=EUT_MAX_PEAK_V,
                max_current_a=CURRENT_LIMIT_A,
                diagnostico=DIAGNOSTICO_MODE,
            )
            fonte.configure_safe_baseline(
                voltage_range_rms=SOURCE_VOLTAGE_RANGE_RMS,
                # VOLTage:HIGH é um limite de pico em Vp. Passamos EUT_MAX_PEAK_V
                # diretamente: o firmware rejeita (erro 14) qualquer saída cujo
                # pico exceda esse valor.
                voltage_high_vp=EUT_MAX_PEAK_V,
                current_limit_a=CURRENT_LIMIT_A,
                protection_delay_s=CURRENT_PROTECTION_DELAY_S,
                frequency_hz=GRID_FREQUENCY_HZ,
            )
            if AMETEK_CLEAR_USER_WAVEFORMS:
                fonte.clear_all_traces()

            try:
                from pymeasure.adapters import VISAAdapter
                from oscilloscope_orm import KeysightDSOX4034A
            except ImportError as exc:
                raise ImportError("Instale PyMeasure e PyVISA para abrir o Keysight") from exc

            resource = (
                _discover_keysight_resource(KEYSIGHT_EXPECTED_MODEL)
                if KEYSIGHT_RESOURCE.upper() in {"", "AUTO"}
                else KEYSIGHT_RESOURCE
            )
            adapter = VISAAdapter(resource, timeout=KEYSIGHT_TIMEOUT_MS)
            osc = KeysightDSOX4034A(adapter)
            logger.info("Keysight identificado: %s", osc.verify_identity(KEYSIGHT_EXPECTED_MODEL))
            osc.initialize_safe()

            voltage_scale = EUT_MAX_PEAK_V / 3.0
            osc.configure_channel(
                1,
                scale=voltage_scale,
                probe_attenuation=float(VOLTAGE_PROBE_ATTENUATION),
                coupling="DC",
                units="VOLT",
            )
            actual_voltage_scale = float(osc.ask(":CHANnel1:SCALe?"))
            if 4.0 * actual_voltage_scale < 1.05 * EUT_MAX_PEAK_V:
                raise RuntimeError(
                    f"Escala CH1 insuficiente: {actual_voltage_scale} V/div para "
                    f"pico limite {EUT_MAX_PEAK_V} V"
                )
            if CAPTURE_CURRENT:
                current_peak = max(float(CURRENT_BASE_A), CURRENT_LIMIT_A) * math.sqrt(2.0)
                osc.configure_channel(
                    2,
                    scale=current_peak / 3.5,
                    probe_attenuation=float(CURRENT_PROBE_ATTENUATION),
                    coupling="DC",
                    units="AMP",
                )
            else:
                osc.disable_channel(2)
            osc.configure_acquisition(sample_rate_hz=FS_HZ, points=POINTS, duration_s=DURATION_S)
            osc.setup_external_trigger(
                level_v=EXT_TRIGGER_LEVEL_V,
                probe_attenuation=EXT_TRIGGER_PROBE_ATTENUATION,
                range_v=EXT_TRIGGER_RANGE_V,
            )
            fonte.authorize_output(require_output and OUTPUT_ARMED)
            if require_output and OUTPUT_ARMED:
                # Energiza uma única vez para toda a bateria. Cada captura, daqui
                # em diante, só reprograma o transiente (PULSe/LIST/CSINe/TRACe) e
                # dispara — nunca desliga a saída entre capturas (ver
                # ametek_orm.program_capture / energize_baseline).
                fonte.energize_baseline()
            logger.info(
                "Instrumentos prontos: AMETEK=%s; Keysight=%s; CH2=%s",
                fonte.idn,
                osc.idn,
                "ON" if CAPTURE_CURRENT else "OFF",
            )
            return cls(fonte, osc, config)
        except BaseException:
            if fonte is not None:
                fonte.disconnect()
            if osc is not None:
                osc.close()
            raise

    # Rede de segurança grosseira para falhas de INSTRUMENTO intermitentes
    # (ex.: -113/-300 esporádicos na Rev. 5.53 mesmo com *WAI/assert_no_errors
    # já no lugar certo) — não substitui investigar a causa raiz quando há
    # tempo, só evita perder uma classe inteira por uma falha que passaria na
    # tentativa seguinte.
    MAX_TENTATIVAS_POR_CLASSE = 3

    def executar_bateria(self, scripts: List[Path]) -> List[ResultadoClasse]:
        """Roda cada classe isoladamente: uma falha de EXPERIMENTO (RMS fora
        de tolerância, timeout de trigger, exceção em ``gerar()``, script
        quebrado...) é tentada até ``MAX_TENTATIVAS_POR_CLASSE`` vezes (com
        ``recuperar_estado_seguro`` entre tentativas) antes de ser registrada
        como ``FALHOU`` e a bateria seguir para a próxima classe. Uma falha de
        INFRAESTRUTURA real (``CommunicationError`` — serial caiu — ou
        ``FalhaFatalDeInstrumento`` — não foi possível confirmar OUTPUT/
        recuperar estado seguro) continua abortando a bateria inteira
        IMEDIATAMENTE, sem retry: não é seguro tentar mais nada com o
        instrumento em estado desconhecido. ``KeyboardInterrupt`` também
        propaga sempre (não é ``Exception``, não é capturada abaixo)."""
        resultados: List[ResultadoClasse] = []
        for script_path in scripts:
            class_id = script_path.stem
            nome = class_id
            try:
                experimento_cls = self._carregar_classe_experimento(script_path)
            except Exception as exc:
                logger.exception("[%s] FALHOU ao carregar — classe abortada, bateria continua", class_id)
                resultados.append(ResultadoClasse(class_id, nome, ok=False, motivo=str(exc)))
                if BENCH_MODE:
                    time.sleep(0.5)
                continue
            nome = getattr(experimento_cls, "nome", class_id)

            sucesso = False
            ultimo_erro: Optional[str] = None
            for tentativa in range(1, self.MAX_TENTATIVAS_POR_CLASSE + 1):
                if tentativa > 1:
                    logger.warning(
                        "[%s] tentativa %d/%d depois de falha: %s",
                        class_id, tentativa, self.MAX_TENTATIVAS_POR_CLASSE, ultimo_erro,
                    )
                logger.info(
                    "========== Experimento %s (%s) ==========", class_id, script_path.parent.name
                )
                try:
                    experimento_cls(self).executar()
                    sucesso = True
                    break
                except (CommunicationError, FalhaFatalDeInstrumento):
                    logger.error(
                        "[%s] Falha de infraestrutura — abortando o restante da bateria", class_id
                    )
                    raise
                except Exception as exc:
                    ultimo_erro = str(exc)
                    logger.exception(
                        "[%s] FALHOU (tentativa %d/%d)", class_id, tentativa, self.MAX_TENTATIVAS_POR_CLASSE,
                    )
                    if tentativa < self.MAX_TENTATIVAS_POR_CLASSE:
                        self.recuperar_estado_seguro()

            if sucesso:
                resultados.append(ResultadoClasse(class_id, nome, ok=True))
            else:
                logger.error(
                    "[%s] FALHOU definitivamente após %d tentativas — classe abortada, "
                    "bateria continua", class_id, self.MAX_TENTATIVAS_POR_CLASSE,
                )
                resultados.append(ResultadoClasse(class_id, nome, ok=False, motivo=ultimo_erro))
                self.recuperar_estado_seguro()
            if BENCH_MODE:
                time.sleep(0.5)

        ok_count = sum(1 for resultado in resultados if resultado.ok)
        logger.info("Bateria concluída: %d/%d classes OK", ok_count, len(resultados))
        for resultado in resultados:
            if not resultado.ok:
                logger.warning("  FALHOU [%s] %s: %s", resultado.id, resultado.nome, resultado.motivo)
        return resultados

    @staticmethod
    def _carregar_classe_experimento(script_path: Path) -> type:
        module_name = f"experimento_{script_path.parent.name}_{script_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Não foi possível carregar {script_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        experimento_cls = getattr(module, "Experimento", None)
        if experimento_cls is None:
            raise AttributeError(f"{script_path.name} não define a classe Experimento")
        return experimento_cls

    def executar_experimento(self, script_path: Path) -> None:
        experimento_cls = self._carregar_classe_experimento(script_path)
        logger.info("========== Experimento %s (%s) ==========", script_path.stem, script_path.parent.name)
        experimento_cls(self).executar()

    def assegurar_tensao_base(self) -> None:
        """Garante que a saída está em ``BASE_VOLTAGE_RMS`` via um STEP nativo
        real — a mesma mecânica que 01/NORMAL usa.

        ``configure_safe_baseline()`` programa a tensão IMEDIATA em 0 V por
        segurança (nunca pula direto para a tensão de teste sem um transiente
        controlado e sincronizado); ``energize_baseline()`` só liga a saída
        nesse nível seguro. Dentro de ``executar_bateria()`` isso nunca é um
        problema porque 01/NORMAL (STEP) sempre roda primeiro e STEP é
        "sticky" (o nível permanece depois do transiente) — as classes
        seguintes herdam essa tensão. `trigger_pulse()` (usado por 02/SAG,
        03/SWELL, 04/INTERRUPTION) NUNCA eleva a tensão imediata sozinho, só
        programa o nível TRANSIENTE (``VOLTage:TRIGgered``) — sem uma classe
        STEP rodando antes na MESMA conexão, o "antes/depois" do pulso fica no
        nível de segurança (0 V), não em ``BASE_VOLTAGE_RMS``. Confirmado na
        bancada: `run 02` isolado (nova conexão, sem 01/NORMAL antes) mediu
        ~0 V antes/depois do SAG em vez de ~127 V.

        Chame isto antes de rodar uma classe isolada (``run <NN>`` na CLI)
        que não seja garantidamente a primeira da bateria. Redundante (mas
        inofensivo) para classes que já elevam a tensão sozinhas
        (``trigger_step``/``program_capture``/``frequency_drift_list``)."""
        if self.osc is None:
            return  # modo simulado: nada físico para ajustar
        self.fonte.trigger_step(self.config.base_voltage_rms)
        self.fonte.arm()
        self.fonte.trigger()
        self.fonte.wait_transient_complete(timeout_s=5.0)

    def recuperar_estado_seguro(self) -> None:
        """Devolve a AMETEK a um estado seguro conhecido depois de uma falha
        de EXPERIMENTO isolada (não de infraestrutura): sistema de trigger
        ocioso (``ABORt``), forma de onda senoidal e modo AC/offset padrão
        (``restaurar_forma_e_modo_padrao``, desfaz o que HARMONICS/DC_OFFSET
        possam ter deixado ligado) e tensão imediata de volta à base — sem
        nunca desligar a saída (ela permanece ligada durante toda a bateria,
        ver ``energize_baseline``).

        Levanta ``FalhaFatalDeInstrumento`` se a fonte não responder durante a
        recuperação ou se a saída cair e não confirmar religada — nesses casos
        não é seguro continuar tentando as classes seguintes. Uma falha
        isolada em ``restaurar_forma_e_modo_padrao()`` (a mesma operação que
        pode ter acabado de falhar dentro da classe que estamos recuperando)
        NÃO vira ``FalhaFatalDeInstrumento`` sozinha — repetir cegamente uma
        chamada que já provou estar quebrada não ajudaria; só a confirmação
        FINAL (tensão de volta à base, fila de erros limpa, OUTPUT no estado
        esperado) decide se a bateria pode continuar."""
        if self.osc is None:
            return  # modo simulado: nada físico para recuperar
        fonte = self.fonte
        try:
            fonte.write("ABORt")
            fonte.write("*CLS")
            fonte.write("FUNCtion:MODE FIXed")
            fonte.write("VOLTage:MODE FIXed")
            fonte.write("SOURce:FREQuency:MODE FIXed")
        except Exception as exc:
            raise FalhaFatalDeInstrumento(
                f"Não foi possível resetar o sistema de trigger para recuperação: {exc}"
            ) from exc

        try:
            fonte.restaurar_forma_e_modo_padrao()
        except Exception:
            logger.warning(
                "Falha ao restaurar forma/modo padrão durante a recuperação — "
                "prosseguindo mesmo assim; a confirmação final abaixo decide se a "
                "bateria pode continuar.",
                exc_info=True,
            )

        try:
            fonte.voltage = self.config.base_voltage_rms
            fonte.assert_no_errors("recuperação de estado seguro pós-falha de experimento")
            if fonte.output_authorized and not fonte.output_enabled:
                logger.warning("OUTPUT caiu durante a falha; religando para a próxima classe.")
                fonte.output_enabled = True
                fonte.assert_no_errors("religar OUTPUT durante recuperação pós-falha")
        except Exception as exc:
            raise FalhaFatalDeInstrumento(
                f"Não foi possível recuperar a AMETEK a um estado seguro após falha de "
                f"experimento: {exc}"
            ) from exc
        logger.info(
            "Estado seguro restaurado: %.3f Vrms, senoide, OUTPUT %s",
            self.config.base_voltage_rms, "ON" if fonte.output_enabled else "OFF",
        )


# ---------------------------------------------------------------------------
# Hierarquia das 20 classes de distúrbio
# ---------------------------------------------------------------------------

class ExperimentoBase(ABC):
    """Base de toda classe de distúrbio. Recebe a ``Bancada`` e expõe
    ``fonte``/``osc``/``config`` como atributos próprios — cada
    ``experimentos_nativos/NN.py`` ou ``experimentos_waveform/NN.py`` herda
    de ``ExperimentoNativo`` ou ``ExperimentoWaveform`` (abaixo) e só
    implementa o que é específico daquela classe.

    ``executar()`` é o laço genérico (capturas, ruído AWGN, gravação) —
    substitui o antigo ``executar_classe_nativa``/``executar_classe_waveform``
    duplicado em dois ``comum.py``.
    """

    id: str
    nome: str
    pre_trigger_s: float = 0.0

    def __init__(self, bancada: Bancada):
        self.bancada = bancada
        self.config = bancada.config
        self.fonte = bancada.fonte
        self.osc = bancada.osc

    @abstractmethod
    def gerar(
        self, t: np.ndarray, f0: float, capture_index: int, rng: np.random.Generator
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """Fórmula da classe: produz a captura do dataset SIMULADO (sem
        hardware). Usada também na bancada real pelas classes que precisam
        de forma de onda arbitrária (ver ``ExperimentoWaveform``)."""

    def total_niveis(self) -> int:
        """Quantos valores discretos de parâmetro esta classe tem (ex.:
        5 para SAG/SWELL/HARMONICS via ``NIVEIS``). ``1`` (padrão) para
        classes de parâmetro contínuo ou sem parâmetro nenhum — usado por
        ``executar()`` para decidir se agrupa capturas por nível quando
        ``set capturas N`` está ativo (ver Task 4)."""
        niveis = getattr(self, "NIVEIS", None)
        return len(niveis) if niveis is not None else 1

    @abstractmethod
    def _capturar_real(
        self, capture_index: int, t: np.ndarray, rng: np.random.Generator
    ) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], Dict[str, float]]:
        """Produz uma captura física: programa a fonte, dispara, lê o
        osciloscópio. Implementado por ``ExperimentoNativo``/``ExperimentoWaveform``."""

    def _preparar_acquisicao_real(self) -> None:
        """Hook opcional, chamado uma vez antes do laço de capturas (bancada
        real), para ajustes que não mudam entre capturas."""

    def _ler_captura(
        self, parametros: Dict[str, float]
    ) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], Dict[str, float]]:
        pontos_efetivos = self._pontos_efetivos_captura_atual
        time_s, voltage_v = self.osc.get_waveform(1, expected_points=pontos_efetivos)
        voltage_pu = voltage_v / (self.config.base_voltage_rms * math.sqrt(2.0))
        current_values = None
        if self.config.capture_current:
            current_time, current_a = self.osc.get_waveform(2, expected_points=pontos_efetivos)
            if not np.allclose(current_time, time_s, rtol=0, atol=1e-9):
                raise RuntimeError("CH1 e CH2 possuem eixos temporais diferentes")
            current_values = current_a / float(self.config.current_base_a)
        return time_s, voltage_pu, current_values, parametros

    def _validar_captura(
        self, time_s: np.ndarray, voltage_pu: np.ndarray, *, pontos_esperados: Optional[int] = None,
    ) -> None:
        config = self.config
        esperado = pontos_esperados if pontos_esperados is not None else config.points
        if time_s.shape != (esperado,) or voltage_pu.shape != (esperado,):
            raise ValueError(
                f"Captura deve ter {esperado} pontos; recebido {time_s.size}/{voltage_pu.size}"
            )
        if not np.all(np.isfinite(time_s)) or not np.all(np.isfinite(voltage_pu)):
            raise ValueError("Captura contém NaN ou infinito")
        incrementos = np.diff(time_s)
        incremento_esperado = 1.0 / config.fs_hz
        if not np.allclose(incrementos, incremento_esperado, rtol=0, atol=1e-9):
            raise ValueError(f"Eixo temporal não corresponde a {config.fs_hz:.0f} Sa/s")

    @staticmethod
    def _calcular_margem(*, margin_mode: bool, config_points: int, fs_hz: float) -> Tuple[int, int]:
        """``margin on``: 400ms de folga de cada lado (12000 amostras a
        30kSa/s). Os 25ms originais (CHANGELOG/v1.7.md) só cobriam o atraso
        universal de rampa inicial (~20ms); a hipótese LIST:REPeat
        (CHANGELOG/v1.9.md) previu o DISTÚRBIO em si atrasando até ~2,7x a
        janela nominal de 200ms (~540ms), o que motivou uma folga de 500ms
        na v1.9 — mas uma aquisição SINGLE real em modo AUTO (o único modo
        viável neste osciloscópio; ``:ACQuire:DIGitizer ON`` foi investigado
        a fundo e rejeitado, ver CHANGELOG/v1.10.md) entrega só ~32,3-32,7
        mil pontos reais, quase constante e bem abaixo do teto teórico de
        60000 do ``:WAVeform:POINts``. 400ms de cada lado (30000 pontos
        totais) fica ~7,5% abaixo do pior valor real já medido (32258),
        cobrindo o atraso universal (~20ms) com folga confortável mas SEM
        cobrir o pior caso hipotético de 540ms do LIST:REPeat — trade-off
        aceito na ausência de uma correção completa para esse atraso
        (CHANGELOG/v1.10.md tem a investigação: a hipótese foi parcialmente
        confirmada e uma correção candidata já foi aplicada em
        ``ametek_orm.py``, mas não elimina todo o atraso sozinha). Devolve
        (amostras de margem de UM lado, total de amostras incluindo os dois
        lados)."""
        if not margin_mode:
            return 0, config_points
        margem_amostras = int(round(0.4 * fs_hz))
        return margem_amostras, config_points + 2 * margem_amostras

    def _salvar_classe(
        self,
        *,
        tempo_ms: np.ndarray,
        tensao_limpa: np.ndarray,
        tensao_por_snr: Dict[float, np.ndarray],
        ids: List[str],
        corrente: Optional[np.ndarray],
        metadados: List[dict],
        simulated: bool,
    ) -> None:
        """Grava a classe completa. O LAYOUT depende de ``simulated``:

        * ``simulated=True`` (dataset sintético, ``SIM_CAPTURES_PER_CLASS``
          capturas por classe): UM ``.npz`` por classe
          (``{id}_{nome}.npz``) com todas as capturas EMPILHADAS, shape
          ``(total, pontos)`` — o formato que valeu por toda a história do
          projeto. Arquivo por captura aqui não só não traz nada (arrays
          numpy não colidem, e nenhuma captura simulada é uma "condição
          física" irrepetível) como DESTRÓI dados: o nome derivado de
          ``parametros`` se repete entre capturas em pelo menos 11 das 20
          classes (02/03/05 ciclam 5 níveis por ``capture_index % 5``, 18
          alterna 2 valores, 10-17 devolvem dicts LITERAIS constantes), e
          as capturas seguintes sobrescreviam as anteriores em silêncio.
          Um nome determinístico por classe também é naturalmente
          idempotente entre rodadas — nunca gera órfão, nunca precisa de
          limpeza.
        * ``simulated=False`` (bancada real): UM ``.npz`` POR CAPTURA, já
          que ``set capturas N`` pode gerar N capturas por nível e cada uma
          é uma condição física distinta que merece arquivo próprio. O nome
          carrega o parâmetro físico da captura quando existe algum em
          ``parametros`` (ex.: ``sag_pu-0.1``); cai para ``capNN``
          (posição, 1-based) quando não há parâmetro nomeável. Como
          ``set capturas N`` agrupa N capturas no MESMO nível (mesmo
          ``capture_index``, ver ``executar()``), o rótulo derivado do
          parâmetro se REPETE dentro da mesma rodada — a 2ª ocorrência em
          diante ganha sufixo ``_NN`` (1-based por ocorrência:
          ``sag_pu-0.1.npz``, ``sag_pu-0.1_02.npz``, ...), sem o qual as N
          capturas físicas colapsariam num arquivo só. O fallback
          ``capNN`` já é único por captura (``indice`` enumera 0..total-1),
          então não entra no contador.

        Em ambos os casos a escrita é atômica (``.part`` -> ``os.replace``)
        e o ``metadata/{id}_{nome}.jsonl`` é o mesmo: 1 arquivo por classe,
        1 linha por captura.

        Os dados puros (sem ruído) vão direto em ``resultados/``, uma cópia
        com AWGN aplicado por nível de SNR em ``resultados/snr_XXdb/``
        (mesmo nome de arquivo, pasta diferente). Os dados puros são o que
        efetivamente saiu do gerador/instrumento — gravá-los sempre
        significa que aplicar (ou reaplicar) ruído no futuro, com outro SNR
        ou outra técnica, não exige regerar nem recapturar nada.

        Só no caminho REAL o nome do arquivo depende do parâmetro (ou da
        posição) de CADA captura; por isso só ele precisa limpar órfãos.
        Rodar a mesma classe de novo com um conjunto de capturas diferente
        (ex.: ``set capturas 5`` entre duas chamadas de ``run 02``) pode
        deixar arquivos da rodada ANTERIOR sem nenhuma captura desta rodada
        apontando para eles — órfãos, sem linha correspondente no
        ``metadata/{id}_{nome}.jsonl`` recém-escrito. Por isso, só depois
        que TODO arquivo novo desta rodada já foi gravado e promovido
        (``.part`` -> replace) com sucesso — dados por captura E o
        ``metadata.jsonl``, nessa ordem — varremos cada diretório tocado
        nesta chamada (``results_dir``, cada ``snr_XXdb/``, ``corrente/``)
        por arquivos que casem com o prefixo desta classe
        (``{id}_{nome}_*.npz``) mas não estejam entre os nomes que ESTA
        rodada escreveu, e apagamos os que sobrarem. A limpeza roda por
        último, depois do metadata: se o processo morrer antes disso, o
        metadata sobrevivente (velho ou novo) nunca aponta para um arquivo
        que já apagamos — na pior hipótese sobra um órfão que a PRÓXIMA
        rodada bem-sucedida limpa.
        """
        config = self.config
        config.results_dir.mkdir(parents=True, exist_ok=True)

        if simulated:
            self._salvar_classe_simulada(
                tempo_ms=tempo_ms, tensao_limpa=tensao_limpa, tensao_por_snr=tensao_por_snr,
                ids=ids, corrente=corrente, metadados=metadados,
            )
            return

        # Caminho real: a gravação é feita CAPTURA A CAPTURA (ver
        # _iniciar_gravacao_incremental/_salvar_captura/_finalizar_gravacao).
        # Este método continua existindo com a mesma assinatura porque é a
        # porta de entrada usada por quem já tem a classe inteira em memória.
        self._iniciar_gravacao_incremental()
        for indice, metadado_captura in enumerate(metadados):
            self._salvar_captura(
                tempo_ms=tempo_ms,
                tensao_limpa_captura=tensao_limpa[indice],
                tensao_por_snr_captura={
                    snr_db: tensao[indice] for snr_db, tensao in tensao_por_snr.items()
                },
                corrente_captura=None if corrente is None else corrente[indice],
                id_captura=ids[indice],
                metadado=metadado_captura,
            )
        self._finalizar_gravacao(parcial=False)

    def _iniciar_gravacao_incremental(self) -> None:
        """Abre o ``metadata/*.jsonl.part`` da classe e zera o estado de
        gravação. Depois disto cada captura pode ir para o disco sozinha."""
        config = self.config
        config.results_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir = config.results_dir / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        metadata_final = metadata_dir / f"{self.id}_{self.nome.lower()}.jsonl"
        metadata_partial = metadata_final.with_suffix(".jsonl.part")
        self._gravacao = {
            "ocorrencias": {},
            "nomes_por_diretorio": {},
            "metadata_final": metadata_final,
            "metadata_partial": metadata_partial,
            "handle": metadata_partial.open("w", encoding="utf-8"),
            "linhas": 0,
            "indice": 0,
        }

    def _salvar_captura(
        self,
        *,
        tempo_ms: np.ndarray,
        tensao_limpa_captura: np.ndarray,
        tensao_por_snr_captura: Dict[float, np.ndarray],
        corrente_captura: Optional[np.ndarray],
        id_captura: str,
        metadado: dict,
    ) -> None:
        """Grava UMA captura (dados puros + cada ``snr_XXdb/`` + corrente) e
        acrescenta a linha dela ao ``metadata/*.jsonl.part``, com ``flush`` +
        ``fsync`` por linha.

        Escrita atômica por arquivo (``.part`` -> ``os.replace``), igual ao
        comportamento anterior — a diferença é QUANDO ela acontece: antes, no
        fim da classe inteira; agora, assim que a captura existe. É o que
        teria salvo as 7 capturas boas de 08 e as 52 de 03 da sessão 2
        (relatório 01 §3 P1)."""
        config = self.config
        gravacao = self._gravacao
        indice = gravacao["indice"]
        gravacao["indice"] = indice + 1
        rotulo = self._rotulo_da_captura(indice, metadado.get("parametros") or {})
        nome_base = f"{self.id}_{self.nome.lower()}_{rotulo}.npz"
        id_captura_array = np.array([id_captura], dtype=object)

        def _registrar(directory: Path, nome_arquivo: str) -> None:
            gravacao["nomes_por_diretorio"].setdefault(directory, set()).add(nome_arquivo)

        def _gravar(directory: Path, nome_arquivo: str, **arrays) -> None:
            directory.mkdir(parents=True, exist_ok=True)
            final_path = directory / nome_arquivo
            partial_path = final_path.with_suffix(".npz.part")
            with partial_path.open("wb") as handle:
                np.savez(handle, classe=self.nome, id_captura=id_captura_array, **arrays)
            os.replace(partial_path, final_path)
            _registrar(directory, nome_arquivo)

        _gravar(
            config.results_dir, nome_base,
            tempo_ms=tempo_ms, tensao_pu=tensao_limpa_captura[np.newaxis, :],
        )
        for snr_db, tensao in tensao_por_snr_captura.items():
            rotulo_snr = str(int(snr_db)) if float(snr_db).is_integer() else str(snr_db).replace(".", "_")
            _gravar(
                config.results_dir / f"snr_{rotulo_snr}db", nome_base,
                tempo_ms=tempo_ms, tensao_pu=tensao[np.newaxis, :],
            )
        if corrente_captura is not None:
            _gravar(
                config.results_dir / "corrente",
                f"{self.id}_{self.nome.lower()}_{rotulo}_corrente.npz",
                tempo_ms=tempo_ms, corrente_pu=corrente_captura[np.newaxis, :],
            )

        handle = gravacao["handle"]
        handle.write(json.dumps(metadado, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        gravacao["linhas"] += 1

    def _finalizar_gravacao(self, *, parcial: bool) -> None:
        """Promove o ``metadata/*.jsonl.part`` e, só quando a rodada terminou
        INTEIRA (``parcial=False``), remove órfãos de rodadas anteriores.

        Numa rodada abortada no meio, os arquivos da rodada anterior ainda são
        os melhores dados existentes — apagá-los com base numa lista
        incompleta seria trocar dado bom por dado faltando."""
        gravacao = getattr(self, "_gravacao", None)
        if not gravacao:
            return
        self._gravacao = None
        handle = gravacao["handle"]
        try:
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            handle.close()
        if gravacao["linhas"] == 0:
            gravacao["metadata_partial"].unlink(missing_ok=True)
            return
        os.replace(gravacao["metadata_partial"], gravacao["metadata_final"])
        if parcial:
            logger.error(
                "[%s] classe interrompida: %d captura(s) preservada(s) em %s "
                "(metadata PARCIAL; limpeza de órfãos NÃO executada)",
                self.id, gravacao["linhas"], self.config.results_dir,
            )
            return
        prefixo_classe = f"{self.id}_{self.nome.lower()}_"
        for directory, nomes_escritos in gravacao["nomes_por_diretorio"].items():
            for arquivo_existente in directory.glob(f"{prefixo_classe}*.npz"):
                if arquivo_existente.name not in nomes_escritos:
                    arquivo_existente.unlink()

    def _rotulo_da_captura(self, indice: int, parametros: dict) -> str:
        """Nome legível da captura dentro da classe. 1ª ocorrência de um
        rótulo fica sem sufixo (nome histórico); da 2ª em diante `_02`, `_03`,
        ... — sem isso as N capturas de `set capturas N` colapsariam num
        arquivo só (ver docstring de _salvar_classe)."""
        if not parametros:
            # Já único por captura: `indice` percorre 0..total-1.
            return f"cap{indice + 1:02d}"
        chave, valor = next(iter(parametros.items()))
        valor_fmt = f"{valor:g}" if isinstance(valor, float) else str(valor)
        base = f"{chave}-{valor_fmt}"
        ocorrencias = self._gravacao["ocorrencias"]
        ocorrencia = ocorrencias.get(base, 0) + 1
        ocorrencias[base] = ocorrencia
        return base if ocorrencia == 1 else f"{base}_{ocorrencia:02d}"


    def _salvar_classe_simulada(
        self,
        *,
        tempo_ms: np.ndarray,
        tensao_limpa: np.ndarray,
        tensao_por_snr: Dict[float, np.ndarray],
        ids: List[str],
        corrente: Optional[np.ndarray],
        metadados: List[dict],
    ) -> None:
        """Layout histórico do dataset sintético: um ``.npz`` por classe com
        todas as capturas empilhadas (``tensao_pu`` com shape
        ``(total, pontos)``, ``id_captura`` com um id por linha), o mesmo em
        cada ``snr_XXdb/`` e em ``corrente/``. Escrita atômica: tudo grava em
        ``.part`` e só é promovido (``os.replace``) depois que TODOS os
        arquivos terminaram sem erro — nunca deixa uma classe meio gravada.
        """
        config = self.config
        ids_array = np.array(ids, dtype=object)
        final_paths = []

        final_path = config.results_dir / f"{self.id}_{self.nome.lower()}.npz"
        partial_path = final_path.with_suffix(".npz.part")
        with partial_path.open("wb") as handle:
            np.savez(handle, tempo_ms=tempo_ms, tensao_pu=tensao_limpa, classe=self.nome, id_captura=ids_array)
        final_paths.append((partial_path, final_path))

        for snr_db, tensao in tensao_por_snr.items():
            rotulo = str(int(snr_db)) if float(snr_db).is_integer() else str(snr_db).replace(".", "_")
            directory = config.results_dir / f"snr_{rotulo}db"
            directory.mkdir(parents=True, exist_ok=True)
            final_path = directory / f"{self.id}_{self.nome.lower()}.npz"
            partial_path = final_path.with_suffix(".npz.part")
            with partial_path.open("wb") as handle:
                np.savez(handle, tempo_ms=tempo_ms, tensao_pu=tensao, classe=self.nome, id_captura=ids_array)
            final_paths.append((partial_path, final_path))

        if corrente is not None:
            directory = config.results_dir / "corrente"
            directory.mkdir(parents=True, exist_ok=True)
            final_path = directory / f"{self.id}_{self.nome.lower()}_corrente.npz"
            partial_path = final_path.with_suffix(".npz.part")
            with partial_path.open("wb") as handle:
                np.savez(handle, tempo_ms=tempo_ms, corrente_pu=corrente, classe=self.nome, id_captura=ids_array)
            final_paths.append((partial_path, final_path))

        metadata_dir = config.results_dir / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        metadata_final = metadata_dir / f"{self.id}_{self.nome.lower()}.jsonl"
        metadata_partial = metadata_final.with_suffix(".jsonl.part")
        with metadata_partial.open("w", encoding="utf-8") as handle:
            for registro in metadados:
                handle.write(json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n")

        for partial_path, final_path in final_paths:
            os.replace(partial_path, final_path)
        os.replace(metadata_partial, metadata_final)

    def executar(self) -> None:
        simulated = self.osc is None
        niveis_count = self.total_niveis()
        cobertura_por_nivel_ativa = (
            not simulated and self.config.capturas_override is not None and niveis_count > 1
        )
        if cobertura_por_nivel_ativa:
            capturas_por_nivel = self.config.capturas(False)
            total = niveis_count * capturas_por_nivel
        else:
            total = self.config.capturas(simulated)
        logger.info(
            "[%s] %s: %d capturas, SNR=%s dB, modo=%s",
            self.id, self.nome, total, self.config.snr_levels_db,
            "SIMULADO" if simulated else "BANCADA",
        )
        t = tempo(self.config)
        margem_amostras, pontos_efetivos = self._calcular_margem(
            margin_mode=(not simulated and self.config.margin_mode),
            config_points=self.config.points, fs_hz=self.config.fs_hz,
        )
        self._pontos_efetivos_captura_atual = pontos_efetivos
        if not simulated:
            duracao_efetiva = pontos_efetivos / self.config.fs_hz
            pre_trigger_efetivo = self.pre_trigger_s + margem_amostras / self.config.fs_hz
            self.osc.configure_acquisition(
                sample_rate_hz=self.config.fs_hz,
                points=pontos_efetivos,
                duration_s=duracao_efetiva,
                pre_trigger_s=pre_trigger_efetivo,
            )
            self._preparar_acquisicao_real()

        tensao_limpa = np.empty((total, pontos_efetivos), dtype=np.float64)
        tensao_por_snr: Dict[float, np.ndarray] = {
            snr_db: np.empty((total, pontos_efetivos), dtype=np.float64)
            for snr_db in self.config.snr_levels_db
        }
        corrente = (
            np.empty((total, pontos_efetivos), dtype=np.float64)
            if self.config.capture_current else None
        )
        ids: List[str] = []
        metadados: List[dict] = []
        tempo_ms_eixo = None
        if not simulated:
            # Gravação incremental: cada captura vai para o disco assim que
            # sai (ver _salvar_captura). Sem isto, uma falha na captura k
            # jogava fora as k-1 boas, que só existiam em memória —
            # exatamente o que aconteceu com as 7 capturas de 08 e as 52 de
            # 03 na sessão 2 (relatório 01 §3 P1, caminho #1).
            self._iniciar_gravacao_incremental()
        try:
            for indice_global in range(total):
                if cobertura_por_nivel_ativa:
                    capture_index = indice_global // capturas_por_nivel  # nivel, agrupado
                else:
                    capture_index = indice_global
                seed = self.config.base_seed + int(self.id) * 1_000_000 + indice_global
                rng = np.random.default_rng(seed)

                if simulated:
                    voltage_pu, parametros = self.gerar(t, self.config.grid_frequency_hz, capture_index, rng)
                    voltage_pu = np.asarray(voltage_pu, dtype=np.float64)
                    if voltage_pu.shape != (self.config.points,) or not np.all(np.isfinite(voltage_pu)):
                        raise RuntimeError(f"gerar() do experimento {self.id} produziu forma inválida")
                    time_s = t
                    measured_voltage_pu = voltage_pu
                    measured_current_pu = (
                        0.8 * np.sin(2.0 * np.pi * self.config.grid_frequency_hz * t - 0.2)
                        if self.config.capture_current else None
                    )
                else:
                    time_s, measured_voltage_pu, measured_current_pu, parametros = self._capturar_real(
                        capture_index, t, rng,
                    )
                self._validar_captura(time_s, measured_voltage_pu, pontos_esperados=pontos_efetivos)
                tempo_ms_eixo = time_s * 1000.0
                capture_id = f"{self.id}-{indice_global + 1:04d}"
                ids.append(capture_id)
                tensao_limpa[indice_global] = measured_voltage_pu

                medidas_snr = {}
                for snr_db in self.config.snr_levels_db:
                    noise_seed = seed + int(round(snr_db * 1000.0)) + 50_000_000
                    ruidoso = ruido_awgn(measured_voltage_pu, snr_db, np.random.default_rng(noise_seed))
                    tensao_por_snr[snr_db][indice_global] = ruidoso
                    medidas_snr[str(snr_db)] = snr_medida(measured_voltage_pu, ruidoso)

                if corrente is not None and measured_current_pu is not None:
                    corrente[indice_global] = measured_current_pu

                metadados.append({
                    "id_captura": capture_id,
                    "classe": self.nome,
                    "seed": seed,
                    "simulado": simulated,
                    "fs_hz": self.config.fs_hz,
                    "pontos": self.config.points,
                    "parametros": parametros,
                    "snr_medido_db": medidas_snr,
                    "nivel_indice": capture_index if (cobertura_por_nivel_ativa or not simulated) else 0,
                })
                if margem_amostras > 0:
                    metadados[-1]["margem_amostras_antes"] = margem_amostras
                    metadados[-1]["margem_amostras_depois"] = margem_amostras
                    metadados[-1]["amostras_totais"] = pontos_efetivos
                if not simulated:
                    self._salvar_captura(
                        tempo_ms=tempo_ms_eixo,
                        tensao_limpa_captura=tensao_limpa[indice_global],
                        tensao_por_snr_captura={
                            snr_db: tensao[indice_global]
                            for snr_db, tensao in tensao_por_snr.items()
                        },
                        corrente_captura=(
                            None if corrente is None or measured_current_pu is None
                            else corrente[indice_global]
                        ),
                        id_captura=capture_id,
                        metadado=metadados[-1],
                    )
                    logger.info("[%s] captura %d/%d gravada", self.id, indice_global + 1, total)

        except BaseException:
            # Fecha a gravação incremental PRESERVANDO o que já foi para o
            # disco (metadata parcial promovido, limpeza de órfãos suprimida)
            # antes de deixar a exceção subir para executar_bateria().
            if not simulated:
                self._finalizar_gravacao(parcial=True)
            raise

        if not simulated:
            # Forma de onda, modo AC/ACDC e offset são estado PERMANENTE, não
            # transiente: sem desfazer aqui, a classe SEGUINTE capturaria com
            # a senoide clipada que a 05 (HARMONICS) ligou, ou com o offset e
            # o modo ACDC que a 19 (DC_OFFSET) ligou. As classes waveform se
            # salvam por acaso (program_capture() reprograma forma e modo);
            # as nativas, não.
            self.fonte.restaurar_forma_e_modo_padrao()
            self._finalizar_gravacao(parcial=False)
        else:
            self._salvar_classe(
                tempo_ms=tempo_ms_eixo, tensao_limpa=tensao_limpa,
                tensao_por_snr=tensao_por_snr, ids=ids, corrente=corrente,
                metadados=metadados, simulated=True,
            )
        logger.info("[%s] classe concluída: %s", self.id, self.nome)


class ExperimentoNativo(ExperimentoBase):
    """Classes cujo distúrbio é um recurso NATIVO da AMETEK (PULSe/LIST/CSINe).

    Cada subclasse implementa ``configurar(capture_index)``, que manda os
    comandos SCPI nativos por métodos semânticos de ``self.fonte``
    (``trigger_step``/``trigger_pulse``/``configure_harmonics_csine``/...) —
    nunca ``self.fonte.write()`` cru — e devolve os parâmetros físicos
    daquela captura (ex.: nível de sag).
    """

    @abstractmethod
    def configurar(self, capture_index: int) -> Dict[str, float]:
        """Programa o transiente nativo para esta captura na bancada real."""

    def usar_trace(self, capture_index: int) -> bool:
        """Override para classes de mecanismo misto (ex.: 05/HARMONICS):
        sinaliza que este índice deve usar ``gerar()`` + TRACe
        (``program_capture``/``arm_transient``) em vez de ``configurar()``."""
        return False

    def scope_scale_v(self) -> Optional[float]:
        """Override para fixar a escala vertical do osciloscópio antes do
        laço de capturas, quando o pico não muda entre capturas."""
        return None

    def _preparar_acquisicao_real(self) -> None:
        scale = self.scope_scale_v()
        if scale is not None:
            self.osc.set_vertical_scale(1, scale)

    def _capturar_real(self, capture_index, t, rng):
        if self.usar_trace(capture_index):
            voltage_pu, parametros = self.gerar(t, self.config.grid_frequency_hz, capture_index, rng)
            voltage_pu = np.asarray(voltage_pu, dtype=np.float64)
            scale = self.scope_scale_v()
            if scale is not None:
                self.osc.set_vertical_scale(1, scale)
            self.fonte.program_capture(
                voltage_pu,
                base_voltage_rms=self.config.base_voltage_rms,
                frequency_hz=self.config.grid_frequency_hz,
            )
            self.osc.arm()
            self.osc.wait_for_armed()
            self.fonte.arm_transient()
        else:
            parametros = self.configurar(capture_index)
            self.osc.arm()
            self.osc.wait_for_armed()
            self.fonte.arm()
        self.fonte.trigger()
        self.osc.wait_for_trigger_complete(timeout_s=5.0)
        self.fonte.wait_transient_complete(timeout_s=5.0)
        return self._ler_captura(parametros)


class ExperimentoWaveform(ExperimentoBase):
    """Classes que precisam de forma de onda arbitrária (TRACe/LIST) — sempre
    ``gerar()`` + ``program_capture``/``arm_transient``, também na bancada real."""

    def limite_pico_bancada_pu(self) -> Optional[float]:
        """Override para classes cujo pico especificado em ``gerar()`` pode
        exceder o range físico da fonte na tensão de comissionamento (ex.:
        08/TRANSIENT pede 5-10 pu de amplitude ADICIONAL — a 127 Vrms isso
        passa de 900-1800 V, muito acima do teto físico de ~415 Vp no range
        de 300 Vrms). ``None`` (padrão): sem limite adicional.

        Aplica-se SÓ à captura FÍSICA de comissionamento (``_capturar_real``,
        chamado só em ``BENCH_MODE=1``) — nunca a ``gerar()`` nem ao dataset
        SIMULADO, que continuam com a amplitude real da especificação
        (``experimentos.txt``). ``REAL_CAPTURES_PER_CLASS`` existe para
        confirmar que a bancada reproduz o modelo, não para substituir o
        dataset de treino."""
        return None

    def _capturar_real(self, capture_index, t, rng):
        voltage_pu, parametros = self.gerar(t, self.config.grid_frequency_hz, capture_index, rng)
        voltage_pu = np.asarray(voltage_pu, dtype=np.float64)
        if voltage_pu.shape != (self.config.points,) or not np.all(np.isfinite(voltage_pu)):
            raise RuntimeError(f"gerar() do experimento {self.id} produziu forma inválida")
        limite_pico_pu = self.limite_pico_bancada_pu()
        if limite_pico_pu is not None:
            pico_atual_pu = float(np.max(np.abs(voltage_pu)))
            if pico_atual_pu > limite_pico_pu:
                fator = limite_pico_pu / pico_atual_pu
                logger.warning(
                    "[%s] Pico %.3f pu excede o limite físico de comissionamento (%.3f pu); "
                    "escalando por %.3f só nesta captura FÍSICA (gerar()/dataset simulado "
                    "não são afetados).",
                    self.id, pico_atual_pu, limite_pico_pu, fator,
                )
                voltage_pu = voltage_pu * fator
        expected_peak_v = float(np.max(np.abs(voltage_pu))) * self.config.base_voltage_rms * math.sqrt(2.0)
        self.fonte.program_capture(
            voltage_pu,
            base_voltage_rms=self.config.base_voltage_rms,
            frequency_hz=self.config.grid_frequency_hz,
            dc_offset_pu=float(parametros.get("dc_offset_pu", 0.0)),
        )
        # Margem de headroom de 25% sobre o pico programado (arredondamento do
        # firmware, sobremodulação de classes como FLICKER/SWELL, overshoot de
        # transitórios rápidos). Para transitórios de alto fator de crista
        # (>3x o pico nominal) a margem sobe para 60%.
        programmed_peak_v = max(
            expected_peak_v, float(getattr(self.fonte, "last_programmed_peak_v", expected_peak_v))
        )
        nominal_peak_v = self.config.base_voltage_rms * math.sqrt(2.0)
        headroom = 1.60 if programmed_peak_v > 3.0 * nominal_peak_v else 1.25
        self.osc.set_vertical_scale(1, max(programmed_peak_v * headroom, self.config.base_voltage_rms * 0.1))

        self.osc.arm()
        self.osc.wait_for_armed()
        self.fonte.arm_transient()
        self.fonte.trigger()
        self.osc.wait_for_trigger_complete(timeout_s=5.0)
        self.fonte.wait_transient_complete(timeout_s=5.0)
        return self._ler_captura(parametros)


# ---------------------------------------------------------------------------
# Descoberta dos scripts e ponto de entrada
# ---------------------------------------------------------------------------

def _experiment_scripts() -> List[Path]:
    scripts: List[Path] = []
    missing: List[str] = []
    for index in range(1, 21):
        name = f"{index:02d}.py"
        candidates = [directory / name for directory in EXPERIMENT_DIRS if (directory / name).is_file()]
        if len(candidates) != 1:
            missing.append(f"{name} (encontrado em {len(candidates)} pastas)")
            continue
        scripts.append(candidates[0])
    if missing:
        raise FileNotFoundError(f"Experimentos ausentes ou duplicados: {missing}")
    return scripts


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    scripts = _experiment_scripts()
    logger.info(
        "Modo=%s; fs=%.0f Hz; pontos=%d; fundamental=%.1f Hz; tensão-base=%.3f Vrms",
        "BANCADA" if BENCH_MODE else "SIMULADO",
        FS_HZ,
        POINTS,
        GRID_FREQUENCY_HZ,
        BASE_VOLTAGE_RMS,
    )
    try:
        with Bancada.from_env() as bancada:
            resultados = bancada.executar_bateria(scripts)
        falharam = [resultado for resultado in resultados if not resultado.ok]
        if falharam:
            logger.error(
                "%d/%d classes falharam: %s",
                len(falharam), len(resultados),
                ", ".join(f"{resultado.id}({resultado.nome})" for resultado in falharam),
            )
            return 1
        return 0
    except KeyboardInterrupt:
        logger.error("Interrupção pelo usuário; iniciando shutdown")
        return 130
    except BaseException:
        logger.exception("Bateria abortada por falha de infraestrutura")
        return 1


if __name__ == "__main__":
    # Importar como módulo "mestre" (em vez de rodar como __main__) garante
    # que um NN.py carregado dinamicamente por Bancada.executar_experimento()
    # que fizer "import mestre" reaproveite este mesmo módulo já em
    # sys.modules, em vez de reexecutar este arquivo do zero sob outro nome.
    import mestre
    sys.exit(mestre.main())
