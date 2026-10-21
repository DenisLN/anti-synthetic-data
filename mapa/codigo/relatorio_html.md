---
tipo: modulo
arquivo: logica/relatorio_html.py
camada: analise
linhas: 767
simbolos: [gerar_relatorio, gerar_relatorio_recortado, Captura, escolher_detalhes, figura_completa, tabela_metadados]
pendencias: ["[[P-15]]"]
tags: [codigo]
---
# relatorio_html
Gera um relatório HTML autocontido (figuras em base64) de uma sessão.
- **Faz:** Por captura: visão completa e até 3 detalhes; correlações vêm de `analisar_sessao`.
- Importa `matplotlib` e `analisar_sessao` tardiamente (ler o módulo não exige matplotlib).
- Modelo em `logica/modelos/relatorio_capturas.html`; padrão 3 capturas/classe/perfil (P-15).
- **Importa:** [[mapa/codigo/analisar_sessao|analisar_sessao]], [[mapa/codigo/recortar_margem|recortar_margem]], [[mapa/codigo/sessao_io|sessao_io]]. **Importado por:** [[mapa/codigo/cli|cli]].
Detalhe: [[docs/codigo/relatorio_html|guia completo]]
