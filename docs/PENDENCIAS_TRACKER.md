# Rastreador P-01–P-31

Fonte única de **estado**. Narrativa e critérios completos: `execucao_pendencias.md`. Estado de máquina: `estado_prontidao.json` (manter coerente com esta tabela). Visita à bancada: `bancada_pendencias.md`. Decisões do responsável: `decisoes_pendentes.md`. Fechamento: `python scripts/fechar_pendencias.py --sessao <dir> ... --pc-bancada <json> --saida <json>`.

**Atualizado:** 2026-10-22 · branch `feat/execucao-pendencias-v1-15` · suíte offline 759 OK / 0 skips no PC da bancada (`evidencias/2026-10-22/pc_bancada.json`).

## Placar

| Concluídas | Software pronto, falta bancada | Falta decisão/dado do responsável | Abertas |
|---|---|---|---|
| 13 | 11 | 7 | 0 |

## Protocolo para agentes (economia de contexto)

0. Entrada do mapa: `mapa/00 Início.md` (vault Obsidian; cartões de módulo, notas P-NN, `Pendencias.base`, `Mapa.canvas`). Após mudar estados aqui, rode `python scripts/gerar_mapa_pendencias.py`.
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
| P-02 | 🔧→🏭 | Reprovada em 2026-10-22 (`evidencias/2026-10-22/fechamento.json`): marcadores 30/30 sem espúrios, recapturas 08/09 a 50 e 60 Hz presentes, mas posição da 08 a 127 V/60 Hz desvia −16 amostras (limite 10) em uma captura por perfil (`sessao_2026-10-22_15-19-56`); hipótese da cópia de 100 ms sem critério definido | K,R |
| P-03 | ✅ | — (2026-10-22: 3/3 capturas a 127 V/50 Hz com evento 90 ms, desvio 2 amostras, pico 339 V ≤ 374,2 V, sobressinal 0,295 pu ≤ 0,55; `evidencias/2026-10-22/fechamento.json`) | — |
| P-04 | ✅ | — (software) | — |
| P-05 | ❓ | Evidência suficiente (2026-10-22), falta revisão humana: largura ≤ 1,1 ms (limite 2); pre-trigger determinístico até ±6 amostras (aviso, limite 2 nunca validado; ver `evidencias/2026-10-22/LEIA-ME.md`); critério de fase/início não definido | K,R,D |
| P-06 | 🔧→🏭 | Bug de estado corrigido; falta continuidade de fase 47→53 Hz real | K,R |
| P-07 | ❓ | Evidência suficiente (2026-10-22), falta revisão humana do diff e decisão: 07 1,186 → 1,615 e 17 1,031 → 1,575 (`022bb5c`, `a22fba9`); na Parte 6 a 07 rodou sem alerta de extremo; 17 recusada a 220 V | K,R,D |
| P-08 | 🔧→🏭 | Reprovada em 2026-10-22: extremos até 1,30× o previsto (12: 264 V contra 203,5 V), abaixo do teto. Recalibrado (`13b9bdb`); validar na próxima coleta e nas outras condições | K,R |
| P-09 | 🔧→🏭 | `diag_list_offset.py` real (2026-10-22): **sem suporte** a `SOURce:LIST:VOLTage:OFFSet` (`-113`), braço C não roda. Falta braço A (refazer, parado no alerta), braço B e análise A/B; depois aceitar a limitação com métricas (d) | K,R |
| P-10 | ✅ | — (2026-10-22: níveis 2/5/10/15/20/30 % com validação física ok; rota CSIN para 2–20 % e TRACe para 30 %; `evidencias/2026-10-22/fechamento.json`) | — |
| P-11 | ✅ | — | — |
| P-12 | ✅ | — | — |
| P-13 | ✅ | — | — |
| P-14 | ✅ | — | — |
| P-15 | ✅ | — | — |
| P-16 | ✅ | — (suíte 680/0 falhas/0 skips no PC da bancada DESKTOP-FSEESJI, `21fb300`; `evidencias/2026-10-21/pc_bancada.json`; repetida em 2026-10-22 com 759/0, `evidencias/2026-10-22/pc_bancada.json`) | — |
| P-17 | ❓ | Evidência suficiente (2026-10-22, 50 e 60 Hz, AC / ACDC offset 0 / ACDC com offset): falta decidir se o déficit em ACDC é aceitável (critério não definido) | K,R,D |
| P-18 | 🔧→🏭 | SINE integrado OFF; validar aceitação LIST/restauração na fonte; responsável confirma padrão OFF | K,R,D |
| P-19 | 🔧→🏭 | 2026-10-22: `TRACe:DATA? TCC00` devolve 10 valores (9 leituras, classes 08/09), nem 1024 finitos nem erro de comando não suportado: investigar o formato da resposta | K,R |
| P-20 | ❓ | Aguarda o Denis: licença, autoria, citação, tag/Zenodo | D |
| P-21 | 🔧→🏭 | Calibrar 220 V/60 Hz e 33 V/60 Hz antes da coleta científica. 50 Hz: calibração pela campanha de 127 V antes da de 230 V (`aac725b`). 220 V/60 Hz: decisão sobre a regra de condição sem tabela (`evidencias/2026-10-22/LEIA-ME.md`) | K,R,D |
| P-22 | ❓ | Evidência suficiente (2026-10-22: 14 sessões físicas lidas sem erro no DESKTOP-FSEESJI, benchmark com hashes iguais): falta definir tempo/tamanho aceitáveis | K,R,D |
| P-23 | 🔧→🏭 | Orçamento 216/conexão aplicado; causa física da trava só com diagnóstico real | K,R |
| P-24 | ✅ | — | — |
| P-25 | ✅ | — | — |
| P-26 | 🔧→🏭 | Decidida em 21/10: 5 condições, `set perfil todos`, 1 captura/classe, sem ACDC a 230 V. Fecha quando as sessões registrarem essa configuração | K,R |
| P-27 | ✅ | — | — |
| P-28 | ❓ | Evidência suficiente (2026-10-22: 135 exportações brutas íntegras, reamostragem casada por SHA-256): falta decidir se o FIR substitui o interpolador | K,R,D |
| P-29 | 🔧→🏭 | Decisão B (21/10): logs antigos indisponíveis; usar `scpi_transcricao.log` das sessões novas, com revisão de dados sensíveis | R,D |
| P-30 | ✅ | — (retificação: 63/99 históricos não verificáveis; `tres_versoes.md`, `AGENTS.md`) | — |
| P-31 | ❓ | Evidência suficiente (2026-10-22: capturas físicas das 06/10/11/12/15/16 com três versões, correlações publicadas): falta escolher a métrica oficial | K,R,D |

## Log de rodadas (uma linha por rodada, mais recente no topo)

- 2026-10-22 — Visita à bancada (Inspiron, COM10): Blocos 1–9 e 8-A completos a 127 V/60 Hz, parada no braço A da P-09. Fechamento parcial (`evidencias/2026-10-22/fechamento.json`): **P-03 e P-10 concluídas**; P-05, P-07, P-17, P-22, P-28 e P-31 com evidência suficiente aguardando revisão; P-02 e P-08 reprovadas; P-09 sem suporte a offset por passo. Correções: recalibração 127 V/60 Hz, forma volta à senoide depois de classe waveform (THD de 18/19), visita (P-09, Bloco 7, 50 Hz). 759 OK.

- 2026-10-21 — Visita num comando: `scripts\VISITA_BANCADA.cmd` conduz os Blocos 1–10, 8-A, 10-A, 10-B, as cinco condições da P-26 (com calibração P-21 de 220/33 V) e o fechamento; CLI ganhou modo roteiro (`--comando`), as confirmações seguem com o operador. 754 OK.

- 2026-10-21 — Pedido do responsável: capacidades da MX30 conferidas antes de I/O (LIST ≤32, TRACe ≤50, dwell, PULSe, offset), captura que excede é pulada e a bateria segue; orçamento esgotado desliga e registra; `falhas.json`; `run falhas` / `rerun`. Revisão Opus OK; 726 OK no Mac e no Inspiron (`suite.ps1`, EXIT=0, sem instrumentos).

- 2026-10-21 — P-09: experimento A/B/C (braço A byte a byte idêntico; B = AC+DC; C = offset por passo, com consulta de suporte e recusa sem fallback; métricas modelo→programada no metadata); revisão Opus sem violação de limites, 3 achados corrigidos; 704 OK. Bloco 10-B no roteiro.

- 2026-10-21 — **P-30 concluída** (decisão D: contagens históricas não verificáveis). P-09: implementação do experimento A/B/C (OFF por padrão) em andamento.

- 2026-10-21 — P-29: decisão B (logs novos). P-20: aguarda Denis. P-09: alternativas pesquisadas (manual p. 96/126); plano (d)+(b)-simulado+consulta na bancada. P-30: proposta D aguardando confirmação.

- 2026-10-21 — P-26 decidida (todos, padrão, ACDC só a 127 V); passa a aguardar só a conferência nas sessões. Roteiro atualizado.

- 2026-10-21 — P-26 parcial: responsável fixou as cinco condições. Plano offline (`evidencias/2026-10-21/plano_campanhas_5_condicoes.json`): 230/50 com 13 recusas (swells), 220/60 sem calibração e 52 recusas, 33/60 sem calibração. `bancada_pendencias.md` ganhou "Campanhas por condição".

- 2026-10-21 — Mapa Obsidian (skills oficiais kepano/obsidian-skills `3ccff53`): `mapa/` com 31 notas P-NN geradas por Knap, 15 cartões de módulo (dependências do grafo real de imports), 6 hubs de domínio, `Pendencias.base`, `Mapa.canvas`; `CLAUDE.md` na raiz aponta para o mapa.

- 2026-10-21 — Inspiron 15 (DESKTOP-FSEESJI) definido como PC da bancada e preparado (Python 3.11.9, env validado, NI-VISA, energia/USB, atalho START_BENCH). **P-16 concluída** (8/8 critérios do agregador). Drivers: NI-VISA 26.5 (passaportes USB e serial; PyVISA usa `visa32.dll`) e driver USB da AMETEK (TUSB3410, `usbuart3410.inf` 6.7.2.0, WHQL, do download oficial "USB VCP Driver" da página MX; cópia em `C:\drivers_bancada\ametek_vcp`). Falta: ligar os instrumentos, ajustar a porta da AMETEK para COM10 e conferir `*IDN?` dos dois sem energizar.

- 2026-10-21 — Software das P-03 (sobressinal gravado), P-10 (rota + sequência Bloco 8-A), P-22/P-31 (ferramentas sobre sessões reais) e roteiro sem contradições; revisão Opus sem achado alto; 680 OK. Inspiron 15 (DESKTOP-FSEESJI) preparado: Python 3.11.9, env com versões validadas, NI-VISA. Restante destas quatro: só bancada.

- 2026-10-20 — Revisão independente (Opus) do trabalho do Codex e desta sessão: sem violação dos limites; P-04, P-11–P-15 confirmadas no código. 17 achados corrigidos (ver CHANGELOG "Correções da revisão independente"); 650 OK. Lacunas abertas: campo de sobressinal na coleta (P-03), hostname no benchmark (P-22), `TRACe:DEFine` no orçamento (P-23, decisão).

- 2026-10-20 — C: integradas as frentes K (`fechar_pendencias.py`, `validar_pc_bancada.ps1`, 18 testes), R (`bancada_pendencias.md`) e D (`decisoes_pendentes.md`); 633 OK; Sphinx -W OK. **Próximo:** responsável preenche `decisoes_pendentes.md`; resolver as 4 contradições do roteiro (CHANGELOG v1.15, kit de fechamento); visita à bancada seguindo `bancada_pendencias.md`; rodar `fechar_pendencias.py` e atualizar esta matriz.
- 2026-10-20 — C: commit `f974954` (P-28 preservação do bruto); criado este rastreador.
- 2026-10-17 — Codex: 9 concluídas (P-04, P-11–P-15, P-24, P-25, P-27); suíte 574 OK; evidências em `evidencias/2026-10-17/`.
