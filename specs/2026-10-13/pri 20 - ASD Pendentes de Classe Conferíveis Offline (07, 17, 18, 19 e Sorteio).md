#spec #pri 20

# ASD: Pendentes de Classe Conferíveis Offline (07, 17, 18, 19 e Sorteio)

## Contexto

Os relatórios pendentes `classes_05_07_18_VERIFICAR.md`, `sorteio_inicio_fase_VERIFICAR_BANCADA.md` e `acdc_amplitude_VERIFICAR.md` (branch `arquivo/analises`) deixaram itens que só a bancada fecha, mas parte deles pode ser preparada ou reduzida offline, para a bancada de 14/10 só confirmar:

- 07/17 com entalhes em todos os ciclos (~36 por captura): a tolerância da validação física (envelope/THD) nunca foi testada com tantos entalhes; o THD esperado da 07 subiu.
- 18: a 50 Hz a deriva agora é 47 → 53 Hz; a continuidade de fase na troca de passo não foi verificada.
- 19 (ACDC): CA 5–6 % abaixo do programado; `diag_acdc_amplitude.py` pronto e nunca executado; `measure_voltage()` devolve rms total em ACDC (sem uso hoje); `enable_dc_offset()` reenvia `SOURce:MODE ACDC` a cada captura (inócuo, ~0,3 s).
- Sorteio: largura de `PULSe:WIDTh` de 8 a 166 ms, disparo sincronizado em fase de LIST/CSINe/ACDC, `pre_trigger_desvio_amostras` (nunca medido), fatores de extremo medidos com fase fixa.

## Entradas

- `experimentos_waveform/07.py`, `17.py`, `experimentos_nativos/18.py`, `19.py`, `logica/mestre.py` (`_validar_fisicamente`, `pre_trigger_desvio_amostras`), `logica/ametek_orm.py` (`measure_voltage`, `enable_dc_offset`), `scripts/diag_acdc_amplitude.py`, `logica/sinais.py` (`forma_programada_nativa`)
- Depende de: ASD: RMS por Ciclo da TRACE sem a Média e Previsão de Pico Correta

## Missão

1. Rodar offline a validação física da 07 e da 17 tendo como "medida" a forma programada, e a mesma forma com os entalhes atenuados por um filtro de 2.ª ordem de ~10 kHz (resposta da fonte medida em 07/10), e reportar se alguma captura seria reprovada; se for, propor o ajuste sem aplicá-lo.
2. Escrever um verificador offline (função em `scripts/` ou no próprio `diag_ciclos_trace.py`) que, numa sessão real, mede a continuidade de fase da 18 na troca de passo, a largura medida do PULSe (02–04) contra a programada e o `pre_trigger_desvio_amostras`, para rodar logo depois da bancada.
3. Documentar em `logica/ametek_orm.py` (comentário) que `measure_voltage()` em ACDC devolve rms total, e confirmar com teste que `diag_acdc_amplitude.py --simulado` continua passando.
4. Listar, para o roteiro de bancada, cada item que só a bancada fecha, com o comando exato, o que olhar e o critério de aprovação.

## Limites

- Não afrouxar tolerâncias de validação nem limites; só reportar e propor.
- Não mudar a sequência SCPI das classes 18 e 19.
- Não tocar no hardware.

## Entregável

- Relatório por item, com a lista do item 4 pronta para o roteiro.
- Verificação: `python -m unittest tests.test_offline`.

## Critério de Parada

O resultado do item 1 está no relatório com número por captura; o verificador do item 2 roda numa sessão sintética (teste); a lista do item 4 cobre os três relatórios pendentes; suíte sem falha nova.
