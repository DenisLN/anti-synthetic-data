# Relatório final — sessões de bancada de 2026-09-16 (v1.8 / v1.9 / v1.10)

Análise de 2026-09-21, **100 % offline**: nenhum instrumento foi tocado, nenhum arquivo do projeto
(código, `resultados/`, CHANGELOG) foi alterado, nada foi commitado. Tudo o que criei está em
`docs/analise-2026-09-21/` (índice na seção 10). Fluxo seguido, como você pediu: eu recortei ("trim") e
analisei as formas de onda antes de tudo → subagente 1 (logs + dados) → subagente 2 (verificação contra
os manuais AMETEK/Keysight, local e MCP painel-conhecimento ids 63/64) → subagente 3 (melhorias).
Detalhe e evidência por afirmação: `01_conclusao_investigacao.md`, `02_verificacao_manual.md`,
`03_propostas_melhorias.md`.

## 0. Resumo — o que você precisa saber (ordem de importância)

1. **Os dados das classes nativas (01–05) das duas sessões estão errados e não servem para dataset.**
   A fonte não aplicou o que o código escreveu (STEP/PULSe/CSINe) e **não gerou nenhum erro SCPI**:
   - Sessão 2 (220 V/50 Hz configurados): 01/02/04 saíram fisicamente a **127,2 Vrms** (0,578 pu onde
     deveria ser 1,0); 02 (50 capturas) não tem afundamento; 04 (10 capturas) tem um **pulso de 60 ms a
     ~242 V** (= 1,1 pu do nível da classe 03) **no lugar de uma interrupção** — rótulo ativamente errado.
     03 e 05 não têm arquivo (ver 5). [verifiquei nos `.npz`: 127,2 V estável; pulso de 60 ms começando
     em 560,0 ms nas 10 capturas, 1,91× a base]
   - Sessão 1 (127 V/60 Hz): 02/03/04 sem nenhum distúrbio; 05 (CSINe 5 %) saiu com THD ≈ 0 % (4,95 %
     nos dados antigos de 09/09) [verifiquei por FFT].
   - As classes **LIST/TRACe (06–17, 20) e a 18 saíram corretas**: alinhadas no início da saída, batem
     com o `gerar()` com correlação ≥ 0,989 (média ≈ 0,998).
   Causa exata: **em aberto** (só a bancada resolve; teste de ~5 min na seção 8). Diferença estrutural
   entre o que funciona e o que não funciona: `arm_transient()` (LIST) **lê de volta 9 parâmetros** e
   recusa divergência; `arm()` (nativo) **não lê nada de volta**.
2. **O "atraso da fonte" (~20 ms no v1.7, ~100 ms no v1.10, "500 ms de silêncio") não existe: é artefato
   do osciloscópio.** `:TIMebase:REFerence LEFT` põe a referência a **1 divisão** (=`RANGe`/10) da borda
   esquerda (manual Keysight p. 1337) e `get_waveform()` descarta o `x_origin` (`time_axis -=
   time_axis[0]`). Resultado: o trigger cai em `pre_trigger + RANGe/10` do registro. Previsto × medido:
   20,0 ms × 20,1–20,6 (janela 200 ms, dados de 09/09), 500,0 × 500,0–502,2 (janela 1 s, pre 400 ms,
   35 capturas nas 2 sessões), 560,0 × **560,00** (classe 04, dispersão zero). Consequência: a margem de
   400 ms do v1.10 foi dimensionada contra dois números falsos; **só 20 % do registro de 1 s é conteúdo**
   (o resto é 0 V antes e senoide nominal depois).
3. **Vereditos das hipóteses v1.8/v1.9 com `diagnostico on`** — ver seção 2. Em resumo: `LIST:REPeat`
   (v1.9) **confirmada por completo** (evento a 58–67 ms após o início da saída, nominal 60; nos dados
   antigos 108–150 ms), mas a medida por timestamp que o v1.9/v1.10 usou **não discriminava nada** (mede o
   pós-trigger do osciloscópio); o bit `transiente_ativo` **está com o sentido invertido** (bit 3 =
   "Transient is *completed*"; `True` em repouso é o correto); o `-113` **não** vem dos writes de
   `trigger_step/pulse` (0 de 1043 linhas com erro) — vem da janela `*WAI`+`INITiate:IMMediate`.
4. **Seu palpite estava certo: os logs não são gravados.** Só há `logging.basicConfig(stream=stdout)`;
   `logs/` está vazio; as pastas de sessão têm só `.npz`/`metadata`. O `metadata` também não guarda f0,
   tensão base, probe, margem, pre_trigger, flags nem versão do código (a sessão 2 foi 220 V/50 Hz e isso
   só existe no console). Além disso `run 01` e `run all` compartilham a pasta e o segundo sobrescreve o
   primeiro.
5. **A lógica de "tentar 3 vezes" perde os dados bons e retenta erro que nunca vai passar.** A classe
   inteira é reexecutada da captura 1 e o `_salvar_classe()` só roda no fim: 03 (52 capturas físicas) e
   05 (29) terminaram com **zero arquivos**, e as 7 capturas boas da 08 se perderam junto com a trava. A
   03 **é impossível a 220 V** (nível 1,4 pu = 308 V > 300 V do manual; pico 435 V > 415,8 Vp): falhou 3×
   igual, cada vez depois de 20 capturas. (3 falhas numa classe **não** abortam a bateria — abortam a
   classe; o que abortou a bateria foi o `CommunicationError` da trava, que é o comportamento desejado
   quando a fonte morre.)
6. **Por que as classes waveform "demoram a acontecer"**: cada captura reescreve 10–12 TRACe:
   ≈ 0,98 s de transferência ASCII (11 kB/linha a 115200 baud) + `time.sleep(1.0)` fixo por TRACe ⇒
   **19,7 s/captura** medidos (sessão 2), contra ~2,1 s de uma nativa. Só parte estava documentada (em
   comentários de código, não no README/CHANGELOG). O manual diz `TRACe:DEFine` ≈ 500 ms (o código espera
   3 s) e **não prescreve nenhuma espera após `TRACe:DATA`** (~10 s de 20 s são empíricos). O cache
   nunca acerta com `set capturas N` (bytes diferentes a cada captura).
7. **A trava da fonte (exp 08, sessão 2)**: o último comando com fila de erro lida com sucesso foi
   `FUNCtion:MODE LIST`; depois disso tudo deu timeout e o painel também morreu ⇒ travamento do
   controlador (firmware), não problema de USB/VISA. Contexto novo: `TRACe:DATA` grava em **memória não
   volátil** (manual p. 126) e aquela conexão já tinha feito ~280 gravações (o dobro de qualquer sessão
   anterior); nenhum aviso de desgaste no manual; catálogo estava longe de cheio (10 de 50). Causa **não
   determinável offline**; candidatos ordenados e mitigações na seção 6.
8. **Suas 3 ideias**: (i) margem 20 ms antes e (iii) margem curta depois — **viáveis e recomendadas**
   (20 ms antes / 50 ms depois, janela ~270 ms), **desde que antes se corrija a posição do trigger**
   (senão o evento de 200 ms é truncado em 4–8 ms); (ii) zerar a saída depois — **viável, mas não
   recomendo** (seção 4).

## 1. O trim das formas de onda (o que você pediu antes de tudo)

Método (`analise_trim.py`): detectar o início real da saída (|x| > 0,25 pu, refinado no cruzamento por
zero), recortar `[início − 20 ms, início + 250 ms]`, reconstruir o esperado com `gerar()` + `seed` (sessão
1, exata) e comparar já alinhado. Saídas: `saida_s1/`, `saida_s2/` (`tabela.json` + `trim/*.npz` por
captura), figuras em `figuras/` (`fig1` registro completo com a janela assumida × trim real; `fig2` trim ×
esperado; `fig3` pulso nativo antigo × novo).

| item | resultado |
|---|---|
| início da saída no registro de 1 s | 500,0–502,2 ms (sessão 1, n=15); 500,1–500,8 ms (sessão 2, n=20) — **não** 400/460 ms |
| conteúdo útil | 200 ms de 1000 ms (20 %); descarte com trim 20/250 ms: 73 % |
| fidelidade após alinhar (correlação c/ `gerar()`) | 06: 0,9988 · 07: 0,9993 · 09: 0,9998 · 10: 0,9976 · 11: 0,9972 · 12: 0,9979 · 13: 0,9990 · 14: 0,9994 · 15: 0,9996 · 16: 0,9893 · 17: 0,9994 · 20: 0,9992 · 01: 0,9997 (lag residual −0,1…−0,7 ms) |
| eventos SAG/SWELL/INT (início–fim após o início da saída; nominal 60–120 ms) | novo (REPeat 0): 10: 58–117 · 11: 58–117 · 12: 67–100 · 13: 67–117 · 14: 58–100 · 16: 67–117; antigo (REPeat 1): 108–150 início, fim fora da janela |
| observações | 08: escala física ×0,34 (documentada) e 220 V ⇒ limite 1,2 pu; 10/11/16/17: sobre-pico de **transição** de 18–22 % (ciclos nominais em 1,02–1,04 pu); 19: offset de 3 % ≈ 2 LSB do osciloscópio (medida sem resolução); 18: frequência 60→57→63 Hz e **o último valor (63 Hz) persiste** depois da lista |

Validade dos dados (para você saber o que pode usar):

| classe | sessão 1 (127 V, 1 captura) | sessão 2 (220 V, 10 capt./nível) |
|---|---|---|
| 01 NORMAL | ok | **inválida** (127 V, 0,578 pu) |
| 02 SAG | **inválida** (sem afundamento) | **inválida** (127 V, sem afundamento) |
| 03 SWELL | **inválida** (sem elevação) | sem arquivo (falhou 3×) |
| 04 INTERRUPTION | **inválida** (sem interrupção) | **inválida** (pulso de 242 V no lugar da interrupção) |
| 05 HARMONICS | **inválida** (THD ≈ 0 %) | sem arquivo |
| 06–17, 20 (LIST) | ok (ver fidelidade; 08 escalada ×0,34) | 06, 07 ok; 08–17, 20 não rodaram |
| 18 FREQUENCY_DRIFT | ok | não rodou |
| 19 DC_OFFSET | duvidosa (resolução vertical) | não rodou |

## 2. Hipóteses do v1.8 e v1.9 — foram diagnosticadas corretamente com `diagnostico on`?

| hipótese | veredito | o método de diagnóstico discriminava? | evidência-chave |
|---|---|---|---|
| **H-REPEAT** (v1.9): `LIST:REPeat 1` toca cada ciclo 2× | **CONFIRMADA por completo** | Por timestamp: **não** com `margin on` (Δ = pós-trigger do osciloscópio + ~0,14 s de overhead: 0,58 s nas classes PULSe [pre 0,46 s] e 0,64 s nas demais [STEP, CSINe, LIST]; **igual** para transiente de duração zero, de 60 ms e de 200 ms). Só com `margin off` e só para a *diferença*. Pela forma de onda: **sim, decisivo** | evento a 58–67 ms (novo) × 108–150 ms (antigo) do início da saída; o mesmo na classe 18 (dwell de 100 ms cumprido). O "parcialmente confirmada / 2,19× residual" do v1.10 é artefato de não descontar o piso da medida. Manual: só diz "how many times each data point will repeat", faixa 0–99 (0 = uma vez é a leitura natural) |
| **H-ZERO-LIST** (v1.7/v1.8): `VOLTage:MODE LIST` zera a saída | **REFUTADA para esse comando** | sim (par antes/depois) | 0,06 V **antes** de `VOLTage:MODE LIST` em 40/40 leituras; a saída fica em ~0,06 V durante todo o `program_capture()` (~19,7 s). Quem zera ainda é candidato: `ABORt` (linha 981) ou `FUNCtion:MODE LIST` — manual não diz; falta um ponto de log `apos_abort` |
| **H-ZERO-ACDC** (v1.8): `SOURce:MODE ACDC` zera a saída | **CONFIRMADA** | sim | 126,59 → 0,055 V; manual p. 98: "output is automatically set to zero" ao trocar de modo (é projeto, não anomalia) |
| **H-WAI** (v1.7→v1.8): race residual do `*WAI`; IDLE não garante que assentou | **CONFIRMADA (fenômeno), mecanismo em aberto** | **não** — `transiente_ativo` = `True` em 1042/1043 leituras porque o bit 3 é "transiente *concluído*" (manual p. 169): o campo está invertido | manual: falso IDLE é documentado (p. 132), `*WAI` não espera transientes (p. 173) e é abortado pelo comando seguinte (p. 142) — o `*WAI` de `arm()` é seguido imediatamente de `INITiate:IMMediate`. As falhas reais (03#2, 05#1–3, 18) concentram-se em `arm_antes_wai`/`arm_apos_init` |
| **H-113** (v1.7→v1.8): qual comando origina o `-113` | **PARCIALMENTE respondida** | sim para excluir, não para localizar | `extra={'erros': [...]}` não vazio em **0 de 1043** linhas ⇒ não são os writes de `trigger_step/pulse`; os 2 `-113` saíram de `assert_no_errors` logo após `INITiate:IMMediate` (janela: `*WAI` + INIT + 3 queries de diagnóstico). Hipótese (inferência): linhas coladas `*WAIINITiate:IMMediate`. `-226` da classe 18 **explicado pelo manual** (p. 90/214): `FUNCtion:MODE LIST` + lista de 12 pontos herdada da 17 vs listas de 2 pontos da 18; o manual manda pôr tudo em FIXed (§6.4.2 passo 1, p. 152) e o caminho nativo nunca faz isso |
| H-DIAG / H-MARGIN (minhas, antes da investigação) | **REFUTADAS** | — | eram uma explicação errada para o offset de ~100 ms e o pulso sumido; o offset é H-REF10 (acima) |

## 3. Problemas que você relatou

**P1 — "tentar 3 vezes… bateria abortada".** Leitura mais provável do seu relato (a que o código
confirma): numa classe com N capturas, 3 falhas descartam a classe inteira **e todas as capturas boas**.
Caminhos que perdem/abortam (`mestre.py`): (1) `_salvar_classe()` só depois do laço todo; (2) 3 tentativas
esgotadas ⇒ zero arquivos; (3) `CommunicationError`/`FalhaFatalDeInstrumento` aborta tudo sem retry
(correto quando a fonte morre, mas perde a classe em curso); (4) erro **determinístico** retentado 3×
(`ParameterOutOfBoundsError` é `ValueError`); (5) `recuperar_estado_seguro()` pode levantar
`FalhaFatalDeInstrumento` e derrubar a bateria por um passo "soft"; (6) a limpeza de órfãos em
`_salvar_classe` apaga arquivos de rodada anterior; (7) uma pasta de sessão por processo, sobrescrita
entre `run`s. Correção proposta: salvar por captura, retry por captura, classificar erro, validar níveis
antes (seção 6 e `03_propostas_melhorias.md`).

**P2 — waveform lento**: já explicado na seção 0.6 (números do log; documentação existente só em
comentários).

**P3 — a fonte travar**: seção 0.7 e 6.

## 4. Viabilidade das suas 3 ideias

| ideia | veredito | condição / desenho |
|---|---|---|
| (i) margem "antes" de 20 ms | **viável** | só depois de corrigir a posição do trigger (senão pre-trigger real = 44 ms e o pós-trigger é curto: 20/20 ms trunca o evento em 4 ms; 40/20 em 6 ms; 60/20 em 8 ms). Correção: `:TIMebase:REFerence CUSTom` + `:TIMebase:REFerence:LOCation 0.0` (manual p. 1337-1338, referência na borda esquerda) ou compensar `POSition` ou (melhor, robusto) usar `x_origin` da preamble para gravar `indice_trigger`. Vantagem extra: com janela de ~270 ms desaparece o problema dos ~32,5 kpts que motivou o v1.10 inteiro (na verdade o teto era do modo `WAVeform:POINts:MODE NORMal`; `RAW` entrega o bruto — manual p. 1458-1459) |
| (iii) margem curta "depois" | **viável e recomendada** | 50 ms depois cobre o retorno ao regime e o sobre-pico de transição; >100 ms não acrescenta nada. **Proposta consolidada: 20 ms antes + 50 ms depois (janela 270 ms = 8100 amostras); nas classes com `pre_trigger_s>0` (PULSe) a margem "antes" vira `pre_trigger_s + 20 ms`** |
| (ii) zerar a saída após o experimento | **viável tecnicamente; não recomendo agora** | (a) a saída já fica ~0,06 V durante os ~19,7 s de programação das classes waveform (por acidente do `ABORt`, não por projeto); (b) depois de um LIST o último passo persiste — para as classes de amplitude o último passo é a senoide nominal, então "zerar" só serve de marcador de fim; na 18 serviria para sair dos 63 Hz; (c) nas nativas o nível "depois" É a linha de base da medida (PULSe volta ao imediato) — zerar destrói o pós-evento; (d) a escrita imediata `SOURce:VOLTage 220` **não funcionou** 3× na sessão 2 (mesma família do problema nativo), então "zerar por escrita" não é confiável hoje; teria de ser um último passo de LIST a 0 V ou `OUTPut:STATe OFF` (derruba o relé); (e) adiciona uma transição 0→V por captura, justamente o tipo de estresse candidato à trava. Alternativa barata e melhor: gravar `indice_trigger`, `pre_trigger_s`, duração do evento, f0 e tensão base no metadata; e, se quiser marcador de fim em hardware, `OUTPut:TTLTrg:SOURce EOT`/`LIST:TTLTrg` (manual p. 77, p. 95) |

## 5. Como a sessão 2 se perdeu (linha do tempo)

`run all` 16:16:16 (220 V/50 Hz, `capturas 10`, `margin on`, `diagnostico on`): 01 e 02 ok (mas a 127 V) →
**03 falha 3× (308 V > 300 V) e 05 falha 3×** (INIT sem armar × 2, `-113` × 1) → 04 e 06, 07 ok → **08:
7 capturas boas; na 8ª a fonte para de responder logo depois de `FUNCtion:MODE LIST`** (16:33:33) →
`CommunicationError` → bateria abortada (correto), `safe_shutdown` não consegue confirmar → fonte
desligada na chave. Nada disso ficou salvo além dos `.npz` das classes que terminaram.

## 6. Trava da fonte — hipóteses em ordem

Fatos: última fila de erros lida com sucesso = `FUNCtion:MODE LIST`; as 3 leituras seguintes (5 s cada) e o
`SYST:ERR?` deram timeout; painel frontal morto (o projeto nunca envia `SYSTem:REMote`, que bloquearia o
painel); 28ª captura waveform da conexão (~280 `TRACe:DATA`); a 8ª captura programou seus 10 TRACe no
tempo normal (17,2 s) — a trava veio depois dos writes de forma de onda.
1. **Travamento do controlador (firmware Rev 5.53)** na transição para `FUNCtion:MODE LIST`, com gatilho
   provável em uma destas: (a) volume de gravações em memória não volátil na conexão (`TRACe:DATA` grava em
   não volátil — manual p. 126; ~280 vs ≤ 170 antes; o manual não fala em desgaste, mas também não exclui);
   (b) etapa de "compilação" da lista no controlador (manual p. 153/214 — sem custo documentado); (c)
   linhas de ~11 kB (`TRACe:DATA`) contra o buffer de entrada (erro 25 "Input buffer full" existe) — os 10
   writes da captura 8 passaram, então é o gatilho menos provável.
2. Estresse térmico/elétrico (16 min a 220 V, 27 transições 0→220 V): baixa evidência (sem proteção
   sinalizada).
3. USB/VISA no PC: **refutada** (painel também morreu).
Mitigações independentes de causa: salvar por captura; gravar o transcript SCPI em disco (o que faltou
para saber o último byte); parar de consultar depois do primeiro timeout; reduzir as gravações de TRACe
(reaproveitar ciclos idênticos, usar `SINusoid` para ciclo de seno puro variando só `LIST:VOLTage` — isso
também corta ~50–100 % do tempo por captura); contar gravações por conexão e parar de forma graciosa.
Ao religar a fonte: **antes de qualquer outro comando** ler `SYSTem:ERRor?`, `*ESR?`.

## 7. Melhorias propostas (detalhe: `03_propostas_melhorias.md`; patches: `propostas/`)

Critério de projeto (o seu): **"não contornar SCPI instável"** — validar e falhar rápido (ler de volta o que
foi escrito, checar o dado físico capturado, registrar tudo) em vez de empilhar `sleep`, retry cego e margem
gigante. Nada foi aplicado no projeto: os 8 patches estão prontos, testados offline (TDD; **83 → 125 testes,
todos verdes**; eu mesmo os reaplico em ordem numa cópia limpa do worktree e rodei a suíte: OK) e respeitam
os "Limites inegociáveis" do `AGENTS.md` (não tocam `max_*`, porta/baud, `assert_no_errors`, cache de TRACe,
confirmações digitadas). Dois grupos de testes existentes foram **adaptados**, não enfraquecidos
(`RemapeamentoNivelTests`: fonte fake com o teto real de 300 V; `MargemCapturaTests`: margem 20/50 ms).

| # | prioridade | proposta | patch (testes) |
|---|---|---|---|
| 1 | P0 | Caminho nativo íntegro: `FUNCtion:MODE FIXed` antes de STEP/PULSe/CSINe/LIST:FREQ (manual §6.4.2 passo 1; fecha o `-226` da classe 18), esperar `TRIG:STATe?`=IDLE antes de escrever, ler a fila incondicionalmente e interpretar o erro 19 | `p01` (+8) |
| 2 | P0 | `arm()` lê de volta `VOLTage:MODE?`/`TRIGgered?`/`PULSe:WIDTh?`/`FUNCtion:MODE?`/`FREQuency:MODE?` (tol. 0,5 %) e falha rápido; diagnostica `-220 Init ignored`. (`FUNCtion:SHAPe?`/`SOURce:MODE?` **não existem como query** na Rev. 5.53 — dão `-113`; corrige o 01) | `p02` (+6) |
| 3 | P0 | **Validação física pós-captura**, independente de mecanismo: envelope rms de meio ciclo + THD por FFT + fator de crista contra a forma realmente programada; marca no metadata e falha sem retry, **sem apagar dado**. Teria pego os 127 V, o SAG ausente, a interrupção invertida e a CSINe que não pegou | `p05` (+8) |
| 4 | P0 | Salvamento **por captura** (metadata parcial preservado) — recupera 03/05/08 | `p03` (+3) |
| 5 | P0 | Erro determinístico ≠ intermitente (sem retry de `ParameterOutOfBoundsError`/`ValueError`) + **pré-validação dos níveis** contra os limites: 03 a 220 V pula 1,4/1,6/1,8 pu antes de energizar | `p04` (+4) |
| 6 | P0 | Log em arquivo por sessão + transcrição SCPI com timestamp (o que faltou na trava) + metadata enriquecido (f0, tensão base, probe, margem, pre_trigger, `indice_trigger`, flags, `git describe --dirty`, IDN) + pasta por `run` (nada se sobrescreve) | `p06` (+5) |
| 7 | P1 | Posição do trigger: `REFerence CUSTom` + `LOCation 0.0` **com leitura de volta** (fallback `LEFT` compensado, logado) + `indice_trigger` a partir do `x_origin` | `p07` (+4) |
| 8 | P1 | `margin on` = **20 ms antes + 50 ms depois** (janela 270 ms; PULSe soma o pre-trigger ⇒ 80 ms) e `analisar_sessao.py` lendo f0/vbase/trigger do metadata. **Depende do `p07`** | `p08` (+4) |
| 9 | só desenho | Trava da fonte: contador de gravações de TRACe por conexão com parada graciosa (`AMETEK_MAX_TRACE_WRITES`), parar de consultar depois do 1.º timeout, relatório de trava em disco, ler `SYST:ERR?`/`*ESR?` ao religar | P0-7 |
| 10 | só desenho | Velocidade/Flash: **59 % dos ciclos são seno puro** (usar `SINusoid` variando só `LIST:VOLTage`; reutilizar nome de TRACe por hash de ciclo), `%.5g` custa 0,16 LSB e corta 26 % dos bytes, esperas `TRACe:DEFine`/`DATA` medidas e configuráveis; `RAW`/`MAXimum` no lugar de `NORMal`+`np.interp` (o "teto de ~32,5 kpts" é do modo de transferência, manual p. 1458-1459) | P1-3, P1-4 |
| 11 | só desenho | Diagnóstico honesto: renomear/inverter `transiente_ativo`; sem `MEAS…?` ao redor do `*TRG` (ou `;*WAI`); ponto `apos_abort`; `STATus:OPERation:EVENt?`; medir duração de evento no dado do osciloscópio | P1-5 |

Achados do manual que o projeto ignora ou usa errado (02 §(f)): `VOLTage:HIGH` é **rms** no manual (o projeto
trata como Vp — só teste T12, **não mudar o limite**); `*OPC?` é documentado (a Rev. 5.53 pode não
responder: teste T11); `VOLT? MAX` valida nível sem gerar erro; `LIST:TTLTrg`/`OUTPut:TTLTrg:SOURce EOT`
dão marcador de fim em hardware; `STATus:OPERation:EVENt?` é o detector de "transiente concluído";
erros device-specific (19, 20, 21, 24, 25, 27, 14) nunca são interpretados; guard de clipping 1/255 não
está no guia Keysight (só `0 = hole`) — **não enfraquecer sem medir** (teste offline T13).

**Como aplicar (quando você revisar):** `propostas/README.md` tem a ordem, as dependências (`p08` exige
`p07`) e o que cada patch NÃO cobre. `git apply --check` cada um antes; rodar
`env\Scripts\python.exe -m unittest tests.test_offline`.

## 8. Plano para a próxima visita à bancada (≤ 45 min, saída OFF ou 5 V, sem EUT)

**Antes de qualquer bateria de novo: não rode `run all` a 220 V nem confie em 02/03/04/05 até T1.** Ordem
de risco crescente (script proposto `logica/bench_diag_scpi.py` no 03 — rascunho, não executado; para no
1.º sintoma; a confirmação digitada `ENERGIZAR-DIAGNOSTICO` nunca é automatizada):

| id | energiza? | min | pergunta → decisão |
|---|---|---|---|
| T10, T11 | não | 1+1 | `SYST:CONF?`/`*IDN?`/`*OPT?` (Series I ou II ⇒ limite de 32 ou 100 pontos de lista); `*OPC?` responde? |
| T2 | não | 2 | só osciloscópio: `x_origin` esperado −pre_trigger (com `p07`) ou −(pre+RANGe/10) sem ele ⇒ confirma H-REF10 no firmware |
| T3 | não | 2 | `POINts:MODE MAXimum` + `POINts? MAXimum`: ≫ 32,5 k ⇒ trocar para RAW e tirar o `np.interp` |
| T12 | não | 2 | `VOLT:HIGH 200` → `VOLT 250` → `SYST:ERR?`: 250 V recusado ⇒ é rms |
| T6, T7, T8 | não | 5+5+3 | tempos reais de `TRACe:DEFine` (manual: 500 ms) e `TRACe:DATA` sem `sleep`; linha de 11,3 kB × 8,7 kB (erro 25?) |
| **T1** | 5 V | 5 | **H-NATIVO**: `VOLT:TRIG?` antes/depois de um transiente e escrita ≤ 50 ms depois dele; `FUNC:MODE?`. Valor antigo ou erro 19 ⇒ candidato 1 (o `aguardar_idle` do `p01` é a correção); `FUNC:MODE?`=LIST numa classe nativa ⇒ candidato 2 (o `p01` já corrige); tudo certo mas a saída erra ⇒ o `p05` segura a validade dos dados e vale abrir chamado com o fabricante |
| T5 | 5 V | 2 | `apos_abort` entre `ABORt` e `*CLS`: é o `ABORt` que zera a saída? |
| T4 | 5 V | 3 | o osciloscópio precisa encher o pré-trigger? (`FORCe` imediato × tardio, comparar `x_origin`) |
| T9 | não | 12 | 300 `TRACe:DATA` sobre um único nome, `SYST:ERR?` a cada 25: desgaste de Flash? |
| T13 | offline | — | contar amostras em 1/255 nos `.npz` bons: o guard de clipping descarta dado válido? |
| T14 | — | — | se a fonte travar de novo: religar e, **antes de qualquer outro comando**, ler `SYST:ERR?`, `*ESR?`, `STAT:QUES:COND?`; só depois repetir 06/07/08 com `set capturas 3` a **127 V**, log em arquivo, parando no 1.º timeout |

Depois: refazer 01–05 a 127 V com os patches `p01`–`p06` e conferir que a validação física aprova.

## 9. O que eu fiz, não fiz e como interpretei suas instruções

- **Fiz:** análise offline dos dois logs e das duas sessões (e das capturas antigas de 09/09 como
  referência); trim/alinhamento por captura; 3 subagentes em sequência (investigar → verificar no
  manual → propor melhorias), todos com o modelo `opus`; verifiquei por conta própria
  as afirmações mais pesadas (127,2 V nas nativas, pulso da 04 em 560,0 ms, THD da 05, aplicação em ordem dos
  8 patches numa cópia limpa e a suíte de 125 testes); extraí os manuais (`pdftotext`) para texto com marcador de página
  (`manuais_txt/`, ~4 MB) para os subagentes consultarem sem despejar o PDF no contexto.
- **Não fiz:** nada em hardware; **nenhum arquivo do projeto alterado** (o `git status` do worktree é
  o mesmo de antes: v1.10 não commitado + `docs/analise-2026-09-21/` novo); nenhum commit; nenhum
  patch aplicado. Os 8 patches e o script de bancada são **propostas** para você revisar.
- **Ajustes às suas instruções** (você autorizou): (1) "esse computador também" — você confirmou no meio
  da sessão: desligo o aspire5050 por ssh **e** este Windows; (2) a leitura de "5 vezes 3 falhas" está na
  seção 3 (P1) com a alternativa; (3) o primeiro subagente recebeu minhas hipóteses H-DIAG/H-MARGIN só
  para poder refutá-las — foram refutadas; (4) o subagente 3 também entregou patches testados (você
  pediu "propor"; fica tudo fora do projeto até você decidir); (5) `00_achados_do_orquestrador.md` ficou
  como registro histórico, marcado como superado.
- **Ainda em aberto (só a bancada resolve):** o mecanismo exato de H-NATIVO (T1); a causa da trava (só
  hipóteses ordenadas; T9/T14); qual comando zera a saída em `program_capture()` (T5); a semântica exata de
  `LIST:REPeat 0` (o manual só diz "how many times each data point will repeat", 0–99; os dados
  confirmam que 0 = uma vez).

## 10. Índice dos arquivos (`docs/analise-2026-09-21/`)

| arquivo | conteúdo |
|---|---|
| `RELATORIO_FINAL.md` | este documento |
| `01_conclusao_investigacao.md` | subagente 1: vereditos por hipótese, H-REF10, H-NATIVO, P1–P3, outros achados, testes de bancada |
| `02_verificacao_manual.md` | subagente 2: 79 afirmações (23 Keysight + 56 AMETEK) × manuais com página, correções ao 01, candidatos de mecanismo, achados novos do manual |
| `03_propostas_melhorias.md` | subagente 3: propostas P0/P1/P2, decisão sobre as 3 ideias, sessão de diagnóstico de bancada, "o que NÃO fazer" |
| `propostas/README.md`, `p01…p08.patch` | patches testados (ordem, dependências, testes, limites de cada um) |
| `00_achados_do_orquestrador.md` | briefing inicial do orquestrador (histórico; várias partes refutadas) |
| `analise_trim.py`, `figuras.py`, `parse_logs.py`, `repeat_old_vs_new.py`, `analise_2x2.py`, `s1_*.py` | scripts reprodutíveis (só leitura; usam `env\Scripts\python.exe`) |
| `saida_s1/`, `saida_s2/` | `tabela.json` e `trim/*.npz` (janela alinhada no início da saída) por captura |
| `figuras/fig1…fig3.png` | registro completo × janela assumida × trim; trim × esperado; pulso nativo antigo × novo |
| `manuais_txt/` | texto extraído dos dois manuais (apague se quiser; ~4 MB, derivado dos PDFs) |
