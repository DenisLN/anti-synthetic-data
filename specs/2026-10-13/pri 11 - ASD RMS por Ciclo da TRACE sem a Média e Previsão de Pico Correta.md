#spec #pri 11

# ASD: RMS por Ciclo da TRACE sem a Média e Previsão de Pico Correta

## Contexto

`AmetekMX30.montar_programacao` (`logica/ametek_orm.py:1366-1380`) calcula o `SOURce:LIST:VOLTage` de cada ciclo com o rms do ciclo **com a média** (`cycle_rms_pu = sqrt(mean(cycle²))`), mas envia a TRACE **sem a média** (`trace -= mean(trace)`). Pelo manual (p. 126) a fonte remove a componente DC da TRACE e a escala para o rms programado: a forma sem DC sai escalada para um rms maior que o dela, ou seja, a amplitude CA do ciclo sai inflada. Medido nas sessões de 07/10 (relatório das três versões): máx |programada − modelo| de 0,18–0,43 pu nas classes 10, 11, 12, 16, e a medida segue a programada.

Consequência de segurança: a previsão de pico (`cycle_peak_v = scale · base · √2`) ignora esse reescalonamento e **subestima** o pico real nos ciclos com média ≠ 0. Hoje só a conferência pós-captura de VMAX/VMIN protege.

Junto, a mesma função tem um defeito menor: `_resample_cycle` (`:1316-1319`) usa `np.interp` sem fechar o ciclo, e os ~2 últimos dos 1024 pontos repetem a última amostra (erro até 1,3·10⁻³ pu). Corrigir agora aproveita a mesma mudança de SCPI.

Decisão do usuário (2026-10-13): corrigir antes da bancada de 14/10. Não muda `gerar()` (dataset); muda o que é programado na fonte e a forma programada.

## Entradas

- `logica/ametek_orm.py`: `_resample_cycle`, `montar_programacao`, `ProgramacaoCaptura.programada_pu`, `program_capture`
- `tests/test_offline.py`: `TresVersoesTests` (`test_programada_de_senoide_pura_e_a_senoide`, `test_funcao_pura_gera_byte_a_byte_o_que_program_capture_envia`)
- Previsão de pico usada pela pré-validação: `last_programmed_peak_v` / `pico_acumulado_v` e quem os lê em `logica/mestre.py`
- Verificação: `python -m unittest tests.test_offline`
- Depende de: nada

## Missão

1. Calcular o `LIST:VOLTage` de cada ciclo com o rms da componente CA do ciclo (sem a média), para que a forma emitida tenha a amplitude CA do modelo; manter o tratamento de `dc_offset_pu`.
2. Fazer a previsão de pico refletir o que a fonte emite (pico da TRACE normalizada escalada ao rms programado) e provar com teste que ela não subestima o pico de `programada_pu()` em formas com degrau no meio do ciclo (classes 10, 11, 12, 16).
3. Fechar o ciclo em `_resample_cycle` (interpolação periódica) e ajustar a tolerância do teste da senoide pura para o novo erro.
4. Quantificar, com as formas de `gerar()` (sorteio ligado, 50 e 60 Hz), quanto a programada passou a se aproximar do modelo (máx |programada − modelo| antes e depois, por classe TRACE).
5. Registrar em `CHANGELOG/v1.15.md` (Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO), em `docs/scpi.md` e `docs/tres_versoes.md`.

## Limites

- Não mudar `max_voltage_rms`, `max_peak_v`, `max_current_a`, a pré-validação de pico (só passar a alimentá-la com o valor correto), as validações de 6000 pontos/IDN/SCPI, nem o cache de TRACe (a assinatura muda naturalmente com o conteúdo).
- Não mudar `gerar()`.
- Não tocar no hardware.

## Entregável

- Relatório por item (formato do template), com a tabela do item 4.
- Verificação: `python -m unittest tests.test_offline` (saída no relatório).
- Evidência com arquivo:linha ou comando e saída; NÃO VERIFICADO quando não confirmado (a resposta real da fonte só a bancada confirma).

## Critério de Parada

Teste novo mostra o pico previsto ≥ pico de `programada_pu()` em formas com degrau a meio ciclo; o `LIST:VOLTage` sai do rms CA; o teste byte a byte função-pura × `program_capture` passa; a suíte offline não tem falha nova.
