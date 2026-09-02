# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

## [Não lançado]

### Corrigido
- `preflight_new.py --native-commands`: a etapa "PULSe nativo (SAG a 50%)" media
  RMS "fora da janela" errado porque o osciloscópio não estava configurado com
  `pre_trigger_s=DISTURBANCE_START_S` (como a classe SAG real,
  `experimentos_nativos/02.py`, faz). Sem esse pre-trigger, o PULSe da AMETEK —
  que cai imediatamente no `*TRG`, sem parâmetro de delay — caía em `t=0` do
  buffer, e a janela de comparação (que assume o distúrbio em
  `DISTURBANCE_START_S=0.060s`) recortava parte da própria queda de tensão como
  se fosse baseline. Resultado: RMS "fora" media ~113 V em vez de ~127 V, e o
  preflight falhava mesmo com o SAG correto no osciloscópio.
