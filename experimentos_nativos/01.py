"""Classe 01: NORMAL — senoide limpa, sem distúrbio."""

import numpy as np

from comum import executar_classe_nativa


def gerar(t, f0, capture_index, rng):
    voltage = np.sin(2.0 * np.pi * f0 * t)
    return voltage, {}


def _configurar(fonte, config, capture_index):
    # Sem distúrbio nenhum: um STEP para o mesmo valor imediato só para gerar
    # o pulso de trigger (Beginning Of Transient) que o osciloscópio aguarda.
    fonte.write("VOLTage:MODE STEP")
    fonte.write(f"VOLTage:TRIGgered {config.base_voltage_rms:.8g}")
    return {}


def run(fonte, osc, config):
    executar_classe_nativa(config, fonte, osc, "01", "NORMAL", gerar, _configurar)
