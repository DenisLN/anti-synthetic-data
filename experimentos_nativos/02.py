"""Classe 02: SAG (afundamento de tensão) — transiente nativo PULSe."""

import numpy as np

import perfis
from mestre import ExperimentoNativo
from sinais import janela


class Experimento(ExperimentoNativo):
    id = "02"
    nome = "SAG"
    pre_trigger_s = 0.060

    INICIO_S = 0.060
    DURACAO_S = 0.060

    @property
    def NIVEIS(self):
        # Níveis do perfil ativo (logica/perfis.py); literatura = os de sempre.
        return perfis.faixa(self.config, "sag_niveis")

    def gerar(self, t, f0, capture_index, rng):
        sorteio = self.sortear(
            rng, f0, inicio_legado_s=self.INICIO_S, duracao_legada_s=self.DURACAO_S, duracao_variavel=True,
        )
        voltage = np.sin(2.0 * np.pi * f0 * (t + sorteio.deslocamento_s))
        nivel = self.NIVEIS[capture_index % len(self.NIVEIS)]
        voltage[janela(t, sorteio.inicio_s, sorteio.duracao_s)] *= nivel
        return voltage, {"sag_pu": nivel, **sorteio.parametros()}

    def configurar(self, capture_index):
        nivel = self.NIVEIS[capture_index % len(self.NIVEIS)]
        self.fonte.trigger_pulse(nivel * self.config.base_voltage_rms, width_s=self.largura_do_pulso_s(self.DURACAO_S))
        return {"sag_pu": nivel}
