import importlib.util
import json
import logging
import math
import shutil
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
        """Bancada 2026-09-30 (docs/analise-2026-09-30, N1): sem controle de
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
            # RMS e recebe max_voltage_rms (T12, docs/analise-2026-09-30).
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
                self.assertEqual(dados["tensao_pu"].shape, (2, 6_000))
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
    def test_grava_um_npz_por_captura_com_nivel_no_nome(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = mestre.Config(
                fs_hz=30_000.0, points=4, duration_s=0.2, grid_frequency_hz=60.0,
                base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
                capture_current=False, current_base_a=None, results_dir=tmp_dir,
                sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
            )
            class _Concreta(mestre.ExperimentoWaveform):
                id = "02"
                nome = "SAG"

                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {}

            bancada_fake = mock.Mock(config=config, fonte=None, osc=None)
            experimento = _Concreta(bancada_fake)
            tensao = np.zeros((2, 4))
            experimento._salvar_classe(
                tempo_ms=np.zeros(4),
                tensao_limpa=tensao,
                tensao_por_snr={},
                ids=["02-0001", "02-0002"],
                corrente=None,
                metadados=[
                    {"id_captura": "02-0001", "classe": "SAG", "nivel_indice": 0,
                     "parametros": {"sag_pu": 0.1}, "seed": 1, "simulado": False,
                     "fs_hz": 30000.0, "pontos": 4, "snr_medido_db": {}},
                    {"id_captura": "02-0002", "classe": "SAG", "nivel_indice": 1,
                     "parametros": {"sag_pu": 0.3}, "seed": 2, "simulado": False,
                     "fs_hz": 30000.0, "pontos": 4, "snr_medido_db": {}},
                ],
                simulated=False,
            )
            arquivos = sorted(p.name for p in tmp_dir.glob("02_sag*.npz"))
            self.assertEqual(arquivos, ["02_sag_sag_pu-0.1.npz", "02_sag_sag_pu-0.3.npz"])
            self.assertTrue((tmp_dir / "metadata" / "02_sag.jsonl").exists())
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_classe_sem_parametro_nomeavel_usa_capNN(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = mestre.Config(
                fs_hz=30_000.0, points=4, duration_s=0.2, grid_frequency_hz=60.0,
                base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
                capture_current=False, current_base_a=None, results_dir=tmp_dir,
                sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
            )
            class _Concreta(mestre.ExperimentoWaveform):
                id = "01"
                nome = "NORMAL"

                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {}

            bancada_fake = mock.Mock(config=config, fonte=None, osc=None)
            experimento = _Concreta(bancada_fake)
            experimento._salvar_classe(
                tempo_ms=np.zeros(4), tensao_limpa=np.zeros((1, 4)), tensao_por_snr={},
                ids=["01-0001"], corrente=None,
                metadados=[{"id_captura": "01-0001", "classe": "NORMAL", "nivel_indice": 0,
                            "parametros": {}, "seed": 1, "simulado": False,
                            "fs_hz": 30000.0, "pontos": 4, "snr_medido_db": {}}],
                simulated=False,
            )
            self.assertTrue((tmp_dir / "01_normal_cap01.npz").exists())
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_rodada_com_capturas_diferentes_remove_arquivos_orfaos_da_rodada_anterior(self):
        """Regressão do review: antes desta task, uma classe sempre gravava
        UM arquivo (`{id}_{nome}.npz`) — uma nova rodada naturalmente
        sobrescrevia esse único arquivo, órfão nunca sobrava. Agora que o
        nome depende do parâmetro/posição de CADA captura, uma rodada com
        um conjunto de capturas DIFERENTE (menos capturas, ou parâmetros
        diferentes — ex.: `run 02` e depois `set capturas` + `run 02` de
        novo) deixava os arquivos da rodada anterior, sem nenhuma captura
        atual apontando pra eles, órfãos em `results_dir`/`snr_XXdb/`/
        `corrente/`. `_salvar_classe()` deve limpar esses órfãos (só depois
        que os arquivos novos já estão gravados com sucesso)."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = mestre.Config(
                fs_hz=30_000.0, points=4, duration_s=0.2, grid_frequency_hz=60.0,
                base_voltage_rms=127.0, snr_levels_db=(30.0,), base_seed=1,
                capture_current=True, current_base_a=1.0, results_dir=tmp_dir,
                sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
            )
            class _Concreta(mestre.ExperimentoWaveform):
                id = "02"
                nome = "SAG"

                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {}

            bancada_fake = mock.Mock(config=config, fonte=None, osc=None)
            experimento = _Concreta(bancada_fake)

            # Rodada 1: 2 capturas (sag_pu 0.1 e 0.3).
            experimento._salvar_classe(
                tempo_ms=np.zeros(4),
                tensao_limpa=np.zeros((2, 4)),
                tensao_por_snr={30.0: np.zeros((2, 4))},
                ids=["02-0001", "02-0002"],
                corrente=np.zeros((2, 4)),
                metadados=[
                    {"id_captura": "02-0001", "classe": "SAG", "nivel_indice": 0,
                     "parametros": {"sag_pu": 0.1}, "seed": 1, "simulado": False,
                     "fs_hz": 30000.0, "pontos": 4, "snr_medido_db": {}},
                    {"id_captura": "02-0002", "classe": "SAG", "nivel_indice": 1,
                     "parametros": {"sag_pu": 0.3}, "seed": 2, "simulado": False,
                     "fs_hz": 30000.0, "pontos": 4, "snr_medido_db": {}},
                ],
                simulated=False,
            )
            arquivo_orfao = tmp_dir / "02_sag_sag_pu-0.1.npz"
            arquivo_orfao_snr = tmp_dir / "snr_30db" / "02_sag_sag_pu-0.1.npz"
            arquivo_orfao_corrente = tmp_dir / "corrente" / "02_sag_sag_pu-0.1_corrente.npz"
            self.assertTrue(arquivo_orfao.exists())
            self.assertTrue(arquivo_orfao_snr.exists())
            self.assertTrue(arquivo_orfao_corrente.exists())

            # Rodada 2: 1 captura só, com um parâmetro diferente (sag_pu 0.5)
            # — simula `set capturas` mudando o conjunto entre duas rodadas.
            experimento._salvar_classe(
                tempo_ms=np.zeros(4),
                tensao_limpa=np.zeros((1, 4)),
                tensao_por_snr={30.0: np.zeros((1, 4))},
                ids=["02-0003"],
                corrente=np.zeros((1, 4)),
                metadados=[
                    {"id_captura": "02-0003", "classe": "SAG", "nivel_indice": 0,
                     "parametros": {"sag_pu": 0.5}, "seed": 3, "simulado": False,
                     "fs_hz": 30000.0, "pontos": 4, "snr_medido_db": {}},
                ],
                simulated=False,
            )

            # Órfãos da rodada 1 devem ter sido removidos das três pastas.
            self.assertFalse(arquivo_orfao.exists())
            self.assertFalse(arquivo_orfao_snr.exists())
            self.assertFalse(arquivo_orfao_corrente.exists())

            # Só o arquivo da rodada 2 deve sobrar em cada pasta.
            self.assertEqual(
                sorted(p.name for p in tmp_dir.glob("02_sag_*.npz")),
                ["02_sag_sag_pu-0.5.npz"],
            )
            self.assertEqual(
                sorted(p.name for p in (tmp_dir / "snr_30db").glob("02_sag_*.npz")),
                ["02_sag_sag_pu-0.5.npz"],
            )
            self.assertEqual(
                sorted(p.name for p in (tmp_dir / "corrente").glob("02_sag_*.npz")),
                ["02_sag_sag_pu-0.5_corrente.npz"],
            )

            # metadata.jsonl deve refletir só a rodada 2 (1 linha, captura 3).
            linhas = (tmp_dir / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(linhas), 1)
            self.assertIn("02-0003", linhas[0])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_capturas_reais_com_mesmo_rotulo_nao_se_sobrescrevem(self):
        """Regressão crítica: `set capturas 5` numa classe com NIVEIS agrupa
        5 capturas FÍSICAS no MESMO nível (mesmo `capture_index`, ver o ramo
        `cobertura_por_nivel_ativa` de executar()), logo as 5 têm o mesmo
        `parametros` e o mesmo rótulo. Sem desambiguação, as 5 gravavam no
        mesmo `.npz` e 4 capturas reais eram silenciosamente descartadas —
        exatamente o oposto do que a feature promete ("cada uma em um .npz
        diferente")."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = mestre.Config(
                fs_hz=30_000.0, points=4, duration_s=0.2, grid_frequency_hz=60.0,
                base_voltage_rms=127.0, snr_levels_db=(30.0,), base_seed=1,
                capture_current=True, current_base_a=1.0, results_dir=tmp_dir,
                sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
            )
            class _Concreta(mestre.ExperimentoWaveform):
                id = "02"
                nome = "SAG"

                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {}

            bancada_fake = mock.Mock(config=config, fonte=None, osc=None)
            experimento = _Concreta(bancada_fake)
            # 3 capturas no nível 0.1 + 2 no nível 0.3 (o que `set capturas`
            # produz de verdade ao agrupar por nível).
            niveis = [0.1, 0.1, 0.1, 0.3, 0.3]
            tensao = np.arange(5 * 4, dtype=np.float64).reshape(5, 4)
            experimento._salvar_classe(
                tempo_ms=np.zeros(4),
                tensao_limpa=tensao,
                tensao_por_snr={30.0: tensao + 100.0},
                ids=[f"02-{indice + 1:04d}" for indice in range(5)],
                corrente=tensao + 1000.0,
                metadados=[
                    {"id_captura": f"02-{indice + 1:04d}", "classe": "SAG",
                     "nivel_indice": indice // 3, "parametros": {"sag_pu": nivel},
                     "seed": indice, "simulado": False, "fs_hz": 30000.0, "pontos": 4,
                     "snr_medido_db": {}}
                    for indice, nivel in enumerate(niveis)
                ],
                simulated=False,
            )

            esperados = [
                "02_sag_sag_pu-0.1.npz", "02_sag_sag_pu-0.1_02.npz", "02_sag_sag_pu-0.1_03.npz",
                "02_sag_sag_pu-0.3.npz", "02_sag_sag_pu-0.3_02.npz",
            ]
            self.assertEqual(sorted(p.name for p in tmp_dir.glob("02_sag_*.npz")), sorted(esperados))
            self.assertEqual(
                sorted(p.name for p in (tmp_dir / "snr_30db").glob("02_sag_*.npz")),
                sorted(esperados),
            )
            self.assertEqual(
                sorted(p.name for p in (tmp_dir / "corrente").glob("02_sag_*.npz")),
                sorted(nome.replace(".npz", "_corrente.npz") for nome in esperados),
            )

            # Cada arquivo carrega a captura CERTA — nenhuma foi sobrescrita.
            for indice, nome in enumerate(esperados):
                with np.load(tmp_dir / nome, allow_pickle=True) as dados:
                    np.testing.assert_array_equal(dados["tensao_pu"], tensao[indice: indice + 1])
                    self.assertEqual(list(dados["id_captura"]), [f"02-{indice + 1:04d}"])

            linhas = (tmp_dir / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(linhas), 5)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class SalvarClasseSimuladoTests(unittest.TestCase):
    """O dataset SIMULADO nunca teve motivo para um arquivo por captura:
    arrays numpy não colidem, e o formato empilhado (um `.npz` por classe,
    shape `(N, pontos)`) foi o que valeu por toda a história do projeto.
    Task 5 aplicou o nome-por-parâmetro aos DOIS caminhos, e como muitas
    classes repetem `parametros` entre capturas (02/03/05 ciclam 5 níveis,
    18 alterna 2, 10-17 devolvem dicts constantes), até 2000 capturas
    simuladas colapsavam em punhado de arquivos."""

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
                self.assertEqual(dados["tensao_pu"].shape, (3, 4))
                np.testing.assert_array_equal(dados["tensao_pu"], tensao)
                self.assertEqual(list(dados["id_captura"]), ids)
                self.assertEqual(str(dados["classe"]), "SAG")
            with np.load(tmp_dir / "snr_30db" / "02_sag.npz", allow_pickle=True) as dados:
                np.testing.assert_array_equal(dados["tensao_pu"], tensao + 100.0)
            with np.load(tmp_dir / "corrente" / "02_sag_corrente.npz", allow_pickle=True) as dados:
                np.testing.assert_array_equal(dados["corrente_pu"], tensao + 1000.0)

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
                self.assertEqual(dados["tensao_pu"].shape, (total, 4))
                np.testing.assert_array_equal(dados["tensao_pu"], tensao)
                self.assertEqual(list(dados["id_captura"]), ids)
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
                self.assertEqual(dados["tensao_pu"].shape, (4, 6_000))
                self.assertEqual(
                    list(dados["id_captura"]),
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
    completa em 03_propostas_melhorias.md, proposta P1-2, e no pedido do
    dono de 2026-09-22 ("descontinue o margin on... faça esse comportamento
    de janela o default")."""

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
        """Pedido do dono, 2026-09-22: descontinuar 'set margin on|off' e
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

            def observador(n):
                vistos.append(len(list((config.results_dir).glob("96_*.npz"))))

            experimento = self._experimento(config, observador=observador)
            experimento.executar()
            # antes da captura 1 não há nada; antes da 2 já existe 1 arquivo...
            self.assertEqual(vistos, [0, 1, 2, 3])
            self.assertEqual(len(list(config.results_dir.glob("96_*.npz"))), 4)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_falha_no_meio_preserva_as_capturas_boas_anteriores(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados")
            experimento = self._experimento(config, falhar_em=3)
            with self.assertRaises(CommunicationError):
                experimento.executar()
            arquivos = sorted(p.name for p in config.results_dir.glob("96_*.npz"))
            self.assertEqual(len(arquivos), 2, f"esperava 2 capturas preservadas, achei {arquivos}")
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
            arquivos = sorted(p.name for p in (tmp_dir / "resultados").glob("03_swell*.npz"))
            self.assertEqual(len(arquivos), 2)
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
    """P11 — pedido do dono, 2026-09-22: "faça o diagnostico on abrir um
    terminal com algo como tail -f nas logs de scpi concomitantemente ao
    terminal". Com ``set diagnostico on`` e captura FÍSICA (``BENCH_MODE``),
    cada ``_garantir_pasta_sessao()`` (chamada no início de todo `run`/`run
    all`) abre uma janela de console nova acompanhando
    ``scpi_transcricao.log`` (P06) da pasta da sessão em tempo real, sem
    nunca derrubar a sessão se o console não puder ser aberto."""

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

    Pedido do dono em 2026-09-22, reagindo ao p01/p02 ("a captura falha na
    hora"): "só por favor não aborte a bateria de testes. apenas log e
    descarte. abortar a bateria gasta MUITO tempo." Antes deste patch,
    QUALQUER InstrumentHardwareError dentro de _capturar_real() (erro 19 do
    p01, divergência de readback do p02) propagava para fora do laço de
    executar() e disparava o retry de CLASSE INTEIRA de executar_bateria()
    (até 3×, refazendo do zero até as capturas que já tinham dado certo) —
    exatamente o custo que o dono não quer pagar por uma falha isolada."""

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
            arquivos = sorted(p.name for p in (tmp_dir / "resultados").glob("97_*.npz"))
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
            arquivos = list((tmp_dir / "resultados").glob("97_*.npz"))
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
    bancada (``capturas_padrao``). Pedido do dono (2026-10-07): 3 nas classes
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
    """v1.13, Tarefa 4 — opção (b) do dono para 220 V: nas classes waveform
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
        reduzidas = set()
        for indice in range(1, 21):
            classe_id = f"{indice:02d}"
            for info in self._avaliar_classe(classe_id):
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
        self.assertEqual(reduzidas, {"09", "10", "11", "14", "16", "17"})

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
        sessao = PROJECT_ROOT / "docs" / "analise-2026-09-30" / "dados" / "sessao_2026-09-30_15-26-05"
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
        sessao = PROJECT_ROOT / "docs" / "analise-2026-09-30" / "dados" / "sessao_2026-09-30_15-26-05"
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
        for cid, nome in (("01", "normal"), ("02", "sag"), ("05", "harmonics")):
            with np.load(saida / f"{cid}_{nome}_cap01.npz", allow_pickle=True) as dados:
                self.assertEqual(dados["tensao_pu"].shape, (1, 6000))
                np.testing.assert_allclose(dados["tensao_pu"][0], self.nominais[cid])
                self.assertEqual(dados["tempo_ms"][0], 0.0)
            with np.load(saida / "snr_30db" / f"{cid}_{nome}_cap01.npz", allow_pickle=True) as dados:
                np.testing.assert_allclose(dados["tensao_pu"][0], self.nominais[cid] + 0.01)
        origens = {linha["id_captura"]: linha["origem"] for linha in relatorio}
        self.assertEqual(origens["01-0001"], "indice_trigger")
        self.assertEqual(origens["05-0001"], "margem_amostras_antes")

        md = json.loads((saida / "metadata" / "02_sag.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(md["recorte"]["inicio_amostra"], 605)
        self.assertEqual(md["margem_amostras_antes"], 0)
        self.assertEqual(md["amostras_totais"], 6000)
        self.assertEqual(md["indice_trigger"], 1800)  # 60 ms dentro da janela nominal

        with np.load(saida / "empilhado" / "02_sag.npz", allow_pickle=True) as dados:
            self.assertEqual(dados["tensao_pu"].shape, (1, 6000))
            self.assertEqual(list(dados["id_captura"]), ["02-0001"])

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
        for chave, esperado in ref["hashes"].items():
            cid, f0, seed, indice = chave.split("/")
            for experimento in (_sem_sorteio(_load_experimento(cid)), self._com_perfil(cid, "literatura")):
                self.assertEqual(
                    self._assinatura(experimento, float(f0), int(seed), int(indice)), esperado, chave,
                )

    def test_norma_e_fronteira_mudam_so_o_que_a_spec_manda(self):
        ref = json.loads(self.REFERENCIA.read_text(encoding="utf-8"))["hashes"]
        afetadas = {"norma": {"02", "03", "05", "06", "11", "15", "20"},
                    "fronteira": {"02", "03", "10", "11", "12", "13", "14"}}
        for perfil, esperadas in afetadas.items():
            mudou = set()
            for chave, h in ref.items():
                cid, f0, seed, indice = chave.split("/")
                if self._assinatura(self._com_perfil(cid, perfil), float(f0), int(seed), int(indice)) != h:
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
    (docs/analise-2026-10-12/sorteio_inicio_fase.md)."""

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
        """A conta do professor (formas distintas entre capturas de uma
        classe): com o sorteio, nenhuma classe volta a ser cópia da mesma onda."""
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
        for chave, esperado in ref["hashes"].items():
            cid, f0, seed, indice = chave.split("/")
            self.assertEqual(
                PerfisDeFaixasTests._assinatura(_load_experimento(cid), float(f0), int(seed), int(indice)),
                esperado, chave,
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
        for classe_id in self.CLASSES:
            if classe_id == "03":
                continue  # 03 a 220 V já pulava níveis (1,4 pu > 300 Vrms)
            config = _config_bancada(self.tmp_dir, base_voltage_rms=220.0, sorteio_posicao=True)
            fonte = mestre.AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=415.8)
            experimento = _carregar_classe(classe_id)(mestre.Bancada(fonte, mock.Mock(), config))
            for indice_global, capture_index in experimento.plano_de_capturas(False):
                info = experimento.avaliar_captura_na_bancada(indice_global, capture_index)
                self.assertTrue(info["cabe"], (classe_id, indice_global, info.get("motivo")))

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
    sorteio ligado (docs/analise-2026-10-12/compostas_sorteadas.md), e o teste
    do item f) do professor: nenhuma classe volta a ter poucas formas
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

    def test_literatura_cobre_as_faixas_da_proposta_4(self):
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
    """v1.16 — modelo / programada / medida (docs/tres_versoes.md). O ponto
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
            for stem in ("02_sag", "10_sag_harmonics"):
                with np.load(config.results_dir / "tres_versoes" / f"{stem}.npz", allow_pickle=True) as dados, np.load(config.results_dir / f"{stem}.npz", allow_pickle=True) as principal:
                    np.testing.assert_array_equal(dados["modelo_pu"], principal["tensao_pu"])
                    self.assertEqual(dados["programada_pu"].shape, (3, 6000))
                    self.assertFalse(np.any(np.isnan(dados["programada_pu"])))
                    self.assertNotIn("medida_pu", dados.files)
                linha = json.loads((config.results_dir / "metadata" / f"{stem}.jsonl").read_text(encoding="utf-8").splitlines()[0])
                self.assertEqual(linha["tres_versoes"]["arquivo"], f"tres_versoes/{stem}.npz")
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
            arquivo = config.results_dir / "tres_versoes" / "95_teste_tres_cap01.npz"
            with np.load(arquivo, allow_pickle=True) as dados:
                self.assertEqual(dados["modelo_pu"].shape, (1, 6000))
                np.testing.assert_allclose(dados["modelo_pu"][0], np.sin(2.0 * np.pi * 60.0 * self.T), atol=1e-12)
                np.testing.assert_allclose(dados["programada_pu"][0], 0.8 * dados["modelo_pu"][0], atol=2e-3)
                np.testing.assert_array_equal(dados["medida_pu"][0], registro[600:6600])
                self.assertEqual(int(dados["inicio_janela"]), 600)
                self.assertEqual(dados["tempo_ms"].shape, (6000,))
            linha = json.loads((config.results_dir / "metadata" / "95_teste_tres.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(linha["tres_versoes"]["arquivo"], "tres_versoes/95_teste_tres_cap01.npz")
            # o .npz principal (a medida com margem) continua sendo gravado como sempre
            with np.load(config.results_dir / "95_teste_tres_cap01.npz") as principal:
                self.assertEqual(principal["tensao_pu"].shape, (1, 8100))
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
    """docs/analise-2026-10-12/classe08_fronteira.md: a 50 Hz o impulso de
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
    f0-3..f0+3 (docs/analise-2026-10-12/classes_05_07_18.md). Valem com o
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
        for chave, esperado in ref["hashes"].items():
            cid, f0, seed, indice = chave.split("/")
            if cid in ("05", "07", "17", "18"):
                experimento = _sem_sorteio(_load_experimento(cid))
                self.assertEqual(
                    PerfisDeFaixasTests._assinatura(experimento, float(f0), int(seed), int(indice)), esperado, chave,
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
    """Proposta 8: AWGN de 20/30/40 dB só na janela rotulada; SNR da bancada
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
            limpa = np.load(pasta / "02_sag.npz", allow_pickle=True)["tensao_pu"]
            for snr in (20, 30, 40):
                ruidosa = np.load(pasta / f"snr_{snr}db" / "02_sag.npz", allow_pickle=True)["tensao_pu"]
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
            nomes = sorted(p.name for p in pasta.glob("96_*.npz"))
            self.assertEqual(len(nomes), 2)
            for nome in nomes:
                limpa = np.load(pasta / nome, allow_pickle=True)["tensao_pu"][0]
                self.assertEqual(limpa.size, 8100)  # o limpo mantém as margens
                for snr in (20, 40):
                    dados = np.load(pasta / f"snr_{snr}db" / nome, allow_pickle=True)
                    self.assertEqual(dados["tensao_pu"].shape, (1, 6000))
                    self.assertEqual(dados["tempo_ms"].shape, (6000,))
                    janela = limpa[600:6600]
                    medido = 10.0 * math.log10(np.mean(janela**2) / np.mean((dados["tensao_pu"][0] - janela) ** 2))
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
        self.assertIn("02_sag_cap01", texto)
        self.assertIn("sessao_teste (sem_margem)", texto)
        self.assertTrue((self.sessao / "sem_margem" / "02_sag_cap01.npz").is_file())
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
                mock.patch.object(mestre.Bancada, "from_env", return_value=self._bancada_falsa(resultados)), \
                mock.patch.object(self.sessao_cli, "_recalibrar_ao_fim", side_effect=RuntimeError("boom")), \
                mock.patch.object(self.sessao_cli, "_gerar_html_ao_fim", side_effect=RuntimeError("boom")):
            codigo, saida = self._rodar(self.sessao_cli._run_all)
        self.assertEqual(codigo, 0)
        self.assertIn("1/1 classes OK", saida)
        self.assertIn("AVISO", saida)


if __name__ == "__main__":
    unittest.main()


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

