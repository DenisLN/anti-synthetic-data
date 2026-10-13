#spec #pri 15

# ASD: Diagnóstico da Cópia do Evento em 100 ms (Classes 08 e 09)

## Contexto

Nas capturas de 07/10 o início do evento aparece repetido ou deslocado, sempre em 100,0 ms da janela:

- 08 a 50 Hz: impulso programado em 80 ms (ponto 0 do 5.º ciclo) saiu em 100 ms; nada em 80 ms (3 de 3 capturas).
- 09 a 50 Hz: a oscilação que começa em 80 ms some ali e aparece em 100 ms.
- 09 a 60 Hz: aparece em 80 ms (no meio do ciclo, amostra 400 de 500) **e** uma cópia menor (0,04–0,18 pu) sai em 100 ms, que a 60 Hz é o início do 7.º ciclo, não um ponto 0 do ciclo do evento.
- Em 9 de 9 capturas da 09 há um impulso de 0,12–0,27 pu em 100,0–100,2 ms que a forma programada não tem. Gravidade alta: é defeito do dado, não só da métrica.

A montagem da TRACE está descartada como causa (`montar_programacao` põe o impulso onde foi pedido; teste `test_montagem_da_trace_nao_desloca_o_impulso_a_50_nem_a_60hz`). A hipótese "um ponto da TRACE" foi refutada pelos dados. `_resample_cycle` sem fechar o ciclo (erro de 1,3·10⁻³ pu nos 2 últimos pontos) também não explica 0,27 pu 20 ms depois. O fato de a cópia cair num **instante fixo** (100 ms) nas duas frequências, e não num ponto fixo do ciclo, sugere um mecanismo ligado ao tempo ou à troca de passos do LIST (ex.: a fonte tocar o passo k+1 com a forma do passo k a partir de certo instante). O usuário quer **diagnosticar e prever** o comportamento da fonte, não só contornar.

Na 08 a mudança da v1.15 (impulso a 90 ms a 50 Hz, longe da fronteira, e a validação física conferindo a posição) contorna o sintoma; a 08 não sorteia posição nem fase (calibração do sobressinal). A 09 sorteia início e fase, então a cópia pode cair em qualquer lugar.

As sessões de 07/10 (`resultados/`) só existem no PC da bancada; esta spec entrega ferramentas que rodam lá amanhã.

## Entradas

- `logica/ametek_orm.py` (`montar_programacao`, `ProgramacaoCaptura`, `program_capture`), `logica/mestre.py`, `logica/oscilloscope_orm.py`, `logica/recortar_margem.py`
- Formato das sessões: `.npz` da captura + `metadata/NN_*.jsonl` (`indice_trigger`, `inicio_janela`, `seed`, `parametros`), `tres_versoes/` (`programada_pu`); reconstrução offline: `scripts/gerar_tres_versoes.py` (`reconstruir_versoes`)
- Modelos de script de bancada com confirmação: `scripts/diag_acdc_amplitude.py`, `scripts/diag_fonte_vs_osciloscopio.py`
- Depende de: ASD: RMS por Ciclo da TRACE sem a Média e Previsão de Pico Correta

## Missão

1. Escrever `scripts/diag_ciclos_trace.py` (offline, só leitura): para cada captura TRACE de uma sessão, comparar cada ciclo medido (alinhado em `inicio_janela`) com os ciclos programados k−1, k e k+1 e com o ciclo k da forma programada sem DC, e listar por captura qual ciclo programado explica melhor cada ciclo medido, a partir de que instante há troca e a amplitude do resíduo em 100 ms. Saída em texto/markdown legível e JSON.
2. Escrever `scripts/diag_marcadores_trace.py` (bancada): uma captura TRACE em que cada ciclo tem um marcador único (posição e amplitude diferentes por ciclo, tudo dentro dos limites de pico), a 50 e 60 Hz e na tensão base, que identifica na medida qual forma saiu em cada ciclo e mede o atraso; reaproveitar `program_capture`, o ORM do osciloscópio e as validações; confirmação digitada `ENERGIZAR-MARCADORES`; `--simulado` para testar o fluxo.
3. Acrescentar ao script do item 2 a variante com o evento na fronteira e a variante com o evento a meio ciclo (os dois casos de 07/10), para separar "ponto 0" de "instante fixo".
4. Escrever um modelo preditivo provisório (função pura) que, dada a programação e uma hipótese de mecanismo, devolve a forma que a fonte emitiria; deixar as hipóteses candidatas parametrizadas, para serem confrontadas com o resultado do item 2 na bancada.
5. Documentar uso e leitura dos resultados em `docs/diagnostico.md` e o comportamento observado em `docs/quirks.md` (como NÃO VERIFICADO até a bancada).

## Limites

- Os scripts de bancada não podem rodar sem confirmação digitada nem relaxar `max_voltage_rms`/`max_peak_v`/`max_current_a`; sem `BENCH_MODE=1` só `--simulado`.
- Nunca consultar a fonte logo após `TRACe:DATA` (achado da v1.12).
- Não mudar `gerar()` nem `montar_programacao` nesta spec.
- Não tocar no hardware (a execução fica para o roteiro de bancada).

## Entregável

- Relatório por item; `scripts/diag_ciclos_trace.py`, `scripts/diag_marcadores_trace.py`.
- Verificação: `python -m unittest tests.test_offline` com testes novos (sessão sintética com um ciclo deslocado de propósito: o script do item 1 o detecta; `--simulado` do item 2 roda e o marcador de cada ciclo é recuperado).

## Critério de Parada

Os dois scripts existem; o teste sintético mostra o item 1 detectando o ciclo trocado e o instante; `diag_marcadores_trace.py --simulado` termina e recupera os marcadores; suíte sem falha nova.
