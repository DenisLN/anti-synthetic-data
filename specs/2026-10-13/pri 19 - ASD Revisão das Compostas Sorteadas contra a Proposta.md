#spec #pri 19

# ASD: Revisão das Compostas Sorteadas contra a Proposta

## Contexto

O usuário pediu: "na implementação das compostas sorteadas, verificar se realmente está de acordo com o atividade.tex e revisá-las". O `atividade.tex` não está no repositório; o texto da proposta foi citado literalmente na spec original ("Parâmetros Sorteados nas Compostas e Teste de Formas Distintas"):

> "na 10, sag ~ U(0,1; 0,9) e THD ~ U(0,05; 0,20); na 12 e na 14, f_osc ~ U(300, 2400) Hz; na 11 e na 15, flicker de U(8, 25) Hz, com a profundidade do item 6. O padrão de capturas dessas classes sobe de 1 para 3, como nas classes que já sorteiam."

O executor anterior marcou como "escolhas minhas, revise": (a) sag também em 11 e 12 e swell em 13 e 14; (b) faixa do swell = extremos de `swell_niveis`; (c) norma com sag 0,15–0,85 e THD 2–20 %; (d) fronteira alternando 0,1/0,9 e 1,1/1,8 por `capture_index`; (e) 16 com interrupção fixa, 17 com 300 Hz fixo. Também sorteou THD em 13, 15 e 16, que a proposta não cita.

## Entradas

- `logica/perfis.py` (`FAIXAS`, `FAIXAS_SORTEADAS`, `composto`), `experimentos_waveform/10.py`–`17.py` (`gerar`, `parametros_com_disturbio_reduzido`, `capturas_padrao`)
- Testes `ParametrosSorteadosNasCompostasTests` em `tests/test_offline.py`
- `docs/perfis.md`, `docs/classes.md`
- Depende de: nada

## Missão

1. Montar a tabela proposta × código, parâmetro por parâmetro e classe por classe (faixa, distribuição, perfil, sorteio ligado/desligado), citando arquivo:linha, e marcar cada linha como conforme, extensão ou divergente.
2. Conferir a correção de cada sorteio: faixas por perfil, uso do `rng` da classe sem tocar no sub-fluxo de posição, tradução do fator k nos ganchos de bancada com os parâmetros sorteados (inclusive a frequência do flicker/oscilação não reduzida por k), e `capturas_padrao = 3`.
3. Conferir a representação da oscilação de 2400 Hz e do flicker de 25 Hz depois da TRACE por ciclo (modelo × programada nas piores combinações, 50 e 60 Hz).
4. Documentar as extensões (a)–(e) e o THD em 13/15/16 como decisões de projeto em `docs/perfis.md`/`docs/decisoes.md`, com a justificativa técnica, sem atribuí-las a pessoas.
5. Corrigir só o que for divergente da proposta ou defeito; extensões ficam como estão e entram em "Decisões pendentes do usuário".

## Limites

- Não reverter extensões sem decisão do usuário (mudaria o dataset da versão congelada).
- Correção de defeito que mude `gerar()`: fixture `gerar_sorteio_v1_15.json` regravado só nas entradas afetadas, `gerar_literatura_34a0d82.json` intacto.
- Não tocar no hardware.

## Entregável

- Relatório com a tabela do item 1 e os números dos itens 2 e 3.
- Verificação: `python -m unittest tests.test_offline`.

## Critério de Parada

Tabela cobre as classes 10–17 e todos os parâmetros citados na proposta; cada extensão está documentada como decisão de projeto; suíte sem falha nova.
