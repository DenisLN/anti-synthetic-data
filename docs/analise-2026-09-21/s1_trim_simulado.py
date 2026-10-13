"""s1_trim_simulado.py - recorte offline das capturas reais, usando o instante
de trigger MEDIDO (500 ms para margin on / pre 0.40; 560 ms para 02/03/04).

Responde: qual a janela minima segura antes/depois do trigger por tipo de
classe, e quanto do registro atual de 1 s e' descartado.

Tambem verifica A4 (LIST:REPeat) de forma independente: inicio/fim do evento
medido a partir do trigger, antigo (REPeat=1) x novo (REPeat=0), contra o
nominal de gerar() (60..120 ms para 10-16, 60..140 ms para 07).

Uso: python docs/analise-2026-09-21/s1_trim_simulado.py
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

# nominal do gerar(): (inicio_ms, fim_ms) do disturbio DENTRO da janela de 200 ms
NOMINAL = {"02": (60, 120), "03": (60, 120), "04": (60, 120), "07": (60, 140),
           "08": (80, 80.05), "09": (60, 120), "10": (60, 120), "11": (60, 120),
           "12": (60, 120), "13": (60, 120), "14": (60, 120), "16": (60, 120),
           "17": (60, 140)}
KIND = {"10": "sag", "11": "sag", "12": "sag", "13": "swell", "14": "swell",
        "16": "int", "02": "sag", "03": "swell", "04": "int"}


def envelope(x, f0, div=4):
    n = max(2, int(round(FS / (div * f0))))
    m = len(x) // n
    pk = np.abs(x[: m * n]).reshape(m, n).max(axis=1)
    t = (np.arange(m) * n + n / 2.0) / FS * 1000.0
    return t, pk


def span(x, f0, kind, t_trig_ms, jan_ms=260.0):
    """Inicio/fim do evento, em ms APOS o trigger, dentro de [trig, trig+jan]."""
    t, pk = envelope(x, f0)
    fora = (t < t_trig_ms - 5) | (t > t_trig_ms + jan_ms + 5)
    dentro = (t >= t_trig_ms) & (t <= t_trig_ms + jan_ms)
    ref = float(np.median(pk[dentro])) if dentro.any() else 0.0
    if ref <= 1e-6:
        return None
    r = pk / ref
    if kind == "sag":
        m = (r < 0.80) & dentro
    elif kind == "swell":
        m = (r > 1.12) & dentro
    else:
        m = (r < 0.30) & dentro
    if not m.any():
        return None
    i = np.where(m)[0]
    q = 1000.0 / (8 * f0)
    return float(t[i[0]] - q - t_trig_ms), float(t[i[-1]] + q - t_trig_ms)


def carregar(pasta, prefixo="*"):
    out = []
    for f in sorted(glob.glob(os.path.join(pasta, f"{prefixo}.npz"))):
        z = np.load(f, allow_pickle=True)
        X = z["tensao_pu"]
        for k in range(X.shape[0]):
            out.append((os.path.basename(f)[:-4], X[k]))
    return out


print("=" * 78)
print("A4 (LIST:REPeat) - inicio/fim do evento em ms APOS o trigger medido")
print("=" * 78)
print(f"{'cls':<4} {'nominal':>12} {'ANTIGO REPeat=1':>22} {'NOVO REPeat=0 (s1)':>22}")
for cid in ("10", "11", "12", "13", "14", "16"):
    nom = NOMINAL[cid]
    a = carregar(str(ANTIGO), f"{cid}*")
    n1 = carregar(str(S1), f"{cid}*")
    sa = span(a[0][1], 60.0, KIND[cid], 20.0) if a else None
    sn = span(n1[0][1], 60.0, KIND[cid], 500.0) if n1 else None
    fa = "nao detectado" if sa is None else f"{sa[0]:6.1f}..{sa[1]:6.1f}"
    fn = "nao detectado" if sn is None else f"{sn[0]:6.1f}..{sn[1]:6.1f}"
    print(f"{cid:<4} {nom[0]:5.0f}..{nom[1]:5.0f} {fa:>22} {fn:>22}")
print("  (antigo: janela de 200 ms; o evento que passa de 180 ms e' truncado pela janela)")

print()
print("=" * 78)
print("TRIM SIMULADO - janela minima que contem o evento inteiro")
print("=" * 78)


def analisa_trim(pasta, f0, rot, trig_padrao=500.0, trig_pulse=560.0):
    print(f"\n--- {rot}")
    print(f"{'classe':<40} {'trigger':>8} {'ini_ev':>8} {'fim_ev':>8} {'1o ciclo':>9}")
    resumo = []
    for nome, x in carregar(pasta):
        cid = nome[:2]
        trig = trig_pulse if cid in ("02", "03", "04") else trig_padrao
        i_tr = int(trig / 1000 * FS)
        # amplitude do 1o ciclo apos o trigger vs. a mediana dos 200 ms
        n = int(round(FS / f0))
        if i_tr + 6 * n > len(x):
            continue
        c1 = float(np.max(np.abs(x[i_tr:i_tr + n])))
        ref = float(np.median([np.max(np.abs(x[i_tr + k * n:i_tr + (k + 1) * n])) for k in range(1, 6)]))
        ev = span(x, f0, KIND.get(cid, ""), trig) if cid in KIND else None
        ini = "-" if ev is None else f"{ev[0]:8.1f}"
        fim = "-" if ev is None else f"{ev[1]:8.1f}"
        resumo.append((nome, trig, ev, c1 / (ref + 1e-12)))
    vistos = set()
    for nome, trig, ev, rc1 in resumo:
        if nome[:2] in vistos:
            continue
        vistos.add(nome[:2])
        ini = "       -" if ev is None else f"{ev[0]:8.1f}"
        fim = "       -" if ev is None else f"{ev[1]:8.1f}"
        print(f"{nome[:40]:<40} {trig:8.1f} {ini} {fim} {rc1:9.4f}")
    # razao do 1o ciclo: menor/maior entre todas as capturas
    r = [v[3] for v in resumo]
    print(f"  razao pico(1o ciclo apos trigger)/pico(ciclos 2-6): min={min(r):.4f} max={max(r):.4f} "
          f"n={len(r)}  -> mede se ha rampa inicial")


analisa_trim(str(S1), 60.0, "SESSAO 1 (127 V / 60 Hz)")
analisa_trim(str(S2), 50.0, "SESSAO 2 (220 V / 50 Hz)")

print()
print("=" * 78)
print("QUANTO DO REGISTRO DE 1 s SERIA DESCARTADO")
print("=" * 78)
for antes, depois in ((20, 20), (20, 50), (40, 60), (60, 100), (400, 400)):
    total = 200 + antes + depois
    print(f"  margem {antes:3d} ms antes / {depois:3d} ms depois -> janela util {total:4d} ms "
          f"({total/1000*100:5.1f}% do registro de 1000 ms atual; descarta {1000-total:4d} ms = "
          f"{(1000-total)/10:.1f}%)")
print()
print("  ATENCAO: com :TIMebase:REFerence LEFT o trigger cai em "
      "pre_trigger + RANGe/10, nao em pre_trigger.")
for antes in (20, 40, 60):
    for depois in (20, 50, 100):
        pontos = int((0.200 + antes / 1000 + depois / 1000) * FS)
        dur = pontos / FS
        offset = dur / 10 * 1000
        pre_real = antes + offset
        pos_real = dur * 1000 - pre_real
        print(f"   margem pedida {antes:3d}/{depois:3d} ms -> janela {dur*1000:6.1f} ms, "
              f"deslocamento REF LEFT {offset:5.1f} ms -> pre-trigger REAL {pre_real:6.1f} ms, "
              f"pos-trigger REAL {pos_real:6.1f} ms "
              f"{'*** EVENTO DE 200 ms TRUNCADO EM ' + format(200-pos_real,'.1f') + ' ms' if pos_real < 200 else 'OK'}")
