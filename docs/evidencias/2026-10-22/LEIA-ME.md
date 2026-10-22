# Visita à bancada de 2026-10-22: onde paramos

Visita `2026-10-22_13-31-58`, Inspiron 15 (DESKTOP-FSEESJI), commits `022bb5c` e `a22fba9` (calibração do Bloco 7). Encerrada às 15:35, quando o operador escolheu parar no alerta de extremo do braço A da P-09. OUTPUT OFF conferido pelo operador.

## Estado das etapas

| Etapa | Estado |
|---|---|
| 01 a 02 (suíte, infra) | ok |
| 03 (ciclos de 07/10) | pulada: sessões de 07/10 não estão no PC |
| 04, 05, 06 (marcadores, ACDC 50/60, 08 e 09) | ok |
| 07 (07 e 17, duas rodadas) | ok; calibração commitada (`022bb5c`, `a22fba9`) |
| 08-parte1 | falhas: 02 (crista 1,83 > 1,81; fator 1,164 baixo, hoje 1,192), 18 (THD 3,4%) e 19 (THD ~9,7%) por bug de software (`72bbcd6`); no `run falhas` (`14-42-21`) 18 e 19 passaram |
| 08-A (05 norma e literatura) | ok |
| 09 partes 2 a 6 | ok |
| 10B-diag | ok: **sem suporte** a `SOURce:LIST:VOLTage:OFFSet` (`-113 Undefined header`, `diag_list_offset.json`); o "None" do log era a visita lendo o caminho errado (`192791e`); braço C pulado com razão |
| 10B-braco-A | parada pelo operador; capturas em `sessao_2026-10-22_15-27-50`; roda de novo na retomada |
| 10B-braco-C/B, 10B-analise, 10A, campanhas, 11 | não rodaram |

Arquivos: `visita_estado.json` e `visita.log` (cópia de `logs/visita_2026-10-22_13-31-58/`), `verificar_parte1_*.json`, `diag_list_offset.*`, `recalibracao_proposta_127V_60Hz.md`.

## Antes de energizar de novo (obrigatório)

1. **Fatores de extremo baixos (achado de segurança).** Hoje os extremos medidos passaram do previsto em 1-30%; a 13-0002 chegou a 378 V (teto 415,8 V). **Resolvido a 60 Hz:** recalibração de 127 V/60 Hz commitada (`13b9bdb`, proposta em `recalibracao_proposta_127V_60Hz.md`); a 220 V, 05 e 18 saem e 13, 14 e 19 perdem capturas (decisão do responsável). **50 Hz:** a visita agora grava a calibração de 50 Hz com a campanha de 127 V/50 Hz (etapa `C-127V_50Hz-calibrar`) antes da campanha de 230 V/50 Hz.
2. ~~17 fora de 220 V pelo fator 1,575~~ Conferido: 1,575 é o máximo medido na 2.ª rodada do Bloco 7 (`sessao_2026-10-22_14-27-02`: mín. 1,369, mediana 1,423). A exclusão vale.
3. ~~P-09 (10B-diag)~~ Resolvido: a fonte não aceita offset por passo; o `*ESR?=32` depois de `SOURce:MODE AC` é o mesmo `-113` da consulta, lido pela primeira vez ali. Modo AC restaurado.
4. **220 V/60 Hz sem tabela (decisão pendente, antes de `C-220V_60Hz-rodada-calibracao`).** Ver a seção abaixo.

## Decisão pendente: fatores a 220 V/60 Hz

Hoje `carregar_fatores_extremo` trata 220 V/60 Hz como condição sem tabela: toda classe usa o maior fator já medido (1,615, da 07), menos a 01. Com isso, na rodada de calibração de 220 V só cabem 07, 10, 11, 15 e 16 (e parte da 12 e da 20); 01-06, 09, 13, 14, 17, 18 e 19 seriam puladas, e a rodada não calibra essas classes. Já era assim antes de 2026-10-22 (máximo 1,475).

| Opção | O que muda | Prós | Contras |
|---|---|---|---|
| A. Manter | nada | regra mais conservadora | a campanha de 220 V fica sem a maioria das classes, sem caminho para calibrá-las |
| B. Mesma frequência basta | condição sem tabela própria, mas com tabela de mesma frequência (127 V/60 Hz), usa o fator da própria classe nessas tabelas, como a regra de condição calibrada | coerente com o achado da v1.14 (o sobressinal depende da frequência, não da tensão: 127 V e 230 V a 50 Hz deram fatores próximos); a 220 V cabem todas menos 05, 14, 17, 18, parte de 13/19 e a 03 no perfil norma (os testes já supõem isso) | a dependência com a tensão a 60 Hz nunca foi medida; a margem de 1,10 é a única folga até a rodada de calibração medir |
| C. B com folga extra só na rodada | como B, mas a rodada de calibração de 220 V usa margem maior (por exemplo, perfil literatura e fração reduzida) | mede antes de chegar ao teto | exige definir a folga, que não existe em nenhuma fonte (não inventar) |

Conferido depois: a regra atual foi decisão explícita da v1.14 para 220 V, por causa do incidente dos 444 V (que foi entre frequências, 230 V/50 Hz com tabela de 60 Hz). A evidência de que a tensão não influi é fraca (capturas reduzidas, só limite inferior). **Decisão do operador em 2026-10-22: manter a regra atual (A)** até o responsável decidir; opções registradas em `docs/decisoes_pendentes.md`, seção P-21. Um dado que ajudaria (opção C): comparar 127 V/50 Hz com 230 V/50 Hz nas campanhas da próxima visita.

## Retomar

Mesmo PC: `scripts\VISITA_BANCADA.cmd`. Retoma no braço A da P-09. Depois do 10-A, antes das campanhas, a visita reexecuta o que reprovou hoje e foi corrigido (bloco R): `run 02,17,18,19`, `run 10,11` e `run 12,16` a 127 V/60 Hz.

Outro PC:
1. `git pull` do branch `feat/execucao-pendencias-v1-15` (fork `rmlinxic/anti-synthetic-data`).
2. Descompactar `bancada_2026-10-22.zip` na raiz do projeto: ele traz `resultados/sessao_2026-10-22_*` e `logs/` (com `logs/visita_2026-10-22_13-31-58/estado.json`). Sem o zip a visita começa do zero e as sessões de hoje não entram no fechamento.
3. Preparar o PC (COM10, NI-VISA, `env`) como em `CLAUDE.md` e rodar `scripts\VISITA_BANCADA.cmd`. A visita acha as sessões pelo nome mesmo que a pasta do projeto seja outra.

## Para o fechamento

- **Pre-trigger (primeira medida em bancada)**: desvio determinístico, função do instante programado do evento, igual nos três perfis e no rerun: 02 (início 19,07 ms) +5 amostras em 5/5; 03 (58,07 ms) −1; 04 (110,8 / 114,8 / 132,1 ms) −2 / −6 / +6. Até ±0,2 ms a 30 kHz. O limite de 2 amostras do verificador nunca foi validado; não foi mudado (sem fonte para outro valor). Decidir se vira compensação do rótulo de início ou limite novo.
- **18 e 19 (THD)**: causa encontrada e corrigida (`72bbcd6`): depois da 17 a forma fixa ficava na última TRACE entalhada (ímpares de 2-3%, THD ≈ 4,7%, igual ao fim da 17; a 01 sai com 0,19%). As frequências da 18 no triplo (171/189 Hz) são provavelmente o mesmo efeito (cruzamentos de zero extras dos entalhes): não verificado.
- 08: `TRACe:DATA?` devolve 10 valores em vez de 1024 (evidência para a P-19).
- Visita, corrigido: leitura do diagnóstico da P-09 (`192791e`), commit da calibração entre as rodadas do Bloco 7 (`e7c87c0`), calibração de 50 Hz antes de 230 V (`aac725b`), retomada em outro PC (`9730cd4`).
