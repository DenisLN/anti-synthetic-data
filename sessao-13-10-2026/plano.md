# Plano da rodada 13/10/2026

Executores: haiku em 10, 13, 22; sonnet nas demais. Máx. 3 em paralelo, um worktree por spec; o orquestrador mescla no branch claude/specs-v1-15-review-3w2bgl depois de cada onda.

- Onda 1: 11 (sonnet), 12 (sonnet), 10 (haiku)
- Onda 2: 13 (haiku), 14 (sonnet), 21 (sonnet)
- Onda 3: 15 (sonnet, dep 11), 19 (sonnet), 20 (sonnet, dep 11)
- Onda 4: 16 (sonnet, dep 10), 17 (sonnet, dep 11 e 14), 18 (sonnet, dep 11 e 15)
- Onda 5: 22 (haiku, dep 10, 12, 17)
- Onda 6: 23 (sonnet, dep 18, 19, 20, 22)

Primeira: 11/12/10. Última: 23. Caminho crítico: 11 -> 15 -> 18 -> 23 e 11/14 -> 17 -> 22 -> 23.
Linha de base da suíte (Linux): 370 testes, 4 falhas conhecidas de fixture (spec 21).
