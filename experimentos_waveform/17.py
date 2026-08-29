"""Classe 17: NOTCH + OSCILLATORY_TRANSIENT — forma de onda arbitrária."""

import numpy as np

from mestre import ExperimentoWaveform
from sinais import aplicar_entalhes, oscilacao_amortecida


class Experimento(ExperimentoWaveform):
    id = "17"
    nome = "NOTCH_OSCILLATORY_TRANSIENT"

    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        pulsos = aplicar_entalhes(voltage, t, rng, frequencia_hz=f0, inicio_s=0.060, duracao_s=0.060)
        voltage = voltage + oscilacao_amortecida(t, inicio_s=0.060, duracao_s=0.060, frequencia_hz=300.0)
        return voltage, {"notch_pulses": float(pulsos), "oscillation_hz": 300.0}
