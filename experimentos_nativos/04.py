"""Classe 04: INTERRUPTION (interrupção) — transiente nativo PULSe."""

import numpy as np

from comum import executar_classe_nativa, janela

INICIO_S = 0.060
DURACAO_S = 0.060


def gerar(t, f0, capture_index, rng):
    voltage = np.sin(2.0 * np.pi * f0 * t)
    nivel = float(rng.uniform(0.0, 0.09))
    voltage[janela(t, INICIO_S, DURACAO_S)] *= nivel
    return voltage, {"interruption_pu": nivel}


def _configurar(fonte, config, capture_index):
    # Sem osciloscópio real por captura para gerar o rng "certo", reproduz a
    # mesma semente usada em gerar() para esse capture_index.
    seed = config.base_seed + 4_000_000 + capture_index
    nivel = float(np.random.default_rng(seed).uniform(0.0, 0.09))
    fonte.write("VOLTage:MODE PULSe")
    fonte.write(f"VOLTage:TRIGgered {nivel * config.base_voltage_rms:.8g}")
    fonte.write(f"PULSe:WIDTh {DURACAO_S:.8g}")
    return {"interruption_pu": nivel}


def run(fonte, osc, config):
    executar_classe_nativa(
        config, fonte, osc, "04", "INTERRUPTION", gerar, _configurar, pre_trigger_s=INICIO_S,
    )
