import importlib.util
import math
import sys
import unittest
from pathlib import Path

import numpy as np
from pymeasure.adapters import Adapter

from ametek_orm import AmetekMX30, ParameterOutOfBoundsError
from oscilloscope_orm import KeysightDSOX4034A

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_DIRS = (PROJECT_ROOT / "experimentos_nativos", PROJECT_ROOT / "experimentos_waveform")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sinais import ruido_awgn, snr_medida  # noqa: E402


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

    def test_configure_harmonics_csine_rejects_above_documented_ceiling(self):
        source = AmetekMX30(simulated=True, max_voltage_rms=10.0, max_peak_v=100.0, max_current_a=0.5)
        with self.assertRaises(ParameterOutOfBoundsError):
            source.configure_harmonics_csine(30.0)
        source.configure_harmonics_csine(20.0)
        self.assertIn("SOURCE:FUNCTION:SHAPE CSINE", "\n".join(source.command_log).upper())

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
        adapter = ScriptedAdapter()
        scope = KeysightDSOX4034A(adapter)
        scope.initialize_safe()
        scope.configure_acquisition(pre_trigger_s=0.060)
        joined = "\n".join(adapter.commands)
        self.assertIn(":TIMebase:POSition 0.06", joined)


if __name__ == "__main__":
    unittest.main()
