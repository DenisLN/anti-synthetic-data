"""Reproduz a sequencia REAL que falha na bancada e testa uma hipotese
num so ciclo, para nao gastar mais uma rodada de `run 01` adivinhando.

Contexto: diag_digitizer_range.py provou que :TIMebase:RANGe 1.2 e aceito
em modo Digitizer -- mas SEMPRE a partir de Digitizer ja ligado, subindo a
faixa aos poucos (1.0 -> 1.1 -> 1.19 -> 1.199 -> 1.2). O fluxo real e
diferente: Bancada.from_env() SEMPRE configura AUTO 6000pts/0.2s primeiro
(todo `run`, incondicional), e so DEPOIS executar() pula direto pra
Digitizer 36000pts/1.2s -- essa transicao especifica (AUTO 0.2s -> Digitizer
1.2s, de uma vez) nunca foi testada isoladamente. Este script:

  1. Reproduz exatamente essa transicao (deve falhar do jeito que falhou
     na bancada, senao a hipotese abaixo esta errada).
  2. Se falhar, tenta a MESMA transicao mas subindo a faixa aos poucos
     depois de ligar o Digitizer (0.2 -> 0.6 -> 1.2), igual ao que o
     probe anterior fez com sucesso.

So fala com o Keysight (força um trigger simulado, sem AMETEK/EUT).
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


def passo1_reproduzir_falha(osc: KeysightDSOX4034A) -> bool:
    print("\n== Passo 1: reproduzir a sequencia REAL (AUTO 0.2s -> Digitizer 1.2s direto) ==")
    osc.configure_acquisition(sample_rate_hz=FS_HZ, points=6_000, duration_s=0.2)
    print("  AUTO 6000pts/0.2s -> OK (igual Bancada.from_env())")
    try:
        osc.configure_acquisition(
            sample_rate_hz=FS_HZ, points=36_000, duration_s=1.2,
            pre_trigger_s=0.5, digitizer=True,
        )
        print("  Digitizer 36000pts/1.2s direto -> OK (nao reproduziu a falha!)")
        return True
    except Exception as exc:
        print(f"  Digitizer 36000pts/1.2s direto -> FALHOU: {exc}")
        return False


def passo2_subir_aos_poucos(osc: KeysightDSOX4034A) -> bool:
    print("\n== Passo 2: mesma transicao, mas subindo a faixa aos poucos apos ligar Digitizer ==")
    osc.configure_acquisition(sample_rate_hz=FS_HZ, points=6_000, duration_s=0.2)
    print("  AUTO 6000pts/0.2s -> OK")
    osc.write(":STOP")
    osc.write(":ACQuire:DIGitizer ON")
    osc.write(":ACQuire:SRATe:ANALog:AUTO OFF")
    osc.write(f":ACQuire:SRATe:ANALog {FS_HZ:.12g}")
    osc.write(":ACQuire:POINts:ANALog:AUTO OFF")
    erros = osc.check_errors()
    print(f"  Digitizer ON + taxa 30kSa/s -> {'OK' if not erros else erros}")

    degraus_s = [0.2, 0.6, 1.0, 1.2]
    for alvo_s in degraus_s:
        pontos = round(alvo_s * FS_HZ)
        osc.write(f":ACQuire:POINts:ANALog {pontos}")
        erros_pontos = osc.check_errors()
        osc.write(f":TIMebase:RANGe {alvo_s:.12g}")
        erros_range = osc.check_errors()
        status = "OK" if not (erros_pontos or erros_range) else f"pontos={erros_pontos} range={erros_range}"
        print(f"    degrau {alvo_s:>4.2f}s ({pontos} pts) -> {status}")
        if erros_pontos or erros_range:
            osc.write(":ACQuire:DIGitizer OFF")
            osc.write(":ACQuire:SRATe:ANALog:AUTO ON")
            osc.write(":ACQuire:POINts:ANALog:AUTO ON")
            osc.check_errors()
            return False

    osc.write(":TIMebase:REFerence CENTer")
    osc.write(":TIMebase:POSition 0.1")
    erros_ref = osc.check_errors()
    print(f"  REFerence CENTer + POSition 0.1 -> {'OK' if not erros_ref else erros_ref}")

    osc.write(":ACQuire:DIGitizer OFF")
    osc.write(":ACQuire:SRATe:ANALog:AUTO ON")
    osc.write(":ACQuire:POINts:ANALog:AUTO ON")
    osc.check_errors()
    return not erros_ref


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
        osc.initialize_safe()

        reproduziu_ok_direto = passo1_reproduzir_falha(osc)
        if reproduziu_ok_direto:
            print(
                "\nNAO reproduziu a falha -- a hipotese de transicao AUTO->Digitizer "
                "esta errada, o problema e outra coisa (ou intermitente)."
            )
            return 0

        subir_aos_poucos_funcionou = passo2_subir_aos_poucos(osc)
        print(
            "\nRESULTADO: subir a faixa aos poucos apos ligar Digitizer "
            f"{'FUNCIONOU' if subir_aos_poucos_funcionou else 'TAMBEM FALHOU'}."
        )
    finally:
        osc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
