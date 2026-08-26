"""
Driver ORM Python para Osciloscópio Keysight InfiniiVision DSO-X 4043A (4 Canais).

Refatorado e auditado estritamente com base no Keysight InfiniiVision 4000 X-Series
Oscilloscopes Programmer's Guide (Edição de 31 de Outubro de 2025, Software v07.66.0000).
"""

import logging
import time
import numpy as np
from pymeasure.instruments.keysight.keysightDSOX1102G import KeysightDSOX1102G
from pymeasure.instruments import Channel

logger = logging.getLogger(__name__)


class OscChannel(Channel):
    """Representação de um canal analógico individual (CH1 a CH4)."""

    bwlimit = Channel.control(
        ":CHANnel{ch}:BWLimit?",
        ":CHANnel{ch}:BWLimit %s",
        """Controla o filtro de limite de banda (BWLimit) de 20 MHz. (Manual pág. 360)""",
        validator=lambda v, ms: v in [0, 1, True, False, "ON", "OFF", "on", "off"],
        values={True: "1", False: "0", "ON": "1", "OFF": "0", "on": "1", "off": "0"},
    )

    coupling = Channel.control(
        ":CHANnel{ch}:COUPling?",
        ":CHANnel{ch}:COUPling %s",
        """Controla o acoplamento do canal: 'AC' ou 'DC'. (Manual pág. 361)""",
        validator=lambda v, ms: str(v).upper() in ["AC", "DC"],
        values={"AC": "AC", "DC": "DC"},
    )

    display = Channel.control(
        ":CHANnel{ch}:DISPlay?",
        ":CHANnel{ch}:DISPlay %s",
        """Habilita ou desabilita a exibição do canal na tela: True/False ou 1/0. (Manual pág. 362)""",
        validator=lambda v, ms: v in [0, 1, True, False],
        values={True: "1", False: "0"},
    )

    offset = Channel.control(
        ":CHANnel{ch}:OFFSet?",
        ":CHANnel{ch}:OFFSet %e",
        """Define o offset vertical em Volts. (Manual pág. 366)""",
    )

    probe = Channel.control(
        ":CHANnel{ch}:PROBe?",
        ":CHANnel{ch}:PROBe %e",
        """Define a atenuação da ponta de prova (ex: 1.0, 10.0, 100.0). (Manual pág. 367)""",
    )

    scale = Channel.control(
        ":CHANnel{ch}:SCALE?",
        ":CHANnel{ch}:SCALE %e",
        """Define a escala vertical em Volts por divisão. (Manual pág. 384)""",
    )

    range = Channel.control(
        ":CHANnel{ch}:RANGe?",
        ":CHANnel{ch}:RANGe %e",
        """Define a faixa vertical total em Volts (8 * escala). (Manual pág. 383)""",
    )


class KeysightDSOX4043A(KeysightDSOX1102G):
    """Driver PyMeasure para a série Keysight InfiniiVision DSO-X 4043A (4 Canais Analógicos)."""

    def __init__(self, adapter, name="Keysight InfiniiVision DSO-X 4043A", **kwargs):
        super().__init__(adapter, name, **kwargs)
        # Suporte aos 4 canais analógicos do DSO-X 4043A
        self.ch1 = OscChannel(self, 1)
        self.ch2 = OscChannel(self, 2)
        self.ch3 = OscChannel(self, 3)
        self.ch4 = OscChannel(self, 4)
        self.channels = {1: self.ch1, 2: self.ch2, 3: self.ch3, 4: self.ch4}
        self._is_armed_flag = False

    @property
    def sample_rate(self) -> float:
        """Retorna a taxa de amostragem analógica atual em Hz.

        Comando SCPI: :ACQuire:SRATe[:ANALog]? (Manual pág. 328).
        """
        try:
            return float(self.ask(":ACQuire:SRATe?"))
        except Exception as e:
            logger.error("Falha ao consultar a taxa de amostragem (:ACQuire:SRATe?): %s", e)
            raise

    def configure_channel(
        self,
        channel: int,
        scale: float = None,
        offset: float = None,
        coupling: str = None,
        probe_attenuation: float = None,
        display: bool = True,
    ):
        """Configura os parâmetros de um canal analógico (1 a 4).

        Comandos SCPI empregados:
        - :CHANnel<n>:DISPlay (Manual pág. 362)
        - :CHANnel<n>:SCALE   (Manual pág. 384)
        - :CHANnel<n>:OFFSet  (Manual pág. 366)
        - :CHANnel<n>:COUPling(Manual pág. 361)
        - :CHANnel<n>:PROBe   (Manual pág. 367)
        """
        if channel not in self.channels:
            raise ValueError(f"Canal inválido: {channel}. O modelo DSO-X 4043A possui canais 1 a 4.")

        ch = self.channels[channel]

        if display is not None:
            ch.display = display
        if scale is not None:
            ch.scale = scale
        if offset is not None:
            ch.offset = offset
        if coupling is not None:
            ch.coupling = coupling
        if probe_attenuation is not None:
            ch.probe = probe_attenuation

    def configure_timebase(
        self,
        scale: float = None,
        offset: float = None,
        time_range: float = None,
    ):
        """Configura a base de tempo horizontal.

        Comandos SCPI empregados:
        - :TIMebase:MODE MAIN  (Manual pág. 1333)
        - :TIMebase:SCALE      (Manual pág. 1339)
        - :TIMebase:POSition   (Manual pág. 1334)
        - :TIMebase:RANGe      (Manual pág. 1335)
        """
        self.write(":TIMebase:MODE MAIN")

        if time_range is not None:
            self.write(f":TIMebase:RANGe {time_range:e}")
        elif scale is not None:
            self.write(f":TIMebase:SCALE {scale:e}")

        if offset is not None:
            self.write(f":TIMebase:POSition {offset:e}")

    def setup_single_trigger(
        self,
        source: str = "CHANnel1",
        level: float = 0.0,
        slope: str = "POSitive",
    ):
        """Configura o sistema de disparo em modo de varredura normal e borda única.

        Comandos SCPI empregados:
        - :TRIGger:MODE EDGE        (Manual pág. 1358)
        - :TRIGger:SWEep NORMal     (Manual pág. 1360)
        - :TRIGger:EDGE:SOURce      (Manual pág. 1379)
        - :TRIGger:EDGE:LEVel       (Manual pág. 1376)
        - :TRIGger:EDGE:SLOPe       (Manual pág. 1378)
        """
        self.write(":TRIGger:MODE EDGE")
        self.write(":TRIGger:SWEep NORMal")
        self.write(f":TRIGger:EDGE:SOURce {source}")
        self.write(f":TRIGger:EDGE:LEVel {level:e}")
        self.write(f":TRIGger:EDGE:SLOPe {slope}")

    def arm(self):
        """Prepara e arma o osciloscópio para uma captura única.

        Comandos SCPI empregados:
        - :AER? (Arm Event Register query, Manual pág. 272 / 1624): limpa o evento anterior.
        - :TER? (Trigger Event Register query, Manual pág. 309 / 1615): limpa o evento anterior.
        - :SINGle (Manual pág. 306): coloca o hardware em modo de disparo único.
        """
        try:
            # Limpa os registradores de evento gravados anteriormente (clear-on-read)
            _ = self.ask(":AER?")
            _ = self.ask(":TER?")
            self._is_armed_flag = False

            # Envia comando de aquisição única
            self.write(":SINGle")
        except Exception as e:
            logger.error("Erro de comunicação ao armar o osciloscópio via :SINGle: %s", e)
            raise

    def is_armed(self) -> bool:
        """Verifica se o osciloscópio está armado e aguardando um evento de disparo.

        Comando SCPI de condição de operação (Manual pág. 292):
        - :OPERegister:CONDition? (Bit 5 = 32 'Wait for Trigger')
        """
        try:
            oper_cond = int(self.ask(":OPERegister:CONDition?"))
            return (oper_cond & 32) != 0
        except ValueError as ve:
            logger.error("Resposta SCPI inválida ou não numérica em is_armed(): %s", ve)
            raise
        except Exception as e:
            logger.error("Falha I/O de comunicação VISA/SCPI em is_armed(): %s", e)
            raise

    def wait_for_armed(self, timeout: float = 5.0, poll_interval: float = 0.05) -> bool:
        """Aguarda até que o osciloscópio confirme o estado armado (Arm Event)."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_armed():
                return True
            time.sleep(poll_interval)
        return False

    def wait_for_trigger_complete(self, timeout: float = 10.0, poll_interval: float = 0.05) -> bool:
        """Aguarda até que o evento de disparo ocorra e a aquisição seja concluída.

        Comandos SCPI empregados:
        - :TER? (Trigger Event Register query, Manual pág. 309 / 1615)
        - *OPC? (Operation Complete query, Manual pág. 252 / 1636)
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                ter_val = int(self.ask(":TER?"))
                if ter_val == 1:
                    self._is_armed_flag = False
                    # Garante a conclusão da rotina interna de digitalização do hardware
                    _ = self.ask("*OPC?")
                    return True
            except Exception as e:
                logger.error("Erro durante polling de disparo (:TER?): %s", e)
                raise
            time.sleep(poll_interval)

        raise TimeoutError(f"Timeout de {timeout}s atingido aguardando pelo disparo do osciloscópio.")

    def get_waveform(self, channel: int = 1):
        """Lê os dados da forma de onda do canal especificado e retorna os vetores de tempo e tensão.

        Comandos SCPI empregados:
        - :WAVeform:SOURce CHANnel<n> (Manual pág. 1467)
        - :WAVeform:FORMat BYTE       (Manual pág. 1455)
        - :WAVeform:BYTeorder MSBF    (Manual pág. 1451)
        - :WAVeform:POINts:MODE RAW   (Manual pág. 1458)
        - :WAVeform:PREamble?         (Manual pág. 1460)
        - :WAVeform:DATA?             (Manual pág. 1453)

        Campos da Preamble Documentados (Manual pág. 1460):
        [0] format     [1] type        [2] points      [3] count
        [4] xincrement [5] xorigin     [6] xreference
        [7] yincrement [8] yorigin     [9] yreference

        Fórmula Oficial da Keysight (Manual pág. 1460):
        Voltage = ((Data_Point - Y_reference) * Y_increment) + Y_origin
        Time    = ((Point_Index - X_reference) * X_increment) + X_origin
        """
        if channel not in self.channels:
            raise ValueError(f"Canal inválido: {channel}")

        self.write(f":WAVeform:SOURce CHANnel{channel}")
        self.write(":WAVeform:FORMat BYTE")
        self.write(":WAVeform:POINts:MODE RAW")

        # Consulta o preâmbulo contendo as constantes de calibração e escala
        preamble_raw = self.ask(":WAVeform:PREamble?")
        preamble = [float(val) for val in preamble_raw.split(",")]

        points = int(preamble[2])
        x_increment = preamble[4]
        x_origin = preamble[5]
        x_reference = preamble[6]
        y_increment = preamble[7]
        y_origin = preamble[8]
        y_reference = preamble[9]

        # Transferência dos dados binários dos pontos de forma de onda
        raw_bytes = self.adapter.connection.query_binary_values(
            ":WAVeform:DATA?", datatype="B", container=np.ndarray
        )

        # Cálculo exato do vetor de tensão segundo a documentação Keysight
        voltage = ((raw_bytes.astype(np.float32) - y_reference) * y_increment) + y_origin

        # Cálculo do eixo horizontal temporal
        time_axis = ((np.arange(len(raw_bytes), dtype=np.float32) - x_reference) * x_increment) + x_origin

        return time_axis, voltage
