"""Diagnóstico 2026-10-07: a AMETEK entrega o que foi programado?

Liga a saída em 50 Vrms / 60 Hz (faixa 150 V, sem carga), lê a cada 0,5 s o
que a PRÓPRIA fonte mede em cada fase (MEASure:VOLTage:AC?) por ~20 s e
desliga a saída no final (sempre, inclusive com Ctrl+C ou erro). Compare com
o MEAS do osciloscópio durante o teste.

Exige a confirmação digitada ENERGIZAR-50V (case-sensitive). Feche o MX GUI
antes (ele segura a COM10).
"""
import argparse
import time

import pyvisa
from pyvisa.constants import Parity, StopBits, VI_ASRL_FLOW_NONE

ap = argparse.ArgumentParser()
ap.add_argument("--tensao", type=float, default=50.0, help="Vrms (máx. 130 neste diagnóstico)")
ap.add_argument("--faixa", type=int, choices=(150, 300), default=150)
ap.add_argument("--duracao", type=float, default=20.0)
args = ap.parse_args()
if not 0 < args.tensao <= 130 or args.tensao > args.faixa * 0.95:
    raise SystemExit(f"Tensão {args.tensao} fora do permitido (0-130 V e < 95% da faixa {args.faixa})")
TENSAO_V = args.tensao
DURACAO_S = args.duracao
CONFIRMACAO = f"ENERGIZAR-{TENSAO_V:g}V"

rm = pyvisa.ResourceManager()
r = rm.open_resource("ASRL10::INSTR")
r.baud_rate = 115200
r.data_bits = 8
r.parity = Parity.none
r.stop_bits = StopBits.one
r.flow_control = VI_ASRL_FLOW_NONE
r.read_termination = "\n"
r.write_termination = "\n"
r.timeout = 3000


def checar(contexto, timeout_ms=3000):
    # A troca de faixa (VOLTage:RANGe) chaveia contatores e a fonte fica
    # muda por ~2 s: a resposta só chega depois disso.
    r.timeout = timeout_ms
    try:
        err = r.query("SYSTem:ERRor?").strip()
    finally:
        r.timeout = 3000
    if not err.startswith("0"):
        raise RuntimeError(f"{contexto}: {err}")


# Resposta atrasada de uma execução anterior (ex.: SYST:ERR? que estourou o
# timeout) não pode ser lida como resposta do *IDN? abaixo.
r.flush(pyvisa.constants.BufferOperation.discard_read_buffer)
idn = r.query("*IDN?").strip()
print("IDN:", idn)
if "MX30" not in idn:
    raise SystemExit("IDN inesperado, abortando")

r.write("OUTPut:STATe OFF")
for cmd in ("INSTrument:COUPle ALL", f"VOLTage:RANGe {args.faixa}", "FREQuency 60",
            "FUNCtion:SHAPe SINusoid", f"VOLTage {TENSAO_V}"):
    r.write(cmd)
    checar(cmd, timeout_ms=15000 if "RANGe" in cmd else 3000)

print(f"\nVai ligar a saída em {TENSAO_V:g} Vrms (faixa {args.faixa} V) nas 3 fases, sem carga, por ~{DURACAO_S:.0f} s.")
if input(f"Digite {CONFIRMACAO} para continuar: ") != CONFIRMACAO:
    r.close()
    raise SystemExit("Não confirmado; saída continua OFF.")

try:
    r.write("OUTPut:STATe ON")
    checar("OUTPut:STATe ON")
    t0 = time.monotonic()
    print("\n   t(s)   A (V)    B (V)    C (V)   programado")
    while time.monotonic() - t0 < DURACAO_S:
        medidas = []
        for fase in (1, 2, 3):
            r.write(f"INSTrument:NSELect {fase}")
            medidas.append(float(r.query("MEASure:VOLTage:AC?")))
        print(f"  {time.monotonic() - t0:5.1f}  " + "  ".join(f"{m:7.2f}" for m in medidas) + f"   {TENSAO_V:.0f}")
        time.sleep(0.5)
finally:
    r.write("OUTPut:STATe OFF")
    time.sleep(0.3)
    print("\nOUTPut:STATe? ->", r.query("OUTPut:STATe?").strip(), "(0 = desligada; confira no painel)")
    r.close()
