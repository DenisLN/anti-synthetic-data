"""Orçamento cumulativo de uploads, sem fonte física nem esperas."""
import unittest
from unittest import mock

import numpy as np

from logica.ametek_orm import AmetekMX30, CommunicationError
from logica.politica_traces import LIMITE_ESCRITAS_TRACE_CONEXAO, LimiteEscritasTraceError


class OrcamentoTracesTests(unittest.TestCase):
    def setUp(self):
        self.fonte = AmetekMX30(simulated=True, max_voltage_rms=10, max_peak_v=100)
        self.forma = np.sin(2 * np.pi * 60 * np.arange(6000) / 30000)

    def programar(self):
        self.fonte.program_capture(self.forma, base_voltage_rms=5, frequency_hz=60)

    def test_captura_inteira_cabe_na_fronteira(self):
        self.assertEqual(LIMITE_ESCRITAS_TRACE_CONEXAO, 216)
        self.fonte.escritas_trace = 204
        self.programar()
        self.assertEqual(self.fonte.escritas_trace, 216)
        self.assertEqual(sum(c.upper().startswith('TRACE:DATA ') for c in self.fonte.command_log), 12)

    def test_captura_inteira_recusada_sem_upload_parcial_ou_mutacao(self):
        self.fonte.escritas_trace = 205
        with mock.patch.object(self.fonte, 'write') as write, \
             mock.patch.object(self.fonte, 'query') as query, \
             mock.patch.object(self.fonte, '_ensure_trace_slots') as slots:
            with self.assertRaises(LimiteEscritasTraceError):
                self.programar()
        for operacao in (write, query, slots):
            operacao.assert_not_called()
        self.assertEqual(self.fonte.escritas_trace, 205)
        self.assertIsNone(self.fonte.ultima_programacao)

    def test_repeticoes_acumulam_e_nao_reiniciam_orcamento(self):
        self.fonte.escritas_trace = 192
        self.programar()
        self.programar()
        antes = list(self.fonte.command_log)
        with self.assertRaises(LimiteEscritasTraceError):
            self.programar()
        self.assertEqual(self.fonte.escritas_trace, 216)
        self.assertEqual(self.fonte.command_log, antes)

    def test_escritas_diretas_e_abreviadas_contam(self):
        for comando in ('TRACe:DATA TCC00,0,1', 'TRAC:DATA TCC01,0,1',
                        ':TRACe:DATA TCC02,0,1'):
            self.fonte.write(comando)
        self.assertEqual(self.fonte.escritas_trace, 3)

    def test_comando_composto_nao_burla_orcamento(self):
        self.fonte.escritas_trace = 215
        for comando in ('TRACe:DATA TCC00,0,1;:TRAC:DATA TCC01,0,1',
                        'TRACe:DATA TCC00,0,1;DATA TCC01,0,1'):
            with self.subTest(comando=comando), self.assertRaises(LimiteEscritasTraceError):
                self.fonte.write(comando)
        self.assertEqual(self.fonte.escritas_trace, 215)
        self.assertEqual(self.fonte.command_log, [])

    def test_ultima_escrita_direta_permitida_proxima_bloqueada(self):
        self.fonte.escritas_trace = 215
        self.fonte.write('TRAC:DATA TCC00,0,1')
        antes = list(self.fonte.command_log)
        with self.assertRaises(LimiteEscritasTraceError):
            self.fonte.write('TRAC:DATA TCC00,0,1')
        self.assertEqual(self.fonte.escritas_trace, 216)
        self.assertEqual(self.fonte.command_log, antes)

    def test_timeout_de_envio_consume_tentativa_incerta(self):
        self.fonte.simulated = False
        self.fonte._connected = True
        self.fonte._resource = mock.Mock()
        self.fonte._resource.write_raw.side_effect = TimeoutError('envio pode ter chegado')
        with self.assertRaises(CommunicationError):
            self.fonte.write('TRACe:DATA TCC00,0,1')
        self.assertEqual(self.fonte.escritas_trace, 1)
        self.fonte.simulated = True

    def test_consultas_definicao_e_exclusao_nao_contam_como_data(self):
        for comando in ('TRACe:DATA? TCC00', 'TRAC:DATA? TCC00',
                        'TRACe:DEFine TCC00', 'TRACe:DELete TCC00', 'ABORt'):
            self.fonte.write(comando)
        self.assertEqual(self.fonte.escritas_trace, 0)

    def preparar_cache(self):
        self.programar()
        self.fonte.escritas_trace = 216
        self.fonte.simulated = False

    def test_cache_confirmado_permite_reuso_sem_novos_uploads(self):
        self.preparar_cache()
        original_write, original_query = self.fonte.write, self.fonte.query

        def write_simulado(comando):
            self.fonte.simulated = True
            try:
                return original_write(comando)
            finally:
                self.fonte.simulated = False

        def query_simulada(comando):
            self.fonte.simulated = True
            try:
                return original_query(comando)
            finally:
                self.fonte.simulated = False

        inicio = len(self.fonte.command_log)
        with mock.patch.object(self.fonte, 'write', side_effect=write_simulado), \
             mock.patch.object(self.fonte, 'query', side_effect=query_simulada), \
             mock.patch.object(self.fonte, '_ensure_trace_slots') as slots:
            self.programar()
        slots.assert_not_called()
        self.assertFalse(any(c.upper().startswith('TRACE:DATA ') for c in self.fonte.command_log[inicio:]))
        self.assertEqual(self.fonte.escritas_trace, 216)
        self.assertIsNotNone(self.fonte._last_capture_signature)
        self.fonte.simulated = True

    def test_cache_nao_confirmado_recusa_antes_mutacoes_e_preserva_assinatura(self):
        self.preparar_cache()
        assinatura = self.fonte._last_capture_signature
        with mock.patch.object(self.fonte, '_trace_catalog_contains', return_value=False) as catalogo, \
             mock.patch.object(self.fonte, 'write') as write, \
             mock.patch.object(self.fonte, '_ensure_trace_slots') as slots:
            with self.assertRaises(LimiteEscritasTraceError):
                self.programar()
        catalogo.assert_called_once()
        write.assert_not_called()
        slots.assert_not_called()
        self.assertEqual(self.fonte._last_capture_signature, assinatura)
        self.fonte.simulated = True

    def test_escrita_direta_invalida_assinatura_mesmo_se_envio_falha(self):
        self.programar()
        self.assertIsNotNone(self.fonte._last_capture_signature)
        self.fonte.simulated = False
        self.fonte._connected = True
        self.fonte._resource = mock.Mock()
        self.fonte._resource.write_raw.side_effect = TimeoutError('incerto')
        with self.assertRaises(CommunicationError):
            self.fonte.write('TRAC:DATA TCC00,0,1')
        self.assertIsNone(self.fonte._last_capture_signature)
        self.assertEqual(self.fonte.escritas_trace, 13)
        self.fonte.simulated = True


if __name__ == '__main__':
    unittest.main()
