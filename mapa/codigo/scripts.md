---
tipo: modulo
arquivo: scripts/
camada: utilitario
linhas: 6878
simbolos: [recalibrar_extremos, diag_marcadores_trace, fechar_pendencias, verificar_prontidao, planejar_campanhas, START_BENCH.cmd]
pendencias: ["[[P-02]]", "[[P-16]]", "[[P-17]]", "[[P-22]]", "[[P-28]]", "[[P-31]]"]
tags: [codigo]
---
# scripts
Utilitários fora de `logica/`, agrupados por função.
- **Visita num comando:** `VISITA_BANCADA.cmd` -> `visita_bancada_windows.ps1` -> `visita_bancada.py`. Conduz todos os blocos e as cinco condições, chamando [[mapa/codigo/cli|cli]] em modo roteiro (`--comando`); o operador digita as confirmações; retoma de onde parou (`logs/visita_<id>/estado.json`).
- **Windows (entrada/ambiente):** `START_BENCH.cmd` -> `start_bench_windows.ps1` (pergunta fator da probe, tensão, frequência; recusa >270 V), `bench_config.ps1`, `setup_windows.ps1`, `run_simulation_windows.ps1`, `package_windows.ps1`, `validar_pc_bancada.ps1` (P-16).
- **Diagnóstico de bancada:** `diag_marcadores_trace` (energiza, P-02), `diag_acdc_amplitude` (energiza, P-17), `diag_saida_vs_medida`, `diag_fonte_vs_osciloscopio`, `diag_nativo_output_off` (nunca envia `OUTPut ON`), `diag_osciloscopio_canais`, `diag_ciclos_trace` (offline), `teste_passo_final_sin` (P-18).
- **Análise offline:** `analisar_modelo_programado` (P-09/P-12/P-31), `analisar_reamostragem` (P-28), `benchmark_sessao_io` (P-22), `verificar_sessao_bancada`, `gerar_tres_versoes`, `gerar_ruido_janela`, `relatorio_limites_bancada`.
- **Fechamento/planejamento:** `fechar_pendencias` (agrega evidência P-01..P-31), `verificar_prontidao` (gate de encerramento), `planejar_campanhas` (grupos <=216 gravações TRACe), `recalibrar_extremos` (fatores de extremo, ver [[docs/medicao/recalibracao|recalibração]]).
- **Depende de / usado por:** importam [[mapa/codigo/mestre|mestre]], [[mapa/codigo/ametek_orm|ametek_orm]], [[mapa/codigo/sessao_io|sessao_io]], [[mapa/codigo/analisar_sessao|analisar_sessao]]; `diag_marcadores_trace` usa [[mapa/codigo/modelo_lista_fonte|modelo_lista_fonte]]; `START_BENCH` chama [[mapa/codigo/cli|cli]].
> [!danger] Limites
> Scripts que energizam pedem token digitado (`ENERGIZAR-50V`, `ENERGIZAR-127V`, `ENERGIZAR-MARCADORES`, `ENERGIZAR-ACDC`); `diag_*` com PyVISA cru não passam pelas validações do ORM; fechar o MX GUI (segura a COM10).
Detalhe: [[docs/codigo/scripts|guia completo]]
