"""Diagnóstico 2026-10-07: estado dos canais do Keysight (SOMENTE LEITURA,
exceto :RUN para a tela atualizar e as medidas terem dado novo).

Rode com a bateria PARADA (o VISA não compartilha a sessão) e, de
preferência, com a fonte em 127 V rodando scripts/diag_saida_vs_medida.py em
outro terminal, para as medidas de VRMS/VPP terem sinal.
"""
import pyvisa

RESOURCE = "USB0::0x0957::0x17A4::MY59240844::0::INSTR"

rm = pyvisa.ResourceManager()
osc = rm.open_resource(RESOURCE)
osc.timeout = 5000
osc.clear()  # destrava a USBTMC se uma consulta anterior estourou o timeout


def q(cmd):
    try:
        resp = osc.query(cmd).strip()
    except Exception as exc:  # noqa: BLE001
        resp = f"<sem resposta: {type(exc).__name__}>"
    err = osc.query(":SYSTem:ERRor?").strip()
    print(f"  {cmd:<36} -> {resp}" + ("" if err.startswith("+0") or err.startswith("0") else f"   [ERRO: {err}]"))


print("IDN:", osc.query("*IDN?").strip())
osc.write(":RUN")
for ch in (1, 2, 3, 4):
    print(f"CH{ch}:")
    for c in ("DISPlay?", "PROBe?", "PROBe:ID?", "IMPedance?", "COUPling?", "SCALe?",
              "OFFSet?", "BWLimit?", "UNITs?"):
        q(f":CHANnel{ch}:{c}")
print("Trigger / medidas:")
for c in (":TRIGger:EDGE:SOURce?", ":MEASure:VRMS? DISPlay,AC,CHANnel1",
          ":MEASure:VPP? CHANnel1", ":MEASure:VRMS? DISPlay,AC,CHANnel2",
          ":MEASure:VPP? CHANnel2"):
    q(c)
osc.close()
