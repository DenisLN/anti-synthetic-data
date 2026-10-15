# 02. Lacunas contra o conjunto-alvo e inventário SCPI

Base: `main` em `fa82f49`, 2026-10-15. Conjunto-alvo da rodada: (a) ficha das 20 classes, (b) referência SCPI comando a comando, (c) correlação esperada por classe, (d) recalibração passo a passo, (e) pendências por classe. Linhas de `docs/` são de `fa82f49`; linhas de código são as atuais (as citadas pelos `docs/` estão deslocadas, ver `01-inventario.md` §5).

## 1. Lacunas em uma linha por item

| Item | Onde está hoje | O que falta |
|---|---|---|
| (a) Ficha das 20 classes | `docs/classes.md:11-32` (tabela de uma linha por classe), `:36-43` (diferenças de `experimentos.txt`), `:45-51` (capturas), `:53-60` (08), `:62-68` (05), `:70-72` (06), `:74-76` (09); `docs/perfis.md` (faixas); `experimentos.txt:1-166`; `CHANGELOG/v1.15.md` (diário); código `experimentos_*/NN.py` | só 05, 06, 08 e 09 têm seção própria; 01-04, 07, 10-20 têm uma linha. Não há, por classe: norma/definição, forma esperada, mecanismo na bancada passo a passo, parâmetros por perfil, limites de segurança, correlação esperada, medidas reais por condição, quirks aplicáveis, histórico, estado e pendências. `03-fontes-por-classe.md` junta as fontes das 20; falta escrever as 20 fichas |
| (b) Referência SCPI por comando | `docs/scpi.md:16-130` (tabelas por método, não por comando), `docs/quirks.md` (A1-A25, K1-K10), `docs/manuais_txt/` (texto dos manuais) | cada comando não tem página própria; os 24 comandos exigidos pela spec estão todos citados em `scpi.md`, mas misturados (seção 3.2 abaixo); nenhum tem exemplo real de transcrição; as linhas citadas estão 7 a 107 posições deslocadas (`01-inventario.md` §5); os comandos do Keysight não têm transcrição (`scpi_transcricao.log` só registra a fonte); `TRACe:DATA?` nunca rodou (P-19) |
| (c) Correlação esperada por classe | `docs/correlacao_disturbio.md:5-31` (definição), `:33-58` (tabela de 07/10 em 3 condições), `:60-65` (divergências), `:85-94` (fundamental ajustada), `:96-102` (05, 09, 06) | "esperada" hoje é só a coluna "faixa de referência" (`:37-58`), de origem ausente do repositório (P-27) e vazia para 01, 18 e 19; sem valor teórico por classe, sem tabela por perfil, sem o resultado da métrica ajustada (NÃO VERIFICADO, `:94`); o cabeçalho (`:3`) ainda diz "árvore NÃO commitada"; citações de linha antigas (`sinais.py:307` hoje 485; `:520` hoje 535) |
| (d) Recalibração passo a passo | `docs/limites_e_calibracao.md:24-43` (§4 e §5, resumo de 4 passos), `docs/operacao.md:143-163` (recalibração automática), `ROTEIRO_BANCADA.md:228-278` (Bloco 7), `scripts/recalibrar_extremos.py`, `cli.py:895-927` | não há um procedimento único com comando, saída esperada de cada passo, como ler a tabela, o que fazer quando a 1.ª rodada reprova a crista (P-07), nem como reverter; o motivo histórico (230 V/50 Hz, 17 previu 405 V e mediu 444 V) está em `limites_e_calibracao.md:32` e a fórmula só em código |
| (e) Pendências por classe | espalhadas: `ROTEIRO_BANCADA.md`, `docs/*.md` (seções NÃO VERIFICADO: `correlacao_disturbio.md:78-83`, `operacao.md:152`, `versionamento.md:22,41`, `tres_versoes.md`, `diagnostico.md:78-79`), `CHANGELOG/v1.15.md` (uma seção NÃO VERIFICADO por tema), `README.md:69-72` | sem lista única com id, classe, fonte, o que fecha e prioridade; `04-pendencias.md` entrega isso (31 ids); falta o site publicá-la com filtro por classe |

## 2. Detalhe por item

### 2.1 (a) Fichas das 20 classes

- Estado do material: cada classe tem de 1 a 4 fontes nos relatórios de 13/10 (`03-fontes-por-classe.md`), seções do CHANGELOG de v1.7 a v1.15 e código com `gerar()`/`configurar()`. Nenhuma classe tem verificação de bancada com o código da v1.15 (P-01); o mais recente é 07/10 (63 ou 99 capturas, P-30).
- Classes sem nenhum relatório próprio de 13/10 (só tabela e CHANGELOG): ver coluna "Relatórios" de `03-fontes-por-classe.md`.
- Dependência: a ficha de cada classe precisa de uma linha do tempo curta (qual versão a mudou e por quê); isso está no CHANGELOG, de forma dispersa (`03` já lista as seções).

### 2.2 (b) Referência SCPI

- Fonte única para o site: a tabela da seção 3 deste arquivo (comando, método e linha atuais, exemplo real, o que falta). O inventário foi obtido **por busca no código** (AST sobre `ametek_orm.py`, `oscilloscope_orm.py`, `mestre.py`, `preflight_new.py` e 10 scripts de `scripts/`: 188 formas de comando normalizadas) e não só pela lista da spec.
- Cobertura de `docs/scpi.md` sobre o código: das 188 formas, 72 não aparecem em `docs/scpi.md` por busca textual. Leitura manual dessas 72: 21 são abreviações do **simulador** (`FREQ:MODE`, `TRAC:DATA`, `*RST`, `SOURCE:FUNCTION:MODE`...), 5 são leituras de lista do simulador, 7 são formas do caminho real escritas diferente no texto (`SOURce:LIST:FUNCtion|VOLTage|DWELl|REPeat:POINts?`, `...:AMPLitude?`, `SOURce:FREQuency?`, em `scpi.md:52-53,90`), 5 são formas (`EXTernal:RANGe`, `EXTernal:UNITs`, `EXTernal:RANGe?`, `TIMebase:REFerence?`, `TIMebase:REFerence:LOCation?`) cobertas só em prosa (`scpi.md:118,120`), 32 vêm de scripts de diagnóstico, 1 é rótulo de medida do `preflight_new.py` e 1 é `CHANnel1:SCALe?` do `mestre.py`. **Em substância, só dois comandos do caminho principal faltam em `scpi.md`**: `CHANnel1:SCALe?` (`mestre.py:1094`, `Bancada.from_env`) e `:EXTernal:RANGe?` como leitura de volta (`oscilloscope_orm.py:380`).
- Comandos que existem **só em script de diagnóstico** e que `scpi.md` não cobre (por construção: o arquivo declara só `ametek_orm.py` e `oscilloscope_orm.py`): ver seção 3.4.
- Duas famílias diferentes no manual: abreviações como `SOUR:`, `VOLT:`, `FUNC:` aparecem no simulador (`ametek_orm.py:541-623`); o caminho real só envia as formas longas, e `_GRAVA_FLASH` aceita as curtas de TRACe (`:181-183`) enquanto `_SEM_SINCRONISMO` não (`:178`), risco latente H-3 de `01-inventario.md`.

### 2.3 (c) Correlação esperada

- Existente: função `sinais.correlacao_disturbio` (`sinais.py:485`) e `correlacao_disturbio_fundamental_ajustada` (`:535`); `analisar_sessao._correlacao_disturbio_alinhada` (`analisar_sessao.py:190`); colunas no terminal e no HTML.
- Tabela medida (07/10, sem sorteio): `docs/correlacao_disturbio.md:37-58`. Divergências já assinaladas: 06 (0,83-0,96 contra 0,95-1,00), 20 (duas capturas a 60 Hz abaixo de 0,95), 03 (0,943/0,945 contra 0,94), 08 a 127 V/60 Hz (0,82-0,83 contra 0,005).
**Medida de hoje (VERIFICADO OFFLINE; dado de bancada de 07/10, código de `fa82f49`).** `python logica/analisar_sessao.py resultados/<sessao>` nas três sessões (99 capturas; reconstruídas sem sorteio, como em `correlacao_disturbio.md:35`), formato `nominal / fundamental ajustada` (intervalo quando a classe tem várias capturas); a coluna nominal reproduz `correlacao_disturbio.md:37-58`:

| classe | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| 01 | n/a / n/a | n/a / n/a | n/a / n/a |
| 02 | 0,999 / 0,999 | 0,997 / 0,996 | — |
| 03 | 0,945 / 0,926 | 0,943 / 0,920 | — |
| 04 | 0,999 / 0,999 | 0,996-0,997 / 0,995-0,997 | — |
| 05 | 0,504 / 0,506 | 0,503 / 0,506 | 0,499 / 0,504 |
| 06 | 0,826-0,935 / 0,831-0,940 | 0,878-0,960 / 0,882-0,964 | 0,836-0,945 / 0,838-0,948 |
| 07 | 0,916-0,942 / 0,917-0,942 | 0,912-0,924 / 0,917-0,930 | 0,899-0,922 / 0,907-0,924 |
| 08 | 0,004-0,011 / 0,001-0,006 | 0,824-0,831 / 0,831-0,839 | — |
| 09 | 0,749-0,797 / 0,799-0,854 | 0,883-0,910 / 0,932-0,938 | 0,850-0,925 / 0,857-0,934 |
| 10 | 0,999 / 0,999 | 0,975 / 0,966 | 0,998 / 0,997 |
| 11 | 0,999 / 0,998 | 0,969 / 0,957 | 0,996 / 0,995 |
| 12 | 0,998 / 0,997 | 0,967 / 0,959 | 0,998 / 0,998 |
| 13 | 0,996 / 0,996 | 0,976 / 0,972 | 0,997 / 0,997 |
| 14 | 0,989 / 0,988 | 0,961 / 0,955 | 0,972 / 0,972 |
| 15 | 0,988 / 0,989 | 0,991 / 0,991 | 0,988 / 0,988 |
| 16 | 1,000 / 1,000 | 0,972 / 0,960 | — |
| 17 | 0,914-0,923 / 0,923-0,931 | 0,921-0,931 / 0,925-0,933 | 0,902-0,918 / 0,912-0,924 |
| 18 | 0,982 / 0,964 | 0,939 / 0,960 | 0,982 / 0,964 |
| 19 | n/a / n/a | n/a / n/a | n/a / n/a |
| 20 | 0,954-0,957 / 0,966-0,969 | 0,907-0,966 / 0,918-0,975 | 0,975-0,981 / 0,978-0,983 |

Leitura: a ajustada sobe nas classes de distúrbio pequeno (09, 20, 17, 07, 06) e desce nas de evento grande ou que mexem na fundamental (03, 10-14, 16 a 127 V/60 Hz, 18 a 50 Hz), como previsto em `correlacao_disturbio.md:92-94`; o ganho real da 09 (0,749-0,797 para 0,799-0,854 a 127 V/50 Hz) é maior que a estimativa daquele texto (0,750 para 0,800 etc.) só em parte. Isto **não** foi comparado com a faixa de referência (origem ausente, P-27) nem medido com sorteio ligado (P-31).

- Faltam para a página do site: (1) a **definição** de "esperado" por classe (valor teórico quando existe: a 05 dá 0,50 por construção; a 08 depende do alinhamento de 1 amostra; 01 e 19 são degeneradas); (2) o efeito do perfil e do sorteio (nenhuma sessão real com sorteio foi analisada, `correlacao_disturbio.md:82`); (3) a origem da faixa (P-27); (4) a métrica ajustada medida em dado real (P-31 em `04`).

### 2.4 (d) Recalibração

- Procedimentos hoje, três descrições do mesmo fato: `limites_e_calibracao.md` §5, `operacao.md` §9 e `ROTEIRO_BANCADA.md` Bloco 7. Código: `scripts/recalibrar_extremos.py` (`coletar` `:118`, `recalibrar` `:214`, fator = max(|VMAX|, |VMIN|) ÷ pico programado, nunca diminui salvo `--substituir`, 08 e simuladas de fora), `cli.py:895-927` (`_recalibrar_ao_fim`).
- Falta: sequência única com comando, saída de exemplo e critério de aceitação; a relação com a crista da validação (spec 26, `mestre.py:1896-1920`); o que acontece com condição sem tabela (usa o maior fator já medido, 1,475 hoje); como reverter (`git checkout logica/calibracao_extremos.json`; NÃO VERIFICADO no fluxo real, é inferência do `git diff` recomendado em `limites_e_calibracao.md:43`); quando recalibrar manualmente (P-07, P-21).

### 2.5 (e) Pendências

- Ver `04-pendencias.md`: 31 pendências abertas (P-01 a P-31), 14 itens na seção 3 (resolvidos, parciais ou conferidos) e o mapa decisões do relatório final → ids.
- Faltam no site: página "Pendências" gerada por classe, com selo PENDENTE e link para a ficha; as seções NÃO VERIFICADO dos `docs/` precisam virar avisos padronizados (nota de verificação, decisão em aberto) apontando para o id.

## 3. Inventário SCPI

A tabela 3.1 tem 78 linhas e a 3.2 tem 29 (algumas linhas agrupam comandos de uma mesma função). Convenções: "Método:linha" = função e linha do primeiro envio hoje; "scpi.md" = linha de `docs/scpi.md` onde o comando consta (— = ausente); "Ex." = id do exemplo real da seção 4 (— = sem exemplo; a causa vem na coluna "Falta"). Comandos da AMETEK são enviados por `AmetekMX30.write/query`, que gravam a transcrição; os do Keysight vão por PyMeasure e não são transcritos.

### 3.1 AMETEK MX30-3Pi: comandos do caminho real

| Comando | Método:linha | scpi.md | Ex. | Falta |
|---|---|---|---|---|
| `OUTPut:STATe OFF` | `connect :350`; `safe_shutdown :1937-1961` | 18 | E53 | primeiro comando de toda conexão; só 1 exemplo |
| `OUTPut:STATe ON` | `energize_baseline :706-726` | 47 | E01 | exige `authorize_output` (H-4) |
| `OUTPut:STATe?` | `output_enabled :695-698`; `arm_transient :1846`; `safe_shutdown :1948` | 25 | E02 | |
| `*IDN?` | `connect :351` | 19 | E56 | resposta real traz modelo `MX30-3Pi` e `Rev 5.53` |
| `*CLS` | baseline `:1256`; `program_capture :1549,1616`; `recuperar_estado_seguro` (`mestre.py:1450`) | 21 | E03 | |
| `*ESR?` | `write :437`; `_sincronizar_apos :451-478` | 22 | E53 | sincronismo padrão; é o comando mais frequente da transcrição |
| `*OPC?` | `_sincronizar_apos :454,468,470` (só com `AMETEK_SINCRONISMO=OPC`) | 22 | — | não usado na bancada (A17: sem ganho; `wait_ready :1198` diz que a Rev. 5.53 não respondeu) |
| `*WAI` | `configure_harmonics_csine :975,985`; `select_sine_shape :1009`; `enable_dc_offset :1131`; `arm :1736`; `arm_transient :1884` | 23 | E04 | |
| `*TRG` | `trigger :1910-1922` | 73 | E42 | |
| `SYSTem:ERRor?` | `check_errors :633-645`; `write :444` | 20 | E55 | a resposta `0,"No error"` é a única |
| `STATus:OPERation:CONDition?` | `_log_diagnostico :670` | 24 | E46 | bit 3 = transiente; resposta 24 no exemplo |
| `ABORt` | baseline `:1258`; `program_capture :1541`; `safe_shutdown :1942,1952` | 33, 83 | E05 | |
| `INSTrument:COUPle ALL` | baseline `:1259` | 34 | E51 | |
| `SOURce:MODE AC` / `ACDC` | baseline; `disable_dc_offset :1030`; `enable_dc_offset :1131`; `program_capture :1553` | 35, 67-68, 83 | E63, E09 | `SOURce:MODE?` não existe (`scpi.md:101`) |
| `SOURce:VOLTage:RANGe` | baseline `:1261` | 36 | E64 | |
| `SOURce:VOLTage:HIGH` | baseline `:1262` | 37 | E06 | é limite RMS (v1.12) |
| `SOURce:CURRent` | baseline `:1263` | 38 | E65 | |
| `SOURce:CURRent:PROTection:STATe` | baseline `:1264` | 38 | E52 | |
| `SOURce:CURRent:PROTection:DELay` | baseline `:1265` | 38 | E66 | |
| `SOURce:FUNCtion:SHAPe SINusoid` | baseline `:1266`; `select_sine_shape :1010` | 39, 66 | E07 | |
| `SOURce:FUNCtion:SHAPe CSINusoid` | `configure_harmonics_csine :965` | 65, 99 | E08 (valor `:CSINusoid 5`) | forma curta `CSINe` dá `-256` |
| `SOURce:FUNCtion:SHAPe:CSINusoid <THD>` | `configure_harmonics_csine :976,986` | 65 | E08 | THD 0-20 % (`MAX_CSINE_THD_PCT`, `:163`) |
| `FUNCtion:MODE FIXed` | baseline `:1267`; `_neutralizar_transientes_residuais :835,841`; `program_capture` | 40, 58 | E61 | |
| `FUNCtion:MODE LIST` | `program_capture :1668` | 86 | E38 | |
| `FUNCtion:MODE?` | `trigger_step :901`; `_conferir_transiente_programado :1789`; `arm_transient :1847` | 72, 90 | E18 | |
| `VOLTage:MODE FIXed` | baseline `:1268`; `frequency_drift_list :1092`; `program_capture :1551` | 40, 69 | E62 | |
| `VOLTage:MODE STEP` | `trigger_step :896` | 62 | E11 | |
| `VOLTage:MODE PULSe` | `trigger_pulse :925` | 63 | E12 | |
| `VOLTage:MODE LIST` | `frequency_drift_list :1106`; `program_capture :1669` | 69, 86 | E39 | |
| `VOLTage:MODE?` | `trigger_step :899`; `trigger_pulse :929`; `arm_transient :1848` | 72, 90 | E17 | |
| `VOLTage:TRIGgered <V>` | `trigger_step :897`; `trigger_pulse :926` | 62-63 | E13 | a fonte trunca a 0,1 V (v1.12 N3) |
| `VOLTage:TRIGgered?` | `trigger_step :900`; `_conferir_transiente_programado` | 72 | E15 | |
| `PULSe:WIDTh <s>` | `trigger_pulse :927` | 63 | E14 | |
| `PULSe:WIDTh?` | `trigger_pulse :931` | 72 | E16 | |
| `SOURce:FREQuency:MODE FIXed` | baseline `:1269`; `_neutralizar... :842`; `restaurar_frequencia_base :1061` | 40, 70 | E60 | |
| `SOURce:FREQuency:MODE?` | `trigger_step :902`; `arm_transient :1849` | 72, 90 | E47 | |
| `FREQuency:MODE LIST` | `frequency_drift_list :1094` | 69 | E20 | |
| `SOURce:FREQuency:SLEW MAXimum` | baseline `:1270` | 41 | E67 | |
| `SOURce:VOLTage:SLEW MAXimum` | baseline `:1271` | 41 | E68 | |
| `SOURce:FREQuency <Hz>` | baseline `:1272`; `frequency :755`; `restaurar_frequencia_base :1062` | 42, 53, 70 | E48 | |
| `SOURce:FREQuency?` | `frequency :748` | 53 | — | nunca consultado nas sessões de 07/10 |
| `SOURce:VOLTage 0` / `<V>` | baseline `:1273`; `program_capture :1559` | 42, 83 | E49 | baseline deixa a saída a 0 V |
| `SOURce:VOLTage:LEVel:IMMediate:AMPLitude <V>` / `?` | `voltage :729-742` (`:741` escrita, `:732` leitura) | 52 | E71 | |
| `SOURce:CURRent:LEVel:IMMediate:AMPLitude <A>` / `?` | `current_limit :762,771` | 54 | — | não usado nas sessões de 07/10 |
| `SOURce:VOLTage:OFFSet <V>` | `disable_dc_offset :1022,1029,1032`; `enable_dc_offset`; `program_capture :1561` | 67-68, 83 | E10 | só aceito em `ACDC` (A10) |
| `TRIGger:SOURce BUS` | baseline `:1274`; `program_capture :1670` | 43, 86 | E50 | |
| `TRIGger:SOURce?` | `arm_transient :1854` | 90 | E44 | |
| `TRIGger:SYNChronize:SOURce PHASe` | baseline `:1275`; `program_capture :1671` | 44, 86 | E59 | |
| `TRIGger:SYNChronize:PHASe <°>` | `definir_fase_de_disparo :846-855`; baseline e `program_capture` com 0 | 44, 64 | E19 | sem consulta de volta (`scpi.md:102`; P-05) |
| `TRIGger:STATe?` | `aguardar_idle :775,797`; `arm :1742`; `arm_transient :1833` | 26 | E43 | |
| `OUTPut:TTLTrg:MODE TRIG` | baseline `:1277`; `program_capture :1673` | 45, 86 | E40 | |
| `OUTPut:TTLTrg:SOURce BOT` | baseline `:1278`; `program_capture :1674` | 45, 86 | E57 | |
| `OUTPut:TTLTrg ON` | baseline `:1279`; `program_capture :1675` | 45, 86 | E58 | |
| `INITiate:IMMediate` | `arm :1737,1738`; `arm_transient :1888,1890` | 72, 90 | E41 | ignorado fora de IDLE (`-220`, `:1766`) |
| `LIST:FREQuency a,b` | `frequency_drift_list :1095` | 69 | E21 | forma sem `SOURce:` |
| `LIST:VOLTage v,v` | `frequency_drift_list :1096` | 69 | E22 | |
| `LIST:DWELl d,d` | `frequency_drift_list :1097` | 69 | E23 | |
| `SOURce:LIST:REPeat 0,...,0` | `frequency_drift_list :1103`; `program_capture :1665` | 69, 86 | E24 | `LIST:REPeat:COUNt` dá `-113` (`scpi.md:100`) |
| `LIST:COUNt 1` | `frequency_drift_list :1104` | 69 | E25 | |
| `LIST:STEP AUTO` | `frequency_drift_list :1105` | 69 | E26 | |
| `SOURce:LIST:FUNCtion:SHAPe TCC00,...` | `program_capture :1644` | 85 | E31 | |
| `SOURce:LIST:VOLTage v0,...` | `program_capture :1645` | 85 | E32 | |
| `SOURce:LIST:DWELl d,...` | `program_capture :1646` | 85 | E33 | |
| `SOURce:LIST:FUNCtion:POINts?` | `program_capture :1644`; `arm_transient :1850` | 85, 90 | E34 | |
| `SOURce:LIST:VOLTage:POINts?` | `program_capture :1645`; `arm_transient :1851` | 85, 90 | E69 | |
| `SOURce:LIST:DWELl:POINts?` | `program_capture :1646`; `arm_transient :1852` | 85, 90 | E70 | |
| `SOURce:LIST:REPeat:POINts?` | `arm_transient :1853` | 90 | E35 | |
| `SOURce:LIST:COUNt 1` | `program_capture :1666` | 86 | E36 | |
| `SOURce:LIST:STEP AUTO` | `program_capture :1667` | 86 | E37 | |
| `TRACe:CATalog?` | `_trace_catalog :1319-1334` | 84 | E27 | resposta real `"SINE,SQUARE,CLIPPED"` antes de definir `TCC00` |
| `TRACe:DEFine TCCnn` | `_ensure_trace_slots :1335-1352` | 84 | E28 | ~3 s de espera, sem `*ESR?` |
| `TRACe:DATA TCCnn,<1024 valores>` | `program_capture`; comando montado em `ProgramacaoCaptura.comando_trace :122` | 84 | E29 | ~11,7 kB; transcrição trunca em 160 caracteres; manual p. 126/147 |
| `TRACe:DATA? <nome>` | `ler_trace :1353-1405` (`:1356,1383`) | 94 | — | **nunca executado na fonte real** (P-19) |
| `TRACe:DELete:ALL` | `clear_all_traces :1303-1317` | 92 | E30 | ~15 s sem consultar; só com a saída desligada |
| `MEASure:VOLTage:AC?` | `measure_voltage :1963-1977` | 55 | E45 | em ACDC é RMS total (H-1) |
| `MEASure:CURRent:AC?` | `measure_current :1980` | 55 | — | captura de corrente desligada por padrão |
| `MEASure:POWer:AC:REAL?` | `measure_power_w :1983` | 55 | — | não usado nas sessões de 07/10 |
| `MEASure:POWer:AC:PFACtor?` | `measure_power_factor :1986` | 55 | — | idem |

**Os 24 itens exigidos pela spec**, cobertura em `scpi.md` e exemplo: `TRACe:DATA` (84; E29), `TRACe:DEFine` (84; E28), `TRACe:DELete` (92, só `:ALL`; E30), `TRACe:CATalog?` (84; E27), `SOURce:LIST:VOLTage` (85; E32), `SOURce:LIST:FREQuency` (69, como `LIST:FREQuency`; E21), `SOURce:LIST:FUNCtion:SHAPe` (85; E31), `SOURce:LIST:DWELl` (85; E33), `SOURce:LIST:COUNt` (86; E36), `SOURce:LIST:STEP` (86; E37), `VOLTage:MODE LIST/STEP/PULSe/FIXed` (86/62/63/40; E39/E11/E12/E62), `FUNCtion:MODE` (40, 86; E61, E38), `SOURce:FUNCtion:SHAPe CSINusoid` e `:CSINusoid` (65; E08), `SOURce:MODE ACDC` (67; E09) com `SOURce:VOLTage:OFFSet` (67; E10), `TRIGger:SYNChronize` (44; E59, E19), `OUTPut:TTLTrg` (45; E40, E57, E58), `*TRG` (73; E42), `*WAI` (23; E04), `*ESR?` (22; E53). Todos têm exemplo real em 07/10; **nenhum** tem entrada própria. `SOURce:LIST:SHAPe` não existe: a forma da lista é `SOURce:LIST:FUNCtion:SHAPe`.

### 3.2 Keysight DSO-X 4034A (`oscilloscope_orm.py` e uma consulta em `mestre.py`)

Sem transcrição na sessão: `scpi_transcricao.log` contém 0 ocorrências de `TIMebase`, `WAVeform` ou `:ACQuire` (busca em `sessao_2026-10-07_127V_50Hz`). Os exemplos do osciloscópio só existem nos logs de nível debug do PyVISA, que não foram versionados: tudo abaixo está sem exemplo real (NÃO VERIFICADO além do código e do manual).

| Comando | Método:linha | scpi.md | Falta |
|---|---|---|---|
| `*IDN?` | `verify_identity :78-84` | 111 | |
| `:SYSTem:ERRor?` | `check_errors :86-98` | 112 | |
| `:STOP` | `initialize_safe :106`; `configure_acquisition :238`; `safe_stop :541` | 113, 117, 128 | |
| `*CLS` | `initialize_safe :107` | 113 | |
| `:ACQuire:TYPE NORMal` | `initialize_safe :108`; `configure_acquisition :239` | 113, 117 | |
| `:ACQuire:MODE RTIMe` | `configure_acquisition :240` | 117 | |
| `:ACQuire:DIGitizer OFF` | `configure_acquisition :241` | 117 | descartado como modo (v1.10) |
| `:TIMebase:MODE MAIN` | `configure_acquisition :242` | 117 | |
| `:TIMebase:RANGe <s>` / `?` | `configure_acquisition :243,268` | 117 | 200 ms ou 270 ms |
| `:ACQuire:POINts:ANALog:AUTO ON` e `:SRATe:ANALog:AUTO ON` | `configure_acquisition :253-254` | 117 | |
| `:ACQuire:POINts:ANALog?` e `:SRATe:ANALog?` | `configure_acquisition :266-267`; `sample_rate :445` | 117 | ≥ 0,995 × 30 kSa/s |
| `:WAVeform:POINts:MODE RAW`/`NORMal` | `initialize_safe :111`; `configure_acquisition :255`; `get_waveform :454` | 113, 117, 127 | RAW na inicialização, NORMal na aquisição |
| `:WAVeform:POINts 60000` | `configure_acquisition :256`; `get_waveform :455` | 117 | |
| `:WAVeform:FORMat BYTE` / `:UNSigned ON` | `initialize_safe :109-110`; `configure_acquisition :257-258`; `get_waveform :452-453` | 113, 117, 127 | |
| `:WAVeform:SOURce` | `get_waveform :451` | 127 | |
| `:WAVeform:PREamble?` | `get_waveform :458` | 127 | 10 campos |
| `:WAVeform:DATA?` | `get_waveform :478` | 127 | ≥ 6000 pontos, rejeita 0, 1 e 255 |
| `:CHANnel<n>:DISPlay/PROBe/COUPling/UNITs/OFFSet/SCALe/BWLimit` | `OscChannel` (`:26-68`), `configure_channel :114-137`, `disable_channel :139`, `set_vertical_scale :145-175` | 114-116 | `OscChannel.display` só como setter (K9) |
| `CHANnel1:SCALe?` | `mestre.py:1094` (`Bancada.from_env`) | — | **ausente de `scpi.md`** |
| `:MEASure:VMAX?`/`:VMIN?` `CHANnel1` | `medir_extremos :181-207` | 126 | `9.9E37` = inválido |
| `:MEASure:VRMS? DISPlay,AC,CHANnel1` | `medir_vrms_forcado :395-414` | 125 | |
| `:TIMebase:REFerence CUSTom` / `LEFT`, `:REFerence:LOCation 0.0`, leituras | `_programar_referencia_horizontal :295-337` | 118 | `LEFT` + compensação de `RANGe/10` |
| `:TIMebase:POSition` | `_programar_referencia_horizontal :300,328`; `definir_pre_trigger :339-354` | 118-119 | |
| `:EXTernal:PROBe/UNITs/RANGe` | `setup_external_trigger :368-370` | 120 | |
| `:EXTernal:RANGe?` | `setup_external_trigger :380` | — | **leitura ausente de `scpi.md`** |
| `:TRIGger:HFReject/MODE/SWEep/EDGE:SOURce/LEVel/SLOPe` | `setup_external_trigger :371-376` | 120 | |
| `:AER?`, `:TER?`, `:SINGle` | `arm :387-389`; `wait_for_trigger_complete :435` | 121, 123 | |
| `:OPERegister:CONDition?` | `is_armed :417`; `wait_for_trigger_complete :436` | 122-123 | bit 32 (armado) e bit 8 (run) |
| `:TRIGger:FORCe` | `force_trigger :393` | 124 | |

### 3.3 Cobertura dos manuais

- AMETEK: `docs/manuais_txt/AMETEK_MX_SCPI_Programming_Manual.txt` (494.011 bytes), páginas citadas em `scpi.md` (coluna "Manual", p. 7 a 154). Ambiguidade conhecida do manual: `TRACe[:DATA]` "Query Syntax: none" (`:5862-5863`) contra "when queried, trace data is returned as normalized values" (`:6823-6826`), P-19.
- Keysight: `docs/manuais_txt/Keysight_4000X_Programmers_Guide.txt` (3.283.969 bytes); `scpi.md` cita `[KS] p.` só no cabeçalho (`:107`), sem página por comando (lacuna).

### 3.4 Comandos que só aparecem em scripts (não passam por `ametek_orm.py`)

| Origem | Comandos |
|---|---|
| `diag_acdc_amplitude.py` | `MEASure:VOLTage:DC?` (`:130`, cinco usos), `SOURce:VOLTage:RANGe?` (`:269`) |
| `diag_nativo_output_off.py` | `*OPT?`, `*STB?`, `SYSTem:CONFigure?`, `STATus:QUEStionable:CONDition?`, `SOURce:VOLTage:HIGH?`, `PULSe:PERIod`, `PULSe:COUNt`, `PULSe:DCYCle?`, `PULSe:HOLD?` e variantes `?` (`:136-176,333-354,461-462`) |
| `diag_fonte_vs_osciloscopio.py` | `INSTrument:NSELect` (`:63`), `MEASure:VMAX?` do osciloscópio (`:66`), `CHANnel1:*`, `TIMebase:SCALe`, `RUN`, `VOLTage:RANGe` (`:78-88`) |
| `diag_osciloscopio_canais.py` | consultas `PROBe?`, `PROBe:ID?`, `IMPedance?`, `BWLimit?`, `COUPling?`, `DISPlay?`, `OFFSet?`, `SCALe?`, `UNITs?`, `TRIGger:EDGE:SOURce?`, `MEASure:VPP?` (`:31-36`); envia `:RUN` |
| `preflight_new.py` | `FUNCtion:SHAPe`, `LIST:REPeat:COUNt`/`SOURce:LIST:REPeat:COUNt` (testes de comandos que **falham**, `:659-661`), medidas (`:445-448`) |

Estes comandos devem aparecer no site como "usados só em diagnóstico", sem entrada de referência completa, mas com o aviso de H-8 (energizam sem passar por `validate_bench_configuration`).

### 3.5 Resposta real e consequências para a ficha de comando

Formato: `[HH:MM:SS.mmm] t=<monotonic> W|Q|R <texto>`; `W` = escrita, `Q` = pedido de consulta, `R` = resposta (`_transcrever`, `ametek_orm.py:42`). Cada `write()` produz `W comando`, `Q *ESR?`, `W *ESR?`, `R *ESR? -> 0`: o `*ESR?` é o sincronismo (A1). Latência de uma escrita sincronizada nos exemplos: 0,031 s (E03, E19) a 0,047 s (E24), contada de `W comando` até `R *ESR?`. `TRACe:DEFine` dá 3,0 s antes de `SYSTem:ERRor?` (E28), `TRACe:DATA` não tem `*ESR?` (E29) e `TRACe:DELete:ALL` também não (E30).

## 4. Exemplos reais (transcrição SCPI de 07/10)

Origem: `resultados/sessao_2026-10-07_127V_50Hz/scpi_transcricao.log` (127 V/50 Hz), `resultados/sessao_2026-10-07_14-59-54_run02/` (127 V/60 Hz) e `resultados/sessao_2026-10-07_230V_50Hz/` (230 V/50 Hz), todas do PC da bancada, em `.gitignore`: **não estão em nenhum branch** (P-29). Cada bloco é a linha de escrita (ou a pergunta e a resposta) mais a confirmação `*ESR?`, copiada sem alteração, exceto E29, em que a própria transcrição já trunca a 160 caracteres (o `…` e `[N bytes no total]` são dela). Selo: VERIFICADO NA BANCADA para o fato "o comando foi aceito e o `*ESR?` voltou 0" nas condições indicadas (não para o efeito físico).

**E01** `OUTPut:STATe ON` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 174)

```text
[15:57:05.257] t=7530.687000 W OUTPut:STATe ON
[15:57:05.285] t=7530.718000 R *ESR? -> 0
```

**E02** `OUTPut:STATe?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 169)

```text
[15:56:49.626] t=7515.046000 Q OUTPut:STATe?
[15:56:49.656] t=7515.078000 W OUTPut:STATe?
[15:56:49.660] t=7515.093000 R OUTPut:STATe? -> 0
```

**E03** `*CLS` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 9)

```text
[15:56:47.821] t=7513.250000 W *CLS
[15:56:47.855] t=7513.281000 R *ESR? -> 0
```

**E04** `*WAI` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 267)

```text
[15:57:07.845] t=7533.265000 W *WAI
[15:57:07.876] t=7533.296000 R *ESR? -> 0
```

**E05** `ABORt` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 13)

```text
[15:56:47.855] t=7513.281000 W ABORt
[15:56:47.887] t=7513.312000 R *ESR? -> 0
```

**E06** `SOURce:VOLTage:HIGH` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 41)

```text
[15:56:48.128] t=7513.546000 W SOURce:VOLTage:HIGH 300
[15:56:48.170] t=7513.593000 R *ESR? -> 0
```

**E07** `SOURce:FUNCtion:SHAPe SINusoid` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 69)

```text
[15:56:48.397] t=7513.828000 W SOURce:FUNCtion:SHAPe SINusoid
[15:56:48.432] t=7513.859000 R *ESR? -> 0
```

**E08** `SOURce:FUNCtion:SHAPe:CSINusoid` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 710)

```text
[15:57:20.290] t=7545.718000 W SOURce:FUNCtion:SHAPe:CSINusoid 5
[15:57:20.329] t=7545.750000 R *ESR? -> 0
```

**E09** `SOURce:MODE ACDC` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 6184)

```text
[16:04:44.106] t=7989.531000 W SOURce:MODE ACDC
[16:04:44.150] t=7989.578000 R *ESR? -> 0
```

**E10** `SOURce:VOLTage:OFFSet` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 6195)

```text
[16:04:44.216] t=7989.640000 W SOURce:VOLTage:OFFSet 5.5795947
[16:04:44.248] t=7989.671000 R *ESR? -> 0
```

**E11** `VOLTage:MODE STEP` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 241)

```text
[15:57:07.383] t=7532.812000 W VOLTage:MODE STEP
[15:57:07.413] t=7532.843000 R *ESR? -> 0
```

**E12** `VOLTage:MODE PULSe` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 312)

```text
[15:57:09.887] t=7535.312000 W VOLTage:MODE PULSe
[15:57:09.919] t=7535.343000 R *ESR? -> 0
```

**E13** `VOLTage:TRIGgered` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 245)

```text
[15:57:07.413] t=7532.843000 W VOLTage:TRIGgered 127.0
[15:57:07.446] t=7532.875000 R *ESR? -> 0
```

**E14** `PULSe:WIDTh` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 320)

```text
[15:57:09.951] t=7535.375000 W PULSe:WIDTh 0.06
[15:57:09.983] t=7535.406000 R *ESR? -> 0
```

**E15** `VOLTage:TRIGgered?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 260)

```text
[15:57:07.740] t=7533.171000 Q VOLTage:TRIGgered?
[15:57:07.765] t=7533.187000 W VOLTage:TRIGgered?
[15:57:07.766] t=7533.187000 R VOLTage:TRIGgered? -> 127.0
```

**E16** `PULSe:WIDTh?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 338)

```text
[15:57:10.290] t=7535.718000 Q PULSe:WIDTh?
[15:57:10.322] t=7535.750000 W PULSe:WIDTh?
[15:57:10.322] t=7535.750000 R PULSe:WIDTh? -> 0.0600
```

**E17** `VOLTage:MODE?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 257)

```text
[15:57:07.712] t=7533.140000 Q VOLTage:MODE?
[15:57:07.740] t=7533.171000 W VOLTage:MODE?
[15:57:07.740] t=7533.171000 R VOLTage:MODE? -> STEP
```

**E18** `FUNCtion:MODE?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 263)

```text
[15:57:07.766] t=7533.187000 Q FUNCtion:MODE?
[15:57:07.803] t=7533.234000 W FUNCtion:MODE?
[15:57:07.804] t=7533.234000 R FUNCtion:MODE? -> FIX
```

**E19** `TRIGger:SYNChronize:PHASe` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 139)

```text
[15:56:49.098] t=7514.531000 W TRIGger:SYNChronize:PHASe 0
[15:56:49.132] t=7514.562000 R *ESR? -> 0
```

**E20** `FREQuency:MODE LIST` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 6104)

```text
[16:04:41.845] t=7987.265000 W FREQuency:MODE LIST
[16:04:41.876] t=7987.296000 R *ESR? -> 0
```

**E21** `LIST:FREQuency` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 6108)

```text
[16:04:41.876] t=7987.296000 W LIST:FREQuency 57,63
[16:04:41.910] t=7987.343000 R *ESR? -> 0
```

**E22** `LIST:VOLTage` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 6112)

```text
[16:04:41.910] t=7987.343000 W LIST:VOLTage 127,127
[16:04:41.940] t=7987.359000 R *ESR? -> 0
```

**E23** `LIST:DWELl` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 6116)

```text
[16:04:41.940] t=7987.359000 W LIST:DWELl 0.1,0.1
[16:04:41.975] t=7987.406000 R *ESR? -> 0
```

**E24** `SOURce:LIST:REPeat` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 958)

```text
[15:58:10.776] t=7596.203000 W SOURce:LIST:REPeat 0,0,0,0,0,0,0,0,0,0
[15:58:10.825] t=7596.250000 R *ESR? -> 0
```

**E25** `LIST:COUNt` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 6124)

```text
[16:04:42.006] t=7987.437000 W LIST:COUNt 1
[16:04:42.036] t=7987.468000 R *ESR? -> 0
```

**E26** `LIST:STEP` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 6128)

```text
[16:04:42.036] t=7987.468000 W LIST:STEP AUTO
[16:04:42.072] t=7987.500000 R *ESR? -> 0
```

**E27** `TRACe:CATalog?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 837)

```text
[15:57:23.054] t=7548.484000 Q TRACe:CATalog?
[15:57:23.077] t=7548.500000 W TRACe:CATalog?
[15:57:23.082] t=7548.515000 R TRACe:CATalog? -> "SINE,SQUARE,CLIPPED"
```

**E28** `TRACe:DEFine` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 838)

```text
[15:57:23.083] t=7548.515000 W TRACe:DEFine TCC00
# sem *ESR? a seguir; próxima linha da transcrição:
[15:57:26.087] t=7551.515000 Q SYSTem:ERRor?
```

**E29** `TRACe:DATA` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 878)

```text
[15:57:53.494] t=7578.921000 W TRACe:DATA TCC00,0.011314514,0.016806151,0.022299671,0.027797725,0.033299188,0.038803054,0.0443115,0.049821368,0.055335037,0.060850567,0.066368224,0.071888449,0... [11719 bytes no total]
# sem *ESR? a seguir; próxima linha da transcrição:
[15:57:55.156] t=7580.578000 W *CLS
```

**E30** `TRACe:DELete:ALL` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 173)

```text
[15:56:49.697] t=7515.125000 W TRACe:DELete:ALL
# sem *ESR? a seguir; próxima linha da transcrição:
[15:57:05.257] t=7530.687000 W OUTPut:STATe ON
```

**E31** `SOURce:LIST:FUNCtion:SHAPe` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 928)

```text
[15:58:10.471] t=7595.890000 W SOURce:LIST:FUNCtion:SHAPe TCC00,TCC01,TCC02,TCC03,TCC04,TCC05,TCC06,TCC07,TCC08,TCC09
[15:58:10.502] t=7595.921000 R *ESR? -> 0
```

**E32** `SOURce:LIST:VOLTage` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 938)

```text
[15:58:10.568] t=7596.000000 W SOURce:LIST:VOLTage 140.57746,116.66659,132.7802,128.55889,120.19009,138.97496,113.17566,139.97638,118.2173,130.84036
[15:58:10.599] t=7596.031000 R *ESR? -> 0
```

**E33** `SOURce:LIST:DWELl` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 948)

```text
[15:58:10.660] t=7596.093000 W SOURce:LIST:DWELl 0.02,0.02,0.02,0.02,0.02,0.02,0.02,0.02,0.02,0.02
[15:58:10.710] t=7596.140000 R *ESR? -> 0
```

**E34** `SOURce:LIST:FUNCtion:POINts?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 937)

```text
[15:58:10.538] t=7595.968000 Q SOURce:LIST:FUNCtion:POINts?
[15:58:10.564] t=7595.984000 W SOURce:LIST:FUNCtion:POINts?
[15:58:10.568] t=7596.000000 R SOURce:LIST:FUNCtion:POINts? -> 10
```

**E35** `SOURce:LIST:REPeat:POINts?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 1064)

```text
[15:58:12.041] t=7597.468000 Q SOURce:LIST:REPeat:POINts?
[15:58:12.070] t=7597.500000 W SOURce:LIST:REPeat:POINts?
[15:58:12.075] t=7597.500000 R SOURce:LIST:REPeat:POINts? -> 10
```

**E36** `SOURce:LIST:COUNt` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 965)

```text
[15:58:10.862] t=7596.281000 W SOURce:LIST:COUNt 1
[15:58:10.890] t=7596.312000 R *ESR? -> 0
```

**E37** `SOURce:LIST:STEP` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 972)

```text
[15:58:10.926] t=7596.359000 W SOURce:LIST:STEP AUTO
[15:58:10.968] t=7596.390000 R *ESR? -> 0
```

**E38** `FUNCtion:MODE LIST` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 979)

```text
[15:58:11.001] t=7596.421000 W FUNCtion:MODE LIST
[15:58:11.036] t=7596.468000 R *ESR? -> 0
```

**E39** `VOLTage:MODE LIST` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 986)

```text
[15:58:11.070] t=7596.500000 W VOLTage:MODE LIST
[15:58:11.113] t=7596.546000 R *ESR? -> 0
```

**E40** `OUTPut:TTLTrg:MODE` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 146)

```text
[15:56:49.170] t=7514.593000 W OUTPut:TTLTrg:MODE TRIG
[15:56:49.207] t=7514.640000 R *ESR? -> 0
```

**E41** `INITiate:IMMediate` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 271)

```text
[15:57:07.876] t=7533.296000 W INITiate:IMMediate
[15:57:07.912] t=7533.343000 R *ESR? -> 0
```

**E42** `*TRG` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 284)

```text
[15:57:08.003] t=7533.437000 W *TRG
[15:57:08.037] t=7533.468000 R *ESR? -> 0
```

**E43** `TRIGger:STATe?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 232)

```text
[15:57:07.263] t=7532.687000 Q TRIGger:STATe?
[15:57:07.304] t=7532.734000 W TRIGger:STATe?
[15:57:07.307] t=7532.734000 R TRIGger:STATe? -> IDLE
```

**E44** `TRIGger:SOURce?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 1067)

```text
[15:58:12.075] t=7597.500000 Q TRIGger:SOURce?
[15:58:12.103] t=7597.531000 W TRIGger:SOURce?
[15:58:12.107] t=7597.531000 R TRIGger:SOURce? -> BUS
```

**E45** `MEASure:VOLTage:AC?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 222)

```text
[15:57:05.953] t=7531.375000 Q MEASure:VOLTage:AC?
[15:57:05.977] t=7531.406000 W MEASure:VOLTage:AC?
[15:57:06.160] t=7531.593000 R MEASure:VOLTage:AC? -> 126.525
```

**E46** `STATus:OPERation:CONDition?` (127 V/60 Hz; `sessao_2026-10-07_14-59-54_run02/scpi_transcricao.log`, linha 218)

```text
[15:00:37.973] t=4143.390000 Q STATus:OPERation:CONDition?
[15:00:38.002] t=4143.421000 W STATus:OPERation:CONDition?
[15:00:38.008] t=4143.421000 R STATus:OPERation:CONDition? -> 24
```

**E47** `SOURce:FREQuency:MODE?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 266)

```text
[15:57:07.804] t=7533.234000 Q SOURce:FREQuency:MODE?
[15:57:07.845] t=7533.265000 W SOURce:FREQuency:MODE?
[15:57:07.845] t=7533.265000 R SOURce:FREQuency:MODE? -> FIX
```

**E48** `SOURce:FREQuency` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 111)

```text
[15:56:48.824] t=7514.250000 W SOURce:FREQuency 50
[15:56:48.860] t=7514.281000 R *ESR? -> 0
```

**E49** `SOURce:VOLTage 0` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 118)

```text
[15:56:48.896] t=7514.328000 W SOURce:VOLTage 0
[15:56:48.932] t=7514.359000 R *ESR? -> 0
```

**E50** `TRIGger:SOURce BUS` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 125)

```text
[15:56:48.964] t=7514.390000 W TRIGger:SOURce BUS
[15:56:48.997] t=7514.421000 R *ESR? -> 0
```

**E51** `INSTrument:COUPle` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 20)

```text
[15:56:47.916] t=7513.343000 W INSTrument:COUPle ALL
[15:56:47.948] t=7513.375000 R *ESR? -> 0
```

**E52** `SOURce:CURRent:PROTection:STATe` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 55)

```text
[15:56:48.268] t=7513.703000 W SOURce:CURRent:PROTection:STATe ON
[15:56:48.296] t=7513.718000 R *ESR? -> 0
```

**E53** `*ESR?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 8)

```text
[15:56:47.776] t=7513.203000 W OUTPut:STATe OFF
[15:56:47.776] t=7513.203000 Q *ESR?
[15:56:47.820] t=7513.250000 W *ESR?
[15:56:47.821] t=7513.250000 R *ESR? -> 0
```

**E54** `SYSTem:ERRor?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 18)

```text
[15:56:47.916] t=7513.343000 W SYSTem:ERRor?
# sem *ESR? a seguir; próxima linha da transcrição:
[15:56:47.916] t=7513.343000 R SYSTem:ERRor? -> 0,"No error"
```

**E55** `SYSTem:ERRor?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 19)

```text
[15:56:47.887] t=7513.312000 Q SYSTem:ERRor?
[15:56:47.916] t=7513.343000 W SYSTem:ERRor?
[15:56:47.916] t=7513.343000 R SYSTem:ERRor? -> 0,"No error"
```

**E56** `*IDN?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 4)

```text
[15:56:47.738] t=7513.171000 W OUTPut:STATe OFF
[15:56:47.738] t=7513.171000 Q *IDN?
[15:56:47.767] t=7513.187000 W *IDN?
[15:56:47.774] t=7513.203000 R *IDN? -> "CALIFORNIA INSTRUMENTS,MX30-3Pi,1921A03213,Rev 5.53"
```

**E57** `OUTPut:TTLTrg:SOURce` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 153)

```text
[15:56:49.241] t=7514.671000 W OUTPut:TTLTrg:SOURce BOT
[15:56:49.271] t=7514.703000 R *ESR? -> 0
```

**E58** `OUTPut:TTLTrg ON` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 160)

```text
[15:56:49.304] t=7514.734000 W OUTPut:TTLTrg ON
[15:56:49.338] t=7514.765000 R *ESR? -> 0
```

**E59** `TRIGger:SYNChronize:SOURce` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 132)

```text
[15:56:49.032] t=7514.453000 W TRIGger:SYNChronize:SOURce PHASe
[15:56:49.065] t=7514.500000 R *ESR? -> 0
```

**E60** `SOURce:FREQuency:MODE FIXed` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 90)

```text
[15:56:48.600] t=7514.031000 W SOURce:FREQuency:MODE FIXed
[15:56:48.641] t=7514.062000 R *ESR? -> 0
```

**E61** `FUNCtion:MODE FIXed` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 76)

```text
[15:56:48.464] t=7513.890000 W FUNCtion:MODE FIXed
[15:56:48.500] t=7513.921000 R *ESR? -> 0
```

**E62** `VOLTage:MODE FIXed` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 83)

```text
[15:56:48.531] t=7513.953000 W VOLTage:MODE FIXed
[15:56:48.565] t=7513.984000 R *ESR? -> 0
```

**E63** `SOURce:MODE AC` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 27)

```text
[15:56:47.986] t=7513.406000 W SOURce:MODE AC
[15:56:48.028] t=7513.453000 R *ESR? -> 0
```

**E64** `SOURce:VOLTage:RANGe` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 34)

```text
[15:56:48.063] t=7513.484000 W SOURce:VOLTage:RANGe 300
[15:56:48.090] t=7513.515000 R *ESR? -> 0
```

**E65** `SOURce:CURRent` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 48)

```text
[15:56:48.204] t=7513.625000 W SOURce:CURRent 0.5
[15:56:48.232] t=7513.656000 R *ESR? -> 0
```

**E66** `SOURce:CURRent:PROTection:DELay` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 62)

```text
[15:56:48.333] t=7513.765000 W SOURce:CURRent:PROTection:DELay 0.1
[15:56:48.365] t=7513.796000 R *ESR? -> 0
```

**E67** `SOURce:FREQuency:SLEW` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 97)

```text
[15:56:48.674] t=7514.093000 W SOURce:FREQuency:SLEW MAXimum
[15:56:48.710] t=7514.140000 R *ESR? -> 0
```

**E68** `SOURce:VOLTage:SLEW` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 104)

```text
[15:56:48.752] t=7514.171000 W SOURce:VOLTage:SLEW MAXimum
[15:56:48.788] t=7514.218000 R *ESR? -> 0
```

**E69** `SOURce:LIST:VOLTage:POINts?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 947)

```text
[15:58:10.629] t=7596.062000 Q SOURce:LIST:VOLTage:POINts?
[15:58:10.660] t=7596.093000 W SOURce:LIST:VOLTage:POINts?
[15:58:10.660] t=7596.093000 R SOURce:LIST:VOLTage:POINts? -> 10
```

**E70** `SOURce:LIST:DWELl:POINts?` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 957)

```text
[15:58:10.740] t=7596.171000 Q SOURce:LIST:DWELl:POINts?
[15:58:10.770] t=7596.203000 W SOURce:LIST:DWELl:POINts?
[15:58:10.776] t=7596.203000 R SOURce:LIST:DWELl:POINts? -> 10
```

**E71** `SOURce:VOLTage:LEVel:IMMediate:AMPLitude` (127 V/50 Hz; `sessao_2026-10-07_127V_50Hz/scpi_transcricao.log`, linha 207)

```text
[15:57:05.812] t=7531.234000 W SOURce:VOLTage:LEVel:IMMediate:AMPLitude 127
[15:57:05.845] t=7531.265000 R *ESR? -> 0
```

## 5. O que o site precisa para cumprir a regra "todo comando é um link com exemplo real"

1. Uma entrada por comando (as 78 linhas da seção 3.1 e as 29 da 3.2, desdobrando as que agrupam comandos) com: sintaxe, parâmetros, quem envia (símbolo, não linha), por que existe, erros conhecidos (A/K), página do manual, exemplo real da seção 4.
2. Transcrições: decidir o que versionar (P-29); sugestão mínima, os 71 trechos acima (cada um com 2 a 8 linhas) num arquivo de dados incluído no build.
3. Keysight: capturar o tráfego SCPI (nível debug do PyVISA ou transcrição equivalente no `KeysightDSOX4034A`) numa próxima bancada; até lá, sem exemplo e com selo NÃO VERIFICADO.
4. Comandos sem exemplo hoje: `*OPC?`, `SOURce:FREQuency?`, `SOURce:CURRent:LEVel...`, `MEASure:CURRent:AC?`, `MEASure:POWer:*`, `TRACe:DATA? <nome>` (P-19) e todos os do Keysight.
