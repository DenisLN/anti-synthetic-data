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
[`CHANGELOG/`](CHANGELOG/) (`v1.0.md` a `v1.6.md`) — este README é um resumo
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
    preflight_new.py            Validação estendida: comandos nativos dos dois ORMs (STEP/PULSe/CSINe/
                                 LIST:FREQuency/ACDC/MEASure* da AMETEK, canal 2 do Keysight), log por etapa
    cli.py                     REPL interativo do operador (status/list/comm/trigger/lowvoltage/native/run) —
                                 ver seção 5.3
    visualizador.py             CLI: gera um PNG de inspeção de um .npz de resultados/ e abre no visualizador do SO
    analisar_sessao.py          Análise offline de uma pasta de sessão (gerar() + seed do metadata x captura)
    recortar_margem.py          Recorta a folga de 20/50 ms das capturas físicas (janela nominal, sem tocar no original)
    relatorio_html.py           HTML autocontido (figuras em base64) de uma sessão, para compartilhar
    modelos/relatorio_capturas.html  Modelo HTML preenchido por relatorio_html.py
    calibracao_extremos.json    Fatores (extremo medido / pico programado) por classe da pré-validação de pico

scripts/                    Todo o PowerShell/CMD que o operador roda no Windows
    bench_config.ps1           ÚNICA fonte de variáveis de ambiente da bancada física
    start_bench_windows.ps1    Prepara o venv, pergunta probe/Vrms/Hz uma vez e abre a CLI (logica/cli.py)
    START_BENCH.cmd            Ponto de entrada único do operador (chama start_bench_windows.ps1)
    run_simulation_windows.ps1 Gera o dataset simulado (sem hardware)
    setup_windows.ps1          Cria/atualiza o venv (env/) e instala requirements.txt
    package_windows.ps1        Empacota o repositório em .zip para transporte
    visualizar_npz.ps1         Wrapper de logica/visualizador.py
    relatorio_limites_bancada.py  Offline: o que cabe a uma tensão base (pico/extremo previsto, limite de bancada)
    recalibrar_extremos.py     Offline: recalcula calibracao_extremos.json (por condição) a partir do VMAX/VMIN do metadata
    diag_nativo_output_off.py  Diagnóstico da AMETEK com OUTPUT OFF (ver CHANGELOG/v1.12.md)
    diag_saida_vs_medida.py    Energiza (confirmação digitada) e lê a medida da própria fonte nas 3 fases (v1.14)
    diag_fonte_vs_osciloscopio.py  Fonte e CH1 lado a lado, direto e em degrau (v1.14)
    diag_osciloscopio_canais.py    Estado dos 4 canais do Keysight, só leitura (v1.14)

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
`PyVISA`, `matplotlib`). `start_bench_windows.ps1` já chama isso sozinho —
normalmente você não precisa rodar à parte.

### 5.3 O único comando do operador

```powershell
cd C:\Users\denis\TCC\code
scripts\START_BENCH.cmd
```

Isso roda `start_bench_windows.ps1`, que prepara o venv, pergunta o fator
**exato** da probe de tensão e a tensão/frequência do teste (uma vez — esses
valores viram constantes de módulo assim que o processo Python inicia, então
mudá-los exige reiniciar o `START_BENCH.cmd`, não só um comando) e entrega o
resto da sessão para a **CLI interativa** (`logica/cli.py`).

A tensão pedida é **fase-neutro**, no máximo **270 V** (127 e 220 V são os
casos de uso). **380 V não é aceito** (v1.13): a MX30-3Pi gera até 300 Vrms
por fase (425 Vp) e a bancada mede uma fase L-N; num sistema 220/380 V, 380 V
é a tensão de linha e cada fase tem 219,4 V — digite 220. Ver 5.6 e
`CHANGELOG/v1.13.md` (opção A, fase-fase, documentada e não implementada).

A partir daí, o operador digita comandos explícitos em vez de seguir um fluxo
fixo. `help` (ou `?`) dentro da CLI imprime a referência completa a qualquer
momento; resumo:

| Comando | Energiza a saída? | Equivale a |
|---|---|---|
| `status` | não | — mostra o que está configurado (inclusive seed e capturas efetivas por classe, com a estimativa de gravações de TRACe) e o resultado da última execução de cada classe nesta sessão |
| `list` | não | lista as 20 classes com id/nome, capturas efetivas (e o padrão da classe) e status (OK/FALHOU/nunca rodou) |
| `comm` | não | antiga etapa "Comunicação" — identifica AMETEK e Keysight (`*IDN?`) |
| `trigger` | não | antiga etapa "Trigger" — força aquisição do Keysight (BNC ainda não testado aqui) |
| `lowvoltage` | **sim, 5 Vrms** | antiga etapa "Baixa tensão" — recomissionamento (BNC + trigger real + RMS). **Opcional**: só rode quando precisar recomissionar a bancada depois de mexer em fiação/probe, não a cada sessão — reprograma ~12 TRACe na Flash (~40-50s) |
| `native` | **sim** | antiga etapa "Comandos nativos" — `preflight_new.py --native-commands` |
| `run <NN\|nome>` | **sim** | roda UMA classe isolada (ex.: `run 02` ou `run SAG`) |
| `run all` | **sim** | bateria completa das 20 classes, sequencial, resiliente por classe (ver 5.5) |
| `set diagnostico on\|off` | não | liga/desliga log extra de `STATus:OPERation:CONDition?`/`OUTPut:STATe?`/tensão imediata em pontos-chave de `run`/`run all`, para testar as hipóteses de timing do `CHANGELOG/v1.7.md` (`OFF` por padrão); com `on`, também abre um terminal extra acompanhando a transcrição SCPI da sessão em tempo real |
| `set capturas <N>` | não | mínimo de capturas por classe na bancada real: cada classe roda **max(N, padrão da classe)** (ver 5.3.1); em classes com níveis discretos (SAG/SWELL/HARMONICS), por nível; com ele, 04/06/09/19 cobrem o intervalo do parâmetro e a 08 entra em caracterização (rampa de amplitude). A CLI avisa onde o padrão vence |
| `set capturas padrao` | não | desfaz o `set capturas`: só o padrão de cada classe, com sorteio |
| `set seed <N>` | não | seed base dos próximos `run` (inteiro ≥ 0; `set seed padrao` volta à do início). Mesma seed → mesmas formas, parâmetros e plano de capturas. Gravada no metadata (`base_seed`) |
| `quit` / `exit` | não | sai da CLI |

Ordem recomendada para uma sessão do zero: `comm` → `trigger` → `native` →
(`lowvoltage`, só se for recomissionar) → `run all`.

Sem hardware (`BENCH_MODE=0`), `status`/`list`/`run` continuam funcionando em
modo simulado; `comm`/`trigger`/`lowvoltage`/`native` exigem bancada física de
verdade (mesma restrição que `preflight.py`/`preflight_new.py` sempre
tiveram) e falham com uma mensagem clara.

**Margem de captura (desde 2026-09-22, v1.11):** toda captura FÍSICA grava com
folga fixa de `MARGEM_ANTES_S`/`MARGEM_DEPOIS_S` (20 ms antes / 50 ms depois da
janela nominal por padrão) — deixou de ser opt-in. O comando `set margin
on|off` (v1.8–v1.10) foi **descontinuado**: não existe mais um modo "sem
margem" para captura real, e digitá-lo na CLI só imprime um aviso. Ajustável
só por variável de ambiente antes de iniciar a sessão, nunca em runtime. Ver
`CHANGELOG/v1.11.md`.

### 5.3.1 Capturas por classe e seed (v1.13)

Cada classe tem um número **padrão** de capturas na bancada
(`capturas_padrao` no `NN.py`; o dataset simulado não muda). O número que
roda é `max(set capturas N` — ou `REAL_CAPTURES_PER_CLASS` sem ele —
`, padrão da classe)`, por nível nas classes com `NIVEIS`; a pré-validação
de pico/rms ainda pode pular capturas (sempre logado e contado no resumo).

| Classe | Padrão | Por quê |
|---|---|---|
| 01 NORMAL, 02 SAG, 03 SWELL, 05 HARMONICS, 10–16 (composições), 18 FREQUENCY_DRIFT | 1 | determinísticas (nível fixo, `NIVEIS` ou alternância por índice) |
| 04 INTERRUPTION, 06 FLICKER, 07 NOTCH, 08 TRANSIENT, 09 OSCILLATORY_TRANSIENT, 17 NOTCH_OSC, 19 DC_OFFSET, 20 INTERHARMONICS | 3 | `gerar()` sorteia parâmetros (pedido do dono, 2026-10-07) |

Sem `set capturas`, as capturas padrão **sorteiam** (a 08 aplica o impulso
máximo seguro em todas). Com `set capturas` (qualquer N), 04/06/09/19 cobrem
o intervalo do parâmetro e a 08 faz a **rampa de caracterização** sobre o
total efetivo. Com os padrões, um `run all` faz até ~300 gravações de TRACe
numa conexão (a fonte travou na ~280.ª em 2026-09-16): a CLI mostra a
estimativa antes de confirmar.

Seed de cada captura = `seed base + id × 1 000 000 + índice`; a seed base vem
de `BASE_SEED` (env, padrão 20 260 827) ou de `set seed N`.

### 5.4 Confirmações interativas — não são automatizáveis

Nada muda aqui em relação ao fluxo antigo — só o lugar onde a pergunta
acontece (a CLI, não mais um script PowerShell por etapa). Nenhuma delas deve
ser contornada ou escriptada:

1. **Fator da probe de tensão** (`VOLTAGE_PROBE_ATTENUATION`), se não estiver
   definido em `scripts\bench_config.ps1`: perguntado pelo próprio
   `start_bench_windows.ps1`, antes de abrir a CLI. O operador digita o fator
   **exato** gravado na probe diferencial instalada (ex.: `10`, `100`). Nunca
   invente esse valor — ele é usado para escalar a tensão medida pelo
   osciloscópio de volta ao valor real no EUT.
2. **Tensão RMS e frequência do teste**: também perguntadas pelo
   `start_bench_windows.ps1`, uma vez por sessão, em V e Hz (ex.: `127`,
   `60`). O script recalcula automaticamente, a partir da tensão escolhida, o
   range da fonte (fixo em 300 Vrms se `vrms ≤ 270`) e o pico máximo permitido
   (98% do teto físico do range, ~415 Vp) — não edite esses dois manualmente.
3. **`ENERGIZAR-5V`** (comando `lowvoltage`), **`ENERGIZAR-COMANDOS`**
   (comando `native`), **`EXECUTAR-CLASSE-<NN>`** (comando `run <NN>`, ex.
   `EXECUTAR-CLASSE-02`) ou **`EXECUTAR-20-CLASSES`** (comando `run all`):
   cada comando que energiza a saída pede a SUA própria confirmação, dentro
   da CLI. Antes de digitar, confirme fisicamente **probe, cabos, botão de
   emergência (E-stop) e o EUT** conectado. Só depois disso a saída é
   autorizada (`ARM_OUTPUT=YES`, e só durante aquele comando — a CLI revoga a
   autorização assim que o comando termina).

Essas strings são comparadas **case-sensitive** — digite exatamente como
pedido.

### 5.5 Se algo falhar

Duas categorias bem diferentes, e só uma delas exige parar tudo:

- **Falha de UMA classe dentro de `run all`** (RMS fora de tolerância,
  timeout de trigger, uma exceção dentro de `gerar()`...): `Bancada.
  executar_bateria()` já isola isso sozinha — loga o traceback completo,
  registra a classe como `FALHOU` no resumo final, devolve a fonte a um
  estado seguro conhecido (`recuperar_estado_seguro()`: trigger ocioso,
  senoide padrão, tensão de volta à base, saída ainda ligada) e segue para a
  próxima classe. Isso não é motivo para interromper a sessão — veja o
  resumo no fim de `run all` (quantas OK, quais falharam e por quê) e decida
  se vale rodar `run <NN>` de novo isoladamente para aquela classe depois.
- **Falha de INFRAESTRUTURA real** (porta serial caiu, `*IDN?` parou de
  responder, impossível confirmar `OUTPUT` no estado esperado): aparece como
  `CommunicationError` ou `FalhaFatalDeInstrumento` e SEMPRE aborta o comando
  inteiro (`run all` incluído) — não é seguro continuar tentando com o
  instrumento em estado desconhecido. O procedimento abaixo é sempre o
  mesmo, e não deve ser pulado:

1. **Confirme fisicamente `OUTPUT OFF` no painel da AMETEK.** O script tenta
   desligar a saída no `shutdown()` (`Bancada.__exit__`/`finally`), mas a
   confirmação visual no painel é obrigatória.
2. **Não execute novamente de forma automática.** Investigue a causa antes
   de tentar de novo.
3. **Recupere o log mais recente** em `logs\startup-bench-*.log` — cada
   execução gera um arquivo timestampado com toda a saída do Python. A etapa
   `NativeCommands` também grava seu próprio log por etapa em
   `logs\preflight_new-<etapa>-<timestamp>.log`, com uma linha `OK:`/`FALHOU:`
   para cada comando exercitado (STEP, PULSe, CSINe, LIST:FREQuency, ACDC,
   `MEASure:*`, canal 2).
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

**Pré-validação de pico e tensões de teste (v1.12/v1.13).** Antes de
qualquer comando SCPI, cada captura é avaliada (`avaliar_captura_na_bancada`):
rms programado ≤ 300 Vrms e extremo PREVISTO (pico programado × fator medido
em `logica/calibracao_extremos.json` × 1,10) ≤ `max_peak_v` (415,8 V; 0,9 ×
isso na 08). Depois de cada captura, VMAX/VMIN do Keysight são conferidos
contra o mesmo teto.

- **127 V**: tudo cabe.
- **220 V**: nas classes **waveform** cujo extremo previsto não cabe, a
  captura física reduz só o distúrbio (`senoide + k × (gerar() − senoide)`,
  maior k que cabe; "limite de bancada", opção b do dono) e grava
  `fator_disturbio_bancada` e os parâmetros aplicados `*_bancada` no
  metadata — com a calibração da v1.13: 10 (88%), 11 (78%), 14 (48%), 16
  (37%), 17 (98%). Abaixo de `LIMITE_BANCADA_FRACAO_MINIMA` (0,25) a captura é
  pulada; `LIMITE_BANCADA_DISTURBIO=0` volta a pular sempre. Nativas não
  reduzem: a 03 roda só 1,1 pu (1,2 pu: extremo previsto acima do teto; ≥ 1,4 pu:
  > 300 Vrms). Relatório completo, offline:
  `python scripts\relatorio_limites_bancada.py --tensao 127 --tensao 220`.
- **380 V**: recusado (ver 5.3).

**Calibração por condição (v1.14).** Os fatores ficam por condição de bancada
(tensão base ±2%, frequência ±0,5 Hz) em `por_condicao`; hoje há
**127 V/60 Hz** e **230 V/50 Hz**. Numa condição calibrada, cada classe usa o
maior entre o fator dela ali e nas outras condições. **Numa condição sem
tabela** (ex.: 220 V/60 Hz, nunca medida), toda classe usa o maior fator já
medido — o log avisa e muito mais capturas são reduzidas/puladas até a
condição ser calibrada. Motivo: a 230 V/50 Hz, com a tabela de 127 V, a 17
previu 405 V e mediu **444 V** (acima dos 425 Vp do hardware). Para calibrar
uma condição: rode a bateria nela e depois
`python scripts\recalibrar_extremos.py resultados\sessao_A ... [--gravar]`
(separa por condição; capturas com distúrbio reduzido entram invertendo a
fórmula do limite de bancada; com `--gravar`, nenhum fator diminui sem
`--substituir`).

**Checagem da cadeia de medição (v1.14).** Antes da primeira classe de todo
`run`, a bancada põe a senoide base, espera a MEDIDA da fonte confirmar a base
(±5%) e compara com o Vrms do CH1 numa aquisição forçada (±10%). Fora disso
aborta com a leitura dos dois — pega disjuntor aberto, probe no lugar errado
ou fator de probe errado antes de gastar a bateria.

**Ctrl+C (v1.14).** Com as sessões VISA abertas, o NI-VISA descartava o
Ctrl+C. Agora ele interrompe o comando assim que a chamada VISA em curso
termina (até ~15 s), a saída é desligada ao fechar a conexão e a CLI volta ao
prompt. Em emergência continua valendo OUTPUT OFF / E-stop na fonte.

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
| `BASE_VOLTAGE_RMS` / `GRID_FREQUENCY_HZ` | Tensão/frequência base do teste | Perguntadas interativamente nas etapas `Full`/`LowVoltage`/`NativeCommands`/`Run` |
| `SOURCE_VOLTAGE_RANGE_RMS` / `EUT_MAX_VOLTAGE_RMS` / `EUT_MAX_PEAK_V` | Limites físicos derivados da tensão escolhida | Calculados pelo script — não sobrescrever manualmente |
| `CURRENT_LIMIT_A` / `CURRENT_PROTECTION_DELAY_S` | Proteção de corrente da fonte | |
| `CAPTURE_CURRENT` | Liga captura de corrente | Ver 5.6 — requer `CURRENT_PROBE_ATTENUATION` e `CURRENT_BASE_A` |
| `REAL_CAPTURES_PER_CLASS` | Piso global de capturas físicas por classe | `1`; cada classe roda max(isto, padrão da classe) — ver 5.3.1 |
| `BASE_SEED` | Seed base das capturas (inteiro ≥ 0) | Vazio = 20260827; também `set seed N` na CLI |
| `LIMITE_BANCADA_DISTURBIO` / `LIMITE_BANCADA_FRACAO_MINIMA` | Limite de bancada (220 V): reduzir o distúrbio das waveform para caber / menor fração aceita | `1` / `0.25`; `0` = só pular (comportamento da v1.12) |
| `SNR_LEVELS_DB` | Níveis de SNR para o AWGN aplicado, separados por vírgula | Ex.: `20,30,40,50` |

### 5.8 Onde os dados caem

**Cada sessão da CLI interativa grava numa pasta própria.** No primeiro
`run`/`run all` da sessão (não no boot da CLI — `status`/`comm`/`trigger`/
`native` sozinhos não criam pasta), `logica/cli.py` cria
`resultados/sessao_<timestamp>/` e passa a gravar tudo ali; qualquer `run`
seguinte na MESMA sessão de CLI usa a mesma pasta, então reabrir a CLI
depois (ou rodar `logica/mestre.py`/os testes fora da CLI) nunca sobrescreve
os dados de uma sessão anterior. Fora da CLI interativa (scripts standalone,
`tests/test_offline.py`, geração do dataset simulado), a gravação continua
indo direto para `resultados/`, sem subpasta de sessão.

Dentro da pasta (`resultados/` ou `resultados/sessao_<timestamp>/`), o
formato do `.npz` depende do modo — a bancada real precisa identificar cada
condição física capturada; a geração do dataset simulado nunca precisou
disso e mantém o formato de sempre:

- **Bancada real** (execução via CLI, `run`/`run all`): cada CAPTURA
  individual grava seu próprio arquivo. O nome carrega o parâmetro físico
  quando existe algum (ex.: `02_sag_sag_pu-0.1.npz`); classes sem parâmetro
  nomeável usam a posição (`01_normal_cap01.npz`). Quando `set capturas N`
  agrupa N capturas físicas no mesmo nível/parâmetro, a 1ª ocorrência fica
  sem sufixo e as seguintes ganham `_02`, `_03`, ... (`sag_pu-0.1.npz`,
  `sag_pu-0.1_02.npz`, ...) — sem isso, capturas com o mesmo rótulo se
  sobrescreveriam.
  - **Dados puros** (sem ruído): `{id}_{classe}_{parametro-valor|capNN}[_NN].npz`
  - **Dados com AWGN**, um arquivo por nível de SNR, mesmo nome de arquivo:
    `snr_XXdb/{id}_{classe}_{parametro-valor|capNN}[_NN].npz`
- **Dataset simulado** (`run_simulation_windows.ps1`, `SIM_CAPTURES_PER_CLASS`
  capturas por classe): formato histórico do projeto, inalterado — UM `.npz`
  por classe com todas as capturas empilhadas (`tensao_pu.shape = (total,
  pontos)`): `{id}_{classe}.npz` / `snr_XXdb/{id}_{classe}.npz` (ver 6, mais
  abaixo).
- **Metadados** (parâmetros físicos da captura, SNR medido por nível, e o
  `nivel_indice` usado para reconstruir a captura depois): continua **um
  arquivo por classe**, uma linha por captura, nos dois modos —
  `metadata/{id}_{classe}.jsonl`.

Rodar a mesma classe de novo na bancada real com um conjunto de capturas
diferente (ex.: `set capturas 5` entre duas chamadas de `run 02`) pode deixar
arquivos órfãos da rodada anterior sem captura correspondente no metadata
novo; `_salvar_classe()` limpa esses órfãos automaticamente, sempre depois
que os arquivos novos e o `metadata.jsonl` já foram gravados com sucesso.
Isso só se aplica ao caminho real — o nome fixo por classe do dataset
simulado nunca gera órfão.

Gravação é atômica (`.npz.part`/`.jsonl.part` → `os.replace`), então uma
execução interrompida no meio não deixa arquivo de dados corrompido — só
incompleto (faltando classes ou capturas posteriores).

Para inspecionar uma sessão inteira depois — deslocamento por
cross-correlação, razão de pico e comparação visual gerado-vs-capturado por
arquivo — use `logica/analisar_sessao.py <pasta_da_sessao>` (offline, sem
hardware; ver 8, `CHANGELOG/v1.8.md`).

**Captura física = janela nominal + folga.** Cada `.npz` da bancada real tem
8100 pontos: 20 ms antes + os 200 ms nominais + 50 ms depois (ver 5.3). Para
ter só a janela nominal (a mesma base de tempo de `gerar()` e do dataset
simulado):

```powershell
.\env\Scripts\python.exe logica\recortar_margem.py resultados\sessao_2026-09-30_15-26-05
# --saida outra_pasta   (padrão: <sessao>\sem_margem\)
# --empilhar            (também 1 .npz por classe com as capturas empilhadas, formato do simulado)
```

O recorte é o mesmo da validação física e de `analisar_sessao.py`
(`sinais.janela_nominal()`, alinhado pelo `indice_trigger` real). A sessão
original nunca é alterada; a pasta nova tem a mesma estrutura (`*.npz`,
`snr_XXdb/`, `corrente/`, `metadata/`), cada linha do metadata ganha um bloco
`recorte` (de onde saiu a janela) e as outras ferramentas rodam nela sem
mudança. O terminal lista, por arquivo, a origem do recorte e o deslocamento do
trigger em relação à margem; metadata sem `indice_trigger` (anterior à v1.11)
cai em `margem_amostras_antes` e é sinalizado.

**Relatório HTML para compartilhar.** Um único `.html`, com as figuras
embutidas em base64 — abre offline em qualquer navegador, dá para mandar por
e-mail:

```powershell
.\env\Scripts\python.exe logica\relatorio_html.py resultados\sessao_2026-09-30_15-26-05 `
    --titulo "Bancada 30/09 — 127 V" --descricao "20 classes, 1 captura cada"
# --classes 02,05,10   --max-capturas-por-classe 2   --snr 30   --dpi 80
# --com-esperado       (sobrepõe a forma de gerar() + seed em tracejado)
# --detalhes-manuais detalhes.json   ({"02_sag_sag_pu-0.1": [[50, 85], [105, 140]]}, tempos em ms)
```

Por captura: **1 visualização completa** (a folga sombreada em cinza, o eixo
começa em 0 ms no início da janela nominal, linha do trigger, eixo secundário
em volts) e **até 3 detalhes** — zooms de 2 ciclos onde o sinal mais muda
(bordas de sag/swell/interrupção, notches, transitórios); sem nenhum evento,
1 detalhe do regime. Os detalhes aparecem marcados (D1–D3) na completa.
Também mostra parâmetros, seed e o resultado da validação física de cada
captura. Clicar numa figura amplia. Funciona na sessão original, na pasta
`sem_margem/` e no dataset simulado (aí só as 3 primeiras capturas de cada
classe, salvo `--max-capturas-por-classe`). Acima de 20 MB o script avisa.

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

### Visualizando os dados capturados

Cada `.npz` em `resultados/` gerado pelo dataset simulado (`N =
SIM_CAPTURES_PER_CLASS`, 2000 por padrão) guarda **várias capturas
empilhadas**, não um waveform só — `tensao_pu` tem shape `(N, 6000)`, uma
linha por captura, exatamente como sempre foi (ver 5.8: `_salvar_classe()`
tem um formato para o dataset simulado e outro para a bancada real desde a
v1.8 — o simulado nunca mudou). É por isso que os 20 arquivos gerados por
`run_simulation_windows.ps1` têm praticamente o mesmo tamanho (~91,6 MB): o
`.npz` não é comprimido, então o tamanho em disco só depende da forma do
array, igual para todas as classes — não do conteúdo.

Já um `.npz` capturado na **bancada real** (via CLI, `run`/`run all`) guarda
uma única captura por arquivo, nomeado pelo parâmetro físico ou posição (ver
5.8) — inspecione o arquivo específico da condição que interessa, sem
precisar de `--captura`.

Para inspecionar visualmente um arquivo:

```powershell
# dataset simulado (várias capturas empilhadas):
.\scripts\visualizar_npz.ps1 -Npz resultados\02_sag.npz
.\env\Scripts\python.exe logica\visualizador.py resultados\02_sag.npz --captura 12

# captura real (um arquivo por captura):
.\scripts\visualizar_npz.ps1 -Npz resultados\sessao_2026-09-15_14-30-00\02_sag_sag_pu-0.1.npz
```

Gera um PNG (amostra de capturas sobrepostas, uma captura individual,
envelope média±desvio-padrão, resumo textual) e abre no visualizador de
imagens padrão do sistema. Veja `--help` para todas as opções.

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

- [`AGENTS.md`](AGENTS.md) — instruções para automação/IA rodando no
  computador da bancada: fluxo do operador, o que pode ser refatorado e os
  limites de segurança que nunca podem mudar (portas, tolerâncias, validações,
  confirmações de energização).
- [`CHANGELOG/v1.0.md`](CHANGELOG/v1.0.md) — arquitetura original, os 20
  experimentos em detalhe, e o bugfix de ciclo/frequência.
- [`CHANGELOG/v1.1.md`](CHANGELOG/v1.1.md) — remoção de SCPI cru dos
  experimentos, `mestre.py` orientado a objetos.
- [`CHANGELOG/v1.2.md`](CHANGELOG/v1.2.md) — gravação de dados puros além
  dos dados com ruído.
- [`CHANGELOG/v1.3.md`](CHANGELOG/v1.3.md) — reorganização em `logica/` e
  `scripts/`.
- [`CHANGELOG/v1.4.md`](CHANGELOG/v1.4.md) — visualizador de capturas `.npz`
  (`logica/visualizador.py`).
- [`CHANGELOG/v1.5.md`](CHANGELOG/v1.5.md) — rearmamento do Keysight nas
  classes nativas e `preflight_new.py`.
- [`CHANGELOG/v1.6.md`](CHANGELOG/v1.6.md) — comissionamento na bancada:
  timing do SAG, CSINe e resiliência da serial.
- [`CHANGELOG/v1.7.md`](CHANGELOG/v1.7.md) — correção do timing do CSINe
  (segundo `aguardar_resposta()`), resiliência por classe na bateria de 20,
  CLI interativa (`logica/cli.py`) e cache de TRACe por conexão.
- [`CHANGELOG/v1.8.md`](CHANGELOG/v1.8.md) — `set margin`/`diagnostico`/
  `capturas`, sessão isolada por pasta (`resultados/sessao_<timestamp>/`),
  cobertura determinística de níveis/parâmetros e `logica/analisar_sessao.py`.
- [`CHANGELOG/v1.9.md`](CHANGELOG/v1.9.md) — hipótese `LIST:REPeat`
  dobrando cada ciclo, dois pontos de diagnóstico novos, folga de
  `margin on` para 500ms.
- [`CHANGELOG/v1.10.md`](CHANGELOG/v1.10.md) — `LIST:REPeat` confirmado
  parcialmente e corrigido, modo Digitizer investigado e descartado,
  margem cai para 400ms; três bugs encontrados e ainda não corrigidos
  naquela versão (resolvidos em v1.11, ver abaixo).
- [`CHANGELOG/v1.11.md`](CHANGELOG/v1.11.md) — análise offline completa das
  duas sessões de 2026-09-16 (`docs/analise-2026-09-21/`): caminho nativo
  íntegro (H-NATIVO), validação física pós-captura, posição do trigger
  corrigida (H-REF10), margem fixa de 20/50ms (`set margin` descontinuado),
  captura com erro descartável não aborta mais a bateria, terminal de
  `tail -f` da transcrição SCPI com `diagnostico on`.
- [`CHANGELOG/v1.12.md`](CHANGELOG/v1.12.md) — comissionamento de
  2026-09-30 (`docs/analise-2026-09-30/`): writes sincronizados (a causa real
  do H-NATIVO eram comandos em rajada perdidos), fase de disparo das nativas,
  frequência restaurada após a 18, classe 08 caracterizada com VMAX/VMIN do
  osciloscópio, bloqueio prévio de pico calibrado, `VOLTage:HIGH` como RMS;
  de 2/20 para 20/20 classes a 127 V.
- [`docs/TAREFAS_NUVEM_2026-10-07.md`](docs/TAREFAS_NUVEM_2026-10-07.md) —
  tarefas da sessão de 2026-10-07 (capturas padrão por classe, seed na CLI,
  220/380 V), implementadas na v1.13.
- [`CHANGELOG/v1.13.md`](CHANGELOG/v1.13.md) — capturas padrão por classe
  (3 nas que sorteiam), `set seed`, capturas = max(`set capturas`, padrão),
  220 V com limite de bancada (distúrbio reduzido só na captura física),
  380 V recusado com explicação, relatório de limites e script de
  recalibração dos fatores de extremo; checklist de bancada.
- [`CHANGELOG/v1.14.md`](CHANGELOG/v1.14.md) — validação de 2026-10-07
  (disjuntor aberto; 230 V/50 Hz mediu 444 V): fatores de extremo por
  condição (tensão/frequência) com regra conservadora sem calibração,
  checagem fonte × CH1 antes da primeira classe, Ctrl+C que de fato para a
  bateria, 08 a 50 Hz, log de tentativas correto; checklist de bancada.
  Mais `logica/recortar_margem.py` (tira a folga de 20/50 ms das capturas
  físicas) e `logica/relatorio_html.py` (relatório HTML autocontido para
  compartilhar).
- `docs/AMETEK_MX_SCPI_Programming_Manual.pdf` e
  `docs/Keysight_4000X_Programmers_Guide.pdf` — manuais SCPI originais dos
  dois instrumentos.
