# ametek_orm.py: a fonte AMETEK MX30-3Pi

```{include} /_includes/aviso-base.md
```


{bdg-info}`OFFLINE` Lido por inteiro em 2026-10-16 (`main` em `fa82f49`). Comportamentos da fonte real citam a quirk (A1 a A25) e o selo da evidência em {doc}`../quirks`.

**Pergunta:** o que o `ametek_orm.py` faz que um simples `write()` serial não faria? **Resposta:** traduz métodos Python em SCPI **validando antes, sincronizando depois de cada comando e conferindo a fila de erros**, mantém um modelo do estado da fonte (modo, forma, frequência base), monta de forma **pura** (sem SCPI) o que será programado numa captura de TRACe e tem um modo simulado. Tudo que o torna "estranho" (esperas, `*WAI`, readbacks, no-ops) é uma quirk medida na Rev. 5.53.

Os comandos têm entrada própria em {doc}`../scpi`; as sequências em {doc}`../scpi/sequencias`; o percurso de uma captura em {doc}`percurso-captura-trace`.

| Símbolo | Assinatura | Linha | Papel |
|---|---|---|---|
| `_transcrever` | `(tipo: str, texto: str) -> None` | [ametek_orm.py:42-47](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L42-L47) | grava `W`, `Q` e `R` com `time.monotonic()` no logger `AmetekORM.scpi` (trunca em 160 caracteres) |
| `ParameterOutOfBoundsError` | `class (AmetekORMError, ValueError)` | [ametek_orm.py:54-55](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L54-L55) | valor fora do limite de software (é também `ValueError`) |
| `CommunicationError` | `class (AmetekORMError)` | [ametek_orm.py:58-59](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L58-L59) | serial caiu, timeout, resposta vazia: **falha de infraestrutura**, nunca retentada |
| `InstrumentHardwareError` | `class (AmetekORMError)` | [ametek_orm.py:62-63](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L62-L63) | a fonte reportou erro SCPI ou não confirmou um estado: falha de experimento |
| `LeituraTraceError` | `class (AmetekORMError)` | [ametek_orm.py:66-70](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L66-L70) | a leitura de diagnóstico de uma TRACe falhou (não é falha de infraestrutura) |
| `FalhaFatalDeInstrumento` | `class (AmetekORMError)` | [ametek_orm.py:73-80](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L73-L80) | estado seguro irrecuperável: aborta a bateria |
| `formatar_valores` | `(valores: Sequence[float]) -> str` | [ametek_orm.py:87-91](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L87-L91) | `%.8g` separado por vírgula: fonte única do formato dos números enviados |
| `ProgramacaoCaptura` | `class ` | [ametek_orm.py:100-151](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L100-L151) | tudo o que `program_capture` programa, calculado sem SCPI |
| `ProgramacaoCaptura.programada_pu` | `(self) -> np.ndarray` | [ametek_orm.py:127-151](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L127-L151) | a forma que a fonte emite, de volta na grade de 30 kSa/s |
| `AmetekMX30` | `class ` | [ametek_orm.py:154-1986](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L154-L1986) | o driver |
| `AmetekMX30.connect` | `(self) -> None` | [ametek_orm.py:334-364](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L334-L364) | `OUTPut:STATe OFF` antes de qualquer coisa, depois confere o `*IDN?` |
| `AmetekMX30._raw_write` | `(self, command: str, *, append_eot: Optional[bool]=None) -> None` | [ametek_orm.py:394-421](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L394-L421) | LF mais EOT 0x04 em segunda transferência |
| `AmetekMX30.write` | `(self, command: str) -> None` | [ametek_orm.py:423-449](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L423-L449) | envia e só retorna depois que a fonte consumiu (`*ESR?`), salvo gravações em Flash |
| `AmetekMX30._sincronizar_apos` | `(self, command: str) -> None` | [ametek_orm.py:451-478](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L451-L478) | a consulta de sincronismo, com prazo de 20 s e tolerância a mudez |
| `AmetekMX30.query` | `(self, command: str) -> str` | [ametek_orm.py:480-503](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L480-L503) | descarta o buffer, escreve com EOT, lê; resposta vazia é `CommunicationError` |
| `AmetekMX30.check_errors` | `(self, max_errors: int=20) -> List[Tuple[int, str]]` | [ametek_orm.py:633-645](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L633-L645) | esvazia `SYSTem:ERRor?` (até 20) |
| `AmetekMX30.assert_no_errors` | `(self, context: str) -> None` | [ametek_orm.py:647-655](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L647-L655) | `check_errors` que vira `InstrumentHardwareError` |
| `AmetekMX30.output_enabled` | `(self, state: bool) -> None` | [ametek_orm.py:701-704](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L701-L704) | getter consulta; setter exige `authorize_output` para ligar |
| `AmetekMX30.energize_baseline` | `(self) -> None` | [ametek_orm.py:706-726](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L706-L726) | liga a saída uma vez, confirma por até 5 s |
| `AmetekMX30.aguardar_idle` | `(self, timeout_s: float=20.0) -> str` | [ametek_orm.py:774-808](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L774-L808) | espera `TRIGger:STATe?` = `IDLE` antes de escrever um transiente |
| `AmetekMX30._neutralizar_transientes_residuais` | `(self) -> None` | [ametek_orm.py:830-842](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L830-L842) | `FUNCtion:MODE FIXed` e `SOURce:FREQuency:MODE FIXed` |
| `AmetekMX30.definir_fase_de_disparo` | `(self, graus: float) -> None` | [ametek_orm.py:844-855](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L844-L855) | `TRIGger:SYNChronize:PHASe` com 0,1°; sem readback |
| `AmetekMX30.quantizar_tensao_rms` | `(cls, voltage_rms: float, max_voltage_rms: float) -> float` | [ametek_orm.py:868-874](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L868-L874) | arredonda a 0,1 V sem passar do teto (a fonte trunca) |
| `AmetekMX30.trigger_step` | `(self, voltage_rms: float) -> None` | [ametek_orm.py:876-906](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L876-L906) | STEP nativo (01, 05, 19) |
| `AmetekMX30.trigger_pulse` | `(self, voltage_rms: float, *, width_s: float) -> None` | [ametek_orm.py:908-937](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L908-L937) | PULSe nativo (02, 03, 04) |
| `AmetekMX30.configure_harmonics_csine` | `(self, thd_pct: float) -> None` | [ametek_orm.py:939-987](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L939-L987) | senoide clipada até 20 % (05) |
| `AmetekMX30.select_sine_shape` | `(self) -> None` | [ametek_orm.py:989-1011](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L989-L1011) | volta à senoide; no-op se já está nela |
| `AmetekMX30.enable_dc_offset` | `(self, offset_v: float, *, ac_peak_v: float) -> None` | [ametek_orm.py:1108-1138](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1108-L1138) | ACDC mais offset (19), limitado pelo pico |
| `AmetekMX30.disable_dc_offset` | `(self) -> None` | [ametek_orm.py:1013-1033](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1013-L1033) | desfaz; no-op fora de ACDC |
| `AmetekMX30.restaurar_forma_e_modo_padrao` | `(self) -> None` | [ametek_orm.py:1035-1048](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1035-L1048) | desfaz todo estado permanente que uma classe deixou |
| `AmetekMX30.restaurar_frequencia_base` | `(self) -> None` | [ametek_orm.py:1050-1064](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1050-L1064) | desfaz o último ponto da lista de frequência |
| `AmetekMX30.frequency_drift_list` | `(self, start_hz: float, end_hz: float, *, voltage_rms: float, dwell_s: float) -> None` | [ametek_orm.py:1066-1106](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1066-L1106) | rampa de 2 pontos (18) |
| `AmetekMX30.configure_safe_baseline` | `(self, *, voltage_range_rms: float, voltage_high_vp: float, current_limit_a: float, protection_delay_s: float, frequency_hz: float) -> None` | [ametek_orm.py:1212-1301](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1212-L1301) | os 22 comandos do estado seguro |
| `AmetekMX30.clear_all_traces` | `(self) -> None` | [ametek_orm.py:1303-1317](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1303-L1317) | `TRACe:DELete:ALL` só com a saída desligada; espera 15 s |
| `AmetekMX30._ensure_trace_slots` | `(self, trace_names: Sequence[str]) -> None` | [ametek_orm.py:1335-1351](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1335-L1351) | `TRACe:DEFine` dos nomes que faltam (3 s cada) |
| `AmetekMX30.ler_trace` | `(self, nome: str, *, espera_minima_s: float=2.0, timeout_s: float=15.0) -> np.ndarray` | [ametek_orm.py:1353-1405](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1353-L1405) | leitura de diagnóstico (`TRACe:DATA? <nome>`) com guardas contra a trava |
| `AmetekMX30.montar_programacao` | `(cls, waveform_pu: Sequence[float], *, base_voltage_rms: float, frequency_hz: float, dc_offset_pu: float=0.0) -> ProgramacaoCaptura` | [ametek_orm.py:1416-1509](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1416-L1509) | função pura: ciclos, TRACes e `LIST:VOLTage` de uma captura |
| `AmetekMX30.program_capture` | `(self, waveform_pu: Sequence[float], *, base_voltage_rms: float, frequency_hz: float, dc_offset_pu: float=0.0) -> None` | [ametek_orm.py:1511-1705](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1511-L1705) | programa a lista inteira e confere cada etapa |
| `AmetekMX30.arm` | `(self, timeout_s: float=20.0) -> None` | [ametek_orm.py:1707-1752](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1707-L1752) | arma um transiente nativo, com readback de cinco parâmetros |
| `AmetekMX30._conferir_transiente_programado` | `(self) -> None` | [ametek_orm.py:1782-1821](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1782-L1821) | compara o lido com o escrito (tolerância de 0,5 %) |
| `AmetekMX30.arm_transient` | `(self, timeout_s: float=20.0) -> None` | [ametek_orm.py:1823-1908](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1823-L1908) | arma a lista TRACe/LIST com nove leituras de volta |
| `AmetekMX30.trigger` | `(self) -> None` | [ametek_orm.py:1910-1922](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1910-L1922) | `*TRG` só se `ARM`/`WTRIG` |
| `AmetekMX30.wait_transient_complete` | `(self, timeout_s: float=5.0) -> None` | [ametek_orm.py:1924-1935](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1924-L1935) | espera `IDLE` e confere a fila |
| `AmetekMX30.safe_shutdown` | `(self) -> None` | [ametek_orm.py:1937-1961](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1937-L1961) | `ABORt`, `OUTPut:STATe OFF`, leitura, repetição, nunca levanta |
| `AmetekMX30.measure_voltage` | `(self) -> float` | [ametek_orm.py:1963-1977](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1963-L1977) | `MEASure:VOLTage:AC?` (em ACDC é o RMS total) |

## 1. Camadas de proteção, em ordem

```{mermaid}
flowchart TD
    M["método do projeto<br/>(ex.: trigger_pulse)"] --> V{"valida limites<br/>ParameterOutOfBoundsError"}
    V --> Q["quantiza (0,1 V) e espera IDLE"]
    Q --> W["write(): comando + EOT + *ESR?"]
    W --> E["check_errors(): SYSTem:ERRor? até 0"]
    E --> R["arm(): readback do que foi escrito"]
    R --> T["trigger(): só se ARM/WTRIG"]
```

1. **Limites no construtor e nos métodos.** `max_peak_v = min(max_peak_v, 425)` ([ametek_orm.py:194](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L194), constante `MAX_SOURCE_PEAK_V`); cada método semântico recusa valor fora de `0..max_voltage_rms`, `45..500 Hz` e `0 < A <= max_current_a` antes de qualquer SCPI.
2. **Interlock de software da saída.** `output_enabled = True` sem `authorize_output(True)` levanta `PermissionError`; só a CLI autoriza, durante o comando, e `authorize_output(False)` no `finally`.
3. **Primeira ação ao abrir é retirar potência.** `connect` manda `OUTPut:STATe OFF` por `_raw_write` **antes** do `*IDN?`, e confere o modelo contra `AMETEK_EXPECTED_MODEL`.
4. **Sincronismo por comando.** `write()` termina com `*ESR?` (`SINCRONISMO = "ESR"`). Exceção: `_SEM_SINCRONISMO` (`TRACE:DATA`, `TRACE:DEFINE`, `TRACE:DELETE`).
5. **Fila de erros** após cada passo relevante; 20 erros sem esvaziar viram `InstrumentHardwareError`.
6. **Readback** do que foi escrito antes de armar: cinco parâmetros no nativo (`_conferir_transiente_programado`), nove na lista (`arm_transient`).
7. **Estado seguro e desligamento.** `configure_safe_baseline` deixa a saída em **0 V**; `safe_shutdown` é a última linha e nunca levanta.

## 2. Invariantes (o que o resto do projeto pode supor)

- Todo `write()` termina com `*ESR?`, exceto as três gravações em Flash: a fonte perde comandos em rajada (A1) e fica muda se consultada logo depois de `TRACe:DATA` (A2).
- O EOT `0x04` vai numa segunda transferência (A23).
- `_modo_saida` e `_forma_atual` espelham o que a fonte tem; `select_sine_shape` e `disable_dc_offset` viram **no-op** quando nada há a desfazer, porque `SOURce:VOLTage:OFFSet` só é aceito em ACDC (A10) e um `SHAPe SINusoid` desnecessário custa uma troca de tabela (A7).
- `program_capture` reprograma tudo (inclusive `ABORt` e `*CLS` primeiro) e `arm_transient` **não** repete `ABORt` (A16).
- O cache de TRACe é atributo da **instância** e sempre reconfirma contra `TRACe:CATalog?` antes de reaproveitar; uma conexão nova começa com cache vazio, o que invalida o cache quando `AMETEK_CLEAR_USER_WAVEFORMS=1` apagou as TRACes.
- `montar_programacao` é função pura: `program_capture` envia **exatamente** o que ela devolve, e `ProgramacaoCaptura.programada_pu()` reconstrói offline a forma emitida. O que se envia e o que se grava como "programada" não podem divergir.

## 3. A função pura `montar_programacao`

[ametek_orm.py:1416-1509](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1416-L1509): dados 6000 amostras em pu, uma tensão base e uma frequência, devolve a `ProgramacaoCaptura`.

1. `pontos_por_ciclo = FS_HZ / frequency_hz` precisa ser inteiro e dividir 6000 (500 a 60 Hz, 600 a 50 Hz); senão `ValueError`.
2. Para cada ciclo: tira o componente CC do offset, calcula o **rms da componente CA** (sem a média do ciclo), `voltage_rms = base · √2 · rms_pu`, reamostra a 1024 pontos de forma **periódica** (`_resample_cycle`, `period=1.0`: ciclo fechado), tira a média da TRACe e normaliza pelo pico.
3. O pico físico reconstruído de cada ciclo é `max|TRACe enviada| · LIST:VOLTage / rms(TRACe enviada)`, calculado sobre os números **já arredondados a `%.8g`**, mais o pico do offset CC.

```{literalinclude} ../../logica/ametek_orm.py
:pyobject: ProgramacaoCaptura.programada_pu
:language: python
:caption: logica/ametek_orm.py, ProgramacaoCaptura.programada_pu
```

## 4. Armadilhas

1. `_SEM_SINCRONISMO` só tem as **formas longas** em maiúsculas, enquanto `_GRAVA_FLASH` cobre também `TRAC:DATA`, `TRAC:DEF`, `TRAC:DEL`. Hoje nenhum código manda a abreviada fora do simulador; quem o fizer faria `write()` consultar a fonte logo após a gravação (A2). Latente.
2. `safe_shutdown` captura **qualquer exceção**, inclusive o `InstrumentHardwareError("SHUTDOWN NÃO CONFIRMADO")` que ele mesmo levanta: a falha só vai a `logger.exception`. Quem confere é o operador no painel (`START_BENCH.cmd`).
3. **Atualização P-04:** `program_capture` recusa pico/RMS excessivos e valores não finitos antes de SCPI, catálogo ou cache. A guarda considera senoide base, forma completa, TRACe reconstruída e cada passo; o comportamento de aviso pertence à baseline histórica.
4. O simulador não modela os nove readbacks do `arm_transient`; testes e scripts de diagnóstico trocam `arm_transient`/`trigger` por stubs.
5. Os setters `voltage`, `frequency`, `current_limit` atualizam `_sim[...]` também em modo real: estado duplicado, inofensivo.
6. `measure_voltage` em ACDC devolve o RMS **total** (CA mais CC), apesar do manual; uma leitura sustenta isso (A19/H-1).
7. `*OPC?` não segura a resposta nesta revisão (A17): `AMETEK_SINCRONISMO` fica em `ESR`.
8. `measure_power_w` multiplica por 1000 supondo kW; a unidade de `MEASure:POWer:AC:REAL?` não foi verificada na fonte real.

## 5. Por que é assim: o histórico

- **`write()` sincronizado (v1.12, N1).** A rajada de quatro comandos pegou 0 de 3 vezes sem consulta e 9 de 9 com uma consulta depois de cada um; era a causa de H-NATIVO (`VOLTage:MODE` lido `FIX`, `PULSe:WIDTh` "preso").
- **`VOLTage:HIGH` com `max_voltage_rms` (v1.12, T12).** É limite **rms**, não de pico: o código antigo escrevia 415,8 achando que limitava o pico.
- **`quantizar_tensao_rms` (v1.12, N3).** A fonte trunca `VOLTage:TRIGgered` a 0,1 V; o readback com tolerância de 0,5 % recusava 2,7367 V lido como 2,7 V.
- **`LIST:REPeat 0` (v1.10).** `1` tocava cada ciclo duas vezes.
- **`*WAI` em lugar de polling por `*IDN?` (v1.7).** 15 a 47 ms contra vários segundos, 3 de 3 na bancada. `aguardar_resposta` ficou como recurso reserva.
- **`_neutralizar_transientes_residuais` (v1.11, P01).** `FUNCtion:MODE LIST` residual dava `-226` na classe 18.
- **Rms CA por ciclo (v1.15).** O código antigo calculava o rms com a média; a fonte remove a média e escala, então ciclos com degrau a meio ciclo saíam com amplitude maior e o pico previsto ficava até 38 % abaixo do real.
- **Passo final `SINE` (branch `feat/passo-final-sin`).** **Não existe na `main`**; ver a seção 7 abaixo ({ref}`passo-final-sin`).

## 6. Depende de e quem depende

Importa só `numpy` e `pyvisa` (opcional: sem PyVISA importa e roda simulado). **Não importa `mestre`.** É usado por `mestre.py`, `preflight_new.py`, por `analisar_sessao.py`/`recalibrar_extremos.py`/`gerar_tres_versoes.py` (para `montar_programacao` e `quantizar_tensao_rms`) e por vários `diag_*`. Mudar `ProgramacaoCaptura` ou `montar_programacao` afeta `programada_pu`, `program_capture`, `modelo_lista_fonte` e os scripts de diagnóstico ({doc}`acoplamentos`).

(passo-final-sin)=
## 7. Passo final SINE (experimental, desligado por padrão)

:::{warning} Estado atual da integração
P-18 foi integrado ao checkout de execução como opção experimental **desligada por padrão** (`AMETEK_PASSO_FINAL_SIN=0`; `passo_final_sin=False`). A autorização desta execução substitui a orientação anterior do branch de aguardar bancada para integrar. Isso não é aprovação física: a aceitação de `SINE` na lista pela Rev. 5.53 ainda exige o diagnóstico presencial e a confirmação digitada. Não habilitar automaticamente durante coleta.
:::

{bdg-warning}`NÃO VERIFICADO NA BANCADA` {bdg-danger}`PENDENTE P-18 FÍSICO`

O passo extra acrescenta `SINE` ao final da lista na tensão base e com um ciclo de duração, sem gravar uma TRACe adicional. O diagnóstico compara a saída antes/depois; teste simulado não comprova aceitação do comando pelo firmware. As seções abaixo registram o desenho e os resultados históricos do branch `feat/passo-final-sin`; onde descrevem padrão ligado ou integração bloqueada, a orientação vigente é a do aviso acima.

### 7.1 Por que existe

Ao fim de um `LIST` a MX30 continua no **último passo**: a lista de uma classe de TRACe acaba no último ciclo da forma, e a saída fica ali até outro comando (o mesmo fato que mantinha a fonte em 63 Hz depois da classe 18, quirk A11). Na margem de 50 ms depois da janela nominal, isso aparece como um ciclo repetido com a amplitude do último ciclo programado: a simulação do próprio branch mostra `LIST:VOLTage` final de **134,12689 V rms (1,056 pu)** a 127 V na classe 06, em vez da tensão base. O passo `SINE` na tensão base acaba com esse "último ciclo mantido". {bdg-warning}`NÃO VERIFICADO` na fonte real: o valor 1,056 pu é a conta do simulador do script (`--simulado`), não uma medida.

### 7.2 O que muda na SCPI

Para uma captura a 60 Hz (12 ciclos de 500 amostras), segundo o branch e os testes dele (324 testes, sem hardware):

| Comando | Sem o passo (padrão da `main`) | Com o passo (branch) |
|---|---|---|
| {scpi}`SOURce:LIST:FUNCtion:SHAPe` | `TCC00,...,TCC11` | `TCC00,...,TCC11,SINE` |
| {scpi}`SOURce:LIST:VOLTage` | 12 valores, o último é o rms do último ciclo (134,12689 no exemplo do branch) | 13 valores; o último é a tensão base (127) |
| {scpi}`SOURce:LIST:DWELl` | 12 valores | 13 valores (o passo `SINE` dura um ciclo, como os demais) |
| {scpi}`SOURce:LIST:REPeat` | `0` x 12 | `0` x 13 |
| `:POINts?` dos quatro eixos ({scpi}`SOURce:LIST:FUNCtion:POINts?`) | 12 | 13 |
| {scpi}`TRACe:DATA` | 12 gravações | **as mesmas 12** (nada novo na Flash) |

A conferência por `:POINts?` e o `assert_no_errors` logo depois de `LIST:FUNCtion:SHAPe` apontariam um nome rejeitado na hora, com a saída ainda sem disparar (erro `-113` ou `-224`).

**A evidência do nome.** O manual (`docs/manuais_txt/AMETEK_MX_SCPI_Programming_Manual.txt`, seção de `LIST:FUNCtion[:SHAPe]`, p. 93) aceita `SINe | SQUare | CSIN | <nome de forma>`; a transcrição de 07/10/2026 mostra `TRACe:CATalog? -> "SINE,SQUARE,CLIPPED"` ({doc}`../scpi/ametek-lista-trace`, exemplo E27), logo o nome do catálogo é `SINE`. Mas nenhuma sessão gravada usou uma forma interna na lista (todas usam `TCCnn`); `SIN` e `SINusoid` (esta é a forma que `SOURce:FUNCtion:SHAPe` aceita) são alternativas se `SINE` for rejeitado.

### 7.3 O que muda no ORM e no mestre (no branch)

Linhas do branch `github/feat/passo-final-sin` (base `d37e403`, não as da `main`):

| Onde | O que |
|---|---|
| [logica/ametek_orm.py:217](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L217) | `AmetekMX30.PASSO_FINAL_SIN_FORMA = "SINE"` |
| [logica/ametek_orm.py:235](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L235) | parâmetro do construtor `passo_final_sin: bool = True` (ligado por padrão) |
| [logica/ametek_orm.py:115](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L115) | campo `ProgramacaoCaptura.passo_final_sin`, mais `passos_nomes`, `passos_tensoes_rms`, `margem_final_pu()` e `programada_com_margem_pu()` |
| [logica/ametek_orm.py:1365-1446](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1365-L1446) | `montar_programacao(..., passo_final_sin=)` descreve o passo na função pura; `program_capture` envia exatamente o que ela devolve |
| [logica/ametek_orm.py:1469](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1469) | recusa (`ValueError`) se a tensão base passa de `max_voltage_rms`, antes de qualquer escrita |
| [logica/mestre.py:341](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L341) e `:990` | `AMETEK_PASSO_FINAL_SIN = env_bool("AMETEK_PASSO_FINAL_SIN", default=True)`, repassada ao construtor em `Bancada.from_env` |

`_last_cycles = N + 1`, que `arm_transient()` usa para conferir os `:POINts?`; `programada_pu()` continua devolvendo 6000 amostras (a margem final, uma senoide na base, sai de `margem_final_pu()`). As validações de IDN, timeout, 6000 pontos, `check_errors`/`assert_no_errors`, os limites de tensão e de pico e o cache de TRACe ficam como estavam: o passo é acrescentado depois do cache e a assinatura de TRACe não muda.

### 7.4 O script de validação e o critério

`diag/teste_passo_final_sin.py` (223 linhas, só no branch) roda a **mesma captura** (classe 06, mesma seed) sem e com o passo, ligando e desligando `fonte.passo_final_sin` entre as capturas, mede o rms por ciclo da margem final (os 50 ms depois da janela nominal) e a identidade da janela rotulada, grava `resultados/passo_final_sin_<data>/{registros.npz,resultado.json}` e dá o veredito. Reutiliza `Bancada`, `ExperimentoWaveform` e `_capturar_real` de `mestre.py`; **não escreve SCPI próprio**.

- **Segurança:** pergunta o fator exato da probe, a tensão e a frequência (sem valores padrão) e exige digitar `ENERGIZAR-PASSO-SIN` (case-sensitive) **antes** de definir `BENCH_MODE`/`ARM_OUTPUT=YES` e de importar `mestre`. Faixa de 300 V rms e 415,8 Vp como em `start_bench_windows.ps1`. A saída é desligada ao fim.
- **Critério de aprovação (código de saída 0; 2 = não eficaz):**

| Medida | Limite |
|---|---|
| rms por ciclo da margem final com o passo | 1,00 ± 0,01 pu da tensão base |
| janela rotulada, com × sem o passo | correlação ≥ 0,999 e diferença máxima de rms por ciclo ≤ 0,01 pu |
| erros SCPI | nenhum |

Os limiares (0,01 pu e 0,999) são **escolha do autor do script**, constantes no topo do arquivo, sem dado de bancada. Testado só em modo simulado (`--simulado`: registros sintéticos, valida a análise, não é medida) e na recusa de confirmação errada (nada é aberto).

### 7.5 Estado e o que fecha

- **O que fecha:** executar o script na bancada ({bdg-danger}`PENDENTE P-18`: operador, fonte e osciloscópio; o branch previa a validação para 14/10/2026) e **decidir** se o padrão deve ser desligado. Nenhuma pasta `resultados/passo_final_sin_*` existe no checkout principal nem no diretório de trabalho do branch (conferido em 2026-10-16): não há registro de que o script tenha rodado.
- **Depois de aprovado:** rodar uma classe de TRACe pela CLI (`run 06`) e conferir as três versões ({doc}`../tres_versoes`).
- **Se reprovar:** não integrar, ou mudar o padrão para `False`.

:::{note} Nota de verificação
Conferido offline em 2026-10-16 com `git`:

- `git diff --stat d37e403 github/feat/passo-final-sin`: 6 arquivos, 457 inserções e 13 remoções (`CHANGELOG/v1.15.md`, `docs/analise-2026-10-12/passo_final_sin.md`, `logica/ametek_orm.py`, `logica/mestre.py`, `diag/teste_passo_final_sin.py`, `tests/test_offline.py`).
- **Divergência registrada:** o relatório dentro do branch diz "rebaseado sobre a main 2abee44", mas o pai do único commit do branch é `d37e403` (`git merge-base main github/feat/passo-final-sin` devolve `d37e403`). O merge com a `main` (`fa82f49`) tem conflito textual em `CHANGELOG/v1.15.md` e em `tests/test_offline.py`; `ametek_orm.py` e `mestre.py` fundem sem marcador de conflito, mas a suíte do merge **não foi rodada** {bdg-warning}`NÃO VERIFICADO`. A suíte do branch (324 testes) é anterior à da `main` (497).
:::
