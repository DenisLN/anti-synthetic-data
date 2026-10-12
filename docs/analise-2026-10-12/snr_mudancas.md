# Ruído de 20, 30 e 40 dB na janela recortada: o que mudou (2026-10-12)

Nada foi commitado; nenhum hardware tocado. Linhas de código são da árvore de trabalho de hoje. A versão sem ruído acrescentado (`.npz` limpo, com margens) não mudou. Temporários (sessão simulada, execuções de apoio, `TEMP` dos testes) ficaram no scratchpad `...\scratchpad\spec11\`.

Uma frase sobre o pedido: o rótulo "40 dB" é o SNR **acrescentado**; a bancada sozinha já está em 32 a 42 dB (item 3), então o efetivo do nível de 40 dB fica em 31,7 a 37 dB nas sessões de 07/10. Segui o pedido; o `snr_efetivo_db` existe para isso.

## 1. Padrão 20, 30 e 40 dB

- `logica/mestre.py:296`: `SNR_LEVELS_DB = env_float_tuple("SNR_LEVELS_DB", (20.0, 30.0, 40.0))` (era `(30.0,)`).
- `scripts/bench_config.ps1:37`: `$env:SNR_LEVELS_DB = "20,30,40"`.
- `scripts/run_simulation_windows.ps1:3`: `[string]$SnrLevels = "20,30,40"`.
- `README.md` (tabela de variáveis) e `docs/metadata.md` (campos novos) atualizados.
- Verificação sem variável de ambiente: `sim.py` (scratchpad) apaga `SNR_LEVELS_DB` do ambiente, aponta `RESULTS_DIR` para o scratchpad e chama `mestre.main()` com 6 capturas por classe. Saída: `SNR default: (20.0, 30.0, 40.0)`, `Bateria concluída: 20/20 classes OK`, pasta com `snr_20db/`, `snr_30db/`, `snr_40db/`.
- NÃO VERIFICADO: executar `run_simulation_windows.ps1` e `START_BENCH.cmd` de fato (o primeiro escreve em `resultados\` e a regra de temporários proíbe; o segundo é bancada). Verifiquei o valor do padrão no código e no `mestre.main()`.

## 2. Ruído só na janela, margens e seed

Código novo em `logica/sinais.py`: `semente_do_ruido` (`:171`), `ruido_na_janela` (`:224`); usado por `mestre.py` (`:2547-2556`) e pelo script offline, para a conta ter uma só definição.

- Janela = `registro[inicio_janela : inicio_janela + config.points]` (6000 amostras). `inicio_janela` vem do metadata da própria captura (`mestre.py:2547`); sem ele, `margem_amostras_antes`; no simulado, 0 (o registro já é a janela).
- Potência de referência = `mean(janela**2)`.
- Seed: `seed + round(snr*1000) + 50_000_000` (`sinais.py:171`), igual à de antes (`mestre.py` antigo, linha 2501). Teste `test_semente_mantem_a_formula_historica`.
- **Ruído de potência exata (decisão do coordenador, 2026-10-12).** `ruido_na_janela` sorteia `rng.normal(0, 1, 6000)` com a seed acima e escala o vetor para que `mean(ruido**2) = P_ref / 10^(SNR/10)` exatamente (`sinais.py`, laço de `ruido_na_janela`). Troca a estatística: antes a potência do ruído era `P_ref/10^(SNR/10)` só em esperança (o SNR medido variava com desvio-padrão ~0,077 dB e uma medida em 360 passou de 0,2 dB); agora é o nominal por construção, e o ruído deixa de ser i.i.d. estrito (a potência da amostra é fixa). A seed continua reproduzindo o mesmo vetor (formato idêntico ao sorteio de antes, só a escala muda). `ruido_awgn` (`sinais.py:149`) não foi alterada e deixou de ser usada pela bancada.

**Decisão sobre as margens: os arquivos com ruído (`snr_XXdb/`) têm só as 6000 amostras da janela, sem margem.** Justificativa:
1. É o que o professor pediu ("ruído aplicado só na janela recortada") e o que o dono quer rotulado (a janela nominal de 200 ms).
2. Margem sem ruído acrescentado ao lado de janela com ruído deixaria uma fronteira de nível de ruído nas amostras 600 e 6600, que um classificador aprende; margem com ruído contradiz o pedido.
3. As margens (20 ms antes, 50 ms depois) existem para alinhar pelo trigger e medir o ruído da bancada; ambos já estão no `.npz` limpo.
4. Compatível com os leitores: `recortar_margem.calcular_recorte` (`recortar_margem.py:87-89`) trata registro com `n <= pontos` como `sem_margem` e `relatorio_html` passa por ele (`relatorio_html.py:285`). NÃO VERIFICADO: rodar `relatorio_html --snr 30` num `snr_30db/` novo de sessão física (só li o código; os testes passam).
O eixo `tempo_ms` desses arquivos vai de 0 a 199,97 ms (`mestre.py:2212`). O metadata marca `ruido_janela.margens_com_ruido = false`.

No simulado nada muda além dos níveis: janela = registro inteiro, então a conta é a de antes. Consequência para sessões físicas antigas: o `snr_30db/` que já existe nelas (8100 amostras, ruído no registro inteiro) **não é igual** ao `ruido_janela/snr_30db/` novo (outra janela, outra referência, outro sorteio). O 30 dB antigo medido dentro da janela deu (comando `antigo.py`, scratchpad): 127V_50Hz min 29,53 / mediana 30,22 / max 30,54; run02 29,52 / 30,24 / 30,55; 230V_50Hz 30,00 / 30,27 / 30,55 dB; nas classes de margem em zero a mediana é 30,3 dB. Confirma o ~30,3 dB da spec.

## 3. Ruído próprio da bancada, SNR acrescentado e efetivo

**Método** (`sinais.py:177`, `:192`): potência do ruído pela segunda diferença `x[n] - 2x[n+1] + x[n+2]` (variância `6 sigma^2` para ruído branco), na margem **anterior** à janela (`registro[:inicio_janela]`, 595 a 605 amostras nas sessões de 07/10); se tiver menos de 100 amostras, na posterior; sem nenhuma, `null`. SNR da bancada = `10 log10(potência da janela / potência do ruído)`.

Por que não "a margem em zero": em 07/10 só as classes TRACe/LIST têm a margem anterior em zero (06, 07, 09 a 17, 20 e parte de 08/19); nas nativas (01 a 05, 18, parte de 08/19, e todas as de 02/03/04) a fonte já emite a senoide nessa margem (`explora.py`, rms da margem 0,70 pu). A segunda diferença serve aos dois casos (a senoide de 600 amostras/ciclo contribui ~1e-4 pu) e ignora o offset DC. Validação dos números (`explora2.py`, 127V_50Hz): em margem em zero, desvio-padrão 0,0119 / segunda diferença 0,0121 / ajuste por harmônicas 0,0118 pu; em margem com senoide, segunda diferença 0,0125 e ajuste de 9 harmônicas 0,0124 (classe 01). Nas 36 capturas de 127V_50Hz, 36 usaram a margem anterior; idem 36 e 27 nas outras (0 posteriores).

Convenção: o ruído da bancada exclui o offset DC (média da margem, gravada em `media_da_margem_pu`). A "margem em zero" da spec (rms incluindo o offset) dá 34,3 dB de mediana a 127 V e 38,2 a 230 V (`tab.py`, classes de margem quieta), próximo dos "≈ 34" e "≈ 37" da spec; a diferença para a tabela abaixo é o offset.

**Metadata** (`mestre.py:2551-2556`, `docs/metadata.md`): `snr_medido_db` (acrescentado, por nível, mesma chave de antes; agora igual ao nominal), `snr_bancada_db`, `snr_efetivo_db` (por nível; potências somadas: `sinal / (ruído da bancada + ruído acrescentado)`) e `ruido_janela`. No simulado `snr_bancada_db = null` e o efetivo é igual ao acrescentado.

**SNR da bancada nas sessões de 07/10** (dB, 1 valor por captura; os valores por captura estão em `<sessão>\ruido_janela\indice.json`):

| Sessão | Capturas | Bancada mín / mediana / máx | Ruído rms (pu) mín / mediana / máx | Efetivo @30 dB mín / mediana | Efetivo @40 dB mín / mediana |
|---|---|---|---|---|---|
| 127V_50Hz | 36 | 32,36 / 35,71 / 40,53 | 0,0067 / 0,0118 / 0,0143 | 28,01 / 28,97 | 31,67 / 34,33 |
| 230V_50Hz | 27 | 38,91 / 39,94 / 40,42 | 0,0068 / 0,0071 / 0,0077 | 29,47 / 29,58 | 36,41 / 36,96 |
| 14-59-54_run02 (60 Hz) | 36 | 32,42 / 40,50 / 42,59 | 0,0053 / 0,0067 / 0,0152 | 28,03 / 29,63 | 31,72 / 37,23 |

Efetivo @20 dB: 19,88 a 19,96 de mediana nas três (a bancada pesa pouco). Os mínimos da bancada (32 a 33 dB) ocorrem em 02/03/04/08 (janelas de potência menor: sag e interrupção reduzem a potência de referência) e em capturas com ruído de 0,012 a 0,015 pu; o ruído da bancada varia de 0,005 a 0,015 pu entre capturas (a 230 V é estável, 0,007).

Achados sobre a medição (gravidade entre parênteses):
- (média) A 127 V e no run02 o nível de 40 dB é dominado pela bancada: efetivo de 31,7 dB no pior caso. Não é erro, mas o rótulo "40 dB" não é o SNR do arquivo.
- (baixa) Na run02, a razão ruído(margem anterior)/ruído(margem posterior) chega a -5,04 dB numa captura (medianas -0,19, -0,27 e -0,29 dB; nas outras duas sessões os extremos ficam entre -1,5 e +1,4 dB). Por isso a margem posterior é só reserva: pode conter cauda do evento. NÃO VERIFICADO qual captura/qual causa (não investiguei).
- (baixa) O método supõe margem anterior sem evento. Nas sessões de 07/10 o pré-trigger é fixo e a margem anterior tem 595 a 605 amostras; com o pré-trigger sorteado da v1.15 o trigger acompanha o sorteio e a margem anterior continua sendo `margem_antes` (`mestre.py:2547-2550`). NÃO VERIFICADO em sessão física com sorteio (não existe ainda).
- (baixa) Metadata das sessões de 07/10 (`metadata\*.jsonl`) não ganhou os campos novos (originais intocados); eles estão em `ruido_janela\metadata\`.

## 4. Script offline e as sessões de 07/10

`scripts/gerar_ruido_janela.py`: lê o `.npz` limpo e o metadata, recorta a janela com `recortar_margem.calcular_recorte` (usa `inicio_janela`; sessões antigas caem em `indice_trigger`, `recortar_margem.py:90-99`), chama a mesma `ruido_na_janela` e grava em pasta nova:

```
<sessão>\ruido_janela\snr_20db\, snr_30db\, snr_40db\   (mesmo nome do .npz limpo; tensao_pu (1, 6000), tempo_ms)
<sessão>\ruido_janela\metadata\NN_classe.jsonl           (linha original recortada + snr_medido_db, snr_bancada_db, snr_efetivo_db, ruido_janela)
<sessão>\ruido_janela\indice.json                        (procedência e SNRs por captura)
```
Recusa uma pasta que já tenha arquivos (a menos que `--refazer`, e só se tiver `indice.json`). Níveis por `--snr 20,30,40` (padrão).

Comando e saída resumida (`env\Scripts\python scripts\gerar_ruido_janela.py resultados\<sessão>`; tabela completa por captura na saída do comando):

```
sessao_2026-10-07_127V_50Hz:   SNR da bancada: min 32.36 / mediana 35.71 / max 40.53 dB (36 capturas)
                               36 captura(s), níveis [20.0, 30.0, 40.0] dB, em resultados\sessao_2026-10-07_127V_50Hz\ruido_janela
sessao_2026-10-07_230V_50Hz:   SNR da bancada: min 38.91 / mediana 39.94 / max 40.42 dB (27 capturas)
sessao_2026-10-07_14-59-54_run02: SNR da bancada: min 32.42 / mediana 40.50 / max 42.59 dB (36 capturas)
```

Pastas criadas (cada `snr_XXdb/` com um `.npz` por captura, shape `(1, 6000)`): `resultados\sessao_2026-10-07_127V_50Hz\ruido_janela\` (36 por nível, 11 MB), `...230V_50Hz\ruido_janela\` (27 por nível, 7,8 MB), `...14-59-54_run02\ruido_janela\` (36 por nível, 11 MB). A 230 V só há 27 capturas: 02, 03, 04, 08 e 16 não rodaram nessa sessão.

Originais intocados: SHA-256 de todos os arquivos de cada sessão fora de `ruido_janela\` (incluindo `sem_margem\`, `snr_30db\` e `tres_versoes\` que já existiam), antes e depois da execução, são idênticos: `cmp` sem diferença em 226, 131 e 101 arquivos. Os `.zip` não foram tocados. As pastas `ruido_janela` foram regeneradas com `--refazer` após a normalização do ruído; a verificação de SHA-256 foi repetida depois dessa regeneração e continua idêntica.

## 5. Testes

`tests/test_offline.py`, classe `RuidoNaJanelaTests` (13 testes): padrão 20/30/40; fórmula da seed; seed reproduzível e distinta entre seeds; só a janela recebe ruído (6000 amostras) e o SNR medido na janela fica a 1e-6 dB do nominal em 120 sorteios; referência é a potência da janela; SNR da bancada em margem em zero e viva; offset DC não conta como ruído; margem posterior como reserva; efetivo = soma de potências; simulado sem bancada; sessão simulada (`executar()`) grava os três níveis (1e-6 dB); captura física (stub com margens, 8100 amostras) grava 6000 amostras com `snr_bancada_db`; script offline reproduz bit a bit a conta da bancada e recusa pasta existente.

`env\Scripts\python.exe -m unittest tests.test_offline -v` (com `TEMP` no scratchpad): `Ran 356 tests in 31.304s` / `OK` (343 antes, 13 novos).

**Critério "SNR medido na janela a ±0,2 dB": atendido por construção.** Com o ruído normalizado, a sessão simulada de teste regenerada (`sim.py` + `medsim.py`: 20 classes x 6 capturas x 3 níveis = 360 medidas, lidas direto dos `.npz`, sem o metadata) tem desvio máximo de 7,1e-15 dB (20 dB: -3,6e-15; 40 dB: -7,1e-15; 30 dB abaixo disso). Antes da normalização o pior era +0,220 dB. Os testes exigem 1e-6 dB em toda captura (a tolerância ±0,2 dB do critério, bem mais apertada); a captura física de teste também. Isso vale para o SNR acrescentado; o SNR efetivo continua limitado pela bancada (item 3).

## Arquivos

Alterados: `logica/mestre.py`, `logica/sinais.py`, `scripts/bench_config.ps1`, `scripts/run_simulation_windows.ps1`, `tests/test_offline.py`, `README.md`, `docs/metadata.md`. Criados: `scripts/gerar_ruido_janela.py`, este arquivo, e as três pastas `ruido_janela\` em `resultados\`. Nenhuma validação de IDN, timeout, tamanho de waveform, SCPI, `max_*` ou `gerar()` foi tocada.
