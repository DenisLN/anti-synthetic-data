#spec #pri 10

# ASD: Análises Fora de docs e Arquivo em Branch Separado

## Contexto

Prioridade máxima do usuário (2026-10-13): `docs/` passa a conter só documentação autocontida do projeto. Relatórios datados de análise (`docs/analise-2026-09-21/`, `docs/analise-2026-09-30/`, `docs/analise-2026-10-12/`), planos/specs antigos (`docs/superpowers/`) e listas de tarefas (`docs/TAREFAS_NUVEM_2026-10-07.md`) saem de `docs/` e vão para um branch separado, de preferência só com esses arquivos (decisão do usuário: "outro branch; se der para fazer só de docs, ótimo"). Os scripts temporários de diagnóstico também saem ("não faz sentido").

O que fica: os manuais em PDF (`docs/*.pdf`) e o texto extraído deles, que a documentação cita (`docs/analise-2026-09-21/manuais_txt/`), precisam continuar acessíveis a partir de `docs/`.

## Entradas

- Repositório: `/home/user/anti-synthetic-data`, branch de trabalho `claude/specs-v1-15-review-3w2bgl`
- A mover: `docs/analise-2026-09-21/` (exceto `manuais_txt/`), `docs/analise-2026-09-30/`, `docs/analise-2026-10-12/` (inclui `pendente/`, `resolvido/`, `scripts/`, `limites_perfis/`), `docs/superpowers/`, `docs/TAREFAS_NUVEM_2026-10-07.md`
- Temporários de diagnóstico a apagar do branch principal: `docs/analise-2026-10-12/scripts/diag_*.py`, `logica/diag_digitizer_hipoteses.py`, `logica/diag_digitizer_range.py`, `logica/diag_digitizer_transicao.py`
- Ferramentas de bancada que ficam: `scripts/diag_*.py`
- Depende de: nada

## Missão

1. Criar o branch órfão `arquivo/analises` contendo só os arquivos movidos (mesma árvore de pastas) e as specs desta rodada; dar push.
2. No branch de trabalho, remover esses arquivos de `docs/`, mover `manuais_txt/` para `docs/manuais_txt/` e corrigir toda referência que apontava para os caminhos antigos.
3. Apagar os scripts temporários de diagnóstico listados nas Entradas e as referências a eles na documentação.
4. Garantir que nenhum `.md` de `docs/`, `README.md` ou `AGENTS.md` aponte para um caminho que não existe mais.

## Limites

- Não apagar `scripts/diag_*.py` (ferramentas de bancada usadas no roteiro).
- Não reescrever o conteúdo dos relatórios movidos.
- `CHANGELOG/vX.Y.md` fechados não se reescrevem; referências a caminhos antigos neles ficam (histórico), com uma nota única em `docs/versionamento.md` dizendo onde está o arquivo.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.
- Se algum limite impedir ou restringir o resultado, registrar no relatório em "Limitações de escopo", sem ultrapassá-lo.

## Entregável

- Relatório `.md` com um bloco por item da Missão (texto do item, CUMPRIDO/PARCIAL/NÃO CUMPRIDO/IMPEDIDO, evidência); Critério de Parada; pendências; limitações de escopo; achados.
- Branch `arquivo/analises` no remoto.
- Verificação: `git ls-tree -r --name-only origin/arquivo/analises | head` e um verificador de links nos `.md` (saída no relatório); `python -m unittest tests.test_offline`.
- Toda afirmação cita arquivo e linha, ou o comando e a saída. O que não deu para confirmar entra como NÃO VERIFICADO.

## Critério de Parada

`origin/arquivo/analises` existe com os arquivos movidos; `ls docs/` não tem mais `analise-*`, `superpowers` nem `TAREFAS_*`; o verificador de links não acha caminho quebrado fora dos CHANGELOG fechados; a suíte offline tem o mesmo resultado de antes.
