# Classe 01: NORMAL

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 (127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` fase sorteada e disparo na fase sorteada {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-05`

| Campo | Valor |
|---|---|
| Número e nome | 01 NORMAL |
| Arquivo | `experimentos_nativos/01.py`, classe `Experimento(ExperimentoNativo)` |
| Mecanismo na bancada | **nativa**: um STEP para a própria tensão base ({scpi}`VOLTage:MODE` `STEP`), só para gerar o pulso BOT que dispara o osciloscópio |
| `capturas_padrao` | 1 (herdado de `ExperimentoBase.capturas_padrao`, [mestre.py:1564](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1564)) |
| Sorteio de posição | F (só a fase; a classe não tem evento) |
| Depende do perfil? | não: com `set perfil todos` é capturada uma vez, sob `literatura` ({doc}`../perfis`) |
| Condições já medidas | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 1 captura em cada (07/10/2026) |

## 1. Em uma resposta

**Pergunta:** o que é a classe 01 e para que o dataset a tem? **Resposta:** é a **senoide limpa dos 200 ms inteiros, sem anomalia**; serve de exemplo "normal" para o classificador e de controle da bancada (se a 01 sai errada, nenhuma das outras 19 classes é confiável). Na fonte ela não programa distúrbio nenhum: manda um STEP de {scpi}`VOLTage:TRIGgered` para o mesmo valor que a saída já tem, apenas para a fonte emitir o pulso de trigger.

Estado: a classe rodou na bancada com o código anterior à v1.15; o que a v1.15 mudou (fase sorteada e disparo nessa fase) nunca foi medido ({ref}`P-01 <p-01>`, {ref}`P-05 <p-05>`).

## 2. O fenômeno e a norma

Não é um fenômeno: é a **condição de referência** contra a qual os eventos das outras classes são definidos. A IEEE Std 1159-2019 define os fenômenos de qualidade de energia como desvios de tensão e de frequência nominais e não tem um item de sinal normal na sua Tabela 2; o dataset precisa dele para que o classificador aprenda o que não é distúrbio. Na bancada, a 01 também prova a cadeia inteira: o pico medido da senoide pura define o fator de referência da calibração de extremos ({doc}`../limites_e_calibracao`, `fator_referencia_extremo`).

Unidade: *pu* é a tensão dividida pelo pico nominal $\sqrt{2}\,V_\text{base}$ ({doc}`../glossario`); a 127 V rms, 1 pu = 179,6 V.

## 3. O modelo em `gerar()`

$$
v(t)=\sin\!\big(2\pi f_0\,(t+\tau)\big),\qquad \tau=\frac{\varphi}{360\,f_0},\qquad t\in[0;\,200\ \text{ms}),\ 6000\ \text{amostras a } 30\ \text{kSa/s}
$$

$f_0$ é a frequência da rede da sessão (50 ou 60 Hz) e $\varphi$ a fase da senoide em $t=0$, sorteada em passos de 0,1° ({ref}`sorteio <sorteio-de-posicao>`). Sem evento localizado, o sorteio devolve só `fase_graus`; com `set sorteio off` a fase é 0 e `gerar()` devolve `{}` (o `gerar()` de 34a0d82, byte a byte).

```{literalinclude} ../../experimentos_nativos/01.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_nativos/01.py, Experimento.gerar
```

- **Parâmetros que vão ao metadata:** `fase_graus` (e `sorteio_posicao`); nenhum outro.
- **Seed:** `seed_da_captura` = `base_seed + 1 · 1 000 000 + indice_global` (`ExperimentoBase.seed_da_captura`, [mestre.py:1703-1707](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1703-L1707)). A classe não consome o `rng`: o sorteio de fase vem de um sub-fluxo da mesma seed (`_rng_do_sorteio`, [mestre.py:857-867](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L857-L867)), então a seed fixa a forma inteira.
- **Capturas:** `capturas_padrao` = 1. Sem `set capturas`, a bancada faz uma captura; `set capturas N` faz N, cada uma com uma fase diferente.

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** se a 01 é só uma senoide, por que ela manda um degrau para a fonte? **Resposta:** porque o osciloscópio dispara pelo pulso BOT da fonte, e a fonte só emite BOT num `*TRG` que aplica um transiente; o STEP para a **mesma** tensão é o menor transiente possível.

Ordem dos comandos de uma captura (`ExperimentoNativo._capturar_real`, [mestre.py:2936-2983](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2936-L2983), ramo nativo; sequência completa e diagrama em {doc}`../scpi/sequencias` §3):

1. `gerar()` fixa a fase da captura; como a 01 não sorteia `inicio_disturbio_s`, o pré-trigger do osciloscópio não muda ({scpik}`:TIMebase:POSition` fica no valor da aquisição da classe).
2. {scpi}`TRIGger:SYNChronize:PHASe` recebe a fase de disparo `fase_de_disparo_graus` (`ExperimentoNativo.fase_de_disparo_graus`, [mestre.py:2918-2934](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2918-L2934); aqui igual a `fase_graus`, porque `pre_trigger_s` é 0) por `AmetekMX30.definir_fase_de_disparo` ([ametek_orm.py:844-855](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L844-L855)), seguido de {scpi}`SYSTem:ERRor?`; **sem leitura de volta** (a consulta de fase nunca foi testada na Rev. 5.53).
3. `configurar()` chama `AmetekMX30.trigger_step` ([ametek_orm.py:876-906](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L876-L906)): {scpi}`TRIGger:STATe?` até `IDLE`; {scpi}`FUNCtion:MODE` `FIXed` e {scpi}`SOURce:FREQuency:MODE` `FIXed` (neutralizam listas residuais, quirk A9); {scpi}`VOLTage:MODE` `STEP`; {scpi}`VOLTage:TRIGgered` com a tensão base (múltiplo de 0,1 V, quirk A12); {scpi}`SYSTem:ERRor?` (o erro 19, "Illegal during transient", recusa a captura).
4. O osciloscópio é armado ({scpik}`:AER?`, {scpik}`:TER?`, {scpik}`:SINGle`, espera do bit de armado em {scpik}`:OPERegister:CONDition?`).
5. `AmetekMX30.arm` ([ametek_orm.py:1707-1752](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1707-L1752)): espera `IDLE`; lê de volta {scpi}`VOLTage:MODE?`, {scpi}`VOLTage:TRIGgered?`, {scpi}`FUNCtion:MODE?` e {scpi}`SOURce:FREQuency:MODE?` (`_conferir_transiente_programado`, [ametek_orm.py:1782-1821](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1782-L1821)); {scpi}`*WAI`; {scpi}`INITiate:IMMediate`; espera `ARM`/`WTRIG`.
6. `AmetekMX30.trigger` ([ametek_orm.py:1910-1922](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1910-L1922)): {scpi}`TRIGger:STATe?` e {scpi}`*TRG`. A saída continua na tensão base e o BOT segue pelo BNC ao EXT Trigger.
7. Espera dos dois lados e leitura do osciloscópio ({scpik}`:WAVeform:PREamble?`, {scpik}`:WAVeform:DATA?`); ao fim da classe, `restaurar_forma_e_modo_padrao` ([ametek_orm.py:1035-1048](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1035-L1048)).

:::{note} Nota de verificação
Conferido offline em 2026-10-16: a ordem acima foi lida em `mestre.py` e `ametek_orm.py` (`main` em `fa82f49`). Em bancada, a ordem foi observada com o código da v1.13/v1.14 em 07/10/2026 (127 V/50 Hz); com o código da v1.15 {bdg-warning}`NÃO VERIFICADO` (P-01).
:::

**Janela e margem.** A 01 não tem pré-trigger próprio (`pre_trigger_s` = 0): o trigger cai no início da janela e o registro físico tem 20 ms antes e 50 ms depois (8100 amostras; {doc}`../medicao`). Quem diz onde o trigger caiu é a preamble, não a classe.

**Por que a tensão base já está na saída.** A baseline programa a tensão imediata em **0 V** por segurança (`configure_safe_baseline`). Até a v1.13 era a 01 que, sendo o primeiro STEP da bateria, levava a saída a `BASE_VOLTAGE_RMS`; desde a v1.14 a checagem da cadeia de medição (`Bancada.verificar_cadeia_de_medicao`, [mestre.py:1496-1533](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1496-L1533)) chama `recuperar_estado_seguro`, que programa a tensão imediata na base (`fonte.voltage = base_voltage_rms`), antes da primeira classe, e o STEP da 01 passa a ser mesmo para o mesmo valor. A docstring de `assegurar_tensao_base` e o texto do {doc}`Guia do código <../codigo/mestre>` ainda descrevem a 01 como quem eleva a tensão; isso vale para o código anterior à v1.14, e a leitura do código atual indica que `assegurar_tensao_base` ficou redundante ({bdg-warning}`NÃO VERIFICADO` na bancada: só leitura de código).

## 5. Parâmetros por perfil

Esta classe não lê nenhum componente de `perfis.py` (`COMPONENTES_POR_CLASSE` não a lista): `gerar()` é igual nos três perfis.

Os níveis, a duração e o início não existem na 01; o sorteio de fase vale igualmente nos três perfis. É uma das oito classes que `perfis.classes_independentes_do_perfil` lista com o sorteio ligado (01, 04, 07, 08, 09, 17, 18, 19; com `set sorteio off` entra também a 16).

## 6. Limites físicos e fator de extremo

**Pergunta:** a senoide pura cabe sempre? **Resposta:** sim em todas as condições com tabela; o pico programado é o nominal (1 pu) e o extremo previsto é esse pico vezes o fator da condição vezes a margem de 1,10 (`MARGEM_FATOR_EXTREMO`, [mestre.py:504](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L504)) contra o teto de 415,8 V (`max_peak_v`).

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 1,063 | 1 | 179,6 | 210,0 | 415,8 | 100 % | 1/1 rodam |
| 127 V/50 Hz | 1,063 | 1 | 179,6 | 210,0 | 415,8 | 100 % | 1/1 rodam |
| 230 V/50 Hz | 1,030 | 1 | 325,3 | 380,3 | 415,8 | 100 % | 1/1 rodam |
| 220 V/60 Hz (sem tabela) | 1,063 (maior fator da 01) | 1 | 311,1 | 363,8 | 415,8 | 100 % | 1/1 rodam |

*Fonte:* `logica/calibracao_extremos.json` (fatores) e `scripts/relatorio_limites_bancada.py`, rodado em 2026-10-16 sobre `fa82f49` (perfil `literatura`, seed base 20260827, capturas padrão, sorteio ligado). A 01 é a **referência** da calibração: `fator_referencia_extremo` ([mestre.py:639-646](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L639-L646)) usa o fator da 01 como a parcela de senoide pura quando o limite de bancada reduz o distúrbio de outra classe. A 01 não é reduzida (nativas não reduzem; {doc}`../limites_e_calibracao` §3).

A 220 V/60 Hz (sem tabela) a 01 usa o maior fator da própria 01, não o maior de todas as tabelas.

## 7. Validação física

`ExperimentoBase._validar_fisicamente` ([mestre.py:1827-1894](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1827-L1894)) compara o medido com a forma programada pelas três sondas de `sinais.comparar_fisicamente` ([sinais.py:360-456](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L360-L456)): mediana, mínimo e máximo do envelope rms de meio ciclo (tolerância 15 %, `VALIDACAO_TOL_ENVELOPE`, [mestre.py:704](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L704)), THD (20 % relativos, com piso absoluto de 1 %, `VALIDACAO_TOL_THD`, [mestre.py:705](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L705)) e fator de crista do ciclo mediano (10 %, bilateral, com o fator de extremo calibrado da classe: `fator_extremo_efetivo_para_validacao`, [mestre.py:1896-1920](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1896-L1920)).

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,708 / 0,707 | 0,701 / 0,707 | 0,715 / 0,707 | 0,003 / 0,000 | 1,457 / 1,414 |
| 127 V/50 Hz | 0,708 / 0,707 | 0,699 / 0,707 | 0,717 / 0,707 | 0,003 / 0,000 | 1,462 / 1,414 |
| 230 V/50 Hz | 0,707 / 0,707 | 0,703 / 0,707 | 0,712 / 0,707 | 0,002 / 0,000 | 1,436 / 1,414 |

*Fonte:* `validacao_fisica` do metadata das capturas de 07/10/2026 (cada célula `medido / esperado`; sessões na seção 9 de {doc}`../projeto/estado-validacao`). Os THD de 0,2 % a 0,3 % medidos contra 0 esperado ficam abaixo do piso de 1 % e nunca reprovam a 01; a crista medida fica 1,6 % a 3,4 % acima da senoide, dentro dos 10 %.

## 8. As três versões e a correlação esperada

As três versões ({doc}`../tres_versoes`) da 01 são a mesma senoide: o `modelo` é $\sin(2\pi f_0(t+\tau))$; a `programada` (`sinais.forma_programada_nativa`, [sinais.py:624-683](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L624-L683)) é essa senoide na tensão base **quantizada em 0,1 V** (127,0 V já é múltiplo); a `medida` é o CH1.

**Resumo por par** (correlação do distúrbio com a senoide nominal; faixa quando há várias capturas):

| Par | Valor | Origem do número |
|---|---|---|
| modelo × programada | n/a | simulação offline, código da v1.15 (sorteio ligado, `literatura`, 127 V, 50 e 60 Hz, seis capturas por célula) |
| programada × medida | n/a | 99 capturas de 07/10/2026, programada reconstruída com o código de `fa82f49` |
| modelo × medida | n/a | `analisar_sessao` sobre as mesmas capturas (sem sorteio, como foram gravadas) |

**Modelo × programada por frequência e sorteio** (`nominal / ajustada`, simulação offline):

| 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|
| n/a | n/a | n/a | n/a |

**Em 07/10, por condição** (`nominal / fundamental ajustada`; "—" = a classe não rodou nessa sessão):

| Par | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| programada × medida | n/a | n/a | n/a |
| modelo × medida | n/a | n/a | n/a |

Causa de a classe ficar abaixo de 0,90, quando fica: degenerada: o resíduo do modelo é nulo (limiar 1e-6 pu, [sinais.py:482](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L482)); não há distúrbio a correlacionar

A correlação do distúrbio da 01 é **`n/a` por definição**: o resíduo do modelo (modelo menos a senoide nominal) tem rms abaixo de `LIMITE_RESIDUO_DEGENERADO_PU = 1e-6` ([sinais.py:482](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L482)) e a função devolve `(None, motivo)` em vez de um número sem sentido ({doc}`../medicao/correlacao` §1). Para a 01 vale a razão de pico e a validação física, não a correlação.

## 9. Quirks e armadilhas

- **A1, A14, A9** ({doc}`../quirks`): a escrita em rajada se perdia (corrigida por `*ESR?` depois de cada comando); escrever durante um transiente é aceito e ignorado; um `FUNCtion:MODE LIST` residual de uma classe de lista continua valendo no `*TRG` de uma nativa. O STEP da 01 protege-se das duas últimas com `aguardar_idle` e `_neutralizar_transientes_residuais`.
- **A12:** `VOLTage:TRIGgered` é truncado a 0,1 V; `trigger_step` escreve o múltiplo de 0,1 V mais próximo (`_na_resolucao_da_fonte`, [ametek_orm.py:857-865](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L857-L865)) para o readback não divergir. Em 127 V, 220 V e 230 V a base já é múltiplo.
- **A18:** o `*TRG` age na fase de {scpi}`TRIGger:SYNChronize:PHASe`, não no instante do comando; por isso a fase é programada **antes** do armamento.
- **B1:** em 07/10/2026 (`sessao_2026-10-07_14-05-40`, `_14-35-31`) um disjuntor aberto fez a 01 e as outras 19 classes saírem a ~0,45 do esperado, sem erro SCPI; a checagem da cadeia (fonte dentro de 5 % da base, CH1/fonte dentro de 10 %) foi criada por isso.
- **Acoplamento:** o STEP da 01 só é inofensivo porque a saída já está na base. Rodar a 01 **depois** de um nível diferente em outro contexto seria uma mudança de tensão real, e a bateria não foi desenhada para isso.

## 10. Histórico por versão

- **v1.7** (`CHANGELOG/v1.7.md`): `run all` falhava de forma determinística na 02 logo depois da 01 com `-300` no `INITiate:IMMediate`. O primeiro remédio, um `*WAI` antes de `INITiate:IMMediate` em `arm()`, **não resolveu sozinho**, segundo o CHANGELOG: o `restaurar_forma_e_modo_padrao` do fim da 01 mandava `SOURce:VOLTage:OFFSet 0` fora do modo `ACDC` (quirk A10) e nada consultava a fila de erros, de modo que o erro ficava pendente até o `arm()` da 02. Corrigido com o rastreio de `_modo_saida`/`_forma_atual` (no-op quando não há o que desfazer) e `assert_no_errors` depois de cada troca. *Divergência registrada:* o comentário de `AmetekMX30.arm` ([ametek_orm.py:1707-1752](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1707-L1752)) e a seção 3 de {doc}`../scpi/sequencias` atribuem o `*WAI` à troca de modo STEP → PULSe sem reconexão; as duas explicações coexistem no repositório e o código mantém o `*WAI` e o `assert_no_errors` (vale o código). Na mesma versão, `Bancada.assegurar_tensao_base` passou a reproduzir o STEP da 01 antes de uma classe isolada (`run 02` isolado media ~0 V).
- **v1.11:** P01/P02: a espera por `IDLE` antes de programar e o readback do STEP.
- **v1.12** (30/09/2026): a escrita passa a ser sincronizada por `*ESR?` (N1/N2); `VOLTage:MODE?` voltava `FIX` depois de escrever `STEP` nas classes 01, 05 e 19. A fase de disparo (F1) passou a ser programada.
- **v1.14** (07/10/2026): a checagem da cadeia de medição antes da primeira classe; a 01 deixa de ser a classe que leva a saída à base.
- **v1.15:** a fase é sorteada em passos de 0,1° e o disparo acontece nessa fase; a classe é independente do perfil (capturada uma vez com `set perfil todos`).

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| `gerar()` reproduz o de 34a0d82 com `set sorteio off` | {bdg-info}`OFFLINE` | fixtures `gerar_literatura_34a0d82.json` (400 entradas), `tests.test_offline` (497 testes, `OK`, 2026-10-16) |
| STEP a 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz | {bdg-success}`VERIFICADO NA BANCADA` | sessões de 07/10/2026, 1 captura em cada, validação física aprovada |
| Fase sorteada e disparo na fase sorteada | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15; `TRIGger:SYNChronize:PHASe` não tem readback |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15 ({doc}`../projeto/pendencias`). Fecha com: bancada (roteiro de 10 blocos). Prioridade ALTA.
:::

:::{important} Pendência P-05
O sorteio de posição nas nativas (disparo na fase sorteada em passos de 0,1°, `:TIMebase:POSition` por captura, `pre_trigger_desvio_amostras`) nunca foi medido. Para a 01 só a fase importa. Fecha com: bancada (`scripts/verificar_sessao_bancada.py`). Prioridade MÉDIA.
:::

## 12. Como o código da classe funciona

O arquivo tem 22 linhas e uma classe. Contrato geral das 20 classes: {doc}`../codigo/classes_contrato`.

| Símbolo | Linhas | Recebe | Devolve | Quem chama |
|---|---|---|---|---|
| `Experimento.gerar` ([experimentos_nativos/01.py:12-16](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/01.py#L12-L16)) | 12-16 | `t` (6000 instantes em s), `f0`, `capture_index`, `rng` | `(voltage, parametros)`: a senoide com a fase sorteada e `{"fase_graus": ...}` | os chamadores da seção 3 |
| `Experimento.configurar` ([experimentos_nativos/01.py:18-22](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/01.py#L18-L22)) | 18-22 | `capture_index` (ignorado) | `{}` | a linha [mestre.py:2972](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2972) de `ExperimentoNativo._capturar_real` |

- `gerar` chama `ExperimentoBase.sortear` ([mestre.py:1669-1673](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1669-L1673)), que chama `sortear_posicao` ([mestre.py:870-915](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L870-L915)) sem `inicio_legado_s`: o sorteio devolve só a fase (`theta` é a própria fase em $t=0$). Com o sorteio desligado devolve `Sorteio(False, ...)` e `deslocamento_s` é 0.
- `configurar` chama `self.fonte.trigger_step(self.config.base_voltage_rms)`; `self.fonte` é a `AmetekMX30` da bancada. A classe **não** define `pre_trigger_s` (herda 0), `capturas_padrao` (herda 1), nem os ganchos de bancada (`usar_trace`, `scope_scale_v`, `parametros_com_disturbio_reduzido`, `forma_para_bancada`): a bancada usa o comportamento da classe-base.
- Quem a carrega: `Bancada._carregar_classe_experimento` ([mestre.py:1381](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1381)) por caminho. O contrato e o carregador estão em {doc}`../codigo/classes_contrato`; o percurso de um `run` em {doc}`../codigo/percurso-run`; o módulo `mestre.py` em {doc}`../codigo/mestre` e a fonte em {doc}`../codigo/ametek_orm`.

## 13. Referências

- Código: `experimentos_nativos/01.py`; `logica/mestre.py` (`ExperimentoNativo`, `sortear_posicao`); `logica/ametek_orm.py` (`trigger_step`, `arm`, `trigger`).
- Documentos do site: {doc}`../classes`, {doc}`../perfis`, {doc}`../scpi/sequencias`, {doc}`../medicao/correlacao`, {doc}`../projeto/estado-validacao`, {doc}`../projeto/pendencias`, {doc}`../quirks`.
- Histórico: `CHANGELOG/v1.7.md`, `v1.11.md`, `v1.12.md`, `v1.14.md`, `v1.15.md`. Norma: IEEE Std 1159-2019, Tabela 2.
