# Instrução para o Codex no computador Windows da bancada

O projeto deve estar em C:\Users\denis\TCC\code.

Não refatore o código, não troque portas, não altere limites e não rode testes
separados. A fonte e o osciloscópio já devem estar conectados assim:

- AMETEK MX30: porta USB da fonte, exposta pelo driver como PyVISA
  ASRL10::INSTR (COM10), 115200 baud confirmados no equipamento real.
- Keysight DSO-X 4034A:
  USB0::0x0957::0x17A4::MY59240844::0::INSTR.
- BNC: AMETEK Trigger Out -> Keysight EXT Trigger.
- O cabo USB da AMETEK deve permanecer conectado. Não usar simultaneamente o
  conector DB9 RS-232.

## Único comando

Abra um terminal como usuário normal:

    cd C:\Users\denis\TCC\code
    scripts\START_BENCH.cmd

O script cria o ambiente Python automaticamente se ele ainda não existir.
Depois faz internamente identificação, confirmação de OUTPUT OFF, trigger BNC,
aquisição de 6000 pontos, teste em 5 Vrms, validação dos comandos nativos da
AMETEK (STEP/PULSe/CSINe/LIST:FREQuency/ACDC) e do canal 2 do Keysight
(preflight_new.py --native-commands) e, por fim, uma captura de cada classe.

O operador terá de informar o fator exato da probe de tensão e digitar
ENERGIZAR/ENERGIZAR-5V/ENERGIZAR-COMANDOS conforme a etapa. Não invente o
fator e não automatize essas confirmações.

Se o script terminar com erro:

1. confirmar fisicamente OUTPUT OFF no painel da AMETEK;
2. não executar novamente de forma automática;
3. entregar ao usuário o arquivo mais recente de logs\startup-bench-*.log;
4. não remover validações de IDN, timeout, tamanho de waveform ou SCPI.

Captura de corrente permanece desligada. Não ativá-la sem fator da probe de
corrente e corrente-base fornecidos pelo usuário.
