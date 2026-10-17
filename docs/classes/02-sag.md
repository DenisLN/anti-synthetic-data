# Classe 02: SAG

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 (127 V/60 Hz e 127 V/50 Hz, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` sorteio de início, duração e fase; 230 V/50 Hz {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-05`

| Campo | Valor |
|---|---|
| Número e nome | 02 SAG (afundamento de tensão) |
| Arquivo | `experimentos_nativos/02.py`, classe `Experimento(ExperimentoNativo)` |
| Mecanismo na bancada | **nativa**: PULSe ({scpi}`VOLTage:MODE` `PULSe`, {scpi}`VOLTage:TRIGgered`, {scpi}`PULSe:WIDTh`) |
| `capturas_padrao` | 1 (herdado, [mestre.py:1564](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1564)); a classe tem 5 níveis, e **sem `set capturas` só o nível 0 roda** |
| Sorteio de posição | I D F (início, duração e fase) |
| Depende do perfil? | sim: os cinco níveis mudam (`sag_niveis`) |
| Condições já medidas | 127 V/60 Hz e 127 V/50 Hz (1 captura, nível 0,1 pu); 230 V/50 Hz foi pulada |

## 1. Em uma resposta

**Pergunta:** o que a classe 02 produz? **Resposta:** uma senoide que **cai a um nível $\ell$ entre 0,1 e 0,9 pu por um trecho sorteado dos 200 ms e volta ao normal**; na fonte, o afundamento é um PULSe nativo que a AMETEK aplica sozinha a partir do `*TRG`.

Estado: o PULSe foi medido em 07/10/2026 e o mínimo do envelope bateu com o nível pedido; o sorteio de posição, a fase de disparo em passos de 0,1° e a largura do pulso sorteada nunca foram medidos ({ref}`P-05 <p-05>`), e nenhum dado existe com o código da v1.15 ({ref}`P-01 <p-01>`).

## 2. O fenômeno e a norma

Afundamento de tensão (*sag*): redução do valor rms da tensão por um intervalo curto, geralmente por falta ou partida de carga. A Tabela 2 da IEEE Std 1159-2019 o classifica no item 2.1.1 (instantâneo): **0,1 a 0,9 pu, de 0,5 a 30 ciclos**. O modelo do projeto usa os mesmos limites de amplitude (0,1 a 0,9 pu, perfil `literatura`) e, desde a v1.15, sorteia a duração de meio ciclo (8,3 ms a 60 Hz) até a janela menos dois ciclos (166,7 ms = 10 ciclos a 60 Hz; 160 ms = 8 ciclos a 50 Hz), sempre dentro dos 0,5 a 30 ciclos da norma.

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v(t)=a(t)\,\sin\!\big(2\pi f_0\,(t+\tau)\big),\qquad
a(t)=\begin{cases}\ell & t_0\le t<t_0+d\\ 1 & \text{caso contrário}\end{cases},\qquad
\ell=\texttt{NIVEIS}[\,\text{capture\_index}\bmod 5\,]
$$

$t_0$ (início), $d$ (duração) e $\varphi$ (fase em $t=0$, $\tau=\varphi/(360 f_0)$) vêm do sorteio de posição ({ref}`fórmulas <sorteio-de-posicao>`); sem sorteio valem $t_0=60$ ms, $d=60$ ms e $\varphi=0$ (`INICIO_S` ([02.py:15](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/02.py#L15)) e `DURACAO_S` ([02.py:16](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/02.py#L16))). O nível não é sorteado: é escolhido por `capture_index`, e os cinco valores vêm do perfil ativo (`NIVEIS`, propriedade que lê `perfis.faixa(config, "sag_niveis")`).

```{literalinclude} ../../experimentos_nativos/02.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_nativos/02.py, Experimento.gerar
```

- **Ordem do `rng`:** `gerar()` não consome o `rng` da classe; o sorteio de posição usa um sub-fluxo da mesma seed. O nível depende só de `capture_index`.
- **Parâmetros no metadata:** `sag_pu` (o nível), `inicio_disturbio_s`, `duracao_s`, `fase_graus`.
- **Seed:** `base_seed + 2 · 1 000 000 + indice_global`.
- **Capturas e níveis:** `capturas_padrao` = 1. Com os padrões o plano tem **uma** captura e usa só `NIVEIS[0]` (0,1 pu na `literatura`). Para cobrir os cinco níveis é preciso `set capturas N`: com N ≥ 1 digitado a bancada agrupa **N capturas por nível** (`capture_index = indice_global // N`; `dimensionar_capturas`, [mestre.py:1684-1701](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1684-L1701)), 5 N capturas no total. No simulado os níveis se alternam por `capture_index mod 5`.

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** como a fonte produz o afundamento? **Resposta:** com um PULSe nativo: a saída fica na tensão base, e a partir do `*TRG` cai para $\ell \cdot V_\text{base}$ por `PULSe:WIDTh` segundos e volta sozinha.

Ordem de uma captura (`ExperimentoNativo._capturar_real`, [mestre.py:2936-2983](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2936-L2983); diagrama em {doc}`../scpi/sequencias` §4):

1. `gerar()` sorteia início, duração e fase; `_duracao_sorteada_s` guarda a duração para `largura_do_pulso_s` (`ExperimentoNativo.largura_do_pulso_s`, [mestre.py:2880-2883](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2880-L2883)).
2. {scpik}`:TIMebase:POSition` por captura: `KeysightDSOX4034A.definir_pre_trigger` ([oscilloscope_orm.py:339-354](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L339-L354)) põe `pré-trigger = inicio_disturbio_s + 20 ms de margem` com referência `CUSTom` na borda esquerda (quirk K1); o osciloscópio passa a ver o evento a `inicio_disturbio_s` do trigger.
3. {scpi}`TRIGger:SYNChronize:PHASe` recebe a fase de disparo $\theta = \varphi + 360\,f_0\,t_0 \pmod{360}$, a fase da senoide **no instante do evento** (`ExperimentoNativo.fase_de_disparo_graus`, [mestre.py:2918-2934](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2918-L2934)), em passos de 0,1°, sem leitura de volta.
4. `AmetekMX30.trigger_pulse` ([ametek_orm.py:908-937](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L908-L937)): {scpi}`TRIGger:STATe?` até `IDLE`; {scpi}`FUNCtion:MODE` `FIXed` e {scpi}`SOURce:FREQuency:MODE` `FIXed`; {scpi}`VOLTage:MODE` `PULSe`; {scpi}`VOLTage:TRIGgered` $\ell \cdot V_\text{base}$ (arredondado ao múltiplo de 0,1 V mais próximo, `quantizar_tensao_rms`, [ametek_orm.py:868-874](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L868-L874)); {scpi}`PULSe:WIDTh` com a duração; {scpi}`SYSTem:ERRor?` (erro 19 recusa a captura).
5. Armamento e disparo como na {doc}`01-normal` (passos 4 a 7 da seção 4), com um readback a mais em `arm()`: {scpi}`PULSe:WIDTh?` ([ametek_orm.py:1782-1821](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1782-L1821)).

**Por que a fase de disparo importa.** O `*TRG` age na fase programada, não no instante do comando (quirk A18). Antes da v1.12 a fonte disparava sempre em 0° e, com `pre_trigger_s` = 60 ms = 3,6 ciclos a 60 Hz, a senoide saía defasada 216° do modelo: correlação $-0{,}78$ contra `gerar()` e 0,999 contra o modelo com a fase corrigida (sessão de 30/09/2026 14:44).

**O PULSe não eleva a tensão imediata.** `trigger_pulse` só programa o nível transiente; sem uma classe STEP antes, o "antes/depois" do pulso ficaria no nível de segurança (0 V). Por isso `Bancada.assegurar_tensao_base` ([mestre.py:1398-1425](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1398-L1425)) faz um STEP real à base antes de um `run 02` isolado.

**Janela e margem.** A classe declara `pre_trigger_s` = 0,060 ([02.py:13](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/02.py#L13)); com o sorteio ligado, o pré-trigger da captura é o `inicio_disturbio_s` sorteado. O registro físico tem 20 ms antes e 50 ms depois da janela ({doc}`../medicao`).

## 5. Parâmetros por perfil

| Componente em `perfis.py` | `norma` | `literatura` (padrão) | `fronteira` |
|---|---|---|---|
| `sag_niveis` | níveis 0,15 / 0,325 / 0,5 / 0,675 / 0,85 | níveis 0,1 / 0,3 / 0,5 / 0,7 / 0,9 | níveis 0,1 / 0,9 |

Os níveis programados a cada tensão (a fonte só aceita múltiplos de 0,1 V em `VOLTage:TRIGgered`):

| Nível (pu) | Perfis que o usam | Programa a 127 V (V rms) | Programa a 230 V (V rms) | Cabe no limite de 300 Vrms a 230 V? |
|---|---|---|---|---|
| 0,1 | `literatura`, `fronteira` | 12,7 | 23,0 | sim |
| 0,15 | `norma` | 19,0 | 34,5 | sim |
| 0,3 | `literatura` | 38,1 | 69,0 | sim |
| 0,325 | `norma` | 41,3 | 74,8 | sim |
| 0,5 | `norma`, `literatura` | 63,5 | 115,0 | sim |
| 0,675 | `norma` | 85,7 | 155,2 | sim |
| 0,7 | `literatura` | 88,9 | 161,0 | sim |
| 0,85 | `norma` | 108,0 | 195,5 | sim |
| 0,9 | `literatura`, `fronteira` | 114,3 | 207,0 | sim |

*Fonte:* `AmetekMX30.quantizar_tensao_rms` aplicado a $\ell \cdot V_\text{base}$ (cálculo offline de 2026-10-16). O perfil `fronteira` tem só os dois extremos (0,1 e 0,9 pu), alternados por `capture_index`. Os níveis intermediários da `norma` (0,325 e 0,675) são escolha de implementação: espaçamento uniforme dentro da faixa, que a norma fixa só nos extremos ({doc}`../perfis`).

## 6. Limites físicos e fator de extremo

O afundamento só reduz a tensão, então o limite que importa é o da **volta** do afundamento: a saída sobressai ao voltar à base (quirk A20). O pico programado é o da senoide base (1 pu); o extremo previsto é pico × fator × 1,10, contra o teto de 415,8 V. `ExperimentoNativo.tensao_rms_programada` ([mestre.py:2903-2911](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2903-L2911)) também informa à pré-validação o rms do nível (12,7 V a 127 V no nível 0,1 pu), que é conferido contra 300 Vrms e `max_peak_v`.

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,164 | 1 | 179,6 | 230,0 | 415,8 | 100 % | 1/1 rodam |
| 127 V/50 Hz | 1,063 | 1 | 179,6 | 210,0 | 415,8 | 100 % | 1/1 rodam |
| 230 V/50 Hz | sem entrada | 1 | 325,3 | 380,3 | 415,8 | 100 % | 1/1 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 1 | 311,1 | 504,8 | 415,8 | 100 % | 0/1 rodam, 1 pulada(s) |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, rodado em 2026-10-16 sobre `fa82f49` (perfil `literatura`, seed 20260827, nível 0 apenas, sorteio ligado). Os fatores medidos diferem por frequência: 1,164 a 127 V/60 Hz contra 1,063 a 127 V/50 Hz; a regra por frequência (v1.15) faz a 230 V/50 Hz usar o fator da tabela de 127 V/50 Hz, de modo que 325,3 V × 1,063 × 1,10 = 380,3 V e a 02 **roda** a 230 V/50 Hz (em 07/10 foi pulada: ainda valia a regra do maior fator de todas as tabelas, 1,475). A 220 V/60 Hz (sem tabela) é pulada: 311,1 V × 1,475 × 1,10 = 504,8 V > 415,8 V ({ref}`P-21 <p-21>`). Classes nativas **não reduzem** o distúrbio (o nível é o parâmetro discreto da classe): se não cabe, a captura é pulada antes de qualquer SCPI.

## 7. Validação física

Sondas e tolerâncias: mediana, mínimo e máximo do envelope (15 %), THD (20 % relativos, piso de 1 %) e fator de crista (10 %, com o fator calibrado da classe); ver {ref}`as tolerâncias <validacao-fisica-tolerancias>`. Para a 02 o **mínimo do envelope** é a sonda que pega um afundamento que não aconteceu: o esperado é $\ell/\sqrt{2}$ (0,0707 pu para $\ell$ = 0,1).

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,703 / 0,707 | 0,065 / 0,071 | 0,714 / 0,707 | 0,042 / 0,041 | 1,463 / 1,414 |
| 127 V/50 Hz | 0,700 / 0,707 | 0,062 / 0,071 | 0,716 / 0,707 | 0,004 / 0,000 | 1,464 / 1,414 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`). O mínimo do envelope medido (0,065 e 0,062 pu) contra 0,071 pu esperado mostra o afundamento aplicado. O THD esperado a 60 Hz (4,1 %) não é zero porque, sem sorteio, o degrau do pulso cai a 60 ms = 3,6 ciclos, no meio de um ciclo, e injeta harmônicos; a 50 Hz o degrau cai em 3 ciclos exatos, no cruzamento por zero, e o esperado é 0,0 % (explicação por construção do modelo, conferida offline; o medido, 4,2 % e 0,4 %, acompanha). Captura reprovada é gravada com `ok=false`.

## 8. As três versões e a correlação esperada

A `programada` da 02 é a senoide com $a(t)$ no nível **quantizado em 0,1 V** (2,1813 V vira 2,2 V), no início e na duração do metadata (`sinais.forma_programada_nativa`, [sinais.py:624-683](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L624-L683)). Fora do pulso, a base. Não inclui o toque da fonte na volta do afundamento: isso é a diferença programada × medida.

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 1,000 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,997–0,999 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,997–0,999 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,999 / 0,999 | 0,997 / 0,996 | — |
| modelo × medida | 0,999 / 0,999 | 0,997 / 0,996 | — |

Causa de a classe ficar abaixo de 0,90, quando fica: —

A 02 é a mais bem comportada das nativas (0,997–0,999 em 07/10): o evento é grande e a métrica só vê o que o evento acrescenta. A correlação modelo × programada é 1,000 nas quatro células de frequência e sorteio.

## 9. Quirks e armadilhas

- **A14:** escrever durante um transiente é aceito e ignorado (erro 19); por isso `aguardar_idle` precede toda escrita e o erro 19 recusa a captura em vez de gravar um dado errado.
- **A12:** `VOLTage:TRIGgered` é truncado a 0,1 V; o nível é arredondado antes de escrever para o readback não divergir (tolerância de 0,5 %).
- **A18:** `*TRG` age na fase de `TRIGger:SYNChronize:PHASe` (corrigido na v1.12, F1).
- **A20:** a volta do afundamento sobressai ~16 % a 127 V/60 Hz (fator 1,164) e ~6 % a 127 V/50 Hz (1,063).
- **A1:** escritas em rajada se perdiam; `PULSe:WIDTh` "preso" era o terceiro comando de uma rajada, não um acoplamento largura-período.
- **K1:** a referência horizontal `LEFT` fica a uma divisão da borda; o pré-trigger usa `CUSTom` + `LOCation 0.0`.
- **Acoplamento:** `forma_programada_nativa` lê `INICIO_S`/`DURACAO_S` por `getattr` e `fase_de_disparo_graus` lê `pre_trigger_s`; mudar um deles muda o que a programada e a fase de disparo entendem como evento ({doc}`../codigo/acoplamentos`).

## 10. Histórico por versão

- **v1.7:** a 02 falhava de forma determinística logo depois da 01 com `-300` no `INITiate:IMMediate`; segundo o CHANGELOG a causa era o `restaurar_forma_e_modo_padrao` mandando `SOURce:VOLTage:OFFSet 0` fora do modo `ACDC` (A10), com a fila de erros não consultada (a divergência desta explicação com o comentário de `arm()` está na {doc}`01-normal`). Também nesta versão `run 02` isolado mediu ~0 V antes e depois do pulso (o PULSe não eleva a tensão imediata): nasceu `assegurar_tensao_base`.
- **v1.10:** o "Bug A": nas classes PULSe o pulso não aparecia em lugar nenhum da janela de 1 s (envelope chapado 1,018–1,062 pu onde deveria cair a 0,1 pu). Hipótese da época: atraso fixo do pulso. A causa mais provável veio na v1.11 (P07), com a referência horizontal `LEFT` a uma divisão da borda (K1); o texto do CHANGELOG não declara qual versão fechou o bug, e em 07/10 o mínimo do envelope da 02 bateu com o nível pedido.
- **v1.11:** H-NATIVO: as sessões de 16/09/2026 mostraram valores errados aplicados em silêncio (a sessão de 220 V saiu a 127 V nas classes 01/02/04); P01 (esperar `IDLE`, neutralizar listas, erro 19) e P02 (readback do transiente); P04: nível inviável é pulado antes de capturar.
- **v1.12:** a rajada de escritas se perdia (N1/N2: `PULSe:WIDTh?` lido 0,0167 depois de escrever 0,06); `VOLTage:TRIGgered` truncado a 0,1 V (N3); fase de disparo (F1).
- **v1.13:** a 220 V as nativas não reduzem o distúrbio (a 03 roda só 1,1 pu); `capturas_padrao` e `set seed`.
- **v1.14:** fatores de extremo por condição; a 230 V/50 Hz a 02 fica pulada (sem tabela).
- **v1.15:** perfis `norma`/`literatura`/`fronteira`; início, duração e fase sorteados; a regra por frequência faz a 02 rodar a 230 V/50 Hz.

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| PULSe aplica o nível pedido (mínimo do envelope) | {bdg-success}`VERIFICADO NA BANCADA` | 127 V/60 Hz e 127 V/50 Hz, 07/10/2026, 1 captura cada |
| `gerar()` e programada de hoje | {bdg-info}`OFFLINE` | fixtures de `gerar()`; correlação modelo × programada 1,000 |
| Sorteio de início, duração e fase; `PULSe:WIDTh` sorteada | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15 |
| Os níveis 0,3 a 0,9 pu na bancada | {bdg-warning}`NÃO VERIFICADO` | as sessões de 07/10 capturaram só o nível 0 (0,1 pu); os outros exigem `set capturas N` |
| 230 V/50 Hz | {bdg-warning}`NÃO VERIFICADO` | pulada em 07/10; hoje roda (previsto 380,3 V) |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
:::

:::{important} Pendência P-05
Sorteio de posição nas nativas: disparo na fase sorteada (sem readback), `:TIMebase:POSition` por captura, `PULSe:WIDTh` sorteada e `pre_trigger_desvio_amostras` nunca foram medidos; os limiares de `verificar_sessao_bancada.py` (2 ms, 2 amostras) são propostas. Fecha com: bancada. Prioridade MÉDIA.
:::

## 12. Como o código da classe funciona

| Símbolo | Recebe | Devolve | Quem chama |
|---|---|---|---|
| `Experimento.NIVEIS` ([experimentos_nativos/02.py:19-21](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/02.py#L19-L21)) | nada (propriedade) | `perfis.faixa(self.config, "sag_niveis")`, tupla de 5 níveis (ou 2 em `fronteira`) | `gerar`, `configurar`, `ExperimentoBase.total_niveis` ([mestre.py:1675-1682](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1675-L1682)) e `ExperimentoNativo.tensao_rms_programada` ([mestre.py:2903-2911](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2903-L2911)) |
| `Experimento.gerar` ([experimentos_nativos/02.py:23-30](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/02.py#L23-L30)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"sag_pu", "inicio_disturbio_s", "duracao_s", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.configurar` ([experimentos_nativos/02.py:32-35](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/02.py#L32-L35)) | `capture_index` | `{"sag_pu": nível}` | a linha [mestre.py:2972](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2972) de `ExperimentoNativo._capturar_real` |

- `gerar` chama `self.sortear(rng, f0, inicio_legado_s=INICIO_S, duracao_legada_s=DURACAO_S, duracao_variavel=True)` (`ExperimentoBase.sortear`, [mestre.py:1669-1673](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1669-L1673)), multiplica por `nivel` a máscara `sinais.janela(t, inicio, duracao)` ([sinais.py:20-21](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L20-L21)) e devolve os parâmetros. Com o sorteio desligado, `sortear_posicao` devolve `Sorteio(False, ...)` com os valores legados (60 ms, 60 ms, fase 0) e `parametros()` vazio.
- `configurar` chama `self.fonte.trigger_pulse(nivel × base, width_s=self.largura_do_pulso_s(DURACAO_S))`. `largura_do_pulso_s` devolve a duração sorteada (`_duracao_sorteada_s`, posta por `_capturar_real` **antes** de `configurar`) ou, sem sorteio, os 60 ms de `DURACAO_S`. Chamar `configurar()` fora de `_capturar_real` usa a duração legada.
- Atributos: `pre_trigger_s` = 0,060 ([02.py:13](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/02.py#L13)), `INICIO_S` ([02.py:15](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/02.py#L15)) e `DURACAO_S` ([02.py:16](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/02.py#L16)); `capturas_padrao` herdado (1). Sem `usar_trace`, `scope_scale_v` nem ganchos de redução (nativa).
- Contrato geral e acoplamentos: {doc}`../codigo/classes_contrato`; o percurso de uma captura nativa: {doc}`../scpi/sequencias`.

## 13. Referências

- Código: `experimentos_nativos/02.py`; `logica/mestre.py` (`ExperimentoNativo`, `sortear_posicao`); `logica/ametek_orm.py` (`trigger_pulse`, `definir_fase_de_disparo`); `logica/sinais.py` (`janela`, `forma_programada_nativa`).
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`../scpi/sequencias`, {doc}`../limites_e_calibracao`, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`.
- Histórico: `CHANGELOG/v1.7.md`, `v1.10.md`, `v1.11.md`, `v1.12.md`, `v1.13.md`, `v1.14.md`, `v1.15.md`. Norma: IEEE Std 1159-2019, Tabela 2, item 2.1.1.
