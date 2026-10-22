import contextlib
import importlib.util
import io
import json
import logging
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from pymeasure.adapters import Adapter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGICA_DIR = PROJECT_ROOT / "logica"
EXPERIMENT_DIRS = (PROJECT_ROOT / "experimentos_nativos", PROJECT_ROOT / "experimentos_waveform")
if str(LOGICA_DIR) not in sys.path:
    sys.path.insert(0, str(LOGICA_DIR))

from ametek_orm import (  # noqa: E402
    AmetekMX30, CommunicationError, InstrumentHardwareError, ParameterOutOfBoundsError,
)
from oscilloscope_orm import KeysightDSOX4034A, OscilloscopeError  # noqa: E402
from sinais import ruido_awgn, snr_medida  # noqa: E402
import sinais  # noqa: E402
from tests import assinatura_portavel  # noqa: E402
import mestre  # noqa: E402
import preflight_new  # noqa: E402

# Calibração de extremos REAL (testes de CalibracaoPorCondicaoTests e da
# recalibração a leem explicitamente).
CALIBRACAO_REAL = mestre.CALIBRACAO_EXTREMOS_PATH
_calibracao_de_teste = None


def setUpModule():
    """Os testes de mecânica (limite de bancada, pré-validação, metadata)
    rodam a 220 V/60 Hz, que a bancada nunca mediu — sem tabela própria a
    previsão é conservadora (v1.14) e quase tudo seria pulado. Aqui 220 V/
    60 Hz é declarado calibrado com a tabela REAL de 127 V/60 Hz, que é o que
    esses testes assumiam; a 230 V/50 Hz real fica de fora para as
    expectativas não mudarem a cada recalibração. O comportamento sem
    calibração é testado à parte, com o arquivo real."""
    global _calibracao_de_teste
    real = json.loads(CALIBRACAO_REAL.read_text(encoding="utf-8"))
    tabela = real["por_condicao"]["127V_60Hz"]
    dados = {"por_condicao": {
        "127V_60Hz": tabela,
        "220V_60Hz": dict(tabela, tensao_rms=220.0),
        "220V_50Hz": dict(tabela, tensao_rms=220.0, frequencia_hz=50.0),
    }}
    pasta = Path(tempfile.mkdtemp())
    caminho = pasta / "calibracao_extremos_teste.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    _calibracao_de_teste = (pasta, mock.patch.object(mestre, "CALIBRACAO_EXTREMOS_PATH", caminho))
    _calibracao_de_teste[1].start()


def tearDownModule():
    pasta, patch = _calibracao_de_teste
    patch.stop()
    shutil.rmtree(pasta, ignore_errors=True)


class _BancadaFake:
    """Suficiente para instanciar um Experimento sem abrir instrumento nenhum:
    gerar() de 04/06/08/09/19 lê self.config/self.osc para decidir
    sorteio vs. cobertura determinística (osc=None => sempre "simulado",
    ou seja, sempre sorteio — capturas_override não se aplica)."""

    config = mestre.Config(
        fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
        base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
        capture_current=False, current_base_a=None, results_dir=Path("."),
        sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
    )
    fonte = None
    osc = None

    @staticmethod
    def experimento_sem_niveis():
        class _SemNiveis(mestre.ExperimentoWaveform):
            id = "99"
            nome = "SEM_NIVEIS"

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

        return _SemNiveis(_BancadaFake())

    @staticmethod
    def experimento_com_niveis():
        class _ComNiveis(mestre.ExperimentoNativo):
            id = "98"
            nome = "COM_NIVEIS"
            NIVEIS = (0.1, 0.3, 0.5, 0.7, 0.9)

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

            def configurar(self, capture_index):
                return {}

        return _ComNiveis(_BancadaFake())


def _load_experimento(experiment_id: str):
    """Carrega a classe Experimento de um experimentos_nativos/NN.py ou
    experimentos_waveform/NN.py, do mesmo jeito que
    Bancada.executar_experimento() faz em produção, e instancia com uma
    bancada fake (só para poder chamar gerar())."""
    name = f"{experiment_id}.py"
    candidates = [directory / name for directory in EXPERIMENT_DIRS if (directory / name).is_file()]
    assert len(candidates) == 1, f"{name}: encontrado em {candidates}"
    script_path = candidates[0]
    module_name = f"teste_{script_path.parent.name}_{script_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Experimento(_BancadaFake())


def _sem_sorteio(experimento):
    """O mesmo experimento com as posições fixas de antes da v1.15."""
    import dataclasses
    experimento.config = dataclasses.replace(experimento.config, sorteio_posicao=False)
    return experimento


def _load_gerar(experiment_id: str):
    return _load_experimento(experiment_id).gerar


class ScriptedVisaConnection:
    def __init__(self, adapter):
        self.adapter = adapter
        self.pontos = 6000

    def query_binary_values(self, command, **kwargs):
        self.adapter.commands.append(command)
        return (20 + np.arange(self.pontos, dtype=np.int64) % 200).astype(np.uint8)

    def close(self):
        pass


class ScriptedSerialVisaResource:
    def __init__(self):
        self.writes = []
        self.flushes = []
        self.response = "AMETEK,MX30-3Pi,SERIAL,4.00\n"

    def write_raw(self, payload):
        self.writes.append(payload)

    def read(self):
        return self.response

    def flush(self, operation):
        self.flushes.append(operation)

    def close(self):
        pass


class _FakeTraceDevice:
    """Simula o suficiente da AMETEK (catálogo de TRACE + pontos de LIST) para
    exercitar o cache de program_capture() com ``simulated=False`` — o cache
    é desligado em modo simulado de propósito (ver ametek_orm.program_capture),
    então testar o cache exige um "instrumento" falso, não o modo simulado
    embutido do ORM."""

    def __init__(self):
        self.catalog = set()
        self.list_points = {"FUNCTION": 0, "VOLTAGE": 0, "DWELL": 0}
        self.trace_data_writes = 0

    def handle_write(self, command: str) -> None:
        upper = command.upper()
        if upper.startswith("TRACE:DEFINE "):
            self.catalog.add(command.split()[-1].upper())
        elif upper.startswith("TRACE:DATA "):
            self.trace_data_writes += 1
        elif upper.startswith("SOURCE:LIST:FUNCTION:SHAPE "):
            self.list_points["FUNCTION"] = len(command.split(None, 1)[1].split(","))
        elif upper.startswith("SOURCE:LIST:VOLTAGE "):
            self.list_points["VOLTAGE"] = len(command.split(None, 1)[1].split(","))
        elif upper.startswith("SOURCE:LIST:DWELL "):
            self.list_points["DWELL"] = len(command.split(None, 1)[1].split(","))

    def handle_query(self, command: str) -> str:
        upper = command.upper()
        if upper in {"SYSTEM:ERROR?", "SYST:ERR?"}:
            return '0,"No error"'
        if upper == "TRACE:CATALOG?":
            return ",".join(sorted(self.catalog))
        if upper == "SOURCE:LIST:FUNCTION:POINTS?":
            return str(self.list_points["FUNCTION"])
        if upper == "SOURCE:LIST:VOLTAGE:POINTS?":
            return str(self.list_points["VOLTAGE"])
        if upper == "SOURCE:LIST:DWELL:POINTS?":
            return str(self.list_points["DWELL"])
        return "0"


class ScriptedAdapter(Adapter):
    def __init__(self):
        super().__init__()
        self.connection = ScriptedVisaConnection(self)
        self.commands = []
        self.last_command = ""
        self.channel_scale = 10.0
        self.timebase_range = 0.2
        # Firmware que ACEITA :TIMebase:REFerence CUSTom ([KS] p. 1337-1338).
        # Para exercitar o caminho de fallback, os testes trocam estes dois.
        self.referencia_horizontal = "CUST"
        self.referencia_location = "0"
        self.preamble = "0,0,6000,1,3.333333333333e-5,0,0,0.01,0,128"

    def write(self, command, **kwargs):
        self.last_command = command
        self.commands.append(command)
        if command.upper().startswith(":CHANNEL1:SCALE "):
            self.channel_scale = float(command.split()[-1])
        if command.upper().startswith(":TIMEBASE:RANGE "):
            self.timebase_range = float(command.split()[-1])

    def read(self):
        command = self.last_command.upper()
        if command == "*IDN?":
            return "KEYSIGHT TECHNOLOGIES,DSOX4034A,MY59240844,07.66"
        if "SYSTEM:ERROR?" in command:
            return '0,"No error"'
        if "ACQUIRE:POINTS:ANALOG?" in command:
            return "6000"
        if "ACQUIRE:SRATE:ANALOG?" in command:
            return "30000"
        if "EXTERNAL:RANGE?" in command:
            return "8"
        if "CHANNEL1:SCALE?" in command:
            return str(self.channel_scale)
        if "TIMEBASE:RANGE?" in command:
            return str(self.timebase_range)
        if "TIMEBASE:REFERENCE:LOCATION?" in command:
            return self.referencia_location
        if "TIMEBASE:REFERENCE?" in command:
            return self.referencia_horizontal
        if "WAVEFORM:PREAMBLE?" in command:
            return self.preamble
        return "0"


class SignalTests(unittest.TestCase):
    def test_all_classes_are_finite_and_have_6000_points(self):
        t = np.arange(6000, dtype=np.float64) / 30000.0
        for number in range(1, 21):
            gerar = _load_gerar(f"{number:02d}")
            voltage, _parametros = gerar(t, 60.0, 0, np.random.default_rng(number))
            voltage = np.asarray(voltage)
            self.assertEqual(voltage.shape, (6000,))
            self.assertTrue(np.all(np.isfinite(voltage)))

    def test_sag_and_swell_have_400_captures_per_band(self):
        t = np.arange(6000, dtype=np.float64) / 30000.0
        for experiment, key in (("02", "sag_pu"), ("03", "swell_pu")):
            gerar = _load_gerar(experiment)
            counts = {}
            for index in range(2000):
                _voltage, parametros = gerar(t, 60.0, index, np.random.default_rng(index))
                level = parametros[key]
                counts[level] = counts.get(level, 0) + 1
            self.assertEqual(set(counts.values()), {400})

    def test_awgn_meets_requested_snr(self):
        t = np.arange(6000, dtype=np.float64) / 30000.0
        clean, _parametros = _load_gerar("01")(t, 60.0, 0, np.random.default_rng(1))
        for snr in (20.0, 30.0, 40.0, 50.0):
            noisy = ruido_awgn(clean, snr, np.random.default_rng(int(snr)))
            self.assertAlmostEqual(snr_medida(clean, noisy), snr, delta=0.3)


class ValorParaCapturaTests(unittest.TestCase):
    def test_cobertura_inativa_sempre_sorteia(self):
        rng = np.random.default_rng(1)
        valor = sinais.valor_para_captura(rng, 5.0, 10.0, 0, 1, cobertura_ativa=False)
        self.assertTrue(5.0 <= valor <= 10.0)

    def test_total_capturas_1_sempre_sorteia_mesmo_com_cobertura_ativa(self):
        rng = np.random.default_rng(1)
        valor = sinais.valor_para_captura(rng, 5.0, 10.0, 0, 1, cobertura_ativa=True)
        self.assertTrue(5.0 <= valor <= 10.0)

    def test_cobertura_ativa_cobre_exatamente_lo_e_hi_nas_pontas(self):
        rng = np.random.default_rng(1)
        primeiro = sinais.valor_para_captura(rng, 5.0, 10.0, 0, 4, cobertura_ativa=True)
        ultimo = sinais.valor_para_captura(rng, 5.0, 10.0, 3, 4, cobertura_ativa=True)
        self.assertEqual(primeiro, 5.0)
        self.assertEqual(ultimo, 10.0)

    def test_cobertura_ativa_e_deterministica_independente_do_rng(self):
        valor_a = sinais.valor_para_captura(np.random.default_rng(1), 0.0, 1.0, 2, 5, cobertura_ativa=True)
        valor_b = sinais.valor_para_captura(np.random.default_rng(999), 0.0, 1.0, 2, 5, cobertura_ativa=True)
        self.assertEqual(valor_a, valor_b)


class AmetekTests(unittest.TestCase):
    def test_pyvisa_asrl10_configuration_and_eot(self):
        resource = ScriptedSerialVisaResource()
        source = AmetekMX30(simulated=False, visa_resource=resource)
        source._configure_visa_resource()
        self.assertEqual(source.resource_name, "ASRL10::INSTR")
        self.assertEqual(resource.baud_rate, 115200)
        self.assertEqual(resource.data_bits, 8)
        self.assertEqual(resource.read_termination, "\n")
        self.assertEqual(resource.write_termination, "\n")
        self.assertIn("MX30", source.query("*IDN?"))
        self.assertEqual(resource.writes[-2:], [b"*IDN?\n", b"\x04"])
        source.disconnect()

    def test_write_espera_a_fonte_consumir_antes_do_proximo_comando(self):
        """Bancada 2026-09-30 (`arquivo/analises:docs/analise-2026-09-30`, N1): sem controle de
        fluxo, writes em rajada eram perdidos em silêncio ou colados (-113).
        Cada write agora é seguido de uma consulta de sincronismo antes que
        qualquer outro comando saia."""
        resource = ScriptedSerialVisaResource()
        resource.response = "0\n"
        source = AmetekMX30(simulated=False, visa_resource=resource)
        source.write("VOLTage:MODE STEP")
        source.write("VOLTage:TRIGgered 5.0")
        enviados = [w for w in resource.writes if w != b"\x04"]
        self.assertEqual(
            enviados,
            [b"VOLTage:MODE STEP\n", b"*ESR?\n", b"VOLTage:TRIGgered 5.0\n", b"*ESR?\n"],
        )

    def test_sincronismo_por_opc_quando_configurado(self):
        resource = ScriptedSerialVisaResource()
        resource.response = "1\n"
        source = AmetekMX30(simulated=False, visa_resource=resource)
        source.SINCRONISMO = "OPC"
        source.write("VOLTage:MODE STEP")
        enviados = [w for w in resource.writes if w != b"\x04"]
        self.assertEqual(enviados, [b"VOLTage:MODE STEP\n", b"*OPC?\n"])

    def test_sincronismo_invalido_e_recusado(self):
        resource = ScriptedSerialVisaResource()
        source = AmetekMX30(simulated=False, visa_resource=resource)
        source.SINCRONISMO = "NADA"
        with self.assertRaises(ValueError):
            source.write("VOLTage:MODE STEP")

    def test_write_nao_consulta_a_fonte_durante_gravacao_na_flash(self):
        """clear_all_traces(): não consultar durante a gravação da Flash —
        TRACe:DATA/DEFine/DELete têm espera própria."""
        resource = ScriptedSerialVisaResource()
        resource.response = "0\n"
        source = AmetekMX30(simulated=False, visa_resource=resource)
        for comando in ("TRACe:DATA TCC00,0,1", "TRACe:DEFine TCC00", "TRACe:DELete:ALL"):
            source.write(comando)
        self.assertNotIn(b"*ESR?\n", resource.writes)

    def test_sincronismo_tolera_mudez_ate_o_prazo(self):
        resource = ScriptedSerialVisaResource()
        respostas = iter(["", "", "0\n"])  # duas consultas sem resposta, depois volta
        resource.read = lambda: next(respostas)
        source = AmetekMX30(simulated=False, visa_resource=resource)
        source.write("SOURce:FUNCtion:SHAPe CSINusoid")
        self.assertEqual(resource.writes.count(b"*ESR?\n"), 3)

    def test_sincronismo_vira_falha_de_comunicacao_depois_do_prazo(self):
        resource = ScriptedSerialVisaResource()
        resource.response = ""
        source = AmetekMX30(simulated=False, visa_resource=resource)
        source.PRAZO_SINCRONISMO_S = 0.0
        with self.assertRaises(CommunicationError):
            source.write("SOURce:MODE ACDC")

    def test_tensao_disparada_e_escrita_na_resolucao_de_0v1(self):
        """A Rev. 5.53 TRUNCA VOLTage:TRIGgered a 0,1 V (2,7367 -> 2,7): a
        classe 04 era recusada pelo readback. Escreve-se o valor representável
        e o readback compara contra ELE, com a mesma tolerância de sempre."""
        source = AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
        source.trigger_pulse(2.7367107, width_s=0.060)
        self.assertIn("VOLTage:TRIGgered 2.7", source.command_log)
        self.assertEqual(source._transiente_esperado["VOLTage:TRIGgered?"], 2.7)
        source.trigger_step(139.7)
        self.assertIn("VOLTage:TRIGgered 139.7", source.command_log)
        source.trigger_step(4.96)
        self.assertEqual(source._transiente_esperado["VOLTage:TRIGgered?"], 5.0)

    def test_quantizacao_nunca_passa_do_teto_de_software(self):
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0)
        source.trigger_step(9.99)
        self.assertLessEqual(source._transiente_esperado["VOLTage:TRIGgered?"], 10.0)
        source.trigger_step(9.97)
        self.assertEqual(source._transiente_esperado["VOLTage:TRIGgered?"], 10.0)

    def test_output_requires_authorization(self):
        source = AmetekMX30(simulated=True)
        with self.assertRaises(PermissionError):
            source.output_enabled = True

    def test_trigger_pulse_rejects_voltage_above_limit(self):
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        with self.assertRaises(ParameterOutOfBoundsError):
            source.trigger_pulse(11.0, width_s=0.060)

    def test_trigger_pulse_and_trigger_step_compile_expected_commands(self):
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        source.trigger_step(5.0)
        source.trigger_pulse(1.5, width_s=0.060)
        commands = "\n".join(source.command_log).upper()
        self.assertIn("VOLTAGE:MODE STEP", commands)
        self.assertIn("VOLTAGE:TRIGGERED 5", commands)
        self.assertIn("VOLTAGE:MODE PULSE", commands)
        self.assertIn("PULSE:WIDTH 0.06", commands)

    def test_trigger_step_resets_residual_frequency_list_from_previous_class(self):
        """Regressão: classe 18 (FREQUENCY_DRIFT) deixa FREQuency:MODE em LIST;
        a bateria roda a classe 19 (DC_OFFSET) logo em seguida na mesma sessão,
        sem desligar a saída entre elas. FREQuency:MODE e VOLTage:MODE são
        eixos independentes (cap. 4.13/4.17 do manual SCPI) — sem um reset
        explícito, o *TRG da classe 19 aplicaria a rampa residual 57↔63 Hz da
        classe 18 em vez de manter a frequência fixa."""
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        source.frequency_drift_list(57.0, 63.0, voltage_rms=5.0, dwell_s=0.1)
        self.assertIn("FREQuency:MODE LIST", source.command_log)
        source.command_log.clear()
        source.trigger_step(5.0)
        self.assertIn("SOURce:FREQuency:MODE FIXed", source.command_log)
        self.assertLess(
            source.command_log.index("SOURce:FREQuency:MODE FIXed"),
            source.command_log.index("VOLTage:MODE STEP"),
        )

    def test_frequency_drift_list_repeat_e_zero_nao_um(self):
        """Hipótese LIST:REPeat (CHANGELOG/v1.9.md), confirmada na bancada
        v1.10 (NOTCH real: 516ms de transiente contra ~200ms nominais,
        2,58x — dentro da faixa 2x-2,7x já medida): 'SOURce:LIST:REPeat 1'
        é lido pelo firmware Rev. 5.53 como 'repete uma vez' (toca 2x), não
        'sem repetição'. Mesma correção de program_capture(), aqui para os
        2 pontos (início/fim) da rampa de frequência da classe 18."""
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        source.frequency_drift_list(57.0, 63.0, voltage_rms=5.0, dwell_s=0.1)
        self.assertIn("SOURce:LIST:REPeat 0,0", source.command_log)
        self.assertNotIn("SOURce:LIST:REPeat 1,1", source.command_log)

    def test_trigger_pulse_resets_residual_frequency_list_from_previous_class(self):
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        source.frequency_drift_list(57.0, 63.0, voltage_rms=5.0, dwell_s=0.1)
        source.command_log.clear()
        source.trigger_pulse(3.0, width_s=0.060)
        self.assertIn("SOURce:FREQuency:MODE FIXed", source.command_log)
        self.assertLess(
            source.command_log.index("SOURce:FREQuency:MODE FIXed"),
            source.command_log.index("VOLTage:MODE PULSe"),
        )

    def test_troca_de_forma_e_modo_usa_wai_e_confirma_fila_de_erros(self):
        """Regressão de bancada: ``select_sine_shape()``/``disable_dc_offset()``
        trocavam ``FUNCtion:SHAPe``/``SOURce:MODE`` sem confirmar a fila de
        erros depois (só ``aguardar_resposta()``, que apenas confirma que a
        fonte voltou a falar, não que a fila está limpa). Um erro real gerado
        por essas trocas ficava pendente até o ``assert_no_errors()`` dentro
        do ``arm()`` da PRÓXIMA classe, atribuído erroneamente ao
        ``INITiate:IMMediate`` dela — reproduzido de forma determinística na
        bancada: 01/NORMAL (STEP) seguida de 02/SAG (PULSe) na MESMA conexão.
        ``configure_harmonics_csine()``/``select_sine_shape()``/
        ``disable_dc_offset()``/``enable_dc_offset()`` agora usam ``*WAI``
        (mais rápido e confiável que o polling por ``*IDN?`` de
        ``aguardar_resposta()`` — validado na bancada real, 3/3) seguido de
        ``assert_no_errors()``."""
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)

        source.configure_harmonics_csine(10.0)
        source.select_sine_shape()
        source.enable_dc_offset(1.0, ac_peak_v=7.0)
        source.disable_dc_offset()

        # configure_harmonics_csine() manda *WAI duas vezes (após escolher a
        # forma CSINusoid e após programar o nível de clipping — só a
        # SEGUNDA é seguida de assert_no_errors ali, de propósito: aponta o
        # erro para o comando mais provável de falhar); as outras três
        # chamadas mandam *WAI uma vez cada, sempre seguido de
        # assert_no_errors.
        self.assertEqual(source.command_log.count("*WAI"), 5)
        self.assertEqual(source.command_log.count("SYSTem:ERRor?"), 4)
        ultimos_wai = [index for index, cmd in enumerate(source.command_log) if cmd == "*WAI"][-4:]
        for index in ultimos_wai:
            self.assertEqual(
                source.command_log[index + 1], "SYSTem:ERRor?",
                "*WAI deve ser seguido de confirmação da fila de erros",
            )

    def test_arm_tolera_fonte_muda_por_alguns_segundos(self):
        """Regressão da falha que abortou a bateria na classe 05/HARMONICS:
        ``FUNCtion:SHAPe CSINusoid`` deixa a Rev. 5.53 muda por segundos, a
        consulta seguinte estourava o timeout do VISA e ``arm()`` morria na
        PRIMEIRA tentativa, derrubando as 20 classes."""
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        original_query = source.query
        mudez = {"restantes": 3}

        def query_com_fonte_muda(command):
            if command.strip().upper().startswith("TRIG") and mudez["restantes"] > 0:
                mudez["restantes"] -= 1
                raise CommunicationError("VI_ERROR_TMO simulado")
            return original_query(command)

        source.query = query_com_fonte_muda
        source.arm(timeout_s=5.0)
        self.assertEqual(mudez["restantes"], 0)

    def test_arm_ainda_falha_quando_a_fonte_nunca_responde(self):
        """A tolerância acima não pode virar espera infinita: um cabo solto
        continua reprovando, com mensagem própria em vez de traceback de VISA."""
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)

        def query_sempre_muda(command):
            raise CommunicationError("VI_ERROR_TMO simulado")

        source.query = query_sempre_muda
        with self.assertRaises(TimeoutError):
            source.arm(timeout_s=0.5)

    def test_configure_harmonics_csine_rejects_above_documented_ceiling(self):
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        with self.assertRaises(ParameterOutOfBoundsError):
            source.configure_harmonics_csine(30.0)
        source.configure_harmonics_csine(20.0)
        # Nome completo 'CSINusoid', não a forma curta 'CSINe' documentada no
        # manual — a Rev. 5.53 resolve FUNCtion:SHAPe como lookup no
        # catálogo de waveforms (TRACe:CATalog?) e rejeita a forma curta com
        # -256 "File name not found".
        joined = "\n".join(source.command_log).upper()
        self.assertIn("SOURCE:FUNCTION:SHAPE CSINUSOID", joined)
        self.assertIn("SOURCE:FUNCTION:SHAPE:CSINUSOID 20", joined)

    def test_enable_dc_offset_rejects_combined_peak_above_limit(self):
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=15.0, max_current_a=0.5)
        with self.assertRaises(ParameterOutOfBoundsError):
            source.enable_dc_offset(10.0, ac_peak_v=10.0)
        source.enable_dc_offset(1.0, ac_peak_v=10.0)

    def test_capture_compiles_to_documented_trace_and_list_commands(self):
        source = AmetekMX30(
            simulated=True,
            max_voltage_rms=10.0,
            max_peak_v=100.0,
            max_current_a=0.5,
        )
        source.configure_safe_baseline(
            voltage_range_rms=150.0,
            # Limite de PICO do software (validado). O VOLTage:HIGH da fonte é
            # RMS e recebe max_voltage_rms (T12, `arquivo/analises:docs/analise-2026-09-30`).
            voltage_high_vp=100.0,
            current_limit_a=0.5,
            protection_delay_s=0.1,
            frequency_hz=50.0,
        )
        self.assertIn("SOURce:VOLTage:HIGH 10", source.command_log)
        self.assertNotIn("SOURce:VOLTage:HIGH 100", source.command_log)
        t = np.arange(6000, dtype=np.float64) / 30000.0
        voltage = np.sin(2.0 * np.pi * 50.0 * t)
        source.program_capture(voltage, base_voltage_rms=5.0, frequency_hz=50.0)
        self.assertAlmostEqual(source.last_programmed_peak_v, 5.0 * np.sqrt(2.0), places=3)
        commands = "\n".join(source.command_log).upper()
        self.assertIn("OUTPUT:TTLTRG:MODE TRIG", commands)
        self.assertIn("SOURCE:LIST:FUNCTION:SHAPE", commands)
        self.assertIn("SOURCE:LIST:VOLTAGE", commands)
        self.assertIn("SOURCE:LIST:DWELL", commands)
        self.assertIn("SOURCE:CURRENT:PROTECTION:STATE ON", commands)
        self.assertNotIn("HARMONIC:CLEAR", commands)
        self.assertNotIn("OUTPUT:TRIGGER", commands)
        self.assertNotIn("CURRENT:LIMIT", commands)

    def test_impulsive_transient_reports_reconstructed_peak(self):
        source = AmetekMX30(
            simulated=True,
            max_voltage_rms=10.0,
            max_peak_v=100.0,
            max_current_a=0.5,
        )
        t = np.arange(6000, dtype=np.float64) / 30000.0
        signal, _parametros = _load_gerar("08")(t, 50.0, 0, np.random.default_rng(8))
        source.program_capture(signal, base_voltage_rms=5.0, frequency_hz=50.0)
        # Com o ciclo/frequência corrigido, o pico reconstruído da TRACE que
        # contém o pulso deve refletir de perto o pico realmente amostrado
        # (não mais inflado por viés de ciclo mal fechado) e ser muito maior
        # que o pico de uma senoide limpa na mesma tensão base.
        sampled_peak = float(np.max(np.abs(signal))) * 5.0 * np.sqrt(2.0)
        nominal_peak = 5.0 * np.sqrt(2.0)
        self.assertAlmostEqual(source.last_programmed_peak_v, sampled_peak, delta=sampled_peak * 0.02)
        self.assertGreater(source.last_programmed_peak_v, 3.0 * nominal_peak)
        self.assertLessEqual(source.last_programmed_peak_v, 100.0)

    def test_arm_envia_wai_antes_do_init(self):
        """Regressão de bancada: 01/NORMAL (VOLTage:MODE STEP) seguido de
        02/SAG (VOLTage:MODE PULSe) na MESMA conexão (sem passar de novo por
        configure_safe_baseline, que força VOLTage:MODE FIXed) reproduzia
        (-300, 'Device specific error') no INITiate:IMMediate de forma
        determinística — comandos de trigger são processados em paralelo pela
        Rev. 5.53 (manual, seção 7.7), e TRIGger:STATe? relatar IDLE não
        garante que a troca de VOLTage:MODE já assentou. *WAI (validado na
        bancada como mais rápido e confiável que o polling *IDN? de
        aguardar_resposta) precisa ser o comando imediatamente anterior ao
        INITiate:IMMediate dentro de arm()."""
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        source.trigger_step(5.0)
        source.command_log.clear()
        source.arm()
        wai_index = source.command_log.index("*WAI")
        init_index = source.command_log.index("INITiate:IMMediate")
        self.assertEqual(init_index, wai_index + 1)

    def test_disable_dc_offset_e_select_sine_shape_sao_no_op_no_estado_padrao(self):
        """Regressão de bancada: ``disable_dc_offset()`` mandava
        SOURce:VOLTage:OFFSet incondicionalmente, mesmo com o modo já em AC
        puro (nunca tendo passado por ACDC) — o Apêndice C do manual documenta
        -300 para "Attempt to program voltage offset while in DC or AC mode
        only" (offset só é aceito em modo ACDC). Isso derrubava a PRIMEIRA
        classe da bateria (01/NORMAL, que nunca toca offset) só por chamar
        restaurar_forma_e_modo_padrao() no fim. Numa instância nova (estado
        padrão AC/SINusoid, igual ao que configure_safe_baseline() programa),
        nenhum dos dois deve escrever nada."""
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        source.select_sine_shape()
        source.disable_dc_offset()
        source.restaurar_forma_e_modo_padrao()
        self.assertEqual(source.command_log, [])

    def test_forma_volta_a_senoide_depois_de_classe_waveform(self):
        """Regressão de bancada (2026-10-22): depois da LIST de TRACEs de uma
        classe waveform (17), restaurar_forma_e_modo_padrao() não mandava
        FUNCtion:SHAPe SINusoid, e as nativas seguintes (18, 19) tocaram a
        forma entalhada da 17."""
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        t = np.arange(6000, dtype=np.float64) / 30000.0
        source.program_capture(np.sin(2.0 * np.pi * 50.0 * t), base_voltage_rms=5.0, frequency_hz=50.0)
        source.command_log.clear()
        source.restaurar_forma_e_modo_padrao()
        self.assertEqual(source.command_log[:3], ["SOURce:FUNCtion:SHAPe SINusoid", "*WAI", "SYSTem:ERRor?"])
        source.command_log.clear()
        source.restaurar_forma_e_modo_padrao()
        self.assertEqual(source.command_log, [])

    def test_disable_dc_offset_roda_de_verdade_quando_modo_e_acdc(self):
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        source.enable_dc_offset(1.0, ac_peak_v=7.0)
        source.command_log.clear()
        source.disable_dc_offset()
        joined = "\n".join(source.command_log).upper()
        self.assertIn("SOURCE:VOLTAGE:OFFSET 0", joined)
        self.assertIn("SOURCE:MODE AC", joined)

    def test_cycle_count_matches_grid_frequency_not_hardcoded_50hz(self):
        """Regressão: POINTS_PER_CYCLE fixo em 600 só fecha 1 ciclo a 50 Hz.
        A 60 Hz (padrão do projeto) isso gerava viés de pico de ~15%."""
        source = AmetekMX30(
            simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5,
        )
        t = np.arange(6000, dtype=np.float64) / 30000.0
        voltage = np.sin(2.0 * np.pi * 60.0 * t)
        source.program_capture(voltage, base_voltage_rms=5.0, frequency_hz=60.0)
        self.assertEqual(source._last_cycles, 12)
        expected_peak = 5.0 * math.sqrt(2.0)
        erro_relativo = abs(source.last_programmed_peak_v - expected_peak) / expected_peak
        self.assertLess(erro_relativo, 0.001)
        dwell_commands = [c for c in source.command_log if c.startswith("SOURce:LIST:DWELl ")]
        self.assertTrue(dwell_commands, "Nenhum comando SOURce:LIST:DWELl encontrado")
        primeiro_dwell = float(dwell_commands[-1].split()[-1].split(",")[0])
        self.assertAlmostEqual(primeiro_dwell, 1.0 / 60.0, places=6)

    def test_list_repeat_e_zero_nao_um_para_nao_dobrar_cada_ciclo(self):
        """Hipótese LIST:REPeat (CHANGELOG/v1.9.md) confirmada na bancada
        (v1.10): NOTCH real levou 516ms para concluir o transiente
        (apos_trigger -> transiente_concluido) contra ~200ms nominais (12
        ciclos x 16,67ms a 60Hz) — 2,58x, dentro da faixa de 2x-2,7x já
        medida nas outras 7 classes TRACe. 'SOURce:LIST:REPeat 1' é lido
        pelo firmware Rev. 5.53 como 'repete uma vez' (toca 2x cada ciclo),
        não 'sem repetição' — o valor certo para tocar cada ciclo uma única
        vez é 0."""
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        t = np.arange(6000, dtype=np.float64) / 30000.0
        voltage = np.sin(2.0 * np.pi * 60.0 * t)
        source.program_capture(voltage, base_voltage_rms=5.0, frequency_hz=60.0)
        repeat_commands = [c for c in source.command_log if c.startswith("SOURce:LIST:REPeat ")]
        self.assertTrue(repeat_commands, "Nenhum comando SOURce:LIST:REPeat encontrado")
        self.assertEqual(repeat_commands[-1], "SOURce:LIST:REPeat " + ",".join("0" for _ in range(12)))

    def test_program_capture_reaproveita_trace_identica_na_mesma_conexao(self):
        """Regressão: --low-voltage (e qualquer classe que reuse a mesma forma
        base) reprogramava ~12 TRACe na Flash (~1s cada) mesmo sem nenhuma
        mudança de forma/tensão/frequência desde a última chamada bem-sucedida
        nesta conexão. O cache só é considerado fora do modo simulado (ver
        ametek_orm.program_capture) — por isso o teste força
        ``source.simulated = False`` com um instrumento falso."""
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        source.simulated = False
        device = _FakeTraceDevice()

        def fake_write(command):
            source.command_log.append(command)
            device.handle_write(command)

        def fake_query(command):
            source.command_log.append(command)
            return device.handle_query(command)

        source.write = fake_write
        source.query = fake_query

        t = np.arange(6000, dtype=np.float64) / 30000.0
        voltage = np.sin(2.0 * np.pi * 60.0 * t)
        voltage_diferente = np.sin(2.0 * np.pi * 60.0 * t + 0.3)

        with mock.patch("ametek_orm.time.sleep"):
            source.program_capture(voltage, base_voltage_rms=5.0, frequency_hz=60.0)
            self.assertEqual(device.trace_data_writes, 12)

            device.trace_data_writes = 0
            source.program_capture(voltage, base_voltage_rms=5.0, frequency_hz=60.0)
            self.assertEqual(device.trace_data_writes, 0, "forma idêntica deveria reaproveitar o cache")

            device.trace_data_writes = 0
            source.program_capture(voltage_diferente, base_voltage_rms=5.0, frequency_hz=60.0)
            self.assertEqual(device.trace_data_writes, 12, "forma diferente deve reprogramar")

            # Catálogo apagado por fora (ex.: TRACe:DELete:ALL de outra sessão)
            # não pode ser mascarado por um cache local desatualizado.
            device.catalog.clear()
            device.trace_data_writes = 0
            source.program_capture(voltage_diferente, base_voltage_rms=5.0, frequency_hz=60.0)
            self.assertEqual(
                device.trace_data_writes, 12,
                "catálogo vazio no instrumento não pode confiar cegamente no cache local",
            )


class DiagnosticoLogTests(unittest.TestCase):
    def test_sem_diagnostico_nao_loga(self):
        fonte = mestre.AmetekMX30(simulated=True, diagnostico=False)
        with self.assertLogs("AmetekORM", level="INFO") as captura:
            fonte._log_diagnostico("ponto_teste")
            # nenhuma chamada real acontece; força um log de controle pra
            # assertLogs não estourar por falta de QUALQUER log capturado
            logging.getLogger("AmetekORM").info("controle")
        self.assertEqual(len(captura.records), 1)
        self.assertIn("controle", captura.records[0].getMessage())

    def test_com_diagnostico_loga_ponto_e_timestamp(self):
        fonte = mestre.AmetekMX30(simulated=True, diagnostico=True)
        with self.assertLogs("AmetekORM", level="INFO") as captura:
            fonte._log_diagnostico("ponto_teste", extra_info=42)
        linhas = [registro.getMessage() for registro in captura.records]
        self.assertTrue(any("ponto_teste" in linha for linha in linhas))
        self.assertTrue(any("extra_info" in linha for linha in linhas))

    def test_com_diagnostico_tolera_resposta_nao_numerica_de_measure_voltage(self):
        """Regressão: measure_voltage() faz ``float(self.query(...))`` — uma
        resposta malformada/não numérica do instrumento levanta ValueError,
        não CommunicationError/InstrumentHardwareError. Sem capturar
        ValueError especificamente aqui (mesmo padrão já usado no bloco de
        STATus:OPERation:CONDition? logo acima), essa falha de UMA leitura de
        diagnóstico abortaria a chamada de produção inteira (trigger_step,
        arm, etc.), contradizendo a docstring de _log_diagnostico()."""
        fonte = mestre.AmetekMX30(simulated=True, diagnostico=True)
        with mock.patch.object(fonte, "measure_voltage", side_effect=ValueError("resposta malformada")):
            with self.assertLogs("AmetekORM", level="INFO") as captura:
                fonte._log_diagnostico("ponto_teste")  # não deve propagar ValueError
        linhas = [registro.getMessage() for registro in captura.records]
        self.assertTrue(any("tensao_v=None" in linha for linha in linhas))

    def test_trigger_step_com_diagnostico_nao_muda_writes_enviados(self):
        # max_voltage_rms explícito: o default da classe é 10.0 Vrms, que
        # rejeitaria 100.0 (ParameterOutOfBoundsError) antes de qualquer
        # write — o teste precisa exercitar trigger_step() de ponta a ponta,
        # não abortar na validação de faixa.
        sem_log = mestre.AmetekMX30(simulated=True, diagnostico=False, max_voltage_rms=100.0)
        sem_log.trigger_step(100.0)
        com_log = mestre.AmetekMX30(simulated=True, diagnostico=True, max_voltage_rms=100.0)
        com_log.trigger_step(100.0)
        # _log_diagnostico() só LÊ estado (query() sempre termina em "?"), e em
        # modo simulado query() também grava em command_log — é assim que este
        # mesmo arquivo já testa, por ex., os SYSTem:ERRor? de check_errors()
        # (ver AmetekTests: "source.command_log.count('SYSTem:ERRor?')").
        # Então diagnostico=True naturalmente adiciona ENTRADAS DE LEITURA a
        # command_log; a garantia que a constraint global do plano pede é que
        # nenhum WRITE (comando que muda estado do instrumento) seja
        # reordenado/adicionado/removido — por isso comparamos só os comandos
        # que não terminam em "?" (toda query SCPI usada neste driver termina
        # em "?"; todo write, não).
        def escritas(log):
            return [comando for comando in log if not comando.endswith("?")]

        self.assertEqual(escritas(sem_log.command_log), escritas(com_log.command_log))

    def test_program_capture_com_diagnostico_loga_antes_e_depois_voltage_mode_list(self):
        # Hipótese em aberto (CHANGELOG/v1.9.md): a captura real de classes
        # TRACe/LIST começa com a saída visivelmente zerada por ~20ms. Este
        # par de logs (mesmo idioma de antes_sourcemode_acdc/
        # apos_sourcemode_acdc) é o que vai permitir, na próxima sessão
        # física, ver se a tensão já cai ANTES de VOLTage:MODE LIST ou só
        # DEPOIS dele.
        t = np.arange(6000, dtype=np.float64) / 30000.0
        voltage = np.sin(2.0 * np.pi * 50.0 * t)
        fonte = AmetekMX30(simulated=True, diagnostico=True, max_voltage_rms=10.0, max_peak_v=100.0)
        with self.assertLogs("AmetekORM", level="INFO") as captura:
            fonte.program_capture(voltage, base_voltage_rms=5.0, frequency_hz=50.0)
        linhas = [registro.getMessage() for registro in captura.records]
        indice_antes = next(i for i, linha in enumerate(linhas) if "ponto=antes_voltage_mode_list" in linha)
        indice_depois = next(i for i, linha in enumerate(linhas) if "ponto=apos_voltage_mode_list" in linha)
        self.assertLess(indice_antes, indice_depois)

    def test_program_capture_com_diagnostico_nao_muda_writes_enviados(self):
        t = np.arange(6000, dtype=np.float64) / 30000.0
        voltage = np.sin(2.0 * np.pi * 50.0 * t)
        sem_log = AmetekMX30(simulated=True, diagnostico=False, max_voltage_rms=10.0, max_peak_v=100.0)
        sem_log.program_capture(voltage, base_voltage_rms=5.0, frequency_hz=50.0)
        com_log = AmetekMX30(simulated=True, diagnostico=True, max_voltage_rms=10.0, max_peak_v=100.0)
        com_log.program_capture(voltage, base_voltage_rms=5.0, frequency_hz=50.0)

        def escritas(log):
            return [comando for comando in log if not comando.endswith("?")]

        self.assertEqual(escritas(sem_log.command_log), escritas(com_log.command_log))

    def test_trigger_com_diagnostico_loga_apos_trigger(self):
        fonte = AmetekMX30(simulated=True, diagnostico=True, max_voltage_rms=10.0, max_peak_v=100.0)
        fonte.write("INITiate:IMMediate")  # simulado: TRIGger:STATe? -> ARM (ver _simulate_write)
        with self.assertLogs("AmetekORM", level="INFO") as captura:
            fonte.trigger()
        linhas = [registro.getMessage() for registro in captura.records]
        self.assertTrue(any("ponto=apos_trigger" in linha for linha in linhas))

    def test_trigger_com_diagnostico_nao_muda_writes_enviados(self):
        sem_log = AmetekMX30(simulated=True, diagnostico=False, max_voltage_rms=10.0, max_peak_v=100.0)
        sem_log.write("INITiate:IMMediate")
        sem_log.trigger()
        com_log = AmetekMX30(simulated=True, diagnostico=True, max_voltage_rms=10.0, max_peak_v=100.0)
        com_log.write("INITiate:IMMediate")
        com_log.trigger()

        def escritas(log):
            return [comando for comando in log if not comando.endswith("?")]

        self.assertEqual(escritas(sem_log.command_log), escritas(com_log.command_log))


class KeysightTests(unittest.TestCase):
    def test_channel_mapping_and_acquisition(self):
        adapter = ScriptedAdapter()
        scope = KeysightDSOX4034A(adapter)
        self.assertIn("DSOX4034A", scope.verify_identity())
        scope.initialize_safe()
        scope.configure_channel(
            1,
            scale=10.0,
            probe_attenuation=100.0,
            coupling="DC",
            units="VOLT",
        )
        self.assertGreater(scope.set_vertical_scale(1, 7.1), 0)
        scope.configure_acquisition()
        scope.setup_external_trigger(level_v=1.5, probe_attenuation=1.0, range_v=8.0)
        joined = "\n".join(adapter.commands)
        self.assertIn(":CHANnel1:DISPlay 1", joined)
        self.assertIn(":CHANnel1:COUPling DC", joined)
        self.assertNotIn("True", joined)
        time_s, voltage = scope.get_waveform(1)
        self.assertEqual(time_s.shape, (6000,))
        self.assertEqual(voltage.shape, (6000,))
        self.assertAlmostEqual(time_s[1] - time_s[0], 1.0 / 30000.0, places=12)

    def test_pre_trigger_shifts_timebase_position(self):
        # Manual Keysight (cap. 35): :TIMebase:POSition = t_referencia -
        # t_trigger. Com REFerence LEFT a referência é a borda esquerda da
        # janela; para sobrar baseline ANTES do trigger essa borda precisa
        # ficar cronologicamente ANTES dele, ou seja pos NEGATIVO.
        adapter = ScriptedAdapter()
        scope = KeysightDSOX4034A(adapter)
        scope.initialize_safe()
        scope.configure_acquisition(pre_trigger_s=0.060)
        joined = "\n".join(adapter.commands)
        self.assertIn(":TIMebase:POSition -0.06", joined)

    def test_pre_trigger_zero_does_not_send_negative_zero(self):
        adapter = ScriptedAdapter()
        scope = KeysightDSOX4034A(adapter)
        scope.initialize_safe()
        scope.configure_acquisition(pre_trigger_s=0.0)
        joined = "\n".join(adapter.commands)
        self.assertIn(":TIMebase:POSition 0", joined)
        self.assertNotIn(":TIMebase:POSition -0", joined)


class PreflightNewTests(unittest.TestCase):
    """Não exercita o ciclo arm/trigger real (depende de hardware físico
    respondendo TER?/OPERegister em tempo real); confirma que as chamadas aos
    dois ORMs feitas por preflight_new usam assinaturas/kwargs válidos e que
    os utilitários puramente numéricos calculam o esperado."""

    def test_native_ametek_commands_compile_without_error(self):
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        source.configure_safe_baseline(
            voltage_range_rms=150.0, voltage_high_vp=100.0, current_limit_a=0.5,
            protection_delay_s=0.1, frequency_hz=50.0,
        )
        source.authorize_output(True)
        source.energize_baseline()
        source.trigger_step(5.0)
        source.trigger_pulse(preflight_new.SAG_LEVEL_PU * 5.0, width_s=preflight_new.SAG_DURATION_S)
        source.configure_harmonics_csine(preflight_new.CSINE_THD_PCT)
        source.trigger_step(5.0)
        source.frequency_drift_list(
            preflight_new.FREQ_DRIFT_START_HZ, preflight_new.FREQ_DRIFT_END_HZ,
            voltage_rms=5.0, dwell_s=0.1,
        )
        ac_peak_v = 5.0 * math.sqrt(2.0)
        source.enable_dc_offset(preflight_new.DC_OFFSET_PU * ac_peak_v, ac_peak_v=ac_peak_v)
        self.assertTrue(np.isfinite(source.measure_voltage()))
        self.assertTrue(np.isfinite(source.measure_current()))
        self.assertTrue(np.isfinite(source.measure_power_w()))
        self.assertTrue(np.isfinite(source.measure_power_factor()))

    def test_scope_error_queue_and_channel2_helpers(self):
        adapter = ScriptedAdapter()
        scope = KeysightDSOX4034A(adapter)
        scope.initialize_safe()
        self.assertEqual(preflight_new._test_scope_error_queue(scope), "fila de erros vazia")
        detail = preflight_new._test_channel2_toggle(scope)
        self.assertIn("CAPTURE_CURRENT=0", detail)

    def test_step_segue_apos_desvio_de_medida_mas_aborta_em_falha_estrutural(self):
        """Uma medida fora da tolerância vira AVISO e NÃO aborta o preflight
        (para que uma única execução na bancada mostre todos os desvios);
        qualquer outra exceção continua abortando."""
        preflight_new._AVISOS_DE_MEDIDA.clear()
        executadas = []

        def desvio_de_medida():
            executadas.append("desvio")
            preflight_new._assert_close("medida X", 13.334, 8.980, 1.796)

        preflight_new._step("etapa com desvio", desvio_de_medida)
        preflight_new._step("etapa seguinte", lambda: executadas.append("seguinte"))

        self.assertEqual(executadas, ["desvio", "seguinte"])
        self.assertEqual(len(preflight_new._AVISOS_DE_MEDIDA), 1)
        self.assertIn("medida X", preflight_new._AVISOS_DE_MEDIDA[0])

        def falha_estrutural():
            raise InstrumentHardwareError("AMETEK rejeitou comando")

        with self.assertRaises(InstrumentHardwareError):
            preflight_new._step("etapa estrutural", falha_estrutural)
        preflight_new._AVISOS_DE_MEDIDA.clear()

    def test_measurements_isola_falha_de_uma_query_como_aviso(self):
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        self.assertIn("VOLTage", preflight_new._test_measurements(source))

        def query_quebrada():
            raise ValueError("resposta serial malformada")

        source.measure_current = query_quebrada
        with self.assertRaises(preflight_new.ToleranciaExcedida) as capturado:
            preflight_new._test_measurements(source)
        self.assertIn("MEASure:CURRent", str(capturado.exception))

    def test_restaurar_forma_e_modo_padrao_desfaz_csine_e_offset(self):
        """Regressão: a classe 05 deixava a senoide clipada e a 19 o offset/
        ACDC ligados para a classe seguinte (estado permanente, não
        transiente)."""
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        source.configure_harmonics_csine(10.0)
        source.enable_dc_offset(1.0, ac_peak_v=7.0)
        source.command_log.clear()
        source.restaurar_forma_e_modo_padrao()
        joined = "\n".join(source.command_log).upper()
        self.assertIn("SOURCE:FUNCTION:SHAPE SINUSOID", joined)
        self.assertIn("SOURCE:VOLTAGE:OFFSET 0", joined)
        self.assertIn("SOURCE:MODE AC", joined)

    def test_select_sine_shape_e_disable_dc_offset_desfazem_estado_permanente(self):
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        source.configure_harmonics_csine(10.0)
        source.enable_dc_offset(1.0, ac_peak_v=7.0)
        source.command_log.clear()
        source.select_sine_shape()
        source.disable_dc_offset()
        joined = "\n".join(source.command_log).upper()
        self.assertIn("SOURCE:FUNCTION:SHAPE SINUSOID", joined)
        self.assertIn("SOURCE:VOLTAGE:OFFSET 0", joined)
        self.assertIn("SOURCE:MODE AC", joined)

    def test_rms_and_assert_close_helpers(self):
        t = np.arange(6000, dtype=np.float64) / 30000.0
        voltage = 5.0 * math.sqrt(2.0) * np.sin(2.0 * np.pi * 60.0 * t)
        self.assertAlmostEqual(preflight_new._rms(voltage), 5.0, delta=0.01)
        preflight_new._assert_close("teste", 5.0, 5.05, 0.1)
        with self.assertRaises(RuntimeError):
            preflight_new._assert_close("teste", 5.0, 6.0, 0.1)

    def test_write_and_confirm_returns_response_and_elapsed_time(self):
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        response, elapsed_s = preflight_new._write_and_confirm(source, "VOLTage 5.0", "VOLTage?")
        self.assertEqual(response, "5.0")
        self.assertGreaterEqual(elapsed_s, 0.0)

    def test_list_voltage_identical_values_diagnostic_runs_offline(self):
        # O modo simulado conta ingenuamente len(csv.split(",")) — não
        # reproduz o bug de firmware (colapso de valores idênticos para o
        # caso especial de lista de 1 item), então em modo simulado as duas
        # listas devem registrar 12 pontos. O objetivo deste teste é só
        # confirmar que a função roda sem erro e que o formato do detalhe
        # bate com o esperado, não replicar o bug real de hardware.
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        detail = preflight_new._test_list_voltage_identical_values(source)
        self.assertIn("distintos: 12 pontos", detail)
        self.assertIn("idênticos: 12 pontos", detail)

    def test_list_sequence_matches_production_runs_offline(self):
        # _simulate_write/_simulate_query contam cada eixo LIST (FUNCTION/
        # VOLTAGE/DWELL/REPEAT) separadamente — confirma que a sequência real
        # de program_capture() roda sem erro e que os três eixos batem 12/12/12.
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        detail = preflight_new._test_list_sequence_matches_production(source)
        self.assertIn("FUNCtion:SHAPe=12 pontos", detail)
        self.assertIn("VOLTage=12 pontos", detail)
        self.assertIn("DWELl=12 pontos", detail)


class BateriaResilienciaTests(unittest.TestCase):
    """Regressão: antes, uma exceção em qualquer classe propagava até
    main() e abortava a bateria inteira — as classes restantes nunca
    rodavam (ver Bancada.executar_bateria em mestre.py)."""

    def _config_temporaria(self, results_dir: Path) -> "mestre.Config":
        return mestre.Config(
            fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(30.0,), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=results_dir,
            sim_captures_per_class=2, real_captures_per_class=1, disturbance_start_s=0.06,
        )

    def test_falha_de_uma_classe_nao_aborta_a_bateria(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            ok_script = tmp_dir / "01.py"
            ok_script.write_text(
                "import numpy as np\n"
                "from mestre import ExperimentoWaveform\n"
                "class Experimento(ExperimentoWaveform):\n"
                "    id = '01'\n"
                "    nome = 'OK'\n"
                "    def gerar(self, t, f0, capture_index, rng):\n"
                "        return np.sin(2.0 * np.pi * f0 * t), {}\n",
                encoding="utf-8",
            )
            bad_script = tmp_dir / "02.py"
            bad_script.write_text(
                "from mestre import ExperimentoWaveform\n"
                "class Experimento(ExperimentoWaveform):\n"
                "    id = '02'\n"
                "    nome = 'RUIM'\n"
                "    def gerar(self, t, f0, capture_index, rng):\n"
                "        raise RuntimeError('falha proposital')\n",
                encoding="utf-8",
            )
            results_dir = tmp_dir / "resultados"
            config = self._config_temporaria(results_dir)
            bancada = mestre.Bancada(mestre.AmetekMX30(simulated=True), None, config)

            resultados = bancada.executar_bateria([ok_script, bad_script, ok_script])

            self.assertEqual([resultado.ok for resultado in resultados], [True, False, True])
            self.assertEqual(resultados[1].id, "02")
            self.assertIn("falha proposital", resultados[1].motivo)
            # Caminho SIMULADO: um único .npz por classe com as
            # sim_captures_per_class=2 capturas empilhadas.
            self.assertTrue((results_dir / "01_ok.npz").exists())
            with np.load(results_dir / "01_ok.npz", allow_pickle=True) as dados:
                self.assertEqual(dados["literatura/medida"].shape, (2, 6_000))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_falha_intermitente_passa_no_retry_e_falha_persistente_esgota_tentativas(self):
        """Rede de segurança grosseira para falhas de INSTRUMENTO intermitentes
        (ex.: -113/-300 esporádicos observados na bancada mesmo com *WAI/
        assert_no_errors já no lugar certo): até MAX_TENTATIVAS_POR_CLASSE
        tentativas antes de marcar FALHOU de vez."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            intermitente = tmp_dir / "01.py"
            intermitente.write_text(
                "import numpy as np\n"
                "from mestre import ExperimentoWaveform\n"
                "class Experimento(ExperimentoWaveform):\n"
                "    id = '01'\n"
                "    nome = 'INTERMITENTE'\n"
                "    tentativas = 0\n"
                "    def gerar(self, t, f0, capture_index, rng):\n"
                "        type(self).tentativas += 1\n"
                "        if type(self).tentativas < 3:\n"
                "            raise RuntimeError(f'falha na tentativa {type(self).tentativas}')\n"
                "        return np.sin(2.0 * np.pi * f0 * t), {}\n",
                encoding="utf-8",
            )
            persistente = tmp_dir / "02.py"
            persistente.write_text(
                "from mestre import ExperimentoWaveform\n"
                "class Experimento(ExperimentoWaveform):\n"
                "    id = '02'\n"
                "    nome = 'PERSISTENTE'\n"
                "    tentativas = 0\n"
                "    def gerar(self, t, f0, capture_index, rng):\n"
                "        type(self).tentativas += 1\n"
                "        raise RuntimeError(f'sempre falha (tentativa {type(self).tentativas})')\n",
                encoding="utf-8",
            )
            config = self._config_temporaria(tmp_dir / "resultados")
            bancada = mestre.Bancada(mestre.AmetekMX30(simulated=True), None, config)

            resultados = bancada.executar_bateria([intermitente, persistente])

            self.assertTrue(resultados[0].ok, "deveria ter passado na 3ª tentativa")
            self.assertFalse(resultados[1].ok)
            self.assertIn("tentativa 3", resultados[1].motivo)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_falha_de_comunicacao_aborta_a_bateria_inteira(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            bad_script = tmp_dir / "02.py"
            bad_script.write_text(
                "from mestre import ExperimentoWaveform\n"
                "from ametek_orm import CommunicationError\n"
                "class Experimento(ExperimentoWaveform):\n"
                "    id = '02'\n"
                "    nome = 'RUIM'\n"
                "    def gerar(self, t, f0, capture_index, rng):\n"
                "        raise CommunicationError('porta serial caiu')\n",
                encoding="utf-8",
            )
            never_reached = tmp_dir / "03.py"
            never_reached.write_text(
                "import numpy as np\n"
                "from mestre import ExperimentoWaveform\n"
                "class Experimento(ExperimentoWaveform):\n"
                "    id = '03'\n"
                "    nome = 'NUNCA'\n"
                "    def gerar(self, t, f0, capture_index, rng):\n"
                "        return np.sin(2.0 * np.pi * f0 * t), {}\n",
                encoding="utf-8",
            )
            config = self._config_temporaria(tmp_dir / "resultados")
            bancada = mestre.Bancada(mestre.AmetekMX30(simulated=True), None, config)

            with self.assertRaises(CommunicationError):
                bancada.executar_bateria([bad_script, never_reached])

            self.assertFalse((tmp_dir / "resultados" / "03_nunca.npz").exists())
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_assegurar_tensao_base_faz_step_real_para_a_tensao_base(self):
        """Regressão de bancada: `run 02` isolado (CLI, nova conexão, sem
        01/NORMAL antes) media ~0V antes/depois do pulso SAG em vez de
        BASE_VOLTAGE_RMS. Causa: configure_safe_baseline() deixa a tensão
        IMEDIATA em 0V por segurança; trigger_pulse() (usado por SAG/SWELL/
        INTERRUPTION) nunca eleva essa tensão sozinho, só programa o nível
        TRANSIENTE. assegurar_tensao_base() faz o mesmo STEP que 01/NORMAL
        faria, sticky, antes de rodar uma classe isolada."""
        config = self._config_temporaria(Path(tempfile.mkdtemp()))
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=200.0, max_peak_v=400.0)
        bancada = mestre.Bancada(fonte, object(), config)  # osc não-None: simula bancada real

        bancada.assegurar_tensao_base()

        commands = "\n".join(fonte.command_log).upper()
        self.assertIn(f"VOLTAGE:TRIGGERED {config.base_voltage_rms:.8g}".upper(), commands)
        self.assertIn("VOLTAGE:MODE STEP", commands)
        self.assertIn("*TRG", fonte.command_log)

    def test_recuperar_estado_seguro_no_op_em_modo_simulado(self):
        config = self._config_temporaria(Path(tempfile.mkdtemp()))
        bancada = mestre.Bancada(mestre.AmetekMX30(simulated=True), None, config)
        bancada.recuperar_estado_seguro()  # osc is None: não deve levantar nada

    def test_recuperar_estado_seguro_nao_falha_so_porque_restaurar_forma_falhou(self):
        """Regressão de bancada: recuperar_estado_seguro() chamava
        restaurar_forma_e_modo_padrao() sem isolar sua falha — se essa MESMA
        operação já tinha acabado de falhar dentro da classe que estamos
        recuperando, ela falharia de novo do mesmo jeito, virando
        FalhaFatalDeInstrumento e abortando a bateria por um motivo que não
        era de infraestrutura real. Uma falha isolada aí não deve ser fatal
        se a confirmação final (tensão de volta à base, fila de erros limpa)
        ainda for bem-sucedida."""
        config = self._config_temporaria(Path(tempfile.mkdtemp()))
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=200.0, max_peak_v=400.0)
        bancada = mestre.Bancada(fonte, object(), config)

        def restaurar_quebrado():
            raise InstrumentHardwareError("AMETEK rejeitou SOURce:FUNCtion:SHAPe SINusoid")

        fonte.restaurar_forma_e_modo_padrao = restaurar_quebrado
        bancada.recuperar_estado_seguro()  # não deve levantar

    def test_recuperar_estado_seguro_levanta_falha_fatal_quando_fonte_nao_responde(self):
        config = self._config_temporaria(Path(tempfile.mkdtemp()))
        fonte = mestre.AmetekMX30(simulated=True)
        bancada = mestre.Bancada(fonte, object(), config)  # osc não-None: simula bancada real

        def write_quebrado(command):
            raise mestre.CommunicationError("porta caiu")

        fonte.write = write_quebrado
        with self.assertRaises(mestre.FalhaFatalDeInstrumento):
            bancada.recuperar_estado_seguro()


class ConfigCoberturaTests(unittest.TestCase):
    def _config(self, **overrides):
        base = dict(
            fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(30.0,), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=Path("."),
            sim_captures_per_class=2, real_captures_per_class=1, disturbance_start_s=0.06,
        )
        base.update(overrides)
        return mestre.Config(**base)

    def test_capturas_override_ausente_mantem_real_captures_per_class(self):
        config = self._config()
        self.assertEqual(config.capturas(simulated=False), 1)

    def test_capturas_override_presente_vence_real_captures_per_class(self):
        config = self._config(capturas_override=5)
        self.assertEqual(config.capturas(simulated=False), 5)

    def test_capturas_override_nao_afeta_modo_simulado(self):
        config = self._config(capturas_override=5)
        self.assertEqual(config.capturas(simulated=True), 2)

    def test_defaults_reproduzem_config_de_hoje(self):
        config = self._config()
        self.assertIsNone(config.capturas_override)
        self.assertFalse(config.diagnostico_mode)


class TotalNiveisTests(unittest.TestCase):
    def test_classe_sem_niveis_retorna_1(self):
        experimento = _BancadaFake.experimento_sem_niveis()
        self.assertEqual(experimento.total_niveis(), 1)

    def test_classe_com_niveis_retorna_o_tamanho_da_tupla(self):
        experimento = _BancadaFake.experimento_com_niveis()
        self.assertEqual(experimento.total_niveis(), 5)


class RemapeamentoNivelTests(unittest.TestCase):
    """Nota (P04): a fonte fake destes testes passou a ser criada com
    ``max_voltage_rms=300`` — o teto REAL do manual ([AM] §4.14, p. 84) — em
    vez do default de comissionamento de 10 Vrms. Com base de 127 V e níveis
    de 0,1 a 0,9 pu, o default antigo descrevia uma bancada fisicamente
    impossível (12,7 V pedidos contra um teto de 10 V) que só passava porque
    ninguém validava os níveis antes de capturar. As asserções destes testes
    (quais capture_index o laço visita) continuam exatamente as mesmas."""

    def _config(self, results_dir, **overrides):
        base = dict(
            fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=results_dir,
            sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
        )
        base.update(overrides)
        return mestre.Config(**base)

    def test_sem_capturas_override_roda_so_1_capturas_nivel_0(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados")
            fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
            bancada = mestre.Bancada(fonte, mock.Mock(), config)
            niveis_vistos = []

            class _ComNiveis(mestre.ExperimentoNativo):
                id = "97"
                nome = "TESTE_NIVEIS"
                NIVEIS = (0.1, 0.3, 0.5, 0.7, 0.9)
                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {"nivel": self.NIVEIS[capture_index % 5]}
                def configurar(self, capture_index):
                    niveis_vistos.append(self.NIVEIS[capture_index % 5])
                    return {"nivel": self.NIVEIS[capture_index % 5]}

            experimento = _ComNiveis(bancada)
            experimento.osc = mock.Mock()  # simulated=False via osc não-None
            self._forcar_captura_real_stub(experimento)
            experimento.executar()

            self.assertEqual(niveis_vistos, [0.1])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_com_capturas_override_3_agrupa_3_por_nivel(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados", capturas_override=3)
            fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
            bancada = mestre.Bancada(fonte, mock.Mock(), config)
            niveis_vistos = []

            class _ComNiveis(mestre.ExperimentoNativo):
                id = "97"
                nome = "TESTE_NIVEIS"
                NIVEIS = (0.1, 0.3, 0.5, 0.7, 0.9)
                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {"nivel": self.NIVEIS[capture_index % 5]}
                def configurar(self, capture_index):
                    niveis_vistos.append(self.NIVEIS[capture_index % 5])
                    return {"nivel": self.NIVEIS[capture_index % 5]}

            experimento = _ComNiveis(bancada)
            experimento.osc = mock.Mock()
            self._forcar_captura_real_stub(experimento)
            experimento.executar()

            self.assertEqual(
                niveis_vistos,
                [0.1, 0.1, 0.1, 0.3, 0.3, 0.3, 0.5, 0.5, 0.5, 0.7, 0.7, 0.7, 0.9, 0.9, 0.9],
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_nivel_indice_registra_capture_index_real_mesmo_sem_niveis_discretos(self):
        """Task 9 (analisar_sessao.py) expôs que classes SEM NIVEIS (04/06/08/09/19,
        18) nunca agrupam por nível (niveis_count sempre 1), então
        cobertura_por_nivel_ativa é sempre False para elas e o nivel_indice
        gravado ficava sempre 0 mesmo com `set capturas N>1` ativo — apesar de
        _capturar_real(capture_index, ...) (linha ~880) sempre receber o
        capture_index real. mestre.py:908 agora grava capture_index também
        quando `not simulated`, não só quando agrupado por nível."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados", capturas_override=3)
            # Limites coerentes com 127 V de base (o padrão do simulador, 100 Vp,
            # fica abaixo do pico nominal e a pré-validação de pico pularia tudo).
            bancada = mestre.Bancada(
                mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0),
                mock.Mock(), config,
            )

            class _SemNiveis(mestre.ExperimentoNativo):
                id = "95"
                nome = "TESTE_SEM_NIVEIS"

                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {}

                def configurar(self, capture_index):
                    return {}

            experimento = _SemNiveis(bancada)
            experimento.osc = mock.Mock()  # simulated=False via osc não-None
            self._forcar_captura_real_stub(experimento)
            experimento.executar()

            metadata_path = config.results_dir / "metadata" / "95_teste_sem_niveis.jsonl"
            registros = [
                json.loads(linha) for linha in metadata_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual([registro["nivel_indice"] for registro in registros], [0, 1, 2])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @staticmethod
    def _forcar_captura_real_stub(experimento):
        """Substitui _capturar_real por um stub que devolve uma captura
        válida sem tocar osciloscópio/fonte de verdade — só precisamos
        observar QUAL capture_index cada chamada recebeu."""
        experimento._calcular_margem = lambda **kw: (0, 0, kw["config_points"])
        pontos = experimento.config.points
        tempo_s = np.arange(pontos, dtype=np.float64) / experimento.config.fs_hz
        def _stub(capture_index, t, rng):
            parametros = experimento.configurar(capture_index)
            return tempo_s, np.sin(2.0 * np.pi * 60.0 * tempo_s), None, parametros
        experimento._capturar_real = _stub
        experimento._preparar_acquisicao_real = lambda: None


class SalvarClasseArquivoUnicoTests(unittest.TestCase):
    """Bancada real: as capturas de uma classe vão para UM ``NN_classe.npz``
    (formato 2, ``sessao_io``), não mais para um arquivo por captura."""

    @staticmethod
    def _config(tmp_dir, **sobrescritas):
        base = dict(
            fs_hz=30_000.0, points=4, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=tmp_dir,
            sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
        )
        base.update(sobrescritas)
        return mestre.Config(**base)

    @staticmethod
    def _experimento(config, id_="02", nome="SAG"):
        class _Concreta(mestre.ExperimentoWaveform):
            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

        _Concreta.id, _Concreta.nome = id_, nome
        return _Concreta(mock.Mock(config=config, fonte=None, osc=None))

    @staticmethod
    def _metadado(indice, **parametros):
        return {"id_captura": f"02-{indice + 1:04d}", "classe": "SAG", "nivel_indice": indice,
                "parametros": parametros, "seed": indice + 1, "simulado": False,
                "fs_hz": 30000.0, "pontos": 4, "snr_medido_db": {}}

    def test_grava_um_unico_npz_por_classe_e_indexa_no_metadata(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            experimento = self._experimento(self._config(tmp_dir))
            tensao = np.arange(8, dtype=np.float64).reshape(2, 4)
            experimento._salvar_classe(
                tempo_ms=np.zeros(4), tensao_limpa=tensao, tensao_por_snr={},
                ids=["02-0001", "02-0002"], corrente=None,
                metadados=[self._metadado(0, sag_pu=0.1), self._metadado(1, sag_pu=0.3)],
                simulated=False,
            )
            self.assertEqual(sorted(p.name for p in tmp_dir.glob("*.npz")), ["02_sag.npz"])
            with np.load(tmp_dir / "02_sag.npz") as dados:
                np.testing.assert_array_equal(dados["literatura/medida"], tensao)
                self.assertEqual(list(dados["literatura/id_captura"]), ["02-0001", "02-0002"])
            linhas = [json.loads(l) for l in (tmp_dir / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([l["arquivo_classe"] for l in linhas], ["02_sag.npz", "02_sag.npz"])
            self.assertEqual([l["indice_no_arquivo"] for l in linhas], [0, 1])
            self.assertEqual([l["perfil"] for l in linhas], ["literatura", "literatura"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_classe_sem_parametro_nomeavel_tambem_vai_para_o_arquivo_da_classe(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            experimento = self._experimento(self._config(tmp_dir), "01", "NORMAL")
            md = self._metadado(0)
            md.update(id_captura="01-0001", classe="NORMAL")
            experimento._salvar_classe(
                tempo_ms=np.zeros(4), tensao_limpa=np.zeros((1, 4)), tensao_por_snr={},
                ids=["01-0001"], corrente=None, metadados=[md], simulated=False,
            )
            self.assertEqual(sorted(p.name for p in tmp_dir.glob("*.npz")), ["01_normal.npz"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_rodada_nova_da_mesma_classe_substitui_a_anterior_em_todos_os_arquivos(self):
        """Uma classe rodada de novo (mesmo perfil) não deixa nada da rodada
        anterior: nem no .npz da classe, nem em snr_XXdb/, nem em corrente/,
        nem no metadata (nunca houve órfãos no formato 2: o nome é fixo)."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir, snr_levels_db=(30.0,), capture_current=True, current_base_a=1.0)
            experimento = self._experimento(config)
            experimento._salvar_classe(
                tempo_ms=np.zeros(4), tensao_limpa=np.zeros((2, 4)),
                tensao_por_snr={30.0: np.zeros((2, 4))}, ids=["02-0001", "02-0002"],
                corrente=np.zeros((2, 4)),
                metadados=[self._metadado(0, sag_pu=0.1), self._metadado(1, sag_pu=0.3)],
                simulated=False,
            )
            experimento._salvar_classe(
                tempo_ms=np.zeros(4), tensao_limpa=np.ones((1, 4)),
                tensao_por_snr={30.0: np.ones((1, 4)) * 2}, ids=["02-0003"],
                corrente=np.ones((1, 4)) * 3,
                metadados=[self._metadado(2, sag_pu=0.5)], simulated=False,
            )
            self.assertEqual(sorted(p.name for p in tmp_dir.glob("*.npz")), ["02_sag.npz"])
            with np.load(tmp_dir / "02_sag.npz") as dados:
                self.assertEqual(list(dados["literatura/id_captura"]), ["02-0003"])
                np.testing.assert_array_equal(dados["literatura/medida"], np.ones((1, 4)))
            with np.load(tmp_dir / "snr_30db" / "02_sag.npz") as dados:
                np.testing.assert_array_equal(dados["literatura/tensao_pu"], np.ones((1, 4)) * 2)
            with np.load(tmp_dir / "corrente" / "02_sag_corrente.npz") as dados:
                np.testing.assert_array_equal(dados["literatura/corrente_pu"], np.ones((1, 4)) * 3)
            linhas = (tmp_dir / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(linhas), 1)
            self.assertIn("02-0003", linhas[0])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_capturas_reais_com_mesmo_parametro_ficam_todas_no_arquivo_da_classe(self):
        """`set capturas 5` agrupa N capturas FÍSICAS no mesmo nível (mesmo
        `parametros`): no formato antigo exigiam sufixos `_02`, `_03` para não
        se sobrescreverem; no formato 2 são linhas do mesmo array, na ordem."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir, snr_levels_db=(30.0,), capture_current=True, current_base_a=1.0)
            experimento = self._experimento(config)
            niveis = [0.1, 0.1, 0.1, 0.3, 0.3]
            tensao = np.arange(5 * 4, dtype=np.float64).reshape(5, 4)
            experimento._salvar_classe(
                tempo_ms=np.zeros(4), tensao_limpa=tensao, tensao_por_snr={30.0: tensao + 100.0},
                ids=[f"02-{i + 1:04d}" for i in range(5)], corrente=tensao + 1000.0,
                metadados=[self._metadado(i, sag_pu=n) for i, n in enumerate(niveis)],
                simulated=False,
            )
            self.assertEqual(sorted(p.name for p in tmp_dir.glob("*.npz")), ["02_sag.npz"])
            self.assertEqual(sorted(p.name for p in (tmp_dir / "snr_30db").glob("*.npz")), ["02_sag.npz"])
            self.assertEqual(sorted(p.name for p in (tmp_dir / "corrente").glob("*.npz")), ["02_sag_corrente.npz"])
            with np.load(tmp_dir / "02_sag.npz") as dados:
                np.testing.assert_array_equal(dados["literatura/medida"], tensao)
                self.assertEqual(list(dados["literatura/id_captura"]), [f"02-{i + 1:04d}" for i in range(5)])
            with np.load(tmp_dir / "snr_30db" / "02_sag.npz") as dados:
                np.testing.assert_array_equal(dados["literatura/tensao_pu"], tensao + 100.0)
            linhas = (tmp_dir / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(linhas), 5)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class SalvarClasseSimuladoTests(unittest.TestCase):
    """O dataset SIMULADO grava UM ``NN_classe.npz`` (formato 2): as chaves
    ``<perfil>/medida|modelo|programada`` empilhadas ``(N, pontos)``; SNRs em
    ``snr_XXdb/NN_classe.npz``; corrente em ``corrente/``."""

    def _config(self, results_dir, **overrides):
        base = dict(
            fs_hz=30_000.0, points=4, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(30.0,), base_seed=1,
            capture_current=True, current_base_a=1.0, results_dir=results_dir,
            sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
        )
        base.update(overrides)
        return mestre.Config(**base)

    @staticmethod
    def _experimento(config):
        class _Concreta(mestre.ExperimentoWaveform):
            id = "02"
            nome = "SAG"

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

        return _Concreta(mock.Mock(config=config, fonte=None, osc=None))

    def test_simulado_grava_um_unico_npz_por_classe_com_capturas_empilhadas(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir)
            experimento = self._experimento(config)
            tensao = np.arange(3 * 4, dtype=np.float64).reshape(3, 4)
            ids = ["02-0001", "02-0002", "02-0003"]
            experimento._salvar_classe(
                tempo_ms=np.zeros(4),
                tensao_limpa=tensao,
                tensao_por_snr={30.0: tensao + 100.0},
                ids=ids,
                corrente=tensao + 1000.0,
                metadados=[
                    {"id_captura": id_captura, "classe": "SAG", "nivel_indice": 0,
                     "parametros": {"sag_pu": 0.1}, "seed": indice, "simulado": True,
                     "fs_hz": 30000.0, "pontos": 4, "snr_medido_db": {}}
                    for indice, id_captura in enumerate(ids)
                ],
                simulated=True,
            )

            self.assertEqual(sorted(p.name for p in tmp_dir.glob("*.npz")), ["02_sag.npz"])
            self.assertEqual(
                sorted(p.name for p in (tmp_dir / "snr_30db").glob("*.npz")), ["02_sag.npz"],
            )
            self.assertEqual(
                sorted(p.name for p in (tmp_dir / "corrente").glob("*.npz")), ["02_sag_corrente.npz"],
            )

            with np.load(tmp_dir / "02_sag.npz", allow_pickle=True) as dados:
                self.assertEqual(dados["literatura/medida"].shape, (3, 4))
                np.testing.assert_array_equal(dados["literatura/medida"], tensao)
                self.assertEqual(list(dados["literatura/id_captura"]), ids)
                self.assertEqual(str(dados["classe"]), "SAG")
            with np.load(tmp_dir / "snr_30db" / "02_sag.npz", allow_pickle=True) as dados:
                np.testing.assert_array_equal(dados["literatura/tensao_pu"], tensao + 100.0)
            with np.load(tmp_dir / "corrente" / "02_sag_corrente.npz", allow_pickle=True) as dados:
                np.testing.assert_array_equal(dados["literatura/corrente_pu"], tensao + 1000.0)

            linhas = (tmp_dir / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(linhas), 3)
            self.assertEqual([json.loads(linha)["id_captura"] for linha in linhas], ids)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_simulado_nao_perde_capturas_com_parametros_repetidos(self):
        """O caso real: 02/03/05 ciclam `capture_index % 5` entre 5 níveis,
        então 12 capturas simuladas geram só 5 rótulos distintos. No formato
        empilhado nada colide — as 12 continuam no array."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir, snr_levels_db=(), capture_current=False,
                                  current_base_a=None)
            experimento = self._experimento(config)
            niveis = (0.1, 0.3, 0.5, 0.7, 0.9)
            total = 12
            tensao = np.arange(total * 4, dtype=np.float64).reshape(total, 4)
            ids = [f"02-{indice + 1:04d}" for indice in range(total)]
            experimento._salvar_classe(
                tempo_ms=np.zeros(4), tensao_limpa=tensao, tensao_por_snr={}, ids=ids,
                corrente=None,
                metadados=[
                    {"id_captura": ids[indice], "classe": "SAG", "nivel_indice": 0,
                     "parametros": {"sag_pu": niveis[indice % 5]}, "seed": indice,
                     "simulado": True, "fs_hz": 30000.0, "pontos": 4, "snr_medido_db": {}}
                    for indice in range(total)
                ],
                simulated=True,
            )

            self.assertEqual(sorted(p.name for p in tmp_dir.glob("*.npz")), ["02_sag.npz"])
            with np.load(tmp_dir / "02_sag.npz", allow_pickle=True) as dados:
                self.assertEqual(dados["literatura/medida"].shape, (total, 4))
                np.testing.assert_array_equal(dados["literatura/medida"], tensao)
                self.assertEqual(list(dados["literatura/id_captura"]), ids)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_executar_simulado_grava_arquivo_unico_com_todas_as_capturas(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados", points=6_000,
                                  sim_captures_per_class=4, snr_levels_db=(),
                                  capture_current=False, current_base_a=None)
            bancada = mestre.Bancada(mestre.AmetekMX30(simulated=True), None, config)

            class _ComNiveis(mestre.ExperimentoWaveform):
                id = "02"
                nome = "SAG"
                NIVEIS = (0.1, 0.3, 0.5, 0.7, 0.9)

                def gerar(self, t, f0, capture_index, rng):
                    nivel = self.NIVEIS[capture_index % 5]
                    return (1.0 - nivel) * np.sin(2.0 * np.pi * f0 * t), {"sag_pu": nivel}

            _ComNiveis(bancada).executar()

            resultados = config.results_dir
            self.assertEqual(sorted(p.name for p in resultados.glob("*.npz")), ["02_sag.npz"])
            with np.load(resultados / "02_sag.npz", allow_pickle=True) as dados:
                self.assertEqual(dados["literatura/medida"].shape, (4, 6_000))
                self.assertEqual(
                    list(dados["literatura/id_captura"]),
                    ["02-0001", "02-0002", "02-0003", "02-0004"],
                )
            linhas = (resultados / "metadata" / "02_sag.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(linhas), 4)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class CoberturaParametroContinuoTests(unittest.TestCase):
    def _carregar(self, relative_path):
        script_path = PROJECT_ROOT / relative_path
        spec = importlib.util.spec_from_file_location("teste_cobertura", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(script_path.parent))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.remove(str(script_path.parent))
        return module.Experimento

    def _config(self, capturas_override=None):
        return mestre.Config(
            fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=Path("."),
            sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
            capturas_override=capturas_override,
        )

    def test_04_interruption_sem_override_sorteia(self):
        cls = self._carregar("experimentos_nativos/04.py")
        instancia = cls.__new__(cls)
        instancia.config = self._config(capturas_override=None)
        instancia.osc = mock.Mock()  # not simulated
        t = np.arange(6000) / 30000.0
        _, parametros_a = instancia.gerar(t, 60.0, 0, np.random.default_rng(1))
        _, parametros_b = instancia.gerar(t, 60.0, 0, np.random.default_rng(2))
        self.assertNotEqual(parametros_a["interruption_pu"], parametros_b["interruption_pu"])

    def test_04_interruption_com_override_cobre_intervalo(self):
        cls = self._carregar("experimentos_nativos/04.py")
        instancia = cls.__new__(cls)
        instancia.config = self._config(capturas_override=3)
        instancia.osc = mock.Mock()
        t = np.arange(6000) / 30000.0
        niveis = [
            instancia.gerar(t, 60.0, indice, np.random.default_rng(indice))[1]["interruption_pu"]
            for indice in range(3)
        ]
        self.assertAlmostEqual(niveis[0], 0.0)
        self.assertAlmostEqual(niveis[-1], 0.09)

    def test_04_interruption_simulado_ignora_override(self):
        cls = self._carregar("experimentos_nativos/04.py")
        instancia = cls.__new__(cls)
        instancia.config = self._config(capturas_override=3)
        instancia.osc = None  # simulado
        t = np.arange(6000) / 30000.0
        primeiro = instancia.gerar(t, 60.0, 0, np.random.default_rng(1))[1]["interruption_pu"]
        segundo = instancia.gerar(t, 60.0, 0, np.random.default_rng(7))[1]["interruption_pu"]
        self.assertNotEqual(primeiro, segundo)  # continua sorteio, override não se aplica

    def test_08_transient_com_override_usa_pico_fisico_nao_a_spec(self):
        cls = self._carregar("experimentos_waveform/08.py")
        instancia = cls.__new__(cls)
        instancia.config = self._config(capturas_override=3)
        instancia.osc = mock.Mock()
        instancia.fonte = mestre.AmetekMX30(simulated=True)
        instancia.fonte.max_peak_v = 200.0  # limite_pico_bancada_pu() = 0.9*200/(127*sqrt2) ~ 0.79
        t = np.arange(6000) / 30000.0
        amplitudes = [
            instancia.gerar(t, 60.0, indice, np.random.default_rng(indice))[1]["transient_amplitude_pu"]
            for indice in range(3)
        ]
        limite_pico_pu = instancia.limite_pico_bancada_pu()
        self.assertAlmostEqual(amplitudes[0], 1.2 - 1.0)
        self.assertAlmostEqual(amplitudes[-1], limite_pico_pu - 1.0)


class MargemCapturaTests(unittest.TestCase):
    """ADAPTADO em P10 (não enfraquecido, 2026-09-22): a margem deixou de ser
    opt-in — ``_calcular_margem`` trocou o parâmetro ``margin_mode: bool``
    (toggle ligado/desligado por ``set margin on|off``) por
    ``captura_fisica: bool`` (é captura real ou dataset simulado?). As
    asserções continuam as mesmas em natureza (simulado = janela nominal,
    sem folga; captura real = folga dos dois lados, dentro dos dois tetos do
    osciloscópio, SEMPRE — não há mais 'desligado' para captura real); os
    NÚMEROS (20/50 ms) já vinham do P08 e não mudam aqui. Justificativa
    completa em `arquivo/analises:docs/analise-2026-09-21/03_propostas_melhorias.md`
    (item P1-2) e na decisão de projeto de 2026-09-22 (descontinuar
    `set margin on|off`; a janela pequena passa a ser o padrão)."""

    def test_simulado_mantem_pontos_nominais_sem_margem(self):
        antes, depois, pontos_totais = mestre.ExperimentoBase._calcular_margem(
            captura_fisica=False, config_points=6000, fs_hz=30_000.0,
        )
        self.assertEqual((antes, depois), (0, 0))
        self.assertEqual(pontos_totais, 6000)

    def test_captura_fisica_sempre_adiciona_amostras_de_cada_lado(self):
        antes, depois, pontos_totais = mestre.ExperimentoBase._calcular_margem(
            captura_fisica=True, config_points=6000, fs_hz=30_000.0,
        )
        self.assertEqual(antes, 600)    # 20 ms * 30 kSa/s
        self.assertEqual(depois, 1_500)  # 50 ms * 30 kSa/s
        self.assertEqual(pontos_totais, 6000 + 600 + 1_500)

    def test_margem_cobre_o_fim_de_evento_mais_tardio_ja_medido(self):
        """O conteúdo programado termina em trigger+200 ms e o fim de evento
        mais tardio medido nas duas sessões é 116,7 ms (relatório 01 §2(i)).
        A janela precisa conter os 200 ms nominais E a folga de retorno ao
        regime."""
        _, depois, pontos_totais = mestre.ExperimentoBase._calcular_margem(
            captura_fisica=True, config_points=6000, fs_hz=30_000.0,
        )
        self.assertGreaterEqual(6000 + depois, int(0.250 * 30_000))
        self.assertEqual(pontos_totais / 30_000.0, 0.270)

    def test_captura_fisica_fica_dentro_do_teto_de_pontos_do_osciloscopio(self):
        # oscilloscope_orm.py fixa ":WAVeform:POINts 60000" tanto em
        # configure_acquisition() quanto em get_waveform() — um pontos_totais
        # acima disso faria a preamble real declarar menos pontos do que
        # pedido, e get_waveform() levantaria OscilloscopeError na próxima
        # sessão física (CHANGELOG/v1.9.md).
        *_, pontos_totais = mestre.ExperimentoBase._calcular_margem(
            captura_fisica=True, config_points=6000, fs_hz=30_000.0,
        )
        self.assertLess(pontos_totais, 60_000)

    def test_captura_fisica_fica_com_folga_do_teto_real_do_modo_auto(self):
        # CHANGELOG/v1.10.md: uma aquisição SINGLE real em modo AUTO entrega
        # só ~32,3-32,7 mil pontos reais, quase independente da janela
        # pedida (medido: 32258/32258/32653/32432 pontos para janelas de
        # 0.2/0.25/0.8/1.2s) -- MUITO abaixo do teto teórico de 60000 do
        # :WAVeform:POINts acima. É esse teto REAL, não o teórico, que
        # limita quanto pontos_totais pode pedir; 30000 fica com ~2258
        # pontos (~7,5%) de folga sobre o pior caso já medido.
        *_, pontos_totais = mestre.ExperimentoBase._calcular_margem(
            captura_fisica=True, config_points=6000, fs_hz=30_000.0,
        )
        self.assertLessEqual(pontos_totais, 30_000)

    def test_nao_ha_mais_modo_sem_margem_para_captura_fisica(self):
        """Decisão de projeto, 2026-09-22: descontinuar 'set margin on|off' e
        tornar a janela pequena o default — não pode sobrar nenhum jeito de
        pedir 'captura real sem margem' pela assinatura da função."""
        import inspect
        assinatura = inspect.signature(mestre.ExperimentoBase._calcular_margem)
        self.assertNotIn("margin_mode", assinatura.parameters)
        self.assertIn("captura_fisica", assinatura.parameters)

    def test_validar_captura_aceita_pontos_extras_quando_esperado_explicito(self):
        config = mestre.Config(
            fs_hz=30_000.0, points=6000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=Path("."),
            sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
        )
        class _ExperimentoWaveformConcreto(mestre.ExperimentoWaveform):
            def gerar(self, t, f0, capture_index, rng):
                raise NotImplementedError

        experimento = _ExperimentoWaveformConcreto.__new__(_ExperimentoWaveformConcreto)
        experimento.config = config
        pontos_totais = 7500
        tempo_s = np.arange(pontos_totais) / 30_000.0
        experimento._validar_captura(tempo_s, np.zeros(pontos_totais), pontos_esperados=pontos_totais)  # não levanta


class AnalisarSessaoTests(unittest.TestCase):
    def test_analisar_offset_detecta_deslocamento_conhecido(self):
        import analisar_sessao
        fs_hz = 30_000.0
        t = np.arange(6000) / fs_hz
        esperado = np.sin(2.0 * np.pi * 60.0 * t)
        # 200 amostras (<1 período de 500 amostras a 60 Hz/30 kSa/s), não 599:
        # uma senoide pura de 60 Hz é exatamente periódica a cada 500 amostras
        # dentro do array de 6000, então qualquer deslocamento >= meio período
        # é matematicamente ambíguo com seu equivalente mod-500 (roll(x,599) é
        # bit-a-bit idêntico a roll(x,99) para esta senoide) — nenhuma técnica
        # de cross-correlação consegue distinguir os dois só a partir dos
        # dados. 200 evita essa ambiguidade e cai fora da faixa onde a curva
        # de correlação desta senoide pura fica quase simétrica ao redor do
        # pico (empiricamente, várias amostras entre ~60 e ~190 dão erro de
        # +-1 amostra por essa quase-simetria; 200 tem margem clara).
        deslocamento_amostras = 200
        capturado = np.roll(esperado, deslocamento_amostras)
        lag, corr = analisar_sessao.analisar_offset(esperado, capturado, fs_hz)
        self.assertEqual(lag, deslocamento_amostras)
        self.assertGreater(corr, 0.9)

    def test_analisar_sessao_gera_relatorio_para_uma_pasta(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            sessao_dir = tmp_dir / "sessao_teste"
            (sessao_dir / "metadata").mkdir(parents=True)
            fs_hz = 30_000.0
            pontos = 6000
            t = np.arange(pontos) / fs_hz
            captura = np.sin(2.0 * np.pi * 60.0 * t)
            np.savez(
                sessao_dir / "01_normal_cap01.npz", tempo_ms=t * 1000.0,
                tensao_pu=captura.reshape(1, -1), classe="NORMAL",
                id_captura=np.array(["01-0001"], dtype=object),
            )
            (sessao_dir / "metadata" / "01_normal.jsonl").write_text(
                json.dumps({"classe": "NORMAL", "fs_hz": fs_hz, "id_captura": "01-0001",
                            "parametros": {}, "pontos": pontos, "seed": 21260827, "simulado": False}) + "\n",
                encoding="utf-8",
            )
            import analisar_sessao
            relatorio = analisar_sessao.analisar_sessao(sessao_dir)
            self.assertEqual(len(relatorio), 1)
            self.assertEqual(relatorio[0]["classe"], "01_normal_cap01")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_analisar_sessao_relata_erro_para_npz_simulado_empilhado(self):
        # Formato simulado (_salvar_classe_simulada em mestre.py): um único
        # .npz por classe com tensao_pu empilhado (N, pontos) e um id_captura
        # por linha — em vez do formato real (1 .npz por captura, sempre 1
        # linha). analisar_sessao() deve reconhecer isso e reportar um erro
        # claro por arquivo, nunca analisar silenciosamente só a linha 0 como
        # se fosse a captura inteira da classe.
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            sessao_dir = tmp_dir / "sessao_teste"
            (sessao_dir / "metadata").mkdir(parents=True)
            fs_hz = 30_000.0
            pontos = 6000
            t = np.arange(pontos) / fs_hz
            n_capturas = 3
            capturas = np.stack([np.sin(2.0 * np.pi * 60.0 * t) for _ in range(n_capturas)])
            ids = np.array([f"01-{i + 1:04d}" for i in range(n_capturas)], dtype=object)
            np.savez(
                sessao_dir / "01_normal.npz", tempo_ms=t * 1000.0,
                tensao_pu=capturas, classe="NORMAL", id_captura=ids,
            )
            with (sessao_dir / "metadata" / "01_normal.jsonl").open("w", encoding="utf-8") as handle:
                for i in range(n_capturas):
                    handle.write(json.dumps({
                        "classe": "NORMAL", "fs_hz": fs_hz, "id_captura": f"01-{i + 1:04d}",
                        "parametros": {}, "pontos": pontos, "seed": 21260827, "simulado": True,
                    }) + "\n")
            import analisar_sessao
            relatorio = analisar_sessao.analisar_sessao(sessao_dir)
            self.assertEqual(len(relatorio), 1)
            self.assertEqual(relatorio[0]["classe"], "01_normal")
            self.assertIn("erro", relatorio[0])
            self.assertNotIn("lag_amostras", relatorio[0])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class CorrelacaoDisturbioTests(unittest.TestCase):
    FS_HZ = 30_000.0
    F0_HZ = 60.0

    def _t(self):
        return np.arange(6000) / self.FS_HZ

    def _senoide(self, fase_graus=0.0):
        return np.sin(2.0 * np.pi * self.F0_HZ * self._t() + np.radians(fase_graus))

    def _disturbio(self):
        # pulso de 1 ms + oscilação amortecida: resíduo sem simetria nem média nula
        t = self._t()
        pulso = np.where((t > 0.05) & (t < 0.051), 0.8, 0.0)
        osc = 0.3 * np.exp(-(t - 0.1).clip(0) / 0.01) * np.sin(2 * np.pi * 900 * t) * (t >= 0.1)
        return pulso + osc

    def _corr(self, esperado, capturado, fase_graus=0.0):
        return sinais.correlacao_disturbio(
            esperado, capturado, fs_hz=self.FS_HZ, f0_hz=self.F0_HZ, fase_graus=fase_graus,
        )

    def test_disturbio_identico_da_1(self):
        sinal = self._senoide() + self._disturbio()
        valor, motivo = self._corr(sinal, sinal.copy())
        self.assertIsNone(motivo)
        self.assertAlmostEqual(valor, 1.0, places=9)

    def test_disturbio_com_sinal_trocado_da_menos_1(self):
        senoide = self._senoide()
        valor, motivo = self._corr(senoide + self._disturbio(), senoide - self._disturbio())
        self.assertIsNone(motivo)
        self.assertAlmostEqual(valor, -1.0, places=9)

    def test_escala_do_disturbio_nao_muda_a_correlacao(self):
        senoide = self._senoide()
        valor, _ = self._corr(senoide + self._disturbio(), senoide + 0.4 * self._disturbio())
        self.assertAlmostEqual(valor, 1.0, places=9)

    def test_correlacao_total_alta_mas_disturbio_ortogonal_da_zero(self):
        # a fundamental domina a correlação do sinal inteiro (>0,99) mesmo
        # quando o distúrbio capturado não tem nada a ver com o esperado
        senoide = self._senoide()
        esperado = senoide + 0.2 * np.sin(2 * np.pi * 180 * self._t())
        capturado = senoide + 0.2 * np.sin(2 * np.pi * 180 * self._t() + np.pi / 2)
        import analisar_sessao
        _, total = analisar_sessao.analisar_offset(esperado, capturado, self.FS_HZ)
        self.assertGreater(total, 0.95)
        valor, _ = self._corr(esperado, capturado)
        self.assertAlmostEqual(valor, 0.0, places=6)

    def test_usa_a_fase_do_modelo_na_senoide_nominal(self):
        fase = 37.0
        sinal = self._senoide(fase) + self._disturbio()
        valor, motivo = self._corr(sinal, sinal.copy(), fase_graus=fase)
        self.assertIsNone(motivo)
        self.assertAlmostEqual(valor, 1.0, places=9)
        # com a fase errada o resíduo carrega a senoide mal subtraída e a
        # correlação com um capturado sem a mesma senoide deixa de ser 1
        capturado = self._senoide(fase) + 0.5 * self._disturbio()
        errado, _ = self._corr(sinal, capturado, fase_graus=0.0)
        self.assertLess(errado, 0.999)

    def test_classe_01_sem_disturbio_devolve_none_com_motivo(self):
        valor, motivo = self._corr(self._senoide(), self._senoide() + 0.01 * np.cos(self._t() * 1e4))
        self.assertIsNone(valor)
        self.assertIn("~ 0", motivo)

    def test_offset_dc_puro_devolve_none_com_motivo(self):
        valor, motivo = self._corr(self._senoide() + 0.05, self._senoide() + 0.05)
        self.assertIsNone(valor)
        self.assertIn("constante", motivo)

    def test_capturado_com_residuo_constante_devolve_none(self):
        valor, motivo = self._corr(self._senoide() + self._disturbio(), self._senoide())
        self.assertIsNone(valor)
        self.assertIn("capturado constante", motivo)

    def test_formas_incompativeis_devolvem_none(self):
        valor, motivo = self._corr(np.zeros(10), np.zeros(9))
        self.assertIsNone(valor)
        self.assertIn("incompat", motivo)

    def test_analisar_sessao_expoe_a_correlacao_do_disturbio(self):
        # captura == esperado de uma classe com distúrbio real (05, THD 5%):
        # correlação do distúrbio ~1; na 01 vem None com motivo
        import analisar_sessao
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            sessao_dir = tmp_dir / "sessao_teste"
            (sessao_dir / "metadata").mkdir(parents=True)
            fs_hz, pontos = self.FS_HZ, 6000
            for classe, nome, seed in (("01", "normal", 21260827), ("05", "harmonics", 25260827)):
                md = {"classe": nome.upper(), "fs_hz": fs_hz, "id_captura": f"{classe}-0001", "f0_hz": 60.0,
                      "parametros": {}, "pontos": pontos, "seed": seed, "simulado": False, "nivel_indice": 0}
                esperado = analisar_sessao._reconstruir_esperado(classe, md)
                np.savez(
                    sessao_dir / f"{classe}_{nome}_cap01.npz", tempo_ms=self._t() * 1000.0,
                    tensao_pu=esperado.reshape(1, -1), classe=nome.upper(),
                    id_captura=np.array([f"{classe}-0001"], dtype=object),
                )
                (sessao_dir / "metadata" / f"{classe}_{nome}.jsonl").write_text(json.dumps(md) + "\n", encoding="utf-8")
            relatorio = {r["classe"]: r for r in analisar_sessao.analisar_sessao(sessao_dir)}
            self.assertIsNone(relatorio["01_normal_cap01"]["correlacao_disturbio"])
            self.assertTrue(relatorio["01_normal_cap01"]["correlacao_disturbio_motivo"])
            self.assertAlmostEqual(relatorio["05_harmonics_cap01"]["correlacao_disturbio"], 1.0, places=6)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class CaminhoNativoIntegridadeTests(unittest.TestCase):
    """P01 — integridade do caminho nativo (STEP/PULSe/CSINe).

    Manual AMETEK §6.4.2 p. 152, Passo 1: "Set the functions that you do not
    want to generate transients to FIXed mode." O caminho nativo nunca
    escrevia ``FUNCtion:MODE FIXed`` — causa documentada do ``-226`` da
    classe 18 (02 §(b) item 8) e candidato n.º 2 de H-NATIVO (02 §(c)).
    Manual p. 217, erro 19 "Illegal during transient" + p. 132 (falso IDLE)
    são o candidato n.º 1: escrever enquanto um transiente ainda roda é
    aceito na fila mas ignorado."""

    def _fonte(self, **kwargs):
        kwargs.setdefault("max_voltage_rms", 300.0)
        kwargs.setdefault("max_peak_v", 425.0)
        kwargs.setdefault("max_current_a", 0.5)
        return AmetekMX30(simulated=True, **kwargs)

    def test_trigger_step_poe_function_mode_em_fixed_antes_do_voltage_mode(self):
        fonte = self._fonte()
        fonte.trigger_step(127.0)
        log = fonte.command_log
        self.assertIn("FUNCtion:MODE FIXed", log)
        self.assertLess(log.index("FUNCtion:MODE FIXed"), log.index("VOLTage:MODE STEP"))

    def test_trigger_pulse_poe_function_mode_em_fixed_antes_do_voltage_mode(self):
        fonte = self._fonte()
        fonte.trigger_pulse(12.7, width_s=0.060)
        log = fonte.command_log
        self.assertIn("FUNCtion:MODE FIXed", log)
        self.assertLess(log.index("FUNCtion:MODE FIXed"), log.index("VOLTage:MODE PULSe"))

    def test_configure_harmonics_csine_neutraliza_listas_residuais(self):
        fonte = self._fonte()
        fonte.configure_harmonics_csine(5.0)
        log = fonte.command_log
        self.assertIn("FUNCtion:MODE FIXed", log)
        self.assertLess(
            log.index("FUNCtion:MODE FIXed"),
            log.index("SOURce:FUNCtion:SHAPe CSINusoid"),
        )

    def test_frequency_drift_list_neutraliza_lista_de_forma_residual(self):
        """Causa exata do ``-226 Lists not same length`` da classe 18 depois da
        17 (relatório 02 §(b) item 8): a lista de FORMA de 12 pontos da 17
        continua ativa enquanto a 18 programa uma lista de FREQuência de 2
        pontos."""
        fonte = self._fonte()
        fonte.frequency_drift_list(57.0, 63.0, voltage_rms=127.0, dwell_s=0.1)
        log = fonte.command_log
        self.assertIn("FUNCtion:MODE FIXed", log)
        self.assertLess(log.index("FUNCtion:MODE FIXed"), log.index("FREQuency:MODE LIST"))

    def test_caminho_nativo_espera_idle_antes_de_escrever(self):
        """Nada pode ser escrito enquanto ``TRIGger:STATe?`` for BUSY."""
        fonte = self._fonte()
        estados = ["BUSY", "BUSY", "IDLE"]
        escritas_quando_busy = []
        query_original = fonte.query
        write_original = fonte.write

        def query_fake(command):
            if command.strip().upper().startswith("TRIG"):
                return estados.pop(0) if estados else "IDLE"
            return query_original(command)

        def write_espiao(command):
            if estados:  # ainda não chegou em IDLE
                escritas_quando_busy.append(command)
            return write_original(command)

        fonte.query = query_fake
        fonte.write = write_espiao
        fonte.trigger_step(127.0)
        self.assertEqual(escritas_quando_busy, [])
        self.assertEqual(estados, [])

    def test_caminho_nativo_recusa_erro_19_illegal_during_transient(self):
        """Manual p. 217: erro 19 = "Operation requested not available while
        transient is running". Hoje a fila só era lida com ``diagnostico on``
        e o valor escrito ficava silenciosamente sem efeito."""
        fonte = self._fonte()
        query_original = fonte.query
        fila = ['19,"Illegal during transient"', '0,"No error"']

        def query_fake(command):
            if command.strip().upper().startswith(("SYST", "SYSTEM")):
                return fila.pop(0) if fila else '0,"No error"'
            return query_original(command)

        fonte.query = query_fake
        with self.assertRaises(InstrumentHardwareError) as ctx:
            fonte.trigger_step(127.0)
        self.assertIn("19", str(ctx.exception))
        self.assertIn("transiente", str(ctx.exception).lower())

    def test_aguardar_idle_falha_com_mensagem_propria(self):
        fonte = self._fonte()
        fonte.query = lambda command: "BUSY"
        with self.assertRaises(TimeoutError) as ctx:
            fonte.aguardar_idle(timeout_s=0.3)
        self.assertIn("IDLE", str(ctx.exception))

    def test_diagnostico_continua_sem_mudar_writes_no_trigger_step(self):
        sem_log = self._fonte(diagnostico=False)
        sem_log.trigger_step(127.0)
        com_log = self._fonte(diagnostico=True)
        com_log.trigger_step(127.0)

        def escritas(log):
            return [comando for comando in log if not comando.endswith("?")]

        self.assertEqual(escritas(sem_log.command_log), escritas(com_log.command_log))


class ArmLeDeVoltaTests(unittest.TestCase):
    """P02 — ``arm()`` (caminho nativo) lê de volta o que foi escrito.

    Assimetria que deixou H-NATIVO passar em silêncio por duas sessões
    (relatório 01 §1.2): ``arm_transient()`` (LIST) lê 9 parâmetros do
    instrumento e recusa divergência; ``arm()`` (nativo) não lia nada.
    NÃO consultamos ``FUNCtion:SHAPe?``/``SOURce:MODE?``: a Rev. 5.53 não os
    implementa como QUERY e devolve ``-113`` (documentado na docstring de
    ``aguardar_resposta``) — o relatório 01 recomenda ler ``FUNCtion:SHAPe?``
    e nisso ele está errado para este firmware."""

    def _fonte(self, **kwargs):
        kwargs.setdefault("max_voltage_rms", 300.0)
        kwargs.setdefault("max_peak_v", 425.0)
        kwargs.setdefault("max_current_a", 0.5)
        return AmetekMX30(simulated=True, **kwargs)

    def test_arm_consulta_os_parametros_do_step(self):
        fonte = self._fonte()
        fonte.trigger_step(127.0)
        fonte.command_log.clear()
        fonte.arm(timeout_s=2.0)
        consultas = [c.upper() for c in fonte.command_log if c.endswith("?")]
        self.assertIn("VOLTAGE:MODE?", consultas)
        self.assertIn("VOLTAGE:TRIGGERED?", consultas)
        self.assertIn("FUNCTION:MODE?", consultas)
        self.assertIn("SOURCE:FREQUENCY:MODE?", consultas)
        self.assertNotIn("SOURCE:FUNCTION:SHAPE?", consultas)
        self.assertNotIn("SOURCE:MODE?", consultas)

    def test_arm_consulta_pulse_width_so_em_modo_pulse(self):
        fonte = self._fonte()
        fonte.trigger_step(127.0)
        fonte.command_log.clear()
        fonte.arm(timeout_s=2.0)
        self.assertNotIn("PULSE:WIDTH?", [c.upper() for c in fonte.command_log])
        fonte.trigger()  # devolve o simulador ao estado IDLE, como na bancada
        fonte.trigger_pulse(12.7, width_s=0.060)
        fonte.command_log.clear()
        fonte.arm(timeout_s=2.0)
        self.assertIn("PULSE:WIDTH?", [c.upper() for c in fonte.command_log])

    def test_arm_recusa_quando_voltage_triggered_nao_pegou(self):
        """O caso exato da sessão 2: a classe escreveu 220 V e a fonte
        continuou com 242 V (nível anterior). Sem readback isso virou dado
        rotulado errado; com readback vira falha de captura."""
        fonte = self._fonte()
        fonte.trigger_pulse(220.0, width_s=0.060)
        original = fonte.query

        def query_valor_preso(command):
            if command.strip().upper().startswith("VOLTAGE:TRIGGERED?"):
                return "242.0"
            return original(command)

        fonte.query = query_valor_preso
        with self.assertRaises(InstrumentHardwareError) as ctx:
            fonte.arm(timeout_s=2.0)
        mensagem = str(ctx.exception)
        self.assertIn("VOLTage:TRIGgered", mensagem)
        self.assertIn("242", mensagem)

    def test_arm_recusa_quando_function_mode_ficou_em_list(self):
        """Candidato n.º 2 de H-NATIVO: lista de forma residual de uma classe
        waveform anterior ainda ativa no *TRG nativo."""
        fonte = self._fonte()
        fonte.trigger_step(127.0)
        original = fonte.query

        def query_modo_residual(command):
            if command.strip().upper().startswith("FUNCTION:MODE?"):
                return "LIST"
            return original(command)

        fonte.query = query_modo_residual
        with self.assertRaises(InstrumentHardwareError) as ctx:
            fonte.arm(timeout_s=2.0)
        self.assertIn("FUNCtion:MODE", str(ctx.exception))

    def test_arm_aceita_abreviacoes_do_firmware(self):
        """A Rev. 5.53 responde 'FIX'/'PULS'/'STEP' (forma curta SCPI)."""
        fonte = self._fonte()
        fonte.trigger_pulse(12.7, width_s=0.060)
        original = fonte.query

        def query_abreviado(command):
            upper = command.strip().upper()
            if upper == "VOLTAGE:MODE?":
                return "PULS"
            if upper == "FUNCTION:MODE?":
                return "FIX"
            if upper == "SOURCE:FREQUENCY:MODE?":
                return "FIX"
            return original(command)

        fonte.query = query_abreviado
        fonte.arm(timeout_s=2.0)  # não deve levantar

    def test_arm_relata_init_ignorado_lendo_a_fila(self):
        """Manual p. 129: "If the trigger system is not in the Idle state, the
        initiate commands are ignored" e p. 214 ``-220 "Init ignored"``.
        Assinatura observada na classe 05 (relatório 01 §1.3 B5): INIT sem
        erro e o estado nunca sai de IDLE."""
        fonte = self._fonte()
        fonte.trigger_step(127.0)
        original = fonte.query
        fila = ['0,"No error"', '-220,"Init ignored"', '0,"No error"']

        def query_preso_em_idle(command):
            upper = command.strip().upper()
            if upper.startswith(("TRIGGER:STATE?", "TRIG:STATE?")):
                return "IDLE"
            if upper.startswith(("SYST", "SYSTEM")):
                return fila.pop(0) if fila else '0,"No error"'
            return original(command)

        fonte.query = query_preso_em_idle
        with self.assertRaises(TimeoutError) as ctx:
            fonte.arm(timeout_s=0.3)
        self.assertIn("220", str(ctx.exception))


class SalvamentoIncrementalTests(unittest.TestCase):
    """P03 — cada captura vai para o disco assim que sai.

    Relatório 01 §3 P1 caminho #1: ``executar()`` só chamava
    ``_salvar_classe()`` DEPOIS do laço inteiro. Na sessão 2, as 7 capturas
    boas da classe 08 e as 52 físicas da 03 foram perdidas porque só existiam
    em memória quando a falha ocorreu."""

    def _config(self, results_dir, **overrides):
        base = dict(
            fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=results_dir,
            sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
            capturas_override=4,
        )
        base.update(overrides)
        return mestre.Config(**base)

    def _experimento(self, config, falhar_em=None, observador=None):
        # Limites coerentes com 127 V de base (ver pré-validação de pico).
        bancada = mestre.Bancada(
            mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0),
            mock.Mock(), config,
        )

        class _Classe(mestre.ExperimentoNativo):
            id = "96"
            nome = "TESTE_INCREMENTAL"

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

            def configurar(self, capture_index):
                return {}

        experimento = _Classe(bancada)
        experimento.osc = mock.Mock()
        # Esta classe testa gravação incremental, não margem (P10) — neutraliza
        # a folga fixa para os stubs poderem devolver arrays de config.points.
        experimento._calcular_margem = lambda **kw: (0, 0, kw["config_points"])
        pontos = config.points
        tempo_s = np.arange(pontos, dtype=np.float64) / config.fs_hz
        chamadas = {"n": 0}

        def _stub(capture_index, t, rng):
            chamadas["n"] += 1
            if observador is not None:
                observador(chamadas["n"])
            if falhar_em is not None and chamadas["n"] == falhar_em:
                # CommunicationError (não InstrumentHardwareError): desde o
                # P09 (2026-09-22), InstrumentHardwareError de UMA captura é
                # descartada e a classe SEGUE (ver CapturaDescartavelTests) —
                # deixaria de exercitar o abort-preserva-parcial que esta
                # classe testa. CommunicationError continua abortando de
                # propósito (serial caiu de verdade), que é o cenário real
                # que a gravação incremental foi desenhada para proteger.
                raise CommunicationError("falha de infraestrutura simulada no meio da classe")
            return tempo_s, np.sin(2.0 * np.pi * 60.0 * tempo_s), None, {}

        experimento._capturar_real = _stub
        experimento._preparar_acquisicao_real = lambda: None
        return experimento

    def test_cada_captura_aparece_no_disco_antes_da_proxima(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados")
            vistos = []

            spool = config.results_dir / "parcial" / "96_teste_incremental"

            def observador(n):
                vistos.append(len(list(spool.glob("*.npz"))))

            experimento = self._experimento(config, observador=observador)
            experimento.executar()
            # Formato 2: cada captura vai para parcial/NN_classe/ (atômica) assim
            # que sai; antes da captura 1 não há nada; antes da 2 já existe 1...
            self.assertEqual(vistos, [0, 1, 2, 3])
            # ...e, ao fim da classe, tudo está no 96_teste_incremental.npz e o spool some.
            self.assertEqual(len(_capturas_gravadas(config.results_dir, "96")), 4)
            self.assertFalse(spool.exists())
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_falha_no_meio_preserva_as_capturas_boas_anteriores(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados")
            experimento = self._experimento(config, falhar_em=3)
            with self.assertRaises(CommunicationError):
                experimento.executar()
            arquivos = _capturas_gravadas(config.results_dir, "96")
            self.assertEqual(len(arquivos), 2, f"esperava 2 capturas preservadas, achei {arquivos}")
            self.assertFalse((config.results_dir / "parcial" / "96_teste_incremental").exists())
            metadata = config.results_dir / "metadata" / "96_teste_incremental.jsonl"
            self.assertTrue(metadata.exists(), "metadata parcial precisa existir para os .npz serem usáveis")
            linhas = [l for l in metadata.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(len(linhas), 2)
            self.assertTrue(all(json.loads(l)["id_captura"].startswith("96-") for l in linhas))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_falha_parcial_nao_apaga_arquivos_da_rodada_anterior(self):
        """A limpeza de órfãos (docstring de ``_salvar_classe``) só pode rodar
        quando a rodada terminou inteira: numa rodada abortada no meio, os
        arquivos da rodada anterior ainda são os melhores dados existentes."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados")
            config.results_dir.mkdir(parents=True, exist_ok=True)
            orfao = config.results_dir / "96_teste_incremental_cap09.npz"
            np.savez(orfao, tempo_ms=np.zeros(3), tensao_pu=np.zeros((1, 3)))
            experimento = self._experimento(config, falhar_em=2)
            with self.assertRaises(CommunicationError):
                experimento.executar()
            self.assertTrue(orfao.exists(), "rodada abortada não pode apagar dados da rodada anterior")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class ErroDeterministicoEPreValidacaoTests(unittest.TestCase):
    """P04 — erro determinístico não é retentado; nível inviável é detectado
    ANTES da primeira captura.

    Relatório 01 §3 P1 caminho #4 e §3 P1 "Defeito adicional": a classe 03 a
    220 V pede 1,4 pu = 308 Vrms, acima do teto FÍSICO de 300 Vrms do manual
    ([AM] §4.14, p. 84 / relatório 02 B46). O código só descobria isso depois
    de 20 capturas físicas, três vezes seguidas, e terminava com zero
    arquivos."""

    def _bancada(self, results_dir, **overrides):
        base = dict(
            fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=220.0, snr_levels_db=(), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=results_dir,
            sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
            capturas_override=1,
        )
        base.update(overrides)
        config = mestre.Config(**base)
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
        return mestre.Bancada(fonte, mock.Mock(), config)

    @staticmethod
    def _classe_swell(tentativas):
        class _Swell(mestre.ExperimentoNativo):
            id = "03"
            nome = "SWELL"
            NIVEIS = (1.1, 1.2, 1.4, 1.6, 1.8)

            def gerar(self, t, f0, capture_index, rng):
                nivel = self.NIVEIS[capture_index % len(self.NIVEIS)]
                return np.sin(2.0 * np.pi * f0 * t) * nivel, {"swell_pu": nivel}

            def configurar(self, capture_index):
                nivel = self.NIVEIS[capture_index % len(self.NIVEIS)]
                tentativas.append(nivel)
                self.fonte.trigger_pulse(nivel * self.config.base_voltage_rms, width_s=0.060)
                return {"swell_pu": nivel}

        return _Swell

    def _preparar(self, experimento):
        experimento._calcular_margem = lambda **kw: (0, 0, kw["config_points"])
        pontos = experimento.config.points
        tempo_s = np.arange(pontos, dtype=np.float64) / experimento.config.fs_hz

        def _stub(capture_index, t, rng):
            # devolve a MESMA forma que gerar() produz para este nível: a
            # validação física (P05) reprovaria uma captura incoerente, e o
            # que este teste exercita é a seleção de níveis, não ela.
            parametros = experimento.configurar(capture_index)
            nivel = experimento.NIVEIS[capture_index % len(experimento.NIVEIS)]
            return tempo_s, np.sin(2.0 * np.pi * 60.0 * tempo_s) * nivel, None, parametros

        experimento._capturar_real = _stub
        experimento._preparar_acquisicao_real = lambda: None

    def test_extremo_previsto_pela_calibracao_pula_nivel_que_cabe_em_rms(self):
        """Com a calibração REAL (swell 1,038 × margem 1,10), 1,2 pu a 220 V
        (264 Vrms, 373 Vp — cabe no rms e no pico programado) prevê 426 V de
        extremo: acima dos 415,8 V da bancada, pulado ANTES de programar."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            tentativas = []
            bancada = self._bancada(tmp_dir / "resultados")
            bancada.fonte.max_peak_v = 415.8
            experimento = self._classe_swell(tentativas)(bancada)
            experimento.osc = mock.Mock()
            self._preparar(experimento)
            with self.assertLogs("MestreExperimentos", level="WARNING") as logs:
                experimento.executar()
            self.assertEqual(tentativas, [1.1])
            self.assertTrue(any("extremo PREVISTO" in linha for linha in logs.output), logs.output)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_nivel_acima_do_teto_e_pulado_antes_de_qualquer_captura(self):
        # Isola a regra de RMS da P04: fator de extremo neutro (1,0 × 1,0).
        fatores = mock.patch.object(mestre, "carregar_fatores_extremo", return_value={"03": 1.0})
        margem = mock.patch.object(mestre, "MARGEM_FATOR_EXTREMO", 1.0)
        fatores.start(); margem.start()
        self.addCleanup(fatores.stop); self.addCleanup(margem.stop)
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            tentativas = []
            bancada = self._bancada(tmp_dir / "resultados")
            experimento = self._classe_swell(tentativas)(bancada)
            experimento.osc = mock.Mock()
            self._preparar(experimento)
            with self.assertLogs("MestreExperimentos", level="WARNING"):
                experimento.executar()
            # 1,4/1,6/1,8 x 220 V passam de 300 Vrms: só 1,1 e 1,2 rodam.
            self.assertEqual(tentativas, [1.1, 1.2])
            # Formato 2: um 03_swell.npz com as 2 capturas viáveis empilhadas.
            self.assertEqual(len(_capturas_gravadas(tmp_dir / "resultados", "03")), 2)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_classe_sem_nenhum_nivel_viavel_falha_sem_capturar(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            tentativas = []
            bancada = self._bancada(tmp_dir / "resultados", base_voltage_rms=280.0)
            experimento = self._classe_swell(tentativas)(bancada)
            experimento.osc = mock.Mock()
            self._preparar(experimento)
            with self.assertRaises(ParameterOutOfBoundsError):
                experimento.executar()
            self.assertEqual(tentativas, [])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_erro_deterministico_nao_e_retentado_pela_bateria(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            bancada = self._bancada(tmp_dir / "resultados")
            chamadas = {"n": 0}

            class _Determinista(mestre.ExperimentoNativo):
                id = "03"
                nome = "SWELL"

                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {}

                def configurar(self, capture_index):
                    return {}

                def executar(self):
                    chamadas["n"] += 1
                    raise ParameterOutOfBoundsError("Tensão 308.0 Vrms fora do limite 0..300.0")

            with mock.patch.object(
                mestre.Bancada, "_carregar_classe_experimento",
                staticmethod(lambda script_path: _Determinista),
            ), mock.patch.object(mestre.Bancada, "recuperar_estado_seguro", lambda self: None), \
                    self.assertLogs("MestreExperimentos", level="ERROR") as logs:
                resultados = bancada.executar_bateria([Path("03.py")])
            self.assertEqual(chamadas["n"], 1, "erro determinístico não pode ser retentado 3x")
            self.assertFalse(resultados[0].ok)
            # O log final conta as tentativas FEITAS (bancada 2026-10-07 dizia "após 3").
            final = [r.getMessage() for r in logs.records if "definitivamente" in r.getMessage()]
            self.assertEqual(len(final), 1)
            self.assertIn("após 1 tentativa(s) (erro determinístico, sem retry)", final[0])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_erro_intermitente_continua_sendo_retentado(self):
        """A rede de segurança para -113/-300 esporádicos (docstring de
        ``executar_bateria``) NÃO pode ser removida junto."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            bancada = self._bancada(tmp_dir / "resultados")
            chamadas = {"n": 0}

            class _Intermitente(mestre.ExperimentoNativo):
                id = "03"
                nome = "SWELL"

                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {}

                def configurar(self, capture_index):
                    return {}

                def executar(self):
                    chamadas["n"] += 1
                    if chamadas["n"] < 2:
                        raise InstrumentHardwareError("-113 esporádico")

            with mock.patch.object(
                mestre.Bancada, "_carregar_classe_experimento",
                staticmethod(lambda script_path: _Intermitente),
            ), mock.patch.object(mestre.Bancada, "recuperar_estado_seguro", lambda self: None):
                resultados = bancada.executar_bateria([Path("03.py")])
            self.assertEqual(chamadas["n"], 2)
            self.assertTrue(resultados[0].ok)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class FaseDeDisparoTests(unittest.TestCase):
    """Sessão 2026-09-30 14:44: 02/03/04 saíram defasadas 216° de gerar()
    (pré-trigger 60 ms = 3,6 ciclos, disparo sempre em 0°)."""

    def _experimento(self, pre_trigger_s, f0=60.0):
        config = mock.Mock(grid_frequency_hz=f0)
        experimento = mock.Mock(spec=mestre.ExperimentoNativo)
        experimento.pre_trigger_s = pre_trigger_s
        experimento.config = config
        return experimento

    def test_fase_e_a_de_gerar_no_instante_do_trigger(self):
        fase = mestre.ExperimentoNativo.fase_de_disparo_graus
        self.assertAlmostEqual(fase(self._experimento(0.060)), 216.0)
        self.assertAlmostEqual(fase(self._experimento(0.060, f0=50.0)), 0.0)
        self.assertAlmostEqual(fase(self._experimento(0.0)), 0.0)

    def test_caminho_nativo_programa_a_fase_antes_do_transiente(self):
        fonte = AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
        experimento = mock.Mock(spec=mestre.ExperimentoNativo)
        experimento.pre_trigger_s = 0.060
        experimento.config = mock.Mock(grid_frequency_hz=60.0)
        experimento.fonte = fonte
        experimento.osc = mock.Mock()
        experimento.usar_trace.return_value = False
        experimento.fase_de_disparo_graus = (
            lambda *a, **k: mestre.ExperimentoNativo.fase_de_disparo_graus(experimento, *a, **k)
        )
        experimento.configurar.side_effect = lambda ci: (fonte.trigger_pulse(2.7, width_s=0.06), {})[1]
        experimento._ler_captura.return_value = "ok"
        experimento.gerar.return_value = (None, {})  # sem sorteio: fase e pré-trigger de sempre
        self.assertEqual(mestre.ExperimentoNativo._capturar_real(experimento, 0, None, None), "ok")
        log = fonte.command_log
        fase = log.index("TRIGger:SYNChronize:PHASe 216.0")
        self.assertLess(fase, log.index("VOLTage:MODE PULSe"))
        experimento.osc.definir_pre_trigger.assert_not_called()


class FrequenciaBaseTests(unittest.TestCase):
    """Sessão 2026-09-30 14:44: a lista de frequência da 18 terminou em 63 Hz
    e a 19 rodou inteira a 63,03 Hz."""

    def test_fim_de_classe_volta_a_frequencia_base_depois_de_lista(self):
        fonte = AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
        fonte._frequencia_base_hz = 60.0
        fonte.frequency_drift_list(57.0, 63.0, voltage_rms=127.0, dwell_s=0.1)
        fonte.command_log.clear()
        fonte.restaurar_forma_e_modo_padrao()
        self.assertIn("SOURce:FREQuency 60", fonte.command_log)
        fonte.command_log.clear()
        fonte.restaurar_forma_e_modo_padrao()  # já restaurada: no-op
        self.assertNotIn("SOURce:FREQuency 60", fonte.command_log)

    def test_classe_sem_lista_de_frequencia_nao_reescreve_frequencia(self):
        fonte = AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
        fonte._frequencia_base_hz = 60.0
        fonte.trigger_step(127.0)
        fonte.command_log.clear()
        fonte.restaurar_forma_e_modo_padrao()
        self.assertEqual([c for c in fonte.command_log if "FREQuency" in c], [])


class Classe08BancadaTests(unittest.TestCase):
    """ANALISE.md T8-1/T8-2: o limite de pico escalava a forma inteira (base a
    43 Vrms) e a oscilação da saída após o impulso (vale ~45% do degrau abaixo
    da partida) não era prevista."""

    T = np.arange(6000, dtype=np.float64) / 30_000.0

    def _experimento(self, capturas_override=None, base_v=127.0):
        experimento = _load_experimento("08")
        experimento.fonte = mock.Mock(max_peak_v=415.8)
        experimento.osc = mock.Mock()
        campos = dict(_BancadaFake.config.__dict__)
        campos.update(base_voltage_rms=base_v, capturas_override=capturas_override)
        experimento.config = mestre.Config(**campos)
        return experimento

    def _forma(self, experimento, capture_index=0):
        onda, parametros = experimento.gerar(self.T, 60.0, capture_index, np.random.default_rng(3))
        forma = experimento.forma_para_bancada(onda, parametros, capture_index)
        return forma, parametros

    def test_base_fica_em_1pu_e_so_o_impulso_e_limitado(self):
        forma, parametros = self._forma(self._experimento())
        fora = np.ones(6000, dtype=bool)
        fora[[2400, 2401]] = False
        np.testing.assert_allclose(forma[fora], np.sin(2 * np.pi * 60 * self.T)[fora])
        self.assertLess(parametros["amplitude_bancada_pu"], parametros["transient_amplitude_pu"])
        self.assertGreater(parametros["amplitude_bancada_pu"], 0.0)

    def test_pico_e_vale_previstos_cabem_no_teto(self):
        for base_v in (127.0, 220.0):
            experimento = self._experimento(base_v=base_v)
            _, parametros = self._forma(experimento)
            teto_v = 0.9 * 415.8
            self.assertLessEqual(parametros["pico_previsto_v"], teto_v + 1e-6)
            self.assertGreaterEqual(parametros["vale_previsto_v"], -teto_v - 1e-6)
            self.assertAlmostEqual(experimento.excursao_fisica_prevista_v(), teto_v, delta=1.0)

    def test_50hz_pico_real_medido_cabe_no_teto_e_60hz_nao_muda(self):
        """Bancada 2026-10-07: a 50 Hz o impulso parte do cruzamento por zero
        e o PICO limita; a saída fez sobressinal de 0,457 e mediu 376 V contra
        teto de 374,2 V (127 V e 230 V). Com o sobressinal REAL o pico tem de
        caber; a 60 Hz (vale limita) a amplitude continua 1,618 pu a 127 V."""
        teto_v = 0.9 * 415.8
        for base_v in (127.0, 230.0):
            experimento = self._experimento(base_v=base_v)
            campos = dict(experimento.config.__dict__, grid_frequency_hz=50.0)
            experimento.config = mestre.Config(**campos)
            onda, parametros = experimento.gerar(self.T, 50.0, 0, np.random.default_rng(3))
            experimento.forma_para_bancada(onda, parametros, 0)
            partida = float(np.max(np.sin(2 * np.pi * 50 * self.T[[2400, 2401]])))
            pico_real_v = (partida + parametros["amplitude_bancada_pu"] * 1.457) * base_v * math.sqrt(2.0)
            self.assertLess(pico_real_v, teto_v, base_v)
        _, parametros = self._forma(self._experimento())
        self.assertAlmostEqual(parametros["amplitude_bancada_pu"], 1.618, places=3)

    def test_caracterizacao_sobe_em_rampa_a_partir_de_amplitude_pequena(self):
        experimento = self._experimento(capturas_override=5)
        amplitudes = [self._forma(experimento, k)[1]["amplitude_bancada_pu"] for k in range(5)]
        self.assertAlmostEqual(amplitudes[0], experimento.AMPLITUDE_MIN_CARACTERIZACAO_PU)
        self.assertTrue(all(b > a for a, b in zip(amplitudes, amplitudes[1:])), amplitudes)
        self.assertAlmostEqual(amplitudes[-1], self._forma(self._experimento())[1]["amplitude_bancada_pu"])

    def test_exige_medida_de_pico_e_exclui_ciclos_do_impulso(self):
        experimento = self._experimento()
        self.assertTrue(experimento.exige_medida_de_pico)
        self.assertEqual(experimento.fracao_teto_pico_medido, 0.9)
        self.assertEqual(tuple(experimento.ciclos_excluidos_da_validacao(0)), (4, 5))


class ExtremosFisicosTests(unittest.TestCase):
    """VMAX/VMIN medidos pelo osciloscópio na taxa cheia (o array de 30 kSa/s
    subestima picos estreitos) e parada da classe acima do teto."""

    class _AdapterComMedidas(ScriptedAdapter):
        vmax = "3.8E+02"
        vmin = "-3.2E+02"

        def read(self):
            comando = self.last_command.upper()
            if comando.startswith(":MEASURE:VMAX?"):
                return self.vmax
            if comando.startswith(":MEASURE:VMIN?"):
                return self.vmin
            return super().read()

    def test_medir_extremos_le_vmax_e_vmin_do_canal(self):
        adapter = self._AdapterComMedidas()
        scope = KeysightDSOX4034A(adapter)
        self.assertEqual(scope.medir_extremos(1), (380.0, -320.0))
        self.assertIn(":MEASure:VMAX? CHANnel1", adapter.commands)
        self.assertIn(":MEASure:VMIN? CHANnel1", adapter.commands)

    def test_medida_invalida_do_keysight_levanta(self):
        adapter = self._AdapterComMedidas()
        adapter.vmax = "9.9E+37"
        scope = KeysightDSOX4034A(adapter)
        with self.assertRaises(OscilloscopeError):
            scope.medir_extremos(1)

    def _executar(self, *, medida, exige=False, max_peak_v=200.0):
        # Estes testes exercitam o extremo MEDIDO acima do teto (200 V, baixo
        # de propósito); neutraliza a pré-validação do extremo PREVISTO, que
        # pularia a captura antes (testada em ErroDeterministicoEPreValidacaoTests).
        for alvo, valor in (("carregar_fatores_extremo", mock.Mock(return_value={"01": 1.0})),
                            ("MARGEM_FATOR_EXTREMO", 1.0)):
            patcher = mock.patch.object(mestre, alvo, valor)
            patcher.start()
            self.addCleanup(patcher.stop)
        tmp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp_dir, ignore_errors=True)
        config = mestre.Config(
            fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=tmp_dir / "resultados",
            sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
            capturas_override=2,
        )
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=max_peak_v)
        bancada = mestre.Bancada(fonte, mock.Mock(), config)

        class _Classe(mestre.ExperimentoNativo):
            id = "01"
            nome = "NORMAL"
            exige_medida_de_pico = exige

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

            def configurar(self, capture_index):
                return {}

        experimento = _Classe(bancada)
        experimento.osc = mock.Mock()
        if isinstance(medida, Exception):
            experimento.osc.medir_extremos.side_effect = medida
        else:
            experimento.osc.medir_extremos.return_value = medida
        experimento._calcular_margem = lambda **kw: (0, 0, kw["config_points"])
        tempo_s = np.arange(6000, dtype=np.float64) / 30_000.0
        experimento._capturar_real = lambda ci, t, rng: (
            tempo_s, np.sin(2.0 * np.pi * 60.0 * tempo_s), None, {},
        )
        experimento._preparar_acquisicao_real = lambda: None
        metadata = config.results_dir / "metadata" / "01_normal.jsonl"
        return experimento, metadata

    def _registros(self, metadata):
        return [json.loads(l) for l in metadata.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_extremo_acima_do_teto_para_a_classe_sem_retry_mas_grava_a_captura(self):
        experimento, metadata = self._executar(medida=(250.0, -180.0), max_peak_v=200.0)
        with self.assertRaises(mestre.PicoFisicoExcedidoError):
            experimento.executar()
        registros = self._registros(metadata)
        self.assertEqual(len(registros), 1, "parou na PRIMEIRA captura, depois de gravá-la")
        self.assertEqual(registros[0]["pico_medido_v"], 250.0)
        self.assertIn(mestre.PicoFisicoExcedidoError, mestre.Bancada.ERROS_DETERMINISTICOS)
        self.assertFalse(issubclass(mestre.PicoFisicoExcedidoError, mestre.ERROS_CAPTURA_DESCARTAVEL))

    def test_extremos_dentro_do_teto_vao_para_o_metadata(self):
        experimento, metadata = self._executar(medida=(181.0, -179.0), max_peak_v=200.0)
        experimento.executar()
        registro = self._registros(metadata)[0]
        self.assertEqual((registro["pico_medido_v"], registro["vale_medido_v"]), (181.0, -179.0))
        self.assertEqual(registro["teto_extremos_v"], 200.0)

    def test_classe_que_exige_medida_para_quando_ela_nao_vem(self):
        experimento, _ = self._executar(medida=OscilloscopeError("9.9E+37"), exige=True)
        with self.assertRaises(mestre.PicoFisicoExcedidoError):
            experimento.executar()

    def test_classe_comum_sem_medida_so_registra(self):
        experimento, metadata = self._executar(medida=OscilloscopeError("9.9E+37"), exige=False)
        experimento.executar()
        self.assertIn("extremos_indisponiveis", self._registros(metadata)[0])


class ValidacaoSemCiclosExcluidosTests(unittest.TestCase):
    def test_ciclos_excluidos_nao_entram_na_comparacao(self):
        class _Classe(mestre.ExperimentoNativo):
            id = "97"
            nome = "EXCLUI"
            excluir = ()

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

            def configurar(self, capture_index):
                return {}

            def ciclos_excluidos_da_validacao(self, capture_index):
                return self.excluir

        experimento = _Classe(_BancadaFake())
        t = np.arange(6000, dtype=np.float64) / 30_000.0
        medido = np.sin(2.0 * np.pi * 60.0 * t)
        medido[2400:2410] = 3.0  # "oscilação" no ciclo 4
        medido[2500:2510] = -2.0  # e no 5
        self.assertFalse(experimento._validar_fisicamente(0, t, 1, medido)["ok"])
        experimento.excluir = (4, 5)
        self.assertTrue(experimento._validar_fisicamente(0, t, 1, medido)["ok"])


class BateriaExcluirTests(unittest.TestCase):
    """``BATERIA_EXCLUIR`` tira classes do run all físico (a 08 ficou fora de
    14:44 a 15:25 de 2026-09-30); padrão vazio = as 20 classes."""

    def test_padrao_roda_as_20_classes(self):
        self.assertEqual(mestre.BATERIA_EXCLUIR, ())
        self.assertEqual(len(mestre.scripts_da_bateria_fisica()), 20)

    def test_classe_excluida_sai_so_do_run_all_fisico(self):
        with mock.patch.object(mestre, "BATERIA_EXCLUIR", ("08",)):
            ids = [script.stem for script in mestre.scripts_da_bateria_fisica()]
        self.assertNotIn("08", ids)
        self.assertEqual(len(ids), 19)
        self.assertIn("08", [script.stem for script in mestre._experiment_scripts()])


class ValidacaoFisicaTests(unittest.TestCase):
    """P05 — validação FÍSICA pós-captura, independente do mecanismo.

    H-NATIVO (relatório 01 §1.2) produziu, por duas sessões, dado rotulado
    errado sem um único erro SCPI. Um readback SCPI (P02) cobre o que a fonte
    DIZ; isto cobre o que ela FEZ, comparando a captura com a forma que a
    classe pediu. É deliberadamente insensível a alinhamento: compara
    estatísticas do envelope rms de meio ciclo (mediana/min/max) e o fator de
    crista do ciclo mediano, não amostra a amostra."""

    FS = 30_000.0
    F0 = 60.0

    def _t(self, pontos=6000):
        return np.arange(pontos, dtype=np.float64) / self.FS

    def test_captura_fiel_passa(self):
        t = self._t()
        esperado = np.sin(2.0 * np.pi * self.F0 * t)
        capturado = esperado * 1.02  # ganho de 2%, dentro da tolerância
        resultado = sinais.comparar_fisicamente(esperado, capturado, fs_hz=self.FS, f0=self.F0)
        self.assertTrue(resultado["ok"], resultado)

    def test_tensao_base_errada_e_reprovada(self):
        """Sessão 2: configurada para 220 V, as classes nativas saíram a
        127 V (razão 0,578)."""
        t = self._t()
        esperado = np.sin(2.0 * np.pi * self.F0 * t)
        capturado = esperado * (127.0 / 220.0)
        resultado = sinais.comparar_fisicamente(esperado, capturado, fs_hz=self.FS, f0=self.F0)
        self.assertFalse(resultado["ok"])
        self.assertTrue(any("mediana" in m for m in resultado["motivos"]), resultado["motivos"])

    def test_distúrbio_ausente_e_reprovado(self):
        """Classe 02/SAG da sessão 2: 0 de 50 capturas tinham qualquer
        evento (relatório 01 §1.3 A3)."""
        t = self._t()
        esperado = np.sin(2.0 * np.pi * self.F0 * t)
        esperado[sinais.janela(t, 0.060, 0.060)] *= 0.1
        capturado = np.sin(2.0 * np.pi * self.F0 * t)  # sem sag nenhum
        resultado = sinais.comparar_fisicamente(esperado, capturado, fs_hz=self.FS, f0=self.F0)
        self.assertFalse(resultado["ok"])
        self.assertTrue(any("mínimo" in m for m in resultado["motivos"]), resultado["motivos"])

    def test_disturbio_invertido_e_reprovado(self):
        """Classe 04 da sessão 2: interrupção virou elevação de 1,1 pu."""
        t = self._t()
        esperado = np.sin(2.0 * np.pi * self.F0 * t)
        esperado[sinais.janela(t, 0.060, 0.060)] *= 0.02
        capturado = np.sin(2.0 * np.pi * self.F0 * t)
        capturado[sinais.janela(t, 0.060, 0.060)] *= 1.1
        resultado = sinais.comparar_fisicamente(esperado, capturado, fs_hz=self.FS, f0=self.F0)
        self.assertFalse(resultado["ok"])

    def test_harmonicos_ausentes_sao_reprovados_pela_thd(self):
        """Classe 05 da sessão 1: THD medida 0,98% contra 5% programado —
        a senoide clipada simplesmente não foi aplicada (relatório 01 §1.2)."""
        t = self._t()
        w = 2.0 * np.pi * self.F0
        esperado = np.sin(w * t) + 0.04 * np.sin(3 * w * t) + 0.02 * np.sin(5 * w * t)
        capturado = np.sin(w * t) + 0.008 * np.sin(3 * w * t)  # THD ~0,8%
        resultado = sinais.comparar_fisicamente(esperado, capturado, fs_hz=self.FS, f0=self.F0)
        self.assertFalse(resultado["ok"])
        self.assertTrue(any("THD" in m for m in resultado["motivos"]), resultado["motivos"])

    def test_ruido_de_quantizacao_nao_reprova_classe_sem_harmonicos(self):
        """O piso de 1% da THD existe para isso: a classe 01/NORMAL não pode
        ser reprovada pelo ruído de 8 bits do osciloscópio."""
        t = self._t()
        rng = np.random.default_rng(7)
        esperado = np.sin(2.0 * np.pi * self.F0 * t)
        capturado = esperado + rng.normal(0.0, 0.004, size=esperado.size)
        resultado = sinais.comparar_fisicamente(esperado, capturado, fs_hz=self.FS, f0=self.F0)
        self.assertTrue(resultado["ok"], resultado)

    def test_oscilacao_curta_nao_distorce_o_fator_de_crista(self):
        """Sessão 2026-09-30 run04, classe 09: uma oscilação de 2 kHz de
        poucos ms mal muda o rms do ciclo onde cai, então o "ciclo mediano"
        escolhia justamente esse ciclo e media crista 1,62 contra 1,414. A
        forma de onda grosseira é a de regime: mediana da crista de todos os
        ciclos."""
        # 25 meios ciclos com amplitudes ligeiramente diferentes (como o
        # ruído/ondulação real): o meio ciclo 12, que recebe a oscilação,
        # fica exatamente na mediana do envelope — o caso da 09 no run04.
        t = self._t(6250)
        amplitude = np.repeat([0.95] * 12 + [1.0] + [1.05] * 12, 250)
        esperado = amplitude * np.sin(2.0 * np.pi * self.F0 * t)
        capturado = esperado.copy()
        janela_osc = sinais.janela(t, 0.1032, 0.002)
        capturado[janela_osc] += 0.35 * np.sin(2.0 * np.pi * 2000.0 * t[janela_osc])
        resultado = sinais.comparar_fisicamente(esperado, capturado, fs_hz=self.FS, f0=self.F0)
        self.assertTrue(resultado["ok"], resultado)

    def test_senoide_clipada_em_todos_os_ciclos_muda_o_fator_de_crista(self):
        """A razão de existir da sonda: CSINe aplicada dá crista ~1,34 em
        TODO ciclo; a mediana por ciclo tem de continuar vendo isso."""
        t = self._t()
        limpa = np.sin(2.0 * np.pi * self.F0 * t)
        clipada = np.clip(limpa, -0.85, 0.85)
        crista = sinais.fator_de_crista_do_ciclo_mediano(clipada, fs_hz=self.FS, f0=self.F0)
        self.assertLess(crista, 1.30)
        self.assertAlmostEqual(
            sinais.fator_de_crista_do_ciclo_mediano(limpa, fs_hz=self.FS, f0=self.F0), math.sqrt(2.0), places=2,
        )

    def test_margem_extra_no_registro_nao_reprova(self):
        """A captura real tem margem de senoide nominal antes/depois do
        evento; a comparação não pode depender de recorte nem alinhamento."""
        t = self._t()
        esperado = np.sin(2.0 * np.pi * self.F0 * t)
        esperado[sinais.janela(t, 0.060, 0.060)] *= 0.5
        t_longo = np.arange(8100, dtype=np.float64) / self.FS
        capturado = np.sin(2.0 * np.pi * self.F0 * t_longo)
        capturado[sinais.janela(t_longo, 0.0805, 0.060)] *= 0.5
        resultado = sinais.comparar_fisicamente(esperado, capturado, fs_hz=self.FS, f0=self.F0)
        self.assertTrue(resultado["ok"], resultado)

    def test_classe_valida_so_a_janela_alinhada_ignorando_margem_em_zero(self):
        """Sessão 2026-09-30 run04: a saída fica em 0 V antes do trigger (por
        projeto), então os 20 ms de margem ANTES são ~0 pu. Comparando o
        registro inteiro, TODA captura das classes 05-20 foi reprovada com
        mínimo do envelope 0,01 pu. Só a janela alinhada com a forma esperada
        (margem_antes .. margem_antes+pontos) deve ser comparada."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = mestre.Config(
                fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
                base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
                capture_current=False, current_base_a=None, results_dir=tmp_dir / "resultados",
                sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
                capturas_override=1,
            )
            fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
            bancada = mestre.Bancada(fonte, mock.Mock(), config)

            class _Classe(mestre.ExperimentoNativo):
                id = "10"
                nome = "SAG_TESTE"

                def gerar(self, t, f0, capture_index, rng):
                    onda = np.sin(2.0 * np.pi * f0 * t)
                    onda[sinais.janela(t, 0.060, 0.060)] *= 0.5
                    return onda, {}

                def configurar(self, capture_index):
                    return {}

            experimento = _Classe(bancada)
            experimento.osc = mock.Mock()
            experimento._calcular_margem = lambda **kw: (600, 1500, kw["config_points"] + 2100)
            tempo_s = np.arange(8100, dtype=np.float64) / 30_000.0
            registro = np.zeros(8100)
            t_janela = tempo_s[: 7500]
            registro[600:] = np.sin(2.0 * np.pi * 60.0 * t_janela)
            registro[600:][sinais.janela(t_janela, 0.060, 0.060)] *= 0.5
            experimento._capturar_real = lambda ci, t, rng: (tempo_s, registro.copy(), None, {})
            experimento._preparar_acquisicao_real = lambda: None
            experimento.executar()
            metadata = config.results_dir / "metadata" / "10_sag_teste.jsonl"
            registro_meta = json.loads(metadata.read_text(encoding="utf-8").splitlines()[0])
            self.assertTrue(registro_meta["validacao_fisica"]["ok"], registro_meta["validacao_fisica"])
            self.assertAlmostEqual(registro_meta["validacao_fisica"]["envelope_minimo_medido"], 0.3536, places=2)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_classe_marca_metadata_e_falha_sem_retry_quando_invalida(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = mestre.Config(
                fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
                base_voltage_rms=220.0, snr_levels_db=(), base_seed=1,
                capture_current=False, current_base_a=None, results_dir=tmp_dir / "resultados",
                sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
                capturas_override=2,
            )
            fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
            bancada = mestre.Bancada(fonte, mock.Mock(), config)

            class _Classe(mestre.ExperimentoNativo):
                id = "01"
                nome = "NORMAL"

                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {}

                def configurar(self, capture_index):
                    return {}

            experimento = _Classe(bancada)
            experimento.osc = mock.Mock()
            experimento._calcular_margem = lambda **kw: (0, 0, kw["config_points"])
            tempo_s = np.arange(6000, dtype=np.float64) / 30_000.0
            # a "fonte" entrega 127 V onde a classe pediu 220 V
            experimento._capturar_real = lambda ci, t, rng: (
                tempo_s, np.sin(2.0 * np.pi * 60.0 * tempo_s) * (127.0 / 220.0), None, {},
            )
            experimento._preparar_acquisicao_real = lambda: None
            with self.assertRaises(mestre.ValidacaoFisicaError):
                experimento.executar()
            metadata = config.results_dir / "metadata" / "01_normal.jsonl"
            registros = [
                json.loads(l) for l in metadata.read_text(encoding="utf-8").splitlines() if l.strip()
            ]
            self.assertEqual(len(registros), 2, "capturas suspeitas ainda são gravadas, com a marca")
            self.assertFalse(registros[0]["validacao_fisica"]["ok"])
            self.assertIn(mestre.ValidacaoFisicaError, mestre.Bancada.ERROS_DETERMINISTICOS)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class LogDeSessaoEMetadataTests(unittest.TestCase):
    """P06 — nada do contexto da sessão era gravado (relatório 01 §1.3 B6 e
    §4 item 9): ``logging.basicConfig(stream=sys.stdout)`` e nenhum
    ``FileHandler``; ``logs/`` vazio; metadata sem f0, tensão base, probe,
    pre_trigger, flags, versão nem IDN. Quando a fonte travou, o único
    registro do que tinha sido enviado era o console do operador."""

    def test_configurar_log_de_sessao_cria_arquivo_e_faz_flush_por_linha(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            caminho = mestre.configurar_log_de_sessao(tmp_dir)
            try:
                logging.getLogger("MestreExperimentos").info("linha de teste")
                # flush por linha: o conteúdo precisa estar em disco JÁ, sem
                # esperar o fim do processo — foi o que faltou no travamento.
                self.assertIn("linha de teste", caminho.read_text(encoding="utf-8"))
            finally:
                mestre.encerrar_log_de_sessao()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_transcricao_scpi_registra_writes_e_queries_com_timestamp(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mestre.configurar_log_de_sessao(tmp_dir)
            transcricao = tmp_dir / "scpi_transcricao.log"
            try:
                fonte = AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
                fonte.write("VOLTage:MODE STEP")
                fonte.query("VOLTage:MODE?")
                texto = transcricao.read_text(encoding="utf-8")
            finally:
                mestre.encerrar_log_de_sessao()
            self.assertIn("VOLTage:MODE STEP", texto)
            self.assertIn("VOLTage:MODE?", texto)
            self.assertIn("W ", texto)
            self.assertIn("Q ", texto)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_transcricao_trunca_trace_data_mas_registra_o_tamanho(self):
        """Um ``TRACe:DATA`` tem ~11,3 kB numa linha. Guardar os 280 de uma
        conexão inteiros inflaria o arquivo sem acrescentar nada; o que
        importa é QUE ele foi enviado e QUANDO."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            mestre.configurar_log_de_sessao(tmp_dir)
            transcricao = tmp_dir / "scpi_transcricao.log"
            try:
                fonte = AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
                fonte.write("TRACe:DATA TCC00," + ",".join("0.123456" for _ in range(1024)))
                texto = transcricao.read_text(encoding="utf-8")
            finally:
                mestre.encerrar_log_de_sessao()
            linha = [l for l in texto.splitlines() if "TRACe:DATA" in l][0]
            self.assertLess(len(linha), 400)
            self.assertIn("bytes", linha)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_metadata_grava_contexto_da_sessao(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = mestre.Config(
                fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=50.0,
                base_voltage_rms=220.0, snr_levels_db=(), base_seed=1,
                capture_current=False, current_base_a=None, results_dir=tmp_dir / "resultados",
                sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
                capturas_override=1, diagnostico_mode=True,
            )
            fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
            bancada = mestre.Bancada(fonte, mock.Mock(), config)

            class _Classe(mestre.ExperimentoNativo):
                id = "02"
                nome = "SAG"
                pre_trigger_s = 0.060

                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {}

                def configurar(self, capture_index):
                    return {}

            experimento = _Classe(bancada)
            experimento.osc = mock.Mock()
            experimento.osc.ultimo_indice_trigger = 777
            experimento.osc.idn = "KEYSIGHT,DSOX4034A,MY59240844,07.66"
            tempo_s = np.arange(6000 + 2 * 600, dtype=np.float64) / 30_000.0
            experimento._capturar_real = lambda ci, t, rng: (
                tempo_s, np.sin(2.0 * np.pi * 50.0 * tempo_s), None, {},
            )
            experimento._preparar_acquisicao_real = lambda: None
            with mock.patch.object(
                mestre.ExperimentoBase, "_calcular_margem", staticmethod(lambda **kw: (600, 600, 7200))
            ):
                experimento.executar()
            registro = json.loads(
                (config.results_dir / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8").splitlines()[0]
            )
            for chave in (
                "f0_hz", "tensao_base_rms", "pre_trigger_s", "margem_antes_s", "margem_depois_s",
                "diagnostico_mode", "versao_codigo", "idn_fonte", "indice_trigger",
                "escritas_trace_na_conexao",
            ):
                self.assertIn(chave, registro, f"metadata precisa gravar {chave}")
            self.assertEqual(registro["f0_hz"], 50.0)
            self.assertEqual(registro["tensao_base_rms"], 220.0)
            self.assertEqual(registro["pre_trigger_s"], 0.060)
            self.assertEqual(registro["indice_trigger"], 777)
            self.assertEqual(registro["margem_antes_s"], mestre.ExperimentoBase.MARGEM_ANTES_S)
            self.assertEqual(registro["margem_depois_s"], mestre.ExperimentoBase.MARGEM_DEPOIS_S)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class PastaDeSessaoPorRunTests(unittest.TestCase):
    """P06b — ``run 01`` e o ``run all`` seguinte gravavam na MESMA pasta e o
    segundo sobrescrevia o primeiro em silêncio, mesmo com flags diferentes
    (relatório 01 §3 P1 caminho #7 / §4 item 10; log1 linhas 89-110)."""

    def test_cada_run_ganha_a_sua_pasta_e_o_seu_log(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            import cli
            sessao = cli.SessaoCLI()
            with mock.patch.object(mestre, "RESULTS_DIR", tmp_dir):
                sessao._garantir_pasta_sessao()
                primeira = mestre.SESSION_RESULTS_DIR
                sessao._garantir_pasta_sessao()
                segunda = mestre.SESSION_RESULTS_DIR
            mestre.encerrar_log_de_sessao()
            self.assertNotEqual(primeira, segunda)
            self.assertTrue(primeira.is_dir() and segunda.is_dir())
            self.assertTrue((segunda / "sessao.log").exists())
        finally:
            mestre.encerrar_log_de_sessao()
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TerminalDeDiagnosticoTests(unittest.TestCase):
    """P11 — recurso de ``set diagnostico on`` (2026-09-22): abrir um
    terminal acompanhando o log SCPI do run (``tail -f``). Com ``set diagnostico on`` e captura FÍSICA (``BENCH_MODE``),
    cada ``_garantir_pasta_sessao()`` (chamada no início de todo `run`/`run
    all`) abre uma janela de console nova acompanhando
    ``scpi_transcricao.log`` (P06) da pasta da sessão em tempo real, sem
    nunca derrubar a sessão se o console não puder ser aberto."""

    def setUp(self):
        # Desde a v1.15 (spec 14) cada pasta de sessão recalcula a procedência com
        # `git`, que também passa por subprocess.Popen; estes testes contam só
        # os Popen do terminal, então a procedência fica fixa aqui.
        procedencia = {
            "git_commit": "abc", "git_sujo": False, "arquivos_nao_rastreados": [],
            "versao_codigo": "abc", "numpy_versao": np.__version__, "python_versao": "3",
        }
        patch = mock.patch.object(mestre, "info_do_codigo", return_value=procedencia)
        patch.start()
        self.addCleanup(patch.stop)

    def _sessao(self, tmp_dir):
        import cli
        sessao = cli.SessaoCLI()
        return sessao, tmp_dir

    def test_comando_do_terminal_aponta_para_o_scpi_transcricao_log_e_usa_tail(self):
        """Função pura (sem Popen): o comando gerado precisa referenciar o
        arquivo certo e usar o equivalente a `tail -f` (Get-Content -Wait)."""
        import cli
        caminho = Path(r"C:\bancada\resultados\sessao_x\scpi_transcricao.log")
        comando = cli.comando_terminal_diagnostico(caminho)
        self.assertIsInstance(comando, list)
        junto = " ".join(comando)
        self.assertIn(str(caminho), junto)
        self.assertIn("Get-Content", junto)
        self.assertIn("-Wait", junto)

    def test_abre_terminal_quando_diagnostico_on_e_bench_mode(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            sessao, _ = self._sessao(tmp_dir)
            with mock.patch.object(mestre, "RESULTS_DIR", tmp_dir), \
                 mock.patch.object(mestre, "DIAGNOSTICO_MODE", True), \
                 mock.patch.object(mestre, "BENCH_MODE", True), \
                 mock.patch("cli.subprocess.Popen") as popen_mock:
                popen_mock.return_value = mock.Mock(poll=lambda: None)
                sessao._garantir_pasta_sessao()
            mestre.encerrar_log_de_sessao()
            popen_mock.assert_called_once()
            _args, kwargs = popen_mock.call_args
            self.assertIn("scpi_transcricao.log", " ".join(_args[0]))
            self.assertIn("creationflags", kwargs)
        finally:
            mestre.encerrar_log_de_sessao()
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_nao_abre_terminal_com_diagnostico_off(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            sessao, _ = self._sessao(tmp_dir)
            with mock.patch.object(mestre, "RESULTS_DIR", tmp_dir), \
                 mock.patch.object(mestre, "DIAGNOSTICO_MODE", False), \
                 mock.patch.object(mestre, "BENCH_MODE", True), \
                 mock.patch("cli.subprocess.Popen") as popen_mock:
                sessao._garantir_pasta_sessao()
            mestre.encerrar_log_de_sessao()
            popen_mock.assert_not_called()
        finally:
            mestre.encerrar_log_de_sessao()
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_nao_abre_terminal_em_modo_simulado(self):
        """diagnostico on sozinho não basta — sem captura FÍSICA não há SCPI
        de verdade para acompanhar."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            sessao, _ = self._sessao(tmp_dir)
            with mock.patch.object(mestre, "RESULTS_DIR", tmp_dir), \
                 mock.patch.object(mestre, "DIAGNOSTICO_MODE", True), \
                 mock.patch.object(mestre, "BENCH_MODE", False), \
                 mock.patch("cli.subprocess.Popen") as popen_mock:
                sessao._garantir_pasta_sessao()
            mestre.encerrar_log_de_sessao()
            popen_mock.assert_not_called()
        finally:
            mestre.encerrar_log_de_sessao()
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_opt_out_por_variavel_de_ambiente(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            import cli
            sessao, _ = self._sessao(tmp_dir)
            with mock.patch.object(mestre, "RESULTS_DIR", tmp_dir), \
                 mock.patch.object(mestre, "DIAGNOSTICO_MODE", True), \
                 mock.patch.object(mestre, "BENCH_MODE", True), \
                 mock.patch.object(cli, "DIAGNOSTICO_ABRIR_TERMINAL", False), \
                 mock.patch("cli.subprocess.Popen") as popen_mock:
                sessao._garantir_pasta_sessao()
            mestre.encerrar_log_de_sessao()
            popen_mock.assert_not_called()
        finally:
            mestre.encerrar_log_de_sessao()
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_falha_ao_abrir_terminal_nao_derruba_a_sessao(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            sessao, _ = self._sessao(tmp_dir)
            with mock.patch.object(mestre, "RESULTS_DIR", tmp_dir), \
                 mock.patch.object(mestre, "DIAGNOSTICO_MODE", True), \
                 mock.patch.object(mestre, "BENCH_MODE", True), \
                 mock.patch("cli.subprocess.Popen", side_effect=FileNotFoundError("powershell.exe")), \
                 self.assertLogs("cli", level="WARNING"):
                sessao._garantir_pasta_sessao()  # NÃO pode levantar
            mestre.encerrar_log_de_sessao()
            self.assertTrue(mestre.SESSION_RESULTS_DIR.is_dir())
        finally:
            mestre.encerrar_log_de_sessao()
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_fecha_terminal_anterior_antes_de_abrir_o_proximo(self):
        """2 'run's na mesma sessão de CLI: só uma janela de tail por vez,
        sempre acompanhando a pasta do run ATUAL — a do run anterior (que
        aponta pra uma pasta antiga) é encerrada antes de abrir a nova."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            sessao, _ = self._sessao(tmp_dir)
            processo_1 = mock.Mock(poll=lambda: None)  # ainda "rodando"
            with mock.patch.object(mestre, "RESULTS_DIR", tmp_dir), \
                 mock.patch.object(mestre, "DIAGNOSTICO_MODE", True), \
                 mock.patch.object(mestre, "BENCH_MODE", True), \
                 mock.patch("cli.subprocess.Popen") as popen_mock:
                popen_mock.side_effect = [processo_1, mock.Mock(poll=lambda: None)]
                sessao._garantir_pasta_sessao()
                sessao._garantir_pasta_sessao()
            mestre.encerrar_log_de_sessao()
            self.assertEqual(popen_mock.call_count, 2)
            processo_1.terminate.assert_called_once()
        finally:
            mestre.encerrar_log_de_sessao()
            shutil.rmtree(tmp_dir, ignore_errors=True)


class PosicaoDoTriggerTests(unittest.TestCase):
    """P07 — H-REF10 (relatório 01 §0 ACHADO 1, confirmada em 02 A1-A6).

    ``:TIMebase:REFerence LEFT`` põe a referência a UMA DIVISÃO da borda
    esquerda ([KS] p. 1337), ou seja 10% do ``RANGe`` ([KS] p. 1335), e
    ``get_waveform()`` descartava ``x_origin`` — o único campo da preamble que
    diz onde o trigger caiu ([KS] p. 1476). Resultado: o trigger caía em
    ``pre_trigger + janela/10`` e ninguém sabia."""

    def test_referencia_horizontal_e_a_borda_esquerda_de_verdade(self):
        adapter = ScriptedAdapter()
        scope = KeysightDSOX4034A(adapter)
        scope.initialize_safe()
        scope.configure_acquisition(pre_trigger_s=0.060)
        joined = chr(10).join(adapter.commands)
        self.assertIn(":TIMebase:REFerence CUSTom", joined)
        self.assertIn(":TIMebase:REFerence:LOCation 0", joined)
        # com a referência na borda esquerda, POSition volta a ser só
        # -pre_trigger (sem compensação de 1 divisão)
        self.assertIn(":TIMebase:POSition -0.06", joined)
        self.assertEqual(scope.referencia_horizontal_efetiva, "CUSTOM")

    def test_fallback_compensa_a_divisao_quando_custom_nao_existe(self):
        """Se o firmware não aceitar CUSTom, a posição do trigger continua
        CONHECIDA: compensa-se a divisão no comando e o desvio fica
        registrado — nunca se deixa o erro de 10% em silêncio."""
        adapter = ScriptedAdapter()
        adapter.referencia_horizontal = "LEFT"  # firmware ignorou o CUSTom
        scope = KeysightDSOX4034A(adapter)
        scope.initialize_safe()
        with self.assertLogs("KeysightDSOX4034A", level="WARNING"):
            scope.configure_acquisition(duration_s=0.2, pre_trigger_s=0.060)
        joined = chr(10).join(adapter.commands)
        self.assertIn(":TIMebase:REFerence LEFT", joined)
        # -(0,060) + 0,200/10 = -0,04
        self.assertIn(":TIMebase:POSition -0.04", joined)
        self.assertEqual(scope.referencia_horizontal_efetiva, "LEFT")

    def test_get_waveform_calcula_indice_do_trigger_pela_preamble(self):
        adapter = ScriptedAdapter()
        # x_origin = -0,4 s, x_increment = 1/30000 -> trigger na amostra 12000
        adapter.preamble = "0,0,30000,1,3.3333333333333e-5,-0.4,0,0.01,0,128"
        adapter.connection.pontos = 30000
        scope = KeysightDSOX4034A(adapter)
        scope.initialize_safe()
        tempo, valores = scope.get_waveform(1, expected_points=30000)
        self.assertEqual(scope.ultimo_indice_trigger, 12000)
        self.assertAlmostEqual(scope.ultimo_x_origin, -0.4, places=9)
        self.assertEqual(tempo.shape, (30000,))

    def test_indice_do_trigger_e_na_grade_de_30ksa_devolvida_nao_na_bruta(self):
        """Sessão 2026-09-30: o Keysight amostrou a ~116,7 kSa/s e
        ``indice_trigger`` saiu 2333 (amostras BRUTAS em 20 ms), mas o array
        devolvido é reamostrado a 30 kSa/s, onde o trigger está na amostra
        600 — o sinal real começava exatamente ali."""
        adapter = ScriptedAdapter()
        x_inc = 0.02 / 2333.0
        adapter.preamble = f"0,0,31500,1,{x_inc!r},-0.02,0,0.01,0,128"
        adapter.connection.pontos = 31500
        scope = KeysightDSOX4034A(adapter)
        scope.initialize_safe()
        tempo, _ = scope.get_waveform(1, expected_points=8100)
        self.assertEqual(tempo.shape, (8100,))
        self.assertEqual(scope.ultimo_indice_trigger, 600)

    def test_cobertura_minima_acompanha_a_janela_pedida(self):
        """O teste antigo era chumbado em 0,2 s: com margin on (janela maior)
        ele aceitava um registro curto demais. Passa a exigir
        ``expected_points/30000``."""
        adapter = ScriptedAdapter()
        adapter.preamble = "0,0,6000,1,3.3333333333333e-5,-0.02,0,0.01,0,128"
        scope = KeysightDSOX4034A(adapter)
        scope.initialize_safe()
        with self.assertRaises(OscilloscopeError):
            scope.get_waveform(1, expected_points=8100)


class JanelaNominalEAnaliseTests(unittest.TestCase):
    """P08 — recorte e análise offline passam a usar ``indice_trigger`` e o
    contexto gravado no metadata, em vez de ``margem_amostras_antes`` e de
    60 Hz/127 V chumbados (relatório 01 §1.1 e §4 item 8)."""

    def test_janela_nominal_desconta_o_pre_trigger_da_classe(self):
        registro = np.arange(8100, dtype=np.float64)
        janela = sinais.janela_nominal(
            registro, indice_trigger=600, pre_trigger_s=0.0, pontos=6000, fs_hz=30_000.0,
        )
        self.assertEqual(janela[0], 600.0)
        # classe PULSe: o evento começa no trigger e gerar() o quer em 60 ms
        janela_pulse = sinais.janela_nominal(
            registro, indice_trigger=2400, pre_trigger_s=0.060, pontos=6000, fs_hz=30_000.0,
        )
        self.assertEqual(janela_pulse[0], 2400.0 - 1800.0)

    def test_janela_nominal_nao_estoura_o_registro(self):
        registro = np.arange(6000, dtype=np.float64)
        janela = sinais.janela_nominal(
            registro, indice_trigger=5000, pre_trigger_s=0.0, pontos=6000, fs_hz=30_000.0,
        )
        self.assertEqual(janela.size, 6000)

    def test_analisar_sessao_usa_f0_e_tensao_base_do_metadata(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            sessao_dir = tmp_dir / "sessao_teste"
            (sessao_dir / "metadata").mkdir(parents=True)
            fs_hz, pontos = 30_000.0, 6000
            t = np.arange(pontos, dtype=np.float64) / fs_hz
            capturado = np.sin(2.0 * np.pi * 50.0 * t)  # sessão de 50 Hz
            np.savez(
                sessao_dir / "01_normal_cap01.npz",
                tempo_ms=t * 1000.0, tensao_pu=capturado[np.newaxis, :],
                classe="NORMAL", id_captura=np.array(["01-0001"], dtype=object),
            )
            with (sessao_dir / "metadata" / "01_normal.jsonl").open("w", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "classe": "NORMAL", "fs_hz": fs_hz, "id_captura": "01-0001",
                    "parametros": {}, "pontos": pontos, "seed": 21260827, "simulado": False,
                    "nivel_indice": 0, "f0_hz": 50.0, "tensao_base_rms": 220.0,
                    "pre_trigger_s": 0.0, "indice_trigger": 0,
                }) + chr(10))
            import analisar_sessao
            import importlib
            importlib.reload(analisar_sessao)
            relatorio = analisar_sessao.analisar_sessao(sessao_dir)
            self.assertEqual(len(relatorio), 1)
            self.assertNotIn("erro", relatorio[0])
            # com f0 correto a correlação é ~1; com 60 Hz chumbado seria baixa
            self.assertGreater(relatorio[0]["correlacao"], 0.99)
            self.assertEqual(relatorio[0]["f0_hz"], 50.0)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class CapturaDescartavelTests(unittest.TestCase):
    """P09 — uma captura com erro descartável (InstrumentHardwareError,
    TimeoutError, ValueError de _validar_captura) é logada e PULADA — não
    retenta a classe inteira, não aborta a bateria.

    Decisão de projeto de 2026-09-22, motivada pela medida dos ensaios
    p01/p02 (a captura falha na hora): não abortar a bateria por uma captura,
    só registrar e descartar, porque abortar custa reexecutar a classe
    inteira. Antes deste patch,
    QUALQUER InstrumentHardwareError dentro de _capturar_real() (erro 19 do
    p01, divergência de readback do p02) propagava para fora do laço de
    executar() e disparava o retry de CLASSE INTEIRA de executar_bateria()
    (até 3×, refazendo do zero até as capturas que já tinham dado certo) —
    exatamente o custo que a decisão de projeto evita para uma falha isolada."""

    def _config(self, results_dir, **overrides):
        base = dict(
            fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=results_dir,
            sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
            capturas_override=5,
        )
        base.update(overrides)
        return mestre.Config(**base)

    def _experimento(self, config, falhas=None):
        """``falhas``: dict {n_da_chamada (1-based): excecao_a_levantar}."""
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
        bancada = mestre.Bancada(fonte, mock.Mock(), config)

        class _Classe(mestre.ExperimentoNativo):
            id = "97"
            nome = "TESTE_DESCARTE"

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

            def configurar(self, capture_index):
                return {}

        experimento = _Classe(bancada)
        experimento.osc = mock.Mock()
        # Este teste é sobre a lógica de descarte, não sobre margem (P10) —
        # neutraliza a folga fixa para os stubs poderem devolver arrays do
        # tamanho nominal de sempre.
        experimento._calcular_margem = lambda **kw: (0, 0, kw["config_points"])
        pontos = config.points
        tempo_s = np.arange(pontos, dtype=np.float64) / config.fs_hz
        chamadas = {"n": 0}
        falhas = falhas or {}

        def _stub(capture_index, t, rng):
            chamadas["n"] += 1
            if chamadas["n"] in falhas:
                raise falhas[chamadas["n"]]
            return tempo_s, np.sin(2.0 * np.pi * 60.0 * tempo_s), None, {}

        experimento._capturar_real = _stub
        experimento._preparar_acquisicao_real = lambda: None
        return experimento, chamadas

    def test_uma_captura_com_erro_descartavel_nao_aborta_as_demais(self):
        """5 capturas planejadas, a 3ª levanta InstrumentHardwareError (erro
        19 simulado). As outras 4 devem sair normalmente, SEM exceção."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados")
            experimento, chamadas = self._experimento(
                config, falhas={3: InstrumentHardwareError("erro 19 simulado")},
            )
            with self.assertLogs("MestreExperimentos", level="ERROR") as captura:
                experimento.executar()  # NÃO pode levantar
            self.assertEqual(chamadas["n"], 5, "as 5 posições do plano devem ser tentadas")
            arquivos = _capturas_gravadas(tmp_dir / "resultados", "97")
            self.assertEqual(len(arquivos), 4, f"esperava 4 capturas boas, achei {arquivos}")
            self.assertTrue(
                any("DESCARTADA" in m for m in captura.output),
                "precisa logar claramente que a captura foi descartada",
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_timeout_error_tambem_e_descartavel(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados", capturas_override=3)
            experimento, chamadas = self._experimento(
                config, falhas={2: TimeoutError("AMETEK não entrou em ARM/WTRIG")},
            )
            experimento.executar()
            arquivos = _capturas_gravadas(tmp_dir / "resultados", "97")
            self.assertEqual(len(arquivos), 2)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_captura_descartada_nao_dispara_retry_de_classe_na_bateria(self):
        """No nível de executar_bateria(): a classe deve rodar UMA vez só
        (não 3×) quando algumas capturas internas são descartadas mas a
        classe como um todo termina com dado bom."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados")
            fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
            bancada = mestre.Bancada(fonte, mock.Mock(), config)
            chamadas_executar = {"n": 0}

            class _Classe(mestre.ExperimentoNativo):
                id = "97"
                nome = "TESTE_DESCARTE"

                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {}

                def configurar(self, capture_index):
                    return {}

                def executar(self):
                    chamadas_executar["n"] += 1
                    # Simula o comportamento real de ExperimentoBase.executar():
                    # 1 de 5 capturas descartada, classe termina OK.

            with mock.patch.object(
                mestre.Bancada, "_carregar_classe_experimento",
                staticmethod(lambda script_path: _Classe),
            ), mock.patch.object(mestre.Bancada, "recuperar_estado_seguro", lambda self: None):
                resultados = bancada.executar_bateria([Path("97.py")])
            self.assertEqual(chamadas_executar["n"], 1, "classe sem exceção não pode ser retentada")
            self.assertTrue(resultados[0].ok)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_todas_as_capturas_descartadas_ainda_falha_a_classe(self):
        """Rede de segurança: se TODAS as capturas planejadas forem
        descartadas, a classe não pode terminar silenciosamente como OK com
        zero arquivos — isso ainda precisa levantar (e ainda pode ser
        retentado pela bateria, ao contrário do caso comum de 1-em-N)."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados", capturas_override=3)
            experimento, chamadas = self._experimento(
                config, falhas={
                    1: InstrumentHardwareError("erro 19"),
                    2: InstrumentHardwareError("erro 19"),
                    3: InstrumentHardwareError("erro 19"),
                },
            )
            with self.assertRaises(InstrumentHardwareError):
                experimento.executar()
            self.assertEqual(len(list((tmp_dir / "resultados").glob("97_*.npz"))), 0)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_communication_error_continua_propagando_na_hora_para_abortar_bateria(self):
        """CRÍTICO: CommunicationError (serial caiu) NUNCA pode ser tratada
        como descarte-e-continua — precisa propagar imediatamente para
        executar_bateria() abortar a bateria inteira (AGENTS.md: não ampliar
        o que conta como falha recuperável sem entender a fundo)."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados", capturas_override=5)
            experimento, chamadas = self._experimento(
                config, falhas={2: CommunicationError("porta serial caiu")},
            )
            with self.assertRaises(CommunicationError):
                experimento.executar()
            self.assertEqual(chamadas["n"], 2, "não pode tentar as capturas seguintes após a serial cair")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_runtime_error_de_gerar_nao_e_descartado(self):
        """RuntimeError (forma inválida de gerar()) indica um BUG na classe,
        não uma falha intermitente de hardware — não deve ser silenciosamente
        descartada captura a captura até sobrar zero; propaga na hora."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados", capturas_override=3)
            experimento, chamadas = self._experimento(
                config, falhas={1: RuntimeError("bug: forma com shape errado")},
            )
            with self.assertRaises(RuntimeError):
                experimento.executar()
            self.assertEqual(chamadas["n"], 1, "não deve tentar as próximas capturas depois de um bug")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_captura_fisicamente_invalida_nao_aborta_classe_com_boas_misturadas(self):
        """P05 já não abortava a captura seguinte (só reprovava no fim se
        HOUVESSE alguma inválida). Este teste confirma o refinamento: com
        1 boa + 1 inválida, a classe agora passa (fica só o aviso no log e a
        marca 'validacao_fisica.ok=false' no metadata) — só falha se NENHUMA
        captura da classe for fisicamente válida (ver
        ValidacaoFisicaTests.test_classe_marca_metadata_e_falha_sem_retry_quando_invalida,
        que continua cobrindo o caso de 100% inválido)."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = mestre.Config(
                fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
                base_voltage_rms=220.0, snr_levels_db=(), base_seed=1,
                capture_current=False, current_base_a=None, results_dir=tmp_dir / "resultados",
                sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
                capturas_override=2,
            )
            fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
            bancada = mestre.Bancada(fonte, mock.Mock(), config)

            class _Classe(mestre.ExperimentoNativo):
                id = "01"
                nome = "NORMAL"

                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {}

                def configurar(self, capture_index):
                    return {}

            experimento = _Classe(bancada)
            experimento.osc = mock.Mock()
            experimento._calcular_margem = lambda **kw: (0, 0, kw["config_points"])
            tempo_s = np.arange(6000, dtype=np.float64) / 30_000.0
            chamadas = {"n": 0}

            def _stub(ci, t, rng):
                chamadas["n"] += 1
                # 1ª captura: correta (220V). 2ª: sai a 127V (H-NATIVO).
                razao = 1.0 if chamadas["n"] == 1 else 127.0 / 220.0
                return tempo_s, np.sin(2.0 * np.pi * 60.0 * tempo_s) * razao, None, {}

            experimento._capturar_real = _stub
            experimento._preparar_acquisicao_real = lambda: None
            experimento.executar()  # NÃO pode levantar: 1 de 2 é boa
            metadata = config.results_dir / "metadata" / "01_normal.jsonl"
            registros = [
                json.loads(l) for l in metadata.read_text(encoding="utf-8").splitlines() if l.strip()
            ]
            self.assertEqual(len(registros), 2, "as duas capturas continuam gravadas")
            self.assertTrue(registros[0]["validacao_fisica"]["ok"])
            self.assertFalse(registros[1]["validacao_fisica"]["ok"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_resultado_classe_registra_contagem_de_descartes_e_invalidas(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados")
            fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
            bancada = mestre.Bancada(fonte, mock.Mock(), config)

            class _ClasseReal(mestre.ExperimentoNativo):
                id = "97"
                nome = "TESTE_DESCARTE"

                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {}

                def configurar(self, capture_index):
                    return {}

            experimento_instancia = _ClasseReal(bancada)
            experimento_instancia.osc = mock.Mock()
            experimento_instancia._calcular_margem = lambda **kw: (0, 0, kw["config_points"])
            tempo_s = np.arange(6000, dtype=np.float64) / 30_000.0
            chamadas = {"n": 0}

            def _stub(ci, t, rng):
                chamadas["n"] += 1
                if chamadas["n"] == 3:
                    raise InstrumentHardwareError("erro 19 simulado")
                return tempo_s, np.sin(2.0 * np.pi * 60.0 * tempo_s), None, {}

            experimento_instancia._capturar_real = _stub
            experimento_instancia._preparar_acquisicao_real = lambda: None

            with mock.patch.object(
                mestre.Bancada, "_carregar_classe_experimento",
                staticmethod(lambda script_path: _ClasseReal),
            ), mock.patch.object(
                mestre.Bancada, "_instanciar_experimento",
                lambda self, cls: experimento_instancia,
            ):
                resultados = bancada.executar_bateria([Path("97.py")])
            self.assertTrue(resultados[0].ok)
            self.assertEqual(resultados[0].descartadas, 1)
            self.assertEqual(resultados[0].invalidas, 0)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _carregar_classe(experiment_id: str):
    """Classe Experimento de um NN.py, sem instanciar (ver _load_experimento)."""
    name = f"{experiment_id}.py"
    candidates = [directory / name for directory in EXPERIMENT_DIRS if (directory / name).is_file()]
    assert len(candidates) == 1, f"{name}: encontrado em {candidates}"
    return mestre.Bancada._carregar_classe_experimento(candidates[0])


def _config_bancada(results_dir, **overrides):
    base = dict(
        fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
        base_voltage_rms=127.0, snr_levels_db=(), base_seed=20_260_827,
        capture_current=False, current_base_a=None, results_dir=results_dir,
        sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
        # Estes testes cobrem a MECÂNICA da bancada (limite, pré-validação,
        # metadata) com as posições fixas de antes da v1.15; o sorteio de
        # início/duração/fase tem a classe de testes própria
        # (SorteioInicioDuracaoFaseTests), que liga o campo explicitamente.
        sorteio_posicao=False,
    )
    base.update(overrides)
    return mestre.Config(**base)


def _executar_classe_real_com_stub(experiment_id, config, *, max_peak_v=415.8):
    """Roda ``executar()`` de uma classe REAL no caminho de BANCADA (osc
    não-None) sem instrumento: fonte simulada com os limites da bancada
    (300 Vrms / ``max_peak_v``) e ``_capturar_real`` trocado por um stub que
    devolve a forma que a classe programaria (``forma_prevista_para_bancada``
    com a MESMA seed). Devolve (metadados gravados, formas programadas)."""
    experimento_cls = _carregar_classe(experiment_id)
    fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=max_peak_v)
    osc = mock.Mock()
    osc.medir_extremos = lambda canal: (100.0, -100.0)
    bancada = mestre.Bancada(fonte, osc, config)
    experimento = experimento_cls(bancada)
    experimento._calcular_margem = lambda **kw: (0, 0, kw["config_points"])
    experimento._preparar_acquisicao_real = lambda: None
    formas = []

    def _stub(capture_index, t, rng):
        # A seed do rng recebido é a de executar(); reproduzimos a forma pela
        # mesma seed (o rng ainda não foi consumido aqui).
        seed = int(rng.bit_generator.seed_seq.entropy)
        voltage_pu, parametros = experimento.gerar(
            t, config.grid_frequency_hz, capture_index, np.random.default_rng(seed),
        )
        forma = np.asarray(voltage_pu, dtype=np.float64)
        if isinstance(experimento, mestre.ExperimentoWaveform):
            forma = np.asarray(experimento.forma_para_bancada(forma, parametros, capture_index))
            experimento._forma_programada_pu = forma
        formas.append(forma)
        return t, forma, None, parametros

    experimento._capturar_real = _stub
    experimento.executar()
    metadata_path = config.results_dir / "metadata" / f"{experimento.id}_{experimento.nome.lower()}.jsonl"
    registros = [json.loads(linha) for linha in metadata_path.read_text(encoding="utf-8").splitlines()]
    return registros, formas


class CapturasPadraoPorClasseTests(unittest.TestCase):
    """v1.13, Tarefa 1 — cada classe tem um número PADRÃO de capturas na
    bancada (``capturas_padrao``). Decisão de projeto (v1.13): 3 nas classes
    que sorteiam parâmetros em ``gerar()``, 1 nas determinísticas."""

    COM_SORTEIO = {"04", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "19", "20"}

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_tabela_de_padroes_e_a_pedida_pelo_dono(self):
        for indice in range(1, 21):
            classe_id = f"{indice:02d}"
            esperado = 3 if classe_id in self.COM_SORTEIO else 1
            self.assertEqual(_carregar_classe(classe_id).capturas_padrao, esperado, classe_id)

    def test_padrao_da_base_e_1(self):
        self.assertEqual(mestre.ExperimentoBase.capturas_padrao, 1)

    def test_config_sem_override_usa_o_maior_entre_global_e_padrao(self):
        config = _config_bancada(self.tmp_dir, capturas_padrao_classe=3)
        self.assertEqual(config.capturas(simulated=False), 3)
        self.assertEqual(replace_config(config, real_captures_per_class=5).capturas(False), 5)

    def test_padrao_nao_muda_o_dataset_simulado(self):
        config = _config_bancada(self.tmp_dir, sim_captures_per_class=2000, capturas_padrao_classe=3)
        self.assertEqual(config.capturas(simulated=True), 2000)

    def test_init_injeta_o_padrao_sem_mexer_na_config_da_bancada(self):
        config = _config_bancada(self.tmp_dir)
        bancada = mestre.Bancada(None, None, config)
        experimento = _carregar_classe("04")(bancada)
        self.assertEqual(experimento.config.capturas_padrao_classe, 3)
        self.assertEqual(bancada.config.capturas_padrao_classe, 1)
        self.assertEqual(experimento.config.capturas(False), 3)

    def test_padrao_invalido_e_recusado(self):
        class _Invalida(mestre.ExperimentoWaveform):
            id = "96"
            nome = "INVALIDA"
            capturas_padrao = 0

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

        with self.assertRaises(ValueError):
            _Invalida(mestre.Bancada(None, None, _config_bancada(self.tmp_dir)))

    def test_classe_com_sorteio_roda_3_capturas_sorteadas_sem_set_capturas(self):
        registros, _ = _executar_classe_real_com_stub("04", _config_bancada(self.tmp_dir))
        self.assertEqual(len(registros), 3)
        niveis = [registro["parametros"]["interruption_pu"] for registro in registros]
        # Sorteio (não cobertura): não bate nas pontas 0 / 0,09 do linspace.
        self.assertEqual(len(set(niveis)), 3)
        self.assertNotIn(0.0, niveis)
        self.assertNotIn(0.09, niveis)

    def test_classe_deterministica_continua_com_1(self):
        registros, _ = _executar_classe_real_com_stub("18", _config_bancada(self.tmp_dir))
        self.assertEqual(len(registros), 1)

    def test_classe_com_niveis_e_padrao_maior_que_1_agrupa_por_nivel(self):
        class _ComNiveis(mestre.ExperimentoNativo):
            id = "97"
            nome = "TESTE_NIVEIS"
            NIVEIS = (0.1, 0.3, 0.5, 0.7, 0.9)
            capturas_padrao = 2

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

            def configurar(self, capture_index):
                return {}

        experimento = _ComNiveis(mestre.Bancada(None, None, _config_bancada(self.tmp_dir)))
        self.assertEqual(experimento.dimensionar_capturas(False), (True, 2, 10))
        self.assertEqual(
            [nivel for _, nivel in experimento.plano_de_capturas(False)],
            [0, 0, 1, 1, 2, 2, 3, 3, 4, 4],
        )

    def test_classe_com_niveis_e_padrao_1_roda_so_o_nivel_0_como_antes(self):
        experimento = _carregar_classe("02")(mestre.Bancada(None, None, _config_bancada(self.tmp_dir)))
        self.assertEqual(experimento.plano_de_capturas(False), [(0, 0)])

    def test_08_com_padrao_3_sem_set_capturas_nao_caracteriza(self):
        registros, _ = _executar_classe_real_com_stub("08", _config_bancada(self.tmp_dir))
        self.assertEqual(len(registros), 3)
        amplitudes = {round(registro["parametros"]["amplitude_bancada_pu"], 9) for registro in registros}
        self.assertEqual(len(amplitudes), 1)  # todas no máximo seguro, sem rampa
        self.assertTrue(all(registro["parametros"]["caracterizacao"] == 0.0 for registro in registros))

    def test_capturas_efetivas_da_classe_e_escritas_de_trace(self):
        config = _config_bancada(self.tmp_dir)
        info = mestre.capturas_efetivas_da_classe(_carregar_classe("06"), config)
        self.assertEqual((info["padrao"], info["total"], info["escritas_trace"]), (3, 3, 36))
        info = mestre.capturas_efetivas_da_classe(_carregar_classe("04"), config)
        self.assertEqual((info["total"], info["escritas_trace"]), (3, 0))
        # 05 só grava TRACe no nível de 30% (usar_trace), que só roda agrupado por nível.
        info = mestre.capturas_efetivas_da_classe(_carregar_classe("05"), replace_config(config, capturas_override=1))
        self.assertEqual((info["niveis"], info["total"], info["escritas_trace"]), (5, 5, 12))


def replace_config(config, **campos):
    import dataclasses
    return dataclasses.replace(config, **campos)


class CliCapturasTests(unittest.TestCase):
    def setUp(self):
        import cli
        self.cli = cli
        self._override = mock.patch.object(mestre, "CAPTURAS_OVERRIDE", None)
        self._override.start()

    def tearDown(self):
        self._override.stop()

    def _rodar(self, metodo, args):
        import io
        from contextlib import redirect_stdout
        saida = io.StringIO()
        with redirect_stdout(saida):
            codigo = metodo(args)
        return codigo, saida.getvalue()

    def test_ctrl_c_num_comando_volta_ao_prompt(self):
        """Bancada 2026-10-07: o Ctrl+C não parava a bateria (NI-VISA
        descartava o evento; ver mestre.garantir_ctrl_c_no_windows). Agora
        ele chega como KeyboardInterrupt — a CLI avisa e continua."""
        chamadas = []

        def _interrompido(_sessao, _args):
            chamadas.append("run")
            raise KeyboardInterrupt

        def _status(_sessao, _args):
            chamadas.append("status")

        sessao = self.cli.SessaoCLI()
        comandos = dict(self.cli.SessaoCLI.COMANDOS, run=_interrompido, status=_status)
        with mock.patch.object(self.cli.SessaoCLI, "COMANDOS", comandos), \
                mock.patch("builtins.input", side_effect=["run all", "status", EOFError]):
            codigo, saida = self._rodar(lambda _args: sessao.loop(), [])
        self.assertEqual(codigo, 0)
        self.assertEqual(chamadas, ["run", "status"])
        self.assertIn("INTERROMPIDO pelo operador", saida)

    def test_list_mostra_capturas_efetivas_e_padrao(self):
        codigo, saida = self._rodar(self.cli.SessaoCLI().cmd_list, [])
        self.assertEqual(codigo, 0)
        linha_04 = next(linha for linha in saida.splitlines() if linha.strip().startswith("04"))
        self.assertIn("capturas 3 (padrão 3)", linha_04)
        linha_01 = next(linha for linha in saida.splitlines() if linha.strip().startswith("01"))
        self.assertIn("capturas 1 (padrão 1)", linha_01)

    def test_status_mostra_capturas_por_classe_e_nao_quebra(self):
        codigo, saida = self._rodar(self.cli.SessaoCLI().cmd_status, [])
        self.assertEqual(codigo, 0)
        self.assertIn("04=3", saida)
        # Sorteio ligado (padrão): a conta é exata, cada captura TRACE regrava a Flash.
        self.assertIn("468 gravações na Flash", saida)  # 300 + 7 compostas x 2 capturas a mais x 12 ciclos (v1.15)
        self.assertIn("cada captura TRACE grava a Flash", saida)
        with mock.patch.object(self.cli.mestre, "SORTEIO_POSICAO", False):
            _, saida_sem = self._rodar(self.cli.SessaoCLI().cmd_status, [])
        self.assertIn("TRACe: até 468 gravações", saida_sem)

    def test_set_capturas_padrao_desfaz_o_override(self):
        sessao = self.cli.SessaoCLI()
        self._rodar(sessao.cmd_set, ["capturas", "4"])
        self.assertEqual(mestre.CAPTURAS_OVERRIDE, 4)
        codigo, _ = self._rodar(sessao.cmd_set, ["capturas", "padrao"])
        self.assertEqual(codigo, 0)
        self.assertIsNone(mestre.CAPTURAS_OVERRIDE)



class SeedReprodutivelTests(unittest.TestCase):
    """v1.13, Tarefa 2 — ``set seed N`` na CLI: mesma seed => mesmas formas
    programadas, mesmos parâmetros e mesmo plano; seed diferente =>
    parâmetros diferentes nas classes com sorteio."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _rodar(self, classe_id, seed, pasta, **overrides):
        config = _config_bancada(self.tmp_dir / pasta, base_seed=seed, **overrides)
        return _executar_classe_real_com_stub(classe_id, config)

    def test_mesma_seed_reproduz_formas_parametros_e_plano(self):
        for classe_id in ("04", "06", "07", "09", "17", "19", "20"):
            registros_a, formas_a = self._rodar(classe_id, 1234, f"a{classe_id}")
            registros_b, formas_b = self._rodar(classe_id, 1234, f"b{classe_id}")
            self.assertEqual(
                [(r["id_captura"], r["seed"], r["nivel_indice"]) for r in registros_a],
                [(r["id_captura"], r["seed"], r["nivel_indice"]) for r in registros_b],
                classe_id,
            )
            self.assertEqual([r["parametros"] for r in registros_a], [r["parametros"] for r in registros_b])
            for forma_a, forma_b in zip(formas_a, formas_b):
                np.testing.assert_array_equal(forma_a, forma_b)

    def test_seed_diferente_muda_os_parametros_sorteados(self):
        for classe_id in ("04", "06", "09", "19", "20"):
            registros_a, _ = self._rodar(classe_id, 1234, f"a{classe_id}")
            registros_b, _ = self._rodar(classe_id, 98765, f"b{classe_id}")
            self.assertNotEqual(
                [r["parametros"] for r in registros_a], [r["parametros"] for r in registros_b], classe_id,
            )

    def test_seed_da_captura_e_a_formula_documentada(self):
        registros, _ = self._rodar("06", 1000, "f")
        self.assertEqual([r["seed"] for r in registros], [1000 + 6_000_000 + k for k in range(3)])

    def test_seed_zero_e_aceita(self):
        registros, _ = self._rodar("01", 0, "zero")
        self.assertEqual(registros[0]["seed"], 1_000_000)

    def test_metadata_grava_a_seed_base_e_o_modo_de_capturas(self):
        registros, _ = self._rodar("04", 4321, "m", capturas_override=2)
        self.assertEqual(registros[0]["base_seed"], 4321)
        self.assertEqual(registros[0]["capturas_override"], 2)
        self.assertEqual(registros[0]["capturas_padrao_classe"], 3)

    def test_env_base_seed_aceita_zero_e_vazio_e_recusa_negativo(self):
        with mock.patch.dict("os.environ", {"BASE_SEED": "0"}):
            self.assertEqual(mestre.env_int_nao_negativo("BASE_SEED", 7), 0)
        with mock.patch.dict("os.environ", {"BASE_SEED": "  "}):
            self.assertEqual(mestre.env_int_nao_negativo("BASE_SEED", 7), 7)
        with mock.patch.dict("os.environ", {"BASE_SEED": "-3"}):
            with self.assertRaises(ValueError):
                mestre.env_int_nao_negativo("BASE_SEED", 7)


class CliSeedTests(unittest.TestCase):
    def setUp(self):
        import cli
        self.cli = cli
        self._seed = mock.patch.object(mestre, "BASE_SEED", 20_260_827)
        self._seed.start()

    def tearDown(self):
        self._seed.stop()

    def _rodar(self, metodo, args):
        import io
        from contextlib import redirect_stdout
        saida = io.StringIO()
        with redirect_stdout(saida):
            codigo = metodo(args)
        return codigo, saida.getvalue()

    def test_set_seed_vale_no_proximo_build_config(self):
        sessao = self.cli.SessaoCLI()
        codigo, _ = self._rodar(sessao.cmd_set, ["seed", "42"])
        self.assertEqual(codigo, 0)
        self.assertEqual(mestre.BASE_SEED, 42)
        self.assertEqual(mestre._build_config().base_seed, 42)
        _, saida = self._rodar(sessao.cmd_status, [])
        self.assertIn("seed base: 42", saida)

    def test_set_seed_recusa_negativo_e_texto(self):
        sessao = self.cli.SessaoCLI()
        for valor in ("-1", "abc"):
            codigo, _ = self._rodar(sessao.cmd_set, ["seed", valor])
            self.assertEqual(codigo, 1, valor)
        self.assertEqual(mestre.BASE_SEED, 20_260_827)

    def test_set_seed_padrao_volta_a_seed_do_inicio(self):
        sessao = self.cli.SessaoCLI()
        self._rodar(sessao.cmd_set, ["seed", "5"])
        self._rodar(sessao.cmd_set, ["seed", "padrao"])
        self.assertEqual(mestre.BASE_SEED, 20_260_827)

    def test_help_documenta_set_seed(self):
        self.assertIn("set seed <N>", self.cli.HELP_TEXT)



class CapturasMaxCliPadraoTests(unittest.TestCase):
    """v1.13, Tarefa 3 — capturas efetivas = max(set capturas, padrão da
    classe), por nível nas classes com NIVEIS; capturas podadas pela
    pré-validação entram no log e no resumo."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _instancia(self, classe_id, **overrides):
        return _carregar_classe(classe_id)(mestre.Bancada(None, None, _config_bancada(self.tmp_dir, **overrides)))

    def test_config_max_entre_cli_e_padrao(self):
        config = _config_bancada(self.tmp_dir, capturas_padrao_classe=6, capturas_override=3)
        self.assertEqual(config.capturas(False), 6)
        self.assertEqual(replace_config(config, capturas_padrao_classe=1).capturas(False), 3)
        self.assertEqual(replace_config(config, capturas_override=None).capturas(False), 6)
        self.assertEqual(config.capturas(True), 1)  # simulado: SIM_CAPTURES_PER_CLASS

    def test_sem_override_vale_o_padrao(self):
        self.assertEqual(self._instancia("04").dimensionar_capturas(False), (False, 1, 3))
        self.assertEqual(self._instancia("01").dimensionar_capturas(False), (False, 1, 1))

    def test_override_menor_que_o_padrao_perde_e_cobertura_usa_o_total_efetivo(self):
        registros, _ = _executar_classe_real_com_stub("04", _config_bancada(self.tmp_dir, capturas_override=2))
        niveis = [registro["parametros"]["interruption_pu"] for registro in registros]
        np.testing.assert_allclose(niveis, [0.0, 0.045, 0.09])

    def test_override_maior_que_o_padrao_vence(self):
        self.assertEqual(self._instancia("04", capturas_override=5).dimensionar_capturas(False), (False, 1, 5))
        self.assertEqual(self._instancia("10", capturas_override=4).dimensionar_capturas(False), (False, 1, 4))

    def test_classe_com_niveis_aplica_o_max_por_nivel(self):
        self.assertEqual(self._instancia("02", capturas_override=2).dimensionar_capturas(False), (True, 2, 10))

        class _ComNiveis(mestre.ExperimentoNativo):
            id = "97"
            nome = "TESTE_NIVEIS"
            NIVEIS = (0.1, 0.3, 0.5, 0.7, 0.9)
            capturas_padrao = 3

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

            def configurar(self, capture_index):
                return {}

        experimento = _ComNiveis(mestre.Bancada(None, None, _config_bancada(self.tmp_dir, capturas_override=2)))
        self.assertEqual(experimento.dimensionar_capturas(False), (True, 3, 15))

    def test_08_com_set_capturas_menor_que_o_padrao_caracteriza_no_total_efetivo(self):
        registros, _ = _executar_classe_real_com_stub("08", _config_bancada(self.tmp_dir, capturas_override=2))
        amplitudes = [registro["parametros"]["amplitude_bancada_pu"] for registro in registros]
        self.assertEqual(len(amplitudes), 3)
        self.assertTrue(all(registro["parametros"]["caracterizacao"] == 1.0 for registro in registros))
        self.assertAlmostEqual(amplitudes[0], 0.25)
        self.assertTrue(amplitudes[0] < amplitudes[1] < amplitudes[2], amplitudes)

    def test_08_sem_set_capturas_nunca_caracteriza(self):
        registros, _ = _executar_classe_real_com_stub("08", _config_bancada(self.tmp_dir))
        self.assertTrue(all(registro["parametros"]["caracterizacao"] == 0.0 for registro in registros))

    def test_capturas_puladas_pela_pre_validacao_vao_para_o_resultado(self):
        """03 a 220 V com set capturas 1: 1,4/1,6/1,8 pu passam de 300 Vrms e
        1,2 pu passa do extremo previsto — 4 das 5 puladas, logado e contado."""
        config = _config_bancada(self.tmp_dir, base_voltage_rms=220.0, capturas_override=1)
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=415.8)
        osc = mock.Mock()
        osc.medir_extremos = lambda canal: (100.0, -100.0)
        bancada = mestre.Bancada(fonte, osc, config)
        experimento_cls = _carregar_classe("03")

        def _instanciar(_self, cls):
            experimento = cls(bancada)
            experimento._calcular_margem = lambda **kw: (0, 0, kw["config_points"])
            experimento._preparar_acquisicao_real = lambda: None

            def _stub(capture_index, t, rng):
                parametros = experimento.configurar(capture_index)
                forma, _ = experimento.gerar(t, 60.0, capture_index, rng)
                return t, forma, None, parametros

            experimento._capturar_real = _stub
            return experimento

        with mock.patch.object(mestre.Bancada, "_carregar_classe_experimento", staticmethod(lambda p: experimento_cls)), \
             mock.patch.object(mestre.Bancada, "_instanciar_experimento", _instanciar), \
             self.assertLogs("MestreExperimentos", level="WARNING") as logs:
            resultados = bancada.executar_bateria([Path("03.py")])
        self.assertTrue(resultados[0].ok)
        self.assertEqual(resultados[0].puladas, 4)
        self.assertTrue(any("PULADA(S) pela pré-validação" in linha for linha in logs.output), logs.output)

    def test_cli_avisa_quando_o_padrao_vence(self):
        import io
        from contextlib import redirect_stdout
        import cli
        saida = io.StringIO()
        with mock.patch.object(mestre, "CAPTURAS_OVERRIDE", None), redirect_stdout(saida):
            cli.SessaoCLI().cmd_set(["capturas", "2"])
        texto = saida.getvalue()
        self.assertIn("AVISO", texto)
        self.assertIn("04 (3)", texto)
        self.assertIn("CARACTERIZAÇÃO", texto)
        self.assertNotIn("01 (", texto)



def _carregar_script(nome):
    caminho = PROJECT_ROOT / "scripts" / f"{nome}.py"
    spec = importlib.util.spec_from_file_location(f"teste_script_{nome}", caminho)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LimiteDeBancada220VTests(unittest.TestCase):
    """v1.13, Tarefa 4 — opção (b) para 220 V: nas classes waveform
    cujo extremo previsto passa do teto, a captura FÍSICA reduz só o
    distúrbio até caber; gerar()/dataset não mudam; nativas continuam
    puladas."""

    TETO = 415.8

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _instancia(self, classe_id, base_v=220.0, **overrides):
        config = _config_bancada(self.tmp_dir, base_voltage_rms=base_v, **overrides)
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=self.TETO)
        return _carregar_classe(classe_id)(mestre.Bancada(fonte, mock.Mock(), config))

    def _avaliar_classe(self, classe_id, base_v=220.0, **overrides):
        experimento = self._instancia(classe_id, base_v, **overrides)
        return [experimento.avaliar_captura_na_bancada(ig, ci) for ig, ci in experimento.plano_de_capturas(False)]

    def test_formula_com_fracao_1_e_a_da_v1_12(self):
        self.assertAlmostEqual(
            mestre.extremo_previsto_com_disturbio_v(300.0, 300.0, 1.0, fator=1.459, fator_referencia=1.063),
            300.0 * 1.459 * mestre.MARGEM_FATOR_EXTREMO,
        )
        # Sem distúrbio sobra só a parte da senoide pura.
        self.assertAlmostEqual(
            mestre.extremo_previsto_com_disturbio_v(311.0, 311.0, 0.0, fator=1.459, fator_referencia=1.063),
            311.0 * 1.063 * mestre.MARGEM_FATOR_EXTREMO,
        )

    def test_fator_de_referencia_nunca_passa_do_da_classe(self):
        fatores = {"01": 1.063, "14": 0.977}
        self.assertEqual(mestre.fator_referencia_extremo(1.459, fatores), 1.063)
        self.assertEqual(mestre.fator_referencia_extremo(1.0, fatores), 1.0)
        self.assertEqual(mestre.fator_referencia_extremo(1.3, {"16": 1.3}), 1.3)  # sem a 01: conservador

    def test_127v_nada_e_reduzido_nem_pulado_e_extremo_e_o_da_v1_12(self):
        fatores = mestre.carregar_fatores_extremo()
        for indice in range(1, 21):
            classe_id = f"{indice:02d}"
            for info in self._avaliar_classe(classe_id, base_v=127.0):
                self.assertTrue(info["cabe"], (classe_id, info.get("motivo")))
                self.assertNotIn("fator_disturbio_bancada", info, classe_id)
                if classe_id != "08":
                    esperado = (
                        info["pico_programado_v"] * mestre.fator_extremo_da_classe(classe_id, fatores)
                        * mestre.MARGEM_FATOR_EXTREMO
                    )
                    self.assertAlmostEqual(info["extremo_previsto_v"], esperado, places=9, msg=classe_id)

    def test_220v_reduz_09_10_11_14_16_17_e_tudo_cabe_no_padrao(self):
        # Capturas recusadas a 220 V desde as recalibrações de 2026-10-22 (127 V/60 Hz):
        # 17 (1,575) nem com a redução mínima; 14 (1,200) idem; 05 (1,255), 18 (1,264)
        # e uma da 19 (1,119) são nativas, puladas por passar do teto (sem redução).
        recusadas_esperadas = {"05": 1, "14": 3, "17": 3, "18": 1, "19": 1}
        reduzidas = set()
        recusadas = {}
        for indice in range(1, 21):
            classe_id = f"{indice:02d}"
            for info in self._avaliar_classe(classe_id):
                if not info["cabe"]:
                    recusadas[classe_id] = recusadas.get(classe_id, 0) + 1
                    self.assertIn("teto", info["motivo"], classe_id)
                    continue
                self.assertTrue(info["cabe"], (classe_id, info.get("motivo")))
                self.assertLessEqual(info["extremo_previsto_v"], self.TETO + 1e-6, classe_id)
                if "fator_disturbio_bancada" in info:
                    reduzidas.add(classe_id)
                    fracao = info["fator_disturbio_bancada"]
                    self.assertGreaterEqual(fracao, mestre.LIMITE_BANCADA_FRACAO_MINIMA)
                    self.assertLess(fracao, 1.0)
                    # Bissecção: justo no teto, não muito abaixo.
                    self.assertGreater(info["extremo_previsto_v"], self.TETO - 1.0, classe_id)
        # 17: só na seed padrão (pico de 368 V × 1,031 × 1,10 = 417 V, 1 V acima).
        # 09: desde a recalibração de 2026-10-07 (fator 1,002 -> 1,036 a 127 V).
        # 07: desde a recalibração de 2026-10-22 (fator 1,186 -> 1,615 a 127 V).
        # 06, 12, 13: desde a recalibração com a campanha de 2026-10-22 (1,232; 1,47; 1,292).
        self.assertEqual(recusadas, recusadas_esperadas)
        self.assertEqual(reduzidas, {"06", "07", "09", "10", "11", "12", "13", "16"})

    def test_reducao_mantem_a_senoide_fora_do_disturbio_e_nao_muda_gerar(self):
        experimento = self._instancia("16")
        t = mestre.tempo(experimento.config)
        modelo_antes, parametros_modelo = experimento.gerar(t, 60.0, 0, np.random.default_rng(5))
        forma, parametros = experimento.forma_e_parametros_para_bancada(0, t, 5)
        modelo_depois, _ = experimento.gerar(t, 60.0, 0, np.random.default_rng(5))
        np.testing.assert_array_equal(modelo_antes, modelo_depois)
        janela = sinais.janela(t, 0.060, 0.060)
        senoide = np.sin(2.0 * np.pi * 60.0 * t)
        np.testing.assert_allclose(forma[~janela], senoide[~janela], atol=1e-12)
        fracao = parametros["fator_disturbio_bancada"]
        np.testing.assert_allclose(forma, senoide + fracao * (modelo_antes - senoide), atol=1e-12)
        self.assertEqual(parametros["interruption_pu"], parametros_modelo["interruption_pu"])  # rótulo do modelo
        self.assertAlmostEqual(parametros["interruption_pu_bancada"], 1.0 - fracao * 0.95)

    def test_parametros_bancada_batem_com_a_forma_aplicada(self):
        """Nível e THD na janela do distúrbio, medidos por FFT na forma
        reduzida, conferem com o que o gancho grava no metadata."""
        t = np.arange(6000, dtype=np.float64) / 30_000.0
        senoide = np.sin(2.0 * np.pi * 60.0 * t)
        trecho = slice(1800, 3300)  # 3 ciclos inteiros dentro de 60-120 ms
        for classe_id, chave_nivel in (("10", "sag_pu"), ("13", "swell_pu"), ("16", "interruption_pu")):
            experimento = self._instancia(classe_id)
            modelo, parametros = experimento.gerar(t, 60.0, 0, np.random.default_rng(0))
            fracao = 0.6
            forma = senoide + fracao * (np.asarray(modelo) - senoide)
            esperado = experimento.parametros_com_disturbio_reduzido(dict(parametros), fracao)
            espectro = np.abs(np.fft.rfft(forma[trecho])) * 2.0 / 1500
            fundamental = espectro[3]
            thd = math.sqrt(sum(espectro[3 * ordem] ** 2 for ordem in (3, 5, 7))) / fundamental
            self.assertAlmostEqual(fundamental, esperado[f"{chave_nivel}_bancada"], places=6, msg=classe_id)
            self.assertAlmostEqual(thd, esperado["thd_bancada"], places=6, msg=classe_id)

    def test_opcao_a_continua_disponivel_por_variavel(self):
        with mock.patch.object(mestre, "LIMITE_BANCADA_DISTURBIO", False):
            for classe_id in ("10", "11", "14", "16"):
                infos = self._avaliar_classe(classe_id)
                self.assertFalse(infos[0]["cabe"], classe_id)
                self.assertIn("extremo PREVISTO", infos[0]["motivo"])

    def test_fracao_abaixo_do_minimo_e_pulada_com_motivo(self):
        with mock.patch.object(mestre, "LIMITE_BANCADA_FRACAO_MINIMA", 0.5):
            info = self._avaliar_classe("16")[0]
        self.assertFalse(info["cabe"])
        self.assertIn("precisaria reduzir o distúrbio", info["motivo"])

    def test_nativas_nao_reduzem_03_continua_pulando_niveis(self):
        infos = self._avaliar_classe("03", capturas_override=1)
        self.assertEqual([info["cabe"] for info in infos], [True, False, False, False, False])
        self.assertTrue(all("fator_disturbio_bancada" not in info for info in infos))

    def test_captura_reduzida_grava_metadata_e_valida_contra_a_forma_programada(self):
        registros, formas = _executar_classe_real_com_stub("16", _config_bancada(self.tmp_dir, base_voltage_rms=220.0))
        registro = registros[0]
        self.assertIn("fator_disturbio_bancada", registro["parametros"])
        self.assertIn("interruption_pu_bancada", registro["parametros"])
        self.assertNotIn("fator_disturbio_necessario", registro["parametros"])
        self.assertLessEqual(registro["extremo_previsto_v"], self.TETO + 1e-6)
        self.assertAlmostEqual(registro["pico_programado_v"], 220.0 * math.sqrt(2.0), places=6)
        self.assertTrue(registro["validacao_fisica"]["ok"], registro["validacao_fisica"]["motivos"])
        # A validação comparou com a forma REDUZIDA (mínimo do envelope ~0,45 pu, não ~0,04 do modelo).
        self.assertGreater(registro["validacao_fisica"]["envelope_minimo_esperado"], 0.3)

    def test_escala_do_ch1_cobre_o_extremo_previsto(self):
        experimento = self._instancia("16")
        experimento.fonte = mock.Mock(max_peak_v=self.TETO, max_voltage_rms=300.0, last_programmed_peak_v=0.0)
        t = mestre.tempo(experimento.config)
        experimento.osc.get_waveform.return_value = (t, np.zeros_like(t))
        experimento._pontos_efetivos_captura_atual = t.size
        experimento._capturar_real(0, t, np.random.default_rng(1))
        pedido = experimento.osc.set_vertical_scale.call_args[0][1]
        previsto = experimento.avaliar_captura_na_bancada(0, 0, seed=1)["extremo_previsto_v"]
        self.assertGreaterEqual(pedido, previsto - 1e-6)

    def test_analisar_sessao_reconstroi_a_forma_reduzida(self):
        import analisar_sessao
        metadado = {
            "fs_hz": 30_000.0, "pontos": 6000, "seed": 1, "nivel_indice": 0, "f0_hz": 60.0,
            "tensao_base_rms": 220.0, "parametros": {"fator_disturbio_bancada": 0.4},
        }
        esperado = analisar_sessao._reconstruir_esperado("16", metadado)
        t = np.arange(6000) / 30_000.0
        senoide = np.sin(2.0 * np.pi * 60.0 * t)
        # Metadata sem "sorteio_posicao" = sessão anterior à v1.15 (posições fixas).
        modelo, _ = _sem_sorteio(_load_experimento("16")).gerar(t, 60.0, 0, np.random.default_rng(1))
        np.testing.assert_allclose(esperado, senoide + 0.4 * (modelo - senoide), atol=1e-12)


class RelatorioERecalibracaoTests(unittest.TestCase):
    def test_relatorio_lista_todas_as_classes_e_recusa_380(self):
        import io
        from contextlib import redirect_stdout
        relatorio = _carregar_script("relatorio_limites_bancada")
        saida = io.StringIO()
        with redirect_stdout(saida):
            relatorio.main(["--tensao", "220", "--tensao", "380"])
        texto = saida.getvalue()
        for indice in range(1, 21):
            self.assertIn(f"| {indice:02d} ", texto)
        self.assertIn("16: 3/3 rodam, 3 com distúrbio reduzido", texto)
        self.assertIn("380 Vrms — RECUSADA", texto)
        self.assertNotIn("CLIPA", texto)

    def test_recalibracao_reproduz_os_fatores_da_sessao_de_origem(self):
        """A sessão 15-26-05 é a origem da calibração da v1.12: reconstruir o
        pico programado pelo código e dividir pelo VMAX/VMIN gravado devolve
        os mesmos fatores (o JSON da v1.12)."""
        recalibrar = _carregar_script("recalibrar_extremos")
        sessao = PROJECT_ROOT / "tests" / "fixtures" / "sessao_2026-09-30_15-26-05"
        por_condicao, ignoradas, _ = recalibrar.coletar([sessao])
        self.assertEqual(set(por_condicao), {"127V_60Hz"})
        medidos = por_condicao["127V_60Hz"]
        v1_12 = {
            "01": 1.063, "02": 1.164, "03": 1.038, "04": 1.164, "05": 0.998, "06": 1.018, "07": 1.180,
            "09": 1.002, "10": 1.236, "11": 1.258, "12": 1.030, "13": 1.034, "14": 0.977, "15": 1.017,
            "16": 1.459, "17": 1.017, "18": 1.036, "19": 0.972, "20": 1.022,
        }
        self.assertEqual(set(medidos), set(v1_12))
        for classe_id, fator in v1_12.items():
            self.assertAlmostEqual(max(medidos[classe_id]), fator, places=3, msg=classe_id)
        self.assertEqual(ignoradas["08 (modelo próprio)"], 1)

    def test_calibracao_atual_nunca_ficou_abaixo_da_v1_12(self):
        recalibrar = _carregar_script("recalibrar_extremos")
        sessao = PROJECT_ROOT / "tests" / "fixtures" / "sessao_2026-09-30_15-26-05"
        por_condicao, _, _ = recalibrar.coletar([sessao])
        atuais = mestre.carregar_fatores_extremo(CALIBRACAO_REAL, tensao_rms=127.0, frequencia_hz=60.0)
        for classe_id, valores in por_condicao["127V_60Hz"].items():
            self.assertGreaterEqual(atuais[classe_id], round(max(valores), 3), classe_id)

    def test_inversao_de_captura_reduzida(self):
        recalibrar = _carregar_script("recalibrar_extremos")
        registro = {"pico_programado_v": 350.0,
                    "parametros": {"fator_disturbio_bancada": 0.5, "pico_programado_modelo_v": 400.0}}
        # 1,03 + (380 - 1,03 × 350) / (0,5 × 400) = 1,1275 (> 380/350).
        self.assertAlmostEqual(recalibrar.fator_de_captura_reduzida(registro, 380.0, 1.03), 1.1275)
        # Extremo que veio da senoide: a inversão daria < f_ref; vale extremo/pico.
        self.assertAlmostEqual(recalibrar.fator_de_captura_reduzida(registro, 355.0, 1.03), 355.0 / 350.0)

    def test_recalibracao_separa_condicoes(self):
        recalibrar = _carregar_script("recalibrar_extremos")
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        for nome, tensao, frequencia, extremo in (("a", 127.0, 60.0, 190.0), ("b", 230.0, 50.0, 340.0)):
            pasta = tmp / nome / "metadata"
            pasta.mkdir(parents=True)
            registro = {"id_captura": "05-0001", "tensao_base_rms": tensao, "f0_hz": frequencia,
                        "pico_programado_v": tensao * math.sqrt(2.0), "pico_medido_v": extremo,
                        "vale_medido_v": -extremo, "parametros": {}}
            (pasta / "05_harmonics.jsonl").write_text(json.dumps(registro) + "\n", encoding="utf-8")
        por_condicao, _, condicoes = recalibrar.coletar([tmp / "a", tmp / "b"])
        self.assertEqual(set(por_condicao), {"127V_60Hz", "230V_50Hz"})
        self.assertEqual(condicoes["230V_50Hz"], (230.0, 50.0))
        self.assertAlmostEqual(por_condicao["230V_50Hz"]["05"][0], 340.0 / (230.0 * math.sqrt(2.0)))


class CadeiaDeMedicaoTests(unittest.TestCase):
    """v1.14: antes da primeira classe, fonte (medida dela) x CH1. Origem:
    bancada 2026-10-07, disjuntor aberto entre fonte e probe — fonte
    126,6 Vrms, CH1 ~50 Vrms, 20 classes reprovadas na validação física."""

    def _bancada(self, medidas_fonte, osc_vrms):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        fonte = mock.Mock()
        fonte.measure_voltage.side_effect = list(medidas_fonte)
        osc = mock.Mock()
        osc.medir_vrms_forcado.return_value = osc_vrms
        bancada = mestre.Bancada(fonte, osc, _config_bancada(tmp, base_voltage_rms=127.0))
        bancada.recuperar_estado_seguro = mock.Mock()
        return bancada

    def test_cadeia_ok(self):
        bancada = self._bancada([126.6], 125.9)
        leituras = bancada.verificar_cadeia_de_medicao()
        bancada.recuperar_estado_seguro.assert_called_once()
        self.assertAlmostEqual(leituras["razao_osc_fonte"], 125.9 / 126.6)

    def test_disjuntor_aberto_aborta_antes_da_primeira_classe(self):
        bancada = self._bancada([126.6], 52.0)  # números da bancada 2026-10-07
        with self.assertRaises(mestre.CadeiaDeMedicaoError) as ctx:
            bancada.verificar_cadeia_de_medicao()
        self.assertIn("razão 0.411", str(ctx.exception))
        # Infraestrutura: executar_bateria re-levanta, nada é retentado.
        self.assertIsInstance(ctx.exception, mestre.FalhaFatalDeInstrumento)

    def test_espera_a_fonte_subir_e_desiste_se_nao_chegar(self):
        bancada = self._bancada([0.1, 60.0, 126.5], 126.0)
        with mock.patch.object(mestre.time, "sleep"):
            bancada.verificar_cadeia_de_medicao()
        self.assertEqual(bancada.fonte.measure_voltage.call_count, 3)

        bancada = self._bancada([60.0], 60.0)
        with mock.patch.object(mestre.time, "sleep"), \
                mock.patch.object(mestre.Bancada, "TIMEOUT_CADEIA_FONTE_S", 0.0):
            with self.assertRaises(mestre.CadeiaDeMedicaoError) as ctx:
                bancada.verificar_cadeia_de_medicao()
        self.assertIn("A fonte mede 60.00 Vrms", str(ctx.exception))
        bancada.osc.medir_vrms_forcado.assert_not_called()

    def test_simulado_nao_verifica(self):
        bancada = mestre.Bancada(mock.Mock(), None, _config_bancada(Path("."), base_voltage_rms=127.0))
        self.assertEqual(bancada.verificar_cadeia_de_medicao(), {})

    def test_osciloscopio_mede_vrms_com_trigger_forcado_e_valida(self):
        osc = mock.Mock(spec=KeysightDSOX4034A)
        osc.channels = {1: object()}
        osc._MEDIDA_INVALIDA = KeysightDSOX4034A._MEDIDA_INVALIDA
        osc.ask.return_value = "+1.2590E+02"
        self.assertAlmostEqual(KeysightDSOX4034A.medir_vrms_forcado(osc, 1), 125.9)
        nomes = [c[0] for c in osc.method_calls]
        self.assertLess(nomes.index("arm"), nomes.index("force_trigger"))
        self.assertLess(nomes.index("force_trigger"), nomes.index("wait_for_trigger_complete"))
        osc.ask.assert_called_with(":MEASure:VRMS? DISPlay,AC,CHANnel1")
        osc.ask.return_value = "9.9E+37"
        with self.assertRaises(OscilloscopeError):
            KeysightDSOX4034A.medir_vrms_forcado(osc, 1)


class CalibracaoPorCondicaoTests(unittest.TestCase):
    """v1.14: fatores de extremo por condição (tensão base, frequência).
    Origem: 2026-10-07, 230 V/50 Hz com a tabela de 127 V/60 Hz — a 17
    previu 405 V e mediu 444 V, acima dos 425 Vp do hardware."""

    def setUp(self):
        mestre._CONDICOES_SEM_CALIBRACAO_AVISADAS.clear()

    def _fatores(self, tensao, frequencia):
        return mestre.carregar_fatores_extremo(CALIBRACAO_REAL, tensao_rms=tensao, frequencia_hz=frequencia)

    def test_passo1_e_2_so_tabelas_de_mesma_frequencia_e_maior_da_classe(self):
        """Regra por frequência (v1.15): 230 V/50 Hz usa só 127 V/50 Hz e
        230 V/50 Hz entre si; 127 V/60 Hz não entra (sobressinal depende da
        frequência, não da tensão)."""
        condicoes = mestre.carregar_calibracao_extremos(CALIBRACAO_REAL)
        a50 = [condicoes["230V_50Hz"]["fatores"], condicoes["127V_50Hz"]["fatores"]]
        for tensao, frequencia, tabelas in ((230.0, 50.0, a50), (127.0, 50.0, a50),
                                            (127.0, 60.0, [condicoes["127V_60Hz"]["fatores"]])):
            fatores = self._fatores(tensao, frequencia)
            for classe_id in {c for t in tabelas for c in t}:
                esperado = max(t[classe_id] for t in tabelas if classe_id in t)
                self.assertEqual(fatores[classe_id], esperado, (tensao, frequencia, classe_id))
        # 10 a 230 V só rodou reduzida; a 127 V/50 Hz mediu 1,03 — e o 1,242 de 60 Hz não vale a 50 Hz.
        self.assertEqual(self._fatores(230.0, 50.0)["10"], 1.03)
        self.assertEqual(self._fatores(230.0, 50.0)["07"], condicoes["127V_50Hz"]["fatores"]["07"])

    def test_passo3_classe_sem_medida_na_frequencia_usa_o_maior_de_todos(self):
        condicoes = mestre.carregar_calibracao_extremos(CALIBRACAO_REAL)
        maior = max(max(t["fatores"].values()) for t in condicoes.values())
        # 02, 04 e 16 não têm medida a 230 V/50 Hz mas têm a 127 V/50 Hz: usam esta, não o 1,475.
        fatores = self._fatores(230.0, 50.0)
        self.assertNotIn("02", condicoes["230V_50Hz"]["fatores"])
        for classe_id in ("02", "04", "16"):
            self.assertEqual(fatores[classe_id], condicoes["127V_50Hz"]["fatores"][classe_id], classe_id)
        self.assertLess(fatores["16"], maior)
        # Classe só medida em outra frequência: conservador (maior de todas as tabelas).
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        caminho = tmp / "cal.json"
        caminho.write_text(json.dumps({"por_condicao": {
            "127V_60Hz": {"tensao_rms": 127.0, "frequencia_hz": 60.0, "fatores": {"01": 1.06, "16": 1.475}},
            "127V_50Hz": {"tensao_rms": 127.0, "frequencia_hz": 50.0, "fatores": {"01": 1.06, "02": 1.1}},
        }}), encoding="utf-8")
        fatores = mestre.carregar_fatores_extremo(caminho, tensao_rms=127.0, frequencia_hz=50.0)
        self.assertEqual(fatores["02"], 1.1)
        self.assertEqual(fatores["16"], 1.475)

    def test_03_a_230v_50hz_fica_de_fora_pela_margem_sem_excecao(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        with mock.patch.object(mestre, "CALIBRACAO_EXTREMOS_PATH", CALIBRACAO_REAL):
            config = _config_bancada(tmp, base_voltage_rms=230.0, grid_frequency_hz=50.0)
            fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=415.8)
            infos = {}
            for classe_id in ("02", "03", "04", "16"):
                experimento = _carregar_classe(classe_id)(mestre.Bancada(fonte, mock.Mock(), config))
                infos[classe_id] = experimento.avaliar_captura_na_bancada(0, 0)
        for classe_id, previsto in (("02", 380.3), ("04", 380.3), ("16", 368.5)):
            self.assertTrue(infos[classe_id]["cabe"], classe_id)
            self.assertAlmostEqual(infos[classe_id]["extremo_previsto_v"], previsto, places=1)
        self.assertFalse(infos["03"]["cabe"])
        self.assertAlmostEqual(infos["03"]["extremo_previsto_v"], 416.4, places=1)
        self.assertIn("1.058", infos["03"]["motivo"])  # fator e pico aparecem no motivo

    def test_tolerancia_de_condicao(self):
        self.assertEqual(self._fatores(129.0, 60.4), self._fatores(127.0, 60.0))  # 1,6% e 0,4 Hz
        with self.assertLogs("MestreExperimentos", level="WARNING"):
            self.assertNotEqual(self._fatores(130.0, 60.0), self._fatores(127.0, 60.0))  # 2,4%
        with self.assertLogs("MestreExperimentos", level="WARNING"):
            self.assertNotEqual(self._fatores(127.0, 61.0), self._fatores(127.0, 60.0))  # 1 Hz

    def test_sem_calibracao_e_conservador_e_avisa_uma_vez(self):
        condicoes = mestre.carregar_calibracao_extremos(CALIBRACAO_REAL)
        maior = max(max(t["fatores"].values()) for t in condicoes.values())
        maior_01 = max(t["fatores"]["01"] for t in condicoes.values())
        with self.assertLogs("MestreExperimentos", level="WARNING") as logs:
            fatores = self._fatores(220.0, 60.0)
            self._fatores(220.0, 60.0)
        self.assertEqual(len([r for r in logs.records if "SEM tabela para 220V_60Hz" in r.getMessage()]), 1)
        self.assertEqual(fatores["01"], maior_01)
        self.assertTrue(all(v == maior for k, v in fatores.items() if k != "01"))

    def test_regressao_17_a_230v_50hz_nao_programa_mais_o_que_mediu_444v(self):
        """Mesma classe/seed base/condição da sessão 2026-10-07_15-15-25: lá
        as 3 capturas da 17 rodaram SEM redução (previsto 405 V) e uma mediu
        444 V. Com a tabela de 230 V/50 Hz, toda captura que cabe tem o
        distúrbio reduzido e o fator usado cobre os 444 V medidos."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        with mock.patch.object(mestre, "CALIBRACAO_EXTREMOS_PATH", CALIBRACAO_REAL):
            config = _config_bancada(tmp, base_voltage_rms=230.0, grid_frequency_hz=50.0)
            fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=415.8)
            experimento = _carregar_classe("17")(mestre.Bancada(fonte, mock.Mock(), config))
            infos = [experimento.avaliar_captura_na_bancada(ig, ci) for ig, ci in experimento.plano_de_capturas(False)]
            fator = mestre.fator_extremo_da_classe("17", experimento._fatores_extremo())
        self.assertGreaterEqual(fator * 357.5, 444.0)  # 357,5 V = pico programado na sessão
        for info in infos:
            if info["cabe"]:
                self.assertLess(info["fator_disturbio_bancada"], 1.0)
                self.assertLessEqual(info["extremo_previsto_v"], 415.8 + 1e-6)


class RecorteMargemERelatorioHtmlTests(unittest.TestCase):
    """recortar_margem.py e relatorio_html.py sobre uma sessão sintética no
    formato da bancada real: 8100 pontos (600 antes + 6000 + 1500 depois),
    1 .npz por captura, snr_XXdb/ e metadata/*.jsonl com indice_trigger."""

    FS = 30_000.0
    F0 = 60.0

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.sessao = self.tmp / "sessao_teste"
        (self.sessao / "metadata").mkdir(parents=True)
        (self.sessao / "snr_30db").mkdir()
        self.nominais = {}
        # 01: trigger 5 amostras antes da margem (como na sessão real de
        # 2026-09-30); 02: pre_trigger 60 ms (PULSe); 05: sem indice_trigger
        # (metadata antigo, cai na margem_amostras_antes).
        self._captura("01", "NORMAL", {}, pre_s=0.0, indice_trigger=595, sag=None)
        self._captura("02", "SAG", {"sag_pu": 0.5}, pre_s=0.060, indice_trigger=2405, sag=(0.060, 0.120))
        self._captura("05", "HARMONICS", {"thd": 0.1}, pre_s=0.0, indice_trigger=None, sag=None)

    def _captura(self, cid, nome, parametros, *, pre_s, indice_trigger, sag):
        t_nom = np.arange(6000) / self.FS
        nominal = np.sin(2 * np.pi * self.F0 * t_nom)
        if sag is not None:
            nominal[(t_nom >= sag[0]) & (t_nom < sag[1])] *= 0.5
        inicio = 600 if indice_trigger is None else indice_trigger - int(round(pre_s * self.FS))
        registro = np.zeros(8100)
        registro[inicio:inicio + 6000] = nominal
        registro[inicio + 6000:] = 0.123  # marcador da folga depois
        self.nominais[cid] = nominal
        md = {
            "id_captura": f"{cid}-0001", "classe": nome, "seed": 1, "simulado": False,
            "fs_hz": self.FS, "pontos": 6000, "parametros": parametros, "nivel_indice": 0,
            "f0_hz": self.F0, "tensao_base_rms": 127.0, "pre_trigger_s": pre_s,
            "margem_amostras_antes": 600, "margem_amostras_depois": 1500, "amostras_totais": 8100,
            "validacao_fisica": {"ok": cid != "05", "motivos": [] if cid != "05" else ["THD <fora>"]},
        }
        if indice_trigger is not None:
            md["indice_trigger"] = indice_trigger
        nome_arquivo = f"{cid}_{nome.lower()}_cap01.npz"
        for pasta, ruido in ((self.sessao, 0.0), (self.sessao / "snr_30db", 0.01)):
            np.savez(
                pasta / nome_arquivo, classe=nome, id_captura=np.array([md["id_captura"]], dtype=object),
                tempo_ms=np.arange(8100) / self.FS * 1000.0, tensao_pu=(registro + ruido)[np.newaxis, :],
            )
        (self.sessao / "metadata" / f"{cid}_{nome.lower()}.jsonl").write_text(json.dumps(md) + "\n", encoding="utf-8")

    def test_recorte_devolve_exatamente_a_janela_nominal(self):
        import recortar_margem

        saida = self.tmp / "sem_margem"
        relatorio = recortar_margem.recortar_sessao(self.sessao, saida, empilhar=True)
        self.assertEqual(len(relatorio), 6)  # 3 capturas x (puro + snr_30db)
        # Sessão no formato antigo (1 .npz por captura) -> saída no formato 2:
        # um NN_classe.npz por classe, e o SNR em snr_30db/NN_classe.npz.
        for cid, nome in (("01", "normal"), ("02", "sag"), ("05", "harmonics")):
            with np.load(saida / f"{cid}_{nome}.npz", allow_pickle=True) as dados:
                self.assertEqual(dados["literatura/medida"].shape, (1, 6000))
                np.testing.assert_allclose(dados["literatura/medida"][0], self.nominais[cid])
                self.assertEqual(dados["tempo_ms"][0], 0.0)
                self.assertEqual(list(dados["literatura/inicio_janela"]), [0])
            with np.load(saida / "snr_30db" / f"{cid}_{nome}.npz", allow_pickle=True) as dados:
                np.testing.assert_allclose(dados["literatura/tensao_pu"][0], self.nominais[cid] + 0.01)
        origens = {linha["id_captura"]: linha["origem"] for linha in relatorio}
        self.assertEqual(origens["01-0001"], "indice_trigger")
        self.assertEqual(origens["05-0001"], "margem_amostras_antes")

        md = json.loads((saida / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(md["recorte"]["inicio_amostra"], 605)
        self.assertEqual(md["margem_amostras_antes"], 0)
        self.assertEqual(md["amostras_totais"], 6000)
        self.assertEqual(md["indice_trigger"], 1800)  # 60 ms dentro da janela nominal

        self.assertEqual(md["arquivo_classe"], "02_sag.npz")
        self.assertEqual(md["indice_no_arquivo"], 0)
        self.assertFalse((saida / "empilhado").exists())  # --empilhar não faz mais nada

    def test_recorte_nunca_escreve_na_propria_sessao(self):
        import recortar_margem

        with self.assertRaises(ValueError):
            recortar_margem.recortar_sessao(self.sessao, self.sessao)

    def test_recorte_bate_com_janela_nominal_de_sinais(self):
        """Mesmo recorte da validação física/analisar_sessao, não uma conta paralela."""
        import recortar_margem

        md = json.loads((self.sessao / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8"))
        registro = np.arange(8100, dtype=np.float64)
        inicio, pontos, _ = recortar_margem.calcular_recorte(8100, md)
        esperado = sinais.janela_nominal(
            registro, indice_trigger=md["indice_trigger"], pre_trigger_s=md["pre_trigger_s"],
            pontos=6000, fs_hz=self.FS,
        )
        np.testing.assert_array_equal(registro[inicio:inicio + pontos], esperado)

    def test_detalhes_no_maximo_tres_e_nas_bordas_do_sag(self):
        import relatorio_html

        nominal = self.nominais["02"]
        janelas = relatorio_html.escolher_detalhes(nominal, fs_hz=self.FS, f0_hz=self.F0, quantidade=9, largura_ms=20.0)
        self.assertLessEqual(len(janelas), relatorio_html.MAX_DETALHES)
        for borda_ms in (60.0, 120.0):
            self.assertTrue(any(a <= borda_ms <= b for a, b in janelas), (borda_ms, janelas))
        # Sessão real 2026-10-07 (17, notch): o rms de meio ciclo alterna
        # ~0,72/0,70 entre semiciclos (offset da bancada). Esse "salto" de
        # fundo não pode puxar um detalhe para um trecho sem evento.
        t = np.arange(6000) / self.FS
        assimetrico = np.sin(2 * np.pi * self.F0 * t) + 0.012
        for inicio_ms in (64.0, 72.0, 81.0, 97.0, 105.0, 114.0, 122.0):
            i = int(inicio_ms * self.FS / 1000.0)
            assimetrico[i:i + 10] -= 0.2 * np.sign(assimetrico[i:i + 10])
        janelas = relatorio_html.escolher_detalhes(assimetrico, fs_hz=self.FS, f0_hz=self.F0, quantidade=3, largura_ms=33.3)
        self.assertTrue(janelas)
        for a, b in janelas:
            self.assertTrue(any(a <= n_ms <= b for n_ms in (64.0, 72.0, 81.0, 97.0, 105.0, 114.0, 122.0)), (a, b))
        # Eventos colados no fim: janelas empurradas para dentro do registro
        # não podem se sobrepor (sessão 2026-10-07, classe 20).
        no_fim = np.sin(2 * np.pi * self.F0 * t)
        for inicio_ms in (150.0, 172.0, 195.0):
            i = int(inicio_ms * self.FS / 1000.0)
            no_fim[i:i + 10] -= 0.5 * np.sign(no_fim[i:i + 10])
        janelas = relatorio_html.escolher_detalhes(no_fim, fs_hz=self.FS, f0_hz=self.F0, quantidade=3, largura_ms=33.3)
        for (_, b1), (a2, _) in zip(janelas, janelas[1:]):
            self.assertLessEqual(b1, a2 + 1e-9, janelas)
        for evento_ms in (150.0, 172.0, 195.0):  # deslizar, não descartar
            self.assertTrue(any(a <= evento_ms <= b for a, b in janelas), (evento_ms, janelas))
        regime = relatorio_html.escolher_detalhes(self.nominais["01"], fs_hz=self.FS, f0_hz=self.F0, quantidade=3, largura_ms=20.0)
        self.assertEqual(len(regime), 1)
        self.assertEqual(relatorio_html.escolher_detalhes(nominal, fs_hz=self.FS, f0_hz=self.F0, quantidade=0, largura_ms=20.0), [])

    def test_html_autocontido_com_no_maximo_1_completa_e_3_detalhes(self):
        import re
        import relatorio_html

        saida = self.tmp / "relatorio.html"
        manuais = self.tmp / "detalhes.json"
        manuais.write_text(json.dumps({"05_harmonics_cap01": [[1, 2], [3, 4], [5, 6], [7, 8]]}), encoding="utf-8")
        relatorio_html.main([
            str(self.sessao), "--saida", str(saida), "--titulo", "Teste <&>",
            "--detalhes-manuais", str(manuais), "--dpi", "40",
        ])
        texto = saida.read_text(encoding="utf-8")
        self.assertNotIn("$", texto)  # todo marcador do modelo preenchido
        self.assertIn("Teste &lt;&amp;&gt;", texto)
        self.assertIn("THD &lt;fora&gt;", texto)
        self.assertNotRegex(texto, r'src="(?!data:)')  # nenhuma imagem/arquivo externo
        secoes = re.findall(r'<section class="captura".*?</section>', texto, flags=re.S)
        self.assertEqual(len(secoes), 3)
        for secao in secoes:
            imagens = secao.count('src="data:image/png;base64,')
            self.assertGreaterEqual(imagens, 1)
            self.assertLessEqual(imagens, 1 + relatorio_html.MAX_DETALHES)
            self.assertEqual(secao.count("visualização completa"), 1)
        # 4 janelas manuais -> só 3 entram
        self.assertEqual(secoes[2].count("definidos manualmente"), 3)

    def test_html_roda_na_pasta_recortada_e_no_snr(self):
        import recortar_margem
        import relatorio_html

        recortado = self.tmp / "sem_margem"
        recortar_margem.recortar_sessao(self.sessao, recortado)
        caminho, total = relatorio_html.gerar_relatorio(
            recortado, self.tmp / "r.html", snr="30", classes=["02"], dpi=40,
        )
        self.assertEqual(total, 1)
        self.assertIn("snr_30db", caminho.read_text(encoding="utf-8"))
        capturas = relatorio_html.ler_capturas(recortado, recortar_margem.carregar_metadados(recortado))
        self.assertTrue(all(not c.tem_margem for c in capturas))



class MetadataLegivelERastreavelTests(unittest.TestCase):
    """Metadata legível (.json indentado ao lado do .jsonl), ``inicio_janela``,
    cópia da calibração e procedência do código na pasta da sessão."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _config(self, results_dir, **overrides):
        base = dict(
            fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=results_dir,
            sim_captures_per_class=2, real_captures_per_class=1, disturbance_start_s=0.06,
            capturas_override=1,
        )
        base.update(overrides)
        return mestre.Config(**base)

    def _classe_fisica(self, config, indice_trigger, pre_trigger_s=0.060):
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
        bancada = mestre.Bancada(fonte, mock.Mock(), config)

        class _Classe(mestre.ExperimentoNativo):
            id = "02"
            nome = "SAG"

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

            def configurar(self, capture_index):
                return {}

        _Classe.pre_trigger_s = pre_trigger_s
        experimento = _Classe(bancada)
        experimento.osc = mock.Mock()
        experimento.osc.ultimo_indice_trigger = indice_trigger
        tempo_s = np.arange(7200, dtype=np.float64) / 30_000.0
        experimento._capturar_real = lambda ci, t, rng: (
            tempo_s, np.sin(2.0 * np.pi * 60.0 * tempo_s), None, {},
        )
        experimento._preparar_acquisicao_real = lambda: None
        return experimento

    def _rodar_fisica(self, indice_trigger):
        config = self._config(self.tmp / "resultados")
        experimento = self._classe_fisica(config, indice_trigger)
        with mock.patch.object(
            mestre.ExperimentoBase, "_calcular_margem", staticmethod(lambda **kw: (600, 600, 7200))
        ):
            experimento.executar()
        return config.results_dir

    def _primeiro_registro(self, pasta):
        texto = (pasta / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8")
        return json.loads(texto.splitlines()[0])

    def test_fisica_grava_json_indentado_igual_ao_jsonl(self):
        pasta = self._rodar_fisica(2500)
        jsonl = pasta / "metadata" / "02_sag.jsonl"
        legivel = pasta / "metadata" / "02_sag.json"
        self.assertTrue(legivel.exists())
        texto = legivel.read_text(encoding="utf-8")
        self.assertGreater(texto.count("\n"), 10, "o .json precisa ser indentado (várias linhas)")
        linhas = [json.loads(l) for l in jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(json.loads(texto), linhas)
        self.assertFalse(list((pasta / "metadata").glob("*.part")))

    def test_inicio_janela_segue_a_formula_do_recorte(self):
        # 2500 - 0,060 s * 30 kHz = 700, dentro de [0, 7200 - 6000].
        registro = self._primeiro_registro(self._rodar_fisica(2500))
        self.assertEqual(registro["inicio_janela"], 700)
        self.assertFalse(registro["inicio_janela_ajustado"])
        self.assertEqual(registro["indice_trigger"], 2500)  # campo antigo preservado

    def test_fisica_grava_perfil(self):
        registro = self._primeiro_registro(self._rodar_fisica(2500))
        self.assertEqual(registro["perfil"], "literatura")

    def test_inicio_janela_respeita_o_limite_do_registro(self):
        # 3500 - 1800 = 1700 > 7200 - 6000: a janela é empurrada para 1200.
        registro = self._primeiro_registro(self._rodar_fisica(3500))
        self.assertEqual(registro["inicio_janela"], 1200)
        self.assertTrue(registro["inicio_janela_ajustado"])

    def test_leitores_preferem_inicio_janela(self):
        import recortar_margem
        md = {
            "pontos": 6000, "fs_hz": 30_000.0, "pre_trigger_s": 0.060,
            "margem_amostras_antes": 600, "indice_trigger": 2500, "inicio_janela": 900,
        }
        inicio, pontos, info = recortar_margem.calcular_recorte(7200, md)
        self.assertEqual((inicio, pontos, info["origem"]), (900, 6000, "inicio_janela"))
        sem = {k: v for k, v in md.items() if k != "inicio_janela"}
        inicio_antigo, _, info_antigo = recortar_margem.calcular_recorte(7200, sem)
        self.assertEqual((inicio_antigo, info_antigo["origem"]), (700, "indice_trigger"))
        recortado = recortar_margem.metadado_recortado(md, info)
        self.assertEqual(recortado["inicio_janela"], 0)
        self.assertEqual(recortado["indice_trigger"], 2500 - 900)

    def test_analisar_sessao_usa_inicio_janela(self):
        import analisar_sessao
        sessao = self.tmp / "sessao_analise"
        (sessao / "metadata").mkdir(parents=True)
        t = np.arange(6000) / 30_000.0
        nominal = np.sin(2 * np.pi * 60.0 * t)
        registro = np.zeros(7200)
        registro[900:6900] = nominal
        md = {
            "id_captura": "01-0001", "classe": "NORMAL", "seed": 1, "simulado": False,
            "fs_hz": 30_000.0, "pontos": 6000, "parametros": {}, "nivel_indice": 0,
            "f0_hz": 60.0, "tensao_base_rms": 127.0, "pre_trigger_s": 0.0,
            "margem_amostras_antes": 600, "margem_amostras_depois": 600, "amostras_totais": 7200,
            "indice_trigger": 123, "inicio_janela": 900,  # indice_trigger inconsistente de propósito
        }
        np.savez(
            sessao / "01_normal_cap01.npz", classe="NORMAL",
            id_captura=np.array(["01-0001"], dtype=object),
            tempo_ms=np.arange(7200) / 30.0, tensao_pu=registro[np.newaxis, :],
        )
        (sessao / "metadata" / "01_normal.jsonl").write_text(json.dumps(md) + "\n", encoding="utf-8")
        resultado = analisar_sessao.analisar_sessao(sessao)
        self.assertEqual(resultado[0]["lag_amostras"], 0)
        self.assertGreater(resultado[0]["correlacao"], 0.99)

    def _rodar_simulada(self):
        config = self._config(self.tmp / "sim")
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
        bancada = mestre.Bancada(fonte, None, config)

        class _Classe(mestre.ExperimentoNativo):
            id = "01"
            nome = "NORMAL"

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

            def configurar(self, capture_index):
                return {}

        _Classe(bancada).executar()
        return config.results_dir

    def test_sessao_simulada_grava_legivel_calibracao_e_procedencia(self):
        pasta = self._rodar_simulada()
        registros = json.loads((pasta / "metadata" / "01_normal.json").read_text(encoding="utf-8"))
        texto_jsonl = (pasta / "metadata" / "01_normal.jsonl").read_text(encoding="utf-8")
        linhas = [json.loads(l) for l in texto_jsonl.splitlines()]
        self.assertEqual(registros, linhas)
        self.assertEqual(len(linhas), 2)
        copia = pasta / "calibracao_extremos.json"
        self.assertEqual(copia.read_bytes(), mestre.CALIBRACAO_EXTREMOS_PATH.read_bytes())
        sessao = json.loads((pasta / "sessao.json").read_text(encoding="utf-8"))
        self.assertEqual(sessao["calibracao_extremos"]["sha256"], mestre.sha256_do_arquivo(copia))
        self.assertEqual(sessao["calibracao_extremos"]["copia_na_sessao"], "calibracao_extremos.json")
        self.assertEqual(sessao["numpy_versao"], np.__version__)
        self.assertEqual(sessao["modo"], "simulado")
        self.assertIn("git_commit", sessao)
        self.assertIn("git_sujo", sessao)
        self.assertIn("python_versao", sessao)

    def test_fisica_repete_procedencia_no_registro(self):
        pasta = self._rodar_fisica(2500)
        registro = self._primeiro_registro(pasta)
        sessao = json.loads((pasta / "sessao.json").read_text(encoding="utf-8"))
        self.assertEqual(sessao["modo"], "bancada")
        self.assertEqual(registro["calibracao_extremos_sha256"], sessao["calibracao_extremos"]["sha256"])
        self.assertEqual(registro["numpy_versao"], np.__version__)
        self.assertEqual(registro["git_commit"], sessao["git_commit"])

    def test_commit_e_versao_do_numpy_sao_lidos_do_ambiente(self):
        resultado = mock.Mock(stdout="abc123\n")
        with mock.patch.object(mestre, "_INFO_CODIGO_CACHE", None), \
                mock.patch("subprocess.run", return_value=resultado) as run:
            info = mestre.info_do_codigo()
        comandos = [c.args[0] for c in run.call_args_list]
        self.assertIn(["git", "rev-parse", "HEAD"], comandos)
        self.assertEqual(info["git_commit"], "abc123")
        self.assertTrue(info["git_sujo"])  # status "abc123" != vazio
        self.assertEqual(info["numpy_versao"], np.__version__)

    def test_arvore_suja_em_bancada_avisa_em_destaque_sem_bloquear(self):
        pasta = self.tmp / "bancada"
        sujo = {"git_commit": "abc", "git_sujo": True, "versao_codigo": "abc-dirty",
                "numpy_versao": np.__version__, "python_versao": "3"}
        with mock.patch.object(mestre, "info_do_codigo", return_value=sujo), \
                mock.patch("builtins.print") as imprimir, \
                self.assertLogs("MestreExperimentos", level="WARNING") as logs:
            info = mestre.preparar_pasta_da_sessao(pasta, bancada=True)
        self.assertTrue(info["git_sujo"])
        self.assertIn("SUJA", "".join(str(c.args[0]) for c in imprimir.call_args_list))
        self.assertIn("SUJA", "".join(logs.output))
        self.assertTrue((pasta / "sessao.json").exists())

    def test_arvore_limpa_ou_simulado_nao_avisa(self):
        for bancada, sujo_flag in ((True, False), (False, True)):
            pasta = self.tmp / f"p_{bancada}"
            info = {"git_commit": "abc", "git_sujo": sujo_flag, "versao_codigo": "abc",
                    "numpy_versao": np.__version__, "python_versao": "3"}
            with mock.patch.object(mestre, "info_do_codigo", return_value=info), \
                    mock.patch("builtins.print") as imprimir:
                mestre.preparar_pasta_da_sessao(pasta, bancada=bancada)
            imprimir.assert_not_called()

    def test_leitores_continuam_lendo_sessao_antiga_de_uma_linha(self):
        import recortar_margem
        sessao = self.tmp / "antiga"
        (sessao / "metadata").mkdir(parents=True)
        md = {"id_captura": "01-0001", "pontos": 6000, "fs_hz": 30_000.0, "pre_trigger_s": 0.0,
              "margem_amostras_antes": 600, "indice_trigger": 600, "amostras_totais": 7200}
        (sessao / "metadata" / "01_normal.jsonl").write_text(json.dumps(md) + "\n", encoding="utf-8")
        (sessao / "metadata" / "01_normal.json").write_text("[\n  {}\n]\n", encoding="utf-8")  # não pode atrapalhar
        lidos = recortar_margem.carregar_metadados(sessao)
        self.assertEqual(list(lidos), ["01-0001"])
        self.assertEqual(recortar_margem.calcular_recorte(7200, lidos["01-0001"])[2]["origem"], "indice_trigger")


class PerfisDeFaixasTests(unittest.TestCase):
    """Perfis norma/literatura/fronteira (logica/perfis.py, v1.15)."""

    REFERENCIA = PROJECT_ROOT / "tests" / "fixtures" / "gerar_literatura_34a0d82.json"

    @staticmethod
    def _com_perfil(experiment_id, perfil):
        import dataclasses
        experimento = _load_experimento(experiment_id)
        # Estes testes isolam o PERFIL: início/duração/fase ficam fixos (v1.15).
        experimento.config = dataclasses.replace(experimento.config, perfil=perfil, sorteio_posicao=False)
        return experimento

    @staticmethod
    def _assinatura(experimento, f0, seed, indice):
        import hashlib
        t = np.arange(6000, dtype=np.float64) / 30_000.0
        tensao, parametros = experimento.gerar(t, f0, indice, np.random.default_rng(seed))
        corpo = np.asarray(tensao, dtype="<f8").tobytes() + json.dumps(parametros, sort_keys=True).encode()
        return hashlib.sha256(corpo).hexdigest()

    def _parametros(self, experiment_id, perfil, f0=60.0):
        experimento = self._com_perfil(experiment_id, perfil)
        t = np.arange(6000, dtype=np.float64) / 30_000.0
        for seed in range(40):
            for indice in range(5):
                yield experimento.gerar(t, f0, indice, np.random.default_rng(seed))[1]

    def test_literatura_reproduz_byte_a_byte_o_gerar_do_commit_34a0d82(self):
        """As 400 assinaturas (20 classes x 60/50 Hz x 2 seeds x 5 índices:
        sha256 dos bytes float64 da tensão + parâmetros) foram gravadas com o
        ``gerar()`` do commit 34a0d82, ANTES da v1.15. Valem para o perfil
        padrão e para ``perfil="literatura"`` explícito, com
        ``sorteio_posicao=False`` (as posições fixas de antes do sorteio de
        início/duração/fase; o ``gerar()`` com sorteio tem o fixture
        ``gerar_sorteio_v1_15.json``, ver SorteioInicioDuracaoFaseTests). O fixture grava a
        versão do numpy que o gerou; outra versão só pode divergir por
        aritmética do próprio numpy."""
        ref = json.loads(self.REFERENCIA.read_text(encoding="utf-8"))
        self.assertEqual(len(ref["hashes"]), 400)
        self.assertEqual(len(ref["portavel"]["resumos"]), 400)
        # Assinatura PORTAVEL (por tolerancia, vale em qualquer plataforma);
        # a exata (SHA-256) so na plataforma de origem: AssinaturaPortavelTests.
        for chave, esperado in ref["portavel"]["resumos"].items():
            cid, f0, seed, indice = chave.split("/")
            for experimento in (_sem_sorteio(_load_experimento(cid)), self._com_perfil(cid, "literatura")):
                self.assertEqual(
                    assinatura_portavel.diferencas(
                        assinatura_portavel.gerar_resumo(experimento, float(f0), int(seed), int(indice)), esperado,
                    ), [], chave,
                )

    def test_norma_e_fronteira_mudam_so_o_que_a_spec_manda(self):
        ref = json.loads(self.REFERENCIA.read_text(encoding="utf-8"))["portavel"]["resumos"]
        afetadas = {"norma": {"02", "03", "05", "06", "11", "15", "20"},
                    "fronteira": {"02", "03", "10", "11", "12", "13", "14"}}
        for perfil, esperadas in afetadas.items():
            mudou = set()
            for chave, h in ref.items():
                cid, f0, seed, indice = chave.split("/")
                if not assinatura_portavel.confere(
                        self._com_perfil(cid, perfil), float(f0), int(seed), int(indice), h):
                    mudou.add(cid)
            self.assertEqual(mudou, esperadas, perfil)

    def test_faixas_da_norma(self):
        for p in self._parametros("02", "norma"):
            self.assertTrue(0.15 <= p["sag_pu"] <= 0.85, p)
        for p in self._parametros("03", "norma"):
            self.assertTrue(1.15 <= p["swell_pu"] <= 1.75, p)
        niveis05 = {p["thd"] for p in self._parametros("05", "norma")}
        self.assertEqual(max(niveis05), 0.20)
        self.assertLessEqual(max(niveis05), AmetekMX30.MAX_CSINE_THD_PCT / 100.0)
        for cid in ("06", "11", "15"):
            for p in self._parametros(cid, "norma"):
                self.assertTrue(0.02 <= p["flicker_depth"] <= 0.07, (cid, p))
        for p in self._parametros("20", "norma"):
            for chave, valor in p.items():
                self.assertTrue(0.005 <= valor <= 0.02, (chave, valor))
        for cid in ("10", "11", "12"):
            for p in self._parametros(cid, "norma"):
                self.assertTrue(0.15 <= p["sag_pu"] <= 0.85, (cid, p))
        for cid in ("13", "14"):
            for p in self._parametros(cid, "norma"):
                self.assertTrue(1.15 <= p["swell_pu"] <= 1.75, (cid, p))
        for cid in ("10", "13", "15", "16"):
            for p in self._parametros(cid, "norma"):
                self.assertLessEqual(p["thd"], 0.20)

    def test_05_norma_nao_usa_trace_e_literatura_usa_so_o_30(self):
        norma = self._com_perfil("05", "norma")
        self.assertFalse(any(norma.usar_trace(i) for i in range(norma.total_niveis())))
        lit = self._com_perfil("05", "literatura")
        self.assertEqual([lit.usar_trace(i) for i in range(5)], [False, False, False, False, True])

    def test_fronteira_so_nos_valores_de_fronteira(self):
        self.assertEqual({p["sag_pu"] for p in self._parametros("02", "fronteira")}, {0.1, 0.9})
        self.assertEqual({p["swell_pu"] for p in self._parametros("03", "fronteira")}, {1.1, 1.8})
        for cid in ("10", "11", "12"):
            self.assertEqual({p["sag_pu"] for p in self._parametros(cid, "fronteira")}, {0.1, 0.9}, cid)
        for cid in ("13", "14"):
            self.assertEqual({p["swell_pu"] for p in self._parametros(cid, "fronteira")}, {1.1, 1.8}, cid)
        self.assertEqual(self._com_perfil("02", "fronteira").total_niveis(), 2)

    def test_perfil_invalido_e_padrao(self):
        import perfis
        self.assertEqual(mestre.Config.__dataclass_fields__["perfil"].default, "literatura")
        with self.assertRaises(ValueError):
            perfis.validar("outro")
        with self.assertRaises(ValueError):
            self._com_perfil("02", "outro").gerar(
                np.arange(6000) / 30_000.0, 60.0, 0, np.random.default_rng(1))
        with mock.patch.dict("os.environ", {"PERFIL": "Norma"}):
            self.assertEqual(perfis.perfil_do_ambiente(), "norma")
        with mock.patch.dict("os.environ", {"PERFIL": ""}):
            self.assertEqual(perfis.perfil_do_ambiente(), "literatura")
        with mock.patch.dict("os.environ", {"PERFIL": "xyz"}):
            with self.assertRaises(ValueError):
                perfis.perfil_do_ambiente()

    def test_cada_perfil_tem_todos_os_componentes_e_as_classes_apontam_para_eles(self):
        import perfis
        for componente, por_perfil in perfis.FAIXAS.items():
            self.assertEqual(set(por_perfil), set(perfis.PERFIS), componente)
        usados = {c for comps in perfis.COMPONENTES_POR_CLASSE.values() for c in comps}
        self.assertEqual(usados, set(perfis.FAIXAS))

    def test_cli_set_perfil_status_e_help(self):
        import io
        from contextlib import redirect_stdout
        import cli
        with mock.patch.object(mestre, "PERFIL", "literatura"):
            sessao = cli.SessaoCLI()

            def rodar(metodo, args):
                saida = io.StringIO()
                with redirect_stdout(saida):
                    return metodo(args), saida.getvalue()

            for valor in ("norma", "fronteira", "literatura"):
                codigo, _ = rodar(sessao.cmd_set, ["perfil", valor])
                self.assertEqual(codigo, 0, valor)
                self.assertEqual(mestre.PERFIL, valor)
                self.assertEqual(mestre._build_config().perfil, valor)
                _, saida = rodar(sessao.cmd_status, [])
                self.assertIn(f"perfil de faixas: {valor}", saida)
            codigo, _ = rodar(sessao.cmd_set, ["perfil", "xyz"])
            self.assertEqual(codigo, 1)
            self.assertEqual(mestre.PERFIL, "literatura")
        self.assertIn("set perfil norma|literatura|fronteira", cli.HELP_TEXT)

    def test_metadata_grava_perfil_em_cada_captura(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        for perfil in ("norma", "literatura", "fronteira"):
            config = mestre.Config(
                fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
                base_voltage_rms=127.0, snr_levels_db=(), base_seed=1, capture_current=False,
                current_base_a=None, results_dir=tmp / perfil, sim_captures_per_class=2,
                real_captures_per_class=1, disturbance_start_s=0.06, perfil=perfil,
            )
            fonte = AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
            classe = type(_load_experimento("02"))(mestre.Bancada(fonte, None, config))
            classe.executar()
            registros = [
                json.loads(l) for l in
                (tmp / perfil / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual({r["perfil"] for r in registros}, {perfil})
            self.assertEqual(len(registros), 2)

    def test_analisar_sessao_reconstroi_com_o_perfil_da_captura(self):
        import analisar_sessao
        md = {"fs_hz": 30_000.0, "pontos": 6000, "seed": 5, "nivel_indice": 0,
              "f0_hz": 60.0, "tensao_base_rms": 127.0}
        antigo = analisar_sessao._reconstruir_esperado("02", md)
        lit = analisar_sessao._reconstruir_esperado("02", dict(md, perfil="literatura"))
        fronteira = analisar_sessao._reconstruir_esperado("02", dict(md, perfil="fronteira"))
        norma = analisar_sessao._reconstruir_esperado("02", dict(md, perfil="norma"))
        np.testing.assert_array_equal(antigo, lit)
        t = np.arange(6000) / 30_000.0
        base = np.sin(2 * np.pi * 60.0 * t)
        evento = (t >= 0.06) & (t < 0.12)
        # nível 0: literatura 0,1 pu, fronteira 0,1 pu, norma 0,15 pu
        np.testing.assert_allclose(lit[evento], 0.1 * base[evento])
        np.testing.assert_allclose(fronteira[evento], 0.1 * base[evento])
        np.testing.assert_allclose(norma[evento], 0.15 * base[evento])
        np.testing.assert_array_equal(norma[~evento], base[~evento])


class SorteioInicioDuracaoFaseTests(unittest.TestCase):
    """v1.15 — início, duração e fase sorteados em ``gerar()``
    (`arquivo/analises:docs/analise-2026-10-12/pendente/sorteio_inicio_fase_VERIFICAR_BANCADA.md`)."""

    FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "gerar_sorteio_v1_15.json"
    CLASSES = [f"{i:02d}" for i in range(1, 21)]
    # Classes que sorteiam início (e duração onde o evento tem duração livre).
    # 07 só sorteia a fase (entalhes contínuos em toda a janela, v1.15); 17 sorteia o
    # início da oscilação.
    COM_INICIO = {"02", "03", "04", "09", "10", "11", "12", "13", "14", "16", "17"}
    COM_DURACAO_LIVRE = {"02", "03", "04", "10", "11", "12", "13", "14", "16"}
    SEM_SORTEIO = {"08"}
    T = np.arange(6000, dtype=np.float64) / 30_000.0

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _gerar(self, classe_id, seed, f0=60.0, indice=0, sorteio=True):
        experimento = _load_experimento(classe_id)
        if not sorteio:
            _sem_sorteio(experimento)
        return experimento.gerar(self.T, f0, indice, np.random.default_rng(seed))

    def test_mesma_seed_mesma_forma_e_mesmos_campos(self):
        for classe_id in self.CLASSES:
            for f0 in (60.0, 50.0):
                v1, p1 = self._gerar(classe_id, 123, f0)
                v2, p2 = self._gerar(classe_id, 123, f0)
                np.testing.assert_array_equal(v1, v2, classe_id)
                self.assertEqual(p1, p2, classe_id)
                # a mesma instância, chamada duas vezes com rng novo, também
                experimento = _load_experimento(classe_id)
                a = experimento.gerar(self.T, f0, 0, np.random.default_rng(9))
                b = experimento.gerar(self.T, f0, 0, np.random.default_rng(9))
                np.testing.assert_array_equal(a[0], b[0], classe_id)

    def test_seeds_diferentes_dao_inicio_e_fase_diferentes(self):
        for classe_id in self.CLASSES:
            if classe_id in self.SEM_SORTEIO:
                continue
            fases = {self._gerar(classe_id, seed)[1]["fase_graus"] for seed in range(40)}
            self.assertGreater(len(fases), 30, classe_id)
            if classe_id in self.COM_INICIO:
                inicios = {self._gerar(classe_id, seed)[1]["inicio_disturbio_s"] for seed in range(40)}
                self.assertGreater(len(inicios), 30, classe_id)
        # 01: só fase, sem evento a posicionar
        self.assertNotIn("inicio_disturbio_s", self._gerar("01", 1)[1])

    def test_faixas_sorteadas_respeitam_tmin_e_a_janela(self):
        for f0 in (60.0, 50.0):
            ciclo = 1.0 / f0
            for classe_id in sorted(self.COM_INICIO):
                for seed in range(60):
                    p = self._gerar(classe_id, seed, f0)[1]
                    t0, d = p["inicio_disturbio_s"], p["duracao_s"]
                    self.assertGreaterEqual(t0, ciclo - 1e-9, (classe_id, seed))
                    self.assertLessEqual(t0 + d, 0.2 - ciclo + 1e-9, (classe_id, seed))
                    if classe_id in self.COM_DURACAO_LIVRE:
                        self.assertGreaterEqual(d, 0.5 * ciclo - 1e-9, (classe_id, seed))
                    self.assertTrue(0.0 <= p["fase_graus"] < 360.0, (classe_id, seed))

    def test_duracao_cobre_de_meio_ciclo_ate_o_que_a_janela_permite(self):
        duracoes = [self._gerar("02", seed)[1]["duracao_s"] for seed in range(400)]
        self.assertLess(min(duracoes), 0.5 / 60.0 * 1.15)
        self.assertGreater(max(duracoes), (0.2 - 2.0 / 60.0) * 0.9)

    def test_formas_distintas_em_200_capturas(self):
        """Formas distintas entre capturas de uma
        classe, com o sorteio:, nenhuma classe volta a ser cópia da mesma onda."""
        for classe_id in self.CLASSES:
            com = {self._gerar(classe_id, seed)[0].tobytes() for seed in range(200)}
            self.assertGreater(len(com), 150, classe_id)
        sem = {self._gerar("01", seed, sorteio=False)[0].tobytes() for seed in range(200)}
        self.assertEqual(len(sem), 1)

    def test_sem_sorteio_nao_acrescenta_campos(self):
        for classe_id in self.CLASSES:
            voltage, parametros = self._gerar(classe_id, 5, sorteio=False)
            self.assertFalse(set(mestre.CHAVES_SORTEIO) & set(parametros), classe_id)

    def test_parametros_ja_sorteados_nao_mudam_com_o_sorteio(self):
        """O sorteio usa um sub-fluxo da seed: flicker_hz, amplitudes etc. de
        uma dada seed são os de antes."""
        for classe_id in ("04", "06", "09", "19", "20"):
            com = self._gerar(classe_id, 77)[1]
            sem = self._gerar(classe_id, 77, sorteio=False)[1]
            for chave, valor in sem.items():
                self.assertEqual(com[chave], valor, (classe_id, chave))

    def test_08_fica_de_fora_com_impulso_e_fase_de_sempre(self):
        voltage, parametros = self._gerar("08", 3)
        self.assertFalse(set(mestre.CHAVES_SORTEIO) & set(parametros))
        np.testing.assert_array_equal(voltage, self._gerar("08", 3, sorteio=False)[0])

    def test_fase_e_inicio_aparecem_na_forma(self):
        """Fase: a senoide fora do evento é sin(2 pi f0 t + fase); evento: o
        nível cai exatamente em [t0, t0 + d)."""
        voltage, p = self._gerar("02", 11)
        fase = np.deg2rad(p["fase_graus"])
        base = np.sin(2.0 * np.pi * 60.0 * self.T + fase)
        dentro = sinais.janela(self.T, p["inicio_disturbio_s"], p["duracao_s"])
        np.testing.assert_allclose(voltage[~dentro], base[~dentro], atol=1e-12)
        np.testing.assert_allclose(voltage[dentro], p["sag_pu"] * base[dentro], atol=1e-12)

    def test_fase_de_disparo_e_multiplo_de_0_1_grau_e_reproduz_a_fase_de_gerar(self):
        experimento = _load_experimento("02")
        for seed in range(60):
            _, p = experimento.gerar(self.T, 60.0, 0, np.random.default_rng(seed))
            disparo = mestre.ExperimentoNativo.fase_de_disparo_graus(
                experimento, p["inicio_disturbio_s"], p["fase_graus"],
            )
            self.assertAlmostEqual(disparo * 10.0, round(disparo * 10.0), places=6)
            fase_no_t0 = (p["fase_graus"] + 360.0 * 60.0 * p["inicio_disturbio_s"]) % 360.0
            delta = abs((fase_no_t0 - disparo + 180.0) % 360.0 - 180.0)
            self.assertLess(delta, 1e-6, seed)

    def test_17_acopla_a_fase_ao_inicio_da_oscilacao(self):
        _, p = self._gerar("17", 4)
        t0 = p["inicio_disturbio_s"]
        self.assertAlmostEqual(math.sin(math.radians(p["fase_graus"]) + 2 * math.pi * 60.0 * t0), 0.0, places=9)

    def test_resultado_congelado_da_v1_15(self):
        """400 assinaturas (20 classes x 60/50 Hz x 2 seeds x 5 índices) do
        ``gerar()`` COM sorteio, perfil literatura, gravadas na v1.15.
        Detecta qualquer mudança do dataset por acidente (mudar de propósito
        exige regravar o fixture e declarar a versão)."""
        ref = json.loads(self.FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(len(ref["hashes"]), 400)
        self.assertEqual(len(ref["portavel"]["resumos"]), 400)
        for chave, esperado in ref["portavel"]["resumos"].items():
            cid, f0, seed, indice = chave.split("/")
            self.assertEqual(
                assinatura_portavel.diferencas(
                    assinatura_portavel.gerar_resumo(_load_experimento(cid), float(f0), int(seed), int(indice)),
                    esperado,
                ), [], chave,
            )

    # -- bancada ---------------------------------------------------------

    def _bancada_pulso(self, classe_id, sorteio=True, f0=60.0):
        """Classe nativa de pulso rodando ``executar()`` inteiro no caminho de
        BANCADA, com um osciloscópio de mentira que entrega o registro físico
        que ``gerar()`` descreve, no lugar do trigger que o pré-trigger pede."""
        config = _config_bancada(self.tmp_dir, sorteio_posicao=sorteio, grid_frequency_hz=f0)
        fonte = AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=415.8)
        osc = mock.Mock()
        osc.medir_extremos = lambda canal: (100.0, -100.0)
        osc.posicoes = []
        osc.definir_pre_trigger.side_effect = lambda **kw: osc.posicoes.append(kw)
        experimento = _carregar_classe(classe_id)(mestre.Bancada(fonte, osc, config))
        registros_osc = []

        def _get_waveform(canal, expected_points):
            ordem = len(registros_osc)
            seed = experimento.seed_da_captura(ordem)
            forma, p = experimento.gerar(
                mestre.tempo(config), f0, 0, np.random.default_rng(seed),
            )
            antes, depois = mestre.ExperimentoBase.MARGEM_ANTES_S, mestre.ExperimentoBase.MARGEM_DEPOIS_S
            n_antes, n_depois = int(round(antes * 30_000)), int(round(depois * 30_000))
            registro = np.concatenate([np.full(n_antes, 0.37), forma, np.full(n_depois, 0.41)])
            pre = p.get("inicio_disturbio_s", experimento.pre_trigger_s)
            osc.ultimo_indice_trigger = int(round(pre * 30_000)) + n_antes
            registros_osc.append(registro)
            volts = registro * config.base_voltage_rms * math.sqrt(2.0)
            return np.arange(registro.size) / 30_000.0, volts

        osc.get_waveform.side_effect = _get_waveform
        return config, fonte, osc, experimento, registros_osc

    def test_pulso_programa_fase_largura_e_pre_trigger_sorteados_e_o_recorte_acerta(self):
        import recortar_margem
        config, fonte, osc, experimento, registros = self._bancada_pulso("02")
        experimento.executar()
        metadata = config.results_dir / "metadata" / "02_sag.jsonl"
        registro = json.loads(metadata.read_text(encoding="utf-8").splitlines()[0])
        t0, d, fase = registro["inicio_disturbio_s"], registro["duracao_s"], registro["fase_graus"]
        self.assertTrue(registro["sorteio_posicao"])
        self.assertNotIn("inicio_disturbio_s", registro["parametros"])
        # pré-trigger efetivo da captura (não o 0,060 da classe) no metadata e no osciloscópio
        self.assertAlmostEqual(registro["pre_trigger_s"], t0)
        self.assertNotAlmostEqual(registro["pre_trigger_s"], 0.060, places=6)
        margem_s = mestre.ExperimentoBase.MARGEM_ANTES_S
        self.assertAlmostEqual(osc.posicoes[-1]["pre_trigger_s"], t0 + margem_s)
        # fase de disparo e largura do pulso na fonte
        disparo = round((fase + 360.0 * 60.0 * t0) % 360.0, 1) % 360.0
        log = fonte.command_log
        self.assertIn(f"TRIGger:SYNChronize:PHASe {disparo:.1f}", log)
        self.assertIn(f"PULSe:WIDTh {d:.8g}", log)
        # inicio_janela segue o pré-trigger variável e o recorte devolve gerar()
        self.assertEqual(registro["pre_trigger_desvio_amostras"], 0)
        n_antes = int(round(margem_s * 30_000))
        self.assertEqual(registro["inicio_janela"], n_antes)
        self.assertFalse(registro["inicio_janela_ajustado"])
        bruto = registros[0]
        inicio, pontos, info = recortar_margem.calcular_recorte(bruto.size, registro)
        self.assertEqual(info["origem"], "inicio_janela")
        forma, _ = experimento.gerar(mestre.tempo(config), 60.0, 0, np.random.default_rng(registro["seed"]))
        np.testing.assert_array_equal(bruto[inicio : inicio + pontos], forma)
        # a validação física comparou com a janela certa
        self.assertTrue(registro["validacao_fisica"]["ok"], registro["validacao_fisica"]["motivos"])

    def test_recorte_acerta_a_janela_pelo_indice_do_trigger_sem_inicio_janela(self):
        """Metadata sem ``inicio_janela`` (só ``indice_trigger`` e o
        ``pre_trigger_s`` DA CAPTURA): o recorte usa o pré-trigger sorteado."""
        import recortar_margem
        config, fonte, osc, experimento, registros = self._bancada_pulso("03")
        experimento.executar()
        registro = json.loads(
            (config.results_dir / "metadata" / "03_swell.jsonl").read_text(encoding="utf-8").splitlines()[0]
        )
        registro.pop("inicio_janela")
        registro.pop("inicio_janela_ajustado")
        bruto = registros[0]
        inicio, pontos, info = recortar_margem.calcular_recorte(bruto.size, registro)
        self.assertEqual(info["origem"], "indice_trigger")
        forma, _ = experimento.gerar(mestre.tempo(config), 60.0, 0, np.random.default_rng(registro["seed"]))
        np.testing.assert_array_equal(bruto[inicio : inicio + pontos], forma)

    def test_pre_trigger_varia_entre_capturas_da_mesma_classe(self):
        config, fonte, osc, experimento, registros = self._bancada_pulso("04")
        experimento.executar()
        linhas = (config.results_dir / "metadata" / "04_interruption.jsonl").read_text(encoding="utf-8").splitlines()
        pres = [json.loads(linha)["pre_trigger_s"] for linha in linhas]
        self.assertEqual(len(pres), 3)
        self.assertEqual(len(set(pres)), 3)
        self.assertEqual(len(osc.posicoes), 3)

    def test_sem_sorteio_o_osciloscopio_nao_e_reposicionado(self):
        config, fonte, osc, experimento, registros = self._bancada_pulso("02", sorteio=False)
        experimento.executar()
        osc.definir_pre_trigger.assert_not_called()
        registro = json.loads(
            (config.results_dir / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8").splitlines()[0]
        )
        self.assertFalse(registro["sorteio_posicao"])
        self.assertEqual(registro["pre_trigger_s"], 0.060)
        self.assertNotIn("inicio_disturbio_s", registro)
        self.assertIn("TRIGger:SYNChronize:PHASe 216.0", fonte.command_log)

    def test_osciloscopio_definir_pre_trigger_so_mexe_na_posicao(self):
        adapter = ScriptedAdapter()
        scope = KeysightDSOX4034A(adapter)
        scope.initialize_safe()
        scope.configure_acquisition(duration_s=0.2, pre_trigger_s=0.060)
        antes = len(adapter.commands)
        scope.definir_pre_trigger(duration_s=0.2, pre_trigger_s=0.0437)
        novos = adapter.commands[antes:]
        self.assertEqual(novos[0], ":TIMebase:POSition -0.0437")
        self.assertFalse([c for c in novos if "RANGe" in c or "REFerence" in c])
        with self.assertRaises(ValueError):
            scope.definir_pre_trigger(duration_s=0.2, pre_trigger_s=0.2)
        sem_config = KeysightDSOX4034A(ScriptedAdapter())
        with self.assertRaises(OscilloscopeError):
            sem_config.definir_pre_trigger(duration_s=0.2, pre_trigger_s=0.01)

    def test_fase_sorteada_na_bancada_waveform_mantem_a_senoide_fora_do_disturbio(self):
        """Limite de bancada com a fase sorteada: a senoide base da forma
        reduzida é a da fase sorteada (e não a de fase 0)."""
        config = _config_bancada(self.tmp_dir, base_voltage_rms=220.0, sorteio_posicao=True)
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=415.8)
        experimento = _carregar_classe("16")(mestre.Bancada(fonte, mock.Mock(), config))
        t = mestre.tempo(config)
        modelo, _ = experimento.gerar(t, 60.0, 0, np.random.default_rng(5))
        forma, parametros = experimento.forma_e_parametros_para_bancada(0, t, 5)
        self.assertIn("fator_disturbio_bancada", parametros)
        senoide = np.sin(2.0 * np.pi * 60.0 * t + np.deg2rad(parametros["fase_graus"]))
        janela = sinais.janela(t, parametros["inicio_disturbio_s"], parametros["duracao_s"])
        np.testing.assert_allclose(forma[~janela], senoide[~janela], atol=1e-12)
        fracao = parametros["fator_disturbio_bancada"]
        np.testing.assert_allclose(forma, senoide + fracao * (modelo - senoide), atol=1e-12)

    def test_todas_as_classes_cabem_a_220v_com_sorteio(self):
        # Exceções desde as recalibrações de 2026-10-22 (127 V/60 Hz): capturas
        # recusadas pelo teto, mesmas classes do teste de 220 V sem sorteio.
        recusadas_esperadas = {"13": 1, "14": 3, "17": 3, "18": 1, "19": 1}
        recusadas = {}
        for classe_id in self.CLASSES:
            if classe_id == "03":
                continue  # 03 a 220 V já pulava níveis (1,4 pu > 300 Vrms)
            config = _config_bancada(self.tmp_dir, base_voltage_rms=220.0, sorteio_posicao=True)
            fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=415.8)
            experimento = _carregar_classe(classe_id)(mestre.Bancada(fonte, mock.Mock(), config))
            for indice_global, capture_index in experimento.plano_de_capturas(False):
                info = experimento.avaliar_captura_na_bancada(indice_global, capture_index)
                if not info["cabe"]:
                    recusadas[classe_id] = recusadas.get(classe_id, 0) + 1
                    self.assertIn("teto", info["motivo"], (classe_id, indice_global))
        self.assertEqual(recusadas, recusadas_esperadas)

    def test_analisar_sessao_reconstroi_a_forma_com_sorteio(self):
        import analisar_sessao
        for classe_id in ("01", "02", "07", "10", "18", "20"):
            voltage, p = self._gerar(classe_id, 21)
            metadado = {
                "fs_hz": 30_000.0, "pontos": 6000, "seed": 21, "nivel_indice": 0, "f0_hz": 60.0,
                "tensao_base_rms": 127.0, "sorteio_posicao": True,
                **{chave: p[chave] for chave in mestre.CHAVES_SORTEIO if chave in p},
            }
            np.testing.assert_array_equal(analisar_sessao._reconstruir_esperado(classe_id, metadado), voltage)

    def test_metadata_simulado_grava_inicio_duracao_e_fase_no_nivel_de_cima(self):
        config = _config_bancada(self.tmp_dir, sorteio_posicao=True, sim_captures_per_class=3)
        classe = _carregar_classe("10")(mestre.Bancada(None, None, config))
        classe.executar()
        arquivos = list(self.tmp_dir.rglob("10_*.jsonl"))
        self.assertTrue(arquivos)
        registros = [json.loads(l) for l in arquivos[0].read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(registros), 3)
        for registro in registros:
            for chave in mestre.CHAVES_SORTEIO:
                self.assertIn(chave, registro)
                self.assertNotIn(chave, registro["parametros"])
            self.assertTrue(registro["sorteio_posicao"])
        self.assertEqual(len({r["fase_graus"] for r in registros}), 3)

    def test_estimativa_do_run_all_conta_cada_captura_trace_como_gravacao_exata(self):
        cls = _carregar_classe("10")
        info = mestre.capturas_efetivas_da_classe(cls, _config_bancada(self.tmp_dir, sorteio_posicao=True))
        self.assertTrue(info["escritas_trace_exatas"])
        self.assertEqual(info["escritas_trace"], 36)  # 3 capturas (padrão da 10 desde a v1.15) x 12 ciclos a 60 Hz
        info = mestre.capturas_efetivas_da_classe(cls, _config_bancada(self.tmp_dir, sorteio_posicao=False))
        self.assertFalse(info["escritas_trace_exatas"])

    def test_cli_set_sorteio(self):
        import io
        from contextlib import redirect_stdout
        import cli
        anterior = mestre.SORTEIO_POSICAO
        try:
            for valor, esperado in (("off", False), ("on", True)):
                with redirect_stdout(io.StringIO()):
                    codigo = cli.SessaoCLI().cmd_set(["sorteio", valor])
                self.assertEqual(codigo, 0)
                self.assertIs(mestre.SORTEIO_POSICAO, esperado)
                self.assertIs(mestre._build_config().sorteio_posicao, esperado)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.SessaoCLI().cmd_set(["sorteio", "talvez"]), 1)
            self.assertIn("set sorteio on|off", cli.HELP_TEXT)
        finally:
            mestre.SORTEIO_POSICAO = anterior

class ParametrosSorteadosNasCompostasTests(unittest.TestCase):
    """v1.15 — compostas 10 a 16 sorteiam os parâmetros em ``gerar()`` com o
    sorteio ligado (`arquivo/analises:docs/analise-2026-10-12/pendente/compostas_sorteadas_REVISAR.md`), e o teste
    de cobertura de formas: nenhuma classe volta a ter poucas formas
    distintas no simulado."""

    COMPOSTAS = [f"{i}" for i in range(10, 17)]
    CLASSES = [f"{i:02d}" for i in range(1, 21)]
    T = np.arange(6000, dtype=np.float64) / 30_000.0
    # Item f): N capturas simuladas por classe, forma contada ANTES do ruído
    # (o que gerar() devolve). N = 100: as 4 combinações custam ~2 s no total e
    # deixa o pior caso (classes só com fase sorteada, 3600 valores de 0,1
    # grau: ~1,4 colisões esperadas em 100) a ~98 formas. MINIMO = 90 (90 %)
    # fica longe das colisões casuais (10 colisões de 100 não ocorrem) e
    # reprova qualquer classe que volte a repetir a mesma onda (1, 2 ou 5).
    N_CAPTURAS = 100
    MINIMO_DISTINTAS = 90

    @staticmethod
    def _com(classe_id, perfil="literatura", sorteio=True):
        import dataclasses
        experimento = _load_experimento(classe_id)
        experimento.config = dataclasses.replace(
            experimento.config, perfil=perfil, sorteio_posicao=sorteio,
        )
        return experimento

    def _formas(self, experimento, f0=60.0, n=None):
        n = self.N_CAPTURAS if n is None else n
        formas, parametros = set(), []
        for indice in range(n):
            tensao, p = experimento.gerar(
                self.T, f0, indice, np.random.default_rng(experimento.seed_da_captura(indice)),
            )
            formas.add(np.asarray(tensao, dtype=np.float64).tobytes())
            parametros.append(p)
        return formas, parametros

    def test_toda_classe_tem_formas_distintas_suficientes_em_todos_os_perfis(self):
        """Item f): falha se alguma das 20 classes tiver menos de
        MINIMO_DISTINTAS formas distintas em N_CAPTURAS (simulado, antes do
        ruído), nos 3 perfis a 60 Hz e na literatura a 50 Hz."""
        casos = [(perfil, 60.0) for perfil in ("literatura", "norma", "fronteira")] + [("literatura", 50.0)]
        for perfil, f0 in casos:
            for classe_id in self.CLASSES:
                formas, _ = self._formas(self._com(classe_id, perfil), f0)
                self.assertGreaterEqual(
                    len(formas), self.MINIMO_DISTINTAS, f"classe {classe_id}, {perfil}, {f0:g} Hz",
                )

    def test_o_teste_de_formas_distintas_reprova_uma_classe_que_repete_a_onda(self):
        """Sem sorteio as compostas voltam a ser 1 forma só (34a0d82): o limite
        do teste acima as pegaria."""
        for classe_id in self.COMPOSTAS:
            formas, _ = self._formas(self._com(classe_id, sorteio=False), n=20)
            self.assertLess(len(formas), self.MINIMO_DISTINTAS, classe_id)

    def test_parametros_sorteados_dentro_da_faixa_do_perfil(self):
        import perfis
        faixas = {
            "sag_pu": "sag_composto", "swell_pu": "swell_composto", "thd": "thd_composto",
            "flicker_depth": "flicker_composto", "flicker_hz": "flicker_composto_hz",
            "oscillation_hz": "oscilacao_composto_hz",
        }
        for perfil in perfis.PERFIS:
            for classe_id in self.COMPOSTAS:
                experimento = self._com(classe_id, perfil)
                _, todos = self._formas(experimento, n=60)
                for p in todos:
                    for chave, componente in faixas.items():
                        if chave not in p:
                            continue
                        intervalo = perfis.FAIXAS_SORTEADAS[componente][perfil]
                        if intervalo is None:  # fronteira de sag/swell: níveis discretos
                            self.assertIn(p[chave], perfis.FAIXAS[componente][perfil], (classe_id, chave))
                        else:
                            self.assertTrue(intervalo[0] <= p[chave] <= intervalo[1], (perfil, classe_id, chave, p))
                if perfil != "fronteira":
                    for chave in set(todos[0]) & set(faixas):
                        self.assertGreater(len({p[chave] for p in todos}), 50, (perfil, classe_id, chave))

    def test_literatura_cobre_as_faixas_de_componentes_compostos(self):
        """sag U(0,1; 0,9), THD U(0,05; 0,20), f_osc U(300; 2400), flicker U(8; 25)."""
        esperado = {
            "10": {"sag_pu": (0.1, 0.9), "thd": (0.05, 0.20)},
            "11": {"sag_pu": (0.1, 0.9), "flicker_hz": (8.0, 25.0)},
            "12": {"oscillation_hz": (300.0, 2400.0)}, "14": {"oscillation_hz": (300.0, 2400.0)},
            "15": {"thd": (0.05, 0.20), "flicker_hz": (8.0, 25.0)},
        }
        for classe_id, chaves in esperado.items():
            _, todos = self._formas(self._com(classe_id), n=100)
            for chave, (lo, hi) in chaves.items():
                valores = [p[chave] for p in todos]
                self.assertGreaterEqual(min(valores), lo, (classe_id, chave))
                self.assertLessEqual(max(valores), hi, (classe_id, chave))
                self.assertLess(min(valores), lo + 0.1 * (hi - lo), (classe_id, chave))
                self.assertGreater(max(valores), hi - 0.1 * (hi - lo), (classe_id, chave))

    def test_sem_sorteio_as_compostas_voltam_aos_valores_fixos(self):
        fixos = {"sag_pu": 0.5, "swell_pu": 1.3, "thd": 0.20, "flicker_depth": 0.10,
                 "flicker_hz": 15.0, "oscillation_hz": 600.0}
        for classe_id in self.COMPOSTAS:
            _, p = self._com(classe_id, sorteio=False).gerar(self.T, 60.0, 0, np.random.default_rng(3))
            for chave, valor in p.items():
                if chave in fixos:
                    self.assertEqual(valor, fixos[chave], (classe_id, chave))

    def test_sorteio_dos_parametros_nao_muda_o_sub_fluxo_de_inicio_duracao_fase(self):
        """Os parâmetros saem do rng da classe; início/duração/fase, de um
        sub-fluxo da mesma seed: o sorteio de posição é o que
        ``sortear_posicao`` devolve para a seed pura."""
        opcoes = {
            "10": dict(inicio_legado_s=0.060, duracao_legada_s=0.060, duracao_variavel=True),
            "11": dict(inicio_legado_s=0.060, duracao_legada_s=0.060, duracao_variavel=True),
            "12": dict(inicio_legado_s=0.060, duracao_legada_s=0.040, duracao_variavel=True),
            "13": dict(inicio_legado_s=0.060, duracao_legada_s=0.060, duracao_variavel=True),
            "14": dict(inicio_legado_s=0.060, duracao_legada_s=0.040, duracao_variavel=True),
            "15": {},
            "16": dict(inicio_legado_s=0.060, duracao_legada_s=0.060, duracao_variavel=True),
        }
        for classe_id, kw in opcoes.items():
            experimento = self._com(classe_id)
            for seed in range(25):
                _, p = experimento.gerar(self.T, 60.0, 0, np.random.default_rng(seed))
                s = mestre.sortear_posicao(np.random.default_rng(seed), experimento.config, 60.0, **kw)
                self.assertEqual(p["fase_graus"], s.fase_graus, (classe_id, seed))
                self.assertEqual(p.get("inicio_disturbio_s"), s.inicio_s, (classe_id, seed))
                self.assertEqual(p.get("duracao_s"), s.duracao_s, (classe_id, seed))

    def test_padrao_de_capturas_das_compostas_e_3(self):
        for classe_id in self.COMPOSTAS + ["17"]:
            self.assertEqual(_carregar_classe(classe_id).capturas_padrao, 3, classe_id)

    def test_gancho_de_bancada_traduz_o_fator_k_com_os_parametros_sorteados(self):
        """forma física = senoide + k (gerar() - senoide) é a forma construída
        só com os parâmetros ``*_bancada``, para parâmetros sorteados (inclui
        frequência de flicker e de oscilação)."""
        import perfis
        k = 0.6
        for seed in range(12):
            for classe_id in ("10", "11", "12", "13", "14", "16"):
                experimento = self._com(classe_id)
                forma, p = experimento.gerar(self.T, 60.0, 0, np.random.default_rng(seed))
                tau = p["fase_graus"] / (360.0 * 60.0)
                tt = self.T + tau
                senoide = np.sin(2.0 * np.pi * 60.0 * tt)
                fisica = senoide + k * (forma - senoide)
                b = experimento.parametros_com_disturbio_reduzido(p, k)
                mask = sinais.janela(self.T, p["inicio_disturbio_s"], p["duracao_s"])
                esperada = senoide.copy()
                if classe_id in ("10", "13", "16"):
                    nivel = b[next(c for c in b if c.endswith("_pu_bancada"))]
                    esperada[mask] = nivel * sinais.onda_com_harmonicos(tt[mask], b["thd_bancada"], frequencia_hz=60.0)
                elif classe_id == "11":
                    esperada[mask] = b["sag_pu_bancada"] * senoide[mask] * (
                        1.0 + b["flicker_depth_bancada"] * np.sin(2.0 * np.pi * p["flicker_hz"] * self.T[mask])
                    )
                else:
                    chave = "sag_pu_bancada" if classe_id == "12" else "swell_pu_bancada"
                    esperada[mask] = b[chave] * senoide[mask]
                    esperada = esperada + sinais.oscilacao_amortecida(
                        self.T, inicio_s=p["inicio_disturbio_s"], duracao_s=p["duracao_s"],
                        frequencia_hz=p["oscillation_hz"], amplitude_pu=b["oscillation_amplitude_pu_bancada"],
                    )
                np.testing.assert_allclose(esperada, fisica, atol=1e-9, err_msg=f"{classe_id} seed {seed}")

class TresVersoesTests(unittest.TestCase):
    """v1.15 — modelo / programada / medida (docs/tres_versoes.md). O ponto
    central: ``AmetekMX30.montar_programacao`` e ``program_capture`` nunca
    divergem, porque a segunda usa a primeira."""

    T = np.arange(6000, dtype=np.float64) / 30_000.0
    WAVEFORM = ("06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "20")

    @staticmethod
    def _fonte():
        return AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0, max_current_a=0.5)

    def _formas(self):
        """(nome, forma, frequência, tensão base, offset) — gerar() real."""
        casos = []
        for classe_id in self.WAVEFORM:
            for f0, base in ((50.0, 127.0), (60.0, 230.0)):
                for sorteio in (False, True):
                    experimento = _load_experimento(classe_id)
                    import dataclasses
                    experimento.config = dataclasses.replace(experimento.config, sorteio_posicao=sorteio)
                    forma, _ = experimento.gerar(self.T, f0, 0, np.random.default_rng(31 + int(sorteio)))
                    casos.append((f"{classe_id} f0={f0:g} sorteio={sorteio}", np.asarray(forma), f0, base, 0.0))
        senoide = np.sin(2.0 * np.pi * 60.0 * self.T)
        casos.append(("senoide + DC", senoide + 0.05, 60.0, 127.0, 0.05))
        casos.append(("zeros", np.zeros(6000), 50.0, 127.0, 0.0))
        return casos

    def test_funcao_pura_gera_byte_a_byte_o_que_program_capture_envia(self):
        for nome, forma, f0, base, dc in self._formas():
            with self.subTest(nome):
                programacao = AmetekMX30.montar_programacao(
                    forma, base_voltage_rms=base, frequency_hz=f0, dc_offset_pu=dc,
                )
                fonte = self._fonte()
                # P04: o teste de serialização não pode exigir que o ORM
                # programe formas que excedem os limites reais. Primeiro
                # comprova a recusa sem IO; testa a mesma forma a 5 Vrms.
                acima = (
                    np.max(np.abs(forma)) * base * np.sqrt(2) > fonte.max_peak_v
                    or programacao.pico_reconstruido_v > fonte.max_peak_v
                    or np.max(programacao.list_voltages_rms) > fonte.max_voltage_rms
                )
                if acima:
                    with self.assertRaises(ParameterOutOfBoundsError):
                        fonte.program_capture(forma, base_voltage_rms=base, frequency_hz=f0, dc_offset_pu=dc)
                    self.assertEqual(fonte.command_log, [])
                    base = 5.0
                    programacao = AmetekMX30.montar_programacao(
                        forma, base_voltage_rms=base, frequency_hz=f0, dc_offset_pu=dc,
                    )
                fonte.program_capture(forma, base_voltage_rms=base, frequency_hz=f0, dc_offset_pu=dc)
                enviados = [c for c in fonte.command_log if c.startswith("TRACe:DATA ")]
                self.assertEqual(enviados, [programacao.comando_trace(i) for i in range(programacao.ciclos)])
                self.assertIn(f"SOURce:LIST:VOLTage {programacao.texto_list_voltages()}", fonte.command_log)
                self.assertIn(
                    "SOURce:LIST:DWELl " + ",".join(f"{programacao.pontos_por_ciclo / 30000.0:.10g}" for _ in range(programacao.ciclos)),
                    fonte.command_log,
                )
                self.assertEqual(fonte.last_programmed_peak_v, programacao.pico_reconstruido_v)
                self.assertIs(fonte.ultima_programacao.__class__, programacao.__class__)
                np.testing.assert_array_equal(fonte.ultima_programacao.traces, programacao.traces)

    def test_programada_tem_o_rms_do_list_voltage_em_cada_ciclo(self):
        forma, _ = _load_experimento("10").gerar(self.T, 60.0, 0, np.random.default_rng(3))
        programacao = AmetekMX30.montar_programacao(forma, base_voltage_rms=127.0, frequency_hz=60.0)
        programada = programacao.programada_pu()
        self.assertEqual(programada.shape, (6000,))
        n = programacao.pontos_por_ciclo
        for i, rms_v in enumerate(programacao.list_voltages_rms):
            ciclo_v = programada[i * n:(i + 1) * n] * 127.0 * np.sqrt(2.0)
            # reamostragem 1024 -> n pontos muda o rms de ~1e-4; a ordem de grandeza e a conta valem
            self.assertAlmostEqual(float(np.sqrt(np.mean(ciclo_v ** 2))), float(rms_v), delta=max(0.02 * float(rms_v), 0.05))

    def test_programada_de_senoide_pura_e_a_senoide(self):
        senoide = np.sin(2.0 * np.pi * 50.0 * self.T)
        programada = AmetekMX30.montar_programacao(senoide, base_voltage_rms=127.0, frequency_hz=50.0).programada_pu()
        # Com a interpolação periódica em _resample_cycle (ciclo fechado) o erro
        # é só o da reamostragem 600 -> 1024 -> 600 (~1e-5 pu medido); antes,
        # até 1,3e-3 pu nas últimas amostras (np.interp repetia a última).
        np.testing.assert_allclose(programada, senoide, atol=1e-4)

    def test_programada_soma_o_offset_dc_enviado(self):
        senoide = np.sin(2.0 * np.pi * 60.0 * self.T) + 0.0895731
        programada = AmetekMX30.montar_programacao(
            senoide, base_voltage_rms=127.0, frequency_hz=60.0, dc_offset_pu=0.0895731,
        ).programada_pu()
        np.testing.assert_allclose(programada, senoide, atol=2e-3)

    def test_montar_programacao_mantem_as_recusas_de_antes(self):
        with self.assertRaises(ValueError):
            AmetekMX30.montar_programacao(np.zeros(5999), base_voltage_rms=127.0, frequency_hz=60.0)
        with self.assertRaises(ValueError):
            AmetekMX30.montar_programacao(np.full(6000, np.nan), base_voltage_rms=127.0, frequency_hz=60.0)
        with self.assertRaises(ValueError):
            AmetekMX30.montar_programacao(np.zeros(6000), base_voltage_rms=127.0, frequency_hz=61.0)

    # --- nativas -----------------------------------------------------------

    def _nativa(self, classe_id, parametros, f0=60.0, base=127.0):
        experimento = _sem_sorteio(_load_experimento(classe_id))
        programada, origem = experimento.forma_programada(
            np.zeros(6000), parametros, 0, self.T,
        )
        return programada, origem

    def test_pulse_programa_o_nivel_truncado_em_0_1_v(self):
        programada, origem = self._nativa("04", {"interruption_pu": 0.0171752})
        self.assertIn("PULSe", origem)
        nivel = 2.2 / 127.0  # 0,0171752 x 127 = 2,1813 V -> 2,2 V
        mask = sinais.janela(self.T, 0.060, 0.060)
        senoide = np.sin(2.0 * np.pi * 60.0 * self.T)
        np.testing.assert_allclose(programada[mask], senoide[mask] * nivel, atol=1e-12)
        np.testing.assert_allclose(programada[~mask], senoide[~mask], atol=1e-12)

    def test_pulse_usa_a_posicao_sorteada_do_metadata(self):
        experimento = _load_experimento("02")
        parametros = {"sag_pu": 0.5, "inicio_disturbio_s": 0.1, "duracao_s": 0.05, "fase_graus": 90.0}
        programada, _ = experimento.forma_programada(np.zeros(6000), parametros, 0, self.T)
        mask = sinais.janela(self.T, 0.1, 0.05)
        senoide = np.sin(2.0 * np.pi * 60.0 * (self.T + 90.0 / (360.0 * 60.0)))
        np.testing.assert_allclose(programada, senoide * np.where(mask, 0.5, 1.0), atol=1e-12)

    def test_step_e_offset_das_nativas_01_e_19(self):
        normal, _ = self._nativa("01", {})
        np.testing.assert_allclose(normal, np.sin(2.0 * np.pi * 60.0 * self.T), atol=1e-12)
        dc, origem = self._nativa("19", {"dc_offset_pu": 0.0505661})
        self.assertIn("OFFSet", origem)
        np.testing.assert_allclose(dc, np.sin(2.0 * np.pi * 60.0 * self.T) + 0.0505661, atol=1e-7)

    def test_csine_programada_tem_o_thd_pedido(self):
        for thd in (0.05, 0.10, 0.20):
            programada, origem = self._nativa("05", {"thd": thd})
            self.assertIn("CSINe", origem)
            self.assertAlmostEqual(sinais.thd_medida(programada, fs_hz=30_000.0, f0=60.0), thd, delta=0.003)
            self.assertAlmostEqual(float(np.sqrt(np.mean(programada ** 2))), 1.0 / np.sqrt(2.0), places=3)

    def test_csine_a_30_por_cento_usa_o_caminho_trace(self):
        experimento = _sem_sorteio(_load_experimento("05"))
        indice_30 = list(experimento.NIVEIS_THD).index(0.30)
        self.assertTrue(experimento.grava_trace(indice_30))
        forma, parametros = experimento.gerar(self.T, 60.0, indice_30, np.random.default_rng(1))
        programada, origem = experimento.forma_programada(forma, parametros, indice_30, self.T)
        self.assertIn("TRACe", origem)
        esperada = AmetekMX30.montar_programacao(forma, base_voltage_rms=127.0, frequency_hz=60.0).programada_pu()
        np.testing.assert_array_equal(programada, esperada)

    def test_frequency_drift_programa_dois_degraus_com_fase_continua(self):
        programada, origem = self._nativa("18", {"start_hz": 57.0, "end_hz": 63.0})
        self.assertIn("LIST:FREQuency", origem)
        fase = np.concatenate([2.0 * np.pi * 57.0 * self.T[:3000], 2.0 * np.pi * 57.0 * 3000 / 30000.0 + 2.0 * np.pi * 63.0 * (self.T[3000:] - self.T[3000])])
        np.testing.assert_allclose(programada[:3000], np.sin(fase[:3000]), atol=1e-9)
        np.testing.assert_allclose(programada[3001:], np.sin(fase[3001:]), atol=1e-9)

    # --- gravação ----------------------------------------------------------

    def test_simulado_grava_modelo_e_programada_empilhados_e_aponta_no_metadata(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = mestre.Config(
                fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
                base_voltage_rms=127.0, snr_levels_db=(), base_seed=5,
                capture_current=False, current_base_a=None, results_dir=tmp_dir / "r",
                sim_captures_per_class=3, real_captures_per_class=1, disturbance_start_s=0.06,
            )
            bancada = mestre.Bancada(None, None, config)
            for classe_id in ("02", "10"):
                script = next(s for s in mestre._experiment_scripts() if s.stem == classe_id)
                mestre.Bancada._carregar_classe_experimento(script)(bancada).executar()
            self.assertFalse((config.results_dir / "tres_versoes").exists())  # formato 2: tudo no .npz da classe
            for stem in ("02_sag", "10_sag_harmonics"):
                with np.load(config.results_dir / f"{stem}.npz", allow_pickle=True) as dados:
                    # simulado: não há instrumento, a "medida" é a série do dataset (= modelo)
                    np.testing.assert_array_equal(dados["literatura/modelo"], dados["literatura/medida"])
                    self.assertEqual(dados["literatura/programada"].shape, (3, 6000))
                    self.assertFalse(np.any(np.isnan(dados["literatura/programada"])))
                linha = json.loads((config.results_dir / "metadata" / f"{stem}.jsonl").read_text(encoding="utf-8").splitlines()[0])
                self.assertEqual(linha["tres_versoes"]["arquivo"], f"{stem}.npz")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_fisico_grava_as_tres_versoes_alinhadas_na_janela(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = mestre.Config(
                fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
                base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
                capture_current=False, current_base_a=None, results_dir=tmp_dir / "r",
                sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
            )
            fonte = AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
            bancada = mestre.Bancada(fonte, mock.Mock(), config)
            registro = np.concatenate([np.zeros(600), np.sin(2.0 * np.pi * 60.0 * np.arange(6000) / 30000.0), np.zeros(1500)])

            class _Classe(mestre.ExperimentoWaveform):
                id = "95"
                nome = "TESTE_TRES"

                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {}

                def _capturar_real(self, capture_index, t, rng):
                    modelo, _ = self.gerar(t, 60.0, capture_index, rng)
                    forma = 0.8 * modelo  # "bancada" reduziu a forma
                    self.fonte.program_capture(forma, base_voltage_rms=127.0, frequency_hz=60.0)
                    self._registrar_versoes(modelo, forma, {}, capture_index, t, self._programacao_enviada())
                    return np.arange(8100) / 30000.0, registro, None, {}

            experimento = _Classe(bancada)
            experimento.osc = mock.Mock()
            experimento._preparar_acquisicao_real = lambda: None
            experimento.executar()
            arquivo = config.results_dir / "95_teste_tres.npz"
            with np.load(arquivo, allow_pickle=True) as dados:
                self.assertEqual(dados["literatura/modelo"].shape, (1, 6000))
                np.testing.assert_allclose(dados["literatura/modelo"][0], np.sin(2.0 * np.pi * 60.0 * self.T), atol=1e-12)
                np.testing.assert_allclose(dados["literatura/programada"][0], 0.8 * dados["literatura/modelo"][0], atol=2e-3)
                # medida = o registro inteiro (com a folga); a janela rotulada é o recorte por inicio_janela
                self.assertEqual(dados["literatura/medida"].shape, (1, 8100))
                inicio = int(dados["literatura/inicio_janela"][0])
                self.assertEqual(inicio, 600)
                np.testing.assert_array_equal(dados["literatura/medida"][0][inicio:inicio + 6000], registro[600:6600])
                self.assertEqual(dados["tempo_janela_ms"].shape, (6000,))
            linha = json.loads((config.results_dir / "metadata" / "95_teste_tres.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(linha["tres_versoes"]["arquivo"], "95_teste_tres.npz")
            self.assertEqual((linha["arquivo_classe"], linha["perfil"], linha["indice_no_arquivo"]), ("95_teste_tres.npz", "literatura", 0))
            self.assertFalse((config.results_dir / "tres_versoes").exists())
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_falha_na_programada_nao_derruba_a_captura(self):
        experimento = _BancadaFake.experimento_sem_niveis()
        experimento._registrar_versoes(np.zeros(6000), np.zeros(5999), {}, 0, self.T)
        self.assertIn("modelo", experimento._versoes_atuais)
        self.assertNotIn("programada", experimento._versoes_atuais)

    # --- script offline ----------------------------------------------------

    def test_script_offline_reconstroi_o_que_a_bancada_programou(self):
        gerar_tres = _carregar_script("gerar_tres_versoes")
        k = 0.6
        registro = {
            "id_captura": "10-0001", "classe": "SAG_HARMONICS", "seed": 12345, "nivel_indice": 0, "simulado": False,
            "fs_hz": 30_000.0, "pontos": 6000, "f0_hz": 60.0, "tensao_base_rms": 220.0,
            "parametros": {"sag_pu": 0.5, "fator_disturbio_bancada": k},
        }
        resultado = gerar_tres.reconstruir_versoes(registro)
        modelo, _ = _sem_sorteio(_load_experimento("10")).gerar(self.T, 60.0, 0, np.random.default_rng(12345))
        np.testing.assert_array_equal(resultado["modelo"], modelo)
        senoide = np.sin(2.0 * np.pi * 60.0 * self.T)
        esperada = AmetekMX30.montar_programacao(
            senoide + k * (modelo - senoide), base_voltage_rms=220.0, frequency_hz=60.0,
        ).programada_pu()
        np.testing.assert_array_equal(resultado["programada"], esperada)

    def test_script_offline_nao_altera_a_sessao_e_recusa_pasta_com_arquivos(self):
        gerar_tres = _carregar_script("gerar_tres_versoes")
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            sessao = tmp_dir / "sessao"
            (sessao / "metadata").mkdir(parents=True)
            registro = {
                "id_captura": "02-0001", "classe": "SAG", "seed": 7, "nivel_indice": 0, "simulado": False,
                "fs_hz": 30_000.0, "pontos": 6000, "f0_hz": 50.0, "tensao_base_rms": 127.0,
                "parametros": {"sag_pu": 0.1},
            }
            (sessao / "metadata" / "02_sag.jsonl").write_text(json.dumps(registro) + "\n", encoding="utf-8")
            np.savez(sessao / "02_sag_sag_pu-0.1.npz", classe="SAG", id_captura=np.array(["02-0001"], dtype=object), tensao_pu=np.zeros((1, 8100)))
            antes = {p.name: p.read_bytes() for p in sessao.rglob("*") if p.is_file()}
            linhas = gerar_tres.gerar_sessao(sessao, sessao / "tres_versoes")
            self.assertEqual(linhas[0]["arquivo"], "02_sag_sag_pu-0.1.npz")
            with np.load(sessao / "tres_versoes" / "02_sag_sag_pu-0.1.npz", allow_pickle=True) as dados:
                self.assertEqual(dados["programada_pu"].shape, (1, 6000))
            depois = {p.name: p.read_bytes() for p in sessao.rglob("*") if p.is_file() and "tres_versoes" not in p.parts}
            self.assertEqual(antes, depois)
            with self.assertRaises(FileExistsError):
                gerar_tres.gerar_sessao(sessao, sessao / "tres_versoes")
            gerar_tres.gerar_sessao(sessao, sessao / "tres_versoes", refazer=True)
            with self.assertRaises(FileExistsError):
                gerar_tres.gerar_sessao(sessao, sessao / "metadata", refazer=True)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class Classe08FronteiraTests(unittest.TestCase):
    """`arquivo/analises:docs/analise-2026-10-12/pendente/classe08_fronteira_REVISAR.md`: a 50 Hz o impulso de
    80 ms (amostra 0 do 5.º ciclo) saiu em 100 ms; ele não pode mais cair
    perto de uma fronteira de ciclo, e a validação física confere a posição."""

    T = np.arange(6000, dtype=np.float64) / 30_000.0

    def _experimento(self, f0, *, sorteio=True, base_v=127.0):
        import dataclasses
        experimento = _load_experimento("08")
        experimento.fonte = mock.Mock(max_peak_v=415.8)
        experimento.osc = mock.Mock()
        experimento.config = dataclasses.replace(
            experimento.config, grid_frequency_hz=f0, sorteio_posicao=sorteio, base_voltage_rms=base_v,
        )
        return experimento

    def _distancias(self, experimento, f0):
        """(amostras entre a fronteira anterior e o impulso, entre o impulso e a próxima)."""
        indices = experimento._indices_impulso(30_000.0, f0)
        n = int(round(30_000.0 / f0))
        return int(indices[0]) % n, n - int(indices[0]) % n - indices.size

    def test_o_impulso_nunca_cai_a_menos_de_n_amostras_da_fronteira_a_50_e_60hz(self):
        minimo = _load_experimento("08").DISTANCIA_MIN_FRONTEIRA_AMOSTRAS
        for f0 in (50.0, 60.0):
            experimento = self._experimento(f0)
            antes, depois = self._distancias(experimento, f0)
            self.assertGreaterEqual(antes, minimo, f0)
            self.assertGreaterEqual(depois, minimo, f0)
            voltage, parametros = experimento.gerar(self.T, f0, 0, np.random.default_rng(5))
            achados = np.flatnonzero(np.abs(voltage - np.sin(2.0 * np.pi * f0 * self.T)) > 1.0)
            np.testing.assert_array_equal(achados, experimento._indices_impulso(30_000.0, f0))
            self.assertEqual(parametros["pulse_samples"], achados.size)

    def test_qualquer_inicio_preferido_e_empurrado_para_fora_da_fronteira(self):
        """Varre o início preferido por todas as amostras da janela: a regra
        vale para qualquer valor de ``INICIO_IMPULSO_S``, não só os 80 ms."""
        for f0 in (50.0, 60.0):
            experimento = self._experimento(f0)
            minimo = experimento.DISTANCIA_MIN_FRONTEIRA_AMOSTRAS
            n = int(round(30_000.0 / f0))
            for amostra in range(0, 6000 - 2):
                experimento.INICIO_IMPULSO_S = amostra / 30_000.0
                antes, depois = self._distancias(experimento, f0)
                self.assertGreaterEqual(antes, minimo, (f0, amostra))
                self.assertGreaterEqual(depois, minimo, (f0, amostra))
                if amostra % n >= minimo and n - amostra % n - 2 >= minimo:
                    # já longe da fronteira: a regra não mexe
                    self.assertEqual(int(experimento._indices_impulso(30_000.0, f0)[0]), amostra)

    def test_50hz_vai_para_90ms_no_meio_do_ciclo_e_60hz_continua_em_80ms(self):
        a50 = self._experimento(50.0)._indices_impulso(30_000.0, 50.0)
        a60 = self._experimento(60.0)._indices_impulso(30_000.0, 60.0)
        self.assertEqual(list(a50), [2700, 2701])
        self.assertEqual(list(a60), [2400, 2401])
        # mesmo nível de partida do 80 ms de antes (cruzamento por zero)
        self.assertAlmostEqual(math.sin(2.0 * math.pi * 50.0 * a50[0] / 30_000.0), 0.0, places=9)

    def test_sorteio_desligado_reproduz_o_80ms_de_34a0d82_tambem_a_50hz(self):
        for f0 in (50.0, 60.0):
            experimento = self._experimento(f0, sorteio=False)
            self.assertEqual(list(experimento._indices_impulso(30_000.0, f0)), [2400, 2401], f0)

    def test_forma_para_bancada_calcula_a_amplitude_pela_partida_real_e_grava_a_posicao(self):
        for f0, esperado_s in ((50.0, 0.090), (60.0, 0.080)):
            experimento = self._experimento(f0)
            onda, parametros = experimento.gerar(self.T, f0, 0, np.random.default_rng(3))
            forma = experimento.forma_para_bancada(onda, parametros, 0)
            self.assertAlmostEqual(parametros["inicio_impulso_s"], esperado_s, places=9)
            indices = experimento._indices_impulso(30_000.0, f0)
            base = np.sin(2.0 * np.pi * f0 * self.T)
            np.testing.assert_allclose(forma[indices] - base[indices], parametros["amplitude_bancada_pu"])
            fora = np.ones(6000, dtype=bool)
            fora[indices] = False
            np.testing.assert_allclose(forma[fora], base[fora])
            # o pico previsto continua dentro do teto de 90 % (como no 80 ms de antes)
            self.assertLessEqual(parametros["pico_previsto_v"], 0.9 * 415.8 + 1e-6)

    def test_montagem_da_trace_nao_desloca_o_impulso_a_50_nem_a_60hz(self):
        """Hipótese do deslocamento de um ponto, parte da montagem: com a
        função de montagem do projeto, um impulso na amostra 0 do ciclo vai
        para os pontos 0 a 3 da TRACE (não para o fim) e a forma reconstruída
        o devolve na mesma amostra, antes e depois da correção."""
        for f0, inicio in ((50.0, 2400), (50.0, 2700), (60.0, 2400)):
            forma = np.sin(2.0 * np.pi * f0 * self.T)
            forma[inicio:inicio + 2] += 1.3374832769767175
            programacao = AmetekMX30.montar_programacao(forma, base_voltage_rms=127.0, frequency_hz=f0)
            n = programacao.pontos_por_ciclo
            ponto_no_ciclo = (inicio % n) * AmetekMX30.TRACE_POINTS / n
            trace = programacao.traces[inicio // n]
            salto = int(np.argmax(np.abs(np.diff(trace))))  # a queda do impulso: pontos p+1 a p+3
            self.assertTrue(ponto_no_ciclo - 2 <= salto <= ponto_no_ciclo + 4, (f0, inicio, salto, ponto_no_ciclo))
            reconstruida = programacao.programada_pu()
            achados = np.flatnonzero(np.abs(reconstruida - np.sin(2.0 * np.pi * f0 * self.T)) > 0.2)
            np.testing.assert_array_equal(achados, [inicio, inicio + 1], str((f0, inicio)))

    def _medido_com_impulso_em(self, f0, amostra, amplitude=1.9):
        """Janela medida de mentira: senoide + o toque de 7,5 kHz da fonte."""
        medido = np.sin(2.0 * np.pi * f0 * self.T)
        k = np.arange(30)
        medido[amostra:amostra + 30] += amplitude * np.exp(-k / 8.0) * np.cos(2.0 * np.pi * 7500.0 * k / 30_000.0 - 0.6)
        return medido

    def test_validacao_confere_a_posicao_do_impulso(self):
        for f0 in (50.0, 60.0):
            experimento = self._experimento(f0)
            onda, parametros = experimento.gerar(self.T, f0, 0, np.random.default_rng(3))
            experimento.forma_para_bancada(onda, parametros, 0)
            previsto = int(experimento._indices_impulso(30_000.0, f0)[0])
            for atraso in (-3, 0, 1, 3, 10):
                resultado = experimento.conferir_posicao_do_evento(0, self._medido_com_impulso_em(f0, previsto + atraso))
                self.assertTrue(resultado["ok"], (f0, atraso, resultado))
            # o caso de 07/10 a 50 Hz (impulso 600 amostras = 20 ms depois) e outros fora da tolerância
            for atraso in (600, -600, 11, -14, 300):
                resultado = experimento.conferir_posicao_do_evento(0, self._medido_com_impulso_em(f0, previsto + atraso))
                self.assertFalse(resultado["ok"], (f0, atraso))
                self.assertIn("posição do impulso", resultado["motivos"][0])
            vazio = experimento.conferir_posicao_do_evento(0, np.sin(2.0 * np.pi * f0 * self.T))
            self.assertFalse(vazio["ok"])
            self.assertIn("impulso não encontrado", vazio["motivos"][0])

    def test_validacao_fisica_reprova_o_impulso_deslocado_que_a_exclusao_de_ciclos_escondia(self):
        f0 = 50.0
        experimento = self._experimento(f0)
        onda, parametros = experimento.gerar(self.T, f0, 0, np.random.default_rng(3))
        experimento.forma_para_bancada(onda, parametros, 0)
        previsto = int(experimento._indices_impulso(30_000.0, f0)[0])

        def registro(amostra):
            # 600 amostras de margem, trigger no índice 595 (como a bancada de 07/10)
            bruto = np.zeros(8100)
            bruto[595:595 + 6000] = self._medido_com_impulso_em(f0, amostra)
            return bruto

        certo = experimento._validar_fisicamente(0, self.T, 3, registro(previsto), margem_antes=600, inicio_janela=595)
        self.assertTrue(certo["ok"], certo)
        self.assertIn(certo["posicao_evento"]["desvio_amostras"], range(-3, 4))
        errado = experimento._validar_fisicamente(
            0, self.T, 3, registro(previsto + 600), margem_antes=600, inicio_janela=595,
        )
        self.assertFalse(errado["ok"])
        self.assertTrue(any("posição do impulso" in m for m in errado["motivos"]), errado["motivos"])

    def test_classes_sem_posicao_a_conferir_nao_mudam_a_validacao(self):
        self.assertIsNone(_load_experimento("07").conferir_posicao_do_evento(0, self.T))


class Classes05_07_18Tests(unittest.TestCase):
    """v1.15 — 05 pelo modelo do CSINe, 07/17 com entalhes contínuos e 18 em
    f0-3..f0+3 (`arquivo/analises:docs/analise-2026-10-12/pendente/classes_05_07_18_VERIFICAR.md`). Valem com o
    sorteio ligado; ``set sorteio off`` reproduz 34a0d82 (teste de bytes)."""

    T = np.arange(6000, dtype=np.float64) / 30_000.0

    def _gerar(self, classe_id, seed, f0=60.0, indice=0, sorteio=True):
        experimento = _load_experimento(classe_id)
        if not sorteio:
            _sem_sorteio(experimento)
        return experimento.gerar(self.T, f0, indice, np.random.default_rng(seed))

    # -- 05 --------------------------------------------------------------

    def test_05_modelo_dos_niveis_csine_tem_o_thd_e_o_rms_pedidos(self):
        import dataclasses
        for perfil in ("literatura", "norma"):
            experimento = _load_experimento("05")
            experimento.config = dataclasses.replace(experimento.config, perfil=perfil)
            for f0 in (60.0, 50.0):
                for indice, thd in enumerate(experimento.NIVEIS_THD):
                    if experimento.usar_trace(indice):
                        continue
                    for seed in range(5):
                        voltage, p = experimento.gerar(self.T, f0, indice, np.random.default_rng(seed))
                        self.assertEqual(p["thd"], thd)
                        self.assertAlmostEqual(sinais.thd_medida(voltage, fs_hz=30_000.0, f0=f0), thd, delta=0.003)
                        self.assertAlmostEqual(float(np.sqrt(np.mean(voltage ** 2))), 1.0 / math.sqrt(2.0), delta=0.003)
                        self.assertLessEqual(float(np.max(np.abs(voltage))), 1.0)

    def test_05_nivel_por_trace_continua_sendo_a_soma_de_harmonicas(self):
        experimento = _load_experimento("05")
        indice = list(experimento.NIVEIS_THD).index(0.30)
        self.assertTrue(experimento.usar_trace(indice))
        voltage, p = experimento.gerar(self.T, 60.0, indice, np.random.default_rng(3))
        tau = p["fase_graus"] / (360.0 * 60.0)
        np.testing.assert_allclose(
            voltage, sinais.onda_com_harmonicos(self.T + tau, 0.30, frequencia_hz=60.0), atol=1e-12,
        )

    def test_05_modelo_e_forma_programada_do_csine_sao_a_mesma_forma(self):
        experimento = _load_experimento("05")
        voltage, p = experimento.gerar(self.T, 60.0, 1, np.random.default_rng(8))
        programada, origem = experimento.forma_programada(voltage, p, 1, self.T)
        self.assertIn("CSINe", origem)
        np.testing.assert_allclose(programada, voltage, atol=1e-12)

    def test_05_sem_sorteio_todos_os_niveis_seguem_a_soma_de_harmonicas(self):
        for indice in range(5):
            voltage, p = self._gerar("05", 3, indice=indice, sorteio=False)
            esperada = sinais.onda_com_harmonicos(self.T, p["thd"], frequencia_hz=60.0)
            np.testing.assert_array_equal(voltage, esperada)

    # -- 07 / 17 ---------------------------------------------------------

    def _picos_sem_entalhe(self, voltage, f0, origem_s):
        """Picos (T/4 e 3T/4 dos ciclos que cabem INTEIROS na janela) sem
        nenhuma amostra zerada em até 0,7 ms."""
        ciclo = 1.0 / f0
        faltando, picos = [], 0
        k = int(math.ceil((0.0 - origem_s) / ciclo))
        while origem_s + (k + 1) * ciclo <= self.T[-1]:
            for fracao in (0.25, 0.75):
                centro = origem_s + k * ciclo + fracao * ciclo
                picos += 1
                if not np.any(voltage[np.abs(self.T - centro) <= 0.0007] == 0.0):
                    faltando.append(round(centro, 5))
            k += 1
        return picos, faltando

    def test_07_tem_entalhes_em_todos_os_ciclos_da_janela_nos_picos_da_senoide(self):
        for f0 in (60.0, 50.0):
            for seed in range(20):
                voltage, p = self._gerar("07", seed, f0)
                self.assertNotIn("inicio_disturbio_s", p)
                origem = -p["fase_graus"] / (360.0 * f0)
                picos, faltando = self._picos_sem_entalhe(voltage, f0, origem)
                self.assertGreaterEqual(picos, 2 * (int(0.2 * f0) - 1))
                self.assertEqual(faltando, [], (f0, seed))

    def test_07_sem_sorteio_so_ha_entalhes_na_janela_antiga(self):
        voltage, _ = self._gerar("07", 3, 60.0, sorteio=False)
        zeros = self.T[voltage != np.sin(2.0 * np.pi * 60.0 * self.T)]
        self.assertGreater(zeros.size, 0)
        self.assertGreaterEqual(zeros.min(), 0.060 - 1e-9)
        self.assertLess(zeros.max(), 0.060 + 0.080 + 1e-9)

    def test_aplicar_entalhes_continuos_descarta_pulso_com_centro_fora_da_janela(self):
        """A regra antiga zerava a amostra mais próxima quando o centro caía
        fora da grade; aqui o pulso é descartado e o rng é consumido igual."""
        sinal = np.ones_like(self.T)
        origem = -0.0123
        total = sinais.aplicar_entalhes_continuos(
            sinal, self.T, np.random.default_rng(1), frequencia_hz=60.0, origem_s=origem,
        )
        self.assertGreater(total, 20)
        # nenhum zero longe de um pico (T/4 ou 3T/4 da grade de origem, ±0,7 ms)
        ciclo = 1.0 / 60.0
        fase = ((self.T[sinal == 0.0] - origem) % (ciclo / 2.0)) - ciclo / 4.0
        self.assertLessEqual(float(np.max(np.abs(fase))), 0.0007)

    def test_17_tem_entalhes_continuos_e_a_oscilacao_localizada_em_t0(self):
        for f0 in (60.0, 50.0):
            for seed in range(10):
                voltage, p = self._gerar("17", seed, f0)
                t0, d = p["inicio_disturbio_s"], p["duracao_s"]
                origem = -p["fase_graus"] / (360.0 * f0)
                fora = (self.T < t0) | (self.T >= t0 + d)
                zerados = fora & (voltage == 0.0)
                self.assertGreater(int(np.sum(zerados)), 6, (f0, seed))
                # fora da oscilação, tudo o que não é entalhe é a senoide
                resto = fora & (voltage != 0.0)
                senoide = np.sin(2.0 * np.pi * f0 * (self.T - origem))
                np.testing.assert_allclose(voltage[resto], senoide[resto], atol=1e-12)
                # há entalhe antes e depois da oscilação (quando cabe um ciclo)
                if t0 > 2.0 / f0:
                    self.assertTrue(np.any(zerados & (self.T < t0)), (f0, seed))
                if t0 + d < 0.2 - 2.0 / f0:
                    self.assertTrue(np.any(zerados & (self.T >= t0 + d)), (f0, seed))

    def test_05_07_17_18_sem_sorteio_reproduzem_34a0d82(self):
        ref = json.loads(
            (PROJECT_ROOT / "tests" / "fixtures" / "gerar_literatura_34a0d82.json").read_text(encoding="utf-8")
        )
        verificados = 0
        for chave, esperado in ref["portavel"]["resumos"].items():
            cid, f0, seed, indice = chave.split("/")
            if cid in ("05", "07", "17", "18"):
                experimento = _sem_sorteio(_load_experimento(cid))
                self.assertEqual(
                    assinatura_portavel.diferencas(
                        assinatura_portavel.gerar_resumo(experimento, float(f0), int(seed), int(indice)), esperado,
                    ), [], chave,
                )
                verificados += 1
        self.assertEqual(verificados, 80)

    # -- 18 --------------------------------------------------------------

    def test_18_varre_f0_menos_3_ate_f0_mais_3_e_o_inverso(self):
        for f0 in (60.0, 50.0):
            _, par = self._gerar("18", 1, f0, 0)
            _, impar = self._gerar("18", 1, f0, 1)
            self.assertEqual((par["start_hz"], par["end_hz"]), (f0 - 3.0, f0 + 3.0))
            self.assertEqual((impar["start_hz"], impar["end_hz"]), (f0 + 3.0, f0 - 3.0))

    def test_18_a_50_hz_nao_vira_uma_senoide_de_60(self):
        voltage, _ = self._gerar("18", 5, 50.0, 0)
        subidas = int(np.sum((voltage[:-1] < 0.0) & (voltage[1:] >= 0.0)))
        # 0,2 s a 47 -> 53 Hz = 10 ciclos; a rampa antiga 57 -> 63 dava 12
        self.assertLessEqual(abs(subidas - 10), 1)

    def test_18_sem_sorteio_continua_em_57_63(self):
        _, p = self._gerar("18", 1, 50.0, 0, sorteio=False)
        self.assertEqual((p["start_hz"], p["end_hz"]), (57.0, 63.0))

    def test_18_configurar_envia_os_mesmos_extremos_que_gerar_registra(self):
        for sorteio in (True, False):
            for f0 in (60.0, 50.0):
                for indice in (0, 1):
                    fonte = mock.Mock()
                    tmp = Path(tempfile.mkdtemp())
                    try:
                        config = _config_bancada(tmp, sorteio_posicao=sorteio, grid_frequency_hz=f0)
                        experimento = _carregar_classe("18")(mestre.Bancada(fonte, mock.Mock(), config))
                        _, p = experimento.gerar(self.T, f0, indice, np.random.default_rng(1))
                        enviados = experimento.configurar(indice)
                    finally:
                        shutil.rmtree(tmp, ignore_errors=True)
                    args = fonte.frequency_drift_list.call_args
                    self.assertEqual(args.args, (p["start_hz"], p["end_hz"]), (sorteio, f0, indice))
                    self.assertEqual(enviados, {"start_hz": p["start_hz"], "end_hz": p["end_hz"]})

    def test_18_a_frequencia_base_e_restaurada_depois_de_47_53(self):
        fonte = AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=415.8, max_current_a=0.5)
        fonte.configure_safe_baseline(
            voltage_range_rms=300.0, voltage_high_vp=415.8, current_limit_a=0.5,
            protection_delay_s=0.1, frequency_hz=50.0,
        )
        fonte.frequency_drift_list(47.0, 53.0, voltage_rms=127.0, dwell_s=0.1)
        fonte.command_log.clear()
        fonte.restaurar_forma_e_modo_padrao()
        self.assertIn("SOURce:FREQuency 50", fonte.command_log)


class RuidoNaJanelaTests(unittest.TestCase):
    """AWGN de 20/30/40 dB só na janela rotulada (v1.15); SNR da bancada
    medido na margem; SNR efetivo combinado."""

    FS = 30_000.0

    def _registro(self, rng, *, sigma=0.01, margem_viva=False, offset=0.0):
        """8100 amostras: 600 de margem, 6000 de janela (senoide 60 Hz), 1500 de margem."""
        n = np.arange(8100)
        seno = 0.9 * np.sin(2.0 * np.pi * 60.0 * n / self.FS)
        x = seno.copy()
        if not margem_viva:
            x[:600] = 0.0
            x[6600:] = 0.0
        return x + offset + rng.normal(0.0, sigma, size=n.size)

    def test_padrao_e_20_30_40_db(self):
        if "SNR_LEVELS_DB" in mestre.os.environ:
            self.skipTest("SNR_LEVELS_DB definido no ambiente")
        self.assertEqual(mestre.SNR_LEVELS_DB, (20.0, 30.0, 40.0))

    def test_semente_mantem_a_formula_historica(self):
        for seed, snr in ((22260827, 30.0), (1, 20.0), (123456, 40.0)):
            self.assertEqual(sinais.semente_do_ruido(seed, snr), seed + int(round(snr * 1000.0)) + 50_000_000)

    def test_seed_reproduzivel_e_distinta_entre_seeds(self):
        registro = self._registro(np.random.default_rng(0))
        a = sinais.ruido_na_janela(registro, 600, 6000, (20.0, 30.0, 40.0), 777)
        b = sinais.ruido_na_janela(registro, 600, 6000, (20.0, 30.0, 40.0), 777)
        c = sinais.ruido_na_janela(registro, 600, 6000, (20.0, 30.0, 40.0), 778)
        for snr in (20.0, 30.0, 40.0):
            np.testing.assert_array_equal(a["janelas"][snr], b["janelas"][snr])
            self.assertFalse(np.array_equal(a["janelas"][snr], c["janelas"][snr]))
        self.assertEqual(a["metadata"], b["metadata"])

    def test_so_a_janela_recebe_ruido_e_snr_medido_na_janela_bate_com_o_nominal(self):
        desvios = []
        for seed in range(40):
            registro = self._registro(np.random.default_rng(seed))
            res = sinais.ruido_na_janela(registro, 600, 6000, (20.0, 30.0, 40.0), seed)
            for snr, janela in res["janelas"].items():
                self.assertEqual(janela.shape, (6000,))  # sem as margens
                limpa = registro[600:6600]
                medido = 10.0 * math.log10(np.mean(limpa**2) / np.mean((janela - limpa) ** 2))
                self.assertAlmostEqual(medido, res["metadata"]["snr_medido_db"][str(snr)], places=9)
                desvios.append(medido - snr)
            self.assertFalse(res["metadata"]["ruido_janela"]["margens_com_ruido"])
        # potência do ruído normalizada: SNR medido exato por construção (ruído da janela = P_ref/10^(snr/10))
        self.assertLess(max(abs(d) for d in desvios), 1e-6)
        self.assertLess(abs(float(np.mean(desvios))), 1e-6)

    def test_referencia_e_a_potencia_da_janela_nao_a_do_registro(self):
        # janela em 0,2 pu no meio de um registro de 1 pu: o ruido segue a janela
        registro = np.ones(1000)
        registro[300:700] = 0.2
        res = sinais.ruido_na_janela(registro, 300, 400, (30.0,), 5, simulado=True)
        ruido = res["janelas"][30.0] - 0.2
        self.assertAlmostEqual(float(np.mean(ruido**2)), 0.04 / 1000.0, delta=0.04 / 1000.0 * 0.2)

    def test_snr_da_bancada_em_margem_em_zero_e_em_margem_viva(self):
        # sigma 0,01 e janela de 0,9 pu de pico: P = 0,405 -> 10log(0,405/1e-4) = 36,07 dB
        esperado = 10.0 * math.log10(0.405 / 1e-4)
        for viva in (False, True):
            registro = self._registro(np.random.default_rng(3), margem_viva=viva)
            bancada = sinais.medir_ruido_da_bancada(registro, 600, 6000)
            self.assertEqual(bancada["margem"], "anterior")
            self.assertAlmostEqual(bancada["snr_db"], esperado, delta=0.5)

    def test_offset_dc_nao_conta_como_ruido_da_bancada(self):
        sem = sinais.medir_ruido_da_bancada(self._registro(np.random.default_rng(4)), 600, 6000)
        com = sinais.medir_ruido_da_bancada(self._registro(np.random.default_rng(4), offset=0.02), 600, 6000)
        self.assertAlmostEqual(sem["snr_db"], com["snr_db"], delta=0.05)

    def test_usa_margem_posterior_quando_a_anterior_e_curta(self):
        registro = self._registro(np.random.default_rng(5))
        bancada = sinais.medir_ruido_da_bancada(registro, 50, 6000)
        self.assertEqual(bancada["margem"], "posterior")
        self.assertIsNone(sinais.medir_ruido_da_bancada(registro[:6050], 50, 6000))

    def test_snr_efetivo_soma_as_potencias_de_bancada_e_acrescentada(self):
        registro = self._registro(np.random.default_rng(6))
        res = sinais.ruido_na_janela(registro, 600, 6000, (30.0, 40.0), 9)
        meta = res["metadata"]
        bancada_db = meta["snr_bancada_db"]
        for snr in ("30.0", "40.0"):
            soma = 10.0 ** (-bancada_db / 10.0) + 10.0 ** (-meta["snr_medido_db"][snr] / 10.0)
            self.assertAlmostEqual(meta["snr_efetivo_db"][snr], -10.0 * math.log10(soma), delta=0.01)
            self.assertLess(meta["snr_efetivo_db"][snr], min(bancada_db, meta["snr_medido_db"][snr]))

    def test_simulado_nao_tem_snr_de_bancada_e_efetivo_igual_ao_acrescentado(self):
        sinal = 0.9 * np.sin(2.0 * np.pi * 60.0 * np.arange(6000) / self.FS)
        meta = sinais.ruido_na_janela(sinal, 0, 6000, (20.0,), 3, simulado=True)["metadata"]
        self.assertIsNone(meta["snr_bancada_db"])
        self.assertEqual(meta["snr_efetivo_db"], meta["snr_medido_db"])

    def test_sessao_simulada_grava_os_tres_niveis(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = mestre.Config(
                fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
                base_voltage_rms=127.0, snr_levels_db=(20.0, 30.0, 40.0), base_seed=1,
                capture_current=False, current_base_a=None, results_dir=tmp_dir / "resultados",
                sim_captures_per_class=4, real_captures_per_class=1, disturbance_start_s=0.06,
            )
            bancada = mestre.Bancada(mestre.AmetekMX30(simulated=True), None, config)

            class _Classe(mestre.ExperimentoWaveform):
                id = "02"
                nome = "SAG"

                def gerar(self, t, f0, capture_index, rng):
                    return 0.5 * np.sin(2.0 * np.pi * f0 * t), {"sag_pu": 0.5}

            _Classe(bancada).executar()
            pasta = config.results_dir
            limpa = np.load(pasta / "02_sag.npz", allow_pickle=True)["literatura/medida"]
            for snr in (20, 30, 40):
                ruidosa = np.load(pasta / f"snr_{snr}db" / "02_sag.npz", allow_pickle=True)["literatura/tensao_pu"]
                self.assertEqual(ruidosa.shape, limpa.shape)
                for k in range(limpa.shape[0]):
                    medido = 10.0 * math.log10(np.mean(limpa[k] ** 2) / np.mean((ruidosa[k] - limpa[k]) ** 2))
                    self.assertAlmostEqual(medido, snr, delta=1e-6)
            linha = json.loads((pasta / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(sorted(linha["snr_medido_db"]), ["20.0", "30.0", "40.0"])
            self.assertIsNone(linha["snr_bancada_db"])
            self.assertEqual(linha["snr_efetivo_db"], linha["snr_medido_db"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_captura_fisica_grava_ruido_so_na_janela_com_snr_de_bancada(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = mestre.Config(
                fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
                base_voltage_rms=127.0, snr_levels_db=(20.0, 40.0), base_seed=1,
                capture_current=False, current_base_a=None, results_dir=tmp_dir / "resultados",
                sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
                capturas_override=2,
            )
            bancada = mestre.Bancada(
                mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0), mock.Mock(), config,
            )

            class _Classe(mestre.ExperimentoNativo):
                id = "96"
                nome = "TESTE_RUIDO"

                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {}

                def configurar(self, capture_index):
                    return {}

            experimento = _Classe(bancada)
            experimento.osc = mock.Mock()
            experimento._calcular_margem = lambda **kw: (600, 1500, 8100)
            n = np.arange(8100, dtype=np.float64)
            tempo_s = n / 30_000.0
            registro = np.zeros(8100)
            registro[600:6600] = np.sin(2.0 * np.pi * 60.0 * tempo_s[:6000])
            registro += np.random.default_rng(11).normal(0.0, 0.01, size=8100)
            experimento._capturar_real = lambda capture_index, t, rng: (tempo_s, registro.copy(), None, {})
            experimento._preparar_acquisicao_real = lambda: None
            experimento.executar()

            pasta = config.results_dir
            self.assertEqual(sorted(p.name for p in pasta.glob("96_*.npz")), ["96_teste_ruido.npz"])
            medidas = np.load(pasta / "96_teste_ruido.npz", allow_pickle=True)["literatura/medida"]
            self.assertEqual(medidas.shape, (2, 8100))  # o limpo mantém as margens
            for k in range(2):
                limpa = medidas[k]
                for snr in (20, 40):
                    dados = np.load(pasta / f"snr_{snr}db" / "96_teste_ruido.npz", allow_pickle=True)
                    self.assertEqual(dados["literatura/tensao_pu"].shape, (2, 6000))
                    self.assertEqual(dados["tempo_ms"].shape, (6000,))
                    janela = limpa[600:6600]
                    medido = 10.0 * math.log10(np.mean(janela**2) / np.mean((dados["literatura/tensao_pu"][k] - janela) ** 2))
                    self.assertAlmostEqual(medido, snr, delta=1e-6)
            linhas = [json.loads(l) for l in (pasta / "metadata" / "96_teste_ruido.jsonl").read_text(encoding="utf-8").splitlines()]
            for linha in linhas:
                self.assertEqual(linha["ruido_janela"]["inicio_janela"], 600)
                self.assertEqual(linha["ruido_janela"]["bancada"]["margem"], "anterior")
                esperado = 10.0 * math.log10(0.5 / 1e-4)  # P=0,5 pu^2, sigma 0,01
                self.assertAlmostEqual(linha["snr_bancada_db"], esperado, delta=0.5)
                self.assertLess(linha["snr_efetivo_db"]["40.0"], linha["snr_bancada_db"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_script_offline_reproduz_a_conta_da_bancada(self):
        import importlib
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        try:
            gerar = importlib.import_module("gerar_ruido_janela")
        finally:
            sys.path.pop(0)
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            sessao = tmp_dir / "sessao"
            (sessao / "metadata").mkdir(parents=True)
            registro = self._registro(np.random.default_rng(21))
            np.savez(sessao / "96_teste_cap01.npz", classe="TESTE", id_captura=np.array(["96-0001"], dtype=object),
                     tempo_ms=np.arange(8100) / 30.0, tensao_pu=registro[np.newaxis, :])
            meta = {"id_captura": "96-0001", "classe": "TESTE", "seed": 4242, "simulado": False, "fs_hz": 30000.0,
                    "pontos": 6000, "pre_trigger_s": 0.0, "indice_trigger": 600, "margem_amostras_antes": 600,
                    "margem_amostras_depois": 1500, "amostras_totais": 8100}
            (sessao / "metadata" / "96_teste.jsonl").write_text(json.dumps(meta) + "\n", encoding="utf-8")
            gerar.gerar_sessao(sessao, sessao / "ruido_janela")
            esperado = sinais.ruido_na_janela(registro, 600, 6000, (20.0, 30.0, 40.0), 4242)
            for snr in (20, 30, 40):
                saida = np.load(sessao / "ruido_janela" / f"snr_{snr}db" / "96_teste_cap01.npz", allow_pickle=True)
                np.testing.assert_array_equal(saida["tensao_pu"][0], esperado["janelas"][float(snr)])
            linha = json.loads((sessao / "ruido_janela" / "metadata" / "96_teste.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(linha["snr_efetivo_db"], esperado["metadata"]["snr_efetivo_db"])
            with self.assertRaises(FileExistsError):
                gerar.gerar_sessao(sessao, sessao / "ruido_janela")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class CliRecalibracaoEHtmlTests(unittest.TestCase):
    """``set recalibracao`` / ``set html`` e os ganchos de fim de run da CLI."""

    FS = RecorteMargemERelatorioHtmlTests.FS
    F0 = RecorteMargemERelatorioHtmlTests.F0
    _captura = RecorteMargemERelatorioHtmlTests._captura

    def setUp(self):
        import cli
        self.cli = cli
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.sessao = self.tmp / "sessao_teste"
        (self.sessao / "metadata").mkdir(parents=True)
        (self.sessao / "snr_30db").mkdir()
        self.nominais = {}
        self._captura("01", "NORMAL", {}, pre_s=0.0, indice_trigger=595, sag=None)
        self._captura("02", "SAG", {"sag_pu": 0.5}, pre_s=0.060, indice_trigger=2405, sag=(0.060, 0.120))
        # Calibração de teste, no lugar da real: 127 V/60 Hz com 06 alto (o
        # medido é menor) e sem a 09; 05 baixo (o medido é maior).
        self.calibracao = self.tmp / "calibracao_extremos.json"
        self.calibracao.write_text(json.dumps({"por_condicao": {"127V_60Hz": {
            "tensao_rms": 127.0, "frequencia_hz": 60.0, "origem": "teste",
            "fatores": {"01": 1.05, "05": 1.0, "06": 1.5},
        }}}), encoding="utf-8")
        patch = mock.patch.object(mestre, "CALIBRACAO_EXTREMOS_PATH", self.calibracao)
        patch.start()
        self.addCleanup(patch.stop)
        self.sessao_cli = cli.SessaoCLI()

    def _rodar(self, metodo, *args):
        import io
        from contextlib import redirect_stdout
        saida = io.StringIO()
        with redirect_stdout(saida):
            codigo = metodo(*args)
        return codigo, saida.getvalue()

    def _metadata_de_bancada(self, classe_id, extremo, *, tensao=127.0, frequencia=60.0, pico=180.0):
        registro = {"id_captura": f"{classe_id}-0001", "tensao_base_rms": tensao, "f0_hz": frequencia,
                    "pico_programado_v": pico, "pico_medido_v": extremo, "vale_medido_v": -extremo,
                    "parametros": {}}
        with (self.sessao / "metadata" / f"{classe_id}_x.jsonl").open("a", encoding="utf-8") as arq:
            arq.write(json.dumps(registro) + "\n")

    def _preparar_copia(self):
        shutil.copyfile(self.calibracao, self.sessao / mestre.NOME_CALIBRACAO_NA_SESSAO)

    def _fatores(self):
        return json.loads(self.calibracao.read_text(encoding="utf-8"))["por_condicao"]

    # -- set / status / help ---------------------------------------------

    def test_padrao_off_e_set_liga_e_desliga(self):
        self.assertFalse(self.sessao_cli.recalibracao_ao_fim)
        self.assertFalse(self.sessao_cli.html_ao_fim)
        codigo, saida = self._rodar(self.sessao_cli.cmd_set, ["recalibracao", "on"])
        self.assertEqual(codigo, 0)
        self.assertTrue(self.sessao_cli.recalibracao_ao_fim)
        self.assertIn("AVISO", saida)  # o operador é avisado de que o JSON será alterado
        self._rodar(self.sessao_cli.cmd_set, ["html", "on"])
        self.assertTrue(self.sessao_cli.html_ao_fim)
        _, status = self._rodar(self.sessao_cli.cmd_status, [])
        self.assertIn("recalibração automática ao fim do run: ON", status)
        self.assertIn("relatório HTML ao fim do run: ON", status)
        self._rodar(self.sessao_cli.cmd_set, ["recalibracao", "off"])
        self._rodar(self.sessao_cli.cmd_set, ["html", "off"])
        _, status = self._rodar(self.sessao_cli.cmd_status, [])
        self.assertIn("recalibração automática ao fim do run: OFF", status)
        self.assertIn("relatório HTML ao fim do run: OFF", status)

    def test_set_recusa_valor_invalido_e_help_documenta(self):
        for chave in ("recalibracao", "html"):
            codigo, _ = self._rodar(self.sessao_cli.cmd_set, [chave, "talvez"])
            self.assertEqual(codigo, 1, chave)
        self.assertFalse(self.sessao_cli.recalibracao_ao_fim or self.sessao_cli.html_ao_fim)
        self.assertIn("set recalibracao on|off", self.cli.HELP_TEXT)
        self.assertIn("set html on|off", self.cli.HELP_TEXT)

    # -- recalibração ------------------------------------------------------

    def test_recalibracao_so_sobe_fator_e_guarda_a_copia_anterior(self):
        self._metadata_de_bancada("05", 216.0)  # 216/180 = 1,2 > 1,0
        self._metadata_de_bancada("06", 198.0)  # 1,1 < 1,5: não pode baixar
        self._preparar_copia()
        antes = self.calibracao.read_text(encoding="utf-8")
        with mock.patch.object(mestre, "BENCH_MODE", True):
            _, saida = self._rodar(self.sessao_cli._recalibrar_ao_fim, self.sessao)
        fatores = self._fatores()["127V_60Hz"]["fatores"]
        self.assertEqual(fatores["05"], 1.2)
        self.assertEqual(fatores["06"], 1.5)
        self.assertEqual(fatores["01"], 1.05)
        self.assertIn("RECALIBRAÇÃO AUTOMÁTICA: 1 fator(es)", saida)
        self.assertIn("[127V_60Hz] classe 05: 1.000 -> 1.200", saida)
        self.assertNotIn("classe 06", saida)
        # A cópia do início do run segue igual ao arquivo de antes.
        self.assertEqual((self.sessao / mestre.NOME_CALIBRACAO_NA_SESSAO).read_text(encoding="utf-8"), antes)
        self.assertIn("automático, CLI", self._fatores()["127V_60Hz"]["origem"])

    def test_recalibracao_sem_mudanca_nao_reescreve_o_arquivo(self):
        self._metadata_de_bancada("06", 198.0)
        self._preparar_copia()
        antes = self.calibracao.read_bytes()
        with mock.patch.object(mestre, "BENCH_MODE", True):
            _, saida = self._rodar(self.sessao_cli._recalibrar_ao_fim, self.sessao)
        self.assertEqual(self.calibracao.read_bytes(), antes)
        self.assertIn("nenhum fator mudou", saida)

    def test_recalibracao_automatica_nao_cria_tabela_nem_baixa_o_efetivo(self):
        self._metadata_de_bancada("05", 216.0, tensao=230.0, frequencia=50.0, pico=325.0)  # condição sem tabela
        self._metadata_de_bancada("09", 200.0)  # classe sem entrada: efetivo = maior da tabela (1,5)
        self._preparar_copia()
        antes = self.calibracao.read_bytes()
        with mock.patch.object(mestre, "BENCH_MODE", True):
            _, saida = self._rodar(self.sessao_cli._recalibrar_ao_fim, self.sessao)
        self.assertEqual(self.calibracao.read_bytes(), antes)
        self.assertIn("condição 230V_50Hz sem tabela própria", saida)
        self.assertIn("classe 09: medido 1.111 abaixo do fator efetivo 1.500", saida)

    def test_recalibracao_automatica_recusa_substituir(self):
        recalibrar = _carregar_script("recalibrar_extremos")
        with self.assertRaises(ValueError):
            recalibrar.recalibrar([self.sessao], gravar=True, substituir=True, automatico=True)

    def test_recalibracao_em_modo_simulado_nao_faz_nada(self):
        self._metadata_de_bancada("05", 216.0)
        self._preparar_copia()
        antes = self.calibracao.read_bytes()
        with mock.patch.object(mestre, "BENCH_MODE", False):
            _, saida = self._rodar(self.sessao_cli._recalibrar_ao_fim, self.sessao)
        self.assertEqual(self.calibracao.read_bytes(), antes)
        self.assertIn("SIMULADO", saida)

    def test_recalibracao_sem_a_copia_da_calibracao_nao_grava(self):
        self._metadata_de_bancada("05", 216.0)
        antes = self.calibracao.read_bytes()
        with mock.patch.object(mestre, "BENCH_MODE", True):
            _, saida = self._rodar(self.sessao_cli._recalibrar_ao_fim, self.sessao)
        self.assertEqual(self.calibracao.read_bytes(), antes)
        self.assertIn("falta a cópia", saida)

    def test_recalibrar_extremos_main_continua_igual(self):
        """A linha de comando segue imprimindo e gravando como antes."""
        recalibrar = _carregar_script("recalibrar_extremos")
        # main() baixa o nível do logger do mestre (efeito global na CLI do script).
        logger_mestre = logging.getLogger("MestreExperimentos")
        self.addCleanup(logger_mestre.setLevel, logger_mestre.level)
        self._metadata_de_bancada("05", 216.0)
        self._metadata_de_bancada("06", 198.0)
        codigo, saida = self._rodar(recalibrar.main, [str(self.sessao), "--arquivo", str(self.calibracao)])
        self.assertEqual(codigo, 0)
        self.assertIn("Nada gravado (use --gravar).", saida)
        self.assertEqual(self._fatores()["127V_60Hz"]["fatores"]["05"], 1.0)
        self._rodar(recalibrar.main, [str(self.sessao), "--arquivo", str(self.calibracao), "--gravar"])
        self.assertEqual(self._fatores()["127V_60Hz"]["fatores"]["05"], 1.2)
        self.assertEqual(self._fatores()["127V_60Hz"]["fatores"]["06"], 1.5)

    # -- HTML --------------------------------------------------------------

    def test_html_ao_fim_gera_a_versao_recortada_sem_tocar_nos_originais(self):
        antes = {p.name: p.read_bytes() for p in self.sessao.glob("*.npz")}
        _, saida = self._rodar(self.sessao_cli._gerar_html_ao_fim, self.sessao)
        html = self.sessao / "relatorio_sessao_teste.html"
        self.assertTrue(html.is_file())
        self.assertIn(str(html), saida)
        texto = html.read_text(encoding="utf-8")
        self.assertIn("02_sag · literatura · 02-0001", texto)
        self.assertIn("sessao_teste (sem_margem)", texto)
        self.assertTrue((self.sessao / "sem_margem" / "02_sag.npz").is_file())
        self.assertEqual({p.name: p.read_bytes() for p in self.sessao.glob("*.npz")}, antes)

    # -- falha não derruba a sessão ---------------------------------------

    def test_falha_da_recalibracao_e_do_html_so_avisa(self):
        self.sessao_cli.recalibracao_ao_fim = True
        self.sessao_cli.html_ao_fim = True
        with mock.patch.object(mestre, "BENCH_MODE", True):
            # Sem metadata/*.jsonl com extremos: coletar() usa SystemExit.
            vazia = self.tmp / "vazia"
            vazia.mkdir()
            self._preparar_copia_em(vazia)
            _, saida = self._rodar(self.sessao_cli._fim_da_sessao, vazia)
        self.assertIn("recalibração automática FALHOU", saida)
        self.assertIn("relatório HTML FALHOU", saida)
        with mock.patch.object(self.sessao_cli, "_recalibrar_ao_fim", side_effect=RuntimeError("x")), \
                mock.patch.object(self.sessao_cli, "_gerar_html_ao_fim", side_effect=RuntimeError("y")):
            _, saida = self._rodar(self.sessao_cli._fim_da_sessao, self.sessao)
        self.assertIn("RuntimeError: x", saida)
        self.assertIn("RuntimeError: y", saida)

    def _preparar_copia_em(self, pasta):
        shutil.copyfile(self.calibracao, pasta / mestre.NOME_CALIBRACAO_NA_SESSAO)

    # -- ganchos em run / run all -----------------------------------------

    def _bancada_falsa(self, resultados=None, erro=None):
        bancada = mock.MagicMock()
        bancada.__enter__.return_value = bancada
        if erro is not None:
            bancada.executar_bateria.side_effect = erro
        else:
            bancada.executar_bateria.return_value = resultados
        return bancada

    def test_run_all_dispara_os_ganchos_so_quando_ligados_e_sem_abortar(self):
        resultados = [mestre.ResultadoClasse("01", "NORMAL", ok=True),
                      mestre.ResultadoClasse("02", "SAG", ok=False, motivo="RMS fora")]
        for ligado in (False, True):
            self.sessao_cli.recalibracao_ao_fim = ligado
            self.sessao_cli.html_ao_fim = ligado
            with mock.patch.object(self.sessao_cli, "confirmar", return_value=True), \
                    mock.patch.object(self.sessao_cli, "_garantir_pasta_sessao"), \
                    mock.patch.object(self.sessao_cli, "autorizar_saida"), \
                    mock.patch.object(mestre, "SESSION_RESULTS_DIR", self.sessao), \
                mock.patch.object(mestre, "scripts_da_bateria_fisica",
                                  return_value=[p for p in mestre._experiment_scripts() if p.stem in ("01", "02")]), \
                    mock.patch.object(mestre.Bancada, "from_env", return_value=self._bancada_falsa(resultados)), \
                    mock.patch.object(self.sessao_cli, "_recalibrar_ao_fim") as recal, \
                    mock.patch.object(self.sessao_cli, "_gerar_html_ao_fim") as html:
                codigo, _ = self._rodar(self.sessao_cli._run_all)
            self.assertEqual(codigo, 1)  # a falha de experimento continua contando
            self.assertEqual(recal.called, ligado)
            self.assertEqual(html.called, ligado)

    def test_run_all_abortado_por_infraestrutura_nao_dispara_os_ganchos(self):
        self.sessao_cli.recalibracao_ao_fim = True
        self.sessao_cli.html_ao_fim = True
        with mock.patch.object(self.sessao_cli, "confirmar", return_value=True), \
                mock.patch.object(self.sessao_cli, "_garantir_pasta_sessao"), \
                mock.patch.object(self.sessao_cli, "autorizar_saida"), \
                mock.patch.object(mestre, "SESSION_RESULTS_DIR", self.sessao), \
                mock.patch.object(mestre, "scripts_da_bateria_fisica",
                                  return_value=[p for p in mestre._experiment_scripts() if p.stem in ("01", "02")]), \
                mock.patch.object(mestre.Bancada, "from_env",
                                  return_value=self._bancada_falsa(erro=mestre.CommunicationError("serial caiu"))), \
                mock.patch.object(self.sessao_cli, "_recalibrar_ao_fim") as recal, \
                mock.patch.object(self.sessao_cli, "_gerar_html_ao_fim") as html:
            codigo, saida = self._rodar(self.sessao_cli._run_all)
        self.assertEqual(codigo, 1)
        self.assertIn("BATERIA ABORTADA", saida)
        recal.assert_not_called()
        html.assert_not_called()

    def test_falha_do_gancho_nao_muda_o_resultado_do_run_all(self):
        self.sessao_cli.recalibracao_ao_fim = True
        self.sessao_cli.html_ao_fim = True
        resultados = [mestre.ResultadoClasse("01", "NORMAL", ok=True)]
        with mock.patch.object(self.sessao_cli, "confirmar", return_value=True), \
                mock.patch.object(self.sessao_cli, "_garantir_pasta_sessao"), \
                mock.patch.object(self.sessao_cli, "autorizar_saida"), \
                mock.patch.object(mestre, "SESSION_RESULTS_DIR", self.sessao), \
                mock.patch.object(mestre, "scripts_da_bateria_fisica",
                                  return_value=[p for p in mestre._experiment_scripts() if p.stem in ("01", "02")]), \
                mock.patch.object(mestre.Bancada, "from_env", return_value=self._bancada_falsa(resultados)), \
                mock.patch.object(self.sessao_cli, "_recalibrar_ao_fim", side_effect=RuntimeError("boom")), \
                mock.patch.object(self.sessao_cli, "_gerar_html_ao_fim", side_effect=RuntimeError("boom")):
            codigo, saida = self._rodar(self.sessao_cli._run_all)
        self.assertEqual(codigo, 0)
        self.assertIn("1/1 classes OK", saida)
        self.assertIn("AVISO", saida)


class PreflightUnicoTests(unittest.TestCase):
    """Preflight único (spec 12): preflight.py removido, lowvoltage pede
    ENERGIZAR-TESTE na tensão base e a CLI grava logs/preflight_new-*.log."""

    def setUp(self):
        import cli
        self.cli = cli
        self.sessao = cli.SessaoCLI()

    def _rodar(self, metodo, args=()):
        import io
        from contextlib import redirect_stdout
        saida = io.StringIO()
        with redirect_stdout(saida):
            codigo = metodo(list(args))
        return codigo, saida.getvalue()

    def test_preflight_py_nao_existe_e_cli_so_usa_preflight_new(self):
        self.assertFalse((LOGICA_DIR / "preflight.py").exists())
        self.assertFalse(hasattr(self.cli, "preflight"))
        self.assertTrue(callable(preflight_new.run_basic_stage))
        self.assertEqual(preflight_new.normal_waveform().shape, (mestre.POINTS,))

    def test_lowvoltage_pede_energizar_teste_com_tensao_base(self):
        pedidos = []

        def recusar(aviso, esperado):
            pedidos.append((aviso, esperado))
            return False

        with mock.patch.object(self.sessao, "confirmar", side_effect=recusar), \
                mock.patch.object(preflight_new, "run_basic_stage") as basico:
            codigo, _ = self._rodar(self.sessao.cmd_lowvoltage)
        self.assertEqual(codigo, 1)
        basico.assert_not_called()
        self.assertEqual(pedidos[0][1], "ENERGIZAR-TESTE")
        self.assertIn(f"{mestre.BASE_VOLTAGE_RMS:g} Vrms", pedidos[0][0])
        self.assertNotIn("5 Vrms" if mestre.BASE_VOLTAGE_RMS != 5 else "\0", pedidos[0][0])

    def test_confirmacao_e_case_sensitive(self):
        for digitado in ("energizar-teste", "ENERGIZAR-5V", "ENERGIZAR-TESTE "):
            with mock.patch("builtins.input", return_value=digitado), \
                    mock.patch.object(preflight_new, "run_basic_stage") as basico, \
                    mock.patch.object(preflight_new, "_configure_logging") as log:
                codigo, _ = self._rodar(self.sessao.cmd_lowvoltage)
            self.assertEqual(codigo, 1, digitado)
            basico.assert_not_called()
            log.assert_not_called()

    def test_lowvoltage_confirmado_energiza_e_revoga(self):
        estados = []

        def basico(trigger_test, low_voltage):
            estados.append((trigger_test, low_voltage, mestre.OUTPUT_ARMED, preflight_new.OUTPUT_ARMED))
            return 0

        with mock.patch("builtins.input", return_value="ENERGIZAR-TESTE"), \
                mock.patch.object(preflight_new, "_configure_logging", return_value=Path("x.log")), \
                mock.patch.object(preflight_new, "run_basic_stage", side_effect=basico):
            codigo, _ = self._rodar(self.sessao.cmd_lowvoltage)
        self.assertEqual(codigo, 0)
        self.assertEqual(estados, [(False, True, True, True)])
        self.assertFalse(mestre.OUTPUT_ARMED)
        self.assertFalse(preflight_new.OUTPUT_ARMED)

    def test_help_e_codigo_sem_energizar_5v(self):
        self.assertIn("ENERGIZAR-TESTE", self.cli.HELP_TEXT)
        self.assertNotIn("ENERGIZAR-5V", self.cli.HELP_TEXT)
        self.assertNotIn("5 Vrms", self.cli.HELP_TEXT)

    def test_cli_grava_log_em_arquivo_para_native_e_lowvoltage(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            chamadas = []

            def native():
                preflight_new.logger.info("linha de teste native")
                chamadas.append("native")
                return 0

            def basico(trigger_test, low_voltage):
                preflight_new.logger.info("linha de teste lowvoltage")
                return 0

            try:
                with mock.patch.object(preflight_new, "LOG_DIR", logs), \
                        mock.patch("builtins.input", return_value="ENERGIZAR-COMANDOS"), \
                        mock.patch.object(preflight_new, "run_native_commands", side_effect=native):
                    self.assertEqual(self._rodar(self.sessao.cmd_native)[0], 0)
                with mock.patch.object(preflight_new, "LOG_DIR", logs), \
                        mock.patch("builtins.input", return_value="ENERGIZAR-TESTE"), \
                        mock.patch.object(preflight_new, "run_basic_stage", side_effect=basico):
                    self.assertEqual(self._rodar(self.sessao.cmd_lowvoltage)[0], 0)
            finally:
                for handler in list(preflight_new.logger.handlers):
                    handler.close()
                preflight_new.logger.handlers.clear()
            arquivos = sorted(p.name for p in logs.glob("preflight_new-*.log"))
            self.assertEqual(len(arquivos), 2, arquivos)
            native_log = next(logs.glob("preflight_new-native-commands-*.log")).read_text(encoding="utf-8")
            baixa_log = next(logs.glob("preflight_new-low-voltage-*.log")).read_text(encoding="utf-8")
            self.assertIn("linha de teste native", native_log)
            self.assertIn("linha de teste lowvoltage", baixa_log)



class RmsCaEPicoPrevistoTests(unittest.TestCase):
    """Spec 11 (v1.15): LIST:VOLTage com o rms da componente CA do ciclo e
    previsão de pico igual ao pico que a fonte emite (docs/tres_versoes.md)."""

    T = np.arange(6000, dtype=np.float64) / 30_000.0
    MARGEM = 1e-9

    @staticmethod
    def _degrau(f0, nivel, meio=0.5):
        """Senoide de amplitude 1 com degrau de amplitude (nivel) na segunda
        parte de cada ciclo: média do ciclo != 0 e degrau a meio ciclo."""
        t = RmsCaEPicoPrevistoTests.T
        fase = (t * f0) % 1.0
        return np.sin(2.0 * np.pi * f0 * t) * np.where(fase < meio, 1.0, nivel) + np.where(fase < meio, 0.0, 0.3)

    def test_list_voltage_e_o_rms_da_componente_ca_do_ciclo(self):
        for f0 in (50.0, 60.0):
            forma = self._degrau(f0, 0.4)
            programacao = AmetekMX30.montar_programacao(forma, base_voltage_rms=127.0, frequency_hz=f0)
            n = programacao.pontos_por_ciclo
            for i, rms_v in enumerate(programacao.list_voltages_rms):
                ciclo = forma[i * n:(i + 1) * n]
                esperado = 127.0 * np.sqrt(2.0) * float(np.std(ciclo))
                self.assertAlmostEqual(float(rms_v), esperado, delta=1e-6 * esperado)
                com_media = 127.0 * np.sqrt(2.0) * float(np.sqrt(np.mean(ciclo ** 2)))
                self.assertLess(float(rms_v), com_media)

    def test_pico_previsto_nao_subestima_o_pico_de_programada_em_degraus(self):
        import dataclasses
        casos = [(f"degrau f0={f0:g} nivel={nivel}", self._degrau(f0, nivel), f0)
                 for f0 in (50.0, 60.0) for nivel in (0.2, 0.4, 0.8)]
        for classe_id in ("10", "11", "12", "16"):
            for f0 in (50.0, 60.0):
                for sorteio in (False, True):
                    experimento = _load_experimento(classe_id)
                    experimento.config = dataclasses.replace(experimento.config, sorteio_posicao=sorteio)
                    forma, _ = experimento.gerar(self.T, f0, 0, np.random.default_rng(31 + int(sorteio)))
                    casos.append((f"{classe_id} f0={f0:g} sorteio={sorteio}", np.asarray(forma), f0))
        for nome, forma, f0 in casos:
            for base in (127.0, 230.0):
                with self.subTest(nome, base=base):
                    programacao = AmetekMX30.montar_programacao(forma, base_voltage_rms=base, frequency_hz=f0)
                    pico_programada_v = float(np.max(np.abs(programacao.programada_pu()))) * base * np.sqrt(2.0)
                    self.assertGreaterEqual(programacao.pico_reconstruido_v + self.MARGEM, pico_programada_v)
                    self.assertGreaterEqual(programacao.pico_acumulado_v[-1] + self.MARGEM, pico_programada_v)
                    # e a previsão não é folgada à toa: fica a menos de 1% do pico emitido
                    self.assertLess(programacao.pico_reconstruido_v, pico_programada_v * 1.01)

    def test_programada_de_degrau_aproxima_o_modelo_sem_a_media_do_ciclo(self):
        forma = self._degrau(60.0, 0.4)
        programacao = AmetekMX30.montar_programacao(forma, base_voltage_rms=127.0, frequency_hz=60.0)
        n = programacao.pontos_por_ciclo
        alvo = np.concatenate([forma[i * n:(i + 1) * n] - forma[i * n:(i + 1) * n].mean() for i in range(programacao.ciclos)])
        # a fonte remove o DC de cada TRACE: o que resta é o modelo sem a média do ciclo
        self.assertLess(float(np.max(np.abs(programacao.programada_pu() - alvo))), 0.05)


class RastreabilidadeRuidoEArvoreTests(unittest.TestCase):
    """v1.15 (spec 14): semente de cada nível do ruído gravada em
    ``ruido_janela``; procedência do código recalculada a cada pasta de sessão
    e com arquivos não rastreados em ``PASTAS_DO_CODIGO``; perfis dos runs da
    CLI em ``sessao.json``."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._cache = mock.patch.object(mestre, "_INFO_CODIGO_CACHE", None)
        self._cache.start()
        self.addCleanup(self._cache.stop)

    def _repo_git(self):
        """Repositório git temporário que imita a estrutura do projeto."""
        repo = self.tmp / "repo"
        for pasta in ("logica", "docs", "scripts", "experimentos_nativos", "experimentos_waveform"):
            (repo / pasta).mkdir(parents=True)
        (repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (repo / "logica" / "base.py").write_text("X = 1\n", encoding="utf-8")
        self._git(repo, "init", "-q")
        self._git(repo, "add", "logica/base.py", ".gitignore")
        self._git(repo, "commit", "-q", "-m", "base")
        return repo

    @staticmethod
    def _git(repo, *args):
        import subprocess
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
            cwd=str(repo), check=True, capture_output=True,
        )

    def _config_simulada(self, results_dir):
        return mestre.Config(
            fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(20.0, 30.0, 40.0), base_seed=1234,
            capture_current=False, current_base_a=None, results_dir=results_dir,
            sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
            capturas_override=1,
        )

    # -- semente do ruído --------------------------------------------------

    def test_semente_gravada_reproduz_o_vetor_de_ruido(self):
        registro = np.sin(2.0 * np.pi * 60.0 * np.arange(8000) / 30_000.0)
        seed = 777
        resultado = sinais.ruido_na_janela(registro, 600, 6000, (20.0, 30.0, 40.0), seed, simulado=True)
        rj = resultado["metadata"]["ruido_janela"]
        self.assertEqual(rj["formula_semente"], "seed + round(snr_db*1000) + 50000000")
        self.assertEqual(set(rj["sementes_por_snr_db"]), {"20.0", "30.0", "40.0"})
        json.dumps(rj)  # serializável como o metadata exige
        limpa = registro[600:6600]
        potencia = float(np.mean(np.square(limpa)))
        for snr_db in (20.0, 30.0, 40.0):
            semente = rj["sementes_por_snr_db"][str(snr_db)]
            self.assertEqual(semente, seed + int(round(snr_db * 1000.0)) + 50_000_000)
            # Reconstrução SÓ a partir da semente gravada e da fórmula de potência.
            ruido = np.random.default_rng(semente).normal(0.0, 1.0, size=limpa.shape)
            ruido *= math.sqrt(potencia / (10.0 ** (snr_db / 10.0)) / float(np.mean(np.square(ruido))))
            np.testing.assert_allclose(resultado["janelas"][snr_db] - limpa, ruido, rtol=0, atol=1e-12)

    def test_mesma_seed_mesmo_ruido_e_semente_registrada(self):
        registro = np.sin(2.0 * np.pi * 50.0 * np.arange(8000) / 30_000.0)
        a = sinais.ruido_na_janela(registro, 600, 6000, (30.0,), 5, simulado=True)
        b = sinais.ruido_na_janela(registro, 600, 6000, (30.0,), 5, simulado=True)
        np.testing.assert_array_equal(a["janelas"][30.0], b["janelas"][30.0])
        self.assertEqual(a["metadata"]["ruido_janela"]["sementes_por_snr_db"], {"30.0": 5 + 30_000 + 50_000_000})

    def test_sessao_simulada_grava_sementes_em_ruido_janela(self):
        config = self._config_simulada(self.tmp / "sim")
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
        bancada = mestre.Bancada(fonte, None, config)

        class _Classe(mestre.ExperimentoNativo):
            id = "01"
            nome = "NORMAL"

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

            def configurar(self, capture_index):
                return {}

        _Classe(bancada).executar()
        pasta = config.results_dir
        registros = [json.loads(l) for l in (pasta / "metadata" / "01_normal.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertTrue(registros)
        for registro in registros:
            rj = registro["ruido_janela"]
            self.assertEqual(rj["formula_semente"], "seed + round(snr_db*1000) + 50000000")
            self.assertEqual(
                rj["sementes_por_snr_db"],
                {str(s): registro["seed"] + int(round(s * 1000)) + 50_000_000 for s in (20.0, 30.0, 40.0)},
            )

    # -- procedência do código ---------------------------------------------

    def test_arquivo_novo_em_pasta_do_codigo_acende_git_sujo(self):
        repo = self._repo_git()
        with mock.patch.object(mestre, "PROJECT_ROOT", repo):
            # Arquivo novo fora das pastas do código não conta.
            (repo / "docs" / "nota.md").write_text("nota\n", encoding="utf-8")
            limpo = mestre.info_do_codigo(recalcular=True)
            self.assertFalse(limpo["git_sujo"])
            self.assertEqual(limpo["arquivos_nao_rastreados"], [])
            # Arquivo novo em logica/ conta e aparece na lista.
            (repo / "logica" / "novo.py").write_text("Y = 2\n", encoding="utf-8")
            sujo = mestre.info_do_codigo(recalcular=True)
            self.assertTrue(sujo["git_sujo"])
            self.assertEqual(sujo["arquivos_nao_rastreados"], ["logica/novo.py"])
            # Recalcula: sem o arquivo, a árvore volta a estar limpa.
            (repo / "logica" / "novo.py").unlink()
            self.assertFalse(mestre.info_do_codigo(recalcular=True)["git_sujo"])

    def test_cada_pasta_do_codigo_conta_e_ignorado_nao(self):
        repo = self._repo_git()
        with mock.patch.object(mestre, "PROJECT_ROOT", repo):
            for pasta in ("scripts", "experimentos_nativos", "experimentos_waveform"):
                (repo / pasta / "novo.py").write_text("Z = 3\n", encoding="utf-8")
                self.assertTrue(mestre.info_do_codigo(recalcular=True)["git_sujo"], pasta)
                (repo / pasta / "novo.py").unlink()
            (repo / "logica" / "__pycache__").mkdir()
            (repo / "logica" / "__pycache__" / "x.pyc").write_bytes(b"\0")
            self.assertFalse(mestre.info_do_codigo(recalcular=True)["git_sujo"])

    def test_cache_sem_recalcular_mantem_o_valor_do_processo(self):
        repo = self._repo_git()
        with mock.patch.object(mestre, "PROJECT_ROOT", repo):
            self.assertFalse(mestre.info_do_codigo(recalcular=True)["git_sujo"])
            (repo / "logica" / "novo.py").write_text("Y = 2\n", encoding="utf-8")
            self.assertFalse(mestre.info_do_codigo()["git_sujo"])  # cache do processo
            self.assertTrue(mestre.info_do_codigo(recalcular=True)["git_sujo"])

    def test_preparar_pasta_recalcula_entre_runs_e_grava_perfis(self):
        repo = self._repo_git()
        with mock.patch.object(mestre, "PROJECT_ROOT", repo), mock.patch("builtins.print"):
            primeira = mestre.preparar_pasta_da_sessao(self.tmp / "run01", bancada=True, perfis_usados=["literatura"])
            (repo / "logica" / "novo.py").write_text("Y = 2\n", encoding="utf-8")
            segunda = mestre.preparar_pasta_da_sessao(
                self.tmp / "run02", bancada=True, perfis_usados=["literatura", "norma"],
            )
        self.assertFalse(primeira["git_sujo"])
        self.assertTrue(segunda["git_sujo"])
        sessao = json.loads((self.tmp / "run02" / "sessao.json").read_text(encoding="utf-8"))
        self.assertTrue(sessao["git_sujo"])
        self.assertEqual(sessao["arquivos_nao_rastreados"], ["logica/novo.py"])
        self.assertEqual(sessao["perfis_usados_na_cli"], ["literatura", "norma"])
        self.assertEqual(sessao["perfil"], mestre.PERFIL)

    def test_cli_grava_perfil_de_cada_run_na_sua_pasta(self):
        import cli
        sessao_cli = cli.SessaoCLI()
        with mock.patch.object(mestre, "RESULTS_DIR", self.tmp / "resultados"), \
                mock.patch.object(mestre, "SESSION_RESULTS_DIR", None), \
                mock.patch.object(mestre, "configurar_log_de_sessao"), \
                mock.patch("builtins.print"):
            with mock.patch.object(mestre, "PERFIL", "literatura"):
                sessao_cli._garantir_pasta_sessao()
            with mock.patch.object(mestre, "PERFIL", "norma"):
                sessao_cli._garantir_pasta_sessao()
        primeira, segunda = sorted((self.tmp / "resultados").glob("sessao_*"))
        self.assertTrue(segunda.name.endswith("_run02"))
        s1 = json.loads((primeira / "sessao.json").read_text(encoding="utf-8"))
        s2 = json.loads((segunda / "sessao.json").read_text(encoding="utf-8"))
        self.assertEqual((s1["perfil"], s1["perfis_usados_na_cli"]), ("literatura", ["literatura"]))
        self.assertEqual((s2["perfil"], s2["perfis_usados_na_cli"]), ("norma", ["literatura", "norma"]))


class RunListaTests(unittest.TestCase):
    """``run <lista>`` na CLI (``01-07,09-20``): parser, recusa sem energizar,
    confirmação específica (``EXECUTAR-CLASSES-<normalizada>``) e execução da
    lista por ``Bancada.executar_bateria``, na ordem numérica."""

    def setUp(self):
        import cli
        self.cli = cli
        self.sessao = cli.SessaoCLI()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _rodar(self, metodo, *args):
        import io
        from contextlib import redirect_stdout
        saida = io.StringIO()
        with redirect_stdout(saida):
            codigo = metodo(*args)
        return codigo, saida.getvalue()

    # -- parser e normalização (funções puras) ------------------------------

    def test_parser_aceita_intervalos_e_ids_soltos(self):
        p = self.cli.parsear_lista_classes
        self.assertEqual(p("01-07,09-20"), list(range(1, 8)) + list(range(9, 21)))
        self.assertEqual(p("2,5,8"), [2, 5, 8])
        self.assertEqual(p("10-16"), list(range(10, 17)))
        self.assertEqual(p("5"), [5])
        self.assertEqual(p("2,2-3"), [2, 3])  # repetido não duplica
        self.assertEqual(p(" 01 - 03 , 05 "), [1, 2, 3, 5])  # espaços ignorados
        self.assertEqual(p("20,1"), [1, 20])  # ordem numérica, não a digitada

    def test_parser_recusa_entradas_invalidas(self):
        for texto in ("07-01", "01-", "-05", "01,,02", "01,", ",01", "", "   ",
                      "0", "21", "00", "1-21", "0-5", "a", "1.5", "²", "01-07,xx"):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                self.cli.parsear_lista_classes(texto)

    def test_normalizacao_forma_a_confirmacao(self):
        n = self.cli.normalizar_lista_classes
        self.assertEqual(n(self.cli.parsear_lista_classes("01-07,09-20")), "01-07,09-20")
        self.assertEqual(n(self.cli.parsear_lista_classes("2,5,8")), "02,05,08")
        self.assertEqual(n(self.cli.parsear_lista_classes("1,2")), "01-02")
        self.assertEqual(n([3]), "03")

    # -- recusa sem energizar ----------------------------------------------

    def test_entrada_invalida_e_recusada_sem_chamar_a_bancada(self):
        for entrada in (["07-01"], ["01-07,"], ["0-5"], ["1-21"], ["01-"], ["a-b"], ["01-07,,09"]):
            with self.subTest(entrada=entrada), \
                    mock.patch.object(mestre.Bancada, "from_env") as from_env, \
                    mock.patch.object(self.sessao, "confirmar") as confirmar, \
                    mock.patch.object(self.sessao, "autorizar_saida") as saida, \
                    mock.patch.object(self.sessao, "_garantir_pasta_sessao") as pasta:
                codigo, saida_txt = self._rodar(self.sessao.cmd_run, entrada)
                self.assertEqual(codigo, 1)
                self.assertIn("recusada", saida_txt)
                self.assertIn("Nada foi energizado", saida_txt)
                from_env.assert_not_called()
                confirmar.assert_not_called()
                saida.assert_not_called()
                pasta.assert_not_called()

    def test_id_unico_inexistente_segue_o_caminho_de_uma_classe_e_nao_energiza(self):
        # Sem vírgula nem hífen, 'run 21' é o caminho de uma classe (inalterado).
        for entrada in (["21"], ["00"], ["a"]):
            with self.subTest(entrada=entrada), \
                    mock.patch.object(mestre.Bancada, "from_env") as from_env, \
                    mock.patch.object(self.sessao, "confirmar") as confirmar:
                codigo, saida_txt = self._rodar(self.sessao.cmd_run, entrada)
                self.assertEqual(codigo, 1)
                self.assertIn("não encontrada", saida_txt)
                from_env.assert_not_called()
                confirmar.assert_not_called()

    def test_run_com_uma_classe_mantem_a_confirmacao_antiga(self):
        with mock.patch.object(self.sessao, "confirmar", return_value=False) as confirmar:
            codigo, _ = self._rodar(self.sessao.cmd_run, ["5"])
        self.assertEqual(codigo, 1)
        self.assertEqual(confirmar.call_args[0][1], "EXECUTAR-CLASSE-05")

    def test_run_all_viavel_mantem_a_confirmacao_antiga(self):
        with mock.patch.object(mestre, "scripts_da_bateria_fisica",
                               return_value=[p for p in mestre._experiment_scripts() if p.stem in ("01", "02")]), \
                mock.patch.object(self.sessao, "confirmar", return_value=False) as confirmar:
            codigo, _ = self._rodar(self.sessao.cmd_run, ["all"])
        self.assertEqual(codigo, 1)
        self.assertEqual(confirmar.call_args[0][1], "EXECUTAR-20-CLASSES")

    # -- confirmação --------------------------------------------------------

    def test_confirmacao_mostra_capturas_so_das_classes_escolhidas(self):
        with mock.patch("builtins.input", return_value="nao confere"), \
                mock.patch.object(mestre.Bancada, "from_env") as from_env:
            codigo, saida = self._rodar(self.sessao.cmd_run, ["01-03,05"])
        self.assertEqual(codigo, 1)
        from_env.assert_not_called()
        self.assertIn("4 capturas planejadas", saida)
        self.assertIn("TRACe:", saida)
        for classe in ("01", "02", "03", "05"):
            self.assertIn(f"  {classe}  ", saida)
        self.assertNotIn("  04  ", saida)
        self.assertNotIn("  08  ", saida)

    def test_confirmacao_exige_a_lista_normalizada_case_sensitive(self):
        recusadas = ("EXECUTAR-CLASSES-1-3,5", "executar-classes-01-03,05",
                     "EXECUTAR-CLASSES-01-03,05 ", "EXECUTAR-CLASSE-01-03,05",
                     "EXECUTAR-20-CLASSES", "")
        for resposta in recusadas:
            with self.subTest(resposta=resposta), \
                    mock.patch("builtins.input", return_value=resposta), \
                    mock.patch.object(mestre.Bancada, "from_env") as from_env:
                codigo, saida = self._rodar(self.sessao.cmd_run, ["01-03,05"])
                self.assertEqual(codigo, 1)
                self.assertIn("Cancelado", saida)
                from_env.assert_not_called()

    # -- execução simulada pelo executar_bateria ----------------------------

    def _executar_com_classes_falsas(self, entrada, executadas, *, extra=None, falhas=()):
        """Roda ``cmd_run`` de verdade (``from_env`` real em modo simulado e
        ``executar_bateria`` real), trocando só as classes por falsas que
        registram o id em ``executadas`` — sem gerar formas nem gravar arquivo.
        ``falhas``: ids cuja ``executar()`` levanta erro de EXPERIMENTO."""
        def carregar(script_path):
            class_id = script_path.stem

            class _Falsa:
                nome = f"FALSA_{class_id}"

                def __init__(self, bancada):
                    pass

                def executar(self):
                    executadas.append(class_id)
                    if class_id in falhas:
                        raise ValueError("RMS fora de tolerância (teste)")

            return _Falsa

        def capturas_falsas(scripts=None):
            return [(s.stem, s.stem, {"total": 1, "niveis": 1, "por_nivel": 1, "padrao": 1,
                                      "escritas_trace": 0, "escritas_trace_exatas": True})
                    for s in scripts]

        patches = [
            mock.patch.object(mestre, "SIMULATED_MODE", True),
            mock.patch.object(mestre, "SESSION_RESULTS_DIR", self.tmp),
            mock.patch.object(mestre.Bancada, "_carregar_classe_experimento", side_effect=carregar),
            mock.patch.object(self.cli.SessaoCLI, "_capturas_das_classes", new=staticmethod(capturas_falsas)),
            mock.patch.object(self.sessao, "_garantir_pasta_sessao"),
            mock.patch.object(self.sessao, "autorizar_saida"),
            mock.patch.object(self.sessao, "confirmar", return_value=True),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        if extra:
            for patch in extra:
                patch.start()
                self.addCleanup(patch.stop)
        return self._rodar(self.sessao.cmd_run, entrada)

    def test_run_lista_executa_exatamente_a_lista_em_ordem(self):
        executadas = []
        codigo, saida = self._executar_com_classes_falsas(["01-03,05"], executadas)
        self.assertEqual(executadas, ["01", "02", "03", "05"])
        self.assertEqual(codigo, 0)
        self.assertIn("4/4 classes OK", saida)
        self.assertEqual(sorted(self.sessao.ultimo_resultado), ["01", "02", "03", "05"])

    def test_run_lista_aplica_bateria_excluir_conforme_pendencia_atualizada(self):
        executadas = []
        codigo, _ = self._executar_com_classes_falsas(
            ["02,03"], executadas,
            extra=[mock.patch.object(mestre, "BATERIA_EXCLUIR", ("02",))],
        )
        self.assertEqual(executadas, ["03"])
        self.assertEqual(codigo, 0)

    def test_run_lista_falha_de_experimento_nao_para_a_lista(self):
        # Resiliência de executar_bateria (não ampliada aqui): a 02 falha com
        # erro de experimento, a lista segue para a 03 e a 05.
        executadas = []
        codigo, saida = self._executar_com_classes_falsas(["01-03,05"], executadas, falhas=("02",))
        self.assertEqual(executadas[0], "01")
        self.assertIn("03", executadas)
        self.assertIn("05", executadas)
        self.assertEqual(codigo, 1)
        self.assertIn("FALHOU [02]", saida)
        self.assertIn("3/4 classes OK", saida)

    def test_run_lista_recusada_pela_confirmacao_nao_chama_executar_bateria(self):
        with mock.patch.object(self.sessao, "confirmar", return_value=False), \
                mock.patch.object(mestre.Bancada, "from_env") as from_env:
            codigo, _ = self._rodar(self.sessao.cmd_run, ["01-07,09-20"])
        self.assertEqual(codigo, 1)
        from_env.assert_not_called()

    def test_help_documenta_a_lista(self):
        self.assertIn("run 01-07,09-20", self.cli.HELP_TEXT)
        self.assertIn("EXECUTAR-CLASSES-", self.cli.HELP_TEXT)





class AssinaturaPortavelTests(unittest.TestCase):
    """Fixtures de ``gerar()`` portaveis entre plataformas (v1.15).

    Contra-prova: a assinatura por tolerancia ainda pega qualquer mudanca real
    (uma amostra, um parametro) e ignora diferencas de ultimo bit de
    ``np.sin``. A assinatura EXATA (SHA-256) so vale onde o fixture foi
    gravado: pulada (skip) fora do Windows, a nao ser com ``ASD_HASH_EXATO=1``.
    """

    FIXTURES = {
        "literatura": (PerfisDeFaixasTests.REFERENCIA, True),
        "sorteio": (PROJECT_ROOT / "tests" / "fixtures" / "gerar_sorteio_v1_15.json", False),
    }

    @staticmethod
    def _exato_vale_aqui():
        import os
        return sys.platform == "win32" or os.environ.get("ASD_HASH_EXATO") == "1"

    def _verificar_exato(self, nome):
        if not self._exato_vale_aqui():
            self.skipTest(
                "assinatura SHA-256 exata so vale na plataforma onde o fixture foi gravado (Windows, Python 3.11, "
                "numpy 2.4.6): np.sin difere no ultimo bit entre plataformas. A verificacao portavel cobre esta "
                "plataforma; ASD_HASH_EXATO=1 forca a exata."
            )
        caminho, sem_sorteio = self.FIXTURES[nome]
        ref = json.loads(caminho.read_text(encoding="utf-8"))
        self.assertEqual(len(ref["hashes"]), 400)
        for chave, esperado in ref["hashes"].items():
            cid, f0, seed, indice = chave.split("/")
            exp = _load_experimento(cid)
            if sem_sorteio:
                exp = _sem_sorteio(exp)
            self.assertEqual(PerfisDeFaixasTests._assinatura(exp, float(f0), int(seed), int(indice)), esperado, chave)

    def test_literatura_exato_na_plataforma_de_origem(self):
        self._verificar_exato("literatura")

    def test_sorteio_exato_na_plataforma_de_origem(self):
        self._verificar_exato("sorteio")

    def _caso(self, cid="03", f0=60.0, seed=1234567, indice=2, sem_sorteio=True):
        exp = _load_experimento(cid)
        if sem_sorteio:
            exp = _sem_sorteio(exp)
        t = np.arange(6000, dtype=np.float64) / 30_000.0
        v, p = exp.gerar(t, f0, indice, np.random.default_rng(seed))
        return np.array(v, dtype=np.float64), p

    @staticmethod
    def _dif(v, p, ref):
        return assinatura_portavel.diferencas(assinatura_portavel.resumo(v, p), ref)

    def test_ignora_diferenca_de_ultimo_bit_como_a_de_np_sin_entre_plataformas(self):
        for cid in ("01", "03", "09", "17"):
            v, p = self._caso(cid)
            ref = assinatura_portavel.resumo(v, p)
            # ate 64 ULP em todas as amostras (os 16 ULP medidos entre o numpy do Linux e long double)
            ruido = v + np.spacing(np.abs(v)) * np.random.default_rng(5).integers(-64, 65, v.size)
            self.assertEqual(self._dif(ruido, p, ref), [], cid)
            # o SHA-256 exato mudaria (por isso ele nao e portavel)
            self.assertNotEqual(np.asarray(ruido, "<f8").tobytes(), np.asarray(v, "<f8").tobytes(), cid)

    def test_pega_uma_unica_amostra_alterada(self):
        rng = np.random.default_rng(11)
        for cid in ("01", "03", "10", "18"):
            v, p = self._caso(cid)
            ref = assinatura_portavel.resumo(v, p)
            posicoes = [0, 1, 2999, 5998, 5999] + [int(i) for i in rng.integers(0, 6000, 40)]
            for i in posicoes:
                for delta in (1e-7, -1e-7):
                    w = v.copy()
                    w[i] += delta
                    self.assertNotEqual(self._dif(w, p, ref), [], (cid, i, delta))

    def test_pega_amostra_alterada_em_1e8_pu(self):
        v, p = self._caso("03")
        ref = assinatura_portavel.resumo(v, p)
        posicoes = range(0, 6000, 37)
        achou = 0
        for i in posicoes:
            w = v.copy()
            w[i] += 1e-8
            achou += bool(self._dif(w, p, ref))
        self.assertEqual(achou, len(posicoes))

    def test_pega_forma_deslocada_ou_amplitude_trocada(self):
        v, p = self._caso("01")
        ref = assinatura_portavel.resumo(v, p)
        for w in (np.roll(v, 1), v * (1.0 + 1e-7), v[::-1].copy(), v + 1e-7):
            self.assertNotEqual(self._dif(w, p, ref), [])

    def test_pega_parametro_alterado(self):
        v, p = self._caso("03")
        ref = assinatura_portavel.resumo(v, p)
        self.assertTrue(p)
        for chave, valor in p.items():
            q = dict(p)
            if isinstance(valor, float):
                q[chave] = valor + 1e-6
            elif isinstance(valor, int):
                q[chave] = valor + 1
            else:
                q[chave] = str(valor) + "x"
            self.assertIn("parametros", self._dif(v, q, ref), chave)
        r = dict(p)
        r["parametro_novo"] = 1
        self.assertIn("parametros", self._dif(v, r, ref))
        self.assertIn("parametros", self._dif(v, {}, ref))

    def test_pega_numero_de_amostras_diferente(self):
        v, p = self._caso("01")
        ref = assinatura_portavel.resumo(v, p)
        self.assertIn("n", self._dif(v[:-1], p, ref))

    def test_fixtures_portaveis_nao_confundem_classes_diferentes(self):
        """Entradas com resumo identico so podem ser da mesma classe e, entre
        classes, nenhum par cai dentro da tolerancia (ela nao e frouxa demais)."""
        for caminho, _ in self.FIXTURES.values():
            resumos = json.loads(caminho.read_text(encoding="utf-8"))["portavel"]["resumos"]
            grupos = {}
            for chave, r in resumos.items():
                grupos.setdefault(json.dumps(r, sort_keys=True), []).append(chave)
            for grupo in grupos.values():
                self.assertEqual(len({c.split("/")[0] for c in grupo}), 1, grupo[:4])
            por_classe = {}
            for chave, r in resumos.items():
                por_classe.setdefault(chave.split("/")[0], r)
            ids = sorted(por_classe)
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    self.assertNotEqual(
                        assinatura_portavel.diferencas(por_classe[a], por_classe[b]), [], (caminho.name, a, b),
                    )


class ComposicaoSorteadaRepresentacaoTests(unittest.TestCase):
    """Revisão das compostas sorteadas (spec 19): o limite da oscilação de
    2400 Hz (classes 12/14) e do flicker de 25 Hz (11/15) depois da TRACe por
    ciclo, com sag/swell neutros (a TRACe por ciclo tira o DC de um ciclo com
    borda no meio e isso já vale para 02/03, não é da composta)."""

    T = np.arange(6000, dtype=np.float64) / 30000.0

    def _pior_erro(self, classe_id, componente, valor, f0, n=12):
        import dataclasses
        import perfis
        salvo = {chave: dict(v) for chave, v in perfis.FAIXAS_SORTEADAS.items()}
        try:
            perfis.FAIXAS_SORTEADAS["sag_composto"]["literatura"] = (1.0, 1.0)
            perfis.FAIXAS_SORTEADAS["swell_composto"]["literatura"] = (1.0, 1.0)
            perfis.FAIXAS_SORTEADAS[componente]["literatura"] = (valor, valor)
            experimento = _load_experimento(classe_id)
            experimento.config = dataclasses.replace(experimento.config, perfil="literatura", sorteio_posicao=True)
            pior = 0.0
            for indice in range(n):
                forma, _ = experimento.gerar(
                    self.T, f0, indice, np.random.default_rng(experimento.seed_da_captura(indice)),
                )
                programada = AmetekMX30.montar_programacao(
                    forma, base_voltage_rms=127.0, frequency_hz=f0,
                ).programada_pu()
                pior = max(pior, float(np.max(np.abs(programada - forma))))
            return pior
        finally:
            for chave, v in salvo.items():
                perfis.FAIXAS_SORTEADAS[chave].update(v)

    def test_oscilacao_de_2400_hz_sobrevive_a_trace_por_ciclo(self):
        # Medido: <= 0,035 pu (amplitude da oscilação 0,3 pu, ~12 %) em 50 e 60 Hz.
        for classe_id in ("12", "14"):
            for f0 in (50.0, 60.0):
                with self.subTest(classe=classe_id, f0=f0):
                    self.assertLess(self._pior_erro(classe_id, "oscilacao_composto_hz", 2400.0, f0), 0.05)

    def test_flicker_de_25_hz_sobrevive_a_trace_por_ciclo(self):
        # Medido: <= 0,054 pu em 50 e 60 Hz (o flicker vira degraus de 1 ciclo).
        for classe_id in ("11", "15"):
            for f0 in (50.0, 60.0):
                with self.subTest(classe=classe_id, f0=f0):
                    self.assertLess(self._pior_erro(classe_id, "flicker_composto_hz", 25.0, f0), 0.07)


class DiagnosticoCopiaEm100msTests(unittest.TestCase):
    """v1.15, diagnóstico da cópia do evento em 100 ms: modelo provisório da
    fonte, ``diag_ciclos_trace.py`` (offline) e ``diag_marcadores_trace.py``
    (bancada, aqui só ``--simulado``). Sem hardware."""

    @staticmethod
    def _programacao_com_impulso(f0=50.0, amostra=2400, amp=0.8):
        forma = np.sin(2 * np.pi * f0 * np.arange(6000) / 30000.0)
        forma[amostra : amostra + 2] += amp
        return AmetekMX30.montar_programacao(forma, base_voltage_rms=127.0, frequency_hz=f0)

    def _sessao_sintetica(self, medida, programada, f0=50.0):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "metadata").mkdir()
        (tmp / "tres_versoes").mkdir()
        registro = {
            "id_captura": "99-0001", "pontos": 6000, "fs_hz": 30000.0, "f0_hz": f0, "tensao_base_rms": 127.0,
            "inicio_janela": 600, "seed": 1, "parametros": {},
            "tres_versoes": {"arquivo": "tres_versoes/99_sintetica.npz", "programada": "TRACe+LIST"},
        }
        (tmp / "metadata" / "99_sintetica.jsonl").write_text(json.dumps(registro) + "\n", encoding="utf-8")
        # Formato 1 (como as sessões de 07/10): o .npz da captura na raiz, com o registro
        # inteiro (margem + janela), e tres_versoes/ com modelo e programada.
        np.savez(
            tmp / "99_sintetica.npz", classe="SINTETICA", id_captura=np.array(["99-0001"], dtype=object),
            tempo_ms=np.arange(600 + 6000) / 30.0, tensao_pu=np.concatenate([np.zeros(600), medida])[np.newaxis, :],
        )
        np.savez(
            tmp / "tres_versoes" / "99_sintetica.npz", classe="SINTETICA", id_captura=np.array(["99-0001"], dtype=object),
            tempo_ms=np.arange(6000) / 30.0, modelo_pu=programada[np.newaxis, :], medida_pu=medida[np.newaxis, :],
            programada_pu=programada[np.newaxis, :], inicio_janela=np.array(600),
            origem_programada=np.array("TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)"),
        )
        return tmp

    # --- modelo provisório -------------------------------------------------
    def test_modelo_ideal_reproduz_programada_pu(self):
        import modelo_lista_fonte as modelo
        for f0 in (50.0, 60.0):
            prog = self._programacao_com_impulso(f0, 2400)
            np.testing.assert_allclose(modelo.prever_forma(prog, "ideal"), prog.programada_pu(), rtol=0, atol=1e-12)

    def test_modelo_atraso_de_passos_move_o_evento_20ms(self):
        import modelo_lista_fonte as modelo
        prog = self._programacao_com_impulso(50.0, 2400)
        ideal = modelo.prever_forma(prog, "ideal")
        atrasado = modelo.prever_forma(prog, "atraso_de_passos", d=1, t_inicio_s=0.080)
        self.assertGreater(abs(ideal[2400]), 0.5)
        self.assertLess(abs(atrasado[2400] - np.sin(2 * np.pi * 50 * 2400 / 30000.0)), 0.05)
        self.assertGreater(abs(atrasado[3000]), 0.5)  # 100 ms
        with self.assertRaises(ValueError):
            modelo.prever_forma(prog, "inexistente")
        with self.assertRaises(ValueError):
            modelo.prever_forma(prog, "atraso_de_passos", nao_existe=1)

    def test_modelo_confrontar_poe_a_hipotese_verdadeira_primeiro(self):
        import modelo_lista_fonte as modelo
        prog = self._programacao_com_impulso(50.0, 2400)
        medida = modelo.prever_forma(prog, "atraso_de_passos", d=1, t_inicio_s=0.080)
        ranking = modelo.confrontar(prog, medida)
        self.assertEqual(ranking[0]["nome"], "passo_atrasado_1_a_partir_de_80ms")
        self.assertLess(ranking[0]["rms_residuo_pu"], 1e-9)
        self.assertGreater(ranking[-1]["rms_residuo_pu"], ranking[0]["rms_residuo_pu"])

    # --- diag_ciclos_trace.py ----------------------------------------------
    def test_diag_ciclos_detecta_o_ciclo_trocado_e_o_instante(self):
        script = _carregar_script("diag_ciclos_trace")
        prog = self._programacao_com_impulso(50.0, 2400)
        programada = prog.programada_pu()
        n = prog.pontos_por_ciclo
        medida = programada.copy()
        # O defeito de 07/10: o impulso do ciclo 4 sai um ciclo (20 ms) depois.
        medida[4 * n : 5 * n] = programada[3 * n : 4 * n]
        medida[5 * n : 6 * n] = programada[4 * n : 5 * n]
        sessao = self._sessao_sintetica(medida, programada)
        capturas = script.carregar_sessao(sessao, usar_forma_bancada=False)
        self.assertEqual(len(capturas), 1)
        r = script.analisar_captura(capturas[0])
        self.assertEqual(r["troca"]["ciclos_trocados"], [4, 5])
        self.assertEqual(r["troca"]["primeiro_ciclo"], 4)
        self.assertEqual(r["troca"]["explicado_por"], "k-1")
        self.assertAlmostEqual(r["troca"]["instante_ciclo_ms"], 80.0, places=6)
        self.assertEqual(r["troca"]["primeira_amostra_divergente"], 2400)
        self.assertEqual({c["estado"] for c in r["ciclos_detalhe"] if c["ciclo"] not in (4, 5)}, {"ok"})
        self.assertGreater(r["residuo_no_instante"]["max_abs_pu"], 0.5)
        self.assertAlmostEqual(r["residuo_no_instante"]["instante_ms"], 100.0, delta=0.2)
        texto = script.montar_markdown("sintetica", [r])
        self.assertIn("99-0001", texto)
        self.assertIn("k-1", texto)

    def test_diag_ciclos_sessao_sem_defeito_nao_acusa_troca(self):
        script = _carregar_script("diag_ciclos_trace")
        prog = self._programacao_com_impulso(60.0, 2400)
        programada = prog.programada_pu()
        ruido = np.random.default_rng(0).normal(0, 0.003, programada.size)
        sessao = self._sessao_sintetica(programada + ruido, programada, f0=60.0)
        capturas = script.carregar_sessao(sessao, usar_forma_bancada=False)
        r = script.analisar_captura(capturas[0])
        self.assertIsNone(r["troca"])
        self.assertEqual({c["estado"] for c in r["ciclos_detalhe"]}, {"ok"})

    def test_diag_ciclos_nao_escreve_na_pasta_da_sessao(self):
        script = _carregar_script("diag_ciclos_trace")
        prog = self._programacao_com_impulso(50.0, 2400)
        programada = prog.programada_pu()
        sessao = self._sessao_sintetica(programada.copy(), programada)
        antes = sorted(str(p.relative_to(sessao)) for p in sessao.rglob("*"))
        saida = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, saida, ignore_errors=True)
        with mock.patch("sys.stdout"):
            codigo = script.main([str(sessao), "--saida", str(saida), "--sem-forma-bancada"])
        self.assertEqual(codigo, 0)
        self.assertEqual(sorted(str(p.relative_to(sessao)) for p in sessao.rglob("*")), antes)
        self.assertEqual(len(list(saida.glob("diag_ciclos_trace-*.json"))), 1)
        self.assertEqual(len(list(saida.glob("diag_ciclos_trace-*.md"))), 1)

    # --- diag_marcadores_trace.py ------------------------------------------
    def test_marcadores_sao_unicos_e_dentro_do_limite_de_pico(self):
        script = _carregar_script("diag_marcadores_trace")
        for f0 in (50.0, 60.0):
            forma, marcas = script.forma_marcadores(f0, 0.45)
            self.assertEqual(len({m["pos"] for m in marcas}), len(marcas))
            self.assertEqual(len({round(m["amp"], 6) for m in marcas}), len(marcas))
            self.assertLessEqual(float(np.max(np.abs(forma))) * 127.0 * math.sqrt(2.0), script.MAX_PICO_V)
        plano = script.planejar([50.0, 60.0], list(script.VARIANTES), [40.0, 80.0], 127.0, 0.45)
        self.assertEqual(len(plano), 10)
        self.assertEqual(sum(item["escritas_trace"] for item in plano), 110)
        self.assertTrue(all(item["pico_reconstruido_v"] <= script.MAX_PICO_V for item in plano))
        # 80 ms: ponto 0 do ciclo 4 a 50 Hz; a 60 Hz o primeiro ciclo que começa depois é o 5.
        self.assertEqual(script.ciclo_do_instante(80.0, 50.0), 4)
        self.assertEqual(script.ciclo_do_instante(80.0, 60.0), 5)

    def test_marcadores_recusa_tensao_sem_folga_de_pico(self):
        script = _carregar_script("diag_marcadores_trace")
        with self.assertRaises(SystemExit):
            script.amplitude_maxima_pu(270.0, 0.45)
        self.assertLessEqual(script.amplitude_maxima_pu(220.0, 0.45), 0.45)

    def test_marcadores_exige_probe_e_bench_mode_sem_simulado(self):
        script = _carregar_script("diag_marcadores_trace")
        saida = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, saida, ignore_errors=True)
        import os
        ambiente = {k: v for k, v in os.environ.items() if k not in {"VOLTAGE_PROBE_ATTENUATION", "BENCH_MODE"}}
        with mock.patch.dict("os.environ", ambiente, clear=True):
            with self.assertRaises(SystemExit):  # sem --probe
                script.main(["--simulado", "--saida", str(saida)])
            with self.assertRaises(SystemExit):  # real sem BENCH_MODE=1
                script.main(["--probe", "500", "--saida", str(saida)])
        self.assertEqual(list(saida.iterdir()), [])  # nada gravado, nenhum instrumento aberto

    def _rodar_simulado(self, simular, *extra):
        script = _carregar_script("diag_marcadores_trace")
        saida = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, saida, ignore_errors=True)
        with mock.patch("sys.stdout"):
            codigo = script.main(["--simulado", "--probe", "500", "--vrms", "127", "--simular", simular,
                                  "--saida", str(saida), *extra])
        self.assertEqual(codigo, 0)
        dados = json.loads(next(saida.glob("diag_marcadores_trace-*.json")).read_text(encoding="utf-8"))
        return dados["capturas"]

    def test_marcadores_simulado_ideal_recupera_cada_marcador_no_seu_ciclo(self):
        capturas = self._rodar_simulado("ideal", "--frequencias", "50,60", "--variantes", "marcadores")
        self.assertEqual([c["rotulo"] for c in capturas], ["marcadores@50Hz", "marcadores@60Hz"])
        for c in capturas:
            n_marc = len(c["marcadores_programados"])
            self.assertEqual(len(c["observados"]), n_marc)
            self.assertEqual([o["k"] for o in c["observados"]], list(range(n_marc)))
            self.assertTrue(all(o["troca_ciclos"] == 0 and o["atraso_amostras"] == 0 for o in c["observados"]))
            self.assertIsNone(c["resumo"]["troca_de_passo"])
            self.assertEqual(c["resumo"]["espurios"], [])
            self.assertEqual(c["hipoteses"][0]["nome"], "ideal")

    def test_marcadores_simulado_recupera_a_troca_de_passo_e_o_instante(self):
        capturas = self._rodar_simulado("atraso_de_passos:d=1,t_inicio_s=0.1", "--frequencias", "50,60", "--variantes", "marcadores")
        for c, ciclo_100ms in zip(capturas, (5, 6)):
            troca = c["resumo"]["troca_de_passo"]
            self.assertEqual(troca["primeiro_ciclo_medido"], ciclo_100ms)
            self.assertAlmostEqual(troca["instante_ms"], 100.0, places=6)
            self.assertEqual(troca["deslocamento_ciclos"], 1)
            for o in c["observados"]:
                esperado = 1 if o["ciclo_medido"] >= ciclo_100ms else 0
                self.assertEqual(o["troca_ciclos"], esperado)
                self.assertEqual(o["k"], o["ciclo_medido"] - esperado)
            self.assertEqual(c["hipoteses"][0]["nome"], "passo_atrasado_1_a_partir_de_100ms")

    def test_marcadores_simulado_atraso_global_em_amostras_e_variantes_de_evento(self):
        capturas = self._rodar_simulado("ideal", "--frequencias", "50", "--variantes", "marcadores", "--atraso-simulado", "3")
        self.assertEqual({o["atraso_amostras"] for o in capturas[0]["observados"]}, {3})
        capturas = self._rodar_simulado("atraso_de_passos:d=1,t_inicio_s=0.08", "--frequencias", "50", "--variantes", "fronteira,meio_ciclo")
        self.assertEqual([c["rotulo"] for c in capturas],
                         ["fronteira@50Hz/ciclo2", "fronteira@50Hz/ciclo4", "meio_ciclo@50Hz/ciclo2", "meio_ciclo@50Hz/ciclo4"])
        for c in capturas:
            ciclos_vistos = [o["ciclo_medido"] for o in c["observados"]]
            if c.get("ciclo_evento") == 2:
                self.assertEqual(ciclos_vistos, [2])  # antes de 80 ms: sem cópia
            else:
                self.assertEqual(ciclos_vistos, [5])  # com a troca desde 80 ms o evento do ciclo 4 sai no 5
                self.assertEqual(c["resumo"]["troca_de_passo"]["instante_ms"], 100.0)


class VerificadorSessaoBancadaTests(unittest.TestCase):
    """Spec 20: ``scripts/verificar_sessao_bancada.py`` numa sessão SINTÉTICA
    (formato v1.15: ``metadata/*.jsonl`` + um ``.npz`` por captura) e o
    ``diag_acdc_amplitude.py --simulado``."""

    FS = 30_000.0
    MARGEM_ANTES = 600
    TOTAL = 8100

    @classmethod
    def setUpClass(cls):
        caminho = PROJECT_ROOT / "scripts" / "verificar_sessao_bancada.py"
        spec = importlib.util.spec_from_file_location("verificar_sessao_bancada_teste", caminho)
        cls.v = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.v  # @dataclass com `from __future__ import annotations` exige
        spec.loader.exec_module(cls.v)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="verificador_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "metadata").mkdir()
        self.linhas = {}

    def _gravar(self, id_captura, nome_arquivo, registro, metadado):
        np.savez(
            self.tmp / nome_arquivo, classe="X", id_captura=np.array([id_captura], dtype=object),
            tempo_ms=np.arange(registro.size) / self.FS * 1000.0, tensao_pu=registro[np.newaxis, :],
        )
        self.linhas.setdefault(nome_arquivo.split("_")[0], []).append(metadado)
        for classe, registros in self.linhas.items():
            (self.tmp / "metadata" / f"{classe}.jsonl").write_text(
                "\n".join(json.dumps(r) for r in registros) + "\n", encoding="utf-8",
            )

    def _base(self, id_captura, inicio_janela, pre_trigger_s, f0=60.0):
        previsto = int(round(pre_trigger_s * self.FS)) + self.MARGEM_ANTES
        return {
            "id_captura": id_captura, "fs_hz": self.FS, "f0_hz": f0, "pontos": 6000,
            "amostras_totais": self.TOTAL, "margem_amostras_antes": self.MARGEM_ANTES,
            "pre_trigger_s": pre_trigger_s, "inicio_janela": inicio_janela,
            "indice_trigger": inicio_janela + int(round(pre_trigger_s * self.FS)),
            "pre_trigger_desvio_amostras": inicio_janela + int(round(pre_trigger_s * self.FS)) - previsto,
        }

    def _sag(self, numero, t0, d, nivel=0.5, fase_graus=123.4, desvio=1, f0=60.0):
        iw = self.MARGEM_ANTES + desvio
        r = (np.arange(self.TOTAL) - iw) / self.FS
        x = np.sin(2 * np.pi * f0 * r + np.deg2rad(fase_graus))
        x[(r >= t0) & (r < t0 + d)] *= nivel
        id_captura = f"02-{numero:04d}"
        meta = dict(self._base(id_captura, iw, t0, f0), inicio_disturbio_s=t0, duracao_s=d, parametros={"sag_pu": nivel})
        self._gravar(id_captura, f"02_sag_{numero}.npz", x, meta)
        return id_captura

    def _deriva(self, numero, inicio_hz, fim_hz, salto_graus=0.0, fase_graus=40.0):
        iw = self.MARGEM_ANTES
        k = np.arange(self.TOTAL) - iw
        freq = np.where(k < 3000, inicio_hz, fim_hz)
        fase = np.zeros(self.TOTAL)
        fase[1:] = 2 * np.pi * np.cumsum(freq[:-1]) / self.FS
        fase += np.deg2rad(salto_graus) * (k >= 3000)
        x = np.sin(fase + np.deg2rad(fase_graus))
        id_captura = f"18-{numero:04d}"
        meta = dict(self._base(id_captura, iw, 0.0), parametros={"start_hz": inicio_hz, "end_hz": fim_hz})
        self._gravar(id_captura, f"18_frequency_drift_{numero}.npz", x, meta)
        return id_captura

    def test_largura_do_pulso_medida_bate_com_a_programada(self):
        casos = [(0.0167, 0.0083), (0.0476, 0.1032), (0.0300, 0.0400), (0.0170, 0.1650)]
        for numero, (t0, d) in enumerate(casos, start=1):
            for nivel in (0.1, 0.5, 0.9):
                self._sag(numero * 10 + int(nivel * 10), t0, d, nivel=nivel, fase_graus=17.0 * numero)
        resultados = self.v.verificar_capturas(self.v.carregar_sessao(self.tmp))
        larguras = [r for r in resultados if r.verificacao == "largura_pulse"]
        self.assertEqual(len(larguras), len(casos) * 3)
        for r in larguras:
            self.assertIsNotNone(r.ok, r.nota)
            self.assertLessEqual(abs(r.valor), 1.5, (r.id_captura, r.nota))
            self.assertTrue(r.ok, (r.id_captura, r.nota))

    def test_largura_errada_e_reprovada(self):
        # O metadata diz 100 ms, mas o sinal tem 60 ms de afundamento.
        self._sag(1, 0.040, 0.060)
        captura = self.v.carregar_sessao(self.tmp)[0]
        captura.metadado["duracao_s"] = 0.100
        r = [x for x in self.v.verificar_capturas([captura]) if x.verificacao == "largura_pulse"][0]
        self.assertFalse(r.ok)
        self.assertAlmostEqual(r.valor, -40.0, delta=1.5)

    def test_pre_trigger_desvio_do_campo_e_limite(self):
        self._sag(1, 0.0476, 0.1032, desvio=1)
        self._sag(2, 0.0300, 0.0500, desvio=-2)
        self._sag(3, 0.0300, 0.0500, desvio=5)
        resultados = {
            r.id_captura: r for r in self.v.verificar_capturas(self.v.carregar_sessao(self.tmp))
            if r.verificacao == "pre_trigger"
        }
        self.assertEqual([resultados[f"02-000{i}"].valor for i in (1, 2, 3)], [1.0, -2.0, 5.0])
        self.assertEqual([resultados[f"02-000{i}"].ok for i in (1, 2, 3)], [True, True, False])

    def test_pre_trigger_sem_o_campo_e_calculado_do_metadata(self):
        meta = self._base("02-0001", 601, 0.0476)
        del meta["pre_trigger_desvio_amostras"]
        self.assertEqual(self.v.desvio_do_pre_trigger(meta), 1)
        del meta["indice_trigger"]
        self.assertIsNone(self.v.desvio_do_pre_trigger(meta))

    def test_fase_continua_da_18_da_salto_zero_nos_dois_sentidos_e_a_50_e_60_hz(self):
        for numero, (a, b) in enumerate([(57.0, 63.0), (63.0, 57.0), (47.0, 53.0), (53.0, 47.0)], start=1):
            self._deriva(numero, a, b, fase_graus=33.0 * numero)
        resultados = [
            r for r in self.v.verificar_capturas(self.v.carregar_sessao(self.tmp)) if r.verificacao == "fase_18"
        ]
        self.assertEqual(len(resultados), 4)
        for r in resultados:
            self.assertTrue(r.ok, (r.id_captura, r.valor, r.nota))
            self.assertLess(abs(r.valor), 1.5, r.id_captura)

    def test_salto_de_fase_injetado_na_18_e_detectado(self):
        self._deriva(1, 57.0, 63.0, salto_graus=40.0)
        self._deriva(2, 47.0, 53.0, salto_graus=-60.0)
        resultados = {
            r.id_captura: r for r in self.v.verificar_capturas(self.v.carregar_sessao(self.tmp))
            if r.verificacao == "fase_18"
        }
        self.assertAlmostEqual(resultados["18-0001"].valor, 40.0, delta=3.0)
        self.assertAlmostEqual(resultados["18-0002"].valor, -60.0, delta=3.0)
        self.assertFalse(resultados["18-0001"].ok)
        self.assertFalse(resultados["18-0002"].ok)

    def test_main_codigos_de_saida_e_json(self):
        saida = self.tmp / "saida.json"
        self._sag(1, 0.0476, 0.1032)
        self._deriva(1, 57.0, 63.0)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            codigo = self.v.main([str(self.tmp), "--json", str(saida)])
        self.assertEqual(codigo, 0, buffer.getvalue())
        self.assertIn("fase_18: 1/1 OK", buffer.getvalue())
        self.assertIn("largura_pulse: 1/1 OK", buffer.getvalue())
        self.assertEqual(len(json.loads(saida.read_text(encoding="utf-8"))), 4)
        self._deriva(2, 47.0, 53.0, salto_graus=90.0)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.v.main([str(self.tmp)]), 1)

    def test_main_sessao_sem_nada_a_verificar_sai_com_2(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.v.main([str(self.tmp)]), 2)

    def test_pasta_que_nao_e_sessao_levanta(self):
        with self.assertRaises(FileNotFoundError):
            self.v.carregar_sessao(self.tmp / "nao_existe")

    def test_diag_acdc_amplitude_simulado_continua_passando(self):
        saida = self.tmp / "diag"
        ambiente = {k: v for k, v in os.environ.items() if k != "BENCH_MODE"}
        r = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "diag_acdc_amplitude.py"), "--simulado",
             "--probe", "500", "--vrms", "127", "--hz", "60", "--testar-compensacao", "--saida", str(saida)],
            capture_output=True, text=True, env=ambiente, timeout=300,
        )
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        self.assertIn("ACDC / STEP / off 0", r.stdout)
        self.assertIn("V_prog=", r.stdout)
        self.assertTrue(list(saida.glob("diag_acdc_amplitude-*.json")))


class DiagnosticoRetrieveTests(unittest.TestCase):
    """v1.15 — ``set diagnostico retrieve``: ler de volta as TRACEs gravadas
    (``AmetekMX30.ler_trace``) sem violar o quirk A2 (nunca consultar a fonte
    colado a um ``TRACe:DATA``)."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    @staticmethod
    def _programada(fonte, seno_pu=1.0):
        t = np.arange(6000) / 30_000.0
        forma = seno_pu * np.sin(2 * np.pi * 60.0 * t)
        fonte.program_capture(forma, base_voltage_rms=127.0, frequency_hz=60.0)
        return fonte.ultima_programacao

    def test_ler_trace_simulado_devolve_o_que_foi_gravado(self):
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
        programacao = self._programada(fonte)
        for indice, nome in enumerate(programacao.trace_names):
            lido = fonte.ler_trace(nome)
            self.assertEqual(lido.shape, (1024,))
            np.testing.assert_array_equal(lido, programacao.traces[indice])

    def test_ler_trace_recusa_tamanho_errado_e_resposta_ilegivel(self):
        from ametek_orm import LeituraTraceError
        fonte = mestre.AmetekMX30(simulated=True)
        fonte.write("TRACe:DEFine CURTA")
        fonte.write("TRACe:DATA CURTA,0.1,0.2,0.3")
        fonte.write("*CLS")
        with self.assertRaisesRegex(LeituraTraceError, "3 valores"):
            fonte.ler_trace("CURTA")
        with self.assertRaises(LeituraTraceError):  # nunca gravada: resposta vazia
            fonte.ler_trace("NAO_EXISTE")

    def test_leitura_nunca_e_o_comando_seguinte_a_um_trace_data(self):
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
        programacao = self._programada(fonte)
        # Colado a uma escrita de TRACe: recusado, nada é enviado.
        fonte.write(programacao.comando_trace(0))
        enviados = len(fonte.command_log)
        with self.assertRaisesRegex(Exception, "escrita de TRACe"):
            fonte.ler_trace(programacao.trace_names[0])
        self.assertEqual(len(fonte.command_log), enviados)
        # No fluxo normal a leitura vem depois de comandos de outro tipo.
        fonte.write("*CLS")
        for nome in programacao.trace_names:
            fonte.ler_trace(nome)
        log = fonte.command_log
        leituras = [i for i, c in enumerate(log) if c.upper().startswith("TRACE:DATA?")]
        self.assertEqual(len(leituras), len(programacao.trace_names))
        for i in leituras:
            self.assertFalse(log[i - 1].upper().startswith("TRACE:DATA "), log[i - 1][:30])
        # E nenhuma escrita de TRACe depois da primeira leitura.
        self.assertFalse(
            any(c.upper().startswith(("TRACE:DATA ", "TRACE:DEFINE")) for c in log[leituras[0]:])
        )

    def test_espera_minima_desde_a_ultima_escrita_de_trace(self):
        class Recurso:
            def __init__(self):
                self.timeout = 5000
                self.timeouts_vistos = []
                self.ultimo = ""

            def flush(self, *args):
                pass

            def write_raw(self, payload):
                if payload != b"\x04":
                    self.ultimo = payload.decode().strip()

            def read(self):
                self.timeouts_vistos.append(self.timeout)
                if self.ultimo.upper().startswith("TRACE:DATA?"):
                    return ",".join(["0.5"] * 1024)
                return "0"

        recurso = Recurso()
        fonte = mestre.AmetekMX30(visa_resource=recurso)
        fonte._raw_write("TRACe:DATA T1," + ",".join(["0.5"] * 1024))
        fonte._raw_write("*CLS")
        with mock.patch("ametek_orm.time.sleep") as dormir:
            lido = fonte.ler_trace("T1", espera_minima_s=2.0, timeout_s=9.0)
        self.assertEqual(lido.size, 1024)
        dormir.assert_called_once()
        self.assertGreater(dormir.call_args[0][0], 1.5)
        self.assertLessEqual(dormir.call_args[0][0], 2.0)
        self.assertEqual(recurso.timeouts_vistos[-1], 9000)  # timeout próprio...
        self.assertEqual(recurso.timeout, 5000)               # ...restaurado
        # A própria leitura não conta como escrita: a segunda não espera de novo.
        with mock.patch("ametek_orm.time.sleep") as dormir:
            with mock.patch("ametek_orm.time.monotonic", return_value=fonte._t_ultima_escrita_trace + 30.0):
                fonte.ler_trace("T1", espera_minima_s=2.0)
        dormir.assert_not_called()

    def _executar_waveform(self, *, retrieve, lido_adulterado=None):
        config = _config_bancada(
            self.tmp_dir, base_voltage_rms=127.0, diagnostico_retrieve=retrieve,
            diagnostico_retrieve_espera_s=2.0,
        )
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
        if lido_adulterado is not None:
            original = fonte.ler_trace
            fonte.ler_trace = lambda nome, **kw: lido_adulterado(original(nome, **kw))
        # O readback de arm_transient() exige estado que o simulador não modela.
        fonte.arm_transient = lambda *args, **kwargs: None
        fonte.trigger = lambda: fonte.command_log.append("*TRG")
        osc = mock.Mock()
        osc.medir_extremos = lambda canal: (100.0, -100.0)
        experimento = _carregar_classe("07")(mestre.Bancada(fonte, osc, config))
        experimento._calcular_margem = lambda **kw: (0, 0, kw["config_points"])
        experimento._preparar_acquisicao_real = lambda: None
        t = mestre.tempo(config)
        # O osciloscópio devolve exatamente a forma programada (passa na validação física).
        osc.get_waveform.side_effect = lambda *a, **k: (
            t, experimento._forma_programada_pu * 127.0 * math.sqrt(2.0),
        )
        original_capturar = experimento._capturar_real

        def _capturar(capture_index, tt, rng):
            experimento._pontos_efetivos_captura_atual = tt.size
            return original_capturar(capture_index, tt, rng)

        experimento._capturar_real = _capturar
        experimento.executar()
        metadata = config.results_dir / "metadata" / f"{experimento.id}_{experimento.nome.lower()}.jsonl"
        registros = [json.loads(linha) for linha in metadata.read_text(encoding="utf-8").splitlines()]
        return fonte, registros

    def test_sessao_com_retrieve_grava_pasta_separada_com_enviado_igual_a_lido(self):
        fonte, registros = self._executar_waveform(retrieve=True)
        self.assertTrue(registros)
        for registro in registros:
            info = registro["diagnostico_trace"]
            self.assertIsNone(info["erro"])
            self.assertEqual(info["desvio_max"], 0.0)
            self.assertEqual(info["traces_lidas"], info["traces_programadas"])
            arquivo = self.tmp_dir / info["arquivo"]
            self.assertEqual(arquivo.parent.name, "diagnostico_trace")
            with np.load(arquivo, allow_pickle=True) as dados:
                np.testing.assert_array_equal(dados["enviado"], dados["lido"])
                self.assertEqual(dados["enviado"].shape[1], 1024)
                self.assertEqual(dados["list_voltage_rms"].shape[0], dados["enviado"].shape[0])
        # Nada de diagnóstico dentro dos .npz da captura.
        for npz in self.tmp_dir.glob("*.npz"):
            with np.load(npz, allow_pickle=True) as dados:
                self.assertNotIn("lido", dados.files)
        # Ordem: leituras depois do disparo e nenhuma colada a TRACe:DATA.
        log = fonte.command_log
        primeira = next(i for i, c in enumerate(log) if c.upper().startswith("TRACE:DATA?"))
        self.assertTrue(any(c.upper() == "*TRG" for c in log[:primeira]))
        for i, c in enumerate(log):
            if c.upper().startswith("TRACE:DATA?"):
                self.assertFalse(log[i - 1].upper().startswith("TRACE:DATA "))

    def test_desligado_por_padrao_nao_le_nem_grava(self):
        fonte, registros = self._executar_waveform(retrieve=False)
        self.assertFalse(any(c.upper().startswith("TRACE:DATA?") for c in fonte.command_log))
        self.assertNotIn("diagnostico_trace", registros[0])
        self.assertFalse((self.tmp_dir / "diagnostico_trace").exists())

    def test_desvio_aparece_no_metadata(self):
        _, registros = self._executar_waveform(retrieve=True, lido_adulterado=lambda v: v + 0.25)
        for registro in registros:
            self.assertAlmostEqual(registro["diagnostico_trace"]["desvio_max"], 0.25, places=6)

    def test_leitura_com_erro_nao_derruba_a_captura(self):
        from ametek_orm import LeituraTraceError

        def _falha(_valores):
            raise LeituraTraceError("timeout simulado")

        _, registros = self._executar_waveform(retrieve=True, lido_adulterado=_falha)
        self.assertTrue(registros)  # a captura foi gravada mesmo assim
        info = registros[0]["diagnostico_trace"]
        self.assertIn("timeout simulado", info["erro"])
        self.assertEqual(info["traces_lidas"], 0)
        self.assertIsNone(info["desvio_max"])

    def test_cli_set_diagnostico_retrieve_liga_desliga_e_help_menciona(self):
        import cli
        antes = mestre.DIAGNOSTICO_RETRIEVE
        self.addCleanup(setattr, mestre, "DIAGNOSTICO_RETRIEVE", antes)
        sessao = cli.SessaoCLI.__new__(cli.SessaoCLI)
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            self.assertEqual(sessao.cmd_set(["diagnostico", "retrieve"]), 0)
            self.assertTrue(mestre.DIAGNOSTICO_RETRIEVE)
            self.assertEqual(sessao.cmd_set(["diagnostico", "retrieve", "off"]), 0)
            self.assertFalse(mestre.DIAGNOSTICO_RETRIEVE)
            self.assertEqual(sessao.cmd_set(["diagnostico", "retrieve", "talvez"]), 1)
        self.assertIn("diagnostico retrieve: ON", saida.getvalue())
        self.assertIn("set diagnostico retrieve", cli.HELP_TEXT)


class PendentesCorrelacaoDisturbioTests(unittest.TestCase):
    """v1.15, pendentes da correlação do distúrbio (05 contra o diagnóstico,
    correlação com a fundamental ajustada, 09 nas ferramentas da cópia em 100
    ms e a perda da 06 na TRACE por ciclo). Sem hardware."""

    T = np.arange(6000, dtype=np.float64) / 30_000.0
    FS = 30_000.0

    # -- 05 contra o diagnóstico -------------------------------------------

    def test_05_niveis_por_csine_ficam_dentro_do_teto_de_20_pct_em_todos_os_perfis(self):
        import dataclasses
        teto = AmetekMX30.MAX_CSINE_THD_PCT / 100.0
        for perfil in ("norma", "literatura", "fronteira"):
            experimento = _load_experimento("05")
            experimento.config = dataclasses.replace(experimento.config, perfil=perfil)
            for indice, thd in enumerate(experimento.NIVEIS_THD):
                if experimento.usar_trace(indice):
                    self.assertGreater(thd, teto)
                else:
                    self.assertLessEqual(thd, teto)
                    sinais.corte_da_senoide_clipada(thd)  # não levanta dentro do alcance do CSINe
        with self.assertRaises(ValueError):
            sinais.corte_da_senoide_clipada(0.30)

    def test_05_modelo_csine_usa_a_fase_sorteada_da_forma_programada(self):
        experimento = _load_experimento("05")
        for f0 in (50.0, 60.0):
            for seed in range(6):
                voltage, p = experimento.gerar(self.T, f0, 1, np.random.default_rng(seed))
                tau = p["fase_graus"] / (360.0 * f0)
                np.testing.assert_allclose(voltage, sinais.senoide_clipada_pu(self.T, f0, tau, p["thd"]), atol=1e-12)
                # a fase é a da senoide base: o modelo correlaciona com a senoide
                # clipada de MESMA fase (>0,9999) e quase nada com a fase trocada em 90 graus
                corte = sinais.corte_da_senoide_clipada(p["thd"])
                mesma = np.clip(np.sin(2 * np.pi * f0 * (self.T + tau)), -corte, corte)
                outra = np.clip(np.sin(2 * np.pi * f0 * (self.T + tau) + math.pi / 2), -corte, corte)
                self.assertGreater(np.corrcoef(voltage, mesma)[0, 1], 0.9999)
                self.assertLess(abs(np.corrcoef(voltage, outra)[0, 1]), 0.2)
                programada = sinais.forma_programada_nativa(
                    "05", t=self.T, f0_hz=f0, base_voltage_rms=127.0, parametros=p, quantizar=lambda v: v,
                )
                np.testing.assert_allclose(programada, voltage, atol=1e-12)

    def test_05_sem_a_normalizacao_por_rms_o_modelo_ficaria_errado(self):
        # O diagnóstico: sem escalar ao rms da senoide a fundamental sai ~5 % menor
        # (THD 5 %) e a correlação do distúrbio contra a captura cai de 0,97 a 0,67.
        for thd in (0.05, 0.10, 0.20):
            modelo = sinais.senoide_clipada_pu(self.T, 60.0, 0.0, thd)
            corte = sinais.corte_da_senoide_clipada(thd)
            sem_escala = np.clip(np.sin(2 * np.pi * 60.0 * self.T), -corte, corte)
            self.assertAlmostEqual(float(np.sqrt(np.mean(modelo ** 2))), 1 / math.sqrt(2.0), delta=2e-3)
            self.assertLess(float(np.sqrt(np.mean(sem_escala ** 2))), 1 / math.sqrt(2.0) - 0.01)

    def test_05_nivel_de_30_por_trace_a_fonte_emite_o_rms_do_proprio_modelo(self):
        # O modelo do nível de 30 % tem rms sqrt((1+thd^2)/2) = 0,738 (fundamental
        # 1 pu), não 0,707 como os níveis do CSINe. montar_programacao põe esse
        # rms no LIST:VOLTage, então a programada reproduz o modelo (corr. 1,000)
        # e a fonte emite 1,044 x a tensão base nesse nível: a diferença é entre
        # níveis, não entre modelo e programada (docs/correlacao_disturbio.md).
        experimento = _load_experimento("05")
        indice = list(experimento.NIVEIS_THD).index(0.30)
        for f0 in (50.0, 60.0):
            for seed in range(4):
                voltage, p = experimento.gerar(self.T, f0, indice, np.random.default_rng(seed))
                programacao = AmetekMX30.montar_programacao(voltage, base_voltage_rms=127.0, frequency_hz=f0)
                programada = programacao.programada_pu()
                self.assertLess(float(np.max(np.abs(programada - voltage))), 2e-3)
                valor, _ = sinais.correlacao_disturbio(
                    voltage, programada, fs_hz=self.FS, f0_hz=f0, fase_graus=p["fase_graus"],
                )
                self.assertGreater(valor, 0.9999)
                self.assertAlmostEqual(float(np.sqrt(np.mean(voltage ** 2))), math.sqrt((1 + 0.30 ** 2) / 2), delta=2e-3)
                self.assertAlmostEqual(
                    float(np.max(programacao.list_voltages_rms)) / 127.0, math.sqrt(1 + 0.30 ** 2), delta=2e-3,
                )
                self.assertLess(programacao.pico_reconstruido_v, 425.0)

    # -- correlação com a fundamental ajustada -----------------------------

    def _09(self, f0=60.0, seed=5):
        experimento = _load_experimento("09")
        voltage, p = experimento.gerar(self.T, f0, 0, np.random.default_rng(seed))
        return voltage, p

    def test_fundamental_ajustada_amplitude_1_pct_maior_da_quase_1(self):
        for f0 in (50.0, 60.0):
            esperado, p = self._09(f0)
            tau = p["fase_graus"] / (360.0 * f0)
            fundamental = np.sin(2 * np.pi * f0 * (self.T + tau))
            capturado = esperado + 0.01 * fundamental  # fundamental 1 % maior, distúrbio igual
            nominal, _ = sinais.correlacao_disturbio(
                esperado, capturado, fs_hz=self.FS, f0_hz=f0, fase_graus=p["fase_graus"],
            )
            ajustada, motivo = sinais.correlacao_disturbio_fundamental_ajustada(
                esperado, capturado, fs_hz=self.FS, f0_hz=f0,
            )
            self.assertIsNone(motivo)
            self.assertGreater(ajustada, 0.9999)
            self.assertLess(nominal, 0.99)  # a métrica nominal paga o 1 % (a 09 tem distúrbio pequeno)
            # e o mesmo para 1 % no ganho do sinal inteiro e para um desvio de fase de 1 grau
            escalado, _ = sinais.correlacao_disturbio_fundamental_ajustada(
                esperado, 1.01 * esperado, fs_hz=self.FS, f0_hz=f0,
            )
            self.assertGreater(escalado, 0.9999)
            fase = np.sin(2 * np.pi * f0 * (self.T + tau) + math.radians(1.0))
            defasado, _ = sinais.correlacao_disturbio_fundamental_ajustada(
                esperado, esperado - fundamental + fase, fs_hz=self.FS, f0_hz=f0,
            )
            self.assertGreater(defasado, 0.999)

    def test_fundamental_ajustada_distingue_distubio_diferente(self):
        esperado, p = self._09(60.0)
        outro, _ = self._09(60.0, seed=6)
        valor, _ = sinais.correlacao_disturbio_fundamental_ajustada(esperado, outro, fs_hz=self.FS, f0_hz=60.0)
        self.assertLess(abs(valor), 0.6)
        # sinal trocado no distúrbio: -1
        tau = p["fase_graus"] / (360.0 * 60.0)
        fundamental = np.sin(2 * np.pi * 60.0 * (self.T + tau))
        invertido = fundamental - (esperado - fundamental)
        valor, _ = sinais.correlacao_disturbio_fundamental_ajustada(esperado, invertido, fs_hz=self.FS, f0_hz=60.0)
        self.assertLess(valor, -0.999)

    def test_fundamental_ajustada_degenerados_como_na_metrica_nominal(self):
        fundamental = np.sin(2 * np.pi * 60.0 * self.T)
        # 01: só a fundamental
        valor, motivo = sinais.correlacao_disturbio_fundamental_ajustada(
            fundamental, 1.02 * fundamental, fs_hz=self.FS, f0_hz=60.0,
        )
        self.assertIsNone(valor)
        self.assertTrue(motivo)
        # 19: fundamental + offset DC puro
        valor, motivo = sinais.correlacao_disturbio_fundamental_ajustada(
            fundamental + 0.05, fundamental + 0.05, fs_hz=self.FS, f0_hz=60.0,
        )
        self.assertIsNone(valor)
        self.assertTrue(motivo)
        # capturado só com a fundamental (sem distúrbio) e formas incompatíveis
        esperado, _ = self._09(60.0)
        valor, motivo = sinais.correlacao_disturbio_fundamental_ajustada(
            esperado, fundamental, fs_hz=self.FS, f0_hz=60.0,
        )
        self.assertIsNone(valor)
        self.assertTrue(motivo)
        valor, motivo = sinais.correlacao_disturbio_fundamental_ajustada(
            esperado, esperado[:-1], fs_hz=self.FS, f0_hz=60.0,
        )
        self.assertIsNone(valor)
        self.assertIn("incompat", motivo)

    def _sessao_09_com_fundamental_1_pct_maior(self):
        import analisar_sessao
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "metadata").mkdir()
        voltage, p = self._09(60.0)
        md = {"classe": "OSCILLATORY_TRANSIENT", "fs_hz": self.FS, "id_captura": "09-0001", "f0_hz": 60.0,
              "parametros": {}, "pontos": 6000, "seed": 5, "simulado": False, "nivel_indice": 0,
              "sorteio_posicao": True, "fase_graus": p["fase_graus"], "tensao_base_rms": 127.0}
        esperado = analisar_sessao._reconstruir_esperado("09", md)
        np.testing.assert_allclose(esperado, voltage, atol=1e-12)
        fundamental = np.sin(2 * np.pi * 60.0 * (self.T + p["fase_graus"] / (360.0 * 60.0)))
        np.savez(
            tmp / "09_oscillatory_transient_cap01.npz", tempo_ms=self.T * 1000.0,
            tensao_pu=(esperado + 0.01 * fundamental).reshape(1, -1), classe="OSCILLATORY_TRANSIENT",
            id_captura=np.array(["09-0001"], dtype=object),
        )
        (tmp / "metadata" / "09_oscillatory_transient.jsonl").write_text(json.dumps(md) + "\n", encoding="utf-8")
        return tmp, md, esperado, esperado + 0.01 * fundamental

    def test_analisar_sessao_expoe_a_correlacao_com_a_fundamental_ajustada(self):
        import io
        import analisar_sessao
        tmp, _, _, _ = self._sessao_09_com_fundamental_1_pct_maior()
        relatorio = analisar_sessao.analisar_sessao(tmp)
        linha = relatorio[0]
        self.assertGreater(linha["correlacao_disturbio_fundamental_ajustada"], 0.9999)
        self.assertLess(linha["correlacao_disturbio"], 0.99)
        self.assertIsNone(linha["correlacao_disturbio_fundamental_ajustada_motivo"])
        with mock.patch("sys.stdout", new_callable=io.StringIO) as saida:
            self.assertEqual(analisar_sessao.main([str(tmp)]), 0)
        self.assertIn("fund.aj.", saida.getvalue())
        self.assertIn("1.000", saida.getvalue())

    def test_html_mostra_a_correlacao_com_a_fundamental_ajustada(self):
        import relatorio_html
        _, md, esperado, medida = self._sessao_09_com_fundamental_1_pct_maior()
        captura = relatorio_html.Captura(
            arquivo=Path("09_oscillatory_transient_cap01.npz"), linha=0, id_captura="09-0001", classe="OSCILLATORY_TRANSIENT",
            sinal=medida, fs_hz=self.FS, f0_hz=60.0, metadado=md, inicio_nominal=0, pontos_nominais=6000,
            recorte={"origem": "teste"},
        )
        correlacoes = relatorio_html._correlacoes(captura, esperado)
        self.assertGreater(correlacoes["disturbio_fund_ajustada"], 0.9999)
        self.assertLess(correlacoes["disturbio"], 0.99)
        captura.correlacoes = correlacoes
        self.assertIn("fundamental ajustada 1.000", relatorio_html.tabela_metadados(captura))

    # -- 09 nas ferramentas da cópia em 100 ms -----------------------------

    def _sessao_09_sorteada(self, f0, seed, hipotese):
        import gerar_tres_versoes as gtv
        import modelo_lista_fonte as modelo
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "metadata").mkdir()
        (tmp / "tres_versoes").mkdir()
        registro = {
            "id_captura": "09-0001", "classe": "OSCILLATORY_TRANSIENT", "pontos": 6000, "fs_hz": self.FS, "f0_hz": f0,
            "tensao_base_rms": 127.0, "inicio_janela": 600, "seed": seed, "parametros": {}, "nivel_indice": 0,
            "sorteio_posicao": True, "perfil": "literatura",
            "tres_versoes": {"arquivo": "tres_versoes/09_osc.npz", "programada": "TRACe+LIST"},
        }
        versoes = gtv.reconstruir_versoes(registro)
        programacao = AmetekMX30.montar_programacao(versoes["forma_bancada"], base_voltage_rms=127.0, frequency_hz=f0)
        self.assertIn("TRACe", versoes["origem"])
        if hipotese:
            medida = modelo.prever_forma(programacao, hipotese[0], **hipotese[1])
        else:
            medida = programacao.programada_pu()
        (tmp / "metadata" / "09_osc.jsonl").write_text(json.dumps(registro) + "\n", encoding="utf-8")
        np.savez(  # formato 1: o registro inteiro na raiz (a janela começa em inicio_janela = 600)
            tmp / "09_osc.npz", classe="OSCILLATORY_TRANSIENT", id_captura=np.array(["09-0001"], dtype=object),
            tempo_ms=np.arange(600 + 6000) / 30.0, tensao_pu=np.concatenate([np.zeros(600), medida])[np.newaxis, :],
        )
        np.savez(
            tmp / "tres_versoes" / "09_osc.npz", classe="OSCILLATORY_TRANSIENT", id_captura=np.array(["09-0001"], dtype=object),
            tempo_ms=np.arange(6000) / 30.0, modelo_pu=versoes["modelo"][np.newaxis, :], medida_pu=medida[np.newaxis, :],
            programada_pu=programacao.programada_pu()[np.newaxis, :], inicio_janela=np.array(600),
            origem_programada=np.array(versoes["origem"]),
        )
        return tmp, programacao, medida

    def test_ferramentas_da_copia_em_100ms_rodam_numa_09_sorteada_e_acusam_a_copia(self):
        import modelo_lista_fonte as modelo
        script = _carregar_script("diag_ciclos_trace")
        copia = ("copia_no_instante", {"t_s": 0.100, "ganho": 0.5, "modo": "somar"})
        hipoteses = {"ideal": ("ideal", {}), "copia_de_meio_ganho_em_100ms": copia}
        for f0 in (50.0, 60.0):
            for seed in (3, 11):
                sessao, programacao, medida = self._sessao_09_sorteada(f0, seed, copia)
                capturas = script.carregar_sessao(sessao, classes=["09"], usar_forma_bancada=True)
                self.assertEqual(len(capturas), 1)
                self.assertIsNotNone(capturas[0].forma_bancada_pu)  # reconstruída do metadata sorteado
                r = script.analisar_captura(capturas[0])
                self.assertGreater(r["residuo_no_instante"]["max_abs_pu"], 0.1)
                self.assertAlmostEqual(r["residuo_no_instante"]["instante_ms"], 100.0, delta=2.5)
                ranking = modelo.confrontar(programacao, medida, hipoteses)
                self.assertEqual(ranking[0]["nome"], "copia_de_meio_ganho_em_100ms")
                self.assertLess(ranking[0]["rms_residuo_pu"], 1e-9)
                self.assertGreater(ranking[1]["rms_residuo_pu"], 0.01)
                # controle: sem a cópia, nada é acusado
                sessao, programacao, medida = self._sessao_09_sorteada(f0, seed, None)
                r = script.analisar_captura(script.carregar_sessao(sessao, classes=["09"], usar_forma_bancada=True)[0])
                self.assertIsNone(r["troca"])
                self.assertLess(r["residuo_no_instante"]["max_abs_pu"], 1e-6)

    # -- 06: o que a TRACE por ciclo não reproduz ---------------------------

    def test_06_a_perda_na_trace_e_so_a_media_por_ciclo_que_a_fonte_remove(self):
        experimento = _load_experimento("06")
        piores = []
        for f0 in (50.0, 60.0):
            n = int(round(self.FS / f0))
            for seed in range(12):
                voltage, p = experimento.gerar(self.T, f0, seed % 3, np.random.default_rng(seed))
                programada = AmetekMX30.montar_programacao(voltage, base_voltage_rms=127.0, frequency_hz=f0).programada_pu()
                ciclos = voltage.reshape(-1, n)
                sem_media = (ciclos - ciclos.mean(axis=1, keepdims=True)).reshape(-1)
                completo, _ = sinais.correlacao_disturbio(
                    voltage, programada, fs_hz=self.FS, f0_hz=f0, fase_graus=p["fase_graus"],
                )
                sem_dc, _ = sinais.correlacao_disturbio(
                    sem_media, programada, fs_hz=self.FS, f0_hz=f0, fase_graus=p["fase_graus"],
                )
                self.assertGreater(sem_dc, 0.999)          # a TRACE reproduz o modelo sem a média de cada ciclo
                self.assertLessEqual(completo, sem_dc + 1e-9)
                piores.append((completo, p["flicker_hz"]))
        piores.sort()
        self.assertLess(piores[0][0], 0.95)                # a perda existe (flicker alto)
        self.assertGreater(piores[0][1], 17.0)             # e cresce com a frequência do flicker




def _capturas_gravadas(pasta, classe_id, *, versoes=("medida",), perfis=None):
    """Capturas de uma classe numa pasta de sessão, em qualquer formato
    (``sessao_io.ler_pasta``): o que os testes antigos contavam como arquivos."""
    import sessao_io
    return sessao_io.ler_pasta(Path(pasta), versoes=versoes, classes=[classe_id], perfis=perfis)

class NpzPorClasseTests(unittest.TestCase):
    """Formato 2 (``logica/sessao_io.py``, ``docs/dataset.md``): UM ``NN_classe.npz``
    comprimido por classe e sessão, com ``<perfil>/<versão>`` de todos os
    perfis (``set perfil todos``); SNRs fora dele, em ``snr_XXdb/NN_classe.npz``."""

    PERFIS = ("norma", "literatura", "fronteira")
    ITENS = ("medida", "modelo", "programada")

    def setUp(self):
        import sessao_io
        self.sessao_io = sessao_io
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # As classes falsas "96" destes testes dependem do perfil (como as reais
        # 02/05/10...); a "97" de PerfisCompartilhadosTests não.
        import perfis
        patcher = mock.patch.dict(perfis.COMPONENTES_POR_CLASSE, {"96": ("sag_niveis",)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _config(self, pasta, **sobrescritas):
        base = dict(
            fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(20.0, 30.0), base_seed=7,
            capture_current=False, current_base_a=None, results_dir=pasta,
            sim_captures_per_class=3, real_captures_per_class=1, disturbance_start_s=0.06,
        )
        base.update(sobrescritas)
        return mestre.Config(**base)

    def _scripts(self, *ids):
        return [s for s in mestre._experiment_scripts() if s.stem in ids]

    def _sessao_simulada_todos(self, pasta, *ids):
        config = self._config(pasta)
        bancada = mestre.Bancada(None, None, config)
        with mock.patch.object(mestre, "PERFIL_TODOS", True):
            resultados = bancada.executar_bateria(self._scripts(*ids))
        self.assertTrue(all(r.ok for r in resultados), resultados)
        return config

    # -- escrita ------------------------------------------------------------

    def test_set_perfil_todos_grava_um_npz_por_classe_com_as_nove_chaves(self):
        config = self._sessao_simulada_todos(self.tmp / "r", "02", "05")
        pasta = config.results_dir
        self.assertEqual(sorted(p.name for p in pasta.glob("*.npz")), ["02_sag.npz", "05_harmonics.npz"])
        for nome in ("02_sag.npz", "05_harmonics.npz"):
            with np.load(pasta / nome) as dados:  # sem pickle: nada de object
                for perfil in self.PERFIS:
                    for item in self.ITENS:
                        self.assertIn(f"{perfil}/{item}", dados.files)
                    self.assertEqual(dados[f"{perfil}/medida"].shape, (3, 6000))
                    self.assertEqual(dados[f"{perfil}/modelo"].shape, (3, 6000))
                    self.assertEqual(dados[f"{perfil}/programada"].shape, (3, 6000))
                    self.assertEqual(list(dados[f"{perfil}/id_captura"]), ["%s-%04d" % (nome[:2], i) for i in (1, 2, 3)])
                self.assertEqual(list(dados["perfis"]), list(self.PERFIS))
                self.assertEqual(int(dados["formato_npz"]), 2)
                self.assertNotIn("tensao_pu", dados.files)
                # SNR NÃO está no arquivo da classe
                self.assertFalse([k for k in dados.files if "snr" in k.lower()])
                self.assertEqual(dados["literatura/medida"].dtype, np.float64)
        # SNRs em arquivos por classe e nível
        for nivel in (20, 30):
            self.assertEqual(sorted(p.name for p in (pasta / f"snr_{nivel}db").glob("*.npz")), ["02_sag.npz", "05_harmonics.npz"])
            with np.load(pasta / f"snr_{nivel}db" / "02_sag.npz") as dados:
                self.assertEqual(dados["norma/tensao_pu"].shape, (3, 6000))
                self.assertEqual(list(dados["perfis"]), list(self.PERFIS))
        # Nada de sobra: nem .part, nem spool, nem pasta tres_versoes/
        self.assertEqual(list(pasta.rglob("*.part")), [])
        self.assertFalse((pasta / "parcial").exists())
        self.assertFalse((pasta / "tres_versoes").exists())
        # metadata: 9 linhas por classe (3 perfis x 3 capturas), com o índice de cada uma
        linhas = [json.loads(l) for l in (pasta / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(linhas), 9)
        self.assertEqual([l["perfil"] for l in linhas], [p for p in self.PERFIS for _ in range(3)])
        self.assertEqual([l["indice_no_arquivo"] for l in linhas], [0, 1, 2] * 3)
        self.assertEqual({l["arquivo_classe"] for l in linhas}, {"02_sag.npz"})
        # sessao.json avisa o formato
        info = json.loads((pasta / "sessao.json").read_text(encoding="utf-8"))
        self.assertEqual(info["formato_npz"], 2)
        self.assertEqual(info["perfis_da_rodada"], list(self.PERFIS))

    def test_arrays_sao_identicos_aos_de_uma_rodada_de_um_perfil_so(self):
        """Compressão sem perda e dtypes preservados: cada bloco do arquivo de
        `todos` é igual, bit a bit (valores e dtype), ao que uma rodada só
        daquele perfil grava; e no simulado `medida` é a série do dataset
        (= `modelo`)."""
        todos = self._sessao_simulada_todos(self.tmp / "todos", "02", "10").results_dir
        for perfil in self.PERFIS:
            config = self._config(self.tmp / f"so_{perfil}", perfil=perfil)
            mestre.Bancada(None, None, config).executar_bateria(self._scripts("02", "10"))
            for nome in ("02_sag.npz", "10_sag_harmonics.npz"):
                with np.load(todos / nome) as a, np.load(config.results_dir / nome) as b:
                    for item in self.ITENS:
                        self.assertEqual(a[f"{perfil}/{item}"].dtype, b[f"{perfil}/{item}"].dtype)
                        np.testing.assert_array_equal(a[f"{perfil}/{item}"], b[f"{perfil}/{item}"])
                    np.testing.assert_array_equal(a[f"{perfil}/medida"], a[f"{perfil}/modelo"])
                    np.testing.assert_array_equal(a["tempo_ms"], b["tempo_ms"])
                with np.load(todos / "snr_20db" / nome) as a, np.load(config.results_dir / "snr_20db" / nome) as b:
                    np.testing.assert_array_equal(a[f"{perfil}/tensao_pu"], b[f"{perfil}/tensao_pu"])

    def test_perfil_unico_continua_gravando_so_o_perfil_da_config(self):
        config = self._config(self.tmp / "r", perfil="fronteira")
        mestre.Bancada(None, None, config).executar_bateria(self._scripts("02"))
        with np.load(config.results_dir / "02_sag.npz") as dados:
            self.assertEqual(list(dados["perfis"]), ["fronteira"])
            self.assertEqual([k for k in dados.files if "/" in k and not k.startswith("fronteira/")], [])

    def test_perfis_rodam_em_ordem_e_a_falha_de_um_nao_apaga_os_outros(self):
        executadas = []

        class _Classe(mestre.ExperimentoWaveform):
            id = "96"
            nome = "TESTE_PERFIS"

            def gerar(self, t, f0, capture_index, rng):
                executadas.append(self.config.perfil)
                if self.config.perfil == "literatura":
                    raise RuntimeError("falha de experimento no perfil literatura")
                return np.sin(2.0 * np.pi * f0 * t), {}

        config = self._config(self.tmp / "r", snr_levels_db=(), sim_captures_per_class=2)
        bancada = mestre.Bancada(None, None, config)
        with mock.patch.object(mestre, "PERFIL_TODOS", True), \
                mock.patch.object(mestre.Bancada, "_carregar_classe_experimento", staticmethod(lambda p: _Classe)), \
                mock.patch.object(mestre.Bancada, "recuperar_estado_seguro", lambda self: None):
            resultados = bancada.executar_bateria([Path("96.py")])
        self.assertFalse(resultados[0].ok)
        self.assertIn("perfil literatura", resultados[0].motivo)
        self.assertEqual(sorted(set(executadas)), ["fronteira", "literatura", "norma"])
        self.assertEqual(executadas[0], "norma")
        with np.load(config.results_dir / "96_teste_perfis.npz") as dados:
            self.assertEqual(list(dados["perfis"]), ["norma", "fronteira"])
        self.assertEqual(bancada.config.perfil, config.perfil)  # a Bancada volta ao perfil de antes

    # -- bancada: resiliência -------------------------------------------------

    def _classe_fisica(self, falhar_na_chamada=None):
        chamadas = {"n": 0}

        class _Classe(mestre.ExperimentoNativo):
            id = "96"
            nome = "TESTE_INTERROMPIDA"

            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}

            def configurar(self, capture_index):
                return {}

            @staticmethod
            def _calcular_margem(*, captura_fisica, config_points, fs_hz):
                return 0, 0, config_points

            def _preparar_acquisicao_real(self):
                pass

            def _capturar_real(self, capture_index, t, rng):
                chamadas["n"] += 1
                if falhar_na_chamada is not None and chamadas["n"] == falhar_na_chamada:
                    raise CommunicationError("serial caiu (teste)")
                return t, np.sin(2.0 * np.pi * 60.0 * t) + 0.001 * chamadas["n"], None, {}

        return _Classe, chamadas

    def _bancada_fisica(self, config):
        fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=425.0)
        return mestre.Bancada(fonte, mock.Mock(), config)

    def test_bancada_com_todos_os_perfis_acumula_no_mesmo_arquivo(self):
        classe, _ = self._classe_fisica()
        config = self._config(self.tmp / "r", snr_levels_db=(30.0,), capturas_override=2)
        bancada = self._bancada_fisica(config)
        with mock.patch.object(mestre.Bancada, "_carregar_classe_experimento", staticmethod(lambda p: classe)):
            resultados = bancada.executar_bateria([Path("96.py")], ("norma", "literatura", "fronteira"))
        self.assertTrue(resultados[0].ok)
        pasta = config.results_dir
        self.assertEqual(sorted(p.name for p in pasta.glob("*.npz")), ["96_teste_interrompida.npz"])
        with np.load(pasta / "96_teste_interrompida.npz") as dados:
            for perfil in self.PERFIS:
                self.assertEqual(dados[f"{perfil}/medida"].shape, (2, 6000))
        self.assertFalse((pasta / "parcial").exists())
        self.assertEqual(list(pasta.rglob("*.part")), [])
        linhas = [json.loads(l) for l in (pasta / "metadata" / "96_teste_interrompida.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([l["perfil"] for l in linhas], [p for p in self.PERFIS for _ in range(2)])

    def test_interrupcao_no_meio_do_segundo_perfil_preserva_tudo_o_que_ja_foi_capturado(self):
        classe, _ = self._classe_fisica(falhar_na_chamada=4)  # 2 de norma + 1 de literatura + falha
        config = self._config(self.tmp / "r", snr_levels_db=(30.0,), capturas_override=2)
        bancada = self._bancada_fisica(config)
        with mock.patch.object(mestre.Bancada, "_carregar_classe_experimento", staticmethod(lambda p: classe)), \
                self.assertRaises(CommunicationError):
            bancada.executar_bateria([Path("96.py")], ("norma", "literatura", "fronteira"))
        pasta = config.results_dir
        with np.load(pasta / "96_teste_interrompida.npz") as dados:
            self.assertEqual(list(dados["perfis"]), ["norma", "literatura"])
            self.assertEqual(dados["norma/medida"].shape, (2, 6000))
            self.assertEqual(dados["literatura/medida"].shape, (1, 6000))
        with np.load(pasta / "snr_30db" / "96_teste_interrompida.npz") as dados:
            self.assertEqual(dados["literatura/tensao_pu"].shape, (1, 6000))
        linhas = (pasta / "metadata" / "96_teste_interrompida.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(linhas), 3)
        self.assertFalse((pasta / "parcial").exists())
        self.assertEqual(list(pasta.rglob("*.part")), [])

    def test_morte_do_processo_deixa_o_spool_e_recuperar_parcial_promove_sem_perder_perfis(self):
        pasta = self.tmp / "r"
        io = self.sessao_io
        t = np.arange(6000) / 30_000.0

        def captura(arquivo, perfil, n, valor):
            md = {"id_captura": f"96-{n:04d}", "classe": "X", "perfil": perfil, "pontos": 6000, "fs_hz": 30_000.0}
            arquivo.adicionar(
                perfil, id_captura=md["id_captura"], medida=np.full(6000, valor), tempo_ms=t * 1000.0, fs_hz=30_000.0,
                modelo=np.full(6000, valor + 1), snr={30.0: np.full(6000, valor + 2)}, metadado=md,
            )

        a = io.ArquivoDaClasse(pasta, "96", "TESTE")
        a.iniciar_perfil("norma")
        captura(a, "norma", 1, 1.0)
        captura(a, "norma", 2, 2.0)
        a.consolidar()
        a.encerrar_perfil("norma")
        a.iniciar_perfil("literatura")
        captura(a, "literatura", 1, 3.0)  # o processo morre aqui: sem consolidar
        self.assertEqual(len(list((pasta / "parcial" / "96_teste").glob("*.npz"))), 1)
        a.close()  # Simula o lease liberado pelo SO ao morrer o escritor.
        recuperados = io.recuperar_parcial(pasta)
        self.assertEqual(recuperados, [pasta / "96_teste.npz"])
        with np.load(pasta / "96_teste.npz") as dados:
            self.assertEqual(sorted(str(p) for p in dados["perfis"]), ["literatura", "norma"])
            np.testing.assert_array_equal(dados["norma/medida"][1], np.full(6000, 2.0))
            np.testing.assert_array_equal(dados["literatura/medida"][0], np.full(6000, 3.0))
            self.assertEqual(str(dados["classe"]), "TESTE")
        with np.load(pasta / "snr_30db" / "96_teste.npz") as dados:
            np.testing.assert_array_equal(dados["norma/tensao_pu"][0], np.full(6000, 3.0))
            np.testing.assert_array_equal(dados["literatura/tensao_pu"][0], np.full(6000, 5.0))
        self.assertFalse((pasta / "parcial").exists())

    # -- leitura --------------------------------------------------------------

    def test_leitura_devolve_exatamente_os_arrays_gravados_com_o_metadata_do_perfil_certo(self):
        pasta = self._sessao_simulada_todos(self.tmp / "r", "02").results_dir
        capturas = self.sessao_io.ler_capturas(pasta, versoes=self.ITENS)
        self.assertEqual(len(capturas), 9)
        with np.load(pasta / "02_sag.npz") as dados:
            for c in capturas:
                self.assertEqual(c.formato, "classe")
                for item in self.ITENS:
                    np.testing.assert_array_equal(c.versoes[item], dados[f"{c.perfil}/{item}"][c.linha])
                self.assertEqual(c.metadado["perfil"], c.perfil)  # o mesmo id existe nos 3 perfis
                self.assertEqual(c.metadado["id_captura"], c.id_captura)
                self.assertEqual(c.metadado["indice_no_arquivo"], c.linha)
        self.assertEqual(len({c.id_captura for c in capturas}), 3)
        # filtros
        so_norma = self.sessao_io.ler_capturas(pasta, perfis=["norma"])
        self.assertEqual({c.perfil for c in so_norma}, {"norma"})
        self.assertEqual([c.id_captura for c in self.sessao_io.ler_capturas(pasta, capturas="02-0002")], ["02-0002"] * 3)
        self.assertEqual([c.linha for c in self.sessao_io.ler_capturas(pasta, perfis=["fronteira"], capturas="1,3")], [0, 2])
        self.assertEqual([c.linha for c in self.sessao_io.ler_capturas(pasta, perfis=["fronteira"], capturas="2-3")], [1, 2])
        snr = self.sessao_io.ler_capturas(pasta, subpasta="snr_20db", perfis=["norma"])
        self.assertEqual([c.sinal.size for c in snr], [6000] * 3)
        with self.assertRaises(ValueError):
            self.sessao_io.parsear_selecao_capturas("abc")

    def _sessao_antiga(self, pasta):
        """Um .npz por captura + tres_versoes/ (o formato até a v1.15 sem tag)."""
        (pasta / "metadata").mkdir(parents=True)
        (pasta / "tres_versoes").mkdir()
        (pasta / "snr_30db").mkdir()
        registro = np.concatenate([np.zeros(600), np.sin(2.0 * np.pi * 60.0 * np.arange(6000) / 30000.0), np.zeros(1500)])
        modelo = np.sin(2.0 * np.pi * 60.0 * np.arange(6000) / 30000.0)
        np.savez(pasta / "02_sag_sag_pu-0.1.npz", classe="SAG", id_captura=np.array(["02-0001"], dtype=object),
                 tempo_ms=np.arange(8100) / 30.0, tensao_pu=registro[np.newaxis, :])
        np.savez(pasta / "snr_30db" / "02_sag_sag_pu-0.1.npz", classe="SAG", id_captura=np.array(["02-0001"], dtype=object),
                 tempo_ms=np.arange(6000) / 30.0, tensao_pu=(modelo + 0.01)[np.newaxis, :])
        np.savez(pasta / "tres_versoes" / "02_sag_sag_pu-0.1.npz", classe="SAG", id_captura=np.array(["02-0001"], dtype=object),
                 tempo_ms=np.arange(6000) / 30.0, modelo_pu=modelo[np.newaxis, :], programada_pu=(0.9 * modelo)[np.newaxis, :],
                 medida_pu=modelo[np.newaxis, :], inicio_janela=np.array(600), origem_programada=np.array("PULSe"))
        # simulado antigo: um .npz por classe, N linhas
        np.savez(pasta / "01_normal.npz", classe="NORMAL", id_captura=np.array(["01-0001", "01-0002"], dtype=object),
                 tempo_ms=np.arange(6000) / 30.0, tensao_pu=np.vstack([modelo, 2 * modelo]))
        base = {"classe": "SAG", "seed": 1, "fs_hz": 30_000.0, "pontos": 6000, "parametros": {"sag_pu": 0.1},
                "nivel_indice": 0, "f0_hz": 60.0, "tensao_base_rms": 127.0}
        (pasta / "metadata" / "02_sag.jsonl").write_text(json.dumps({
            **base, "id_captura": "02-0001", "simulado": False, "pre_trigger_s": 0.0, "margem_amostras_antes": 600,
            "margem_amostras_depois": 1500, "amostras_totais": 8100, "inicio_janela": 600,
        }) + "\n", encoding="utf-8")
        (pasta / "metadata" / "01_normal.jsonl").write_text(
            "".join(json.dumps({**base, "classe": "NORMAL", "id_captura": f"01-000{i}", "simulado": True}) + "\n" for i in (1, 2)),
            encoding="utf-8")
        return registro, modelo

    def test_sessao_antiga_continua_legivel_com_as_tres_versoes_e_o_perfil_legado(self):
        pasta = self.tmp / "antiga"
        registro, modelo = self._sessao_antiga(pasta)
        capturas = self.sessao_io.ler_capturas(pasta, versoes=self.ITENS, classes=["02"])
        self.assertEqual(len(capturas), 1)
        c = capturas[0]
        self.assertEqual((c.formato, c.perfil, c.id_captura, c.inicio_janela), ("por_captura", "literatura", "02-0001", 600))
        np.testing.assert_array_equal(c.versoes["medida"], registro)
        np.testing.assert_array_equal(c.versoes["modelo"], modelo)
        np.testing.assert_allclose(c.versoes["programada"], 0.9 * modelo)
        self.assertEqual(c.origem_programada, "PULSe")
        sim = self.sessao_io.ler_capturas(pasta, classes=["01"])
        self.assertEqual([(x.formato, x.id_captura) for x in sim], [("empilhado", "01-0001"), ("empilhado", "01-0002")])
        snr = self.sessao_io.ler_capturas(pasta, subpasta="snr_30db")
        np.testing.assert_allclose(snr[0].sinal, modelo + 0.01)

    def test_formato_do_arquivo_distingue_os_dois(self):
        pasta = self.tmp / "antiga"
        self._sessao_antiga(pasta)
        self.assertEqual(self.sessao_io.formato_do_arquivo(pasta / "02_sag_sag_pu-0.1.npz"), "legado")
        nova = self._sessao_simulada_todos(self.tmp / "nova", "02").results_dir
        self.assertEqual(self.sessao_io.formato_do_arquivo(nova / "02_sag.npz"), "classe")

    # -- consumidores -----------------------------------------------------------

    def test_recortar_margem_le_os_dois_formatos_e_grava_o_formato_2(self):
        import recortar_margem
        pasta = self.tmp / "antiga"
        registro, modelo = self._sessao_antiga(pasta)
        saida = self.tmp / "sem_margem"
        recortar_margem.recortar_sessao(pasta, saida)
        with np.load(saida / "02_sag.npz") as dados:
            np.testing.assert_array_equal(dados["literatura/medida"][0], registro[600:6600])
            np.testing.assert_array_equal(dados["literatura/modelo"][0], modelo)
            np.testing.assert_allclose(dados["literatura/programada"][0], 0.9 * modelo)
            self.assertEqual(list(dados["literatura/inicio_janela"]), [0])
        with np.load(saida / "snr_30db" / "02_sag.npz") as dados:
            np.testing.assert_allclose(dados["literatura/tensao_pu"][0], modelo + 0.01)
        # formato 2 -> recorte -> mesmas capturas, todos os perfis
        nova = self._sessao_simulada_todos(self.tmp / "nova", "02").results_dir
        recortar_margem.recortar_sessao(nova, self.tmp / "nova_sem_margem")
        with np.load(nova / "02_sag.npz") as a, np.load(self.tmp / "nova_sem_margem" / "02_sag.npz") as b:
            for perfil in self.PERFIS:
                np.testing.assert_array_equal(a[f"{perfil}/medida"], b[f"{perfil}/medida"])
                np.testing.assert_array_equal(a[f"{perfil}/programada"], b[f"{perfil}/programada"])
        linhas = (self.tmp / "nova_sem_margem" / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(linhas), 9)

    def test_analisar_sessao_le_o_formato_2_e_acusa_o_simulado_uma_vez_por_perfil(self):
        import analisar_sessao
        pasta = self._sessao_simulada_todos(self.tmp / "nova", "02").results_dir
        relatorio = analisar_sessao.analisar_sessao(pasta)
        self.assertEqual(len(relatorio), 3)
        self.assertEqual({l["classe"] for l in relatorio}, {f"02_sag:{p}" for p in self.PERFIS})
        self.assertTrue(all("erro" in l for l in relatorio))
        # bancada: uma linha por captura de cada perfil (id repetido entre perfis)
        classe, _ = self._classe_fisica()
        config = self._config(self.tmp / "fisica", snr_levels_db=(), capturas_override=1)
        bancada = self._bancada_fisica(config)
        with mock.patch.object(mestre.Bancada, "_carregar_classe_experimento", staticmethod(lambda p: classe)):
            bancada.executar_bateria([Path("96.py")], ("norma", "literatura"))
        with mock.patch.object(analisar_sessao, "_reconstruir_esperado", side_effect=RuntimeError("sem classe 96")):
            relatorio = analisar_sessao.analisar_sessao(config.results_dir)
        self.assertEqual(sorted(l["classe"] for l in relatorio),
                         ["96_teste_interrompida:literatura:96-0001", "96_teste_interrompida:norma:96-0001"])

    def test_html_seleciona_classe_perfil_versao_e_captura(self):
        import relatorio_html
        pasta = self._sessao_simulada_todos(self.tmp / "nova", "02", "05").results_dir
        _, total = relatorio_html.gerar_relatorio(pasta, self.tmp / "tudo.html", dpi=40)
        self.assertEqual(total, 18)  # simulado, 3 capturas por bloco (limite padrão = 3) x 3 perfis x 2 classes
        caminho, total = relatorio_html.gerar_relatorio(
            pasta, self.tmp / "sel.html", classes=["02"], perfis=["norma", "fronteira"],
            versoes=["medida", "programada"], capturas_escolhidas="2-3", dpi=40,
        )
        self.assertEqual(total, 4)
        texto = caminho.read_text(encoding="utf-8")
        self.assertIn("02_sag · norma · 02-0002", texto)
        self.assertIn("02_sag · fronteira · 02-0003", texto)
        self.assertNotIn("literatura ·", texto)
        self.assertNotIn("05_harmonics", texto)
        self.assertNotIn("02-0001", texto)
        self.assertIn("medida, programada", texto)  # versões desenhadas
        _, total = relatorio_html.gerar_relatorio(
            pasta, self.tmp / "id.html", capturas_escolhidas="05-0001", versoes=["modelo"], dpi=40,
        )
        self.assertEqual(total, 3)
        # CLI
        saida = self.tmp / "cli.html"
        relatorio_html.main([str(pasta), "--saida", str(saida), "--classes", "05", "--perfis", "literatura",
                             "--versoes", "modelo,programada", "--capturas", "1", "--dpi", "40"])
        self.assertIn("05_harmonics · literatura · 05-0001", saida.read_text(encoding="utf-8"))
        with self.assertRaises(SystemExit):
            relatorio_html.main([str(pasta), "--versoes", "xyz"])
        with self.assertRaises(SystemExit):
            relatorio_html.main([str(pasta), "--perfis", "inexistente"])

    def test_html_de_sessao_de_bancada_limita_capturas_por_padrao(self):
        import relatorio_html
        classe, _ = self._classe_fisica()
        config = self._config(self.tmp / "fisica", snr_levels_db=(), capturas_override=5)
        bancada = self._bancada_fisica(config)
        with mock.patch.object(mestre.Bancada, "_carregar_classe_experimento", staticmethod(lambda p: classe)):
            bancada.executar_bateria([Path("96.py")], ("norma",))
        _, total = relatorio_html.gerar_relatorio(config.results_dir, self.tmp / "f.html", detalhes=0, dpi=30)
        self.assertEqual(total, 3)

    def test_gerar_ruido_janela_le_o_formato_2_e_grava_snr_por_classe(self):
        gerar = _carregar_script("gerar_ruido_janela")
        pasta = self._sessao_simulada_todos(self.tmp / "nova", "02").results_dir
        saida = self.tmp / "ruido"
        linhas = gerar.gerar_sessao(pasta, saida, (10.0, 25.0))
        self.assertEqual(len(linhas), 9)
        self.assertEqual(sorted(p.name for p in saida.rglob("*.npz")), ["02_sag.npz", "02_sag.npz"])
        with np.load(saida / "snr_10db" / "02_sag.npz") as dados:
            self.assertEqual(list(dados["perfis"]), list(self.PERFIS))
            self.assertEqual(dados["fronteira/tensao_pu"].shape, (3, 6000))
        with np.load(pasta / "02_sag.npz") as limpo, np.load(saida / "snr_25db" / "02_sag.npz") as dados:
            janela = limpo["norma/medida"][1]
            ruido = dados["norma/tensao_pu"][1] - janela
            medido = 10.0 * math.log10(np.mean(janela ** 2) / np.mean(ruido ** 2))
            self.assertAlmostEqual(medido, 25.0, delta=1e-6)

    def test_consumidores_fecham_writers_no_sucesso_e_na_falha(self):
        import recortar_margem
        gerar = _carregar_script("gerar_ruido_janela")
        pasta = self._sessao_simulada_todos(self.tmp / "origem_close", "02").results_dir
        construtor = self.sessao_io.ArquivoDaClasse
        for nome, operacao in (("recorte", recortar_margem.recortar_sessao),
                               ("ruido", gerar.gerar_sessao)):
            for falha in (False, True):
                with self.subTest(utilitario=nome, falha=falha):
                    writers = []

                    def construir(*args, **kwargs):
                        writer = construtor(*args, **kwargs)
                        writers.append(writer)  # Mantém vivo para testar close explícito.
                        if falha:
                            writer.consolidar = mock.Mock(side_effect=RuntimeError("falha de disco"))
                        return writer

                    with mock.patch.object(self.sessao_io, "ArquivoDaClasse", side_effect=construir):
                        saida = self.tmp / f"{nome}_{falha}"
                        if falha:
                            with self.assertRaisesRegex(RuntimeError, "falha de disco"):
                                operacao(pasta, saida)
                        else:
                            operacao(pasta, saida)
                    self.assertTrue(writers)
                    for writer in writers:
                        with self.assertRaisesRegex(RuntimeError, "encerrado"):
                            writer.iniciar_perfil("norma")
                    with self.sessao_io.BloqueioSessao(saida, escritor=False):
                        pass  # O lock é exclusivo mesmo com os writers ainda vivos.

    def test_gerar_tres_versoes_recusa_sessao_do_formato_2(self):
        gerar_tres = _carregar_script("gerar_tres_versoes")
        pasta = self._sessao_simulada_todos(self.tmp / "nova", "02").results_dir
        with self.assertRaises(ValueError) as ctx:
            gerar_tres._nomes_dos_npz(pasta)
        self.assertIn("formato 2", str(ctx.exception))

    # -- CLI -------------------------------------------------------------------

    def _cli(self):
        import cli
        return cli, cli.SessaoCLI()

    def test_set_perfil_todos_na_cli(self):
        import io
        from contextlib import redirect_stdout
        cli, sessao = self._cli()
        with mock.patch.object(mestre, "PERFIL", "norma"), mock.patch.object(mestre, "PERFIL_TODOS", False):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(sessao.cmd_set(["perfil", "todos"]), 0)
            self.assertTrue(mestre.PERFIL_TODOS)
            self.assertEqual(mestre.perfis_da_rodada(), ("norma", "literatura", "fronteira"))
            saida = io.StringIO()
            with redirect_stdout(saida):
                sessao.cmd_status([])
            self.assertIn("perfil de faixas: todos", saida.getvalue())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(sessao.cmd_set(["perfil", "fronteira"]), 0)
            self.assertFalse(mestre.PERFIL_TODOS)
            self.assertEqual(mestre.perfis_da_rodada(), ("fronteira",))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(sessao.cmd_set(["perfil", "xyz"]), 1)
        self.assertIn("set perfil norma|literatura|fronteira|todos", cli.HELP_TEXT)

    def test_resumo_dos_tres_perfis_preserva_contagem_e_recusa_excesso(self):
        import io
        from contextlib import redirect_stdout
        cli, sessao = self._cli()
        sozinhos = 0
        escritas = 0
        import perfis
        independentes = set(perfis.classes_independentes_do_perfil(True))
        with mock.patch.object(mestre, "PERFIL_TODOS", False):
            for perfil in self.PERFIS:
                with mock.patch.object(mestre, "PERFIL", perfil):
                    linhas = cli.SessaoCLI._capturas_das_classes(mestre.scripts_da_bateria_fisica())
                # classe independente do perfil: conta só uma vez (no perfil canônico)
                linhas = [l for l in linhas if l[0] not in independentes or perfil == perfis.PERFIL_CANONICO]
                sozinhos += sum(i["total"] for _, _, i in linhas)
                escritas += sum(i["escritas_trace"] for _, _, i in linhas)
        with mock.patch.object(mestre, "PERFIL_TODOS", True):
            mensagens = []
            with mock.patch.object(sessao, "confirmar", side_effect=lambda aviso, esperado: mensagens.append((aviso, esperado)) or False), \
                    redirect_stdout(io.StringIO()):
                sessao._run_all()
            linhas = cli.SessaoCLI._capturas_das_classes(mestre.scripts_da_bateria_fisica())
        self.assertEqual(sum(i["total"] for _, _, i in linhas), sozinhos)
        self.assertEqual(sum(i["escritas_trace"] for _, _, i in linhas), escritas)
        self.assertTrue(all("por_perfil" in i for _, _, i in linhas))
        self.assertEqual(mensagens, [])  # O orçamento precede confirmação.
        self.assertGreater(escritas, mestre.LIMITE_ESCRITAS_TRACE_CONEXAO)
        aviso = sessao._aviso_escritas_trace(linhas)
        self.assertIn(f"{escritas} gravações", aviso)
        self.assertIn("capturas repetidas evitadas", aviso)

    def test_run_all_com_todos_roda_cada_classe_uma_vez_por_perfil(self):
        cli, sessao = self._cli()
        perfis_vistos = []

        class _Falsa:
            nome = "FALSA"

            def __init__(self, bancada):
                self.perfil = bancada.config.perfil

            def executar(self):
                perfis_vistos.append(self.perfil)

        import io
        from contextlib import redirect_stdout
        with mock.patch.object(mestre, "PERFIL_TODOS", True), \
                mock.patch.object(mestre, "SIMULATED_MODE", True), \
                mock.patch.object(mestre, "SESSION_RESULTS_DIR", self.tmp), \
                mock.patch.object(mestre.Bancada, "_carregar_classe_experimento", staticmethod(lambda p: _Falsa)), \
                mock.patch.object(mestre, "scripts_da_bateria_fisica", lambda: [Path("01.py"), Path("02.py")]), \
                mock.patch.object(sessao, "_garantir_pasta_sessao"), mock.patch.object(sessao, "autorizar_saida"), \
                mock.patch.object(sessao, "_fim_da_sessao"):
            with redirect_stdout(io.StringIO()):
                codigo = sessao._executar_scripts([Path("01.py"), Path("02.py")])
        self.assertEqual(codigo, 0)
        # 01 não depende do perfil: roda uma vez (literatura); 02, nos três
        self.assertEqual(perfis_vistos, ["literatura", "norma", "literatura", "fronteira"])


class SessaoFormatoNovoScriptsTests(unittest.TestCase):
    """Os dois scripts de diagnóstico sobre uma sessão no formato 2 (um
    ``NN_classe.npz`` por classe com ``<perfil>/<versão>``, ``set perfil todos``),
    lida pelo leitor único ``logica/sessao_io.py``; e o ``diag_ciclos_trace``
    sobre o formato 1 sem ``tres_versoes/`` (programada reconstruída pelo
    metadata, como as sessões de 07/10). Sessões sintéticas gravadas com
    ``sessao_io.ArquivoDaClasse``, como a bancada faz."""

    FS = 30_000.0
    MARGEM = 600
    TOTAL = 8100
    PONTOS = 6000

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "verificar_formato2_teste", PROJECT_ROOT / "scripts" / "verificar_sessao_bancada.py",
        )
        cls.v = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.v  # @dataclass com `from __future__ import annotations` exige
        spec.loader.exec_module(cls.v)
        cls.diag = _carregar_script("diag_ciclos_trace")

    def setUp(self):
        import sessao_io
        self.io = sessao_io
        self.tmp = Path(tempfile.mkdtemp(prefix="formato2_scripts_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    # -- sessão sintética no formato 2 -------------------------------------

    def _sessao_formato_2(self, perfis=("norma", "fronteira")):
        """Classe 99 (TRACe: capturas 1 e 2; a 2 tem a cópia de 2 ciclos
        (4 e 5) SÓ no perfil norma) e classe 02 (afundamentos; a 2 tem a
        duração errada SÓ no perfil fronteira). Metadata de cada perfil em
        ``metadata/``, como a bancada grava."""
        pasta = self.tmp / "sessao_formato_2"
        (pasta / "metadata").mkdir(parents=True)
        programada = DiagnosticoCopiaEm100msTests._programacao_com_impulso(50.0, 2400).programada_pu()
        n = 600  # pontos por ciclo a 50 Hz em 30 kHz
        defeito = programada.copy()
        defeito[4 * n : 5 * n] = programada[3 * n : 4 * n]
        defeito[5 * n : 6 * n] = programada[4 * n : 5 * n]
        arq99 = self.io.ArquivoDaClasse(pasta, "99", "SINTETICA", spool=False)
        arq02 = self.io.ArquivoDaClasse(pasta, "02", "SAG", spool=False)
        for perfil in perfis:
            arq99.iniciar_perfil(perfil)
            for numero in (1, 2):
                janela = defeito if (numero == 2 and perfil == "norma") else programada
                id_captura = f"99-{numero:04d}"
                arq99.adicionar(
                    perfil, id_captura=id_captura, medida=np.concatenate([np.zeros(self.MARGEM), janela]),
                    tempo_ms=np.arange(self.MARGEM + self.PONTOS) / self.FS * 1000.0, fs_hz=self.FS,
                    modelo=programada, programada=programada,
                    origem_programada="TRACe+LIST:VOLTage (teste de formato 2)",
                    inicio_janela=self.MARGEM, pontos=self.PONTOS,
                    metadado={
                        "id_captura": id_captura, "classe": "SINTETICA", "perfil": perfil, "pontos": self.PONTOS,
                        "fs_hz": self.FS, "f0_hz": 50.0, "tensao_base_rms": 127.0, "inicio_janela": self.MARGEM,
                        "seed": numero, "parametros": {}, "simulado": False,
                    },
                )
            arq02.iniciar_perfil(perfil)
            for numero, (t0, duracao_real) in enumerate([(0.0476, 0.1032), (0.0300, 0.0400)], start=1):
                id_captura = f"02-{numero:04d}"
                duracao_md = 0.060 if (perfil == "fronteira" and numero == 2) else duracao_real
                x, iw = self._sag(t0, duracao_real)
                pre = int(round(t0 * self.FS))
                janela = x[iw : iw + self.PONTOS]
                arq02.adicionar(
                    perfil, id_captura=id_captura, medida=x, tempo_ms=np.arange(self.TOTAL) / self.FS * 1000.0,
                    fs_hz=self.FS, modelo=janela, programada=janela, origem_programada="",
                    inicio_janela=iw, pontos=self.PONTOS,
                    metadado={
                        "id_captura": id_captura, "classe": "SAG", "perfil": perfil, "pontos": self.PONTOS,
                        "fs_hz": self.FS, "f0_hz": 60.0, "amostras_totais": self.TOTAL,
                        "margem_amostras_antes": self.MARGEM, "pre_trigger_s": t0, "inicio_janela": iw,
                        "indice_trigger": iw + pre, "pre_trigger_desvio_amostras": iw + pre - (pre + self.MARGEM),
                        "inicio_disturbio_s": t0, "duracao_s": duracao_md, "seed": numero,
                        "parametros": {"sag_pu": 0.5}, "simulado": False,
                    },
                )
        for arquivo in (arq99, arq02):
            arquivo.consolidar()
            linhas = [json.dumps(r, ensure_ascii=False) for r in arquivo.registros()]
            (pasta / "metadata" / f"{arquivo.id}_{arquivo.nome.lower()}.jsonl").write_text(
                "\n".join(linhas) + "\n", encoding="utf-8",
            )
        return pasta

    def _sag(self, t0, duracao, nivel=0.5, fase_graus=123.4, desvio=1, f0=60.0):
        """Mesmo sinal de ``VerificadorSessaoBancadaTests._sag`` (sem gravar)."""
        iw = self.MARGEM + desvio
        r = (np.arange(self.TOTAL) - iw) / self.FS
        x = np.sin(2 * np.pi * f0 * r + np.deg2rad(fase_graus))
        x[(r >= t0) & (r < t0 + duracao)] *= nivel
        return x, iw

    # -- diag_ciclos_trace.py ----------------------------------------------

    def test_diag_le_o_formato_2_e_separa_os_perfis(self):
        pasta = self._sessao_formato_2()
        capturas = self.diag.carregar_sessao(pasta, classes=["99"], usar_forma_bancada=False)
        self.assertEqual(
            sorted(c.rotulo for c in capturas),
            ["99-0001 [fronteira]", "99-0001 [norma]", "99-0002 [fronteira]", "99-0002 [norma]"],
        )
        por_rotulo = {c.rotulo: self.diag.analisar_captura(c) for c in capturas}
        self.assertEqual(por_rotulo["99-0002 [norma]"]["troca"]["ciclos_trocados"], [4, 5])
        self.assertIsNone(por_rotulo["99-0002 [fronteira]"]["troca"])
        self.assertIsNone(por_rotulo["99-0001 [norma]"]["troca"])
        self.assertEqual(por_rotulo["99-0002 [norma]"]["perfil"], "norma")
        self.assertEqual(por_rotulo["99-0002 [norma]"]["rotulo"], "99-0002 [norma]")

    def test_diag_com_um_so_perfil_o_rotulo_e_o_id(self):
        pasta = self._sessao_formato_2(perfis=("norma",))
        capturas = self.diag.carregar_sessao(pasta, classes=["99"], usar_forma_bancada=False)
        self.assertEqual([c.rotulo for c in capturas], ["99-0001", "99-0002"])
        self.assertEqual(self.diag.analisar_captura(capturas[1])["troca"]["ciclos_trocados"], [4, 5])

    def test_diag_main_no_formato_2_rotula_por_perfil_e_nao_escreve_na_sessao(self):
        pasta = self._sessao_formato_2()
        antes = sorted(str(p.relative_to(pasta)) for p in pasta.rglob("*"))
        saida = self.tmp / "saida"
        with mock.patch("sys.stdout"):
            codigo = self.diag.main([str(pasta), "--classes", "99", "--sem-forma-bancada", "--saida", str(saida)])
        self.assertEqual(codigo, 0)
        self.assertEqual(sorted(str(p.relative_to(pasta)) for p in pasta.rglob("*")), antes)
        texto = next(saida.glob("diag_ciclos_trace-*.md")).read_text(encoding="utf-8")
        self.assertIn("## 99-0002 [norma]: ciclos que não são simplesmente k", texto)
        self.assertNotIn("## 99-0002 [fronteira]", texto)
        dados = json.loads(next(saida.glob("diag_ciclos_trace-*.json")).read_text(encoding="utf-8"))
        self.assertEqual({(c["perfil"], c["id_captura"]) for c in dados["capturas"]},
                         {("norma", "99-0001"), ("norma", "99-0002"), ("fronteira", "99-0001"), ("fronteira", "99-0002")})

    def test_diag_reconstroi_a_programada_do_formato_1_sem_tres_versoes(self):
        """Sessão de 07/10 sem ``tres_versoes/``: a programada e a forma de
        bancada saem de ``reconstruir_versoes`` (metadata), e a medida é a
        programada (sem defeito), então nenhum ciclo é acusado."""
        import gerar_tres_versoes as gtv
        tmp = self.tmp / "formato_1"
        (tmp / "metadata").mkdir(parents=True)
        registro = {
            "id_captura": "09-0001", "classe": "OSCILLATORY_TRANSIENT", "pontos": 6000, "fs_hz": self.FS, "f0_hz": 50.0,
            "tensao_base_rms": 127.0, "inicio_janela": 600, "seed": 3, "parametros": {}, "nivel_indice": 0,
            "sorteio_posicao": True, "perfil": "literatura",
        }
        versoes = gtv.reconstruir_versoes(registro)
        programacao = AmetekMX30.montar_programacao(versoes["forma_bancada"], base_voltage_rms=127.0, frequency_hz=50.0)
        self.assertIn("TRACe", versoes["origem"])
        (tmp / "metadata" / "09_osc.jsonl").write_text(json.dumps(registro) + "\n", encoding="utf-8")
        np.savez(
            tmp / "09_osc.npz", classe="OSCILLATORY_TRANSIENT", id_captura=np.array(["09-0001"], dtype=object),
            tempo_ms=np.arange(600 + 6000) / 30.0,
            tensao_pu=np.concatenate([np.zeros(600), programacao.programada_pu()])[np.newaxis, :],
        )
        capturas = self.diag.carregar_sessao(tmp, classes=["09"])
        self.assertEqual(len(capturas), 1)
        self.assertEqual(capturas[0].rotulo, "09-0001")
        self.assertIsNotNone(capturas[0].forma_bancada_pu)
        r = self.diag.analisar_captura(capturas[0])
        self.assertIsNone(r["troca"])
        self.assertLess(r["residuo_no_instante"]["max_abs_pu"], 1e-9)

    # -- verificar_sessao_bancada.py ---------------------------------------

    def test_verificador_le_o_formato_2_com_rotulo_por_perfil(self):
        pasta = self._sessao_formato_2()
        capturas = self.v.carregar_sessao(pasta)
        self.assertEqual({c.perfil for c in capturas}, {"norma", "fronteira"})
        resultados = self.v.verificar_capturas(capturas)
        larguras = {r.id_captura: r for r in resultados if r.verificacao == "largura_pulse"}
        self.assertEqual(sorted(larguras), [
            "02-0001 [fronteira]", "02-0001 [norma]", "02-0002 [fronteira]", "02-0002 [norma]",
        ])
        self.assertTrue(larguras["02-0001 [norma]"].ok)
        self.assertTrue(larguras["02-0002 [norma]"].ok)
        # só o perfil fronteira tem a duração errada no metadata: só ele reprova
        self.assertFalse(larguras["02-0002 [fronteira]"].ok)
        self.assertAlmostEqual(larguras["02-0002 [fronteira]"].valor, -20.0, delta=2.0)
        self.assertEqual(len([r for r in resultados if r.verificacao == "pre_trigger"]), 4)

    def test_verificador_com_um_so_perfil_o_rotulo_e_o_id(self):
        pasta = self._sessao_formato_2(perfis=("norma",))
        capturas = self.v.carregar_sessao(pasta)
        self.assertEqual(sorted(c.rotulo for c in capturas if c.classe_id == "02"), ["02-0001", "02-0002"])

    def test_verificador_main_no_formato_2_grava_o_json_com_perfil_e_codigo_1(self):
        pasta = self._sessao_formato_2()
        saida = self.tmp / "verificar.json"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            codigo = self.v.main([str(pasta), "--json", str(saida)])
        self.assertEqual(codigo, 1)  # há uma reprovação (fronteira, 02-0002)
        impresso = buf.getvalue()
        self.assertIn("02-0002 [fronteira]", impresso)
        dados = {(d["id_captura"], d["ok"]) for d in json.loads(saida.read_text(encoding="utf-8"))
                 if d["verificacao"] == "largura_pulse"}
        self.assertIn(("02-0002 [fronteira]", False), dados)
        self.assertIn(("02-0002 [norma]", True), dados)


def _toque_da_fonte(x, fn_hz=10_000.0, zeta=0.2, fs_hz=30_000.0, sobreamostragem=8):
    """Resposta de 2.ª ordem (bilinear) da fonte a uma forma programada: o
    modelo da spec 20/26 (fn 9-11 kHz, zeta 0,1-0,3, medido em 07/10)."""
    xs = np.repeat(np.asarray(x, dtype=np.float64), sobreamostragem)
    c = 2.0 * fs_hz * sobreamostragem
    w = 2.0 * math.pi * fn_hz
    a0 = c * c + 2.0 * zeta * w * c + w * w
    b0 = w * w / a0
    a1 = 2.0 * (w * w - c * c) / a0
    a2 = (c * c - 2.0 * zeta * w * c + w * w) / a0
    y = np.empty_like(xs)
    x1 = x2 = y1 = y2 = xs[0]
    for n in range(xs.size):
        yn = b0 * (xs[n] + 2.0 * x1 + x2) - a1 * y1 - a2 * y2
        y[n] = yn
        x2, x1, y2, y1 = x1, xs[n], y1, yn
    return y.reshape(-1, sobreamostragem).mean(axis=1)


class CristaComFatorDeExtremoTests(unittest.TestCase):
    """Spec 26 (v1.15): a crista esperada da validação física usa o fator de
    extremo calibrado da classe; aceita [modelo x (1-tol), modelo x fator x (1+tol)]."""

    T = np.arange(6000, dtype=np.float64) / 30_000.0

    def _experimento_07(self, f0=60.0):
        import dataclasses
        e = _load_experimento("07")
        e.config = dataclasses.replace(e.config, grid_frequency_hz=f0, base_voltage_rms=127.0)
        return e

    def _validar(self, e, fatores, indice=0, toque=True):
        seed = e.seed_da_captura(indice)
        forma, _ = e.forma_e_parametros_para_bancada(indice, self.T, seed)
        e._forma_programada_pu = forma
        medido = _toque_da_fonte(forma) if toque else forma
        with mock.patch.object(type(e), "_fatores_extremo", lambda self: fatores):
            return e._validar_fisicamente(indice, self.T, seed, medido, margem_antes=0)

    def test_07_com_entalhes_e_toque_passa_com_fator_que_cobre_e_reprova_com_1(self):
        e = self._experimento_07()
        for indice in range(3):
            coberto = self._validar(e, {"07": 1.5}, indice)
            self.assertTrue(coberto["ok"], coberto["motivos"])
            self.assertEqual(coberto["fator_extremo_crista"], 1.5)
            self.assertGreater(coberto["crista_medida"], coberto["crista_modelo"] * 1.25)
            nu = self._validar(e, {"07": 1.0}, indice)
            self.assertFalse(nu["ok"])
            self.assertTrue(any("fator de crista" in m for m in nu["motivos"]), nu["motivos"])

    def test_sem_toque_o_fator_nao_muda_o_veredito_e_o_limite_inferior_continua(self):
        e = self._experimento_07()
        for fator in (1.0, 1.186, 1.5):
            r = self._validar(e, {"07": fator}, toque=False)
            self.assertTrue(r["ok"], (fator, r["motivos"]))
            self.assertAlmostEqual(r["crista_minima_aceita"], r["crista_modelo"] * 0.9)
            self.assertAlmostEqual(r["crista_maxima_aceita"], r["crista_modelo"] * fator * 1.1)

    def test_comparar_fisicamente_bilateral_com_fator(self):
        base = np.sin(2.0 * np.pi * 60.0 * self.T)

        def com_pico(escala):
            x = base.copy()
            x[125::500] = escala  # pico de cada ciclo (500 amostras por ciclo)
            return x

        kw = dict(fs_hz=30_000.0, f0=60.0)
        r = sinais.comparar_fisicamente(base, com_pico(1.2), **kw, fator_crista=1.3)
        self.assertTrue(r["ok"], r["motivos"])
        self.assertTrue(sinais.comparar_fisicamente(base, base, **kw, fator_crista=1.3)["ok"])
        # acima de crista x fator x 1,1 continua reprovada
        cima = sinais.comparar_fisicamente(base, com_pico(1.3 * 1.1 * 1.05), **kw, fator_crista=1.3)
        self.assertFalse(cima["ok"])
        self.assertTrue(any("fator de crista" in m for m in cima["motivos"]))
        # abaixo da crista ideal x 0,9 (pico achatado) reprova mesmo com fator
        achatado = np.clip(base, -0.8, 0.8)
        self.assertFalse(sinais.comparar_fisicamente(base, achatado, **kw, fator_crista=1.3)["ok"])
        # fator 1,0 == comparação simétrica de antes
        r1 = sinais.comparar_fisicamente(base, com_pico(1.2), **kw)
        self.assertFalse(r1["ok"])
        self.assertEqual(r1["fator_extremo_crista"], 1.0)

    def test_fator_e_o_mesmo_da_previsao_de_pico(self):
        e = self._experimento_07()
        fatores = {"01": 1.063, "07": 1.186}
        with mock.patch.object(type(e), "_fatores_extremo", lambda self: fatores):
            fator = e.fator_extremo_efetivo_para_validacao(None)
            self.assertEqual(fator, mestre.fator_extremo_da_classe("07", fatores))
            self.assertAlmostEqual(
                e._extremo_previsto_da_forma_v(100.0, {}), 100.0 * fator * mestre.MARGEM_FATOR_EXTREMO,
            )
            e.id = "99"  # classe fora da tabela: o mesmo critério da previsão (maior fator)
            self.assertEqual(e.fator_extremo_efetivo_para_validacao(None), 1.186)
        # condição sem tabela: o conservador de carregar_fatores_extremo, como na previsão
        e = self._experimento_07(f0=50.0)
        self.assertEqual(
            e.fator_extremo_efetivo_para_validacao(None),
            mestre.fator_extremo_da_classe("07", e._fatores_extremo()),
        )

    def test_disturbio_reduzido_usa_a_formula_da_previsao_sem_margem(self):
        e = self._experimento_07()
        fatores = {"01": 1.063, "07": 1.5}
        avaliacao = {"pico_programado_v": 200.0, "parametros": {
            "fator_disturbio_bancada": 0.5, "pico_programado_modelo_v": 300.0}}
        with mock.patch.object(type(e), "_fatores_extremo", lambda self: fatores):
            efetivo = e.fator_extremo_efetivo_para_validacao(avaliacao)
            previsto = e._extremo_previsto_da_forma_v(200.0, avaliacao["parametros"])
        self.assertAlmostEqual(efetivo, previsto / (200.0 * mestre.MARGEM_FATOR_EXTREMO))
        self.assertLess(efetivo, 1.5)
        self.assertGreater(efetivo, 1.063)

    def test_08_com_excursao_propria_usa_fator_1(self):
        e = _load_experimento("08")
        with mock.patch.object(type(e), "excursao_fisica_prevista_v", lambda self: 250.0):
            self.assertEqual(e.fator_extremo_efetivo_para_validacao(None), 1.0)


class PerfisCompartilhadosTests(unittest.TestCase):
    """``set perfil todos`` sem recapturas iguais (spec 25): classes cujo
    ``gerar()`` não depende do perfil (``perfis.depende_do_perfil``) são
    capturadas uma vez; o metadata dos três perfis aponta para a mesma captura
    (arquivo, índice, SHA-256) e ``sessao_io``/HTML a resolvem."""

    PERFIS = NpzPorClasseTests.PERFIS
    ITENS = NpzPorClasseTests.ITENS
    _config = NpzPorClasseTests._config
    _scripts = NpzPorClasseTests._scripts
    _sessao_simulada_todos = NpzPorClasseTests._sessao_simulada_todos
    _classe_fisica = NpzPorClasseTests._classe_fisica
    _bancada_fisica = NpzPorClasseTests._bancada_fisica

    def setUp(self):
        import sessao_io
        self.sessao_io = sessao_io
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    @staticmethod
    def _gerar(classe_id, perfil, sorteio, f0, indice):
        import dataclasses
        experimento = _load_experimento(classe_id)
        experimento.config = dataclasses.replace(
            experimento.config, perfil=perfil, sorteio_posicao=sorteio, grid_frequency_hz=f0,
        )
        t = np.arange(6000) / 30_000.0
        tensao, parametros = experimento.gerar(t, f0, indice, np.random.default_rng(experimento.seed_da_captura(indice)))
        return np.asarray(tensao, dtype=np.float64).tobytes(), json.dumps(parametros, sort_keys=True, default=repr)

    def test_independentes_derivadas_da_tabela_e_conferidas_contra_o_gerar_real(self):
        import perfis
        esperado = {
            True: ("01", "04", "07", "08", "09", "17", "18", "19"),
            False: ("01", "04", "07", "08", "09", "16", "17", "18", "19"),
        }
        for sorteio in (True, False):
            self.assertEqual(perfis.classes_independentes_do_perfil(sorteio), esperado[sorteio])
            for classe_id in perfis.CLASSES:
                for f0 in (60.0, 50.0):
                    diferiu = False
                    for indice in range(8):
                        por_perfil = {p: self._gerar(classe_id, p, sorteio, f0, indice) for p in perfis.PERFIS}
                        iguais = len(set(por_perfil.values())) == 1
                        if classe_id in esperado[sorteio]:
                            self.assertTrue(iguais, (classe_id, sorteio, f0, indice))  # arrays E parâmetros
                        diferiu = diferiu or not iguais
                    if classe_id not in esperado[sorteio]:
                        self.assertTrue(diferiu, (classe_id, sorteio, f0))

    def test_plano_de_perfis(self):
        import perfis
        todos = perfis.PERFIS
        self.assertEqual(perfis.plano_de_perfis("01", todos), [("literatura", ("norma", "fronteira"))])
        self.assertEqual(perfis.plano_de_perfis("02", todos), [(p, ()) for p in todos])
        self.assertEqual(perfis.plano_de_perfis("01", ("norma",)), [("norma", ())])  # perfil único: como sempre
        self.assertEqual(perfis.plano_de_perfis("01", ("norma", "fronteira")), [("norma", ("fronteira",))])

    def test_simulado_captura_independente_uma_vez_e_metadata_dos_tres_perfis_aponta_para_ela(self):
        vistos = []
        original = mestre.Bancada._executar_classe_no_perfil

        def espia(self_, class_id, *a, **k):
            vistos.append((class_id, self_.config.perfil, self_.config.perfis_espelho))
            return original(self_, class_id, *a, **k)

        config = self._config(self.tmp / "r")
        with mock.patch.object(mestre.Bancada, "_executar_classe_no_perfil", espia):
            self._sessao_simulada_todos(self.tmp / "r", "01", "02")
        self.assertEqual([v for v in vistos if v[0] == "01"], [("01", "literatura", ("norma", "fronteira"))])
        self.assertEqual([v[1] for v in vistos if v[0] == "02"], list(self.PERFIS))
        pasta = config.results_dir
        with np.load(pasta / "01_normal.npz") as dados:
            self.assertEqual(list(dados["perfis"]), ["literatura"])
            self.assertEqual(list(dados["compartilhadas_perfis"]), ["norma", "fronteira"])
            self.assertEqual(list(dados["compartilhadas_origem"]), ["literatura", "literatura"])
            self.assertNotIn("norma/medida", dados.files)
        with np.load(pasta / "02_sag.npz") as dados:
            self.assertEqual(list(dados["perfis"]), list(self.PERFIS))
            self.assertNotIn("compartilhadas_perfis", dados.files)
        linhas = [json.loads(l) for l in (pasta / "metadata" / "01_normal.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(linhas), 9)
        por_id = {}
        for l in linhas:
            por_id.setdefault(l["id_captura"], []).append(l)
        for id_captura, grupo in por_id.items():
            self.assertEqual(sorted(l["perfil"] for l in grupo), sorted(self.PERFIS))
            self.assertEqual(len({(l["arquivo_classe"], l["indice_no_arquivo"], l["sha256_captura"]) for l in grupo}), 1)
            self.assertEqual({l["perfil_de_origem"] for l in grupo}, {"literatura"})
            self.assertTrue(all(l["captura_compartilhada"] for l in grupo))
            self.assertEqual({tuple(l["compartilhada_com_perfis"]) for l in grupo}, {("literatura", "norma", "fronteira")})
            self.assertEqual(len({json.dumps(l["parametros"], sort_keys=True) for l in grupo}), 1)
        # as classes dependentes não ganham campo nenhum
        dependentes = [json.loads(l) for l in (pasta / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertTrue(all("sha256_captura" not in l and "perfil_de_origem" not in l for l in dependentes))
        # snr_XXdb/ e sem sobra
        with np.load(pasta / "snr_20db" / "01_normal.npz") as dados:
            self.assertEqual(list(dados["perfis"]), ["literatura"])
            self.assertEqual(list(dados["compartilhadas_perfis"]), ["norma", "fronteira"])
        self.assertEqual(list(pasta.rglob("*.part")), [])

    def test_sessao_io_resolve_as_compartilhadas_e_o_hash_confere(self):
        pasta = self._sessao_simulada_todos(self.tmp / "r", "01").results_dir
        capturas = self.sessao_io.ler_capturas(pasta, versoes=self.ITENS)
        self.assertEqual(len(capturas), 9)
        self.assertEqual([c.perfil for c in capturas[::3]], list(self.PERFIS))  # ordem norma, literatura, fronteira
        for c in capturas:
            self.assertTrue(c.compartilhada)
            self.assertEqual(c.perfil_de_origem, "literatura")
            self.assertEqual(c.espelho, c.perfil != "literatura")
            self.assertEqual(set(c.perfis_compartilhados), set(self.PERFIS))
            self.assertEqual(c.metadado["perfil"], c.perfil)
            pontos = c.versoes["modelo"].size
            self.assertEqual(
                self.sessao_io.hash_captura(c.versoes["medida"], c.versoes.get("modelo"), c.versoes.get("programada"), pontos),
                c.metadado["sha256_captura"],
            )
        por_id = {}
        for c in capturas:
            por_id.setdefault(c.id_captura, []).append(c)
        for grupo in por_id.values():
            for c in grupo:
                np.testing.assert_array_equal(c.versoes["medida"], grupo[0].versoes["medida"])
        # pedir só a norma devolve a captura canônica, marcada como compartilhada
        so_norma = self.sessao_io.ler_capturas(pasta, versoes=("medida",), perfis=["norma"])
        self.assertEqual(len(so_norma), 3)
        self.assertTrue(all(c.espelho and c.perfil == "norma" and c.perfil_de_origem == "literatura" for c in so_norma))
        self.assertEqual({c.metadado["perfil"] for c in so_norma}, {"norma"})
        # SNR: o mesmo
        snr = self.sessao_io.ler_pasta(pasta / "snr_20db", self.sessao_io.carregar_metadados(pasta))
        self.assertEqual(sorted({c.perfil for c in snr}), sorted(self.PERFIS))
        self.assertEqual(len(snr), 9)

    def test_html_desenha_a_captura_compartilhada_uma_vez_e_diz_isso(self):
        import relatorio_html
        pasta = self._sessao_simulada_todos(self.tmp / "r", "01", "02").results_dir
        caminho, total = relatorio_html.gerar_relatorio(pasta, self.tmp / "t.html", dpi=40)
        self.assertEqual(total, 3 + 9)  # 01: 3 figuras (não 9); 02: 3 capturas x 3 perfis
        texto = caminho.read_text(encoding="utf-8")
        self.assertEqual(texto.count("mesma captura nos perfis literatura, norma, fronteira"), 3)
        self.assertIn("(= norma, fronteira)", texto)
        # só a norma: a captura aparece (marcada), não some
        caminho, total = relatorio_html.gerar_relatorio(
            pasta, self.tmp / "n.html", dpi=40, classes=["01"], perfis=["norma"],
        )
        self.assertEqual(total, 3)
        texto = caminho.read_text(encoding="utf-8")
        self.assertIn("esta captura é a do perfil literatura", texto)

    def test_recortar_margem_preserva_o_compartilhamento(self):
        from recortar_margem import recortar_sessao
        pasta = self._sessao_simulada_todos(self.tmp / "r", "01", "02").results_dir
        saida = self.tmp / "sem_margem"
        recortar_sessao(pasta, saida)
        with np.load(saida / "01_normal.npz") as dados:
            self.assertEqual(list(dados["perfis"]), ["literatura"])
            self.assertEqual(sorted(dados["compartilhadas_perfis"]), ["fronteira", "norma"])
        linhas = [json.loads(l) for l in (saida / "metadata" / "01_normal.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sorted({l["perfil"] for l in linhas}), sorted(self.PERFIS))
        self.assertEqual(len(self.sessao_io.ler_pasta(saida, self.sessao_io.carregar_metadados(saida), classes=["01"])), 9)
        self.assertEqual(len(self.sessao_io.ler_pasta(saida, self.sessao_io.carregar_metadados(saida), classes=["02"])), 9)

    def test_analisar_sessao_ve_a_captura_compartilhada_uma_vez(self):
        import analisar_sessao
        pasta = self._sessao_simulada_todos(self.tmp / "r", "01").results_dir
        relatorio = analisar_sessao.analisar_sessao(pasta)
        self.assertEqual([l["classe"] for l in relatorio], ["01_normal:literatura"])  # simulado: um aviso, sob a origem

    def test_bancada_fisica_captura_a_classe_independente_uma_so_vez(self):
        classe, chamadas = self._classe_fisica()
        classe.id = "97"  # fora da tabela de perfis: independente do perfil
        config = self._config(self.tmp / "r", snr_levels_db=(30.0,), capturas_override=2)
        bancada = self._bancada_fisica(config)
        with mock.patch.object(mestre.Bancada, "_carregar_classe_experimento", staticmethod(lambda p: classe)):
            resultados = bancada.executar_bateria([Path("97.py")], self.PERFIS)
        self.assertTrue(resultados[0].ok)
        self.assertEqual(chamadas["n"], 2)  # 2 capturas, não 6
        pasta = config.results_dir
        with np.load(pasta / "97_teste_interrompida.npz") as dados:
            self.assertEqual(list(dados["perfis"]), ["literatura"])
            self.assertEqual(dados["literatura/medida"].shape, (2, 6000))
        linhas = [json.loads(l) for l in (pasta / "metadata" / "97_teste_interrompida.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([l["perfil"] for l in linhas], ["literatura"] * 2 + ["norma"] * 2 + ["fronteira"] * 2)
        self.assertEqual(len({l["sha256_captura"] for l in linhas[:2]}), 2)
        self.assertEqual({l["sha256_captura"] for l in linhas[:2]}, {l["sha256_captura"] for l in linhas[2:4]})
        self.assertEqual([l["indice_no_arquivo"] for l in linhas], [0, 1] * 3)
        self.assertEqual(bancada.config.perfis_espelho, ())  # a Bancada volta ao que era

    def test_falha_da_classe_independente_nao_deixa_espelhos(self):
        classe, _ = self._classe_fisica(falhar_na_chamada=2)
        classe.id = "97"
        config = self._config(self.tmp / "r", snr_levels_db=(), capturas_override=2)
        bancada = self._bancada_fisica(config)
        with mock.patch.object(mestre.Bancada, "_carregar_classe_experimento", staticmethod(lambda p: classe)), \
                self.assertRaises(CommunicationError):
            bancada.executar_bateria([Path("97.py")], self.PERFIS)
        with np.load(config.results_dir / "97_teste_interrompida.npz") as dados:
            self.assertNotIn("compartilhadas_perfis", dados.files)  # captura incompleta não é replicada

    def test_estimativa_conta_so_o_que_roda_de_fato(self):
        import cli
        import perfis
        scripts = mestre.scripts_da_bateria_fisica()
        with mock.patch.object(mestre, "PERFIL_TODOS", True):
            linhas = {i: info for i, _, info in cli.SessaoCLI._capturas_das_classes(scripts)}
        independentes = set(perfis.classes_independentes_do_perfil(True))
        for classe_id, info in linhas.items():
            if classe_id in independentes:
                self.assertEqual(list(info["por_perfil"]), ["literatura"], classe_id)
                self.assertEqual(info["espelhos"], {"literatura": ("norma", "fronteira")})
                self.assertEqual(info["evitadas"], 2 * info["total"])
            else:
                self.assertEqual(list(info["por_perfil"]), list(perfis.PERFIS), classe_id)
        self.assertIn("igual em norma, fronteira", cli.SessaoCLI._descrever_capturas(linhas["01"]))

    def test_recuperar_parcial_preserva_espelhos_de_origem_nao_refeita(self):
        pasta = self.tmp / "r"
        io = self.sessao_io
        t = np.arange(6000) / 30_000.0
        a = io.ArquivoDaClasse(pasta, "97", "TESTE")

        def cap(arq, perfil, n, valor):
            md = {"id_captura": f"97-{n:04d}", "classe": "X", "perfil": perfil, "pontos": 6000, "fs_hz": 30_000.0}
            arq.adicionar(perfil, id_captura=md["id_captura"], medida=np.full(6000, valor), tempo_ms=t * 1000.0,
                          fs_hz=30_000.0, modelo=np.full(6000, valor), metadado=md)

        a.iniciar_perfil("literatura")
        cap(a, "literatura", 1, 1.0)
        a.espelhar("literatura", ["norma"])
        a.consolidar()
        a.encerrar_perfil("literatura")
        (pasta / "metadata").mkdir()
        (pasta / "metadata" / "97_teste.jsonl").write_text(
            "\n".join(json.dumps(r) for r in a.registros()) + "\n", encoding="utf-8")
        a.iniciar_perfil("fronteira")
        cap(a, "fronteira", 1, 3.0)  # processo morre antes de consolidar
        a.close()  # Escritor encerrado antes da recuperação exclusiva.
        io.recuperar_parcial(pasta)
        with np.load(pasta / "97_teste.npz") as dados:
            self.assertEqual(sorted(str(p) for p in dados["perfis"]), ["fronteira", "literatura"])
            self.assertEqual(list(dados["compartilhadas_perfis"]), ["norma"])
        capturas = io.ler_capturas(pasta, versoes=("medida",))
        self.assertEqual(sorted(c.perfil for c in capturas), ["fronteira", "literatura", "norma"])
        linhas = [json.loads(l) for l in (pasta / "metadata" / "97_teste.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sorted(l["perfil"] for l in linhas), ["fronteira", "literatura", "norma"])


if __name__ == "__main__":
    unittest.main()
