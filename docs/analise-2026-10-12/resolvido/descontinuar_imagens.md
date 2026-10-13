# Descontinuar o gerador de imagens (2026-10-12)

Decisão do dono: só `logica/relatorio_html.py` gera figuras. Nada foi commitado; hardware não tocado.

## 1. `visualizador.py` e `visualizar_npz.ps1`
Removidos (`git rm` não usado; aparecem como ` D` no `git status`). Recuperáveis pelo git.

## 2. `analisar_sessao.py`
Saíram `--sem-imagens`, o parâmetro `gerar_imagens`, `_salvar_imagem_comparacao`, o `import matplotlib` e a criação da pasta `analise/`. Mantidos intactos: `_reconstruir_esperado`, `_correlacao_disturbio_alinhada`, `analisar_offset`, `_ConfigOffline` e o relatório numérico (usados por `relatorio_html.py` e `scripts/gerar_tres_versoes.py`). Os 5 usos de `gerar_imagens=False` em `tests/test_offline.py` e o `--sem-imagens` em `docs/correlacao_disturbio.md` foram ajustados.

## 3. `comparar_visual.py` e `imagens/`
Não versionados, então copiados antes de apagar para fora do repositório (a spec permite): `C:\Users\denis\Documents\1 Projetos\asd-arquivo-descontinuado\2026-10-12\` (`comparar_visual.py` + `imagens\`). Conferência: 20 PNG na origem e no destino, 2.632.317 bytes nos dois, SHA-256 idêntico em todos os 20 e no `.py`. Só depois os originais foram apagados.

## 4. Referências restantes
`git grep -n -i "visualizador\|comparar_visual\|sem-imagens\|visualizar_npz\|gerar_imagens\|_salvar_imagem" -- . ':!CHANGELOG'` não acha nada em código, testes ou scripts. Restam, todas justificadas:

- `README.md:658` e `:690-691`: nota de descontinuação e a entrada histórica do CHANGELOG v1.4, ambas dizendo que foi descontinuado.
- `docs/analise-2026-09-21/propostas/p08_...patch`: patch datado, descreve o código da época.
- `docs/analise-2026-10-12/perfis_mudancas.md:19`: cita `comparar_visual.StubConfig`, relatório datado de hoje de outra spec (não reescrito).
- `docs/superpowers/plans/2026-09-11-...v18.md` e `specs/2026-09-11-...v18-design.md`: plano/spec históricos de v1.8.

`matplotlib` fica em `requirements.txt` (`matplotlib==3.11.2`): `grep` em `logica/` e `scripts/` só o acha em `relatorio_html.py`. `docs/analise-2026-09-21/figuras.py` é script avulso de análise datada, fora do código do projeto.

## 5. README e CHANGELOG
README: removidas as linhas de `visualizador.py`/`visualizar_npz.ps1` da árvore, seção "Para inspecionar visualmente" agora aponta para `set html on` / `relatorio_html.py`. `CHANGELOG/v1.15.md`: nova seção.

## Verificação
`.\env\Scripts\python.exe -m unittest tests.test_offline -v` (TEMP/TMP no scratchpad): `Ran 370 tests in 32.293s` / `OK`.

`analisar_sessao.py resultados\sessao_2026-10-07_127V_50Hz`: 36 linhas de arquivo com lag, correlação, corr. distúrbio e razão de pico (ex.: `02_sag_sag_pu-0.1  -0.03  1.000  0.999  1.036`); não cria `analise/`; `--help` só mostra `sessao_dir`.

`relatorio_html.py resultados\sessao_2026-10-07_127V_50Hz --classes 02,06 --saida <scratchpad>\rel.html`: "Relatório com 4 captura(s) ... (0.6 MB)", 15 figuras base64.

NÃO VERIFICADO: `set html on` dentro de uma sessão física real da CLI (só testes offline e a CLI do relatório); `scripts/package_windows.ps1` e `start_bench_windows.ps1` não foram lidos linha a linha, mas o `git grep` não acha os nomes removidos neles.
