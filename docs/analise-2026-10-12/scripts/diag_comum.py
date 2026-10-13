"""Carregador comum dos scripts de diagnostico da correlacao do disturbio.

Somente leitura: le as sessoes de 07/10 da arvore principal, reconstroi
modelo/programada/forma_bancada na memoria (scripts/gerar_tres_versoes.py) e
nao grava nada nelas. Uso:  python docs/analise-2026-10-12/<script>.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "logica"))
sys.path.insert(0, str(RAIZ / "scripts"))

import analisar_sessao as AS  # noqa: E402
import gerar_tres_versoes as G3V  # noqa: E402
import sinais  # noqa: E402

RESULTADOS = Path(r"C:\Users\denis\Documents\1 Projetos\anti-synthetic-data\resultados")
SESSOES = {
    "127V/60Hz": "sessao_2026-10-07_14-59-54_run02",
    "127V/50Hz": "sessao_2026-10-07_127V_50Hz",
    "230V/50Hz": "sessao_2026-10-07_230V_50Hz",
}
FS = 30000.0


def corr_dist(esperado, registro, inicio, lag, f0, fase=0.0):
    """Mesma conta de analisar_sessao._correlacao_disturbio_alinhada."""
    return AS._correlacao_disturbio_alinhada(
        esperado, registro, inicio, lag, {"fs_hz": FS, "f0_hz": f0, "fase_graus": fase})[0]


def melhor_lag(esperado, registro, inicio, f0, faixa=80):
    """Lag (amostras) que maximiza a correlacao do disturbio, e o valor."""
    melhor = (None, -2.0)
    for lag in range(-faixa, faixa + 1):
        c = corr_dist(esperado, registro, inicio, lag, f0)
        if c is not None and c > melhor[1]:
            melhor = (lag, c)
    return melhor


def capturas(rotulo, classes=None):
    """Lista de dicts, uma por captura fisica da sessao."""
    sessao = RESULTADOS / SESSOES[rotulo]
    nomes = G3V._nomes_dos_npz(sessao)
    saida = []
    for reg in G3V._registros_da_sessao(sessao):
        if reg.get("simulado"):
            continue
        idc = str(reg["id_captura"])
        cid = idc.split("-")[0]
        if classes and cid not in classes:
            continue
        v = G3V.reconstruir_versoes(reg)
        npz = np.load(sessao / nomes[idc], allow_pickle=True)
        raw = np.asarray(npz["tensao_pu"][0], dtype=np.float64)
        if reg.get("inicio_janela") is not None:
            ini = int(reg["inicio_janela"])
        else:
            ini = int(sinais.janela_nominal(np.arange(raw.size), indice_trigger=int(reg["indice_trigger"]),
                                            pre_trigger_s=float(reg.get("pre_trigger_s", 0.0)),
                                            pontos=int(reg["pontos"]), fs_hz=FS)[0])
        saida.append(dict(sessao=rotulo, id=idc, classe=cid, arquivo=nomes[idc], reg=reg,
                          f0=float(reg.get("f0_hz", 60.0)), raw=raw, ini=ini, medida=raw[ini:ini + int(reg["pontos"])],
                          modelo=v["modelo"], programada=v["programada"], bancada=v["forma_bancada"],
                          origem=v["origem"], parametros=reg.get("parametros") or {}))
    return saida
