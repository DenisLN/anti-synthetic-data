# Classe 14: SWELL_OSCILLATORY_TRANSIENT

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 com parâmetros fixos (swell 1,3 e oscilação de 600 Hz; 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 1 captura cada, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` parâmetros sorteados; 230 V/50 Hz inviável com swell sorteado {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-11` {bdg-danger}`PENDENTE P-18` {bdg-danger}`PENDENTE P-19`

| Campo | Valor |
|---|---|
| Número e nome | 14 SWELL_OSCILLATORY_TRANSIENT (elevação com transitório oscilatório) |
| Arquivo | `experimentos_waveform/14.py`, classe `Experimento(ExperimentoWaveform)` |
| Mecanismo na bancada | **forma de onda**: TRACe/LIST ({scpi}`TRACe:DATA`, {scpi}`SOURce:LIST:VOLTage`, um passo por ciclo) |
| `capturas_padrao` | 3 ([14.py:16](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/14.py#L16)) |
| Sorteio de posição | I D F, mais o swell e a frequência da oscilação |
| Depende do perfil? | sim: o swell muda (`swell_composto`) |
| Condições já medidas | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 1 captura cada, com swell 1,3 e 600 Hz fixos |

## 1. Em uma resposta

**Pergunta:** como o dataset combina uma elevação com um transitório oscilatório, e por que é a composta mais difícil de rodar a tensões altas? **Resposta:** durante o evento a tensão sobe a $\ell$ (1,1 a 1,8 pu) **e** uma oscilação amortecida de 300 a 2400 Hz, 0,3 pu, é somada; o pico do patamar mais a oscilação passa do teto de 415,8 V já a 230 V/50 Hz, e o limite de bancada, que só reduz o distúrbio até 25 %, **não basta**: as três capturas do plano são puladas (0 de 3) e a classe não roda nessa condição.

## 2. O fenômeno e a norma

Composta da elevação (item 2.1.2 da Tabela 2 da IEEE Std 1159-2019, 1,1 a 1,8 pu, de 0,5 a 30 ciclos) com o transitório oscilatório (item 1.2.1, abaixo de 5 kHz, 0,3 a 50 ms, 0 a 4 pu). A norma não define a composição. A especificação (`experimentos.txt`, classe 14) fixava swell 1,3 pu e oscilação de 600 Hz sobreposta, início 60 ms, duração 40 ms; desde a v1.15 o swell e a frequência são sorteados e a duração é a do evento sorteado.

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v(t)=\underbrace{\ell\,\sin\theta}_{t_0\le t<t_0+d}+0{,}3\,\sin\!\big(2\pi f_\text{osc}(t-t_0)\big)\,e^{-(t-t_0)/\tau_d}\,\mathbb{1}\big[t_0\le t<t_0+d\big],\qquad \ell\sim\mathcal{U}(1{,}1;\,1{,}8),\ \ \tau_d=5\ \text{ms}
$$

(fora do evento, $v=\sin\theta$). A oscilação não é escalada por $\ell$: soma ao patamar. $t_0$, $d$ e $\varphi$ vêm do sorteio de posição ({ref}`fórmulas <sorteio-de-posicao>`; sem sorteio, 60 ms e 40 ms).

```{literalinclude} ../../experimentos_waveform/14.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_waveform/14.py, Experimento.gerar
```

- **Ordem do `rng`:** swell, depois frequência da oscilação (`oscilacao_composto_hz`).
- **Parâmetros no metadata:** `swell_pu`, `oscillation_hz`, `inicio_disturbio_s`, `duracao_s`, `fase_graus`.
- **Seed:** `base_seed + 14 · 1 000 000 + indice_global`.
- **Capturas:** `capturas_padrao` = 3 ([14.py:16](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/14.py#L16)).

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** o que impede a 14 a 230 V? **Resposta:** o extremo previsto. O patamar de $\ell \cdot 325{,}3$ V (230 V/50 Hz) mais a oscilação chega a 535–594 V de pico programado; mesmo com o distúrbio reduzido ao mínimo de 25 %, o extremo previsto passaria do teto de 415,8 V.

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

O gancho `parametros_com_disturbio_reduzido` ([14.py:33-40](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/14.py#L33-L40)) devolve `swell_pu_bancada` $=1+k(\ell-1)$ e `oscillation_amplitude_pu_bancada` $=k\cdot0{,}3$.

**Janela e margem.** `pre_trigger_s` herdado (0); registro de 20 ms antes e 50 ms depois ({doc}`../medicao`).

:::{warning} Decisão em aberto P-04
`AmetekMX30.program_capture` só **avisa** quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga", [ametek_orm.py:1522-1527](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1522-L1527)); quem recusa é a pré-validação do `mestre.py` (`ExperimentoBase._indices_viaveis`, antes de qualquer SCPI, e `_conferir_extremos_fisicos`, depois da captura já gravada). Pergunta ao responsável pelo projeto: o ORM também deve recusar? Opções: manter como está, ou recusar no ORM (um limite de segurança mais restritivo). Este site não decide ({ref}`P-04 <p-04>`, prioridade MÉDIA).
:::

:::{warning} Decisão em aberto P-23
A fonte travou na ~280.ª gravação de TRACe de uma mesma conexão (quirk A3; causa {bdg-warning}`NÃO VERIFICADO`), e cada captura desta classe grava 12 TRACes a 60 Hz (10 a 50 Hz). `README.md` e `AGENTS.md` ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `set perfil todos`), enquanto o roteiro de bancada usa listas de classes (menos de 250 por conexão). Pergunta: qual texto os documentos devem adotar? Opção recomendada pelo roteiro: listas (`run 01-07`, depois `run 09-20`). Decisão do responsável pelo projeto ({ref}`P-23 <p-23>`, prioridade MÉDIA).
:::

## 5. Parâmetros por perfil

**O que o sorteio cobre em cada componente.** Na 14: swell (1,1 a 1,8 pu na `literatura`) e frequência da oscilação (300 a 2400 Hz); amplitude e $\tau_d$ constantes. ({ref}`Detalhe das compostas <sorteio-das-compostas>`.)

| Componente em `perfis.py` | `norma` | `literatura` (padrão) | `fronteira` |
|---|---|---|---|
| `swell_composto` | sorteio off: 1,3; sorteio on: U(1,15; 1,75) | sorteio off: 1,3; sorteio on: U(1,1; 1,8) | sorteio off: 1,1 / 1,8; sorteio on: níveis por `capture_index` (sem intervalo) |
| `oscilacao_composto_hz` | sorteio off: 600; sorteio on: U(300; 2400) | sorteio off: 600; sorteio on: U(300; 2400) | sorteio off: 600; sorteio on: U(300; 2400) |

O perfil `fronteira` alterna 1,1 e 1,8 pu por `capture_index`. Os valores com `set sorteio off` (swell 1,3 e 600 Hz) reproduzem o `gerar()` de 34a0d82.

## 6. Limites físicos e fator de extremo

Fatores medidos: **0,977** a 127 V/60 Hz (< 1, tratado como 1,0: o código nunca prevê abaixo do programado), 1,012 a 127 V/50 Hz e 1,021 a 230 V/50 Hz. O pico programado é o do patamar mais a oscilação: de 295 a 328 V a 127 V.

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 0,977 | 3 | 295,0–328,1 | 324,5–360,9 | 415,8 | 100 % | 3/3 rodam |
| 127 V/50 Hz | 1,012 | 3 | 295,4–327,7 | 331,8–368,1 | 415,8 | 100 % | 3/3 rodam |
| 230 V/50 Hz | 1,021 | 3 | 535,0–593,5 | 600,9–666,6 | 415,8 | 100 % | 0/3 rodam, 3 pulada(s) |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 3 | 511,1–568,4 | 829,2–922,2 | 415,8 | 100 % | 0/3 rodam, 3 pulada(s) |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 3 capturas padrão, seed 20260827, sorteio ligado). A 127 V as três rodam (extremo previsto de 325 a 368 V, 78 a 89 % do teto de 415,8 V). A 230 V/50 Hz as **três são puladas**: extremo previsto de 600,9 a 666,6 V e k necessário de 17 a 22 %, abaixo do mínimo aceito de 25 %; a 220 V/60 Hz (sem tabela) também 0 de 3 (k de 9 a 11 %). Em 07/10 (swell 1,3 fixo) a 14 rodou a 230 V/50 Hz com $k$ = 36 %. A v1.13 já registrava a 14 reduzida a 48 % a 220 V (`swell_pu_bancada` = 1,15). Há um limite conceitual além do numérico: o swell aplicado é $1+k(\ell-1)$, e com $k$ = 25 % (o mínimo aceito) e $\ell$ = 1,3 ele cai a 1,075 pu, **abaixo do limiar de 1,1 pu** do item 2.1.2 da norma, ou seja, deixaria de ser um swell.

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`.

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,720 / 0,707 | 0,708 / 0,707 | 0,935 / 0,920 | 0,012 / 0,011 | 1,448 / 1,414 |
| 127 V/50 Hz | 0,715 / 0,707 | 0,699 / 0,707 | 0,931 / 0,925 | 0,010 / 0,010 | 1,457 / 1,414 |
| 230 V/50 Hz | 0,714 / 0,707 | 0,703 / 0,707 | 0,792 / 0,785 | 0,004 / 0,004 | 1,437 / 1,414 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`, swell 1,3 e 600 Hz fixos). O máximo do envelope medido (0,93 pu a 127 V) acompanha o esperado (0,92); as capturas passaram.

## 8. As três versões e a correlação esperada

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 0,925–0,999 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,972–0,989 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,961–0,989 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 1,000 / 1,000 | 0,925–0,999 / 0,905–0,999 | 0,972 / 0,965 | 0,971–0,996 / 0,962–0,994 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,989 / 0,988 | 0,987 / 0,988 | 0,972 / 0,972 |
| modelo × medida | 0,989 / 0,988 | 0,961 / 0,955 | 0,972 / 0,972 |

Causa de a classe ficar abaixo de 0,90, quando fica: idem 10 (P-09)

O modelo × programada fica em 0,925–0,999 (a oscilação sorteada e os degraus) e programada × medida em 0,972–0,989.

## 9. Quirks e armadilhas

- **A20, A2, A3, A4, A5, A16, K7:** como na {doc}`10-sag-harmonics` e na {doc}`06-flicker`.
- **Fator < 1:** o fator medido de 0,977 a 127 V/60 Hz é arredondado para 1 em `fator_extremo_da_classe` ([mestre.py:626-630](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L626-L630)).
- **Acoplamento:** a ordem das chamadas a `perfis.composto` define o `rng`.

## 10. Histórico por versão

- **v1.12:** o bloqueio prévio: a 220 V a 14 era pulada.
- **v1.13:** a 220 V a 14 roda reduzida a 48 % (`swell_pu_bancada` = 1,15); `capturas_padrao` fica em 1.
- **v1.14:** fatores por condição; a 230 V/50 Hz a 14 roda reduzida a 36 % com o swell fixo de 1,3.
- **v1.15:** `capturas_padrao` = 3; swell U(1,1; 1,8) e frequência sorteados; com o swell sorteado a 230 V/50 Hz a 14 não roda (0 de 3) e a 220 V ("não verificado de novo") também não.

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| Swell 1,3 com oscilação de 600 Hz via TRACe/LIST | {bdg-success}`VERIFICADO NA BANCADA` | 3 condições, 07/10/2026; programada × medida 0,972–0,989 |
| Parâmetros sorteados | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15 |
| 230 V/50 Hz inviável com swell sorteado | {bdg-info}`OFFLINE` | previsto 600,9 a 666,6 V (seed 20260827) |
| `gerar()` e programada de hoje | {bdg-info}`OFFLINE` | modelo × programada 0,925–0,999 |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
:::

:::{warning} Decisão em aberto P-11
Manter ou reverter as extensões das compostas, entre elas o swell sorteado em 13 e 14: reverter devolveria o swell fixo de 1,3 pu, que roda a 230 V/50 Hz reduzido a 36 %. Decisão do responsável pelo projeto ({ref}`P-11 <p-11>`, prioridade MÉDIA).
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
| `Experimento.gerar` ([experimentos_waveform/14.py:19-31](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/14.py#L19-L31)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"swell_pu", "oscillation_hz", "inicio_disturbio_s", "duracao_s", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.parametros_com_disturbio_reduzido` ([experimentos_waveform/14.py:33-40](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/14.py#L33-L40)) | `parametros`, `fracao` ($k$) | `{"swell_pu_bancada", "oscillation_amplitude_pu_bancada"}` | a linha [mestre.py:3109](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3109) de `ExperimentoWaveform._limitar_disturbio_para_bancada` |

- `gerar` é a `12` com `swell_composto`: `perfis.composto` duas vezes, `self.sortear(..., inicio_legado_s=0.060, duracao_legada_s=0.040, duracao_variavel=True)`, janela multiplicada por `swell` e oscilação somada por `sinais.oscilacao_amortecida` ([sinais.py:131-146](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L131-L146)).
- Atributos: `capturas_padrao` = 3 ([14.py:16](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/14.py#L16)). `pre_trigger_s` herdado.
- Contrato e acoplamentos: {doc}`../codigo/classes_contrato` §4.

## 13. Referências

- Código: `experimentos_waveform/14.py`; `logica/perfis.py` (`composto`); `logica/sinais.py` (`oscilacao_amortecida`); `logica/mestre.py` (`_limitar_disturbio_para_bancada`).
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`12-sag-oscillatory-transient`, {doc}`../limites_e_calibracao`, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`.
- Histórico: `CHANGELOG/v1.12.md`, `v1.13.md`, `v1.14.md`, `v1.15.md`. Norma: IEEE Std 1159-2019, Tabela 2, itens 2.1.2 e 1.2.1.
