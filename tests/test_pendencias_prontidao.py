"""Fixtures de contrato sintéticas: nunca constituem prova de sessão física."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "verificar_prontidao.py"
spec = importlib.util.spec_from_file_location("verificar_prontidao", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class PendenciasProntidao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.manifesto = self.base / "manifesto.json"
        self.dados = {"pendencias": {}, "sessoes": {}}

    def verificar(self):
        self.manifesto.write_text(json.dumps(self.dados), encoding="utf-8")
        return gate.verificar(self.manifesto)

    def test_template_real_permanece_aberto_e_cinco_condicoes_ausentes(self):
        template = SCRIPT.parent.parent / "docs" / "manifesto_prontidao.json"
        resultado = gate.verificar(template)
        self.assertFalse(resultado["pronto"])
        self.assertEqual(len(resultado["sessoes"]), 5)
        for ident in gate.PENDENCIAS:
            self.assertTrue(any(p.startswith(ident + ":") for p in resultado["faltantes"]))
        self.assertTrue(all(s["capturas_independentes"] == 0 for s in resultado["sessoes"].values()))

    def test_status_sozinho_sem_evidencia_nao_conclui(self):
        self.dados["pendencias"] = {p: {"status": "concluida", "evidencias": []} for p in gate.PENDENCIAS}
        resultado = self.verificar()
        self.assertFalse(resultado["pronto"])
        self.assertTrue(any("P01: evidências" in p for p in resultado["faltantes"]))

    def test_caminhos_absolutos_ou_externos_recusados(self):
        for caminho in (str(self.manifesto), "../fora.txt", ""):
            with self.subTest(caminho=caminho):
                self.dados["pendencias"]["P01"] = {"status": "concluida", "evidencias": [caminho]}
                resultado = self.verificar()
                self.assertTrue(any(p.startswith("P01:") for p in resultado["faltantes"]))

    def test_arquivo_existente_referencia_valida_mas_nao_atesta_ciencia(self):
        (self.base / "evidencia.txt").write_text("FIXTURE SINTÉTICA de contrato; não física.")
        self.dados["pendencias"] = {p: {"status": "concluida", "evidencias": ["evidencia.txt"]} for p in gate.PENDENCIAS}
        resultado = self.verificar()
        self.assertFalse(resultado["pronto"])
        self.assertFalse(any(p.startswith("P01:") for p in resultado["faltantes"]))
        self.assertTrue(all(any(p.startswith(c + ":") for p in resultado["faltantes"])
                            for c in gate.CONDICOES))

    def test_fixture_explicitamente_sintetica_nunca_comprova_bancada(self):
        pasta = self.base / "fixture_sintetica_nao_fisica"
        pasta.mkdir()
        self.dados["sessoes"]["127V_60Hz"] = pasta.name
        # Esta fixture apenas exercita declarações contraditórias; o marcador
        # obrigatório identifica que não houve aquisição física.
        (pasta / "sessao.json").write_text(json.dumps({"modo": "bancada", "fixture_sintetica": True,
                                                     "git_sujo": False, "git_commit": "fixture-sem-commit-real"}))
        resultado = self.verificar()
        self.assertFalse(resultado["pronto"])
        self.assertTrue(any("sintéticos não comprovam" in p for p in resultado["faltantes"]))
        self.assertEqual(resultado["sessoes"]["127V_60Hz"]["capturas_independentes"], 0)

    def test_sessao_simulada_e_json_invalido_sao_recusados(self):
        pasta = self.base / "simulado"
        pasta.mkdir()
        self.dados["sessoes"]["127V_60Hz"] = pasta.name
        (pasta / "sessao.json").write_text('{"modo":"simulado"}')
        self.assertTrue(any("não é de bancada física" in p for p in self.verificar()["faltantes"]))
        (pasta / "sessao.json").write_text("JSON inválido")
        self.assertFalse(self.verificar()["pronto"])

    def test_cli_saida_fechada_exit_um_sem_sobrescrita(self):
        self.verificar()
        saida = self.base / "status.json"
        self.assertEqual(gate.main(["--manifesto", str(self.manifesto), "--saida", str(saida)]), 1)
        original = saida.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            gate.main(["--manifesto", str(self.manifesto), "--saida", str(saida)])
        self.assertEqual(saida.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
