# 03 — Propostas de melhoria (subagente 3)

Análise **100 % offline**, 2026-09-21. Nenhum instrumento foi tocado; nenhum arquivo do projeto
ou de `resultados/` foi alterado. Os patches foram desenvolvidos e testados numa **cópia de
scratch** e entregues como diffs em `propostas/` (ver `propostas/README.md`).

Base: `01_conclusao_investigacao.md` (subagente 1) e `02_verificacao_manual.md` (subagente 2),
que corrige partes do 01. Citações como "01 §1.2" e "02 B46" apontam para esses dois documentos.

## Critério de projeto que orienta tudo abaixo

> **"Não vamos tentar contornar softwares SCPI instáveis."**

Traduzido em regras de decisão, aplicadas em todas as propostas:

1. **Ler de volta o que se escreve.** Um write aceito na fila não é um write
   aplicado (01 §1.2 é a prova: duas sessões inteiras de dado errado sem um
   único erro SCPI).
2. **Checar o dado FÍSICO capturado**, não só o que o instrumento responde.
   Readback SCPI cobre o que a fonte *diz*; a validação de forma de onda cobre
   o que ela *fez*.
3. **Falhar rápido e marcar**, nunca compensar em silêncio. Onde o firmware é
   frágil (Rev. 5.53), isolar, documentar e **registrar** — não empilhar
   `sleep`, retry cego nem margem gigante para esconder o sintoma.
4. **Nunca perder dado bom por causa de dado ruim.** Marcar e quarentenar é
   sempre melhor que descartar ou que não gravar.

---

## Índice

- [P0 — Validade dos dados e segurança da bancada](#p0)
  - [P0-1. Integridade do caminho nativo (FIXed, IDLE, erro 19)](#p0-1) — patch `p01`
  - [P0-2. `arm()` lê de volta e falha rápido](#p0-2) — patch `p02`
  - [P0-3. Validação FÍSICA pós-captura](#p0-3) — patch `p05`
  - [P0-4. Salvamento incremental por captura](#p0-4) — patch `p03`
  - [P0-5. Erro determinístico × intermitente e pré-validação de níveis](#p0-5) — patch `p04`
  - [P0-6. Log em arquivo, transcrição SCPI e metadata enriquecido](#p0-6) — patch `p06`
  - [P0-7. Trava da fonte: mitigar, registrar, recuperar](#p0-7) — só desenho
- [P1 — Precisão e velocidade](#p1)
  - [P1-1. Posição do trigger (H-REF10)](#p1-1) — patch `p07`
  - [P1-2. Nova janela do `margin on` e `analisar_sessao.py`](#p1-2) — patch `p08`
  - [P1-3. RAW/MAXimum e o fim do `np.interp`](#p1-3) — só desenho
  - [P1-4. Velocidade e exposição da Flash](#p1-4) — só desenho
  - [P1-5. Diagnóstico honesto](#p1-5) — só desenho
- [P2 — Higiene](#p2)
- [As três ideias do dono: decisão final](#ideias)
- [Sessão de diagnóstico de bancada (T1–T14)](#diagnostico)
- [O que NÃO fazer](#nao-fazer)

---

<a id="p0"></a>
## P0 — Validade dos dados e segurança da bancada

<a id="p0-1"></a>
### P0-1. Integridade do caminho nativo: `FUNCtion:MODE FIXed`, esperar IDLE, checar o erro 19
**Patch `p01_caminho_nativo_modo_fixed_e_idle.patch` · risco baixo · esforço baixo · benefício altíssimo**

**Problema e evidência.** O caminho nativo (`trigger_step`/`trigger_pulse`/
`configure_harmonics_csine`/`frequency_drift_list`) **nunca** escreve `FUNCtion:MODE FIXed`. O
manual é explícito (02 B10, [AM] §6.4.2 p. 152, Passo 1): "Set the functions that you do not
want to generate transients to FIXed mode." Consequências documentadas:

- é a **causa provada** do `-226 "Lists not same length"` da classe 18 depois
  da 17 (02 §(b) item 8; [AM] §4.17 p. 90 + Apêndice C p. 214);
- é o **candidato n.º 2 de H-NATIVO** (02 §(c)): depois de qualquer classe
  waveform, `FUNCtion:MODE` fica em `LIST` com 12 pontos de forma, que passam a
  participar do `*TRG` junto com o STEP/PULSe de tensão.

Além disso, `trigger_step`/`trigger_pulse` escrevem `VOLTage:MODE` e `VOLTage:TRIGgered` **antes
de qualquer consulta de estado** — só `arm()`, depois, espera IDLE. Se o transiente anterior
ainda roda, [AM] p. 217, erro
**19 "Illegal during transient"** diz que a operação não está disponível: o
valor antigo permanece e o `*TRG` seguinte o reaplica. É exatamente o padrão observado (classe
04 recebendo o nível 1,1 pu da classe 03, 01 §1.2). E a fila de erros só era lida **com
`diagnostico on`** — por isso 01 §1.3 B5 registra `erros=[]` em 1043 de 1043 linhas.

**Desenho.**
1. `AmetekMX30.aguardar_idle(timeout_s=20)` — polling tolerante de
   `TRIGger:STATe?` até IDLE, com mensagem própria citando o erro 19.
2. `_neutralizar_transientes_residuais()` — `FUNCtion:MODE FIXed` +
   `SOURce:FREQuency:MODE FIXed`, chamado nos **quatro** pontos do caminho
   nativo antes de qualquer `VOLTage:MODE`.
3. `_confirmar_fila_apos_transiente(contexto)` — `check_errors()`
   **incondicional** (não mais só com `diagnostico on`) que interpreta o
   código 19 e levanta com mensagem específica.
4. `frequency_drift_list` ganha `VOLTage:MODE FIXed` explícito antes de
   `FREQuency:MODE LIST` (fecha o `-226`).

```python
def trigger_step(self, voltage_rms: float) -> None:
    ...
    self.aguardar_idle()                          # nada é escrito com a fonte BUSY
    self._neutralizar_transientes_residuais()     # FUNC:MODE FIXed + FREQ:MODE FIXed
    self.write("VOLTage:MODE STEP")
    self.write(f"VOLTage:TRIGgered {voltage_rms:.8g}")
    self._transiente_esperado = {...}             # conferido por arm(), ver P0-2
    erros = self._confirmar_fila_apos_transiente("programação do STEP nativo")
```

**Testes (8 novos, todos offline).** `FUNCtion:MODE FIXed` presente e **antes**
de `VOLTage:MODE` nos quatro pontos; nenhum write ocorre enquanto `TRIGger:STATe?` devolve BUSY;
erro 19 vira `InstrumentHardwareError` com a palavra "transiente"; `aguardar_idle` falha com
mensagem própria; `diagnostico on/off` continua sem mudar **nenhum write**.

**Validar na bancada.** Rodar `native` e depois `run 18` logo após `run 17` na
MESMA conexão: sem o patch o `-226` é garantido; com ele, não deve aparecer. Custo: ~1 min.

**Risco.** O `check_errors()` incondicional acrescenta ~39 ms por captura
nativa (01 §4 item 11). É o preço de saber. Nenhuma validação foi enfraquecida.

---

<a id="p0-2"></a>
### P0-2. `arm()` lê de volta o que foi escrito e falha rápido
**Patch `p02_arm_le_de_volta_e_falha_rapido.patch` · risco baixo · esforço baixo · benefício altíssimo**

**Problema e evidência.** 01 §1.2 (a recomendação mais acionável do relatório):
`arm_transient()` (LIST) **lê de volta 9 parâmetros** e recusa divergência
(`ametek_orm.py:1243-1278`); `arm()` (nativo) **não lê nada**. O caminho que verifica é
exatamente o que funcionou nas duas sessões; o que não verifica é o que produziu dado errado em
silêncio.

**Correção ao relatório 01.** O 01 recomenda ler também `FUNCtion:SHAPe?`.
**Não fazer isso**: a docstring de `aguardar_resposta()` documenta, com
evidência de bancada, que `SOURce:FUNCtion:SHAPe?` e `SOURce:MODE?` **não existem como QUERY na
Rev. 5.53** — não respondem nada (perde-se o timeout inteiro) e ainda deixam `-113` na fila,
atribuído ao próximo comando. As consultas seguras são as cinco pedidas: `VOLTage:MODE?`,
`VOLTage:TRIGgered?`, `PULSe:WIDTh?`, `FUNCtion:MODE?`, `SOURce:FREQuency:MODE?`.

**Desenho.** Cada escrita nativa registra `self._transiente_esperado` (um dict
consulta → valor). `arm()` chama `aguardar_idle()` e depois `_conferir_transiente_programado()`,
que compara:

- **strings** por prefixo comum (a Rev. 5.53 responde `FIX`/`PULS`/`STEP`);
- **números** com `TOLERANCIA_READBACK = 0,5 %` — folgado para arredondamento
  do firmware, apertado o bastante para pegar 242 V onde foram pedidos 220 V
  (10 % de diferença).

Divergência ⇒ `InstrumentHardwareError` nomeando o parâmetro, o valor esperado e o valor lido. A
captura é recusada **antes** de virar arquivo rotulado.

`arm()` também ganha `_pista_de_init_ignorado()`: quando o estado não sai de IDLE depois do
`INITiate`, lê a fila de forma tolerante e, se achar `-220 "Init ignored"`, diz isso na mensagem
([AM] p. 129/214; assinatura da classe 05 em 01 §1.3 B5).

**Testes (6 novos).** `arm()` consulta os cinco cabeçalhos e **não** consulta
`FUNCtion:SHAPe?`/`SOURce:MODE?`; `PULSe:WIDTh?` só em modo PULSe; valor preso (242 contra 220)
é recusado com a mensagem certa; `FUNCtion:MODE` residual em LIST é recusado; abreviações do
firmware são aceitas; `-220` aparece na mensagem do timeout.

**Validar na bancada.** É o T1 da sessão de diagnóstico (ver §T1). Se, depois
de p01+p02, alguma classe nativa passar a falhar no readback, **o patch está funcionando**:
aquela captura teria virado dado errado.

---

<a id="p0-3"></a>
### P0-3. Validação FÍSICA pós-captura, independente de mecanismo
**Patch `p05_validacao_fisica_pos_captura.patch` · risco médio-baixo · esforço médio · benefício altíssimo**

**Problema e evidência.** O mecanismo exato de H-NATIVO está **em aberto** (01
§1.2, 02 §(c) lista 7 candidatos). Uma correção que dependa de adivinhar o mecanismo pode falhar
de novo de um jeito novo. O que não depende de mecanismo é conferir o **dado físico**: 01 §4
itens 1–3 mostram que os defeitos eram todos visíveis na própria captura (127 V onde se esperava
220; sem sag; pulso invertido; THD 0,98 % onde se esperava 5 %).

**Desenho.** Três sondas em `sinais.comparar_fisicamente()`, todas
**insensíveis a alinhamento** (não dependem de H-REF10 estar corrigido):

| sonda | o que mede | pega |
|---|---|---|
| mediana do **envelope rms de meio ciclo** | nível de regime | sessão inteira a 127 V onde 220 V foram programados (razão 0,578) |
| **mínimo e máximo** do envelope | profundidade/altura do evento | SAG que não aconteceu; interrupção que virou elevação |
| **THD por FFT** (piso absoluto de 1 %) | conteúdo harmônico | CSINe não aplicada (5,05 % de referência contra 0,98 % medidos) |
| fator de crista do ciclo mediano (tol. 10 %) | forma grosseira | complemento da THD |

O referencial é a forma **realmente programada**: `ExperimentoWaveform` guarda
`_forma_programada_pu` (já escalada por `limite_pico_bancada_pu`, que reduz a classe 08); as
nativas reconstroem por `gerar()` com um rng novo da mesma seed.

**Por que a THD e não só o fator de crista:** medido offline, uma senoide
clipada a 5 % de THD difere de uma senoide limpa em apenas ~5 % de fator de crista — dentro do
espalhamento de uma medida real (01 mediu 1,4594 num registro onde o ideal é 1,4142). A THD
separa os dois casos por um fator 5.

**Política de dado.** A captura suspeita é **gravada** com
`validacao_fisica: {"ok": false, "motivos": [...]}` no metadata e um `ERROR` no log; no fim da
classe, `ValidacaoFisicaError` (subclasse de `ValueError`, membro de `ERROS_DETERMINISTICOS` ⇒
**sem retry**). Dado marcado é melhor que dado apagado — e é o que permite diagnosticar depois.

Tolerâncias por ambiente: `VALIDACAO_FISICA=0/1`, `VALIDACAO_TOL_ENVELOPE` (0,15),
`VALIDACAO_TOL_THD` (0,20).

**Testes (8 novos).** Captura fiel (ganho de 2 %) passa; tensão base errada,
distúrbio ausente, distúrbio invertido e harmônicos ausentes reprovam com o motivo certo; ruído
de quantização **não** reprova a classe 01; margem extra no registro não reprova; a classe marca
o metadata e levanta sem retry.

**Risco e mitigação.** Falso positivo trava a classe. Mitigado por: tolerâncias
folgadas e configuráveis; piso absoluto na THD; comparação contra a forma programada; e o fato
de os dados ficarem no disco de qualquer jeito. Na primeira sessão física, rodar com
`VALIDACAO_FISICA=1` e observar os motivos antes de confiar cegamente.

---

<a id="p0-4"></a>
### P0-4. Salvamento incremental por captura
**Patch `p03_salvamento_incremental_por_captura.patch` · risco baixo · esforço médio · benefício alto**

**Problema e evidência.** 01 §3 P1 caminho #1: `executar()` só chamava
`_salvar_classe()` **depois** do laço inteiro. Resultado factual: classe 03 com 52 capturas
físicas → 0 arquivos; classe 05 com 29 → 0; classe 08 com 7 boas →
0. As capturas só existiam em memória quando a fonte travou.

**Desenho.** `_salvar_classe()` (assinatura preservada) passa a orquestrar
três peças novas:

- `_iniciar_gravacao_incremental()` — abre `metadata/{id}_{nome}.jsonl.part`;
- `_salvar_captura(...)` — grava os `.npz` da captura (puro + cada `snr_XXdb/`
  + corrente) com escrita atômica `.part → os.replace`, e acrescenta a linha do
  metadata com **`flush()` + `os.fsync()`**;
- `_finalizar_gravacao(parcial: bool)` — promove o jsonl e, **só quando
  `parcial=False`**, roda a limpeza de órfãos.

`executar()` envolve o laço num `try/except BaseException` que chama
`_finalizar_gravacao(parcial=True)` antes de propagar. A limpeza de órfãos
**não** roda numa rodada abortada: uma lista incompleta apagaria arquivos bons
da rodada anterior.

**Testes (3 novos).** Cada captura aparece no disco antes da próxima começar;
falha na captura 3 de 4 preserva 2 `.npz` + metadata com 2 linhas; rodada abortada não apaga
arquivos da rodada anterior.

**Risco.** `fsync` por captura custa alguns ms — irrelevante contra 2–20 s por
captura.

---

<a id="p0-5"></a>
### P0-5. Erro determinístico × intermitente e pré-validação de níveis
**Patch `p04_erro_deterministico_e_pre_validacao_de_niveis.patch` · risco baixo · esforço baixo · benefício alto**

**Problema e evidência.** 01 §3 P1 caminho #4 e "Defeito adicional": a classe
03 a 220 V pede 1,4 pu = **308 Vrms**, acima do teto **físico** de 300 Vrms do manual (02 B46,
[AM] §4.14 p. 84). O código descobria isso na 21.ª captura,
**três vezes**, e terminava com zero arquivos — 52 capturas físicas de desgaste
para um erro conhecido antes de energizar.

**Desenho.**
1. `Bancada.ERROS_DETERMINISTICOS = (ParameterOutOfBoundsError,
   ValidacaoFisicaError)` — sem retry, com log explicando por quê. A lista é
   **deliberadamente estreita**: `ValueError` em geral (ex.: contagem de pontos
   da captura) pode ser intermitente e continua com as 3 tentativas. A rede de
   segurança para `-113`/`-300` esporádicos permanece intacta.
2. `ExperimentoBase.tensao_rms_programada(capture_index)` (padrão `None`),
   implementado em `ExperimentoNativo` a partir de `NIVEIS` × tensão base.
3. `_indices_viaveis(plano)` roda **antes do primeiro comando SCPI**: nível que
   não cabe em `max_voltage_rms`/`max_peak_v` é **pulado** com log claro; se
   nenhum couber, `ParameterOutOfBoundsError` (determinístico ⇒ sem retry).

Resultado para a classe 03 a 220 V: roda 1,1 e 1,2 pu e **pula** 1,4/1,6/1,8, gravando 2 níveis
úteis em vez de 0.

**`VOLT? MAX` (02 §(f) item 15).** [AM] p. 84: "This query will return the
maximum possible rms voltage that can be programmed without exceeding the 425 Volt peak voltage
limitation. This feature can be used to avoid unnecessary error messages during program
execution." **Desenho, não implementado** (exige a fonte): em `configure_safe_baseline`, ler
`VOLT? MAX` uma vez por conexão e usar `min(max_voltage_rms, VOLT? MAX)` como teto da
pré-validação — **nunca** para relaxar `max_voltage_rms`, só para apertar. Vale um ponto do T10.

**Testes (4 novos).** Nível acima do teto é pulado antes de qualquer captura;
classe sem nenhum nível viável falha sem capturar; erro determinístico roda 1 vez; erro
intermitente continua sendo retentado.

**Teste existente ADAPTADO (registrado).** `RemapeamentoNivelTests` criava a
fonte fake com o default de comissionamento (`max_voltage_rms=10`) e tensão base de 127 V — uma
bancada fisicamente impossível, que só passava porque nada validava os níveis. Passou a usar
`max_voltage_rms=300` (o teto do manual). As asserções — quais `capture_index` o laço visita —
**não** mudaram.

---

<a id="p0-6"></a>
### P0-6. Log em arquivo, transcrição SCPI e metadata enriquecido
**Patch `p06_log_de_sessao_transcricao_scpi_e_metadata.patch` · risco baixo · esforço médio · benefício alto**

**Problema e evidência.** 01 §1.3 B6 e §4 item 9: `mestre.py:23` faz
`logging.basicConfig(stream=sys.stdout)`, `cli.py` nunca acrescentou `FileHandler`, `logs/` está
vazio. Quando a fonte travou (01 §3 P3), o único registro do que tinha sido enviado era o
console do operador. E o metadata não grava f0, tensão base, probe, `pre_trigger`, escala
vertical, flags, versão nem IDN — não há como saber, a partir de `resultados/`, que a sessão 2
foi 220 V/50 Hz com `capturas 10`, `margin on`, `diagnostico on` e probe 500×.

**Desenho.**
1. `mestre.configurar_log_de_sessao(pasta)` anexa dois handlers com **flush por
   linha** (`_HandlerComFlush`): `sessao.log` (INFO, tudo) e
   `scpi_transcricao.log` (DEBUG, só o logger `AmetekORM.scpi`, com
   `propagate=False` para não poluir o console).
2. `AmetekMX30._raw_write`/`query` chamam `_transcrever("W"/"Q", comando)` com
   `time.monotonic()`. Payload gigante entra **truncado** em 160 caracteres com
   o tamanho total anotado — um `TRACe:DATA` tem ~11,3 kB e o que importa é
   **que** foi enviado e **quando**.
3. `_contexto_da_sessao()` acrescenta a cada linha de metadata: `f0_hz`,
   `tensao_base_rms`, `probe_tensao`, `pre_trigger_s`, `margin_mode`,
   `diagnostico_mode`, `versao_codigo` (`git describe --always --dirty
   --tags`), `idn_fonte`, `idn_osciloscopio`, `indice_trigger`,
   `escala_vertical_v_div` e `escritas_trace_na_conexao`.
4. `cli._garantir_pasta_sessao()` cria **uma pasta por `run`**: o primeiro
   mantém o nome histórico `sessao_<ts>`, os seguintes ganham `_run02`,
   `_run03`... Fecha 01 §3 P1 caminho #7 (o `run all` sobrescrevendo em
   silêncio o `run 01` anterior, com flags diferentes).

**Testes (5 novos).** O log existe e tem a linha **antes** do fim do processo;
a transcrição registra writes e queries com marcador `W`/`Q`; `TRACe:DATA` sai truncado mas com
o tamanho; o metadata traz as nove chaves novas; dois `run` gravam em pastas diferentes, cada
uma com o seu log.

---

<a id="p0-7"></a>
### P0-7. Trava da fonte: mitigação, registro e recuperação (só desenho)
**Risco médio · esforço médio · benefício alto — NÃO implementado (exige a bancada para validar)**

**Evidência.** 01 §3 P3 e 02 §(d): a fonte parou de responder **por SCPI e pelo
painel** logo depois de `FUNCtion:MODE LIST` na 28.ª captura waveform da conexão (~280
`TRACe:DATA`). O manual confirma o meio (memória **não volátil**, [AM] p. 126, 02 B30),
**exclui** a explicação benigna do painel morto (`SYSTem:REMote` nunca é enviado, 02 §(d) item
5) e acrescenta um gatilho novo: erro **25 "Input buffer full"** com remédio "Break up data in
smaller blocks" — e um `TRACe:DATA` de ~11,3 kB **numa única linha** é exatamente esse padrão.

**Desenho, em quatro peças — nenhuma delas "contorna" a trava:**

1. **Parar de consultar depois do timeout.** Hoje, `_log_diagnostico` gasta
   3 × 5 s de timeout VISA e o `check_errors()` seguinte estoura mais um. Um
   `self._mudo_desde` marcado no primeiro `CommunicationError` faz as consultas
   seguintes falharem **imediatamente** enquanto a janela não expira: menos
   espera, mesma conclusão.
2. **Relatório de trava em disco.** Ao primeiro `CommunicationError` numa
   captura, gravar `sessao_.../trava_<timestamp>.json` com: os últimos N
   comandos de `command_log`, o último ponto de diagnóstico, o contador
   `escritas_trace`, a classe/captura, e os timestamps. Hoje esse material
   morre com o processo.
3. **Salvar o parcial** — já resolvido por P0-4.
4. **Mensagem ao operador, em português e imperativa**: "A fonte parou de
   responder por SCPI. **Confirme fisicamente OUTPUT OFF no painel**, desligue
   a fonte na chave, aguarde 30 s, religue e rode `comm`. **Antes de qualquer
   outro comando**, leia `SYSTem:ERRor?`, `*ESR?` e `STAT:QUES:COND?` — a fila
   pode ter sobrevivido e é a melhor pista do que aconteceu." Isso é o T14.

**Limite de escritas por conexão (graceful stop).** `escritas_trace` já é
contado (P0-6). Acrescentar `AMETEK_MAX_TRACE_WRITES` (sugestão: **200**, contra as 280 do
evento e as ~156 das sessões que sobreviveram): ao atingir, `program_capture` recusa **antes**
de escrever, com mensagem pedindo reconexão. Não é contorno: é reconhecer que a exposição não é
monitorada e parar num ponto conhecido, com todos os dados já no disco. Só ative depois do T9
dar um número melhor.

---

<a id="p1"></a>
## P1 — Precisão e velocidade

<a id="p1-1"></a>
### P1-1. Posição do trigger (H-REF10)
**Patch `p07_posicao_do_trigger_e_indice_trigger.patch` · risco baixo · esforço baixo · benefício alto**

**Problema e evidência.** 01 §0 ACHADO 1, confirmado por 02 A1–A6 com citações
literais: `:TIMebase:REFerence LEFT` põe a referência a **uma divisão** da borda esquerda ([KS]
p. 1337) e uma divisão é 10 % do `RANGe` ([KS] p. 1335); `get_waveform()` fazia `time_axis -=
time_axis[0]`, jogando fora `x_origin` — o único campo da preamble que diz onde o trigger caiu
([KS] p. 1476, com `XREFerence` sempre 0 na p. 1477). Previsão fechada `t_trigger = pre_trigger
+ RANGe/10`, medida em 62 capturas com resíduo zero.

**Escolha entre as alternativas — e por que as DUAS.**

| alternativa | prós | contras |
|---|---|---|
| (A) compensar `POSition` (`-pre + duracao/10`) | uma linha | depende da convenção de `LEFT` continuar valendo; se o firmware mudar, erra em silêncio |
| (A') `REFerence CUSTom` + `LOCation 0.0` ([KS] p. 1337-1338: "0.0 is the left edge") | resolve na origem, sem aritmética | pode não existir em todo firmware |
| (B) gravar `indice_trigger = round(-x_origin/x_increment)` | funciona **mesmo se a convenção mudar**; é medida, não suposição | não corrige o comando: a janela continua deslocada |

**Decisão: (A') com verificação, fallback para (A), e (B) sempre.** O comando é
corrigido na origem *e* a posição efetiva é medida na preamble. Nenhum dos dois sozinho dá as
duas garantias: (A') corrige mas não verifica; (B) verifica mas não corrige. Juntos, o
deslocamento nunca fica desconhecido.

```python
# escreve CUSTom + LOCation 0.0, LÊ DE VOLTA os dois e, se o firmware não
# honrar, cai para LEFT com a divisão compensada — logando WARNING e
# registrando em referencia_horizontal_efetiva (vai para o metadata):
compensacao = 0.0 if self.referencia_horizontal_efetiva == "CUSTOM" else duration_s / 10.0
self.write(f":TIMebase:POSition {(-pre_trigger_s + compensacao) or 0.0:.12g}")
```

O fallback **não é** um contorno silencioso: loga em WARNING, registra qual convenção valeu e
continua conferindo pela preamble.

**Efeito no metadata.** `indice_trigger` (P0-6) passa a valer; o eixo de tempo
devolvido continua começando em zero, então nem o formato do `.npz` nem `_validar_captura()`
mudam.

**Endurecimento junto.** O teste de cobertura do registro estava **chumbado em
0,2 s** (`oscilloscope_orm.py:389`) independentemente de `expected_points`: com `margin on` ele
aceitava um registro curto demais. Passou a exigir `expected_points / 30000` — é um
**fortalecimento**, não uma flexibilização.

**Testes (4 novos).** `CUSTom` + `LOCation 0` enviados e `POSition = -pre`;
fallback compensa a divisão, loga WARNING e registra `LEFT`; `indice_trigger` derivado de
`x_origin = −0,4 s` dá 12000; cobertura mínima acompanha `expected_points`.

**Validar na bancada.** É o T2: `:TRIGger:FORCe` e ler `:WAVeform:PREamble?`.
Previsão com o patch: `x_origin = −pre_trigger` exato (antes: `−(pre + RANGe/10)`).

---

<a id="p1-2"></a>
### P1-2. Nova janela do `margin on` e correção do `analisar_sessao.py`
**Patch `p08_margem_20_50_e_analisar_sessao.patch` · risco baixo · esforço médio · benefício alto**

**Problema e evidência.** Os 400 ms de cada lado do v1.10 foram dimensionados
contra dois números que os relatórios mostraram **falsos**: o "atraso universal de ~20 ms" (é o
offset de referência) e o "pior caso de 540 ms do LIST:REPeat" (com `REPeat 0` o evento é
nominal, 01 §1.3 A4). Resultado: 73 % do registro é descarte (01 §2(i)). E `analisar_sessao.py`
está chumbado em 60 Hz (linha 138) e 127 V (linha 67) — aplicado à sessão 2 (50 Hz/220 V) produz
comparações sem sentido (01 §4 item 8).

**Desenho.** `_calcular_margem` passa a devolver `(antes, depois, total)`:
`MARGEM_ANTES_S = 0,020` e `MARGEM_DEPOIS_S = 0,050` (configuráveis por ambiente). Janela de
**270 ms = 8100 amostras**. Classes com `pre_trigger_s > 0` (02/03/04, PULSe) somam o
pré-trigger **por cima**, como já acontece: `pre_trigger_efetivo = pre_trigger_s + antes/fs` =
80 ms.

`sinais.janela_nominal(registro, indice_trigger, pre_trigger_s, pontos, fs_hz)` passa a ser o
único recorte oficial, usado por `analisar_sessao.py` (e pronto para quem mais precise): começa
em `indice_trigger − pre_trigger_s·fs`, com saturação nas bordas.

`analisar_sessao.py`: `f0` e tensão base saem do **metadata da própria sessão** (`f0_hz`,
`tensao_base_rms`), com fallback 60 Hz/127 V só para metadata antigo — e nesse caso o relatório
**avisa**. O alinhamento passa a ser por `indice_trigger`; sem ele, cai no comportamento
anterior **com aviso explícito de viés de janela/10**. O relatório ganha as colunas `f0_hz`,
`tensao_base_rms`, `indice_trigger` e `validacao_fisica_ok`.

**Testes (3 novos + 4 adaptados).** `janela_nominal` desconta o pré-trigger e
não estoura o registro; `analisar_sessao` usa o f0 do metadata (correlação
> 0,99 numa sessão de 50 Hz, onde o código antigo comparava contra 60 Hz);
margem = 600/1500 amostras, total 270 ms, cobrindo ≥ 250 ms depois do trigger.

**Testes existentes ADAPTADOS (registrado).** `MargemCapturaTests` (4 testes):
`_calcular_margem` devolve 3 valores em vez de 2 porque a margem deixou de ser simétrica. As
asserções continuam as mesmas em natureza (margin off = janela nominal; margin on = folga dos
dois lados, **dentro dos dois tetos** de 60000 e de ~32,3 k pontos); só os números mudaram, de
400/400 ms para 20/50 ms.

**Dependência.** Aplicar **depois** do p07. Sem a correção da posição do
trigger, 20/20 ms trunca o evento em 4 ms (01 §2(i), tabela).

---

<a id="p1-3"></a>
### P1-3. `RAW`/`MAXimum` e o fim do `np.interp` (só desenho)
**Risco médio · esforço médio · benefício alto — NÃO implementado**

**Evidência.** 02 A8 e §(b) item 2: o teto de ~32,5 kpts **não é da aquisição**,
é do modo de transferência. `:WAVeform:POINts:MODE NORMal` devolve o
*measurement record* ([KS] p. 1458) e é escrito **duas vezes**
(`configure_acquisition:211` e `get_waveform:328`), anulando o `RAW` de `initialize_safe:111`.
`RAW`/`MAXimum` entrega até 4.000.000 de pontos (p. 1459) e **as três pré-condições já são
satisfeitas** depois da `:SINGle` (parado, `TIMebase:MODE MAIN`, `ACQuire:TYPE NORMal`). O
`np.interp` de ~32,5 k → 30 k destrói a quantização (01 §4 item 14: 15 000–18 800 níveis
distintos onde 8 bits dariam ≤256) e interpola linearmente notches de 100 µs e o impulso de 50
µs da classe 08 — justamente os mais afetados.

**Desenho.** `configure_acquisition`/`get_waveform` passam a `MAXimum`, leem
`:WAVeform:POINts? MAXimum` e a preamble; se `x_increment` já for exatamente 1/30000, dispensam
o `np.interp`; senão, **gravam o bruto num `.npz` paralelo** (`bruto/{nome}.npz` com `fs_hz`
real) e mantêm a versão reamostrada como hoje. Todas as validações permanecem (formato,
contagem, `hole=0`, faixa, taxa mínima).

**Por que só o desenho:** o número de pontos de uma `:SINGle` real em `MAXimum`
é desconhecido (o T3 mede em 1 minuto, com risco zero — é só leitura). Mudar o tamanho de todas
as capturas sem esse número é trocar um problema conhecido por um desconhecido. **Faça o T3
primeiro.**

**Guard de clipping — não mexer, medir primeiro.** 02 A23/§(b) item 10: a
convenção "1 = clipped low, 255 = clipped high" **não existe** no guia (só `0 = hole`, [KS] p.
1448), e `get_waveform()` pode estar descartando capturas boas. **A proposta é o teste T13, não
a mudança**: sobre as capturas já salvas, contar quantas amostras encostam no trilho (|v| ≥
3,969 × escala). Se der zero, o guard nunca descartou nada e pode ficar como está; se der mais
que zero, aí se discute — com dado, não com suposição. O guard **não foi enfraquecido em nenhum
patch**.

---

<a id="p1-4"></a>
### P1-4. Velocidade e exposição da Flash (só desenho, com números medidos)
**Risco médio · esforço médio · benefício alto — NÃO implementado**

**Evidência.** 01 §3 P2: 19,64–20,42 s por captura waveform (mediana 19,73 s),
metade transferência e metade `time.sleep(1.0)`. 02 §(b) item 4: a espera de 3 s por
`TRACe:DEFine` é **6× a documentada** (500 ms, [AM] p. 127) e a de 1 s por `TRACe:DATA` **não é
exigida em lugar nenhum do manual**. 02 B31: bloco binário **não existe** (`-168 "Block data not
allowed"`) — essa ideia do 01 está morta.

**Medições que fiz offline, nesta análise** (a 50 Hz, 10 ciclos por captura):

| ideia | medida | ganho |
|---|---|---|
| **usar `SINusoid` do catálogo para ciclos de seno puro** | **77 de 130 ciclos (59 %)** das 13 classes waveform são seno puro (correlação > 0,99995) | 59 % menos `TRACe:DATA` **e** 59 % menos gravação em Flash |
| **deduplicar ciclos idênticos por hash** | 53 formas únicas em 70 ciclos (classes 06–20 amostradas) | mais 24 % onde o seno puro não se aplica |
| **`%.8g` → `%.5g`** | pior erro **5,0 × 10⁻⁶ pu** = **0,16 LSB** de um DAC de 16 bits; 11739 → 8698 bytes | 26 % menos bytes: 1,02 s → 0,76 s por TRACe; 10,2 s → 7,6 s por captura |
| **`sleep(1.0)` → confirmado por `SYST:ERR?`** | o manual não exige espera nenhuma após `TRACe:DATA` | até 10 s por captura |

**Desenho.** (a) `program_capture` classifica cada ciclo: seno puro →
`SOURce:LIST:FUNCtion:SHAPe SINusoid` naquele passo, variando só `LIST:VOLTage`; forma repetida
→ reutiliza o **mesmo nome de TRACe** (hash do ciclo normalizado); só o resto vira gravação
nova. (b) `%.5g` com o erro quantificado acima registrado no código. (c) `AMETEK_TRACE_DEFINE_S`
e `AMETEK_TRACE_DATA_S` configuráveis e **medidos** pelos testes T6/T7, em vez de fixos e
adivinhados. (d) contador e limite de gravações por conexão (P0-7).

**Por que só o desenho:** (a) muda a composição do LIST e precisa de uma
captura física para confirmar que o passo `SINusoid` tem a mesma fase e o mesmo dwell que uma
TRACe; (c) depende do T6/T7. O ganho estimado somado é de ~19,7 s para **~5 s** por captura
waveform, com ~60–80 % menos escrita em memória não volátil — que é também a mitigação mais
forte da hipótese 2 do P3.

---

<a id="p1-5"></a>
### P1-5. Diagnóstico honesto (só desenho)
**Risco baixo · esforço baixo · benefício médio**

1. **Renomear/inverter `transiente_ativo`** (02 B25: [AM] Tabela 7-2 p. 169, bit 3 = TRANS =
   "Transient is **completed**"): o campo está invertido, `True` em repouso é o correto, e por isso
   nunca discriminou nada (01 §1.3 B1: 1042/1043). Virar `transiente_concluido_bit`; para saber se
   um transiente está **em curso**, `TRIGger:STATe? == BUSY` (p. 132, §7.7 p. 173).
2. **Tirar `MEAS...` de perto do `*TRG`** (02 B38/B39): o manual prescreve `MEAS:VOLT:AC?;*WAI` e
   avisa que as medidas vêm de um buffer de 4096 pontos — logo após um transiente a resposta pode
   ser **anterior** a ele. No ponto `apos_trigger`, medir só `TRIG:STATe?`; nos demais, usar a
   forma prescrita.
3. **Ponto `apos_abort`** entre o `ABORt` e o `*CLS` de `program_capture()`: uma linha que decide
   H-ZERO-LIST sem risco (T4/T5; 02 B19 mantém a hipótese aberta pelo manual).
4. **`STATus:OPERation:EVENt?`** (02 §(f) item 14): registrador que "latches any condition ...
   cleared when read". Com o bit 3 = "transiente concluído", **é o detector de conclusão que o
   projeto queria** e que o `:COND?` não dá.
5. **`OUTPut:TTLTrg:SOURce EOT`** e **`LIST:TTLTrg`** (02 §(f) itens 12-13): pulso no fim do
   transiente e por passo de lista. `LIST:TTLTrg` tornaria o recorte offline trivial e independente
   de H-REF10. Exigem um 2.º canal no BNC; experimento dedicado, não mudança na bateria.
6. **Medir a duração do evento pelo DADO**, não por timestamps: com `margin on` a medida por
   timestamp está saturada no pós-trigger do osciloscópio e não discrimina nada (01 §1.3 B2). Com
   `indice_trigger` (P1-1) e o envelope (P0-3) ela sai do registro, com resolução de meio ciclo.

---

<a id="p2"></a>
## P2 — Higiene

| # | item | evidência | proposta |
|---|---|---|---|
| H1 | **`VOLTage:HIGH`: rms ou Vp?** | 02 B47/§(b) item 11: [AM] p. 109 diz "maximum **rms** voltage ... Unit: V (rms voltage)"; o projeto trata como Vp | **NÃO mudar o limite.** Só o **teste T12** (saída OFF: `VOLT:HIGH 200` → `VOLT 250` → `SYST:ERR?`). Se o firmware seguir o manual, o teto efetivo está ~1,41× mais alto do que o projeto acredita — mas trocar a unidade sem medir seria afrouxar um limite de segurança com base num manual que já se contradiz em outros pontos (ver 02 B41) |
| H2 | **`OscChannel.display` getter com `KeyError`** | 01 §4 item 13 | `values={True:"1",False:"0"}` com resposta parseada como float: trocar por `cast=bool` / `values={True:1,False:0}`. Duas linhas, sem efeito em hardware |
| H3 | **Classe 08 a 220 V perde o sentido** | 01 §4 item 5: `limite_pico_bancada_pu()` = 1,203 pu ⇒ transiente de +0,20 pu, e `set capturas 10` gera `linspace(1,200; 1,203; 10)` — 0,3 % de variação com 10 reescritas de TRACe cada | A classe deve **recusar** rodar quando `limite_pico_bancada_pu() − 1` for menor que ~10 % da amplitude especificada, com log claro: "08/TRANSIENT não é representável a 220 V; rode a 127 V". Encaixa em `_indices_viaveis` (P0-5) |
| H4 | **Classe 19 sem resolução vertical** | 01 §4 item 6: classes nativas nunca chamam `set_vertical_scale`, então 19 herda a escala da 17 (~89,6 V/div ⇒ 2,8 V/LSB) e o offset programado vale **2 LSB** | `ExperimentoNativo._preparar_acquisicao_real` já chama `scope_scale_v()` quando definido: **definir `scope_scale_v()` na classe 19** (pico nominal × 1,15). Não resolve a resolução do offset (é 8 bits), mas tira o fator 3 de escala desperdiçado |
| H5 | **`set capturas N` em classe com nível inviável** | P0-5 | resolvido: o nível é pulado, não a classe |
| H6 | **`:EXTernal:RANGe` é decorativo** | 02 A20/§(b) item 9: [KS] p. 456 "provided for product compatibility"; quem manda é `:EXTernal:PROBe` | A validação `abs(level_v) >= actual_range` lê um valor que o projeto não controla. Manter o write (inofensivo) e trocar a validação por uma contra `:EXTernal:PROBe?`, ou documentar que ela é informativa |
| H7 | **Memória cai pela metade com CH1+CH2** | 02 A11: [KS] p. 320 | Confirmar que `disable_channel(2)` roda quando `CAPTURE_CURRENT=0`. Uma linha de verificação no preflight |
| H8 | **Sobre-pico de 18–22 % nas bordas** | 01 §4 item 7; 02 §(f) item 16: o projeto programa `SOURce:VOLTage:SLEW MAXimum` | `LIST:VOLTage:SLEW` poderia atenuar, **mas** [AM] p. 217 erro 17 "Slew time exceed dwell" é o risco imediato com dwell de 1 ciclo. **Não mexer**: medir primeiro o sobre-pico com `indice_trigger` correto (P1-1) e só então decidir |
| H9 | **`*OPC?` "não funciona nesta Rev."** | 02 B23: o manual documenta `*OPC?` como suportado ([AM] §7.7 p. 173) | Registrar como **desvio de firmware** (não como "o manual não tem") e confirmar no T11. Se responder, vários `sleep` podem virar espera determinística |

---

<a id="ideias"></a>
## As três ideias do dono: decisão final

### (i) Reduzir a margem "antes" para ~20 ms — **ACEITA**
### (iii) Margem para capturar um pouco depois do fim — **ACEITA**

**Valores finais: 20 ms antes, 50 ms depois. Janela de 270 ms (8100
amostras).** Implementado no `p08`.

Justificativa: o conteúdo programado termina em `trigger + 200 ms`; o fim de evento mais tardio
medido nas duas sessões é **116,7 ms** (01 §2(i)); 50 ms depois cobrem o retorno ao regime e o
sobre-pico de transição; 20/20 ms truncaria o evento em 4 ms. Descarte cai de 73 % para ~26 % do
registro, e a folga contra o teto real de ~32,3 k pontos do modo AUTO volta a ser enorme.

**Condição inegociável: só depois do `p07`.** Enquanto o trigger cair em
`pre_trigger + janela/10`, qualquer margem pequena vira recorte errado.

**Classes com `pre_trigger_s > 0` (02/03/04, PULSe):** a margem "antes" é
**somada** ao pré-trigger, não o substitui — `pre_trigger_efetivo = 0,060 +
0,020 = 80 ms`, janela de 270 ms, pós-trigger real de 190 ms. Cabe o pulso de 60 ms com folga de
3×. Isso já é o comportamento do código (`executar()` soma os dois); o patch só troca o valor da
margem.

**Classes de estado permanente (05 CSINe, 18 LIST:FREQ, 19 DC offset):** 270 ms
é folgado — o estado está presente no registro inteiro. Para a 18, o último passo **persiste**
(01 §1.3 A5, 02 B4): 250 ms depois do trigger cobrem os 200 ms de lista e 50 ms do patamar
final, que é o dado interessante.

**Não ir abaixo disto** sem refazer a medida. Os valores são constantes de
classe (`MARGEM_ANTES_S`/`MARGEM_DEPOIS_S`), sobrescrevíveis por ambiente para experimentação —
mas o default é o medido.

### (ii) Zerar a saída após o fim do experimento — **RECUSADA como comportamento padrão; aceita como opção `opt-in` restrita**

**Por que recusar o padrão** (concordo com o 01 §2(ii), e o manual reforça):

1. **Já acontece por acidente.** A saída fica em ~0,06 V durante os ~19,7 s de
   `program_capture()` de cada classe waveform (01 §1.3 B3). Entre capturas a
   saída **já** está praticamente zerada.
2. **Destrói o pós-evento das classes nativas.** 02 B6, [AM] p. 109: depois de
   um PULSe "the voltage is changed ... **for a duration determined by the
   pulse commands**" e volta ao nível imediato. Esse retorno **é** a linha de
   base da medida. Zerar depois apaga metade da informação do rótulo.
3. **Não há garantia de que funcione por escrita imediata.** 01 §1.2:
   `SOURce:VOLTage 220` de `recuperar_estado_seguro()` **não** mudou a saída em
   três ocasiões da sessão 2. Um "zerar depois" que às vezes não zera é pior
   que não zerar.
4. **Acrescenta um ciclo 0→V por captura** — exatamente o tipo de estresse que
   é candidato na análise da trava (01 §3 P3 hipótese 3).
5. **O problema real que (ii) tentava resolver — "saber onde o experimento
   termina" — é resolvido de graça por metadata**: `indice_trigger`,
   `pre_trigger_s`, `f0_hz` e o envelope da P0-3 dão o fim do evento com
   resolução de meio ciclo, sem tocar em hardware.

**Como fazer, se o dono ainda quiser, de forma segura** (nesta ordem de
preferência):

- **(ii-a) Marcador, não zeramento — `OUTPut:TTLTrg:SOURce EOT`** ([AM] p. 77,
  02 §(f) item 13): pulso TTL no **fim** do transiente. Responde à pergunta
  "onde termina?" em hardware, **sem mexer na saída**. É a alternativa que eu
  recomendo se algo tiver de ser feito. Exige o segundo canal do osciloscópio
  no BNC.
- **(ii-b) Passo final de LIST a 0 V, só para classes LIST**, ativado por
  `ZERAR_APOS_EVENTO=1`: acrescenta um 11.º passo com `LIST:VOLTage 0` e
  `LIST:DWELl 0,001` (o mínimo do manual, [AM] p. 91). Bônus documentado: 02
  B16 mostra que um ponto final curto é justamente a **mitigação prescrita do
  falso IDLE** ([AM] p. 132). Nunca para classes nativas (PULSe/STEP/CSINe), e
  nunca dentro da janela de aquisição — o passo entra **depois** dos 200 ms
  nominais, dentro dos 50 ms de margem, e o metadata registra
  `zeramento_apos_evento: true` para que a análise offline o ignore.
- **(ii-c) `OUTPut:STATe OFF` entre classes** — **não**. Derruba o relé a cada
  classe, viola "a saída fica ligada durante toda a bateria"
  (`energize_baseline`, alinhado ao exemplo do cap. 6.4.2 do manual) e
  multiplica o chaveamento a quente.

---

<a id="diagnostico"></a>
## Sessão de diagnóstico de bancada (≤ 45 min, saída OFF ou 5 V, sem EUT)

Script proposto: **`logica/bench_diag_scpi.py`** — só desenho e rascunho abaixo; **não foi
executado e não deve ser executado por nenhum agente**. Roda os testes T1–T14 dos relatórios
01/02 em ordem de risco crescente, para ao primeiro sintoma, grava tudo em
`logs/bench_diag_<ts>.log` + um JSON com as respostas cruas.

**Regras de segurança do script (invariantes):** nunca energiza acima de 5 Vrms;
todo bloco que energiza pede a confirmação digitada `ENERGIZAR-DIAGNOSTICO` (case-sensitive,
**jamais automatizada**); para ao primeiro `CommunicationError` e grava o relatório de trava;
reusa `mestre.Bancada.from_env()` e as validações existentes; não toca em `AMETEK_PORT`/baud.

```python
# logica/bench_diag_scpi.py  (RASCUNHO — não executar)
BLOCOS = [
    # (id, energiza?, minutos, função)
    ("T10", False, 1, t10_identidade),        # SYST:CONF?, *IDN?, *OPT?  -> Series I ou II
    ("T11", False, 1, t11_opc),               # *OPC? isolado, timeout curto
    ("T2",  False, 2, t2_referencia),         # só osciloscópio: REF CUSTom/LOCation + FORCe + PREamble
    ("T3",  False, 2, t3_raw),                # POINts:MODE MAXimum + POINts? MAXimum (só leitura)
    ("T12", False, 2, t12_voltage_high),      # VOLT:HIGH 200 -> VOLT 250 -> SYST:ERR?
    ("T6",  False, 5, t6_trace_define),       # TRACe:DEFine + CATalog? em laço, mede o mínimo
    ("T7",  False, 5, t7_trace_data),         # TRACe:DATA sem espera -> SYST:ERR?; degraus 1,0/0,3/0,1/0
    ("T8",  False, 3, t8_buffer),             # mesma TRACe em %.8g (11,3 kB) e %.5g (8,7 kB); SYST:ERR? nos dois
    ("T1",  True,  5, t1_h_nativo),           # 5 V: readback de VOLT:TRIG/MODE antes e DEPOIS de um transiente
    ("T5",  True,  2, t5_abort),              # 5 V: _log_diagnostico("apos_abort") entre ABORt e *CLS
    ("T4",  True,  3, t4_pre_trigger_fill),   # 5 V: FORCe imediato vs tardio, comparar x_origin
    ("T9",  False, 12, t9_flash),             # 300 TRACe:DATA sobre UM nome, SYST:ERR? a cada 25
]
```

**T13 e T14 não entram no script:** T13 é **offline** (sobre os `.npz` já
salvos) e T14 é um **procedimento do operador** ao religar a fonte.

### Regras de decisão (resultado X ⇒ ação Y)

| teste | pergunta | resultado | ação |
|---|---|---|---|
| **T1** | H-NATIVO: a escrita é ignorada? | `VOLT:TRIG?` devolve o valor ANTIGO depois de um transiente, e/ou aparece erro **19** | candidato 1 confirmado ⇒ o `aguardar_idle()` do `p01` é a correção; acrescentar espera por `STAT:OPER:EVEN?` bit 3 |
| | | `FUNC:MODE?` devolve `LIST` numa classe nativa | candidato 2 confirmado ⇒ `p01` já corrige |
| | | prefixo `SOURce:` faz diferença | correção de uma linha em `trigger_step`/`trigger_pulse` (02 §(c) item 6 considera improvável) |
| | | tudo lê de volta certo e mesmo assim a saída erra | mecanismo ainda aberto ⇒ a **P0-3** é o que segura a validade dos dados; abrir chamado com o fabricante |
| **T2** | H-REF10 no firmware | `x_origin = −pre_trigger` (com `p07`) | confirmado; seguir para o `p08` |
| | | `x_origin = −(pre + RANGe/10)` | o firmware ignorou `CUSTom` ⇒ o fallback do `p07` assume (já loga WARNING) |
| **T3** | ganho do `RAW`/`MAXimum` | `POINts? MAXimum` ≫ 32,5 k | implementar P1-3 e tirar o `np.interp` |
| | | ≈ 32,5 k | o teto é da aquisição; manter `NORMal` e **documentar** |
| **T6/T7** | as esperas de Flash são necessárias? | `SYST:ERR?` limpo sem espera | reduzir em degraus e tornar configurável (P1-4) |
| | | erro em espera curta | manter o valor mínimo que passou, **registrado com o número medido** |
| **T8** | `TRACe:DATA` estoura o buffer? | erro **25** com 11,3 kB e limpo com 8,7 kB | `%.5g` deixa de ser otimização e vira **correção** (P1-4) |
| **T9** | desgaste de Flash | falha antes de 300 escritas | ativar `AMETEK_MAX_TRACE_WRITES` com margem (P0-7) e priorizar P1-4 |
| | | 300 sem falha | hipótese 2 do P3 enfraquece; suspeita volta para a transição `FUNCtion:MODE LIST` |
| **T10** | Series I ou II | Series II | teto de 100 pontos de lista; `TRIG:STATe? → WTRIG` coerente |
| **T11** | `*OPC?` responde? | sim | trocar `sleep` por `*OPC?` onde couber e corrigir a documentação interna |
| **T12** | `VOLT:HIGH` rms ou Vp? | 250 V **recusado** com `HIGH 200` | é **rms** ⇒ abrir tarefa própria para revisar `configure_safe_baseline` (nunca afrouxar sem revisão) |
| | | 250 V aceito | é Vp (comportamento atual) ⇒ nada a fazer |
| **T13** | o guard de clipping descarta dado bom? | > 0 amostras em 1/255 em capturas boas | discutir o guard **com o número na mão** |
| | | zero | manter como está |
| **T14** | a trava é reprodutível | `SYST:ERR?`/`*ESR?` ao religar trazem algo | é a melhor pista existente; anexar ao relatório de trava |

---

<a id="nao-fazer"></a>
## O que NÃO fazer

1. **Bloco binário em `TRACe:DATA`** — não existe (02 B31: `-168 "Block data not allowed"`).
2. **Confiar em `*WAI` para esperar transiente** — [AM] §7.7 p. 173 diz "except for transients" e
   §5.14 p. 142 diz que "**\*WAI can be aborted by sending any other command**", que é literalmente
   o que `arm()` faz ao emendar `INITiate:IMMediate`. O que funciona é `TRIG:STATe?`
   (`aguardar_idle`, P0-1) mais o readback (P0-2).
3. **Consultar `SOURce:FUNCtion:SHAPe?` ou `SOURce:MODE?`** na Rev. 5.53 — não existem como QUERY,
   devolvem `-113` e o erro é atribuído ao comando seguinte (correção ao 01 §6 item 1).
4. **Mexer nos limites inegociáveis** — `max_voltage_rms`, `max_peak_v`, `max_current_a`, porta,
   baud, `validate_bench_configuration()`, e qualquer validação de IDN, timeout, tamanho de
   waveform, `assert_no_errors`/`check_errors`. Nenhum patch aqui faz isso.
5. **Trocar o guard de clipping por suposição** — medir (T13) primeiro.
6. **Mudar `VOLTage:HIGH` de Vp para rms sem o T12** — afrouxaria um limite de segurança com base
   num manual que se contradiz em outros pontos.
7. **Empilhar `sleep` novo ou retry cego.** Onde há espera fixa (`TRACe:DEFine`/`DATA`/`DELete:ALL`),
   o caminho é **medir** (T6/T7) e tornar configurável, não aumentar por precaução.
8. **Automatizar qualquer confirmação digitada pelo operador.** O script de diagnóstico continua
   pedindo `ENERGIZAR-DIAGNOSTICO`.
9. **Ampliar o que conta como "falha recuperável"** — `executar_bateria` continua abortando sem
   retry em `CommunicationError`/`FalhaFatalDeInstrumento`. O `p04` só **reduz** o retry.
10. **Rodar a bateria completa a 220 V antes de T1** — metade das classes produz dado errado de
    qualquer forma (01 §5 T5).
11. **Persistir o cache de TRACe entre processos** sem antes resolver como
    `AMETEK_CLEAR_USER_WAVEFORMS=1` o invalidaria (limite inegociável do `AGENTS.md`).
12. **Zerar a saída por padrão depois do evento** — ver a decisão sobre a ideia (ii).
