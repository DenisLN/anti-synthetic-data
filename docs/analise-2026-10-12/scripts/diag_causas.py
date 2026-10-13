"""Item 1: separa as causas da perda de correlacao do disturbio por captura.

Colunas (todas = correlacao so do disturbio, sinais.correlacao_disturbio):
  mod_med   modelo(gerar) x medida, lag de analisar_offset  (= analisar_sessao)
  ban_med   forma de bancada (modelo com k/limite de pico) x medida
  prog_med  programada (TRACe 1024 pts / nativa) x medida, mesmo metodo de lag
  prog_opt  idem com o lag que maximiza a correlacao (+-80 amostras)  -> alinhamento
  mod_ban   modelo x forma de bancada (efeito do fator k / limite de pico)
  ban_prog  forma de bancada x programada (efeito da reamostragem a 1024 pts)
  mod_prog  modelo x programada (efeito total do lado da bancada, sem fonte)
Uso: python docs/analise-2026-10-12/diag_causas.py [classes...]
"""
import sys
import numpy as np
import diag_comum as D

classes = set(sys.argv[1:]) or {"03", "05", "07", "08", "09", "17"}


def par(a, b, f0):
    v, _ = D.sinais.correlacao_disturbio(a, b, fs_hz=D.FS, f0_hz=f0)
    return v


def f(x):
    return "  n/a" if x is None else f"{x:6.3f}"


print(f"{'sessao':10s} {'id':8s} {'mod_med':>7s} {'ban_med':>7s} {'prog_med':>8s} {'prog_opt':>8s} {'lag_opt':>7s} {'lag_ao':>6s} {'mod_ban':>7s} {'ban_prog':>8s} {'mod_prog':>8s}  parametros")
for rot in D.SESSOES:
    for c in D.capturas(rot, classes):
        f0, raw, ini = c["f0"], c["raw"], c["ini"]
        out = []
        lags = {}
        for nome in ("modelo", "bancada", "programada"):
            lag, _ = D.AS.analisar_offset(c[nome], c["medida"], D.FS)
            lags[nome] = lag
            out.append(D.corr_dist(c[nome], raw, ini, lag, f0))
        lo, co = D.melhor_lag(c["programada"], raw, ini, f0)
        print(f"{rot:10s} {c['id']:8s} {f(out[0])} {f(out[1])} {f(out[2]):>8s} {f(co):>8s} {lo:7d} {lags['programada']:6d} "
              f"{f(par(c['modelo'], c['bancada'], f0))} {f(par(c['bancada'], c['programada'], f0)):>8s} {f(par(c['modelo'], c['programada'], f0)):>8s}  "
              f"{ {k: round(v, 4) if isinstance(v, float) else v for k, v in c['parametros'].items() if k != 'caracterizacao'} }")
