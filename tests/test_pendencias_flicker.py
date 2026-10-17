"""P12: esperado físico é programado; medida/modelo continuam independentes."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "logica") not in sys.path:
    sys.path.insert(0, str(ROOT / "logica"))
from ametek_orm import AmetekMX30
from mestre import ExperimentoWaveform

spec = importlib.util.spec_from_file_location("flicker_pendencias", ROOT / "experimentos_waveform" / "06.py")
modulo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modulo)


class PendenciasFlicker(unittest.TestCase):
    def setUp(self):
        self.t = np.arange(6000) / 30_000.0
        self.experimento = modulo.Experimento.__new__(modulo.Experimento)
        self.experimento.config = SimpleNamespace(base_voltage_rms=127, grid_frequency_hz=60)
        self.experimento.fonte = SimpleNamespace(passo_final_sin=False)
        self.experimento._versoes_atuais = None
        self.forma = np.sin(2 * np.pi * 60 * self.t) * (1 + 0.2 * np.sin(2 * np.pi * 13 * self.t))

    def test_programada_registrada_e_usada_exatamente_sem_recalcular(self):
        planejada = AmetekMX30.montar_programacao(self.forma, base_voltage_rms=127,
                                                frequency_hz=60).programada_pu()
        self.experimento._versoes_atuais = {"modelo": self.forma.copy(), "programada": planejada,
                                          "origem_programada": "TRACe+LIST:VOLTage"}
        with mock.patch.object(AmetekMX30, "montar_programacao") as montar:
            esperada = self.experimento.forma_esperada_para_validacao(0, self.t, 123)
        np.testing.assert_array_equal(esperada, planejada)
        self.assertGreater(float(np.max(np.abs(esperada - self.forma))), 0.001)
        np.testing.assert_array_equal(self.experimento._versoes_atuais["modelo"], self.forma)
        montar.assert_not_called()

    def test_sem_registro_reconstroi_programacao_da_forma_limitada(self):
        self.experimento._forma_programada_pu = self.forma * 0.8
        original = self.experimento._forma_programada_pu.copy()
        prevista = AmetekMX30.montar_programacao(original, base_voltage_rms=127,
                                               frequency_hz=60).programada_pu()
        esperada = self.experimento.forma_esperada_para_validacao(0, self.t, 123)
        np.testing.assert_array_equal(esperada, prevista)
        np.testing.assert_array_equal(self.experimento._forma_programada_pu, original)
        self.assertGreater(float(np.max(np.abs(esperada - original))), 0.001)

    def test_programada_invalida_recua_sem_usar_modelo_ou_medida(self):
        for invalida in (np.full(6000, np.nan), np.zeros(5), "invalida"):
            with self.subTest(tipo=type(invalida).__name__):
                self.experimento._versoes_atuais = {"programada": invalida, "modelo": np.zeros(6000),
                                                  "medida": np.full(6000, 123.0)}
                self.experimento._forma_programada_pu = self.forma
                esperada = self.experimento.forma_esperada_para_validacao(0, self.t, 123)
                self.assertGreater(float(np.std(esperada)), 0.5)
                self.assertFalse(np.array_equal(esperada, self.experimento._versoes_atuais["medida"]))

    def test_sem_forma_de_origem_nao_inventa_referencia(self):
        with mock.patch.object(ExperimentoWaveform, "forma_esperada_para_validacao", return_value=None):
            self.assertIsNone(self.experimento.forma_esperada_para_validacao(0, self.t, 123))


if __name__ == "__main__":
    unittest.main()
