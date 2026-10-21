"""P28: análise exclusivamente matemática; nenhuma evidência de bancada."""
import contextlib
import hashlib
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
        self.assertFalse(resultado["bruto"]["thd"]["disponivel"])
        self.assertIn("fundamental nula", resultado["bruto"]["thd"]["motivo"])

    def test_thd_dez_porcento_ajuste_conjunto_sem_vazamento_e_dc_invariante(self):
        # 6,59 ciclos: FFT retangular não separa estes harmônicos sem vazamento.
        t = np.arange(13_181) / 120_000.0
        y = 4 * np.sin(2 * np.pi * 60 * t + .37) + .4 * np.cos(2 * np.pi * 180 * t + .61)
        for dc in (0, 27):
            with self.subTest(dc=dc):
                resultado = analise.comparar(t, y + dc, harmonicos=5)
                self.assertAlmostEqual(resultado["bruto"]["thd"]["thd_percentual"], 10, places=8)
                self.assertAlmostEqual(resultado["bruto"]["thd"]["dc_v"], dc, places=8)
                for janela in ("registro_completo", "interior_sem_bordas"):
                    self.assertAlmostEqual(resultado[janela]["interp"]["thd"]["thd_percentual"],
                                           10, places=6)
                    self.assertAlmostEqual(resultado[janela]["bruto_mesma_janela_thd"]["thd_percentual"],
                                           10, places=8)
                json.dumps(resultado, allow_nan=False)

    def test_thd_poucos_ciclos_indisponivel(self):
        t = self.t[:2400]
        resultado = analise.comparar(t, np.sin(2 * np.pi * 60 * t))
        for thd in (resultado["bruto"]["thd"], resultado["registro_completo"]["interp"]["thd"],
                    resultado["interior_sem_bordas"]["fir_interp"]["thd"]):
            self.assertFalse(thd["disponivel"])
            self.assertIsNone(thd["thd_percentual"])
            self.assertIn("dois ciclos", thd["motivo"])
        json.dumps(resultado, allow_nan=False)

    def test_harmonicos_fundamental_e_grade_invalida_recusados(self):
        y = np.sin(2 * np.pi * 60 * self.t)
        for kwargs in ({"harmonicos": 251}, {"harmonicos": 1}, {"harmonicos": 2.5},
                       {"harmonicos": True}, {"f0_hz": 0}, {"f0_hz": float("nan")},
                       {"pontos_salvos": 4000}, {"pontos_salvos": 4.5},
                       {"pontos_salvos": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                analise.comparar(self.t, y, **kwargs)

    def test_hashes_deterministas_sensiveis_a_sinal_e_configuracao(self):
        y = np.sin(2 * np.pi * 60 * self.t)
        base = analise.comparar(self.t, y, pontos_salvos=2500)["rastreabilidade"]
        repetido = analise.comparar(self.t, y.copy(), pontos_salvos=2500)["rastreabilidade"]
        outro_sinal = analise.comparar(self.t, y + .1, pontos_salvos=2500)["rastreabilidade"]
        outra_config = analise.comparar(self.t, y, pontos_salvos=2501)["rastreabilidade"]
        self.assertEqual(base, repetido)
        self.assertNotEqual(base["sinais_float64_le_sha256"], outro_sinal["sinais_float64_le_sha256"])
        self.assertNotEqual(base["configuracao_sha256"], outra_config["configuracao_sha256"])

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
            self.assertEqual(resultado["fonte"]["arquivo_sha256"], hashlib.sha256(original).hexdigest())
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                analise.main(["--sintetico", "--saida", str(saida)])
            self.assertEqual(json.loads(saida.read_text()), resultado)

    def test_cli_respeita_grade_npz_e_permite_override_explicito(self):
        with tempfile.TemporaryDirectory() as pasta:
            entrada = Path(pasta) / "bruto.npz"
            np.savez(entrada, tempo_s=self.t, tensao_v=np.sin(2 * np.pi * 50 * self.t),
                     fs_destino=24_000.0, pontos_destino=2000)
            original = entrada.read_bytes()
            for extras, fs, pontos in (([], 24000, 2000),
                                      (["--fs-salvo", "30000", "--pontos-salvos", "2500"], 30000, 2500)):
                saida = io.StringIO()
                with contextlib.redirect_stdout(saida):
                    analise.main(["--entrada", str(entrada), "--f0-hz", "50"] + extras)
                resultado = json.loads(saida.getvalue())
                self.assertEqual(resultado["amostras_salvas"], pontos)
                self.assertEqual(resultado["fs_salvo_hz"], fs)
                self.assertEqual(resultado["analise_harmonica"]["f0_hz"], 50)
                self.assertAlmostEqual(resultado["registro_completo"]["interp"]["thd"]["thd_percentual"],
                                       0, places=7)
            self.assertEqual(entrada.read_bytes(), original)

    def test_cli_demonstracao_identificada_como_sintetica(self):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            self.assertEqual(analise.main(["--sintetico"]), 0)
        self.assertEqual(json.loads(saida.getvalue())["fonte"]["tipo"], "sintetica_nao_fisica")

    def test_metadata_json_bruto_schema1_preserva_grade_e_rastreabilidade(self):
        meta = {"versao_schema": 1, "origem": "teste matemático", "canal": 1,
                "fs_destino_hz": 24000.0, "pontos_destino": 2000,
                "sinal_salvo_sha256": "0" * 64}
        with tempfile.TemporaryDirectory() as pasta:
            entrada = Path(pasta) / "bruto.npz"
            np.savez(entrada, tempo_s=self.t, tensao_v=np.sin(2 * np.pi * 60 * self.t),
                     metadata_json=np.array(json.dumps(meta)))
            saida = io.StringIO()
            with contextlib.redirect_stdout(saida):
                analise.main(["--entrada", str(entrada)])
            resultado = json.loads(saida.getvalue())
            self.assertEqual(resultado["amostras_salvas"], 2000)
            self.assertEqual(resultado["fs_salvo_hz"], 24000)
            self.assertEqual(resultado["fonte"]["metadata_bruto"], meta)
            # A captura possui janela adicional; a comparação usa só o destino.
            self.assertGreater(resultado["bruto"]["thd"]["ciclos_observados"],
                               resultado["registro_completo"]["bruto_mesma_janela_thd"]["ciclos_observados"])

    def test_metadata_json_invalido_e_recusado(self):
        validos = {"versao_schema": 1, "fs_destino_hz": 30000, "pontos_destino": 2000}
        casos = [np.array([json.dumps(validos)]), np.array("{}"),
                 np.array(json.dumps(dict(validos, versao_schema=True))),
                 np.array(json.dumps(dict(validos, fs_destino_hz="30000"))),
                 np.array(json.dumps(dict(validos, fs_destino_hz=float("nan")))),
                 np.array(json.dumps(dict(validos, pontos_destino=2.5))),
                 np.array(json.dumps(dict(validos, pontos_destino=True)))]
        for meta in casos:
            with self.subTest(metadata=str(meta)), self.assertRaises(ValueError):
                analise._metadados_brutos({"metadata_json": meta})


if __name__ == "__main__":
    unittest.main()
