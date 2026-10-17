# preflight_new.py: os preflights

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Lido em 2026-10-16 (`main` em `fa82f49`); os preflights não foram executados (energizam ou abrem instrumentos). Uso pelo operador: {doc}`../operacao` e {doc}`../guia-operador`.

**Pergunta:** o que cada preflight prova e por que existem dois níveis? **Resposta:** `comm` prova a comunicação e `OUTPUT OFF`; `trigger` prova a aquisição e o download do Keysight (sem testar o BNC); `lowvoltage` prova a cadeia inteira na **tensão base digitada** (BNC, 6000 pontos, rms dentro de 10 %); `native` exercita STEP, PULSe, CSINusoid, lista de frequência, ACDC, as medidas `MEASure:*` e o canal 2, cada um pela **mesma sequência de armamento** que `ExperimentoNativo._capturar_real` usa. Testar uma ordem diferente validaria um caminho que a bancada real não percorre.

| Símbolo | Assinatura | Linha | Papel |
|---|---|---|---|
| `RMS_TOLERANCE_V` | (constante ou variável de módulo) | [preflight_new.py:52](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L52) | tolerância de rms: `max(0,25 V, 10 % da base)` |
| `run_basic_stage` | `(trigger_test: bool, low_voltage: bool) -> int` | [preflight_new.py:86-164](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L86-L164) | `comm`, `trigger` e `lowvoltage` |
| `run_com_log` | `(stage: str, funcao: Callable[[], int]) -> int` | [preflight_new.py:167-174](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L167-L174) | executa uma função gravando `logs/preflight_new-<etapa>-*.log` (entrada da CLI) |
| `ToleranciaExcedida` | `class (RuntimeError)` | [preflight_new.py:177-195](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L177-L195) | medida fora da tolerância: **aviso**, não aborta |
| `_capture_native` | `(source, scope, *, configure: Callable[[], None], expected_peak_v: float) -> Tuple[np.ndarray, np.ndarray]` | [preflight_new.py:253-274](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L253-L274) | reproduz `ExperimentoNativo._capturar_real` (ramo não-TRACe) |
| `_test_step` | `(source, scope) -> str` | [preflight_new.py:277-286](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L277-L286) | STEP nativo |
| `_test_pulse_sag` | `(source, scope) -> str` | [preflight_new.py:289-344](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L289-L344) | PULSe nativo |
| `_test_csine` | `(source, scope) -> str` | [preflight_new.py:347-366](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L347-L366) | senoide clipada nativa |
| `_test_frequency_drift` | `(source, scope) -> str` | [preflight_new.py:369-383](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L369-L383) | lista de frequência |
| `_test_dc_offset` | `(source, scope) -> str` | [preflight_new.py:386-434](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L386-L434) | ACDC mais offset |
| `_test_measurements` | `(source) -> str` | [preflight_new.py:437-463](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L437-L463) | as quatro `MEASure:*`, isoladas |
| `_test_list_repeat_count` | `(source) -> str` | [preflight_new.py:596-680](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L596-L680) | prova que `LIST:REPeat:COUNt` é rejeitado (espera o erro) |
| `run_list_diagnostics` | `() -> int` | [preflight_new.py:683-707](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L683-L707) | só programa e lê de volta listas SCPI, nunca energiza |
| `run_native_commands` | `() -> int` | [preflight_new.py:710-749](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L710-L749) | o preflight `native` |
| `main` | `() -> int` | [preflight_new.py:752-802](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L752-L802) | linha de comando (`--list-diagnostics`, `--native-commands`, ...) |

## 1. Estágios e o que energiza

| Comando da CLI | Função | Energiza? | Confirmação digitada |
|---|---|---|---|
| `comm` | `run_basic_stage(trigger_test=False, low_voltage=False)` | não; falha se a saída estiver ligada | nenhuma |
| `trigger` | `run_basic_stage(trigger_test=True, low_voltage=False)` | não; só força o osciloscópio (`force_trigger`) | nenhuma |
| `lowvoltage` | `run_basic_stage(trigger_test=False, low_voltage=True)` | sim, tensão base | `ENERGIZAR-TESTE` |
| `native` | `run_native_commands` | sim | `ENERGIZAR-COMANDOS` |

A confirmação digitada fica **na CLI**, não aqui. `lowvoltage` programa as TRACes (cerca de 40 a 50 s de Flash) e é a única etapa que arma e dispara a fonte com TRACe; `trigger` não: a MX30 Rev. 5.53 não arma o transiente com a saída desligada, então forçar só o osciloscópio valida a aquisição "sem fingir que o BNC foi testado".

## 2. Armadilhas

1. `OUTPUT_ARMED` é importado **por valor** (`from mestre import ... OUTPUT_ARMED`); por isso `SessaoCLI.autorizar_saida` atualiza `preflight_new.OUTPUT_ARMED` também ({doc}`cli`).
2. Abre os instrumentos por `Bancada.from_env`, mas o tratador de Ctrl+C só entra em `from_env` (`garantir_ctrl_c_no_windows`). O aviso da v1.14 ("não coberto") refere-se ao preflight rodado **direto** (`python logica/preflight_new.py`).
3. `ToleranciaExcedida` é **aviso**: o comando foi aceito e o transiente ocorreu; só o número não bateu. A cadeia de medição (probe de 500×, 8 bits de resolução vertical, offset CC da probe) tem erro próprio. Falha **estrutural** (SCPI rejeitado, timeout, waveform ausente ou com clipping) aborta.
4. `_test_list_repeat_count` **espera** a rejeição de `LIST:REPeat:COUNt`: um "erro" ali é o resultado correto ({doc}`../scpi/ametek-nao-funciona`).
5. As constantes de teste (`SAG_LEVEL_PU = 0,5`, `CSINE_THD_PCT = 10`, `FREQ_DRIFT_START_HZ = f0 − 3`, `DC_OFFSET_PU = 0,05`) são **de preflight**, não vêm de `perfis.py`.

## 3. Por que é assim

- **Preflight único (v1.15).** O `preflight.py` foi removido; `lowvoltage` sempre rodou na tensão digitada no início (127 V) apesar do rótulo "5 V". A confirmação passou a ser `ENERGIZAR-TESTE` e o aviso mostra a tensão real; para recomissionar a 5 V, inicie o `START_BENCH` digitando 5 V.
- **Log em disco.** A CLI só deixava saída no terminal; `run_com_log` grava `logs/preflight_new-<etapa>-*.log`, o arquivo que se entrega a quem diagnostica uma falha de `comm`, `trigger`, `lowvoltage` ou `native`.
- **Mesma ordem da bancada.** `configurar → osc.arm()/wait_for_armed() → fonte.arm() → fonte.trigger()`.

## 4. Depende de e quem depende

Importa `mestre` (constantes, `Bancada`) e `sinais.janela`. É chamado por `cli.py` e, direto, por `python logica/preflight_new.py`.
