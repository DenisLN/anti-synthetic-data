"""Configuração do site de documentação do ASD (Sphinx + MyST + Furo).

O código-fonte do projeto fica em ``../logica`` e nunca é importado aqui: as
páginas incluem trechos por ``literalinclude`` e citam ``arquivo:linha``.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath("_ext"))


def _commit_curto():
    """Commit curto do checkout (carimbo no rodapé); vazio se não houver git."""
    try:
        saida = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return saida.stdout.strip() if saida.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


_commit = _commit_curto()

project = "ASD: dataset sintético com bancada física"
author = "Projeto ASD"
release = "v1.15 (em andamento, sem tag)"
copyright = "Documentação do código da v1.15" + (f", commit {_commit}" if _commit else "")
language = "pt_BR"

extensions = [
    "myst_parser",
    "sphinx_design",
    "sphinxcontrib.mermaid",
    "scpi",
]

source_suffix = {".md": "markdown"}
root_doc = "index"

myst_enable_extensions = ["colon_fence", "dollarmath", "amsmath", "deflist", "attrs_inline"]
myst_heading_anchors = 4

# Os PDFs/manuais em texto, o build e artefatos brutos gerados em evidencias/
# não são páginas do site; páginas de síntese podem ligar aos resultados.
exclude_patterns = ["_build", "manuais_txt", "*.pdf", "requirements.txt", "evidencias/**"]

html_theme = "furo"
html_title = "ASD Docs"
html_static_path = ["_static"]
html_css_files = ["asd.css"]
html_theme_options = {
    "source_repository": "https://github.com/DenisLN/anti-synthetic-data/",
    "source_branch": "main",
    "source_directory": "docs/",
}

# Diagramas Mermaid são desenhados no navegador (JavaScript), sem Node no build.
mermaid_output_format = "raw"

# Sem supressão de avisos: o build roda com -W.
suppress_warnings = []


# Três links relativos quebrados em CHANGELOG/v1.0.md e v1.2.md (apontam para
# ``../ametek_orm.py`` etc., caminhos que nunca existiram a partir de CHANGELOG/).
# Os changelogs fechados não se reescrevem (AGENTS.md), então só esses três
# avisos exatos são ignorados; qualquer outro link quebrado continua falhando o -W.
_LINKS_QUEBRADOS_DO_CHANGELOG = (
    "'../ametek_orm.py'",
    "'../oscilloscope_orm.py'",
    "'../mestre.py'",
)


def _ignorar_links_do_changelog(record):
    if getattr(record, "subtype", None) != "xref_missing":
        return True
    texto = record.getMessage()
    return not any(alvo in texto for alvo in _LINKS_QUEBRADOS_DO_CHANGELOG)


class _FiltroLinksDoChangelog:
    def filter(self, record):
        return _ignorar_links_do_changelog(record)


def setup(app):
    import logging

    # Entra antes dos filtros do Sphinx (contagem de avisos e -W).
    for handler in logging.getLogger("sphinx").handlers:
        if handler.level == logging.WARNING:
            handler.filters.insert(0, _FiltroLinksDoChangelog())
