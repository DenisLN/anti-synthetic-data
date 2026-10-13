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

- As compostas herdam o componente (`sag_composto`, `swell_composto`, `thd_composto`, `flicker_composto` em `perfis.py`). Compostas têm valor único por perfil, exceto `fronteira` para sag/swell, que alterna entre as duas fronteiras pelo `capture_index`: com 1 captura por classe (padrão da bancada) só aparece 0,1 (sag) e 1,1 (swell); `set capturas 2` ou mais cobre as duas.
- A spec só define fronteira para sag/swell (0,1, 0,9, 1,1, 1,8 pu). THD, flicker e inter-harmônicas usam a literatura no perfil `fronteira` (escolha minha; ver `arquivo/analises:docs/analise-2026-10-12/resolvido/perfis_mudancas.md`).
- Os níveis intermediários da norma (0,325, 0,675, 1,30, 1,45, 2 % de THD, 4,5 % de flicker composto) são escolha de implementação: espaçamento uniforme dentro da faixa pedida; a spec fixa só os extremos.
- Os níveis `2 %` de THD no CSINe e os sag/swell de fronteira não foram exercitados na bancada real.
- Desde a v1.15, com o sorteio ligado (padrão) as compostas 10 a 16 sorteiam esses componentes por captura (FAIXAS_SORTEADAS em perfis.py): sag U(0,1; 0,9), swell U(1,1; 1,8), THD U(0,05; 0,20), flicker U(8; 25) Hz, oscilação U(300; 2400) Hz, profundidade do flicker = faixa da 06; norma e fronteira conforme a tabela de componentes; fronteira de sag/swell continua em dois níveis. Os valores da tabela valem com set sorteio off. Detalhe: `arquivo/analises:docs/analise-2026-10-12/pendente/compostas_sorteadas_REVISAR.md.`
