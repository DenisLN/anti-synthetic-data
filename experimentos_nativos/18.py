"""Classe 18: DESVIO/VARIAÇÃO DE FREQUÊNCIA — transiente nativo LIST:FREQuency.

Nota: a rampa nativa é aproximada por 2 pontos de LIST:FREQuency (início/fim)
com dwell dividindo os 200 ms ao meio — não é uma rampa contínua amostra a
amostra como o modelo em Python usa para o dataset simulado. Validar na
bancada antes do dataset físico.
"""

import numpy as np

from mestre import ExperimentoNativo


class Experimento(ExperimentoNativo):
    id = "18"
    nome = "FREQUENCY_DRIFT"

    def gerar(self, t, f0, capture_index, rng):
        fs_hz = 1.0 / (t[1] - t[0])
        points = t.size
        start_hz, end_hz = (57.0, 63.0) if capture_index % 2 == 0 else (63.0, 57.0)
        instantaneous_frequency = np.linspace(start_hz, end_hz, points, endpoint=True)
        phase = np.empty(points, dtype=np.float64)
        phase[0] = 0.0
        phase[1:] = 2.0 * np.pi * np.cumsum(instantaneous_frequency[:-1]) / fs_hz
        voltage = np.sin(phase)
        return voltage, {"start_hz": start_hz, "end_hz": end_hz}

    def configurar(self, capture_index):
        start_hz, end_hz = (57.0, 63.0) if capture_index % 2 == 0 else (63.0, 57.0)
        meio_s = self.config.duration_s / 2.0
        self.fonte.frequency_drift_list(
            start_hz, end_hz, voltage_rms=self.config.base_voltage_rms, dwell_s=meio_s,
        )
        return {"start_hz": start_hz, "end_hz": end_hz}
