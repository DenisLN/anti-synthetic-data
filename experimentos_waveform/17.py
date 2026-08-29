"""Classe 17: NOTCH + OSCILLATORY_TRANSIENT — forma de onda arbitrária."""

import numpy as np

from comum import aplicar_entalhes, executar_classe_waveform, oscilacao_amortecida


def gerar(t, f0, capture_index, rng):
    voltage = np.sin(2.0 * np.pi * f0 * t)
    pulsos = aplicar_entalhes(voltage, t, rng, frequencia_hz=f0, inicio_s=0.060, duracao_s=0.060)
    voltage = voltage + oscilacao_amortecida(t, inicio_s=0.060, duracao_s=0.060, frequencia_hz=300.0)
    return voltage, {"notch_pulses": float(pulsos), "oscillation_hz": 300.0}


def run(fonte, osc, config):
    executar_classe_waveform(config, fonte, osc, "17", "NOTCH_OSCILLATORY_TRANSIENT", gerar)
