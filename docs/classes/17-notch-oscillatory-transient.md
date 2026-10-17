# Classe 17: NOTCH_OSCILLATORY_TRANSIENT

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 (entalhes em 4 ciclos; 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 3 capturas cada, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` entalhes contínuos e a validação da crista {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-07` {bdg-danger}`PENDENTE P-18` {bdg-danger}`PENDENTE P-19`

| Campo | Valor |
|---|---|
| Número e nome | 17 NOTCH_OSCILLATORY_TRANSIENT (entalhe com transitório oscilatório) |
| Arquivo | `experimentos_waveform/17.py`, classe `Experimento(ExperimentoWaveform)` |
| Mecanismo na bancada | **forma de onda**: TRACe/LIST ({scpi}`TRACe:DATA`, {scpi}`SOURce:LIST:VOLTage`, um passo por ciclo) |
| `capturas_padrao` | 3 ([17.py:17](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/17.py#L17)) |
| Sorteio de posição | I F, com a fase **acoplada** ao início: a senoide cruza zero em $t_0$ |
| Depende do perfil? | não: capturada uma vez com `set perfil todos` |
| Condições já medidas | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 3 capturas cada (a 230 V/50 Hz com o distúrbio reduzido a 37 %) |

## 1. Em uma resposta

**Pergunta:** como o dataset combina entalhes com um transitório oscilatório? **Resposta:** os **entalhes de 0,1 ms estão em todos os ciclos da janela** (como na {doc}`07-notch`) e uma **oscilação amortecida de 300 Hz, 0,3 pu, τ = 5 ms, começa em $t_0$ sorteado** por 60 ms. Só a oscilação é localizada; os entalhes são contínuos. A classe herda o toque da fonte de cada entalhe e herda também o problema da crista da 07, pior: a 127 V/60 Hz o fator calibrado (1,031) está muito abaixo do que o toque pede (≥ 1,420) e a primeira rodada tende a reprovar pela crista (P-07).

## 2. O fenômeno e a norma

Composta do entalhe (item 5.4 da Tabela 2 da IEEE Std 1159-2019 e cláusula 4.4.5.4: periódico e contínuo, em regime permanente) com o transitório oscilatório de baixa frequência (item 1.2.1, abaixo de 5 kHz, 0,3 a 50 ms, 0 a 4 pu). A norma não define a composição. A especificação (`experimentos.txt`, classe 17) pede o entalhe da classe 7 e uma oscilação de 300 Hz sobreposta, início 60 ms, duração 60 ms; a partir da v1.15 o entalhe vale na janela inteira e o início da oscilação é sorteado.

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v(t)=\mathcal{N}\big[\sin\theta\big](t)\;+\;0{,}3\,\sin\!\big(2\pi\cdot300\,(t-t_0)\big)\,e^{-(t-t_0)/\tau_d}\,\mathbb{1}\big[t_0\le t<t_0+0{,}060\big],\qquad \tau_d=5\ \text{ms}
$$

$\mathcal{N}$ é o operador de entalhes contínuos da 07 (`aplicar_entalhes_continuos`, 2 a 4 pulsos de 0,1 ms por ciclo, em todos os ciclos), com a grade de ciclos acompanhando a fase. A fase é **acoplada ao início** ($\theta=0$ em $t_0$, `fase_acoplada_ao_inicio=True`): a senoide cruza zero subindo em $t_0$, logo $\varphi=-360\,f_0\,t_0 \bmod 360°$. A duração do evento é fixa em 60 ms (`duracao_variavel` desligado), e só $t_0$ é sorteado ({ref}`fórmulas <sorteio-de-posicao>`). Com `set sorteio off`: `aplicar_entalhes` em 60 ms a partir de 60 ms (4 ciclos a 60 Hz, 3 a 50 Hz) e fase 0.

```{literalinclude} ../../experimentos_waveform/17.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_waveform/17.py, Experimento.gerar
```

- **Ordem do `rng`:** os entalhes consomem o `rng` (um `integers(2, 5)` por ciclo e um `uniform` por pulso, também para ciclos e pulsos fora da janela); a oscilação não consome nada (frequência fixa). Mudar o número de chamadas por ciclo muda todas as formas da seed.
- **Parâmetros no metadata:** `notch_pulses`, `oscillation_hz` (300,0), `inicio_disturbio_s`, `duracao_s` (0,06), `fase_graus`.
- **Seed:** `base_seed + 17 · 1 000 000 + indice_global`.
- **Capturas:** `capturas_padrao` = 3 ([17.py:17](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/17.py#L17)).

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** a bancada reproduz os dois componentes? **Resposta:** reproduz os dois pela lista, com o **toque da fonte** dos entalhes (7,5 a 10 kHz, morre em menos de 0,5 ms) somado à oscilação de 300 Hz, que a programação preserva. A razão pela qual a oscilação, de 300 Hz, sobrevive e os entalhes de 0,1 ms vão suavizados está em que a TRACe tem 1024 pontos por ciclo (16,3 µs a 60 Hz): a oscilação de 300 Hz tem cerca de 200 pontos por período, e o pulso do entalhe tem ~6.

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

O gancho `parametros_com_disturbio_reduzido` ([17.py:42-51](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/17.py#L42-L51)) devolve `notch_profundidade_pu_bancada` $=k$ e `oscillation_amplitude_pu_bancada` $=k\cdot0{,}3$.

**Janela e margem.** `pre_trigger_s` herdado (0); a oscilação começa em $t_0$ dentro da janela; registro de 20 ms antes e 50 ms depois ({doc}`../medicao`).

| Erro máximo \|programada − modelo\| (pu) | 50 Hz, 127 V | 60 Hz, 230 V |
|---|---|---|
| antes da correção do rms CA | 0,2926 | 0,2350 |
| depois (código de hoje) | 0,2925 | 0,2350 |

*Fonte:* `CHANGELOG/v1.15.md`, "RMS por ciclo da TRACE" (`gerar()` com sorteio ligado, seed 32, simulação offline, sem hardware).

O erro programada × modelo da 17 (0,29 pu a 50 Hz; 0,24 pu a 60 Hz) é o mesmo antes e depois da correção do rms CA: vem dos entalhes (como na 07), não do degrau do rms por ciclo.

:::{warning} Decisão em aberto P-04
`AmetekMX30.program_capture` só **avisa** quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga", [ametek_orm.py:1522-1527](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1522-L1527)); quem recusa é a pré-validação do `mestre.py` (`ExperimentoBase._indices_viaveis`, antes de qualquer SCPI, e `_conferir_extremos_fisicos`, depois da captura já gravada). Pergunta ao responsável pelo projeto: o ORM também deve recusar? Opções: manter como está, ou recusar no ORM (um limite de segurança mais restritivo). Este site não decide ({ref}`P-04 <p-04>`, prioridade MÉDIA).
:::

:::{warning} Decisão em aberto P-23
A fonte travou na ~280.ª gravação de TRACe de uma mesma conexão (quirk A3; causa {bdg-warning}`NÃO VERIFICADO`), e cada captura desta classe grava 12 TRACes a 60 Hz (10 a 50 Hz). `README.md` e `AGENTS.md` ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `set perfil todos`), enquanto o roteiro de bancada usa listas de classes (menos de 250 por conexão). Pergunta: qual texto os documentos devem adotar? Opção recomendada pelo roteiro: listas (`run 01-07`, depois `run 09-20`). Decisão do responsável pelo projeto ({ref}`P-23 <p-23>`, prioridade MÉDIA).
:::

## 5. Parâmetros por perfil

Esta classe não lê nenhum componente de `perfis.py` (`COMPONENTES_POR_CLASSE` não a lista): `gerar()` é igual nos três perfis.

A 17 é **independente do perfil**: a oscilação fica em 300 Hz e 0,3 pu (decisão de projeto (e): valores fixos na 16 e na 17), e os entalhes são constantes de `sinais.py`. É uma das oito classes que `perfis.classes_independentes_do_perfil` lista com o sorteio ligado.

## 6. Limites físicos e fator de extremo

Fatores medidos: **1,031** a 127 V/60 Hz, **1,307** a 127 V/50 Hz e **1,242** a 230 V/50 Hz. A diferença é por **frequência**, não por tensão: a 230 V/50 Hz com a tabela de 127 V/60 Hz a 17 previu 405 V e mediu **444 V**, acima dos 425 Vp do hardware (07/10/2026), e foi o caso que fez nascer a calibração por condição (v1.14).

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,031 | 3 | 203,1 | 230,4 | 415,8 | 100 % | 3/3 rodam |
| 127 V/50 Hz | 1,307 | 3 | 197,4 | 283,8 | 415,8 | 100 % | 3/3 rodam |
| 230 V/50 Hz | 1,242 | 3 | 330,9 | 415,8 | 415,8 | 30 % | 3/3 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 3 | 321,3 | 415,8 | 415,8 | 25 % | 3/3 rodam |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 3 capturas padrão, seed 20260827, sorteio ligado). A 230 V/50 Hz as três rodam com o distúrbio **reduzido a 30 %** (`notch_profundidade_pu_bancada` = 0,301 e `oscillation_amplitude_pu_bancada` = 0,090); em 07/10, com o fator 1,242 daquele dia, $k$ = 37 % e o pico máximo medido foi 382 V (antes, sem redução, 444 V). A 220 V/60 Hz (sem tabela) as três rodam a 25 %. Mudou, para menos, o previsto a 127 V/60 Hz depois da regra por frequência: de 292,0 V para 230,4 V.

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. Na 17 a sonda que importa é a **crista**, como na {doc}`07-notch`, com o fator calibrado da classe.

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,703–0,704 / 0,707 | 0,689–0,692 / 0,690–0,691 | 0,720–0,721 / 0,707 | 0,029–0,030 / 0,031–0,031 | 1,440–1,452 / 1,414 |
| 127 V/50 Hz | 0,709–0,711 / 0,707 | 0,695–0,696 / 0,693 | 0,724 / 0,707 | 0,028–0,032 / 0,028–0,033 | 1,455–1,463 / 1,414 |
| 230 V/50 Hz | 0,703 / 0,707 | 0,693–0,694 / 0,699 | 0,711–0,712 / 0,707 | 0,010–0,012 / 0,010–0,012 | 1,437–1,439 / 1,414 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`, entalhes em 4 ciclos). A crista medida (1,44–1,45 a 127 V/60 Hz) contra 1,414 esperado cabe nos 10 % do código de então.

**O que esperar da primeira rodada com o código da v1.15** (simulação offline da crista com fator calibrado, modelo de 2.ª ordem, 135 capturas por linha; razão = crista medida ÷ crista do modelo; "fator mínimo" = máximo da razão ÷ 1,1):

| f0 | Fator calibrado (JSON) | Razão mediana / p95 / máx. | Fator mínimo | Fator para 95 % | Aprovadas com o calibrado | Aprovadas com 1,0 |
|---|---|---|---|---|---|---|
| 60 Hz | 1,031 | 1,314 / 1,443 / 1,562 | 1,420 | 1,312 | **0/135** | 0/135 |
| 50 Hz | 1,307 | 1,314 / 1,424 / 1,536 | 1,397 | 1,295 | 130/135 | 0/135 |

A 17 a 127 V/60 Hz é, portanto, a classe com a **maior defasagem** entre o fator calibrado e o necessário: a primeira captura reprova pela crista se a fonte tocar como o modelo (1,314 × 1,0 contra 1,031 × 1,1 = 1,134). A recalibração (`set recalibracao on`) corrige o JSON ao fim do run, para o run seguinte.

:::{important} Pendência P-07
Crista da validação física: fatores calibrados a 127 V/60 Hz (07 = 1,186; 17 = 1,031) não cobrem o toque simulado (≥ 1,344 e ≥ 1,420); a primeira rodada tende a reprovar só por "fator de crista". Fecha com: bancada (rodar com `set recalibracao on`, `git diff`, commitar). Prioridade ALTA.
:::

## 8. As três versões e a correlação esperada

A `programada` é a reconstrução da TRACe (entalhes suavizados pela reamostragem, oscilação de 300 Hz preservada).

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 0,993–0,996 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,915–0,948 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,902–0,931 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 0,994–0,995 / 0,994–0,995 | 0,993–0,994 / 0,993–0,994 | 0,993–0,995 / 0,993–0,995 | 0,995–0,996 / 0,994–0,996 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,932–0,937 / 0,941–0,946 | 0,935–0,948 / 0,940–0,950 | 0,915–0,929 / 0,925–0,935 |
| modelo × medida | 0,914–0,923 / 0,923–0,931 | 0,921–0,931 / 0,925–0,933 | 0,902–0,918 / 0,912–0,924 |

Causa de a classe ficar abaixo de 0,90, quando fica: idem 07: oscilação da saída após o entalhe (A20)

Modelo × programada é 0,993–0,996 e a medida cai a 0,90–0,95 pela mesma causa da 07: a saída oscila depois de cada degrau do entalhe (A20). A correlação com a fundamental ajustada **sobe** (0,925–0,950), como nas outras classes de distúrbio pequeno.

## 9. Quirks e armadilhas

- **A20:** a saída oscila após degrau rápido (7,5–10 kHz, < 0,5 ms); é o que a calibração da crista tenta cobrir.
- **A2, A3, A4, A5, A16, K7:** como na {doc}`06-flicker` e na {doc}`07-notch`.
- **B7:** a 220/230 V a previsão com a tabela de 127 V/60 Hz subestimou (a 17 mediu 444 V, acima de 425 Vp); por isso as tabelas por condição.
- **Acoplamento:** a fase acoplada ao início faz $\varphi$ depender de $t_0$; o número de chamadas ao `rng` por ciclo em `aplicar_entalhes_continuos` fixa as formas ({doc}`../codigo/acoplamentos`).

## 10. Histórico por versão

- **v1.12:** a 17 entra nas 20 classes aprovadas a 127 V/60 Hz (bancada de 30/09/2026).
- **v1.14:** a 230 V/50 Hz a 17 mediu 444 V (acima dos 425 Vp) com previsão de 405 V: origem da calibração por condição; com a tabela nova a 17 mediu no máximo 382 V, reduzida a ~37 %; a 127 V/50 Hz o fator é 1,307.
- **v1.15:** o início da oscilação é sorteado, com a fase acoplada a ele; os entalhes viram contínuos (mesma regra da 07); a simulação do toque da fonte mostra a crista 31–59 % acima; a mudança da crista com fator calibrado faz a validação usar a calibração de extremos; o relatório de limites a 127 V dá 17 sem redução.

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| Entalhes em 4 ciclos com oscilação de 300 Hz via TRACe/LIST | {bdg-success}`VERIFICADO NA BANCADA` | 3 condições, 07/10/2026; fatores 1,031, 1,307 e 1,242 |
| Entalhes em todos os ciclos; crista com fator | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15; previsão por simulação |
| `gerar()` e programada de hoje | {bdg-info}`OFFLINE` | modelo × programada 0,993–0,996 |

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
| `Experimento.gerar` ([experimentos_waveform/17.py:19-40](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/17.py#L19-L40)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"notch_pulses", "oscillation_hz", "inicio_disturbio_s", "duracao_s", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.parametros_com_disturbio_reduzido` ([experimentos_waveform/17.py:42-51](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/17.py#L42-L51)) | `parametros`, `fracao` ($k$) | `{"notch_profundidade_pu_bancada", "oscillation_amplitude_pu_bancada"}` | a linha [mestre.py:3109](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3109) de `ExperimentoWaveform._limitar_disturbio_para_bancada` |

- `gerar` chama `self.sortear(rng, f0, inicio_legado_s=0.060, duracao_legada_s=0.060, fase_acoplada_ao_inicio=True)`; se `sorteio_posicao` está ligado, `sinais.aplicar_entalhes_continuos(voltage, t, rng, frequencia_hz=f0, origem_s=-sorteio.deslocamento_s)` ([sinais.py:92-128](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L92-L128)), senão `sinais.aplicar_entalhes` ([sinais.py:65-89](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L65-L89)) em `[inicio, inicio + duracao)`; depois soma `sinais.oscilacao_amortecida(t, inicio_s, duracao_s, frequencia_hz=300.0)` ([sinais.py:131-146](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L131-L146)).
- Atributos: `capturas_padrao` = 3 ([17.py:17](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/17.py#L17)). `pre_trigger_s` herdado.
- Contrato e acoplamentos: {doc}`../codigo/classes_contrato` §4 ("07, 17: o número de chamadas ao `rng` por ciclo").

## 13. Referências

- Código: `experimentos_waveform/17.py`; `logica/sinais.py` (`aplicar_entalhes_continuos`, `oscilacao_amortecida`); `logica/mestre.py` (`fator_extremo_efetivo_para_validacao`, `sortear_posicao`).
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`07-notch`, {doc}`../limites_e_calibracao`, {doc}`../medicao/recalibracao`, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`.
- Histórico: `CHANGELOG/v1.12.md`, `v1.14.md`, `v1.15.md` (seções "Classes 05, 07, 17 e 18", "Pendentes de classe conferíveis offline" e "Crista esperada da validação física"). Norma: IEEE Std 1159-2019, Tabela 2, itens 5.4 e 1.2.1.
