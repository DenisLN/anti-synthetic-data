"""P06: readback da classe 18 após STEP/PULSe na mesma conexão."""
import unittest

from logica.ametek_orm import AmetekMX30, InstrumentHardwareError


class FrequenciaReadbackTests(unittest.TestCase):
    def fonte(self):
        return AmetekMX30(simulated=True, max_voltage_rms=300, max_peak_v=415.8)

    def preparar_drift(self, fonte):
        fonte.frequency_drift_list(57, 63, voltage_rms=127, dwell_s=.1)

    def test_step_e_pulso_seguidos_de_drift_armam_sem_expectativas_residuais(self):
        for anterior in ('STEP', 'PULSe'):
            with self.subTest(anterior=anterior):
                fonte = self.fonte()
                if anterior == 'STEP':
                    fonte.trigger_step(127)
                else:
                    fonte.trigger_pulse(90, width_s=.04)
                # Executa o ciclo de trigger simulado inteiro na mesma
                # instância, antes de preparar a classe18.
                fonte.arm(timeout_s=.1)
                fonte.trigger()
                self.assertEqual(fonte.query('TRIGger:STATe?'), 'IDLE')
                self.preparar_drift(fonte)
                marca = len(fonte.command_log)
                fonte.arm(timeout_s=.1)
                self.assertEqual(fonte.query('TRIGger:STATe?'), 'ARM')
                comandos = fonte.command_log[marca:]
                self.assertNotIn('VOLTage:TRIGgered?', comandos)
                self.assertNotIn('PULSe:WIDTh?', comandos)
                inicio = comandos.index('INITiate:IMMediate')
                for query in ('VOLTage:MODE?', 'FUNCtion:MODE?', 'SOURce:FREQuency:MODE?',
                              'SOURce:LIST:FREQuency:POINts?', 'SOURce:LIST:VOLTage:POINts?',
                              'SOURce:LIST:DWELl:POINts?'):
                    self.assertLess(comandos.index(query), inicio)

    def test_modo_ou_lista_errados_ainda_recusam_antes_de_init(self):
        corrupcoes = ('VOLTage:MODE FIXed', 'FUNCtion:MODE LIST',
                      'FREQuency:MODE FIXed', 'LIST:FREQuency 57',
                      'LIST:VOLTage 127', 'LIST:DWELl .1')
        for comando in corrupcoes:
            with self.subTest(comando=comando):
                fonte = self.fonte()
                fonte.trigger_step(127)
                self.preparar_drift(fonte)
                # Injeta divergência via o próprio protocolo do simulador:
                # readback resulta do estado que o comando efetivamente mudou.
                fonte.write(comando)
                marca = len(fonte.command_log)
                with self.assertRaises(InstrumentHardwareError):
                    fonte.arm(timeout_s=.1)
                self.assertNotIn('INITiate:IMMediate', fonte.command_log[marca:])

    def test_drift_para_pulso_restaura_validacao_nativa(self):
        fonte = self.fonte()
        self.preparar_drift(fonte)
        fonte.arm(timeout_s=.1)
        fonte.trigger()
        fonte.trigger_pulse(90, width_s=.04)
        fonte.arm(timeout_s=.1)
        self.assertEqual(fonte.query('TRIGger:STATe?'), 'ARM')
        self.assertEqual(fonte.query('SOURce:FREQuency:MODE?'), 'FIXED')
        self.assertEqual(fonte._transiente_esperado['VOLTage:MODE?'], 'PULS')
        self.assertNotIn('SOURce:LIST:FREQuency:POINts?', fonte._transiente_esperado)


if __name__ == '__main__':
    unittest.main()
