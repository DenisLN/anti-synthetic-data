#spec #pri 16

# ASD: Leitura das TRACEs Gravadas (set diagnostico retrieve)

## Contexto

Nunca se conferiu o que de fato fica gravado na Flash da AMETEK depois de `TRACe:DATA`. O manual descreve `TRACe:DATA? <nome>` devolvendo os valores normalizados (±1). O usuário quer isso num modo extra da CLI, ligado por `set diagnostico retrieve` (ao lado do `set diagnostico on|off` de hoje), com o resultado gravado **fora** do `.npz` da captura.

Restrição de segurança conhecida (`CHANGELOG/v1.12.md`, "Achado de segurança"; `docs/quirks.md` A2): consultar a fonte logo depois de `TRACe:DATA` deixou a fonte muda até ser religada. Hoje há `sleep(1.0)` + `*CLS` depois de cada `TRACe:DATA` e `TRACe:DATA/DEFine/DELete` ficam fora do sincronismo por `*ESR?` (`logica/ametek_orm.py`, `_SEM_SINCRONISMO`). A leitura tem de acontecer num momento seguro (depois da captura terminar e a lista concluir, antes de qualquer nova programação) e nunca colada a uma escrita.

## Entradas

- `logica/ametek_orm.py` (`program_capture`, `write`/`query`, `_SEM_SINCRONISMO`, `TRACE_POINTS`, modo simulado), `logica/mestre.py` (`DIAGNOSTICO_MODE`, `_capturar_real` das classes TRACE), `logica/cli.py` (`set diagnostico`)
- Manual: `docs/AMETEK_MX_SCPI_Programming_Manual.pdf` e o texto extraído (seção TRACe:DATA)
- Depende de: ASD: Análises Fora de docs e Arquivo em Branch Separado (o texto extraído do manual muda de pasta)

## Missão

1. Confirmar no manual a sintaxe e o formato de resposta de `TRACe:DATA?` e registrar em `docs/scpi.md`.
2. Implementar `AmetekMX30.ler_trace(nome)` (query com timeout próprio, parse e validação de 1024 valores, erro claro se vier outro tamanho) e o equivalente no modo simulado (devolve o que foi gravado).
3. Implementar `set diagnostico retrieve`: com ele, cada captura TRACE lê de volta as TRACEs usadas, num ponto seguro do fluxo, com espera mínima configurável depois da última escrita, e grava em `<sessao>/diagnostico_trace/<nome da captura>.npz` (enviado × lido, `LIST:VOLTage`) mais o desvio máximo no metadata da captura.
4. Mostrar o estado em `status`/`HELP_TEXT` e documentar o custo de tempo em `docs/diagnostico.md`; registrar em `CHANGELOG/v1.15.md`.

## Limites

- Desligado por padrão. Não ler no meio da sequência de escritas; nunca logo após `TRACe:DATA` sem a espera.
- Não mudar validações de IDN/timeout/6000 pontos/SCPI; não mudar o cache de TRACe.
- Não gravar dentro do `.npz` da captura.
- Não tocar no hardware.

## Entregável

- Relatório por item.
- Verificação: `python -m unittest tests.test_offline` (testes no simulado: lê o que foi gravado; recusa resposta com tamanho errado; a leitura nunca é o comando seguinte a um `TRACe:DATA`; arquivo gravado na pasta separada).

## Critério de Parada

Com `set diagnostico retrieve` numa sessão simulada aparece `diagnostico_trace/` com enviado × lido idênticos; o teste de ordem dos comandos passa; suíte sem falha nova.
