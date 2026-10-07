"""Classe 11: SAG + FLICKER — forma de onda arbitrária."""

import numpy as np

from mestre import ExperimentoWaveform
from sinais import janela


class Experimento(ExperimentoWaveform):
    id = "11"
    nome = "SAG_FLICKER"

    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        mask = janela(t, 0.060, 0.060)
        voltage[mask] *= 0.5 * (1.0 + 0.10 * np.sin(2.0 * np.pi * 15.0 * t[mask]))
        return voltage, {"sag_pu": 0.5, "flicker_hz": 15.0, "flicker_depth": 0.10}

    def parametros_com_disturbio_reduzido(self, parametros, fracao):
        # Gancho de bancada (limite de bancada, v1.13): forma física =
        # senoide + fracao x (gerar() - senoide). gerar() não muda.
        nivel = 1.0 + fracao * (parametros["sag_pu"] - 1.0)
        return {
            "sag_pu_bancada": nivel,
            "flicker_depth_bancada": fracao * parametros["sag_pu"] * parametros["flicker_depth"] / nivel,
        }
