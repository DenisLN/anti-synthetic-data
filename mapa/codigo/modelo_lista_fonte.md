---
tipo: modulo
arquivo: logica/modelo_lista_fonte.py
camada: analise
linhas: 209
simbolos: [prever_forma, confrontar, HIPOTESES_CANDIDATAS]
pendencias: ["[[P-02]]"]
tags: [codigo]
---
# modelo_lista_fonte
Hipóteses (NÃO VERIFICADAS) sobre o que a fonte toca num LIST, para o evento repetido em 100 ms das classes 08/09.
- **Faz:** Cada hipótese é função pura: dada uma `ProgramacaoCaptura`, devolve a forma que a fonte emitiria se fosse verdade.
- `confrontar` compara com o medido por `scripts/diag_marcadores_trace.py` (quirks A22/A25).
- **Importa:** nenhum módulo do projeto. **Importado por:** nenhum módulo do projeto.
> [!danger] Limites
> - Nada neste módulo é fato sobre o equipamento; valores numéricos são chutes de partida.
Detalhe: [[docs/codigo/modelo_lista_fonte|guia completo]]
