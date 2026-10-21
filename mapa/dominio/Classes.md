---
tipo: dominio
tags: [dominio]
---
# Classes
20 distúrbios, 200 ms = 6000 amostras a 30 kSa/s, gerados por `gerar()` ([[mapa/codigo/mestre|mestre]]); níveis em [[mapa/codigo/perfis|perfis]]; matemática em [[mapa/codigo/sinais|sinais]].

| # | Classe | Rota na bancada |
|---|---|---|
| 01 | [[docs/classes/01-normal|normal]] | STEP (`trigger_step`) |
| 02 | [[docs/classes/02-sag|sag]] | nativa PULSe |
| 03 | [[docs/classes/03-swell|swell]] | nativa PULSe |
| 04 | [[docs/classes/04-interruption|interruption]] | nativa PULSe |
| 05 | [[docs/classes/05-harmonics|harmonics]] | CSINusoid até 20 %; TRACe a 30 % |
| 06 | [[docs/classes/06-flicker|flicker]] | TRACe/LIST |
| 07 | [[docs/classes/07-notch|notch]] | TRACe/LIST |
| 08 | [[docs/classes/08-transient|transient]] | TRACe/LIST |
| 09 | [[docs/classes/09-oscillatory-transient|oscillatory-transient]] | TRACe/LIST |
| 10 | [[docs/classes/10-sag-harmonics|sag-harmonics]] | TRACe/LIST |
| 11 | [[docs/classes/11-sag-flicker|sag-flicker]] | TRACe/LIST |
| 12 | [[docs/classes/12-sag-oscillatory-transient|sag-oscillatory-transient]] | TRACe/LIST |
| 13 | [[docs/classes/13-swell-harmonics|swell-harmonics]] | TRACe/LIST |
| 14 | [[docs/classes/14-swell-oscillatory-transient|swell-oscillatory-transient]] | TRACe/LIST |
| 15 | [[docs/classes/15-harmonics-flicker|harmonics-flicker]] | TRACe/LIST |
| 16 | [[docs/classes/16-interruption-harmonics|interruption-harmonics]] | TRACe/LIST |
| 17 | [[docs/classes/17-notch-oscillatory-transient|notch-oscillatory-transient]] | TRACe/LIST |
| 18 | [[docs/classes/18-frequency-drift|frequency-drift]] | nativa `LIST:FREQuency` |
| 19 | [[docs/classes/19-dc-offset|dc-offset]] | nativa ACDC + offset |
| 20 | [[docs/classes/20-interharmonics|interharmonics]] | TRACe/LIST |

Visão geral e divergências do `experimentos.txt`: [[docs/classes|classes]]; contrato: [[docs/codigo/classes_contrato|contrato]]. Capturas por classe = max(`set capturas`, `capturas_padrao`).
> [!warning] 08 e 05
> A 08 é limitada a 0,9 x `max_peak_v` (374,2 V); a 05 usa CSINusoid só até 20 % (`MAX_CSINE_THD_PCT`).
