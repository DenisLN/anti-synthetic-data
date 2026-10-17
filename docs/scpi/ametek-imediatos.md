# AMETEK: valores imediatos e medidas

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` {bdg-success}`VERIFICADO NA BANCADA`

**Pergunta:** quais comandos mudam um valor imediato da saída ou medem o que a fonte entrega? **Resposta:** `SOURce:FREQuency` e `SOURce:VOLTage` (e suas formas longas) mudam frequência e tensão imediatas; as quatro `MEASure:*` leem tensão, corrente, potência e fator de potência; só `MEASure:VOLTage:AC?` é usado de fato, e só na verificação da cadeia de medição e no diagnóstico.

(scpi-frequency)=

## `SOURce:FREQuency`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Programa a frequência imediata da saída (Hz).**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:FREQuency <Hz>` e `SOURce:FREQuency?`
- **Parâmetros e unidades:** O setter `frequency` aceita 45 a 500 Hz (`ParameterOutOfBoundsError` fora disso); a baseline envia a frequência de teste e `program_capture` a reenvia a cada captura.
- **Sincronismo e ordem:** `restaurar_frequencia_base` reescreve a base depois de uma lista (A11). A consulta `SOURce:FREQuency?` existe no getter e não aparece nas sessões de 07/10.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1272](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1272)); `AmetekMX30.frequency` (setter) ([ametek_orm.py:755](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L755)); `AmetekMX30.restaurar_frequencia_base` ([ametek_orm.py:1062](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1062)); `AmetekMX30.program_capture` ([ametek_orm.py:1556](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1556))
- **Manual:** p. 81.
- **Classes que usam:** todas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 111; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:48.824] t=7514.250000 W SOURce:FREQuency 50
  [15:56:48.860] t=7514.281000 R *ESR? -> 0
  ```

(scpi-voltage)=

## `SOURce:VOLTage`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Programa a tensão imediata da saída (V rms) com a fonte em modo `AC`.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:VOLTage <V rms>` (forma curta de `SOURce:VOLTage:LEVel:IMMediate:AMPLitude`)
- **Parâmetros e unidades:** A baseline programa **0 V** de propósito: a saída só chega à tensão de teste por um STEP depois de energizada. `program_capture` programa a tensão base a cada captura.
- **Sincronismo e ordem:** No modo `ACDC` o mesmo cabeçalho com `:OFFSet` programa o offset ({scpi}`SOURce:VOLTage:OFFSet`).
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.configure_safe_baseline` ([ametek_orm.py:1273](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1273)); `AmetekMX30.program_capture` ([ametek_orm.py:1559](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1559))
- **Manual:** p. 108.
- **Classes que usam:** todas

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 118; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:48.896] t=7514.328000 W SOURce:VOLTage 0
  [15:56:48.932] t=7514.359000 R *ESR? -> 0
  ```

(scpi-voltage-level-immediate-amplitude)=

## `SOURce:VOLTage:LEVel:IMMediate:AMPLitude`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Forma longa de {scpi}`SOURce:VOLTage`, usada pelo setter `voltage`.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:VOLTage:LEVel:IMMediate:AMPLitude <V rms>` e a consulta correspondente
- **Parâmetros e unidades:** O setter `voltage` aceita 0 a `max_voltage_rms` (`ParameterOutOfBoundsError` fora disso).
- **Sincronismo e ordem:** Write sincronizado como os demais.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.voltage` (setter) ([ametek_orm.py:741](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L741))
- **Manual:** p. 108.
- **Classes que usam:** usado nos preflights

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 207; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:05.812] t=7531.234000 W SOURce:VOLTage:LEVel:IMMediate:AMPLitude 127
  [15:57:05.845] t=7531.265000 R *ESR? -> 0
  ```

(scpi-current-level-immediate-amplitude)=

## `SOURce:CURRent:LEVel:IMMediate:AMPLitude`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código; nenhuma sessão de 07/10 o exerceu.

**O que faz?** **Forma longa de {scpi}`SOURce:CURRent`, usada pelo setter `current_limit`.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:CURRent:LEVel:IMMediate:AMPLitude <A>` e a consulta correspondente
- **Parâmetros e unidades:** O setter aceita `0 < A <= max_current_a`.
- **Sincronismo e ordem:** Write sincronizado como os demais.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.current_limit` (setter) ([ametek_orm.py:771](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L771))
- **Manual:** p. 79.
- **Classes que usam:** não usado nas sessões de 07/10

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (nenhuma sessão de 07/10 exerceu este comando).

  ```text
  W SOURce:CURRent:LEVel:IMMediate:AMPLitude 0.5
  R *ESR? -> 0      (forma enviada por `current_limit`)
  ```

(scpi-measure-voltage-ac)=

## `MEASure:VOLTage:AC?`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Mede a tensão rms da saída, vista pela própria fonte.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `MEASure:VOLTage:AC?` devolve V rms (NR2)
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** Usado por `verificar_cadeia_de_medicao` (fonte dentro de 5 % da base, sempre em AC) e por `set diagnostico on`. A consulta demora cerca de 0,2 s (E45: 0,2 s entre a pergunta e a resposta).
- **Erros e quirks:** **Em `ACDC` devolve o RMS total (CA mais CC)**, apesar de o manual falar em "ac rms voltage": com offset de 5,58 V já programado e antes do degrau CA, a fonte leu 5,491 V (sessão de 127 V/60 Hz de 07/10, transcrição). Interpretação sustentada por uma leitura e pela consistência de três capturas; `MEASure:VOLTage:DC?` fecharia a dúvida (`scripts/diag_acdc_amplitude.py`, nunca rodou, P-17).
- **Quem envia:** `AmetekMX30.measure_voltage` ([ametek_orm.py:1977](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1977))
- **Manual:** p. 70.
- **Classes que usam:** nenhuma classe (cadeia de medição e diagnóstico)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 220; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:05.953] t=7531.375000 Q MEASure:VOLTage:AC?
  [15:57:05.977] t=7531.406000 W MEASure:VOLTage:AC?
  [15:57:06.160] t=7531.593000 R MEASure:VOLTage:AC? -> 126.525
  ```

(scpi-measure-current-ac)=

## `MEASure:CURRent:AC?`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código; nenhuma sessão de 07/10 o exerceu.

**O que faz?** **Mede a corrente rms da saída.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `MEASure:CURRent:AC?` devolve A rms
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** A captura de corrente está desligada por padrão (`CAPTURE_CURRENT=0`).
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.measure_current` ([ametek_orm.py:1980](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1980))
- **Manual:** p. 62 (corrente AC).
- **Classes que usam:** nenhuma

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (nenhuma sessão de 07/10 exerceu este comando).

  ```text
  Q MEASure:CURRent:AC?
  R MEASure:CURRent:AC? -> 0.0123      (valor ilustrativo)
  ```

(scpi-measure-power-ac-real)=

## `MEASure:POWer:AC:REAL?`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código; nenhuma sessão de 07/10 o exerceu.

**O que faz?** **Mede a potência ativa; o código multiplica por 1000.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `MEASure:POWer:AC:REAL?` devolve a potência na unidade do manual
- **Parâmetros e unidades:** Sem parâmetros. O fator 1000 em `measure_power_w` pressupõe resposta em kW; o manual lista a unidade só na tabela da p. 159 ("power in VA"): unidade NÃO VERIFICADA na fonte real.
- **Sincronismo e ordem:** Sem sincronismo especial.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.measure_power_w` ([ametek_orm.py:1983](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1983))
- **Manual:** p. 159 (tabela; seção própria não localizada no texto).
- **Classes que usam:** nenhuma

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (nenhuma sessão de 07/10 exerceu este comando).

  ```text
  Q MEASure:POWer:AC:REAL?
  R MEASure:POWer:AC:REAL? -> 0.0015      (valor ilustrativo; a unidade supõe kW)
  ```

(scpi-measure-power-ac-pfactor)=

## `MEASure:POWer:AC:PFACtor?`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código; nenhuma sessão de 07/10 o exerceu.

**O que faz?** **Mede o fator de potência.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `MEASure:POWer:AC:PFACtor?` devolve um número sem unidade
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** Sem sincronismo especial.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.measure_power_factor` ([ametek_orm.py:1986](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1986))
- **Manual:** p. 69.
- **Classes que usam:** nenhuma

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (nenhuma sessão de 07/10 exerceu este comando).

  ```text
  Q MEASure:POWer:AC:PFACtor?
  R MEASure:POWer:AC:PFACtor? -> 0.98      (valor ilustrativo)
  ```
