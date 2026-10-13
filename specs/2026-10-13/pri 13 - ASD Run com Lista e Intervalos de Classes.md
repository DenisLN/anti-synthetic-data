#spec #pri 13

# ASD: Run com Lista e Intervalos de Classes

## Contexto

Na CLI (`logica/cli.py`), `run` aceita uma classe (`run 08`, `run TRANSIENT`) ou `run all` (`cmd_run`, `:541`; `_resolver_classe`, `:266`). O usuário quer `run 01-07,09-20`. Hoje a única forma de excluir classes é a variável `BATERIA_EXCLUIR`. Isso importa para a bancada: o `run all` padrão planeja 468 gravações de TRACe numa conexão, contra a trava da fonte em ~280, e rodar por partes é o caminho recomendado.

O caminho de execução de várias classes é `Bancada.executar_bateria` (`logica/mestre.py`), que isola falhas de experimento e aborta em falha de infraestrutura; a lista precisa passar por ele, não por um laço novo.

## Entradas

- `logica/cli.py` (`cmd_run`, `_run_uma`, `_run_all`, `_aviso_escritas_trace`, `_capturas_das_classes`, `HELP_TEXT`)
- `logica/mestre.py` (`executar_bateria`, `scripts_da_bateria_fisica`, `BATERIA_EXCLUIR`)
- Testes de CLI em `tests/test_offline.py`
- Depende de: nada

## Missão

1. Aceitar em `run` uma lista de ids e intervalos (`01-07,09-20`, `2,5,8`, `10-16`), com validação (id inexistente, intervalo invertido ou vazio são recusados com mensagem e código 1, sem energizar).
2. Executar a lista por `Bancada.executar_bateria`, na ordem numérica, com a mesma resiliência e os mesmos ganchos de fim de run (`set recalibracao`, `set html`) do `run all`, e com o resumo final por classe.
3. Exigir uma confirmação digitada específica para listas, case-sensitive, que contenha a lista normalizada (ex.: `EXECUTAR-CLASSES-01-07,09-20`), mostrando antes as capturas planejadas e a estimativa de gravações de TRACe só das classes escolhidas.
4. Documentar em `HELP_TEXT`, `docs/operacao.md` e `CHANGELOG/v1.15.md`.

## Limites

- `run <NN>` e `run all` continuam com o comportamento e as confirmações atuais (`EXECUTAR-CLASSE-<NN>`, `EXECUTAR-20-CLASSES`).
- Não ampliar o que conta como falha de experimento recuperável; não mudar `executar_bateria` além do necessário para receber a lista.
- Não tocar no hardware.

## Entregável

- Relatório por item.
- Verificação: `python -m unittest tests.test_offline` (testes novos: parser, recusa sem energizar, confirmação, execução simulada de uma lista).

## Critério de Parada

`run 01-03,05` em modo simulado executa exatamente 01, 02, 03 e 05 via `executar_bateria` (teste); entradas inválidas são recusadas sem chamar `Bancada.from_env` (teste); suíte sem falha nova.
