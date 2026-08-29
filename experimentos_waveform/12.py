"""Classe 12: SAG + OSCILLATORY_TRANSIENT — forma de onda arbitrária."""

import numpy as np

from mestre import ExperimentoWaveform
from sinais import janela, oscilacao_amortecida


class Experimento(ExperimentoWaveform):
    id = "12"
    nome = "SAG_OSCILLATORY_TRANSIENT"

    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        mask = janela(t, 0.060, 0.040)
        voltage[mask] *= 0.5
        voltage = voltage + oscilacao_amortecida(t, inicio_s=0.060, duracao_s=0.040, frequencia_hz=600.0)
        return voltage, {"sag_pu": 0.5, "oscillation_hz": 600.0}
