"""scripts/fechar_pendencias.py: sessões sintéticas mínimas no formato real do sessao_io.

Tudo aqui é FIXTURE sintética montada em diretório temporário; nada disto é
evidência física nem fecha pendência.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "fechar_pendencias.py"
sys.path.insert(0, str(RAIZ / "logica"))
spec = importlib.util.spec_from_file_location("fechar_pendencias", SCRIPT)
fp = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fp
spec.loader.exec_module(fp)
from sessao_io import ArquivoDaClasse  # noqa: E402

FS, PONTOS, MARGEM = 30000.0, 6000, 600


def registro(id_captura, **extra):
    base = {"id_captura": id_captura, "simulado": False, "perfil": "literatura", "tensao_base_rms": 127.0,
            "f0_hz": 60.0, "fs_hz": FS, "pontos": PONTOS, "seed": 1, "parametros": {}, "git_commit": "abc123",
            "git_sujo": False, "validacao_fisica": {"ok": True, "motivos": []}}
    base.update(extra)
    return base


def montar_sessao(raiz, nome, registros, *, git_sujo=False, modo="bancada", extras=None):
    pasta = Path(raiz) / nome
    (pasta / "metadata").mkdir(parents=True)
    (pasta / "sessao.json").write_text(json.dumps({"modo": modo, "git_commit": "abc123", "git_sujo": git_sujo,
                                                   "versao_codigo": "teste"}), encoding="utf-8")
    por_classe = {}
    for r in registros:
        por_classe.setdefault(r["id_captura"].split("-")[0], []).append(r)
    for classe, regs in por_classe.items():
        linhas = "\n".join(json.dumps(r) for r in regs) + "\n"
        (pasta / "metadata" / f"{classe}_teste.jsonl").write_text(linhas, encoding="utf-8")
    for rel, conteudo in (extras or {}).items():
        alvo = pasta / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(conteudo if isinstance(conteudo, str) else json.dumps(conteudo), encoding="utf-8")
    return pasta


def r08(i, desvio=3, pico=280.3, vale=-374.2, f0=50.0, v=127.0, inicio=0.09):
    return registro(f"08-{i:04d}", f0_hz=f0, tensao_base_rms=v, pico_medido_v=pico, vale_medido_v=vale,
                    parametros={"inicio_impulso_s": inicio},
                    validacao_fisica={"ok": True, "motivos": [], "posicao_evento": {
                        "desvio_amostras": desvio, "tolerancia_amostras": 10}})


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)

    def agregar(self, *pastas, pc=None, artefatos=()):
        saida = self.raiz / f"saida_{len(list(self.raiz.glob('saida_*')))}.json"
        argv = []
        for p in pastas:
            argv += ["--sessao", str(p)]
        for a in artefatos:
            argv += ["--artefatos", str(a)]
        if pc is not None:
            argv += ["--pc-bancada", str(pc)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fp.main(argv + ["--saida", str(saida)]), 0)
        return json.loads(saida.read_text(encoding="utf-8")), saida

    def criterio(self, item, nome):
        return next(c for c in item["criterios"] if c["criterio"] == nome)


class AprovadoReprovadoSemDados(Base):
    def test_p03_aprovado_com_procedencia_e_hash(self):
        pasta = montar_sessao(self.raiz, "sessao_ok", [r08(1), r08(2, desvio=-10)])
        rel, _ = self.agregar(pasta)
        item = rel["itens"]["P-03"]
        self.assertEqual(item["status"], "evidencia_suficiente")
        self.assertEqual(self.criterio(item, "desvio_de_posicao_amostras")["valor_medido"], 10)
        self.assertEqual(self.criterio(item, "pico_absoluto_v")["valor_medido"], 374.2)
        self.assertEqual(rel["sessoes"][0]["git_commit"], "abc123")
        self.assertIs(rel["sessoes"][0]["git_sujo"], False)

    def test_p03_reprovado_por_desvio_ou_pico(self):
        for kwargs in ({"desvio": 11}, {"pico": 376.0}, {"vale": -380.0}):
            with self.subTest(kwargs=kwargs):
                pasta = montar_sessao(self.raiz, f"sessao_ruim_{len(kwargs)}_{list(kwargs.values())[0]}", [r08(1, **kwargs)])
                rel, _ = self.agregar(pasta)
                self.assertEqual(rel["itens"]["P-03"]["status"], "reprovado")

    def test_p03_outra_condicao_ou_evento_diferente_e_insuficiente(self):
        pasta = montar_sessao(self.raiz, "sessao_60", [r08(1, f0=60.0), r08(2, inicio=0.08)])
        rel, _ = self.agregar(pasta)
        self.assertEqual(rel["itens"]["P-03"]["status"], "insuficiente")

    def test_sem_dados_para_sessao_vazia_e_simulada(self):
        vazia = self.raiz / "vazia"
        vazia.mkdir()
        sim = montar_sessao(self.raiz, "sessao_sim", [dict(r08(1), simulado=True)], modo="simulado")
        rel, _ = self.agregar(vazia, sim)
        for pid in fp.FISICAS:
            self.assertEqual(rel["itens"][pid]["status"], "sem_dados", pid)
        self.assertEqual(rel["resumo"], {"sem_dados": len(fp.FISICAS)})
        self.assertEqual(rel["bloco_estado_prontidao"]["pendencias"], {})

    def test_arvore_suja_nao_da_evidencia_suficiente(self):
        pasta = montar_sessao(self.raiz, "sessao_suja", [r08(1)], git_sujo=True)
        rel, _ = self.agregar(pasta)
        item = rel["itens"]["P-03"]
        self.assertEqual(item["status"], "insuficiente")
        self.assertEqual(self.criterio(item, "procedencia_commit_limpo")["resultado"], "insuficiente")

    def test_p08_reprova_extremo_acima_do_previsto(self):
        regs = [registro(f"{c}-0001", pico_medido_v=300.0, vale_medido_v=-290.0, extremo_previsto_v=320.0,
                         teto_extremos_v=415.8) for c in ("10", "11", "12", "16")]
        rel, _ = self.agregar(montar_sessao(self.raiz, "sessao_p08", regs))
        self.assertEqual(rel["itens"]["P-08"]["status"], "evidencia_suficiente")
        regs[2] = dict(regs[2], pico_medido_v=330.0)
        rel, _ = self.agregar(montar_sessao(self.raiz, "sessao_p08b", regs))
        self.assertEqual(rel["itens"]["P-08"]["status"], "reprovado")

    def test_itens_humanos_nunca_passam_de_revisao(self):
        regs = [registro(f"{c}-0001", pico_medido_v=150.0, vale_medido_v=-150.0, pico_programado_v=160.0)
                for c in ("07", "17")]
        pasta = montar_sessao(self.raiz, "sessao_cal", regs)
        rel, _ = self.agregar(pasta)
        p07 = rel["itens"]["P-07"]
        self.assertEqual(p07["status"], "evidencia_suficiente")
        self.assertTrue(p07["requer_revisao_humana"])
        self.assertEqual(p07["detalhes"]["recalibracao"]["codigo_saida"], 0)
        self.assertNotIn("--gravar", p07["detalhes"]["recalibracao"]["argv"])

    def test_p21_hash_da_calibracao_e_condicao_sem_tabela(self):
        cal = {"por_condicao": {"127V_60Hz": {"fatores": {c: 1.0 for c in fp.CLASSES}, "origem": "teste"}}}
        pasta = montar_sessao(self.raiz, "sessao_p21", [registro("01-0001")], extras={"calibracao_extremos.json": cal})
        sj = json.loads((pasta / "sessao.json").read_text())
        sj["calibracao_extremos"] = {"copia_na_sessao": "calibracao_extremos.json",
                                     "sha256": fp.sha256_arquivo(pasta / "calibracao_extremos.json")}
        (pasta / "sessao.json").write_text(json.dumps(sj))
        item = self.agregar(pasta)[0]["itens"]["P-21"]
        self.assertEqual(item["status"], "evidencia_suficiente")
        self.assertTrue(item["requer_revisao_humana"])
        pasta2 = montar_sessao(self.raiz, "sessao_p21b", [registro("01-0001", tensao_base_rms=230.0, f0_hz=50.0)],
                               extras={"calibracao_extremos.json": cal})
        self.assertEqual(self.agregar(pasta2)[0]["itens"]["P-21"]["status"], "insuficiente")


class ClassesComNpz(Base):
    def test_p05_largura_e_pretrigger_sao_avisos_nao_reprovacao(self):
        pasta = self.raiz / "sessao_p05"
        (pasta / "metadata").mkdir(parents=True)
        t = np.arange(PONTOS + 2 * MARGEM) / FS
        sinal = np.sin(2 * np.pi * 60 * t)
        inicio_s, dur_s = 0.06, 0.04
        i0, i1 = int((MARGEM / FS + inicio_s) * FS), int((MARGEM / FS + inicio_s + dur_s) * FS)
        sinal[i0:i1] *= 0.5
        regs = []
        sj = {"modo": "bancada", "git_commit": "abc123", "git_sujo": False}
        (pasta / "sessao.json").write_text(json.dumps(sj))
        with ArquivoDaClasse(pasta, "02", "teste", spool=False) as arq:
            arq.iniciar_perfil("literatura")
            for i, desvio in enumerate((0, 5), 1):
                meta = registro(f"02-{i:04d}", inicio_disturbio_s=inicio_s, duracao_s=dur_s, sorteio_posicao=True,
                                indice_trigger=MARGEM + 1800 + desvio, pre_trigger_s=inicio_s,
                                margem_amostras_antes=MARGEM - 1800 + 1800, inicio_janela=MARGEM,
                                pre_trigger_desvio_amostras=desvio)
                arq.adicionar("literatura", id_captura=meta["id_captura"], medida=sinal, tempo_ms=t * 1000.0,
                              fs_hz=FS, inicio_janela=MARGEM, pontos=PONTOS, metadado=meta)
                regs.append(meta)
            arq.consolidar()
        (pasta / "metadata" / "02_teste.jsonl").write_text("\n".join(json.dumps(r) for r in regs) + "\n")
        rel, _ = self.agregar(pasta)
        item = rel["itens"]["P-05"]
        self.assertNotIn("erro_interno", item)
        pt = self.criterio(item, "pre_trigger_desvio_amostras")
        self.assertEqual(pt["resultado"], "aviso")
        self.assertEqual(pt["valor_medido"], 5)
        self.assertNotEqual(item["status"], "reprovado")
        self.assertEqual(self.criterio(item, "fase_e_inicio_medidos")["resultado"], "criterio_nao_definido")


class P16P19Artefatos(Base):
    def pc(self, **mudancas):
        base = {"sistema": "Windows", "plataforma": "Windows-10", "hostname": "BANCADA", "git_commit": "abc123",
                "git_sujo": False, "codigo_saida": 0, "testes_executados": 615, "falhas": 0, "erros": 0, "skips": 0,
                "python": "3.11", "numpy": "2", "pymeasure": "0.11", "pyvisa": "1.14", "log": "pc_bancada.log"}
        base.update(mudancas)
        arq = self.raiz / f"pc_{len(list(self.raiz.glob('pc_*.json')))}.json"
        log = self.raiz / "pc_bancada.log"
        log.write_text("Ran 615 tests\nOK\n")
        base["log_sha256"] = fp.sha256_arquivo(log)
        arq.write_text(json.dumps(base), encoding="utf-8")
        return arq

    def test_p16_aprovado_e_reprovado(self):
        rel, _ = self.agregar(pc=self.pc())
        self.assertEqual(rel["itens"]["P-16"]["status"], "evidencia_suficiente")
        self.assertTrue(all(f["sha256"] for f in rel["itens"]["P-16"]["arquivos_origem"]))
        rel, _ = self.agregar(pc=self.pc(codigo_saida=1, falhas=2))
        self.assertEqual(rel["itens"]["P-16"]["status"], "reprovado")
        rel, _ = self.agregar(pc=self.pc(sistema="Darwin", plataforma="macOS"))
        self.assertEqual(rel["itens"]["P-16"]["status"], "insuficiente")

    def test_p19_finitos_e_erro(self):
        pasta = montar_sessao(self.raiz, "sessao_p19", [])
        (pasta / "diagnostico_trace").mkdir()
        np.savez(pasta / "diagnostico_trace" / "01-0001.npz", lido=np.zeros((2, 1024)), enviado=np.zeros((2, 1024)))
        meta = registro("01-0001", diagnostico_trace={"arquivo": "diagnostico_trace/01-0001.npz",
                                                      "traces_programadas": 2, "traces_lidas": 2, "erro": None})
        (pasta / "metadata" / "01_teste.jsonl").write_text(json.dumps(meta) + "\n")
        self.assertEqual(self.agregar(pasta)[0]["itens"]["P-19"]["status"], "evidencia_suficiente")
        np.savez(pasta / "diagnostico_trace" / "01-0001.npz", lido=np.full((2, 1024), np.nan))
        self.assertEqual(self.agregar(pasta)[0]["itens"]["P-19"]["status"], "insuficiente")
        # comando registrado como não suportado: suficiente, mas com revisão humana
        meta["diagnostico_trace"].update(erro="-113,Undefined header", traces_lidas=0)
        (pasta / "metadata" / "01_teste.jsonl").write_text(json.dumps(meta) + "\n")
        item = self.agregar(pasta)[0]["itens"]["P-19"]
        self.assertEqual(item["status"], "evidencia_suficiente")
        self.assertTrue(item["requer_revisao_humana"])

    LINHAS17 = [{"rotulo": "AC", "modo": "AC", "offset_pu": 0.0, "razao_ch1_ac_sobre_alvo": 1.0},
                {"rotulo": "ACDC0", "modo": "ACDC", "offset_pu": 0.0, "razao_ch1_ac_sobre_alvo": 0.95},
                {"rotulo": "ACDC10", "modo": "ACDC", "offset_pu": 0.1, "razao_ch1_ac_sobre_alvo": 0.94}]
    PROC = {"git_commit": "abc123", "git_sujo": False}

    def test_p17_so_conta_artefato_real_com_procedencia(self):
        pasta = montar_sessao(self.raiz, "sessao_p17", [], extras={
            "logs/diag_acdc_amplitude-1.json": dict({"simulado": False, "linhas": self.LINHAS17}, **self.PROC)})
        self.assertEqual(self.agregar(pasta)[0]["itens"]["P-17"]["status"], "evidencia_suficiente")
        pasta2 = montar_sessao(self.raiz, "sessao_p17sim", [], extras={
            "logs/diag_acdc_amplitude-1.json": dict({"simulado": True, "linhas": self.LINHAS17}, **self.PROC)})
        self.assertEqual(self.agregar(pasta2)[0]["itens"]["P-17"]["status"], "sem_dados")

    def test_p17_sem_procedencia_ou_sujo_e_insuficiente(self):
        for nome, proc in (("sem", {}), ("sujo", {"git_commit": "abc123", "git_sujo": True})):
            pasta = montar_sessao(self.raiz, f"sessao_p17_{nome}", [], extras={
                "logs/diag_acdc_amplitude-1.json": dict({"simulado": False, "linhas": self.LINHAS17}, **proc)})
            self.assertEqual(self.agregar(pasta)[0]["itens"]["P-17"]["status"], "insuficiente", nome)

    def test_artefatos_fora_da_sessao_via_opcao_repetivel(self):
        logs = self.raiz / "logs"
        logs.mkdir()
        (logs / "diag_acdc_amplitude-1.json").write_text(json.dumps(
            dict({"simulado": False, "linhas": self.LINHAS17}, **self.PROC)), encoding="utf-8")
        outra = self.raiz / "outra"
        outra.mkdir()
        vazia = self.raiz / "vazia"
        vazia.mkdir()
        self.assertEqual(self.agregar(vazia)[0]["itens"]["P-17"]["status"], "sem_dados")
        rel, _ = self.agregar(vazia, artefatos=[outra, logs])
        self.assertEqual(rel["itens"]["P-17"]["status"], "evidencia_suficiente")
        self.assertEqual(len(rel["artefatos"]), 2)
        # só --artefatos também é aceito pela CLI
        saida = self.raiz / "so_art.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fp.main(["--artefatos", str(logs), "--saida", str(saida)]), 0)

    def resultado18(self, **extra):
        r = {"margem_sem": [1.0], "margem_com": [1.0, 1.001], "janela_corr": 0.9999, "janela_dif_max_pu": 0.001}
        return dict({"vrms": 127, "resultados": [r]}, **extra)

    def test_p18_exige_procedencia_fisica_e_arvore_limpa(self):
        casos = {"sem": ({}, "insuficiente"),
                 "sujo": ({"simulado": False, "git_commit": "abc123", "git_sujo": True}, "insuficiente"),
                 "limpo": ({"simulado": False, "git_commit": "abc123", "git_sujo": False}, "evidencia_suficiente")}
        for nome, (proc, esperado) in casos.items():
            pasta = self.raiz / f"passo_final_sin_{nome}"
            pasta.mkdir()
            (pasta / "resultado.json").write_text(json.dumps(self.resultado18(**proc)), encoding="utf-8")
            vazia = self.raiz / f"vazia_{nome}"
            vazia.mkdir()
            item = self.agregar(vazia, artefatos=[pasta])[0]["itens"]["P-18"]
            self.assertEqual(item["status"], esperado, nome)

    def test_p16_versao_indisponivel_reprova_versoes_registradas(self):
        rel, _ = self.agregar(pc=self.pc(pymeasure="indisponivel: No package metadata was found"))
        item = rel["itens"]["P-16"]
        self.assertEqual(self.criterio(item, "versoes_registradas")["resultado"], "insuficiente")
        self.assertEqual(item["status"], "insuficiente")
        rel, _ = self.agregar(pc=self.pc(numpy="Indisponivel"))
        self.assertEqual(rel["itens"]["P-16"]["status"], "insuficiente")


class P22P23P28(Base):
    def test_p03_exige_validacao_fisica_ok_e_sobressinal(self):
        ruim = dict(r08(1), validacao_fisica={"ok": False, "motivos": ["x"], "posicao_evento": {
            "desvio_amostras": 1, "tolerancia_amostras": 10}})
        item = self.agregar(montar_sessao(self.raiz, "sessao_okfalso", [ruim]))[0]["itens"]["P-03"]
        self.assertEqual(item["status"], "reprovado")
        self.assertEqual(self.criterio(item, "validacao_fisica_ok_nas_capturas_usadas")["resultado"], "falha")
        alto = self.agregar(montar_sessao(self.raiz, "sessao_sobre", [dict(r08(1), sobressinal_medido=0.6)]))[0]["itens"]["P-03"]
        self.assertEqual(alto["status"], "reprovado")
        bom = self.agregar(montar_sessao(self.raiz, "sessao_sobre_ok", [dict(r08(1), sobressinal_medido=0.40)]))[0]["itens"]["P-03"]
        self.assertEqual(bom["status"], "evidencia_suficiente")
        self.assertEqual(self.criterio(bom, "sobressinal_pu")["resultado"], "ok")
        limite = self.agregar(montar_sessao(self.raiz, "sessao_sobre_lim", [dict(r08(1), sobressinal_medido=0.55)]))[0]["itens"]["P-03"]
        self.assertEqual(self.criterio(limite, "sobressinal_pu")["resultado"], "aviso")  # ≤0,55 mas >0,45: revisão humana
        self.assertTrue(limite["requer_revisao_humana"])
        sem = self.agregar(montar_sessao(self.raiz, "sessao_sem_sobre", [r08(1)]))[0]["itens"]["P-03"]
        self.assertEqual(self.criterio(sem, "sobressinal_pu")["resultado"], "criterio_nao_definido")
        self.assertTrue(sem["requer_revisao_humana"])

    LOG = ("[10:00:00.000] t=1.0 W TRACe:DATA wave1,1,2\n[10:00:00.100] t=1.1 W trac:data wave2,1,2\n"
           "[10:00:00.200] t=1.2 W TRACE:DATA wave3,1,2\n[10:00:00.300] t=1.3 W TRACe:DATA? wave1\n"
           "[10:00:00.400] t=1.4 R TRACe:DATA\n")

    def test_p23_contagem_igual_a_do_orm(self):
        self.assertEqual(sum(fp._gravacoes_trace_na_linha(l) for l in self.LOG.splitlines()), 3)
        self.assertEqual(fp._gravacoes_trace_na_linha("t=1.0 W OUTPut:STATe OFF; TRAC:DATA a,1; DATA b,2"), 2)

    def diag(self, **mudar):
        base = {"T0": {"ok": 1}, "_procedencia": {"simulado": False, "modo": "bancada", "git_commit": "abc123",
                                                  "git_sujo": False}}
        base.update(mudar)
        return base

    def test_p23_ignora_sessao_simulada_e_diag_arbitrario(self):
        sim = montar_sessao(self.raiz, "sessao_sim23", [], modo="simulado", extras={
            "scpi_transcricao.log": self.LOG, "logs/diag_nativo-1.json": self.diag()})
        item = self.agregar(sim)[0]["itens"]["P-23"]
        # log da sessão simulada não é contado; o diag dentro dela também vale por si (físico declarado)
        self.assertEqual(item["detalhes"]["gravacoes_por_log"], {})
        reais = montar_sessao(self.raiz, "sessao_real23", [], extras={"scpi_transcricao.log": self.LOG})
        item = self.agregar(reais)[0]["itens"]["P-23"]
        self.assertEqual(list(item["detalhes"]["gravacoes_por_log"].values()), [3])
        for nome, conteudo in (("arbitrario", {"qualquer": 1}), ("sem_proc", {"T0": {}}),
                               ("sujo", self.diag(_procedencia={"simulado": False, "git_commit": "a", "git_sujo": True})),
                               ("simulado", self.diag(_procedencia={"simulado": True, "git_commit": "a", "git_sujo": False}))):
            pasta = montar_sessao(self.raiz, f"sessao_d_{nome}", [], extras={"scpi_transcricao.log": self.LOG,
                                                                       f"logs/diag_nativo-{nome}.json": conteudo})
            item = self.agregar(pasta)[0]["itens"]["P-23"]
            self.assertEqual(self.criterio(item, "diag_nativo_output_off_presente")["resultado"], "insuficiente", nome)
        bom = montar_sessao(self.raiz, "sessao_d_bom", [], extras={"scpi_transcricao.log": self.LOG,
                                                                  "logs/diag_nativo-1.json": self.diag()})
        item = self.agregar(bom)[0]["itens"]["P-23"]
        self.assertEqual(self.criterio(item, "diag_nativo_output_off_presente")["resultado"], "ok")

    def sessao28(self, nome, conteudo=b"bruto-ch1"):
        reg = registro("01-0001", bruto_osciloscopio={"arquivos": [
            {"canal": 1, "arquivo": "bruto_osciloscopio/ch1.npz", "erro": None}]})
        pasta = montar_sessao(self.raiz, nome, [reg])
        (pasta / "bruto_osciloscopio").mkdir()
        (pasta / "bruto_osciloscopio" / "ch1.npz").write_bytes(conteudo)
        return pasta

    def test_p28_exige_sha256_casado(self):
        pasta = self.sessao28("sessao_p28")
        sha = hashlib.sha256(b"bruto-ch1").hexdigest()
        analise = self.raiz / "analises"
        analise.mkdir()
        (analise / "a.json").write_text(json.dumps({"fonte": {"tipo": "arquivo_bruto_fornecido", "arquivo_sha256": "0" * 64}}))
        item = self.agregar(pasta, artefatos=[analise])[0]["itens"]["P-28"]
        self.assertEqual(self.criterio(item, "analise_de_reamostragem_sobre_bruto_real")["resultado"], "insuficiente")
        self.assertEqual(item["status"], "insuficiente")
        (analise / "a.json").write_text(json.dumps({"fonte": {"tipo": "arquivo_bruto_fornecido", "arquivo_sha256": sha}}))
        item = self.agregar(pasta, artefatos=[analise])[0]["itens"]["P-28"]
        self.assertEqual(self.criterio(item, "analise_de_reamostragem_sobre_bruto_real")["resultado"], "ok")

    def test_p22_usa_hostname_do_artefato_nao_o_do_computador_de_analise(self):
        pasta = montar_sessao(self.raiz, "sessao_p22", [registro("01-0001")])
        pc = self.raiz / "pc.json"
        pc.write_text(json.dumps({"hostname": "BANCADA-LONGO-NOME-X"}), encoding="utf-8")
        art = self.raiz / "art"
        art.mkdir()
        (art / "benchmark_bancada.json").write_text(json.dumps({"x": 1}), encoding="utf-8")
        item = self.agregar(pasta, pc=pc, artefatos=[art])[0]["itens"]["P-22"]
        self.assertEqual(self.criterio(item, "executado_no_pc_da_bancada")["resultado"], "criterio_nao_definido")
        for host, esperado in (("bancada-longo-nome", "ok"), ("BANCADA-LONGO-NOME-X", "ok"), ("OUTRO", "insuficiente")):
            (art / "benchmark_bancada.json").write_text(json.dumps({"hostname": host}), encoding="utf-8")
            item = self.agregar(pasta, pc=pc, artefatos=[art])[0]["itens"]["P-22"]
            self.assertEqual(self.criterio(item, "executado_no_pc_da_bancada")["resultado"], esperado, host)
        self.assertFalse(fp._mesmo_host("abc", "abd"))
        self.assertTrue(fp._mesmo_host("ABCDEFGHIJKLMNO", "abcdefghijklmnopq"))
        self.assertFalse(fp._mesmo_host("abcdefghijklmn", "abcdefghijklmnX"[:14] + "z"))


class IntegridadeEIsolamento(Base):
    def test_recusa_sobrescrever_saida(self):
        pasta = montar_sessao(self.raiz, "sessao_x", [r08(1)])
        saida = self.raiz / "fechamento.json"
        saida.write_text("original", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            fp.main(["--sessao", str(pasta), "--saida", str(saida)])
        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(saida.read_text(encoding="utf-8"), "original")

    def test_sha256_dos_arquivos_de_origem_confere(self):
        pasta = montar_sessao(self.raiz, "sessao_h", [r08(1)])
        rel, _ = self.agregar(pasta)
        origens = rel["itens"]["P-03"]["arquivos_origem"]
        self.assertTrue(origens)
        for o in origens:
            self.assertEqual(o["sha256"], hashlib.sha256(Path(o["arquivo"]).read_bytes()).hexdigest())
        nomes = {Path(o["arquivo"]).name for o in origens}
        self.assertIn("08_teste.jsonl", nomes)
        self.assertIn("sessao.json", nomes)

    def test_nao_grava_estado_prontidao_e_propoe_bloco(self):
        estado = RAIZ / "docs" / "estado_prontidao.json"
        antes = estado.read_bytes()
        pasta = montar_sessao(self.raiz, "sessao_b", [r08(1)])
        rel, saida = self.agregar(pasta)
        self.assertEqual(estado.read_bytes(), antes)
        bloco = rel["bloco_estado_prontidao"]["pendencias"]["P03"]
        self.assertEqual(bloco["status"], "aberta" if rel["itens"]["P-03"]["requer_revisao_humana"] else "concluida")
        self.assertEqual(len(bloco["evidencias"]), 1)

    def test_nenhum_import_de_pyvisa_ou_pymeasure(self):
        regs = [r08(1)] + [registro(f"{c}-0001", pico_medido_v=1.0, vale_medido_v=-1.0, pico_programado_v=1.0)
                           for c in ("07", "17")]
        pasta = montar_sessao(self.raiz, "sessao_iso", regs)
        saida = self.raiz / "iso.json"
        codigo = (
            "import runpy, sys\n"
            f"sys.argv = ['fechar_pendencias.py', '--sessao', {str(pasta)!r}, '--saida', {str(saida)!r}]\n"
            "try:\n"
            f"    runpy.run_path({str(SCRIPT)!r}, run_name='__main__')\n"
            "except SystemExit as e:\n"
            "    assert e.code in (0, None), e.code\n"
            "ruins = sorted(m for m in sys.modules if m.split('.')[0] in ('pyvisa', 'pymeasure', 'visa', 'mestre', 'ametek_orm', 'oscilloscope_orm'))\n"
            "print('MODULOS_PROIBIDOS=' + repr(ruins))\n"
        )
        p = subprocess.run([sys.executable, "-I", "-c", codigo], capture_output=True, timeout=300)
        # Bytes + decodificação tolerante: no Windows o filho escreve na
        # codificação local (cp1252) e text=True pode devolver stdout=None.
        stdout = p.stdout.decode("utf-8", errors="replace")
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", errors="replace"))
        self.assertIn("MODULOS_PROIBIDOS=[]", stdout)
        self.assertTrue(saida.exists())

    def test_codigo_nao_referencia_instrumentos(self):
        texto = SCRIPT.read_text(encoding="utf-8")
        for proibido in ("import pyvisa", "from pyvisa", "import pymeasure", "from pymeasure", "import visa",
                         "import mestre", "ResourceManager", "AmetekMX30", "KeysightDSOX4034A"):
            self.assertNotIn(proibido, texto)


class ScriptPowerShell(unittest.TestCase):
    def test_ps1_tem_os_campos_e_recusa_sobrescrita(self):
        texto = (RAIZ / "scripts" / "validar_pc_bancada.ps1").read_text(encoding="utf-8")
        for trecho in ("unittest", "discover", "rev-parse", "status", "--short", "COMPUTERNAME", "pymeasure",
                       "pyvisa", "numpy", "pc_bancada.json", "pc_bancada.log", "skips", "falhas", "erros"):
            self.assertIn(trecho, texto)
        self.assertIn("nao sobrescrevo", texto)
        # sujeira só nas pastas de código + rastreados; git ausente não herda $LASTEXITCODE
        for trecho in ("--untracked-files=no", "ls-files", "experimentos_waveform", "Get-Command git", "^Ran (",
                       '"^FAILED', "indisponivel"):
            self.assertIn(trecho, texto)
        for proibido in ("OUTPut", "ResourceManager", "ENERGIZAR"):
            self.assertNotIn(proibido, texto)


if __name__ == "__main__":
    unittest.main()
