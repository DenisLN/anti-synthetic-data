# Visita à bancada de 2026-10-22: onde paramos

Visita `2026-10-22_13-31-58`, Inspiron 15 (DESKTOP-FSEESJI), commits `022bb5c` e `a22fba9` (calibração do Bloco 7). Encerrada às 15:35, quando o operador escolheu parar no alerta de extremo do braço A da P-09. OUTPUT OFF conferido pelo operador.

## Estado das etapas

| Etapa | Estado |
|---|---|
| 01 a 02 (suíte, infra) | ok |
| 03 (ciclos de 07/10) | pulada: sessões de 07/10 não estão no PC |
| 04, 05, 06 (marcadores, ACDC 50/60, 08 e 09) | ok |
| 07 (07 e 17, duas rodadas) | ok; calibração commitada (`022bb5c`, `a22fba9`) |
| 08-parte1 | falhas: 02 (crista 1,83 > 1,81), 18 (THD 3,4%), 19 (THD ~9,7%) |
| 08-A (05 norma e literatura) | ok |
| 09 partes 2 a 6 | ok |
| 10B-diag | marcada ok, mas **inconclusiva**: `*ESR?=32` logo após `SOURce:MODE AC`, offset nunca testado (`diag_list_offset.*`) |
| 10B-braco-A | parada pelo operador; capturas em `sessao_2026-10-22_15-27-50`; roda de novo na retomada |
| 10B-braco-C/B, 10B-analise, 10A, campanhas, 11 | não rodaram |

Arquivos: `visita_estado.json` e `visita.log` (cópia de `logs/visita_2026-10-22_13-31-58/`), `verificar_parte1_*.json`, `diag_list_offset.*`, `recalibracao_proposta_127V_60Hz.md`.

## Antes de energizar de novo (obrigatório)

1. **Fatores de extremo baixos (achado de segurança).** Hoje os extremos medidos passaram do previsto em 1-30%; a 13-0002 chegou a 378 V (teto 415,8 V). **Resolvido a 60 Hz:** recalibração de 127 V/60 Hz commitada (`13b9bdb`, proposta em `recalibracao_proposta_127V_60Hz.md`); a 220 V, 05 e 18 saem e 13, 14 e 19 perdem capturas (decisão do responsável). **50 Hz:** a visita agora grava a calibração de 50 Hz com a campanha de 127 V/50 Hz (etapa `C-127V_50Hz-calibrar`) antes da campanha de 230 V/50 Hz.
2. **17 fora de 220 V** pelo fator 1,575 (commit `a22fba9`). A medida de hoje dá no máximo 1,408 para a 17; conferir por que a CLI gravou 1,575 antes de aceitar a exclusão.
3. **P-09 (10B-diag)**: entender o erro de `SOURce:MODE AC` antes de confiar no braço C pulado.
4. **220 V/60 Hz sem tabela**: a regra de condição sem tabela usa o maior fator já medido (1,615) em toda classe, e quase nada cabe na rodada de calibração de 220 V. Decisão de projeto antes dessa rodada.

## Retomar

Mesmo PC: `scripts\VISITA_BANCADA.cmd`. Retoma no braço A da P-09.

Outro PC:
1. `git pull` do branch `feat/execucao-pendencias-v1-15` (fork `rmlinxic/anti-synthetic-data`).
2. Descompactar `bancada_2026-10-22.zip` na raiz do projeto: ele traz `resultados/sessao_2026-10-22_*` e `logs/` (com `logs/visita_2026-10-22_13-31-58/estado.json`). Sem o zip a visita começa do zero e as sessões de hoje não entram no fechamento.
3. Preparar o PC (COM10, NI-VISA, `env`) como em `CLAUDE.md` e rodar `scripts\VISITA_BANCADA.cmd`. A visita acha as sessões pelo nome mesmo que a pasta do projeto seja outra.

## Para o fechamento

- Pre-trigger de 5 a 6 amostras (limite 2) em 02-0001 e 04-0001/0002.
- 18: frequências estimadas no triplo das programadas (171/189 Hz para 57/63 Hz), junto com a THD alta de 18 e 19.
- 08: `TRACe:DATA?` devolve 10 valores em vez de 1024 (evidência para a P-19).
- Visita: ordem da 2.ª rodada do Bloco 7 contra a checagem de árvore suja; `--saida` do `diag_list_offset.py` virou pasta; 10B-diag com resultado `None` marcada como ok.
