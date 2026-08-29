"""Orquestrador fail-safe dos 20 experimentos: config, instrumentos, execução."""

from __future__ import annotations

import importlib.util
import logging
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from ametek_orm import AmetekMX30


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

PROJECT_ROOT = Path(__file__).resolve().parent
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


# ---------------------------------------------------------------------------
# Instrumentos
# ---------------------------------------------------------------------------

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


def inicializar_instrumentos(
    *, require_output: bool = True
) -> Tuple[AmetekMX30, Optional[object], Config]:
    config = _build_config()
    if SIMULATED_MODE:
        logger.warning("MODO SIMULADO: nenhum instrumento será aberto")
        # Nenhum experimento toca fonte/osc no modo simulado (usam gerar());
        # a instância existe só por consistência de assinatura.
        return AmetekMX30(simulated=True), None, config

    validate_bench_configuration(require_output=require_output)
    source: Optional[AmetekMX30] = None
    scope = None
    try:
        source = AmetekMX30(
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
        source.configure_safe_baseline(
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
            source.clear_all_traces()

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
        scope = KeysightDSOX4034A(adapter)
        logger.info("Keysight identificado: %s", scope.verify_identity(KEYSIGHT_EXPECTED_MODEL))
        scope.initialize_safe()

        voltage_scale = EUT_MAX_PEAK_V / 3.0
        scope.configure_channel(
            1,
            scale=voltage_scale,
            probe_attenuation=float(VOLTAGE_PROBE_ATTENUATION),
            coupling="DC",
            units="VOLT",
        )
        actual_voltage_scale = float(scope.ask(":CHANnel1:SCALe?"))
        if 4.0 * actual_voltage_scale < 1.05 * EUT_MAX_PEAK_V:
            raise RuntimeError(
                f"Escala CH1 insuficiente: {actual_voltage_scale} V/div para "
                f"pico limite {EUT_MAX_PEAK_V} V"
            )
        if CAPTURE_CURRENT:
            current_peak = max(float(CURRENT_BASE_A), CURRENT_LIMIT_A) * math.sqrt(2.0)
            scope.configure_channel(
                2,
                scale=current_peak / 3.5,
                probe_attenuation=float(CURRENT_PROBE_ATTENUATION),
                coupling="DC",
                units="AMP",
            )
        else:
            scope.disable_channel(2)
        scope.configure_acquisition(sample_rate_hz=FS_HZ, points=POINTS, duration_s=DURATION_S)
        scope.setup_external_trigger(
            level_v=EXT_TRIGGER_LEVEL_V,
            probe_attenuation=EXT_TRIGGER_PROBE_ATTENUATION,
            range_v=EXT_TRIGGER_RANGE_V,
        )
        source.authorize_output(require_output and OUTPUT_ARMED)
        if require_output and OUTPUT_ARMED:
            # Energiza uma única vez para toda a bateria. Cada captura, daqui
            # em diante, só reprograma o transiente (PULSe/LIST/CSINe/TRACe) e
            # dispara — nunca desliga a saída entre capturas (ver
            # ametek_orm.program_capture / energize_baseline).
            source.energize_baseline()
        logger.info(
            "Instrumentos prontos: AMETEK=%s; Keysight=%s; CH2=%s",
            source.idn,
            scope.idn,
            "ON" if CAPTURE_CURRENT else "OFF",
        )
        return source, scope, config
    except BaseException:
        if source is not None:
            source.disconnect()
        if scope is not None:
            scope.close()
        raise


# ---------------------------------------------------------------------------
# Execução dos experimentos
# ---------------------------------------------------------------------------

def executar_experimento(script_path: Path, source: AmetekMX30, scope, config: Config) -> None:
    module_name = f"experimento_{script_path.parent.name}_{script_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Não foi possível carregar {script_path}")
    module = importlib.util.module_from_spec(spec)
    # Cada pasta de experimentos tem seu próprio comum.py (autocontido, sem
    # importar mestre.py). Colocamos a pasta correta no início do sys.path só
    # durante a execução deste módulo, e limpamos o cache de "comum" antes e
    # depois para não misturar o comum.py de uma pasta com o de outra.
    directory = str(script_path.parent)
    sys.modules.pop("comum", None)
    sys.path.insert(0, directory)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(directory)
        sys.modules.pop("comum", None)
    run = getattr(module, "run", None)
    if not callable(run):
        raise AttributeError(f"{script_path.name} não contém run(fonte, osc, config)")
    logger.info("========== Experimento %s (%s) ==========", script_path.stem, script_path.parent.name)
    run(source, scope, config)


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
    source: Optional[AmetekMX30] = None
    scope = None
    try:
        source, scope, config = inicializar_instrumentos()
        for script_path in scripts:
            executar_experimento(script_path, source, scope, config)
            if BENCH_MODE:
                time.sleep(0.5)
        logger.info("Bateria concluída: 20/20")
        return 0
    except KeyboardInterrupt:
        logger.error("Interrupção pelo usuário; iniciando shutdown")
        return 130
    except BaseException:
        logger.exception("Bateria abortada na primeira falha")
        return 1
    finally:
        logger.info("Shutdown fail-safe")
        if source is not None:
            source.disconnect()
        if scope is not None:
            scope.close()


if __name__ == "__main__":
    sys.exit(main())
