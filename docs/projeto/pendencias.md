# Pendências — inventário histórico de 16/10/2026

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


:::{important} Estado atual em outra página
Esta página preserva o inventário e as opções anteriores ao início da execução. “Hoje”, contagens, conferências, decisões em aberto e estados abaixo pertencem ao relato de 15–16/10/2026, não à execução atual. O usuário autorizou tratar plenamente as pendências, atualizando escolhas anteriores; código e testes já estão em alteração. Consulte {doc}`../execucao_pendencias` para decisões vigentes, implementação, testes e bloqueios. As 31 entradas não significam 31 itens ainda inalterados. Alegações históricas de acesso a sessões/transcrições não foram repetidas neste checkout.
:::


{bdg-info}`BASELINE HISTÓRICA` 31 itens então abertos (P-01 a P-31) {bdg-info}`OFFLINE` base `main` em `fa82f49`, conferida em 2026-10-15 e 2026-10-16

**Escopo histórico:** no levantamento de 16/10/2026 havia **31 pendências abertas**, cada uma com id estável `P-NN`, a classe que afeta, a fonte, **o que a fecha** (bancada, decisão do usuário ou código) e a prioridade; a maior, **P-01**, é que nenhum dado de bancada existe com o código da v1.15, o que deixa as outras classes de pendência dependentes de uma única campanha. Os ids não mudam de número quando fecham: a pendência passa para a seção "Resolvidas ou obsoletas".

Resumo por tipo de fechamento (o primeiro tipo citado na coluna "O que fecha"): BANCADA 17, DECISÃO DO USUÁRIO 13, CÓDIGO 1. Por prioridade: ALTA 5, MÉDIA 16, BAIXA 10.

Fontes das pendências: o relatório final da rodada de 13 a 15/10/2026 e o estado dessa rodada (branch `arquivo/analises`, ver {doc}`analises-arquivadas`), o `CHANGELOG/v1.15.md`, o `ROTEIRO_BANCADA.md` ({doc}`../roteiro-bancada`), as seções "NÃO VERIFICADO" de cada documento de `docs/` e o diff real do branch `feat/passo-final-sin` ({doc}`passo-final-sin`). As pendências de 21/09, 30/09 e 12/10/2026 não foram reabertas: só entram as que as fontes acima ainda citam.

:::{warning} Decisão em aberto
As pendências marcadas **DECISÃO DO USUÁRIO** pedem uma escolha do responsável pelo projeto; este site não decide por ele. Ver a seção 4. Ids: P-04, P-09, P-11 a P-15, P-20, P-23, P-25 e P-26, mais as partes de decisão de P-18, P-29, P-30 e P-31 (a P-10 é só de bancada).
:::

## 1. Tabela geral

| Id | Classe | Pendência | O que fecha | Prioridade |
|---|---|---|---|---|
| {ref}`P-01 <p-01>` | GLOBAL (todas) | Nenhum dado de bancada com o código da v1.15 (perfis, sorteio, compostas, entalhes contínuos, 08 a 90 ms, crista com fator, cópia em 100 ms): a última campanha é de 07/10 | BANCADA (roteiro de 10 blocos; estimativa do roteiro: 2 h a 3 h com um perfil, 2 h 30 a 3 h 30 com `todos`) | {bdg-danger}`ALTA` |
| {ref}`P-02 <p-02>` | 08, 09 | Mecanismo da cópia/deslocamento do evento em 100,0 ms (quirks A22 e A25): a 08 a 50 Hz saiu em 100 ms em 3/3; a 09 tem impulso de 0,12-0,27 pu em 100,0-100,2 ms em 9/9. Cinco hipóteses em ... | BANCADA (Blocos 4 e 6: `diag_marcadores_trace.py`, retrieve, recaptura) | {bdg-danger}`ALTA` |
| {ref}`P-03 <p-03>` | 08 | Recaptura a 127 V/50 Hz com impulso em 90 ms: posição (`abs(desvio)` ≤ 10 amostras), pico ≤ 374,2 V, sobressinal ≤ 0,55. Acima disso é achado de segurança | BANCADA | {bdg-danger}`ALTA` |
| {ref}`P-04 <p-04>` | GLOBAL | `program_capture()` só AVISA quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga"); quem recusa é a pré-validação de `mestre.py` e o script de marcadores. Proposta: o ... | DECISÃO DO USUÁRIO, depois CÓDIGO | {bdg-warning}`MÉDIA` |
| {ref}`P-05 <p-05>` | 01-04 | Sorteio de posição nas nativas: disparo na fase sorteada (`TRIGger:SYNChronize:PHASe` em passos de 0,1°, sem readback), `:TIMebase:POSition` por captura, `PULSe:WIDTh` sorteada, ... | BANCADA (Parte 1 da campanha e `verificar_sessao_bancada.py`) | {bdg-warning}`MÉDIA` |
| {ref}`P-06 <p-06>` | 18 | Continuidade de fase na troca `start_hz` → `end_hz` do `LIST:FREQuency`; rampa 47 → 53 Hz a 50 Hz; `restaurar_frequencia_base` depois da rampa nova. Limiar de 10° é proposta sem dado | BANCADA | {bdg-warning}`MÉDIA` |
| {ref}`P-07 <p-07>` | 07, 17 | Crista da validação física: fatores calibrados a 127 V/60 Hz (07 = 1,186; 17 = 1,031) não cobrem o toque simulado (≥ 1,344 e ≥ 1,420); a 1.ª rodada tende a reprovar só por "fator de ... | BANCADA (rodar com `set recalibracao on`, `git diff`, commitar) | {bdg-danger}`ALTA` |
| {ref}`P-08 <p-08>` | 10, 11, 12, 16 | Conferir na 1.ª sessão que `pico_medido_v`/`vale_medido_v` ≤ `extremo_previsto_v` depois da correção do rms CA por ciclo (previsão antiga subestimava até 38 %) | BANCADA | {bdg-danger}`ALTA` |
| {ref}`P-09 <p-09>` | 10, 11, 12, 16 (e compostas com degrau no meio do ciclo) | Resta a média de cada ciclo (erro programada × modelo 0,24-0,33 pu): só recuperável por offset por passo (ACDC, que tem o déficit de P-17). Decisão: investigar depois da bancada? | DECISÃO DO USUÁRIO | {bdg-secondary}`BAIXA` |
| {ref}`P-10 <p-10>` | 05 | Nunca medidos: rms e THD da CSINusoid interna a 10/15/20 %; nível de 2 % (perfil `norma`); nível de 30 % por TRACe; modelo novo (senoide clipada) contra a bancada | BANCADA | {bdg-warning}`MÉDIA` |
| {ref}`P-11 <p-11>` | 10-16 | Manter ou reverter as extensões das compostas (a)-(f) (sag em 11/12, swell em 13/14, faixas da `norma`, `fronteira` alternada, THD em 13/15/16). Reverter muda o dataset e exige regravar ... | DECISÃO DO USUÁRIO | {bdg-warning}`MÉDIA` |
| {ref}`P-12 <p-12>` | 06 (e 11, 15) | Comparar a 06 com a forma programada (sem mudar dataset) ou redefinir o flicker com média nula por ciclo (muda `gerar()`, exige autorização em `AGENTS.md`). Efeito nas 11 e 15 não calculado | DECISÃO DO USUÁRIO | {bdg-warning}`MÉDIA` |
| {ref}`P-13 <p-13>` | GLOBAL | `sessao_io.recuperar_parcial` é função manual; ninguém a chama no início do `run` | DECISÃO DO USUÁRIO, depois CÓDIGO | {bdg-secondary}`BAIXA` |
| {ref}`P-14 <p-14>` | GLOBAL | `run 01 02` (espaço, sem vírgula) roda só a 01, sem aviso; `BATERIA_EXCLUIR` não vale para listas | DECISÃO DO USUÁRIO | {bdg-secondary}`BAIXA` |
| {ref}`P-15 <p-15>` | GLOBAL | `docs/operacao.md:122` e o relatório individual 22 dizem que o HTML do fim do run mostra só as 3 primeiras capturas por classe e perfil; no código ([sessao_io.py:771-776](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L771-L776), ... | DECISÃO DO USUÁRIO | {bdg-secondary}`BAIXA` |
| {ref}`P-16 <p-16>` | GLOBAL | Rodar `tests.test_offline` no Windows. **Parcialmente resolvida hoje** (ver seção 2) | BANCADA (PC da bancada) | {bdg-warning}`MÉDIA` |
| {ref}`P-17 <p-17>` | 19 | Déficit de 5-6 % de CA em ACDC (0,938-0,951 pu); `diag_acdc_amplitude.py` pronto, nunca rodou; compensação `V/g` é proposta; 230 V no ACDC é escolha do dia | BANCADA | {bdg-warning}`MÉDIA` |
| {ref}`P-18 <p-18>` | 01-20 TRACe | Passo final `SINE` no `LIST` (PR #3, `18b144d`): `SINE` aceito em `LIST:FUNCtion:SHAPe`? Padrão LIGADO no branch (`AMETEK_PASSO_FINAL_SIN` = 1). Merge com a `main`: conflito textual só em ... | BANCADA (`scripts/teste_passo_final_sin.py`, `ENERGIZAR-PASSO-SIN`) e DECISÃO DO USUÁRIO (padrão desligado?) | {bdg-warning}`MÉDIA` |
| {ref}`P-19 <p-19>` | GLOBAL (TRACe) | A Rev. 5.53 aceita `TRACe:DATA? <nome>` e responde lista NRf separada por vírgula? O manual se contradiz (p. 126 "Query Syntax: none"; p. 147 "when queried... normalized"). Query nova numa ... | BANCADA (1.ª captura da 08 com `set diagnostico retrieve on` e painel à vista) | {bdg-warning}`MÉDIA` |
| {ref}`P-20 <p-20>` | GLOBAL | Congelar a v1.15: tag `v1.15`, release no GitHub e Zenodo (não configurado); o projeto não tem `LICENSE` nem `CITATION.cff` | DECISÃO DO USUÁRIO | {bdg-warning}`MÉDIA` |
| {ref}`P-21 <p-21>` | GLOBAL | Condições sem tabela de extremos (220 V/60 Hz e outras) rodam com previsão conservadora (fator 1,475) e várias classes puladas; a 230 V/50 Hz a 03 fica de fora (416,4 V > 415,8 V). Calibrar ... | BANCADA (bateria na condição + `recalibrar_extremos.py --gravar`) | {bdg-warning}`MÉDIA` |
| {ref}`P-22 <p-22>` | GLOBAL | Tamanho e custo de reescrita do `NN_classe.npz` com medida física real (ruído de bancada comprime menos); capturas "espelho" (`set perfil todos`) são cópia, não 3 medidas | BANCADA | {bdg-secondary}`BAIXA` |
| {ref}`P-23 <p-23>` | GLOBAL | Trava da fonte na ~280.ª gravação de TRACe por conexão (quirk A3; causa NÃO VERIFICADA). `README.md:26` e `AGENTS.md` ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `todos`); o ... | DECISÃO DO USUÁRIO (texto dos docs) e BANCADA (causa) | {bdg-warning}`MÉDIA` |
| {ref}`P-24 <p-24>` | GLOBAL | Documentação: 63 das 85 citações `arquivo:linha` conferidas em `classes.md`, `scpi.md` e `limites_e_calibracao.md` estão deslocadas; 8 documentos carimbados com `d37e403`; contagens de ... | CÓDIGO (site com símbolos em vez de linhas; próxima etapa do site) | {bdg-warning}`MÉDIA` |
| {ref}`P-25 <p-25>` | GLOBAL | Decisões menores da tarefa 22: identificadores de tarefa no texto (8 ocorrências hoje fora dos CHANGELOG fechados); um termo de governança em `AGENTS.md` (9 ocorrências); um nome de ... | DECISÃO DO USUÁRIO | {bdg-secondary}`BAIXA` |
| {ref}`P-26 <p-26>` | GLOBAL | Escolhas do dia de bancada: um perfil ou `set perfil todos`; frequência da campanha (roteiro assume 60 Hz); ACDC a 230 V | DECISÃO DO USUÁRIO | {bdg-warning}`MÉDIA` |
| {ref}`P-27 <p-27>` | GLOBAL | A faixa de referência da correlação do distúrbio (0,95-1,00; 0,75-0,94; 0,005 da 08) vem de `validacao_gerador_v1.14.md`, que não está no repositório: a coluna "bate?" de ... | DECISÃO DO USUÁRIO (fornecer o arquivo) | {bdg-secondary}`BAIXA` |
| {ref}`P-28 <p-28>` | GLOBAL | Reamostragem do osciloscópio (~116,7 kSa/s → 30 kSa/s) por interpolação linear, sem anti-aliasing: efeito não quantificado (quirk K4) | BANCADA/OFFLINE (comparar com taxa bruta) | {bdg-secondary}`BAIXA` |
| {ref}`P-29 <p-29>` | GLOBAL | As transcrições SCPI reais (`scpi_transcricao.log`) das sessões de 07/10 existem só em `resultados/` desta máquina (gitignored; 3 arquivos, 6846 a 9675 linhas) e não estão em nenhum branch: ... | DECISÃO DO USUÁRIO (versionar trechos selecionados ou autorizar a extração) | {bdg-warning}`MÉDIA` |
| {ref}`P-30 <p-30>` | GLOBAL | Contagem de capturas de 07/10 incoerente: `AGENTS.md:125` e `CHANGELOG/v1.15.md:9` dizem 63; `docs/tres_versoes.md:59` diz 99; os arquivos têm 36 + 36 + 27 = 99 e `analisar_sessao.py` leu ... | DECISÃO DO USUÁRIO (o que é "piloto") | {bdg-secondary}`BAIXA` |
| {ref}`P-31 <p-31>` | GLOBAL (correlação) | A correlação do distúrbio com a fundamental ajustada foi calculada hoje, offline, nas três sessões de 07/10 (99 capturas, tabela em `02-lacunas.md` §2.3), o que fecha o NÃO VERIFICADO de ... | BANCADA (qualquer sessão nova) e DECISÃO DO USUÁRIO (métrica oficial) | {bdg-secondary}`BAIXA` |

## 2. Pendências por classe

**Pergunta:** o que está aberto na classe NN? **Resposta:** a tabela abaixo; as pendências globais (P-01 e outras de GLOBAL) afetam todas as classes e só aparecem aqui quando mencionam a classe pelo número ou por "todas".

| Classe | Pendências |
|---|---|
| 01 | {ref}`P-01 <p-01>`, {ref}`P-05 <p-05>` |
| 02 | {ref}`P-01 <p-01>`, {ref}`P-05 <p-05>` |
| 03 | {ref}`P-01 <p-01>`, {ref}`P-05 <p-05>` |
| 04 | {ref}`P-01 <p-01>`, {ref}`P-05 <p-05>` |
| 05 | {ref}`P-01 <p-01>`, {ref}`P-10 <p-10>`, {ref}`P-18 <p-18>`, {ref}`P-19 <p-19>` |
| 06 | {ref}`P-01 <p-01>`, {ref}`P-12 <p-12>`, {ref}`P-18 <p-18>`, {ref}`P-19 <p-19>` |
| 07 | {ref}`P-01 <p-01>`, {ref}`P-07 <p-07>`, {ref}`P-18 <p-18>`, {ref}`P-19 <p-19>` |
| 08 | {ref}`P-01 <p-01>`, {ref}`P-02 <p-02>`, {ref}`P-03 <p-03>`, {ref}`P-18 <p-18>`, {ref}`P-19 <p-19>` |
| 09 | {ref}`P-01 <p-01>`, {ref}`P-02 <p-02>`, {ref}`P-18 <p-18>`, {ref}`P-19 <p-19>` |
| 10 | {ref}`P-01 <p-01>`, {ref}`P-08 <p-08>`, {ref}`P-09 <p-09>`, {ref}`P-11 <p-11>`, {ref}`P-18 <p-18>`, {ref}`P-19 <p-19>` |
| 11 | {ref}`P-01 <p-01>`, {ref}`P-08 <p-08>`, {ref}`P-09 <p-09>`, {ref}`P-11 <p-11>`, {ref}`P-12 <p-12>`, {ref}`P-18 <p-18>`, {ref}`P-19 <p-19>` |
| 12 | {ref}`P-01 <p-01>`, {ref}`P-08 <p-08>`, {ref}`P-09 <p-09>`, {ref}`P-11 <p-11>`, {ref}`P-18 <p-18>`, {ref}`P-19 <p-19>` |
| 13 | {ref}`P-01 <p-01>`, {ref}`P-11 <p-11>`, {ref}`P-18 <p-18>`, {ref}`P-19 <p-19>` |
| 14 | {ref}`P-01 <p-01>`, {ref}`P-11 <p-11>`, {ref}`P-18 <p-18>`, {ref}`P-19 <p-19>` |
| 15 | {ref}`P-01 <p-01>`, {ref}`P-11 <p-11>`, {ref}`P-12 <p-12>`, {ref}`P-18 <p-18>`, {ref}`P-19 <p-19>` |
| 16 | {ref}`P-01 <p-01>`, {ref}`P-08 <p-08>`, {ref}`P-09 <p-09>`, {ref}`P-11 <p-11>`, {ref}`P-18 <p-18>`, {ref}`P-19 <p-19>` |
| 17 | {ref}`P-01 <p-01>`, {ref}`P-07 <p-07>`, {ref}`P-18 <p-18>`, {ref}`P-19 <p-19>` |
| 18 | {ref}`P-01 <p-01>`, {ref}`P-06 <p-06>` |
| 19 | {ref}`P-01 <p-01>`, {ref}`P-17 <p-17>` |
| 20 | {ref}`P-01 <p-01>`, {ref}`P-18 <p-18>`, {ref}`P-19 <p-19>` |

Globais sem classe própria: {ref}`P-04 <p-04>`, {ref}`P-13 <p-13>`, {ref}`P-14 <p-14>`, {ref}`P-15 <p-15>`, {ref}`P-16 <p-16>`, {ref}`P-20 <p-20>`, {ref}`P-21 <p-21>`, {ref}`P-22 <p-22>`, {ref}`P-23 <p-23>`, {ref}`P-24 <p-24>`, {ref}`P-25 <p-25>`, {ref}`P-26 <p-26>`, {ref}`P-27 <p-27>`, {ref}`P-28 <p-28>`, {ref}`P-29 <p-29>`, {ref}`P-30 <p-30>`, {ref}`P-31 <p-31>`.

## 3. Cada pendência: o que é, a fonte, o que a fecha e a evidência

(p-01)=
### P-01: GLOBAL (todas)

{bdg-danger}`PENDENTE P-01` {bdg-danger}`ALTA`

**Pendência.** Nenhum dado de bancada com o código da v1.15 (perfis, sorteio, compostas, entalhes contínuos, 08 a 90 ms, crista com fator, cópia em 100 ms): a última campanha é de 07/10

- **Fonte:** `ESTADO.md`; `relatorio-final.md` §1; `ROTEIRO_BANCADA.md` §0-§8
- **O que fecha:** BANCADA (roteiro de 10 blocos; estimativa do roteiro: 2 h a 3 h com um perfil, 2 h 30 a 3 h 30 com `todos`)
- **Conferência feita:** o `ROTEIRO_BANCADA.md` (490 linhas) existe na raiz e na `main`; nenhum bloco foi executado (nenhuma sessão posterior a 07/10 em `resultados/`: só `sessao_2026-10-07_*`, com mtime 12/10).

(p-02)=
### P-02: 08, 09

{bdg-danger}`PENDENTE P-02` {bdg-danger}`ALTA`

**Pendência.** Mecanismo da cópia/deslocamento do evento em 100,0 ms (quirks A22 e A25): a 08 a 50 Hz saiu em 100 ms em 3/3; a 09 tem impulso de 0,12-0,27 pu em 100,0-100,2 ms em 9/9. Cinco hipóteses em `modelo_lista_fonte.py`, nenhuma confirmada

- **Fonte:** `CHANGELOG/v1.15.md:354-380`; `relatorio-final.md` §3; relatório individual 15; `docs/quirks.md` A22, A25
- **O que fecha:** BANCADA (Blocos 4 e 6: `diag_marcadores_trace.py`, retrieve, recaptura)
- **Conferência feita:** `scripts/diag_ciclos_trace.py` (Bloco 3 do roteiro, offline) rodado hoje, com `--saida` fora do repositório, nas duas sessões reais: `sessao_2026-10-07_127V_50Hz` e `sessao_2026-10-07_14-59-54_run02`, classes 08 e 09. Resultado: carrega o formato 1 sem erro (código de saída 0 nas duas), o que fecha o NÃO VERIFICADO do relatório individual 15 ("carregamento de `.npz` bruto + reconstrução não exercitado com dado real"). Medidas: nenhuma captura com "ciclos trocados" pelo critério do script; resíduo máximo em torno de 100 ms: 08 a 50 Hz 1,887/1,887/1,321 pu; 08 a 60 Hz 0,034/0,034/0,040 pu; 09 a 50 Hz 0,281/0,148/0,181 pu; 09 a 60 Hz 0,151/0,114/0,237 pu. Isso **não** decide o mecanismo (a decisão exige os Blocos 4 e 6); as sessões não foram alteradas (mtime inalterado).

(p-03)=
### P-03: 08

{bdg-danger}`PENDENTE P-03` {bdg-danger}`ALTA`

**Pendência.** Recaptura a 127 V/50 Hz com impulso em 90 ms: posição (`abs(desvio)` ≤ 10 amostras), pico ≤ 374,2 V, sobressinal ≤ 0,55. Acima disso é achado de segurança

- **Fonte:** `CHANGELOG/v1.15.md:72-84`; `ROTEIRO_BANCADA.md` Bloco 6
- **O que fecha:** BANCADA
- **Conferência feita:** [experimentos_waveform/08.py:35,82-99](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L35) (`DISTANCIA_MIN_FRONTEIRA_AMOSTRAS = 30`; com sorteio ligado e frequência em que 80 ms cai na fronteira, o impulso vai ao meio do ciclo: 90 ms a 50 Hz; 80 ms a 60 Hz); `:39` (`TOLERANCIA_POSICAO_AMOSTRAS = 10`); `:181-216` (`conferir_posicao_do_evento`). Nenhuma sessão com este código.

(p-04)=
### P-04: GLOBAL

{bdg-danger}`PENDENTE P-04` {bdg-warning}`MÉDIA`

**Pendência.** `program_capture()` só AVISA quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga"); quem recusa é a pré-validação de `mestre.py` e o script de marcadores. Proposta: o ORM também recusar

- **Fonte:** `relatorio-final.md` §2.3 e decisão 2; relatório individual 15 achado
- **O que fecha:** DECISÃO DO USUÁRIO, depois CÓDIGO
- **Conferência feita:** [ametek_orm.py:1522-1527](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1522-L1527) (`logger.warning(... prosseguindo sem carga)`) e `:1597-1608` (idem por ciclo) confirmam; a recusa fica em [mestre.py:2123-2167](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2123-L2167) (`_indices_viaveis`, antes de qualquer SCPI) e `:1962-1979` (`_conferir_extremos_fisicos`, depois, com a captura já gravada).

(p-05)=
### P-05: 01-04

{bdg-danger}`PENDENTE P-05` {bdg-warning}`MÉDIA`

**Pendência.** Sorteio de posição nas nativas: disparo na fase sorteada (`TRIGger:SYNChronize:PHASe` em passos de 0,1°, sem readback), `:TIMebase:POSition` por captura, `PULSe:WIDTh` sorteada, `pre_trigger_desvio_amostras` (aviso > 2 amostras): nenhum foi medido

- **Fonte:** `CHANGELOG/v1.15.md:34,40,385-420`; relatório individual 20; `relatorio-final.md` §7.5
- **O que fecha:** BANCADA (Parte 1 da campanha e `verificar_sessao_bancada.py`)
- **Conferência feita:** [mestre.py:2955-2972](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2955-L2972) (nativa: pré-trigger por captura e `definir_fase_de_disparo`); [ametek_orm.py:844-855](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L844-L855) sem readback da fase; `scripts/verificar_sessao_bancada.py` só foi validado com sinais sintéticos (relatório individual 20).

(p-06)=
### P-06: 18

{bdg-danger}`PENDENTE P-06` {bdg-warning}`MÉDIA`

**Pendência.** Continuidade de fase na troca `start_hz` → `end_hz` do `LIST:FREQuency`; rampa 47 → 53 Hz a 50 Hz; `restaurar_frequencia_base` depois da rampa nova. Limiar de 10° é proposta sem dado

- **Fonte:** `CHANGELOG/v1.15.md:385-420`; relatório individual 20; `docs/tres_versoes.md:61`
- **O que fecha:** BANCADA
- **Conferência feita:** [experimentos_nativos/18.py:21-30](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/18.py#L21-L30) (`extremos_hz`: f0 ± 3 Hz com sorteio; 57 -> 63 Hz sem), `:45-51` (`configurar`); a restauração da frequência está em [ametek_orm.py:1050-1064](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1050-L1064) (`restaurar_frequencia_base`). Continuidade de fase na troca: sem leitura de volta (nenhum código a mede além de `verificar_sessao_bancada.py::continuidade_de_fase :138`, só testado com sinal sintético).

(p-07)=
### P-07: 07, 17

{bdg-danger}`PENDENTE P-07` {bdg-danger}`ALTA`

**Pendência.** Crista da validação física: fatores calibrados a 127 V/60 Hz (07 = 1,186; 17 = 1,031) não cobrem o toque simulado (≥ 1,344 e ≥ 1,420); a 1.ª rodada tende a reprovar só por "fator de crista". Recalibração ao fim do run vale só para o run seguinte

- **Fonte:** `CHANGELOG/v1.15.md:398-405,573-603`; relatórios individuais 20, 26; `ROTEIRO_BANCADA.md` Bloco 7
- **O que fecha:** BANCADA (rodar com `set recalibracao on`, `git diff`, commitar)
- **Conferência feita:** `logica/calibracao_extremos.json:16,25` (07 = 1,186; 17 = 1,031 a 127 V/60 Hz); [mestre.py:1896-1920](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1896-L1920) e [sinais.py:360-456](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L360-L456) (crista bilateral); [cli.py:895-927](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L895-L927) (recalibração ao fim do run, nunca diminui).

(p-08)=
### P-08: 10, 11, 12, 16

{bdg-danger}`PENDENTE P-08` {bdg-danger}`ALTA`

**Pendência.** Conferir na 1.ª sessão que `pico_medido_v`/`vale_medido_v` ≤ `extremo_previsto_v` depois da correção do rms CA por ciclo (previsão antiga subestimava até 38 %)

- **Fonte:** `CHANGELOG/v1.15.md:165-205`; relatório individual 11; `relatorio-final.md` §2.1; `ROTEIRO_BANCADA.md:343`
- **O que fecha:** BANCADA
- **Conferência feita:** [mestre.py:1962-1979](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1962-L1979) (`_conferir_extremos_fisicos` compara VMAX/VMIN medidos com o teto) e [ametek_orm.py:1416-1509](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1416-L1509) (`montar_programacao` com rms CA do ciclo): a correção existe; falta dado de bancada.

(p-09)=
### P-09: 10, 11, 12, 16 (e compostas com degrau no meio do ciclo)

{bdg-danger}`PENDENTE P-09` {bdg-secondary}`BAIXA`

**Pendência.** Resta a média de cada ciclo (erro programada × modelo 0,24-0,33 pu): só recuperável por offset por passo (ACDC, que tem o déficit de P-17). Decisão: investigar depois da bancada?

- **Fonte:** `relatorio-final.md` §2.1 e decisão 1; `ESTADO.md`
- **O que fecha:** DECISÃO DO USUÁRIO
- **Conferência feita:** `docs/manuais_txt/AMETEK_MX_SCPI_Programming_Manual.txt` não traz comando de offset por passo de `LIST` (busca por `LIST:` + `OFFSet` vazia; as ocorrências de "offset" são calibração e o modo AC+DC); `TRACe[:DATA]` "Query Syntax: none" em `:5862-5863`; "removes the dc component" / "When queried, trace data is returned as normalized values" em `:6823-6826`.

(p-10)=
### P-10: 05

{bdg-danger}`PENDENTE P-10` {bdg-warning}`MÉDIA`

**Pendência.** Nunca medidos: rms e THD da CSINusoid interna a 10/15/20 %; nível de 2 % (perfil `norma`); nível de 30 % por TRACe; modelo novo (senoide clipada) contra a bancada

- **Fonte:** `docs/classes.md:64`; `CHANGELOG/v1.15.md:531-533`; relatório individual 18
- **O que fecha:** BANCADA
- **Conferência feita:** [ametek_orm.py:163,945](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L163) (`MAX_CSINE_THD_PCT = 20,0`, recusa acima), [sinais.py:600-601](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L600-L601) (`corte_da_senoide_clipada` recusa THD > 25 %); o nível de 30 % sai por TRACe ([experimentos_nativos/05.py:69-70](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/05.py#L69-L70), `usar_trace`).

(p-11)=
### P-11: 10-16

{bdg-danger}`PENDENTE P-11` {bdg-warning}`MÉDIA`

**Pendência.** Manter ou reverter as extensões das compostas (a)-(f) (sag em 11/12, swell em 13/14, faixas da `norma`, `fronteira` alternada, THD em 13/15/16). Reverter muda o dataset e exige regravar `gerar_sorteio_v1_15.json`. Sem `parametros_com_disturbio_reduzido` na 15 (metadata sem THD/profundidade efetivos quando reduzida)

- **Fonte:** `relatorio-final.md` §7.4 e decisão 6; relatório individual 19
- **O que fecha:** DECISÃO DO USUÁRIO
- **Conferência feita:** `experimentos_waveform/15.py` não tem `parametros_com_disturbio_reduzido` (AST); as outras compostas (10-14, 16) têm; as faixas estão em [perfis.py:37-250](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L37-L250).

(p-12)=
### P-12: 06 (e 11, 15)

{bdg-danger}`PENDENTE P-12` {bdg-warning}`MÉDIA`

**Pendência.** Comparar a 06 com a forma programada (sem mudar dataset) ou redefinir o flicker com média nula por ciclo (muda `gerar()`, exige autorização em `AGENTS.md`). Efeito nas 11 e 15 não calculado

- **Fonte:** `relatorio-final.md` §7.3 e decisão 5; `CHANGELOG/v1.15.md:496-522`
- **O que fecha:** DECISÃO DO USUÁRIO
- **Conferência feita:** [experimentos_waveform/06.py:18-28](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/06.py#L18-L28) (`gerar`: profundidade e frequência sorteadas); a média por ciclo vem de `montar_programacao` (remove a média do ciclo, manual `TRACe:DATA` p. 147).

(p-13)=
### P-13: GLOBAL

{bdg-danger}`PENDENTE P-13` {bdg-secondary}`BAIXA`

**Pendência.** `sessao_io.recuperar_parcial` é função manual; ninguém a chama no início do `run`

- **Fonte:** `relatorio-final.md` §5 e decisão 3
- **O que fecha:** DECISÃO DO USUÁRIO, depois CÓDIGO
- **Conferência feita:** `grep recuperar_parcial\(`: só [logica/sessao_io.py:455](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L455) (definição) e dois testes ([tests/test_offline.py:8577,9418](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/tests/test_offline.py#L8577)).

(p-14)=
### P-14: GLOBAL

{bdg-danger}`PENDENTE P-14` {bdg-secondary}`BAIXA`

**Pendência.** `run 01 02` (espaço, sem vírgula) roda só a 01, sem aviso; `BATERIA_EXCLUIR` não vale para listas

- **Fonte:** `relatorio-final.md` §6 e decisão 4; relatório individual 13
- **O que fecha:** DECISÃO DO USUÁRIO
- **Conferência feita:** [cli.py:723-726](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L723-L726) (`texto = "".join(args)`; sem `,` nem `-` cai em `_run_uma(args[0])`) e `:737-738` (a lista usa `mestre._experiment_scripts()`, não `scripts_da_bateria_fisica()`).

(p-15)=
### P-15: GLOBAL

{bdg-danger}`PENDENTE P-15` {bdg-secondary}`BAIXA`

**Pendência.** `docs/operacao.md:122` e o relatório individual 22 dizem que o HTML do fim do run mostra só as 3 primeiras capturas por classe e perfil; no código ([sessao_io.py:771-776](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L771-L776), [relatorio_html.py:310](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/relatorio_html.py#L310)) o limite de 3 vale só para o dataset simulado (formato 2) e para o formato 1 empilhado; numa sessão de bancada em formato 2 entram todas as capturas, o que pode aumentar o HTML além dos 20 MB. Decidir: corrigir o texto ou limitar também na bancada (não executado com sessão real: NÃO VERIFICADO)

- **Fonte:** `relatorio-final.md` §8; relatório individual 22; `01-inventario.md` §6 divergência 7
- **O que fecha:** DECISÃO DO USUÁRIO

(p-16)=
### P-16: GLOBAL

{bdg-danger}`PENDENTE P-16` {bdg-warning}`MÉDIA`

**Pendência.** Rodar `tests.test_offline` no Windows. **Parcialmente resolvida hoje** (ver seção 2)

- **Fonte:** `relatorio-final.md` §8; `ROTEIRO_BANCADA.md` Bloco 1; relatório individual 21
- **O que fecha:** BANCADA (PC da bancada)
- **Conferência feita:** `tests.test_offline` rodado neste PC Windows (Windows 11 10.0.26200, Python 3.11.9, numpy 2.4.6, o mesmo da bancada segundo `requirements.txt:1`): `Ran 497 tests in 93.003s`, `OK`, **nenhum teste pulado** (`skip` não aparece na saída). Isso inclui os dois SHA-256 exatos, que só rodam no Windows, e as assinaturas portáveis gravadas no Linux. O que falta: o mesmo no PC da bancada (se for outra máquina: `C:\Users\denis\TCC\code` não existe aqui) com a calibração e o `git status` limpos da data da coleta.

(p-17)=
### P-17: 19

{bdg-danger}`PENDENTE P-17` {bdg-warning}`MÉDIA`

**Pendência.** Déficit de 5-6 % de CA em ACDC (0,938-0,951 pu); `diag_acdc_amplitude.py` pronto, nunca rodou; compensação `V/g` é proposta; 230 V no ACDC é escolha do dia

- **Fonte:** `docs/quirks.md` A19; relatório individual 20; `ROTEIRO_BANCADA.md` Bloco 5
- **O que fecha:** BANCADA
- **Conferência feita:** `scripts/diag_acdc_amplitude.py` existe (493 linhas, `Diag` `:190`, confirmação `ENERGIZAR-ACDC`); `docs/quirks.md` A19; `measure_voltage` em ACDC devolve RMS total ([ametek_orm.py:1963-1977](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1963-L1977), achado H-1 de `01-inventario.md`).

(p-18)=
### P-18: 01-20 TRACe

{bdg-danger}`PENDENTE P-18` {bdg-warning}`MÉDIA`

**Pendência.** Passo final `SINE` no `LIST` (PR #3, `18b144d`): `SINE` aceito em `LIST:FUNCtion:SHAPe`? Padrão LIGADO no branch (`AMETEK_PASSO_FINAL_SIN` = 1). Merge com a `main`: conflito textual só em `CHANGELOG/v1.15.md` e `tests/test_offline.py`; `ametek_orm.py` e `mestre.py` fundem sem conflito, mas a suíte do merge não foi rodada

- **Fonte:** `README.md:71-72`; `docs/versionamento.md:71`; `github/feat/passo-final-sin:docs/analise-2026-10-12/passo_final_sin.md`
- **O que fecha:** BANCADA (`scripts/teste_passo_final_sin.py`, `ENERGIZAR-PASSO-SIN`) e DECISÃO DO USUÁRIO (padrão desligado?)
- **Conferência feita:** `git diff d37e403 github/feat/passo-final-sin` toca 6 arquivos (457 inserções, 13 remoções); `git merge-tree d37e403 main github/feat/passo-final-sin`: "changed in both" em `CHANGELOG/v1.15.md` (conflito textual), `ametek_orm.py` (sem marcador), `mestre.py` (sem marcador), `tests/test_offline.py` (conflito textual). `AMETEK_PASSO_FINAL_SIN` default `True` no branch (`mestre.py`, +4 linhas no diff: leitura da variável e repasse a `AmetekMX30`; `ametek_orm.py`: parâmetro `passo_final_sin=True`).

(p-19)=
### P-19: GLOBAL (TRACe)

{bdg-danger}`PENDENTE P-19` {bdg-warning}`MÉDIA`

**Pendência.** A Rev. 5.53 aceita `TRACe:DATA? <nome>` e responde lista NRf separada por vírgula? O manual se contradiz (p. 126 "Query Syntax: none"; p. 147 "when queried... normalized"). Query nova numa fonte com histórico de travas

- **Fonte:** `CHANGELOG/v1.15.md:443-448`; relatório individual 16
- **O que fecha:** BANCADA (1.ª captura da 08 com `set diagnostico retrieve on` e painel à vista)
- **Conferência feita:** [ametek_orm.py:1353-1405](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1353-L1405) (`ler_trace`, recusa resposta que não seja lista de 1024 valores finitos) e [mestre.py:2169-2260](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2169-L2260) (leitura em `set diagnostico retrieve`): a consulta existe e não foi executada na fonte real.

(p-20)=
### P-20: GLOBAL

{bdg-danger}`PENDENTE P-20` {bdg-warning}`MÉDIA`

**Pendência.** Congelar a v1.15: tag `v1.15`, release no GitHub e Zenodo (não configurado); o projeto não tem `LICENSE` nem `CITATION.cff`

- **Fonte:** `docs/versionamento.md:33`; `AGENTS.md:260-265`
- **O que fecha:** DECISÃO DO USUÁRIO
- **Conferência feita:** `Get-ChildItem` da raiz: sem `LICENSE` nem `CITATION.cff`.

(p-21)=
### P-21: GLOBAL

{bdg-danger}`PENDENTE P-21` {bdg-warning}`MÉDIA`

**Pendência.** Condições sem tabela de extremos (220 V/60 Hz e outras) rodam com previsão conservadora (fator 1,475) e várias classes puladas; a 230 V/50 Hz a 03 fica de fora (416,4 V > 415,8 V). Calibrar a condição antes de coletar nela

- **Fonte:** `docs/operacao.md:85-91`; `docs/limites_e_calibracao.md:28-36`
- **O que fecha:** BANCADA (bateria na condição + `recalibrar_extremos.py --gravar`)
- **Conferência feita:** `logica/calibracao_extremos.json` tem as condições `127V_60Hz`, `230V_50Hz`, `127V_50Hz`; maior fator 1,475 (classe 16 a 127 V/60 Hz; a 230 V/50 Hz a 16 não tem fator); nenhuma tabela para 220 V ou 60 Hz fora de 127 V.

(p-22)=
### P-22: GLOBAL

{bdg-danger}`PENDENTE P-22` {bdg-secondary}`BAIXA`

**Pendência.** Tamanho e custo de reescrita do `NN_classe.npz` com medida física real (ruído de bancada comprime menos); capturas "espelho" (`set perfil todos`) são cópia, não 3 medidas

- **Fonte:** `CHANGELOG/v1.15.md:563-567,627`; relatórios individuais 17, 25
- **O que fecha:** BANCADA
- **Conferência feita:** [sessao_io.py:420](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L420) (`ArquivoDaClasse.consolidar` reescreve a classe inteira a cada fim de perfil) e `:177` (`espelhar`): tamanho do arquivo com medida real não medido.

(p-23)=
### P-23: GLOBAL

{bdg-danger}`PENDENTE P-23` {bdg-warning}`MÉDIA`

**Pendência.** Trava da fonte na ~280.ª gravação de TRACe por conexão (quirk A3; causa NÃO VERIFICADA). `README.md:26` e `AGENTS.md` ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `todos`); o roteiro usa listas (< 250 por conexão)

- **Fonte:** `docs/quirks.md` A3; `docs/operacao.md:79`; `ROTEIRO_BANCADA.md` §4-§5
- **O que fecha:** DECISÃO DO USUÁRIO (texto dos docs) e BANCADA (causa)
- **Conferência feita:** [mestre.py:3213](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3213) (`ESCRITAS_TRACE_REFERENCIA_TRAVA = 280`); [cli.py:495-497](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L495-L497) só avisa.

(p-24)=
### P-24: GLOBAL

{bdg-danger}`PENDENTE P-24` {bdg-warning}`MÉDIA`

**Pendência.** Documentação: 63 das 85 citações `arquivo:linha` conferidas em `classes.md`, `scpi.md` e `limites_e_calibracao.md` estão deslocadas; 8 documentos carimbados com `d37e403`; contagens de testes e classes desatualizadas; `quirks.md` B8 contradiz o código

- **Fonte:** `01-inventario.md` §5 e §6
- **O que fecha:** CÓDIGO (site com símbolos em vez de linhas; próxima etapa do site)
- **Conferência feita:** `01-inventario.md` §5 (85 citações, 22 exatas, 63 deslocadas) e §6.

(p-25)=
### P-25: GLOBAL

{bdg-danger}`PENDENTE P-25` {bdg-secondary}`BAIXA`

**Pendência.** Decisões menores da tarefa 22: identificadores de tarefa no texto (8 ocorrências hoje fora dos CHANGELOG fechados); um termo de governança em `AGENTS.md` (9 ocorrências); um nome de variável local em [mestre.py:2398,2412](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2398); texto de `uso_limite_bancada` em `calibracao_extremos.json:81` (muda o SHA-256 do arquivo)

- **Fonte:** relatório individual 22; `relatorio-final.md` §8 e decisão 7
- **O que fecha:** DECISÃO DO USUÁRIO
- **Conferência feita:** contagem por busca textual do identificador de tarefa: 8 ocorrências em 6 arquivos (`ROTEIRO_BANCADA.md` 2, `docs/decisoes.md` 1, `docs/limites_e_calibracao.md` 1, `docs/metadata.md` 1, `docs/tres_versoes.md` 1, `scripts/verificar_sessao_bancada.py` 2); o relatório individual 22 contava 25.

(p-26)=
### P-26: GLOBAL

{bdg-danger}`PENDENTE P-26` {bdg-warning}`MÉDIA`

**Pendência.** Escolhas do dia de bancada: um perfil ou `set perfil todos`; frequência da campanha (roteiro assume 60 Hz); ACDC a 230 V

- **Fonte:** `relatorio-final.md` decisão 8; relatório individual 23
- **O que fecha:** DECISÃO DO USUÁRIO
- **Conferência feita:** decisão sem conferência de código (escolha do dia da bancada).

(p-27)=
### P-27: GLOBAL

{bdg-danger}`PENDENTE P-27` {bdg-secondary}`BAIXA`

**Pendência.** A faixa de referência da correlação do distúrbio (0,95-1,00; 0,75-0,94; 0,005 da 08) vem de `validacao_gerador_v1.14.md`, que não está no repositório: a coluna "bate?" de `docs/correlacao_disturbio.md:38-58` compara contra origem desconhecida

- **Fonte:** `docs/correlacao_disturbio.md:80`
- **O que fecha:** DECISÃO DO USUÁRIO (fornecer o arquivo)
- **Conferência feita:** `validacao_gerador_v1.14.md` não existe em `git ls-files` da `main` nem em `git ls-tree -r github/arquivo/analises` (busca por `validacao_gerador`: nenhuma ocorrência).

(p-28)=
### P-28: GLOBAL

{bdg-danger}`PENDENTE P-28` {bdg-secondary}`BAIXA`

**Pendência.** Reamostragem do osciloscópio (~116,7 kSa/s → 30 kSa/s) por interpolação linear, sem anti-aliasing: efeito não quantificado (quirk K4)

- **Fonte:** `docs/quirks.md` K4; [oscilloscope_orm.py:536](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L536)
- **O que fecha:** BANCADA/OFFLINE (comparar com taxa bruta)
- **Conferência feita:** [oscilloscope_orm.py:536](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L536) (`np.interp(target_time, time_axis, values)`, sem filtro anti-aliasing); nenhum teste compara com a taxa bruta.

(p-29)=
### P-29: GLOBAL

{bdg-danger}`PENDENTE P-29` {bdg-warning}`MÉDIA`

**Pendência.** As transcrições SCPI reais (`scpi_transcricao.log`) das sessões de 07/10 existem só em `resultados/` desta máquina (gitignored; 3 arquivos, 6846 a 9675 linhas) e não estão em nenhum branch: o site precisa de exemplos reais por comando

- **Fonte:** `docs-site-plano/02-lacunas.md` §3
- **O que fecha:** DECISÃO DO USUÁRIO (versionar trechos selecionados ou autorizar a extração)
- **Conferência feita:** `Get-ChildItem` de `<repositório>\resultados` (gitignored) e contagem de linhas de `metadata/*.jsonl`.

(p-30)=
### P-30: GLOBAL

{bdg-danger}`PENDENTE P-30` {bdg-secondary}`BAIXA`

**Pendência.** Contagem de capturas de 07/10 incoerente: `AGENTS.md:125` e `CHANGELOG/v1.15.md:9` dizem 63; `docs/tres_versoes.md:59` diz 99; os arquivos têm 36 + 36 + 27 = 99 e `analisar_sessao.py` leu 99 capturas nas três sessões em 2026-10-15 (63 = só as duas sessões de 50 Hz, hipótese NÃO VERIFICADA)

- **Fonte:** `AGENTS.md:125`; `docs/tres_versoes.md:59`; `resultados/`
- **O que fecha:** DECISÃO DO USUÁRIO (o que é "piloto")
- **Conferência feita:** `Get-ChildItem` de `<repositório>\resultados` (gitignored) e contagem de linhas de `metadata/*.jsonl`.

(p-31)=
### P-31: GLOBAL (correlação)

{bdg-danger}`PENDENTE P-31` {bdg-secondary}`BAIXA`

**Pendência.** A correlação do distúrbio com a fundamental ajustada foi calculada hoje, offline, nas três sessões de 07/10 (99 capturas, tabela em `02-lacunas.md` §2.3), o que fecha o NÃO VERIFICADO de `docs/correlacao_disturbio.md:94` para essas sessões; falta calcular em sessão com sorteio e com os perfis da v1.15, e decidir qual das duas métricas o dataset publica

- **Fonte:** `docs/correlacao_disturbio.md:82,94`; `v1.15`
- **O que fecha:** BANCADA (qualquer sessão nova) e DECISÃO DO USUÁRIO (métrica oficial)
- **Conferência feita:** `python -I -X utf8 logica/analisar_sessao.py resultados/<sessao>` (Python do projeto, só leitura; mtime das pastas inalterado, `git status` limpo) nas sessões `sessao_2026-10-07_127V_50Hz`, `sessao_2026-10-07_14-59-54_run02` (127 V/60 Hz) e `sessao_2026-10-07_230V_50Hz`: saída 45, 45 e 36 linhas, código de saída 0, 99 linhas de captura no total. Os valores nominais reproduzem a tabela de `docs/correlacao_disturbio.md:37-58` (por exemplo 08 = 0,004-0,011 e 0,824-0,831). A coluna `corr. dist. fund.aj.` está em `02-lacunas.md` §2.3.

## 4. Decisões do usuário

Cada item abaixo é uma escolha que só o responsável pelo projeto faz. A página registra a pergunta e as opções; **não escolhe**.

| Id | Pergunta | Opções conhecidas |
|---|---|---|
| {ref}`P-04 <p-04>` | A gravação da TRACe (`program_capture`) deve recusar pico acima do limite, hoje só avisa? | (a) recusar também no ORM (validação mais forte, nunca mais fraca); (b) manter só a recusa de `mestre.py`. |
| {ref}`P-09 <p-09>` | Investigar, depois da bancada, recuperar a média de cada ciclo nas classes 10, 11, 12 e 16 por offset por passo em ACDC? | (a) investigar (esbarra no déficit de CA de 5 a 6 % da P-17); (b) aceitar a perda como limite físico do modo TRACe. |
| {ref}`P-11 <p-11>` | Manter ou reverter as extensões das compostas 10 a 16 (sag em 11 e 12, swell em 13 e 14, faixas da `norma`, `fronteira` alternada, THD em 13, 15 e 16)? | (a) manter, como decisão de projeto documentada em `docs/perfis.md`; (b) reverter, o que muda o dataset e exige regravar `tests/fixtures/gerar_sorteio_v1_15.json`. |
| {ref}`P-12 <p-12>` | Classe 06: comparar com a forma programada ou redefinir o flicker com média nula por ciclo? | (a) comparar com a programada, sem mudar o dataset; (b) mudar `gerar()` (exige autorização registrada em `AGENTS.md`). |
| {ref}`P-13 <p-13>` | Chamar `sessao_io.recuperar_parcial` automaticamente no início de cada `run`? | (a) sim; (b) manter manual. |
| {ref}`P-14 <p-14>` | `run 01 02` (com espaço) deve recusar em vez de rodar só a 01? `BATERIA_EXCLUIR` vale para listas? | (a) recusar e aplicar a exclusão; (b) manter. |
| {ref}`P-15 <p-15>` | Corrigir o texto (o HTML mostra todas as capturas numa sessão de bancada em formato 2) ou limitar também na bancada? | (a) corrigir `docs/operacao.md`; (b) limitar o relatório a 3 capturas por classe e perfil. |
| {ref}`P-20 <p-20>` | Congelar a v1.15 (tag `v1.15`, release no GitHub, Zenodo) e escolher licença e `CITATION.cff`? | decisão do responsável; o projeto não tem `LICENSE` nem `CITATION.cff`. |
| {ref}`P-23 <p-23>` | Atualizar o texto dos documentos que recomendam `run all` (468 gravações de TRACe a 60 Hz; 1116 com `set perfil todos`), acima da trava de cerca de 280 por conexão? | (a) recomendar listas de classes (< 250 gravações por conexão, como o roteiro); (b) manter. |
| {ref}`P-25 <p-25>` | Decisões menores de autocontenção: identificadores de tarefa no texto; um termo de governança em `AGENTS.md`; um nome de variável local em `mestre.py`; texto de `uso_limite_bancada` em `calibracao_extremos.json` (muda o SHA-256 do arquivo). | aceitar ou retirar, item a item. |
| {ref}`P-26 <p-26>` | Escolhas do dia de bancada: um perfil ou `set perfil todos`; frequência da campanha (o roteiro assume 60 Hz); ACDC a 230 V. | decidir antes de começar o roteiro. |
| {ref}`P-29 <p-29>` | Versionar trechos selecionados das transcrições SCPI ou manter só os exemplos citados na referência? | ver {doc}`../scpi/transcricoes`. |
| {ref}`P-30 <p-30>` | O que é "piloto": 63 ou 99 capturas de 07/10? | o texto diz 63 (`AGENTS.md`, `CHANGELOG/v1.15.md`); os arquivos têm 99 (36 + 36 + 27). |
| {ref}`P-31 <p-31>` | Qual das duas métricas de correlação (nominal ou com a fundamental ajustada) o dataset publica? | ver {doc}`../medicao/correlacao`. |

## 5. Resolvidas ou obsoletas (para não reaparecerem)

| Item | Estado | Evidência |
|---|---|---|
| `lowvoltage` dizia "5 Vrms" e pedia `ENERGIZAR-5V` com a tensão base digitada | RESOLVIDA em `ba24d45` | [cli.py:686-700](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L686-L700) pede `ENERGIZAR-TESTE` e mostra `BASE_VOLTAGE_RMS`; `preflight.py` não existe mais |
| Previsão de pico subestimava ciclos com degrau; `LIST:VOLTage` com rms com média | RESOLVIDA em `0a405e3` | [ametek_orm.py:1416-1509](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1416-L1509) (rms CA, pico da TRACe enviada, `_resample_cycle` periódico em `:1408-1413`); resta a média do ciclo (P-09) |
| `git_sujo` ignorava arquivo novo e era calculado uma vez por processo | RESOLVIDA em `928f4fd` | [mestre.py:121-171,220](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L121-L171); **`docs/quirks.md` B8 ainda descreve o comportamento antigo** (divergência registrada em `01-inventario.md`) |
| `run all` único passava da trava; sem como dividir | RESOLVIDA em `7219674` | [cli.py:209-246,728-753](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L209-L246) |
| Fixtures byte a byte só no Windows | RESOLVIDA em `c337e9b` | `tests/assinatura_portavel.py`; suíte passa no Windows sem pulos (P-16) |
| Um `.npz` por captura, três versões em pasta à parte | RESOLVIDA em `c6d3e0e` | `logica/sessao_io.py` (880 linhas) |
| `set perfil todos` capturava 3× as classes independentes | RESOLVIDA em `6a2add0` | [perfis.py:217-250](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L217-L250); [mestre.py:1273-1282](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1273-L1282) |
| Crista da 07/17 reprovada sem critério | PARCIAL em `006cdfe` | [mestre.py:1896-1920](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1896-L1920); o critério passa a depender da calibração; ver P-07 |
| Semente do AWGN e perfil por run sem registro | RESOLVIDA em `928f4fd` | [sinais.py:164-178,282-283](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L164-L178) |
| Diagnóstico da cópia em 100 ms sem ferramenta | PARCIAL em `6893cb5` e `be688b5` | ferramentas existem; mecanismo segue em P-02 |
| `set diagnostico retrieve` inexistente | PARCIAL em `c17fbb7` | [ametek_orm.py:1353-1405](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1353-L1405), [mestre.py:2169-2260](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2169-L2260); resposta real da fonte em P-19 |
| `docs/operacao.md:152` "NÃO VERIFICADO: a CLI relê `calibracao_extremos.json` a cada run" | RESOLVIDA por leitura de código | [mestre.py:566-590](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L566-L590) abre o arquivo a cada chamada e `:2011-2016` (`_fatores_extremo`) chama a cada avaliação; `preparar_pasta_da_sessao` (`:199-258`) copia a cada pasta. O documento ainda diz NÃO VERIFICADO |
| Relatório 23: "`operacao.md` §7 diz tentar 3 vezes e `AGENTS.md` diz não tentar de novo" | CONFORME, sem contradição | [mestre.py:1146](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1146) (`MAX_TENTATIVAS_POR_CLASSE = 3`) vale para `Exception` genérica (`:1221-1228`); `CommunicationError`/`FalhaFatalDeInstrumento` propagam sem retry (`:1206-1210`) e `ERROS_DETERMINISTICOS` não retentam (`:1211-1220`) |
| NÃO VERIFICADO: `diag_ciclos_trace.py` carrega as sessões reais de 07/10 | RESOLVIDA hoje | ver P-02, seção 2 |

## 6. Como esta página é mantida

Uma pendência que fecha **sai** das seções 1 a 3, passa para a seção 5 com a evidência e o commit, e o selo `PENDENTE P-NN` sai das páginas que a citavam; o id **não é reaproveitado**. Uma afirmação que dependia da pendência volta a valer com o selo certo (VERIFICADO NA BANCADA com sessão e condição, ou OFFLINE com comando e saída), nunca por omissão.
