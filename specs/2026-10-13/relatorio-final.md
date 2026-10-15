# Relatório da rodada 13–15/10/2026

## Resumo
17 specs executadas (10–26, incluindo a 24, extra, e as 25 e 26, pedidas no meio da rodada), todas mescladas em `claude/specs-v1-15-review-3w2bgl` (último merge `ca64d09`). 7 sem pendências, 10 com pendências (quase todas são verificação na bancada ou decisões menores). Nenhuma pulada ou bloqueada. Suíte offline no Linux: 497 testes, OK, 2 pulados (SHA-256 exatos, só no Windows).

## Ordem de execução
Onda 1: 11, 12, 10 · Onda 2: 13, 14, 21 · Onda 3: 15, 20, 19 · Onda 4: 17, 18, 16 · extra: 24 · pausa a pedido do usuário (25 e 26 interrompidas, retomadas em 15/10) · Onda 5: 25, 26 · Onda 6: 22, 23. Primeira: 11/12/10. Última: 22. Máx. 3 executores em paralelo, cada um num worktree; mescla pelo orquestrador.

## Specs
| pri | Título | Executor | Estado | Critério de Parada | Relatório |
|---|---|---|---|---|---|
| 10 | Análises fora de docs e arquivo em branch separado | haiku | feito | atendido | sem-pendencias/10-analises-fora-de-docs.md |
| 11 | RMS por ciclo da TRACE sem a média e pico previsto | sonnet | feito | atendido | sem-pendencias/11-rms-por-ciclo-trace.md |
| 12 | Preflight único na tensão base com ENERGIZAR-TESTE | sonnet | feito | atendido | sem-pendencias/12-preflight-unico.md |
| 13 | Run com lista e intervalos | haiku | feito | atendido | sem-pendencias/13-run-com-lista.md |
| 14 | Semente do ruído e árvore suja | haiku | feito | atendido | sem-pendencias/14-rastreabilidade-ruido-git.md |
| 15 | Diagnóstico da cópia em 100 ms (08/09) | sonnet | parcial (bancada) | atendido | com-pendencias/15-diag-copia-100ms.md |
| 16 | set diagnostico retrieve (TRACe:DATA?) | sonnet | parcial (bancada) | atendido | com-pendencias/16-diagnostico-retrieve.md |
| 17 | Um npz comprimido por classe | sonnet | parcial (decisões) | atendido | com-pendencias/17-npz-por-classe.md |
| 18 | Pendentes da correlação (05, 09, 06, métrica) | sonnet | parcial (decisões) | atendido | com-pendencias/18-pendentes-correlacao.md |
| 19 | Revisão das compostas | sonnet | parcial (decisão) | atendido | com-pendencias/19-revisao-compostas.md |
| 20 | Pendentes conferíveis offline | sonnet | parcial (bancada) | atendido | com-pendencias/20-pendentes-offline.md |
| 21 | Fixtures portáveis | sonnet | parcial (Windows) | atendido | com-pendencias/21-fixtures-portaveis.md |
| 22 | Documentação autocontida | haiku | parcial (decisões menores) | atendido | com-pendencias/22-docs-autocontidas.md |
| 23 | Roteiro da próxima bancada | sonnet | parcial (escolhas do dia) | atendido | com-pendencias/23-roteiro-bancada.md |
| 24 | Scripts de diagnóstico via sessao_io (extra) | haiku | feito | atendido | sem-pendencias/24-scripts-sessao-io.md |
| 25 | set perfil todos sem recapturas | sonnet | feito | atendido | sem-pendencias/25-perfil-todos-sem-repeticao.md |
| 26 | Crista com o fator calibrado | sonnet | parcial (bancada) | atendido | com-pendencias/26-crista-com-fator-calibrado.md |

## Achados por spec
### 11
- [ ] (alta, segurança) A previsão de pico subestimava até 38 % em ciclos com degrau a meio ciclo; corrigida. Conferir VMAX/VMIN das classes 10/11/12/16 na 1.ª sessão.
- [ ] (média) Resta a média de cada ciclo (0,24–0,33 pu nas 10/11/12/16): a fonte a remove; só compensável com offset por passo (ACDC).
### 15
- [ ] (alta) Mecanismo da cópia em 100 ms continua NÃO VERIFICADO; ferramentas prontas (`diag_ciclos_trace.py`, `diag_marcadores_trace.py`, `modelo_lista_fonte.py`).
- [ ] (média) `program_capture` só avisa quando o pico passa de `max_peak_v`; a recusa fica na pré-validação de `mestre` e no script novo. Avaliar recusar no ORM (endurece).
### 16
- [ ] (média) O manual se contradiz sobre `TRACe:DATA?`; primeiro uso na 1.ª captura da 08, painel à vista.
### 17
- [ ] (média) Quebra de formato dos `.npz` em sessões novas (aviso no CHANGELOG); `recuperar_parcial` é manual.
### 18
- [ ] (média) 06 perde correlação pela média de cada ciclo; decidir: comparar contra a programada ou mudar `gerar()`.
- [ ] (média) 09: com sorteio, 100 ms cai no evento em só 17–18 % das capturas; critério de aceite proposto no roteiro.
### 19
- [ ] (baixa) Extensões das compostas além do texto da proposta (sag em 11/12, swell em 13/14, faixas da norma, fronteira alternada, THD em 13/15/16).
- [ ] (baixa) 15 não tem gancho de redução de bancada.
### 20
- [ ] (alta) 07/17 com entalhes em todos os ciclos seriam reprovadas pela crista — tratado pela 26.
- [ ] (baixa) limiares do `verificar_sessao_bancada.py` são propostas sem dado.
### 21
- [ ] (média) Rodar `tests.test_offline` no Windows (resumos portáveis gravados no Linux; SHA-256 exatos só lá).
### 22
- [ ] (baixa) `dono` → `pai` em variável local de `mestre.py`; texto mudou em `calibracao_extremos.json` (SHA-256 novo); "spec NN" ficou no texto; "dono" mantido no `AGENTS.md`.
- [ ] (média) O HTML do fim do run mostra só 3 capturas por classe e perfil por padrão.
### 23
- [ ] (baixa) `set capturas` é piso (max com o padrão da classe): não há captura TRACe isolada.
- [ ] (baixa) `docs/operacao.md` §7 diz "até 3 tentativas" por classe; conferir contra o AGENTS.md (vale para erro não determinístico, não infraestrutura).
### 26
- [ ] (alta, bancada) A 127 V/60 Hz os fatores calibrados da 07 (1,186) e da 17 (1,031) não cobrem o toque simulado (~1,34–1,42): 1.ª rodada sai inválida; recalibrar e repetir (no roteiro).
- [ ] (baixa) Em condição sem tabela (fator 1,475) o teto da crista afrouxa para ~1,62×.

## Decisões pendentes do usuário
- [ ] Extensões das compostas: manter ou reverter (19).
- [ ] 06: comparar contra a programada ou mudar `gerar()` (18).
- [ ] Compensar a média por ciclo (offset por passo/ACDC) nas 10/11/12/16 (11).
- [ ] `run 01 02` (sem vírgula) roda só a 01; `BATERIA_EXCLUIR` não vale para listas (13).
- [ ] `recuperar_parcial` automático no início do run (17).
- [ ] HTML do fim do run: mostrar todas as capturas ou manter 3 (22).
- [ ] Itens menores da 22 (`pai`, JSON, "spec NN").
- [ ] No dia da bancada: perfil único ou `todos`, frequência da campanha, ACDC a 230 V (23).

## Premissas assumidas
- Análises novas passam a ser registradas no branch `arquivo/analises` (mesmo caminho `docs/analise-AAAA-MM-DD/`).
- A 26 vale para todas as classes; a 08 usa fator 1,0 (impulso já fora da crista).
- Com `set perfil todos`, as classes independentes do perfil são capturadas em `literatura` e espelhadas no metadata dos outros perfis.
- Roteiro sem data fixa (`ROTEIRO_BANCADA.md`), porque a bancada de 14/10 não ocorreu com este código.

## Parecer do orquestrador
O ganho mais importante da rodada foi de segurança e fidelidade, não de funcionalidade: o rms por ciclo da TRACE (11) corrigiu uma previsão de pico que subestimava o que a fonte emite. O segundo foi ter achado, antes da bancada, que a mudança de ontem na 07/17 colidia com a validação da crista; a solução (26) liga a validação à calibração, como deveria ser. As specs de diagnóstico (15, 16, 20) só rendem com a bancada: o mecanismo da cópia em 100 ms continua em aberto e é o maior risco de dado ruim (08/09). O NPZ por classe (17, 25) foi a maior mudança e a mais arriscada de mesclar; a suíte cobre o caminho simulado, não a bancada real. A paralelização em worktrees custou mesclas manuais (CHANGELOG e testes, e dois conflitos de código), sem perda.

## Sugestões
- Recusar no ORM a programação de TRACe com pico acima de `max_peak_v` (hoje só avisa).
- Medir na 1.ª sessão o tamanho e o tempo de reescrita do NPZ por classe com medida física.
- Gancho de redução de bancada para a classe 15.
- Depois da bancada: decidir o mecanismo da cópia em 100 ms com os marcadores e, se for previsível, modelá-lo na forma programada.
