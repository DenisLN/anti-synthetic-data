## Análise do orquestrador

- Implementação completa? Sim: 05 conferida (30 % sem mudança, justificado), correlacao_disturbio_fundamental_ajustada em sinais/analisar_sessao/HTML, 09 coberta pelas ferramentas da 15, perda da 06 quantificada; merge ok.
- Pendências do usuário: recomendação da 09 para amanhã (6–9 capturas, critério 0,05 pu) — vai ao roteiro; 06 fiel à fonte exigiria autorizar mudança de gerar() (flicker com média nula por ciclo) ou comparar contra a programada.
- Escopo limitado demais? Não.
- Resolve o contexto? Sim.
- Critério de Parada: atendido.
- Classificação: com pendências (decisões).

---

# Relatório: ASD: Pendentes da Correlação do Distúrbio (05, 09, 06 e Métrica)

Branch: `worktree-agent-a61f061def7218007`. Commits: `510f77a` (feat: métrica + testes), `dd01e22` (docs + CHANGELOG). Merge prévio de `claude/specs-v1-15-review-3w2bgl` já presente (HEAD anterior `67840e9`). Suíte: 435 testes, OK (2 pulados); linha de base antes: 424, OK.

## Missão, item a item

**Item 1 — Conferir a 05 contra o diagnóstico (THD, rms, fase, teto) com testes; decidir e implementar a coerência do nível de 30 % entre modelo e programada (modelo normalizado ao rms que a fonte emite, ou documentar por que não), sem mexer no que `gerar()` produz para o sorteio desligado.**
- Status: CUMPRIDO
- Explicação: a 05 (`experimentos_nativos/05.py:48-51`, `sinais.senoide_clipada_pu` em `sinais.py:598`) confere com o diagnóstico: THD do ciclo = pedido (0,0200 a 0,3000), rms 0,7071 nos níveis CSINe (normalização por rms presente; sem ela a fundamental sairia ~5 % menor a 5 %), fase igual à de `forma_programada_nativa` (`tau = fase_graus/(360 f0)`), teto de 20 % respeitado nos 3 perfis (`corte_da_senoide_clipada(0.30)` levanta). Tabela completa no CHANGELOG. Nível de 30 % por TRACE: o modelo tem fundamental 1 pu e rms 0,7382 (= sqrt((1+0,09)/2)); `montar_programacao` põe no `LIST:VOLTage` o rms CA do próprio ciclo do modelo, então a fonte emite exatamente o rms do modelo: programada × modelo corr. do distúrbio 1,00000, diferença máxima 1,1e-4 pu (50 e 60 Hz); `LIST:VOLTage` = 1,044 × base, pico 148,2 V a 127 V. A incoerência de rms é ENTRE níveis (0,738 vs 0,707), não entre modelo e programada. Decisão: não mudar `gerar()` (normalizar a 1/√2 baixaria a fundamental a 0,958 pu, corr. modelo×normalizado 0,989, sem ganho). Portanto fixtures não regravadas (permitido pelo Limite: "só se o item 1 concluir que é necessário"). Testes: `PendentesCorrelacaoDisturbioTests` (4 testes de 05) em `tests/test_offline.py` (fim do arquivo).

**Item 2 — Implementar `correlacao_disturbio_fundamental_ajustada` (ajuste de amplitude e fase da fundamental em cada sinal antes do resíduo) e expô-la em `analisar_sessao.py` e no HTML ao lado da métrica atual, com caso degenerado tratado como na métrica atual.**
- Status: CUMPRIDO
- Explicação: `sinais.py:520` (+ helper `_residuo_sem_fundamental`, `:509`): mínimos quadrados `a sin + b cos + c` em f0 em cada sinal, Pearson dos resíduos; mesmos limiares degenerados (1e-6), `(None, motivo)` para 01, 19, capturado sem distúrbio, formas incompatíveis. `analisar_sessao.py`: argumento `fundamental_ajustada` em `_correlacao_disturbio_alinhada` (`:188-210`), chaves `correlacao_disturbio_fundamental_ajustada[_motivo]` (`:319`), coluna `corr. dist. fund.aj.` (`:344-350`). `relatorio_html.py`: `_correlacoes` (`:241`) e linha "distúrbio com a fundamental ajustada X" em `tabela_metadados`. Mudanças pequenas; carregamento de `.npz` não tocado. Testes: fundamental 1 % maior (09 sorteada, 50 e 60 Hz) dá ajustada > 0,9999 e nominal < 0,99; ganho 1 % e fase 1 grau também; degenerados; ponta a ponta em `analisar_sessao` (stdout inclui "fund.aj." e 1.000) e em `relatorio_html`.

**Item 3 — Incluir a 09 no diagnóstico da cópia em 100 ms (confirmar com teste sintético que as ferramentas da spec 15 rodam numa 09 sorteada e acusam a cópia) e escrever no relatório a recomendação para a campanha de amanhã (rodar a 09 ou não, e em que condição), para o roteiro.**
- Status: CUMPRIDO
- Explicação: teste `test_ferramentas_da_copia_em_100ms_rodam_numa_09_sorteada_e_acusam_a_copia` (50/60 Hz, 2 sementes): `reconstruir_versoes` + `diag_ciclos_trace.carregar_sessao(usar_forma_bancada=True)` funcionam com metadata sorteado (forma de bancada reconstruída), o resíduo máximo perto de 100 ms fica > 0,1 pu, e `modelo_lista_fonte.confrontar` põe a cópia primeiro (rms resíduo < 1e-9 vs > 0,01 do `ideal`); controle sem cópia não acusa nada. Dado novo: com o sorteio, 100 ms cai dentro do evento rotulado em só 18,1 % (50 Hz) / 17,1 % (60 Hz) das 2000 sementes (~41 % o evento termina antes, ~42 % começa depois). **Recomendação para o roteiro (juízo):** rodar a 09 amanhã, sim, nestas condições: (1) logo após a 08, rodar `scripts/diag_ciclos_trace.py <sessão> --classes 08,09` (offline); se houver tempo de bancada antes, `diag_marcadores_trace.py` (`ENERGIZAR-MARCADORES`); (2) a 09 sorteada é o primeiro dado que separa "instante fixo em 100 ms" de "acompanha o evento"; com as 3 capturas padrão só ~18 % cairiam dentro do evento, então pedir 6–9 (`set capturas`) se houver tempo; (3) aceitar sem ressalva só capturas sem ciclo trocado e resíduo perto de 100 ms < ~0,05 pu (ruído da 09: 0,008–0,017 pu rms); acima disso manter, marcar suspeita, não usar para treino; (4) é defeito de dado, não de infraestrutura: não interrompe o `run all`. Texto também no CHANGELOG v1.15 (seção nova, no fim).

**Item 4 — Quantificar a perda da 06 na TRACE por ciclo (modelo × programada por perfil e frequência, com a correlação do distúrbio) e propor, sem implementar, se vale mudar a programação.**
- Status: CUMPRIDO
- Explicação: tabelas por perfil × f0 × sorteio e por faixa de `flicker_hz` no CHANGELOG. Resumo (corr. do distúrbio programada × modelo): 60 Hz sorteio ligado 0,881/0,966/1,000 (mín/mediana/máx), 50 Hz 0,794/0,953/0,999; sem sorteio 0,774–0,857 de mínimo, mediana 0,902–0,916; perfis idênticos (só mudam a profundidade); por flicker: 8–12 Hz mediana 0,984–0,989, 20–25 Hz 0,912–0,939 (mín 0,794). Causa medida: tirando do modelo a média de cada ciclo (que a fonte remove da TRACe) a correlação vai a 0,9999–1,0000 nas 28 capturas calculadas; essa média é uma escada de rms 0,002–0,032 pu (máx 0,044) contra distúrbio rms 0,036–0,074 (até ~47 %). Proposta: não vale mudar a programação (nenhum offset por passo de `LIST` no manual extraído; `grep LIST:.*OFFS` vazio); alternativas: (a) comparar a 06 contra a programada e tratar 0,77–1,00 como limite da fonte, (b) métrica adicional sem a média por ciclo, (c) redefinir o flicker com média nula por ciclo (muda `gerar()`, exige autorização e fixtures). Teste: `test_06_a_perda_na_trace_e_so_a_media_por_ciclo_que_a_fonte_remove`.

**Item 5 — Atualizar `docs/correlacao_disturbio.md`, `docs/classes.md` e `CHANGELOG/v1.15.md` (seção nova no fim). Não use "professor", "dono" ou ".tex" no texto novo.**
- Status: CUMPRIDO
- Explicação: `docs/correlacao_disturbio.md` §6–7, `docs/classes.md` (nível de 30 %, seções 5 e 6 novas), `CHANGELOG/v1.15.md` (seção "Pendentes da correlação do distúrbio..." no fim, com Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO). `git diff` das adições não contém "professor", "dono" nem ".tex" (grep vazio).

## Critério de Parada
Atendido. Testes da 05 cobrem THD/rms/fase/teto (`PendentesCorrelacaoDisturbioTests`); a métrica ajustada aparece em `analisar_sessao` e no HTML, com teste de fundamental 1 % maior dando > 0,9999; a 06 tem número (tabelas acima); `TMPDIR=/tmp/claude-0/tmpt /tmp/claude-0/venv/bin/python -m unittest tests.test_offline` -> `Ran 435 tests ... OK (skipped=2)`.

## Pendências que exigem o usuário
- Decidir se a recomendação da 09 (rodar com 6–9 capturas, critério 0,05 pu) entra no roteiro.
- Se quiser a 06 fiel à fonte: autorizar (c) (flicker com média nula por ciclo muda `gerar()`); não implementado.

## Limitações de escopo
Nenhuma que prejudicasse. As sessões reais de 07/10 só existem no PC da bancada, então o ganho real da métrica ajustada por classe não foi medido (apenas sintético).

## A missão resolve o contexto?
Sim. Achado que muda a leitura: a perda da 06 e o "erro" do nível de 30 % da 05 não são defeitos de programação; a 06 perde a média por ciclo que a TRACe não leva, e o 30 % é coerente entre modelo e programada.

## Achados
- (média) 06: toda a perda na TRACe é a média por ciclo; não corrigível pela programação. As compostas com flicker (11, 15) provavelmente herdam o efeito: NÃO VERIFICADO (não calculado).
- (média) A métrica ajustada absorve parte do evento em distúrbios grandes (02/03/04, 18); documentado como complemento, não substituto.
- (baixa) Nível de 30 % da 05 a 380 V: pico 0,8252 pu·√2·380 = 443,5 V > 425 Vp; o limite de bancada deve tratar; NÃO VERIFICADO (não simulado).
- (baixa) `forma_programada_nativa("05")` levantaria `ValueError` para THD > 25 % (só é chamada para níveis nativos; o 30 % vai por TRACe); sem uso errado hoje.
- (info) O CHANGELOG da spec 15 cita "4 falhas" de fixtures no Linux; hoje a suíte passa inteira (baseline atualizada).
- NÃO VERIFICADO: mecanismo da cópia em 100 ms; CSINe a 10/15/20 % e 05 por TRACE na bancada; ganho da métrica ajustada nas sessões reais.
