"""Sonda mínima e somente-leitura: descobre que valores de :TIMebase:RANGe
o modo Digitizer aceita perto de 1.2s. Motivo: `:ACQuire:POINts:ANALog
36360` + `:TIMebase:RANGe 1.212` foi rejeitado na bancada com SCPI -222
"Data out of range", mas 1.2/36000 (mesma configuração sem folga) foi
aceito antes. O manual (:TIMebase:RANGe / :TIMebase:SCALe) não documenta o
limite numérico na página do comando -- mais rápido perguntar direto ao
instrumento do que continuar procurando no manual.

Só escreve comandos e lê a fila de erro (:SYSTem:ERRor?) -- nunca arma
(:SINGle) nem dispara. AMETEK não é aberta. Seguro rodar a qualquer momento
com o Keysight sozinho na porta USB.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pymeasure.adapters import VISAAdapter  # noqa: E402

from mestre import (  # noqa: E402
    KEYSIGHT_EXPECTED_MODEL,
    KEYSIGHT_RESOURCE,
    KEYSIGHT_TIMEOUT_MS,
    _discover_keysight_resource,
)
from oscilloscope_orm import KeysightDSOX4034A  # noqa: E402

FS_HZ = 30_000.0
# Abaixo, em cima, bem em cima (a folga de 1% que falhou), e bem acima --
# se só os valores "quase 1.2" falharem, é grade de passo; se tudo acima de
# 1.2 falhar (inclusive 2.0/3.0/5.0, bem longe de qualquer limite de
# memória), é teto de faixa/tempo do próprio modo Digitizer nesta taxa.
CANDIDATOS_S = [1.0, 1.1, 1.19, 1.199, 1.2, 1.201, 1.21, 1.212, 1.22, 1.25, 1.3, 1.5, 2.0, 3.0, 5.0]


def main() -> int:
    resource = (
        _discover_keysight_resource(KEYSIGHT_EXPECTED_MODEL)
        if KEYSIGHT_RESOURCE.upper() in {"", "AUTO"}
        else KEYSIGHT_RESOURCE
    )
    adapter = VISAAdapter(resource, timeout=KEYSIGHT_TIMEOUT_MS)
    osc = KeysightDSOX4034A(adapter)
    try:
        print("Identidade:", osc.verify_identity(KEYSIGHT_EXPECTED_MODEL))
        osc.write(":STOP")
        osc.write(":ACQuire:DIGitizer ON")
        osc.write(":ACQuire:SRATe:ANALog:AUTO OFF")
        osc.write(f":ACQuire:SRATe:ANALog {FS_HZ:.12g}")
        osc.write(":ACQuire:POINts:ANALog:AUTO OFF")
        erros_setup = osc.check_errors()
        print(f"setup taxa=30kSa/s -> {'OK' if not erros_setup else erros_setup}")

        for candidato_s in CANDIDATOS_S:
            pontos = round(candidato_s * FS_HZ)
            osc.write(f":ACQuire:POINts:ANALog {pontos}")
            erros_pontos = osc.check_errors()
            osc.write(f":TIMebase:RANGe {candidato_s:.12g}")
            erros_range = osc.check_errors()
            atual = osc.ask(":TIMebase:RANGe?").strip()
            status = "OK" if not (erros_pontos or erros_range) else f"pontos={erros_pontos} range={erros_range}"
            print(f"  pedido {candidato_s:>8.4f}s ({pontos} pts) -> {status}; RANGe? devolveu {atual}")

        osc.write(":ACQuire:DIGitizer OFF")
        osc.write(":ACQuire:SRATe:ANALog:AUTO ON")
        osc.write(":ACQuire:POINts:ANALog:AUTO ON")
        osc.check_errors()
    finally:
        osc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
