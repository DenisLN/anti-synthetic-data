# Comandos SCPI usados e sua função

Extraído de `logica/ametek_orm.py` e `logica/oscilloscope_orm.py` (referências por símbolos revisadas sobre `fa82f496`; mudanças correntes: `docs/execucao_pendencias.md`). "Manual" = página do **PDF** em `docs/AMETEK_MX_SCPI_Programming_Manual.pdf` / `docs/Keysight_4000X_Programmers_Guide.pdf` (texto pesquisável em `docs/manuais_txt/`). Onde a Rev. 5.53 (AMETEK) ou o firmware 07.30 (Keysight) difere do manual, está em `docs/quirks.md`. Nenhum experimento escreve SCPI cru: tudo passa pelos métodos da coluna "Método".

## 1. Camada de transporte (AMETEK)

- Serial virtual pela USB, `ASRL10::INSTR`: 115200 baud, 8 bits, sem paridade, 1 stop, sem controle de fluxo, terminadores `\n` (`_configure_visa_resource`, `ametek_orm.py`).
- Cada comando vai em `comando + "\n"` e, se `AMETEK_QUERY_EOT=1` (padrão), o byte `0x04` vai em **uma segunda transferência** (`_raw_write`, `logica/ametek_orm.py`). Sem o EOT a fonte não executa comandos sem resposta.
- `write()` espera a fonte consumir o comando com uma consulta `*ESR?` (ou `*OPC?` com `AMETEK_SINCRONISMO=OPC`); não aplica a `TRACe:DATA/DEFine/DELete` (`_SEM_SINCRONISMO`, `logica/ametek_orm.py`). Bits de erro do ESR (0x04|0x08|0x10|0x20) viram aviso no log.
- `query()` descarta o buffer de entrada antes, escreve com EOT e lê; resposta vazia = `CommunicationError`.
- Transcrição: todo W/Q/R com `time.monotonic()` no logger `AmetekORM.scpi` (gravada em `scpi_transcricao.log` da sessão; payloads truncados a 160 caracteres).

## 2. AMETEK MX30-3Pi

### 2.1 Identificação, erros e estado
| Comando | Função | Método (símbolo no ORM) | Manual |
|---|---|---|---|
| `OUTPut:STATe OFF` | desliga a saída; **primeiro** comando de `connect` e de `safe_shutdown` | `connect`, `safe_shutdown` | 16, 19, 73 |
| `*IDN?` | identificação; conferida contra `AMETEK_EXPECTED_MODEL` | `connect` | 7 |
| `SYSTem:ERRor?` | esvazia a fila de erros (até 20) | `check_errors` | 117 |
| `*CLS` | limpa fila/registradores | `configure_safe_baseline`, `program_capture`, recuperação | 7 |
| `*ESR?` / `*OPC?` | sincronismo de cada `write()` | `_sincronizar_apos` | 133-141 |
| `*WAI` | espera o processamento em paralelo de list/trigger | `configure_harmonics_csine`, `select_sine_shape`, `enable_dc_offset`, `arm`, `arm_transient` | 142 |
| `STATus:OPERation:CONDition?` | bit 3 = transiente ativo (só com `diagnostico on`) | `_log_diagnostico` | 114 |
| `OUTPut:STATe?` | confirma estado da saída | `output_enabled`, `safe_shutdown` | 16, 19 |
| `TRIGger:STATe?` | `IDLE`/`ARM`/`WTRIG`; esperas | `aguardar_idle`, `arm`, `wait_transient_complete` | 132 |

### 2.2 Baseline (`configure_safe_baseline`, `logica/ametek_orm.py`)
Antes: `OUTPut:STATe OFF` e `*CLS`. Depois cada um destes, com `check_errors()`:

| Comando | Função |
|---|---|
| `ABORt` | reseta o sistema de trigger (não desliga a saída aqui) |
| `INSTrument:COUPle ALL` | acopla as 3 fases |
| `SOURce:MODE AC` | saída AC pura |
| `SOURce:VOLTage:RANGe <300>` | range da fonte |
| `SOURce:VOLTage:HIGH <max_voltage_rms>` | limite **rms** da fonte (não de pico; ver quirks) |
| `SOURce:CURRent <A>`, `SOURce:CURRent:PROTection:STATe ON`, `SOURce:CURRent:PROTection:DELay <s>` | limite e proteção de corrente |
| `SOURce:FUNCtion:SHAPe SINusoid` | forma de onda senoidal |
| `FUNCtion:MODE FIXed`, `VOLTage:MODE FIXed`, `SOURce:FREQuency:MODE FIXed` | eixos independentes em modo fixo |
| `SOURce:FREQuency:SLEW MAXimum`, `SOURce:VOLTage:SLEW MAXimum` | taxa de variação máxima |
| `SOURce:FREQuency <f0>`, `SOURce:VOLTage 0` | frequência base; **0 V** (nunca pula direto para a tensão de teste) |
| `TRIGger:SOURce BUS` | transiente disparado por `*TRG` |
| `TRIGger:SYNChronize:SOURce PHASe`, `TRIGger:SYNChronize:PHASe 0` | transiente começa numa fase definida |
| `OUTPut:TTLTrg:MODE TRIG`, `OUTPut:TTLTrg:SOURce BOT`, `OUTPut:TTLTrg ON` | pulso BOT na saída Trigger Out (vai ao BNC) |

Depois: `OUTPut:STATe ON` só por `energize_baseline` (exige `authorize_output`); `energize_baseline` confirma por leitura em até 5 s.

### 2.3 Valores imediatos
| Comando | Método |
|---|---|
| `SOURce:VOLTage:LEVel:IMMediate:AMPLitude <V>` / `?` | `voltage` (0 a `max_voltage_rms`) |
| `SOURce:FREQuency <Hz>` / `?` | `frequency` (45–500 Hz) |
| `SOURce:CURRent:LEVel:IMMediate:AMPLitude <A>` / `?` | `current_limit` (0 a `max_current_a`) |
| `MEASure:VOLTage:AC?`, `MEASure:CURRent:AC?`, `MEASure:POWer:AC:REAL?`, `MEASure:POWer:AC:PFACtor?` | `measure_*` |

### 2.4 Caminho nativo (classes 01–05, 18, 19)
Antes de cada programação: `aguardar_idle()` e `_neutralizar_transientes_residuais()` (`FUNCtion:MODE FIXed`, `SOURce:FREQuency:MODE FIXed`, `logica/ametek_orm.py`).

| Método | Comandos | Função |
|---|---|---|
| `trigger_step` | `VOLTage:MODE STEP`, `VOLTage:TRIGgered <V>` (múltiplo de 0,1 V) | no `*TRG` a tensão salta e **permanece** (classes 01, 05, 19) |
| `trigger_pulse` | `VOLTage:MODE PULSe`, `VOLTage:TRIGgered <V>`, `PULSe:WIDTh <s>` | no `*TRG` a tensão vai a `<V>` por `<s>` e volta (02, 03, 04) |
| `definir_fase_de_disparo` | `TRIGger:SYNChronize:PHASe <graus, 1 casa>` | fase da saída em que o `*TRG` aplica o transiente |
| `configure_harmonics_csine` | `SOURce:FUNCtion:SHAPe CSINusoid`, `*WAI`, `SOURce:FUNCtion:SHAPe:CSINusoid <THD %>`, `*WAI` | senoide clipada (THD 0–20 %) |
| `select_sine_shape` | `SOURce:FUNCtion:SHAPe SINusoid`, `*WAI` | volta à senoide (no-op se já senoide) |
| `enable_dc_offset` | `SOURce:MODE ACDC`, `*WAI`, `SOURce:VOLTage:OFFSet <V>` | offset contínuo; recusa se `abs(offset)` + pico AC > `max_peak_v` |
| `disable_dc_offset` | `SOURce:VOLTage:OFFSet 0`, `SOURce:MODE AC`, `*WAI` | no-op se já AC. Braços B/C da P-09: só `SOURce:VOLTage:OFFSet 0`, `*WAI` (fica em AC+DC) |
| `frequency_drift_list` | `VOLTage:MODE FIXed`, `FREQuency:MODE LIST`, `LIST:FREQuency a,b`, `LIST:VOLTage v,v`, `LIST:DWELl d,d`, `SOURce:LIST:REPeat 0,0`, `LIST:COUNt 1`, `LIST:STEP AUTO`, `VOLTage:MODE LIST` | rampa de 2 pontos (classe 18) |
| `restaurar_frequencia_base` | `SOURce:FREQuency:MODE FIXed`, `SOURce:FREQuency <base>` | desfaz o último ponto da lista |
| `restaurar_forma_e_modo_padrao` | os três acima | chamado no fim de toda classe física |
| `arm` | `*WAI`, `INITiate:IMMediate`, leitura de `TRIGger:STATe?` até `ARM`/`WTRIG` | arma; antes, `_conferir_transiente_programado` lê `VOLTage:MODE?`, `VOLTage:TRIGgered?`, `PULSe:WIDTh?`, `FUNCtion:MODE?`, `SOURce:FREQuency:MODE?` e recusa divergência (tolerância 0,5 %) |
| `trigger` | `*TRG` (só se `ARM`/`WTRIG`) | dispara |
| `wait_transient_complete` | `TRIGger:STATe?` até `IDLE`, depois `SYSTem:ERRor?` | espera o fim |

Manual: `VOLTage:MODE` 90-153, `VOLTage:TRIGgered` 108-109, `PULSe:WIDTh` 104-106, `FUNCtion:MODE` 85, `FREQuency:MODE` 81, `TRIGger:SYNChronize` 131, `INITiate` 129, offset 108.

### 2.5 Caminho TRACe/LIST (classes 06–17, 20, 05 a 30 %)
`program_capture`:

| Passo | Comandos |
|---|---|
| reset | `ABORt`, `*CLS`, `FUNCtion:MODE FIXed`, `VOLTage:MODE FIXed`, `SOURce:MODE AC` (ou `ACDC` com offset), `SOURce:FREQuency <f0>`, `SOURce:FREQuency:MODE FIXed`, `SOURce:FUNCtion:SHAPe SINusoid`, `SOURce:VOLTage <base>`, `SOURce:VOLTage:OFFSet` (se houver) |
| TRACes (só se a assinatura mudou ou o catálogo perdeu) | `TRACe:CATalog?`; para cada ausente `TRACe:DEFine TCCnn` (~3 s); para cada ciclo `TRACe:DATA TCCnn,<1024 valores %.8g>` seguido de **1 s de espera** e `*CLS` (sem consultar a fonte) |
| lista | `SOURce:LIST:FUNCtion:SHAPe TCC00,…`, `SOURce:LIST:VOLTage v0,…`, `SOURce:LIST:DWELl d,…` (cada um com `check_errors` e `…:POINts?` igual ao nº de ciclos) |
| modos | `SOURce:LIST:REPeat 0,0,…`, `SOURce:LIST:COUNt 1`, `SOURce:LIST:STEP AUTO`, `FUNCtion:MODE LIST`, `VOLTage:MODE LIST`, `TRIGger:SOURce BUS`, `TRIGger:SYNChronize:SOURce PHASe`, `TRIGger:SYNChronize:PHASe 0`, `OUTPut:TTLTrg:MODE TRIG`, `OUTPut:TTLTrg:SOURce BOT`, `OUTPut:TTLTrg ON` |

Em `montar_programacao`: ciclos de `30000/f0` amostras (12 a 60 Hz → 500 amostras; 10 a 50 Hz → 600), cada um reamostrado a 1024 pontos, média removida, normalizado pelo pico, com reamostragem periódica (ciclo fechado); o rms da componente CA do ciclo (sem a média, como a fonte escala a TRACe sem DC) vai em `LIST:VOLTage`; `DWELl` = 1 ciclo exato. O nome da TRACe é `TCC00…`.

`arm_transient` espera `IDLE`, lê 9 consultas de volta (`OUTPut:STATe?`, `FUNCtion:MODE?`, `VOLTage:MODE?`, `SOURce:FREQuency:MODE?`, `SOURce:LIST:FUNCtion|VOLTage|DWELl|REPeat:POINts?`, `TRIGger:SOURce?`), compara com o esperado, e então `*WAI`, `INITiate:IMMediate`. **Não** repetir `ABORt` aqui. Depois: `trigger`, `wait_transient_complete`.

Apagar TRACes: `TRACe:DELete:ALL` (`clear_all_traces`): só com OUTPUT OFF, antes de `energize_baseline`; espera 15 s sem consultar.

Ler de volta uma TRACe (só diagnóstico, `set diagnostico retrieve`; `ametek_orm.py`): `TRACe:DATA? <nome>` → 1024 valores separados por vírgula, "normalized values in the range of ±1" (manual p. 147, §6.2.7). **O manual é ambíguo**: a descrição do `TRACe[:DATA]` (p. 126) diz `Query Syntax: none`, e a p. 147 diz que, "when queried, trace data is returned as normalized values". A sintaxe `TRACe:DATA? <nome>` e o formato (lista NRf separada por vírgula, sem bloco `#`) são, portanto, **NÃO VERIFICADOS na fonte real**; `ler_trace` aceita só uma lista numérica de exatamente 1024 valores finitos (`LeituraTraceError` caso contrário). Regras de segurança: nunca como comando seguinte a uma escrita de TRACe (recusa), espera mínima de 2 s desde a última escrita de TRACe/DEFine/DELete (quirk A2), timeout próprio de 15 s restaurado depois, e só depois de a captura terminar.

**Experimento P-09 (`AMETEK_P09_BRACO`, padrão `A`).** No braço A nada acima muda. Nos braços B e C a conexão vai a AC+DC uma vez, com a saída OFF, ao fim de `configure_safe_baseline` (`preparar_braco_p09`): `*CLS`, `SOURce:MODE ACDC`, `*WAI`, a consulta de suporte abaixo (B também consulta, mas não recusa), `SOURce:VOLTage:OFFSet 0` e, se a fonte confirmou o comando, offsets de LIST zerados. Com o suporte confirmado, os offsets de LIST são zerados (`SOURce:LIST:VOLTage:OFFSet 0,…` do tamanho da lista, `SYSTem:ERRor?` e leitura de volta; `_zerar_offsets_lista`) também em cada captura B, em `frequency_drift_list` (2 pontos), no fim de cada classe e na recuperação (`disable_dc_offset`) e em `safe_shutdown` (depois do OFF, antes de voltar a AC). Falha ao zerar é `BracoP09Error` (fatal; `recuperar_estado_seguro` a repassa). Daí em diante `program_capture` **não** envia `SOURce:MODE` (trocar o modo zera a saída, manual p. 98) e manda sempre `SOURce:VOLTage:OFFSet <offset global em V>` (0 sem classe de offset). `disable_dc_offset` só zera o offset, sem trocar o modo. `safe_shutdown` envia `SOURce:MODE AC` depois de `OUTPut:STATe OFF`.

| Comando (braço C) | Função | Método | Manual |
|---|---|---|---|
| `SOURce:LIST:VOLTage:OFFSet?` | consulta de suporte em AC+DC, com a saída OFF, seguida de `SYSTem:ERRor?`. Sem resposta, resposta não numérica ou erro na fila: no C, `OffsetPorPassoNaoSuportadoError`, antes de energizar. Se falhar no meio, `consultar_suporte_offset_lista` volta ao modo pedido (com a saída OFF) antes de repassar o erro | `consultar_suporte_offset_lista`, `preparar_braco_p09`, `scripts/diag_list_offset.py` | **não confirmado**: p. 96 só como "Related Command" (`LIST:VOLT:OFFS`) |
| `SOURce:LIST:VOLTage:OFFSet o0,o1,…` | offset DC de cada passo (V, `%.8g`) = offset global + média do ciclo (`ProgramacaoCaptura.passos_offsets_v`). Enviado depois de `LIST:DWELl`, com `check_errors` e leitura de volta (quantidade igual ao nº de passos, valores dentro de 0,1 V + 0,5 %) | `program_capture` → `_programar_offsets_lista` | **não confirmado** (idem) |

Antes de qualquer I/O, o braço C recusa (`ParameterOutOfBoundsError`): pico de algum passo com o seu offset acima de `max_peak_v` (pico com sinal, `max|CA escalada + offset do passo|` sobre os 1024 pontos enviados, em `pico_reconstruido_v`; classe 16, fronteira, seed 2, 50 Hz: 179,6 V, o pico do modelo), offset com módulo acima de 220 V (`MAX_DC_OFFSET_V`; manual p. 10: 220 Vdc na Série II, 250 Vdc na Série I) e rms total `sqrt(CA² + CC²)` de algum passo acima de `max_voltage_rms`. A assinatura do cache de TRACe inclui o braço e os offsets nos braços B e C.

Manual: TRACe 126-127, LIST 90-97 e 153-154, `SOURce:MODE` 79/98, `INSTrument:COUPle` 53.

### 2.6 Comandos que **não** funcionam ou **não** são usados
- `SOURce:FUNCtion:SHAPe CSINe` (abreviação do manual) → `-256`; use `CSINusoid`.
- `SOURce:LIST:REPeat:COUNt`, `LIST:REPeat:COUNt` → `-113`; só `SOURce:LIST:REPeat` (com prefixo, sem `:COUNt`).
- `SOURce:FUNCtion:SHAPe?` e `SOURce:MODE?` **não existem como consulta** na Rev. 5.53 (deixam `-113` na fila).
- `TRIGger:SYNChronize:PHASe?`: nunca testado (por isso `definir_fase_de_disparo` não faz readback).
- `SYSTem:REMote`: nunca enviado (painel frontal permanece ativo).

## 3. Keysight DSO-X 4034A

Referências `[KS] p.` são as do código (PDF).

| Método (símbolo no ORM) | Comandos | Função |
|---|---|---|
| `verify_identity` | `*IDN?` | confere `DSOX4034A` |
| `check_errors` | `:SYSTem:ERRor?` | esvazia a fila |
| `initialize_safe` | `:STOP`, `*CLS`, `:ACQuire:TYPE NORMal`, `:WAVeform:FORMat BYTE`, `:WAVeform:UNSigned ON`, `:WAVeform:POINts:MODE RAW` | estado inicial seguro |
| `configure_channel` | `:CHANnel<n>:DISPlay/PROBe/COUPling/UNITs/OFFSet/SCALe/BWLimit` | CH1 (tensão, DC, escala `EUT_MAX_PEAK_V/3`); CH2 só com `CAPTURE_CURRENT` |
| `disable_channel` | `:CHANnel<n>:DISPlay 0` | desliga o CH2 |
| `set_vertical_scale` | `:CHANnel<n>:OFFSet 0`, `:CHANnel<n>:SCALe pico/3` | 3 das 4 divisões por polaridade; reajusta a `pico/2` se `4·escala < 1,05·pico`; erro se ainda não cobre |
| `configure_acquisition` | `:STOP`, `:ACQuire:TYPE NORMal`, `:ACQuire:MODE RTIMe`, `:ACQuire:DIGitizer OFF`, `:TIMebase:MODE MAIN`, `:TIMebase:RANGe <200 ms ou 270 ms>`, referência e posição (abaixo), `:ACQuire:POINts:ANALog:AUTO ON`, `:ACQuire:SRATe:ANALog:AUTO ON`, `:WAVeform:POINts:MODE NORMal`, `:WAVeform:POINts 60000`, FORMat/UNSigned; confere `:ACQuire:POINts:ANALog?`, `:ACQuire:SRATe:ANALog?` (≥ 0,995 × 30 kSa/s), `:TIMebase:RANGe?` (±1 %) | modo automático (taxa e pontos explícitos ligam o Digitizer, descartado) |
| `_programar_referencia_horizontal` | `:TIMebase:REFerence CUSTom`, `:TIMebase:REFerence:LOCation 0.0`, leitura de volta; se falhar: `:TIMebase:REFerence LEFT` e compensa 1 divisão (RANGe/10) | referência exatamente na borda esquerda |
| `definir_pre_trigger` | `:TIMebase:POSition -<pré-trigger>` (+ `RANGe/10` se a referência caiu para LEFT) | pré-trigger; por captura quando sorteado |
| `setup_external_trigger` | `:EXTernal:PROBe/UNITs/RANGe`, `:TRIGger:HFReject OFF`, `:TRIGger:MODE EDGE`, `:TRIGger:SWEep NORMal`, `:TRIGger:EDGE:SOURce EXTernal`, `:TRIGger:EDGE:LEVel`, `:TRIGger:EDGE:SLOPe POSitive` | dispara no BOT da AMETEK |
| `arm` | `:AER?`, `:TER?` (zeram registradores), `:SINGle` | arma (necessário a **cada** captura) |
| `is_armed`/`wait_for_armed` | `:OPERegister:CONDition?` bit 32 | espera "wait for trigger" |
| `wait_for_trigger_complete` | `:TER?` = 1 e bit 8 (RUN) apagado de `:OPERegister:CONDition?` | espera a aquisição single terminar |
| `force_trigger` | `:TRIGger:FORCe` | aquisição sem o BNC (usado por `trigger` e pela cadeia de medição) |
| `medir_vrms_forcado` | `:MEASure:VRMS? DISPlay,AC,CHANnel1` | Vrms do CH1 em regime |
| `medir_extremos` | `:MEASure:VMAX? CHANnel1`, `:MEASure:VMIN? CHANnel1` | extremos na taxa cheia; `9.9E37` = medida inválida ⇒ erro |
| `get_waveform` | `:WAVeform:SOURce/FORMat/UNSigned/POINts:MODE/POINts`, `:WAVeform:PREamble?`, `:WAVeform:DATA?` | lê o registro; exige 10 campos de preamble, BYTE, ≥ 6000 pontos, rejeita código 0 (buraco) e 1/255 (clipping); reamostra a 30 kSa/s |
| `safe_stop/close` | `:STOP` | não fecha o `ResourceManager` |

`indice_trigger = round(−x_origin × 30000)` é onde o trigger caiu no registro entregue.

## Referências verificáveis e transcrições (P-24/P-29)

Os nomes das tabelas apontam para métodos em `logica/ametek_orm.py` ou `logica/oscilloscope_orm.py`; números de página são dos manuais, não linhas de código. Localize um símbolo com `rg -n 'def NOME' logica/ametek_orm.py logica/oscilloscope_orm.py`.

Esta referência descreve os comandos encontrados no código e nos manuais. **Não substitui uma transcrição real.** Os logs físicos das sessões citadas não estão disponíveis neste checkout; P-29 continua bloqueada. Exemplos de resposta só poderão ser chamados de medidos quando acompanhados de sessão, condição, SHA e arquivo de transcrição. Não foram criadas respostas artificiais como evidência de bancada.

```{toctree}
:hidden:

scpi/ametek-baseline
scpi/ametek-estado
scpi/ametek-imediatos
scpi/ametek-lista-trace
scpi/ametek-nao-funciona
scpi/ametek-nativo
scpi/diagnostico
scpi/keysight-aquisicao
scpi/keysight-trigger
scpi/keysight-waveform
scpi/sequencias
scpi/transcricoes
```
