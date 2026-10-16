# Referência SCPI

{bdg-info}`OFFLINE` {bdg-success}`VERIFICADO NA BANCADA` {bdg-warning}`NÃO VERIFICADO` (Keysight)

**Pergunta:** que comandos SCPI o projeto envia, em que ordem, e o que cada um faz? **Resposta:** o projeto envia 55 comandos distintos à fonte AMETEK MX30-3Pi (Rev. 5.53) e 45 ao osciloscópio Keysight DSO-X 4034A (firmware 07.30); cada um tem uma **entrada própria** nas páginas abaixo, com sintaxe, parâmetros, sincronismo, erro típico, o método do projeto que o envia (`arquivo:linha`), a página do manual e um exemplo, real quando existe transcrição de bancada. Nenhum experimento escreve SCPI cru: tudo passa pelos métodos de `AmetekMX30` e `KeysightDSOX4034A`.

Como ler: todo comando SCPI no texto desta documentação é um link para a sua entrada (papel `` {scpi}`TRACe:DATA` `` para a AMETEK e `` {scpik}`:TIMebase:RANGe` `` para o Keysight). Quirks são citadas pelos códigos de {doc}`quirks` (A1 a A25 na fonte, K1 a K10 no osciloscópio, B1 a B9 na bancada).

## 1. Transporte e sincronismo (AMETEK)

A fonte fala SCPI pela USB virtual serial `ASRL10::INSTR` (COM10), 115200 baud, 8 bits, sem paridade, 1 stop, sem controle de fluxo (`VI_ASRL_FLOW_NONE`), terminador `\n` (`AmetekMX30._configure_visa_resource`, `ametek_orm.py:312`). Os números são os da bancada e fixos: `validate_bench_configuration` (`mestre.py`) recusa outra porta ou outro baud.

- **Cada comando vai com LF e, se `AMETEK_QUERY_EOT=1` (padrão), com o byte `0x04` em uma segunda transferência** (`_raw_write`, `ametek_orm.py:393`). Sem o EOT a fonte não executa comandos que não têm resposta (A23): `OUTPUT ON/OFF` ficava no buffer até a próxima consulta.
- **`write()` espera a fonte consumir o comando** com uma consulta `*ESR?` ({scpi}`*ESR?`; `*OPC?` se `AMETEK_SINCRONISMO=OPC`, sem ganho). A exceção são as três gravações em Flash ({scpi}`TRACe:DATA`, {scpi}`TRACe:DEFine`, {scpi}`TRACe:DELete:ALL`: `_SEM_SINCRONISMO`, `ametek_orm.py:177`). Bits de erro do ESR (0x04, 0x08, 0x10 e 0x20) viram aviso no log com o comando que os causou.
- **`query()` descarta o buffer de entrada antes, escreve com EOT e lê** (`ametek_orm.py:479`); resposta vazia é `CommunicationError`, com a lista de conferência (COM10, driver, 115200 baud, cabo).
- **Transcrição.** Todo `W`, `Q` e `R` entra no logger `AmetekORM.scpi` com `time.monotonic()` (gravado em `scpi_transcricao.log` da pasta da sessão); payloads maiores que 160 caracteres são truncados (`MAX_TRANSCRICAO_CHARS`). O Keysight (PyMeasure) não é transcrito. Formato e índice em {doc}`scpi/transcricoes`.

O histórico das três regras de ordem que valem para tudo está em {doc}`scpi/sequencias`: a gravação em rajada se perdia (v1.12), a consulta logo após `TRACe:DATA` travava a fonte (v1.12) e `SOURce:VOLTage:HIGH` é limite rms, não de pico (v1.12).

## 2. Como ler uma entrada

Cada entrada abre com a pergunta "o que faz?" e a resposta em negrito, e traz, nesta ordem: **instrumento**, **sintaxe**, **parâmetros e unidades**, **sincronismo e ordem**, **erros e quirks**, **quem envia** (método e `arquivo:linha`, conferidos contra o código em 2026-10-16), **manual** (página do PDF), **classes que usam** e **exemplo**. O selo da entrada resume o estado:

| Selo | Significado nesta referência |
|---|---|
| {bdg-success}`VERIFICADO NA BANCADA` | o comando aparece na transcrição de 07/10/2026 e a fonte respondeu `*ESR? -> 0` (ou devolveu o valor mostrado): vale para o fato "aceito" naquela condição, não para o efeito físico |
| {bdg-info}`OFFLINE` | conferido no código e, quando citado, no manual |
| {bdg-warning}`NÃO VERIFICADO` | sem transcrição real: "exemplo derivado do código, transcrição NÃO VERIFICADA" (todo o Keysight e alguns comandos da fonte) |

Páginas do manual: AMETEK = página do PDF `docs/AMETEK_MX_SCPI_Programming_Manual.pdf` (texto em `docs/manuais_txt/`); `[KS]` = Keysight 4000 X-Series Programmer's Guide. Os PDFs e os textos **não** entram no site publicado; o site cita a página e o comando.

## 3. Mapa das entradas

| Página | Conteúdo | Entradas |
|---|---|---|
| {doc}`scpi/sequencias` | sete sequências completas, com diagramas e o porquê da ordem | (sem entradas) |
| {doc}`scpi/ametek-estado` | identificação, erros, sincronismo, estado de trigger e saída | 12 |
| {doc}`scpi/ametek-baseline` | os 22 comandos do estado seguro inicial | 18 |
| {doc}`scpi/ametek-imediatos` | frequência e tensão imediatas, medidas `MEASure:*` | 8 |
| {doc}`scpi/ametek-nativo` | STEP, PULSe, CSINusoid, offset ACDC, lista de frequência | 6 |
| {doc}`scpi/ametek-lista-trace` | TRACe e lista (classes 06 a 17, 20 e 05 acima de 20 %) | 11 |
| {doc}`scpi/ametek-nao-funciona` | o que a Rev. 5.53 rejeita, ignora ou deixa sem resposta | 7 |
| {doc}`scpi/keysight-aquisicao` | aquisição, base de tempo e canal | 21 |
| {doc}`scpi/keysight-trigger` | trigger externo, armamento e registradores | 14 |
| {doc}`scpi/keysight-waveform` | registro, preamble e medidas de extremos | 10 |
| {doc}`scpi/diagnostico` | comandos que só existem em scripts de diagnóstico | (tabelas) |
| {doc}`scpi/transcricoes` | formato da transcrição e índice dos 71 trechos reais | (tabela) |

## 4. Cobertura e o que não foi coberto

:::{note} Nota de verificação
Conferido offline em 2026-10-16: todo comando que `ametek_orm.py` e `oscilloscope_orm.py` enviam (extraído por busca de padrões `write(...)`, `query(...)` e `ask(...)` nos dois arquivos) tem entrada ou está listado em {doc}`scpi/ametek-nao-funciona`; os comandos que só aparecem em `scripts/` e em `logica/preflight_new.py` estão em {doc}`scpi/diagnostico` e **não** têm entrada completa, porque não passam pelo ORM (nem por `validate_bench_configuration`).
:::

- **Divergência das páginas do manual na versão anterior desta página.** A tabela antiga citava, por exemplo, `VOLTage:MODE` nas pp. 90-153; a busca no texto extraído do manual coloca a descrição em p. 109 (e `VOLTage:TRIGgered` em p. 108, `PULSe:WIDTh` em p. 106). As páginas desta referência foram refeitas com a busca; as que o texto não permitiu confirmar levam `~` ou "NÃO VERIFICADO".
- **`SOURce:VOLTage:OFFSet`** não tem seção própria no manual: aparece como parâmetro de `VOLTage` (p. 108) e no erro `-300` do Apêndice C.
- **Consulta `TRACe:DATA? <nome>`** nunca foi executada na fonte real e o manual se contradiz (P-19, {doc}`scpi/ametek-lista-trace`).
- **Keysight.** Sem transcrição; exemplos derivados do código; páginas `~` conferidas só por busca no texto.

```{toctree}
:maxdepth: 1
:caption: Entradas da referência

scpi/sequencias
scpi/ametek-estado
scpi/ametek-baseline
scpi/ametek-imediatos
scpi/ametek-nativo
scpi/ametek-lista-trace
scpi/ametek-nao-funciona
scpi/keysight-aquisicao
scpi/keysight-trigger
scpi/keysight-waveform
scpi/diagnostico
scpi/transcricoes
```
