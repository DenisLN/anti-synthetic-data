---
tipo: modulo
arquivo: logica/perfis.py
camada: utilitario
linhas: 250
simbolos: [FAIXAS, FAIXAS_SORTEADAS, PERFIS, faixa, nivel, composto, plano_de_perfis]
pendencias: ["[[P-11]]"]
tags: [codigo]
---
# perfis
Fonte única das faixas por perfil (`norma`, `literatura`, `fronteira`).
- **Faz:** `FAIXAS`: 11 componentes x 3 perfis; `FAIXAS_SORTEADAS` para as compostas.
- Perfil ativo vem de `Config.perfil`; `literatura` (padrão) reproduz byte a byte o `gerar()` do commit `34a0d82`.
- Extensões das compostas 10-16 mantidas (P-11).
- **Importa:** nenhum módulo do projeto. **Importado por:** [[mapa/codigo/cli|cli]], [[mapa/codigo/mestre|mestre]].
Detalhe: [[docs/codigo/perfis|guia completo]]
