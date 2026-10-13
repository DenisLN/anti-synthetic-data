"""Classe 14: SWELL + OSCILLATORY_TRANSIENT — forma de onda arbitrária."""

import inspect

import numpy as np

import perfis
from mestre import ExperimentoWaveform
from sinais import janela, oscilacao_amortecida


class Experimento(ExperimentoWaveform):
    id = "14"
    # Parâmetros SORTEADOS em gerar() (v1.15, com o sorteio ligado): 3 capturas
    # por padrão na bancada (`arquivo/analises:docs/analise-2026-10-12/pendente/compostas_sorteadas_REVISAR.md`).
    capturas_padrao = 3
    nome = "SWELL_OSCILLATORY_TRANSIENT"

    def gerar(self, t, f0, capture_index, rng):
        swell = perfis.composto(self.config, "swell_composto", capture_index, rng)
        oscilacao_hz = perfis.composto(self.config, "oscilacao_composto_hz", capture_index, rng)
        sorteio = self.sortear(
            rng, f0, inicio_legado_s=0.060, duracao_legada_s=0.040, duracao_variavel=True,
        )
        voltage = np.sin(2.0 * np.pi * f0 * (t + sorteio.deslocamento_s))
        mask = janela(t, sorteio.inicio_s, sorteio.duracao_s)
        voltage[mask] *= swell
        voltage = voltage + oscilacao_amortecida(
            t, inicio_s=sorteio.inicio_s, duracao_s=sorteio.duracao_s, frequencia_hz=oscilacao_hz,
        )
        return voltage, {"swell_pu": swell, "oscillation_hz": oscilacao_hz, **sorteio.parametros()}

    def parametros_com_disturbio_reduzido(self, parametros, fracao):
        # Gancho de bancada (limite de bancada, v1.13): forma física =
        # senoide + fracao x (gerar() - senoide). gerar() não muda.
        amplitude = inspect.signature(oscilacao_amortecida).parameters["amplitude_pu"].default
        return {
            "swell_pu_bancada": 1.0 + fracao * (parametros["swell_pu"] - 1.0),
            "oscillation_amplitude_pu_bancada": fracao * amplitude,
        }
