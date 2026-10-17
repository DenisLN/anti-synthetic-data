# AMETEK: identificação, erros e estado

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` {bdg-success}`VERIFICADO NA BANCADA`

**Pergunta:** como o projeto abre a conexão com a fonte, espera cada comando ser consumido e lê o estado? **Resposta:** a conexão começa por `OUTPut:STATe OFF`, confere o `*IDN?`, e cada escrita seguinte termina com um `*ESR?` que força a fonte a processar o comando antes do próximo; o estado do sistema de trigger é lido por `TRIGger:STATe?` e os erros por `SYSTem:ERRor?`.

Convenções da referência: ver {doc}`../scpi`. Os exemplos reais vêm das transcrições de 07/10/2026 (premissa: trechos de até cinco linhas por comando, sem versionar os arquivos de log).

(scpi-idn)=

## `*IDN?`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Devolve a identificação do instrumento; o código aborta a conexão se o modelo esperado não estiver contido na resposta.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `*IDN?` devolve `<fabricante>,<modelo>,<série>,<revisão>`
- **Parâmetros e unidades:** Sem parâmetros. O modelo esperado vem de `AMETEK_EXPECTED_MODEL` (padrão `MX30`); a comparação ignora tudo que não é letra ou algarismo e a caixa.
- **Sincronismo e ordem:** É a primeira consulta da conexão e vem logo depois de `OUTPut:STATe OFF`, que é enviado por `_raw_write` (sem `*ESR?`, porque o sincronismo de `write()` ainda não vale: a conexão está abrindo). Não use `*IDN?` para esperar a fonte voltar depois de trocar forma ou modo: `aguardar_resposta` o faz, mas ficou como recurso reserva desde que `*WAI` o substituiu.
- **Erros e quirks:** Modelo diferente: `CommunicationError` ("Instrumento inesperado"). Sem resposta no prazo de 5 s: `CommunicationError` com a lista de conferência (COM10, driver, 115200 baud, cabo).
- **Quem envia:** `AmetekMX30.connect` ([ametek_orm.py:351](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L351))
- **Manual:** p. 136 (seção 5.4); lista de comandos comuns na p. 133.
- **Classes que usam:** todas (abertura da conexão)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 1; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:47.738] t=7513.171000 W OUTPut:STATe OFF
  [15:56:47.738] t=7513.171000 Q *IDN?
  [15:56:47.767] t=7513.187000 W *IDN?
  [15:56:47.774] t=7513.203000 R *IDN? -> "CALIFORNIA INSTRUMENTS,MX30-3Pi,1921A03213,Rev 5.53"
  ```

(scpi-cls)=

## `*CLS`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Limpa a fila de erros SCPI e os registradores de eventos.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `*CLS` (sem resposta)
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** Como todo `write()`, vem seguido de `*ESR?`. Em `program_capture`, depois de cada `TRACe:DATA` o código espera 1 s e só então manda `*CLS`: a fonte não pode ser consultada logo após a gravação ({scpi}`TRACe:DATA`), e o `*CLS` desse ponto vai com a fonte já assentada.
- **Erros e quirks:** Sem erro conhecido. Não limpa a causa de um erro, só o registro dele: por isso `check_errors` roda antes do próximo passo, não depois do `*CLS`.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1256](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1256)); `AmetekMX30.program_capture` (início) ([ametek_orm.py:1549](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1549)); `AmetekMX30.program_capture` (depois de cada TRACe) ([ametek_orm.py:1616](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1616))
- **Manual:** p. 134.
- **Classes que usam:** todas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 9; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:47.821] t=7513.250000 W *CLS
  [15:56:47.855] t=7513.281000 R *ESR? -> 0
  ```

(scpi-esr)=

## `*ESR?`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Devolve e zera o Standard Event Status Register; é o comando que o projeto usa para **esperar a fonte consumir cada escrita**.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `*ESR?` devolve um inteiro de 0 a 255
- **Parâmetros e unidades:** Sem parâmetros. O código trata os bits 0x04 (QYE), 0x08 (DDE), 0x10 (EXE) e 0x20 (CME) como erro e só registra aviso com o comando que o causou (`_ESR_BITS_DE_ERRO`, [ametek_orm.py:184](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L184)); a fila `SYSTem:ERRor?` fica intacta.
- **Sincronismo e ordem:** Cada `write()` termina com uma consulta `*ESR?` (`_sincronizar_apos`). A USB virtual serial da fonte não tem controle de fluxo (`VI_ASRL_FLOW_NONE`) e uma rajada de comandos se perde em silêncio: a rajada de quatro comandos pegou 0 de 3 vezes sem consulta, e 9 de 9 com uma consulta depois de cada um (quirk A1, bancada de 30/09/2026). A fonte só responde depois de processar tudo o que veio antes, então o comando seguinte nunca sai com o anterior pendente. Exceção: `TRACe:DATA`, `TRACe:DEFine` e `TRACe:DELete` (`_SEM_SINCRONISMO`, [ametek_orm.py:177](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L177)), porque consultar a fonte durante a gravação em Flash a deixa muda (A2). Prazo de 20 s (`PRAZO_SINCRONISMO_S`); a mudez transitória depois de trocar forma ou modo não derruba a bateria.
- **Erros e quirks:** Resposta não numérica: aviso e segue. Sem resposta em 20 s: `CommunicationError`.
- **Quem envia:** `AmetekMX30.write` ([ametek_orm.py:449](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L449)); `AmetekMX30._sincronizar_apos` ([ametek_orm.py:454](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L454))
- **Manual:** p. 135 (seção 5.3); lista de comandos comuns na p. 133.
- **Classes que usam:** todas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 5; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:47.776] t=7513.203000 W OUTPut:STATe OFF
  [15:56:47.776] t=7513.203000 Q *ESR?
  [15:56:47.820] t=7513.250000 W *ESR?
  [15:56:47.821] t=7513.250000 R *ESR? -> 0
  ```

(scpi-opc)=

## `*OPC?`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código; nenhuma sessão de 07/10 o exerceu.

**O que faz?** **Devolve `1` quando as operações pendentes terminaram; no projeto é só a alternativa a `*ESR?` quando `AMETEK_SINCRONISMO=OPC`.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `*OPC?` devolve `1` (ou `0` com operação pendente)
- **Parâmetros e unidades:** Sem parâmetros. Seleção por variável de ambiente: `AMETEK_SINCRONISMO` aceita `ESR` (padrão) ou `OPC`.
- **Sincronismo e ordem:** **A Rev. 5.53 não segura a resposta** como o IEEE 488.2 manda: responde na hora `1` (nada pendente) ou `0` (por exemplo, um STEP armado depois de `INITiate:IMMediate`). Não trava, mas não sincroniza mais do que {scpi}`*ESR?`, e todo `arm()` logaria "devolveu '0'" (quirk A17, bancada de 30/09/2026, ensaio T15).
- **Erros e quirks:** Resposta diferente de `1` em modo `OPC`: aviso.
- **Quem envia:** `AmetekMX30._sincronizar_apos` ([ametek_orm.py:454](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L454))
- **Manual:** p. 136; comparação dos três modos de esperar nas pp. 173-174.
- **Classes que usam:** nenhuma (modo não usado na bancada)

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (nenhuma sessão de 07/10 exerceu este comando).

  ```text
  Q *OPC?
  R *OPC? -> 1      (resposta que o código espera; a Rev. 5.53 responde na hora)
  ```

(scpi-wai)=

## `*WAI`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Bloqueia o processamento do comando seguinte até as operações paralelas pendentes (lista e trigger) terminarem.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `*WAI` (sem resposta)
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** A Rev. 5.53 processa em paralelo os comandos que afetam lista e trigger; trocar a forma de onda recarrega a tabela e deixa a fonte muda por alguns segundos (A7). O projeto manda `*WAI` depois de {scpi}`SOURce:FUNCtion:SHAPe`, de {scpi}`SOURce:FUNCtion:SHAPe:CSINusoid`, de {scpi}`SOURce:MODE ACDC` e antes de {scpi}`INITiate:IMMediate`. Validado na bancada em 3 de 3, com 15 a 47 ms, contra vários segundos do polling por `*IDN?` que ele substituiu. Como o manual diz (p. 142) que "*WAI can be aborted by sending any other command", só funciona porque o `write()` seguinte espera `*ESR?`: nada é enviado antes de a espera terminar.
- **Erros e quirks:** Sem erro próprio; um erro da operação esperada aparece na fila e é conferido por `assert_no_errors` logo depois.
- **Quem envia:** `AmetekMX30.configure_harmonics_csine` ([ametek_orm.py:975](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L975)); `AmetekMX30.select_sine_shape` ([ametek_orm.py:1009](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1009)); `AmetekMX30.enable_dc_offset` ([ametek_orm.py:1131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1131)); `AmetekMX30.arm` ([ametek_orm.py:1736](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1736)); `AmetekMX30.arm_transient` ([ametek_orm.py:1884](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1884))
- **Manual:** p. 142.
- **Classes que usam:** 05 (CSINusoid), 19 (ACDC), todas as nativas e as de lista (armamento)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 267; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:07.845] t=7533.265000 W *WAI
  [15:57:07.876] t=7533.296000 R *ESR? -> 0
  ```

(scpi-trg)=

## `*TRG`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Dispara o transiente armado: aplica o STEP, o PULSe ou o primeiro ponto da lista.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `*TRG` (sem resposta)
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** Só é enviado se `TRIGger:STATe?` for `ARM` ou `WTRIG`; senão `InstrumentHardwareError` ("não estava armada antes de *TRG"). Com `TRIGger:SOURce BUS` e `TRIGger:SYNChronize:SOURce PHASe`, o transiente começa na **fase** de {scpi}`TRIGger:SYNChronize:PHASe`, não no instante do comando (A18): 02, 03 e 04 saíam defasadas 216° do modelo antes de o código programar a fase do modelo no instante do disparo. O pulso BOT que dispara o osciloscópio sai na mesma fase.
- **Erros e quirks:** Escrever outro comando durante o transiente é aceito e ignorado (erro 19, A14).
- **Quem envia:** `AmetekMX30.trigger` ([ametek_orm.py:1914](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1914))
- **Manual:** p. 142.
- **Classes que usam:** todas as classes físicas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 284; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:08.003] t=7533.437000 W *TRG
  [15:57:08.037] t=7533.468000 R *ESR? -> 0
  ```

(scpi-system-error)=

## `SYSTem:ERRor?`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Lê um erro da fila SCPI; o projeto repete até receber `0,"No error"`.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SYSTem:ERRor?` devolve `<código>,"<mensagem>"`
- **Parâmetros e unidades:** Sem parâmetros. `check_errors` lê no máximo 20 erros; 20 sem esvaziar viram `InstrumentHardwareError`.
- **Sincronismo e ordem:** É a conferência que fecha cada passo relevante (`assert_no_errors`). **Nunca logo depois de {scpi}`TRACe:DATA`**, {scpi}`TRACe:DEFine` ou {scpi}`TRACe:DELete:ALL`: a fonte fica muda (A2); depois de `TRACe:DEFine` o código espera 3 s e só então consulta a fila (E28).
- **Erros e quirks:** Resposta fora do formato `código,mensagem`: `CommunicationError`. Códigos que o código reconhece: -113 (cabeçalho indefinido, geralmente comando inexistente ou perdido), -256 (nome de arquivo não encontrado, `CSINe`), -226 (listas de tamanhos diferentes, A9), -300 (erro específico, offset fora de ACDC, A10), -220 (`INITiate` ignorado, A15), 19 (ilegal durante transiente, A14).
- **Quem envia:** `AmetekMX30.check_errors` ([ametek_orm.py:636](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L636))
- **Manual:** pp. 117-118 e Apêndice C (pp. 213-217).
- **Classes que usam:** todas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 17; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:47.887] t=7513.312000 Q SYSTem:ERRor?
  [15:56:47.916] t=7513.343000 W SYSTem:ERRor?
  [15:56:47.916] t=7513.343000 R SYSTem:ERRor? -> 0,"No error"
  ```

(scpi-status-operation-condition)=

## `STATus:OPERation:CONDition?`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Lê o registrador de condição de operação; o bit 3 (valor 8) indica transiente ativo. Só é consultado com `set diagnostico on`.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `STATus:OPERation:CONDition?` devolve um inteiro
- **Parâmetros e unidades:** Sem parâmetros. O código testa `valor & 0x8`.
- **Sincronismo e ordem:** Fora do caminho normal: `_log_diagnostico` tolera falha de leitura (`CommunicationError`, `ValueError`) para o diagnóstico não abortar a captura.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30._log_diagnostico` ([ametek_orm.py:670](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L670))
- **Manual:** p. 114; bits na Tabela 7-1 (p. 169).
- **Classes que usam:** qualquer classe rodada com diagnóstico ligado

- **Exemplo real** (127 V/60 Hz; sessão `sessao_2026-10-07_14-59-54_run02`, `scpi_transcricao.log`, linha 216; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:00:37.973] t=4143.390000 Q STATus:OPERation:CONDition?
  [15:00:38.002] t=4143.421000 W STATus:OPERation:CONDition?
  [15:00:38.008] t=4143.421000 R STATus:OPERation:CONDition? -> 24
  ```

(scpi-output-state)=

## `OUTPut:STATe`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Liga ou desliga a saída da fonte; é o primeiro comando de toda conexão e o último de todo desligamento.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `OUTPut:STATe OFF|ON` ou `OUTPut:STATe?` (devolve `0` ou `1`)
- **Parâmetros e unidades:** `ON` só chega à fonte depois de `authorize_output(True)`: o setter `output_enabled = True` sem autorização levanta `PermissionError` (interlock de software).
- **Sincronismo e ordem:** `connect` envia `OUTPut:STATe OFF` por `_raw_write` **antes** de qualquer consulta, até do `*IDN?`: retirar potência vem antes de identificar. `energize_baseline` liga uma vez no início da bateria, confere `assert_no_errors` e lê de volta por até 5 s; a saída fica ligada durante toda a bateria e `program_capture` só a religa se `ABORt` a derrubou. `safe_shutdown` envia `ABORt`, `OUTPut:STATe OFF`, espera 0,2 s e lê de volta; repete uma vez se não for `0`/`OFF`. O EOT vai em transferência separada (A23): sem ele `OUTPUT ON/OFF` ficava no buffer até a próxima consulta.
- **Erros e quirks:** `SHUTDOWN NÃO CONFIRMADO` é levantado dentro de `safe_shutdown` e capturado por ele mesmo (só vai ao log): quem confere é o operador no painel. `TRACe:DELete:ALL` exige saída desligada (A24).
- **Quem envia:** `AmetekMX30.connect` (OFF) ([ametek_orm.py:350](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L350)); `AmetekMX30.output_enabled` (setter) ([ametek_orm.py:704](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L704)); `AmetekMX30.output_enabled` (getter) ([ametek_orm.py:698](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L698)); `AmetekMX30.safe_shutdown` ([ametek_orm.py:1943](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1943))
- **Manual:** p. 73 (e pp. 16 e 19).
- **Classes que usam:** todas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 174; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:05.257] t=7530.687000 W OUTPut:STATe ON
  [15:57:05.285] t=7530.718000 R *ESR? -> 0
  ```
- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 167; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:49.626] t=7515.046000 Q OUTPut:STATe?
  [15:56:49.656] t=7515.078000 W OUTPut:STATe?
  [15:56:49.660] t=7515.093000 R OUTPut:STATe? -> 0
  ```
- **Outros usos na mesma transcrição:** E53 (linha 5, 127 V/50 Hz). Índice em {doc}`transcricoes`.

(scpi-abort)=

## `ABORt`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Reseta o sistema de trigger e cancela qualquer transiente armado.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `ABORt` (sem resposta)
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** Aparece em `configure_safe_baseline`, no início de `program_capture` e em `safe_shutdown`. **Nunca em `arm_transient`**: na Rev. 5.53 um segundo `ABORt` restaurou `FUNCtion:MODE`/`VOLTage:MODE` para `FIX` e `OUTPUT OFF`, destruindo a lista preparada (A16). Por isso `program_capture` religa a saída quando ela caiu depois do `ABORt` e a reprogramação.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1258](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1258)); `AmetekMX30.program_capture` ([ametek_orm.py:1541](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1541)); `AmetekMX30.safe_shutdown` ([ametek_orm.py:1942](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1942))
- **Manual:** p. 128.
- **Classes que usam:** todas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 13; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:47.855] t=7513.281000 W ABORt
  [15:56:47.887] t=7513.312000 R *ESR? -> 0
  ```

(scpi-initiate-immediate)=

## `INITiate:IMMediate`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Arma o sistema de trigger; com `TRIGger:SOURce BUS` a fonte passa a esperar o `*TRG`.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `INITiate:IMMediate` (sem resposta)
- **Parâmetros e unidades:** Sem parâmetros. Vem sempre depois de {scpi}`*WAI` e de {scpi}`TRIGger:STATe?` mostrar `IDLE`.
- **Sincronismo e ordem:** `arm()` e `arm_transient()` mandam `*WAI`, `INITiate:IMMediate`, conferem a fila e leem `TRIGger:STATe?` até `ARM`/`WTRIG` (prazo de 20 s).
- **Erros e quirks:** **Fora de IDLE o `INITiate` é ignorado**, com `-220 "Init ignored"` na fila (manual pp. 129 e 214) e nenhum erro no próprio comando (A15); a assinatura é fila limpa e estado preso em `IDLE`. `_pista_de_init_ignorado` enriquece a mensagem do `TimeoutError`. Sem `*WAI` antes, STEP seguido de PULSe na mesma conexão reproduzia `-300` de forma determinística (visto na bancada, 01/NORMAL seguido de 02/SAG).
- **Quem envia:** `AmetekMX30.arm` ([ametek_orm.py:1737](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1737)); `AmetekMX30.arm_transient` ([ametek_orm.py:1888](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1888))
- **Manual:** p. 129.
- **Classes que usam:** todas as classes físicas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 271; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:07.876] t=7533.296000 W INITiate:IMMediate
  [15:57:07.912] t=7533.343000 R *ESR? -> 0
  ```

(scpi-trigger-state)=

## `TRIGger:STATe?`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Devolve o estado do sistema de trigger: `IDLE`, `ARM`, `WTRIG` ou `BUSY`.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `TRIGger:STATe?` devolve `IDLE|ARM|WTRIG|BUSY`
- **Parâmetros e unidades:** Sem parâmetros. O código compara pelo prefixo (`startswith`).
- **Sincronismo e ordem:** Antes de programar qualquer transiente nativo (`aguardar_idle`, prazo de 20 s), depois do `INITiate` (espera `ARM` ou `WTRIG`), antes do `*TRG` e ao final (`wait_transient_complete` espera `IDLE` e então confere a fila). Consultas sem resposta contam como "ainda ocupada" (`_query_tolerante`), não como falha. O "falso IDLE" documentado (manual p. 132) existe: `IDLE` não prova que a troca de modo terminou, por isso `arm()` ainda lê de volta cinco parâmetros.
- **Erros e quirks:** Escrever com o transiente em curso gera o erro 19 "Illegal during transient" (manual p. 217) e o valor antigo permanece (A14).
- **Quem envia:** `AmetekMX30.aguardar_idle` ([ametek_orm.py:775](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L775)); `AmetekMX30.arm` ([ametek_orm.py:1742](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1742)); `AmetekMX30.arm_transient` ([ametek_orm.py:1833](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1833)); `AmetekMX30.trigger` ([ametek_orm.py:1911](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1911))
- **Manual:** p. 132 (e p. 128).
- **Classes que usam:** todas as classes físicas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 230; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:07.263] t=7532.687000 Q TRIGger:STATe?
  [15:57:07.304] t=7532.734000 W TRIGger:STATe?
  [15:57:07.307] t=7532.734000 R TRIGger:STATe? -> IDLE
  ```
