"""Classe 14: SWELL + OSCILLATORY_TRANSIENT — forma de onda arbitrária."""

import inspect

import numpy as np

from mestre import ExperimentoWaveform
from sinais import janela, oscilacao_amortecida


class Experimento(ExperimentoWaveform):
    id = "14"
    nome = "SWELL_OSCILLATORY_TRANSIENT"

    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        mask = janela(t, 0.060, 0.040)
        voltage[mask] *= 1.3
        voltage = voltage + oscilacao_amortecida(t, inicio_s=0.060, duracao_s=0.040, frequencia_hz=600.0)
        return voltage, {"swell_pu": 1.3, "oscillation_hz": 600.0}

    def parametros_com_disturbio_reduzido(self, parametros, fracao):
        # Gancho de bancada (limite de bancada, v1.13): forma física =
        # senoide + fracao x (gerar() - senoide). gerar() não muda.
        amplitude = inspect.signature(oscilacao_amortecida).parameters["amplitude_pu"].default
        return {
            "swell_pu_bancada": 1.0 + fracao * (parametros["swell_pu"] - 1.0),
            "oscillation_amplitude_pu_bancada": fracao * amplitude,
        }
