# Histórico das versões

```{include} /_includes/aviso-base.md
```


```{toctree}
:maxdepth: 1

historico/v1-0
historico/v1-1
historico/v1-2
historico/v1-3
historico/v1-4
historico/v1-5
historico/v1-6
historico/v1-7
historico/v1-8
historico/v1-9
historico/v1-10
historico/v1-11
historico/v1-12
historico/v1-13
historico/v1-14
historico/v1-15
```

(analises-arquivadas)=
## Rodada de análise de 13 a 15/10/2026 (análises arquivadas)

{bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` (rodada de 13 a 15/10/2026 sem bancada)

**Pergunta:** o que a última rodada de análise concluiu e o que ficou em aberto? **Resposta:** a rodada de **13 a 15/10/2026** executou 17 tarefas de código e de documentação (numeradas 10 a 26), todas integradas na `main` (`fa82f49`), com a suíte offline passando (497 testes), mas **nada foi validado na bancada**: tudo o que depende da fonte e do osciloscópio está marcado "a confirmar", e a última campanha de bancada continua sendo a de 07/10/2026 (P-01).

As rodadas anteriores (21/09, 30/09 e 12/10/2026) já foram revisadas e não são reabertas aqui; os achados duráveis delas estão nas quirks ({doc}`quirks`: A1, A2, A13, K1 e outras) e nas versões v1.11 a v1.15 listadas acima. Os relatórios datados ficam no branch `arquivo/analises` (fora de `docs/` desde 13/10/2026) e **não** se reescrevem. Fontes desta página: `github/arquivo/analises:sessao-13-10-2026/{ESTADO.md,relatorio-final.md,docs/roteiro-bancada.md,wip/}` e `:specs/2026-10-13/relatorios-individuais/` (commit `3ba499c` do branch), mais `CHANGELOG/v1.15.md`.

:::{caution} Limitação
**A análise de 13 a 15/10 não foi validada na bancada.** Perfis, sorteio de início, duração e fase, compostas sorteadas, entalhes contínuos, a 08 a 90 ms, a crista com fator, o leitor de um `.npz` por classe e a leitura de volta das TRACes existem no código e passam nos testes offline, mas nenhuma sessão física os exerceu. O estado de cada classe está em {doc}`projeto/estado-validacao`; o que falta, em {doc}`projeto/pendencias`.
:::

### 1. O que cada tarefa concluiu

| Tarefa | Tema | Conclusão | O que ficou aberto |
|---|---|---|---|
| 10 | Análises fora de `docs/` | relatórios datados, planos antigos e scripts temporários foram para o branch `arquivo/analises`; `docs/` ficou só com a documentação do projeto e os manuais | nada |
| 11 | RMS por ciclo da TRACe sem a média e previsão de pico | `LIST:VOLTage` passou a levar o rms **CA** do ciclo e o pico previsto é calculado sobre a forma realmente enviada; antes o pico previsto podia ficar **até 38 % abaixo** do real em ciclos com degrau (10, 11, 12, 16), e a forma emitida diferia do modelo em até 0,43 pu | a fonte continua removendo a média de cada ciclo (erro programada × modelo de 0,24 a 0,33 pu): P-09; conferir `pico_medido_v` das 10, 11, 12, 16 na 1.ª sessão: P-08 |
| 12 | Preflight único | `preflight.py` foi removido; `lowvoltage` sempre rodou na tensão digitada (127 V) apesar do rótulo "5 V"; agora a confirmação é `ENERGIZAR-TESTE` e mostra a tensão real; `comm`, `trigger`, `lowvoltage` e `native` gravam `logs\preflight_new-*.log` | nada |
| 13 | `run` com lista de classes | `run 01-07,09-20` com a confirmação `EXECUTAR-CLASSES-01-07,09-20`, para dividir a bateria abaixo da trava de cerca de 280 gravações de TRACe por conexão | `run 01 02` (com espaço) roda só a 01; `BATERIA_EXCLUIR` não vale para listas: P-14 |
| 14 | Rastreabilidade | o metadata grava a semente do ruído e a fórmula; `git_sujo` passou a contar arquivo novo e é recalculado a cada pasta de sessão; `sessao.json` grava o perfil | `docs/quirks.md` B8 ainda descreve o comportamento antigo (P-24) |
| 15 | Cópia do evento em 100 ms (08 e 09) | três ferramentas: `diag/diag_ciclos_trace.py` (offline), `diag/diag_marcadores_trace.py` (bancada, `ENERGIZAR-MARCADORES`) e `logica/modelo_lista_fonte.py` (hipóteses); cinco hipóteses, nenhuma confirmada; com o início sorteado, 100 ms cai dentro do evento da 09 em só 17 a 18 % das capturas | mecanismo: P-02 (Blocos 4 e 6 do roteiro) |
| 16 | `set diagnostico retrieve` | lê de volta as TRACes (`TRACe:DATA? <nome>`) com a captura já terminada e 2 s depois da última gravação; salva enviado × lido em `diagnostico_trace/` | o manual se contradiz; só a bancada diz se funciona: P-19 |
| 17 | Um `.npz` por classe | `NN_classe.npz` comprimido, com as três versões de cada perfil; `sessao_io.py` lê os dois formatos; os níveis de ruído ficam em arquivos à parte | quebra de formato nas sessões novas; `recuperar_parcial` é manual (P-13); tamanho com dado real não medido (P-22) |
| 18 | Pendentes da correlação | 05: o modelo até 20 % já é a senoide clipada e no nível de 30 % modelo e programada são idênticos; nova métrica com a fundamental ajustada; a perda da 06 vem inteira da média de cada ciclo | decisão sobre a 06: P-12; qual métrica publicar: P-31; ver {doc}`medicao/correlacao` |
| 19 | Compostas sorteadas contra a proposta | as extensões (sag em 11 e 12, swell em 13 e 14, THD em 13, 15 e 16, faixas da `norma`, `fronteira` alternada) vão além da proposta, sem defeito; a 2400 Hz a oscilação sai 2,4 % menor na programada | manter ou reverter: P-11; a 15 não tem `parametros_com_disturbio_reduzido` |
| 20 | Pendentes conferíveis offline (ACDC, 18, sorteio) | `scripts/verificar_sessao_bancada.py` mede a continuidade de fase da 18, a largura do PULSe e o desvio do pré-trigger numa sessão gravada; limiares de 10°, 2 ms e 2 amostras são propostas, sem dado de bancada | P-05, P-06, P-17 |
| 21 | Fixtures portáveis | o hash exato do `gerar()` difere entre Windows e Linux no último bit do seno (2·10⁻¹⁶); comparação por tolerância de 1e-9, e o hash exato continua só no Windows | rodar `tests.test_offline` no PC da bancada: P-16 |
| 22 | Documentação autocontida | seção única sobre HTML e recalibração em `docs/operacao.md` §9; autorizações que faltavam em `AGENTS.md` | decisões menores: P-25; HTML mostra todas as capturas numa sessão de bancada em formato 2: P-15 |
| 23 | Roteiro da bancada | `docs/roteiro-bancada.md` (10 blocos, de 2 h a 3 h com um perfil) | nenhum bloco executado: P-01, P-26; ver {doc}`roteiro-bancada` |
| 24 | Scripts e `sessao_io` | os scripts de diagnóstico foram adaptados ao leitor único | nada |
| 25 | `set perfil todos` sem repetir | classes que não dependem do perfil (com sorteio ligado: 01, 04, 07, 08, 09, 17, 18, 19) são capturadas uma vez, sob `literatura`; o metadata dos três perfis aponta para a mesma captura; com `todos`, `run all` planeja 1116 gravações de TRACe a 60 Hz (1404 sem a deduplicação; 468 com um perfil) | acima da trava de ~280 por conexão: P-23 |
| 26 | Crista com fator calibrado | a validação da crista usa a calibração de extremos (`fator_crista`): aceita de `crista × 0,9` até `crista × fator × 1,1`; decisão de usar a calibração em vez de afrouxar a tolerância | os fatores de 07 e 17 a 127 V/60 Hz (1,186 e 1,031) não cobrem o toque simulado (≥ 1,344 e ≥ 1,420): a 1.ª rodada deve reprovar; ver {doc}`medicao/recalibracao`: P-07 |

Duas tarefas tinham ficado interrompidas em 13/10 (25 e 26) e foram concluídas em 15/10 a partir de patches guardados em `sessao-13-10-2026/wip/`.

### 2. Decisões que a rodada deixou para o responsável

O relatório final reúne oito decisões; todas entram em {doc}`projeto/pendencias` com id:

| Decisão do relatório | Id |
|---|---|
| investigar a média por ciclo via ACDC depois da bancada | P-09 |
| a gravação de TRACe recusar pico acima do limite (hoje só avisa) | P-04 |
| `recuperar_parcial` automático no início do `run` | P-13 |
| `run 01 02` recusar; `BATERIA_EXCLUIR` fora das listas | P-14 |
| classe 06: comparar com a programada ou mudar `gerar()` | P-12 |
| compostas: manter ou reverter as extensões | P-11 |
| detalhes da documentação autocontida e o HTML com todas as capturas | P-25, P-15 |
| no dia da bancada: um perfil ou `todos`, frequência da campanha, ACDC a 230 V | P-26 |

### 3. O que a rodada não resolveu e o que mudou desde o relatório

- **Contagem de testes.** O estado da rodada (`ESTADO.md`) fala em 480 testes com 2 pulados; o relatório final, em 497 com 2 pulados (Linux). Em 2026-10-15, no Windows 11 (Python 3.11.9), a suíte deu `Ran 497 tests in 93.003s`, `OK`, **sem testes pulados** (P-16, parcialmente resolvida); em 2026-10-16 foi repetida para esta documentação (resultado em {doc}`projeto/estado-validacao`).
- **Rodada seguinte.** O branch `feat/passo-final-sin` ({ref}`passo-final-sin`) é anterior a esta rodada e continua fora da `main`.
- **O que não foi auditado aqui.** Os relatórios individuais foram lidos para esta página só até o nível de conclusão por tarefa; a leitura de cada um, linha a linha, não foi refeita.

(execucao-pendencias)=
## Execução das pendências P-01 a P-31 (17 a 22/10/2026)

Registro de trabalho de 17 a 22/10/2026, migrado para esta página em 2026-10-27 (a página de execução das pendências foi removida); é histórico datado, os estados citados valem na data de cada linha. O estado vigente está em {doc}`projeto/pendencias`.

Fonte do inventário: {doc}`projeto/pendencias`. A autorização do usuário nesta sessão determina implementar plenamente as pendências como atualização das escolhas anteriores. Não se interpreta um contrato antigo de teste como impedimento à atualização: P-14 passa a aplicar exclusões às listas, e P-15 passa a limitar o HTML também na bancada. Resultados de testes antigos devem ser atualizados para o novo contrato e acompanhados de regressões independentes.

O fork `rmlinxic/anti-synthetic-data`, com parent `DenisLN/anti-synthetic-data`, foi confirmado pela API. A baseline teve 497 testes aprovados. A integração do código em `58130af2e58b914e17b5e15615bdc655f905ca3f` executou **574 testes em 63,686 s: OK, com dois hashes específicos de Windows pulados no macOS**. Ambiente: Python 3.11.15/numpy 2.4.6; assinaturas portáveis executadas. A evidência e o log completos estão em `docs/evidencias/2026-10-17/`. Isso não equivale à execução no PC da bancada nem a uma validação física.

As mudanças funcionais estão implementadas e verificadas na suíte integrada. A P-13 inclui exclusão entre processos, recuperação após morte abrupta, fechamento explícito dos escritores e pastas exclusivas para CLIs iniciadas no mesmo segundo. Sessões legadas sem marcador de lock exigem recuperação explícita offline; a recuperação automática não pressupõe que qualquer pasta parcial esteja abandonada.

### Registro de rodadas (uma linha por rodada, mais recente no topo)

Migrado do antigo rastreador de pendências em 2026-10-27. É histórico datado: os estados citados valem na data de cada linha, não hoje.

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

### Ferramentas e evidências offline entregues

Os arquivos em `docs/evidencias/2026-10-16/` são resultados reprodutíveis de software. Não são capturas físicas e não encerram as partes de bancada. Não regenerar por cima dos resultados: os scripts recusam sobrescrita de JSON; use outro destino para uma repetição.

```powershell
.\env\Scripts\python.exe diag\analisar_modelo_programado.py --saida modelo_programado_novo.json
.\env\Scripts\python.exe diag\analisar_reamostragem.py --sintetico --saida reamostragem_nova.json
.\env\Scripts\python.exe diag\benchmark_sessao_io.py --capturas 3 10 30 --saida benchmark_novo.json
```

- `docs/evidencias/2026-10-16/modelo_programado.json`: seis classes, três perfis, 50/60 Hz e três seeds; representação TRACe/LIST comparada ao modelo, perda da média por ciclo e correlações nominal/ajustada. Sem hardware, calibração ou redução de bancada.
- `docs/evidencias/2026-10-16/reamostragem_sintetica.json`: comparação sintética entre interpolação linear e FIR anti-aliasing; não é avaliação do bruto do osciloscópio real.
- `docs/evidencias/2026-10-16/benchmark_sintetico.json`: writer real com dados sintéticos, integridade de leitura e aliases; diretório temporário/cache, sem `fsync`, e `tracemalloc` não equivale a RSS.
- `docs/evidencias/2026-10-16/limites_50hz.md` e `limites_60hz.md`: relatórios offline de limites, não medições.
- `docs/evidencias/2026-10-16/plano_campanhas.json`: planejamento offline por condição; não registra campanha executada.

A documentação de referência importada usa permalinks do snapshot `fa82f49600543456adf78e22485ab6de5dd032b9` para citações históricas de linhas. Os 25 `literalinclude` selecionam objetos por símbolo, verificados por AST contra o checkout atual; não dependem de números de linha. As alterações atuais de contrato estão identificadas nas páginas CLI/ORM/persistência/HTML/SINE, além desta matriz.
