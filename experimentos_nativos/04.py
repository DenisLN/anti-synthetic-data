"""Classe 04: INTERRUPTION (interrupção) — transiente nativo PULSe."""

import numpy as np

from mestre import ExperimentoNativo
from sinais import janela


class Experimento(ExperimentoNativo):
    id = "04"
    nome = "INTERRUPTION"
    pre_trigger_s = 0.060

    INICIO_S = 0.060
    DURACAO_S = 0.060

    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        nivel = float(rng.uniform(0.0, 0.09))
        voltage[janela(t, self.INICIO_S, self.DURACAO_S)] *= nivel
        return voltage, {"interruption_pu": nivel}

    def configurar(self, capture_index):
        # Sem osciloscópio real por captura para gerar o rng "certo", reproduz a
        # mesma semente usada em gerar() para esse capture_index.
        seed = self.config.base_seed + 4_000_000 + capture_index
        nivel = float(np.random.default_rng(seed).uniform(0.0, 0.09))
        self.fonte.trigger_pulse(nivel * self.config.base_voltage_rms, width_s=self.DURACAO_S)
        return {"interruption_pu": nivel}
