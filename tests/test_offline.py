import importlib.util
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
import mestre  # noqa: E402
import preflight_new  # noqa: E402


class _BancadaFake:
    """Suficiente para instanciar um Experimento sem abrir instrumento nenhum:
    gerar() só usa self.config/self.fonte/self.osc se explicitamente
    sobrescrito, e nenhuma classe hoje faz isso."""

    config = None
    fonte = None
    osc = None


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
            self.assertTrue((results_dir / "01_ok.npz").exists())
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


if __name__ == "__main__":
    unittest.main()
