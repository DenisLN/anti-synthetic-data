"""P28: análise exclusivamente matemática; nenhuma evidência de bancada."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "analisar_reamostragem.py"
spec = importlib.util.spec_from_file_location("analisar_reamostragem", SCRIPT)
analise = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analise)


class PendenciasReamostragem(unittest.TestCase):
    def setUp(self):
        self.t = np.arange(12_000) / 120_000.0

    def test_sinal_na_banda_preserva_rms_e_correlacao(self):
        y = np.sin(2 * np.pi * 60 * self.t)
        resultado = analise.comparar(self.t, y)
        interior = resultado["interior_sem_bordas"]
        self.assertLess(interior["erro_rms_v"], 0.002)
        self.assertGreater(interior["correlacao"], 0.9999)
        self.assertLess(abs(interior["fir_interp"]["rms_v"] - interior["interp"]["rms_v"]), 0.002)

    def test_20khz_produz_alias_a_30ksa_e_fir_atenua(self):
        y = np.sin(2 * np.pi * 20_000 * self.t)
        resultado = analise.comparar(self.t, y)
        interior = resultado["interior_sem_bordas"]
        self.assertGreater(interior["interp"]["rms_v"], 0.70)
        self.assertLess(interior["fir_interp"]["rms_v"], 0.005)
        self.assertGreater(resultado["espectro_bruto"]["fracao_acima_nyquist"], 0.999)
        self.assertAlmostEqual(resultado["fs_bruto_hz"], 120_000, places=4)
        self.assertEqual(resultado["fs_salvo_hz"], 30_000)

    def test_entrada_invalida_e_recusada(self):
        y = np.ones_like(self.t)
        invalido = self.t.copy()
        invalido[10] = invalido[9]
        for t, v, kwargs in ((invalido, y, {}), (self.t[::-1], y, {}),
                             (self.t, y[:-1], {}), (self.t, y * np.nan, {}),
                             (self.t[:8], y[:8], {}),
                             (self.t, y, {"fs_salvo": 0}),
                             (self.t, y, {"fs_salvo": 240_000}),
                             (self.t, y, {"taps": 256})):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                analise.comparar(t, v, **kwargs)

    def test_constante_gera_json_sem_nan(self):
        resultado = analise.comparar(self.t, np.ones_like(self.t))
        self.assertIsNone(resultado["interior_sem_bordas"]["correlacao"])
        json.dumps(resultado, allow_nan=False)
        self.assertLess(resultado["interior_sem_bordas"]["erro_rms_v"], 1e-12)

    def test_cli_npz_com_chaves_personalizadas_nao_altera_origem(self):
        with tempfile.TemporaryDirectory() as pasta:
            entrada, saida = Path(pasta) / "bruto.npz", Path(pasta) / "analise.json"
            np.savez(entrada, t=self.t, y=np.sin(2 * np.pi * 60 * self.t))
            original = entrada.read_bytes()
            self.assertEqual(analise.main(["--entrada", str(entrada), "--chave-tempo", "t",
                                          "--chave-tensao", "y", "--saida", str(saida)]), 0)
            self.assertEqual(entrada.read_bytes(), original)
            resultado = json.loads(saida.read_text())
            self.assertEqual(resultado["fonte"]["tipo"], "arquivo_bruto_fornecido")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                analise.main(["--sintetico", "--saida", str(saida)])
            self.assertEqual(json.loads(saida.read_text()), resultado)

    def test_cli_demonstracao_identificada_como_sintetica(self):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            self.assertEqual(analise.main(["--sintetico"]), 0)
        self.assertEqual(json.loads(saida.getvalue())["fonte"]["tipo"], "sintetica_nao_fisica")


if __name__ == "__main__":
    unittest.main()
