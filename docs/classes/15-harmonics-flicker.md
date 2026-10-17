# Classe 15: HARMONICS_FLICKER

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 com parâmetros fixos (THD 20 % e flicker de 15 Hz a ±10 %; 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 1 captura cada, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` parâmetros sorteados; flicker de 25 Hz e a média por ciclo {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-11` {bdg-danger}`PENDENTE P-12` {bdg-danger}`PENDENTE P-18` {bdg-danger}`PENDENTE P-19`

| Campo | Valor |
|---|---|
| Número e nome | 15 HARMONICS_FLICKER (harmônicos com flicker) |
| Arquivo | `experimentos_waveform/15.py`, classe `Experimento(ExperimentoWaveform)` |
| Mecanismo na bancada | **forma de onda**: TRACe/LIST ({scpi}`TRACe:DATA`, {scpi}`SOURce:LIST:VOLTage`, um passo por ciclo) |
| `capturas_padrao` | 3 ([15.py:14](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/15.py#L14)) |
| Sorteio de posição | F (só a fase: os 200 ms inteiros são distorcidos), mais THD, profundidade e frequência do flicker |
| Depende do perfil? | sim: o THD sorteado (a `norma` começa em 2 %) e a profundidade (2 a 7 % na `norma`) mudam |
| Condições já medidas | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 1 captura cada, com parâmetros fixos |

## 1. Em uma resposta

**Pergunta:** como o dataset combina harmônicos com flicker? **Resposta:** nos **200 ms inteiros** a forma é a soma de 3.ª, 5.ª e 7.ª harmônicas (THD de 5 a 20 %) multiplicada por uma modulação de amplitude de 8 a 25 Hz; não há evento localizado, então não há ciclos de borda. É a única composta sem o gancho `parametros_com_disturbio_reduzido`: quando o limite de bancada reduz o distúrbio (a 220 V), o metadata traz `fator_disturbio_bancada`, mas não `thd_bancada` nem `flicker_depth_bancada`.

## 2. O fenômeno e a norma

Composta da distorção harmônica (item 5.2 da Tabela 2 da IEEE Std 1159-2019, 0 a 20 % de THD) com a flutuação de tensão (item 6.0, 0,1 a 7 %, abaixo de 25 Hz). A norma não define a composição. A especificação (`experimentos.txt`, classe 15) fixava THD 20 % e flicker de ±10 % a 15 Hz em toda a janela; desde a v1.15 todos os três são sorteados.

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v(t)=\big[1+m\,\sin(2\pi f_\text{fl}\,t)\big]\;\big[\sin\theta+a_3\sin3\theta+a_5\sin5\theta+a_7\sin7\theta\big],\qquad \theta=2\pi f_0(t+\tau)
$$

com $a_k=\mathrm{THD}\,r_k/\lVert r\rVert$, $r=(0{,}60;\,0{,}30;\,0{,}10)$ ({doc}`10-sag-harmonics`). O flicker multiplica **os harmônicos também**; a modulação usa $t$, não $t+\tau$. $\varphi$ vem do sub-fluxo do sorteio de fase ({ref}`fórmulas <sorteio-de-posicao>`).

```{literalinclude} ../../experimentos_waveform/15.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_waveform/15.py, Experimento.gerar
```

- **Ordem do `rng`:** `perfis.composto` consome um `rng.uniform` por chamada: THD (`thd_composto`), profundidade (`flicker_composto`), frequência (`flicker_composto_hz`).
- **Parâmetros no metadata:** `thd`, `flicker_hz`, `flicker_depth`, `fase_graus` (sem `inicio_disturbio_s` nem `duracao_s`: os 200 ms inteiros).
- **Seed:** `base_seed + 15 · 1 000 000 + indice_global`.
- **Capturas:** `capturas_padrao` = 3 ([15.py:14](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/15.py#L14)). Com o sorteio, as formas distintas em 2000 capturas passam de 1543 a 2000 (v1.15).

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** o que a TRACe por ciclo faz com harmônicos modulados? **Resposta:** os harmônicos vão no formato de cada ciclo e a modulação lenta vai nos rms de passo; o flicker de 25 Hz vira degraus de um ciclo e sai com erro máximo de até 0,053 pu contra o modelo.

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

Sem evento localizado não há ciclos de borda; o que resta é a **média por ciclo do flicker** ({doc}`06-flicker`), cujo efeito nesta classe e na 11 não foi calculado ({bdg-warning}`NÃO VERIFICADO`, {ref}`P-12 <p-12>`).

Representação por ciclo medida na revisão das compostas (`programada_pu` contra `gerar()`, flicker de 25 Hz, 60 capturas; `CHANGELOG/v1.15.md`):

| Classe e f_fl | 50 Hz: erro máx. (pu) / rms relativo | 60 Hz: erro máx. (pu) / rms relativo | Pico do distúrbio, modelo → programada |
|---|---|---|---|
| 15, 25 Hz | 0,031 / 4,3 % | 0,053 / 5,4 % | 0,218 → 0,237 |

| Erro máximo \|programada − modelo\| (pu) | 50 Hz, 127 V | 60 Hz, 230 V |
|---|---|---|
| antes da correção do rms CA | 0,0309 | 0,0259 |
| depois (código de hoje) | 0,0301 | 0,0253 |

*Fonte:* `CHANGELOG/v1.15.md`, "RMS por ciclo da TRACE" (`gerar()` com sorteio ligado, seed 32, simulação offline, sem hardware).

:::{warning} Decisão em aberto P-12
Para a 06, comparar contra a forma programada ou redefinir o flicker com média nula por ciclo; as classes 11 e 15 herdam o efeito, ainda não calculado. Decisão do responsável pelo projeto ({ref}`P-12 <p-12>`, prioridade MÉDIA; detalhes na {doc}`06-flicker`).
:::

**Janela e margem.** `pre_trigger_s` herdado (0); os 200 ms distorcidos; registro de 20 ms antes e 50 ms depois ({doc}`../medicao`).

:::{warning} Decisão em aberto P-04
`AmetekMX30.program_capture` só **avisa** quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga", [ametek_orm.py:1522-1527](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1522-L1527)); quem recusa é a pré-validação do `mestre.py` (`ExperimentoBase._indices_viaveis`, antes de qualquer SCPI, e `_conferir_extremos_fisicos`, depois da captura já gravada). Pergunta ao responsável pelo projeto: o ORM também deve recusar? Opções: manter como está, ou recusar no ORM (um limite de segurança mais restritivo). Este site não decide ({ref}`P-04 <p-04>`, prioridade MÉDIA).
:::

:::{warning} Decisão em aberto P-23
A fonte travou na ~280.ª gravação de TRACe de uma mesma conexão (quirk A3; causa {bdg-warning}`NÃO VERIFICADO`), e cada captura desta classe grava 12 TRACes a 60 Hz (10 a 50 Hz). `README.md` e `AGENTS.md` ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `set perfil todos`), enquanto o roteiro de bancada usa listas de classes (menos de 250 por conexão). Pergunta: qual texto os documentos devem adotar? Opção recomendada pelo roteiro: listas (`run 01-07`, depois `run 09-20`). Decisão do responsável pelo projeto ({ref}`P-23 <p-23>`, prioridade MÉDIA).
:::

## 5. Parâmetros por perfil

**O que o sorteio cobre em cada componente.** Na 15: THD (5 a 20 % na `literatura`; 2 a 20 % na `norma`), profundidade do flicker (a faixa da 06 do perfil) e frequência (8 a 25 Hz). ({ref}`Detalhe das compostas <sorteio-das-compostas>`.)

| Componente em `perfis.py` | `norma` | `literatura` (padrão) | `fronteira` |
|---|---|---|---|
| `thd_composto` | sorteio off: 0,2; sorteio on: U(0,02; 0,2) | sorteio off: 0,2; sorteio on: U(0,05; 0,2) | sorteio off: 0,2; sorteio on: U(0,05; 0,2) |
| `flicker_composto` | sorteio off: 0,045; sorteio on: U(0,02; 0,07) | sorteio off: 0,1; sorteio on: U(0,05; 0,15) | sorteio off: 0,1; sorteio on: U(0,05; 0,15) |
| `flicker_composto_hz` | sorteio off: 15; sorteio on: U(8; 25) | sorteio off: 15; sorteio on: U(8; 25) | sorteio off: 15; sorteio on: U(8; 25) |

O perfil `fronteira` usa os componentes da literatura. Os valores com `set sorteio off` (THD 20 %, profundidade 10 % na `literatura`/`fronteira` e 4,5 % na `norma`, 15 Hz) reproduzem o `gerar()` de 34a0d82. Com o sorteio ligado a 15 **depende do perfil** (`flicker_composto` e `thd_composto` mudam entre perfis).

## 6. Limites físicos e fator de extremo

A forma não tem degrau de evento: o pico programado é o da soma harmônica modulada (167 a 174 V a 127 V nas capturas do relatório offline, ~0,93 a 0,97 pu) e o fator de extremo é próximo de 1 (1,017 a 127 V/60 Hz, 1,034 a 127 V/50 Hz e 1,028 a 230 V/50 Hz).

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,017 | 3 | 167,5–173,7 | 187,4–194,4 | 415,8 | 100 % | 3/3 rodam |
| 127 V/50 Hz | 1,034 | 3 | 167,4–173,7 | 190,4–197,6 | 415,8 | 100 % | 3/3 rodam |
| 230 V/50 Hz | 1,028 | 3 | 303,2–314,6 | 344,8–357,8 | 415,8 | 100 % | 3/3 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 3 | 301,0–306,9 | 415,8 | 415,8 | 42–49 % | 3/3 rodam |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 3 capturas padrão, seed 20260827, sorteio ligado). A 230 V/50 Hz as três rodam inteiras; a 220 V/60 Hz (sem tabela) rodam reduzidas a 42–49 %, e aí falta o gancho: o metadata registra o `fator_disturbio_bancada` mas não os parâmetros físicos aplicados.

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. O THD confere os harmônicos.

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,723 / 0,721 | 0,667 / 0,656 | 0,780 / 0,787 | 0,199 / 0,200 | 1,251 / 1,257 |
| 127 V/50 Hz | 0,725 / 0,721 | 0,651 / 0,651 | 0,797 / 0,791 | 0,200 / 0,200 | 1,250 / 1,258 |
| 230 V/50 Hz | 0,723 / 0,721 | 0,655 / 0,651 | 0,791 / 0,791 | 0,199 / 0,200 | 1,252 / 1,258 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`, THD 20 % e flicker de 15 Hz fixos). O THD medido (19,9 a 20,0 %) bate o esperado (20,0 %) nas três condições; o máximo do envelope acompanha.

## 8. As três versões e a correlação esperada

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 0,966–0,995 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,998 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,988–0,991 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 0,990 / 0,990 | 0,966–0,993 / 0,966–0,993 | 0,993 / 0,993 | 0,976–0,995 / 0,976–0,995 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,998 / 0,998 | 0,998 / 0,998 | 0,998 / 0,998 |
| modelo × medida | 0,988 / 0,989 | 0,991 / 0,991 | 0,988 / 0,988 |

Causa de a classe ficar abaixo de 0,90, quando fica: —

A 15 fica **sempre acima de 0,95** em modelo × programada com o sorteio ligado (0,966–0,995) e em programada × medida (0,998): sem bordas de evento, a perda é só a média do flicker.

## 9. Quirks e armadilhas

- **A2, A3, A4, A5, A16, K7:** como na {doc}`06-flicker`.
- **Sem gancho de bancada:** `Experimento` não define `parametros_com_disturbio_reduzido` (a única composta sem ele); com redução (220 V), `thd_bancada` e `flicker_depth_bancada` não vão ao metadata (`CHANGELOG/v1.15.md`, "Revisão das compostas sorteadas"). A forma física segue sendo `senoide + k·(gerar() − senoide)`, e `analisar_sessao` a reconstrói a partir de `fator_disturbio_bancada`.
- **Acoplamento:** a ordem das três chamadas a `perfis.composto` define o `rng`.

## 10. Histórico por versão

- **v1.12 a v1.14:** a 15 rodava com parâmetros fixos (THD 20 %, flicker de 15 Hz a ±10 %) e sem sorteio de posição; `capturas_padrao` = 1.
- **v1.15:** `capturas_padrao` = 3; THD (extensão (f)), profundidade e frequência sorteados, fase sorteada (formas distintas em 2000 capturas: de 1543 a 2000); a revisão contra a proposta registra a ausência do gancho de bancada.

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| THD 20 % com flicker de 15 Hz via TRACe/LIST | {bdg-success}`VERIFICADO NA BANCADA` | 3 condições, 07/10/2026; THD 19,9–20,0 %; programada × medida 0,998 |
| Parâmetros sorteados; flicker de 25 Hz e a média por ciclo | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15 |
| `gerar()` e programada de hoje | {bdg-info}`OFFLINE` | modelo × programada 0,966–0,995 |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
:::

:::{warning} Decisão em aberto P-11
Manter ou reverter as extensões das compostas (THD sorteado em 13, 15 e 16, faixas da `norma`, ...) e acrescentar ou não o gancho `parametros_com_disturbio_reduzido` à 15. Decisão do responsável pelo projeto ({ref}`P-11 <p-11>`, prioridade MÉDIA).
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
| `Experimento.gerar` ([experimentos_waveform/15.py:17-24](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/15.py#L17-L24)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"thd", "flicker_hz", "flicker_depth", "fase_graus"})` | os chamadores da seção 3 |

- `gerar` chama `perfis.composto` três vezes (`thd_composto`, `flicker_composto`, `flicker_composto_hz`), monta `flicker = 1 + profundidade * sin(2π f t)`, chama `self.sortear(rng, f0)` (só fase) e devolve `flicker * sinais.onda_com_harmonicos(t + sorteio.deslocamento_s, thd, frequencia_hz=f0)` ([sinais.py:52-62](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L52-L62)).
- Atributos: `capturas_padrao` = 3 ([15.py:14](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/15.py#L14)). **Sem** `parametros_com_disturbio_reduzido` (a base devolve `{}`; `ExperimentoWaveform.parametros_com_disturbio_reduzido`, [mestre.py:3042-3050](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3042-L3050)). `pre_trigger_s` herdado.
- Contrato e acoplamentos: {doc}`../codigo/classes_contrato` §3 (a tabela dos ganchos lista a 15 como a exceção).

## 13. Referências

- Código: `experimentos_waveform/15.py`; `logica/perfis.py` (`composto`); `logica/sinais.py` (`onda_com_harmonicos`).
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`06-flicker`, {doc}`10-sag-harmonics`, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`.
- Histórico: `CHANGELOG/v1.15.md` (seções "Parâmetros das compostas 10 a 16 sorteados" e "Revisão das compostas sorteadas"). Norma: IEEE Std 1159-2019, Tabela 2, itens 5.2 e 6.0.

## Atualização de metadata P-11

O hook `Experimento.parametros_com_disturbio_reduzido` registra os parâmetros efetivos quando o limite da bancada reduz o distúrbio, incluindo envelopes THD mínimo/máximo. O modelo de `gerar()` foi preservado. Os campos efetivos não devem ser interpretados como novo valor de THD constante: a redução conserva a composição harmônicos/flicker e é dependente do tempo. Estado e regressões em {doc}`../execucao_pendencias`.
