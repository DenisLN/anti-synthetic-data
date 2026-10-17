"""Papéis ``{scpi}`` (AMETEK) e ``{scpik}`` (Keysight) para o site do ASD.

Uso nas páginas: {scpi}`TRACe:DATA` vira um link para a entrada de referência
``(scpi-trace-data)=``. O texto pode levar argumentos ({scpi}`VOLTage:MODE STEP`):
só a primeira palavra define o alvo. Com ``-W``, um comando sem entrada falha o
build (aviso de referência não resolvida), que é o objetivo.
"""

import re

from docutils import nodes
from sphinx import addnodes
from sphinx.util.docutils import SphinxRole


def chave(comando, prefixo="scpi"):
    """Rótulo da entrada de um comando.

    Remove argumentos, dois-pontos inicial, ``?`` final e o prefixo opcional
    ``SOURce:`` (que o manual da AMETEK declara facultativo); minúsculas;
    qualquer caractere fora de ``[a-z0-9]`` vira hífen.
    """
    primeira = comando.strip().split()[0]
    primeira = primeira.lstrip(":").rstrip("?")
    primeira = re.sub(r"^sour(ce)?:", "", primeira, flags=re.IGNORECASE)
    miolo = re.sub(r"[^a-z0-9]+", "-", primeira.lower()).strip("-")
    return f"{prefixo}-{miolo}"


class _PapelScpi(SphinxRole):
    prefixo = "scpi"

    def run(self):
        alvo = chave(self.text, self.prefixo)
        no = addnodes.pending_xref(
            "",
            refdomain="std",
            reftype="ref",
            reftarget=alvo,
            refexplicit=True,
            refwarn=True,
        )
        no += nodes.literal(self.text, self.text, classes=["scpi-cmd"])
        return [no], []


class PapelScpi(_PapelScpi):
    prefixo = "scpi"


class PapelScpiKeysight(_PapelScpi):
    prefixo = "scpik"


def setup(app):
    app.add_role("scpi", PapelScpi())
    app.add_role("scpik", PapelScpiKeysight())
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
