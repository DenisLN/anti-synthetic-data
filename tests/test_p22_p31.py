"""P-22/P-31 offline: benchmark e correlações sobre sessões FIXTURE sintéticas no formato real.

Nada aqui é evidência física nem fecha pendência.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "logica"))
sys.path.insert(0, str(RAIZ / "tests"))


def _carregar(nome):
    spec = importlib.util.spec_from_file_location(nome, RAIZ / "scripts" / f"{nome}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nome] = mod
    spec.loader.exec_module(mod)
    return mod


bench = _carregar("benchmark_sessao_io")
amp = _carregar("analisar_modelo_programado")
from sessao_io import ArquivoDaClasse  # noqa: E402
import test_pendencias_fechamento as tf  # noqa: E402

FS, PONTOS, MARGEM = 30000.0, 6000, 600


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def montar(raiz, nome, classes=("06", "10"), *, modo="bancada", simulado=False, n=2):
    """Sessão no formato 2: perfil literatura (+ alias fronteira) e norma, 3 versões."""
    pasta = Path(raiz) / nome
    (pasta / "metadata").mkdir(parents=True)
    (pasta / "sessao.json").write_text(json.dumps({"modo": modo, "git_commit": "abc123", "git_sujo": False}))
    rng = np.random.default_rng(7)
    t = np.arange(PONTOS) / FS
    tt = np.arange(PONTOS + 2 * MARGEM) / FS
    for classe in classes:
        regs = []
        with ArquivoDaClasse(pasta, classe, "teste", spool=False) as arq:
            for perfil in ("norma", "literatura"):
                arq.iniciar_perfil(perfil)
                for i in range(1, n + 1):
                    ident = f"{classe}-{i:04d}"
                    modelo = np.sin(2 * np.pi * 60 * t) + 0.2 * np.sin(2 * np.pi * 300 * t + i + len(perfil))
                    prog = modelo + rng.normal(0, 0.01, PONTOS)
                    medida = np.concatenate([np.zeros(MARGEM), prog * 0.98 + rng.normal(0, 0.01, PONTOS), np.zeros(MARGEM)])
                    meta = tf.registro(ident, perfil=perfil, simulado=simulado, tres_versoes={"arquivo": "x", "programada": "o"})
                    arq.adicionar(perfil, id_captura=ident, medida=medida, modelo=modelo, programada=prog,
                                  tempo_ms=tt * 1000, fs_hz=FS, inicio_janela=MARGEM, pontos=PONTOS, metadado=meta)
            arq.espelhar("literatura", ["fronteira"])
            regs = arq.registros()
            arq.consolidar()
        (pasta / "metadata" / f"{classe}_teste.jsonl").write_text("\n".join(json.dumps(r) for r in regs) + "\n")
    return pasta


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)

    def rodar(self, modulo, argv):
        with contextlib.redirect_stdout(io.StringIO()):
            return modulo.main(argv)


class BenchmarkSessoes(Base):
    def test_mede_sem_modificar_e_identifica_aliases(self):
        pasta = montar(self.raiz, "sessao_a")
        antes = {p.name: sha(p) for p in pasta.rglob("*") if p.is_file()}
        saida = self.raiz / "b.json"
        self.assertEqual(self.rodar(bench, ["--sessao", str(pasta), "--saida", str(saida)]), 0)
        self.assertEqual(antes, {p.name: sha(p) for p in pasta.rglob("*") if p.is_file()})
        j = json.loads(saida.read_text(encoding="utf-8"))
        self.assertIs(j["simulado"], False)
        for campo in ("hostname", "plataforma", "versoes", "git_commit", "git_sujo", "pico_rss_processo_bytes"):
            self.assertIn(campo, j)
        s = j["sessoes"][0]
        self.assertEqual(s["aliases_identificados"], 2 * 2)  # 2 classes x 2 capturas, alias fronteira
        self.assertEqual(s["capturas_logicas_lidas"], 2 * 2 * 3)
        self.assertTrue(s["integridade"]["hash_arrays_antes_depois_iguais"])
        self.assertIs(s["originais_inalterados"], True)
        self.assertEqual(s["consolidacao_em_copia"]["capturas_reescritas"], 2 * 2 * 2)
        self.assertEqual(len(s["sha256_metadata"]), 2)
        self.assertGreater(s["leitura_s"], 0)

    def test_simulado_true_se_sessao_nao_for_bancada(self):
        pasta = montar(self.raiz, "sessao_s", modo="simulado", simulado=True)
        j = bench.benchmark_sessoes([pasta])
        self.assertIs(j["simulado"], True)

    def test_recusa_sobrescrita_e_repeticao(self):
        pasta = montar(self.raiz, "sessao_a", classes=("06",))
        saida = self.raiz / "b.json"
        saida.write_text("x")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            bench.main(["--sessao", str(pasta), "--saida", str(saida)])
        self.assertEqual(saida.read_text(), "x")
        with self.assertRaises(ValueError):
            bench.benchmark_sessoes([pasta, pasta])

    def test_recusa_sessao_com_lock_ocupado(self):
        from sessao_io import BloqueioSessao, SessaoEmUsoError
        pasta = montar(self.raiz, "sessao_l", classes=("06",))
        self.assertIs(bench.medir_sessao(pasta)["lock_ocupado"], False)
        with BloqueioSessao(pasta):
            with self.assertRaises(SessaoEmUsoError):
                bench.medir_sessao(pasta)
            saida = self.raiz / "l.json"
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                bench.main(["--sessao", str(pasta), "--saida", str(saida)])
            self.assertFalse(saida.exists())

    def test_modo_sintetico_intacto(self):
        saida = self.raiz / "s.json"
        self.rodar(bench, ["--capturas", "1", "--pontos", "600", "--saida", str(saida)])
        j = json.loads(saida.read_text(encoding="utf-8"))
        self.assertNotIn("hostname", j)
        self.assertEqual(len(j["series"]), 1)


class CorrelacaoSessoes(Base):
    def test_duas_correlacoes_ignora_alias_e_simulada(self):
        fis = montar(self.raiz, "sessao_f", classes=("06", "10", "99"))
        sim = montar(self.raiz, "sessao_sim", classes=("06",), modo="simulado", simulado=True)
        saida = self.raiz / "c.json"
        self.assertEqual(self.rodar(amp, ["--sessao", str(fis), "--sessao", str(sim), "--saida", str(saida)]), 0)
        j = json.loads(saida.read_text(encoding="utf-8"))
        self.assertIs(j["simulado"], True)  # uma sessão não é bancada
        self.assertEqual({r["classe"] for r in j["registros"]}, {"06", "10"})
        self.assertEqual({r["perfil"] for r in j["registros"]}, {"norma", "literatura"})  # sem alias fronteira
        self.assertEqual(len(j["registros"]), 2 * 2 * 2)
        self.assertEqual(j["ignoradas"]["alias"], 3 * 2 + 2)  # 3 classes x2 + sessão simulada 1 classe x2
        self.assertEqual(j["ignoradas"]["simulada_ou_sem_metadata"], 4)  # sessão simulada, classe 06, 2 perfis x 2
        self.assertEqual(j["ignoradas"]["classe_fora_do_escopo"], 4)  # classe 99
        r = j["registros"][0]
        self.assertEqual(r["condicao"], "127V_60Hz")
        for par in ("modelo_x_programada", "modelo_x_medida", "programada_x_medida"):
            self.assertEqual(set(r["pares"][par]), {"nominal", "fundamental_ajustada"})
        self.assertIsNone(j["metrica_oficial"])
        self.assertTrue(j["agregados_por_classe_perfil_condicao"])
        self.assertTrue(all(e["sha256"] and e["arquivo"] for e in j["arquivos_entrada"]))
        # mesmas funções do modo sintético: valor idêntico ao cálculo direto
        import sinais
        from sessao_io import ler_capturas
        cap = next(c for c in ler_capturas(fis, versoes=("medida", "modelo", "programada"))
                   if c.perfil == "norma" and c.id_captura == r["id_captura"])
        direto, _ = sinais.correlacao_disturbio(cap.versoes["modelo"], cap.versoes["programada"],
                                                fs_hz=FS, f0_hz=60.0, fase_graus=0.0)
        self.assertAlmostEqual(r["pares"]["modelo_x_programada"]["nominal"]["valor"], direto)

    def test_sessao_aplica_filtros_de_classe_perfil_e_frequencia(self):
        fis = montar(self.raiz, "sessao_f", classes=("06", "10"))
        saida = self.raiz / "f.json"
        self.rodar(amp, ["--sessao", str(fis), "--classes", "06", "--perfis", "norma", "--saida", str(saida)])
        j = json.loads(saida.read_text(encoding="utf-8"))
        self.assertEqual({(r["classe"], r["perfil"]) for r in j["registros"]}, {("06", "norma")})
        saida2 = self.raiz / "f2.json"
        self.rodar(amp, ["--sessao", str(fis), "--frequencias", "50", "--saida", str(saida2)])
        self.assertEqual(json.loads(saida2.read_text(encoding="utf-8"))["registros"], [])  # fixture é 60 Hz

    def test_nan_nao_deixa_arquivo_parcial(self):
        fis = montar(self.raiz, "sessao_f", classes=("06",))
        saida = self.raiz / "n.json"
        rel = amp.analisar_sessoes([fis])
        rel["registros"][0]["x"] = float("nan")
        with mock.patch.object(amp, "analisar_sessoes", return_value=rel), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            amp.main(["--sessao", str(fis), "--saida", str(saida)])
        self.assertFalse(saida.exists())

    def test_fisica_bancada_e_recusa_sobrescrita(self):
        fis = montar(self.raiz, "sessao_f", classes=("06",))
        saida = self.raiz / "c.json"
        amp_j = amp.analisar_sessoes([fis])
        self.assertIs(amp_j["simulado"], False)
        saida.write_text("x")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            amp.main(["--sessao", str(fis), "--saida", str(saida)])
        self.assertEqual(saida.read_text(), "x")


class Agregador(tf.Base):
    def test_p22_le_benchmark_fisico_e_casa_hostname(self):
        pasta = montar(self.raiz, "sessao_p22", classes=("06",))
        art = self.raiz / "art"
        art.mkdir()
        j = bench.benchmark_sessoes([pasta])
        j["hostname"], j["git_sujo"], j["git_commit"] = "BANCADA", False, "abc123"
        (art / "benchmark_sessao_io_bancada.json").write_text(json.dumps(j), encoding="utf-8")
        pc = self.raiz / "pc.json"
        pc.write_text(json.dumps({"hostname": "bancada"}), encoding="utf-8")
        item = self.agregar(pasta, pc=pc, artefatos=[art])[0]["itens"]["P-22"]
        self.assertEqual(self.criterio(item, "executado_no_pc_da_bancada")["resultado"], "ok")
        self.assertEqual(self.criterio(item, "benchmark_de_sessoes_fisicas")["resultado"], "ok")
        j["sessoes"][0]["originais_inalterados"] = False
        (art / "benchmark_sessao_io_bancada.json").write_text(json.dumps(j), encoding="utf-8")
        item = self.agregar(pasta, pc=pc, artefatos=[art])[0]["itens"]["P-22"]
        self.assertEqual(self.criterio(item, "benchmark_de_sessoes_fisicas")["resultado"], "insuficiente")
        j["simulado"] = True  # benchmark simulado não vale
        (art / "benchmark_sessao_io_bancada.json").write_text(json.dumps(j), encoding="utf-8")
        item = self.agregar(pasta, pc=pc, artefatos=[art])[0]["itens"]["P-22"]
        self.assertEqual(self.criterio(item, "benchmark_de_sessoes_fisicas")["resultado"], "sem_dados")

    def test_p22_sessao_citada_nao_fornecida_ou_hash_divergente_e_insuficiente(self):
        a = montar(self.raiz, "sessao_a", classes=("06",))
        b = montar(self.raiz, "sessao_b", classes=("06",))
        art = self.raiz / "art"
        art.mkdir()
        j = bench.benchmark_sessoes([a, b])
        j["hostname"], j["git_sujo"], j["git_commit"] = "BANCADA", False, "abc123"
        (art / "benchmark_sessao_io_bancada.json").write_text(json.dumps(j), encoding="utf-8")
        item = self.agregar(a, b, artefatos=[art])[0]["itens"]["P-22"]
        self.assertEqual(self.criterio(item, "benchmark_de_sessoes_fisicas")["resultado"], "ok")
        item = self.agregar(a, artefatos=[art])[0]["itens"]["P-22"]
        c = self.criterio(item, "benchmark_de_sessoes_fisicas")
        self.assertEqual(c["resultado"], "insuficiente")
        self.assertIn("sessao_b", json.dumps(c["valor_medido"]))
        j["sessoes"][1]["sha256_sessao_json"] = "0" * 64
        (art / "benchmark_sessao_io_bancada.json").write_text(json.dumps(j), encoding="utf-8")
        item = self.agregar(a, b, artefatos=[art])[0]["itens"]["P-22"]
        self.assertEqual(self.criterio(item, "benchmark_de_sessoes_fisicas")["resultado"], "insuficiente")

    def test_p31_sessao_citada_nao_fornecida_e_insuficiente(self):
        classes = amp.CLASSES
        a = montar(self.raiz, "sessao_a", classes=classes, n=1)
        b = montar(self.raiz, "sessao_b", classes=("06",), n=1)
        art = self.raiz / "art"
        art.mkdir()
        j = amp.analisar_sessoes([a, b])
        j["git_sujo"], j["git_commit"] = False, "abc123"
        (art / "modelo_programada_sessoes_x.json").write_text(json.dumps(j), encoding="utf-8")
        item = self.agregar(a, b, artefatos=[art])[0]["itens"]["P-31"]
        self.assertEqual(self.criterio(item, "correlacoes_nominal_e_ajustada_publicadas")["resultado"], "ok")
        item = self.agregar(a, artefatos=[art])[0]["itens"]["P-31"]
        c = self.criterio(item, "correlacoes_nominal_e_ajustada_publicadas")
        self.assertEqual(c["resultado"], "insuficiente")
        self.assertIn("sessao_b", json.dumps(c["valor_medido"]))

    def test_p31_publica_as_duas_e_exige_classes(self):
        classes = amp.CLASSES
        pasta = montar(self.raiz, "sessao_p31", classes=classes, n=1)
        art = self.raiz / "art"
        art.mkdir()
        j = amp.analisar_sessoes([pasta])
        j["git_sujo"], j["git_commit"] = False, "abc123"  # árvore de teste pode estar suja
        (art / "modelo_programada_sessoes_x.json").write_text(json.dumps(j), encoding="utf-8")
        item = self.agregar(pasta, artefatos=[art])[0]["itens"]["P-31"]
        c = self.criterio(item, "correlacoes_nominal_e_ajustada_publicadas")
        self.assertEqual(c["resultado"], "ok", c)
        self.assertTrue(item["requer_revisao_humana"])
        self.assertEqual(self.criterio(item, "metrica_oficial")["resultado"], "criterio_nao_definido")
        j["registros"] = [r for r in j["registros"] if r["classe"] != "16"]
        (art / "modelo_programada_sessoes_x.json").write_text(json.dumps(j), encoding="utf-8")
        item = self.agregar(pasta, artefatos=[art])[0]["itens"]["P-31"]
        self.assertEqual(self.criterio(item, "correlacoes_nominal_e_ajustada_publicadas")["resultado"], "insuficiente")
        (art / "modelo_programada_sessoes_x.json").unlink()
        item = self.agregar(pasta, artefatos=[art])[0]["itens"]["P-31"]
        self.assertEqual(self.criterio(item, "correlacoes_nominal_e_ajustada_publicadas")["resultado"], "sem_dados")


if __name__ == "__main__":
    unittest.main()
