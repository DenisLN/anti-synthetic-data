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
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np

from ametek_orm import (
    AmetekMX30, CommunicationError, FalhaFatalDeInstrumento, InstrumentHardwareError,
    ParameterOutOfBoundsError,
)
from sinais import comparar_fisicamente, ruido_awgn, snr_medida, tempo


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("MestreExperimentos")

_HANDLERS_DE_SESSAO: List[logging.Handler] = []


class _HandlerComFlush(logging.FileHandler):
    """``FileHandler`` que dá flush em CADA linha.

    Sem isto, o buffer do arquivo teria sido perdido exatamente no cenário que
    interessa: a fonte travou, o processo morreu e o que estava em memória
    nunca chegou ao disco (relatório 01 §3 P3)."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


def configurar_log_de_sessao(pasta: Path) -> Path:
    """Anexa à pasta da sessão um log de execução e uma transcrição SCPI.

    Fecha o buraco do relatório 01 §1.3 B6: ``logging.basicConfig`` manda só
    para ``sys.stdout``, ``cli.py`` nunca acrescentou ``FileHandler`` e
    ``logs/`` ficou vazio nas duas sessões. Devolve o caminho do log."""
    encerrar_log_de_sessao()
    pasta.mkdir(parents=True, exist_ok=True)
    formato = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    execucao = _HandlerComFlush(pasta / "sessao.log", encoding="utf-8")
    execucao.setFormatter(formato)
    execucao.setLevel(logging.INFO)
    logging.getLogger().addHandler(execucao)
    logging.getLogger().setLevel(logging.INFO)

    transcricao = _HandlerComFlush(pasta / "scpi_transcricao.log", encoding="utf-8")
    transcricao.setFormatter(logging.Formatter("[%(asctime)s.%(msecs)03d] %(message)s", datefmt="%H:%M:%S"))
    transcricao.setLevel(logging.DEBUG)
    scpi = logging.getLogger("AmetekORM.scpi")
    scpi.setLevel(logging.DEBUG)
    # propagate=False: a transcrição não polui o console do operador.
    scpi.propagate = False
    scpi.addHandler(transcricao)

    _HANDLERS_DE_SESSAO.extend([execucao, transcricao])
    logger.info("Log desta sessão em %s", pasta / "sessao.log")
    return pasta / "sessao.log"


def encerrar_log_de_sessao() -> None:
    scpi = logging.getLogger("AmetekORM.scpi")
    for handler in list(_HANDLERS_DE_SESSAO):
        logging.getLogger().removeHandler(handler)
        scpi.removeHandler(handler)
        handler.close()
    _HANDLERS_DE_SESSAO.clear()
    scpi.setLevel(logging.NOTSET)
    scpi.propagate = True


def versao_do_codigo() -> str:
    """``git describe --dirty`` do próprio repositório, ou ``desconhecida``.

    Sem isto não há como saber, a partir de ``resultados/``, que as duas
    sessões de 2026-09-16 rodaram "v1.9 commitado + v1.10 não commitado"."""
    global _VERSAO_CACHE
    if _VERSAO_CACHE is not None:
        return _VERSAO_CACHE
    try:
        import subprocess
        _VERSAO_CACHE = subprocess.run(
            ["git", "describe", "--always", "--dirty", "--tags"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip() or "desconhecida"
    except Exception:  # noqa: BLE001 - nunca impedir uma sessão por causa disto
        _VERSAO_CACHE = "desconhecida"
    return _VERSAO_CACHE


_VERSAO_CACHE: Optional[str] = None


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


def env_int_nao_negativo(name: str, default: int) -> int:
    """Inteiro >= 0; variável ausente OU vazia usa ``default``."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    value = int(raw)
    if value < 0:
        raise ValueError(f"{name} deve ser inteiro >= 0; recebido {value!r}")
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
# Seed base da sessão. Seed de cada captura = BASE_SEED + int(id) × 1 000 000
# + índice global da captura (ExperimentoBase.seed_da_captura); o ruído AWGN
# deriva dela. Mesma seed => mesmas formas, parâmetros e plano de capturas.
# Mutável em runtime pela CLI ("set seed N", v1.13); vale na próxima
# Bancada.from_env, como CAPTURAS_OVERRIDE.
BASE_SEED_PADRAO = 20_260_827
BASE_SEED = env_int_nao_negativo("BASE_SEED", BASE_SEED_PADRAO)
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


class ValidacaoFisicaError(ValueError):
    """A captura saiu do instrumento, mas não corresponde ao que a classe
    pediu (nível base, profundidade do evento ou conteúdo harmônico).

    Determinística por natureza: repetir a mesma classe com a mesma
    configuração produziria o mesmo desvio — por isso entra em
    ``Bancada.ERROS_DETERMINISTICOS`` e não é retentada. As capturas
    suspeitas continuam GRAVADAS, com ``validacao_fisica.ok=false`` no
    metadata: dado marcado é melhor que dado apagado, e é o que permite
    diagnosticar o problema depois."""


# Extremo físico previsto = pico programado × fator MEDIDO da classe × esta
# margem. Fatores em logica/calibracao_extremos.json (origem e definição lá).
MARGEM_FATOR_EXTREMO = env_float("MARGEM_FATOR_EXTREMO", 1.10)
CALIBRACAO_EXTREMOS_PATH = Path(__file__).resolve().parent / "calibracao_extremos.json"


def carregar_fatores_extremo(caminho: Path = CALIBRACAO_EXTREMOS_PATH) -> Dict[str, float]:
    """Fatores (extremo medido / pico programado) por classe. Arquivo ausente
    ou ilegível LEVANTA: sem ele a pré-validação de pico não tem base, e
    seguir sem ela seria enfraquecer a proteção em silêncio."""
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    fatores = {str(k).zfill(2): float(v) for k, v in dados["fatores"].items()}
    if not fatores or any(not math.isfinite(v) or v <= 0 for v in fatores.values()):
        raise ValueError(f"Fatores de extremo inválidos em {caminho}: {fatores}")
    return fatores


def fator_extremo_da_classe(classe_id: str, fatores: Dict[str, float]) -> float:
    """Nunca abaixo de 1 (não prever extremo menor que o programado); classe
    sem medida usa o MAIOR fator conhecido."""
    fator = fatores.get(str(classe_id).zfill(2), max(fatores.values()))
    return max(1.0, float(fator))


# Classe cuja calibração é a de uma senoide PURA (01/NORMAL): a parte do
# extremo que existe mesmo sem distúrbio. O resto do fator de cada classe é
# atribuído ao distúrbio (ver extremo_previsto_com_disturbio_v).
CLASSE_REFERENCIA_EXTREMO = "01"


def fator_referencia_extremo(fator_da_classe: float, fatores: Dict[str, float]) -> float:
    """Fator da senoide pura, nunca acima do da classe. Sem a 01 na
    calibração, usa o próprio fator da classe — o caso mais conservador (o
    distúrbio reduzido não ganha nada no extremo previsto)."""
    referencia = fatores.get(CLASSE_REFERENCIA_EXTREMO)
    if referencia is None:
        return float(fator_da_classe)
    return min(float(fator_da_classe), max(1.0, float(referencia)))


def extremo_previsto_com_disturbio_v(
    pico_v: float, pico_modelo_v: float, fracao: float, *,
    fator: float, fator_referencia: float, margem: Optional[float] = None,
) -> float:
    """Extremo físico previsto de uma captura com o distúrbio reduzido a
    ``fracao`` (forma = senoide + fracao × (modelo - senoide)).

    margem × (fator_ref × pico + fracao × (fator - fator_ref) × pico_modelo)

    - ``fator_ref × pico``: a parte que a saída faz mesmo sem distúrbio
      (senoide pura, classe 01: 1,063), sobre o pico da forma REDUZIDA;
    - o excesso que o distúrbio do MODELO produziu na calibração
      ((fator - fator_ref) × pico_modelo) escala com a fração: a oscilação
      da saída é proporcional ao degrau que a excita — 08 caracterizada em
      2026-09-30 (T8-4): sobressinal ~0,38 e subsinal ~0,58 do degrau,
      constantes de 104 V a 339 V.
    Com ``fracao`` = 1 (pico = pico_modelo) reduz-se exatamente à fórmula da
    v1.12, pico × fator × margem. Convexa em ``fracao`` (máximo de |·| de
    funções afins + termo linear): a bissecção do limite de bancada acha o
    maior valor que cabe."""
    margem = MARGEM_FATOR_EXTREMO if margem is None else margem
    return margem * (fator_referencia * pico_v + fracao * (fator - fator_referencia) * pico_modelo_v)


# Limite de bancada (v1.13, decisão do dono para 220 V: opção b). Nas classes
# WAVEFORM cujo extremo previsto passa do teto, a captura FÍSICA reduz só a
# amplitude do distúrbio (forma = senoide + fração × (gerar() - senoide)) até
# o extremo previsto caber, grava a fração e os parâmetros aplicados no
# metadata e valida contra a forma realmente programada. gerar()/dataset
# simulado não mudam. Abaixo de LIMITE_BANCADA_FRACAO_MINIMA a captura é
# PULADA (a forma já não representaria a classe). LIMITE_BANCADA_DISTURBIO=0
# volta ao comportamento da v1.12 (opção a: pular). Nativas (PULSe/LIST/
# CSINe) não reduzem: o nível É o parâmetro discreto da classe e um nível
# reduzido coincidiria com o anterior.
LIMITE_BANCADA_DISTURBIO = env_bool("LIMITE_BANCADA_DISTURBIO", default=True)
LIMITE_BANCADA_FRACAO_MINIMA = env_float("LIMITE_BANCADA_FRACAO_MINIMA", 0.25)
if LIMITE_BANCADA_FRACAO_MINIMA > 1.0:
    raise ValueError("LIMITE_BANCADA_FRACAO_MINIMA deve estar em (0, 1]")


class PicoFisicoExcedidoError(RuntimeError):
    """O osciloscópio mediu (taxa cheia, ``:MEASure:VMAX?/VMIN?``) um extremo
    acima do teto da classe, ou a classe exige essa medida e ela não veio.

    DE PROPÓSITO fora de ``ERROS_CAPTURA_DESCARTAVEL`` (não é ``ValueError``/
    ``InstrumentHardwareError``/``TimeoutError``): descartar e seguir para a
    próxima captura faria uma varredura de amplitude CRESCENTE (``run 08`` com
    ``set capturas N``) continuar subindo depois de passar do teto. Está em
    ``Bancada.ERROS_DETERMINISTICOS``: a classe para na hora, sem retry; a
    captura que passou do teto é GRAVADA antes (é a evidência)."""


VALIDACAO_FISICA = env_bool("VALIDACAO_FISICA", default=True)
VALIDACAO_TOL_ENVELOPE = env_float("VALIDACAO_TOL_ENVELOPE", 0.15)
VALIDACAO_TOL_THD = env_float("VALIDACAO_TOL_THD", 0.20)

# Classes que o ``run all`` FÍSICO pula (ids separados por vírgula; vazio =
# nenhuma, o padrão). ``run <NN>`` isolado continua possível, com a
# confirmação digitada de sempre, e o dataset simulado não é afetado. A 08
# ficou aqui de 14:44 a 15:25 de 2026-09-30 (pico de 415,3 V no teto de
# 415,8 V) e voltou depois de redimensionada pelos extremos MEDIDOS
# (docs/analise-2026-09-30/ANALISE.md, T8-4: VMAX 230 V / VMIN -334 V).
BATERIA_EXCLUIR = tuple(
    item.strip().zfill(2)
    for item in os.environ.get("BATERIA_EXCLUIR", "").split(",")
    if item.strip()
)

# Erros que invalidam só UMA captura: ExperimentoBase.executar() loga,
# descarta a captura (não grava nada para ela) e segue para a PRÓXIMA
# posição do plano — nunca propaga para executar_bateria(). Pedido do dono
# em 2026-09-22, reagindo ao readback do p01/p02 ("a captura falha na
# hora"): "não aborte a bateria de testes, apenas log e descarte — abortar
# gasta MUITO tempo" (reexecutar a classe inteira do zero, até 3x, custava
# exatamente isso).
#
# - InstrumentHardwareError: erro 19 "Illegal during transient" (p01),
#   divergência de readback (p02), ou qualquer outro assert_no_errors()
#   dentro de _capturar_real() — sempre sobre O QUE ACABOU DE SER
#   programado/armado/disparado NESTA captura, nunca sobre o estado da
#   conexão em si (isso é CommunicationError, de propósito FORA desta
#   lista — ver o comentário em executar()).
# - TimeoutError: espera de IDLE/ARM/trigger de UMA captura (ex.: o -113
#   esporádico documentado desde o v1.7).
# - ValueError (cobre ParameterOutOfBoundsError): _validar_captura() ou um
#   nível fora de faixa não pego pela pré-validação do p04 (classes de
#   parâmetro contínuo, onde _indices_viaveis() não filtra por não
#   conhecer o valor de antemão) — outro capture_index pode estar dentro
#   da faixa, vale tentar o próximo.
#
# Deliberadamente NÃO inclui CommunicationError/FalhaFatalDeInstrumento
# (a serial caiu / não é seguro recuperar um estado conhecido — isso
# continua abortando a bateria imediatamente, ver AGENTS.md "Limites
# inegociáveis") nem RuntimeError (gerar() com forma inválida é bug de
# código, não falha intermitente de hardware — descartar captura a
# captura só adiaria a mesma exceção até sobrar zero, sem nunca avisar).
ERROS_CAPTURA_DESCARTAVEL = (InstrumentHardwareError, TimeoutError, ValueError)


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
    diagnostico_mode: bool = False
    # ``capturas_padrao`` da classe em execução (atributo de classe de
    # ``ExperimentoBase``), preenchido por ``ExperimentoBase.__init__`` com
    # ``dataclasses.replace`` — a ``Config`` da ``Bancada`` continua sem
    # classe nenhuma (1). Assim ``capturas()`` já devolve o número EFETIVO
    # da classe para quem chama de dentro dela (``executar()``, e
    # ``gerar()``/``configurar()`` de 04/06/08/09/19), sem cada script
    # precisar repassar o próprio padrão.
    capturas_padrao_classe: int = 1

    def capturas(self, simulated: bool) -> int:
        """Capturas desta classe (por nível, nas classes com ``NIVEIS``).

        Simulado: ``SIM_CAPTURES_PER_CLASS``, sempre — o dataset não depende
        de padrão de bancada nem da CLI. Bancada: o MAIOR entre o valor
        global (``set capturas N`` quando o operador digitou, senão
        ``REAL_CAPTURES_PER_CLASS``, padrão 1) e o padrão da classe — pedido
        do dono (2026-10-07): ``set capturas 3`` numa classe de padrão 6 roda
        6; numa de padrão 1, 3. A CLI avisa quando o padrão vence."""
        if simulated:
            return self.sim_captures_per_class
        global_ = (
            self.capturas_override if self.capturas_override is not None
            else self.real_captures_per_class
        )
        return max(global_, self.capturas_padrao_classe)


@dataclass
class ResultadoClasse:
    """Resultado de uma classe dentro da bateria — ver ``Bancada.executar_bateria``."""

    id: str
    nome: str
    ok: bool
    motivo: Optional[str] = None
    # Capturas individuais perdidas dentro de uma classe que, no total,
    # terminou ``ok=True`` (ver ERROS_CAPTURA_DESCARTAVEL/ExperimentoBase.
    # executar()). ``descartadas`` = erro (nada gravado); ``invalidas`` =
    # gravada, mas a validação física (P05) reprovou o conteúdo.
    descartadas: int = 0
    invalidas: int = 0
    # Capturas do plano que a pré-validação (``_indices_viaveis``) pulou ANTES
    # de programar (rms/pico/extremo previsto acima do teto) — nada foi
    # enviado à fonte para elas. Não é falha: é o limite da bancada.
    puladas: int = 0

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
                # Limite de PICO do software, validado por configure_safe_baseline.
                # O VOLTage:HIGH da fonte é RMS e recebe EUT_MAX_VOLTAGE_RMS (ver
                # lá; T12 em docs/analise-2026-09-30). A proteção de pico é de
                # software: _indices_viaveis (previsto) + medir_extremos (medido).
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

    # Erros que NUNCA mudam de resultado numa nova tentativa: o parâmetro
    # pedido é fisicamente impossível nesta configuração de bancada. Retentar
    # é garantir 3x o mesmo erro e 3x o desgaste — foi o que a classe 03 fez
    # na sessão 2 (52 capturas físicas para terminar com zero arquivos,
    # relatório 01 §3 P1 caminho #4). A lista é DELIBERADAMENTE estreita:
    # ``ValueError`` em geral (ex.: contagem de pontos da captura) pode ser
    # intermitente e continua ganhando as 3 tentativas.
    ERROS_DETERMINISTICOS = (ParameterOutOfBoundsError, ValidacaoFisicaError, PicoFisicoExcedidoError)

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
            descartadas = 0
            invalidas = 0
            puladas = 0
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
                    experimento = self._instanciar_experimento(experimento_cls)
                    experimento.executar()
                    sucesso = True
                    descartadas = getattr(experimento, "_capturas_descartadas_count", 0)
                    invalidas = getattr(experimento, "_capturas_invalidas_count", 0)
                    puladas = getattr(experimento, "_capturas_puladas_count", 0)
                    break
                except (CommunicationError, FalhaFatalDeInstrumento):
                    logger.error(
                        "[%s] Falha de infraestrutura — abortando o restante da bateria", class_id
                    )
                    raise
                except self.ERROS_DETERMINISTICOS as exc:
                    ultimo_erro = str(exc)
                    logger.error(
                        "[%s] FALHOU com erro DETERMINÍSTICO (%s) — não será retentado: "
                        "o mesmo parâmetro produziria o mesmo erro nas tentativas "
                        "seguintes. Corrija a configuração da classe ou a tensão base.",
                        class_id, exc,
                    )
                    self.recuperar_estado_seguro()
                    break
                except Exception as exc:
                    ultimo_erro = str(exc)
                    logger.exception(
                        "[%s] FALHOU (tentativa %d/%d)", class_id, tentativa, self.MAX_TENTATIVAS_POR_CLASSE,
                    )
                    if tentativa < self.MAX_TENTATIVAS_POR_CLASSE:
                        self.recuperar_estado_seguro()

            if sucesso:
                resultados.append(ResultadoClasse(
                    class_id, nome, ok=True, descartadas=descartadas, invalidas=invalidas,
                    puladas=puladas,
                ))
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
            elif resultado.descartadas or resultado.invalidas:
                logger.warning(
                    "  OK COM RESSALVAS [%s] %s: %d captura(s) descartada(s) por erro, "
                    "%d marcada(s) inválida(s) na validação física (gravadas mesmo assim, "
                    "ver 'validacao_fisica' no metadata)",
                    resultado.id, resultado.nome, resultado.descartadas, resultado.invalidas,
                )
            if resultado.ok and resultado.puladas:
                logger.warning(
                    "  [%s] %s: %d captura(s) do plano PULADA(S) pela pré-validação (limite "
                    "rms/pico da fonte ou extremo previsto) — nada programado para elas",
                    resultado.id, resultado.nome, resultado.puladas,
                )
        return resultados

    def _instanciar_experimento(self, experimento_cls: type) -> "ExperimentoBase":
        """Seam de teste: ``executar_bateria`` sempre cria a instância por
        aqui, nunca inline, para poder ler ``_capturas_descartadas_count``/
        ``_capturas_invalidas_count`` dela depois de ``.executar()`` retornar
        (ver ResultadoClasse.descartadas/invalidas) e para que um teste possa
        injetar uma instância já preparada (stubs de ``_capturar_real`` etc.)
        sem reconstruir toda a cadeia de carregamento dinâmico do script."""
        return experimento_cls(self)

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
    # Capturas PADRÃO desta classe na bancada real — por nível nas classes
    # com ``NIVEIS`` (02/03/05), como ``set capturas N``. 1 = comportamento
    # até a v1.12. Pedido do dono (2026-10-07): 3 nas classes que SORTEIAM
    # parâmetros em ``gerar()`` (04, 06, 07, 08, 09, 17, 19, 20), 1 nas
    # determinísticas. Não afeta o dataset simulado (``SIM_CAPTURES_PER_CLASS``)
    # nem a regra de cobertura determinística/caracterização da 08, que
    # continua exigindo ``set capturas`` digitado pelo operador
    # (``capturas_override``). Tabela completa: README, seção "Capturas por
    # classe".
    capturas_padrao: int = 1

    def __init__(self, bancada: Bancada):
        padrao = self.capturas_padrao
        if isinstance(padrao, bool) or not isinstance(padrao, int) or padrao < 1:
            raise ValueError(
                f"[{getattr(self, 'id', '?')}] capturas_padrao deve ser inteiro >= 1; recebido {padrao!r}"
            )
        self.bancada = bancada
        config = bancada.config
        # Só a Config de verdade carrega o padrão; substitutos mínimos (ex.:
        # _ConfigOffline de analisar_sessao.py) seguem como vieram.
        if isinstance(config, Config):
            config = replace(config, capturas_padrao_classe=padrao)
        self.config = config
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

    def dimensionar_capturas(self, simulated: bool) -> Tuple[bool, int, int]:
        """(agrupa por nível?, capturas por nível, total planejado) — ANTES
        da poda de ``_indices_viaveis``.

        Classe com ``NIVEIS`` agrupa N capturas por nível quando o operador
        digitou ``set capturas`` OU quando o número efetivo passa de 1 (padrão
        da classe/``REAL_CAPTURES_PER_CLASS``). Com 1 e sem ``set capturas``,
        roda só o nível 0, exatamente como até a v1.12. Usado também pela CLI
        (``status``/``list``) para mostrar o número efetivo por classe."""
        niveis_count = self.total_niveis()
        capturas = self.config.capturas(simulated)
        por_nivel = (
            not simulated and niveis_count > 1
            and (self.config.capturas_override is not None or capturas > 1)
        )
        if por_nivel:
            return True, capturas, niveis_count * capturas
        return False, 1, capturas

    def seed_da_captura(self, indice_global: int) -> int:
        """Seed da captura ``indice_global`` desta classe — a ÚNICA fórmula
        (``executar()`` e a pré-validação de pico usam esta; 04/19 a repetem
        em ``configurar()`` com o id fixo). Gravada no metadata (``seed``)."""
        return int(self.config.base_seed) + int(self.id) * 1_000_000 + int(indice_global)

    def plano_de_capturas(self, simulated: bool) -> List[Tuple[int, int]]:
        """Plano ``(indice_global, capture_index)`` de ``executar()``, ANTES
        da poda de ``_indices_viaveis``. ``indice_global`` entra na seed;
        ``capture_index`` escolhe o nível (``indice // N`` quando agrupado)."""
        por_nivel, capturas_por_nivel, total = self.dimensionar_capturas(simulated)
        return [
            (indice, indice // capturas_por_nivel if por_nivel else indice)
            for indice in range(total)
        ]

    def grava_trace(self, capture_index: int) -> bool:
        """Esta captura grava TRACEs na Flash da fonte (``program_capture``)?
        Waveform: sempre. Nativa: só os índices de ``usar_trace`` (05 a 30%)."""
        return False

    @abstractmethod
    def _capturar_real(
        self, capture_index: int, t: np.ndarray, rng: np.random.Generator
    ) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], Dict[str, float]]:
        """Produz uma captura física: programa a fonte, dispara, lê o
        osciloscópio. Implementado por ``ExperimentoNativo``/``ExperimentoWaveform``."""

    def _preparar_acquisicao_real(self) -> None:
        """Hook opcional, chamado uma vez antes do laço de capturas (bancada
        real), para ajustes que não mudam entre capturas."""

    def _contexto_da_sessao(self) -> dict:
        """Tudo que só existia no console do operador e, por isso, não podia
        ser recuperado de ``resultados/`` (relatório 01 §1.3 B6 / §4 item 9):
        f0, tensão base, fator de probe, pré-trigger da classe, escala
        vertical, índice do trigger dentro do registro, flags da sessão,
        versão do código e IDN dos dois instrumentos."""
        osc = self.osc
        contexto = {
            "f0_hz": self.config.grid_frequency_hz,
            "tensao_base_rms": self.config.base_voltage_rms,
            "probe_tensao": VOLTAGE_PROBE_ATTENUATION,
            "pre_trigger_s": float(getattr(self, "pre_trigger_s", 0.0)),
            # Desde 2026-09-22 (P10) a margem de captura deixou de ser opt-in
            # (era "margin_mode"/`set margin on|off`) — passa a ser aplicada
            # sempre, então o que vale registrar são os valores em si, não
            # mais um booleano "estava ligado?". margem_amostras_antes/depois
            # (gravados logo abaixo, por captura) são os números REALMENTE
            # usados; estes dois são a config-fonte (útil se alguém rodou com
            # MARGEM_ANTES_S/MARGEM_DEPOIS_S sobrescritos por ambiente).
            "margem_antes_s": ExperimentoBase.MARGEM_ANTES_S,
            "margem_depois_s": ExperimentoBase.MARGEM_DEPOIS_S,
            "diagnostico_mode": bool(self.config.diagnostico_mode),
            # Seed base da sessão (``set seed``): com ela + ``nivel_indice``
            # + ``capturas_override`` qualquer captura é reproduzível.
            "base_seed": int(self.config.base_seed),
            "capturas_override": self.config.capturas_override,
            "capturas_padrao_classe": int(getattr(self.config, "capturas_padrao_classe", 1)),
            "versao_codigo": versao_do_codigo(),
            "idn_fonte": str(getattr(self.fonte, "idn", "")),
            "idn_osciloscopio": str(getattr(osc, "idn", "")),
            "escritas_trace_na_conexao": int(getattr(self.fonte, "escritas_trace", 0)),
        }
        # indice_trigger vem da preamble do osciloscópio (ver
        # oscilloscope_orm.get_waveform): é a única informação que diz onde o
        # trigger caiu DENTRO do registro.
        indice_trigger = getattr(osc, "ultimo_indice_trigger", None)
        if isinstance(indice_trigger, (int, float)):
            contexto["indice_trigger"] = int(indice_trigger)
        escala = getattr(osc, "ultima_escala_vertical_v", None)
        if isinstance(escala, (int, float)):
            contexto["escala_vertical_v_div"] = float(escala)
        return contexto

    def forma_esperada_para_validacao(
        self, capture_index: int, t: np.ndarray, seed: int
    ) -> Optional[np.ndarray]:
        """Forma de onda que a classe PEDIU nesta captura, em pu, para a
        validação física pós-captura.

        Padrão: reexecuta ``gerar()`` com um rng novo da MESMA seed (mesma
        técnica de ``analisar_sessao.py``). ``ExperimentoWaveform`` devolve a
        forma REALMENTE programada (já escalada por
        ``limite_pico_bancada_pu``), que pode diferir de ``gerar()``."""
        try:
            voltage_pu, _ = self.gerar(
                t, self.config.grid_frequency_hz, capture_index, np.random.default_rng(seed),
            )
        except Exception:  # noqa: BLE001 - validação nunca derruba a captura
            logger.warning("[%s] não foi possível reconstruir a forma esperada", self.id, exc_info=True)
            return None
        return np.asarray(voltage_pu, dtype=np.float64)

    def _validar_fisicamente(
        self, capture_index: int, t: np.ndarray, seed: int, medido_pu: np.ndarray,
        *, margem_antes: int = 0,
    ) -> Optional[dict]:
        """Compara o que saiu do instrumento com o que a classe pediu.

        Complemento do readback SCPI de ``arm()``: aquele confere o que a
        fonte DIZ ter programado, este confere o que ela FEZ. H-NATIVO
        (relatório 01 §1.2) passou em silêncio por não existir nenhum dos
        dois.

        Compara só a janela do registro que corresponde à forma esperada
        (``margem_antes`` .. ``margem_antes + len(esperado)``): o registro
        físico tem 20 ms ANTES do trigger (saída em 0 V por projeto, antes do
        transiente) e 50 ms DEPOIS que a forma esperada não tem. Com o
        registro inteiro, os 20 ms em 0 V reprovavam o mínimo do envelope de
        TODA captura (0,01 pu, sessão 2026-09-30 run04, classes 05-20) e os
        50 ms extras quebravam o número inteiro de ciclos da THD (18: 1,60%
        contra 0,28% na janela alinhada)."""
        if not VALIDACAO_FISICA:
            return None
        esperado = self.forma_esperada_para_validacao(capture_index, t, seed)
        if esperado is None:
            return None
        medido_pu = np.asarray(medido_pu, dtype=np.float64)[margem_antes : margem_antes + len(esperado)]
        if medido_pu.size != len(esperado):
            logger.warning(
                "[%s] registro tem %d amostras na janela alinhada; esperado %d — validação física não calculada",
                self.id, medido_pu.size, len(esperado),
            )
            return None
        excluidos = tuple(self.ciclos_excluidos_da_validacao(capture_index))
        if excluidos:
            # Remove ciclos INTEIROS dos dois lados: a concatenação continua
            # contínua em fase, então envelope/THD/crista seguem válidos.
            n = int(round(self.config.fs_hz / self.config.grid_frequency_hz))
            manter = [k for k in range(len(esperado) // n) if k not in excluidos]
            esperado = np.concatenate([np.asarray(esperado)[k * n : (k + 1) * n] for k in manter])
            medido_pu = np.concatenate([medido_pu[k * n : (k + 1) * n] for k in manter])
        try:
            return comparar_fisicamente(
                esperado, medido_pu,
                fs_hz=self.config.fs_hz, f0=self.config.grid_frequency_hz,
                tol_envelope=VALIDACAO_TOL_ENVELOPE, tol_thd=VALIDACAO_TOL_THD,
            )
        except Exception:  # noqa: BLE001
            logger.warning("[%s] validação física não pôde ser calculada", self.id, exc_info=True)
            return None

    def ciclos_excluidos_da_validacao(self, capture_index: int) -> Sequence[int]:
        """Ciclos (índices na janela nominal) que a validação física ignora.
        Padrão: nenhum. A 08 exclui o ciclo do impulso e o seguinte: a fonte
        reproduz o impulso de 66 µs como uma oscilação limitada em banda, que
        nunca coincide com o modelo nesse trecho (ANALISE.md, T8-3); o que
        importa ali é o pico, conferido por ``medir_extremos``."""
        return ()

    # A medida de extremos na taxa cheia é OBRIGATÓRIA nesta classe? Sem ela
    # não há prova de que a captura ficou dentro do teto (ver 08).
    exige_medida_de_pico: bool = False
    # Teto dos extremos MEDIDOS, como fração de ``fonte.max_peak_v``. 1,0 para
    # todas as classes (é o limite configurado); a 08 usa menos (ver lá).
    fracao_teto_pico_medido: float = 1.0

    def _medir_extremos_fisicos(self) -> Dict[str, object]:
        """Mede VMAX/VMIN da última aquisição no osciloscópio e devolve o que
        vai para o metadata. Nunca levanta: quem decide abortar é
        ``_conferir_extremos_fisicos`` — DEPOIS de a captura ser gravada."""
        osc = self.osc
        medir = getattr(osc, "medir_extremos", None)
        if not callable(medir):
            return {"extremos_indisponiveis": "osciloscópio sem medir_extremos"}
        try:
            vmax, vmin = medir(1)
            vmax, vmin = float(vmax), float(vmin)
        except Exception as exc:  # noqa: BLE001 - decisão fica para _conferir_extremos_fisicos
            logger.warning("[%s] medida de extremos no osciloscópio falhou: %s", self.id, exc)
            return {"extremos_indisponiveis": f"{type(exc).__name__}: {exc}"}
        teto = self.fracao_teto_pico_medido * float(getattr(self.fonte, "max_peak_v", float("inf")))
        return {"pico_medido_v": vmax, "vale_medido_v": vmin, "teto_extremos_v": teto}

    def _conferir_extremos_fisicos(self, capture_id: str, extremos: Dict[str, object]) -> None:
        if "extremos_indisponiveis" in extremos:
            if self.exige_medida_de_pico:
                raise PicoFisicoExcedidoError(
                    f"[{self.id}] captura {capture_id}: a classe exige a medida de pico na taxa "
                    f"cheia e ela não veio ({extremos['extremos_indisponiveis']}). Classe parada "
                    "sem retry — sem essa medida não há prova de que a saída ficou no teto."
                )
            return
        teto = float(extremos["teto_extremos_v"])
        maior = max(abs(float(extremos["pico_medido_v"])), abs(float(extremos["vale_medido_v"])))
        if maior > teto:
            raise PicoFisicoExcedidoError(
                f"[{self.id}] captura {capture_id}: extremo MEDIDO pelo osciloscópio "
                f"{maior:.1f} V > teto {teto:.1f} V (pico {extremos['pico_medido_v']:.1f} V, "
                f"vale {extremos['vale_medido_v']:.1f} V). Captura GRAVADA; classe parada sem "
                "retry. CONFIRME NO PAINEL que a fonte está bem."
            )

    def forma_e_parametros_para_bancada(
        self, capture_index: int, t: np.ndarray, seed: int,
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """Forma (pu) e parâmetros que ESTA captura vai programar, calculados
        sem tocar a fonte — mesma seed que ``executar()`` usa.
        ``ExperimentoWaveform`` sobrescreve para aplicar ``forma_para_bancada``
        (limite de bancada; 08)."""
        voltage_pu, parametros = self.gerar(
            t, self.config.grid_frequency_hz, capture_index, np.random.default_rng(seed),
        )
        return np.asarray(voltage_pu, dtype=np.float64), dict(parametros)

    def forma_prevista_para_bancada(
        self, capture_index: int, t: np.ndarray, seed: int,
    ) -> np.ndarray:
        return self.forma_e_parametros_para_bancada(capture_index, t, seed)[0]

    def _pico_da_forma_v(self, forma_pu: np.ndarray, capture_index: int) -> float:
        nominal_v = self.config.base_voltage_rms * math.sqrt(2.0)
        pico = float(np.max(np.abs(forma_pu))) * nominal_v
        rms = self.tensao_rms_programada(capture_index)
        if rms is not None:
            pico = max(pico, float(rms) * math.sqrt(2.0))
        return pico

    def pico_programado_v(self, capture_index: int, t: np.ndarray, seed: int) -> float:
        """Pico que a captura PROGRAMA — a definição usada para medir os fatores
        de ``calibracao_extremos.json`` (mudar aqui exige recalibrar)."""
        return self._pico_da_forma_v(self.forma_prevista_para_bancada(capture_index, t, seed), capture_index)

    def _extremo_previsto_da_forma_v(self, pico_v: float, parametros: Dict[str, float]) -> float:
        """Modelo do extremo físico a partir do pico programado e dos
        parâmetros de bancada da captura (ver ``extremo_fisico_previsto_v``)."""
        proprio = getattr(self, "excursao_fisica_prevista_v", None)
        if callable(proprio):
            excursao = proprio()
            if excursao is not None:
                return float(excursao)
        fatores = carregar_fatores_extremo()
        fator = fator_extremo_da_classe(self.id, fatores)
        k = float(parametros.get("fator_disturbio_bancada", 1.0))
        if k >= 1.0:
            return pico_v * fator * MARGEM_FATOR_EXTREMO
        return extremo_previsto_com_disturbio_v(
            pico_v, float(parametros["pico_programado_modelo_v"]), k,
            fator=fator, fator_referencia=fator_referencia_extremo(fator, fatores),
        )

    def extremo_fisico_previsto_v(self, capture_index: int, t: np.ndarray, seed: int) -> float:
        """|Extremo| que a SAÍDA deve atingir: o pico programado não basta —
        sessão 2026-09-30 15:26 mediu até 1,46× o programado (volta de
        interrupção da 16) por causa da oscilação da saída. Classes com modelo
        próprio da resposta (08, ``excursao_fisica_prevista_v``) usam o delas.
        Captura com o distúrbio reduzido pelo limite de bancada (v1.13) usa
        ``extremo_previsto_com_disturbio_v``; sem redução, a fórmula é a da
        v1.12 (pico × fator × margem)."""
        forma, parametros = self.forma_e_parametros_para_bancada(capture_index, t, seed)
        return self._extremo_previsto_da_forma_v(self._pico_da_forma_v(forma, capture_index), parametros)

    def tensao_rms_programada(self, capture_index: int) -> Optional[float]:
        """Tensão rms que ESTA captura vai pedir à fonte, quando ela é
        conhecida antes de programar nada. ``None`` = desconhecida (a
        pré-validação não opina). Ver ``_indices_viaveis``."""
        return None

    def avaliar_captura_na_bancada(
        self, indice_global: Optional[int], capture_index: int, *,
        t: Optional[np.ndarray] = None, seed: Optional[int] = None,
    ) -> Dict[str, object]:
        """Tudo o que a pré-validação sabe de UMA captura, sem tocar a fonte:
        rms e pico programados, extremo previsto, teto, se cabe e por quê, e
        o fator de redução do distúrbio (limite de bancada, v1.13). Fonte
        única de ``_indices_viaveis``, do metadata (``pico_programado_v``/
        ``extremo_previsto_v``) e de ``scripts/relatorio_limites_bancada.py``."""
        fonte = self.fonte
        teto_rms = float(getattr(fonte, "max_voltage_rms", float("inf")))
        teto_pico = float(getattr(fonte, "max_peak_v", float("inf")))
        # Teto do extremo PREVISTO = o mesmo teto do extremo MEDIDO
        # (_conferir_extremos_fisicos): 1,0 × max_peak_v; 0,9 na 08.
        teto_extremo = self.fracao_teto_pico_medido * teto_pico
        info: Dict[str, object] = {
            "indice_global": indice_global, "capture_index": capture_index,
            "teto_rms_v": teto_rms, "teto_extremo_v": teto_extremo, "cabe": False,
        }
        rms = self.tensao_rms_programada(capture_index)
        if rms is not None:
            info["rms_programado_v"] = float(rms)
            if rms > teto_rms + 1e-9:
                info["motivo"] = f"{rms:.1f} Vrms > {teto_rms:.1f} Vrms (limite rms da fonte)"
                return info
            if rms * math.sqrt(2.0) > teto_pico + 1e-9:
                info["motivo"] = f"{rms * math.sqrt(2.0):.1f} Vp > {teto_pico:.1f} Vp"
                return info
        if seed is None:
            seed = self.seed_da_captura(int(indice_global or 0))
        t = tempo(self.config) if t is None else t
        try:
            # Ordem importa: a forma primeiro (a 08 calcula a excursão nela).
            forma, parametros = self.forma_e_parametros_para_bancada(capture_index, t, seed)
            pico = self._pico_da_forma_v(forma, capture_index)
            extremo = self._extremo_previsto_da_forma_v(pico, parametros)
        except Exception as exc:  # noqa: BLE001 - sem previsão não há prova de que cabe
            info["motivo"] = f"extremo previsto incalculável ({type(exc).__name__}: {exc})"
            return info
        info.update(pico_programado_v=pico, extremo_previsto_v=extremo, parametros=parametros)
        if "fator_disturbio_bancada" in parametros:
            info["fator_disturbio_bancada"] = float(parametros["fator_disturbio_bancada"])
        if extremo > teto_extremo + 1e-9:
            motivo = (
                f"extremo PREVISTO {extremo:.1f} V > teto {teto_extremo:.1f} V "
                f"(pico programado × fator medido × margem {MARGEM_FATOR_EXTREMO:.2f})"
            )
            necessario = parametros.get("fator_disturbio_necessario")
            if necessario is not None:
                motivo += (
                    f"; o limite de bancada precisaria reduzir o distúrbio a "
                    f"{100.0 * float(necessario):.0f}% (mínimo aceito: "
                    f"{100.0 * LIMITE_BANCADA_FRACAO_MINIMA:.0f}%)"
                )
            info["motivo"] = motivo
            return info
        info["cabe"] = True
        return info

    def _indices_viaveis(self, indices: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Filtra, ANTES da primeira captura, os índices cujo nível não cabe
        nos limites da fonte.

        Manual AMETEK §4.14, p. 84: "the maximum voltage that can be
        programmed is 300 V rms" (e 425 V de pico). A classe 03 a 220 V pede
        1,4 pu = 308 Vrms: impossível, não um bug de software. Antes, o código
        descobria isso na 21.ª captura, três vezes seguidas, e a classe
        terminava sem nenhum arquivo (relatório 01 §3 P1).

        Um nível inviável é PULADO com log claro (os demais continuam
        valendo); se nenhum for viável, levanta ``ParameterOutOfBoundsError``
        — determinístico, portanto sem retry (ver ``Bancada.ERROS_DETERMINISTICOS``).
        Nas classes waveform, o limite de bancada (v1.13) já reduziu o
        distúrbio quando isso bastava para caber — aqui só chega como
        inviável o que nem reduzido cabe."""
        fonte = self.fonte
        if fonte is None:
            return indices
        t = tempo(self.config)
        self._avaliacoes_bancada: Dict[int, Dict[str, object]] = {}
        viaveis: List[Tuple[int, int]] = []
        recusados: Dict[Tuple[int, int], str] = {}
        for indice_global, capture_index in indices:
            info = self.avaliar_captura_na_bancada(indice_global, capture_index, t=t)
            if not info["cabe"]:
                recusados[(indice_global, capture_index)] = str(info["motivo"])
                continue
            self._avaliacoes_bancada[indice_global] = info
            viaveis.append((indice_global, capture_index))
        for (indice_global, capture_index), motivo in sorted(recusados.items()):
            logger.warning(
                "[%s] captura %d (nível %d) PULADA ANTES de programar: %s (limite rms/pico da "
                "fonte, manual §4.14 p. 84, ou extremo previsto pela calibração). A classe roda "
                "com as capturas restantes.",
                self.id, indice_global + 1, capture_index, motivo,
            )
        if not viaveis:
            raise ParameterOutOfBoundsError(
                f"[{self.id}] nenhum nível desta classe cabe nos limites da fonte a "
                f"{self.config.base_voltage_rms:.1f} Vrms de base: "
                f"{ {chave[1]: motivo for chave, motivo in recusados.items()} }. "
                "Baixe a tensão base ou ajuste os níveis da classe."
            )
        return viaveis

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

    # Margem de captura, em segundos, ANTES e DEPOIS da janela nominal.
    # Histórico dos valores (por que 400ms → 20/50ms, não 500ms nem 25ms):
    # v1.7/v1.8 mediram um "atraso universal de ~20ms" e adotaram 25ms; v1.9
    # hipotetizou o DISTÚRBIO inteiro atrasando até ~2,7x (500ms); v1.10 caiu
    # para 400ms por causa do teto real do modo AUTO do osciloscópio
    # (~32,3-32,7 mil pontos). Os relatórios 01/02 (2026-09-21) mostraram os
    # dois números de origem FALSOS: o "atraso" era só o offset de referência
    # horizontal do osciloscópio (H-REF10, corrigido no P07/indice_trigger),
    # não latência real da fonte; e com LIST:REPeat=0 (v1.10) o evento já sai
    # no lugar nominal. Sem esse "atraso" fantasma para cobrir, a folga real
    # necessária é medida diretamente: o fim de evento mais tardio das duas
    # sessões de 2026-09-16 é 116,7ms após o trigger, e o conteúdo programado
    # termina em 200ms (relatório 01 §2(i)); 50ms depois cobrem o retorno ao
    # regime e o sobre-pico de transição observado nas bordas do evento.
    #
    # Desde 2026-09-22 (P10, pedido do dono) esta margem deixou de ser
    # opt-in — não existe mais ``set margin on|off`` nem modo "sem margem"
    # para captura física; é sempre aplicada. NÃO reduzir abaixo disto sem
    # refazer a medida (ver docs/analise-2026-09-21/01_conclusao_investigacao.md §2(i)).
    MARGEM_ANTES_S = env_float("MARGEM_ANTES_S", 0.020)
    MARGEM_DEPOIS_S = env_float("MARGEM_DEPOIS_S", 0.050)

    @staticmethod
    def _calcular_margem(*, captura_fisica: bool, config_points: int, fs_hz: float) -> Tuple[int, int, int]:
        """Folga de ``MARGEM_ANTES_S``/``MARGEM_DEPOIS_S`` de cada lado da
        janela nominal (20ms/50ms por padrão — 600/1500 amostras a 30kSa/s,
        8100 pontos totais) — SEMPRE, em toda captura física, sem opt-in
        (ver comentário acima do módulo/campo). ``captura_fisica=False``
        (dataset simulado, ``gerar()``) nunca teve margem e continua sem —
        devolve ``(0, 0, config_points)`` sem folga nenhuma, comportamento
        idêntico ao de sempre. Devolve (amostras de margem antes, amostras
        de margem depois, total de amostras incluindo os dois lados)."""
        if not captura_fisica:
            return 0, 0, config_points
        antes = int(round(ExperimentoBase.MARGEM_ANTES_S * fs_hz))
        depois = int(round(ExperimentoBase.MARGEM_DEPOIS_S * fs_hz))
        return antes, depois, config_points + antes + depois

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
        cobertura_por_nivel_ativa, capturas_por_nivel, total = self.dimensionar_capturas(simulated)
        logger.info(
            "[%s] %s: %d capturas, SNR=%s dB, modo=%s, seed base=%d",
            self.id, self.nome, total, self.config.snr_levels_db,
            "SIMULADO" if simulated else "BANCADA", self.config.base_seed,
        )
        # Plano de capturas: (indice_global, capture_index). A pré-validação
        # de níveis roda ANTES de qualquer comando SCPI e pode encurtar este
        # plano (ver _indices_viaveis).
        plano = self.plano_de_capturas(simulated)
        self._capturas_puladas_count = 0
        if not simulated:
            planejadas = len(plano)
            plano = self._indices_viaveis(plano)
            total = len(plano)
            self._capturas_puladas_count = planejadas - total
            if self._capturas_puladas_count:
                logger.warning(
                    "[%s] plano: %d capturas; %d PULADA(S) pela pré-validação; roda %d.",
                    self.id, planejadas, self._capturas_puladas_count, total,
                )
        t = tempo(self.config)
        margem_antes, margem_depois, pontos_efetivos = self._calcular_margem(
            captura_fisica=not simulated,
            config_points=self.config.points, fs_hz=self.config.fs_hz,
        )
        self._pontos_efetivos_captura_atual = pontos_efetivos
        if not simulated:
            duracao_efetiva = pontos_efetivos / self.config.fs_hz
            pre_trigger_efetivo = self.pre_trigger_s + margem_antes / self.config.fs_hz
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
        capturas_invalidas: List[Tuple[str, List[str]]] = []
        capturas_descartadas: List[Tuple[str, int, str]] = []
        tempo_ms_eixo = None
        if not simulated:
            # Gravação incremental: cada captura vai para o disco assim que
            # sai (ver _salvar_captura). Sem isto, uma falha na captura k
            # jogava fora as k-1 boas, que só existiam em memória —
            # exatamente o que aconteceu com as 7 capturas de 08 e as 52 de
            # 03 na sessão 2 (relatório 01 §3 P1, caminho #1).
            self._iniciar_gravacao_incremental()
        try:
            for posicao, (indice_global, capture_index) in enumerate(plano):
                seed = self.seed_da_captura(indice_global)
                rng = np.random.default_rng(seed)
                capture_id = f"{self.id}-{indice_global + 1:04d}"

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
                    self._validar_captura(time_s, measured_voltage_pu, pontos_esperados=pontos_efetivos)
                else:
                    try:
                        time_s, measured_voltage_pu, measured_current_pu, parametros = self._capturar_real(
                            capture_index, t, rng,
                        )
                        self._validar_captura(time_s, measured_voltage_pu, pontos_esperados=pontos_efetivos)
                    except ERROS_CAPTURA_DESCARTAVEL as exc:
                        # Só ESTA captura é perdida — a bateria/classe seguem para a
                        # próxima posição do plano, sem retentar do zero (pedido do
                        # dono em 2026-09-22: "não aborte, apenas log e descarte;
                        # abortar a bateria gasta MUITO tempo"). Nada é gravado para
                        # ela. Ver ERROS_CAPTURA_DESCARTAVEL para o que entra/não
                        # entra nesta lista e por quê.
                        logger.error(
                            "[%s] captura %s (%d/%d, nível %d) DESCARTADA — %s: %s. A "
                            "classe e a bateria continuam; nada foi gravado para esta "
                            "captura.",
                            self.id, capture_id, posicao + 1, total, capture_index,
                            type(exc).__name__, exc,
                        )
                        capturas_descartadas.append((capture_id, capture_index, str(exc)))
                        continue
                tempo_ms_eixo = time_s * 1000.0
                ids.append(capture_id)
                tensao_limpa[posicao] = measured_voltage_pu

                medidas_snr = {}
                for snr_db in self.config.snr_levels_db:
                    noise_seed = seed + int(round(snr_db * 1000.0)) + 50_000_000
                    ruidoso = ruido_awgn(measured_voltage_pu, snr_db, np.random.default_rng(noise_seed))
                    tensao_por_snr[snr_db][posicao] = ruidoso
                    medidas_snr[str(snr_db)] = snr_medida(measured_voltage_pu, ruidoso)

                if corrente is not None and measured_current_pu is not None:
                    corrente[posicao] = measured_current_pu

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
                extremos: Dict[str, object] = {}
                if not simulated:
                    metadados[-1].update(self._contexto_da_sessao())
                    # Logo depois da aquisição, antes de qualquer outro comando
                    # ao osciloscópio: a medida é sobre o registro que ele tem.
                    extremos = self._medir_extremos_fisicos()
                    metadados[-1].update(extremos)
                    avaliacao = getattr(self, "_avaliacoes_bancada", {}).get(indice_global)
                    if avaliacao is not None:
                        metadados[-1]["extremo_previsto_v"] = avaliacao["extremo_previsto_v"]
                        metadados[-1]["pico_programado_v"] = avaliacao["pico_programado_v"]
                if margem_antes or margem_depois:
                    metadados[-1]["margem_amostras_antes"] = margem_antes
                    metadados[-1]["margem_amostras_depois"] = margem_depois
                    metadados[-1]["amostras_totais"] = pontos_efetivos
                if not simulated:
                    validacao = self._validar_fisicamente(
                        capture_index, t, seed, measured_voltage_pu,
                        margem_antes=margem_antes,
                    )
                    if validacao is not None:
                        metadados[-1]["validacao_fisica"] = validacao
                        if not validacao["ok"]:
                            capturas_invalidas.append((capture_id, validacao["motivos"]))
                            logger.error(
                                "[%s] captura %s NÃO corresponde ao que foi programado: %s",
                                self.id, capture_id, "; ".join(validacao["motivos"]),
                            )
                    self._salvar_captura(
                        tempo_ms=tempo_ms_eixo,
                        tensao_limpa_captura=tensao_limpa[posicao],
                        tensao_por_snr_captura={
                            snr_db: tensao[posicao]
                            for snr_db, tensao in tensao_por_snr.items()
                        },
                        corrente_captura=(
                            None if corrente is None or measured_current_pu is None
                            else corrente[posicao]
                        ),
                        id_captura=capture_id,
                        metadado=metadados[-1],
                    )
                    logger.info("[%s] captura %d/%d gravada", self.id, posicao + 1, total)
                    # Só DEPOIS de gravada: a captura que passou do teto é a evidência.
                    self._conferir_extremos_fisicos(capture_id, extremos)

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
            capturas_boas = total - len(capturas_descartadas) - len(capturas_invalidas)
            self._capturas_descartadas_count = len(capturas_descartadas)
            self._capturas_invalidas_count = len(capturas_invalidas)
            if capturas_descartadas or capturas_invalidas:
                # Os dados válidos e os inválidos (marcados) já estão no
                # disco. Log sempre, mesmo quando a classe vai terminar OK —
                # silêncio aqui seria exatamente o que deixou duas sessões
                # inteiras com rótulo errado sem ninguém notar.
                logger.warning(
                    "[%s] %d/%d capturas boas; %d descartada(s) por erro (nada gravado), "
                    "%d marcada(s) inválida(s) na validação física (gravadas mesmo assim, "
                    "ver 'validacao_fisica' no metadata).",
                    self.id, capturas_boas, total, len(capturas_descartadas), len(capturas_invalidas),
                )
            if total > 0 and capturas_boas <= 0:
                # Rede de segurança: só chega aqui se TODA captura planejada
                # foi perdida — a classe não pode terminar silenciosamente
                # como OK com zero dado. Isto ainda propaga para
                # executar_bateria() (ao contrário do caso comum de 1-em-N
                # acima, que não levanta nada).
                if capturas_invalidas:
                    raise ValidacaoFisicaError(
                        f"[{self.id}] nenhuma das {total} capturas planejadas passou na "
                        f"validação física ({len(capturas_invalidas)} gravadas mas "
                        f"reprovadas, {len(capturas_descartadas)} descartadas por erro): "
                        f"{capturas_invalidas}. Os arquivos foram GRAVADOS com "
                        "validacao_fisica.ok=false no metadata."
                    )
                raise InstrumentHardwareError(
                    f"[{self.id}] nenhuma das {total} capturas planejadas produziu dado "
                    f"válido — todas descartadas por erro: {capturas_descartadas}."
                )
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

    def grava_trace(self, capture_index: int) -> bool:
        return bool(self.usar_trace(capture_index))

    def scope_scale_v(self) -> Optional[float]:
        """Override para fixar a escala vertical do osciloscópio antes do
        laço de capturas, quando o pico não muda entre capturas."""
        return None

    def tensao_rms_programada(self, capture_index: int) -> Optional[float]:
        """Deriva a tensão rms do nível discreto da classe (``NIVEIS`` em pu
        da tensão base) — é o que 02/SAG e 03/SWELL programam em
        ``trigger_pulse``. Classes cujos ``NIVEIS`` não são pu de tensão (ex.:
        05/HARMONICS, que lista THD) devem sobrescrever devolvendo ``None``."""
        niveis = getattr(self, "NIVEIS", None)
        if not niveis:
            return None
        return float(niveis[capture_index % len(niveis)]) * self.config.base_voltage_rms

    def _preparar_acquisicao_real(self) -> None:
        scale = self.scope_scale_v()
        if scale is not None:
            self.osc.set_vertical_scale(1, scale)

    def fase_de_disparo_graus(self) -> float:
        """Fase que ``gerar()`` tem no instante do trigger.

        ``gerar()`` põe fase 0 em t=0 da janela e o trigger cai em
        ``pre_trigger_s``; a fonte dispara na fase de
        ``TRIGger:SYNChronize:PHASe``. Com 0° fixo, 02/03/04 (pré-trigger de
        60 ms = 3,6 ciclos a 60 Hz) saíam defasadas 216° do modelo — sessão
        2026-09-30 14:44: correlação -0,78 contra ``gerar()``, 0,999 contra
        o modelo com fase 0 no trigger, e a THD da 04 reprovada (3,38% contra
        4,61%) porque o corte físico começava no zero e o do modelo num
        degrau. Disparando na fase do modelo, a bancada reproduz o dataset."""
        ciclos = float(self.pre_trigger_s) * float(self.config.grid_frequency_hz)
        return round((ciclos % 1.0) * 360.0, 1) % 360.0

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
            self.fonte.definir_fase_de_disparo(self.fase_de_disparo_graus())
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

    def grava_trace(self, capture_index: int) -> bool:
        return True

    def forma_esperada_para_validacao(self, capture_index, t, seed):
        forma = getattr(self, "_forma_programada_pu", None)
        if forma is not None:
            return np.asarray(forma, dtype=np.float64)
        return super().forma_esperada_para_validacao(capture_index, t, seed)

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

    def forma_para_bancada(
        self, voltage_pu: np.ndarray, parametros: Dict[str, float], capture_index: int,
    ) -> np.ndarray:
        """Adapta a forma de ``gerar()`` ao que a bancada pode programar.
        Padrão: se o pico passa de ``limite_pico_bancada_pu()``, escala a forma
        INTEIRA; depois aplica o limite de bancada do distúrbio
        (``_limitar_disturbio_para_bancada``, v1.13). A 08 sobrescreve
        (escalar tudo derrubava a base de 127 V para 43 Vrms — ANALISE.md,
        T8-1 — e ela tem modelo próprio do impulso). Pode acrescentar chaves a
        ``parametros`` (vão para o metadata)."""
        voltage_pu = self._limitar_pico_da_forma(voltage_pu)
        return self._limitar_disturbio_para_bancada(voltage_pu, parametros, capture_index)

    def _limitar_pico_da_forma(self, voltage_pu: np.ndarray) -> np.ndarray:
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
        return voltage_pu

    def parametros_com_disturbio_reduzido(
        self, parametros: Dict[str, float], fracao: float,
    ) -> Dict[str, float]:
        """Gancho de bancada: tradução da ``fracao`` do limite de bancada
        para os parâmetros físicos da classe (chaves ``*_bancada``, vão para
        o metadata ao lado dos do modelo). Padrão: nada — a forma aplicada
        continua definida por ``fator_disturbio_bancada`` (senoide + fração ×
        (modelo - senoide))."""
        return {}

    def _limitar_disturbio_para_bancada(
        self, voltage_pu: np.ndarray, parametros: Dict[str, float], capture_index: int,
    ) -> np.ndarray:
        """Opção (b) do dono para 220 V: se o extremo previsto da forma do
        modelo passa do teto, reduz SÓ o distúrbio (a senoide base fica em
        1 pu) à maior fração que cabe pelo modelo de
        ``extremo_previsto_com_disturbio_v``. Nunca sobe nada; nunca toca
        ``max_peak_v``. Fração < ``LIMITE_BANCADA_FRACAO_MINIMA``: devolve a
        forma do modelo (que a pré-validação pula), anotando a fração
        necessária para o log."""
        fonte = self.fonte
        if not LIMITE_BANCADA_DISTURBIO or fonte is None:
            return voltage_pu
        teto = self.fracao_teto_pico_medido * float(getattr(fonte, "max_peak_v", float("inf")))
        if not math.isfinite(teto):
            return voltage_pu
        nominal_v = self.config.base_voltage_rms * math.sqrt(2.0)
        fatores = carregar_fatores_extremo()
        fator = fator_extremo_da_classe(self.id, fatores)
        fator_ref = fator_referencia_extremo(fator, fatores)
        voltage_pu = np.asarray(voltage_pu, dtype=np.float64)
        pico_modelo_v = float(np.max(np.abs(voltage_pu))) * nominal_v
        if pico_modelo_v * fator * MARGEM_FATOR_EXTREMO <= teto + 1e-9:
            return voltage_pu
        n = voltage_pu.size
        t = np.arange(n, dtype=np.float64) / self.config.fs_hz
        senoide = np.sin(2.0 * np.pi * self.config.grid_frequency_hz * t)
        disturbio = voltage_pu - senoide

        def extremo(fracao: float) -> float:
            pico_v = float(np.max(np.abs(senoide + fracao * disturbio))) * nominal_v
            return extremo_previsto_com_disturbio_v(
                pico_v, pico_modelo_v, fracao, fator=fator, fator_referencia=fator_ref,
            )

        if extremo(0.0) > teto + 1e-9:
            parametros["fator_disturbio_necessario"] = 0.0
            return voltage_pu
        cabe, nao_cabe = 0.0, 1.0
        for _ in range(40):
            meio = 0.5 * (cabe + nao_cabe)
            if extremo(meio) <= teto:
                cabe = meio
            else:
                nao_cabe = meio
        if cabe < LIMITE_BANCADA_FRACAO_MINIMA:
            parametros["fator_disturbio_necessario"] = cabe
            return voltage_pu
        parametros.update({
            "fator_disturbio_bancada": cabe,
            "pico_programado_modelo_v": pico_modelo_v,
            "extremo_previsto_modelo_v": pico_modelo_v * fator * MARGEM_FATOR_EXTREMO,
        })
        parametros.update(self.parametros_com_disturbio_reduzido(parametros, cabe))
        return senoide + cabe * disturbio

    def forma_e_parametros_para_bancada(self, capture_index, t, seed):
        voltage_pu, parametros = self.gerar(
            t, self.config.grid_frequency_hz, capture_index, np.random.default_rng(seed),
        )
        parametros = dict(parametros)
        forma = self.forma_para_bancada(np.asarray(voltage_pu, dtype=np.float64), parametros, capture_index)
        return np.asarray(forma, dtype=np.float64), parametros

    def excursao_fisica_prevista_v(self) -> Optional[float]:
        """|extremo| físico previsto para a captura atual (inclui a resposta da
        fonte, que pode passar do programado — ver 08). ``None``: usa só o pico
        programado para a escala do osciloscópio, como sempre."""
        return None

    def _capturar_real(self, capture_index, t, rng):
        voltage_pu, parametros = self.gerar(t, self.config.grid_frequency_hz, capture_index, rng)
        voltage_pu = np.asarray(voltage_pu, dtype=np.float64)
        if voltage_pu.shape != (self.config.points,) or not np.all(np.isfinite(voltage_pu)):
            raise RuntimeError(f"gerar() do experimento {self.id} produziu forma inválida")
        voltage_pu = np.asarray(self.forma_para_bancada(voltage_pu, parametros, capture_index), dtype=np.float64)
        if voltage_pu.shape != (self.config.points,) or not np.all(np.isfinite(voltage_pu)):
            raise RuntimeError(f"forma_para_bancada() do experimento {self.id} produziu forma inválida")
        if "fator_disturbio_bancada" in parametros:
            logger.warning(
                "[%s] LIMITE DE BANCADA: distúrbio FÍSICO reduzido a %.0f%% do modelo para o "
                "extremo previsto caber no teto (modelo: %.0f V previstos); gerar()/dataset "
                "simulado não mudam. Parâmetros aplicados no metadata (fator_disturbio_bancada, *_bancada).",
                self.id, 100.0 * float(parametros["fator_disturbio_bancada"]),
                float(parametros["extremo_previsto_modelo_v"]),
            )
        parametros.pop("fator_disturbio_necessario", None)
        # Forma REALMENTE programada (já escalada): é contra ela, e não
        # contra gerar(), que a validação física deve comparar — a classe 08
        # é reduzida por limite_pico_bancada_pu() só na captura física.
        self._forma_programada_pu = voltage_pu
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
        excursao = self.excursao_fisica_prevista_v()
        if excursao is not None:
            programmed_peak_v = max(programmed_peak_v, float(excursao))
        nominal_peak_v = self.config.base_voltage_rms * math.sqrt(2.0)
        headroom = 1.60 if programmed_peak_v > 3.0 * nominal_peak_v else 1.25
        # A escala também cobre o extremo PREVISTO pela calibração (até 1,6×
        # o programado; a 220 V perto do teto): set_vertical_scale põe o pico
        # pedido em 3 das 4 divisões, então a tela vai a 4/3 dele (v1.13).
        previsto_v = self._extremo_previsto_da_forma_v(self._pico_da_forma_v(voltage_pu, capture_index), parametros)
        self.osc.set_vertical_scale(
            1, max(programmed_peak_v * headroom, previsto_v, self.config.base_voltage_rms * 0.1),
        )

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


# Gravações de TRACe:DATA numa mesma conexão: a fonte travou na ~280.ª em
# 2026-09-16 (``AmetekMX30.escritas_trace``). Não é limite do manual, é a
# única referência medida — a CLI só AVISA quando a estimativa passa dela.
ESCRITAS_TRACE_REFERENCIA_TRAVA = 280


def capturas_efetivas_da_classe(experimento_cls: type, config: Optional[Config] = None) -> Dict[str, int]:
    """Número de capturas que ``run`` faria desta classe NA BANCADA com a
    configuração atual (``set capturas``/``REAL_CAPTURES_PER_CLASS``/padrão
    da classe), sem abrir instrumento nenhum. ``total`` é o planejado ANTES
    da pré-validação de pico/rms, que ainda pode pular capturas (logado)."""
    config = config or _build_config()
    experimento = experimento_cls(Bancada(None, None, config))
    por_nivel, capturas_por_nivel, total = experimento.dimensionar_capturas(False)
    ciclos = int(round(config.duration_s * config.grid_frequency_hz))
    com_trace = sum(
        1 for _, capture_index in experimento.plano_de_capturas(False)
        if experimento.grava_trace(capture_index)
    )
    return {
        "padrao": int(experimento.capturas_padrao),
        "niveis": experimento.total_niveis() if por_nivel else 1,
        "por_nivel": capturas_por_nivel,
        "total": total,
        # Teto: o cache de program_capture (forma idêntica na mesma conexão)
        # e a poda de _indices_viaveis só podem diminuir.
        "escritas_trace": com_trace * ciclos,
    }


def scripts_da_bateria_fisica() -> List[Path]:
    """Scripts do ``run all`` na bancada: todos menos ``BATERIA_EXCLUIR``
    (logado, nunca em silêncio)."""
    scripts = _experiment_scripts()
    excluidos = [script for script in scripts if script.stem in BATERIA_EXCLUIR]
    if excluidos:
        logger.warning(
            "run all FÍSICO sem as classes %s (BATERIA_EXCLUIR=%s). Rode-as isoladas com "
            "'run <NN>' se precisar.",
            ", ".join(script.stem for script in excluidos), ",".join(BATERIA_EXCLUIR),
        )
    return [script for script in scripts if script.stem not in BATERIA_EXCLUIR]


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    scripts = scripts_da_bateria_fisica() if BENCH_MODE else _experiment_scripts()
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
