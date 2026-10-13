# Metadata legível e rastreável: o que mudou (2026-10-12)

Formato campo a campo: `docs/metadata.md`. Nada foi commitado; nenhum hardware tocado (`BENCH_MODE=0`).

## 1. Metadata legível

- Mantido o `.jsonl` (máquina) e gravado ao lado `NN_classe.json` indentado, derivado dele:
  `_gravar_metadata_legivel` (`logica/mestre.py:156`), chamado em `_finalizar_gravacao` (`mestre.py:1979`, caminho físico, também quando a classe é interrompida) e em `_salvar_classe_simulada` (`mestre.py:2068`).
- Por que não trocar o formato: ver `docs/metadata.md` (4 leitores e as sessões de 07/10 dependem do `.jsonl`).
- Sessões antigas: `recortar_margem` roda sobre `sessao_2026-10-07_127V_50Hz` (saída abaixo); teste `test_leitores_continuam_lendo_sessao_antiga_de_uma_linha`.

## 2. `inicio_janela`

- `ExperimentoBase._inicio_janela_para_metadata` (`mestre.py:1392`), chamado em `mestre.py:2214` para toda captura física com `indice_trigger`. Reusa `sinais.janela_nominal` (mesma função do recorte), então a conta é idêntica por construção, inclusive o limite `[0, n - pontos]`. Grava também `inicio_janela_ajustado`.
- Leitores: `recortar_margem.py:90-94` (nova origem `inicio_janela`, antes de `indice_trigger`), `analisar_sessao.py:237-240`. `relatorio_html.py` não mudou: usa `calcular_recorte`. `metadado_recortado` zera `inicio_janela` no `sem_margem/` (`recortar_margem.py:139-142`).
- `scripts/recalibrar_extremos.py` não usa posição de janela; não alterei.
- Testes: `test_inicio_janela_segue_a_formula_do_recorte` (2500 -> 700), `test_inicio_janela_respeita_o_limite_do_registro` (3500 -> 1200, ajustado), `test_leitores_preferem_inicio_janela`, `test_analisar_sessao_usa_inicio_janela` (com `indice_trigger` inconsistente de propósito).

## 3. Cópia da calibração

- `preparar_pasta_da_sessao` (`mestre.py:175`): uma vez por processo e pasta, copia `CALIBRACAO_EXTREMOS_PATH` para `calibracao_extremos.json` na pasta da sessão e grava `sessao.json` com `origem`, `copia_na_sessao` e `sha256`. Chamada no início de cada `run` pela CLI (`cli.py:179`) e, por segurança, ao abrir a gravação (`mestre.py:1879`, `2028`).
- Cada captura física repete `calibracao_extremos_sha256` (`mestre.py:1373` e vizinhas).
- Verificado: o `sha256sum` da cópia da sessão simulada é igual ao de `logica/calibracao_extremos.json` (`af4bf8ac...e138`).
- Não verificado nem alterado: `recalibrar_extremos.py` ainda lê só o `.jsonl`; não compara com a cópia da calibração (ver Sugestões).

## 4. Procedência e árvore suja

- `info_do_codigo` (`mestre.py:116`): `git rev-parse HEAD`, `git_sujo`, `versao_codigo`, `numpy_versao`, `python_versao`; gravados em `sessao.json`.
- Aviso em destaque, sem bloquear, quando `modo == bancada` e `git_sujo` (`mestre.py`, fim de `preparar_pasta_da_sessao`); não existe mecanismo de bloqueio no fluxo.
- Limitação (média): `git_sujo` ignora arquivos não rastreados (critério do `-dirty`). Um experimento novo ainda não adicionado ao git não acende o aviso.
- Teste do aviso com `git_sujo` simulado: `test_arvore_suja_em_bancada_avisa_em_destaque_sem_bloquear`. NÃO VERIFICADO na bancada real (sem hardware nesta tarefa).

## 5. Testes e verificação

Novos: classe `MetadataLegivelERastreavelTests` (11 testes, `tests/test_offline.py:4697`).

```
> .\env\Scripts\python.exe -m unittest tests.test_offline
Ran 251 tests in 9.264s
OK
```
(antes: 240 testes, OK)

```
> .\env\Scripts\python.exe logica\recortar_margem.py resultados\sessao_2026-10-07_127V_50Hz
arquivo                                                                origem  início    fim  desloc. (ms)
01_normal_cap01.npz                                            indice_trigger     595   6595         -0.17
02_sag_sag_pu-0.1.npz                                          indice_trigger     605   6605          0.17
...
Recortado em: resultados\sessao_2026-10-07_127V_50Hz\sem_margem
```
(72 linhas com `origem = indice_trigger`; nenhum aviso. Efeito colateral: criou `resultados\sessao_2026-10-07_127V_50Hz\sem_margem\` (npz recortados, `snr_30db/`, `metadata/*.jsonl`); nada existente foi alterado ou apagado; `resultados/` está no `.gitignore`.)

Sessão simulada (`run all` via `cli.SessaoCLI.loop` com `input` simulado, `BENCH_MODE=0`, `SIM_CAPTURES_PER_CLASS=3`, `mestre.RESULTS_DIR` redirecionado): 20/20 OK em
`C:\Users\denis\AppData\Local\Temp\claude\C--Users-denis-Documents-1-Projetos-anti-synthetic-data\2fd9015d-15c8-40f8-a5f9-a614736fca29\scratchpad\sim_resultados\sessao_2026-10-12_13-50-29`.
`sessao.json` gerado:

```json
{"calibracao_extremos": {"copia_na_sessao": "calibracao_extremos.json", "sha256": "af4bf8acbfd5a557f1d5c68b23ca63a307ded2bd93fcd30f55cdace5deb2e138", "origem": "...\\logica\\calibracao_extremos.json"},
 "criada_em": "2026-10-12T13:50:29-0300", "formato_metadata": 2,
 "git_commit": "34a0d820a12b035a84c438baf52b756dacf77b41", "git_sujo": true, "modo": "simulado",
 "numpy_versao": "2.4.6", "python_versao": "3.11.9", "versao_codigo": "34a0d82-dirty"}
```
(`git_sujo: true` porque as edições desta tarefa não estão commitadas.) A sessão simulada não tem `inicio_janela` (só físicas); a cobertura é por teste.

## Achados (gravidade)

- Baixa: classe interrompida por queda do processo (sem exceção tratada) deixa só `.jsonl.part`, sem `.json`.
- Baixa: execução fora da CLI (`mestre.py` direto, sem `SESSION_RESULTS_DIR`) grava `sessao.json` e a cópia da calibração em `resultados/` raiz, sobrescrevendo na primeira captura de cada processo.
- Baixa: `sem_margem/metadata` continua só `.jsonl` (sem `.json` legível).
- Baixa: os testes que criam `SessaoCLI` com `BENCH_MODE` ligado imprimem o banner de árvore suja enquanto a árvore estiver suja (ruído de console, sem falha).
- Sugestão (fora de escopo): `recalibrar_extremos.py` poderia comparar o `sha256` do metadata com a calibração atual e avisar quando divergirem (pergunta 11 do professor); `git_sujo` poderia contar arquivos não rastreados dentro de `logica/` e `experimentos_*`.
