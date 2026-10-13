"""Assinatura portavel entre plataformas do ``gerar()`` (v1.15).

O SHA-256 dos bytes float64 so se reproduz onde ``np.sin``/``np.cos`` dao o
mesmo ultimo bit (medido: o numpy do Linux difere de uma referencia em
long double em ate 2,2e-16 pu por amostra; ver CHANGELOG/v1.15.md). Esta
assinatura compara por TOLERANCIA, sem hash de valores arredondados (que cairia
numa fronteira de arredondamento por acaso):

- ``n``: numero de amostras (exato);
- ``parametros``: o dicionario de parametros do ``gerar()``; inteiros, textos,
  booleanos e chaves exatos, floats com ``rtol=1e-9``;
- ``soma``, ``energia``, ``minimo``, ``maximo`` e ``projecoes`` (produtos
  internos com ``NPROJ`` vetores fixos, gerados por ``default_rng(1000+k)``),
  todos somados com ``math.fsum`` e comparados com ``TOL_ABS``.

``TOL_ABS = 1e-9`` e 4 ordens de grandeza acima do erro de plataforma esperado
(6000 amostras x 2,2e-16 x |peso| ~ 1e-12) e 3 ordens abaixo da resolucao da
fonte (16 bits ~ 3e-5 pu) e do osciloscopio (8 bits). Uma unica amostra
alterada em 1e-7 pu muda alguma projecao em ~1e-7 x |peso| >> TOL_ABS.
"""

import json
import math

import numpy as np

N_AMOSTRAS = 6000
NPROJ = 4
TOL_ABS = 1e-9
RTOL_PARAMETROS = 1e-9


def _pesos():
    return [np.random.default_rng(1000 + k).standard_normal(N_AMOSTRAS) for k in range(NPROJ)]


_PESOS = _pesos()


def _limpa(parametros):
    """Os parametros como JSON puro (mesma normalizacao da assinatura exata)."""
    return json.loads(json.dumps(parametros, sort_keys=True))


def resumo(tensao, parametros):
    v = np.asarray(tensao, dtype=np.float64)
    return {
        "n": int(v.size),
        "parametros": _limpa(parametros),
        "soma": math.fsum(v.tolist()),
        "energia": math.fsum((v * v).tolist()),
        "minimo": float(v.min()),
        "maximo": float(v.max()),
        "projecoes": [math.fsum((v * w).tolist()) if v.size == w.size else float("nan") for w in _PESOS],
    }


def gerar_resumo(experimento, f0, seed, indice):
    t = np.arange(N_AMOSTRAS, dtype=np.float64) / 30_000.0
    tensao, parametros = experimento.gerar(t, f0, indice, np.random.default_rng(seed))
    return resumo(tensao, parametros)


def _parametros_iguais(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_parametros_iguais(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_parametros_iguais(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool) or isinstance(a, str) or isinstance(b, str) or a is None or b is None:
        return a == b and type(a) is type(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if isinstance(a, int) and isinstance(b, int):
            return a == b
        return math.isclose(a, b, rel_tol=RTOL_PARAMETROS, abs_tol=1e-12)
    return False


def diferencas(obtido, esperado):
    """Lista (vazia se iguais dentro da tolerancia) do que diverge."""
    erros = []
    if obtido["n"] != esperado["n"]:
        erros.append("n")
    if not _parametros_iguais(obtido["parametros"], esperado["parametros"]):
        erros.append("parametros")
    for campo in ("soma", "energia", "minimo", "maximo"):
        if not abs(obtido[campo] - esperado[campo]) <= TOL_ABS:
            erros.append(campo)
    for k, (a, b) in enumerate(zip(obtido["projecoes"], esperado["projecoes"])):
        if not abs(a - b) <= TOL_ABS:
            erros.append(f"projecao{k}")
    if len(obtido["projecoes"]) != len(esperado["projecoes"]):
        erros.append("projecoes")
    return erros


def confere(experimento, f0, seed, indice, esperado):
    return not diferencas(gerar_resumo(experimento, f0, seed, indice), esperado)
