"""Classe 03: SWELL (elevação de tensão) — transiente nativo PULSe."""

import numpy as np

from mestre import ExperimentoNativo
from sinais import janela


class Experimento(ExperimentoNativo):
    id = "03"
    nome = "SWELL"
    pre_trigger_s = 0.060

    NIVEIS = (1.1, 1.2, 1.4, 1.6, 1.8)
    INICIO_S = 0.060
    DURACAO_S = 0.060

    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        nivel = self.NIVEIS[capture_index % len(self.NIVEIS)]
        voltage[janela(t, self.INICIO_S, self.DURACAO_S)] *= nivel
        return voltage, {"swell_pu": nivel}

    def configurar(self, capture_index):
        nivel = self.NIVEIS[capture_index % len(self.NIVEIS)]
        self.fonte.trigger_pulse(nivel * self.config.base_voltage_rms, width_s=self.DURACAO_S)
        return {"swell_pu": nivel}
