"""s1_niveis.py - nivel fisico real (Vrms) de cada classe, nas duas sessoes e
nos dados antigos, comparado com o que a configuracao pedia.

Motivo: a sessao 2 foi configurada para 220 Vrms mas o proprio
MEASure:VOLTage:AC? da AMETEK reporta ~126,6 V em todos os pontos de
diagnostico. Este script confronta osciloscopio x config.

Uso: python docs/analise-2026-09-21/s1_niveis.py
Somente leitura.
"""
from __future__ import annotations

import collections
import glob
import os
import re
import statistics as st
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
S1 = ROOT / "resultados" / "sessao_2026-09-16_16-07-44"
S2 = ROOT / "resultados" / "sessao_2026-09-16_16-16-16"
ANTIGO = Path(r"C:\Users\denis\Documents\1 Projetos\anti-synthetic-data\resultados")
FS = 30000.0
SQ2 = np.sqrt(2.0)


def rms_v(x, vbase, i0, i1):
    seg = x[i0:i1]
    return float(np.sqrt(np.mean(seg ** 2))) * vbase * SQ2


def resumo(pasta, vbase, rot, jan_repouso, jan_evento):
    print(f"\n### {rot}  (base configurada = {vbase} Vrms)")
    print(f"{'classe':<42} {'Vrms repouso':>13} {'Vrms evento':>12} {'pico pu':>8}")
    for f in sorted(glob.glob(os.path.join(pasta, "*.npz"))):
        z = np.load(f, allow_pickle=True)
        X = z["tensao_pu"]
        x = X[0]
        n = len(x)
        a0, a1 = [int(v / 1000 * FS) for v in jan_repouso]
        b0, b1 = [int(v / 1000 * FS) for v in jan_evento]
        a1, b1 = min(a1, n), min(b1, n)
        print(f"{os.path.basename(f)[:-4][:42]:<42} {rms_v(x, vbase, a0, a1):13.1f} "
              f"{rms_v(x, vbase, b0, b1):12.1f} {float(np.max(np.abs(x))):8.3f}")


# janelas: repouso = logo antes do trigger; evento = 30 ms depois do trigger
resumo(str(ANTIGO), 127.0, "ANTIGOS 2026-09-09 (janela 200 ms, trigger em 20/80 ms)",
       (0, 18), (90, 130))
resumo(str(S1), 127.0, "SESSAO 1 (janela 1000 ms, trigger em 500/560 ms)",
       (300, 480), (520, 690))
resumo(str(S2), 220.0, "SESSAO 2 (janela 1000 ms, trigger em 500/560 ms)",
       (300, 480), (520, 690))

print()
print("=" * 78)
print("MEASure:VOLTage:AC? da AMETEK, por classe e ponto (dos logs)")
print("=" * 78)
dpat = re.compile(r"\[DIAGNOSTICO\] ponto=(\S+) t=([\d.]+) transiente_ativo=(\S+) "
                  r"output=(\S+) tensao_v=(\S+)")
cpat = re.compile(r"Experimento (\d\d) \((\w+)\)")
for path, rot in ((r"C:\Users\denis\Desktop\log1.txt", "log1 / sessao 1 (127 V)"),
                  (r"C:\Users\denis\Desktop\log2.txt", "log2 / sessao 2 (220 V)")):
    cur = None
    acc = collections.defaultdict(list)
    for line in open(path, encoding="utf-8", errors="replace"):
        c = cpat.search(line)
        if c:
            cur = c.group(1)
        d = dpat.search(line)
        if d and d.group(5) != "None":
            acc[(cur, d.group(1))].append(float(d.group(5)))
    print(f"\n--- {rot}")
    for (cls, ponto), v in sorted(acc.items(), key=lambda kv: (kv[0][0] or "", kv[0][1])):
        print(f"  {str(cls):>4} {ponto:<26} n={len(v):4d} med={st.median(v):8.3f} "
              f"min={min(v):8.3f} max={max(v):8.3f}")
