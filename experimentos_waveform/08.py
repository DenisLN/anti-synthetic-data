"""Classe 08: TRANSIENT (transitório impulsivo) — forma de onda arbitrária."""

import math

import numpy as np

from comum import executar_classe_waveform


def gerar(t, f0, capture_index, rng):
    fs_hz = 1.0 / (t[1] - t[0])
    voltage = np.sin(2.0 * np.pi * f0 * t)
    amplitude = float(rng.uniform(5.0, 10.0))
    start_index = int(round(0.080 * fs_hz))
    pulse_samples = max(1, int(math.ceil(0.00005 * fs_hz)))
    voltage[start_index : start_index + pulse_samples] += amplitude
    return voltage, {"transient_amplitude_pu": amplitude, "pulse_samples": float(pulse_samples)}


def run(fonte, osc, config):
    executar_classe_waveform(config, fonte, osc, "08", "TRANSIENT", gerar)
