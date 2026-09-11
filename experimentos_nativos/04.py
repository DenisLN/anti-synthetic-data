"""Classe 04: INTERRUPTION (interrupção) — transiente nativo PULSe."""

import numpy as np

import sinais
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
        simulado = self.osc is None
        total = self.config.capturas(simulado)
        cobertura_ativa = not simulado and self.config.capturas_override is not None
        nivel = sinais.valor_para_captura(rng, 0.0, 0.09, capture_index, total, cobertura_ativa=cobertura_ativa)
        voltage[janela(t, self.INICIO_S, self.DURACAO_S)] *= nivel
        return voltage, {"interruption_pu": nivel}

    def configurar(self, capture_index):
        # Sem osciloscópio real por captura para gerar o rng "certo", reproduz a
        # mesma semente usada em gerar() para esse capture_index.
        seed = self.config.base_seed + 4_000_000 + capture_index
        cobertura_ativa = self.config.capturas_override is not None
        total = self.config.capturas(False)
        nivel = sinais.valor_para_captura(
            np.random.default_rng(seed), 0.0, 0.09, capture_index, total, cobertura_ativa=cobertura_ativa,
        )
        self.fonte.trigger_pulse(nivel * self.config.base_voltage_rms, width_s=self.DURACAO_S)
        return {"interruption_pu": nivel}
