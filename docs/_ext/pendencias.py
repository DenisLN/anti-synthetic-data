"""Renderiza o estado das pendências (P-01 a P-31) no build do Sphinx.

A página ``projeto/pendencias.md`` (a única que é processada) traz uma linha com o marcador
``@@pendencias-estado@@``; no evento ``source-read`` o marcador é trocado pelo
Markdown gerado de ``docs/estado_prontidao.json`` (placar, matriz e uma seção
por pendência com a âncora ``estado-p-NN``). O arquivo é validado antes: um
estado inválido (P-NN faltando ou repetido, estado fora da lista, evidência
inexistente) derruba o build, que roda com ``-W``. A lógica está em
``estado_pendencias.py``, que não depende do Sphinx.
"""

from pathlib import Path

from sphinx.errors import ExtensionError

import estado_pendencias

MARCADOR = "@@pendencias-estado@@"
ARQUIVO = "estado_prontidao.json"
PAGINA = "projeto/pendencias"  # só esta página recebe o trecho gerado


def _substituir(app, docname, source):
    if docname != PAGINA or MARCADOR not in source[0]:
        return
    caminho = Path(app.srcdir) / ARQUIVO
    app.env.note_dependency(str(caminho))
    try:
        dados = estado_pendencias.carregar(caminho)
    except estado_pendencias.EstadoInvalido as exc:
        raise ExtensionError(str(exc)) from exc
    erros = estado_pendencias.validar(dados, app.srcdir)
    if erros:
        raise ExtensionError(f"{ARQUIVO} inválido:\n  " + "\n  ".join(erros))
    source[0] = source[0].replace(MARCADOR, estado_pendencias.gerar_markdown(dados))


def setup(app):
    app.connect("source-read", _substituir)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
