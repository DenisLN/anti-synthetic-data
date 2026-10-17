# Keysight: trigger e estado

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE`

**Pergunta:** como o osciloscópio é armado e como o código sabe que a captura terminou? **Resposta:** `:AER?` e `:TER?` zeram os registradores, `:SINGle` arma (a cada captura), o bit 32 de `:OPERegister:CONDition?` diz que espera o trigger, e a captura só termina quando `:TER?` é 1 **e** o bit 8 (RUN) apagou; o disparo vem do pulso BOT da AMETEK no `EXT Trigger`.

(scpik-external-probe)=

## `:EXTernal:PROBe`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Informa a atenuação da entrada de trigger externo (`EXT Trigger`).**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:EXTernal:PROBe <fator>`
- **Parâmetros e unidades:** `EXT_TRIGGER_PROBE_ATTENUATION` (padrão 1,0, [mestre.py:413](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L413)).
- **Sincronismo e ordem:** Primeiro comando de `setup_external_trigger`; a fila é conferida depois de todos.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.setup_external_trigger` ([oscilloscope_orm.py:368](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L368))
- **Manual:** [KS] p. 455.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :EXTernal:PROBe 1
  ```

(scpik-external-units)=

## `:EXTernal:UNITs`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Define a unidade da entrada externa (`VOLT`).**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:EXTernal:UNITs VOLT`
- **Parâmetros e unidades:** `VOLT`.
- **Sincronismo e ordem:** Em `setup_external_trigger`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.setup_external_trigger` ([oscilloscope_orm.py:369](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L369))
- **Manual:** [KS] p. 457.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :EXTernal:UNITs VOLT
  ```

(scpik-external-range)=

## `:EXTernal:RANGe`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Define a faixa da entrada externa e a lê de volta para validar o nível do trigger.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:EXTernal:RANGe <V>` e `:EXTernal:RANGe?`
- **Parâmetros e unidades:** `EXT_TRIGGER_RANGE_V` (padrão 8 V, [mestre.py:414](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L414)).
- **Sincronismo e ordem:** Depois de configurar, o código lê a faixa e recusa se `|nível| >= faixa`.
- **Erros e quirks:** `OscilloscopeError("Nível de trigger ... fora da faixa externa")`.
- **Quem envia:** `KeysightDSOX4034A.setup_external_trigger` ([oscilloscope_orm.py:370](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L370)); `KeysightDSOX4034A.setup_external_trigger` (leitura) ([oscilloscope_orm.py:380](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L380))
- **Manual:** [KS] p. 456.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :EXTernal:RANGe 8
  ```

(scpik-trigger-hfreject)=

## `:TRIGger:HFReject`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Desliga o filtro de rejeição de alta frequência do trigger.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:TRIGger:HFReject OFF`
- **Parâmetros e unidades:** `OFF`.
- **Sincronismo e ordem:** Em `setup_external_trigger`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.setup_external_trigger` ([oscilloscope_orm.py:371](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L371))
- **Manual:** [KS] p. 1350.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :TRIGger:HFReject OFF
  ```

(scpik-trigger-mode)=

## `:TRIGger:MODE`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Seleciona o tipo de trigger; o projeto usa `EDGE` (borda).**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:TRIGger:MODE EDGE`
- **Parâmetros e unidades:** `EDGE`.
- **Sincronismo e ordem:** Em `setup_external_trigger`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.setup_external_trigger` ([oscilloscope_orm.py:372](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L372))
- **Manual:** [KS] p. 1358.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :TRIGger:MODE EDGE
  ```

(scpik-trigger-sweep)=

## `:TRIGger:SWEep`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Seleciona o modo de varredura do trigger; `NORMal` espera o evento, sem disparar sozinho.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:TRIGger:SWEep NORMal`
- **Parâmetros e unidades:** `NORMal`.
- **Sincronismo e ordem:** Em `setup_external_trigger`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.setup_external_trigger` ([oscilloscope_orm.py:373](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L373))
- **Manual:** [KS] p. 1360.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :TRIGger:SWEep NORMal
  ```

(scpik-trigger-edge-source)=

## `:TRIGger:EDGE:SOURce`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Escolhe a fonte do trigger de borda; o projeto usa `EXTernal`, o pulso BOT da AMETEK pelo BNC.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:TRIGger:EDGE:SOURce EXTernal`
- **Parâmetros e unidades:** `EXTernal`.
- **Sincronismo e ordem:** Em `setup_external_trigger`. O pulso vem de {scpi}`OUTPut:TTLTrg` e `BOT` da fonte.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.setup_external_trigger` ([oscilloscope_orm.py:374](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L374))
- **Manual:** [KS] capítulo `:TRIGger[:EDGE]` (página exata NÃO VERIFICADA).
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :TRIGger:EDGE:SOURce EXTernal
  ```

(scpik-trigger-edge-level)=

## `:TRIGger:EDGE:LEVel`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Define o nível de disparo (V) na entrada externa.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:TRIGger:EDGE:LEVel <V>`
- **Parâmetros e unidades:** `EXT_TRIGGER_LEVEL_V` (padrão 1,5 V, [mestre.py:415](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L415)).
- **Sincronismo e ordem:** Em `setup_external_trigger`; o código recusa nível maior ou igual à faixa externa.
- **Erros e quirks:** Ver {scpik}`:EXTernal:RANGe`.
- **Quem envia:** `KeysightDSOX4034A.setup_external_trigger` ([oscilloscope_orm.py:375](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L375))
- **Manual:** [KS] capítulo `:TRIGger[:EDGE]` (página exata NÃO VERIFICADA).
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :TRIGger:EDGE:LEVel 1.5
  ```

(scpik-trigger-edge-slope)=

## `:TRIGger:EDGE:SLOPe`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Escolhe a borda que dispara; `POSitive` é a subida do pulso BOT.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:TRIGger:EDGE:SLOPe POSitive|NEGative|EITHer|ALTernate`
- **Parâmetros e unidades:** `POSitive`.
- **Sincronismo e ordem:** Em `setup_external_trigger`.
- **Erros e quirks:** Valor fora do conjunto: `ValueError` antes de qualquer SCPI.
- **Quem envia:** `KeysightDSOX4034A.setup_external_trigger` ([oscilloscope_orm.py:376](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L376))
- **Manual:** [KS] p. 218 (tabela do comando); capítulo `:TRIGger[:EDGE]`.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :TRIGger:EDGE:SLOPe POSITIVE
  ```

(scpik-trigger-force)=

## `:TRIGger:FORCe`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Força um disparo, sem passar pelo BNC.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:TRIGger:FORCe`
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** Usado só pela cadeia de medição (`medir_vrms_forcado`) para medir a saída em regime sem depender do trigger externo. **Não** testa o caminho BNC.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.force_trigger` ([oscilloscope_orm.py:393](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L393))
- **Manual:** [KS] p. 1349.
- **Classes que usam:** nenhuma classe (cadeia de medição)

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :TRIGger:FORCe
  ```

(scpik-aer)=

## `:AER?`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Lê e zera o registrador de eventos de aquisição armada.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:AER?` devolve `0` ou `1`
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** Em `arm()`, antes de {scpik}`:SINGle`: zera o registrador para que a próxima leitura de {scpik}`:TER?` seja da nova aquisição.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.arm` ([oscilloscope_orm.py:387](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L387))
- **Manual:** [KS] p. 272.
- **Classes que usam:** todas as classes físicas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  Q :AER?
  ```

(scpik-ter)=

## `:TER?`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Lê e zera o registrador de eventos de trigger.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:TER?` devolve `0` ou `1`
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** `arm()` o zera; `wait_for_trigger_complete` o lê até `1`. O `:TER?` continua em 1 do último armamento se não for zerado (K5).
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.arm` ([oscilloscope_orm.py:388](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L388)); `KeysightDSOX4034A.wait_for_trigger_complete` ([oscilloscope_orm.py:435](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L435))
- **Manual:** [KS] p. 309.
- **Classes que usam:** todas as classes físicas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  Q :TER?
  ```

(scpik-single)=

## `:SINGle`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Arma uma aquisição única.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:SINGle`
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** **Precisa ser reenviado a cada captura** (K5). As nativas também armam o osciloscópio desde a v1.5. Depois dele o código espera o bit 32 de {scpik}`:OPERegister:CONDition?` (`wait_for_armed`).
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.arm` ([oscilloscope_orm.py:389](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L389))
- **Manual:** [KS] p. 306.
- **Classes que usam:** todas as classes físicas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :SINGle
  ```

(scpik-operegister-condition)=

## `:OPERegister:CONDition?`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Lê o registrador de condição de operação: o bit 32 indica "aguardando trigger" e o bit 8, "em execução".**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:OPERegister:CONDition?` devolve um inteiro
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** `is_armed` testa `valor & 32`; `wait_for_trigger_complete` exige `:TER?` = 1 **e** o bit 8 apagado (a aquisição `:SINGle` terminou). O guia recomenda exatamente esse polling para um DUT de disparo único.
- **Erros e quirks:** Prazo esgotado: `TimeoutError("Keysight não recebeu/concluiu o trigger externo")`.
- **Quem envia:** `KeysightDSOX4034A.is_armed` ([oscilloscope_orm.py:417](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L417)); `KeysightDSOX4034A.wait_for_trigger_complete` ([oscilloscope_orm.py:436](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L436))
- **Manual:** [KS] p. 292.
- **Classes que usam:** todas as classes físicas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  Q :OPERegister:CONDition?
  ```
