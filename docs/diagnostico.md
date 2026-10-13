# Diagnóstico: como investigar antes de corrigir

Regra do projeto: comportamento que parece errado **não se corrige por palpite**. Primeiro diagnostique com as funções internas (`set diagnostico on`) ou com um script que chame as funções do projeto isoladamente e reproduza o caso; registre o resultado (`docs/analise-AAAA-MM-DD/`); só então mude o código, com teste de regressão. Linhas: commit `d37e403`.

## 1. `set diagnostico on` (CLI)

`mestre.DIAGNOSTICO_MODE = True` (`cli.py:401-407`). Vale a partir do próximo `run`. Efeitos:
- `AmetekMX30._log_diagnostico(ponto)` (`ametek_orm.py:620`) lê `STATus:OPERation:CONDition?` (bit 3 = transiente ativo), `OUTPut:STATe?` e `MEASure:VOLTage:AC?` e grava `[DIAGNOSTICO] ponto=… t=… transiente_ativo=… output=… tensao_v=…`. Cada leitura tolera falha sem derrubar a captura.
- Pontos: `fim_trigger_step`, `fim_trigger_pulse`, `antes_sourcemode_acdc`, `apos_sourcemode_acdc`, `antes_voltage_mode_list`, `apos_voltage_mode_list`, `arm_antes_wai`, `arm_apos_init`, `arm_transient_antes_wai`, `arm_transient_apos_init`, `apos_trigger`, `transiente_concluido`.
- Abre um terminal PowerShell com `Get-Content -Wait -Tail 20` da `scpi_transcricao.log` da sessão (`cli.py:43-57,222-254`). `DIAGNOSTICO_ABRIR_TERMINAL=0` desliga a janela.
- `metadata`: `diagnostico_mode`.

A **transcrição SCPI** (`sessao.log` e `scpi_transcricao.log`) existe em todo `run`, com ou sem diagnóstico: `W` comando, `Q` consulta, `R consulta -> resposta`, com `t=` monotônico. É a primeira coisa a ler numa falha.

## 2. Roteiro de investigação

1. Reproduza **offline** quando possível: `tests.test_offline` (instrumentos simulados e `ScriptedVisaConnection`), ou um script em `docs/analise-AAAA-MM-DD/` que importe `mestre`/`ametek_orm`/`sinais` com `sys.path.insert(0, "logica")` (exemplos: `scripts/diag_fonte_vs_osciloscopio.py`; os diagnósticos temporários de 2026-10-12 estão em `arquivo/analises:docs/analise-2026-10-12/scripts/`).
2. Para dados já gravados: `logica\analisar_sessao.py`, `scripts\gerar_tres_versoes.py`, `scripts\relatorio_limites_bancada.py`, `relatorio_html.py`.
3. Só então use hardware, com a menor energia possível e os scripts da seção 3.
4. Registre hipóteses refutadas junto com as confirmadas.

## 3. Scripts de diagnóstico

| Script | Energiza? | Confirmação | Uso |
|---|---|---|---|
| `scripts/diag_nativo_output_off.py` | **não** (nunca envia `OUTPut ON`; tensões ≤ 5 V só nos registradores) | — | `--so estado,pulso,resolucao,rajada,opcoes,limite,pos_trava,opc` (padrão `opcoes,limite`). Feche a CLI antes. `--flash` é recusado (consultar após `TRACe:DATA` trava a fonte) |
| `scripts/diag_saida_vs_medida.py` | sim | `ENERGIZAR-<V>V` | `--tensao` (≤ 130, padrão 50), `--faixa 150\|300`, `--duracao`; lê a medida da própria fonte nas 3 fases |
| `scripts/diag_fonte_vs_osciloscopio.py` | sim | `ENERGIZAR-127V` | fonte e CH1 lado a lado, direto e em degrau |
| `scripts/diag_osciloscopio_canais.py` | não | — | só leitura dos 4 canais do Keysight (envia `:RUN`) |
| `scripts/diag_acdc_amplitude.py` | sim | `ENERGIZAR-ACDC` | `BENCH_MODE=1`, `--probe` obrigatório; `--vrms`, `--hz`, `--offsets-pu`, `--testar-compensacao`, `--simulado` (sem hardware, ganho FICTÍCIO); mede o déficit de CA em ACDC |
| `scripts/diag_ciclos_trace.py` | **não** (offline, só lê a sessão) | — | `<sessao_dir> [--classes 08,09] [--instante-ms 100] [--tol-rms-pu] [--margem-empate] [--saida logs]`; ver §3.1 |
| `scripts/diag_marcadores_trace.py` | sim | `ENERGIZAR-MARCADORES` | `BENCH_MODE=1`, `--probe` obrigatório; `--vrms`, `--frequencias 50,60`, `--variantes marcadores,fronteira,meio_ciclo`, `--instantes-evento-ms 40,80`, `--amp-pu`, `--simulado` (+ `--simular "mecanismo:chave=valor"`); ver §3.1 |
| `logica/diag_digitizer_*.py` | — | — | removidos em 2026-10-13 (modo Digitizer, v1.10, descartado; histórico no git até `d3c7ce7`) |
| `preflight_new.py --list-diagnostics` | não | — | confirma comandos `SOURce:LIST:*` com write+leitura |

Cada diagnóstico que energiza desliga a saída no `finally` (inclusive Ctrl+C). Conferir OUTPUT OFF no painel ao final. Exceções de infraestrutura: seguir `docs/operacao.md` §7.

### 3.1 Cópia do evento em 100 ms (08 e 09): leitura dos resultados

Sintoma (07/10, `docs/quirks.md` A22 e A25): o início do evento aparece repetido ou deslocado em 100,0 ms a 50 e a 60 Hz. A montagem da TRACE está descartada (`montar_programacao` põe o evento onde foi pedido); o mecanismo dentro da fonte é **NÃO VERIFICADO**. Três peças, nesta ordem:

1. **`diag_ciclos_trace.py` (offline, nas sessões de 07/10, no PC da bancada).** Para cada captura TRACe compara cada ciclo medido k, alinhado em `inicio_janela`, com os ciclos programados k-1, k, k+1 e, quando o metadata permite reconstruir `gerar()`, com o ciclo k da forma de bancada sem a média (`k_sem_dc`). Colunas do resumo: ciclos cujo melhor explicador não é k (`trocado`), primeiro ciclo trocado e seu instante, quem o explica (`k-1` = a fonte tocou a forma do passo anterior), a primeira amostra com divergência > `--limiar-amostra-pu` (0,05) e o resíduo máximo em torno de 100 ms (de 99,5 a 102 ms) e global. Um candidato diferente de k só vence se reduzir o resíduo rms em mais de `--margem-empate` (0,01 pu): ciclos de senoide pura são idênticos entre si e empatam, e então vale k. `sem_explicacao` = nenhum candidato fica abaixo de `--tol-rms-pu` (0,03 pu); olhar o resíduo por candidato na tabela da captura. Saída em `logs/diag_ciclos_trace-<sessao>.md` e `.json`; a pasta da sessão não é escrita. O carregamento do formato em disco está só em `carregar_sessao()`.
2. **`diag_marcadores_trace.py` (bancada).** Programa pelo mesmo `program_capture` e mede pelo mesmo ORM do osciloscópio. Variantes: `marcadores` (um marcador de posição e amplitude únicas em cada ciclo), `fronteira` (impulso no ponto 0 do ciclo) e `meio_ciclo` (impulso a meio ciclo), estas duas nos instantes de `--instantes-evento-ms` (40 e 80 ms: a 50 Hz os ciclos 2 e 4, a 60 Hz os ciclos 3 e 5). Se a cópia cair em 100 ms **nos dois instantes**, é instante fixo; se acompanhar o ciclo do evento (+1 ciclo), é troca de passo. Na tabela por captura: `k tocado` é o passo cujo marcador saiu naquele ciclo medido, `deslocamento (ciclos)` = ciclo medido - k, `atraso (amostras)` o resto abaixo de um ciclo, `ESPÚRIO` um pico sem marcador programado e `ausentes` os marcadores que nunca saíram (o último, se tudo foi atrasado um passo). A última linha de cada captura é o ranking das hipóteses de `logica/modelo_lista_fonte.py` (menor rms do resíduo primeiro).
3. **`logica/modelo_lista_fonte.py` (provisório).** `prever_forma(programacao, mecanismo, **params)` devolve a forma que a fonte emitiria se o mecanismo fosse verdadeiro: `ideal` (= `programada_pu()`), `atraso_de_passos` (`d`, `t_inicio_s`, `tensao`), `transicao_forma_anterior` (`amostras`, `t_inicio_s`), `copia_no_instante` (`t_s`, `ciclo_origem`, `inicio_na_origem`, `n_amostras`, `ganho`, `modo`) e `deslocamento_no_tempo` (`t_inicio_s`, `atraso_s`). `confrontar()` ordena `HIPOTESES_CANDIDATAS` contra uma medida. A hipótese vencedora não é prova: é a que menos erra naquele dado. Os valores de partida são chutes dos sintomas de 07/10.

`--simulado` do `diag_marcadores_trace.py` usa fonte e osciloscópio FICTÍCIOS que tocam o mecanismo dado em `--simular` (padrão `ideal`; ex. `"atraso_de_passos:d=1,t_inicio_s=0.1"`) e `--atraso-simulado N` amostras: só exercita o fluxo e a leitura, não diz nada sobre a fonte real.

## 4. Achados que esperam diagnóstico na bancada
Ver a seção "NÃO VERIFICADO" de `arquivo/analises:docs/analise-2026-10-12/pendente/apresentabilidade_VERIFICAR.md` e `docs/quirks.md` (itens A3, A19, A22, A25, K4).
