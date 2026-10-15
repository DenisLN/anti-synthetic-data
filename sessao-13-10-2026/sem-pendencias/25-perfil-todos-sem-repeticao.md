## Análise do orquestrador

- Implementação completa? Sim: perfis.classes_independentes_do_perfil derivada das tabelas e testada contra gerar() real; captura única em literatura espelhada no metadata dos 3 perfis (arquivo/índice/sha256 + captura_compartilhada/perfil_de_origem); sessao_io, HTML e scripts resolvem; estimativa 1404→1116 (60 Hz). Merge ok: 497 testes OK.
- Pendências: nenhuma. Observação: logica/perfis.py só ganhou funções; registrar no AGENTS.md (spec 22).
- Critério de Parada: atendido. Classificação: sem pendências.

---

# Relatório: ASD: set perfil todos sem Recapturas Iguais

Branch: `worktree-agent-a5ba87a310ebb69eb`, commit `6a2add0` (local, sem push). Suíte: `tests.test_offline` 491 testes, OK, 2 pulados (SHA-256 exatos, só Windows).

## Missão, item a item

**Item 1 — Determinar de forma automática e testada quais classes têm `gerar()` independente do perfil (função em `logica/perfis.py` ou `mestre.py`, derivada do código/tabela, não uma lista escrita à mão sem teste; um teste confere que, para essas classes, `gerar()` dá arrays e parâmetros idênticos nos três perfis para várias seeds e índices, e que para as outras difere).**
- Status: CUMPRIDO
- Explicação: `logica/perfis.py` ganhou `depende_do_perfil`, `classes_independentes_do_perfil` e `plano_de_perfis`. A decisão vem das tabelas (`COMPONENTES_POR_CLASSE`, `FAIXAS`, `FAIXAS_SORTEADAS`): a classe depende se algum componente que ela lê tem valor efetivo diferente entre perfis, e isso varia com o sorteio. Independentes com sorteio ligado (padrão): 01, 04, 07, 08, 09, 17, 18, 19. Com `set sorteio off` entra também a 16. O teste `PerfisCompartilhadosTests.test_independentes_derivadas_da_tabela_e_conferidas_contra_o_gerar_real` roda o `gerar()` real das 20 classes nos 3 perfis, a 60 e 50 Hz, com sorteio ligado e desligado, 8 índices: arrays e parâmetros iguais nas independentes, diferença em pelo menos um índice nas demais.

**Item 2 — Com `set perfil todos`, capturar essas classes uma vez só (gravadas sob um perfil canônico, ex. `literatura`) e registrar no metadata, para os outros perfis, entradas que apontam para a mesma captura: mesmo `arquivo_classe`, mesmo `indice_no_arquivo` (ou campo equivalente) e o hash (SHA-256) dos arrays da captura, mais um campo explícito do tipo `compartilhada_com_perfis` / `perfil_de_origem`. Classes dependentes do perfil continuam rodando uma vez por perfil.**
- Status: CUMPRIDO
- Explicação: `Bancada.executar_bateria` e `executar_classe_nos_perfis` (`logica/mestre.py`) usam `perfis.plano_de_perfis`: a independente roda só em `literatura`, com `Config.perfis_espelho=("norma","fronteira")`. Ao terminar sem erro, `_gravar_arquivos_da_classe` chama `ArquivoDaClasse.espelhar` (`logica/sessao_io.py`). O metadata passa a ter uma linha por perfil com `arquivo_classe`, `indice_no_arquivo`, `sha256_captura` (`hash_captura`), `perfil_de_origem`, `compartilhada_com_perfis` e `captura_compartilhada`. O `.npz` guarda só o bloco `literatura` mais `compartilhadas_perfis`/`compartilhadas_origem`, também em `snr_XXdb/` e `corrente/`. Dependentes inalteradas. Falha ou interrupção não espelha. Testes: `test_simulado_captura_independente_uma_vez...`, `test_bancada_fisica_captura_a_classe_independente_uma_so_vez` (2 capturas, não 6), `test_falha_da_classe_independente_nao_deixa_espelhos`.

**Item 3 — Fazer `logica/sessao_io.py` (e por ele `relatorio_html.py`, `analisar_sessao.py`, `recortar_margem.py`, scripts) resolver essas entradas compartilhadas: pedir o perfil `norma` de uma classe compartilhada devolve a captura canônica, marcada como compartilhada. O HTML deve mostrar que é a mesma captura (não duplicar figuras sem dizer).**
- Status: CUMPRIDO
- Explicação: `ler_pasta` (`_ler_formato2`) devolve, para `perfis=["norma"]`, a captura de `literatura` com `perfil="norma"`, `compartilhada=True`, `perfil_de_origem="literatura"`, `espelho=True` e o metadata da linha `norma`. O hash gravado confere com os arrays lidos (teste). `relatorio_html`: uma figura por captura compartilhada, rotulada "(= norma, fronteira)", com linha "Captura compartilhada" e SHA-256; com `--perfis norma` a captura aparece marcada como do perfil de origem. `analisar_sessao`, `diag_ciclos_trace`, `verificar_sessao_bancada` tratam a captura uma vez (sob a origem). `recortar_margem` e `gerar_ruido_janela` preservam o espelhamento (sem duplicar blocos). `recuperar_parcial` preserva os espelhos. Testes: `test_sessao_io_resolve...`, `test_html_desenha...`, `test_recortar_margem_preserva...`, `test_analisar_sessao_ve...`, `test_recuperar_parcial_preserva...`.

**Item 4 — Atualizar a confirmação/estimativa de capturas e gravações de TRACe do `run` com `todos` para contar só o que roda de fato.**
- Status: CUMPRIDO
- Explicação: `cli.py` `_capturas_das_classes` usa `plano_de_perfis` (campos `por_perfil`, `espelhos`, `evitadas`); `_descrever_capturas` e `_aviso_escritas_trace` dizem "igual em norma, fronteira, sem recaptura" e quantas capturas repetidas foram evitadas; `HELP_TEXT` atualizado. Teste `test_estimativa_conta_so_o_que_roda_de_fato` e o da confirmação do `run all` (ajustado). Medido (sorteio ligado, `run all` com `todos`): gravações de TRACe **1116 a 60 Hz e 930 a 50 Hz**; antes 1404 e 1170; um perfil só 468 e 390. Capturas planejadas 110 (antes 150).

**Item 5 — Atualizar `docs/dataset.md`, `docs/metadata.md` (só acrescentar campos), `docs/perfis.md`, `docs/operacao.md` e `CHANGELOG/v1.15.md` (seção nova no fim, ou subseção da seção da spec 17).**
- Status: CUMPRIDO
- Explicação: os cinco arquivos atualizados; `metadata.md` só ganhou linhas; seção nova no fim do `CHANGELOG/v1.15.md` (Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO). A frase antiga da seção da spec 17 ("triplica ... fica como decisão do dono") não foi reescrita (registro histórico); a nova seção a supera.

## Critério de Parada
Atendido. Sessão simulada com `todos` captura as independentes uma vez (`01_normal.npz` só com `literatura`, teste que espia as execuções); metadata dos 3 perfis com mesmo arquivo/índice/hash; `sessao_io` e HTML resolvem (testes); estimativa atualizada; `python -m unittest tests.test_offline`: 491 testes, OK.

## Pendências que exigem o usuário
nenhuma (ver NÃO VERIFICADO em Achados).

## Limitações de escopo
nenhuma.

## A missão resolve o contexto?
Sim: o `run all` com `todos` deixa de recapturar as 8 classes iguais, preservando nos metadados e no HTML a informação de que o perfil é o mesmo. O pedido não parece equivocado.

## Achados
- (info) Esclarecimento do usuário seguido: todas as capturas compartilhadas ficam registradas no metadata dos três perfis.
- (média) A classe 16 é independente só com `set sorteio off`; com sorteio a norma sorteia THD desde 2 %. A decisão usa `Config.sorteio_posicao` da rodada.
- (baixa) `logica/perfis.py` não está nominalmente listado nas autorizações de `AGENTS.md`; só foram acrescentadas funções, `FAIXAS` intocada. Registrado no CHANGELOG.
- (baixa) Testes antigos de `NpzPorClasseTests` precisaram de ajuste: a classe falsa 96 foi tornada dependente via `mock.patch.dict` e as expectativas da classe 01 mudaram (uma execução).
- (baixa) Espelho é cópia, não medida: perde-se a comparação de três capturas físicas do mesmo sinal (ruído de bancada). NÃO VERIFICADO em bancada real (`BENCH_MODE=1` proibido aqui).
- (baixa) Metadata de `gerar_ruido_janela` mantém o `sha256_captura` do dado original da sessão (o `.npz` de saída só traz SNR).
