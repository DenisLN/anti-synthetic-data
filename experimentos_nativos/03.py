"""Classe 03: SWELL (elevação de tensão) — transiente nativo PULSe."""

import numpy as np

from comum import executar_classe_nativa, janela

NIVEIS = (1.1, 1.2, 1.4, 1.6, 1.8)
INICIO_S = 0.060
DURACAO_S = 0.060


def gerar(t, f0, capture_index, rng):
    voltage = np.sin(2.0 * np.pi * f0 * t)
    nivel = NIVEIS[capture_index % len(NIVEIS)]
    voltage[janela(t, INICIO_S, DURACAO_S)] *= nivel
    return voltage, {"swell_pu": nivel}


def _configurar(fonte, config, capture_index):
    nivel = NIVEIS[capture_index % len(NIVEIS)]
    fonte.write("VOLTage:MODE PULSe")
    fonte.write(f"VOLTage:TRIGgered {nivel * config.base_voltage_rms:.8g}")
    fonte.write(f"PULSe:WIDTh {DURACAO_S:.8g}")
    return {"swell_pu": nivel}


def run(fonte, osc, config):
    executar_classe_nativa(
        config, fonte, osc, "03", "SWELL", gerar, _configurar, pre_trigger_s=INICIO_S,
    )
