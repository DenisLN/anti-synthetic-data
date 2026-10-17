"""Diagnóstico de bancada: que forma a MX30 emite em cada passo do LIST de TRACEs?

Contexto (CHANGELOG/v1.15.md, "Diagnóstico da cópia do evento em 100 ms"): nas
capturas de 07/10 o início do evento da 08 e da 09 aparece repetido ou
deslocado em 100,0 ms, a 50 e a 60 Hz. A montagem da TRACE está descartada
como causa. Este script programa, pelo MESMO caminho das classes
(``AmetekMX30.program_capture`` + ``KeysightDSOX4034A``), capturas TRACe em que
é possível dizer, olhando só a medida, QUAL passo programado saiu em cada ciclo
e com que atraso:

  marcadores   senoide de 1 pu e, em cada ciclo k, UM marcador (lombada de 24
               amostras) de posição e amplitude ÚNICAS por ciclo. Na medida, o
               par (posição, amplitude) de cada marcador diz de que passo ele
               veio; (ciclo medido - k) é a troca de passo e o resto é o atraso.
  fronteira    um impulso estreito no PONTO 0 de um ciclo (o caso da 08 a 50 Hz
               em 80 ms), repetido em cada ``--instantes-evento-ms`` (padrão 40 e 80 ms).
  meio_ciclo   o mesmo impulso a MEIO ciclo (aproxima a 09 a 60 Hz), idem.

Rodar o evento em dois instantes (40 e 80 ms; a 50 Hz os ciclos 2 e 4, a 60 Hz os
ciclos 3 e 5) separa
"ponto 0 do ciclo" (a cópia acompanha o ciclo) de "instante fixo" (a cópia cai
em 100 ms nos dois). Por captura, o relatório traz: marcadores/picos
observados, o passo que cada um tocou, a troca de passo e o instante em que
começa, o atraso em amostras, picos espúrios (sem marcador programado) e o
ranking das hipóteses de ``logica/modelo_lista_fonte.py`` contra a medida.

Segurança (AGENTS.md, "Limites inegociáveis" — nada aqui os altera):
* Mesmos limites do ``start_bench_windows.ps1`` para range 300 V
  (max_voltage_rms=300, max_peak_v=415,8, 0,5 A); COM10/115200 vêm do ORM;
  ``configure_safe_baseline`` mantém as validações de IDN, SCPI e pico.
  ``program_capture`` só AVISA sobre pico acima do limite; por isso o script
  recusa, ANTES de energizar, qualquer forma planejada cujo pico reconstruído
  ou rms de passo passe do limite.
* A saída só é ligada depois de você DIGITAR ``ENERGIZAR-MARCADORES``
  (case-sensitive). Em ``--simulado`` nada é energizado e a confirmação não é
  pedida. Sem ``BENCH_MODE=1`` só ``--simulado`` roda. ``--probe`` é
  obrigatório (fator ESCRITO na probe; sem valor padrão).
* Nenhuma consulta à fonte depois de ``TRACe:DATA`` além das que o fluxo normal
  de ``arm_transient`` já faz (achado da v1.12).
* No ``finally`` o script manda ``safe_shutdown()`` (ABORt + OUTPut OFF +
  confirmação). Se a infraestrutura falhar (serial, OUTPUT não confirmado):
  confirme OUTPUT OFF no painel, NÃO repita automaticamente e entregue o
  ``logs/diag_marcadores_trace-*.log`` mais recente.
* Custo de Flash: cada captura grava um TRACe por ciclo. O script soma as
  gravações planejadas e recusa passar de 216 (a fonte travou na ~280.ª em
  2026-09-16; ``docs/quirks.md`` A3). Reduza ``--frequencias`` ou
  ``--variantes`` e rode em duas vezes, reiniciando a conexão.

Feche a CLI da bancada (libera COM10 e o USB do Keysight) antes de rodar.

Uso (PowerShell, na raiz do projeto, com o fator da probe escrito nela):

    $env:BENCH_MODE = "1"
    env\\Scripts\\python.exe scripts\\diag_marcadores_trace.py --probe 500 --vrms 127

Teste sem hardware (fonte e osciloscópio FICTÍCIOS que tocam a hipótese pedida):

    env\\Scripts\\python.exe scripts\\diag_marcadores_trace.py --simulado --probe 500 --vrms 127 --simular "atraso_de_passos:d=1,t_inicio_s=0.1"
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "logica"))

from ametek_orm import AmetekMX30  # noqa: E402
from politica_traces import LIMITE_ESCRITAS_TRACE_CONEXAO  # noqa: E402
import modelo_lista_fonte as modelo  # noqa: E402

CONFIRMACAO = "ENERGIZAR-MARCADORES"
PORTA = "COM10"
BAUD = 115_200
RANGE_RMS = 300.0
MAX_RMS = 300.0
MAX_PICO_V = round(RANGE_RMS * math.sqrt(2.0) * 0.98, 1)  # 415,8
LIMITE_CORRENTE_A = 0.5
ATRASO_PROTECAO_S = 0.1
TENSAO_MAX_V = 270.0
FS_HZ = 30_000.0
PONTOS = 6_000
MARGEM_ANTES_S = 0.020   # igual a ExperimentoBase.MARGEM_ANTES_S
MARGEM_DEPOIS_S = 0.050  # igual a ExperimentoBase.MARGEM_DEPOIS_S
PONTOS_REGISTRO = PONTOS + int(round((MARGEM_ANTES_S + MARGEM_DEPOIS_S) * FS_HZ))  # 8100
IDN_OSC = "DSOX4034A"
RECURSO_OSC = "USB0::0x0957::0x17A4::MY59240844::0::INSTR"
LARGURA_MARCADOR = 24      # amostras (lombada de cosseno elevado)
LARGURA_EVENTO = 4         # amostras (impulso retangular estreito)
BORDA_MARCADOR = 40        # amostras livres no começo e no fim do ciclo
ESCRITAS_TRACE_MAX = LIMITE_ESCRITAS_TRACE_CONEXAO
SEMENTE_PERMUTACAO = 20261013
VARIANTES = ("marcadores", "fronteira", "meio_ciclo")

logger = logging.getLogger("diag_marcadores")


# ---------------------------------------------------------------------------
# Formas planejadas (puras)
# ---------------------------------------------------------------------------
def senoide_pu(f0_hz: float, pontos: int = PONTOS) -> np.ndarray:
    return np.sin(2.0 * np.pi * f0_hz * np.arange(pontos, dtype=np.float64) / FS_HZ)


def forma_marcadores(f0_hz: float, amp_max_pu: float, *, amp_min_pu: float = 0.08) -> Tuple[np.ndarray, List[dict]]:
    """Senoide + um marcador por ciclo, com (posição, amplitude) únicas por
    ciclo: amplitude cresce com o ciclo, posição segue uma permutação fixa."""
    n = int(round(FS_HZ / f0_hz))
    ciclos = PONTOS // n
    forma = senoide_pu(f0_hz)
    permutacao = np.random.default_rng(SEMENTE_PERMUTACAO).permutation(ciclos)
    livre = n - 2 * BORDA_MARCADOR - LARGURA_MARCADOR
    passo = livre // max(ciclos - 1, 1)
    marcadores = []
    for k in range(ciclos):
        amp = amp_min_pu + (amp_max_pu - amp_min_pu) * k / max(ciclos - 1, 1)
        pos = BORDA_MARCADOR + LARGURA_MARCADOR // 2 + int(permutacao[k]) * passo
        inicio = k * n + pos - LARGURA_MARCADOR // 2
        x = np.arange(LARGURA_MARCADOR)
        forma[inicio : inicio + LARGURA_MARCADOR] += amp * 0.5 * (1.0 - np.cos(2.0 * np.pi * x / LARGURA_MARCADOR))
        marcadores.append({"k": k, "pos": int(pos), "amp": float(amp), "abs": int(k * n + pos)})
    return forma, marcadores


def forma_evento(f0_hz: float, ciclo: int, onde: str, amp_pu: float) -> Tuple[np.ndarray, List[dict]]:
    """Senoide + um impulso estreito no ponto 0 (``fronteira``) ou a meio ciclo
    (``meio_ciclo``) do ciclo ``ciclo``."""
    if onde not in {"fronteira", "meio_ciclo"}:
        raise ValueError("onde deve ser 'fronteira' ou 'meio_ciclo'")
    n = int(round(FS_HZ / f0_hz))
    ciclos = PONTOS // n
    if not 0 <= ciclo < ciclos:
        raise ValueError(f"ciclo do evento {ciclo} fora de 0..{ciclos - 1}")
    forma = senoide_pu(f0_hz)
    pos = 0 if onde == "fronteira" else n // 2
    inicio = ciclo * n + pos
    forma[inicio : inicio + LARGURA_EVENTO] += amp_pu
    return forma, [{"k": ciclo, "pos": int(pos + (LARGURA_EVENTO - 1) // 2), "amp": float(amp_pu), "abs": int(inicio + (LARGURA_EVENTO - 1) // 2)}]


def amplitude_maxima_pu(vrms: float, pedida: float) -> float:
    """Maior amplitude de marcador/evento que mantém o pico (1 + amp) em até 90 %
    de ``MAX_PICO_V``; recusa se sobrar menos de 0,15 pu."""
    teto = 0.90 * MAX_PICO_V / (vrms * math.sqrt(2.0)) - 1.0
    amp = min(pedida, teto)
    if amp < 0.15:
        raise SystemExit(
            f"--vrms {vrms:g} deixa só {teto:.2f} pu de folga até {MAX_PICO_V} Vp; os marcadores precisam de >= 0,15 pu"
        )
    return amp


def ciclo_do_instante(instante_ms: float, f0_hz: float) -> int:
    """Primeiro ciclo que começa em ou depois de ``instante_ms`` (a 50 Hz,
    80 ms é o ponto 0 do ciclo 4; a 60 Hz o ciclo 5 começa em 83,3 ms)."""
    return int(math.ceil(instante_ms / 1000.0 * f0_hz - 1e-9))


def planejar(frequencias: Sequence[float], variantes: Sequence[str], instantes_evento_ms: Sequence[float], vrms: float, amp_pu: float) -> List[dict]:
    """Lista de capturas planejadas, já com a forma e o marcador/evento
    programados. Valida pico reconstruído e rms de passo contra os limites."""
    plano: List[dict] = []
    for f0 in frequencias:
        for variante in variantes:
            if variante == "marcadores":
                forma, marcas = forma_marcadores(f0, amp_pu)
                plano.append({"f0_hz": f0, "variante": variante, "rotulo": f"marcadores@{f0:g}Hz", "forma": forma, "marcadores": marcas})
            else:
                for instante_ms in instantes_evento_ms:
                    ciclo = ciclo_do_instante(instante_ms, f0)
                    forma, marcas = forma_evento(f0, ciclo, variante, amp_pu)
                    plano.append({"f0_hz": f0, "variante": variante, "ciclo_evento": ciclo,
                                  "rotulo": f"{variante}@{f0:g}Hz/ciclo{ciclo}", "forma": forma, "marcadores": marcas})
    for item in plano:
        prog = AmetekMX30.montar_programacao(item["forma"], base_voltage_rms=vrms, frequency_hz=item["f0_hz"])
        if prog.pico_reconstruido_v > MAX_PICO_V:
            raise SystemExit(f"{item['rotulo']}: pico reconstruído {prog.pico_reconstruido_v:.1f} V > {MAX_PICO_V} V; recuso")
        if float(np.max(prog.list_voltages_rms)) > MAX_RMS:
            raise SystemExit(f"{item['rotulo']}: rms de passo acima de {MAX_RMS} V; recuso")
        item["pico_reconstruido_v"] = prog.pico_reconstruido_v
        item["escritas_trace"] = prog.ciclos
    return plano


# ---------------------------------------------------------------------------
# Leitura dos marcadores na medida (pura)
# ---------------------------------------------------------------------------
def residuo_sem_fundamental(medida_pu: np.ndarray, n: int, limiar_pu: float) -> np.ndarray:
    """``medida - (a sin + b cos + c)`` ajustado ciclo a ciclo, duas vezes (a
    segunda sem as amostras que a primeira já marcou como marcador/evento)."""
    ciclos = len(medida_pu) // n
    saida = np.zeros(ciclos * n, dtype=np.float64)
    x = np.arange(n, dtype=np.float64)
    base = np.column_stack([np.sin(2 * np.pi * x / n), np.cos(2 * np.pi * x / n), np.ones(n)])
    for j in range(ciclos):
        y = np.asarray(medida_pu[j * n : (j + 1) * n], dtype=np.float64)
        mascara = np.ones(n, dtype=bool)
        for _ in range(2):
            coef, *_ = np.linalg.lstsq(base[mascara], y[mascara], rcond=None)
            res = y - base @ coef
            mascara = np.abs(res) < 0.5 * limiar_pu
            if mascara.sum() < n // 2:
                break
        saida[j * n : (j + 1) * n] = res
    return saida


def achar_picos(residuo: np.ndarray, limiar_pu: float, separacao: int, suavizar: int = 3) -> List[Tuple[int, float]]:
    """Picos positivos do resíduo acima do limiar, separados de ao menos
    ``separacao`` amostras: lista de (amostra, amplitude)."""
    if suavizar > 1:
        kernel = np.ones(suavizar) / suavizar
        s = np.convolve(residuo, kernel, mode="same")
    else:
        s = residuo
    candidatos = np.nonzero(s > limiar_pu)[0]
    picos: List[Tuple[int, float]] = []
    usados = np.zeros(len(s), dtype=bool)
    for i in candidatos[np.argsort(-s[candidatos])]:
        if usados[max(0, i - separacao) : i + separacao + 1].any():
            continue
        picos.append((int(i), float(s[i])))
        usados[max(0, i - separacao) : i + separacao + 1] = True
    picos.sort()
    return picos


def _dist_circular(a: int, b: int, n: int) -> int:
    d = (a - b) % n
    return min(d, n - d)


def identificar(
    picos: Sequence[Tuple[int, float]], marcadores: Sequence[dict], n: int, *, tol_pos: int = 12, rel_amp: float = 0.25,
    score_max: float = 4.0,
) -> List[dict]:
    """Para cada pico observado, o marcador programado mais parecido em
    (posição no ciclo, amplitude). Devolve, por pico: ciclo medido ``j``,
    posição ``pos``, amplitude, ``k`` identificado (ou None = espúrio),
    ``troca_ciclos`` = j - k e ``atraso_amostras`` (resto, assinado, dentro
    de ±n/2)."""
    saida = []
    for amostra, amp in picos:
        j, pos = divmod(amostra, n)
        melhor, melhor_score = None, None
        for m in marcadores:
            dpos = _dist_circular(pos, m["pos"], n)
            damp = amp - m["amp"]
            score = (dpos / tol_pos) ** 2 + (damp / (rel_amp * m["amp"] + 0.02)) ** 2
            if melhor_score is None or score < melhor_score:
                melhor, melhor_score = m, score
        registro = {"amostra": int(amostra), "instante_ms": 1000.0 * amostra / FS_HZ, "ciclo_medido": int(j), "pos": int(pos), "amp": float(amp)}
        if melhor is not None and melhor_score <= score_max:
            esperado = melhor["abs"]
            troca = int(round((amostra - esperado) / n))
            resto = amostra - esperado - troca * n
            registro.update({"k": int(melhor["k"]), "troca_ciclos": troca, "atraso_amostras": int(resto), "score": float(melhor_score)})
        else:
            registro.update({"k": None, "troca_ciclos": None, "atraso_amostras": None, "score": melhor_score})
        saida.append(registro)
    return saida


def resumir(identificados: Sequence[dict], marcadores: Sequence[dict], n: int, ciclos: int) -> dict:
    """Resumo por captura: a troca de passo começa em qual ciclo/instante, o
    atraso típico, espúrios (sem marcador) e marcadores que não saíram."""
    casados = [r for r in identificados if r["k"] is not None]
    espurios = [r for r in identificados if r["k"] is None]
    ausentes = [m["k"] for m in marcadores if m["k"] not in {r["k"] for r in casados}]
    trocados = [r for r in casados if r["troca_ciclos"] != 0]
    copias = []
    vistos: Dict[int, dict] = {}
    for r in casados:
        if r["k"] in vistos:
            copias.append({"k": r["k"], "instantes_ms": [vistos[r["k"]]["instante_ms"], r["instante_ms"]]})
        else:
            vistos[r["k"]] = r
    primeira = min(trocados, key=lambda r: r["ciclo_medido"]) if trocados else None
    atrasos = [r["atraso_amostras"] for r in casados]
    return {
        "marcadores_programados": len(marcadores), "picos_observados": len(identificados),
        "identificados": len(casados), "ausentes": ausentes, "espurios": espurios, "copias": copias,
        "troca_de_passo": ({
            "primeiro_ciclo_medido": primeira["ciclo_medido"], "k_tocado": primeira["k"],
            "deslocamento_ciclos": primeira["troca_ciclos"],
            "instante_ms": 1000.0 * primeira["ciclo_medido"] * n / FS_HZ,
            "deslocamentos_vistos": sorted({r["troca_ciclos"] for r in casados}),
        } if primeira else None),
        "atraso_amostras_mediana": (float(np.median(atrasos)) if atrasos else None),
        "atraso_amostras_min_max": ([int(min(atrasos)), int(max(atrasos))] if atrasos else None),
    }


def analisar_medida(medida_pu: np.ndarray, f0_hz: float, marcadores: Sequence[dict]) -> dict:
    n = int(round(FS_HZ / f0_hz))
    ciclos = len(medida_pu) // n
    menor = min(m["amp"] for m in marcadores)
    limiar = 0.5 * menor
    residuo = residuo_sem_fundamental(medida_pu, n, limiar)
    picos = achar_picos(residuo, limiar, separacao=max(LARGURA_MARCADOR, 2 * LARGURA_EVENTO))
    ident = identificar(picos, marcadores, n)
    return {"limiar_pu": limiar, "observados": ident, "resumo": resumir(ident, marcadores, n, ciclos)}


# ---------------------------------------------------------------------------
# Modo simulado: fonte e osciloscópio FICTÍCIOS que tocam uma hipótese
# ---------------------------------------------------------------------------
def parsear_simulacao(texto: str) -> Tuple[str, dict]:
    """``"atraso_de_passos:d=1,t_inicio_s=0.1"`` -> (mecanismo, parâmetros)."""
    nome, _, resto = texto.partition(":")
    parametros: dict = {}
    for par in filter(None, resto.split(",")):
        chave, _, valor = par.partition("=")
        try:
            parametros[chave.strip()] = int(valor)
        except ValueError:
            try:
                parametros[chave.strip()] = float(valor)
            except ValueError:
                parametros[chave.strip()] = valor.strip()
    if nome not in modelo.MECANISMOS:
        raise SystemExit(f"--simular: mecanismo {nome!r} desconhecido; válidos: {sorted(modelo.MECANISMOS)}")
    return nome, parametros


class _OscFicticio:
    """Keysight FICTÍCIO: devolve, no registro de 8100 amostras, o que a
    hipótese ``mecanismo`` prevê para a última ``program_capture`` da fonte."""

    idn = "SIMULADO,DSO-X 4034A,FICTICIO,0"

    def __init__(self, fonte: AmetekMX30, vrms: float, mecanismo: str, parametros: dict, atraso_amostras: int = 0):
        self.fonte, self.vrms = fonte, vrms
        self.mecanismo, self.parametros, self.atraso = mecanismo, parametros, atraso_amostras
        self.rng = np.random.default_rng(3)
        self.ultimo_indice_trigger = int(round(MARGEM_ANTES_S * FS_HZ))

    def __getattr__(self, nome):
        return lambda *a, **k: None

    def verify_identity(self, *_a, **_k):
        return self.idn

    def set_vertical_scale(self, _canal, pico):
        return pico / 3.0

    def get_waveform(self, _canal, *, expected_points=PONTOS_REGISTRO):
        prog = self.fonte.ultima_programacao
        prevista = modelo.prever_forma(prog, self.mecanismo, **self.parametros)
        if self.atraso:
            prevista = np.roll(prevista, self.atraso)
        volts = np.zeros(expected_points, dtype=np.float64)
        ini = self.ultimo_indice_trigger
        n = min(prevista.size, expected_points - ini)
        volts[ini : ini + n] = prevista[:n] * self.vrms * math.sqrt(2.0)
        volts += self.rng.normal(0.0, 0.2, expected_points)
        return np.arange(expected_points) / FS_HZ, volts


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
def capturar(fonte: AmetekMX30, osc, item: dict, vrms: float) -> np.ndarray:
    """Uma captura pela MESMA sequência de ``mestre._capturar_real``; devolve a
    janela de 6000 amostras (pu) alinhada ao trigger."""
    forma = item["forma"]
    fonte.program_capture(forma, base_voltage_rms=vrms, frequency_hz=item["f0_hz"], dc_offset_pu=0.0)
    pico_v = max(float(np.max(np.abs(forma))) * vrms * math.sqrt(2.0), float(fonte.last_programmed_peak_v))
    osc.set_vertical_scale(1, max(pico_v * 1.25, vrms * 0.1))
    osc.arm()
    osc.wait_for_armed()
    fonte.arm_transient()
    fonte.trigger()
    osc.wait_for_trigger_complete(timeout_s=5.0)
    fonte.wait_transient_complete(timeout_s=5.0)
    _t, volts = osc.get_waveform(1, expected_points=PONTOS_REGISTRO)
    indice = getattr(osc, "ultimo_indice_trigger", None)
    inicio = int(indice) if isinstance(indice, (int, float)) else int(round(MARGEM_ANTES_S * FS_HZ))
    inicio = max(0, min(inicio, len(volts) - PONTOS))
    item["indice_trigger"] = inicio
    return np.asarray(volts[inicio : inicio + PONTOS], dtype=np.float64) / (vrms * math.sqrt(2.0))


def montar_markdown(resultados: List[dict]) -> str:
    linhas = ["# Marcadores por ciclo na TRACe", ""]
    linhas.append("| captura | picos | casados/programados | ausentes | espúrios | cópias | troca de passo (1.º ciclo, instante, deslocamento) | atraso mediano (amostras) | melhor hipótese |")
    linhas.append("|---|---|---|---|---|---|---|---|---|")
    for r in resultados:
        s, t = r["resumo"], r["resumo"]["troca_de_passo"]
        troca = (f"ciclo {t['primeiro_ciclo_medido']}, {t['instante_ms']:.1f} ms, {t['deslocamento_ciclos']:+d}" if t else "nenhuma")
        melhor = r["hipoteses"][0] if r["hipoteses"] else {"nome": "n/d", "rms_residuo_pu": float("nan")}
        linhas.append(
            f"| {r['rotulo']} | {s['picos_observados']} | {s['identificados']}/{s['marcadores_programados']} "
            f"| {s['ausentes'] or '-'} | {len(s['espurios'])} | {len(s['copias'])} | {troca} "
            f"| {s['atraso_amostras_mediana'] if s['atraso_amostras_mediana'] is not None else '-'} "
            f"| {melhor['nome']} ({melhor['rms_residuo_pu']:.4f}) |"
        )
    for r in resultados:
        linhas += ["", f"## {r['rotulo']}", "", "| ciclo medido | instante (ms) | posição | amplitude (pu) | k tocado | deslocamento (ciclos) | atraso (amostras) |", "|---|---|---|---|---|---|---|"]
        for o in r["observados"]:
            linhas.append(
                f"| {o['ciclo_medido']} | {o['instante_ms']:.2f} | {o['pos']} | {o['amp']:.3f} "
                f"| {o['k'] if o['k'] is not None else 'ESPÚRIO'} | {o['troca_ciclos'] if o['troca_ciclos'] is not None else '-'} "
                f"| {o['atraso_amostras'] if o['atraso_amostras'] is not None else '-'} |"
            )
        linhas += ["", "Hipóteses (rms do resíduo, pu): " + "; ".join(f"{h['nome']}={h['rms_residuo_pu']:.4f}" for h in r["hipoteses"][:5])]
    return "\n".join(linhas) + "\n"


def validar_args(a) -> None:
    if not 0 < a.vrms <= TENSAO_MAX_V:
        raise SystemExit(f"--vrms deve estar em (0, {TENSAO_MAX_V:g}] Vrms (teto da bancada)")
    if a.probe is None or a.probe <= 0:
        raise SystemExit("Informe --probe (ou VOLTAGE_PROBE_ATTENUATION) com o fator ESCRITO na probe instalada; não há valor padrão.")
    for f in a.frequencias:
        n = FS_HZ / f
        if abs(n - round(n)) > 1e-6 or PONTOS % round(n) != 0:
            raise SystemExit(f"{f:g} Hz não fecha ciclos inteiros em {PONTOS} amostras a {FS_HZ:g} Sa/s")
    for v in a.variantes:
        if v not in VARIANTES:
            raise SystemExit(f"variante {v!r} desconhecida; válidas: {', '.join(VARIANTES)}")
    if not 0.15 <= a.amp_pu <= 0.6:
        raise SystemExit("--amp-pu deve estar em 0,15..0,6 pu")
    if not a.simulado and os.environ.get("BENCH_MODE", "").strip() not in {"1", "true", "TRUE", "yes", "YES"}:
        raise SystemExit("Defina BENCH_MODE=1 para usar a bancada real (ou use --simulado).")


def main(argv=None, entrada=input) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vrms", type=float, default=float(os.environ.get("BASE_VOLTAGE_RMS", "127")))
    ap.add_argument("--probe", type=float, default=float(os.environ["VOLTAGE_PROBE_ATTENUATION"]) if os.environ.get("VOLTAGE_PROBE_ATTENUATION") else None)
    ap.add_argument("--frequencias", type=lambda s: [float(x) for x in s.split(",")], default=[50.0, 60.0])
    ap.add_argument("--variantes", type=lambda s: [x.strip() for x in s.split(",")], default=list(VARIANTES))
    ap.add_argument("--instantes-evento-ms", type=lambda s: [float(x) for x in s.split(",")], default=[40.0, 80.0],
                    help="instantes aproximados dos eventos; cada um vira o ponto 0 (fronteira) ou o meio (meio_ciclo) do primeiro ciclo que começa nele ou depois")
    ap.add_argument("--amp-pu", type=float, default=0.45, help="amplitude máxima do marcador / do impulso (pu); reduzida para caber no pico")
    ap.add_argument("--simulado", action="store_true")
    ap.add_argument("--simular", default="ideal", help='SÓ com --simulado: hipótese que a fonte FICTÍCIA toca, "mecanismo:chave=valor,..."')
    ap.add_argument("--atraso-simulado", type=int, default=0, help="FICTÍCIO: atraso global (amostras), só com --simulado")
    ap.add_argument("--saida", type=Path, default=RAIZ / "logs")
    args = ap.parse_args(argv)
    validar_args(args)
    amp = amplitude_maxima_pu(args.vrms, args.amp_pu)
    plano = planejar(args.frequencias, args.variantes, args.instantes_evento_ms, args.vrms, amp)
    escritas = sum(item["escritas_trace"] for item in plano)
    if escritas > ESCRITAS_TRACE_MAX:
        raise SystemExit(f"{escritas} gravações de TRACe planejadas (> {ESCRITAS_TRACE_MAX}); divida em duas rodadas")

    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    args.saida.mkdir(parents=True, exist_ok=True)
    base = args.saida / f"diag_marcadores_trace-{ts}"
    raiz_log = logging.getLogger()
    nivel_anterior = raiz_log.level
    formato = logging.Formatter("%(message)s")
    handlers_proprios = [logging.StreamHandler(sys.stdout), logging.FileHandler(f"{base}.log", encoding="utf-8")]
    for h in handlers_proprios:
        h.setFormatter(formato)
        raiz_log.addHandler(h)
    raiz_log.setLevel(logging.INFO)
    scpi = logging.getLogger("AmetekORM.scpi")
    nivel_scpi, propagar_scpi = scpi.level, scpi.propagate
    scpi.setLevel(logging.DEBUG)
    scpi.propagate = False
    h_scpi = logging.FileHandler(f"{base}-scpi.log", encoding="utf-8")
    h_scpi.setFormatter(logging.Formatter("[%(asctime)s.%(msecs)03d] %(message)s", datefmt="%H:%M:%S"))
    scpi.addHandler(h_scpi)

    fonte = AmetekMX30(
        PORTA, baudrate=BAUD, timeout_s=5.0, query_eot=True, expected_model="MX30",
        max_voltage_rms=MAX_RMS, max_peak_v=MAX_PICO_V, max_current_a=LIMITE_CORRENTE_A,
        simulated=args.simulado,
    )
    osc = None
    try:
        if args.simulado:
            mecanismo, parametros = parsear_simulacao(args.simular)
            osc = _OscFicticio(fonte, args.vrms, mecanismo, parametros, args.atraso_simulado)
            # A fonte simulada do ORM não responde ao readback de arm_transient
            # (TRIGger:SOURce? etc.): no modo FICTÍCIO o disparo é um no-op.
            for nome in ("arm_transient", "trigger", "wait_transient_complete"):
                setattr(fonte, nome, lambda *a, **k: None)
        else:
            from pymeasure.adapters import VISAAdapter
            from oscilloscope_orm import KeysightDSOX4034A
            osc = KeysightDSOX4034A(VISAAdapter(RECURSO_OSC, timeout=15_000))
            logger.info("Keysight: %s", osc.verify_identity(IDN_OSC))
            osc.initialize_safe()
            try:  # Ctrl+C no Windows com as duas sessões VISA abertas (ver mestre.py)
                from mestre import garantir_ctrl_c_no_windows
                garantir_ctrl_c_no_windows()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Ctrl+C pode não interromper este script (%s). Em emergência: botão OUTPUT no painel.", exc)

        fonte.configure_safe_baseline(
            voltage_range_rms=RANGE_RMS, voltage_high_vp=MAX_PICO_V, current_limit_a=LIMITE_CORRENTE_A,
            protection_delay_s=ATRASO_PROTECAO_S, frequency_hz=args.frequencias[0],
        )
        pico_planejado = max(item["pico_reconstruido_v"] for item in plano)
        osc.configure_channel(1, scale=pico_planejado * 1.25 / 3.0, probe_attenuation=args.probe, coupling="DC", units="VOLT")
        osc.disable_channel(2)
        osc.configure_acquisition(sample_rate_hz=FS_HZ, points=PONTOS_REGISTRO, duration_s=PONTOS_REGISTRO / FS_HZ, pre_trigger_s=MARGEM_ANTES_S)
        osc.setup_external_trigger(level_v=1.5, probe_attenuation=1.0, range_v=8.0)
        logger.info("Fonte: %s | probe %gx | %g Vrms | %d capturas, %d gravações de TRACe, pico máximo %.0f Vp (limite %.1f Vp)",
                    fonte.idn, args.probe, args.vrms, len(plano), escritas, pico_planejado, MAX_PICO_V)

        print(f"\nVai LIGAR a saída em {args.vrms:g} Vrms, sem carga, em {len(plano)} capturas "
              f"({', '.join(f'{f:g}' for f in args.frequencias)} Hz).")
        if not args.simulado and entrada(f"Digite {CONFIRMACAO} para continuar: ") != CONFIRMACAO:
            print("Não confirmado; a saída continua OFF.")
            return 2

        fonte.authorize_output(True)
        fonte.energize_baseline()
        resultados = []
        for item in plano:
            logger.info("--- %s ---", item["rotulo"])
            medida = capturar(fonte, osc, item, args.vrms)
            analise = analisar_medida(medida, item["f0_hz"], item["marcadores"])
            prog = fonte.ultima_programacao
            hipoteses = modelo.confrontar(prog, medida) if prog is not None else []
            resultados.append({
                "rotulo": item["rotulo"], "f0_hz": item["f0_hz"], "variante": item["variante"],
                "ciclo_evento": item.get("ciclo_evento"), "indice_trigger": item["indice_trigger"],
                "marcadores_programados": item["marcadores"], "pico_reconstruido_v": item["pico_reconstruido_v"],
                **analise, "hipoteses": hipoteses,
            })
            s = analise["resumo"]
            logger.info("%s: %d/%d identificados, %d espúrio(s), troca=%s", item["rotulo"], s["identificados"],
                        s["marcadores_programados"], len(s["espurios"]), s["troca_de_passo"])
        texto = montar_markdown(resultados)
        print("\n" + texto)
        with open(f"{base}.json", "w", encoding="utf-8") as fh:
            json.dump({"argumentos": {k: str(v) for k, v in vars(args).items()}, "idn_fonte": fonte.idn,
                       "simulado": args.simulado, "capturas": resultados}, fh, indent=1, ensure_ascii=False, default=float)
        with open(f"{base}.md", "w", encoding="utf-8") as fh:
            fh.write(texto)
        print(f"Resultados: {base}.json | .md | .log | -scpi.log")
        return 0
    finally:
        try:
            fonte.safe_shutdown()
            if not args.simulado:
                print("OUTPut:STATe? ->", fonte.query("OUTPut:STATe?").strip(), "(0 = desligada; CONFIRA NO PAINEL)")
        finally:
            fonte.disconnect()
            if osc is not None and not args.simulado:
                osc.close()
            # Devolve o logging ao estado de antes (importa quando chamado de testes).
            for h in handlers_proprios:
                raiz_log.removeHandler(h)
                h.close()
            raiz_log.setLevel(nivel_anterior)
            scpi.removeHandler(h_scpi)
            h_scpi.close()
            scpi.setLevel(nivel_scpi)
            scpi.propagate = propagar_scpi


if __name__ == "__main__":
    sys.exit(main())
