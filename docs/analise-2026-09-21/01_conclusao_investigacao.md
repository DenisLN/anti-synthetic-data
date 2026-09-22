# 01 — Conclusão da investigação (subagente 1)

Análise **offline**, 2026-09-21. Nenhum instrumento foi tocado. Fontes: as duas
sessões de 2026-09-16, os logs de console `log1.txt`/`log2.txt`, as capturas de
referência de 2026-09-09 e o código do worktree `sessao-bancada-v18`
(v1.9 commitado + v1.10 não commitado).

Convenção de marcação, usada em **toda** afirmação:
**[FATO]** = medido/lido, com a fonte citada · **[INFERÊNCIA]** = dedução a
partir de fatos · **[ESPECULAÇÃO]** = hipótese plausível sem evidência decisiva.

Scripts próprios (reprodutíveis, só leitura) nesta pasta:
`s1_explorar.py`, `s1_onset.py`, `s1_trigger_instante.py`, `s1_pulse_csine.py`,
`s1_pulse04.py`, `s1_niveis.py`, `s1_trim_simulado.py`, `s1_resolucao.py`,
`s1_logs.py`.

---

## 0. Resumo executivo

Dois achados novos mudam o quadro inteiro e tornam **desnecessárias** as duas
hipóteses concorrentes do arquivo 00 (H-DIAG e H-MARGIN):

> **ACHADO 1 (H-REF10).** O trigger **não** cai em `margem_amostras_antes`
> dentro do registro. Ele cai em `pre_trigger_efetivo + janela/10`, porque
> `:TIMebase:REFerence LEFT` no InfiniiVision põe a referência a **uma divisão**
> da borda esquerda (10 % da janela) e `get_waveform()` joga fora `x_origin`
> (`time_axis -= time_axis[0]`). Não existe atraso nenhum entre o `*TRG` e a
> saída: ele sempre foi ~0 ms. O "atraso universal de ~20 ms" do v1.7 e o
> "atraso de ~100 ms" do v1.10 são **o mesmo artefato**, medindo 0,2/10 e
> 1,0/10 da janela.

> **ACHADO 2 (H-NATIVO).** As classes nativas das duas sessões de 2026-09-16
> **não aplicaram os valores que o código escreveu**. A sessão 2 foi configurada
> para 220 V e as classes 01/02/03/04 saíram fisicamente a **127 V**; a classe 04
> produziu uma **elevação de 60 ms a 242 V** (= o nível 1,1 pu da classe 03) onde
> deveria haver uma interrupção a ~0 V; a classe 05 da sessão 1 saiu com
> **THD 0,98 %** com CSINe 5 % programado. As classes waveform (LIST/TRACe), no
> mesmo par de sessões, saíram **corretas** (220 V, THD 20 %, notches). Esse é o
> verdadeiro motivo de "com `margin on` os experimentos nativos falham" —
> `margin on` é coincidência temporal, não causa.

### Veredito por hipótese

| id | enunciado | veredito | o método de diagnóstico discriminava? | confiança |
|---|---|---|---|---|
| **H-WAI** | "IDLE" em `TRIGger:STATe?` não garante que a troca de modo assentou (race residual do `*WAI`) | **CONFIRMADA** (por evidência independente, não pelo método) | **NÃO** — `transiente_ativo` é `True` em 115/115 e 927/928 linhas; os três campos lidos não refletem "o modo assentou" | Alta no fenômeno; média no mecanismo ser exatamente o `*WAI` |
| **H-113** | qual comando origina o `-113` intermitente | **PARCIALMENTE RESPONDIDA** | **SIM para excluir**, **NÃO para localizar**: excluiu `trigger_step`/`trigger_pulse` (0 de 1043 linhas com `erros` não vazio) mas não separa `*WAI` × `INITiate:IMMediate` × as 3 queries de `arm_antes_wai` | Alta na exclusão; nenhuma no mecanismo |
| **H-ZERO-LIST** | `VOLTage:MODE LIST` zera a saída | **REFUTADA para esse comando** | **SIM** (par antes/depois) | Alta |
| **H-ZERO-ACDC** | `SOURce:MODE ACDC` zera a saída | **CONFIRMADA** | **SIM** (par antes/depois) | Alta |
| **H-REPEAT** | `LIST:REPeat 1` toca cada ciclo 2× | **CONFIRMADA POR COMPLETO** | pelo **timestamp**: só com `margin off`, e só para detectar a *diferença*, nunca o valor absoluto; pela **forma de onda**: sim, de forma decisiva | Alta |
| **H-DIAG** (do arquivo 00) | as leituras de diagnóstico após `*TRG` atrasam o transiente em ~80 ms e matam o PULSe | **REFUTADA** | — | Alta |
| **H-MARGIN** (do arquivo 00) | a janela de 1 s / pre-trigger 0,46 s mata o PULSe | **REFUTADA** | — | Alta |
| **H-REF10** (novo) | o trigger cai em `pre_trigger + janela/10` por causa de `REFerence LEFT` + descarte de `x_origin` | **CONFIRMADA** | 4 verificações independentes | Muito alta |
| **H-NATIVO** (novo) | o caminho nativo (STEP/PULSe/CSINe) aplica valores diferentes dos escritos | **CONFIRMADA** (fenômeno) / mecanismo **em aberto** | — | Muito alta no fenômeno; nenhuma no mecanismo interno da fonte |

### O que corrigi no arquivo 00

| item do 00 | correção |
|---|---|
| **A1** "onset em ~500 ms — por quê?" | é o **trigger**, em `0,400 + 1,000/10 = 0,500 s`. Não há fenômeno físico a explicar. |
| **A3** "05/HARMONICS e 18 funcionam com margin on" | **05 NÃO funciona**: THD medido 0,98 % contra 5,05 % nos dados antigos. 18 funciona. |
| **A3** "0 de 50 de 02 e 0 de 10 de 04 têm qualquer evento" | 02: confirmado (0/50). **04: as 10 capturas TÊM evento** — 60 ms a 242 V começando em 560,00 ms (o detector do 00 só procurava afundamento). |
| **A6 / H-DIAG** "diferença de ~80 ms precisa de explicação" | explicada: `1,0/10 − 0,2/10 = 0,08 s`. Nenhum atraso real. |
| **B2** "a medida por timestamp nunca poderia discriminar" | verdadeiro **para as sessões de 16/09** (`margin on` satura a medida no osciloscópio: 0,625 s para STEP de duração zero e 0,640 s para LIST de 200 ms). **Falso para a medida do v1.10**, feita com `margin off`. O erro do v1.10 foi não subtrair o piso de ≥0,25 s da própria medida, não o método. |
| **A4 / H-REPEAT** | confirmo integralmente com script próprio; e mostro que o "2,19x residual" do v1.10 é artefato do piso da medida. |
| **A2** "razão de pico 1,18–1,22 em 10/11/16" | confirmado, **mas é sobre-pico de TRANSIÇÃO**: os ciclos nominais saem a 1,02–1,04 pu; o excesso está só nas bordas do evento. |
| **D/H-DIAG** "só um teste 2×2 na bancada separa" | não é mais necessário: H-DIAG e H-MARGIN estão refutadas offline. |
| **C** "a bateria é abortada" | o abort real da bateria (classe 08) veio de `CommunicationError`; 3 falhas numa classe **não** abortam a bateria, abortam a classe. Detalhe em P1. |

---

## 1. Evidências

### 1.1 H-REF10 — onde o trigger realmente cai (script `s1_onset.py`, `s1_trigger_instante.py`)

`oscilloscope_orm.py:207-208` programa `:TIMebase:REFerence LEFT` e
`:TIMebase:POSition -pre_trigger_s`; `oscilloscope_orm.py:387` faz
`time_axis -= time_axis[0]`, descartando `x_origin` (o único campo da preamble
que diz onde está o trigger).

**Previsão de H-REF10:** `t_trigger = pre_trigger_efetivo + RANGe/10`.

| conjunto | janela | pre-trigger pedido | previsto | **medido** | n |
|---|---|---|---|---|---|
| antigos 2026-09-09, classes LIST/STEP | 200 ms | 0 ms | **20,0 ms** | 20,1–20,6 ms | 15 |
| antigos, PULSe (02/04) | 200 ms | 60 ms | **80,0 ms** | evento em 83,3–133,3 ms (resolução de ¼ de ciclo = 4,2 ms) | 2 |
| sessão 1, LIST/STEP/waveform | 1000 ms | 400 ms | **500,0 ms** | 500,0–502,2 ms | 15 |
| sessão 2, waveform | 1000 ms | 400 ms | **500,0 ms** | 500,1–500,8 ms | 20 |
| sessão 2, classe 04 (PULSe) | 1000 ms | 460 ms | **560,0 ms** | **560,00 ms** (10/10 capturas, dispersão zero) | 10 |

Três sondas independentes do instante do trigger, que **não** dependem do onset
de 0 V (`s1_trigger_instante.py`):

1. **[FATO] Classe 18 (LIST:FREQuency), sessão 1** — a frequência sai de 60,00 Hz
   e a primeira medida < 59 Hz aparece em `t = 508,65 ms`. Como a frequência é
   estimada por período completo e é centrada, uma mudança exatamente em 500,0 ms
   é detectada em 500 + 8,3 = 508,3 ms. Perfil medido: 60,09 Hz @475 ms →
   56,99 Hz @544 ms → 63,03 Hz @644 ms → 63,03 Hz @755 ms (dwell de 100 ms como
   programado; último valor persiste).
2. **[FATO] Classe 04, sessão 2** — o pulso começa em 560,00 ms nas 10 capturas,
   com 57,5–60 ms de largura (nominal 60 ms).
3. **[FATO] Dados antigos, classe 18** — mesma medida, mudança entre 12 ms e
   64 ms, compatível com 20 ms.

**[FATO] Corroboração histórica:** `CHANGELOG/v1.7.md` linhas 287-297 mede, por
cross-correlação em 4 classes TRACe, "**+598 a +600 amostras (~20,0 ms)**" —
600 amostras a 30 kSa/s = 20,000 ms = exatamente `0,2 s / 10`. O v1.7 chamou
isso de "latência fixa adicional específica de transientes baseados em LIST".
**[INFERÊNCIA]** É o mesmo artefato de referência, não latência.

**[FATO] Não existe rampa inicial** (`s1_trim_simulado.py`): a razão entre o pico
do 1.º ciclo depois do trigger e a mediana dos ciclos 2–6 é 0,9983 (01/NORMAL),
0,9988 (07/NOTCH), 0,9999 (08/TRANSIENT). As classes que fogem disso (06 flicker
1,128; 14 swell 0,777) fogem pelo **conteúdo** programado. A saída já está na
amplitude final no primeiro ciclo.

**[INFERÊNCIA] Consequências diretas:**
- A margem `antes` que o código julga ter (400 ms) é na verdade **500 ms**; a
  margem `depois` que ele julga ter (400 ms) é na verdade **300 ms**.
- Qualquer recorte offline que use `margem_amostras_antes` como índice do
  trigger erra por `janela/10`. Isso inclui `analisar_sessao.py`.
- O pré-trigger de 60 ms das classes PULSe (02/03/04), pensado para alinhar o
  pulso com `INICIO_S = 0.060` do `gerar()`, sai sempre 1 divisão adiantado.

### 1.2 H-NATIVO — o caminho nativo não aplica o que escreve

**[FATO] Nível físico por classe** (`s1_niveis.py`; o osciloscópio e o
`MEASure:VOLTage:AC?` da própria AMETEK concordam entre si):

| sessão 2 (configurada para **220 Vrms / 50 Hz**, probe 500×) | Vrms medido |
|---|---|
| 01 NORMAL (nativa, STEP) | **127,2** |
| 02 SAG (nativa, PULSe) — 50 capturas | **127,1–127,3** |
| 03 SWELL (nativa, PULSe) — só log | **126,58** (mediana de 53 leituras) |
| 04 INTERRUPTION (nativa, PULSe) | **127,2** de base, **242,1** durante o pulso |
| 06 FLICKER (waveform, LIST) | **219,3–226,0** |
| 07 NOTCH (waveform, LIST) | **218,0–218,7** |
| 08 TRANSIENT (waveform, LIST) | **219,17–219,19** (log) |

**[FATO]** `recuperar_estado_seguro()` registrou três vezes
`Estado seguro restaurado: 220.000 Vrms` (log2 linhas 613, 705, 845), com
`assert_no_errors()` passando, e a leitura de tensão imediatamente seguinte
continuou 126,57–126,59 V.

**[FATO]** A classe 05 da sessão 2 é o caso decisivo (log2 linhas 911-946):
`fim_trigger_step` = 126,562 V → depois do `*TRG` a saída vai para **241,017 V**
(a classe escreveu `VOLTage:TRIGgered 220`). Depois do `recuperar_estado_seguro`
seguinte a saída vai para **219,2 V** e fica lá. Ou seja, o mesmo comando
`SOURce:VOLTage 220` funcionou numa hora e não funcionou em outra.

**[FATO]** 241,0 V lidos pela fonte correspondem a **242,0 V programados** (a
fonte lê consistentemente 0,4 % baixo: 126,58↔127,0 e 219,2↔220,0). 242,0 V =
`1,1 × 220` = o **primeiro nível de SWELL da classe 03**.

**[FATO] Classe 05 (CSINe) da sessão 1** (`s1_pulse_csine.py`):

| | fundamental | THD | h3 / h5 / h7 | fator de crista |
|---|---|---|---|---|
| 2026-09-09 (`05_harmonics.npz`) | 1,0024 pu | **5,047 %** | 4,01 / 2,65 / 1,07 % | 1,3440 (clipada) |
| sessão 1 (`05_harmonics_thd-0.05.npz`) | 1,0043 pu | **0,979 %** | 0,02 / 0,06 / 0,06 % | 1,4594 |

Os 0,98 % são ruído de banda larga (quantização), não harmônicos: a senoide
clipada simplesmente não foi aplicada. Controle na mesma sessão: 13 mede
THD 18,9 %, 15 mede 20,9 % (programado 20 %), 20 mede 8,3 % — as classes
waveform funcionam.

**[FATO] Referência de 2026-09-09** (`s1_pulse04.py`), mesmos comandos, PULSe
perfeito:

| classe | programado | medido |
|---|---|---|
| 02 SAG 0,1 pu | 12,7 V | 12,8 V |
| 03 SWELL 1,1 pu | 139,7 V | 138,9 V |
| 04 INTERRUPTION 0,0215 pu | 2,7 V | 4,0 V |

**[INFERÊNCIA]** O caminho nativo (`trigger_step` / `trigger_pulse` /
`configure_harmonics_csine` → `arm()` → `*TRG`) deixou de aplicar os valores
programados entre 09/09 e 16/09. Na sessão 1 o valor "preso" era 127 V, que
coincide com a tensão base da sessão — por isso SAG/SWELL/INTERRUPTION
"sumiram": a fonte pulsou do nível base para o nível base. Na sessão 2 o valor
preso passou a ser 242 V e o pulso apareceu, mas **invertido**.

**[INFERÊNCIA] — e esta é a recomendação mais acionável do relatório:**
`arm_transient()` (caminho LIST) **lê de volta 9 parâmetros** do instrumento e
recusa a captura se algum divergir (`ametek_orm.py:1243-1278`). `arm()`
(caminho nativo) **não lê nada de volta** (`ametek_orm.py:1164-1219`). O caminho
que verifica é exatamente o que funcionou nas duas sessões; o que não verifica é
exatamente o que produziu dados errados em silêncio, por duas sessões, sem um
único erro SCPI. Acrescentar em `arm()` a leitura de `VOLTage:MODE?`,
`VOLTage:TRIGgered?`, `PULSe:WIDTh?`, `SOURce:FUNCtion:SHAPe?` e
`SOURce:FREQuency:MODE?` teria pegado os três casos.

**[ESPECULAÇÃO]** sobre o mecanismo interno (nenhuma evidência decisiva; ver
"o que só a bancada resolve"): (a) escritas de `VOLTage:TRIGgered` sem prefixo
`SOURce:` sendo aceitas na fila de erro mas ignoradas pelo subsistema de
transiente da Rev. 5.53 — o projeto já documenta que `LIST:REPeat` **exige** o
prefixo `SOURce:` (`ametek_orm.py:694-696`), então esse firmware é sensível a
isso; (b) processamento em paralelo de comandos "list and trigger" (cap. 7.7 do
manual, já citado no código) fazendo o `*TRG` usar um valor antigo; (c) troca de
range/limite de tensão na fonte.

### 1.3 Verificação independente dos achados do arquivo 00

**A1** — CORRIGIDO (ver 1.1). Números do 00 confirmados; a interpretação muda.

**A2** — CONFIRMADO com ressalva. **[FATO]** (`s1_resolucao.py`) os ciclos
nominais das classes waveform saem a 1,018–1,039 pu (classe 01 nativa: 1,036),
ou seja o ganho está certo. O "pico 18–22 % acima" aparece **só nas bordas do
evento**: 10 → 1,176; 11 → 1,181; 16 → 1,218; 17 → 1,202, enquanto os ciclos
nominais das mesmas capturas ficam em 1,021–1,039. **[INFERÊNCIA]** é
sobre-sinal (overshoot) na transição de passo do LIST, concentrado nas classes
cujo evento é um afundamento profundo com harmônicos — não um erro de escala de
`LIST:VOLTage`. Classe 13 (swell 1,3 com harmônicos) mede 1,183 contra
`gerar()` = 1,147, ou seja só +3 %: quando a transição é suave o pico bate.

**A3** — CORRIGIDO em dois pontos (ver quadro do resumo).

**A4 / H-REPEAT** — CONFIRMADO integralmente (`s1_trim_simulado.py`), início/fim
do evento em ms **após o trigger medido**:

| classe | nominal `gerar()` | antigo (REPeat=1, janela 200 ms) | novo (REPeat=0) |
|---|---|---|---|
| 10 | 60–120 | 109,2–180,0 (truncado) | **58,3–116,7** |
| 11 | 60–120 | 109,2–180,0 (truncado) | **58,3–116,7** |
| 12 | 60–120 | 113,3–180,0 (truncado) | **66,7–100,0** |
| 13 | 60–120 | 134,2–180,0 (truncado) | **66,7–116,7** |
| 14 | 60–120 | 109,2–180,0 (truncado) | **58,3–100,0** |
| 16 | 60–120 | 134,2–180,0 (truncado) | **66,7–116,7** |

Com `REPeat 0` o evento está no lugar nominal dentro de meio ciclo. Não sobra
atraso nenhum a explicar. **[INFERÊNCIA]** O "2,19x residual" do v1.10 é
artefato: aquela medida tem um piso grande que nunca foi subtraído (ver B2).

**A5** — CONFIRMADO. **[FATO]** classe 18: 63,03 Hz persiste até 755 ms, ≥150 ms
depois do fim da lista. Classes de amplitude: o último passo é a senoide nominal,
então a saída "volta ao normal" por construção. **[FATO]** classe 08 da sessão 1:
`transiente_concluido` = 42,9 V — a forma inteira foi escalada por 0,340
(`limite_pico_bancada_pu`), inclusive a parte nominal, e o último passo persiste
nesse nível.

**A6** — CORRIGIDO (ver 1.1): não há atraso trigger→saída, nem ~20 ms nem
~100 ms.

**B1** — CONFIRMADO (`s1_logs.py`). `transiente_ativo` = `True` em **115/115**
(log1) e **927/928** (log2, 1 `None` na trava). `output` = `1` em 115/115 e
927/928. O campo não discrimina nada.

**B2** — CONFIRMADO e refinado. **[FATO]** sessão 1, Δ(`apos_trigger` →
`transiente_concluido`) por classe: 02/03/04 (pre 0,46 s) = 0,562–0,578 s;
todas as outras (pre 0,40 s) = 0,625–0,671 s. **[FATO]** classe 01 (STEP,
transiente de duração zero) = 0,625 s e classes 06/07 (LIST de 200 ms) =
0,625/0,656 s — a lista não contribui nada. **[INFERÊNCIA]** com `margin on` a
medida está saturada no pós-trigger do osciloscópio (≈ `janela − pre_trigger` +
30 ms) e não tem poder de discriminação. **[INFERÊNCIA]** com `margin off`
(caso do v1.10) o pós-trigger do osciloscópio cai para 0,2 s e a medida passa a
enxergar a lista — mas só a **diferença** (516 → 438 ms) é informativa; o valor
absoluto carrega ≥0,25 s de overhead fixo (bloco de 3 queries de diagnóstico +
polling + `assert_no_errors`), que o v1.10 comparou contra "200 ms nominais"
sem descontar. **[FATO]** custo medido de um bloco `_log_diagnostico`:
`antes_voltage_mode_list` → `apos_voltage_mode_list` = 0,156 s de mediana
(3 queries + 1 write + 1 `check_errors`), ou seja **~39 ms por query** na serial
de 115200.

**B3** — CONFIRMADO. **[FATO]** `antes_voltage_mode_list` mediana 0,063 V
(n=13, log1) e 0,060 V (n=27, log2); `apos_voltage_mode_list` 0,064 / 0,060 V.
`antes_sourcemode_acdc` 126,592 V → `apos_sourcemode_acdc` 0,055 V (n=1).
**[INFERÊNCIA] posso estreitar a hipótese H-ZERO-LIST:** a saída fica em
~0,06 V durante **todos** os ~19,7 s de `program_capture()` — inclusive depois
de `SOURce:VOLTage <base>` ter sido escrito. O código já documenta
(`ametek_orm.py:1222-1224`) que na Rev. 5.53 um `ABORt` "restaurou FUNC/VOLT:MODE
FIX **e OUTPUT OFF**". O `ABORt` da linha 981, primeira instrução de
`program_capture()`, é o candidato dominante. Não há ponto de log para
bissecionar — e bastaria um `_log_diagnostico` entre `ABORt` e `*CLS`.

**B4** — CONFIRMADO e medido melhor. **[FATO]** intervalo entre
`antes_voltage_mode_list` consecutivos na sessão 2 (ciclo completo de uma
captura waveform): **19,64 – 20,42 s**, n=27, mediana 19,73 s. Sessão 1
(12 TRACe a 60 Hz): ~23 s por captura (log1, classe 07: 16:10:05 → 16:10:28).
**[FATO]** zero acertos de cache de TRACe na sessão 2 (nenhuma linha
"reaproveitando"). **[FATO]** 10 `TRACe:DEFine` na sessão 2 (uma vez, ~3 s cada).

**B5** — CONFIRMADO, com as localizações exatas (`s1_logs.py`):

| momento | classe | último ponto de diagnóstico | exceção |
|---|---|---|---|
| 16:14:26 (s1) | 18 | `arm_antes_wai` | `-226 Lists not same length` no `INITiate:IMMediate` |
| 16:20:13 | 03 t1 | `transiente_concluido` | `ParameterOutOfBoundsError` 308 V (antes de qualquer write) |
| 16:20:41 | 03 t2 | `arm_antes_wai` | `-113` no `INITiate:IMMediate` |
| 16:21:24 | 03 t3 | `transiente_concluido` | `ParameterOutOfBoundsError` 308 V |
| 16:22:13 | 05 t1 | `arm_apos_init` | `TimeoutError ... último estado='IDLE'` |
| 16:23:03 | 05 t2 | `arm_apos_init` | idem |
| 16:23:36 | 05 t3 | `arm_antes_wai` | `-113` no `INITiate:IMMediate` |
| 16:33:38 | 08 | `antes_voltage_mode_list` (3 campos `None`) | `CommunicationError` VI_ERROR_TMO |

**[FATO]** `extra={'erros': [...]}` não vazio: **0 linhas em 1043** (115 + 928).
Nenhum `-113` veio dos writes de `trigger_step`/`trigger_pulse`.
**[INFERÊNCIA]** os dois `-113` foram levantados por
`assert_no_errors("comando INITiate:IMMediate")`, que fica entre
`arm_antes_wai` e `arm_apos_init` — a janela contém `*WAI`,
`INITiate:IMMediate` **e as 3 queries do próprio `arm_antes_wai`**. O método de
diagnóstico não separa os três.

**B6** — CONFIRMADO. **[FATO]** `mestre.py:22-27` faz
`logging.basicConfig(..., stream=sys.stdout)` e `cli.py` não adiciona
`FileHandler`; `logs/` está vazio. **[FATO]** as chaves do `metadata/*.jsonl`
são apenas `id_captura, classe, seed, simulado, fs_hz, pontos, parametros,
snr_medido_db, nivel_indice, margem_amostras_antes, margem_amostras_depois,
amostras_totais` — sem f0, tensão base, probe, `pre_trigger_s`, escala vertical,
flags `margin`/`diagnostico`, versão do código ou IDN.

**C** — CONFIRMADO; detalhe em P1.

---

## 2. Viabilidade das três ideias do dono

Pré-requisito comum, **obrigatório para qualquer uma das três**: enquanto
`get_waveform()` descartar `x_origin`, o pipeline não sabe onde está o trigger,
e qualquer margem pequena vira recorte errado. Duas correções possíveis
(`[INFERÊNCIA]`, ambas simples):

- **(A) compensar o comando:** `:TIMebase:POSition {(-pre_trigger + duration/10)}`
  — mantém `REFerence LEFT` e faz a borda esquerda cair exatamente em
  `-pre_trigger`.
- **(B) usar a preamble:** parar de fazer `time_axis -= time_axis[0]`, devolver o
  eixo referenciado ao trigger e gravar `indice_trigger` no metadata. Essa é a
  mais robusta: passa a funcionar mesmo se o firmware mudar a convenção.

### (i) Reduzir a margem "antes" para 20 ms

**Viável, com uma armadilha.** **[FATO]** (`s1_trim_simulado.py`) sem a correção
(A)/(B), pedir 20 ms antes e 20 ms depois dá uma janela de 240 ms, deslocamento
de `REFerence LEFT` de 24 ms, pré-trigger real de 44 ms e pós-trigger real de
196 ms → **o evento de 200 ms é truncado em 4 ms**. Com 20/50 ms (janela de
270 ms) o pós-trigger real é 223 ms e cabe. A tabela completa:

| margem pedida antes/depois | janela | pré-trigger REAL | pós-trigger REAL | resultado |
|---|---|---|---|---|
| 20 / 20 | 240 ms | 44 ms | 196 ms | **trunca 4 ms** |
| 20 / 50 | 270 ms | 47 ms | 223 ms | OK |
| 40 / 20 | 260 ms | 66 ms | 194 ms | **trunca 6 ms** |
| 40 / 50 | 290 ms | 69 ms | 221 ms | OK |
| 60 / 20 | 280 ms | 88 ms | 192 ms | **trunca 8 ms** |
| 60 / 50 | 310 ms | 91 ms | 219 ms | OK |
| 60 / 100 | 360 ms | 96 ms | 264 ms | OK, folgado |

**[FATO]** A margem de 400 ms do v1.10 foi dimensionada contra dois números que
agora sabemos falsos: o "atraso universal de ~20 ms" (é o offset de referência)
e o "pior caso de 540 ms do LIST:REPeat" (A4 mostra que com `REPeat 0` o evento
é nominal). **[INFERÊNCIA]** Não há mais justificativa técnica para 400 ms.
Reduzir também resolve de graça o problema que motivou o v1.10 inteiro (o teto
de ~32,3 k pontos do modo AUTO): com 270–360 ms a folga volta a ser enorme.

**Janela mínima segura por tipo de classe** (medida, não estimada):

| tipo | classes | evento medido, em ms após o trigger | janela mínima | recomendada |
|---|---|---|---|---|
| STEP | 01 | degrau em `t = trigger`; 200 ms de conteúdo | 0 antes / 200 depois | 20 / 250 |
| LIST de amplitude/forma | 06–17, 20 | 58,3 – 116,7 (nominal 60–120), lista de 200 ms | 0 antes / 200 depois | 20 / 250 |
| LIST de frequência | 18 | degrau em 0 ms e em 100 ms; último valor **persiste** | 0 antes / 200 depois | 20 / 250 |
| PULSe nativo | 02, 03, 04 | pulso em 0 – 60 ms; `gerar()` o quer em 60–120 ms | **60 antes** / 140 depois | 60 / 200 |
| CSINe / DC offset | 05 (≤20 % THD), 19 | estado permanente, presente em todo o registro | qualquer 200 ms | 20 / 250 |

**[FATO] Trim simulado** sobre os registros atuais de 1 s: um recorte de
`[trigger−20 ms, trigger+250 ms]` (índices 14400–22500 com o trigger em 15000)
contém o evento inteiro de todas as classes das duas sessões — os eventos
medidos terminam em 116,7 ms após o trigger no pior caso, e a lista inteira em
200 ms. Descarte: **730 de 1000 ms = 73 %** do registro atual. Com 60/200 ms
(classes PULSe) o descarte é 74 %.

**[INFERÊNCIA] O que pode dar errado:** (a) o truncamento de 4–8 ms descrito
acima, se (A)/(B) não for feito antes; (b) `get_waveform()` tem um teste
chumbado em 0,2 s (`oscilloscope_orm.py:389`) que continua válido para janelas
≥200 ms, mas quebra se alguém pedir menos; (c) a margem pequena deixa de cobrir
um evento atrasado — mas, como A4 mostra que com `REPeat 0` não há atraso, esse
risco hoje é teórico. Recomendo **não** ir abaixo de 20 ms antes e 50 ms depois.

### (ii) Zerar a saída após o fim do experimento

**Viável tecnicamente, mas resolve pouco e custa caro. Não recomendo.**

- **[FATO]** hoje a saída **já** fica em ~0,06 V durante os ~19,7 s de
  `program_capture()` de cada classe waveform — ou seja, entre capturas a saída
  já está praticamente zerada, por acidente (`ABORt`), não por projeto.
- **[FATO]** depois do LIST o último passo persiste (A5). Para as classes de
  amplitude o último passo é a senoide nominal, então "zerar depois" só serve
  para marcar o fim; para a classe 18 serviria para sair dos 63 Hz.
- **[FATO]** `SOURce:VOLTage 220` escrito por `recuperar_estado_seguro()` **não**
  mudou a saída em três ocasiões da sessão 2 (log2 613/705/845). **[INFERÊNCIA]**
  não há garantia de que um "zerar depois" por escrita imediata funcione; teria
  de ser um passo de LIST a 0 V, ou `OUTPut:STATe OFF`, que derruba o relé.
- **[INFERÊNCIA] riscos:** (a) para as classes nativas o nível "depois" É a
  linha de base da medida (o PULSe volta ao nível imediato) — zerar destrói o
  pós-evento; (b) acrescenta um ciclo 0→V por captura, exatamente o tipo de
  estresse que é candidato na análise da trava (P3); (c) se o zeramento entrar
  dentro da janela de aquisição, contamina o registro.
- **[INFERÊNCIA] alternativa melhor e barata:** gravar `indice_trigger`,
  `pre_trigger_s`, `duracao_evento_s`, f0 e tensão base no metadata. O fim do
  evento passa a ser conhecido sem mexer em hardware nenhum.

### (iii) Ajustar a margem para capturar um pouco depois do fim

**Viável e recomendado — é o complemento necessário de (i).** **[FATO]** o
conteúdo programado termina em `trigger + 200 ms`; o maior fim de evento medido
é 116,7 ms (os ~83 ms restantes da lista são ciclos nominais). **[INFERÊNCIA]**
20 ms depois é o mínimo para ver o retorno ao regime; 50 ms é confortável e já
absorve o sobre-pico de transição (A2). Mais de 100 ms não acrescenta nada
observável nos dados atuais.

**Proposta consolidada [INFERÊNCIA]:** `margin on` = 20 ms antes + 50 ms depois
(janela de 270 ms, 8100 amostras) para tudo, exceto classes com
`pre_trigger_s > 0`, onde a margem "antes" passa a ser
`pre_trigger_s + 20 ms`; e corrigir `:TIMebase:POSition` ou usar `x_origin`
**antes** de aplicar a redução.

---

## 3. Os três problemas relatados

### P1 — "tentar 3 vezes" e o aborto da bateria

**Leituras possíveis do relato ("se ela acontecer dentro de uma bateria de 5 ×
3 falhas, a bateria é abortada"):**

1. *"numa classe com 5 níveis × N capturas, 3 falhas descartam a classe
   inteira"* — **[FATO] é isto que o código faz** e é o que aconteceu.
2. *"3 falhas numa classe abortam a bateria toda"* — **[FATO] falso**:
   `mestre.py:466-472` registra `FALHOU`, chama `recuperar_estado_seguro()` e
   segue para a classe seguinte. A sessão 2 provou: 03 e 05 falharam 3× e a
   bateria continuou até a 08.
3. *"uma falha de infraestrutura aborta a bateria sem retry"* — **[FATO]
   verdadeiro** (`mestre.py:451-455`) e foi o que matou 08–20 na sessão 2.

**[INFERÊNCIA] A leitura real é a (1) combinada com a (3):** o dono viu uma
sessão que perdeu 03 e 05 por completo e depois morreu na 08. O que "não
deveria acontecer" é a **perda total dos dados bons**.

**Todos os caminhos que abortam ou perdem dados** (leitura de `mestre.py` e
`cli.py`):

| # | caminho | efeito | evidência |
|---|---|---|---|
| 1 | `executar()` só chama `_salvar_classe()` **depois** do laço completo (`mestre.py:1044`) | uma falha na captura *k* joga fora as *k−1* boas, que só existiam em memória | **[FATO]** classe 08 da sessão 2: 7 capturas boas, **nenhum** `.npz` e **nenhum** `metadata/08_*.jsonl` no disco |
| 2 | 3 tentativas esgotadas | classe fica com zero arquivos | **[FATO]** 03 e 05 da sessão 2: 0 `.npz`, apesar de 52 e 29 capturas fisicamente executadas |
| 3 | `CommunicationError` / `FalhaFatalDeInstrumento` | aborta a bateria inteira, sem retry, e perde a classe em curso | **[FATO]** log2 16:33:38 |
| 4 | erro **determinístico** é retentado igual a um intermitente | 3× o mesmo erro garantido, 3× o desgaste | **[FATO]** classe 03: 20 + 12 + 20 = 52 capturas físicas para terminar com 0 arquivos; `ParameterOutOfBoundsError` é subclasse de `ValueError`, nunca de `CommunicationError` |
| 5 | `recuperar_estado_seguro()` pode levantar `FalhaFatalDeInstrumento` (`mestre.py:557-560, 579-583`) | derruba a bateria por um passo de recuperação, mesmo que a classe fosse recuperável | não ocorreu nas duas sessões |
| 6 | limpeza de órfãos em `_salvar_classe` apaga `{id}_{nome}_*.npz` que **esta** rodada não escreveu | rodar a mesma classe com menos capturas apaga os arquivos da rodada anterior | **[FATO]** documentado na própria docstring (`mestre.py:753-770`) |
| 7 | `cli.py` cria **uma** pasta de sessão por processo (`_garantir_pasta_sessao`) | `run 01` antes de `set diagnostico on` e o `run all` seguinte escrevem na mesma pasta, com configurações diferentes, e o segundo sobrescreve | **[FATO]** log1 linhas 89-110: `run 01` com `margin on`/`diagnostico off` gravou em `sessao_2026-09-16_16-07-44` e foi sobrescrito pelo `run all` |

**[INFERÊNCIA] Defeito adicional descoberto aqui:** a **classe 03 nunca pode
terminar a 220 V**. Os níveis são `(1.1, 1.2, 1.4, 1.6, 1.8)` e
`max_voltage_rms = 300`; `1.4 × 220 = 308 > 300`. A falha é estrutural e
determinística, e o código só a descobre depois de 20 capturas físicas, três
vezes. O mesmo vale para qualquer classe cujo nível máximo × tensão base passe
do limite. Uma validação de "todos os níveis cabem no limite" antes da primeira
captura resolveria.

### P2 — Por que as classes waveform "demoram a acontecer"

**[FATO] A resposta está parcialmente documentada**, em código e não em
CHANGELOG/README: o comentário de `program_capture()`
(`ametek_orm.py:1070-1074`) explica o `time.sleep(1.0)` por TRACe, e
`_ensure_trace_slots()` (`ametek_orm.py:920-930`) explica os ~3 s de
`TRACe:DEFine`. O README só menciona o custo agregado em um lugar
(linha 256: "reprograma ~12 TRACe na Flash (~40-50s)", na descrição de
`lowvoltage`). **Não achei nenhum texto que diga quanto custa UMA captura
waveform** — é isso que falta documentar.

**[FATO] Números medidos** (`s1_logs.py`, gaps entre `antes_voltage_mode_list`
consecutivos): **19,64 – 20,42 s por captura** na sessão 2 (10 TRACe a 50 Hz),
mediana 19,73 s; **~23 s** na sessão 1 (12 TRACe a 60 Hz).

**[INFERÊNCIA] Decomposição** (as duas parcelas são quase iguais):
- transferência: `TRACe:DATA <nome>,<1024 valores em ASCII>`; com `%.8g` cada
  valor ocupa ~11 bytes → ~11,3 kB por TRACe; a 115200 baud (≈11,5 kB/s) dá
  **~0,98 s**;
- espera fixa: `time.sleep(1.0)` depois de cada `TRACe:DATA`
  (`ametek_orm.py:1073`) → **1,00 s**;
- total ≈ 2,0 s × 10 TRACe = 20 s, que é exatamente o medido. Mais `*CLS` e
  os comandos de lista.

**[FATO]** O cache de TRACe (v1.7) exige bytes idênticos; com `set capturas N`
os parâmetros mudam a cada captura e o cache **nunca** acerta: zero linhas
"reaproveitando" em toda a sessão 2.

**[INFERÊNCIA] Onde está o ganho, se algum dia interessar:** formato binário em
vez de ASCII (`TRACe:DATA` aceita bloco definido em muitos firmwares — verificar
no manual), reduzir `%.8g` para `%.5g` (~40 % menos bytes), e trocar o
`time.sleep(1.0)` cego por uma confirmação (`*OPC?` não funciona nesta Rev.,
mas `TRACe:CATalog?` ou uma releitura funcionaria).

### P3 — A trava da fonte no experimento 08 da sessão 2

**Fatos, na ordem** (log2 linhas 1341-1351):

- **[FATO]** 16:33:01 — captura 7/10 da classe 08 concluída normalmente
  (`transiente_concluido`, 219,19 V, `t = 10765,140`).
- **[FATO]** A captura 8 começa e roda `program_capture()` até o ponto
  `antes_voltage_mode_list` **no tempo normal**: `t = 10782,343`, ou seja
  **+17,20 s** — idêntico às 26 capturas anteriores. Logo, os 10 `TRACe:DATA`
  da captura 8 foram todos aceitos.
- **[FATO]** As 3 queries desse ponto de diagnóstico retornaram `None`
  (`transiente_ativo=None output=None tensao_v=None`) — 3 × 5 s de timeout VISA,
  linha impressa às 16:33:33.
- **[FATO]** O `check_errors()` logo depois de `VOLTage:MODE LIST` estourou às
  16:33:38 com `VI_ERROR_TMO`; `safe_shutdown()` também não confirmou
  (`OUTPut:STATe?` em timeout).
- **[FATO]** **O último comando cuja fila de erro foi lida com sucesso é
  `FUNCtion:MODE LIST`** — o comando imediatamente anterior ao ponto de
  diagnóstico, dentro do laço de `ametek_orm.py:1118-1151`.
- **[FATO]** O dono relata que a fonte não respondia **nem pelo painel frontal**
  e teve de ser desligada na chave.
- **[FATO] Contexto quantitativo:** 27 capturas waveform concluídas nessa
  conexão (06: 10, 07: 10, 08: 7) × 10 TRACe = **270 `TRACe:DATA`**, mais 10
  `TRACe:DEFine`, mais os 10 da captura 8 = **280 `TRACe:DATA`**. Sessão 1: 13
  classes waveform × 1 captura × 12 = **156**. É o maior volume que uma única
  conexão já teve.
- **[FATO] O que mudou no 08 em relação ao 06/07:** tensão 220 V (vs 127 V da
  sessão 1), 50 Hz, e `limite_pico_bancada_pu()` = `0,9 × 415,8 / (220·√2)` =
  **1,203 pu** — ou seja, a 220 V a classe 08 tem o transiente reduzido a
  +0,20 pu e as 10 capturas de `set capturas 10` ficam em
  `linspace(1,200; 1,203; 10)`, praticamente idênticas entre si (mas com bytes
  diferentes, o que anula o cache e força 10 gravações novas por captura).
- **[FATO]** Na sessão 1 a mesma classe 08 rodou 1 captura sem problema.

**Hipóteses ordenadas:**

| # | hipótese | a favor | contra | como testar **sem risco** |
|---|---|---|---|---|
| 1 | **Travamento do controlador da fonte (firmware), disparado na transição `FUNCtion:MODE LIST` com catálogo cheio e carga máxima de escritas** | o painel frontal morreu junto — só um travamento do controlador explica isso; é exatamente o comando seguinte ao último confirmado; a Rev. 5.53 já é documentada no projeto por processar comandos de list/trigger "em paralelo" | não reproduzido; a sessão 1 fez a mesma transição 13 vezes | ler `SYSTem:ERRor?` e `*ESR?` logo depois de religar (fila pode sobreviver); repetir só 06/07/08 com `set capturas 3` a 127 V e depois a 220 V, com log em arquivo, parando ao primeiro timeout |
| 2 | **Desgaste/saturação de escrita da Flash** (280 `TRACe:DATA` numa conexão contra 156 na sessão 1 e ~156 no v1.7) | a trava ocorreu no maior volume já atingido; escala monotônica com o histórico | **[FATO] contra:** os 10 `TRACe:DATA` da captura 8 passaram no tempo normal — a trava veio **depois** deles; e não se sabe se `TRACe:DATA` (ao contrário de `TRACe:DEFine`) grava em Flash | confirmar no manual se `TRACe:DATA` grava em não-volátil (tarefa do subagente 2); depois, rodar 300 `TRACe:DATA` sobre 1 nome só, com a saída **desligada**, contando falhas |
| 3 | **Estresse térmico/elétrico** — 16 min de saída ligada a 220 V/50 Hz, 27 transições 0 V → 220 V (a saída cai a 0,06 V durante cada 19,7 s de programação) e picos de 374 Vp da classe 08 | é a sessão de maior potência já feita; a sessão 1 rodou a 127 V | a fonte não sinalizou proteção antes de morrer; nenhum erro na fila até o fim | repetir a sessão 2 **sem** as classes waveform (só nativas) por 20 min a 220 V e ver se sobrevive; monitorar temperatura pelo painel |
| 4 | **Interação entre a saída ligada e a gravação de TRACe** — `clear_all_traces()` recusa rodar com OUTPUT ligado (`ametek_orm.py:892-893`), mas `TRACe:DATA` é enviada com a saída **ligada** o tempo todo | o próprio projeto já reconhece que operações de Flash e saída ligada não combinam | `TRACe:DEFine` também roda com a saída ligada e nunca travou | rodar uma bateria waveform com `AMETEK_CLEAR_USER_WAVEFORMS=1` e a saída desligada entre classes |
| 5 | **Problema de serial/USB (VCP) no PC** | o sintoma inicial é `VI_ERROR_TMO` | **[FATO] refutado pelo relato:** o painel frontal também estava morto; um problema de VCP não afeta o painel | — |

**[INFERÊNCIA]** A hipótese 1 é a única compatível com **todos** os fatos,
principalmente com o painel morto. As 2 e 3 são candidatas a **gatilho** da 1,
não a causa isolada. **[ESPECULAÇÃO]** A combinação "catálogo de 10 TRACe
totalmente reescrito 28 vezes + transição para `FUNCtion:MODE LIST` com a saída
entregando 220 V" é o cenário mais estreito que reúne as três.

**[INFERÊNCIA] Mitigação independente da causa:** salvar cada captura
incrementalmente (ver P1 #1). Na sessão 2, sete capturas boas de 08 foram
perdidas por um travamento que não tinha nada a ver com elas.

---

## 4. Outros achados relevantes (não listados no arquivo 00)

1. **[FATO] A sessão 2 inteira, nas classes nativas, está a 127 V e não a
   220 V.** Os `.npz` de 01, 02 e 04 estão em pu de 220 V (`tensao_pu = V /
   (220·√2)`), então valem 0,58 pu onde deveriam valer 1,0 pu. Os 70 arquivos
   dessas três classes **não servem para dataset** sem reprocessamento — e
   mesmo reprocessados, 02 não tem distúrbio e 04 tem o distúrbio invertido.
2. **[FATO] Classe 04 da sessão 2: interrupção virou elevação.** 60 ms a
   242,1 Vrms (1,1 pu da classe 03) começando em 560,00 ms, nas 10 capturas, com
   `interruption_pu` de 0,0 a 0,09 no metadata. É um rótulo **ativamente errado**
   no dataset, pior que um dado faltando.
3. **[FATO] Classe 05 da sessão 1 não tem harmônico nenhum** (THD 0,98 %
   contra 5,05 % em 09/09). O arquivo `05_harmonics_thd-0.05.npz` está rotulado
   como 5 % de THD.
4. **[FATO] Classe 03 é impossível a 220 V**: `1.4 × 220 = 308 > 300` — ver P1.
   A 127 V o teto (300/127 = 2,36 pu) não incomoda; a 220 V ele corta o nível 1,4.
5. **[FATO] Classe 08 a 220 V perde o sentido**: `limite_pico_bancada_pu()` =
   1,203 pu, então o "transiente impulsivo de 5–10 pu" vira +0,20 pu. Com
   `set capturas 10` as 10 capturas ficam em `linspace(1,200; 1,203; 10)` —
   variação de 0,3 % entre a primeira e a décima, com 10 reescritas de TRACe cada.
6. **[FATO] Classe 19 (DC_OFFSET) é inmensurável na escala usada.** Classes
   nativas nunca chamam `set_vertical_scale` (só quem define `scope_scale_v()`),
   então 19 herda a escala da classe 17 (~89,6 V/div ⇒ ~2,8 V/LSB ⇒ 0,0156 pu).
   O offset programado é 0,0311 pu = **2 LSB**. O offset medido ciclo a ciclo
   varia 0,048 → 0,085 → 0,048 pu, ou seja 1,5 a 2,7× o programado e com deriva
   lenta. **[INFERÊNCIA]** não dá para dizer se a fonte errou; a medida não tem
   resolução nem estabilidade para isso.
7. **[FATO] Sobre-pico nas transições do LIST**: ciclos nominais a 1,018–1,039 pu
   mas 1,176/1,181/1,218/1,202 pu nas bordas dos eventos de 10/11/16/17. As
   capturas têm um artefato que o `gerar()` não tem.
8. **[FATO] `analisar_sessao.py` está chumbado para a sessão 1**: `60.0` na
   chamada de `gerar()` (linha 138) e `base_voltage_rms: float = 127.0`
   (linha 67). Aplicado à sessão 2 (50 Hz / 220 V) produz comparações sem
   sentido. **[INFERÊNCIA]** além disso ele desconhece H-REF10, então sua coluna
   de "lag" tem um viés fixo de `janela/10`.
9. **[FATO] Nada do contexto da sessão é gravado** (ver B6). Não há como, a
   partir de `resultados/`, saber que a sessão 2 foi 220 V/50 Hz, com
   `capturas 10`, `margin on`, `diagnostico on`, probe 500× — tudo isso só existe
   no console, que também não é salvo.
10. **[FATO] `run 01` e `run all` compartilham a pasta de sessão** e o segundo
    sobrescreve o primeiro silenciosamente, mesmo com flags diferentes (log1,
    linhas 89-110).
11. **[FATO] `_log_diagnostico` custa ~39 ms por query** (3 queries = ~120 ms) e
    é chamado 5× por captura; na sessão 2 foram 928 pontos = **~1,9 min** só de
    diagnóstico. Não é problema, mas explica parte do custo por captura nativa
    (~2,1 s).
12. **[FATO] `arm()` não valida nada e `arm_transient()` valida 9 parâmetros** —
    a assimetria que deixou H-NATIVO passar em silêncio (ver 1.2).
13. **[FATO] Bug C do v1.10 (`OscChannel.display` getter com `KeyError`)**
    continua no código (`oscilloscope_orm.py`, propriedade com
    `values={True:"1",False:"0"}` e resposta parseada como float).
14. **[FATO] `get_waveform()` reamostra por `np.interp` de ~32,5 kSa/s para
    30 kSa/s exatos.** Isso destrói a quantização original (os `.npz` têm
    15 000–18 800 níveis distintos em 30 000 amostras, onde 8 bits dariam ≤256) e
    introduz interpolação linear em eventos rápidos — notches de 100 µs e o
    impulso de 50 µs da classe 08 são justamente os mais afetados.
    **[INFERÊNCIA]** para essas classes vale guardar também o bruto.

---

## 5. O que só a bancada resolve, e o teste mínimo

Tudo o que estava listado como "só a bancada separa" no arquivo 00 (o teste 2×2
de `margin` × `diagnostico`) **não é mais necessário**: H-DIAG e H-MARGIN estão
refutadas offline. O que sobra é:

### T1 (prioridade máxima) — confirmar H-NATIVO e achar o comando culpado
**Custo: ~2 minutos, saída em 5 Vrms, sem EUT.** Com a saída **desligada** ou em
5 V, a partir de uma conexão nova:
```
SOURce:VOLTage:RANGe?        -> anotar
VOLTage:MODE?                -> anotar
VOLTage:TRIGgered?           -> anotar (valor "preso" herdado)
VOLTage:MODE STEP
VOLTage:TRIGgered 5
VOLTage:TRIGgered?           -> (a) devolve 5?  (b) devolve o valor antigo?
SOURce:VOLTage:TRIGgered 5   -- com prefixo
SOURce:VOLTage:TRIGgered?    -> compara
SYSTem:ERRor?                -> confirma fila vazia nos dois casos
```
Se (b), H-NATIVO está fechada e a causa é a escrita ser ignorada; se o prefixo
`SOURce:` fizer diferença, a correção é de uma linha em `trigger_step`/
`trigger_pulse`. Repetir a mesma sequência para `PULSe:WIDTh` e
`SOURce:FUNCtion:SHAPe`.

### T2 — confirmar H-REF10 no instrumento
**Custo: ~1 minuto, só osciloscópio, sem fonte.** Depois de
`configure_acquisition(..., duration_s=1.0, pre_trigger_s=0.40)` e um
`:TRIGger:FORCe`, ler `:WAVeform:PREamble?` e imprimir `x_origin`. H-REF10 prevê
`x_origin = −0,500 s`. Se prever, a correção é (A) ou (B) da seção 2.

### T3 — separar o -113 (H-113)
**Custo: ~5 minutos.** Rodar a classe 05 ou 03 com `diagnostico on` e um ponto
de log **entre** `*WAI` e `INITiate:IMMediate` (uma linha em `arm()`), mais
`SYSTem:ERRor?` imediatamente antes do `*WAI`. Isso reduz a janela de três
comandos para um.

### T4 — fechar H-ZERO-LIST
**Custo: ~1 minuto.** Um `_log_diagnostico("apos_abort")` entre o `ABORt` e o
`*CLS` de `program_capture()` (`ametek_orm.py:981-986`) decide se é o `ABORt`
que derruba a saída.

### T5 — investigar a trava (P3) com risco mínimo
Ordem sugerida: religar a fonte, ler `SYSTem:ERRor?` / `*ESR?` / contador de
horas do painel **antes** de qualquer outro comando; depois repetir apenas
06/07/08 com `set capturas 3` a **127 V**, com log em arquivo, e só então repetir
a 220 V. Parar ao primeiro timeout. Não repetir a bateria completa a 220 V até
T1 estar resolvido — metade das classes daquela sessão produz dado errado de
qualquer forma.

---

## 6. Recomendações, por retorno sobre esforço

1. **Ler de volta o que se escreve no caminho nativo** (`arm()` validando
   `VOLTage:MODE?`, `VOLTage:TRIGgered?`, `PULSe:WIDTh?`, `FUNCtion:SHAPe?`),
   como `arm_transient()` já faz. Teria evitado duas sessões inteiras de dado
   errado.
2. **Parar de descartar `x_origin`** em `get_waveform()` e gravar
   `indice_trigger` no metadata. Resolve A1, o recorte, o `analisar_sessao.py` e
   viabiliza as ideias (i) e (iii).
3. **Salvar cada captura assim que ela sai** (hoje `_salvar_classe` só roda no
   fim). Recuperaria as 7 capturas de 08 e as 52 de 03.
4. **Não retentar erro determinístico** (`ParameterOutOfBoundsError`,
   `ValueError`) e validar antecipadamente que todos os níveis da classe cabem
   em `max_voltage_rms`.
5. **Gravar o log em arquivo dentro da pasta da sessão** e gravar f0, tensão
   base, probe, flags, versão e IDN no metadata.
6. **Reduzir `margin` para 20 ms antes / 50 ms depois** — só depois do item 2.
