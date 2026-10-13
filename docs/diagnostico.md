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
| `logica/diag_digitizer_*.py` | — | — | removidos em 2026-10-13 (modo Digitizer, v1.10, descartado; histórico no git até `d3c7ce7`) |
| `preflight_new.py --list-diagnostics` | não | — | confirma comandos `SOURce:LIST:*` com write+leitura |

Cada diagnóstico que energiza desliga a saída no `finally` (inclusive Ctrl+C). Conferir OUTPUT OFF no painel ao final. Exceções de infraestrutura: seguir `docs/operacao.md` §7.

## 4. Achados que esperam diagnóstico na bancada
Ver a seção "NÃO VERIFICADO" de `arquivo/analises:docs/analise-2026-10-12/pendente/apresentabilidade_VERIFICAR.md` e `docs/quirks.md` (itens A3, A19, A22, K4).
