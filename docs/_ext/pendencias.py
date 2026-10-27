"""Renderiza o estado das pendências (P-01 a P-31) no build do Sphinx.

A página ``projeto/pendencias.md`` traz uma linha com o marcador
``@@pendencias-estado@@``; no evento ``source-read`` o marcador é trocado pelo
Markdown gerado de ``docs/estado_prontidao.json`` (placar, perguntas ao dono, matriz e uma
seção por pendência com a âncora ``estado-p-NN``). Qualquer página pode trazer o marcador
``@@pendencias-placar@@``, trocado por uma linha com o placar (assim o número citado fora da
página de pendências nunca diverge do arquivo). O arquivo é validado antes: um
estado inválido (P-NN faltando ou repetido, estado fora da lista, evidência
inexistente) derruba o build, que roda com ``-W``. A lógica está em
``estado_pendencias.py``, que não depende do Sphinx.
"""

import re
from pathlib import Path

from sphinx.errors import ExtensionError

import estado_pendencias

MARCADOR = "@@pendencias-estado@@"
MARCADOR_PLACAR = "@@pendencias-placar@@"
# fora de código em linha: uma página pode citar o marcador entre crases sem ser substituída
_PLACAR_RE = re.compile(r"(?<!`)" + re.escape(MARCADOR_PLACAR) + r"(?!`)")
ARQUIVO = "estado_prontidao.json"
PAGINA = "projeto/pendencias"  # só esta página recebe o trecho completo


def _substituir(app, docname, source):
    completo = docname == PAGINA and MARCADOR in source[0]
    placar = bool(_PLACAR_RE.search(source[0]))
    if not completo and not placar:
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
    if completo:
        source[0] = source[0].replace(MARCADOR, estado_pendencias.gerar_markdown(dados))
    if placar:
        source[0] = _PLACAR_RE.sub(lambda _: estado_pendencias.gerar_placar_linha(dados), source[0])


def setup(app):
    app.connect("source-read", _substituir)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
