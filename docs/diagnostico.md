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
| `scripts/verificar_sessao_bancada.py` | **não** (offline: só lê `resultados\sessao_*`) | — | `<pasta da sessão>` `[--tol-fase-graus 10] [--tol-largura-ms 2] [--tol-pretrigger-amostras 2] [--json arq]`; rodar logo depois da bancada (ver abaixo) |
| `logica/diag_digitizer_*.py` | — | — | removidos em 2026-10-13 (modo Digitizer, v1.10, descartado; histórico no git até `d3c7ce7`) |
| `preflight_new.py --list-diagnostics` | não | — | confirma comandos `SOURce:LIST:*` com write+leitura |

Cada diagnóstico que energiza desliga a saída no `finally` (inclusive Ctrl+C). Conferir OUTPUT OFF no painel ao final. Exceções de infraestrutura: seguir `docs/operacao.md` §7.

### 3.1 `verificar_sessao_bancada.py` (offline, depois da bancada)

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
Ver a seção "NÃO VERIFICADO" de `arquivo/analises:docs/analise-2026-10-12/pendente/apresentabilidade_VERIFICAR.md` e `docs/quirks.md` (itens A3, A19, A22, K4).
