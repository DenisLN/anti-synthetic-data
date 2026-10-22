"""P-09: experimento A/B/C de offset por passo, só simulação (sem hardware).

A = comportamento de sempre (padrão). B = AC+DC com offset zero. C = AC+DC com
offset DC por passo de LIST (SOURce:LIST:VOLTage:OFFSet, NÃO confirmado no
manual). Nada aqui encerra a P-09: o suporte real é decidido na bancada.
"""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "logica") not in sys.path:
    sys.path.insert(0, str(RAIZ / "logica"))

import ametek_orm  # noqa: E402
import mestre  # noqa: E402
from ametek_orm import (  # noqa: E402
    AmetekMX30, BracoP09Error, OffsetPorPassoNaoSuportadoError, ParameterOutOfBoundsError,
)

# sha256 da sequência de comandos SCPI simulados de _sequencia() (sem as linhas
# TRACe:DATA e SOURce:LIST:VOLTage, cujos números dependem do arredondamento
# de ponto flutuante da plataforma), gravada com o código ANTES da P-09
# (árvore em ef3d49d): 156 comandos, 948394cd... Desde 2026-10-22 cada
# restaurar_forma_e_modo_padrao() depois de uma LIST de TRACEs manda também
# FUNCtion:SHAPe SINusoid, *WAI, SYSTem:ERRor? (2 trios aqui); sem os trios a
# sequência é a de ef3d49d, byte a byte.
SHA_SEQUENCIA_A_ANTES = "755ce5d5d92de5f82d4dddff0bcbd1af9d3a11a04857cddaed09d95ce5f340c8"
N_SEQUENCIA_A_ANTES = 162


def forma_classe16(f0=50.0, seed=2, perfil="fronteira"):
    """Caso de referência da P-09: classe 16, perfil fronteira, seed 2, 50 Hz
    (mesma receita de scripts/analisar_modelo_programado.gerar_relatorio)."""
    config = mestre.Config(
        fs_hz=30000., points=6000, duration_s=.2, grid_frequency_hz=f0,
        base_voltage_rms=127., snr_levels_db=(), base_seed=seed, capture_current=False,
        current_base_a=None, results_dir=Path('.'), sim_captures_per_class=1,
        real_captures_per_class=1, disturbance_start_s=.06, sorteio_posicao=True, perfil=perfil,
    )
    tipo = mestre.Bancada._carregar_classe_experimento(RAIZ / "experimentos_waveform" / "16.py")
    experimento = tipo(mestre.Bancada(None, None, config))
    t = np.arange(6000) / 30000.
    forma, _ = experimento.gerar(t, f0, 0, np.random.default_rng(seed))
    return np.asarray(forma, dtype=np.float64)


def _fonte(braco=None, suportado=False, **kw):
    extra = {} if braco is None else {"p09_braco": braco}
    return AmetekMX30(
        simulated=True, max_voltage_rms=kw.pop("max_voltage_rms", 140.), max_peak_v=kw.pop("max_peak_v", 400.),
        max_current_a=0.5, sim_list_offset_suportado=suportado, **extra, **kw,
    )


def _baseline(fonte):
    fonte.configure_safe_baseline(
        voltage_range_rms=300., voltage_high_vp=fonte.max_peak_v, current_limit_a=0.5,
        protection_delay_s=0.1, frequency_hz=50.,
    )


def _sequencia(fonte):
    _baseline(fonte)
    fonte.authorize_output(True)
    fonte.energize_baseline()
    fonte.program_capture(forma_classe16(), base_voltage_rms=127., frequency_hz=50.)
    fonte.restaurar_forma_e_modo_padrao()
    senoide = np.sin(2 * np.pi * 50 * np.arange(6000) / 30000.) * 0.9 + 0.05
    fonte.program_capture(senoide, base_voltage_rms=127., frequency_hz=50., dc_offset_pu=0.05)
    fonte.restaurar_forma_e_modo_padrao()
    fonte.safe_shutdown()
    return fonte.command_log


def _sem_dados(log):
    return [c for c in log if not c.startswith(("TRACe:DATA", "SOURce:LIST:VOLTage "))]


class BracoAIdenticoTests(unittest.TestCase):
    def test_padrao_e_a_e_sequencia_scpi_igual_a_de_antes(self):
        padrao = _fonte()
        self.assertEqual(padrao.p09_braco, "A")
        log_padrao = _sequencia(padrao)
        log_a = _sequencia(_fonte("a"))
        self.assertEqual(log_padrao, log_a)
        filtrado = _sem_dados(log_a)
        self.assertEqual(len(filtrado), N_SEQUENCIA_A_ANTES)
        self.assertEqual(hashlib.sha256("\n".join(filtrado).encode()).hexdigest(), SHA_SEQUENCIA_A_ANTES)
        self.assertFalse(any("LIST:VOLTage:OFFSet" in c for c in log_a))

    def test_programacao_a_igual_a_b_e_sem_offsets_por_passo(self):
        forma = forma_classe16()
        a = AmetekMX30.montar_programacao(forma, base_voltage_rms=127., frequency_hz=50.)
        b = AmetekMX30.montar_programacao(forma, base_voltage_rms=127., frequency_hz=50., p09_braco="B")
        self.assertIsNone(a.dc_offset_por_passo_pu)
        self.assertEqual(a.p09_braco, "A")
        np.testing.assert_array_equal(a.programada_pu(), b.programada_pu())
        np.testing.assert_array_equal(a.traces, b.traces)
        self.assertEqual(a.pico_reconstruido_v, b.pico_reconstruido_v)
        self.assertEqual(a.passos_offsets_v.size, 0)

    def test_braco_invalido_recusado(self):
        with self.assertRaises(ParameterOutOfBoundsError):
            _fonte("D")
        with self.assertRaises(ParameterOutOfBoundsError):
            AmetekMX30.montar_programacao(np.zeros(6000), base_voltage_rms=127., frequency_hz=50., p09_braco="X")


class BracosBCTests(unittest.TestCase):
    def test_b_envia_acdc_com_saida_off_e_offset_zero(self):
        fonte = _fonte("B")
        log = _sequencia(fonte)
        modo = [i for i, c in enumerate(log) if c == "SOURce:MODE ACDC"]
        self.assertEqual(len(modo), 1, "uma única troca para AC+DC por conexão")
        ligar = log.index("OUTPut:STATe ON")
        self.assertLess(modo[0], ligar, "AC+DC programado antes de energizar")
        self.assertIn("SOURce:VOLTage:OFFSet 0", log[modo[0]:ligar])
        # Nenhuma troca de modo com a saída ligada: só a volta a AC depois do OFF final.
        depois = log[ligar:]
        trocas = [c for c in depois if c.startswith("SOURce:MODE")]
        self.assertEqual(trocas, ["SOURce:MODE AC"])
        ultimo_off = len(depois) - 1 - depois[::-1].index("OUTPut:STATe OFF")
        self.assertLess(ultimo_off, depois.index("SOURce:MODE AC"))
        # B numa fonte sem o comando: só a consulta de suporte, nenhum envio de offsets.
        self.assertFalse(any(c.startswith("SOURce:LIST:VOLTage:OFFSet ") for c in log))
        self.assertLess(log.index("SOURce:LIST:VOLTage:OFFSet?"), ligar)
        # O offset global (classe com dc_offset_pu) continua indo por VOLTage:OFFSet.
        self.assertIn("SOURce:VOLTage:OFFSet 8.9802561", log)

    def test_c_envia_offsets_por_passo_esperados(self):
        fonte = _fonte("C", suportado=True)
        _baseline(fonte)
        fonte.authorize_output(True)
        fonte.energize_baseline()
        forma = forma_classe16()
        fonte.program_capture(forma, base_voltage_rms=127., frequency_hz=50.)
        prog = fonte.ultima_programacao
        self.assertEqual(prog.p09_braco, "C")
        esperado = [np.mean(forma[i * 600:(i + 1) * 600]) * 127. * np.sqrt(2) for i in range(10)]
        np.testing.assert_allclose(prog.passos_offsets_v, esperado, atol=1e-6)
        self.assertGreater(np.max(np.abs(prog.passos_offsets_v)), 10.0)
        comandos = [c for c in fonte.command_log if c.startswith("SOURce:LIST:VOLTage:OFFSet ")]
        # Zeros na preparação da conexão (saída OFF), depois os da captura.
        self.assertEqual(comandos, ["SOURce:LIST:VOLTage:OFFSet 0",
                                    f"SOURce:LIST:VOLTage:OFFSet {prog.texto_list_offsets()}"])
        self.assertEqual(fonte._sim["list_offset"], prog.texto_list_offsets())
        log = fonte.command_log
        self.assertLess(log.index("SOURce:MODE ACDC"), log.index("SOURce:LIST:VOLTage:OFFSet?"))
        self.assertLess(log.index("SOURce:LIST:VOLTage:OFFSet?"), log.index("OUTPut:STATe ON"))
        self.assertEqual([c for c in log if c.startswith("SOURce:MODE")], ["SOURce:MODE AC", "SOURce:MODE ACDC"])

    def test_c_nao_suportado_recusa_antes_de_energizar_sem_fallback(self):
        fonte = _fonte("C", suportado=False)
        with self.assertRaises(OffsetPorPassoNaoSuportadoError) as ctx:
            _baseline(fonte)
        self.assertIn("Sem fallback", str(ctx.exception))
        self.assertFalse(fonte.p09_suporte_list_offset["suportado"])
        self.assertEqual(fonte.p09_braco, "C")
        self.assertNotIn("OUTPut:STATe ON", fonte.command_log)
        self.assertFalse(fonte._sim["output"])
        fonte.authorize_output(True)
        with self.assertRaises(BracoP09Error):
            fonte.energize_baseline()
        with self.assertRaises(BracoP09Error):
            fonte.program_capture(forma_classe16(), base_voltage_rms=127., frequency_hz=50.)
        self.assertNotIn("OUTPut:STATe ON", fonte.command_log)
        self.assertFalse(any(c.startswith("TRACe:") for c in fonte.command_log))

    def _c_programado(self):
        fonte = _fonte("C", suportado=True)
        _baseline(fonte)
        fonte.authorize_output(True)
        fonte.energize_baseline()
        fonte.program_capture(forma_classe16(), base_voltage_rms=127., frequency_hz=50.)
        self.assertTrue(any(float(v) != 0.0 for v in fonte._sim["list_offset"].split(",")))
        return fonte

    @staticmethod
    def _offsets_lista(fonte):
        return [float(v) for v in fonte._sim["list_offset"].split(",")]

    def test_c_seguido_da_classe_18_nao_deixa_offset(self):
        fonte = self._c_programado()
        fonte.restaurar_forma_e_modo_padrao()  # fim da classe C
        self.assertTrue(all(v == 0.0 for v in self._offsets_lista(fonte)))
        fonte._sim["list_offset"] = "7,7"  # mesmo que algo tenha sobrado
        fonte.frequency_drift_list(50., 51., voltage_rms=127., dwell_s=0.1)
        self.assertEqual(self._offsets_lista(fonte), [0.0, 0.0])

    def test_run_b_zera_offsets_velhos(self):
        fonte = _fonte("B", suportado=True)
        fonte._sim["list_offset"] = "51.75,-19.4"  # sobra de um run C anterior
        _baseline(fonte)
        self.assertTrue(all(v == 0.0 for v in self._offsets_lista(fonte)))
        fonte.authorize_output(True)
        fonte.energize_baseline()
        fonte._sim["list_offset"] = "3"
        fonte.program_capture(forma_classe16(), base_voltage_rms=127., frequency_hz=50.)
        self.assertEqual(self._offsets_lista(fonte), [0.0] * 10)

    def test_shutdown_zera_offsets_antes_de_voltar_a_ac(self):
        fonte = self._c_programado()
        fonte.safe_shutdown()
        self.assertTrue(all(v == 0.0 for v in self._offsets_lista(fonte)))
        log = fonte.command_log
        ultimo_off = len(log) - 1 - log[::-1].index("OUTPut:STATe OFF")
        zeros = max(i for i, c in enumerate(log) if c.startswith("SOURce:LIST:VOLTage:OFFSet 0"))
        self.assertLess(ultimo_off, zeros)
        self.assertLess(zeros, log.index("SOURce:MODE AC", ultimo_off))

    def test_falha_ao_zerar_em_c_e_fatal_inclusive_na_recuperacao(self):
        fonte = self._c_programado()
        fonte._sim["list_offset_suportado"] = False  # a fonte passa a rejeitar
        with self.assertRaises(BracoP09Error):
            fonte.restaurar_forma_e_modo_padrao()
        config = mestre.Config(
            fs_hz=30000., points=6000, duration_s=.2, grid_frequency_hz=50., base_voltage_rms=127.,
            snr_levels_db=(), base_seed=1, capture_current=False, current_base_a=None,
            results_dir=Path("."), sim_captures_per_class=1, real_captures_per_class=1,
            disturbance_start_s=.06,
        )
        bancada = mestre.Bancada(fonte, mock.Mock(), config)
        with self.assertRaises(mestre.FalhaFatalDeInstrumento):
            bancada.recuperar_estado_seguro()

    def test_consulta_restaura_modo_se_falhar_no_meio(self):
        fonte = _fonte("C", suportado=True)
        with mock.patch.object(fonte, "check_errors", side_effect=[[], ametek_orm.CommunicationError("caiu"), []]):
            with self.assertRaises(ametek_orm.CommunicationError):
                fonte.consultar_suporte_offset_lista(modo_restaurar="AC")
        self.assertEqual(fonte.command_log[-2:], ["SOURce:MODE AC", "*WAI"])
        self.assertEqual(fonte._sim["source_mode"], "AC")
        self.assertFalse(fonte._sim["output"])
        self.assertNotIn("OUTPut:STATe ON", fonte.command_log)

    def test_bancada_simulada_herda_braco(self):
        with mock.patch.object(mestre, "P09_BRACO", "C"), mock.patch.object(mestre, "SIMULATED_MODE", True):
            bancada = mestre.Bancada._from_env_sem_bloqueio(require_output=False)
        self.assertEqual(bancada.fonte.p09_braco, "C")
        self.assertEqual(bancada.fonte.command_log, [])

    def test_b_c_sem_preparo_recusam_programacao_sem_io(self):
        for braco in ("B", "C"):
            fonte = _fonte(braco, suportado=True)
            with self.assertRaises(BracoP09Error):
                fonte.program_capture(forma_classe16(), base_voltage_rms=127., frequency_hz=50.)
            self.assertEqual(fonte.command_log, [])

    def test_consulta_recusada_com_saida_ligada(self):
        fonte = _fonte("C", suportado=True)
        fonte._sim["output"] = True
        with self.assertRaises(BracoP09Error):
            fonte.consultar_suporte_offset_lista(modo_restaurar="AC")
        self.assertEqual(fonte.command_log, [])

    def test_cache_nao_reaproveita_entre_bracos(self):
        forma = forma_classe16()
        assinaturas = {}
        for braco in ("A", "B", "C"):
            fonte = _fonte(braco, suportado=True)
            _baseline(fonte)
            fonte.program_capture(forma, base_voltage_rms=127., frequency_hz=50.)
            assinaturas[braco] = fonte._last_capture_signature
        self.assertEqual(len(set(assinaturas.values())), 3)
        self.assertEqual(len(assinaturas["A"]), 5, "assinatura do braço A inalterada")


class SegurancaTests(unittest.TestCase):
    def test_pico_de_c_e_com_sinal_classe_16(self):
        forma = forma_classe16()
        prog = AmetekMX30.montar_programacao(forma, base_voltage_rms=127., frequency_hz=50., p09_braco="C")
        modelo_v = np.max(np.abs(forma)) * 127. * np.sqrt(2)
        self.assertAlmostEqual(prog.pico_reconstruido_v, 179.6, delta=0.1)
        self.assertAlmostEqual(prog.pico_reconstruido_v, modelo_v, delta=0.5)
        np.testing.assert_allclose(prog.pico_reconstruido_v,
                                   np.max(np.abs(prog.programada_pu())) * 127. * np.sqrt(2), rtol=2e-3)

    def test_pico_com_offset_acima_do_teto_recusado_antes_de_io(self):
        # Ciclo 0: CA de pico +0,8 pu com offset +0,8 pu do mesmo sinal -> 1,6 pu.
        t = np.arange(6000) / 30000.
        forma = np.sin(2 * np.pi * 50 * t) * 0.8
        forma[:600] += 0.8
        base = 127.
        a = AmetekMX30.montar_programacao(forma, base_voltage_rms=base, frequency_hz=50.)
        c = AmetekMX30.montar_programacao(forma, base_voltage_rms=base, frequency_hz=50., p09_braco="C")
        self.assertAlmostEqual(c.pico_reconstruido_v, 1.6 * base * np.sqrt(2), delta=1.0)
        teto = 250.
        self.assertLess(a.pico_reconstruido_v, teto)
        self.assertGreater(c.pico_reconstruido_v, teto)
        fonte = _fonte("C", suportado=True, max_peak_v=teto, max_voltage_rms=200.)
        fonte.configure_safe_baseline(
            voltage_range_rms=300., voltage_high_vp=teto, current_limit_a=0.5,
            protection_delay_s=0.1, frequency_hz=50.,
        )
        antes = list(fonte.command_log)
        with mock.patch.object(fonte, "write", wraps=fonte.write) as write, \
                mock.patch.object(fonte, "query", wraps=fonte.query) as query:
            with self.assertRaises(ParameterOutOfBoundsError):
                fonte.program_capture(forma, base_voltage_rms=base, frequency_hz=50.)
            write.assert_not_called()
            query.assert_not_called()
        self.assertEqual(fonte.command_log, antes)

    def test_rms_total_e_offset_maximo_recusados_antes_de_io(self):
        t = np.arange(6000) / 30000.
        forma = np.sin(2 * np.pi * 50 * t) * 0.1 + 0.95
        fonte = _fonte("C", suportado=True, max_voltage_rms=140., max_peak_v=400.)
        _baseline(fonte)
        antes = list(fonte.command_log)
        with self.assertRaises(ParameterOutOfBoundsError):
            fonte.program_capture(forma, base_voltage_rms=127., frequency_hz=50.)
        self.assertEqual(fonte.command_log, antes)
        self.assertEqual(AmetekMX30.MAX_DC_OFFSET_V, 220.0)


class MetricasEGanhoTests(unittest.TestCase):
    def test_ganho_de_c_na_classe_16(self):
        forma = forma_classe16()
        erros = {}
        for braco in ("A", "C"):
            prog = AmetekMX30.montar_programacao(forma, base_voltage_rms=127., frequency_hz=50., p09_braco=braco)
            erros[braco] = mestre.distancia_modelo_programada(forma, prog.programada_pu(), pontos_por_ciclo=600)
        self.assertGreater(erros["A"]["erro_rms_pu"], 0.05)
        self.assertLess(erros["C"]["erro_rms_pu"], 0.01)
        self.assertGreater(erros["A"]["media_perdida_maxima_absoluta_pu"], 0.2)
        self.assertLess(erros["C"]["media_perdida_maxima_absoluta_pu"], 1e-3)

    def test_prever_forma_ideal_usa_offset_por_passo(self):
        import modelo_lista_fonte
        forma = forma_classe16()
        prog = AmetekMX30.montar_programacao(forma, base_voltage_rms=127., frequency_hz=50., p09_braco="C")
        np.testing.assert_allclose(modelo_lista_fonte.prever_forma(prog), prog.programada_pu(), atol=1e-9)

    def _rodar_classe16_simulada(self, braco, pasta):
        config = mestre.Config(
            fs_hz=30000., points=6000, duration_s=.2, grid_frequency_hz=50., base_voltage_rms=127.,
            snr_levels_db=(), base_seed=2, capture_current=False, current_base_a=None,
            results_dir=pasta, sim_captures_per_class=1, real_captures_per_class=1,
            disturbance_start_s=.06, sorteio_posicao=True, perfil="fronteira",
        )
        fonte = AmetekMX30(simulated=True, p09_braco=braco)
        tipo = mestre.Bancada._carregar_classe_experimento(RAIZ / "experimentos_waveform" / "16.py")
        with mock.patch("sys.stdout", new=io.StringIO()):
            tipo(mestre.Bancada(fonte, None, config)).executar()
        (arquivo,) = (pasta / "metadata").glob("16_*.jsonl")
        (registro,) = [json.loads(linha) for linha in arquivo.read_text(encoding="utf-8").splitlines()]
        return registro, fonte

    def test_metricas_no_metadata(self):
        registros = {}
        with tempfile.TemporaryDirectory() as tmp:
            for braco in ("A", "C"):
                registro, fonte = self._rodar_classe16_simulada(braco, Path(tmp) / braco)
                self.assertEqual(fonte.command_log, [], "simulado não toca a fonte")
                registros[braco] = registro
        for braco, registro in registros.items():
            self.assertEqual(registro["p09_braco"], braco)
            for campo in ("media_perdida_maxima_absoluta_pu", "erro_rms_modelo_programada_pu",
                          "salto_pico_modelo_programada_v"):
                self.assertIsInstance(registro[campo], float)
        # Captura simulada de seed 16000002 (média perdida de A ~0,03 pu): C cai ~5x.
        self.assertLess(registros["C"]["erro_rms_modelo_programada_pu"],
                        registros["A"]["erro_rms_modelo_programada_pu"] / 3)
        self.assertLess(registros["C"]["media_perdida_maxima_absoluta_pu"],
                        registros["A"]["media_perdida_maxima_absoluta_pu"] / 10)


class ConfiguracaoCliEDiagTests(unittest.TestCase):
    def test_cli_set_p09_e_status(self):
        import cli
        with mock.patch.object(mestre, "P09_BRACO", "A"):
            sessao = cli.SessaoCLI()
            with mock.patch("builtins.print"):
                self.assertEqual(sessao.cmd_set(["p09", "c"]), 0)
                self.assertEqual(mestre.P09_BRACO, "C")
                self.assertEqual(sessao.cmd_set(["p09", "D"]), 1)
                self.assertEqual(mestre.P09_BRACO, "C")
            saida = io.StringIO()
            with mock.patch("sys.stdout", new=saida):
                sessao.cmd_status([])
            self.assertIn("p09: C", saida.getvalue())
        self.assertIn("set p09 A|B|C", cli.HELP_TEXT)

    def test_variavel_documentada(self):
        self.assertIn("AMETEK_P09_BRACO", (RAIZ / "docs" / "configuracao.md").read_text(encoding="utf-8"))
        self.assertIn("AMETEK_P09_BRACO", (RAIZ / ".env.example").read_text(encoding="utf-8"))

    def test_diag_list_offset_simulado_so_consulta(self):
        sys.path.insert(0, str(RAIZ / "scripts"))
        try:
            import diag_list_offset
        finally:
            sys.path.remove(str(RAIZ / "scripts"))
        for suportado in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                argv = ["--simulado", "--saida", tmp] + (["--sim-suportado"] if suportado else [])
                with mock.patch("sys.stdout", new=io.StringIO()):
                    self.assertEqual(diag_list_offset.main(argv), 0)
                (arquivo,) = Path(tmp).glob("diag_list_offset-*.json")
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
            self.assertIs(dados["resultado"]["suportado"], suportado)
            self.assertFalse(dados["energizou"])
            self.assertIn("git_commit", dados)
            self.assertIn("git_sujo", dados)
            comandos = dados["comandos_scpi"]
            self.assertNotIn("OUTPut:STATe ON", comandos)
            self.assertLess(comandos.index("SOURce:MODE ACDC"), comandos.index("SOURce:LIST:VOLTage:OFFSet?"))
            self.assertIn("SOURce:MODE AC", comandos[comandos.index("SOURce:LIST:VOLTage:OFFSet?"):])
            self.assertEqual(dados["resultado"]["modo_restaurado"], "AC")


if __name__ == "__main__":
    unittest.main()
