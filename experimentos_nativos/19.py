"""Classe 19: INJEÇÃO DE COMPONENTE CONTÍNUA (DC Offset) — transiente nativo.

Usa SOURce:MODE ACDC + SOURce:VOLTage:OFFSet (nível imediato, não transiente
disparado) — o offset fica presente na janela inteira, como o modelo pede.
"""

import math

import numpy as np

import sinais
from mestre import ExperimentoNativo


class Experimento(ExperimentoNativo):
    id = "19"
    nome = "DC_OFFSET"
    # Parâmetro SORTEADO em gerar(): 3 capturas por padrão na bancada (uma
    # captura mostra uma só realização do sorteio; CHANGELOG/v1.13.md). Não
    # muda o dataset simulado.
    capturas_padrao = 3

    def gerar(self, t, f0, capture_index, rng):
        simulado = self.osc is None
        total = self.config.capturas(simulado)
        cobertura_ativa = not simulado and self.config.capturas_override is not None
        dc_offset = sinais.valor_para_captura(rng, 0.02, 0.10, capture_index, total, cobertura_ativa=cobertura_ativa)
        sorteio = self.sortear(rng, f0)
        voltage = np.sin(2.0 * np.pi * f0 * (t + sorteio.deslocamento_s)) + dc_offset
        return voltage, {"dc_offset_pu": dc_offset, **sorteio.parametros()}

    def _offset_da_captura(self, capture_index):
        """(dc_offset_pu, offset_v, ac_peak_v) que configurar() programa."""
        seed = self.config.base_seed + 19_000_000 + capture_index
        cobertura_ativa = self.config.capturas_override is not None
        total = self.config.capturas(False)
        dc_offset = sinais.valor_para_captura(
            np.random.default_rng(seed), 0.02, 0.10, capture_index, total, cobertura_ativa=cobertura_ativa,
        )
        ac_peak_v = self.config.base_voltage_rms * math.sqrt(2.0)
        return dc_offset, dc_offset * ac_peak_v, ac_peak_v

    def exigencias_nativas(self, capture_index, parametros):
        """Offset DC em AC+DC: conferido contra ametek_orm.CAPACIDADES_MX30 antes de programar."""
        return {"dc_offset_v": self._offset_da_captura(capture_index)[1]}

    def configurar(self, capture_index):
        dc_offset, offset_v, ac_peak_v = self._offset_da_captura(capture_index)
        self.fonte.enable_dc_offset(offset_v, ac_peak_v=ac_peak_v)
        self.fonte.trigger_step(self.config.base_voltage_rms)
        return {"dc_offset_pu": dc_offset}
