"""Classe 19: INJEÇÃO DE COMPONENTE CONTÍNUA (DC Offset) — transiente nativo.

Usa SOURce:MODE ACDC + SOURce:VOLTage:OFFSet (nível imediato, não transiente
disparado) — o offset fica presente na janela inteira, como o modelo pede.
"""

import math

import numpy as np

from comum import executar_classe_nativa


def gerar(t, f0, capture_index, rng):
    dc_offset = float(rng.uniform(0.02, 0.10))
    voltage = np.sin(2.0 * np.pi * f0 * t) + dc_offset
    return voltage, {"dc_offset_pu": dc_offset}


def _configurar(fonte, config, capture_index):
    seed = config.base_seed + 19_000_000 + capture_index
    dc_offset = float(np.random.default_rng(seed).uniform(0.02, 0.10))
    offset_v = dc_offset * config.base_voltage_rms * math.sqrt(2.0)
    fonte.write("SOURce:MODE ACDC")
    fonte.write(f"SOURce:VOLTage:OFFSet {offset_v:.8g}")
    fonte.write("VOLTage:MODE STEP")
    fonte.write(f"VOLTage:TRIGgered {config.base_voltage_rms:.8g}")
    return {"dc_offset_pu": dc_offset}


def run(fonte, osc, config):
    executar_classe_nativa(config, fonte, osc, "19", "DC_OFFSET", gerar, _configurar)
