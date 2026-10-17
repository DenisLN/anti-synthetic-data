# Classe 09: OSCILLATORY_TRANSIENT

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 **com defeito de dado conhecido** (A25; 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 3 capturas cada, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` mecanismo da cópia em 100 ms {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-02` {bdg-danger}`PENDENTE P-18` {bdg-danger}`PENDENTE P-19`

| Campo | Valor |
|---|---|
| Número e nome | 09 OSCILLATORY_TRANSIENT (transitório oscilatório) |
| Arquivo | `experimentos_waveform/09.py`, classe `Experimento(ExperimentoWaveform)` |
| Mecanismo na bancada | **forma de onda**: TRACe/LIST ({scpi}`TRACe:DATA`, {scpi}`SOURce:LIST:VOLTage`, um passo por ciclo) |
| `capturas_padrao` | 3 ([09.py:18](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/09.py#L18)) |
| Sorteio de posição | I F (início e fase; a duração já era sorteada pela classe) |
| Depende do perfil? | não: capturada uma vez com `set perfil todos` |
| Condições já medidas | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 3 capturas cada |

## 1. Em uma resposta

**Pergunta:** a fonte reproduz uma oscilação amortecida de 300 a 2400 Hz sobre a senoide? **Resposta:** **sim, a oscilação chega à saída**, mas a medida traz um **impulso extra de 0,12 a 0,27 pu em 100,0 a 100,2 ms que a forma programada não tem**, em 9 de 9 capturas de 07/10: um defeito de dado (gravidade alta) cujo mecanismo é desconhecido. Enquanto não se conhece, a captura da 09 só entra no dataset sem ressalva se não tiver ciclo trocado e o resíduo perto de 100 ms ficar abaixo de ~0,05 pu.

## 2. O fenômeno e a norma

Transitório oscilatório: variação súbita, bidirecional, de tensão em regime permanente, com frequência de oscilação e decaimento exponencial, em geral por chaveamento de bancos de capacitores. O item 1.2.1 da Tabela 2 da IEEE Std 1159-2019 dá frequência **abaixo de 5 kHz**, duração de **0,3 a 50 ms** e amplitude de **0 a 4 pu**. O modelo (300 a 2400 Hz, 10 a 40 ms, 0,3 pu) **está dentro** da faixa.

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v(t)=\sin\!\big(2\pi f_0\,(t+\tau)\big)+0{,}3\,\sin\!\big(2\pi f_\text{osc}\,(t-t_0)\big)\,e^{-(t-t_0)/\tau_d}\;\mathbb{1}\big[t_0\le t<t_0+d\big],\qquad \tau_d=5\ \text{ms}
$$

$f_\text{osc}\sim\mathcal{U}(300;\,2400)$ Hz e $d\sim\mathcal{U}(10;\,40)$ ms são sorteados com o `rng` da classe; $t_0$ e a fase $\varphi$ vêm do sorteio de posição ({ref}`fórmulas <sorteio-de-posicao>`; $t_0\in[T_\text{ciclo},\,T-d-T_\text{ciclo}]$, a duração fixa em $d$; sem sorteio, $t_0=80$ ms). A oscilação parte de zero em $t_0$ (fase própria, sem relação com $\varphi$) e a amplitude de 0,3 pu e o $\tau_d$ de 5 ms são os padrões de `oscilacao_amortecida` ([sinais.py:131-146](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L131-L146)). Como o decaimento é exponencial, com $d$ = 10 ms o evento termina com 0,3·$e^{-2}$ = 0,04 pu de amplitude (um degrau), e com $d$ = 40 ms termina em ~0,0001 pu.

```{literalinclude} ../../experimentos_waveform/09.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_waveform/09.py, Experimento.gerar
```

- **Ordem do `rng`:** primeiro $f_\text{osc}$ (`valor_para_captura`, [sinais.py:24-49](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L24-L49), com cobertura por `linspace` quando o operador digita `set capturas N`, N > 1: v1.8), depois $d$ (`rng.uniform(0.010, 0.040)`); o sorteio de posição vem de um sub-fluxo.
- **Parâmetros no metadata:** `oscillation_hz`, `duration_s` (e `duracao_s`, igual, vinda do sorteio), `inicio_disturbio_s`, `fase_graus`.
- **Seed:** `base_seed + 9 · 1 000 000 + indice_global`.
- **Capturas:** `capturas_padrao` = 3 ([09.py:18](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/09.py#L18)). Três capturas não bastam para discriminar a cópia em 100 ms (seção 4): só ~18 % delas têm o evento cobrindo 100 ms.

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** a oscilação de 2400 Hz sobrevive à TRACe por ciclo? **Resposta:** sim: 2400 Hz tem 12,5 amostras por período a 30 kSa/s e 40 períodos por ciclo de 60 Hz; a amplitude programada sai ~2,4 % menor. Com sag ou swell sorteado o erro máximo da programada sobe por outro motivo (a borda do degrau cai no meio de um ciclo), mas na 09 sozinha o modelo × programada é 0,996–1,000.

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

O gancho `parametros_com_disturbio_reduzido` ([09.py:34-38](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/09.py#L34-L38)) devolve `oscillation_amplitude_pu_bancada` $=k\cdot 0{,}3$ (a amplitude padrão lida por `inspect.signature` de `oscilacao_amortecida`).

**Janela e margem.** `pre_trigger_s` herdado (0); o evento começa em $t_0$ dentro da janela; registro de 20 ms antes e 50 ms depois ({doc}`../medicao`).

### O impulso em 100 ms (quirk A25)

A medida tem um impulso de **0,12 a 0,27 pu em 100,0 a 100,2 ms** que a forma programada não tem, em **9 de 9** capturas de 07/10 (dado defeituoso, gravidade alta, não só da métrica). A 50 Hz o início da oscilação (80 ms) some e reaparece em 100 ms; a 60 Hz aparece em 80 ms (amostra 400 de 500, meio do ciclo) e uma cópia menor (0,04–0,18 pu) em 100 ms, que a 60 Hz é o início do 7.º ciclo, não um ponto 0. Junto com a A22 da 08, o evento aparece repetido ou deslocado num **instante fixo** (100 ms) nas duas frequências.

Ferramentas e o que se sabe:

- A montagem da TRACe está descartada como causa (`test_montagem_da_trace_nao_desloca_o_impulso_a_50_nem_a_60hz`); a hipótese "um ponto da TRACe" foi refutada. Os mecanismos candidatos (passo da lista tocando a forma do anterior a partir de certo instante, cópia em instante fixo, troca de forma atrasada na fronteira do passo, deslocamento no tempo) **não foram medidos**: `modelo_lista_fonte.py` (`HIPOTESES_CANDIDATAS`, [modelo_lista_fonte.py:32-50](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/modelo_lista_fonte.py#L32-L50)) os reúne e `scripts/diag_ciclos_trace.py` (offline) e `scripts/diag_marcadores_trace.py` (bancada) estão prontos.
- `diag_ciclos_trace.py` e `modelo_lista_fonte.py` aceitam a 09 **sorteada** (teste sintético `PendentesCorrelacaoDisturbioTests`, que acusa uma cópia de ganho 0,5 em 100 ms como resíduo maior que 0,1 pu e põe a hipótese `copia_no_instante` em primeiro).
- **Offline em 2026-10-16**, `diag_ciclos_trace.py` com `--saida` fora do repositório, nas duas sessões reais de 07/10 (a 127 V/50 Hz e a 127 V/60 Hz): carrega o formato 1 sem erro, nenhuma captura com "ciclos trocados" pelo critério do script e resíduo máximo em torno de 100 ms de 0,281 / 0,148 / 0,181 pu (09 a 50 Hz) e 0,151 / 0,114 / 0,237 pu (09 a 60 Hz). Isso **não** decide o mecanismo (precisa dos Blocos 4 e 6 do roteiro de bancada).
- Com o sorteio ligado, 100 ms cai **dentro** do evento rotulado em 18,1 % (50 Hz) e 17,1 % (60 Hz) de 2000 sementes (início de 16,7 a 172 ms, duração de 10 a 40 ms); em ~41 % o evento termina antes e em ~42 % começa depois. Por isso a 09 sorteada é o primeiro dado que discrimina: se o impulso aparecer em 100 ms independentemente do início, o mecanismo é de instante fixo; se acompanhar o evento (+20 ms ou +1 ciclo), é de troca de passo.

**Recomendação para a campanha** (juízo, não medida): rodar a 09 logo depois da 08, com 6 a 9 capturas (`set capturas`) se houver tempo, e na mesma sessão `scripts/diag_ciclos_trace.py <sessão> --classes 08,09`. Para a captura entrar no dataset sem ressalva: nenhum ciclo trocado e resíduo máximo perto de 100 ms abaixo de ~0,05 pu (o piso de ruído da 09 é 0,008–0,017 pu rms). Acima disso, manter a captura, marcá-la como suspeita e não usá-la para treino até o mecanismo ser conhecido: a cópia fora da janela rotulada é um rótulo errado. Não apagar nem refazer sozinho; é defeito de dado, não de infraestrutura.

:::{important} Pendência P-02
Mecanismo da cópia ou deslocamento do evento em 100,0 ms (quirks A22 e A25). Fecha com: bancada (Blocos 4 e 6 do roteiro). Prioridade ALTA.
:::

:::{warning} Decisão em aberto P-04
`AmetekMX30.program_capture` só **avisa** quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga", [ametek_orm.py:1522-1527](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1522-L1527)); quem recusa é a pré-validação do `mestre.py` (`ExperimentoBase._indices_viaveis`, antes de qualquer SCPI, e `_conferir_extremos_fisicos`, depois da captura já gravada). Pergunta ao responsável pelo projeto: o ORM também deve recusar? Opções: manter como está, ou recusar no ORM (um limite de segurança mais restritivo). Este site não decide ({ref}`P-04 <p-04>`, prioridade MÉDIA).
:::

:::{warning} Decisão em aberto P-23
A fonte travou na ~280.ª gravação de TRACe de uma mesma conexão (quirk A3; causa {bdg-warning}`NÃO VERIFICADO`), e cada captura desta classe grava 12 TRACes a 60 Hz (10 a 50 Hz). `README.md` e `AGENTS.md` ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `set perfil todos`), enquanto o roteiro de bancada usa listas de classes (menos de 250 por conexão). Pergunta: qual texto os documentos devem adotar? Opção recomendada pelo roteiro: listas (`run 01-07`, depois `run 09-20`). Decisão do responsável pelo projeto ({ref}`P-23 <p-23>`, prioridade MÉDIA).
:::

## 5. Parâmetros por perfil

Esta classe não lê nenhum componente de `perfis.py` (`COMPONENTES_POR_CLASSE` não a lista): `gerar()` é igual nos três perfis.

A 09 é **independente do perfil**: a frequência, a duração, a amplitude e o $\tau_d$ não vêm de `perfis.py`. É uma das oito classes que `perfis.classes_independentes_do_perfil` lista com o sorteio ligado.

## 6. Limites físicos e fator de extremo

O pico programado é a senoide mais a oscilação (até ~1,3 pu quando a oscilação soma à crista): de 184 a 212 V a 127 V nas capturas do relatório offline (seed 20260827).

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,036 | 3 | 192,9–210,8 | 219,8–240,2 | 415,8 | 100 % | 3/3 rodam |
| 127 V/50 Hz | 1,051 | 3 | 184,1–212,0 | 212,9–245,1 | 415,8 | 100 % | 3/3 rodam |
| 230 V/50 Hz | 1,017 | 3 | 333,4–359,7 | 385,5–415,8 | 415,8 | 59–100 % | 3/3 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 3 | 317,5–365,2 | 415,8–592,5 | 415,8 | 26–100 % | 2/3 rodam, 1 pulada(s) |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 3 capturas padrão, seed 20260827, sorteio ligado). A 230 V/50 Hz uma das três capturas roda com a amplitude da oscilação reduzida a 59 %; a 220 V/60 Hz (sem tabela) duas rodam reduzidas a 26 % e 29 % e uma é pulada. Fatores medidos: 1,036 (127 V/60 Hz), 1,051 (127 V/50 Hz) e 1,017 (230 V/50 Hz).

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. A oscilação sorteada é pequena (0,3 pu), então envelope e THD passam folgados; a validação **não pega** a cópia em 100 ms (não é um erro de envelope, THD ou crista).

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,711–0,713 / 0,707 | 0,700–0,705 / 0,697–0,707 | 0,722–0,728 / 0,709–0,710 | 0,009–0,010 / 0,009 | 1,437–1,442 / 1,414 |
| 127 V/50 Hz | 0,718–0,718 / 0,707 | 0,710 / 0,707 | 0,724–0,726 / 0,715 | 0,005–0,010 / 0,005–0,011 | 1,455–1,459 / 1,414 |
| 230 V/50 Hz | 0,709–0,711 / 0,707 | 0,702–0,703 / 0,707 | 0,715–0,718 / 0,715 | 0,005–0,011 / 0,005–0,011 | 1,434–1,447 / 1,414 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`). Todas as 9 capturas passaram na validação física, inclusive as com o impulso extra da A25.

## 8. As três versões e a correlação esperada

A `programada` da 09 é a reconstrução da TRACe (sem a média de cada ciclo). Não tem o impulso em 100 ms, que é física da fonte; a diferença programada × medida é, aqui, o defeito A25.

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 0,996–1,000 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,750–0,927 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,749–0,925 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 0,996–1,000 / 0,996–1,000 | 0,998–1,000 / 0,998–1,000 | 0,995–1,000 / 0,995–1,000 | 0,996–1,000 / 0,996–1,000 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,750–0,798 / 0,800–0,855 | 0,885–0,911 / 0,932–0,940 | 0,850–0,927 / 0,857–0,937 |
| modelo × medida | 0,749–0,797 / 0,799–0,854 | 0,883–0,910 / 0,932–0,938 | 0,850–0,925 / 0,857–0,934 |

Causa de a classe ficar abaixo de 0,90, quando fica: a 127 V/50 Hz a medida tem um impulso de 0,12–0,27 pu em 100,0–100,2 ms que a programada não tem (A25, P-02)

A queda abaixo de 0,90 a **127 V/50 Hz** (0,75–0,80 nominal; 0,80–0,86 ajustada) vem da cópia em 100 ms (A25, P-02): a medida tem o impulso extra que a programada não tem. A correlação com a fundamental ajustada **sobe** na 09 (distúrbio pequeno): 0,749–0,797 para 0,799–0,854 a 127 V/50 Hz. A 60 Hz o par fica em 0,88–0,91.

## 9. Quirks e armadilhas

- **A25:** impulso de 0,12–0,27 pu em 100,0–100,2 ms que a forma programada não tem (9 de 9 capturas); mecanismo {bdg-warning}`NÃO VERIFICADO`.
- **A22:** o mesmo instante fixo (100 ms) aparece na 08 a 50 Hz.
- **A2, A3, A4, A5, A16:** como na {doc}`06-flicker` (sem consulta após `TRACe:DATA`, trava, `REPeat`, `ABORt`).
- **K7:** o extremo vem do osciloscópio no registro bruto.
- **`analisar_sessao` e a cobertura:** a reconstrução offline instancia a classe sem osciloscópio e cai sempre no ramo do sorteio de `valor_para_captura`, mesmo quando a captura usou a cobertura ([analisar_sessao.py:163-175](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L163-L175)); o efeito na correlação desta classe com cobertura ativa é {bdg-warning}`NÃO VERIFICADO` ({doc}`../medicao/correlacao` §8).

## 10. Histórico por versão

- **v1.8:** a frequência da oscilação passa a ter cobertura determinística com `set capturas N` (N > 1).
- **v1.13:** `capturas_padrao` = 3 (frequência e duração são sorteadas); o gancho `parametros_com_disturbio_reduzido`.
- **v1.15:** sorteio de início e fase (a duração já era sorteada); o diagnóstico da cópia em 100 ms acrescenta a A25 ao que se sabia da A22 e entrega `diag_ciclos_trace.py`, `diag_marcadores_trace.py` e `modelo_lista_fonte.py`; a revisão dos pendentes da correlação inclui a 09 sorteada no diagnóstico e recomenda 6 a 9 capturas.

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| A oscilação de 300–2400 Hz chega à saída | {bdg-success}`VERIFICADO NA BANCADA` | 3 condições, 07/10/2026; programada × medida 0,750–0,927 |
| Impulso extra em 100 ms, 9 de 9 | {bdg-success}`VERIFICADO NA BANCADA` | 07/10/2026; 0,12–0,27 pu em 100,0–100,2 ms |
| Mecanismo do impulso extra | {bdg-warning}`NÃO VERIFICADO` | `modelo_lista_fonte.py` sem confronto com dado real |
| `gerar()` e programada de hoje | {bdg-info}`OFFLINE` | modelo × programada 0,996–1,000 |

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
| `Experimento.gerar` ([experimentos_waveform/09.py:20-32](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/09.py#L20-L32)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"oscillation_hz", "duration_s", "inicio_disturbio_s", "duracao_s", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.parametros_com_disturbio_reduzido` ([experimentos_waveform/09.py:34-38](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/09.py#L34-L38)) | `parametros`, `fracao` ($k$) | `{"oscillation_amplitude_pu_bancada": k · 0,3}` | a linha [mestre.py:3109](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3109) de `ExperimentoWaveform._limitar_disturbio_para_bancada` |

- `gerar` decide `cobertura_ativa = not simulado and capturas_override is not None`, sorteia `frequencia` (`valor_para_captura(rng, 300.0, 2400.0, ...)`) e `duracao` (`rng.uniform(0.010, 0.040)`), chama `self.sortear(rng, f0, inicio_legado_s=0.080, duracao_legada_s=duracao)` (sem `duracao_variavel`: a duração do sorteio é a própria $d$) e soma `sinais.oscilacao_amortecida(t, inicio_s=sorteio.inicio_s, duracao_s=duracao, frequencia_hz=frequencia)` à senoide deslocada.
- Atributos: `capturas_padrao` = 3 ([09.py:18](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/09.py#L18)). `pre_trigger_s` herdado.
- O gancho lê a amplitude padrão com `inspect.signature(oscilacao_amortecida)`: se a assinatura mudar, o gancho acompanha (acoplamento sutil).
- Contrato e ganchos: {doc}`../codigo/classes_contrato`; o diagnóstico da cópia: {doc}`../diagnostico` e {doc}`../codigo/modelo_lista_fonte`.

## 13. Referências

- Código: `experimentos_waveform/09.py`; `logica/sinais.py` (`oscilacao_amortecida`, `valor_para_captura`); `logica/modelo_lista_fonte.py`; `scripts/diag_ciclos_trace.py`.
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`../quirks` (A22, A25), {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`.
- Histórico: `CHANGELOG/v1.8.md`, `v1.13.md`, `v1.15.md` (seções "Diagnóstico da cópia do evento em 100 ms" e "Pendentes da correlação do distúrbio"). Norma: IEEE Std 1159-2019, Tabela 2, item 1.2.1.
