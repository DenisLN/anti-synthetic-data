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

    def parametros_com_disturbio_reduzido(self, parametros, fracao):
        """Envelopes exatos de senoide + f * (modelo - senoide).

        No modelo o flicker multiplica fundamental E harmônicos. Após a
        redução, a fundamental tem envelope 1 + f*d*m, e os harmônicos
        f*(1 + d*m), com m = sin(2*pi*flicker_hz*t). Logo a THD local é
        f*thd*(1 + d*m)/(1 + f*d*m), não uma constante f*thd. Os extremos
        abaixo cobrem m em [-1, 1], independentemente da janela de captura.
        """
        f = float(fracao)
        d = float(parametros["flicker_depth"])
        thd = float(parametros["thd"])
        if not np.isfinite(f) or not 0 <= f <= 1:
            raise ValueError("Fração de redução deve estar entre 0 e 1")
        if not np.isfinite(d) or not 0 <= d < 1:
            raise ValueError("Profundidade de flicker deve estar entre 0 (inclusive) e 1")
        if not np.isfinite(thd) or thd < 0:
            raise ValueError("THD deve ser finita e não negativa")
        return {
            "flicker_depth_bancada": f * d,
            "thd_bancada_centro": f * thd,
            "thd_bancada_min": f * thd * (1 - d) / (1 - f * d),
            "thd_bancada_max": f * thd * (1 + d) / (1 + f * d),
            # Junto com fator_disturbio_bancada e os parâmetros do modelo,
            # estes coeficientes permitem reconstruir os dois envelopes.
            "harmonicos_envelope_centro_bancada": f,
            "harmonicos_envelope_modulacao_bancada": f * d,
        }
