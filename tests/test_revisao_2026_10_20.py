"""Achados confirmados da revisão de 2026-10-20."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "logica"))
sys.path.insert(0, str(RAIZ / "scripts"))
import cli
import mestre
from logica.ametek_orm import AmetekMX30
import analisar_reamostragem as ar


class QuebraDeLinhaTests(unittest.TestCase):
    def test_write_com_quebra_e_recusado_antes_de_contar_ou_transportar(self):
        for comando in ("*CLS\nTRACe:DATA T1,0.1,0.2", "*CLS\rTRACe:DATA T1,0.1", "TRACe:DATA T1,0.1\n*CLS"):
            with self.subTest(comando=comando):
                fonte = AmetekMX30(simulated=True, max_voltage_rms=10, max_peak_v=100)
                with mock.patch.object(fonte, "_simulate_write") as transporte:
                    with self.assertRaises(ValueError):
                        fonte.write(comando)
                    transporte.assert_not_called()
                self.assertEqual(fonte.command_log, [])
                self.assertEqual(fonte.escritas_trace, 0)

    def test_query_com_quebra_e_recusada(self):
        fonte = AmetekMX30(simulated=True, max_voltage_rms=10, max_peak_v=100)
        with self.assertRaises(ValueError):
            fonte.query("*IDN?\n*CLS")
        self.assertEqual(fonte.command_log, [])

    def test_comando_de_uma_linha_continua_contado(self):
        fonte = AmetekMX30(simulated=True, max_voltage_rms=10, max_peak_v=100)
        fonte.write("TRACe:DATA T1,0.1,0.2\n")  # \n final é só terminador, removido por strip
        self.assertEqual(fonte.escritas_trace, 1)


class MensagemOrcamentoTests(unittest.TestCase):
    def test_recusa_nao_promete_teto(self):
        linhas = [("08", "TRANSIENT", {"escritas_trace": 217, "total": 19})]
        with contextlib.redirect_stdout(io.StringIO()) as saida:
            self.assertFalse(cli.SessaoCLI._verificar_orcamento_trace(linhas))
        texto = saida.getvalue()
        self.assertIn("sem retentativas", texto)
        self.assertNotIn("Execução recusada: até", texto)
        self.assertIn("Nada foi energizado", texto)


class BloqueioAteOFimTests(unittest.TestCase):
    def _sessao(self):
        sessao = cli.SessaoCLI()
        bloqueio = mock.Mock()
        sessao._bloqueio_sessao = bloqueio
        return sessao, bloqueio

    def _rodar(self, fim):
        sessao, bloqueio = self._sessao()
        visto = {}

        def gancho(_pasta):
            visto["ativo"] = sessao._bloqueio_sessao is bloqueio and not bloqueio.close.called
            return fim()
        with mock.patch.object(sessao, "_garantir_pasta_sessao"), \
                mock.patch.object(sessao, "autorizar_saida"), \
                mock.patch.object(sessao, "_fim_da_sessao", side_effect=gancho), \
                mock.patch.object(mestre.Bancada, "from_env") as from_env, \
                contextlib.redirect_stdout(io.StringIO()):
            from_env.return_value.__enter__.return_value.executar_bateria.return_value = []
            try:
                sessao._executar_scripts([])
            finally:
                return sessao, bloqueio, visto

    def test_lock_ativo_durante_gancho_e_liberado_depois(self):
        sessao, bloqueio, visto = self._rodar(lambda: None)
        self.assertTrue(visto["ativo"])
        bloqueio.close.assert_called_once()
        self.assertIsNone(sessao._bloqueio_sessao)

    def test_lock_liberado_mesmo_se_gancho_levanta(self):
        def falha():
            raise RuntimeError("gancho")
        sessao, bloqueio, visto = self._rodar(falha)
        self.assertTrue(visto["ativo"])
        bloqueio.close.assert_called_once()
        self.assertIsNone(sessao._bloqueio_sessao)


class BrutoOrfaoTests(unittest.TestCase):
    def test_so_arquivos_listados_no_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            sessao = Path(tmp)
            pasta = sessao / "bruto_osciloscopio" / "literatura"
            pasta.mkdir(parents=True)
            listado = pasta / "01-0001-ch1-aaa.npz"
            orfao = pasta / "01-0001-ch1-bbb.npz"
            np.savez(listado, x=np.zeros(2))
            np.savez(orfao, x=np.zeros(2))
            meta = {"id_captura": "01-0001", "bruto_osciloscopio": {"arquivos": [
                {"canal": 1, "arquivo": "bruto_osciloscopio/literatura/01-0001-ch1-aaa.npz", "erro": None},
                {"canal": 2, "arquivo": None, "erro": "falhou"},
            ]}}
            achados = ar.arquivos_brutos_da_captura(sessao, meta)
            self.assertEqual(achados, [listado.resolve()])
            self.assertNotIn(orfao.resolve(), achados)
            self.assertEqual(ar.arquivos_brutos_da_captura(sessao, {"id_captura": "01-0001"}), [])

    def test_caminho_fora_da_sessao_e_recusado(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta = {"bruto_osciloscopio": {"arquivos": [{"arquivo": "../fora.npz", "erro": None}]}}
            with self.assertRaises(ValueError):
                ar.arquivos_brutos_da_captura(tmp, meta)


if __name__ == "__main__":
    unittest.main()
