"""Classe 09: OSCILLATORY_TRANSIENT (transitório oscilatório) — forma de onda arbitrária."""

import numpy as np

from mestre import ExperimentoWaveform
from sinais import oscilacao_amortecida


class Experimento(ExperimentoWaveform):
    id = "09"
    nome = "OSCILLATORY_TRANSIENT"

    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        frequencia = float(rng.uniform(300.0, 2400.0))
        duracao = float(rng.uniform(0.010, 0.040))
        voltage = voltage + oscilacao_amortecida(
            t, inicio_s=0.080, duracao_s=duracao, frequencia_hz=frequencia,
        )
        return voltage, {"oscillation_hz": frequencia, "duration_s": duracao}
