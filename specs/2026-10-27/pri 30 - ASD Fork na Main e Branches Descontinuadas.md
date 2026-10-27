#spec #pri 30

# ASD: Fork na Main e Branches Descontinuadas

## Contexto

O Ricardo (dupla de TCC) trabalhou num fork, `rmlinxic/anti-synthetic-data`. Todo o trabalho dele está no branch `feat/execucao-pendencias-v1-15` do fork, HEAD `cd1e6a9` (2026-10-22): 42 commits à frente da `main` do Denis (`fa82f49`), que é ancestral direto. Ou seja, a `main` avança por **fast-forward**, sem conflito. Os outros branches do fork são idênticos aos do upstream (mesmos SHAs, conferido em 2026-10-27).

O dono quer: "coloque tudo que ele fez na minha main, e descontinue todas as outras branchs que eu tenho".

Estado dos branches do upstream `DenisLN/anti-synthetic-data` em 2026-10-27:

| Branch | SHA | Relação com `cd1e6a9` |
|---|---|---|
| `main` | `fa82f49` | ancestral (fast-forward) |
| `docs/site-readthedocs` | `5bf366f` | **não** é ancestral; 14 commits sobre `fa82f49`. O conteúdo de `docs/` foi trazido para o fork (o fork tem `docs/conf.py`, `.readthedocs.yaml`, `docs/classes/` etc.); só a pasta `docs-site-plano/` da raiz ficou de fora |
| `feat/passo-final-sin` | `18b144d` | **não** é ancestral. O fork reintegrou o recurso com padrão **desligado** (`logica/ametek_orm.py:206`, `passo_final_sin: bool = False`), enquanto o branch tinha padrão ligado. PR aberto: https://github.com/DenisLN/anti-synthetic-data/pull/3 |
| `claude/specs-v1-15-review-3w2bgl` | `ca64d09` | ancestral |
| `arquivo/analises` | `49c1d28` | branch de arquivo histórico (análises e specs). **Fica**: é onde estas specs moram |
| `claude/blissful-heisenberg-cck1vb` | `fa82f49` | branch de trabalho de sessão de agente |

O Read the Docs publica hoje a versão `docs-site-readthedocs` (link em `docs/execucao_pendencias.md:5` do fork: `https://anti-synthetic-data.readthedocs.io/pt/docs-site-readthedocs/...`). Apagar esse branch derruba essa versão do site, e a configuração de qual branch o RTD constrói fica no painel do RTD, fora do repositório.

## Entradas

- Repositório: `DenisLN/anti-synthetic-data` (remoto `origin`).
- Fork: `git remote add fork https://github.com/rmlinxic/anti-synthetic-data && git fetch fork` (público, leitura anônima).
- Comandos de conferência: `git rev-list --left-right --count fork/feat/execucao-pendencias-v1-15...origin/main`; `git merge-base --is-ancestor <a> <b>`; `git diff <branch> fork/feat/execucao-pendencias-v1-15 --stat`.
- `AGENTS.md`, seção "Como versionar" (cita `feat/passo-final-sin`, PR #3, como trabalho pendente).
- `CLAUDE.md` do fork (diz "Remoto `origin` = fork `rmlinxic/anti-synthetic-data`. Não altere `main` nem `upstream`").
- Depende de: nada

## Missão

1. Antes de apagar qualquer coisa, comparar `docs/site-readthedocs` e `feat/passo-final-sin` com `cd1e6a9` e listar no relatório tudo o que existe nesses branches e **não** está no fork (arquivo, trecho de código ou de doc), com a decisão para cada item: já coberto de outra forma, trazido para a `main` neste trabalho, ou descartado de propósito (com o motivo).
2. Avançar `origin/main` para `cd1e6a9` por fast-forward (`git merge --ff-only`) e dar push. Autoria dos commits do Ricardo preservada.
3. Criar uma tag anotada `arquivo/<nome-do-branch-com-barras-trocadas-por-hifen>` no HEAD de cada branch a descontinuar (`docs/site-readthedocs`, `feat/passo-final-sin`, `claude/specs-v1-15-review-3w2bgl`) e dar push das tags, para que nenhum commit fique inalcançável.
4. Fechar o PR #3 (sem merge) com um comentário dizendo que o passo final SINE entrou na `main` desligado por padrão em `cd1e6a9` e que a validação física segue como pendência P-18; depois apagar no `origin` os branches `docs/site-readthedocs`, `feat/passo-final-sin` e `claude/specs-v1-15-review-3w2bgl`.
5. Atualizar `AGENTS.md` ("Como versionar": não há mais branch/PR de trabalho pendente; trabalho pendente vive na página de pendências do site) e `CLAUDE.md` (o `origin` passa a ser `DenisLN/anti-synthetic-data`; o fork deixa de ser o remoto de trabalho), e registrar a integração em `CHANGELOG/v1.15.md` no modelo do projeto.
6. Escrever no relatório, como pendência do dono, o passo manual no painel do Read the Docs: ativar a versão `latest` construída da `main` como padrão e desativar a versão `docs-site-readthedocs`.

## Limites

- Nunca `push --force` na `main`; se o fast-forward não for possível, parar e relatar.
- Não apagar `arquivo/analises`. Os branches `claude/*` de sessões de agente em andamento só são apagados depois que o seu trabalho estiver na `main`.
- Não mexer no fork do Ricardo (sem permissão de escrita; nem tentar).
- Não alterar código em `logica/`, `experimentos_*` nem `tests/` nesta spec (só git, `AGENTS.md`, `CLAUDE.md`, `CHANGELOG/v1.15.md`).
- Limites inegociáveis do `AGENTS.md` intactos.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.
- Se algum limite impedir ou restringir o resultado, registrar no relatório em "Limitações de escopo", sem ultrapassá-lo.

## Entregável

- Relatório `.md` no caminho que o despacho indicar, com: um bloco por item da Missão (copiar o texto do item, dizer CUMPRIDO, PARCIAL, NÃO CUMPRIDO ou IMPEDIDO, e explicar nos dois casos, com evidência); Critério de Parada atendido ou não; pendências que exigem o usuário; limitações de escopo; se a missão resolve o contexto; achados.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Verificação: `python -m unittest discover -s tests -p "test*.py"` na `main` depois do fast-forward (saída resumida no relatório: total, falhas, erros, skips) e `git ls-remote --heads origin` / `git ls-remote --tags origin 'arquivo/*'` depois das remoções.

## Critério de Parada

`git rev-parse origin/main` = `cd1e6a9` (ou descendente com só os commits de `AGENTS.md`/`CLAUDE.md`/`CHANGELOG`); `git ls-remote --heads origin` lista só `main`, `arquivo/analises` e branches `claude/*` de sessão em andamento; as três tags `arquivo/*` existem no `origin` apontando para os SHAs da tabela do Contexto; PR #3 fechado; o relatório lista o que ficou só nos branches apagados.
