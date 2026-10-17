# ametek_orm.py: a fonte AMETEK MX30-3Pi

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


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
- **Passo final `SINE` (branch `feat/passo-final-sin`).** **Não existe na `main`**; ver {doc}`../projeto/passo-final-sin`.

## 6. Depende de e quem depende

Importa só `numpy` e `pyvisa` (opcional: sem PyVISA importa e roda simulado). **Não importa `mestre`.** É usado por `mestre.py`, `preflight_new.py`, por `analisar_sessao.py`/`recalibrar_extremos.py`/`gerar_tres_versoes.py` (para `montar_programacao` e `quantizar_tensao_rms`) e por vários `diag_*`. Mudar `ProgramacaoCaptura` ou `montar_programacao` afeta `programada_pu`, `program_capture`, `modelo_lista_fonte` e os scripts de diagnóstico ({doc}`acoplamentos`).
