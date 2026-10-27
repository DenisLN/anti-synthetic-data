# Plano da rodada "Fork na main e docs no RTD" (2026-10-27)

Pedido do dono (2026-10-27): trazer para a `main` tudo o que o Ricardo fez no fork `rmlinxic/anti-synthetic-data`, descontinuar os outros branches, unificar a documentação no Read the Docs, listar lá as 31 pendências e como foram resolvidas, integrar o rastreador de pendências ao site, mover os scripts de diagnóstico de `scripts/` para `diag/` com a visita à bancada rodando de lá, e atualizar a documentação dos `NN.py` alterados.

Entrada de análise: `findings-pendencias-v1-15-detalhado.md` (nesta pasta), relatório que conferiu P-01 a P-31 contra as evidências do fork (HEAD `cd1e6a9`).

## Ordem

Cadeia única: as specs mexem nos mesmos arquivos de `docs/`, e rodá-las em paralelo geraria conflito.

| pri | Spec | Depende de | Escreve em |
|---|---|---|---|
| 30 | ASD: Fork na Main e Branches Descontinuadas | nada | git (main, tags `arquivo/*`, branches remotos, PR #3), `AGENTS.md`, `CLAUDE.md`, `CHANGELOG/v1.15.md` |
| 31 | ASD: Scripts de Diagnóstico em diag/ e Visita Rodando de Lá | 30 | `scripts/`, `diag/`, `logica/mestre.py:128`, `tests/`, referências em `docs/` |
| 32 | ASD: Documentação Unificada no Read the Docs | 31 | `README.md`, `AGENTS.md`, `CLAUDE.md`, `ROTEIRO_BANCADA.md` → `docs/`, `mapa/` (sai), `docs/` (exceto classes e pendências) |
| 33 | ASD: Rastreador de Pendências Integrado ao Read the Docs | 32 | arquivo de estado único, `docs/_ext/`, `docs/projeto/pendencias.md`, `scripts/` de pendências, teste |
| 34 | ASD: Página de Pendências com Estado e Resolução de P-01 a P-31 | 33 | arquivo de estado, `docs/projeto/`, `docs/index.md` |
| 35 | ASD: Fichas das Classes Atualizadas com as Mudanças nos NN.py | 34 | `docs/classes/`, `docs/metadata.md`, `docs/classes.md`, `docs/codigo/classes_contrato.md` |

## Ações que só o dono faz

- Painel do Read the Docs: tornar `latest` (da `main`) a versão padrão e desativar `docs-site-readthedocs` depois da spec 30.
- Decisões de pendência que a spec 34 vai listar (P-09, P-18, P-20, P-23, P-31, P-25 item a item, confirmação das escolhas do fork).
- Rodar a suíte no PC da bancada no HEAD novo (P-16).

`arquivo/analises` continua existindo: é o arquivo histórico e guarda estas specs.
