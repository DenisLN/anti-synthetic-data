# Classe 11: SAG_FLICKER

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 com parâmetros fixos (sag 0,5, flicker de 15 Hz a ±10 %; 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 1 captura cada, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` parâmetros sorteados; efeito da média por ciclo do flicker {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-08` {bdg-danger}`PENDENTE P-09` {bdg-danger}`PENDENTE P-11` {bdg-danger}`PENDENTE P-12` {bdg-danger}`PENDENTE P-18` {bdg-danger}`PENDENTE P-19`

| Campo | Valor |
|---|---|
| Número e nome | 11 SAG_FLICKER (afundamento com flicker) |
| Arquivo | `experimentos_waveform/11.py`, classe `Experimento(ExperimentoWaveform)` |
| Mecanismo na bancada | **forma de onda**: TRACe/LIST ({scpi}`TRACe:DATA`, {scpi}`SOURce:LIST:VOLTage`, um passo por ciclo) |
| `capturas_padrao` | 3 ([11.py:14](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/11.py#L14)) |
| Sorteio de posição | I D F, mais os três parâmetros (sag, profundidade e frequência do flicker) |
| Depende do perfil? | sim: sag e profundidade mudam |
| Condições já medidas | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 1 captura cada, com parâmetros fixos |

## 1. Em uma resposta

**Pergunta:** como o dataset combina um afundamento com flicker? **Resposta:** durante o evento (início e duração sorteados) a tensão cai a $\ell$ (0,1 a 0,9 pu) **e** a amplitude é modulada a $f_\text{fl}$ (8 a 25 Hz) com profundidade $m$ da faixa da classe 06; fora do evento a senoide é limpa. Na bancada herda os dois efeitos já descritos: a perda da média dos ciclos de borda do degrau ({doc}`10-sag-harmonics`) e a perda da média por ciclo do flicker ({doc}`06-flicker`); o efeito combinado do flicker nesta classe **não foi calculado** ({ref}`P-12 <p-12>`).

## 2. O fenômeno e a norma

Composta do afundamento (item 2.1.1 da Tabela 2 da IEEE Std 1159-2019, 0,1 a 0,9 pu, de 0,5 a 30 ciclos) com a flutuação de tensão (item 6.0, 0,1 a 7 %, abaixo de 25 Hz). A norma não define a composição; cada componente herda a faixa do seu item. A especificação (`experimentos.txt`, classe 11) fixava sag 0,5 pu e flicker de ±10 % a 15 Hz, início 60 ms, duração 60 ms; desde a v1.15 todos são sorteados (e a profundidade do perfil `literatura`, 5 a 15 %, passa de 7 % da norma).

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v(t)=\begin{cases}
\ell\,\big[1+m\sin(2\pi f_\text{fl}\,t)\big]\,\sin\theta & t_0\le t<t_0+d\\[2pt]
\sin\theta & \text{caso contrário}
\end{cases},\qquad \theta=2\pi f_0(t+\tau)
$$

A modulação existe **só dentro do evento** e usa $t$ (não $t+\tau$), como na 06. $\ell$, $m$ e $f_\text{fl}$ vêm de `perfis.composto`; $t_0$, $d$ e $\varphi$ do sorteio de posição ({ref}`fórmulas <sorteio-de-posicao>`; sem sorteio, 60 ms e 60 ms).

```{literalinclude} ../../experimentos_waveform/11.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_waveform/11.py, Experimento.gerar
```

- **Ordem do `rng`:** `perfis.composto` consome um `rng.uniform` por chamada, nesta ordem: sag, profundidade (`flicker_composto`), frequência (`flicker_composto_hz`); o sorteio de posição vem de um sub-fluxo. Mudar a ordem muda o dataset.
- **Parâmetros no metadata:** `sag_pu`, `flicker_hz`, `flicker_depth`, `inicio_disturbio_s`, `duracao_s`, `fase_graus`.
- **Seed:** `base_seed + 11 · 1 000 000 + indice_global`.
- **Capturas:** `capturas_padrao` = 3 ([11.py:14](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/11.py#L14)).

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** o flicker de 8 a 25 Hz sobrevive dentro de um afundamento? **Resposta:** sobrevive em degraus de um ciclo: a TRACe por ciclo leva a variação lenta no rms de cada passo; o flicker de 25 Hz sai com erro máximo de até 0,053 pu contra o modelo (sem sag, 50 e 60 Hz), e o sag acrescenta o erro dos ciclos de borda.

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

O gancho `parametros_com_disturbio_reduzido` ([11.py:30-37](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/11.py#L30-L37)) devolve `sag_pu_bancada` $=1+k(\ell-1)$ e `flicker_depth_bancada` $=k\,\ell\,m/\text{nivel}$.

**Janela e margem.** `pre_trigger_s` herdado (0); registro de 20 ms antes e 50 ms depois ({doc}`../medicao`).

**Por que a programada perde a média dos ciclos de borda.** O evento começa em $t_0$ e termina em $t_0+d$, que em geral não caem em fronteiras de ciclo. Nos ciclos de borda a forma tem um degrau a meio ciclo e, portanto, **média diferente de zero**. A fonte remove o componente CC de cada TRACe (manual, `TRACe:DATA`, p. 126) e a escala ao rms de `LIST:VOLTage`, e `SOURce:VOLTage:OFFSet` é um valor único da captura, não um offset por passo de `LIST` (o manual extraído não tem esse comando). O que a correção do rms por ciclo da TRACe mediu (127 V, `gerar()` com sorteio ligado, seed 32):

- **Antes da correção** o `LIST:VOLTage` levava o rms do ciclo **com** a média, mas a TRACe seguia **sem** ela: a amplitude CA saía inflada e a previsão de pico subestimava até 38 % (106,9 a 141,2 V previstos contra 153,3 a 172,1 V emitidos, com degraus sintéticos de nível 0,2 a 0,8 a 50 e 60 Hz).
- **Depois** (rms CA no `LIST:VOLTage`, pico previsto pela TRACe enviada) a previsão coincide com o emitido (diferença menor que 1 %), e **resta a média do ciclo**: erro máximo |programada − modelo| de 0,24 a 0,33 pu nas classes 10, 11, 12 e 16. Contra o modelo **sem** a média de cada ciclo, o erro cai a 0,02–0,04 pu. Só um offset por passo (modo ACDC, que tem o déficit de 5 a 6 % de CA da classe 19) o recuperaria.
- Que a fonte real escale a TRACe ao rms CA programado, como prevê o manual, e que o pico emitido nas classes 10, 11, 12 e 16 continue dentro de 425 Vp com o novo `LIST:VOLTage` são {bdg-warning}`NÃO VERIFICADO`: só a bancada confirma (comparar `pico_medido_v` e `vale_medido_v` com `extremo_previsto_v`, {ref}`P-08 <p-08>`).

| Erro máximo \|programada − modelo\| (pu) | 50 Hz, 127 V | 60 Hz, 230 V |
|---|---|---|
| antes da correção do rms CA | 0,3047 | 0,3039 |
| depois (código de hoje) | 0,2735 | 0,2420 |

*Fonte:* `CHANGELOG/v1.15.md`, "RMS por ciclo da TRACE" (`gerar()` com sorteio ligado, seed 32, simulação offline, sem hardware).

Ao erro dos ciclos de borda soma-se, nesta classe, a média por ciclo do próprio flicker dentro do evento (cresce com $f_\text{fl}/f_0$, {doc}`06-flicker`): quanto ela pesa na 11 e na 15 é {bdg-warning}`NÃO VERIFICADO`, não foi calculado. Erros da programação por ciclo medidos na revisão das compostas sorteadas (sag e swell em 1 pu para isolar o componente): flicker de 25 Hz, erro máximo 0,048 pu a 50 Hz (rms relativo 3,3 %) e 0,053 pu a 60 Hz (4,7 %); pico do distúrbio do modelo 0,094 para 0,087 pu na programada. **Com o sag sorteado** o erro máximo sobe a 0,25–0,32 pu, vindo da borda do sag no meio do ciclo, não do flicker.

:::{warning} Decisão em aberto P-09
Resta a média de cada ciclo de borda; só um offset por passo (modo ACDC, com o déficit de 5 a 6 % de CA da classe 19) a recuperaria. Investigar depois da primeira bancada com o código da v1.15? Decisão do responsável pelo projeto ({ref}`P-09 <p-09>`, prioridade BAIXA).
:::

:::{warning} Decisão em aberto P-12
Para a 06, comparar contra a forma programada ou redefinir o flicker com média nula por ciclo; as classes 11 e 15 herdam o efeito, ainda não calculado. Decisão do responsável pelo projeto ({ref}`P-12 <p-12>`, prioridade MÉDIA; detalhes na {doc}`06-flicker`).
:::

:::{warning} Decisão em aberto P-04
`AmetekMX30.program_capture` só **avisa** quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga", [ametek_orm.py:1522-1527](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1522-L1527)); quem recusa é a pré-validação do `mestre.py` (`ExperimentoBase._indices_viaveis`, antes de qualquer SCPI, e `_conferir_extremos_fisicos`, depois da captura já gravada). Pergunta ao responsável pelo projeto: o ORM também deve recusar? Opções: manter como está, ou recusar no ORM (um limite de segurança mais restritivo). Este site não decide ({ref}`P-04 <p-04>`, prioridade MÉDIA).
:::

:::{warning} Decisão em aberto P-23
A fonte travou na ~280.ª gravação de TRACe de uma mesma conexão (quirk A3; causa {bdg-warning}`NÃO VERIFICADO`), e cada captura desta classe grava 12 TRACes a 60 Hz (10 a 50 Hz). `README.md` e `AGENTS.md` ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `set perfil todos`), enquanto o roteiro de bancada usa listas de classes (menos de 250 por conexão). Pergunta: qual texto os documentos devem adotar? Opção recomendada pelo roteiro: listas (`run 01-07`, depois `run 09-20`). Decisão do responsável pelo projeto ({ref}`P-23 <p-23>`, prioridade MÉDIA).
:::

## 5. Parâmetros por perfil

**O que o sorteio cobre em cada componente.** Na 11 o sorteio contínuo cobre o sag (0,1 a 0,9 pu na `literatura`), a profundidade do flicker (a faixa da classe 06 do perfil) e a frequência (8 a 25 Hz); sag e swell são o mesmo componente compartilhado entre as compostas (decisão de projeto (a) em {ref}`o que o sorteio cobre <sorteio-das-compostas>` e `docs/perfis.md`).

| Componente em `perfis.py` | `norma` | `literatura` (padrão) | `fronteira` |
|---|---|---|---|
| `sag_composto` | sorteio off: 0,5; sorteio on: U(0,15; 0,85) | sorteio off: 0,5; sorteio on: U(0,1; 0,9) | sorteio off: 0,1 / 0,9; sorteio on: níveis por `capture_index` (sem intervalo) |
| `flicker_composto` | sorteio off: 0,045; sorteio on: U(0,02; 0,07) | sorteio off: 0,1; sorteio on: U(0,05; 0,15) | sorteio off: 0,1; sorteio on: U(0,05; 0,15) |
| `flicker_composto_hz` | sorteio off: 15; sorteio on: U(8; 25) | sorteio off: 15; sorteio on: U(8; 25) | sorteio off: 15; sorteio on: U(8; 25) |

## 6. Limites físicos e fator de extremo

Fatores medidos: 1,258 a 127 V/60 Hz, 1,030 a 127 V/50 Hz e a 230 V/50 Hz (o mesmo da 01, 1,03: uma captura reduzida só dá um limite inferior do fator).

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,258 | 3 | 179,6 | 248,5 | 415,8 | 100 % | 3/3 rodam |
| 127 V/50 Hz | 1,030 | 3 | 179,6 | 203,5 | 415,8 | 100 % | 3/3 rodam |
| 230 V/50 Hz | 1,030 | 3 | 325,3 | 368,5 | 415,8 | 100 % | 3/3 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 3 | 311,1 | 415,8 | 415,8 | 37 % | 3/3 rodam |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 3 capturas padrão, seed 20260827, sorteio ligado). A 220 V/60 Hz (sem tabela) as três capturas rodam reduzidas a 37 %. A fórmula do limite de bancada em {doc}`../limites_e_calibracao` §3.

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. O mínimo do envelope confere o sag.

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,703 / 0,707 | 0,321 / 0,321 | 0,724 / 0,707 | 0,022 / 0,021 | 1,450 / 1,414 |
| 127 V/50 Hz | 0,699 / 0,707 | 0,317 / 0,319 | 0,717 / 0,707 | 0,002 / 0,000 | 1,443 / 1,414 |
| 230 V/50 Hz | 0,703 / 0,707 | 0,512 / 0,510 | 0,711 / 0,707 | 0,002 / 0,000 | 1,437 / 1,414 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`, sag 0,5 e flicker de 15 Hz fixos). O mínimo do envelope (0,32 a 0,51 pu) acompanha o esperado; as capturas passaram.

## 8. As três versões e a correlação esperada

A `programada` é a reconstrução da TRACe (rms CA por passo, sem a média de cada ciclo).

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 0,843–0,998 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,996–0,999 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,969–0,999 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 1,000 / 0,999 | 0,843–0,989 / 0,833–0,985 | 0,971 / 0,959 | 0,846–0,998 / 0,838–0,996 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,999 / 0,999 | 0,997 / 0,997 | 0,996 / 0,996 |
| modelo × medida | 0,999 / 0,998 | 0,969 / 0,957 | 0,996 / 0,995 |

Causa de a classe ficar abaixo de 0,90, quando fica: idem 10; a média por ciclo do flicker somado ao SAG não foi calculada (P-09, P-12)

O modelo × programada é o mais baixo das compostas de sag (0,843–0,998): ao erro dos ciclos de borda soma-se a média por ciclo do flicker; a medida física acompanha a programada (0,996–0,999), isto é, a perda está na programação.

## 9. Quirks e armadilhas

- **A20:** a volta do afundamento sobressai (fator 1,258 a 127 V/60 Hz).
- **A2, A3, A4, A5, A16, K7:** como na {doc}`06-flicker`.
- **Programada de 07/10 reconstruída com o código de hoje:** a coluna "programada × medida" é estimativa com o código de hoje ({doc}`../medicao/correlacao` §2).
- **Acoplamento:** a ordem das três chamadas a `perfis.composto` define o `rng`.

## 10. Histórico por versão

- **v1.12:** bloqueio prévio do extremo físico; a 220 V a 11 era pulada.
- **v1.13:** o limite de bancada reduz só o distúrbio (a 11 a 78 % em 220 V); `capturas_padrao` fica em 1.
- **v1.14:** a 230 V/50 Hz o fator da 11 é igual ao da 01 (1,03): a captura reduzida só dá limite inferior.
- **v1.15:** `capturas_padrao` = 3; sag U(0,1; 0,9) (extensão: o sorteio do sag em 11 e 12), profundidade e frequência do flicker sorteados; rms CA por ciclo; revisão contra a proposta.

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| Sag 0,5 com flicker de 15 Hz via TRACe/LIST | {bdg-success}`VERIFICADO NA BANCADA` | 3 condições, 07/10/2026; programada × medida 0,996–0,999 |
| Parâmetros sorteados, rms CA por ciclo | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15 |
| Efeito da média por ciclo do flicker na 11 | {bdg-warning}`NÃO VERIFICADO` | não calculado (`CHANGELOG/v1.15.md`, "Pendentes da correlação do distúrbio") |
| `gerar()` e programada de hoje | {bdg-info}`OFFLINE` | modelo × programada 0,843–0,998 |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
:::

:::{important} Pendência P-08
Conferir `pico_medido_v` e `vale_medido_v` contra `extremo_previsto_v` depois da correção do rms CA por ciclo. Fecha com: bancada. Prioridade ALTA.
:::

:::{warning} Decisão em aberto P-11
Manter ou reverter as extensões das compostas, entre elas o sag em 11 e 12 e a profundidade do flicker da `norma` (2 a 7 %); o texto da proposta pedia o sorteio só na 10. Decisão do responsável pelo projeto ({ref}`P-11 <p-11>`, prioridade MÉDIA).
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
| `Experimento.gerar` ([experimentos_waveform/11.py:17-28](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/11.py#L17-L28)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"sag_pu", "flicker_hz", "flicker_depth", "inicio_disturbio_s", "duracao_s", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.parametros_com_disturbio_reduzido` ([experimentos_waveform/11.py:30-37](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/11.py#L30-L37)) | `parametros`, `fracao` ($k$) | `{"sag_pu_bancada", "flicker_depth_bancada"}` | a linha [mestre.py:3109](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3109) de `ExperimentoWaveform._limitar_disturbio_para_bancada` |

- `gerar` chama `perfis.composto` três vezes (`sag_composto`, `flicker_composto`, `flicker_composto_hz`), depois `self.sortear(rng, f0, inicio_legado_s=0.060, duracao_legada_s=0.060, duracao_variavel=True)` e **multiplica** a janela por `sag * (1 + profundidade * sin(2π f t[mask]))`.
- Atributos: `capturas_padrao` = 3 ([11.py:14](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/11.py#L14)). `pre_trigger_s` herdado.
- Contrato e acoplamentos: {doc}`../codigo/classes_contrato` §4; as faixas: {doc}`../codigo/perfis`.

## 13. Referências

- Código: `experimentos_waveform/11.py`; `logica/perfis.py` (`composto`); `logica/ametek_orm.py` (`montar_programacao`).
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`10-sag-harmonics`, {doc}`06-flicker`, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`.
- Histórico: `CHANGELOG/v1.12.md`, `v1.13.md`, `v1.14.md`, `v1.15.md`. Norma: IEEE Std 1159-2019, Tabela 2, itens 2.1.1 e 6.0.
