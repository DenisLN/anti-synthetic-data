"""Leitura e validação do arquivo único de estado das pendências (P-01 a P-31).

Módulo só com a biblioteca padrão, sem importar o Sphinx, para ser usado por três
consumidores: a extensão ``pendencias`` (renderiza o estado no site), os scripts
``gerar_mapa_pendencias.py`` e ``verificar_prontidao.py`` e o teste offline
``tests/test_estado_pendencias.py``. O arquivo é ``docs/estado_prontidao.json``;
o formato está descrito em ``docs/contribuir_docs.md``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ESQUEMA = 2
IDS = tuple(f"P-{n:02d}" for n in range(1, 32))

# slug -> (rótulo no site, selo sphinx-design). A ordem é a do placar.
ESTADOS = {
    "concluida": ("Concluída", "success"),
    "aguarda-bancada": ("Software pronto, falta bancada", "warning"),
    "aguarda-decisao": ("Falta decisão ou dado do responsável", "info"),
    "em-andamento": ("Em andamento", "secondary"),
    "reprovada-bancada": ("Reprovada na bancada", "danger"),
}
QUEM_FECHA = {"bancada": "bancada", "decisao-dono": "decisão do dono", "codigo": "código"}
PRIORIDADES = ("alta", "media", "baixa")
_CAMPOS_TEXTO = ("titulo", "responsavel", "acao", "dependencia", "criterio", "falta")
_CAMPOS_TEXTO_OPCIONAL = ("como_tratada", "situacao_execucao", "entrega", "direcao_vigente")


class EstadoInvalido(ValueError):
    """Arquivo de estado ilegível ou com chave repetida."""


def _sem_repetidas(pares):
    saida = {}
    for chave, valor in pares:
        if chave in saida:
            raise EstadoInvalido(f"chave repetida no JSON: {chave!r}")
        saida[chave] = valor
    return saida


def carregar(caminho):
    """Lê o JSON recusando chaves repetidas (um P-NN repetido não passa em silêncio)."""
    try:
        texto = Path(caminho).read_text(encoding="utf-8")
        dados = json.loads(texto, object_pairs_hook=_sem_repetidas)
    except OSError as exc:
        raise EstadoInvalido(f"{caminho}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EstadoInvalido(f"{caminho}: JSON inválido: {exc}") from exc
    if not isinstance(dados, dict):
        raise EstadoInvalido(f"{caminho}: a raiz deve ser um objeto")
    return dados


def _caminho_relativo_ok(base, texto):
    if not isinstance(texto, str) or not texto.strip() or Path(texto).is_absolute():
        return "caminho relativo não vazio obrigatório"
    alvo = (base / texto).resolve()
    if not alvo.is_relative_to(base.resolve()):
        return "caminho fora de docs/"
    if not alvo.is_file():
        return "arquivo inexistente"
    return None


def validar(dados, base_docs):
    """Devolve a lista de problemas (vazia se o arquivo é válido).

    ``base_docs`` é a pasta ``docs/``: as evidências são caminhos relativos a ela
    (por exemplo ``evidencias/2026-10-22/fechamento.json``) e precisam existir.
    """
    base = Path(base_docs)
    erros = []
    if dados.get("esquema") != ESQUEMA:
        erros.append(f"esquema deve ser {ESQUEMA}")
    pend = dados.get("pendencias")
    if not isinstance(pend, dict):
        return erros + ["'pendencias' deve ser um objeto"]
    for ident in IDS:
        if ident not in pend:
            erros.append(f"{ident}: pendência faltando")
    for ident in pend:
        if ident not in IDS:
            erros.append(f"{ident}: identificador fora de P-01..P-31")
    for ident in IDS:
        item = pend.get(ident)
        if item is None:
            continue
        if not isinstance(item, dict):
            erros.append(f"{ident}: deve ser um objeto")
            continue
        estado = item.get("estado")
        if estado not in ESTADOS:
            erros.append(f"{ident}: estado {estado!r} fora da lista {sorted(ESTADOS)}")
        if item.get("prioridade") not in PRIORIDADES:
            erros.append(f"{ident}: prioridade {item.get('prioridade')!r} fora de {PRIORIDADES}")
        for campo in _CAMPOS_TEXTO:
            if not isinstance(item.get(campo), str) or not item[campo].strip():
                erros.append(f"{ident}: campo '{campo}' obrigatório (texto não vazio)")
        for campo in _CAMPOS_TEXTO_OPCIONAL:
            if item.get(campo) is not None and not isinstance(item[campo], str):
                erros.append(f"{ident}: campo '{campo}' deve ser texto ou null")
        quem = item.get("quem_fecha")
        if not isinstance(quem, list) or not quem or any(q not in QUEM_FECHA for q in quem):
            erros.append(f"{ident}: quem_fecha deve ser lista não vazia de {sorted(QUEM_FECHA)}")
        frentes = item.get("frentes")
        if not isinstance(frentes, list) or any(not isinstance(f, str) for f in frentes):
            erros.append(f"{ident}: frentes deve ser lista de textos")
        decisao = item.get("decisao_dono")
        if (not isinstance(decisao, dict) or not isinstance(decisao.get("registrada"), bool)
                or not isinstance(decisao.get("texto"), str) or not decisao["texto"].strip()):
            erros.append(f"{ident}: decisao_dono exige 'registrada' (booleano) e 'texto'")
        commits = item.get("commits")
        if not isinstance(commits, list) or any(
                not isinstance(c, str) or not re.fullmatch(r"[0-9a-f]{7,40}", c) for c in commits):
            erros.append(f"{ident}: commits deve ser lista de hashes hexadecimais (7 a 40)")
        evidencias = item.get("evidencias")
        if not isinstance(evidencias, list):
            erros.append(f"{ident}: evidencias deve ser lista")
            evidencias = []
        for ev in evidencias:
            problema = _caminho_relativo_ok(base, ev)
            if problema:
                erros.append(f"{ident}: evidência {ev!r}: {problema}")
        if estado == "concluida" and not evidencias:
            erros.append(f"{ident}: pendência concluída exige ao menos uma evidência")
    return erros


def contagem(dados):
    """Placar: número de pendências por estado (todos os estados, na ordem do placar)."""
    saida = {slug: 0 for slug in ESTADOS}
    for item in dados["pendencias"].values():
        saida[item["estado"]] += 1
    return saida


def _celula(texto):
    return str(texto).replace("|", "\\|").replace("\n", " ")


def _selo(estado):
    rotulo, cor = ESTADOS[estado]
    return "{bdg-%s}`%s`" % (cor, rotulo)


def _quem(item):
    return ", ".join(QUEM_FECHA[q] for q in item["quem_fecha"])


def _decisao(item):
    return "registrada" if item["decisao_dono"]["registrada"] else "não registrada"


def gerar_markdown(dados):
    """Markdown (MyST) do placar, da matriz e do detalhe por pendência, com âncoras
    ``estado-p-NN``. Um título de seção por pendência, ``####``: a página que recebe o
    trecho deve ter o nível ``###`` livre para os subtítulos abaixo."""
    pend = dados["pendencias"]
    cont = contagem(dados)
    linhas = []
    atualizado = dados.get("atualizado", "")
    nota = dados.get("nota_atualizacao", "")
    linhas.append(f"**Atualizado em {atualizado}** ({nota}). " if nota else f"**Atualizado em {atualizado}.** ")
    linhas[-1] += "Gerado no build a partir de `docs/estado_prontidao.json`; não edite esta tabela à mão."
    linhas += ["", "### Placar", ""]
    linhas.append("| " + " | ".join(ESTADOS[s][0] for s in ESTADOS) + " |")
    linhas.append("|" + "---|" * len(ESTADOS))
    linhas.append("| " + " | ".join(str(cont[s]) for s in ESTADOS) + " |")
    linhas += ["", "### Matriz", ""]
    linhas.append("| ID | Estado | Prioridade | Quem fecha | Decisão do dono | O que falta para fechar |")
    linhas.append("|---|---|---|---|---|---|")
    for ident in IDS:
        it = pend[ident]
        linhas.append("| {ref}`%s <estado-%s>` | %s | %s | %s | %s | %s |" % (
            ident, ident.lower(), _selo(it["estado"]), it["prioridade"], _quem(it), _decisao(it),
            _celula(it["falta"])))
    linhas += ["", "### Cada pendência: o que pede, o que foi feito, o que falta", ""]
    for ident in IDS:
        it = pend[ident]
        linhas += [f"(estado-{ident.lower()})=", f"#### {ident} — {it['titulo']}", "",
                   f"{_selo(it['estado'])} prioridade {it['prioridade']}; quem fecha: {_quem(it)}.", ""]
        linhas.append(f"- **Pede:** {it['acao']}")
        linhas.append(f"- **Fecha quando:** {it['criterio']}")
        linhas.append(f"- **Depende de:** {it['dependencia']}")
        linhas.append(f"- **Como foi resolvida ou tratada:** {it.get('como_tratada') or 'a registrar na revisão dos estados'}")
        if it.get("entrega"):
            situacao = it.get("situacao_execucao") or ""
            linhas.append(f"- **Registro da execução** ({situacao}): {it['entrega']}")
        if it.get("direcao_vigente"):
            linhas.append(f"- **Direção vigente:** {it['direcao_vigente']}")
        linhas.append(f"- **O que falta:** {it['falta']}")
        d = it["decisao_dono"]
        data = f" ({d['data']})" if d.get("data") else ""
        linhas.append(f"- **Decisão do dono ({_decisao(it)}){data}:** {d['texto']}")
        commits = ", ".join(f"`{c}`" for c in it["commits"]) or "—"
        linhas.append(f"- **Commits:** {commits}")
        evid = ", ".join(f"`docs/{e}`" for e in it["evidencias"]) or "—"
        linhas.append(f"- **Evidências:** {evid}")
        linhas.append("")
    return "\n".join(linhas) + "\n"
