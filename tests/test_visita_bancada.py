"""Visita à bancada num comando (scripts/visita_bancada.py) e o modo roteiro
da CLI (``cli.py --comando``): sem hardware, sem energizar."""

import contextlib
import io
import json
import math
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
for pasta in (RAIZ / "logica", RAIZ / "scripts"):
    if str(pasta) not in sys.path:
        sys.path.insert(0, str(pasta))

import cli
import mestre
import visita_bancada as vb


class RoteiroDaCLI(unittest.TestCase):
    def setUp(self):
        self.sessao = cli.SessaoCLI()

    def roteiro(self, comandos):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.sessao.executar_roteiro(comandos)

    def test_recusa_entrada_que_nao_e_terminal_antes_de_tudo(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=False), \
                mock.patch.object(cli.SessaoCLI, "executar_roteiro") as roteiro, \
                contextlib.redirect_stdout(io.StringIO()) as saida:
            codigo = cli.main(["--comando", "run 01"])
        self.assertEqual(codigo, cli.SessaoCLI.ROTEIRO_INVALIDO)
        roteiro.assert_not_called()
        self.assertIn("não é um terminal", saida.getvalue())

    def test_confirmacao_nao_digitada_para_o_roteiro_sem_energizar(self):
        with mock.patch.object(mestre, "BATERIA_EXCLUIR", ()), \
                mock.patch("builtins.input", return_value="errado"), \
                mock.patch.object(mestre.Bancada, "from_env") as bancada, \
                mock.patch.object(self.sessao, "cmd_status") as status:
            codigo = self.roteiro(["run 01,02", "status"])
        self.assertEqual(codigo, cli.SessaoCLI.ROTEIRO_NAO_CONFIRMADO)
        bancada.assert_not_called()
        status.assert_not_called()  # parou no primeiro run não confirmado

    def test_a_confirmacao_vem_do_teclado_e_nao_dos_comandos(self):
        pedidos = []

        def teclado(prompt):
            pedidos.append(prompt)
            return "nao"

        with mock.patch.object(mestre, "BATERIA_EXCLUIR", ()), \
                mock.patch("builtins.input", side_effect=teclado), \
                mock.patch.object(mestre.Bancada, "from_env"):
            self.roteiro(["run 01,02"])
        self.assertEqual(pedidos, ["Digite EXECUTAR-CLASSES-01-02: "])

    def test_falhas_de_classe_seguem_e_infraestrutura_para(self):
        chamadas = []

        def run(_self, args):
            chamadas.append(args)
            return 1

        with mock.patch.dict(cli.SessaoCLI.COMANDOS, {"run": run}):
            self.assertEqual(self.roteiro(["run 07,17", "run 07,17"]), cli.SessaoCLI.ROTEIRO_COM_FALHAS)
        self.assertEqual(len(chamadas), 2)

        def run_infra(_self, args):
            _self.falha_infraestrutura = True
            return 1

        chamadas.clear()
        with mock.patch.dict(cli.SessaoCLI.COMANDOS, {"run": run_infra}):
            self.assertEqual(self.roteiro(["run 01", "run 02"]), cli.SessaoCLI.ROTEIRO_INFRAESTRUTURA)

    def test_excecao_preflight_ou_set_recusado_param(self):
        def explode(_self, args):
            raise RuntimeError("serial caiu")

        with mock.patch.dict(cli.SessaoCLI.COMANDOS, {"run": explode}):
            self.assertEqual(self.roteiro(["run 01"]), cli.SessaoCLI.ROTEIRO_INFRAESTRUTURA)
        with mock.patch.dict(cli.SessaoCLI.COMANDOS, {"comm": lambda _s, _a: 1}):
            self.assertEqual(self.roteiro(["comm", "run 01"]), cli.SessaoCLI.ROTEIRO_INFRAESTRUTURA)
        with mock.patch.object(mestre.Bancada, "from_env") as bancada:
            self.assertEqual(self.roteiro(["set perfil inexistente", "run 01"]), cli.SessaoCLI.ROTEIRO_INVALIDO)
            self.assertEqual(self.roteiro(["quit"]), cli.SessaoCLI.ROTEIRO_INVALIDO)
        bancada.assert_not_called()

    def test_excecao_num_run_de_classe_marca_infraestrutura(self):
        with mock.patch.object(self.sessao, "confirmar", return_value=True), \
                mock.patch.object(self.sessao, "autorizar_saida"), \
                mock.patch.object(self.sessao, "_garantir_pasta_sessao"), \
                mock.patch.object(self.sessao, "_liberar_bloqueio_sessao"), \
                mock.patch.object(mestre.Bancada, "from_env", side_effect=RuntimeError("sem fonte")):
            codigo = self.roteiro(["run 01"])
        self.assertEqual(codigo, cli.SessaoCLI.ROTEIRO_INFRAESTRUTURA)

    def test_codigos_iguais_aos_do_orquestrador(self):
        self.assertEqual(
            (vb.CLI_OK, vb.CLI_COM_FALHAS, vb.CLI_INFRA, vb.CLI_NAO_CONFIRMADO, vb.CLI_INVALIDO),
            (cli.SessaoCLI.ROTEIRO_OK, cli.SessaoCLI.ROTEIRO_COM_FALHAS, cli.SessaoCLI.ROTEIRO_INFRAESTRUTURA,
             cli.SessaoCLI.ROTEIRO_NAO_CONFIRMADO, cli.SessaoCLI.ROTEIRO_INVALIDO))


class SegurancaDoOrquestrador(unittest.TestCase):
    FONTE = (RAIZ / "scripts" / "visita_bancada.py").read_text(encoding="utf-8")

    def test_nao_contem_palavra_de_confirmacao(self):
        self.assertIsNone(re.search(r"(EXECUTAR|ENERGIZAR)-", self.FONTE))

    def test_processos_filhos_herdam_o_teclado(self):
        self.assertNotIn("stdin=", self.FONTE)
        self.assertNotIn("input=", self.FONTE)
        self.assertNotIn("communicate(", self.FONTE)

    def test_ctrl_c_espera_o_filho_sem_mata_lo(self):
        proc = mock.Mock()
        proc.wait.side_effect = [KeyboardInterrupt, 0]
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
            vb.esperar_processo(proc)
        self.assertEqual(proc.wait.call_count, 2)
        proc.kill.assert_not_called()
        proc.terminate.assert_not_called()
        self.assertNotIn("subprocess.call(", self.FONTE)

    def test_limites_iguais_aos_do_start_bench(self):
        self.assertEqual(vb.TETO_PICO_V, 415.8)
        env = vb.env_condicao(230, 50, base={})
        self.assertEqual(env["EUT_MAX_PEAK_V"], "415.8")
        self.assertEqual(env["SOURCE_VOLTAGE_RANGE_RMS"], "300")
        self.assertEqual(env["EUT_MAX_VOLTAGE_RMS"], "300")
        self.assertEqual(env["ARM_OUTPUT"], "NO")
        self.assertEqual((env["BASE_VOLTAGE_RMS"], env["GRID_FREQUENCY_HZ"]), ("230", "50"))
        self.assertNotIn("AMETEK_PORT", env)  # não mexe na porta: vem do bench_config.ps1
        ps1 = (RAIZ / "scripts" / "start_bench_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("$sourceRange = 300.0", ps1)
        self.assertIn("[math]::Sqrt(2) * 0.98, 1)", ps1)
        for tensao in (0, 271, 380):
            with self.assertRaises(ValueError):
                vb.env_condicao(tensao, 60, base={})

    def test_ambiente_exige_com10_probe_e_corrente_desligada(self):
        ok = {"AMETEK_PORT": "COM10", "AMETEK_BAUDRATE": "115200", "VOLTAGE_PROBE_ATTENUATION": "100",
              "CAPTURE_CURRENT": "0"}
        self.assertEqual(vb.conferir_ambiente_bancada(ok), [])
        for chave, valor in (("AMETEK_PORT", "COM3"), ("AMETEK_BAUDRATE", "9600"),
                             ("VOLTAGE_PROBE_ATTENUATION", ""), ("CAPTURE_CURRENT", "1")):
            self.assertTrue(vb.conferir_ambiente_bancada(dict(ok, **{chave: valor})), chave)

    def test_tipos_reexecutaveis_iguais_ao_mestre(self):
        self.assertEqual(vb.TIPOS_REEXECUTAVEIS, mestre.TIPOS_REEXECUTAVEIS)

    def test_etapas_unicas_ordem_do_roteiro_e_condicoes_da_p26(self):
        ids = [e.id for e in vb.ETAPAS]
        self.assertEqual(len(ids), len(set(ids)))
        ordem = ["01-suite", "02-infra", "04-marcadores", "05-acdc-60", "06-classe08", "07-rodada1",
                 "07-commit1", "07-rodada2", "07-commit", "08-parte1", "09-parte2", "10B-diag", "10A-passo-sine", "C-127V_50Hz",
                 "C-127V_50Hz-calibrar", "C-230V_50Hz", "11-entrega"]
        self.assertEqual([i for i in ids if i in ordem], ordem)
        # Toda campanha acima de 127 V vem depois da calibração da própria frequência.
        for antes, depois in (("C-127V_50Hz-calibrar", "C-230V_50Hz"),
                              ("C-220V_60Hz-calibrar", "C-220V_60Hz"), ("C-33V_60Hz-calibrar", "C-33V_60Hz")):
            self.assertLess(ids.index(antes), ids.index(depois))
        condicoes = {vb.chave(*e.condicao) for e in vb.ETAPAS if e.condicao}
        self.assertEqual(condicoes, {"127V_60Hz", "127V_50Hz", "230V_50Hz", "220V_60Hz", "33V_60Hz"})
        for e in vb.ETAPAS:
            if e.energiza:
                self.assertIsNotNone(e.condicao, e.id)
        # Sem ACDC a 230 V (P-26, opção A).
        self.assertFalse([e for e in vb.ETAPAS if "acdc" in e.id and e.condicao[0] != 127])

    def test_reexecucoes_de_2026_10_22_depois_do_10a_e_antes_de_50hz(self):
        ids = [e.id for e in vb.ETAPAS]
        reexec = [e for e in vb.ETAPAS if e.bloco == "R"]
        self.assertEqual([e.id for e in reexec], ["R-02-17-18-19", "R-p08-10-11", "R-p08-12-16"])
        for e in reexec:
            self.assertTrue(e.energiza)
            self.assertEqual(e.condicao, (127.0, 60.0))
            self.assertLess(ids.index("10A-passo-sine"), ids.index(e.id))
            self.assertLess(ids.index(e.id), ids.index("C-127V_50Hz"))
        # A 17 vai junto e antes da 18 (a correção da forma só se prova assim).
        classes = vb.REEXECUCOES_2026_10_22[0][1].split(",")
        self.assertLess(classes.index("17"), classes.index("18"))
        # P-08: 10/11/12/16 custam 108 gravações cada; dois por conexão (216).
        self.assertEqual(sorted(c for _, l in vb.REEXECUCOES_2026_10_22[1:] for c in l.split(",")),
                         ["10", "11", "12", "16"])
        self.assertTrue(all(len(l.split(",")) == 2 for _, l in vb.REEXECUCOES_2026_10_22[1:]))

    def test_empacotar_respeita_orcamento(self):
        grupos, fora = vb.empacotar_grupos([("01", 0), ("06", 108), ("10", 108), ("11", 108), ("99", 300)], 216)
        self.assertEqual(grupos, [["01", "06", "10"], ["11"]])
        self.assertEqual(fora, ["99"])

    def test_exclusoes(self):
        self.assertEqual(vb.sem_excluidas("07,08,09,20", ["08", "07"]), "09,20")


class FluxoDaVisita(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.resultados = self.tmp / "resultados"
        self.resultados.mkdir()
        p = mock.patch.object(vb, "RESULTADOS", self.resultados)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(vb, "arvore_suja", return_value=[])
        self.arvore = p.start()
        self.addCleanup(p.stop)
        silencio = contextlib.redirect_stdout(io.StringIO())
        silencio.__enter__()
        self.addCleanup(silencio.__exit__, None, None, None)
        self.chamadas = []
        self.respostas = []
        self.codigos = []
        self.v = vb.Visita(self.tmp / "visita", {"id": "t", "etapas": {}},
                           entrada=lambda _p: self.respostas.pop(0) if self.respostas else "",
                           executar_processo=self.processo)

    def processo(self, argv, env):
        self.chamadas.append((argv, env))
        if "--comando" in argv:
            (self.resultados / f"sessao_{len(self.chamadas):03d}").mkdir()
        return self.codigos.pop(0) if self.codigos else 0

    def etapa(self, executar, energiza=True, condicao=(127.0, 60.0), eid="x"):
        return vb.Etapa(eid, "t", "teste", energiza, executar, condicao)

    def comandos(self, argv):
        return [argv[i + 1] for i, a in enumerate(argv) if a == "--comando"]

    def test_cli_recebe_comandos_e_condicao_e_registra_sessao(self):
        et = self.etapa(vb.e_parte9("06,10"), eid="09-parte2")
        with mock.patch.object(vb.Visita, "conferir"), mock.patch.object(vb.Visita, "offline"):
            vb.rodar_visita(self.v, [et])
        argv, env = self.chamadas[0]
        self.assertEqual(self.comandos(argv), ["set perfil todos", "set diagnostico bruto on", "run 06,10"])
        self.assertEqual((env["BASE_VOLTAGE_RMS"], env["GRID_FREQUENCY_HZ"]), ("127", "60"))
        reg = self.v.estado["etapas"]["09-parte2"]
        self.assertEqual(reg["status"], "ok")
        self.assertEqual(len(reg["sessoes"]), 1)

    def _diag_grava(self, conteudo):
        def diag(_v, _et, script, args):
            pasta = Path(args[args.index("--saida") + 1])
            self.assertEqual(pasta, self.v.pasta)
            pasta.mkdir(parents=True, exist_ok=True)
            if conteudo is not None:
                (pasta / "diag_list_offset-20261022-152743.json").write_text(json.dumps(conteudo), encoding="utf-8")
            return 0
        return mock.patch.object(vb.Visita, "diag", diag)

    def test_diag_list_offset_le_o_json_dentro_da_pasta(self):
        et = next(e for e in vb.ETAPAS if e.id == "10B-diag")
        with self._diag_grava({"resultado": {"suportado": False}}):
            self.assertEqual(et.executar(self.v, et), "ok")
        self.assertIs(self.v.estado["p09_c_suportado"], False)
        with self._diag_grava({"resultado": {"suportado": True}}):
            et.executar(self.v, et)
        self.assertIs(self.v.estado["p09_c_suportado"], True)

    def test_diag_list_offset_sem_resultado_para_em_vez_de_ok(self):
        et = next(e for e in vb.ETAPAS if e.id == "10B-diag")
        with self._diag_grava(None), self.assertRaises(vb.VisitaParada):
            et.executar(self.v, et)
        self.assertNotIn("p09_c_suportado", self.v.estado)

    def test_calibracao_de_50hz_usa_as_sessoes_da_campanha_de_127v(self):
        sessao = self.resultados / "sessao_c127_50"
        sessao.mkdir()
        self.v.estado["etapas"] = {"C-127V_50Hz": {"sessoes": [str(sessao)]}}
        et = next(e for e in vb.ETAPAS if e.id == "C-127V_50Hz-calibrar")
        with mock.patch.object(vb.Visita, "offline", return_value=0) as offline, \
             mock.patch.object(vb, "commit_calibracao", return_value="ok") as commit:
            self.respostas = ["P"]
            with self.assertRaises(vb.VisitaParada):
                et.executar(self.v, et)
            commit.assert_not_called()
            self.respostas = ["GRAVAR"]
            self.assertEqual(et.executar(self.v, et), "ok")
        self.assertEqual(offline.call_args_list[-1].args[1], [str(sessao), "--gravar"])
        self.assertIn("127V_50Hz", commit.call_args.args[1])

    def test_sessao_gravada_em_outro_pc_e_achada_pelo_nome(self):
        (self.resultados / "sessao_2026-10-22_15-19-56").mkdir()
        outro_pc = r"C:\Users\Outra Pessoa\anti-synthetic-data\resultados\sessao_2026-10-22_15-19-56"
        sumida = r"C:\Users\Outra Pessoa\anti-synthetic-data\resultados\sessao_inexistente"
        self.v.estado["etapas"] = {"a": {"sessoes": [outro_pc]}, "b": {"sessoes": [sumida, outro_pc]}}
        local = self.resultados / "sessao_2026-10-22_15-19-56"
        self.assertEqual(self.v.sessoes_de("a"), [local])
        self.assertEqual(self.v.todas_as_sessoes(), [local, Path(sumida)])
        self.assertFalse(Path(sumida).is_dir())  # inexistente continua inexistente: quem usa filtra

    def test_nao_confirmado_para_e_retoma_da_mesma_etapa(self):
        a = self.etapa(vb.e_parte9("06,10"), eid="a")
        b = self.etapa(vb.e_parte9("11,12"), eid="b")
        self.codigos = [vb.CLI_NAO_CONFIRMADO]
        with mock.patch.object(vb.Visita, "conferir"):
            with self.assertRaises(vb.NaoConfirmado):
                vb.rodar_visita(self.v, [a, b])
            self.assertEqual(self.v.estado["etapas"]["a"]["status"], "parada")
            self.assertEqual(len(self.chamadas), 1)
            vb.rodar_visita(self.v, [a, b])
        self.assertEqual([self.comandos(c[0])[-1] for c in self.chamadas], ["run 06,10", "run 06,10", "run 11,12"])
        vb.rodar_visita(self.v, [a, b])  # tudo concluído: nada roda de novo
        self.assertEqual(len(self.chamadas), 3)

    def test_infraestrutura_para_a_visita(self):
        self.codigos = [vb.CLI_INFRA]
        with self.assertRaises(vb.VisitaParada) as ctx:
            vb.rodar_visita(self.v, [self.etapa(vb.e_parte9("06,10"))])
        self.assertIn("OUTPUT OFF", str(ctx.exception))

    def test_diagnostico_com_erro_para_a_visita(self):
        self.codigos = [2]
        with mock.patch.dict("os.environ", {"VOLTAGE_PROBE_ATTENUATION": "100"}), \
                self.assertRaises(vb.VisitaParada):
            vb.rodar_visita(self.v, [self.etapa(vb.e_acdc(60))])
        argv, _ = self.chamadas[0]
        self.assertIn("--testar-compensacao", argv)
        self.assertEqual(argv[argv.index("--probe") + 1], "100")

    def test_arvore_suja_impede_etapa_que_energiza(self):
        self.arvore.return_value = [" M logica/mestre.py"]
        with self.assertRaises(vb.VisitaParada):
            vb.rodar_visita(self.v, [self.etapa(vb.e_parte9("06,10"))])
        self.assertEqual(self.chamadas, [])

    def test_falhas_oferecem_rerun_na_mesma_condicao(self):
        def processo(argv, env):
            self.chamadas.append((argv, env))
            pasta = self.resultados / f"sessao_{len(self.chamadas):03d}"
            pasta.mkdir()
            if len(self.chamadas) == 1:
                (pasta / "falhas.json").write_text(json.dumps({"itens": [
                    {"tipo": "invalida"}, {"tipo": "pulada_preflight"}]}), encoding="utf-8")
                return vb.CLI_COM_FALHAS
            return vb.CLI_OK

        self.v.executar_processo = processo
        self.respostas = ["s"]
        with mock.patch.object(vb.Visita, "conferir"):
            vb.rodar_visita(self.v, [self.etapa(vb.e_parte9("06,10"), condicao=(230.0, 50.0))])
        self.assertEqual(len(self.chamadas), 2)
        rerun_argv, rerun_env = self.chamadas[1]
        cmds = self.comandos(rerun_argv)
        self.assertTrue(cmds[-1].startswith("run falhas "))
        self.assertIn("set diagnostico bruto on", cmds)
        self.assertEqual(rerun_env["BASE_VOLTAGE_RMS"], "230")

    def test_08_reprovada_sai_da_parte6_e_nao_tem_rerun(self):
        self.codigos = [vb.CLI_COM_FALHAS]
        with mock.patch.object(vb.Visita, "conferir"), \
                mock.patch.object(vb, "classe_reprovou", return_value=True):
            vb.rodar_visita(self.v, [self.etapa(vb.e_classe08, condicao=(127.0, 50.0), eid="06-classe08")])
            self.assertEqual(self.v.excluidas_127_60, ["08"])
            self.assertEqual(len(self.chamadas), 1)
            vb.rodar_visita(self.v, [self.etapa(vb.e_parte9("07,08,09,20"), eid="09-parte6")])
        self.assertEqual(self.comandos(self.chamadas[1][0])[-1], "run 07,09,20")

    def test_braco_c_pulado_sem_suporte(self):
        etapas = [e for e in vb.ETAPAS if e.id == "10B-braco-C"]
        with mock.patch.object(vb.Visita, "conferir"):
            vb.rodar_visita(self.v, etapas)
        self.assertEqual(self.v.estado["etapas"]["10B-braco-C"]["status"], "pulada")
        self.assertEqual(self.chamadas, [])

    def test_campanha_retoma_do_grupo_seguinte(self):
        plano = {"grupos": ["01,02", "06,10", "11,12"], "excedentes": []}
        self.codigos = [vb.CLI_OK, vb.CLI_INFRA]
        et = self.etapa(vb.e_campanha("todos", True), condicao=(127.0, 50.0), eid="C")
        with mock.patch.object(vb, "planejar_grupos", return_value=plano), \
                mock.patch.object(vb.Visita, "conferir"):
            with self.assertRaises(vb.VisitaParada):
                vb.rodar_visita(self.v, [et])
            vb.rodar_visita(self.v, [et])
        self.assertEqual([self.comandos(c[0])[-1] for c in self.chamadas],
                         ["run 01,02", "run 06,10", "run 06,10", "run 11,12"])


class ConferenciaDeSeguranca(unittest.TestCase):
    def sessao(self, registros):
        pasta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        (pasta / "metadata").mkdir()
        with open(pasta / "metadata" / "x.jsonl", "w", encoding="utf-8") as fh:
            for r in registros:
                fh.write(json.dumps(dict({"simulado": False}, **r)) + "\n")
        return pasta

    def test_sobressinal_da_08_para(self):
        s = self.sessao([{"id_captura": "08-0001", "tensao_base_rms": 127.0, "f0_hz": 50.0,
                          "parametros": {"inicio_impulso_s": 0.09}, "pico_medido_v": 300.0, "vale_medido_v": -200.0,
                          "validacao_fisica": {"ok": True, "posicao_evento": {"sobressinal_medido": 0.6}}}])
        parar, _ = vb.conferir_seguranca([s])
        self.assertTrue(parar)

    def test_extremo_acima_do_previsto_alerta_e_acima_do_teto_para(self):
        s = self.sessao([{"id_captura": "10-0001", "pico_medido_v": 250.0, "vale_medido_v": -240.0,
                          "extremo_previsto_v": 230.0, "teto_extremos_v": 400.0}])
        parar, alertas = vb.conferir_seguranca([s])
        self.assertEqual(parar, [])
        self.assertEqual(len(alertas), 1)
        s2 = self.sessao([{"id_captura": "10-0002", "pico_medido_v": 405.0, "vale_medido_v": -240.0,
                           "extremo_previsto_v": 230.0, "teto_extremos_v": 400.0}])
        parar, _ = vb.conferir_seguranca([s2])
        self.assertTrue(parar)

    def test_alerta_pede_decisao(self):
        v = vb.Visita(Path(tempfile.mkdtemp()), {}, entrada=lambda _p: "P")
        self.addCleanup(shutil.rmtree, v.pasta, ignore_errors=True)
        with mock.patch.object(vb, "conferir_seguranca", return_value=([], ["x"])):
            with self.assertRaises(vb.VisitaParada):
                v.conferir([Path("s")])
        v.entrada = lambda _p: "C"
        with mock.patch.object(vb, "conferir_seguranca", return_value=([], ["x"])):
            v.conferir([Path("s")])


if __name__ == "__main__":
    unittest.main()
