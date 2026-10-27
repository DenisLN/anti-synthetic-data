#spec #pri 32

# ASD: Documentação Unificada no Read the Docs

## Contexto

O dono quer "unificar a documentação apenas na read the docs, que já está na fork dele". Depois da integração do fork na `main`, o site Sphinx/MyST está em `docs/` (`.readthedocs.yaml`, `docs/conf.py` com `fail_on_warning: true`, tema furo, `docs/index.md` com os toctrees). Mas o estado do projeto continua espalhado em cópias fora do site ou duplicadas (relatório de achados de 2026-10-27, `specs/2026-10-27/findings-pendencias-v1-15-detalhado.md` neste branch, seções 2 e 4):

- `ROTEIRO_BANCADA.md` na raiz (52 KB) e `docs/roteiro-bancada.md` no site; `README.md:26` aponta para o da raiz, enquanto o rastreador manda não lê-lo.
- `README.md` tem uma seção "Mapa da documentação" legada, que não cita os arquivos de rastreio; `AGENTS.md` tem um mapa próprio de `docs/`.
- `mapa/` (vault Obsidian, 57 arquivos, gerado por `scripts/gerar_mapa_pendencias.py`) e `CLAUDE.md`, que manda agentes começar por `mapa/00 Início.md`. **Decisão do dono (2026-10-27): o `mapa/` é do Ricardo e fica na `main`, junto com o site.** Não é removido nem reescrito por esta spec.
- Textos do site que descrevem bugs já corrigidos ou estão datados: `docs/codigo/cli.md` (`run 01 02` roda só a 01), `docs/operacao.md` (HTML limitado a 3 capturas só na simulação), `docs/correlacao_disturbio.md` (coluna "bate?"), `docs/limites_e_calibracao.md:51` ("(v1.15, spec 26)"), banners "main em `fa82f49`... baseline documental de 2026-10-16" (`docs/index.md` e o `note` "Revisão e procedência" repetido nas páginas), caminhos `/tmp/asd-exec-venv/...` e `/tmp/asd-docs-build.log` em `docs/execucao_pendencias.md`, e o link para a versão `docs-site-readthedocs` (`docs/execucao_pendencias.md:5`), que deixa de existir.

Regra: o site em `docs/` é a única documentação de referência. Fora de `docs/` ficam só `README.md` (curto, aponta para o site), `AGENTS.md` e `CLAUDE.md` (instruções para agentes, que apontam para páginas do site em vez de duplicar conteúdo), `mapa/` (vault do Ricardo, navegação para agentes, mantido) e `CHANGELOG/` (registro histórico). As páginas de pendências e de classes são tratadas em outras specs desta rodada.

## Entradas

- `README.md`, `AGENTS.md` (seção "Documentação (mapa)"), `CLAUDE.md`, `ROTEIRO_BANCADA.md`, `docs/roteiro-bancada.md`, `docs/index.md`, `docs/conf.py`, `docs/requirements.txt`, `mapa/`
- Build local: `python -m venv .venv-docs && .venv-docs/bin/pip install -r docs/requirements.txt && .venv-docs/bin/sphinx-build -W -b html docs docs/_build/html`
- Relatório de achados: `specs/2026-10-27/findings-pendencias-v1-15-detalhado.md` (branch `arquivo/analises`), seções 4.1, 4.2, 4.4 e 4.6
- Depende de: ASD: Scripts de Diagnóstico em diag/ e Visita Rodando de Lá

## Missão

1. Fundir `ROTEIRO_BANCADA.md` da raiz em `docs/roteiro-bancada.md` (o conteúdo que só existe na raiz passa para o site; nada some) e remover o arquivo da raiz, corrigindo todas as referências.
2. Reduzir `README.md` a: o que é o projeto, link para o site (`https://anti-synthetic-data.readthedocs.io/`), início rápido (`scripts\START_BENCH.cmd`, `scripts\VISITA_BANCADA.cmd`, suíte offline) e onde ficam `AGENTS.md`/`CHANGELOG`; trocar o mapa de `docs/` do `AGENTS.md` por links para as páginas do site, mantendo intactas as autorizações e os "Limites inegociáveis".
3. Manter `mapa/` na `main` e intacto; conferir que as notas do `mapa/` que citam `ROTEIRO_BANCADA.md` ou caminhos movidos continuam válidas, corrigindo só esses links (se o `mapa/` for gerado, corrigir no gerador `scripts/gerar_mapa_pendencias.py` e regenerar), e citar o `mapa/` no `README.md` como navegação para agentes.
4. Corrigir os textos desatualizados listados no Contexto (fora de `docs/classes/` e das páginas de pendências), conferindo cada fato no código atual com `arquivo:linha`, e trocar os banners de baseline `fa82f49`/16-10 por um aviso único que diga a base real da página.
5. Garantir que o build com `-W` passa e que toda página em `docs/` está num toctree ou marcada `orphan` de propósito; registrar a mudança em `CHANGELOG/v1.15.md`.

## Limites

- Não editar `docs/classes/`, `docs/projeto/pendencias.md`, `docs/PENDENCIAS_TRACKER.md`, `docs/execucao_pendencias.md` (exceto o link e os caminhos `/tmp` citados no item 4), `docs/decisoes_pendentes.md`, `docs/bancada_pendencias.md`, `docs/estado_prontidao.json`: são de outras specs.
- Não reescrever `CHANGELOG/vX.Y.md` fechados nem `docs/evidencias/` (registro histórico).
- Não mexer em código (`logica/`, `experimentos_*`, `tests/`), exceto se o build exigir algo em `docs/_ext/`.
- Não remover nem reescrever as autorizações e os limites inegociáveis do `AGENTS.md`.
- Todo fato sobre comportamento conferido no código (`arquivo:linha`); se o CHANGELOG divergir do código, vale o código.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.
- Se algum limite impedir ou restringir o resultado, registrar no relatório em "Limitações de escopo", sem ultrapassá-lo.

## Entregável

- Relatório `.md` no caminho que o despacho indicar, com: um bloco por item da Missão (copiar o texto do item, dizer CUMPRIDO, PARCIAL, NÃO CUMPRIDO ou IMPEDIDO, e explicar nos dois casos, com evidência); Critério de Parada atendido ou não; pendências que exigem o usuário; limitações de escopo; se a missão resolve o contexto; achados.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo (a publicação remota no RTD depende do painel do RTD, ver spec da integração do fork).
- Verificação: o comando de build das Entradas, com as últimas linhas da saída no relatório; `python -m unittest discover -s tests -p "test*.py"` (resumo).

## Critério de Parada

`ROTEIRO_BANCADA.md` não existe na raiz e `mapa/` continua na `main`; `git grep -n 'ROTEIRO_BANCADA.md' -- . ':!CHANGELOG' ':!docs/evidencias'` vazio; `git grep -n 'docs-site-readthedocs\|/tmp/asd-' -- docs` vazio; `sphinx-build -W` termina sem erro; `README.md` tem o link do site e não tem mapa de documentação próprio.
