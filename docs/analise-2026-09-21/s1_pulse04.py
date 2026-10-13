"""s1_pulse04.py - medida precisa do unico evento PULSe que aparece nas duas
sessoes novas: classe 04 da sessao 2 (largura, nivel, instante).

Uso: python docs/analise-2026-09-21/s1_pulse04.py
Somente leitura.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
S2 = ROOT / "resultados" / "sessao_2026-09-16_16-16-16"
ANTIGO = Path(r"C:\Users\denis\Documents\1 Projetos\anti-synthetic-data\resultados")
FS = 30000.0


def rms_janela(x, t0_ms, t1_ms, vbase):
    seg = x[int(t0_ms / 1000 * FS):int(t1_ms / 1000 * FS)]
    return float(np.sqrt(np.mean(seg ** 2))) * vbase * np.sqrt(2.0)


def envelope(x, f0, div=8):
    n = max(2, int(round(FS / (div * f0))))
    m = len(x) // n
    pk = np.abs(x[: m * n]).reshape(m, n).max(axis=1)
    t = (np.arange(m) * n + n / 2.0) / FS * 1000.0
    return t, pk, n


print("### classe 04 (INTERRUPTION nativa PULSe), sessao 2, base config = 220 Vrms")
print("   trigger previsto (H-REF10) = 0.46 s de pre-trigger + 1.0 s/10 = 560.0 ms")
print(f"{'arquivo':<40} {'inicio':>8} {'fim':>8} {'larg':>7} {'V base':>8} {'V pulso':>8}")
for f in sorted(glob.glob(str(S2 / "04*.npz"))):
    x = np.load(f, allow_pickle=True)["tensao_pu"][0]
    t, pk, n = envelope(x, 50.0, div=8)
    ref = float(np.median(pk))
    r = pk / ref
    dentro = np.where(r > 1.4)[0]
    if dentro.size == 0:
        print(f"{os.path.basename(f)[:-4][:40]:<40}  sem evento")
        continue
    i0, i1 = int(dentro[0]), int(dentro[-1])
    # bordas: metade de um oitavo de ciclo de cada lado
    t0 = t[i0] - 1000.0 / (16 * 50.0)
    t1 = t[i1] + 1000.0 / (16 * 50.0)
    vbase = rms_janela(x, 300, 480, 220.0)
    # nivel do pulso medido no miolo (1 ciclo inteiro centrado)
    meio = (t0 + t1) / 2.0
    vp = rms_janela(x, meio - 10.0, meio + 10.0, 220.0)
    print(f"{os.path.basename(f)[:-4][:40]:<40} {t0:8.2f} {t1:8.2f} {t1-t0:7.2f} "
          f"{vbase:8.1f} {vp:8.1f}")

print()
print("### referencia: os mesmos PULSe nos dados de 2026-09-09 (base 127 Vrms)")
print("   trigger previsto (H-REF10) = 0.06 + 0.2/10 = 80.0 ms; largura nominal 60 ms")
for cid, nivel in (("02", 0.1), ("03", 1.1), ("04", 0.0215489)):
    f = sorted(glob.glob(str(ANTIGO / f"{cid}*.npz")))[0]
    x = np.load(f, allow_pickle=True)["tensao_pu"][0]
    t, pk, n = envelope(x, 60.0, div=8)
    ref = float(np.median(pk[:int(len(pk) * 0.3)]))
    r = pk / ref
    m = (r < 0.9) | (r > 1.08)
    idx = np.where(m)[0]
    i0, i1 = int(idx[0]), int(idx[-1])
    t0 = t[i0] - 1000.0 / (16 * 60.0)
    t1 = t[i1] + 1000.0 / (16 * 60.0)
    meio = (t0 + t1) / 2.0
    print(f"  {cid}: evento {t0:6.2f}..{t1:6.2f} ms (larg {t1-t0:5.2f}) "
          f"V_base={rms_janela(x, 5, 70, 127.0):6.1f} V_evento={rms_janela(x, meio-8, meio+8, 127.0):6.1f} "
          f"(programado {nivel*127:6.1f})")
