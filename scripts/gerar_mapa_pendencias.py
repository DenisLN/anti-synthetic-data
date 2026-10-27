"""Regenera mapa/pendencias/P-NN.md a partir do arquivo único de estado.

Fonte: docs/estado_prontidao.json (formato em docs/contribuir_docs.md), validado
antes de qualquer escrita. Grava mapa/_modelos/pendencias.json e renderiza as 31
notas com o renderizador embutido, que reproduz o modelo mapa/_modelos/pendencia.knap.md
sem Node.js nem rede. Com --knap, renderiza com o Knap (skill oficial do Obsidian;
requer Node.js 20+ e `npx knap`) em vez do renderizador embutido.

Uso: python scripts/gerar_mapa_pendencias.py [--sem-render] [--knap]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ESTADO = RAIZ / "docs" / "estado_prontidao.json"
MODELO_JSON = RAIZ / "mapa" / "_modelos" / "pendencias.json"
MODELO_KNAP = RAIZ / "mapa" / "_modelos" / "pendencia.knap.md"
SAIDA = RAIZ / "mapa" / "pendencias"

# Callout de cada estado do esquema 3 (docs/_ext/estado_pendencias.py: ESTADOS); espelha o modelo Knap.
CALLOUTS = {
    "concluida": "> [!success] Concluída",
    "aguarda-bancada": "> [!todo] Software pronto; falta bancada — ver [[docs/bancada_pendencias]]",
    "aguarda-decisao": "> [!question] Aguarda decisão ou dado do responsável — ver [[docs/projeto/pendencias]]",
    "em-andamento": "> [!info] Em andamento",
    "insuficiente-bancada": "> [!warning] Insuficiente na bancada: medida feita, resultado inconclusivo — ver [[docs/bancada_pendencias]]",
    "reprovada-bancada": "> [!failure] Reprovada na bancada — ver [[docs/bancada_pendencias]]",
}


def _carregar_lib():
    caminho = RAIZ / "docs" / "_ext" / "estado_pendencias.py"
    spec = importlib.util.spec_from_file_location("estado_pendencias", caminho)
    lib = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lib)
    return lib


def montar(dados: dict) -> list[dict]:
    """Itens do modelo do mapa (mesmas chaves do pendencias.json anterior)."""
    itens = []
    for pid, it in dados["pendencias"].items():
        # O texto de destaque da nota: para concluída, como foi tratada; senão, o que falta.
        destaque = (it.get("como_tratada") or it["falta"]) if it["estado"] == "concluida" else it["falta"]
        itens.append({
            "id": pid,
            "titulo": it["titulo"],
            "status": it["estado"],
            "prioridade": it["prioridade"],
            "responsavel": it["responsavel"],
            "acao": it["acao"],
            "dependencia": it["dependencia"],
            "criterio": it["criterio"],
            "falta": destaque,
            "frentes": list(it["frentes"]),
            "evidencias": list(it["evidencias"]),
            "evidencias_txt": ", ".join(f"`docs/{e}`" for e in it["evidencias"]) or "—",
        })
    return itens


def _yaml(chave: str, valor) -> str:
    if isinstance(valor, list):
        if not valor:
            return f"{chave}: []"
        return chave + ":\n" + "\n".join(f"  - {json.dumps(v, ensure_ascii=False)}" for v in valor)
    return f"{chave}: {json.dumps(valor, ensure_ascii=False)}"


def renderizar(it: dict) -> str:
    """Nota Obsidian de uma pendência; espelha mapa/_modelos/pendencia.knap.md."""
    st = it["status"]
    cab = "\n".join(_yaml(c, it[c]) for c in
                    ("id", "titulo", "status", "prioridade", "responsavel", "frentes", "evidencias"))
    callout = CALLOUTS.get(st)
    if callout is None:
        raise ValueError(f"estado sem callout no mapa: {st!r}")
    corpo = [f"{callout}\n> {it['falta']}\n"]
    linhas = []
    if it["acao"] != it["titulo"]:
        linhas.append(f"- **Ação:** {it['acao']}")
    linhas += [f"- **Depende de:** {it['dependencia']}",
               f"- **Fecha quando:** {it['criterio']}",
               f"- **Evidências:** {it['evidencias_txt']}"]
    corpo.append("\n".join(linhas) + "\n")
    corpo.append("Estado geral: [[docs/projeto/pendencias|estado das pendências]] · "
                 "[[mapa/Pendencias.base|painel]] · [[mapa/00 Início|início]]")
    return (f"---\n{cab}\ntags:\n  - pendencia\n  - {st}\n---\n# {it['id']} — {it['titulo']}\n\n"
            + "\n".join(corpo) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sem-render", action="store_true", help="só grava o JSON do modelo")
    ap.add_argument("--knap", action="store_true", help="renderiza com `npx knap` (Node.js 20+) em vez do embutido")
    a = ap.parse_args(argv)
    lib = _carregar_lib()
    try:
        dados = lib.carregar(ESTADO)
    except lib.EstadoInvalido as exc:
        raise SystemExit(str(exc))
    erros = lib.validar(dados, ESTADO.parent)
    if erros:
        raise SystemExit("docs/estado_prontidao.json inválido:\n  " + "\n  ".join(erros))
    itens = montar(dados)
    MODELO_JSON.write_bytes((json.dumps(itens, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    if a.sem_render:
        return 0
    if a.knap:
        npx = "npx.cmd" if sys.platform == "win32" else "npx"
        return subprocess.call([npx, "--yes", "knap", "batch", str(MODELO_KNAP), "--data", str(MODELO_JSON),
                                "--output-dir", str(SAIDA), "--filename", "{{ id | safe_name }}.md", "--overwrite"])
    SAIDA.mkdir(parents=True, exist_ok=True)
    for it in itens:
        (SAIDA / f"{it['id']}.md").write_bytes(renderizar(it).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
