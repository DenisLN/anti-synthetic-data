"""Classe 15: HARMONICS + FLICKER — forma de onda arbitrária, os 200 ms inteiros."""

import numpy as np

from comum import executar_classe_waveform, onda_com_harmonicos


def gerar(t, f0, capture_index, rng):
    flicker = 1.0 + 0.10 * np.sin(2.0 * np.pi * 15.0 * t)
    voltage = flicker * onda_com_harmonicos(t, 0.20, frequencia_hz=f0)
    return voltage, {"thd": 0.20, "flicker_hz": 15.0, "flicker_depth": 0.10}


def run(fonte, osc, config):
    executar_classe_waveform(config, fonte, osc, "15", "HARMONICS_FLICKER", gerar)
