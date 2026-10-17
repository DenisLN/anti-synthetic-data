"""Contrato atualizado P14: seleção inequívoca antes de acessar a bancada."""

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

LOGICA_DIR = Path(__file__).resolve().parent.parent / "logica"
if str(LOGICA_DIR) not in sys.path:
    sys.path.insert(0, str(LOGICA_DIR))

import cli
import mestre


class PendenciasCLI(unittest.TestCase):
    def setUp(self):
        self.sessao = cli.SessaoCLI()

    def rodar(self, args):
        texto = io.StringIO()
        with contextlib.redirect_stdout(texto):
            codigo = self.sessao.cmd_run(args)
        return codigo, texto.getvalue()

    def test_argumentos_ambiguos_recusados_antes_de_confirmacao_ou_contato(self):
        for args in (["01", "02"], ["all", "extras"], ["ALL", "01-03"],
                     ["SAG", "SWELL"], ["1", "2,3"], ["01-03", "05"],
                     ["01", "02-03"], ["01-03,", "0", "5"]):
            with self.subTest(args=args), \
                    mock.patch.object(self.sessao, "confirmar") as confirmar, \
                    mock.patch.object(self.sessao, "autorizar_saida") as armar, \
                    mock.patch.object(self.sessao, "_garantir_pasta_sessao") as pasta, \
                    mock.patch.object(mestre.Bancada, "from_env") as bancada:
                codigo, texto = self.rodar(args)
                self.assertEqual(codigo, 1)
                self.assertIn("Nada foi energizado", texto)
                confirmar.assert_not_called()
                armar.assert_not_called()
                pasta.assert_not_called()
                bancada.assert_not_called()

    def test_espacos_em_torno_de_separadores_preservam_selecao(self):
        with mock.patch.object(mestre, "BATERIA_EXCLUIR", ()), \
                mock.patch.object(self.sessao, "confirmar", return_value=False) as confirmar, \
                mock.patch.object(mestre.Bancada, "from_env") as bancada:
            codigo, _ = self.rodar(["01", "-", "03", ",", "05"])
        self.assertEqual(codigo, 1)
        self.assertEqual(confirmar.call_args.args[1], "EXECUTAR-CLASSES-01-03,05")
        bancada.assert_not_called()

    def test_exclusoes_definem_confirmacao_capturas_e_execucao_efetivas(self):
        with mock.patch.object(mestre, "BATERIA_EXCLUIR", ("02",)), \
                mock.patch.object(self.sessao, "confirmar", return_value=True) as confirmar, \
                mock.patch.object(self.sessao, "autorizar_saida") as armar, \
                mock.patch.object(self.sessao, "_garantir_pasta_sessao"), \
                mock.patch.object(self.sessao, "_fim_da_sessao"), \
                mock.patch.object(mestre.Bancada, "from_env") as from_env:
            bancada = from_env.return_value.__enter__.return_value
            bancada.executar_bateria.return_value = [
                mestre.ResultadoClasse("01", "NORMAL", ok=True),
                mestre.ResultadoClasse("03", "SWELL", ok=True),
            ]
            codigo, texto = self.rodar(["03,01-02"])
        self.assertEqual(codigo, 0)
        self.assertEqual(confirmar.call_args.args[1], "EXECUTAR-CLASSES-01,03")
        self.assertIn("classes 01,03 (2 classes", confirmar.call_args.args[0])
        self.assertIn("Classes removidas por BATERIA_EXCLUIR: 02", texto)
        self.assertIn("  01  ", texto)
        self.assertIn("  03  ", texto)
        self.assertNotIn("  02  ", texto)
        self.assertEqual([p.stem for p in bancada.executar_bateria.call_args.args[0]], ["01", "03"])
        self.assertEqual(armar.call_args_list, [mock.call(True), mock.call(False)])

    def test_exclusoes_totais_cancelam_sem_confirmacao_ou_bancada(self):
        for args in (["01-02"], ["all"]):
            with self.subTest(args=args), \
                    mock.patch.object(mestre, "BATERIA_EXCLUIR", tuple(f"{n:02d}" for n in range(1, 21))), \
                    mock.patch.object(self.sessao, "confirmar") as confirmar, \
                    mock.patch.object(self.sessao, "autorizar_saida") as armar, \
                    mock.patch.object(mestre.Bancada, "from_env") as bancada:
                codigo, texto = self.rodar(args)
                self.assertEqual(codigo, 1)
                self.assertIn("Nenhuma classe restante", texto)
                confirmar.assert_not_called()
                armar.assert_not_called()
                bancada.assert_not_called()

    def test_classe_isolada_excluida_continua_exigindo_confirmacao_individual(self):
        with mock.patch.object(mestre, "BATERIA_EXCLUIR", ("02",)), \
                mock.patch.object(self.sessao, "confirmar", return_value=False) as confirmar, \
                mock.patch.object(mestre.Bancada, "from_env") as bancada:
            codigo, _ = self.rodar(["02"])
        self.assertEqual(codigo, 1)
        self.assertEqual(confirmar.call_args.args[1], "EXECUTAR-CLASSE-02")
        bancada.assert_not_called()


if __name__ == "__main__":
    unittest.main()
