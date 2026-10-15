# Estado da rodada 13/10/2026 (CONCLUÍDA em 15/10; ver relatorio-final.md)

Branch de código: `claude/specs-v1-15-review-3w2bgl` (480 testes OK, 2 pulados = SHA-256 exatos, só no Windows).

## Feito e mesclado
Specs 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21 + adaptação dos scripts de diagnóstico ao `sessao_io` (24). Relatórios com a análise do orquestrador em `sem-pendencias/` e `com-pendencias/`.

## Interrompido (trabalho parcial em `wip/`, aplicar com `git apply` sobre o commit em `NN-base.txt`)
- 25 `set perfil todos` sem recapturas iguais: classes que não dependem do perfil capturadas uma vez; metadata dos três perfis aponta para o mesmo arquivo/índice/hash; `sessao_io` e HTML resolvem. Decisão do usuário: liberado.
- 26 Crista esperada da validação física = crista do modelo × fator de extremo calibrado (todas as classes), aceitando [crista×(1−tol), crista×fator×(1+tol)]. Motivo: com entalhes em todos os ciclos, o toque da fonte (~10 kHz) eleva a crista da 07/17 em 31–59 % (simulação da spec 20). Decisão do usuário: usar a calibração.

## Falta
- 22 Documentação autocontida (haiku).
- 23 Roteiro da bancada (incluir: rodar a 07 com `set recalibracao on`; 09 logo após a 08 com 6–9 capturas; diag_marcadores, diag_acdc_amplitude, recaptura da 08; `set diagnostico retrieve` numa captura isolada; rodar `tests.test_offline` no Windows).

## Decisões pendentes do usuário
- Extensões das compostas (spec 19): manter ou reverter.
- 06: comparar contra a programada ou mudar `gerar()` (média nula por ciclo).
- Resto da média por ciclo nas classes 10/11/12/16 (spec 11): só compensável com offset por passo (ACDC).
- `run 01 02` (sem vírgula) roda só a 01; `BATERIA_EXCLUIR` não vale para listas (spec 13).
- `recuperar_parcial` automático no início do `run` (spec 17).
