"""Classe 07: NOTCH (entalhe) — forma de onda arbitrária."""

import numpy as np

from mestre import ExperimentoWaveform
from sinais import aplicar_entalhes


class Experimento(ExperimentoWaveform):
    id = "07"
    nome = "NOTCH"

    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        pulsos = aplicar_entalhes(voltage, t, rng, frequencia_hz=f0)
        return voltage, {"notch_pulses": float(pulsos)}
