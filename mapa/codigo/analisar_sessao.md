---
tipo: modulo
arquivo: logica/analisar_sessao.py
camada: analise
linhas: 360
simbolos: [analisar_sessao, analisar_offset, _ConfigOffline, _reconstruir_esperado, _correlacao_disturbio_alinhada]
pendencias: []
tags: [codigo]
---
# analisar_sessao
Análise offline: reconstrói a forma esperada e correlaciona com a medida de bancada.
- **Faz:** Recria `gerar()` com seed/parâmetros do metadata (e redução de bancada, se houve).
- Alinha por correlação cruzada (FFT): `lag`, correlação total e correlação do distúrbio.
- Executado nas três sessões de 07/10/2026 ([[docs/medicao/correlacao|medição]]).
- **Importa:** [[mapa/codigo/sessao_io|sessao_io]], [[mapa/codigo/sinais|sinais]]. **Importado por:** [[mapa/codigo/relatorio_html|relatorio_html]].
Detalhe: [[docs/codigo/analisar_sessao|guia completo]]
