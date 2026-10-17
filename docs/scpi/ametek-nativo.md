# AMETEK: caminho nativo

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` {bdg-success}`VERIFICADO NA BANCADA`

**Pergunta:** quais comandos programam o distúrbio nas classes que a própria fonte gera (01 a 05, 18 e 19)? **Resposta:** `VOLTage:MODE STEP` ou `PULSe` com `VOLTage:TRIGgered` (e `PULSe:WIDTh`) para os degraus e afundamentos; `SOURce:FUNCtion:SHAPe:CSINusoid` para a senoide clipada da 05; `SOURce:MODE ACDC` com `SOURce:VOLTage:OFFSet` para a 19; `FREQuency:MODE LIST` com `LIST:FREQuency` para a 18. Antes de cada programação o código espera `IDLE` e põe os outros eixos em `FIXed`.

As sequências completas, com o porquê da ordem, estão em {doc}`sequencias`.

(scpi-voltage-mode)=

## `VOLTage:MODE`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Define como a tensão se comporta quando um transiente dispara: `FIXed` (não muda), `STEP` (salta e fica), `PULSe` (vai e volta) ou `LIST` (segue a lista de tensões).**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `VOLTage:MODE FIXed|STEP|PULSe|LIST` e `VOLTage:MODE?` (devolve `FIX`, `STEP`, `PULS` ou `LIST`)
- **Parâmetros e unidades:** `STEP`: classes 01, 05 (nível nativo) e 19, que usam o salto também para só emitir o pulso BOT (01) ou para retomar a base. `PULSe`: 02 (SAG), 03 (SWELL) e 04 (INTERRUPTION). `LIST`: 18 e as de TRACe (06 a 17, 20 e 05 acima de 20 %). `FIXed`: baseline, entre classes e na classe 18 antes de ligar a lista de frequência.
- **Sincronismo e ordem:** Eixo independente de {scpi}`FUNCtion:MODE` e de {scpi}`SOURce:FREQuency:MODE`. Antes de programar STEP ou PULSe, `aguardar_idle` espera `TRIGger:STATe?` = `IDLE` (escrever durante o transiente é aceito e ignorado, erro 19, A14) e `_neutralizar_transientes_residuais` põe os outros dois eixos em `FIXed`. Depois do comando, `arm()` lê `VOLTage:MODE?` de volta e recusa divergência: a forma curta que a fonte devolve (`FIX`, `PULS`) é aceita por prefixo comum. Sem `*WAI` entre uma classe STEP e uma PULSe na mesma conexão, o `INITiate:IMMediate` reproduzia `-300` de forma determinística.
- **Erros e quirks:** O comando perdido em rajada deixava `VOLTage:MODE` lido como `FIX` (H-NATIVO): corrigido pelo sincronismo de {scpi}`*ESR?` (A1, v1.12).
- **Quem envia:** `AmetekMX30.trigger_step` ([ametek_orm.py:896](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L896)); `AmetekMX30.trigger_pulse` ([ametek_orm.py:925](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L925)); `AmetekMX30.frequency_drift_list` (FIXed e LIST) ([ametek_orm.py:1092](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1092)); `AmetekMX30.frequency_drift_list` ([ametek_orm.py:1106](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1106)); `AmetekMX30.program_capture` (FIXed) ([ametek_orm.py:1551](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1551)); `AmetekMX30.program_capture` (LIST) ([ametek_orm.py:1669](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1669)); `AmetekMX30.arm_transient` (consulta) ([ametek_orm.py:1848](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1848))
- **Manual:** p. 109 (descrição dos quatro modos).
- **Classes que usam:** 01, 02, 03, 04, 05, 18, 19 (nativas); 06 a 17 e 20 (LIST)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 241; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:07.383] t=7532.812000 W VOLTage:MODE STEP
  [15:57:07.413] t=7532.843000 R *ESR? -> 0
  ```
- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 312; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:09.887] t=7535.312000 W VOLTage:MODE PULSe
  [15:57:09.919] t=7535.343000 R *ESR? -> 0
  ```
- **Outros usos na mesma transcrição:** E39 (linha 986, 127 V/50 Hz), E62 (linha 83, 127 V/50 Hz), E17 (linha 255, 127 V/50 Hz). Índice em {doc}`transcricoes`.

(scpi-voltage-triggered)=

## `VOLTage:TRIGgered`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Programa o nível de tensão (V rms) que a saída assume no transiente STEP ou PULSe.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `VOLTage:TRIGgered <V rms>` e `VOLTage:TRIGgered?`
- **Parâmetros e unidades:** O nível passa antes por `quantizar_tensao_rms`: a Rev. 5.53 **trunca** a 0,1 V (2,76 vira 2,7; 4,999 vira 4,9; medido em 30/09/2026, `scripts/diag_nativo_output_off.py`), e o manual não documenta isso. O código escreve já o múltiplo de 0,1 V mais próximo, sem passar do teto de software, para que o metadata e o readback de `arm()` (tolerância de 0,5 %) mostrem o que a fonte de fato aplica (A12).
- **Sincronismo e ordem:** Write sincronizado; `arm()` lê de volta e compara com tolerância de 0,5 % (`TOLERANCIA_READBACK`): apertado o bastante para pegar um valor **preso** de outra classe (242 V contra 220 V = 10 %).
- **Erros e quirks:** Fora de `0..max_voltage_rms`: `ParameterOutOfBoundsError` antes de qualquer SCPI. Escrita durante transiente: erro 19, captura recusada.
- **Quem envia:** `AmetekMX30.trigger_step` ([ametek_orm.py:897](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L897)); `AmetekMX30.trigger_pulse` ([ametek_orm.py:926](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L926))
- **Manual:** p. 108.
- **Classes que usam:** 01 a 05, 19

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 245; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:07.413] t=7532.843000 W VOLTage:TRIGgered 127.0
  [15:57:07.446] t=7532.875000 R *ESR? -> 0
  ```
- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 258; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:07.740] t=7533.171000 Q VOLTage:TRIGgered?
  [15:57:07.765] t=7533.187000 W VOLTage:TRIGgered?
  [15:57:07.766] t=7533.187000 R VOLTage:TRIGgered? -> 127.0
  ```

(scpi-pulse-width)=

## `PULSe:WIDTh`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Define por quanto tempo (s) o PULSe mantém o nível de {scpi}`VOLTage:TRIGgered` antes de voltar à tensão imediata.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `PULSe:WIDTh <s>` e `PULSe:WIDTh?`
- **Parâmetros e unidades:** Segundos, `{width_s:.8g}`; deve ser positiva. A partir da v1.15 a duração do evento é sorteada por captura (`_duracao_sorteada_s`), mas nenhuma largura sorteada foi medida na bancada (P-05).
- **Sincronismo e ordem:** `arm()` lê de volta e compara com tolerância de 0,5 %. Antes da correção do sincronismo, o valor ficava "preso" em 0,0167 s (H-NATIVO).
- **Erros e quirks:** Largura não positiva: `ParameterOutOfBoundsError`.
- **Quem envia:** `AmetekMX30.trigger_pulse` ([ametek_orm.py:927](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L927))
- **Manual:** p. 106.
- **Classes que usam:** 02, 03, 04

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 320; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:09.951] t=7535.375000 W PULSe:WIDTh 0.06
  [15:57:09.983] t=7535.406000 R *ESR? -> 0
  ```
- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 336; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:10.290] t=7535.718000 Q PULSe:WIDTh?
  [15:57:10.322] t=7535.750000 W PULSe:WIDTh?
  [15:57:10.322] t=7535.750000 R PULSe:WIDTh? -> 0.0600
  ```

(scpi-function-shape-csinusoid)=

## `SOURce:FUNCtion:SHAPe:CSINusoid`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Programa o nível de clipping da senoide clipada nativa, expresso como THD em percentual.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:FUNCtion:SHAPe:CSINusoid <THD %>`, depois de selecionar a forma com {scpi}`SOURce:FUNCtion:SHAPe` `CSINusoid`
- **Parâmetros e unidades:** `0 < THD <= 20` (`MAX_CSINE_THD_PCT`, [ametek_orm.py:162](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L162)); acima disso a classe 05 sintetiza a forma em Python e a envia por TRACe (`usar_trace`). O nome completo `CSINusoid` é obrigatório: `CSINe` dá `-256`.
- **Sincronismo e ordem:** Sequência da classe 05: `aguardar_idle`, neutralizar eixos residuais, {scpi}`SOURce:FUNCtion:SHAPe` `CSINusoid`, {scpi}`*WAI`, este comando, {scpi}`*WAI`, `assert_no_errors`. Cada troca recarrega a tabela e deixa a fonte muda por segundos. Rms e THD reais da CSINusoid interna a 10, 15 e 20 % nunca foram medidos na bancada (P-10).
- **Erros e quirks:** THD fora de `(0, 20]`: `ParameterOutOfBoundsError`.
- **Quem envia:** `AmetekMX30.configure_harmonics_csine` ([ametek_orm.py:976](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L976))
- **Manual:** p. 85.
- **Classes que usam:** 05

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 710; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:20.290] t=7545.718000 W SOURce:FUNCtion:SHAPe:CSINusoid 5
  [15:57:20.329] t=7545.750000 R *ESR? -> 0
  ```

(scpi-voltage-offset)=

## `SOURce:VOLTage:OFFSet`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Soma um offset contínuo (V) à saída; só é aceito com {scpi}`SOURce:MODE` em `ACDC`.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:VOLTage:OFFSet <V>`
- **Parâmetros e unidades:** `enable_dc_offset` recusa quando `|offset| + pico CA > max_peak_v`: o pico físico é a soma, não só a amplitude CA. `program_capture` calcula `dc_offset_pu × base × √2`.
- **Sincronismo e ordem:** Ordem obrigatória: {scpi}`SOURce:MODE` `ACDC`, {scpi}`*WAI`, `assert_no_errors`, só então este comando (`_modo_saida` já em `ACDC`). `disable_dc_offset` manda `SOURce:VOLTage:OFFSet 0`, {scpi}`SOURce:MODE` `AC` e `*WAI`, e é no-op quando o modo já é `AC`.
- **Erros e quirks:** Em modo `AC` ou `DC`: `-300 "Device specific error"` (Apêndice C: "Attempt to program voltage offset while in DC or AC mode only"). O código antigo mandava o comando incondicionalmente no fim de toda classe e falhava já na 01/NORMAL (A10). A CA sai 5 a 6 % menor em ACDC (A19, P-17).
- **Quem envia:** `AmetekMX30.enable_dc_offset` ([ametek_orm.py:1135](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1135)); `AmetekMX30.disable_dc_offset` ([ametek_orm.py:1029](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1029)); `AmetekMX30.program_capture` ([ametek_orm.py:1564](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1564))
- **Manual:** p. 108 (descrição de `VOLTage`: "must also be set to AC+DC to accept a DC offset value"); erro `-300` no Apêndice C.
- **Classes que usam:** 19

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 6195; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [16:04:44.216] t=7989.640000 W SOURce:VOLTage:OFFSet 5.5795947
  [16:04:44.248] t=7989.671000 R *ESR? -> 0
  ```

(scpi-list-frequency)=

## `LIST:FREQuency`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Programa a lista de frequências do transiente; a classe 18 usa dois pontos (início e fim da rampa).**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `[SOURce:]LIST:FREQuency <Hz>,<Hz>`
- **Parâmetros e unidades:** Dois valores entre 45 e 500 Hz. Com `SORTEIO=0` a rampa é 57 → 63 Hz fixa, como no commit de referência 34a0d82; com sorteio ligado (v1.15) é `f0 − 3 → f0 + 3` Hz, invertida nas capturas ímpares (`experimentos_nativos/18.py`, `extremos_hz`). O exemplo real abaixo, de 07/10, é de antes da v1.15: 57,63 mesmo na sessão de 50 Hz (+14 % e +26 % da rede).
- **Sincronismo e ordem:** `frequency_drift_list` programa, em ordem: {scpi}`VOLTage:MODE` `FIXed`, {scpi}`SOURce:FREQuency:MODE` `LIST`, este comando, `LIST:VOLTage` (dois valores iguais, ver {scpi}`SOURce:LIST:VOLTage`), `LIST:DWELl` (metade da duração em cada ponto), {scpi}`SOURce:LIST:REPeat` `0,0`, {scpi}`SOURce:LIST:COUNt` `1`, {scpi}`SOURce:LIST:STEP` `AUTO` e por fim {scpi}`VOLTage:MODE` `LIST`. Todas sem o prefixo `SOURce:` exceto `REPeat`. Ao fim a saída fica no último ponto: `restaurar_frequencia_base`.
- **Erros e quirks:** Lista de forma residual de 12 pontos contra esta de 2: `-226 Lists not same length`, evitado por {scpi}`FUNCtion:MODE` `FIXed` antes (A9). Continuidade de fase na troca entre os dois pontos nunca foi medida (P-06).
- **Quem envia:** `AmetekMX30.frequency_drift_list` ([ametek_orm.py:1095](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1095))
- **Manual:** p. 92.
- **Classes que usam:** 18

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 6108; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [16:04:41.876] t=7987.296000 W LIST:FREQuency 57,63
  [16:04:41.910] t=7987.343000 R *ESR? -> 0
  ```
