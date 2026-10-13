"""Compara o instante do evento (SAG/SWELL/INTERRUPTION) relativo ao onset da
saida: capturas antigas de 2026-09-09 (LIST:REPeat=1, sem margem, janela 200 ms)
vs. sessao de 2026-09-16 (LIST:REPeat=0, margem 400 ms). Nominal (gerar()): 60 ms."""
import glob, os, json, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from analise_trim import half_cycle_peaks, onset_index, KIND, FS

OLD = sys.argv[1]  # <repo main>/resultados
NEW = sys.argv[2]  # sessao_2026-09-16_16-07-44
F0 = 60.0
def span(x, kind):
    on = onset_index(x, F0)
    if on is None:
        return None
    xw = x[on:]
    t, pk = half_cycle_peaks(xw, F0)
    ref = np.median(pk[:4])
    r = pk / ref
    m = {"sag": r < 0.8, "swell": r > 1.12, "int": r < 0.3}[kind]
    if not m.any():
        return dict(onset=on / FS * 1e3, inicio=None, fim=None, janela=len(xw) / FS * 1e3)
    i = np.where(m)[0]
    return dict(onset=on / FS * 1e3, inicio=float(t[i[0]] - 1000 / (4 * F0)),
                fim=float(t[i[-1]] + 1000 / (4 * F0)), janela=len(xw) / FS * 1e3,
                fim_dentro_da_janela=bool(t[i[-1]] < t[-1] - 20))
print("classe | ANTIGO (REPeat=1, janela 200ms): inicio/fim ms apos onset | NOVO (REPeat=0): inicio/fim | nominal 60/120")
for cid in ("10", "11", "12", "13", "14", "16"):
    fo = glob.glob(os.path.join(OLD, f"{cid}_*.npz"))[0]
    fn = glob.glob(os.path.join(NEW, f"{cid}_*.npz"))[0]
    kind = KIND[cid]
    so = span(np.load(fo)["tensao_pu"][0], kind)
    sn = span(np.load(fn)["tensao_pu"][0], kind)
    f = lambda s: "sem evento" if s is None or s["inicio"] is None else f"{s['inicio']:.0f}/{s['fim']:.0f} (onset {s['onset']:.1f}; janela util {s['janela']:.0f} ms; fim_visivel={s.get('fim_dentro_da_janela')})"
    print(f"{cid} {kind:5s} | {f(so)} | {f(sn)}")
