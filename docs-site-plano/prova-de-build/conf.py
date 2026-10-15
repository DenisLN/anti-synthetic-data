"""Configuração mínima da prova de build do site (spec 06). Não é o site final."""

project = "ASD Docs (prova de build)"
author = "Projeto ASD"
language = "pt_BR"

extensions = [
    "myst_parser",
    "sphinx_design",
    "sphinxcontrib.mermaid",
]

myst_enable_extensions = ["colon_fence", "dollarmath", "amsmath", "deflist", "attrs_inline"]
myst_heading_anchors = 3

html_theme = "furo"
html_title = "ASD Docs"
html_theme_options = {"source_repository": "https://github.com/DenisLN/anti-synthetic-data/", "source_branch": "main"}

# Diagramas: o Mermaid é desenhado no navegador (JavaScript), sem Node nem Chromium no build.
mermaid_output_format = "raw"

suppress_warnings = []
exclude_patterns = ["_build"]
