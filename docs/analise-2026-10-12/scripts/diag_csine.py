"""Itens 2 e 3: a CSINe da fonte (classe 05, THD 5 %) e a funcao gerar_csine.

Somente os 3 registros de 07/10 existem para a 05 (um nivel, THD 5 %, por
sessao): os niveis 10/15/20 % nunca foram capturados na bancada.
Uso: python docs/analise-2026-10-12/diag_csine.py
"""
import numpy as np
import diag_comum as D

FS = D.FS


def thd_ciclo(x):
    a = np.abs(np.fft.rfft(x))
    return float(np.sqrt(np.sum(a[2:] ** 2)) / a[1])


def corte_para_thd(thd, n=8192):
    """Nivel de corte c (pu do pico da senoide) tal que clip(sin,-c,c) tem a THD pedida."""
    th = np.sin(2 * np.pi * np.arange(n) / n)
    lo, hi = 0.05, 1.0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if thd_ciclo(np.clip(th, -m, m)) > thd else (lo, m)
    return 0.5 * (lo + hi)


def gerar_csine(t, f0, thd, fase_graus=0.0, normalizacao="rms"):
    """Senoide grampeada simetricamente (clip duro) cujo THD e 'thd' (fracao).
    normalizacao='rms': escala para o rms da senoide de pico 1 (1/sqrt 2);
    'pico': nao escala (pico = nivel de corte c, em pu do pico nominal)."""
    c = corte_para_thd(thd)
    x = np.clip(np.sin(2 * np.pi * f0 * t + np.radians(fase_graus)), -c, c)
    if normalizacao == "rms":
        ciclo = np.clip(np.sin(2 * np.pi * np.arange(8192) / 8192), -c, c)
        x = x / (np.sqrt(2) * np.sqrt(np.mean(ciclo ** 2)))
    return x


def ciclo_medio(x, f0):
    n = int(round(FS / f0)); k = len(x) // n
    return x[:k * n].reshape(k, n), n


def spec(c):
    F = np.fft.rfft(c) / len(c) * 2
    return np.abs(F), np.angle(F)


def principal():
    print("== corte c para cada THD (hard clip simetrico, rms/pico):")
    for thd in (0.05, 0.10, 0.15, 0.20, 0.30):
        try:
            c = corte_para_thd(thd)
        except Exception as e:
            c = float('nan')
        th = np.clip(np.sin(2 * np.pi * np.arange(8192) / 8192), -c, c)
        s = np.abs(np.fft.rfft(th)); s = s / s[1]
        print(f"  THD {thd:4.2f}: c={c:.4f}  h3={s[3]:.4f} h5={s[5]:.4f} h7={s[7]:.4f} h9={s[9]:.4f} rms/rms_senoide={np.sqrt(np.mean(th**2))*np.sqrt(2):.4f}")

    for rot in D.SESSOES:
        cap = D.capturas(rot, {"05", "01"})
        um = {c["classe"]: c for c in cap}
        c5, c1 = um["05"], um["01"]
        f0 = c5["f0"]
        print(f"\n===== {rot} (f0={f0:g} Hz, THD pedido {c5['parametros']['thd']})")
        m5 = c5["medida"]; m1 = c1["medida"]
        print(f"rms medido 05 {m5.std():.4f}  01 {m1.std():.4f}  razao {m5.std() / m1.std():.4f} ; pico 05 {m5.max():.4f}/{m5.min():.4f}  01 {m1.max():.4f}/{m1.min():.4f}")
        print(f"rms programada 05 {c5['programada'].std():.4f} ; pico {c5['programada'].max():.4f}")
        cy, n = ciclo_medio(m5, f0)
        med = cy.mean(0)
        ruido = (cy - med).std()
        print(f"ciclos {cy.shape[0]} x {n}; ruido ciclo-a-ciclo (rms) {ruido:.4f} pu ; rms do residuo harmonico medio {np.std(med - np.sin(2*np.pi*np.arange(n)/n)*np.abs(spec(med)[0][1])):.4f}")
        A, P = spec(med)
        print(f"THD medido (ciclo medio) {thd_ciclo(med):.4f}; fundamental {A[1]:.4f} pu; DC {A[0]/2:.4f}")
        # hard clip de referencia no mesmo THD, mesma fase da fundamental
        c = corte_para_thd(c5["parametros"]["thd"])
        th = np.arange(n) / n * 2 * np.pi
        hc = np.clip(np.sin(th), -c, c)
        Ah, Ph = spec(hc)
        print("h   amp/h1 medida  amp/h1 hard-clip  fase_rel medida(graus)  fase_rel hard-clip   [fase_rel = fase_h - h*fase_1]")
        for h in range(2, 16):
            fm = np.degrees((P[h] - h * P[1] + np.pi) % (2 * np.pi) - np.pi)
            fh = np.degrees((Ph[h] - h * Ph[1] + np.pi) % (2 * np.pi) - np.pi)
            print(f"{h:2d}  {A[h]/A[1]:12.5f}  {Ah[h]/Ah[1]:14.5f}  {fm:20.1f}  {fh:18.1f}")
        # ajuste livre: s*clip(sin(th+phi), -c, c) + dc ; c por grade, s por MQ
        melhor = None
        for cc in np.arange(0.70, 1.0001, 0.0025):
            for phi in [P[1] + np.pi / 2 + d for d in np.radians(np.arange(-2, 2.01, 0.25))]:
                g = np.clip(np.sin(th + phi), -cc, cc)
                s = float(g @ (med - med.mean()) / (g @ g))
                err = float(np.std(med - s * g - (med - s * g).mean()))
                if melhor is None or err < melhor[0]:
                    melhor = (err, cc, s, phi)
        err, cc, s, phi = melhor
        print(f"AJUSTE LIVRE s*clip(sin(th+phi),+-c): c={cc:.4f} (c do THD pedido {c:.4f}), s={s:.4f}, rms erro {err:.4f} pu (ruido {ruido:.4f}); THD do ajuste {thd_ciclo(np.clip(np.sin(th), -cc, cc)):.4f}")
        # correlacoes do disturbio contra a medida
        f0 = c5["f0"]; raw = c5["raw"]; ini = c5["ini"]
        t = np.arange(6000) / FS
        cand = {
            "modelo atual (3a/5a/7a)": c5["modelo"],
            "gerar_csine rms (=sinais.senoide_clipada_pu)": gerar_csine(t, f0, 0.05, 0.0, "rms"),
            "gerar_csine pico (sem escala)": gerar_csine(t, f0, 0.05, 0.0, "pico"),
            "ajuste livre (s,c) [teto]": s * np.clip(np.sin(2*np.pi*f0*t + phi), -cc, cc),
        }
        print(f"{'candidato':48s} {'corr_dist':>9s} {'lag':>4s} {'melhor':>7s} {'lag':>4s}  pico")
        for nome, x in cand.items():
            lag, _ = D.AS.analisar_offset(x, c5["medida"], FS)
            cd = D.corr_dist(x, raw, ini, lag, f0)
            lo, co = D.melhor_lag(x, raw, ini, f0, 40)
            print(f"{nome:48s} {cd:9.3f} {lag:4d} {co:7.3f} {lo:4d}  {np.abs(x).max():.4f}")


if __name__ == "__main__":
    principal()
