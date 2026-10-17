# Classe 06: FLICKER

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 (127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 3 capturas cada, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` perfil `norma`, fonte reproduzindo o flicker de 25 Hz {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-12` {bdg-danger}`PENDENTE P-18` {bdg-danger}`PENDENTE P-19`

| Campo | Valor |
|---|---|
| Número e nome | 06 FLICKER (flutuação de tensão) |
| Arquivo | `experimentos_waveform/06.py`, classe `Experimento(ExperimentoWaveform)` |
| Mecanismo na bancada | **forma de onda**: TRACe/LIST ({scpi}`TRACe:DATA`, {scpi}`SOURce:LIST:VOLTage`, um passo por ciclo) |
| `capturas_padrao` | 3 ([06.py:16](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/06.py#L16)) |
| Sorteio de posição | F (só a fase; o flicker ocupa os 200 ms) |
| Depende do perfil? | sim: a profundidade muda (`flicker_profundidade`) |
| Condições já medidas | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 3 capturas cada (a 230 V/50 Hz com o distúrbio reduzido a 87–97 %) |

## 1. Em uma resposta

**Pergunta:** a fonte reproduz o flicker? **Resposta:** **em parte**: a amplitude modulada entre 8 e 25 Hz chega à saída, mas a fonte remove a **média de cada ciclo** da TRACe, e o flicker tem média de ciclo não nula; essa média é todo o desvio entre o modelo e o que a bancada programa (correlação do distúrbio programada × modelo de 0,77 a 1,00, mediana 0,90 a 0,97). A decisão entre aceitar isso ou redefinir o flicker é do responsável pelo projeto ({ref}`P-12 <p-12>`).

## 2. O fenômeno e a norma

Flutuação de tensão: variação cíclica ou aleatória do envelope da tensão, que provoca cintilação perceptível na iluminação (*flicker*). O item 6.0 da Tabela 2 da IEEE Std 1159-2019 dá **0,1 a 7 %** de amplitude, **abaixo de 25 Hz**, e a cláusula 4.4.6 diz que a tensão fica normalmente entre 0,95 e 1,05 pu. O perfil `literatura` usa 5 a 15 % (acima da norma) e o perfil `norma` usa 2 a 7 %; a frequência de modulação, 8 a 25 Hz, é a mesma nos dois.

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v(t)=\sin\!\big(2\pi f_0\,(t+\tau)\big)\,\Big[1+m\,\sin\!\big(2\pi f_\text{fl}\,t\big)\Big],\qquad
f_\text{fl}\sim\mathcal{U}(8;\,25)\ \text{Hz},\quad m\sim\mathcal{U}(\text{faixa do perfil})
$$

$m$ é a profundidade (fração, 0,05 a 0,15 na `literatura`) e a modulação **não** carrega a fase sorteada: $\sin(2\pi f_\text{fl}t)$ parte de zero em $t=0$ enquanto a portadora tem a fase $\varphi$ ({ref}`sorteio <sorteio-de-posicao>`).

```{literalinclude} ../../experimentos_waveform/06.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_waveform/06.py, Experimento.gerar
```

- **Ordem do `rng`:** `f_fl` primeiro (`valor_para_captura`, [sinais.py:24-49](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L24-L49): sorteia, ou cobre 8 a 25 Hz por `linspace` com `set capturas N`, N > 1), depois $m$ (`rng.uniform(*faixa)`); o sorteio de fase vem de um sub-fluxo. Mudar essa ordem muda todas as formas da seed.
- **Parâmetros no metadata:** `flicker_hz`, `flicker_depth`, `fase_graus`.
- **Seed:** `base_seed + 6 · 1 000 000 + indice_global`.
- **Capturas:** `capturas_padrao` = 3 ([06.py:16](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/06.py#L16)): o parâmetro é sorteado e uma captura mostra uma só realização.

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** como se programa uma amplitude que varia a 8 a 25 Hz numa fonte que toca ciclos? **Resposta:** cada ciclo da janela vira uma TRACe de 1024 pontos e um passo da lista; a variação lenta de amplitude entre ciclos vai no **rms de cada passo** (`SOURce:LIST:VOLTage`) e a variação dentro do ciclo vai no formato da TRACe.

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

O gancho `parametros_com_disturbio_reduzido` ([06.py:30-33](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/06.py#L30-L33)) traduz o limite de bancada $k$ para o metadata: `flicker_depth_bancada` $=k\cdot m$. A forma aplicada continua sendo `senoide + k·(gerar() − senoide)`.

**Janela e margem.** `pre_trigger_s` herdado (0); sem evento localizado, o flicker ocupa a janela inteira; registro de 20 ms antes e 50 ms depois ({doc}`../medicao`).

### Por que a correlação cai: a média de cada ciclo

O manual (`TRACe:DATA`, p. 126 e 147) diz que a fonte **remove o componente CC** da TRACe e a escala ao rms de `LIST:VOLTage`. O flicker $\sin(2\pi f_0 t)(1+m\sin 2\pi f_\text{fl}t)$ tem, em cada ciclo, uma média **não nula** (vazamento espectral das bandas laterais $f_0\pm f_\text{fl}$), que cresce com $f_\text{fl}/f_0$. Medido sobre `gerar()` e `montar_programacao().programada_pu()` a 127 V:

- a média por ciclo é uma escada de rms **0,002 a 0,032 pu** (máximo 0,044 pu), contra um distúrbio de rms 0,036 a 0,074 pu: até ~47 % do distúrbio com flicker de 18 a 24 Hz;
- tirando do modelo a média de cada ciclo, a correlação programada × modelo vai a **0,9999 a 1,0000** nas 28 capturas calculadas; a interpolação de 1024 pontos custa menos que 0,001;
- não há comando de offset por passo de `LIST` no manual extraído, e `SOURce:VOLTage:OFFSet` é um valor único da captura, então a programação **não** pode reproduzir essa média. **Nada foi mudado** na programação nem no `gerar()` da 06 por causa disso (`CHANGELOG/v1.15.md`, "Pendentes da correlação do distúrbio").

Correlação programada × modelo por perfil, frequência e sorteio (mínimo / mediana / máximo; 60 sementes por linha; 127 V; v1.15):

| Perfil | f0 | Sorteio | Mín. / mediana / máx. |
|---|---|---|---|
| `norma` | 50 Hz | ligado | 0,794 / 0,953 / 0,999 |
| `norma` | 50 Hz | desligado | 0,774 / 0,902 / 0,972 |
| `norma` | 60 Hz | ligado | 0,881 / 0,966 / 1,000 |
| `norma` | 60 Hz | desligado | 0,857 / 0,916 / 0,980 |
| `literatura` e `fronteira` | 50 Hz | ligado | 0,794 / 0,953 / 0,999 |
| `literatura` e `fronteira` | 50 Hz | desligado | 0,774 / 0,902 / 0,972 |
| `literatura` e `fronteira` | 60 Hz | ligado | 0,881 / 0,966 / 1,000 |
| `literatura` e `fronteira` | 60 Hz | desligado | 0,857 / 0,916 / 0,980 |

*Fonte:* `CHANGELOG/v1.15.md`, "Pendentes da correlação do distúrbio", item 4 (simulação offline, sem hardware). Os perfis só mudam a profundidade; a correlação depende da frequência do flicker e da fase. Por faixa de $f_\text{fl}$ (`literatura`, sorteio ligado, 200 sementes):

| $f_\text{fl}$ (Hz) | 50 Hz: n, mediana (mín–máx) | 60 Hz: n, mediana (mín–máx) |
|---|---|---|
| 8–12 | 39, 0,984 (0,952–0,999) | 39, 0,989 (0,966–1,000) |
| 12–16 | 36, 0,956 (0,901–0,996) | 36, 0,969 (0,931–0,998) |
| 16–20 | 55, 0,953 (0,871–0,990) | 55, 0,966 (0,905–0,995) |
| 20–25 | 70, 0,912 (0,794–0,991) | 70, 0,939 (0,863–0,986) |

A correlação com a fundamental ajustada não muda isso (0,792–0,999, mesma mediana): é conteúdo do modelo que a TRACe não leva, não erro de fundamental. Um exemplo executável que reproduz um destes números está em {doc}`../medicao/correlacao` §7 (classe 06 a 60 Hz: `flicker_hz` = 23,5173; modelo × programada 0,8585; médias por ciclo do modelo de até ±0,02 pu e zero na programada).

:::{warning} Decisão em aberto P-12
Pergunta ao responsável pelo projeto: o que fazer com a perda de correlação da 06? Opções, da mais barata à mais cara: (a) comparar a 06 medida contra a forma **programada** (`programada_pu`, {doc}`../tres_versoes`) além do modelo e relatar a faixa 0,77–1,00 como limite da fonte, não do gerador; (b) analisar a 06 também depois de tirar a média por ciclo do modelo (métrica adicional, sem tocar `gerar()`); (c) redefinir o flicker com **média nula por ciclo**, o que muda `gerar()` e o dataset e exige autorização registrada em `AGENTS.md` e fixtures novas. Vale também para as classes 11 e 15, que herdam o efeito (não calculado). Este site não decide ({ref}`P-12 <p-12>`, prioridade MÉDIA).
:::

## 5. Parâmetros por perfil

| Componente em `perfis.py` | `norma` | `literatura` (padrão) | `fronteira` |
|---|---|---|---|
| `flicker_profundidade` | U(0,02; 0,07), sempre sorteado | U(0,05; 0,15), sempre sorteado | U(0,05; 0,15), sempre sorteado |

Só a profundidade depende do perfil; a frequência $f_\text{fl}$ (8 a 25 Hz) é igual nos três. O perfil `fronteira` usa a faixa da literatura para o flicker.

## 6. Limites físicos e fator de extremo

O flicker é uma modulação de amplitude: o pico programado é $(1+m)$ pu no máximo (205,3 V a 127 V com $m$ ≈ 0,14), e o fator de extremo é próximo de 1 (1,034 a 127 V/60 Hz).

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,034 | 3 | 202,2–205,4 | 230,0–233,6 | 415,8 | 100 % | 3/3 rodam |
| 127 V/50 Hz | 1,057 | 3 | 202,6–205,1 | 235,5–238,5 | 415,8 | 100 % | 3/3 rodam |
| 230 V/50 Hz | 1,021 | 3 | 357,6 | 415,8 | 415,8 | 70–78 % | 3/3 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 3 | 321,1–355,8 | 415,8–577,3 | 415,8 | 25–100 % | 1/3 rodam, 2 pulada(s) |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 3 capturas padrão, seed 20260827, sorteio ligado). A 230 V/50 Hz as três capturas rodam com o distúrbio **reduzido** a 70–78 %: com a forma inteira o extremo previsto passaria de 415,8 V, e a bisseção (`_limitar_disturbio_para_bancada`, [mestre.py:3052-3110](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3052-L3110)) acha o maior $k$ que cabe (`flicker_depth_bancada` ≈ 0,10), com extremo previsto igual ao teto de 415,8 V; o pico programado da forma já reduzida é 357,6 V. A 220 V/60 Hz (sem tabela) só 1 das 3 roda, com $k$ = 25 %. A fórmula e o mínimo de 25 % em {doc}`../limites_e_calibracao` §3.

:::{warning} Decisão em aberto P-04
`AmetekMX30.program_capture` só **avisa** quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga", [ametek_orm.py:1522-1527](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1522-L1527)); quem recusa é a pré-validação do `mestre.py` (`ExperimentoBase._indices_viaveis`, antes de qualquer SCPI, e `_conferir_extremos_fisicos`, depois da captura já gravada). Pergunta ao responsável pelo projeto: o ORM também deve recusar? Opções: manter como está, ou recusar no ORM (um limite de segurança mais restritivo). Este site não decide ({ref}`P-04 <p-04>`, prioridade MÉDIA).
:::

:::{warning} Decisão em aberto P-23
A fonte travou na ~280.ª gravação de TRACe de uma mesma conexão (quirk A3; causa {bdg-warning}`NÃO VERIFICADO`), e cada captura desta classe grava 12 TRACes a 60 Hz (10 a 50 Hz). `README.md` e `AGENTS.md` ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `set perfil todos`), enquanto o roteiro de bancada usa listas de classes (menos de 250 por conexão). Pergunta: qual texto os documentos devem adotar? Opção recomendada pelo roteiro: listas (`run 01-07`, depois `run 09-20`). Decisão do responsável pelo projeto ({ref}`P-23 <p-23>`, prioridade MÉDIA).
:::

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. A comparação é contra a **forma programada** (já com $k$ e sem a média por ciclo), não contra `gerar()`.

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,713–0,742 / 0,713–0,734 | 0,606–0,616 / 0,607–0,617 | 0,806–0,819 / 0,797–0,807 | 0,002–0,002 / 0,001–0,002 | 1,444–1,448 / 1,454–1,489 |
| 127 V/50 Hz | 0,704–0,751 / 0,711–0,732 | 0,610–0,628 / 0,609–0,617 | 0,797–0,806 / 0,796–0,807 | 0,002–0,003 / 0,001–0,002 | 1,454–1,475 / 1,456–1,505 |
| 230 V/50 Hz | 0,700–0,746 / 0,711–0,731 | 0,622–0,637 / 0,620–0,622 | 0,782–0,791 / 0,792–0,794 | 0,002–0,003 / 0,001–0,002 | 1,448–1,455 / 1,451–1,493 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`). Medido e esperado concordam: o THD de 0,2–0,3 % fica abaixo do piso de 1 %, o envelope tem mínimo 0,61–0,64 e máximo 0,78–0,82 pu e a crista medida acompanha a esperada.

## 8. As três versões e a correlação esperada

A `programada` da 06 é a reconstrução da TRACe (`ProgramacaoCaptura.programada_pu()`, {doc}`../tres_versoes`): cada ciclo sem a média, escalado ao rms de `LIST:VOLTage`. É nela que a média por ciclo desaparece.

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 0,870–0,998 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,967–0,991 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,826–0,960 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 0,785–0,971 / 0,784–0,970 | 0,870–0,997 / 0,870–0,997 | 0,859–0,979 / 0,858–0,979 | 0,895–0,998 / 0,895–0,998 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,967–0,978 / 0,974–0,983 | 0,984–0,991 / 0,989–0,995 | 0,981–0,989 / 0,984–0,991 |
| modelo × medida | 0,826–0,935 / 0,831–0,940 | 0,878–0,960 / 0,882–0,964 | 0,836–0,945 / 0,838–0,948 |

Causa de a classe ficar abaixo de 0,90, quando fica: a fonte remove a média de cada ciclo da TRACe (manual, `TRACe:DATA`, p. 126); a média por ciclo do flicker (até ±0,02 pu) fica no modelo e não na programada

A 06 fica abaixo da faixa 0,95 a 1,00 histórica em 7 de 9 capturas de 07/10 (modelo × medida 0,826–0,960); a faixa de referência é de origem ausente do repositório ({ref}`P-27 <p-27>`), por isso esta página não compara contra ela. A causa é a média por ciclo, que fica no modelo e não na programada, e não a fonte: programada × medida é 0,967–0,991.

## 9. Quirks e armadilhas

- **A2, A3:** nunca consultar a fonte logo depois de `TRACe:DATA`; trava na ~280.ª gravação de TRACe por conexão (cada captura grava 12 TRACes a 60 Hz).
- **A4, A5:** `SOURce:LIST:REPeat` com `0` por passo e o prefixo `SOURce:`; `1` toca cada ciclo duas vezes.
- **A16:** `ABORt` só em `program_capture`, nunca em `arm_transient` (restauraria `FIX` e `OUTPUT OFF`).
- **K1, K3, K4, K7:** referência horizontal, pontos por aquisição, reamostragem sem anti-aliasing e extremos no registro bruto.
- **Limite do manual:** a TRACe perde a média de cada ciclo (p. 126). É o fato que explica a correlação desta classe.
- **Acoplamento:** a ordem das duas chamadas ao `rng` em `gerar()` (frequência, depois profundidade) decide todas as formas da seed ({doc}`../codigo/acoplamentos`).

## 10. Histórico por versão

- **v1.8:** `valor_para_captura` dá cobertura determinística de $f_\text{fl}$ com `set capturas N` (N > 1).
- **v1.12:** as classes 05 a 20 eram reprovadas pela validação física com "mínimo do envelope 0,01 pu" (falso negativo): o registro tinha 20 ms em 0 V antes do trigger; passou-se a validar só a janela alinhada (`medido[margem_antes : margem_antes + 6000]`).
- **v1.13:** `capturas_padrao` = 3 na 06; a 220 V o limite de bancada passa a reduzir só o distúrbio ($k$) e o gancho `parametros_com_disturbio_reduzido` traduz $k$ em `flicker_depth_bancada`.
- **v1.15:** perfis (`flicker_profundidade`); fase sorteada; a correção do rms por ciclo da TRACe passa o `LIST:VOLTage` para o rms CA do ciclo (efeito pequeno na 06: erro máximo 0,0229 → 0,0218 pu a 50 Hz); a revisão dos pendentes da correlação quantifica a perda da 06 na TRACe e conclui que não vale mudar a programação (decisão pendente, P-12).

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| A fonte reproduz o flicker de 8 a 25 Hz | {bdg-success}`VERIFICADO NA BANCADA` | 3 condições, 07/10/2026; programada × medida 0,967–0,991; validação física 3/3 |
| A perda de correlação vem da média por ciclo | {bdg-info}`OFFLINE` | 0,9999 a 1,0000 sem a média, 28 capturas |
| Perfil `norma` (2–7 %) | {bdg-warning}`NÃO VERIFICADO` | nunca capturado |
| Flicker de 25 Hz fisicamente reproduzido (degraus de um ciclo, erro até 0,05 pu) | {bdg-warning}`NÃO VERIFICADO` | só o modelo `programada_pu` |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
:::

:::{important} Pendência P-12
Comparar a 06 com a forma programada ou redefinir o flicker com média nula por ciclo; decisão do responsável pelo projeto (caixa da seção 4). Prioridade MÉDIA.
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
| `Experimento.gerar` ([experimentos_waveform/06.py:18-28](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/06.py#L18-L28)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"flicker_hz", "flicker_depth", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.parametros_com_disturbio_reduzido` ([experimentos_waveform/06.py:30-33](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/06.py#L30-L33)) | `parametros`, `fracao` ($k$) | `{"flicker_depth_bancada": k · flicker_depth}` | a linha [mestre.py:3109](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3109) de `ExperimentoWaveform._limitar_disturbio_para_bancada` |

- `gerar` decide `cobertura_ativa = not simulado and capturas_override is not None` (`simulado` é `self.osc is None`), chama `valor_para_captura(rng, 8.0, 25.0, ...)`, sorteia a profundidade com `rng.uniform(*perfis.faixa(self.config, "flicker_profundidade"))`, `self.sortear(rng, f0)` (só fase) e monta a forma.
- A classe herda de `ExperimentoWaveform`: `grava_trace` é sempre verdadeiro, `forma_para_bancada` é o padrão (limite de pico: `None`; limite de bancada: sim), `forma_esperada_para_validacao` usa a forma realmente programada.
- Atributos: `capturas_padrao` = 3 ([06.py:16](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/06.py#L16)). `pre_trigger_s` herdado (0).
- Contrato e ganchos: {doc}`../codigo/classes_contrato`; o percurso de uma captura TRACe: {doc}`../codigo/percurso-captura-trace`; a função pura da programação: {doc}`../codigo/ametek_orm` §3.

## 13. Referências

- Código: `experimentos_waveform/06.py`; `logica/ametek_orm.py` (`montar_programacao`, `program_capture`); `logica/mestre.py` (`ExperimentoWaveform`); `logica/sinais.py` (`valor_para_captura`).
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`../scpi/sequencias` §7, {doc}`../medicao/correlacao`, {doc}`../tres_versoes`, {doc}`../projeto/pendencias`.
- Histórico: `CHANGELOG/v1.8.md`, `v1.12.md`, `v1.13.md`, `v1.15.md` (seções "RMS por ciclo da TRACE" e "Pendentes da correlação do distúrbio"). Norma: IEEE Std 1159-2019, Tabela 2, item 6.0 e cláusula 4.4.6.
