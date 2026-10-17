# Classe 20: INTERHARMONICS

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 (127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 3 capturas cada, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` perfil `norma`; duas capturas a 60 Hz abaixo de 0,95 {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-18` {bdg-danger}`PENDENTE P-19`

| Campo | Valor |
|---|---|
| Número e nome | 20 INTERHARMONICS (inter-harmônicas) |
| Arquivo | `experimentos_waveform/20.py`, classe `Experimento(ExperimentoWaveform)` |
| Mecanismo na bancada | **forma de onda**: TRACe/LIST ({scpi}`TRACe:DATA`, {scpi}`SOURce:LIST:VOLTage`, um passo por ciclo) |
| `capturas_padrao` | 3 ([20.py:20](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/20.py#L20)) |
| Sorteio de posição | F (só a fase da fundamental; as três fases das inter-harmônicas são parâmetros) |
| Depende do perfil? | sim: a amplitude de cada componente muda (`interharmonica_amplitude`) |
| Condições já medidas | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 3 capturas cada |

## 1. Em uma resposta

**Pergunta:** o que são as inter-harmônicas do dataset? **Resposta:** **três componentes senoidais em 145, 210 e 330 Hz**, com amplitude sorteada de cada uma (3 a 8 % do pico no perfil `literatura`, 0,5 a 2 % no `norma`) e fase sorteada, somadas à fundamental nos 200 ms inteiros; são frequências que **não** são múltiplos inteiros da rede de 60 Hz.

## 2. O fenômeno e a norma

Inter-harmônicas: componentes em frequências não inteiras da fundamental, muito comuns em indústrias com inversores de frequência (VFDs) e em sistemas fotovoltaicos operando em cargas parciais (`experimentos.txt`, classe 20). O item 5.3 da Tabela 2 da IEEE Std 1159-2019 dá **0 a 2 %** de tensão. O perfil `literatura` usa 3 a 8 % (acima da norma) e o perfil `norma` usa 0,5 a 2 %.

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v(t)=\sin\!\big(2\pi f_0\,(t+\tau)\big)+\sum_{i=1}^{3} a_i\,\sin\!\big(2\pi f_i\,t+\psi_i\big),\qquad
f=(145;\,210;\,330)\ \text{Hz},\quad a_i\sim\mathcal{U}(\text{faixa do perfil}),\quad \psi_i\sim\mathcal{U}(0;\,2\pi)
$$

As três amplitudes saem de **uma** chamada `rng.uniform(lo, hi, size=3)`; as três fases saem de três chamadas seguintes dentro do laço. As inter-harmônicas **não** carregam a fase sorteada da fundamental ($\psi_i$ é própria). A razão $f_i/f_0$ nunca é inteira:

| f0 | 145 Hz | 210 Hz | 330 Hz |
|---|---|---|---|
| 60 Hz | 2,417 | 3,5 | 5,5 |
| 50 Hz | 2,9 | 4,2 | 6,6 |

```{literalinclude} ../../experimentos_waveform/20.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_waveform/20.py, Experimento.gerar
```

- **Ordem do `rng`:** amplitudes (uma chamada com `size=3`), depois as três fases em sequência; o sorteio de fase da fundamental vem de um sub-fluxo. Mudar a ordem muda todas as formas da seed.
- **Parâmetros no metadata:** `interharmonic_145_pu`, `interharmonic_210_pu`, `interharmonic_330_pu`, `fase_graus` (as fases $\psi_i$ **não** vão ao metadata; só a seed as reproduz).
- **Seed:** `base_seed + 20 · 1 000 000 + indice_global`. A 20 fica fora da cobertura determinística da v1.8: com 3 amplitudes e 3 fases simultâneas não há cobertura limpa em 3 eixos, e ela continua sorteando.
- **Capturas:** `capturas_padrao` = 3 ([20.py:20](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/20.py#L20)).

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** a TRACe, que repete um ciclo por passo, carrega frequências que não são harmônicas? **Resposta:** carrega, com um custo pequeno: cada ciclo da janela é recortado, perde a média e é reamostrado; como 145, 210 e 330 Hz não fecham em um número inteiro de períodos por ciclo, cada recorte tem média não nula e perde um pouco; o erro máximo |programada − modelo| medido na correção do rms por ciclo da TRACe (`gerar()` com sorteio, seed 32) é de 0,0168 pu a 50 Hz e 127 V e de 0,0085 pu a 60 Hz e 230 V (eram 0,0045 e 0,0055 pu antes da correção do rms CA).

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

O gancho `parametros_com_disturbio_reduzido` ([20.py:35-42](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/20.py#L35-L42)) devolve `interharmonic_<f>_pu_bancada` $=k\cdot$ o valor do modelo, para cada chave que começa por `interharmonic_`.

**Janela e margem.** `pre_trigger_s` herdado (0); os 200 ms ocupados; registro de 20 ms antes e 50 ms depois ({doc}`../medicao`).

## 5. Parâmetros por perfil

| Componente em `perfis.py` | `norma` | `literatura` (padrão) | `fronteira` |
|---|---|---|---|
| `interharmonica_amplitude` | U(0,005; 0,02), sempre sorteado | U(0,03; 0,08), sempre sorteado | U(0,03; 0,08), sempre sorteado |

O perfil `fronteira` usa a faixa da literatura. As frequências são as mesmas nos três perfis.

## 6. Limites físicos e fator de extremo

Três componentes de até 8 % cada somam no pior caso 24 % de pico: nas capturas do relatório offline o pico programado vai de 193 a 203 V a 127 V (1,07 a 1,13 pu), e o fator de extremo é próximo de 1 (1,041 a 127 V/60 Hz).

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,041 | 3 | 192,7–203,4 | 220,6–233,0 | 415,8 | 100 % | 3/3 rodam |
| 127 V/50 Hz | 1,056 | 3 | 197,3–202,3 | 229,2–235,0 | 415,8 | 100 % | 3/3 rodam |
| 230 V/50 Hz | 1,032 | 3 | 357,3–358,0 | 415,1–415,8 | 415,8 | 80–100 % | 3/3 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 3 | 317,7–321,3 | 415,8 | 415,8 | 25–29 % | 3/3 rodam |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 3 capturas padrão, seed 20260827, sorteio ligado). A 230 V/50 Hz duas das três capturas rodam com as amplitudes reduzidas (80 % e 92 %); a 220 V/60 Hz (sem tabela) as três rodam reduzidas a 25–29 %.

:::{warning} Decisão em aberto P-04
`AmetekMX30.program_capture` só **avisa** quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga", [ametek_orm.py:1522-1527](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1522-L1527)); quem recusa é a pré-validação do `mestre.py` (`ExperimentoBase._indices_viaveis`, antes de qualquer SCPI, e `_conferir_extremos_fisicos`, depois da captura já gravada). Pergunta ao responsável pelo projeto: o ORM também deve recusar? Opções: manter como está, ou recusar no ORM (um limite de segurança mais restritivo). Este site não decide ({ref}`P-04 <p-04>`, prioridade MÉDIA).
:::

:::{warning} Decisão em aberto P-23
A fonte travou na ~280.ª gravação de TRACe de uma mesma conexão (quirk A3; causa {bdg-warning}`NÃO VERIFICADO`), e cada captura desta classe grava 12 TRACes a 60 Hz (10 a 50 Hz). `README.md` e `AGENTS.md` ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `set perfil todos`), enquanto o roteiro de bancada usa listas de classes (menos de 250 por conexão). Pergunta: qual texto os documentos devem adotar? Opção recomendada pelo roteiro: listas (`run 01-07`, depois `run 09-20`). Decisão do responsável pelo projeto ({ref}`P-23 <p-23>`, prioridade MÉDIA).
:::

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. As componentes são pequenas (3 a 8 %), então a mediana do envelope fica perto de 0,71 pu e o THD fica abaixo do piso de 1 %.

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,715–0,720 / 0,710–0,711 | 0,688–0,694 / 0,697–0,700 | 0,738–0,742 / 0,716–0,719 | 0,002–0,004 / 0,000 | 1,473–1,498 / 1,458–1,478 |
| 127 V/50 Hz | 0,717–0,720 / 0,709–0,709 | 0,701–0,707 / 0,705–0,706 | 0,730–0,732 / 0,712–0,713 | 0,002–0,003 / 0,000 | 1,499–1,513 / 1,477–1,483 |
| 230 V/50 Hz | 0,710–0,710 / 0,709–0,709 | 0,696–0,699 / 0,705–0,706 | 0,720–0,722 / 0,712–0,712 | 0,001 / 0,000 | 1,480–1,502 / 1,474–1,480 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`). Todas as 9 capturas passaram. O THD esperado é 0,0 % porque as frequências não são harmônicos; a validação por THD não vê a inter-harmônica, e o envelope vê só o excesso (máximo 0,73 contra 0,71 pu).

## 8. As três versões e a correlação esperada

A `programada` é a reconstrução da TRACe (cada ciclo sem a média).

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 0,991–0,999 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,912–0,982 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,907–0,981 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 0,999 / 0,999 | 0,999 / 0,999 | 0,991–0,999 / 0,991–0,999 | 0,991–0,999 / 0,991–0,999 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,955–0,958 / 0,967–0,970 | 0,912–0,973 / 0,923–0,982 | 0,976–0,982 / 0,979–0,984 |
| modelo × medida | 0,954–0,957 / 0,966–0,969 | 0,907–0,966 / 0,918–0,975 | 0,975–0,981 / 0,978–0,983 |

Causa de a classe ficar abaixo de 0,90, quando fica: —

A 20 fica em 0,91–0,98 em programada × medida (07/10) e em modelo × medida; a faixa é larga porque o distúrbio é pequeno. **Duas capturas a 60 Hz ficaram abaixo de 0,95**; a causa é {bdg-warning}`NÃO VERIFICADO`. A correlação com a fundamental ajustada **sobe** (0,923–0,982 a 127 V/60 Hz), como nas outras classes de distúrbio pequeno.

## 9. Quirks e armadilhas

- **A2, A3, A4, A5, A16:** como na {doc}`06-flicker`.
- **K7:** o extremo vem do osciloscópio no registro bruto.
- **Observação desta revisão (sem id de pendência):** o motivo que o código registra para ter removido o 150 Hz ("em uma rede de 60 Hz ele seria a 2,5.ª harmônica, muito próximo de uma harmônica real", [20.py:8-10](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/20.py#L8-L10)) não vale a 60 Hz (2,5 não é inteiro) e o motivo que valeria é outro: **a 50 Hz, 150 Hz é a 3.ª harmônica**, um múltiplo inteiro da rede. Com 145 Hz a 50 Hz (2,9.ª), a componente fica a 0,1 ordem da 3.ª harmônica, o que a aproxima do conteúdo harmônico. Isso não é defeito do código; é uma ressalva para quem lê "inter-harmônica" no rótulo da classe a 50 Hz.
- **Acoplamento:** a ordem das chamadas ao `rng` (amplitudes, depois fases) fixa as formas da seed ({doc}`../codigo/acoplamentos`).

## 10. Histórico por versão

- **v1.8:** a 20 fica fora da cobertura determinística de `set capturas` (3 amplitudes e 3 fases simultâneas). A remoção do 150 Hz da lista (hoje 145, 210 e 330 Hz) está registrada só no comentário do código ([20.py:8-10](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/20.py#L8-L10)); a versão que a fez não consta nos CHANGELOG lidos.
- **v1.13:** `capturas_padrao` = 3 (as amplitudes e fases são sorteadas); a 220 V a classe roda reduzida pelo limite de bancada.
- **v1.14:** fatores de extremo por condição (1,041; 1,056; 1,032).
- **v1.15:** perfil `norma` com 0,5 a 2 %; fase sorteada; a correção do rms por ciclo da TRACe passa o rms CA ao `LIST:VOLTage` (o erro máximo programada × modelo subiu de 0,0045 para 0,0168 pu a 50 Hz e de 0,0055 para 0,0085 pu a 60 Hz: classe de média de ciclo pequena, onde a amplitude inflada de antes compensava parte da média removida; hipótese não confirmada ponto a ponto).

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| As três inter-harmônicas chegam à saída | {bdg-success}`VERIFICADO NA BANCADA` | 3 condições, 07/10/2026; validação 3/3 |
| `gerar()` e programada de hoje | {bdg-info}`OFFLINE` | modelo × programada 0,991–0,999 |
| Perfil `norma` (0,5–2 %) | {bdg-warning}`NÃO VERIFICADO` | nunca capturado; 0,5 % do pico é 0,9 V a 127 V, menos que 1 LSB do osciloscópio nas escalas de 07/10 (89,7 a 139 V/div, 8 bits em 8 divisões: 2,8 a 4,3 V por código; estimativa) |
| Causa das duas capturas a 60 Hz abaixo de 0,95 | {bdg-warning}`NÃO VERIFICADO` | não investigada |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15 (perfil `norma` e fases sorteadas incluídos). Fecha com: bancada. Prioridade ALTA.
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
| `FREQUENCIAS` ([experimentos_waveform/20.py:11](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/20.py#L11)) | nada | `(145.0, 210.0, 330.0)` | `gerar` |
| `Experimento.gerar` ([experimentos_waveform/20.py:22-33](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/20.py#L22-L33)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"interharmonic_145_pu", "interharmonic_210_pu", "interharmonic_330_pu", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.parametros_com_disturbio_reduzido` ([experimentos_waveform/20.py:35-42](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/20.py#L35-L42)) | `parametros`, `fracao` ($k$) | `{"interharmonic_<f>_pu_bancada": k · valor}` para cada chave `interharmonic_*` | a linha [mestre.py:3109](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3109) de `ExperimentoWaveform._limitar_disturbio_para_bancada` |

- `gerar` chama `self.sortear(rng, f0)` (só fase), sorteia as três amplitudes com `rng.uniform(*perfis.faixa(self.config, "interharmonica_amplitude"), size=3)` e soma, para cada par (amplitude, frequência), uma senoide com fase `rng.uniform(0.0, 2.0 * np.pi)`.
- Atributos: `capturas_padrao` = 3 ([20.py:20](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_waveform/20.py#L20)). `pre_trigger_s` herdado.
- Contrato e ganchos: {doc}`../codigo/classes_contrato`.

## 13. Referências

- Código: `experimentos_waveform/20.py`; `logica/perfis.py` (`FAIXAS["interharmonica_amplitude"]`); `logica/ametek_orm.py` (`montar_programacao`).
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`, {doc}`../quirks`.
- Histórico: `CHANGELOG/v1.8.md`, `v1.13.md`, `v1.14.md`, `v1.15.md` (seção "RMS por ciclo da TRACE"). Norma: IEEE Std 1159-2019, Tabela 2, item 5.3.
