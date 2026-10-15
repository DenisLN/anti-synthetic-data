## Análise do orquestrador

- Implementação completa? Sim: comparar_fisicamente com fator_crista (aceita [modelo×0,9, modelo×fator×1,1]), fator = o da previsão de pico sem margem (08 fica em 1,0), campos novos em validacao_fisica, 6 testes; merge limpo, suíte OK.
- Pendências do usuário: a 127 V/60 Hz os fatores calibrados (07 1,186; 17 1,031) não cobrem o toque simulado (precisaria ~1,34–1,42): a 1.ª captura da 07/17 a 60 Hz deve reprovar e a recalibração só vale para o run seguinte. Efeito colateral: em condição sem tabela (1,475) o teto da crista afrouxa para ~1,62×.
- Resolve o contexto? Sim, condicionado à recalibração.
- Critério de Parada: atendido. Classificação: com pendências.

---

# Relatório: ASD: Crista Esperada da Validação Física com o Fator de Extremo Calibrado

Branch: `worktree-agent-aafca8c79e79ae042`. Commit: `006cdfe` (feat: crista da validação física usa o fator de extremo calibrado da classe). Merge prévio de `claude/specs-v1-15-review-3w2bgl` feito. Não toquei em `executar_bateria`, `set perfil todos`, `sessao_io` nem na gravação. Scripts da medida: `.../scratchpad/spec26/fatores.py`.

## Missão, item a item

**Item 1 — Fazer a conferência da crista usar como esperado a crista do modelo multiplicada pelo fator de extremo efetivo da classe na condição da captura (o mesmo que a previsão de pico usou nessa captura, inclusive a regra por frequência e o caso sem tabela), aplicado a TODAS as classes; manter a tolerância de 10 % sobre esse esperado. A comparação continua bilateral? Decidir e justificar: com o fator, a medida pode ficar entre a crista ideal e a crista × fator (a fonte pode tocar menos do que o máximo calibrado) — o critério deve aceitar qualquer valor em [crista_modelo × (1 − tol), crista_modelo × fator × (1 + tol)] e reprovar fora disso.**
- Status: CUMPRIDO
- Explicação: `sinais.comparar_fisicamente(..., fator_crista=1.0)` (`logica/sinais.py:359`, lógica em `:429`) aceita `[crista_modelo × 0,9, crista_modelo × fator × 1,1]`; sim, continua bilateral (justificativa: a fonte pode tocar menos que o máximo calibrado; o limite inferior segue pegando forma achatada/atenuada). `ExperimentoBase.fator_extremo_efetivo_para_validacao` (`logica/mestre.py:1872`) devolve o mesmo fator da previsão (`fator_extremo_da_classe(id, _fatores_extremo())`: regra por frequência, condição sem tabela, classe fora da tabela), sem a `MARGEM_FATOR_EXTREMO` (a folga é a tolerância de 10 %). Com distúrbio reduzido pelo limite de bancada usa a fórmula de `extremo_previsto_com_disturbio_v` com margem 1 (a partir de `_avaliacoes_bancada`, passado por `_validar_fisicamente`, `:1803/:1854`, e pela chamada em `_capturar_real`). Aplica-se a todas as classes; exceção deliberada: classe com `excursao_fisica_prevista_v()` não nulo (08) usa 1,0, porque o impulso é excluído da crista e a tabela não a representa (a previsão de pico também usa o modelo próprio dela). Descoberta durante a implementação: `ExperimentoWaveform` define `excursao_fisica_prevista_v` devolvendo `None`, então a checagem é por valor não nulo, não por `callable`. Fator 1,0 reproduz a comparação antiga.

**Item 2 — Gravar no metadata da captura, em `validacao_fisica`, a crista do modelo, o fator usado e a crista medida (só acrescentar campos; `docs/metadata.md`).**
- Status: CUMPRIDO
- Explicação: novos campos em `validacao_fisica`: `crista_modelo`, `fator_extremo_crista`, `crista_minima_aceita`, `crista_maxima_aceita` (`crista_medida` e `crista_esperada` já existiam, inalterados). Documentado em `docs/metadata.md` (nova linha antes de `git_commit`).

**Item 3 — Testes: a 07 com entalhes em todos os ciclos e o toque simulado (filtro de 2.ª ordem com fn 10 kHz, ζ 0,2, como na spec 20) passa quando o fator calibrado cobre o toque e reprova quando o fator é 1,0; classes sem sobressinal (fator ~1) não mudam de veredito; captura com crista acima de crista × fator × 1,1 continua reprovada; o fator é o mesmo da previsão de pico.**
- Status: CUMPRIDO
- Explicação: `CristaComFatorDeExtremoTests` no fim de `tests/test_offline.py` (6 testes): 07 (60 Hz, 3 capturas) com toque passa com 1,5 e reprova com 1,0 (motivo "fator de crista"); sem toque o veredito é o mesmo com fatores 1,0/1,186/1,5 e os limites são 0,9 e fator × 1,1; crista acima de crista × fator × 1,1 reprova, pico achatado reprova mesmo com fator, fator 1,0 reproduz o simétrico; fator igual ao da previsão (inclusive `_extremo_previsto_da_forma_v`, classe fora da tabela, condição 127 V/50 Hz, distúrbio reduzido); 08 usa 1,0. Os testes antigos de `_validar_fisicamente` seguem passando.

**Item 4 — Medir offline, com o mesmo modelo de toque da spec 20, que fator a 07 e a 17 precisariam (por frequência) e comparar com o calibrado (1,180 e 1,017): escrever no relatório e no CHANGELOG o que se espera amanhã (se a primeira captura deve reprovar e a recalibração automática corrigir).**
- Status: CUMPRIDO
- Explicação: filtro de 2.ª ordem, banda fn 9/10/11 kHz × ζ 0,1/0,2/0,3, 127 V, 15 capturas por combinação (135 por linha). Razão = crista medida ÷ crista do modelo; fator mínimo = máx ÷ 1,1.

| classe / f0 | fator calibrado (JSON) | razão mediana / p95 / máx | fator mínimo (máx ÷ 1,1) | fator p/ 95 % (p95 ÷ 1,1) | aprovadas com o calibrado | aprovadas com 1,0 |
|---|---|---|---|---|---|---|
| 07 / 60 Hz | 1,186 | 1,312 / 1,423 / 1,479 | 1,344 | 1,293 | 58/135 | 0/135 |
| 07 / 50 Hz | 1,375 | 1,312 / 1,435 / 1,510 | 1,373 | 1,305 | 135/135 | 0/135 |
| 17 / 60 Hz | 1,031 | 1,314 / 1,443 / 1,562 | 1,420 | 1,312 | 0/135 | 0/135 |
| 17 / 50 Hz | 1,307 | 1,314 / 1,424 / 1,536 | 1,397 | 1,295 | 130/135 | 0/135 |

  Os valores do JSON hoje são 1,186 (07) e 1,031 (17) a 127 V/60 Hz, não 1,180/1,017 (texto antigo do CHANGELOG). Expectativa para amanhã a 127 V/60 Hz: a primeira captura de 07 e 17 deve reprovar pela crista se a fonte tocar como o modelo (razão ~1,31 contra 1,186 × 1,1 = 1,30 na 07 e 1,031 × 1,1 = 1,13 na 17); a 50 Hz os fatores calibrados cobrem quase tudo. A recalibração automática (`set recalibracao on`) roda ao FIM do run e só sobe fatores, então corrige o JSON para o run seguinte, não as capturas do mesmo run. Fica em `CHANGELOG/v1.15.md` (seção nova no fim).

**Item 5 — Registrar em `CHANGELOG/v1.15.md` (seção nova no fim), `docs/limites_e_calibracao.md` (a calibração passa a servir também à validação) e `docs/decisoes.md`.**
- Status: CUMPRIDO
- Explicação: seção "Crista esperada da validação física com o fator de extremo calibrado (2026-10-15, spec 26)" no fim de `CHANGELOG/v1.15.md` (Por quê / O que mudou / expectativa e tabela / O que não mudou / Testes / NÃO VERIFICADO); parágrafo novo em `docs/limites_e_calibracao.md` §4; linha em `docs/decisoes.md` (Segurança e hardware).

## Critério de Parada
Atendido. Crista esperada usa o fator efetivo (`test_fator_e_o_mesmo_da_previsao_de_pico`, `test_07_..._reprova_com_1`); campos novos no metadata; `TMPDIR=/tmp/claude-0/tmpt /tmp/claude-0/venv/bin/python -m unittest tests.test_offline` -> `Ran 486 tests ... OK (skipped=2)` (0 falhas).

## Pendências que exigem o usuário
Nenhuma. (Decisão informativa: a 60 Hz a primeira bateria de 07/17 provavelmente reprova pela crista; opção de recalibrar o JSON antes com `scripts/recalibrar_extremos.py` sobre uma sessão que o permita, ou aceitar a reprovação do 1.º run.)

## Limitações de escopo
O limite "não mudar `calibracao_extremos.json`" impede subir hoje 07/17 a 60 Hz para ~1,35/1,42; consequência prevista: reprovação no primeiro run até haver recalibração com dado real. Sem hardware, o toque real é só o modelo.

## A missão resolve o contexto?
Parcialmente: o critério passa a depender da calibração e só reprova o que ela não cobre, mas a calibração atual de 07/17 a 60 Hz (feita com 4 ciclos entalhados) é baixa demais segundo o modelo, então a validade da 1.ª captura depende de recalibrar com dado de bancada.

## Achados
- [média] A 07/17 a 127 V/60 Hz: fatores 1,186/1,031 não cobrem o toque simulado (ver tabela); a 17 a 60 Hz 0/135 aprovadas.
- [baixa] Condição sem tabela (ex. 220 V): fator conservador 1,475 afrouxa o limite superior da crista a ~1,62 × o modelo (o inferior não muda); efeito colateral inevitável de "o mesmo que a previsão de pico".
- [baixa] 08 usa fator 1,0 (decisão minha, ver item 1).
- [baixa] `ExperimentoWaveform.excursao_fisica_prevista_v` existe para todas as classes waveform (devolve `None`); `callable()` não serve para distinguir a 08.
- [info] Valores 1,180/1,017 citados no pedido divergem do JSON (1,186/1,031); vale o código.
- NÃO VERIFICADO: toque real da fonte com entalhes em todos os ciclos; se a recalibração leva o fator ao mínimo da tabela (sem bancada).
