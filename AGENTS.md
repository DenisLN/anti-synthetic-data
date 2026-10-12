# Instrução para agentes de IA no computador Windows da bancada

O projeto deve estar em `C:\Users\denis\TCC\code` (ajuste o caminho conforme a
máquina). A fonte e o osciloscópio já devem estar conectados assim:

- AMETEK MX30: porta USB da fonte, exposta pelo driver como PyVISA
  `ASRL10::INSTR` (`COM10`), 115200 baud confirmados no equipamento real.
- Keysight DSO-X 4034A: `USB0::0x0957::0x17A4::MY59240844::0::INSTR`.
- BNC: AMETEK Trigger Out -> Keysight EXT Trigger.
- O cabo USB da AMETEK deve permanecer conectado. Não usar simultaneamente o
  conector DB9 RS-232.

## Fluxo do operador (a partir da v1.7)

A operação deixou de ser um fluxo fixo de 5 etapas obrigatórias. O operador
roda:

```powershell
cd C:\Users\denis\TCC\code
scripts\START_BENCH.cmd
```

Isso prepara o venv, pergunta o fator EXATO da probe de tensão e a
tensão/frequência do teste (uma vez, no início do processo — ver por quê na
seção 5.3 do README) e entrega o resto para a CLI interativa
(`logica/cli.py`). Dentro da CLI, `help`/`?` imprime a referência completa;
resumo:

| Comando | Energiza? | Equivale a |
|---|---|---|
| `status`, `list` | não | — |
| `comm` | não | antiga etapa Communication |
| `trigger` | não | antiga etapa Trigger |
| `lowvoltage` | sim, 5V | antiga etapa LowVoltage — agora OPCIONAL, só para recomissionar (fiação/probe mexidas), não roda mais automaticamente dentro de nada |
| `native` | sim | antiga etapa NativeCommands (`preflight_new.py --native-commands`) |
| `run <NN\|nome>` | sim | roda uma classe isolada |
| `run all` | sim | bateria completa das 20 classes, resiliente por classe (ver abaixo) |

Todas as confirmações físicas (fator de probe, Vrms/Hz, e a string digitada
antes de energizar — `ENERGIZAR-5V`, `ENERGIZAR-COMANDOS`,
`EXECUTAR-CLASSE-<NN>`, `EXECUTAR-20-CLASSES`, todas case-sensitive) continuam
existindo exatamente como no fluxo antigo. Não invente o fator de probe e não
automatize essas confirmações.

Se algo falhar de um jeito que indique infraestrutura real comprometida (porta
serial caiu, impossível confirmar OUTPUT):

1. confirmar fisicamente OUTPUT OFF no painel da AMETEK;
2. não executar de novo automaticamente;
3. entregar ao usuário o arquivo mais recente de `logs\startup-bench-*.log`
   (ou `logs\preflight_new-*.log` para falhas de `native`);
4. não remover validações de IDN, timeout, tamanho de waveform ou SCPI.

Uma falha isolada de EXPERIMENTO (RMS fora de tolerância, timeout de trigger,
exceção em `gerar()`) durante `run all` **não** é motivo para parar e chamar o
usuário — `Bancada.executar_bateria()` já isola, registra e segue para a
classe seguinte sozinha (ver "Limites inegociáveis" abaixo). Só pare e avise
diante de uma falha de infraestrutura real.

Captura de corrente permanece desligada por padrão. Não ativá-la sem fator da
probe de corrente e corrente-base fornecidos pelo usuário.

## O que pode ser refatorado

Este arquivo historicamente dizia "não refatore, não rode testes separados".
Essa restrição está **suspensa** para os módulos abaixo, e continua suspensa
para qualquer sessão futura que precise mexer neles (autorização registrada
em 2026-09-09, ver `CHANGELOG/v1.7.md`):

- `logica/mestre.py`, `logica/ametek_orm.py`, `logica/preflight.py`,
  `logica/preflight_new.py`, `logica/cli.py`, e os scripts em `scripts/`.
- `tests/test_offline.py` pode ser rodado e editado livremente — não toca
  hardware, roda os dois ORMs em modo simulado.

Nenhuma outra restrição foi suspensa. Em especial, os limites físicos abaixo
continuam absolutos.

### Autorização de 2026-10-07 (tarefas em `docs/TAREFAS_NUVEM_2026-10-07.md`)

O dono autorizou, para cumprir essas tarefas (capturas padrão por classe,
seed na CLI, capturas = max(CLI, padrão), 220/380 V), editar também:

- `logica/sinais.py`, `logica/oscilloscope_orm.py`,
  `logica/calibracao_extremos.json` e `logica/analisar_sessao.py`;
- `experimentos_nativos/NN.py` e `experimentos_waveform/NN.py` **só** para
  atributos de classe (ex. `capturas_padrao`) e ganchos de bancada
  (`forma_para_bancada`, `ciclos_excluidos_da_validacao` etc.) — **nunca**
  mudando o que `gerar()` produz para uma dada seed (é o dataset).

Os limites inegociáveis abaixo continuam valendo integralmente: 220 V ou
380 V não autorizam subir `max_voltage_rms`/`max_peak_v` acima do hardware
(300 Vrms por fase, 425 Vp). Ver CHANGELOG/v1.12.md para o que mudou na
v1.12 (writes sincronizados por `*ESR?`, bloqueio prévio de pico,
`VOLTage:HIGH` = limite RMS, e o achado de segurança: nunca consultar a
fonte logo após `TRACe:DATA`).

### Autorização de 2026-10-12 (perfis de faixas; `CHANGELOG/v1.15.md`)

O dono autorizou mudar o que `gerar()` produz para uma dada seed, para
implementar os perfis `norma`, `literatura` e `fronteira` (`set perfil`):

- `experimentos_nativos/02.py`, `03.py`, `05.py` e
  `experimentos_waveform/06.py`, `10.py`–`16.py`, `20.py`: faixas e níveis
  passam a ser lidos de `logica/perfis.py` pelo perfil ativo;
- `logica/mestre.py`, `logica/cli.py`, `logica/analisar_sessao.py`,
  `scripts/relatorio_limites_bancada.py`: plumbing do perfil.

Condições: o perfil `literatura` (padrão) continua reproduzindo byte a byte o
`gerar()` do commit 34a0d82 (teste em `tests/test_offline.py`,
`PerfisDeFaixasTests`); as mudanças entram juntas numa versão congelada antes
da próxima campanha; as 63 capturas de 07/10 ficam como piloto. Início,
duração, fase e forma das classes não mudam. Os limites inegociáveis abaixo
continuam valendo integralmente (`max_voltage_rms`, `max_peak_v`,
`max_current_a`, pré-validação de pico).

### Autorização de 2026-10-12 (início, duração e fase sorteados; `CHANGELOG/v1.15.md`)

O dono autorizou também que `gerar()` passe a sortear início, duração e fase
da senoide base (Pergunta 7 e proposta 3 de `atividade.tex`), na mesma versão
congelada dos perfis, o que substitui a frase "início, duração, fase e forma
não mudam" da autorização acima. Editados: `experimentos_nativos/01.py`–`05.py`,
`18.py`, `19.py`; `experimentos_waveform/06.py`, `07.py`, `09.py`–`17.py`, `20.py`
(a 08 fica de fora); `logica/mestre.py` (`Sorteio`, pré-trigger por captura),
`logica/oscilloscope_orm.py` (só `definir_pre_trigger`), `logica/cli.py`
(`set sorteio`, estimativa de gravações), `logica/analisar_sessao.py`,
`scripts/recalibrar_extremos.py`. `SORTEIO=0` / `set sorteio off` reproduz byte a
byte o `gerar()` de 34a0d82. Limites e validações abaixo intactos.

## Limites inegociáveis (não mudar em nenhuma hipótese)

- `AMETEK_PORT=COM10` e `AMETEK_BAUDRATE=115200` continuam fixos e validados
  em `validate_bench_configuration()` (`logica/mestre.py`); não trocar
  porta/baud nem remover essa validação.
- Não remover nem enfraquecer validações de IDN, timeout, tamanho de waveform
  (6000 pontos) ou erros SCPI (`assert_no_errors`/`check_errors`) — inclusive
  as que ficaram MAIS específicas (ex.: o `assert_no_errors()` logo após
  `SOURce:FUNCtion:SHAPe:CSINusoid` em `configure_harmonics_csine()`, que
  corrigiu um erro que antes era atribuído ao comando SEGUINTE); nunca
  torná-las mais fracas.
- Não alterar `max_voltage_rms`, `max_peak_v` nem `max_current_a`, nem remover
  `ParameterOutOfBoundsError` em `ametek_orm.py`.
- Nenhum comando que energiza a saída pode rodar sem confirmação explícita
  digitada pelo operador (case-sensitive) — vale para a CLI de hoje e para
  qualquer fluxo futuro.
- A resiliência por classe (`Bancada.executar_bateria`) isola falhas de
  EXPERIMENTO mas continua abortando tudo, sem tentar de novo sozinho, diante
  de `CommunicationError` ou `FalhaFatalDeInstrumento` (serial caiu,
  impossível confirmar OUTPUT, impossível recuperar um estado seguro
  conhecido via `recuperar_estado_seguro()`). Não amplie o que conta como
  "falha de experimento recuperável" sem entender por que aquele tipo de erro
  específico é seguro de ignorar.
- O cache de TRACe em `program_capture()` (evita reescrever a Flash quando
  forma/tensão/frequência não mudaram desde a última chamada bem-sucedida na
  MESMA conexão) sempre reconfirma contra o instrumento (`TRACe:CATalog?`)
  antes de reaproveitar, e é automaticamente invalidado a cada reconexão
  (é um atributo da instância `AmetekMX30`, não algo persistido em disco). Não
  troque isso por um cache entre processos sem antes resolver como
  `AMETEK_CLEAR_USER_WAVEFORMS=1` (que apaga as TRACEs a cada conexão)
  invalidaria um cache assim.
- Captura de corrente permanece desligada por padrão (`CAPTURE_CURRENT=0`);
  não ativar sem `CURRENT_PROBE_ATTENUATION` e `CURRENT_BASE_A` fornecidos
  pelo usuário.
