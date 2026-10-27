"""Diagnóstico 2026-10-07: fonte e osciloscópio concordam NO MESMO INSTANTE?

Na bateria, a fonte mediu 126,6 Vrms (MEAS interno, sense INT = antes do relé
de saída) enquanto o Keysight capturou ~56 Vrms nos bornes. Este script lê os
dois lado a lado, a cada ~0,5 s:

  fase 1: 127 Vrms direto (como diag_saida_vs_medida.py), ~15 s;
  fase 2: VOLT 0 -> 127 em degrau com a saída ligada (como a classe 01), ~10 s.

O osciloscópio é posto em trigger AUTO no CH1 (a bateria reconfigura tudo de
novo quando rodar). Saída da fonte sempre desligada no final, inclusive em
erro/Ctrl+C. Exige a confirmação digitada ENERGIZAR-127V. Feche o MX GUI e a
CLI da bancada antes.
"""
import time

import pyvisa
from pyvisa.constants import BufferOperation, Parity, StopBits, VI_ASRL_FLOW_NONE

TENSAO_V = 127.0
CONFIRMACAO = "ENERGIZAR-127V"

rm = pyvisa.ResourceManager()

fonte = rm.open_resource("ASRL10::INSTR")
fonte.baud_rate = 115200
fonte.data_bits = 8
fonte.parity = Parity.none
fonte.stop_bits = StopBits.one
fonte.flow_control = VI_ASRL_FLOW_NONE
fonte.read_termination = "\n"
fonte.write_termination = "\n"
fonte.timeout = 3000
fonte.flush(BufferOperation.discard_read_buffer)

osc = rm.open_resource("USB0::0x0957::0x17A4::MY59240844::0::INSTR")
osc.timeout = 5000
# Device clear: uma consulta anterior que estourou o timeout (ex.: :MEASure
# sem trigger) deixa a interface USBTMC do Keysight travada.
osc.clear()
osc.write("*CLS")  # descarta erros velhos (ex.: -310 deixado pelo travamento)


def checar_fonte(contexto, timeout_ms=3000):
    fonte.timeout = timeout_ms
    try:
        err = fonte.query("SYSTem:ERRor?").strip()
    finally:
        fonte.timeout = 3000
    if not err.startswith("0"):
        raise RuntimeError(f"fonte, {contexto}: {err}")


def medir_osc(cmd):
    try:
        v = float(osc.query(cmd))
    except Exception:  # noqa: BLE001
        return float("nan")
    return float("nan") if abs(v) > 9e36 else v


def linha(t0, rotulo):
    fonte.write("INSTrument:NSELect 1")
    va = float(fonte.query("MEASure:VOLTage:AC?"))
    vrms = medir_osc(":MEASure:VRMS? DISPlay,AC,CHANnel1")
    vmax = medir_osc(":MEASure:VMAX? CHANnel1")
    razao = vrms / va if va > 1 else float("nan")
    print(f"  {rotulo:<7} {time.monotonic() - t0:5.1f}   {va:8.2f}   {vrms:8.2f}   {vmax:8.1f}   {razao:6.3f}")


print("Fonte:", fonte.query("*IDN?").strip())
print("Osc:  ", osc.query("*IDN?").strip())
if "MX30" not in fonte.query("*IDN?") or "DSO-X 4034A" not in osc.query("*IDN?"):
    raise SystemExit("IDN inesperado, abortando")

# Osciloscópio: CH1 como a bateria (probe 500, DC), mas trigger AUTO no
# próprio CH1 para a tela e as medidas acompanharem a saída continuamente.
for cmd in (":CHANnel1:DISPlay 1", ":CHANnel1:PROBe 500", ":CHANnel1:COUPling DC",
            ":CHANnel1:SCALe 50", ":CHANnel1:OFFSet 0", ":TIMebase:SCALe 0.01",
            ":TIMebase:POSition 0", ":TRIGger:MODE EDGE", ":TRIGger:EDGE:SOURce CHANnel1",
            ":TRIGger:EDGE:LEVel 0", ":TRIGger:SWEep AUTO", ":RUN"):
    osc.write(cmd)
err = osc.query(":SYSTem:ERRor?").strip()
if not err.startswith("+0"):
    raise SystemExit(f"Keysight reportou erro na configuração: {err}")

fonte.write("OUTPut:STATe OFF")
for cmd in ("INSTrument:COUPle ALL", "VOLTage:RANGe 300", "FREQuency 60",
            "FUNCtion:SHAPe SINusoid", f"VOLTage {TENSAO_V}"):
    fonte.write(cmd)
    checar_fonte(cmd, timeout_ms=15000 if "RANGe" in cmd else 3000)

print(f"\nVai ligar a saída em {TENSAO_V:g} Vrms (faixa 300 V), sem carga, ~25 s no total.")
if input(f"Digite {CONFIRMACAO} para continuar: ") != CONFIRMACAO:
    fonte.close()
    osc.close()
    raise SystemExit("Não confirmado; saída continua OFF.")

print("\n  fase       t(s)   fonte A   osc Vrms   osc Vmax   osc/fonte")
try:
    fonte.write("OUTPut:STATe ON")
    checar_fonte("OUTPut:STATe ON")
    t0 = time.monotonic()
    while time.monotonic() - t0 < 15:
        linha(t0, "direto")
        time.sleep(0.3)

    fonte.write("VOLTage 0")
    checar_fonte("VOLTage 0")
    time.sleep(2.0)
    t0 = time.monotonic()
    linha(t0, "zero")
    fonte.write(f"VOLTage {TENSAO_V}")
    while time.monotonic() - t0 < 10:
        linha(t0, "degrau")
        time.sleep(0.3)
finally:
    fonte.write("OUTPut:STATe OFF")
    time.sleep(0.3)
    print("\nOUTPut:STATe? ->", fonte.query("OUTPut:STATe?").strip(), "(0 = desligada; confira no painel)")
    fonte.close()
    osc.close()
