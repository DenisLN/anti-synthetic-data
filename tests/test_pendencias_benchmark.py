"""P22: carga pequena, integridade de leitura e distinção de aliases."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "benchmark_sessao_io.py"
spec = importlib.util.spec_from_file_location("benchmark_sessao_io", SCRIPT)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class PendenciasBenchmark(unittest.TestCase):
    def test_carga_pequena_mede_checkpoints_e_valida_sinais_e_aliases(self):
        resultado = bench.benchmark(2, 64)
        self.assertEqual(resultado["capturas_materializadas"], 4)
        self.assertEqual(resultado["aliases_logicos"], 2)
        self.assertEqual(resultado["integridade"]["registros_logicos_lidos"], 6)
        self.assertTrue(all(resultado["integridade"][k] for k in
                            ("ids_e_sinais_exatos", "snr_exato", "aliases_sem_blocos_duplicados")))
        self.assertGreater(resultado["pico_tracemalloc_bytes"], 0)
        self.assertGreater(resultado["adicionar_s"], 0)
        self.assertGreater(resultado["consolidar_s"], 0)
        self.assertEqual([c["capturas_materializadas"] for c in resultado["checkpoints"]], [2, 4])
        self.assertGreater(resultado["armazenamento_final"]["total_bytes"], 0)
        self.assertTrue(any(p.startswith("parcial/") for p in
                            resultado["armazenamento_final"]["arquivos_bytes"]))

    def test_mesma_seed_reproduz_sinais_e_outra_seed_muda(self):
        a = bench.benchmark(1, 32, 123, spool=False)
        b = bench.benchmark(1, 32, 123, spool=False)
        c = bench.benchmark(1, 32, 456, spool=False)
        self.assertEqual(a["sha256_sinais_entrada"], b["sha256_sinais_entrada"])
        self.assertNotEqual(a["sha256_sinais_entrada"], c["sha256_sinais_entrada"])
        self.assertFalse(any(p.startswith("parcial/") for p in
                             a["armazenamento_final"]["arquivos_bytes"]))

    def test_corrupcao_na_leitura_e_detectada(self):
        leitor = bench.ler_capturas

        def corromper(*args, **kwargs):
            capturas = leitor(*args, **kwargs)
            if not kwargs.get("subpasta"):
                capturas[0].versoes["medida"][0] += 1
            return capturas

        with mock.patch.object(bench, "ler_capturas", side_effect=corromper), \
                self.assertRaisesRegex(AssertionError, "sinal não preservado"):
            bench.benchmark(1, 32)

    def test_fecha_writer_mesmo_quando_leitura_falha(self):
        construtor = bench.ArquivoDaClasse
        for falha in (False, True):
            with self.subTest(falha=falha):
                writers = []

                def construir(*args, **kwargs):
                    writer = construtor(*args, **kwargs)
                    writers.append(writer)  # Impede que __del__ mascare a falta de close.
                    return writer

                with mock.patch.object(bench, "ArquivoDaClasse", side_effect=construir):
                    if falha:
                        with mock.patch.object(bench, "ler_capturas", side_effect=RuntimeError("leitura falhou")), \
                                self.assertRaisesRegex(RuntimeError, "leitura falhou"):
                            bench.benchmark(1, 32)
                    else:
                        bench.benchmark(1, 32)
                self.assertEqual(len(writers), 1)
                with self.assertRaisesRegex(RuntimeError, "encerrado"):
                    writers[0].consolidar()

    def test_valida_entrada_antes_da_carga(self):
        for args in ((0, 32, 0), (1, 1, 0), (1, 32, -1), (True, 32, 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                bench.benchmark(*args)

    def test_cli_json_novo_sem_sobrescrita(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "benchmark.json"
            self.assertEqual(bench.main(["--capturas", "1", "2", "--pontos", "32",
                                        "--saida", str(destino)]), 0)
            original = destino.read_bytes()
            resultado = json.loads(original)
            self.assertEqual(len(resultado["series"]), 2)
            self.assertEqual(resultado["series"][0]["origem"], "benchmark_sintetico_nao_fisico")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                bench.main(["--saida", str(destino)])
            self.assertEqual(destino.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
