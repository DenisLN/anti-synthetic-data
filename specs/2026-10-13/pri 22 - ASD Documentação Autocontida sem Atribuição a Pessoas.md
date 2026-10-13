#spec #pri 22

# ASD: Documentação Autocontida sem Atribuição a Pessoas

## Contexto

Prioridade máxima do usuário (2026-10-13): "retirar qualquer referência a professor, dono, .tex. A documentação deve ser autocontida, e decisões 'de alguém' são decisões de projeto; potencialmente justificando aquelas que são provenientes, por exemplo, de bugs, mas não precisando de justificativa aquelas que mudam a arquitetura do projeto."

Levantamento (`git grep -il "professor\|atividade\.tex\|\bdono\b"`): `docs/correlacao_disturbio.md`, `docs/decisoes.md`, `docs/estender.md`, `docs/limites_e_calibracao.md`, `docs/tres_versoes.md`, `docs/versionamento.md`, `CHANGELOG/v1.15.md` (em andamento), comentários e docstrings em `logica/mestre.py`, `logica/cli.py`, `logica/sinais.py`, `logica/perfis.py`, `logica/calibracao_extremos.json`, `scripts/recalibrar_extremos.py`, `scripts/start_bench_windows.ps1`, `experimentos_nativos/04.py`, `19.py`, `experimentos_waveform/06.py`, `07.py`, `08.py`, `09.py`, `17.py`, `20.py`, `tests/test_offline.py`. Também ficaram de pé: a documentação de HTML e recalibração está espalhada; `.env.example` diz `SNR_LEVELS_DB=30` (padrão é `20,30,40`); rótulos "v1.16" em `logica/sinais.py`, `scripts/gerar_tres_versoes.py`, `tests/test_offline.py`; `AGENTS.md` não registra as autorizações de 2026-10-12 para compostas, 08 e 05/07/17/18 (estavam no enunciado das specs originais) nem as de 2026-10-13.

`AGENTS.md` é instrução para agentes, não documentação do projeto: a governança (autorizações) continua lá, mas sem referências ao `.tex` ou a "professor".

## Entradas

- Todos os `.md` de `docs/`, `README.md`, `CHANGELOG/v1.15.md`, `AGENTS.md`, `.env.example`, os arquivos de código listados acima
- Depende de: ASD: Análises Fora de docs e Arquivo em Branch Separado; ASD: Um NPZ Comprimido por Classe com Perfis e Versões; ASD: Preflight Único na Tensão Base com ENERGIZAR-TESTE

## Missão

1. Reescrever as passagens que citam professor, dono ou `.tex` em `docs/`, `README.md` e `CHANGELOG/v1.15.md` como decisões de projeto: justificar as que vieram de defeito/medida (com a evidência técnica) e só enunciar as de arquitetura.
2. Fazer o mesmo nos comentários, docstrings, mensagens e strings de log do código e dos testes, sem mudar comportamento (nomes de testes podem mudar).
3. Consolidar em `docs/operacao.md` uma seção única "Relatório HTML e recalibração ao fim do run" (quando ligar, o que gera, onde fica, custo, como reverter a recalibração, linha de comando equivalente), e fazer os outros docs apontarem para ela.
4. Corrigir `.env.example` (SNR) e os rótulos "v1.16" para v1.15; registrar em `AGENTS.md` as autorizações de 2026-10-12 (compostas, 08, 05/07/17/18) e as de 2026-10-13 desta rodada, sem citar `.tex`/professor.
5. Conferir que nenhum `.md` ficou com link quebrado e que nenhum fato de comportamento ficou sem `arquivo:linha` conferido.

## Limites

- `CHANGELOG/vX.Y.md` fechados (v1.0–v1.14) não se reescrevem; registrar no relatório quantas menções ficam neles.
- Não mudar comportamento do código; a suíte tem de dar o mesmo resultado.
- Não mexer nos limites de segurança nem nas confirmações digitadas.

## Entregável

- Relatório por item, com o `git grep` antes/depois.
- Verificação: `git grep -il "professor\|atividade\.tex\|\bdono\b" -- . ':!CHANGELOG/v1.[0-9].md' ':!CHANGELOG/v1.1[0-4].md' ':!AGENTS.md'` vazio; `python -m unittest tests.test_offline`.

## Critério de Parada

O `git grep` acima não acha nada; a seção de HTML/recalibração existe e é referenciada; `.env.example` e rótulos corrigidos; `AGENTS.md` com as autorizações; suíte sem falha nova.
