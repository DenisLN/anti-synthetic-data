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
        self.assertErro("esquema deve ser 3")

    def test_estado_reprovada_bancada_e_aceito(self):
        self.dados["pendencias"]["P-02"]["estado"] = "reprovada-bancada"
        self.assertEqual(self.erros(), [])

    def test_estado_insuficiente_bancada_e_aceito(self):
        self.dados["pendencias"]["P-19"]["estado"] = "insuficiente-bancada"
        self.assertEqual(self.erros(), [])

    def test_como_tratada_obrigatorio(self):
        self.dados["pendencias"]["P-06"]["como_tratada"] = None
        self.assertErro("P-06: campo 'como_tratada' obrigatório")

    def test_falta_por_tipo_obrigatorio_quando_nao_concluida(self):
        self.dados["pendencias"]["P-06"]["falta_por_tipo"] = {}
        self.assertErro("P-06: pendência não concluída exige falta_por_tipo")

    def test_falta_por_tipo_precisa_bater_com_quem_fecha(self):
        self.dados["pendencias"]["P-06"]["falta_por_tipo"] = {"decisao-dono": "x"}
        self.assertErro("P-06: falta_por_tipo ['decisao-dono'] difere de quem_fecha ['bancada']")

    def test_falta_por_tipo_chave_desconhecida(self):
        self.dados["pendencias"]["P-03"]["falta_por_tipo"] = {"ninguem": "x"}
        self.assertErro("P-03: falta_por_tipo tem chave 'ninguem'")

    def test_situacao_da_decisao_fora_da_lista(self):
        self.dados["pendencias"]["P-03"]["decisao_dono"]["situacao"] = "talvez"
        self.assertErro("P-03: decisao_dono.situacao 'talvez'")

    def test_registrada_so_vale_com_situacao_confirmada(self):
        self.dados["pendencias"]["P-03"]["decisao_dono"]["registrada"] = True
        self.assertErro("P-03: decisao_dono.registrada só é verdadeira quando a situação é 'confirmada'")

    def test_decisao_confirmada_exige_data(self):
        del self.dados["pendencias"]["P-30"]["decisao_dono"]["data"]
        self.assertErro("P-30: decisão confirmada exige 'data'")

    def test_escolha_do_fork_sem_pergunta(self):
        del self.dados["pendencias"]["P-04"]["decisao_dono"]["pergunta"]
        self.assertErro("P-04: decisão tomada-no-fork exige 'pergunta'")

    def test_pergunta_exige_opcoes_e_fonte(self):
        self.dados["pendencias"]["P-04"]["decisao_dono"]["opcoes"] = []
        self.dados["pendencias"]["P-04"]["decisao_dono"]["fonte_opcoes"] = "palpite"
        self.assertErro("P-04: 'opcoes' deve ser lista não vazia")
        self.assertErro("P-04: 'fonte_opcoes' deve ser uma de")

    def test_concluida_com_decisao_em_branco(self):
        self.dados["pendencias"]["P-03"]["decisao_dono"].update({"situacao": "em-branco"})
        self.assertErro("P-03: pendência concluída não pode ter a decisão do dono em branco")


class RevisaoDe2026_10_27(unittest.TestCase):
    """A revisão de 27/10: o que as evidências de 22/10 e o relatório de achados mostram."""

    def setUp(self):
        self.dados = lib.carregar(ARQUIVO)
        self.pend = self.dados["pendencias"]

    def test_p02_e_p08_estao_reprovadas_na_bancada(self):
        self.assertEqual(self.pend["P-02"]["estado"], "reprovada-bancada")
        self.assertEqual(self.pend["P-08"]["estado"], "reprovada-bancada")

    def test_p19_tem_evidencia_insuficiente(self):
        self.assertEqual(self.pend["P-19"]["estado"], "insuficiente-bancada")

    def test_p16_e_p25_nao_estao_concluidas(self):
        for ident in ("P-16", "P-25"):
            self.assertNotEqual(self.pend[ident]["estado"], "concluida", ident)

    def test_nenhuma_concluida_sem_escolha_confirmada_ou_do_fork_marcada(self):
        for ident, item in self.pend.items():
            if item["estado"] == "concluida":
                self.assertIn(item["decisao_dono"]["situacao"], ("confirmada", "tomada-no-fork", "nao-se-aplica"), ident)

    def test_escolhas_do_fork_aguardando_confirmacao(self):
        esperadas = ["P-03", "P-04", "P-10", "P-11", "P-12", "P-13", "P-14", "P-15", "P-27"]
        self.assertEqual(lib.aguardam_confirmacao(self.dados), esperadas)
        for ident in ("P-25",):
            self.assertEqual(self.pend[ident]["decisao_dono"]["situacao"], "tomada-no-fork")

    def test_p09_registra_o_conflito_como_pergunta_ao_dono(self):
        decisao = self.pend["P-09"]["decisao_dono"]
        self.assertTrue(decisao["registrada"])
        self.assertIn("braços A e B", decisao["pergunta"])

    def test_decisoes_confirmadas_citam_a_fonte(self):
        for ident, item in self.pend.items():
            decisao = item["decisao_dono"]
            if decisao["situacao"] == "confirmada":
                self.assertIn("projeto/pendencias.md", decisao["texto"], ident)

    def test_pergunta_ao_dono_em_toda_decisao_aberta(self):
        for ident, item in self.pend.items():
            if item["decisao_dono"]["situacao"] in ("tomada-no-fork", "em-branco"):
                self.assertTrue(item["decisao_dono"].get("pergunta"), ident)

    def test_placar_soma_31_e_a_linha_bate_com_a_contagem(self):
        cont = lib.contagem(self.dados)
        self.assertEqual(sum(cont.values()), 31)
        linha = lib.gerar_placar_linha(self.dados)
        for slug, n in cont.items():
            if n:
                self.assertIn(f"{n} {lib.ESTADOS_CURTO[slug]}", linha)

    def test_markdown_gerado_traz_as_secoes_pedidas_para_as_31(self):
        texto = lib.gerar_markdown(self.dados)
        self.assertEqual(texto.count("**Como foi resolvida ou o que foi feito:**"), 31)
        self.assertEqual(texto.count("**Pedido original:**"), 31)
        self.assertEqual(texto.count("**Escolha do fork e decisão do dono"), 31)
        self.assertIn("### Perguntas ao dono", texto)


if __name__ == "__main__":
    unittest.main()
