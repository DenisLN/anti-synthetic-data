# Classe 16: INTERRUPTION_HARMONICS

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 com THD fixo (interrupção de 0,05 pu e THD 20 %; 127 V/60 Hz e 127 V/50 Hz, 1 captura cada, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` THD sorteado, rms CA por ciclo, 230 V/50 Hz {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-08` {bdg-danger}`PENDENTE P-09` {bdg-danger}`PENDENTE P-11` {bdg-danger}`PENDENTE P-18` {bdg-danger}`PENDENTE P-19`

| Campo | Valor |
|---|---|
| Número e nome | 16 INTERRUPTION_HARMONICS (interrupção com harmônicos) |
| Arquivo | `experimentos_waveform/16.py`, classe `Experimento(ExperimentoWaveform)` |
| Mecanismo na bancada | **forma de onda**: TRACe/LIST ({scpi}`TRACe:DATA`, {scpi}`SOURce:LIST:VOLTage`, um passo por ciclo) |
| `capturas_padrao` | 3 ([16.py:18](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/16.py#L18)) |
| Sorteio de posição | I D F, mais o THD; a interrupção é **fixa** em 0,05 pu |
| Depende do perfil? | **sim com o sorteio ligado** (a `norma` sorteia THD desde 2 %); **não** com `set sorteio off` (só `thd_composto`, igual nos três perfis) |
| Condições já medidas | 127 V/60 Hz e 127 V/50 Hz, 1 captura cada (230 V/50 Hz foi pulada em 07/10) |

## 1. Em uma resposta

**Pergunta:** como o dataset combina uma interrupção com harmônicos? **Resposta:** durante o evento (início e duração sorteados) a tensão cai a **0,05 pu fixos** e os 3.º, 5.º e 7.º harmônicos (THD sorteado entre 5 e 20 %) ficam escalados por esse nível, ou seja, quase só harmônicos sobre ~zero; fora do evento a senoide é limpa. É a composta cuja **volta** mais sobressai: o fator de extremo de 1,475 a 127 V/60 Hz é o maior de todas as tabelas (262 V medidos com 180 V programados, v1.12), e a mais afetada pela perda da média dos ciclos de borda (erro programada × modelo até 0,33 pu).

## 2. O fenômeno e a norma

Composta da interrupção (item 2.2.1 da Tabela 2 da IEEE Std 1159-2019, abaixo de 0,1 pu, de 0,5 ciclo a 3 s) com a distorção harmônica (item 5.2, 0 a 20 % de THD). A norma não define a composição. A especificação (`experimentos.txt`, classe 16) pede interrupção abaixo de 0,1 pu e THD 20 % no mesmo período, início 60 ms, duração 60 ms. O nível da interrupção **não é sorteado** de propósito: o limite de interrupção da norma é 0,1 pu, e sortear o nível dentro da faixa deixaria de ser interrupção em parte das capturas (decisão de projeto (e) de `docs/perfis.md`).

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v(t)=\begin{cases}
0{,}05\;\big[\sin\theta+a_3\sin3\theta+a_5\sin5\theta+a_7\sin7\theta\big] & t_0\le t<t_0+d\\[2pt]
\sin\theta & \text{caso contrário}
\end{cases},\qquad \mathrm{THD}\sim\mathcal{U}(0{,}05;\,0{,}20)
$$

(Os $a_k$ como na {doc}`10-sag-harmonics`.) Dentro do evento, o harmônico de 3.ª ordem de 20 % tem amplitude $0{,}05\cdot0{,}1769\approx0{,}009$ pu: a forma é quase nula. $t_0$, $d$ e $\varphi$ vêm do sorteio de posição ({ref}`fórmulas <sorteio-de-posicao>`; sem sorteio, 60 ms e 60 ms).

```{literalinclude} ../../experimentos_waveform/16.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_waveform/16.py, Experimento.gerar
```

- **Ordem do `rng`:** uma única chamada a `perfis.composto` (`thd_composto`); o sorteio de posição vem de um sub-fluxo.
- **Parâmetros no metadata:** `interruption_pu` (sempre 0,05), `thd`, `inicio_disturbio_s`, `duracao_s`, `fase_graus`.
- **Seed:** `base_seed + 16 · 1 000 000 + indice_global`.
- **Capturas:** `capturas_padrao` = 3 ([16.py:18](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/16.py#L18)).

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** a fonte chega perto de zero por um trecho em lista de TRACes? **Resposta:** chega: o passo de interrupção tem rms de ~0,05 pu, e o degrau entre os passos é o maior possível; a saída oscila ao voltar (A20) e o pico medido passa muito do programado.

Ordem dos comandos de uma captura (`ExperimentoWaveform._capturar_real`, [mestre.py:3126-3188](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3126-L3188); diagrama e porquês em {doc}`../scpi/sequencias` §7 e o percurso completo em {doc}`../codigo/percurso-captura-trace`):

1. `gerar()` produz a forma e os parâmetros; a forma tem de ter 6000 valores finitos, senão `RuntimeError` (bug de código, não é descartável).
2. `forma_para_bancada` (sem SCPI): limita o pico (só a 08) e aplica o **limite de bancada** $k$ ({doc}`../limites_e_calibracao` §3), que reduz só o distúrbio quando o extremo previsto passa do teto.
3. `AmetekMX30.program_capture` ([ametek_orm.py:1511-1705](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1511-L1705)), que começa por `montar_programacao` (função pura, [ametek_orm.py:1416-1509](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1416-L1509)): corta a forma em ciclos de $30000/f_0$ amostras (500 a 60 Hz, 12 ciclos; 600 a 50 Hz, 10 ciclos), tira a média de cada ciclo, reamostra para 1024 pontos, normaliza pelo pico e calcula o rms da componente CA do ciclo. Depois envia, nesta ordem:
    - {scpi}`ABORt`, {scpi}`*CLS`, {scpi}`FUNCtion:MODE` `FIXed`, {scpi}`VOLTage:MODE` `FIXed` (com `assert_no_errors`), {scpi}`SOURce:MODE` `AC`, {scpi}`SOURce:FREQuency` $f_0$, {scpi}`SOURce:FREQuency:MODE` `FIXed`, {scpi}`SOURce:FUNCtion:SHAPe` `SINusoid`, {scpi}`SOURce:VOLTage` base;
    - se a assinatura (bytes da forma, nomes, tensão, frequência e offset) é a da última programação da conexão **e** {scpi}`TRACe:CATalog?` ainda lista as TRACes, a gravação é pulada; com o sorteio ligado a forma muda a cada captura e o cache nunca acerta;
    - {scpi}`TRACe:DEFine` `TCCnn` das TRACes que faltam (3 s de espera cada) e, para cada ciclo, {scpi}`TRACe:DATA` `TCCnn,<1024 valores>` seguido de 1 s de espera e {scpi}`*CLS`, **sem consultar a fonte** (quirk A2);
    - {scpi}`SOURce:LIST:FUNCtion:SHAPe` (os nomes), {scpi}`SOURce:LIST:VOLTage` (o rms CA de cada ciclo, `%.8g`) e {scpi}`SOURce:LIST:DWELl` (um período exato por passo), cada um confirmado por {scpi}`SOURce:LIST:FUNCtion:POINts?` e as consultas irmãs;
    - {scpi}`SOURce:LIST:REPeat` `0,…,0`, {scpi}`SOURce:LIST:COUNt` `1`, {scpi}`SOURce:LIST:STEP` `AUTO`, {scpi}`FUNCtion:MODE` `LIST`, {scpi}`VOLTage:MODE` `LIST`, {scpi}`TRIGger:SOURce` `BUS`, {scpi}`TRIGger:SYNChronize:SOURce` `PHASe`, {scpi}`TRIGger:SYNChronize:PHASe` `0`, {scpi}`OUTPut:TTLTrg:MODE` `TRIG`, {scpi}`OUTPut:TTLTrg:SOURce` `BOT` e {scpi}`OUTPut:TTLTrg` `ON`, cada um seguido de {scpi}`SYSTem:ERRor?`;
    - se o `ABORt` derrubou o relé, religa a saída ({scpi}`OUTPut:STATe`), só se a saída já estava autorizada.
4. Escala vertical do osciloscópio: {scpik}`:CHANnel<n>:SCALe` para o maior entre o pico programado vezes o *headroom* (1,25; 1,60 se o pico passa de 3 vezes o nominal) e o extremo previsto.
5. Osciloscópio armado ({scpik}`:AER?`, {scpik}`:TER?`, {scpik}`:SINGle`, espera do bit de armado em {scpik}`:OPERegister:CONDition?`) **antes** da fonte.
6. `AmetekMX30.arm_transient` ([ametek_orm.py:1823-1908](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1823-L1908)): espera `IDLE`; lê de volta nove parâmetros da lista; {scpi}`*WAI`; {scpi}`INITiate:IMMediate`; espera `ARM` ou `WTRIG`. Nunca repete o `ABORt` (quirk A16).
7. `AmetekMX30.trigger` ([ametek_orm.py:1910-1922](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1910-L1922)): {scpi}`TRIGger:STATe?` e {scpi}`*TRG`; a lista toca e o BOT segue pelo BNC ao EXT Trigger.
8. Espera dos dois lados e leitura: {scpik}`:WAVeform:PREamble?` e {scpik}`:WAVeform:DATA?` (o `indice_trigger` sai da preamble), depois {scpik}`:MEASURE:VMAX?` e {scpik}`:MEASURE:VMIN?` sobre o registro bruto (extremos de segurança).

O gancho `parametros_com_disturbio_reduzido` ([16.py:32-39](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/16.py#L32-L39)) devolve `interruption_pu_bancada` $=1+k(0{,}05-1)$ e `thd_bancada` $=k\cdot0{,}05\cdot\mathrm{THD}/\text{nivel}$.

**Janela e margem.** `pre_trigger_s` herdado (0); registro de 20 ms antes e 50 ms depois ({doc}`../medicao`).

**Por que a programada perde a média dos ciclos de borda.** O evento começa em $t_0$ e termina em $t_0+d$, que em geral não caem em fronteiras de ciclo. Nos ciclos de borda a forma tem um degrau a meio ciclo e, portanto, **média diferente de zero**. A fonte remove o componente CC de cada TRACe (manual, `TRACe:DATA`, p. 126) e a escala ao rms de `LIST:VOLTage`, e `SOURce:VOLTage:OFFSet` é um valor único da captura, não um offset por passo de `LIST` (o manual extraído não tem esse comando). O que a correção do rms por ciclo da TRACe mediu (127 V, `gerar()` com sorteio ligado, seed 32):

- **Antes da correção** o `LIST:VOLTage` levava o rms do ciclo **com** a média, mas a TRACe seguia **sem** ela: a amplitude CA saía inflada e a previsão de pico subestimava até 38 % (106,9 a 141,2 V previstos contra 153,3 a 172,1 V emitidos, com degraus sintéticos de nível 0,2 a 0,8 a 50 e 60 Hz).
- **Depois** (rms CA no `LIST:VOLTage`, pico previsto pela TRACe enviada) a previsão coincide com o emitido (diferença menor que 1 %), e **resta a média do ciclo**: erro máximo |programada − modelo| de 0,24 a 0,33 pu nas classes 10, 11, 12 e 16. Contra o modelo **sem** a média de cada ciclo, o erro cai a 0,02–0,04 pu. Só um offset por passo (modo ACDC, que tem o déficit de 5 a 6 % de CA da classe 19) o recuperaria.
- Que a fonte real escale a TRACe ao rms CA programado, como prevê o manual, e que o pico emitido nas classes 10, 11, 12 e 16 continue dentro de 425 Vp com o novo `LIST:VOLTage` são {bdg-warning}`NÃO VERIFICADO`: só a bancada confirma (comparar `pico_medido_v` e `vale_medido_v` com `extremo_previsto_v`, {ref}`P-08 <p-08>`).

| Erro máximo \|programada − modelo\| (pu) | 50 Hz, 127 V | 60 Hz, 230 V |
|---|---|---|
| antes da correção do rms CA | 0,4368 | 0,3904 |
| depois (código de hoje) | 0,3300 | 0,3039 |

*Fonte:* `CHANGELOG/v1.15.md`, "RMS por ciclo da TRACE" (`gerar()` com sorteio ligado, seed 32, simulação offline, sem hardware).

O erro da 16 é o **maior das compostas**: 0,33 pu a 50 Hz e 0,30 pu a 60 Hz depois da correção (eram 0,44 e 0,39 pu), porque o degrau é o de 1 pu para 0,05 pu e os ciclos de borda têm média grande.

:::{warning} Decisão em aberto P-09
Resta a média de cada ciclo de borda; só um offset por passo (modo ACDC, com o déficit de 5 a 6 % de CA da classe 19) a recuperaria. Investigar depois da primeira bancada com o código da v1.15? Decisão do responsável pelo projeto ({ref}`P-09 <p-09>`, prioridade BAIXA).
:::

:::{warning} Decisão em aberto P-04
`AmetekMX30.program_capture` só **avisa** quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga", [ametek_orm.py:1522-1527](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1522-L1527)); quem recusa é a pré-validação do `mestre.py` (`ExperimentoBase._indices_viaveis`, antes de qualquer SCPI, e `_conferir_extremos_fisicos`, depois da captura já gravada). Pergunta ao responsável pelo projeto: o ORM também deve recusar? Opções: manter como está, ou recusar no ORM (um limite de segurança mais restritivo). Este site não decide ({ref}`P-04 <p-04>`, prioridade MÉDIA).
:::

:::{warning} Decisão em aberto P-23
A fonte travou na ~280.ª gravação de TRACe de uma mesma conexão (quirk A3; causa {bdg-warning}`NÃO VERIFICADO`), e cada captura desta classe grava 12 TRACes a 60 Hz (10 a 50 Hz). `README.md` e `AGENTS.md` ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `set perfil todos`), enquanto o roteiro de bancada usa listas de classes (menos de 250 por conexão). Pergunta: qual texto os documentos devem adotar? Opção recomendada pelo roteiro: listas (`run 01-07`, depois `run 09-20`). Decisão do responsável pelo projeto ({ref}`P-23 <p-23>`, prioridade MÉDIA).
:::

## 5. Parâmetros por perfil

**O que o sorteio cobre em cada componente.** Na 16 o único componente sorteado é o **THD** (5 a 20 % na `literatura`; 2 a 20 % na `norma`); a interrupção fica em 0,05 pu (decisão (e)). É a extensão (f) do THD sorteado em 13, 15 e 16 ({ref}`o que o sorteio cobre <sorteio-das-compostas>`).

| Componente em `perfis.py` | `norma` | `literatura` (padrão) | `fronteira` |
|---|---|---|---|
| `thd_composto` | sorteio off: 0,2; sorteio on: U(0,02; 0,2) | sorteio off: 0,2; sorteio on: U(0,05; 0,2) | sorteio off: 0,2; sorteio on: U(0,05; 0,2) |

Com `set sorteio off` o THD vale 20 % nos três perfis (por isso a 16 vira independente do perfil). O perfil `fronteira` usa o THD da literatura.

## 6. Limites físicos e fator de extremo

A 16 tem o **maior fator de extremo de todas as tabelas**: **1,475** a 127 V/60 Hz (a v1.12 mediu 262 V com 180 V programados, ~46 %; em 07/10 mediu 263 V, razão 1,464), mas **1,030** a 127 V/50 Hz. Na tabela de 230 V/50 Hz **não há entrada** da 16 (ela foi pulada), então a regra por frequência a trata com o maior fator das tabelas de 50 Hz (1,030).

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,475 | 3 | 179,6 | 291,4 | 415,8 | 100 % | 3/3 rodam |
| 127 V/50 Hz | 1,030 | 3 | 179,6 | 203,5 | 415,8 | 100 % | 3/3 rodam |
| 230 V/50 Hz | sem entrada | 3 | 325,3 | 368,5 | 415,8 | 100 % | 3/3 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 3 | 311,1 | 415,8 | 415,8 | 37 % | 3/3 rodam |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 3 capturas padrão, seed 20260827, sorteio ligado). A 230 V/50 Hz a 16 **roda** pela regra por frequência (extremo previsto 368,5 V = 325,3 V × 1,030 × 1,10); em 07/10, com a regra anterior (maior fator de todas as tabelas, 1,475), foi pulada. A 220 V/60 Hz (sem tabela) as três rodam reduzidas a 37 %, e a 16 reduzida é **quase um afundamento** (`interruption_pu_bancada` = 0,65 pu, THD de 0,35 a 0,52 % no evento): representa mal "interrupção + harmônicos" (v1.13). A fórmula do limite de bancada em {doc}`../limites_e_calibracao` §3.

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. O mínimo do envelope confere a interrupção; o piso absoluto da tolerância (5 % da mediana esperada) vale porque o esperado é próximo de zero.

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,698 / 0,707 | 0,025 / 0,036 | 0,718 / 0,707 | 0,048 / 0,044 | 1,453 / 1,414 |
| 127 V/50 Hz | 0,699 / 0,707 | 0,026 / 0,036 | 0,718 / 0,707 | 0,004 / 0,004 | 1,432 / 1,414 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`, THD 20 % fixo). O mínimo do envelope medido (0,025–0,026 pu) contra 0,036 pu esperado fica dentro do piso; o THD esperado a 60 Hz (4,4 %) vem do degrau a 3,6 ciclos.

## 8. As três versões e a correlação esperada

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 0,879–1,000 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,997–1,000 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,972–1,000 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 1,000 / 1,000 | 0,879–1,000 / 0,866–1,000 | 0,974 / 0,963 | 0,993–1,000 / 0,968–1,000 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 1,000 / 1,000 | 0,997 / 0,995 | — |
| modelo × medida | 1,000 / 1,000 | 0,972 / 0,960 | — |

Causa de a classe ficar abaixo de 0,90, quando fica: idem 10: degrau a meio ciclo (P-09)

O modelo × programada é o de maior faixa das compostas (0,879–1,000) e o modelo × medida a 127 V/60 Hz é 0,972 contra 1,000 a 127 V/50 Hz: nada na medida física derruba a correlação além da perda de programação (programada × medida 0,997–1,000).

## 9. Quirks e armadilhas

- **A20:** a volta de interrupção sobressai 15–46 %.
- **A2, A3, A4, A5, A16, K7:** como na {doc}`06-flicker`.
- **Interrupção fixa:** `interruption_pu` não é sorteado; a classe não muda de nível entre capturas.
- **Acoplamento:** uma única chamada a `perfis.composto`; a independência de perfil depende de `Config.sorteio_posicao`, e a decisão é por rodada.

## 10. Histórico por versão

- **v1.7:** na estimativa de atraso por correlação cruzada a 16 deu −2402 amostras, descartada como provável artefato (a região de interrupção quase nula enfraquece o pico da correlação); as outras classes de TRACe deram cerca de +20 ms, o "atraso" que as v1.10 e v1.11 explicaram pela referência horizontal do osciloscópio (K1).
- **v1.12:** a volta da interrupção sobressai 15–46 %: 262 V medidos com 180 V programados; o bloqueio prévio do extremo físico nasceu daí; a 220 V a 16 era pulada.
- **v1.13:** o limite de bancada reduz só o distúrbio; a 220 V a 16 reduzida a 37 % é "quase um afundamento" (0,65 pu).
- **v1.14:** a 50 Hz as nativas 02, 04 e 16 deram fatores menores (~1,03–1,06 contra 1,16–1,48 a 60 Hz): a resposta da saída depende da **frequência**.
- **v1.15:** `capturas_padrao` = 3; THD sorteado (extensão (f)); a regra por frequência a traz de volta a 230 V/50 Hz (previsto 368,5 V); a correção do rms por ciclo da TRACe reduz o erro programada × modelo de 0,44 para 0,33 pu a 50 Hz.

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| Interrupção de 0,05 pu com THD 20 % via TRACe/LIST | {bdg-success}`VERIFICADO NA BANCADA` | 127 V/60 Hz e 127 V/50 Hz, 07/10/2026; fator 1,475 e 1,030 |
| THD sorteado; rms CA por ciclo; pico das 10/11/12/16 | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15; conferência obrigatória na primeira sessão (roteiro) |
| `gerar()` e programada de hoje | {bdg-info}`OFFLINE` | modelo × programada 0,879–1,000 |
| 230 V/50 Hz | {bdg-warning}`NÃO VERIFICADO` | pulada em 07/10; hoje o previsto é 368,5 V e roda |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
:::

:::{important} Pendência P-08
Conferir `pico_medido_v` e `vale_medido_v` contra `extremo_previsto_v` das classes 10, 11, 12 e 16 na primeira sessão (a previsão antiga subestimava até 38 %). Fecha com: bancada. Prioridade ALTA.
:::

:::{warning} Decisão em aberto P-11
Manter ou reverter as extensões das compostas, entre elas o THD sorteado em 16 (a interrupção fixa em 0,05 pu foi decisão de projeto (e)). Decisão do responsável pelo projeto ({ref}`P-11 <p-11>`, prioridade MÉDIA).
:::

:::{important} Pendência P-18
Passo final `SINE` no `LIST`: existe só no branch `feat/passo-final-sin`, **fora da `main`** ({doc}`../projeto/passo-final-sin`). Fecha com: bancada e decisão do responsável pelo projeto. Prioridade MÉDIA.
:::

:::{important} Pendência P-19
`TRACe:DATA?` (`set diagnostico retrieve`) nunca foi executado na fonte real. Fecha com: bancada, com o painel à vista. Prioridade MÉDIA.
:::

## 12. Como o código da classe funciona

| Símbolo | Recebe | Devolve | Quem chama |
|---|---|---|---|
| `Experimento.gerar` ([experimentos_waveform/16.py:21-30](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/16.py#L21-L30)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"interruption_pu": 0.05, "thd", "inicio_disturbio_s", "duracao_s", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.parametros_com_disturbio_reduzido` ([experimentos_waveform/16.py:32-39](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/16.py#L32-L39)) | `parametros`, `fracao` ($k$) | `{"interruption_pu_bancada", "thd_bancada"}` | a linha [mestre.py:3109](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3109) de `ExperimentoWaveform._limitar_disturbio_para_bancada` |

- `gerar` chama `perfis.composto(self.config, "thd_composto", capture_index, rng)`, depois `self.sortear(..., inicio_legado_s=0.060, duracao_legada_s=0.060, duracao_variavel=True)` e **substitui** a janela por `0.05 * sinais.onda_com_harmonicos(tt[mask], thd, frequencia_hz=f0)`.
- Atributos: `capturas_padrao` = 3 ([16.py:18](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/16.py#L18)). `pre_trigger_s` herdado.
- Contrato e acoplamentos: {doc}`../codigo/classes_contrato` §4.

## 13. Referências

- Código: `experimentos_waveform/16.py`; `logica/perfis.py` (`composto`, `depende_do_perfil`); `logica/sinais.py` (`onda_com_harmonicos`).
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`10-sag-harmonics`, {doc}`../limites_e_calibracao`, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`.
- Histórico: `CHANGELOG/v1.7.md`, `v1.12.md`, `v1.13.md`, `v1.14.md`, `v1.15.md`. Norma: IEEE Std 1159-2019, Tabela 2, itens 2.2.1 e 5.2.
