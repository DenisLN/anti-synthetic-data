#spec #pri 31

# ASD: Scripts de Diagnóstico em diag/ e Visita Rodando de Lá

## Contexto

Depois da integração do fork, `scripts/` tem 31 arquivos e mistura o que o operador usa no dia a dia (`START_BENCH.cmd`, `setup_windows.ps1`, `recalibrar_extremos.py`...) com scripts de diagnóstico e de uma pendência só. O dono disse: "existem muitos .py poluindo o diretório scripts/, mover os de diagnóstico para diag/ e fazer o script rodar de lá".

"O script" é a visita às pendências da bancada, análoga ao `START_BENCH`: `scripts/VISITA_BANCADA.cmd` → `scripts/visita_bancada_windows.ps1` → `scripts/visita_bancada.py`. O `visita_bancada.py` acha os scripts por `SCRIPTS = RAIZ / "scripts"` (`:51`) e chama `diag_*.py`, `analisar_*.py`, `benchmark_sessao_io.py` e `teste_passo_final_sin.py` por esse caminho (`:384`, `:444`, `:450`, `:456`, `:481`, `:552`, `:580`, `:588`, `:684`–`:693`), além de pôr `scripts/` no `sys.path` (`:198`).

Dois pontos que quebram silenciosamente se esquecidos:
- `logica/mestre.py:128`, `PASTAS_DO_CODIGO = ("logica", "experimentos_nativos", "experimentos_waveform", "scripts")`, decide o `git_sujo` gravado no metadata de cada sessão. Arquivo novo não rastreado em `diag/` precisa sujar a árvore igual a `scripts/`.
- `AGENTS.md` autoriza editar "os scripts em `scripts/`"; a autorização precisa passar a cobrir `diag/`.

Classificação decidida para esta spec (pastas na raiz do repositório):

| Vai para `diag/` | Fica em `scripts/` |
|---|---|
| `diag_acdc_amplitude.py`, `diag_ciclos_trace.py`, `diag_fonte_vs_osciloscopio.py`, `diag_list_offset.py`, `diag_marcadores_trace.py`, `diag_nativo_output_off.py`, `diag_osciloscopio_canais.py`, `diag_saida_vs_medida.py`, `analisar_modelo_programado.py`, `analisar_reamostragem.py`, `benchmark_sessao_io.py`, `teste_passo_final_sin.py` | `.cmd`, `.ps1`, `visita_bancada.py`, `recalibrar_extremos.py`, `relatorio_limites_bancada.py`, `gerar_ruido_janela.py`, `gerar_tres_versoes.py`, `verificar_sessao_bancada.py`, `fechar_pendencias.py`, `planejar_campanhas.py`, `verificar_prontidao.py`, `gerar_mapa_pendencias.py` |

## Entradas

- `scripts/` e `scripts/visita_bancada.py`, `scripts/visita_bancada_windows.ps1`, `scripts/VISITA_BANCADA.cmd`, `scripts/fechar_pendencias.py`, `scripts/validar_pc_bancada.ps1`
- `logica/mestre.py:128` (`PASTAS_DO_CODIGO`), `logica/cli.py` e `logica/ametek_orm.py` (citam scripts por caminho em textos de ajuda)
- Testes: `tests/test_visita_bancada.py`, `tests/test_pendencias_fechamento.py`, `tests/test_p09_bracos.py`, `tests/test_offline.py` (citam esses caminhos)
- Docs com referências: `docs/diagnostico.md`, `docs/scpi/diagnostico.md`, `docs/bancada_pendencias.md`, `docs/codigo/scripts.md`, `docs/classes/*.md`, `docs/configuracao.md`, `ROTEIRO_BANCADA.md`, `CLAUDE.md`, `AGENTS.md`. Achar todas: `git grep -nE 'scripts[/\\\\](diag_|analisar_|benchmark_sessao_io|teste_passo_final_sin)'`
- Depende de: ASD: Fork na Main e Branches Descontinuadas

## Missão

1. Mover com `git mv` os 12 arquivos da coluna "Vai para `diag/`" e confirmar, para cada um, que ele roda a partir de `diag/` (imports de `logica/` e de helpers de `scripts/`, caminhos relativos à raiz, `--help` sem erro).
2. Fazer a visita (`visita_bancada.py` e o `.ps1`/`.cmd`) chamar os diagnósticos em `diag/`, sem mudar etapas, ordem, confirmações digitadas nem o arquivo de estado da visita (uma visita salva antes continua retomável).
3. Incluir `"diag"` em `PASTAS_DO_CODIGO` (`logica/mestre.py:128`) com teste de regressão de que um arquivo novo não rastreado em `diag/` marca `git_sujo`.
4. Atualizar toda referência aos caminhos antigos (código, testes, docs, `AGENTS.md` incluindo a autorização de edição de `scripts/` estendida a `diag/`, `CLAUDE.md`) e registrar em `CHANGELOG/v1.15.md`. `CHANGELOG` de versões fechadas e `docs/evidencias/` não se reescrevem.
5. Rodar `python scripts/visita_bancada.py --plano` (não energiza) e mostrar a saída no relatório.

## Limites

- Não mudar a lógica de nenhum diagnóstico nem de `visita_bancada.py` além dos caminhos.
- Não remover nem enfraquecer confirmações digitadas (`ENERGIZAR-PASSO-SIN` etc.), validações SCPI/IDN/timeout/6000 pontos, nem os limites inegociáveis do `AGENTS.md`.
- Não tocar no hardware; nada que energize.
- Pode alterar: `scripts/`, `diag/`, `logica/mestre.py` (só `PASTAS_DO_CODIGO`), textos de ajuda em `logica/cli.py` e `logica/ametek_orm.py`, `tests/`, `docs/`, `AGENTS.md`, `CLAUDE.md`, `ROTEIRO_BANCADA.md`, `CHANGELOG/v1.15.md`.
- Se o pedido parecer equivocado ou existir abordagem melhor (por exemplo, um script da coluna "fica" que seja claramente diagnóstico), dizer isso em uma frase e seguir com a tabela.
- Se algum limite impedir ou restringir o resultado, registrar no relatório em "Limitações de escopo", sem ultrapassá-lo.

## Entregável

- Relatório `.md` no caminho que o despacho indicar, com: um bloco por item da Missão (copiar o texto do item, dizer CUMPRIDO, PARCIAL, NÃO CUMPRIDO ou IMPEDIDO, e explicar nos dois casos, com evidência); Critério de Parada atendido ou não; pendências que exigem o usuário; limitações de escopo; se a missão resolve o contexto; achados.
- Pasta `diag/` com os 12 scripts.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo (o `.cmd`/`.ps1` só roda no Windows da bancada).
- Verificação: `python -m unittest discover -s tests -p "test*.py"` (total, falhas, erros, skips) e `git grep -nE 'scripts[/\\\\](diag_|analisar_|benchmark_sessao_io|teste_passo_final_sin)' -- . ':!CHANGELOG' ':!docs/evidencias'` vazio.

## Critério de Parada

`ls scripts/*.py` não lista nenhum dos 12 arquivos e `ls diag/` lista os 12; o `git grep` da Verificação não devolve nada; `visita_bancada.py --plano` roda sem erro; o teste novo de `git_sujo` com `diag/` passa; suíte sem falha nova em relação à `main` antes da mudança.
