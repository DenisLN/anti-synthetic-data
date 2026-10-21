"""Modelo preditivo PROVISÓRIO do que a MX30 emite ao tocar um LIST de TRACEs.

Contexto (CHANGELOG/v1.15.md, "Diagnóstico da cópia do evento em 100 ms"):
nas capturas de 07/10 o início do evento aparece repetido ou deslocado num
instante fixo (100,0 ms) a 50 e a 60 Hz. A montagem da TRACE
(``AmetekMX30.montar_programacao``) está descartada como causa; o mecanismo
dentro da fonte é DESCONHECIDO. Este módulo guarda as hipóteses candidatas
como funções puras e parametrizadas, para serem confrontadas com o que
``scripts/diag_marcadores_trace.py`` medir na bancada.

NADA aqui é fato sobre o equipamento: cada mecanismo é uma hipótese
(NÃO VERIFICADO até a bancada). ``mecanismo="ideal"`` é o contrato de
``ProgramacaoCaptura.programada_pu()`` (cada passo do LIST toca a sua TRACE
escalada ao seu rms) e reproduz essa função exatamente.

Função pura: sem SCPI, sem estado, sem instrumento.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

FS_HZ = 30_000.0

# Nome -> (mecanismo, parâmetros). Escolhidas dos sintomas de 07/10:
# 08/50 Hz e 09/50 Hz (evento do ciclo 4 sai no ciclo 5), 09/60 Hz (evento a
# meio ciclo em 80 ms e cópia menor em 100 ms). Os valores numéricos são
# chutes de partida, não medidas.
HIPOTESES_CANDIDATAS: Dict[str, Tuple[str, dict]] = {
    "ideal": ("ideal", {}),
    "passo_atrasado_1_a_partir_de_80ms": ("atraso_de_passos", {"d": 1, "t_inicio_s": 0.080}),
    "passo_atrasado_1_a_partir_de_100ms": ("atraso_de_passos", {"d": 1, "t_inicio_s": 0.100}),
    "passo_atrasado_1_so_tensao_propria_100ms": (
        "atraso_de_passos", {"d": 1, "t_inicio_s": 0.100, "tensao": "da_forma"},
    ),
    "copia_do_evento_em_100ms": ("copia_no_instante", {"t_s": 0.100, "ganho": 1.0, "modo": "somar"}),
    "copia_pequena_em_100ms": ("copia_no_instante", {"t_s": 0.100, "ganho": 0.15, "modo": "somar"}),
    "inicio_do_passo_com_forma_anterior_3_amostras": (
        "transicao_forma_anterior", {"amostras": 3},
    ),
    "inicio_do_passo_com_forma_anterior_30_amostras": (
        "transicao_forma_anterior", {"amostras": 30},
    ),
    "resto_deslocado_20ms_a_partir_de_100ms": (
        "deslocamento_no_tempo", {"t_inicio_s": 0.100, "atraso_s": 0.020},
    ),
}


def _formas_unitarias(programacao) -> np.ndarray:
    """(ciclos, pontos_por_ciclo): a forma que cada TRACE toca, na grade de
    30 kSa/s, com rms 1 (a mesma inversa de ``_resample_cycle`` que
    ``programada_pu`` usa), SEM o offset DC. Ciclo nulo -> zeros."""
    n = programacao.pontos_por_ciclo
    pontos = programacao.traces.shape[1]
    posicao = np.arange(n, dtype=np.float64) * (pontos / n)
    grade = np.arange(pontos, dtype=np.float64)
    formas = []
    for trace in programacao.traces:
        rms_trace = float(np.sqrt(np.mean(np.square(trace))))
        if rms_trace < 1e-12:
            formas.append(np.zeros(n, dtype=np.float64))
        else:
            formas.append(np.interp(posicao, grade, trace, period=pontos) / rms_trace)
    return np.vstack(formas)


def _montar(programacao, formas: np.ndarray, indice_forma: Sequence[int], indice_tensao: Sequence[int]) -> np.ndarray:
    pico_nominal_v = programacao.base_voltage_rms * math.sqrt(2.0)
    ciclos = [
        formas[int(f)] * float(programacao.list_voltages_rms[int(v)]) / pico_nominal_v
        for f, v in zip(indice_forma, indice_tensao)
    ]
    return np.concatenate(ciclos)


def _inicio_s(programacao, j: int) -> float:
    return j * programacao.pontos_por_ciclo / FS_HZ


def _ideal(programacao, formas: np.ndarray) -> np.ndarray:
    idx = list(range(programacao.ciclos))
    return _montar(programacao, formas, idx, idx)


def _atraso_de_passos(programacao, formas, *, d: int = 1, t_inicio_s: float = 0.100, tensao: str = "propria") -> np.ndarray:
    """Hipótese: a partir de ``t_inicio_s`` a fonte toca no passo j a forma do
    passo j-d (clamp em 0). ``tensao="propria"``: o rms de LIST:VOLTage é o do
    passo j (a forma antiga com a tensão nova); ``"da_forma"``: o rms do passo
    de onde veio a forma (o passo todo atrasado)."""
    if tensao not in {"propria", "da_forma"}:
        raise ValueError("tensao deve ser 'propria' ou 'da_forma'")
    idx_forma, idx_tensao = [], []
    for j in range(programacao.ciclos):
        origem = max(j - int(d), 0) if _inicio_s(programacao, j) >= t_inicio_s - 1e-12 else j
        idx_forma.append(origem)
        idx_tensao.append(j if tensao == "propria" else origem)
    return _montar(programacao, formas, idx_forma, idx_tensao)


def _transicao_forma_anterior(programacao, formas, *, amostras: int = 3, t_inicio_s: float = 0.0) -> np.ndarray:
    """Hipótese: nas primeiras ``amostras`` de cada passo (a partir de
    ``t_inicio_s``) a fonte ainda toca a forma do passo anterior, com a tensão
    do passo novo (troca de forma atrasada em relação à de tensão)."""
    base = _ideal(programacao, formas)
    n = programacao.pontos_por_ciclo
    pico_nominal_v = programacao.base_voltage_rms * math.sqrt(2.0)
    m = max(0, min(int(amostras), n))
    for j in range(1, programacao.ciclos):
        if _inicio_s(programacao, j) < t_inicio_s - 1e-12 or m == 0:
            continue
        antiga = formas[j - 1][:m] * float(programacao.list_voltages_rms[j]) / pico_nominal_v
        base[j * n : j * n + m] = antiga
    return base


def _copia_no_instante(
    programacao, formas, *, t_s: float = 0.100, ciclo_origem: Optional[int] = None,
    inicio_na_origem: int = 0, n_amostras: Optional[int] = None, ganho: float = 1.0, modo: str = "somar",
) -> np.ndarray:
    """Hipótese: num instante FIXO ``t_s`` (não ligado a ponto do ciclo) a
    fonte acrescenta ('somar') ou impõe ('substituir') um trecho de
    ``n_amostras`` do passo ``ciclo_origem`` (padrão: o de maior pico, isto é,
    o que carrega o evento), começando em ``inicio_na_origem`` dentro do ciclo,
    multiplicado por ``ganho``."""
    if modo not in {"somar", "substituir"}:
        raise ValueError("modo deve ser 'somar' ou 'substituir'")
    saida = _ideal(programacao, formas)
    n = programacao.pontos_por_ciclo
    ideal_ciclos = saida.reshape(programacao.ciclos, n)
    if ciclo_origem is None:
        ciclo_origem = int(np.argmax(np.max(np.abs(ideal_ciclos), axis=1)))
    comprimento = n if n_amostras is None else int(n_amostras)
    ini = int(inicio_na_origem)
    trecho = ideal_ciclos[int(ciclo_origem)][ini : ini + comprimento] * float(ganho)
    destino = int(round(t_s * FS_HZ))
    fim = min(destino + trecho.size, saida.size)
    trecho = trecho[: max(0, fim - destino)]
    if modo == "somar":
        saida[destino:fim] += trecho
    else:
        saida[destino:fim] = trecho
    return saida


def _deslocamento_no_tempo(programacao, formas, *, t_inicio_s: float = 0.100, atraso_s: float = 0.020) -> np.ndarray:
    """Hipótese: a partir de ``t_inicio_s`` o que a fonte emite é a forma ideal
    deslocada de ``atraso_s`` (negativo adianta); antes, o ideal."""
    ideal = _ideal(programacao, formas)
    saida = ideal.copy()
    delta = int(round(atraso_s * FS_HZ))
    inicio = int(round(t_inicio_s * FS_HZ))
    for i in range(max(inicio, 0), ideal.size):
        origem = i - delta
        saida[i] = ideal[origem] if 0 <= origem < ideal.size else 0.0
    return saida


MECANISMOS: Dict[str, Callable[..., np.ndarray]] = {
    "ideal": lambda prog, formas: _ideal(prog, formas),
    "atraso_de_passos": _atraso_de_passos,
    "transicao_forma_anterior": _transicao_forma_anterior,
    "copia_no_instante": _copia_no_instante,
    "deslocamento_no_tempo": _deslocamento_no_tempo,
}


def prever_forma(programacao, mecanismo: str = "ideal", **parametros) -> np.ndarray:
    """Forma (pu do pico nominal, grade de 30 kSa/s, ``ciclos * pontos_por_ciclo``
    amostras) que a fonte emitiria para ``programacao`` (uma
    ``ProgramacaoCaptura``) SE o ``mecanismo`` (hipótese) fosse verdadeiro.
    O offset DC da programação é somado no fim, como em ``programada_pu``:
    o global, ou, no braço C da P-09 (``dc_offset_por_passo_pu``), o de cada
    passo. Levanta ``ValueError`` para mecanismo ou parâmetro desconhecido."""
    if mecanismo not in MECANISMOS:
        raise ValueError(f"mecanismo desconhecido {mecanismo!r}; válidos: {sorted(MECANISMOS)}")
    formas = _formas_unitarias(programacao)
    try:
        saida = MECANISMOS[mecanismo](programacao, formas, **parametros)
    except TypeError as exc:
        raise ValueError(f"parâmetros inválidos para {mecanismo!r}: {exc}") from exc
    if getattr(programacao, "dc_offset_por_passo_pu", None) is not None:
        offsets = programacao.offset_por_amostra_pu()
        n = min(saida.size, offsets.size)
        saida = saida.copy()
        saida[:n] = saida[:n] + offsets[:n]
        if saida.size > n:
            saida[n:] = saida[n:] + float(programacao.dc_offset_pu)
        return saida
    return saida + float(programacao.dc_offset_pu)


def confrontar(
    programacao, medida_pu: np.ndarray, hipoteses: Optional[Dict[str, Tuple[str, dict]]] = None,
) -> List[dict]:
    """Confronta ``medida_pu`` (alinhada ao início do LIST, mesma grade) com a
    previsão de cada hipótese; devolve uma lista ordenada pelo rms do resíduo
    (a que melhor explica o dado primeiro). Cada item: ``nome``, ``mecanismo``,
    ``parametros``, ``rms_residuo_pu``, ``max_residuo_pu``, ``amostra_max``.
    Compara só o comprimento comum. Uma hipótese vencedora NÃO é prova: é a que
    menos erra neste dado."""
    medida = np.asarray(medida_pu, dtype=np.float64)
    resultado = []
    for nome, (mecanismo, parametros) in (hipoteses or HIPOTESES_CANDIDATAS).items():
        prevista = prever_forma(programacao, mecanismo, **parametros)
        n = min(prevista.size, medida.size)
        residuo = medida[:n] - prevista[:n]
        resultado.append({
            "nome": nome, "mecanismo": mecanismo, "parametros": dict(parametros),
            "rms_residuo_pu": float(np.sqrt(np.mean(np.square(residuo)))),
            "max_residuo_pu": float(np.max(np.abs(residuo))),
            "amostra_max": int(np.argmax(np.abs(residuo))),
        })
    resultado.sort(key=lambda item: item["rms_residuo_pu"])
    return resultado
