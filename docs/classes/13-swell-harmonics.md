# Classe 13: SWELL_HARMONICS

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 com parâmetros fixos (swell 1,3 e THD 20 %; 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 1 captura cada, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` parâmetros sorteados; 230 V/50 Hz com swell alto {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-11` {bdg-danger}`PENDENTE P-18` {bdg-danger}`PENDENTE P-19`

| Campo | Valor |
|---|---|
| Número e nome | 13 SWELL_HARMONICS (elevação com harmônicos) |
| Arquivo | `experimentos_waveform/13.py`, classe `Experimento(ExperimentoWaveform)` |
| Mecanismo na bancada | **forma de onda**: TRACe/LIST ({scpi}`TRACe:DATA`, {scpi}`SOURce:LIST:VOLTage`, um passo por ciclo) |
| `capturas_padrao` | 3 ([13.py:18](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/13.py#L18)) |
| Sorteio de posição | I D F, mais o swell e o THD |
| Depende do perfil? | sim: swell e THD mudam (`swell_composto`, `thd_composto`) |
| Condições já medidas | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 1 captura cada, com swell 1,3 e THD 20 % fixos |

## 1. Em uma resposta

**Pergunta:** como o dataset combina uma elevação de tensão com harmônicos? **Resposta:** é a {doc}`10-sag-harmonics` com o patamar **acima** de 1: durante o evento a tensão sobe a $\ell$ entre 1,1 e 1,8 pu e carrega 3.ª, 5.ª e 7.ª harmônicas com THD sorteado entre 5 e 20 %. O que a distingue é o limite: o pico do patamar (até $1{,}8\sqrt2 V_\text{base}$ mais os harmônicos) é o que mais desafia o teto de 415,8 V, de modo que, com a seed do relatório offline (20260827), a 230 V/50 Hz dois dos três swells sorteados rodam reduzidos e um é pulado.

## 2. O fenômeno e a norma

Composta da elevação (item 2.1.2 da Tabela 2 da IEEE Std 1159-2019, 1,1 a 1,8 pu, de 0,5 a 30 ciclos) com a distorção harmônica (item 5.2, 0 a 20 % de THD). A norma não define a composição. A especificação (`experimentos.txt`, classe 13) fixava swell 1,3 pu e THD 20 %, início 60 ms e duração 60 ms; desde a v1.15 o swell e o THD são sorteados (o swell sorteado, em 13 e 14, é extensão do texto da proposta).

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v(t)=\begin{cases}
\ell\;\big[\sin\theta+a_3\sin3\theta+a_5\sin5\theta+a_7\sin7\theta\big] & t_0\le t<t_0+d\\[2pt]
\sin\theta & \text{caso contrário}
\end{cases},\qquad \ell\sim\mathcal{U}(1{,}1;\,1{,}8),\ \ \mathrm{THD}\sim\mathcal{U}(0{,}05;\,0{,}20)
$$

(Os $a_k$ como na {doc}`10-sag-harmonics`.) O harmônico é escalado junto com o swell. $t_0$, $d$ e $\varphi$ vêm do sorteio de posição ({ref}`fórmulas <sorteio-de-posicao>`; sem sorteio, 60 ms e 60 ms).

```{literalinclude} ../../experimentos_waveform/13.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_waveform/13.py, Experimento.gerar
```

- **Ordem do `rng`:** `perfis.composto` consome um `rng.uniform` por chamada: primeiro o swell, depois o THD.
- **Parâmetros no metadata:** `swell_pu`, `thd`, `inicio_disturbio_s`, `duracao_s`, `fase_graus`.
- **Seed:** `base_seed + 13 · 1 000 000 + indice_global`.
- **Capturas:** `capturas_padrao` = 3 ([13.py:18](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/13.py#L18)).

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** a fonte reproduz o swell com harmônicos? **Resposta:** reproduz pela lista, como a 10, com o limite de pico mais apertado: o patamar de 1,8 pu somado aos harmônicos pode passar do teto, e então a captura física reduz só o distúrbio ($k$).

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

O gancho `parametros_com_disturbio_reduzido` ([13.py:33-40](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/13.py#L33-L40)) devolve `swell_pu_bancada` $=1+k(\ell-1)$ e `thd_bancada` $=k\,\ell\,\mathrm{THD}/\text{nivel}$. Exemplo (230 V/50 Hz, relatório offline abaixo): `swell_pu_bancada` 1,15 e `thd_bancada` 0,084 a $k$ = 90 %; 1,14 e 0,072 a $k$ = 50 %.

**Janela e margem.** `pre_trigger_s` herdado (0); registro de 20 ms antes e 50 ms depois ({doc}`../medicao`).

**A média dos ciclos de borda.** Vale o que a {doc}`10-sag-harmonics` descreve (a TRACe perde a média de cada ciclo). Na 13 o erro máximo programada × modelo medido na correção do rms por ciclo da TRACe é menor que nas compostas de sag (a média do ciclo de borda de um patamar acima de 1 não foi analisada separadamente):

| Erro máximo \|programada − modelo\| (pu) | 50 Hz, 127 V | 60 Hz, 230 V |
|---|---|---|
| antes da correção do rms CA | 0,1099 | 0,0955 |
| depois (código de hoje) | 0,1138 | 0,0912 |

*Fonte:* `CHANGELOG/v1.15.md`, "RMS por ciclo da TRACE" (`gerar()` com sorteio ligado, seed 32, simulação offline, sem hardware).

:::{warning} Decisão em aberto P-04
`AmetekMX30.program_capture` só **avisa** quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga", [ametek_orm.py:1522-1527](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1522-L1527)); quem recusa é a pré-validação do `mestre.py` (`ExperimentoBase._indices_viaveis`, antes de qualquer SCPI, e `_conferir_extremos_fisicos`, depois da captura já gravada). Pergunta ao responsável pelo projeto: o ORM também deve recusar? Opções: manter como está, ou recusar no ORM (um limite de segurança mais restritivo). Este site não decide ({ref}`P-04 <p-04>`, prioridade MÉDIA).
:::

:::{warning} Decisão em aberto P-23
A fonte travou na ~280.ª gravação de TRACe de uma mesma conexão (quirk A3; causa {bdg-warning}`NÃO VERIFICADO`), e cada captura desta classe grava 12 TRACes a 60 Hz (10 a 50 Hz). `README.md` e `AGENTS.md` ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `set perfil todos`), enquanto o roteiro de bancada usa listas de classes (menos de 250 por conexão). Pergunta: qual texto os documentos devem adotar? Opção recomendada pelo roteiro: listas (`run 01-07`, depois `run 09-20`). Decisão do responsável pelo projeto ({ref}`P-23 <p-23>`, prioridade MÉDIA).
:::

## 5. Parâmetros por perfil

**O que o sorteio cobre em cada componente.** Na 13: swell (1,1 a 1,8 pu na `literatura`, os extremos de `swell_niveis`) e THD (5 a 20 %). O THD sorteado em 13, 15 e 16 é a extensão (f) de {ref}`o que o sorteio cobre <sorteio-das-compostas>`: sem ela, essas classes ficariam com THD fixo de 20 %, o teto da CSINusoid, e um classificador aprenderia "THD = 20 %" como marca da classe.

| Componente em `perfis.py` | `norma` | `literatura` (padrão) | `fronteira` |
|---|---|---|---|
| `swell_composto` | sorteio off: 1,3; sorteio on: U(1,15; 1,75) | sorteio off: 1,3; sorteio on: U(1,1; 1,8) | sorteio off: 1,1 / 1,8; sorteio on: níveis por `capture_index` (sem intervalo) |
| `thd_composto` | sorteio off: 0,2; sorteio on: U(0,02; 0,2) | sorteio off: 0,2; sorteio on: U(0,05; 0,2) | sorteio off: 0,2; sorteio on: U(0,05; 0,2) |

O perfil `fronteira` alterna 1,1 e 1,8 pu por `capture_index` (sem sorteio contínuo). Os valores com `set sorteio off` (swell 1,3 e THD 20 %) reproduzem o `gerar()` de 34a0d82.

## 6. Limites físicos e fator de extremo

Fatores medidos: 1,034 a 127 V/60 Hz, 1,063 a 127 V/50 Hz e 1,047 a 230 V/50 Hz. O pico programado cresce com o swell: 198 a 263 V a 127 V nas três capturas do relatório offline (de 1,10 a 1,46 pu).

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,034 | 3 | 198,2–262,8 | 225,4–298,9 | 415,8 | 100 % | 3/3 rodam |
| 127 V/50 Hz | 1,063 | 3 | 198,2–262,8 | 231,8–307,3 | 415,8 | 100 % | 3/3 rodam |
| 230 V/50 Hz | 1,047 | 3 | 355,6–476,0 | 415,8–556,6 | 415,8 | 50–100 % | 2/3 rodam, 1 pulada(s) |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 3 | 319,8–455,3 | 415,8–738,7 | 415,8 | 27–100 % | 1/3 rodam, 2 pulada(s) |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 3 capturas padrão, seed 20260827, sorteio ligado). A 230 V/50 Hz a 13 roda **2 de 3**: a primeira com $k$ = 90 %, a segunda com 50 % e a terceira é **pulada** (swell sorteado mais alto: extremo previsto 556,6 V, e o limite de bancada precisaria reduzir o distúrbio a 20 %, abaixo do mínimo de 25 %). A 220 V/60 Hz (sem tabela) só 1 das 3 roda, a 27 %. Em 07/10 (swell 1,3 fixo) a 13 rodou a 230 V/50 Hz com $k$ = 75 % e fator 1,030 medido.

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. O máximo do envelope confere o swell.

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,722 / 0,707 | 0,701 / 0,707 | 0,954 / 0,937 | 0,071 / 0,071 | 1,436 / 1,414 |
| 127 V/50 Hz | 0,720 / 0,707 | 0,707 / 0,707 | 0,952 / 0,937 | 0,071 / 0,072 | 1,446 / 1,414 |
| 230 V/50 Hz | 0,712 / 0,707 | 0,704 / 0,707 | 0,884 / 0,877 | 0,055 / 0,055 | 1,437 / 1,414 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`, swell 1,3 e THD 20 % fixos). O máximo do envelope medido (0,95 pu a 127 V) acompanha o esperado (0,94); o THD de 7,1 % medido bate o esperado a 127 V.

## 8. As três versões e a correlação esperada

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 0,950–0,999 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,996–0,997 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,976–0,997 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 1,000 / 1,000 | 0,950–0,999 / 0,938–0,997 | 0,978 / 0,973 | 0,955–0,997 / 0,946–0,996 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,996 / 0,996 | 0,997 / 0,998 | 0,997 / 0,997 |
| modelo × medida | 0,996 / 0,996 | 0,976 / 0,972 | 0,997 / 0,997 |

Causa de a classe ficar abaixo de 0,90, quando fica: idem 10 (P-09)

O modelo × programada de 0,950–0,999 e programada × medida de 0,996–0,997 mostram que a perda é pequena nesta classe.

## 9. Quirks e armadilhas

- **A20, A2, A3, A4, A5, A16, K7:** como na {doc}`10-sag-harmonics` e na {doc}`06-flicker`.
- **Pré-validação de rms:** o nível $\ell \cdot V_\text{base}$ não é conferido pela pré-validação (a classe não conhece o rms antes de gerar); o que barra é o extremo previsto.
- **Acoplamento:** a ordem das duas chamadas a `perfis.composto` define o `rng`.

## 10. Histórico por versão

- **v1.12:** bloqueio prévio do extremo físico.
- **v1.13:** o limite de bancada reduz só o distúrbio; a 220 V a 13 roda reduzida; `capturas_padrao` fica em 1.
- **v1.14:** fator 1,063 a 127 V/50 Hz e 1,047 a 230 V/50 Hz.
- **v1.15:** `capturas_padrao` = 3; swell U(1,1; 1,8) e THD U(0,05; 0,20) sorteados; a 220 V a 13 roda 1 de 3 e a 14 roda 0 de 3 (`CHANGELOG/v1.15.md`, "não verificado de novo"); a 230 V/50 Hz a 13 roda 2 de 3.

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| Swell 1,3 com THD 20 % via TRACe/LIST | {bdg-success}`VERIFICADO NA BANCADA` | 3 condições, 07/10/2026; programada × medida 0,996–0,997 |
| Parâmetros sorteados; 230 V/50 Hz com swell alto | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15; 2 de 3 rodam por conta offline |
| `gerar()` e programada de hoje | {bdg-info}`OFFLINE` | modelo × programada 0,950–0,999 |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
:::

:::{warning} Decisão em aberto P-11
Manter ou reverter as extensões das compostas, entre elas o swell em 13 e 14 e o THD em 13, 15 e 16. Decisão do responsável pelo projeto ({ref}`P-11 <p-11>`, prioridade MÉDIA).
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
| `Experimento.gerar` ([experimentos_waveform/13.py:21-31](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/13.py#L21-L31)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"swell_pu", "thd", "inicio_disturbio_s", "duracao_s", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.parametros_com_disturbio_reduzido` ([experimentos_waveform/13.py:33-40](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/13.py#L33-L40)) | `parametros`, `fracao` ($k$) | `{"swell_pu_bancada", "thd_bancada"}` | a linha [mestre.py:3109](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3109) de `ExperimentoWaveform._limitar_disturbio_para_bancada` |

- `gerar` chama `perfis.composto(self.config, "swell_composto", ...)` e `"thd_composto"`, depois `self.sortear(..., inicio_legado_s=0.060, duracao_legada_s=0.060, duracao_variavel=True)`, e **substitui** a janela por `swell * sinais.onda_com_harmonicos(...)`.
- Atributos: `capturas_padrao` = 3 ([13.py:18](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/13.py#L18)). `pre_trigger_s` herdado.
- Contrato e acoplamentos: {doc}`../codigo/classes_contrato` §4.

## 13. Referências

- Código: `experimentos_waveform/13.py`; `logica/perfis.py` (`composto`, `FAIXAS_SORTEADAS`); `logica/sinais.py` (`onda_com_harmonicos`).
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`10-sag-harmonics`, {doc}`../limites_e_calibracao`, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`.
- Histórico: `CHANGELOG/v1.12.md`, `v1.13.md`, `v1.14.md`, `v1.15.md`. Norma: IEEE Std 1159-2019, Tabela 2, itens 2.1.2 e 5.2.
