"""
Script Mestre de Coordenação de Experimentos (mestre.py)
=========================================================
Orquestra a execução sequencial dos 20 experimentos SCPI de injeção harmônica e aquisição,
integrando a Fonte CA AMETEK MX30 (`ametek_orm.py`) e o Osciloscópio Keysight DSO-X 4043A (`oscilloscope_orm.py`).

Data: 2026
"""

import os
import glob
import time
import logging
import importlib.util
from typing import Tuple, Optional

# Importação dos ORMs de Hardware desenvolvidos
from ametek_orm import AmetekMX30
from oscilloscope_orm import KeysightDSOX4043A

try:
    from pymeasure.adapters import VISAAdapter
except ImportError:
    VISAAdapter = None

# Configuração do Sistema de Logs
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("MestreExperimentos")


# --- CONFIGURAÇÕES DE RECURSOS E BANCADA ---
AMETEK_RESOURCE = "TCPIP0::192.168.1.100::5025::SOCKET"
KEYSIGHT_RESOURCE = "USB0::0x0957::0x17A0::MY50000000::INSTR"

SIMULATED_MODE = False  # Altere para True para testes offline sem hardware físico


def inicializar_instrumentos(simulated: bool = False) -> Tuple[AmetekMX30, Optional[KeysightDSOX4043A]]:
    """Inicializa as conexões VISA com a Fonte AMETEK e o Osciloscópio Keysight."""
    logger.info("Conectando aos instrumentos da bancada...")

    if simulated:
        fonte = AmetekMX30(AMETEK_RESOURCE, simulated=True)
        osc = None
        logger.info("Modo SIMULADO ativado.")
        return fonte, osc

    # 1. Conexão com a Fonte CA AMETEK MX30 (Limite de segurança de corrente ajustado para 10.0 A em bancada)
    fonte = AmetekMX30(AMETEK_RESOURCE, max_voltage=300.0, max_current=10.0)
    
    # 2. Conexão com o Osciloscópio Keysight DSO-X 4043A via PyMeasure VISAAdapter
    if VISAAdapter is None:
        raise ImportError("O pacote 'pymeasure' é necessário para conectar ao Keysight DSO-X 4043A.")
        
    adapter = VISAAdapter(KEYSIGHT_RESOURCE)
    osc = KeysightDSOX4043A(adapter)

    # Configuração de segurança inicial
    fonte.output_enabled = False
    fonte.clear_harmonics()
    fonte.configure_trigger(source="BUS", output_sync=True)  # <-- Configuração única do trigger

    logger.info("Instrumentos inicializados e sincronizados com sucesso.")
    return fonte, osc


def executar_experimento(script_path: str, fonte: AmetekMX30, osc: Optional[KeysightDSOX4043A]) -> bool:
    """Carrega dinamicamente o arquivo .py do experimento e executa a rotina run(fonte, osc)."""
    nome_script = os.path.basename(script_path)
    exp_id = os.path.splitext(nome_script)[0]
    
    logger.info(f"========== Executando Experimento {exp_id} ({nome_script}) ==========")

    try:
        # Carregamento dinâmico do mini-script em tempo de execução
        spec = importlib.util.spec_from_file_location(exp_id, script_path)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)

        if not hasattr(modulo, "run"):
            logger.error(f"Erro: O script {nome_script} não contém a função 'run(fonte, osc)'.")
            return False

        # Chamada com passagem dos dois objetos de hardware
        modulo.run(fonte, osc)
        logger.info(f"Experimento {exp_id} concluído e dados gravados em resultados/{exp_id}.npz.")
        return True

    except Exception as e:
        logger.error(f"Falha ao executar o experimento {exp_id}: {e}", exc_info=True)
        # Proteção de hardware: desliga a saída da fonte em caso de exceção no experimento
        try:
            if fonte:
                fonte.output_enabled = False
        except Exception:
            pass
        return False


def main():
    dir_experimentos = "experimentos"
    dir_resultados = "resultados"
    
    os.makedirs(dir_experimentos, exist_ok=True)
    os.makedirs(dir_resultados, exist_ok=True)

    # Busca os scripts no padrão 01.py até 20.py
    scripts = sorted(glob.glob(os.path.join(dir_experimentos, "[0-9][0-9].py")))

    if not scripts:
        logger.warning(
            f"Nenhum script localizado em '{dir_experimentos}/'. "
            "Rode o script bash 'gerar_experimentos.sh' para criar a suite de experimentos."
        )
        return

    logger.info(f"Total de {len(scripts)} experimentos identificados para execução.")

    fonte = None
    osc = None

    try:
        # Abre a sessão de bancada
        fonte, osc = inicializar_instrumentos(simulated=SIMULATED_MODE)

        # Loop de orquestração sequencial
        falhas = []
        for script_path in scripts:
            sucesso = executar_experimento(script_path, fonte, osc)
            if not sucesso:
                falhas.append(script_path)
            
            # Pausa para resfriamento / estabilização da bancada
            time.sleep(1.0)

        # Relatório final de execução
        logger.info("==================================================")
        logger.info(f"Bateria encerrada. Sucesso: {len(scripts) - len(falhas)}/{len(scripts)}")
        if falhas:
            logger.warning(f"Experimentos com erro: {[os.path.basename(f) for f in falhas]}")
        logger.info("==================================================")

    except KeyboardInterrupt:
        logger.warning("Execução interrompida manualmente pelo usuário.")
    finally:
        # Procedimento seguro de shutdown da bancada
        logger.info("Finalizando saídas de potência e fechando barramentos VISA...")
        if fonte:
            try:
                fonte.output_enabled = False
                fonte.disconnect()
            except Exception as e:
                logger.error(f"Erro ao desligar fonte: {e}")

        if osc and hasattr(osc, 'adapter'):
            try:
                osc.adapter.close()
                logger.info("Conexão VISA do osciloscópio encerrada.")
            except Exception as e:
                logger.error(f"Erro ao fechar sessão do osciloscópio: {e}")


if __name__ == "__main__":
    main()
