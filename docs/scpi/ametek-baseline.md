# AMETEK: estado seguro inicial

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` {bdg-success}`VERIFICADO NA BANCADA`

**Pergunta:** o que a fonte recebe antes de a primeira classe rodar? **Resposta:** `configure_safe_baseline` envia, depois de `OUTPut:STATe OFF` e `*CLS`, 22 comandos nesta ordem (`ABORt`, `INSTrument:COUPle ALL`, `SOURce:MODE AC`, faixa, `VOLTage:HIGH`, corrente, forma, três modos `FIXed`, dois `SLEW`, frequência, **0 V**, trigger e BOT), cada um seguido de `check_errors`; a saída fica em 0 V de propósito até um STEP.

A primeira rejeição aborta com `InstrumentHardwareError` apontando o comando, para não continuar a partir de um estado ambíguo. Só depois, `energize_baseline` liga a saída (exige `authorize_output`). Cada entrada abaixo traz o comando, o que ele faz nessa sequência e o exemplo da transcrição de 07/10.

(scpi-instrument-couple)=

## `INSTrument:COUPle`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Acopla as três fases da fonte para programar todas ao mesmo tempo.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `INSTrument:COUPle ALL`
- **Parâmetros e unidades:** `ALL` (o projeto não usa outro valor).
- **Sincronismo e ordem:** Quinto comando da baseline; cada comando da baseline é seguido de `check_errors`, e a primeira rejeição aborta com `InstrumentHardwareError("AMETEK rejeitou ...")`, para não continuar configurando a partir de estado ambíguo.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1259](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1259))
- **Manual:** p. 53.
- **Classes que usam:** todas (abertura da conexão)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 20; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:47.916] t=7513.343000 W INSTrument:COUPle ALL
  [15:56:47.948] t=7513.375000 R *ESR? -> 0
  ```

(scpi-mode)=

## `SOURce:MODE`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Seleciona o modo de tensão da saída: `AC` (padrão do projeto) ou `ACDC`, que permite somar um offset contínuo.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:MODE AC|DC|ACDC`. A consulta `SOURce:MODE?` consta do manual (p. 98) mas a Rev. 5.53 **não a implementa** (ver [comandos que não funcionam](#scpi-nf-mode-consulta)).
- **Parâmetros e unidades:** O projeto usa `AC` e `ACDC`. `program_capture` escolhe `ACDC` quando `dc_offset_pu` não é zero.
- **Sincronismo e ordem:** Trocar de modo deixa a fonte muda por alguns segundos (A7): `enable_dc_offset` manda `*WAI` e confere a fila logo depois. `_modo_saida` espelha o que a fonte tem; `disable_dc_offset` só age quando está em `ACDC`.
- **Erros e quirks:** `SOURce:VOLTage:OFFSet` só é aceito em `ACDC` (`-300`, A10). Em `ACDC` `MEASure:VOLTage:AC?` devolve o RMS total, CA mais CC (H-1, ver {scpi}`MEASure:VOLTage:AC?`) e a CA sai 5 a 6 % menor (A19, 0,938 a 0,951 pu na classe 19, causa NÃO VERIFICADA).
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1260](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1260)); `AmetekMX30.disable_dc_offset` ([ametek_orm.py:1030](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1030)); `AmetekMX30.enable_dc_offset` ([ametek_orm.py:1132](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1132)); `AmetekMX30.program_capture` ([ametek_orm.py:1553](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1553))
- **Manual:** p. 98 (também pp. 79 e 100).
- **Classes que usam:** 19 (ACDC); as demais em AC

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 27; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:47.986] t=7513.406000 W SOURce:MODE AC
  [15:56:48.028] t=7513.453000 R *ESR? -> 0
  ```
- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 6184; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [16:04:44.106] t=7989.531000 W SOURce:MODE ACDC
  [16:04:44.150] t=7989.578000 R *ESR? -> 0
  ```

(scpi-voltage-range)=

## `SOURce:VOLTage:RANGe`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Escolhe a faixa de tensão da fonte (em V rms); o projeto usa 300 V, a maior.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:VOLTage:RANGe <V rms>`
- **Parâmetros e unidades:** `SOURCE_VOLTAGE_RANGE_RMS` (o `start_bench_windows.ps1` sobrescreve com a faixa de trabalho). A baseline recusa `max_voltage_rms` acima da faixa e `max_peak_v` acima de `faixa × √2`.
- **Sincronismo e ordem:** Comando da baseline com `check_errors` imediato.
- **Erros e quirks:** Faixa menor que o limite de software: `ParameterOutOfBoundsError` antes de qualquer SCPI.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1261](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1261))
- **Manual:** p. 110.
- **Classes que usam:** todas (abertura da conexão)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 34; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:48.063] t=7513.484000 W SOURce:VOLTage:RANGe 300
  [15:56:48.090] t=7513.515000 R *ESR? -> 0
  ```

(scpi-voltage-high)=

## `SOURce:VOLTage:HIGH`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Programa o **limite máximo de tensão rms** que a fonte aceita; não é limite de pico.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:VOLTage:HIGH <V rms>`
- **Parâmetros e unidades:** O projeto envia `max_voltage_rms` (300 V). O limite de pico (415,8 V, 425 V absoluto) é só de software.
- **Sincronismo e ordem:** Comando da baseline com `check_errors` imediato.
- **Erros e quirks:** O código antigo escrevia 415,8 aqui, acreditando ser limite de pico; na verdade era um limite de 415,8 V rms, que não protegia pico nenhum. Medido em 30/09/2026 (ensaio T12): com `HIGH` = 4, 3,5 Vrms (4,95 Vp) foi aceito e 4,5 Vrms deu `-222` (quirk A13, corrigido na v1.12).
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1262](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1262))
- **Manual:** p. 109 ("programs the maximum rms voltage").
- **Classes que usam:** todas (abertura da conexão)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 41; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:48.128] t=7513.546000 W SOURce:VOLTage:HIGH 300
  [15:56:48.170] t=7513.593000 R *ESR? -> 0
  ```

(scpi-current)=

## `SOURce:CURRent`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Programa o limite de corrente da fonte (A).**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:CURRent <A>`
- **Parâmetros e unidades:** `CURRENT_LIMIT_A` (padrão 0,5 A, [mestre.py:406](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L406)). O setter `current_limit` recusa valores fora de `0 < A <= max_current_a`; captura de corrente continua desligada por padrão.
- **Sincronismo e ordem:** Comando da baseline com `check_errors` imediato. O manual (p. 79) acopla a corrente à faixa de tensão e ao modo.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1263](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1263))
- **Manual:** p. 79.
- **Classes que usam:** todas (abertura da conexão)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 48; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:48.204] t=7513.625000 W SOURce:CURRent 0.5
  [15:56:48.232] t=7513.656000 R *ESR? -> 0
  ```

(scpi-current-protection-state)=

## `SOURce:CURRent:PROTection:STATe`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Liga a proteção por sobrecorrente.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:CURRent:PROTection:STATe ON|OFF`
- **Parâmetros e unidades:** O projeto envia `ON`.
- **Sincronismo e ordem:** Comando da baseline com `check_errors` imediato.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1264](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1264))
- **Manual:** p. 80.
- **Classes que usam:** todas (abertura da conexão)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 55; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:48.268] t=7513.703000 W SOURce:CURRent:PROTection:STATe ON
  [15:56:48.296] t=7513.718000 R *ESR? -> 0
  ```

(scpi-current-protection-delay)=

## `SOURce:CURRent:PROTection:DELay`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Define por quanto tempo a corrente pode exceder o limite antes de a proteção atuar.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:CURRent:PROTection:DELay <s>`
- **Parâmetros e unidades:** `CURRENT_PROTECTION_DELAY_S` (padrão 0,1 s, [mestre.py:407](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L407)). Entre 0,1 e 5 s; a baseline recusa valores fora disso antes de qualquer SCPI (`ParameterOutOfBoundsError`).
- **Sincronismo e ordem:** Comando da baseline com `check_errors` imediato.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1265](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1265))
- **Manual:** p. 80.
- **Classes que usam:** todas (abertura da conexão)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 62; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:48.333] t=7513.765000 W SOURce:CURRent:PROTection:DELay 0.1
  [15:56:48.365] t=7513.796000 R *ESR? -> 0
  ```

(scpi-function-shape)=

## `SOURce:FUNCtion:SHAPe`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Seleciona a forma de onda da saída: `SINusoid` (padrão) ou `CSINusoid`, a senoide clipada.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:FUNCtion:SHAPe SINusoid|CSINusoid|<nome de TRACe>`. A consulta `SOURce:FUNCtion:SHAPe?` **não existe** na Rev. 5.53.
- **Parâmetros e unidades:** O nome completo é obrigatório: a forma abreviada do manual, `CSINe`, é rejeitada com `-256 "File name not found"` (A6): a Rev. 5.53 resolve `FUNCtion:SHAPe` como busca no catálogo de formas e só reconhece o nome completo.
- **Sincronismo e ordem:** Trocar a forma recarrega a tabela e deixa a fonte muda por alguns segundos (A7): `*WAI` logo depois, com `assert_no_errors` apontando o comando certo (antes, um erro daqui aparecia na fila do `INITiate` seguinte e era atribuído a ele, visto como `-113` na classe 05). `select_sine_shape` só envia se `_forma_atual` não é `SINusoid` (a baseline já a deixa assim); `restaurar_forma_e_modo_padrao` roda ao fim de toda classe física.
- **Erros e quirks:** `-256` com `CSINe`. Com `FUNCtion:MODE LIST` residual a forma efetiva no `*TRG` é a da lista, não a recém-selecionada (A9).
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1266](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1266)); `AmetekMX30.configure_harmonics_csine` ([ametek_orm.py:965](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L965)); `AmetekMX30.select_sine_shape` ([ametek_orm.py:1008](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1008)); `AmetekMX30.program_capture` ([ametek_orm.py:1557](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1557))
- **Manual:** p. 84.
- **Classes que usam:** 05 (CSINusoid até 20 %); todas as demais em SINusoid

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 69; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:48.397] t=7513.828000 W SOURce:FUNCtion:SHAPe SINusoid
  [15:56:48.432] t=7513.859000 R *ESR? -> 0
  ```

(scpi-function-mode)=

## `FUNCtion:MODE`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Escolhe se a forma de onda é fixa (`FIXed`) ou vem de uma lista (`LIST`) quando um transiente dispara.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `FUNCtion:MODE FIXed|LIST` e `FUNCtion:MODE?` (devolve `FIX` ou `LIST`)
- **Parâmetros e unidades:** `FIXed` na baseline e antes de toda programação nativa; `LIST` só em `program_capture`.
- **Sincronismo e ordem:** `FUNCtion:MODE`, `VOLTage:MODE` e `SOURce:FREQuency:MODE` são eixos **independentes** (manual, seções 4.13 e 4.17): uma lista de forma residual de uma classe de lista continua sendo aplicada em todo `*TRG`, mesmo com `VOLTage:MODE` em STEP. `_neutralizar_transientes_residuais` manda `FUNCtion:MODE FIXed` e `SOURce:FREQuency:MODE FIXed` antes de toda programação nativa (passo 1 do procedimento do manual, seção 6.4.2, p. 152).
- **Erros e quirks:** `FUNCtion:MODE LIST` residual dá `-226 Lists not same length` na classe 18 quando ela roda depois da 17 (lista de forma de 12 pontos contra lista de frequência de 2): manual seção 4.17, p. 90, e quirk A9.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1267](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1267)); `AmetekMX30._neutralizar_transientes_residuais` ([ametek_orm.py:841](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L841)); `AmetekMX30.program_capture` (LIST) ([ametek_orm.py:1668](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1668)); `AmetekMX30._conferir_transiente_programado` ([ametek_orm.py:1798](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1798))
- **Manual:** p. 85.
- **Classes que usam:** todas (FIXed); 06 a 17 e 20 (LIST)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 76; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:48.464] t=7513.890000 W FUNCtion:MODE FIXed
  [15:56:48.500] t=7513.921000 R *ESR? -> 0
  ```
- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 979; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:58:11.001] t=7596.421000 W FUNCtion:MODE LIST
  [15:58:11.036] t=7596.468000 R *ESR? -> 0
  ```
- **Outros usos na mesma transcrição:** E18 (linha 261, 127 V/50 Hz). Índice em {doc}`transcricoes`.

(scpi-frequency-mode)=

## `SOURce:FREQuency:MODE`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Escolhe se a frequência é fixa (`FIXed`) ou vem de uma lista (`LIST`) no transiente.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:FREQuency:MODE FIXed|LIST` e `SOURce:FREQuency:MODE?` (devolve `FIX`)
- **Parâmetros e unidades:** `LIST` só na classe 18 (`frequency_drift_list`, que também usa a forma sem prefixo `FREQuency:MODE LIST`).
- **Sincronismo e ordem:** Mesma independência de eixos de {scpi}`FUNCtion:MODE`. Ao fim de um `LIST`, a saída **fica no último ponto da lista**: `FREQuency:MODE FIXed` troca o modo, não o valor (A11); a 19 rodou inteira a 63,03 Hz depois da 18 até `restaurar_frequencia_base` reescrever {scpi}`SOURce:FREQuency`.
- **Erros e quirks:** Sem erro próprio conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1269](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1269)); `AmetekMX30._neutralizar_transientes_residuais` ([ametek_orm.py:842](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L842)); `AmetekMX30.frequency_drift_list` ([ametek_orm.py:1094](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1094)); `AmetekMX30.restaurar_frequencia_base` ([ametek_orm.py:1061](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1061)); `AmetekMX30.program_capture` ([ametek_orm.py:1556](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1556))
- **Manual:** p. 81.
- **Classes que usam:** todas (FIXed); 18 (LIST)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 90; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:48.600] t=7514.031000 W SOURce:FREQuency:MODE FIXed
  [15:56:48.641] t=7514.062000 R *ESR? -> 0
  ```
- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 6104; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [16:04:41.845] t=7987.265000 W FREQuency:MODE LIST
  [16:04:41.876] t=7987.296000 R *ESR? -> 0
  ```
- **Outros usos na mesma transcrição:** E47 (linha 264, 127 V/50 Hz). Índice em {doc}`transcricoes`.

(scpi-frequency-slew)=

## `SOURce:FREQuency:SLEW`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Define a taxa de variação da frequência; o projeto a deixa no máximo.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:FREQuency:SLEW MAXimum`
- **Parâmetros e unidades:** `MAXimum`.
- **Sincronismo e ordem:** Comando da baseline com `check_errors` imediato.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1270](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1270))
- **Manual:** p. 82.
- **Classes que usam:** todas (abertura da conexão)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 97; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:48.674] t=7514.093000 W SOURce:FREQuency:SLEW MAXimum
  [15:56:48.710] t=7514.140000 R *ESR? -> 0
  ```

(scpi-voltage-slew)=

## `SOURce:VOLTage:SLEW`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Define a taxa de variação da tensão; o projeto a deixa no máximo.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:VOLTage:SLEW MAXimum`
- **Parâmetros e unidades:** `MAXimum`.
- **Sincronismo e ordem:** Comando da baseline com `check_errors` imediato. A taxa máxima não elimina o toque (sobressinal) da saída depois de um degrau rápido (A20).
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1271](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1271))
- **Manual:** p. 111.
- **Classes que usam:** todas (abertura da conexão)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 104; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:48.752] t=7514.171000 W SOURce:VOLTage:SLEW MAXimum
  [15:56:48.788] t=7514.218000 R *ESR? -> 0
  ```

(scpi-trigger-source)=

## `TRIGger:SOURce`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Escolhe a fonte do trigger do transiente; o projeto usa `BUS`, ou seja, o `*TRG` enviado pelo PC.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `TRIGger:SOURce BUS` e `TRIGger:SOURce?` (devolve `BUS`)
- **Parâmetros e unidades:** `BUS`.
- **Sincronismo e ordem:** Programado na baseline e de novo em `program_capture`; `arm_transient` lê de volta e exige `BUS`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1274](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1274)); `AmetekMX30.program_capture` ([ametek_orm.py:1670](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1670)); `AmetekMX30.arm_transient` ([ametek_orm.py:1854](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1854))
- **Manual:** p. 130.
- **Classes que usam:** todas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 125; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:48.964] t=7514.390000 W TRIGger:SOURce BUS
  [15:56:48.997] t=7514.421000 R *ESR? -> 0
  ```
- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 1065; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:58:12.075] t=7597.500000 Q TRIGger:SOURce?
  [15:58:12.103] t=7597.531000 W TRIGger:SOURce?
  [15:58:12.107] t=7597.531000 R TRIGger:SOURce? -> BUS
  ```

(scpi-trigger-synchronize-source)=

## `TRIGger:SYNChronize:SOURce`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Escolhe o que sincroniza o início do transiente; o projeto usa `PHASe`, a fase da saída.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `TRIGger:SYNChronize:SOURce PHASe`
- **Parâmetros e unidades:** `PHASe`.
- **Sincronismo e ordem:** Baseline e `program_capture`. Com `PHASe`, o `*TRG` age na fase de {scpi}`TRIGger:SYNChronize:PHASe`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1275](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1275)); `AmetekMX30.program_capture` ([ametek_orm.py:1671](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1671))
- **Manual:** p. 131.
- **Classes que usam:** todas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 132; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:49.032] t=7514.453000 W TRIGger:SYNChronize:SOURce PHASe
  [15:56:49.065] t=7514.500000 R *ESR? -> 0
  ```

(scpi-trigger-synchronize-phase)=

## `TRIGger:SYNChronize:PHASe`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Define a fase da saída, em graus, em que o `*TRG` aplica o transiente (e em que sai o pulso BOT que dispara o osciloscópio).**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `TRIGger:SYNChronize:PHASe <graus>`
- **Parâmetros e unidades:** Graus em módulo 360, com uma casa decimal (`{graus:.1f}`). Baseline e `program_capture` programam `0`.
- **Sincronismo e ordem:** `definir_fase_de_disparo` envia e confere a fila; **sem leitura de volta**: `TRIGger:SYNChronize:PHASe?` nunca foi testado na Rev. 5.53 e um cabeçalho de consulta não implementado deixa `-113` na fila. Quem confirma a fase é a validação física (correlação e THD contra `gerar()`). Fase sorteada por captura (v1.15) ainda não foi medida na bancada (P-05).
- **Erros e quirks:** Fase diferente da pretendida desloca o início do evento em até um ciclo (A18).
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1276](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1276)); `AmetekMX30.definir_fase_de_disparo` ([ametek_orm.py:854](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L854)); `AmetekMX30.program_capture` ([ametek_orm.py:1672](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1672))
- **Manual:** p. 131.
- **Classes que usam:** 01 a 04, 18 e 19 (nativas); zero nas de lista

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 139; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:49.098] t=7514.531000 W TRIGger:SYNChronize:PHASe 0
  [15:56:49.132] t=7514.562000 R *ESR? -> 0
  ```

(scpi-output-ttltrg-mode)=

## `OUTPut:TTLTrg:MODE`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Seleciona o modo do sinal TTL de trigger de saída (conector Trigger Out); o projeto usa `TRIG`.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `OUTPut:TTLTrg:MODE TRIG|FSTR`
- **Parâmetros e unidades:** `TRIG`.
- **Sincronismo e ordem:** Baseline e `program_capture`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1277](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1277)); `AmetekMX30.program_capture` ([ametek_orm.py:1673](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1673))
- **Manual:** p. 76.
- **Classes que usam:** todas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 146; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:49.170] t=7514.593000 W OUTPut:TTLTrg:MODE TRIG
  [15:56:49.207] t=7514.640000 R *ESR? -> 0
  ```

(scpi-output-ttltrg-source)=

## `OUTPut:TTLTrg:SOURce`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Escolhe qual evento gera o pulso TTL; o projeto usa `BOT`, o início do transiente.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `OUTPut:TTLTrg:SOURce BOT`
- **Parâmetros e unidades:** `BOT` (begin of transient).
- **Sincronismo e ordem:** Baseline e `program_capture`. O pulso BOT segue pelo BNC até o `EXT Trigger` do osciloscópio ({scpik}`:TRIGger:EDGE:SOURce`).
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1278](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1278)); `AmetekMX30.program_capture` ([ametek_orm.py:1674](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1674))
- **Manual:** p. 77.
- **Classes que usam:** todas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 153; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:49.241] t=7514.671000 W OUTPut:TTLTrg:SOURce BOT
  [15:56:49.271] t=7514.703000 R *ESR? -> 0
  ```

(scpi-output-ttltrg)=

## `OUTPut:TTLTrg`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Liga o sinal TTL de trigger de saída.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `OUTPut:TTLTrg ON|OFF`
- **Parâmetros e unidades:** `ON`.
- **Sincronismo e ordem:** Baseline e `program_capture`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1279](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1279)); `AmetekMX30.program_capture` ([ametek_orm.py:1675](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1675))
- **Manual:** p. 76.
- **Classes que usam:** todas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 160; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:49.304] t=7514.734000 W OUTPut:TTLTrg ON
  [15:56:49.338] t=7514.765000 R *ESR? -> 0
  ```
