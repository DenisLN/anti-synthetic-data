## Análise do orquestrador

- Implementação completa? Sim. Conferido: `ROTEIRO_BANCADA.md` fora da raiz; `git grep 'ROTEIRO_BANCADA.md'` (sem CHANGELOG/evidências) = 0; `git grep 'docs-site-readthedocs\|/tmp/asd-' -- docs ':!docs/evidencias'` = 0; `README.md` com o link do site; `mapa/` presente; `docs/_includes/aviso-base.md` em 46 páginas; `sphinx-build -W -n --keep-going` exit 0 (rodado pelo orquestrador). Mudanças em `experimentos_waveform/08.py` e `scripts/fechar_pendencias.py` são só comentário/texto (diff conferido), sem efeito em `gerar()`.
- Pendências do usuário: nenhuma nova (RTD no painel já listado na spec 30).
- Escopo limitou? O item 4 ficou parcial só porque `docs/classes/` e `docs/projeto/pendencias.md` eram de outras specs; as specs 34 e 35 recebem a instrução de usar o mesmo `aviso-base`.
- Resolve o contexto? Sim.
- Critério de Parada: atendido.
- Classificação: sem-pendencias.

# Relatório: ASD: Documentação Unificada no Read the Docs

Commits locais na `main` (sem push), sobre `38a9d31`: `230740d` (roteiro fundido), `5988b73` (README/AGENTS/CLAUDE), `dafde1f` (aviso único e textos), e o último, `docs: CHANGELOG da unificação e citações de linha em cli.md e operacao.md`.

## Missão, item a item

**Item 1 — Fundir `ROTEIRO_BANCADA.md` da raiz em `docs/roteiro-bancada.md` (o conteúdo que só existe na raiz passa para o site; nada some) e remover o arquivo da raiz, corrigindo todas as referências.**
- Status: CUMPRIDO
- Explicação: `docs/roteiro-bancada.md` antes só fazia `{include} ../ROTEIRO_BANCADA.md`. Agora tem o conteúdo inteiro (553 linhas), com títulos um nível abaixo (mesmo efeito do `heading-offset: 1` anterior; blocos de código intactos). Única frase reescrita: a conferência do Bloco 1 ("`ROTEIRO_BANCADA.md` existe na raiz"). Arquivo da raiz removido com `git rm`. Referências corrigidas em docs/ (tracker, bancada_pendencias, execucao_pendencias, metadata, projeto/analises-arquivadas, estado-validacao, pendencias), `CLAUDE.md`, `README.md`, `mapa/` (2 notas), `scripts/fechar_pendencias.py:57,439` e comentário de `experimentos_waveform/08.py:61` (ver Limitações). Testes citando o arquivo: nenhum. Comando: `git grep -n 'ROTEIRO_BANCADA.md' -- . ':!CHANGELOG' ':!docs/evidencias'` -> vazio.

**Item 2 — Reduzir `README.md` a: o que é o projeto, link para o site (`https://anti-synthetic-data.readthedocs.io/`), início rápido (`scripts\START_BENCH.cmd`, `scripts\VISITA_BANCADA.cmd`, suíte offline) e onde ficam `AGENTS.md`/`CHANGELOG`; trocar o mapa de `docs/` do `AGENTS.md` por links para as páginas do site, mantendo intactas as autorizações e os "Limites inegociáveis".**
- Status: CUMPRIDO
- Explicação: `README.md` reescrito (de 5,8 KB com tabela de 25 linhas, estrutura de pastas e seção de segurança para ~2,3 KB): descrição, link do site, início rápido (setup, `unittest discover`, simulação, `START_BENCH.cmd`, `VISITA_BANCADA.cmd`), e "Fora do site" (AGENTS, CLAUDE, mapa/, CHANGELOG). `AGENTS.md`, seção "Documentação (mapa)": lista por assunto com links para 29 páginas de `docs/` (todas conferidas com `[ -f ]`) e o link do site; o resto do arquivo não foi tocado (`git diff` só nessa seção). `CLAUDE.md` ganhou uma frase apontando para o site. O link raiz do site é o único URL usado; páginas citadas por arquivo, porque o slug de idioma do RTD não é verificável (NÃO VERIFICADO, abaixo). Removidas do README a "Estrutura (resumo)" e "Pendente fora da `main`" (já estão em `docs/arquitetura.md` e `AGENTS.md`); `docs/arquitetura.md:49` deixou de dizer que o índice está no README.

**Item 3 — Manter `mapa/` na `main` e intacto; conferir que as notas do `mapa/` que citam `ROTEIRO_BANCADA.md` ou caminhos movidos continuam válidas, corrigindo só esses links (se o `mapa/` for gerado, corrigir no gerador `scripts/gerar_mapa_pendencias.py` e regenerar), e citar o `mapa/` no `README.md` como navegação para agentes.**
- Status: CUMPRIDO
- Explicação: `mapa/` mantido (57 arquivos). Só duas linhas mudaram: `mapa/00 Início.md:18` e `mapa/dominio/Operação na bancada.md:6` (`[[ROTEIRO_BANCADA]]` -> `[[docs/roteiro-bancada]]`). O gerador só escreve `mapa/pendencias/P-NN.md` e `mapa/_modelos/pendencias.json` (`scripts/gerar_mapa_pendencias.py:1-5`), e nesses não há referência ao roteiro (git grep), então não foi regenerado (também precisa de `../entregas/` e `npx knap`, ausentes, como registra o CHANGELOG da spec anterior). Varredura de todo caminho `docs|scripts|logica|diag|tests|...` entre crases nas notas do mapa: nenhum inexistente. Citação do `mapa/` no `README.md`: seção "Fora do site".

**Item 4 — Corrigir os textos desatualizados listados no Contexto (fora de `docs/classes/` e das páginas de pendências), conferindo cada fato no código atual com `arquivo:linha`, e trocar os banners de baseline `fa82f49`/16-10 por um aviso único que diga a base real da página.**
- Status: PARCIAL
- Explicação: Verificado item por item no checkout atual:
  - `docs/codigo/cli.md` (`run 01 02`): já estava correto ("Atualização P-14", linha 68); código: `logica/cli.py:823-836` (recusa `run all x` e `run 01 02` sem energizar), `:848-854` (`BATERIA_EXCLUIR` em listas). Acrescentei as citações.
  - `docs/operacao.md` (HTML): já correto (linha 128, "vale para ... bancada/simulação"); código `logica/relatorio_html.py:75` (`MAX_CAPTURAS_EMPILHADAS_PADRAO = 3`), `:305-316` (limite aplicado sem distinguir modo). Citação acrescentada.
  - `docs/correlacao_disturbio.md` ("bate?"): já removido (linha 37 diz que foi retirado); nenhuma coluna restante (`grep`).
  - `docs/limites_e_calibracao.md:51`: tirei "(spec 26)", citei `mestre.py:2479-2507` e `sinais.py:430-432`, e corrigi um erro factual: dizia "O JSON não mudou" e exemplificava 07/17 = 1,186/1,031, mas `logica/calibracao_extremos.json:16,25` traz hoje 1,615/1,575 (recalibração de 22/10; o tracker P-07 registra 1,186 -> 1,615 e 1,031 -> 1,575).
  - `docs/execucao_pendencias.md`: link `docs-site-readthedocs` virou `{doc}`projeto/pendencias``; `/tmp/asd-exec-venv/...` virou `sphinx-build ... <pasta de saída>`; `/tmp/asd-docs-build.log` removido.
  - Banners: o `note` "Revisão e procedência" (texto idêntico em 46 páginas fora de `docs/classes/` e `projeto/pendencias.md`) foi trocado por `{include} /_includes/aviso-base.md` (fonte única, `docs/_includes/aviso-base.md`, excluído do build em `docs/conf.py`). O aviso diz: citações `arquivo:linha` conferidas contra `fa82f49` (2026-10-16) salvo indicação na página, a `main` andou, vale o código atual, rodapé mostra o commit do build. `docs/index.md:10` e `docs/como-ler.md:53` deixaram de afirmar "`main` em `fa82f49`".
  - Falta (por isso PARCIAL): os 20 arquivos de `docs/classes/` e `docs/projeto/pendencias.md` seguem com o banner antigo (proibido tocar). E ~45 páginas de `docs/codigo/` e `docs/scpi/` têm um selo próprio "Lido/Conferido em 2026-10-16 (`main` em `fa82f49`)" no corpo: é a data real daquela leitura com permalinks `fa82f49`, mantido; não é o banner.

**Item 5 — Garantir que o build com `-W` passa e que toda página em `docs/` está num toctree ou marcada `orphan` de propósito; registrar a mudança em `CHANGELOG/v1.15.md`.**
- Status: CUMPRIDO
- Explicação: `sphinx-build -W -n --keep-going -b html docs <scratchpad>/out2` -> `build succeeded.` (saída final: "dumping object inventory... done / build succeeded."). Com `-W`, página fora de toctree viraria erro; passou, e conferi que todo `.md` fora de `evidencias/`, `_includes/` e `manuais_txt/` gerou HTML. Nenhum `orphan` foi necessário. Saída em pasta do scratchpad, `docs/_build` não criado. Registro: seção "Documentação unificada no Read the Docs (2026-10-27, mesma versão)" ao fim de `CHANGELOG/v1.15.md`, com Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO.

## Critério de Parada
Atendido, com um reparo de leitura:
- `ls ROTEIRO_BANCADA.md` -> não existe; `mapa/` presente.
- `git grep -n 'ROTEIRO_BANCADA.md' -- . ':!CHANGELOG' ':!docs/evidencias'` -> vazio.
- `git grep -n 'docs-site-readthedocs\|/tmp/asd-' -- docs` sem exclusão ainda acha 4 linhas em `docs/evidencias/2026-10-17/build_documentacao.log` (`/private/tmp/asd-docs-entrega`, log histórico que a spec proíbe reescrever); com `':!docs/evidencias'` -> vazio. Fora de evidencias está limpo.
- `sphinx-build -W` sem erro. `README.md` tem o link do site e `grep -c 'Mapa da documentação'` = 0.
- Suíte: `python -m unittest discover -s tests -p "test*.py"` -> `Ran 760 tests ... OK (skipped=2)` (igual à linha de base).

## Pendências que exigem o usuário
- Conferir no painel do RTD que o build da `main` publica (config `.readthedocs.yaml` inalterada) e qual o slug de idioma das URLs de página (se quiser links de página no AGENTS em vez de caminhos de arquivo).
- Push (orquestrador).

## Limitações de escopo
- `docs/classes/` e `docs/projeto/pendencias.md` mantêm o banner antigo "Revisão e procedência"/`fa82f49` (proibido editar; outras specs). Em `pendencias.md` só troquei as referências ao roteiro (e reescrevi a linha 101 que dizia "existe na raiz").
- Para cumprir o critério `git grep ROTEIRO_BANCADA.md` vazio toquei em código: comentário de `experimentos_waveform/08.py:61` e o comentário/texto de critério de `scripts/fechar_pendencias.py:57,439`. Sem mudança de comportamento nem de `gerar()`; o limite "não mexer em código" admite exceção só para `docs/_ext` e testes, então registro aqui. Suíte verde depois da mudança.
- Não regenerei o `mapa/` (gerador sem entradas aqui e sem o que corrigir).

## A missão resolve o contexto?
Em grande parte: há uma única cópia do roteiro, o README deixou de ser um segundo índice, o AGENTS aponta para o site, e os textos/caminhos citados foram corrigidos; resta o banner antigo nas páginas de classes e de pendências, que dependem de outras specs.

## Achados
- (média) `docs/limites_e_calibracao.md:51` afirmava "O JSON não mudou" e usava 1,186/1,031; falso desde a recalibração de 22/10. Corrigido.
- (média) `docs/roteiro-bancada.md` (Bloco 7, ~linha 253) ainda diz que os fatores do JSON são 07: 1,186 e 17: 1,031 (valores pré-recalibração). Conteúdo movido sem alterar, por ser texto de roteiro/histórico; precisa de decisão do dono (P-07 aguarda revisão do diff). Também citado em `CHANGELOG/v1.15.md:594`.
- (baixa) Três dos quatro itens de "textos desatualizados" do Contexto (cli.md, operacao.md, correlacao_disturbio.md) já estavam corrigidos na `main` pós-integração do fork; só faltavam citações de linha.
- (baixa) `docs/projeto/pendencias.md` e `docs/PENDENCIAS_TRACKER.md` têm referências a linhas do roteiro antigo (ex. "Bloco 8-A", `docs/operacao.md:79`) que não revi além do nome do arquivo.
- (baixa) `docs/execucao_pendencias.md` ainda diz "Baseline de código: `fa82f49...`" no cabeçalho (linha 3) e "atualizada em 17/10/2026" com matriz de 22/10: pertence à spec de pendências, não toquei.
- (sugestão, não feita) Um teste/CI que falhe se reaparecer `ROTEIRO_BANCADA.md` ou o banner antigo; e `.github` check do `sphinx-build -W`.
- NÃO VERIFICADO: publicação remota no RTD e slug de idioma (`/pt/` vs `/pt-br/`; o link antigo usava `/pt/`), pois depende do painel do RTD. NÃO VERIFICADO: a afirmação do aviso de que as citações foram conferidas em `fa82f49` (herdada do banner original; só reconferi as páginas listadas no Item 4).
