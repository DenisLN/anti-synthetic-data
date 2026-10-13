# Horas de bancada por perfil (50 capturas por classe)

2026-10-12. Somente leitura: nada tocou o hardware nem o código. Cálculo reproduzível pelo script do item 2.

Observação sobre o pedido: a conta do professor assume 50 capturas por classe, mas `set capturas 50` na CLI significa 50 **por nível** (`cli.py:396` e `mestre.py:1427-1444`): 02, 03 e 05 têm 5 níveis no perfil norma/literatura e viram 250 capturas cada. Calculei as duas leituras (B = o que a CLI executa; A = 50 no total por classe, que a CLI não consegue pedir nas classes com níveis).

## 1. Tempo medido por captura (logs de 07/10)

Fonte: `resultados/sessao_2026-10-07_*/sessao.log` (a linha "captura i/n gravada" sai depois da validação física e do `_salvar_captura`, `mestre.py:2381-2405`, então o tempo entre duas dessas linhas já inclui validação e gravação em disco) e `scpi_transcricao.log` (resolução de ms). `run02` = 127 V / 60 Hz; `127V_50Hz` e `230V_50Hz` = 50 Hz.

| Tipo | 50 Hz | 60 Hz | Evidência |
|---|---|---|---|
| TRACE **com** gravação na Flash (N = 10 / 12 TRACes) | **20,4 s** (41 capturas, 20,0 a 21,7 s) | **24,3 s** (20 capturas, 23,9 a 24,7 s) | início-a-início do 1.º `TRACe:DATA` de capturas consecutivas, `scpi_transcricao.log` (`127V_50Hz` e `230V_50Hz`: início de cada bloco de 10 `TRACe:DATA` a partir da L878 e L686; `run02`: blocos de 12 a partir da L1165). Confere com `sessao.log` (`127V_50Hz` L44-45: 20 s e 20 s; `run02` L90, L97: 24 s e 24 s) |
| TRACE **sem** gravação (cache reaproveitado) | NÃO VERIFICADO em 50 Hz | 3,5 s (2 capturas) | `run02/sessao.log` L137, L146 ("TRACe idêntica ... reaproveitando"), 08 capturas 2/3 e 3/3 (4 s e 3 s). Este caso **deixa de existir** com o sorteio (toda captura TRACE tem forma única) e na 08 com `set capturas N` (rampa de amplitude, `08.py:112-114`) |
| Nativa (01-05, 18, 19) | 2,2 s (17 capturas, 1 a 4 s) | 2,7 s (11 capturas, 2 a 4 s) | `sessao.log` das três sessões, linhas de classes 01-05, 18, 19. Resolução de 1 s no log: erro de ±0,5 s |

Composição do tempo TRACE: cada `TRACe:DATA` custa 1,70 s entre escritas consecutivas (L1165 a L1220 do transcript do `run02`: 12 escritas em 18,7 s; `time.sleep(1.0)` + `*CLS` + transferência a 115200 baud, `ametek_orm.py:1377-1383`), e o resto da captura (LIST, trigger, aquisição, validação, disco) soma ~3,4 a 4 s. Na prática **2,0 s por ciclo da rede** (24,3 / 12 = 2,03; 20,4 / 10 = 2,04). A "≈ 20 s" do professor é exatamente o caso 50 Hz. A mensagem da CLI ("1 s por TRACe", `cli.py:317`) é um piso: o tempo real é ~2 s por TRACe.

Custos fixos por conexão (`Bancada.from_env`, aberta a cada `run`, `cli.py:513` e `cli.py:559`):

- Conexão: **18 s** do primeiro log ao "Instrumentos prontos" (`sessao.log` L1 a L5: 15:00:19 a 15:00:37 no `run02`; 15:56:47 a 15:57:05 no `127V_50Hz`; 15:47:07 a 15:47:25 no `230V_50Hz`). Os 15,5 s de espera estão antes de `OUTPut:STATe ON` (transcript `run02` L174).
- Redefinição dos slots TRACE: `bench_config.ps1:12` põe `AMETEK_CLEAR_USER_WAVEFORMS=1`, que apaga as TRACEs a cada conexão (`TRACe:DELete:ALL`, transcript `run02` L173); o 1.º uso de TRACE na conexão faz `TRACe:DEFine` + 3 s por slot (`ametek_orm.py:1229-1234`): 3 s × N = **30 s (50 Hz) / 36 s (60 Hz)**. Medido: 1.ª captura da 06 leva 51 s (50 Hz) e 61 s (60 Hz) contra 20 e 24 s das seguintes (`127V_50Hz/sessao.log` L33-L42 definem TCC00 a TCC09 e L43; `run02/sessao.log` L65-L76 e L83).
- Tempo do operador (digitar `EXECUTAR-CLASSE-NN`, conferências): NÃO VERIFICADO, não está nos logs; fica fora das horas abaixo.

Referência do travamento: a CLI usa 280 gravações de `TRACe:DATA` por conexão (`mestre.py:2797-2799`, `CHANGELOG/v1.13.md:55`). O contador conta só `TRACe:DATA` (`ametek_orm.py:1377`). O `run02` fez 276 escritas numa conexão sem travar (transcript: 23 capturas x 12, L1165 a L9445). Se `TRACe:DEFine` também conta para o limite: NÃO VERIFICADO.

## 2. Horas para 50 capturas por classe, 20 classes

Premissas (todas citadas acima): toda captura TRACE grava a Flash (sorteio ligado; 08 também, pela rampa de `set capturas`); TRACE = 13 classes (06 a 17 e 20) mais, na 05, só o nível de 30 % (`05.py:60-61`: 1 dos 5 níveis em literatura e fronteira, 0 na norma). Escritas por captura = ciclos = 10 (50 Hz) ou 12 (60 Hz) (`mestre.py:2810`).

Fórmula: `T = n_TRACE x t_TRACE + n_nativa x t_nativa + n_conexões x 18 s + n_conexões_com_TRACE x 3 s x N`, com t_TRACE = 20,41 / 24,30 s, t_nativa = 2,24 / 2,73 s (50 / 60 Hz).

**Uma classe de 50 capturas já passa de 280 gravações** (500 escritas a 50 Hz, 600 a 60 Hz), então não basta reconectar entre classes: cada classe TRACE tem de ser rodada em 2 conexões (50 Hz: 25 + 25 capturas, 250 escritas cada) ou 3 (60 Hz: 17 + 17 + 16, ~204 cada), cada uma com uma conexão nova. A CLI hoje só avisa ("Considere 'run <NN>' por partes", `cli.py:327`) e `run <NN>` roda a classe inteira numa conexão; partir uma classe exige, por exemplo, `set capturas` menor e `set seed` diferente em cada parte (NÃO TESTADO; não há opção de índice inicial). As classes nativas rodam numa conexão cada. Cálculo de conexões: por classe `ceil(escritas / 279)`.

Leitura B (`set capturas 50`, por nível) - horas totais (capturas + conexões + slots):

| Perfil | Capturas (TRACE + nativas) | Escritas Flash 50 Hz | Conexões 50 Hz | **Horas 50 Hz** | Escritas 60 Hz | Conexões 60 Hz | **Horas 60 Hz** |
|---|---|---|---|---|---|---|---|
| norma | 1600 (650 + 950) | 6500 | 33 | **4,7 h** | 7800 | 46 | **5,7 h** |
| literatura | 1600 (700 + 900) | 7000 | 34 | **4,9 h** | 8400 | 48 | **6,1 h** |
| fronteira | 1300 (700 + 600) | 7000 | 34 | **4,8 h** | 8400 | 48 | **5,8 h** |

Detalhe da literatura a 50 Hz: 700 x 20,41 = 14 287 s; 900 x 2,24 = 2 016 s; 34 x 18 = 612 s; 28 x 30 = 840 s; soma 17 755 s = 4,93 h. A 60 Hz: 700 x 24,30 = 17 010 s; 900 x 2,73 = 2 457 s; 48 x 18 = 864 s; 42 x 36 = 1 512 s; soma 21 843 s = 6,07 h. Sem o limite de 280 (uma conexão só) seriam 4,5 h e 5,4 h (literatura): o limite custa ~0,4 a 0,7 h de reconexão e redefinição de slots, mais o tempo do operador (NÃO VERIFICADO).

Leitura A (50 capturas no total por classe, 1000 capturas): norma 4,3 h (50 Hz) / 5,3 h (60 Hz); literatura e fronteira 4,3 h / 5,3 h (as duas coincidem, pois com 50 no total só difere a 05 e a fronteira não altera TRACE).

Mínimo teórico de conexões se o empacotamento pudesse cruzar classes: `ceil(escritas / 279)` = 24 a 31, mas `run all` e `run NN` não permitem: usei o plano por classe acima.

Reproduzir: o script usado está na sessão (scratchpad `calc.py`); os parâmetros são os da tabela do item 1.

## 3. Os três perfis e 127 V em 50 e 60 Hz: capturas puladas

Nenhum perfil muda o número de capturas puladas: **0 em todos**. Fonte: `docs/analise-2026-10-12/limites_perfis/{norma,literatura,fronteira}_127V_{50,60}Hz_cap5.md`; contagem de linhas "sim" na coluna "Cabe?" = total de linhas (`grep -c '| sim |'`): norma 160/160 e literatura 160/160 nas duas frequências, fronteira 130/130 nas duas; nenhuma linha "não". O último rodapé "Resumo" diz "N/N rodam" para as 20 classes.

O que muda de perfil para perfil é o **número de capturas** (fronteira tem 2 níveis em 02 e 03, 1300 em vez de 1600 na leitura B) e quantas vão por TRACE (norma: 05 inteira nativa), não quantas são puladas. Ressalvas: (a) o relatório foi gerado com `set capturas 5`, e a previsão não depende do número de capturas por nível, mas a 08 com `set capturas 50` percorre a rampa de amplitude até o máximo seguro, que é a captura 5/5 do relatório; (b) é previsão, não medição: na sessão de 07/10 a 08 a 127 V / 50 Hz foi abortada pela medição (376,0 V > teto 374,2 V, `127V_50Hz/sessao.log` L61), com a calibração da época (sem tabela para 127V_50Hz, L10). Se o relatório novo prevê que cabe (`literatura_127V_50Hz_cap5.md` L100-102, "sim") sem ter sido reconfirmado na bancada: NÃO VERIFICADO.

## 4. Parágrafo para o professor

Medindo os logs da sessão de 07/10, uma captura por TRACE (formas gravadas na Flash da AMETEK) leva cerca de 20 s a 50 Hz (10 gravações) e 24 s a 60 Hz (12 gravações), isto é, ~2 s por ciclo da rede, contra ~2,2 a 2,7 s numa captura nativa (PULSe, LIST, CSINe). Como o sorteio de início e fase faz toda captura TRACE gravar a Flash, 50 capturas por classe (`set capturas 50`, que na CLI vale por nível: 250 em SAG, SWELL e HARMONICS) dão cerca de 4,7 h (norma), 4,9 h (literatura) e 4,8 h (fronteira) a 127 V / 50 Hz, e 5,7, 6,1 e 5,8 h a 60 Hz, já contando 18 s por conexão e a redefinição das TRACEs após cada reconexão. O travamento na ~280.ª gravação pesa mais do que parecia: uma única classe TRACE de 50 capturas já faz 500 gravações a 50 Hz (600 a 60 Hz), então cada uma tem de ser partida em 2 (ou 3) conexões, o que dá 33 a 48 conexões por campanha. Os perfis quase não mudam a conta: a diferença vem do número de níveis (a fronteira só tem 2 níveis de sag e swell) e de a norma não usar TRACE na classe 05; em nenhum deles o relatório de limites prevê captura pulada a 127 V, em 50 ou 60 Hz. Fora das horas: o tempo do operador entre as conexões (confirmações digitadas), que não está nos logs.
