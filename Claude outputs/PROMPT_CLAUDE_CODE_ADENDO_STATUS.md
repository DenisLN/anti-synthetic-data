# Adendo — comando de conclusão de operação em vez do timer/polling atual

Antes de mais nada: `aguardar_resposta()` (`logica/ametek_orm.py`,
linha ~628) já é espera determinística por polling, não um `sleep` no
chute — ela repete `*IDN?` até a fonte responder de novo. A pergunta é
se dá pra trocar isso por algo mais direto, baseado no que a fonte
realmente expõe pra "operação pendente terminou".

## O que já foi tentado e falhou (ler antes de mexer)

Em `wait_ready()` (linha ~657-664), o docstring já documenta: a
MX30-3Pi Rev. 5.53 responde a `*IDN?` mas **não respondeu a `*OPC?`**
(a query de sincronização do IEEE-488.2) mesmo com o EOT exigido pelo
protocolo. É por isso que o projeto usa `*IDN?` como proxy hoje — não
foi preferência, foi o que sobrou depois do jeito "certo" falhar nesse
firmware.

## O que a seção 7 do manual (p.167-173) mostra, em ordem de prioridade de teste

A seção 7.7 "SCPI Command Completion" (p.173) explica o próprio
mecanismo do bug: comandos SCPI na fonte são sequenciais ou
**paralelos**, e cita explicitamente "commands that affect list and
trigger actions, measurements and calibration" como paralelos — ou
seja, `TRACe:DEFine`, `FUNCtion:SHAPe` e `SOURce:MODE` (os três pontos
que hoje usam `aguardar_resposta()`) são aceitos pela fonte e continuam
processando EM PARALELO com o que vem depois. É exatamente aí que o
próximo comando chega cedo demais e gera o erro.

A mesma seção lista três formas de esperar isso terminar. Teste NESSA
ordem, porque cada uma tem uma razão pra ser mais ou menos provável de
funcionar dado que `*OPC?` já falhou:

1. **`*WAI`** (comando, sem `?`) — impede a fonte de processar o
   PRÓXIMO comando até que operações pendentes terminem, **exceto
   transientes**. É estruturalmente diferente de `*OPC?`: não exige que
   a fonte devolva nenhuma resposta (é isso que travou no `*OPC?`), só
   depende do sequenciador interno de comandos — que aparentemente já
   funciona, é o que está causando o bug. Teste primeiro por ser o mais
   simples e o menos provável de repetir a falha do `*OPC?`. A ressalva
   "except for transients" é ok pro nosso caso: `TRACe:DEFine`/
   `FUNCtion:SHAPe`/`SOURce:MODE` não são "transiente" no sentido do
   manual (transiente = evento de `*TRG`/`INITiate:IMMediate`), então
   `*WAI` deveria cobrir os três pontos problemáticos sem interferir no
   polling de `TRIGger:STATe?` que já existe em `arm()`/
   `wait_transient_complete()` pra saber se um transiente terminou —
   aquele mecanismo continua sendo o certo depois do `*TRG`, não mexer
   nele.
2. **`*OPC` (comando) + `*ESR?` depois, em loop tolerante.** `*OPC`
   seta o bit 0 (OPC) do Standard Event Status quando a operação
   termina; `*ESR?` só lê esse registrador (limpa ao ler) — uma query
   comum, não a sincronização bloqueante que já falhou. Dá pra
   reaproveitar `_query_tolerante()` num loop igual ao que já existe
   para `TRIGger:STATe?`.
3. **`STAT:OPER:COND?`** (Operation Status Condition, tabela 7-2,
   p.169): bit 3 = TRANS ("Transient is completed"), bit 4 = MEAS
   ("Measurement is completed"). Registrador de tempo real (não trava
   ao ler), pensado pra "a fonte ainda está processando algo" —
   conceitualmente o mais preciso dos três, mas teste por último porque
   é o mais distante do que já sabemos que funciona nesse firmware.

## O que pedir para o Claude Code fazer

1. Na bancada real (fonte já conectada), escrever um teste isolado e
   descartável (não precisa virar parte do preflight) que manda
   `SOURce:FUNCtion:SHAPe CSINusoid` (o comando "lento" de referência,
   já sabidamente problemático) e testa as três opções acima NESSA
   ordem, cronometrando cada uma e registrando se ela evita o erro
   -113 que hoje só aparece depois, dentro de `arm()`.
2. Assim que uma funcionar de forma confiável (repita o teste pelo
   menos 3x seguidas pra garantir que não é coincidência), pare aí — não
   precisa testar as outras duas. Troque o(s) call site(s) relevante(s)
   (`configure_harmonics_csine()`, o `SOURce:MODE ACDC` em
   `enable_dc_offset()` ou nome equivalente, e possivelmente
   `program_capture()`) para usar essa opção em vez de
   `aguardar_resposta()`. Mantenha `aguardar_resposta(*IDN?)` como
   fallback documentado se nenhuma das três responder — não tire a rede
   de segurança que já existe.
3. Se as três falharem do mesmo jeito que `*OPC?`, documente isso no
   comentário de `wait_ready()`/`aguardar_resposta()`, do mesmo jeito
   que já documentaram a falha do `*OPC?`, pra ninguém perder tempo
   testando de novo depois.
4. Isso é independente da correção da Prioridade 0 do prompt principal
   (adicionar `aguardar_resposta()` depois do segundo write em
   `configure_harmonics_csine()`) — resolva a Prioridade 0 primeiro com
   o mecanismo que já existe (`*IDN?`), porque ela é o que está
   bloqueando a bateria agora. Isso aqui é melhoria de robustez/
   velocidade em cima disso, não precisa travar o resto se o tempo
   apertar.
