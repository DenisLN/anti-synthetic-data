"""Classe 12: SAG + OSCILLATORY_TRANSIENT — forma de onda arbitrária."""

import numpy as np

from comum import executar_classe_waveform, janela, oscilacao_amortecida


def gerar(t, f0, capture_index, rng):
    voltage = np.sin(2.0 * np.pi * f0 * t)
    mask = janela(t, 0.060, 0.040)
    voltage[mask] *= 0.5
    voltage = voltage + oscilacao_amortecida(t, inicio_s=0.060, duracao_s=0.040, frequencia_hz=600.0)
    return voltage, {"sag_pu": 0.5, "oscillation_hz": 600.0}


def run(fonte, osc, config):
    executar_classe_waveform(config, fonte, osc, "12", "SAG_OSCILLATORY_TRANSIENT", gerar)
