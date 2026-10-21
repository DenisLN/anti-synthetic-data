---
tipo: modulo
arquivo: logica/preflight_new.py
camada: orquestracao
linhas: 806
simbolos: [run_basic_stage, run_native_commands, run_list_diagnostics, ToleranciaExcedida, RMS_TOLERANCE_V, main]
pendencias: []
tags: [codigo]
---
# preflight_new
Preflights em níveis (`comm`, `trigger`, `lowvoltage`, `native`) que provam a cadeia antes de uma campanha.
- **Faz:** `comm`: comunicação e `OUTPUT OFF`; `trigger`: aquisição/download Keysight (não testa o BNC).
- `lowvoltage`: cadeia inteira na tensão base digitada (BNC, 6000 pontos, rms ±10 %); pede `ENERGIZAR-TESTE`.
- `native`: STEP, PULSe, CSINusoid, lista de frequência, ACDC e `MEASure:*`.
- **Importa:** [[mapa/codigo/mestre|mestre]], [[mapa/codigo/sinais|sinais]]. **Importado por:** [[mapa/codigo/cli|cli]].
> [!danger] Limites
> - Estágios que energizam exigem confirmação digitada do operador.
Detalhe: [[docs/codigo/preflight_new|guia completo]]
