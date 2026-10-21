# Rastreador P-01–P-31

Fonte única de **estado**. Narrativa e critérios completos: `execucao_pendencias.md`. Estado de máquina: `estado_prontidao.json` (manter coerente com esta tabela). Visita à bancada: `bancada_pendencias.md`. Decisões do responsável: `decisoes_pendentes.md`. Fechamento: `python scripts/fechar_pendencias.py --sessao <dir> ... --pc-bancada <json> --saida <json>`.

**Atualizado:** 2026-10-20 · branch `feat/execucao-pendencias-v1-15` · suíte offline 633 OK / 2 skips (macOS, Python 3.11.15, `/tmp/asd-exec-venv`).

## Placar

| Concluídas | Software pronto, falta bancada | Falta decisão/dado do responsável | Abertas |
|---|---|---|---|
| 9 | 17 | 5 | 0 |

## Protocolo para agentes (economia de contexto)

1. Leia **só** este arquivo e os arquivos citados na linha da sua pendência. Não leia `ROTEIRO_BANCADA.md`, `AGENTS.md` ou `execucao_pendencias.md` inteiros; use `grep -n` para a seção necessária.
2. Limites inegociáveis: `AGENTS.md` seção "Limites inegociáveis" (COM10/115200, limites RMS/pico/corrente, confirmação digitada para energizar, validações SCPI, `gerar()`/fixtures intocados).
3. Escopo de arquivos por frente (abaixo). Não editar arquivos de outra frente; este rastreador, `estado_prontidao.json`, `execucao_pendencias.md` e `CHANGELOG/v1.15.md` são editados **só pelo coordenador**. Agentes devolvem um trecho de CHANGELOG pronto no relatório.
4. Relatório final do agente: ≤25 linhas — arquivos alterados, comando de teste e resultado, P-NN afetados, o que NÃO foi verificado.
5. Nenhum agente encerra pendência física. Simulação ≠ medição.

## Frentes

| Frente | Escopo de arquivos | Pendências |
|---|---|---|
| **K** kit de bancada | `scripts/fechar_pendencias.py`, `scripts/validar_pc_bancada.ps1`, `tests/test_pendencias_fechamento.py` | ferramentas para P-01–P-08, P-10, P-16–P-19, P-21–P-23, P-28, P-31 |
| **R** roteiro de fechamento | `docs/bancada_pendencias.md` | sequência única de visita à bancada |
| **D** decisões e fontes | `docs/decisoes_pendentes.md` | P-09, P-18, P-20, P-23, P-26, P-29, P-30, P-31 |
| **C** coordenador | este arquivo, `estado_prontidao.json`, `execucao_pendencias.md`, CHANGELOG, commits | integração |

## Matriz

Estados: **✅** concluída · **🔧→🏭** software pronto, falta bancada · **❓** falta decisão/dado do responsável · **⏳** em andamento.

| ID | Estado | O que falta para fechar | Frente |
|---|---|---|---|
| P-01 | 🔧→🏭 | Campanha v1.15 real por classe/perfil/condição | K,R |
| P-02 | 🔧→🏭 | Marcadores + TRACe recuperada + recaptura 08/09 (evento 100 ms) | K,R |
| P-03 | 🔧→🏭 | Recaptura 08, 127 V/50 Hz, evento 90 ms: ≤10 amostras, pico ≤374,2 V | K,R |
| P-04 | ✅ | — (software) | — |
| P-05 | 🔧→🏭 | Fase/início/largura/pretrigger nas 01–04 com sorteio | K,R |
| P-06 | 🔧→🏭 | Bug de estado corrigido; falta continuidade de fase 47→53 Hz real | K,R |
| P-07 | 🔧→🏭 | Recalibrar 07/17 com medidas reais e validar na coleta seguinte | K,R |
| P-08 | 🔧→🏭 | Pico/vale 10/11/12/16 contra teto previsto, por condição | K,R |
| P-09 | ❓ | Perda quantificada (`evidencias/2026-10-16/modelo_programado.json`); responsável aprova "aceitar limite" | D |
| P-10 | 🔧→🏭 | RMS/THD da 05: CSIN 10/15/20%, norma 2%, TRACe 30% | K,R |
| P-11 | ✅ | — | — |
| P-12 | ✅ | — | — |
| P-13 | ✅ | — | — |
| P-14 | ✅ | — | — |
| P-15 | ✅ | — | — |
| P-16 | 🔧→🏭 | Suíte offline no PC Windows da bancada (log, SHA, versões) | K,R |
| P-17 | 🔧→🏭 | Diagnóstico ACDC (`scripts/diag_acdc_amplitude.py`) real | K,R |
| P-18 | 🔧→🏭 | SINE integrado OFF; validar aceitação LIST/restauração na fonte; responsável confirma padrão OFF | K,R,D |
| P-19 | 🔧→🏭 | `TRACe:DATA?` real: 1024 finitos ou não suportado | K,R |
| P-20 | ❓ | Licença, autoria, citação, tag/Zenodo — só o responsável decide | D |
| P-21 | 🔧→🏭 | Calibração por condição nova antes de coleta | K,R |
| P-22 | 🔧→🏭 | Benchmark com sessões físicas no PC/disco da bancada | K,R |
| P-23 | 🔧→🏭 | Orçamento 216/conexão aplicado; causa física da trava só com diagnóstico real | K,R |
| P-24 | ✅ | — | — |
| P-25 | ✅ | — | — |
| P-26 | ❓ | Responsável fixa perfis/frequências/tensões e decide ACDC 230 V | D |
| P-27 | ✅ | — | — |
| P-28 | 🔧→🏭 | Preservação do bruto implementada (`f974954`); falta exportação real + análise | K,R |
| P-29 | ❓ | Transcrições reais de sessões (logs locais do PC da bancada) | D |
| P-30 | ❓ | Sessões originais para reconciliar 99 (36+36+27) × 63 piloto | D |
| P-31 | 🔧→🏭 | Métricas offline publicadas; falta sessões novas + escolha da métrica oficial | K,R,D |

## Log de rodadas (uma linha por rodada, mais recente no topo)

- 2026-10-20 — C: integradas as frentes K (`fechar_pendencias.py`, `validar_pc_bancada.ps1`, 18 testes), R (`bancada_pendencias.md`) e D (`decisoes_pendentes.md`); 633 OK; Sphinx -W OK. **Próximo:** responsável preenche `decisoes_pendentes.md`; resolver as 4 contradições do roteiro (CHANGELOG v1.15, kit de fechamento); visita à bancada seguindo `bancada_pendencias.md`; rodar `fechar_pendencias.py` e atualizar esta matriz.
- 2026-10-20 — C: commit `f974954` (P-28 preservação do bruto); criado este rastreador.
- 2026-10-17 — Codex: 9 concluídas (P-04, P-11–P-15, P-24, P-25, P-27); suíte 574 OK; evidências em `evidencias/2026-10-17/`.
