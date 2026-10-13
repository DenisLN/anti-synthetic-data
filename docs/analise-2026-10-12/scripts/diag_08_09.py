"""Item 1 (cont.): 08 (impulso fora de lugar a 50 Hz) e 09 (impulso espurio em 100 ms).

08: desloca o RESIDUO do evento da programada em +N amostras (N=600 = 20 ms) e
    recalcula a correlacao do disturbio (lag otimo +-80). Reproduz o 0,005 -> 0,6
    do professor com a programada. Tambem mostra onde esta o maior pico da medida.
09: amplitude do impulso espurio em 100 ms e sua posicao relativa ao inicio da
    oscilacao (+600 amostras = 20 ms?).
Uso: python docs/analise-2026-10-12/diag_08_09.py
"""
import numpy as np
import diag_comum as D

FS = D.FS
print("== 08: deslocar o evento da programada")
print(f"{'sessao':10s} {'id':8s} {'c0':>6s}  " + "  ".join(f"+{s:3d}" for s in (0, 300, 600, 601, 602, 603)) + "   pico medida (ms,pu)  pico prog (ms)")
for rot in D.SESSOES:
    for c in D.capturas(rot, {"08"}):
        sen = np.sin(2 * np.pi * c["f0"] * np.arange(6000) / FS)
        r = c["programada"] - sen
        lag, c0 = D.melhor_lag(c["programada"], c["raw"], c["ini"], c["f0"], 80)
        vals = []
        for s in (0, 300, 600, 601, 602, 603):
            x = sen + np.roll(r, s)
            vals.append(D.melhor_lag(x, c["raw"], c["ini"], c["f0"], 80)[1])
        rm = c["medida"] - sen
        ip = int(np.argmax(np.abs(rm))); ipp = int(np.argmax(np.abs(r)))
        print(f"{rot:10s} {c['id']:8s} {c0:6.3f}  " + "  ".join(f"{v:5.3f}" for v in vals) + f"   {ip / 30:6.2f},{rm[ip]:+.2f}      {ipp / 30:.2f}")

print("\n== 09: impulso espurio perto de 100 ms (erro = medida - programada, 99..103 ms)")
for rot in D.SESSOES:
    for c in D.capturas(rot, {"09"}):
        lag, _ = D.melhor_lag(c["programada"], c["raw"], c["ini"], c["f0"], 80)
        i0 = c["ini"] + lag
        e = c["raw"][i0:i0 + 6000] - c["programada"]
        j = slice(99 * 30, 103 * 30)
        k = int(np.argmax(np.abs(e[j]))) + 99 * 30
        base = np.abs(e[:2000]).max()
        print(f"{rot:10s} {c['id']:8s} max|erro| em 99-103 ms: {e[k]:+.3f} pu em {k / 30:.2f} ms ; max|erro| nos 66 ms iniciais (sem evento): {base:.3f}; "
              f"duracao {c['parametros']['duration_s'] * 1000:.1f} ms, f_osc {c['parametros']['oscillation_hz']:.0f} Hz")

print("\n== 08 a 50 Hz: evento deslocado +600 amostras (20 ms) E filtro linear de 2.a ordem (mesma grade de diag_resposta_fonte.py)")
from diag_resposta_fonte import pear, resp2  # noqa: E402
for c in D.capturas("127V/50Hz", {"08"}):
    sen = np.sin(2 * np.pi * c["f0"] * np.arange(6000) / FS)
    r = np.roll(c["programada"] - sen, 600)
    x = sen + r
    lag, c600 = D.melhor_lag(x, c["raw"], c["ini"], c["f0"], 80)
    i0 = c["ini"] + lag
    rm = c["raw"][i0:i0 + 6000] - sen
    best = max((pear(resp2(r, fn, z, d), rm), fn, z, d) for fn in range(4000, 20001, 1000)
               for z in (0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0) for d in (-1, -0.5, 0, 0.5, 1))
    print(f"{c['id']}: +600 amostras {c600:.3f} (lag {lag}); + 2.a ordem {best[0]:.3f} (fn {best[1]} Hz, zeta {best[2]}, atraso {best[3]:+.1f})")
