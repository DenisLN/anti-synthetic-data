"""Recusas offline da P04: limites aplicados antes de tocar a fonte."""
import math
import unittest
from unittest import mock

import numpy as np

from logica.ametek_orm import AmetekMX30, ParameterOutOfBoundsError


class LimitesCapturaTests(unittest.TestCase):
    def setUp(self):
        self.fonte = AmetekMX30(simulated=True, max_voltage_rms=10, max_peak_v=100)
        self.forma = np.sin(2 * np.pi * 60 * np.arange(6000) / 30000)

    def recusa_sem_io(self, forma=None, **kwargs):
        parametros = dict(base_voltage_rms=5, frequency_hz=60)
        parametros.update(kwargs)
        with mock.patch.object(self.fonte, 'write') as write, \
             mock.patch.object(self.fonte, 'query') as query, \
             mock.patch.object(self.fonte, '_ensure_trace_slots') as slots, \
             mock.patch.object(self.fonte, '_trace_catalog_contains') as catalog:
            with self.assertRaises(ParameterOutOfBoundsError):
                self.fonte.program_capture(self.forma if forma is None else forma, **parametros)
            for operacao in (write, query, slots, catalog):
                operacao.assert_not_called()
        self.assertEqual(self.fonte.command_log, [])
        self.assertIsNone(self.fonte.ultima_programacao)
        self.assertEqual(self.fonte.escritas_trace, 0)

    def test_pico_entrada_acima_limite(self):
        self.fonte.max_peak_v = 7
        self.recusa_sem_io()

    def test_rms_de_um_ciclo_acima_limite(self):
        # Base segura, mas apenas o último ciclo tem amplitude excessiva.
        forma = self.forma.copy()
        forma[-500:] *= 3
        self.recusa_sem_io(forma)

    def test_pico_reconstruido_excede_entrada_por_reamostragem(self):
        forma = np.tile(np.r_[np.ones(250), -np.ones(250)], 12)
        plano = self.fonte.montar_programacao(forma, base_voltage_rms=5, frequency_hz=60)
        pico_entrada = 5 * math.sqrt(2)
        self.assertGreater(plano.pico_reconstruido_v, pico_entrada)
        self.fonte.max_peak_v = (pico_entrada + plano.pico_reconstruido_v) / 2
        self.recusa_sem_io(forma)

    def test_offset_incluido_no_pico_reconstruido(self):
        # Média da captura removida na TRACE: offset explícito é adicionado
        # novamente pela fonte, mesmo quando o sinal de entrada é centrado.
        self.fonte.max_peak_v = 8
        self.recusa_sem_io(dc_offset_pu=0.5)

    def test_parametros_invalidos_e_nao_finitos(self):
        for nome in ('base_voltage_rms', 'frequency_hz'):
            for valor in (0, -1, math.nan, math.inf, -math.inf, 'inválido'):
                with self.subTest(nome=nome, valor=valor):
                    self.recusa_sem_io(**{nome: valor})
        for valor in (math.nan, math.inf, -math.inf):
            with self.subTest(offset=valor):
                self.recusa_sem_io(dc_offset_pu=valor)
        for valor in (math.nan, math.inf, -math.inf):
            forma = self.forma.copy()
            forma[17] = valor
            self.recusa_sem_io(forma)
        self.recusa_sem_io(np.zeros(5999))
        self.recusa_sem_io(frequency_hz=1e-300)
        self.recusa_sem_io(frequency_hz=1e300)

    def test_tensao_base_acima_limite_mesmo_captura_nula(self):
        self.recusa_sem_io(np.zeros(6000), base_voltage_rms=10.00001)

    def test_frequencias_fora_da_faixa_fisica_recusam_antes_de_io(self):
        # Todas fecham ciclos inteiros na grade, mas isso não as torna
        # frequências aceitas pelo instrumento (mesma faixa do setter).
        for hz in (10, 1000, 30000):
            with self.subTest(hz=hz):
                forma = np.sin(2 * np.pi * hz * np.arange(6000) / 30000)
                self.recusa_sem_io(forma, frequency_hz=hz)

    def test_faixa_fisica_ainda_exige_ciclos_inteiros_na_grade(self):
        # 45 Hz é o limite físico inferior, mas não fecha ciclos de
        # amostras inteiras; 50 Hz fecha. 500 Hz fecha ciclos, mas pede 100
        # passos de LIST (> 32, manual p. 153): recusado antes de I/O (v1.15).
        self.recusa_sem_io(frequency_hz=45)
        self.recusa_sem_io(np.sin(2 * np.pi * 500 * np.arange(6000) / 30000), frequency_hz=500)
        for hz in (50,):
            with self.subTest(hz=hz):
                fonte = AmetekMX30(simulated=True, max_voltage_rms=10, max_peak_v=100)
                forma = np.sin(2 * np.pi * hz * np.arange(6000) / 30000)
                fonte.program_capture(forma, base_voltage_rms=5, frequency_hz=hz)
                self.assertIsNotNone(fonte.ultima_programacao)
                self.assertEqual(fonte.escritas_trace, hz // 5)

    def test_pico_da_base_imediata_respeita_limite_mesmo_captura_nula(self):
        self.fonte.max_peak_v = 7
        self.recusa_sem_io(np.zeros(6000))

    def test_senoide_imediata_com_dc_recusa_antes_de_io_em_ambos_modos(self):
        for passo_final in (False, True):
            for offset in (-.1, .1):
                with self.subTest(passo_final=passo_final, offset=offset):
                    self.fonte.passo_final_sin = passo_final
                    self.fonte.max_peak_v = 7.2
                    self.recusa_sem_io(.1 * self.forma + offset, dc_offset_pu=offset)

    def test_fronteira_exata_senoide_imediata_com_dc_e_aceita(self):
        for passo_final in (False, True):
            for offset in (-.1, .1):
                with self.subTest(passo_final=passo_final, offset=offset):
                    self.fonte = AmetekMX30(
                        simulated=True, max_voltage_rms=10,
                        max_peak_v=5 * math.sqrt(2) * (1 + abs(offset)),
                        passo_final_sin=passo_final,
                    )
                    self.fonte.program_capture(
                        .1 * self.forma + offset, base_voltage_rms=5,
                        frequency_hz=60, dc_offset_pu=offset,
                    )
                    self.assertIsNotNone(self.fonte.ultima_programacao)
                    self.assertEqual(self.fonte.escritas_trace, 12)

    def test_fronteiras_exatas_sao_aceitas(self):
        plano = self.fonte.montar_programacao(self.forma, base_voltage_rms=5, frequency_hz=60)
        self.fonte.max_voltage_rms = max(5, float(np.max(plano.list_voltages_rms)))
        self.fonte.max_peak_v = max(5 * math.sqrt(2), plano.pico_reconstruido_v)
        self.fonte.program_capture(self.forma, base_voltage_rms=5, frequency_hz=60)
        self.assertIsNotNone(self.fonte.ultima_programacao)
        self.assertEqual(self.fonte.escritas_trace, 12)

    def test_cache_nao_contorna_limites_reduzidos(self):
        self.fonte.simulated = False
        plano = self.fonte.montar_programacao(self.forma, base_voltage_rms=5, frequency_hz=60)
        self.fonte._last_capture_signature = (self.forma.tobytes(), plano.trace_names, 5., 60., 0.)
        self.fonte._last_capture_list_voltages = list(plano.list_voltages_rms)
        self.fonte._last_capture_peak_v = plano.pico_reconstruido_v
        for limite, valor in (('max_peak_v', 7.), ('max_voltage_rms', 4.9)):
            with self.subTest(limite=limite):
                with mock.patch.object(self.fonte, limite, valor):
                    self.recusa_sem_io()

    def test_cache_nao_reutiliza_rms_ou_pico_desatualizados(self):
        plano = self.fonte.montar_programacao(self.forma, base_voltage_rms=5, frequency_hz=60)
        self.fonte.simulated = False
        self.fonte._last_capture_signature = (self.forma.tobytes(), plano.trace_names, 5., 60., 0.)
        self.fonte._last_capture_list_voltages = [999.] * plano.ciclos
        self.fonte._last_capture_peak_v = 999.
        with mock.patch.object(self.fonte, '_trace_catalog_contains', return_value=True), \
             mock.patch.object(self.fonte, 'write') as write, \
             mock.patch.object(self.fonte, 'check_errors', return_value=[]), \
             mock.patch.object(self.fonte, 'query', return_value='12'):
            self.fonte.program_capture(self.forma, base_voltage_rms=5, frequency_hz=60)
        self.assertEqual(self.fonte.last_programmed_peak_v, plano.pico_reconstruido_v)
        comandos = [c.args[0] for c in write.call_args_list]
        self.assertIn('SOURce:LIST:VOLTage ' + plano.texto_list_voltages(), comandos)
        self.assertFalse(any(c.startswith('TRACe:DATA') for c in comandos))


if __name__ == '__main__':
    unittest.main()
