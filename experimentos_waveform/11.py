"""Classe 11: SAG + FLICKER — forma de onda arbitrária."""

import numpy as np

import perfis
from mestre import ExperimentoWaveform
from sinais import janela


class Experimento(ExperimentoWaveform):
    id = "11"
    # Parâmetros SORTEADOS em gerar() (v1.15, com o sorteio ligado): 3 capturas
    # por padrão na bancada (`arquivo/analises:docs/analise-2026-10-12/pendente/compostas_sorteadas_REVISAR.md`).
    capturas_padrao = 3
    nome = "SAG_FLICKER"

    def gerar(self, t, f0, capture_index, rng):
        sag = perfis.composto(self.config, "sag_composto", capture_index, rng)
        profundidade = perfis.composto(self.config, "flicker_composto", capture_index, rng)
        flicker_hz = perfis.composto(self.config, "flicker_composto_hz", capture_index, rng)
        sorteio = self.sortear(
            rng, f0, inicio_legado_s=0.060, duracao_legada_s=0.060, duracao_variavel=True,
        )
        tt = t + sorteio.deslocamento_s
        voltage = np.sin(2.0 * np.pi * f0 * tt)
        mask = janela(t, sorteio.inicio_s, sorteio.duracao_s)
        voltage[mask] *= sag * (1.0 + profundidade * np.sin(2.0 * np.pi * flicker_hz * t[mask]))
        return voltage, {"sag_pu": sag, "flicker_hz": flicker_hz, "flicker_depth": profundidade, **sorteio.parametros()}

    def parametros_com_disturbio_reduzido(self, parametros, fracao):
        # Gancho de bancada (limite de bancada, v1.13): forma física =
        # senoide + fracao x (gerar() - senoide). gerar() não muda.
        nivel = 1.0 + fracao * (parametros["sag_pu"] - 1.0)
        return {
            "sag_pu_bancada": nivel,
            "flicker_depth_bancada": fracao * parametros["sag_pu"] * parametros["flicker_depth"] / nivel,
        }
