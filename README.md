# Bancada de instrumentação para dataset de qualidade de energia

Repositório da etapa inicial de um TCC cujo objetivo final é um analisador de
qualidade de energia embarcado num microcontrolador ESP32. Para treinar o
classificador que vai rodar no ESP32, primeiro é preciso um dataset rotulado
de distúrbios de tensão — e é isso que este repositório produz, tanto em
**simulação pura (Python/NumPy)** quanto em **bancada física real**
(AMETEK MX30-3Pi + Keysight DSO-X 4034A).

Este README cobre o básico de arquitetura (para quem vai mexer no código) e,
com mais profundidade, tudo que o **operador da bancada** precisa saber antes
de energizar qualquer coisa. Se você só vai apertar o botão, vá direto para a
[seção 5](#5-operação-na-bancada-física-o-que-o-operador-precisa-saber).

O histórico detalhado de decisões e mudanças de cada versão está em
[`CHANGELOG/`](CHANGELOG/) (`v1.0.md` a `v1.3.md`) — este README é um resumo
operacional, não substitui esses documentos.

---

## 1. Visão geral

A bancada física tem dois instrumentos, controlados via SCPI/VISA:

- **Fonte CA programável AMETEK MX30-3Pi** (California Instruments) — gera a
  tensão de alimentação e injeta os distúrbios.
- **Osciloscópio Keysight DSO-X 4034A** (série 4000X) — captura a forma de
  onda resultante.

Os dois são sincronizados por um cabo BNC: a saída de trigger da AMETEK
("Trigger Out") vai para o trigger externo do Keysight, de forma que o
osciloscópio sempre captura a partir do instante exato em que a fonte inicia
um distúrbio.

O produto do repositório são **20 classes de distúrbio** ([`experimentos.txt`](experimentos.txt)),
cada uma gerando (em modo simulado) milhares de capturas de 200 ms
(6000 amostras a 30 kSa/s), salvas em [`resultados/`](resultados/) como
`.npz` (dado puro + dado com AWGN por nível de SNR) e metadados em `.jsonl`.

Existem **dois modos de execução**, escolhidos por uma única variável de
ambiente (`BENCH_MODE`):

| Modo | Como ativar | O que faz | Quantas capturas |
|---|---|---|---|
| **SIMULADO** (padrão) | `BENCH_MODE` ausente/`0` | Nenhum hardware é aberto. Matemática pura em Python/NumPy. | `SIM_CAPTURES_PER_CLASS` (padrão 2000) por classe — é o que gera o dataset de treino. |
| **BANCADA** | `BENCH_MODE=1` | Abre AMETEK (serial/PyVISA) e Keysight (USB/VISA) de verdade, energiza a saída e captura fisicamente. | `REAL_CAPTURES_PER_CLASS` (padrão 1) por classe — é o comissionamento físico, para confirmar que a bancada real reproduz o que o modelo Python prevê. |

---

## 2. Estrutura de arquivos

A partir da v1.3, o repositório é dividido em três categorias claras:
**lógica** (Python puro, roda em qualquer SO), **scripts** (PowerShell/CMD,
específicos do fluxo de bancada Windows) e **experimentos** (as 20 classes,
que continuam soltas na raiz por serem carregadas dinamicamente por caminho,
não por nome de pacote).

```
logica/                     Todo o código Python "de motor" do projeto
    ametek_orm.py              Driver (ORM) da fonte AMETEK MX30 — classe AmetekMX30
    oscilloscope_orm.py        Driver (ORM) do osciloscópio Keysight — classe KeysightDSOX4034A
    sinais.py                  Matemática de sinal pura (janela, ruído AWGN, SNR medida, formas de onda)
    mestre.py                  Config + classes Bancada/ExperimentoBase + orquestração dos 20 experimentos
    preflight.py                Validação progressiva em bancada real, sem energizar por padrão

scripts/                    Todo o PowerShell/CMD que o operador roda no Windows
    bench_config.ps1           ÚNICA fonte de variáveis de ambiente da bancada física
    start_bench_windows.ps1    Fluxo guiado (-Stage Full/Communication/Trigger/LowVoltage/Run)
    START_BENCH.cmd            Ponto de entrada único do operador (chama -Stage Full)
    run_simulation_windows.ps1 Gera o dataset simulado (sem hardware)
    setup_windows.ps1          Cria/atualiza o venv (env/) e instala requirements.txt
    package_windows.ps1        Empacota o repositório em .zip para transporte

experimentos_nativos/       Classes cujo distúrbio é um recurso NATIVO da AMETEK (PULSe/LIST/CSINe)
    01.py .. 19.py           NORMAL, SAG, SWELL, INTERRUPTION, HARMONICS, FREQUENCY_DRIFT, DC_OFFSET

experimentos_waveform/      Classes que precisam de forma de onda arbitrária (TRACe)
    06.py .. 20.py           FLICKER, NOTCH, TRANSIENT, OSCILLATORY_TRANSIENT e composições

tests/test_offline.py       Testes sem hardware (ORMs em modo simulado, todas as 20 classes)

docs/                       Manuais SCPI da AMETEK e do Keysight (PDF)
resultados/                 Saída: dados puros, snr_XXdb/*.npz, metadata/*.jsonl
logs/                       Logs de cada execução de start_bench_windows.ps1
CHANGELOG/                  Histórico técnico detalhado de cada versão
```

`experimentos_nativos/NN.py` e `experimentos_waveform/NN.py` fazem
`from mestre import ExperimentoNativo` / `from sinais import ...` como se
esses módulos estivessem no mesmo diretório. Isso continua funcionando sem
nenhum ajuste nesses arquivos porque `logica/mestre.py` é sempre o script de
entrada do processo Python (`python logica\mestre.py` ou, indiretamente,
`python logica\preflight.py`) — o Python insere automaticamente o diretório
do script de entrada (`logica/`) no início do `sys.path`, tornando `mestre`
e `sinais` importáveis de qualquer módulo carregado depois, de qualquer
pasta. Só `tests/test_offline.py`, que roda fora desse fluxo, precisa inserir
`logica/` manualmente no `sys.path`.

---

## 3. Arquitetura (OOP e "ORM")

O projeto usa orientação a objetos onde ela realmente ajuda — encapsular o
estado e as regras de segurança de cada instrumento físico — e não a força em
lugares onde uma função simples já resolve.

### `AmetekMX30` ([logica/ametek_orm.py](logica/ametek_orm.py))

"ORM" no sentido de que mapeia objetos Python para comandos SCPI do
instrumento, do mesmo jeito que um ORM de banco mapeia objetos para SQL. Os
pontos centrais:

- **Limites de segurança no construtor.** `max_voltage_rms`, `max_peak_v` e
  `max_current_a` são passados uma vez (por `mestre.py`, a partir da config).
  Os *setters* (`voltage`, `frequency`, `current_limit`) e os métodos
  semânticos (`trigger_step`, `trigger_pulse`, `configure_harmonics_csine`,
  `frequency_drift_list`, `enable_dc_offset`) **recusam** qualquer valor fora
  desses limites, levantando `ParameterOutOfBoundsError`. Um experimento
  nunca sabe qual é o limite — ele só tenta setar um valor, e o objeto decide
  se é seguro.
- **Sem SCPI cru nos experimentos.** Nenhum `experimentos_*/NN.py` chama
  `fonte.write(...)` diretamente para programar um distúrbio — tudo passa
  pelos métodos semânticos validados acima.
- **Modo simulado embutido** (`simulated=True`): os métodos de escrita/
  consulta desviam para um dicionário interno em vez de abrir a porta serial.
  É o que permite `tests/test_offline.py` testar toda a lógica de
  programação de transientes sem hardware nenhum.

### `KeysightDSOX4034A` ([logica/oscilloscope_orm.py](logica/oscilloscope_orm.py))

Mesma ideia do lado do osciloscópio: encapsula canais, aquisição, trigger
externo e a decodificação do bloco binário IEEE 488.2 devolvido pelo
`:WAVeform:DATA?`. `OscChannel` é uma subclasse de
`pymeasure.instruments.Channel` que mapeia atributos de canal (escala,
offset, acoplamento) para os comandos SCPI via descritores `Channel.control`.

### `mestre.py` ([logica/mestre.py](logica/mestre.py)) — `Bancada` e a hierarquia de experimentos

- **`Config`**: `@dataclass(frozen=True)` — só dados (fs, pontos, tensão/
  frequência base, níveis de SNR, seeds, ...). Nenhum `experimentos_*/NN.py`
  importa `mestre` para pegar config; tudo chega por injeção de dependência.
- **`Bancada`**: encapsula `fonte`/`osc`/`config`. `Bancada.from_env(...)` é
  o ponto único de abertura de instrumentos e é um *context manager*
  (`with Bancada.from_env() as bancada:`) — garante `shutdown()`
  (desconecta a fonte, fecha o osciloscópio) mesmo se a bateria falhar no
  meio.
- **`ExperimentoBase`** (`abc.ABC`): base de toda classe de distúrbio.
  Recebe a `Bancada` no construtor e implementa `executar()` — o laço
  genérico de capturas, AWGN e gravação (dado puro + dado com ruído).
- **`ExperimentoNativo`** / **`ExperimentoWaveform`**: subclasses para os
  dois mecanismos físicos possíveis (ver seção 4). Cada
  `experimentos_nativos/NN.py` / `experimentos_waveform/NN.py` define uma
  classe `Experimento` (convenção fixa) herdando de uma delas e implementando
  só `gerar()` (+ `configurar()` para nativos).

---

## 4. Os 20 experimentos

Cada classe é definida por dois efeitos possíveis: um **transiente nativo**
da AMETEK (mudança de nível real, capturada como a fonte de verdade reage) ou
uma **forma de onda arbitrária** via `TRACe` (array calculado em Python,
reproduzido ciclo a ciclo pela fonte). No modo **simulado**, todas as classes
vêm sempre de `gerar()` — a distinção nativo/waveform só importa para a
captura física de comissionamento.

| # | Classe | Pasta | Mecanismo na bancada real |
|---|--------|-------|----------------------------|
| 01 | NORMAL | nativos | sem distúrbio (STEP para o mesmo valor, só para gerar o trigger) |
| 02 | SAG | nativos | `VOLTage:MODE PULSe` |
| 03 | SWELL | nativos | `VOLTage:MODE PULSe` |
| 04 | INTERRUPTION | nativos | `VOLTage:MODE PULSe` |
| 05 | HARMONICS | nativos (misto) | `FUNCtion:SHAPe CSINe` (4 níveis) + TRACe (nível de 30%) |
| 06 | FLICKER | waveform | TRACe (modulação contínua 8–25 Hz) |
| 07 | NOTCH | waveform | TRACe (pulsos de 0,1 ms) |
| 08 | TRANSIENT | waveform | TRACe (pico único de 0,05 ms) |
| 09 | OSCILLATORY_TRANSIENT | waveform | TRACe (oscilação amortecida 300–2400 Hz) |
| 10 | SAG_HARMONICS | waveform | TRACe |
| 11 | SAG_FLICKER | waveform | TRACe |
| 12 | SAG_OSCILLATORY_TRANSIENT | waveform | TRACe |
| 13 | SWELL_HARMONICS | waveform | TRACe |
| 14 | SWELL_OSCILLATORY_TRANSIENT | waveform | TRACe |
| 15 | HARMONICS_FLICKER | waveform | TRACe |
| 16 | INTERRUPTION_HARMONICS | waveform | TRACe |
| 17 | NOTCH_OSCILLATORY_TRANSIENT | waveform | TRACe |
| 18 | FREQUENCY_DRIFT | nativos | `FREQuency:MODE LIST` |
| 19 | DC_OFFSET | nativos | `SOURce:MODE ACDC` + `VOLTage:OFFSet` |
| 20 | INTERHARMONICS | waveform | TRACe |

A descrição física completa de cada classe (amplitudes, durações, faixas de
frequência) está em [`experimentos.txt`](experimentos.txt).

---

## 5. Operação na bancada física — o que o operador precisa saber

Esta é a parte que importa de verdade se você vai apertar o botão. Leia tudo
antes de conectar qualquer cabo.

### 5.1 Ligação física obrigatória

- **AMETEK MX30**: conectada por **USB**, exposta pelo driver como porta
  serial virtual `COM10` (PyVISA `ASRL10::INSTR`), **115200 baud**. Isso é
  fixo — `bench_config.ps1` e `validate_bench_configuration()` em
  `mestre.py` recusam qualquer outra porta/baudrate quando `BENCH_MODE=1`.
- **Não conecte o conector DB9 RS-232 da AMETEK ao mesmo tempo que a USB.**
  Os dois caminhos de comunicação conflitam.
- **Keysight DSO-X 4034A**: `USB0::0x0957::0x17A4::MY59240844::0::INSTR`
  (endereço VISA fixo desta unidade específica).
- **Cabo BNC**: saída **AMETEK Trigger Out → Keysight EXT Trigger**. Sem
  esse cabo, o osciloscópio nunca dispara e todo o comissionamento físico
  falha na etapa de trigger.
- Instale o **Keysight IO Libraries Suite** ou **NI-VISA x64** antes de
  qualquer coisa — é isso que expõe os recursos VISA ao Python.

### 5.2 Pré-requisitos de software

```powershell
.\scripts\setup_windows.ps1
```

Cria/atualiza o virtualenv em `env/` (Python 3.9–3.12, 3.11 recomendado) e
instala [`requirements.txt`](requirements.txt) (`numpy`, `PyMeasure`,
`PyVISA`). `start_bench_windows.ps1` já chama isso sozinho — normalmente você
não precisa rodar à parte.

### 5.3 O único comando do operador

```powershell
cd C:\Users\denis\TCC\code
scripts\START_BENCH.cmd
```

Isso roda `start_bench_windows.ps1 -Stage Full`, que executa **4 etapas em
sequência**, cada uma abortando a bateria inteira se falhar:

| Etapa | O que faz | Saída física durante o teste |
|---|---|---|
| 1. Comunicação | Identifica AMETEK e Keysight (`*IDN?`), confirma protocolo/porta | **OFF** |
| 2. Trigger | Força aquisição do Keysight para validar download/decodificação da waveform (BNC ainda **não** testado aqui — a MX30 não arma transiente com saída OFF) | **OFF** |
| 3. Baixa tensão | Pede confirmação `ENERGIZAR`, energiza o baseline e valida BNC + trigger real + RMS medido em 5 Vrms (tolerância 0,25 V ou 10%) | **ON, 5 Vrms** |
| 4. Bateria completa | Uma captura de cada uma das 20 classes | **ON** |

Também é possível rodar uma etapa isolada:

```powershell
.\scripts\start_bench_windows.ps1 -Stage Communication
.\scripts\start_bench_windows.ps1 -Stage Trigger
.\scripts\start_bench_windows.ps1 -Stage LowVoltage
.\scripts\start_bench_windows.ps1 -Stage Run
```

### 5.4 Confirmações interativas — não são automatizáveis

O script **para e pergunta** nestes pontos; nenhum deles deve ser
contornado ou escriptado:

1. **Fator da probe de tensão** (`VOLTAGE_PROBE_ATTENUATION`), se não estiver
   definido em `scripts\bench_config.ps1`: o operador digita o fator **exato**
   gravado na probe diferencial instalada (ex.: `10`, `100`). Nunca
   invente esse valor — ele é usado para escalar a tensão medida pelo
   osciloscópio de volta ao valor real no EUT.
2. **Tensão RMS e frequência do teste** (etapas `Full`/`LowVoltage`/`Run`):
   digitadas em V e Hz (ex.: `127`, `60`). O script recalcula
   automaticamente, a partir da tensão escolhida, o range da fonte (fixo em
   300 Vrms se `vrms ≤ 270`) e o pico máximo permitido (98% do teto físico do
   range, ~415 Vp) — não edite esses dois manualmente.
3. **`ENERGIZAR`** (etapa `Full`) ou **`ENERGIZAR-5V`** (etapa
   `LowVoltage` isolada): antes de digitar, confirme fisicamente **probe,
   cabos, botão de emergência (E-stop) e o EUT** conectado. Só depois disso
   a saída é autorizada (`ARM_OUTPUT=YES`).
4. **`EXECUTAR-20-CLASSES`** (etapa `Run` isolada): confirma que todos os
   preflights já passaram antes de rodar a bateria completa.

Essas strings são comparadas **case-sensitive** (`-cne`) — digite
exatamente como pedido.

### 5.5 Se algo falhar

O procedimento é sempre o mesmo, e não deve ser pulado:

1. **Confirme fisicamente `OUTPUT OFF` no painel da AMETEK.** O script tenta
   desligar a saída no `shutdown()` (`Bancada.__exit__`/`finally`), mas a
   confirmação visual no painel é obrigatória.
2. **Não execute novamente de forma automática.** Investigue a causa antes
   de tentar de novo.
3. **Recupere o log mais recente** em `logs\startup-bench-*.log` — cada
   execução gera um arquivo timestampado com toda a saída do Python.
4. **Não remova validações** de IDN, timeout, tamanho de waveform (6000
   pontos) ou SCPI só para "fazer passar" — elas existem porque já
   pegaram problemas reais (ver `CHANGELOG/v1.0.md`, seção 6.2, para o
   exemplo do bug de ciclo/frequência que corrompia a forma de onda).

### 5.6 Limites de segurança — o que está travado e por quê

`validate_bench_configuration()` em [`logica/mestre.py`](logica/mestre.py) roda antes de
abrir qualquer instrumento em `BENCH_MODE=1` e recusa a execução se:

- a porta não for `COM10` ou o baudrate não for `115200`;
- `VOLTAGE_PROBE_ATTENUATION` não estiver definido ou for ≤ 0;
- `CAPTURE_CURRENT=1` e faltar `CURRENT_PROBE_ATTENUATION` ou
  `CURRENT_BASE_A`;
- `BASE_VOLTAGE_RMS` exceder `EUT_MAX_VOLTAGE_RMS`, ou este exceder o range
  da fonte (`SOURCE_VOLTAGE_RANGE_RMS`);
- a saída for solicitada (`require_output`) sem `ARM_OUTPUT=YES`.

Além disso, **dentro do ORM** (`AmetekMX30`), todo comando que muda tensão,
frequência, THD ou offset DC é validado de novo contra `max_voltage_rms` /
`max_peak_v` no momento da chamada — é uma segunda barreira, independente da
validação de configuração acima.

**Captura de corrente vem desligada por padrão** (`CAPTURE_CURRENT=0`).
**Não ative sem o fator da probe de corrente e a corrente-base fornecidos
pelo usuário** — sem esses dois valores a leitura de corrente não tem
escala física correta.

### 5.7 Variáveis de ambiente da bancada

A fonte única de configuração física é
[`scripts/bench_config.ps1`](scripts/bench_config.ps1) (há também
[`.env.example`](.env.example) como referência para quem for rodar fora do
fluxo PowerShell). Campos que o operador tipicamente revisa:

| Variável | Significado | Observação |
|---|---|---|
| `BENCH_MODE` | `1` = bancada real, ausente/`0` = simulado | |
| `ARM_OUTPUT` | `YES` autoriza energizar a saída | Setado automaticamente pelo script após a confirmação `ENERGIZAR` |
| `AMETEK_PORT` / `AMETEK_BAUDRATE` | `COM10` / `115200` | Fixos para esta bancada; alterar quebra `validate_bench_configuration` |
| `AMETEK_CLEAR_USER_WAVEFORMS` | `1` apaga formas `TRACe` do usuário na conexão, mantém SIN/SQU/CSIN internas | |
| `KEYSIGHT_RESOURCE` | Endereço VISA do osciloscópio | Específico desta unidade (`MY59240844`) |
| `VOLTAGE_PROBE_ATTENUATION` | Fator da probe diferencial de tensão | **Obrigatório em `BENCH_MODE=1`**; sem valor, o script pergunta interativamente |
| `BASE_VOLTAGE_RMS` / `GRID_FREQUENCY_HZ` | Tensão/frequência base do teste | Perguntadas interativamente nas etapas `Full`/`LowVoltage`/`Run` |
| `SOURCE_VOLTAGE_RANGE_RMS` / `EUT_MAX_VOLTAGE_RMS` / `EUT_MAX_PEAK_V` | Limites físicos derivados da tensão escolhida | Calculados pelo script — não sobrescrever manualmente |
| `CURRENT_LIMIT_A` / `CURRENT_PROTECTION_DELAY_S` | Proteção de corrente da fonte | |
| `CAPTURE_CURRENT` | Liga captura de corrente | Ver 5.6 — requer `CURRENT_PROBE_ATTENUATION` e `CURRENT_BASE_A` |
| `REAL_CAPTURES_PER_CLASS` | Capturas físicas por classe | `1` em comissionamento |
| `SNR_LEVELS_DB` | Níveis de SNR para o AWGN aplicado, separados por vírgula | Ex.: `20,30,40,50` |

### 5.8 Onde os dados caem

Cada execução (simulada ou real) grava em [`resultados/`](resultados/):

- **Dados puros** (sem ruído): `resultados/{id}_{classe}.npz`
- **Dados com AWGN**, um arquivo por nível de SNR:
  `resultados/snr_XXdb/{id}_{classe}.npz`
- **Metadados** (parâmetros físicos da captura, SNR medido por nível):
  `resultados/metadata/{id}_{classe}.jsonl`

Gravação é atômica (`.npz.part` → `os.replace`), então uma execução
interrompida no meio não deixa arquivo de dados corrompido — só incompleto
(faltando classes posteriores).

Logs de cada execução do fluxo guiado ficam em `logs\startup-bench-*.log`,
nomeados com a etapa e o timestamp.

`resultados/`, `logs/`, `env/` e `__pycache__/` estão no `.gitignore` — não
são versionados.

---

## 6. Rodando sem hardware

### Gerar o dataset simulado completo

```powershell
.\scripts\run_simulation_windows.ps1
# ou, para customizar:
.\scripts\run_simulation_windows.ps1 -CapturesPerClass 2000 -SnrLevels "20,30,40,50"
```

Força `BENCH_MODE=0`/`ARM_OUTPUT=NO` — nenhum instrumento é aberto.

### Testes offline

```powershell
.\env\Scripts\python.exe -m unittest tests.test_offline -v
```

Roda os dois ORMs em modo simulado (`simulated=True`, sem porta serial) contra
todas as 20 classes, incluindo a regressão do bug de ciclo/frequência
descrito em `CHANGELOG/v1.0.md` (seção 6.2).

---

## 7. Empacotamento

```powershell
.\scripts\package_windows.ps1
```

Gera `..\tcc-instrumentacao-bancada.zip` com o repositório, excluindo
`env/`, `.venv/`, `__pycache__/`, `resultados/`, `logs/`, `backups/` e `.git/`
— útil para transportar o código para o computador da bancada sem carregar
resultado de execuções anteriores.

---

## 8. Referências

- [`AGENTS.md`](AGENTS.md) — instruções restritivas para automação/IA rodando
  no computador da bancada (não refatorar, não trocar portas/limites).
- [`CHANGELOG/v1.0.md`](CHANGELOG/v1.0.md) — arquitetura original, os 20
  experimentos em detalhe, e o bugfix de ciclo/frequência.
- [`CHANGELOG/v1.1.md`](CHANGELOG/v1.1.md) — remoção de SCPI cru dos
  experimentos, `mestre.py` orientado a objetos.
- [`CHANGELOG/v1.2.md`](CHANGELOG/v1.2.md) — gravação de dados puros além
  dos dados com ruído.
- [`CHANGELOG/v1.3.md`](CHANGELOG/v1.3.md) — reorganização em `logica/` e
  `scripts/`.
- `docs/AMETEK_MX_SCPI_Programming_Manual.pdf` e
  `docs/Keysight_4000X_Programmers_Guide.pdf` — manuais SCPI originais dos
  dois instrumentos.
