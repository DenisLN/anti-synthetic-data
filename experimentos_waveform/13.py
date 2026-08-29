"""Classe 13: SWELL + HARMONICS — forma de onda arbitrária.

Candidata a virar nativa (LIST:VOLTage + LIST:FUNCtion:SHAPe sincronizados) —
validar na bancada; por ora fica em TRACe, garantido de funcionar.
"""

import numpy as np

from mestre import ExperimentoWaveform
from sinais import janela, onda_com_harmonicos


class Experimento(ExperimentoWaveform):
    id = "13"
    nome = "SWELL_HARMONICS"

    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        mask = janela(t, 0.060, 0.060)
        voltage[mask] = 1.3 * onda_com_harmonicos(t[mask], 0.20, frequencia_hz=f0)
        return voltage, {"swell_pu": 1.3, "thd": 0.20}
