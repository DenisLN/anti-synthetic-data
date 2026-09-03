"""Driver seguro para AMETEK MX30 via USB/COM virtual sobre PyVISA.

Comunicação baseada no manual BPS/MX/RS:
115200 baud confirmados na MX30 da bancada, 8 bits, LF e EOT separado após comandos.
"""

from __future__ import annotations

import logging
import math
import re
import threading
import time
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    import pyvisa
    from pyvisa.constants import BufferOperation, Parity, StopBits, VI_ASRL_FLOW_NONE
except ImportError:  # permite importar o modo simulado sem PyVISA
    pyvisa = None
    BufferOperation = Parity = StopBits = VI_ASRL_FLOW_NONE = None


logger = logging.getLogger("AmetekORM")


class AmetekORMError(Exception):
    pass


class ParameterOutOfBoundsError(AmetekORMError, ValueError):
    pass


class CommunicationError(AmetekORMError):
    pass


class InstrumentHardwareError(AmetekORMError):
    pass


def _normalized_identity(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


class AmetekMX30:
    """AMETEK MX30/3Pi usando a porta serial do Windows."""

    FS_HZ = 30000.0
    TRACE_POINTS = 1024
    CAPTURE_POINTS = 6000
    MAX_SOURCE_PEAK_V = 425.0
    # Teto documentado do CSINe nativo (cap. 6.4 do manual SCPI). Acima disso,
    # a classe 05 (HARMONICS) desvia para TRACe (gerar() + program_capture()).
    MAX_CSINE_THD_PCT = 20.0

    def __init__(
        self,
        port: str = "COM10",
        *,
        baudrate: int = 115200,
        timeout_s: float = 5.0,
        query_eot: bool = True,
        expected_model: str = "MX30",
        clear_user_waveforms: bool = False,
        max_voltage_rms: float = 10.0,
        max_peak_v: float = 100.0,
        max_current_a: float = 0.5,
        simulated: bool = False,
        visa_resource=None,
        resource_manager=None,
    ):
        self.port = port
        self.baudrate = int(baudrate)
        self.timeout_s = float(timeout_s)
        self.query_eot = bool(query_eot)
        self.expected_model = expected_model
        self.clear_user_waveforms = bool(clear_user_waveforms)
        self.max_voltage_rms = float(max_voltage_rms)
        self.max_peak_v = min(float(max_peak_v), self.MAX_SOURCE_PEAK_V)
        self.max_current_a = float(max_current_a)
        self.simulated = bool(simulated)
        self.resource_name = self._port_to_visa_resource(port)
        self._resource = visa_resource
        self._resource_manager = resource_manager
        self._owns_resource_manager = False
        self._connected = visa_resource is not None
        self._lock = threading.RLock()
        self._output_authorized = False
        self.idn = ""
        self.command_log: List[str] = []
        self.last_programmed_peak_v = 0.0
        self._last_cycles = 0
        self._sim: Dict[str, object] = {
            "output": False,
            "voltage": 0.0,
            "frequency": 50.0,
            "current": max_current_a,
            "trigger_state": "IDLE",
            "trace_names": set(),
            # Um contador por eixo (FUNCTION/VOLTAGE/DWELL/REPEAT) — cada
            # SOURce:LIST:* tem sua própria consulta :POINts?, independente
            # das outras (ver _simulate_write/_simulate_query).
            "list_points": {},
        }
        if not self.simulated and self._resource is None:
            self.connect()
        elif self.simulated:
            self.idn = "AMETEK,MX30-3Pi,SIMULATED,4.00"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    @property
    def is_connected(self) -> bool:
        return self.simulated or self._connected

    @staticmethod
    def _port_to_visa_resource(port: str) -> str:
        match = re.fullmatch(r"COM(\d+)", port.strip(), flags=re.IGNORECASE)
        if not match:
            raise ValueError(f"Porta serial Windows inválida: {port!r}")
        return f"ASRL{int(match.group(1))}::INSTR"

    def _configure_visa_resource(self) -> None:
        self._resource.baud_rate = self.baudrate
        self._resource.data_bits = 8
        self._resource.parity = Parity.none
        self._resource.stop_bits = StopBits.one
        self._resource.flow_control = VI_ASRL_FLOW_NONE
        self._resource.read_termination = "\n"
        self._resource.write_termination = "\n"
        self._resource.timeout = int(round(self.timeout_s * 1000.0))

    def _discard_input(self) -> None:
        if self._resource is None or BufferOperation is None:
            return
        try:
            self._resource.flush(BufferOperation.discard_read_buffer)
            self._resource.flush(BufferOperation.discard_receive_buffer)
        except Exception:
            # O descarte é apenas preventivo; alguns backends VISA não o
            # implementam para ASRL e a comunicação continua válida sem ele.
            logger.debug("Backend VISA não implementa descarte do buffer ASRL", exc_info=True)

    def connect(self) -> None:
        if self.simulated:
            return
        if pyvisa is None:
            raise ImportError("Instale PyVISA para comunicar com a AMETEK em COM10")
        if self.baudrate != 115200:
            raise ValueError("A MX30 da bancada foi confirmada em 115200 baud")
        try:
            if self._resource_manager is None:
                self._resource_manager = pyvisa.ResourceManager()
                self._owns_resource_manager = True
            self._resource = self._resource_manager.open_resource(self.resource_name)
            self._connected = True
            self._configure_visa_resource()
            self._discard_input()
            # Primeira ação: retirar potência antes até mesmo de consultar identificação.
            self._raw_write("OUTPut:STATe OFF")
            self.idn = self.query("*IDN?")
            if _normalized_identity(self.expected_model) not in _normalized_identity(self.idn):
                raise CommunicationError(
                    f"Instrumento inesperado em {self.port}: {self.idn!r}; "
                    f"esperado modelo contendo {self.expected_model!r}"
                )
            logger.info(
                "AMETEK identificada em %s (%s): %s", self.port, self.resource_name, self.idn
            )
        except Exception as exc:
            self._close_resource()
            if isinstance(exc, (CommunicationError, ImportError, ValueError)):
                raise
            raise CommunicationError(f"Falha ao abrir {self.port} a {self.baudrate} baud: {exc}") from exc

    def _close_resource(self) -> None:
        if self._resource is not None:
            try:
                self._resource.close()
            except Exception:
                logger.exception("Falha ao fechar recurso VISA da AMETEK")
            finally:
                self._resource = None
                self._connected = False
        if self._owns_resource_manager and self._resource_manager is not None:
            # Fechar um ResourceManager no backend VISA do Windows invalidou a
            # sessão USB do Keysight criada por outro adapter. O recurso ASRL
            # acima já foi fechado; o processo libera o manager ao terminar.
            self._resource_manager = None
            self._owns_resource_manager = False

    def disconnect(self) -> None:
        try:
            self.safe_shutdown()
        finally:
            self._close_resource()

    def _raw_write(self, command: str, *, append_eot: Optional[bool] = None) -> None:
        command = command.strip()
        if append_eot is None:
            # A USB serial da MX30 da bancada exige LF e uma transferência EOT
            # separada para executar também comandos sem resposta. Sem isso,
            # OUTPUT ON/OFF permanecia no buffer até a próxima consulta.
            append_eot = self.query_eot
        self.command_log.append(command)
        if self.simulated:
            self._simulate_write(command)
            return
        if self._resource is None or not self._connected:
            raise CommunicationError("Recurso VISA serial da AMETEK não está aberto")
        payload = (command + "\n").encode("ascii")
        try:
            self._resource.write_raw(payload)
            # A MX30 física somente respondeu quando EOT foi enviado em uma
            # segunda transferência, como no exemplo do manual.
            if append_eot:
                self._resource.write_raw(b"\x04")
        except Exception as exc:
            raise CommunicationError(f"Falha escrevendo {command!r}: {exc}") from exc

    def write(self, command: str) -> None:
        with self._lock:
            self._raw_write(command)

    def query(self, command: str) -> str:
        command = command.strip()
        with self._lock:
            if self.simulated:
                self.command_log.append(command)
                return self._simulate_query(command)
            if self._resource is None or not self._connected:
                raise CommunicationError("Recurso VISA serial da AMETEK não está aberto")
            try:
                self._discard_input()
                self._raw_write(command, append_eot=self.query_eot)
                response = self._resource.read()
            except Exception as exc:
                raise CommunicationError(f"Falha consultando {command!r}: {exc}") from exc
            if not response:
                raise CommunicationError(
                    f"Timeout aguardando resposta a {command!r} em {self.port}; "
                    "confirme COM10, driver USB virtual, 115200 baud e cabo USB da fonte"
                )
            return str(response).strip()

    # Comandos SOURce:LIST:* usados neste driver, mapeados para um eixo
    # próprio — cada eixo tem sua PRÓPRIA consulta :POINts? no instrumento
    # real (ver program_capture()), então o simulador precisa contar cada um
    # separadamente em vez de um único contador compartilhado.
    _LIST_WRITE_AXES = {
        "LIST:FUNCTION:SHAPE ": "FUNCTION",
        "LIST:VOLTAGE ": "VOLTAGE",
        "LIST:FREQUENCY ": "FREQUENCY",
        "LIST:DWELL ": "DWELL",
        "LIST:REPEAT ": "REPEAT",
    }
    _LIST_QUERY_AXES = {
        "LIST:FUNCTION:POINTS?": "FUNCTION",
        "LIST:VOLTAGE:POINTS?": "VOLTAGE",
        "LIST:FREQUENCY:POINTS?": "FREQUENCY",
        "LIST:DWELL:POINTS?": "DWELL",
        "LIST:REPEAT:POINTS?": "REPEAT",
    }

    @staticmethod
    def _strip_source_prefix(upper_command: str) -> str:
        prefix = "SOURCE:"
        return upper_command[len(prefix):] if upper_command.startswith(prefix) else upper_command

    @classmethod
    def _list_axis_for_write(cls, upper_command: str) -> Optional[str]:
        stripped = cls._strip_source_prefix(upper_command)
        for command_prefix, axis in cls._LIST_WRITE_AXES.items():
            if stripped.startswith(command_prefix):
                return axis
        return None

    @classmethod
    def _list_axis_for_points_query(cls, upper_command: str) -> Optional[str]:
        return cls._LIST_QUERY_AXES.get(cls._strip_source_prefix(upper_command))

    def _simulate_write(self, command: str) -> None:
        upper = command.upper()
        list_axis = self._list_axis_for_write(upper)
        if upper.startswith("OUTPUT:STATE "):
            self._sim["output"] = upper.endswith((" ON", " 1"))
        elif upper.startswith("VOLTAGE ") or upper.startswith("VOLT "):
            try:
                self._sim["voltage"] = float(command.split()[-1])
            except ValueError:
                pass
        elif upper.startswith("FREQUENCY ") or upper.startswith("FREQ "):
            try:
                self._sim["frequency"] = float(command.split()[-1])
            except ValueError:
                pass
        elif upper.startswith("CURRENT ") or upper.startswith("CURR "):
            try:
                self._sim["current"] = float(command.split()[-1])
            except ValueError:
                pass
        elif upper.startswith("TRACE:DEFINE ") or upper.startswith("TRAC:DEF "):
            self._sim["trace_names"].add(command.split()[-1].upper())
        elif list_axis is not None:
            self._sim["list_points"][list_axis] = len(command.split(None, 1)[1].split(","))
        elif upper.startswith("INIT"):
            self._sim["trigger_state"] = "ARM"
        elif upper == "*TRG":
            self._sim["trigger_state"] = "IDLE"
        elif upper in {"ABORT", "ABOR", "*RST"}:
            self._sim["trigger_state"] = "IDLE"

    def _simulate_query(self, command: str) -> str:
        upper = command.upper()
        if upper == "*IDN?":
            return self.idn or "AMETEK,MX30-3Pi,SIMULATED,4.00"
        if upper in {"SYSTEM:ERROR?", "SYST:ERR?"}:
            return '0,"No error"'
        if upper == "*OPC?":
            return "1"
        if upper in {"OUTPUT:STATE?", "OUTP?"}:
            return "1" if self._sim["output"] else "0"
        if upper in {"TRIGGER:STATE?", "TRIG:STATE?"}:
            return str(self._sim["trigger_state"])
        if upper == "TRACE:CATALOG?":
            return ",".join(sorted(self._sim["trace_names"]))
        list_axis = self._list_axis_for_points_query(upper)
        if list_axis is not None:
            return str(self._sim["list_points"].get(list_axis, 0))
        if upper.endswith(":POINTS?") or upper.endswith(":POIN?"):
            return "0"
        if "VOLTAGE" in upper or upper.startswith("VOLT"):
            return str(self._sim["voltage"])
        if "FREQUENCY" in upper or upper.startswith("FREQ"):
            return str(self._sim["frequency"])
        if "CURRENT" in upper or upper.startswith("CURR"):
            return str(self._sim["current"])
        return "0"

    def check_errors(self, max_errors: int = 20) -> List[Tuple[int, str]]:
        errors: List[Tuple[int, str]] = []
        for _ in range(max_errors):
            raw = self.query("SYSTem:ERRor?")
            try:
                code_text, message = raw.split(",", 1)
                code = int(code_text)
            except (ValueError, TypeError) as exc:
                raise CommunicationError(f"Resposta inválida de SYST:ERR?: {raw!r}") from exc
            if code == 0:
                return errors
            errors.append((code, message.strip().strip('"')))
        raise InstrumentHardwareError(f"Fila SCPI não esvaziou após {max_errors} erros: {errors}")

    def assert_no_errors(self, context: str) -> None:
        try:
            errors = self.check_errors()
        except CommunicationError as exc:
            raise CommunicationError(
                f"Falha verificando fila SCPI após {context}: {exc}"
            ) from exc
        if errors:
            raise InstrumentHardwareError(f"AMETEK reportou erros após {context}: {errors}")

    def authorize_output(self, authorized: bool) -> None:
        self._output_authorized = bool(authorized)

    @property
    def output_enabled(self) -> bool:
        if self.simulated:
            return bool(self._sim["output"])
        return self.query("OUTPut:STATe?").upper() in {"1", "ON"}

    @output_enabled.setter
    def output_enabled(self, state: bool) -> None:
        if state and not self._output_authorized:
            raise PermissionError("Saída AMETEK não autorizada pelo interlock de software")
        self.write(f"OUTPut:STATe {'ON' if state else 'OFF'}")

    def energize_baseline(self) -> None:
        """Liga a saída uma única vez, em modo FIXed na tensão/frequência base.

        Chamado uma vez no início da bateria (não a cada captura). O exemplo
        oficial do manual (cap. 6.4.2) liga a saída uma vez e dispara vários
        transientes em sequência sem desligar; ``program_capture`` conta com
        a saída já ligada e nunca a desliga entre capturas.
        """
        if self.simulated:
            self.output_enabled = True
            return
        if not self._output_authorized:
            raise PermissionError("Saída AMETEK não autorizada pelo interlock de software")
        self.output_enabled = True
        self.assert_no_errors("OUTPUT ON no baseline")
        relay_deadline = time.monotonic() + 5.0
        while time.monotonic() < relay_deadline:
            if self.output_enabled:
                return
            time.sleep(0.25)
        raise InstrumentHardwareError("MX30 não confirmou OUTPUT ON dentro de 5 s")

    @property
    def voltage(self) -> float:
        if self.simulated:
            return float(self._sim["voltage"])
        return float(self.query("SOURce:VOLTage:LEVel:IMMediate:AMPLitude?"))

    @voltage.setter
    def voltage(self, value: float) -> None:
        value = float(value)
        if not 0 <= value <= self.max_voltage_rms:
            raise ParameterOutOfBoundsError(
                f"Tensão {value} Vrms fora do limite de software 0..{self.max_voltage_rms}"
            )
        self.write(f"SOURce:VOLTage:LEVel:IMMediate:AMPLitude {value:.8g}")
        self._sim["voltage"] = value

    @property
    def frequency(self) -> float:
        if self.simulated:
            return float(self._sim["frequency"])
        return float(self.query("SOURce:FREQuency?"))

    @frequency.setter
    def frequency(self, value: float) -> None:
        value = float(value)
        if not 45.0 <= value <= 500.0:
            raise ParameterOutOfBoundsError(f"Frequência {value} Hz fora de 45..500 Hz")
        self.write(f"SOURce:FREQuency {value:.8g}")
        self._sim["frequency"] = value

    @property
    def current_limit(self) -> float:
        if self.simulated:
            return float(self._sim["current"])
        return float(self.query("SOURce:CURRent:LEVel:IMMediate:AMPLitude?"))

    @current_limit.setter
    def current_limit(self, value: float) -> None:
        value = float(value)
        if not 0 < value <= self.max_current_a:
            raise ParameterOutOfBoundsError(
                f"Limite {value} A fora do permitido 0..{self.max_current_a} A"
            )
        self.write(f"SOURce:CURRent:LEVel:IMMediate:AMPLitude {value:.8g}")
        self._sim["current"] = value

    def trigger_step(self, voltage_rms: float) -> None:
        """Programa um STEP para ``voltage_rms`` no próximo *TRG.

        Usado tanto para gerar o pulso de trigger (BOT) de uma captura sem
        distúrbio (STEP para o mesmo valor já em regime) quanto para retomar
        o nível base depois de um efeito imediato (ex.: DC_OFFSET).
        """
        voltage_rms = float(voltage_rms)
        if not 0 <= voltage_rms <= self.max_voltage_rms:
            raise ParameterOutOfBoundsError(
                f"Tensão {voltage_rms} Vrms fora do limite de software 0..{self.max_voltage_rms}"
            )
        # FREQuency:MODE é um eixo independente de VOLTage:MODE (cap. 4.13/4.17
        # do manual SCPI): um LIST de frequência residual de uma captura
        # anterior (ex.: classe 18/FREQUENCY_DRIFT) continua sendo aplicado a
        # cada *TRG mesmo com VOLTage:MODE em STEP. Força FIXed aqui, único
        # ponto por onde toda captura nativa sem TRACe passa antes de armar.
        self.write("SOURce:FREQuency:MODE FIXed")
        self.write("VOLTage:MODE STEP")
        self.write(f"VOLTage:TRIGgered {voltage_rms:.8g}")

    def trigger_pulse(self, voltage_rms: float, *, width_s: float) -> None:
        """Programa um PULSe nativo: cai/sobe para ``voltage_rms`` por ``width_s``
        a partir do *TRG, e retorna ao nível imediato em seguida. Usado por
        SAG/SWELL/INTERRUPTION (cap. 6.4.3 do manual)."""
        voltage_rms = float(voltage_rms)
        width_s = float(width_s)
        if not 0 <= voltage_rms <= self.max_voltage_rms:
            raise ParameterOutOfBoundsError(
                f"Tensão {voltage_rms} Vrms fora do limite de software 0..{self.max_voltage_rms}"
            )
        if not width_s > 0:
            raise ParameterOutOfBoundsError(f"Duração do pulso deve ser positiva; recebido {width_s}")
        # Ver comentário equivalente em trigger_step(): neutraliza um LIST de
        # frequência residual antes de armar este PULSe.
        self.write("SOURce:FREQuency:MODE FIXed")
        self.write("VOLTage:MODE PULSe")
        self.write(f"VOLTage:TRIGgered {voltage_rms:.8g}")
        self.write(f"PULSe:WIDTh {width_s:.8g}")

    def configure_harmonics_csine(self, thd_pct: float) -> None:
        """Programa o gerador nativo de senoide clipada (CSINe) para o THD
        pedido, em percentual. Recusa acima de ``MAX_CSINE_THD_PCT`` — nesse
        caso o experimento deve sintetizar a forma em Python e subir por
        ``program_capture`` (ver classe 05, ``usar_trace``)."""
        thd_pct = float(thd_pct)
        if not 0 < thd_pct <= self.MAX_CSINE_THD_PCT:
            raise ParameterOutOfBoundsError(
                f"THD {thd_pct}% fora do teto do CSINe nativo (0..{self.MAX_CSINE_THD_PCT}%)"
            )
        # A forma abreviada 'CSINe' (a documentada em cap. 4.14/6.2.7 do
        # manual para o parâmetro de FUNCtion:SHAPe) é rejeitada pela Rev.
        # 5.53 com -256 "File name not found" — a mesma forma curta que o
        # cap. 4.25/Trace Subsystem usa para descrever a entrada pré-definida
        # do catálogo (TRACe:CATalog?) é 'CSINusoid' (nome completo); a Rev.
        # 5.53 resolve FUNCtion:SHAPe como lookup no catálogo de waveforms e
        # só reconhece o nome completo. Ordem também alinhada ao exemplo
        # funcional do cap. 6.2.7: seleciona a forma primeiro, só depois
        # ajusta o nível de clipping.
        self.write("SOURce:FUNCtion:SHAPe CSINusoid")
        # Trocar a forma de onda recarrega a tabela e deixa a Rev. 5.53 MUDA
        # por alguns segundos. Enquanto o comando falhava com -256 isso não
        # aparecia (a fonte rejeitava na hora, sem trabalho nenhum); com ele
        # funcionando, a consulta seguinte estourava o timeout do VISA e
        # derrubava a bateria na classe 05/HARMONICS. Espera determinística:
        # segue assim que a fonte responder de novo. Com *IDN? (padrão), NÃO
        # com SOURce:FUNCtion:SHAPe? — ver aguardar_resposta().
        self.aguardar_resposta()
        self.write(f"SOURce:FUNCtion:SHAPe:CSINusoid {thd_pct:.8g}")

    def select_sine_shape(self) -> None:
        """Volta a forma de onda para a senoide pré-definida. Contrapartida de
        ``configure_harmonics_csine()``: ``FUNCtion:SHAPe`` é estado
        PERMANENTE, não um transiente — a senoide clipada continua valendo
        para todas as capturas seguintes até alguém trocar de volta."""
        self.write("SOURce:FUNCtion:SHAPe SINusoid")
        self.aguardar_resposta()

    def disable_dc_offset(self) -> None:
        """Contrapartida de ``enable_dc_offset()``: zera o offset e volta ao
        modo AC puro. Como a forma de onda, o offset e o ``SOURce:MODE ACDC``
        são estado permanente e continuariam aplicados nas capturas
        seguintes."""
        self.write("SOURce:VOLTage:OFFSet 0")
        self.write("SOURce:MODE AC")
        self.aguardar_resposta()

    def restaurar_forma_e_modo_padrao(self) -> None:
        """Desfaz todo o estado PERMANENTE que uma classe possa ter deixado
        ligado: forma de onda (``FUNCtion:SHAPe``) e modo/offset da saída
        (``SOURce:MODE``/``VOLTage:OFFSet``).

        Nada disso é transiente — continua valendo para as capturas seguintes
        até alguém trocar de volta. Sem isto, a classe 05 (HARMONICS) deixa a
        senoide CLIPADA ligada e a 19 (DC_OFFSET) deixa o offset e o modo
        ACDC ligados para quem vier depois. As classes waveform se salvam por
        acaso (``program_capture()`` reprograma forma e modo antes de cada
        captura); as nativas, não."""
        self.select_sine_shape()
        self.disable_dc_offset()

    def frequency_drift_list(
        self, start_hz: float, end_hz: float, *, voltage_rms: float, dwell_s: float,
    ) -> None:
        """Programa uma rampa de frequência aproximada por 2 pontos de
        ``LIST:FREQuency`` (início/fim), cada um com duração ``dwell_s``.
        Usado pela classe 18 (FREQUENCY_DRIFT)."""
        start_hz, end_hz, voltage_rms, dwell_s = (
            float(start_hz), float(end_hz), float(voltage_rms), float(dwell_s)
        )
        for label, value in (("start_hz", start_hz), ("end_hz", end_hz)):
            if not 45.0 <= value <= 500.0:
                raise ParameterOutOfBoundsError(f"{label} {value} Hz fora de 45..500 Hz")
        if not 0 <= voltage_rms <= self.max_voltage_rms:
            raise ParameterOutOfBoundsError(
                f"Tensão {voltage_rms} Vrms fora do limite de software 0..{self.max_voltage_rms}"
            )
        if not dwell_s > 0:
            raise ParameterOutOfBoundsError(f"Dwell deve ser positivo; recebido {dwell_s}")
        self.write("FREQuency:MODE LIST")
        self.write(f"LIST:FREQuency {start_hz:.8g},{end_hz:.8g}")
        self.write(f"LIST:VOLTage {voltage_rms:.8g},{voltage_rms:.8g}")
        self.write(f"LIST:DWELl {dwell_s:.8g},{dwell_s:.8g}")
        # Rev. 5.53 rejeita ':COUNt' (-113 Undefined header) e também rejeita
        # sem o prefixo 'SOURce:' — confirmado em preflight_new.py
        # --list-diagnostics: só 'SOURce:LIST:REPeat' (sem ':COUNt') é aceito.
        self.write("SOURce:LIST:REPeat 1,1")
        self.write("LIST:COUNt 1")
        self.write("LIST:STEP AUTO")
        self.write("VOLTage:MODE LIST")

    def enable_dc_offset(self, offset_v: float, *, ac_peak_v: float) -> None:
        """Liga o modo ACDC e programa um offset contínuo permanente de
        ``offset_v``. ``ac_peak_v`` é o pico AC que vai conviver com o offset
        (a base senoidal); a soma dos dois nunca pode exceder ``max_peak_v`` —
        diferente do AC puro, aqui o pico físico real é offset + amplitude AC,
        não só a amplitude AC."""
        offset_v = float(offset_v)
        ac_peak_v = float(ac_peak_v)
        combined_peak_v = abs(offset_v) + ac_peak_v
        if combined_peak_v > self.max_peak_v:
            raise ParameterOutOfBoundsError(
                f"Offset {offset_v:.3f} V + pico AC {ac_peak_v:.3f} V = {combined_peak_v:.3f} V "
                f"excede o limite de pico {self.max_peak_v:.3f} V"
            )
        self.write("SOURce:MODE ACDC")
        # Trocar SOURce:MODE também deixa a fonte ocupada — mesma razão do
        # aguardar_resposta() em configure_harmonics_csine(). Com *IDN?: a
        # Rev. 5.53 não implementa SOURce:MODE? como query (-113).
        self.aguardar_resposta()
        self.write(f"SOURce:VOLTage:OFFSet {offset_v:.8g}")

    def _query_tolerante(self, command: str) -> Optional[str]:
        """Consulta que devolve ``None`` em vez de levantar quando a fonte não
        respondeu dentro do timeout do VISA.

        A Rev. 5.53 fica MUDA por vários segundos depois de comandos que
        recarregam a tabela de forma de onda (``FUNCtion:SHAPe``) ou trocam o
        modo da saída (``SOURce:MODE AC/ACDC``) — o mesmo motivo pelo qual
        ``TRACe:DEFine`` precisa de ~3 s e ``TRACe:DELete:ALL`` de ~15 s. Nos
        laços de espera isso é transitório e esperado: quem chama continua
        tentando até o SEU próprio deadline, em vez de abortar a bateria
        inteira de 20 classes na primeira consulta que estourou. O deadline
        de quem chama continua finito, então um cabo realmente solto ainda
        falha — só que com mensagem própria, não com um traceback de VISA."""
        try:
            return self.query(command).strip().upper()
        except CommunicationError as exc:
            logger.debug("Consulta %r sem resposta (tentando de novo): %s", command, exc)
            return None

    def aguardar_resposta(self, command: str = "*IDN?", timeout_s: float = 20.0) -> None:
        """Bloqueia até a fonte voltar a responder ``command``.

        Espera determinística (não um sleep adivinhado) para usar depois de um
        comando que deixa a Rev. 5.53 ocupada: retorna assim que a fonte
        responde de novo. Sem isso, quem chama a seguir paga o timeout cheio
        do VISA em cada consulta.

        Use SEMPRE o ``*IDN?`` padrão, a menos que a query escolhida seja
        comprovadamente suportada por esta revisão. Só interessa saber SE a
        fonte voltou a falar, não o valor — e uma query com header não
        implementado é pior que inútil: a Rev. 5.53 não responde nada (o
        timeout inteiro é desperdiçado) e ainda deixa ``-113 "Undefined
        header"`` na fila, que estoura depois, atribuído ao próximo comando
        que consultar a fila. Foi o que aconteceu na bancada com
        ``SOURce:FUNCtion:SHAPe?`` e ``SOURce:MODE?``: os dois aceitam a
        forma de COMANDO, mas não existem como QUERY."""
        if self.simulated:
            return
        deadline = time.monotonic() + float(timeout_s)
        while time.monotonic() < deadline:
            if self._query_tolerante(command) is not None:
                return
            time.sleep(0.05)
        raise CommunicationError(
            f"AMETEK não voltou a responder {command!r} em {timeout_s:.1f} s; "
            f"confirme {self.port}, cabo USB e alimentação da fonte"
        )

    def wait_ready(self, settle_s: float = 0.25) -> None:
        """Aguarda comandos imediatos sem depender de ``*OPC?``.

        A MX30-3Pi Rev. 5.53 da bancada responde a ``*IDN?`` pela USB
        virtual serial, mas não respondeu a ``*OPC?`` mesmo com o EOT exigido
        pelo protocolo. Os comandos usados no baseline são imediatos. A espera
        local é finita e, logo depois, a fila SCPI e OUTPUT OFF são consultados.
        """
        settle_s = float(settle_s)
        if not 0.0 <= settle_s <= 2.0:
            raise ValueError("Espera de estabilização deve estar entre 0 e 2 s")
        if not self.simulated:
            time.sleep(settle_s)

    def configure_safe_baseline(
        self,
        *,
        voltage_range_rms: float,
        voltage_high_vp: float,
        current_limit_a: float,
        protection_delay_s: float,
        frequency_hz: float,
    ) -> None:
        # VOLTage:HIGH na AMETEK MX30 é um limite de PICO em Vp — não Vrms.
        # O firmware rejeita (erro 14) qualquer saída cujo pico exceda esse valor.
        range_peak_v = voltage_range_rms * math.sqrt(2.0)
        if voltage_high_vp > self.max_peak_v + 1e-6:
            raise ParameterOutOfBoundsError(
                f"VOLTage:HIGH {voltage_high_vp:.3f} Vp excede o limite de pico do software "
                f"{self.max_peak_v:.3f} Vp"
            )
        if voltage_high_vp + 1e-6 < self.max_peak_v:
            raise ParameterOutOfBoundsError(
                f"VOLTage:HIGH {voltage_high_vp:.3f} Vp abaixo do pico autorizado "
                f"{self.max_peak_v:.3f} Vp"
            )
        if voltage_high_vp > range_peak_v + 1e-6:
            raise ParameterOutOfBoundsError(
                f"VOLTage:HIGH {voltage_high_vp:.3f} Vp excede a capacidade de pico "
                f"do range {voltage_range_rms} Vrms ({range_peak_v:.3f} Vp)"
            )
        if not 0.1 <= protection_delay_s <= 5.0:
            raise ParameterOutOfBoundsError("Delay de proteção deve estar entre 0,1 e 5 s")
        self.output_enabled = False
        # Limpa erros antigos somente depois de ordenar OUTPUT OFF; a leitura
        # de estado ao final confirma que a saída realmente permaneceu inativa.
        self.write("*CLS")
        commands = (
            "ABORt",
            "INSTrument:COUPle ALL",
            "SOURce:MODE AC",
            f"SOURce:VOLTage:RANGe {voltage_range_rms:.8g}",
            f"SOURce:VOLTage:HIGH {voltage_high_vp:.8g}",
            f"SOURce:CURRent {current_limit_a:.8g}",
            "SOURce:CURRent:PROTection:STATe ON",
            f"SOURce:CURRent:PROTection:DELay {protection_delay_s:.8g}",
            "SOURce:FUNCtion:SHAPe SINusoid",
            "FUNCtion:MODE FIXed",
            "VOLTage:MODE FIXed",
            "SOURce:FREQuency:MODE FIXed",
            "SOURce:FREQuency:SLEW MAXimum",
            "SOURce:VOLTage:SLEW MAXimum",
            f"SOURce:FREQuency {frequency_hz:.8g}",
            "SOURce:VOLTage 0",
            "TRIGger:SOURce BUS",
            "TRIGger:SYNChronize:SOURce PHASe",
            "TRIGger:SYNChronize:PHASe 0",
            "OUTPut:TTLTrg:MODE TRIG",
            "OUTPut:TTLTrg:SOURce BOT",
            "OUTPut:TTLTrg ON",
        )
        for command in commands:
            self.write(command)
            # A Rev. 5.53 pode não implementar todos os cabeçalhos das revisões
            # mais novas do manual. Identifique imediatamente o comando
            # rejeitado, sem continuar configurando a partir de estado ambíguo.
            errors = self.check_errors()
            if errors:
                raise InstrumentHardwareError(
                    f"AMETEK rejeitou {command!r} durante baseline seguro: {errors}"
                )
        self.wait_ready()
        if self.output_enabled:
            raise InstrumentHardwareError("AMETEK continuou com saída ligada após baseline")

    def clear_all_traces(self) -> None:
        """Apaga todas as TRACEs de usuário. Só pode ser chamada com OUTPUT OFF,
        antes de ``energize_baseline()`` — a saída fica ligada durante toda a
        bateria depois disso e ``TRACe:DELete:ALL`` recusa com OUTPUT ligado."""
        if self.simulated:
            self._sim["trace_names"].clear()
            return
        if self.output_enabled:
            raise InstrumentHardwareError("Recusado TRACe:DELete:ALL porque OUTPUT está ligado")
        self.write("TRACe:DELete:ALL")
        # A MX30-3Pi Rev. 5.53 manteve a interface ocupada por mais de seis
        # segundos ao apagar um catálogo cheio. Não consulte SYST:ERR?
        # durante a gravação da Flash; aguarde e valide pelo catálogo.
        time.sleep(15.0)

    def _ensure_trace_slots(self, trace_names: Sequence[str]) -> None:
        catalog = {
            token.strip().strip('"').upper()
            for token in self.query("TRACe:CATalog?").split(",")
            if token.strip()
        }
        for name in trace_names:
            if name not in catalog:
                # Gravação em Flash: com N nomes ausentes, isso sozinho leva
                # N*3s SEM nenhuma resposta do instrumento no meio — sem este
                # log, esse intervalo parece uma trava em vez de trabalho
                # esperado (só ocorre a definição de cada TRACE uma vez; nas
                # próximas chamadas já está no catálogo).
                logger.info("Definindo TRACE %s (grava na Flash; ~3 s)...", name)
                self.write(f"TRACe:DEFine {name}")
                # O manual cita ~500 ms, mas a Rev. 5.53 permaneceu ocupada por
                # mais tempo ao gravar Flash; use margem conservadora.
                if not self.simulated:
                    time.sleep(3.0)
                self.assert_no_errors(f"definição da TRACE {name}")
                catalog.add(name)

    @staticmethod
    def _resample_cycle(cycle: np.ndarray) -> np.ndarray:
        source_x = np.arange(len(cycle), dtype=np.float64) / len(cycle)
        target_x = np.arange(AmetekMX30.TRACE_POINTS, dtype=np.float64) / AmetekMX30.TRACE_POINTS
        return np.interp(target_x, source_x, cycle)

    def program_capture(
        self,
        waveform_pu: Sequence[float],
        *,
        base_voltage_rms: float,
        frequency_hz: float,
        dc_offset_pu: float = 0.0,
    ) -> None:
        waveform = np.asarray(waveform_pu, dtype=np.float64)
        if waveform.shape != (self.CAPTURE_POINTS,) or not np.all(np.isfinite(waveform)):
            raise ValueError("A captura para a AMETEK deve conter exatamente 6000 valores finitos")
        physical_peak = float(np.max(np.abs(waveform)) * base_voltage_rms * math.sqrt(2.0))
        if physical_peak > self.max_peak_v:
            logger.warning(
                "Pico calculado %.3f V excede limite %.3f V; prosseguindo sem carga.",
                physical_peak, self.max_peak_v,
            )
        # pontos_por_ciclo é o tamanho, em amostras, de UM período fechado da
        # onda na frequência que será programada. Cada TRACE representa
        # exatamente um ciclo (o manual exige 1024 pontos = 1 ciclo por
        # forma); um pedaço que não seja um ciclo fechado tem viés DC real e,
        # ao ser normalizado, gera pico inflado e descontinuidade de fase na
        # troca de passo do LIST (bug corrigido: antes fixo em 600 amostras,
        # que só fecha um ciclo a 50 Hz).
        pontos_por_ciclo_f = self.FS_HZ / frequency_hz
        pontos_por_ciclo = round(pontos_por_ciclo_f)
        if abs(pontos_por_ciclo_f - pontos_por_ciclo) > 1e-6:
            raise ValueError(
                f"FS_HZ/frequency_hz ({self.FS_HZ}/{frequency_hz}) não é um número inteiro "
                "de amostras por ciclo"
            )
        if self.CAPTURE_POINTS % pontos_por_ciclo != 0:
            raise ValueError(
                f"{self.CAPTURE_POINTS} amostras não dividem em ciclos inteiros de "
                f"{pontos_por_ciclo} amostras (frequency_hz={frequency_hz})"
            )
        ciclos = self.CAPTURE_POINTS // pontos_por_ciclo
        trace_names = tuple(f"TCC{index:02d}" for index in range(ciclos))

        # ABORt aqui não desliga OUTPUT (a saída fica ligada durante toda a
        # bateria — ver energize_baseline()). Só reseta o sistema de trigger.
        self.write("ABORt")
        # Retorna ao modo FIXed antes de reprogramar o LIST. O Rev 5.53
        # rejeita (-113) comandos LIST quando o instrumento ainda está em
        # FUNCtion:MODE LIST de uma captura anterior. *CLS limpa erros
        # residuais acumulados entre experimentos.
        self.write("*CLS")
        self.write("FUNCtion:MODE FIXed")
        self.write("VOLTage:MODE FIXed")
        self.assert_no_errors("reset para modo FIXed")
        self.write(f"SOURce:MODE {'ACDC' if dc_offset_pu else 'AC'}")
        self.write(f"SOURce:FREQuency {frequency_hz:.8g}")
        self.write("SOURce:FREQuency:MODE FIXed")
        self.write("SOURce:FUNCtion:SHAPe SINusoid")
        self.write(f"SOURce:VOLTage {base_voltage_rms:.8g}")
        if dc_offset_pu:
            offset_v = dc_offset_pu * base_voltage_rms * math.sqrt(2.0)
            self.write(f"SOURce:VOLTage:OFFSet {offset_v:.8g}")
        self._ensure_trace_slots(trace_names)

        dc_component = float(dc_offset_pu)
        list_voltages: List[float] = []
        reconstructed_peak_v = abs(dc_component) * base_voltage_rms * math.sqrt(2.0)
        for index, name in enumerate(trace_names):
            start = index * pontos_por_ciclo
            cycle = waveform[start : start + pontos_por_ciclo] - dc_component
            cycle_rms_pu = float(np.sqrt(np.mean(np.square(cycle))))
            voltage_rms = base_voltage_rms * math.sqrt(2.0) * cycle_rms_pu
            if voltage_rms > self.max_voltage_rms:
                logger.warning(
                    "Ciclo %d: %.3f Vrms acima do limite configurado %.3f Vrms; aceito.",
                    index, voltage_rms, self.max_voltage_rms,
                )
            list_voltages.append(voltage_rms)
            trace = self._resample_cycle(cycle)
            trace -= np.mean(trace)
            scale = float(np.max(np.abs(trace)))
            if scale < 1e-12:
                trace = np.zeros(self.TRACE_POINTS, dtype=np.float64)
            else:
                trace /= scale
                # O pico físico real do ciclo reconstruído é o pico em pu
                # (scale, antes da normalização) multiplicado pela tensão base
                # de pico. A abordagem anterior (voltage_rms / trace_rms)
                # infla incorretamente o resultado porque voltage_rms já
                # incorpora o fator sqrt(2), levando a uma superestimativa de
                # ~17% para senoide de 60 Hz reamostrada a 1024 pontos.
                cycle_peak_v = scale * base_voltage_rms * math.sqrt(2.0)
                reconstructed_peak_v = max(
                    reconstructed_peak_v,
                    cycle_peak_v + abs(dc_component) * base_voltage_rms * math.sqrt(2.0),
                )
                if reconstructed_peak_v > self.max_peak_v:
                    logger.warning(
                        "TRACE reconstruída atingiria %.3f Vp, acima do limite %.3f Vp; prosseguindo.",
                        reconstructed_peak_v, self.max_peak_v,
                    )
            values = ",".join(f"{value:.8g}" for value in trace)
            self.write(f"TRACe:DATA {name},{values}")
            # A transferência serial em 115200 baud na Rev. 5.53 pode deixar o buffer ocupado
            # se checado imediatamente via SYST:ERR?. Limpamos com *CLS e aguardamos o processamento.
            if not self.simulated:
                time.sleep(1.0)
                self.write("*CLS")

        # DWELl = 1 período exato (1/frequency_hz), não um valor fixo: cada
        # TRACE precisa terminar exatamente quando o ciclo real dela termina,
        # senão o próximo passo do LIST começa no meio de um ciclo.
        dwell_s = pontos_por_ciclo / self.FS_HZ
        names = ",".join(trace_names)
        voltages = ",".join(f"{value:.8g}" for value in list_voltages)
        dwells = ",".join(f"{dwell_s:.10g}" for _ in trace_names)
        repeats = ",".join("1" for _ in trace_names)
        # Cada comando de dados de LISTA é confirmado IMEDIATAMENTE pela sua
        # própria consulta ":POINts?" (write seguido de query, sem delay
        # adivinhado) — se um comando não "pegar" (ex.: o firmware ainda
        # processando o anterior), o erro aponta exatamente qual comando
        # falhou, em vez de só descobrir no fim que algo deu errado.
        # Diferente de TRACe:DATA (gravação em Flash, sem query dedicada no
        # manual — ver o time.sleep(1.0) acima), estes comandos SOURce:LIST:*
        # são apenas configuração em RAM e têm consulta ":POINts?" própria.
        expected = len(trace_names)
        list_data_commands = (
            (f"SOURce:LIST:FUNCtion:SHAPe {names}", "SOURce:LIST:FUNCtion:POINts?"),
            (f"SOURce:LIST:VOLTage {voltages}", "SOURce:LIST:VOLTage:POINts?"),
            (f"SOURce:LIST:DWELl {dwells}", "SOURce:LIST:DWELl:POINts?"),
        )
        for command, points_query in list_data_commands:
            self.write(command)
            errors = self.check_errors()
            if errors:
                raise InstrumentHardwareError(
                    f"AMETEK rejeitou {command!r} durante programação da lista: {errors}"
                )
            actual = int(float(self.query(points_query)))
            if actual != expected:
                raise InstrumentHardwareError(
                    f"{points_query} retornou {actual} logo após {command!r}; esperado {expected}"
                )
        for command in (
            # Rev. 5.53 rejeita ':COUNt' (-113 Undefined header); confirmado
            # em preflight_new.py --list-diagnostics testando as 4 variantes
            # de cabeçalho — só esta (com 'SOURce:', sem ':COUNt') é aceita,
            # mesmo o manual documentando ':COUNt' como sufixo válido.
            f"SOURce:LIST:REPeat {repeats}",
            "SOURce:LIST:COUNt 1",
            "SOURce:LIST:STEP AUTO",
            "FUNCtion:MODE LIST",
            "VOLTage:MODE LIST",
            "TRIGger:SOURce BUS",
            "TRIGger:SYNChronize:SOURce PHASe",
            "TRIGger:SYNChronize:PHASe 0",
            "OUTPut:TTLTrg:MODE TRIG",
            "OUTPut:TTLTrg:SOURce BOT",
            "OUTPut:TTLTrg ON",
        ):
            self.write(command)
            errors = self.check_errors()
            if errors:
                raise InstrumentHardwareError(
                    f"AMETEK rejeitou {command!r} durante programação da lista: {errors}"
                )
        self.last_programmed_peak_v = reconstructed_peak_v
        self._last_cycles = ciclos
        # A saída fica ligada durante toda a bateria (energize_baseline() é
        # chamado uma vez, fora daqui). Se o ABORt/reprogramação acima
        # derrubou o relé por algum motivo, religa aqui — já estamos em modo
        # LIST com a TRACE nova carregada, então ligar aqui só expõe o nível
        # imediato (o transiente só ocorre depois de armar+disparar).
        if self._output_authorized and not self.output_enabled:
            logger.warning("OUTPUT caiu durante a reprogramação da lista; religando.")
            self.output_enabled = True
            self.assert_no_errors("religar OUTPUT após reprogramação da lista")

    def arm(self, timeout_s: float = 20.0) -> None:
        """Arma o sistema de trigger para um transiente já configurado (PULSe/STEP/CSINe
        aplicado a nível imediato, ou LIST). Genérico — sem diagnóstico específico de LIST;
        use arm_transient() para uma captura TRACe/LIST completa com esse diagnóstico.

        Usa ``_query_tolerante``: o comando que configurou o transiente pode
        ter deixado a fonte muda por alguns segundos (ver a docstring de
        ``_query_tolerante``), e o timeout do VISA é menor que este deadline —
        sem tolerar a consulta que estoura, a PRIMEIRA tentativa derrubava a
        bateria inteira (visto na bancada na classe 05/HARMONICS, logo depois
        de ``FUNCtion:SHAPe CSINusoid``)."""
        idle_deadline = time.monotonic() + timeout_s
        last_state = ""
        while time.monotonic() < idle_deadline:
            state = self._query_tolerante("TRIGger:STATe?")
            if state is None:
                continue
            last_state = state
            if last_state.startswith("IDLE"):
                break
            time.sleep(0.05)
        else:
            raise TimeoutError(
                f"AMETEK não estava IDLE antes do INIT em {timeout_s:.1f} s; "
                f"último estado={last_state!r}"
            )
        self.write("INITiate:IMMediate")
        self.assert_no_errors("comando INITiate:IMMediate")
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            state = self._query_tolerante("TRIGger:STATe?")
            if state is None:
                continue
            last_state = state
            if last_state.startswith(("ARM", "WTRIG")):
                return
            time.sleep(0.05)
        raise TimeoutError(f"AMETEK não entrou em ARM/WTRIG; último estado={last_state!r}")

    def arm_transient(self, timeout_s: float = 20.0) -> None:
        # program_capture() já envia ABORt antes de configurar a lista. Não
        # repita aqui: na MX30-3Pi Rev. 5.53, um novo ABORt também restaurou
        # FUNC/VOLT:MODE FIX e OUTPUT OFF, destruindo a configuração preparada.
        idle_deadline = time.monotonic() + timeout_s
        last_state = ""
        while time.monotonic() < idle_deadline:
            # Tolera consulta sem resposta (ver arm()/_query_tolerante): a
            # lista recém-programada por program_capture() envia 12 TRACe:DATA
            # de 1024 pontos pela serial e pode deixar a fonte ocupada.
            state = self._query_tolerante("TRIGger:STATe?")
            if state is None:
                continue
            last_state = state
            if last_state.startswith("IDLE"):
                break
            time.sleep(0.05)
        else:
            raise TimeoutError(
                f"AMETEK não estava IDLE antes do INIT em {timeout_s:.1f} s; "
                f"último estado={last_state!r}"
            )
        diagnostics = {
            "output": self.query("OUTPut:STATe?"),
            "function_mode": self.query("FUNCtion:MODE?"),
            "voltage_mode": self.query("VOLTage:MODE?"),
            "frequency_mode": self.query("SOURce:FREQuency:MODE?"),
            "function_points": self.query("SOURce:LIST:FUNCtion:POINts?"),
            "voltage_points": self.query("SOURce:LIST:VOLTage:POINts?"),
            "dwell_points": self.query("SOURce:LIST:DWELl:POINts?"),
            "repeat_points": self.query("SOURce:LIST:REPeat:POINts?"),
            "trigger_source": self.query("TRIGger:SOURce?"),
        }
        expected_points = str(self._last_cycles)
        expected_text = {
            "output": {"1", "ON"},
            "function_mode": {"LIST"},
            "voltage_mode": {"LIST"},
            "frequency_mode": {"FIX", "FIXED"},
            "function_points": {expected_points},
            "voltage_points": {expected_points},
            "dwell_points": {expected_points},
            # A Rev. 5.53 retorna 1 para REPeat:POINts mesmo quando recebeu a
            # lista de valores unitários; um único valor é válido e se aplica
            # implicitamente a todos os pontos.
            "repeat_points": {"1", expected_points},
            "trigger_source": {"BUS"},
        }
        invalid = {
            key: value
            for key, value in diagnostics.items()
            if value.strip().upper() not in expected_text[key]
        }
        if invalid:
            raise InstrumentHardwareError(
                f"Configuração transient lida da MX30 é inválida: {invalid}; "
                f"diagnóstico completo={diagnostics}"
            )
        # A seção 6.5.2 do manual prescreve INITiate:IMMediate para iniciar uma
        # única ação. Com TRIGger:SOURce BUS, isso arma; o evento continua sendo
        # fornecido posteriormente por *TRG.
        self.write("INITiate:IMMediate")
        try:
            self.assert_no_errors("comando INITiate:IMMediate de armamento transient")
        except InstrumentHardwareError as exc:
            raise InstrumentHardwareError(
                f"{exc}; configuração antes do INIT={diagnostics}"
            ) from exc
        deadline = time.monotonic() + timeout_s
        last_state = ""
        while time.monotonic() < deadline:
            state = self._query_tolerante("TRIGger:STATe?")
            if state is None:
                continue
            last_state = state
            if last_state.startswith(("ARM", "WTRIG")):
                return
            time.sleep(0.05)
        raise TimeoutError(
            f"AMETEK não entrou em ARM/WTRIG; último estado={last_state!r}"
        )

    def trigger(self) -> None:
        state = self.query("TRIGger:STATe?").strip().upper()
        if not state.startswith(("ARM", "WTRIG")):
            raise InstrumentHardwareError(f"AMETEK não estava armada antes de *TRG: {state!r}")
        self.write("*TRG")

    def wait_transient_complete(self, timeout_s: float = 5.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            state = self._query_tolerante("TRIGger:STATe?")
            if state is None:
                continue
            if state.startswith("IDLE"):
                self.assert_no_errors("execução do transiente")
                return
            time.sleep(0.05)
        raise TimeoutError("AMETEK não concluiu a lista transitória")

    def safe_shutdown(self) -> None:
        try:
            if self.simulated or self._resource is not None:
                # Saia primeiro de INIT/WAIT/BUSY. A Rev. 5.53 pode ignorar a
                # alteração de OUTPUT enquanto o transient está ativo.
                self._raw_write("ABORt")
                self._raw_write("OUTPut:STATe OFF")
                self._sim["output"] = False
                self._sim["trigger_state"] = "IDLE"
                if not self.simulated:
                    time.sleep(0.2)
                    state = self.query("OUTPut:STATe?").strip().upper()
                    if state not in {"0", "OFF"}:
                        # Uma repetição explícita é preferível a encerrar com
                        # a saída em estado desconhecido.
                        self._raw_write("ABORt")
                        self._raw_write("OUTPut:STATe OFF")
                        time.sleep(0.2)
                        state = self.query("OUTPut:STATe?").strip().upper()
                    if state not in {"0", "OFF"}:
                        raise InstrumentHardwareError(
                            f"SHUTDOWN NÃO CONFIRMADO: OUTPut:STATe?={state!r}"
                        )
        except Exception:
            logger.exception("Não foi possível confirmar shutdown da AMETEK")

    def measure_voltage(self) -> float:
        return float(self.query("MEASure:VOLTage:AC?"))

    def measure_current(self) -> float:
        return float(self.query("MEASure:CURRent:AC?"))

    def measure_power_w(self) -> float:
        return 1000.0 * float(self.query("MEASure:POWer:AC:REAL?"))

    def measure_power_factor(self) -> float:
        return float(self.query("MEASure:POWer:AC:PFACtor?"))


if __name__ == "__main__":
    source = AmetekMX30(simulated=True)
    source.configure_safe_baseline(
        voltage_range_rms=150.0,
        voltage_high_vp=100.0,
        current_limit_a=0.5,
        protection_delay_s=0.1,
        frequency_hz=50.0,
    )
    print(source.idn)
