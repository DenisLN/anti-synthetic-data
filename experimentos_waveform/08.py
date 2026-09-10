"""Classe 08: TRANSIENT (transitório impulsivo) — forma de onda arbitrária."""

import math

import numpy as np

from mestre import ExperimentoWaveform


class Experimento(ExperimentoWaveform):
    id = "08"
    nome = "TRANSIENT"

    def limite_pico_bancada_pu(self):
        # experimentos.txt pede 5-10 pu de amplitude ADICIONAL ao pico normal
        # (até ~11 pu total) — a 127 Vrms isso passa de 1900 V, muito acima
        # do teto físico da AMETEK MX30 no range de 300 Vrms (~415 Vp).
        # 90% do pico máximo autorizado (self.fonte.max_peak_v) como margem
        # de segurança sobre o teto físico; só afeta a captura de
        # comissionamento (ver docstring em ExperimentoWaveform).
        nominal_peak_v = self.config.base_voltage_rms * math.sqrt(2.0)
        return 0.9 * self.fonte.max_peak_v / nominal_peak_v

    def gerar(self, t, f0, capture_index, rng):
        fs_hz = 1.0 / (t[1] - t[0])
        voltage = np.sin(2.0 * np.pi * f0 * t)
        amplitude = float(rng.uniform(5.0, 10.0))
        start_index = int(round(0.080 * fs_hz))
        pulse_samples = max(1, int(math.ceil(0.00005 * fs_hz)))
        voltage[start_index : start_index + pulse_samples] += amplitude
        return voltage, {"transient_amplitude_pu": amplitude, "pulse_samples": float(pulse_samples)}
