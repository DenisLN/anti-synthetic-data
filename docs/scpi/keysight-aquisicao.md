# Keysight: aquisição e escala

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE`

**Pergunta:** como o osciloscópio é configurado para entregar 6000 pontos a 30 kSa/s com o trigger no lugar certo? **Resposta:** modo automático de memória (o Digitizer foi descartado), referência horizontal `CUSTom` na borda esquerda e posição igual a menos o pré-trigger, canal 1 em DC com escala de um terço do pico esperado; o trigger vem do BNC do BOT da AMETEK.

:::{caution} Limitação
O Keysight não tem transcrição SCPI real: o `scpi_transcricao.log` registra só a fonte, e o tráfego do PyMeasure nunca foi gravado. Todos os exemplos desta e das duas páginas seguintes são **derivados do código**, com selo NÃO VERIFICADO; as páginas do manual marcadas com `~` foram localizadas por busca no texto extraído e não conferidas no PDF.
:::

(scpik-idn)=

## `*IDN?`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Identifica o osciloscópio; o código exige que a resposta contenha `DSOX4034A`.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `*IDN?`
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** Primeira consulta depois de abrir o recurso VISA (`verify_identity`).
- **Erros e quirks:** Modelo diferente: `OscilloscopeError("Osciloscópio inesperado")`.
- **Quem envia:** `KeysightDSOX4034A.verify_identity` ([oscilloscope_orm.py:79](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L79))
- **Manual:** [KS] p. 248.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  Q *IDN?
  ```

(scpik-system-error)=

## `:SYSTem:ERRor?`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Lê um erro da fila do osciloscópio; o código repete até `0`.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:SYSTem:ERRor?` devolve `<código>,"<mensagem>"`
- **Parâmetros e unidades:** Sem parâmetros; no máximo 20 leituras por chamada.
- **Sincronismo e ordem:** Conferência que fecha cada configuração (`assert_no_errors`).
- **Erros e quirks:** Fila que não esvazia ou resposta fora do formato: `OscilloscopeError`.
- **Quem envia:** `KeysightDSOX4034A.check_errors` ([oscilloscope_orm.py:89](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L89))
- **Manual:** [KS] p. ~1311.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  Q :SYSTem:ERRor?
  ```

(scpik-cls)=

## `*CLS`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Limpa a fila de erros e os registradores de status do osciloscópio.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `*CLS`
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** Em `initialize_safe`, logo depois de `:STOP`. O osciloscópio não usa `*ESR?` a cada escrita como a fonte; só confere a fila nos pontos de `assert_no_errors`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.initialize_safe` ([oscilloscope_orm.py:107](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L107))
- **Manual:** [KS] p. 245.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W *CLS
  ```

(scpik-stop)=

## `:STOP`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Para a aquisição em curso.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:STOP`
- **Parâmetros e unidades:** Sem parâmetros.
- **Sincronismo e ordem:** Primeiro comando de `initialize_safe` e de `configure_acquisition`, e único de `safe_stop` (usado no `close`). **Não** fecha o `ResourceManager` do PyVISA: fechá-lo no Windows invalidou a sessão ASRL da fonte, que ainda precisava receber `OUTPUT OFF` (B3).
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.initialize_safe` ([oscilloscope_orm.py:106](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L106)); `KeysightDSOX4034A.configure_acquisition` ([oscilloscope_orm.py:238](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L238)); `KeysightDSOX4034A.safe_stop` ([oscilloscope_orm.py:541](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L541))
- **Manual:** [KS] p. 308.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :STOP
  ```

(scpik-acquire-type)=

## `:ACQuire:TYPE`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Define o tipo de aquisição; o projeto usa `NORMal` (sem média nem pico).**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:ACQuire:TYPE NORMal`
- **Parâmetros e unidades:** `NORMal`.
- **Sincronismo e ordem:** Em `initialize_safe` e `configure_acquisition`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.initialize_safe` ([oscilloscope_orm.py:108](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L108)); `KeysightDSOX4034A.configure_acquisition` ([oscilloscope_orm.py:239](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L239))
- **Manual:** [KS] p. ~330.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :ACQuire:TYPE NORMal
  ```

(scpik-acquire-mode)=

## `:ACQuire:MODE`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Seleciona aquisição em tempo real (`RTIMe`).**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:ACQuire:MODE RTIMe`
- **Parâmetros e unidades:** `RTIMe`.
- **Sincronismo e ordem:** Em `configure_acquisition`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.configure_acquisition` ([oscilloscope_orm.py:240](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L240))
- **Manual:** [KS] p. ~319.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :ACQuire:MODE RTIMe
  ```

(scpik-acquire-digitizer)=

## `:ACQuire:DIGitizer`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Liga ou desliga o modo Digitizer; o projeto o mantém `OFF`.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:ACQuire:DIGitizer OFF`
- **Parâmetros e unidades:** `OFF`.
- **Sincronismo e ordem:** Em `configure_acquisition`. Pontos ou taxa explícitos ligam o Digitizer no firmware 07.30; ele exige `REFerence CENTer` (não aceita `LEFT` nem `CUSTom`), não entrega 36 000 pontos a 30 kSa/s (`-221`, `-222`) e foi **descartado** na v1.10 (K3). Não tentar de novo sem reler `CHANGELOG/v1.10.md`.
- **Erros e quirks:** Sem erro com `OFF`.
- **Quem envia:** `KeysightDSOX4034A.configure_acquisition` ([oscilloscope_orm.py:241](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L241))
- **Manual:** [KS] p. ~318.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :ACQuire:DIGitizer OFF
  ```

(scpik-acquire-points-analog)=
(scpik-acquire-points-analog-auto)=

## `:ACQuire:POINts:ANALog`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Liga a profundidade de memória automática e lê o número de pontos que o osciloscópio vai usar.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:ACQuire:POINts:ANALog:AUTO ON` e `:ACQuire:POINts:ANALog?`
- **Parâmetros e unidades:** `ON` (modo automático).
- **Sincronismo e ordem:** O modo automático entrega cerca de 32,3 a 32,7 mil pontos por aquisição `:SINGle`, praticamente constante e independente da janela pedida (K3, v1.10). Parado, o firmware 07.30 informou 3000 pontos, então a suficiência real é validada pela preamble depois da captura (`get_waveform` exige pelo menos 6000 pontos).
- **Erros e quirks:** `actual_points <= 0`: `OscilloscopeError("Aquisição insuficiente")`.
- **Quem envia:** `KeysightDSOX4034A.configure_acquisition` (ligar) ([oscilloscope_orm.py:253](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L253)); `KeysightDSOX4034A.configure_acquisition` (ler) ([oscilloscope_orm.py:266](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L266))
- **Manual:** [KS] p. 320.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :ACQuire:POINts:ANALog:AUTO ON
  ```

(scpik-acquire-srate-analog)=
(scpik-acquire-srate-analog-auto)=

## `:ACQuire:SRATe:ANALog`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Liga a taxa de amostragem automática e lê a taxa efetiva.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:ACQuire:SRATe:ANALog:AUTO ON` e `:ACQuire:SRATe:ANALog?`
- **Parâmetros e unidades:** `ON`.
- **Sincronismo e ordem:** A taxa lida precisa ser pelo menos 0,995 × 30 kSa/s. A taxa bruta real (cerca de 116,7 kSa/s na sessão de 30/09/2026) não é 30 kSa/s: `get_waveform` reamostra por interpolação linear, sem anti-aliasing (K4, P-28).
- **Erros e quirks:** Taxa abaixo do mínimo: `OscilloscopeError("Aquisição insuficiente")`.
- **Quem envia:** `KeysightDSOX4034A.configure_acquisition` (ligar) ([oscilloscope_orm.py:254](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L254)); `KeysightDSOX4034A.configure_acquisition` (ler) ([oscilloscope_orm.py:267](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L267)); `KeysightDSOX4034A.sample_rate` ([oscilloscope_orm.py:445](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L445))
- **Manual:** [KS] p. ~321.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :ACQuire:SRATe:ANALog:AUTO ON
  ```

(scpik-timebase-mode)=

## `:TIMebase:MODE`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Seleciona a base de tempo principal (`MAIN`).**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:TIMebase:MODE MAIN`
- **Parâmetros e unidades:** `MAIN`.
- **Sincronismo e ordem:** Em `configure_acquisition`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `KeysightDSOX4034A.configure_acquisition` ([oscilloscope_orm.py:242](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L242))
- **Manual:** [KS] p. ~1333.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :TIMebase:MODE MAIN
  ```

(scpik-timebase-range)=

## `:TIMebase:RANGe`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Define a janela total de tempo visível, que vira a duração da captura.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:TIMebase:RANGe <s>` e `:TIMebase:RANGe?`
- **Parâmetros e unidades:** Segundos. `configure_acquisition` aceita só `pontos = taxa × duração`: 200 ms (6000 pontos a 30 kSa/s) ou, com as margens de 20 ms antes e 50 ms depois, 270 ms (8100 pontos).
- **Sincronismo e ordem:** Lido de volta e comparado com tolerância de 1 %.
- **Erros e quirks:** Janela diferente da pedida: `OscilloscopeError("Keysight aceitou janela ...")`.
- **Quem envia:** `KeysightDSOX4034A.configure_acquisition` ([oscilloscope_orm.py:243](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L243)); `KeysightDSOX4034A.configure_acquisition` (leitura) ([oscilloscope_orm.py:268](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L268))
- **Manual:** [KS] p. 1335.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :TIMebase:RANGe 0.27
  ```

(scpik-timebase-reference)=

## `:TIMebase:REFerence`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Escolhe onde, na tela, fica a referência horizontal do tempo; o projeto a põe **exatamente na borda esquerda**.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:TIMebase:REFerence CUSTom|LEFT` e `:TIMebase:REFerence?`
- **Parâmetros e unidades:** `CUSTom` com {scpik}`:TIMebase:REFerence:LOCation` `0.0`; se o firmware recusar, `LEFT` com compensação de uma divisão em {scpik}`:TIMebase:POSition`.
- **Sincronismo e ordem:** Programado antes da posição. `:TIMebase:REFerence LEFT` **não** é a borda: o manual ([KS] p. 1337) diz "one division from the left side of the screen", e uma divisão é 10 % do `RANGe` ([KS] p. 1335). O "atraso de 20 ms" da v1.7 e o "atraso de 100 ms" da v1.10 eram esse artefato (H-REF10, K1). O que valeu fica em `referencia_horizontal_efetiva` no metadata.
- **Erros e quirks:** Recusa de `CUSTom`: aviso e queda para `LEFT` compensada, sem aborto.
- **Quem envia:** `KeysightDSOX4034A._programar_referencia_horizontal` ([oscilloscope_orm.py:327](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L327)); `KeysightDSOX4034A._programar_referencia_horizontal` (queda) ([oscilloscope_orm.py:332](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L332))
- **Manual:** [KS] pp. 1337-1338.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :TIMebase:REFerence CUSTom
  ```

(scpik-timebase-reference-location)=

## `:TIMebase:REFerence:LOCation`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Posiciona a referência customizada na tela; `0.0` é a borda esquerda.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:TIMebase:REFerence:LOCation 0.0` e a consulta correspondente
- **Parâmetros e unidades:** `0.0`.
- **Sincronismo e ordem:** Lida de volta junto com {scpik}`:TIMebase:REFerence`; qualquer valor diferente de `CUST`/`0.0` aciona a queda para `LEFT`.
- **Erros e quirks:** Ver {scpik}`:TIMebase:REFerence`.
- **Quem envia:** `KeysightDSOX4034A._programar_referencia_horizontal` ([oscilloscope_orm.py:313](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L313))
- **Manual:** [KS] p. 1338.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :TIMebase:REFerence:LOCation 0.0
  ```

(scpik-timebase-position)=

## `:TIMebase:POSition`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Define o tempo entre o trigger e a referência: `posição = t_referência − t_trigger`; o projeto usa **−pré-trigger**.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:TIMebase:POSition <s>`
- **Parâmetros e unidades:** Com `CUSTom`/`0.0`: `−pré_trigger`. Com `LEFT`: `−pré_trigger + RANGe/10`. Sinal positivo faz a janela só começar depois do trigger e pula o distúrbio (K2).
- **Sincronismo e ordem:** Programado uma vez em `configure_acquisition` e de novo por captura (`definir_pre_trigger`) quando o início do distúrbio é sorteado (v1.15). O instante em que o trigger de fato caiu volta na preamble (`ultimo_indice_trigger`).
- **Erros e quirks:** Pré-trigger fora de `[0, duração)`: `ValueError` antes de qualquer SCPI.
- **Quem envia:** `KeysightDSOX4034A.definir_pre_trigger` ([oscilloscope_orm.py:353](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L353))
- **Manual:** [KS] p. 1334.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :TIMebase:POSition -0.02
  ```

(scpik-channel-n-display)=

## `:CHANnel<n>:DISPlay`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Liga ou desliga a exibição do canal.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:CHANnel<n>:DISPlay 1|0`
- **Parâmetros e unidades:** CH1 sempre ligado; CH2 só com `CAPTURE_CURRENT`. Só funciona como **escrita**: o getter lançava `KeyError` (K9, Bug C da v1.10).
- **Sincronismo e ordem:** Propriedade `OscChannel.display` do PyMeasure; o `configure_channel` confere a fila depois de todas as propriedades.
- **Erros e quirks:** Getter: ver K9.
- **Quem envia:** `OscChannel.display` ([oscilloscope_orm.py:44](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L44))
- **Manual:** [KS] p. 362.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :CHANnel1:DISPlay 1
  ```

(scpik-channel-n-probe)=

## `:CHANnel<n>:PROBe`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Informa o fator de atenuação da probe, para o osciloscópio exibir a tensão real.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:CHANnel<n>:PROBe <fator>`
- **Parâmetros e unidades:** `VOLTAGE_PROBE_ATTENUATION` (digitado pelo operador no início do `START_BENCH`; **não inventar**). O PyMeasure formata com `%e`.
- **Sincronismo e ordem:** Em `configure_channel`.
- **Erros e quirks:** Fator não positivo: `ValueError`.
- **Quem envia:** `OscChannel.probe` ([oscilloscope_orm.py:55](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L55))
- **Manual:** [KS] p. ~368.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :CHANnel1:PROBe 5.000000e+02
  ```

(scpik-channel-n-coupling)=

## `:CHANnel<n>:COUPling`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Seleciona o acoplamento do canal; o projeto usa `DC`.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:CHANnel<n>:COUPling AC|DC`
- **Parâmetros e unidades:** `DC`.
- **Sincronismo e ordem:** Em `configure_channel`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `OscChannel.coupling` ([oscilloscope_orm.py:36](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L36))
- **Manual:** [KS] p. 361.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :CHANnel1:COUPling DC
  ```

(scpik-channel-n-units)=

## `:CHANnel<n>:UNITs`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Define a unidade vertical do canal (`VOLT` ou `AMP`).**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:CHANnel<n>:UNITs VOLT|AMP`
- **Parâmetros e unidades:** `VOLT` no CH1; `AMP` no CH2 (captura de corrente, desligada por padrão).
- **Sincronismo e ordem:** Em `configure_channel`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `OscChannel.units` ([oscilloscope_orm.py:62](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L62))
- **Manual:** [KS] p. 385.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :CHANnel1:UNITs VOLT
  ```

(scpik-channel-n-offset)=

## `:CHANnel<n>:OFFSet`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Define o offset vertical do canal; o projeto usa `0`.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:CHANnel<n>:OFFSet <V>`
- **Parâmetros e unidades:** `0`. A sonda diferencial de 500× tem offset DC próprio: 9 V de DC na escala de 180 V de pico fica no fundo de escala (erro de 4,35 V só do offset da probe, B5); a medida absoluta de DC não é confiável, e a classe 19 usa a medida da fonte.
- **Sincronismo e ordem:** Em `configure_channel` e em `set_vertical_scale`, que zera o offset antes de mudar a escala.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `OscChannel.offset` ([oscilloscope_orm.py:52](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L52)); `KeysightDSOX4034A.set_vertical_scale` ([oscilloscope_orm.py:157](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L157))
- **Manual:** [KS] p. 366.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :CHANnel1:OFFSet 0.000000e+00
  ```

(scpik-channel-n-scale)=

## `:CHANnel<n>:SCALe`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Define a escala vertical (V/div). O projeto programa `pico/3` para que 3 das 4 divisões de cada polaridade cubram o pico esperado.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:CHANnel<n>:SCALe <V/div>` e `:CHANnel<n>:SCALe?`
- **Parâmetros e unidades:** Inicial: `EUT_MAX_PEAK_V / 3`. Por captura, `set_vertical_scale` usa `pico/3`, reajusta para `pico/2` se `4 × escala < 1,05 × pico` e levanta erro se ainda não cobrir.
- **Sincronismo e ordem:** A escala real usada fica em `ultima_escala_vertical_v` (metadata `escala_vertical_v`): sem ela não dá para saber quantos LSB do conversor o sinal ocupava, o que importa para decidir se a classe 19 mediu a fonte ou o ruído do ADC (K10, ≈ 2 LSB). `Bancada.from_env` lê `CHANnel1:SCALe?` de volta.
- **Erros e quirks:** Escala que não cobre o pico: `OscilloscopeError("CH1 cobre apenas ...")`.
- **Quem envia:** `OscChannel.scale` ([oscilloscope_orm.py:58](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L58)); `KeysightDSOX4034A.set_vertical_scale` ([oscilloscope_orm.py:164](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L164))
- **Manual:** [KS] p. 384.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :CHANnel1:SCALe 1.386000e+02
  ```

(scpik-channel-n-bwlimit)=

## `:CHANnel<n>:BWLimit`

{bdg-warning}`NÃO VERIFICADO` {bdg-info}`OFFLINE` Comando conferido no código e no manual; sem transcrição real.

**O que faz?** **Liga ou desliga o filtro de limite de banda do canal; o projeto o mantém desligado.**

- **Instrumento:** Keysight DSO-X 4034A, firmware 07.30
- **Sintaxe:** `:CHANnel<n>:BWLimit 1|0`
- **Parâmetros e unidades:** `0`.
- **Sincronismo e ordem:** Em `configure_channel`.
- **Erros e quirks:** Sem erro conhecido.
- **Quem envia:** `OscChannel.bwlimit` ([oscilloscope_orm.py:29](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L29))
- **Manual:** [KS] p. 360.
- **Classes que usam:** todas

- **Exemplo:** exemplo derivado do código, transcrição NÃO VERIFICADA (o `scpi_transcricao.log` registra só a fonte; o Keysight não tem transcrição, e o tráfego do PyMeasure nunca foi gravado):

  ```text
  W :CHANnel1:BWLimit 0
  ```
