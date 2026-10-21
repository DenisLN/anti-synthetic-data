---
tipo: modulo
arquivo: logica/sinais.py
camada: utilitario
linhas: 683
simbolos: [tempo, janela, aplicar_entalhes, oscilacao_amortecida, ruido_na_janela, thd_medida, janela_nominal, comparar_fisicamente]
pendencias: ["[[P-10]]"]
tags: [codigo]
---
# sinais
Matemática de sinal pura (array entra, array ou número sai), sem importar nada do projeto.
- **Faz:** Constrói componentes das classes: entalhes, oscilação amortecida, harmônicos, senoide clipada (05).
- Ruído com SNR por construção só na janela rotulada; semente do ruído determinística.
- Validação física (envelope, THD, crista) e janela nominal de 6000 amostras.
- **Importa:** nenhum módulo do projeto. **Importado por:** [[mapa/codigo/analisar_sessao|analisar_sessao]], [[mapa/codigo/mestre|mestre]], [[mapa/codigo/preflight_new|preflight_new]], [[mapa/codigo/recortar_margem|recortar_margem]].
Detalhe: [[docs/codigo/sinais|guia completo]]
