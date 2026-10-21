---
tipo: modulo
arquivo: logica/politica_traces.py
camada: utilitario
linhas: 7
simbolos: [LIMITE_ESCRITAS_TRACE_CONEXAO, LimiteEscritasTraceError]
pendencias: ["[[P-23]]"]
tags: [codigo]
---
# politica_traces
Constante e exceção do orçamento operacional de 216 gravações TRACe por conexão.
- **Faz:** `LIMITE_ESCRITAS_TRACE_CONEXAO = 216`: conservador, não é limite do fabricante.
- `LimiteEscritasTraceError`: sem orçamento, abortar a campanha sem retry.
- **Importa:** nenhum módulo do projeto. **Importado por:** [[mapa/codigo/ametek_orm|ametek_orm]], [[mapa/codigo/mestre|mestre]].
> [!danger] Limites
> - Esgotamento do orçamento aborta a bateria; não contornar nem aumentar o limite.
Detalhe: sem guia em docs/codigo; ver docstrings do módulo.
