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

ESQUEMA = 3
IDS = tuple(f"P-{n:02d}" for n in range(1, 32))

# slug -> (rótulo no site, selo sphinx-design). A ordem é a do placar.
ESTADOS = {
    "concluida": ("Concluída", "success"),
    "aguarda-bancada": ("Software pronto, falta bancada", "warning"),
    "aguarda-decisao": ("Falta decisão ou dado do responsável", "info"),
    "em-andamento": ("Em andamento", "secondary"),
    "insuficiente-bancada": ("Insuficiente na bancada", "primary"),
    "reprovada-bancada": ("Reprovada na bancada", "danger"),
}
# Forma curta (plural) de cada estado, para a linha de placar das outras páginas.
ESTADOS_CURTO = {
    "concluida": "concluídas",
    "aguarda-bancada": "aguardam a bancada",
    "aguarda-decisao": "aguardam decisão ou dado do dono",
    "em-andamento": "em andamento",
    "insuficiente-bancada": "com evidência insuficiente na bancada",
    "reprovada-bancada": "reprovadas na bancada",
}
# situação da escolha feita no fork em relação ao dono do projeto
SITUACOES_DECISAO = {
    "confirmada": "confirmada pelo dono",
    "tomada-no-fork": "tomada no fork, aguardando confirmação do dono",
    "em-branco": "sem escolha: resposta do dono em branco",
    "nao-se-aplica": "sem decisão do dono envolvida",
}
SITUACOES_CURTAS = {
    "confirmada": "confirmada",
    "tomada-no-fork": "tomada no fork, aguarda confirmação",
    "em-branco": "em branco",
    "nao-se-aplica": "—",
}
# de onde vêm as opções listadas em uma pergunta ao dono
FONTES_OPCOES = {
    "formulario": "formulário de decisões em `docs/projeto/pendencias.md`",
    "inventario": "inventário de 16/10",
    "evidencia": "evidência de 22/10",
    "sem-opcoes-previas": "sem opções prévias; proposta do revisor, não do formulário",
}
QUEM_FECHA = {"bancada": "bancada", "decisao-dono": "decisão do dono", "codigo": "código"}
PRIORIDADES = ("alta", "media", "baixa")
_CAMPOS_TEXTO = ("titulo", "responsavel", "acao", "dependencia", "criterio", "falta", "como_tratada")
_CAMPOS_TEXTO_OPCIONAL = ("situacao_execucao", "entrega", "direcao_vigente")


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


def _texto(valor):
    return isinstance(valor, str) and bool(valor.strip())


def _validar_decisao(ident, item, estado):
    """``decisao_dono``: registrada (booleano), situacao, texto e, quando há pergunta, opções."""
    erros = []
    decisao = item.get("decisao_dono")
    if not isinstance(decisao, dict) or not isinstance(decisao.get("registrada"), bool) \
            or not _texto(decisao.get("texto")):
        return [f"{ident}: decisao_dono exige 'registrada' (booleano) e 'texto'"]
    situacao = decisao.get("situacao")
    if situacao not in SITUACOES_DECISAO:
        erros.append(f"{ident}: decisao_dono.situacao {situacao!r} fora da lista {sorted(SITUACOES_DECISAO)}")
    elif decisao["registrada"] != (situacao == "confirmada"):
        erros.append(f"{ident}: decisao_dono.registrada só é verdadeira quando a situação é 'confirmada'")
    if situacao == "confirmada" and not _texto(decisao.get("data")):
        erros.append(f"{ident}: decisão confirmada exige 'data' e a fonte no texto")
    if estado == "concluida" and situacao == "em-branco":
        erros.append(f"{ident}: pendência concluída não pode ter a decisão do dono em branco")
    pergunta = decisao.get("pergunta")
    opcoes = decisao.get("opcoes")
    if situacao in ("tomada-no-fork", "em-branco") and not _texto(pergunta):
        erros.append(f"{ident}: decisão {situacao} exige 'pergunta' ao dono")
    if pergunta is not None or opcoes is not None:
        if not _texto(pergunta):
            erros.append(f"{ident}: 'pergunta' deve ser texto não vazio")
        if not isinstance(opcoes, list) or not opcoes or any(not _texto(o) for o in opcoes):
            erros.append(f"{ident}: 'opcoes' deve ser lista não vazia de textos")
        if decisao.get("fonte_opcoes") not in FONTES_OPCOES:
            erros.append(f"{ident}: 'fonte_opcoes' deve ser uma de {sorted(FONTES_OPCOES)}")
    return erros


def _validar_falta_por_tipo(ident, item, estado):
    """``falta_por_tipo``: o que falta separado por quem faz (bancada, código, decisão do dono)."""
    falta = item.get("falta_por_tipo")
    if not isinstance(falta, dict):
        return [f"{ident}: falta_por_tipo deve ser objeto (pode ser vazio se concluída)"]
    erros = []
    for chave, texto in falta.items():
        if chave not in QUEM_FECHA:
            erros.append(f"{ident}: falta_por_tipo tem chave {chave!r} fora de {sorted(QUEM_FECHA)}")
        elif not _texto(texto):
            erros.append(f"{ident}: falta_por_tipo[{chave!r}] deve ser texto não vazio")
    if estado != "concluida":
        if not falta:
            erros.append(f"{ident}: pendência não concluída exige falta_por_tipo não vazio")
        elif isinstance(item.get("quem_fecha"), list) and set(falta) != set(item["quem_fecha"]):
            erros.append(f"{ident}: falta_por_tipo {sorted(falta)} difere de quem_fecha {sorted(item['quem_fecha'])}")
    return erros


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
        erros.extend(_validar_decisao(ident, item, estado))
        erros.extend(_validar_falta_por_tipo(ident, item, estado))
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


def aguardam_confirmacao(dados):
    """Ids das pendências concluídas no fork cuja escolha ainda espera o dono."""
    return [ident for ident, item in dados["pendencias"].items()
            if item["estado"] == "concluida" and item["decisao_dono"].get("situacao") == "tomada-no-fork"]


def perguntas_ao_dono(dados):
    """Pares (id, decisao_dono) das pendências que têm pergunta ao dono, na ordem P-01..P-31."""
    return [(ident, dados["pendencias"][ident]["decisao_dono"]) for ident in IDS
            if dados["pendencias"][ident]["decisao_dono"].get("pergunta")]


def gerar_placar_linha(dados):
    """Uma linha com o placar, para páginas que apontam para a página de pendências."""
    cont = contagem(dados)
    partes = [f"{cont[s]} {ESTADOS_CURTO[s]}" for s in ESTADOS if cont[s]]
    texto = ", ".join(partes)
    espera = aguardam_confirmacao(dados)
    if espera:
        texto += f"; das concluídas, {len(espera)} aguardam a confirmação do dono"
    return texto + f" (total {sum(cont.values())}, atualizado em {dados.get('atualizado', '?')})"


def _celula(texto):
    return str(texto).replace("|", "\\|").replace("\n", " ")


def _selo(estado):
    rotulo, cor = ESTADOS[estado]
    return "{bdg-%s}`%s`" % (cor, rotulo)


def _quem(item):
    return ", ".join(QUEM_FECHA[q] for q in item["quem_fecha"])


def _situacao(item):
    return SITUACOES_CURTAS[item["decisao_dono"]["situacao"]]


def _opcoes_markdown(decisao):
    fonte = FONTES_OPCOES[decisao["fonte_opcoes"]]
    return "; ".join(decisao["opcoes"]) + f" (opções: {fonte})"


def gerar_markdown(dados):
    """Markdown (MyST) do placar, das perguntas ao dono, da matriz e do detalhe por pendência,
    com âncoras ``estado-p-NN``. Um título de seção por pendência, ``####``: a página que
    recebe o trecho deve ter o nível ``###`` livre para os subtítulos abaixo."""
    pend = dados["pendencias"]
    cont = contagem(dados)
    linhas = []
    atualizado = dados.get("atualizado", "")
    nota = dados.get("nota_atualizacao", "")
    linhas.append(f"**Atualizado em {atualizado}** ({nota}). " if nota else f"**Atualizado em {atualizado}.** ")
    linhas[-1] += "Gerado no build a partir de `docs/estado_prontidao.json`; não edite esta tabela à mão."
    linhas += ["", "### Placar", ""]
    linhas.append("| " + " | ".join(ESTADOS[s][0] for s in ESTADOS) + " | Total |")
    linhas.append("|" + "---|" * (len(ESTADOS) + 1))
    linhas.append("| " + " | ".join(str(cont[s]) for s in ESTADOS) + f" | {sum(cont.values())} |")
    espera = aguardam_confirmacao(dados)
    linhas += ["", f"Das {cont['concluida']} concluídas, **{len(espera)} aguardam a confirmação do dono** "
               "(a escolha foi tomada no fork, sem resposta registrada no formulário de decisões desta página): "
               + ", ".join(f"{{ref}}`{i} <estado-{i.lower()}>`" for i in espera) + "."]
    perguntas = perguntas_ao_dono(dados)
    linhas += ["", "### Perguntas ao dono", "",
               f"{len(perguntas)} decisões esperam o dono do projeto. Nenhuma foi tomada por esta página: "
               "cada linha traz a pergunta e as opções conhecidas; só vale o que o dono responder "
               "(registre no formulário de decisões desta página e em `decisao_dono`).", ""]
    for ident, d in perguntas:
        linhas.append(f"- {{ref}}`{ident} <estado-{ident.lower()}>` ({SITUACOES_DECISAO[d['situacao']]}): "
                      f"{d['pergunta']} Opções: {_opcoes_markdown(d)}")
    linhas += ["", "### Matriz", ""]
    linhas.append("| ID | Estado | Prioridade | Quem fecha | Escolha do fork / dono | O que falta para fechar |")
    linhas.append("|---|---|---|---|---|---|")
    for ident in IDS:
        it = pend[ident]
        linhas.append("| {ref}`%s <estado-%s>` | %s | %s | %s | %s | %s |" % (
            ident, ident.lower(), _selo(it["estado"]), it["prioridade"], _quem(it), _situacao(it),
            _celula(it["falta"])))
    linhas += ["", "### Cada pendência: o que pede, o que foi feito, o que falta", ""]
    for ident in IDS:
        it = pend[ident]
        d = it["decisao_dono"]
        linhas += [f"(estado-{ident.lower()})=", f"#### {ident} — {it['titulo']}", "",
                   f"{_selo(it['estado'])} prioridade {it['prioridade']}; quem fecha: {_quem(it)}.", ""]
        linhas.append(f"- **Pedido original:** {it['acao']} (inventário de 16/10: {{ref}}`{ident} <{ident.lower()}>`)")
        linhas.append(f"- **Fecha quando:** {it['criterio']}")
        linhas.append(f"- **Depende de:** {it['dependencia']}")
        linhas.append(f"- **Como foi resolvida ou o que foi feito:** {it['como_tratada']}")
        if it.get("entrega"):
            situacao = it.get("situacao_execucao") or ""
            linhas.append(f"- **Registro da execução** ({situacao}): {it['entrega']}")
        if it.get("direcao_vigente"):
            linhas.append(f"- **Direção vigente:** {it['direcao_vigente']}")
        faltas = it["falta_por_tipo"]
        if faltas:
            linhas.append("- **O que falta:**")
            for chave in QUEM_FECHA:
                if chave in faltas:
                    linhas.append(f"  - *{QUEM_FECHA[chave].capitalize()}:* {faltas[chave]}")
        else:
            linhas.append(f"- **O que falta:** {it['falta']}")
        data = f" ({d['data']})" if d.get("data") else ""
        linhas.append(f"- **Escolha do fork e decisão do dono, {SITUACOES_DECISAO[d['situacao']]}{data}:** {d['texto']}")
        if d.get("pergunta"):
            linhas.append(f"  - *Pergunta ao dono:* {d['pergunta']} Opções: {_opcoes_markdown(d)}")
        commits = ", ".join(f"`{c}`" for c in it["commits"]) or "—"
        linhas.append(f"- **Commits:** {commits}")
        evid = ", ".join(f"`docs/{e}`" for e in it["evidencias"]) or "—"
        linhas.append(f"- **Evidências:** {evid}")
        linhas.append("")
    return "\n".join(linhas) + "\n"
