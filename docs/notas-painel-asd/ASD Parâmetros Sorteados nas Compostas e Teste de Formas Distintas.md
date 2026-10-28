#spec #pri 5

# ASD: Parâmetros Sorteados nas Compostas e Teste de Formas Distintas

## Contexto

As classes compostas (10 a 17) têm parâmetros fixos (sag 0,5; THD 0,2; oscilação de 600 Hz; flicker de 15 Hz). Pela contagem do professor, 01 e 10–16 têm 1 forma distinta em 2000 capturas simuladas. Comentário da Pergunta 15: "esta é a prioridade número 2. As faixas do item 4 [...] estão boas."

Proposta 4 do `atividade.tex`: "na 10, sag ~ U(0,1; 0,9) e THD ~ U(0,05; 0,20); na 12 e na 14, f_osc ~ U(300, 2400) Hz; na 11 e na 15, flicker de U(8, 25) Hz, com a profundidade do item 6. O padrão de capturas dessas classes sobe de 1 para 3, como nas classes que já sorteiam." As faixas de amplitude de cada perfil (norma/literatura/fronteira) já estão definidas pela spec de perfis; as compostas herdam as faixas dos componentes.

Item f) da lista final do professor: "um teste em `tests/test_offline.py` que conte as formas distintas por classe no simulado e falhe se alguma classe tiver poucas, para o problema não voltar."

Autorização do dono (2026-10-12): esta spec pode mudar o que `gerar()` produz para uma dada seed, como parte da mesma versão congelada.

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- `experimentos_waveform/10.py` a `17.py` (`gerar`, `parametros_com_disturbio_reduzido`, `capturas_padrao`), faixas por perfil criadas pela spec de perfis
- Testes: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`
- Depende de: ASD: Início, Duração e Fase Sorteados no gerar()
- Executor: sonnet

## Missão

1. Sortear em `gerar()` os parâmetros de cada composta, usando as faixas do perfil ativo e as da proposta 4 onde o perfil não define.
2. Ajustar `parametros_com_disturbio_reduzido` de cada composta para os parâmetros sorteados, mantendo a tradução do fator k correta.
3. Subir `capturas_padrao` das compostas para 3.
4. Escrever o teste do item f): gerar N capturas simuladas por classe (N pequeno o bastante para o teste rodar rápido), contar formas distintas antes do ruído e falhar se alguma classe tiver menos que um mínimo; justificar N e o mínimo.
5. Registrar a mudança em `CHANGELOG/v1.15.md`.

## Limites

- Pode alterar: `experimentos_waveform/10.py` a `17.py`, `tests/test_offline.py`, `CHANGELOG/v1.15.md`, documentação.
- Não alterar limites de tensão nem a pré-validação de pico (`AGENTS.md`, "Limites inegociáveis").
- Não tocar no hardware. Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/analise-2026-10-12/compostas_sorteadas.md`, uma seção por item da Missão, com tabela classe × formas distintas antes/depois.
- Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

O teste de formas distintas existe e passa para todas as classes; nenhuma composta tem uma forma só; testes offline passam.
