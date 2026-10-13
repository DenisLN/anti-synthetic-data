#spec #pri 12

# ASD: Preflight Único na Tensão Base com ENERGIZAR-TESTE

## Contexto

Existem dois preflights: `logica/preflight.py` (comunicação, trigger e "baixa tensão") e `logica/preflight_new.py` (comandos nativos), que importa o `run` do primeiro. A CLI usa os dois (`logica/cli.py:508-536`). O comando `lowvoltage` diz "5 Vrms" e pede `ENERGIZAR-5V`, mas programa `BASE_VOLTAGE_RMS` (a tensão digitada no início, 127 V normalmente): rótulo enganoso de segurança. Decisão do usuário (2026-10-13): descontinuar o `preflight.py`, manter só o `preflight_new.py`, rodar de fato na tensão base (127 V) e trocar a confirmação de `lowvoltage` para `ENERGIZAR-TESTE`.

Fato conferido: `preflight_new.py:52-53` já usa `GRID_FREQUENCY_HZ ± 3` na deriva de frequência; a nota "ainda usa 57/63 Hz" está desatualizada. Os testes com 57/63 em `tests/test_offline.py:426-450,2165,2697` exercitam o ORM e ficam.

Também em aberto: `native` pela CLI não grava log em arquivo (o log `logs/preflight_new-*.log` só existe chamando o script direto).

## Entradas

- `logica/preflight.py`, `logica/preflight_new.py`, `logica/cli.py` (`cmd_comm`, `cmd_trigger`, `cmd_lowvoltage`, `cmd_native`, `HELP_TEXT`)
- `scripts/start_bench_windows.ps1`, `scripts/START_BENCH.cmd`, `scripts/package_windows.ps1` (procurar `preflight`)
- Testes que importam `preflight`/`preflight_new` em `tests/test_offline.py`
- Docs: `docs/operacao.md`, `docs/arquitetura.md`, `docs/diagnostico.md`, `docs/testes.md`, `AGENTS.md` (tabela de comandos e lista de confirmações)
- Depende de: nada

## Missão

1. Mover para `preflight_new.py` o que a CLI usa do `preflight.py` (comunicação/IDN, OUTPUT OFF, trigger forçado, teste na tensão base via TRACe/LIST), sem mudar a sequência de comandos nem as validações, e apagar `logica/preflight.py`.
2. Trocar todos os rótulos "5 V"/"5 Vrms" do fluxo por "tensão base (<V> Vrms)" com o valor real, e a confirmação de `lowvoltage` para `ENERGIZAR-TESTE` (case-sensitive).
3. Fazer `native` (e `lowvoltage`) chamados pela CLI gravarem o mesmo log em arquivo `logs/preflight_new-*.log` que o script direto grava.
4. Atualizar testes, scripts `.ps1`/`.cmd` e docs (incluindo `AGENTS.md`: tabela de comandos e lista de confirmações).

## Limites

- Não remover nem enfraquecer validações de IDN, timeout, 6000 pontos, `assert_no_errors`/`check_errors`, nem a exigência de confirmação digitada antes de energizar.
- Não mudar `AMETEK_PORT`/`AMETEK_BAUDRATE` nem `validate_bench_configuration()`.
- Não tocar no hardware.

## Entregável

- Relatório por item; `git grep -n "preflight\.py\|import preflight$\|ENERGIZAR-5V\|5 Vrms"` antes/depois.
- Verificação: `python -m unittest tests.test_offline`.

## Critério de Parada

`logica/preflight.py` não existe; `git grep "ENERGIZAR-5V"` só acha CHANGELOG fechados; a CLI chama apenas `preflight_new`; testes novos cobrem a confirmação `ENERGIZAR-TESTE` e a gravação do log; suíte sem falha nova.
