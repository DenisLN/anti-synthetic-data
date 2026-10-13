# Rodada de specs 2026-10-13 (v1.15, antes da bancada de 14/10)

| pri | Spec | Depende de |
|---|---|---|
| 10 | Análises Fora de docs e Arquivo em Branch Separado | nada |
| 11 | RMS por Ciclo da TRACE sem a Média e Previsão de Pico Correta | nada |
| 12 | Preflight Único na Tensão Base com ENERGIZAR-TESTE | nada |
| 13 | Run com Lista e Intervalos de Classes | nada |
| 14 | Rastreabilidade da Semente do Ruído e da Árvore Suja | nada |
| 15 | Diagnóstico da Cópia do Evento em 100 ms (Classes 08 e 09) | 11 |
| 16 | Leitura das TRACEs Gravadas (set diagnostico retrieve) | 10 |
| 17 | Um NPZ Comprimido por Classe com Perfis e Versões | 11, 14 |
| 18 | Pendentes da Correlação do Distúrbio (05, 09, 06 e Métrica) | 11, 15 |
| 19 | Revisão das Compostas Sorteadas contra a Proposta | nada |
| 20 | Pendentes de Classe Conferíveis Offline (07, 17, 18, 19 e Sorteio) | 11 |
| 21 | Fixtures Byte a Byte Portáveis entre Plataformas | nada |
| 22 | Documentação Autocontida sem Atribuição a Pessoas | 10, 12, 17 |
| 23 | Roteiro da Bancada de 14/10 | 18, 19, 20, 22 |

Primeira: 10 (ou qualquer de 10–14, 19, 21 em paralelo). Última: 23.

## Onde cada item de `pendente/` foi parar

| Relatório pendente | Item | Spec |
|---|---|---|
| classe08_fronteira_REVISAR | mecanismo do deslocamento (NÃO VERIFICADO), cópia em 100 ms | 15 |
| | recaptura a 127 V/50 Hz | 23 |
| correlacao_disturbio_diagnostico_IMPLEMENTAR | 05 com `senoide_clipada_pu` (já no código: conferir) e nível de 30 % | 18 |
| | 09: impulso espúrio em 100 ms | 15, 18 |
| | métrica com fundamental ajustada | 18 |
| | 06 perde correlação na TRACE por ciclo | 18 |
| acdc_amplitude_VERIFICAR | rodar `diag_acdc_amplitude.py`, comentário de `measure_voltage` | 20, 23 |
| classes_05_07_18_VERIFICAR | tolerância da validação da 07/17 com ~36 entalhes, 47→53 Hz | 20, 23 |
| | `preflight_new` com 57/63 Hz (já é f0±3: nota desatualizada) | 12 |
| compostas_sorteadas_REVISAR | conferir contra a proposta, 2400 Hz por TRACE | 19 |
| sorteio_inicio_fase_VERIFICAR_BANCADA | PULSe, disparo em fase, desvio do pré-trigger, recalibração | 20, 23 |
| | ciclos com média removida pela TRACE | 11 |
| apresentabilidade_VERIFICAR | F1 (5 V) | 12 |
| | F2 (`git_sujo`) | 14 |
| | F4 (log do `native`) | 12 |
| | F5 (468 gravações) | 13, 23 |
| | F8 ("v1.16"), `.env.example`, autorizações no AGENTS.md | 22 |

## Pedidos novos de 2026-10-13

| Pedido | Spec |
|---|---|
| tirar análises de `docs/` (outro branch), apagar temporários de diagnóstico | 10 |
| sem referência a professor/dono/.tex; decisões de projeto | 22 |
| descontinuar `preflight.py`, rodar em 127 V, `ENERGIZAR-TESTE` | 12 |
| `run 01-07,09-20` | 13 |
| seed do ruído no metadata | 14 |
| um `.npz` comprimido por classe (perfis × versões, sem SNRs), HTML seletivo, aviso de quebra | 17 |
| `TRACe:DATA?` em `set diagnostico retrieve`, fora do `.npz` | 16 |
| HTML e recalibração bem documentados | 22 |
| rms por ciclo sem a média (achado novo, aprovado) | 11 |
| roteiro `.md` da bancada | 23 |
