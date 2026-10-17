# Estado de validação das 20 classes

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` {bdg-success}`VERIFICADO NA BANCADA` (código anterior à v1.15) {bdg-warning}`NÃO VERIFICADO` (v1.15) {bdg-danger}`PENDENTE P-01`

**Pergunta:** quanto de cada classe foi verificado, em que camada e com que código? **Resposta:** todas as 20 classes têm `gerar()` e programada conferidos **offline**; todas rodaram na **bancada em 127 V/60 Hz e 127 V/50 Hz** em 07/10/2026 e 15 delas também a 230 V/50 Hz; **mas esse código é o anterior à v1.15**: perfis, sorteio de início, duração e fase, compostas sorteadas, entalhes contínuos, a 08 a 90 ms e a crista com fator **nunca foram medidos**. Em 2026-10-16 a `main` está em `fa82f49` e a última campanha de bancada continua sendo a de 07/10/2026 (P-01).

O que cada selo exige está em {doc}`../como-ler`. Esta página não afirma que o passo final SINE existe: ele está fora da `main` ({doc}`passo-final-sin`).

## 1. Camadas de verificação e a fonte de cada célula

| Camada | O que é | Fonte |
|---|---|---|
| Offline | `gerar()` determinístico e a suíte de testes: duas fixtures byte a byte de 400 entradas (20 por classe): `gerar_literatura_34a0d82.json` (o `gerar()` do commit `34a0d82`, perfil `literatura`, sorteio desligado) e `gerar_sorteio_v1_15.json` | `tests/fixtures/`; suíte `tests/test_offline.py`: `Ran 497 tests in 115.362s`, `OK`, sem testes pulados (Windows 11, Python 3.11.9, 2026-10-16, `main` em `fa82f49` com a documentação do site ainda não commitada) |
| Dataset simulado | `python logica/mestre.py` sem `BENCH_MODE`: fonte e osciloscópio simulados, 20 classes | execução de 2026-10-16 neste worktree, `SIM_CAPTURES_PER_CLASS=3` |
| Programada | correlação do distúrbio entre o modelo e o que `montar_programacao`/`forma_programada_nativa` reconstroem | simulação offline, v1.15 padrão (sorteio ligado, `literatura`), seis capturas por frequência: {doc}`../medicao/correlacao` §4 |
| Bancada, 127 V/60 Hz | sessão `sessao_2026-10-07_14-59-54_run02` | 07/10/2026, 20/20 classes (`CHANGELOG/v1.14.md`); contagem de capturas lida do metadata |
| Bancada, 127 V/50 Hz | sessão `sessao_2026-10-07_127V_50Hz` | 07/10/2026, incluindo a 08 numa rodada à parte |
| Bancada, 230 V/50 Hz | sessão `sessao_2026-10-07_230V_50Hz` | 07/10/2026, 15 de 20 classes |
| Perfis | `norma`, `literatura`, `fronteira` | `perfis.py`; **nenhuma sessão de bancada** com perfil (P-01) |

## 2. Offline, simulado e programada

| Classe | Offline (`gerar()` e fixtures) | Dataset simulado | Programada (modelo × programada) |
|---|---|---|---|
| 01 NORMAL | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `01_normal.npz` | {bdg-info}`OFFLINE` n/a (degenerada) |
| 02 SAG | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `02_sag.npz` | {bdg-info}`OFFLINE` 1,000 |
| 03 SWELL | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `03_swell.npz` | {bdg-info}`OFFLINE` 1,000 |
| 04 INTERRUPTION | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `04_interruption.npz` | {bdg-info}`OFFLINE` 1,000 |
| 05 HARMONICS | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `05_harmonics.npz` | {bdg-info}`OFFLINE` 1,000 |
| 06 FLICKER | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `06_flicker.npz` | {bdg-info}`OFFLINE` 0,870–0,998 |
| 07 NOTCH | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `07_notch.npz` | {bdg-info}`OFFLINE` 0,993–0,996 |
| 08 TRANSIENT | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `08_transient.npz` | {bdg-info}`OFFLINE` 0,986–0,993 |
| 09 OSCILLATORY_TRANSIENT | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `09_oscillatory_transient.npz` | {bdg-info}`OFFLINE` 0,996–1,000 |
| 10 SAG_HARMONICS | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `10_sag_harmonics.npz` | {bdg-info}`OFFLINE` 0,963–1,000 |
| 11 SAG_FLICKER | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `11_sag_flicker.npz` | {bdg-info}`OFFLINE` 0,843–0,998 |
| 12 SAG_OSCILLATORY_TRANSIENT | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `12_sag_oscillatory_transient.npz` | {bdg-info}`OFFLINE` 0,938–0,998 |
| 13 SWELL_HARMONICS | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `13_swell_harmonics.npz` | {bdg-info}`OFFLINE` 0,950–0,999 |
| 14 SWELL_OSCILLATORY_TRANSIENT | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `14_swell_oscillatory_transient.npz` | {bdg-info}`OFFLINE` 0,925–0,999 |
| 15 HARMONICS_FLICKER | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `15_harmonics_flicker.npz` | {bdg-info}`OFFLINE` 0,966–0,995 |
| 16 INTERRUPTION_HARMONICS | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `16_interruption_harmonics.npz` | {bdg-info}`OFFLINE` 0,879–1,000 |
| 17 NOTCH_OSCILLATORY_TRANSIENT | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `17_notch_oscillatory_transient.npz` | {bdg-info}`OFFLINE` 0,993–0,996 |
| 18 FREQUENCY_DRIFT | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `18_frequency_drift.npz` | {bdg-info}`OFFLINE` 0,952–0,952 |
| 19 DC_OFFSET | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `19_dc_offset.npz` | {bdg-info}`OFFLINE` n/a (degenerada) |
| 20 INTERHARMONICS | {bdg-info}`OFFLINE` 20 + 20 entradas | {bdg-info}`OFFLINE` 3 captura(s) gravada(s), arquivo `20_interharmonics.npz` | {bdg-info}`OFFLINE` 0,991–0,999 |

"Programada" é a faixa da correlação do distúrbio modelo × programada com sorteio ligado (seis capturas por frequência, 50 e 60 Hz; sementes e método em {doc}`../medicao/correlacao`). Valores abaixo de 0,95 vêm da média de cada ciclo da TRACe (06, 10, 11, 12, 14, 16) ou do degrau de frequência (18). A 01 e a 19 são degeneradas por definição.

## 3. Bancada, por condição (07/10/2026, código anterior à v1.15)

Cada célula verificada cita a quantidade de capturas lidas do metadata das três sessões (99 no total). {bdg-success}`VERIFICADO NA BANCADA` vale para **aquele código** e aquela condição; não prova nada sobre o `gerar()` atual.

| Classe | 127 V/60 Hz | 127 V/50 Hz | 230 V/50 Hz | Defeito conhecido na medida |
|---|---|---|---|---|
| 01 NORMAL | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | — |
| 02 SAG | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-warning}`NÃO VERIFICADO` pulada em 07/10: sem medida a 230 V, extremo previsto acima do teto | — |
| 03 SWELL | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-warning}`NÃO VERIFICADO` inviável a 230 V/50 Hz: 357,8 V × 1,058 × 1,10 = 416,4 V > 415,8 V | — |
| 04 INTERRUPTION | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-warning}`NÃO VERIFICADO` pulada em 07/10: sem medida a 230 V | — |
| 05 HARMONICS | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | modelo antigo (soma de harmônicas) contra a CSINusoid: correlação 0,50 |
| 06 FLICKER | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | — |
| 07 NOTCH | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | — |
| 08 TRANSIENT | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-warning}`NÃO VERIFICADO` parada em 07/10: 376 V medidos > teto de 374,2 V | impulso filtrado; a 50 Hz saiu a 100 ms em vez de 80 ms (A22) |
| 09 OSCILLATORY_TRANSIENT | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | impulso de 0,12 a 0,27 pu em 100 ms que a programada não tem (A25) |
| 10 SAG_HARMONICS | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | — |
| 11 SAG_FLICKER | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | — |
| 12 SAG_OSCILLATORY_TRANSIENT | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | — |
| 13 SWELL_HARMONICS | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | — |
| 14 SWELL_OSCILLATORY_TRANSIENT | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | — |
| 15 HARMONICS_FLICKER | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | — |
| 16 INTERRUPTION_HARMONICS | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-warning}`NÃO VERIFICADO` pulada em 07/10: sem medida a 230 V | — |
| 17 NOTCH_OSCILLATORY_TRANSIENT | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | — |
| 18 FREQUENCY_DRIFT | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 1 captura(s) | — |
| 19 DC_OFFSET | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | CA 5 a 6 % abaixo em ACDC (A19) |
| 20 INTERHARMONICS | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | {bdg-success}`VERIFICADO NA BANCADA` 3 captura(s) | — |

Nas sessões de 07/10 o código era o da v1.13/v1.14 (`CHANGELOG/v1.14.md`): parâmetros de várias compostas fixos (sag 0,5; THD 20 %), 4 ciclos entalhados na 07 e na 17, rampa 57 a 63 Hz na 18, posição do evento fixa.

## 4. Perfis e o que a v1.15 mudou sem medida

`norma` e `fronteira` existem no código, nos testes e na correlação simulada; nenhuma captura física usou um perfil. A coluna "Pendências" aponta o que fecha cada classe.

| Classe | Depende do perfil? | O que a v1.15 mudou e nenhuma bancada mediu | Pendências |
|---|---|---|---|
| 01 NORMAL | não (capturada uma vez com `set perfil todos`) | {bdg-warning}`NÃO VERIFICADO` fase sorteada; disparo na fase sorteada | {ref}`P-05 <p-05>` |
| 02 SAG | sim | {bdg-warning}`NÃO VERIFICADO` início, duração e fase sorteados; `TRIGger:SYNChronize:PHASe` em passos de 0,1°; `PULSe:WIDTh` sorteada | {ref}`P-05 <p-05>` |
| 03 SWELL | sim | {bdg-warning}`NÃO VERIFICADO` idem 02 | {ref}`P-05 <p-05>` |
| 04 INTERRUPTION | não (capturada uma vez com `set perfil todos`) | {bdg-warning}`NÃO VERIFICADO` idem 02 | {ref}`P-05 <p-05>` |
| 05 HARMONICS | sim | {bdg-warning}`NÃO VERIFICADO` modelo passa a ser a senoide clipada; nível de 2 % (`norma`); nível de 30 % por TRACe | {ref}`P-10 <p-10>` |
| 06 FLICKER | sim | {bdg-warning}`NÃO VERIFICADO` perfis; média por ciclo da TRACe | {ref}`P-12 <p-12>` |
| 07 NOTCH | não (capturada uma vez com `set perfil todos`) | {bdg-warning}`NÃO VERIFICADO` entalhes em todos os ciclos; validação da crista com fator | {ref}`P-07 <p-07>` |
| 08 TRANSIENT | não (capturada uma vez com `set perfil todos`) | {bdg-warning}`NÃO VERIFICADO` impulso a 90 ms a 50 Hz; conferência de posição; cópia em 100 ms | {ref}`P-02 <p-02>`, {ref}`P-03 <p-03>` |
| 09 OSCILLATORY_TRANSIENT | não (capturada uma vez com `set perfil todos`) | {bdg-warning}`NÃO VERIFICADO` início e fase sorteados; cópia em 100 ms | {ref}`P-02 <p-02>` |
| 10 SAG_HARMONICS | sim | {bdg-warning}`NÃO VERIFICADO` sag e THD sorteados; rms CA por ciclo | {ref}`P-08 <p-08>`, {ref}`P-09 <p-09>`, {ref}`P-11 <p-11>` |
| 11 SAG_FLICKER | sim | {bdg-warning}`NÃO VERIFICADO` sag e flicker sorteados; rms CA por ciclo | {ref}`P-08 <p-08>`, {ref}`P-09 <p-09>`, {ref}`P-11 <p-11>` |
| 12 SAG_OSCILLATORY_TRANSIENT | sim | {bdg-warning}`NÃO VERIFICADO` sag e oscilação sorteados; rms CA por ciclo | {ref}`P-08 <p-08>`, {ref}`P-09 <p-09>`, {ref}`P-11 <p-11>` |
| 13 SWELL_HARMONICS | sim | {bdg-warning}`NÃO VERIFICADO` swell e THD sorteados | {ref}`P-11 <p-11>` |
| 14 SWELL_OSCILLATORY_TRANSIENT | sim | {bdg-warning}`NÃO VERIFICADO` swell e oscilação sorteados | {ref}`P-11 <p-11>` |
| 15 HARMONICS_FLICKER | sim | {bdg-warning}`NÃO VERIFICADO` THD e flicker nos 200 ms inteiros; sem `parametros_com_disturbio_reduzido` | {ref}`P-11 <p-11>` |
| 16 INTERRUPTION_HARMONICS | sim com sorteio ligado; independente com `set sorteio off` | {bdg-warning}`NÃO VERIFICADO` interrupção fixa, THD sorteado; rms CA por ciclo | {ref}`P-08 <p-08>`, {ref}`P-09 <p-09>`, {ref}`P-11 <p-11>` |
| 17 NOTCH_OSCILLATORY_TRANSIENT | não (capturada uma vez com `set perfil todos`) | {bdg-warning}`NÃO VERIFICADO` entalhes contínuos e oscilação de 300 Hz; crista com fator | {ref}`P-07 <p-07>` |
| 18 FREQUENCY_DRIFT | não (capturada uma vez com `set perfil todos`) | {bdg-warning}`NÃO VERIFICADO` rampa f0 ± 3 Hz (era 57 a 63 Hz); continuidade de fase na troca | {ref}`P-06 <p-06>` |
| 19 DC_OFFSET | não (capturada uma vez com `set perfil todos`) | {bdg-warning}`NÃO VERIFICADO` fase sorteada; ACDC | {ref}`P-17 <p-17>` |
| 20 INTERHARMONICS | sim | {bdg-warning}`NÃO VERIFICADO` amplitudes do perfil; fases sorteadas | {ref}`P-01 <p-01>` |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. A campanha prevista é o `ROTEIRO_BANCADA.md` (10 blocos; 2 h a 3 h com um perfil e 2 h 30 a 3 h 30 com `set perfil todos`): {doc}`../roteiro-bancada`. Fecha com: BANCADA. Prioridade ALTA.
:::

## 5. O que não está verificado

- **Equivalência entre os dois PCs.** A suíte rodou neste PC Windows; o PC da bancada pode ser outro (P-16).
- **Cada célula "offline"** diz que o código roda e reproduz as fixtures, não que a forma está fisicamente correta.
- **Contagem de capturas de 07/10:** 99 no metadata, contra "63" em `AGENTS.md` e `CHANGELOG/v1.15.md` (P-30).
