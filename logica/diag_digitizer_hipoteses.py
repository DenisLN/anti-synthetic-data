"""Bateria de diagnostico: testa TODAS as hipoteses pendentes sobre o modo
Digitizer numa unica sessao, cada uma a partir de `*RST` (reset padrao
SCPI do instrumento -- limpa timebase/aquisicao para o default de
fabrica), para eliminar de vez a duvida "o sucesso/falha anterior era
estado residual de outra coisa enviada antes na mesma sessao?".

So fala com o Keysight (nunca abre AMETEK, nunca precisa do EUT -- usa
force_trigger(), mesmo padrao ja validado por `bancada> trigger` em
preflight.py).

Hipoteses:
  H1. O bracket original (1.0s-1.2s todos aceitos, diag_digitizer_range.py)
      era genuino, ou artefato de config residual de ANTES daquele script
      rodar? -- repete o mesmo bracket a partir de *RST.
  H2. A transicao AUTO 0.2s -> Digitizer 1.2s (que falhou na bancada e em
      diag_digitizer_transicao.py) falha TAMBEM a partir de *RST, ou so
      falhava por causa de outro estado residual daquela sessao
      especifica?
  H3. Pedir SO os pontos explicitos (:ACQuire:POINts:ANALog, AUTO OFF),
      deixando a TAXA em AUTO (:ACQuire:SRATe:ANALog:AUTO ON) -- evita
      entrar em modo Digitizer? Aceita :TIMebase:REFerence LEFT (que o
      driver sempre dependeu)? Quantos pontos REAIS isso entrega numa
      aquisicao SINGLE de verdade?
  H4. O inverso de H3: taxa explicita, pontos em AUTO.

Cada hipotese comeca do zero (*RST) -- nenhuma carrega sujeira de
configuracao das anteriores.
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


def resetar(osc: KeysightDSOX4034A) -> None:
    osc.write("*RST")
    osc.ask("*OPC?")  # bloqueia ate o reset terminar de verdade
    osc.initialize_safe()


def ler_preamble_pontos_taxa(osc: KeysightDSOX4034A):
    osc.write(":WAVeform:SOURce CHANnel1")
    osc.write(":WAVeform:FORMat BYTE")
    osc.write(":WAVeform:UNSigned ON")
    osc.write(":WAVeform:POINts:MODE NORMal")
    osc.write(":WAVeform:POINts 60000")
    preamble = [float(v) for v in osc.ask(":WAVeform:PREamble?").strip().split(",")]
    return int(preamble[2]), 1.0 / preamble[4]


def disparar_e_ler(osc: KeysightDSOX4034A):
    osc.channels[1].display = True  # setter funciona (so o getter tem bug -- ver diag_margin_scope.py)
    osc.arm()
    osc.wait_for_armed()
    osc.force_trigger()
    osc.wait_for_trigger_complete(timeout_s=8.0)
    return ler_preamble_pontos_taxa(osc)


def h1_bracket_original_desde_reset(osc: KeysightDSOX4034A) -> bool:
    print("\n=== H1: bracket original (1.0s a 1.2s) a partir de *RST ===")
    resetar(osc)
    osc.write(":STOP")
    osc.write(":ACQuire:DIGitizer ON")
    osc.write(":ACQuire:SRATe:ANALog:AUTO OFF")
    osc.write(f":ACQuire:SRATe:ANALog {FS_HZ:.12g}")
    osc.write(":ACQuire:POINts:ANALog:AUTO OFF")
    osc.check_errors()
    for candidato_s in (1.0, 1.1, 1.19, 1.199, 1.2):
        pontos = round(candidato_s * FS_HZ)
        osc.write(f":ACQuire:POINts:ANALog {pontos}")
        erros_pontos = osc.check_errors()
        osc.write(f":TIMebase:RANGe {candidato_s:.12g}")
        erros_range = osc.check_errors()
        status = "OK" if not (erros_pontos or erros_range) else f"pontos={erros_pontos} range={erros_range}"
        print(f"  {candidato_s:>5.3f}s ({pontos} pts) -> {status}")
        if erros_pontos or erros_range:
            return False
    return True


def h2_transicao_desde_reset(osc: KeysightDSOX4034A) -> bool:
    print("\n=== H2: AUTO 0.2s -> Digitizer 1.2s direto, a partir de *RST ===")
    resetar(osc)
    osc.configure_acquisition(sample_rate_hz=FS_HZ, points=6_000, duration_s=0.2)
    print("  AUTO 6000pts/0.2s -> OK")
    try:
        osc.configure_acquisition(
            sample_rate_hz=FS_HZ, points=36_000, duration_s=1.2,
            pre_trigger_s=0.5, digitizer=True,
        )
        print("  Digitizer 36000pts/1.2s direto -> OK")
        return True
    except Exception as exc:
        print(f"  Digitizer 36000pts/1.2s direto -> FALHOU: {exc}")
        return False


def _testar_um_lado_explicito(osc: KeysightDSOX4034A, *, nome: str, passos: list[str]):
    print(f"\n=== {nome} ===")
    resetar(osc)
    for cmd in passos:
        osc.write(cmd)
        erros = osc.check_errors()
        print(f"  {cmd!r:45s} -> {'OK' if not erros else erros}")
        if erros:
            return None
    digitizer_ligado = osc.ask(":ACQuire:DIGitizer?").strip()
    referencia = osc.ask(":TIMebase:REFerence?").strip()
    print(f"  :ACQuire:DIGitizer? -> {digitizer_ligado!r} (esperado 0/OFF)")
    print(f"  :TIMebase:REFerence? -> {referencia!r} (esperado algo tipo 'LEFT')")
    pontos, taxa = disparar_e_ler(osc)
    print(f"  REAL (apos SINGLE real): {pontos} pontos a {taxa:.1f} Sa/s (pedido 36000 a 30000 Sa/s)")
    return pontos, taxa, digitizer_ligado, referencia


def h3_pontos_explicitos_taxa_auto(osc: KeysightDSOX4034A):
    return _testar_um_lado_explicito(
        osc,
        nome="H3: so POINTS explicito (SRATe fica AUTO), REFerence LEFT",
        passos=[
            ":STOP",
            ":ACQuire:TYPE NORMal",
            ":ACQuire:MODE RTIMe",
            ":ACQuire:DIGitizer OFF",
            ":TIMebase:MODE MAIN",
            ":TIMebase:RANGe 1.2",
            ":TIMebase:REFerence LEFT",
            ":TIMebase:POSition -0.5",
            ":ACQuire:SRATe:ANALog:AUTO ON",
            ":ACQuire:POINts:ANALog:AUTO OFF",
            ":ACQuire:POINts:ANALog 36000",
        ],
    )


def h4_taxa_explicita_pontos_auto(osc: KeysightDSOX4034A):
    return _testar_um_lado_explicito(
        osc,
        nome="H4: so SRATe explicito (POINTS fica AUTO), REFerence LEFT",
        passos=[
            ":STOP",
            ":ACQuire:TYPE NORMal",
            ":ACQuire:MODE RTIMe",
            ":ACQuire:DIGitizer OFF",
            ":TIMebase:MODE MAIN",
            ":TIMebase:RANGe 1.2",
            ":TIMebase:REFerence LEFT",
            ":TIMebase:POSition -0.5",
            ":ACQuire:SRATe:ANALog:AUTO OFF",
            f":ACQuire:SRATe:ANALog {FS_HZ:.12g}",
            ":ACQuire:POINts:ANALog:AUTO ON",
        ],
    )


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

        h1_ok = h1_bracket_original_desde_reset(osc)
        h2_ok = h2_transicao_desde_reset(osc)
        h3 = h3_pontos_explicitos_taxa_auto(osc)
        h4 = h4_taxa_explicita_pontos_auto(osc)

        print("\n\n========== RESUMO ==========")
        print(f"H1 (bracket 1.0-1.2s a partir de *RST): {'reproduziu o sucesso original' if h1_ok else 'FALHOU -- sucesso original era estado residual'}")
        print(f"H2 (AUTO 0.2s -> Digitizer 1.2s a partir de *RST): {'funcionou (falha bancada era estado residual)' if h2_ok else 'FALHOU (confirma: nao e estado residual, e real)'}")
        if h3 is None:
            print("H3 (so POINTS explicito, taxa AUTO): rejeitado por erro SCPI antes de disparar")
        else:
            pontos, taxa, digitizer_ligado, referencia = h3
            print(
                f"H3 (so POINTS explicito, taxa AUTO): DIGitizer={digitizer_ligado!r} "
                f"REFerence={referencia!r} -> {pontos} pontos reais a {taxa:.1f} Sa/s"
            )
        if h4 is None:
            print("H4 (so SRATe explicito, pontos AUTO): rejeitado por erro SCPI antes de disparar")
        else:
            pontos, taxa, digitizer_ligado, referencia = h4
            print(
                f"H4 (so SRATe explicito, pontos AUTO): DIGitizer={digitizer_ligado!r} "
                f"REFerence={referencia!r} -> {pontos} pontos reais a {taxa:.1f} Sa/s"
            )

        resetar(osc)
        osc.configure_acquisition(sample_rate_hz=FS_HZ, points=6_000, duration_s=0.2)
        print("\n(osciloscópio devolvido ao modo AUTO 6000pts/0.2s de sempre)")
    finally:
        osc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
