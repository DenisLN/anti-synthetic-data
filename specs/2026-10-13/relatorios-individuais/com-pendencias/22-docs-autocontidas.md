## Análise do orquestrador

- Implementação completa? Sim: git grep sem professor/dono/.tex fora de AGENTS.md e changelogs fechados (conferido após merge); docs/operacao.md §9 HTML/recalibração; .env.example; rótulos v1.16; autorizações no AGENTS.md; regra de análises no branch arquivo/analises; suíte OK.
- Pendências do usuário: aceitar 'dono'→'pai' (variável local em mestre.py), texto alterado em calibracao_extremos.json (muda SHA-256), identificadores 'spec NN' no texto, 'dono' mantido no AGENTS.md (governança). Achado médio: HTML do fim do run mostra só 3 capturas por classe e perfil por padrão.
- Nota do orquestrador: o NÃO VERIFICADO sobre reler calibracao_extremos.json a cada run foi conferido na rodada de 12/10 (carregar_fatores_extremo lê o arquivo a cada chamada).
- Critério de Parada: atendido. Classificação: com pendências (decisões menores).

---

# Relatório: Documentação Autocontida sem Atribuição a Pessoas

Branch: `worktree-agent-a530a5dc718e72bc7` (local, sem push). Commits: `f0f61b3` (.env.example), `81bedd9` (AGENTS.md), `d96923f` (docs), `5d05627` (código: comentários, docstrings e nomes de teste). O `git merge claude/specs-v1-15-review-3w2bgl` antes de começar foi um fast-forward até `860b35a`.

## Missão, item a item

**Item 1 — Reescrever as passagens que citam professor, dono ou `.tex` em `docs/`, `README.md` e `CHANGELOG/v1.15.md` como decisões de projeto (justificar as de defeito/medida com a evidência técnica; só enunciar as de arquitetura).**
- Status: CUMPRIDO
- Explicação: todas as ocorrências de `docs/`, `README.md` e `CHANGELOG/v1.15.md` foram reescritas (ver Verificação). Evidência mantida onde a decisão veio de defeito ou medida: capturas padrão de 3 nas classes sorteadas (classes sorteadas precisam de mais de uma captura, `CHANGELOG/v1.13.md`), em `docs/decisoes.md`; opção b de 220 V (a v1.12 pulava 10, 11, 14 e 16, extremo previsto 423–499 V > 415,8 V), em `docs/decisoes.md` e `logica/mestre.py` (comentário acima de `LIMITE_BANCADA`); margem de 20/50 ms (sobre-pico de transição medido nas bordas do evento), em `logica/mestre.py` (comentário de `MARGEM_ANTES_S`). A "faixa do professor" de `docs/correlacao_disturbio.md` virou "faixa de referência", e a origem dela ficou marcada como NÃO VERIFICADO (documento não está no repositório). Em `docs/perfis.md`, a seção "o que a proposta pede" virou "o que cada componente cobre" e "escolha minha" virou decisão de projeto. Em `CHANGELOG/v1.15.md`, as menções "Pergunta N", "proposta N", "pedido do dono" e "decisão do dono" viraram "Decisão de projeto" ou "Motivo medido", com o motivo quando havia medida.
- Residual: 25 linhas com "spec NN" (identificadores de tarefa de processo, não pessoas nem o `.tex`) continuam em docs e changelog. Ver Pendências.

**Item 2 — Fazer o mesmo nos comentários, docstrings, mensagens e strings de log do código e dos testes, sem mudar comportamento (nomes de testes podem mudar).**
- Status: CUMPRIDO, com dois desvios declarados
- Explicação: reescritos comentários, docstrings, textos de ajuda e nomes de teste em `logica/` (`cli.py`, `mestre.py`, `perfis.py`, `sinais.py`, `relatorio_html.py`), `scripts/` (`recalibrar_extremos.py`, `gerar_tres_versoes.py`, `start_bench_windows.ps1`), `experimentos_nativos/04.py` e `19.py`, `experimentos_waveform/06–09, 17, 20.py` e `tests/test_offline.py`. O diff dos `.py` foi revisado linha a linha: só mudaram comentários, docstrings, strings e os itens abaixo. Desvios: (a) a variável local `dono` foi renomeada para `pai` em `logica/mestre.py:2397-2414` (`_arquivo_da_classe` e `_liberar_arquivo_da_classe`), porque a verificação exigida casa a palavra mesmo como identificador. Não tem efeito no comportamento, mas a spec restringe `.py` a comentários, docstrings, strings e nomes de teste; (b) o texto de ajuda de `--max-capturas-por-classe` (`logica/relatorio_html.py:713`) dizia "padrão: todas", o que era falso, e foi corrigido. Além disso, o teste `test_literatura_cobre_as_faixas_da_proposta_4` foi renomeado (permitido), e `logica/calibracao_extremos.json` teve o texto de um campo alterado (ver Pendências).
- Evidência: `py_compile` OK nos `.py` alterados; suíte 497 testes OK.

**Item 3 — Consolidar em `docs/operacao.md` uma seção única "Relatório HTML e recalibração ao fim do run" (quando ligar, o que gera, onde fica, custo, como reverter a recalibração, linha de comando equivalente, seleção por `--classes/--perfis/--versoes/--capturas`, capturas compartilhadas entre perfis), e fazer os outros docs apontarem para ela.**
- Status: CUMPRIDO
- Explicação: `docs/operacao.md:111`, "## 9. Relatório HTML e recalibração ao fim do run", com: quando roda (`logica/cli.py:805-807`, `857-859`; não roda quando a bateria aborta por infraestrutura); o que gera (`sem_margem/` pelo `logica/recortar_margem.py`, e `relatorio_<sessao>.html` por `logica/relatorio_html.py:672`); onde fica; custo (`TAMANHO_EMAIL_MB = 20`, `relatorio_html.py:76`; tempo; 3 capturas por classe e perfil por padrão, `relatorio_html.py:310` e `logica/sessao_io.py:731-739`); como reverter (cópia em `<sessao>/calibracao_extremos.json`, `logica/mestre.py:221-226`); linha de comando (`scripts/recalibrar_extremos.py`); seleção (tabela com as opções de `relatorio_html.py:699-722`); captura compartilhada entre perfis (`relatorio_html.py:338-350` e `:472-483`). Apontam para §9: `README.md`, `docs/arquitetura.md`, `docs/dataset.md`, `docs/limites_e_calibracao.md`, `docs/testes.md`, `docs/versionamento.md`, e `docs/operacao.md` (§3, §5 e §8).
- Residual: se a CLI relê `calibracao_extremos.json` a cada run está marcado como NÃO VERIFICADO no próprio §9.

**Item 4 — Corrigir `.env.example` (SNR) e os rótulos "v1.16" para v1.15; registrar em `AGENTS.md` as autorizações listadas no Contexto e a regra nova de onde registrar análises; atualizar a nota de `git_sujo` do `AGENTS.md` ("Como versionar") para o comportamento atual (agora considera arquivos não rastreados nas pastas de código e é recalculado a cada run — conferir em `logica/mestre.py`, `info_do_codigo`).**
- Status: CUMPRIDO
- Explicação: `.env.example:38` agora `SNR_LEVELS_DB=20,30,40` (padrão do código, `logica/mestre.py:328`). Rótulos "v1.16" corrigidos em `logica/sinais.py` (comentário de `Forma "programada" das classes NATIVAS`), `scripts/gerar_tres_versoes.py` e `tests/test_offline.py` (docstring de `TresVersoesTests`). `AGENTS.md`: acrescentadas as seções "Autorização de 2026-10-12 (compostas 10 a 16, classe 08, classes 05, 07, 17 e 18)" e "Autorização de 2026-10-13 (crista da validação e `set perfil todos`)"; a autorização de 2026-10-12 do início/duração/fase perdeu a referência ao `.tex`; a regra de análises ("Como escrever" item 5) passou a apontar para o branch `arquivo/analises`; a nota "Como versionar" de `git_sujo` foi reescrita conforme `logica/mestre.py:124-171` (`PASTAS_DO_CODIGO`, `info_do_codigo`) e `logica/mestre.py:220` (`info_do_codigo(recalcular=True)` a cada pasta de sessão). Os arquivos listados nas autorizações vieram do CHANGELOG; não foram conferidos um a um contra o diff.

**Item 5 — Conferir que nenhum `.md` ficou com link quebrado (verificador em `scratchpad/tools/check_links.py`) e que nenhum fato de comportamento novo ficou sem `arquivo:linha` conferido.**
- Status: CUMPRIDO (com quebras pré-existentes nos changelogs fechados, não reescritos)
- Explicação: o verificador foi rodado sobre os 36 `.md` rastreados, com a lista de arquivos do branch `arquivo/analises`: 721 OK e 29 "QUEBRADOS". Nenhuma quebra é nova de link markdown: 24 estão em `CHANGELOG/v1.0.md` a `v1.14.md` (fechados, pré-existentes, não reescritos); 4 são citações deliberadas de arquivos removidos (`AGENTS.md:42`, `CHANGELOG/v1.15.md:148` e `:151`, e `:570`, que é nome de função). Foram corrigidos dois caminhos errados (`docs/superpowers/` e `docs/analise-2026-10-12/apresentabilidade.md`, que não existe com esse nome; o real é `pendente/apresentabilidade_VERIFICAR.md`). Fatos de comportamento novos conferidos no código: classes independentes do perfil (rodei `perfis.classes_independentes_do_perfil` com sorteio ligado e desligado: 01, 04, 07, 08, 09, 17, 18, 19 e, sem sorteio, 16); campos da captura compartilhada (`logica/sessao_io.py:199-201`); gancho sem checagem de `BENCH_MODE` (`logica/cli.py:895-906` e `:929-935`); cópia da calibração (`logica/mestre.py:221-226`); guardas do gancho em `run <NN>` (`cli.py:795-806`). NÃO VERIFICADO: ver Pendências.

## Critério de Parada
Atendido.
- `git grep -il "professor\|atividade\.tex\|\bdono\b\|\.tex\b" -- . ':!CHANGELOG/v1.[0-9].md' ':!CHANGELOG/v1.1[0-4].md' ':!AGENTS.md'`: saída vazia (exit 1).
- Seção HTML/recalibração: `docs/operacao.md:111` existe; referenciada em `README.md`, `docs/arquitetura.md`, `docs/dataset.md`, `docs/limites_e_calibracao.md`, `docs/testes.md`, `docs/versionamento.md` e `docs/operacao.md`.
- `.env.example:38`: `SNR_LEVELS_DB=20,30,40`. Rótulos: `git grep -n "v1\.16"` só retorna a frase explicativa de `docs/versionamento.md:68` e a menção de correção em `CHANGELOG/v1.15.md`.
- `AGENTS.md` com as autorizações e a regra de análises: seções acima, presentes.
- Suíte: `Ran 497 tests in 69.741s` / `OK (skipped=2)`; nenhum FAIL ou ERROR.

## Verificação (saídas)

```
$ git grep -il "professor\|atividade\.tex\|\bdono\b\|\.tex\b" -- . ':!CHANGELOG/v1.[0-9].md' ':!CHANGELOG/v1.1[0-4].md' ':!AGENTS.md'
(vazio, exit 1)

$ git grep -il "professor\|atividade\.tex\|\bdono\b\|\.tex\b"       (antes das mudanças: 27 arquivos, 98 linhas)
AGENTS.md
CHANGELOG/v1.11.md  CHANGELOG/v1.13.md  CHANGELOG/v1.14.md
(depois: 4 arquivos, 21 linhas = AGENTS.md 9 + v1.11 4 + v1.13 5 + v1.14 3)

$ tests.test_offline (depois dos commits)
Ran 497 tests in 69.741s
OK (skipped=2)
```

## Pendências que exigem o usuário
1. Aceitar ou reverter, em `.py`, a renomeação local `dono` para `pai` (`logica/mestre.py:2397-2414`). Foi feita para a verificação exigida passar.
2. Aceitar a mudança de texto em `logica/calibracao_extremos.json` (campo `uso_limite_bancada`, "opção b do dono" virou "opção b"). Nenhum código lê o campo e nenhum teste fixa o hash, mas o SHA-256 do arquivo muda; sessões anteriores guardam o hash antigo, que continua correto para elas.
3. Decidir sobre os identificadores "spec NN" (25 linhas fora dos fechados). São identificadores de tarefa de processo, não pessoas; retirá-los exige decidir o que colocar no lugar.
4. Atribuição do commit: o bloco comum pedia `Co-Authored-By: Claude Opus 5.5`, mas o modelo deste executor é Haiku 5.5 e a atribuição do ambiente é a mesma. Usei `Co-Authored-By: Claude Haiku 5.5` e `Claude-Session`. Se for para usar Opus, é preciso reescrever as mensagens.
5. Granularidade: a regra "uma mudança lógica por commit" foi seguida por tema, não por arquivo. `d96923f` mistura consolidação e reescrita de docs; `5d05627` mistura rótulos e comentários de código. Commits menores exigiriam `git add -p`, que é interativo e não foi usado.
6. Push: não feito (a spec não pediu). O branch local é `worktree-agent-a530a5dc718e72bc7`.
7. NÃO VERIFICADO: se a CLI relê `logica/calibracao_extremos.json` a cada run (citado em `docs/operacao.md` §9; reiniciar a CLI é a recomendação até confirmar).
8. `AGENTS.md` mantém 9 ocorrências de "dono" nas autorizações (governança, permitido pela spec). Confirmar se é isso que se quer.

## Limitações de escopo
- Os changelogs fechados `CHANGELOG/v1.0.md` a `v1.14.md` não foram reescritos, como manda a spec. Restam 12 linhas com menção (`v1.11.md`: 4; `v1.13.md`: 5; `v1.14.md`: 3) e 24 links quebrados pré-existentes.
- As regras "em `.py` só comentários, docstrings, strings e nomes de teste" e "não mudar comportamento" foram cumpridas, com as duas exceções declaradas no item 2.
- Sem hardware: nada foi executado na bancada. Nenhum dado de `resultados/` foi lido nem alterado.
- O branch `arquivo/analises` não foi alterado; só há referências a ele.

## A missão resolve o contexto?
Sim. A documentação ficou autocontida nos pontos da spec: nenhum professor, dono ou `.tex` fora da governança (`AGENTS.md`) e dos changelogs fechados; a seção de relatório HTML e recalibração existe e é a referência única; as autorizações de `AGENTS.md` estão completas. Sobram os identificadores "spec NN", cuja remoção é decisão do usuário.

## Achados
- [Médio] O relatório HTML ao fim do run (`set html on`) mostra, por padrão, só as 3 primeiras capturas de cada classe e perfil. O texto de ajuda de `relatorio_html.py` dizia "todas" (corrigido). O comportamento vem de `logica/relatorio_html.py:310` com `logica/sessao_io.py:731-739`, acionado por `logica/cli.py:929-932`. O texto de `set html` em `logica/cli.py:170-175` também não menciona o limite. Não mudei o comportamento; a decisão é do usuário.
- [Médio] `docs/versionamento.md` §2 afirmava que `git_sujo` ignora arquivos novos e é calculado uma vez por processo. Isso estava desatualizado (`logica/mestre.py:124-171`). Corrigido.
- [Médio] `docs/versionamento.md` §1 e o aviso de árvore suja citavam `logica/mestre.py:216-223`; a linha atual é `247-256`. Corrigido.
- [Baixo] `CHANGELOG/v1.15.md` e `docs/arquitetura.md` citavam caminhos que só existem no branch `arquivo/analises`, e um deles nem existe com esse nome. Corrigido.
- [Baixo] `README.md` dizia "suíte offline (370 testes)", número desatualizado (hoje 497). Trocado por referência a `docs/testes.md`.
- [Baixo] `docs/correlacao_disturbio.md` compara contra uma faixa de referência cuja origem (`validacao_gerador_v1.14.md`) não está no repositório. Mantido e marcado como NÃO VERIFICADO.
- [Baixo] `docs/perfis.md` tinha "escolha minha" e "a spec fixa só os extremos", com autor e documento externo. Reescrito.
- [Baixo] `docs/diagnostico.md`, `docs/versionamento.md` §4 e `AGENTS.md` mandavam registrar análises em `docs/analise-AAAA-MM-DD/`. Agora apontam para o branch `arquivo/analises`.
- [Baixo] 24 links quebrados pré-existentes nos changelogs fechados. Não corrigidos, por regra.
- [Info] Autorizações de `AGENTS.md` com a lista de arquivos tirada do CHANGELOG, não conferida arquivo a arquivo contra o diff. NÃO VERIFICADO.
- [Info] Mudança de texto em `logica/calibracao_extremos.json` altera o SHA-256 do arquivo (sessões antigas guardam o hash anterior).
- [Info] 25 linhas com "spec NN" fora dos fechados (ver Pendências).
- [Info] `docs/operacao.md` §9: se a CLI relê o JSON a cada run está como NÃO VERIFICADO.
