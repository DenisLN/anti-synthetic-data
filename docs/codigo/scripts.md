# Scripts

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Lido por docstrings, símbolos e partes de `recalibrar_extremos.py` e `diag_*` em 2026-10-16 (`main` em `fa82f49`). Quais scripts já rodaram na bancada: cada linha abaixo diz.

**Pergunta:** que scripts existem em `scripts/`, quais energizam e qual a ordem em que se usam? **Resposta:** são 6 arquivos `.ps1`/`.cmd` (porta de entrada, ambiente, limites) e 12 `.py` (recalibração, relatórios offline, verificações de sessão e diagnósticos). **Só os `diag_marcadores_trace.py`, `diag_acdc_amplitude.py`, `diag_saida_vs_medida.py`, `diag_fonte_vs_osciloscopio.py` e os preflights energizam**; todos pedem confirmação digitada. Os dois primeiros passam pelos ORMs; os dois últimos usam PyVISA cru ({doc}`../scpi/diagnostico`).

## 1. Porta de entrada e ambiente (`.cmd` e `.ps1`)

| Arquivo | O que faz | Observações |
|---|---|---|
| `START_BENCH.cmd` | chama `start_bench_windows.ps1` sem perfil de usuário e com `ExecutionPolicy Bypass`; imprime "CONFIRME OUTPUT OFF NO PAINEL" ao fim | é o que o operador roda |
| `start_bench_windows.ps1` | prepara o ambiente (`setup_windows.ps1`), carrega `bench_config.ps1`, pergunta o fator **exato** da probe, a tensão e a frequência, recusa tensão acima de 270 V, **sobrescreve** `SOURCE_VOLTAGE_RANGE_RMS`, `EUT_MAX_VOLTAGE_RMS` (300) e `EUT_MAX_PEAK_V` (415,8 = 98 % de 300·√2) e executa `logica/cli.py` | os limites vivem aqui **e** em `mestre.py`/`relatorio_limites_bancada.py`/`diag_*` (três cópias de 300 e 415,8) |
| `bench_config.ps1` | `BENCH_MODE=1`, `ARM_OUTPUT=NO`, `AMETEK_PORT=COM10`, `AMETEK_BAUDRATE=115200`, `AMETEK_CLEAR_USER_WAVEFORMS=1`, valores de partida dos limites | `VOLTAGE_PROBE_ATTENUATION` fica vazio de propósito: o operador digita |
| `setup_windows.ps1` | cria o `env\` (Python 3.9 a 3.12) e instala `requirements.txt` | |
| `run_simulation_windows.ps1` | dataset simulado: `BENCH_MODE=0`, `ARM_OUTPUT=NO`, chama `logica\mestre.py` | |
| `package_windows.ps1` | zip sem `env`, `resultados`, `logs`, `.git` | |

## 2. Recalibração e relatórios offline

| Símbolo | Assinatura | Linha | Papel |
|---|---|---|---|
| `pico_programado_reconstruido_v` | `(registro: dict, script_path: Path) -> float` | [recalibrar_extremos.py:71-95](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/recalibrar_extremos.py#L71-L95) | reconstrói o pico programado de sessão antiga com o código atual da classe |
| `condicao_do_registro` | `(registro: dict) -> Tuple[str, float, float]` | [recalibrar_extremos.py:98-101](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/recalibrar_extremos.py#L98-L101) | `(chave, tensão, frequência)` de uma linha de metadata |
| `fator_de_captura_reduzida` | `(registro: dict, extremo_v: float, fator_referencia: float) -> float` | [recalibrar_extremos.py:104-112](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/recalibrar_extremos.py#L104-L112) | inverte a fórmula do limite de bancada |
| `coletar` | `(sessoes: List[Path], tabelas_atuais: Optional[Dict[str, Dict[str, object]]]=None) -> Tuple[Fatores, Dict[str, int], Dict[str, Tuple[float, float]]]` | [recalibrar_extremos.py:118-185](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/recalibrar_extremos.py#L118-L185) | `{condição: {classe: [fatores]}}` das sessões, contando o que ignorou |
| `MudancaDeFator` | `class (NamedTuple)` | [recalibrar_extremos.py:188-194](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/recalibrar_extremos.py#L188-L194) | um fator que muda (ou é criado) numa tabela |
| `ResultadoRecalibracao` | `class ` | [recalibrar_extremos.py:197-207](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/recalibrar_extremos.py#L197-L207) | o que mudou, o que ignorou, condições sem tabela |
| `recalibrar` | `(sessoes: List[Path], *, gravar: bool=False, substituir: bool=False, arquivo: Optional[Path]=None, automatico: bool=False, saida=print) -> Resultad...` | [recalibrar_extremos.py:214-315](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/recalibrar_extremos.py#L214-L315) | o que `main` faz, como função; `automatico` nunca diminui e nunca cria tabela |
| `main` | `(argv: Optional[List[str]]=None) -> int` | [recalibrar_extremos.py:318-330](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/recalibrar_extremos.py#L318-L330) | linha de comando: `--gravar`, `--substituir`, `--arquivo` |

`recalibrar_extremos.py` (**offline**): fator = `max(|VMAX|, |VMIN|) ÷ pico programado`; capturas reduzidas entram invertendo a fórmula; a 08 e as simuladas ficam de fora; usa `_OscOffline` (basta não ser `None`) e **altera `mestre.LIMITE_BANCADA_DISTURBIO` temporariamente** durante a reconstrução ({doc}`../medicao/recalibracao`).

| Símbolo | Assinatura | Linha | Papel |
|---|---|---|---|
| `relatorio` | `(tensao: float, *, frequencia: float, capturas: Optional[int], seed: int, perfil: str=perfis.PERFIL_PADRAO) -> List[str]` | [relatorio_limites_bancada.py:84-135](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/relatorio_limites_bancada.py#L84-L135) | a tabela do que cabe na bancada, com `avaliar_captura_na_bancada` (sem segunda implementação) |
| `main` | `(argv: Optional[List[str]]=None) -> int` | [relatorio_limites_bancada.py:138-157](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/relatorio_limites_bancada.py#L138-L157) | `--tensao`, `--frequencia`, `--capturas`, `--seed`, `--perfil` |

`relatorio_limites_bancada.py` (**offline**) repete `RANGE_RMS` e `TETO_PICO_V` à mão (os limites de `start_bench_windows.ps1`).

| Script | Papel | Energiza? | Notas |
|---|---|---|---|
| `gerar_tres_versoes.py` | regenera modelo e programada de sessões do **formato 1** em pasta nova | não | recusa pasta com arquivos e recusa o formato 2 ({doc}`../tres_versoes`) |
| `gerar_ruido_janela.py` | AWGN de 20, 30 e 40 dB só na janela rotulada, offline | não | mesma conta de `sinais.ruido_na_janela`; lê os dois formatos |
| `verificar_sessao_bancada.py` | `fase_18` (continuidade de fase na troca de frequência), `largura_pulse`, `pre_trigger`; saída 0, 1 ou 2 | não | só validado com sinais sintéticos; limiares de 10°, 2 ms e 2 amostras são propostas (P-05, P-06) |
| `diag_ciclos_trace.py` | qual ciclo programado (k−1, k, k+1 ou k sem CC) explica cada ciclo medido | não | rodado em 2026-10-15 nas sessões reais de 07/10 (P-02); carrega o formato 1 sem erro |

## 3. Diagnósticos de bancada

| Script | Pergunta que responde | Confirmação | Estado |
|---|---|---|---|
| `diag_marcadores_trace.py` | que forma a MX30 emite em cada passo do LIST? (marcadores por ciclo, evento na fronteira e a meio ciclo) | `ENERGIZAR-MARCADORES` | pronto, **nunca rodou**; recusa pico/rms acima do limite antes de energizar (compensa P-04); teto de 250 gravações |
| `diag_acdc_amplitude.py` | por que o CA da classe 19 sai 5 a 6 % menor em ACDC? | `ENERGIZAR-ACDC` | pronto, **nunca rodou** (P-17) |
| `diag_nativo_output_off.py` | N1 a N3 e T10 a T14 do caminho nativo, com a saída **sempre desligada** | nenhuma (nunca envia `OUTPut ON`) | rodado em 30/09/2026; `--flash` recusado |
| `diag_saida_vs_medida.py`, `diag_fonte_vs_osciloscopio.py` | a medida do osciloscópio concorda com a da fonte? | `ENERGIZAR-50V`, `ENERGIZAR-127V` | **PyVISA cru**, `ASRL10::INSTR` e endereço USB fixos, sem `validate_bench_configuration` |
| `diag_osciloscopio_canais.py` | configuração dos canais | nenhuma (só lê e manda `:RUN`) | 39 linhas |

## 4. Armadilhas

1. Os limites 300 Vrms e 415,8 Vp estão copiados em `start_bench_windows.ps1`, `relatorio_limites_bancada.py` e nos `diag_*`: três fontes de verdade (risco R-6).
2. `recalibrar_extremos.py` é importado pela CLI por `sys.path.append` ({doc}`cli`).
3. `gerar_tres_versoes.py` reconstrói a programada com `montar_programacao` **de hoje**: para sessões gravadas antes da v1.15 a programada difere do que a fonte recebeu nas classes de média por ciclo diferente de zero ({doc}`../medicao/correlacao`).
4. Vários `diag_*` têm `_OscFicticio`/`_FisicaFicticia` para o modo `--simulado`; o simulado valida a análise, **não é medida** de bancada.

## 5. Ordem de uso típica

1. Antes da bancada: `relatorio_limites_bancada.py --tensao V --frequencia F` (o que cabe).
2. Bancada: `START_BENCH.cmd` → `comm`, `trigger`, `native`, `run ...`.
3. Depois: `verificar_sessao_bancada.py`, `diag_ciclos_trace.py`, `analisar_sessao.py`, `recalibrar_extremos.py`, `relatorio_html.py`.
