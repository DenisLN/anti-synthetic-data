#!/usr/bin/env python3
"""Agregador OFFLINE de evidência por pendência física (frente K, 2026-10-20).

Roda DEPOIS da bancada, sobre pastas ``resultados/sessao_*`` (e, para P-16, o
JSON de ``scripts/validar_pc_bancada.ps1``). Para cada P-NN física emite um
item com status, critérios avaliados (valor medido, limite, origem do limite),
arquivos de origem com SHA-256 e a procedência (``git_commit``/``git_sujo``)
lida da sessão. NÃO fecha pendência: o status máximo é ``evidencia_suficiente``
e a decisão de encerrar continua com o responsável (``docs/PENDENCIAS_TRACKER.md``).

    python scripts/fechar_pendencias.py --sessao resultados/sessao_A [--sessao resultados/sessao_B ...] \\
        [--artefatos logs] [--artefatos resultados/passo_final_sin_<data>] \\
        [--pc-bancada docs/evidencias/2026-10-21/pc_bancada.json] --saida docs/evidencias/2026-10-21/fechamento.json

Status por item: ``evidencia_suficiente`` | ``insuficiente`` | ``reprovado`` | ``sem_dados``.
Resultado por critério: ``ok`` | ``falha`` | ``insuficiente`` | ``aviso`` |
``criterio_nao_definido`` | ``sem_dados``. ``falha`` => reprovado;
``insuficiente``/``sem_dados`` => insuficiente; ``aviso`` e
``criterio_nao_definido`` nunca reprovam, mas marcam ``requer_revisao_humana``.
Onde o código/docs não definem tolerância, NENHUMA é inventada.

Segurança: nunca abre instrumento e não importa PyVISA/PyMeasure. Só lê
metadata/``.npz``/JSON. P-07 chama ``scripts/recalibrar_extremos.py`` em
subprocesso SEM ``--gravar`` (apenas imprime o diff proposto). Recusa
sobrescrever ``--saida`` existente. Sessões/artefatos simulados não contam
como evidência física.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "logica"))

ESQUEMA = 1
CLASSES = tuple(f"{n:02d}" for n in range(1, 21))
PERFIS = ("norma", "literatura", "fronteira")  # docs/perfis.md
# scripts/verificar_prontidao.py::CONDICOES (tensão V, frequência Hz)
CONDICOES = {"127V_60Hz": (127, 60), "127V_50Hz": (127, 50), "230V_50Hz": (230, 50),
             "220V_60Hz": (220, 60), "33V_60Hz": (33, 60)}
TETO_08_V = 374.2  # 0,9 x max_peak_v 415,8 (docs/classes/08-transient.md; execucao_pendencias P-03)
SOBRESSINAL_REVISAO_08 = 0.45  # acima disso o valor amostrado pode subestimar o real: revisão humana
SOBRESSINAL_MAX_08 = 0.55  # ROTEIRO_BANCADA.md:197/374 e docs/classes/08-transient.md: acima é achado de segurança
TOL_POSICAO_08 = 10  # amostras (docs/metadata.md, validacao_fisica.posicao_evento)
ORCAMENTO_TRACES = 216  # gravações TRACe por conexão (execucao_pendencias P-23)
FISICAS = ("P-01", "P-02", "P-03", "P-05", "P-06", "P-07", "P-08", "P-10", "P-16", "P-17",
           "P-18", "P-19", "P-21", "P-22", "P-23", "P-28", "P-31")
TITULOS = {
    "P-01": "Campanha v1.15 real por classe/perfil/condição",
    "P-02": "Marcadores + TRACe recuperada + recaptura 08/09 (evento 100 ms)",
    "P-03": "Classe 08 a 127 V/50 Hz, evento 90 ms: posição e teto de pico",
    "P-05": "Fase/início/largura/pré-trigger nas classes 01-04 com sorteio",
    "P-06": "Continuidade de fase 47->53 Hz (classe 18)",
    "P-07": "Recalibração das classes 07/17 com medidas reais",
    "P-08": "Pico/vale das classes 10/11/12/16 contra o teto previsto",
    "P-10": "RMS/THD da classe 05 (CSIN 10/15/20 %, norma 2 %, TRACe 30 %)",
    "P-16": "Suíte offline no PC Windows da bancada",
    "P-17": "Diagnóstico ACDC (diag_acdc_amplitude.py) real",
    "P-18": "Passo final SINE: eficácia medida (aceitação/restauração e padrão OFF a confirmar)",
    "P-19": "TRACe:DATA? real: 1024 finitos ou não suportado",
    "P-21": "Calibração por condição nova antes de coleta",
    "P-22": "Leitura/armazenamento de sessões físicas no PC/disco da bancada",
    "P-23": "Orçamento de 216 gravações TRACe por conexão; causa física da trava",
    "P-28": "Exportação bruta do osciloscópio + análise de reamostragem",
    "P-31": "Sessões novas para a métrica oficial modelo/programada",
}
# Itens cuja conclusão depende de decisão humana: nunca passam de
# evidencia_suficiente + requer_revisao_humana.
HUMANOS = {"P-07": "diff de calibração a revisar e validar em coleta seguinte",
           "P-21": "origem dos fatores e momento da calibração a conferir",
           "P-31": "escolha da métrica oficial é decisão do responsável"}

OK, FALHA, INSUF, AVISO, ND, SEMDADOS = ("ok", "falha", "insuficiente", "aviso",
                                         "criterio_nao_definido", "sem_dados")


# --------------------------------------------------------------------- util
def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def limpar(valor: Any) -> Any:
    """Converte tipos numpy e troca não finitos por None (JSON estrito)."""
    if isinstance(valor, dict):
        return {str(k): limpar(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [limpar(v) for v in valor]
    if isinstance(valor, np.generic):
        valor = valor.item()
    if isinstance(valor, float) and not math.isfinite(valor):
        return None
    if isinstance(valor, Path):
        return str(valor)
    return valor


def crit(nome: str, resultado: str, valor: Any = None, limite: Any = None, origem: Optional[str] = None,
         nota: Optional[str] = None) -> dict:
    c = {"criterio": nome, "resultado": resultado, "valor_medido": valor, "limite": limite,
         "origem_do_criterio": origem}
    if nota:
        c["nota"] = nota
    return c


def chave_condicao(tensao: float, freq: float) -> str:
    return f"{float(tensao):g}V_{float(freq):g}Hz"  # = mestre.chave_condicao


def _num(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _classe(registro: dict) -> str:
    return str(registro.get("id_captura", "")).split("-")[0].zfill(2)


# ------------------------------------------------------------------ sessões
class Sessao:
    """Uma pasta ``resultados/sessao_*`` lida só com ``json`` (sem sessao_io)."""

    def __init__(self, pasta: Path) -> None:
        self.pasta = Path(pasta)
        self.sessao_json: Optional[dict] = None
        self.arquivo_sessao: Optional[Path] = None
        self.registros: List[dict] = []
        self.arquivos_metadata: List[Path] = []
        self.erros: List[str] = []
        if not self.pasta.is_dir():
            self.erros.append(f"{self.pasta} não é uma pasta")
            return
        sj = self.pasta / "sessao.json"
        if sj.is_file():
            try:
                lido = json.loads(sj.read_text(encoding="utf-8"))
                if isinstance(lido, dict):
                    self.sessao_json, self.arquivo_sessao = lido, sj
            except (OSError, ValueError) as exc:
                self.erros.append(f"sessao.json ilegível: {exc}")
        for jsonl in sorted((self.pasta / "metadata").glob("*.jsonl")):
            self.arquivos_metadata.append(jsonl)
            try:
                for n, linha in enumerate(jsonl.read_text(encoding="utf-8").splitlines(), 1):
                    if linha.strip():
                        r = json.loads(linha)
                        if isinstance(r, dict) and r.get("id_captura"):
                            r["_arquivo_metadata"] = str(jsonl)
                            self.registros.append(r)
            except (OSError, ValueError) as exc:
                self.erros.append(f"{jsonl.name} ilegível: {exc}")

    @property
    def fisicos(self) -> List[dict]:
        """Capturas físicas independentes (sem simuladas nem aliases de perfil)."""
        saida = []
        for r in self.registros:
            if r.get("simulado") is not False:
                continue
            if r.get("captura_compartilhada") and r.get("perfil_de_origem") not in (None, r.get("perfil")):
                continue
            saida.append(r)
        return saida

    def procedencia(self) -> dict:
        sj = self.sessao_json or {}
        r0 = self.registros[0] if self.registros else {}
        return {
            "sessao": str(self.pasta),
            "modo": sj.get("modo"),
            "git_commit": sj.get("git_commit", r0.get("git_commit")),
            "git_sujo": sj.get("git_sujo", r0.get("git_sujo")),
            "versao_codigo": sj.get("versao_codigo", r0.get("versao_codigo")),
            "capturas_registradas": len(self.registros),
            "capturas_fisicas": len(self.fisicos),
            "capturas_simuladas": sum(1 for r in self.registros if r.get("simulado") is not False),
        }


class Contexto:
    def __init__(self, sessoes: Sequence[Sessao], pc: Optional[dict], pc_arquivo: Optional[Path],
                 artefatos: Sequence[Path] = ()) -> None:
        self.sessoes = list(sessoes)
        self.artefatos = [Path(a) for a in artefatos]
        self.pc = pc
        self.pc_arquivo = pc_arquivo
        self.fisicos = [r for s in sessoes for r in s.fisicos]
        self.fontes: set = set()  # arquivos lidos pelo item corrente
        self._artefatos: Dict[str, List[Path]] = {}

    def marcar(self, caminho: Optional[Any]) -> None:
        if caminho:
            self.fontes.add(Path(caminho))

    def da_classe(self, *classes: str, filtro: Optional[Callable[[dict], bool]] = None) -> List[dict]:
        sel = [r for r in self.fisicos if _classe(r) in classes and (filtro is None or filtro(r))]
        for r in sel:
            self.marcar(r["_arquivo_metadata"])
        return sel

    def procura(self, padrao: str) -> List[Path]:
        """Artefatos ``padrao`` (glob recursivo) nas pastas de sessão e nas ``--artefatos``
        (``logs\\`` dos diagnósticos e ``resultados\\passo_final_sin_*`` ficam fora da sessão)."""
        if padrao not in self._artefatos:
            achados: List[Path] = []
            for pasta in [s.pasta for s in self.sessoes] + self.artefatos:
                if pasta.is_dir():
                    achados += [p for p in pasta.rglob(padrao) if p.is_file()]
            self._artefatos[padrao] = sorted(set(achados))
        return self._artefatos[padrao]

    def json_de(self, caminho: Path) -> Optional[dict]:
        try:
            lido = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return lido if isinstance(lido, dict) else None

    def sessao_do(self, caminho: Path) -> Optional[Sessao]:
        for s in self.sessoes:
            try:
                caminho.resolve().relative_to(s.pasta.resolve())
                return s
            except ValueError:
                continue
        return None


def criterio_procedencia(ctx: Contexto, registros: Sequence[dict]) -> dict:
    """Sessão física de commit limpo (AGENTS.md, 'Como versionar')."""
    ruins = []
    for s in ctx.sessoes:
        if not any(r in registros for r in s.registros) and registros:
            continue
        p = s.procedencia()
        if p["git_sujo"] is not False or not isinstance(p["git_commit"], str) or not p["git_commit"].strip():
            ruins.append(f"{s.pasta.name}: git_sujo={p['git_sujo']!r}, git_commit={p['git_commit']!r}")
        if s.arquivo_sessao:
            ctx.marcar(s.arquivo_sessao)
    return crit("procedencia_commit_limpo", INSUF if ruins else OK, valor=ruins or None,
                limite="git_sujo=false e git_commit não vazio",
                origem="AGENTS.md 'Como versionar': toda sessão de coleta sai de commit limpo")


def procedencia_do_artefato(j: dict) -> List[str]:
    """Motivos pelos quais um JSON de diagnóstico não prova coleta física de commit limpo."""
    motivos = []
    if j.get("simulado") is not False:
        motivos.append(f"simulado={j.get('simulado')!r}")
    commit = j.get("git_commit")
    if not isinstance(commit, str) or not commit.strip():
        motivos.append(f"git_commit={commit!r}")
    if j.get("git_sujo") is not False:
        motivos.append(f"git_sujo={j.get('git_sujo')!r}")
    return motivos


def criterio_procedencia_artefatos(nomes_e_jsons: Sequence[tuple]) -> dict:
    ruins = []
    for nome, j in nomes_e_jsons:
        m = procedencia_do_artefato(j)
        if m:
            ruins.append(f"{nome}: " + ", ".join(m))
    return crit("procedencia_commit_limpo", INSUF if ruins else OK, valor=ruins or None,
                limite="simulado=false, git_sujo=false e git_commit não vazio gravados no próprio artefato",
                origem="AGENTS.md 'Como versionar'; artefato sem procedência não vale como evidência")


def decidir(criterios: Sequence[dict], tem_dados: bool, humano: Optional[str] = None) -> tuple:
    """(status, requer_revisao_humana)."""
    if not tem_dados:
        return "sem_dados", False
    res = [c["resultado"] for c in criterios]
    if FALHA in res:
        return "reprovado", False
    if INSUF in res or SEMDADOS in res or OK not in res:
        return "insuficiente", False
    revisao = bool(humano) or ND in res or AVISO in res
    return "evidencia_suficiente", revisao


# ---------------------------------------------------------------- avaliadores
def _ver_sessao_bancada():
    caminho = RAIZ / "scripts" / "verificar_sessao_bancada.py"
    spec = importlib.util.spec_from_file_location("verificar_sessao_bancada_fp", caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo  # @dataclass do módulo exige isto
    spec.loader.exec_module(modulo)
    return modulo


def p01(ctx: Contexto) -> tuple:
    fis = ctx.da_classe(*CLASSES)
    if not fis:
        return [], False, {}
    classes = sorted({_classe(r) for r in fis})
    perfis = sorted({str(r.get("perfil")) for r in fis if r.get("perfil")})
    conds = sorted({chave_condicao(r.get("tensao_base_rms", 0), r.get("f0_hz", 0)) for r in fis})
    invalidas = [r["id_captura"] for r in fis if not (isinstance(r.get("validacao_fisica"), dict)
                                                       and r["validacao_fisica"].get("ok") is True)]
    faltam_cl = [c for c in CLASSES if c not in classes]
    faltam_pf = [p for p in PERFIS if p not in perfis]
    faltam_cd = [c for c in CONDICOES if c not in conds]
    cs = [
        crit("classes_cobertas", OK if not faltam_cl else INSUF, len(classes), 20,
             "AGENTS.md: 'run all' = bateria das 20 classes", nota=f"faltam: {faltam_cl}" if faltam_cl else None),
        crit("perfis_cobertos", OK if not faltam_pf else INSUF, perfis, list(PERFIS),
             "docs/perfis.md; 'set perfil todos'", nota=f"faltam: {faltam_pf}" if faltam_pf else None),
        crit("condicoes_cobertas", OK if not faltam_cd else INSUF, conds, list(CONDICOES),
             "scripts/verificar_prontidao.py::CONDICOES", nota=f"faltam: {faltam_cd}" if faltam_cd else None),
        crit("validacao_fisica_ok_em_todas", OK if not invalidas else INSUF, len(invalidas), 0,
             "metadata validacao_fisica.ok (mestre.py)", nota=f"ids: {invalidas[:10]}" if invalidas else None),
        crit("quantidade_de_capturas_por_classe_perfil_condicao", ND, len(fis), None,
             "não definido no código/docs (scripts/planejar_campanhas.py só planeja)"),
        criterio_procedencia(ctx, fis),
    ]
    return cs, True, {"capturas_fisicas": len(fis)}


def p02(ctx: Contexto) -> tuple:
    arts = [a for a in ctx.procura("diag_marcadores_trace-*.json")]
    reais = []
    for a in arts:
        j = ctx.json_de(a)
        if j and j.get("simulado") is False:
            reais.append((a, j))
            ctx.marcar(a)
    r08 = ctx.da_classe("08", "09")
    if not reais and not r08:
        return [], False, {}
    cs: List[dict] = []
    if not reais:
        cs.append(crit("diag_marcadores_trace_real", SEMDADOS, None, None,
                       "scripts/diag_marcadores_trace.py (--saida .json, sem --simulado)"))
    else:
        n = ident = prog = esp = 0
        for _, j in reais:
            for c in j.get("capturas", []):
                s = c.get("resumo", {})
                n += 1
                ident += int(s.get("identificados", 0))
                prog += int(s.get("marcadores_programados", 0))
                esp += len(s.get("espurios", []))
        ok = n > 0 and ident == prog and esp == 0
        cs.append(crit("marcadores_identificados", OK if n else INSUF, {"capturas": n, "identificados": ident,
                       "programados": prog, "espurios": esp}, "identificados == programados e 0 espúrios",
                       "scripts/diag_marcadores_trace.py (resumo)",
                       nota=None if ok else "divergência é achado do diagnóstico, não reprovação do critério"
                       if n else "JSON sem capturas"))
        cs[-1]["resultado"] = OK if n else INSUF
        if n and not ok:
            cs[-1]["resultado"] = AVISO
    cs.append(crit("hipotese_da_copia_100ms", ND, None, None,
                   "execucao_pendencias P-02: 'distinguir hipóteses antes da correção' (sem limiar)"))
    for f in (50.0, 60.0):
        for classe in ("08", "09"):
            sel = [r for r in r08 if _classe(r) == classe and _num(r.get("f0_hz")) == f]
            cs.append(crit(f"captura_{classe}_{f:g}Hz_presente", OK if sel else INSUF, len(sel), ">=1",
                           "execucao_pendencias P-02: recaptura 08/09"))
    desv = [(r["id_captura"], (r.get("validacao_fisica") or {}).get("posicao_evento", {}).get("desvio_amostras"))
            for r in r08 if _classe(r) == "08"]
    desv = [(i, d) for i, d in desv if d is not None]
    if desv:
        pior = max(abs(d) for _, d in desv)
        cs.append(crit("posicao_08_desvio_amostras", OK if pior <= TOL_POSICAO_08 else FALHA, pior, TOL_POSICAO_08,
                       "metadata validacao_fisica.posicao_evento.tolerancia_amostras = 10"))
    cs.append(criterio_procedencia(ctx, r08))
    return cs, True, {}


def p03(ctx: Contexto) -> tuple:
    r08 = ctx.da_classe("08")
    if not r08:
        return [], False, {}
    alvo = [r for r in r08 if _num(r.get("tensao_base_rms")) == 127.0 and _num(r.get("f0_hz")) == 50.0]
    evento90 = [r for r in alvo if abs((_num((r.get("parametros") or {}).get("inicio_impulso_s")) or -1) - 0.09) < 1e-6]
    cs = [crit("capturas_127V_50Hz_evento_90ms", OK if evento90 else INSUF,
               {"127V/50Hz": len(alvo), "com_evento_90ms": len(evento90)}, ">=1",
               "execucao_pendencias P-03; parametros.inicio_impulso_s = 0,09 (docs/metadata.md)")]
    desvios, picos, pico_detalhe, sobressinais = [], [], [], []
    invalidas = [r["id_captura"] for r in evento90 if not (
        isinstance(r.get("validacao_fisica"), dict) and r["validacao_fisica"].get("ok") is True)]
    cs.append(crit("validacao_fisica_ok_nas_capturas_usadas", SEMDADOS if not evento90 else (FALHA if invalidas else OK),
                   {"capturas": len(evento90), "com_ok_falso_ou_ausente": invalidas}, "validacao_fisica.ok = true em todas",
                   "metadata validacao_fisica.ok (mestre.py); captura reprovada não prova P-03"))
    for r in evento90:
        vf = r.get("validacao_fisica") or {}
        sb = _num((vf.get("posicao_evento") or {}).get("sobressinal_medido"))
        if sb is None:  # formato legado/ainda não gravado pela coleta
            sb = _num(vf.get("sobressinal_medido"))
        if sb is None:
            sb = _num(r.get("sobressinal_medido"))
        if sb is not None:
            sobressinais.append(sb)
        d = ((r.get("validacao_fisica") or {}).get("posicao_evento") or {}).get("desvio_amostras")
        pk, vl = _num(r.get("pico_medido_v")), _num(r.get("vale_medido_v"))
        if d is not None:
            desvios.append(abs(float(d)))
        if pk is not None and vl is not None:
            picos.append(max(abs(pk), abs(vl)))
            pico_detalhe.append({"id": r["id_captura"], "pico_v": pk, "vale_v": vl})
    picos_v = [abs(v) for v in (_num(r.get("pico_medido_v")) for r in evento90) if v is not None]
    sb_max = max(sobressinais) if sobressinais else None
    pk_max = max(picos_v) if picos_v else None
    if sb_max is not None and (sb_max > SOBRESSINAL_MAX_08 or (pk_max is not None and pk_max > TETO_08_V + 1e-9)):
        res_sb, nota_sb = FALHA, None
    elif sb_max is None or pk_max is None:
        res_sb = ND
        nota_sb = ("metadata não traz validacao_fisica.posicao_evento.sobressinal_medido; conferir manualmente contra 0,55"
                   if sb_max is None else "metadata não traz pico_medido_v; conferir manualmente contra 374,2 V")
    elif sb_max > SOBRESSINAL_REVISAO_08:
        res_sb = AVISO
        nota_sb = (f"sobressinal {sb_max:.3f} > {SOBRESSINAL_REVISAO_08}: o valor amostrado (30 kSa/s, oscilação de ~10 kHz) "
                   "subestima o pico real e pode já estar acima de 0,55; revisão humana obrigatória")
    else:
        res_sb, nota_sb = OK, None
    cs.append(crit("sobressinal_pu", res_sb, sb_max, SOBRESSINAL_MAX_08,
                   "ROTEIRO_BANCADA.md:197/374 e docs/classes/08-transient.md: sobressinal > 0,55 ou pico_medido_v > 374,2 V "
                   "é achado de segurança",
                   nota="; ".join(x for x in (nota_sb, f"pico_medido_v máx |.| = {pk_max:.1f} V (teto {TETO_08_V})"
                                              if pk_max is not None else None) if x) or None))
    cs.append(crit("desvio_de_posicao_amostras", SEMDADOS if not desvios else (OK if max(desvios) <= TOL_POSICAO_08 else FALHA),
                   max(desvios) if desvios else None, TOL_POSICAO_08,
                   "docs/metadata.md validacao_fisica.posicao_evento (tolerância 10)"))
    cs.append(crit("pico_absoluto_v", SEMDADOS if not picos else (OK if max(picos) <= TETO_08_V + 1e-9 else FALHA),
                   max(picos) if picos else None, TETO_08_V,
                   "0,9 x max_peak_v (docs/classes/08-transient.md); excesso exige investigação, não relaxar teto",
                   nota="; ".join(f"{d['id']}: +{d['pico_v']:.1f}/{d['vale_v']:.1f} V" for d in pico_detalhe) or None))
    cs.append(criterio_procedencia(ctx, evento90 or r08))
    return cs, True, {}


def _conferir_sessao_citada(ctx: "Contexto", ref: Any, hashes: Dict[str, Any]) -> List[str]:
    """Toda sessão citada por um artefato tem de estar em ``--sessao`` (mesmo nome de pasta) e cada arquivo citado
    tem de existir nela com o mesmo sha256. Retorna os problemas (vazio = confere)."""
    nome = Path(str(ref)).name
    s_ = next((x for x in ctx.sessoes if x.pasta.name == nome), None)
    if s_ is None:
        return [f"sessão citada '{nome}' não foi passada em --sessao"]
    ruins = []
    if not hashes:
        ruins.append(f"sessão '{nome}' citada sem hash de arquivo")
    for arq, esperado in hashes.items():
        cand = s_.pasta / arq
        if not cand.is_file():
            ruins.append(f"{nome}/{arq} citado e ausente em --sessao")
        elif not isinstance(esperado, str) or sha256_arquivo(cand).lower() != esperado.lower():
            ruins.append(f"sha256 divergente em {nome}/{arq}")
    return ruins


def p05(ctx: Contexto) -> tuple:
    return _via_verificador(ctx, "P-05")


def p06(ctx: Contexto) -> tuple:
    return _via_verificador(ctx, "P-06")


def _via_verificador(ctx: Contexto, pid: str) -> tuple:
    ver = _ver_sessao_bancada()
    classes = ("01", "02", "03", "04") if pid == "P-05" else ("18",)
    if not ctx.da_classe(*classes):
        return [], False, {}
    capturas = []
    for s in ctx.sessoes:
        if not s.fisicos:
            continue
        try:
            for c in ver.carregar_sessao(s.pasta):
                if c.classe_id in classes and c.metadado.get("simulado") is False:
                    capturas.append(c)
                    if c.arquivo:
                        ctx.marcar(s.pasta / c.arquivo)
        except Exception as exc:  # noqa: BLE001
            s.erros.append(f"carregar_sessao: {exc}")
    cs: List[dict] = []
    if not capturas:
        cs.append(crit("capturas_com_dados_brutos", INSUF, 0, ">=1", "logica/sessao_io.py (.npz da classe)",
                       nota="metadata existe, mas o .npz da classe não foi lido"))
        return cs, True, {}
    if pid == "P-06":
        alvo = [c for c in capturas if abs(float((c.metadado.get("parametros") or {}).get("start_hz", 0)) - 47.0) < 0.01
                and abs(float((c.metadado.get("parametros") or {}).get("end_hz", 0)) - 53.0) < 0.01]
        cs.append(crit("capturas_18_47_para_53Hz", OK if alvo else INSUF, len(alvo), ">=1",
                       "PENDENCIAS_TRACKER P-06: continuidade de fase 47->53 Hz"))
        res = [r for r in ver.verificar_capturas(alvo) if r.verificacao == "fase_18"] if alvo else []
        medidas = [r for r in res if r.valor is not None]
        pior = max((abs(r.valor) for r in medidas), default=None)
        cs.append(crit("salto_de_fase_graus", SEMDADOS if not medidas else
                       (OK if all(r.ok for r in medidas) else FALHA), pior, ver.TOL_FASE_GRAUS,
                       "scripts/verificar_sessao_bancada.py::TOL_FASE_GRAUS",
                       nota="; ".join(f"{r.id_captura}: {r.valor:+.2f} graus ({r.nota})" for r in medidas) or None))
        cs.append(criterio_procedencia(ctx, [c.metadado for c in alvo]))
        return cs, True, {}
    res = ver.verificar_capturas(capturas)
    por = {c.classe_id for c in capturas}
    faltam = [c for c in classes if c not in por]
    com_sorteio = all(c.metadado.get("sorteio_posicao") for c in capturas)
    cs.append(crit("classes_01_a_04_presentes", OK if not faltam else INSUF, sorted(por), list(classes),
                   "PENDENCIAS_TRACKER P-05", nota=f"faltam: {faltam}" if faltam else None))
    cs.append(crit("sorteio_de_posicao_ligado", OK if com_sorteio else INSUF, com_sorteio, True,
                   "metadata sorteio_posicao (docs/metadata.md)"))
    larg = [r for r in res if r.verificacao == "largura_pulse" and r.valor is not None]
    cs.append(crit("largura_do_pulso_ms", SEMDADOS if not larg else (OK if all(r.ok for r in larg) else AVISO),
                   max((abs(r.valor) for r in larg), default=None), ver.TOL_LARGURA_MS,
                   "scripts/verificar_sessao_bancada.py::TOL_LARGURA_MS (limiar PROPOSTO, não critério físico validado)",
                   nota="excesso é aviso: execucao_pendencias P-05 mantém o limiar distinto de critério validado"))
    pt = [r for r in res if r.verificacao == "pre_trigger" and r.valor is not None]
    cs.append(crit("pre_trigger_desvio_amostras", SEMDADOS if not pt else (OK if all(r.ok for r in pt) else AVISO),
                   max((abs(r.valor) for r in pt), default=None), ver.TOL_PRETRIGGER_AMOSTRAS,
                   "scripts/verificar_sessao_bancada.py::TOL_PRETRIGGER_AMOSTRAS (mestre.py avisa acima de 2)",
                   nota="desvio > 2 amostras é AVISO, não reprovação"))
    cs.append(crit("fase_e_inicio_medidos", ND, None, None,
                   "nenhum verificador mede fase/início da senoide nas classes 01-04; fase_graus/inicio_disturbio_s "
                   "estão no metadata como valores PROGRAMADOS"))
    cs.append(criterio_procedencia(ctx, [c.metadado for c in capturas]))
    return cs, True, {}


def p07(ctx: Contexto) -> tuple:
    r = ctx.da_classe("07", "17", filtro=lambda x: "pico_medido_v" in x and "vale_medido_v" in x)
    if not r:
        return [], False, {}
    cs = []
    por = {_classe(x) for x in r}
    cs.append(crit("classes_07_e_17_com_vmax_vmin", OK if por >= {"07", "17"} else INSUF, sorted(por), ["07", "17"],
                   "scripts/recalibrar_extremos.py: precisa de pico_medido_v/vale_medido_v"))
    pastas = [str(s.pasta) for s in ctx.sessoes if s.fisicos]
    extra: Dict[str, Any] = {}
    try:
        p = subprocess.run([sys.executable, str(RAIZ / "scripts" / "recalibrar_extremos.py"), *pastas],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
                           env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
        saida = p.stdout
        extra = {"argv": ["recalibrar_extremos.py", *pastas],
                 "comando": "recalibrar_extremos.py <sessões> (dry-run: sem a opção de gravação)",
                 "codigo_saida": p.returncode, "saida_sha256": hashlib.sha256(saida.encode("utf-8")).hexdigest(),
                 "diff_proposto": saida[-6000:], "stderr": p.stderr[-1500:]}
        cs.append(crit("recalibrar_extremos_executou", OK if p.returncode == 0 else INSUF, p.returncode, 0,
                       "scripts/recalibrar_extremos.py (dry-run; nada é gravado)"))
    except (OSError, subprocess.SubprocessError) as exc:
        cs.append(crit("recalibrar_extremos_executou", INSUF, str(exc), 0, "scripts/recalibrar_extremos.py"))
    cs.append(crit("diff_de_calibracao_revisado", ND, None, None,
                   "execucao_pendencias P-07: 'revisar diff'; validação em coleta SEGUINTE, sem aprovação retroativa"))
    cs.append(criterio_procedencia(ctx, r))
    return cs, True, {"recalibracao": extra}


def p08(ctx: Contexto) -> tuple:
    r = ctx.da_classe("10", "11", "12", "16")
    if not r:
        return [], False, {}
    conds: Dict[str, List[dict]] = {}
    for x in r:
        conds.setdefault(chave_condicao(x.get("tensao_base_rms", 0), x.get("f0_hz", 0)), []).append(x)
    cs: List[dict] = []
    for cond, regs in sorted(conds.items()):
        faltam = [c for c in ("10", "11", "12", "16") if c not in {_classe(x) for x in regs}]
        cs.append(crit(f"{cond}: classes_10_11_12_16_presentes", OK if not faltam else INSUF,
                       sorted({_classe(x) for x in regs}), ["10", "11", "12", "16"], "PENDENCIAS_TRACKER P-08"))
        viol, sem, pior = [], [], None
        for x in regs:
            pk, vl, prev = _num(x.get("pico_medido_v")), _num(x.get("vale_medido_v")), _num(x.get("extremo_previsto_v"))
            if pk is None or vl is None or prev is None:
                sem.append(x["id_captura"])
                continue
            m = max(abs(pk), abs(vl))
            pior = max(pior or 0.0, m / prev)
            if m > prev:
                viol.append(f"{x['id_captura']}: {m:.1f} V > {prev:.1f} V")
        cs.append(crit(f"{cond}: extremo_medido_ate_extremo_previsto",
                       INSUF if sem and not viol else (FALHA if viol else OK), {"maior_razao": pior, "sem_medida": sem},
                       "razão <= 1", "metadata extremo_previsto_v; execucao_pendencias P-08 (violação exige investigação)",
                       nota="; ".join(viol[:8]) or None))
        teto_viol = [x["id_captura"] for x in regs if (_num(x.get("teto_extremos_v")) is not None
                     and _num(x.get("pico_medido_v")) is not None and _num(x.get("vale_medido_v")) is not None
                     and max(abs(float(x["pico_medido_v"])), abs(float(x["vale_medido_v"]))) > float(x["teto_extremos_v"]))]
        cs.append(crit(f"{cond}: extremo_medido_ate_teto_de_bancada", FALHA if teto_viol else OK, teto_viol or None,
                       "<= teto_extremos_v", "mestre.py::_conferir_extremos_fisicos"))
    cs.append(criterio_procedencia(ctx, r))
    return cs, True, {}


def _nivel_thd(r: dict) -> Optional[float]:
    t = _num((r.get("parametros") or {}).get("thd"))
    if t is None:
        return None
    return round(t / 100.0 if t > 1.0 else t, 6)


ROTA_ESPERADA_05 = {0.02: "CSIN", 0.10: "CSIN", 0.15: "CSIN", 0.20: "CSIN", 0.30: "TRACe"}


def _rota_05(r: dict) -> tuple:
    """(rota, inferida?). Campo ``rota_programacao`` do metadata; sem ele, inferida
    pelo nível (acima de 20 % = TRACe, teto do CSINe) e marcada como inferida."""
    rota = r.get("rota_programacao")
    if isinstance(rota, str) and rota:
        return rota, False
    nivel = _nivel_thd(r)
    if nivel is None:
        return None, True
    return ("TRACe" if nivel > 0.20 + 1e-9 else "CSIN"), True


def p10(ctx: Contexto) -> tuple:
    r = ctx.da_classe("05")
    if not r:
        return [], False, {}
    niveis = {_nivel_thd(x) for x in r} - {None}
    exigidos = set(ROTA_ESPERADA_05)
    faltam = sorted(exigidos - niveis)
    linhas, ruins = [], []
    por_ponto: dict = {}
    for x in r:
        v = x.get("validacao_fisica") or {}
        nivel = _nivel_thd(x)
        rota, inferida = _rota_05(x)
        linhas.append({"id": x["id_captura"], "perfil": x.get("perfil"), "thd_programado": nivel, "rota": rota,
                       "rota_inferida": inferida,
                       "thd_medida": v.get("thd_medida"), "thd_esperada": v.get("thd_esperada"),
                       "envelope_mediana_medida": v.get("envelope_mediana_medida"),
                       "envelope_mediana_esperada": v.get("envelope_mediana_esperada"), "ok": v.get("ok")})
        if v.get("ok") is not True:
            ruins.append(x["id_captura"])
        if nivel in ROTA_ESPERADA_05:
            por_ponto.setdefault(nivel, []).append((x["id_captura"], rota, inferida, v.get("ok") is True))
    sem_campo = [l["id"] for l in linhas if l["rota_inferida"]]
    rota_errada = [f"{i}: nível {n:g} rota {rt}" for n, itens in por_ponto.items() for i, rt, _inf, _ok in itens
                   if rt != ROTA_ESPERADA_05[n]]
    pontos_ruins = sorted(n for n in exigidos if n in por_ponto and not any(ok for *_x, ok in por_ponto[n]))
    pontos = {f"{n:g}": {"rota_esperada": ROTA_ESPERADA_05[n], "capturas": len(por_ponto.get(n, [])),
                         "com_validacao_ok": sum(1 for *_x, ok in por_ponto.get(n, []) if ok)} for n in sorted(exigidos)}
    cs = [crit("niveis_thd_cobertos", OK if not faltam else INSUF, sorted(niveis), sorted(exigidos),
               "execucao_pendencias P-10 (CSIN 10/15/20 %, norma 2 %, TRACe 30 %)",
               nota=f"faltam: {faltam}" if faltam else None),
          crit("validacao_fisica_ok", OK if not ruins else FALHA, ruins or None, "ok=true em todas",
               "mestre.py comparar_fisicamente (tol. envelope/THD de VALIDACAO_TOL_*)"),
          crit("validacao_fisica_ok_por_nivel", SEMDADOS if not por_ponto else (FALHA if pontos_ruins else OK),
               pontos, "cada nível exigido com ao menos uma captura validacao_fisica.ok=true",
               "P-10: RMS/THD por nível (envelope_mediana_* e thd_* em validacao_fisica)",
               nota=f"níveis sem captura válida: {pontos_ruins}" if pontos_ruins else None),
          crit("rota_csin_vs_trace", SEMDADOS if not por_ponto else (FALHA if rota_errada else (AVISO if sem_campo else OK)),
               rota_errada or ROTA_ESPERADA_05, "10/15/20 % e 2 % por CSIN; 30 % por TRACe",
               "metadata rotulo rota_programacao (05.py rota_programacao); sem ele a rota é inferida pelo nível",
               nota=(f"rota inferida pelo nível (campo rota_programacao ausente) em {len(sem_campo)} captura(s)"
                     if sem_campo else None)),
          criterio_procedencia(ctx, r)]
    return cs, True, {"medidas_por_captura": linhas}


def _versao_valida(v: Any) -> bool:
    """Versão registrada de verdade: não vazia e sem o marcador ``indisponivel`` do .ps1."""
    return isinstance(v, str) and bool(v.strip()) and not v.strip().lower().startswith("indisponivel")


def p16(ctx: Contexto) -> tuple:
    if ctx.pc is None:
        return [], False, {}
    pc = ctx.pc
    ctx.marcar(ctx.pc_arquivo)
    win = "windows" in str(pc.get("sistema", "")).lower() or "windows" in str(pc.get("plataforma", "")).lower()
    n, falhas, erros = pc.get("testes_executados"), pc.get("falhas"), pc.get("erros")
    commits = {s.procedencia()["git_commit"] for s in ctx.sessoes if s.procedencia()["git_commit"]}
    cs = [
        crit("sistema_windows", OK if win else INSUF, pc.get("plataforma"), "Windows",
             "execucao_pendencias P-16: Windows efetivo; suíte em outra máquina não fecha"),
        crit("codigo_de_saida_zero", OK if pc.get("codigo_saida") == 0 else FALHA, pc.get("codigo_saida"), 0, "unittest discover"),
        crit("sem_falhas_nem_erros", OK if falhas == 0 and erros == 0 else FALHA,
             {"falhas": falhas, "erros": erros}, 0, "unittest discover"),
        crit("testes_executados", OK if isinstance(n, int) and n > 0 else INSUF,
             {"testes": n, "skips": pc.get("skips")}, "> 0",
             "nº exato de testes depende do ambiente e da versão; não é fixado, só exige > 0"),
        crit("arvore_git_limpa", OK if pc.get("git_sujo") is False else INSUF, pc.get("git_sujo"), False,
             "AGENTS.md 'Como versionar'"),
        crit("git_commit_registrado", OK if isinstance(pc.get("git_commit"), str) and pc.get("git_commit") else INSUF,
             pc.get("git_commit"), "não vazio", "git rev-parse HEAD"),
        crit("versoes_registradas", OK if all(_versao_valida(pc.get(k)) for k in ("python", "numpy", "pymeasure", "pyvisa")) else INSUF,
             {k: pc.get(k) for k in ("python", "numpy", "pymeasure", "pyvisa")}, "todas presentes", "validar_pc_bancada.ps1"),
    ]
    if commits and pc.get("git_commit"):
        cs.append(crit("commit_igual_ao_das_sessoes", OK if commits == {pc["git_commit"]} else AVISO,
                       sorted(commits), pc.get("git_commit"), "coerência de procedência (informativo)"))
    log = Path(ctx.pc_arquivo).with_name(str(pc.get("log", ""))) if ctx.pc_arquivo and pc.get("log") else None
    if log and log.is_file():
        ctx.marcar(log)
        igual = pc.get("log_sha256") == sha256_arquivo(log)
        cs.append(crit("log_integro", OK if igual else FALHA, igual, True, "log_sha256 do JSON x arquivo"))
    else:
        cs.append(crit("log_integro", INSUF, None, True, "pc_bancada.log ao lado do JSON ausente"))
    return cs, True, {}


def p17(ctx: Contexto) -> tuple:
    arts = ctx.procura("diag_acdc_amplitude-*.json")
    reais = [(a, j) for a in arts for j in [ctx.json_de(a)] if j and j.get("simulado") is False]
    if not reais:
        return [], False, {}
    cs, resumo = [], []
    for a, j in reais:
        ctx.marcar(a)
        linhas = j.get("linhas", [])
        modos = [(l.get("modo"), l.get("offset_pu")) for l in linhas]
        tem_ac = any(m == "AC" for m, _ in modos)
        tem_acdc0 = any(m == "ACDC" and (o or 0) == 0 for m, o in modos)
        tem_off = any(m == "ACDC" and (o or 0) > 0 for m, o in modos)
        finito = all(_num(l.get("razao_ch1_ac_sobre_alvo")) is not None for l in linhas) and bool(linhas)
        cs.append(crit(f"{a.name}: condicoes_medidas", OK if (tem_ac and tem_acdc0 and tem_off and finito) else INSUF,
                       {"AC": tem_ac, "ACDC_offset0": tem_acdc0, "ACDC_com_offset": tem_off, "razoes_finitas": finito},
                       "AC, ACDC off 0 e ACDC com offset, razões finitas", "scripts/diag_acdc_amplitude.py (linhas)"))
        resumo += [{"rotulo": l.get("rotulo"), "razao_ch1_ac_sobre_alvo": l.get("razao_ch1_ac_sobre_alvo"),
                    "razao_ch1_total_sobre_fonte_ac": l.get("razao_ch1_total_sobre_fonte_ac")} for l in linhas]
    cs.append(crit("deficit_acdc_aceitavel", ND, None, None,
                   "execucao_pendencias P-17 só pede caracterizar (CA e RMS total); sem tolerância; V/g não é correção"))
    cs.append(criterio_procedencia_artefatos([(a.name, j) for a, j in reais]))
    return cs, True, {"razoes": resumo}


def p18(ctx: Contexto) -> tuple:
    arts = [a for a in ctx.procura("resultado.json") if a.parent.name.startswith("passo_final_sin_")]
    arts = [a for a in arts if (ctx.json_de(a) or {}).get("simulado") is not True]
    if not arts:
        return [], False, {}
    spec = importlib.util.spec_from_file_location("teste_passo_final_sin_fp", RAIZ / "scripts" / "teste_passo_final_sin.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # só constantes; main() não roda
    cs = []
    for a in arts:
        ctx.marcar(a)
        j = ctx.json_de(a) or {}
        for i, r in enumerate(j.get("resultados", []), 1):
            mc = r.get("margem_com") or []
            margem_ok = bool(mc) and all(abs(x - 1.0) <= mod.TOL_MARGEM_PU for x in mc)
            cs.append(crit(f"{a.parent.name}#{i}: margem_final_1pu", OK if margem_ok else FALHA,
                           max((abs(x - 1.0) for x in mc), default=None), mod.TOL_MARGEM_PU,
                           "scripts/teste_passo_final_sin.py::TOL_MARGEM_PU (escolha do script, ajustável)"))
            corr, dif = _num(r.get("janela_corr")), _num(r.get("janela_dif_max_pu"))
            jan_ok = corr is not None and dif is not None and corr >= mod.CORR_MIN_JANELA and dif <= mod.TOL_JANELA_PU
            cs.append(crit(f"{a.parent.name}#{i}: janela_rotulada_identica", OK if jan_ok else FALHA,
                           {"corr": corr, "dif_max_pu": dif}, {"corr_min": mod.CORR_MIN_JANELA, "dif_max_pu": mod.TOL_JANELA_PU},
                           "scripts/teste_passo_final_sin.py::CORR_MIN_JANELA/TOL_JANELA_PU"))
    if not cs:
        cs.append(crit("resultados_no_json", INSUF, 0, ">=1", "resultado.json de teste_passo_final_sin.py"))
    cs.append(criterio_procedencia_artefatos([(a.parent.name, ctx.json_de(a) or {}) for a in arts]))
    cs.append(crit("aceitacao_LIST_e_restauracao_na_fonte", ND, None, None,
                   "execucao_pendencias P-18: conferir no scpi_transcricao.log; sem critério automático"))
    cs.append(crit("padrao_OFF_confirmado_pelo_responsavel", ND, None, None, "decisão do responsável (frente D)"))
    return cs, True, {}


def p19(ctx: Contexto) -> tuple:
    r = ctx.da_classe("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16",
                      "17", "18", "19", "20", filtro=lambda x: isinstance(x.get("diagnostico_trace"), dict))
    if not r:
        return [], False, {}
    cs, finitas, erros, nao_sup = [], 0, [], []
    for x in r:
        d = x["diagnostico_trace"]
        arq = d.get("arquivo")
        s = next((s for s in ctx.sessoes if x in s.registros), None)
        if arq and s and (s.pasta / arq).is_file():
            ctx.marcar(s.pasta / arq)
            try:
                with np.load(s.pasta / arq, allow_pickle=False) as z:
                    lido = np.asarray(z["lido"], dtype=np.float64)
                if lido.ndim == 2 and lido.shape[1] == 1024 and lido.shape[0] >= 1 and np.all(np.isfinite(lido)) \
                        and lido.shape[0] == d.get("traces_programadas"):
                    finitas += 1
            except Exception as exc:  # noqa: BLE001
                erros.append(f"{x['id_captura']}: npz ilegível ({exc})")
        if d.get("erro"):
            txt = str(d["erro"]).lower()
            (nao_sup if any(k in txt for k in ("undefined header", "-113", "not supported", "não suportado", "nao suportado"))
             else erros).append(f"{x['id_captura']}: {d['erro']}")
    if finitas and not erros:
        res, nota = OK, None
    elif nao_sup and not finitas and not erros:
        res, nota = OK, "comando registrado como não suportado: confirmar a leitura do erro SCPI na revisão"
    else:
        res, nota = INSUF, "; ".join(erros[:5]) or "nenhum .npz de diagnóstico com 1024 valores finitos por TRACe"
    cs.append(crit("trace_data_1024_finitos_ou_nao_suportado", res,
                   {"capturas_com_1024_finitos": finitas, "nao_suportado_registrado": len(nao_sup), "erros": len(erros)},
                   "1024 valores finitos por TRACe, ou erro SCPI explícito de comando não suportado",
                   "ametek_orm.ler_trace (TRACE_POINTS=1024) / execucao_pendencias P-19", nota=nota))
    cs.append(criterio_procedencia(ctx, r))
    humano = bool(nao_sup)
    return cs, True, {"revisao_forcada": humano}


def p21(ctx: Contexto) -> tuple:
    if not ctx.fisicos:
        return [], False, {}
    cs = []
    for s in ctx.sessoes:
        fis = s.fisicos
        if not fis:
            continue
        sj = s.sessao_json or {}
        cal = sj.get("calibracao_extremos") or {}
        copia = s.pasta / (cal.get("copia_na_sessao") or "calibracao_extremos.json")
        conds = sorted({chave_condicao(x.get("tensao_base_rms", 0), x.get("f0_hz", 0)) for x in fis})
        if not copia.is_file():
            cs.append(crit(f"{s.pasta.name}: copia_da_calibracao", INSUF, None, "arquivo presente",
                           "mestre.py grava calibracao_extremos.json na sessão"))
            continue
        ctx.marcar(copia)
        ctx.marcar(s.arquivo_sessao)
        ok_hash = cal.get("sha256") == sha256_arquivo(copia)
        cs.append(crit(f"{s.pasta.name}: sha256_da_copia_confere_com_sessao_json",
                       INSUF if not cal.get("sha256") else (OK if ok_hash else FALHA),
                       ok_hash, True, "sessao.json calibracao_extremos.sha256"))
        tabela = (json.loads(copia.read_text(encoding="utf-8")).get("por_condicao") or {})
        for cond in conds:
            e = tabela.get(cond)
            faltam = [c for c in CLASSES if c not in ((e or {}).get("fatores") or {})]
            cs.append(crit(f"{s.pasta.name}: {cond}: calibracao_da_condicao", OK if e and not faltam else INSUF,
                           {"existe": bool(e), "classes_sem_fator": faltam, "origem": (e or {}).get("origem")},
                           "entrada por_condicao com fatores das 20 classes e origem registrada",
                           "logica/calibracao_extremos.json (por_condicao) / execucao_pendencias P-21"))
    cs.append(crit("calibracao_feita_antes_da_coleta", ND, None, None,
                   "ordem temporal não é verificável offline; conferir origem dos fatores e datas (sem elevar limites)"))
    cs.append(criterio_procedencia(ctx, ctx.fisicos))
    return cs, True, {}


def _mesmo_host(a: Any, b: Any) -> bool:
    """Hostnames iguais sem diferenciar caixa, tolerando truncamento NetBIOS (15 caracteres)."""
    if not isinstance(a, str) or not isinstance(b, str) or not a.strip() or not b.strip():
        return False
    a, b = a.strip().lower(), b.strip().lower()
    return a == b or a[:15] == b[:15] and (len(a) > 15 or len(b) > 15)


def p22(ctx: Contexto) -> tuple:
    if not ctx.fisicos:
        return [], False, {}
    import sessao_io  # só leitura de .npz/metadata; não conecta instrumento
    medidas = []
    cs = []
    for s in ctx.sessoes:
        if not s.fisicos:
            continue
        npz = [p for p in s.pasta.rglob("*.npz")]
        t0 = time.perf_counter()
        try:
            caps = sessao_io.ler_capturas(s.pasta)
            erro = None
        except Exception as exc:  # noqa: BLE001
            caps, erro = [], str(exc)
        dt = time.perf_counter() - t0
        for p in npz:
            ctx.marcar(p)
        medidas.append({"sessao": str(s.pasta), "capturas_lidas": len(caps), "tempo_leitura_s": round(dt, 4),
                        "arquivos_npz": len(npz), "bytes_npz": sum(p.stat().st_size for p in npz), "erro": erro})
        cs.append(crit(f"{s.pasta.name}: leitura_sem_erro", OK if (erro is None and caps) else INSUF,
                       {"capturas": len(caps), "tempo_s": round(dt, 4)}, "leitura completa sem exceção",
                       "logica/sessao_io.py::ler_capturas", nota=erro))
    host = platform.node()  # só informativo: é o computador de ANÁLISE, não o que mediu
    origem22 = "execucao_pendencias P-22: PC/disco da bancada; hostname gravado no próprio artefato de medição"
    medicoes = []
    for padrao in ("benchmark_bancada*.json", "benchmark_sessao_io*.json"):
        for a in ctx.procura(padrao):
            j = ctx.json_de(a)
            if j is not None and j.get("simulado") is not True and (a, j) not in medicoes:
                medicoes.append((a, j))  # benchmark simulado/sintético nunca vale como medição da bancada
    if ctx.pc is None:
        cs.append(crit("executado_no_pc_da_bancada", SEMDADOS, None, "hostname do artefato = hostname de --pc-bancada", origem22))
    else:
        ctx.marcar(ctx.pc_arquivo)
        hosts = {a.name: j.get("hostname") for a, j in medicoes if isinstance(j.get("hostname"), str) and j["hostname"].strip()}
        if not hosts:
            cs.append(crit("executado_no_pc_da_bancada", ND, {"artefatos_de_medicao": [a.name for a, _ in medicoes],
                                                              "pc_bancada": ctx.pc.get("hostname")},
                           "hostname no artefato de medição", origem22,
                           nota="nenhum artefato de medição (--artefatos) traz hostname; conferir manualmente"))
        else:
            for a, j in medicoes:
                if a.name in hosts:
                    ctx.marcar(a)
            mesmo = all(_mesmo_host(h, ctx.pc.get("hostname")) for h in hosts.values())
            cs.append(crit("executado_no_pc_da_bancada", OK if mesmo else INSUF,
                           {"hostname_do_artefato": hosts, "pc_bancada": ctx.pc.get("hostname")},
                           "iguais (sem diferenciar maiúsculas; truncamento NetBIOS de 15 caracteres tolerado)", origem22))
    fisicos22 = [(a, j) for a, j in medicoes if j.get("tipo") == "benchmark_sessoes_fisicas" and j.get("simulado") is False]
    if not fisicos22:
        cs.append(crit("benchmark_de_sessoes_fisicas", SEMDADOS, None,
                       "JSON de scripts/benchmark_sessao_io.py --sessao (simulado=false) em --artefatos", origem22))
    else:
        ruins22, resumo22 = [], []
        for a, j in fisicos22:
            ctx.marcar(a)
            if not j.get("sessoes"):
                ruins22.append(f"{a.name}: nenhuma sessão citada")
            for sb in j.get("sessoes") or []:
                ruins22.extend(f"{a.name}: {m}" for m in _conferir_sessao_citada(ctx, sb.get("sessao"), {
                    **{k: v for k, v in (sb.get("sha256_npz") or {}).items()},
                    **{f"metadata/{k}": v for k, v in (sb.get("sha256_metadata") or {}).items()},
                    **({"sessao.json": sb["sha256_sessao_json"]} if sb.get("sha256_sessao_json") else {})}))
                integ = sb.get("integridade") or {}
                if not (integ.get("hash_arrays_antes_depois_iguais") is True and sb.get("originais_inalterados") is True):
                    ruins22.append(f"{a.name}:{Path(str(sb.get('sessao'))).name}")
                resumo22.append({"artefato": a.name, "sessao": sb.get("sessao"), "leitura_s": sb.get("leitura_s"),
                                 "bytes_npz": sb.get("bytes_npz"), "aliases": sb.get("aliases_identificados"),
                                 "consolidacao": (sb.get("consolidacao_em_copia") or {}).get("consolidar_s")})
            if j.get("git_sujo") is not False or not j.get("git_commit"):
                ruins22.append(f"{a.name}: git_sujo={j.get('git_sujo')!r}, git_commit={j.get('git_commit')!r}")
        cs.append(crit("benchmark_de_sessoes_fisicas", INSUF if ruins22 or not resumo22 else OK,
                       {"sessoes": resumo22, "problemas": ruins22 or None},
                       "hash antes/depois iguais, originais inalterados, procedência limpa", origem22))
    cs.append(crit("tempo_e_tamanho_aceitaveis", ND, None, None,
                   "nenhum limite de tempo/tamanho definido no código/docs; valores medidos em 'medidas'"))
    cs.append(criterio_procedencia(ctx, ctx.fisicos))
    return cs, True, {"medidas": medidas, "ambiente": {"hostname_do_computador_de_analise": host, "plataforma": platform.platform(),
                                                         "python": sys.version.split()[0]}}


# Mesma semântica de logica/ametek_orm.py::_raw_write (contagem de escritas TRACe:DATA).
_RE_ESCRITA_TRACE = re.compile(r"(?:^|;)\s*:?(?:(?:TRACE|TRAC):DATA|DATA)(?=\s)", re.I)
_RE_ESCRITA_NO_LOG = re.compile(r"\bt=[0-9.]+ W (.*)$")


def _gravacoes_trace_na_linha(linha: str) -> int:
    m = _RE_ESCRITA_NO_LOG.search(linha)
    return len(_RE_ESCRITA_TRACE.findall(m.group(1).strip() if m else linha.strip()))


def p23(ctx: Contexto) -> tuple:
    logs = []
    for lg in ctx.procura("scpi_transcricao.log"):
        s = ctx.sessao_do(lg)
        if s is not None and (s.sessao_json or {}).get("modo") != "bancada":
            continue  # sessão simulada (ou sem modo registrado) não prova orçamento de TRACe real
        logs.append(lg)
    diag_todos = list(ctx.procura("diag_nativo-*.json"))
    diag, diag_rejeitados = [], []
    for a in diag_todos:
        j = ctx.json_de(a)
        motivos = ["JSON ilegível ou não é objeto"] if j is None else []
        if j is not None:
            if not any(re.fullmatch(r"T\d+", str(k)) for k in j):
                motivos.append("sem resultados de teste (chaves T<n>)")
            proc = j.get("_procedencia")
            motivos += procedencia_do_artefato(proc if isinstance(proc, dict) else {})
        (diag_rejeitados.append(f"{a.name}: " + "; ".join(motivos)) if motivos else diag.append(a))
    if not logs and not diag_todos:
        return [], False, {}
    cs, totais = [], {}
    for lg in logs:
        ctx.marcar(lg)
        n = sum(_gravacoes_trace_na_linha(linha)
                for linha in lg.read_text(encoding="utf-8", errors="replace").splitlines())
        totais[str(lg)] = n
        cs.append(crit(f"{lg.parent.name}: gravacoes_TRACe_no_log", OK if n <= ORCAMENTO_TRACES else INSUF, n, ORCAMENTO_TRACES,
                       "orçamento por CONEXÃO (execucao_pendencias P-23); o log da sessão soma conexões",
                       nota=None if n <= ORCAMENTO_TRACES else "acima de 216 no total: separar por conexão manualmente; "
                       "formato do log não verificado contra bancada real"))
    if not logs:
        cs.append(crit("scpi_transcricao_log_presente", INSUF, 0, ">=1", "sessao.log/scpi_transcricao.log"))
    for a in diag:
        ctx.marcar(a)
    cs.append(crit("diag_nativo_output_off_presente", OK if diag else INSUF, len(diag), ">=1",
                   "scripts/diag_nativo_output_off.py (diag_nativo-*.json com resultados T<n> e _procedencia física, commit limpo)",
                   nota="; ".join(diag_rejeitados) or None))
    cs.append(crit("causa_fisica_da_trava", ND, None, None,
                   "execucao_pendencias P-23: causa só com diagnóstico real e interpretação humana"))
    if ctx.fisicos:
        cs.append(criterio_procedencia(ctx, ctx.fisicos))
    return cs, True, {"gravacoes_por_log": totais}


def p28(ctx: Contexto) -> tuple:
    r = ctx.da_classe(*CLASSES, filtro=lambda x: isinstance(x.get("bruto_osciloscopio"), dict))
    if not r:
        return [], False, {}
    total = faltando = com_erro = 0
    hashes_bruto: set = set()
    for x in r:
        s = next((s for s in ctx.sessoes if x in s.registros), None)
        for info in x["bruto_osciloscopio"].get("arquivos", []):
            total += 1
            if info.get("erro"):
                com_erro += 1
                continue
            arq = info.get("arquivo")
            if not (arq and s and (s.pasta / arq).is_file()):
                faltando += 1
            else:
                ctx.marcar(s.pasta / arq)
                hashes_bruto.add(sha256_arquivo(s.pasta / arq))
                if isinstance(info.get("arquivo_sha256"), str):
                    hashes_bruto.add(info["arquivo_sha256"].lower())
    cs = [crit("exportacoes_brutas_integras", OK if total and not faltando and not com_erro else INSUF,
               {"arquivos_registrados": total, "ausentes": faltando, "com_erro": com_erro}, "todas presentes, sem erro",
               "metadata bruto_osciloscopio (mestre._preservar_bruto_lido)")]
    analises = []
    for a in ctx.procura("*.json"):
        if "metadata" in a.parts or a.stat().st_size > 5_000_000:
            continue
        j = ctx.json_de(a)
        if j and isinstance(j.get("fonte"), dict) and j["fonte"].get("tipo") == "arquivo_bruto_fornecido":
            analises.append((a, j))
    casadas = [(a, j) for a, j in analises
               if str(j["fonte"].get("arquivo_sha256", "")).lower() in hashes_bruto]
    for a, j in casadas:
        ctx.marcar(a)
    cs.append(crit("analise_de_reamostragem_sobre_bruto_real", OK if casadas else INSUF,
                   {"casadas": [a.name for a, _ in casadas],
                    "sem_casamento": [a.name for a, _ in analises if (a, _) not in casadas]},
                   ">=1 JSON de scripts/analisar_reamostragem.py --entrada cujo fonte.arquivo_sha256 é o de um bruto_osciloscopio da sessão",
                   "scripts/analisar_reamostragem.py; metadata bruto_osciloscopio",
                   nota=None if casadas else "análise sem casamento de SHA-256 com os brutos registrados não conta"))
    cs.append(crit("fir_substitui_interpolador", ND, None, None,
                   "analisar_reamostragem: 'Nenhuma métrica desta ferramenta define critério de aceite físico'"))
    cs.append(criterio_procedencia(ctx, r))
    return cs, True, {}


def p31(ctx: Contexto) -> tuple:
    classes = ("06", "10", "11", "12", "15", "16")  # scripts/analisar_modelo_programado.py::CLASSES
    r = ctx.da_classe(*classes, filtro=lambda x: x.get("tres_versoes") is not None)
    if not r:
        return [], False, {}
    por = {_classe(x) for x in r}
    faltam = [c for c in classes if c not in por]
    cs = [crit("capturas_fisicas_com_tres_versoes", OK if not faltam else INSUF, sorted(por), list(classes),
               "scripts/analisar_modelo_programado.py::CLASSES; metadata tres_versoes",
               nota=f"faltam: {faltam}" if faltam else None),
          crit("metrica_oficial", ND, None, None, "execucao_pendencias P-31: falta justificar a métrica (nominal x fundamental ajustada)"),
          criterio_procedencia(ctx, r)]
    arts = []
    for a in ctx.procura("modelo_programada_sessoes*.json"):
        j = ctx.json_de(a)
        if j is not None and j.get("tipo") == "correlacao_modelo_programada_medida_sessoes_fisicas":
            arts.append((a, j))
    origem31 = "scripts/analisar_modelo_programado.py --sessao (nominal e fundamental ajustada)"
    ok31 = [(a, j) for a, j in arts if j.get("simulado") is False]
    if not ok31:
        cs.append(crit("correlacoes_nominal_e_ajustada_publicadas", SEMDADOS, None,
                       "JSON com simulado=false em --artefatos", origem31))
    else:
        problemas, cobertas = [], set()
        for a, j in ok31:
            ctx.marcar(a)
            if j.get("git_sujo") is not False or not j.get("git_commit"):
                problemas.append(f"{a.name}: git_sujo={j.get('git_sujo')!r}, git_commit={j.get('git_commit')!r}")
            for rg in j.get("registros") or []:
                pares = rg.get("pares") or {}
                if all(set((pares.get(p) or {}).keys()) >= {"nominal", "fundamental_ajustada"}
                       for p in ("modelo_x_programada", "modelo_x_medida", "programada_x_medida")):
                    cobertas.add(str(rg.get("classe")))
                else:
                    problemas.append(f"{a.name}: {rg.get('id_captura')} sem as duas correlações")
            entradas = [e for e in j.get("arquivos_entrada") or [] if isinstance(e, dict)]
            if not entradas:
                problemas.append(f"{a.name}: sem arquivos_entrada")
            citadas: Dict[str, Dict[str, Any]] = {}
            for e in entradas:
                citadas.setdefault(str(e.get("sessao")), {})[str(e.get("arquivo"))] = e.get("sha256")
            for ref in {str(rg.get("sessao")) for rg in j.get("registros") or []} - set(citadas):
                citadas[ref] = {}  # registro cita sessão sem arquivos de entrada: precisa ao menos estar em --sessao
            for ref, hashes in citadas.items():
                problemas.extend(f"{a.name}: {m}" for m in _conferir_sessao_citada(ctx, ref, hashes))
        faltam31 = [c for c in classes if c not in cobertas]
        cs.append(crit("correlacoes_nominal_e_ajustada_publicadas",
                       OK if not problemas and not faltam31 else INSUF,
                       {"classes_cobertas": sorted(cobertas), "problemas": problemas or None}, list(classes), origem31,
                       nota=f"faltam classes: {faltam31}" if faltam31 else None))
    return cs, True, {}


AVALIADORES = {"P-01": p01, "P-02": p02, "P-03": p03, "P-05": p05, "P-06": p06, "P-07": p07, "P-08": p08,
               "P-10": p10, "P-16": p16, "P-17": p17, "P-18": p18, "P-19": p19, "P-21": p21, "P-22": p22,
               "P-23": p23, "P-28": p28, "P-31": p31}


# ------------------------------------------------------------------ orquestra
def avaliar(pid: str, ctx: Contexto) -> dict:
    ctx.fontes = set()
    try:
        criterios, tem_dados, extra = AVALIADORES[pid](ctx)
        erro = None
    except Exception as exc:  # noqa: BLE001 - um item com defeito não derruba o relatório
        criterios, tem_dados, extra, erro = [], True, {}, f"{type(exc).__name__}: {exc}"
        criterios.append(crit("avaliador_executou", INSUF, erro, "sem exceção", "scripts/fechar_pendencias.py"))
    humano = HUMANOS.get(pid)
    if humano and tem_dados:
        criterios.append(crit("decisao_humana", ND, None, None, humano))
    status, revisao = decidir(criterios, tem_dados, humano)
    if extra.get("revisao_forcada"):
        revisao = revisao or status == "evidencia_suficiente"
    extra = {k: v for k, v in extra.items() if k != "revisao_forcada"}
    fontes = []
    for f in sorted(ctx.fontes, key=str):
        try:
            fontes.append({"arquivo": str(f), "sha256": sha256_arquivo(f)})
        except OSError as exc:
            fontes.append({"arquivo": str(f), "sha256": None, "erro": str(exc)})
    item = {"id": pid, "titulo": TITULOS[pid], "status": status, "requer_revisao_humana": bool(revisao),
            "criterios": criterios, "arquivos_origem": fontes, "detalhes": extra}
    if erro:
        item["erro_interno"] = erro
    if status == "sem_dados":
        item["nota"] = "sem material físico para este item (sessões simuladas e artefatos simulados não contam)"
    if status == "evidencia_suficiente":
        item["nota"] = "evidência suficiente NÃO é encerramento: o fechamento é decisão do coordenador/responsável"
    return item


def bloco_estado(itens: Dict[str, dict], saida: Path, sessoes: Sequence[Sessao]) -> dict:
    """Trecho opcional para docs/estado_prontidao.json (NÃO é gravado aqui).
    ``status_sugerido`` só vira "concluida" para evidência suficiente sem revisão."""
    base = (RAIZ / "docs").resolve()
    try:
        rel = Path(__import__("os").path.relpath(saida.resolve(), base)).as_posix()
    except ValueError:
        rel = saida.name
    pend = {}
    for pid, it in itens.items():
        if it["status"] != "evidencia_suficiente":
            continue
        chave = pid.replace("-", "")
        pend[chave] = {"status": "aberta" if it["requer_revisao_humana"] else "concluida", "evidencias": [rel],
                       "comentario": ("revisão humana pendente" if it["requer_revisao_humana"]
                                      else "evidência suficiente; o coordenador decide o encerramento")}
    cond: Dict[str, str] = {}
    for s in sessoes:
        regs = s.fisicos
        conds = {chave_condicao(r.get("tensao_base_rms", 0), r.get("f0_hz", 0)) for r in regs}
        if len(conds) == 1:
            c = next(iter(conds))
            if c in CONDICOES:
                try:
                    cond[c] = Path(__import__("os").path.relpath(s.pasta.resolve(), base)).as_posix()
                except ValueError:
                    cond[c] = str(s.pasta)
    return {"aviso": "Proposta; não gravada. Caminhos relativos a docs/. Confira antes de colar.",
            "pendencias": pend, "sessoes": cond}


def montar(sessoes_dirs: Sequence[Path], pc_arquivo: Optional[Path], saida: Path,
           artefatos: Sequence[Path] = ()) -> dict:
    sessoes = [Sessao(p) for p in sessoes_dirs]
    pc = None
    avisos: List[str] = []
    if pc_arquivo is not None:
        try:
            lido = json.loads(Path(pc_arquivo).read_text(encoding="utf-8-sig"))
            pc = lido if isinstance(lido, dict) else None
        except (OSError, ValueError) as exc:
            avisos.append(f"--pc-bancada ilegível: {exc}")
    for s in sessoes:
        avisos += [f"{s.pasta.name}: {e}" for e in s.erros]
        if s.pasta.is_dir() and not s.registros:
            avisos.append(f"{s.pasta.name}: sem metadata/*.jsonl (só artefatos serão avaliados)")
    for a in artefatos:
        if not Path(a).is_dir():
            avisos.append(f"--artefatos {a} não é uma pasta")
    ctx = Contexto(sessoes, pc, pc_arquivo, artefatos)
    itens = {pid: avaliar(pid, ctx) for pid in FISICAS}
    contagem: Dict[str, int] = {}
    for it in itens.values():
        contagem[it["status"]] = contagem.get(it["status"], 0) + 1
    return {
        "esquema": ESQUEMA,
        "ferramenta": "scripts/fechar_pendencias.py",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "aviso": "Evidência offline derivada de sessões; não fecha pendência. Simulação != medição.",
        "ambiente": {"hostname": platform.node(), "plataforma": platform.platform(), "python": sys.version.split()[0],
                     "numpy": np.__version__},
        "sessoes": [s.procedencia() for s in sessoes],
        "pc_bancada": str(pc_arquivo) if pc_arquivo else None,
        "artefatos": [str(a) for a in artefatos],
        "avisos": avisos,
        "resumo": contagem,
        "itens": itens,
        "bloco_estado_prontidao": bloco_estado(itens, saida, sessoes),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sessao", action="append", type=Path, default=[], help="pasta resultados/sessao_* (repetível)")
    ap.add_argument("--artefatos", action="append", type=Path, default=[],
                    help="pasta com artefatos fora da sessão (ex.: logs\\ dos diag_*, resultados\\passo_final_sin_*); repetível")
    ap.add_argument("--pc-bancada", type=Path, default=None, help="JSON de scripts/validar_pc_bancada.ps1 (P-16)")
    ap.add_argument("--saida", type=Path, required=True, help="JSON novo; arquivo existente não será sobrescrito")
    args = ap.parse_args(argv)
    if not args.sessao and args.pc_bancada is None:
        if not args.artefatos:
            ap.error("informe ao menos uma --sessao, --artefatos ou --pc-bancada")
    if args.saida.exists():
        ap.error(f"{args.saida} já existe; recuso sobrescrever (use outro nome)")
    relatorio = limpar(montar(args.sessao, args.pc_bancada, args.saida, args.artefatos))
    texto = json.dumps(relatorio, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.saida.open("x", encoding="utf-8") as destino:
            destino.write(texto)
    except FileExistsError:
        ap.error(f"{args.saida} já existe; recuso sobrescrever (use outro nome)")
    for pid, it in relatorio["itens"].items():
        print(f"{pid}  {it['status']:<22} {'(revisão humana)' if it['requer_revisao_humana'] else ''}  {it['titulo']}")
    print(f"\nRelatório: {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
