"""s1_trigger_instante.py - localiza o instante do trigger em classes cuja
saida JA esta no nominal antes do disparo (nao ha "onset" de 0 V).

Tres sondas independentes:
  (a) classe 18 (LIST:FREQuency): frequencia instantanea por intervalo entre
      cruzamentos por zero -> o degrau 60->57 Hz marca o inicio da lista.
  (b) classe 05 (CSINe): energia de 3o/5o/7o harmonico em janelas deslizantes
      -> o inicio do clipping marca o inicio do transiente.
  (c) classes 02/03/04 (PULSe): envelope de 1/4 de ciclo em TODO o registro,
      procurando qualquer desvio, com zoom na regiao prevista.

Uso: python docs/analise-2026-09-21/s1_trigger_instante.py
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


def carregar_um(pasta, prefixo):
    for f in sorted(glob.glob(os.path.join(pasta, f"{prefixo}*.npz"))):
        z = np.load(f, allow_pickle=True)
        return os.path.basename(f), z["tensao_pu"][0]
    return None, None


def carregar_todos(pasta, prefixo):
    out = []
    for f in sorted(glob.glob(os.path.join(pasta, f"{prefixo}*.npz"))):
        z = np.load(f, allow_pickle=True)
        X = z["tensao_pu"]
        for k in range(X.shape[0]):
            out.append((os.path.basename(f), X[k]))
    return out


def zeros_ascendentes(x):
    s = np.signbit(x)
    idx = np.where((~s[1:]) & s[:-1])[0]
    # refino linear
    t = []
    for i in idx:
        x0, x1 = x[i], x[i + 1]
        if x1 != x0:
            t.append(i + (0.0 - x0) / (x1 - x0))
    return np.asarray(t)


def freq_instantanea(x):
    z = zeros_ascendentes(x)
    if len(z) < 3:
        return np.array([]), np.array([])
    periodos = np.diff(z) / FS
    t_ms = (z[:-1] + np.diff(z) / 2.0) / FS * 1000.0
    return t_ms, 1.0 / periodos


def energia_harmonica(x, f0, largura_ciclos=2):
    """Razao (energia fora da fundamental)/(energia total) em janelas de N ciclos."""
    n = int(round(largura_ciclos * FS / f0))
    passo = n // 4
    ts, rs = [], []
    for i in range(0, len(x) - n, passo):
        w = x[i:i + n] * np.hanning(n)
        sp = np.abs(np.fft.rfft(w))
        k = int(round(f0 * n / FS))
        tot = float(np.sum(sp[1:] ** 2)) + 1e-18
        fund = float(np.sum(sp[max(1, k - 2):k + 3] ** 2))
        ts.append((i + n / 2.0) / FS * 1000.0)
        rs.append(max(0.0, 1.0 - fund / tot))
    return np.asarray(ts), np.asarray(rs)


def degrau(t, y, frac=0.5):
    """Instante em que y cruza o ponto medio entre o patamar inicial e o final."""
    if len(y) < 8:
        return None
    a = float(np.median(y[: max(3, len(y) // 10)]))
    b = float(np.median(y[-max(3, len(y) // 10):]))
    if abs(b - a) < 1e-9:
        return None
    alvo = a + frac * (b - a)
    sinal = np.sign(b - a)
    idx = np.where(sinal * (y - alvo) > 0)[0]
    return None if idx.size == 0 else float(t[idx[0]])


def envelope_quarto(x, f0):
    n = max(2, int(round(FS / (4 * f0))))
    m = len(x) // n
    pk = np.abs(x[: m * n]).reshape(m, n).max(axis=1)
    t = (np.arange(m) * n + n / 2.0) / FS * 1000.0
    return t, pk


print("=" * 78)
print("(a) CLASSE 18 - degrau de frequencia (LIST:FREQuency, 2 passos de 100 ms)")
print("=" * 78)
for pasta, rot, prev in ((ANTIGO, "antigo 200 ms", 20.0), (S1, "sessao1 1000 ms", 500.0)):
    nome, x = carregar_um(str(pasta), "18")
    if x is None:
        continue
    t, f = freq_instantanea(x)
    ok = np.isfinite(f) & (f > 30) & (f < 120)
    t, f = t[ok], f[ok]
    # primeiro instante em que a frequencia sai de 60 Hz por mais de 1 Hz
    base = float(np.median(f[t < prev * 0.8])) if np.any(t < prev * 0.8) else float(f[0])
    fora = np.where(np.abs(f - base) > 1.0)[0]
    t_mud = float(t[fora[0]]) if fora.size else None
    print(f"  {rot:16s} {nome}")
    print(f"     f base antes = {base:.3f} Hz; 1a mudanca >1 Hz em t = {t_mud} ms "
          f"(previsto H-REF10 = {prev:.1f} ms; codigo = {prev - (prev/5 if prev>100 else 20):.1f} ms)")
    # imprime o perfil resumido
    marcos = [0, prev - 20, prev, prev + 50, prev + 100, prev + 150, prev + 250]
    amostras = []
    for mm in marcos:
        j = np.argmin(np.abs(t - mm))
        if abs(t[j] - mm) < 15:
            amostras.append(f"t={t[j]:.0f}:{f[j]:.2f}Hz")
    print("     perfil:", "  ".join(amostras))

print()
print("=" * 78)
print("(b) CLASSE 05 - inicio do clipping CSINe (THD 5%)")
print("=" * 78)
for pasta, rot, f0, prev in ((ANTIGO, "antigo 200 ms", 60.0, 20.0), (S1, "sessao1 1000 ms", 60.0, 500.0)):
    nome, x = carregar_um(str(pasta), "05")
    if x is None:
        continue
    t, r = energia_harmonica(x, f0)
    td = degrau(t, r)
    a = float(np.median(r[: max(3, len(r) // 10)]))
    b = float(np.median(r[-max(3, len(r) // 10):]))
    print(f"  {rot:16s} {nome}: distorcao antes={a:.5f} depois={b:.5f}; "
          f"degrau em t={td} ms (previsto H-REF10={prev:.1f} ms)")

print()
print("=" * 78)
print("(c) CLASSES PULSe 02/03/04 - procura por QUALQUER evento no registro")
print("=" * 78)
for pasta, rot, f0, prev in ((ANTIGO, "antigo 200ms", 60.0, 80.0),
                             (S1, "sessao1 1000ms", 60.0, 560.0),
                             (S2, "sessao2 1000ms", 50.0, 560.0)):
    for cid in ("02", "03", "04"):
        linhas = carregar_todos(str(pasta), cid)
        if not linhas:
            continue
        piores = []
        for nome, x in linhas:
            t, pk = envelope_quarto(x, f0)
            ref = float(np.median(pk))
            if ref < 1e-6:
                continue
            r = pk / ref
            # ignora bordas (1 ciclo de cada lado)
            k = max(4, int(round(4)))
            rr, tt = r[k:-k], t[k:-k]
            i_min, i_max = int(np.argmin(rr)), int(np.argmax(rr))
            piores.append((rr[i_min], tt[i_min], rr[i_max], tt[i_max], nome))
        rmin = min(piores, key=lambda z: z[0])
        rmax = max(piores, key=lambda z: z[2])
        print(f"  {rot:14s} {cid}: n={len(piores):3d}  "
              f"envelope min {rmin[0]:.4f} @ {rmin[1]:7.2f} ms ({rmin[4][:26]}) | "
              f"max {rmax[2]:.4f} @ {rmax[3]:7.2f} ms")
        # zoom na janela prevista
        nome, x = linhas[0]
        t, pk = envelope_quarto(x, f0)
        ref = float(np.median(pk))
        jan = (t > prev - 30) & (t < prev + 120)
        print(f"        zoom {prev-30:.0f}..{prev+120:.0f} ms (env/ref): "
              + " ".join(f"{v:.3f}" for v in (pk[jan] / ref)[:28]))
