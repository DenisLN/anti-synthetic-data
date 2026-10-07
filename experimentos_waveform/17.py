"""Classe 17: NOTCH + OSCILLATORY_TRANSIENT — forma de onda arbitrária."""

import inspect

import numpy as np

from mestre import ExperimentoWaveform
from sinais import aplicar_entalhes, oscilacao_amortecida


class Experimento(ExperimentoWaveform):
    id = "17"
    nome = "NOTCH_OSCILLATORY_TRANSIENT"
    # Parâmetro SORTEADO em gerar(): 3 capturas por padrão na bancada (pedido
    # do dono, 2026-10-07; CHANGELOG/v1.13.md). Não muda o dataset simulado.
    capturas_padrao = 3

    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        pulsos = aplicar_entalhes(voltage, t, rng, frequencia_hz=f0, inicio_s=0.060, duracao_s=0.060)
        voltage = voltage + oscilacao_amortecida(t, inicio_s=0.060, duracao_s=0.060, frequencia_hz=300.0)
        return voltage, {"notch_pulses": float(pulsos), "oscillation_hz": 300.0}

    def parametros_com_disturbio_reduzido(self, parametros, fracao):
        # Gancho de bancada (limite de bancada, v1.13): forma física =
        # senoide + fracao x (gerar() - senoide). gerar() não muda.
        amplitude = inspect.signature(oscilacao_amortecida).parameters["amplitude_pu"].default
        # Entalhe: o modelo zera a tensão nos pontos; reduzido, desce só
        # "fracao" do valor instantâneo.
        return {
            "notch_profundidade_pu_bancada": fracao,
            "oscillation_amplitude_pu_bancada": fracao * amplitude,
        }
