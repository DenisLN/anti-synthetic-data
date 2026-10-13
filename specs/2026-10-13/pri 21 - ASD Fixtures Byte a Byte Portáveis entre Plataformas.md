#spec #pri 21

# ASD: Fixtures Byte a Byte Portáveis entre Plataformas

## Contexto

No container Linux (Python 3.13, numpy 2.4.6, o mesmo da `requirements.txt`) 4 testes falham e 366 passam:

- `PerfisDeFaixasTests.test_literatura_reproduz_byte_a_byte_o_gerar_do_commit_34a0d82` (primeira divergência: `01/50/1234567/0`)
- `PerfisDeFaixasTests.test_norma_e_fronteira_mudam_so_o_que_a_spec_manda`
- `Classes05_07_18Tests.test_05_07_17_18_sem_sorteio_reproduzem_34a0d82`
- `SorteioInicioDuracaoFaseTests.test_resultado_congelado_da_v1_15`

No Windows da bancada os relatórios de 12/10 dão 370 OK. Hipótese: as assinaturas SHA-256 dependem do último bit de `np.sin` (implementação SIMD/libm diferente por plataforma). Se for isso, a promessa de reprodução byte a byte do dataset só vale numa plataforma, o que pesa para o arquivamento com DOI.

## Entradas

- `tests/test_offline.py` (`PerfisDeFaixasTests._assinatura`, testes acima), `tests/fixtures/gerar_literatura_34a0d82.json`, `tests/fixtures/gerar_sorteio_v1_15.json`
- Ambiente local: `/tmp/claude-0/venv/bin/python -m unittest tests.test_offline`
- Depende de: nada

## Missão

1. Confirmar a causa: comparar, para as chaves divergentes, o array de `gerar()` contra um cálculo de referência e medir a maior diferença (em ULP e em pu); dizer quantas das 400 chaves divergem em cada fixture.
2. Propor e implementar uma assinatura portável que continue detectando qualquer mudança real de `gerar()` (por exemplo, hash dos valores arredondados a uma tolerância muito abaixo da resolução da fonte e do osciloscópio, mais os parâmetros), regravando os fixtures a partir dos **mesmos** arrays e mantendo a assinatura exata antiga como verificação adicional na plataforma de origem.
3. Provar que a assinatura nova pega mudança real (contra-prova: perturbar um parâmetro ou uma amostra muda o hash) e que norma/fronteira continuam mudando exatamente as classes esperadas.
4. Documentar em `docs/testes.md` e `docs/versionamento.md` o que "reproduz byte a byte" significa por plataforma.

## Limites

- Não mudar `gerar()`.
- Os fixtures novos têm de ser gerados do mesmo código que os antigos validam (conferir que a assinatura antiga passa na plataforma de origem; NÃO VERIFICADO aqui sem Windows).
- Não tocar no hardware.

## Entregável

- Relatório por item, com a medida do item 1.
- Verificação: `python -m unittest tests.test_offline` com 0 falhas no Linux.

## Critério de Parada

A suíte passa inteira no Linux; a contra-prova do item 3 está em teste; a documentação diz o que vale em cada plataforma.
