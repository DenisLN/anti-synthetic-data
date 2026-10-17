# Correlação esperada por classe

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` {bdg-success}`VERIFICADO NA BANCADA` (modelo × medida e programada × medida, 07/10/2026, 99 capturas) {bdg-warning}`NÃO VERIFICADO` (v1.15 na bancada)

**Pergunta:** qual correlação de distúrbio se deve esperar de cada uma das 20 classes, em cada par de formas (modelo × programada, programada × medida, modelo × medida), e por que algumas ficam abaixo de 0,90? **Resposta:** o que depende só do código (modelo × programada) é **0,95 a 1,000 na maioria das classes** quando o sorteio está ligado, com exceções que vêm da média de cada ciclo da TRACe (06, 10, 11, 12, 13, 14 e 16, até 0,84), do degrau de frequência da 18 (0,95) e da definição degenerada da 01 e da 19 (sem valor); o que depende da fonte e do osciloscópio (programada × medida e modelo × medida) só existe para o código **anterior à v1.15**, nas sessões de 07/10/2026, e tem quatro classes abaixo de 0,90 (05, 06, 08 e 09, mais 07 e 17 no limite), cada uma com causa registrada abaixo. Com o código da v1.15 não há medida de bancada (P-01).

Esta página constrói em cima de {doc}`../correlacao_disturbio` (a definição e a tabela de 07/10, mantidas) e de {doc}`../tres_versoes` (as três versões de cada captura). A causa de cada queda aponta para as quirks de {doc}`../quirks` e para as pendências de {doc}`../projeto/pendencias`.

## 1. As duas métricas

**Pergunta:** o que a correlação do distúrbio mede? **Resposta:** a correlação de Pearson entre o que sobra de cada sinal depois de tirar a fundamental, de modo que a senoide da rede (que dá mais de 0,99 contra qualquer senoide) não esconda o que o evento acrescenta.

**Com a senoide nominal de 1 pu** (`sinais.correlacao_disturbio`, [logica/sinais.py:485](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L485)). Para o sinal esperado $e(t)$ e o capturado $c(t)$, a mesma senoide nominal sai dos dois:

$$
s(t)=\sin\!\big(2\pi f_0 t+\varphi\big),\qquad
r_e=e-s,\qquad r_c=c-s,\qquad
\rho_\text{nom}=\frac{\sum_k (r_{e,k}-\bar r_e)(r_{c,k}-\bar r_c)}{\lVert r_e-\bar r_e\rVert\,\lVert r_c-\bar r_c\rVert}
$$

com $f_0$ a frequência da sessão e $\varphi$ a fase do modelo (`fase_graus` do metadata; sem sorteio, 0). É indiferente à **escala** do distúrbio (por isso nada diz sobre quanto o evento mede: a 03 e a 08 precisam ser lidas junto com a razão de pico), mas **não** é indiferente a um erro de amplitude ou de fase da fundamental: a fonte emite a fundamental 0,2 % a 1,4 % acima ou abaixo do programado a 127 V (diagnóstico de 12/10/2026, razão medida/programada de 1,0059 a 1,0138 na 09), e essa diferença fica no resíduo capturado.

**Com a fundamental ajustada** (`sinais.correlacao_disturbio_fundamental_ajustada`, [logica/sinais.py:535](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L535)). Em vez de subtrair a mesma senoide dos dois, ajusta em **cada** sinal, por mínimos quadrados na janela inteira, uma fundamental de amplitude e fase livres mais uma constante, e correlaciona o que sobra:

$$
x=\hat a\sin(2\pi f_0 t)+\hat b\cos(2\pi f_0 t)+\hat c+r'_x,\qquad
\rho_\text{aj}=\operatorname{corr}(r'_e,\,r'_c)
$$

(`_residuo_sem_fundamental`, [sinais.py:524](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L524)). É indiferente a erro de amplitude e de fase da fundamental, mas em distúrbios grandes ou que mexem na fundamental (02, 03, 04, 18) parte do evento é absorvida pelo ajuste, igualmente nos dois sinais: é um complemento, não um substituto. Qual das duas o dataset publica é decisão em aberto (P-31).

**Caso degenerado.** Duas condições devolvem `(None, motivo)` em vez de um número sem sentido, e a CLI mostra `n/a`: o resíduo do modelo com rms menor que `LIMITE_RESIDUO_DEGENERADO_PU = 1e-6` ([sinais.py:482](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L482); classe **01**: rms 0,0) e o resíduo do modelo **constante** (classe **19**: offset DC puro, rms de 0,0227 a 0,0929 pu, Pearson indefinido). O resíduo capturado constante também devolve `None`. A 19 é degenerada pela segunda regra; a primeira especificação citava só a 01.

**Alinhamento.** `analisar_sessao._correlacao_disturbio_alinhada` ([analisar_sessao.py:190](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L190)) desloca o início da janela no registro bruto pelo `lag` de `analisar_offset` (correlação cruzada por FFT sobre o sinal inteiro) antes de calcular; assim nenhuma amostra se perde nas bordas enquanto houver margem. Entre modelo e programada não há lag: as duas estão na mesma grade.

## 2. Os três pares

```{mermaid}
flowchart LR
    M["modelo<br/>gerar() com a seed"] -->|"modelo × programada<br/>limite da PROGRAMAÇÃO"| P["programada<br/>montar_programacao() /<br/>forma_programada_nativa()"]
    P -->|"programada × medida<br/>física da FONTE e do osciloscópio"| X["medida<br/>CH1 do osciloscópio"]
    M -->|"modelo × medida<br/>o que o dataset entrega"| X
```

| Par | O que isola | Depende de | Como se calcula |
|---|---|---|---|
| modelo × programada | o que o **código** perde ao programar a fonte: média de cada ciclo da TRACe (a fonte remove o CC de cada ciclo, manual p. 126), quantização do `%.8g`, reamostragem para 1024 pontos, nível de `VOLTage:TRIGgered` truncado a 0,1 V, forma ideal da CSINusoid, degrau de frequência da 18 | só do código | offline, sem instrumento: `AmetekMX30.montar_programacao` e `sinais.forma_programada_nativa` |
| programada × medida | o que a **fonte e o osciloscópio** fazem de diferente do pedido: toque após degrau (A20), filtragem do impulso (A21), cópia do evento em 100 ms (A22, A25), déficit de CA em ACDC (A19) | medida de bancada | só em sessão física; aqui, as 99 capturas de 07/10 |
| modelo × medida | o total que o dataset físico entrega ao usuário | tudo | `logica/analisar_sessao.py`, colunas `corr. distúrbio` e `corr. dist. fund.aj.` |

:::{important} Pendência P-31
A correlação com a fundamental ajustada foi calculada offline nas três sessões de 07/10 (99 capturas); falta calculá-la em sessão com **sorteio ligado** e com os perfis da v1.15, e decidir qual das duas métricas o dataset publica. Fecha com: qualquer sessão nova de bancada (P-01) e decisão do responsável pelo projeto. Prioridade BAIXA.
:::

:::{caution} Limitação
A `programada` das sessões de 07/10 aqui é a que o código **de hoje** (`fa82f49`) reconstrói a partir do metadata gravado, não a que a fonte recebeu em 07/10: desde a v1.15 `LIST:VOLTage` leva o rms da componente CA do ciclo, e antes levava o rms com a média (que inflava a amplitude CA nos ciclos de média diferente de zero). Para as classes sem ciclos de média diferente de zero (02, 03, 04, 05, 07, 08, 09, 17, 18, 20) a diferença é nula ou desprezível; para 06, 10, 11, 12, 13, 14, 15 e 16 a coluna "programada × medida" é uma estimativa com o código de hoje, não uma conferência do que foi programado.
:::

## 3. Tabela das 20 classes: correlação esperada por par

Correlação do **distúrbio com a senoide nominal** (a métrica de `analisar_sessao`). Valores de 3 casas, faixa quando a classe tem várias capturas. Origem dos números:

- **Modelo × programada**: simulação offline com o código da v1.15 (sorteio ligado e perfil `literatura`, os padrões), 127 V, 50 e 60 Hz, seis capturas por célula (índices 0 a 5, sementes `777000 + 100 × classe + índice`); a faixa reúne as duas frequências. Os valores com sorteio desligado, por frequência, estão na seção 4.
- **Programada × medida** e **modelo × medida**: as 99 capturas de 07/10/2026 nas três condições, reconstruídas **sem sorteio** (como as sessões foram gravadas), com `analisar_sessao` para o segundo par e as funções do projeto para o primeiro (seção 5).

| Classe | Modelo × programada (simulação, v1.15 padrão) | Programada × medida (07/10) | Modelo × medida (07/10) | Abaixo de 0,90: causa |
|---|---|---|---|---|
| 01 | n/a | n/a | n/a | degenerada: o resíduo do modelo é nulo (limiar 1e-6 pu, [sinais.py:482](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L482)); não há distúrbio a correlacionar |
| 02 | 1,000 | 0,997–0,999 | 0,997–0,999 | — |
| 03 | 1,000 | 0,943–0,945 | 0,943–0,945 | — |
| 04 | 1,000 | 0,996–0,999 | 0,996–0,999 | — |
| 05 | 1,000 | 0,964–0,974 | 0,499–0,504 | modelo × medida 0,50 em 07/10: sem sorteio (`SORTEIO=0`, como em 07/10) o modelo é a soma 1 + 3.ª/5.ª/7.ª harmônicas e a fonte emite a CSINusoid (senoide clipada): modelo × programada 0,518; programada × medida 0,96–0,97. Com sorteio (padrão da v1.15) o modelo é a senoide clipada e o modelo × programada vai a 1,000 (simulação); modelo × medida nesse modo {bdg-warning}`NÃO VERIFICADO` |
| 06 | 0,870–0,998 | 0,967–0,991 | 0,826–0,960 | a fonte remove a média de cada ciclo da TRACe (manual, `TRACe:DATA`, p. 126); a média por ciclo do flicker (até ±0,02 pu) fica no modelo e não na programada |
| 07 | 0,993–0,996 | 0,911–0,951 | 0,899–0,942 | não fica abaixo de 0,90 na programada (0,91–0,95) nem no modelo (0,90–0,94; 0,899 a 230 V/50 Hz); a queda vem da oscilação da saída depois de cada entalhe (A20) |
| 08 | 0,986–0,993 | 0,028–0,816 | 0,004–0,831 | a 127 V/50 Hz o impulso saiu a 100 ms em vez de 80 ms (A22), pico fora da janela esperada; a 127 V/60 Hz o impulso de 50 µs sai filtrado pela fonte (A21) e a métrica é sensível ao alinhamento de uma amostra (P-02, P-03) |
| 09 | 0,996–1,000 | 0,750–0,927 | 0,749–0,925 | a 127 V/50 Hz a medida tem um impulso de 0,12–0,27 pu em 100,0–100,2 ms que a programada não tem (A25, P-02) |
| 10 | 0,963–1,000 | 0,997–0,999 | 0,975–0,999 | média de cada ciclo nos ciclos de borda do degrau (sorteio ligado); o modelo × medida a 127 V/60 Hz é 0,975 (P-09) |
| 11 | 0,843–0,998 | 0,996–0,999 | 0,969–0,999 | idem 10; a média por ciclo do flicker somado ao SAG não foi calculada (P-09, P-12) |
| 12 | 0,938–0,998 | 0,996–0,998 | 0,967–0,998 | idem 10 (P-09) |
| 13 | 0,950–0,999 | 0,996–0,997 | 0,976–0,997 | idem 10 (P-09) |
| 14 | 0,925–0,999 | 0,972–0,989 | 0,961–0,989 | idem 10 (P-09) |
| 15 | 0,966–0,995 | 0,998 | 0,988–0,991 | — |
| 16 | 0,879–1,000 | 0,997–1,000 | 0,972–1,000 | idem 10: degrau a meio ciclo (P-09) |
| 17 | 0,993–0,996 | 0,915–0,948 | 0,902–0,931 | idem 07: oscilação da saída após o entalhe (A20) |
| 18 | 0,952–0,952 | 1,000 | 0,939–0,982 | a programada troca de frequência em degrau (`start_hz` na 1.ª metade, `end_hz` na 2.ª) e o modelo é uma rampa linear: modelo × programada 0,95 (nominal) e 0,91 (ajustada); a fase na troca nunca foi medida (P-06) |
| 19 | n/a | n/a | n/a | degenerada: o resíduo do modelo é um offset constante (Pearson indefinido); a métrica não se aplica |
| 20 | 0,991–0,999 | 0,912–0,982 | 0,907–0,981 | — |

Leitura: das 20 classes, **01 e 19 não têm valor** (degeneradas); **02, 03, 04, 15 e 20 ficam sempre acima de 0,90** em todos os pares disponíveis; as quedas abaixo de 0,90 em 07/10 são **05, 06, 08 e 09** (e 07 e 17 no limite), todas com causa mensurável; as compostas 10, 11, 12, 13, 14 e 16 perdem correlação **só na programação** (média do ciclo) e a medida física as acompanha (0,96 a 1,000).

## 4. Modelo × programada por frequência e sorteio (simulação offline, v1.15)

Cada célula: `nominal / ajustada`, faixa das seis capturas. **Fonte do número**: simulação offline com `sinais.correlacao_disturbio` e `sinais.correlacao_disturbio_fundamental_ajustada`, sobre as formas de `gerar_tres_versoes.reconstruir_versoes` ({doc}`../tres_versoes`). O limite de bancada (`fator_disturbio_bancada`) não entra: a correlação do distúrbio é invariante à escala do distúrbio.

| Classe | 50 Hz, sorteio desligado | 50 Hz, sorteio ligado | 60 Hz, sorteio desligado | 60 Hz, sorteio ligado |
|---|---|---|---|---|
| 01 | n/a | n/a | n/a | n/a |
| 02 | 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 |
| 03 | 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 |
| 04 | 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 |
| 05 | 0,518–1,000 / 0,518–1,000 | 1,000 / 1,000 | 0,518–1,000 / 0,518–1,000 | 1,000 / 1,000 |
| 06 | 0,785–0,971 / 0,784–0,970 | 0,870–0,997 / 0,870–0,997 | 0,859–0,979 / 0,858–0,979 | 0,895–0,998 / 0,895–0,998 |
| 07 | 0,993–0,995 / 0,993–0,995 | 0,993–0,995 / 0,993–0,994 | 0,994–0,996 / 0,994–0,995 | 0,995–0,996 / 0,995–0,996 |
| 08 | 0,986 / 0,986 | 0,986 / 0,986 | 0,993 / 0,993 | 0,993 / 0,993 |
| 09 | 0,996–1,000 / 0,996–1,000 | 0,998–1,000 / 0,998–1,000 | 0,995–1,000 / 0,995–1,000 | 0,996–1,000 / 0,996–1,000 |
| 10 | 1,000 / 1,000 | 0,963–1,000 / 0,954–1,000 | 0,977 / 0,968 | 0,989–0,999 / 0,971–0,998 |
| 11 | 1,000 / 0,999 | 0,843–0,989 / 0,833–0,985 | 0,971 / 0,959 | 0,846–0,998 / 0,838–0,996 |
| 12 | 1,000 / 1,000 | 0,946–0,998 / 0,936–0,994 | 0,968 / 0,960 | 0,938–0,998 / 0,929–0,994 |
| 13 | 1,000 / 1,000 | 0,950–0,999 / 0,938–0,997 | 0,978 / 0,973 | 0,955–0,997 / 0,946–0,996 |
| 14 | 1,000 / 1,000 | 0,925–0,999 / 0,905–0,999 | 0,972 / 0,965 | 0,971–0,996 / 0,962–0,994 |
| 15 | 0,990 / 0,990 | 0,966–0,993 / 0,966–0,993 | 0,993 / 0,993 | 0,976–0,995 / 0,976–0,995 |
| 16 | 1,000 / 1,000 | 0,879–1,000 / 0,866–1,000 | 0,974 / 0,963 | 0,993–1,000 / 0,968–1,000 |
| 17 | 0,994–0,995 / 0,994–0,995 | 0,993–0,994 / 0,993–0,994 | 0,993–0,995 / 0,993–0,995 | 0,995–0,996 / 0,994–0,996 |
| 18 | 0,959 / 0,917 | 0,952–0,952 / 0,913–0,915 | 0,952 / 0,914 | 0,952 / 0,913–0,915 |
| 19 | n/a | n/a | n/a | n/a |
| 20 | 0,999 / 0,999 | 0,999 / 0,999 | 0,991–0,999 / 0,991–0,999 | 0,991–0,999 / 0,991–0,999 |

Duas leituras. **Sorteio ligado muda o resultado**: a posição do evento passa a variar e, com ela, quanto da média de cada ciclo do degrau cai em ciclos de borda (10, 11, 12, 13, 14, 16), e a 05 deixa de ter o descasamento do modelo (soma de harmônicas) contra a CSINusoid. **A 18 fica em 0,95 (nominal) e 0,91 a 0,92 (ajustada)** porque a programada troca de frequência em degrau no meio da janela e o modelo é uma rampa linear.

## 5. Programada × medida e modelo × medida em 07/10 (por condição)

Cada célula: `nominal / ajustada`. "—" = a classe não está na sessão (230 V/50 Hz não tem 02, 03, 04, 08 nem 16). Sessões: `sessao_2026-10-07_127V_50Hz` (127 V/50 Hz), `sessao_2026-10-07_14-59-54_run02` (127 V/60 Hz) e `sessao_2026-10-07_230V_50Hz` (230 V/50 Hz).

**Programada × medida**

| Classe | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| 01 | n/a | n/a | n/a |
| 02 | 0,999 / 0,999 | 0,997 / 0,996 | — |
| 03 | 0,945 / 0,926 | 0,943 / 0,920 | — |
| 04 | 0,999 / 0,999 | 0,996–0,997 / 0,995–0,997 | — |
| 05 | 0,974 / 0,981 | 0,974 / 0,981 | 0,964 / 0,976 |
| 06 | 0,967–0,978 / 0,974–0,983 | 0,984–0,991 / 0,989–0,995 | 0,981–0,989 / 0,984–0,991 |
| 07 | 0,933–0,951 / 0,934–0,950 | 0,926–0,938 / 0,931–0,943 | 0,911–0,933 / 0,920–0,935 |
| 08 | 0,028–0,058 / 0,024–0,053 | 0,807–0,816 / 0,813–0,824 | — |
| 09 | 0,750–0,798 / 0,800–0,855 | 0,885–0,911 / 0,932–0,940 | 0,850–0,927 / 0,857–0,937 |
| 10 | 0,999 / 0,999 | 0,997 / 0,997 | 0,998 / 0,997 |
| 11 | 0,999 / 0,999 | 0,997 / 0,997 | 0,996 / 0,996 |
| 12 | 0,998 / 0,997 | 0,996 / 0,996 | 0,998 / 0,998 |
| 13 | 0,996 / 0,996 | 0,997 / 0,998 | 0,997 / 0,997 |
| 14 | 0,989 / 0,988 | 0,987 / 0,988 | 0,972 / 0,972 |
| 15 | 0,998 / 0,998 | 0,998 / 0,998 | 0,998 / 0,998 |
| 16 | 1,000 / 1,000 | 0,997 / 0,995 | — |
| 17 | 0,932–0,937 / 0,941–0,946 | 0,935–0,948 / 0,940–0,950 | 0,915–0,929 / 0,925–0,935 |
| 18 | 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 |
| 19 | n/a | n/a | n/a |
| 20 | 0,955–0,958 / 0,967–0,970 | 0,912–0,973 / 0,923–0,982 | 0,976–0,982 / 0,979–0,984 |

**Modelo × medida** (a coluna nominal reproduz a tabela de {doc}`../correlacao_disturbio`, seção 4; a ajustada é nova)

| Classe | 127 V/50 Hz | 127 V/60 Hz | 230 V/50 Hz |
|---|---|---|---|
| 01 | n/a | n/a | n/a |
| 02 | 0,999 / 0,999 | 0,997 / 0,996 | — |
| 03 | 0,945 / 0,926 | 0,943 / 0,920 | — |
| 04 | 0,999 / 0,999 | 0,996–0,997 / 0,995–0,997 | — |
| 05 | 0,504 / 0,506 | 0,503 / 0,506 | 0,499 / 0,504 |
| 06 | 0,826–0,935 / 0,831–0,940 | 0,878–0,960 / 0,882–0,964 | 0,836–0,945 / 0,838–0,948 |
| 07 | 0,916–0,942 / 0,917–0,942 | 0,912–0,924 / 0,917–0,930 | 0,899–0,922 / 0,907–0,924 |
| 08 | 0,004–0,011 / 0,001–0,006 | 0,824–0,831 / 0,831–0,839 | — |
| 09 | 0,749–0,797 / 0,799–0,854 | 0,883–0,910 / 0,932–0,938 | 0,850–0,925 / 0,857–0,934 |
| 10 | 0,999 / 0,999 | 0,975 / 0,966 | 0,998 / 0,997 |
| 11 | 0,999 / 0,998 | 0,969 / 0,957 | 0,996 / 0,995 |
| 12 | 0,998 / 0,997 | 0,967 / 0,959 | 0,998 / 0,998 |
| 13 | 0,996 / 0,996 | 0,976 / 0,972 | 0,997 / 0,997 |
| 14 | 0,989 / 0,988 | 0,961 / 0,955 | 0,972 / 0,972 |
| 15 | 0,988 / 0,989 | 0,991 / 0,991 | 0,988 / 0,988 |
| 16 | 1,000 / 1,000 | 0,972 / 0,960 | — |
| 17 | 0,914–0,923 / 0,923–0,931 | 0,921–0,931 / 0,925–0,933 | 0,902–0,918 / 0,912–0,924 |
| 18 | 0,982 / 0,964 | 0,939 / 0,960 | 0,982 / 0,964 |
| 19 | n/a | n/a | n/a |
| 20 | 0,954–0,957 / 0,966–0,969 | 0,907–0,966 / 0,918–0,975 | 0,975–0,981 / 0,978–0,983 |

A coluna nominal do segundo par reproduz, valor a valor, a tabela de `docs/correlacao_disturbio.md`; a ajustada foi calculada offline em 2026-10-15 (P-31). Nas classes de distúrbio pequeno (09, 20, 17, 07, 06) a ajustada sobe (09 a 127 V/50 Hz: 0,749–0,797 para 0,799–0,854); nas de evento grande ou que mexem na fundamental (03, 10 a 14, 16 a 127 V/60 Hz, 18 a 50 Hz) ela desce, como previsto.

## 6. Por que cada classe cai abaixo de 0,90

**Pergunta:** quando a correlação fica baixa, a culpa é do código ou da fonte? **Resposta:** compare os três pares: se **modelo × programada** já é baixo, a perda está na programação; se só **programada × medida** é baixo, é a física da fonte.

1. **06 (FLICKER): perda na programação.** A fonte remove a média de cada ciclo (manual, `TRACe:DATA`, p. 126). A média por ciclo do flicker é uma escada de rms 0,002 a 0,032 pu contra um distúrbio de rms 0,036 a 0,074 pu e cresce com a frequência do flicker. Com a média de cada ciclo tirada do modelo, programada × modelo vai a 0,9999–1,0000 em todas as 28 capturas calculadas (cálculo registrado em `CHANGELOG/v1.15.md`). Decisão em aberto: comparar a 06 com a forma programada ou redefinir o flicker com média nula por ciclo (P-12).
2. **10, 11, 12, 13, 14, 16: perda na programação, só nos ciclos de borda do degrau.** O degrau a meio ciclo tem média diferente de zero naquele ciclo e a fonte a remove. O erro programada × modelo é de 0,24 a 0,33 pu nas 10, 11, 12 e 16 (P-09; nas 13 e 14 não foi calculado). Só se recuperaria com offset por passo (ACDC, que tem o déficit de 5 a 6 %).
3. **05: descasamento de modelo.** Em 07/10 (`SORTEIO=0`) o modelo é a soma de 1.ª, 3.ª, 5.ª e 7.ª harmônicas e a fonte emite a CSINusoid (senoide clipada): modelo × programada **0,518**, programada × medida **0,96 a 0,97**, modelo × medida 0,50. Com sorteio (padrão da v1.15), `gerar()` passa a produzir a senoide clipada (`sinais.senoide_clipada_pu`) e o modelo × programada vai a 1,000; o modelo × medida com isso {bdg-warning}`NÃO VERIFICADO` (rms e THD da CSINusoid a 10, 15 e 20 % nunca foram medidos: P-10).
4. **07 e 17: física da fonte.** O modelo × programada é 0,993 a 0,996 e a medida cai para 0,90 a 0,95: a saída oscila (7,5 a 10 kHz, morre em menos de 0,5 ms) depois de cada degrau do entalhe (A20). A calibração de crista (fator de 1,186 na 07 e de 1,031 na 17 a 127 V/60 Hz) não cobre esse toque (P-07).
5. **08: física da fonte e posição.** O impulso de 50 µs não é reproduzido (limite de banda: 200 µs de subida 10–90 %, A21) e sai filtrado. A 50 Hz o impulso programado em 80 ms (fronteira de ciclo) saiu em 100 ms nas três capturas (A22): o pico cai fora da janela esperada e o par vai a 0,03 (programada × medida) e 0,004 a 0,011 (modelo × medida). A 60 Hz o pico cai perto do esperado (amostras 2404/2401) e o par é 0,81 a 0,83, sensível ao alinhamento de uma amostra. Recaptura a 127 V/50 Hz com o impulso em 90 ms: P-03.
6. **09: física da fonte.** A medida tem um impulso de 0,12 a 0,27 pu em 100,0 a 100,2 ms que a programada não tem (9 de 9 capturas de 07/10, A25); a 127 V/50 Hz o par fica em 0,75 a 0,80. Mecanismo {bdg-warning}`NÃO VERIFICADO` até a bancada (P-02).
7. **18: troca de frequência.** O modelo é uma rampa linear; a programada, um degrau de frequência; programada × medida é 1,000. A continuidade da fase na troca nunca foi medida (P-06).

## 7. Exemplo numérico reproduzível

**Pergunta:** como verificar um número da tabela com as funções do projeto, sem hardware? **Resposta:** reconstrua o modelo e a programada da classe 06 a 60 Hz e compare; a queda vem das médias por ciclo.

Do diretório raiz do repositório, com o Python do projeto (numpy):

```python
# exemplo_corr.py: executar da raiz do repositório
import sys
sys.path[:0] = ["logica", "scripts"]
import numpy as np
import analisar_sessao as A
import gerar_tres_versoes as g
import sinais

FS, F0 = 30000.0, 60.0
semente, indice = 777_600, 0                      # classe 06, primeira captura
registro = dict(id_captura="06-000", fs_hz=FS, pontos=6000, tensao_base_rms=127.0,
                f0_hz=F0, seed=semente, nivel_indice=indice, perfil="literatura",
                sorteio_posicao=False, parametros={})
t = np.arange(6000) / FS
experimento = A._carregar_experimento_cls("06")(g._BancadaOffline(registro))
_, parametros = experimento.gerar(t, F0, indice, np.random.default_rng(semente))
registro["parametros"] = {k: float(v) for k, v in parametros.items() if isinstance(v, (int, float))}
v = g.reconstruir_versoes(registro)               # modelo e programada (montar_programacao)
modelo, programada = v["modelo"], v["programada"]

nominal, _ = sinais.correlacao_disturbio(modelo, programada, fs_hz=FS, f0_hz=F0)
ajustada, _ = sinais.correlacao_disturbio_fundamental_ajustada(modelo, programada, fs_hz=FS, f0_hz=F0)
print(f"flicker_hz = {parametros['flicker_hz']:.4f}")
print(f"modelo x programada, nominal   : {nominal:.4f}")
print(f"modelo x programada, ajustada  : {ajustada:.4f}")
ciclo = 500                                       # 30000 / 60 amostras por ciclo
print("média por ciclo do modelo (pu)  :", np.round(modelo.reshape(-1, ciclo).mean(axis=1), 4))
print("média por ciclo da programada   :", np.round(programada.reshape(-1, ciclo).mean(axis=1), 4))
```

Saída obtida em 2026-10-16 (Windows 11, Python 3.11.9, numpy 2.4.6, `main` em `fa82f49`):

```text
flicker_hz = 23.5173
modelo x programada, nominal   : 0.8585
modelo x programada, ajustada  : 0.8578
média por ciclo do modelo (pu)  : [-0.0065  0.0167 -0.0194  0.0136 -0.0017 -0.0109  0.0187 -0.0182  0.0096
  0.0032 -0.0147  0.0196]
média por ciclo da programada   : [ 0. -0.  0. -0.  0.  0. -0.  0. -0. -0.  0. -0.]
```

A correlação 0,8585 está dentro da faixa da classe 06 a 60 Hz sem sorteio (seção 4) e a causa fica à vista: o modelo tem média de ciclo de até ±0,02 pu e a programada, zero. Os ciclos têm 500 amostras (30 kSa/s ÷ 60 Hz), como `montar_programacao` os corta.

## 8. O que não está verificado

- **Sorteio ligado, perfis e compostas da v1.15 na bancada** {bdg-warning}`NÃO VERIFICADO`: nenhuma sessão de bancada com o código da v1.15 existe (P-01); a seção 3 usa simulação para o par de código e as 99 capturas de 07/10 para os pares de medida.
- **Faixa de referência histórica** (0,95–1,00; 0,75–0,94; 0,005 da 08): vem de `validacao_gerador_v1.14.md`, que não está no repositório (P-27). Esta página **não** compara os números com essa faixa; descreve o que o código e as sessões de 07/10 produzem.
- **Programada de 07/10 reconstruída com o código de hoje**: ver a limitação da seção 2.
- **Seis capturas por célula** na simulação: a faixa mostra o comportamento, não é um intervalo de confiança; o sorteio da posição do evento deixa a faixa larga nas compostas.
- **Perfis `norma` e `fronteira`** não foram simulados aqui (só `literatura`); a 05 tem nível diferente na `norma` (2 %), nunca medido (P-10).
- **Contra qual forma `analisar_sessao` compara.** A função reconstrói a forma do modelo com `gerar()` e, se o metadata tem `fator_disturbio_bancada`, a substitui por `senoide + fator × (modelo − senoide)`, isto é, a forma **limitada pela bancada** ([analisar_sessao.py:180-187](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L180-L187)). Como a correlação do distúrbio é invariante à escala do distúrbio, o resultado não depende desse fator (seção 4); o que muda é só a razão de pico, que a mesma ferramenta também calcula.
- **Ramo de cobertura nas classes 04, 06, 08, 09 e 19.** `_reconstruir_esperado` instancia o experimento com `osc=None`, o que faz `valor_para_captura()` cair sempre no ramo do sorteio, mesmo quando a captura real usou o ramo determinístico de cobertura (`set capturas N` com N > 1). O próprio código registra isso como limitação residual ([analisar_sessao.py:163-175](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L163-L175)); o efeito declarado é só a razão de pico dessas classes. {bdg-warning}`NÃO VERIFICADO` o efeito na correlação do distúrbio dessas cinco classes quando a cobertura estava ativa.
