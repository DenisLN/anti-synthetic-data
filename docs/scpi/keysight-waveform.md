# Keysight: waveform e medidas

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE`

**Pergunta:** como o registro sai do osciloscópio e o que se valida antes de gravá-lo? **Resposta:** `:WAVeform:PREamble?` descreve o registro, `:WAVeform:DATA?` o entrega em bytes; o código recusa buracos, clipping, preamble malformada e taxa abaixo de 30 kSa/s, e reamostra para 30 kSa/s. Os extremos de verdade (`:MEASure:VMAX?` e `:VMIN?`) vêm do registro bruto do osciloscópio, não do vetor reamostrado.

(scpik-waveform-source)=

## `:WAVeform:SOURce`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Escolhe o canal cujo registro será lido.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:WAVeform:SOURce CHANnel<n>`
- **Parâmetros e unidades:** `CHANnel1` (e `CHANnel2` com captura de corrente).
- **Sincronismo e ordem:** Primeiro dos cinco comandos de preparação de `get_waveform`; nenhum é conferido individualmente: a conferência é a preamble que vem logo depois.
- **Erros e quirks:** Canal inválido: `ValueError` antes de qualquer SCPI.
- **Quem envia:** `KeysightDSOX4034A.get_waveform` ([oscilloscope_orm.py:451](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L451))
- **Manual:** [KS] p. 1467.
- **Classes que usam:** todas as classes físicas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :WAVeform:SOURce CHANnel1
  ```

(scpik-waveform-format)=

## `:WAVeform:FORMat`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Seleciona o formato dos dados do registro; o projeto usa `BYTE`.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:WAVeform:FORMat BYTE`
- **Parâmetros e unidades:** `BYTE` (um byte por amostra, 256 níveis).
- **Sincronismo e ordem:** Em `initialize_safe`, `configure_acquisition` e `get_waveform`. A preamble confirma o formato (`format_code == 0`).
- **Erros e quirks:** Formato diferente de `BYTE=0` na preamble: `OscilloscopeError`.
- **Quem envia:** `KeysightDSOX4034A.initialize_safe` ([oscilloscope_orm.py:109](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L109)); `KeysightDSOX4034A.get_waveform` ([oscilloscope_orm.py:452](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L452))
- **Manual:** [KS] p. 1455.
- **Classes que usam:** todas as classes físicas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :WAVeform:FORMat BYTE
  ```

(scpik-waveform-unsigned)=

## `:WAVeform:UNSigned`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Interpreta os bytes como números sem sinal.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:WAVeform:UNSigned ON`
- **Parâmetros e unidades:** `ON`.
- **Sincronismo e ordem:** Em `initialize_safe`, `configure_acquisition` e `get_waveform`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.get_waveform` ([oscilloscope_orm.py:453](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L453))
- **Manual:** [KS] p. 1473.
- **Classes que usam:** todas as classes físicas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :WAVeform:UNSigned ON
  ```

(scpik-waveform-points-mode)=

## `:WAVeform:POINts:MODE`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Escolhe qual conjunto de pontos do registro será lido: `RAW` na inicialização, `NORMal` na aquisição e na leitura.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:WAVeform:POINts:MODE RAW|NORMal`
- **Parâmetros e unidades:** `RAW` em `initialize_safe`; `NORMal` em `configure_acquisition` e `get_waveform`.
- **Sincronismo e ordem:** Sem conferência individual.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.initialize_safe` ([oscilloscope_orm.py:111](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L111)); `KeysightDSOX4034A.get_waveform` ([oscilloscope_orm.py:454](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L454))
- **Manual:** [KS] p. ~1457.
- **Classes que usam:** todas as classes físicas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :WAVeform:POINts:MODE NORMal
  ```

(scpik-waveform-points)=

## `:WAVeform:POINts`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Pede o número de pontos a transferir (60 000, mais do que o registro tem).**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:WAVeform:POINts 60000`
- **Parâmetros e unidades:** `60000`.
- **Sincronismo e ordem:** A quantidade real vem na preamble; o código exige `pontos >= expected_points` (6000 ou 8100).
- **Erros e quirks:** Preamble com menos pontos que o mínimo: `OscilloscopeError`.
- **Quem envia:** `KeysightDSOX4034A.configure_acquisition` ([oscilloscope_orm.py:256](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L256)); `KeysightDSOX4034A.get_waveform` ([oscilloscope_orm.py:455](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L455))
- **Manual:** [KS] p. 1456.
- **Classes que usam:** todas as classes físicas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :WAVeform:POINts 60000
  ```

(scpik-waveform-preamble)=

## `:WAVeform:PREamble?`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Devolve os dez campos que descrevem o registro: formato, tipo, pontos, contagem, incremento, origem e referência de X e de Y.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:WAVeform:PREamble?` devolve dez números separados por vírgula
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** `x_origin` é o instante, relativo ao trigger, da **primeira** amostra; `-x_origin × 30000` vira `ultimo_indice_trigger`, que alimenta `inicio_janela` no metadata e tudo que depende da posição do evento ([KS] pp. 1476-1477). Antes, o código jogava essa informação fora com `time_axis -= time_axis[0]` (H-REF10).
- **Erros e quirks:** Menos ou mais de 10 campos, NaN/Inf, formato diferente de BYTE, taxa abaixo de 30 kSa/s ou cobertura menor que o pedido: `OscilloscopeError`.
- **Quem envia:** `KeysightDSOX4034A.get_waveform` ([oscilloscope_orm.py:458](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L458))
- **Manual:** [KS] p. 1460.
- **Classes que usam:** todas as classes físicas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  Q :WAVeform:PREamble?
  ```

(scpik-waveform-data)=

## `:WAVeform:DATA?`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Transfere o registro como bloco binário IEEE 488.2.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:WAVeform:DATA?` devolve `#<n><tamanho><bytes>`
- **Parâmetros e unidades:** Sem parâmetros; lido com `query_binary_values` do PyVISA (`datatype='B'`).
- **Sincronismo e ordem:** Depois da leitura o código valida: tamanho igual ao da preamble; **nenhum código 0** (buraco) nem **1 ou 255** (clipping baixo/alto, reservados pelo guia, K8); taxa mínima de 30 kSa/s. O vetor é reamostrado por interpolação linear (`np.interp`, `oscilloscope_orm.py` linha 536) para a grade de 30 kSa/s, sem anti-aliasing (K4, P-28).
- **Erros e quirks:** Código 0: "amostra ausente"; 1/255: "sofreu clipping vertical".
- **Quem envia:** `KeysightDSOX4034A.get_waveform` ([oscilloscope_orm.py:478](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L478))
- **Manual:** [KS] p. 1453.
- **Classes que usam:** todas as classes físicas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  Q :WAVeform:DATA?
  ```

(scpik-measure-vmax)=

## `:MEASure:VMAX?`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Máximo do canal, **medido pelo osciloscópio no registro bruto**, não no vetor reamostrado.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:MEASure:VMAX? CHANnel<n>` devolve V
- **Parâmetros e unidades:** `CHANnel1`.
- **Sincronismo e ordem:** `medir_extremos` consulta VMAX e VMIN depois de cada captura; é o que o teto de pico e a recalibração usam. O array a 30 kSa/s subestima picos estreitos: um pico cai entre amostras (classe 08: 415,3 V no array com o teto em 415,8 V, K7). Medida inválida é `9.9E+37` ([KS] p. 614): `OscilloscopeError`, nunca tensão.
- **Erros e quirks:** `9.9E+37` ou valor não finito: `OscilloscopeError("... a forma de onda está na tela?")`.
- **Quem envia:** `KeysightDSOX4034A.medir_extremos` ([oscilloscope_orm.py:199](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L199))
- **Manual:** [KS] p. 677.
- **Classes que usam:** todas as classes físicas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  Q :MEASure:VMAX? CHANnel1
  ```

(scpik-measure-vmin)=

## `:MEASure:VMIN?`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Mínimo do canal, medido pelo osciloscópio no registro bruto.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:MEASure:VMIN? CHANnel<n>` devolve V
- **Parâmetros e unidades:** `CHANnel1`.
- **Sincronismo e ordem:** Idem {scpik}`:MEASure:VMAX?`.
- **Erros e quirks:** Idem.
- **Quem envia:** `KeysightDSOX4034A.medir_extremos` ([oscilloscope_orm.py:199](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L199))
- **Manual:** [KS] p. 678.
- **Classes que usam:** todas as classes físicas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  Q :MEASure:VMIN? CHANnel1
  ```

(scpik-measure-vrms)=

## `:MEASure:VRMS?`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Vrms do canal, componente AC, na janela inteira.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:MEASure:VRMS? DISPlay,AC,CHANnel<n>` devolve V rms
- **Parâmetros e unidades:** `DISPlay,AC,CHANnel1`.
- **Sincronismo e ordem:** Só em `medir_vrms_forcado`, depois de uma aquisição `:SINGle` com trigger forçado, para a cadeia de medição antes da primeira classe (razão CH1/fonte dentro de 10 %).
- **Erros e quirks:** Medida inválida (`9.9E+37`): `OscilloscopeError`. O comentário do código cita [KS] p. 700; a busca no texto extraído achou a seção na p. ~681.
- **Quem envia:** `KeysightDSOX4034A.medir_vrms_forcado` ([oscilloscope_orm.py:410](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L410))
- **Manual:** [KS] p. ~681.
- **Classes que usam:** nenhuma classe (cadeia de medição)

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  Q :MEASure:VRMS? DISPlay,AC,CHANnel1
  ```
