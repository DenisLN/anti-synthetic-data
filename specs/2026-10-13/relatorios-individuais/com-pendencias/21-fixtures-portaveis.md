## Análise do orquestrador

- Implementação completa? Sim: tests/assinatura_portavel.py (tolerância 1e-9 pu sobre soma/energia/min/max/4 projeções + parâmetros), chave 'portavel' nos fixtures, SHA-256 exato mantido com skip fora do Windows; contra-provas conferidas no código (1e-8 em uma amostra é detectado).
- Pendências do usuário: rodar tests.test_offline no Windows (resumos portáveis gravados com arrays do Linux; SHA-256 exato precisa passar lá).
- Escopo limitado demais? Não.
- Resolve o contexto? Sim no Linux; NÃO VERIFICADO no Windows.
- Critério de Parada: atendido (após merge: 410 testes OK, 2 pulados).
- Classificação: com pendências (verificação no Windows).

---

# Relatório: Fixtures Byte a Byte Portáveis entre Plataformas

Branch: `worktree-agent-a2eb49ddc0bb03a00`. Commit: `c337e9b` (fix: fixtures de gerar() portáveis entre plataformas). Merge de `claude/specs-v1-15-review-3w2bgl` já estava incorporado (ancestral de HEAD, `d1afd33`).

## Missão, item a item

**Item 1 — Confirmar a causa: comparar, para as chaves divergentes, o array de `gerar()` contra um cálculo de referência e medir a maior diferença (em ULP e em pu); dizer quantas das 400 chaves divergem em cada fixture.**
- Status: PARCIAL
- Explicação: Medido (script `scratchpad/medir21.py`, referência = `np.sin`/`np.cos` trocados por `np.longdouble` arredondado a float64, sobre as 400 chaves de cada fixture). Divergem 400/400 no fixture literatura e 400/400 no de sorteio (800 de 800). Todos os 800 arrays diferem da referência: máximo 2,22e-16 pu (literatura: até 16 ULP relativos, nas amostras perto de zero; sorteio: até 4 ULP). Parâmetros idênticos entre nativo e referência. Desligar AVX512/AVX2/FMA3 via `NPY_DISABLE_CPU_FEATURES` não muda os hashes. A referência long double também NÃO reproduz os hashes do fixture (0/800), então a diferença para o Windows não é reconstituível aqui. A causa (último bit de `np.sin` por plataforma) é consistente com a medida (erro de 1 ULP em todos os arrays, parâmetros idênticos) mas NÃO CONFIRMADA: sem arrays do Windows para comparar.

**Item 2 — Propor e implementar uma assinatura portável que continue detectando qualquer mudança real de `gerar()` (por exemplo, hash dos valores arredondados a uma tolerância muito abaixo da resolução da fonte e do osciloscópio, mais os parâmetros), regravando os fixtures a partir dos mesmos arrays e mantendo a assinatura exata antiga como verificação adicional na plataforma de origem (pulada com `skipTest` e mensagem clara fora dela).**
- Status: CUMPRIDO (com desvio justificado)
- Explicação: Em vez de hash de valores arredondados, usei comparação por tolerância (a spec permite: "ex.: comparar por tolerância em vez de hash"). Hash de arredondados cai numa fronteira de arredondamento por acaso (estimativa: dezenas por cento de chance de algum dos ~4,8 milhões de valores cair na fronteira com tolerância 1e-9), mudando o hash inteiro; a tolerância não tem esse risco. `tests/assinatura_portavel.py`: resumo com `n`, parâmetros (`rtol=1e-9`), soma, energia, mínimo, máximo e 4 projeções (vetores `default_rng(1000+k)`), `TOL_ABS=1e-9` pu (~4 ordens acima da diferença medida, ~3 abaixo da resolução da fonte/osciloscópio). `tests/gravar_fixtures_portaveis.py` grava `portavel.resumos` (400 por fixture) nos dois JSON; `hashes` intactos. Os 4 testes que falhavam usam agora o resumo portável. Novos `AssinaturaPortavelTests.test_literatura_exato_na_plataforma_de_origem` e `test_sorteio_exato_na_plataforma_de_origem` mantêm o SHA-256 exato, com `skipTest` e mensagem clara fora do Windows (`ASD_HASH_EXATO=1` força). Limite do "mesmos arrays": só posso gravar a partir dos arrays do Linux (diferem no último bit dos do Windows); a tolerância cobre isso. NÃO VERIFICADO no Windows.

**Item 3 — Provar que a assinatura nova pega mudança real (contra-prova: perturbar um parâmetro ou uma amostra muda o hash) e que norma/fronteira continuam mudando exatamente as classes esperadas.**
- Status: CUMPRIDO
- Explicação: `AssinaturaPortavelTests` (fim de `tests/test_offline.py`): uma amostra mudada em ±1e-7 pu (45 posições x 4 classes), em 1e-8 pu (162 posições), forma deslocada/invertida/ganho 1e-7/offset 1e-7, parâmetro alterado/acrescentado/removido, tamanho diferente: todos pegos. Ruído de até 64 ULP em todas as amostras NÃO é pego (e o SHA-256 mudaria). Nenhuma classe é confundida com outra. Contra-prova ad hoc (`mut21.py`, 50 entradas): amplitude x(1+1e-7) detecta 47/50 (3 não investigadas), fase +1e-8 rad 50/50. `test_norma_e_fronteira_mudam_so_o_que_a_spec_manda` passa com a assinatura portável: os conjuntos esperados saem exatos.

**Item 4 — Documentar em `docs/testes.md` e `docs/versionamento.md` o que "reproduz byte a byte" significa por plataforma; registrar em `CHANGELOG/v1.15.md` (seção nova no fim).**
- Status: CUMPRIDO
- Explicação: `docs/testes.md` (seção Fixtures e mapa), `docs/versionamento.md` §2.1 (garantia entre plataformas por tolerância; bit a bit só na origem; NÃO VERIFICADO no Windows), `CHANGELOG/v1.15.md` seção nova no fim com Por quê / Medido / O que mudou / O que não mudou / Testes / NÃO VERIFICADO.

## Critério de Parada
Atendido. `TMPDIR=/tmp/claude-0/tmpt /tmp/claude-0/venv/bin/python -m unittest tests.test_offline` -> `Ran 388 tests ... OK (skipped=2)` (os 2 SHA-256 exatos). Com `ASD_HASH_EXATO=1` os 2 exatos falham no Linux, como esperado. Contra-prova em teste; documentação diz o que vale em cada plataforma.

## Pendências que exigem o usuário
Rodar `python -m unittest tests.test_offline` no Windows da bancada para confirmar que (a) os resumos portáveis gravados no Linux passam lá e (b) os 2 SHA-256 exatos continuam OK. Se (a) falhar, a causa não é só o último bit de `np.sin`.

## Limitações de escopo
Sem acesso a arrays do Windows: a causa não pôde ser confirmada e o `portavel` foi gravado só com arrays do Linux. `gerar()` não foi tocado, conforme o limite.

## A missão resolve o contexto?
Sim, parcialmente: a suíte passa inteira no Linux e a promessa de reprodução fica definida por plataforma, mas a validade no Windows e a causa exata continuam NÃO VERIFICADAS até uma rodada lá.

## Achados
- (média) Todos os 800 arrays do Linux diferem da referência long double; a causa raiz é só hipótese. NÃO VERIFICADO.
- (baixa) Contra-prova de amplitude pega 47/50 entradas; as 3 restantes não foram investigadas (provavelmente entradas sem `np.sin` relevante). NÃO VERIFICADO.
- (baixa) Se alguma classe tiver ramo discreto dependente do último bit de `sin`, o teste portável falharia visivelmente numa plataforma; não encontrado aqui.
- (baixa) A ordem das chaves dos JSON mudou (`numpy` antes de `hashes`); `hashes` idênticos.
- (baixa) `docs/testes.md` linha 3 ainda diz "370 testes"; não atualizei (outras specs mexem no mesmo arquivo); agora são 388.
- (info) Sugestão: gravar `portavel` também a partir do Windows e comparar os dois conjuntos, para medir a diferença real entre plataformas.
