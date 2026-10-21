"""CLI interativa da bancada (REPL): substitui o fluxo fixo de 5 etapas do
antigo ``start_bench_windows.ps1 -Stage Full`` por comandos explícitos que o
operador digita na ordem que quiser.

Não implementa nenhuma lógica de segurança nova — reaproveita
``mestre.Bancada.from_env()`` e as funções já validadas de
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
import re
import subprocess
import sys
import traceback
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import mestre
import perfis
import preflight_new
import sessao_io

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
                       tensão/frequência base, seed, capturas efetivas por
                       classe) e o resultado da última execução de cada
                       classe nesta sessão.                                 [OFF]
  list                Lista as 20 classes com id, nome, capturas efetivas
                       (e o padrão da classe) e status da última execução
                       (OK / FALHOU / nunca rodou).                         [OFF]
  comm                Identifica AMETEK e Keysight (*IDN?), confirma
                       protocolo/porta. Equivale à antiga etapa
                       "Communication".                                    [OFF]
  trigger             Força aquisição do Keysight para validar
                       download/decodificação da waveform (BNC ainda não
                       testado aqui). Equivale à antiga etapa "Trigger".    [OFF]
  lowvoltage          Recomissionamento na tensão base (BASE_VOLTAGE_RMS, a
                       digitada no início): valida BNC + trigger real
                       + RMS medido. Reprograma ~12 TRACe na Flash da AMETEK
                       (~40-50s) — rode isto só quando precisar
                       re-comissionar a bancada (fiação/probe mexidas), não
                       toda vez que ligar o sistema. Pede ENERGIZAR-TESTE.  [ON]
  native              Preflight de comandos nativos: STEP/PULSe/CSINe/
                       LIST:FREQuency/ACDC/MEASure* da AMETEK e canal 2 do
                       Keysight. Pede ENERGIZAR-COMANDOS.                   [ON]
  run <NN|nome>       Roda UMA classe (ex.: "run 02" ou "run SAG"). Pede
                       EXECUTAR-CLASSE-<NN>.                                [ON]
  run <lista>         Roda uma LISTA de classes por intervalos e/ou ids
                       soltos, na ordem numérica: "run 01-07,09-20",
                       "run 2,5,8", "run 10-16" (espaços ao redor de
                       vírgulas e hífens são aceitos).
                       Mesma execução e ganchos do run all (resumo final,
                       set recalibracao/html). Aplica BATERIA_EXCLUIR e pede
                       confirmação só da lista efetiva. Mostra as capturas de
                       cada classe e a estimativa de TRACe das escolhidas.
                       Pede EXECUTAR-CLASSES-<lista normalizada>, ex.:
                       EXECUTAR-CLASSES-01-07,09-20.                        [ON]
  run all            Roda a bateria completa das 20 classes, sequencialmente,
                       sem parar numa falha isolada (ver Prioridade 1 do
                       CHANGELOG). Pede EXECUTAR-20-CLASSES.                [ON]
                       Pula as classes de BATERIA_EXCLUIR (padrão: nenhuma
                       desde a v1.12); rode-as com "run <NN>". Mostra as
                       capturas planejadas e a estimativa de gravações de
                       TRACe antes de pedir a confirmação.
  run falhas [<pasta_sessao>]
                       Reexecuta o que deu problema numa sessão (padrão: a
                       última pasta criada por esta CLI): capturas
                       descartadas/inválidas, classes que falharam e as não
                       executadas por orçamento de TRACe, lidas do
                       <sessao>/falhas.json. Mesma seed, perfil e nível da
                       captura original; RECUSA sem energizar se tensão,
                       frequência, braço P-09, passo final SINE, limites
                       ou calibração atuais diferirem da sessão de origem. Cria sessão NOVA com "rerun_de". Pede a
                       confirmação normal (EXECUTAR-CLASSE-NN ou
                       EXECUTAR-CLASSES-<lista>).                           [ON]
  rerun <pasta_sessao> <id_captura|NN> [...]
                       Como "run falhas", só para as capturas (ex.: 10-0003)
                       ou classes (ex.: 10 = todas as entradas da classe em
                       falhas.json) escolhidas. Aceita também id de captura
                       gravada (procurado no metadata). Puladas por
                       capacidade/pré-validação são retiradas (só elas =
                       recusa: seriam puladas de novo).                     [ON]
  set diagnostico on|off
                       Liga/desliga log extra de STATus:OPERation:CONDition?/
                       OUTPut:STATe?/tensão imediata em pontos-chave de
                       run/run all — para testar as hipóteses do v1.7. Com
                       "on", também abre um terminal extra acompanhando a
                       transcrição SCPI da sessão em tempo real (tail -f).   [OFF]
  set diagnostico retrieve [on|off]
                       Com "on" (ou sem argumento), cada captura TRACE lê de
                       volta as TRACEs gravadas na fonte (TRACe:DATA?) DEPOIS
                       da captura terminar e com espera mínima de 2 s
                       (DIAGNOSTICO_RETRIEVE_ESPERA_S) desde a última escrita
                       de TRACe, e grava <sessao>/diagnostico_trace/<id>.npz
                       (enviado x lido) + desvio máximo no metadata. Soma
                       alguns segundos por captura (docs/diagnostico.md).   [OFF]
  set diagnostico bruto [on|off]
                       Preserva a exportação BYTE/NORMal dos canais antes da
                       interpolação, sem nova aquisição, em bruto_osciloscopio/.
                       Arquivos independentes com preamble, tempos e hash.  [OFF]
  set p09 A|B|C       Experimento P-09 (vale a partir da próxima conexão/run):
                       A = como sempre (modo AC); B = AC+DC com offset zero;
                       C = AC+DC com offset DC por passo de LIST (comando NÃO
                       confirmado no manual: a conexão consulta o suporte com
                       a saída OFF e recusa o run se a fonte não aceitar, sem
                       cair para A/B). B/C deixam TODA a conexão em AC+DC,
                       inclusive as classes nativas. Gravado no metadata como
                       p09_braco (docs/configuracao.md).                    [A]
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
  set perfil norma|literatura|fronteira|todos
                       Perfil de faixas do dataset (logica/perfis.py,
                       docs/perfis.md), gravado em cada captura (campo
                       "perfil"). "todos": run all / run <lista> / run <NN>
                       percorrem os TRÊS perfis (norma, literatura,
                       fronteira) na mesma sessão, cada classe uma vez por
                       perfil, e gravam tudo no mesmo NN_classe.npz
                       comprimido (chaves <perfil>/<versão>; SNRs em
                       snr_XXdb/NN_classe.npz). Classes cujo gerar() não
                       depende do perfil (01, 04, 07, 08, 09, 17, 18, 19;
                       perfis.classes_independentes_do_perfil) são
                       capturadas UMA vez (perfil literatura) e o metadata
                       dos outros perfis aponta para a mesma captura (mesmo
                       arquivo, índice e SHA-256). A confirmação conta só o
                       que roda de fato. norma = IEEE 1159 (flicker 2-7 %, inter-
                       harmônicas 0,5-2 %, THD até 20 %, sag 0,15-0,85 pu,
                       swell 1,15-1,75 pu); literatura = as faixas de
                       sempre (padrão, reproduz o dataset anterior);
                       fronteira = sag/swell em 0,1/0,9/1,1/1,8 pu. Vale a
                       partir do próximo run; env PERFIL define o inicial. [OFF]
  set sorteio on|off  Início, duração e fase sorteados em gerar() (padrão ON;
                       `arquivo/analises:docs/analise-2026-10-12/pendente/sorteio_inicio_fase_VERIFICAR_BANCADA.md`). ON:
                       o distúrbio cai em posição diferente a cada captura,
                       as classes de pulso (02/03/04) reprogramam fase de
                       disparo e pré-trigger do osciloscópio por captura e
                       cada captura TRACE regrava a Flash (a estimativa
                       passa a ser exata). OFF: posições fixas de antes
                       (60/80 ms, fase 0). Gravado em "sorteio_posicao";
                       env SORTEIO=0 define o inicial.                      [OFF]
  set recalibracao on|off
                       Ao fim de cada run/run all FÍSICO, recalcula os fatores
                       de extremo (scripts/recalibrar_extremos.py) só sobre a
                       sessão que acabou de rodar e GRAVA em logica/
                       calibracao_extremos.json. Nunca diminui um fator, nunca
                       usa --substituir e não cria tabela para condição nova
                       (avisa; rode o script à mão). Cada fator que mudou sai
                       em destaque (antes -> depois, tabela, classe); a cópia
                       anterior fica em <sessao>/calibracao_extremos.json. Os
                       run seguintes desta CLI já usam os fatores novos. Em
                       modo simulado não faz nada. Falha só avisa. Padrão
                       OFF (ligada: altera o JSON do repositório).          [OFF]
  set html on|off     Ao fim de cada run/run all, recorta a margem
                       (<sessao>/sem_margem/) e gera o relatório HTML
                       autocontido da versão recortada, dados puros
                       (<sessao>/relatorio_<sessao>.html; logica/
                       relatorio_html.py --snr para um nível de ruído). Pode
                       levar minutos e passar de 20 MB numa bateria completa.
                       Falha só avisa. Padrão OFF.                          [OFF]
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

# Classes da bateria (experimentos_nativos/NN.py e experimentos_waveform/NN.py,
# 01 a 20; ver mestre._experiment_scripts()).
TOTAL_CLASSES = 20


def _id_de_classe(token: str) -> int:
    if not (token.isascii() and token.isdigit()):
        raise ValueError(f"{token!r} não é um id de classe (use números de 01 a {TOTAL_CLASSES:02d})")
    numero = int(token)
    if not 1 <= numero <= TOTAL_CLASSES:
        raise ValueError(f"classe {token} inexistente (as classes são 01 a {TOTAL_CLASSES:02d})")
    return numero


def parsear_lista_classes(texto: str) -> List[int]:
    """Converte "01-07,09-20", "2,5,8" ou "10-16" em ids ordenados e sem
    repetição. Função pura: não abre instrumento nem lê arquivo. Recusa
    (ValueError com o motivo) id fora de 01-20, intervalo invertido
    ("07-01"), intervalo incompleto ("01-"), item vazio ("01,,02", vírgula
    sobrando) e lista vazia."""
    if not texto.strip():
        raise ValueError("lista vazia")
    ids = set()
    for parte in texto.split(","):
        parte = parte.strip()
        if not parte:
            raise ValueError("item vazio na lista (vírgula sobrando ou repetida)")
        if "-" in parte:
            inicio_txt, _, fim_txt = parte.partition("-")
            if not inicio_txt.strip() or not fim_txt.strip():
                raise ValueError(f"intervalo incompleto {parte!r} (use inicio-fim, ex.: 01-07)")
            inicio, fim = _id_de_classe(inicio_txt.strip()), _id_de_classe(fim_txt.strip())
            if inicio > fim:
                raise ValueError(f"intervalo invertido {parte!r} (o início é maior que o fim)")
            ids.update(range(inicio, fim + 1))
        else:
            ids.add(_id_de_classe(parte))
    return sorted(ids)


def normalizar_lista_classes(ids: List[int]) -> str:
    """Forma canônica usada na confirmação: sequências viram intervalo.
    [1..7, 9..20] -> "01-07,09-20"; [2, 5, 8] -> "02,05,08"."""
    partes = []
    i = 0
    while i < len(ids):
        j = i
        while j + 1 < len(ids) and ids[j + 1] == ids[j] + 1:
            j += 1
        partes.append(f"{ids[i]:02d}" if j == i else f"{ids[i]:02d}-{ids[j]:02d}")
        i = j + 1
    return ",".join(partes)


class SessaoCLI:
    def __init__(self) -> None:
        self.ultimo_resultado: dict[str, "mestre.ResultadoClasse"] = {}
        self._sessao_timestamp = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # Seed com que a CLI começou (env BASE_SEED ou o padrão): destino de
        # "set seed padrao".
        self._seed_inicial = mestre.BASE_SEED
        self._bloqueio_sessao = None
        self._runs_nesta_sessao = 0
        # Perfil de faixas de cada run desta CLI, na ordem (vai para sessao.json
        # de cada pasta, em "perfis_usados_na_cli").
        self._perfis_usados: List[str] = []
        # Janela de "tail -f" da transcrição SCPI (ver
        # _abrir_terminal_de_diagnostico) — no máximo uma por vez; a do run
        # anterior é fechada antes de abrir a do run atual.
        self._processo_terminal_diagnostico: Optional[subprocess.Popen] = None
        # Ganchos de fim de run (set recalibracao / set html), ambos OFF por
        # padrão; ver _fim_da_sessao().
        self.recalibracao_ao_fim = False
        self.html_ao_fim = False
        # Última pasta de sessão criada por esta CLI (destino de "run falhas").
        self._ultima_sessao_dir: Optional[Path] = None
        # Modo roteiro (--comando, usado por scripts/visita_bancada.py): uma
        # exceção num run de classe ou a bateria abortada por infraestrutura
        # liga esta marca, e o roteiro para (não repete nem segue sozinho).
        self.falha_infraestrutura = False

    # -- infraestrutura ----------------------------------------------------

    def autorizar_saida(self, autorizado: bool) -> None:
        """Espelha o ARM_OUTPUT do ambiente nos dois módulos que leram esse
        valor na hora do import (``mestre`` e ``preflight_new``
        fazem ``from mestre import ... OUTPUT_ARMED``, uma cópia própria cada
        um) — sem isto, autorizar a saída aqui dentro do processo de longa
        duração da CLI não teria efeito nenhum nas checagens de segurança
        dessas funções, que continuariam vendo o valor de quando a CLI
        iniciou."""
        os.environ["ARM_OUTPUT"] = "YES" if autorizado else "NO"
        mestre.OUTPUT_ARMED = autorizado
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
        # Recuperar somente arquivos: nunca repetir capturas nem abrir instrumentos.
        # A pasta do novo run ainda não existe e não entra nesta varredura.
        sessao_io.recuperar_sessoes_interrompidas(mestre.RESULTS_DIR)
        self._liberar_bloqueio_sessao()
        # mkdir exclusivo também protege CLIs iniciadas no mesmo segundo:
        # nunca reutilize uma pasta existente, mesmo se seu escritor terminou.
        while True:
            self._runs_nesta_sessao += 1
            sufixo = "" if self._runs_nesta_sessao == 1 else f"_run{self._runs_nesta_sessao:02d}"
            sessao_dir = mestre.RESULTS_DIR / f"sessao_{self._sessao_timestamp}{sufixo}"
            try:
                sessao_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            break
        try:
            self._bloqueio_sessao = sessao_io.BloqueioSessao(sessao_dir)
            mestre.SESSION_RESULTS_DIR = sessao_dir
            self._ultima_sessao_dir = sessao_dir
            mestre.configurar_log_de_sessao(sessao_dir)
            print(f"Sessão gravando em: {sessao_dir}")
            # A procedência é recalculada a cada pasta; a calibração é copiada.
            self._perfis_usados.append(mestre.PERFIL_TODOS_ROTULO if mestre.PERFIL_TODOS else mestre.PERFIL)
            mestre.preparar_pasta_da_sessao(
                sessao_dir, bancada=mestre.BENCH_MODE, perfis_usados=list(self._perfis_usados),
            )
            if mestre.DIAGNOSTICO_MODE and mestre.BENCH_MODE and DIAGNOSTICO_ABRIR_TERMINAL:
                self._abrir_terminal_de_diagnostico(sessao_dir / "scpi_transcricao.log")
        except BaseException:
            self._liberar_bloqueio_sessao()
            raise

    def _liberar_bloqueio_sessao(self) -> None:
        if self._bloqueio_sessao is not None:
            self._bloqueio_sessao.close()
            self._bloqueio_sessao = None

    def _abrir_terminal_de_diagnostico(self, caminho_log: Path) -> None:
        """Abre uma janela de console nova fazendo ``tail -f`` de
        ``caminho_log`` — recurso de ``set diagnostico on`` (2026-09-22): o
        terminal acompanha a transcrição SCPI do run enquanto ele roda.
        Fecha a janela do run ANTERIOR
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
            f"diagnostico retrieve: {'ON' if mestre.DIAGNOSTICO_RETRIEVE else 'OFF'}   "
            f"diagnostico bruto: {'ON' if mestre.SALVAR_BRUTO_OSCILOSCOPIO else 'OFF'}   "
            f"p09: {mestre.P09_BRACO}   "
            f"set capturas: "
            f"{mestre.CAPTURAS_OVERRIDE if mestre.CAPTURAS_OVERRIDE is not None else 'não (padrão das classes)'}"
        )
        print(f"seed base: {mestre.BASE_SEED}" + (
            "" if mestre.BASE_SEED == self._seed_inicial else f" (início da sessão: {self._seed_inicial})"
        ))
        print(f"perfil de faixas: {self._descrever_perfil()}")
        print(f"sorteio de início/duração/fase: {'ON' if mestre.SORTEIO_POSICAO else 'OFF'}")
        print(
            f"recalibração automática ao fim do run: {'ON' if self.recalibracao_ao_fim else 'OFF'}   "
            f"relatório HTML ao fim do run: {'ON' if self.html_ao_fim else 'OFF'}"
        )
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
    def _descrever_perfil() -> str:
        if mestre.PERFIL_TODOS:
            return f"todos ({', '.join(mestre.perfis_da_rodada())}; um só NN_classe.npz por classe)"
        return mestre.PERFIL

    @staticmethod
    def _texto_dos_perfis() -> str:
        if not mestre.PERFIL_TODOS:
            return ""
        return f", nos perfis {', '.join(mestre.perfis_da_rodada())} (classes que dependem do perfil: uma vez por perfil; as demais, uma só vez)"

    @staticmethod
    def _capturas_das_classes(scripts: Optional[List[Path]] = None) -> List[tuple]:
        """(id, nome, capturas_efetivas_da_classe) de cada classe, com a
        configuração ATUAL (set capturas, padrão da classe). Com
        ``set perfil todos`` a classe roda uma vez por perfil: ``total`` e
        ``escritas_trace`` são a SOMA dos três (o número de níveis, e com ele
        o de capturas, muda com o perfil) e ``por_perfil`` traz o detalhe."""
        linhas = []
        perfis_rodada = mestre.perfis_da_rodada()
        base = mestre._build_config() if len(perfis_rodada) > 1 else None
        for script_path in scripts if scripts is not None else mestre._experiment_scripts():
            experimento_cls = mestre.Bancada._carregar_classe_experimento(script_path)
            nome = getattr(experimento_cls, "nome", script_path.stem)
            if base is None:
                info = mestre.capturas_efetivas_da_classe(experimento_cls)
            else:
                # Só o que roda de fato: classe cujo gerar() não depende do perfil
                # entra uma vez (sob o perfil canônico); os outros perfis são
                # a mesma captura (perfis.plano_de_perfis).
                plano = perfis.plano_de_perfis(script_path.stem, perfis_rodada, base.sorteio_posicao)
                partes = {
                    perfil: mestre.capturas_efetivas_da_classe(experimento_cls, replace(base, perfil=perfil))
                    for perfil, _ in plano
                }
                espelhos = {perfil: e for perfil, e in plano if e}
                primeiro = next(iter(partes.values()))
                info = {
                    "padrao": primeiro["padrao"],
                    "niveis": max(i["niveis"] for i in partes.values()),
                    "por_nivel": primeiro["por_nivel"],
                    "total": sum(i["total"] for i in partes.values()),
                    "escritas_trace": sum(i["escritas_trace"] for i in partes.values()),
                    "escritas_trace_exatas": all(i["escritas_trace_exatas"] for i in partes.values()),
                    "por_perfil": {perfil: i["total"] for perfil, i in partes.items()},
                    "espelhos": espelhos,
                    "evitadas": (len(perfis_rodada) - len(partes)) * primeiro["total"] if espelhos else 0,
                }
            linhas.append((script_path.stem, nome, info))
        return linhas

    @staticmethod
    def _descrever_capturas(info: dict) -> str:
        if "por_perfil" in info:
            partes = " + ".join(f"{n} {perfil}" for perfil, n in info["por_perfil"].items())
            if info.get("espelhos"):
                iguais = ", ".join(p for e in info["espelhos"].values() for p in e)
                partes += f"; igual em {iguais}, sem recaptura"
            return f"{info['total']} ({partes})"
        if info["niveis"] > 1:
            return f"{info['total']} ({info['niveis']} níveis x {info['por_nivel']})"
        return str(info["total"])

    @staticmethod
    def _aviso_escritas_trace(linhas: List[tuple]) -> str:
        escritas = sum(info["escritas_trace"] for _, _, info in linhas)
        if linhas and all(info.get("escritas_trace_exatas") for _, _, info in linhas):
            # Sorteio ligado: cada captura TRACE tem forma única, o cache de
            # program_capture não reaproveita nada e cada uma regrava a Flash.
            quantidade = (
                f"{escritas} gravações na Flash da AMETEK nesta bateria (início/duração/fase "
                f"sorteados: cada captura TRACE grava a Flash, sem reaproveitar o cache; pelo "
                f"menos {escritas} s só de espera de gravação, 1 s por TRACe)"
            )
        else:
            quantidade = f"até {escritas} gravações na Flash da AMETEK nesta bateria"
        if linhas and "por_perfil" in linhas[0][2]:
            evitadas = sum(info.get("evitadas", 0) for _, _, info in linhas)
            quantidade += (
                f", só o que roda de fato nos perfis da rodada (as classes que não dependem do "
                f"perfil entram uma vez; {evitadas} capturas repetidas evitadas)"
            )
        texto = (
            f"TRACe: {quantidade} "
            f"(referência: a fonte travou na ~{mestre.ESCRITAS_TRACE_REFERENCIA_TRAVA}.ª "
            "gravação de uma conexão em 2026-09-16)."
        )
        texto += f" Orçamento operacional: {mestre.LIMITE_ESCRITAS_TRACE_CONEXAO} gravações por conexão."
        if escritas > mestre.LIMITE_ESCRITAS_TRACE_CONEXAO:
            texto = "RECUSADA — " + texto + " Divida as classes/capturas em conexões novas."
        return texto

    @staticmethod
    def _verificar_orcamento_trace(linhas: List[tuple]) -> bool:
        escritas = sum(info["escritas_trace"] for _, _, info in linhas)
        if escritas <= mestre.LIMITE_ESCRITAS_TRACE_CONEXAO:
            return True
        print(
            f"Execução recusada: estimativa sem retentativas de {escritas} gravações TRACe excede o "
            f"orçamento de {mestre.LIMITE_ESCRITAS_TRACE_CONEXAO} por conexão (o ORM também aborta a "
            f"bateria se o orçamento esgotar com retentativas). Divida classes/capturas "
            "em conexões novas. Nada foi energizado."
        )
        return False

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
            print("Uso: set diagnostico on|off|retrieve|bruto   |   set p09 A|B|C   |   set capturas <N>|padrao   |   set seed <N>|padrao   |   "
                "set perfil norma|literatura|fronteira|todos   |   set sorteio on|off   |   "
                "set recalibracao on|off   |   set html on|off")
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
            if valor == "bruto":
                estado = args[2].lower() if len(args) > 2 else "on"
                if estado not in ("on", "off") or len(args) > 3:
                    print("Uso: set diagnostico bruto [on|off]")
                    return 1
                mestre.SALVAR_BRUTO_OSCILOSCOPIO = estado == "on"
                print(f"diagnostico bruto: {'ON' if mestre.SALVAR_BRUTO_OSCILOSCOPIO else 'OFF'} "
                      "(exportação BYTE/NORMal em arquivos separados; sem consulta adicional)")
                return 0
            if valor == "retrieve":
                # set diagnostico retrieve [on|off]: independente do log (on/off).
                estado = args[2].lower() if len(args) > 2 else "on"
                if estado not in ("on", "off") or len(args) > 3:
                    print("Uso: set diagnostico retrieve [on|off]")
                    return 1
                mestre.DIAGNOSTICO_RETRIEVE = estado == "on"
                print(
                    f"diagnostico retrieve: {'ON' if mestre.DIAGNOSTICO_RETRIEVE else 'OFF'}"
                    + (
                        f" (lê de volta as TRACEs após cada captura TRACE, espera mínima "
                        f"{mestre.DIAGNOSTICO_RETRIEVE_ESPERA_S:g} s; custo de tempo por captura: docs/diagnostico.md)"
                        if mestre.DIAGNOSTICO_RETRIEVE else ""
                    )
                )
                return 0
            if valor not in ("on", "off"):
                print("Uso: set diagnostico on|off|retrieve|bruto [on|off]")
                return 1
            mestre.DIAGNOSTICO_MODE = valor == "on"
            print(f"diagnostico: {'ON' if mestre.DIAGNOSTICO_MODE else 'OFF'}")
            return 0
        if chave == "p09":
            braco = args[1].strip().upper()
            if braco not in ("A", "B", "C") or len(args) > 2:
                print(f"Uso: set p09 A|B|C (mantendo {mestre.P09_BRACO})")
                return 1
            mestre.P09_BRACO = braco
            descricao = {
                "A": "modo AC, como sempre",
                "B": "AC+DC com offset zero em todos os passos (isola o efeito AC+DC/P-17)",
                "C": "AC+DC com offset DC por passo de LIST (consulta o suporte com a saída OFF "
                     "e recusa o run se a fonte não aceitar; sem fallback)",
            }[braco]
            print(f"p09: {braco} — {descricao} (vale a partir do próximo run; gravado no metadata como p09_braco)")
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
            vence = [
                f"{classe_id} ({info['padrao']})"
                for classe_id, _, info in self._capturas_das_classes()
                if info["padrao"] > n
            ]
            if vence:
                print(
                    f"AVISO: o padrão da classe é maior que {n} e vence (capturas = max(set "
                    f"capturas, padrão)) em: {', '.join(vence)}."
                )
            print(
                "Com set capturas ativo, 04/06/09/19 cobrem o intervalo do parâmetro e a 08 "
                "entra em CARACTERIZAÇÃO (rampa de amplitude) quando roda mais de 1 captura. "
                "'set capturas padrao' desfaz."
            )
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
        if chave == "perfil":
            if valor == mestre.PERFIL_TODOS_ROTULO:
                mestre.PERFIL_TODOS = True
                print(
                    f"perfil de faixas: todos ({', '.join(mestre.perfis_da_rodada())}) — run all / run <lista> / "
                    "run <NN> percorrem os três na mesma sessão, um NN_classe.npz por classe (vale a partir do "
                    "próximo run; cada captura leva o seu perfil no metadata)"
                )
                return 0
            try:
                novo = perfis.validar(valor)
            except ValueError as exc:
                print(f"perfil: {exc} ou {mestre.PERFIL_TODOS_ROTULO}; mantendo {self._descrever_perfil()}")
                return 1
            mestre.PERFIL = novo
            mestre.PERFIL_TODOS = False
            print(f"perfil de faixas: {mestre.PERFIL} (vale a partir do próximo run; gravado no metadata como perfil)")
            return 0
        if chave == "sorteio":
            if valor not in ("on", "off"):
                print("Uso: set sorteio on|off")
                return 1
            mestre.SORTEIO_POSICAO = valor == "on"
            print(
                f"sorteio de início/duração/fase: {valor.upper()} (vale a partir do próximo run; "
                "gravado no metadata como sorteio_posicao)"
            )
            self._imprimir_capturas_por_classe()
            return 0
        if chave in ("recalibracao", "recalibração"):
            if valor not in ("on", "off"):
                print("Uso: set recalibracao on|off")
                return 1
            self.recalibracao_ao_fim = valor == "on"
            print(f"recalibração automática ao fim do run: {valor.upper()}")
            if self.recalibracao_ao_fim:
                print(
                    "AVISO: ao fim de cada run FÍSICO logica/calibracao_extremos.json será ALTERADO "
                    "(só sobe fator, nunca desce; condição nova não ganha tabela). A cópia anterior "
                    "fica em <sessao>/calibracao_extremos.json e os run seguintes desta CLI já usam "
                    "os fatores novos. Confira com 'git diff' antes de commitar."
                )
            return 0
        if chave == "html":
            if valor not in ("on", "off"):
                print("Uso: set html on|off")
                return 1
            self.html_ao_fim = valor == "on"
            print(f"relatório HTML ao fim do run: {valor.upper()}")
            if self.html_ao_fim:
                print(
                    "AVISO: ao fim de cada run a margem é recortada para <sessao>/sem_margem/ e o HTML "
                    "da versão recortada é gerado (pode levar minutos e passar de 20 MB numa bateria completa)."
                )
            return 0
        print(f"Chave desconhecida: {chave!r}. Use diagnostico, capturas, seed, perfil, sorteio, recalibracao ou html.")
        return 1

    # -- preflights (energizam conforme o comando) -----------------------

    def cmd_comm(self, _args: List[str]) -> int:
        return preflight_new.run_com_log(
            "comm", lambda: preflight_new.run_basic_stage(trigger_test=False, low_voltage=False)
        )

    def cmd_trigger(self, _args: List[str]) -> int:
        return preflight_new.run_com_log(
            "trigger-test", lambda: preflight_new.run_basic_stage(trigger_test=True, low_voltage=False)
        )

    def cmd_lowvoltage(self, _args: List[str]) -> int:
        if not self.confirmar(
            f"Recomissionamento na tensão base ({mestre.BASE_VOLTAGE_RMS:g} Vrms, "
            "~40-50s reprogramando TRACe na Flash). "
            "Confirme fisicamente probe, cabos, E-stop e EUT.",
            "ENERGIZAR-TESTE",
        ):
            return 1
        self.autorizar_saida(True)
        try:
            return preflight_new.run_com_log(
                "low-voltage", lambda: preflight_new.run_basic_stage(trigger_test=False, low_voltage=True)
            )
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
            return preflight_new.run_com_log("native-commands", preflight_new.run_native_commands)
        finally:
            self.autorizar_saida(False)

    # -- execução de classes (sempre energiza) ---------------------------

    def cmd_run(self, args: List[str]) -> int:
        if not args:
            print("Uso: run <NN|nome>   |   run <lista>   |   run all   |   run falhas [<pasta_sessao>]")
            return 1
        if args[0].lower() == "falhas":
            return self._run_falhas(args[1:])
        if args[0].lower() == "all":
            if len(args) != 1:
                print("Comando recusado: 'run all' não aceita argumentos extras. Nada foi energizado.")
                return 1
            return self._run_all()
        # Preserva limites entre tokens: juntar sem separador transformava
        # 'run 1 2,3' em 'run 12,3', executando uma seleção diferente.
        texto = " ".join(args)
        if "," in texto or "-" in texto:
            return self._run_lista(texto)
        if len(args) != 1:
            print("Comando recusado: use vírgulas ou intervalos para várias classes "
                  "(ex.: run 01,02). Nada foi energizado.")
            return 1
        return self._run_uma(args[0])

    def _run_lista(self, texto: str) -> int:
        """``run 01-07,09-20``: valida TUDO antes de qualquer confirmação ou
        contato com a bancada (recusa sem energizar)."""
        try:
            ids = parsear_lista_classes(texto)
        except ValueError as exc:
            print(f"Lista de classes recusada: {exc}. Exemplos: run 01-07,09-20 | run 2,5,8 | "
                  "run 10-16. Nada foi energizado.")
            return 1
        removidas = [numero for numero in ids if f"{numero:02d}" in mestre.BATERIA_EXCLUIR]
        ids = [numero for numero in ids if f"{numero:02d}" not in mestre.BATERIA_EXCLUIR]
        if removidas:
            print(f"Classes removidas por BATERIA_EXCLUIR: {normalizar_lista_classes(removidas)}.")
        if not ids:
            print("Nenhuma classe restante após BATERIA_EXCLUIR. Nada foi energizado. "
                  "Para uma execução isolada intencional, use 'run <NN>'.")
            return 1
        mapa = {script.stem: script for script in mestre._experiment_scripts()}
        scripts = [mapa[f"{numero:02d}"] for numero in ids]
        normalizada = normalizar_lista_classes(ids)
        linhas = self._capturas_das_classes(scripts)
        if not self._verificar_orcamento_trace(linhas):
            return 1
        total_capturas = sum(info["total"] for _, _, info in linhas)
        print(f"Classes escolhidas ({len(linhas)}), na ordem numérica, capturas planejadas:")
        for classe_id, nome, info in linhas:
            print(f"  {classe_id}  {nome:30s} {self._descrever_capturas(info)} capturas")
        if not self.confirmar(
            f"Vai energizar a saída e rodar as classes {normalizada} ({len(linhas)} classes"
            f"{self._texto_dos_perfis()}, "
            f"{total_capturas} capturas planejadas). {self._aviso_escritas_trace(linhas)} "
            "Confirme fisicamente probe, cabos, E-stop e EUT.",
            f"EXECUTAR-CLASSES-{normalizada}",
        ):
            return 1
        return self._executar_scripts(scripts)

    def _run_uma(self, alvo: str) -> int:
        script_path = self._resolver_classe(alvo)
        if script_path is None:
            print(f"Classe não encontrada: {alvo!r}. Use 'list' para ver os ids/nomes válidos.")
            return 1
        experimento_cls = mestre.Bancada._carregar_classe_experimento(script_path)
        nome = getattr(experimento_cls, "nome", script_path.stem)
        confirmacao = f"EXECUTAR-CLASSE-{script_path.stem}"
        linhas = self._capturas_das_classes([script_path])
        if not self._verificar_orcamento_trace(linhas):
            return 1
        extra = f" ({self._aviso_escritas_trace(linhas)})"
        if mestre.PERFIL_TODOS:
            extra = (
                f" nos 3 perfis ({self._descrever_capturas(linhas[0][2])} capturas planejadas; "
                f"{self._aviso_escritas_trace(linhas)})"
            )
        if not self.confirmar(
            f"Vai energizar a saída e rodar a classe {script_path.stem} ({nome}){extra}. "
            "Confirme fisicamente probe, cabos, E-stop e EUT.",
            confirmacao,
        ):
            return 1
        self._garantir_pasta_sessao()
        # O bloqueio da sessão só cai DEPOIS dos ganchos de fim (HTML,
        # recalibração), que escrevem na pasta; try/finally cobre qualquer saída.
        try:
            self.autorizar_saida(True)
            try:
                with mestre.Bancada.from_env(require_output=True) as bancada:
                    # run_all() sempre passa por 01/NORMAL primeiro, que eleva a
                    # saída a BASE_VOLTAGE_RMS (STEP é "sticky"). Uma classe
                    # isolada aqui não tem essa garantia — sem isto, SAG/SWELL/
                    # INTERRUPTION mediriam baseline no nível de segurança (0 V)
                    # em vez de BASE_VOLTAGE_RMS (ver Bancada.assegurar_tensao_base).
                    bancada.assegurar_tensao_base()
                    executados = bancada.executar_classe_nos_perfis(experimento_cls)
                resultado = mestre.ResultadoClasse(
                    script_path.stem, nome, ok=True,
                    descartadas=sum(getattr(e, "_capturas_descartadas_count", 0) for e in executados),
                    invalidas=sum(getattr(e, "_capturas_invalidas_count", 0) for e in executados),
                    puladas=sum(getattr(e, "_capturas_puladas_count", 0) for e in executados),
                )
                print(f"OK: [{resultado.id}] {resultado.nome} -> {resultado.pasta_esperada}{self._ressalvas(resultado)}")
                sucesso = True
            except Exception as exc:
                sucesso = False
                self.falha_infraestrutura = True
                resultado = mestre.ResultadoClasse(script_path.stem, nome, ok=False, motivo=str(exc))
                print(f"FALHOU: [{resultado.id}] {resultado.nome}: {exc}")
                traceback.print_exc()
            finally:
                self.autorizar_saida(False)
            self.ultimo_resultado[resultado.id] = resultado
            # Saída já desligada e Bancada fechada. Classe que falhou pode ter sido
            # falha de infraestrutura: só o run que terminou OK dispara os ganchos.
            if sucesso:
                self._fim_da_sessao(mestre.SESSION_RESULTS_DIR)
        finally:
            self._liberar_bloqueio_sessao()
        return 0 if resultado.ok else 1

    def _run_all(self) -> int:
        excluidas = (
            f" SEM as classes {', '.join(mestre.BATERIA_EXCLUIR)} (BATERIA_EXCLUIR; rode-as "
            "isoladas com 'run <NN>' se precisar)."
            if mestre.BATERIA_EXCLUIR else ""
        )
        scripts = mestre.scripts_da_bateria_fisica()
        if not scripts:
            print("Nenhuma classe restante após BATERIA_EXCLUIR. Nada foi energizado.")
            return 1
        linhas = self._capturas_das_classes(scripts)
        if not self._verificar_orcamento_trace(linhas):
            return 1
        total_capturas = sum(info["total"] for _, _, info in linhas)
        if not self.confirmar(
            "Bateria completa das 20 classes, sequencial, sem parar numa falha isolada"
            f"{self._texto_dos_perfis()}{excluidas or '.'} "
            f"Planejadas: {total_capturas} capturas. {self._aviso_escritas_trace(linhas)} "
            "Confirme que comm/trigger/native já passaram e que probe, cabos, E-stop e "
            "EUT estão conferidos.",
            "EXECUTAR-20-CLASSES",
        ):
            return 1
        return self._executar_scripts(scripts)

    def _executar_scripts(
        self, scripts: List[Path], *, perfis_rodada: Optional[Tuple[str, ...]] = None,
        selecao: Optional[Dict[str, Dict[str, Optional[Tuple[int, ...]]]]] = None,
    ) -> int:
        """Corpo comum de ``run all``, ``run <lista>`` e do rerun: uma pasta de
        sessão, a saída ligada só durante ``executar_bateria`` (que isola
        falhas de experimento e aborta em falha de infraestrutura), resumo
        final e os ganchos de fim de run. Quem chama já confirmou a execução.
        ``selecao`` (rerun): só as classes/perfis/capturas escolhidas, depois
        de levar a saída à tensão base (``assegurar_tensao_base``)."""
        self._garantir_pasta_sessao()
        # Bloqueio liberado só depois dos ganchos de fim (ver run de classe única).
        try:
            self.autorizar_saida(True)
            try:
                with mestre.Bancada.from_env(require_output=True) as bancada:
                    if selecao is None:
                        resultados = bancada.executar_bateria(scripts)
                    else:
                        bancada.assegurar_tensao_base()
                        resultados = bancada.executar_bateria(scripts, perfis_rodada, selecao=selecao)
            except Exception as exc:
                self.falha_infraestrutura = True
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
                    print(
                        f"  OK     [{resultado.id}] {resultado.nome} -> {resultado.pasta_esperada}"
                        f"{self._ressalvas(resultado)}"
                    )
                elif getattr(resultado, "nao_executada_orcamento", False):
                    print(f"  NÃO EXECUTADA (orçamento TRACe) [{resultado.id}] {resultado.nome}: "
                          f"{resultado.motivo}")
                else:
                    print(f"  FALHOU [{resultado.id}] {resultado.nome}: {resultado.motivo}")
            if any(getattr(r, "nao_executada_orcamento", False) for r in resultados):
                print("Orçamento de TRACe esgotado: OUTPUT OFF confirmado e conexão encerrada; nada foi "
                      "reconectado. O que não rodou está em falhas.json — confira o painel e use "
                      f"'run falhas {mestre.SESSION_RESULTS_DIR}' (pede confirmação nova).")
            # Falha de EXPERIMENTO não impede os ganchos (a bateria seguiu); a de
            # infraestrutura saiu acima, sem eles.
            self._fim_da_sessao(mestre.SESSION_RESULTS_DIR)
            return 0 if ok == len(resultados) else 1
        finally:
            self._liberar_bloqueio_sessao()

    # -- rerun do que deu problema (falhas.json) ------------------------------

    _ALVO_RERUN = re.compile(r"^\d{1,2}(-\d{4})?$")

    @staticmethod
    def _resolver_pasta_sessao(texto: str) -> Optional[Path]:
        caminho = Path(texto.strip().strip('"'))
        for candidato in (caminho, mestre.RESULTS_DIR / caminho):
            if candidato.is_dir():
                return candidato
        return None

    def _run_falhas(self, args: List[str]) -> int:
        """``run falhas [<pasta>]``: todas as entradas reexecutáveis de falhas.json."""
        if args:
            pasta = self._resolver_pasta_sessao(" ".join(args))
            if pasta is None:
                print(f"Pasta de sessão não encontrada: {' '.join(args)!r}. Nada foi energizado.")
                return 1
        else:
            pasta = self._ultima_sessao_dir
            if pasta is None:
                print("Nenhuma sessão criada por esta CLI ainda: use 'run falhas <pasta_sessao>'. "
                      "Nada foi energizado.")
                return 1
        return self._rerun(pasta, None)

    def cmd_rerun(self, args: List[str]) -> int:
        """``rerun <pasta> <id_captura|NN> [...]`` (a pasta pode ter espaços)."""
        alvos: List[str] = []
        resto = list(args)
        while resto and self._ALVO_RERUN.match(resto[-1]):
            alvos.insert(0, resto.pop())
        if not resto or not alvos:
            print("Uso: rerun <pasta_sessao> <id_captura|NN> [...]   (ex.: rerun sessao_2026-10-21_10-00-00 "
                  "10-0003 02). Nada foi energizado.")
            return 1
        pasta = self._resolver_pasta_sessao(" ".join(resto))
        if pasta is None:
            print(f"Pasta de sessão não encontrada: {' '.join(resto)!r}. Nada foi energizado.")
            return 1
        return self._rerun(pasta, alvos)

    @staticmethod
    @contextmanager
    def _contexto_restaurado(contexto: dict, rerun_de: dict):
        """Põe nos globais do ``mestre`` a seed base, ``set capturas``, sorteio
        e perfis da sessão de origem (e ``RERUN_DE``) só durante o rerun."""
        nomes = ("BASE_SEED", "CAPTURAS_OVERRIDE", "SORTEIO_POSICAO", "PERFIL", "PERFIL_TODOS", "RERUN_DE")
        antes = {nome: getattr(mestre, nome) for nome in nomes}
        try:
            mestre.BASE_SEED = int(contexto["base_seed"])
            mestre.CAPTURAS_OVERRIDE = contexto.get("capturas_override")
            mestre.SORTEIO_POSICAO = bool(contexto.get("sorteio_posicao", True))
            perfis_rodada = tuple(contexto.get("perfis_da_rodada") or (perfis.PERFIL_PADRAO,))
            mestre.PERFIL_TODOS = len(perfis_rodada) > 1
            mestre.PERFIL = perfis.PERFIL_PADRAO if mestre.PERFIL_TODOS else perfis_rodada[0]
            mestre.RERUN_DE = rerun_de
            yield perfis_rodada
        finally:
            for nome, valor in antes.items():
                setattr(mestre, nome, valor)

    def _rerun(self, pasta: Path, alvos: Optional[List[str]]) -> int:
        """Reproduz EXATAMENTE capturas/classes de ``pasta`` (mesmo
        indice_global -> mesma seed, capture_index, perfil e nível), numa
        sessão NOVA com ``rerun_de``. Recusa, sem energizar, se a condição
        atual (tensão, frequência, braço P-09, passo final SINE, limites ou
        calibração: ``mestre.CHAVES_CONDICAO_RERUN``) diferir da original."""
        try:
            contexto, selecao, itens, puladas = mestre.selecionar_para_rerun(pasta, alvos)
            if contexto.get("base_seed") is None:
                raise mestre.RerunRecusadoError("a sessão de origem não registra a seed base")
            # Tensão, frequência, P-09, passo final SINE, limites e calibração
            # têm de ser os da origem; senão a captura não se reproduz.
            mestre.verificar_condicao_para_rerun(contexto, mestre.condicao_atual(), pasta)
        except mestre.RerunRecusadoError as exc:
            print(f"Rerun recusado: {exc}. Nada foi energizado.")
            return 1
        if puladas:
            print(f"AVISO: {len(puladas)} captura(s) escolhida(s) foram PULADAS na origem (capacidade/"
                  "pré-validação) e foram RETIRADAS do rerun: na mesma condição seriam puladas de novo "
                  f"({', '.join(str(i.get('id_captura')) for i in puladas)}).")
        ids = sorted({str(i["id_captura"]) for i in itens if i.get("id_captura")})
        rerun_de = {
            "sessao": str(pasta),
            "calibracao_extremos_sha256": contexto.get("calibracao_extremos_sha256"),
            "ids_captura": ids,
            "classes": sorted(selecao),
            "itens": [
                {k: i.get(k) for k in ("tipo", "classe", "perfil", "indice_global", "id_captura")}
                for i in itens
            ],
        }
        mapa = {script.stem: script for script in mestre._experiment_scripts()}
        faltando = [classe for classe in selecao if classe not in mapa]
        if faltando:
            print(f"Rerun recusado: classe(s) inexistente(s) {faltando}. Nada foi energizado.")
            return 1
        scripts = [mapa[classe] for classe in sorted(selecao)]
        with self._contexto_restaurado(contexto, rerun_de) as perfis_rodada:
            config = mestre._build_config()
            linhas = []
            for script in scripts:
                experimento_cls = mestre.Bancada._carregar_classe_experimento(script)
                total = escritas = 0
                exatas = True
                for perfil, indices in selecao[script.stem].items():
                    config_perfil = replace(config, perfil=perfil, indices_permitidos=indices)
                    # O plano restaurado tem de dar o MESMO capture_index (nível)
                    # de cada captura original; senão o rerun não a reproduz.
                    plano = dict(experimento_cls(mestre.Bancada(None, None, config_perfil)).plano_de_capturas(False))
                    for item in itens:
                        if str(item.get("classe")).zfill(2) != script.stem or item.get("perfil") not in (perfil, None) \
                                or item.get("indice_global") is None:
                            continue
                        indice = int(item["indice_global"])
                        original = item.get("capture_index")
                        if indice not in plano or (original is not None and int(original) != plano[indice]):
                            print(f"Rerun recusado: {item.get('id_captura')} ({perfil}) não reproduz o plano "
                                  f"original (índice {indice}, nível {original}; plano atual: "
                                  f"{plano.get(indice, 'ausente')}). Nada foi energizado.")
                            return 1
                    info = mestre.capturas_efetivas_da_classe(experimento_cls, config_perfil)
                    total += info["total"]
                    escritas += info["escritas_trace"]
                    exatas = exatas and info["escritas_trace_exatas"]
                linhas.append((script.stem, getattr(experimento_cls, "nome", script.stem), {
                    "total": total, "escritas_trace": escritas, "escritas_trace_exatas": exatas,
                    "niveis": 1, "padrao": 1, "por_nivel": 1,
                }))
            if not self._verificar_orcamento_trace(linhas):
                return 1
            print(f"Rerun de {pasta} (seed base {contexto['base_seed']}, set capturas "
                  f"{contexto.get('capturas_override')}, perfis {', '.join(perfis_rodada)}):")
            for classe_id, nome, info in linhas:
                indices = "; ".join(
                    f"{perfil}: {'classe inteira' if idx is None else ', '.join(f'{classe_id}-{i + 1:04d}' for i in idx)}"
                    for perfil, idx in selecao[classe_id].items()
                )
                print(f"  {classe_id}  {nome:30s} {info['total']} captura(s) ({indices})")
            ids_classes = [int(classe) for classe in sorted(selecao)]
            esperado = (
                f"EXECUTAR-CLASSE-{scripts[0].stem}" if len(scripts) == 1
                else f"EXECUTAR-CLASSES-{normalizar_lista_classes(ids_classes)}"
            )
            total_capturas = sum(info["total"] for _, _, info in linhas)
            if not self.confirmar(
                f"Vai energizar a saída e REEXECUTAR {total_capturas} captura(s) de {len(scripts)} classe(s) "
                f"da sessão {pasta.name} (mesma seed/perfil/nível), numa sessão nova. "
                f"{self._aviso_escritas_trace(linhas)} Confirme fisicamente probe, cabos, E-stop e EUT.",
                esperado,
            ):
                return 1
            return self._executar_scripts(scripts, perfis_rodada=perfis_rodada, selecao=selecao)

    # -- ganchos de fim de run (set recalibracao / set html) ----------------

    def _fim_da_sessao(self, sessao_dir: Optional[Path]) -> None:
        """Roda a recalibração e/ou o HTML da sessão que acabou. Offline, depois
        de a saída estar OFF e a conexão fechada. NENHUMA falha aqui derruba a
        CLI nem conta como falha de experimento: só avisa e segue (o resultado
        das classes já foi registrado)."""
        if sessao_dir is None:
            return
        if self.recalibracao_ao_fim:
            try:
                self._recalibrar_ao_fim(Path(sessao_dir))
            except (Exception, SystemExit) as exc:  # noqa: BLE001 - SystemExit: coletar() usa
                print(f"AVISO: recalibração automática FALHOU ({type(exc).__name__}: {exc}); nada foi "
                      f"gravado por ela. A sessão segue normalmente; rode scripts/recalibrar_extremos.py "
                      f"{sessao_dir} à mão se quiser.")
                logger.warning("Recalibração automática falhou", exc_info=True)
        if self.html_ao_fim:
            try:
                self._gerar_html_ao_fim(Path(sessao_dir))
            except (Exception, SystemExit) as exc:  # noqa: BLE001
                print(f"AVISO: relatório HTML FALHOU ({type(exc).__name__}: {exc}). A sessão segue "
                      f"normalmente; rode logica/relatorio_html.py {sessao_dir} à mão se quiser.")
                logger.warning("Relatório HTML falhou", exc_info=True)

    @staticmethod
    def _importar_recalibrador():
        scripts = str(Path(__file__).resolve().parent.parent / "scripts")
        if scripts not in sys.path:
            sys.path.append(scripts)
        import recalibrar_extremos
        return recalibrar_extremos

    def _recalibrar_ao_fim(self, sessao_dir: Path) -> None:
        if not mestre.BENCH_MODE:
            print("recalibração automática: modo SIMULADO, não recalibra (só capturas de bancada medem extremo).")
            return
        copia = sessao_dir / mestre.NOME_CALIBRACAO_NA_SESSAO
        if not copia.is_file():
            print(f"AVISO: recalibração automática NÃO rodou: falta a cópia da calibração anterior ({copia}); "
                  "sem ela a mudança não ficaria reversível dentro da sessão.")
            return
        recalibrar = self._importar_recalibrador()
        resultado = recalibrar.recalibrar([sessao_dir], gravar=True, automatico=True, saida=None)
        barra = "=" * 78
        if resultado.mudancas:
            print("\n" + barra)
            print(f"RECALIBRAÇÃO AUTOMÁTICA: {len(resultado.mudancas)} fator(es) de extremo MUDARAM em "
                  f"{resultado.arquivo}")
            for m in resultado.mudancas:
                antes = "novo" if m.antes is None else f"{m.antes:.3f}"
                print(f"  [{m.tabela}] classe {m.classe}: {antes} -> {m.depois:.3f}  ({m.capturas} captura(s))")
            print(f"Calibração anterior (início do run): {copia}")
            print("Os próximos run desta CLI já usam os fatores novos. Confira com 'git diff' e rode "
                  "tests/test_offline.py antes de commitar.")
            print(barra)
        else:
            print(f"Recalibração automática: nenhum fator mudou ({resultado.capturas_medidas} medida(s) de "
                  "extremo nesta sessão).")
        for chave in resultado.condicoes_sem_tabela:
            print(f"AVISO: condição {chave} sem tabela própria: NÃO criada automaticamente (uma tabela "
                  f"nova trocaria o fator conservador por um medido numa sessão só). Para calibrar: "
                  f"scripts/recalibrar_extremos.py {sessao_dir} --gravar")
        for tabela, classe, proposto, efetivo in resultado.classes_nao_gravadas:
            print(f"AVISO: [{tabela}] classe {classe}: medido {proposto:.3f} abaixo do fator efetivo "
                  f"{efetivo:.3f}; não gravado (nunca diminui).")

    def _gerar_html_ao_fim(self, sessao_dir: Path) -> None:
        import relatorio_html
        caminho, total, tamanho_mb = relatorio_html.gerar_relatorio_recortado(sessao_dir)
        print(f"Relatório HTML (versão recortada, {total} captura(s), {tamanho_mb:.1f} MB): {caminho}")
        if tamanho_mb > relatorio_html.TAMANHO_EMAIL_MB:
            print(f"AVISO: acima de {relatorio_html.TAMANHO_EMAIL_MB:.0f} MB — pode não passar como anexo de "
                  "e-mail. Reduza com logica/relatorio_html.py --classes, --max-capturas-por-classe ou --dpi 80.")

    @staticmethod
    def _ressalvas(resultado: "mestre.ResultadoClasse") -> str:
        partes = []
        if resultado.puladas:
            partes.append(f"{resultado.puladas} pulada(s) pela pré-validação de pico/rms")
        if resultado.descartadas:
            partes.append(f"{resultado.descartadas} descartada(s) por erro")
        if resultado.invalidas:
            partes.append(f"{resultado.invalidas} inválida(s) na validação física")
        return f"  ({'; '.join(partes)})" if partes else ""

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
        "rerun": cmd_rerun,
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
            except KeyboardInterrupt:
                # Ctrl+C durante um comando (mestre.garantir_ctrl_c_no_windows):
                # o ``with Bancada`` já desligou a saída ao sair; volta ao prompt.
                print(
                    "\nINTERROMPIDO pelo operador (Ctrl+C). A saída foi desligada ao encerrar "
                    "a conexão — confira OUTPUT OFF no painel da AMETEK."
                )
            except Exception as exc:  # nunca deixa a CLI cair por uma falha de comando
                print(f"ERRO: {exc}")
                traceback.print_exc()
        return 0


    # -- modo roteiro (scripts/visita_bancada.py) ---------------------------

    # Códigos de saída do roteiro, lidos pelo orquestrador da visita.
    ROTEIRO_OK = 0
    ROTEIRO_COM_FALHAS = 1       # bateria terminou, alguma classe/captura falhou
    ROTEIRO_INFRAESTRUTURA = 2   # exceção, bateria abortada ou preflight falhou: PARAR
    ROTEIRO_NAO_CONFIRMADO = 3   # operador não digitou a confirmação: nada energizado
    ROTEIRO_INVALIDO = 4         # comando desconhecido ou set recusado: nada energizado

    def executar_roteiro(self, comandos: List[str]) -> int:
        """Executa ``comandos`` na ordem, como se o operador os digitasse no
        prompt, e sai. As confirmações que energizam continuam sendo pedidas
        pelo ``confirmar()`` de sempre, no teclado do operador: o roteiro só
        fornece os comandos, nunca as respostas. Para no primeiro comando
        inválido, na primeira confirmação não digitada e na primeira falha de
        infraestrutura; uma bateria que terminou com classes falhas segue."""
        original = self.confirmar
        recusas: List[str] = []

        def confirmar(aviso: str, esperado: str) -> bool:
            if original(aviso, esperado):
                return True
            recusas.append(esperado)
            return False

        self.confirmar = confirmar
        codigo = self.ROTEIRO_OK
        try:
            for linha in comandos:
                partes = linha.split()
                if not partes:
                    continue
                comando, args = partes[0].lower(), partes[1:]
                handler = self.COMANDOS.get(comando)
                if handler is None:
                    print(f"Roteiro: comando desconhecido {comando!r}. Nada mais será executado.")
                    return self.ROTEIRO_INVALIDO
                print(f"\nbancada> {linha}")
                try:
                    retorno = handler(self, args)
                except KeyboardInterrupt:
                    print("\nINTERROMPIDO pelo operador (Ctrl+C). A saída foi desligada ao encerrar a "
                          "conexão — confira OUTPUT OFF no painel da AMETEK.")
                    return self.ROTEIRO_INFRAESTRUTURA
                except Exception as exc:  # noqa: BLE001 - qualquer falha encerra o roteiro
                    print(f"ERRO: {exc}")
                    traceback.print_exc()
                    return self.ROTEIRO_INFRAESTRUTURA
                if recusas:
                    return self.ROTEIRO_NAO_CONFIRMADO
                if self.falha_infraestrutura:
                    return self.ROTEIRO_INFRAESTRUTURA
                if retorno:
                    if comando in ("run", "rerun"):
                        codigo = self.ROTEIRO_COM_FALHAS
                    elif comando in ("comm", "trigger", "lowvoltage", "native"):
                        return self.ROTEIRO_INFRAESTRUTURA
                    else:
                        print(f"Roteiro: '{linha}' recusado. Nada mais será executado.")
                        return self.ROTEIRO_INVALIDO
            return codigo
        finally:
            self.confirmar = original


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="CLI da bancada (sem argumentos: prompt interativo).")
    parser.add_argument(
        "--comando", action="append", default=[],
        help="executa este comando da CLI e sai (repetível, na ordem). As confirmações que "
             "energizam continuam sendo digitadas pelo operador no teclado.",
    )
    args = parser.parse_args(argv)
    if args.comando and not sys.stdin.isatty():
        # Confirmação vinda de pipe/arquivo não é do operador: recusa antes de tudo.
        print("Modo roteiro recusado: a entrada não é um terminal. As confirmações que energizam "
              "precisam ser digitadas pelo operador. Nada foi executado.")
        return SessaoCLI.ROTEIRO_INVALIDO
    sessao = SessaoCLI()
    try:
        return sessao.executar_roteiro(args.comando) if args.comando else sessao.loop()
    finally:
        sessao._liberar_bloqueio_sessao()


if __name__ == "__main__":
    sys.exit(main())
