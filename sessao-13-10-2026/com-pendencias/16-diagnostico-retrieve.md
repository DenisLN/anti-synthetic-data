## Análise do orquestrador

- Implementação completa? Sim no simulado: ler_trace (timeout próprio, 1024 valores, LeituraTraceError fora de CommunicationError), set diagnostico retrieve (desligado), espera ≥ 2 s e recusa colada a TRACe:DATA, gravação em diagnostico_trace/, *IDN? após falha; merge limpo, suíte OK.
- Pendências do usuário: o manual se contradiz sobre a existência da query (p.126 'none' × p.147 'when queried'); só a bancada confirma — primeiro uso numa captura isolada.
- Escopo limitado demais? Não.
- Resolve o contexto? Sim no código; NÃO VERIFICADO no instrumento.
- Critério de Parada: atendido.
- Classificação: com pendências (verificação na bancada).

---

# Relatório: ASD: Leitura das TRACEs Gravadas (set diagnostico retrieve)

Branch: `worktree-agent-a04c6e30f77624d6a`. Commit: `c17fbb7` (após o merge de `claude/specs-v1-15-review-3w2bgl`, feito antes de começar).

## Missão, item a item

**Item 1 — Confirmar no manual a sintaxe e o formato de resposta de `TRACe:DATA?` e registrar em `docs/scpi.md`.**
- Status: PARCIAL
- Explicação: o manual (`docs/manuais_txt/AMETEK_MX_SCPI_Programming_Manual.txt` linhas ~5834-5864 e ~6813-6830) é ambíguo. A descrição do `TRACe[:DATA]` (p. 126) diz `Query Syntax: none`, e a p. 147 diz "When queried, trace data is returned as normalized values in the range of ±1". Não há sintaxe de query nem formato de resposta (vírgulas? bloco `#`?) documentados. Registrei isso em `docs/scpi.md` (parágrafo novo antes de "Manual: TRACe 126-127"), com `TRACe:DATA? <nome>` e lista NRf de 1024 valores como suposição marcada NÃO VERIFICADA. Só a bancada confirma.

**Item 2 — Implementar `AmetekMX30.ler_trace(nome)` (query com timeout próprio, parse e validação de 1024 valores, erro claro se vier outro tamanho) e o equivalente no modo simulado (devolve o que foi gravado).**
- Status: CUMPRIDO
- Explicação: `logica/ametek_orm.py:1353` (`ler_trace(nome, espera_minima_s=2.0, timeout_s=15.0)`), com `LeituraTraceError` (`:66`, não herda `CommunicationError`). O timeout do recurso VISA é trocado durante a query e restaurado em `finally`. O parse exige 1024 valores finitos; senão o erro diz quantos vieram. Timeout vira `LeituraTraceError`. Simulado: `_simulate_write` guarda o texto de `TRACe:DATA` e `_simulate_query` devolve o mesmo para `TRACe:DATA? nome`; `clear_all_traces` limpa. Testes: `test_ler_trace_simulado_devolve_o_que_foi_gravado`, `test_ler_trace_recusa_tamanho_errado_e_resposta_ilegivel`, `test_espera_minima_desde_a_ultima_escrita_de_trace` (recurso VISA falso, timeout 9000 ms e restauração para 5000).

**Item 3 — Implementar `set diagnostico retrieve`: com ele, cada captura TRACE lê de volta as TRACEs usadas, num ponto seguro do fluxo, com espera mínima configurável depois da última escrita, e grava em `<sessao>/diagnostico_trace/<id da captura>.npz` (enviado × lido, `LIST:VOLTage`) mais o desvio máximo no metadata da captura.**
- Status: CUMPRIDO
- Explicação:
  - CLI (`logica/cli.py`): `set diagnostico retrieve [on|off]`, independente de `on|off`.
  - Estado e config (`logica/mestre.py`): `DIAGNOSTICO_RETRIEVE` (`:354`), `DIAGNOSTICO_RETRIEVE_ESPERA_S` (env, padrão 2,0 s; abaixo de 2 s avisa no log), campos novos em `Config`.
  - Ponto seguro: `_ler_traces_de_diagnostico` (`mestre.py:2013`) roda no fim de `_capturar_real`, nas classes waveform (`:3117`) e na nativa que usa TRACe (`:2912`). Vem depois de `wait_transient_complete` e depois de o osciloscópio ser lido, e nada é escrito na fonte até a próxima captura.
  - Proteções em `ler_trace`: recusa se o comando anterior foi escrita de TRACe, e espera o restante da espera mínima desde a última escrita `TRACe:DATA/DEFine/DELete`. Esse instante é marcado em `_raw_write`. Consultas como `TRACe:CATalog?` e a própria leitura não contam como escrita.
  - Gravação: `_gravar_diagnostico_trace` (`mestre.py:2063`) grava `diagnostico_trace/<id>.npz` (`nomes`, `enviado`, `lido`, `list_voltage_rms`), de forma atômica e fora do `.npz` da captura. O metadata ganha `diagnostico_trace` com `arquivo`, `desvio_max`, `desvio_max_por_trace`, `erro` e tempos. O gancho no laço de `executar` é uma linha (`:2660`); `_salvar_captura` e `_finalizar_gravacao` não foram tocados.
  - Testes: `test_sessao_com_retrieve_grava_pasta_separada_com_enviado_igual_a_lido`, `test_desligado_por_padrao_nao_le_nem_grava`, `test_desvio_aparece_no_metadata`, `test_cli_set_diagnostico_retrieve_liga_desliga_e_help_menciona`.

**Item 4 — Mostrar o estado em `status`/`HELP_TEXT` e documentar o custo de tempo em `docs/diagnostico.md`; registrar em `CHANGELOG/v1.15.md` (seção nova no fim) e a variável/estado novo em `docs/configuracao.md` se houver.**
- Status: CUMPRIDO
- Explicação: `status` mostra `diagnostico retrieve: ON|OFF`; `HELP_TEXT` ganhou o bloco do comando. `docs/diagnostico.md` §1.1 traz o custo de tempo, estimado em ~1 s por TRACe, ~12 s por captura de 12 ciclos mais 2 s de espera, ~15 min a mais em 63 capturas, tudo NÃO VERIFICADO. `docs/configuracao.md` ganhou `DIAGNOSTICO_RETRIEVE_ESPERA_S`. `CHANGELOG/v1.15.md` tem a seção nova no fim, com Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO.

## Critério de Parada
Atendido.
- Com `retrieve` ligado e uma classe waveform (07) rodando em `executar()` com fonte simulada, aparece `diagnostico_trace/<id>.npz` com `enviado == lido` e `desvio_max == 0.0`. Evidência: `DiagnosticoRetrieveTests.test_sessao_com_retrieve_grava_pasta_separada_com_enviado_igual_a_lido`.
- Teste de ordem: `test_leitura_nunca_e_o_comando_seguinte_a_um_trace_data` (e as asserções de ordem no teste da sessão: leitura depois do `*TRG`, nenhuma anterior colada a `TRACe:DATA`).
- Suíte: `TMPDIR=/tmp/claude-0/tmpt /tmp/claude-0/venv/bin/python -m unittest tests.test_offline` deu 443 testes, OK (2 pulados esperados), 0 falhas. Os 9 testes novos estão incluídos.

## Pendências que exigem o usuário
- Só a bancada confirma se a fonte aceita `TRACe:DATA? <nome>` e em que formato responde. Sugestão: primeiro uso numa captura isolada (`set capturas 1`, `run <NN>`) com o painel à vista. A leitura nunca é a primeira consulta após um `TRACe:DATA`, mas é uma query nova numa fonte com histórico de travas.

## Limitações de escopo
- Sem hardware, a sintaxe real, o formato de resposta, a escala devolvida (normalizada por pico? por rms?) e o custo de tempo não puderam ser verificados. `desvio_max` é a diferença bruta contra a TRACe enviada (pico 1); um desvio diferente de zero na bancada pode ser normalização, não erro.
- O manual não define a query, então a spec 1 ("confirmar no manual") ficou só em "o manual é ambíguo".

## A missão resolve o contexto?
Parcialmente: o mecanismo seguro e testado está pronto, mas a resposta real da fonte (e se a query existe) só aparece na primeira execução na bancada. Se a Rev. 5.53 não suportar a query, o resultado será `erro` no metadata, sem derrubar a captura.

## Achados
- (Média) Contradição do manual: p. 126 "Query Syntax: none" contra p. 147 "when queried... normalized ±1". Pode significar que a query não existe nessa revisão. Uma query de header não implementado já causou `-113` preso na fila (quirk A8). Mitigação: o `*CLS` do próximo `program_capture` limpa; se a leitura falhar, a checagem de `*IDN?` confirma que a fonte segue viva.
- (Baixa) A leitura inclui `*IDN?` (`aguardar_resposta`) só quando há `LeituraTraceError`. Isso é de propósito, para não engolir mudez real da fonte.
- (Baixa) Incluí também a nativa 05 com TRACe (`usar_trace`) além das waveform, porque ela também grava TRACEs; a spec citava só a classe waveform. Mudança de uma linha em `ExperimentoNativo._capturar_real`.
- (Baixa) `ler_trace` aceita só lista numérica separada por vírgula; um bloco binário/`#` seria recusado como erro de leitura. NÃO VERIFICADO se a fonte usa esse formato.
- (Info) A spec 17 mexe em `_salvar_captura`/`_finalizar_gravacao` e `set perfil`; as mudanças aqui ficam em `cmd_set`/`status`/`HELP_TEXT` (trechos de `set diagnostico`), `Config`/`_build_config` e funções novas. Possível conflito trivial só em `HELP_TEXT` e no fim de `tests/test_offline.py` e `CHANGELOG/v1.15.md`.
- (Info) O passo `arm_transient` do simulador exige readbacks que ele não modela; os testes de sessão trocam `arm_transient`/`trigger` por stubs. Não alterei o simulador.
