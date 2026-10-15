## Análise do orquestrador

- Implementação completa? Sim: sementes_por_snr_db/formula_semente em sinais.ruido_na_janela; git_sujo com não rastreados nas 4 pastas e recálculo por run; perfis em sessao.json; 8 testes; merge conferido (387 testes, 4 conhecidas).
- Pendências do usuário: nenhuma (atribuição do commit usou o modelo do executor; aceitável).
- Escopo limitado demais? Não.
- Resolve o contexto? Sim.
- Critério de Parada: atendido.
- Classificação: sem pendências. Orquestrador moveu o bloco __main__ de test_offline.py para o fim (achado do executor).

---

# Relatório: Rastreabilidade da Semente do Ruído e da Árvore Suja

Branch: `worktree-agent-a13c598803700f339` (merge prévio de `claude/specs-v1-15-review-3w2bgl`, fast-forward até `ed8dd7b`).
Commit local: `928f4fd feat: rastreabilidade da semente do ruído, árvore suja e perfil por run (spec 14)`. Sem push.

## Missão, item a item

**Item 1 — Gravar em `ruido_janela` a semente de cada nível (`sementes_por_snr_db`) e um identificador da fórmula (ex.: `"formula_semente": "seed + round(snr_db*1000) + 50000000"`), no caminho de bancada, no simulado e no script offline.**
- Status: CUMPRIDO
- Explicação: `logica/sinais.py` — `FORMULA_SEMENTE_RUIDO` (constante, linha ~171) e, em `ruido_na_janela`, o dicionário `ruido_janela` ganha `sementes_por_snr_db` (chave `str(snr_db)`, igual a `snr_medido_db`) e `formula_semente`. A semente de cada nível é a mesma chamada de `semente_do_ruido` de antes; o ruído gerado não muda. Como a função é única, bancada (`logica/mestre.py`, chamada de `ruido_na_janela`), simulado (mesmo caminho, `simulado=True`) e `scripts/gerar_ruido_janela.py` gravam o campo. Verificado por `RastreabilidadeRuidoEArvoreTests.test_semente_gravada_reproduz_o_vetor_de_ruido` (reconstrói o vetor só a partir da semente gravada, tolerância 1e-12) e `test_sessao_simulada_grava_sementes_em_ruido_janela` (sessão simulada real com níveis 20/30/40 dB: `ruido_janela.sementes_por_snr_db == {"20.0": seed+20000+5e7, ...}` em cada captura).

**Item 2 — Fazer `git_sujo` considerar também arquivos não rastreados dentro de `logica/`, `experimentos_nativos/`, `experimentos_waveform/` e `scripts/`, e recalcular a procedência a cada `run` da CLI (não uma vez por processo), mantendo o aviso em destaque sem bloquear.**
- Status: CUMPRIDO
- Explicação: `logica/mestre.py` — `PASTAS_DO_CODIGO` e `info_do_codigo(*, recalcular=False)`. `git_sujo` = `git status --porcelain --untracked-files=no` não vazio OU `git ls-files --others --exclude-standard -- <4 pastas>` não vazio (arquivos ignorados, como `__pycache__`, não contam). Novo campo `arquivos_nao_rastreados`. `preparar_pasta_da_sessao` chama `info_do_codigo(recalcular=True)`; a CLI chama essa função no início de cada `run`/`run all` via `_garantir_pasta_sessao` (`logica/cli.py`). O aviso em destaque continua sem bloqueio e agora lista os arquivos novos. Testes: `test_arquivo_novo_em_pasta_do_codigo_acende_git_sujo`, `test_cada_pasta_do_codigo_conta_e_ignorado_nao`, `test_cache_sem_recalcular_mantem_o_valor_do_processo`, `test_preparar_pasta_recalcula_entre_runs_e_grava_perfis` (repositório git temporário; o recálculo entre duas pastas muda `git_sujo` de False para True).

**Item 3 — Registrar em `sessao.json` os perfis usados nos runs da sessão.**
- Status: CUMPRIDO
- Explicação: `sessao.json` (`logica/mestre.py`, `preparar_pasta_da_sessao`) ganha `perfil` (perfil do run) e `perfis_usados_na_cli` (lista, na ordem, do perfil de cada run da CLI até esta pasta, inclusive). `logica/cli.py`: `SessaoCLI._perfis_usados` acumula `mestre.PERFIL` em cada `_garantir_pasta_sessao()`. Interpretação: cada run tem pasta e `sessao.json` próprios, então "perfis dos runs da sessão" foi lido como a lista acumulada da CLI em cada pasta. Teste: `test_cli_grava_perfil_de_cada_run_na_sua_pasta` (run 1 literatura; run 2 norma -> `perfis_usados_na_cli = ["literatura", "norma"]`).

**Item 4 — Documentar os campos em `docs/metadata.md` e registrar em `CHANGELOG/v1.15.md` (seção nova no fim).**
- Status: CUMPRIDO
- Explicação: `docs/metadata.md` — linhas novas em `sessao.json` (`arquivos_nao_rastreados`, `perfil`, `perfis_usados_na_cli`) e em `ruido_janela` (`sementes_por_snr_db`, `formula_semente`); a descrição de `git_sujo` foi corrigida (antes dizia que arquivo novo não conta em nenhuma pasta). Nenhum campo renomeado ou removido. `CHANGELOG/v1.15.md` — seção nova "Rastreabilidade: semente do ruído, árvore suja e perfil por run (spec 14, 2026-10-13, mesma versão)" no fim do arquivo, com Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO.

## Critério de Parada
**Atendido.**
- Testes novos passam: `RastreabilidadeRuidoEArvoreTests`, 8 testes OK.
- `ruido_janela.sementes_por_snr_db` aparece numa sessão simulada: teste `test_sessao_simulada_grava_sementes_em_ruido_janela` OK (sessão simulada executada pelo `Bancada`, `metadata/01_normal.jsonl`).
- Suíte sem falha nova. Evidência, `TMPDIR=/tmp/claude-0/tmpt /tmp/claude-0/venv/bin/python -m unittest tests.test_offline`:
  - Antes (linha de base após o merge): `Ran 379 tests ... FAILED (failures=4)`, as 4 conhecidas.
  - Depois: `Ran 387 tests in 19.707s` / `FAILED (failures=4)`. As 4 falhas são exatamente `test_05_07_17_18_sem_sorteio_reproduzem_34a0d82`, `test_literatura_reproduz_byte_a_byte_o_gerar_do_commit_34a0d82`, `test_norma_e_fronteira_mudam_so_o_que_a_spec_manda` e `test_resultado_congelado_da_v1_15`.
  - Durante o trabalho apareceram 6 falhas novas (5 de `TerminalDeDiagnosticoTests` e 1 `KeyError` em `test_arvore_suja_em_bancada...`); corrigidas antes do commit (ver Achados).
- Log completo das duas rodadas: `scratchpad/baseline_14.txt` e `scratchpad/after_14b.txt`.

## Pendências que exigem o usuário
- **Atribuição do commit:** o `blocos_comuns.md` pede `Co-Authored-By: Claude Opus 5.5`, mas a instrução de atribuição do próprio harness nesta sessão pede `Claude Haiku 5.5`. Usei a do harness (Haiku 5.5). Se o dono quiser Opus 5.5, é só reescrever a última mensagem do commit `928f4fd`.
- **Um commit só:** o `AGENTS.md` pede uma mudança lógica por commit. Fiz um commit único porque os testes novos ficam numa classe só e dividi-la em dois commits exigiria reescrever testes. Se o dono preferir separar (sementes / procedência+perfil), dá para reordenar.

## Limitações de escopo
- `git_sujo` é calculado no início de cada `run`, não durante ele. Uma edição de arquivo feita no meio de um `run all` não aparece no metadata. Limite do escopo (a spec pede recálculo por run, não contínuo) e não foi ultrapassado.
- `perfis_usados_na_cli` vale para o processo da CLI: reiniciar a CLI zera a lista.
- Os testes de terminal (`TerminalDeDiagnosticoTests`) agora fixam `info_do_codigo` no `setUp`. Isso não enfraquece nenhuma asserção (elas continuam verificando o Popen do terminal), mas é uma alteração em teste existente; registrei no CHANGELOG.
- Nada tocou hardware. `BENCH_MODE` não foi definido em nenhum momento.

## A missão resolve o contexto?
Sim. A semente de cada nível e a fórmula agora ficam no metadata da captura, `git_sujo` passa a apanhar código novo não commitado, e `sessao.json` registra o perfil. Nada disso inviabiliza a missão.

## Achados
- **Média (corrigido antes do commit):** `info_do_codigo` com `git ls-files` tinha que lidar com o mock de `subprocess.run` do teste `test_commit_e_versao_do_numpy_sao_lidos_do_ambiente` (ok, continua passando). O aviso de árvore suja falhava com `KeyError` quando `info_do_codigo` era substituído por um dicionário sem o campo novo; trocado por `.get`.
- **Média (corrigido antes do commit):** os 5 testes de `TerminalDeDiagnosticoTests` contam todos os `subprocess.Popen` (patch global), e o recálculo por run passou a gerar `git` por `Popen`. Procedência fixada no `setUp` da classe.
- **Baixa, pré-existente, NÃO alterado:** em `tests/test_offline.py`, `if __name__ == "__main__": unittest.main()` (linha ~6948) fica no meio do arquivo; `RmsCaEPicoPrevistoTests` vem depois dele. Só afeta execução direta do arquivo como script; `python -m unittest tests.test_offline` roda tudo. Mantido como estava (fora do escopo).
- **Baixa, NÃO VERIFICADO:** com `set recalibracao on`, a recalibração ao fim de um run altera `calibracao_extremos.json` e o próximo run copia a nova versão. Agora cada pasta grava o `sha256` da cópia em uso, então a mudança fica rastreada por run; a CLI continua sem avisar. Não verificado numa campanha real.
- **Informativo:** `scripts/gerar_ruido_janela.py` grava `git_sujo` do próprio processo no `indice.json` (sem cache entre processos). Não precisou de mudança; `arquivos_nao_rastreados` não foi acrescentado ao índice.
