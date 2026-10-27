# Protocolo para agentes: pendências P-01–P-31

Esta página não guarda estado. O estado das 31 pendências vive em **um** arquivo, `docs/estado_prontidao.json`, e o site o renderiza (placar, matriz e uma seção por P-NN com âncora `estado-p-NN`) em {doc}`projeto/pendencias`. Formato do arquivo e fluxo de atualização: {doc}`contribuir_docs`. Narrativa e critérios: {doc}`execucao_pendencias`. Visita à bancada: {doc}`bancada_pendencias`. Decisões do responsável: {doc}`decisoes_pendentes`.

## Protocolo para agentes (economia de contexto)

0. Entrada do mapa: `mapa/00 Início.md` (vault Obsidian; cartões de módulo, notas P-NN, `Pendencias.base`, `Mapa.canvas`). Após mudar estados em `docs/estado_prontidao.json`, rode `python scripts/gerar_mapa_pendencias.py`.
1. Leia **só** o bloco da sua pendência em `docs/estado_prontidao.json` (ou a seção dela em `docs/projeto/pendencias.md`) e os arquivos citados na linha da sua pendência. Não leia `docs/roteiro-bancada.md`, `AGENTS.md` ou `execucao_pendencias.md` inteiros; use `grep -n` para a seção necessária.
2. Limites inegociáveis: `AGENTS.md` seção "Limites inegociáveis" (COM10/115200, limites RMS/pico/corrente, confirmação digitada para energizar, validações SCPI, `gerar()`/fixtures intocados).
3. Escopo de arquivos por frente (abaixo). Não editar arquivos de outra frente; `docs/estado_prontidao.json`, `execucao_pendencias.md` e `CHANGELOG/v1.15.md` são editados **só pelo coordenador**. Agentes devolvem um trecho de CHANGELOG pronto no relatório.
4. Relatório final do agente: ≤25 linhas — arquivos alterados, comando de teste e resultado, P-NN afetados, o que NÃO foi verificado.
5. Nenhum agente encerra pendência física. Simulação ≠ medição.

## Frentes

| Frente | Escopo de arquivos | Pendências |
|---|---|---|
| **K** kit de bancada | `scripts/fechar_pendencias.py`, `scripts/validar_pc_bancada.ps1`, `tests/test_pendencias_fechamento.py` | ferramentas para P-01–P-08, P-10, P-16–P-19, P-21–P-23, P-28, P-31 |
| **R** roteiro de fechamento | `docs/bancada_pendencias.md` | sequência única de visita à bancada |
| **D** decisões e fontes | `docs/decisoes_pendentes.md` | P-09, P-18, P-20, P-23, P-26, P-29, P-30, P-31 |
| **C** coordenador | `estado_prontidao.json`, `execucao_pendencias.md`, CHANGELOG, commits | integração |

## Depois da coleta

1. `python scripts/fechar_pendencias.py --sessao <dir> ... --saida docs/evidencias/<data>/fechamento.json` (gera evidência, não decide).
2. Edite o bloco de cada P-NN afetada em `docs/estado_prontidao.json` (estado, `falta`, `falta_por_tipo`, `como_tratada`, `commits`, `evidencias`, `decisao_dono` com `situacao`).
3. `python scripts/gerar_mapa_pendencias.py` (regenera `mapa/pendencias/`), `python -m unittest tests.test_estado_pendencias` e o build `sphinx-build -W -n --keep-going -b html docs docs/_build/html`.
