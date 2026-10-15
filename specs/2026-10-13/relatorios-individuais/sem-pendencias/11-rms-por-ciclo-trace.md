## Análise do orquestrador

- Implementação completa? Sim: rms CA (ametek_orm.py, cycle_ca), pico previsto pela TRACE enviada escalada ao LIST:VOLTage, _resample_cycle periódico; diff conferido; merge com a 12 (conflito só no CHANGELOG, unido).
- Pendências do usuário: nenhuma bloqueante. Achado: resta a média por ciclo (0,24–0,33 pu nas 10/11/12/16); compensar exigiria offset por passo (ACDC) — sugestão.
- Escopo limitado demais? Não.
- Resolve o contexto? Sim para a segurança (pico não subestima); parcialmente para a fidelidade (média do ciclo continua perdida, por física da fonte).
- Critério de Parada: atendido (379 testes no merge, só as 4 conhecidas).
- Classificação: sem pendências.

---

# Relatório: ASD: RMS por Ciclo da TRACE sem a Média e Previsão de Pico Correta

Branch: `worktree-agent-a578ed08e56e21986`. Commit: `0a405e3` (fix: LIST:VOLTage com rms CA do ciclo, previsão de pico da TRACE escalada e ciclo fechado em _resample_cycle).

## Missão, item a item

**Item 1 — Calcular o `LIST:VOLTage` de cada ciclo com o rms da componente CA do ciclo (sem a média), para que a forma emitida tenha a amplitude CA do modelo; manter o tratamento de `dc_offset_pu`.**
- Status: CUMPRIDO
- Explicação: `logica/ametek_orm.py` (`montar_programacao`, ~linhas 1372-1385): `cycle_ca = cycle - np.mean(cycle)`; `voltage_rms = base·√2·rms(cycle_ca)`. O `dc_offset_pu` continua subtraído do ciclo e somado ao pico (`pico_dc_v`), inalterado. Teste `RmsCaEPicoPrevistoTests.test_list_voltage_e_o_rms_da_componente_ca_do_ciclo` confere `LIST:VOLTage == base·√2·std(ciclo)` e que é menor que o rms com média. Ressalva: a amplitude CA do modelo é recuperada; a MÉDIA de cada ciclo continua perdida (a fonte a remove da TRACE e o `SOURce:VOLTage:OFFSet` é único para a captura), o que domina o erro residual das classes 10, 11, 12 e 16 (ver item 4).

**Item 2 — Fazer a previsão de pico refletir o que a fonte emite (pico da TRACE normalizada escalada ao rms programado) e provar com teste que ela não subestima o pico de `programada_pu()` em formas com degrau no meio do ciclo (classes 10, 11, 12, 16).**
- Status: CUMPRIDO
- Explicação: `montar_programacao` (~linhas 1388-1405): `cycle_peak_v = max|TRACE enviada| · LIST:VOLTage enviado / rms(TRACE enviada)` (+ `pico_dc_v`), sobre os números já arredondados a `%.8g` (sem o arredondamento, a diferença de ~1e-7 V fazia o teste falhar). Alimenta `pico_acumulado_v`, `pico_reconstruido_v` e `last_programmed_peak_v`; `program_capture` e `mestre.py` não mudaram. Teste `test_pico_previsto_nao_subestima_o_pico_de_programada_em_degraus`: degraus sintéticos (nível 0,2/0,4/0,8; 50/60 Hz) e `gerar()` das classes 10, 11, 12, 16 (50/60 Hz, sorteio on/off), bases 127 e 230 V: previsto ≥ pico de `programada_pu()` e < 1,01× dele. Prova do defeito antigo (módulo do HEAD, scratchpad/old_check.py): nos degraus sintéticos a previsão antiga dava 106,9-141,2 V contra 153,3-172,1 V emitidos (subestimava até 38 %). Observação: nas formas reais de `gerar()` das classes 10-12/16 (seed 32) a previsão antiga já coincidia (pico de 1,0 pu), então o ganho de segurança aparece nas formas de média diferente de zero com pico CA menor que o da média, como nos degraus.

**Item 3 — Fechar o ciclo em `_resample_cycle` (interpolação periódica) e ajustar a tolerância do teste da senoide pura para o novo erro.**
- Status: CUMPRIDO
- Explicação: `_resample_cycle` agora usa `np.interp(target_x, source_x, cycle, period=1.0)`. Erro da senoide pura: 9,1·10⁻⁶ (50 Hz) e 1,3·10⁻⁵ (60 Hz) pu (antes até 1,3·10⁻³). `test_programada_de_senoide_pura_e_a_senoide` passou de `atol=2e-3` para `atol=1e-4`, com o comentário atualizado.

**Item 4 — Quantificar, com as formas de `gerar()` (sorteio ligado, 50 e 60 Hz), quanto a programada passou a se aproximar do modelo (máx |programada − modelo| antes e depois, por classe TRACE).**
- Status: CUMPRIDO
- Explicação: script `scratchpad/medir11.py` (seed 32, 50 Hz/127 V e 60 Hz/230 V), saídas em `antes11.txt` e `depois11.txt`. Máx |programada − modelo| em pu:

| classe | 50 Hz antes | 50 Hz depois | 60 Hz antes | 60 Hz depois |
|---|---|---|---|---|
| 06 | 0,0229 | 0,0218 | 0,0190 | 0,0187 |
| 07 | 0,1661 | 0,1661 | 0,1258 | 0,1258 |
| 08 | 0,8155 | 0,8152 | 0,5595 | 0,5597 |
| 09 | 0,0076 | 0,0076 | 0,0042 | 0,0048 |
| 10 | 0,3063 | 0,2613 | 0,3019 | 0,2429 |
| 11 | 0,3047 | 0,2735 | 0,3039 | 0,2420 |
| 12 | 0,3108 | 0,2657 | 0,3238 | 0,2524 |
| 13 | 0,1099 | 0,1138 | 0,0955 | 0,0912 |
| 14 | 0,0726 | 0,0822 | 0,0738 | 0,0729 |
| 15 | 0,0309 | 0,0301 | 0,0259 | 0,0253 |
| 16 | 0,4368 | 0,3300 | 0,3904 | 0,3039 |
| 17 | 0,2926 | 0,2925 | 0,2350 | 0,2350 |
| 20 | 0,0045 | 0,0168 | 0,0055 | 0,0085 |

  Melhora nas classes de degrau (10, 11, 12, 16): 0,04-0,11 pu. O que resta nelas é a média do ciclo (até 0,24-0,30 pu) que a fonte remove: contra o modelo sem a média do ciclo, o erro é 0,02-0,04 pu (`medir11b.py`). Piora pequena (0,004-0,012 pu) em 13 e 14 (50 Hz) e 20; hipótese (não confirmada ponto a ponto): erro máximo pontual dominado pela média removida, que a amplitude inflada de antes compensava em parte num ponto. A "aproximação ao modelo" real é limitada pela média do ciclo, não resolvida por esta spec.

**Item 5 — Registrar em `CHANGELOG/v1.15.md` (Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO), em `docs/scpi.md` e `docs/tres_versoes.md`.**
- Status: CUMPRIDO
- Explicação: nova seção no fim de `CHANGELOG/v1.15.md` (com a tabela e as seções pedidas), `docs/scpi.md:88` e `docs/tres_versoes.md` (descrição da função, `programada_pu` e previsão de pico) atualizados; docstring de `montar_programacao` ajustada.

## Critério de Parada
Atendido.
- Teste novo de pico previsto ≥ pico de `programada_pu()` com degrau a meio ciclo: passa.
- `LIST:VOLTage` sai do rms CA (teste acima).
- `test_funcao_pura_gera_byte_a_byte_o_que_program_capture_envia` passa.
- `TMPDIR=/tmp/claude-0/tmpt /tmp/claude-0/venv/bin/python -m unittest tests.test_offline`: `Ran 373 tests ... FAILED (failures=4)`, as 4 conhecidas de fixture (test_05_07_17_18_sem_sorteio_reproduzem_34a0d82, test_literatura_reproduz_byte_a_byte_o_gerar_do_commit_34a0d82, test_norma_e_fronteira_mudam_so_o_que_a_spec_manda, test_resultado_congelado_da_v1_15); nenhuma falha nova (3 testes novos passam).

## Pendências que exigem o usuário
Nenhuma.

## Limitações de escopo
Não alterar `gerar()` e não tocar no hardware impedem recuperar a média de cada ciclo e confirmar a resposta real da fonte; o erro residual das classes 10, 11, 12 e 16 vem dessa média.

## A missão resolve o contexto?
Parcialmente: a amplitude CA inflada e a previsão de pico subestimada foram corrigidas, mas o erro das classes de degrau cai só de ~0,3-0,44 para ~0,24-0,33 pu porque a média de cada ciclo é removida pela fonte. Uma abordagem melhor seria compensar a média por ciclo (não há comando por passo de LIST para offset DC; a verificar no manual), ou aceitar que a "programada" fiel a ela é o modelo sem a média do ciclo.

## Achados
- (média) Erro residual dominado pela média de cada ciclo nas classes 10, 11, 12, 16 (até 0,24-0,30 pu); inerente à TRACE sem DC.
- (baixa) Em 13/14 (50 Hz), 20 e 09 (60 Hz) o máx |programada − modelo| subiu 0,0006-0,012 pu; hipótese em item 4, NÃO verificada.
- (baixa) A previsão antiga já coincidia com o pico nas formas reais das classes 10-12/16 desta seed (pico 1 pu); a subestimação só aparece em degraus onde o pico CA diferente do pico absoluto.
- (informativo) A previsão passou a usar valores em `%.8g` (os que a fonte recebe), para ser ≥ `programada_pu()` sem margem artificial.
- (informativo) As instruções de commit do bloco comum (Claude Opus 5.5) divergem do lembrete de atribuição da sessão (Sonnet 5.5); segui o bloco comum da spec.
- NÃO VERIFICADO: resposta real da fonte (escala ao rms CA, VMAX/VMIN medidos); só a bancada de 14/10 confirma.
