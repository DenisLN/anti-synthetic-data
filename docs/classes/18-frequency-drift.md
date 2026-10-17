# Classe 18: FREQUENCY_DRIFT

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 (rampa de 57 a 63 Hz; 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` rampa f0 ± 3 Hz, continuidade de fase na troca {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-06`

| Campo | Valor |
|---|---|
| Número e nome | 18 FREQUENCY_DRIFT (desvio e variação de frequência) |
| Arquivo | `experimentos_nativos/18.py`, classe `Experimento(ExperimentoNativo)` |
| Mecanismo na bancada | **nativa**: lista de frequência de 2 pontos ({scpi}`FREQuency:MODE` `LIST`, {scpi}`LIST:FREQuency`, {scpi}`SOURce:LIST:DWELl`) |
| `capturas_padrao` | 1 (herdado, [mestre.py:1564](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1564)): só o sentido ascendente roda sem `set capturas` |
| Sorteio de posição | F (só a fase inicial) |
| Depende do perfil? | não: capturada uma vez com `set perfil todos` |
| Condições já medidas | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 1 captura (57 → 63 Hz nas três) |

## 1. Em uma resposta

**Pergunta:** a frequência da rede varia durante a captura; como a bancada reproduz isso? **Resposta:** o modelo é uma **rampa linear de $f_0-3$ a $f_0+3$ Hz em 200 ms** (e a inversa nas capturas ímpares); a fonte recebe só **dois pontos** de frequência, o inicial na primeira metade da janela e o final na segunda, de modo que a bancada toca um degrau de 6 Hz no meio, não a rampa. Por isso modelo × programada fica em 0,95 (nominal).

Estado: a rampa de 57 a 63 Hz foi medida em 07/10/2026; a rampa f0 ± 3 Hz (47 a 53 Hz a 50 Hz), a continuidade de fase na troca de ponto e a restauração da frequência depois dela nunca foram medidas com o código da v1.15 ({ref}`P-06 <p-06>`, {ref}`P-01 <p-01>`).

## 2. O fenômeno e a norma

Variação da frequência da rede em torno do valor nominal. O item 7.0 da Tabela 2 da IEEE Std 1159-2019 trata a variação de frequência de potência como tipicamente de $\pm$0,1 Hz; a classe **foge da faixa típica de propósito** (decisão de projeto): o desvio de $\pm$3 Hz representa microrredes ilhadas e geração distribuída, onde inversores fotovoltaicos desconectam por sub e sobrefrequência (ABNT NBR 16149), e um classificador sem desvios de frequência pode confundir uma mudança no período da onda com um afundamento ou um harmônico (`experimentos.txt`, classe 18).

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

Com $f_k$ crescendo linearmente de $f_\text{ini}$ a $f_\text{fim}$ nas 6000 amostras ($k=0\ldots5999$, `numpy.linspace(..., endpoint=True)`), a fase acumula a frequência instantânea e a senoide parte da fase sorteada $\varphi$:

$$
\phi_0=0,\quad \phi_k=\frac{2\pi}{f_s}\sum_{j=0}^{k-1} f_j,\qquad v_k=\sin\!\big(\phi_k+\varphi\big),\qquad f_s=30\ \text{kSa/s}
$$

Os extremos vêm de `extremos_hz`: com o sorteio ligado, $(f_\text{ini},f_\text{fim})=(f_0-3,\,f_0+3)$ em `capture_index` par e o inverso em `capture_index` ímpar; com `set sorteio off`, $57 \to 63$ Hz (a 50 Hz isso é +14 % e +26 % da rede). Só a fase é sorteada ({ref}`fórmulas <sorteio-de-posicao>`).

```{literalinclude} ../../experimentos_nativos/18.py
:pyobject: Experimento.extremos_hz
:language: python
:caption: experimentos_nativos/18.py, Experimento.extremos_hz
```

```{literalinclude} ../../experimentos_nativos/18.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_nativos/18.py, Experimento.gerar
```

- **Parâmetros no metadata:** `start_hz`, `end_hz`, `fase_graus`.
- **Seed:** `base_seed + 18 · 1 000 000 + indice_global`; a classe não consome o `rng` (a rampa é determinística; só a fase vem do sub-fluxo do sorteio).
- **Capturas:** `capturas_padrao` = 1 (herdado): a captura única tem `capture_index` 0, logo roda só a rampa **ascendente**. Para visitar o sentido descendente é preciso `set capturas 2` ou mais.

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** a fonte reproduz a rampa? **Resposta:** não a rampa: o `LIST:FREQuency` de dois pontos toca $f_\text{ini}$ por 100 ms e $f_\text{fim}$ por 100 ms (um degrau no meio). O código admite isso no cabeçalho de `18.py` ("não é uma rampa contínua amostra a amostra") e a `programada` reconstruída offline já é esse degrau.

Ordem de uma captura (`ExperimentoNativo._capturar_real`, [mestre.py:2936-2983](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2936-L2983), ramo nativo):

1. {scpi}`TRIGger:SYNChronize:PHASe` recebe a fase sorteada (sem evento localizado, o pré-trigger do osciloscópio não muda).
2. `configurar()` chama `AmetekMX30.frequency_drift_list` ([ametek_orm.py:1066-1106](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1066-L1106)) com $f_\text{ini}$, $f_\text{fim}$, a tensão base e `dwell_s = duration_s / 2` = 0,1 s: recusa frequência fora de 45 a 500 Hz; `aguardar_idle`; {scpi}`FUNCtion:MODE` `FIXed` e {scpi}`SOURce:FREQuency:MODE` `FIXed` (neutralizam listas residuais; a causa do `-226` depois da 17, abaixo); {scpi}`VOLTage:MODE` `FIXed`; {scpi}`FREQuency:MODE` `LIST`; {scpi}`LIST:FREQuency` `a,b`; {scpi}`LIST:VOLTage` `v,v`; {scpi}`SOURce:LIST:DWELl` `d,d`; {scpi}`SOURce:LIST:REPeat` `0,0`; {scpi}`SOURce:LIST:COUNt` `1`; {scpi}`SOURce:LIST:STEP` `AUTO`; {scpi}`VOLTage:MODE` `LIST`.
3. Armamento e `*TRG` como na {doc}`01-normal`.
4. Ao fim da classe, `restaurar_frequencia_base` ([ametek_orm.py:1050-1064](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1050-L1064)) reescreve a frequência base: {scpi}`SOURce:FREQuency:MODE` `FIXed`, {scpi}`SOURce:FREQuency`, {scpi}`SYSTem:ERRor?`.

Descrição em {doc}`../scpi/sequencias` §6. Pontos que a ordem protege:

- `FUNCtion:MODE FIXed` **antes**: depois da 17, uma lista de forma de 12 pontos continuava ativa e o `VOLTage:MODE LIST` final dava `-226 Lists not same length` (listas de 12 e de 2 pontos; manual §4.17, p. 90).
- `SOURce:LIST:REPeat 0,0` com o prefixo `SOURce:` e sem `:COUNt` (quirks A4 e A5): `1` toca cada ponto duas vezes.
- **Ao fim de um `LIST` a saída fica no último ponto** (quirk A11): a 19 rodou a 63,03 Hz depois da 18 até `restaurar_frequencia_base` existir (v1.12).

**Janela e margem.** `pre_trigger_s` herdado (0); a rampa ocupa os 200 ms; registro físico com 20 ms antes e 50 ms depois ({doc}`../medicao`).

:::{caution} Achado desta revisão (sem id de pendência)
`frequency_drift_list` **não** define o readback do transiente (o atributo `_transiente_esperado`, inicializado em [ametek_orm.py:271](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L271); só `trigger_step` e `trigger_pulse` o definem e só `program_capture` o zera). Se a 18 roda **logo depois** de uma classe STEP ou PULSe na mesma conexão, sem uma classe de TRACe no meio, o `arm()` confere a lista contra o STEP da classe anterior e recusa a captura (`InstrumentHardwareError`). Reproduzido offline com a fonte simulada em 2026-10-16: `trigger_step(127)` seguido de `frequency_drift_list(57, 63, ...)` e `_conferir_transiente_programado()` levanta "esperado 'STEP', lido 'LIST'". Em `run all` (a 17 vem antes) e em `run 18` isolado o problema não aparece; aparece em listas como `run 01-05,18` ou com `BATERIA_EXCLUIR` removendo as classes 06 a 17. {bdg-warning}`NÃO VERIFICADO` na bancada (só a simulação). Sugestão: zerar `_transiente_esperado` no início de `frequency_drift_list`; o código é somente leitura nesta etapa.
:::

## 5. Parâmetros por perfil

Esta classe não lê nenhum componente de `perfis.py` (`COMPONENTES_POR_CLASSE` não a lista): `gerar()` é igual nos três perfis.

A 18 é **independente do perfil**: não lê nenhum componente de `perfis.py`. O desvio é uma constante de módulo, `DESVIO_HZ = 3.0` ([18.py:14](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/18.py#L14)).

| Condição de f0 | Sorteio ligado (padrão) | `set sorteio off` |
|---|---|---|
| 60 Hz | 57 → 63 Hz (inverso nas capturas ímpares) | 57 → 63 Hz |
| 50 Hz | 47 → 53 Hz (inverso nas capturas ímpares) | 57 → 63 Hz (+14 % / +26 % da rede) |

*Fonte:* `Experimento.extremos_hz` ([experimentos_nativos/18.py:21-30](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/18.py#L21-L30)). Os limites de `frequency_drift_list` (45 a 500 Hz) cobrem as duas.

## 6. Limites físicos e fator de extremo

A rampa não muda a amplitude: o pico programado é o da senoide base, e a fonte, ao trocar de ponto da lista, não produz degrau de tensão relevante (fator próximo de 1).

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,036 | 1 | 179,6 | 204,7 | 415,8 | 100 % | 1/1 rodam |
| 127 V/50 Hz | 1,075 | 1 | 179,6 | 212,4 | 415,8 | 100 % | 1/1 rodam |
| 230 V/50 Hz | 1,042 | 1 | 325,3 | 384,6 | 415,8 | 100 % | 1/1 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 1 | 311,1 | 504,8 | 415,8 | 100 % | 0/1 rodam, 1 pulada(s) |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 1 captura, sorteio ligado). A 220 V/60 Hz (sem tabela) a 18 é pulada: o fator conservador de 1,475 leva o extremo previsto acima de 415,8 V ({ref}`P-21 <p-21>`). Nativas não reduzem o distúrbio.

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. Na 18 o **THD** da janela mede o espalhamento espectral da rampa em torno de $f_0$ (a FFT é feita na frequência da rede); por isso o esperado não é zero e depende de quão longe vai a rampa.

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,711 / 0,707 | 0,684 / 0,691 | 0,740 / 0,724 | 0,003 / 0,002 | 1,436 / 1,415 |
| 127 V/50 Hz | 0,713 / 0,697 | 0,647 / 0,648 | 0,776 / 0,759 | 0,063 / 0,064 | 1,443 / 1,422 |
| 230 V/50 Hz | 0,703 / 0,697 | 0,642 / 0,648 | 0,765 / 0,759 | 0,060 / 0,064 | 1,429 / 1,422 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`). A 127 V/50 Hz a rampa era de **57 a 63 Hz** (código anterior à v1.15), +14 % a +26 % da rede, o que explica o THD de 6,3 % medido (6,4 % esperado) contra 0,3 % a 60 Hz; com a rampa de 47 a 53 Hz o espalhamento é menor. Medido e esperado concordam nas três condições.

## 8. As três versões e a correlação esperada

O `modelo` é a rampa linear; a `programada` (`sinais.forma_programada_nativa`, [sinais.py:624-683](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L624-L683)) é o degrau: `start_hz` na primeira metade da janela, `end_hz` na segunda, com fase contínua e a fase inicial do metadata. A continuidade da fase na troca de ponto da lista é {bdg-warning}`NÃO VERIFICADO` (P-06).

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 0,952–0,952 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 1,000 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,939–0,982 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 0,959 / 0,917 | 0,952–0,952 / 0,913–0,915 | 0,952 / 0,914 | 0,952 / 0,913–0,915 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 |
| modelo × medida | 0,982 / 0,964 | 0,939 / 0,960 | 0,982 / 0,964 |

Causa de a classe ficar abaixo de 0,90, quando fica: a programada troca de frequência em degrau (`start_hz` na 1.ª metade, `end_hz` na 2.ª) e o modelo é uma rampa linear: modelo × programada 0,95 (nominal) e 0,91 (ajustada); a fase na troca nunca foi medida (P-06)

O modelo × programada de 0,95 (nominal) e 0,91 (ajustada) vem inteiro da diferença rampa × degrau, não de erro da fonte; a fonte reproduz o degrau (programada × medida 1,000 em 07/10). O modelo × medida de 07/10 (0,939 a 60 Hz, 0,982 a 50 Hz) usa a rampa de 57 a 63 Hz a 50 Hz.

## 9. Quirks e armadilhas

- **A9:** `FUNCtion:MODE LIST` residual de uma classe de lista (a 17) faz o `VOLTage:MODE LIST` final dar `-226 Lists not same length`; `FUNCtion:MODE FIXed` primeiro resolve.
- **A4, A5:** `SOURce:LIST:REPeat 0,0`; sem `:COUNt`; `1` toca cada ponto duas vezes.
- **A11:** a saída fica no último ponto do `LIST`; `FREQuency:MODE FIXed` troca o modo, não o valor. `restaurar_frequencia_base` reescreve a frequência base ao fim de toda classe que a alterou.
- **A1, A7:** escrita em rajada se perdia; trocar o modo deixa a fonte muda por segundos.
- **Acoplamento:** `DESVIO_HZ` é usado por `gerar()` e por `configurar()` através de `extremos_hz()`; `forma_programada_nativa` lê `start_hz`/`end_hz` do metadata ({doc}`../codigo/acoplamentos`).
- **Achado desta revisão:** o readback do transiente fica obsoleto se a 18 roda logo depois de STEP/PULSe (seção 4).

## 10. Histórico por versão

- **v1.8:** a 18 alterna dois valores por `capture_index % 2` (a rampa e a inversa).
- **v1.10:** `SOURce:LIST:REPeat` passa de `"1,1"` a `"0,0"`: o valor `1` tocava cada ponto duas vezes na Rev. 5.53; o efeito foi parcial no `NOTCH` (516 ms para 438 ms).
- **v1.11:** a 18 depois da 17 dava `-226 Lists not same length` (a lista de forma de 12 pontos da 17 continuava ativa); a neutralização `FUNCtion:MODE FIXed` antes de programar resolveu.
- **v1.12:** F2: a 19 rodava a 63,03 Hz porque a 18 terminava no último ponto (THD por FFT de 5,00 % contra 0,00 %); `restaurar_frequencia_base`.
- **v1.15:** a rampa passa a ser $f_0-3 \to f_0+3$ Hz por `extremos_hz` (a 60 Hz idêntico; a 50 Hz era 57 → 63 Hz, +14 % / +26 % da rede, e vira 47 → 53 Hz); a restauração da frequência foi conferida e ganhou teste a 50 Hz; fase sorteada; `scripts/verificar_sessao_bancada.py` ganhou `fase_18` (salto de fase na troca; o limiar de 10° é proposta sem dado).

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| `LIST:FREQuency` de 2 pontos toca 57 → 63 Hz | {bdg-success}`VERIFICADO NA BANCADA` | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 07/10/2026; programada × medida 1,000 |
| `gerar()` e programada de hoje (f0 ± 3 Hz) | {bdg-info}`OFFLINE` | `Classes05_07_18Tests`; modelo × programada 0,952 |
| Rampa 47 → 53 Hz a 50 Hz | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15 |
| Continuidade de fase na troca `start_hz` → `end_hz` | {bdg-warning}`NÃO VERIFICADO` | nunca medida (o verificador só foi testado com sinal sintético) |
| Frequência base restaurada depois da rampa nova | {bdg-warning}`NÃO VERIFICADO` | conferida em teste, não em bancada |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
:::

:::{important} Pendência P-06
Continuidade de fase na troca de ponto do `LIST:FREQuency`, rampa 47 → 53 Hz a 50 Hz e `restaurar_frequencia_base` depois da rampa nova; o limiar de 10° do verificador é proposta sem dado. Fecha com: bancada. Prioridade MÉDIA.
:::

## 12. Como o código da classe funciona

| Símbolo | Recebe | Devolve | Quem chama |
|---|---|---|---|
| `DESVIO_HZ` ([experimentos_nativos/18.py:14](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/18.py#L14)) | nada | 3,0 Hz | `extremos_hz` |
| `Experimento.extremos_hz` ([experimentos_nativos/18.py:21-30](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/18.py#L21-L30)) | `f0`, `capture_index` | `(início, fim)` em Hz: `(f0 − 3, f0 + 3)` se `capture_index` par, o inverso se ímpar; `57/63` com `sorteio_posicao` desligado | `gerar` e `configurar` |
| `Experimento.gerar` ([experimentos_nativos/18.py:32-43](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/18.py#L32-L43)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"start_hz", "end_hz", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.configurar` ([experimentos_nativos/18.py:45-51](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/18.py#L45-L51)) | `capture_index` | `{"start_hz", "end_hz"}` | a linha [mestre.py:2972](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2972) de `ExperimentoNativo._capturar_real` |

- `gerar` calcula `fs_hz` do passo de `t`, monta a frequência instantânea com `numpy.linspace`, acumula a fase com `cumsum` e soma `deg2rad(sorteio.fase_graus)`; o sorteio é `self.sortear(rng, f0)` (só fase).
- `configurar` lê `self.config.grid_frequency_hz` (não o `f0` de `gerar`, que é o mesmo valor) e `duration_s / 2` para o `dwell`; chama `self.fonte.frequency_drift_list(start_hz, end_hz, voltage_rms=base, dwell_s=meio_s)`. Como `gerar` e `configurar` chamam `extremos_hz` com o mesmo `capture_index` e a mesma configuração, o programado e o modelo concordam por construção.
- Atributos: `capturas_padrao` e `pre_trigger_s` herdados; sem `NIVEIS`, `usar_trace` nem ganchos de redução.
- Contrato e acoplamentos: {doc}`../codigo/classes_contrato` §4 ("18: `DESVIO_HZ`").

## 13. Referências

- Código: `experimentos_nativos/18.py`; `logica/ametek_orm.py` (`frequency_drift_list`, `restaurar_frequencia_base`); `logica/sinais.py` (`forma_programada_nativa`).
- Site: {doc}`../classes`, {doc}`../scpi/sequencias` §6, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`, {doc}`../quirks`.
- Histórico: `CHANGELOG/v1.8.md`, `v1.10.md`, `v1.11.md`, `v1.12.md`, `v1.15.md` (seções "Classes 05, 07, 17 e 18" e "Pendentes de classe conferíveis offline"). Norma: IEEE Std 1159-2019, Tabela 2, item 7.0.
