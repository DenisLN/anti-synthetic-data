"""Classe 18: DESVIO/VARIAÇÃO DE FREQUÊNCIA — transiente nativo LIST:FREQuency.

Nota: a rampa nativa é aproximada por 2 pontos de LIST:FREQuency (início/fim)
com dwell dividindo os 200 ms ao meio — não é uma rampa contínua amostra a
amostra como o modelo em Python usa para o dataset simulado. Validar na
bancada antes do dataset físico.
"""

import numpy as np

from mestre import ExperimentoNativo


DESVIO_HZ = 3.0


class Experimento(ExperimentoNativo):
    id = "18"
    nome = "FREQUENCY_DRIFT"

    def extremos_hz(self, f0, capture_index):
        """(início, fim) da rampa. Com o sorteio ligado (v1.15) varre
        ``f0 - 3`` -> ``f0 + 3`` Hz (e o inverso nas capturas ímpares), em
        torno da frequência da rede da sessão; desligado, 57 -> 63 Hz fixos
        como em 34a0d82 (a 50 Hz isso é +14 % / +26 % da rede)."""
        if getattr(self.config, "sorteio_posicao", True):
            baixo, alto = f0 - DESVIO_HZ, f0 + DESVIO_HZ
        else:
            baixo, alto = 57.0, 63.0
        return (baixo, alto) if capture_index % 2 == 0 else (alto, baixo)

    def gerar(self, t, f0, capture_index, rng):
        fs_hz = 1.0 / (t[1] - t[0])
        points = t.size
        start_hz, end_hz = self.extremos_hz(f0, capture_index)
        instantaneous_frequency = np.linspace(start_hz, end_hz, points, endpoint=True)
        phase = np.empty(points, dtype=np.float64)
        phase[0] = 0.0
        phase[1:] = 2.0 * np.pi * np.cumsum(instantaneous_frequency[:-1]) / fs_hz
        # Só a fase (da fundamental em t = 0) é sorteada (v1.15).
        sorteio = self.sortear(rng, f0)
        voltage = np.sin(phase + np.deg2rad(sorteio.fase_graus))
        return voltage, {"start_hz": start_hz, "end_hz": end_hz, **sorteio.parametros()}

    def exigencias_nativas(self, capture_index, parametros):
        """LIST de 2 pontos (frequência início/fim) com dwell de meia janela:
        conferido contra ametek_orm.CAPACIDADES_MX30 antes de programar."""
        start_hz, end_hz = self.extremos_hz(self.config.grid_frequency_hz, capture_index)
        return {
            "frequencia_hz": [start_hz, end_hz],
            "dwell_s": self.config.duration_s / 2.0,
            "passos_list": 2,
        }

    def configurar(self, capture_index):
        start_hz, end_hz = self.extremos_hz(self.config.grid_frequency_hz, capture_index)
        meio_s = self.config.duration_s / 2.0
        self.fonte.frequency_drift_list(
            start_hz, end_hz, voltage_rms=self.config.base_voltage_rms, dwell_s=meio_s,
        )
        return {"start_hz": start_hz, "end_hz": end_hz}
