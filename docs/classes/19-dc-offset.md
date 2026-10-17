# Classe 19: DC_OFFSET

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` pré-v1.15 com defeito conhecido (CA 5 a 6 % abaixo em ACDC; 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 07/10/2026) {bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` causa do déficit de CA {bdg-danger}`PENDENTE P-01` {bdg-danger}`PENDENTE P-17`

| Campo | Valor |
|---|---|
| Número e nome | 19 DC_OFFSET (injeção de componente contínua) |
| Arquivo | `experimentos_nativos/19.py`, classe `Experimento(ExperimentoNativo)` |
| Mecanismo na bancada | **nativa**: modo `ACDC` e offset imediato ({scpi}`SOURce:MODE` `ACDC`, {scpi}`SOURce:VOLTage:OFFSet`), mais um STEP para o BOT |
| `capturas_padrao` | 3 ([19.py:21](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/19.py#L21)) |
| Sorteio de posição | F (o offset ocupa a janela inteira) |
| Depende do perfil? | não: o offset não vem de `perfis.py`; capturada uma vez com `set perfil todos` |
| Condições já medidas | 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz, 3 capturas cada (07/10/2026) |

## 1. Em uma resposta

**Pergunta:** como a bancada soma um nível contínuo à senoide? **Resposta:** pelo modo `ACDC` da fonte: liga-se `SOURce:MODE ACDC` e programa-se `SOURce:VOLTage:OFFSet` com $\delta \cdot \sqrt{2} V_\text{base}$ volts, com $\delta \in [0{,}02;\,0{,}10]$ pu sorteado; o offset é **imediato** e permanente na janela inteira, não um transiente disparado. O defeito conhecido: **no modo `ACDC` a amplitude CA sai 5 a 6 % menor** que a programada (0,938 a 0,951 pu), enquanto o CC sai como pedido.

Estado: rodou nas três condições; o déficit de CA é medido e a causa é {bdg-warning}`NÃO VERIFICADO` ({ref}`P-17 <p-17>`); nenhum dado existe com o código da v1.15 ({ref}`P-01 <p-01>`).

## 2. O fenômeno e a norma

Componente contínua na tensão de saída: problema crônico em ramais de saída de inversores fotovoltaicos com falha de chaveamento PWM ou saturação de transformadores de acoplamento (motivação da especificação em `experimentos.txt`, classe 19). Item 5.1 da Tabela 2 da IEEE Std 1159-2019: faixa típica de **0 a 0,1 %** da tensão. A classe usa 2 a 10 % do pico nominal por escolha de projeto: 0,1 % (0,18 V a 127 V) fica abaixo da resolução do osciloscópio e não seria mensurável na bancada.

:::{note} Nota de verificação
Os itens e faixas da IEEE 1159-2019 citados nas fichas são os que o projeto usa para definir o perfil `norma`. A norma não está no repositório: a transcrição dos itens {bdg-warning}`NÃO VERIFICADO` contra o texto da norma (motivo: acesso à norma; quem fecha: o responsável pelo projeto).
:::

## 3. O modelo em `gerar()`

$$
v(t)=\sin\!\big(2\pi f_0\,(t+\tau)\big)+\delta,\qquad \delta\sim\mathcal{U}(0{,}02;\,0{,}10)\ \text{pu},\qquad t\in[0;\,200\ \text{ms})
$$

$\delta$ está em pu do **pico** nominal (a 127 V, 0,02 a 0,10 pu = 3,6 a 18,0 V). É o único parâmetro sorteado com o `rng`, por `sinais.valor_para_captura(rng, 0.02, 0.10, ...)`, que sorteia ou, com `set capturas N` (N > 1), cobre o intervalo por `linspace` (primeira captura em 0,02 e última em 0,10). A fase vem do sub-fluxo do sorteio ({ref}`fórmulas <sorteio-de-posicao>`).

```{literalinclude} ../../experimentos_nativos/19.py
:pyobject: Experimento.gerar
:language: python
:caption: experimentos_nativos/19.py, Experimento.gerar
```

- **Parâmetros no metadata:** `dc_offset_pu`, `fase_graus`.
- **Seed:** `base_seed + 19 · 1 000 000 + indice_global`.
- **Capturas:** `capturas_padrao` = 3 ([19.py:21](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/19.py#L21)); sem `set capturas` as 3 capturas sorteiam $\delta$.
- **Ordem do `rng`:** `valor_para_captura` sorteia **primeiro**; o sorteio de fase vem de um sub-fluxo. Essa ordem é um contrato com `configurar()` (seção 12).

`gerar()` é chamado nas linhas [mestre.py:2654](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2654) (dataset simulado, em `ExperimentoBase.executar`); [mestre.py:2957](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2957) (ramo nativo) e [mestre.py:2938](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2938) (ramo TRACe), em `ExperimentoNativo._capturar_real`; [mestre.py:3127](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3127) (bancada), em `ExperimentoWaveform._capturar_real`; [mestre.py:1819](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1819), [mestre.py:1988](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1988) e [mestre.py:3113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3113) (pré-validação e validação física: forma esperada e forma para a bancada, sempre com `default_rng(seed)`); e, fora do `mestre`, em [analisar_sessao.py:178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L178) (`_reconstruir_esperado`) e [scripts/gerar_tres_versoes.py:131](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/scripts/gerar_tres_versoes.py#L131). Em todos os casos o `rng` é o da seed da captura.

## 4. Como a bancada reproduz

**Pergunta:** por que o modo `ACDC` e por que a ordem importa? **Resposta:** `SOURce:VOLTage:OFFSet` só é aceito em `ACDC` (quirk A10; em `AC` dá `-300`), então o modo vem antes do offset, e a troca de modo recarrega tabelas e deixa a fonte muda por segundos, o que exige `*WAI` e `assert_no_errors` logo depois.

Ordem de uma captura (`ExperimentoNativo._capturar_real`, [mestre.py:2936-2983](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2936-L2983), ramo nativo):

1. {scpi}`TRIGger:SYNChronize:PHASe` recebe a fase sorteada (sem evento localizado).
2. `configurar()` reproduz $\delta$ com a seed própria ([19.py:33](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/19.py#L33)) e calcula `offset_v = δ · base · √2` e `ac_peak_v = base · √2`.
3. `AmetekMX30.enable_dc_offset` ([ametek_orm.py:1108-1138](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1108-L1138)): **recusa** `|offset| + pico CA > max_peak_v` com `ParameterOutOfBoundsError` (o pico físico é a soma); `SOURce:MODE ACDC`; {scpi}`*WAI`; `assert_no_errors`; {scpi}`SOURce:VOLTage:OFFSET` com `%.8g`.
4. `trigger_step(base)` ({scpi}`VOLTage:MODE` `STEP`, {scpi}`VOLTage:TRIGgered`) só para gerar o BOT; armamento, `*TRG` e leitura como na {doc}`01-normal`.
5. Ao fim da classe, `restaurar_forma_e_modo_padrao` chama `disable_dc_offset` ([ametek_orm.py:1013-1033](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1013-L1033)): zera o offset **enquanto ainda está em ACDC** (`SOURce:VOLTage:OFFSet 0`), depois `SOURce:MODE AC`, `*WAI` e `assert_no_errors`. É no-op se o modo já é `AC` (senão o offset em `AC` dá `-300`).

**Medir CC com o osciloscópio.** Com a sonda diferencial de 500× e 8 bits de resolução vertical, 9 V de CC na escala de 180 V de pico ficam no fundo de escala (erro de 4,35 V só do offset da sonda, quirk B5), e a resolução vertical limita o offset de CC a cerca de 2 LSB (quirk K10). A medida da própria fonte em ACDC (`MEASure:VOLTage:AC?`) devolve o rms **total** (CA mais CC), não só o CA (comentário em `AmetekMX30.measure_voltage`, [ametek_orm.py:1963-1977](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1963-L1977)). Por isso a análise de CC usa o CH1 com o desvio constante tratado como erro de zero (seção 7), e a medida da fonte só entra em `verificar_cadeia_de_medicao` (em AC) e no log de diagnóstico.

**Janela e margem.** `pre_trigger_s` herdado (0); registro físico com 20 ms antes e 50 ms depois ({doc}`../medicao`).

## 5. Parâmetros por perfil

Esta classe não lê nenhum componente de `perfis.py` (`COMPONENTES_POR_CLASSE` não a lista): `gerar()` é igual nos três perfis.

A 19 é **independente do perfil**: $\delta$ não vem de `perfis.py` e a forma não muda entre perfis. É uma das oito classes que `perfis.classes_independentes_do_perfil` lista com o sorteio ligado.

## 6. Limites físicos e fator de extremo

O limite novo da 19 é a soma de pico: a saída é senoide + CC, e o pico físico é $(1+\delta)\sqrt{2}V_\text{base}$ (`enable_dc_offset` recusa passar de `max_peak_v`). A 127 V o pico programado vai de 185,2 V ($\delta pprox 0{,}031$) a 195,7 V; o fator da 19 é 0,988 a 127 V/60 Hz (< 1, tratado como 1).

| Condição | Fator medido na tabela da condição | Capturas do plano | Pico programado (V) | Extremo previsto (V) | Teto (V) | Distúrbio aplicado (k) | Resultado |
|---|---|---|---|---|---|---|---|
| 127 V/60 Hz | 0,988 | 3 | 185,2–195,7 | 203,7–215,3 | 415,8 | 100 % | 3/3 rodam |
| 127 V/50 Hz | 1,007 | 3 | 185,2–195,7 | 205,1–216,8 | 415,8 | 100 % | 3/3 rodam |
| 230 V/50 Hz | 0,971 | 3 | 335,4–354,4 | 371,5–392,6 | 415,8 | 100 % | 3/3 rodam |
| 220 V/60 Hz (sem tabela) | 1,475 (maior fator de todas as tabelas; regra sem tabela) | 3 | 320,8–339,0 | 520,5–550,0 | 415,8 | 100 % | 0/3 rodam, 3 pulada(s) |

*Fonte:* `logica/calibracao_extremos.json` e `scripts/relatorio_limites_bancada.py`, 2026-10-16 (perfil `literatura`, 3 capturas padrão, seed 20260827, sorteio ligado). A 220 V/60 Hz (sem tabela) a 19 é pulada com o fator conservador ({ref}`P-21 <p-21>`); a decisão de rodar ACDC a 230 V é do dia de bancada ({ref}`P-26 <p-26>`).

## 7. Validação física

Tolerâncias: {ref}`as sondas e as tolerâncias <validacao-fisica-tolerancias>`. Na 19 a mediana do envelope aparece **5 a 6 % abaixo** do esperado, o efeito do déficit de CA, e ainda passa nos 15 % de tolerância.

| Condição | Mediana do envelope | Mínimo do envelope | Máximo do envelope | THD | Fator de crista |
|---|---|---|---|---|---|
| 127 V/60 Hz | 0,667–0,669 / 0,707–0,708 | 0,578–0,629 / 0,628–0,679 | 0,706–0,759 / 0,735–0,789 | 0,002 / 0,000 | 1,494–1,562 / 1,457–1,529 |
| 127 V/50 Hz | 0,673 / 0,707–0,708 | 0,596–0,650 / 0,628–0,679 | 0,695–0,749 / 0,735–0,789 | 0,002 / 0,000 | 1,481–1,560 / 1,457–1,529 |
| 230 V/50 Hz | 0,663–0,664 / 0,707–0,708 | 0,587–0,639 / 0,628–0,679 | 0,688–0,740 / 0,735–0,789 | 0,001 / 0,000 | 1,466–1,542 / 1,457–1,529 |

*Fonte:* `validacao_fisica` do metadata de 07/10/2026 (`medido / esperado`). A mediana do envelope (0,663–0,673) contra 0,707–0,708 esperado dá a razão 0,94 a 0,95: o déficit de CA. O THD (0,1–0,2 %) está abaixo do piso.

**CC e CA por captura, offline.** Recalculados em 2026-10-16 a partir do CH1 gravado (`tensao_pu` do `.npz` de cada captura, janela alinhada pelo `indice_trigger` do metadata = amostra 595, pré-trigger 0), sem alterar a sessão:

| Condição (sessão) | $\delta$ programado (pu / V) | Média medida − programado (pu / V) | Amplitude CA medida (pu do pico) |
|---|---|---|---|
| 127 V/60 Hz (`sessao_2026-10-07_14-59-54_run02`) | 0,0311 / 5,58; 0,0506 / 9,08; 0,0896 / 16,09 | +0,0110, +0,0108, +0,0109 / +1,97, +1,94, +1,96 V | 0,943 |
| 127 V/50 Hz (`sessao_2026-10-07_127V_50Hz`) | 0,0311 / 5,58; 0,0506 / 9,08; 0,0896 / 16,09 | −0,0070, −0,0075, −0,0068 / −1,26, −1,35, −1,22 V | 0,951 |
| 230 V/50 Hz (`sessao_2026-10-07_230V_50Hz`) | 0,0311 / 10,10; 0,0506 / 16,45; 0,0896 / 29,14 | −0,0049, −0,0046, −0,0052 / −1,60, −1,49, −1,68 V | 0,938 |

Duas leituras. **O CC passa:** a média medida acompanha o programado com inclinação 1,0 entre os três níveis (o degrau de 0,0585 pu programado entre o menor e o maior nível sai com 0,0585, 0,0588 e 0,0583 pu medidos), e o desvio é **constante dentro de cada sessão** (+1,97 V, −1,3 V, −1,6 V), da ordem de 1 LSB do osciloscópio (escala vertical de 89,7, 107 e 139 V/div do metadata, 8 bits): é erro de zero do canal (B5, K10), não da fonte. **O CA não passa:** a amplitude (raiz de dois vezes o desvio padrão da janela) é 0,938 a 0,951 pu, **5 a 6 % abaixo** do 1 pu programado, igual nos três níveis de offset de cada sessão. O déficit **não depende de $\delta$**.

:::{caution} Limitação
A causa do déficit de CA em ACDC é {bdg-warning}`NÃO VERIFICADO`: o mecanismo nunca foi isolado. A correção proposta (compensar a tensão base por $V/g$) também é {bdg-warning}`NÃO VERIFICADO`. O script de diagnóstico `scripts/diag_acdc_amplitude.py` está pronto e nunca rodou na bancada ({ref}`P-17 <p-17>`). Quem usa o dataset físico da 19 deve contar com CA 5 a 6 % abaixo do modelo.
:::

## 8. As três versões e a correlação esperada

A `programada` da 19 é a senoide na tensão base (quantizada em 0,1 V) mais o offset **enviado** (`%.8g`) dividido pelo pico nominal (`sinais.forma_programada_nativa`, [sinais.py:624-683](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L624-L683)). Ela **não** inclui o déficit de CA: isso é a diferença programada × medida.

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

Causa de a classe ficar abaixo de 0,90, quando fica: degenerada: o resíduo do modelo é um offset constante (Pearson indefinido); a métrica não se aplica

A correlação do distúrbio da 19 é **`n/a` por definição**: o resíduo do modelo (modelo menos a senoide nominal) é um offset constante, de rms 0,0227 a 0,0929 pu, e o coeficiente de Pearson de uma constante é indefinido; a função devolve `(None, motivo)` ({doc}`../medicao/correlacao` §1). O que mede a 19 é a tabela da seção 7: CC e CA contra o programado.

## 9. Quirks e armadilhas

- **A19:** no modo `ACDC` a amplitude CA sai 5 a 6 % menor (0,938 a 0,951 pu); o código não compensa nada.
- **A10:** `SOURce:VOLTage:OFFSet` só em modo `ACDC` (`-300` caso contrário); por isso `disable_dc_offset` zera o offset antes de voltar a `AC` e é no-op se o modo já é `AC`.
- **A7:** trocar `SOURce:MODE` deixa a fonte ocupada; o `*WAI` e o `assert_no_errors` evitam que um erro pendente apareça no `arm()` da classe seguinte.
- **A11:** a 19 rodou a 63,03 Hz depois da 18 até `restaurar_frequencia_base` existir (v1.12).
- **B5, K10:** a medida absoluta de CC no CH1 não é confiável; a análise usa a diferença constante por sessão.
- **Acoplamento 04/19 com `seed_da_captura`:** `configurar()` repete a conta da seed (`base_seed + 19_000_000 + capture_index`, [19.py:33](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/19.py#L33)); só concorda com `gerar()` enquanto `capture_index == indice_global` ({doc}`../codigo/acoplamentos`).

## 10. Histórico por versão

- **v1.7:** `SOURce:VOLTage:OFFSet` fora de `ACDC` dava `-300`: `disable_dc_offset` mandava o comando no fim de **toda** classe e falhava já na 01; passou a rastrear `_modo_saida` e a zerar o offset enquanto em `ACDC`. `enable_dc_offset` recebeu a mesma espera e o `assert_no_errors` preventivamente (nenhuma classe rodava a 19 logo depois de outra).
- **v1.8:** cobertura determinística de $\delta$ com `set capturas N` (N > 1).
- **v1.12:** a 19 rodava inteira a 63,03 Hz depois da 18 (F2); N1/N2: `VOLTage:MODE?` voltava `FIX` depois de `STEP` na 19 (rajada perdida).
- **v1.13:** `capturas_padrao` = 3 na 19 (o offset é sorteado).
- **v1.14:** primeiras três capturas por condição de 07/10; fator 0,988, 1,007 e 0,971 por condição.
- **v1.15:** fase sorteada; a rodada de pendentes conferíveis offline registrou em `measure_voltage` que em ACDC a leitura é o rms total e deixou o `diag_acdc_amplitude.py` pronto para a bancada.

## 11. Estado de verificação e pendências

| Afirmação | Selo | Evidência |
|---|---|---|
| CC programado chega à saída | {bdg-success}`VERIFICADO NA BANCADA` | três condições, 07/10/2026; inclinação 1,0; desvio constante de ~1 LSB |
| CA 5 a 6 % abaixo em ACDC | {bdg-success}`VERIFICADO NA BANCADA` | 0,943, 0,951 e 0,938 pu nas três condições (recalculado offline em 2026-10-16) |
| Causa do déficit de CA; compensação por $V/g$ | {bdg-warning}`NÃO VERIFICADO` | `diag_acdc_amplitude.py` nunca rodou |
| `gerar()` e programada de hoje | {bdg-info}`OFFLINE` | fixtures; correlação n/a por definição |
| Fase sorteada com ACDC | {bdg-warning}`NÃO VERIFICADO` | nenhuma sessão com o código da v1.15 |

:::{important} Pendência P-01
Nenhum dado de bancada existe com o código da v1.15. Fecha com: bancada. Prioridade ALTA.
:::

:::{important} Pendência P-17
Déficit de 5 a 6 % de CA em ACDC; `diag_acdc_amplitude.py` pronto e nunca rodado; a compensação $V/g$ é proposta; rodar ACDC a 230 V é escolha do dia. Fecha com: bancada. Prioridade MÉDIA.
:::

## 12. Como o código da classe funciona

| Símbolo | Recebe | Devolve | Quem chama |
|---|---|---|---|
| `Experimento.gerar` ([experimentos_nativos/19.py:23-30](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/19.py#L23-L30)) | `t`, `f0`, `capture_index`, `rng` | `(voltage, {"dc_offset_pu", "fase_graus"})` | os chamadores da seção 3 |
| `Experimento.configurar` ([experimentos_nativos/19.py:32-43](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/19.py#L32-L43)) | `capture_index` | `{"dc_offset_pu": δ}` | a linha [mestre.py:2972](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2972) de `ExperimentoNativo._capturar_real` |

- `gerar` decide `cobertura_ativa = not simulado and capturas_override is not None` (`simulado` = `self.osc is None`), sorteia $\delta$ com `valor_para_captura`, sorteia a fase (`self.sortear(rng, f0)`) e soma o offset à senoide deslocada.
- `configurar` **não recebe o `rng`**: constrói `default_rng(base_seed + 19_000_000 + capture_index)`, repete `valor_para_captura` (com `total = self.config.capturas(False)`) e chama `self.fonte.enable_dc_offset(offset_v, ac_peak_v=ac_peak_v)` seguido de `self.fonte.trigger_step(base)`.
- Atributos: `capturas_padrao` = 3 ([19.py:21](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/19.py#L21)); `pre_trigger_s` herdado; sem ganchos de redução (nativa não reduz).
- Contrato e acoplamentos: {doc}`../codigo/classes_contrato` §4 ("04, 19: `seed_da_captura`").

## 13. Referências

- Código: `experimentos_nativos/19.py`; `logica/ametek_orm.py` (`enable_dc_offset`, `disable_dc_offset`, `measure_voltage`); `logica/sinais.py` (`valor_para_captura`, `forma_programada_nativa`); `scripts/diag_acdc_amplitude.py`.
- Site: {doc}`../classes`, {doc}`../perfis`, {doc}`../limites_e_calibracao`, {doc}`../medicao/correlacao`, {doc}`../projeto/pendencias`, {doc}`../quirks`.
- Histórico: `CHANGELOG/v1.7.md`, `v1.8.md`, `v1.12.md`, `v1.13.md`, `v1.14.md`, `v1.15.md`. Norma: IEEE Std 1159-2019, Tabela 2, item 5.1.
