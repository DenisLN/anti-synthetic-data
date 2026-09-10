"""CLI interativa da bancada (REPL): substitui o fluxo fixo de 5 etapas do
antigo ``start_bench_windows.ps1 -Stage Full`` por comandos explícitos que o
operador digita na ordem que quiser.

Não implementa nenhuma lógica de segurança nova — reaproveita
``mestre.Bancada.from_env()`` e as funções já validadas de ``preflight.py``/
``preflight_new.py`` exatamente como o fluxo antigo fazia, uma invocação por
comando. Todas as confirmações físicas obrigatórias (fator de probe, Vrms/Hz,
a string digitada antes de energizar) continuam existindo: a probe e a
tensão/frequência são perguntadas uma vez por ``scripts/start_bench_windows.ps1``
antes deste processo iniciar (não mudam durante a sessão); cada comando que
energiza a saída pede a SUA própria confirmação aqui dentro.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import List, Optional

import mestre
import preflight
import preflight_new

HELP_TEXT = """
Comandos disponíveis (nenhum energiza a saída sem pedir confirmação própria):

  status              O que está configurado (porta, Keysight, ARM_OUTPUT,
                       tensão/frequência base) e o resultado da última
                       execução de cada classe nesta sessão.              [OFF]
  list                Lista as 20 classes com id, nome e status da última
                       execução (OK / FALHOU / nunca rodou).               [OFF]
  comm                Identifica AMETEK e Keysight (*IDN?), confirma
                       protocolo/porta. Equivale à antiga etapa
                       "Communication".                                    [OFF]
  trigger             Força aquisição do Keysight para validar
                       download/decodificação da waveform (BNC ainda não
                       testado aqui). Equivale à antiga etapa "Trigger".    [OFF]
  lowvoltage          Recomissionamento em 5 Vrms: valida BNC + trigger real
                       + RMS medido. Reprograma ~12 TRACe na Flash da AMETEK
                       (~40-50s) — rode isto só quando precisar
                       re-comissionar a bancada (fiação/probe mexidas), não
                       toda vez que ligar o sistema. Pede ENERGIZAR-5V.     [ON, 5V]
  native              Preflight de comandos nativos: STEP/PULSe/CSINe/
                       LIST:FREQuency/ACDC/MEASure* da AMETEK e canal 2 do
                       Keysight. Pede ENERGIZAR-COMANDOS.                   [ON]
  run <NN|nome>       Roda UMA classe (ex.: "run 02" ou "run SAG"). Pede
                       EXECUTAR-CLASSE-<NN>.                                [ON]
  run all             Roda a bateria completa das 20 classes, sequencialmente,
                       sem parar numa falha isolada (ver Prioridade 1 do
                       CHANGELOG). Pede EXECUTAR-20-CLASSES.                [ON]
  help / ?            Mostra esta referência.                              [OFF]
  quit / exit         Sai da CLI (não desliga nada por si só — a saída já
                       deve estar OFF entre comandos; ver "status").       [OFF]

Ordem recomendada para uma sessão do zero:
  comm  ->  trigger  ->  native  ->  (lowvoltage, só se for recomissionar)  ->  run all

Sem hardware (BENCH_MODE=0): comm/trigger/lowvoltage/native exigem bancada
física de verdade e falham com um erro claro; status/list/run continuam
funcionando em modo simulado.
""".strip("\n")


class SessaoCLI:
    def __init__(self) -> None:
        self.ultimo_resultado: dict[str, "mestre.ResultadoClasse"] = {}

    # -- infraestrutura ----------------------------------------------------

    def autorizar_saida(self, autorizado: bool) -> None:
        """Espelha o ARM_OUTPUT do ambiente nos três módulos que leram esse
        valor na hora do import (``mestre``, ``preflight``, ``preflight_new``
        fazem ``from mestre import ... OUTPUT_ARMED``, uma cópia própria cada
        um) — sem isto, autorizar a saída aqui dentro do processo de longa
        duração da CLI não teria efeito nenhum nas checagens de segurança
        dessas três funções, que continuariam vendo o valor de quando a CLI
        iniciou."""
        os.environ["ARM_OUTPUT"] = "YES" if autorizado else "NO"
        mestre.OUTPUT_ARMED = autorizado
        preflight.OUTPUT_ARMED = autorizado
        preflight_new.OUTPUT_ARMED = autorizado

    @staticmethod
    def confirmar(aviso: str, esperado: str) -> bool:
        print(aviso)
        resposta = input(f"Digite {esperado}: ")
        if resposta != esperado:
            print("Cancelado: confirmação não corresponde (comparação sensível a maiúsculas).")
            return False
        return True

    @staticmethod
    def _resolver_classe(token: str) -> Optional[Path]:
        token_norm = token.strip()
        id_norm = token_norm.zfill(2) if token_norm.isdigit() else None
        nome_norm = token_norm.upper()
        for script_path in mestre._experiment_scripts():
            if script_path.stem == id_norm:
                return script_path
            experimento_cls = mestre.Bancada._carregar_classe_experimento(script_path)
            if getattr(experimento_cls, "nome", "").upper() == nome_norm:
                return script_path
        return None

    # -- comandos sem energização --------------------------------------

    def cmd_status(self, _args: List[str]) -> int:
        print(f"Modo: {'BANCADA' if mestre.BENCH_MODE else 'SIMULADO'}")
        if mestre.BENCH_MODE:
            print(f"AMETEK: {mestre.AMETEK_PORT} @ {mestre.AMETEK_BAUDRATE} baud")
            print(f"Keysight: {mestre.KEYSIGHT_RESOURCE}")
        print(f"ARM_OUTPUT: {'YES' if mestre.OUTPUT_ARMED else 'NO'}")
        print(
            f"Tensão/frequência base: {mestre.BASE_VOLTAGE_RMS:.3f} Vrms / "
            f"{mestre.GRID_FREQUENCY_HZ:.3f} Hz"
        )
        if not self.ultimo_resultado:
            print("Nenhuma classe rodada nesta sessão ainda (use 'list' para ver as 20 classes).")
            return 0
        for resultado in sorted(self.ultimo_resultado.values(), key=lambda r: r.id):
            estado = "OK" if resultado.ok else f"FALHOU: {resultado.motivo}"
            print(f"  [{resultado.id}] {resultado.nome}: {estado}")
        return 0

    def cmd_list(self, _args: List[str]) -> int:
        for script_path in mestre._experiment_scripts():
            experimento_cls = mestre.Bancada._carregar_classe_experimento(script_path)
            nome = getattr(experimento_cls, "nome", script_path.stem)
            resultado = self.ultimo_resultado.get(script_path.stem)
            if resultado is None:
                estado = "nunca rodou"
            elif resultado.ok:
                estado = "OK"
            else:
                estado = f"FALHOU: {resultado.motivo}"
            print(f"  {script_path.stem}  {nome:30s} {estado}")
        return 0

    def cmd_help(self, _args: List[str]) -> int:
        print(HELP_TEXT)
        return 0

    # -- preflights (energizam conforme o comando) -----------------------

    def cmd_comm(self, _args: List[str]) -> int:
        return preflight.run(trigger_test=False, low_voltage=False)

    def cmd_trigger(self, _args: List[str]) -> int:
        return preflight.run(trigger_test=True, low_voltage=False)

    def cmd_lowvoltage(self, _args: List[str]) -> int:
        if not self.confirmar(
            "Recomissionamento em 5 Vrms (~40-50s reprogramando TRACe na Flash). "
            "Confirme fisicamente probe, cabos, E-stop e EUT.",
            "ENERGIZAR-5V",
        ):
            return 1
        self.autorizar_saida(True)
        try:
            return preflight.run(trigger_test=False, low_voltage=True)
        finally:
            self.autorizar_saida(False)

    def cmd_native(self, _args: List[str]) -> int:
        if not self.confirmar(
            "Preflight de comandos nativos (STEP/PULSe/CSINe/LIST/ACDC). "
            "Confirme fisicamente probe, cabos, E-stop e EUT.",
            "ENERGIZAR-COMANDOS",
        ):
            return 1
        self.autorizar_saida(True)
        try:
            return preflight_new.run_native_commands()
        finally:
            self.autorizar_saida(False)

    # -- execução de classes (sempre energiza) ---------------------------

    def cmd_run(self, args: List[str]) -> int:
        if not args:
            print("Uso: run <NN|nome>   ou   run all")
            return 1
        if args[0].lower() == "all":
            return self._run_all()
        return self._run_uma(args[0])

    def _run_uma(self, alvo: str) -> int:
        script_path = self._resolver_classe(alvo)
        if script_path is None:
            print(f"Classe não encontrada: {alvo!r}. Use 'list' para ver os ids/nomes válidos.")
            return 1
        experimento_cls = mestre.Bancada._carregar_classe_experimento(script_path)
        nome = getattr(experimento_cls, "nome", script_path.stem)
        confirmacao = f"EXECUTAR-CLASSE-{script_path.stem}"
        if not self.confirmar(
            f"Vai energizar a saída e rodar a classe {script_path.stem} ({nome}). "
            "Confirme fisicamente probe, cabos, E-stop e EUT.",
            confirmacao,
        ):
            return 1
        self.autorizar_saida(True)
        try:
            with mestre.Bancada.from_env(require_output=True) as bancada:
                # run_all() sempre passa por 01/NORMAL primeiro, que eleva a
                # saída a BASE_VOLTAGE_RMS (STEP é "sticky"). Uma classe
                # isolada aqui não tem essa garantia — sem isto, SAG/SWELL/
                # INTERRUPTION mediriam baseline no nível de segurança (0 V)
                # em vez de BASE_VOLTAGE_RMS (ver Bancada.assegurar_tensao_base).
                bancada.assegurar_tensao_base()
                experimento_cls(bancada).executar()
            resultado = mestre.ResultadoClasse(script_path.stem, nome, ok=True)
            print(f"OK: [{resultado.id}] {resultado.nome} -> {resultado.arquivo_esperado}")
        except Exception as exc:
            resultado = mestre.ResultadoClasse(script_path.stem, nome, ok=False, motivo=str(exc))
            print(f"FALHOU: [{resultado.id}] {resultado.nome}: {exc}")
            traceback.print_exc()
        finally:
            self.autorizar_saida(False)
        self.ultimo_resultado[resultado.id] = resultado
        return 0 if resultado.ok else 1

    def _run_all(self) -> int:
        if not self.confirmar(
            "Bateria completa das 20 classes, sequencial, sem parar numa falha isolada. "
            "Confirme que comm/trigger/native já passaram e que probe, cabos, E-stop e "
            "EUT estão conferidos.",
            "EXECUTAR-20-CLASSES",
        ):
            return 1
        self.autorizar_saida(True)
        try:
            scripts = mestre._experiment_scripts()
            with mestre.Bancada.from_env(require_output=True) as bancada:
                resultados = bancada.executar_bateria(scripts)
        except Exception as exc:
            print(f"BATERIA ABORTADA por falha de infraestrutura: {exc}")
            traceback.print_exc()
            return 1
        finally:
            self.autorizar_saida(False)

        for resultado in resultados:
            self.ultimo_resultado[resultado.id] = resultado
        ok = sum(1 for resultado in resultados if resultado.ok)
        print(f"\nResumo final: {ok}/{len(resultados)} classes OK")
        for resultado in resultados:
            if resultado.ok:
                print(f"  OK     [{resultado.id}] {resultado.nome} -> {resultado.arquivo_esperado}")
            else:
                print(f"  FALHOU [{resultado.id}] {resultado.nome}: {resultado.motivo}")
        return 0 if ok == len(resultados) else 1

    # -- laço principal ----------------------------------------------------

    COMANDOS = {
        "status": cmd_status,
        "list": cmd_list,
        "help": cmd_help,
        "comm": cmd_comm,
        "trigger": cmd_trigger,
        "lowvoltage": cmd_lowvoltage,
        "native": cmd_native,
        "run": cmd_run,
    }

    def loop(self) -> int:
        print(HELP_TEXT)
        print()
        while True:
            try:
                linha = input("bancada> ").strip()
            except EOFError:
                print()
                break
            if not linha:
                continue
            partes = linha.split()
            comando, args = partes[0].lower(), partes[1:]
            if comando in ("quit", "exit"):
                break
            if comando == "?":
                comando = "help"
            handler = self.COMANDOS.get(comando)
            if handler is None:
                print(f"Comando desconhecido: {comando!r}. Digite 'help' para a lista.")
                continue
            try:
                handler(self, args)
            except Exception as exc:  # nunca deixa a CLI cair por uma falha de comando
                print(f"ERRO: {exc}")
                traceback.print_exc()
        return 0


def main() -> int:
    return SessaoCLI().loop()


if __name__ == "__main__":
    sys.exit(main())
