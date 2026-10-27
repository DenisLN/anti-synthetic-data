"""Arquivo único de estado das pendências (docs/estado_prontidao.json): offline, sem hardware.

Falha quando o arquivo está inválido (P-NN faltando ou repetido, estado fora da lista,
evidência citada que não existe) ou quando o mapa/ ficou para trás do arquivo.
"""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
ARQUIVO = DOCS / "estado_prontidao.json"


def _carregar(nome, caminho):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


lib = _carregar("estado_pendencias", DOCS / "_ext" / "estado_pendencias.py")
mapa = _carregar("gerar_mapa_pendencias", RAIZ / "scripts" / "gerar_mapa_pendencias.py")


class ArquivoReal(unittest.TestCase):
    def test_arquivo_real_e_valido(self):
        self.assertEqual(lib.validar(lib.carregar(ARQUIVO), DOCS), [])

    def test_31_pendencias_e_placar_soma_31(self):
        dados = lib.carregar(ARQUIVO)
        self.assertEqual(list(dados["pendencias"]), list(lib.IDS))
        self.assertEqual(sum(lib.contagem(dados).values()), 31)

    def test_markdown_gerado_tem_uma_ancora_por_pendencia(self):
        texto = lib.gerar_markdown(lib.carregar(ARQUIVO))
        for ident in lib.IDS:
            self.assertEqual(texto.count(f"(estado-{ident.lower()})="), 1, ident)

    def test_mapa_acompanha_o_arquivo_de_estado(self):
        dados = lib.carregar(ARQUIVO)
        itens = mapa.montar(dados)
        self.assertEqual(json.loads(mapa.MODELO_JSON.read_text(encoding="utf-8")), itens,
                         "mapa/_modelos/pendencias.json desatualizado: rode scripts/gerar_mapa_pendencias.py")
        for it in itens:
            nota = (mapa.SAIDA / f"{it['id']}.md").read_text(encoding="utf-8")
            self.assertEqual(nota, mapa.renderizar(it),
                             f"mapa/pendencias/{it['id']}.md desatualizado: rode scripts/gerar_mapa_pendencias.py")


class ArquivoCorrompido(unittest.TestCase):
    def setUp(self):
        self.dados = copy.deepcopy(lib.carregar(ARQUIVO))

    def erros(self):
        return lib.validar(self.dados, DOCS)

    def assertErro(self, trecho):
        erros = self.erros()
        self.assertTrue(any(trecho in e for e in erros), f"{trecho!r} não apareceu em {erros}")

    def test_pendencia_faltando(self):
        del self.dados["pendencias"]["P-17"]
        self.assertErro("P-17: pendência faltando")

    def test_identificador_fora_da_faixa(self):
        self.dados["pendencias"]["P-32"] = copy.deepcopy(self.dados["pendencias"]["P-01"])
        self.assertErro("P-32: identificador fora de P-01..P-31")

    def test_pendencia_repetida_no_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "estado.json"
            caminho.write_text('{"esquema": 2, "pendencias": {"P-01": {}, "P-01": {}}}', encoding="utf-8")
            with self.assertRaises(lib.EstadoInvalido):
                lib.carregar(caminho)

    def test_estado_fora_da_lista(self):
        self.dados["pendencias"]["P-05"]["estado"] = "quase-pronta"
        self.assertErro("P-05: estado 'quase-pronta' fora da lista")

    def test_estado_binario_antigo_nao_vale(self):
        self.dados["pendencias"]["P-05"]["estado"] = "aberta"
        self.assertErro("P-05: estado 'aberta'")

    def test_evidencia_inexistente(self):
        self.dados["pendencias"]["P-03"]["evidencias"].append("evidencias/2026-10-22/nao_existe.json")
        self.assertErro("P-03: evidência 'evidencias/2026-10-22/nao_existe.json': arquivo inexistente")

    def test_evidencia_fora_de_docs(self):
        self.dados["pendencias"]["P-03"]["evidencias"].append("../AGENTS.md")
        self.assertErro("caminho fora de docs/")

    def test_concluida_sem_evidencia(self):
        self.dados["pendencias"]["P-03"]["evidencias"] = []
        self.assertErro("P-03: pendência concluída exige ao menos uma evidência")

    def test_quem_fecha_desconhecido(self):
        self.dados["pendencias"]["P-01"]["quem_fecha"] = ["ninguem"]
        self.assertErro("P-01: quem_fecha")

    def test_decisao_do_dono_sem_booleano(self):
        self.dados["pendencias"]["P-01"]["decisao_dono"] = {"texto": "x"}
        self.assertErro("P-01: decisao_dono")

    def test_commit_malformado(self):
        self.dados["pendencias"]["P-07"]["commits"] = ["não é hash"]
        self.assertErro("P-07: commits")

    def test_esquema_errado(self):
        self.dados["esquema"] = 1
        self.assertErro("esquema deve ser 2")

    def test_estado_reprovada_bancada_e_aceito(self):
        self.dados["pendencias"]["P-02"]["estado"] = "reprovada-bancada"
        self.assertEqual(self.erros(), [])


if __name__ == "__main__":
    unittest.main()
