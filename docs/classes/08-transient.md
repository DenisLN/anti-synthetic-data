# Classe 08: TRANSIENT

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 **só como impulso filtrado** (127 V/60 Hz e 127 V/50 Hz, 3 capturas cada, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` impulso a 90 ms a 50 Hz e o mecanismo da cópia em 100 ms {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-02` {bdg-danger}`PENDENTE P-03` {bdg-danger}`PENDENTE P-18` {bdg-danger}`PENDENTE P-19`

| Campo | Valor |
|---|---|
| Número e nome | 08 TRANSIENT (transitório impulsivo) |
| Arquivo | `experimentos_waveform/08.py`, classe `Experimento(ExperimentoWaveform)` (216 linhas, a única com lógica própria de bancada) |
| Mecanismo na bancada | **forma de onda**: TRACe/LIST com um impulso de 2 amostras na TRACe do ciclo, **dimensionado ao teto de pico** |
| `capturas_padrao` | 3 ([08.py:22](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L22)): sem `set capturas`, as 3 aplicam o impulso máximo seguro |
| Sorteio de posição | nenhum: **fora do sorteio** de posição e de fase |
| Depende do perfil? | não: capturada uma vez com `set perfil todos` |
| Condições já medidas | 127 V/60 Hz e 127 V/50 Hz (3 capturas cada); 230 V/50 Hz parada em 07/10 (376 V medidos contra o teto de 374,2 V) |

## 1. Em uma resposta

**Pergunta:** a bancada reproduz o impulso de 5 a 10 pu e 50 µs do modelo? **Resposta:** **não**. A captura física da 08 é um **impulso de baixa amplitude filtrado pela fonte** (um pico seguido de oscilação de ~7,5 a 10 kHz que morre em menos de 0,5 ms), por **três limitações independentes**: a amplitude cabe só até 0,9 × `max_peak_v` (374,2 V, 2,084 pu a 127 V), a fonte não sobe em 50 µs, e a TRACe representa o impulso com 3 a 4 pontos. O modelo `gerar()` e o dataset simulado continuam com a amplitude da especificação; só a captura física é limitada. A 08 é, por construção, a exceção da correlação (diferença máxima programada × modelo de 0,56 pu a 60 Hz e 0,82 pu a 50 Hz, correção do rms por ciclo).

Estado: o impulso filtrado foi medido; a 50 Hz o evento saiu a 100 ms em vez de 80 ms nas três capturas (A22), e a correção (impulso a 90 ms e conferência de posição) nunca foi medida ({ref}`P-03 <p-03>`); o mecanismo do deslocamento é desconhecido ({ref}`P-02 <p-02>`).

## 2. O fenômeno e a norma

Transitório impulsivo: variação unidirecional, em geral por descarga atmosférica ou chaveamento, de duração de nanossegundos a 1 ms. O item 1.1.2 da Tabela 2 da IEEE Std 1159-2019 dá **50 ns a 1 ms**, e a cláusula 4.4.1.1 o descreve como unidirecional. A duração do modelo (50 µs) está dentro da norma; a **bancada** não a reproduz (a seção 4 mostra por quê). A especificação original pede 5 a 10 pu de amplitude do pico **acima** do sinal normal, a 80 ms.

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v[k]=\sin\!\big(2\pi f_0\,t_k\big)+A\,\mathbb{1}\big[\,k\in\{k_0,\;k_0+1\}\,\big],\qquad A\sim\mathcal{U}(5;\,10)\ \text{pu},\quad k_0=\operatorname{round}(0{,}080\,f_s)=2400
$$

O impulso tem `pulse_samples = ceil(50 µs × 30 kSa/s) = 2` amostras (1,5 arredondado para cima). **Não há fase sorteada** (a senoide parte de $t=0$ com fase 0) nem início sorteado: a 08 não chama `sortear`. Com o sorteio ligado, um único ajuste de posição: se o início de 80 ms cair a menos de `DISTANCIA_MIN_FRONTEIRA_AMOSTRAS` = 30 amostras (1 ms) de uma fronteira de ciclo da rede, o impulso vai para o **meio do mesmo ciclo** (`_indices_impulso`).

| f0 | Amostras por ciclo $n$ | $k_0 \bmod n$ | Início do impulso (sorteio ligado) | Com `set sorteio off` |
|---|---|---|---|---|
| 60 Hz | 500 | 400 | 80 ms (amostra 2400); fica a 98 amostras da fronteira seguinte | 80 ms |
| 50 Hz | 600 | 0 | **90 ms** (amostra 2700, meio do 5.º ciclo, onde a senoide cruza zero) | 80 ms (amostra 2400, exatamente na fronteira) |

```{literalinclude} ../../experimentos_waveform/08.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_waveform/08.py, Experimento.gerar
```

- **Parâmetros no metadata (`gerar`):** `transient_amplitude_pu` ($A$) e `pulse_samples`; **da bancada** (`forma_para_bancada`): `amplitude_bancada_pu`, `inicio_impulso_s`, `pico_previsto_v`, `vale_previsto_v` e `caracterizacao`.
- **Cobertura:** com `set capturas N` (N > 1) a 08 abandona a faixa da especificação (5 a 10 pu, sempre cortada ao mesmo teto físico) e cobre, em `gerar()`, do pico alvo de 1,2 pu até `limite_pico_bancada_pu()`: `pico_alvo = linspace(1,2; limite; N)[capture_index]` e $A$ = pico alvo − 1 (v1.8). Sem `set capturas`, as 3 capturas padrão sorteiam $A$ e todas saem no mesmo impulso máximo seguro.
- **Seed:** `base_seed + 8 · 1 000 000 + indice_global`.

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

### As três limitações independentes

1. **Amplitude.** O teto é 0,9 × `max_peak_v` = 374,2 V (2,084 pu a 127 V; `limite_pico_bancada_pu`, [08.py:72-80](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L72-L80)). A especificação (`experimentos.txt`) pede 5 a 10 pu acima do sinal normal, até ~11 pu no total, o que passa de 1900 V a 127 V (`CHANGELOG/v1.7.md`), muito acima dos 425 Vp do hardware. A amplitude segura vem do pico e do **vale** da oscilação que segue o degrau, dimensionados com `SOBRESSINAL_DO_DEGRAU` = 0,55 e `SUBSINAL_DO_DEGRAU` = 0,70 ([08.py:59-60](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L59-L60); medidos 0,38 a 0,457 e 0,55 a 0,58 do degrau, margem de ~1,2).
2. **Velocidade.** A subida de 10 a 90 % do fundo de escala leva ~200 µs (quirk A21); o impulso de 50 µs acaba antes da subida. O que se mede é a resposta do amplificador a um degrau, não o impulso.
3. **Representação.** Cada TRACe tem 1024 pontos por ciclo (19,5 µs a 50 Hz, 16,3 µs a 60 Hz); o impulso de 2 amostras ocupa 3 a 4 pontos.

### Dimensionamento da amplitude (`forma_para_bancada`)

A 08 sobrescreve `forma_para_bancada` ([08.py:117-169](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L117-L169)) porque o padrão escalaria a forma **inteira**: na primeira versão, o limite de pico baixava a base de 127 V para 43 Vrms e o osciloscópio, com escala para o impulso, via a base com ±1 código de ruído. Agora a base fica em 1 pu e só o impulso é limitado. Com a partida $s_\text{min}$, $s_\text{max}$ (o menor e o maior valor da senoide nas duas amostras do impulso) e o teto $L$ = `limite_pico_bancada_pu()`:

$$
A_\text{pico}=\frac{L-s_\text{max}}{1+0{,}55},\qquad
A_\text{vale}=\frac{L+s_\text{min}}{0{,}70},\qquad
A=\min(A_\text{pico},A_\text{vale})
$$

Se $A\le 0$, `ParameterOutOfBoundsError` (nenhum impulso cabe). Com `set capturas N` (N > 1) a amplitude varia de $\min(0{,}25;A)$ até $A$ em N passos (caracterização); senão é $A$. O extremo previsto é `excursao_fisica_prevista_v` = o maior entre $|{\rm pico}|$ e $|{\rm vale}|$ previstos, e **substitui** a tabela de fatores de extremo (a 08 é a única classe fora dela).

Amplitudes seguras, calculadas offline em 2026-10-16 com a classe real (`forma_para_bancada` com configuração sintética; $L$ = 0,9 × 415,8 V):

| Condição | $L$ (pu) | Impulso em | Amplitude segura $A$ (pu) | Pico / vale previstos (V) | Quem limita |
|---|---|---|---|---|---|
| 127 V/60 Hz | 2,084 | 80 ms | **1,618** | 280,3 / −374,2 | o vale |
| 127 V/50 Hz (sorteio ligado) | 2,084 | 90 ms | **1,344** | 374,2 / −179,6 | o pico |
| 127 V/50 Hz (`set sorteio off`) | 2,084 | 80 ms | 1,337 | 374,2 / −179,6 | o pico |
| 220 V/50 Hz | 1,203 | 90 ms | 0,776 | 374,2 / −311,1 | o pico |
| 220 V/60 Hz | 1,203 | 80 ms | 0,360 | 311,1 / −374,2 | o vale |
| 230 V/50 Hz | 1,150 | 90 ms | 0,742 | 374,2 / −325,3 | o pico |
| 230 V/60 Hz | 1,150 | 80 ms | 0,285 | 325,3 / −374,2 | o vale |

A 60 Hz o impulso (80 ms) parte de $-0{,}95$ pu e quem limita é o vale; a 50 Hz ele parte do cruzamento por zero, a maior inclinação da senoide, e quem limita é o pico. Por isso o sobressinal subiu de 0,45 para 0,55 na v1.14.

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

A 08 acrescenta ao final: `KeysightDSOX4034A.medir_extremos` (VMAX e VMIN no registro bruto, quirk K7: o array a 30 kSa/s subestimava o pico, 0,08 contra 0,45 do degrau) e `exige_medida_de_pico = True` ([08.py:69](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L69)): sem a medida a captura não prova que ficou no teto e a classe para. Teto dos extremos medidos: `fracao_teto_pico_medido` = 0,9 ([08.py:70](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L70)).

**Janela e margem.** `pre_trigger_s` herdado (0); a 08 não tem pré-trigger próprio, e o impulso está na amostra 2400 (ou 2700) da janela de 6000, mais 600 de margem no registro físico ({doc}`../medicao`).

### A posição: 80 ms, 90 ms e a cópia em 100 ms

A 50 Hz os 80 ms são o início do 5.º ciclo (fronteira) e a fonte tocou o impulso a **100 ms** (+20 ms) nas três capturas de 07/10/2026 (A22); a 60 Hz saiu no lugar (amostras 2404 e 2401). A validação antiga não via, porque excluía os dois ciclos do impulso. O mecanismo do deslocamento é {bdg-warning}`NÃO VERIFICADO`: a montagem da TRACe (`montar_programacao`, `_resample_cycle`) põe o impulso nos pontos 0 a 3 da TRACe e a forma reconstruída o devolve nas amostras 2400 a 2401; o deslocamento acontece na **reprodução pela fonte**, e a hipótese "um ponto da TRACe" é recusada pelos dados (precisa de pelo menos 3 pontos). `logica/modelo_lista_fonte.py` (`HIPOTESES_CANDIDATAS`, [modelo_lista_fonte.py:32-50](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/modelo_lista_fonte.py#L32-L50)) reúne os mecanismos candidatos (passo da lista atrasado, cópia do evento em instante fixo, início do passo com a forma anterior, deslocamento no tempo, mais o controle `ideal`); nenhum foi confrontado com dado real. `scripts/diag_ciclos_trace.py` e `scripts/diag_marcadores_trace.py` são as ferramentas de diagnóstico ({doc}`../diagnostico`).

Com o sorteio ligado o impulso vai a 90 ms a 50 Hz (meio do ciclo, cruzamento por zero como o de 80 ms, mesmo nível de partida), nunca a menos de 30 amostras de uma fronteira: o deslocamento medido envolve até 4 pontos da TRACe (até 2,3 amostras), as capturas diferem ±2 amostras entre si e o toque pós-impulso dura menos de 0,5 ms (15 amostras). A 08 fica fora do sorteio de posição e de fase porque o sobressinal foi calibrado para um ponto de partida.

:::{important} Pendência P-02
Mecanismo da cópia ou deslocamento do evento em 100,0 ms (quirks A22 e A25): a 08 a 50 Hz saiu em 100 ms em 3 de 3; a 09 tem impulso de 0,12–0,27 pu em 100,0–100,2 ms em 9 de 9. Fecha com: bancada (Blocos 4 e 6 do roteiro: `diag_marcadores_trace.py`, retrieve, recaptura). Prioridade ALTA.
:::

:::{important} Pendência P-03
Recaptura a 127 V/50 Hz com o impulso em 90 ms: posição (|desvio| ≤ 10 amostras), pico ≤ 374,2 V e sobressinal ≤ 0,55. Acima disso é achado de segurança. Fecha com: bancada. Prioridade ALTA.
:::

:::{warning} Decisão em aberto P-04
`AmetekMX30.program_capture` só **avisa** quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga", [ametek_orm.py:1522-1527](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1522-L1527)); quem recusa é a pré-validação do `mestre.py` (`ExperimentoBase._indices_viaveis`, antes de qualquer SCPI, e `_conferir_extremos_fisicos`, depois da captura já gravada). Pergunta ao responsável pelo projeto: o ORM também deve recusar? Opções: manter como está, ou recusar no ORM (um limite de segurança mais restritivo). Este site não decide ({ref}`P-04 <p-04>`, prioridade MÉDIA).
:::

:::{warning} Decisão em aberto P-23
A fonte travou na ~280.ª gravação de TRACe de uma mesma conexão (quirk A3; causa {bdg-warning}`NÃO VERIFICADO`), e cada captura desta classe grava 12 TRACes a 60 Hz (10 a 50 Hz). `README.md` e `AGENTS.md` ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `set perfil todos`), enquanto o roteiro de bancada usa listas de classes (menos de 250 por conexão). Pergunta: qual texto os documentos devem adotar? Opção recomendada pelo roteiro: listas (`run 01-07`, depois `run 09-20`). Decisão do responsável pelo projeto ({ref}`P-23 <p-23>`, prioridade MÉDIA).
:::

## 5. Parâmetros por perfil

Esta classe não lê nenhum componente de `perfis.py` (`COMPONENTES_POR_CLASSE` não a lista): `gerar()` é igual nos três perfis.

A 08 é **independente do perfil**: amplitude, posição e forma não vêm de `perfis.py`. É uma das oito classes que `perfis.classes_independentes_do_perfil` lista com o sorteio ligado.

## 6. Limites físicos e fator de extremo

A 08 **não usa** a tabela `calibracao_extremos.json` (`observacao_08` do arquivo): o extremo previsto é `excursao_fisica_prevista_v` e o teto é 0,9 × `max_peak_v`, não 1,0. O pico programado de `forma_para_bancada` fica sempre **no teto** por construção.

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | sem entrada | 3 | 179,6 | 374,2 | 374,2 | 100 % | 3/3 rodam |
| 127 V/50 Hz | sem entrada | 3 | 241,4 | 374,2 | 374,2 | 100 % | 3/3 rodam |
| 230 V/50 Hz | sem entrada | 3 | 325,3 | 374,2 | 374,2 | 100 % | 3/3 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 3 | 311,1 | 374,2 | 374,2 | 100 % | 3/3 rodam |

*Fonte:* `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 3 capturas padrão, seed 20260827). A coluna "Teto" é 374,2 V, e "Extremo previsto" = teto por construção. A 08 roda em todas as condições (inclusive 220 V/60 Hz e 230 V/50 Hz), com a **amplitude** reduzida (tabela da seção 4); o que muda com a tensão é a amplitude segura.

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. Na 08, `ciclos_excluidos_da_validacao` ([08.py:174-179](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L174-L179)) remove o ciclo do impulso e o seguinte (a oscilação) dos dois lados antes de comparar envelope, THD e crista, e `fator_extremo_efetivo_para_validacao` devolve 1,0 (o impulso fica fora da crista). A **posição** é conferida à parte por `conferir_posicao_do_evento` ([08.py:181-216](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L181-L216)): o maior desvio da senoide, na janela alinhada ao trigger, tem de cair a até 10 amostras do início previsto (`TOLERANCIA_POSICAO_AMOSTRAS`, [08.py:39](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L39)), e o desvio tem de ser pelo menos 0,25 da amplitude de bancada (`FRACAO_MIN_DESVIO_VISIVEL`, [08.py:42](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L42)); senão a captura é marcada inválida ("impulso não encontrado" ou "posição do impulso").

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,710–0,711 / 0,707 | 0,699–0,700 / 0,707 | 0,721–0,722 / 0,707 | 0,003 / 0,000 | 1,460–1,471 / 1,414 |
| 127 V/50 Hz | 0,710 / 0,707 | 0,697–0,699 / 0,707 | 0,722–0,723 / 0,707 | 0,003–0,004 / 0,000 | 1,470–1,471 / 1,414 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`). O THD medido (0,3–0,4 %) está abaixo do piso. A conferência de posição (v1.15) aplicada às seis capturas de 07/10 **reprovaria** as de 50 Hz (+600, +600 e +597 amostras) e aprovaria as de 60 Hz (0, 0 e −1).

**Medidas de 07/10 do dimensionamento** (`pico_previsto_v` / `vale_previsto_v` do metadata contra `pico_medido_v` / `vale_medido_v` do osciloscópio, teto 374,2 V):

| Condição | Amplitude de bancada | Previsto (pico / vale, V) | Medido (pico / vale, V) |
|---|---|---|---|
| 127 V/60 Hz (`sessao_2026-10-07_14-59-54_run02`) | 1,618 pu | 251 / −374 | 230 / −339 (as duas primeiras), 230 / −334 (a terceira) |
| 127 V/50 Hz (`sessao_2026-10-07_127V_50Hz`) | 1,337 pu | 374 / −180 | 350 / −193 (as três) |

O medido ficou 6 a 11 % abaixo do previsto (previsto daquele dia, com o sobressinal em 0,45; hoje o pico previsto a 127 V/60 Hz é 280,3 V): o dimensionamento é conservador e o teto de 374,2 V não foi tocado nessas seis capturas. (A 230 V/50 Hz, antes da v1.14, a saída fez 376 V contra o teto de 374,2 V com o sobressinal em 0,45; por isso 0,55.)

## 8. As três versões e a correlação esperada

A `programada` da 08 é a TRACe reconstruída **da forma de bancada** (impulso de $A$ pu em vez de 5 a 10 pu) e inclui o filtro da própria reconstrução; a `medida` inclui o toque. Por isso modelo × programada já é baixo (0,56 a 0,82 pu de diferença máxima) mesmo sem a fonte: a 08 é a exceção por construção.

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 0,986–0,993 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,028–0,816 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,004–0,831 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 0,986 / 0,986 | 0,986 / 0,986 | 0,993 / 0,993 | 0,993 / 0,993 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,028–0,058 / 0,024–0,053 | 0,807–0,816 / 0,813–0,824 | — |
| modelo × medida | 0,004–0,011 / 0,001–0,006 | 0,824–0,831 / 0,831–0,839 | — |

Causa de a classe ficar abaixo de 0,90, quando fica: a 127 V/50 Hz o impulso saiu a 100 ms em vez de 80 ms (A22), pico fora da janela esperada; a 127 V/60 Hz o impulso de 50 µs sai filtrado pela fonte (A21) e a métrica é sensível ao alinhamento de uma amostra (P-02, P-03)

Leitura. **A 127 V/60 Hz** o impulso saiu no lugar (modelo × medida 0,824–0,831), e a métrica é sensível ao alinhamento de **uma amostra**; **a 127 V/50 Hz** o impulso saiu a 100 ms e o pico cai fora da janela esperada (modelo × medida 0,004–0,011): é o defeito A22, não a fonte filtrando. A correlação do distúrbio é invariante à escala do distúrbio, então ela não mede quanto o impulso chegou; para isso vale a razão de pico e a tabela de amplitudes da seção 4. O modelo × programada com o código da v1.15 é 0,986–0,993.

## 9. Quirks e armadilhas

- **A21:** o impulso de 50 µs não é reproduzido (limite de banda: 200 µs de subida); sai um impulso filtrado.
- **A22:** a 50 Hz o impulso programado em 80 ms (fronteira de ciclo) saiu a 100 ms; a 60 Hz saiu no lugar. Mecanismo {bdg-warning}`NÃO VERIFICADO`.
- **A20:** oscilação de ~7,5–10 kHz após o degrau: sobressinal 0,38 (60 Hz) a 0,457 (50 Hz) do degrau; subsinal 0,55–0,58.
- **K7:** o extremo vem do osciloscópio no registro bruto; o array a 30 kSa/s subestima picos estreitos.
- **A2, A3:** sem consulta após `TRACe:DATA`; trava na ~280.ª gravação.
- **Acoplamento (`classes_contrato` §4):** `_indices_impulso`, as constantes, `forma_para_bancada`, `ciclos_excluidos_da_validacao`, `conferir_posicao_do_evento` e `gerar()` chamam a mesma função de índices; mudar uma constante muda todos. A calibração do sobressinal depende do ponto de partida. A 08 é a única classe fora da tabela de fatores ([mestre.py:2018-2034](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2018-L2034), [mestre.py:1896-1920](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1896-L1920)).

## 10. Histórico por versão

- **v1.7:** a 08 pedia ~1900 V a 127 V (5 a 10 pu somados ao sinal). O gancho `limite_pico_bancada_pu` passou a escalar o pico só na captura física; a primeira versão escalava a **forma inteira**.
- **v1.8:** sortear 5 a 10 pu sempre cortava ao mesmo teto físico (~2,1 pu): captura redundante; a 08 passa a cobrir de 1,2 pu até o limite com `set capturas N` (caracterização).
- **v1.11:** o `run all` na bancada de 30/09/2026 mostrou a 08 com 415,3 V medidos (teto 415,8 V), sem folga.
- **v1.12 (T8):** o escalonamento da forma inteira derrubava a base de 127 V para 43 Vrms (T8-1); passou a limitar só o impulso (`forma_para_bancada`); caracterizada com `set capturas 6` (degraus de 45 a 339 V, VMAX e VMIN na taxa cheia): sobressinal 0,38 e subsinal 0,58 do degrau; confirmação VMAX 230 V / VMIN −334 V (previstos 230 / −339). `medir_extremos` por captura e `PicoFisicoExcedidoError` **depois** de gravar.
- **v1.14:** a 50 Hz o impulso parte do cruzamento por zero e quem limita é o pico; o sobressinal chegou a 0,457 e mediu 376 V contra o teto de 374,2 V nas três sessões a 50 Hz: `SOBRESSINAL_DO_DEGRAU` de 0,45 para 0,55.
- **v1.15:** impulso a 90 ms a 50 Hz (`DISTANCIA_MIN_FRONTEIRA_AMOSTRAS` = 30) e a conferência de posição na validação física (`conferir_posicao_do_evento`); diagnóstico da cópia em 100 ms (`diag_ciclos_trace.py`, `diag_marcadores_trace.py`, `modelo_lista_fonte.py`).

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| Impulso filtrado, dentro do teto | {bdg-success}`VERIFICADO NA BANCADA` | 127 V/60 Hz e 127 V/50 Hz, 07/10/2026; previsto 6–11 % acima do medido |
| `gerar()`, dimensionamento e conferência de posição | {bdg-info}`OFFLINE` | `Classe08FronteiraTests` (9 testes); tabela da seção 4 |
| Impulso a 90 ms a 50 Hz | {bdg-warning}`NÃO VERIFICADO` | Bloco 6 do roteiro; nenhuma sessão com o código da v1.15 |
| Mecanismo da cópia em 100 ms | {bdg-warning}`NÃO VERIFICADO` | `diag_ciclos_trace.py` rodado offline em 07/10 (08 a 50 Hz: resíduo máximo em torno de 100 ms 1,887 / 1,887 / 1,321 pu; a 60 Hz 0,034 / 0,034 / 0,040 pu); não decide o mecanismo |
| 230 V/50 Hz | {bdg-warning}`NÃO VERIFICADO` | parada em 07/10 com o sobressinal antigo; hoje a amplitude segura é 0,742 pu |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
:::

:::{important} Pendência P-18
Passo final `SINE` no `LIST`: existe só no branch `feat/passo-final-sin`, **fora da `main`** ({doc}`../projeto/passo-final-sin`). Fecha com: bancada e decisão do responsável pelo projeto. Prioridade MÉDIA.
:::

:::{important} Pendência P-19
`TRACe:DATA?` (`set diagnostico retrieve`) nunca foi executado na fonte real; a primeira captura da 08 é o lugar indicado para ligá-lo, com o painel à vista. Fecha com: bancada. Prioridade MÉDIA.
:::

## 12. Como o código da classe funciona

| Símbolo | Recebe | Devolve | Quem chama |
|---|---|---|---|
| constantes (`INICIO_IMPULSO_S` [08.py:24](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L24), `DURACAO_IMPULSO_S` [08.py:25](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L25), `DISTANCIA_MIN_FRONTEIRA_AMOSTRAS` [08.py:35](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L35), `TOLERANCIA_POSICAO_AMOSTRAS` [08.py:39](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L39), `FRACAO_MIN_DESVIO_VISIVEL` [08.py:42](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L42), `SOBRESSINAL_DO_DEGRAU` [08.py:59](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L59), `SUBSINAL_DO_DEGRAU` [08.py:60](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L60), `AMPLITUDE_MIN_CARACTERIZACAO_PU` [08.py:62](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L62), `exige_medida_de_pico` [08.py:69](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L69), `fracao_teto_pico_medido` [08.py:70](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L70)) | nada | valores numéricos | os métodos abaixo e `ExperimentoBase` |
| `Experimento.limite_pico_bancada_pu` ([experimentos_waveform/08.py:72-80](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L72-L80)) | nada | $0{,}9\cdot\text{max\_peak\_v}/(\sqrt2 V_\text{base})$ | `_limitar_pico_da_forma` (a linha [mestre.py:3028](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3028)), `gerar` (cobertura) e `forma_para_bancada` |
| `Experimento._indices_impulso` ([experimentos_waveform/08.py:82-99](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L82-L99)) | `fs_hz`, `f0_hz` (opcional) | `numpy.arange(start, start + pulse_samples)` | `gerar`, `forma_para_bancada`, `ciclos_excluidos_da_validacao`, `conferir_posicao_do_evento`, `scripts/gerar_tres_versoes.py` |
| `Experimento.gerar` ([experimentos_waveform/08.py:101-115](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L101-L115)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"transient_amplitude_pu", "pulse_samples"})` | os chamadores da seção 3 |
| `Experimento.forma_para_bancada` ([experimentos_waveform/08.py:117-169](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L117-L169)) | `voltage_pu`, `parametros` (alterado no lugar), `capture_index` | a forma com o impulso limitado | as linhas [mestre.py:3117](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3117) e [mestre.py:3132](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3132) (em `forma_e_parametros_para_bancada` e em `ExperimentoWaveform._capturar_real`) |
| `Experimento.excursao_fisica_prevista_v` ([experimentos_waveform/08.py:171-172](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L171-L172)) | nada | `_excursao_prevista_v` da última `forma_para_bancada` (ou `None`) | a pré-validação ([mestre.py:2021](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2021)), a escala vertical ([mestre.py:3165](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3165)) e a linha [mestre.py:1906](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1906) de `fator_extremo_efetivo_para_validacao` |
| `Experimento.ciclos_excluidos_da_validacao` ([experimentos_waveform/08.py:174-179](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L174-L179)) | `capture_index` | os dois índices de ciclo (do impulso e o seguinte) | a linha [mestre.py:1865](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1865) de `ExperimentoBase._validar_fisicamente` |
| `Experimento.conferir_posicao_do_evento` ([experimentos_waveform/08.py:181-216](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/08.py#L181-L216)) | `capture_index`, `janela_medida_pu` | `{"ok", "motivos", "posicao"}` | a linha [mestre.py:1885](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1885) de `ExperimentoBase._validar_fisicamente` |

- `gerar` usa o `rng` uma vez (`rng.uniform(5.0, 10.0)`), exceto na cobertura. `forma_para_bancada` **muta** `parametros` (acrescenta as chaves da bancada) e guarda `_excursao_prevista_v` e `_amplitude_bancada_pu` na instância; `conferir_posicao_do_evento` usa o segundo para o critério de "impulso não encontrado".
- `exige_medida_de_pico` e `fracao_teto_pico_medido` são atributos de classe de `ExperimentoBase`, nas linhas [mestre.py:1940](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1940) e [mestre.py:1943](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1943), sobrescritos aqui; são lidos nas linhas [mestre.py:1964](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1964) (`_conferir_extremos_fisicos`), [mestre.py:2077](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2077) (`avaliar_captura_na_bancada`) e [mestre.py:3065](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3065) (`_limitar_disturbio_para_bancada`).
- Contrato e ganchos: {doc}`../codigo/classes_contrato` §3 e §5 (a 08 como o único arquivo com lógica própria de bancada).

## 13. Referências

- Código: `experimentos_waveform/08.py`; `logica/mestre.py` (`ExperimentoWaveform.forma_para_bancada`, `_validar_fisicamente`); `logica/modelo_lista_fonte.py`; `scripts/diag_ciclos_trace.py`, `scripts/diag_marcadores_trace.py`.
- Site: {doc}`../classes`, {doc}`../limites_e_calibracao`, {doc}`../diagnostico`, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`, {doc}`../quirks`.
- Análise arquivada do deslocamento a 50 Hz (registro histórico, não reescrito): `arquivo/analises:docs/analise-2026-10-12/pendente/classe08_fronteira_REVISAR.md` ({doc}`../projeto/analises-arquivadas`).
- Histórico: `CHANGELOG/v1.7.md`, `v1.8.md`, `v1.11.md`, `v1.12.md`, `v1.14.md`, `v1.15.md` (seções "Classe 08: impulso fora da fronteira de ciclo" e "Diagnóstico da cópia do evento em 100 ms"). Norma: IEEE Std 1159-2019, Tabela 2, item 1.1.2 e cláusula 4.4.1.1.
