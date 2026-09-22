# 00 — Achados do orquestrador (antes de qualquer subagente)

> **⚠ ARQUIVO HISTÓRICO — várias conclusões abaixo foram REFUTADAS ou CORRIGIDAS.**
> Este foi o briefing que o orquestrador deu ao subagente 1 (2026-09-21, antes de qualquer
> verificação independente). Foram superadas por `01_conclusao_investigacao.md` (logs/dados) e
> `02_verificacao_manual.md` (manuais): **H-DIAG e H-MARGIN (seção D) estão refutadas**; o "onset em
> ~500 ms" (A1) e o "atraso de ~20 ms → ~100 ms" (A6) são o artefato de `:TIMebase:REFerence LEFT`
> (1 divisão = `RANGe/10`), não latência da fonte; em A3, a classe 05 NÃO funciona (THD ≈ 0) e a 04 TEM
> evento (pulso invertido); B1 (`transiente_ativo` sempre `True`) tem causa: o bit 3 significa
> "Transient is *completed*". Fica preservado só como registro do raciocínio. Leia primeiro
> `RELATORIO_FINAL.md`.

Data da análise: 2026-09-21. Dados: sessões de bancada de 2026-09-16 (worktree
`sessao-bancada-v18`, código = v1.9 commitado + v1.10 **não commitado**), logs de
console em `C:\Users\denis\Desktop\log1.txt` e `log2.txt`. Nada aqui foi rodado
em hardware; tudo é análise offline. Scripts reprodutíveis nesta pasta:
`analise_trim.py`, `parse_logs.py`, `repeat_old_vs_new.py`, `figuras.py`.

## 0. O que é o quê

| | Sessão 1 (`resultados/sessao_2026-09-16_16-07-44`, log1) | Sessão 2 (`.../sessao_2026-09-16_16-16-16`, log2) |
|---|---|---|
| Ponto de operação | 127 Vrms / 60 Hz, `set capturas` = 1 | 220 Vrms / 50 Hz, `set capturas 10` |
| Toggles | `margin on` + `diagnostico on` | `margin on` + `diagnostico on` |
| Código | **idêntico** entre as duas (todos os `.py` de lógica foram editados por último às 15:56–16:05, antes das 16:07:44; só o texto de ajuda do `cli.py` mudou às 16:09) | idem |
| Resultado | `run all`: 20/20 OK (1 retry em 18) | `run all`: 03 e 05 falharam 3x (sem nenhum `.npz` salvo), 08 derrubou a bateria (fonte travou); 09–20 nunca rodaram |

Ambas rodaram **v1.10 em andamento**: `LIST:REPeat` = `0` (não `1`), folga de `margin on`
= 400 ms (12000 amostras) de cada lado → registro de 30000 amostras (1 s) a 30 kSa/s;
`metadata` confirma `margem_amostras_antes=12000`. As pastas de sessão **não contêm
log** (ver B6). Referência "antiga": `resultados/*.npz` do repositório principal
(2026-09-09; janela 200 ms, sem margem, **sem diagnóstico**, `LIST:REPeat=1`).

## A. O que as formas de onda dizem (com trim)

Método: para cada `.npz` detectei o instante em que a saída deixa o repouso (`|x|>0.25 pu`,
refinado ao cruzamento por zero anterior), recortei em `[onset−20 ms, onset+250 ms]`,
reconstruí a forma esperada com `gerar()`+`seed` (sessão 1, f0=60, exata) e comparei já alinhada.
Saída: `saida_s1/`, `saida_s2/` (`tabela.json` + `trim/*.npz`); figuras em `figuras/`.

**A1. O onset da saída cai em ~500 ms do registro, sempre — não em 400 ms nem 460 ms.**
Sessão 1: 15 de 15 capturas com onset (01, 06–17, 19, 20): 500.0–502.2 ms. Sessão 2:
20/20 (06 e 07): 500.1–500.8 ms (dispersão < 1 ms). Vale para STEP (01, 19), LIST de
amplitude (06–17, 20) e LIST de frequência (18: freq. muda em ~500 ms, de 60 → 57 Hz, e
em ~600 ms para 63 Hz — dwell de 100 ms como programado). O código assume o trigger em
`margem_amostras_antes` = 400 ms (waveform/01/19/18/05) ou 460 ms (02/03/04, `pre_trigger_s=0.060`).
Consequência: com margem 400 ms o registro tem **~500 ms de silêncio (0 V) antes**, os 200 ms
úteis do evento no meio, e ~300 ms de senoide nominal depois → só 20% do registro é
conteúdo do experimento. O "Bug B" do v1.10 ("500 ms de silêncio") é exatamente isso.

**A2. Alinhado no onset, a captura bate com o `gerar()` quase perfeitamente.** Correlação
com o esperado: 06:0.9988, 07:0.9993, 09:0.9998, 10:0.9976, 11:0.9972, 12:0.9979,
13:0.9990, 14:0.9994, 15:0.9996, 16:0.9893, 17:0.9994, 20:0.9992, 01:0.9997; lag residual
após o onset: −0.1 a −0.7 ms (08: −2.2 ms). Ou seja, o conteúdo capturado é fiel; o
problema é onde ele está no registro. Exceções/observações: (a) 08 TRANSIENT sai com
razão de pico 0.317 (escala física 0.34, documentada; o pico de 6 pu vira ~2 pu);
(b) 10, 11, 16 têm razão de pico 1.18/1.18/1.22 — o ciclo com harmônicos/sag sai com
pico ~18–22% acima do esperado (LIST:VOLTage programa RMS, TRACe é normalizada por pico);
(c) 19 DC_OFFSET: correlação só 0.55 e offset medido oscila 0.017–0.077 pu (programado 0.031)
— 1 LSB do osciloscópio nessa escala vertical (~4 V/LSB ⇒ ~0.024 pu) é do tamanho do sinal;
falta resolução vertical, não é (necessariamente) defeito da fonte.

**A3. Classes nativas PULSe (02 SAG, 03 SWELL, 04 INTERRUPTION) NÃO mostram distúrbio nenhum
com `margin on`+`diagnostico on`.** Sessão 1: envelope de meio ciclo chapado (02: 0 eventos;
03; 04). Sessão 2: **0 de 50** capturas de 02 e **0 de 10** de 04 têm qualquer evento
(detector de envelope: limiares 0.8/1.12/0.3 do nominal). Em contraste, as capturas antigas
(2026-09-09, sem margem/sem diag) mostram claramente: SAG a 0.1 pu por ~60 ms começando ~20 ms
após o trigger (t≈80 ms na janela de 200 ms, trigger em 60 ms), INTERRUPTION a ~0 pu, SWELL 1.1 pu
(figura `fig3_nativos_pulse_antigo_vs_novo.png`). O usuário lembrava exatamente disto
("com margin on os experimentos nativos falham"). 05/HARMONICS (CSINe) e 18 (LIST:FREQ) funcionam
com margin on (não dependem de um pulso curto). Ainda **não** se sabe se a causa é `margin on`
(janela 1 s / pre-trigger 460 ms no Keysight) ou `diagnostico on` (ver A6/B2/H-DIAG).

**A4. A hipótese v1.9 (LIST:REPeat=1 dobra cada ciclo) está CONFIRMADA — e por completo, não
"parcialmente" como diz o v1.10.** Início/fim do evento (SAG/SWELL/INTERRUPTION), em ms após o
onset da saída (`repeat_old_vs_new.py`); nominal do `gerar()` = 60/120 ms:

| classe | antigo (REPeat=1, janela 200 ms) | novo (REPeat=0, margin on) |
|---|---|---|
| 10 SAG_HARM | 108 / 175+ (fim fora da janela) | 58 / 117 |
| 11 SAG_FLICKER | 108 / 175+ | 58 / 117 |
| 12 SAG_OSC | 150 / 200+ | 67 / 100 |
| 13 SWELL_HARM | 133 / 175+ | 67 / 117 |
| 14 SWELL_OSC | 108 / 175+ | 58 / 100 |
| 16 INT_HARM | 133 / 175+ | 67 / 117 |

Antigo: evento 1.8–2.5× atrasado e truncado pela janela; novo: nominal. O atraso "de ~2–2,7x"
sumiu com `REPeat 0` — não há "causa restante" no atraso do evento. O que sobra é o A1
(onset em 500 ms), que é outro fenômeno.

**A5. Estado final após LIST:** após LIST:FREQuency (classe 18) a frequência **fica no último
valor da lista** (63 Hz persiste até o fim do registro, ≥400 ms além do fim da lista de 200 ms).
Após LIST de amplitude/forma (06–17, 20) a saída "volta" a senoide nominal porque o último passo
da lista (ciclo 12) é a própria senoide nominal — coerente com "último passo persiste". Relevante
para "zerar a saída após o fim do experimento".

**A6. Comparação antigo × novo do atraso trigger→saída:** antigo (sem diag/sem margem): saída
~20 ms depois do início do registro (=trigger, `pre_trigger_s=0`) para LIST/STEP, e ~80 ms
(=60 ms de pre-trigger + ~20 ms) para PULSe. Novo: onset a 100 ms depois do trigger comandado
(500 vs 400 ms) para LIST/STEP, e PULSe ausente. A diferença (~80 ms extra) é o que precisa de
explicação — ver H-DIAG abaixo.

## B. O que os logs de diagnóstico dizem (`parse_logs.py`)

**B1. `transiente_ativo` é `True` em 115/115 (log1) e 927/928 (log2; 1 `None` na trava)
linhas** — inclusive em repouso, em `transiente_concluido` e antes do disparo. O campo
(`STATus:OPERation:CONDition? & 0x8`, "bit 3 = TRANS, manual pg. 169") não discrimina nada:
provavelmente sinaliza "modo transiente habilitado" e não "transiente rodando". `output=1`
sempre (exceto `None` na trava).

**B2. O timestamp `apos_trigger → transiente_concluido` mede o osciloscópio, não a lista.**
Ordem de grandeza e estrutura: log2, mediana por classe: 02 SAG (PULSe, pre 0.46 s) 0.578 s (n=50),
03 0.578 s (n=52), 04 0.594, 01 STEP 0.641 (n=10), 05 0.641 (n=29), 06/07 LIST 0.640 (n=10 cada),
08 0.656 (n=7). O que separa os dois grupos é exatamente `pre_trigger_s` (0.06 s): 1.0 s − 0.46 =
0.54 s de pós-trigger + ~0.04 s de overhead = 0.58; 1.0 − 0.40 = 0.60 + 0.04 = 0.64. STEP (duração
zero), PULSe (60 ms) e LIST (200 ms nominais / 400 ms se dobrasse) dão o mesmo Δ.
Em `_capturar_real` a sequência é `fonte.trigger()` → `osc.wait_for_trigger_complete()` (bloqueia
até o Keysight terminar de adquirir o pós-trigger) → `fonte.wait_transient_complete()` (loga
`transiente_concluido`, a fonte já está IDLE há tempo). O teste proposto no v1.9 ("~200 ms
confirma, ~400 ms refuta REPeat") e a medida do v1.10 (516→438 ms) **não têm poder de
discriminação** com `margin on`. Só a forma de onda (A4) discrimina.

**B3. Tensão medida (`MEASure:VOLTage:AC?`) nos pontos-chave** (mediana; log1+log2):
`antes_voltage_mode_list` 0.06 V (27+13 amostras) e `apos_voltage_mode_list` 0.06 V ⇒ a saída
das classes LIST **já está em ~0 V antes** de `VOLTage:MODE LIST` — a zeragem não é causada por
esse comando (hipótese de zeragem "ao entrar em LIST" do v1.7/v1.8 refutada *para esse comando*;
ocorre antes dele, dentro de `program_capture()`: `ABORt`/`*CLS`/`FUNCtion:MODE FIXed`/`VOLTage:MODE
FIXed`/`SOURce:VOLTage`/TRACe:DATA…/`SOURce:LIST:*`/`FUNCtion:MODE LIST` — não há ponto de log para
bisseccionar). Para ACDC (classe 19): `antes_sourcemode_acdc` 126.59 V → `apos_sourcemode_acdc`
0.055 V ⇒ **`SOURce:MODE ACDC` zera a saída** (confirmado). Antes do disparo, classes waveform
ficam em ~0.06 V; nativas ficam em 126.6 V (exceto 01 e 19, ~0–5.5 V).

**B4. Custo de cada captura waveform** (por que "demora a acontecer"): gap
`transiente_concluido → antes_voltage_mode_list` = **17.19–17.28 s** (n=25, sessão 2, 10 TRACe;
~20 s na sessão 1 com 12 TRACe) e ~1.33 s até armar. Vem de `program_capture()`: por TRACe
(`TRACe:DATA` com 1024 valores em ASCII, 115200 baud) ~0.72 s de transferência + `time.sleep(1.0)`
fixo + `*CLS` = ~1.72 s × 10–12. Captura nativa: ~2.1 s. Primeira vez: +3 s por `TRACe:DEFine`.
O cache de TRACe (v1.7) só pega quando os bytes da forma são idênticos; com `set capturas N` (cobertura
determinística de parâmetro) nunca acontece.

**B5. Falhas e o que os pontos de diagnóstico localizam:**
- Sessão 1, classe 18, tentativa 1: `INITiate:IMMediate` → `-226 "Lists not same length"`.
  Sequência real: 17 (12 passos de LIST:FUNCtion:SHAPe/VOLTage/DWELl) → 18 (`frequency_drift_list`
  escreve `FREQuency:MODE LIST`, `LIST:FREQuency/VOLTage/DWELl` com 2 pontos, **sem** `FUNCtion:MODE
  FIXed`/limpar as listas de forma da 17). Falhou 1x, passou após `recuperar_estado_seguro()` (que
  faz `ABORt`, `*CLS`, `FUNCtion:MODE FIXed`, `VOLTage:MODE FIXed`, `SOURce:FREQuency:MODE FIXed`).
  Causa provável: lista de forma de 12 pontos herdada da 17 + lista de frequência de 2 pontos.
  (`trigger_step()`/`trigger_pulse()` também nunca forçam `FUNCtion:MODE FIXed`.)
- Sessão 2, classe 03 (SWELL, 5 níveis × 10): tentativa 1 falhou na captura 21 com
  `ParameterOutOfBoundsError: Tensão 308.0 Vrms fora do limite de software 0..300.0` (nível
  1.4 pu × 220 V) — **determinística**, depois de 20 capturas boas. Tentativa 2: 12 capturas boas e
  `-113 "Undefined header"` no `INITiate:IMMediate` da captura 13. Tentativa 3: idem tentativa 1.
  Nenhum `.npz` de 03 foi salvo.
- Sessão 2, classe 05 (HARMONICS, CSINe): 3 tentativas: `TimeoutError ... último estado='IDLE'` (INIT
  sem erro mas a fonte nunca armou) nas capturas 3 e 14 (tentativas 1 e 2) e `-113` no INIT da captura
  15 (tentativa 3). Nenhum `.npz` de 05 salvo.
- Nos 5 casos (03#2, 05#1, 05#2, 05#3 e a classe 18 da sessão 1 com outro erro) o último ponto de log
  é `arm_antes_wai` ou `arm_apos_init`, e o `fim_trigger_*` anterior tem `erros=[]` em todos:
  **o `-113` não vem dos writes de `trigger_step/trigger_pulse` (v1.8 queria localizar isso) —
  vem do par `*WAI` + `INITiate:IMMediate` (ou das leituras de diagnóstico imediatamente antes)**.
  O caso "INIT sem erro mas o estado fica IDLE" tem o mesmo lugar geométrico.
- Sessão 2, classe 08 (TRANSIENT, 10 capturas): 7 capturas boas; na 8ª, `program_capture()` chegou
  normalmente a `antes_voltage_mode_list` (t = +17.2 s, igual às anteriores) mas as 3 leituras do ponto
  de diagnóstico retornaram `None` (3×5 s de timeout VISA = 15 s; ponto logado às 16:33:33), o
  `check_errors()` seguinte estourou em 16:33:38 (`CommunicationError`, VI_ERROR_TMO) → bateria
  abortada por "infraestrutura"; `safe_shutdown()` também não conseguiu confirmar (`OUTPut:STATe?`
  timeout). O usuário relata que a fonte não respondia nem no painel nem por SCPI e foi desligada na
  chave. **O último comando cuja fila de erro foi verificada com sucesso foi `FUNCtion:MODE LIST`**
  (o comando seguinte, `VOLTage:MODE LIST`, nem chegou a ser confirmado). Contexto: era a 28ª captura
  waveform da conexão (≈ 280 `TRACe:DATA` + 10 `TRACe:DEFine` + `TRACe:DELete:ALL` no connect), o maior
  volume de gravações de Flash que uma única conexão já teve (sessão 1: ~170; v1.7: ~156).

**B6. Os logs não são gravados.** `logica/mestre.py:23` faz `logging.basicConfig(... stream=sys.stdout)`
(só console); `cli.py` não adiciona `FileHandler`; só `preflight_new.py` grava em `logs/`. `logs/`
está vazio; as pastas de sessão têm só `.npz`, `metadata/*.jsonl`, `snr_30db/`, `analise/`.
O `metadata` também **não** grava f0, tensão base, fator de probe, `pre_trigger`, escala vertical,
flags margin/diag, versão do código nem IDN dos instrumentos — `analisar_sessao.py` chumba
`gerar(t, 60.0, ...)` e `base_voltage_rms=127` (errado para a sessão 2, que foi 50 Hz/220 V).

## C. Lógica de retry / abortos (mestre.py `executar_bateria`)

- `MAX_TENTATIVAS_POR_CLASSE=3`: qualquer `Exception` que não seja `CommunicationError`/
  `FalhaFatalDeInstrumento` reexecuta a **classe inteira**, da captura 1, depois de
  `recuperar_estado_seguro()`.
- `executar()` só chama `_salvar_classe()` **depois** de todas as capturas da classe → uma falha na
  captura k joga fora as k−1 boas (memória) e tenta de novo; 3 falhas = classe com zero dados.
  Erros determinísticos (`ParameterOutOfBoundsError`, `ValueError`) são retentados igual.
- Interpretação do relato do usuário ("dentro de uma bateria de 5×3 falhas, a bateria é abortada"):
  a leitura mais provável é: numa classe com N capturas, 3 falhas seguidas abortam a classe inteira
  perdendo tudo, o que não deveria acontecer (deveria reter as capturas boas e retentar só a que
  falhou, e/ou nem retentar erro determinístico). Uma segunda leitura possível: uma falha "de
  infraestrutura" (`CommunicationError`, ex. timeout VISA) aborta toda a `run all` sem retry; foi o que
  matou 08–20 na sessão 2 (a fonte realmente tinha morrido, então abortar era correto; mas os dados
  das 7 capturas boas de 08 se perderam por não terem sido salvas incrementalmente).
  `recuperar_estado_seguro()` pode levantar `FalhaFatalDeInstrumento` e derrubar tudo por um erro
  em passo "soft" (aviso hoje só para `restaurar_forma_e_modo_padrao`).

## D. Hipóteses em avaliação e leitura preliminar (para o subagente 1 desafiar)

| id | origem | enunciado | veredito preliminar |
|---|---|---|---|
| H-WAI | v1.7→v1.8 | "IDLE" em `TRIGger:STATe?` não garante que a troca de modo assentou (race residual do `*WAI`) | **inconclusivo pelo método**: o campo TRANS é sempre True; tensão voltou à base em todos os pontos; mas as falhas reais (03#2, 05#1–3) concentram-se exatamente no par `*WAI`+`INIT` de `arm()` |
| H-113 | v1.7→v1.8 | qual comando origina o `-113` intermitente | **respondida em parte**: não são os writes de `trigger_step/pulse` (`erros=[]` em todos); é `*WAI`/`INITiate:IMMediate` (ou as leituras de diag logo antes). Mecanismo desconhecido (candidatos: linhas coladas `*WAIINITiate…`; INIT ignorado por firmware ocupado) |
| H-ZERO-LIST | v1.7→v1.8 | `VOLTage:MODE LIST` zera a saída | **refutada para esse comando** (já 0.06 V antes dele); zeragem ocorre antes (ponto de log ausente) |
| H-ZERO-ACDC | v1.8 | `SOURce:MODE ACDC` zera a saída | **confirmada** (126.59 → 0.055 V) |
| H-REPEAT | v1.9 | `LIST:REPeat 1` toca cada ciclo 2× | **confirmada**, por completo, pela forma de onda (A4); a medida por timestamp (B2) nunca poderia ter discriminado; o "parcialmente confirmada" do v1.10 é artefato |
| H-DIAG (nova) | este trabalho | as leituras de diagnóstico feitas logo após `*TRG` (`apos_trigger`: 3 queries ≈ 40 ms cada, inclusive `MEASure:VOLTage:AC?`) atrasam o transiente da fonte em ~80 ms e fazem o PULSe de 60 ms desaparecer (pulso expira antes de a saída ser atualizada) | **plausível, não provada**. Evidência: (i) o Keysight honra o pre-trigger comandado (Δ de B2 = pós-trigger + 40 ms, para 0.40 e 0.46 s), logo o BOT sai cedo; (ii) o onset fica 100 ms depois do trigger contra ~20 ms nos dados antigos sem diag; (iii) PULSe de 60 ms some, STEP/LIST (persistentes) só atrasam 100 ms; (iv) `apos_trigger` foi adicionado no v1.9 e a primeira sessão com `margin`+`diag`+distúrbio foi a v1.10. Alternativa H-MARGIN: a janela de 1 s/pre-trigger 0.46 s no Keysight causa o sumiço. Só um teste 2×2 na bancada separa (margin on/off × diag on/off, classes 02 e 07). |

## E. O que não sei / o que o subagente 1 deve checar por conta própria

1. Reproduzir A1–A4 e B1–B5 com scripts próprios (não confiar nos meus números).
2. Procurar erros no meu raciocínio de B2 (a estrutura de `_capturar_real`) e em H-DIAG.
3. O que `STATus:OPERation:CONDition?` bit 3 realmente significa (manual pg. 169, Tabela 7-1).
4. Quantificar, por classe, quanto do registro de 1 s é útil (A1) e o quanto se ganha com trim.
5. Avaliar as três ideias do usuário (margem de 20 ms antes; zerar a saída após o experimento; margem
   pequena depois) contra os dados: janela mínima necessária, viabilidade dado A1/A5/H-DIAG.
6. Investigar a trava da fonte (B5, classe 08): o que mais mudou nas últimas capturas; existe padrão
   (contagem de escritas de Flash, tamanho do transiente, `LIST:VOLTage` do ciclo do pico) que a
   explique? Listar hipóteses ordenadas com evidência a favor/contra e como testar.
7. Confirmar o mecanismo de perda de dados (C) e ler `cli.py` para ver por que nada é persistido.
