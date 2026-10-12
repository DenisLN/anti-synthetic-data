"""Classe 17: NOTCH + OSCILLATORY_TRANSIENT — forma de onda arbitrária."""

import inspect

import numpy as np

from mestre import ExperimentoWaveform
from sinais import aplicar_entalhes, aplicar_entalhes_continuos, oscilacao_amortecida


class Experimento(ExperimentoWaveform):
    id = "17"
    nome = "NOTCH_OSCILLATORY_TRANSIENT"
    # Parâmetro SORTEADO em gerar(): 3 capturas por padrão na bancada (pedido
    # do dono, 2026-10-07; CHANGELOG/v1.13.md). Não muda o dataset simulado.
    capturas_padrao = 3

    def gerar(self, t, f0, capture_index, rng):
        # Início sorteado (da oscilação), fase acoplada a ele: a senoide cruza
        # zero em t0.
        sorteio = self.sortear(
            rng, f0, inicio_legado_s=0.060, duracao_legada_s=0.060, fase_acoplada_ao_inicio=True,
        )
        voltage = np.sin(2.0 * np.pi * f0 * (t + sorteio.deslocamento_s))
        if getattr(self.config, "sorteio_posicao", True):
            # Mesma regra da 07 (IEEE 1159-2019, 4.4.5.4): entalhes periódicos
            # e contínuos, em todos os ciclos da janela, nos picos da senoide.
            # Só a oscilação amortecida continua localizada em t0.
            pulsos = aplicar_entalhes_continuos(
                voltage, t, rng, frequencia_hz=f0, origem_s=-sorteio.deslocamento_s,
            )
        else:
            pulsos = aplicar_entalhes(
                voltage, t, rng, frequencia_hz=f0, inicio_s=sorteio.inicio_s, duracao_s=sorteio.duracao_s,
            )
        voltage = voltage + oscilacao_amortecida(
            t, inicio_s=sorteio.inicio_s, duracao_s=sorteio.duracao_s, frequencia_hz=300.0,
        )
        return voltage, {"notch_pulses": float(pulsos), "oscillation_hz": 300.0, **sorteio.parametros()}

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
