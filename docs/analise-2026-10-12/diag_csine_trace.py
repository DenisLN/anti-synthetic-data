"""Item 3 (cont.): CSINe no modelo x todos os niveis por TRACE.

Para THD 5/10/15/20/30 %:
  mod_hc      correlacao do disturbio entre o modelo atual (3.a/5.a/7.a, 05.py)
              e o grampeamento duro (gerar_csine) -> quanto o modelo difere da CSINe
  conv_mod    modelo atual -> TRACE de 1024 pontos (montar_programacao) -> grade
              de 30 kSa/s: perda so da conversao
  conv_hc     idem para gerar_csine (se a CSINe fosse mandada por TRACE)
  pico_*      pico da forma programada (pu): tem de caber em max_peak_v (425 V)
Uso: python docs/analise-2026-10-12/diag_csine_trace.py
"""
import numpy as np
import diag_comum as D
from ametek_orm import AmetekMX30
from diag_csine import gerar_csine

FS = D.FS
t = np.arange(6000) / FS


def modelo_atual(f0, thd):
    r = np.array([0.60, 0.30, 0.10]); k = thd * r / np.linalg.norm(r); w = 2 * np.pi * f0
    return np.sin(w * t) + k[0] * np.sin(3 * w * t) + k[1] * np.sin(5 * w * t) + k[2] * np.sin(7 * w * t)


def corr(a, b, f0):
    return D.sinais.correlacao_disturbio(a, b, fs_hz=FS, f0_hz=f0)[0]


print(f"{'f0':>3s} {'THD':>4s} {'mod_hc':>6s} {'conv_mod':>8s} {'conv_hc':>7s} {'pico_mod':>8s} {'pico_hc_rms':>11s}")
for f0 in (50.0, 60.0):
    for thd in (0.05, 0.10, 0.15, 0.20, 0.30):
        m = modelo_atual(f0, thd)
        h = gerar_csine(t, f0, thd, 0.0, "rms")
        pm = AmetekMX30.montar_programacao(m, base_voltage_rms=127.0, frequency_hz=f0).programada_pu()
        ph = AmetekMX30.montar_programacao(h, base_voltage_rms=127.0, frequency_hz=f0).programada_pu()
        print(f"{f0:3.0f} {thd:4.2f} {corr(m, h, f0):6.3f} {corr(m, pm, f0):8.4f} {corr(h, ph, f0):7.4f} {np.abs(pm).max():8.3f} {np.abs(ph).max():11.3f}")
