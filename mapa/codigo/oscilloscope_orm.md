---
tipo: modulo
arquivo: logica/oscilloscope_orm.py
camada: instrumento
linhas: 581
simbolos: [KeysightDSOX4034A, OscChannel, OscilloscopeError, get_waveform, set_vertical_scale, wait_for_trigger_complete]
pendencias: ["[[P-28]]"]
tags: [codigo]
---
# oscilloscope_orm
Driver (PyMeasure) do osciloscópio Keysight DSO-X 4034A: aquisição, trigger e download validado da forma de onda.
- **Faz:** Garante janela de tempo pedida (6000/8100 pontos a 30 kSa/s), posição real do trigger, sem buracos nem clipping vertical.
- Extremos de segurança vêm do registro bruto medido pelo próprio instrumento.
- `get_waveform` expõe BYTE/preamble para a preservação do bruto (P-28, ver [[mapa/codigo/bruto_osciloscopio_io|bruto_osciloscopio_io]]).
- **Importa:** nenhum módulo do projeto. **Importado por:** [[mapa/codigo/mestre|mestre]].
> [!danger] Limites
> - Não enfraquecer validações de timeout, tamanho de waveform (6000 pontos) nem erros SCPI.
Detalhe: [[docs/codigo/oscilloscope_orm|guia completo]]
