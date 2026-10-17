"""Regressões das pendências P13 (spool) e P15 (relatório amostrado)."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "logica"))
import sessao_io as io
import relatorio_html as html


class PersistenciaPendenciasTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.sessao = self.base / "sessao_interrompida"

    def adicionar(self, arquivo, perfil, n=1):
        md = {"id_captura": f"02-{n:04d}", "perfil": perfil, "fs_hz": 30000.,
              "pontos": 8, "anotacao": f"original-{perfil}-{n}"}
        arquivo.adicionar(perfil, id_captura=md["id_captura"], medida=np.arange(8.) + n,
                          modelo=np.arange(8.), tempo_ms=np.arange(8.) / 30., fs_hz=30000.,
                          snr={30.: np.arange(8.) + 10}, corrente=np.arange(8.) + 20,
                          metadado=md)

    def interrompida(self):
        a = io.ArquivoDaClasse(self.sessao, "02", "SAG")
        self.adicionar(a, "norma")
        a.espelhar("norma", ["literatura"])
        a.consolidar()
        a.encerrar_perfil("norma")
        destino = self.sessao / "metadata" / "02_sag.jsonl"
        destino.parent.mkdir()
        destino.write_text("\n".join(json.dumps(r) for r in a.registros()) + "\n")
        self.adicionar(a, "fronteira")
        a.close()
        return a, destino

    def test_recuperacao_preserva_metadata_corrente_espelhos_e_nao_duplica(self):
        _, destino = self.interrompida()
        antigas = destino.read_text().splitlines()
        self.assertEqual(io.recuperar_parcial(self.sessao), [self.sessao / "02_sag.npz"])
        linhas = destino.read_text().splitlines()
        self.assertEqual(linhas[:2], antigas)
        self.assertEqual(len(linhas), 3)
        self.assertEqual({json.loads(l)["perfil"] for l in linhas}, {"norma", "literatura", "fronteira"})
        dados = io.ler_capturas(self.sessao, versoes=io.VERSOES)
        self.assertTrue(all(c.metadado["anotacao"].startswith("original-") for c in dados))
        correntes = io.ler_pasta(self.sessao / "corrente")
        self.assertEqual({c.perfil for c in correntes}, {"norma", "literatura", "fronteira"})
        for c in correntes:
            np.testing.assert_array_equal(c.sinal, np.arange(8.) + 20)
        self.assertEqual(io.recuperar_parcial(self.sessao), [])
        self.assertEqual(destino.read_text().splitlines(), linhas)

    def test_falha_de_metadata_preserva_spool_e_retry_idempotente(self):
        _, destino = self.interrompida()
        replace = io.os.replace
        def falhar_metadata(src, dst):
            if Path(dst) == destino:
                raise OSError("disco indisponível")
            return replace(src, dst)
        with mock.patch.object(io.os, "replace", side_effect=falhar_metadata):
            with self.assertRaises(OSError):
                io.recuperar_parcial(self.sessao)
        self.assertTrue(list((self.sessao / "parcial").rglob("*.npz")))
        io.recuperar_parcial(self.sessao)
        self.assertEqual(len(destino.read_text().splitlines()), 3)
        self.assertEqual(len(io.ler_capturas(self.sessao)), 3)

    def test_recuperacao_automatica_isola_erro_e_ignora_diretorios_alheios(self):
        self.interrompida()
        corrompido = self.base / "sessao_corrompida" / "parcial" / "02_sag" / "norma__000000.npz"
        corrompido.parent.mkdir(parents=True)
        corrompido.write_bytes(b"invalido")
        (corrompido.parents[2] / io.ARQUIVO_BLOQUEIO).touch()
        alheio = self.base / "outro_projeto" / "parcial" / "02_sag"
        alheio.mkdir(parents=True)
        (alheio / "norma__000000.npz").write_bytes(b"nao tocar")
        logs = []
        saida = io.recuperar_sessoes_interrompidas(self.base, avisar=logs.append)
        self.assertEqual(saida, [self.sessao / "02_sag.npz"])
        self.assertEqual(corrompido.read_bytes(), b"invalido")
        self.assertTrue(any("Spool preservado" in l for l in logs))
        self.assertEqual((alheio / "norma__000000.npz").read_bytes(), b"nao tocar")

    def test_spool_corrompido_nao_altera_classe_consolidada(self):
        a, _ = self.interrompida()
        antes = (self.sessao / "02_sag.npz").read_bytes()
        next(a.pasta_spool.glob("*.npz")).write_bytes(b"invalido")
        with self.assertRaises(Exception):
            io.recuperar_parcial(self.sessao)
        self.assertEqual((self.sessao / "02_sag.npz").read_bytes(), antes)
        self.assertTrue(a.pasta_spool.is_dir())

    def test_html_limita_bancada_tres_por_perfil_e_permite_overrides(self):
        a = io.ArquivoDaClasse(self.sessao, "02", "SAG", spool=False)
        for perfil in ("norma", "fronteira"):
            for n in range(1, 6):
                self.adicionar(a, perfil, n)
        a.consolidar()
        # Os consumidores de dataset continuam recebendo todas as capturas.
        self.assertEqual(len(io.ler_pasta(self.sessao)), 10)
        with mock.patch("builtins.print") as aviso:
            self.assertEqual(len(html.ler_capturas(self.sessao, {})), 6)
        self.assertTrue(any("3 primeiras" in str(c) for c in aviso.call_args_list))
        self.assertEqual(len(html.ler_capturas(self.sessao, {}, max_por_classe=4)), 8)
        self.assertEqual(len(html.ler_capturas(self.sessao, {}, capturas="4-5")), 4)
        self.assertEqual(len(html.ler_capturas(self.sessao, {}, capturas="4-5", max_por_classe=1)), 2)


if __name__ == "__main__":
    unittest.main()
