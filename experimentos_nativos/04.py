"""Classe 04: INTERRUPTION (interrupção) — transiente nativo PULSe."""

import numpy as np

import sinais
from mestre import ExperimentoNativo
from sinais import janela


class Experimento(ExperimentoNativo):
    id = "04"
    nome = "INTERRUPTION"
    # Parâmetro SORTEADO em gerar(): 3 capturas por padrão na bancada (uma
    # captura mostra uma só realização do sorteio; CHANGELOG/v1.13.md). Não
    # muda o dataset simulado.
    capturas_padrao = 3
    pre_trigger_s = 0.060

    INICIO_S = 0.060
    DURACAO_S = 0.060

    def gerar(self, t, f0, capture_index, rng):
        sorteio = self.sortear(
            rng, f0, inicio_legado_s=self.INICIO_S, duracao_legada_s=self.DURACAO_S, duracao_variavel=True,
        )
        voltage = np.sin(2.0 * np.pi * f0 * (t + sorteio.deslocamento_s))
        simulado = self.osc is None
        total = self.config.capturas(simulado)
        cobertura_ativa = not simulado and self.config.capturas_override is not None
        nivel = sinais.valor_para_captura(rng, 0.0, 0.09, capture_index, total, cobertura_ativa=cobertura_ativa)
        voltage[janela(t, sorteio.inicio_s, sorteio.duracao_s)] *= nivel
        return voltage, {"interruption_pu": nivel, **sorteio.parametros()}

    def configurar(self, capture_index):
        # Sem osciloscópio real por captura para gerar o rng "certo", reproduz a
        # mesma semente usada em gerar() para esse capture_index.
        seed = self.config.base_seed + 4_000_000 + capture_index
        cobertura_ativa = self.config.capturas_override is not None
        total = self.config.capturas(False)
        nivel = sinais.valor_para_captura(
            np.random.default_rng(seed), 0.0, 0.09, capture_index, total, cobertura_ativa=cobertura_ativa,
        )
        self.fonte.trigger_pulse(nivel * self.config.base_voltage_rms, width_s=self.largura_do_pulso_s(self.DURACAO_S))
        return {"interruption_pu": nivel}
