"""Classe 07: NOTCH (entalhe) — forma de onda arbitrária."""

import numpy as np

from comum import aplicar_entalhes, executar_classe_waveform


def gerar(t, f0, capture_index, rng):
    voltage = np.sin(2.0 * np.pi * f0 * t)
    pulsos = aplicar_entalhes(voltage, t, rng, frequencia_hz=f0)
    return voltage, {"notch_pulses": float(pulsos)}


def run(fonte, osc, config):
    executar_classe_waveform(config, fonte, osc, "07", "NOTCH", gerar)
