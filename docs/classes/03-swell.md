# Classe 03: SWELL

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 (127 V/60 Hz e 127 V/50 Hz, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` sorteio de início, duração e fase; 230 V/50 Hz inviável {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-05`

| Campo | Valor |
|---|---|
| Número e nome | 03 SWELL (elevação de tensão) |
| Arquivo | `experimentos_nativos/03.py`, classe `Experimento(ExperimentoNativo)` |
| Mecanismo na bancada | **nativa**: PULSe ({scpi}`VOLTage:MODE` `PULSe`, {scpi}`VOLTage:TRIGgered`, {scpi}`PULSe:WIDTh`), igual à 02 com o nível acima da base |
| `capturas_padrao` | 1 (herdado, [mestre.py:1564](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1564)); 5 níveis, e **sem `set capturas` só o nível 0 roda** |
| Sorteio de posição | I D F |
| Depende do perfil? | sim: os cinco níveis mudam (`swell_niveis`) |
| Condições já medidas | 127 V/60 Hz e 127 V/50 Hz (1 captura, nível 1,1 pu); 230 V/50 Hz é inviável |

## 1. Em uma resposta

**Pergunta:** o que a classe 03 produz? **Resposta:** uma senoide que **sobe a um nível $\ell$ entre 1,1 e 1,8 pu por um trecho sorteado dos 200 ms e volta ao normal**; é a 02 com o nível acima de 1, e o que muda na bancada é o limite: 1,8 pu a 127 V já pede 228,6 Vrms, e a 230 V só o nível 1,1 cabe nos 300 Vrms da fonte.

Estado: o PULSe foi medido em 07/10/2026 com o nível 1,1 pu; o sorteio de posição e a largura do pulso sorteada nunca foram medidos ({ref}`P-05 <p-05>`), e nenhum dado existe com o código da v1.15 ({ref}`P-01 <p-01>`).

## 2. O fenômeno e a norma

Elevação de tensão (*swell*): aumento do valor rms da tensão por um intervalo curto, geralmente por falta fase-terra em outra fase ou desligamento de carga grande. Item 2.1.2 da Tabela 2 da IEEE Std 1159-2019 (instantâneo): **1,1 a 1,8 pu, de 0,5 a 30 ciclos**. O perfil `literatura` usa os extremos da norma (1,1 e 1,8 pu); o perfil `norma` fica dentro (1,15 a 1,75 pu); a duração sorteada vai de meio ciclo à janela menos dois ciclos.

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v(t)=a(t)\,\sin\!\big(2\pi f_0\,(t+\tau)\big),\qquad
a(t)=\begin{cases}\ell & t_0\le t<t_0+d\\ 1 & \text{caso contrário}\end{cases},\qquad
\ell=\texttt{NIVEIS}[\,\text{capture\_index}\bmod 5\,]
$$

$t_0$, $d$ e $\varphi$ vêm do sorteio de posição ({ref}`fórmulas <sorteio-de-posicao>`); sem sorteio valem 60 ms, 60 ms e fase 0 (`INICIO_S` em [03.py:15](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/03.py#L15) e `DURACAO_S` em [03.py:16](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/03.py#L16)). O código é o da 02 trocando `sag_niveis` por `swell_niveis`; o nível vem de `capture_index`, não do `rng`.

```{literalinclude} ../../experimentos_nativos/03.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_nativos/03.py, Experimento.gerar
```

- **Parâmetros no metadata:** `swell_pu`, `inicio_disturbio_s`, `duracao_s`, `fase_graus`.
- **Seed:** `base_seed + 3 · 1 000 000 + indice_global`.
- **Capturas e níveis:** `capturas_padrao` = 1: o plano padrão é **uma** captura no nível 0 (1,1 pu na `literatura`). Cobrir os cinco níveis exige `set capturas N` (N capturas por nível, `ExperimentoBase.dimensionar_capturas`, [mestre.py:1684-1701](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1684-L1701)).

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** a fonte consegue subir a tensão por 60 ms? **Resposta:** consegue, com o mesmo PULSe da 02, desde que o nível, o pico e a volta caibam nos limites: o PULSe vai a $\ell \cdot V_\text{base}$ por `PULSe:WIDTh` e retorna ao nível imediato.

A ordem dos comandos é a da {doc}`02-sag` (seção 4), com o nível $\ell \cdot V_\text{base}$ acima da base:

1. {scpik}`:TIMebase:POSition` com o pré-trigger sorteado (`definir_pre_trigger`, [oscilloscope_orm.py:339-354](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L339-L354)).
2. {scpi}`TRIGger:SYNChronize:PHASe` na fase da senoide no instante do evento (`fase_de_disparo_graus`, [mestre.py:2918-2934](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2918-L2934)).
3. `AmetekMX30.trigger_pulse` ([ametek_orm.py:908-937](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L908-L937)): {scpi}`VOLTage:MODE` `PULSe`, {scpi}`VOLTage:TRIGgered` $\ell \cdot V_\text{base}$ (múltiplo de 0,1 V), {scpi}`PULSe:WIDTh`; recusa $\ell V_\text{base} > $ `max_voltage_rms` (300 V) com `ParameterOutOfBoundsError` (a recusa está nas linhas [ametek_orm.py:914-917](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L914-L917)), mas a pré-validação já pulou o nível antes.
4. Armamento, `*TRG` e leitura como na {doc}`01-normal`, com o readback de {scpi}`PULSe:WIDTh?`.

Em 07/10/2026 a fonte aplicou o nível pedido: o máximo do envelope medido foi 0,784 pu (127 V/60 Hz) e 0,787 pu (127 V/50 Hz) contra 0,778 pu esperado ($1{,}1/\sqrt{2}$).

## 5. Parâmetros por perfil

| Componente em `perfis.py` | `norma` | `literatura` (padrão) | `fronteira` |
|---|---|---|---|
| `swell_niveis` | níveis 1,15 / 1,3 / 1,45 / 1,6 / 1,75 | níveis 1,1 / 1,2 / 1,4 / 1,6 / 1,8 | níveis 1,1 / 1,8 |

Níveis programados a cada tensão (múltiplos de 0,1 V; a fonte limita a **300 Vrms**):

| Nível (pu) | Perfis que o usam | Programa a 127 V (V rms) | Programa a 230 V (V rms) | Cabe no limite de 300 Vrms a 230 V? |
|---|---|---|---|---|
| 1,1 | `literatura`, `fronteira` | 139,7 | 253,0 | sim |
| 1,15 | `norma` | 146,0 | 264,5 | sim |
| 1,2 | `literatura` | 152,4 | 276,0 | sim |
| 1,3 | `norma` | 165,1 | 299,0 | sim |
| 1,4 | `literatura` | 177,8 | 321,9 | não (o nível pede mais que 300 Vrms) |
| 1,45 | `norma` | 184,2 | 333,4 | não (o nível pede mais que 300 Vrms) |
| 1,6 | `norma`, `literatura` | 203,2 | 367,9 | não (o nível pede mais que 300 Vrms) |
| 1,75 | `norma` | 222,2 | 402,4 | não (o nível pede mais que 300 Vrms) |
| 1,8 | `literatura`, `fronteira` | 228,6 | 413,9 | não (o nível pede mais que 300 Vrms) |

*Fonte:* `AmetekMX30.quantizar_tensao_rms` aplicado a $\ell \cdot V_\text{base}$ (cálculo offline de 2026-10-16). A 230 V só 1,1 pu, 1,15, 1,2 e 1,3 pu cabem em 300 Vrms; o que decide é o extremo previsto (seção 6), não só o rms.

## 6. Limites físicos e fator de extremo

Aqui os dois limites da fonte se encontram: o **rms** do nível ($\ell V_\text{base} \le 300$ Vrms; `avaliar_captura_na_bancada`, [mestre.py:2063-2121](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2063-L2121), e `tensao_rms_programada`, [mestre.py:2903-2911](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2903-L2911)) e o **pico** do extremo previsto. O pico programado da 03 é o do patamar, $\ell V_\text{base}\sqrt{2}$ (`_pico_da_forma_v`, [mestre.py:1998-2004](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1998-L2004), usa o maior entre o pico da forma e o rms × √2).

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,058 | 1 | 197,6 | 229,9 | 415,8 | 100 % | 1/1 rodam |
| 127 V/50 Hz | 1,058 | 1 | 197,6 | 229,9 | 415,8 | 100 % | 1/1 rodam |
| 230 V/50 Hz | sem entrada | 1 | 357,8 | 416,4 | 415,8 | 100 % | 0/1 rodam, 1 pulada(s) |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 1 | 342,2 | 555,3 | 415,8 | 100 % | 0/1 rodam, 1 pulada(s) |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, nível 0 apenas, sorteio ligado). A 230 V/50 Hz a 03 **fica de fora**: 357,8 V × 1,058 × 1,10 = 416,4 V > 415,8 V, por 0,6 V; a regra não tem exceção na margem e a decisão de projeto (v1.15) foi mantê-la. A 220 V/60 Hz (sem tabela) também é pulada: 342,2 V × 1,475 × 1,10 = 555,3 V ({ref}`P-21 <p-21>`). Nativas **não reduzem** o distúrbio: reduzir 1,2, 1,4, 1,6 e 1,8 pu "para caber" produziria capturas iguais com rótulos diferentes (decisão da v1.13).

## 7. Validação física

Tolerâncias: {ref}`ver as sondas e as tolerâncias <validacao-fisica-tolerancias>`. Para a 03 o **máximo do envelope** é a sonda que pega uma elevação que não aconteceu: esperado $\ell/\sqrt{2}$ (0,778 pu para $\ell$ = 1,1).

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,713 / 0,707 | 0,701 / 0,707 | 0,784 / 0,778 | 0,005 / 0,003 | 1,461 / 1,414 |
| 127 V/50 Hz | 0,715 / 0,707 | 0,699 / 0,707 | 0,787 / 0,778 | 0,002 / 0,000 | 1,458 / 1,414 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`). O máximo do envelope (0,784 e 0,787 contra 0,778) passa na tolerância de 15 %; o THD esperado a 60 Hz (0,3 %) e a 50 Hz (0,0 %) vem do degrau do pulso cair a 3,6 e a 3,0 ciclos.

## 8. As três versões e a correlação esperada

A `programada` da 03 é a senoide com $a(t)$ no nível quantizado, como na 02 (`sinais.forma_programada_nativa`, [sinais.py:624-683](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L624-L683)); o toque da volta do patamar é física da fonte e fica só na `medida`.

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 1,000 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,943–0,945 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,943–0,945 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,945 / 0,926 | 0,943 / 0,920 | — |
| modelo × medida | 0,945 / 0,926 | 0,943 / 0,920 | — |

Causa de a classe ficar abaixo de 0,90, quando fica: —

Entre as classes de degrau por PULSe (02, 03 e 04), a 03 é a única que fica **abaixo de 0,95** em modelo × medida (0,943–0,945), embora o modelo × programada seja 1,000. O evento da 03 é pequeno em amplitude (0,1 pu de excesso em 1,1 pu) e a fundamental da fonte difere do programado em 0,2 % a 1,4 % a 127 V ({doc}`../medicao/correlacao` §1), erro que cobre uma parte relevante do resíduo; a correlação com a fundamental ajustada **cai** (0,920–0,926) porque o ajuste absorve parte do evento. A explicação é compatível com os números, mas não foi isolada por medida.

## 9. Quirks e armadilhas

- **A14, A12, A18, A1, K1:** como na {doc}`02-sag` (escrita durante transiente, truncamento a 0,1 V, fase de disparo, rajada, referência horizontal).
- **A20:** a volta de um patamar acima da base também toca: fator 1,058 a 127 V/60 Hz e a 127 V/50 Hz.
- **Limite de rms:** o `ParameterOutOfBoundsError` de `trigger_pulse` é determinístico e não é retentado; o plano pula o nível antes de qualquer SCPI (v1.11, P04).
- **Acoplamento:** os mesmos de `INICIO_S`/`DURACAO_S`/`pre_trigger_s` da 02 ({doc}`../codigo/acoplamentos`).

## 10. Histórico por versão

- **v1.7 a v1.12:** igual à {doc}`02-sag` (a 03 usa o mesmo `trigger_pulse`).
- **v1.11 (P04):** a 03 a 220 V pedia 1,4 pu = 308 Vrms, acima dos 300 Vrms da fonte, e o código antigo só descobria na 21.ª captura, três vezes seguidas; passou a pular o nível antes de capturar.
- **v1.13:** a 220 V a 03 roda só 1,1 pu (1,2 pu prevê 434 V; 1,4 pu e mais passam de 300 Vrms); nativas não reduzem.
- **v1.14:** fatores por condição; a 230 V/50 Hz a 03 não roda.
- **v1.15:** perfis, sorteio de início, duração e fase; a regra por frequência não a traz de volta a 230 V/50 Hz (416,4 V > 415,8 V, mantida por decisão de projeto).

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| PULSe aplica o nível 1,1 pu | {bdg-success}`VERIFICADO NA BANCADA` | 127 V/60 Hz e 127 V/50 Hz, 07/10/2026 |
| `gerar()` e programada de hoje | {bdg-info}`OFFLINE` | fixtures; correlação modelo × programada 1,000 |
| Sorteio de início, duração e fase; `PULSe:WIDTh` sorteada | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15 |
| Níveis 1,2 a 1,8 pu na bancada | {bdg-warning}`NÃO VERIFICADO` | as sessões de 07/10 capturaram só o nível 0; os outros exigem `set capturas N` |
| 230 V/50 Hz | {bdg-info}`OFFLINE` | inviável por conta (416,4 V > 415,8 V) |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
:::

:::{important} Pendência P-05
Sorteio de posição nas nativas (fase de disparo sem readback, pré-trigger por captura, `PULSe:WIDTh` sorteada) nunca medido. Fecha com: bancada. Prioridade MÉDIA.
:::

## 12. Como o código da classe funciona

| Símbolo | Recebe | Devolve | Quem chama |
|---|---|---|---|
| `Experimento.NIVEIS` ([experimentos_nativos/03.py:19-21](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/03.py#L19-L21)) | nada (propriedade) | `perfis.faixa(self.config, "swell_niveis")` | `gerar`, `configurar`, `total_niveis` ([mestre.py:1675-1682](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1675-L1682)), `tensao_rms_programada` ([mestre.py:2903-2911](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2903-L2911)) |
| `Experimento.gerar` ([experimentos_nativos/03.py:23-30](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/03.py#L23-L30)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"swell_pu", "inicio_disturbio_s", "duracao_s", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.configurar` ([experimentos_nativos/03.py:32-35](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/03.py#L32-L35)) | `capture_index` | `{"swell_pu": nível}` | a linha [mestre.py:2972](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2972) de `ExperimentoNativo._capturar_real` |

- O arquivo é o da {doc}`02-sag` com `swell_niveis` e a chave `swell_pu`; os atributos de classe são os mesmos (`pre_trigger_s` = 0,060 em [03.py:13](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/03.py#L13), `INICIO_S` e `DURACAO_S` em [03.py:15-16](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/03.py#L15-L16)).
- `ExperimentoNativo.tensao_rms_programada` ([mestre.py:2903-2911](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2903-L2911)) lê `NIVEIS` e devolve $\ell \cdot V_\text{base}$: é por ela que a pré-validação conhece o rms da 03 (e da 02) antes de qualquer SCPI.
- Contrato e acoplamentos: {doc}`../codigo/classes_contrato`.

## 13. Referências

- Código: `experimentos_nativos/03.py`; `logica/mestre.py` (`ExperimentoNativo`, `avaliar_captura_na_bancada`); `logica/ametek_orm.py` (`trigger_pulse`).
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`../limites_e_calibracao`, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`, {doc}`02-sag`.
- Histórico: `CHANGELOG/v1.11.md`, `v1.13.md`, `v1.14.md`, `v1.15.md`. Norma: IEEE Std 1159-2019, Tabela 2, item 2.1.2.
