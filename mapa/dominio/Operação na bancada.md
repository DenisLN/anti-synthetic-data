---
tipo: dominio
tags: [dominio]
---
# Operação na bancada
- Roteiro por blocos: [[ROTEIRO_BANCADA]]; pendências físicas: [[docs/bancada_pendencias]]; passo a passo do operador: [[docs/guia-operador]].
- Referência: [[docs/operacao|operação]], [[docs/execucao_pendencias|execução das pendências]], [[docs/decisoes_pendentes|decisões pendentes]].
- Entrada: `scripts/START_BENCH.cmd` ([[mapa/codigo/scripts|scripts]]) -> [[mapa/codigo/cli|cli]]; preflights em [[mapa/codigo/preflight_new|preflight_new]] (`comm`, `trigger`, `lowvoltage`, `native`).
- Antes: git limpo, ligação física, fator da probe exato. Depois: confirmar `OUTPUT OFF` no painel.
- O que falhou (puladas, descartadas, inválidas, classes, orçamento TRACe esgotado) fica em `<sessao>/falhas.json`; `run falhas` repete só isso, com confirmação nova ([[docs/guia-operador]]).
- Ambiente: [[mapa/dominio/Bancada|Bancada]]; limites: [[mapa/dominio/Segurança e limites|Segurança e limites]]; fluxo: [[mapa/dominio/Fluxo de uma captura|Fluxo]].
