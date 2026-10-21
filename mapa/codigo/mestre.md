---
tipo: modulo
arquivo: logica/mestre.py
camada: orquestracao
linhas: 3414
simbolos: [Bancada, Config, ExperimentoBase, ExperimentoNativo, ExperimentoWaveform, validate_bench_configuration, executar_bateria]
pendencias: ["[[P-03]]", "[[P-04]]", "[[P-06]]", "[[P-10]]", "[[P-12]]", "[[P-13]]", "[[P-18]]", "[[P-23]]"]
tags: [codigo]
---
# mestre
Orquestrador: único módulo que conhece os dois instrumentos e o que as 20 classes pedem.
- **Faz:** Lê o ambiente, valida a bancada, abre fonte e osciloscópio e executa a bateria de capturas por classe (`Bancada.executar_bateria`).
- Pré-valida pico, valida fisicamente (`_validar_fisicamente`), confere extremos e grava com `sessao_io`.
- Isola falhas de experimento; aborta tudo em `CommunicationError`/`FalhaFatalDeInstrumento` e chama `recuperar_estado_seguro()`.
- **Importa:** [[mapa/codigo/ametek_orm|ametek_orm]], [[mapa/codigo/bruto_osciloscopio_io|bruto_osciloscopio_io]], [[mapa/codigo/oscilloscope_orm|oscilloscope_orm]], [[mapa/codigo/perfis|perfis]], [[mapa/codigo/politica_traces|politica_traces]], [[mapa/codigo/sessao_io|sessao_io]], [[mapa/codigo/sinais|sinais]]. **Importado por:** [[mapa/codigo/cli|cli]], [[mapa/codigo/preflight_new|preflight_new]].
> [!danger] Limites
> - `AMETEK_PORT=COM10`/`AMETEK_BAUDRATE=115200` validados em `validate_bench_configuration()`; não trocar nem remover.
> - Não ampliar o que é 'falha de experimento recuperável'; abortar sem retry em falha de comunicação/fatal.
Detalhe: [[docs/codigo/mestre|guia completo]]
