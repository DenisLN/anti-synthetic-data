---
tipo: modulo
arquivo: logica/ametek_orm.py
camada: instrumento
linhas: 2133
simbolos: [AmetekMX30, ProgramacaoCaptura, montar_programacao, program_capture, ParameterOutOfBoundsError, FalhaFatalDeInstrumento, CommunicationError]
pendencias: ["[[P-04]]", "[[P-18]]", "[[P-23]]"]
tags: [codigo]
---
# ametek_orm
Driver SCPI da fonte AMETEK MX30-3Pi (serial COM10) com validação prévia, sincronismo e modo simulado.
- **Faz:** Traduz métodos Python em SCPI: valida antes, sincroniza (`*OPC`/`*WAI`) e confere a fila de erros depois de cada comando.
- Monta de forma pura (`montar_programacao`) o que será programado numa captura TRACe/LIST (`ProgramacaoCaptura`).
- Mantém o modelo de estado da fonte (modo, forma, frequência base); recusa offline RMS/pico/frequência inválidos (P-04); orçamento de 216 gravações TRACe por conexão (P-23); passo final SINE experimental, OFF (P-18).
- **Importa:** [[mapa/codigo/politica_traces|politica_traces]]. **Importado por:** [[mapa/codigo/mestre|mestre]].
> [!danger] Limites
> - `COM10`/115200 fixos; não remover validações de IDN, timeout, 6000 pontos, `assert_no_errors`/`check_errors`.
> - Não alterar `max_voltage_rms`, `max_peak_v`, `max_current_a` nem `ParameterOutOfBoundsError`.
> - Saída só energiza com confirmação digitada do operador.
Detalhe: [[docs/codigo/ametek_orm|guia completo]]
