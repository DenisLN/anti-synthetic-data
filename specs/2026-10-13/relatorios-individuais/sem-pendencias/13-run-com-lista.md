## Análise do orquestrador

- Implementação completa? Sim: parsear_lista_classes/normalizar_lista_classes, _run_lista via executar_bateria (corpo extraído de _run_all), confirmação EXECUTAR-CLASSES-<lista>; 14 testes; merge conferido (suíte com as 4 conhecidas).
- Pendências do usuário: decisões menores (BATERIA_EXCLUIR não se aplica à lista; 'run 01 02' roda só a 01) — registradas no relatório final, não bloqueiam.
- Escopo limitado demais? Não.
- Resolve o contexto? Sim.
- Critério de Parada: atendido.
- Classificação: sem pendências.

---

# Relatório: ASD: Run com Lista e Intervalos de Classes

Branch: `worktree-agent-a1ff877ba7d4191a7` (worktree `/home/user/anti-synthetic-data/.claude/worktrees/agent-a1ff877ba7d4191a7`)
Commits: `7219674` feat: run com lista e intervalos de classes na CLI; `a41fc80` docs: run com lista em operacao e CHANGELOG v1.15. Sem push.
Pré-requisito: o worktree estava em `d3c7ce7`, sem o merge da spec 12. Rodei `git merge claude/specs-v1-15-review-3w2bgl` antes de começar; `eb8d236` agora é ancestral de HEAD.

## Missão, item a item

**Item 1 — Aceitar em `run` uma lista de ids e intervalos (`01-07,09-20`, `2,5,8`, `10-16`), com validação (id inexistente, intervalo invertido ou vazio são recusados com mensagem e código 1, sem energizar).**
- Status: CUMPRIDO
- Explicação: `logica/cli.py:189` `parsear_lista_classes()` (função pura) aceita ids e intervalos separados por vírgula, dedupe e ordena. Recusa com `ValueError` e motivo: id fora de 01-20 (`_id_de_classe`, `cli.py:179`), intervalo invertido (`07-01`), intervalo incompleto (`01-`, `-05`), item vazio (`01,,02`, vírgula sobrando) e lista vazia. `cmd_run` (`cli.py:610`) despacha para `_run_lista` (`cli.py:621`) quando o argumento tem `,` ou `-`; espaços são removidos antes (argumentos concatenados). A recusa imprime "Lista de classes recusada: ... Nada foi energizado." e retorna 1 antes de `confirmar`, `_garantir_pasta_sessao`, `autorizar_saida` e `Bancada.from_env`. Testes: `RunListaTests.test_parser_*`, `test_entrada_invalida_e_recusada_sem_chamar_a_bancada`. Verificado também no REPL real (ver "Verificação").

**Item 2 — Executar a lista por `Bancada.executar_bateria`, na ordem numérica, com a mesma resiliência e os mesmos ganchos de fim de run (`set recalibracao`, `set html`) do `run all`, e com o resumo final por classe.**
- Status: CUMPRIDO
- Explicação: `_run_lista` chama `_executar_scripts` (`cli.py:714`), que é o corpo extraído de `_run_all`: `_garantir_pasta_sessao`, `autorizar_saida(True)`, `Bancada.from_env(require_output=True)` com `executar_bateria(scripts)`, resumo "N/M classes OK", e `_fim_da_sessao` (ganchos `set recalibracao`/`set html`). A ordem é a numérica do parser. `executar_bateria` (`mestre.py:1095`) não foi alterado. A resiliência vem dele: falha de experimento isolada e a lista segue (`test_run_lista_falha_de_experimento_nao_para_a_lista`); infraestrutura aborta. `_run_all` continua com a mesma sequência e confirmação `EXECUTAR-20-CLASSES` (testes `test_run_all_mantem_a_confirmacao_antiga` e os existentes `CliRecalibracaoEHtmlTests`, que passam).

**Item 3 — Exigir uma confirmação digitada específica para listas, case-sensitive, que contenha a lista normalizada (ex.: `EXECUTAR-CLASSES-01-07,09-20`), mostrando antes as capturas planejadas e a estimativa de gravações de TRACe só das classes escolhidas.**
- Status: CUMPRIDO
- Explicação: `_run_lista` (`cli.py:621`) imprime cada classe escolhida com suas capturas (`_descrever_capturas`), depois chama `confirmar` com a mensagem "Vai energizar ... (N classes, M capturas planejadas). TRACe: ..." (`_aviso_escritas_trace` sobre `_capturas_das_classes(scripts)`, só das escolhidas) e a string `EXECUTAR-CLASSES-<normalizada>`. `normalizar_lista_classes()` (`cli.py:215`) produz `01-07,09-20`, `02,05,08`, `01-02`. A comparação é a de `confirmar()`, exata e sensível a maiúsculas. Testes: `test_confirmacao_mostra_capturas_so_das_classes_escolhidas` (não aparecem 04 nem 08), `test_confirmacao_exige_a_lista_normalizada_case_sensitive` (recusa `EXECUTAR-CLASSES-1-7,9-20`, minúsculas, espaço final, `EXECUTAR-CLASSE-...`, `EXECUTAR-20-CLASSES` e vazio).

**Item 4 — Documentar em `HELP_TEXT`, `docs/operacao.md` e `CHANGELOG/v1.15.md` (seção nova no fim).**
- Status: CUMPRIDO
- Explicação: `HELP_TEXT` ganhou a entrada `run <lista>` (`cli.py:85`). `docs/operacao.md`: linha nova na tabela de comandos (`run <lista>`, após `run all`) e uma frase na seção de TRACe recomendando rodar por listas, com a referência `cli.py` `_executar_scripts` e `mestre.py:969` (`from_env`). `CHANGELOG/v1.15.md`: seção nova "## `run <lista>`: intervalos de classes na CLI (2026-10-13, mesma versão)" no fim do arquivo, com Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO. Teste `test_help_documenta_a_lista` cobre o `HELP_TEXT`.

## Critério de Parada
- `run 01-03,05` executa exatamente 01, 02, 03 e 05 via `executar_bateria`: ATENDIDO. Teste `RunListaTests.test_run_lista_executa_exatamente_a_lista_em_ordem` usa `from_env` real em modo simulado e `executar_bateria` real, trocando só as classes por falsas; resultado `['01','02','03','05']` e "4/4 classes OK". Execução simulada real com classes verdadeiras (42 s, fora da suíte): `codigo 0`, `4/4 classes OK`, mesma ordem.
- Entradas inválidas recusadas sem chamar `Bancada.from_env`: ATENDIDO. `test_entrada_invalida_e_recusada_sem_chamar_a_bancada` (`from_env`, `confirmar`, `autorizar_saida` e `_garantir_pasta_sessao` com `assert_not_called`), `test_id_unico_inexistente_...` para `run 21`/`00`/`a`.
- Suíte sem falha nova: ATENDIDO. Ver saída abaixo: 390 testes, mesmas 4 falhas da linha de base.

## Pendências que exigem o usuário
- Atribuição nos commits: o bloco "Ambiente" pede o trailer `Co-Authored-By: Claude Opus 5.5`, mas a atribuição do sistema manda `Claude Haiku 5.5`, que é o modelo de fato desta sessão. Usei Haiku 5.5 (os dois trailers estão nos commits). Se o dono quiser Opus, é só reescrever as mensagens dos dois commits.
- `BATERIA_EXCLUIR` não se aplica à lista (decisão minha: `run 02` explícito roda a 02, como `run <NN>` já fazia). Se o dono quiser que a lista também respeite a exclusão, é uma linha em `_run_lista`.
- `run 01 02` (dois ids com espaço e sem vírgula) continua indo para `_run_uma("01")`, como antes, sem aviso. Recusar isso é decisão do dono.

## Limitações de escopo
- Não houve execução em bancada (`BENCH_MODE=1`). Não há hardware neste ambiente. O caminho físico é o de `run all` (mesmo `_executar_scripts`), não exercitado com fonte e Keysight.
- Testes de execução usam classes falsas (`_Falsa`) com `executar()` que só registra o id. A execução com classes reais foi feita manualmente (`cmd_run(["01-03,05"])` em modo simulado, 42 s) e não entrou na suíte porque cada classe gera 2000 capturas simuladas.
- `executar_bateria` e `mestre.py` não foram tocados, conforme o Limite da spec.

## A missão resolve o contexto?
Sim. A lista `run 01-07,09-20` roda por `executar_bateria`, com a mesma resiliência e os mesmos ganchos do `run all`, e permite fatiar a bateria para ficar abaixo da trava de ~280 gravações de TRACe numa conexão (cada `run` abre uma conexão nova em `Bancada.from_env`). Nenhum achado inviabiliza a missão.

## Achados
- Pré-existente, baixa: `run 01 02` executa só a 01 sem avisar (ver Pendências). Gravidade: baixa, mas silenciosa. Não corrigido.
- Pré-existente, baixa: `_run_all` chamava `mestre.scripts_da_bateria_fisica()` duas vezes (uma para planejar, outra para executar), o que duplicava o aviso de exclusão no log. Com `_executar_scripts`, a segunda chamada ainda existe em `_run_all` (`cli.py:695-712`); não alterei, para não mudar `run all` além do necessário.
- Pré-existente, baixa (cosmética): o aviso de TRACe diz "pelo menos 0 s só de espera de gravação" quando a lista não tem TRACe (classes nativas 01/02/03/05 dão 0). Mesma origem de `_aviso_escritas_trace`. Não alterei.
- Cosmética, baixa: "1 capturas" (plural) em `_run_lista`, igual ao padrão existente de `_imprimir_capturas_por_classe`.
- Fora de escopo, baixa: `AGENTS.md` (raiz) não cita `run <lista>` na tabela de comandos. A spec não pedia essa edição; fica como sugestão.
- Verificado no código: classes nativas (01, 02, 03, 05) geram 0 gravações de TRACe, classes de forma arbitrária (08, 10) geram 72 para `08,10` (3 capturas cada). A estimativa separa as duas.
- NÃO VERIFICADO: execução física da lista na bancada (sem hardware). Motivo: ambiente sem instrumento.

## Verificação

Comandos e saídas (raiz do worktree):

```
TMPDIR=/tmp/claude-0/tmpt /tmp/claude-0/venv/bin/python -m unittest tests.test_offline.RunListaTests
...
Ran 14 tests in 0.069s
OK
```

Suíte completa (antes de qualquer mudança, linha de base após o merge da spec 12: 376 testes, 4 falhas; depois: 390 testes):

```
TMPDIR=/tmp/claude-0/tmpt /tmp/claude-0/venv/bin/python -m unittest tests.test_offline
Ran 390 tests in 18.203s
FAILED (failures=4)
FAIL: test_05_07_17_18_sem_sorteio_reproduzem_34a0d82
FAIL: test_literatura_reproduz_byte_a_byte_o_gerar_do_commit_34a0d82
FAIL: test_norma_e_fronteira_mudam_so_o_que_a_spec_manda
FAIL: test_resultado_congelado_da_v1_15
```

As 4 são as fixtures byte a byte conhecidas deste Linux, citadas no Ambiente. Nenhuma falha nova.

Execução simulada real (`cmd_run(["01-03,05"])` com `SIMULATED_MODE=True`, `BENCH_MODE=False`, classes reais, fora da suíte):

```
Classes escolhidas (4), na ordem numérica, capturas planejadas:
  01  NORMAL ...  02  SAG ...  03  SWELL ...  05  HARMONICS ...
Bateria concluída: 4/4 classes OK
codigo 0 tempo 42.0
[('01', True, None), ('02', True, None), ('03', True, None), ('05', True, None)]
```

CLI real pelo REPL (`printf '...' | python logica/cli.py`):

```
bancada> Lista de classes recusada: intervalo invertido '07-01' (o início é maior que o fim). ... Nada foi energizado.
bancada> Lista de classes recusada: item vazio na lista (vírgula sobrando ou repetida). ... Nada foi energizado.
bancada> Classes escolhidas (4) ... 01 02 03 05 ...
Digite EXECUTAR-CLASSES-01-03,05: Cancelado: confirmação não corresponde (comparação sensível a maiúsculas).
```

E `run 08,10` mostra `TRACe: 72 gravações` (só das classes escolhidas).
