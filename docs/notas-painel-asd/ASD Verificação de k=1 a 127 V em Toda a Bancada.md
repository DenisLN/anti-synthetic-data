#spec #pri 2

# ASD: Verificação de k=1 a 127 V em Toda a Bancada

## Contexto

O documento enviado ao professor afirma (`atividade.tex`, seção "Tensão de referência para rodar todas as classes sem redução"): "A 127 V (50 ou 60 Hz), todas as 20 classes rodam com o distúrbio inteiro (k=1) em todos os níveis. É a tensão de referência proposta." O professor aprovou usar 127 V como referência (k=1 em tudo) e 230 V como teste de generalização. O dono quer uma verificação pequena que ateste isso, já com as mudanças de `gerar()` da nova versão (perfis, sorteios, compostas, classes 05/07/18) e a regra de extremos por frequência.

A exceção conhecida é a 08, que tem teto próprio e nunca roda o modelo inteiro; ela deve ser reportada à parte, não contada como falha.

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- Relatório offline de limites: `.\env\Scripts\python.exe scripts\relatorio_limites_bancada.py --tensao 127 --frequencia 60 --capturas 5` (e `--frequencia 50`); perfil via a variável/opção criada pela spec de perfis
- Depende de: ASD: Regra de Previsão de Extremos por Frequência; ASD: Classes 05, 07 e 18 Alinhadas à Fonte e à Norma
- Executor: haiku

## Missão

1. Rodar o relatório de limites a 127 V/60 Hz e 127 V/50 Hz, com `--capturas 5` e também com 50 capturas, para cada perfil (norma, literatura, fronteira).
2. Listar toda captura com k < 1 ou pulada, por perfil e condição, com o motivo que o relatório dá.
3. Concluir, em uma frase por perfil e condição, se "127 V ⇒ k=1 em todas as classes exceto a 08" vale.

## Limites

- Somente leitura: não alterar código nem calibração.
- Não tocar no hardware. Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/analise-2026-10-12/verificacao_k1_127V.md`, uma seção por item da Missão, com os comandos e as saídas relevantes.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

O relatório traz a conclusão para os 3 perfis × 2 frequências, sustentada pelas saídas do relatório de limites.
