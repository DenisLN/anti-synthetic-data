"""Driver PyMeasure para Keysight DSO-X 4034A via USB/VISA."""

from __future__ import annotations

import logging
import re
import time
from typing import List, Tuple

import numpy as np
from pymeasure.instruments import Channel, Instrument, SCPIMixin
from pymeasure.instruments.validators import strict_discrete_set


logger = logging.getLogger("KeysightDSOX4034A")


def _normalized_identity(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


class OscilloscopeError(RuntimeError):
    pass


class OscChannel(Channel):
    bwlimit = Channel.control(
        ":CHANnel{ch}:BWLimit?",
        ":CHANnel{ch}:BWLimit %s",
        "Limite de banda do canal.",
        validator=strict_discrete_set,
        values={True: "1", False: "0"},
        map_values=True,
    )
    coupling = Channel.control(
        ":CHANnel{ch}:COUPling?",
        ":CHANnel{ch}:COUPling %s",
        "Acoplamento AC/DC do canal.",
        validator=strict_discrete_set,
        values={"AC": "AC", "DC": "DC"},
        map_values=True,
    )
    display = Channel.control(
        ":CHANnel{ch}:DISPlay?",
        ":CHANnel{ch}:DISPlay %s",
        "Exibição do canal.",
        validator=strict_discrete_set,
        values={True: "1", False: "0"},
        map_values=True,
    )
    offset = Channel.control(
        ":CHANnel{ch}:OFFSet?", ":CHANnel{ch}:OFFSet %e", "Offset vertical."
    )
    probe = Channel.control(
        ":CHANnel{ch}:PROBe?", ":CHANnel{ch}:PROBe %e", "Atenuação da probe."
    )
    scale = Channel.control(
        ":CHANnel{ch}:SCALe?", ":CHANnel{ch}:SCALe %e", "Escala vertical."
    )
    units = Channel.control(
        ":CHANnel{ch}:UNITs?",
        ":CHANnel{ch}:UNITs %s",
        "Unidade vertical do canal.",
        validator=strict_discrete_set,
        values={"VOLT": "VOLT", "AMP": "AMP"},
        map_values=True,
    )


class KeysightDSOX4034A(SCPIMixin, Instrument):
    """Controle mínimo e determinístico do DSO-X 4034A."""

    def __init__(self, adapter, name: str = "Keysight DSO-X 4034A", **kwargs):
        super().__init__(adapter, name, **kwargs)
        self.channels = {index: OscChannel(self, index) for index in range(1, 5)}
        self.idn = ""

    def verify_identity(self, expected_model: str = "DSOX4034A") -> str:
        self.idn = self.ask("*IDN?").strip()
        if _normalized_identity(expected_model) not in _normalized_identity(self.idn):
            raise OscilloscopeError(
                f"Osciloscópio inesperado: {self.idn!r}; esperado {expected_model!r}"
            )
        return self.idn

    def check_errors(self, max_errors: int = 20) -> List[Tuple[int, str]]:
        errors: List[Tuple[int, str]] = []
        for _ in range(max_errors):
            raw = self.ask(":SYSTem:ERRor?").strip()
            try:
                code_text, message = raw.split(",", 1)
                code = int(code_text)
            except (ValueError, TypeError) as exc:
                raise OscilloscopeError(f"Resposta inválida de :SYST:ERR?: {raw!r}") from exc
            if code == 0:
                return errors
            errors.append((code, message.strip().strip('"')))
        raise OscilloscopeError(f"Fila de erros Keysight não esvaziou: {errors}")

    def assert_no_errors(self, context: str) -> None:
        errors = self.check_errors()
        if errors:
            raise OscilloscopeError(f"Keysight reportou erros após {context}: {errors}")

    def initialize_safe(self) -> None:
        self.write(":STOP")
        self.write("*CLS")
        self.write(":ACQuire:TYPE NORMal")
        self.write(":WAVeform:FORMat BYTE")
        self.write(":WAVeform:UNSigned ON")
        self.write(":WAVeform:POINts:MODE RAW")
        self.assert_no_errors("inicialização")

    def configure_channel(
        self,
        channel: int,
        *,
        scale: float,
        probe_attenuation: float,
        offset: float = 0.0,
        coupling: str = "DC",
        units: str = "VOLT",
        display: bool = True,
    ) -> None:
        if channel not in self.channels:
            raise ValueError(f"Canal inválido: {channel}")
        if scale <= 0 or probe_attenuation <= 0:
            raise ValueError("Scale e atenuação de probe devem ser positivas")
        ch = self.channels[channel]
        ch.display = display
        ch.probe = probe_attenuation
        ch.coupling = coupling.upper()
        ch.units = units.upper()
        ch.offset = offset
        ch.scale = scale
        ch.bwlimit = False
        self.assert_no_errors(f"configuração do CH{channel}")

    def disable_channel(self, channel: int) -> None:
        if channel not in self.channels:
            raise ValueError(f"Canal inválido: {channel}")
        self.channels[channel].display = False
        self.assert_no_errors(f"desativação do CH{channel}")

    def set_vertical_scale(self, channel: int, required_peak: float) -> float:
        """Ajusta V/div (ou A/div) e confirma margem para o pico esperado.

        O display tem oito divisões verticais. Com offset zero, quatro divisões
        ficam disponíveis em cada polaridade. O alvo usa apenas três delas para
        absorver arredondamento de escala e pequena sobremodulação.
        """
        if channel not in self.channels:
            raise ValueError(f"Canal inválido: {channel}")
        if not np.isfinite(required_peak) or required_peak <= 0:
            raise ValueError("Pico esperado deve ser positivo e finito")
        channel_object = self.channels[channel]
        channel_object.offset = 0.0
        channel_object.scale = max(required_peak / 3.0, 1e-3)
        self.assert_no_errors(f"ajuste de escala do CH{channel}")
        actual_scale = float(channel_object.scale)
        if actual_scale * 4.0 < required_peak * 1.05:
            channel_object.scale = max(required_peak / 2.0, 1e-3)
            self.assert_no_errors(f"reajuste de escala do CH{channel}")
            actual_scale = float(channel_object.scale)
        if actual_scale * 4.0 < required_peak * 1.05:
            raise OscilloscopeError(
                f"CH{channel} cobre apenas +/-{actual_scale * 4.0:.3f}; "
                f"pico requerido {required_peak:.3f}"
            )
        return actual_scale

    def configure_acquisition(
        self,
        *,
        sample_rate_hz: float = 30_000.0,
        points: int = 6_000,
        duration_s: float = 0.2,
        pre_trigger_s: float = 0.0,
    ) -> None:
        if abs(sample_rate_hz * duration_s - points) > 1e-9:
            raise ValueError("sample_rate * duration deve ser igual ao número de pontos")
        if not 0.0 <= pre_trigger_s < duration_s:
            raise ValueError(f"pre_trigger_s deve estar entre 0 e {duration_s} s")
        # O firmware 07.30 entra em Digitizer quando POINts/SRATe recebem um
        # número. Digitizer não aceita referência horizontal diferente de
        # CENTer e 30 kSa/s pode estar abaixo da taxa física disponível. Para
        # manter o trigger no início dos 200 ms, usamos modo automático com
        # referência LEFT e reamostramos os dados adquiridos no download.
        # :TIMebase:POSition é "tempo do trigger até a referência de exibição"
        # (manual Keysight, cap. 35): pos = t_referencia - t_trigger. Com
        # REFerence LEFT, a referência é a borda esquerda da janela (nossa
        # amostra t=0 após o download). Para sobrar baseline ANTES do trigger
        # (ex.: antes de um SAG/SWELL disparado no próprio instante do
        # trigger), a borda esquerda precisa ficar CRONOLOGICAMENTE ANTES do
        # trigger, ou seja pos < 0 — por isso o sinal invertido abaixo. Um
        # pos positivo faz o oposto: a janela só começa a ser capturada
        # pre_trigger_s DEPOIS do trigger, pulando o próprio distúrbio (bug
        # que fazia o preflight nativo medir só o patamar recuperado, tanto
        # "dentro" quanto "fora" da janela do PULSe).
        for command in (
            ":STOP",
            ":ACQuire:TYPE NORMal",
            ":ACQuire:MODE RTIMe",
            ":ACQuire:DIGitizer OFF",
            ":TIMebase:MODE MAIN",
            f":TIMebase:RANGe {duration_s:.12g}",
            ":TIMebase:REFerence LEFT",
            f":TIMebase:POSition {(-pre_trigger_s) or 0.0:.12g}",
            ":ACQuire:POINts:ANALog:AUTO ON",
            ":ACQuire:SRATe:ANALog:AUTO ON",
            ":WAVeform:POINts:MODE NORMal",
            ":WAVeform:POINts 60000",
            ":WAVeform:FORMat BYTE",
            ":WAVeform:UNSigned ON",
        ):
            self.write(command)
            errors = self.check_errors()
            if errors:
                raise OscilloscopeError(
                    f"Keysight rejeitou {command!r} durante configuração da aquisição: {errors}"
                )
        actual_points = int(float(self.ask(":ACQuire:POINts:ANALog?")))
        actual_rate = float(self.ask(":ACQuire:SRATe:ANALog?"))
        actual_range = float(self.ask(":TIMebase:RANGe?"))
        # Em modo automático, estando parado, o firmware 07.30 informou 3000
        # pontos; uma aquisição SINGLE usa outra profundidade. A suficiência
        # real é validada pela preamble imediatamente após a captura.
        if actual_points <= 0 or actual_rate < sample_rate_hz * 0.995:
            raise OscilloscopeError(
                f"Aquisição insuficiente: {actual_points} pontos a {actual_rate} Sa/s; "
                f"taxa mínima {sample_rate_hz * 0.995} Sa/s"
            )
        if not np.isclose(actual_range, duration_s, rtol=0, atol=duration_s * 0.01):
            raise OscilloscopeError(
                f"Keysight aceitou janela {actual_range} s; esperado {duration_s} s"
            )

    def setup_external_trigger(
        self,
        *,
        level_v: float,
        probe_attenuation: float,
        range_v: float,
        slope: str = "POSitive",
    ) -> None:
        slope = slope.upper()
        if slope not in {"POSITIVE", "NEGATIVE", "EITHER", "ALTERNATE"}:
            raise ValueError(f"Slope inválido: {slope}")
        for command in (
            f":EXTernal:PROBe {probe_attenuation:.12g}",
            ":EXTernal:UNITs VOLT",
            f":EXTernal:RANGe {range_v:.12g}",
            ":TRIGger:HFReject OFF",
            ":TRIGger:MODE EDGE",
            ":TRIGger:SWEep NORMal",
            ":TRIGger:EDGE:SOURce EXTernal",
            f":TRIGger:EDGE:LEVel {level_v:.12g}",
            f":TRIGger:EDGE:SLOPe {slope}",
        ):
            self.write(command)
        self.assert_no_errors("trigger externo")
        actual_range = float(self.ask(":EXTernal:RANGe?"))
        if abs(level_v) >= actual_range:
            raise OscilloscopeError(
                f"Nível de trigger {level_v} V fora da faixa externa {actual_range} V"
            )

    def arm(self) -> None:
        self.ask(":AER?")
        self.ask(":TER?")
        self.write(":SINGle")

    def force_trigger(self) -> None:
        """Força uma aquisição no scope; não testa o caminho BNC externo."""
        self.write(":TRIGger:FORCe")

    def is_armed(self) -> bool:
        condition = int(float(self.ask(":OPERegister:CONDition?")))
        return bool(condition & 32)

    def wait_for_armed(self, timeout_s: float = 5.0, poll_s: float = 0.05) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.is_armed():
                return
            time.sleep(poll_s)
        raise TimeoutError("Keysight não entrou em WAIT FOR TRIGGER")

    def wait_for_trigger_complete(self, timeout_s: float = 5.0, poll_s: float = 0.05) -> None:
        deadline = time.monotonic() + timeout_s
        trigger_seen = False
        while time.monotonic() < deadline:
            # TER confirma que houve evento de trigger; o bit RUN (peso 8)
            # somente cai quando a aquisição SINGLE terminou. O guia Keysight
            # recomenda exatamente esse polling para um DUT de disparo único.
            trigger_seen = trigger_seen or int(float(self.ask(":TER?"))) == 1
            operation_condition = int(float(self.ask(":OPERegister:CONDition?")))
            if trigger_seen and not (operation_condition & 8):
                self.assert_no_errors("conclusão da aquisição")
                return
            time.sleep(poll_s)
        raise TimeoutError("Keysight não recebeu/concluiu o trigger externo")

    @property
    def sample_rate(self) -> float:
        return float(self.ask(":ACQuire:SRATe:ANALog?"))

    def get_waveform(self, channel: int, *, expected_points: int = 6000) -> Tuple[np.ndarray, np.ndarray]:
        if channel not in self.channels:
            raise ValueError(f"Canal inválido: {channel}")
        for command in (
            f":WAVeform:SOURce CHANnel{channel}",
            ":WAVeform:FORMat BYTE",
            ":WAVeform:UNSigned ON",
            ":WAVeform:POINts:MODE NORMal",
            ":WAVeform:POINts 60000",
        ):
            self.write(command)
        preamble_text = self.ask(":WAVeform:PREamble?").strip()
        fields = preamble_text.split(",")
        if len(fields) != 10:
            raise OscilloscopeError(f"Preamble inválida ({len(fields)} campos): {preamble_text!r}")
        preamble = [float(value) for value in fields]
        format_code, points = int(preamble[0]), int(preamble[2])
        if format_code != 0:
            raise OscilloscopeError(f"Formato da preamble é {format_code}; esperado BYTE=0")
        if points < expected_points:
            raise OscilloscopeError(
                f"Preamble declara somente {points} pontos; mínimo {expected_points}"
            )
        # PyMeasure 0.16 CommonBase.binary_values() usa o parser genérico do
        # Adapter e não a assinatura query_binary_values() do PyVISA. Para um
        # bloco IEEE 488.2 do Keysight, a conexão VISA deve remover o header.
        connection = getattr(self.adapter, "connection", None)
        query_binary_values = getattr(connection, "query_binary_values", None)
        if not callable(query_binary_values):
            raise OscilloscopeError("Adapter não expõe uma conexão PyVISA binária")
        raw = query_binary_values(
            ":WAVeform:DATA?",
            datatype="B",
            is_big_endian=False,
            container=np.array,
            header_fmt="ieee",
            expect_termination=True,
            data_points=points,
        )
        raw = np.asarray(raw, dtype=np.float64)
        if raw.shape != (points,):
            raise OscilloscopeError(
                f"Waveform CH{channel} contém {raw.size} pontos; preamble declarou {points}"
            )
        # O guia 4000 X-Series reserva esses códigos em BYTE: 0=hole,
        # 1=clipped low e 255=clipped high. Não salvar dados corrompidos.
        if np.any(raw == 0):
            raise OscilloscopeError(f"Waveform CH{channel} contém amostra ausente (código 0)")
        if np.any((raw == 1) | (raw == 255)):
            raise OscilloscopeError(f"Waveform CH{channel} sofreu clipping vertical")
        x_increment, x_origin, x_reference = preamble[4:7]
        y_increment, y_origin, y_reference = preamble[7:10]
        if not all(np.isfinite(value) for value in preamble):
            raise OscilloscopeError("Preamble contém NaN/Inf")
        time_axis = (
            (np.arange(points, dtype=np.float64) - x_reference) * x_increment
            + x_origin
        )
        values = ((raw - y_reference) * y_increment) + y_origin
        if not np.all(np.isfinite(values)) or np.ptp(time_axis) <= 0:
            raise OscilloscopeError("Waveform convertida contém valores inválidos")
        actual_rate = 1.0 / x_increment
        if actual_rate < 30_000.0:
            raise OscilloscopeError(
                f"Preamble indica somente {actual_rate} Sa/s; mínimo 30000 Sa/s"
            )
        time_axis -= time_axis[0]
        target_time = np.arange(expected_points, dtype=np.float64) / 30_000.0
        if time_axis[-1] + x_increment < 0.2 - (0.5 / 30_000.0):
            raise OscilloscopeError(
                f"Waveform cobre apenas {time_axis[-1] + x_increment:.9f} s; esperado 0.2 s"
            )
        target_values = np.interp(target_time, time_axis, values)
        return target_time, target_values

    def safe_stop(self) -> None:
        try:
            self.write(":STOP")
        except Exception:
            logger.exception("Não foi possível parar o Keysight")

    def close(self) -> None:
        self.safe_stop()
        # VISAAdapter.close() fecha o recurso. Não feche aqui o ResourceManager:
        # no backend Windows usado na bancada isso invalidou a sessão ASRL da
        # AMETEK, que ainda precisava receber OUTPUT OFF.
        self.adapter.close()
