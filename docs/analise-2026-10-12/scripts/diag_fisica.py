"""Item 1 (cont.): quanto da perda 'programada x medida' e cada efeito fisico.

Todas as correlacoes sao a do DISTURBIO (sinais.correlacao_disturbio), a
programada contra a medida, janela alinhada pelo lag que maximiza c0.
  c0       valor atual
  c_frac   com atraso sub-amostra da programada (-1..+1 amostra, passo 0,05)
  c_filtro com um polo (passa-baixa de 1.a ordem, tau 0..4 amostras) + atraso
           sub-amostra: modelo de resposta da fonte (largura de banda)
  c_fund   removendo de cada sinal a sua fundamental+DC ajustada (erro de
           amplitude/fase da fundamental da fonte)
  c_borda  erro zerado a +-1,5 ms de onde |diff(programada)| > 10 % do maximo
  borda%   % da energia do erro dentro dessas janelas; amp_m/p = amplitude da
           fundamental medida / programada (ajuste por minimos quadrados)
  c_semesp so 09: zerando o erro em 99..102 ms (impulso espurio, ver
           diag_picos_espurios.py); c_fund+esp: fundamental removida E erro
           zerado em 99..102 ms
  piso     rms de (medida - programada) nos primeiros 56 ms da PROPRIA captura,
           antes de qualquer evento (ruido do osciloscopio + ondulacao repetivel);
           na 05 (distorcao em toda a janela) usa a janela inteira, o que
           inclui o erro do modelo, entao o piso fica alto e o teto, baixo
  teto     sqrt(var_dist/(var_dist+piso^2)): correlacao maxima esperada se a
           programada fosse perfeita e so o piso atrapalhasse
  fe_*     % da energia do erro (medida - g*programada) por faixa de frequencia
Uso: python docs/analise-2026-10-12/diag_fisica.py [classes...]
"""
import sys
import numpy as np
import diag_comum as D

classes = set(sys.argv[1:]) or {"03", "05", "07", "08", "09", "17"}
FS = D.FS


def pear(a, b):
    a = a - a.mean(); b = b - b.mean()
    return float(a @ b / np.sqrt((a @ a) * (b @ b)))


def fit_fund(x, f0):
    t = np.arange(len(x)) / FS
    A = np.column_stack([np.sin(2 * np.pi * f0 * t), np.cos(2 * np.pi * f0 * t), np.ones_like(t)])
    coef, *_ = np.linalg.lstsq(A, x, rcond=None)
    return A @ coef


def resposta(x, atraso, tau):
    """Atraso (amostras, fracionario) e polo de 1.a ordem (tau em amostras), via FFT com zero-padding."""
    n = len(x); m = 2 * n
    X = np.fft.rfft(x, m)
    w = 2 * np.pi * np.fft.rfftfreq(m)  # rad/amostra
    H = np.exp(-1j * w * atraso) / (1 + 1j * w * tau)
    return np.fft.irfft(X * H, m)[:n]


def banda(x, f1, f2):
    X = np.fft.rfft(x); fr = np.fft.rfftfreq(len(x), 1 / FS)
    X[(fr < f1) | (fr > f2)] = 0
    return np.fft.irfft(X, len(x))


print(f"{'sessao':10s} {'id':8s} {'c0':>6s} {'c_frac':>6s} {'c_filtro':>8s} {'(tau,atr)':>11s} {'c_fund':>6s} {'c_borda':>7s} {'borda%':>6s} {'amp_m/p':>7s} {'c_semesp':>8s} {'c_fund+esp':>10s} {'teto':>5s} {'piso':>6s} | fe <1k 1-5k 5-8.5k >8.5k")
for rot in D.SESSOES:
    base = D.capturas(rot, {"01"})[0]
    f0 = base["f0"]
    n_ciclo = int(round(FS / f0)); K = 6000 // n_ciclo
    for c in D.capturas(rot, classes):
        n = 6000
        lag, c0 = D.melhor_lag(c["programada"], c["raw"], c["ini"], f0)
        i0 = max(0, min(c["ini"] + lag, c["raw"].size - n))
        t = np.arange(n) / FS
        sen = np.sin(2 * np.pi * f0 * t)
        rp = c["programada"] - sen; rm = c["raw"][i0:i0 + n] - sen
        rp = rp - rp.mean(); rm = rm - rm.mean()
        c_frac = max(pear(resposta(rp, d, 0.0), rm) for d in np.arange(-1, 1.001, 0.05))
        melhor = (-2, 0, 0)
        for tau in np.arange(0, 4.01, 0.25):
            for d in np.arange(-1, 1.001, 0.1):
                v = pear(resposta(rp, d, tau), rm)
                if v > melhor[0]:
                    melhor = (v, tau, d)
        dp = c["programada"] - fit_fund(c["programada"], f0)
        dm = c["raw"][i0:i0 + n] - fit_fund(c["raw"][i0:i0 + n], f0)
        c_fund = pear(dp, dm)
        c_sem = c_amb = float("nan")
        if c["classe"] == "09":
            m = np.zeros(n, bool); m[int(99 * 30):int(102 * 30)] = True
            g = float(rp @ rm / (rp @ rp)); e = rm - g * rp
            c_sem = pear(rp, rm - e * m)
            dpc, dmc = dp - dp.mean(), dm - dm.mean()
            g2 = float(dpc @ dmc / (dpc @ dpc)); e2 = dmc - g2 * dpc
            c_amb = pear(dpc, dmc - e2 * m)
        gb = float(rp @ rm / (rp @ rp)); eb = rm - gb * rp
        d_ = np.abs(np.diff(rp, prepend=rp[0])); borda = np.zeros(n, bool)
        for i in np.where(d_ > 0.10 * d_.max())[0]:
            borda[max(0, i - 45):i + 46] = True
        c_borda = pear(rp, rm - eb * borda)
        pb = float(eb[borda] @ eb[borda] / (eb @ eb) * 100)  # % da energia do erro perto de bordas
        def amp(x):
            A = np.column_stack([np.sin(2 * np.pi * f0 * t), np.cos(2 * np.pi * f0 * t)])
            return float(np.hypot(*np.linalg.lstsq(A, x - x.mean(), rcond=None)[0]))
        razao_fund = amp(c["raw"][i0:i0 + n]) / amp(c["programada"])
        sd = rp.std()
        quieto = slice(0, 1700) if c["classe"] != "05" else slice(0, 6000)  # antes de qualquer evento (<= 56 ms)
        piso = float((rm[quieto] - rp[quieto]).std())  # ruido + ondulacao repetivel, medido na propria captura
        teto = np.sqrt(sd ** 2 / (sd ** 2 + piso ** 2)); teto1 = piso
        g = float(rp @ rm / (rp @ rp)); e = rm - g * rp; tot = e @ e
        fe = [float(banda(e, a, b) @ banda(e, a, b)) / tot * 100 for a, b in ((0, 1000), (1000, 5000), (5000, 8500), (8500, 15001))]
        print(f"{rot:10s} {c['id']:8s} {c0:6.3f} {c_frac:6.3f} {melhor[0]:8.3f} {melhor[1]:5.2f},{melhor[2]:+5.1f} {c_fund:6.3f} {c_borda:7.3f} {pb:6.0f} {razao_fund:7.4f} {c_sem:8.3f} {c_amb:10.3f} {teto:5.3f} {teto1:6.4f} | " + " ".join(f"{x:4.0f}" for x in fe))
