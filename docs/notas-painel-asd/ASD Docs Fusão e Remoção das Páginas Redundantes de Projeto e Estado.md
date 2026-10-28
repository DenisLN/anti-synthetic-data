#spec #pri 11

# ASD Docs: Fusão e Remoção das Páginas Redundantes de Projeto e Estado

## Contexto

O site de documentação (Sphinx, fonte em `docs/`, publicado no Read the Docs) tem, no menu "Projeto e estado" (`docs/index.md`, toctree com `:caption: Projeto e estado`), 12 entradas, e boa parte repete a mesma lista de pendências P-01 a P-31. Cada página nasceu de uma frente diferente da integração do fork e ninguém consolidou depois. O dono pediu: **fundir e apagar páginas, centralizar tudo, sem coisa repetida nem inútil**.

Fonte viva e única do estado: `docs/estado_prontidao.json`, renderizado no build por `docs/_ext/estado_pendencias.py` e `docs/_ext/pendencias.py` em `docs/projeto/pendencias.md`. O vault Obsidian `mapa/` é gerado por `scripts/gerar_mapa_pendencias.py`. As demais páginas são narrativa duplicada. O que se sabe pelos cabeçalhos (a spec exige conferir o corpo antes de agir):

| Página | O que parece ser | Suspeita |
|---|---|---|
| `docs/projeto/pendencias.md` | gerada do JSON (estado, resolução, perguntas ao dono) | **fica** |
| `docs/projeto/pendencias-inventario-2026-10-16.md` (565 linhas) | pedido original de 16/10, "histórico" | cada P-NN em `pendencias.md` aponta para uma âncora dela |
| `docs/execucao_pendencias.md` | registro de trabalho de 17/10 com critérios e decisões | diz que não repete estados |
| `docs/PENDENCIAS_TRACKER.md` | protocolo para agentes; abre dizendo "Esta página não guarda estado" | instrução de IA, não de leitor do site |
| `docs/bancada_pendencias.md` (273 linhas) | roteiro da visita física | sobrepõe `docs/roteiro-bancada.md` e `scripts/visita_bancada.py` |
| `docs/decisoes_pendentes.md` (144 linhas) | formulário de decisões do dono | sobrepõe as "perguntas ao dono" geradas em `pendencias.md` |
| `docs/projeto/passo-final-sin.md` | ficha de uma só pendência (P-18) | conteúdo técnico de SCPI/ORM |
| `docs/projeto/analises-arquivadas.md` | lista de análises do branch `arquivo/analises` | cabe em `docs/historico.md` |
| `docs/projeto/estado-validacao.md` | matriz das 20 classes por camada | tem conteúdo próprio; replica o placar |
| `docs/sobre.md`, `docs/historico.md`, `docs/contribuir_docs.md` | licença/citação, versões, como contribuir | ficam; `contribuir_docs` sai do menu "Projeto e estado" |

Meta de forma final do menu "Projeto e estado": `projeto/estado-validacao`, `projeto/pendencias`, `historico` e `sobre`; `contribuir_docs` num caption próprio (por exemplo "Contribuir"), junto com o protocolo para agentes se ele for mantido no site.

Há referências cruzadas em muitos arquivos (grep de 2026-10-27): `AGENTS.md`, `CLAUDE.md`, `CHANGELOG/v1.15.md`, `docs/classes.md`, `docs/classes/05-harmonics.md`, `docs/classes/08-transient.md`, `docs/codigo/acoplamentos.md`, `docs/codigo/ametek_orm.md`, `docs/como-ler.md`, `docs/configuracao.md`, `docs/dataset.md`, `docs/decisoes.md`, `docs/limites_e_calibracao.md`, `docs/operacao.md`, `docs/scpi.md`, `docs/versionamento.md`, `docs/visao-geral.md`, `docs/_ext/estado_pendencias.py`, `mapa/00 Início.md`, `mapa/dominio/Operação na bancada.md`, `mapa/Mapa.canvas` e as notas `mapa/pendencias/P-NN.md`. O build usa `-W`: link quebrado reprova.

Esta spec vem depois da spec de publicação do Zenodo, que edita `docs/decisoes_pendentes.md`, `docs/sobre.md` e `docs/versionamento.md` (a decisão de licença e autoria da P-20 precisa estar preservada ao fundir).

## Entradas

- Projeto: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`, partindo do branch `feat/publicacao-zenodo` já mesclado ou, se ainda não estiver, dele mesmo.
- Leia: `docs/index.md`, `docs/contribuir_docs.md` (formato do JSON e fluxo), `docs/_ext/estado_pendencias.py`, `docs/_ext/pendencias.py`, `scripts/gerar_mapa_pendencias.py`, `tests/test_estado_pendencias.py`, `CLAUDE.md`, `AGENTS.md` (seção "Documentação (mapa)").
- Comandos: `sphinx-build -W -n --keep-going -b html docs docs/_build/html`; `python scripts/gerar_mapa_pendencias.py`; `python -m unittest tests.test_estado_pendencias`; suíte completa `python -m unittest discover -s tests -p "test*.py"`.
- Depende de: ASD: Pacote de Publicação do Dataset e Preparação do Zenodo (P-20)
- Executor: sonnet

## Missão

1. Inventariar, só leitura, o corpo de cada página da tabela do Contexto e classificar cada bloco de conteúdo como ÚNICO (não existe em outro lugar), DUPLICADO (existe em `estado_prontidao.json`, `pendencias.md` gerada, `roteiro-bancada.md`, `CLAUDE.md`, `AGENTS.md` ou nos `CHANGELOG`) ou MORTO (desatualizado ou sem leitor). Para cada DUPLICADO citar arquivo e linha onde o fato continua; para cada ÚNICO dizer o destino.
2. Fundir o que for ÚNICO nos destinos definidos pelo inventário, seguindo o alvo do Contexto: decisões e perguntas ao dono para `estado_prontidao.json`/`pendencias.md` (sem mudar o formato do JSON, salvo se o inventário provar que é indispensável, e então atualizando `docs/contribuir_docs.md` e o teste); roteiro da visita para `docs/roteiro-bancada.md`; passo final SINE para a página técnica que já trata do assunto (`docs/scpi.md` ou `docs/codigo/ametek_orm.md`, escolhida com evidência); análises arquivadas para `docs/historico.md`; protocolo para agentes para `CLAUDE.md` ou `docs/contribuir_docs.md`. Mover o texto sem reescrever fatos; cortar só duplicata. A decisão de licença, autoria e Zenodo da P-20 deve sobreviver.
3. Apagar com `git rm` as páginas que ficaram sem conteúdo único: no mínimo `docs/execucao_pendencias.md`, `docs/PENDENCIAS_TRACKER.md`, `docs/bancada_pendencias.md`, `docs/decisoes_pendentes.md`, `docs/projeto/passo-final-sin.md` e `docs/projeto/analises-arquivadas.md`. Para `docs/projeto/pendencias-inventario-2026-10-16.md`: apagar só se cada âncora para a qual `pendencias.md` aponta tiver o pedido original preservado no destino; se não der, tirá-la do menu com `:orphan:` e listar no relatório o que falta migrar, sem apagá-la.
4. Atualizar todas as referências às páginas removidas ou movidas: toctree de `docs/index.md` (menu final conforme a meta do Contexto), todos os `{doc}` e links nos arquivos listados no Contexto, as extensões em `docs/_ext/`, `scripts/gerar_mapa_pendencias.py` (se citar caminhos), as notas e o canvas de `mapa/`, `CLAUDE.md` e a seção "Documentação (mapa)" de `AGENTS.md`. Em `CHANGELOG/vX.Y.md` fechados e em `docs/historico/*` não corrigir caminhos antigos; são registro histórico.
5. Verificar e registrar: build do site com `-W` sem nenhum aviso; `python scripts/gerar_mapa_pendencias.py` duas vezes seguidas sem diferença no `git diff` da segunda; `tests.test_estado_pendencias` e a suíte completa passando; grep por qualquer link ou nome das páginas removidas fora dos arquivos históricos sem resultado; acrescentar entrada em `CHANGELOG/v1.15.md` (Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO) com a contagem antes e depois de entradas no menu "Projeto e estado" e de linhas totais em `docs/*.md`.

## Limites

- Trabalhar num branch novo `docs/enxugar-site`, a partir da `main` (já com a spec de Zenodo mesclada, ou do branch dela se ainda não estiver), com um commit por mudança lógica (`tipo: resumo em português`). Não fazer push, não usar `--force`, não mexer direto na `main`.
- Somente documentação e os arquivos de infraestrutura de documentação listados (`docs/`, `docs/_ext/`, `mapa/`, `scripts/gerar_mapa_pendencias.py`, `CLAUDE.md`, `AGENTS.md`, `CHANGELOG/v1.15.md`, e o teste do estado se o formato mudar). Não alterar `logica/`, `experimentos_nativos/`, `experimentos_waveform/`, `tests/fixtures/` nem os limites inegociáveis do `AGENTS.md`.
- Não alterar o conteúdo de `docs/estado_prontidao.json` (estados, resoluções, evidências); nada de encerrar ou reabrir pendência. Não tocar `docs/evidencias/`, `docs/historico/*` nem `CHANGELOG/vX.Y.md` fechados.
- Não reescrever nem resumir fatos ao mover; não inventar conteúdo. Se um bloco ÚNICO não tiver destino claro, mantê-lo e listá-lo no relatório como pendência para o dono.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.
- Se algum limite impedir ou restringir o resultado, registrar no relatório em "Limitações de escopo", sem ultrapassá-lo.

## Entregável

- Relatório `.md` no caminho que o despacho indicar, com: um bloco por item da Missão (copiar o texto do item, dizer CUMPRIDO, PARCIAL, NÃO CUMPRIDO ou IMPEDIDO, e explicar nos dois casos, com evidência); Critério de Parada atendido ou não; pendências que exigem o usuário; limitações de escopo; se a missão resolve o contexto; achados.
- Tabela do inventário (item 1): página, bloco, classificação (ÚNICO, DUPLICADO, MORTO) e destino ou onde continua (arquivo:linha).
- Lista das páginas apagadas, das movidas, das mantidas e das que viraram `:orphan:`, cada uma com o motivo.
- Verificação: a saída do build `sphinx-build -W`, da suíte completa e do grep de referências residuais vai no relatório.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo (por exemplo, o build no Read the Docs de verdade, que só roda depois do push). Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

Todos verdadeiros: (a) as páginas listadas no item 3 não existem mais no branch `docs/enxugar-site`, exceto as que o relatório justificar como `:orphan:`; (b) o toctree "Projeto e estado" de `docs/index.md` tem no máximo 5 entradas e `contribuir_docs` está fora dele; (c) `sphinx-build -W -n --keep-going -b html docs docs/_build/html` termina sem avisos, a suíte completa passa e o gerador do mapa é idempotente, com as saídas no relatório; (d) `git grep` pelos nomes das páginas apagadas só encontra `CHANGELOG/vX.Y.md` fechados, `docs/historico/*` e `docs/evidencias/`; (e) `git diff --stat main -- logica experimentos_nativos experimentos_waveform tests/fixtures docs/estado_prontidao.json` está vazio, exceto o que o item 2 justificar sobre o JSON; (f) o relatório cobre os 5 itens da Missão e a tabela do inventário.
