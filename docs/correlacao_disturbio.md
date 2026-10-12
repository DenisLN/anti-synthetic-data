# Correlação da componente de distúrbio

Data: 2026-10-12. Árvore NÃO commitada (v1.15 em andamento por cima de `34a0d82`).

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

| classe | 127 V/60 Hz | 127 V/50 Hz | 230 V/50 Hz | faixa do professor | bate? |
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

**08 e 05.** 05 = 0,50 nas três sessões, igual ao professor. 08 = 0,004–0,011 a 127 V/50 Hz, igual ao 0,005 do professor: nessas capturas o pico está na amostra 3000/2997 da janela e não na 2401 onde o modelo põe o pulso, razão de pico 0,18–0,29 (a transitória não foi registrada). A 127 V/60 Hz a 08 dá 0,82–0,83: o pico capturado cai em 2404/2401, perto do esperado, com melhor lag −1 amostra (script de apoio, não versionado: busca de lag ±40 amostras). Ou seja, o 0,005 do professor corresponde à sessão 127 V/50 Hz, e a sessão 127 V/60 Hz (mais nova, com os fatores da v1.14) capturou o pulso. [média: a métrica é sensível ao alinhamento de uma amostra em pulso de 2 amostras; o lag vem do sinal inteiro]

**Divergências (todas conferidas na tabela acima):**
- 06 (flicker): 0,83–0,96, abaixo da faixa 0,95–1,00 do professor em 7 de 9 capturas. [média]
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

- Quais sessões/capturas o professor usou: `validacao_gerador_v1.14.md` não está no repositório. A coluna "bate?" compara contra a faixa por classe, sem saber qual sessão gerou cada número dele.
- Causa da diferença na 06 e na 20: não investigada (alinhamento por lag do sinal inteiro, fase ou o próprio gerador).
- Sessões com `sorteio_posicao` ligado (fase sorteada, janela rotulada menor): a função usa `fase_graus`, mas nenhuma sessão real com sorteio foi analisada; só o teste sintético da fase.
- Alinhamento quando o registro não tem margem (arquivo `sem_margem/`): o deslocamento por lag fica limitado ao registro e pode não ser aplicado por inteiro.
