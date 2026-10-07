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

import datetime as _dt
import logging
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import List, Optional

import mestre
import preflight
import preflight_new

logger = logging.getLogger(__name__)

# Opt-out do terminal de diagnóstico (ver comando_terminal_diagnostico() /
# SessaoCLI._abrir_terminal_de_diagnostico()) — "0"/"false"/"off"/"no"
# desliga; qualquer outro valor (inclusive ausente) mantém o padrão (ligado).
# Existe para quem roda a CLI sem uma sessão gráfica de console (ex.: SSH
# headless) ou simplesmente não quer a janela extra.
DIAGNOSTICO_ABRIR_TERMINAL = os.getenv("DIAGNOSTICO_ABRIR_TERMINAL", "1").strip().lower() not in (
    "0", "false", "off", "no",
)


def comando_terminal_diagnostico(caminho_log: Path) -> List[str]:
    """Monta o comando do PowerShell que acompanha ``caminho_log`` (a
    transcrição SCPI da sessão, ver ``mestre.configurar_log_de_sessao``) em
    tempo real — o equivalente a ``tail -f`` no Windows. Função PURA: só
    monta a lista de argumentos, não abre nada sozinha (ver
    ``SessaoCLI._abrir_terminal_de_diagnostico``, quem chama
    ``subprocess.Popen`` de fato) — assim dá para testar offline sem
    depender de conseguir abrir uma janela de verdade."""
    titulo = f"diagnostico SCPI - {caminho_log.parent.name}"
    script = (
        f"$Host.UI.RawUI.WindowTitle = '{titulo}'; "
        f"Write-Host 'Acompanhando {caminho_log} (Ctrl+C fecha so esta janela, nao a bancada)'; "
        f"Get-Content -Path '{caminho_log}' -Wait -Tail 20"
    )
    return ["powershell.exe", "-NoExit", "-Command", script]

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
                       Pula as classes de BATERIA_EXCLUIR (padrão: 08, pico
                       medido no teto da fonte); rode-as com "run <NN>".
  set diagnostico on|off
                       Liga/desliga log extra de STATus:OPERation:CONDition?/
                       OUTPut:STATe?/tensão imediata em pontos-chave de
                       run/run all — para testar as hipóteses do v1.7. Com
                       "on", também abre um terminal extra acompanhando a
                       transcrição SCPI da sessão em tempo real (tail -f).   [OFF]
  set capturas <N>    Mínimo de capturas por classe na bancada real: cada
                       classe roda max(N, padrão da classe) — ver "list".
                       Em classes com níveis discretos (SAG/SWELL/
                       HARMONICS), N por nível. Com "set capturas" ativo,
                       04/06/09/19 cobrem o intervalo do parâmetro e a 08
                       entra em CARACTERIZAÇÃO (rampa de amplitude).        [OFF]
  set capturas padrao Volta a usar só o padrão de cada classe (sorteio,
                       sem cobertura/caracterização).                       [OFF]
  set seed <N>        Seed base dos próximos run (inteiro >= 0). Seed de
                       cada captura = N + id x 1 000 000 + índice; mesma
                       seed => mesmas formas, parâmetros e plano de
                       capturas (testes reprodutíveis). Gravada no metadata
                       (base_seed). "set seed padrao" volta à do início.    [OFF]
  help / ?            Mostra esta referência.                              [OFF]
  quit / exit         Sai da CLI (não desliga nada por si só — a saída já
                       deve estar OFF entre comandos; ver "status").       [OFF]

Ordem recomendada para uma sessão do zero:
  comm  ->  trigger  ->  native  ->  (lowvoltage, só se for recomissionar)  ->  run all

Sem hardware (BENCH_MODE=0): comm/trigger/lowvoltage/native exigem bancada
física de verdade e falham com um erro claro; status/list/run continuam
funcionando em modo simulado.

Margem de captura: desde 2026-09-22 toda captura FÍSICA grava com folga fixa
de MARGEM_ANTES_S/MARGEM_DEPOIS_S (20ms antes / 50ms depois da janela nominal
por padrão) — não é mais opt-in ("set margin on|off" foi descontinuado, não
existe mais modo sem margem para captura real). Ajustável só por variável de
ambiente antes de iniciar a sessão, nunca em runtime.
""".strip("\n")


class SessaoCLI:
    def __init__(self) -> None:
        self.ultimo_resultado: dict[str, "mestre.ResultadoClasse"] = {}
        self._sessao_timestamp = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # Seed com que a CLI começou (env BASE_SEED ou o padrão): destino de
        # "set seed padrao".
        self._seed_inicial = mestre.BASE_SEED
        self._runs_nesta_sessao = 0
        # Janela de "tail -f" da transcrição SCPI (ver
        # _abrir_terminal_de_diagnostico) — no máximo uma por vez; a do run
        # anterior é fechada antes de abrir a do run atual.
        self._processo_terminal_diagnostico: Optional[subprocess.Popen] = None

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

    def _garantir_pasta_sessao(self) -> None:
        """Cria uma pasta NOVA para CADA ``run`` (não no boot da CLI —
        status/comm/trigger sem run não deixam pasta vazia).

        Antes, todos os ``run`` de uma sessão de CLI compartilhavam a mesma
        pasta e o segundo sobrescrevia o primeiro EM SILÊNCIO, mesmo com
        flags diferentes: na sessão 1, um ``run 01`` com ``margin on`` e
        ``diagnostico off`` foi apagado pelo ``run all`` seguinte (relatório
        01 §3 P1 caminho #7). O primeiro run mantém o nome histórico
        ``sessao_<timestamp>``; do segundo em diante, ``_run02``, ``_run03``...

        Também anexa o log de execução e a transcrição SCPI à pasta — sem
        isso nada do que foi enviado à fonte sobrevive ao fim do processo."""
        self._runs_nesta_sessao += 1
        sufixo = "" if self._runs_nesta_sessao == 1 else f"_run{self._runs_nesta_sessao:02d}"
        sessao_dir = mestre.RESULTS_DIR / f"sessao_{self._sessao_timestamp}{sufixo}"
        sessao_dir.mkdir(parents=True, exist_ok=True)
        mestre.SESSION_RESULTS_DIR = sessao_dir
        mestre.configurar_log_de_sessao(sessao_dir)
        print(f"Sessão gravando em: {sessao_dir}")
        if mestre.DIAGNOSTICO_MODE and mestre.BENCH_MODE and DIAGNOSTICO_ABRIR_TERMINAL:
            self._abrir_terminal_de_diagnostico(sessao_dir / "scpi_transcricao.log")

    def _abrir_terminal_de_diagnostico(self, caminho_log: Path) -> None:
        """Abre uma janela de console nova fazendo ``tail -f`` de
        ``caminho_log`` — pedido do dono em 2026-09-22 ("faça o diagnostico
        on abrir um terminal com algo como tail -f nas logs de scpi
        concomitantemente ao terminal"). Fecha a janela do run ANTERIOR
        desta mesma sessão de CLI antes de abrir a nova (só uma por vez,
        sempre acompanhando a pasta do run atual — cada run tem sua própria
        pasta/log, ver P06b). Nunca deixa uma falha aqui (console
        indisponível, ``powershell.exe`` não encontrado etc.) derrubar a
        sessão de bancada — só loga um aviso e segue sem a janela extra."""
        processo_anterior = self._processo_terminal_diagnostico
        if processo_anterior is not None and processo_anterior.poll() is None:
            try:
                processo_anterior.terminate()
            except Exception:  # noqa: BLE001 - best-effort, nunca crítico
                logger.warning("Não foi possível fechar o terminal de diagnóstico anterior", exc_info=True)
        self._processo_terminal_diagnostico = None
        try:
            self._processo_terminal_diagnostico = subprocess.Popen(
                comando_terminal_diagnostico(caminho_log),
                # CREATE_NEW_CONSOLE só existe no Windows (a bancada); fora dele
                # (testes offline no Linux) cai para 0 em vez de AttributeError.
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
        except Exception:  # noqa: BLE001 - conveniência, nunca pode derrubar a sessão
            logger.warning(
                "Não foi possível abrir o terminal de diagnóstico (tail -f de %s) — "
                "a sessão continua normalmente, sem essa janela extra.",
                caminho_log, exc_info=True,
            )

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
        print(
            f"margem: {mestre.ExperimentoBase.MARGEM_ANTES_S * 1000:.0f}ms antes / "
            f"{mestre.ExperimentoBase.MARGEM_DEPOIS_S * 1000:.0f}ms depois (fixo, "
            f"não é mais opt-in)   "
            f"diagnostico: {'ON' if mestre.DIAGNOSTICO_MODE else 'OFF'}   "
            f"set capturas: "
            f"{mestre.CAPTURAS_OVERRIDE if mestre.CAPTURAS_OVERRIDE is not None else 'não (padrão das classes)'}"
        )
        print(f"seed base: {mestre.BASE_SEED}" + (
            "" if mestre.BASE_SEED == self._seed_inicial else f" (início da sessão: {self._seed_inicial})"
        ))
        self._imprimir_capturas_por_classe()
        if mestre.SESSION_RESULTS_DIR is not None:
            print(f"Sessão: {mestre.SESSION_RESULTS_DIR}")
        if not self.ultimo_resultado:
            print("Nenhuma classe rodada nesta sessão ainda (use 'list' para ver as 20 classes).")
            return 0
        for resultado in sorted(self.ultimo_resultado.values(), key=lambda r: r.id):
            estado = "OK" if resultado.ok else f"FALHOU: {resultado.motivo}"
            print(f"  [{resultado.id}] {resultado.nome}: {estado}")
        return 0

    @staticmethod
    def _capturas_das_classes(scripts: Optional[List[Path]] = None) -> List[tuple]:
        """(id, nome, capturas_efetivas_da_classe) de cada classe, com a
        configuração ATUAL (set capturas, padrão da classe)."""
        linhas = []
        for script_path in scripts if scripts is not None else mestre._experiment_scripts():
            experimento_cls = mestre.Bancada._carregar_classe_experimento(script_path)
            nome = getattr(experimento_cls, "nome", script_path.stem)
            linhas.append((script_path.stem, nome, mestre.capturas_efetivas_da_classe(experimento_cls)))
        return linhas

    @staticmethod
    def _descrever_capturas(info: dict) -> str:
        if info["niveis"] > 1:
            return f"{info['total']} ({info['niveis']} níveis x {info['por_nivel']})"
        return str(info["total"])

    @staticmethod
    def _aviso_escritas_trace(linhas: List[tuple]) -> str:
        escritas = sum(info["escritas_trace"] for _, _, info in linhas)
        texto = (
            f"TRACe: até {escritas} gravações na Flash da AMETEK nesta bateria "
            f"(referência: a fonte travou na ~{mestre.ESCRITAS_TRACE_REFERENCIA_TRAVA}.ª "
            "gravação de uma conexão em 2026-09-16)."
        )
        if escritas > mestre.ESCRITAS_TRACE_REFERENCIA_TRAVA:
            texto = "ATENÇÃO — " + texto + " Considere 'run <NN>' por partes."
        return texto

    def _imprimir_capturas_por_classe(self) -> None:
        linhas = self._capturas_das_classes()
        print(
            "Capturas por classe na bancada (efetivas; a pré-validação de pico/rms "
            "ainda pode pular algumas, sempre logado):"
        )
        itens = [f"{classe_id}={self._descrever_capturas(info)}" for classe_id, _, info in linhas]
        for inicio in range(0, len(itens), 5):
            print("  " + "  ".join(itens[inicio : inicio + 5]))
        print("  " + self._aviso_escritas_trace(linhas))

    def cmd_list(self, _args: List[str]) -> int:
        for classe_id, nome, info in self._capturas_das_classes():
            resultado = self.ultimo_resultado.get(classe_id)
            if resultado is None:
                estado = "nunca rodou"
            elif resultado.ok:
                estado = "OK"
            else:
                estado = f"FALHOU: {resultado.motivo}"
            capturas = f"capturas {self._descrever_capturas(info)} (padrão {info['padrao']})"
            print(f"  {classe_id}  {nome:30s} {capturas:34s} {estado}")
        return 0

    def cmd_help(self, _args: List[str]) -> int:
        print(HELP_TEXT)
        return 0

    def cmd_set(self, args: List[str]) -> int:
        if len(args) < 2:
            print("Uso: set diagnostico on|off   |   set capturas <N>|padrao   |   set seed <N>|padrao")
            return 1
        chave, valor = args[0].lower(), args[1].lower()
        if chave == "margin":
            print(
                "set margin foi descontinuado em 2026-09-22: a margem de captura "
                f"({mestre.ExperimentoBase.MARGEM_ANTES_S * 1000:.0f}ms antes / "
                f"{mestre.ExperimentoBase.MARGEM_DEPOIS_S * 1000:.0f}ms depois) agora é "
                "SEMPRE aplicada em toda captura física — não há mais 'on'/'off'. Ver "
                "CHANGELOG/v1.11.md."
            )
            return 0
        if chave == "diagnostico":
            if valor not in ("on", "off"):
                print("Uso: set diagnostico on|off")
                return 1
            mestre.DIAGNOSTICO_MODE = valor == "on"
            print(f"diagnostico: {'ON' if mestre.DIAGNOSTICO_MODE else 'OFF'}")
            return 0
        if chave == "capturas":
            if valor in ("padrao", "padrão", "off"):
                mestre.CAPTURAS_OVERRIDE = None
                print("capturas: padrão de cada classe (sem set capturas; sorteio, sem caracterização da 08)")
                self._imprimir_capturas_por_classe()
                return 0
            try:
                n = int(args[1])
            except ValueError:
                print("Uso: set capturas <N> (inteiro positivo) ou set capturas padrao")
                return 1
            if n < 1:
                atual = mestre.CAPTURAS_OVERRIDE if mestre.CAPTURAS_OVERRIDE is not None else "padrão das classes"
                print(f"capturas: valor inválido ({n}); mantendo {atual}")
                return 1
            mestre.CAPTURAS_OVERRIDE = n
            print(f"capturas: {n} por classe (por nível, nas classes que têm níveis discretos)")
            self._imprimir_capturas_por_classe()
            return 0
        if chave == "seed":
            if valor in ("padrao", "padrão"):
                mestre.BASE_SEED = self._seed_inicial
                print(f"seed base: {mestre.BASE_SEED} (a do início da sessão)")
                return 0
            try:
                seed = int(args[1])
            except ValueError:
                print("Uso: set seed <N> (inteiro >= 0) ou set seed padrao")
                return 1
            if seed < 0:
                print(f"seed: valor inválido ({seed}); mantendo {mestre.BASE_SEED}")
                return 1
            mestre.BASE_SEED = seed
            print(f"seed base: {seed} (vale a partir do próximo run; gravada no metadata como base_seed)")
            return 0
        print(f"Chave desconhecida: {chave!r}. Use diagnostico, capturas ou seed.")
        return 1

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
        self._garantir_pasta_sessao()
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
            print(f"OK: [{resultado.id}] {resultado.nome} -> {resultado.pasta_esperada}")
        except Exception as exc:
            resultado = mestre.ResultadoClasse(script_path.stem, nome, ok=False, motivo=str(exc))
            print(f"FALHOU: [{resultado.id}] {resultado.nome}: {exc}")
            traceback.print_exc()
        finally:
            self.autorizar_saida(False)
        self.ultimo_resultado[resultado.id] = resultado
        return 0 if resultado.ok else 1

    def _run_all(self) -> int:
        excluidas = (
            f" SEM as classes {', '.join(mestre.BATERIA_EXCLUIR)} (BATERIA_EXCLUIR; rode-as "
            "isoladas com 'run <NN>' se precisar)."
            if mestre.BATERIA_EXCLUIR else ""
        )
        linhas = self._capturas_das_classes(mestre.scripts_da_bateria_fisica())
        total_capturas = sum(info["total"] for _, _, info in linhas)
        if not self.confirmar(
            "Bateria completa das 20 classes, sequencial, sem parar numa falha isolada"
            f"{excluidas or '.'} "
            f"Planejadas: {total_capturas} capturas. {self._aviso_escritas_trace(linhas)} "
            "Confirme que comm/trigger/native já passaram e que probe, cabos, E-stop e "
            "EUT estão conferidos.",
            "EXECUTAR-20-CLASSES",
        ):
            return 1
        self._garantir_pasta_sessao()
        self.autorizar_saida(True)
        try:
            scripts = mestre.scripts_da_bateria_fisica()
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
                print(f"  OK     [{resultado.id}] {resultado.nome} -> {resultado.pasta_esperada}")
            else:
                print(f"  FALHOU [{resultado.id}] {resultado.nome}: {resultado.motivo}")
        return 0 if ok == len(resultados) else 1

    # -- laço principal ----------------------------------------------------

    COMANDOS = {
        "status": cmd_status,
        "list": cmd_list,
        "help": cmd_help,
        "set": cmd_set,
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
