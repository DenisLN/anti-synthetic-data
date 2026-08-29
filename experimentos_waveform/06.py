"""Classe 06: FLICKER — modulação de amplitude contínua, forma de onda arbitrária."""

import numpy as np

from comum import executar_classe_waveform


def gerar(t, f0, capture_index, rng):
    flicker_hz = float(rng.uniform(8.0, 25.0))
    profundidade = float(rng.uniform(0.05, 0.15))
    voltage = np.sin(2.0 * np.pi * f0 * t) * (1.0 + profundidade * np.sin(2.0 * np.pi * flicker_hz * t))
    return voltage, {"flicker_hz": flicker_hz, "flicker_depth": profundidade}


def run(fonte, osc, config):
    executar_classe_waveform(config, fonte, osc, "06", "FLICKER", gerar)
