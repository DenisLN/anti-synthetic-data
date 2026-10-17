"""P18: integração experimental do passo SINE sem perder a validação P04."""
import math
from pathlib import Path
import sys
import unittest
from unittest import mock

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "logica"))
from ametek_orm import AmetekMX30, ParameterOutOfBoundsError


class PassoFinalSineTests(unittest.TestCase):
    @staticmethod
    def fonte(**kwargs):
        return AmetekMX30(simulated=True, max_voltage_rms=10., max_peak_v=100., **kwargs)

    @staticmethod
    def forma(freq=60.):
        t = np.arange(6000) / 30000.
        return np.sin(2 * np.pi * freq * t) * np.linspace(1., .6, 6000)

    def test_experimental_desligado_por_padrao(self):
        fonte = self.fonte()
        self.assertFalse(fonte.passo_final_sin)
        fonte.program_capture(self.forma(), base_voltage_rms=5., frequency_hz=60.)
        self.assertEqual(fonte._last_cycles, 12)
        self.assertNotIn(",SINE", "\n".join(fonte.command_log))

    def test_listas_doze_ou_treze_passos_sem_flash_extra(self):
        for ligado in (False, True):
            with self.subTest(ligado=ligado):
                fonte = self.fonte(passo_final_sin=ligado)
                fonte.program_capture(self.forma(), base_voltage_rms=5., frequency_hz=60.)
                esperado = 12 + int(ligado)
                for campo in ("FUNCtion:SHAPe", "VOLTage", "DWELl", "REPeat"):
                    comando = next(c for c in fonte.command_log if c.startswith(f"SOURce:LIST:{campo} "))
                    valores = comando.split(" ", 1)[1].split(",")
                    self.assertEqual(len(valores), esperado)
                    if campo == "REPeat":
                        self.assertEqual(valores, ["0"] * esperado)
                    elif campo == "DWELl":
                        np.testing.assert_allclose([float(v) for v in valores], 1 / 60.)
                    elif campo == "FUNCtion:SHAPe" and ligado:
                        self.assertEqual(valores[-1], "SINE")
                    elif campo == "VOLTage" and ligado:
                        self.assertEqual(float(valores[-1]), 5.)
                self.assertEqual(sum(c.startswith("TRACe:DATA ") for c in fonte.command_log), 12)
                self.assertEqual(fonte._last_cycles, esperado)

    def test_programacao_pura_mantem_janela_200ms_e_margem_senoidal(self):
        for freq in (50., 60.):
            n = round(30000 / freq)
            for dc in (0., .05):
                with self.subTest(freq=freq, dc=dc):
                    forma = self.forma(freq) + dc
                    sem = AmetekMX30.montar_programacao(forma, base_voltage_rms=5., frequency_hz=freq, dc_offset_pu=dc)
                    com = AmetekMX30.montar_programacao(forma, base_voltage_rms=5., frequency_hz=freq,
                                                      dc_offset_pu=dc, passo_final_sin=True)
                    self.assertEqual(com.programada_pu().shape, (6000,))
                    np.testing.assert_array_equal(com.programada_pu(), sem.programada_pu())
                    np.testing.assert_allclose(com.margem_final_pu(), np.sin(2*np.pi*np.arange(n)/n) + dc)
                    np.testing.assert_array_equal(sem.margem_final_pu(), sem.programada_pu()[-n:])
                    self.assertEqual(com.programada_com_margem_pu().shape, (6000+n,))
                    self.assertAlmostEqual(np.sqrt(np.mean((com.margem_final_pu()-dc)**2)), 1/math.sqrt(2))

    def test_descricao_pura_igual_ao_scpi_em_ambos_modos(self):
        for ligado in (False, True):
            for freq in (50., 60.):
                with self.subTest(ligado=ligado, freq=freq):
                    fonte = self.fonte(passo_final_sin=ligado)
                    p = AmetekMX30.montar_programacao(self.forma(freq), base_voltage_rms=5.,
                                                    frequency_hz=freq, passo_final_sin=ligado)
                    fonte.program_capture(self.forma(freq), base_voltage_rms=5., frequency_hz=freq)
                    self.assertEqual([c for c in fonte.command_log if c.startswith("TRACe:DATA ")],
                                     [p.comando_trace(i) for i in range(p.ciclos)])
                    self.assertIn("SOURce:LIST:FUNCtion:SHAPe " + ",".join(p.passos_nomes), fonte.command_log)
                    self.assertIn("SOURce:LIST:VOLTage " + p.texto_list_voltages(), fonte.command_log)
                    self.assertEqual(fonte.last_programmed_peak_v, p.pico_reconstruido_v)

    def test_p04_parametros_invalidos_recusados_antes_de_qualquer_io(self):
        for ligado in (False, True):
            casos = [{"base_voltage_rms": 11.}, {"base_voltage_rms": float("nan")},
                     {"base_voltage_rms": -1.}, {"frequency_hz": 0.}, {"frequency_hz": float("inf")},
                     {"dc_offset_pu": float("nan")}, {"waveform_pu": np.ones(5999)},
                     {"waveform_pu": np.full(6000, float("nan"))}, {"waveform_pu": self.forma()*30}]
            for caso in casos:
                with self.subTest(ligado=ligado, parametro=next(iter(caso))):
                    fonte = self.fonte(passo_final_sin=ligado)
                    params = dict(waveform_pu=self.forma(), base_voltage_rms=5., frequency_hz=60.)
                    params.update(caso)
                    with mock.patch.object(fonte, "write") as write, mock.patch.object(fonte, "query") as query:
                        with self.assertRaises(ParameterOutOfBoundsError):
                            fonte.program_capture(**params)
                    write.assert_not_called()
                    query.assert_not_called()
                    self.assertEqual(fonte.command_log, [])

    def test_pico_da_margem_inclui_dc_e_respeita_limite_antes_de_io(self):
        fonte = AmetekMX30(simulated=True, max_voltage_rms=10., max_peak_v=7.2, passo_final_sin=True)
        forma = .1 * np.sin(2*np.pi*60*np.arange(6000)/30000.) + .1
        with self.assertRaises(ParameterOutOfBoundsError):
            fonte.program_capture(forma, base_voltage_rms=5., frequency_hz=60., dc_offset_pu=.1)
        self.assertEqual(fonte.command_log, [])


if __name__ == "__main__":
    unittest.main()
