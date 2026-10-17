# AMETEK: TRACe e lista

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` {bdg-success}`VERIFICADO NA BANCADA`

**Pergunta:** como o projeto faz a fonte reproduzir uma forma arbitrária (classes 06 a 17, 20 e a 05 acima de 20 %)? **Resposta:** grava um ciclo por TRACe (`TRACe:DEFine`, `TRACe:DATA` de 1024 pontos), monta uma lista com um passo por ciclo (`SOURce:LIST:FUNCtion:SHAPe`, `:VOLTage`, `:DWELl`) e dispara a lista inteira por `*TRG`; as gravações em Flash são as únicas escritas que **não** são sincronizadas por `*ESR?`.

Histórico das quirks desta família: a gravação em rajada se perdia (v1.12), a consulta logo após `TRACe:DATA` travava a fonte (v1.12) e `LIST:REPeat 1` tocava cada ciclo duas vezes (v1.9 e v1.10). A sequência completa está em {doc}`sequencias`.

(scpi-trace-catalog)=

## `TRACe:CATalog?`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Lista os nomes de formas de onda existentes na fonte (as pré-definidas e as de usuário).**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `TRACe:CATalog?` devolve nomes entre aspas, separados por vírgula
- **Parâmetros e unidades:** Sem parâmetros. O código tira aspas e põe em maiúsculas.
- **Sincronismo e ordem:** Primeira consulta de `_ensure_trace_slots` e de `_trace_catalog_contains`. O cache de TRACe de `program_capture` **sempre** reconfirma aqui antes de reaproveitar: se outro processo apagou o catálogo, força reprogramar. Com sorteio ligado a forma muda a cada captura e o cache nunca acerta.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30._trace_catalog` ([ametek_orm.py:1322](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1322))
- **Manual:** p. 127.
- **Classes que usam:** 06 a 17, 20 (05 acima de 20 %)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 835; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:23.054] t=7548.484000 Q TRACe:CATalog?
  [15:57:23.077] t=7548.500000 W TRACe:CATalog?
  [15:57:23.082] t=7548.515000 R TRACe:CATalog? -> "SINE,SQUARE,CLIPPED"
  ```

(scpi-trace-define)=

## `TRACe:DEFine`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Reserva um nome de forma de onda de usuário (`TCC00`, `TCC01`, ...) na memória não volátil da fonte.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `TRACe:DEFine <nome>`
- **Parâmetros e unidades:** Um nome por ciclo da captura: `TCC00` a `TCC11` a 60 Hz (12 ciclos de 500 amostras) e `TCC00` a `TCC09` a 50 Hz (10 ciclos de 600). O manual limita a 50 formas de usuário por grupo (p. 126).
- **Sincronismo e ordem:** **Sem `*ESR?`** (`_SEM_SINCRONISMO`). O manual cita cerca de 500 ms, mas a Rev. 5.53 ficou ocupada por mais tempo gravando Flash; o código espera 3 s e só então confere a fila (E28 mostra os 3,0 s antes de `SYSTem:ERRor?`). Só é definido uma vez por nome numa conexão; depois já consta do catálogo.
- **Erros e quirks:** Sem erro conhecido; o intervalo de 3 s sem resposta parece trava mas é trabalho esperado (log "Definindo TRACE ... grava na Flash").
- **Quem envia:** `AmetekMX30._ensure_trace_slots` ([ametek_orm.py:1345](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1345))
- **Manual:** p. 127.
- **Classes que usam:** 06 a 17, 20 (05 acima de 20 %)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 838; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:23.083] t=7548.515000 W TRACe:DEFine TCC00
  # sem *ESR? a seguir; próxima linha da transcrição:
  [15:57:26.087] t=7551.515000 Q SYSTem:ERRor?
  ```

(scpi-trace-data)=

## `TRACe:DATA`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Grava os 1024 pontos de **um ciclo** numa forma de usuário; a fonte remove a componente CC e escala para o rms que {scpi}`SOURce:LIST:VOLTage` pedir.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `TRACe:DATA <nome>,<v1>,...,<v1024>`; a leitura `TRACe:DATA? <nome>` aparece só no diagnóstico
- **Parâmetros e unidades:** Exatamente 1024 pontos em unidades arbitrárias (o manual, p. 126: "An error will occur if exactly 1024 data points are not sent"). O projeto envia `%.8g`, média zero, pico 1, calculados por `montar_programacao`; o comando tem cerca de 11,7 kB (E29: "11719 bytes no total"; a transcrição trunca a 160 caracteres).
- **Sincronismo e ordem:** **Nunca consultar a fonte logo depois** (A2): a fonte ficou muda até ser religada, reproduzível; forte candidato à trava de 16/09/2026. Por isso `TRACe:DATA` está fora do sincronismo, e `program_capture` faz `sleep(1.0)` e depois {scpi}`*CLS`, sem consultar nada, após cada gravação. Cada `TRACe:DATA` incrementa `escritas_trace`; a sessão de 16/09 travou a fonte na 280.ª gravação de uma conexão (A3, P-23; causa NÃO VERIFICADA, hipótese: volume de gravações em memória não volátil), e a CLI só avisa a partir de 280. A reescrita é evitada quando forma, tensão, frequência e offset são os mesmos da última captura da conexão (cache confirmado em {scpi}`TRACe:CATalog?`).
- **Erros e quirks:** Diferente de 1024 pontos: erro SCPI. **`TRACe:DATA?`**: o manual se contradiz (p. 126, "Query Syntax: none"; p. 147, "when queried, trace data is returned as normalized values"); a resposta (lista NRf separada por vírgula) {bdg-warning}`NÃO VERIFICADO` nunca foi obtida da fonte real (P-19). `ler_trace` recusa se o comando anterior foi uma escrita de TRACe, espera 2 s desde a última gravação e usa timeout próprio de 15 s.
- **Quem envia:** `ProgramacaoCaptura.comando_trace` ([ametek_orm.py:122](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L122)); `AmetekMX30.program_capture` ([ametek_orm.py:1610](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1610)); `AmetekMX30.ler_trace` ([ametek_orm.py:1383](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1383))
- **Manual:** p. 126 (comando) e p. 147 (formato normalizado); índice nas pp. 126-127.
- **Classes que usam:** 06 a 17, 20 (05 acima de 20 %)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 878; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:57:53.494] t=7578.921000 W TRACe:DATA TCC00,0.011314514,0.016806151,0.022299671,0.027797725,0.033299188,0.038803054,0.0443115,0.049821368,0.055335037,0.060850567,0.066368224,0.071888449,0... [11719 bytes no total]
  # sem *ESR? a seguir; próxima linha da transcrição:
  [15:57:55.156] t=7580.578000 W *CLS
  ```

(scpi-trace-delete-all)=

## `TRACe:DELete:ALL`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Apaga todas as formas de usuário da memória da fonte.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `TRACe:DELete:ALL`
- **Parâmetros e unidades:** Sem parâmetros. Só roda se `AMETEK_CLEAR_USER_WAVEFORMS=1` (o `bench_config.ps1` liga), uma vez por conexão.
- **Sincronismo e ordem:** **Só com a saída desligada** (A24: a fonte recusa com `OUTPUT ON`; `clear_all_traces` checa antes e levanta `InstrumentHardwareError`). Sem `*ESR?`: a Rev. 5.53 ficou ocupada por mais de 6 s com um catálogo cheio, então o código espera 15 s sem consultar e valida pelo catálogo depois. O efeito é invalidar o cache de TRACe entre conexões.
- **Erros e quirks:** Com a saída ligada a fonte recusa.
- **Quem envia:** `AmetekMX30.clear_all_traces` ([ametek_orm.py:1312](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1312))
- **Manual:** p. 127.
- **Classes que usam:** nenhuma (abertura da conexão)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 173; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:56:49.697] t=7515.125000 W TRACe:DELete:ALL
  # sem *ESR? a seguir; próxima linha da transcrição:
  [15:57:05.257] t=7530.687000 W OUTPut:STATe ON
  ```

(scpi-list-function-shape)=

## `SOURce:LIST:FUNCtion:SHAPe`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Programa a lista de formas de onda: uma TRACe por passo.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:LIST:FUNCtion:SHAPe <nome>,<nome>,...`
- **Parâmetros e unidades:** Os nomes `TCC00,...,TCC<N-1>`, um por ciclo de 1/f.
- **Sincronismo e ordem:** Cada comando de dados de lista é seguido de `check_errors` e da consulta `:POINts?` do seu eixo ({scpi}`SOURce:LIST:FUNCtion:POINts?`), que precisa devolver o número de ciclos; senão `InstrumentHardwareError` aponta exatamente qual comando falhou. Diferente de `TRACe:DATA` (Flash), estes comandos são só RAM e têm consulta própria.
- **Erros e quirks:** Com `FUNCtion:MODE LIST` residual de uma captura anterior, a Rev. 5.53 rejeita comandos `LIST` com `-113`: `program_capture` volta antes a {scpi}`FUNCtion:MODE` `FIXed` e {scpi}`VOLTage:MODE` `FIXed`.
- **Quem envia:** `AmetekMX30.program_capture` ([ametek_orm.py:1644](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1644))
- **Manual:** p. 93.
- **Classes que usam:** 06 a 17, 20 (05 acima de 20 %)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 928; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:58:10.471] t=7595.890000 W SOURce:LIST:FUNCtion:SHAPe TCC00,TCC01,TCC02,TCC03,TCC04,TCC05,TCC06,TCC07,TCC08,TCC09
  [15:58:10.502] t=7595.921000 R *ESR? -> 0
  ```

(scpi-list-voltage)=

## `SOURce:LIST:VOLTage`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Programa a tensão rms de cada passo da lista.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `[SOURce:]LIST:VOLTage <V rms>,<V rms>,...`
- **Parâmetros e unidades:** Na captura por TRACe: o **rms da componente CA** de cada ciclo (sem a média), `base × √2 × rms_pu`, com `%.8g`. Com o rms "com média", a amplitude CA saía inflada nos ciclos de média diferente de zero (degrau a meio ciclo: classes 10, 11, 12, 16; corrigido na v1.15). Na classe 18: dois valores iguais à tensão base.
- **Sincronismo e ordem:** Mesmo regime de {scpi}`SOURce:LIST:FUNCtion:SHAPe`: `check_errors` e `:POINts?` imediatos. Um ciclo que passe de `max_voltage_rms` só gera aviso aqui; a recusa está na pré-validação de `mestre` (P-04).
- **Erros e quirks:** Sem erro conhecido. A média de cada ciclo continua perdida: a fonte remove o DC da TRACe, de modo que o degrau a meio ciclo perde a média (erro programada × modelo de 0,24 a 0,33 pu nas compostas 10, 11, 12 e 16, P-09).
- **Quem envia:** `AmetekMX30.program_capture` ([ametek_orm.py:1645](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1645)); `AmetekMX30.frequency_drift_list` ([ametek_orm.py:1096](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1096))
- **Manual:** p. 96.
- **Classes que usam:** 06 a 17, 20 (E32); 18 (E22)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 938; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:58:10.568] t=7596.000000 W SOURce:LIST:VOLTage 140.57746,116.66659,132.7802,128.55889,120.19009,138.97496,113.17566,139.97638,118.2173,130.84036
  [15:58:10.599] t=7596.031000 R *ESR? -> 0
  ```
- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 6112; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [16:04:41.910] t=7987.343000 W LIST:VOLTage 127,127
  [16:04:41.940] t=7987.359000 R *ESR? -> 0
  ```

(scpi-list-dwell)=

## `SOURce:LIST:DWELl`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Programa quanto tempo (s) cada passo da lista dura.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `[SOURce:]LIST:DWELl <s>,<s>,...`
- **Parâmetros e unidades:** Na captura por TRACe: `pontos_por_ciclo / 30000` em cada passo, isto é, **um período exato** da frequência (0,02 s a 50 Hz; 1/60 s a 60 Hz), para que cada TRACe termine quando o ciclo real dela termina. Na classe 18: metade da duração em cada um dos dois pontos.
- **Sincronismo e ordem:** Mesmo regime de {scpi}`SOURce:LIST:FUNCtion:SHAPe`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.program_capture` ([ametek_orm.py:1646](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1646)); `AmetekMX30.frequency_drift_list` ([ametek_orm.py:1097](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1097))
- **Manual:** p. 91.
- **Classes que usam:** 06 a 17, 20 (E33); 18 (E23)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 948; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:58:10.660] t=7596.093000 W SOURce:LIST:DWELl 0.02,0.02,0.02,0.02,0.02,0.02,0.02,0.02,0.02,0.02
  [15:58:10.710] t=7596.140000 R *ESR? -> 0
  ```
- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 6116; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [16:04:41.940] t=7987.359000 W LIST:DWELl 0.1,0.1
  [16:04:41.975] t=7987.406000 R *ESR? -> 0
  ```

(scpi-list-repeat)=

## `SOURce:LIST:REPeat`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Programa quantas vezes cada passo se repete; o projeto manda `0` em todos.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:LIST:REPeat <n>,<n>,...` (o manual escreve `[SOURce:]LIST:REPeat[:COUNt]`)
- **Parâmetros e unidades:** `0` em cada passo. O valor `1` era lido pelo firmware como "repete uma vez", tocando cada ciclo **duas vezes**: o NOTCH levou 516 ms em vez de cerca de 200 ms (2,58 vezes os ~200 ms nominais de 12 ciclos a 60 Hz), e com `0` caiu para 438 ms, cuja causa completa não foi explicada (A4, v1.9 e v1.10).
- **Sincronismo e ordem:** Programado depois dos três comandos de dados e antes de {scpi}`SOURce:LIST:COUNt`.
- **Erros e quirks:** O sufixo `:COUNt` é rejeitado (`-113`) e o prefixo `SOURce:` é obrigatório (A5; ver [comandos que não funcionam](#scpi-nf-repeat-count)).
- **Quem envia:** `AmetekMX30.program_capture` ([ametek_orm.py:1665](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1665)); `AmetekMX30.frequency_drift_list` ([ametek_orm.py:1103](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1103))
- **Manual:** p. 94.
- **Classes que usam:** 06 a 17, 20 e 18

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 958; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:58:10.776] t=7596.203000 W SOURce:LIST:REPeat 0,0,0,0,0,0,0,0,0,0
  [15:58:10.825] t=7596.250000 R *ESR? -> 0
  ```

(scpi-list-count)=

## `SOURce:LIST:COUNt`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Quantas vezes a lista inteira é percorrida a cada trigger.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `[SOURce:]LIST:COUNt <n>`
- **Parâmetros e unidades:** `1`.
- **Sincronismo e ordem:** Depois de {scpi}`SOURce:LIST:REPeat`. Na classe 18 a forma sem prefixo é `LIST:COUNt 1`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.program_capture` ([ametek_orm.py:1666](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1666)); `AmetekMX30.frequency_drift_list` ([ametek_orm.py:1104](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1104))
- **Manual:** p. 91.
- **Classes que usam:** 06 a 17, 20 (E36); 18 (E25)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 965; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:58:10.862] t=7596.281000 W SOURce:LIST:COUNt 1
  [15:58:10.890] t=7596.312000 R *ESR? -> 0
  ```
- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 6124; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [16:04:42.006] t=7987.437000 W LIST:COUNt 1
  [16:04:42.036] t=7987.468000 R *ESR? -> 0
  ```

(scpi-list-step)=

## `SOURce:LIST:STEP`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Define como a lista avança de um passo ao seguinte: `AUTO` avança sozinha ao fim do dwell.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `[SOURce:]LIST:STEP AUTO|ONCE`
- **Parâmetros e unidades:** `AUTO`.
- **Sincronismo e ordem:** Depois de {scpi}`SOURce:LIST:COUNt`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `AmetekMX30.program_capture` ([ametek_orm.py:1667](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1667)); `AmetekMX30.frequency_drift_list` ([ametek_orm.py:1105](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1105))
- **Manual:** p. 94.
- **Classes que usam:** 06 a 17, 20 (E37); 18 (E26)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 972; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:58:10.926] t=7596.359000 W SOURce:LIST:STEP AUTO
  [15:58:10.968] t=7596.390000 R *ESR? -> 0
  ```
- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 6128; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [16:04:42.036] t=7987.468000 W LIST:STEP AUTO
  [16:04:42.072] t=7987.500000 R *ESR? -> 0
  ```

(scpi-list-function-points)=
(scpi-list-voltage-points)=
(scpi-list-dwell-points)=
(scpi-list-repeat-points)=

## `SOURce:LIST:FUNCtion:POINts?`

{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE` O selo vale para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições do exemplo, não para o efeito físico.

**O que faz?** **Devolve quantos pontos a lista de formas tem; as outras três consultas `:POINts?` fazem o mesmo para tensão, dwell e repeat.**

- **Instrumento:** AMETEK MX30-3Pi, Rev. 5.53
- **Sintaxe:** `SOURce:LIST:FUNCtion:POINts?`, `SOURce:LIST:VOLTage:POINts?`, `SOURce:LIST:DWELl:POINts?`, `SOURce:LIST:REPeat:POINts?`; todas devolvem um inteiro
- **Parâmetros e unidades:** Sem parâmetros. Cada eixo tem a sua própria consulta, independente das outras.
- **Sincronismo e ordem:** `program_capture` consulta cada eixo **imediatamente** depois de gravá-lo (função, tensão e dwell) e exige o número de ciclos. `arm_transient` repete as quatro, mais `OUTPut:STATe?`, `FUNCtion:MODE?`, `VOLTage:MODE?`, `SOURce:FREQuency:MODE?` e `TRIGger:SOURce?` (nove consultas) e recusa a captura se qualquer uma divergir.
- **Erros e quirks:** `REPeat:POINts?` aceita `1` ou o número de ciclos: o comentário do código e a quirk A5 dizem que a Rev. 5.53 devolve `1` mesmo com a lista de valores unitários, mas o exemplo real de 07/10 (E35, 127 V/50 Hz) devolveu 10, igual ao número de ciclos; o código aceita os dois.
- **Quem envia:** `AmetekMX30.program_capture` ([ametek_orm.py:1644](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1644)); `AmetekMX30.arm_transient` ([ametek_orm.py:1850](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1850)); `AmetekMX30.arm_transient` (REPeat) ([ametek_orm.py:1853](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1853))
- **Manual:** pp. 91-96 (uma consulta por comando de lista).
- **Classes que usam:** 06 a 17, 20 (05 acima de 20 %)

- **Exemplo real** (127 V/50 Hz; sessão `sessao_2026-10-07_127V_50Hz`, `scpi_transcricao.log`, linha 935; `W` = escrita, `Q` = pedido, `R` = resposta):

  ```text
  [15:58:10.538] t=7595.968000 Q SOURce:LIST:FUNCtion:POINts?
  [15:58:10.564] t=7595.984000 W SOURce:LIST:FUNCtion:POINts?
  [15:58:10.568] t=7596.000000 R SOURce:LIST:FUNCtion:POINts? -> 10
  ```
- **Outros usos na mesma transcrição:** E69 (linha 945, 127 V/50 Hz), E70 (linha 955, 127 V/50 Hz), E35 (linha 1062, 127 V/50 Hz). Índice em {doc}`transcricoes`.
