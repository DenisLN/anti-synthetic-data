"""s1_resolucao.py - resolucao vertical real (LSB) de cada captura e
consequencias (classe 19/DC_OFFSET, classe 08/TRANSIENT, sobre-pico).

O passo de quantizacao e' recuperado das diferencas unicas entre amostras
vizinhas do .npz (o dado veio em BYTE, 8 bits).

Uso: python docs/analise-2026-09-21/s1_resolucao.py
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
FS = 30000.0


def lsb(x):
    d = np.abs(np.diff(np.unique(np.round(x, 12))))
    d = d[d > 1e-12]
    return float(np.min(d)) if d.size else float("nan")


def tabela(pasta, vbase, rot):
    print(f"\n### {rot} (base {vbase} Vrms; 1 pu de pico = {vbase*np.sqrt(2):.1f} V)")
    print(f"{'classe':<42} {'LSB (pu)':>10} {'LSB (V)':>9} {'V/div':>8} {'pico pu':>8} {'niveis usados':>14}")
    vistos = set()
    for f in sorted(glob.glob(os.path.join(pasta, "*.npz"))):
        cid = os.path.basename(f)[:2]
        if cid in vistos:
            continue
        vistos.add(cid)
        x = np.load(f, allow_pickle=True)["tensao_pu"][0]
        q = lsb(x)
        qv = q * vbase * np.sqrt(2.0)
        niveis = len(np.unique(np.round(x / q).astype(np.int64)))
        print(f"{os.path.basename(f)[:-4][:42]:<42} {q:10.5f} {qv:9.3f} {qv*256/8:8.2f} "
              f"{float(np.max(np.abs(x))):8.3f} {niveis:14d}")


tabela(str(S1), 127.0, "SESSAO 1")
tabela(str(S2), 220.0, "SESSAO 2")

print()
print("### classe 19 (DC_OFFSET): offset programado x resolucao")
for pasta, vbase, rot in ((S1, 127.0, "sessao 1"),):
    for f in sorted(glob.glob(os.path.join(str(pasta), "19*.npz"))):
        x = np.load(f, allow_pickle=True)["tensao_pu"][0]
        md = [json.loads(l) for l in open(os.path.join(str(pasta), "metadata", "19_dc_offset.jsonl"),
                                          encoding="utf-8") if l.strip()][0]
        alvo = md["parametros"]["dc_offset_pu"]
        q = lsb(x)
        # offset medido em janelas de 1 ciclo depois do trigger
        n = 500
        offs = [float(np.mean(x[i:i + n])) for i in range(15000, 20000, n)]
        print(f"  {rot}: offset programado={alvo:.4f} pu; medido por ciclo="
              f"{['%.4f' % o for o in offs]}; LSB={q:.4f} pu -> o offset vale "
              f"{alvo/q:.1f} LSB")

print()
print("### sobre-pico das classes com harmonicos/eventos (pico medido / pico de gerar())")
print("   (gerar() normaliza por pico=1; LIST:VOLTage programa RMS por ciclo)")
for f in sorted(glob.glob(os.path.join(str(S1), "*.npz"))):
    cid = os.path.basename(f)[:2]
    if cid not in ("10", "11", "13", "14", "15", "16", "17", "20", "06", "09"):
        continue
    x = np.load(f, allow_pickle=True)["tensao_pu"][0]
    seg = x[15000:21000]
    print(f"  {cid} {os.path.basename(f)[:-4][:40]:<42} pico no evento = {float(np.max(np.abs(seg))):.3f} pu")
