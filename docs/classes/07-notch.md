# Classe 07: NOTCH

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 (entalhes em 4 a 5 ciclos; 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` entalhes em todos os ciclos e a validação da crista {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-07` {bdg-danger}`PENDENTE P-18` {bdg-danger}`PENDENTE P-19`

| Campo | Valor |
|---|---|
| Número e nome | 07 NOTCH (entalhe) |
| Arquivo | `experimentos_waveform/07.py`, classe `Experimento(ExperimentoWaveform)` |
| Mecanismo na bancada | **forma de onda**: TRACe/LIST ({scpi}`TRACe:DATA`, {scpi}`SOURce:LIST:VOLTage`, um passo por ciclo) |
| `capturas_padrao` | 3 ([07.py:15](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/07.py#L15)) |
| Sorteio de posição | F (só a fase; os entalhes ocupam a janela inteira) |
| Depende do perfil? | não: capturada uma vez com `set perfil todos` |
| Condições já medidas | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 3 capturas cada (a 230 V/50 Hz com o distúrbio reduzido a 39 %) |

## 1. Em uma resposta

**Pergunta:** a fonte reproduz entalhes de 0,1 ms? **Resposta:** reproduz **com oscilação**: cada degrau a 0 pu excita uma oscilação da saída de ~7,5 a 10 kHz que morre em menos de 0,5 ms e eleva o pico; a forma programada tem pulsos de 0,1 ms em **todos** os ciclos da janela (desde a v1.15) e a validação física tolera o toque pelo fator de extremo calibrado, que a 127 V/60 Hz **ainda não cobre** (a primeira rodada tende a reprovar pela crista, P-07).

## 2. O fenômeno e a norma

Entalhe (*notching*): perturbação periódica da tensão causada pela comutação de conversores, em regime permanente, com a duração de poucas centenas de microssegundos junto aos picos. A cláusula 4.4.5.4 e o item 5.4 da Tabela 2 da IEEE Std 1159-2019 o descrevem como **periódico e contínuo** (e não como um evento isolado em alguns ciclos). Por isso, desde a v1.15, o modelo põe entalhes em todos os ciclos da janela; a especificação original (`experimentos.txt`, classe 7) pedia 4 ciclos a partir de 60 ms.

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

Com $T=1/f_0$ e a origem $o=-\tau$ (instante em que a senoide cruza zero subindo), cada ciclo $c$ da janela tem os picos em $o+cT+T/4$ e $o+cT+3T/4$; nele sorteiam-se $n_c\in\{2,3,4\}$ pulsos que alternam entre os dois picos, cada um centrado em $p+\delta$, $\delta\sim\mathcal{U}(-0{,}35;\,0{,}35)$ ms, e zeram as amostras a menos de 0,05 ms do centro (largura de 0,1 ms, 2 a 3 amostras a 30 kSa/s):

$$
v(t)=\sin\!\big(2\pi f_0\,(t+\tau)\big)\cdot\Big(1-\sum_{j}\mathbb{1}\big[\,|t-c_j|<0{,}05\ \text{ms}\,\big]\Big),\qquad n_\text{pulsos}\approx 3\ \text{por ciclo}
$$

Com `set sorteio off` vale o `gerar()` de 34a0d82: `aplicar_entalhes` em 80 ms a partir de 60 ms (4 ciclos a 50 Hz, 5 a 60 Hz), fase 0.

```{literalinclude} ../../experimentos_waveform/07.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_waveform/07.py, Experimento.gerar
```

```{literalinclude} ../../logica/sinais.py
:pyobject: aplicar_entalhes_continuos
:language: python
:caption: logica/sinais.py, aplicar_entalhes_continuos
```

- **Ordem do `rng`:** por ciclo, um `rng.integers(2, 5)` e, por pulso, um `rng.uniform(-0.00035, 0.00035)`. `aplicar_entalhes_continuos` **consome o `rng` também dos ciclos que ficam só em parte na janela** (e dos pulsos fora dela), para a forma não depender de onde a janela corta. Mudar o número de chamadas por ciclo muda todas as formas da seed ({doc}`../codigo/acoplamentos`).
- **Parâmetros no metadata:** `notch_pulses` (número de pulsos que caíram na janela) e `fase_graus`.
- **Pulsos por captura:** cerca de 36 a 60 Hz com entalhes contínuos (eram ~15 com 4 ciclos).
- **Seed:** `base_seed + 7 · 1 000 000 + indice_global`.
- **Capturas:** `capturas_padrao` = 3 ([07.py:15](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/07.py#L15)).

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** os entalhes de 0,1 ms chegam à saída? **Resposta:** chegam, mas com o **toque da fonte**: a TRACe tem 1024 pontos por ciclo (16,3 µs a 60 Hz, 19,5 µs a 50 Hz), então o pulso de 0,1 ms ocupa cerca de 5 a 6 pontos, e a saída da MX30 oscila depois de cada degrau (quirk A20).

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

O gancho `parametros_com_disturbio_reduzido` ([07.py:38-43](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/07.py#L38-L43)) devolve `notch_profundidade_pu_bancada` $=k$: o modelo zera a tensão nos pontos; reduzido, ela desce só a fração $k$ do valor instantâneo.

**Janela e margem.** `pre_trigger_s` herdado (0); registro de 20 ms antes e 50 ms depois ({doc}`../medicao`).

### O toque da fonte e a crista

A saída da MX30 oscila em ~7,5 a 10 kHz depois de um degrau rápido, e a oscilação morre em menos de 0,5 ms: sobressinal de 0,38 (60 Hz) a 0,457 (50 Hz) do degrau e subsinal de 0,55 a 0,58 (quirk A20, medido com a classe 08). Com 4 ciclos entalhados a **mediana** da crista não era afetada; com entalhes em todos os ciclos o sobressinal entra no pico de **todo** ciclo e move a mediana. Uma simulação offline com filtro de 2.ª ordem (frequência natural de 10 kHz, amortecimento 0,2, degrau segurado pelo conversor) dá crista medida 31 % a 33 % acima da esperada (31 % a 59 % na banda de 9 a 11 kHz e amortecimento 0,1 a 0,3). O modelo é **pessimista** contra o dado real (a 07 antiga mediu extremo de 1,18 pu em 30/09: vale de −212 V sobre pico base de 179,6 V). O toque real com 30 ou mais ciclos é {bdg-warning}`NÃO VERIFICADO`.

## 5. Parâmetros por perfil

Esta classe não lê nenhum componente de `perfis.py` (`COMPONENTES_POR_CLASSE` não a lista): `gerar()` é igual nos três perfis.

A 07 é **independente do perfil**: largura, número de pulsos e jitter são constantes de `sinais.py`. É uma das oito classes que `perfis.classes_independentes_do_perfil` lista com o sorteio ligado.

## 6. Limites físicos e fator de extremo

A 07 tem o **maior fator de extremo das tabelas a 50 Hz**: 1,375 a 127 V/50 Hz e 1,317 a 230 V/50 Hz; a 127 V/60 Hz é 1,186 (`calibracao_extremos.json`). O pico programado é o da senoide (1 pu); o toque é o que o fator mede.

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,186 | 3 | 179,6 | 234,3 | 415,8 | 100 % | 3/3 rodam |
| 127 V/50 Hz | 1,375 | 3 | 179,6 | 271,7 | 415,8 | 100 % | 3/3 rodam |
| 230 V/50 Hz | 1,317 | 3 | 325,3 | 415,8 | 415,8 | 32 % | 3/3 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 3 | 311,1 | 415,8 | 415,8 | 37 % | 3/3 rodam |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 3 capturas padrão, seed 20260827, sorteio ligado). A 230 V/50 Hz as três capturas rodam com o distúrbio **reduzido** a ~32 % pela regra por frequência (fator 1,375 a 1,063 da 01: $k$ = 0,317); em 07/10 o $k$ era 0,39 com a regra anterior. A 220 V/60 Hz (sem tabela) roda a 37 %. Com `set recalibracao on` o fator da 07 sobe no fim do run (a recalibração nunca desce um fator); a previsão é de ~1,3 a 1,4 a 60 Hz, hipótese que depende do toque real ({doc}`../medicao/recalibracao`).

:::{warning} Decisão em aberto P-04
`AmetekMX30.program_capture` só **avisa** quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga", [ametek_orm.py:1522-1527](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1522-L1527)); quem recusa é a pré-validação do `mestre.py` (`ExperimentoBase._indices_viaveis`, antes de qualquer SCPI, e `_conferir_extremos_fisicos`, depois da captura já gravada). Pergunta ao responsável pelo projeto: o ORM também deve recusar? Opções: manter como está, ou recusar no ORM (um limite de segurança mais restritivo). Este site não decide ({ref}`P-04 <p-04>`, prioridade MÉDIA).
:::

:::{warning} Decisão em aberto P-23
A fonte travou na ~280.ª gravação de TRACe de uma mesma conexão (quirk A3; causa {bdg-warning}`NÃO VERIFICADO`), e cada captura desta classe grava 12 TRACes a 60 Hz (10 a 50 Hz). `README.md` e `AGENTS.md` ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `set perfil todos`), enquanto o roteiro de bancada usa listas de classes (menos de 250 por conexão). Pergunta: qual texto os documentos devem adotar? Opção recomendada pelo roteiro: listas (`run 01-07`, depois `run 09-20`). Decisão do responsável pelo projeto ({ref}`P-23 <p-23>`, prioridade MÉDIA).
:::

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. Na 07 a sonda que importa é a **crista**: aceita-se $[c\,(0{,}9),\ c\cdot g\cdot 1{,}1]$ com $c$ a crista do modelo e $g$ o fator calibrado da classe (`fator_extremo_efetivo_para_validacao`, [mestre.py:1896-1920](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1896-L1920)).

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,708–0,709 / 0,707 | 0,696–0,701 / 0,694–0,697 | 0,720 / 0,707 | 0,022–0,031 / 0,023–0,032 | 1,442–1,444 / 1,417 |
| 127 V/50 Hz | 0,701–0,703 / 0,707 | 0,684–0,687 / 0,693 | 0,717–0,718 / 0,707 | 0,025–0,037 / 0,026–0,038 | 1,456 / 1,414 |
| 230 V/50 Hz | 0,704 / 0,707 | 0,694–0,696 / 0,698 | 0,711–0,712 / 0,707 | 0,010–0,014 / 0,010–0,015 | 1,442–1,446 / 1,414 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`, entalhes em 4 a 5 ciclos). A crista medida (1,44 a 1,46) contra 1,417 esperado está dentro dos 10 % do código de então.

**O que esperar da primeira rodada com o código da v1.15** (simulação offline da crista com fator calibrado: modelo de 2.ª ordem, 127 V, 15 capturas por combinação da banda = 135 por linha; razão = crista medida ÷ crista do modelo; "fator mínimo" = máximo da razão ÷ 1,1, o fator que aprovaria 100 % da banda):

| f0 | Fator calibrado (JSON) | Razão mediana / p95 / máx. | Fator mínimo | Fator para 95 % | Aprovadas com o calibrado | Aprovadas com 1,0 |
|---|---|---|---|---|---|---|
| 60 Hz | 1,186 | 1,312 / 1,423 / 1,479 | 1,344 | 1,293 | 58/135 | 0/135 |
| 50 Hz | 1,375 | 1,312 / 1,435 / 1,510 | 1,373 | 1,305 | 135/135 | 0/135 |

A 60 Hz o fator calibrado com 4 ciclos entalhados (1,186) **não cobre** o toque do modelo: se a fonte tocar como o modelo, a primeira captura da 07 a 127 V/60 Hz reprova pela crista (razão mediana 1,312 contra o limite 1,186 × 1,1 = 1,305). A 50 Hz o fator (1,375) vem de outra medida e cobre quase tudo. A recalibração ao fim do run só vale para o run **seguinte**; dentro do run as três capturas usam o fator antigo.

:::{important} Pendência P-07
Crista da validação física: fatores calibrados a 127 V/60 Hz (07 = 1,186; 17 = 1,031) não cobrem o toque simulado (≥ 1,344 e ≥ 1,420); a primeira rodada tende a reprovar só por "fator de crista". Fecha com: bancada (rodar com `set recalibracao on`, `git diff`, commitar). Prioridade ALTA.
:::

## 8. As três versões e a correlação esperada

A `programada` da 07 é a reconstrução da TRACe (cada ciclo sem a média, 1024 pontos): os entalhes de 0,1 ms entram **suavizados pela reamostragem**, e o toque da fonte fica só na `medida`.

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 0,993–0,996 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,911–0,951 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,899–0,942 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 0,993–0,995 / 0,993–0,995 | 0,993–0,995 / 0,993–0,994 | 0,994–0,996 / 0,994–0,995 | 0,995–0,996 / 0,995–0,996 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,933–0,951 / 0,934–0,950 | 0,926–0,938 / 0,931–0,943 | 0,911–0,933 / 0,920–0,935 |
| modelo × medida | 0,916–0,942 / 0,917–0,942 | 0,912–0,924 / 0,917–0,930 | 0,899–0,922 / 0,907–0,924 |

Causa de a classe ficar abaixo de 0,90, quando fica: não fica abaixo de 0,90 na programada (0,91–0,95) nem no modelo (0,90–0,94; 0,899 a 230 V/50 Hz); a queda vem da oscilação da saída depois de cada entalhe (A20)

Modelo × programada é 0,993–0,996, e a medida cai a 0,90–0,95 porque a saída oscila depois do entalhe (A20); a 07 não fica abaixo de 0,90 em programada × medida (0,91–0,95) nem em modelo × medida (0,90–0,94; 0,899 a 230 V/50 Hz). A calibração da crista é a mesma causa vista por outra métrica.

## 9. Quirks e armadilhas

- **A20:** a saída oscila após degrau rápido (~7,5–10 kHz, morre em < 0,5 ms): sobressinal 0,38 a 0,457 do degrau.
- **A4, A5, A16:** `SOURce:LIST:REPeat` com `0`; o `REPeat 1` tocava cada ciclo duas vezes (516 ms em vez de ~200 ms, e 438 ms com `0`, causa completa não explicada).
- **A2, A3:** sem consulta após `TRACe:DATA`; trava na ~280.ª gravação de TRACe.
- **Amplitude do entalhe e fator de extremo:** com `k` < 1 o fator efetivo vira a fórmula de `extremo_previsto_com_disturbio_v` ([mestre.py:649-670](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L649-L670)).
- **Acoplamento:** o número de chamadas ao `rng` por ciclo em `aplicar_entalhes_continuos` fixa todas as formas da seed (fixtures byte a byte).

## 10. Histórico por versão

- **v1.9 e v1.10:** a 07 foi a classe usada para medir o efeito de `SOURce:LIST:REPeat`: com `1` o NOTCH levou 516 ms (2,58 vezes os ~200 ms nominais) e com `0` 438 ms; a causa dos 438 ms não foi explicada.
- **v1.13:** `capturas_padrao` = 3 (há sorteio de posição de entalhe); o gancho `parametros_com_disturbio_reduzido`.
- **v1.14:** a 230 V/50 Hz a 07 mediu fator 1,317 e passou a rodar com o distúrbio reduzido a ~38 %; a 127 V/50 Hz o fator subiu a 1,375.
- **v1.15:** entalhes **contínuos** (IEEE 1159-2019, 4.4.5.4): `sinais.aplicar_entalhes_continuos`, só a fase sorteada, pulsos por captura de ~15 para ~36 a 60 Hz; simulação offline do toque (crista 31–59 % acima); crista com fator calibrado: a validação da crista usa a calibração de extremos em vez de afrouxar a tolerância (decisão de projeto de 2026-10-13).

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| Entalhes em 4 a 5 ciclos chegam à saída, com toque | {bdg-success}`VERIFICADO NA BANCADA` | 3 condições, 07/10/2026; fatores 1,186, 1,375 e 1,317 |
| `gerar()` com entalhes contínuos | {bdg-info}`OFFLINE` | `Classes05_07_18Tests`; modelo × programada 0,993–0,996 |
| Entalhes em todos os ciclos na fonte real | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15; atenuação dos pulsos de 0,1 ms e sobressinal com 10–12 ciclos desconhecidos |
| A primeira rodada a 127 V/60 Hz reprova pela crista | {bdg-warning}`NÃO VERIFICADO` | previsão por simulação (crista com fator calibrado); fecha com a bancada |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
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
| `Experimento.gerar` ([experimentos_waveform/07.py:17-36](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/07.py#L17-L36)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"notch_pulses", "fase_graus"})` com sorteio; com `set sorteio off`, também `inicio_disturbio_s` e `duracao_s` legados | os chamadores da seção 3 |
| `Experimento.parametros_com_disturbio_reduzido` ([experimentos_waveform/07.py:38-43](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/07.py#L38-L43)) | `parametros`, `fracao` ($k$) | `{"notch_profundidade_pu_bancada": k}` | a linha [mestre.py:3109](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3109) de `ExperimentoWaveform._limitar_disturbio_para_bancada` |

- `gerar` tem dois caminhos, decididos por `getattr(self.config, "sorteio_posicao", True)`. **Com sorteio:** `self.sortear(rng, f0)` (só fase), senoide deslocada e `sinais.aplicar_entalhes_continuos(voltage, t, rng, frequencia_hz=f0, origem_s=-sorteio.deslocamento_s)`. **Sem sorteio:** `sortear(..., inicio_legado_s=0.060, duracao_legada_s=0.080)` e `sinais.aplicar_entalhes` ([sinais.py:65-89](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L65-L89)), que reproduz 34a0d82.
- O número de pulsos devolvido em `notch_pulses` conta só os que caíram na janela.
- Atributos: `capturas_padrao` = 3 ([07.py:15](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/07.py#L15)). `pre_trigger_s` herdado.
- Contrato e ganchos: {doc}`../codigo/classes_contrato`; sinais: {doc}`../codigo/sinais`.

## 13. Referências

- Código: `experimentos_waveform/07.py`; `logica/sinais.py` (`aplicar_entalhes_continuos`, `aplicar_entalhes`, `comparar_fisicamente`); `logica/mestre.py` (`fator_extremo_efetivo_para_validacao`).
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`../scpi/sequencias` §7, {doc}`../medicao/correlacao`, {doc}`../medicao/recalibracao`, {doc}`../projeto/pendencias`.
- Histórico: `CHANGELOG/v1.9.md`, `v1.10.md`, `v1.13.md`, `v1.14.md`, `v1.15.md` (seções "Classes 05, 07, 17 e 18", "Pendentes de classe conferíveis offline" e "Crista esperada da validação física"). Norma: IEEE Std 1159-2019, Tabela 2, item 5.4 e cláusula 4.4.5.4.
