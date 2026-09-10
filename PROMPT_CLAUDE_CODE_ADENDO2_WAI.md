# Adendo 2 — achei o mecanismo mais provável: `*WAI`, não polling de registrador

Continuando o adendo anterior (`PROMPT_CLAUDE_CODE_ADENDO_OPC.md`): fui
ver a seção 7.7 "SCPI Command Completion" (p.173 do manual, logo depois
do que eu já tinha lido) e tem uma informação que muda a prioridade de
teste.

## O que a p.173 diz

Primeiro parágrafo da seção: comandos SCPI na fonte são processados
**sequencial ou paralelamente**. Comandos sequenciais terminam antes do
próximo começar; comandos paralelos deixam a fonte aceitar o próximo
comando enquanto ainda processa o anterior — e o manual cita
explicitamente **"commands that affect list and trigger actions,
measurements and calibration"** como parte dos comandos paralelos. Isso
bate exatamente com o sintoma: `TRACe:DEFine`, `FUNCtion:SHAPe` e
`SOURce:MODE` (os três lugares onde o projeto já precisou de
`aguardar_resposta()`) são desse tipo — a fonte aceita o comando e
continua "mastigando" em paralelo, e é aí que um comando seguinte chega
cedo demais.

A tabela logo depois lista três formas de esperar isso terminar:

| Comando | O que faz |
|---|---|
| `*WAI` | Impede a fonte de processar comandos SEGUINTES até que todas as operações pendentes terminem — **exceto transientes**. |
| `*OPC?` | Só responde "1" quando tudo termina (é o que já sabemos que não funciona nesta Rev. 5.53 — não responde nada). |
| `*OPC` | Seta o bit de status quando termina; dá pra checar depois via `*ESR?` (o que já propus no adendo 1). |

## Por que isso muda a ordem de teste

`*WAI` é estruturalmente diferente de `*OPC?`: não é uma query que
espera uma resposta específica da fonte (isso é o que travou com
`*OPC?` — a Rev. 5.53 simplesmente não respondeu nada). `*WAI` é só um
comando — ele não exige que a fonte devolva nada, só que ela **não
processe o próximo comando da fila até estar pronta**. Isso tem bem
menos chance de esbarrar no mesmo bug de firmware que já derrubou
`*OPC?`, porque não depende do canal de resposta funcionar — só do
sequenciador interno de comandos, que aparentemente já funciona (é
literalmente o que causa o problema: comandos paralelos sendo aceitos
fora de ordem).

A ressalva "except for transients" é relevante: `TRACe:DEFine`
(gravação de forma na Flash) e `FUNCtion:SHAPe`/`SOURce:MODE`
(reconfiguração) não são "transientes" no sentido do manual — transiente
aqui é o evento de trigger/PULSe/STEP disparado por `*TRG` /
`INITiate:IMMediate`. Então `*WAI` deveria cobrir exatamente os três
pontos que hoje usam `aguardar_resposta()`, mas **não substitui** o
polling de `TRIGger:STATe?` que já existe em `arm()`/`wait_transient_complete()`
para saber se um transiente terminou — aquilo continua sendo o
mecanismo certo pra depois do `*TRG`.

## Peço pra incluir isso no teste

No mesmo teste isolado do adendo 1 (na bancada real, com
`SOURce:FUNCtion:SHAPe CSINusoid` como o comando "lento" de referência),
adicione `*WAI` como PRIMEIRA alternativa a testar, antes de `*ESR?`
e `STAT:OPER:COND?`:

1. Manda o comando lento, manda `*WAI` logo em seguida (sem esperar
   nada — é comando, não query), e só depois tenta o próximo comando
   real (ex.: `VOLTage:MODE STEP` do `trigger_step()`). Mede se isso já
   evita o erro sozinho, e quanto tempo o `write("*WAI")` propriamente
   leva para retornar (o driver PyVISA pode ou não bloquear aí — vale
   cronometrar).
2. Se `*WAI` sozinho resolver: é a solução mais simples e mais barata
   das três, sem loop de polling nenhum — prefira essa em vez de
   `*ESR?`/`STAT:OPER:COND?` do adendo anterior, e simplifique
   `aguardar_resposta()`/os call sites (`configure_harmonics_csine()`,
   `SOURce:MODE ACDC`, `program_capture()`) para usar `*WAI` em vez do
   loop de `*IDN?`.
3. Se `*WAI` também ficar mudo/travar (mesma falha do `*OPC?`), documente
   isso também e siga para os testes de `*ESR?`/`STAT:OPER:COND?` do
   adendo 1 normalmente.
4. Continua valendo: isso é melhoria de robustez, não bloqueia rodar a
   bateria hoje com o mecanismo atual (`*IDN?`) se não sobrar tempo para
   testar as três opções.
