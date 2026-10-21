"""Snapshot da mesma consulta e arquivo de diagnóstico separado, sem hardware."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np
from pymeasure.adapters import Adapter

from logica.oscilloscope_orm import KeysightDSOX4034A, OscilloscopeError
from logica import bruto_osciloscopio_io as bruto_io


class _Adapter(Adapter):
    def __init__(self):
        super().__init__()
        self.commands = []
        self.preamble = '0,0,12000,1,0.000016666666666666667,-0.02,0,0.01,0,128'
        self.codigos = (20 + np.arange(12000) % 200).astype(np.uint8)
        self.connection = SimpleNamespace(
            query_binary_values=mock.Mock(side_effect=lambda *a, **kw: self.codigos), close=lambda: None,
        )

    def write(self, command, **kwargs):
        self.commands.append(command)

    def read(self):
        return self.preamble


class BrutoOsciloscopioTests(unittest.TestCase):
    def setUp(self):
        self.adapter = _Adapter()
        self.osc = KeysightDSOX4034A(self.adapter)

    def ler(self, canal=1, preservar=True):
        return self.osc.get_waveform(canal, preservar_bruto=preservar)

    def test_retorno_identico_e_uma_unica_consulta_binaria(self):
        t_atual, y_atual = self.ler(preservar=False)
        comandos = list(self.adapter.commands)
        self.adapter.commands.clear()
        self.adapter.connection.query_binary_values.reset_mock()
        t_novo, y_novo = self.ler()
        np.testing.assert_array_equal(t_novo, t_atual)
        np.testing.assert_array_equal(y_novo, y_atual)
        self.assertEqual(self.adapter.commands, comandos)
        self.adapter.connection.query_binary_values.assert_called_once()
        bruto = self.osc.consumir_waveform_bruto(1)
        self.assertEqual(bruto['tempo_s'][0], 0)
        self.assertEqual(bruto['tempo_trigger_s'][0], -0.02)
        self.assertEqual(bruto['codigos_byte'].dtype, np.uint8)
        np.testing.assert_array_equal(bruto['valores'], (self.adapter.codigos.astype(float) - 128) * .01)
        np.testing.assert_array_equal(y_novo, np.interp(t_novo, bruto['tempo_s'], bruto['valores']))
        self.assertEqual(bruto['preamble_texto'], self.adapter.preamble)
        self.assertEqual(bruto['preamble'].shape, (10,))
        self.assertIsNone(self.osc.consumir_waveform_bruto(1))

    def test_snapshot_copia_buffers_e_separa_canais(self):
        self.ler(1)
        self.ler(2)
        self.adapter.codigos[:] = 99
        primeiro = self.osc.consumir_waveform_bruto(1)
        segundo = self.osc.consumir_waveform_bruto(2)
        self.assertEqual(primeiro['canal'], 1)
        self.assertEqual(segundo['canal'], 2)
        self.assertEqual(primeiro['codigos_byte'][0], 20)
        primeiro['valores'][0] = 12345
        self.assertNotEqual(segundo['valores'][0], 12345)

    def test_leitura_sem_preservar_remove_snapshot_anterior(self):
        self.ler()
        self.ler(preservar=False)
        self.assertIsNone(self.osc.consumir_waveform_bruto(1))

    def test_falha_de_leitura_remove_snapshot_anterior(self):
        self.ler()
        self.adapter.connection.query_binary_values.side_effect = TimeoutError('teste')
        with self.assertRaises(TimeoutError):
            self.ler()
        self.assertIsNone(self.osc.consumir_waveform_bruto(1))

    def test_clipping_nao_publica_snapshot(self):
        self.adapter.codigos[8] = 255
        with self.assertRaises(OscilloscopeError):
            self.ler()
        self.assertIsNone(self.osc.consumir_waveform_bruto(1))

    def test_npz_independente_sem_pickle_com_hash_vinculo_e_perfis(self):
        _, salvo = self.ler()
        bruto = self.osc.consumir_waveform_bruto(1)
        with tempfile.TemporaryDirectory() as pasta:
            original = Path(pasta) / '01_normal.npz'
            original.write_bytes(b'dataset intocado')
            relativo = bruto_io.salvar_bruto(pasta, 'literatura', '01-0001', 1, bruto, salvo,
                                             metadata_extra={'simulado': True, 'unidade_sinal_salvo': 'V'})
            repetido = bruto_io.salvar_bruto(pasta, 'literatura', '01-0001', 1, bruto, salvo)
            perfil = bruto_io.salvar_bruto(pasta, 'norma', '01-0001', 1, bruto, salvo)
            self.assertFalse(relativo.is_absolute())
            self.assertNotEqual(relativo, repetido)
            self.assertNotEqual(relativo, perfil)
            self.assertEqual(original.read_bytes(), b'dataset intocado')
            with np.load(Path(pasta) / relativo, allow_pickle=False) as dados:
                for campo in dados.files:
                    self.assertNotEqual(dados[campo].dtype, object)
                np.testing.assert_array_equal(dados['tensao_v'], bruto['valores'])
                np.testing.assert_array_equal(dados['tempo_trigger_s'], bruto['tempo_trigger_s'])
                meta = json.loads(str(dados['metadata_json']))
                self.assertEqual(meta['sinal_salvo_sha256'], bruto_io.sha256_array(salvo))
                self.assertEqual(meta['id_captura'], '01-0001')
                self.assertEqual(meta['perfil'], 'literatura')
                self.assertTrue(meta['metadata_extra']['simulado'])

    def test_ch2_preserva_unidade_corrente_separada(self):
        _, salvo = self.ler(2)
        bruto = self.osc.consumir_waveform_bruto(2)
        with tempfile.TemporaryDirectory() as pasta:
            relativo = bruto_io.salvar_bruto(pasta, 'norma', '01-0001', 2, bruto, salvo)
            with np.load(Path(pasta) / relativo, allow_pickle=False) as dados:
                np.testing.assert_array_equal(dados['corrente_a'], bruto['valores'])
                self.assertNotIn('tensao_v', dados.files)

    def test_colisao_de_nome_nao_sobrescreve_arquivo_existente(self):
        _, salvo = self.ler()
        bruto = self.osc.consumir_waveform_bruto(1)
        with tempfile.TemporaryDirectory() as pasta, mock.patch.object(bruto_io, 'uuid4', return_value=SimpleNamespace(hex='fixo')):
            relativo = bruto_io.salvar_bruto(pasta, 'norma', '01-0001', 1, bruto, salvo)
            original = (Path(pasta) / relativo).read_bytes()
            with self.assertRaises(FileExistsError):
                bruto_io.salvar_bruto(pasta, 'norma', '01-0001', 1, bruto, salvo)
            self.assertEqual((Path(pasta) / relativo).read_bytes(), original)

    def test_falha_limpa_so_arquivo_criado_pela_tentativa(self):
        _, salvo = self.ler()
        bruto = self.osc.consumir_waveform_bruto(1)
        with tempfile.TemporaryDirectory() as pasta:
            anterior = bruto_io.salvar_bruto(pasta, 'norma', '01-0001', 1, bruto, salvo)
            with mock.patch.object(bruto_io.np, 'savez', side_effect=OSError('disco indisponível')):
                with self.assertRaises(OSError):
                    bruto_io.salvar_bruto(pasta, 'norma', '01-0001', 1, bruto, salvo)
            self.assertEqual(list(Path(pasta).rglob('*.npz')), [Path(pasta) / anterior])

    def test_hash_independe_endian_e_contiguidade(self):
        valores = np.arange(12, dtype=float)[::2]
        self.assertEqual(bruto_io.sha256_array(valores), bruto_io.sha256_array(valores.astype('>f8')))
        self.assertNotEqual(bruto_io.sha256_array(valores), bruto_io.sha256_array(valores + 1))

class IntegracaoBrutoMestreTests(unittest.TestCase):
    def setUp(self):
        import sys
        from dataclasses import replace
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'logica'))
        import mestre
        self.mestre = mestre
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name)
        self.adapter = _Adapter()
        self.osc = KeysightDSOX4034A(self.adapter)
        self.config = replace(mestre._build_config(), results_dir=self.pasta,
                              preservar_bruto_osciloscopio=True,
                              capture_current=True, current_base_a=2.)
        tipo = mestre.Bancada._carregar_classe_experimento(mestre._experiment_scripts()[0])
        self.exp = tipo(mestre.Bancada(mestre.AmetekMX30(simulated=True), self.osc, self.config))
        self.exp._pontos_efetivos_captura_atual = 6000
        self.exp._capture_id_atual = '01-0001'
        self.exp._aquisicao_id_atual = 'aquisicao_teste_sintetico'
        self.exp._seed_captura_atual = 7
        self.exp._pre_trigger_atual_s = None

    def test_mesma_aquisicao_preserva_dois_canais_e_hash_do_pu(self):
        t, tensao, corrente, _ = self.exp._ler_captura({'parametro_teste': 1})
        self.assertEqual(self.adapter.connection.query_binary_values.call_count, 2)
        self.assertEqual(len(self.exp._brutos_atuais), 2)
        for info, sinal, chave in zip(self.exp._brutos_atuais, (tensao, corrente), ('tensao_v', 'corrente_a')):
            self.assertIsNone(info['erro'])
            with np.load(self.pasta / info['arquivo'], allow_pickle=False) as dados:
                self.assertEqual(str(dados['sinal_salvo_sha256']), bruto_io.sha256_array(sinal))
                meta = json.loads(str(dados['metadata_json']))['metadata_extra']
                self.assertEqual(meta['aquisicao_id'], 'aquisicao_teste_sintetico')
                self.assertEqual(meta['seed'], 7)
                self.assertIn('pu_', meta['unidade_sinal_salvo'])
                np.testing.assert_array_equal(np.interp(t, dados['tempo_s'], dados[chave]) / meta['base_sinal_salvo'], sinal)

    def test_exportacao_alimenta_analisador_na_grade_do_dataset(self):
        import importlib.util
        self.exp._ler_captura({})
        entrada = self.pasta / self.exp._brutos_atuais[0]['arquivo']
        script = Path(__file__).resolve().parents[1] / 'scripts' / 'analisar_reamostragem.py'
        spec = importlib.util.spec_from_file_location('analise_bruto_integracao', script)
        analise = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(analise)
        saida = self.pasta / 'analise.json'
        self.assertEqual(analise.main(['--entrada', str(entrada), '--f0-hz', '60',
                                      '--saida', str(saida)]), 0)
        relatorio = json.loads(saida.read_text(encoding='utf-8'))
        self.assertEqual(relatorio['amostras_salvas'], 6000)
        self.assertEqual(relatorio['fs_salvo_hz'], 30000.)
        self.assertIn('arquivo_sha256', relatorio['fonte'])
        self.assertEqual(relatorio['fonte']['metadata_bruto']['id_captura'], '01-0001')
        self.assertIn('thd', relatorio['interior_sem_bordas']['interp'])

    def test_ch1_permanece_preservado_se_ch2_falha(self):
        chamada = self.adapter.connection.query_binary_values.side_effect
        contagem = []
        def ler(*args, **kwargs):
            contagem.append(1)
            if len(contagem) == 2:
                raise TimeoutError('CH2 indisponível')
            return chamada(*args, **kwargs)
        self.adapter.connection.query_binary_values.side_effect = ler
        with self.assertRaises(TimeoutError):
            self.exp._ler_captura({})
        self.assertEqual(len(list(self.pasta.rglob('*.npz'))), 1)
        self.assertEqual(self.exp._brutos_atuais[0]['canal'], 1)
        self.assertIsNone(self.exp._brutos_atuais[0]['erro'])

    def test_falha_diagnostica_nao_perde_a_medida_e_fica_explicita(self):
        with mock.patch.object(self.mestre.bruto_osciloscopio_io, 'salvar_bruto', side_effect=OSError('disco cheio')):
            _, tensao, corrente, _ = self.exp._ler_captura({})
        self.assertEqual(tensao.size, 6000)
        self.assertEqual(corrente.size, 6000)
        self.assertEqual(len(self.exp._brutos_atuais), 2)
        self.assertTrue(all(info['arquivo'] is None and 'disco cheio' in info['erro']
                            for info in self.exp._brutos_atuais))

    def test_flag_desligada_nao_retém_snapshot_nem_cria_arquivos(self):
        from dataclasses import replace
        self.exp.config = replace(self.exp.config, preservar_bruto_osciloscopio=False)
        self.exp._ler_captura({})
        self.assertIsNone(self.osc.consumir_waveform_bruto(1))
        self.assertIsNone(self.osc.consumir_waveform_bruto(2))
        self.assertEqual(list(self.pasta.rglob('*.npz')), [])

    def test_cli_flag_independente_e_config(self):
        import cli
        with mock.patch.object(self.mestre, 'SALVAR_BRUTO_OSCILOSCOPIO', False), \
                mock.patch.object(self.mestre, 'DIAGNOSTICO_RETRIEVE', False), \
                mock.patch.object(self.mestre, 'DIAGNOSTICO_MODE', False):
            sessao = cli.SessaoCLI()
            with mock.patch('builtins.print'):
                self.assertEqual(sessao.cmd_set(['diagnostico', 'bruto']), 0)
                self.assertTrue(self.mestre._build_config().preservar_bruto_osciloscopio)
                self.assertEqual(sessao.cmd_set(['diagnostico', 'bruto', 'talvez']), 1)
                self.assertTrue(self.mestre.SALVAR_BRUTO_OSCILOSCOPIO)
                self.assertEqual(sessao.cmd_set(['diagnostico', 'bruto', 'off']), 0)
            self.assertFalse(self.mestre._build_config().preservar_bruto_osciloscopio)
            self.assertFalse(self.mestre.DIAGNOSTICO_RETRIEVE)
            self.assertFalse(self.mestre.DIAGNOSTICO_MODE)


if __name__ == "__main__":
    unittest.main()
