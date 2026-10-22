"""Visita à bancada num comando só: conduz ``docs/bancada_pendencias.md`` do
Bloco 1 ao fechamento, nas cinco condições da P-26.

Uso no PC da bancada (atalho ``scripts\\VISITA_BANCADA.cmd``)::

    scripts\\VISITA_BANCADA.cmd            # começa ou retoma a visita
    scripts\\VISITA_BANCADA.cmd --plano    # só lista as etapas e o estado
    scripts\\VISITA_BANCADA.cmd --pular 03-ciclos-antigos

O que o orquestrador faz e o que ele NÃO faz:

- Escolhe os comandos (os do roteiro), a condição de cada etapa (tensão e
  frequência), as pastas de saída, e confere cada sessão depois que ela
  termina. Cada etapa que energiza é um processo novo (conexão nova) da CLI
  (``logica/cli.py --comando ...``) ou de um ``scripts/diag_*.py``.
- **Nunca responde confirmação.** Os processos filhos herdam o teclado; quem
  digita a palavra de confirmação que cada etapa pede é o operador. Este
  arquivo não contém nenhuma dessas palavras (o teste confere).
- Não muda limites: as variáveis de condição são as mesmas que
  ``scripts/start_bench_windows.ps1`` calcula (range 300 V, pico 415,8 V).
- Falha de infraestrutura (CLI devolve 2, script de diagnóstico termina com
  erro, Ctrl+C): **para a visita**, pede OUTPUT OFF no painel e não repete.
  Rodar o comando de novo retoma da etapa que parou, com confirmação nova.
- Classe ou captura que falhou dentro de uma bateria não para a visita: fica
  no ``falhas.json`` da sessão e, logo depois daquele ``run`` (mesma condição
  e mesma calibração, como o rerun exige), o orquestrador pergunta se você
  quer rodar de novo só essas capturas (``run falhas``, confirmação nova).
- Achado de segurança (P-03: sobressinal ou pico da 08 acima do limite) para
  a visita. Extremo medido acima do ``extremo_previsto_v`` pausa e pede decisão.

Estado: ``logs/visita_<id>/estado.json`` (logs/ não é rastreado pelo git, então
não suja a árvore). Uma etapa concluída nunca roda de novo sozinha.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Callable, Dict, List, Optional, Sequence, Tuple

RAIZ = Path(__file__).resolve().parents[1]
LOGICA = RAIZ / "logica"
SCRIPTS = RAIZ / "scripts"
RESULTADOS = RAIZ / "resultados"
LOGS = RAIZ / "logs"
CALIBRACAO = Path("logica") / "calibracao_extremos.json"

# Mesmo cálculo de scripts/start_bench_windows.ps1 (tensão <= 270 V): range
# 300 Vrms, limite rms = range, pico = 98 % do teto do range. Não é um limite
# novo; o teste test_visita_bancada confere que continua 415,8 V.
RANGE_RMS = 300.0
TETO_PICO_V = round(RANGE_RMS * math.sqrt(2) * 0.98, 1)
TENSAO_MAX_FASE_NEUTRO = 270.0

# Códigos de saída do modo roteiro da CLI (SessaoCLI.ROTEIRO_*).
CLI_OK, CLI_COM_FALHAS, CLI_INFRA, CLI_NAO_CONFIRMADO, CLI_INVALIDO = 0, 1, 2, 3, 4

# Bloco 9 com ``set perfil todos`` (bancada_pendencias.md, passo 9.3).
PARTES_9_TODOS = ("06,10", "11,12", "13,14", "15,16", "07,08,09,20")
PARTE_1_TODOS = "01,02,03,04,05,17,18,19"  # passo 8.1 com set perfil todos
CLASSES_P09 = "10,11,12,16"  # Bloco 10-B
# Reexecução, a 127 V/60 Hz, do que reprovou em 2026-10-22 e foi corrigido depois:
# 02 (crista; fator recalibrado em 13b9bdb), 18/19 (THD; forma da 17 herdada,
# 72bbcd6: a 17 vai junto, antes delas) e 10/11/12/16 (P-08; recalibração
# 13b9bdb), estas em dois grupos de 216 gravações TRACe.
REEXECUCOES_2026_10_22 = (("R-02-17-18-19", "02,17,18,19"), ("R-p08-10-11", "10,11"), ("R-p08-12-16", "12,16"))
# = mestre.TIPOS_REEXECUTAVEIS (o teste confere): o que ``run falhas`` reexecuta.
TIPOS_REEXECUTAVEIS = ("descartada", "invalida", "classe_falhou", "nao_executada_orcamento")


class VisitaParada(Exception):
    """A visita para aqui; o estado fica salvo e o comando retoma depois."""


class NaoConfirmado(VisitaParada):
    """O operador não digitou a confirmação: nada foi energizado."""


# ------------------------------------------------------------------ utilidades

def agora() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def chave(tensao: float, freq: float) -> str:
    return f"{tensao:g}V_{freq:g}Hz"


def env_condicao(tensao: float, freq: float, base: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Ambiente de um processo filho numa condição (o que START_BENCH faria)."""
    if not 0 < tensao <= TENSAO_MAX_FASE_NEUTRO:
        raise ValueError(f"tensão {tensao} fora de (0, {TENSAO_MAX_FASE_NEUTRO}] V fase-neutro")
    env = dict(os.environ if base is None else base)
    env.update({
        "PYTHONUTF8": "1",
        "BENCH_MODE": "1",
        "ARM_OUTPUT": "NO",
        "BASE_VOLTAGE_RMS": f"{tensao:g}",
        "GRID_FREQUENCY_HZ": f"{freq:g}",
        "SOURCE_VOLTAGE_RANGE_RMS": f"{RANGE_RMS:g}",
        "EUT_MAX_VOLTAGE_RMS": f"{RANGE_RMS:g}",
        "EUT_MAX_PEAK_V": f"{TETO_PICO_V:g}",
    })
    return env


def conferir_ambiente_bancada(env: Dict[str, str]) -> List[str]:
    """Problemas que impedem começar (vazio = ok). Só confere; não corrige."""
    problemas = []
    if env.get("AMETEK_PORT") != "COM10" or env.get("AMETEK_BAUDRATE") != "115200":
        problemas.append("AMETEK_PORT/AMETEK_BAUDRATE diferentes de COM10/115200 "
                         "(rode pelo VISITA_BANCADA.cmd, que carrega scripts/bench_config.ps1)")
    if env.get("CAPTURE_CURRENT", "0") != "0":
        problemas.append("CAPTURE_CURRENT precisa ser 0 (captura de corrente desligada)")
    try:
        if float(env.get("VOLTAGE_PROBE_ATTENUATION", "")) <= 0:
            raise ValueError
    except ValueError:
        problemas.append("VOLTAGE_PROBE_ATTENUATION ausente ou inválido (fator escrito na probe)")
    return problemas


def pastas_de_sessao() -> set:
    if not RESULTADOS.is_dir():
        return set()
    return {p.resolve() for p in RESULTADOS.iterdir() if p.is_dir() and p.name.startswith("sessao_")}


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def arvore_suja() -> List[str]:
    """Rastreados alterados ou novos não ignorados (o que ``git_sujo`` conta)."""
    r = git("status", "--porcelain")
    if r.returncode != 0:
        return [f"git status falhou: {r.stderr.strip()}"]
    return [linha for linha in r.stdout.splitlines() if linha.strip()]


def empacotar_grupos(custos: Sequence[Tuple[str, int]], orcamento: int) -> Tuple[List[List[str]], List[str]]:
    """Classes em ordem numérica, agrupadas sem passar ``orcamento`` gravações
    TRACe por grupo (uma conexão por grupo). Classe que sozinha passa do
    orçamento fica de fora (a CLI a recusaria sem energizar)."""
    grupos: List[List[str]] = []
    excedentes: List[str] = []
    atual: List[str] = []
    soma = 0
    for classe, custo in custos:
        if custo > orcamento:
            excedentes.append(classe)
            continue
        if atual and soma + custo > orcamento:
            grupos.append(atual)
            atual, soma = [], 0
        atual.append(classe)
        soma += custo
    if atual:
        grupos.append(atual)
    return grupos, excedentes


def sem_excluidas(lista: str, excluidas: Sequence[str]) -> str:
    return ",".join(c for c in lista.split(",") if c not in set(excluidas))


def esperar_processo(proc) -> int:
    """Espera o filho terminar SEM matá-lo no Ctrl+C. O ``subprocess.call``
    mataria o filho (``kill``) quando o Ctrl+C chega aqui, no meio do
    desligamento: a CLI e os diagnósticos tratam o próprio Ctrl+C (o ``with
    Bancada`` desliga a saída ao sair), então o certo é esperar por isso.
    stdin/stdout são herdados: o operador vê tudo e digita as confirmações."""
    interrompido = False
    while True:
        try:
            codigo = proc.wait()
            break
        except KeyboardInterrupt:
            interrompido = True
            print("\nCtrl+C: esperando o processo da bancada desligar a saída e encerrar...")
    if interrompido:
        raise KeyboardInterrupt
    return codigo


# ------------------------------------------------------- conferência de segurança

def _carregar_fechamento():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import fechar_pendencias
    return fechar_pendencias


def conferir_seguranca(sessoes: Sequence[Path]) -> Tuple[List[str], List[str]]:
    """(achados que PARAM a visita, alertas que pedem decisão), lidos só do
    metadata, com os critérios já definidos em ``fechar_pendencias.py``:
    P-03 (sobressinal > 0,55 ou pico > 374,2 V na 08) e extremo medido acima de
    ``extremo_previsto_v`` ou de ``teto_extremos_v`` em qualquer classe."""
    fp = _carregar_fechamento()
    lidas = [fp.Sessao(Path(s)) for s in sessoes]
    ctx = fp.Contexto(lidas, None, None)
    parar: List[str] = []
    alertas: List[str] = []
    if ctx.da_classe("08"):
        criterios, _, _ = fp.p03(ctx)
        for c in criterios:
            if c.get("criterio") in ("sobressinal_pu", "pico_absoluto_v") and c.get("resultado") == fp.FALHA:
                parar.append(f"P-03 {c['criterio']}: {c.get('valor_medido')} (limite {c.get('limite')}). "
                             f"{c.get('nota') or ''}")
    for r in ctx.fisicos:
        pk, vl = fp._num(r.get("pico_medido_v")), fp._num(r.get("vale_medido_v"))
        if pk is None or vl is None:
            continue
        extremo = max(abs(pk), abs(vl))
        teto, previsto = fp._num(r.get("teto_extremos_v")), fp._num(r.get("extremo_previsto_v"))
        if teto is not None and extremo > teto:
            parar.append(f"{r['id_captura']}: extremo medido {extremo:.1f} V > teto de bancada {teto:.1f} V")
        elif previsto is not None and extremo > previsto:
            alertas.append(f"{r['id_captura']}: extremo medido {extremo:.1f} V > previsto {previsto:.1f} V "
                           f"(teto do equipamento {TETO_PICO_V:g} V)")
    return parar, alertas


def classe_reprovou(sessoes: Sequence[Path], classe: str) -> bool:
    """True se alguma captura física de ``classe`` tem validacao_fisica.ok falso
    ou se a classe não deixou nenhuma captura física."""
    fp = _carregar_fechamento()
    ctx = fp.Contexto([fp.Sessao(Path(s)) for s in sessoes], None, None)
    regs = ctx.da_classe(classe)
    return not regs or any((r.get("validacao_fisica") or {}).get("ok") is not True for r in regs)


def falhas_da_sessao(pasta: Path, so_reexecutaveis: bool = False) -> List[dict]:
    """Itens de ``<pasta>/falhas.json`` (formato de ``mestre.RegistroFalhas``)."""
    arq = Path(pasta) / "falhas.json"
    if not arq.is_file():
        return []
    try:
        dados = json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    itens = dados.get("itens", []) if isinstance(dados, dict) else []
    itens = [i for i in itens if isinstance(i, dict)]
    if so_reexecutaveis:
        itens = [i for i in itens if i.get("tipo") in TIPOS_REEXECUTAVEIS]
    return itens


# ------------------------------------------------------------------ a visita

def sessao_local(caminho: str) -> Path:
    """Sessão registrada no estado com o caminho absoluto do PC onde rodou.
    Retomada em outro PC (resultados/ copiado para outra pasta): se o caminho
    gravado não existe aqui, procura a sessão pelo nome em ``RESULTADOS``."""
    gravado = Path(caminho)
    if gravado.is_dir():
        return gravado
    local = RESULTADOS / PureWindowsPath(caminho).name
    return local if local.is_dir() else gravado


@dataclass
class Etapa:
    id: str
    bloco: str
    titulo: str
    energiza: bool
    executar: Callable[["Visita", "Etapa"], str]
    condicao: Optional[Tuple[float, float]] = None
    # Se devolver texto, a etapa é pulada com esse motivo (decidido na hora).
    pular_se: Optional[Callable[["Visita"], Optional[str]]] = None


@dataclass
class Visita:
    pasta: Path
    estado: dict = field(default_factory=dict)
    entrada: Callable[[str], str] = input
    executar_processo: Optional[Callable[..., int]] = None

    # ---- estado
    @property
    def arquivo_estado(self) -> Path:
        return self.pasta / "estado.json"

    def salvar(self) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        tmp = self.arquivo_estado.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.estado, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.arquivo_estado)

    def log(self, texto: str) -> None:
        print(texto)
        self.pasta.mkdir(parents=True, exist_ok=True)
        with open(self.pasta / "visita.log", "a", encoding="utf-8") as fh:
            fh.write(f"{agora()} {texto}\n")

    def reg(self, etapa_id: str) -> dict:
        return self.estado.setdefault("etapas", {}).setdefault(etapa_id, {})

    def sessoes_de(self, *etapas: str) -> List[Path]:
        return [sessao_local(p) for e in etapas
                for p in self.estado.get("etapas", {}).get(e, {}).get("sessoes", [])]

    def todas_as_sessoes(self) -> List[Path]:
        vistas, saida = set(), []
        for reg in self.estado.get("etapas", {}).values():
            for p in reg.get("sessoes", []):
                if p not in vistas:
                    vistas.add(p)
                    saida.append(sessao_local(p))
        return saida

    @property
    def excluidas_127_60(self) -> List[str]:
        return self.estado.setdefault("excluidas_127V_60Hz", [])

    # ---- processos
    def _rodar(self, argv: List[str], env: Dict[str, str]) -> int:
        if self.executar_processo is not None:
            return self.executar_processo(argv, env)
        return esperar_processo(subprocess.Popen(argv, cwd=RAIZ, env=env))

    def python(self, script: Path, args: Sequence[str], condicao: Tuple[float, float]) -> int:
        argv = [sys.executable, str(script), *args]
        self.log("$ " + " ".join(argv[1:]) + f"   [{chave(*condicao)}]")
        return self._rodar(argv, env_condicao(*condicao))

    def offline(self, script: Path, args: Sequence[str]) -> int:
        argv = [sys.executable, str(script), *args]
        self.log("$ " + " ".join(argv[1:]))
        env = dict(os.environ, PYTHONUTF8="1")
        return self._rodar(argv, env)

    def cli(self, etapa: Etapa, comandos: Sequence[str], oferecer_rerun: bool = True) -> Tuple[int, List[Path]]:
        """Uma conexão nova da CLI com estes comandos; devolve (código, sessões novas).
        Com falhas reexecutáveis, pergunta se roda ``run falhas`` já (outra conexão)."""
        antes = pastas_de_sessao()
        argv = [sys.executable, str(LOGICA / "cli.py")]
        for c in comandos:
            argv += ["--comando", c]
        self.log(f"CLI [{chave(*etapa.condicao)}]: " + " ; ".join(comandos))
        codigo = self._rodar(argv, env_condicao(*etapa.condicao))
        novas = sorted(pastas_de_sessao() - antes)
        reg = self.reg(etapa.id)
        reg.setdefault("sessoes", [])
        reg["sessoes"] += [str(p) for p in novas if str(p) not in reg["sessoes"]]
        self.salvar()
        if codigo == CLI_NAO_CONFIRMADO:
            raise NaoConfirmado("A confirmação não foi digitada; nada foi energizado nesta etapa. "
                               "Rode o comando de novo para retomar daqui.")
        if codigo == CLI_INVALIDO:
            raise VisitaParada("A CLI recusou um comando do roteiro (nada energizado). Entregue a saída acima.")
        if codigo not in (CLI_OK, CLI_COM_FALHAS):
            raise VisitaParada(f"Falha de infraestrutura (código {codigo}). Confira OUTPUT OFF no painel, "
                               "preserve os logs e não repita sem entender a causa.")
        self.conferir(novas)
        if codigo == CLI_COM_FALHAS and oferecer_rerun:
            ajustes = [c for c in comandos if c.split()[0] == "set"]
            for pasta in novas:
                n = len(falhas_da_sessao(pasta, so_reexecutaveis=True))
                if not n:
                    continue
                resp = self.entrada(f"{pasta.name}: {n} captura(s)/classe(s) falharam. Rodar de novo só "
                                    "essas agora (pede confirmação nova)? [s/N] ").strip().lower()
                if resp == "s":
                    try:
                        self.cli(etapa, ajustes + [f"run falhas {pasta}"], oferecer_rerun=False)
                    except NaoConfirmado:
                        self.log("Rerun não confirmado: segue sem ele (as falhas continuam no falhas.json).")
        return codigo, novas

    def diag(self, etapa: Etapa, script: str, args: Sequence[str]) -> int:
        codigo = self.python(SCRIPTS / script, args, etapa.condicao)
        if codigo != 0:
            raise VisitaParada(f"{script} terminou com código {codigo}. Confira OUTPUT OFF no painel. "
                               "Se você só não digitou a confirmação, rode o comando de novo para "
                               "retomar desta etapa; se foi erro, entregue os logs.")
        return codigo

    def conferir(self, sessoes: Sequence[Path]) -> None:
        if not sessoes:
            return
        parar, alertas = conferir_seguranca(sessoes)
        if parar:
            for a in parar:
                self.log(f"ACHADO DE SEGURANÇA: {a}")
            raise VisitaParada("Achado de segurança: visita parada. Confira OUTPUT OFF no painel e "
                               "entregue a sessão e os logs antes de qualquer nova energização.")
        if alertas:
            for a in alertas:
                self.log(f"ALERTA: {a}")
            self.log("Extremo acima do previsto (bancada_pendencias.md, passo 9.5): registrar; perto de "
                     f"{TETO_PICO_V:g} V é achado de segurança.")
            resp = self.entrada("Digite C para continuar a visita ou P para parar aqui: ").strip().upper()
            if resp != "C":
                raise VisitaParada("Parada pelo operador depois do alerta de extremo.")

    def pausar(self, texto: str) -> None:
        resp = self.entrada(f"{texto}\nEnter para continuar, P para parar aqui: ").strip().upper()
        if resp == "P":
            raise VisitaParada("Parada pelo operador.")


# ------------------------------------------------------------- etapas: blocos

def e_suite(v: Visita, et: Etapa) -> str:
    v.log(git("log", "--oneline", "-1").stdout.strip())
    if suite_offline(v) != 0:
        raise VisitaParada("tests.test_offline falhou: não coletar (Bloco 1). Entregue a saída.")
    return "ok"


CONFERENCIA_FISICA = ("Conferência física (Bloco 1.5): probe no CH1 com o fator que você informou, BNC "
                      "Trigger Out -> EXT Trigger, USB da AMETEK (sem DB9), MX GUI fechado, disjuntores, "
                      "E-stop à mão, EUT, OUTPUT OFF no painel.")


def suite_offline(v: Visita) -> int:
    v.log("$ python -m unittest tests.test_offline")
    return v._rodar([sys.executable, "-m", "unittest", "tests.test_offline"], dict(os.environ, PYTHONUTF8="1"))


def e_infra(v: Visita, et: Etapa) -> str:
    v.cli(et, ["status", "comm", "trigger", "native"])
    return "ok"


def e_ciclos_antigos(v: Visita, et: Etapa) -> str:
    feitas = 0
    for nome in ("sessao_2026-10-07_127V_50Hz", "sessao_2026-10-07_14-59-54_run02"):
        pasta = RESULTADOS / nome
        if pasta.is_dir():
            v.offline(SCRIPTS / "diag_ciclos_trace.py", [str(pasta), "--classes", "08,09"])
            feitas += 1
    return "ok" if feitas else "pulada: sessões de 07/10 não estão neste PC"


def e_marcadores(v: Visita, et: Etapa) -> str:
    v.diag(et, "diag_marcadores_trace.py", ["--probe", os.environ["VOLTAGE_PROBE_ATTENUATION"], "--vrms", "127"])
    return "ok"


def e_acdc(hz: float) -> Callable[[Visita, Etapa], str]:
    def executar(v: Visita, et: Etapa) -> str:
        v.diag(et, "diag_acdc_amplitude.py", ["--probe", os.environ["VOLTAGE_PROBE_ATTENUATION"], "--vrms", "127",
                                              "--hz", f"{hz:g}", "--testar-compensacao"])
        return "ok"
    return executar


def e_classe08(v: Visita, et: Etapa) -> str:
    # Passo 6.2: a 08 reprovada não se repete sozinha.
    codigo, novas = v.cli(et, ["status", "set diagnostico bruto on", "set diagnostico retrieve on", "run 08"],
                          oferecer_rerun=False)
    if codigo != CLI_OK or classe_reprovou(novas, "08"):
        if "08" not in v.excluidas_127_60:
            v.excluidas_127_60.append("08")
        v.log("08 reprovou (não repetir sozinho, passo 6.2): fora da Parte 6 da campanha a 127 V/60 Hz.")
        return "falhas"
    return "ok"


def e_classe09(v: Visita, et: Etapa) -> str:
    codigo, _ = v.cli(et, ["set diagnostico bruto on", "set diagnostico retrieve on", "set capturas 6", "run 09"])
    return "ok" if codigo == CLI_OK else "falhas"


def e_ciclos_novos(v: Visita, et: Etapa) -> str:
    for pasta in v.sessoes_de("06-classe08", "06-classe09"):
        v.offline(SCRIPTS / "diag_ciclos_trace.py", [str(pasta), "--classes", "08,09"])
    return "ok"


def e_rodada07(v: Visita, et: Etapa) -> str:
    comandos = ["set recalibracao on", "run 07,17"]
    if et.id.endswith("1"):
        comandos = ["status", "comm"] + comandos
    # Sem rerun: a recalibração do fim do run muda a calibração (o rerun recusaria).
    codigo, _ = v.cli(et, comandos, oferecer_rerun=False)
    if et.id.endswith("2") and codigo != CLI_OK:
        for c in ("07", "17"):
            if c not in v.excluidas_127_60:
                v.excluidas_127_60.append(c)
        v.log("2.ª rodada de 07/17 ainda reprovou: 07 e 17 ficam fora da campanha (tabela de decisão).")
        return "falhas"
    return "ok" if codigo == CLI_OK else "falhas"


def commit_calibracao(v: Visita, mensagem: str) -> str:
    sujos = arvore_suja()
    alterado = f" M {CALIBRACAO.as_posix()}"
    if not sujos:
        return "ok: calibração não mudou"
    if sujos != [alterado]:
        raise VisitaParada("Árvore com outras mudanças além da calibração: " + "; ".join(sujos))
    print(git("diff", "--", str(CALIBRACAO)).stdout)
    if suite_offline(v) != 0:
        raise VisitaParada("Suíte offline falhou com a calibração nova: nada commitado. Entregue o diff.")
    for args in (("add", str(CALIBRACAO)), ("commit", "-m", mensagem)):
        r = git(*args)
        if r.returncode != 0:
            raise VisitaParada(f"git {args[0]} falhou: {r.stderr.strip()}")
    v.log(f"Commit da calibração: {git('log', '--oneline', '-1').stdout.strip()}")
    return "ok"


def e_commit07(v: Visita, et: Etapa) -> str:
    rodada = " (1.ª rodada)" if et.id.endswith("1") else ""
    return commit_calibracao(v, f"chore: recalibra fatores de extremo 07 e 17 a 127 V/60 Hz{rodada}")


def e_parte1(v: Visita, et: Etapa) -> str:
    lista = sem_excluidas(PARTE_1_TODOS, v.excluidas_127_60)
    codigo, novas = v.cli(et, ["set perfil todos", "set diagnostico bruto on", f"run {lista}"])
    for pasta in novas:
        v.offline(SCRIPTS / "verificar_sessao_bancada.py",
                  [str(pasta), "--json", str(v.pasta / f"verificar_parte1_{pasta.name}.json")])
        v.offline(LOGICA / "analisar_sessao.py", [str(pasta)])
    return "ok" if codigo == CLI_OK else "falhas"


def e_p10(perfil: str) -> Callable[[Visita, Etapa], str]:
    def executar(v: Visita, et: Etapa) -> str:
        codigo, _ = v.cli(et, ["set diagnostico bruto on", f"set perfil {perfil}", "set capturas 1", "run 05"])
        return "ok" if codigo == CLI_OK else "falhas"
    return executar


def e_parte9(lista: str) -> Callable[[Visita, Etapa], str]:
    def executar(v: Visita, et: Etapa) -> str:
        efetiva = sem_excluidas(lista, v.excluidas_127_60)
        if not efetiva:
            return "pulada: todas as classes da parte foram excluídas"
        codigo, _ = v.cli(et, ["set perfil todos", "set diagnostico bruto on", f"run {efetiva}"])
        return "ok" if codigo == CLI_OK else "falhas"
    return executar


def e_diag_list_offset(v: Visita, et: Etapa) -> str:
    # --saida é a PASTA; o script grava diag_list_offset-<data>.json dentro dela.
    v.diag(et, "diag_list_offset.py", ["--saida", str(v.pasta)])
    gravados = sorted(v.pasta.glob("diag_list_offset-*.json"))
    try:
        suportado = json.loads(gravados[-1].read_text(encoding="utf-8"))["resultado"].get("suportado")
    except (IndexError, OSError, ValueError, KeyError, AttributeError):
        suportado = None
    if suportado is None:
        raise VisitaParada("diag_list_offset.py sem resultado legível em "
                           f"{v.pasta}: braço C indefinido. Entregue a saída.")
    v.estado["p09_c_suportado"] = suportado is True
    v.log(f"SOURce:LIST:VOLTage:OFFSet aceito pela fonte: {suportado} ({gravados[-1].name})")
    return "ok"


def e_p09(braco: str) -> Callable[[Visita, Etapa], str]:
    def executar(v: Visita, et: Etapa) -> str:
        codigo, _ = v.cli(et, [f"set p09 {braco}", f"run {CLASSES_P09}"])
        return "ok" if codigo == CLI_OK else "falhas"
    return executar


def e_p09_analise(v: Visita, et: Etapa) -> str:
    args = []
    for e in ("10B-braco-A", "10B-braco-B", "10B-braco-C"):
        for p in v.sessoes_de(e):
            args += ["--sessao", str(p)]
    if not args:
        return "pulada: sem sessões do experimento"
    v.offline(SCRIPTS / "analisar_modelo_programado.py",
              args + ["--classes", *CLASSES_P09.split(","), "--saida", str(v.pasta / "p09_abc.json")])
    return "ok"


def e_passo_sine(v: Visita, et: Etapa) -> str:
    print("O script pergunta fator da probe, tensão e frequência: responda "
          f"{os.environ['VOLTAGE_PROBE_ATTENUATION']}, 127 e 60.")
    codigo = v.python(SCRIPTS / "teste_passo_final_sin.py", ["--classe", "06", "--repeticoes", "1"], et.condicao)
    if codigo == 2:
        v.log("Passo final SINE: rodou, critério não atendido (registrado; padrão continua OFF).")
        return "falhas"
    if codigo != 0:
        raise VisitaParada(f"teste_passo_final_sin.py terminou com código {codigo}. Confira OUTPUT OFF no painel.")
    return "ok"


# ------------------------------------------------- etapas: campanhas por condição

def planejar_grupos(v: Visita, condicao: Tuple[float, float], perfil: str) -> dict:
    """Grupos de ``run`` da condição, calculados pela própria CLI (mesmo
    estimador de gravações TRACe que ela usa para recusar), num processo com o
    ambiente da condição."""
    argv = [sys.executable, str(Path(__file__).resolve()), "--_planejar", perfil]
    r = subprocess.run(argv, cwd=RAIZ, env=env_condicao(*condicao), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise VisitaParada(f"Planejamento de {chave(*condicao)} falhou: {r.stderr.strip()[-800:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def _modo_planejar(perfil: str) -> int:
    import contextlib
    import io
    sys.path.insert(0, str(LOGICA))
    import cli
    import mestre
    sessao = cli.SessaoCLI()
    with contextlib.redirect_stdout(io.StringIO()):
        if sessao.cmd_set(["perfil", perfil]) != 0:
            raise SystemExit(f"perfil {perfil} recusado")
        linhas = sessao._capturas_das_classes(mestre.scripts_da_bateria_fisica())
    custos = [(cid, int(info["escritas_trace"])) for cid, _, info in linhas]
    grupos, excedentes = empacotar_grupos(custos, mestre.LIMITE_ESCRITAS_TRACE_CONEXAO)
    print(json.dumps({"perfil": perfil, "grupos": [",".join(g) for g in grupos], "excedentes": excedentes,
                      "custos": dict(custos), "orcamento": mestre.LIMITE_ESCRITAS_TRACE_CONEXAO}))
    return 0


def e_campanha(perfil: str, bruto: bool) -> Callable[[Visita, Etapa], str]:
    def executar(v: Visita, et: Etapa) -> str:
        reg = v.reg(et.id)
        if "plano" not in reg:
            reg["plano"] = planejar_grupos(v, et.condicao, perfil)
            reg["grupos_feitos"] = 0
            v.salvar()
        plano = reg["plano"]
        if plano["excedentes"]:
            v.log(f"Fora do orçamento por conexão (não executadas): {', '.join(plano['excedentes'])}")
        v.log(f"{chave(*et.condicao)}, perfil {perfil}: {len(plano['grupos'])} conexões: "
              + " | ".join(plano["grupos"]))
        resultado = "ok"
        for i in range(reg["grupos_feitos"], len(plano["grupos"])):
            comandos = [f"set perfil {perfil}"] + (["set diagnostico bruto on"] if bruto else [])
            codigo, _ = v.cli(et, comandos + [f"run {plano['grupos'][i]}"])
            if codigo != CLI_OK:
                resultado = "falhas"
            reg["grupos_feitos"] = i + 1
            v.salvar()
        return resultado
    return executar


def e_calibrar(origem: str) -> Callable[[Visita, Etapa], str]:
    """Grava e commita a calibração da condição com as sessões da etapa ``origem``."""
    def executar(v: Visita, et: Etapa) -> str:
        sessoes = [p for p in v.sessoes_de(origem) if p.is_dir()]
        if not sessoes:
            raise VisitaParada(f"Sem sessões de {origem}: nada a calibrar.")
        args = [str(p) for p in sessoes]
        v.offline(SCRIPTS / "recalibrar_extremos.py", args)
        cond = chave(*et.condicao)
        resp = v.entrada(f"Acima, o que mudaria na calibração de {cond} (nunca diminui fator). "
                         f"Digite GRAVAR para gravar, ou P para parar: ").strip()
        if resp != "GRAVAR":
            raise VisitaParada("Calibração não gravada (decisão do operador). Retome quando decidir.")
        if v.offline(SCRIPTS / "recalibrar_extremos.py", args + ["--gravar"]) != 0:
            raise VisitaParada("recalibrar_extremos.py --gravar falhou. Entregue a saída.")
        return commit_calibracao(v, f"chore: calibra fatores de extremo em {cond} (P-21)")
    return executar


def e_entrega(v: Visita, et: Etapa) -> str:
    data = _dt.date.today().isoformat()
    evid = RAIZ / "docs" / "evidencias" / data
    if suite_offline(v) != 0:
        v.log("AVISO: tests.test_offline falhou na entrega (registrado).")
    if not (evid / "pc_bancada.json").exists() and shutil.which("powershell"):
        v._rodar(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                  str(SCRIPTS / "validar_pc_bancada.ps1")], dict(os.environ))
    pcs = sorted((RAIZ / "docs" / "evidencias").glob("*/pc_bancada.json"))
    sessoes = [p for p in v.todas_as_sessoes() if p.is_dir()]
    sess_args = [a for p in sessoes for a in ("--sessao", str(p))]
    if sessoes:
        v.offline(SCRIPTS / "benchmark_sessao_io.py",
                  sess_args + ["--saida", str(v.pasta / "benchmark_sessao_io_bancada.json")])
        v.offline(SCRIPTS / "analisar_modelo_programado.py",
                  sess_args + ["--saida", str(v.pasta / "modelo_programada_sessoes_bancada.json")])
        for reg in v.estado.get("etapas", {}).values():
            cond = reg.get("condicao")
            for p in reg.get("sessoes", []):
                for npz in sorted(Path(p).glob("bruto_osciloscopio/*/*-ch1-*.npz")):
                    (v.pasta / "reamostragem").mkdir(parents=True, exist_ok=True)
                    v.offline(SCRIPTS / "analisar_reamostragem.py",
                              ["--entrada", str(npz), "--f0-hz", f"{cond[1]:g}" if cond else "60",
                               "--harmonicos", "10", "--saida", str(v.pasta / "reamostragem" / f"{npz.stem}.json")])
    evid.mkdir(parents=True, exist_ok=True)
    saida = evid / "fechamento.json"
    if saida.exists():
        saida = evid / f"fechamento_{_dt.datetime.now():%H%M%S}.json"
    args = sess_args + ["--artefatos", "logs", "--artefatos", "resultados", "--saida", str(saida)]
    if pcs:
        args += ["--pc-bancada", str(pcs[-1])]
    v.offline(SCRIPTS / "fechar_pendencias.py", args)
    escrever_resumo(v, saida)
    r = git("add", str(evid.relative_to(RAIZ)))
    if r.returncode == 0 and git("diff", "--cached", "--quiet").returncode != 0:
        git("commit", "-m", f"docs: evidências da visita à bancada de {data}")
        v.log(f"Evidências commitadas: {git('log', '--oneline', '-1').stdout.strip()}")
    return "ok"


def escrever_resumo(v: Visita, fechamento: Path) -> None:
    linhas = [f"# Visita {v.estado.get('id')}", "", f"Fechamento: {fechamento}", "", "## Etapas", ""]
    for et in ETAPAS:
        reg = v.estado.get("etapas", {}).get(et.id, {})
        linhas.append(f"- {et.id} ({et.bloco}): {reg.get('status', 'não executada')}"
                      + (f" — {reg['motivo']}" if reg.get("motivo") else ""))
    linhas += ["", "## Sessões e falhas", ""]
    for p in v.todas_as_sessoes():
        linhas.append(f"- {p.name}: {len(falhas_da_sessao(p))} item(ns) em falhas.json "
                      f"({len(falhas_da_sessao(p, so_reexecutaveis=True))} reexecutáveis com 'run falhas')")
    linhas += ["", f"Excluídas da campanha a 127 V/60 Hz: {', '.join(v.excluidas_127_60) or 'nenhuma'}"]
    (v.pasta / "resumo.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def _so_se_c(v: Visita) -> Optional[str]:
    if v.estado.get("p09_c_suportado") is not True:
        return "fonte não confirmou SOURce:LIST:VOLTage:OFFSet (10B.1): braço C não roda"
    return None


C127_50, C127_60 = (127.0, 50.0), (127.0, 60.0)
ETAPAS: List[Etapa] = [
    Etapa("01-suite", "1", "Suíte offline", False, e_suite),
    Etapa("02-infra", "2", "comm, trigger e native (127 V/50 Hz)", True, e_infra, C127_50),
    Etapa("03-ciclos-antigos", "3", "Ciclos offline das sessões de 07/10", False, e_ciclos_antigos),
    Etapa("04-marcadores", "4", "Marcadores por ciclo (50 e 60 Hz)", True, e_marcadores, C127_50),
    Etapa("05-acdc-60", "5", "ACDC 127 V/60 Hz", True, e_acdc(60), C127_60),
    Etapa("05-acdc-50", "5", "ACDC 127 V/50 Hz", True, e_acdc(50), C127_50),
    Etapa("06-classe08", "6", "Recaptura da 08 (P-03, P-19)", True, e_classe08, C127_50),
    Etapa("06-classe09", "6", "09 com 6 capturas", True, e_classe09, C127_50),
    Etapa("06-ciclos", "6", "Ciclos offline das novas 08/09", False, e_ciclos_novos),
    Etapa("07-rodada1", "7", "07 e 17 com recalibração, 1.ª rodada", True, e_rodada07, C127_60),
    # A 1.ª rodada grava a calibração; a 2.ª energiza e recusa árvore suja.
    Etapa("07-commit1", "7", "Suíte e commit da calibração da 1.ª rodada", False, e_commit07),
    Etapa("07-rodada2", "7", "07 e 17, 2.ª rodada", True, e_rodada07, C127_60),
    Etapa("07-commit", "7", "Suíte e commit da calibração", False, e_commit07),
    Etapa("08-parte1", "8", "Parte 1 (perfil todos) e verificador", True, e_parte1, C127_60),
    Etapa("08A-norma", "8-A", "05 por nível, perfil norma", True, e_p10("norma"), C127_60),
    Etapa("08A-literatura", "8-A", "05 por nível, perfil literatura", True, e_p10("literatura"), C127_60),
    *[Etapa(f"09-parte{n}", "9", f"Parte {n}: run {lista}", True, e_parte9(lista), C127_60)
      for n, lista in enumerate(PARTES_9_TODOS, start=2)],
    Etapa("10B-diag", "10-B", "P-09: a fonte aceita offset por passo? (não energiza)", False,
          e_diag_list_offset, C127_60),
    Etapa("10B-braco-A", "10-B", "P-09 braço A", True, e_p09("A"), C127_60),
    Etapa("10B-braco-C", "10-B", "P-09 braço C", True, e_p09("C"), C127_60, pular_se=_so_se_c),
    Etapa("10B-braco-B", "10-B", "P-09 braço B", True, e_p09("B"), C127_60),
    Etapa("10B-analise", "10-B", "P-09 análise A/B/C", False, e_p09_analise),
    Etapa("10A-passo-sine", "10-A", "Passo final SINE (P-18)", True, e_passo_sine, C127_60),
    *[Etapa(eid, "R", f"Reexecução do que reprovou em 2026-10-22: run {lista}", True, e_parte9(lista), C127_60)
      for eid, lista in REEXECUCOES_2026_10_22],
    Etapa("C-127V_50Hz", "P-26", "Campanha 127 V/50 Hz (perfil todos)", True, e_campanha("todos", True), C127_50),
    # A 230 V o limite de bancada leva o previsto até o teto: antes dela, os
    # fatores de 50 Hz saem da campanha de 127 V (regra por frequência).
    Etapa("C-127V_50Hz-calibrar", "P-21", "50 Hz: gravar e commitar calibração (campanha de 127 V)", False,
          e_calibrar("C-127V_50Hz"), C127_50),
    Etapa("C-230V_50Hz", "P-26", "Campanha 230 V/50 Hz (perfil todos)", True, e_campanha("todos", True),
          (230.0, 50.0)),
    Etapa("C-220V_60Hz-rodada-calibracao", "P-21", "220 V/60 Hz: rodada de calibração (literatura)", True,
          e_campanha("literatura", False), (220.0, 60.0)),
    Etapa("C-220V_60Hz-calibrar", "P-21", "220 V/60 Hz: gravar e commitar calibração", False,
          e_calibrar("C-220V_60Hz-rodada-calibracao"), (220.0, 60.0)),
    Etapa("C-220V_60Hz", "P-26", "Campanha 220 V/60 Hz (perfil todos)", True, e_campanha("todos", True),
          (220.0, 60.0)),
    Etapa("C-33V_60Hz-rodada-calibracao", "P-21", "33 V/60 Hz: rodada de calibração (literatura)", True,
          e_campanha("literatura", False), (33.0, 60.0)),
    Etapa("C-33V_60Hz-calibrar", "P-21", "33 V/60 Hz: gravar e commitar calibração", False,
          e_calibrar("C-33V_60Hz-rodada-calibracao"), (33.0, 60.0)),
    Etapa("C-33V_60Hz", "P-26", "Campanha 33 V/60 Hz (perfil todos)", True, e_campanha("todos", True),
          (33.0, 60.0)),
    Etapa("11-entrega", "10", "Análises offline, fechamento e commit das evidências", False, e_entrega),
]


# ------------------------------------------------------------------ execução

def rodar_visita(v: Visita, etapas: Sequence[Etapa] = ETAPAS) -> int:
    for et in etapas:
        reg = v.reg(et.id)
        if reg.get("status") in ("ok", "falhas", "pulada"):
            continue
        motivo = et.pular_se(v) if et.pular_se else None
        if motivo:
            reg.update(status="pulada", motivo=motivo, fim=agora())
            v.salvar()
            v.log(f"[{et.id}] pulada: {motivo}")
            continue
        print("\n" + "=" * 78)
        v.log(f"[{et.id}] Bloco {et.bloco}: {et.titulo}"
              + (f" — {chave(*et.condicao)}" if et.condicao else "")
              + (" — ENERGIZA (você digita a confirmação)" if et.energiza else ""))
        print("=" * 78)
        if et.energiza:
            sujos = arvore_suja()
            if sujos:
                raise VisitaParada("Árvore do git suja antes de coletar (as sessões gravariam git_sujo): "
                                   + "; ".join(sujos[:10]))
        if et.condicao:
            reg["condicao"] = list(et.condicao)
        reg["inicio"] = agora()
        v.salvar()
        try:
            resultado = et.executar(v, et)
        except KeyboardInterrupt:
            reg.update(status="interrompida", fim=agora())
            v.salvar()
            raise VisitaParada("Interrompida com Ctrl+C. Confira OUTPUT OFF no painel.")
        except VisitaParada as exc:
            reg.update(status="parada", motivo=str(exc), fim=agora())
            v.salvar()
            raise
        status, _, motivo = resultado.partition(":")
        reg.update(status=status.strip(), motivo=motivo.strip() or None, fim=agora())
        v.salvar()
        v.log(f"[{et.id}] {resultado}")
    v.estado["concluida"] = agora()
    v.salvar()
    return 0


def visita_atual(nova: bool, salvar: bool = True) -> Visita:
    if not nova:
        for estado in sorted(LOGS.glob("visita_*/estado.json"), reverse=True):
            dados = json.loads(estado.read_text(encoding="utf-8"))
            if not dados.get("concluida"):
                return Visita(estado.parent, dados)
    vid = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    v = Visita(LOGS / f"visita_{vid}", {"id": vid, "inicio": agora(), "etapas": {}})
    if salvar:
        v.salvar()
    return v


def imprimir_plano(v: Visita) -> None:
    print(f"Visita {v.estado.get('id')} ({v.pasta})")
    for et in ETAPAS:
        reg = v.estado.get("etapas", {}).get(et.id, {})
        marca = {"ok": "✔", "falhas": "!", "pulada": "–", "parada": "✖", "interrompida": "✖"}.get(
            reg.get("status"), " ")
        print(f" [{marca}] {et.id:32s} {'⚡' if et.energiza else ' '} {et.titulo}"
              + (f" ({chave(*et.condicao)})" if et.condicao else ""))


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plano", action="store_true", help="só lista as etapas e o estado da visita")
    ap.add_argument("--nova", action="store_true", help="começa uma visita nova (a anterior fica como está)")
    ap.add_argument("--pular", action="append", default=[], metavar="ETAPA",
                    help="marca a etapa como pulada (repetível)")
    ap.add_argument("--_planejar", metavar="PERFIL", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args._planejar:
        return _modo_planejar(args._planejar)

    v = visita_atual(args.nova, salvar=not args.plano)
    if args.plano and not args.pular:
        imprimir_plano(v)
        return 0
    ids = {et.id for et in ETAPAS}
    for e in args.pular:
        if e not in ids:
            print(f"Etapa desconhecida: {e}. Use --plano para ver os nomes.")
            return 2
        v.reg(e).update(status="pulada", motivo="pulada pelo operador (--pular)", fim=agora())
    v.salvar()
    if args.plano:
        imprimir_plano(v)
        return 0
    problemas = conferir_ambiente_bancada(dict(os.environ))
    if problemas:
        print("Visita recusada antes de tocar a bancada:\n- " + "\n- ".join(problemas))
        return 2
    if not sys.stdin.isatty():
        print("Visita recusada: a entrada não é um terminal (as confirmações são digitadas pelo operador).")
        return 2
    imprimir_plano(v)
    print("\nCada etapa marcada com ⚡ liga a fonte e pede a SUA confirmação digitada. "
          "Você pode parar em qualquer pausa; rodar o comando de novo retoma de onde parou.")
    try:
        # A cada execução (inclusive ao retomar outro dia), antes de qualquer etapa.
        v.pausar(CONFERENCIA_FISICA)
        rodar_visita(v)
    except KeyboardInterrupt:
        v.log("\nVISITA PARADA: Ctrl+C. Confira OUTPUT OFF no painel.")
        return 1
    except VisitaParada as exc:
        v.log(f"\nVISITA PARADA: {exc}")
        print("Estado salvo. Para retomar: scripts\\VISITA_BANCADA.cmd")
        return 1
    v.log(f"\nVISITA CONCLUÍDA. Resumo: {v.pasta / 'resumo.md'}. Confira OUTPUT OFF no painel.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
