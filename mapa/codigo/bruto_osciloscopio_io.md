---
tipo: modulo
arquivo: logica/bruto_osciloscopio_io.py
camada: persistencia
linhas: 79
simbolos: [salvar_bruto, sha256_array]
pendencias: ["[[P-28]]"]
tags: [codigo]
---
# bruto_osciloscopio_io
Preserva a exportação BYTE do osciloscópio em arquivo independente, sem modificar o dataset.
- **Faz:** `salvar_bruto` grava BYTE/preamble/tempos antes da interpolação, vinculado à captura por `id_captura` e hash.
- `sha256_array` hasheia float64 little-endian contíguo; a análise de P-28 casa esse SHA-256.
- Ativado por `set diagnostico bruto on` / `SALVAR_BRUTO_OSCILOSCOPIO=1`.
- **Importa:** nenhum módulo do projeto. **Importado por:** [[mapa/codigo/mestre|mestre]].
Detalhe: sem guia em docs/codigo; ver docstrings do módulo.
