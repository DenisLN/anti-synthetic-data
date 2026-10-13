"""Acrescenta/atualiza a chave ``portavel`` dos dois fixtures de ``gerar()``.

Uso (na raiz do projeto): ``python -m tests.gravar_fixtures_portaveis``.
Nao toca em ``hashes`` (assinatura exata de origem). Grava os resumos do
``gerar()`` ATUAL; so rode isto quando o dataset muda de proposito (declarar no
CHANGELOG) ou para criar a chave ``portavel`` pela primeira vez, com o codigo
que os ``hashes`` ja validam. Ver docs/testes.md.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402

from tests import assinatura_portavel as ap  # noqa: E402
from tests import test_offline as T  # noqa: E402

FIXTURES = RAIZ / "tests" / "fixtures"
ALVOS = {"gerar_literatura_34a0d82.json": True, "gerar_sorteio_v1_15.json": False}  # nome -> sem_sorteio


def _escreve(caminho, dados):
    linhas = ["{"]
    topo = [k for k in dados if k not in ("hashes", "portavel")]
    for k in topo:
        linhas.append(f"{json.dumps(k)}: {json.dumps(dados[k], ensure_ascii=False)},")
    linhas.append('"hashes": {')
    itens = list(dados["hashes"].items())
    for i, (k, v) in enumerate(itens):
        linhas.append(f"{json.dumps(k)}: {json.dumps(v)}" + ("," if i < len(itens) - 1 else ""))
    linhas.append("},")
    p = dados["portavel"]
    linhas.append('"portavel": {')
    for k in ("descricao", "tol_abs", "rtol_parametros", "nproj"):
        linhas.append(f"{json.dumps(k)}: {json.dumps(p[k], ensure_ascii=False)},")
    linhas.append('"resumos": {')
    itens = list(p["resumos"].items())
    for i, (k, v) in enumerate(itens):
        linhas.append(f"{json.dumps(k)}: {json.dumps(v, sort_keys=True)}" + ("," if i < len(itens) - 1 else ""))
    linhas.append("}")
    linhas.append("}")
    linhas.append("}")
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main():
    for nome, sem_sorteio in ALVOS.items():
        caminho = FIXTURES / nome
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        resumos = {}
        for chave in dados["hashes"]:
            cid, f0, seed, indice = chave.split("/")
            exp = T._load_experimento(cid)
            if sem_sorteio:
                exp = T._sem_sorteio(exp)
            resumos[chave] = ap.gerar_resumo(exp, float(f0), int(seed), int(indice))
        dados["portavel"] = {
            "descricao": "assinatura por tolerancia, portavel entre plataformas; ver tests/assinatura_portavel.py "
                         "(gravada no Linux/Python 3.13/numpy " + np.__version__ + "; NAO VERIFICADO no Windows)",
            "tol_abs": ap.TOL_ABS,
            "rtol_parametros": ap.RTOL_PARAMETROS,
            "nproj": ap.NPROJ,
            "resumos": resumos,
        }
        _escreve(caminho, dados)
        print(nome, len(resumos), "resumos")


if __name__ == "__main__":
    main()
