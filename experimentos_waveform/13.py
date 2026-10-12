"""Classe 13: SWELL + HARMONICS — forma de onda arbitrária.

Candidata a virar nativa (LIST:VOLTage + LIST:FUNCtion:SHAPe sincronizados) —
validar na bancada; por ora fica em TRACe, garantido de funcionar.
"""

import numpy as np

import perfis
from mestre import ExperimentoWaveform
from sinais import janela, onda_com_harmonicos


class Experimento(ExperimentoWaveform):
    id = "13"
    # Parâmetros SORTEADOS em gerar() (v1.15, com o sorteio ligado): 3 capturas
    # por padrão na bancada (docs/analise-2026-10-12/compostas_sorteadas.md).
    capturas_padrao = 3
    nome = "SWELL_HARMONICS"

    def gerar(self, t, f0, capture_index, rng):
        swell = perfis.composto(self.config, "swell_composto", capture_index, rng)
        thd = perfis.composto(self.config, "thd_composto", capture_index, rng)
        sorteio = self.sortear(
            rng, f0, inicio_legado_s=0.060, duracao_legada_s=0.060, duracao_variavel=True,
        )
        tt = t + sorteio.deslocamento_s
        voltage = np.sin(2.0 * np.pi * f0 * tt)
        mask = janela(t, sorteio.inicio_s, sorteio.duracao_s)
        voltage[mask] = swell * onda_com_harmonicos(tt[mask], thd, frequencia_hz=f0)
        return voltage, {"swell_pu": swell, "thd": thd, **sorteio.parametros()}

    def parametros_com_disturbio_reduzido(self, parametros, fracao):
        # Gancho de bancada (limite de bancada, v1.13): forma física =
        # senoide + fracao x (gerar() - senoide). gerar() não muda.
        nivel = 1.0 + fracao * (parametros["swell_pu"] - 1.0)
        return {
            "swell_pu_bancada": nivel,
            "thd_bancada": fracao * parametros["swell_pu"] * parametros["thd"] / nivel,
        }
