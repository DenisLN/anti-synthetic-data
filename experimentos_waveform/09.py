"""Classe 09: OSCILLATORY_TRANSIENT (transitório oscilatório) — forma de onda arbitrária."""

import numpy as np

import sinais
from mestre import ExperimentoWaveform
from sinais import oscilacao_amortecida


class Experimento(ExperimentoWaveform):
    id = "09"
    nome = "OSCILLATORY_TRANSIENT"
    # Parâmetro SORTEADO em gerar(): 3 capturas por padrão na bancada (pedido
    # do dono, 2026-10-07; CHANGELOG/v1.13.md). Não muda o dataset simulado.
    capturas_padrao = 3

    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        simulado = self.osc is None
        total = self.config.capturas(simulado)
        cobertura_ativa = not simulado and self.config.capturas_override is not None
        frequencia = sinais.valor_para_captura(rng, 300.0, 2400.0, capture_index, total, cobertura_ativa=cobertura_ativa)
        duracao = float(rng.uniform(0.010, 0.040))
        voltage = voltage + oscilacao_amortecida(
            t, inicio_s=0.080, duracao_s=duracao, frequencia_hz=frequencia,
        )
        return voltage, {"oscillation_hz": frequencia, "duration_s": duracao}
