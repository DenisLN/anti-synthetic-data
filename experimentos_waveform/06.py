"""Classe 06: FLICKER — modulação de amplitude contínua, forma de onda arbitrária."""

import numpy as np

import sinais
from mestre import ExperimentoWaveform


class Experimento(ExperimentoWaveform):
    id = "06"
    nome = "FLICKER"
    # Parâmetro SORTEADO em gerar(): 3 capturas por padrão na bancada (pedido
    # do dono, 2026-10-07; CHANGELOG/v1.13.md). Não muda o dataset simulado.
    capturas_padrao = 3

    def gerar(self, t, f0, capture_index, rng):
        simulado = self.osc is None
        total = self.config.capturas(simulado)
        cobertura_ativa = not simulado and self.config.capturas_override is not None
        flicker_hz = sinais.valor_para_captura(rng, 8.0, 25.0, capture_index, total, cobertura_ativa=cobertura_ativa)
        profundidade = float(rng.uniform(0.05, 0.15))
        voltage = np.sin(2.0 * np.pi * f0 * t) * (1.0 + profundidade * np.sin(2.0 * np.pi * flicker_hz * t))
        return voltage, {"flicker_hz": flicker_hz, "flicker_depth": profundidade}
