# Classe 05: HARMONICS

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 (THD de 5 %; 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` CSINusoid a 10, 15 e 20 %; nível de 2 %; nível de 30 % por TRACe {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-10` {bdg-danger}`PENDENTE P-18` {bdg-danger}`PENDENTE P-19`

| Campo | Valor |
|---|---|
| Número e nome | 05 HARMONICS (distorção harmônica) |
| Arquivo | `experimentos_nativos/05.py`, classe `Experimento(ExperimentoNativo)` |
| Mecanismo na bancada | **misto**: até 20 % de THD, a senoide clipada nativa ({scpi}`SOURce:FUNCtion:SHAPe` `CSINusoid` e {scpi}`SOURce:FUNCtion:SHAPe:CSINusoid`); acima de 20 % (nível de 30 %), TRACe/LIST como as classes de forma de onda |
| `capturas_padrao` | 1 (herdado, [mestre.py:1564](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1564)); 5 níveis, e **sem `set capturas` só o nível 0 roda** |
| Sorteio de posição | F (só a fase; a distorção ocupa os 200 ms inteiros) |
| Depende do perfil? | sim: os cinco níveis de THD mudam (`thd_niveis`) |
| Condições já medidas | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 1 captura (THD de 5 %) em cada |

## 1. Em uma resposta

**Pergunta:** como a bancada produz uma senoide com 5, 10, 15, 20 ou 30 % de THD? **Resposta:** até **20 %** pela senoide clipada interna da AMETEK (CSINusoid), que a fonte aplica sozinha; o nível de **30 %** passa do teto dessa função e é programado como forma de onda arbitrária (TRACe/LIST) calculada em Python. O modelo `gerar()` acompanha a bancada: senoide clipada nos níveis nativos e soma de 3.ª, 5.ª e 7.ª harmônicas no nível por TRACe.

Estado: o THD de 5 % foi medido e bateu (5,0 % esperado e medido, em três condições); os níveis de 10, 15, 20 e 2 % e o de 30 % por TRACe nunca foram capturados, e o modelo clipado (v1.15) nunca foi comparado com a bancada ({ref}`P-10 <p-10>`).

## 2. O fenômeno e a norma

Distorção harmônica: componentes em múltiplos inteiros da frequência fundamental, produzidos por cargas não lineares. O THD (*total harmonic distortion*) é a razão entre o valor rms dos harmônicos e o da fundamental. Item 5.2 da Tabela 2 da IEEE Std 1159-2019: **0 a 20 % de THD de tensão**. O perfil `literatura` usa 5, 10, 15, 20 e 30 % (o 30 % está **fora** da faixa da norma); o perfil `norma` usa 2, 5, 10, 15 e 20 % e nunca passa do teto de 20 % da CSINusoid.

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

Há dois ramos, escolhidos por `sorteio.ativo and not usar_trace(capture_index)`:

**Nível nativo (THD ≤ 20 %, sorteio ligado): senoide clipada normalizada em rms.** Com $\theta(t)=2\pi f_0(t+\tau)$, $c$ o corte tal que $\mathrm{clip}(\sin\theta,-c,c)$ tem o THD pedido (`corte_da_senoide_clipada`, [sinais.py:596-610](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L596-L610), bisseção em um ciclo de 4096 pontos, recusa THD acima de 25 %) e $\rho_c$ o rms do ciclo clipado:

$$
x(t)=\frac{1/\sqrt{2}}{\rho_c}\;\mathrm{clip}\big(\sin\theta(t),\,-c,\,c\big)
$$

A normalização mantém o rms da senoide de pico 1 ($1/\sqrt{2}$ = 0,7071 pu), porque a fonte escala a forma ao rms programado (`senoide_clipada_pu`, [sinais.py:613-621](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L613-L621)).

**Nível por TRACe (30 %) ou sorteio desligado: soma de harmônicas.** Com $r=(0{,}60;\,0{,}30;\,0{,}10)$ e $a_k=\mathrm{THD}\cdot r_k/\lVert r\rVert$ (a soma quadrática dos $a_k$ é exatamente o THD):

$$
x(t)=\sin\theta+a_3\sin 3\theta+a_5\sin 5\theta+a_7\sin 7\theta,\qquad
\text{fundamental}=1\ \text{pu},\quad \text{rms}=\sqrt{\tfrac{1+\mathrm{THD}^2}{2}}
$$

Para THD = 0,30: $a_3=0{,}2654$, $a_5=0{,}1327$, $a_7=0{,}0442$ e rms 0,7382 pu. Com `set sorteio off` a soma vale em **todos** os níveis (o `gerar()` de 34a0d82).

```{literalinclude} ../../experimentos_nativos/05.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_nativos/05.py, Experimento.gerar
```

Os cinco níveis, o mecanismo de cada um e o que `gerar()` produz (cálculo offline com as funções do projeto, `sinais.corte_da_senoide_clipada`, `sinais.senoide_clipada_pu` e `sinais.onda_com_harmonicos`):

| THD | Perfis que o usam | Mecanismo na bancada | Fundamental (pu) | Pico do modelo (pu) | Pico a 127 V (V) | rms do modelo (pu) | Corte da clipagem (pu do pico) |
|---|---|---|---|---|---|---|---|
| 2 % | `norma` | CSINusoid nativa | 0,9998 | 0,9616 | 172,7 | 0,7071 | 0,9483 |
| 5 % | `norma`, `literatura`, `fronteira` | CSINusoid nativa | 0,9988 | 0,9258 | 166,3 | 0,7071 | 0,8834 |
| 10 % | `norma`, `literatura`, `fronteira` | CSINusoid nativa | 0,9950 | 0,8812 | 158,3 | 0,7071 | 0,7787 |
| 15 % | `norma`, `literatura`, `fronteira` | CSINusoid nativa | 0,9889 | 0,8460 | 152,0 | 0,7071 | 0,6740 |
| 20 % | `norma`, `literatura`, `fronteira` | CSINusoid nativa | 0,9806 | 0,8167 | 146,7 | 0,7071 | 0,5690 |
| 30 % | `literatura`, `fronteira` | TRACe/LIST (soma 3.ª/5.ª/7.ª) | 1,0000 | 0,8252 | 148,2 | 0,7382 | — |

- **Parâmetros no metadata:** `thd` (fração) e `fase_graus`.
- **Seed:** `base_seed + 5 · 1 000 000 + indice_global`. A classe não consome o `rng`.
- **Capturas e níveis:** `capturas_padrao` = 1: o plano padrão é uma captura no nível 0 (5 % na `literatura`, 2 % na `norma`). Para cobrir os cinco níveis é preciso `set capturas N`. **Só com `set capturas N` digitado (qualquer N, inclusive 1) o nível de 30 % entra no plano**, e ele custa gravações de TRACe (12 a 60 Hz, 10 a 50 Hz por captura), que contam na estimativa de 280 por conexão ({ref}`P-23 <p-23>`).

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** por que dois mecanismos? **Resposta:** porque `SOURce:FUNCtion:SHAPe:CSINusoid` só aceita até 20 % de THD (`MAX_CSINE_THD_PCT = 20,0`, [ametek_orm.py:163](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L163)); para 30 % a classe usa `usar_trace()` e vira uma classe de forma de onda.

**Níveis até 20 %: CSINusoid.** Ordem (`ExperimentoNativo._capturar_real`, [mestre.py:2936-2983](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2936-L2983), ramo nativo):

1. {scpik}`:TIMebase:POSition` não muda (a classe não tem evento localizado); {scpi}`TRIGger:SYNChronize:PHASe` recebe a fase sorteada.
2. `configurar()` chama `AmetekMX30.configure_harmonics_csine` ([ametek_orm.py:939-987](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L939-L987)): recusa THD fora de $(0;\,20]$ %; `aguardar_idle`; `_neutralizar_transientes_residuais` ({scpi}`FUNCtion:MODE` `FIXed`, {scpi}`SOURce:FREQuency:MODE` `FIXed`); {scpi}`SOURce:FUNCtion:SHAPe` `CSINusoid`; {scpi}`*WAI`; {scpi}`SOURce:FUNCtion:SHAPe:CSINusoid` com o THD em %; {scpi}`*WAI`; e `assert_no_errors` ({scpi}`SYSTem:ERRor?`), que aponta o comando certo.
3. Em seguida `trigger_step(base)` ({scpi}`VOLTage:MODE` `STEP`, {scpi}`VOLTage:TRIGgered`), só para gerar o BOT; a forma já mudou na hora de `SHAPe CSINusoid`.
4. Armamento, `*TRG` e leitura como na {doc}`01-normal`.
5. Ao fim da classe `restaurar_forma_e_modo_padrao` volta a forma para `SINusoid` (`select_sine_shape`, [ametek_orm.py:989-1011](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L989-L1011)).

**Nível de 30 %: TRACe/LIST.** `usar_trace(capture_index)` ([05.py:69-70](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/05.py#L69-L70)) é verdadeiro quando o THD do nível passa de `TETO_CSINE` ([05.py:25](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/05.py#L25)). O ramo TRACe de `_capturar_real` chama `gerar()` (a soma de harmônicas), fixa a escala do osciloscópio em `scope_scale_v` ($1{,}5\,\sqrt{2}\,V_\text{base}$, [05.py:72-75](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/05.py#L72-L75)), `program_capture` ({scpi}`TRACe:DATA`, {scpi}`SOURce:LIST:VOLTage`, … em {doc}`../scpi/sequencias` §7) e `arm_transient`. A fonte emite, nesse nível, o rms do próprio modelo: `montar_programacao` põe o rms CA do ciclo em `LIST:VOLTage`, que é **1,044 × a tensão base** (pico reconstruído 148,2 V a 127 V); o modelo tem fundamental 1 pu e rms 0,738 pu, contra 0,707 pu dos níveis nativos. A diferença é entre níveis, não entre modelo e programada (correlação 1,0000), e `gerar()` não muda.

**Janela e margem.** `pre_trigger_s` herdado (0): o trigger cai no início da janela; registro de 20 ms antes e 50 ms depois ({doc}`../medicao`).

## 5. Parâmetros por perfil

| Componente em `perfis.py` | `norma` | `literatura` (padrão) | `fronteira` |
|---|---|---|---|
| `thd_niveis` | níveis 0,02 / 0,05 / 0,1 / 0,15 / 0,2 | níveis 0,05 / 0,1 / 0,15 / 0,2 / 0,3 | níveis 0,05 / 0,1 / 0,15 / 0,2 / 0,3 |

O perfil `fronteira` usa os mesmos níveis da `literatura` (THD não tem fronteira definida). Os 2 % do perfil `norma` são escolha de implementação (o mínimo da faixa), e a CSINusoid a 2 % **nunca foi exercitada**. O teto de 20 % vale nos três perfis: `corte_da_senoide_clipada` recusa THD acima de 25 % e `configure_harmonics_csine` acima de 20 %.

## 6. Limites físicos e fator de extremo

Os níveis de THD têm pico **menor** que o da senoide pura (a clipagem reduz o pico: 0,82 a 0,96 pu nos níveis nativos), então o limite que importa é o do nível de 30 % por TRACe e o das condições de tensão alta. O fator de extremo da 05 é 0,998 a 127 V (< 1, e o código nunca prevê abaixo do programado: `fator_extremo_da_classe`, [mestre.py:626-630](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L626-L630)).

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 0,998 | 1 | 166,3 | 182,9 | 415,8 | 100 % | 1/1 rodam |
| 127 V/50 Hz | 0,998 | 1 | 166,3 | 183,1 | 415,8 | 100 % | 1/1 rodam |
| 230 V/50 Hz | 1,001 | 1 | 301,1 | 331,6 | 415,8 | 100 % | 1/1 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 1 | 288,0 | 467,3 | 415,8 | 100 % | 0/1 rodam, 1 pulada(s) |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, nível 0 = 5 %, sorteio ligado). O nível de 30 % por TRACe não tem fator medido; o pico a 127 V é 148,2 V. A 220 V/60 Hz (sem tabela) a 05 é pulada: 288,0 V × 1,475 × 1,10 = 467,3 V ({ref}`P-21 <p-21>`). A 380 V, o pico do nível de 30 % seria 443,5 V por conta, acima dos 425 Vp do hardware; o `START_BENCH` recusa 380 V (tensão de linha) e a combinação não foi simulada com a bancada falsa.

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. Para a 05 a sonda decisiva é o **THD**: a CSINusoid que não foi aplicada (5,05 % de referência contra 0,98 % medidos na sessão de 16/09/2026) é pega por ela.

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,709 / 0,708 | 0,698 / 0,708 | 0,721 / 0,708 | 0,050 / 0,050 | 1,345 / 1,371 |
| 127 V/50 Hz | 0,709 / 0,708 | 0,699 / 0,708 | 0,719 / 0,708 | 0,050 / 0,050 | 1,345 / 1,371 |
| 230 V/50 Hz | 0,712 / 0,708 | 0,704 / 0,708 | 0,720 / 0,708 | 0,050 / 0,050 | 1,343 / 1,371 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`). O THD de 5,0 % esperado e medido nas três condições mostra que a CSINusoid de 5 % foi aplicada. A crista medida (1,343–1,345) fica 2 % abaixo da esperada do modelo de então (1,371, a soma de harmônicas); com o modelo clipado de hoje a crista esperada é a da senoide clipada.

## 8. As três versões e a correlação esperada

A `programada` da 05 depende do nível: nos níveis ≤ 20 % é a senoide clipada com o THD pedido (`sinais.forma_programada_nativa`, [sinais.py:624-683](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L624-L683), que chama `senoide_clipada_pu` com a mesma fase do modelo); no de 30 % é a reconstrução da TRACe (`montar_programacao(...).programada_pu()`, igual às classes de forma de onda).

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | 1,000 | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | 0,964–0,974 | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | 0,499–0,504 | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| 0,518–1,000 / 0,518–1,000 | 1,000 / 1,000 | 0,518–1,000 / 0,518–1,000 | 1,000 / 1,000 |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | 0,974 / 0,981 | 0,974 / 0,981 | 0,964 / 0,976 |
| modelo × medida | 0,504 / 0,506 | 0,503 / 0,506 | 0,499 / 0,504 |

Causa de a classe ficar abaixo de 0,90, quando fica: modelo × medida 0,50 em 07/10: sem sorteio (`SORTEIO=0`, como em 07/10) o modelo é a soma 1 + 3.ª/5.ª/7.ª harmônicas e a fonte emite a CSINusoid (senoide clipada): modelo × programada 0,518; programada × medida 0,96–0,97. Com sorteio (padrão da v1.15) o modelo é a senoide clipada e o modelo × programada vai a 1,000 (simulação); modelo × medida nesse modo {bdg-warning}`NÃO VERIFICADO`

A queda de **0,50** em modelo × medida em 07/10 não era da fonte: com `SORTEIO=0`, como as sessões foram gravadas, o modelo era a soma de harmônicas e a fonte emite a senoide clipada. Medido contra a programada (a clipada) dava 0,96–0,97, e modelo × programada é 0,518. Na v1.15 o modelo passou a ser a clipada nos níveis nativos e modelo × programada vai a 1,000. O modelo × medida **com o modelo novo** é {bdg-warning}`NÃO VERIFICADO` (nenhuma sessão com o código da v1.15; o rms e o THD da CSINusoid interna a 10, 15 e 20 % nunca foram medidos, {ref}`P-10 <p-10>`).

## 9. Quirks e armadilhas

- **A6:** `SOURce:FUNCtion:SHAPe CSINe` (a forma curta do manual) é rejeitado com `-256 File name not found`; só `CSINusoid` (o nome do catálogo) funciona.
- **A7:** trocar a forma recarrega a tabela e deixa a fonte muda por segundos; o `*WAI` depois de cada um dos dois comandos assenta a troca.
- **A8:** `SOURce:FUNCtion:SHAPe?` e `SOURce:MODE?` não existem como consulta (sem resposta e um `-113` preso à fila); a classe nunca os consulta.
- **A9:** `FUNCtion:MODE LIST` residual de uma classe de lista passa a participar do `*TRG`; `_neutralizar_transientes_residuais` roda antes de trocar a forma.
- **Ordem dos comandos é inegociável:** `assert_no_errors` logo depois de `SOURce:FUNCtion:SHAPe:CSINusoid` (`AGENTS.md`, limites inegociáveis); antes dele o erro aparecia no comando seguinte e era atribuído a ele.
- **A3:** o nível de 30 % grava TRACes na Flash e entra na contagem da trava de ~280 gravações por conexão.
- **Acoplamento:** `TETO_CSINE` ([05.py:25](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/05.py#L25)) e os níveis decidem `usar_trace`; mudar o teto muda o mecanismo e a estimativa de gravações ({doc}`../codigo/acoplamentos`).
- **Escala do osciloscópio:** `scope_scale_v` dá 1,5 × o pico nominal "com folga" porque a soma de harmônicas em 30 % tem crista um pouco maior que a senoide limpa.

## 10. Histórico por versão

- **v1.6:** `SOURce:FUNCtion:SHAPe CSINe` falhava com `-256`; a forma do catálogo é `CSINusoid`, e a ordem dos dois comandos passou a ser a do exemplo do manual (primeiro a forma, depois o nível). Funcionando, o comando muda a forma de forma **permanente**: no preflight a CSINusoid ficava ligada nas etapas seguintes e a estimativa de frequência saía 97,5 Hz em vez de ~60 Hz (os patamares achatados geram cruzamentos por zero extras); disso veio o `restaurar_forma_e_modo_padrao` ao fim de toda classe.
- **v1.7:** só o primeiro dos dois writes tinha a espera; o segundo recarregava a tabela sem espera e o erro `-113` aparecia no `INITiate:IMMediate` da classe, atribuído ao comando errado. Passou a haver um `*WAI` depois de cada write e `assert_no_errors` logo depois do THD.
- **v1.11:** H-NATIVO: a CSINe de 5 % saiu com THD de 0,98 % (sem harmônico nenhum) nas sessões de 16/09/2026, sem erro SCPI; a neutralização de listas residuais e o readback fecharam o caso.
- **v1.12:** `VOLTage:MODE?` voltava `FIX` depois de escrever `STEP` nas classes 01, 05 e 19 (escrita em rajada perdida); a sincronização por `*ESR?` corrigiu.
- **v1.13:** `capturas_padrao` fica em 1 na 05 (os níveis são discretos); o nível de 30 % passa a custar gravações de TRACe na estimativa.
- **v1.15:** perfis (`thd_niveis`); fase sorteada; o modelo dos níveis nativos passa de soma de harmônicas a **senoide clipada normalizada em rms** (rms 0,7071 contra até 0,721 antes; pico 0,82–0,96 pu contra 0,88–0,99); a revisão dos pendentes da correlação do distúrbio confirmou THD, rms, fase e teto e decidiu **não** normalizar o nível de 30 % (reduziria a fundamental a 0,958 pu e mudaria o dataset).

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| CSINusoid de 5 % aplica THD de 5,0 % | {bdg-success}`VERIFICADO NA BANCADA` | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 07/10/2026, validação 1/1 |
| `gerar()` clipado: THD, rms, fase e teto do CSINe | {bdg-info}`OFFLINE` | tabela da seção 3 e testes `Classes05_07_18Tests` |
| CSINusoid a 10, 15 e 20 %; nível de 2 % | {bdg-warning}`NÃO VERIFICADO` | nunca capturados; rms da CSINusoid interna desconhecido |
| Nível de 30 % por TRACe na bancada | {bdg-warning}`NÃO VERIFICADO` | nunca capturado; pico a 380 V não simulado |
| Modelo clipado contra a medida | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15 |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
:::

:::{important} Pendência P-10
Nunca medidos: rms e THD da CSINusoid interna a 10, 15 e 20 %, o nível de 2 % (perfil `norma`), o nível de 30 % por TRACe e o modelo novo contra a bancada. Fecha com: bancada. Prioridade MÉDIA.
:::

:::{important} Pendência P-18
Passo final `SINE` no `LIST`: existe só no branch `feat/passo-final-sin`, **fora da `main`** ({doc}`../projeto/passo-final-sin`); na 05 afetaria só o nível de 30 %, que usa TRACe/LIST. Fecha com: bancada e decisão do responsável pelo projeto. Prioridade MÉDIA.
:::

:::{important} Pendência P-19
`TRACe:DATA?` (`set diagnostico retrieve`) nunca foi executado na fonte real; vale para o nível de 30 % da 05. Fecha com: bancada, com o painel à vista. Prioridade MÉDIA.
:::

## 12. Como o código da classe funciona

| Símbolo | Recebe | Devolve | Quem chama |
|---|---|---|---|
| `TETO_CSINE` ([experimentos_nativos/05.py:25](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/05.py#L25)) | nada | `AmetekMX30.MAX_CSINE_THD_PCT / 100` = 0,20 | `usar_trace` |
| `Experimento.NIVEIS_THD` ([experimentos_nativos/05.py:33-36](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/05.py#L33-L36)) | nada (propriedade) | `perfis.faixa(self.config, "thd_niveis")` | `gerar`, `configurar`, `usar_trace`, `total_niveis` |
| `Experimento.total_niveis` ([experimentos_nativos/05.py:38-39](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/05.py#L38-L39)) | nada | `len(NIVEIS_THD)` | `dimensionar_capturas` ([mestre.py:1684-1701](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1684-L1701)) |
| `Experimento.gerar` ([experimentos_nativos/05.py:41-59](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/05.py#L41-L59)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"thd", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.configurar` ([experimentos_nativos/05.py:61-67](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/05.py#L61-L67)) | `capture_index` | `{"thd": nível}` | a linha [mestre.py:2972](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2972) de `ExperimentoNativo._capturar_real` (só para níveis ≤ 20 %) |
| `Experimento.usar_trace` ([experimentos_nativos/05.py:69-70](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/05.py#L69-L70)) | `capture_index` | `True` se o THD do nível passa de `TETO_CSINE` | `ExperimentoNativo.grava_trace` ([mestre.py:2895-2896](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2895-L2896)) e as linhas [mestre.py:2937](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2937) e [mestre.py:2981](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2981) de `ExperimentoNativo._capturar_real` |
| `Experimento.scope_scale_v` ([experimentos_nativos/05.py:72-75](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/05.py#L72-L75)) | nada | $1{,}5\sqrt{2}V_\text{base}$ | a linha [mestre.py:2914](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2914) de `ExperimentoNativo._preparar_acquisicao_real` e a linha [mestre.py:2940](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2940) do ramo TRACe |

- `gerar` calcula `thd` e os coeficientes antes do sorteio, chama `self.sortear(rng, f0)` (só fase) e escolhe o ramo: clipada se `sorteio.ativo and not self.usar_trace(capture_index)`, soma de harmônicas caso contrário.
- `configurar` só é chamado para os níveis nativos: `usar_trace` desvia o nível de 30 % para o caminho TRACe **antes** de `configurar` (o comentário do arquivo diz que "os 4 níveis" cabem na CSINusoid, mas com o perfil `norma` são cinco; a lógica depende só de `usar_trace`).
- A classe **não** define `NIVEIS`; por isso `ExperimentoNativo.tensao_rms_programada` ([mestre.py:2903-2911](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2903-L2911)) devolve `None` (o rms da 05 não é informado à pré-validação, que usa o pico da forma).
- Contrato, ganchos e acoplamentos: {doc}`../codigo/classes_contrato` §3 e §4; o módulo de sinais em {doc}`../codigo/sinais`.

## 13. Referências

- Código: `experimentos_nativos/05.py`; `logica/sinais.py` (`corte_da_senoide_clipada`, `senoide_clipada_pu`, `onda_com_harmonicos`, `forma_programada_nativa`); `logica/ametek_orm.py` (`configure_harmonics_csine`, `MAX_CSINE_THD_PCT`, `montar_programacao`).
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`../scpi/sequencias`, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`, {doc}`../projeto/passo-final-sin`.
- Histórico: `CHANGELOG/v1.6.md`, `v1.7.md`, `v1.11.md`, `v1.12.md`, `v1.13.md`, `v1.15.md` (seções "Classes 05, 07, 17 e 18" e "Pendentes da correlação do distúrbio"). Norma: IEEE Std 1159-2019, Tabela 2, item 5.2.
