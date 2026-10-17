"""Recuperação da persistência é anterior à abertura de cada nova sessão."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "logica"))
import cli


class RecuperacaoNaCliTests(unittest.TestCase):
    def test_recupera_antes_de_criar_nova_pasta_sem_tocar_em_hardware(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessao = cli.SessaoCLI()
            def recuperar(pasta):
                self.assertEqual(pasta, base)
                self.assertFalse(list(base.glob("sessao_*")))
                return []
            with mock.patch.object(cli.mestre, "RESULTS_DIR", base), \
                 mock.patch.object(cli.mestre, "BENCH_MODE", False), \
                 mock.patch.object(cli.mestre, "configurar_log_de_sessao"), \
                 mock.patch.object(cli.mestre, "preparar_pasta_da_sessao"), \
                 mock.patch.object(cli.mestre.Bancada, "from_env") as hardware, \
                 mock.patch.object(cli.sessao_io, "recuperar_sessoes_interrompidas", side_effect=recuperar) as recovery:
                try:
                    sessao._garantir_pasta_sessao()
                    recovery.assert_called_once_with(base)
                    hardware.assert_not_called()
                    self.assertEqual(len(list(base.glob("sessao_*"))), 1)
                finally:
                    sessao._liberar_bloqueio_sessao()

    def test_clis_no_mesmo_segundo_nao_reutilizam_arquivos(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            primeira, segunda = cli.SessaoCLI(), cli.SessaoCLI()
            primeira._sessao_timestamp = segunda._sessao_timestamp = "timestamp_igual"
            with mock.patch.object(cli.mestre, "RESULTS_DIR", base), \
                 mock.patch.object(cli.mestre, "BENCH_MODE", False), \
                 mock.patch.object(cli.mestre, "configurar_log_de_sessao"), \
                 mock.patch.object(cli.mestre, "preparar_pasta_da_sessao"):
                try:
                    primeira._garantir_pasta_sessao()
                    original = cli.mestre.SESSION_RESULTS_DIR
                    (original / "sentinela.txt").write_text("capturas originais")
                    primeira._liberar_bloqueio_sessao()
                    segunda._garantir_pasta_sessao()
                    self.assertNotEqual(original, cli.mestre.SESSION_RESULTS_DIR)
                    self.assertEqual((original / "sentinela.txt").read_text(), "capturas originais")
                    self.assertEqual(len(list(base.glob("sessao_*"))), 2)
                finally:
                    primeira._liberar_bloqueio_sessao()
                    segunda._liberar_bloqueio_sessao()

    def test_falha_no_setup_libera_bloqueio_antes_de_propagar(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessao = cli.SessaoCLI()
            with mock.patch.object(cli.mestre, "RESULTS_DIR", base), \
                 mock.patch.object(cli.mestre, "configurar_log_de_sessao"), \
                 mock.patch.object(cli.mestre, "preparar_pasta_da_sessao", side_effect=OSError("disco")):
                with self.assertRaisesRegex(OSError, "disco"):
                    sessao._garantir_pasta_sessao()
                self.assertIsNone(sessao._bloqueio_sessao)
                with cli.sessao_io.BloqueioSessao(cli.mestre.SESSION_RESULTS_DIR, escritor=False):
                    pass


if __name__ == "__main__":
    unittest.main()
