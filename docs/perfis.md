# Perfis de faixas do dataset

Fonte única: `logica/perfis.py` (`FAIXAS`). Escolha: `set perfil norma|literatura|fronteira` na CLI, ou a variável de ambiente `PERFIL` (inicial; simulado e bancada). Padrão: `literatura`, que reproduz o `gerar()` anterior à v1.15 (commit 34a0d82) byte a byte com `set sorteio off` (o sorteio de início/duração/fase, ligado por padrão, é independente do perfil: `arquivo/analises:docs/analise-2026-10-12/pendente/sorteio_inicio_fase_VERIFICAR_BANCADA.md`). O perfil vai em cada captura (`perfil` no metadata; metadata sem o campo = `literatura`).

Só as classes abaixo dependem do perfil. Forma, frequência do flicker, interrupção, notch, transitórios, drift e DC não mudam entre perfis (classes 01, 04, 07, 08, 09, 17, 18, 19 idênticas nos três).

| Classe | Parâmetro | norma (IEEE 1159) | literatura (padrão) | fronteira |
|---|---|---|---|---|
| 02 SAG | nível (pu), 1 por `capture_index` | 0,15 / 0,325 / 0,5 / 0,675 / 0,85 | 0,1 / 0,3 / 0,5 / 0,7 / 0,9 | 0,1 / 0,9 (2 níveis) |
| 03 SWELL | nível (pu) | 1,15 / 1,30 / 1,45 / 1,60 / 1,75 | 1,1 / 1,2 / 1,4 / 1,6 / 1,8 | 1,1 / 1,8 (2 níveis) |
| 05 HARMONICS | THD (CSINe nativo até 20 %; acima, TRACe) | 2 / 5 / 10 / 15 / 20 % (todos nativos) | 5 / 10 / 15 / 20 / 30 % | igual à literatura |
| 06 FLICKER | profundidade, `uniform` | 2 a 7 % | 5 a 15 % | igual à literatura |
| 10 SAG+HARMONICS | sag (pu) / THD | 0,5 / 20 % | 0,5 / 20 % | 0,1 e 0,9 alternando por `capture_index` / 20 % |
| 11 SAG+FLICKER | sag (pu) / profundidade | 0,5 / 4,5 % | 0,5 / 10 % | 0,1 e 0,9 alternando / 10 % |
| 12 SAG+OSC | sag (pu) | 0,5 | 0,5 | 0,1 e 0,9 alternando |
| 13 SWELL+HARMONICS | swell (pu) / THD | 1,3 / 20 % | 1,3 / 20 % | 1,1 e 1,8 alternando / 20 % |
| 14 SWELL+OSC | swell (pu) | 1,3 | 1,3 | 1,1 e 1,8 alternando |
| 15 HARMONICS+FLICKER | THD / profundidade | 20 % / 4,5 % | 20 % / 10 % | 20 % / 10 % |
| 16 INTERRUPTION+HARMONICS | interrupção (pu) / THD | 0,05 / 20 % | 0,05 / 20 % | 0,05 / 20 % |
| 20 INTERHARMONICS | amplitude de cada uma das 3 (pu), `uniform` | 0,5 a 2 % | 3 a 8 % | igual à literatura |

Notas:

- As compostas herdam o componente (`sag_composto`, `swell_composto`, `thd_composto`, `flicker_composto` em `perfis.py`). Com `set sorteio off`, compostas têm valor único por perfil, exceto `fronteira` para sag/swell, que alterna entre as duas fronteiras pelo `capture_index`: com 1 captura por classe (padrão da bancada) só aparece 0,1 (sag) e 1,1 (swell); `set capturas 2` ou mais cobre as duas.
- A spec só define fronteira para sag/swell (0,1, 0,9, 1,1, 1,8 pu). THD, flicker e inter-harmônicas usam a literatura no perfil `fronteira` (escolha minha; ver `arquivo/analises:docs/analise-2026-10-12/resolvido/perfis_mudancas.md`).
- Os níveis intermediários da norma (0,325, 0,675, 1,30, 1,45, 2 % de THD, 4,5 % de flicker composto) são escolha de implementação: espaçamento uniforme dentro da faixa pedida; a spec fixa só os extremos.
- Os níveis `2 %` de THD no CSINe e os sag/swell de fronteira não foram exercitados na bancada real.
- Desde a v1.15, com o sorteio ligado (padrão) as compostas 10 a 16 sorteiam esses componentes por captura (FAIXAS_SORTEADAS em perfis.py): sag U(0,1; 0,9), swell U(1,1; 1,8), THD U(0,05; 0,20), flicker U(8; 25) Hz, oscilação U(300; 2400) Hz, profundidade do flicker = faixa da 06; norma e fronteira conforme a tabela de componentes; fronteira de sag/swell continua em dois níveis. Os valores da tabela valem com set sorteio off. Detalhe: `arquivo/analises:docs/analise-2026-10-12/pendente/compostas_sorteadas_REVISAR.md.`

## Compostas sorteadas: o que a proposta pede e o que o projeto acrescenta (revisão de 2026-10-13)

Parâmetros que as compostas 10 a 16 sorteiam com o sorteio ligado (`perfis.py:113-134`, `composto` em `perfis.py:182`), perfil `literatura`:

| Componente | Classes | Faixa | Situação |
|---|---|---|---|
| sag | 10 (pedido); 11 e 12 (extensão a) | U(0,1; 0,9) | conforme na 10 |
| swell | 13 e 14 | U(1,1; 1,8) | extensão (a, b) |
| THD | 10 (pedido); 13, 15 e 16 (extensão f) | U(0,05; 0,20) | conforme na 10 |
| flicker (frequência) | 11 e 15 | U(8; 25) Hz | conforme |
| flicker (profundidade) | 11 e 15 | faixa da classe 06 (`flicker_profundidade`) | conforme |
| oscilação | 12 e 14 | U(300; 2400) Hz | conforme |

Decisões de projeto que vão além do que a proposta enumera (nenhuma altera `max_voltage_rms`, `max_peak_v` ou a pré-validação de pico; reverter qualquer uma muda o dataset da v1.15 e exige regravar `gerar_sorteio_v1_15.json`):

- **(a) Sag em 11 e 12, swell em 13 e 14.** `sag_composto`/`swell_composto` já eram um componente compartilhado entre as classes; sortear só na 10 deixaria 11 a 14 com uma forma de nível por classe, o que reproduz o problema de "uma forma só" que o sorteio resolve.
- **(b) Faixa do swell = extremos de `swell_niveis`** (1,1 a 1,8; norma 1,15 a 1,75). O sorteio contínuo cobre o mesmo intervalo que os cinco níveis discretos da classe 03, então 03 e 13/14 variam o swell na mesma faixa.
- **(c) Perfil `norma`:** sag 0,15 a 0,85 e swell 1,15 a 1,75 (extremos de `sag_niveis`/`swell_niveis` da norma) e THD de 2 % a 20 % (extremos de `thd_niveis`). A profundidade do flicker segue a faixa da 06 da norma (2 % a 7 %).
- **(d) Perfil `fronteira`:** sag e swell não são sorteados; alternam 0,1/0,9 e 1,1/1,8 por `capture_index` (`FAIXAS_SORTEADAS[...]["fronteira"] = None`). O perfil serve para estressar as fronteiras, e um sorteio contínuo as tocaria só por acaso. THD, flicker e oscilação mantêm as faixas da literatura.
- **(e) Valores fixos nas classes 16 e 17.** A 16 mantém a interrupção em 0,05 pu (o nível de interrupção de IEEE 1159 é < 0,1 pu; sortear dentro da faixa deixaria de ser interrupção em parte das capturas) e a 17 mantém a oscilação em 300 Hz, com os entalhes já sorteados.
- **(f) THD sorteado em 13, 15 e 16.** O THD é o mesmo componente (`thd_composto`) nas quatro compostas harmônicas; sortear só na 10 deixaria 13, 15 e 16 com THD fixo de 20 %, o teto do CSINe e o extremo da faixa, e um classificador aprenderia "THD = 20 %" como marca da classe.

Interruptor: `set sorteio off` volta aos valores fixos da tabela de cima (o `gerar()` de 34a0d82, byte a byte).

Limite conhecido, medido: na TRACe por ciclo a oscilação de 2400 Hz e o flicker de 25 Hz saem com erro máximo de 0,035 e 0,054 pu (50 e 60 Hz, sem sag/swell); detalhe em `CHANGELOG/v1.15.md`, seção "Revisão das compostas sorteadas".
