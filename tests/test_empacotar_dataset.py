"""scripts/empacotar_dataset.py: pacote do dataset para o Zenodo (P-20).

Tudo aqui é FIXTURE sintética em diretório temporário; nenhuma sessão real é aberta,
nenhum DOI existe e nada chama rede.
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

RAIZ = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("empacotar_dataset", RAIZ / "scripts" / "empacotar_dataset.py")
ed = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ed
spec.loader.exec_module(ed)

COMMIT = "0123456789abcdef0123456789abcdef01234567"
CRIADORES = [{"name": "Autor, Um", "orcid": "0000-0000-0000-0001", "affiliation": "Inst. A"},
             {"name": "Autor Dois", "orcid": "0000-0000-0000-0002"}]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def arvore(raiz):
    """{caminho relativo: (tamanho, sha256)} de tudo sob raiz."""
    return {p.relative_to(raiz).as_posix(): (p.stat().st_size, sha(p)) for p in sorted(Path(raiz).rglob("*")) if p.is_file()}


def montar_sessao(base, nome, *, sujo=False, formato2=True):
    pasta = Path(base) / nome
    (pasta / "metadata").mkdir(parents=True)
    (pasta / "snr_30db").mkdir()
    cal = b'{"descricao": "calibracao de teste"}\n'
    (pasta / "01_normal.npz").write_bytes(b"NPZ-FALSO-01" * 50)
    (pasta / "02_sag.npz").write_bytes(b"NPZ-FALSO-02" * 70)
    (pasta / "snr_30db" / "01_normal.npz").write_bytes(b"SNR-FALSO" * 30)
    reg = {"id_captura": "01-0001", "classe": "NORMAL", "seed": 1}
    if formato2:
        (pasta / "calibracao_extremos.json").write_bytes(cal)
        cal_sha = hashlib.sha256(cal).hexdigest()
        reg.update(git_commit=COMMIT, git_sujo=sujo, versao_codigo="v1.15-3-gabcdef0" + ("-dirty" if sujo else ""),
                   calibracao_extremos_sha256=cal_sha)
        (pasta / "sessao.json").write_text(json.dumps({
            "formato_metadata": 2, "modo": "bancada", "git_commit": COMMIT, "git_sujo": sujo,
            "versao_codigo": reg["versao_codigo"],
            "calibracao_extremos": {"copia_na_sessao": "calibracao_extremos.json", "sha256": cal_sha}}), encoding="utf-8")
    else:  # sessão antiga: só jsonl, sem git_commit/git_sujo/calibração
        reg.update(versao_codigo="994e170-dirty" if sujo else "994e170")
    linha = json.dumps(reg) + "\n"
    (pasta / "metadata" / "01_normal.jsonl").write_text(linha, encoding="utf-8")
    (pasta / "metadata" / "01_normal.json").write_text(json.dumps([reg], indent=2), encoding="utf-8")
    # não devem ser copiados
    (pasta / "sessao.log").write_text("log", encoding="utf-8")
    (pasta / "scpi_transcricao.log").write_text("scpi", encoding="utf-8")
    (pasta / "relatorio_x.html").write_text("<html/>", encoding="utf-8")
    (pasta / "sem_margem").mkdir()
    (pasta / "sem_margem" / "01_normal.npz").write_bytes(b"derivado")
    return pasta


def cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        codigo = ed.main([str(a) for a in args])
    return codigo, out.getvalue(), err.getvalue()


class EmpacotarDatasetTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.sessao = montar_sessao(self.tmp / "resultados", "sessao_A")
        self.saida = self.tmp / "pacote" / "dataset_v1.15"

    def gerar(self, **kw):
        return ed.empacotar([self.sessao], self.saida, "v1.15", criadores=CRIADORES, **kw)

    def test_pacote_gerado_e_verificado(self):
        m = self.gerar()
        self.assertEqual(ed.verificar(self.saida), [])
        for nome in ("README.txt", "MANIFEST.json", "SHA256SUMS", "zenodo_dataset.json", "calibracao_extremos.json"):
            self.assertTrue((self.saida / nome).is_file(), nome)
        self.assertEqual(m["versao"], "v1.15")
        self.assertFalse(m["piloto"])
        s = m["sessoes"][0]
        self.assertEqual((s["git_commit"], s["git_sujo"]), (COMMIT, False))
        caminhos = {e["caminho"] for e in m["arquivos"]}
        self.assertIn("sessoes/sessao_A/01_normal.npz", caminhos)
        self.assertIn("sessoes/sessao_A/snr_30db/01_normal.npz", caminhos)
        self.assertIn("sessoes/sessao_A/metadata/01_normal.jsonl", caminhos)
        self.assertIn("sessoes/sessao_A/calibracao_extremos.json", caminhos)
        # derivados e logs ficam de fora
        self.assertFalse([c for c in caminhos if "sem_margem" in c or c.endswith(".log") or c.endswith(".html")])
        for e in m["arquivos"]:
            self.assertEqual(e["sha256"], sha(self.saida / e["caminho"]))
            self.assertEqual(e["tamanho"], (self.saida / e["caminho"]).stat().st_size)
        sums = (self.saida / "SHA256SUMS").read_text(encoding="utf-8")
        self.assertIn(f"{sha(self.saida / 'MANIFEST.json')}  MANIFEST.json", sums)
        self.assertNotIn("SHA256SUMS", sums)

    def test_zenodo_dataset_json(self):
        self.gerar()
        z = json.loads((self.saida / "zenodo_dataset.json").read_text(encoding="utf-8"))
        self.assertEqual((z["upload_type"], z["license"], z["version"]), ("dataset", "cc-by-4.0", "v1.15"))
        self.assertEqual(z["creators"], CRIADORES)
        rel = z["related_identifiers"]
        self.assertEqual(len(rel), 1)
        self.assertEqual(rel[0]["relation"], "isSupplementTo")
        self.assertEqual(rel[0]["identifier"], "https://github.com/DenisLN/anti-synthetic-data/releases/tag/v1.15")
        self.assertNotIn("publication_date", z)
        self.assertNotIn("doi", z)
        readme = (self.saida / "README.txt").read_text(encoding="utf-8")
        self.assertIn("CC-BY 4.0", readme)
        self.assertIn("SHA256SUMS", readme)
        for p in self.saida.rglob("*"):
            if p.is_file() and p.suffix in (".json", ".txt"):
                self.assertNotIn("10.5281", p.read_text(encoding="utf-8"), p.name)

    def test_arquivo_adulterado_e_detectado(self):
        self.gerar()
        alvo = self.saida / "sessoes" / "sessao_A" / "01_normal.npz"
        alvo.write_bytes(alvo.read_bytes() + b"x")
        problemas = ed.verificar(self.saida)
        self.assertTrue(any("DIVERGENTE" in p and "01_normal.npz" in p for p in problemas), problemas)
        codigo, saida, _ = cli("--verificar", self.saida)
        self.assertEqual(codigo, 1)
        self.assertIn("DIVERGENCIA", saida)

    def test_arquivo_ausente_e_arquivo_extra_sao_detectados(self):
        self.gerar()
        (self.saida / "sessoes" / "sessao_A" / "02_sag.npz").unlink()
        (self.saida / "intruso.txt").write_text("x", encoding="utf-8")
        problemas = ed.verificar(self.saida)
        self.assertTrue(any(p.startswith("AUSENTE") and "02_sag.npz" in p for p in problemas), problemas)
        self.assertTrue(any(p.startswith("FORA DO SHA256SUMS") and "intruso.txt" in p for p in problemas), problemas)
        self.assertEqual(cli("--verificar", self.saida)[0], 1)

    def test_verificar_ok_pela_cli(self):
        self.gerar()
        codigo, saida, _ = cli("--verificar", self.saida)
        self.assertEqual(codigo, 0)
        self.assertIn("OK", saida)

    def test_verificar_sem_pacote_sai_com_erro(self):
        self.assertEqual(cli("--verificar", self.tmp / "nao_existe")[0], 2)

    def test_sessao_suja_recusada_sem_piloto(self):
        suja = montar_sessao(self.tmp / "resultados", "sessao_suja", sujo=True)
        with self.assertRaises(ed.Recusa) as cm:
            ed.empacotar([suja], self.saida, "v1.15", criadores=CRIADORES)
        self.assertIn("git_sujo verdadeiro", str(cm.exception))
        self.assertFalse(self.saida.exists())
        codigo, _, err = cli(suja, "--saida", self.saida, "--versao", "v1.15")
        self.assertEqual(codigo, 2)
        self.assertIn("RECUSADO", err)

    def test_piloto_aceita_suja_e_marca_manifest_e_titulo(self):
        suja = montar_sessao(self.tmp / "resultados", "sessao_suja", sujo=True)
        m = ed.empacotar([suja], self.saida, "v1.15", piloto=True, criadores=CRIADORES)
        self.assertTrue(m["piloto"])
        self.assertTrue(m["sessoes"][0]["git_sujo"])
        self.assertTrue(m["titulo"].startswith("[PILOTO]"))
        z = json.loads((self.saida / "zenodo_dataset.json").read_text(encoding="utf-8"))
        self.assertTrue(z["title"].startswith("[PILOTO]"))
        self.assertTrue(json.loads((self.saida / "MANIFEST.json").read_text(encoding="utf-8"))["piloto"])
        self.assertEqual(ed.verificar(self.saida), [])

    def test_sessao_antiga_sem_sessao_json(self):
        antiga = montar_sessao(self.tmp / "resultados", "sessao_antiga", sujo=True, formato2=False)
        with self.assertRaises(ed.Recusa):
            ed.empacotar([antiga], self.saida, "v1.15", criadores=CRIADORES)
        m = ed.empacotar([antiga], self.saida, "v1.15", piloto=True, criadores=CRIADORES)
        s = m["sessoes"][0]
        self.assertEqual((s["git_commit"], s["git_sujo"]), ("994e170", True))
        self.assertIn("versao_codigo", s["git_commit_origem"])
        self.assertFalse(s["calibracao_extremos"]["presente"])
        self.assertTrue(m["avisos"])
        self.assertFalse((self.saida / "calibracao_extremos.json").exists())

    def test_sessao_antiga_sem_marca_dirty_e_indeterminada(self):
        antiga = montar_sessao(self.tmp / "resultados", "sessao_antiga", sujo=False, formato2=False)
        with self.assertRaises(ed.Recusa) as cm:
            ed.empacotar([antiga], self.saida, "v1.15", criadores=CRIADORES)
        self.assertIn("indeterminado", str(cm.exception))

    def test_calibracao_que_nao_bate_com_o_metadata_e_recusada_mesmo_com_piloto(self):
        (self.sessao / "calibracao_extremos.json").write_text('{"outra": 1}', encoding="utf-8")
        with self.assertRaises(ed.Recusa) as cm:
            self.gerar(piloto=True)
        self.assertIn("não bate", str(cm.exception))

    def test_originais_intactos(self):
        antes = arvore(self.sessao)
        self.gerar()
        self.assertEqual(arvore(self.sessao), antes)
        # idem em modo piloto e na verificação
        self.setUp()
        suja = montar_sessao(self.tmp / "resultados", "sessao_suja", sujo=True)
        antes = arvore(suja)
        ed.empacotar([suja], self.saida, "v1.15", piloto=True, criadores=CRIADORES)
        ed.verificar(self.saida)
        self.assertEqual(arvore(suja), antes)

    def test_saida_ocupada_ou_dentro_da_sessao_e_recusada(self):
        self.gerar()
        with self.assertRaises(ed.Recusa):
            self.gerar()
        with self.assertRaises(ed.Recusa):
            ed.empacotar([self.sessao], self.sessao / "pacote", "v1.15", criadores=CRIADORES)

    def test_duas_sessoes_com_a_mesma_calibracao_geram_um_arquivo_na_raiz(self):
        b = montar_sessao(self.tmp / "resultados", "sessao_B")
        m = ed.empacotar([self.sessao, b], self.saida, "v1.15", criadores=CRIADORES)
        self.assertEqual([s["sessao"] for s in m["sessoes"]], ["sessao_A", "sessao_B"])
        self.assertIsNotNone(m["calibracao_extremos"])
        self.assertEqual(ed.verificar(self.saida), [])


class ArquivosDoRepositorioTests(unittest.TestCase):
    """Os metadados de publicação versionados na raiz."""

    def test_zenodo_json_do_codigo(self):
        z = json.loads((RAIZ / ".zenodo.json").read_text(encoding="utf-8"))
        self.assertEqual((z["upload_type"], z["license"]), ("software", "mit"))
        self.assertEqual([c["orcid"] for c in z["creators"]], ["0009-0002-5691-6774", "0009-0001-3141-4498"])
        self.assertNotIn("doi", z)
        self.assertNotIn("publication_date", z)

    def test_citation_cff_e_licenca(self):
        cff = (RAIZ / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn("cff-version: 1.2.0", cff)
        self.assertIn("license: MIT", cff)
        self.assertIn("repository-code: \"https://github.com/DenisLN/anti-synthetic-data\"", cff)
        self.assertLess(cff.index("0009-0002-5691-6774"), cff.index("0009-0001-3141-4498"))
        self.assertNotIn("doi:", cff)
        self.assertEqual(ed.versao_do_citation(), "v1.15")
        self.assertTrue((RAIZ / "LICENSE").read_text(encoding="utf-8").startswith("MIT License"))
        self.assertEqual([c["name"] for c in ed.criadores_do_zenodo_json()],
                         [c["name"] for c in json.loads((RAIZ / ".zenodo.json").read_text(encoding="utf-8"))["creators"]])


if __name__ == "__main__":
    unittest.main()
