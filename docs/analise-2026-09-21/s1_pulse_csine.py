"""s1_pulse_csine.py - dois achados que o arquivo 00 nao tem:
  (1) o PULSe da classe 04 na sessao 2 aparece, mas com amplitude ~1.9x em vez
      de ~0 -> inspeciona amostra a amostra.
  (2) a classe 05 (CSINe) da sessao 1 nao tem harmonico nenhum -> mede THD
      real contra os dados antigos.

Uso: python docs/analise-2026-09-21/s1_pulse_csine.py
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


def carregar(pasta, prefixo):
    out = []
    for f in sorted(glob.glob(os.path.join(pasta, f"{prefixo}*.npz"))):
        z = np.load(f, allow_pickle=True)
        X = z["tensao_pu"]
        for k in range(X.shape[0]):
            out.append((os.path.basename(f)[:-4], X[k]))
    return out


def meta(pasta, prefixo):
    m = {}
    for p in glob.glob(os.path.join(pasta, "metadata", f"{prefixo}*.jsonl")):
        for line in open(p, encoding="utf-8"):
            if line.strip():
                j = json.loads(line)
                m[j["id_captura"]] = j["parametros"]
    return m


def rms_meio_ciclo(x, f0):
    n = int(round(FS / (2 * f0)))
    m = len(x) // n
    seg = x[: m * n].reshape(m, n)
    r = np.sqrt(np.mean(seg ** 2, axis=1))
    t = (np.arange(m) * n + n / 2.0) / FS * 1000.0
    return t, r


def thd_harmonicos(x, f0, t0_ms=None, t1_ms=None):
    """THD por FFT de um trecho com numero inteiro de ciclos."""
    i0 = 0 if t0_ms is None else int(t0_ms / 1000 * FS)
    i1 = len(x) if t1_ms is None else int(t1_ms / 1000 * FS)
    seg = x[i0:i1]
    ciclos = int(len(seg) * f0 / FS)
    n = int(round(ciclos * FS / f0))
    seg = seg[:n]
    sp = np.abs(np.fft.rfft(seg)) * 2.0 / n
    k = ciclos
    fund = sp[k]
    harms = {h: float(sp[h * k] / (fund + 1e-18)) for h in (2, 3, 5, 7, 9) if h * k < len(sp)}
    total = np.sqrt(max(0.0, float(np.sum(sp[1:] ** 2)) - fund ** 2)) / (fund + 1e-18)
    return float(fund), total, harms


print("=" * 78)
print("(1) CLASSE 04 sessao 2 - o que acontece em 560..620 ms")
print("=" * 78)
par = meta(str(S2), "04")
linhas = carregar(str(S2), "04")
for nome, x in linhas:
    t, r = rms_meio_ciclo(x, 50.0)
    base = float(np.median(r))
    jan = (t >= 555) & (t <= 630)
    print(f"  {nome[:44]:46s} rms_base={base:.4f} pu  "
          f"rms[560..620]={np.mean(r[jan])/base:6.3f} x base   "
          f"min={r.min()/base:.3f} max={r.max()/base:.3f}")
nome, x = linhas[0]
print(f"\n  Amostras de {nome} (pu) a cada 0.5 ms entre 550 e 640 ms:")
idx = np.arange(int(0.550 * FS), int(0.640 * FS), 15)
print("   ", " ".join(f"{x[i]:+.2f}" for i in idx))
print(f"\n  pico do registro inteiro: {np.max(np.abs(x)):.3f} pu "
      f"({np.max(np.abs(x))*220*np.sqrt(2):.1f} V com base 220 Vrms)")

print()
print("=" * 78)
print("(2) CLASSE 05 - THD real (CSINe programado: 5%)")
print("=" * 78)
for pasta, rot, f0 in ((ANTIGO, "antigo 2026-09-09", 60.0), (S1, "sessao 1", 60.0)):
    for nome, x in carregar(str(pasta), "05"):
        # trecho inteiro e trecho depois do trigger previsto
        f_all, thd_all, h_all = thd_harmonicos(x, f0)
        t0 = 520.0 if len(x) > 10000 else 30.0
        t1 = 900.0 if len(x) > 10000 else 190.0
        f_p, thd_p, h_p = thd_harmonicos(x, f0, t0, t1)
        crista = float(np.max(np.abs(x)) / (np.sqrt(np.mean(x ** 2)) + 1e-18))
        print(f"  {rot:18s} {nome[:34]:36s}")
        print(f"      registro inteiro: fund={f_all:.4f} pu  THD={thd_all*100:6.3f}%  "
              f"h3={h_all.get(3,0)*100:.2f}% h5={h_all.get(5,0)*100:.2f}% h7={h_all.get(7,0)*100:.2f}%")
        print(f"      trecho {t0:.0f}..{t1:.0f} ms:  fund={f_p:.4f} pu  THD={thd_p*100:6.3f}%  "
              f"fator de crista={crista:.4f} (senoide pura=1.4142)")

print()
print("=" * 78)
print("(3) THD das demais classes com harmonicos (controle) - sessao 1")
print("=" * 78)
for cid, f0 in (("13", 60.0), ("15", 60.0), ("20", 60.0)):
    for nome, x in carregar(str(S1), cid):
        f_p, thd_p, h_p = thd_harmonicos(x, f0, 520.0, 680.0)
        print(f"  {cid} {nome[:40]:42s} THD(520..680ms)={thd_p*100:6.2f}%  h3={h_p.get(3,0)*100:.2f}%")
