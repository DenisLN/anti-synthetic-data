# Configuração: variáveis de ambiente e limites

Fonte única na bancada: `scripts/bench_config.ps1` (carregado pelo `start_bench_windows.ps1`, que ainda sobrescreve tensão, frequência, range e limites). `.env.example` é só referência para quem roda fora do fluxo PowerShell. O código lê tudo em `logica/mestre.py:233-363` (helpers `env_*`), `ametek_orm.py:180`, `cli.py:38` e `perfis.py:32`.

Valores booleanos aceitos: `1/true/yes/on` e `0/false/no/off` (`env_bool`, `mestre.py:233`); qualquer outro levanta `ValueError`. Números positivos obrigatórios onde o helper é `env_float`/`env_int`.

## Variáveis lidas pelo código

| Variável | Padrão no código | Significado |
|---|---|---|
| `BENCH_MODE` | `0` | `1` abre os instrumentos; `0` é simulado |
| `ARM_OUTPUT` | vazio (= não) | `YES` autoriza energizar. `bench_config.ps1` põe `NO`; a CLI liga só durante o comando |
| `AMETEK_PORT` | `COM10` | **fixo**: outra porta é recusada com `BENCH_MODE=1` |
| `AMETEK_BAUDRATE` | `115200` | **fixo**, idem |
| `AMETEK_TIMEOUT_S` | `5` | timeout de leitura da serial |
| `AMETEK_QUERY_EOT` | `1` | envia o byte `0x04` separado depois de cada comando (a USB da MX30 só responde assim) |
| `AMETEK_EXPECTED_MODEL` | `MX30` | substring conferida no `*IDN?` |
| `AMETEK_P09_BRACO` | `A` | Experimento P-09 (perda da média por ciclo). `A`: modo AC, como sempre. `B`: a conexão inteira em AC+DC com offset zero (isola o efeito AC+DC, P-17). `C`: AC+DC com offset DC por passo de LIST (`SOURce:LIST:VOLTage:OFFSet`, **não confirmado no manual**) igual à média de cada ciclo que a TRACe perde. B/C programam `SOURce:MODE ACDC` só com a saída OFF, ao fim de `configure_safe_baseline`, e voltam a AC em `safe_shutdown` depois do OFF; classes nativas também rodam em AC+DC. B e C consultam `SOURce:LIST:VOLTage:OFFSet?` antes de energizar (com suporte, os offsets de LIST são zerados fora das capturas C e no shutdown); C recusa a conexão (`OffsetPorPassoNaoSuportadoError`) se a fonte não confirmar, sem cair para A/B. Valor inválido é recusado ao abrir a conexão. Na CLI: `set p09 A\|B\|C` (próximo run); gravado no metadata como `p09_braco` |
| `AMETEK_CLEAR_USER_WAVEFORMS` | `0` (`bench_config.ps1`: **`1`**) | `1` apaga as TRACes de usuário a cada conexão (`TRACe:DELete:ALL`, ~15 s); invalida o cache de TRACe entre conexões |
| `AMETEK_SINCRONISMO` | `ESR` | consulta de sincronismo de `write()`: `ESR` (`*ESR?`) ou `OPC` (`*OPC?`); sem ganho com `OPC` |
| `KEYSIGHT_RESOURCE` | `USB0::0x0957::0x17A4::MY59240844::0::INSTR` | endereço VISA; `AUTO` ou vazio = descoberta |
| `KEYSIGHT_EXPECTED_MODEL` | `DSOX4034A` | conferido no `*IDN?` |
| `KEYSIGHT_TIMEOUT_MS` | `15000` | timeout VISA |
| `VOLTAGE_PROBE_ATTENUATION` | sem valor | **obrigatório** com `BENCH_MODE=1`; o `START_BENCH` pergunta se vazio |
| `BASE_VOLTAGE_RMS` | `127` | tensão base rms fase-neutro (o `START_BENCH` sobrescreve) |
| `GRID_FREQUENCY_HZ` | `60` | frequência da rede (idem) |
| `SOURCE_VOLTAGE_RANGE_RMS` | `150` (`START_BENCH`: 300) | range da fonte |
| `EUT_MAX_VOLTAGE_RMS` | `140` (`START_BENCH`: 300) | teto rms de software → `max_voltage_rms` do ORM e `SOURce:VOLTage:HIGH` |
| `EUT_MAX_PEAK_V` | `400` (`START_BENCH`: 415,8) | teto de pico de software → `max_peak_v` (limitado a 425 V no ORM) |
| `CURRENT_LIMIT_A` | `0.5` | limite de corrente → `max_current_a` e `SOURce:CURRent` |
| `CURRENT_PROTECTION_DELAY_S` | `0.1` | atraso da proteção (aceito entre 0,1 e 5 s) |
| `EXT_TRIGGER_PROBE_ATTENUATION`, `EXT_TRIGGER_RANGE_V`, `EXT_TRIGGER_LEVEL_V` | `1`, `8`, `1.5` | entrada EXT Trigger do osciloscópio |
| `CAPTURE_CURRENT` | `0` | exige `CURRENT_PROBE_ATTENUATION` e `CURRENT_BASE_A`; **não ativar sem fornecidos pelo usuário** |
| `CURRENT_PROBE_ATTENUATION`, `CURRENT_BASE_A` | sem valor | idem |
| `REAL_CAPTURES_PER_CLASS` | `1` | piso global de capturas físicas; cada classe roda `max(isto ou set capturas, padrão da classe)` |
| `SIM_CAPTURES_PER_CLASS` | `2000` | capturas por classe do dataset simulado (`run_simulation_windows.ps1` passa **1** por padrão) |
| `SNR_LEVELS_DB` | `20,30,40` | níveis de ruído acrescentado (dB); `.env.example` traz `30` |
| `BASE_SEED` | `20260827` (vazio = padrão) | seed base (inteiro ≥ 0) |
| `PERFIL` | `literatura` (vazio = padrão) | `norma`, `literatura` ou `fronteira` |
| `SORTEIO` | `1` | sorteio de início/duração/fase; `0` reproduz as posições fixas de antes |
| `LIMITE_BANCADA_DISTURBIO` | `1` | `0` desliga a redução do distúrbio (só pula) |
| `LIMITE_BANCADA_FRACAO_MINIMA` | `0.25` | menor fração aceita (em (0, 1]) |
| `MARGEM_FATOR_EXTREMO` | `1.10` | margem sobre o fator de extremo |
| `MARGEM_ANTES_S`, `MARGEM_DEPOIS_S` | `0.020`, `0.050` | folga de captura física; **não reduzir** sem refazer a medida (`mestre.py:2004-2022`) |
| `VALIDACAO_FISICA` | `1` | liga a validação pós-captura |
| `VALIDACAO_TOL_ENVELOPE`, `VALIDACAO_TOL_THD` | `0.15`, `0.20` | tolerâncias da validação |
| `BATERIA_EXCLUIR` | vazio | ids separados por vírgula que `run all` e `run <lista>` físicos excluem antes da confirmação (ex.: `08`); `run <NN>` isolado ainda roda |
| `SALVAR_BRUTO_OSCILOSCOPIO` | `0` | preserva a exportação BYTE/NORMal antes da interpolação em arquivos separados; também controlado por `set diagnostico bruto on\|off`; não faz aquisição extra |
| `DIAGNOSTICO_RETRIEVE_ESPERA_S` | `2.0` | espera mínima (s) entre a última escrita de TRACe e a leitura de `set diagnostico retrieve`; abaixo de 2 s avisa (quirk A2; `docs/diagnostico.md` §1.1). O liga/desliga é o comando `set diagnostico retrieve`, desligado por padrão |
| `DIAGNOSTICO_ABRIR_TERMINAL` | `1` | `0`/`false`/`off`/`no` impede `set diagnostico on` de abrir a janela de `tail -f` |

`scripts/diag_acdc_amplitude.py` também lê `BASE_VOLTAGE_RMS`, `GRID_FREQUENCY_HZ`, `VOLTAGE_PROBE_ATTENUATION`, `BENCH_MODE`.

## Sequência da P-10 (classe 05: RMS e THD por nível)

Sem variável nova: o nível sai de `capture_index` e da faixa do perfil (`thd_niveis`: norma 2/5/10/15/20 %, literatura 5/10/15/20/30 %). Sem `set capturas`, a 05 roda **só o nível 0** do perfil; `set capturas 1` (explícito) agrupa por nível e roda os cinco. Rota: até 20 % por CSINusoid, 30 % por TRACe (`rota_programacao` no metadata).

| Ponto | Comandos | Capturas |
|---|---|---|
| 2 % (norma, CSIN) | `set perfil norma`, `set capturas 1`, `run 05` | 2, 5, 10, 15, 20 % (todos CSIN) |
| 10, 15, 20 % (CSIN) e 30 % (TRACe) | `set perfil literatura`, `set capturas 1`, `run 05` | 5, 10, 15, 20 % (CSIN) e 30 % (TRACe, 12 gravações) |

Cada `run` pede a confirmação digitada. Avaliação: `scripts/fechar_pendencias.py` (P-10) por nível e rota.

## Regras de `validate_bench_configuration()` (`mestre.py:366-387`)

Roda antes de abrir qualquer instrumento com `BENCH_MODE=1` e recusa se: a porta não for `COM10`; o baud não for `115200`; `VOLTAGE_PROBE_ATTENUATION` for ausente ou ≤ 0; `CAPTURE_CURRENT=1` sem `CURRENT_PROBE_ATTENUATION` e `CURRENT_BASE_A`; `BASE_VOLTAGE_RMS > EUT_MAX_VOLTAGE_RMS`; `EUT_MAX_VOLTAGE_RMS > SOURCE_VOLTAGE_RANGE_RMS`; ou a saída for pedida sem `ARM_OUTPUT=YES`.

Dentro do ORM, uma segunda barreira (`configure_safe_baseline`, `ametek_orm.py:1193-1215`) recusa: limite rms acima do range; `VOLTage:HIGH` (pico) acima do limite de pico do software, abaixo do pico autorizado ou acima da capacidade do range; atraso de proteção fora de 0,1–5 s.

## Variáveis que NÃO existem na `main`

`AMETEK_PASSO_FINAL_SIN=0` é o padrão atual: passo final SINE experimental integrado ao checkout de execução, desligado até validação física (P-18). `1` habilita o passo extra na lista; não habilitar automaticamente durante coleta. Ver `docs/projeto/passo-final-sin.md`.
