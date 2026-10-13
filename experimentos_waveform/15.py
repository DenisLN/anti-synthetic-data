"""Classe 15: HARMONICS + FLICKER — forma de onda arbitrária, os 200 ms inteiros."""

import numpy as np

import perfis
from mestre import ExperimentoWaveform
from sinais import onda_com_harmonicos


class Experimento(ExperimentoWaveform):
    id = "15"
    # Parâmetros SORTEADOS em gerar() (v1.15, com o sorteio ligado): 3 capturas
    # por padrão na bancada (`arquivo/analises:docs/analise-2026-10-12/pendente/compostas_sorteadas_REVISAR.md`).
    capturas_padrao = 3
    nome = "HARMONICS_FLICKER"

    def gerar(self, t, f0, capture_index, rng):
        thd = perfis.composto(self.config, "thd_composto", capture_index, rng)
        profundidade = perfis.composto(self.config, "flicker_composto", capture_index, rng)
        flicker_hz = perfis.composto(self.config, "flicker_composto_hz", capture_index, rng)
        flicker = 1.0 + profundidade * np.sin(2.0 * np.pi * flicker_hz * t)
        sorteio = self.sortear(rng, f0)
        voltage = flicker * onda_com_harmonicos(t + sorteio.deslocamento_s, thd, frequencia_hz=f0)
        return voltage, {"thd": thd, "flicker_hz": flicker_hz, "flicker_depth": profundidade, **sorteio.parametros()}
