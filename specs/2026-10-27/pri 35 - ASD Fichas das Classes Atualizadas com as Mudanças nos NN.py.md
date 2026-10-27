#spec #pri 35

# ASD: Fichas das Classes Atualizadas com as Mudanças nos NN.py

## Contexto

O dono notou que "muitos NN.py tiveram mudanças dentro deles" no fork e quer a documentação atualizada. Diff de `fa82f49` (main antes da integração) para `cd1e6a9` (fork), conferido em 2026-10-27 com `git diff --stat fa82f49 cd1e6a9 -- experimentos_nativos experimentos_waveform`:

| Arquivo | Mudança (leitura estática do relatório de achados, seção 5) | Altera `gerar()`? |
|---|---|---|
| `experimentos_nativos/05.py` (+4) | `rota_programacao` no metadata (CSIN ou TRACe por nível) | Não |
| `experimentos_nativos/18.py` (+10) | `exigencias_nativas` (gancho) | Não |
| `experimentos_nativos/19.py` (+12/−2) | `configurar` refatorado em `_offset_da_captura` | Não pelo diff; equivalência não verificada |
| `experimentos_waveform/06.py` (+28) | `forma_esperada_para_validacao` (compara com a programada reconstruída) | Não |
| `experimentos_waveform/08.py` (+28/−1) | métrica de sobressinal (`SOBRESSINAL_ACHADO_DE_SEGURANCA`) e validação alterada | Não pelo diff |
| `experimentos_waveform/15.py` (+29) | `parametros_com_disturbio_reduzido` (envelopes e THD central/mín./máx.) | Não pelo diff |

Também mudaram coisas fora dos `NN.py` que as fichas citam: `logica/sinais.py` (`distancia_modelo_programada`), `logica/calibracao_extremos.json` (fatores da 07 = 1,615 e 17 = 1,575 em `022bb5c`/`a22fba9`, recalibração 127 V/60 Hz em `13b9bdb`, 50 Hz em `aac725b`), e o passo final SINE (desligado por padrão). As fichas em `docs/classes/NN-*.md` têm selos de pendência desatualizados (achados, seção 4.3): `08-transient.md:8` e `05-harmonics.md:8` com `NÃO VERIFICADO`/`PENDENTE` de itens tratados; `PENDENTE P-11` nas classes 10 a 16 e `PENDENTE P-12` nas 06, 11 e 15, quando o que resta é validação física (P-01, P-08).

O problema a resolver: quem lê a ficha de uma classe no site precisa ver o que o código daquela classe faz hoje e o estado real das pendências dela.

## Entradas

- `experimentos_nativos/*.py`, `experimentos_waveform/*.py`, `logica/sinais.py`, `logica/calibracao_extremos.json`, `logica/mestre.py` (ganchos de bancada usados pelas classes)
- `docs/classes/*.md`, `docs/classes.md`, `docs/codigo/classes_contrato.md`, `docs/metadata.md` (campos novos de metadata: `rota_programacao`, sobressinal, parâmetros reduzidos da 15)
- Arquivo de estado das pendências e âncoras P-NN criados nas specs anteriores desta rodada
- `git diff fa82f49 main -- experimentos_nativos experimentos_waveform logica/sinais.py logica/calibracao_extremos.json`
- Teste byte a byte: `python -m unittest tests.test_offline.PerfisDeFaixasTests -v` e as fixtures em `tests/fixtures/`
- Depende de: ASD: Página de Pendências com Estado e Resolução de P-01 a P-31

## Missão

1. Refazer o diff completo dos `NN.py` entre `fa82f49` e a `main` (não confiar só na tabela do Contexto) e listar no relatório, por classe, cada mudança com `arquivo:linha` e se altera o que `gerar()` produz para uma seed (conferir com os testes byte a byte e as fixtures; para a 19, verificar a equivalência de `_offset_da_captura` com um teste ou comparação de saída).
2. Atualizar a ficha de cada classe alterada (05, 06, 08, 15, 18, 19, e qualquer outra que o item 1 encontrar) com o comportamento atual: ganchos novos, métricas novas (sobressinal da 08 e a ressalva de amostragem a 30 kSa/s), rota de programação da 05, parâmetros reduzidos da 15, comparação com a programada da 06.
3. Atualizar em todas as 20 fichas os selos e menções de pendência para que batam com o arquivo de estado (citando a âncora P-NN da página de pendências), e os fatores de extremo citados com o valor atual de `logica/calibracao_extremos.json`.
4. Acrescentar a `docs/metadata.md` os campos novos de metadata que as classes passaram a gravar (só acrescentar) e conferir `docs/classes.md` e `docs/codigo/classes_contrato.md` contra os ganchos novos.
5. Registrar em `CHANGELOG/v1.15.md`.

## Limites

- Não alterar nenhum `NN.py`, `logica/` nem fixtures: esta spec é só documentação. Se o item 1 achar mudança de `gerar()` não declarada, relatar como achado de gravidade alta e não corrigir.
- `docs/metadata.md`: só acrescentar campos.
- Selos de pendência seguem o arquivo de estado; não fechar pendência nas fichas.
- Todo fato sobre comportamento conferido no código (`arquivo:linha`); se o CHANGELOG divergir do código, vale o código.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.
- Se algum limite impedir ou restringir o resultado, registrar no relatório em "Limitações de escopo", sem ultrapassá-lo.

## Entregável

- Relatório `.md` no caminho que o despacho indicar, com: um bloco por item da Missão (copiar o texto do item, dizer CUMPRIDO, PARCIAL, NÃO CUMPRIDO ou IMPEDIDO, e explicar nos dois casos, com evidência); Critério de Parada atendido ou não; pendências que exigem o usuário; limitações de escopo; se a missão resolve o contexto; achados.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo.
- Verificação: `python -m unittest discover -s tests -p "test*.py"` (resumo; nenhum teste deve mudar de resultado, já que não há mudança de código) e `sphinx-build -W -b html docs docs/_build/html`.

## Critério de Parada

Para cada `NN.py` com diff entre `fa82f49` e a `main`, a ficha correspondente cita a mudança com `arquivo:linha`; nenhuma ficha tem selo de pendência que contradiga o arquivo de estado (tabela de conferência das 20 classes no relatório); `docs/metadata.md` tem os campos novos; build `-W` e suíte passam sem diferença em relação a antes.
