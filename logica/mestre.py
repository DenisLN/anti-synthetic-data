"""Orquestrador fail-safe dos 20 experimentos: config, instrumentos, execução."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import math
import os
import shutil
import sys
import time
from uuid import uuid4
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np

from ametek_orm import (
    AmetekMX30, BracoP09Error, CapacidadeExcedidaError, CommunicationError, FalhaFatalDeInstrumento,
    InstrumentHardwareError, LeituraTraceError, ParameterOutOfBoundsError, ProgramacaoCaptura,
    verificar_exigencias,
)
from politica_traces import LIMITE_ESCRITAS_TRACE_CONEXAO, LimiteEscritasTraceError
import perfis
import sessao_io
import bruto_osciloscopio_io
from sinais import (
    FORMA_NATIVA_POR_CLASSE, comparar_fisicamente, distancia_modelo_programada,
    forma_programada_nativa, janela_nominal, ruido_na_janela, tempo,
)


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
_INFO_CODIGO_CACHE: Optional[Dict[str, object]] = None


# Pastas cujos arquivos NÃO rastreados também tornam a árvore "suja" (são o
# código que gera e grava as sessões). Fora delas, arquivo novo não conta (ex.:
# notas em docs/), como no -dirty de ``git describe``.
PASTAS_DO_CODIGO = ("logica", "experimentos_nativos", "experimentos_waveform", "scripts")


def info_do_codigo(*, recalcular: bool = False) -> Dict[str, object]:
    """Procedência do código desta execução: commit (``git rev-parse HEAD``),
    se a árvore está suja, versões do numpy e do Python. ``git_commit``/
    ``git_sujo`` ficam ``None`` quando o git não responde — nunca impede uma
    sessão.

    "Sujo" = alteração rastreada não commitada em QUALQUER arquivo
    (``git status --porcelain --untracked-files=no``) OU arquivo não rastreado
    (e não ignorado) dentro de ``PASTAS_DO_CODIGO``. ``arquivos_nao_rastreados``
    diz quais são esses arquivos novos.

    O resultado fica em cache no processo; ``recalcular=True`` refaz a conta
    (``preparar_pasta_da_sessao`` faz isso a cada pasta de sessão, ou seja, a
    cada ``run`` da CLI)."""
    global _INFO_CODIGO_CACHE
    if _INFO_CODIGO_CACHE is not None and not recalcular:
        return dict(_INFO_CODIGO_CACHE)
    import platform
    import subprocess

    def _git(*args: str) -> Optional[str]:
        try:
            return subprocess.run(
                ["git", *args], cwd=str(PROJECT_ROOT), capture_output=True,
                text=True, timeout=10, check=True,
            ).stdout.strip()
        except Exception:  # noqa: BLE001 - nunca impedir uma sessão por causa disto
            return None

    commit = _git("rev-parse", "HEAD") or None
    status = _git("status", "--porcelain", "--untracked-files=no")
    novos = _git("ls-files", "--others", "--exclude-standard", "--", *PASTAS_DO_CODIGO)
    if status is None or novos is None:
        sujo = None
    else:
        sujo = bool(status or novos)
    _INFO_CODIGO_CACHE = {
        "git_commit": commit,
        "git_sujo": sujo,
        "arquivos_nao_rastreados": sorted(novos.splitlines()) if novos else [],
        "versao_codigo": versao_do_codigo(),
        "numpy_versao": np.__version__,
        "python_versao": platform.python_version(),
    }
    return dict(_INFO_CODIGO_CACHE)


def sha256_do_arquivo(caminho: Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def _gravar_metadata_legivel(jsonl_final: Path, registros: Sequence[dict]) -> None:
    """Ao lado do ``NN_classe.jsonl`` (formato de máquina, 1 linha por captura,
    o que todos os leitores consomem) grava ``NN_classe.json``: a mesma lista de
    registros, indentada, para leitura humana. Derivado do .jsonl, nunca o
    contrário; os leitores não o usam (``glob("*.jsonl")`` não o casa)."""
    destino = Path(jsonl_final).with_suffix(".json")
    parcial = destino.with_suffix(".json.part")
    parcial.write_text(
        json.dumps(list(registros), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(parcial, destino)


NOME_CALIBRACAO_NA_SESSAO = "calibracao_extremos.json"
NOME_METADATA_DA_SESSAO = "sessao.json"
# Modelo / programada / medida de cada captura (docs/tres_versoes.md).
PASTA_TRES_VERSOES = "tres_versoes"
_SESSOES_PREPARADAS: Dict[Path, Dict[str, object]] = {}


def preparar_pasta_da_sessao(
    results_dir: Path, *, bancada: bool, perfis_usados: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    """Uma vez por processo e pasta: copia a ``calibracao_extremos.json`` EM
    USO para dentro da sessão e grava ``sessao.json`` (commit, árvore suja,
    numpy, Python, caminho e SHA-256 da calibração, perfil de faixas). A
    calibração muda depois das sessões (é recalibrada a partir das medidas de cada rodada):
    sem a cópia, o ``k`` recalculado a partir do código de hoje deixa de bater
    com o gravado.

    A procedência é recalculada aqui (``info_do_codigo(recalcular=True)``), ou
    seja, a cada pasta nova = a cada ``run`` da CLI. ``perfis_usados`` são os
    perfis dos runs da CLI até este (inclusive); sem ele, só o perfil atual.

    Árvore suja numa sessão de BANCADA é avisada em destaque, sem bloquear
    (não há mecanismo de bloqueio no fluxo; o operador decide)."""
    results_dir = Path(results_dir)
    chave = results_dir.resolve()
    if chave in _SESSOES_PREPARADAS:
        return _SESSOES_PREPARADAS[chave]
    results_dir.mkdir(parents=True, exist_ok=True)
    codigo = info_do_codigo(recalcular=True)
    copia = results_dir / NOME_CALIBRACAO_NA_SESSAO
    parcial = copia.with_suffix(".json.part")
    shutil.copyfile(CALIBRACAO_EXTREMOS_PATH, parcial)
    os.replace(parcial, copia)
    info: Dict[str, object] = {
        "formato_metadata": 2,
        "criada_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "modo": "bancada" if bancada else "simulado",
        **codigo,
        "perfil": PERFIL_TODOS_ROTULO if PERFIL_TODOS else PERFIL,
        "perfis_da_rodada": list(perfis_da_rodada()),
        "perfis_usados_na_cli": list(perfis_usados) if perfis_usados else [PERFIL_TODOS_ROTULO if PERFIL_TODOS else PERFIL],
        # Formato dos .npz desta sessão (logica/sessao_io.py, docs/dataset.md):
        # 2 = um NN_classe.npz comprimido por classe, com perfis e versões.
        "formato_npz": sessao_io.FORMATO_NPZ,
        "calibracao_extremos": {
            "origem": str(CALIBRACAO_EXTREMOS_PATH),
            "copia_na_sessao": NOME_CALIBRACAO_NA_SESSAO,
            "sha256": sha256_do_arquivo(copia),
        },
        # Condição da rodada (v1.15, acrescentado): o que ``rerun``/``run
        # falhas`` precisa para reproduzir uma captura desta pasta.
        "condicao": {
            "tensao_base_rms": float(BASE_VOLTAGE_RMS),
            "frequencia_hz": float(GRID_FREQUENCY_HZ),
            "p09_braco": str(P09_BRACO),
            "base_seed": int(BASE_SEED),
            "capturas_override": CAPTURAS_OVERRIDE,
            "sorteio_posicao": bool(SORTEIO_POSICAO),
            "perfil": PERFIL_TODOS_ROTULO if PERFIL_TODOS else PERFIL,
            "perfis_da_rodada": list(perfis_da_rodada()),
            **condicao_atual(),
            "calibracao_extremos_sha256": sha256_do_arquivo(copia),
        },
    }
    if RERUN_DE is not None:
        info["rerun_de"] = dict(RERUN_DE)
    destino = results_dir / NOME_METADATA_DA_SESSAO
    parcial = destino.with_suffix(".json.part")
    parcial.write_text(json.dumps(info, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(parcial, destino)
    _SESSOES_PREPARADAS[chave] = info
    if bancada and codigo["git_sujo"]:
        aviso = (
            "ATENÇÃO: árvore git SUJA (alterações rastreadas não commitadas ou "
            f"arquivos novos em {', '.join(PASTAS_DO_CODIGO)}; versão {codigo['versao_codigo']}). "
            f"Arquivos novos: {codigo.get('arquivos_nao_rastreados') or 'nenhum'}. Esta sessão NÃO é "
            "reproduzível só pelo commit. Commit limpo antes de uma sessão de coleta."
        )
        logger.warning(aviso)
        print("\n" + "!" * 78 + f"\n{aviso}\n" + "!" * 78 + "\n")
    elif bancada and codigo["git_sujo"] is None:
        logger.warning("Não foi possível verificar se a árvore git está limpa (git indisponível).")
    return info


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
SNR_LEVELS_DB = env_float_tuple("SNR_LEVELS_DB", (20.0, 30.0, 40.0))
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
# ``set diagnostico retrieve`` (v1.15): lê de volta, a cada captura TRACE, as
# TRACEs gravadas na fonte (``TRACe:DATA?``), num ponto seguro do fluxo, e grava
# em ``<sessao>/diagnostico_trace/``. Desligado por padrão.
DIAGNOSTICO_RETRIEVE: bool = False
SALVAR_BRUTO_OSCILOSCOPIO: bool = env_bool("SALVAR_BRUTO_OSCILOSCOPIO", default=False)
# Espera mínima (s) entre a última escrita de TRACe e a leitura (quirk A2).
DIAGNOSTICO_RETRIEVE_ESPERA_S: float = env_float("DIAGNOSTICO_RETRIEVE_ESPERA_S", 2.0)
PASTA_DIAGNOSTICO_TRACE = "diagnostico_trace"
# Perfil de faixas do dataset (v1.15; logica/perfis.py): norma|literatura|
# fronteira. Inicial = env PERFIL (padrão literatura = dataset de sempre);
# "set perfil" da CLI muda em runtime, vale a partir do próximo run.
PERFIL_TODOS_ROTULO = "todos"
PERFIL_TODOS: bool = os.getenv(perfis.ENV_PERFIL, "").strip().lower() == PERFIL_TODOS_ROTULO
# PERFIL é SEMPRE um perfil de verdade (o da Config e o de "run <NN>" quando
# PERFIL_TODOS é False); com PERFIL_TODOS, run all / run <lista> percorrem os
# três perfis na mesma sessão e gravam tudo no mesmo NN_classe.npz.
PERFIL: str = perfis.PERFIL_PADRAO if PERFIL_TODOS else perfis.perfil_do_ambiente()


def perfis_da_rodada() -> Tuple[str, ...]:
    """Perfis que o próximo run percorre: os três (na ordem de
    ``perfis.PERFIS``) com ``set perfil todos``, senão só ``PERFIL``."""
    return tuple(perfis.PERFIS) if PERFIL_TODOS else (PERFIL,)


# Sorteio de início/duração/fase em gerar() (v1.15; `arquivo/analises:docs/analise-2026-10-12/pendente/sorteio_inicio_fase_VERIFICAR_BANCADA.md`).
# Padrão ligado; SORTEIO=0 (ou "set sorteio off")
# reproduz as posições fixas de antes (60 ms/80 ms, fase 0), byte a byte.
SORTEIO_POSICAO: bool = env_bool("SORTEIO", default=True)
# Rerun em andamento (``rerun``/``run falhas`` da CLI): origem gravada em
# sessao.json e no metadata de cada captura. None fora de um rerun.
RERUN_DE: Optional[Dict[str, object]] = None

# AMETEK pela USB com porta COM virtual; 115200 foi confirmado no equipamento real.
AMETEK_PORT = os.getenv("AMETEK_PORT", "COM10")
AMETEK_BAUDRATE = env_int("AMETEK_BAUDRATE", 115_200)
AMETEK_TIMEOUT_S = env_float("AMETEK_TIMEOUT_S", 5.0)
AMETEK_QUERY_EOT = env_bool("AMETEK_QUERY_EOT", default=True)
AMETEK_EXPECTED_MODEL = os.getenv("AMETEK_EXPECTED_MODEL", "MX30")
AMETEK_CLEAR_USER_WAVEFORMS = env_bool("AMETEK_CLEAR_USER_WAVEFORMS", default=False)
# Experimental: validar a margem física antes de tornar padrão.
AMETEK_PASSO_FINAL_SIN = env_bool("AMETEK_PASSO_FINAL_SIN", default=False)
# Experimento P-09 (A|B|C, padrão A = comportamento de sempre). Validado por
# AmetekMX30 ao abrir a conexão; "set p09 A|B|C" na CLI troca para o próximo run.
P09_BRACO = os.getenv("AMETEK_P09_BRACO", "A").strip().upper() or "A"

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


_CTRL_C_HANDLER = None


def garantir_ctrl_c_no_windows() -> None:
    """Faz o Ctrl+C voltar a interromper a bateria no Windows.

    Com as sessões VISA da bancada abertas (COM10 + USB do Keysight), o
    NI-VISA instala um tratador de console que DESCARTA o CTRL_C_EVENT: o
    Python nunca recebia KeyboardInterrupt (bancada 2026-10-07; reproduzido
    sem enviar comando nenhum, com um read() bloqueante na serial). O Windows
    chama o tratador registrado por ÚLTIMO primeiro; este repassa Ctrl+C/
    Ctrl+Break ao Python (``_thread.interrupt_main``), que levanta
    KeyboardInterrupt assim que a chamada VISA em curso retorna (no máximo o
    timeout dela) — e o ``with Bancada`` desliga a saída na saída.

    Chamar DEPOIS de abrir os instrumentos. Remove e registra de novo (fica
    uma vez só, no topo): registrado duas vezes, um Ctrl+C viraria dois
    KeyboardInterrupt e o segundo poderia cortar o desligamento da saída."""
    global _CTRL_C_HANDLER
    if sys.platform != "win32":
        return
    import _thread
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    if _CTRL_C_HANDLER is None:
        tipo = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

        def _repassar(evento: int) -> bool:
            if evento in (0, 1):  # CTRL_C_EVENT, CTRL_BREAK_EVENT
                _thread.interrupt_main()
                return True
            return False

        _CTRL_C_HANDLER = tipo(_repassar)
    else:
        kernel32.SetConsoleCtrlHandler(_CTRL_C_HANDLER, False)
    if not kernel32.SetConsoleCtrlHandler(_CTRL_C_HANDLER, True):
        logger.warning("Não foi possível registrar o tratador de Ctrl+C; use OUTPUT OFF no painel para parar.")


class CadeiaDeMedicaoError(FalhaFatalDeInstrumento):
    """A fonte não entrega a base, ou o CH1 não vê o que a fonte mede (ver
    ``Bancada.verificar_cadeia_de_medicao``). Infraestrutura: nenhuma classe
    roda, nada é retentado."""


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


def chave_condicao(tensao_rms: float, frequencia_hz: float) -> str:
    """Rótulo da condição de bancada de uma tabela de fatores: "127V_60Hz"."""
    return f"{float(tensao_rms):g}V_{float(frequencia_hz):g}Hz"


# Duas condições são a MESMA calibração se a tensão base difere até 2% e a
# frequência até 0,5 Hz. Fora disso a resposta da saída pode mudar: em
# 2026-10-07 a 17 mediu 1,24× o programado a 230 V/50 Hz contra 1,03× a
# 127 V/60 Hz (444 V, acima dos 425 Vp do hardware, com a pré-validação
# prevendo 405 V pela tabela de 127 V).
TOLERANCIA_CONDICAO_TENSAO = 0.02
TOLERANCIA_CONDICAO_FREQUENCIA_HZ = 0.5


def carregar_calibracao_extremos(caminho: Optional[Path] = None) -> Dict[str, Dict[str, object]]:
    """Tabelas de fatores por condição: {chave: {"tensao_rms", "frequencia_hz",
    "fatores"}}. Arquivo ausente, ilegível ou com fator inválido LEVANTA: sem
    ele a pré-validação de pico não tem base, e seguir sem ela seria
    enfraquecer a proteção em silêncio. Aceita o formato da v1.12/v1.13 (só
    ``fatores``, medidos a 127 V/60 Hz)."""
    caminho = CALIBRACAO_EXTREMOS_PATH if caminho is None else caminho
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    brutas = dados.get("por_condicao")
    if brutas is None:
        brutas = {chave_condicao(127.0, 60.0): {"tensao_rms": 127.0, "frequencia_hz": 60.0, "fatores": dados["fatores"]}}
    condicoes: Dict[str, Dict[str, object]] = {}
    for chave, tabela in brutas.items():
        fatores = {str(k).zfill(2): float(v) for k, v in tabela["fatores"].items()}
        if not fatores or any(not math.isfinite(v) or v <= 0 for v in fatores.values()):
            raise ValueError(f"Fatores de extremo inválidos em {caminho} ({chave}): {fatores}")
        condicoes[chave] = {
            "tensao_rms": float(tabela["tensao_rms"]),
            "frequencia_hz": float(tabela["frequencia_hz"]),
            "fatores": fatores,
        }
    if not condicoes:
        raise ValueError(f"Nenhuma tabela de fatores de extremo em {caminho}")
    return condicoes


def condicao_calibrada(
    condicoes: Dict[str, Dict[str, object]], tensao_rms: float, frequencia_hz: float,
) -> Optional[str]:
    """Chave da tabela medida nesta condição (tensão e frequência dentro das
    tolerâncias), ou ``None``."""
    for chave, tabela in condicoes.items():
        v, f = float(tabela["tensao_rms"]), float(tabela["frequencia_hz"])
        if (
            abs(float(tensao_rms) - v) <= TOLERANCIA_CONDICAO_TENSAO * v
            and abs(float(frequencia_hz) - f) <= TOLERANCIA_CONDICAO_FREQUENCIA_HZ
        ):
            return chave
    return None


_CONDICOES_SEM_CALIBRACAO_AVISADAS: set = set()


def carregar_fatores_extremo(
    caminho: Optional[Path] = None, *,
    tensao_rms: Optional[float] = None, frequencia_hz: Optional[float] = None,
) -> Dict[str, float]:
    """Fatores (extremo medido / pico programado) por classe para ESTA
    condição (padrão: BASE_VOLTAGE_RMS / GRID_FREQUENCY_HZ). O JSON guarda o
    MEDIDO em cada condição; a regra (v1.15, previsão por frequência) é esta:

    - condição calibrada: (1) só entram as tabelas de MESMA frequência (até
      ``TOLERANCIA_CONDICAO_FREQUENCIA_HZ``), qualquer tensão — o sobressinal
      depende da frequência, não da tensão (v1.14: 127 V e 230 V a 50 Hz
      dão fatores próximos; a 60 Hz a 16 chega a 1,475 contra 1,03 a 50 Hz);
      (2) dentro delas, cada classe usa o MAIOR fator da própria classe
      (uma captura com o distúrbio reduzido só dá limite INFERIOR do fator:
      10 e 11 a 230 V deram exatamente o fator da 01); (3) classe sem medida
      em NENHUMA condição de mesma frequência: o MAIOR fator de todas as
      tabelas (regra conservadora da v1.14). A 03 a 230 V/50 Hz continua
      fora pelo teto (1,058 × 357,8 V × margem 1,10 = 416,4 V > 415,8 V);
    - condição sem tabela própria: toda classe usa o MAIOR fator já medido
      em qualquer condição, exceto a 01 (senoide pura, referência de
      ``fator_referencia_extremo``), que usa o maior fator da 01 entre as
      condições — sem isso a parte da senoide também iria ao máximo e nada
      caberia (a 01 a 230 V/50 Hz mediu 0,97× o de 127 V/60 Hz). Avisa uma
      vez por condição."""
    condicoes = carregar_calibracao_extremos(caminho)
    tensao_rms = BASE_VOLTAGE_RMS if tensao_rms is None else float(tensao_rms)
    frequencia_hz = GRID_FREQUENCY_HZ if frequencia_hz is None else float(frequencia_hz)
    todas = [tabela["fatores"] for tabela in condicoes.values()]
    maior = max(max(fatores.values()) for fatores in todas)  # type: ignore[union-attr]
    classes = sorted({classe for fatores in todas for classe in fatores})  # type: ignore[union-attr]
    maior_da_classe = {classe: max(f[classe] for f in todas if classe in f) for classe in classes}  # type: ignore[operator,index]
    chave = condicao_calibrada(condicoes, tensao_rms, frequencia_hz)
    if chave is not None:
        mesma_frequencia = [
            tabela["fatores"] for tabela in condicoes.values()
            if abs(float(tabela["frequencia_hz"]) - frequencia_hz) <= TOLERANCIA_CONDICAO_FREQUENCIA_HZ
        ]
        return {
            classe: (  # type: ignore[operator]
                max(f[classe] for f in mesma_frequencia if classe in f)  # type: ignore[operator,index]
                if any(classe in f for f in mesma_frequencia) else maior
            )
            for classe in classes
        }
    conservadores = {classe: maior for classe in classes}
    if CLASSE_REFERENCIA_EXTREMO in maior_da_classe:
        conservadores[CLASSE_REFERENCIA_EXTREMO] = maior_da_classe[CLASSE_REFERENCIA_EXTREMO]
    alvo = chave_condicao(tensao_rms, frequencia_hz)
    if alvo not in _CONDICOES_SEM_CALIBRACAO_AVISADAS:
        _CONDICOES_SEM_CALIBRACAO_AVISADAS.add(alvo)
        logger.warning(
            "Calibração de extremos SEM tabela para %s (há: %s). Previsão de pico CONSERVADORA: "
            "distúrbio de toda classe com o maior fator já medido (%.3f), senoide pura com %.3f. "
            "Mais capturas serão reduzidas/puladas. Para calibrar esta condição: rode a bateria "
            "nela e depois scripts/recalibrar_extremos.py <sessao> --gravar.",
            alvo, ", ".join(sorted(condicoes)), maior, conservadores.get(CLASSE_REFERENCIA_EXTREMO, maior),
        )
    return conservadores


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


# Limite de bancada (v1.13, opção b para 220 V: reduzir só o distúrbio em vez de
# pular a captura, porque a v1.12 pulava 10, 11, 14 e 16 a 220 V com extremo
# previsto de 423 a 499 V, acima de 415,8 V). Nas classes
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
# (`arquivo/analises:docs/analise-2026-09-30/ANALISE.md`, T8-4: VMAX 230 V / VMIN -334 V).
BATERIA_EXCLUIR = tuple(
    item.strip().zfill(2)
    for item in os.environ.get("BATERIA_EXCLUIR", "").split(",")
    if item.strip()
)

# Erros que invalidam só UMA captura: ExperimentoBase.executar() loga,
# descarta a captura (não grava nada para ela) e segue para a PRÓXIMA
# posição do plano — nunca propaga para executar_bateria(). Decisão de projeto
# de 2026-09-22, motivada pela medida dos ensaios p01/p02 (a captura falha na
# hora, erro 19 e divergência de readback): não abortar a bateria por uma
# captura, porque abortar reexecutava a classe inteira do zero, até 3x.
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
    # Perfil de faixas lido por gerar() das classes 02/03/05/06/10-16/20
    # (logica/perfis.py). O padrão reproduz o dataset anterior à v1.15.
    perfil: str = perfis.PERFIL_PADRAO
    # Perfis que são a MESMA captura deste (``set perfil todos`` numa classe
    # cujo gerar() não depende do perfil: ``perfis.plano_de_perfis``). Vazio =
    # captura própria. Só ``Bancada`` preenche; ver ``ArquivoDaClasse.espelhar``.
    perfis_espelho: Tuple[str, ...] = ()
    # Início, duração e fase sorteados em gerar() (ver ``Sorteio``). False =
    # posições fixas anteriores à v1.15.
    sorteio_posicao: bool = True
    # Leitura de volta das TRACEs gravadas (``set diagnostico retrieve``).
    preservar_bruto_osciloscopio: bool = False
    diagnostico_retrieve: bool = False
    diagnostico_retrieve_espera_s: float = 2.0
    # Rerun (v1.15): só estes ``indice_global`` do plano rodam (None = todos,
    # o caminho normal). Posto por ``Bancada.executar_bateria(selecao=...)``.
    indices_permitidos: Optional[Tuple[int, ...]] = None
    # Rerun: {"sessao": pasta de origem, ...}; vai para o metadata de cada
    # captura (``rerun_de``). None no caminho normal.
    rerun_de: Optional[Dict[str, object]] = None

    def capturas(self, simulated: bool) -> int:
        """Capturas desta classe (por nível, nas classes com ``NIVEIS``).

        Simulado: ``SIM_CAPTURES_PER_CLASS``, sempre — o dataset não depende
        de padrão de bancada nem da CLI. Bancada: o MAIOR entre o valor
        global (``set capturas N`` quando o operador digitou, senão
        ``REAL_CAPTURES_PER_CLASS``, padrão 1) e o padrão da classe (decisão de
        projeto, v1.13): ``set capturas 3`` numa classe de padrão 6 roda
        6; numa de padrão 1, 3. A CLI avisa quando o padrão vence."""
        if simulated:
            return self.sim_captures_per_class
        global_ = (
            self.capturas_override if self.capturas_override is not None
            else self.real_captures_per_class
        )
        return max(global_, self.capturas_padrao_classe)


# ---------------------------------------------------------------------------
# Sorteio de início, duração e fase (v1.15)
# ---------------------------------------------------------------------------

# Margem mínima, em ciclos da rede, entre as bordas da janela e o distúrbio
# (t_min do desenho do sorteio, v1.15): ao menos 1 ciclo de senoide limpa
# antes e depois. A duração de um evento vai de meio ciclo ao que sobra.
SORTEIO_TMIN_CICLOS = 1.0
SORTEIO_DURACAO_MIN_CICLOS = 0.5
# Resolução de TRIGger:SYNChronize:PHASe (ametek_orm.definir_fase_de_disparo).
SORTEIO_FASE_RESOLUCAO_GRAUS = 0.1
# Chaves que gerar() acrescenta a ``parametros`` quando o sorteio está ligado;
# executar() as move para o nível de cima do metadata.
CHAVES_SORTEIO = ("inicio_disturbio_s", "duracao_s", "fase_graus")
_CHAVE_DO_SUBFLUXO = 0x50525445  # separa o sub-fluxo do sorteio do fluxo do rng


@dataclass(frozen=True)
class Sorteio:
    """Posição sorteada de uma captura: ``inicio_s``/``duracao_s`` do distúrbio
    (``None`` quando a classe não tem evento localizado) e ``fase_graus`` da
    senoide base em t = 0, ou seja ``sin(2 pi f0 t + fase)``. Inativo
    (``ativo=False``) devolve os valores fixos de antes da v1.15: fase 0 e
    nada acrescentado a ``parametros``."""

    ativo: bool
    f0_hz: float
    inicio_s: Optional[float] = None
    duracao_s: Optional[float] = None
    fase_graus: float = 0.0

    @property
    def deslocamento_s(self) -> float:
        """``tau`` tal que ``sin(2 pi f0 (t + tau))`` tem a fase sorteada.
        Somar ``tau`` a ``t`` em TODA parcela periódica (fundamental e
        harmônicas) é deslocar a forma inteira no tempo, sem refazer fórmula."""
        return self.fase_graus / (360.0 * self.f0_hz) if self.ativo else 0.0

    def parametros(self) -> Dict[str, float]:
        if not self.ativo:
            return {}
        sorteados = {
            "inicio_disturbio_s": self.inicio_s,
            "duracao_s": self.duracao_s,
            "fase_graus": self.fase_graus,
        }
        return {chave: float(valor) for chave, valor in sorteados.items() if valor is not None}


def _rng_do_sorteio(rng: np.random.Generator) -> np.random.Generator:
    """Sub-fluxo determinístico da MESMA seed, independente de quantas vezes
    ``rng`` já foi usado: os parâmetros que ``gerar()`` já sorteava (flicker_hz,
    amplitudes...) continuam idênticos para uma dada seed."""
    seed_seq = getattr(rng.bit_generator, "seed_seq", None)
    if isinstance(seed_seq, np.random.SeedSequence):
        filho = np.random.SeedSequence(
            entropy=seed_seq.entropy, spawn_key=tuple(seed_seq.spawn_key) + (_CHAVE_DO_SUBFLUXO,),
        )
        return np.random.default_rng(filho)
    return np.random.default_rng(rng.integers(0, 2**32, size=4))


def sortear_posicao(
    rng: np.random.Generator, config, f0_hz: float, *,
    inicio_legado_s: Optional[float] = None, duracao_legada_s: Optional[float] = None,
    duracao_variavel: bool = False, fase_acoplada_ao_inicio: bool = False,
) -> Sorteio:
    """Início ``t0``, duração ``d`` e fase ``phi`` da captura.

    Com ``t0`` e ``d`` sorteados: ``d ~ U(0,5 ciclo, T - 2 tmin)`` (se
    ``duracao_variavel``; senão ``d = duracao_legada_s``) e
    ``t0 ~ U(tmin, T - d - tmin)``, ambos na grade de amostragem. A fase vem de
    ``theta ~ U(0, 360)`` na resolução de 0,1 grau, onde ``theta`` é a fase da
    senoide NO INSTANTE ``t0`` (a que o ``TRIGger:SYNChronize:PHASe`` da fonte
    reproduz); a fase em t = 0 é ``theta - 360 f0 t0``. Sem evento
    (``inicio_legado_s=None``) ``theta`` é a própria fase em t = 0.
    ``fase_acoplada_ao_inicio``: a senoide cruza zero em ``t0`` (entalhes
    posicionados nos picos acompanham o início); a fase deixa de ser livre.

    Desligado (``config.sorteio_posicao`` falso): valores legados, fase 0."""
    f0_hz = float(f0_hz)
    if not getattr(config, "sorteio_posicao", True):
        return Sorteio(False, f0_hz, inicio_legado_s, duracao_legada_s, 0.0)
    fs_hz = float(config.fs_hz)
    janela_s = float(config.points) / fs_hz
    ciclo_s = 1.0 / f0_hz
    tmin_s = SORTEIO_TMIN_CICLOS * ciclo_s
    u_duracao, u_inicio, u_fase = _rng_do_sorteio(rng).random(3)

    def grade(valor_s: float) -> float:
        return round(valor_s * fs_hz) / fs_hz

    duracao_s = duracao_legada_s
    if duracao_s is not None and duracao_variavel:
        minimo = SORTEIO_DURACAO_MIN_CICLOS * ciclo_s
        maximo = max(minimo, janela_s - 2.0 * tmin_s)
        duracao_s = grade(minimo + u_duracao * (maximo - minimo))
    inicio_s = None
    if inicio_legado_s is not None:
        folga = janela_s - float(duracao_s or 0.0) - tmin_s
        inicio_s = grade(tmin_s + u_inicio * max(0.0, folga - tmin_s))
    theta = (
        0.0 if fase_acoplada_ao_inicio
        else round(u_fase * 360.0 / SORTEIO_FASE_RESOLUCAO_GRAUS) * SORTEIO_FASE_RESOLUCAO_GRAUS
    )
    # round(): só tira o ruído de ponto flutuante do metadata (1e-6 grau).
    fase_graus = round((theta - 360.0 * f0_hz * (inicio_s or 0.0)) % 360.0, 6) % 360.0
    return Sorteio(True, f0_hz, inicio_s, duracao_s, fase_graus)


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
    # A classe (ou parte dela) não rodou porque o orçamento de gravações TRACe
    # da conexão esgotou: registrada em falhas.json para ``run falhas``.
    nao_executada_orcamento: bool = False

    @property
    def pasta_esperada(self) -> Path:
        return SESSION_RESULTS_DIR or RESULTS_DIR


# ---------------------------------------------------------------------------
# Registro de falhas da sessão (falhas.json) e seleção para rerun (v1.15)
# ---------------------------------------------------------------------------

NOME_FALHAS_DA_SESSAO = "falhas.json"
FORMATO_FALHAS = 1
TIPOS_FALHA = (
    "pulada_capacidade",        # exigência acima de CAPACIDADES_MX30 (pré-validação, sem I/O)
    "pulada_preflight",         # rms/pico/extremo previsto acima do teto (pré-validação, sem I/O)
    "descartada",               # erro de ERROS_CAPTURA_DESCARTAVEL durante a captura; nada gravado
    "invalida",                 # gravada, reprovada na validação física
    "classe_falhou",            # a classe (num perfil) terminou FALHOU
    "nao_executada_orcamento",  # não rodou: orçamento de TRACe da conexão esgotou
)
# ``run falhas`` reexecuta estes; as puladas repetiriam a mesma recusa na
# mesma condição (só ``rerun`` explícito as aceita, com aviso).
TIPOS_REEXECUTAVEIS = ("descartada", "invalida", "classe_falhou", "nao_executada_orcamento")
CAMPOS_FALHA = (
    "tipo", "classe", "classe_nome", "perfil", "indice_global", "capture_index", "nivel_indice",
    "seed", "id_captura", "motivo",
)


class RegistroFalhas:
    """``<sessao>/falhas.json``: uma entrada por captura pulada/descartada/
    inválida, classe que falhou ou não executada por orçamento, com o contexto
    para reproduzi-la (``contexto``). Reescrito atomicamente (``.part`` ->
    ``os.replace``) a cada entrada, ao longo da bateria; criado só na primeira.
    Uma falha de disco aqui é logada e NÃO derruba a bateria."""

    def __init__(self, pasta: Path, contexto: Dict[str, object]):
        self.pasta = Path(pasta)
        self.caminho = self.pasta / NOME_FALHAS_DA_SESSAO
        self.contexto = dict(contexto)
        self.itens: List[Dict[str, object]] = []
        if self.caminho.is_file():  # outra Bancada na mesma pasta: acrescenta
            try:
                self.itens = list(ler_falhas(self.pasta).get("itens", []))
            except (OSError, ValueError):
                logger.exception("falhas.json existente ilegível; recomeçando a lista")

    def registrar(self, tipo: str, **campos) -> Dict[str, object]:
        if tipo not in TIPOS_FALHA:
            raise ValueError(f"tipo de falha desconhecido: {tipo!r}")
        entrada: Dict[str, object] = {chave: None for chave in CAMPOS_FALHA}
        entrada.update(campos)
        entrada["tipo"] = tipo
        entrada["registrado_em"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        entrada["contexto"] = dict(campos.get("contexto") or self.contexto)
        self.itens.append(entrada)
        self.gravar()
        return entrada

    def gravar(self) -> None:
        documento = {
            "formato_falhas": FORMATO_FALHAS,
            "sessao": str(self.pasta),
            "atualizado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "contexto": self.contexto,
            "itens": self.itens,
        }
        try:
            self.pasta.mkdir(parents=True, exist_ok=True)
            parcial = self.caminho.with_suffix(".json.part")
            parcial.write_text(
                json.dumps(documento, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8",
            )
            os.replace(parcial, self.caminho)
        except OSError:
            logger.exception("Não foi possível gravar %s; a bateria continua", self.caminho)


def ler_falhas(pasta: Path) -> Dict[str, object]:
    """Conteúdo de ``<pasta>/falhas.json`` ({} se não existe)."""
    caminho = Path(pasta) / NOME_FALHAS_DA_SESSAO
    if not caminho.is_file():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


class RerunRecusadoError(ValueError):
    """Pedido de rerun que não pode reproduzir a captura original (condição da
    CLI diferente, alvo inexistente, contexto ausente). Nada é energizado."""


# Condição da bancada que o rerun NÃO muda sozinho: tensão e frequência vêm do
# START_BENCH (fixas no processo), o braço P-09 e o passo final SINE são fixos
# por conexão, os limites vêm do ambiente e a calibração muda a pré-validação e
# o limite de bancada (logo a forma programada). Divergência = recusa.
CHAVES_CONDICAO_RERUN = (
    "tensao_base_rms", "frequencia_hz", "p09_braco", "passo_final_sin",
    "max_voltage_rms", "max_peak_v", "source_voltage_range_rms", "calibracao_extremos_sha256",
)


def condicao_atual() -> Dict[str, object]:
    """A condição desta CLI/processo nos nomes de ``CHAVES_CONDICAO_RERUN``
    (limites efetivos que ``Bancada.from_env`` passa à fonte na bancada)."""
    try:
        sha = sha256_do_arquivo(CALIBRACAO_EXTREMOS_PATH)
    except OSError:
        sha = None
    return {
        "tensao_base_rms": float(BASE_VOLTAGE_RMS),
        "frequencia_hz": float(GRID_FREQUENCY_HZ),
        "p09_braco": str(P09_BRACO),
        "passo_final_sin": bool(AMETEK_PASSO_FINAL_SIN),
        "max_voltage_rms": float(EUT_MAX_VOLTAGE_RMS),
        "max_peak_v": float(min(EUT_MAX_PEAK_V, AmetekMX30.MAX_SOURCE_PEAK_V)),
        "source_voltage_range_rms": float(SOURCE_VOLTAGE_RANGE_RMS),
        "calibracao_extremos_sha256": sha,
    }


_COMO_MUDAR = {
    "tensao_base_rms": "reinicie a bancada com START_BENCH digitando a tensão original",
    "frequencia_hz": "reinicie a bancada com START_BENCH digitando a frequência original",
    "p09_braco": "use 'set p09 {original}'",
    "passo_final_sin": "reinicie a CLI com AMETEK_PASSO_FINAL_SIN={valor_env}",
    "max_voltage_rms": "reinicie a CLI com EUT_MAX_VOLTAGE_RMS={original}",
    "max_peak_v": "reinicie a CLI com EUT_MAX_PEAK_V={original}",
    "source_voltage_range_rms": "reinicie a CLI com SOURCE_VOLTAGE_RANGE_RMS={original}",
}


def comparar_condicao_para_rerun(
    original: Dict[str, object], atual: Dict[str, object], pasta: Optional[Path] = None,
) -> List[str]:
    """Diferenças entre a condição original (``contexto`` de falhas.json ou
    ``condicao`` de sessao.json) e ``atual`` (``condicao_atual()``), cada uma
    dizendo o que mudar; lista vazia = pode reproduzir."""
    diferencas: List[str] = []
    for chave in CHAVES_CONDICAO_RERUN:
        if original.get(chave) is None:
            diferencas.append(f"a sessão de origem não registra {chave} (contexto ausente)")
            continue
        antes, agora = original[chave], atual.get(chave)
        if isinstance(antes, bool) or isinstance(agora, bool) or isinstance(antes, str):
            igual = str(antes).upper() == str(agora).upper()
        else:
            try:
                igual = abs(float(antes) - float(agora)) <= 1e-6
            except (TypeError, ValueError):
                igual = False
        if igual:
            continue
        if chave == "calibracao_extremos_sha256":
            copia = (Path(pasta) / NOME_CALIBRACAO_NA_SESSAO) if pasta is not None else NOME_CALIBRACAO_NA_SESSAO
            diferencas.append(
                f"calibração de extremos mudou (sha256 original {str(antes)[:12]}…, atual {str(agora)[:12]}…): "
                f"para reproduzir, copie {copia} sobre {CALIBRACAO_EXTREMOS_PATH} (confira com git diff e "
                "restaure depois do rerun)"
            )
            continue
        dica = _COMO_MUDAR[chave].format(original=antes, valor_env="1" if antes else "0")
        diferencas.append(f"{chave}: original {antes}, atual {agora} ({dica})")
    return diferencas


def verificar_condicao_para_rerun(
    original: Dict[str, object], atual: Optional[Dict[str, object]] = None, pasta: Optional[Path] = None,
) -> None:
    """Levanta ``RerunRecusadoError`` com todas as diferenças (nada energizado)."""
    diferencas = comparar_condicao_para_rerun(original, atual or condicao_atual(), pasta)
    if diferencas:
        raise RerunRecusadoError("a condição atual difere da sessão de origem — " + "; ".join(diferencas))


def selecionar_para_rerun(
    pasta: Path, alvos: Optional[Sequence[str]] = None,
) -> Tuple[
    Dict[str, object], Dict[str, Dict[str, Optional[Tuple[int, ...]]]], List[Dict[str, object]],
    List[Dict[str, object]],
]:
    """Seleção de ``run falhas`` (``alvos`` None: todas as entradas de
    ``TIPOS_REEXECUTAVEIS``) ou ``rerun <pasta> <id_captura|classe> ...``.

    Devolve ``(contexto, selecao, itens, puladas_retiradas)``: ``selecao[classe][perfil]`` é a
    tupla de ``indice_global`` a rodar, ou None = a classe inteira naquele
    perfil (classe_falhou/nao_executada_orcamento sem índice). ``id_captura``
    que não está em falhas.json é procurado no metadata da sessão (qualquer
    captura gravada pode ser reproduzida). Levanta ``RerunRecusadoError``."""
    pasta = Path(pasta)
    try:
        documento = ler_falhas(pasta)
        if not isinstance(documento, dict) or not isinstance(documento.get("itens", []), list):
            raise ValueError("estrutura inesperada (esperado objeto com lista 'itens')")
    except (OSError, ValueError) as exc:
        raise RerunRecusadoError(
            f"{pasta / NOME_FALHAS_DA_SESSAO} ilegível ou corrompido ({exc}); não dá para saber o que "
            "reproduzir — confira o arquivo (sessao.log tem as mesmas falhas)"
        ) from exc
    itens_falha = list(documento.get("itens", []))
    contexto = dict(documento.get("contexto") or {})
    if not contexto:
        contexto = dict(_ler_json_opcional(pasta / NOME_METADATA_DA_SESSAO).get("condicao") or {})
    escolhidos: List[Dict[str, object]] = []
    if alvos is None:
        escolhidos = [item for item in itens_falha if item.get("tipo") in TIPOS_REEXECUTAVEIS]
        if not escolhidos:
            raise RerunRecusadoError(
                f"nenhuma falha reexecutável em {pasta / NOME_FALHAS_DA_SESSAO} "
                f"({len(itens_falha)} entrada(s); puladas por capacidade/pré-validação só com 'rerun')"
            )
    else:
        metadados = None
        for alvo in alvos:
            alvo = str(alvo).strip()
            if alvo.isdigit() and len(alvo) <= 2:
                classe = alvo.zfill(2)
                da_classe = [item for item in itens_falha if str(item.get("classe")) == classe]
                if not da_classe:
                    raise RerunRecusadoError(f"classe {classe}: nenhuma entrada em falhas.json de {pasta}")
                escolhidos.extend(da_classe)
                continue
            da_captura = [item for item in itens_falha if item.get("id_captura") == alvo]
            if da_captura:
                escolhidos.extend(da_captura)
                continue
            if metadados is None:
                metadados = sessao_io.carregar_metadados(pasta)
            registros = [r for r in metadados.registros if r.get("id_captura") == alvo]
            if not registros:
                raise RerunRecusadoError(f"captura {alvo!r} não está em falhas.json nem no metadata de {pasta}")
            for registro in registros:
                classe = alvo.split("-", 1)[0]
                base = int(registro.get("base_seed", contexto.get("base_seed", 0)))
                indice = int(registro["seed"]) - base - int(classe) * 1_000_000
                escolhidos.append({
                    "tipo": "captura_gravada", "classe": classe, "perfil": registro.get("perfil"),
                    "indice_global": indice, "capture_index": registro.get("nivel_indice"),
                    "seed": registro["seed"], "id_captura": alvo,
                    "contexto": {**contexto, **{k: registro[k] for k in ("base_seed", "capturas_override") if k in registro}},
                })
    # Puladas (capacidade/pré-validação) seriam puladas de novo na mesma
    # condição: só elas = recusa; mistura = retiradas, com aviso de quem chama.
    puladas = [item for item in escolhidos if str(item.get("tipo", "")).startswith("pulada_")]
    if puladas and len(puladas) == len(escolhidos):
        raise RerunRecusadoError(
            f"só capturas puladas ({', '.join(str(i.get('id_captura')) for i in puladas)}): a pré-validação "
            "(capacidade da fonte ou extremo/rms previsto) as pularia de novo na mesma condição"
        )
    escolhidos = [item for item in escolhidos if item not in puladas]
    selecao: Dict[str, Dict[str, Optional[Tuple[int, ...]]]] = {}
    for item in escolhidos:
        ctx = item.get("contexto") or {}
        for chave in ("base_seed", "capturas_override", "sorteio_posicao") + CHAVES_CONDICAO_RERUN:
            if chave in ctx and chave in contexto and ctx[chave] != contexto[chave]:
                raise RerunRecusadoError(
                    f"entradas com contextos diferentes ({chave}: {contexto[chave]!r} x {ctx[chave]!r}); "
                    "faça um rerun por contexto"
                )
            contexto.setdefault(chave, ctx.get(chave))
        classe = str(item["classe"]).zfill(2)
        perfil = item.get("perfil") or (contexto.get("perfis_da_rodada") or [perfis.PERFIL_PADRAO])[0]
        por_perfil = selecao.setdefault(classe, {})
        indice = item.get("indice_global")
        if indice is None:
            por_perfil[perfil] = None
        elif perfil not in por_perfil or por_perfil[perfil] is not None:
            por_perfil[perfil] = tuple(sorted(set(por_perfil.get(perfil) or ()) | {int(indice)}))
    return contexto, selecao, escolhidos, puladas


def _ler_json_opcional(caminho: Path) -> Dict[str, object]:
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


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
        preservar_bruto_osciloscopio=SALVAR_BRUTO_OSCILOSCOPIO,
        diagnostico_retrieve=DIAGNOSTICO_RETRIEVE,
        diagnostico_retrieve_espera_s=DIAGNOSTICO_RETRIEVE_ESPERA_S,
        perfil=PERFIL,
        sorteio_posicao=SORTEIO_POSICAO,
        rerun_de=RERUN_DE,
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
        self._bloqueio_sessao = None

    def __enter__(self) -> "Bancada":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown()

    def shutdown(self) -> None:
        logger.info("Shutdown fail-safe")
        try:
            self.fonte.disconnect()
        finally:
            try:
                if self.osc is not None:
                    self.osc.close()
            finally:
                for arquivo in self.__dict__.pop("_arquivos_classe", {}).values():
                    arquivo.close()
                if self._bloqueio_sessao is not None:
                    self._bloqueio_sessao.close()
                    self._bloqueio_sessao = None

    @classmethod
    def from_env(cls, *, require_output: bool = True) -> "Bancada":
        # Reservar antes de setup/hardware e reter até o shutdown completo.
        bloqueio = sessao_io.BloqueioSessao(_build_config().results_dir)
        try:
            bancada = cls._from_env_sem_bloqueio(require_output=require_output)
            bancada._bloqueio_sessao = bloqueio
            return bancada
        except BaseException:
            bloqueio.close()
            raise

    @classmethod
    def _from_env_sem_bloqueio(cls, *, require_output: bool = True) -> "Bancada":
        config = _build_config()
        if SIMULATED_MODE:
            logger.warning("MODO SIMULADO: nenhum instrumento será aberto")
            # Nenhum experimento toca fonte/osc no modo simulado (usam gerar());
            # a instância existe só por consistência de assinatura.
            return cls(
                AmetekMX30(simulated=True, diagnostico=DIAGNOSTICO_MODE, p09_braco=P09_BRACO),
                None, config,
            )

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
                passo_final_sin=AMETEK_PASSO_FINAL_SIN,
                p09_braco=P09_BRACO,
                max_voltage_rms=EUT_MAX_VOLTAGE_RMS,
                max_peak_v=EUT_MAX_PEAK_V,
                max_current_a=CURRENT_LIMIT_A,
                diagnostico=DIAGNOSTICO_MODE,
            )
            fonte.configure_safe_baseline(
                voltage_range_rms=SOURCE_VOLTAGE_RANGE_RMS,
                # Limite de PICO do software, validado por configure_safe_baseline.
                # O VOLTage:HIGH da fonte é RMS e recebe EUT_MAX_VOLTAGE_RMS (ver
                # lá; T12 em `arquivo/analises:docs/analise-2026-09-30`). A proteção de pico é de
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
            garantir_ctrl_c_no_windows()  # depois das duas sessões VISA abertas

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
            bancada = cls(fonte, osc, config)
            if require_output and OUTPUT_ARMED:
                bancada.verificar_cadeia_de_medicao()
            return bancada
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

    # -- registro de falhas (falhas.json) e orçamento de TRACe ---------------

    def contexto_de_reproducao(self) -> Dict[str, object]:
        """O que ``rerun`` precisa para reproduzir uma captura desta bancada:
        seed base, ``set capturas``, perfis da rodada, tensão, frequência,
        braço P-09, sorteio e SHA-256 da calibração em uso."""
        config = self.config
        perfis_rodada = getattr(self, "_perfis_rodada_atual", None) or self._perfis_para_bateria(None)
        try:
            sha = sha256_do_arquivo(CALIBRACAO_EXTREMOS_PATH)
        except OSError:
            sha = None
        limites = condicao_atual()
        passo_final_sin = getattr(self.fonte, "passo_final_sin", None)
        return {
            # Limites efetivos e passo final SINE da bancada (os do ambiente,
            # que from_env passa à fonte; o passo, o da fonte quando há).
            **limites,
            "passo_final_sin": passo_final_sin if isinstance(passo_final_sin, bool) else limites["passo_final_sin"],
            "base_seed": int(config.base_seed),
            "capturas_override": config.capturas_override,
            "perfil": PERFIL_TODOS_ROTULO if len(perfis_rodada) > 1 else perfis_rodada[0],
            "perfis_da_rodada": list(perfis_rodada),
            "tensao_base_rms": float(config.base_voltage_rms),
            "frequencia_hz": float(config.grid_frequency_hz),
            "p09_braco": str(getattr(self.fonte, "p09_braco", P09_BRACO)),
            "sorteio_posicao": bool(getattr(config, "sorteio_posicao", True)),
            "calibracao_extremos_sha256": sha,
            "rerun_de": getattr(config, "rerun_de", None),
        }

    def registrar_falha(self, tipo: str, **campos) -> Optional[Dict[str, object]]:
        """Acrescenta uma entrada a ``<results_dir>/falhas.json`` (criado na
        primeira). Nunca levanta por falha de disco (logada)."""
        try:
            registro = self.__dict__.get("registro_falhas")
            if registro is None:
                pasta = getattr(self.config, "results_dir", None)
                if pasta is None:
                    return None
                registro = RegistroFalhas(Path(pasta), self.contexto_de_reproducao())
                self.registro_falhas = registro
            return registro.registrar(tipo, contexto=self.contexto_de_reproducao(), **campos)
        except (CommunicationError, FalhaFatalDeInstrumento):
            raise  # infraestrutura nunca é engolida
        except Exception:  # noqa: BLE001 - registrar nunca vira aborto da bateria
            logger.exception("Não foi possível registrar a falha (%s) em falhas.json; a bateria continua", tipo)
            return None

    def _encerrar_conexao_por_orcamento(self) -> None:
        """Orçamento de TRACe esgotado: ABORt + OUTPUT OFF CONFIRMADO e a
        conexão fechada. Nenhuma reconexão nem reenergização automática (a
        próxima exige comando e confirmação digitada nova). Sem a confirmação
        do OFF, ``FalhaFatalDeInstrumento`` (aborta, como qualquer falha de
        infraestrutura)."""
        fonte = self.fonte
        if fonte is None:
            logger.warning("Orçamento de TRACe esgotado sem fonte aberta: nada a desligar.")
            return
        try:
            fonte.authorize_output(False)
        except Exception:  # noqa: BLE001 - só retira a autorização em Python
            logger.debug("authorize_output(False) falhou", exc_info=True)
        confirmado = fonte.safe_shutdown()
        fechar = getattr(fonte, "_close_resource", None)
        if callable(fechar):
            fechar()
        if not confirmado:
            raise FalhaFatalDeInstrumento(
                "Orçamento de TRACe esgotado e OUTPUT OFF NÃO confirmado ao encerrar a conexão — "
                "confira o painel da AMETEK (OUTPUT OFF) e o E-stop."
            )
        logger.warning(
            "Orçamento de TRACe esgotado: OUTPUT OFF confirmado e conexão com a AMETEK encerrada. "
            "Nada será reconectado nem energizado automaticamente; as classes restantes ficam em "
            "falhas.json como nao_executada_orcamento ('run falhas' com confirmação nova)."
        )

    def _perfis_da_selecao(
        self, class_id: str, lista_perfis: Sequence[str],
        selecao: Optional[Dict[str, Dict[str, Optional[Tuple[int, ...]]]]],
    ) -> List[Tuple[str, Optional[Tuple[int, ...]]]]:
        """(perfil, índices ou None) que a classe rodaria nesta bateria."""
        if selecao is not None:
            return list(selecao.get(class_id, {}).items())
        return [
            (perfil, None) for perfil, _ in perfis.plano_de_perfis(
                class_id, lista_perfis, getattr(self.config, "sorteio_posicao", True),
            )
        ]

    def _perfis_para_bateria(self, perfis_da_rodada_: Optional[Sequence[str]]) -> Tuple[str, ...]:
        """Perfis que ``executar_bateria`` percorre por classe: os pedidos; ou,
        sem pedido, os três com ``set perfil todos``; ou o da própria
        ``config`` (nunca troca o perfil de uma ``Bancada`` montada à mão)."""
        if perfis_da_rodada_:
            return tuple(perfis.validar(p) for p in perfis_da_rodada_)
        if PERFIL_TODOS:
            return tuple(perfis.PERFIS)
        return (perfis.perfil_da_config(self.config),)

    @staticmethod
    def _config_do_perfil(
        config_original: "Config", perfil: str, espelhos: Tuple[str, ...],
        indices_permitidos: Optional[Tuple[int, ...]] = None,
    ) -> "Config":
        """``config_original`` com ``perfil`` e ``perfis_espelho`` postos (a
        mesma instância se nada muda); ``indices_permitidos`` só no rerun."""
        if indices_permitidos is not None:
            return replace(
                config_original, perfil=perfil, perfis_espelho=tuple(espelhos),
                indices_permitidos=tuple(int(i) for i in indices_permitidos),
            )
        if perfis.perfil_da_config(config_original) == perfil \
                and tuple(getattr(config_original, "perfis_espelho", ())) == tuple(espelhos):
            return config_original
        return replace(config_original, perfil=perfil, perfis_espelho=tuple(espelhos))

    def _executar_classe_no_perfil(
        self, class_id: str, script_path: Path, experimento_cls: type, rotulo: str,
    ) -> Tuple[bool, Optional[str], int, int, int, int]:
        """Roda UMA classe com o perfil já posto em ``self.config``, com as
        ``MAX_TENTATIVAS_POR_CLASSE`` tentativas e a recuperação de estado
        seguro entre elas. Devolve ``(sucesso, ultimo_erro, descartadas,
        invalidas, puladas, tentativas_feitas)``. Falha de infraestrutura
        propaga (aborta a bateria inteira, sem retry)."""
        sucesso = False
        ultimo_erro: Optional[str] = None
        descartadas = invalidas = puladas = 0
        tentativas_feitas = 0
        for tentativa in range(1, self.MAX_TENTATIVAS_POR_CLASSE + 1):
            tentativas_feitas = tentativa
            if tentativa > 1:
                logger.warning(
                    "[%s]%s tentativa %d/%d depois de falha: %s",
                    class_id, rotulo, tentativa, self.MAX_TENTATIVAS_POR_CLASSE, ultimo_erro,
                )
            logger.info(
                "========== Experimento %s (%s)%s ==========", class_id, script_path.parent.name, rotulo
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
            except LimiteEscritasTraceError:
                # Sem retry nesta conexão: executar_bateria encerra a conexão
                # com OUTPUT OFF confirmado e registra o restante em falhas.json.
                logger.error(
                    "[%s] Orçamento de TRACe da conexão esgotado — encerrando a conexão; o restante "
                    "vai para falhas.json (nao_executada_orcamento)", class_id,
                )
                raise
            except self.ERROS_DETERMINISTICOS as exc:
                ultimo_erro = str(exc)
                logger.error(
                    "[%s]%s FALHOU com erro DETERMINÍSTICO (%s) — não será retentado: "
                    "o mesmo parâmetro produziria o mesmo erro nas tentativas "
                    "seguintes. Corrija a configuração da classe ou a tensão base.",
                    class_id, rotulo, exc,
                )
                self.recuperar_estado_seguro()
                break
            except Exception as exc:
                ultimo_erro = str(exc)
                logger.exception(
                    "[%s]%s FALHOU (tentativa %d/%d)", class_id, rotulo, tentativa,
                    self.MAX_TENTATIVAS_POR_CLASSE,
                )
                if tentativa < self.MAX_TENTATIVAS_POR_CLASSE:
                    self.recuperar_estado_seguro()
        return sucesso, ultimo_erro, descartadas, invalidas, puladas, tentativas_feitas

    def executar_bateria(
        self, scripts: List[Path], perfis_da_rodada_: Optional[Sequence[str]] = None,
        selecao: Optional[Dict[str, Dict[str, Optional[Tuple[int, ...]]]]] = None,
    ) -> List[ResultadoClasse]:
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
        propaga sempre (não é ``Exception``, não é capturada abaixo).

        Com mais de um perfil (``set perfil todos``) cada classe roda uma vez
        por perfil, em sequência, e todos caem no mesmo ``NN_classe.npz``
        (``sessao_io``); o ``ResultadoClasse`` da classe é ``ok`` só se todos
        os perfis foram. Cada perfil é isolado como uma classe: a falha de um
        não impede os seguintes.

        ``LimiteEscritasTraceError`` (orçamento operacional de TRACe, não limite
        do fabricante): encerra a conexão com OUTPUT OFF confirmado
        (``_encerrar_conexao_por_orcamento``), registra o resto da classe
        corrente e as classes seguintes em falhas.json como
        ``nao_executada_orcamento`` e devolve os resultados — sem reconectar.

        ``selecao`` (rerun): ``{classe: {perfil: indices ou None}}``; só essas
        classes/perfis/capturas rodam. None = caminho normal, sem mudança."""
        resultados: List[ResultadoClasse] = []
        lista_perfis = self._perfis_para_bateria(perfis_da_rodada_)
        self._perfis_rodada_atual = lista_perfis
        varios = len(lista_perfis) > 1
        orcamento_esgotado: Optional[str] = None
        for script_path in scripts:
            class_id = script_path.stem
            if orcamento_esgotado is not None:
                for perfil, indices in self._perfis_da_selecao(class_id, lista_perfis, selecao):
                    for indice in (indices if indices is not None else (None,)):
                        self.registrar_falha(
                            "nao_executada_orcamento", classe=class_id, perfil=perfil,
                            indice_global=indice,
                            id_captura=None if indice is None else f"{class_id}-{int(indice) + 1:04d}",
                            seed=None if indice is None else (
                                int(self.config.base_seed) + int(class_id) * 1_000_000 + int(indice)
                            ),
                            motivo=f"não executada: {orcamento_esgotado}",
                        )
                resultados.append(ResultadoClasse(
                    class_id, class_id, ok=False, nao_executada_orcamento=True,
                    motivo=f"nao_executada_orcamento: {orcamento_esgotado}",
                ))
                continue
            nome = class_id
            try:
                experimento_cls = self._carregar_classe_experimento(script_path)
            except Exception as exc:
                logger.exception("[%s] FALHOU ao carregar — classe abortada, bateria continua", class_id)
                resultados.append(ResultadoClasse(class_id, nome, ok=False, motivo=str(exc)))
                self.registrar_falha("classe_falhou", classe=class_id, motivo=f"falha ao carregar: {exc}")
                if BENCH_MODE:
                    time.sleep(0.5)
                continue
            nome = getattr(experimento_cls, "nome", class_id)

            ok_geral = True
            motivos: List[str] = []
            descartadas = invalidas = puladas = 0
            config_original = self.config
            self._manter_arquivos_classe = True
            plano_perfis = perfis.plano_de_perfis(
                class_id, lista_perfis, getattr(config_original, "sorteio_posicao", True),
            )
            if selecao is not None:
                escolhidos = selecao.get(class_id, {})
                plano_perfis = [(p, e) for p, e in plano_perfis if p in escolhidos]
            try:
                for posicao_perfil, (perfil, espelhos) in enumerate(plano_perfis):
                    rotulo = f" [perfil {perfil}]" if varios else ""
                    if espelhos:
                        logger.info(
                            "[%s] gerar() não depende do perfil: capturada uma vez (perfil %s); %s "
                            "apontam para a mesma captura no metadata.", class_id, perfil, ", ".join(espelhos),
                        )
                    indices = selecao[class_id][perfil] if selecao is not None else None
                    self.config = self._config_do_perfil(config_original, perfil, espelhos, indices)
                    try:
                        sucesso, ultimo_erro, desc, inval, pul, tentativas_feitas = (
                            self._executar_classe_no_perfil(class_id, script_path, experimento_cls, rotulo)
                        )
                    except LimiteEscritasTraceError as exc:
                        # O resto do perfil corrente já foi registrado por
                        # executar() (captura a captura); faltam os perfis
                        # seguintes desta classe.
                        orcamento_esgotado = str(exc)
                        for perfil_restante, _ in plano_perfis[posicao_perfil + 1:]:
                            self.registrar_falha(
                                "nao_executada_orcamento", classe=class_id, classe_nome=nome,
                                perfil=perfil_restante, motivo=f"não executada: {exc}",
                            )
                        ok_geral = False
                        motivos.append(f"nao_executada_orcamento: {exc}")
                        break
                    except (CommunicationError, FalhaFatalDeInstrumento) as exc:
                        # Continua abortando a bateria (limite inegociável);
                        # só deixa a classe registrada para um rerun manual.
                        self.registrar_falha(
                            "classe_falhou", classe=class_id, classe_nome=nome, perfil=perfil,
                            motivo=f"falha de infraestrutura (bateria abortada): {type(exc).__name__}: {exc}",
                        )
                        raise
                    finally:
                        self.config = config_original
                    descartadas += desc
                    invalidas += inval
                    puladas += pul
                    if not sucesso:
                        self.registrar_falha(
                            "classe_falhou", classe=class_id, classe_nome=nome, perfil=perfil,
                            motivo=str(ultimo_erro),
                        )
                        ok_geral = False
                        motivos.append(
                            f"perfil {perfil}{' (e ' + ', '.join(espelhos) + ', mesma captura)' if espelhos else ''}: "
                            f"{ultimo_erro}" if varios else str(ultimo_erro)
                        )
                        logger.error(
                            "[%s]%s FALHOU definitivamente após %d tentativa(s)%s — classe abortada, "
                            "bateria continua", class_id, rotulo, tentativas_feitas,
                            " (erro determinístico, sem retry)" if tentativas_feitas < self.MAX_TENTATIVAS_POR_CLASSE else "",
                        )
                        self.recuperar_estado_seguro()
            finally:
                self._manter_arquivos_classe = False
                pasta = getattr(config_original, "results_dir", None)
                if pasta is not None:
                    arquivo = self.__dict__.get("_arquivos_classe", {}).pop((str(Path(pasta).resolve()), class_id), None)
                    if arquivo is not None:
                        arquivo.close()

            if orcamento_esgotado is not None:
                resultados.append(ResultadoClasse(
                    class_id, nome, ok=False, motivo="; ".join(motivos), nao_executada_orcamento=True,
                    descartadas=descartadas, invalidas=invalidas, puladas=puladas,
                ))
                # Estado seguro ANTES de qualquer outra coisa; sem confirmação
                # do OFF, FalhaFatalDeInstrumento aborta (infraestrutura).
                self._encerrar_conexao_por_orcamento()
                continue
            if ok_geral:
                resultados.append(ResultadoClasse(
                    class_id, nome, ok=True, descartadas=descartadas, invalidas=invalidas,
                    puladas=puladas,
                ))
            else:
                resultados.append(ResultadoClasse(
                    class_id, nome, ok=False, motivo="; ".join(motivos),
                    descartadas=descartadas, invalidas=invalidas, puladas=puladas,
                ))
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

    def executar_classe_nos_perfis(
        self, experimento_cls: type, perfis_da_rodada_: Optional[Sequence[str]] = None,
    ) -> List["ExperimentoBase"]:
        """``run <NN>``: UMA classe, sem as tentativas de ``executar_bateria``,
        uma vez por perfil (todos no mesmo ``NN_classe.npz``). A primeira
        exceção propaga; o que cada perfil já gravou fica no disco."""
        lista = self._perfis_para_bateria(perfis_da_rodada_)
        config_original = self.config
        executados: List["ExperimentoBase"] = []
        self._perfis_rodada_atual = lista
        self._manter_arquivos_classe = True
        class_id = str(getattr(experimento_cls, "id", ""))
        plano_perfis = perfis.plano_de_perfis(class_id, lista, getattr(config_original, "sorteio_posicao", True))
        try:
            for posicao, (perfil, espelhos) in enumerate(plano_perfis):
                self.config = self._config_do_perfil(config_original, perfil, espelhos)
                experimento = experimento_cls(self)
                executados.append(experimento)
                try:
                    experimento.executar()
                except LimiteEscritasTraceError as exc:
                    for perfil_restante, _ in plano_perfis[posicao + 1:]:
                        self.registrar_falha(
                            "nao_executada_orcamento", classe=class_id,
                            classe_nome=getattr(experimento_cls, "nome", class_id),
                            perfil=perfil_restante, motivo=f"não executada: {exc}",
                        )
                    self.config = config_original
                    self._encerrar_conexao_por_orcamento()
                    raise
                except Exception as exc:
                    self.registrar_falha(
                        "classe_falhou", classe=class_id, classe_nome=getattr(experimento_cls, "nome", class_id),
                        perfil=perfil, motivo=f"{type(exc).__name__}: {exc}",
                    )
                    raise
        finally:
            self.config = config_original
            self._manter_arquivos_classe = False
            pasta = getattr(config_original, "results_dir", None)
            if pasta is not None and executados:
                arquivo = self.__dict__.get("_arquivos_classe", {}).pop(
                    (str(Path(pasta).resolve()), executados[0].id), None,
                )
                if arquivo is not None:
                    arquivo.close()
        return executados

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
        except BracoP09Error:
            # P-09 B/C: offsets de LIST não confirmados zerados (ou AC+DC
            # perdido) — não é estado seguro conhecido; aborta a bateria.
            raise
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

    # A fonte tem de entregar a base (medida dela) e o CH1 tem de ver o mesmo
    # que ela mede, dentro destas tolerâncias. A razão CH1/fonte pega o que a
    # validação física de cada classe só denuncia depois de capturar: probe
    # com fator errado (2x, 10x), probe no ponto errado, ou — bancada
    # 2026-10-07 — disjuntor aberto entre a fonte e a probe (CH1 ~0,45 da
    # fonte + 8 Vrms induzidos: 20 classes reprovadas antes de alguém ver).
    TOL_CADEIA_FONTE_BASE = 0.05
    TOL_CADEIA_OSC_FONTE = 0.10
    TIMEOUT_CADEIA_FONTE_S = 5.0

    def verificar_cadeia_de_medicao(self) -> Dict[str, float]:
        """Com a saída ligada, põe a fonte na senoide base
        (``recuperar_estado_seguro``), espera a MEDIDA dela confirmar a base e
        compara com o Vrms do CH1 numa aquisição forçada. Fora das tolerâncias
        levanta ``CadeiaDeMedicaoError`` (infraestrutura: aborta a bateria
        antes da primeira classe). Devolve as leituras."""
        if self.osc is None:
            return {}
        self.recuperar_estado_seguro()
        base = float(self.config.base_voltage_rms)
        fonte_v = float("nan")
        deadline = time.monotonic() + self.TIMEOUT_CADEIA_FONTE_S
        while True:
            fonte_v = float(self.fonte.measure_voltage())
            if abs(fonte_v - base) <= self.TOL_CADEIA_FONTE_BASE * base:
                break
            if time.monotonic() >= deadline:
                raise CadeiaDeMedicaoError(
                    f"A fonte mede {fonte_v:.2f} Vrms na própria saída {self.TIMEOUT_CADEIA_FONTE_S:.0f} s "
                    f"depois de programada em {base:.2f} Vrms (tolerância "
                    f"{100 * self.TOL_CADEIA_FONTE_BASE:.0f}%). Confira o painel da AMETEK."
                )
            time.sleep(0.25)
        osc_v = float(self.osc.medir_vrms_forcado(1))
        razao = osc_v / fonte_v
        leituras = {"fonte_vrms": fonte_v, "osc_ch1_vrms": osc_v, "razao_osc_fonte": razao}
        if abs(razao - 1.0) > self.TOL_CADEIA_OSC_FONTE:
            raise CadeiaDeMedicaoError(
                f"Cadeia de medição NÃO confere: a fonte mede {fonte_v:.2f} Vrms e o CH1 do "
                f"osciloscópio mede {osc_v:.2f} Vrms (razão {razao:.3f}, tolerância "
                f"±{100 * self.TOL_CADEIA_OSC_FONTE:.0f}%). Confira, com a saída DESLIGADA: "
                f"disjuntores/bornes entre a fonte e a probe, probe no CH1 entre fase A e N, e o "
                f"fator da probe ({VOLTAGE_PROBE_ATTENUATION}) igual à chave dela."
            )
        logger.info(
            "Cadeia de medição OK: fonte %.2f Vrms, CH1 %.2f Vrms (razão %.3f)", fonte_v, osc_v, razao,
        )
        return leituras


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
    # até a v1.12. Desde a v1.13: 3 nas classes que SORTEIAM
    # parâmetros em ``gerar()`` (04, 06, 07, 08, 09, 17, 19, 20; uma captura
    # mostra uma só realização do sorteio), 1 nas determinísticas. Não afeta o dataset simulado (``SIM_CAPTURES_PER_CLASS``)
    # nem a regra de cobertura determinística/caracterização da 08, que
    # continua exigindo ``set capturas`` digitado pelo operador
    # (``capturas_override``). Tabela completa: README, seção "Capturas por
    # classe".
    capturas_padrao: int = 1
    # Pré-trigger sorteado da captura em curso (None = o da classe). Zerado a
    # cada captura por ``executar()``; posto pelas classes nativas de pulso.
    _pre_trigger_atual_s: Optional[float] = None
    # Três versões da captura em curso (docs/tres_versoes.md): {"modelo": gerar(),
    # "programada": o que a fonte emitiria, "origem_programada": texto}. Zerado a
    # cada captura por ``executar()``; posto por ``_capturar_real``.
    _versoes_atuais: Optional[Dict[str, object]] = None

    def forma_programada(
        self, forma_bancada_pu: np.ndarray, parametros: Dict[str, float], capture_index: int,
        t: np.ndarray, programacao=None,
    ) -> Tuple[np.ndarray, str]:
        """Forma "programada" (pu, grade da captura): o que a fonte emite para
        o que o código programou, sem tocar nenhum instrumento.

        Captura TRACe/LIST (``grava_trace``): ``AmetekMX30.montar_programacao``
        sobre ``forma_bancada_pu`` (a já reduzida pelo limite de bancada), a
        MESMA função de ``program_capture`` — k, ciclos, 1024 pontos, pico e
        rms por ciclo. Nativa: ``sinais.forma_programada_nativa``. Devolve
        ``(forma, origem)``; levanta se a classe não tiver como. ``programacao``:
        a ``ProgramacaoCaptura`` que ``program_capture`` acabou de enviar (na
        bancada), em vez de recalculá-la."""
        base = float(self.config.base_voltage_rms)
        f0 = float(self.config.grid_frequency_hz)
        if self.grava_trace(capture_index):
            if programacao is None:
                programacao = AmetekMX30.montar_programacao(
                    forma_bancada_pu, base_voltage_rms=base, frequency_hz=f0,
                    dc_offset_pu=float(parametros.get("dc_offset_pu", 0.0)),
                    passo_final_sin=bool(getattr(self.fonte, "passo_final_sin", False)),
                    p09_braco=str(getattr(self.fonte, "p09_braco", "A")),
                )
            return programacao.programada_pu(), "TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)"
        teto_rms = float(getattr(self.fonte, "max_voltage_rms", 300.0))
        forma = forma_programada_nativa(
            self.id, t=t, f0_hz=f0, base_voltage_rms=base, parametros=parametros,
            quantizar=lambda v: AmetekMX30.quantizar_tensao_rms(v, teto_rms),
            inicio_legado_s=getattr(self, "INICIO_S", None),
            duracao_legada_s=getattr(self, "DURACAO_S", None),
        )
        return forma, f"{FORMA_NATIVA_POR_CLASSE[self.id]} nativo (sinais.forma_programada_nativa)"

    def _metricas_p09(self, capture_index: int) -> Dict[str, object]:
        """Campos P-09 do metadata (só acrescentados): ``p09_braco`` sempre;
        nas capturas TRACe/LIST com modelo e programada, a distância modelo ->
        programada efetiva do braço (``sinais.distancia_modelo_programada``):
        ``media_perdida_maxima_absoluta_pu``, ``erro_rms_modelo_programada_pu``
        e ``salto_pico_modelo_programada_v``. Nunca derruba a captura."""
        campos: Dict[str, object] = {"p09_braco": str(getattr(self.fonte, "p09_braco", "A"))}
        versoes = self._versoes_atuais or {}
        if not self.grava_trace(capture_index) or "programada" not in versoes:
            return campos
        try:
            n = int(round(float(self.config.fs_hz) / float(self.config.grid_frequency_hz)))
            distancia = distancia_modelo_programada(
                versoes["modelo"], versoes["programada"], pontos_por_ciclo=n,
            )
        except (ValueError, TypeError, ZeroDivisionError) as exc:
            logger.warning("[%s] métricas P-09 não calculadas (%s)", self.id, exc)
            return campos
        nominal_v = float(self.config.base_voltage_rms) * math.sqrt(2.0)
        campos.update(
            media_perdida_maxima_absoluta_pu=distancia["media_perdida_maxima_absoluta_pu"],
            erro_rms_modelo_programada_pu=distancia["erro_rms_pu"],
            salto_pico_modelo_programada_v=distancia["salto_pico_pu"] * nominal_v,
        )
        return campos

    def _programacao_enviada(self) -> Optional[ProgramacaoCaptura]:
        """A ``ProgramacaoCaptura`` que o ``program_capture`` que acabou de rodar
        enviou (None com fonte que não a expõe)."""
        programacao = getattr(self.fonte, "ultima_programacao", None)
        return programacao if isinstance(programacao, ProgramacaoCaptura) else None

    def _registrar_versoes(
        self, modelo_pu: np.ndarray, forma_bancada_pu: np.ndarray, parametros: Dict[str, float],
        capture_index: int, t: np.ndarray, programacao=None,
    ) -> None:
        """Guarda modelo e programada da captura em curso. Nunca derruba a
        captura: sem a programada (erro logado) só ela deixa de ser gravada."""
        versoes: Dict[str, object] = {"modelo": np.array(modelo_pu, dtype=np.float64)}
        try:
            programada, origem = self.forma_programada(
                forma_bancada_pu, parametros, capture_index, t, programacao,
            )
            versoes["programada"] = np.asarray(programada, dtype=np.float64)
            versoes["origem_programada"] = origem
        except Exception as exc:  # noqa: BLE001 - produto extra, não pode custar a captura
            if not getattr(self, "_aviso_programada_dado", False):
                self._aviso_programada_dado = True
                logger.warning(
                    "[%s] forma programada não calculada (%s: %s); só o modelo será gravado. "
                    "Aviso uma vez por classe.", self.id, type(exc).__name__, exc,
                )
        self._versoes_atuais = versoes

    @staticmethod
    def _versoes_simuladas_da_classe(
        modelo: np.ndarray, programada: np.ndarray, origens: List[str],
    ) -> Dict[str, np.ndarray]:
        """Arrays empilhados de ``tres_versoes/NN_classe.npz`` (simulado: sem
        medida). Sem nenhuma programada válida, só o modelo."""
        versoes: Dict[str, np.ndarray] = {"modelo_pu": modelo}
        if np.any(np.isfinite(programada)):
            versoes["programada_pu"] = programada
            versoes["origem_programada"] = np.array(origens, dtype=object)
        return versoes

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

    def sortear(self, rng: np.random.Generator, f0: float, **opcoes) -> Sorteio:
        """Início/duração/fase desta captura (ver ``sortear_posicao``). As
        classes chamam dentro de ``gerar()`` e acrescentam
        ``sorteio.parametros()`` ao dicionário que devolvem."""
        return sortear_posicao(rng, self.config, f0, **opcoes)

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
        plano = [
            (indice, indice // capturas_por_nivel if por_nivel else indice)
            for indice in range(total)
        ]
        # Rerun: só os índices escolhidos, com o MESMO indice_global (logo a
        # mesma seed) e o mesmo capture_index do plano original.
        permitidos = getattr(self.config, "indices_permitidos", None)
        if permitidos is not None:
            permitidos = {int(i) for i in permitidos}
            plano = [item for item in plano if item[0] in permitidos]
        return plano

    def grava_trace(self, capture_index: int) -> bool:
        """Esta captura grava TRACEs na Flash da fonte (``program_capture``)?
        Waveform: sempre. Nativa: só os índices de ``usar_trace`` (05 a 30%)."""
        return False

    def rota_programacao(self, capture_index: int) -> str:
        """Rota de programação da captura FÍSICA, gravada em ``rota_programacao``
        (metadata, v1.15): ``"TRACe"`` se grava TRACE, senão ``"nativa"``. A 05
        refina a nativa para ``"CSIN"`` (CSINusoid). Só diagnóstico: não muda
        o que ``gerar()`` produz nem o que vai à fonte."""
        return "TRACe" if self.grava_trace(capture_index) else "nativa"

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
            # Pré-trigger EFETIVO desta captura: o da classe, ou o sorteado
            # (``_pre_trigger_atual_s``, posto por ``_capturar_real`` das nativas).
            "pre_trigger_s": float(
                self._pre_trigger_atual_s if self._pre_trigger_atual_s is not None
                else getattr(self, "pre_trigger_s", 0.0)
            ),
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
            # Procedência repetida em cada captura para o .jsonl sobreviver
            # sozinho (copiado sem a pasta da sessão); o registro completo
            # fica em sessao.json.
            "git_commit": info_do_codigo()["git_commit"],
            "git_sujo": info_do_codigo()["git_sujo"],
            "numpy_versao": np.__version__,
            "calibracao_extremos_sha256": sha256_do_arquivo(CALIBRACAO_EXTREMOS_PATH),
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

    def _inicio_janela_para_metadata(self, metadado: dict, amostras_totais: int) -> dict:
        """``inicio_janela`` = ``indice_trigger - pre_trigger_s * fs_hz``
        (arredondado), limitado a ``[0, amostras_totais - pontos]`` — exatamente
        o que ``sinais.janela_nominal`` devolve, que é o que os leitores
        usavam. ``inicio_janela_ajustado`` = True quando o limite agiu (o
        registro não tinha amostras suficientes e a janela foi empurrada)."""
        fs_hz = float(self.config.fs_hz)
        pontos = int(self.config.points)
        pre_trigger_s = float(metadado.get("pre_trigger_s", 0.0))
        indice_trigger = int(metadado["indice_trigger"])
        trecho = janela_nominal(
            np.arange(amostras_totais), indice_trigger=indice_trigger,
            pre_trigger_s=pre_trigger_s, pontos=pontos, fs_hz=fs_hz,
        )
        inicio = int(trecho[0]) if trecho.size else 0
        ideal = int(round(indice_trigger - pre_trigger_s * fs_hz))
        return {"inicio_janela": inicio, "inicio_janela_ajustado": inicio != ideal}

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
        *, margem_antes: int = 0, inicio_janela: Optional[int] = None,
        avaliacao: Optional[Dict[str, object]] = None,
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
        medido_bruto = medido_pu
        medido_pu = np.asarray(medido_pu, dtype=np.float64)[margem_antes : margem_antes + len(esperado)]
        if medido_pu.size != len(esperado):
            logger.warning(
                "[%s] registro tem %d amostras na janela alinhada; esperado %d — validação física não calculada",
                self.id, medido_pu.size, len(esperado),
            )
            return None
        # Janela alinhada ao TRIGGER real (``inicio_janela`` do metadata; sem
        # ele, ``margem_antes``) para ``conferir_posicao_do_evento``.
        ini = margem_antes if inicio_janela is None else int(inicio_janela)
        tamanho_janela = len(esperado)
        janela_do_trigger = np.asarray(medido_bruto, dtype=np.float64)[ini : ini + tamanho_janela]
        excluidos = tuple(self.ciclos_excluidos_da_validacao(capture_index))
        if excluidos:
            # Remove ciclos INTEIROS dos dois lados: a concatenação continua
            # contínua em fase, então envelope/THD/crista seguem válidos.
            n = int(round(self.config.fs_hz / self.config.grid_frequency_hz))
            manter = [k for k in range(len(esperado) // n) if k not in excluidos]
            esperado = np.concatenate([np.asarray(esperado)[k * n : (k + 1) * n] for k in manter])
            medido_pu = np.concatenate([medido_pu[k * n : (k + 1) * n] for k in manter])
        try:
            resultado = comparar_fisicamente(
                esperado, medido_pu,
                fs_hz=self.config.fs_hz, f0=self.config.grid_frequency_hz,
                tol_envelope=VALIDACAO_TOL_ENVELOPE, tol_thd=VALIDACAO_TOL_THD,
                fator_crista=self.fator_extremo_efetivo_para_validacao(avaliacao),
            )
        except Exception:  # noqa: BLE001
            logger.warning("[%s] validação física não pôde ser calculada", self.id, exc_info=True)
            return None
        if janela_do_trigger.size == tamanho_janela:
            try:
                posicao = self.conferir_posicao_do_evento(capture_index, janela_do_trigger)
            except Exception:  # noqa: BLE001
                logger.warning("[%s] posição do evento não pôde ser conferida", self.id, exc_info=True)
                posicao = None
            if posicao is not None:
                resultado["posicao_evento"] = posicao["posicao"]
                if not posicao["ok"]:
                    resultado["ok"] = False
                    resultado["motivos"] = list(resultado["motivos"]) + list(posicao["motivos"])
        return resultado

    def fator_extremo_efetivo_para_validacao(self, avaliacao: Optional[Dict[str, object]] = None) -> float:
        """Fator de extremo (extremo medido / pico programado) que a validação
        da crista espera para ESTA captura: o mesmo da previsão de pico
        (``_extremo_previsto_da_forma_v``) sem a ``MARGEM_FATOR_EXTREMO`` (a
        tolerância de 10 % da crista já é a folga). Classe com modelo próprio
        da excursão (08) usa 1,0: o impulso fica fora da crista (ciclos
        excluídos) e a tabela não a representa. Captura com o distúrbio
        reduzido (limite de bancada) usa a mesma fórmula de
        ``extremo_previsto_com_disturbio_v`` com margem 1. Sem tabela da
        condição, ``carregar_fatores_extremo`` já devolve o fator conservador."""
        proprio = getattr(self, "excursao_fisica_prevista_v", None)
        if callable(proprio) and proprio() is not None:
            return 1.0
        fatores = self._fatores_extremo()
        fator = fator_extremo_da_classe(self.id, fatores)
        parametros = (avaliacao or {}).get("parametros") or {}
        k = float(parametros.get("fator_disturbio_bancada", 1.0))
        pico = (avaliacao or {}).get("pico_programado_v")
        if k >= 1.0 or not pico or "pico_programado_modelo_v" not in parametros:
            return fator
        efetivo = extremo_previsto_com_disturbio_v(
            float(pico), float(parametros["pico_programado_modelo_v"]), k,
            fator=fator, fator_referencia=fator_referencia_extremo(fator, fatores), margem=1.0,
        ) / float(pico)
        return max(1.0, efetivo)

    def conferir_posicao_do_evento(self, capture_index: int, janela_medida_pu: np.ndarray) -> Optional[dict]:
        """Complemento da validação física para classes cujo evento precisa
        estar num instante conhecido (a 08 exclui os ciclos do impulso do
        envelope/THD e, sem isto, não notaria o impulso 20 ms fora do lugar).
        ``janela_medida_pu``: a janela nominal alinhada ao trigger. Devolve
        ``{"ok", "motivos", "posicao"}`` ou ``None`` (padrão: nada a conferir)."""
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

    def _fatores_extremo(self) -> Dict[str, float]:
        """Tabela de fatores da condição DESTA bancada (tensão base e
        frequência da config), não a do ambiente do processo."""
        return carregar_fatores_extremo(
            tensao_rms=self.config.base_voltage_rms, frequencia_hz=self.config.grid_frequency_hz,
        )

    def _extremo_previsto_da_forma_v(self, pico_v: float, parametros: Dict[str, float]) -> float:
        """Modelo do extremo físico a partir do pico programado e dos
        parâmetros de bancada da captura (ver ``extremo_fisico_previsto_v``)."""
        proprio = getattr(self, "excursao_fisica_prevista_v", None)
        if callable(proprio):
            excursao = proprio()
            if excursao is not None:
                return float(excursao)
        fatores = self._fatores_extremo()
        fator = fator_extremo_da_classe(self.id, fatores)
        k = float(parametros.get("fator_disturbio_bancada", 1.0))
        if k >= 1.0:
            return pico_v * fator * MARGEM_FATOR_EXTREMO
        return extremo_previsto_com_disturbio_v(
            pico_v, float(parametros["pico_programado_modelo_v"]), k,
            fator=fator, fator_referencia=fator_referencia_extremo(fator, fatores),
        )

    def _detalhe_fator_extremo(self, pico_v: float, parametros: Dict[str, float]) -> str:
        """", pico X V × fator Y" para o motivo de pulo, quando a previsão é
        pico × fator × margem (sem modelo próprio nem distúrbio reduzido)."""
        if callable(getattr(self, "excursao_fisica_prevista_v", None)) or float(
            parametros.get("fator_disturbio_bancada", 1.0)
        ) < 1.0:
            return ""
        fator = fator_extremo_da_classe(self.id, self._fatores_extremo())
        return f": {pico_v:.1f} V × {fator:.3f}"

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

    def exigencias_de_capacidade(
        self, capture_index: int, forma_pu: np.ndarray, parametros: Dict[str, float],
    ) -> Dict[str, object]:
        """O que ESTA captura exige da fonte, nos nomes de
        ``ametek_orm.CAPACIDADES_MX30``, sem tocar o instrumento. Frequência da
        rede sempre; captura TRACe/LIST: a ``ProgramacaoCaptura`` que
        ``program_capture`` montaria (passos de LIST, formas no grupo, dwell,
        offsets do braço C). Nativas acrescentam as suas (``exigencias_nativas``)."""
        exigencias: Dict[str, object] = {"frequencia_hz": float(self.config.grid_frequency_hz)}
        if self.grava_trace(capture_index):
            # Só atributos de verdade de AmetekMX30 (um substituto de teste
            # sem eles programa como o padrão: sem SINE final, braço A).
            passo_final_sin = getattr(self.fonte, "passo_final_sin", False)
            braco = getattr(self.fonte, "p09_braco", "A")
            programacao = AmetekMX30.montar_programacao(
                forma_pu, base_voltage_rms=float(self.config.base_voltage_rms),
                frequency_hz=float(self.config.grid_frequency_hz),
                dc_offset_pu=float(parametros.get("dc_offset_pu", 0.0)),
                passo_final_sin=passo_final_sin if isinstance(passo_final_sin, bool) else False,
                p09_braco=braco if isinstance(braco, str) else "A",
            )
            exigencias.update(programacao.exigencias_de_capacidade())
        return exigencias

    def _registrar_falha(
        self, tipo: str, indice_global: Optional[int], capture_index: Optional[int], motivo: str,
    ) -> None:
        """Entrada desta classe/perfil em falhas.json (via ``Bancada.registrar_falha``)."""
        registrar = getattr(getattr(self, "bancada", None), "registrar_falha", None)
        if not callable(registrar):
            return
        try:
            registrar(
                tipo, classe=self.id, classe_nome=getattr(self, "nome", self.id),
                perfil=perfis.perfil_da_config(self.config),
                indice_global=None if indice_global is None else int(indice_global),
                capture_index=None if capture_index is None else int(capture_index),
                nivel_indice=None if capture_index is None else int(capture_index),
                seed=None if indice_global is None else self.seed_da_captura(int(indice_global)),
                id_captura=None if indice_global is None else f"{self.id}-{int(indice_global) + 1:04d}",
                motivo=str(motivo),
            )
        except (CommunicationError, FalhaFatalDeInstrumento):
            raise  # infraestrutura nunca é engolida
        except Exception:  # noqa: BLE001 - o registro nunca derruba a captura
            logger.exception("[%s] não foi possível registrar a falha em falhas.json", self.id)

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
        except Exception as exc:  # noqa: BLE001 - sem previsão não há prova de que cabe
            info["motivo"] = f"extremo previsto incalculável ({type(exc).__name__}: {exc})"
            return info
        # Capacidades do manual (CAPACIDADES_MX30) ANTES de qualquer I/O: o que
        # exceder é pulado com motivo próprio (pulada_capacidade).
        try:
            exigencias = self.exigencias_de_capacidade(capture_index, forma, parametros)
            info["exigencias_capacidade"] = exigencias
            verificar_exigencias(exigencias)
        except CapacidadeExcedidaError as exc:
            info["motivo"] = f"capacidade da fonte excedida: {exc}"
            info["tipo_recusa"] = "pulada_capacidade"
            return info
        except ParameterOutOfBoundsError as exc:
            info["motivo"] = f"programação recusada antes de I/O: {exc}"
            return info
        try:
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
                f"(pico programado × fator medido × margem {MARGEM_FATOR_EXTREMO:.2f}"
                f"{self._detalhe_fator_extremo(pico, parametros)})"
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
                self._registrar_falha(
                    str(info.get("tipo_recusa") or "pulada_preflight"), indice_global, capture_index,
                    str(info["motivo"]),
                )
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

    def _ler_traces_de_diagnostico(self) -> None:
        """``set diagnostico retrieve``: lê de volta as TRACEs que a captura
        corrente gravou e guarda o resultado em ``self._retrieve_atual`` (o
        arquivo e o metadata saem em ``_gravar_diagnostico_trace``).

        Chamado SÓ no fim de ``_capturar_real`` (transiente concluído, registro
        do osciloscópio lido, nada a programar até a próxima captura) e com a
        espera mínima de ``ler_trace`` desde a última escrita de TRACe
        (quirk A2). Falha de leitura (``LeituraTraceError``) é registrada e
        não derruba a captura; mas depois dela confere-se que a fonte ainda
        responde (``aguardar_resposta``): se não, ``CommunicationError`` sobe
        pelo caminho normal de falha de infraestrutura."""
        self._retrieve_atual = None
        if not getattr(self.config, "diagnostico_retrieve", False):
            return
        programacao = self._programacao_enviada()
        if programacao is None:
            logger.warning("[%s] diagnostico retrieve: sem programação para ler de volta", self.id)
            return
        espera_s = float(self.config.diagnostico_retrieve_espera_s)
        if espera_s < 2.0:
            logger.warning(
                "[%s] diagnostico retrieve: espera mínima %.2f s < 2 s (padrão conservador, "
                "docs/quirks.md A2)", self.id, espera_s,
            )
        inicio = time.monotonic()
        lidos: List[np.ndarray] = []
        erro: Optional[str] = None
        try:
            for nome in programacao.trace_names:
                lidos.append(self.fonte.ler_trace(nome, espera_minima_s=espera_s))
        except LeituraTraceError as exc:
            erro = str(exc)
            logger.error(
                "[%s] diagnostico retrieve: leitura de volta falhou (%d/%d TRACEs lidas): %s. "
                "A captura segue.", self.id, len(lidos), len(programacao.trace_names), exc,
            )
        if erro is not None:
            # Não engole mudez real: se a fonte não responde mais, isto levanta
            # CommunicationError e vale o caminho existente de falha fatal.
            self.fonte.aguardar_resposta("*IDN?")
        self._retrieve_atual = {
            "programacao": programacao,
            "lidos": lidos,
            "erro": erro,
            "espera_minima_s": espera_s,
            "duracao_s": time.monotonic() - inicio,
            "espera_efetiva_s": float(getattr(self.fonte, "ultima_espera_leitura_trace_s", 0.0)),
        }

    def _gravar_diagnostico_trace(self, capture_id: str, metadado: dict) -> None:
        """Grava ``<sessao>/diagnostico_trace/<id da captura>.npz`` (enviado x
        lido + ``LIST:VOLTage``) e acrescenta ``diagnostico_trace`` ao
        metadata da captura (desvio máximo, erro). Fora do .npz da captura, e
        independente de ``_salvar_captura``. Nunca levanta por erro de disco."""
        dados = getattr(self, "_retrieve_atual", None)
        self._retrieve_atual = None
        if not dados:
            return
        programacao: ProgramacaoCaptura = dados["programacao"]
        lidos = dados["lidos"]
        enviados = np.asarray(programacao.traces[: len(lidos)], dtype=np.float64)
        lido = np.asarray(lidos, dtype=np.float64) if lidos else np.zeros((0, AmetekMX30.TRACE_POINTS))
        desvios = [float(np.max(np.abs(lido[i] - enviados[i]))) for i in range(len(lidos))]
        info = {
            "arquivo": f"{PASTA_DIAGNOSTICO_TRACE}/{capture_id}.npz",
            "traces_programadas": len(programacao.trace_names),
            "traces_lidas": len(lidos),
            "desvio_max": max(desvios) if desvios else None,
            "desvio_max_por_trace": desvios,
            "erro": dados["erro"],
            "espera_minima_s": dados["espera_minima_s"],
            "espera_efetiva_s": dados["espera_efetiva_s"],
            "duracao_leitura_s": dados["duracao_s"],
        }
        pasta = self.config.results_dir / PASTA_DIAGNOSTICO_TRACE
        final = pasta / f"{capture_id}.npz"
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            parcial = final.with_suffix(".npz.part")
            with parcial.open("wb") as handle:
                np.savez(
                    handle, classe=self.nome, id_captura=np.array([capture_id], dtype=object),
                    nomes=np.array(programacao.trace_names), enviado=enviados, lido=lido,
                    list_voltage_rms=np.asarray(programacao.list_voltages_rms, dtype=np.float64),
                )
            os.replace(parcial, final)
        except OSError as exc:
            logger.error("[%s] diagnostico retrieve: não gravou %s: %s", self.id, final, exc)
            info["erro"] = f"{info['erro'] or ''} gravação do arquivo falhou: {exc}".strip()
            info["arquivo"] = None
        metadado["diagnostico_trace"] = info

    def _preservar_bruto_lido(self, canal: int, sinal_salvo: np.ndarray) -> None:
        """Produto diagnóstico independente; falha fica explícita sem perder a captura."""
        info = {"canal": canal, "arquivo": None, "erro": None}
        if not hasattr(self, "_brutos_atuais"):
            self._brutos_atuais = []
        self._brutos_atuais.append(info)
        try:
            bruto = self.osc.consumir_waveform_bruto(canal)
            if bruto is None:
                raise ValueError("osciloscópio não forneceu snapshot bruto desta leitura")
            contexto = {
                **self._contexto_da_sessao(),
                "aquisicao_id": self._aquisicao_id_atual,
                "classe_id": self.id,
                "seed": self._seed_captura_atual,
                "simulado": False,
                "estado_dataset": "pendente_validacao_e_gravacao",
                "unidade_sinal_salvo": "pu_tensao" if canal == 1 else "pu_corrente",
                "base_sinal_salvo": (self.config.base_voltage_rms * math.sqrt(2.)
                                     if canal == 1 else self.config.current_base_a),
                "parametros": self._parametros_bruto_atuais,
            }
            relativo = bruto_osciloscopio_io.salvar_bruto(
                self.config.results_dir, perfis.perfil_da_config(self.config),
                self._capture_id_atual, canal, bruto, sinal_salvo, metadata_extra=contexto,
            )
            info["arquivo"] = relativo.as_posix()
            info["sinal_salvo_sha256"] = bruto_osciloscopio_io.sha256_array(sinal_salvo)
        except Exception as exc:
            info["erro"] = f"{type(exc).__name__}: {exc}"
            logger.error("[%s] exportação bruta CH%d não preservada: %s", self.id, canal, exc)

    def _ler_captura(
        self, parametros: Dict[str, float]
    ) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], Dict[str, float]]:
        pontos_efetivos = self._pontos_efetivos_captura_atual
        preservar = self.config.preservar_bruto_osciloscopio
        extras = {"preservar_bruto": True} if preservar else {}
        self._parametros_bruto_atuais = dict(parametros)
        time_s, voltage_v = self.osc.get_waveform(1, expected_points=pontos_efetivos, **extras)
        voltage_pu = voltage_v / (self.config.base_voltage_rms * math.sqrt(2.0))
        if preservar:
            self._preservar_bruto_lido(1, voltage_pu)
        current_values = None
        if self.config.capture_current:
            current_time, current_a = self.osc.get_waveform(2, expected_points=pontos_efetivos, **extras)
            current_values = current_a / float(self.config.current_base_a)
            if preservar:
                self._preservar_bruto_lido(2, current_values)
            if not np.allclose(current_time, time_s, rtol=0, atol=1e-9):
                raise RuntimeError("CH1 e CH2 possuem eixos temporais diferentes")
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
    # Desde 2026-09-22 (P10, decisão de projeto) esta margem deixou de ser
    # opt-in — não existe mais ``set margin on|off`` nem modo "sem margem"
    # para captura física; é sempre aplicada. NÃO reduzir abaixo disto sem
    # refazer a medida (ver `arquivo/analises:docs/analise-2026-09-21/01_conclusao_investigacao.md` §2(i)).
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
        versoes: Optional[Dict[str, np.ndarray]] = None,
    ) -> None:
        """Grava a classe completa no formato 2 (``logica/sessao_io.py``,
        ``docs/dataset.md``): UM ``{id}_{nome}.npz`` comprimido com as capturas
        EMPILHADAS por perfil (``<perfil>/medida|modelo|programada``), as SNRs
        em ``snr_XXdb/{id}_{nome}.npz``, a corrente em ``corrente/`` e o
        ``metadata/{id}_{nome}.jsonl`` (1 linha por captura e perfil).

        * ``simulated=True`` (dataset sintético): todas as capturas de uma vez
          (``_salvar_classe_simulada``).
        * ``simulated=False`` (bancada real): uma captura por vez
          (``_iniciar_gravacao_incremental``/``_salvar_captura``/
          ``_finalizar_gravacao``): cada uma vai para ``parcial/`` (atômica) assim
          que existe e o ``.npz`` da classe é reescrito ao fim do perfil ou ao
          interromper. Este método existe com a mesma assinatura de sempre
          porque é a porta de entrada de quem já tem a classe inteira em memória.

        O ``.npz`` da classe tem nome fixo: a mesma classe rodada de novo no
        mesmo perfil substitui o bloco dele (com a mesma ``Bancada``) ou o
        arquivo inteiro (``Bancada`` nova); não existem mais órfãos por captura.
        Escrita atômica (``.part`` -> ``os.replace``, todos os ``.part`` antes
        de qualquer promoção); os dados puros são o que efetivamente saiu do
        gerador/instrumento e o ruído AWGN fica sempre à parte, de modo que
        reaplicar ruído no futuro não exige regerar nem recapturar nada.
        """
        config = self.config
        config.results_dir.mkdir(parents=True, exist_ok=True)

        if simulated:
            self._salvar_classe_simulada(
                tempo_ms=tempo_ms, tensao_limpa=tensao_limpa, tensao_por_snr=tensao_por_snr,
                ids=ids, corrente=corrente, metadados=metadados, versoes=versoes,
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

    def _arquivo_da_classe(self) -> "sessao_io.ArquivoDaClasse":
        """Acumulador do ``NN_classe.npz`` desta classe NESTA sessão. Vive na
        ``Bancada`` (uma conexão): os perfis de um ``set perfil todos`` caem no
        mesmo arquivo; uma ``Bancada`` nova, na mesma pasta, recomeça a classe
        (como a rodada nova sempre substituiu a anterior)."""
        pai = getattr(self, "bancada", None)
        registro = (pai if pai is not None else self).__dict__.setdefault("_arquivos_classe", {})
        chave = (str(Path(self.config.results_dir).resolve()), self.id)
        arquivo = registro.get(chave)
        if arquivo is None:
            arquivo = registro[chave] = sessao_io.ArquivoDaClasse(
                self.config.results_dir, self.id, self.nome, spool=self.osc is not None,
            )
        return arquivo

    def _liberar_arquivo_da_classe(self) -> None:
        """Solta o acumulador da classe (a memória das capturas) quando esta
        execução não faz parte de uma bateria que ainda vai gravar outro
        perfil nele (``Bancada.executar_bateria`` solta no fim da classe)."""
        pai = getattr(self, "bancada", None)
        if pai is not None and getattr(pai, "_manter_arquivos_classe", False):
            return
        registro = (pai if pai is not None else self).__dict__.get("_arquivos_classe", {})
        arquivo = registro.pop((str(Path(self.config.results_dir).resolve()), self.id), None)
        if arquivo is not None:
            arquivo.close()

    def _iniciar_gravacao_incremental(self) -> None:
        """Abre o bloco do perfil atual no ``NN_classe.npz`` da classe e zera
        o estado de gravação. Depois disto cada captura pode ir para o disco
        sozinha (``parcial/``), e o arquivo da classe é reescrito por inteiro
        em ``_finalizar_gravacao``."""
        config = self.config
        config.results_dir.mkdir(parents=True, exist_ok=True)
        preparar_pasta_da_sessao(config.results_dir, bancada=self.osc is not None)
        metadata_dir = config.results_dir / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        perfil = perfis.perfil_da_config(config)
        arquivo = self._arquivo_da_classe()
        arquivo.iniciar_perfil(perfil)
        self._gravacao = {
            "arquivo": arquivo,
            "perfil": perfil,
            "registros": [],
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
        versoes: Optional[Dict[str, object]] = None,
    ) -> None:
        """Entrega UMA captura (medida + modelo + programada + cada SNR +
        corrente) ao acumulador da classe (``sessao_io.ArquivoDaClasse``), que
        a grava de imediato em ``parcial/`` (atômica, por captura). O
        ``NN_classe.npz`` com todas as capturas é reescrito por
        ``_finalizar_gravacao`` (ao fim do perfil ou ao interromper a classe).

        É o que teria salvo as 7 capturas boas de 08 e as 52 de 03 da sessão 2
        (relatório 01 §3 P1): uma falha na captura k nunca perde as k-1 boas.
        O metadata ganha ``arquivo_classe``, ``perfil`` e ``indice_no_arquivo``
        (a linha dela dentro do bloco do perfil)."""
        config = self.config
        gravacao = self._gravacao
        gravacao["indice"] += 1
        registro = np.asarray(tensao_limpa_captura)
        pontos = int(metadado.get("pontos", config.points))
        # Medida = registro inteiro (com a margem de captura); a janela
        # rotulada começa em inicio_janela (docs/tres_versoes.md).
        inicio = metadado.get("inicio_janela")
        if inicio is None:
            inicio = metadado.get("margem_amostras_antes", 0)
        inicio = max(0, min(int(inicio), max(0, registro.size - pontos)))
        modelo = programada = origem = None
        if versoes:
            modelo = versoes.get("modelo")
            programada = versoes.get("programada")
            origem = versoes.get("origem_programada")
            metadado["tres_versoes"] = {
                "arquivo": gravacao["arquivo"].nome_arquivo,
                "programada": origem,
            }
        gravacao["arquivo"].adicionar(
            gravacao["perfil"], id_captura=id_captura, medida=registro, tempo_ms=tempo_ms,
            fs_hz=config.fs_hz, modelo=modelo, programada=programada, origem_programada=origem,
            inicio_janela=inicio, pontos=pontos, snr=tensao_por_snr_captura,
            corrente=corrente_captura, metadado=metadado,
        )
        gravacao["linhas"] += 1
        gravacao["registros"].append(metadado)

    def _finalizar_gravacao(self, *, parcial: bool) -> None:
        """Promove o ``NN_classe.npz`` (+ ``snr_XXdb/`` + ``corrente/``) e o
        ``metadata/NN_classe.jsonl`` com TUDO o que a classe já tem (os perfis
        anteriores da rodada incluídos), mesmo quando a rodada foi
        interrompida (``parcial=True``): o que já foi capturado nunca se perde."""
        gravacao = getattr(self, "_gravacao", None)
        if not gravacao:
            return
        self._gravacao = None
        arquivo = gravacao["arquivo"]
        if gravacao["linhas"] == 0:
            arquivo.encerrar_perfil(gravacao["perfil"])
            return
        self._gravar_arquivos_da_classe(arquivo, parcial=parcial)
        arquivo.encerrar_perfil(gravacao["perfil"])
        if parcial:
            logger.error(
                "[%s] classe interrompida: %d captura(s) do perfil %s preservada(s) em %s/%s "
                "(metadata PARCIAL)",
                self.id, gravacao["linhas"], gravacao["perfil"], self.config.results_dir,
                arquivo.nome_arquivo,
            )

    def _gravar_arquivos_da_classe(self, arquivo: "sessao_io.ArquivoDaClasse", *, parcial: bool = False) -> None:
        """Dados primeiro (todos os ``.part`` antes de qualquer promoção), o
        metadata depois — o metadata sobrevivente nunca descreve dado que não
        foi gravado. Com ``config.perfis_espelho`` (classe independente do
        perfil num ``set perfil todos``) e a classe terminada (não ``parcial``),
        os outros perfis são declarados espelho desta captura antes de gravar
        (``ArquivoDaClasse.espelhar``: mesmo arquivo, índice e SHA-256)."""
        espelhos = tuple(getattr(self.config, "perfis_espelho", ()))
        if espelhos and not parcial:
            arquivo.espelhar(perfis.perfil_da_config(self.config), espelhos)
        arquivo.consolidar()
        metadata_dir = Path(self.config.results_dir) / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        metadata_final = metadata_dir / f"{self.id}_{self.nome.lower()}.jsonl"
        metadata_partial = metadata_final.with_suffix(".jsonl.part")
        registros = arquivo.registros()
        with metadata_partial.open("w", encoding="utf-8") as handle:
            for registro in registros:
                handle.write(json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(metadata_partial, metadata_final)
        _gravar_metadata_legivel(metadata_final, registros)

    def _salvar_classe_simulada(
        self,
        *,
        tempo_ms: np.ndarray,
        tensao_limpa: np.ndarray,
        tensao_por_snr: Dict[float, np.ndarray],
        ids: List[str],
        corrente: Optional[np.ndarray],
        metadados: List[dict],
        versoes: Optional[Dict[str, np.ndarray]] = None,
    ) -> None:
        """Dataset sintético: o bloco do perfil atual (todas as capturas) vai
        para o ``NN_classe.npz`` da classe (formato 2, ``sessao_io``), com
        medida = a série do dataset, modelo e programada; SNRs em
        ``snr_XXdb/NN_classe.npz`` e corrente em ``corrente/``. Escrita
        atômica: tudo grava em ``.part`` e só é promovido depois que TODOS os
        arquivos terminaram sem erro — nunca deixa uma classe meio gravada.
        """
        config = self.config
        preparar_pasta_da_sessao(config.results_dir, bancada=False)
        perfil = perfis.perfil_da_config(config)
        arquivo = self._arquivo_da_classe()
        arquivo.iniciar_perfil(perfil)
        pontos = int(tensao_limpa.shape[1])
        for linha, registro in enumerate(metadados):
            modelo = programada = origem = None
            if versoes:
                modelo = versoes["modelo_pu"][linha]
                if "programada_pu" in versoes:
                    programada = versoes["programada_pu"][linha]
                if "origem_programada" in versoes:
                    origem = str(versoes["origem_programada"][linha]) or None
                registro["tres_versoes"] = {"arquivo": arquivo.nome_arquivo, "programada": origem}
            arquivo.adicionar(
                perfil, id_captura=ids[linha], medida=tensao_limpa[linha], tempo_ms=tempo_ms,
                fs_hz=config.fs_hz, modelo=modelo, programada=programada, origem_programada=origem,
                inicio_janela=0, pontos=pontos,
                snr={snr_db: tensao[linha] for snr_db, tensao in tensao_por_snr.items()},
                corrente=None if corrente is None else corrente[linha], metadado=registro,
            )
        self._gravar_arquivos_da_classe(arquivo)

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
        # Igual ao total dimensionado no caminho normal; menor num rerun
        # (``config.indices_permitidos``).
        total = len(plano)
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
        self._margem_antes_amostras = margem_antes
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
        # Ruído só na janela rotulada (config.points amostras), sem as margens.
        tensao_por_snr: Dict[float, np.ndarray] = {
            snr_db: np.empty((total, self.config.points), dtype=np.float64)
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
        # Simulado: modelo e programada empilhados (None até a 1.ª captura).
        versoes_modelo = np.empty((total, pontos_efetivos), dtype=np.float64) if simulated else None
        versoes_programada = np.full((total, pontos_efetivos), np.nan) if simulated else None
        origens_programada: List[str] = [""] * total
        if not simulated:
            # Gravação incremental: cada captura vai para o disco assim que
            # sai (ver _salvar_captura). Sem isto, uma falha na captura k
            # jogava fora as k-1 boas, que só existiam em memória —
            # exatamente o que aconteceu com as 7 capturas de 08 e as 52 de
            # 03 na sessão 2 (relatório 01 §3 P1, caminho #1).
            self._iniciar_gravacao_incremental()
        try:
            posicao = 0
            for posicao, (indice_global, capture_index) in enumerate(plano):
                seed = self.seed_da_captura(indice_global)
                rng = np.random.default_rng(seed)
                capture_id = f"{self.id}-{indice_global + 1:04d}"
                self._capture_id_atual = capture_id
                self._seed_captura_atual = seed
                self._aquisicao_id_atual = uuid4().hex if not simulated and self.config.preservar_bruto_osciloscopio else None
                self._brutos_atuais = []
                self._pre_trigger_atual_s = None
                self._versoes_atuais = None

                if simulated:
                    voltage_pu, parametros = self.gerar(t, self.config.grid_frequency_hz, capture_index, rng)
                    voltage_pu = np.asarray(voltage_pu, dtype=np.float64)
                    if voltage_pu.shape != (self.config.points,) or not np.all(np.isfinite(voltage_pu)):
                        raise RuntimeError(f"gerar() do experimento {self.id} produziu forma inválida")
                    # Programada ideal do dataset: sem o limite de bancada (a
                    # 08 mantém os 5-10 pu da especificação).
                    self._registrar_versoes(voltage_pu, voltage_pu, parametros, capture_index, t)
                    versoes_modelo[posicao] = voltage_pu
                    if "programada" in self._versoes_atuais:
                        versoes_programada[posicao] = self._versoes_atuais["programada"]
                        origens_programada[posicao] = str(self._versoes_atuais["origem_programada"])
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
                        # próxima posição do plano, sem retentar do zero (decisão de
                        # projeto de 2026-09-22, ver o comentário acima). Nada é gravado para
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
                        self._registrar_falha(
                            "descartada", indice_global, capture_index, f"{type(exc).__name__}: {exc}",
                        )
                        continue
                tempo_ms_eixo = time_s * 1000.0
                ids.append(capture_id)
                tensao_limpa[posicao] = measured_voltage_pu

                if corrente is not None and measured_current_pu is not None:
                    corrente[posicao] = measured_current_pu

                # Início/duração/fase sorteados saem de ``parametros`` (onde
                # gerar() os põe) para o nível de cima do metadata.
                parametros = dict(parametros)
                sorteados = {chave: parametros.pop(chave) for chave in CHAVES_SORTEIO if chave in parametros}
                metadados.append({
                    "id_captura": capture_id,
                    "classe": self.nome,
                    "seed": seed,
                    "simulado": simulated,
                    "perfil": perfis.perfil_da_config(self.config),
                    "sorteio_posicao": bool(getattr(self.config, "sorteio_posicao", True)),
                    **sorteados,
                    "fs_hz": self.config.fs_hz,
                    "pontos": self.config.points,
                    "parametros": parametros,
                    "nivel_indice": capture_index if (cobertura_por_nivel_ativa or not simulated) else 0,
                })
                metadados[-1].update(self._metricas_p09(capture_index))
                rerun_de = getattr(self.config, "rerun_de", None)
                if rerun_de:
                    # Rerun (v1.15, acrescentado): sessão e captura de origem.
                    metadados[-1]["rerun_de"] = {
                        "sessao": rerun_de.get("sessao"), "id_captura": capture_id,
                        "perfil": metadados[-1]["perfil"],
                    }
                extremos: Dict[str, object] = {}
                if not simulated:
                    metadados[-1].update(self._contexto_da_sessao())
                    metadados[-1]["rota_programacao"] = self.rota_programacao(capture_index)
                    self._gravar_diagnostico_trace(capture_id, metadados[-1])
                    if self.config.preservar_bruto_osciloscopio:
                        metadados[-1]["bruto_osciloscopio"] = {
                            "aquisicao_id": self._aquisicao_id_atual,
                            "arquivos": list(self._brutos_atuais),
                            "escopo": "exportação BYTE/NORMal antes de interpolar, não memória interna completa",
                        }
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
                if not simulated and metadados[-1].get("indice_trigger") is not None:
                    # Início da janela nominal dentro do registro, já calculado
                    # (mesma conta de janela_nominal()/recortar_margem.py).
                    metadados[-1].update(self._inicio_janela_para_metadata(metadados[-1], pontos_efetivos))
                # Ruído AWGN só na janela rotulada (inicio_janela .. +points),
                # nunca nas margens; mede também o ruído próprio da bancada
                # (margem anterior) e grava SNR acrescentado/bancada/efetivo.
                inicio_ruido = metadados[-1].get("inicio_janela")
                if inicio_ruido is None:
                    inicio_ruido = margem_antes
                inicio_ruido = max(0, min(int(inicio_ruido), max(0, pontos_efetivos - self.config.points)))
                ruido = ruido_na_janela(
                    measured_voltage_pu, inicio_ruido, self.config.points,
                    self.config.snr_levels_db, seed, simulado=simulated,
                )
                for snr_db, janela_ruidosa in ruido["janelas"].items():
                    tensao_por_snr[snr_db][posicao] = janela_ruidosa
                metadados[-1].update(ruido["metadata"])
                if not simulated and self._pre_trigger_atual_s is not None and metadados[-1].get("indice_trigger") is not None:
                    # Pré-trigger sorteado: o trigger tem de ter caído onde foi
                    # pedido (pre_trigger + margem), na grade de 30 kSa/s.
                    previsto = int(round(self._pre_trigger_atual_s * self.config.fs_hz)) + margem_antes
                    desvio = int(metadados[-1]["indice_trigger"]) - previsto
                    metadados[-1]["pre_trigger_desvio_amostras"] = desvio
                    if abs(desvio) > 2:
                        logger.warning(
                            "[%s] captura %s: trigger na amostra %d, esperado %d (pré-trigger sorteado "
                            "%.3f ms); o recorte por inicio_janela segue o trigger REAL.",
                            self.id, capture_id, metadados[-1]["indice_trigger"], previsto,
                            1000.0 * self._pre_trigger_atual_s,
                        )
                if not simulated:
                    validacao = self._validar_fisicamente(
                        capture_index, t, seed, measured_voltage_pu,
                        margem_antes=margem_antes,
                        inicio_janela=metadados[-1].get("inicio_janela"),
                        avaliacao=getattr(self, "_avaliacoes_bancada", {}).get(indice_global),
                    )
                    if validacao is not None:
                        metadados[-1]["validacao_fisica"] = validacao
                        if not validacao["ok"]:
                            capturas_invalidas.append((capture_id, validacao["motivos"]))
                            self._registrar_falha(
                                "invalida", indice_global, capture_index,
                                "validação física: " + "; ".join(map(str, validacao["motivos"])),
                            )
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
                        versoes=self._versoes_atuais,
                    )
                    logger.info("[%s] captura %d/%d gravada", self.id, posicao + 1, total)
                    # Só DEPOIS de gravada: a captura que passou do teto é a evidência.
                    self._conferir_extremos_fisicos(capture_id, extremos)

        except BaseException as exc:
            if isinstance(exc, LimiteEscritasTraceError):
                # Orçamento de TRACe esgotado NESTA captura: ela e as seguintes
                # do plano ficam em falhas.json para ``run falhas``.
                for indice_restante, capture_restante in plano[posicao:]:
                    self._registrar_falha(
                        "nao_executada_orcamento", indice_restante, capture_restante,
                        f"não executada: {exc}",
                    )
            # Fecha a gravação incremental PRESERVANDO o que já foi para o
            # disco (metadata parcial promovido, limpeza de órfãos suprimida)
            # antes de deixar a exceção subir para executar_bateria().
            if not simulated:
                try:
                    self._finalizar_gravacao(parcial=True)
                except Exception:  # noqa: BLE001 - não mascara o erro original; o spool em parcial/ guarda as capturas
                    logger.exception(
                        "[%s] não foi possível consolidar o .npz da classe interrompida; as capturas "
                        "feitas ficam em parcial/ (sessao_io.recuperar_parcial)", self.id,
                    )
            self._liberar_arquivo_da_classe()
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
            self._liberar_arquivo_da_classe()
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
                versoes=self._versoes_simuladas_da_classe(versoes_modelo, versoes_programada, origens_programada),
            )
            self._liberar_arquivo_da_classe()
        logger.info("[%s] classe concluída: %s", self.id, self.nome)


class ExperimentoNativo(ExperimentoBase):
    """Classes cujo distúrbio é um recurso NATIVO da AMETEK (PULSe/LIST/CSINe).

    Cada subclasse implementa ``configurar(capture_index)``, que manda os
    comandos SCPI nativos por métodos semânticos de ``self.fonte``
    (``trigger_step``/``trigger_pulse``/``configure_harmonics_csine``/...) —
    nunca ``self.fonte.write()`` cru — e devolve os parâmetros físicos
    daquela captura (ex.: nível de sag).
    """

    # Duração do evento sorteada por gerar() para a captura em curso (None =
    # a da classe); posta por ``_capturar_real`` antes de ``configurar()``.
    _duracao_sorteada_s: Optional[float] = None

    def largura_do_pulso_s(self, legada_s: float) -> float:
        """Largura do PULSe desta captura: a sorteada por ``gerar()`` (v1.15)
        ou, sem sorteio, a ``legada_s`` de sempre."""
        return float(legada_s if self._duracao_sorteada_s is None else self._duracao_sorteada_s)

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

    def exigencias_nativas(self, capture_index: int, parametros: Dict[str, float]) -> Dict[str, object]:
        """Exigências do transiente nativo desta captura (nomes de
        ``CAPACIDADES_MX30``), sem tocar a fonte. Padrão: PULSe (02/03/04) exige
        ``pulse_width_s`` = duração sorteada por ``gerar()`` (ou a legada,
        ``DURACAO_S``) — a mesma de ``largura_do_pulso_s``. 18 e 19 sobrescrevem."""
        if FORMA_NATIVA_POR_CLASSE.get(str(self.id)) == "PULSe":
            legada = getattr(self, "DURACAO_S", None)
            largura = parametros.get("duracao_s", legada)
            if largura is not None:
                return {"pulse_width_s": float(largura)}
        return {}

    def exigencias_de_capacidade(self, capture_index, forma_pu, parametros):
        exigencias = super().exigencias_de_capacidade(capture_index, forma_pu, parametros)
        if not self.grava_trace(capture_index):
            exigencias.update(self.exigencias_nativas(capture_index, parametros))
        return exigencias

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

    def fase_de_disparo_graus(self, pre_trigger_s: Optional[float] = None, fase_graus: float = 0.0) -> float:
        """Fase que ``gerar()`` tem no instante do trigger.

        ``gerar()`` põe fase 0 em t=0 da janela e o trigger cai em
        ``pre_trigger_s``; a fonte dispara na fase de
        ``TRIGger:SYNChronize:PHASe``. Com 0° fixo, 02/03/04 (pré-trigger de
        60 ms = 3,6 ciclos a 60 Hz) saíam defasadas 216° do modelo — sessão
        2026-09-30 14:44: correlação -0,78 contra ``gerar()``, 0,999 contra
        o modelo com fase 0 no trigger, e a THD da 04 reprovada (3,38% contra
        4,61%) porque o corte físico começava no zero e o do modelo num
        degrau. Disparando na fase do modelo, a bancada reproduz o dataset."""
        # v1.15: com início/fase sorteados, o trigger cai em ``pre_trigger_s``
        # sorteado e a senoide tem ``fase_graus`` em t = 0: a fase de disparo é
        # ``fase_graus + 360 f0 pre_trigger``. Sem argumentos, o de sempre.
        pre = float(self.pre_trigger_s if pre_trigger_s is None else pre_trigger_s)
        ciclos = pre * float(self.config.grid_frequency_hz)
        return round(((ciclos % 1.0) * 360.0 + float(fase_graus)) % 360.0, 1) % 360.0

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
            self._registrar_versoes(
                voltage_pu, voltage_pu, parametros, capture_index, t, self._programacao_enviada(),
            )
            self.osc.arm()
            self.osc.wait_for_armed()
            self.fonte.arm_transient()
        else:
            # gerar() é a fonte da verdade da posição: a fonte e o
            # osciloscópio reproduzem o que ele sorteou (v1.15).
            modelo_pu, gerados = self.gerar(t, self.config.grid_frequency_hz, capture_index, rng)
            sorteados = {chave: gerados[chave] for chave in CHAVES_SORTEIO if chave in gerados}
            self._duracao_sorteada_s = sorteados.get("duracao_s")
            if "inicio_disturbio_s" in sorteados:
                pre_trigger_s = float(sorteados["inicio_disturbio_s"])
                self.osc.definir_pre_trigger(
                    duration_s=self._pontos_efetivos_captura_atual / self.config.fs_hz,
                    pre_trigger_s=pre_trigger_s + self._margem_antes_amostras / self.config.fs_hz,
                )
                self._pre_trigger_atual_s = pre_trigger_s
            else:
                pre_trigger_s = None
            self.fonte.definir_fase_de_disparo(
                self.fase_de_disparo_graus(pre_trigger_s, sorteados.get("fase_graus", 0.0))
            )
            parametros = {**self.configurar(capture_index), **sorteados}
            self._registrar_versoes(modelo_pu, modelo_pu, parametros, capture_index, t)
            self.osc.arm()
            self.osc.wait_for_armed()
            self.fonte.arm()
        self.fonte.trigger()
        self.osc.wait_for_trigger_complete(timeout_s=5.0)
        self.fonte.wait_transient_complete(timeout_s=5.0)
        resultado = self._ler_captura(parametros)
        if self.usar_trace(capture_index):
            self._ler_traces_de_diagnostico()
        return resultado


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
        """Opção (b) para 220 V: se o extremo previsto da forma do
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
        fatores = self._fatores_extremo()
        fator = fator_extremo_da_classe(self.id, fatores)
        fator_ref = fator_referencia_extremo(fator, fatores)
        voltage_pu = np.asarray(voltage_pu, dtype=np.float64)
        pico_modelo_v = float(np.max(np.abs(voltage_pu))) * nominal_v
        if pico_modelo_v * fator * MARGEM_FATOR_EXTREMO <= teto + 1e-9:
            return voltage_pu
        n = voltage_pu.size
        t = np.arange(n, dtype=np.float64) / self.config.fs_hz
        # A senoide base de gerar() tem a fase sorteada (v1.15); sem sorteio,
        # tau = 0 e a conta é a de sempre.
        f0 = self.config.grid_frequency_hz
        tau = float(parametros.get("fase_graus", 0.0)) / (360.0 * f0)
        senoide = np.sin(2.0 * np.pi * f0 * (t + tau))
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
        modelo_pu = voltage_pu.copy()
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
        self._registrar_versoes(
            modelo_pu, voltage_pu, parametros, capture_index, t, self._programacao_enviada(),
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
        resultado = self._ler_captura(parametros)
        # Só aqui: transiente concluído, osciloscópio já lido, nenhuma
        # programação por vir antes da próxima captura.
        self._ler_traces_de_diagnostico()
        return resultado


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
# referência histórica; o orçamento operacional é menor e bloqueia a execução.
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
    plano = experimento.plano_de_capturas(False)
    # Igual a ``total`` sem filtro; num rerun, só as capturas escolhidas.
    total = len(plano)
    com_trace = sum(1 for _, capture_index in plano if experimento.grava_trace(capture_index))
    return {
        "padrao": int(experimento.capturas_padrao),
        "niveis": experimento.total_niveis() if por_nivel else 1,
        "por_nivel": capturas_por_nivel,
        "total": total,
        # Com o sorteio de início/duração/fase (v1.15) cada captura TRACE tem
        # forma única e o cache de program_capture (forma idêntica na mesma
        # conexão) nunca reaproveita: a conta é EXATA, salvo a poda de
        # _indices_viaveis, que só pode diminuir. Sem sorteio, é um teto.
        "escritas_trace": com_trace * ciclos,
        "escritas_trace_exatas": bool(getattr(config, "sorteio_posicao", True)),
    }


def estimar_escritas_trace_bateria(
    scripts: Sequence[Path], config: Optional[Config] = None,
    perfis_selecionados: Optional[Sequence[str]] = None,
) -> int:
    """Teto offline por conexão, contando somente perfis com aquisição própria."""
    config = config or _build_config()
    selecionados = tuple(perfis_selecionados or perfis_da_rodada())
    total = 0
    for script in scripts:
        tipo = Bancada._carregar_classe_experimento(script)
        for perfil, _ in perfis.plano_de_perfis(
            script.stem, selecionados, config.sorteio_posicao,
        ):
            total += capturas_efetivas_da_classe(tipo, replace(config, perfil=perfil))["escritas_trace"]
    return total


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
        if BENCH_MODE:
            escritas = estimar_escritas_trace_bateria(scripts)
            if escritas > LIMITE_ESCRITAS_TRACE_CONEXAO:
                raise LimiteEscritasTraceError(
                    f"Estimativa sem retentativas: {escritas} gravações TRACe; orçamento por conexão "
                    f"é {LIMITE_ESCRITAS_TRACE_CONEXAO} (o ORM aborta a bateria se esgotar). "
                    "Divida classes/capturas em conexões novas pela CLI; nenhum instrumento foi aberto."
                )
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
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
