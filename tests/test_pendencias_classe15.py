"""Metadata físico da redução de HARMONICS + FLICKER (P11)."""
import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'logica') not in sys.path:
    sys.path.insert(0, str(ROOT / 'logica'))
spec = importlib.util.spec_from_file_location('classe15_pendencias', ROOT / 'experimentos_waveform/15.py')
modulo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modulo)


class Classe15MetadataTests(unittest.TestCase):
    def setUp(self):
        # O gancho é puro e não requer sessão, config ou instrumento.
        self.experimento = object.__new__(modulo.Experimento)
        self.parametros = {'thd': .25, 'flicker_depth': .18, 'flicker_hz': 8.8}

    def test_sem_disturbio(self):
        p = self.experimento.parametros_com_disturbio_reduzido(self.parametros, 0)
        self.assertTrue(all(valor == 0 for valor in p.values()))

    def test_sem_reducao(self):
        p = self.experimento.parametros_com_disturbio_reduzido(self.parametros, 1)
        self.assertEqual(p['flicker_depth_bancada'], .18)
        for chave in ('thd_bancada_min', 'thd_bancada_centro', 'thd_bancada_max'):
            self.assertAlmostEqual(p[chave], .25)

    def test_thd_local_variavel_na_fracao_intermediaria(self):
        p = self.experimento.parametros_com_disturbio_reduzido(self.parametros, .4)
        self.assertNotIn('thd_bancada', p)
        self.assertLess(p['thd_bancada_min'], p['thd_bancada_centro'])
        self.assertLess(p['thd_bancada_centro'], p['thd_bancada_max'])
        self.assertAlmostEqual(p['flicker_depth_bancada'], .072)
        self.assertAlmostEqual(p['thd_bancada_min'], .4 * .25 * .82 / .928)
        self.assertAlmostEqual(p['thd_bancada_max'], .4 * .25 * 1.18 / 1.072)

    def test_reconstrucao_exata_com_fase_e_todos_os_envelopes(self):
        t = np.arange(6000) / 30000
        seno = np.sin(2 * np.pi * 60 * (t + .0037))
        # Componentes explícitas: THD do conjunto é sqrt(a3² + a5²).
        harmonicos = .2 * np.sin(2 * np.pi * 180 * (t + .0037))
        harmonicos += .15 * np.sin(2 * np.pi * 300 * (t + .0037))
        d = self.parametros['flicker_depth']
        m = np.sin(2 * np.pi * self.parametros['flicker_hz'] * t)
        modelo = (1 + d * m) * (seno + harmonicos)
        original = dict(self.parametros)
        for f in (0, .01, .4, .8, 1):
            with self.subTest(fracao=f):
                p = self.experimento.parametros_com_disturbio_reduzido(self.parametros, f)
                fundamental = 1 + p['flicker_depth_bancada'] * m
                envelope_h = p['harmonicos_envelope_centro_bancada']
                envelope_h += p['harmonicos_envelope_modulacao_bancada'] * m
                reconstruida = fundamental * seno + envelope_h * harmonicos
                np.testing.assert_allclose(reconstruida, seno + f * (modelo - seno), atol=1e-15)
                thd_local = .25 * envelope_h / fundamental
                self.assertTrue(np.all(thd_local >= p['thd_bancada_min'] - 1e-15))
                self.assertTrue(np.all(thd_local <= p['thd_bancada_max'] + 1e-15))
                for fase, chave in ((-1, 'thd_bancada_min'), (1, 'thd_bancada_max')):
                    razao = .25 * f * (1 + d * fase) / (1 + f * d * fase)
                    self.assertAlmostEqual(razao, p[chave])
        self.assertEqual(self.parametros, original)

    def test_flicker_nulo_deixa_thd_constante(self):
        parametros = dict(self.parametros, flicker_depth=0)
        p = self.experimento.parametros_com_disturbio_reduzido(parametros, .4)
        for chave in ('thd_bancada_min', 'thd_bancada_centro', 'thd_bancada_max'):
            self.assertAlmostEqual(p[chave], .1)

    def test_entradas_fora_do_dominio_fisico(self):
        for f in (-.1, 1.1, np.nan, np.inf):
            with self.subTest(fracao=f), self.assertRaises(ValueError):
                self.experimento.parametros_com_disturbio_reduzido(self.parametros, f)
        for d in (-.1, 1, np.nan, np.inf):
            with self.subTest(profundidade=d), self.assertRaises(ValueError):
                self.experimento.parametros_com_disturbio_reduzido(dict(self.parametros, flicker_depth=d), .4)


if __name__ == '__main__':
    unittest.main()
