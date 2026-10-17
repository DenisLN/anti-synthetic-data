"""Análise de representação offline: sem hardware nem decisões de aceite."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

from scripts import analisar_modelo_programado as analise


class ModeloProgramadoTests(unittest.TestCase):
    def test_offset_conhecido_quantifica_media_perdida(self):
        t = np.arange(6000) / 30000
        forma = np.sin(2 * np.pi * 60 * t) + .2
        r = analise.analisar_forma(forma, frequency_hz=60)
        self.assertAlmostEqual(r['erro_rms_pu'], .2, places=6)
        np.testing.assert_allclose(r['media_perdida_por_ciclo_pu'], .2, atol=1e-7)
        self.assertAlmostEqual(r['erro_rms_v'], .2 * 127 * np.sqrt(2), places=4)
        self.assertIsNone(r['correlacao_disturbio_nominal']['valor'])
        self.assertIsNotNone(r['correlacao_disturbio_nominal']['motivo_indefinida'])

    def test_senoide_com_fase_tem_erro_pequeno(self):
        t = np.arange(6000) / 30000
        forma = np.sin(2 * np.pi * 50 * t + .37)
        r = analise.analisar_forma(forma, frequency_hz=50, fase_graus=np.degrees(.37))
        self.assertLess(r['erro_rms_pu'], 2e-5)
        self.assertLess(r['erro_maximo_pu'], 3e-5)
        np.testing.assert_allclose(r['modelo']['envelope_fundamental_ajustada_por_ciclo_pu'], 1, atol=1e-12)
        self.assertEqual(r['pontos_por_ciclo'], 600)

    def test_cobertura_completa_e_reprodutibilidade_sem_io(self):
        with mock.patch.object(analise.AmetekMX30, 'program_capture', side_effect=AssertionError('hardware proibido')), \
             mock.patch.object(analise.AmetekMX30, 'connect', side_effect=AssertionError('hardware proibido')):
            r = analise.gerar_relatorio(seeds=(77,))
            repeticao = analise.gerar_relatorio(classes=('15',), perfis_selecionados=('fronteira',),
                                               frequencias=(60.,), seeds=(77,))
        self.assertEqual(len(r['registros']), 36)
        self.assertEqual({p['classe'] for p in r['registros']}, set(analise.CLASSES))
        esperado = next(p for p in r['registros'] if p['classe'] == '15' and
                        p['perfil'] == 'fronteira' and p['frequency_hz'] == 60.)
        self.assertEqual(esperado, repeticao['registros'][0])
        for caso in r['registros']:
            self.assertEqual(caso['fs_hz'], 30000)
            self.assertEqual(caso['amostras'], 6000)
            self.assertIn('fase_graus', caso['parametros_modelo'])
            self.assertNotIn('aprovado', caso)
        json.dumps(r, allow_nan=False)

    def test_cli_exige_arquivo_e_preserva_existente(self):
        with tempfile.TemporaryDirectory() as pasta:
            saida = Path(pasta) / 'relatorio.json'
            args = ['--classes', '06', '--perfis', 'norma', '--frequencias', '50',
                    '--seeds', '42', '--saida', str(saida)]
            self.assertEqual(analise.main(args), 0)
            conteudo = saida.read_text()
            r = json.loads(conteudo)
            self.assertEqual(r['tipo'], 'simulacao_offline_modelo_vs_programada')
            self.assertEqual(r['registros'][0]['seed'], 42)
            with self.assertRaises(SystemExit):
                analise.main(args)
            self.assertEqual(saida.read_text(), conteudo)


if __name__ == '__main__':
    unittest.main()
