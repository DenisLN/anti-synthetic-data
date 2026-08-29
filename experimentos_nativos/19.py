"""Classe 19: INJEÇÃO DE COMPONENTE CONTÍNUA (DC Offset) — transiente nativo.

Usa SOURce:MODE ACDC + SOURce:VOLTage:OFFSet (nível imediato, não transiente
disparado) — o offset fica presente na janela inteira, como o modelo pede.
"""

import math

import numpy as np

from mestre import ExperimentoNativo


class Experimento(ExperimentoNativo):
    id = "19"
    nome = "DC_OFFSET"

    def gerar(self, t, f0, capture_index, rng):
        dc_offset = float(rng.uniform(0.02, 0.10))
        voltage = np.sin(2.0 * np.pi * f0 * t) + dc_offset
        return voltage, {"dc_offset_pu": dc_offset}

    def configurar(self, capture_index):
        seed = self.config.base_seed + 19_000_000 + capture_index
        dc_offset = float(np.random.default_rng(seed).uniform(0.02, 0.10))
        ac_peak_v = self.config.base_voltage_rms * math.sqrt(2.0)
        offset_v = dc_offset * ac_peak_v
        self.fonte.enable_dc_offset(offset_v, ac_peak_v=ac_peak_v)
        self.fonte.trigger_step(self.config.base_voltage_rms)
        return {"dc_offset_pu": dc_offset}
