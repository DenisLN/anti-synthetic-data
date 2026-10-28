#spec #pri 3

# ASD: Classe 08 com Impulso Fora da Fronteira de Ciclo

## Contexto

A 50 Hz o impulso da classe 08 saiu em 100 ms em vez de 80 ms, nas três capturas; a 60 Hz sai em 80,0 ms. A 50 Hz, 80 ms é exatamente o início do 5.º ciclo (amostra 0 da TRACE desse ciclo), e o impulso é reproduzido no fim do ciclo, 20 ms depois. A causa exata ainda é hipótese (deslocamento de um ponto na TRACE, que leva a amostra 0 para o fim do ciclo). A validação física não detectou porque exclui justamente os dois ciclos do impulso (`ciclos_excluidos_da_validacao`).

Proposta 2 do `atividade.tex`: "Tirar o impulso da fronteira de ciclo (ou sortear sua posição, item 3) e recapturar a 08 a 127 V/50 Hz, conferindo a posição na validação. A 230 V, recapturar rende pouco: o maior impulso que cabe é de 0,74 pu, com pico de ≈ 1,15 pu." Comentário do professor: "deslocando o impulso esperado em 20 ms, a correlação do distúrbio sobe de 0,005 para 0,6, e o resto é a filtragem da fonte. Concordo em documentar a 08 como 'impulso filtrado pela fonte'. A campanha separada a ≈ 30 V fica como opcional."

Autorização do dono (2026-10-12): esta spec pode mudar o que `gerar()` da 08 produz para uma dada seed, como parte da mesma versão congelada.

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- `experimentos_waveform/08.py` (`INICIO_IMPULSO_S = 0.080`, `_indices_impulso`, `forma_para_bancada`, `ciclos_excluidos_da_validacao`), `logica/ametek_orm.py` (`program_capture`, `_resample_cycle`, corte em ciclos), validação física em `logica/mestre.py`
- Sessão: `resultados/sessao_2026-10-07_127V_50Hz` (capturas da 08) e `resultados/sessao_2026-10-07_14-59-54_run02` (08 a 60 Hz); figura `C:\Users\denis\Downloads\tcc\02\img\fig_transiente_08.png`
- Sorteio de início implementado pela spec da qual esta depende
- Testes: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`
- Depende de: ASD: Início, Duração e Fase Sorteados no gerar()
- Executor: sonnet

## Missão

1. Reproduzir offline, com a função de montagem da TRACE do projeto, por que um impulso na amostra 0 de um ciclo a 50 Hz vai parar no fim do ciclo, e confirmar ou refutar a hipótese do deslocamento de um ponto. Se a causa estiver na montagem (e não na fonte), corrigir lá.
2. Garantir em `gerar()` da 08 que o impulso nunca caia a menos de N amostras de uma fronteira de ciclo, para 50 e 60 Hz (escolher N e justificar), compatível com o início sorteado.
3. Fazer a validação física da 08 conferir a posição do impulso (pico medido dentro de uma tolerância do previsto), em vez de só excluir os ciclos.
4. Documentar a 08 como "impulso filtrado pela fonte" no `README`/`docs`, com as três limitações (amplitude, tempo de subida de 200 µs, representação em 1024 pontos).
5. Escrever o roteiro de recaptura da 08 a 127 V/50 Hz para o operador (comandos da CLI, confirmações, o que conferir), sem executá-lo.

## Limites

- Pode alterar: `experimentos_waveform/08.py`, `logica/ametek_orm.py` (só se a causa estiver na montagem da TRACE; a sequência SCPI só muda nos pontos da TRACE), `logica/mestre.py` (só validação da 08), `tests/test_offline.py`, `CHANGELOG/v1.15.md`, documentação.
- Não mudar `SOBRESSINAL_DO_DEGRAU`, `fracao_teto_pico_medido`, `exige_medida_de_pico` nem limites de tensão (`AGENTS.md`, "Limites inegociáveis").
- Não executar a recaptura; não tocar no hardware. Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/analise-2026-10-12/classe08_fronteira.md`, uma seção por item da Missão.
- Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

A causa do deslocamento está explicada (ou NÃO VERIFICADO com motivo), há teste mostrando que o impulso nunca cai na fronteira a 50 e 60 Hz, a validação confere a posição, e o roteiro de recaptura está escrito.
