"""Classe 10: SAG + HARMONICS — forma de onda arbitrária.

Candidata a virar nativa (LIST:VOLTage + LIST:FUNCtion:SHAPe sincronizados,
SIN/CSIN por passo) — validar na bancada; por ora fica em TRACe, garantido
de funcionar.
"""

import numpy as np

from comum import executar_classe_waveform, janela, onda_com_harmonicos


def gerar(t, f0, capture_index, rng):
    voltage = np.sin(2.0 * np.pi * f0 * t)
    mask = janela(t, 0.060, 0.060)
    voltage[mask] = 0.5 * onda_com_harmonicos(t[mask], 0.20, frequencia_hz=f0)
    return voltage, {"sag_pu": 0.5, "thd": 0.20}


def run(fonte, osc, config):
    executar_classe_waveform(config, fonte, osc, "10", "SAG_HARMONICS", gerar)
