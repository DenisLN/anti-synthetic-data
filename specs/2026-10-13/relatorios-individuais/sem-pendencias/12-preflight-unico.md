## Análise do orquestrador

- Implementação completa? Sim: preflight.py apagado, CLI só importa preflight_new (cli.py:28), ENERGIZAR-TESTE (cli.py:522), 6 testes novos; conferido no merge eb8d236.
- Pendências do usuário: nenhuma.
- Escopo limitado demais? Não.
- Resolve o contexto? Sim.
- Critério de Parada: atendido na substância; ENERGIZAR-5V ainda aparece só em notas de remoção, CHANGELOG v1.15 e testes de regressão (uso não vivo). Suíte: 376 testes, só as 4 falhas conhecidas.
- Classificação: sem pendências. Observação: o CHANGELOG cita 'decisão do dono' (a spec 22 limpa).

---

# Relatório: ASD Preflight Único na Tensão Base com ENERGIZAR-TESTE

Branch: `worktree-agent-af39ac12e9f42fbc5`, commit `ba24d45` (feat: preflight único na tensão base com ENERGIZAR-TESTE e log da CLI).

## Missão, item a item

**Item 1 — Mover para `preflight_new.py` o que a CLI usa do `preflight.py` (comunicação/IDN, OUTPUT OFF, trigger forçado, teste na tensão base via TRACe/LIST), sem mudar a sequência de comandos nem as validações, e apagar `logica/preflight.py`.**
- Status: CUMPRIDO
- Explicação: `normal_waveform()` e `run_basic_stage()` (antigo `run`) estão em `logica/preflight_new.py:81-160`, com a mesma sequência e as mesmas validações (IDN, OUTPUT OFF/ON, 6000 pontos, tolerância de RMS). Único ajuste no corpo: `print` virou `logger.info` com o mesmo texto, para o texto também ir ao arquivo de log (necessário ao item 3). `git rm logica/preflight.py` feito; o import `from preflight import run` saiu. Comentários/`--help` que citavam `preflight.py` foram ajustados (`preflight_new.py`, `diag_digitizer_hipoteses.py`).

**Item 2 — Trocar todos os rótulos "5 V"/"5 Vrms" do fluxo por "tensão base (<V> Vrms)" com o valor real, e a confirmação de `lowvoltage` para `ENERGIZAR-TESTE` (case-sensitive).**
- Status: CUMPRIDO
- Explicação: `cli.py:517-531` (`cmd_lowvoltage`) usa f"...tensão base ({mestre.BASE_VOLTAGE_RMS:g} Vrms ...)" e `"ENERGIZAR-TESTE"`; `HELP_TEXT` atualizado; mensagem final de `run_basic_stage` mostra `%.3f Vrms` de `BASE_VOLTAGE_RMS`. `confirmar()` já era comparação exata (case-sensitive). Docs/AGENTS.md atualizados.

**Item 3 — Fazer `native` (e `lowvoltage`) chamados pela CLI gravarem o mesmo log em arquivo `logs/preflight_new-*.log` que o script direto grava.**
- Status: CUMPRIDO
- Explicação: novo `preflight_new.run_com_log(etapa, funcao)` (`preflight_new.py:167`) chama `_configure_logging(etapa)` (o mesmo do `main()`); a CLI o usa em `native`, `lowvoltage` e também `comm`/`trigger` (`cli.py:507-545`; os dois últimos por usarem a mesma função, acréscimo mínimo). A configuração do log ocorre só depois da confirmação digitada.

**Item 4 — Atualizar testes, scripts `.ps1`/`.cmd` e docs (incluindo `AGENTS.md`: tabela de comandos e lista de confirmações).**
- Status: CUMPRIDO
- Explicação: testes novos em `PreflightUnicoTests` (fim de `tests/test_offline.py`, 6 testes). `scripts/*.ps1`/`.cmd`/`package_windows.ps1` não citam `preflight` (apenas um comentário genérico "comm/trigger/lowvoltage/native/run" em `start_bench_windows.ps1`, que continua correto): nada a alterar. Docs: `AGENTS.md` (tabela, nota, lista de confirmações, nota de logs, módulos refatoráveis), `docs/operacao.md`, `docs/arquitetura.md`, `docs/quirks.md` (B9), `README.md`; `CHANGELOG/v1.15.md` ganhou seção nova no fim. `docs/testes.md` e `docs/diagnostico.md` não citavam o `preflight.py`. Nada tocado em `docs/analise-*`/`docs/superpowers`.

## Critério de Parada
Atendido, com ressalva de redação.
- `logica/preflight.py` não existe (teste `test_preflight_py_nao_existe_e_cli_so_usa_preflight_new`).
- A CLI não importa mais `preflight` (`git grep -n "^import preflight$" logica` vazio); só `preflight_new`.
- `git grep ENERGIZAR-5V` agora acha: CHANGELOG fechados, e menções explicativas ("foi removido") em `AGENTS.md:41`, `docs/operacao.md:58`, `CHANGELOG/v1.15.md` (seção nova) e nos testes que garantem a ausência/recusa da string. Nenhuma ocorrência é uso vivo; ressalva: a spec dizia "só CHANGELOG fechados".
- Testes: `TMPDIR=/tmp/claude-0/tmpt /tmp/claude-0/venv/bin/python -m unittest tests.test_offline` -> 376 testes (370 + 6 novos), `FAILED (failures=4)`: só as 4 fixtures byte a byte conhecidas.
- git grep antes: 56 linhas (maioria em CHANGELOG/analise antigos; vivas: AGENTS.md:41,45,81, docs/operacao.md, quirks B9, cli.py:6,27,75,79,516,518, preflight_new.py:5,6,406,660,664). Depois: só as menções explicativas acima, mais `Vrms` de outros contextos (ametek_orm.py:1187-1188, diag_nativo_output_off.py:351, quirks A13: "4,5 Vrms", falsos positivos).

## Pendências que exigem o usuário
Nenhuma. (Execução real de `lowvoltage`/`native` pela CLI na bancada é validação futura do operador.)

## Limitações de escopo
Nenhuma. Os limites foram respeitados (nenhuma validação enfraquecida, porta/baud e `validate_bench_configuration()` intactos, sem hardware).

## A missão resolve o contexto?
Sim. Um só preflight, rótulo/confirmação honestos e log em arquivo também pela CLI. A nota de que 57/63 Hz estaria desatualizada se confirma: `preflight_new.py` já usa `GRID_FREQUENCY_HZ ± 3`.

## Achados
- (baixa) `print` -> `logger.info` muda o formato no terminal para `[hh:mm:ss] [INFO] ...` nas etapas comm/trigger/lowvoltage; conteúdo igual. NÃO VERIFICADO no hardware.
- (baixa) A frase da spec "`git grep ENERGIZAR-5V` só acha CHANGELOG fechados" é inalcançável literalmente, pois a nota de remoção e os testes de regressão precisam citar a string.
- (baixa) Em `test_offline.py` o teste de rótulo usa `assertNotIn("5 Vrms" ...)` condicional a BASE_VOLTAGE_RMS != 5 (porque o padrão de teste pode ser 5).
- (info) Os testes antigos de 57/63 Hz no ORM ficaram, como a spec mandou.
- (info) `autorizar_saida` agora espelha `ARM_OUTPUT` só em `mestre` e `preflight_new`.
