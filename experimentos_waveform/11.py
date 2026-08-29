"""Classe 11: SAG + FLICKER — forma de onda arbitrária."""

import numpy as np

from comum import executar_classe_waveform, janela


def gerar(t, f0, capture_index, rng):
    voltage = np.sin(2.0 * np.pi * f0 * t)
    mask = janela(t, 0.060, 0.060)
    voltage[mask] *= 0.5 * (1.0 + 0.10 * np.sin(2.0 * np.pi * 15.0 * t[mask]))
    return voltage, {"sag_pu": 0.5, "flicker_hz": 15.0, "flicker_depth": 0.10}


def run(fonte, osc, config):
    executar_classe_waveform(config, fonte, osc, "11", "SAG_FLICKER", gerar)
