#spec #pri 1

# ASD: Descontinuar o Gerador de Imagens

## Contexto

Com o relatório HTML gerado pela CLI (`set html on`), o dono quer descontinuar todos os geradores de imagem PNG do repositório. Eles se acumularam ao longo de várias versões; o único que fica é o relatório HTML. Hoje são:

- `logica/visualizador.py` + `scripts/visualizar_npz.ps1`: PNG de inspeção de um `.npz` (v1.4);
- `logica/analisar_sessao.py`: imagem lado a lado gerado × capturado por arquivo (desligável com `--sem-imagens`);
- `logica/comparar_visual.py` (não versionado, grava em `imagens/`, também não versionada);
- `logica/relatorio_html.py` embute figuras em base64 no HTML (este FICA).

Decisão do dono (2026-10-12): descontinuar todos menos o `relatorio_html.py`.

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- Arquivos acima, `README.md` (linhas ~69–83, ~531, ~628–636, ~667–668), `tests/test_offline.py`
- Depende de: ASD: CLI com Recalibração Automática e Relatório HTML
- Executor: haiku

## Missão

1. Remover `logica/visualizador.py` e `scripts/visualizar_npz.ps1`.
2. Remover a geração de imagens de `logica/analisar_sessao.py` (a opção `--sem-imagens` e o código de matplotlib), mantendo toda a análise numérica.
3. Remover `logica/comparar_visual.py` e a pasta `imagens/` (não versionados).
4. Conferir que nada no código, nos testes ou nos scripts ainda chama o que foi removido; se `matplotlib` só restar no `relatorio_html.py`, manter no `requirements.txt`.
5. Atualizar `README.md`/`docs` apontando para o relatório HTML como substituto e registrar em `CHANGELOG/v1.15.md`.

## Limites

- Não remover `logica/relatorio_html.py` nem as funções de análise numérica de `analisar_sessao.py`.
- Antes de apagar `logica/comparar_visual.py` e `imagens/` (não se recuperam pelo git), copiá-los para `docs/analise-2026-10-12/arquivo_descontinuado/` ou outra pasta fora do repositório indicada no relatório.
- Não tocar no hardware. Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/analise-2026-10-12/descontinuar_imagens.md`, uma seção por item da Missão.
- Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline -v` e `git grep -n "visualizador\|comparar_visual\|sem-imagens"` — colar as saídas.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

`git grep` não acha referência aos geradores removidos fora do CHANGELOG, os testes passam, e só o `relatorio_html.py` gera figuras.
