---
tipo: modulo
arquivo: logica/recortar_margem.py
camada: analise
linhas: 301
simbolos: [recortar_sessao, calcular_recorte, metadado_recortado, carregar_metadados, diretorios_de_dados]
pendencias: []
tags: [codigo]
---
# recortar_margem
Remove a folga de 20 ms/50 ms e entrega só a janela nominal de 6000 amostras em pasta nova.
- **Faz:** Saída em `<sessao>/sem_margem/` com a estrutura de uma sessão (formato 2, `snr_XXdb/`, `corrente/`, metadata).
- Compatível com `analisar_sessao` e `relatorio_html`; não altera a sessão original.
- **Importa:** [[mapa/codigo/sessao_io|sessao_io]], [[mapa/codigo/sinais|sinais]]. **Importado por:** [[mapa/codigo/relatorio_html|relatorio_html]].
Detalhe: [[docs/codigo/recortar_margem|guia completo]]
