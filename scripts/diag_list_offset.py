"""Diagnóstico P-09: a MX30 aceita ``SOURce:LIST:VOLTage:OFFSet`` (offset DC por passo de LIST)?

O comando só aparece como "Related Command" de ``LIST:VOLTage`` no manual SCPI
(p. 96); não há definição. O braço C do experimento P-09
(``AMETEK_P09_BRACO=C``) depende dele. Este script SÓ CONSULTA:

  1. conecta (``AmetekMX30``: ``OUTPut:STATe OFF`` e ``*IDN?``, como sempre);
  2. confirma OUTPUT OFF (``OUTPut:STATe?``); se estiver ligado, para sem
     enviar mais nada;
  3. ``SOURce:MODE ACDC`` (com a saída OFF), consulta
     ``SOURce:LIST:VOLTage:OFFSet?`` e lê ``SYST:ERR?``;
  4. volta ao modo anterior (``--modo-anterior``, padrão AC: a Rev. 5.53 não
     implementa ``SOURce:MODE?``, então o modo vem do painel/operador);
  5. grava ``logs/diag_list_offset-<data>.json`` com a procedência
     (``git_commit``/``git_sujo``) e a transcrição SCPI.

Nunca envia ``OUTPut:STATe ON``; não pede confirmação de energização porque
não energiza. Ao fim, ``disconnect()`` repete ``ABORt`` + ``OUTPut:STATe OFF``.
Uma consulta sem resposta é esperada se o comando não existir (a Rev. 5.53
não responde a cabeçalho desconhecido e deixa ``-113`` na fila): o script
espera o ``*IDN?`` voltar antes de ler a fila.

Feche a CLI da bancada (libera COM10) antes de rodar.

Uso (PowerShell, na raiz do projeto):

    $env:BENCH_MODE = "1"
    env\\Scripts\\python.exe scripts\\diag_list_offset.py

Sem hardware (exercita o fluxo; resultado FICTÍCIO):

    env\\Scripts\\python.exe scripts\\diag_list_offset.py --simulado [--sim-suportado]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "logica"))

from ametek_orm import AmetekMX30  # noqa: E402

PORTA = "COM10"
BAUD = 115_200
# Limites só para o construtor (nada é programado nem energizado aqui); os
# mesmos de scripts/diag_acdc_amplitude.py para o range 300 V.
MAX_RMS = 300.0
MAX_PICO_V = 415.8
LIMITE_CORRENTE_A = 0.5

logger = logging.getLogger("diag_list_offset")


def executar(fonte: AmetekMX30, *, modo_anterior: str) -> dict:
    """Passos 2 a 4 (sem energizar). Devolve o resultado da consulta."""
    saida_ligada = fonte.output_enabled
    if saida_ligada:
        return {"recusado": "OUTPUT ligado; nada foi enviado além da consulta de estado",
                "suportado": None}
    resultado = fonte.consultar_suporte_offset_lista(modo_restaurar=modo_anterior)
    resultado["output_off_confirmado_depois"] = not fonte.output_enabled
    return resultado


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--modo-anterior", default="AC", choices=("AC", "ACDC", "DC"),
                    help="modo a restaurar no fim (o do painel; padrão AC, o do baseline)")
    ap.add_argument("--simulado", action="store_true", help="sem hardware (resultado FICTÍCIO)")
    ap.add_argument("--sim-suportado", action="store_true",
                    help="só com --simulado: a fonte simulada aceita o comando")
    ap.add_argument("--saida", type=Path, default=RAIZ / "logs")
    args = ap.parse_args(argv)
    if args.sim_suportado and not args.simulado:
        ap.error("--sim-suportado só vale com --simulado")

    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    args.saida.mkdir(parents=True, exist_ok=True)
    base = args.saida / f"diag_list_offset-{ts}"
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    arquivo_log = logging.FileHandler(f"{base}.log", encoding="utf-8")
    logging.getLogger().addHandler(arquivo_log)

    try:  # procedência, calculada ANTES de tocar a fonte
        import mestre
        codigo = mestre.info_do_codigo(recalcular=True)
    except Exception:  # noqa: BLE001 - nunca impede o diagnóstico
        codigo = {}

    if not args.simulado and os.environ.get("BENCH_MODE", "").strip() not in {"1", "true", "TRUE", "yes", "YES"}:
        raise SystemExit("Defina BENCH_MODE=1 para usar a bancada real (ou use --simulado).")

    fonte = AmetekMX30(
        PORTA, baudrate=BAUD, timeout_s=5.0, query_eot=True, expected_model="MX30",
        max_voltage_rms=MAX_RMS, max_peak_v=MAX_PICO_V, max_current_a=LIMITE_CORRENTE_A,
        simulated=args.simulado, sim_list_offset_suportado=args.sim_suportado,
    )
    resultado: dict = {}
    try:
        resultado = executar(fonte, modo_anterior=args.modo_anterior)
    except Exception as exc:  # noqa: BLE001 - registra e devolve erro; o finally desliga
        logger.exception("Diagnóstico interrompido")
        resultado = {"erro": f"{type(exc).__name__}: {exc}", "suportado": None}
    finally:
        idn = fonte.idn
        comandos = list(fonte.command_log)
        fonte.disconnect()

    registro = {
        "tipo": "diag_list_offset", "pendencia": "P-09",
        "modo": "simulado" if args.simulado else "bancada",
        "simulado": args.simulado,
        "sim_list_offset_suportado": args.sim_suportado if args.simulado else None,
        "git_commit": codigo.get("git_commit"), "git_sujo": codigo.get("git_sujo"),
        "idn_fonte": idn, "modo_anterior_informado": args.modo_anterior,
        "energizou": False,
        "manual": "SOURce:LIST:VOLTage:OFFSet só como Related Command (manual SCPI p. 96): não confirmado",
        "resultado": resultado,
        "comandos_scpi": comandos,
    }
    with open(f"{base}.json", "w", encoding="utf-8") as fh:
        json.dump(registro, fh, indent=1, ensure_ascii=False)
    suportado = resultado.get("suportado")
    print(f"\nsuportado={suportado}  (resultado em {base}.json)")
    if not args.simulado:
        print("Confira OUTPUT OFF no painel.")
    logging.getLogger().removeHandler(arquivo_log)
    arquivo_log.close()
    return 0 if suportado is not None else 1


if __name__ == "__main__":
    sys.exit(main())
