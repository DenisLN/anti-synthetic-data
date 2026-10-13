"""s1_onset.py - verificacao independente do achado A1/A6 do arquivo 00.

Hipotese propria (H-REF10): o instante do TRIGGER dentro do registro NAO e
`margem_amostras_antes` e sim `pre_trigger_efetivo + TIMebase:RANGe/10`, porque
`:TIMebase:REFerence LEFT` no InfiniiVision coloca a referencia a UMA DIVISAO
da borda esquerda (10% da janela), e `get_waveform()` joga fora `x_origin`
(`time_axis -= time_axis[0]`).

Previsoes:
  * antigos (2026-09-09): janela 0.2 s, pre=0 -> trigger em 20.0 ms;
    02/03/04 (pre=0.06) -> trigger em 80.0 ms.
  * novos (margin on): janela 1.0 s, pre=0.40 -> trigger em 500.0 ms;
    02/03/04 (pre=0.46) -> trigger em 560.0 ms.

O script mede o onset da saida (classes que comecam com a saida zerada) e o
inicio/fim do evento (classes PULSe, cuja saida ja esta no nominal) sem
assumir nada do codigo.

Uso: python docs/analise-2026-09-21/s1_onset.py
Somente leitura.
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
S1 = ROOT / "resultados" / "sessao_2026-09-16_16-07-44"
S2 = ROOT / "resultados" / "sessao_2026-09-16_16-16-16"
ANTIGO = Path(r"C:\Users\denis\Documents\1 Projetos\anti-synthetic-data\resultados")
FS = 30000.0
PULSE_IDS = {"02", "03", "04"}


def meia_onda(x, f0):
    """Pico |x| por meio ciclo. Devolve (t_centro_ms, pico)."""
    n = int(round(FS / (2 * f0)))
    m = len(x) // n
    pk = np.abs(x[: m * n]).reshape(m, n).max(axis=1)
    t = (np.arange(m) * n + n / 2.0) / FS * 1000.0
    return t, pk, n


def onset_saida(x, thr_rel=0.25):
    """Primeiro instante em que |x| passa de thr_rel (pu) - recuado ate o
    ultimo ponto em que a amostra anterior era <= 2% (cruzamento por zero)."""
    idx = np.where(np.abs(x) > thr_rel)[0]
    if idx.size == 0:
        return None
    i = int(idx[0])
    j = i
    while j > 0 and abs(x[j - 1]) < abs(x[j]) and abs(x[j - 1]) > 0.02:
        j -= 1
    return j


def evento_envelope(x, f0, kind, ref_janela_ms=40.0):
    """Inicio/fim (ms) de sag/swell/interrupcao pelo envelope de meio ciclo,
    usando como referencia a MEDIANA de todo o registro (robusto a eventos
    curtos) em vez do inicio do trecho."""
    t, pk, n = meia_onda(x, f0)
    ref = float(np.median(pk))
    if ref <= 1e-6:
        return None, ref
    r = pk / ref
    if kind == "sag":
        m = r < 0.80
    elif kind == "swell":
        m = r > 1.12
    else:
        m = r < 0.30
    if not m.any():
        return None, ref
    i = np.where(m)[0]
    return (float(t[i[0]] - 1000.0 / (4 * f0)), float(t[i[-1]] + 1000.0 / (4 * f0))), ref


def carregar(pasta):
    metas = {}
    for p in glob.glob(os.path.join(pasta, "metadata", "*.jsonl")):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                j = json.loads(line)
                metas[j["id_captura"]] = j
    out = []
    for f in sorted(glob.glob(os.path.join(pasta, "*.npz"))):
        z = np.load(f, allow_pickle=True)
        X = z["tensao_pu"]
        ids = z["id_captura"]
        for k in range(X.shape[0]):
            out.append((os.path.basename(f)[:-4], str(ids[k]), X[k], metas.get(str(ids[k]), {})))
    return out


KIND = {"02": "sag", "03": "swell", "04": "int", "10": "sag", "11": "sag", "12": "sag",
        "13": "swell", "14": "swell", "16": "int"}


def rodar(pasta, f0, rotulo):
    print(f"\n########## {rotulo}  (f0={f0} Hz, pasta={os.path.basename(pasta)})")
    linhas = carregar(pasta)
    resumo = {}
    for nome, idc, x, md in linhas:
        cid = nome[:2]
        n = len(x)
        dur_ms = n / FS * 1000.0
        ma = md.get("margem_amostras_antes", 0)
        pre_classe = 0.060 if cid in PULSE_IDS else 0.0
        pre_efetivo_ms = pre_classe * 1000.0 + ma / FS * 1000.0
        trig_codigo_ms = ma / FS * 1000.0          # onde o codigo acha que esta o trigger
        trig_h_ref10_ms = pre_efetivo_ms + dur_ms / 10.0   # H-REF10
        on = onset_saida(x)
        on_ms = None if on is None else on / FS * 1000.0
        ev, ref = evento_envelope(x, f0, KIND.get(cid, "")) if cid in KIND else (None, None)
        resumo.setdefault(cid, []).append((on_ms, ev, ref))
    for cid in sorted(resumo):
        ons = [v[0] for v in resumo[cid] if v[0] is not None]
        evs = [v[1] for v in resumo[cid] if v[1] is not None]
        n_tot = len(resumo[cid])
        pre_classe = 60.0 if cid in PULSE_IDS else 0.0
        # recalcula previsoes com o primeiro registro da classe
        dur_ms = None
        for nome, idc, x, md in linhas:
            if nome[:2] == cid:
                dur_ms = len(x) / FS * 1000.0
                ma = md.get("margem_amostras_antes", 0) / FS * 1000.0
                break
        prev = pre_classe + ma + dur_ms / 10.0
        cod = ma
        s_on = (f"onset {min(ons):7.2f}..{max(ons):7.2f} ms (n={len(ons)}/{n_tot})"
                if ons else f"SEM onset (n=0/{n_tot})")
        s_ev = ""
        if evs:
            i0 = [e[0] for e in evs]
            i1 = [e[1] for e in evs]
            s_ev = f" | evento {min(i0):7.2f}..{max(i1):7.2f} ms (n={len(evs)}/{n_tot})"
        elif cid in KIND:
            s_ev = f" | evento NAO DETECTADO em 0/{n_tot}"
        print(f"  {cid}: {s_on}{s_ev}")
        print(f"       previsto: trigger_codigo={cod:.1f} ms  H-REF10={prev:.1f} ms  (janela {dur_ms:.0f} ms)")


if __name__ == "__main__":
    rodar(str(ANTIGO), 60.0, "ANTIGOS 2026-09-09 (sem margem, sem diagnostico, REPeat=1)")
    rodar(str(S1), 60.0, "SESSAO 1 2026-09-16 16:07:44 (127 V / 60 Hz, margin+diag)")
    rodar(str(S2), 50.0, "SESSAO 2 2026-09-16 16:16:16 (220 V / 50 Hz, margin+diag)")
