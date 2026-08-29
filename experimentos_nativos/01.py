"""Classe 01: NORMAL — senoide limpa, sem distúrbio."""

import numpy as np

from mestre import ExperimentoNativo


class Experimento(ExperimentoNativo):
    id = "01"
    nome = "NORMAL"

    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        return voltage, {}

    def configurar(self, capture_index):
        # Sem distúrbio nenhum: um STEP para o mesmo valor imediato só para gerar
        # o pulso de trigger (Beginning Of Transient) que o osciloscópio aguarda.
        self.fonte.trigger_step(self.config.base_voltage_rms)
        return {}
