# As 20 classes de distúrbio

{bdg-info}`OFFLINE` Lido no código em 2026-10-16 (`main` em `fa82f49`, v1.15 em andamento, sem tag). {bdg-success}`VERIFICADO NA BANCADA` só com o código anterior à v1.15 (campanha de 07/10/2026). {bdg-warning}`NÃO VERIFICADO` o que a v1.15 mudou ({ref}`P-01 <p-01>`).

**Pergunta:** o que são as 20 classes e onde está a explicação completa de cada uma? **Resposta:** são 20 formas de onda de **200 ms = 6000 amostras a 30 kSa/s, em pu do pico nominal**, que `gerar(t, f0, capture_index, rng)` produz (`ExperimentoBase.gerar`, `mestre.py:1662-1667`); cada uma tem uma **ficha** própria (tabela abaixo) que conta o fenômeno, a norma, o modelo, o que a bancada faz, os limites, a validação, o histórico e o que falta verificar. No dataset **simulado** só `gerar()` importa. Na **bancada** a classe é **nativa** (a fonte produz o distúrbio com um recurso próprio: STEP, PULSe, CSINusoid, lista de frequência, ACDC) ou de **forma de onda** (o Python calcula a forma e a fonte a toca por TRACe/LIST).

A especificação original está em `experimentos.txt`. As faixas por perfil, em {doc}`perfis`. Como criar uma classe, em {doc}`estender`. O contrato do arquivo `NN.py` e dos ganchos, em {doc}`codigo/classes_contrato`.

(tabela-das-20-classes)=
## 1. Tabela e fichas

Legenda: **Sorteio** = o que `gerar()` sorteia com `set sorteio on` (padrão): F = fase; I = início; D = duração. **Pad.** = `capturas_padrao`. **Perfil** = a classe muda (sim) ou não (não) com `set perfil` ({doc}`perfis`). Cada número da primeira coluna é um link para a ficha.

| Ficha | Nome | Arquivo | Mecanismo na bancada | Parâmetros (perfil `literatura`) | Sorteio | Pad. | Perfil | Estado (código anterior à v1.15; pendências) |
|---|---|---|---|---|---|---|---|---|
| {doc}`01 <classes/01-normal>` | NORMAL | nativos/01 | STEP para a base (`trigger_step`), só gera o trigger | — | F | 1 | não | medida; {ref}`P-05 <p-05>` |
| {doc}`02 <classes/02-sag>` | SAG | nativos/02 | PULSe (`trigger_pulse`) | nível 0,1/0,3/0,5/0,7/0,9 pu por `capture_index` | I D F | 1 | sim | medida no nível 0,1; {ref}`P-05 <p-05>` |
| {doc}`03 <classes/03-swell>` | SWELL | nativos/03 | PULSe | 1,1/1,2/1,4/1,6/1,8 pu | I D F | 1 | sim | medida no nível 1,1; fora a 230 V/50 Hz; {ref}`P-05 <p-05>` |
| {doc}`04 <classes/04-interruption>` | INTERRUPTION | nativos/04 | PULSe | nível U(0; 0,09) pu | I D F | 3 | não | medida; {ref}`P-05 <p-05>` |
| {doc}`05 <classes/05-harmonics>` | HARMONICS | nativos/05 | até 20 % de THD: `SOURce:FUNCtion:SHAPe CSINusoid` + `:CSINusoid <THD>` (senoide clipada); acima: TRACe | THD 5/10/15/20/30 % | F | 1 | sim | só THD de 5 %; {ref}`P-10 <p-10>` |
| {doc}`06 <classes/06-flicker>` | FLICKER | waveform/06 | TRACe/LIST | modulação U(8; 25) Hz, profundidade U(0,05; 0,15) | F | 3 | sim | medida; correlação 0,83–0,96; {ref}`P-12 <p-12>` |
| {doc}`07 <classes/07-notch>` | NOTCH | waveform/07 | TRACe/LIST | 2–4 pulsos de 0,1 ms por ciclo nos picos, em **todos** os ciclos | F | 3 | não | medida com 4 ciclos; {ref}`P-07 <p-07>` |
| {doc}`08 <classes/08-transient>` | TRANSIENT | waveform/08 | TRACe/LIST | impulso de 2 amostras (50 µs), U(5; 10) pu no modelo | — | 3 | não | só como impulso filtrado; {ref}`P-02 <p-02>`, {ref}`P-03 <p-03>` |
| {doc}`09 <classes/09-oscillatory-transient>` | OSCILLATORY_TRANSIENT | waveform/09 | TRACe/LIST | f U(300; 2400) Hz, duração U(10; 40) ms, 0,3 pu, τ = 5 ms | I F | 3 | não | medida com defeito A25; {ref}`P-02 <p-02>` |
| {doc}`10 <classes/10-sag-harmonics>` | SAG_HARMONICS | waveform/10 | TRACe/LIST | sag U(0,1; 0,9), THD U(0,05; 0,20) | I D F | 3 | sim | medida com parâmetros fixos; {ref}`P-08 <p-08>`, {ref}`P-09 <p-09>`, {ref}`P-11 <p-11>` |
| {doc}`11 <classes/11-sag-flicker>` | SAG_FLICKER | waveform/11 | TRACe/LIST | sag, profundidade (faixa da 06), flicker U(8; 25) Hz | I D F | 3 | sim | idem 10; {ref}`P-12 <p-12>` |
| {doc}`12 <classes/12-sag-oscillatory-transient>` | SAG_OSCILLATORY_TRANSIENT | waveform/12 | TRACe/LIST | sag, oscilação U(300; 2400) Hz | I D F | 3 | sim | idem 10 |
| {doc}`13 <classes/13-swell-harmonics>` | SWELL_HARMONICS | waveform/13 | TRACe/LIST | swell U(1,1; 1,8), THD U(0,05; 0,20) | I D F | 3 | sim | idem 10; {ref}`P-11 <p-11>` |
| {doc}`14 <classes/14-swell-oscillatory-transient>` | SWELL_OSCILLATORY_TRANSIENT | waveform/14 | TRACe/LIST | swell, oscilação | I D F | 3 | sim | idem 10; 0/3 a 230 V/50 Hz |
| {doc}`15 <classes/15-harmonics-flicker>` | HARMONICS_FLICKER | waveform/15 | TRACe/LIST | THD, profundidade, flicker (200 ms inteiros) | F | 3 | sim | idem 10; {ref}`P-12 <p-12>` |
| {doc}`16 <classes/16-interruption-harmonics>` | INTERRUPTION_HARMONICS | waveform/16 | TRACe/LIST | 0,05 pu + THD U(0,05; 0,20) | I D F | 3 | sim (não com `set sorteio off`) | idem 10 |
| {doc}`17 <classes/17-notch-oscillatory-transient>` | NOTCH_OSCILLATORY_TRANSIENT | waveform/17 | TRACe/LIST | entalhes contínuos (como 07) + oscilação de 300 Hz em `t0` | I F (fase acoplada a `t0`) | 3 | não | medida com 4 ciclos; {ref}`P-07 <p-07>` |
| {doc}`18 <classes/18-frequency-drift>` | FREQUENCY_DRIFT | nativos/18 | `LIST:FREQuency` de 2 pontos (`frequency_drift_list`) | rampa f0−3 → f0+3 Hz (e o inverso nas capturas ímpares) | F | 1 | não | medida (57 → 63 Hz); {ref}`P-06 <p-06>` |
| {doc}`19 <classes/19-dc-offset>` | DC_OFFSET | nativos/19 | `SOURce:MODE ACDC` + `SOURce:VOLTage:OFFSet` | offset U(0,02; 0,10) pu | F | 3 | não | medida; CA 5–6 % abaixo; {ref}`P-17 <p-17>` |
| {doc}`20 <classes/20-interharmonics>` | INTERHARMONICS | waveform/20 | TRACe/LIST | 3 componentes em 145/210/330 Hz, amplitude U(0,03; 0,08) cada | F | 3 | sim | medida; {ref}`P-01 <p-01>` |

*Fontes:* arquivos das classes (`experimentos_nativos/NN.py`, `experimentos_waveform/NN.py`); `capturas_padrao` e sorteio conferidos por leitura e por `capturas_efetivas_da_classe` (`mestre.py:3216-3240`; 50 capturas planejadas com os padrões); independência de perfil de `perfis.classes_independentes_do_perfil` com o sorteio ligado. As compostas 10 a 16 sorteiam os parâmetros listados com `perfis.composto` quando o sorteio está ligado; desligado, valem os valores fixos de {doc}`perfis`. O estado vem de {doc}`projeto/estado-validacao`.

### Onde o código difere de `experimentos.txt`

- **Início, duração e fase.** A especificação fixa 60 ms / 60 ms (80 ms nas 08 e 09). Com o sorteio ligado eles são sorteados por `sortear_posicao` (`mestre.py:870-915`): início a pelo menos 1 ciclo da borda, duração de meio ciclo até 200 ms menos 2 ciclos, fase $\mathcal{U}(0°;\,360°)$ em passos de 0,1° (seção 2). `set sorteio off` reproduz as posições fixas.
- **05:** o modelo dos níveis ≤ 20 % é a senoide clipada normalizada por rms (`sinais.senoide_clipada_pu`), não a soma de harmônicas; só o nível por TRACe (30 %) usa a soma 3.ª/5.ª/7.ª ({doc}`classes/05-harmonics`).
- **07 e 17:** entalhes em **todos** os ciclos da janela (IEEE 1159-2019, 4.4.5.4), não só 4 ciclos a partir de 60 ms ({doc}`classes/07-notch`, {doc}`classes/17-notch-oscillatory-transient`).
- **18:** rampa $f_0 \pm 3$ Hz (47 → 53 Hz a 50 Hz); com o sorteio desligado, 57 → 63 Hz ({doc}`classes/18-frequency-drift`).
- **20:** frequências 145, 210 e 330 Hz; o 150 Hz foi removido por ser a 2,5.ª harmônica a 60 Hz ({doc}`classes/20-interharmonics`).
- **Perfis `norma` e `fronteira`** mudam os níveis das 02, 03, 05, 06, 10 a 16 e 20 ({doc}`perfis`).
- A especificação cita **400 capturas por nível ou faixa**; o número real é `SIM_CAPTURES_PER_CLASS` (simulado) ou o plano da bancada (seção 3).

(sorteio-de-posicao)=
## 2. O sorteio de início, duração e fase

**Pergunta:** o que `gerar()` sorteia além dos parâmetros da classe? **Resposta:** a posição do evento e a fase da senoide, a partir de um **sub-fluxo** da mesma seed, de modo que os parâmetros que a classe já sorteava (flicker, amplitude, nível) não mudam para uma seed dada.

`sortear_posicao` (`mestre.py:870-915`) devolve um `Sorteio` (`mestre.py:826-854`: `ativo`, `inicio_s`, `duracao_s`, `fase_graus`). Com $T$ = 200 ms, $T_\text{ciclo}=1/f_0$, $t_\min$ = `SORTEIO_TMIN_CICLOS` = 1 ciclo (`mestre.py:815`) e $d_\min$ = `SORTEIO_DURACAO_MIN_CICLOS` = 0,5 ciclo (`mestre.py:816`):

$$
d\sim\mathcal{U}\big(0{,}5\,T_\text{ciclo},\;T-2\,T_\text{ciclo}\big),\qquad
t_0\sim\mathcal{U}\big(T_\text{ciclo},\;T-d-T_\text{ciclo}\big),\qquad
\theta\sim\mathcal{U}(0°;\,360°),\quad \varphi=(\theta-360\,f_0\,t_0)\bmod 360°
$$

$d$ só é sorteada nas classes com `duracao_variavel` (02, 03, 04, 10, 11, 12, 13, 14, 16); nas outras vale a duração legada. $d$ e $t_0$ ficam na **grade de amostragem** (`round(x · fs)/fs`) e $\theta$ na resolução de 0,1° (`SORTEIO_FASE_RESOLUCAO_GRAUS`, `mestre.py:818`, a de `TRIGger:SYNChronize:PHASe`). $\theta$ é a fase da senoide **no instante $t_0$** (a que o disparo da fonte reproduz); $\varphi$ é a fase em $t=0$, que entra em `gerar()` como $\tau=\varphi/(360 f_0)$ somado a todo termo periódico (`Sorteio.deslocamento_s`, `mestre.py:840-844`). Sem evento localizado, $\theta$ é a própria fase em $t=0$. Na 17 a fase é acoplada ao início ($\theta=0$: a senoide cruza zero em $t_0$).

O sub-fluxo vem de `_rng_do_sorteio` (`mestre.py:857-867`): uma `SeedSequence` filha da seed da captura (`spawn_key` acrescido de `_CHAVE_DO_SUBFLUXO`) sorteia sempre três números em ordem (duração, início, fase), independente de quantas vezes o `rng` da classe já foi usado. Os valores saem no metadata como `inicio_disturbio_s`, `duracao_s` e `fase_graus` (`Sorteio.parametros`, `mestre.py:846-854`).

| | 60 Hz | 50 Hz |
|---|---|---|
| $t_\min$ (1 ciclo) | 16,7 ms | 20,0 ms |
| $d_\min$ (½ ciclo) | 8,3 ms | 10,0 ms |
| $d_\max = T-2T_\text{ciclo}$ | 166,7 ms (10 ciclos) | 160,0 ms (8 ciclos) |
| Posições legadas (`set sorteio off`) | 60 ms / 60 ms (02, 03, 04, 10, 11, 13, 16, 17); 60 ms / 40 ms (12, 14); 80 ms com duração U(10; 40) ms (09); entalhes em 80 ms a partir de 60 ms (07) | idem |

*Fonte:* cálculo das constantes de `mestre.py` (2026-10-16). A **08 fica fora do sorteio**: o sobressinal do degrau foi calibrado para um ponto de partida (seção 4 e {doc}`classes/08-transient`).

**Nas nativas** (01 a 05, 18, 19) `ExperimentoNativo._capturar_real` reproduz o sorteio na bancada: pré-trigger do osciloscópio $=t_0$ mais 20 ms de margem (`definir_pre_trigger`), fase de disparo $\theta$ em `TRIGger:SYNChronize:PHASe` (`fase_de_disparo_graus`) e, nas PULSe, `PULSe:WIDTh` $=d$. **Nenhum desses três foi medido** com o código da v1.15 ({ref}`P-05 <p-05>`).

(validacao-fisica-tolerancias)=
## 3. A validação física: as sondas e as tolerâncias

**Pergunta:** como a bancada decide que uma captura corresponde à classe? **Resposta:** `ExperimentoBase._validar_fisicamente` (`mestre.py:1827-1894`) compara o medido, recortado em `medido[margem_antes : margem_antes + 6000]`, com a forma **realmente programada**, por `sinais.comparar_fisicamente` (`sinais.py:360-456`), com **quatro sondas**; reprovada, a captura é **gravada** com `validacao_fisica.ok = false` (não é descartada).

| Sonda | O que pega | Tolerância | Onde |
|---|---|---|---|
| mediana, mínimo e máximo do envelope rms de meio ciclo | regime errado (127 V onde 220 V foram programados), afundamento ou elevação que não aconteceu, interrupção que virou elevação | 15 % do alvo, com piso absoluto de 5 % da mediana esperada | `VALIDACAO_TOL_ENVELOPE`, `mestre.py:704` |
| THD do registro | CSINusoid que não foi aplicada (5,05 % de referência contra 0,98 % medidos em 16/09/2026) | 20 % relativos, piso absoluto de 1 % | `VALIDACAO_TOL_THD`, `mestre.py:705`; `piso_thd` em `sinais.py:360-456` |
| fator de crista do ciclo mediano | forma grosseira | 10 %, **bilateral**: aceita $[c_\text{modelo}\,(1-0{,}10),\;c_\text{modelo}\cdot g\,(1+0{,}10)]$, com $g$ o fator de extremo calibrado da classe | `ExperimentoBase.fator_extremo_efetivo_para_validacao`, `mestre.py:1896-1920` |
| posição do evento (só a 08) | impulso fora do lugar | maior desvio da senoide a até 10 amostras do início previsto | `conferir_posicao_do_evento` da 08 |

O fator $g$ é o mesmo que a previsão de pico usa, sem a margem de 1,10 (a tolerância de 10 % da crista já é a folga); com o distúrbio reduzido pelo limite de bancada usa a fórmula de `extremo_previsto_com_disturbio_v` com margem 1; a 08 usa 1,0 ({doc}`limites_e_calibracao` §4). O THD tem **piso** de 1 % para uma classe sem harmônicos programados nunca ser reprovada por ruído do osciloscópio. Detalhes do percurso em {doc}`codigo/percurso-captura-trace` §3.

(capturas-por-classe)=
## 4. Capturas por classe na bancada

O número que roda é `max(set capturas N ou REAL_CAPTURES_PER_CLASS, capturas_padrao da classe)`, **por nível** nas classes com níveis (02, 03, 05) (`Config.capturas`, `mestre.py:790-805`; `ExperimentoBase.dimensionar_capturas`, `mestre.py:1684-1701`). O padrão é 3 nas classes cujo `gerar()` sorteia parâmetros: **04, 06 a 17, 19 e 20**; é 1 nas demais (01, 02, 03, 05, 18). Com os padrões são **50 capturas planejadas** (1+1+1+3+1+36+1+3+3).

Consequência para as classes com níveis: **sem `set capturas`, a 02, a 03 e a 05 rodam só o nível 0** (0,1 pu, 1,1 pu e THD de 5 %); com `set capturas N`, N capturas por nível, de modo que os cinco níveis exigem `set capturas` digitado.

Sem `set capturas` as capturas padrão **sorteiam** (a 08 aplica o impulso máximo seguro em todas). Com `set capturas` (qualquer N), a 04, a 06, a 09 e a 19 cobrem o intervalo do parâmetro com `linspace` (`sinais.valor_para_captura`, `sinais.py:24-49`) e a 08 faz a rampa de caracterização sobre o total efetivo.

**Seed da captura:** `BASE_SEED + int(id) × 1 000 000 + indice_global` (`ExperimentoBase.seed_da_captura`, `mestre.py:1703-1707`). A 04 e a 19 repetem essa conta em `configurar()` com o id fixo (`base_seed + 4_000_000 + capture_index`, `04.py:37`; `base_seed + 19_000_000 + capture_index`, `19.py:33`): só vale porque nessas classes `capture_index == indice_global`.

## 5. Quatro casos que pedem leitura à parte

- **Classe 08, o impulso filtrado pela fonte.** A bancada não reproduz o impulso de 5 a 10 pu e 50 µs do modelo; a captura física é um impulso de baixa amplitude filtrado pela fonte (um pico seguido de oscilação de ~7,5 a 10 kHz que morre em menos de 0,5 ms), por **três limitações independentes** (amplitude, velocidade e representação). Amplitudes seguras por condição, posição a 80 ms (60 Hz) e a 90 ms (50 Hz), e o mecanismo ainda não explicado do deslocamento a 100 ms: {doc}`classes/08-transient`.
- **Classe 05 e o teto de 20 % da CSINusoid.** `MAX_CSINE_THD_PCT = 20` (`ametek_orm.py:163`); os níveis até 20 % saem pela senoide clipada nativa e o de 30 % por TRACe. Rms e fundamental de cada nível, e o que nunca foi medido: {doc}`classes/05-harmonics`.
- **Classe 06 e a média de cada ciclo da TRACe.** A fonte remove o componente CC de cada ciclo, e o flicker tem média não nula por ciclo; é todo o desvio entre modelo e programada (correlação 0,77 a 1,00): {doc}`classes/06-flicker`.
- **Classe 09 e o impulso em 100 ms.** A medida tem um impulso de 0,12 a 0,27 pu em 100,0 a 100,2 ms que a forma programada não tem; mecanismo {bdg-warning}`NÃO VERIFICADO` (quirk A25): {doc}`classes/09-oscillatory-transient`.

```{toctree}
:maxdepth: 1
:caption: Fichas das classes

classes/01-normal
classes/02-sag
classes/03-swell
classes/04-interruption
classes/05-harmonics
classes/06-flicker
classes/07-notch
classes/08-transient
classes/09-oscillatory-transient
classes/10-sag-harmonics
classes/11-sag-flicker
classes/12-sag-oscillatory-transient
classes/13-swell-harmonics
classes/14-swell-oscillatory-transient
classes/15-harmonics-flicker
classes/16-interruption-harmonics
classes/17-notch-oscillatory-transient
classes/18-frequency-drift
classes/19-dc-offset
classes/20-interharmonics
```
