"""Regenera mapa/pendencias/P-NN.md a partir do rastreador, do plano e do estado.

Fontes: docs/PENDENCIAS_TRACKER.md (estado, o que falta, frentes),
../entregas/Plano_de_acao_ASD.md (prioridade, ação, dependência, critério) e
docs/estado_prontidao.json (evidências). Grava mapa/_modelos/pendencias.json e
renderiza com Knap (skill oficial do Obsidian): requer Node.js 20+ (`npx knap`).

Uso: python scripts/gerar_mapa_pendencias.py [--plano CAMINHO] [--sem-render]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ESTADOS = {"✅": "concluida", "🔧→🏭": "aguarda-bancada", "❓": "aguarda-decisao", "⏳": "em-andamento"}


def montar(plano_txt: str, tracker_txt: str, estado: dict) -> list[dict]:
    itens = []
    for n in range(1, 32):
        pid = f"P-{n:02d}"
        m = re.search(rf"^\| {pid} (Alta|Média|Baixa) \| (.*?) \| (.*?) \| (.*?) \|$", plano_txt, re.M)
        t = re.search(rf"^\| {pid} \| (\S+) \| (.*?) \| (.*?) \|$", tracker_txt, re.M)
        if not m or not t:
            raise SystemExit(f"{pid}: linha ausente no plano ou no rastreador")
        prioridade, acao, dependencia, criterio = m.groups()
        emoji, falta, frente = t.groups()
        if emoji not in ESTADOS:
            raise SystemExit(f"{pid}: estado desconhecido {emoji!r} no rastreador")
        responsavel, _, acao_txt = acao.partition(":")
        evid = estado["pendencias"][pid.replace("-", "")]["evidencias"]
        itens.append({
            "id": pid,
            "titulo": acao_txt.strip().split(";")[0][:110],
            "status": ESTADOS[emoji],
            "prioridade": prioridade.replace("é", "e").lower(),
            "responsavel": responsavel.strip(),
            "acao": acao_txt.strip(),
            "dependencia": dependencia.strip(),
            "criterio": criterio.strip(),
            "falta": falta.strip(),
            "frentes": [f.strip() for f in frente.split(",") if f.strip() not in ("—", "")],
            "evidencias": evid,
            "evidencias_txt": ", ".join(f"`docs/{e}`" for e in evid) or "—",
        })
    return itens


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plano", default=str(RAIZ.parent / "entregas" / "Plano_de_acao_ASD.md"))
    ap.add_argument("--sem-render", action="store_true", help="só grava o JSON")
    a = ap.parse_args(argv)
    plano = Path(a.plano)
    dados = RAIZ / "mapa" / "_modelos" / "pendencias.json"
    if plano.exists():
        itens = montar(plano.read_text(encoding="utf-8"),
                       (RAIZ / "docs" / "PENDENCIAS_TRACKER.md").read_text(encoding="utf-8"),
                       json.loads((RAIZ / "docs" / "estado_prontidao.json").read_text(encoding="utf-8")))
        dados.write_bytes((json.dumps(itens, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    elif not dados.exists():
        raise SystemExit(f"Plano ausente ({plano}) e sem {dados} para reaproveitar")
    else:
        # Fora do Mac o plano (pasta entregas/) não existe: reaproveita o JSON
        # versionado e atualiza só estado/falta/evidências a partir do repositório.
        itens = json.loads(dados.read_text(encoding="utf-8"))
        tracker = (RAIZ / "docs" / "PENDENCIAS_TRACKER.md").read_text(encoding="utf-8")
        estado = json.loads((RAIZ / "docs" / "estado_prontidao.json").read_text(encoding="utf-8"))
        for it in itens:
            t = re.search(rf"^\| {it['id']} \| (\S+) \| (.*?) \| (.*?) \|$", tracker, re.M)
            it["status"], it["falta"] = ESTADOS[t.group(1)], t.group(2).strip()
            it["evidencias"] = estado["pendencias"][it["id"].replace("-", "")]["evidencias"]
            it["evidencias_txt"] = ", ".join(f"`docs/{e}`" for e in it["evidencias"]) or "—"
        dados.write_bytes((json.dumps(itens, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    if a.sem_render:
        return 0
    npx = "npx.cmd" if sys.platform == "win32" else "npx"
    return subprocess.call([npx, "--yes", "knap", "batch", str(RAIZ / "mapa" / "_modelos" / "pendencia.knap.md"),
                            "--data", str(dados), "--output-dir", str(RAIZ / "mapa" / "pendencias"),
                            "--filename", "{{ id | safe_name }}.md", "--overwrite"])


if __name__ == "__main__":
    raise SystemExit(main())
