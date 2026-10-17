# Classe 10: SAG_HARMONICS

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 com parâmetros fixos (sag 0,5 e THD 20 %; 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 1 captura cada, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` parâmetros sorteados e correção do rms CA por ciclo {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-08` {bdg-danger}`PENDENTE P-09` {bdg-danger}`PENDENTE P-11` {bdg-danger}`PENDENTE P-18` {bdg-danger}`PENDENTE P-19`

| Campo | Valor |
|---|---|
| Número e nome | 10 SAG_HARMONICS (afundamento com harmônicos) |
| Arquivo | `experimentos_waveform/10.py`, classe `Experimento(ExperimentoWaveform)` |
| Mecanismo na bancada | **forma de onda**: TRACe/LIST ({scpi}`TRACe:DATA`, {scpi}`SOURce:LIST:VOLTage`, um passo por ciclo) |
| `capturas_padrao` | 3 ([10.py:19](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/10.py#L19)) |
| Sorteio de posição | I D F (início, duração e fase) e, desde a v1.15, os dois parâmetros (sag e THD) |
| Depende do perfil? | sim: sag e THD mudam (`sag_composto`, `thd_composto`) |
| Condições já medidas | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 1 captura cada, com sag 0,5 e THD 20 % fixos |

## 1. Em uma resposta

**Pergunta:** como o dataset combina um afundamento com harmônicos? **Resposta:** durante o evento (início e duração sorteados) a tensão cai a um nível $\ell$ entre 0,1 e 0,9 pu **e** carrega 3.ª, 5.ª e 7.ª harmônicas com THD sorteado entre 5 e 20 %, nos mesmos instantes; fora do evento a senoide é limpa. Na bancada a combinação não é nativa: passa por TRACe/LIST, com a perda da média dos ciclos de borda do degrau (erro programada × modelo de 0,24 a 0,33 pu) e, a tensões altas, com o distúrbio reduzido ao que cabe no teto de pico.

## 2. O fenômeno e a norma

Composta de dois fenômenos simultâneos: o afundamento (item 2.1.1 da Tabela 2 da IEEE Std 1159-2019, 0,1 a 0,9 pu, de 0,5 a 30 ciclos) e a distorção harmônica (item 5.2, 0 a 20 % de THD). A norma não define a composição; cada componente **herda a faixa do seu item**. A especificação (`experimentos.txt`, classe 10) fixava sag 0,5 pu, THD 20 %, início 60 ms e duração 60 ms; desde a v1.15 o sag e o THD são sorteados.

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v(t)=\begin{cases}
\ell\;\big[\sin\theta+a_3\sin3\theta+a_5\sin5\theta+a_7\sin7\theta\big] & t_0\le t<t_0+d\\[2pt]
\sin\theta & \text{caso contrário}
\end{cases},\qquad
\theta=2\pi f_0\,(t+\tau),\quad a_k=\mathrm{THD}\,\frac{r_k}{\lVert r\rVert},\ r=(0{,}60;\,0{,}30;\,0{,}10)
$$

O harmônico é **escalado junto com o sag** ($\ell$ multiplica a soma inteira), de modo que o THD dentro do evento continua sendo o sorteado. $\ell$ e THD vêm de `perfis.composto` ({ref}`o que o sorteio cobre <sorteio-das-compostas>`); $t_0$, $d$ e $\varphi$ do sorteio de posição ({ref}`fórmulas <sorteio-de-posicao>`; $d$ variável; sem sorteio, 60 ms e 60 ms).

```{literalinclude} ../../experimentos_waveform/10.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_waveform/10.py, Experimento.gerar
```

- **Ordem do `rng`:** `perfis.composto` consome **um `rng.uniform` por chamada**, na ordem em que `gerar()` chama: primeiro o sag, depois o THD. O sorteio de posição vem de um sub-fluxo e não consome o `rng`. Mudar a ordem das chamadas muda o `rng` e o dataset ({doc}`../codigo/acoplamentos`).
- **Parâmetros no metadata:** `sag_pu`, `thd`, `inicio_disturbio_s`, `duracao_s`, `fase_graus`.
- **Seed:** `base_seed + 10 · 1 000 000 + indice_global`.
- **Capturas:** `capturas_padrao` = 3 ([10.py:19](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/10.py#L19)): os parâmetros são sorteados e uma captura mostra uma só realização (v1.15: 468 gravações de TRACe por `run all` a 60 Hz).

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** a fonte reproduz o sag e os harmônicos juntos? **Resposta:** reproduz pela lista: cada ciclo é uma TRACe de 1024 pontos com seu rms de passo; o sag vira degrau de rms entre passos e os harmônicos vão no formato da TRACe, até os ciclos de borda, onde a média do ciclo se perde.

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

O gancho `parametros_com_disturbio_reduzido` ([10.py:34-41](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/10.py#L34-L41)) traduz o limite de bancada $k$: com `nivel` $=1+k(\ell-1)$, devolve `sag_pu_bancada` $=$ `nivel` e `thd_bancada` $=k\,\ell\,\mathrm{THD}/\text{nivel}$. A forma física é `senoide + k·(gerar() − senoide)`, que dentro do evento é $\text{nivel}\cdot\sin\theta + k\ell\cdot h(\theta)$, com $h$ a soma harmônica; daí o THD físico da fórmula.

**Janela e margem.** `pre_trigger_s` herdado (0); o evento começa em $t_0$ dentro da janela; registro de 20 ms antes e 50 ms depois ({doc}`../medicao`).

**Por que a programada perde a média dos ciclos de borda.** O evento começa em $t_0$ e termina em $t_0+d$, que em geral não caem em fronteiras de ciclo. Nos ciclos de borda a forma tem um degrau a meio ciclo e, portanto, **média diferente de zero**. A fonte remove o componente CC de cada TRACe (manual, `TRACe:DATA`, p. 126) e a escala ao rms de `LIST:VOLTage`, e `SOURce:VOLTage:OFFSet` é um valor único da captura, não um offset por passo de `LIST` (o manual extraído não tem esse comando). O que a correção do rms por ciclo da TRACe mediu (127 V, `gerar()` com sorteio ligado, seed 32):

- **Antes da correção** o `LIST:VOLTage` levava o rms do ciclo **com** a média, mas a TRACe seguia **sem** ela: a amplitude CA saía inflada e a previsão de pico subestimava até 38 % (106,9 a 141,2 V previstos contra 153,3 a 172,1 V emitidos, com degraus sintéticos de nível 0,2 a 0,8 a 50 e 60 Hz).
- **Depois** (rms CA no `LIST:VOLTage`, pico previsto pela TRACe enviada) a previsão coincide com o emitido (diferença menor que 1 %), e **resta a média do ciclo**: erro máximo |programada − modelo| de 0,24 a 0,33 pu nas classes 10, 11, 12 e 16. Contra o modelo **sem** a média de cada ciclo, o erro cai a 0,02–0,04 pu. Só um offset por passo (modo ACDC, que tem o déficit de 5 a 6 % de CA da classe 19) o recuperaria.
- Que a fonte real escale a TRACe ao rms CA programado, como prevê o manual, e que o pico emitido nas classes 10, 11, 12 e 16 continue dentro de 425 Vp com o novo `LIST:VOLTage` são {bdg-warning}`NÃO VERIFICADO`: só a bancada confirma (comparar `pico_medido_v` e `vale_medido_v` com `extremo_previsto_v`, {ref}`P-08 <p-08>`).

| Erro máximo \|programada − modelo\| (pu) | 50 Hz, 127 V | 60 Hz, 230 V |
|---|---|---|
| antes da correção do rms CA | 0,3063 | 0,3019 |
| depois (código de hoje) | 0,2613 | 0,2429 |

*Fonte:* `CHANGELOG/v1.15.md`, "RMS por ciclo da TRACE" (`gerar()` com sorteio ligado, seed 32, simulação offline, sem hardware).

:::{warning} Decisão em aberto P-09
Resta a média de cada ciclo de borda (erro programada × modelo de 0,24 a 0,33 pu): só um offset por passo a recuperaria, e isso exige o modo ACDC, que tem o déficit de 5 a 6 % de CA da classe 19 ({ref}`P-17 <p-17>`). Pergunta ao responsável pelo projeto: investigar essa compensação depois da primeira bancada com o código da v1.15, ou aceitar a perda como limite da fonte? Este site não decide ({ref}`P-09 <p-09>`, prioridade BAIXA).
:::

:::{warning} Decisão em aberto P-04
`AmetekMX30.program_capture` só **avisa** quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga", [ametek_orm.py:1522-1527](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1522-L1527)); quem recusa é a pré-validação do `mestre.py` (`ExperimentoBase._indices_viaveis`, antes de qualquer SCPI, e `_conferir_extremos_fisicos`, depois da captura já gravada). Pergunta ao responsável pelo projeto: o ORM também deve recusar? Opções: manter como está, ou recusar no ORM (um limite de segurança mais restritivo). Este site não decide ({ref}`P-04 <p-04>`, prioridade MÉDIA).
:::

:::{warning} Decisão em aberto P-23
A fonte travou na ~280.ª gravação de TRACe de uma mesma conexão (quirk A3; causa {bdg-warning}`NÃO VERIFICADO`), e cada captura desta classe grava 12 TRACes a 60 Hz (10 a 50 Hz). `README.md` e `AGENTS.md` ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `set perfil todos`), enquanto o roteiro de bancada usa listas de classes (menos de 250 por conexão). Pergunta: qual texto os documentos devem adotar? Opção recomendada pelo roteiro: listas (`run 01-07`, depois `run 09-20`). Decisão do responsável pelo projeto ({ref}`P-23 <p-23>`, prioridade MÉDIA).
:::

## 5. Parâmetros por perfil

(sorteio-das-compostas)=
**O que o sorteio cobre em cada componente** (`FAIXAS_SORTEADAS` em [perfis.py:113-133](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L113-L133), `composto` em [perfis.py:182-196](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L182-L196); `docs/perfis.md`, "Compostas sorteadas"). Na 10 o sorteio contínuo cobre o sag de 0,1 a 0,9 pu (`literatura`) e o THD de 5 a 20 %; nenhum componente é fixo.

| Componente em `perfis.py` | `norma` | `literatura` (padrão) | `fronteira` |
|---|---|---|---|
| `sag_composto` | sorteio off: 0,5; sorteio on: U(0,15; 0,85) | sorteio off: 0,5; sorteio on: U(0,1; 0,9) | sorteio off: 0,1 / 0,9; sorteio on: níveis por `capture_index` (sem intervalo) |
| `thd_composto` | sorteio off: 0,2; sorteio on: U(0,02; 0,2) | sorteio off: 0,2; sorteio on: U(0,05; 0,2) | sorteio off: 0,2; sorteio on: U(0,05; 0,2) |

A `fronteira` não sorteia o sag: alterna 0,1 e 0,9 por `capture_index` (`FAIXAS_SORTEADAS[...]["fronteira"] = None`); com 3 capturas aparecem 0,1, 0,9 e 0,1. O THD da `fronteira` usa a faixa da literatura. Os valores com `set sorteio off` (0,5 e 20 %) reproduzem o `gerar()` de 34a0d82.

## 6. Limites físicos e fator de extremo

O pico programado é o da senoide base (o sag só reduz o evento); o limite que importa é o da **volta** do afundamento e dos degraus entre ciclos (quirk A20): fator 1,242 a 127 V/60 Hz, mas apenas 1,030 a 127 V/50 Hz e a 230 V/50 Hz (a diferença é por **frequência**, não por tensão).

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,242 | 3 | 179,6 | 245,4 | 415,8 | 100 % | 3/3 rodam |
| 127 V/50 Hz | 1,030 | 3 | 179,6 | 203,5 | 415,8 | 100 % | 3/3 rodam |
| 230 V/50 Hz | 1,030 | 3 | 325,3 | 368,5 | 415,8 | 100 % | 3/3 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 3 | 311,1 | 415,8 | 415,8 | 37 % | 3/3 rodam |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 3 capturas padrão, seed 20260827, sorteio ligado). Pelo limite de bancada ({doc}`../limites_e_calibracao` §3), a 220 V/60 Hz (sem tabela, fator conservador 1,475) as três capturas rodam com o distúrbio reduzido a 37 % (`sag_pu_bancada` 0,73 a 0,93, `thd_bancada` 0,02 a 0,05). Em 07/10 a 230 V/50 Hz a 10 rodou reduzida a 55 % pela regra daquele dia (v1.12: a 220 V a 10 era pulada; v1.13: reduzida a 88 %).

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. A comparação é contra a forma realmente programada (com $k$ e sem a média por ciclo). O mínimo do envelope confere o sag e o THD confere os harmônicos.

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,705 / 0,707 | 0,353 / 0,361 | 0,726 / 0,707 | 0,040 / 0,040 | 1,442 / 1,414 |
| 127 V/50 Hz | 0,699 / 0,707 | 0,349 / 0,361 | 0,718 / 0,707 | 0,035 / 0,035 | 1,432 / 1,414 |
| 230 V/50 Hz | 0,704 / 0,707 | 0,509 / 0,513 | 0,712 / 0,707 | 0,018 / 0,018 | 1,435 / 1,414 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`, sag 0,5 e THD 20 % fixos). O mínimo do envelope medido (0,35 a 0,51 pu) acompanha o esperado; o THD medido bate o esperado nas três condições (4,0 %, 3,5 % e 1,8 %); as três capturas passaram.

## 8. As três versões e a correlação esperada

A `programada` é a reconstrução da TRACe com o rms CA do ciclo em `LIST:VOLTage`. O sag aparece como degrau de rms entre passos; a média dos ciclos de borda **não** aparece.

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 0,963–1,000 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,997–0,999 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,975–0,999 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 1,000 / 1,000 | 0,963–1,000 / 0,954–1,000 | 0,977 / 0,968 | 0,989–0,999 / 0,971–0,998 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,999 / 0,999 | 0,997 / 0,997 | 0,998 / 0,997 |
| modelo × medida | 0,999 / 0,999 | 0,975 / 0,966 | 0,998 / 0,997 |

Causa de a classe ficar abaixo de 0,90, quando fica: média de cada ciclo nos ciclos de borda do degrau (sorteio ligado); o modelo × medida a 127 V/60 Hz é 0,975 (P-09)

O modelo × programada fica em 0,963–1,000 (v1.15, sorteio ligado) e cai quando o evento tem bordas em ciclos de média grande; o par medido acompanha a programada (0,997–0,999), isto é, a medida física segue a programação e a perda está nela (P-09). O modelo × medida a 127 V/60 Hz (0,975) vem da mesma média.

## 9. Quirks e armadilhas

- **A20:** a volta do afundamento sobressai (fator 1,242 a 127 V/60 Hz).
- **A2, A3, A4, A5, A16, K7:** como na {doc}`06-flicker`.
- **Programada de 07/10 reconstruída com o código de hoje:** desde a v1.15 `LIST:VOLTage` leva o rms CA do ciclo; antes levava o rms com a média. Para a 10, a coluna "programada × medida" é uma estimativa com o código de hoje, não uma conferência do que foi programado ({doc}`../medicao/correlacao` §2).
- **Acoplamento:** a ordem das chamadas a `perfis.composto` muda o `rng` e o dataset.

## 10. Histórico por versão

- **v1.12:** o bloqueio prévio do extremo físico: a volta de afundamento ou interrupção sobressai 15 a 46 % (a 16 mediu 262 V com 180 V programados); a 220 V a 10 era pulada.
- **v1.13:** o limite de bancada reduz só o distúrbio (a 10 a 88 % em 220 V); `capturas_padrao` fica em 1 (parâmetros fixos).
- **v1.15:** `capturas_padrao` = 3; sag U(0,1; 0,9) e THD U(0,05; 0,20) sorteados (norma e fronteira herdam os componentes); a correção do rms por ciclo da TRACe passa o rms CA ao `LIST:VOLTage` (erro programada × modelo de 0,31 para 0,26 pu a 50 Hz); a revisão contra a proposta confere as faixas e registra as extensões (sag em 11/12, swell em 13/14, THD em 13/15/16) como decisões de projeto ({ref}`P-11 <p-11>`).

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| Sag 0,5 com THD 20 % via TRACe/LIST | {bdg-success}`VERIFICADO NA BANCADA` | 3 condições, 07/10/2026; programada × medida 0,997–0,999 |
| Parâmetros sorteados, rms CA por ciclo | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15 (conferir `pico_medido_v` contra `extremo_previsto_v`, roteiro) |
| `gerar()` e programada de hoje | {bdg-info}`OFFLINE` | fixtures; correlação modelo × programada 0,963–1,000 |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
:::

:::{important} Pendência P-08
Conferir na primeira sessão que `pico_medido_v` e `vale_medido_v` ficam abaixo de `extremo_previsto_v` depois da correção do rms CA por ciclo (a previsão antiga subestimava até 38 %). Fecha com: bancada. Prioridade ALTA.
:::

:::{warning} Decisão em aberto P-11
As extensões das compostas além do texto da proposta: (a) sag em 11 e 12 e swell em 13 e 14; (b) faixa do swell igual aos extremos de `swell_niveis`; (c) faixas do perfil `norma`; (d) `fronteira` alternada; (e) valores fixos nas classes 16 e 17; (f) THD sorteado em 13, 15 e 16. Manter ou reverter? Reverter muda o dataset da v1.15 e exige regravar `gerar_sorteio_v1_15.json`. A 15 não tem o gancho de bancada. Decisão do responsável pelo projeto ({ref}`P-11 <p-11>`, prioridade MÉDIA).
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
| `Experimento.gerar` ([experimentos_waveform/10.py:22-32](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/10.py#L22-L32)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"sag_pu", "thd", "inicio_disturbio_s", "duracao_s", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.parametros_com_disturbio_reduzido` ([experimentos_waveform/10.py:34-41](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/10.py#L34-L41)) | `parametros`, `fracao` ($k$) | `{"sag_pu_bancada", "thd_bancada"}` | a linha [mestre.py:3109](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3109) de `ExperimentoWaveform._limitar_disturbio_para_bancada` |

- `gerar` chama `perfis.composto(self.config, "sag_composto", capture_index, rng)` e `"thd_composto"` (nessa ordem), depois `self.sortear(rng, f0, inicio_legado_s=0.060, duracao_legada_s=0.060, duracao_variavel=True)`, constrói a senoide deslocada e **substitui** a janela (`sinais.janela`, [sinais.py:20-21](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L20-L21)) por `sag * sinais.onda_com_harmonicos(tt[mask], thd, frequencia_hz=f0)` ([sinais.py:52-62](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L52-L62)).
- Atributos: `capturas_padrao` = 3 ([10.py:19](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/10.py#L19)). `pre_trigger_s` herdado.
- Contrato, ganchos e acoplamentos: {doc}`../codigo/classes_contrato` §4 ("10 a 16: a ordem das chamadas a `perfis.composto`"); as faixas: {doc}`../codigo/perfis`.

## 13. Referências

- Código: `experimentos_waveform/10.py`; `logica/perfis.py` (`composto`, `FAIXAS_SORTEADAS`); `logica/sinais.py` (`onda_com_harmonicos`, `janela`); `logica/ametek_orm.py` (`montar_programacao`).
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`../limites_e_calibracao`, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`.
- Histórico: `CHANGELOG/v1.12.md`, `v1.13.md`, `v1.15.md` (seções "Parâmetros das compostas 10 a 16 sorteados", "RMS por ciclo da TRACE" e "Revisão das compostas sorteadas"). Norma: IEEE Std 1159-2019, Tabela 2, itens 2.1.1 e 5.2.
