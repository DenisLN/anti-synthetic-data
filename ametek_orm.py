"""
AMETEK MX30 / RS / BPS Series AC Power Source Hardware ORM
===========================================================
Driver Orientado a Objetos (ORM de Hardware) para Fontes CA AMETEK California Instruments.
Implementa abstração SCPI, suporte a injeção harmônica até a 50ª ordem, 
sincronização por trigger e segurança contra ultrapassagem de limites operacionais.

Data: 2026
"""

import time
import logging
from typing import Optional, Dict, List, Tuple, Union

try:
    import pyvisa
except ImportError:
    pyvisa = None

# Configuração de Logger
logger = logging.getLogger("AmetekORM")
logger.setLevel(logging.INFO)


# --- EXCEÇÕES CUSTOMIZADAS ---

class AmetekORMError(Exception):
    """Exceção base para falhas do driver Ametek ORM."""
    pass


class ParameterOutOfBoundsError(AmetekORMError, ValueError):
    """Disparada quando um parâmetro ultrapassa os limites físicos configurados."""
    pass


class CommunicationError(AmetekORMError):
    """Disparada quando há falha de comunicação VISA ou estouro de timeout."""
    pass


class InstrumentHardwareError(AmetekORMError):
    """Disparada quando a fonte retorna um erro interno (SYST:ERR?)."""
    pass


# --- CLASSE PRINCIPAL DO ORM ---

class AmetekMX30:
    """
    Abstração Orientada a Objetos para a Fonte de Alimentação CA AMETEK MX30 / RS / BPS.
    
    Exemplo de uso:
        with AmetekMX30("TCPIP0::192.168.1.100::5025::SOCKET") as fonte:
            fonte.voltage = 127.0
            fonte.frequency = 60.0
            fonte.output_enabled = True
            v_rms = fonte.measure_voltage()
    """

    # Limites padrão de segurança de hardware
    DEFAULT_MAX_VOLTAGE: float = 300.0   # Tensão RMS máxima (V)
    DEFAULT_MIN_FREQ: float = 45.0       # Frequência mínima (Hz)
    DEFAULT_MAX_FREQ: float = 500.0      # Frequência máxima (Hz)
    DEFAULT_MAX_CURRENT: float = 100.0   # Corrente limite padrão (A)

    def __init__(
        self,
        resource_name: str,
        resource_manager: Optional[object] = None,
        max_voltage: float = DEFAULT_MAX_VOLTAGE,
        min_freq: float = DEFAULT_MIN_FREQ,
        max_freq: float = DEFAULT_MAX_FREQ,
        max_current: float = DEFAULT_MAX_CURRENT,
        timeout_ms: int = 5000,
        simulated: bool = False
    ):
        """
        Inicializa o objeto ORM da Fonte AMETEK.

        :param resource_name: String VISA (ex: 'TCPIP0::192.168.1.100::5025::SOCKET' ou 'GPIB0::1::INSTR')
        :param resource_manager: Instância opcional de pyvisa.ResourceManager
        :param max_voltage: Limite superior de tensão para proteção do EUT
        :param min_freq: Frequência mínima permitida
        :param max_freq: Frequência máxima permitida
        :param max_current: Corrente máxima permitida
        :param timeout_ms: Timeout de comunicação VISA em milissegundos
        :param simulated: Modo simulação/mock sem hardware físico
        """
        self.resource_name = resource_name
        self._rm = resource_manager
        self._instrument = None
        self.simulated = simulated
        self.timeout_ms = timeout_ms

        # Limites de hardware
        self._max_voltage = float(max_voltage)
        self._min_freq = float(min_freq)
        self._max_freq = float(max_freq)
        self._max_current = float(max_current)

        # Estado interno em modo simulado
        self._sim_voltage = 0.0
        self._sim_frequency = 60.0
        self._sim_output = False
        self._sim_current_limit = max_current

        if not self.simulated:
            self.connect()

    # --- GERENCIAMENTO DE CONTEXTO ---

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.is_connected:
                self.output_enabled = False  # Desliga a saída por segurança
        except Exception as e:
            logger.error(f"Erro ao desligar a saída durante cleanup: {e}")
        finally:
            self.disconnect()

    # --- CAMADA DE COMUNICAÇÃO VISA ---

    def connect(self) -> None:
        """Abre a conexão VISA com a fonte e ajusta terminadores SCPI."""
        if self.simulated:
            logger.info(f"[SIMULATED] Conectado a {self.resource_name}")
            return

        if pyvisa is None:
            raise ImportError("O pacote 'pyvisa' é necessário para comunicação real com a fonte.")

        try:
            if self._rm is None:
                self._rm = pyvisa.ResourceManager()
            
            self._instrument = self._rm.open_resource(self.resource_name)
            self._instrument.timeout = self.timeout_ms
            self._instrument.read_termination = '\n'
            self._instrument.write_termination = '\n'
            
            # Limpa o buffer e faz query de identificação
            idn = self.query("*IDN?")
            logger.info(f"Conectado com sucesso ao instrumento: {idn}")
        except Exception as e:
            raise CommunicationError(f"Falha ao conectar ao recurso {self.resource_name}: {e}") from e

    def disconnect(self) -> None:
        """Fecha a sessão VISA com a fonte."""
        if self._instrument is not None:
            try:
                self._instrument.close()
                logger.info("Conexão VISA encerrada.")
            except Exception as e:
                logger.warning(f"Erro ao fechar instrumento VISA: {e}")
            finally:
                self._instrument = None

    @property
    def is_connected(self) -> bool:
        """Retorna True se a conexão estiver aberta ou em modo simulado."""
        return self.simulated or (self._instrument is not None)

    def write(self, command: str) -> None:
        """Envia um comando SCPI para a fonte."""
        if self.simulated:
            logger.debug(f"[SIM WRITE] {command}")
            return
        try:
            self._instrument.write(command)
        except Exception as e:
            raise CommunicationError(f"Erro na escrita SCPI ('{command}'): {e}") from e

    def query(self, command: str) -> str:
        """Envia um comando SCPI de consulta e retorna a resposta formatada."""
        if self.simulated:
            logger.debug(f"[SIM QUERY] {command}")
            return "0.0"
        try:
            response = self._instrument.query(command).strip()
            return response
        except Exception as e:
            raise CommunicationError(f"Erro na consulta SCPI ('{command}'): {e}") from e

    def check_errors(self) -> List[Tuple[int, str]]:
        """Consulta a fila de erros da fonte (`SYST:ERR?`) até que esteja vazia."""
        errors = []
        if self.simulated:
            return errors
        
        max_attempts = 20
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            err_str = self.query("SYSTem:ERRor?")
            code, msg = err_str.split(',', 1)
            code = int(code)
            msg = msg.strip(' "')
            if code == 0:
                break
            errors.append((code, msg))
            logger.error(f"Erro retornado pela AMETEK: Code {code} - {msg}")
        return errors

    def reset(self) -> None:
        """Restaura as configurações de fábrica da fonte (`*RST`)."""
        self.write("*RST")
        self.wait_ready()

    def wait_ready(self, timeout_sec: float = 10.0) -> None:
        """Bloqueia a execução até que o comando SCPI anterior seja concluído (`*OPC?`)."""
        if self.simulated:
            return
        t_start = time.time()
        while time.time() - t_start < timeout_sec:
            res = self.query("*OPC?")
            if res == "1":
                return
            time.sleep(0.05)
        raise TimeoutError("Tempo limite esgotado aguardando prontidão da fonte (*OPC?).")

    # --- PROPRIEDADES E CONTROLE DE TENSÃO, FREQUÊNCIA E SAÍDA ---

    @property
    def voltage(self) -> float:
        """Retorna o nível de tensão CA programado em Volts RMS."""
        if self.simulated:
            return self._sim_voltage
        return float(self.query("SOURce:VOLTage:LEVel:IMMediate:AMPLitude?"))

    @voltage.setter
    def voltage(self, val: float) -> None:
        """Define o nível de tensão CA RMS com validação de limites de segurança."""
        val = float(val)
        if not (0.0 <= val <= self._max_voltage):
            raise ParameterOutOfBoundsError(
                f"Tensão solicitada ({val} V) fora da faixa permitida [0.0 - {self._max_voltage} V]."
            )
        self.write(f"SOURce:VOLTage:LEVel:IMMediate:AMPLitude {val:.4f}")
        self._sim_voltage = val

    @property
    def frequency(self) -> float:
        """Retorna a frequência programada em Hertz."""
        if self.simulated:
            return self._sim_frequency
        return float(self.query("SOURce:FREQuency:CW?"))

    @frequency.setter
    def frequency(self, val: float) -> None:
        """Define a frequência de saída em Hz com validação de limites."""
        val = float(val)
        if not (self._min_freq <= val <= self._max_freq):
            raise ParameterOutOfBoundsError(
                f"Frequência ({val} Hz) fora da faixa permitida [{self._min_freq} - {self._max_freq} Hz]."
            )
        self.write(f"SOURce:FREQuency:CW {val:.4f}")
        self._sim_frequency = val

    @property
    def output_enabled(self) -> bool:
        """Retorna True se o relé de saída da fonte estiver ligado."""
        if self.simulated:
            return self._sim_output
        res = self.query("OUTPut:STATe?").upper()
        return res in ["1", "ON"]

    @output_enabled.setter
    def output_enabled(self, state: bool) -> None:
        """Conecta ou desconecta a saída física da fonte (`OUTP ON` / `OUTP OFF`)."""
        cmd_val = "ON" if state else "OFF"
        self.write(f"OUTPut:STATe {cmd_val}")
        self._sim_output = bool(state)

    @property
    def current_limit(self) -> float:
        """Retorna o limite de corrente RMS configurado em Ampères."""
        if self.simulated:
            return self._sim_current_limit
        return float(self.query("SOURce:CURRent:LIMit:AMPLitude?"))

    @current_limit.setter
    def current_limit(self, val: float) -> None:
        """Define a proteção de limite de corrente RMS (A)."""
        val = float(val)
        if not (0.0 <= val <= self._max_current):
            raise ParameterOutOfBoundsError(
                f"Limite de corrente ({val} A) excede o máximo permitido ({self._max_current} A)."
            )
        self.write(f"SOURce:CURRent:LIMit:AMPLitude {val:.4f}")
        self._sim_current_limit = val

    def set_phase_coupling(self, couple_all: bool = True) -> None:
        """Configura se os comandos afetam todas as fases simultaneamente ou individualmente."""
        mode = "ALL" if couple_all else "NONE"
        self.write(f"INSTrument:COUPle {mode}")

    def select_phase(self, phase_index: int) -> None:
        """Seleciona a fase ativa para configuração individual (1, 2 ou 3)."""
        if phase_index not in [1, 2, 3]:
            raise ValueError("Índice de fase inválido. Use 1, 2 ou 3.")
        self.write(f"INSTrument:NSELect {phase_index}")

    # --- SÍNTESE E INJEÇÃO DE HARMÔNICAS ---

    def set_harmonic(self, order: int, amplitude_percent: float, phase_deg: float = 0.0) -> None:
        """
        Injeta uma harmônica específica na forma de onda fundamental.

        :param order: Ordem da harmônica (2 a 50)
        :param amplitude_percent: Percentual em relação à fundamental (0.0 a 100.0 %)
        :param phase_deg: Ângulo de fase em graus (-360.0 a 360.0)
        """
        if not (2 <= order <= 50):
            raise ParameterOutOfBoundsError("A ordem da harmônica deve estar entre 2 e 50.")
        if not (0.0 <= amplitude_percent <= 100.0):
            raise ParameterOutOfBoundsError("Percentual de amplitude deve estar entre 0 e 100%.")

        self.write(f"SOURce:HARMonic:AMPLitude {order},{amplitude_percent:.3f}")
        self.write(f"SOURce:HARMonic:PHASe {order},{phase_deg:.2f}")

    def set_harmonic_profile(self, harmonics: Dict[int, float]) -> None:
        """
        Define um perfil harmônico completo de uma vez.

        :param harmonics: Dicionário onde a chave é a ordem harmônica (2 a 50) 
                          e o valor é a amplitude percentual (0.0 a 100.0 %).
        """
        self.clear_harmonics()
        for order, amp in harmonics.items():
            self.set_harmonic(order, amp)

    def clear_harmonics(self) -> None:
        """Zera todas as distorções harmônicas programadas, retornando a onda senoidal pura."""
        self.write("SOURce:HARMonic:CLEar")

    # --- TELEMETRIA E MEDIÇÃO ---

    def measure_voltage(self) -> float:
        """Mede a tensão RMS instantânea de saída (V)."""
        if self.simulated:
            return self._sim_voltage if self._sim_output else 0.0
        return float(self.query("MEASure:VOLTage:AC?"))

    def measure_current(self) -> float:
        """Mede a corrente RMS instantânea de saída (A)."""
        if self.simulated:
            return 1.25 if self._sim_output else 0.0
        return float(self.query("MEASure:CURRent:AC?"))

    def measure_power(self) -> float:
        """Mede a potência ativa real instantânea (W)."""
        if self.simulated:
            return (self._sim_voltage * 1.25 * 0.95) if self._sim_output else 0.0
        return float(self.query("MEASure:POWer:AC:REAL?"))

    def measure_power_factor(self) -> float:
        """Mede o fator de potência instantâneo do sistema."""
        if self.simulated:
            return 0.95
        return float(self.query("MEASure:POWer:AC:PFACtor?"))

    def fetch_harmonics_spectrum(self, max_order: int = 50) -> Dict[str, List[float]]:
        """
        Mede e analisa a amplitude das harmônicas de tensão e corrente até a 50ª ordem.

        :param max_order: Ordem harmônica máxima desejada (até 50)
        :return: Dicionário contendo as listas 'v_harmonics' (V) e 'i_harmonics' (A).
        """
        if max_order > 50 or max_order < 1:
            raise ParameterOutOfBoundsError("A amostragem harmônica deve ser de 1 até 50.")

        if self.simulated:
            v_mock = [self._sim_voltage] + [0.0] * (max_order - 1)
            i_mock = [1.25] + [0.0] * (max_order - 1)
            return {"v_harmonics": v_mock, "i_harmonics": i_mock}

        # Consulta arrays internos de harmônicas do controlador AMETEK
        raw_v = self.query(f"FETCh:ARRay:VOLTage:HARMonic:AMPLitude? 1,{max_order}")
        raw_i = self.query(f"FETCh:ARRay:CURRent:HARMonic:AMPLitude? 1,{max_order}")

        v_harmonics = [float(x) for x in raw_v.split(',')]
        i_harmonics = [float(x) for x in raw_i.split(',')]

        return {
            "v_harmonics": v_harmonics,
            "i_harmonics": i_harmonics
        }

    # --- SINCRONIZAÇÃO E TRIGGERS POR HARDWARE ---

    def configure_trigger(self, source: str = "BUS", output_sync: bool = True) -> None:
        """
        Configura o barramento de disparos (Trigger) da fonte.

        :param source: Fonte do disparador ('BUS', 'EXTernal', ou 'IMMediate')
        :param output_sync: Se True, emite um pulso TTL de sincronismo na porta Trigger Out da fonte.
        """
        valid_sources = ["BUS", "EXT", "EXTERNAL", "IMM", "IMMEDIATE"]
        if source.upper() not in valid_sources:
            raise ValueError(f"Fonte de trigger inválida: {source}")

        self.write(f"TRIGger:SOURce {source.upper()}")
        if output_sync:
            self.write("OUTPut:TRIGger:MODE SYNC")

    def arm_transient(self) -> None:
        """Arma a fonte para aguardar o pulso de disparo de transiente (`INIT:TRAN`)."""
        self.write("INITiate:TRANsient")

    def trigger(self) -> None:
        """Envia o comando SCPI de disparo por software (`*TRG`)."""
        self.write("*TRG")


if __name__ == "__main__":
    # Teste de fumaça em modo simulado
    print("Iniciando verificação do driver AmetekMX30 (Modo Simulado)...")
    with AmetekMX30("TCPIP0::127.0.0.1::5025::SOCKET", simulated=True) as fonte:
        fonte.voltage = 127.0
        fonte.frequency = 60.0
        fonte.output_enabled = True
        
        # Injeta 5% da 5ª harmônica e 2% da 50ª harmônica
        fonte.set_harmonic(order=5, amplitude_percent=5.0)
        fonte.set_harmonic(order=50, amplitude_percent=2.0)
        
        print(f"Tensão Lida: {fonte.measure_voltage()} V")
        print(f"Corrente Lida: {fonte.measure_current()} A")
        print(f"Espectro Harmônico: {fonte.fetch_harmonics_spectrum(max_order=50)}")
        print("Driver verificado com sucesso!")
