"""Classe 10: SAG + HARMONICS — forma de onda arbitrária.

Candidata a virar nativa (LIST:VOLTage + LIST:FUNCtion:SHAPe sincronizados,
SIN/CSIN por passo) — validar na bancada; por ora fica em TRACe, garantido
de funcionar.
"""

import numpy as np

import perfis
from mestre import ExperimentoWaveform
from sinais import janela, onda_com_harmonicos


class Experimento(ExperimentoWaveform):
    id = "10"
    # Parâmetros SORTEADOS em gerar() (v1.15, com o sorteio ligado): 3 capturas
    # por padrão na bancada (docs/analise-2026-10-12/compostas_sorteadas.md).
    capturas_padrao = 3
    nome = "SAG_HARMONICS"

    def gerar(self, t, f0, capture_index, rng):
        sag = perfis.composto(self.config, "sag_composto", capture_index, rng)
        thd = perfis.composto(self.config, "thd_composto", capture_index, rng)
        sorteio = self.sortear(
            rng, f0, inicio_legado_s=0.060, duracao_legada_s=0.060, duracao_variavel=True,
        )
        tt = t + sorteio.deslocamento_s
        voltage = np.sin(2.0 * np.pi * f0 * tt)
        mask = janela(t, sorteio.inicio_s, sorteio.duracao_s)
        voltage[mask] = sag * onda_com_harmonicos(tt[mask], thd, frequencia_hz=f0)
        return voltage, {"sag_pu": sag, "thd": thd, **sorteio.parametros()}

    def parametros_com_disturbio_reduzido(self, parametros, fracao):
        # Gancho de bancada (limite de bancada, v1.13): forma física =
        # senoide + fracao x (gerar() - senoide). gerar() não muda.
        nivel = 1.0 + fracao * (parametros["sag_pu"] - 1.0)
        return {
            "sag_pu_bancada": nivel,
            "thd_bancada": fracao * parametros["sag_pu"] * parametros["thd"] / nivel,
        }
