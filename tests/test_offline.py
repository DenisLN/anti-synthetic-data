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
from oscilloscope_orm import KeysightDSOX4034A  # noqa: E402
from sinais import ruido_awgn, snr_medida  # noqa: E402
import sinais  # noqa: E402
import mestre  # noqa: E402
import preflight_new  # noqa: E402


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


def _load_gerar(experiment_id: str):
    return _load_experimento(experiment_id).gerar


class ScriptedVisaConnection:
    def __init__(self, adapter):
        self.adapter = adapter

    def query_binary_values(self, command, **kwargs):
        self.adapter.commands.append(command)
        return (20 + np.arange(6000, dtype=np.int64) % 200).astype(np.uint8)

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

    def write(self, command, **kwargs):
        self.last_command = command
        self.commands.append(command)
        if command.upper().startswith(":CHANNEL1:SCALE "):
            self.channel_scale = float(command.split()[-1])

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
            return "0.2"
        if "WAVEFORM:PREAMBLE?" in command:
            return "0,0,6000,1,3.333333333333e-5,0,0,0.01,0,128"
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
            # VOLTage:HIGH é um limite de PICO em Vp na AMETEK MX30.
            # Passamos 100.0 Vp diretamente (pico máximo autorizado).
            voltage_high_vp=100.0,
            current_limit_a=0.5,
            protection_delay_s=0.1,
            frequency_hz=50.0,
        )
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
        self.assertFalse(config.margin_mode)
        self.assertFalse(config.diagnostico_mode)


class TotalNiveisTests(unittest.TestCase):
    def test_classe_sem_niveis_retorna_1(self):
        experimento = _BancadaFake.experimento_sem_niveis()
        self.assertEqual(experimento.total_niveis(), 1)

    def test_classe_com_niveis_retorna_o_tamanho_da_tupla(self):
        experimento = _BancadaFake.experimento_com_niveis()
        self.assertEqual(experimento.total_niveis(), 5)


class RemapeamentoNivelTests(unittest.TestCase):
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
            bancada = mestre.Bancada(mestre.AmetekMX30(simulated=True), mock.Mock(), config)
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
            bancada = mestre.Bancada(mestre.AmetekMX30(simulated=True), mock.Mock(), config)
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
            bancada = mestre.Bancada(mestre.AmetekMX30(simulated=True), mock.Mock(), config)

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
    def test_margin_off_mantem_pontos_nominais(self):
        margem_amostras, pontos_totais = mestre.ExperimentoBase._calcular_margem(
            margin_mode=False, config_points=6000, fs_hz=30_000.0,
        )
        self.assertEqual(margem_amostras, 0)
        self.assertEqual(pontos_totais, 6000)

    def test_margin_on_adiciona_amostras_de_cada_lado(self):
        margem_amostras, pontos_totais = mestre.ExperimentoBase._calcular_margem(
            margin_mode=True, config_points=6000, fs_hz=30_000.0,
        )
        self.assertEqual(margem_amostras, 750)  # 25ms * 30kSa/s
        self.assertEqual(pontos_totais, 6000 + 2 * 750)

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
            relatorio = analisar_sessao.analisar_sessao(sessao_dir, gerar_imagens=False)
            self.assertEqual(len(relatorio), 1)
            self.assertEqual(relatorio[0]["classe"], "01_normal_cap01")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
