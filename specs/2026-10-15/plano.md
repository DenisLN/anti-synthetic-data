# Plano de despacho: rodada "ASD Docs" (2026-10-15)

Objetivo da rodada: publicar no Read the Docs um site de documentação profissional do projeto `anti-synthetic-data`, em que uma pessoa que só leia a documentação entenda todas as intricâncias do código, com ficha completa das 20 classes, referência SCPI comando a comando, correlação esperada por classe, recalibração passo a passo, guia do código e pendências por classe.

Decisões do usuário nesta rodada:
- Usar como fonte de análise **apenas a mais recente** (`sessao-13-10-2026/` e `specs/2026-10-13/` neste branch, mais `CHANGELOG/v1.15.md` e o código atual). As análises de 21/09, 30/09 e 12/10 já foram revisadas.
- Executores: sonnet com esforço **high**.
- Executar **uma spec por vez**, em sequência, com julgamento do orquestrador entre elas.
- Documentar a atividade e as specs neste branch (`arquivo/analises`, pasta `specs/2026-10-15/`).

## Ambiente

| Item | Valor |
|---|---|
| Código-base | `main` em `fa82f49` (v1.15 em andamento, sem tag; fast-forward a partir do remote `github` em 2026-10-15) |
| Worktree do site | `C:\Users\denis\Documents\1 Projetos\asd-docs-site`, branch `docs/site-readthedocs` (criado de `main`) |
| Worktree deste arquivo | `C:\Users\denis\Documents\1 Projetos\asd-analises`, branch `arquivo/analises` (rastreia `github/arquivo/analises`) |
| Fora da `main` | `feat/passo-final-sin` (SINE, PR #3) e a análise de 13 a 15/10 estão **sem validação na bancada** |
| Estilo | documentos de referência do usuário em `C:\Users\denis\Downloads\tcc\01` e `\02` |

## Ordem de execução

Grafo de dependências (`Depende de:` das specs) e `pri`:

| Onda | pri | Spec | Depende de | Escreve em |
|---|---|---|---|---|
| 1 | 06 | ASD Docs: Auditoria, Lacunas e Arquitetura do Site de Documentação | nada | `docs-site-plano/` (worktree do site) |
| 2 | 07 | ASD Docs: Site no Read the Docs e Páginas Transversais (SCPI, Correlação, Recalibração, Pendências) | 06 | `docs/`, `.readthedocs.yaml`, `CHANGELOG/v1.15.md` (worktree do site) |
| 3 | 08 | ASD Docs: Fichas das 20 Classes e Revisão Final do Site | 07 | `docs/classes/`, `docs/classes.md`, `README.md`, `AGENTS.md`, `CHANGELOG/v1.15.md` (worktree do site) |

- **Primeira spec:** 06. **Última spec:** 08. O caminho crítico é a cadeia inteira (06 → 07 → 08); não há paralelismo possível, porque cada spec escreve nos mesmos arquivos e usa a saída da anterior.
- Cada spec roda com um único executor (sonnet, esforço high), um de cada vez.
- Relatórios dos executores entram em `_recebidos/` e, depois do julgamento, vão para `sem-pendencias/` ou `com-pendencias/`.

## Registro

O estado de cada spec fica no log do painel ("Despacho de Specs") e no `relatorio-final.md` desta pasta. Nenhum commit, push ou merge de código do projeto é feito pelo orquestrador; os executores commitam apenas no branch `docs/site-readthedocs`, como as specs permitem.
