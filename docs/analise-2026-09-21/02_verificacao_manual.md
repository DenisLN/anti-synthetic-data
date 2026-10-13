# 02 — Verificação contra os manuais (subagente 2)

Análise **100 % offline**, 2026-09-21. Nenhum instrumento foi tocado; nenhum
arquivo existente do projeto foi alterado.

**Fontes primárias**

| sigla | documento | páginas |
|---|---|---|
| **[KS]** | *Keysight InfiniiVision 4000 X-Series Oscilloscopes Programmer's Guide* | 1809 |
| **[AM]** | *AMETEK Programmable Power — BPS / MX / RS Series SCPI Programming Manual (Including MX Series I / Series II)*, P/N 7003-961 **Rev. AB** | 227 |

Todas as páginas citadas são **páginas do PDF** (os marcadores
`===== PAGINA_PDF n =====` dos .txt extraídos coincidem com a numeração
impressa do rodapé em ambos os manuais).

**Cross-check independente** feito no MCP `painel-conhecimento`
(biblioteca id **63** = manual AMETEK `7003-961_RevAB`; id **64** = guia
Keysight InfiniiVision 4000 — identidades confirmadas por `buscar_texto`).
As duas páginas mais críticas e mais mal extraídas por OCR
(AM p. 169, tabela de bits de status; AM p. 126, subsistema TRACe) foram
lidas **como imagem** via `ler_documento(paginas_imagem=[169,126])` e batem
palavra por palavra com o texto usado aqui.

**Marcação de cada afirmação:** **[MANUAL]** = citação ou paráfrase direta,
com seção e página · **[INFERÊNCIA]** = dedução minha a partir do manual +
dados do relatório 01 · **[ESPECULAÇÃO]** = hipótese sem apoio decisivo.

---

## (a) Resumo executivo

### A. Osciloscópio Keysight

| # | afirmação (relatório 01 / código) | fonte no 01 | veredito | evidência no manual | consequência para o projeto |
|---|---|---|---|---|---|
| A1 | **H-REF10**: `REFerence LEFT` põe a referência a **1 divisão** da borda esquerda = 10 % do `RANGe` | §0 ACHADO 1; §1.1 | **APOIADA** (decisiva) | [KS] `:TIMebase:REFerence`, **p. 1337**: "LEFT -- one division from the left side of the screen."; e "The time reference is the point on the display where the trigger point is referenced." | Confirma o artefato. Nada a investigar na bancada sobre o "atraso de 20/100 ms" |
| A2 | `RANGe` = 10 divisões, logo 1 div = `RANGe/10` | §1.1 | **APOIADA** | [KS] `:TIMebase:RANGe`, **p. 1335**: "The range is 10 times the current time-per-division setting." | Fecha a aritmética `pre_trigger + RANGe/10` |
| A3 | `:TIMebase:POSition` = tempo do **trigger até a referência**; sinal negativo põe a borda esquerda antes do trigger | comentário em `oscilloscope_orm.py:189-199` | **APOIADA** | [KS] `:TIMebase:POSition`, **p. 1334**: "<pos> ::= time in seconds from the trigger to the display reference"; "sets the time interval between the trigger event and the display reference point on the screen" | O comentário do código está **correto**; o erro nunca foi o sinal, foi ignorar que a referência não é a borda |
| A4 | Previsão `t_trigger = pre_trigger + RANGe/10` dentro do registro | §1.1 (5 conjuntos, n=62) | **APOIADA** (derivação fechada) | A1+A2+A3: borda esquerda = `POSition − 0,1·RANGe` = `−(pre + RANGe/10)` | Explica 20,0 / 80,0 / 500,0 / 560,00 ms sem resíduo |
| A5 | `x_origin` é o único campo que diz onde está o trigger | §1.1 | **APOIADA** | [KS] `:WAVeform:XORigin`, **p. 1476**: "XORigin is the X-axis value of the data point specified by the :WAVeform:XREFerence value. In this product, that is always the X-axis value of the first data point (XREFerence = 0)." | `time_axis -= time_axis[0]` joga fora exatamente a informação do trigger |
| A6 | Índice do trigger obtenível da preamble | §2 (correção B) | **APOIADA** | [KS] p. 1448: "time = [(data point number - xreference) * xincrement] + xorigin"; `XREFerence` **p. 1477**: "XREFerence is always 0" | `indice_trigger = round(-x_origin / x_increment)`. Correção (B) do 01 é a certa |
| A7 | Preamble tem **10 campos** na ordem usada pelo código | `get_waveform` | **APOIADA** | [KS] `:WAVeform:PREamble`, **p. 1460**: format, type, points, count, xincrement, xorigin, xreference, yincrement, yorigin, yreference | Parsing do projeto está correto |
| A8 | "`:ACQuire:POINts:ANALog:AUTO ON` tem teto real de ~32,3–32,7 kpts" | comentário `oscilloscope_orm.py:225-240`; 01 §4 item 14 | **CONTRADITA (o diagnóstico da causa)** | [KS] `:WAVeform:POINts:MODE`, **p. 1458**: NORMal devolve o *measurement record*, "a 62,500-point (maximum) representation of the raw acquisition record"; RAW devolve "the raw acquisition record". p. 1459: "MAXimum or RAW will allow up to 4,000,000 points to be returned." | **O teto medido é do modo de transferência, não da profundidade de aquisição.** O código pede `POINts:MODE NORMal` (linhas 211 e 328) e por isso nunca vê o registro bruto |
| A9 | Modo AUTO escolhe profundidade/taxa pelo time/div | comentário idem | **APOIADA** | [KS] **p. 321** e **p. 329**: "automatically determined by the oscilloscope based on the horizontal time/div setting (Automatic mode, the oscilloscope's default)"; equivale a Digitizer OFF | `:ACQuire:DIGitizer OFF` do código é redundante com os dois `AUTO ON` |
| A10 | `:ACQuire:POINts:ANALog?` devolveu 3000 parado e a aquisição real é outra | comentário idem | **APOIADA e refinada** | [KS] **p. 320**: "For :SINGle acquisitions, the requested memory depth is used. When the oscilloscope is running (:RUN command...) or when the :DIGitize command is used, the requested amount of memory is halved."; "The number of points acquired is not directly controllable." | Como o projeto usa `:SINGle`, ele tem a profundidade **inteira**, não a metade. Consultar a profundidade com o scope parado não mede o que a SINGLE vai usar |
| A11 | Profundidade cai pela metade com 2 canais do mesmo par ligados | — (não está no 01) | **[MANUAL] novo** | [KS] **p. 320**: "The maximum amount of memory available is halved when both channels in a pair are turned on. Channels 1 and 2 are one pair" | Se a bancada usa CH1+CH2, metade da memória some. Vale conferir `disable_channel` |
| A12 | `:WAVeform:POINts 60000` é aceito | `configure_acquisition:212` | **APOIADA, mas inútil em NORMal** | [KS] `:WAVeform:POINts`, **p. 1456**: "<#_points> ::= an integer between 100 and 10000000"; "Only data visible on the display will be returned."; "the oscilloscope returns as close to the requested number of points as possible" | 60000 > 62500? não — mas em NORMal o teto é o measurement record |
| A13 | Condições para usar RAW/MAXimum | — | **[MANUAL] novo** | [KS] **p. 1458**: "The instrument must be stopped ... in order to return more than the measurement record"; ":TIMebase:MODE must be set to MAIN"; ":ACQuire:TYPE must be set to NORMal, AVERage, or HRESolution" | **As três condições já são satisfeitas** pelo projeto depois do `:SINGle` concluído. RAW está disponível de graça |
| A14 | bit 5 de `:OPERegister:CONDition?` = "wait trig" | `is_armed()` | **APOIADA** | [KS] Tabela 91, **p. 293**: bit 5 "Wait Trig — The trigger is armed (set by the Trigger Armed Event Register (TER))" | Uso correto |
| A15 | bit 3 = "run" | `wait_for_trigger_complete()` | **APOIADA** | [KS] Tabela 91, **p. 293**: bit 3 "Run — The oscilloscope is running (not stopped)"; **p. 1623**: "Is set whenever the instrument is not stopped." | Uso correto |
| A16 | `:AER?` indica sistema armado e **se limpa ao ser lido** | `arm()` lê `:AER?` e `:TER?` antes do `:SINGle` | **APOIADA** | [KS] **p. 272**: "A '1' indicates the trigger system is in the armed state, ready to accept a trigger."; **p. 1624**: "The ARM event register stays set until it is cleared by reading the register with the AER? query or using the *CLS command." | A limpeza prévia do projeto é exatamente o procedimento recomendado |
| A17 | `:TER?` se limpa ao ser lido | `wait_for_trigger_complete` | **APOIADA** | [KS] **p. 309**: "After the Trigger Event Register is read, it is cleared. A one indicates a trigger has occurred." | Correto — e por isso `trigger_seen` precisa ser memorizado, como o código faz |
| A18 | "o osciloscópio só aceita trigger depois de encher o pré-trigger" | pergunta aberta do 00/01 | **NÃO COBERTA** | Nenhuma passagem do guia de programação trata de *pre-trigger fill*. Busquei `pre-trigger`, `pretrigger`, `prefill`: **zero ocorrências** | Fica para a bancada (teste T-KS2 abaixo). Mas a evidência do 01 (dispersão **zero** em 10/10 capturas da classe 04) já torna o efeito irrelevante na prática |
| A19 | Latência/jitter documentado do trigger externo | pergunta 5 | **NÃO COBERTA** | O guia é de programação, não de especificação: `jitter` só aparece em exemplos de outra série. Nada sobre latência de `:TRIGger:EDGE:SOURce EXTernal` | Buscar no *Data Sheet*, não neste guia. O 01 já mede atraso ≈ 0 |
| A20 | `:EXTernal:RANGe <v>` define a faixa do trigger externo | `setup_external_trigger:265` + validação em 275-279 | **CONTRADITA (parcialmente)** | [KS] `:EXTernal:RANGe`, **p. 456**: "The :EXTernal:RANGe command is provided for product compatibility. When using 1:1 probe attenuation, the range is either 1.6 V or 8 V."; "The range is automatically recalculated when the external trigger probe attenuation factor is changed." | O write é **decorativo**: quem manda é `:EXTernal:PROBe`. A validação `abs(level_v) >= actual_range` lê um valor que o projeto não controla |
| A21 | `:EXTernal:PROBe` aceita a atenuação usada | idem | **APOIADA** | [KS] **p. 455**: "The probe attenuation factor may be 0.1 to 1000" | Probe 500× cabe |
| A22 | `:TRIGger:SWEep NORMal` só dispara com trigger real | `setup_external_trigger` | **APOIADA** | [KS] Introdução a `:TRIGger`, **p. 1345**: "NORMal mode -- displays a waveform only if a trigger signal is present and the trigger conditions are met." | Escolha correta para disparo único |
| A23 | "em BYTE, 0 = hole, **1 = clipped low e 255 = clipped high**" | comentário `oscilloscope_orm.py:365-366` ("O guia 4000 X-Series reserva esses códigos") | **PARCIAL: só o 0 é do manual; 1/255 NÃO COBERTOS** | [KS] **p. 1448**: "If there is a hole in the data, the hole is represented by a value of 0." Nada sobre 1 e 255 em BYTE. Busca por `clipped high`/`clipped low`: **zero ocorrências** | `get_waveform()` **rejeita capturas boas** cujas amostras encostem em 1 ou 255. Com escala apertada isso descarta dado válido citando um manual que não diz isso |

### B. Fonte AMETEK

| # | afirmação (relatório 01 / código) | fonte no 01 | veredito | evidência no manual | consequência para o projeto |
|---|---|---|---|---|---|
| B1 | `LIST:REPeat 1` toca cada ponto **2×**; `0` toca 1× (**H-REPEAT**) | §0; §1.3 A4 | **PARCIAL — apoiada pela terminologia, não pela letra** | [AM] §4.17, **p. 90**: "LIST:REPeat determines how many times each data point **will repeat**"; §4.17.5, **p. 94**: parâmetros "**0 to 99**" | O manual nunca define 0 vs 1 explicitamente, **mas** admitir 0 como válido só faz sentido se 0 = "sem repetição". A medida do 01 é a leitura natural. Manter `REPeat 0` |
| B2 | `LIST:COUNt` = nº de execuções da lista inteira | `program_capture` | **APOIADA** | [AM] §4.17.1, **p. 91**: "sets the number of times that the list is executed before it is completed"; *RST = 1 | Uso correto |
| B3 | `LIST:STEP AUTO` roda a lista inteira num único trigger | idem | **APOIADA** | [AM] §4.17.6, **p. 94**: "AUTO causes the entire list to be output sequentially after the starting trigger, paced by its dwell delays." | Uso correto |
| B4 | No fim da lista **o último passo persiste** | §1.3 A5 | **NÃO COBERTA (mas não contradita)** | [AM] §6.5.4, **p. 157**: "If the list is completed, the trigger system returns to the Idle state." O manual descreve o **sistema de trigger** voltando a Idle, e em **nenhum** ponto diz que a saída volta ao nível imediato | [INFERÊNCIA] Persistir o último passo é o comportamento coerente com o texto. A classe 18 ficar em 63 Hz é esperado, não um bug |
| B5 | Nas listas de amplitude "a saída volta ao normal" | §1.3 A5 | **APOIADA por construção, não por comportamento** | O próprio 01 já observa: o último passo **é** a senoide nominal | Não há comportamento de fonte a explicar |
| B6 | Depois de um **PULSe** a saída volta ao nível imediato | implícito no 01 (§2 (ii)) | **APOIADA** | [AM] `VOLTage:MODE`, **p. 109**: "PULSe — The voltage is changed to the value set by VOLTage:TRIGgered **for a duration determined by the pulse commands**" | Confirma que zerar depois destrói o pós-evento das classes nativas (risco (a) do 01 §2(ii)) |
| B7 | Depois de um **STEP** o novo nível fica | implícito | **APOIADA** | [AM] **p. 109**: "STEP — The voltage is programmed to the value set by VOLTage:TRIGgered when a triggered transient occurs." (sem retorno) | STEP é mudança permanente |
| B8 | Regra "todas as listas ativas com o mesmo nº de pontos, erro no **primeiro ponto disparado**" | §1.3 B5 | **APOIADA (literal)** | [AM] §4.17, **p. 90**: "All active subsystems that have their modes set to LIST must have the same number of points (up to 32 for Series I and 100 for Series II), **or an error is generated when the first list point is triggered**. The only exception is a list consisting of only one point." | Explica **por que o `-226` aparece no `INITiate:IMMediate`** e não nos writes da lista |
| B9 | `-226` explica a falha da classe 18 após a 17 ter deixado `FUNCtion:MODE LIST` + lista de 12 pontos | §1.3 B5 | **APOIADA** | [AM] Apêndice C, **p. 214**: `-226 "Lists not same length"` — causa "One or more transient lists programmed has different length"; remédio "All lists must be of same length or transient cannot be compiled and executed." | `frequency_drift_list()` (`ametek_orm.py:690-701`) programa listas de **2** pontos e **nunca escreve `FUNCtion:MODE FIXed`**. Com 12 pontos de forma residuais → `-226` garantido |
| B10 | Como desativar as listas residuais | pergunta 7 | **APOIADA — o manual prescreve explicitamente** | [AM] §6.4.2, **p. 152**, Passo 1: "**Set the functions that you do not want to generate transients to FIXed mode.** A convenient way to do this is with the *RST command." | A correção é uma linha: `FUNCtion:MODE FIXed` no caminho nativo, como `program_capture()` já faz (linhas 987-988) |
| B11 | `LIST:DWELl` é global e precisa casar | — | **[MANUAL] novo** | [AM] §4.17, **p. 90**: "the LIST:DWELl command is active **whenever any function is set to list mode**. Therefore, LIST:DWELl must always be set either to one point, or to the same number of points as the active list." | Mais um caminho para `-226` que o projeto não neutraliza |
| B12 | `VOLTage:MODE {FIXed\|STEP\|PULSe\|LIST}` e o papel de `VOLTage:TRIGgered` | `trigger_step/pulse` | **APOIADA** | [AM] **p. 108**: `VOLTage:TRIGgered` "selects the AC rms or DC amplitude that the output voltage will be set to during a triggered step or pulse transient"; **p. 109** define os 4 modos | Uso conceitualmente correto |
| B13 | **O valor triggered é "latched" no INIT** | H-NATIVO (a), §1.2 | **CONTRADITA** | [AM] §6.5.4, **p. 157**: "When the trigger system enters the Output Change state **upon receipt of a trigger**..., the triggered functions are set to their programmed trigger levels." | O manual põe a aplicação do valor **no trigger**, não no INIT. Um "latch no INIT" não tem apoio documental |
| B14 | **Existe ordem obrigatória entre modo e valor** | H-NATIVO (b) | **APOIADA como procedimento (não como restrição)** | [AM] §6.4.2, **p. 152**: Passo 1 = modo (`VOLTage:MODE STEP`), Passo 2 = valor (`VOLTage:TRIGger 135`), Passo 3 = fonte de trigger, Passo 4 = pulso, Passo 5 = `INITiate` | **O código já obedece essa ordem** (`ametek_orm.py:543-544`, `563-565`). O que ele **viola** é o Passo 1 completo (ver B10) |
| B15 | Existe condição documentada em que a escrita é **aceita sem erro mas ignorada** | H-NATIVO (c) | **APOIADA — duas condições** | (i) [AM] `INITiate`, **p. 129**: "**If the trigger system is not in the Idle state, the initiate commands are ignored.**" (ii) [AM] Apêndice C, **p. 217**, erro **19 "Illegal during transient"**: causa "Operation requested not available while transient is running"; remédio "**Wait till transient execution is completed or abort transient execution first.**" | Ver §(c). São os dois mecanismos mais fortes para H-NATIVO |
| B16 | `TRIGger:STATe?` IDLE **não** garante que o transiente terminou (**H-WAI**) | §0 tabela; §1.3 B5 | **APOIADA (literal!)** | [AM] `TRIG:STATe?`, **p. 132**: "On Series II controllers, the trigger state will be updated when the last list point has been executed. For final voltage or frequency steps with a longer dwell time than needed to reach the end value, this means **the response may change from BUSY to IDLE before the dwell time has expired**." | O manual **documenta** o falso IDLE e até dá a mitigação: "add a final list point with a short durating (e.g. 0.001 second) to hold the BUSY state till the end of the list" |
| B17 | Estados de `TRIGger:STATe?` | `arm()` aceita `IDLE`/`ARM`/`WTRIG` | **APOIADA** | [AM] **p. 132**: IDLE, ARM ("waiting for internal syncronization or external trigger"), BUSY ("The triggered transient is in progress"), WTRIG ("The unit is waiting for a trigger event") | O código cobre os 4 corretamente |
| B18 | `TRIGger:SOURce BUS` + `INITiate` + `*TRG` | `arm/arm_transient` | **APOIADA** | [AM] **p. 130**: "BUS — Triggering occurs following the INIT command after receiving the *TRG command or a Group Execute Trigger (GET) IEEE signal." | Sequência correta |
| B19 | `ABORt` reinicializa modos / desliga OUTPUT (Rev. 5.53) | comentários `ametek_orm.py:1222-1224`, `979-981`; §1.3 B3 | **NÃO COBERTA — o manual só promete o sistema de trigger** | [AM] `ABORt`, **p. 128**: "resets the transient trigger systems to the Idle state. Any output transient or measurement that is in progress is immediately aborted. ABORt also cancels any lists or pulses that may be in process." Nada sobre `VOLT:MODE`, `FUNC:MODE` ou `OUTPut` | **H-ZERO-LIST continua em aberto pelo manual.** O comportamento relatado é extra-manual (firmware) — o teste T4 do 01 continua necessário |
| B20 | `INITiate:CONTinuous OFF` exige INIT por evento | não usado | **APOIADA** | [AM] **p. 129**: "0 or OFF turns off continuous triggering. In this state, the trigger system must be initiated for each triggered event"; *RST = OFF | O projeto está no default correto |
| B21 | Comandos de list/trigger são processados **em paralelo** | comentários em `configure_harmonics_csine`, `arm()`; H-NATIVO (b) | **APOIADA (literal)** | [AM] §7.7, **p. 173**: "SCPI commands sent to the AC source are processed either sequentially or in parallel. ... **Commands that affect list and trigger actions measurements and calibration are among the parallel command.**" | O comentário do código cita a seção certa |
| B22 | `*WAI` resolve essa concorrência | `arm()` e `configure_harmonics_csine` | **CONTRADITA em parte — duas ressalvas graves** | [AM] §7.7, **p. 173**: "*WAI — This prevents the AC source from processing subsequent commands until all pending operations are completed **except for transients**." [AM] §5.14, **p. 142**: "***WAI can be aborted by sending any other command after the *WAI command.**" | (1) `*WAI` **não** espera transientes — exatamente o que o projeto precisa esperar. (2) O `*WAI` seguido imediatamente de `INITiate:IMMediate` (`arm():1206-1207`) **é o caso literal de aborto do `*WAI`** |
| B23 | `*OPC?` "não funciona nesta Rev." | 01 §3 P2 | **CONTRADITA pelo manual (mas pode ser real no firmware)** | [AM] §7.7, **p. 173** lista `*OPC?` entre os três mecanismos: "This places a 1 in the Output Queue when all pending operations have completed." | O manual documenta `*OPC?` como suportado. Se a Rev. 5.53 não responde, é desvio de firmware — vale registrar como tal, não como "o manual não tem" |
| B24 | Jeito recomendado de aguardar comandos lentos | pergunta 11 | **APOIADA** | [AM] §7.7, **p. 173**: `TRIG:STATe?` "will report the state of the transient trigger subsystem and will return IDLE, ARM or BUSY to allow the user monitor the state of the trigger system" | Para **transientes** o manual manda usar `TRIG:STATe?`, não `*WAI` — é o que o projeto faz em `arm()`, e está certo |
| B25 | **bit 3 de `STATus:OPERation:CONDition?` = "transiente em andamento"** (campo `transiente_ativo`) | §1.3 B1 (`True` em 1042/1043) | **CONTRADITA — o bit significa o OPOSTO** | [AM] Tabela 7-2, **p. 169**: bit 3 = **TRANS — "Transient is completed"**. Figura 7-1, **p. 168**, rotula o bit como "Trans. Compl. 3 8" | **O rótulo `transiente_ativo` está invertido.** Ler `True` em repouso é o comportamento *esperado*. O campo nunca poderia discriminar nada — B1 do 01 está certo no fato e agora tem a causa |
| B26 | Tabela completa dos bits do grupo Operation | pergunta 9 | **[MANUAL] completa** | [AM] Tabela 7-2, **p. 169**: **bit 0 = CAL** "Interface complete its calibration cycle"; **bit 3 = TRANS** "Transient is completed"; **bit 4 = MEAS** "Measurement is completed". Nenhum outro bit é definido no grupo Operation | Só 3 bits existem. Não há bit de "transiente em andamento" — para isso o instrumento oferece `TRIG:STATe? → BUSY` |
| B27 | Atraso documentado entre `*TRG` e a mudança de saída | pergunta 10 | **NÃO COBERTA (latência) / APOIADA (semântica)** | [AM] `TRIGger:SYNChronize:SOURce`, **p. 131**: "IMMediate **starts the transient output immediately**"; §6.5.3, **p. 156**: "When IMMediate is selected, the trigger system goes directly to the Output state." Nenhum número de latência em lugar nenhum | Coerente com o achado do 01 de atraso ≈ 0. Mas o projeto usa `SYNChronize:SOURce PHASe` + `PHASe 0`, que adiciona espera **até o próximo cruzamento de zero** — até 1 ciclo (16,7/20 ms) |
| B28 | `OUTPut:TTLTrg:SOURce BOT` = pulso no **início** do transiente | `configure_safe_baseline:862`, `program_capture:1132` | **APOIADA** | [AM] `OUTPut:TTLTrg:SOURce`, **p. 77**: "**BOT** — Beginning of transient output"; "When an event becomes true at the selected TTLTrg source, a pulse is sent to the the function strobe on the system interface connector" | Uso correto; nenhuma latência documentada |
| B29 | `OUTPut:TTLTrg:MODE TRIG` + `OUTPut:TTLTrg ON` são necessários | idem | **APOIADA** | [AM] **p. 76**: "on Series II MX/RS/BPS system having firmware revision 4.00 or higher, factory default is Trigger state which means the **OUTP:TTLT:STAT command is required to generate outputs**"; "the desired mode must be set after turning on the power source as it is not retained as part of the INIT subsystem" | O projeto reprograma os três a cada `program_capture` — correto e necessário |
| B30 | `TRACe:DATA` grava em memória **não volátil** | P3 hipótese 2 ("não se sabe") | **APOIADA — a resposta é SIM** | [AM] Trace Subsystem, **p. 126**: "**Waveform data is stored in nonvolatile memory and is retained when input power is removed.**" (confirmado por leitura da página como imagem) | **Promove a hipótese 2 do P3.** 280 `TRACe:DATA` = 280 gravações em memória não volátil numa conexão |
| B31 | `TRACe:DATA` aceita bloco binário `#` | 01 §3 P2 ("verificar no manual") | **CONTRADITA / NÃO EXISTE** | [AM] **p. 126**: "Command Syntax: `TRACe[:DATA]<waveform_name>,<NRf> {,<NRf>}`"; "An error will occur if **exactly 1024 data points** are not sent with the command." Só `<NRf>` ASCII. E Apêndice C, **p. 213**, lista `-168 "Block data not allowed"` — "Block data was sent." | **A ideia de binário do 01 está morta.** O ganho possível é só encurtar o ASCII (`%.8g` → `%.5g`) |
| B32 | `TRACe:DEFine` custa ~3 s | `_ensure_trace_slots:925-930` | **CONTRADITA pelo número** | [AM] `TRACe:DEFine`, **p. 127**: "The TRAC:DEF command causes waveform catalog data to be writing to the Flash memory of the unit. **This process requires about 500 msec to complete.**" | O projeto espera **6× o documentado**. O próprio comentário do código reconhece ("O manual cita ~500 ms") |
| B33 | É preciso `time.sleep(1.0)` após cada `TRACe:DATA` | `program_capture:1073` | **NÃO COBERTA** | O manual exige espera **só depois do `TRACe:DEFine`** ("The TRACE:DATA command which normally follows should not be sent during this period"). Nenhuma espera é prescrita **após** `TRACe:DATA` | **~10 s por captura waveform sem respaldo no manual** — a maior parcela isolada do custo do P2 |
| B34 | Limites: nº de traces e pontos por trace | `_ensure_trace_slots`, `TRACE_POINTS` | **APOIADA** | [AM] **p. 126**: "1024 data points ... of exactly one cycle"; "**Up to 50 user-defined waveforms** may be created and stored per group" | 10–12 TRACEs contra um teto de 50: **o catálogo NÃO estava cheio** na trava |
| B35 | `TRACe:DELete:ALL` exige OUTPUT OFF | `clear_all_traces:892-893` | **NÃO COBERTA** | [AM] **p. 127** não menciona OUTPUT. O que o manual associa a relé é o erro **24 "Output relay must be open"** e o erro **20 "Output relay must be closed"** (p. 217) | Prudência do projeto, não regra do manual |
| B36 | `TRACe:DELete:ALL` custa 15 s | `clear_all_traces:898` | **NÃO COBERTA** | [AM] **p. 127**: só "This command is only supported by firmware revisions 0.16 and higher" | Número empírico; sem respaldo nem contradição |
| B37 | Alerta sobre gravações repetidas / desgaste de Flash | P3 hipótese 2 | **NÃO COBERTA** | Nenhum aviso de endurance, ciclos de escrita ou desgaste em todo o manual | O manual confirma o *meio* (não volátil, B30) mas **não** o *desgaste*. Lacuna real |
| B38 | `MEASure:VOLTage:AC?` — tempo e bloqueio | pergunta 14 | **APOIADA** | [AM] §6.6, **p. 158**: "The query response for measurements is not immediate. **The source will accept commands from the interface while the measurement in progress.** To prevent the source from accepting additional commands during measurement the *WAI must be used with the measurement query command." Exemplo: `MEAS:FREQ?;*WAI` | Os 3 queries de `_log_diagnostico` (~39 ms cada, 01 §1.3 B2) **rodam em paralelo com o resto**. Se um deles estiver no ar quando `VOLTage:TRIGgered` é escrito, o manual não garante ordem |
| B39 | Medidas vêm de um buffer contínuo | — | **[MANUAL] novo** | [AM] §6.6, **p. 158**: "When the AC source is turned on, it is continuously sampling ... writing the results into a buffer. The buffer holds 4096 voltage and current data points."; MEASure retorna "as soon as the buffer is full" | A leitura da fonte tem latência de ~1 buffer. `MEAS:VOLT:AC?` logo após um transiente pode devolver dado **anterior** ao transiente |
| B40 | `SOURce:MODE ACDC` zera a saída (**H-ZERO-ACDC**) | §0 tabela; §1.3 B3 | **APOIADA (literal)** | [AM] §4.18, **p. 98**: "**When switching modes, the output is automatically set to zero to prevent hot switching of the output. After a mode command, the output voltage needs to be programmed to the desired setting.**" | H-ZERO-ACDC está **fechada pelo manual**. E o manual manda reprogramar a tensão depois — o que `program_capture` faz (linha 996) |
| B41 | `FUNCtion:MODE {FIXed\|LIST}` | `program_capture` | **APOIADA, com ressalva de sintaxe** | [AM] **p. 85**: descrição só define **FIXed** e **LIST**, mas a linha "Parameters" lista "FIXed \| STEP \| PULSe \| LIST" (inconsistência do próprio manual) | Usar só FIXed/LIST, como o projeto faz |
| B42 | `SOURce:FUNCtion:SHAPe` aceita SIN/SQU/CSIN/usuário | `configure_harmonics_csine` | **APOIADA, e explica o `-256`** | [AM] **p. 84**: "SINusoid\|SQUare\|CSINe\|<waveform_name>"; mas `LIST:FUNCtion[:SHAPe]`, **p. 93**: "Parameters: **depends on the available shape defined by the TRACe:CAT?**" | Confirma o raciocínio do comentário do código: a Rev. 5.53 resolve a forma pelo **catálogo**, onde o nome é `CSINusoid` |
| B43 | Faixa do THD do CSINe = 0..20 % (`MAX_CSINE_THD_PCT = 20.0`) | `ametek_orm.py:70` | **APOIADA (exata)** | [AM] `FUNCtion:CSINe`, **p. 85**: "The range is **0 to 20 percent**."; *RST = "0% (no clipping)" | Constante do projeto está certa |
| B44 | `SOURce:VOLTage:OFFSet` só em ACDC | `disable_dc_offset:644-646` | **APOIADA** | [AM] **p. 108**: "The Voltage mode must also be set to AC+DC to accept a DC offset value."; Apêndice C, **p. 215**, `-300`: causas incluem "Attempt to set initial voltage mode to AC+DC" e programar fora do modo | Comentário do código correto |
| B45 | Trocar forma/modo deixa a fonte "muda por segundos" | comentários em `configure_harmonics_csine` | **NÃO COBERTA (para SHAPe) / APOIADA (para RANGe)** | Nada sobre `FUNCtion:SHAPe` ser lento. Mas [AM] **p. 110**: "Effecting a range change takes considerable time (**6 secs**) as the amplifiers have to be powered down to be reconfigured" | A única lentidão documentada é de `VOLTage:RANGe`, que o projeto só usa no baseline |
| B46 | **Limite de 300 Vrms explica o `ParameterOutOfBoundsError` de 308 V** | §1.3 B5; §4 item 4 | **APOIADA (decisiva)** | [AM] §4.14, **p. 84**: "The maximum peak voltage that the AC source can output is **425 V peak**. ... For a sinewave, the maximum voltage that can be programmed is **300 V rms**." E a nota: "**You cannot program a voltage that produces a higher peak voltage on the output than a 300 Vrms sinewave when in the 300 V range.**" | `max_voltage_rms = 300` é o número do manual. A classe 03 a 220 V (1,4 × 220 = 308) é **fisicamente impossível**, não um bug de software. Validar antes de rodar |
| B47 | `VOLTage:HIGH` é em Vp e limita a escrita | `configure_safe_baseline:820-834` | **CONTRADITA na unidade** | [AM] `VOLTage:HIGH`, **p. 109**: "This command programs the maximum **rms** voltage that the power source will accept. The maximum value will be the lower of this value or the voltage range."; "Unit: **V (rms voltage)**" | O projeto chama a variável `voltage_high_vp` e a valida contra `max_peak_v` (pico). **O manual diz rms.** Se o firmware seguir o manual, o teto efetivo está ~1,41× mais alto do que o projeto acredita |
| B48 | Ranges disponíveis | `SOURce:VOLTage:RANGe` | **[MANUAL]** | [AM] **p. 109**: "150 V AC or 200 V DC range"; "300 V AC or 400 V DC range"; "400 V AC or other (-XV) range" | Range 300 V é o correto para 220 V |
| B49 | Mudar range com OUTPUT ligado falha | ordem em `configure_safe_baseline` | **APOIADA** | [AM] **p. 110**: "On MX units with firmware revision 4.24 or higher ... If the output relay is closed (ON), attempting a voltage range change will result in an error message and no range change will occur. The output relay MUST be opened first" | `configure_safe_baseline` já faz `output_enabled = False` antes (linha 837). **Ordem correta** |
| B50 | `-113 "Undefined header"` = cabeçalho não reconhecido | §1.3 B5 | **APOIADA** | [AM] Apêndice C, **p. 213**: `-113 "Undefined header"` — causa "Command header incorrect"; remédio "Check programming manual for correct command syntax" | Duas linhas coladas (`*WAIINITiate:IMMediate`) produziriam exatamente isso — **[INFERÊNCIA]**, não afirmação do manual |
| B51 | Terminadores / `append_eot` | `_raw_write:242-260` | **APOIADA** | [AM] §2.4.7, **p. 20**: "Three permitted message terminators are: newline (<NL>), which is ASCII decimal 10 or hex 0A; end or identify (<END>); both of the above (<NL><END>)." | `\n` é terminador válido. O manual não descreve nenhum protocolo de EOT extra |
| B52 | Limite de comprimento de comando / buffer de entrada | pergunta 12 | **PARCIAL** | Nenhum limite numérico é dado. Mas [AM] Apêndice C, **p. 217**, erro **25 "Input buffer full"**: causa "Too much data received"; remédio "**Break up data in smaller blocks.**" | Existe um buffer finito e um erro para ele. Um `TRACe:DATA` de **~11,3 kB numa única linha** é exatamente o caso de uso de risco |
| B53 | `-300 "Device specific error"` | comentário `arm():1198` | **APOIADA** | [AM] Apêndice C, **p. 215**: causas listadas — "1. Attempt to program a frequency while source is in DC mode. 2. Attempt to set initial voltage mode to AC+DC."; remédio "**Check for proper mode or command sequence operation.**" | O remédio aponta **sequência de comandos** — consistente com o `-300` determinístico visto entre 01/NORMAL e 02/SAG |
| B54 | MX30-3Pi é Series I ou Series II? | P3 (teto de 32 vs 100 pontos) | **PARCIAL — o manual dá só uma pista indireta** | [AM] nota de rodapé em `SYSTem:CONFigure`, **p. 119**: "MX30-3Pi configuration is reported as **MX45 on Series I MX**. If firmware revision is less than 1.11, there is no system field in the syst:conf? query response." | **Não dá para decidir pelo manual.** Resolve-se com um `SYST:CONF?`/`*IDN?` offline-seguro. A Rev. 5.53 e a existência de `TRIG:STATe? → WTRIG` sugerem Series II, mas é [ESPECULAÇÃO] |
| B55 | `INSTrument:COUPle ALL` | `configure_safe_baseline:843` | **APOIADA** | [AM] **p. 165** (cap. 6): "The *RST setting for INSTrument:COUPle is NONE."; "To send a programming command to all of the output phases, set INSTrument:COUPle to ALL" | Uso correto para unidade trifásica operada como bloco |
| B56 | "Changing list data while a subsystem is in list mode generates an implied ABORt" | — | **[MANUAL] novo** | [AM] §4.17 (`LIST:VOLTage:SLEW`), **p. 96**: frase literal | `program_capture` já põe tudo em FIXed antes de reescrever as listas (linhas 987-988), então está protegido. O caminho **nativo** não |

---

## (b) Correções ao relatório 01

1. **[MANUAL] `STATus:OPERation:CONDition?` bit 3 significa "transiente CONCLUÍDO", não "ativo".**
   O 01 §1.3 **B1** registra `transiente_ativo = True` em 115/115 e 927/928 e
   conclui "o campo não discrimina nada". Está **certo no fato e agora tem a
   causa**: [AM] Tabela 7-2, p. 169, bit 3 = TRANS = "Transient is completed".
   O nome do campo no projeto está **invertido**. O valor `True` em repouso é o
   valor correto do instrumento. Não é um campo quebrado — é um campo lido ao
   contrário. Corrigir o rótulo e, para saber se um transiente está *em curso*,
   usar `TRIGger:STATe?` (`BUSY`), que é o mecanismo que o manual oferece
   ([AM] p. 132 e §7.7 p. 173).

2. **[MANUAL] O teto de ~32,3–32,7 kpts não é da aquisição em modo AUTO.**
   O 01 §4 item 14 e o comentário de `oscilloscope_orm.py:225-240` tratam
   ~32,5 kpts como "o teto real deste modo". [KS] p. 1458 mostra que
   `:WAVeform:POINts:MODE NORMal` — programado pelo próprio projeto em
   `configure_acquisition:211` **e de novo** em `get_waveform:328`, anulando o
   `RAW` de `initialize_safe:111` — entrega o *measurement record*, um resumo de
   no máximo 62.500 pontos. O registro bruto sai por `RAW`/`MAXimum` com teto de
   **4.000.000 de pontos** (p. 1459), e as três pré-condições (parado, `MAIN`,
   `ACQuire:TYPE NORMal`) **já são satisfeitas** depois do `:SINGle`.
   [INFERÊNCIA] Isso muda a recomendação 2 do 01: além de guardar `x_origin`,
   trocar para `RAW` provavelmente elimina o `np.interp` de 32,5 k → 30 k que o
   01 §4 item 14 identifica como destruidor da quantização.

3. **[MANUAL] `TRACe:DATA` binário não existe.** O 01 §3 P2 sugere "formato
   binário em vez de ASCII (`TRACe:DATA` aceita bloco definido em muitos
   firmwares — verificar no manual)". Verificado: a sintaxe é
   `TRACe[:DATA]<waveform_name>,<NRf> {,<NRf>}` ([AM] p. 126) e o Apêndice C
   (p. 213) lista `-168 "Block data not allowed"` com causa "Block data was
   sent." Riscar essa ideia.

4. **[MANUAL] A espera de 3 s por `TRACe:DEFine` é 6× a documentada** (500 ms,
   [AM] p. 127) **e a espera de 1 s por `TRACe:DATA` não é exigida em lugar
   nenhum**. O 01 §3 P2 decompõe os ~20 s/captura em ~0,98 s de transferência +
   1,00 s de `sleep` por TRACe. A metade `sleep` (~10 s por captura) é
   **puramente empírica**. Isso recoloca o P2 como problema resolvível.

5. **[MANUAL] `*WAI` não faz o que o código espera dele.** O 01 mantém H-WAI
   como "CONFIRMADA no fenômeno, média no mecanismo". O manual é mais duro:
   [AM] §7.7, p. 173 — `*WAI` espera tudo "**except for transients**"; e
   [AM] §5.14, p. 142 — "***WAI can be aborted by sending any other command
   after the *WAI command.**" Em `arm():1206-1207` o `*WAI` é seguido
   **imediatamente** por `INITiate:IMMediate`. [INFERÊNCIA] O `*WAI` ali é, na
   melhor das hipóteses, inócuo. Isso **reforça** H-WAI e muda o remédio: não
   adianta mais `*WAI`; o que o manual oferece é `TRIG:STATe?` até `IDLE`
   (com a ressalva do falso IDLE, item 6) ou `*OPC?`.

6. **[MANUAL] O falso IDLE é documentado.** [AM] p. 132: "the response may
   change from **BUSY to IDLE before the dwell time has expired**", com a
   mitigação explícita de acrescentar um último ponto de lista de ~1 ms. O 01
   chega a essa suspeita por evidência indireta; o manual a afirma.

7. **[MANUAL] `SOURce:MODE ACDC` zerar a saída é comportamento de projeto, não
   anomalia.** O 01 marca H-ZERO-ACDC como "CONFIRMADA". [AM] §4.18, p. 98
   fecha: "the output is automatically set to zero to prevent hot switching".
   Pode sair da lista de hipóteses.

8. **[MANUAL] O `-226` da classe 18 está totalmente explicado.** [AM] §4.17,
   p. 90 + Apêndice C, p. 214. E a correção é a prescrita em §6.4.2 Passo 1
   (p. 152): pôr em `FIXed` **todas** as funções que não devem gerar transiente.
   `frequency_drift_list()` (`ametek_orm.py:690`) e `trigger_step()`/
   `trigger_pulse()` (linhas 542, 562) só neutralizam `FREQuency:MODE`; nunca
   `FUNCtion:MODE`.

9. **[MANUAL] `:EXTernal:RANGe` é decorativo.** O 01 não discute, mas
   `setup_external_trigger` escreve `:EXTernal:RANGe` e depois valida o nível
   contra a leitura. [KS] p. 456: "provided for product compatibility ... The
   range is automatically recalculated when the external trigger probe
   attenuation factor is changed."

10. **[MANUAL] Os códigos 1 e 255 do BYTE não são do manual.** O comentário de
    `oscilloscope_orm.py:365-366` atribui ao guia uma convenção
    "1 = clipped low, 255 = clipped high" que não existe nele — só
    "hole = 0" ([KS] p. 1448). [INFERÊNCIA] `get_waveform()` pode estar
    **descartando capturas válidas**.

11. **[MANUAL] `VOLTage:HIGH` é rms, não pico.** `configure_safe_baseline`
    (linhas 820-834) trata o parâmetro como Vp. [AM] p. 109: "maximum **rms**
    voltage ... Unit: V (rms voltage)".

12. **Confirmações integrais (sem correção):** H-REF10 (A1–A6), a leitura de
    `:OPERegister` bits 3/5 (A14–A15), o uso de `:AER?`/`:TER?` (A16–A17), a
    ordem modo→valor→INIT (B14), `LIST:STEP AUTO`/`LIST:COUNt` (B2–B3),
    `OUTPut:TTLTrg` (B28–B29), o teto de 300 Vrms (B46) e a ordem
    OUTPUT-OFF→RANGe (B49).

---

## (c) H-NATIVO: candidatos de mecanismo, ordenados por apoio no manual

Fenômeno a explicar (01 §1.2): em duas sessões, `VOLTage:TRIGgered 220`,
`PULSe` de 12,7 V/60 ms e `CSINe 5 %` **não foram aplicados**, sem um único
erro na fila; e o valor efetivamente aplicado na classe 04 foi **242 V**, que é
exatamente o **primeiro nível da classe 03** — ou seja, um valor **anterior**.

### 1.º — Escrita durante um transiente ainda em curso, mascarada pelo falso IDLE  ·  apoio: ALTO (duas citações literais)

**[MANUAL]** [AM] Apêndice C, **p. 217**, erro **19 "Illegal during transient"**:
causa "Operation requested not available while transient is running"; remédio
"Wait till transient execution is completed or abort transient execution first."
**[MANUAL]** [AM] `TRIG:STATe?`, **p. 132**: "the response may change from BUSY
to IDLE before the dwell time has expired."

**[INFERÊNCIA]** `trigger_step()`/`trigger_pulse()` escrevem `VOLTage:MODE` e
`VOLTage:TRIGgered` **antes** de `arm()` — isto é, **antes de qualquer consulta
de `TRIGger:STATe?`**. Se o transiente da captura anterior ainda estiver
rodando, o manual diz que a operação **não está disponível**. O valor antigo
permanece e o próximo `*TRG` o reaplica — que é precisamente o padrão observado
(classe 04 recebendo o nível da classe 03).

*Por que não apareceu erro:* o erro 19 é um código **positivo** (device-specific)
e o `check_errors()` do projeto só roda em `fim_trigger_step`/`fim_trigger_pulse`
**quando `diagnostico` está ligado**; na sessão em que o fenômeno apareceu, o 01
§1.3 B5 registra `erros` não vazio em **0 de 1043** linhas — o que também é
compatível com o erro ter sido consumido por um `*CLS` intermediário
(`program_capture:986`, `:1074`).

*Teste decisivo (seguro):* ver T1 na seção (e).

### 2.º — Modos residuais de uma classe anterior (§6.4.2 Passo 1 não cumprido)  ·  apoio: ALTO

**[MANUAL]** [AM] §6.4.2, **p. 152**, Passo 1: "Set the functions that you do
not want to generate transients to FIXed mode."
**[MANUAL]** [AM] §4.17, **p. 90**: "All active subsystems that have their modes
set to LIST must have the same number of points ... or an error is generated
when the first list point is triggered."

**[INFERÊNCIA]** O caminho nativo nunca escreve `FUNCtion:MODE FIXed`. Depois de
qualquer classe waveform, `FUNCtion:MODE` fica em `LIST` com 12 pontos de forma.
No `*TRG` seguinte, a lista de forma participa do transiente junto com o
STEP/PULSe de tensão. Isso é suficiente para tornar o resultado irreconhecível,
e é **exatamente** a mesma raiz do `-226` da classe 18 (B9), que já está provado.

*A favor:* explica por que as classes nativas falharam nas sessões em que
rodaram **depois** de classes waveform, e funcionaram em 2026-09-09.
*Contra:* sozinho não explica o nível ficar preso em 127 V.

### 3.º — `INITiate` ignorado silenciosamente  ·  apoio: MÉDIO-ALTO

**[MANUAL]** [AM] `INITiate`, **p. 129**: "**If the trigger system is not in the
Idle state, the initiate commands are ignored.**" Apêndice C, **p. 214**, tem
`-220 "Init ignored"` — "Initialization request has been ignored."

**[INFERÊNCIA]** `arm()` **espera IDLE antes do INIT** (linhas 1177-1189), então
o projeto está protegido — **a menos que o IDLE seja falso** (item 1). Os dois
mecanismos se compõem: falso IDLE → INIT possivelmente ignorado → `*TRG` dispara
o que sobrou armado. Isto é coerente com os `TimeoutError ... último
estado='IDLE'` da classe 05 no 01 §1.3 B5: o INIT foi aceito mas o estado nunca
saiu de IDLE — assinatura de INIT ignorado.

### 4.º — Concorrência com queries de medida (comandos paralelos)  ·  apoio: MÉDIO

**[MANUAL]** [AM] §7.7, **p. 173**: "Commands that affect list and trigger
actions measurements and calibration are among the parallel command."
**[MANUAL]** [AM] §6.6, **p. 158**: "The source will accept commands from the
interface while the measurement in progress. To prevent the source from
accepting additional commands during measurement the *WAI must be used with the
measurement query command."
**[MANUAL]** [AM] §5.14, **p. 142**: "*WAI can be aborted by sending any other
command after the *WAI command."

**[INFERÊNCIA]** `_log_diagnostico` faz 3 queries (incluindo `MEAS:VOLT:AC?`)
imediatamente antes de `arm()`. O manual não garante ordem entre uma medida em
voo e a escrita de `VOLTage:TRIGgered`. O projeto **nunca** usa a forma
prescrita `MEAS:...?;*WAI`.
*Contra:* o fenômeno também ocorreu com `diagnostico off`.

### 5.º — Teto de `VOLTage:HIGH` / range  ·  apoio: BAIXO-MÉDIO

**[MANUAL]** [AM] `VOLTage:HIGH`, **p. 109**: "programs the maximum rms voltage
that the power source will accept. The maximum value will be the lower of this
value or the voltage range." [AM] **p. 110**: range só muda com o relé aberto.

**[INFERÊNCIA]** Um teto efetivo baixo recusaria 220 V. Porém
`configure_safe_baseline` programa range e `VOLTage:HIGH` **com OUTPUT OFF e na
ordem certa** (B49), e uma recusa geraria `-222 "Data out of range"` — que o 01
não viu. **Enfraquecido, mas barato de excluir** (query no T1).

### 6.º — Falta do prefixo `SOURce:`  ·  apoio: NENHUM no manual

O 01 §1.2 levanta essa hipótese por analogia com `LIST:REPeat`.
**[MANUAL]** [AM] **p. 108** documenta as duas formas como equivalentes:
"Examples: `VOLT:TRIG 120`   `VOLT:LEV:TRIG 120`", e toda a sintaxe do capítulo
4 é `[SOURce:]` **opcional**. **[ESPECULAÇÃO]** Só um desvio de firmware
sustentaria isso. Continua valendo testar (custa uma linha no T1), mas é o
candidato **menos** apoiado.

### 7.º — "Latch no INIT"  ·  apoio: CONTRADITO

**[MANUAL]** [AM] §6.5.4, **p. 157**: "When the trigger system enters the Output
Change state **upon receipt of a trigger**, the triggered functions are set to
their programmed trigger levels." O manual põe a aplicação no `*TRG`. Descartar
como explicação primária.

---

## (d) Trava da fonte (P3): o que o manual permite concluir

### Fatos que o manual estabelece

1. **[MANUAL] `TRACe:DATA` grava em memória não volátil.** [AM] p. 126:
   "Waveform data is stored in nonvolatile memory and is retained when input
   power is removed." → A pergunta em aberto do 01 (P3, hipótese 2, coluna
   "contra": *"não se sabe se `TRACe:DATA` grava em não-volátil"*) está
   **respondida: grava**. As **280 gravações** de uma única conexão são 280
   escritas em memória não volátil.
2. **[MANUAL] O catálogo NÃO estava cheio.** [AM] p. 126: "Up to 50
   user-defined waveforms may be created and stored per group." O projeto usa
   10–12. → A parte "catálogo cheio" da hipótese 1 do 01 **cai**.
3. **[MANUAL] Existe um erro para buffer de entrada estourado.** [AM] p. 217,
   erro **25 "Input buffer full"** — "Too much data received"; remédio "Break up
   data in smaller blocks." → Um `TRACe:DATA` de ~11,3 kB em **uma linha** é
   exatamente o padrão que esse erro existe para sinalizar. **[ESPECULAÇÃO]**
   Um estouro de buffer no 280.º comando desse tipo é um gatilho plausível.
4. **[MANUAL] Existe um erro de memória ligado a download incompleto de
   waveform.** [AM] p. 215, `-311 "Memory error"`: "May be the result of
   incomplete user-defined waveform download. ... Alternatively, use
   `TRAC:DEL:ALL`."
5. **[MANUAL] O painel morto NÃO se explica por modo remoto.** [AM]
   `SYSTem:REMote`, **p. 119**: "sets the interface in the Remote state, which
   **disables all front panel controls**." — mas **o projeto nunca envia
   `SYSTem:REMote`** (busca em `ametek_orm.py`: zero ocorrências). → A
   explicação benigna está **excluída**, o que **reforça** a hipótese 1 do 01
   (travamento do controlador).
6. **[MANUAL] `FUNCtion:MODE LIST` não tem custo documentado.** Nada no manual
   associa tempo de carga, compilação ou risco a essa transição. A única
   compilação mencionada é indireta: [AM] p. 153, "Unexecuted transient lists
   have not been compiled yet by the AC/DC power source controller", e o remédio
   do `-226`, "transient cannot be **compiled** and executed" (p. 214). Existe,
   portanto, **uma etapa de compilação de lista** no controlador — mas sem custo
   nem falha documentados.
7. **[MANUAL] O único comando com lentidão documentada é `VOLTage:RANGe`**
   (6 s, p. 110) — não usado no laço.

### Lacunas que o manual não cobre

- **Nenhum aviso de endurance/desgaste de Flash** em todo o manual (B37).
- **Nenhum watchdog, recuperação ou modo de falha do controlador** descrito.
- **Nenhum limite de memória de lista** além do nº de pontos (32/100) e do nº de
  waveforms (50) — ambos folgados no caso.
- **Série da MX30-3Pi indecidível pelo manual** (B54); a única menção é que ela
  "is reported as MX45 on Series I MX" (p. 119).

### Veredito

**[INFERÊNCIA]** O manual **não explica** a trava, mas **reordena** as hipóteses
do 01: retira o argumento "catálogo cheio" da hipótese 1, **fortalece** a
hipótese 2 (não-volátil confirmado) e **exclui** a explicação benigna do painel
morto. Acrescenta um gatilho novo e concreto que o 01 não tinha: **"Input buffer
full" com blocos de ~11,3 kB por linha**, com o remédio do próprio manual
("Break up data in smaller blocks").

---

## (e) O que o manual NÃO responde — e o teste mínimo e seguro para cada um

Todos os testes abaixo são **sem EUT**, com a saída **desligada ou em 5 Vrms**,
e param no primeiro sintoma.

| id | pergunta em aberto | teste mínimo e seguro |
|---|---|---|
| **T1** | H-NATIVO: a escrita é ignorada? por qual dos mecanismos? | Numa conexão nova, saída OFF: `TRIG:STATe?` → `VOLT:MODE?` → `VOLT:TRIG?` → `VOLT:MODE STEP` → `VOLT:TRIG 5` → `VOLT:TRIG?` → `SYST:ERR?`. Depois **repetir logo após um transiente** (`INIT`, `*TRG`, e escrever em ≤50 ms) e comparar. Se a segunda forma devolver o valor antigo e/ou erro **19**, o candidato 1 está provado. Acrescentar `FUNC:MODE?` à leitura fecha o candidato 2 |
| **T2** | H-REF10 no instrumento (já previsto pelo manual, resta confirmar o firmware) | Só osciloscópio: `configure_acquisition(duration_s=1.0, pre_trigger_s=0.40)`, `:TRIGger:FORCe`, ler `:WAVeform:PREamble?`. Previsão do manual: `x_origin = −0,500 s`, `x_reference = 0` |
| **T3** | O ganho real de `:WAVeform:POINts:MODE RAW` | Depois de uma `:SINGle` concluída (scope já parado): `:WAVeform:POINts:MODE MAXimum` → `:WAVeform:POINts? MAXimum` → ler `:WAVeform:PREamble?`. Zero risco: é só leitura. Se vier ≫32,5 k, o `np.interp` pode sair |
| **T4** | O pré-trigger precisa encher antes de o scope aceitar trigger? (A18) | Armar com `pre_trigger_s = 0.40` e forçar `:TRIGger:FORCe` **imediatamente** após o `:SINGle`; comparar `x_origin` com o de um trigger tardio |
| **T5** | `ABORt` mesmo derruba OUTPUT e os modos? (B19, H-ZERO-LIST) | Saída em 5 V: `_log_diagnostico("apos_abort")` entre o `ABORt` e o `*CLS` de `program_capture()` (`ametek_orm.py:981-986`) — uma linha. Decide H-ZERO-LIST sem risco |
| **T6** | `TRACe:DEFine` realmente precisa de 3 s? | Com a saída **OFF**: `TRACe:DELete:ALL`, depois `TRACe:DEFine T1` + `TRACe:CATalog?` em laço, medindo o menor intervalo que ainda funciona. O manual prevê 500 ms |
| **T7** | O `sleep(1.0)` pós-`TRACe:DATA` é necessário? (B33) | Com a saída **OFF**: enviar `TRACe:DATA` e, sem espera, `SYST:ERR?`. Se limpo, baixar o sleep em degraus (1,0 → 0,3 → 0,1 → 0) conferindo a forma resultante por `TRACe:CATalog?` + uma captura |
| **T8** | `TRACe:DATA` em linha única estoura o buffer? (erro 25) | Com a saída **OFF**, enviar o mesmo trace (a) numa linha de ~11,3 kB e (b) quebrado com `%.5g` (~7 kB), lendo `SYST:ERR?` nos dois casos. Comparar |
| **T9** | Desgaste de Flash (P3 hip. 2) | Com a saída **OFF** e sem EUT: 300 `TRACe:DATA` **sobre um único nome**, contando falhas e lendo `SYST:ERR?` a cada 25. Parar ao primeiro erro |
| **T10** | Série (I ou II) e limite real de pontos de lista | `SYST:CONF?`, `*IDN?`, `*OPT?` — três queries, zero efeito colateral |
| **T11** | `*OPC?` responde nesta Rev.? (B23) | `*OPC?` isolado, com a saída OFF, timeout curto |
| **T12** | `VOLTage:HIGH` é rms ou Vp neste firmware? (B47) | Saída OFF: `VOLT:HIGH 200` → `VOLT:HIGH?`; depois `VOLT 250` → `SYST:ERR?`. Se 250 for aceito, o teto era rms=200? não — se for **recusado**, `VOLT:HIGH` é rms |
| **T13** | Os códigos 1/255 do BYTE existem? (A23) | Offline, sobre os `.npz`/registros já salvos: contar quantas amostras caem em 1 ou 255. Se >0 em capturas boas, o guard de `get_waveform` já descartou dado válido |
| **T14** | A trava é reprodutível | Religar; **antes de qualquer outro comando**, ler `SYST:ERR?`, `*ESR?`, `STAT:QUES:COND?` e o contador de horas do painel. Depois repetir só 06/07/08 com `set capturas 3` a **127 V**, log em arquivo, parando ao primeiro timeout |

---

## (f) Achados novos do manual (o que o projeto ignora ou usa errado)

### Erros de uso confirmados pelo manual

1. **`FUNCtion:MODE` nunca é zerado no caminho nativo.** [AM] §6.4.2, p. 152,
   Passo 1 exige pôr em `FIXed` tudo que não deve gerar transiente.
   `trigger_step()` (`ametek_orm.py:542`), `trigger_pulse()` (`:562`) e
   `frequency_drift_list()` (`:690`) só cuidam de `FREQuency:MODE`.
   **Causa documentada do `-226` da classe 18 e candidato n.º 2 de H-NATIVO.**
   Correção: uma linha `FUNCtion:MODE FIXed` nos três pontos.
2. **`transiente_ativo` está invertido** ([AM] Tabela 7-2, p. 169 — bit 3 =
   "Transient is **completed**"). Renomear e inverter, ou trocar por
   `TRIGger:STATe? == BUSY`.
3. **`*WAI` é abortado pelo comando seguinte** ([AM] §5.14, p. 142) **e não
   espera transientes** (§7.7, p. 173). Os quatro `*WAI` do projeto
   (`arm():1206`, `arm_transient():1282`, `configure_harmonics_csine():598,608`,
   `select_sine_shape():632`, `disable_dc_offset():654`) não entregam o que os
   comentários afirmam.
4. **`MEASure` nunca é usado na forma prescrita `MEAS:...?;*WAI`** ([AM] §6.6,
   p. 158) — e o manual diz explicitamente que sem isso a fonte aceita outros
   comandos durante a medida.
5. **`VOLTage:HIGH` tratado como Vp quando o manual diz rms** ([AM] p. 109).
6. **`:WAVeform:POINts:MODE NORMal` limita a captura ao measurement record**
   ([KS] p. 1458) — e é escrito **duas vezes** (`configure_acquisition:211`,
   `get_waveform:328`), sobrescrevendo o `RAW` de `initialize_safe:111`. As três
   condições para `RAW`/`MAXimum` já estão satisfeitas.
7. **Guard de clipping em 1/255 sem respaldo no guia** ([KS] p. 1448 só define
   `0 = hole`).
8. **`:EXTernal:RANGe` é "for product compatibility"** ([KS] p. 456); a
   validação de nível em `setup_external_trigger:275-279` se apoia num valor que
   o projeto não controla.
9. **Espera de 3 s por `TRACe:DEFine` contra 500 ms documentados**
   ([AM] p. 127) e **1 s por `TRACe:DATA` sem nenhuma exigência no manual**.
   Juntas, ~10 s de ~20 s por captura waveform.

### Restrições e alternativas documentadas que o projeto não usa

10. **Ponto final curto para segurar o `BUSY`.** [AM] p. 132 dá a mitigação
    literal do falso IDLE: "it will be necessary to add a final list point with
    a short durating (e.g. 0.001 second) to hold the BUSY state till the end of
    the list." Resolve, dentro do vocabulário do instrumento, o problema que
    motivou os `*WAI`.
11. **`TRIGger:COUNt {NONE|ALL}`** ([AM] p. 130) — controla se a sincronização
    de fase é refeita a cada `COUNt`. Não usado; *RST = NONE.
12. **`LIST:TTLTrg`** ([AM] p. 95) — marcador por passo de lista, com
    `OUTPut:TTLTrg:SOURce LIST`. Permitiria um pulso TTL **no passo exato do
    evento**, em vez de só no início do transiente (BOT). Isso tornaria o
    recorte offline trivial e independente de H-REF10.
13. **`OUTPut:TTLTrg:SOURce EOT`** ([AM] p. 77) — pulso no **fim** do transiente.
    Responderia, em hardware, à ideia (ii)/(iii) do 01 (saber onde o evento
    termina) sem mexer na saída.
14. **`STATus:OPERation:EVENt?`** ([AM] p. 167) — "A register that latches any
    condition. It is a read-only register that is cleared when read." Com bit 3
    = "Transient is completed", **isto é o detector de conclusão de transiente
    que o projeto queria** e que o `:COND?` não dá.
15. **`VOLT? MAX`** ([AM] p. 84): "This query will return the maximum possible
    rms voltage that can be programmed without exceeding the 425 Volt peak
    voltage limitation. **This feature can be used to avoid unnecessary error
    messages during program execution.**" → É a validação prévia que o 01
    recomenda para a classe 03 (308 V), e ela já existe no instrumento.
16. **`LIST:VOLTage:SLEW` / `VOLTage:SLEW`** ([AM] p. 96 e p. 112) — o
    sobre-pico de transição do 01 §4 item 7 (1,18–1,22 pu nas bordas) é, em
    primeira leitura, um efeito de slew. O projeto programa
    `SOURce:VOLTage:SLEW MAXimum` no baseline (`:855`). [ESPECULAÇÃO] Reduzir
    o slew nas transições poderia atenuar o artefato; mas atenção ao erro
    **17 "Slew time exceed dwell"** ([AM] p. 217).
17. **Erros device-specific que o projeto não interpreta** ([AM] p. 217): **19**
    "Illegal during transient", **20** "Output relay must be closed"
    ("transient execution requires output relay to be closed"), **21** "Trans.
    duration less then 1msec", **24** "Output relay must be open", **25** "Input
    buffer full", **27** "Waveform harmonics limit" ("Harmonic contents of user
    defined wave shape is too high and could damage amplifier output stage"),
    **14** "Voltage peak error" ("may occur when selecting user defined wave
    shapes with higher crest factors"). Vários são diretamente relevantes às
    classes com harmônicos e à classe 08.
18. **`LIST:DWELl` mínimo de 1 ms** ([AM] p. 91: "0.001 to 9E4") e erro 21
    correspondente. O dwell do projeto (1 ciclo = 16,7/20 ms) está folgado.
19. **`-168 "Block data not allowed"`** ([AM] p. 213) fecha a porta do binário.
20. **"Changing list data while a subsystem is in list mode generates an implied
    ABORt"** ([AM] p. 96) — o caminho nativo pode disparar ABORts implícitos sem
    saber.
21. **`:TIMebase:REFerence CUSTom` + `:TIMebase:REFerence:LOCation`**
    ([KS] p. 1337-1338): "lets you place the time reference location at a
    percent of the graticule width (where 0.0 is the left edge and 1.0 is the
    right edge)." → **`LOCation 0.0` põe a referência exatamente na borda
    esquerda**, que é o que o projeto sempre quis. É a correção (A) do 01 §2,
    mas limpa: sem compensar o comando, sem depender da convenção de `LEFT`.
22. **Memória cai pela metade com os dois canais de um par ligados**
    ([KS] p. 320) — conferir se CH1 e CH2 ficam ambos em `display`.

---

## Apêndice — índice das citações usadas

**Keysight (páginas PDF):** 272 (`:AER`) · 292-293 (Tabela 91, Operation Status
Condition) · 306 (`:SINGle`) · 309 (`:TER`) · 320-321 (`:ACQuire:POINts`) ·
329 (`:ACQuire:SRATe:AUTO`) · 330 (`:ACQuire:TYPE`) · 455-457 (`:EXTernal`) ·
1334 (`:TIMebase:POSition`) · 1335 (`:TIMebase:RANGe`) · 1337-1338
(`:TIMebase:REFerence` e `:LOCation`) · 1345 (intro `:TRIGger`) · 1448
(conversão de dados e formatos) · 1456-1459 (`:WAVeform:POINts` e `:MODE`) ·
1460-1461 (`:WAVeform:PREamble`) · 1476-1477 (`XORigin`, `XREFerence`) ·
1623-1624 (Operation Status / Arm Event).

**AMETEK (páginas PDF):** 20 (§2.4.7 terminadores) · 76-78 (`OUTPut:TTLTrg`) ·
84-85 (§4.14 `FUNCtion`, `FUNCtion:MODE`, `FUNCtion:CSINe`, limite 425 Vp /
300 Vrms) · 90-97 (§4.17 List) · 98 (§4.18 `MODE`, zeramento) · 104-106 (§4.21
Pulse) · 107-110 (§4.22 Voltage) · 119 (`SYSTem:REMote`/`LOCal`,
`SYSTem:CONFigure`) · 126-127 (Trace Subsystem) · 128-132 (§4.25 Trigger) ·
142 (§5.13 `*TRG`, §5.14 `*WAI`) · 152-158 (§6.4.2, §6.4.3, §6.5, §6.6) ·
167-169 (§7.2 e Tabela 7-2) · 173 (§7.7 SCPI Command Completion) ·
213-217 (Apêndice C, tabela de erros).
