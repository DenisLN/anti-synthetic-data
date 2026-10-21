"""Orçamento da P-23: recusa antes de confirmação, pasta ou instrumento."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'logica'))
import cli
import mestre
from politica_traces import LIMITE_ESCRITAS_TRACE_CONEXAO, LimiteEscritasTraceError


class OrcamentoCliTests(unittest.TestCase):
    def setUp(self):
        self.sessao = cli.SessaoCLI()

    def test_tres_caminhos_recusam_excesso_sem_efeitos(self):
        linhas = [('08', 'TRANSIENT', {'escritas_trace': 217, 'total': 19})]
        for entrada in (['08'], ['08,09'], ['all']):
            with self.subTest(entrada=entrada), contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(self.sessao, '_capturas_das_classes', return_value=linhas))
                alvos = [stack.enter_context(mock.patch.object(self.sessao, nome)) for nome in
                         ('confirmar', '_garantir_pasta_sessao', 'autorizar_saida', '_executar_scripts')]
                bancada = stack.enter_context(mock.patch.object(mestre.Bancada, 'from_env'))
                saida = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                self.assertEqual(self.sessao.cmd_run(entrada), 1)
                self.assertIn('217', saida.getvalue())
                self.assertIn(str(LIMITE_ESCRITAS_TRACE_CONEXAO), saida.getvalue())
                self.assertIn('Nada foi energizado', saida.getvalue())
                for alvo in [*alvos, bancada]:
                    alvo.assert_not_called()

    def test_fronteira_216_pede_confirmacao_e_228_recusa_com_plano_real(self):
        for capturas, confirma in ((18, True), (19, False)):
            with self.subTest(capturas=capturas), \
                    mock.patch.object(mestre, 'GRID_FREQUENCY_HZ', 60.), \
                    mock.patch.object(mestre, 'CAPTURAS_OVERRIDE', capturas), \
                    mock.patch.object(mestre, 'PERFIL_TODOS', False), \
                    mock.patch.object(mestre, 'PERFIL', 'literatura'), \
                    mock.patch.object(self.sessao, 'confirmar', return_value=False) as confirmar, \
                    mock.patch.object(mestre.Bancada, 'from_env') as bancada, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.sessao.cmd_run(['08']), 1)
                self.assertEqual(confirmar.called, confirma)
                bancada.assert_not_called()

    def test_estimador_mestre_conta_perfis_conforme_cli(self):
        scripts = mestre._experiment_scripts()
        for todos in (False, True):
            with self.subTest(todos=todos), mock.patch.object(mestre, 'PERFIL_TODOS', todos):
                esperado = sum(info['escritas_trace'] for _, _, info in self.sessao._capturas_das_classes(scripts))
                self.assertEqual(mestre.estimar_escritas_trace_bateria(scripts), esperado)

    def test_main_fisico_recusa_antes_de_criar_pasta_ou_abrir_bancada(self):
        with tempfile.TemporaryDirectory() as pasta, \
                mock.patch.object(mestre, 'RESULTS_DIR', Path(pasta) / 'ainda_nao_criada'), \
                mock.patch.object(mestre, 'BENCH_MODE', True), \
                mock.patch.object(mestre, 'estimar_escritas_trace_bateria', return_value=217), \
                mock.patch.object(mestre.Bancada, 'from_env') as bancada, \
                self.assertLogs('MestreExperimentos', level='INFO'):
            self.assertEqual(mestre.main(), 1)
            bancada.assert_not_called()
            self.assertFalse(mestre.RESULTS_DIR.exists())

    def test_esgotamento_encerra_sem_retry_e_registra_restantes(self):
        # v1.15 (pula-e-segue): o orçamento esgotado não propaga mais; a
        # conexão é encerrada com OUTPUT OFF e a classe corrente e as
        # seguintes ficam em falhas.json como nao_executada_orcamento, sem
        # retry e sem executar a próxima classe.
        executadas = []

        class Falsa:
            nome = 'FALSA'
            def __init__(self, bancada):
                pass
            def executar(self):
                executadas.append('tentativa')
                raise LimiteEscritasTraceError('orçamento esgotado')

        with tempfile.TemporaryDirectory() as pasta:
            config = mestre.replace(mestre._build_config(), results_dir=Path(pasta))
            bancada = mestre.Bancada(None, None, config)
            with mock.patch.object(bancada, '_carregar_classe_experimento', return_value=Falsa), \
                    mock.patch.object(bancada, 'recuperar_estado_seguro') as recuperar:
                resultados = bancada.executar_bateria([Path('08.py'), Path('09.py')], ('literatura',))
            self.assertEqual(executadas, ['tentativa'])
            recuperar.assert_not_called()
            self.assertEqual([r.nao_executada_orcamento for r in resultados], [True, True])
            itens = mestre.ler_falhas(Path(pasta))['itens']
            self.assertEqual([(i['tipo'], i['classe']) for i in itens],
                             [('nao_executada_orcamento', '09')])


if __name__ == '__main__':
    unittest.main()
