# Diagnóstico: como investigar antes de corrigir

Regra do projeto: comportamento que parece errado **não se corrige por palpite**. Primeiro diagnostique com as funções internas (`set diagnostico on`) ou com um script que chame as funções do projeto isoladamente e reproduza o caso; registre o resultado (`docs/analise-AAAA-MM-DD/`); só então mude o código, com teste de regressão. Linhas: commit `d37e403`.

## 1. `set diagnostico on` (CLI)

`mestre.DIAGNOSTICO_MODE = True` (`cli.py:401-407`). Vale a partir do próximo `run`. Efeitos:
- `AmetekMX30._log_diagnostico(ponto)` (`ametek_orm.py:620`) lê `STATus:OPERation:CONDition?` (bit 3 = transiente ativo), `OUTPut:STATe?` e `MEASure:VOLTage:AC?` e grava `[DIAGNOSTICO] ponto=… t=… transiente_ativo=… output=… tensao_v=…`. Cada leitura tolera falha sem derrubar a captura.
- Pontos: `fim_trigger_step`, `fim_trigger_pulse`, `antes_sourcemode_acdc`, `apos_sourcemode_acdc`, `antes_voltage_mode_list`, `apos_voltage_mode_list`, `arm_antes_wai`, `arm_apos_init`, `arm_transient_antes_wai`, `arm_transient_apos_init`, `apos_trigger`, `transiente_concluido`.
- Abre um terminal PowerShell com `Get-Content -Wait -Tail 20` da `scpi_transcricao.log` da sessão (`cli.py:43-57,222-254`). `DIAGNOSTICO_ABRIR_TERMINAL=0` desliga a janela.
- `metadata`: `diagnostico_mode`.

A **transcrição SCPI** (`sessao.log` e `scpi_transcricao.log`) existe em todo `run`, com ou sem diagnóstico: `W` comando, `Q` consulta, `R consulta -> resposta`, com `t=` monotônico. É a primeira coisa a ler numa falha.

### 1.1 `set diagnostico retrieve [on|off]`: ler de volta as TRACEs gravadas (v1.15)

Independente de `on|off` acima; desligado por padrão (`mestre.DIAGNOSTICO_RETRIEVE`, `mestre.py:354`; `status` mostra `diagnostico retrieve: ON|OFF`). Nunca se conferiu o que fica na Flash depois de `TRACe:DATA`; com ele ligado, cada captura que grava TRACEs (classes waveform e a 05 nativa quando usa TRACe) lê de volta as TRACEs que programou:

- **Quando** (`_ler_traces_de_diagnostico`, `mestre.py:2013`, chamado no fim de `_capturar_real`, `:2912` e `:3117`): depois de `wait_transient_complete` e depois de o osciloscópio já ter sido lido; nada é escrito na fonte até a próxima captura. Nunca entre duas escritas de TRACe e nunca logo após uma: `AmetekMX30.ler_trace` (`ametek_orm.py:1353`) recusa se o comando anterior foi `TRACe:DATA/DEFine/DELete` e espera até `DIAGNOSTICO_RETRIEVE_ESPERA_S` (padrão 2 s, o mínimo conservador do quirk A2) desde a última escrita. Valor abaixo de 2 s é aceito, com aviso no log.
- **Onde**: `<sessao>/diagnostico_trace/<id da captura>.npz` (`nomes`, `enviado`, `lido`, ambos `(ciclos, 1024)`, e `list_voltage_rms` = `LIST:VOLTage`), fora do `.npz` da captura (`_gravar_diagnostico_trace`, `:2063`). No metadata da captura, a chave `diagnostico_trace`: `arquivo`, `traces_programadas`, `traces_lidas`, `desvio_max` e `desvio_max_por_trace` (máximo de |lido − enviado|, em unidades da TRACe enviada, pico 1), `erro`, `espera_minima_s`, `espera_efetiva_s`, `duracao_leitura_s`.
- **Falha**: timeout, resposta ilegível ou tamanho diferente de 1024 (`LeituraTraceError`) é logada e gravada em `erro`, e a captura segue. Em seguida confere-se `*IDN?` (`aguardar_resposta`); se a fonte não responde, vale o caminho normal de `CommunicationError`/falha fatal da bateria.
- **Custo de tempo (estimativa, NÃO VERIFICADA na bancada)**: cada TRACe devolve ~10 kB (1024 valores `%.8g`) a 115200 baud, ~1 s de linha por TRACe, ou ~12 s para os 12 ciclos de 60 Hz (10 a 50 Hz), mais a espera mínima de 2 s quando a captura gravou TRACEs agora (o cache de TRACe, que não regrava, não paga a espera). Com o sorteio ligado toda captura regrava, então cerca de +14 s por captura (~15 min a mais em 63 capturas). O que o dado diz é só o que foi medido; use para auditar uma sessão curta, não a campanha inteira.
- **Interpretação**: o manual diz que a fonte remove a componente DC e escala a TRACe a um formato interno e devolve valores normalizados (±1) (p. 126 e 147); `desvio_max` ≠ 0 pode ser essa normalização/quantização, não erro. Se a escala devolvida for outra, só a bancada diz.

### 1.2 `set diagnostico bruto [on|off]`: preservar antes da interpolação

Desligado por padrão. `set diagnostico bruto on` (ou `SALVAR_BRUTO_OSCILOSCOPIO=1`) preserva a exportação BYTE/NORMal da mesma aquisição usada pelo dataset, antes de interpolar para 30 kSa/s. Não faz outra consulta ao osciloscópio. O sinal do dataset e sua interpolação permanecem os mesmos.

Cada canal gera um arquivo exclusivo em `<sessao>/bruto_osciloscopio/<perfil>/`. O NPZ pode ser lido com `allow_pickle=False`: contém códigos BYTE, preamble completa, `tempo_s` iniciado em zero, `tempo_trigger_s` relativo ao trigger e valores físicos (`tensao_v` no CH1; `corrente_a` no CH2). O `metadata_json` registra canal, captura, perfil, aquisição, seed, configuração e hash float64 little-endian do sinal correspondente em pu. O metadata da captura contém os caminhos e erros em `bruto_osciloscopio`.

O arquivo é salvo logo após a leitura de cada canal: CH1 sobrevive se CH2 falhar. Pode existir bruto de uma captura depois descartada; o hash permite procurar sua correspondência, mas não prova que a captura foi validada ou persistida no dataset. Falhas do diagnóstico aparecem no log e no metadata da captura quando disponível, sem eliminar a medida principal. Uma repetição nunca sobrescreve o arquivo anterior.

Para comparar uma exportação CH1, substitua o caminho e informe a frequência da sessão:

```powershell
.\env\Scripts\python.exe scripts\analisar_reamostragem.py --entrada <bruto_CH1.npz> --f0-hz 50 --harmonicos 10 --saida <analise_nova.json>
```

O analisador usa a taxa e o número de pontos registrados no NPZ para reproduzir a grade salva; `--fs-salvo` e `--pontos-salvos` permitem uma comparação alternativa explícita. Publica RMS, pico, erro temporal, energia espectral acima do Nyquist e THD ajustada conjuntamente com DC/seno/cosseno. A THD fica indisponível com justificativa quando faltam ciclos, fundamental ou condições numéricas suficientes. Hashes do arquivo, dos sinais e da configuração identificam a entrada usada.

**Escopo:** BYTE/NORMal é a exportação selecionada pelo driver (até 60000 pontos), não a memória interna completa nem a taxa do ADC. O FIR é referência de análise, sujeito a transição, bordas e suavização de transientes. O resultado não aprova substituir o interpolador nem demonstra a resposta do hardware sem uma captura real.

## 2. Roteiro de investigação

1. Reproduza **offline** quando possível: `tests.test_offline` (instrumentos simulados e `ScriptedVisaConnection`), ou um script em `arquivo/analises:docs/analise-AAAA-MM-DD/` que importe `mestre`/`ametek_orm`/`sinais` com `sys.path.insert(0, "logica")` (exemplos: `scripts/diag_fonte_vs_osciloscopio.py`; os diagnósticos temporários de 2026-10-12 estão em `arquivo/analises:docs/analise-2026-10-12/scripts/`).
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
| `scripts/diag_list_offset.py` | **não** (nunca envia `OUTPut ON`; recusa se a saída estiver ligada) | — | P-09: com OUTPUT OFF confirmado, `SOURce:MODE ACDC`, `SOURce:LIST:VOLTage:OFFSet?` (comando não confirmado no manual) e `SYSTem:ERRor?`, volta a `--modo-anterior` (padrão `AC`; a Rev. 5.53 não tem `SOURce:MODE?`) e grava `logs/diag_list_offset-<data>.json` com `git_commit`/`git_sujo`, resultado e comandos. `BENCH_MODE=1`; `--simulado [--sim-suportado]` roda offline (resultado FICTÍCIO). `suportado=true` libera o braço C (`AMETEK_P09_BRACO=C`) |
| `scripts/diag_ciclos_trace.py` | **não** (offline, só lê a sessão) | — | `<sessao_dir> [--classes 08,09] [--instante-ms 100] [--tol-rms-pu] [--margem-empate] [--saida logs]`; ver §3.1 |
| `scripts/diag_marcadores_trace.py` | sim | `ENERGIZAR-MARCADORES` | `BENCH_MODE=1`, `--probe` obrigatório; `--vrms`, `--frequencias 50,60`, `--variantes marcadores,fronteira,meio_ciclo`, `--instantes-evento-ms 40,80`, `--amp-pu`, `--simulado` (+ `--simular "mecanismo:chave=valor"`); ver §3.1 |
| `scripts/verificar_sessao_bancada.py` | **não** (offline: só lê `resultados\sessao_*`) | — | `<pasta da sessão>` `[--tol-fase-graus 10] [--tol-largura-ms 2] [--tol-pretrigger-amostras 2] [--json arq]`; rodar logo depois da bancada (ver abaixo) |
| `logica/diag_digitizer_*.py` | — | — | removidos em 2026-10-13 (modo Digitizer, v1.10, descartado; histórico no git até `d3c7ce7`) |
| `preflight_new.py --list-diagnostics` | não | — | confirma comandos `SOURce:LIST:*` com write+leitura |

Cada diagnóstico que energiza desliga a saída no `finally` (inclusive Ctrl+C). Conferir OUTPUT OFF no painel ao final. Exceções de infraestrutura: seguir `docs/operacao.md` §7.

### 3.1 Cópia do evento em 100 ms (08 e 09): leitura dos resultados

Sintoma (07/10, `docs/quirks.md` A22 e A25): o início do evento aparece repetido ou deslocado em 100,0 ms a 50 e a 60 Hz. A montagem da TRACE está descartada (`montar_programacao` põe o evento onde foi pedido); o mecanismo dentro da fonte é **NÃO VERIFICADO**. Três peças, nesta ordem:

1. **`diag_ciclos_trace.py` (offline, nas sessões de 07/10, no PC da bancada).** Para cada captura TRACe compara cada ciclo medido k, alinhado em `inicio_janela`, com os ciclos programados k-1, k, k+1 e, quando o metadata permite reconstruir `gerar()`, com o ciclo k da forma de bancada sem a média (`k_sem_dc`). Colunas do resumo: ciclos cujo melhor explicador não é k (`trocado`), primeiro ciclo trocado e seu instante, quem o explica (`k-1` = a fonte tocou a forma do passo anterior), a primeira amostra com divergência > `--limiar-amostra-pu` (0,05) e o resíduo máximo em torno de 100 ms (de 99,5 a 102 ms) e global. Um candidato diferente de k só vence se reduzir o resíduo rms em mais de `--margem-empate` (0,01 pu): ciclos de senoide pura são idênticos entre si e empatam, e então vale k. `sem_explicacao` = nenhum candidato fica abaixo de `--tol-rms-pu` (0,03 pu); olhar o resíduo por candidato na tabela da captura. Saída em `logs/diag_ciclos_trace-<sessao>.md` e `.json`; a pasta da sessão não é escrita. O carregamento do formato em disco está só em `carregar_sessao()`.
2. **`diag_marcadores_trace.py` (bancada).** Programa pelo mesmo `program_capture` e mede pelo mesmo ORM do osciloscópio. Variantes: `marcadores` (um marcador de posição e amplitude únicas em cada ciclo), `fronteira` (impulso no ponto 0 do ciclo) e `meio_ciclo` (impulso a meio ciclo), estas duas nos instantes de `--instantes-evento-ms` (40 e 80 ms: a 50 Hz os ciclos 2 e 4, a 60 Hz os ciclos 3 e 5). Se a cópia cair em 100 ms **nos dois instantes**, é instante fixo; se acompanhar o ciclo do evento (+1 ciclo), é troca de passo. Na tabela por captura: `k tocado` é o passo cujo marcador saiu naquele ciclo medido, `deslocamento (ciclos)` = ciclo medido - k, `atraso (amostras)` o resto abaixo de um ciclo, `ESPÚRIO` um pico sem marcador programado e `ausentes` os marcadores que nunca saíram (o último, se tudo foi atrasado um passo). A última linha de cada captura é o ranking das hipóteses de `logica/modelo_lista_fonte.py` (menor rms do resíduo primeiro).
3. **`logica/modelo_lista_fonte.py` (provisório).** `prever_forma(programacao, mecanismo, **params)` devolve a forma que a fonte emitiria se o mecanismo fosse verdadeiro: `ideal` (= `programada_pu()`), `atraso_de_passos` (`d`, `t_inicio_s`, `tensao`), `transicao_forma_anterior` (`amostras`, `t_inicio_s`), `copia_no_instante` (`t_s`, `ciclo_origem`, `inicio_na_origem`, `n_amostras`, `ganho`, `modo`) e `deslocamento_no_tempo` (`t_inicio_s`, `atraso_s`). `confrontar()` ordena `HIPOTESES_CANDIDATAS` contra uma medida. A hipótese vencedora não é prova: é a que menos erra naquele dado. Os valores de partida são chutes dos sintomas de 07/10.

`--simulado` do `diag_marcadores_trace.py` usa fonte e osciloscópio FICTÍCIOS que tocam o mecanismo dado em `--simular` (padrão `ideal`; ex. `"atraso_de_passos:d=1,t_inicio_s=0.1"`) e `--atraso-simulado N` amostras: só exercita o fluxo e a leitura, não diz nada sobre a fonte real.


### 3.2 `verificar_sessao_bancada.py` (offline, depois da bancada)

```powershell
cd C:\Users\denis\TCC\code
$s = (Get-ChildItem resultados -Directory | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
env\Scripts\python.exe scripts\verificar_sessao_bancada.py $s
```

Três verificações, uma linha por captura mais um resumo (min/mediana/max). Código de saída: 0 tudo aprovado, 1 alguma reprovada, 2 nada a verificar.

| Verificação | Classes | O que mede | Critério padrão |
|---|---|---|---|
| `fase_18` | 18 | salto de fase (graus) na troca `start_hz` -> `end_hz`: fase do sinal analítico, uma reta por passo, extrapoladas até o meio da janela (instante nominal da troca); mostra também f1/f2 medidas e onde as retas se cruzam (`intersecao_ms`) | \|salto\| <= 10 graus |
| `largura_pulse` | 02, 03, 04 | largura medida do evento (amplitude instantânea cruzando o ponto médio entre regime e evento) menos `duracao_s` do metadata | \|erro\| <= 2 ms |
| `pre_trigger` | 02-04 e toda captura com o campo | `pre_trigger_desvio_amostras` (`indice_trigger` do osciloscópio menos o previsto); sem o campo, a mesma conta a partir do metadata | \|desvio\| <= 2 amostras (o mesmo limite do aviso em `mestre.py`) |

Limites do método (medidos em dados sintéticos, `tests.test_offline.VerificadorSessaoBancadaTests`; **não** é medida de bancada): a largura tem viés de até ~1,4 ms a 30 dB de SNR (a 20 dB aparecem erros maiores com nível 0,9 e contraste pequeno); o salto de fase tem desvio ~0,2 graus a 30 dB. Só a fase não separa "salto de fase" de "troca atrasada" (um salto J equivale a uma troca deslocada de J/(360 x \|f2-f1\|) s): se `fase_18` reprovar, olhe `intersecao_ms` (perto de 0 = a fase saltou; longe de 0 = a troca não ocorreu no meio da janela). Os limiares 10 graus e 2 ms são propostas (nenhum dado de bancada os embasa ainda). O carregamento da sessão está isolado em `carregar_sessao()` e `janela_da_captura()` (formato v1.15: `metadata\*.jsonl` + um `.npz` por captura); se o formato mudar, só essas duas funções mudam.

## 4. Achados que esperam diagnóstico na bancada
Ver a seção "NÃO VERIFICADO" de `arquivo/analises:docs/analise-2026-10-12/pendente/apresentabilidade_VERIFICAR.md` e `docs/quirks.md` (itens A3, A19, A22, A25, K4).
