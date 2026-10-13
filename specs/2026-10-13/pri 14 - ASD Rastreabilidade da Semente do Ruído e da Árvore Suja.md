#spec #pri 14

# ASD: Rastreabilidade da Semente do Ruído e da Árvore Suja

## Contexto

Pergunta do usuário: "a seed do ruído é gravada nos metadados?" Hoje não diretamente: o metadata grava a `seed` da captura e o ruído usa `semente_do_ruido(seed, snr) = seed + round(snr·1000) + 50 000 000` (`logica/sinais.py:171`), mas nem a semente de cada nível nem a fórmula aparecem em `ruido_janela` (`sinais.py:262-275`).

Pendências de rastreabilidade do relatório de documentação: `git_sujo` ignora arquivos novos não rastreados e é calculado uma vez por processo (`logica/mestre.py`, `info_do_codigo`); com `set recalibracao on`, `calibracao_extremos.json` muda depois do primeiro run sem a CLI notar. `sessao.json` não registra o perfil.

## Entradas

- `logica/sinais.py` (`semente_do_ruido`, `ruido_na_janela`), `logica/mestre.py` (`info_do_codigo`, `preparar_pasta_da_sessao`, gravação de `sessao.json`), `scripts/gerar_ruido_janela.py`
- `docs/metadata.md` (só acrescentar campos)
- Depende de: nada

## Missão

1. Gravar em `ruido_janela` a semente de cada nível (`sementes_por_snr_db`) e um identificador da fórmula, no caminho de bancada, no simulado e no script offline.
2. Fazer `git_sujo` considerar também arquivos não rastreados dentro de `logica/`, `experimentos_nativos/`, `experimentos_waveform/` e `scripts/`, e recalcular a procedência a cada `run` da CLI (não uma vez por processo), mantendo o aviso em destaque sem bloquear.
3. Registrar em `sessao.json` os perfis usados nos runs da sessão.
4. Documentar os campos em `docs/metadata.md` e registrar em `CHANGELOG/v1.15.md`.

## Limites

- Não mudar a fórmula da semente nem o ruído gerado (os mesmos vetores para a mesma seed).
- Só acrescentar campos ao metadata, sem renomear nem remover.
- Não tocar no hardware.

## Entregável

- Relatório por item.
- Verificação: `python -m unittest tests.test_offline` (testes: semente gravada reproduz o vetor; arquivo não rastreado em `logica/` acende `git_sujo`; recalcula entre runs).

## Critério de Parada

Os testes novos passam; `ruido_janela.sementes_por_snr_db` aparece numa sessão simulada; suíte sem falha nova.
