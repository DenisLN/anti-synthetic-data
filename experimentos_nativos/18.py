"""Classe 18: DESVIO/VARIAÇÃO DE FREQUÊNCIA — transiente nativo LIST:FREQuency.

Nota: a rampa nativa é aproximada por 2 pontos de LIST:FREQuency (início/fim)
com dwell dividindo os 200 ms ao meio — não é uma rampa contínua amostra a
amostra como o modelo em Python usa para o dataset simulado. Validar na
bancada antes do dataset físico.
"""

import numpy as np

from comum import executar_classe_nativa


def gerar(t, f0, capture_index, rng):
    fs_hz = 1.0 / (t[1] - t[0])
    points = t.size
    start_hz, end_hz = (57.0, 63.0) if capture_index % 2 == 0 else (63.0, 57.0)
    instantaneous_frequency = np.linspace(start_hz, end_hz, points, endpoint=True)
    phase = np.empty(points, dtype=np.float64)
    phase[0] = 0.0
    phase[1:] = 2.0 * np.pi * np.cumsum(instantaneous_frequency[:-1]) / fs_hz
    voltage = np.sin(phase)
    return voltage, {"start_hz": start_hz, "end_hz": end_hz}


def _configurar(fonte, config, capture_index):
    start_hz, end_hz = (57.0, 63.0) if capture_index % 2 == 0 else (63.0, 57.0)
    meio_s = config.duration_s / 2.0
    fonte.write("FREQuency:MODE LIST")
    fonte.write(f"LIST:FREQuency {start_hz:.8g},{end_hz:.8g}")
    fonte.write(f"LIST:VOLTage {config.base_voltage_rms:.8g},{config.base_voltage_rms:.8g}")
    fonte.write(f"LIST:DWELl {meio_s:.8g},{meio_s:.8g}")
    fonte.write("LIST:REPeat:COUNt 1,1")
    fonte.write("LIST:COUNt 1")
    fonte.write("LIST:STEP AUTO")
    fonte.write("VOLTage:MODE LIST")
    return {"start_hz": start_hz, "end_hz": end_hz}


def run(fonte, osc, config):
    executar_classe_nativa(config, fonte, osc, "18", "FREQUENCY_DRIFT", gerar, _configurar)
