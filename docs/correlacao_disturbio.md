# Correlação da componente de distúrbio

Data: 2026-10-12. Árvore NÃO commitada (v1.15 em andamento por cima de `34a0d82`).

```{note}
Este texto é de 2026-10-12 (árvore ainda não commitada). Desde então o código foi commitado (`main` em `fa82f49`) e as linhas `arquivo:linha` abaixo **deslocaram**: `correlacao_disturbio` está em `sinais.py:485` (não 307), `correlacao_disturbio_fundamental_ajustada` em `sinais.py:535` e `_correlacao_disturbio_alinhada` em `analisar_sessao.py:190`. As demais linhas citadas aqui não foram reconferidas; procure pelo nome da função. A referência atual, com as duas métricas, a tabela das 20 classes e a recomputação offline, é {doc}`medicao/correlacao`.
```

## 1. Função

`sinais.correlacao_disturbio(esperado, capturado, *, fs_hz, f0_hz, fase_graus=0.0) -> (valor | None, motivo | None)` em `logica/sinais.py:307`.

- Subtrai dos dois sinais a mesma senoide nominal `sin(2π·f0·t + fase)`, amplitude 1 pu, e devolve a correlação de Pearson dos dois resíduos (média removida; indiferente à escala do distúrbio).
- `capturado` já vem alinhado e com o mesmo comprimento de `esperado`; o alinhamento é do chamador.
- Alinhamento (`logica/analisar_sessao.py:187`, `_correlacao_disturbio_alinhada`): lag de `analisar_offset` (o que já existia, sobre o sinal inteiro); o início da janela é deslocado por esse lag no registro bruto, assim não se perdem amostras nas bordas. Fase: `fase_graus` do metadata (as sessões de 07/10 não têm o campo, então 0); `esperado` vem de `_reconstruir_esperado`, que já trata `perfil`/`sorteio_posicao` ausentes.
- Janela: a janela nominal inteira (6000 pontos, 200 ms). A "janela rotulada" por distúrbio (`inicio_disturbio_s`/`duracao_s`) só existe com sorteio ligado; as sessões de 07/10 não a têm, então não foi usada.

**Onde mora e por quê:** em `sinais.py`, porque é matemática pura array-in/valor-out, como `comparar_fisicamente`/`janela_nominal`, testável sem importar o mecanismo de reconstrução (`analisar_sessao` carrega os scripts de `experimentos_*`). O orquestrador (lag, janela, metadata) fica em `analisar_sessao.py`.

**Sobre o pedido:** o método é razoável; ressalva: Pearson é cego à amplitude. O 03 (swell) e o 08 (razão de pico 0,27) dão correlações altas/baixas sem dizer quanto o distúrbio mede; vale ler junto com `razao_pico`. [info]

## 2. Caso degenerado

Dois limiares, ambos `LIMITE_RESIDUO_DEGENERADO_PU = 1e-6` (`sinais.py:304`), com motivo textual:

- rms do resíduo esperado ~ 0: classe 01 (rms 0,0 / ~1e-16). Motivo "sem componente de distúrbio" (`sinais.py:332`).
- resíduo esperado constante, variância ~ 0: classe 19 (offset DC puro, rms 3e-2 a 9e-2 pu, Pearson indefinido) (`sinais.py:335`). **Achado:** a spec só citava a 01; a 19 também é degenerada e sairia como número sem sentido sem este segundo caso. [média]
- resíduo capturado constante, ou formas incompatíveis: também `None` com motivo.

Saída (`analisar_sessao.py` CLI): coluna `corr. distúrbio` mostra `n/a` e uma linha seguinte com o motivo. No dicionário: `correlacao_disturbio` (None) e `correlacao_disturbio_motivo`.

## 3. Onde aparece

- `analisar_sessao.py`: chaves `correlacao_disturbio`/`correlacao_disturbio_motivo` em cada linha (`:307-308`) e coluna nova no terminal (`:356-360`), ao lado de `correlacao`.
- `relatorio_html.py`: linha "Correlação com o esperado" na tabela de metadados da captura ("total X · só do distúrbio Y (após alinhar; lag Z ms)"), de `_correlacoes` (`:228`) e `tabela_metadados` (`:427`). O HTML não tinha correlação total; passou a ter. A forma esperada agora é reconstruída sempre (`:543`) para isso, mas só é desenhada com `--com-esperado`, como antes. Conferido: `relatorio_html.py resultados/sessao_2026-10-07_127V_50Hz --classes 05,08,01 --saida <scratchpad>` deu 05 = 0,504 e 08 = 0,005/0,004/0,011, iguais ao terminal.

## 4. Tabela nas sessões de 07/10

Comando: `.\env\Scripts\python.exe logica\analisar_sessao.py resultados\sessao_2026-10-07_<sessão>` (127 V/60 Hz = `14-59-54_run02`; as três reconstruídas sem sorteio). Valores por captura; intervalo quando a classe tem várias. "—" = classe não está na sessão (230 V não tem 02, 03, 04, 08, 16).

| classe | 127 V/60 Hz | 127 V/50 Hz | 230 V/50 Hz | faixa de referência | bate? |
|---|---|---|---|---|---|
| 01 | n/a | n/a | n/a | não citada | — |
| 02 | 0,997 | 0,999 | — | 0,95–1,00 | sim |
| 03 | 0,943 | 0,945 | — | 0,75–0,94 | borda (0,943–0,945 contra teto 0,94) |
| 04 | 0,996–0,997 | 0,999 | — | 0,95–1,00 | sim |
| 05 | 0,503 | 0,504 | 0,499 | 0,50 | sim |
| 06 | 0,878–0,960 | 0,826–0,935 | 0,836–0,945 | 0,95–1,00 | NÃO (só 10 e 12 Hz a 60 Hz chegam a 0,95; a de 21 Hz fica em 0,83–0,88) |
| 07 | 0,912–0,924 | 0,916–0,942 | 0,899–0,922 | 0,75–0,94 | sim (0,942 na borda) |
| 08 | 0,824–0,831 | 0,004–0,011 | — | 0,005 | 127 V/50 Hz sim; 127 V/60 Hz NÃO (ver abaixo) |
| 09 | 0,883–0,910 | 0,749–0,797 | 0,850–0,925 | 0,75–0,94 | sim |
| 10 | 0,975 | 0,999 | 0,998 | 0,95–1,00 | sim |
| 11 | 0,969 | 0,999 | 0,996 | 0,95–1,00 | sim |
| 12 | 0,967 | 0,998 | 0,998 | 0,95–1,00 | sim |
| 13 | 0,976 | 0,996 | 0,997 | 0,95–1,00 | sim |
| 14 | 0,961 | 0,989 | 0,972 | 0,95–1,00 | sim |
| 15 | 0,991 | 0,988 | 0,988 | 0,95–1,00 | sim |
| 16 | 0,972 | 1,000 | — | 0,95–1,00 | sim |
| 17 | 0,921–0,931 | 0,914–0,923 | 0,902–0,918 | 0,75–0,94 | sim |
| 18 | 0,939 | 0,982 | 0,982 | não citada | — |
| 19 | n/a | n/a | n/a | não citada | — |
| 20 | 0,907–0,966 | 0,954–0,957 | 0,975–0,981 | 0,95–1,00 | parcial (a 60 Hz: 0,907 e 0,943) |

**08 e 05.** 05 = 0,50 nas três sessões, igual à referência. 08 = 0,004–0,011 a 127 V/50 Hz, igual ao 0,005 de referência: nessas capturas o pico está na amostra 3000/2997 da janela e não na 2401 onde o modelo põe o pulso, razão de pico 0,18–0,29 (a transitória não foi registrada). A 127 V/60 Hz a 08 dá 0,82–0,83: o pico capturado cai em 2404/2401, perto do esperado, com melhor lag −1 amostra (script de apoio, não versionado: busca de lag ±40 amostras). Ou seja, o 0,005 de referência corresponde à sessão 127 V/50 Hz, e a sessão 127 V/60 Hz (mais nova, com os fatores da v1.14) capturou o pulso. [média: a métrica é sensível ao alinhamento de uma amostra em pulso de 2 amostras; o lag vem do sinal inteiro]

**Divergências (todas conferidas na tabela acima):**
- 06 (flicker): 0,83–0,96, abaixo da faixa de referência 0,95–1,00 em 7 de 9 capturas. [média]
- 20: duas capturas a 60 Hz abaixo de 0,95. [baixa]
- 03: 0,943/0,945 acima do 0,94 declarado (diferença de arredondamento). [baixa]

## 5. Teste

Classe `CorrelacaoDisturbioTests` em `tests/test_offline.py:2008`: distúrbio idêntico = 1,0; sinal trocado = −1,0; escala do distúrbio irrelevante; correlação total > 0,95 com distúrbio ortogonal e correlação do distúrbio = 0; fase do modelo usada na senoide nominal; classe 01, offset DC, resíduo capturado constante e formas incompatíveis devolvem `None` com motivo; `analisar_sessao` ponta a ponta (01 → None, 05 → 1,0).

```
.\env\Scripts\python.exe -m unittest tests.test_offline
Ran 319 tests in 24.622s
OK
```
(`-v` da classe nova: `Ran 10 tests ... OK`.)

## NÃO VERIFICADO

- Origem da faixa de referência: `validacao_gerador_v1.14.md` não está no repositório, então não se sabe qual sessão gerou cada número dela. A coluna "bate?" compara contra a faixa por classe.
- Causa da diferença na 06 e na 20: não investigada (alinhamento por lag do sinal inteiro, fase ou o próprio gerador).
- Sessões com `sorteio_posicao` ligado (fase sorteada, janela rotulada menor): a função usa `fase_graus`, mas nenhuma sessão real com sorteio foi analisada; só o teste sintético da fase.
- Alinhamento quando o registro não tem margem (arquivo `sem_margem/`): o deslocamento por lag fica limitado ao registro e pode não ser aplicado por inteiro.

## 6. Correlação com a fundamental ajustada (v1.15, pendentes)

`sinais.correlacao_disturbio_fundamental_ajustada(esperado, capturado, *, fs_hz, f0_hz)` (`logica/sinais.py:520`), mesma assinatura de retorno `(valor | None, motivo | None)`.

- Em vez de subtrair dos dois sinais a mesma senoide de 1 pu, ajusta em CADA sinal, por mínimos quadrados na janela inteira, `a·sin + b·cos + c` em `f0_hz` (amplitude e fase livres, mais uma constante) e correlaciona (Pearson) o que sobra (`_residuo_sem_fundamental`, `sinais.py:509`).
- Motivo: a fonte emite a fundamental 0,2–1,4 % acima ou abaixo do programado a 127 V (diagnóstico de 12/10, 09: razão medida/programada 1,0059–1,0138). A métrica nominal deixa essa diferença no resíduo capturado: na 09, de distúrbio rms 0,0235 pu, 1 % de erro de fundamental custa até 0,05–0,06. A ajustada é indiferente a erro de amplitude e de fase da fundamental e ao ganho do sinal inteiro. Teste: capturado = esperado + 0,01 · fundamental dá ajustada > 0,9999 e nominal < 0,99 (`PendentesCorrelacaoDisturbioTests`).
- Caso degenerado como na métrica nominal, com os mesmos limiares (`LIMITE_RESIDUO_DEGENERADO_PU`, 1e-6): resíduo esperado ~ 0 (01, e 19, em que só restam fundamental e constante) devolve `None` com motivo; resíduo capturado ~ 0 e formas incompatíveis também. Diferença: na 19 o motivo é "sem componente de distúrbio ou só offset DC" (a constante também é ajustada), não "resíduo constante".
- Ressalva: o ajuste usa a janela toda, então em distúrbios grandes ou que mexem na fundamental (02/03/04, 18) parte do evento é absorvida no ajuste, igualmente nos dois sinais. É um complemento da métrica nominal, não um substituto; leia as duas lado a lado.
- Onde aparece: `analisar_sessao.py` (chaves `correlacao_disturbio_fundamental_ajustada` e `..._motivo`; coluna `corr. dist. fund.aj.` no terminal, `:300-350`) e `relatorio_html.py` (linha "Correlação com o esperado": "distúrbio com a fundamental ajustada X", `_correlacoes` `:241`). Mesmo recorte e mesmo lag da métrica nominal (`_correlacao_disturbio_alinhada(..., fundamental_ajustada=True)`).
- Efeito esperado (cálculo sobre `gerar()` e TRACE, não medido na bancada): nas classes de distúrbio grande (05, 10–16) praticamente nenhum; na 09 e nas de distúrbio pequeno é onde o erro de fundamental pesa. Nas sessões de 07/10 a ajustada ainda não foi calculada (as sessões só existem no PC da bancada): **NÃO VERIFICADO** o ganho real por classe; a estimativa do diagnóstico (09: 0,911 → 0,932, 0,885 → 0,939, 0,750 → 0,800, 0,798 → 0,855) foi feita com a fundamental ajustada em ciclos médios, não com esta função.

## 7. Pendentes verificados no código (v1.15)

**05, nível de 30 % por TRACE.** O modelo desse nível é a soma 1 + 3.ª/5.ª/7.ª (fundamental 1 pu), de rms `sqrt((1+thd²)/2)` = 0,7382 pu, contra 0,7071 dos níveis ≤ 20 % (senoide clipada normalizada por rms, fundamental 0,98–1,00 pu). `montar_programacao` programa `LIST:VOLTage` com o rms CA do próprio ciclo do modelo e a TRACE escalada a ele, então a fonte emite o modelo: programada × modelo, correlação do distúrbio 1,00000 e diferença máxima 1,1e-4 pu, a 50 e 60 Hz; `LIST:VOLTage` = 1,044 × a tensão base (132,6 V a 127 V); pico reconstruído 148,2 V a 127 V (0,8252 pu). A incoerência é só ENTRE níveis (rms 4,4 % maior no de 30 %), não entre modelo e programada; normalizar o modelo ao rms de 1/√2 baixaria a fundamental a 0,958 pu (correlação do distúrbio modelo × normalizado 0,989) e mudaria o `gerar()` sem ganho. Decisão: não mudar. Cálculo de pico em outras tensões: 0,8252 pu · √2 · V rms; a 380 V dá 443,5 V, acima de 425 Vp, e o limite de bancada (`fator_disturbio_bancada`) é quem trataria; NÃO VERIFICADO em simulação de 380 V neste trabalho.

**09.** As ferramentas de `diag_ciclos_trace.py` e `modelo_lista_fonte.py` rodam numa 09 sorteada (metadata com `sorteio_posicao`) e acusam uma cópia sintética em 100 ms (resíduo máximo perto de 100 ms e hipótese de cópia primeiro em `confrontar`). Com o sorteio ligado, o instante de 100 ms cai dentro do evento rotulado em ~18 % das capturas (17,1 % a 60 Hz, 18,1 % a 50 Hz, 2000 sementes); em ~82 % a cópia cairia fora da janela rotulada, num trecho rotulado como normal. Recomendação para a campanha: ver `CHANGELOG/v1.15.md`, seção "Pendentes da correlação do distúrbio".

**06.** A perda da correlação da 06 na TRACE por ciclo vem inteira da média de cada ciclo, que a fonte remove (manual, `TRACe:DATA`). Com a média de cada ciclo tirada do modelo, programada × modelo vai a 0,9999–1,0000 em todas as 28 capturas calculadas. A média por ciclo da 06 é uma escada de rms 0,002–0,032 pu (até 0,044 pu de pico) contra distúrbio de rms 0,036–0,074 pu, e cresce com a frequência do flicker. Tabela e proposta em `CHANGELOG/v1.15.md`.
