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
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from ametek_orm import AmetekMX30
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

    def capturas(self, simulated: bool) -> int:
        return self.sim_captures_per_class if simulated else self.real_captures_per_class


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
        results_dir=RESULTS_DIR,
        sim_captures_per_class=SIM_CAPTURES_PER_CLASS,
        real_captures_per_class=REAL_CAPTURES_PER_CLASS,
        disturbance_start_s=DISTURBANCE_START_S,
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
            return cls(AmetekMX30(simulated=True), None, config)

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

    def executar_bateria(self, scripts: List[Path]) -> None:
        for script_path in scripts:
            self.executar_experimento(script_path)
            if BENCH_MODE:
                time.sleep(0.5)
        logger.info("Bateria concluída: 20/20")

    def executar_experimento(self, script_path: Path) -> None:
        module_name = f"experimento_{script_path.parent.name}_{script_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Não foi possível carregar {script_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        experimento_cls = getattr(module, "Experimento", None)
        if experimento_cls is None:
            raise AttributeError(f"{script_path.name} não define a classe Experimento")
        logger.info("========== Experimento %s (%s) ==========", script_path.stem, script_path.parent.name)
        experimento_cls(self).executar()


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
        time_s, voltage_v = self.osc.get_waveform(1, expected_points=self.config.points)
        voltage_pu = voltage_v / (self.config.base_voltage_rms * math.sqrt(2.0))
        current_values = None
        if self.config.capture_current:
            current_time, current_a = self.osc.get_waveform(2, expected_points=self.config.points)
            if not np.allclose(current_time, time_s, rtol=0, atol=1e-9):
                raise RuntimeError("CH1 e CH2 possuem eixos temporais diferentes")
            current_values = current_a / float(self.config.current_base_a)
        return time_s, voltage_pu, current_values, parametros

    def _validar_captura(self, time_s: np.ndarray, voltage_pu: np.ndarray) -> None:
        config = self.config
        if time_s.shape != (config.points,) or voltage_pu.shape != (config.points,):
            raise ValueError(
                f"Captura deve ter {config.points} pontos; recebido {time_s.size}/{voltage_pu.size}"
            )
        if not np.all(np.isfinite(time_s)) or not np.all(np.isfinite(voltage_pu)):
            raise ValueError("Captura contém NaN ou infinito")
        incrementos = np.diff(time_s)
        incremento_esperado = 1.0 / config.fs_hz
        if not np.allclose(incrementos, incremento_esperado, rtol=0, atol=1e-9):
            raise ValueError(f"Eixo temporal não corresponde a {config.fs_hz:.0f} Sa/s")

    def _salvar_classe(
        self,
        *,
        tempo_ms: np.ndarray,
        tensao_limpa: np.ndarray,
        tensao_por_snr: Dict[float, np.ndarray],
        ids: List[str],
        corrente: Optional[np.ndarray],
        metadados: List[dict],
    ) -> None:
        """Grava a classe completa: dados puros (sem ruído) direto em
        ``resultados/``, uma cópia com AWGN aplicado por nível de SNR em
        ``resultados/snr_XXdb/`` (mesmo nome de arquivo, pasta diferente), e
        um metadata.jsonl comum às duas.

        Os dados puros são o que efetivamente saiu do gerador/instrumento —
        gravá-los sempre significa que aplicar (ou reaplicar) ruído no futuro,
        com outro SNR ou outra técnica, não exige regerar nem recapturar nada.

        Escrita atômica: grava em ``.part`` e só promove para o nome final
        (via ``os.replace``) depois que tudo terminou sem erro.
        """
        config = self.config
        ids_array = np.array(ids, dtype=object)
        final_paths = []

        config.results_dir.mkdir(parents=True, exist_ok=True)
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
        total = self.config.capturas(simulated)
        logger.info(
            "[%s] %s: %d capturas, SNR=%s dB, modo=%s",
            self.id, self.nome, total, self.config.snr_levels_db,
            "SIMULADO" if simulated else "BANCADA",
        )
        t = tempo(self.config)
        if not simulated:
            self.osc.configure_acquisition(
                sample_rate_hz=self.config.fs_hz,
                points=self.config.points,
                duration_s=self.config.duration_s,
                pre_trigger_s=self.pre_trigger_s,
            )
            self._preparar_acquisicao_real()

        tensao_limpa = np.empty((total, self.config.points), dtype=np.float64)
        tensao_por_snr: Dict[float, np.ndarray] = {
            snr_db: np.empty((total, self.config.points), dtype=np.float64)
            for snr_db in self.config.snr_levels_db
        }
        corrente = (
            np.empty((total, self.config.points), dtype=np.float64)
            if self.config.capture_current else None
        )
        ids: List[str] = []
        metadados: List[dict] = []
        tempo_ms_eixo = None

        for capture_index in range(total):
            seed = self.config.base_seed + int(self.id) * 1_000_000 + capture_index
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
            self._validar_captura(time_s, measured_voltage_pu)
            tempo_ms_eixo = time_s * 1000.0
            capture_id = f"{self.id}-{capture_index + 1:04d}"
            ids.append(capture_id)
            tensao_limpa[capture_index] = measured_voltage_pu

            medidas_snr = {}
            for snr_db in self.config.snr_levels_db:
                noise_seed = seed + int(round(snr_db * 1000.0)) + 50_000_000
                ruidoso = ruido_awgn(measured_voltage_pu, snr_db, np.random.default_rng(noise_seed))
                tensao_por_snr[snr_db][capture_index] = ruidoso
                medidas_snr[str(snr_db)] = snr_medida(measured_voltage_pu, ruidoso)

            if corrente is not None and measured_current_pu is not None:
                corrente[capture_index] = measured_current_pu

            metadados.append({
                "id_captura": capture_id,
                "classe": self.nome,
                "seed": seed,
                "simulado": simulated,
                "fs_hz": self.config.fs_hz,
                "pontos": self.config.points,
                "parametros": parametros,
                "snr_medido_db": medidas_snr,
            })
            if not simulated:
                logger.info("[%s] captura %d/%d concluída", self.id, capture_index + 1, total)

        self._salvar_classe(
            tempo_ms=tempo_ms_eixo, tensao_limpa=tensao_limpa, tensao_por_snr=tensao_por_snr,
            ids=ids, corrente=corrente, metadados=metadados,
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
            self.fonte.arm_transient()
        else:
            parametros = self.configurar(capture_index)
            self.fonte.arm()
        self.fonte.trigger()
        self.osc.wait_for_trigger_complete(timeout_s=5.0)
        self.fonte.wait_transient_complete(timeout_s=5.0)
        return self._ler_captura(parametros)


class ExperimentoWaveform(ExperimentoBase):
    """Classes que precisam de forma de onda arbitrária (TRACe/LIST) — sempre
    ``gerar()`` + ``program_capture``/``arm_transient``, também na bancada real."""

    def _capturar_real(self, capture_index, t, rng):
        voltage_pu, parametros = self.gerar(t, self.config.grid_frequency_hz, capture_index, rng)
        voltage_pu = np.asarray(voltage_pu, dtype=np.float64)
        if voltage_pu.shape != (self.config.points,) or not np.all(np.isfinite(voltage_pu)):
            raise RuntimeError(f"gerar() do experimento {self.id} produziu forma inválida")
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
            bancada.executar_bateria(scripts)
        return 0
    except KeyboardInterrupt:
        logger.error("Interrupção pelo usuário; iniciando shutdown")
        return 130
    except BaseException:
        logger.exception("Bateria abortada na primeira falha")
        return 1


if __name__ == "__main__":
    # Importar como módulo "mestre" (em vez de rodar como __main__) garante
    # que um NN.py carregado dinamicamente por Bancada.executar_experimento()
    # que fizer "import mestre" reaproveite este mesmo módulo já em
    # sys.modules, em vez de reexecutar este arquivo do zero sob outro nome.
    import mestre
    sys.exit(mestre.main())
