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

    def agregar(self, *pastas, pc=None):
        saida = self.raiz / f"saida_{len(list(self.raiz.glob('saida_*')))}.json"
        argv = []
        for p in pastas:
            argv += ["--sessao", str(p)]
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

    def test_p17_so_conta_artefato_real(self):
        linhas = [{"rotulo": "AC", "modo": "AC", "offset_pu": 0.0, "razao_ch1_ac_sobre_alvo": 1.0},
                  {"rotulo": "ACDC0", "modo": "ACDC", "offset_pu": 0.0, "razao_ch1_ac_sobre_alvo": 0.95},
                  {"rotulo": "ACDC10", "modo": "ACDC", "offset_pu": 0.1, "razao_ch1_ac_sobre_alvo": 0.94}]
        pasta = montar_sessao(self.raiz, "sessao_p17", [], extras={
            "logs/diag_acdc_amplitude-1.json": {"simulado": False, "linhas": linhas}})
        self.assertEqual(self.agregar(pasta)[0]["itens"]["P-17"]["status"], "evidencia_suficiente")
        pasta2 = montar_sessao(self.raiz, "sessao_p17sim", [], extras={
            "logs/diag_acdc_amplitude-1.json": {"simulado": True, "linhas": linhas}})
        self.assertEqual(self.agregar(pasta2)[0]["itens"]["P-17"]["status"], "sem_dados")


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
        p = subprocess.run([sys.executable, "-I", "-c", codigo], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("MODULOS_PROIBIDOS=[]", p.stdout)
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
        for proibido in ("OUTPut", "ResourceManager", "ENERGIZAR"):
            self.assertNotIn(proibido, texto)


if __name__ == "__main__":
    unittest.main()
