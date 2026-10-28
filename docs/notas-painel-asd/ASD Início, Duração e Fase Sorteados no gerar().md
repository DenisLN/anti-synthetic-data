#spec #pri 5

# ASD: Início, Duração e Fase Sorteados no gerar()

## Contexto

O distúrbio cai sempre na mesma posição (60 ms, ou 80 ms na 08/09) e com a mesma fase. O professor contou as formas distintas em 2000 capturas simuladas: 1 forma em 01 e 10–16, 2 na 18, 5 em 02, 03 e 05. "Em 11 das 20 o conjunto simulado vira cópias da mesma onda [...] Um classificador acerta por memorização." Comentário da Pergunta 7: "é a prioridade número 1 da próxima versão. Junto com ela, sorteiem a duração nas classes de evento (sag, swell e interrupção podem ir de meio ciclo até onde a janela permitir) e gravem no metadata o início, a duração e a fase sorteados."

Proposta 3 do `atividade.tex`: "Em `gerar()`, com a mesma seed: início t0 ~ U(tmin, 200 ms − d − tmin) e fase da senoide base φ ~ U(0°, 360°). Nas classes TRACE qualquer início é reproduzível, porque a TRACE carrega o detalhe dentro do ciclo. Custo: cada captura passa a gravar a Flash (≈ 20 s), e a contagem de gravações por conexão sobe (a fonte já travou na ~280.ª). Nas classes de pulso, sortear a fase de disparo (`TRIGger:SYNChronize:PHASe`, resolução de 0,1°) e o `pre_trigger_s`, reconfigurando o osciloscópio a cada captura." Item d) da lista final: gravar no metadata o início da janela, início, duração e fase sorteados.

Autorização do dono (2026-10-12): esta spec pode mudar o que `gerar()` produz para uma dada seed, como parte da mesma versão congelada das outras mudanças de `gerar()`.

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- Classes: `experimentos_nativos/*.py`, `experimentos_waveform/*.py`; pulso: `logica/ametek_orm.py` (`trigger_pulse`, `TRIGger:SYNChronize:PHASe`); osciloscópio: `logica/oscilloscope_orm.py`; `pre_trigger_s` e margens em `logica/mestre.py`; recorte: `logica/recortar_margem.py`
- Cache de TRACe e contagem de gravações: `program_capture()` em `logica/ametek_orm.py`; estimativa de gravações mostrada pelo `run all` em `logica/cli.py`
- Testes: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`
- Depende de: ASD: Perfis de Faixas Norma, Literatura e Fronteira
- Executor: sonnet

## Missão

1. Sortear em `gerar()`, com o rng da seed, o início, a duração (classes de evento: de meio ciclo até onde a janela permitir) e a fase da senoide base, em todas as classes em que fizer sentido; listar e justificar as que ficam de fora (ex.: 01 só fase).
2. Nas classes de pulso (02, 03, 04), programar a fase de disparo e ajustar o `pre_trigger_s` do osciloscópio por captura para que a captura física reproduza o `gerar()`.
3. Gravar no metadata `inicio_disturbio_s`, `duracao_s` e `fase_graus`, e manter `inicio_janela` correto com o `pre_trigger_s` variável.
4. Atualizar a estimativa de gravações de TRACe do `run all` e o aviso ao operador para o fato de que cada captura TRACE passa a gravar a Flash; propor (sem implementar) como lidar com o limite de ~280 gravações por conexão.
5. Cobrir com testes: mesma seed → mesma forma; seeds diferentes → início/fase diferentes; o recorte de `recortar_margem.py` acerta a janela com `pre_trigger_s` variável.

## Limites

- Pode alterar: `experimentos_nativos/*.py`, `experimentos_waveform/*.py`, `logica/mestre.py`, `logica/ametek_orm.py` (só a fase de disparo), `logica/oscilloscope_orm.py` (só pré-trigger), `logica/cli.py`, `logica/recortar_margem.py`, `tests/test_offline.py`, `CHANGELOG/v1.15.md`, documentação.
- Não mudar as faixas de amplitude (são da spec de perfis) nem a posição especial do impulso da 08 (outra spec).
- Não mexer no cache de TRACe nem nas validações (`AGENTS.md`, "Limites inegociáveis").
- Não tocar no hardware. Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/analise-2026-10-12/sorteio_inicio_fase.md`, uma seção por item da Missão, com tabela classe × o que é sorteado × faixa.
- Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

Os campos sorteados aparecem no metadata de uma sessão simulada, os testes do item 5 passam e a estimativa do `run all` reflete as gravações por captura.
