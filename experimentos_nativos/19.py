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
    # Parâmetro SORTEADO em gerar(): 3 capturas por padrão na bancada (pedido
    # do dono, 2026-10-07; CHANGELOG/v1.13.md). Não muda o dataset simulado.
    capturas_padrao = 3

    def gerar(self, t, f0, capture_index, rng):
        simulado = self.osc is None
        total = self.config.capturas(simulado)
        cobertura_ativa = not simulado and self.config.capturas_override is not None
        dc_offset = sinais.valor_para_captura(rng, 0.02, 0.10, capture_index, total, cobertura_ativa=cobertura_ativa)
        voltage = np.sin(2.0 * np.pi * f0 * t) + dc_offset
        return voltage, {"dc_offset_pu": dc_offset}

    def configurar(self, capture_index):
        seed = self.config.base_seed + 19_000_000 + capture_index
        cobertura_ativa = self.config.capturas_override is not None
        total = self.config.capturas(False)
        dc_offset = sinais.valor_para_captura(
            np.random.default_rng(seed), 0.02, 0.10, capture_index, total, cobertura_ativa=cobertura_ativa,
        )
        ac_peak_v = self.config.base_voltage_rms * math.sqrt(2.0)
        offset_v = dc_offset * ac_peak_v
        self.fonte.enable_dc_offset(offset_v, ac_peak_v=ac_peak_v)
        self.fonte.trigger_step(self.config.base_voltage_rms)
        return {"dc_offset_pu": dc_offset}
