#spec #pri 3

# ASD: Correlação da Componente de Distúrbio no Código

## Contexto

O projeto `anti-synthetic-data` gera um dataset de distúrbios de tensão numa bancada (fonte AMETEK MX30 + osciloscópio Keysight) e o professor está revisando as capturas físicas. Hoje a comparação captura × modelo usa a correlação do sinal inteiro (0,989–0,9998), que o professor mostrou ser enganosa porque é dominada pela fundamental: quase qualquer captura passa de 0,99 contra uma senoide pura.

Comentário do professor (`atividade.tex`, Pergunta 2): "Medi a correlação só da componente de distúrbio (medido menos a senoide nominal, contra esperado menos a senoide nominal), depois de alinhar. Ela fica entre 0,95 e 1,00 em 02, 04, 06, 10–16 e 20; entre 0,75 e 0,94 em 03, 07, 09 e 17; e cai para 0,50 na 05 e 0,005 na 08."

O objetivo é implementar essa métrica no código, do jeito que o professor descreveu, para que ela apareça em toda análise de sessão.

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data` (branch `main`, v1.14)
- Documento comentado pelo professor: `C:\Users\denis\Downloads\tcc\02\atividade.tex` (comentários dentro do ambiente `comentario`) e o PDF `C:\Users\denis\Downloads\tcc\02\Atividade_01_comentada.pdf`
- Análise offline atual: `logica/analisar_sessao.py` (alinhamento por `indice_trigger` e cross-correlação em `analisar_offset`), `logica/relatorio_html.py`, `logica/recortar_margem.py`, `logica/sinais.py` (`janela_nominal`)
- Sessões reais para conferir: `resultados/sessao_2026-10-07_127V_50Hz`, `resultados/sessao_2026-10-07_230V_50Hz`, `resultados/sessao_2026-10-07_14-59-54_run02` (127 V/60 Hz)
- O relatório do professor `validacao_gerador_v1.14.md` NÃO está no repositório; os números de referência são os do comentário acima.
- Testes: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`
- Depende de: nada
- Executor: sonnet

## Missão

1. Implementar uma função de correlação da componente de distúrbio: alinhar captura e `gerar()` (mesma seed do metadata), subtrair de cada uma a senoide nominal (mesma f0 e fase do modelo) e calcular a correlação de Pearson entre os dois resíduos dentro da janela rotulada. Decidir onde ela mora (`logica/sinais.py` ou `logica/analisar_sessao.py`) e justificar.
2. Tratar o caso degenerado da classe 01 (resíduo esperado ≈ 0): devolver `None`/NaN com motivo, não um número sem sentido.
3. Expor a métrica na saída de `analisar_sessao.py` e no relatório de `relatorio_html.py`, ao lado da correlação total que já existe.
4. Rodar a métrica nas três sessões de 07/10 e montar uma tabela por classe e sessão, comparando com as faixas do professor.
5. Acrescentar teste offline em `tests/test_offline.py` com sinais sintéticos de resultado conhecido (ex.: distúrbio idêntico → 1,0; distúrbio com sinal trocado → −1,0).

## Limites

- Pode alterar: `logica/sinais.py`, `logica/analisar_sessao.py`, `logica/relatorio_html.py`, `tests/test_offline.py`.
- Não alterar o que `gerar()` produz, nem `mestre.py`/`ametek_orm.py`, nem nada em `experimentos_*`.
- Não tocar no hardware. Tudo offline.
- Respeitar `AGENTS.md`, seção "Limites inegociáveis".
- Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/correlacao_disturbio.md`
- Estrutura: uma seção por item da Missão; a tabela do item 4 com colunas classe, 127 V/60 Hz, 127 V/50 Hz, 230 V/50 Hz, faixa do professor, bate?
- Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline -v` — colar o resumo da saída no relatório.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

A função existe, aparece na saída de `analisar_sessao.py` e no HTML, os testes offline passam, e o relatório traz a tabela das três sessões com os valores de 08 e 05 próximos de 0,005 e 0,50 (ou explica por que diferem).
