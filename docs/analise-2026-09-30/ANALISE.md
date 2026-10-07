# Análise da bancada — 2026-09-30 (v1.11, `run all`)

Documento vivo: atualizado conforme a investigação avança. Sessões analisadas
em `resultados/sessao_2026-09-30_14-05-56*` (run01–run04; o `run all` é o
**run04**, 14:11:41–14:18:11, código `b569cdb`, 127 V / 60 Hz, probe 500:1,
`diagnostico on`).

Restrição do dono (2026-09-30): qualquer teste ou correção **não pode
ultrapassar a tensão de saída máxima da fonte** (`max_voltage_rms`/
`max_peak_v` em `ametek_orm.py`, manual §4.14 p. 84: 300 Vrms no range de
300 V). Nenhum limite físico do AGENTS.md foi mexido.

## Resumo do run04

| Classe | Caminho | Resultado | Causa |
|---|---|---|---|
| 01 | nativo STEP | ok na 2ª tentativa | 1ª: `VOLTage:MODE?`=FIX (achado N1) |
| 02, 03 | nativo PULSe | 3/3 descartadas | `PULSe:WIDTh?`=0.0167, pedido 0.06 (achado N2) |
| 04 | nativo PULSe | 3/3 descartadas | N2 + `VOLTage:TRIGgered?` 2.7 contra 2.73671 (achado N3) |
| 05 | nativo CSINe | reprovada na validação | 1ª tentativa N1; 2ª: falso negativo V1 (a THD de 5,03% está certa) |
| 06–15, 17, 20 | waveform | reprovadas na validação | falso negativo V1 (+ V2 na THD, V3 na crista) |
| 16 | waveform | ok | — |
| 18 | nativo LIST de frequência | reprovada na validação | falso negativo V2 (THD) |
| 19 | nativo STEP + ACDC | 3/3 descartadas | N1, determinístico |

## Achados da validação física (P05) — falsos negativos

### V1 — margem de 20 ms ANTES do trigger está em 0 V (esperado, confirmado pelo dono)
Em todas as capturas reprovadas, só os 2 primeiros meios-ciclos (amostras
0–600 = `margem_amostras_antes`) têm envelope ~0,01 pu; o sinal começa na
amostra ~600. A saída fica em 0 V antes do transiente **por projeto**.
`comparar_fisicamente()` comparava o registro inteiro (8100 amostras) com a
forma esperada (6000 amostras, sem margem) → mínimo do envelope 0,01 pu em
toda captura.

### V2 — os 50 ms DEPOIS quebram a THD
Com o registro cortado só na frente (7500 amostras), a THD da 18 dava 2,17%
contra 0,16% esperados; na janela alinhada de 6000 amostras dá 0,28%. O
mesmo vale para 20 (1,58% → 0,29%, esp. 0,00%), 13 (5,79% → 7,11%,
esp. 7,11%), 10 (3,11% → 4,03%, esp. 4,02%).

**Correção aplicada (V1+V2):** `_validar_fisicamente()` compara só
`medido[margem_antes : margem_antes + len(esperado)]`. Teste
`test_classe_valida_so_a_janela_alinhada_ignorando_margem_em_zero` falha com
o código antigo (mesmos motivos do run04) e passa com o novo.

### V3 — fator de crista do "ciclo mediano" é instável em classes impulsivas
Na janela alinhada: 08 = 1,567, 09 = 1,623, 17 = 1,712 (esperado 1,414,
tolerância de 10%). A função escolhe o meio ciclo cujo rms está mais perto da
mediana — em 09/17 é justamente o ciclo com a oscilação (rms quase igual,
pico bem maior). Mediana da crista de TODOS os ciclos: 09 = 1,433,
17 = 1,440; CSINe da 05 continua detectada (1,344 contra ~1,45 da senoide
limpa medida). **Correção aplicada** (`sinais.fator_de_crista_do_ciclo_mediano`
agora é a mediana por ciclo; testes `test_oscilacao_curta_nao_distorce_o_fator_de_crista`
— falha no código antigo com 1,85 — e `test_senoide_clipada_em_todos_os_ciclos_muda_o_fator_de_crista`).

Recalculado no run04 (janela alinhada + crista nova), todas dentro da
tolerância **exceto a 08**: crista 1,556 contra limite 1,5556 (ver V4).

### V4 — classe 08: base com resolução ruim e pico no teto da fonte
- Escala vertical 156 V/div (1248 V de fundo, ~4,9 V por código do ADC de 8
  bits), dimensionada para o pico do transiente; a base (escalada por 0,340 →
  0,24 pu, ~61 V de pico) fica com ±1 código de ruído, que infla a crista de
  todos os ciclos (1,49–1,57). Não é defeito da fonte; tolerância **não** foi
  afrouxada — a 08 continua marcada até se decidir o que fazer (ex.: não
  escalar a base, só o impulso).
- **Atenção (restrição do dono):** o pico MEDIDO foi **415,3 V**, com
  `max_peak_v` = 415,8 V (`SOURce:VOLTage:HIGH`). O programado era 2,084 pu ×
  179,6 V ≈ 374 V — a fonte teve ~11% de overshoot no pulso de 2 amostras.
  O limite de comissionamento de 2,084 pu da classe 08 não prevê esse
  overshoot. Proposta a discutir: dimensionar o limite pelo pico MEDIDO, não
  pelo programado.

## Achado de metadata

### M1 — `indice_trigger` gravado na unidade do registro BRUTO do osciloscópio
`oscilloscope_orm.get_waveform()` faz `indice_trigger = -x_origin/x_increment`
com o `x_increment` bruto (~8,57 µs, ~116,7 kSa/s) → 2333. O array devolvido
é reamostrado a 30 kSa/s, onde o trigger está na amostra 600 (confirmado nos
dados: o sinal começa exatamente ali). O trigger está fisicamente certo (P07
funcionou; nenhum aviso de fallback LEFT no log), só o número está na unidade
errada. `analisar_sessao.py` corta por esse número → desalinha 1733 amostras
(57,8 ms). **Metadata das sessões de 2026-09-30 (código `b569cdb`):** usar
`margem_amostras_antes` (600) em vez de `indice_trigger`. **Correção
aplicada:** `indice_trigger = round(-x_origin × 30000)` (grade devolvida);
teste `test_indice_do_trigger_e_na_grade_de_30ksa_devolvida_nao_na_bruta`
(falhava com 2333).

## Achados do caminho nativo (erros REAIS da fonte)

### N2 — `PULSe:WIDTh 0.06` lido como 0.0167 (02/03/04, 9 de 9 tentativas)
Manual §4.21 p. 104–105: `PULSe:WIDTh`, `PULSe:PERiod` e `PULSe:DCYCle` são
acoplados (Tabelas 4-1/4-2, `PULSe:HOLD`). O código nunca programa
`PULSe:PERiod`/`COUNt`/`HOLD`; o exemplo do manual (§6.4.2 p. 152) programa
WIDTh **e** PERiod. 0,0167 s = exatamente 1 ciclo a 60 Hz. Não coberto pela
análise de 2026-09-21. **Hipótese:** o período/duty residual no instrumento
limita a largura. **Status:** consulta ao manual + teste com OUTPUT OFF.

### N1 — rajada de writes ignorada logo após comando "pesado"
`FUNCtion:MODE FIXed; SOURce:FREQuency:MODE FIXed; VOLTage:MODE STEP;
VOLTage:TRIGgered X` (4 writes em <2 ms), `SYSTem:ERRor?` vazio, mas
`VOLTage:MODE?` = FIX:
- 19 (3/3): logo após `SOURce:MODE ACDC; *WAI; SOURce:VOLTage:OFFSet 5.58`;
- 05 (tentativa 1): logo após troca para CSINe (`VOLTage:TRIGgered?`
  também ficou no valor da classe 04, 2,7 — nada pegou);
- 01 (tentativa 1): ~0,6 s após `OUTPut:STATe ON`.
A mesma rajada funciona logo após o `recuperar_estado_seguro` (ABORt/*CLS/…).
`*OPC?` não responde nesta Rev. 5.53 (v1.7). Não dá para separar "comando
descartado" de "algo reverteu depois" sem teste. **Status:** teste com OUTPUT
OFF (leitura de volta após cada write).

### N3 — `VOLTage:TRIGgered` tem resolução de 0,1 V
2,7367107 → lido 2,7 (127.0, 12.7, 139.7 também com 1 casa). A tolerância
relativa de 0,5% reprova valores < ~10 V. **Correção proposta:** escrever o
valor já arredondado à resolução do instrumento (o valor gravado no metadata
passa a ser o realmente aplicado), sem afrouxar a comparação.

### O que o manual diz (consulta de 2026-09-30, manual SCPI P/N 7003-961 Rev AB)
- **PULSe (p. 104–105, Tab. 4-1):** *RST: COUNt 1, HOLD WIDTh, DCYCle 50%,
  PERiod 1 s, WIDTh 0,5 s. Com HOLD=WIDTh, setar WIDTh ≥ PERiod faz o
  PERiod crescer — pelo manual, 0,06 deveria pegar. O 0,0167 lido **não é
  explicado pelo manual** → comportamento da Rev. 5.53 ou estado residual de
  PERiod/DCYCle/HOLD. Sequência prescrita (p. 152): COUNt, PERiod, DCYCle/
  WIDTh. A query está impressa como `[SOURce:]PERiod?` (provável erro de
  digitação).
- **\*WAI (p. 142): "*WAI can be aborted by sending any other command after
  the *WAI command."** O código manda `*WAI` e em seguida outros comandos
  (`SOURce:MODE ACDC; *WAI; OFFSet …`, CSINe idem) — o `*WAI` é anulado pelo
  próximo comando. Comandos de tensão/estado/relés/trigger são processados
  em paralelo (p. 142, p. 173). **Explica o N1** sem precisar de "descarte
  de bytes": a rajada chega com a troca AC/ACDC ou de forma ainda em curso.
- **\*OPC (p. 136):** "*OPC 1 must be part of the same message" do comando
  monitorado; bit 0 do `*ESR?` (p. 169). Diferente do `*OPC?` que não
  respondeu na v1.7 — **nunca testado assim** nesta bancada.
- "You can not mix STEP, PULSe, and LIST modes among functions" (p. 151).
- Único reset de modos documentado: *RST/Device Clear → FIXed (p. 150).
  `SOURce:MODE` zera a saída e exige reprogramar a tensão (p. 98).
- Resolução de VOLTage:TRIGgered: **o manual SCPI não cobre** (fica no
  User Manual 7003-960, ausente). Pico máximo: 425 V / 300 Vrms senoidal no
  range 300 V (p. 84).
- Nenhum bit de "troca de modo concluída" (STATus:OPERation só tem CAL/TRANS/
  MEAS); o meio documentado é ler de volta / `*ESR?` após cada comando.

### Teste de bancada preparado — `scripts/diag_nativo_output_off.py`
Roda com **OUTPUT OFF** (confirmado por leitura no início, entre testes e no
fim; aborta com `safe_shutdown` se aparecer ligado), nunca manda OUTPut ON,
recusa qualquer tensão > 5 V. Validado no simulador do ORM.
- T0: estado atual de PULSe (WIDTh/PERiod/DCYCle/HOLD/COUNt), modos, fila.
- T1: 5 sequências de PULSe (só WIDTh; COUNt+PERiod+WIDTh; WIDTh<PERiod;
  WIDTh>PERiod; ordem do exemplo do manual).
- T2: resolução de VOLTage:TRIGgered (2,7367107; 2,75; 2,74; 2,76; 4,96; 4,999).
- T3: prelúdio {nenhum, ACDC+OFFSet, CSINe} × rajada {4 writes, 2 writes sem
  FUNC/FREQ, cada write confirmado por query} × 3 repetições, lendo o estado
  logo depois e 1 s depois (descartado vs. revertido); mais ACDC e CSINe
  sincronizados por `;*OPC` + polling do `*ESR?` (mede a duração da troca).
Com saída desligada a troca de modo pode ser mais rápida que com carga; se
o N1 não reproduzir, repetir a 5 V com confirmação digitada do operador.

### Resultado do teste de bancada (14:35, `logs/diag_nativo-2026-09-30_14-35-30*`)
OUTPUT OFF confirmado por leitura do início ao fim.

**T0:** estado residual `PULSe:WIDTh` 0,0167 / `PERiod` 0,0334 / `DCYCle`
50 / `HOLD` WIDT / `COUNt` 1. `PERiod?` (forma impressa no manual) → `-113`;
a query certa é `PULSe:PERiod?`.

**T1 (N2):**

| Caso | Writes em rajada | WIDTh lido | Conclusão |
|---|---|---|---|
| a) MODE PULS; TRIG 5; WIDT 0.06 | 3 | 0.0167 | 3º write perdido |
| b) COUN 1; PER 0.2; WIDT 0.06 | 3 | 0.0167 (PER 0.2001) | 3º write perdido |
| c) WIDT 0.1 | 1 | 0.1001 | ok |
| d) WIDT 0.3 (> PER 0.2) | 1 | 0.3001, PER→0.3010 | ok, acoplamento conforme manual |
| e) PER 1; WIDT 0.06; PER 0.2 | 3 | 0.0600, **PER 1.000** | 3º write perdido |

→ **N2 não é acoplamento**: é o mesmo mecanismo do N1 (write perdido em
rajada). O acoplamento WIDTh/PERiod se comporta como o manual (caso d).

**T2 (N3):** 2,7367→2,7; 2,75→2,7; 2,74→2,7; 2,76→2,7; 4,96→4,9;
4,999→4,9 → a Rev. 5.53 **TRUNCA** `VOLTage:TRIGgered` a 0,1 V.

**T3 (N1)** — STEP e TRIG=5 lidos de volta (imediato = após 1 s em todos os
casos → nada é "revertido depois"; o comando simplesmente não chega):

| Prelúdio | Rajada 4 writes | Rajada 2 writes | Cada write confirmado por query |
|---|---|---|---|
| nenhum | **0/3** | 3/3 | **3/3** |
| ACDC + OFFSet | 1/3 | 1/3 (um `-113`) | **3/3** |
| CSINe | 0/3 | 1/3 | **3/3** |
| ACDC com `;*OPC`/`*ESR?` | 1/3 | — | — |
| CSINe com `;*OPC`/`*ESR?` | 2/3 | — | — |

`*OPC` na mesma mensagem **funciona** nesta Rev. 5.53 (bit OPC em 31–47 ms,
1 leitura) — mas sincronizar só o comando pesado não resolve: a rajada
seguinte continua perdendo writes. O `-113` apareceu na rajada de 5 writes
`MODE ACDC; *WAI; OFFSet 1; VOLTage:MODE STEP; VOLTage:TRIGgered 5` (bytes
colados). O dono confirma: "-113 undefined header geralmente já deu, é coisa
de enviar comandos muito rapidamente".

### Causa raiz (N1 + N2): writes em rajada sem controle de fluxo
A USB virtual serial está em `VI_ASRL_FLOW_NONE`; `write()` retornava assim
que os bytes saíam do host. Com 2+ comandos pendentes a fonte perde comandos
em silêncio (ou cola bytes → `-113`). Só a variante "cada write seguido de
uma query" foi 9/9. O caminho LIST sempre funcionou porque `program_capture`
confere `SYSTem:ERRor?`/`:POINts?` depois de quase cada write.

Rajadas encontradas na transcrição do run04 (writes sem query no meio):
- 42× `recuperar_estado_seguro`: `ABORt; *CLS; FUNC FIX; VOLT:MODE FIX;
  FREQ:MODE FIX; AMPLitude 127` (6) — **estado seguro não confirmado**;
- 13× `program_capture`: `SOURce:MODE AC; FREQ 60; FREQ:MODE FIX;
  SHAPe SINusoid; SOURce:VOLTage 127` (5) — o `SOURce:VOLTage` base é o 5º;
- 9× `trigger_pulse` (5), 7× `trigger_step` (4), 2× CSINe (6), 1× classe 18 (11);
- `*WAI` sempre seguido de outro comando (anula o `*WAI`, manual p. 142).

**Hipótese derivada — REFUTADA pela rodada de 14:44 (ver abaixo): com o
sincronismo, as classes waveform continuam em 0 V antes do trigger, então o
`SOURce:VOLTage` não se perdia; 0 V é o comportamento real (como o dono
disse).** Texto original: os ~20 ms em 0 V antes do
trigger nas classes waveform podem ser o `SOURce:VOLTage 127` perdido nessa
rajada de 5 — `program_capture` escreve explicitamente a tensão base antes
da lista, e o próprio código registrava "a captura real de classes
TRACe/LIST começa com a saída visivelmente zerada por ~20 ms" como hipótese
em aberto (v1.9). O diagnóstico `antes_voltage_mode_list` mediu 0,067 V
depois desse write. Se o 0 V for de fato desejado, o write de
`SOURce:VOLTage base` é que está errado; se não for, o conserto abaixo
deve fazer a base aparecer — e aí a margem de 20 ms deixa de ser 0 V.

**Correção aplicada:** `AmetekMX30.write()` só retorna depois que a fonte
consumiu o comando (consulta `*ESR?` de sincronismo, tolerante a mudez
transitória até `PRAZO_SINCRONISMO_S` = 20 s; depois disso
`CommunicationError`, que continua abortando a bateria como hoje). Exceção:
`TRACe:DATA/DEFine/DELete` (gravação na Flash, com espera própria; o código
pede para não consultar durante a gravação). Bits de erro do ESR são logados
com o comando que os causou. Efeito colateral bom: `*WAI` passa a funcionar
(nada é enviado depois dele até a fonte responder). Custo estimado: ~901
writes × ~32 ms ≈ 29 s por `run all`. Testes:
`test_write_espera_a_fonte_consumir_antes_do_proximo_comando`,
`test_write_nao_consulta_a_fonte_durante_gravacao_na_flash`,
`test_sincronismo_tolera_mudez_ate_o_prazo`,
`test_sincronismo_vira_falha_de_comunicacao_depois_do_prazo`.
O readback de `arm()` (P02) continua valendo e é o que prova, por captura,
que o valor pegou.

**Correção aplicada (N3):** `trigger_step`/`trigger_pulse` escrevem a tensão
já no múltiplo de 0,1 V mais próximo (nunca acima do teto de software) e o
readback compara contra esse valor com a mesma tolerância de 0,5%. Testes
`test_tensao_disparada_e_escrita_na_resolucao_de_0v1`,
`test_quantizacao_nunca_passa_do_teto_de_software`.

## Rodada de validação — `sessao_2026-09-30_14-44-54_run02` (`run all` sem a 08)
Código com V1–V3, M1, sincronismo por write, N3. 14:46:30 → 14:52:42
(6 min 12 s para 19 classes). **17/19 OK** (contra 2/20 no run04). Nenhum
comando perdido, nenhum readback recusado, nenhum `*ESR?` com bit de erro.
Envelopes: 02 sag 0,07 pu, 03 swell 0,78, 04 interrupção 0,02, 05 CSINe ok.
Falharam só 04 e 19 — ambos por problemas NOVOS, reais, expostos agora que
os anteriores saíram da frente:

### F1 — 02/03/04 saem defasadas 216° do modelo (`gerar()`)
A fonte dispara sempre em `TRIGger:SYNChronize:PHASe 0`; `gerar()` põe fase
0 em t=0 da janela e o evento em t=60 ms (`pre_trigger_s` = 60 ms = 3,6
ciclos → fase 216°). Resultado físico: a senoide inteira da bancada está
216° deslocada do dataset simulado. Correlação da captura contra `gerar()`:
**-0,776** (02, 03, 04); contra o modelo com fase 0 no trigger: **0,999**.
A 04 reprovou na THD (3,38% contra 4,61%): o corte físico começa no zero,
o do modelo num degrau em -0,59 pu (THD do modelo com fase 0 no trigger:
3,12%). A 02 passou por pouco (3,10% contra 4,10%, tolerância 1%).
As bordas do evento em si estão no instante certo (60,07 → 120,30 ms).
**Correção aplicada:** `ExperimentoNativo.fase_de_disparo_graus()` =
`(pre_trigger_s × f0 mod 1) × 360` (216° para 02/03/04 a 60 Hz; 0° para as
outras nativas e a 50 Hz) programada via `AmetekMX30.definir_fase_de_disparo()`
antes de cada transiente nativo. Caminho LIST inalterado (`program_capture`
já grava 0°; pré-trigger 0). Sem readback de `TRIGger:SYNChronize:PHASe?`
(nunca testado na Rev. 5.53 — risco de `-113`); a validação física é quem
confirma. Testes `FaseDeDisparoTests`.
Motivo de preferir isto a mudar a validação: a docstring de
`limite_pico_bancada_pu` diz que as capturas reais existem "para confirmar
que a bancada reproduz o modelo".

### F2 — a 19 rodou inteira a 63 Hz (herança da 18)
Frequência por ciclo medida: 18 = 57,0 Hz → 63,0 Hz (correto); **19 =
63,03 Hz o tempo todo**; 20 = 60 Hz. Ao fim de um LIST a saída fica no
último ponto; `FREQuency:MODE FIXed` troca o modo, não o valor. THD por FFT
da 19: 5,00% (vazamento) contra 0,00%. A 20 se salvou porque
`program_capture` reescreve `SOURce:FREQuency 60`.
**Correção aplicada:** `restaurar_frequencia_base()` (chamada por
`restaurar_forma_e_modo_padrao()`, que roda no fim de toda classe e na
recuperação) reescreve `SOURce:FREQuency <base>` quando
`frequency_drift_list()` a alterou. Testes `FrequenciaBaseTests`.
Obs.: isso também significa que qualquer `run 19` isolado depois de um
`run 18` na mesma conexão estava sujeito ao mesmo problema.

**F1 confirmado na bancada** (`sessao_2026-09-30_14-55-22`): correlação com
`gerar()` 02 = 0,996, 03 = 0,998, 04 = 0,995 (antes -0,78); THD 04 4,69%
contra 4,61%, 02 4,16% contra 4,10% — as três aprovadas.

## Classe 08 (TRANSIENT) — análise (fora da bateria desde 14:44)

Dados: run04 (`sessao_2026-09-30_14-05-56_run04`, 08-0001, amplitude
sorteada 7,084 pu, 1 captura).

### T8-1 — o limite de pico escala a forma INTEIRA, não só o impulso
`ExperimentoWaveform._capturar_real` multiplica toda a forma por
`limite/pico` (0,340): a base de 127 V vira **43,1 Vrms** (LIST:VOLTage
43,12 × 11 ciclos + 49,05 no ciclo do impulso). Consequências: a captura não
tem a tensão base do modelo (envelope 0,24 pu), e o osciloscópio, com escala
dimensionada para o impulso (156 V/div, ~4,9 V/código), representa a base
com ±1 código de ruído → crista 1,556 (o motivo da reprovação restante).

### T8-2 — o pico físico passa do programado; a saída oscila
- Programado (forma escalada): 2,084 pu = **374,2 V**.
- A fonte escala cada TRACE pelo rms do ciclo: o ciclo do impulso tem
  crista 7,63 em 500 pontos e **7,81** no TRACE de 1024 pontos (a
  reamostragem alarga o impulso de 2 para 4 pontos) → pico previsto
  **382,8 V** (+2,3%).
- Medido (30 kSa/s): **415,3 V** e, na amostra seguinte, **-230 V**, depois
  +53/-186 V — oscilação da saída (~10 kHz) excitada por um degrau de
  ~424 V em 66 µs. Overshoot ≈ +8% do degrau; **undershoot ≈ 45% do
  degrau** abaixo do nível de partida (-41 V → -230 V).
- 415,3 V está 0,5 V abaixo de `max_peak_v` (415,8 V = `SOURce:VOLTage:HIGH`).
  A 30 kSa/s (reamostrado do registro bruto de ~116,7 kSa/s) o extremo real
  **entre amostras** pode ser maior — o valor medido é um limite inferior do
  pico físico. Pela restrição do dono (não ultrapassar a tensão máxima), a
  08 fica fora da bateria até isto ser medido direito.

### T8-3 — o impulso do modelo está além da banda da fonte
`gerar()` soma 5–10 pu em 2 amostras (50 µs → `ceil` → 66 µs) em t=80 ms
(fase 288°, onde a senoide vale -0,95 pu). A fonte só reproduz uma versão
limitada em banda e oscilante disso; a forma física nunca vai coincidir
amostra a amostra com o modelo, e envelope/crista do ciclo do impulso
refletem a oscilação, não o modelo.

### Riscos de só "consertar a escala" (manter a base a 127 V)
Com a base inteira, o impulso parte de -0,95 pu × 179,6 = **-171 V**. Com
os ~45% de undershoot medidos, um impulso até +X produz um vale em
≈ -171 - 0,45·(X + 171): para X = 300 V → **≈ -383 V** — o limite passa a
ser o **pico NEGATIVO** da oscilação, não o positivo. Os fatores 8%/45% vêm
de UMA captura a 30 kSa/s; não servem para dimensionar sem medir antes.

### Implementado (dono: "ok ótimo", 2026-09-30 ~15:00) — AINDA NÃO RODADO NA BANCADA
1. **Só o impulso é limitado** (`08.forma_para_bancada`, gancho novo
   `ExperimentoWaveform.forma_para_bancada`; o padrão continua escalando a
   forma inteira para qualquer outra classe). Base fica em 1 pu. Amplitude
   máxima = menor entre `(L - s)/(1 + 0,15)` (pico) e `(L + s)/0,60` (vale),
   L = 0,9 × `max_peak_v` / pico nominal, s = senoide no instante do impulso.
   Fatores 0,15/0,60 = medidos (0,08/0,45) × ~1,3 de margem. A 127 V:
   impulso 1,888 pu (degrau 339 V), pico previsto 220 V, **vale previsto
   -374 V** (com os 45% medidos: ≈ -324 V). A 220 V: 0,420 pu. `gerar()`
   (dataset) **inalterado** — conferido igual ao HEAD em 20 seeds.
2. **VMAX/VMIN na taxa cheia** (`KeysightDSOX4034A.medir_extremos`,
   `:MEASure:VMAX?/VMIN? CHANnel1`, [KS] p. 677-678; `+9.9E+37` → erro)
   medidos logo após TODA captura física e gravados no metadata
   (`pico_medido_v`, `vale_medido_v`, `teto_extremos_v`). Teto = fração ×
   `max_peak_v` (1,0 para todas; **0,9 para a 08**). Acima do teto:
   `PicoFisicoExcedidoError` DEPOIS de gravar a captura — classe para, sem
   retry (fora de `ERROS_CAPTURA_DESCARTAVEL` de propósito, senão a
   varredura continuaria subindo). A 08 **exige** a medida: sem ela, para.
   Outras classes sem medida só registram `extremos_indisponiveis`.
3. **Caracterização:** `set capturas N` + `run 08` → amplitude em rampa de
   0,25 pu até o máximo seguro (N=6: 0,25 / 0,58 / 0,90 / 1,23 / 1,56 /
   1,89 pu). Cada captura grava VMAX/VMIN e os previstos → dá para medir os
   fatores reais de sobressinal/subsinal por degrau. Primeira captura acima
   de 374 V interrompe a subida.
4. **Validação da 08** ignora os ciclos 4 e 5 (impulso + oscilação) —
   gancho `ciclos_excluidos_da_validacao`; remove ciclos INTEIROS dos dois
   lados (fase contínua). O pico é conferido pela medida do item 2.
5. Escala do osciloscópio usa a excursão PREVISTA (pico e vale), não só o
   pico programado (`excursao_fisica_prevista_v`), para o vale não clipar.
Testes: `Classe08BancadaTests`, `ExtremosFisicosTests`,
`ValidacaoSemCiclosExcluidosTests` (11 novos). A 08 continua em
`BATERIA_EXCLUIR` até a caracterização.

### T8-4 — caracterização na bancada (`sessao_2026-09-30_15-08-45`, `set capturas 6` + `run 08`)
6/6 capturas gravadas, nenhuma acima do teto de 374 V, todas aprovadas na
validação (ciclos 4 e 5 excluídos). VMAX/VMIN medidos pelo Keysight (taxa
cheia) — partida do impulso s = -171 V (senoide a -0,95 pu):

| Degrau | VMAX | VMIN | VMIN previsto (k=0,60) | (VMAX-(s+degrau))/degrau | (s-VMIN)/degrau |
|---|---|---|---|---|---|
| 45 V | 188 | -199 | -198 | (base domina) | (base domina) |
| 104 V | 185 | -231 | -233 | (base domina) | 0,58 |
| 163 V | 195 | -270 | -268 | (base domina) | 0,61 |
| 221 V | 191 | -298 | -304 | (base domina) | 0,575 |
| 280 V | 217 | -326 | -339 | 0,38 | 0,554 |
| 339 V | **298** | **-366** | -374 | 0,38 | 0,576 |

- **Subsinal real ≈ 0,58 do degrau** (a estimativa de 30 kSa/s dava 0,45):
  a margem de 0,60 segurou por pouco — último nível a **-366 V** com teto
  de 374 V.
- **Sobressinal real ≈ 0,38 do degrau** (a estimativa dava 0,08): pico
  previsto 220 V, medido 298 V. Nos degraus pequenos o VMAX é o pico da
  senoide base (~180 V).
- O array de 30 kSa/s subestima: no último nível, array 231 V contra VMAX
  298 V. Oscilação de ~10 kHz (período ~3 amostras), morta em <0,5 ms;
  depois disso resíduo ≤ 14 V.
- `indice_trigger` = 595 (não 600): o trigger real cai 5 amostras (167 µs)
  antes da margem nominal; o impulso está exatamente 80 ms depois dele. A
  validação alinha por `margem_amostras_antes`; deslocamento irrelevante
  para as métricas hoje — alinhar por `indice_trigger` (como
  `analisar_sessao.janela_nominal`) fica como melhoria.

**Recalibrado:** `SOBRESSINAL_DO_DEGRAU` 0,15 → **0,45**,
`SUBSINAL_DO_DEGRAU` 0,60 → **0,70** (medidos × ~1,2). Impulso físico a
127 V: 1,888 → **1,618 pu** (degrau 291 V). Previsto com margem: pico
251 V / vale -374 V; pelos fatores medidos: **pico ≈ 230 V / vale ≈
-339 V** (35 V abaixo do teto de 374 V, 77 V abaixo de `max_peak_v`).
Próximo passo sugerido: um `run 08` com 1 captura para confirmar antes de
tirar a 08 de `BATERIA_EXCLUIR`.

### Confirmação (`sessao_2026-09-30_15-18-50`, `run 08`, 1 captura)
Impulso 1,618 pu: **VMAX 230 V (previsto pelos fatores medidos: 230 V),
VMIN -334 V (previsto -339 V)**, validação física aprovada (crista 1,449,
THD 0,32% fora dos ciclos 4-5). Teto 374 V com 40 V de folga.

### Proposta original
1. Limitar só a AMPLITUDE do impulso (base fica a 1 pu), dimensionada pelo
   pico positivo E negativo previstos.
2. Medir o pico real com o osciloscópio na taxa cheia: `:MEASure:VMAX?`/
   `:MEASure:VMIN? CHANnel1` após cada captura, gravados no metadata, e
   recusar/abortar a classe se |pico| > limite (validação, não contorno).
3. Caracterizar a oscilação antes: `run 08` com `set capturas N` e
   amplitude crescente a partir de um valor pequeno (ex.: impulso até 1,2 pu),
   medindo VMAX/VMIN, e só subir enquanto |pico| ≤ 0,9 × `max_peak_v`.
4. Validação física da 08: comparar fora do ciclo do impulso (base) + pico
   medido contra o previsto, em vez de crista/envelope do ciclo inteiro.

## Pendências de validação — CHANGELOG v1.11 + RELATORIO_FINAL §8 (estado em 15:25)

### "Validação pendente" do CHANGELOG/v1.11.md
| # | Item | Estado | Evidência |
|---|---|---|---|
| 1 | T1 — P01+P02 corrigem H-NATIVO? | **Resolvido** (a causa era outra) | P02 (readback) pegou; causa = writes em rajada (N1/N2); sincronismo por write → 19/19 |
| 2 | T2 — `REFerence CUSTom` aceito (P07)? | **Confirmado** | nenhum aviso de fallback LEFT em 9 sessões; trigger na amostra 595–605 (M1 corrigia só a unidade) |
| 3 | P09 descarta captura em condição real? | **Confirmado** | run04: capturas nativas descartadas, classe/bateria seguiram; rede de segurança levantou e o retry da 01 passou |
| 4 | P11 abre o terminal `tail -f`? | **Confirmado pelo dono** ("o terminal funcionou") | `diagnostico on` em run04/14:44; `Popen` sem erro |

### RELATORIO_FINAL §8 (T1–T14)
| id | Energiza? | Estado |
|---|---|---|
| T1 | 5 V | resolvido (acima) |
| T2 | não | confirmado (acima) |
| T4 | 5 V | resolvido na prática: P07 + indice_trigger corretos |
| T5 | 5 V | **aberto, baixa prioridade** — quem zera a saída antes da lista; o dono considera o 0 V esperado |
| T10/T11 | não | parcial: `*OPC` na mesma mensagem funciona (bit OPC em 31–47 ms); `*OPC?` não re-testado; `SYST:CONF?`/`*OPT?` (Series I/II, limite de 32/100 pontos de lista) **não testado** |
| T12 | não | **aberto e relevante**: `SOURce:VOLTage:HIGH` é limite de PICO ou de RMS? Define se a fonte protege algo acima de 415,8 V ou não |
| T3 | não | **aberto**: `get_waveform` reamostra ~116,7 kSa/s → 30 kSa/s por `np.interp` (sem anti-aliasing); a 08 mostrou o array subestimando pico (231 × 298 V) |
| T6/T7/T8 | não (grava Flash) | **aberto (desempenho)**: `sleep` fixo de 3 s (DEFine) e 1 s (DATA); com `*OPC`+`*ESR?` funcionando dá para medir e trocar por espera por condição |
| T9 | não (desgaste Flash) | aberto; não recomendado sem necessidade. Hoje: máx. 156 escritas de TRACe por conexão (trava de 16/09 foi na ~280.ª) |
| T13 | offline | aberto, baixa prioridade |
| T14 | — | procedimento se a fonte travar; não aconteceu hoje |

### O que o código NOVO de hoje ainda não provou na bancada
- `run all` com a medida VMAX/VMIN em TODAS as classes (última bateria
  completa, 14:55, foi antes desse código) e com a 08 dentro da bateria.
- `set capturas N` > 1 em classes que não a 08 (P04/P09 com vários níveis).

### T12 — o manual já responde metade
Manual SCPI p. ~110: "VOLTage:HIGH — This command programs the maximum
**rms** voltage that the power source will accept", unidade V rms.
`configure_safe_baseline()` manda `SOURce:VOLTage:HIGH {voltage_high_vp}`
com 415,8 (tratando como PICO). Para a fonte isso é um limite de 415,8 Vrms
— acima do range de 300 V, ou seja, **não protege nada em pico**. A única
proteção de pico é de software (`max_peak_v`), e no caminho LIST ela só avisa
(ver abaixo). O teste de bancada confirma o comportamento real do firmware.

### Script estendido (`scripts/diag_nativo_output_off.py`, rodada 2)
Padrão: `opcoes` (T10/T11: `*OPT?`, `SYST:CONF?`, `*OPC?`) + `limite` (T12:
HIGH = 4 V, programa 2,5/3,5/4,5 Vrms com saída OFF; restaura o HIGH lido).
`--flash` acrescenta T7 (2 × `TRACe:DATA` sobre a TCC00 existente, mede até a
fonte responder um `*ESR?`). Testes da rodada 1 via `--so` (agora medem o
comportamento sincronizado). Validado no simulador.

### Bateria de 20 classes — `sessao_2026-09-30_15-26-05` (15:26 → 15:33, 7 min 13 s)
**20/20 OK.** Nenhuma captura reprovada, descartada ou acima do teto.
Extremos medidos pelo Keysight na taxa cheia (127 V; pico nominal 179,6 V):

| Classe | VMAX | VMIN | máx./179,6 | projetado a 220 V (×1,732) |
|---|---|---|---|---|
| 01 | 191 | -191 | 1,06 | 331 |
| 02 SAG | 209 | -191 | 1,16 | 362 |
| 03 SWELL | 205 | -205 | 1,14 | 355 |
| 04 INTERRUPTION | 209 | -191 | 1,16 | 362 |
| 08 TRANSIENT | 230 | **-339** | (amplitude se adapta ao teto) | — |
| 10 SAG_HARM | 222 | -183 | 1,24 | 385 |
| 11 SAG_FLICKER | 226 | -183 | 1,26 | 391 |
| 13 SWELL_HARM | 213 | -210 | 1,19 | 369 |
| **14 SWELL_OSC** | 248 | **-255** | 1,42 | **442 > 415,8** |
| **16 INTERR_HARM** | **262** | -185 | 1,46 | **454 > 415,8** |
| demais | ≤ 216 | ≥ -216 | ≤ 1,20 | ≤ 374 |

Os extremos MEDIDOS passam dos programados: a volta de um afundamento/
interrupção (02, 04, 10, 11, 16) sobressai ~15-45% (mesma oscilação da
saída vista na 08). **A 220 V, a 14 e a 16 passariam de `max_peak_v`** — e
agora a medida de extremos pararia a classe DEPOIS da captura, i.e., depois
de a fonte já ter saído do teto. Antes de 220 V: bloquear ANTES de programar
com base em pico previsto × fator de oscilação medido (não só pico programado).

### Diagnóstico rodada 2 — `logs/diag_nativo-2026-09-30_15-33-28*`
- **T10/T11:** `*OPT?` = `SCPI,NOUT,ADV,…,SNK,…`; `SYST:CONF?` termina em
  **`MX30-3Pi`** (manual p. 119: Series I reporta `MX45`) → **Series II**
  (limite de 100 pontos de lista). **`*OPC?` responde "1" em 32 ms** — a
  conclusão da v1.7 ("não respondeu") provavelmente vinha dos writes em
  rajada; candidato a sincronismo mais semântico que `*ESR?`.
- **T12:** com `VOLTage:HIGH 4`: 2,5 Vrms aceito; **3,5 Vrms (pico 4,95 V)
  aceito**; 4,5 Vrms → `-222 "Data out of range"` e tensão lida 0,0. ⇒
  **`VOLTage:HIGH` é limite de RMS** (confirma o manual). O `415.8` que
  `configure_safe_baseline` escreve como "Vp" é, para a fonte, 415,8 Vrms:
  **nenhuma proteção de hardware de pico** está ativa. HIGH restaurado para
  415,8 e confirmado. Proposta (não aplicada — dono decide): programar
  `VOLTage:HIGH` com o limite RMS de software (`max_voltage_rms`), o que é
  estritamente mais restritivo que hoje.
- **T7 — TRAVOU A FONTE (erro do Claude).** O teste mandou `TRACe:DATA TCC00`
  e consultou `*ESR?` logo em seguida. A fonte parou de responder a QUALQUER
  comando (58 s, até o fim do script; ver transcrição 15:33:30 → 15:34:21).
  O código já avisava ("Não consulte SYST:ERR? durante a gravação da Flash",
  `clear_all_traces`/`program_capture`) e o teste ignorou isso. Consequências:
  - **Reproduz de forma determinística uma trava da fonte** — forte candidato
    ao mecanismo da trava de 16/09 (exp 08, após muitas escritas de TRACe):
    se alguma gravação demorar mais que o `sleep(1.0)` fixo, a PRIMEIRA
    consulta seguinte cai durante a gravação.
  - Não existe forma segura de medir a duração da gravação (medir = consultar).
    O `sleep(1.0)` após `TRACe:DATA` e o `sleep(3.0)` após `TRACe:DEFine`
    ficam — são o único jeito seguro, e não são "contorno": são o intervalo em
    que o manual/firmware proíbem falar com a fonte.
  - O script também tinha um bug: imprimiu "OUTPUT OFF confirmado por leitura"
    sem ter conseguido ler. Corrigido (a frase agora depende da leitura); T7
    removido (`--flash` recusa); adicionado `--so pos_trava` (T14, só
    consultas, antes de qualquer outro comando).
  - A saída estava OFF (lida às 15:33:29.600, antes do T7) e nada no script
    liga a saída; mesmo assim, **confirmar OFF no painel** (AGENTS.md).
  - **T14 após religar** (`logs/diag_nativo-2026-09-30_15-39-14*`):
    `*ESR?` = 128 (só PON, bit 7 — confirma o power-cycle), fila
    `SYSTem:ERRor?` vazia, `STAT:QUES:COND?` = 0, `STAT:OPER:COND?` = 0,
    `*STB?` = 0; OUTPUT OFF confirmado por leitura. A trava **não deixa
    rastro** nos registradores da fonte depois de religar — o único registro
    dela é a nossa transcrição SCPI (P06/D1). As 2 gravações de teste na TCC00
    são irrelevantes: `program_capture` reescreve as TRACEs a cada conexão.

### Risco para uma futura bateria a 220 V (calculado offline)
`program_capture()` só LOGA "Pico calculado ... excede limite; prosseguindo"
quando o pico da forma passa de `max_peak_v`; a pré-validação P04 cobre só o
RMS das nativas. Pior pico programado em 200 sorteios de `gerar()` a 220 V:
**14 SWELL_OSCILLATORY 452 V**, 03 SWELL 560 V (sorteio simulado; na bancada
P04 pula os níveis > 300 Vrms), 20 INTERHARMONICS 379 V, 09 369 V, 17 368 V.
A 127 V tudo ≤ 323 V. Antes de 220 V: decidir bloquear (validação) em vez
de avisar, e T12.

## Achado de diagnóstico

### D1 — transcrição SCPI não gravava respostas
`query()` transcrevia o comando (Q e depois W), nunca a resposta.
**Correção aplicada:** linha `R <comando> -> <resposta>`.

## Log de mudanças desta análise
- 14:25 — V1+V2 e D1 corrigidos; 142 testes offline OK.
- Dono autorizou mexer em `sinais.py`/`oscilloscope_orm.py` e o teste de
  bancada, "desde que não ultrapasse a tensão de saída máxima da fonte".
- V3 e M1 corrigidos; 145 testes offline OK. Consulta ao manual (subagente).
  Script de diagnóstico com OUTPUT OFF pronto, aguardando execução na bancada.
- 14:36 — diagnóstico rodado na bancada (OUTPUT OFF). N1 e N2 = writes
  perdidos em rajada; N3 = truncamento a 0,1 V.
- Sincronismo por write e quantização de tensão aplicados; 151 testes
  offline OK. Próximo: `run all` na bancada para validar.
- Dono pediu tirar a 08 do `run all` por enquanto: `mestre.BATERIA_EXCLUIR`
  (env `BATERIA_EXCLUIR`, padrão "08"), aplicado só ao `run all` físico
  (`scripts_da_bateria_fisica()`); `run 08` isolado continua possível com a
  confirmação digitada; dataset simulado inalterado; aviso aparece antes da
  confirmação `EXECUTAR-20-CLASSES` (string inalterada). 152 testes OK.
- 14:52 — `run all` (19 classes): 17/19 OK. F1 (fase 216°) e F2 (19 a
  63 Hz) diagnosticados e corrigidos; 156 testes offline OK. Próximo: nova
  rodada — esperado 19/19.
- 15:01 — `sessao_2026-09-30_14-55-22`: **19/19 OK**. F1 confirmado
  (correlação 0,995–0,998); F2 confirmado (19 a 60,00 Hz, THD 0,17%).
- Classe 08: análise T8-1..3; itens 1–5 implementados; 167 testes offline
  OK. Próximo: caracterização `set capturas 6` + `run 08`.
- 15:12 — caracterização rodada: 6/6 OK, extremos -199…-366 V /
  185…298 V; fatores reais 0,38/0,58 (T8-4). Constantes recalibradas
  (0,45/0,70); 167 testes OK. Próximo: `set capturas 1` + `run 08` de
  confirmação.
- 15:20 — `run 08` de confirmação: VMAX 230 V / VMIN -334 V, aprovada.
- 15:25 — `BATERIA_EXCLUIR` volta ao padrão vazio (20 classes), a pedido do
  dono; 168 testes OK. Bateria de 20 classes iniciada às 15:26
  (`sessao_2026-09-30_15-26-05`). Script de diagnóstico estendido (T10/T11,
  T12, T7 opcional).
- 15:33 — **20/20 OK**. Diagnóstico rodada 2: Series II, `*OPC?` responde,
  `VOLTage:HIGH` é RMS; **T7 travou a fonte** (consulta logo após
  `TRACe:DATA`). T7 removido, mensagem final corrigida, T14 adicionado.
  Fonte precisa ser religada; conferir OUTPUT OFF no painel.
- 15:39 — fonte religada; T14 limpo (só PON), OUTPUT OFF confirmado.

## Implementação das 3 decisões (dono: "pode implementar essas coisas e vamos testar", ~15:42)

1. **Bloqueio PRÉVIO do extremo físico.** `logica/calibracao_extremos.json`:
   fator por classe = extremo medido (VMAX/VMIN, 15:26) / pico programado
   (0,97–1,46; 16 = 1,459; classe sem medida usa o maior; nunca < 1).
   `ExperimentoBase.extremo_fisico_previsto_v` = pico programado × fator ×
   `MARGEM_FATOR_EXTREMO` (1,10) — ou o modelo próprio da 08. Aplicado em
   `_indices_viaveis` (antes de QUALQUER comando SCPI) contra o mesmo teto
   do extremo medido: captura acima do teto é PULADA com log; todas puladas →
   `ParameterOutOfBoundsError` (determinístico). `extremo_previsto_v` vai para
   o metadata ao lado de `pico_medido_v`/`vale_medido_v`. Simulado com as
   seeds reais: **127 V — nenhuma captura pulada** (previstos 192–288 V; 08 =
   374); **220 V — 10, 11, 14, 16 puladas** (423–499 V previstos).
   Arquivo de calibração ausente/ilegível LEVANTA (sem base, sem bateria).
2. **`VOLTage:HIGH` = `max_voltage_rms`** (RMS, como o manual e o T12
   mostram); o limite de PICO do software continua validado como antes; nova
   validação: `max_voltage_rms` ≤ range. Comentários errados ("limite de
   PICO; o firmware rejeita (erro 14)") corrigidos em `ametek_orm.py`,
   `mestre.py` e no teste. Com o `START_BENCH` atual (EUT_MAX_VOLTAGE_RMS =
   range = 300) o efeito prático é nulo; passa a valer se o limite rms for
   menor que o range.
3. **`*OPC?` como sincronismo — atrás de `AMETEK_SINCRONISMO` (padrão
   `ESR`).** Risco não testado: se o `*OPC?` esperar o transiente armado
   depois de `INITiate`, o `arm()` entraria em impasse (o `*TRG` só vem
   depois). Teste seguro `--so opc` (T15) no script: *OPC? em repouso, logo
   após troca de forma (enviada crua) e logo após INIT com STEP armado e
   sem *TRG; depois ABORt e confere que a fonte responde. Saída OFF, ≤ 5 V,
   sem Flash. Só trocar o padrão se o T15 disser "seguro após INIT".
   **Resultado T15 (15:48, `logs/diag_nativo-2026-09-30_15-48-18*`):** repouso
   "1" em 31 ms; após troca de forma "1" em 47 ms; **após INIT (WTRIG) "0" em
   32 ms**; ABORt → IDLE, fonte respondendo, sem erros. A Rev. 5.53 não
   segura a resposta do `*OPC?` (fora do IEEE 488.2): informa na hora se há
   operação pendente. Sem impasse, mas sem ganho sobre `*ESR?` e com aviso
   falso em todo `arm()` → **`ESR` continua o padrão; a opção `OPC` fica só
   documentada.** (A conclusão impressa pelo script dizia "não respondeu";
   corrigida — ele respondeu "0".)

Testes: 171 offline OK (novos: bloqueio previsto com a calibração real,
HIGH = max_voltage_rms, sincronismo OPC/valor inválido; testes antigos com
limites incoerentes — 100 Vp com 127 V de base — corrigidos para 300/425,
e os de extremo MEDIDO/P04 isolam o fator em 1,0).

### Validação na bancada — `sessao_2026-09-30_15-58-51` (ESR, 127 V)
15:59:53 → 16:06:03 (6 min 10 s). **20/20 OK**, nenhuma captura pulada,
nenhum aviso além dos dois informativos da 08, `VOLTage:HIGH 300` na
baseline. **Extremo previsto ≥ medido nas 20 classes**, folga de 7% a 13%
(16–40 V): 04 230/214 V (7%, a menor), 16 288/265 V, 14 287/255 V, 08
374/334 V. Ressalvas honestas: (1) mesmas seeds da rodada de calibração
(15:26), então isto mede a REPETIBILIDADE (a 04 variou 209 → 214 V, +2,4%;
a 16, 262 → 265 V), não outros parâmetros sorteados — `set capturas N`
testaria a generalização; (2) 1 captura por classe na calibração.

Rodadas descartadas no caminho: 15:51 (AMETEK_SINCRONISMO=OPC ficou setado
no shell — funcionou, mas com aviso "devolveu '0'" em quase todo comando;
interrompida com Ctrl+C) e 15:55/15:56 (Keysight com `VI_ERROR_IO`/
`VI_ERROR_NCIC` no `*IDN?` logo após o Ctrl+C; nada energizado; voltou na
terceira abertura).

## Estado ao fim do dia / decisões pendentes do dono
- Bancada a 127 V: **20/20 classes OK** com o código deste worktree
  (última: 15:58, com bloqueio prévio de pico, HIGH rms e ESR).
- Nada commitado (dono pediu para esperar).
- (a) bloqueio prévio de pico, (b) `VOLTage:HIGH` rms e (c) `*OPC?`:
  implementados; (a) e (b) validados a 127 V; (c) testado e descartado
  (a Rev. 5.53 não segura a resposta do `*OPC?`).
- Antes de 220 V: a pré-validação pula 10, 11, 14 e 16 (previsto 423–499 V);
  validado só offline. Considerar `set capturas N` a 127 V para medir o fator
  de extremo em mais parâmetros antes de confiar nele a 220 V.
- Melhorias menores: alinhar a validação por `indice_trigger` (hoje por
  `margem_amostras_antes`, deslocamento de 5 amostras); T3 (reamostragem sem
  anti-aliasing no `get_waveform`).
