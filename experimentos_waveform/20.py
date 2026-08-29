"""Classe 20: INTER-HARMÔNICAS — forma de onda arbitrária."""

import numpy as np

from mestre import ExperimentoWaveform

# 150 Hz foi removido: em uma rede de 60 Hz ele seria a 2,5a harmônica, muito
# próximo de uma harmônica real; usamos 145/210/330 Hz (não múltiplos inteiros
# da fundamental).
FREQUENCIAS = (145.0, 210.0, 330.0)


class Experimento(ExperimentoWaveform):
    id = "20"
    nome = "INTERHARMONICS"

    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        amplitudes = rng.uniform(0.03, 0.08, size=3)
        for amplitude, frequencia in zip(amplitudes, FREQUENCIAS):
            voltage = voltage + amplitude * np.sin(2.0 * np.pi * frequencia * t + rng.uniform(0.0, 2.0 * np.pi))
        return voltage, {
            "interharmonic_145_pu": float(amplitudes[0]),
            "interharmonic_210_pu": float(amplitudes[1]),
            "interharmonic_330_pu": float(amplitudes[2]),
        }
