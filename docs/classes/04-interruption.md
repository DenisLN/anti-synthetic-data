# Classe 04: INTERRUPTION

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 (127 V/60 Hz e 127 V/50 Hz, 3 capturas, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` sorteio de início, duração e fase; 230 V/50 Hz {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-05`

| Campo | Valor |
|---|---|
| Número e nome | 04 INTERRUPTION (interrupção de tensão) |
| Arquivo | `experimentos_nativos/04.py`, classe `Experimento(ExperimentoNativo)` |
| Mecanismo na bancada | **nativa**: PULSe para um nível próximo de zero ({scpi}`VOLTage:MODE` `PULSe`, {scpi}`VOLTage:TRIGgered`, {scpi}`PULSe:WIDTh`) |
| `capturas_padrao` | 3 ([04.py:16](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/04.py#L16)): o nível é sorteado e uma captura mostra uma só realização |
| Sorteio de posição | I D F |
| Depende do perfil? | não: nível, forma e posição não vêm de `perfis.py`; capturada uma vez com `set perfil todos` |
| Condições já medidas | 127 V/60 Hz e 127 V/50 Hz (3 capturas cada); 230 V/50 Hz foi pulada em 07/10 |

## 1. Em uma resposta

**Pergunta:** o que a classe 04 produz? **Resposta:** uma senoide que **cai a um nível $\ell \in [0;\,0{,}09]$ pu por um trecho sorteado dos 200 ms e volta ao normal**, ou seja, uma interrupção (quase zero) em vez de um afundamento; é um PULSe nativo como o da 02, com o nível sorteado em vez de tabelado.

Estado: o PULSe com nível próximo de zero foi medido em 07/10/2026; o sorteio de posição nunca ({ref}`P-05 <p-05>`) e nenhum dado existe com o código da v1.15 ({ref}`P-01 <p-01>`).

## 2. O fenômeno e a norma

Interrupção: perda quase total de tensão. Item 2.2.1 da Tabela 2 da IEEE Std 1159-2019 (momentânea): **abaixo de 0,1 pu, de 0,5 ciclo a 3 s**. A classe usa $\ell < 0{,}09$ pu, sempre abaixo do limite; a duração é a do sorteio (meio ciclo a janela menos dois ciclos).

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v(t)=a(t)\,\sin\!\big(2\pi f_0\,(t+\tau)\big),\qquad
a(t)=\begin{cases}\ell & t_0\le t<t_0+d\\ 1 & \text{caso contrário}\end{cases},\qquad
\ell\sim\mathcal{U}(0;\,0{,}09)
$$

O nível $\ell$ é o único parâmetro sorteado com o `rng` da classe, por `sinais.valor_para_captura(rng, 0.0, 0.09, ...)` ([sinais.py:24-49](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L24-L49)); $t_0$, $d$, $\varphi$ vêm do sorteio de posição ({ref}`fórmulas <sorteio-de-posicao>`); sem sorteio valem 60 ms, 60 ms e fase 0 (`INICIO_S` em [04.py:19](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/04.py#L19), `DURACAO_S` em [04.py:20](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/04.py#L20)).

```{literalinclude} ../../experimentos_nativos/04.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_nativos/04.py, Experimento.gerar
```

- **Parâmetros no metadata:** `interruption_pu`, `inicio_disturbio_s`, `duracao_s`, `fase_graus`.
- **Seed:** `base_seed + 4 · 1 000 000 + indice_global`.
- **Capturas:** `capturas_padrao` = 3 ([04.py:16](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/04.py#L16)). Sem `set capturas` as 3 capturas **sorteiam** $\ell$. Com `set capturas N` (N > 1) a bancada usa **cobertura determinística**: `valor_para_captura` devolve `linspace(0; 0,09; N)[capture_index]`, e a primeira captura é exatamente 0 pu e a última 0,09 pu (v1.8).
- **Ordem do `rng`:** `gerar()` sorteia $\ell$ **antes** de qualquer outra coisa que use o `rng`; o sorteio de posição vem de um sub-fluxo e não consome o `rng`. A ordem é um contrato com `configurar()` (seção 12).

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** como a fonte chega perto de zero por um trecho? **Resposta:** com o mesmo PULSe da 02, com o nível $\ell \cdot V_\text{base}$ entre 0 e 11,4 V a 127 V; o valor passa por `VOLTage:TRIGgered` em múltiplos de 0,1 V.

Ordem dos comandos igual à da {doc}`02-sag` (seção 4):

1. {scpik}`:TIMebase:POSition` com o pré-trigger sorteado; {scpi}`TRIGger:SYNChronize:PHASe` na fase no instante do evento.
2. `configurar()` **reproduz o $\ell$ de `gerar()`** com uma seed própria ([04.py:37](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/04.py#L37)) e chama `AmetekMX30.trigger_pulse` ([ametek_orm.py:908-937](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L908-L937)): {scpi}`VOLTage:MODE` `PULSe`, {scpi}`VOLTage:TRIGgered` $\ell \cdot V_\text{base}$ arredondado a 0,1 V, {scpi}`PULSe:WIDTh` com a duração sorteada.
3. Armamento, `*TRG` e leitura como na {doc}`01-normal`, com o readback de {scpi}`PULSe:WIDTh?`.

**O truncamento a 0,1 V.** A Rev. 5.53 trunca `VOLTage:TRIGgered` a 0,1 V: um nível de 2,7367 V era aplicado como 2,7 V e o readback de `arm()` (tolerância de 0,5 %) recusava a captura (v1.12, N3). A classe 04 foi a que mostrou o defeito, porque seus níveis são contínuos: o código passou a escrever o múltiplo de 0,1 V mais próximo (`AmetekMX30._na_resolucao_da_fonte`, [ametek_orm.py:857-865](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L857-L865)), de modo que o metadata e o readback dizem o que a fonte **realmente** aplica. Por isso a `programada` da 04 usa o nível quantizado: 2,1813 V vira 2,2 V (diferença de 0,0004 pu no nível).

**Janela e margem.** `pre_trigger_s` = 0,060 ([04.py:17](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/04.py#L17)); com o sorteio ligado, o pré-trigger é o `inicio_disturbio_s` da captura. Registro físico: 20 ms antes e 50 ms depois ({doc}`../medicao`).

## 5. Parâmetros por perfil

Esta classe não lê nenhum componente de `perfis.py` (`COMPONENTES_POR_CLASSE` não a lista): `gerar()` é igual nos três perfis.

A 04 é **independente do perfil**: o nível $\mathcal{U}(0;\,0{,}09)$, a forma e a posição são os mesmos nos três perfis. Com o sorteio ligado ela é uma das oito classes que `perfis.classes_independentes_do_perfil` lista (01, 04, 07, 08, 09, 17, 18, 19) e `set perfil todos` a captura uma única vez, sob `literatura`, com os outros perfis apontando para a mesma captura ({doc}`../perfis`).

## 6. Limites físicos e fator de extremo

Como na 02, o que limita é a **volta** da interrupção (quirk A20): o pico programado é o da senoide base e o extremo previsto é pico × fator × 1,10 contra 415,8 V. Quanto mais fundo o afundamento, maior o salto da volta: a 04 tem o mesmo tipo de sobressinal da 02 e fator parecido.

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,192 | 3 | 179,6 | 235,5 | 415,8 | 100 % | 3/3 rodam |
| 127 V/50 Hz | 1,063 | 3 | 179,6 | 210,0 | 415,8 | 100 % | 3/3 rodam |
| 230 V/50 Hz | sem entrada | 3 | 325,3 | 380,3 | 415,8 | 100 % | 3/3 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 3 | 311,1 | 504,8 | 415,8 | 100 % | 0/3 rodam, 3 pulada(s) |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 3 capturas padrão, seed 20260827, sorteio ligado). A 230 V/50 Hz a 04 roda desde a v1.15 (regra por frequência: 325,3 V × 1,063 × 1,10 = 380,3 V); em 07/10 foi pulada. A 220 V/60 Hz (sem tabela) é pulada nas três capturas: 311,1 V × 1,475 × 1,10 = 504,8 V ({ref}`P-21 <p-21>`). Nativas não reduzem o distúrbio.

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. Para a 04 o **mínimo do envelope** confere se a interrupção aconteceu; como o esperado é próximo de zero, entra o piso absoluto da tolerância (5 % da mediana esperada, [sinais.py:360-456](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L360-L456)), senão uma tolerância relativa seria impossível de satisfazer.

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,702–0,703 / 0,707 | 0,013–0,019 / 0,012–0,020 | 0,714–0,716 / 0,707 | 0,046–0,047 / 0,046–0,046 | 1,462–1,481 / 1,414 |
| 127 V/50 Hz | 0,700–0,701 / 0,707 | 0,014–0,017 / 0,012–0,020 | 0,715–0,716 / 0,707 | 0,004 / 0,000 | 1,462–1,464 / 1,414 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`). O mínimo do envelope medido (0,013–0,019 pu) acompanha o esperado (0,012–0,020 pu) capturas a capturas; o THD esperado a 60 Hz (4,6 %) vem do degrau a 3,6 ciclos (a 50 Hz, a 3 ciclos exatos, é 0,0 %).

## 8. As três versões e a correlação esperada

A `programada` é a senoide com o nível quantizado a 0,1 V em `[inicio, inicio + duração)` (`sinais.forma_programada_nativa`, [sinais.py:624-683](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L624-L683)). O toque da fonte na volta da interrupção é física da fonte, fica só na `medida`.

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 1,000 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,996–0,999 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,996–0,999 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,999 / 0,999 | 0,996–0,997 / 0,995–0,997 | — |
| modelo × medida | 0,999 / 0,999 | 0,996–0,997 / 0,995–0,997 | — |

Causa de a classe ficar abaixo de 0,90, quando fica: —

A 04 é uma das classes mais bem correlacionadas (0,996–0,999 em 07/10): o evento é o maior possível (de 1 a quase 0 pu) e a métrica só vê o que o evento acrescenta.

## 9. Quirks e armadilhas

- **A12:** `VOLTage:TRIGgered` truncado a 0,1 V (a origem do N3 e do readback recusado).
- **A14, A18, A1, K1:** como na {doc}`02-sag`.
- **A20:** o sobressinal da volta: fator 1,164 a 127 V/60 Hz e 1,063 a 127 V/50 Hz.
- **Acoplamento 04/19 com `seed_da_captura`:** `configurar()` repete a conta da seed à mão (`base_seed + 4_000_000 + capture_index`, [04.py:37](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/04.py#L37)) porque não recebe o `rng`. Só concorda com `gerar()` enquanto `capture_index == indice_global`, que é verdade na 04 (ela não tem `NIVEIS`). Mudar `seed_da_captura` ([mestre.py:1703-1707](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1703-L1707)) ou o id da classe desacopla os dois sem erro ({doc}`../codigo/acoplamentos`).
- **Cobertura e `analisar_sessao`:** a reconstrução offline ([analisar_sessao.py:129-187](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L129-L187)) instancia o experimento sem osciloscópio e sempre cai no ramo do sorteio de `valor_para_captura`, mesmo quando a captura real usou a cobertura; o efeito na correlação da 04 {bdg-warning}`NÃO VERIFICADO` ({doc}`../medicao/correlacao` §8).

## 10. Histórico por versão

- **v1.8:** cobertura determinística (`valor_para_captura`) para a 04, 06, 08, 09 e 19 quando o operador digita `set capturas N` (N > 1); o sorteio de sempre vale sem isso.
- **v1.10 a v1.11:** como na {doc}`02-sag` (o "Bug A" do pulso invisível e o H-NATIVO). Nas sessões de 16/09/2026 a 04 chegou a produzir uma **elevação** de 242 V (o nível da 03) em vez de uma interrupção, sem erro SCPI nenhum: foi o caso que levou ao readback e à validação física.
- **v1.12:** N3, o truncamento a 0,1 V; a causa de `2,7367 V` ser lido como `2,7 V` e o readback recusar a captura.
- **v1.13:** `capturas_padrao` = 3 na 04 (o nível é sorteado).
- **v1.14:** fatores de extremo por condição (1,164 a 127 V/60 Hz, 1,063 a 127 V/50 Hz); a 230 V/50 Hz a 04 fica pulada.
- **v1.15:** sorteio de início, duração e fase; a regra por frequência a traz de volta a 230 V/50 Hz; independente do perfil (capturada uma vez com `set perfil todos`).

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| PULSe com nível próximo de zero | {bdg-success}`VERIFICADO NA BANCADA` | 127 V/60 Hz e 127 V/50 Hz, 07/10/2026, 3 capturas cada, validação física 3/3 |
| `gerar()` e programada de hoje | {bdg-info}`OFFLINE` | fixtures; correlação modelo × programada 1,000 |
| Sorteio de início, duração e fase; `PULSe:WIDTh` sorteada | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15 |
| 230 V/50 Hz | {bdg-warning}`NÃO VERIFICADO` | pulada em 07/10; hoje o previsto é 380,3 V e roda |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
:::

:::{important} Pendência P-05
Sorteio de posição nas nativas (fase de disparo sem readback, pré-trigger por captura, `PULSe:WIDTh` sorteada) nunca medido. Fecha com: bancada. Prioridade MÉDIA.
:::

## 12. Como o código da classe funciona

| Símbolo | Recebe | Devolve | Quem chama |
|---|---|---|---|
| `Experimento.gerar` ([experimentos_nativos/04.py:22-32](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/04.py#L22-L32)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"interruption_pu", "inicio_disturbio_s", "duracao_s", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.configurar` ([experimentos_nativos/04.py:34-44](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/04.py#L34-L44)) | `capture_index` | `{"interruption_pu": nível}` | a linha [mestre.py:2972](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2972) de `ExperimentoNativo._capturar_real` |

- `gerar` sorteia a posição (`sortear(..., duracao_variavel=True)`), decide `cobertura_ativa = not simulado and capturas_override is not None` (`simulado` é `self.osc is None`), chama `valor_para_captura(rng, 0.0, 0.09, capture_index, total, cobertura_ativa=...)` e multiplica a janela pelo nível.
- `configurar` **não recebe o `rng`**: constrói `np.random.default_rng(base_seed + 4_000_000 + capture_index)` e repete `valor_para_captura`, com `total = self.config.capturas(False)`. O resultado é o mesmo $\ell$ de `gerar()` enquanto `capture_index` for o índice global. Depois chama `trigger_pulse(nível × base, width_s=self.largura_do_pulso_s(DURACAO_S))`.
- Atributos: `capturas_padrao` = 3 ([04.py:16](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/04.py#L16)), `pre_trigger_s` = 0,060 ([04.py:17](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/04.py#L17)), `INICIO_S` ([04.py:19](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/04.py#L19)) e `DURACAO_S` ([04.py:20](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/04.py#L20)).
- Contrato e acoplamentos: {doc}`../codigo/classes_contrato` §4 ("04, 19: `seed_da_captura`").

## 13. Referências

- Código: `experimentos_nativos/04.py`; `logica/sinais.py` (`valor_para_captura`); `logica/mestre.py` (`ExperimentoNativo`); `logica/ametek_orm.py` (`trigger_pulse`).
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`../limites_e_calibracao`, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`, {doc}`02-sag`.
- Histórico: `CHANGELOG/v1.8.md`, `v1.11.md`, `v1.12.md`, `v1.13.md`, `v1.14.md`, `v1.15.md`. Norma: IEEE Std 1159-2019, Tabela 2, item 2.2.1.
