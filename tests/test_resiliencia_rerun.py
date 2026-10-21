"""Capacidades da fonte antes de I/O, pula-e-segue, falhas.json e rerun (v1.15).

Tudo offline: fonte AMETEK simulada, osciloscópio ``mock.Mock``. Nenhum
teste energiza nada nem digita confirmação de energização.
"""
import contextlib
import io
import json
import logging
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

LOGICA_DIR = Path(__file__).resolve().parents[1] / "logica"
if str(LOGICA_DIR) not in sys.path:
    sys.path.insert(0, str(LOGICA_DIR))

import cli  # noqa: E402
import mestre  # noqa: E402
from ametek_orm import (  # noqa: E402
    CAPACIDADES_MX30, AmetekMX30, CapacidadeExcedidaError, InstrumentHardwareError,
    ParameterOutOfBoundsError,
)
from politica_traces import LimiteEscritasTraceError  # noqa: E402

PONTOS = 6000
FS = 30_000.0
T = np.arange(PONTOS, dtype=np.float64) / FS


def _config(results_dir, **extra):
    base = dict(
        fs_hz=FS, points=PONTOS, duration_s=0.2, grid_frequency_hz=60.0,
        base_voltage_rms=127.0, snr_levels_db=(), base_seed=20_260_827,
        capture_current=False, current_base_a=None, results_dir=Path(results_dir),
        sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
        sorteio_posicao=False, perfil="literatura",
    )
    base.update(extra)
    return mestre.Config(**base)


def _fonte():
    return AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=415.8)


def _osc_mock():
    osc = mock.Mock()
    osc.get_waveform.side_effect = lambda canal, **kw: (
        T, np.sin(2 * np.pi * 60.0 * T) * 127.0 * np.sqrt(2.0),
    )
    return osc


@contextlib.contextmanager
def _caminho_de_bancada_sem_hardware():
    """Corta só o que depende de um osciloscópio real (margem, extremos
    medidos, validação física): o resto do caminho de bancada roda inteiro."""
    with mock.patch.object(mestre.ExperimentoBase, "_calcular_margem",
                           staticmethod(lambda **kw: (0, 0, kw["config_points"]))), \
            mock.patch.object(mestre.ExperimentoBase, "_medir_extremos_fisicos", lambda self: {}), \
            mock.patch.object(mestre.ExperimentoBase, "_conferir_extremos_fisicos", lambda self, i, e: None), \
            mock.patch.object(mestre.ExperimentoBase, "_validar_fisicamente", lambda self, *a, **k: None), \
            mock.patch.object(mestre, "BENCH_MODE", False), \
            mock.patch.object(mestre, "PERFIL_TODOS", False):
        yield


def _classe_nativa(id_, larguras=None, falha_na=None, invalida_na=None):
    """Classe nativa de teste: ``larguras[capture_index]`` = largura de PULSe
    exigida; ``falha_na`` = chamadas de ``_capturar_real`` que levantam."""
    larguras = larguras or {}
    chamadas = {"n": 0}

    class _Classe(mestre.ExperimentoNativo):
        nome = f"TESTE_{id_}"
        capturas_padrao = 3

        def gerar(self, t, f0, capture_index, rng):
            return np.sin(2.0 * np.pi * f0 * t), {}

        def configurar(self, capture_index):
            return {}

        def exigencias_nativas(self, capture_index, parametros):
            return {"pulse_width_s": larguras.get(capture_index, 0.06)}

        def _capturar_real(self, capture_index, t, rng):
            chamadas["n"] += 1
            if falha_na and chamadas["n"] in falha_na:
                raise falha_na[chamadas["n"]]
            return T, np.sin(2.0 * np.pi * 60.0 * T), None, {}

        def _validar_fisicamente(self, capture_index, *a, **k):
            if invalida_na is not None and capture_index == invalida_na:
                return {"ok": False, "motivos": ["envelope fora"]}
            return None

    _Classe.id = id_
    _Classe.chamadas = chamadas
    return _Classe


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)

    def bateria(self, classes, config, fonte=None, perfis=("literatura",), selecao=None):
        bancada = mestre.Bancada(fonte or _fonte(), _osc_mock(), config)
        mapa = {cls.id: cls for cls in classes}
        with _caminho_de_bancada_sem_hardware(), \
                mock.patch.object(mestre.Bancada, "_carregar_classe_experimento",
                                  staticmethod(lambda p: mapa[Path(p).stem])), \
                mock.patch.object(mestre.Bancada, "recuperar_estado_seguro", lambda self: None):
            resultados = bancada.executar_bateria(
                [Path(f"{cls.id}.py") for cls in classes], perfis, selecao=selecao,
            )
        bancada.shutdown()
        return bancada, resultados


class CapacidadesTests(_Base):
    def test_tabela_documenta_fonte_de_cada_capacidade(self):
        for nome in ("passos_list", "traces_por_grupo", "dwell_s", "pulse_width_s", "dc_offset_v", "frequencia_hz"):
            with self.subTest(nome=nome):
                self.assertIn(nome, CAPACIDADES_MX30)
                self.assertTrue(CAPACIDADES_MX30[nome].fonte)
        self.assertEqual(CAPACIDADES_MX30["passos_list"].maximo, 32)
        self.assertEqual(CAPACIDADES_MX30["traces_por_grupo"].maximo, 50)
        self.assertEqual(CAPACIDADES_MX30["dc_offset_v"].maximo, AmetekMX30.MAX_DC_OFFSET_V)

    def test_list_acima_de_32_passos_recusada_antes_de_io(self):
        fonte = AmetekMX30(simulated=True, max_voltage_rms=10, max_peak_v=100)
        forma = np.sin(2 * np.pi * 200 * T)  # 200 Hz: 40 ciclos -> 40 passos de LIST
        with mock.patch.object(fonte, "write") as write, mock.patch.object(fonte, "query") as query, \
                mock.patch.object(fonte, "_ensure_trace_slots") as slots:
            with self.assertRaises(CapacidadeExcedidaError) as ctx:
                fonte.program_capture(forma, base_voltage_rms=5, frequency_hz=200)
        self.assertIn("passos_list", str(ctx.exception))
        self.assertIn("32", str(ctx.exception))
        for chamada in (write, query, slots):
            chamada.assert_not_called()
        self.assertEqual(fonte.escritas_trace, 0)
        self.assertIsNone(fonte.ultima_programacao)
        self.assertIsInstance(ctx.exception, ParameterOutOfBoundsError)

    def test_nativos_recusam_acima_da_capacidade_antes_de_io(self):
        fonte = AmetekMX30(simulated=True, max_voltage_rms=300, max_peak_v=415)
        casos = (
            lambda: fonte.trigger_pulse(100.0, width_s=0.0005),
            lambda: fonte.trigger_pulse(100.0, width_s=90_001.0),
            lambda: fonte.frequency_drift_list(57, 63, voltage_rms=100, dwell_s=9.1e4),
            lambda: fonte.enable_dc_offset(221.0, ac_peak_v=10.0),
        )
        for indice, caso in enumerate(casos):
            with self.subTest(caso=indice), mock.patch.object(fonte, "write") as write, \
                    mock.patch.object(fonte, "query") as query:
                with self.assertRaises(CapacidadeExcedidaError):
                    caso()
                write.assert_not_called()
                query.assert_not_called()

    def test_grupo_de_traces_acima_de_50_recusado_antes_de_definir(self):
        fonte = AmetekMX30(simulated=True, max_voltage_rms=10, max_peak_v=100)
        # Só os slots do projeto (TCC*) contam: 45 deles + 12 novos > 50.
        fonte._sim["trace_names"].update(f"TCC{i:02d}" for i in range(20, 65))
        with mock.patch.object(fonte, "write") as write:
            with self.assertRaises(CapacidadeExcedidaError):
                fonte._ensure_trace_slots(tuple(f"TCC{i:02d}" for i in range(12)))
        write.assert_not_called()
        # Formas que não são TCC* (de fábrica ou de outro uso) não entram na conta.
        outra = AmetekMX30(simulated=True, max_voltage_rms=10, max_peak_v=100)
        outra._sim["trace_names"].update(f"OUTRA{i:02d}" for i in range(45))
        outra._ensure_trace_slots(tuple(f"TCC{i:02d}" for i in range(12)))

    def test_captura_acima_da_capacidade_e_pulada_e_a_bateria_segue(self):
        config = _config(self.tmp)
        excede = _classe_nativa("91", larguras={0: 1.0e5})
        segue = _classe_nativa("92")
        _, resultados = self.bateria([excede, segue], config)
        self.assertEqual([r.ok for r in resultados], [True, True])
        self.assertEqual(resultados[0].puladas, 1)
        self.assertEqual(excede.chamadas["n"], 2)
        self.assertEqual(segue.chamadas["n"], 3)
        itens = mestre.ler_falhas(self.tmp)["itens"]
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]["tipo"], "pulada_capacidade")
        self.assertEqual(itens[0]["id_captura"], "91-0001")
        self.assertIn("pulse_width_s", itens[0]["motivo"])
        self.assertIn("90000", itens[0]["motivo"])

    def test_classe_waveform_acima_de_32_passos_pulada_no_preflight(self):
        class _Wave(mestre.ExperimentoWaveform):
            id = "93"
            nome = "TESTE_WAVE"

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

        config = _config(self.tmp, grid_frequency_hz=200.0, base_voltage_rms=5.0)
        experimento = _Wave(mestre.Bancada(AmetekMX30(simulated=True, max_voltage_rms=10, max_peak_v=100),
                                           None, config))
        info = experimento.avaliar_captura_na_bancada(0, 0)
        self.assertFalse(info["cabe"])
        self.assertEqual(info["tipo_recusa"], "pulada_capacidade")
        self.assertIn("passos_list", info["motivo"])


class PulaESegueTests(_Base):
    def test_descartada_invalida_e_classe_que_falha_nao_impedem_as_seguintes(self):
        config = _config(self.tmp)
        descarta = _classe_nativa("91", falha_na={2: InstrumentHardwareError("erro 19 simulado")}, invalida_na=2)
        quebra = _classe_nativa("92", falha_na={n: RuntimeError("bug") for n in range(1, 20)})
        segue = _classe_nativa("94")
        _, resultados = self.bateria([descarta, quebra, segue], config)
        self.assertEqual([r.ok for r in resultados], [True, False, True])
        self.assertEqual((resultados[0].descartadas, resultados[0].invalidas), (1, 1))
        self.assertEqual(segue.chamadas["n"], 3)
        itens = mestre.ler_falhas(self.tmp)["itens"]
        tipos = [(i["tipo"], i["classe"], i["id_captura"]) for i in itens]
        self.assertIn(("descartada", "91", "91-0002"), tipos)
        self.assertIn(("invalida", "91", "91-0003"), tipos)
        self.assertIn(("classe_falhou", "92", None), tipos)

    def test_falhas_json_tem_campos_e_contexto_para_reproduzir(self):
        config = _config(self.tmp, capturas_override=3)
        descarta = _classe_nativa("91", falha_na={2: InstrumentHardwareError("erro 19 simulado")})
        self.bateria([descarta], config)
        documento = json.loads((self.tmp / "falhas.json").read_text(encoding="utf-8"))
        self.assertFalse((self.tmp / "falhas.json.part").exists())
        self.assertEqual(documento["formato_falhas"], 1)
        (item,) = documento["itens"]
        for campo in mestre.CAMPOS_FALHA:
            self.assertIn(campo, item)
        self.assertEqual(item["tipo"], "descartada")
        self.assertEqual(item["indice_global"], 1)
        self.assertEqual(item["capture_index"], 1)
        self.assertEqual(item["nivel_indice"], 1)
        self.assertEqual(item["perfil"], "literatura")
        self.assertEqual(item["seed"], 20_260_827 + 91 * 1_000_000 + 1)
        self.assertIn("erro 19", item["motivo"])
        contexto = item["contexto"]
        self.assertEqual(contexto["base_seed"], 20_260_827)
        self.assertEqual(contexto["capturas_override"], 3)
        self.assertEqual(contexto["perfis_da_rodada"], ["literatura"])
        self.assertEqual((contexto["tensao_base_rms"], contexto["frequencia_hz"]), (127.0, 60.0))
        self.assertEqual(contexto["p09_braco"], "A")
        self.assertFalse(contexto["sorteio_posicao"])
        self.assertEqual(contexto["calibracao_extremos_sha256"],
                         mestre.sha256_do_arquivo(mestre.CALIBRACAO_EXTREMOS_PATH))

    def test_orcamento_esgotado_desliga_registra_restantes_e_nao_reconecta(self):
        config = _config(self.tmp)
        esgota = _classe_nativa("91", falha_na={2: LimiteEscritasTraceError("orçamento esgotado")})
        nunca = _classe_nativa("92")
        fonte = _fonte()
        fonte.authorize_output(True)
        fonte._sim["output"] = True
        with mock.patch.object(AmetekMX30, "connect") as connect, \
                mock.patch.object(mestre.Bancada, "from_env") as from_env, \
                mock.patch.object(fonte, "safe_shutdown", wraps=fonte.safe_shutdown) as shutdown:
            _, resultados = self.bateria([esgota, nunca], config, fonte=fonte)
        connect.assert_not_called()
        from_env.assert_not_called()
        self.assertGreaterEqual(shutdown.call_count, 1)
        self.assertFalse(fonte._sim["output"])
        self.assertFalse(fonte.output_authorized)
        self.assertEqual(nunca.chamadas["n"], 0)
        self.assertEqual(esgota.chamadas["n"], 2, "sem retry na mesma conexão")
        self.assertEqual([r.nao_executada_orcamento for r in resultados], [True, True])
        itens = mestre.ler_falhas(self.tmp)["itens"]
        orcamento = [(i["classe"], i["id_captura"]) for i in itens if i["tipo"] == "nao_executada_orcamento"]
        self.assertEqual(orcamento, [("91", "91-0002"), ("91", "91-0003"), ("92", None)])

    def test_orcamento_sem_off_confirmado_aborta_como_falha_fatal(self):
        config = _config(self.tmp)
        esgota = _classe_nativa("91", falha_na={1: LimiteEscritasTraceError("orçamento esgotado")})
        fonte = _fonte()
        with mock.patch.object(fonte, "safe_shutdown", return_value=False), \
                self.assertRaises(mestre.FalhaFatalDeInstrumento):
            self.bateria([esgota], config, fonte=fonte)

    def test_falha_ao_registrar_nao_vira_aborto_mas_infraestrutura_propaga(self):
        config = _config(self.tmp)
        descarta = _classe_nativa("91", falha_na={1: InstrumentHardwareError("x")})
        quebra = _classe_nativa("92", falha_na={n: RuntimeError("bug") for n in range(1, 20)})
        segue = _classe_nativa("94")
        with mock.patch.object(mestre.RegistroFalhas, "registrar", side_effect=RuntimeError("disco")):
            _, resultados = self.bateria([descarta, quebra, segue], config)
        self.assertEqual([r.ok for r in resultados], [True, False, True])
        self.assertEqual(segue.chamadas["n"], 3)
        with mock.patch.object(mestre.RegistroFalhas, "registrar",
                               side_effect=mestre.FalhaFatalDeInstrumento("fatal")), \
                self.assertRaises(mestre.FalhaFatalDeInstrumento):
            self.bateria([_classe_nativa("95", falha_na={1: InstrumentHardwareError("x")})], _config(self.tmp / "b"))

    def test_falha_de_comunicacao_continua_abortando(self):
        config = _config(self.tmp)
        cai = _classe_nativa("91", falha_na={1: mestre.CommunicationError("serial caiu")})
        nunca = _classe_nativa("92")
        with self.assertRaises(mestre.CommunicationError):
            self.bateria([cai, nunca], config)
        self.assertEqual(nunca.chamadas["n"], 0)


class RerunTests(_Base):
    def _executar_10(self, config, *, falhar_chamada=None, selecao=None):
        """Classe 10 REAL no caminho de bancada, com a fonte simulada fazendo o
        program_capture de verdade; grava a programação de cada chamada."""
        cls = mestre.Bancada._carregar_classe_experimento(
            Path(mestre.PROJECT_ROOT) / "experimentos_waveform" / "10.py")
        fonte = _fonte()
        programadas = []
        original = fonte.program_capture

        def program_capture(forma, **kw):
            original(forma, **kw)
            p = fonte.ultima_programacao
            programadas.append(p.traces.tobytes() + p.list_voltages_rms.tobytes() + np.asarray(forma).tobytes())
            if falhar_chamada is not None and len(programadas) == falhar_chamada:
                raise InstrumentHardwareError("falha simulada depois de programar")

        fonte.program_capture = program_capture
        # Armar/disparar dependem do instrumento real; o que se compara é a
        # programação (TRACe/LIST) que program_capture monta e envia.
        for nome in ("arm_transient", "trigger", "wait_transient_complete"):
            setattr(fonte, nome, lambda *a, **k: None)
        bancada = mestre.Bancada(fonte, _osc_mock(), config)
        with _caminho_de_bancada_sem_hardware(), \
                mock.patch.object(mestre.Bancada, "_carregar_classe_experimento", staticmethod(lambda p: cls)), \
                mock.patch.object(mestre.Bancada, "recuperar_estado_seguro", lambda self: None):
            resultados = bancada.executar_bateria([Path("10.py")], ("literatura",), selecao=selecao)
        bancada.shutdown()
        return resultados, programadas

    def test_rerun_reproduz_seed_e_forma_programada_byte_a_byte(self):
        origem = self.tmp / "origem"
        resultados, programadas = self._executar_10(_config(origem, sorteio_posicao=True), falhar_chamada=2)
        self.assertEqual(resultados[0].descartadas, 1)
        contexto, selecao, itens, puladas = mestre.selecionar_para_rerun(origem)
        self.assertEqual(puladas, [])
        self.assertEqual(selecao, {"10": {"literatura": (1,)}})
        self.assertEqual(itens[0]["id_captura"], "10-0002")
        novo = self.tmp / "rerun"
        config = _config(novo, sorteio_posicao=contexto["sorteio_posicao"], base_seed=contexto["base_seed"],
                         capturas_override=contexto["capturas_override"], rerun_de={"sessao": str(origem)})
        _, reprogramadas = self._executar_10(config, selecao=selecao)
        self.assertEqual(len(reprogramadas), 1)
        self.assertEqual(reprogramadas[0], programadas[1], "programação/forma idêntica byte a byte")
        registro = json.loads((novo / "metadata" / "10_sag_harmonics.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(registro["id_captura"], "10-0002")
        self.assertEqual(registro["seed"], itens[0]["seed"])
        self.assertEqual(registro["rerun_de"]["sessao"], str(origem))

    def test_caminho_normal_sem_filtro_mantem_plano(self):
        cls = mestre.Bancada._carregar_classe_experimento(
            Path(mestre.PROJECT_ROOT) / "experimentos_waveform" / "10.py")
        config = _config(self.tmp)
        plano = cls(mestre.Bancada(None, None, config)).plano_de_capturas(False)
        self.assertEqual(plano, [(0, 0), (1, 1), (2, 2)])
        filtrado = cls(mestre.Bancada(None, None, mestre.replace(config, indices_permitidos=(2,)))).plano_de_capturas(False)
        self.assertEqual(filtrado, [(2, 2)])
        self.assertIsNone(config.indices_permitidos)

    def _sessao_de_origem(self, puladas=(), **contexto_extra):
        origem = self.tmp / "sessao_origem"
        origem.mkdir()
        contexto = {
            **mestre.condicao_atual(),
            "base_seed": 7, "capturas_override": None, "perfil": "literatura", "perfis_da_rodada": ["literatura"],
            "tensao_base_rms": 127.0, "frequencia_hz": 60.0, "p09_braco": "A", "sorteio_posicao": True,
        }
        contexto.update(contexto_extra)
        registro = mestre.RegistroFalhas(origem, contexto)
        registro.registrar("descartada", classe="10", perfil="literatura", indice_global=1, capture_index=1,
                           nivel_indice=1, seed=7 + 10_000_000 + 1, id_captura="10-0002", motivo="x")
        for indice in puladas:
            registro.registrar("pulada_capacidade", classe="10", perfil="literatura", indice_global=indice,
                               capture_index=indice, nivel_indice=indice, seed=7 + 10_000_000 + indice,
                               id_captura=f"10-{indice + 1:04d}", motivo="capacidade")
        return origem

    def _rerun_recusado(self, args, *trechos):
        sessao = cli.SessaoCLI()
        with mock.patch.object(mestre, "BASE_VOLTAGE_RMS", 127.0), mock.patch.object(mestre, "GRID_FREQUENCY_HZ", 60.0), \
                mock.patch.object(mestre, "P09_BRACO", "A"), \
                mock.patch.object(sessao, "confirmar") as confirmar, \
                mock.patch.object(sessao, "_garantir_pasta_sessao") as pasta, \
                mock.patch.object(sessao, "autorizar_saida") as autorizar, \
                mock.patch.object(mestre.Bancada, "from_env") as from_env, \
                contextlib.redirect_stdout(io.StringIO()) as saida:
            self.assertEqual(sessao.cmd_rerun(args), 1)
        texto = saida.getvalue()
        self.assertIn("Rerun recusado", texto)
        self.assertIn("Nada foi energizado", texto)
        for trecho in trechos:
            self.assertIn(trecho, texto)
        for alvo in (confirmar, pasta, autorizar, from_env):
            alvo.assert_not_called()
        return texto

    def test_rerun_recusado_se_a_calibracao_mudou_e_diz_como_restaurar(self):
        origem = self._sessao_de_origem(calibracao_extremos_sha256="0" * 64)
        self._rerun_recusado([str(origem), "10-0002"], "calibração de extremos mudou",
                             str(origem / "calibracao_extremos.json"))

    def test_rerun_recusado_se_passo_final_sin_ou_limites_diferem(self):
        for chave, valor, trecho in (("passo_final_sin", True, "AMETEK_PASSO_FINAL_SIN=1"),
                                     ("max_peak_v", 300.0, "EUT_MAX_PEAK_V=300.0"),
                                     ("max_voltage_rms", 99.0, "EUT_MAX_VOLTAGE_RMS=99.0"),
                                     ("source_voltage_range_rms", 300.0, "SOURCE_VOLTAGE_RANGE_RMS=300.0")):
            with self.subTest(chave=chave):
                origem = self._sessao_de_origem(**{chave: valor})
                self._rerun_recusado([str(origem), "10-0002"], chave, trecho)
                shutil.rmtree(origem)

    def test_contexto_registra_passo_final_sin_limites_e_calibracao(self):
        config = _config(self.tmp)
        descarta = _classe_nativa("91", falha_na={1: InstrumentHardwareError("x")})
        self.bateria([descarta], config)
        contexto = mestre.ler_falhas(self.tmp)["itens"][0]["contexto"]
        for chave in mestre.CHAVES_CONDICAO_RERUN:
            self.assertIn(chave, contexto)
            self.assertIsNotNone(contexto[chave])
        self.assertEqual(mestre.comparar_condicao_para_rerun(
            {**contexto, "tensao_base_rms": mestre.BASE_VOLTAGE_RMS, "frequencia_hz": mestre.GRID_FREQUENCY_HZ},
            mestre.condicao_atual()), [])

    def test_so_puladas_recusa_e_mistura_retira_as_puladas(self):
        origem = self._sessao_de_origem(puladas=(2,))
        self._rerun_recusado([str(origem), "10-0003"], "só capturas puladas", "pularia de novo")
        contexto, selecao, itens, puladas = mestre.selecionar_para_rerun(origem, ["10"])
        self.assertEqual(selecao, {"10": {"literatura": (1,)}})
        self.assertEqual([i["id_captura"] for i in puladas], ["10-0003"])

    def test_falhas_json_corrompido_recusa_sem_energizar(self):
        origem = self._sessao_de_origem()
        (origem / "falhas.json").write_text("{ isto não é json", encoding="utf-8")
        self._rerun_recusado([str(origem), "10-0002"], "falhas.json", "corrompido")
        with self.assertRaises(mestre.RerunRecusadoError):
            mestre.selecionar_para_rerun(origem)

    def test_rerun_recusado_sem_energizar_se_a_condicao_difere(self):
        origem = self._sessao_de_origem()
        sessao = cli.SessaoCLI()
        for nome, valor, trecho in (("BASE_VOLTAGE_RMS", 220.0, "tensao_base_rms"),
                                    ("GRID_FREQUENCY_HZ", 50.0, "frequencia_hz"),
                                    ("P09_BRACO", "B", "set p09 A")):
            with self.subTest(nome=nome), mock.patch.object(mestre, "BASE_VOLTAGE_RMS", 127.0), \
                    mock.patch.object(mestre, "GRID_FREQUENCY_HZ", 60.0), mock.patch.object(mestre, "P09_BRACO", "A"), \
                    mock.patch.object(mestre, nome, valor), \
                    mock.patch.object(sessao, "confirmar") as confirmar, \
                    mock.patch.object(sessao, "_garantir_pasta_sessao") as pasta, \
                    mock.patch.object(sessao, "autorizar_saida") as autorizar, \
                    mock.patch.object(mestre.Bancada, "from_env") as from_env, \
                    contextlib.redirect_stdout(io.StringIO()) as saida:
                self.assertEqual(sessao.cmd_rerun([str(origem), "10-0002"]), 1)
                self.assertIn("Rerun recusado", saida.getvalue())
                self.assertIn(trecho, saida.getvalue())
                self.assertIn("Nada foi energizado", saida.getvalue())
                for alvo in (confirmar, pasta, autorizar, from_env):
                    alvo.assert_not_called()

    def test_rerun_na_mesma_condicao_pede_confirmacao_normal_e_restaura_contexto(self):
        origem = self._sessao_de_origem()
        sessao = cli.SessaoCLI()
        vistos = {}

        def executar(scripts, **kw):
            vistos.update(seed=mestre.BASE_SEED, rerun=mestre.RERUN_DE, scripts=[s.stem for s in scripts], **kw)
            return 0

        with mock.patch.object(mestre, "BASE_VOLTAGE_RMS", 127.0), mock.patch.object(mestre, "GRID_FREQUENCY_HZ", 60.0), \
                mock.patch.object(mestre, "P09_BRACO", "A"), mock.patch.object(mestre, "BASE_SEED", 99), \
                mock.patch.object(sessao, "confirmar", return_value=True) as confirmar, \
                mock.patch.object(sessao, "_executar_scripts", side_effect=executar), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sessao._run_falhas([str(origem)]), 0)
            self.assertEqual(mestre.BASE_SEED, 99, "contexto da CLI restaurado depois do rerun")
        self.assertEqual(confirmar.call_args[0][1], "EXECUTAR-CLASSE-10")
        self.assertEqual(vistos["seed"], 7)
        self.assertEqual(vistos["scripts"], ["10"])
        self.assertEqual(vistos["selecao"], {"10": {"literatura": (1,)}})
        self.assertEqual(vistos["rerun"]["sessao"], str(origem))
        self.assertEqual(vistos["rerun"]["ids_captura"], ["10-0002"])

    def test_run_falhas_sem_sessao_nesta_cli_recusa(self):
        sessao = cli.SessaoCLI()
        with contextlib.redirect_stdout(io.StringIO()) as saida:
            self.assertEqual(sessao.cmd_run(["falhas"]), 1)
        self.assertIn("Nada foi energizado", saida.getvalue())


if __name__ == "__main__":
    unittest.main()
