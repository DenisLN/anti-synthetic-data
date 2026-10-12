"""Item 1 (cont.): a resposta da fonte e um sistema linear?

Ajusta, por captura, um filtro LINEAR de 2.a ordem (frequencia natural fn,
amortecimento zeta) + atraso sub-amostra aplicado a forma PROGRAMADA e
reporta a correlacao do disturbio contra a medida (c_2a) ao lado da atual (c0).
Se c_2a sobe, a perda e a resposta (toque) da fonte e nao o modelo/TRACE.
Grade: fn 4..30 kHz (passo 1 k), zeta {0,05..1}, atraso {-1,-0,5,0,0,5,1} amostras.
Uso: python docs/analise-2026-10-12/diag_resposta_fonte.py [classes...]
"""
import sys
import numpy as np
import diag_comum as D

FS = D.FS


def pear(a, b):
    a = a - a.mean(); b = b - b.mean()
    return float(a @ b / np.sqrt((a @ a) * (b @ b)))


def resp2(x, fn, z, d):
    n = len(x); m = 2 * n
    X = np.fft.rfft(x, m); f = np.fft.rfftfreq(m, 1 / FS)
    s = 1j * f / fn
    H = np.exp(-1j * 2 * np.pi * f / FS * d) / (1 + 2 * z * s + s * s)
    return np.fft.irfft(X * H, m)[:n]


def principal():
    classes = set(sys.argv[1:]) or {"03", "07", "08", "09", "17"}
    print(f"{'sessao':10s} {'id':8s} {'c0':>6s} {'c_2a':>6s} {'fn_Hz':>6s} {'zeta':>5s} {'atraso':>6s}")
    for rot in D.SESSOES:
        for c in D.capturas(rot, classes):
            lag, c0 = D.melhor_lag(c["programada"], c["raw"], c["ini"], c["f0"], 80)
            i0 = c["ini"] + lag; n = 6000
            sen = np.sin(2 * np.pi * c["f0"] * np.arange(n) / FS)
            rp = c["programada"] - sen; rm = c["raw"][i0:i0 + n] - sen
            best = (-1, 0, 0, 0)
            for fn in range(4000, 30001, 1000):
                for z in (0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0):
                    for d in (-1, -0.5, 0, 0.5, 1):
                        v = pear(resp2(rp, fn, z, d), rm)
                        if v > best[0]:
                            best = (v, fn, z, d)
            print(f"{rot:10s} {c['id']:8s} {c0:6.3f} {best[0]:6.3f} {best[1]:6d} {best[2]:5.2f} {best[3]:+6.1f}", flush=True)


if __name__ == "__main__":
    principal()
