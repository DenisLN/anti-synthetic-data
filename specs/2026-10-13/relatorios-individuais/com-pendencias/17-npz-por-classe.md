## Análise do orquestrador

- Implementação completa? Sim: NN_classe.npz comprimido (perfil × medida/modelo/programada), SNRs e corrente fora, spool parcial/ atômico, set perfil todos, logica/sessao_io.py lendo os dois formatos, consumidores migrados, aviso de quebra no CHANGELOG, autorização no AGENTS.md; merge com conflitos de código resolvidos à mão (analisar_sessao: import + coluna da métrica da 18; cli: uso do set); 473 testes OK.
- Pendências do usuário: (1) classes que não dependem do perfil rodam 3x em 'todos' (triplica tempo/Flash); (2) recuperar_parcial automático no início do run?
- Escopo limitado demais? Não.
- Resolve o contexto? Sim. Ficou para o orquestrador: diag_ciclos_trace.py e verificar_sessao_bancada.py precisam ler o formato novo via sessao_io (sessões de amanhã).
- Critério de Parada: atendido.
- Classificação: com pendências.

---

# Relatório: ASD: Um NPZ Comprimido por Classe com Perfis e Versões

Branch: `worktree-agent-a1c15286a083cc00d` (worktree `/home/user/anti-synthetic-data/.claude/worktrees/agent-a1c15286a083cc00d`). Commits locais: `c6d3e0e` (código + testes) e `9022286` (docs, CHANGELOG, AGENTS). Merge prévio de `claude/specs-v1-15-review-3w2bgl` feito (fast-forward/merge limpo, sem conflito). Sem push.

Suíte: `TMPDIR=/tmp/claude-0/tmpt /tmp/claude-0/venv/bin/python -m unittest tests.test_offline` -> 431 testes, OK, 2 pulados (linha de base 412, OK). 19 testes novos em `NpzPorClasseTests` (fim do arquivo); 11 classes de teste antigas atualizadas para o formato novo (as que contavam arquivos por captura).

## Missão, item a item

**Item 1 — Definir e documentar o formato: um `NN_classe.npz` comprimido por classe e sessão, com chaves `<perfil>/<versao>` (`medida`, `modelo`, `programada`) empilhadas por captura, `id_captura` por perfil, `tempo_ms`, e o índice de cada captura no metadata (`arquivo_classe`, `perfil`, `indice_no_arquivo`); SNRs fora dele, em arquivos por classe e nível.**
- Status: CUMPRIDO
- Explicação: formato definido em `logica/sessao_io.py` e documentado em `docs/dataset.md` §2 (tabela de chaves), `docs/metadata.md` (campos novos só acrescentados: `arquivo_classe`, `indice_no_arquivo`, e em `sessao.json` `formato_npz` e `perfis_da_rodada`), `docs/tres_versoes.md`. Chaves: `formato_npz`, `classe`, `perfis`, `tempo_ms` (eixo da medida), `tempo_janela_ms` (eixo de 6000 pontos) e, por perfil, `id_captura`, `medida`, `modelo`, `programada`, `origem_programada`, `inicio_janela`. Decisões: `medida` = registro inteiro `(N, 8100)` na bancada (o que era o `tensao_pu` por captura; a janela é `medida[inicio_janela:inicio_janela+6000]`), no simulado `(N, 6000)` e igual a `modelo` (duplicata deliberada, para as 9 chaves existirem sempre); `programada` ausente vira linha de NaN; strings em arrays Unicode (sem pickle). SNRs em `snr_XXdb/NN_classe.npz` (`<perfil>/tensao_pu`), corrente em `corrente/NN_classe_corrente.npz`. Verificado em `tests.test_offline.NpzPorClasseTests.test_set_perfil_todos_grava_um_npz_por_classe_com_as_nove_chaves`.
- Observação (uma frase, como pedido): os SNRs são gravados sem compressão porque o ruído branco só ganhou 4,6 % ao comprimir (medido) e custaria CPU a cada reescrita; o arquivo da classe e a corrente são comprimidos (`np.savez_compressed`).

**Item 2 — Implementar a escrita na bancada (acumulando por classe, gravação atômica com `.part`, sem perder capturas já feitas se a classe for interrompida) e no simulado.**
- Status: CUMPRIDO
- Explicação: `logica/sessao_io.py::ArquivoDaClasse` (acumulador por classe, vive na `Bancada`); `mestre.py`: `_arquivo_da_classe`, `_iniciar_gravacao_incremental`, `_salvar_captura`, `_finalizar_gravacao`, `_gravar_arquivos_da_classe`, `_salvar_classe_simulada`. Atomicidade: todos os `.part` (classe, cada `snr_XXdb/`, `corrente/`) são escritos antes de qualquer `os.replace`. Resiliência: cada captura vai antes para `parcial/NN_classe/<perfil>__NNNNNN.npz` (atômica); o `.npz` da classe + o metadata são reescritos inteiros ao fim de cada perfil e no `except BaseException` de `executar()` (interrupção por exceção, Ctrl+C, falha de infraestrutura), perfis anteriores incluídos; se a consolidação em si falhar, o erro original não é mascarado e o spool fica. Morte do processo: `sessao_io.recuperar_parcial(<sessao>)` promove o spool preservando os outros perfis (função manual; ver pendências). Testes: `test_interrupcao_no_meio_do_segundo_perfil_preserva_tudo_o_que_ja_foi_capturado`, `test_morte_do_processo_deixa_o_spool_e_recuperar_parcial_promove_sem_perder_perfis`, `SalvamentoIncrementalTests` (atualizados: spool visível a cada captura, 2 capturas preservadas após falha).

**Item 3 — Implementar `set perfil todos` (o `run all`/`run <lista>` percorre norma, literatura e fronteira na mesma sessão, com o total de capturas e gravações de TRACe somado na confirmação).**
- Status: CUMPRIDO
- Explicação: `mestre.PERFIL_TODOS` (+ env `PERFIL=todos`), `perfis_da_rodada()`, `Bancada.executar_bateria(scripts, perfis_da_rodada_=None)` (cada classe uma vez por perfil, ordem norma, literatura, fronteira; mesmas tentativas e mesmo aborto em `CommunicationError`/`FalhaFatalDeInstrumento` por (classe, perfil); `ResultadoClasse.ok` só se todos os perfis foram, `motivo` diz o perfil), `Bancada.executar_classe_nos_perfis` (para `run <NN>`, que também percorre os três). CLI: `set perfil norma|literatura|fronteira|todos`, `status`, `HELP_TEXT`, `_capturas_das_classes` (soma por perfil, porque o número de níveis muda com o perfil), confirmações de `run all`/`run <lista>`/`run <NN>` com o total somado e "somadas nos 3 perfis". As strings digitadas (`EXECUTAR-20-CLASSES`, `EXECUTAR-CLASSES-...`, `EXECUTAR-CLASSE-NN`) não mudaram. Exemplo real (CLI simulada, `set perfil todos` + `status`): TRACe passou de 468 para 1404 gravações. Testes: `test_confirmacao_do_run_all_soma_capturas_e_trace_dos_tres_perfis`, `test_run_all_com_todos_roda_cada_classe_uma_vez_por_perfil`, `test_set_perfil_todos_na_cli`, `test_perfis_rodam_em_ordem_e_a_falha_de_um_nao_apaga_os_outros`.

**Item 4 — Migrar todos os consumidores para o formato novo, mantendo leitura das sessões antigas (um `.npz` por captura) quando custar pouco; onde não for mantida, dizer qual quebra. `relatorio_html.py` ganha seleção por `--classes`, `--perfis`, `--versoes` e `--capturas`.**
- Status: CUMPRIDO
- Explicação (consumidores e o que mudou em cada um):
  - `logica/sessao_io.py` (NOVO): ponto único de leitura dos DOIS formatos: `ler_pasta`, `ler_capturas`, `CapturaSessao`, `carregar_metadados` (`MetadadosDaSessao`: continua um `dict` por id e ganhou `.buscar(perfil, id)`), `parsear_selecao_capturas`, `formato_do_arquivo`, `recuperar_parcial`.
  - `logica/recortar_margem.py`: lê os dois formatos, grava SEMPRE o formato 2 em `sem_margem/` (recortar uma sessão antiga também a converte; modelo/programada do `tres_versoes/` antigo entram); `--empilhar` virou no-op (aceito). `carregar_metadados` agora delega a `sessao_io`. QUEBRA: a saída `sem_margem/` não tem mais `NN_classe_<rótulo>.npz` por captura nem `empilhado/`.
  - `logica/relatorio_html.py`: usa `sessao_io`; novos `--perfis`, `--versoes` (a 1.ª é o traço principal, as outras vão tracejadas), `--capturas` (ids `02-0003`, posições `3`, intervalos `1-3`); `--classes` e `--max-capturas-por-classe` (agora por classe E perfil) mantidos; o limite padrão de 3 capturas vale só para o simulado (numa sessão de bancada, agora empilhada por classe, entram todas; testado). Título `NN_classe · perfil · id`.
  - `logica/analisar_sessao.py`: itera por captura/perfil via `sessao_io`; rótulo `arquivo:perfil:id` no formato 2 (formato 1: o nome do arquivo, como antes); o simulado vira um erro por arquivo e perfil (como o teste antigo exigia para o empilhado).
  - `scripts/gerar_ruido_janela.py`: lê os dois formatos; a saída segue a entrada (formato 2 -> `snr_XXdb/NN_classe.npz` com `<perfil>/tensao_pu`; formato 1 -> como antes). Metadata de saída casado por (perfil, id).
  - `scripts/gerar_tres_versoes.py`: formato 1 como sempre; RECUSA o formato 2 (`ValueError` claro), porque as três versões já estão no `.npz`. QUEBRA declarada: não regenera três versões de sessão nova.
  - `scripts/recalibrar_extremos.py`: não lê `.npz` (só `metadata/*.jsonl`); nenhuma mudança necessária. Com `todos` o mesmo `id` aparece 3 vezes no jsonl e a coleta apenas acumula fatores: sem problema.
  - `tests/test_offline.py`: ver cabeçalho.
  - Ressalva ao `git grep` da spec: `logica/oscilloscope_orm.py` só cita `.npz` em comentário.
  - Como `scripts/diag_ciclos_trace.py` e `scripts/verificar_sessao_bancada.py` (outras specs, não existem neste worktree) devem usar o leitor (`logica/sessao_io.py`):
    ```python
    sys.path.insert(0, str(PROJECT_ROOT / "logica")); import sessao_io
    for c in sessao_io.ler_capturas(sessao_dir, classes=["02"], perfis=None,        # None = todos os perfis
                                    versoes=("medida", "modelo", "programada")):
        c.classe_id, c.classe, c.perfil, c.id_captura   # (perfil, id) é a chave única da captura
        registro = c.versoes["medida"]                   # 8100 amostras na bancada (com a folga); c.inicio_janela = onde começa a janela de 6000
        modelo, programada = c.versoes.get("modelo"), c.versoes.get("programada")   # 6000 amostras; ausentes se NaN
        c.metadado                                       # a linha do metadata DO PERFIL certo (não use um dict id -> linha)
    snr = sessao_io.ler_capturas(sessao_dir, subpasta="snr_30db")   # c.sinal = janela com ruído; "corrente" idem
    ```
    Funciona igual em sessão antiga (um `.npz` por captura + `tres_versoes/`, perfil `literatura` ou o do metadata). Evitar `glob("*.npz")` + `dados["tensao_pu"]`. Se o script só precisa de metadata, `sessao_io.carregar_metadados(sessao_dir).buscar(perfil, id)`. Para a "TRACe por ciclo" (diag_ciclos_trace), `c.versoes["programada"]` já é o `programada_pu()` por ciclo do formato novo e o metadata traz `pico_programado_v`.

**Item 5 — Registrar em `CHANGELOG/v1.15.md` (seção nova no fim), com aviso destacado de quebra para quem lia os `.npz` individuais, e atualizar `docs/dataset.md`, `docs/metadata.md` (só acrescentar campos), `docs/tres_versoes.md` e `AGENTS.md` (autorização).**
- Status: CUMPRIDO
- Explicação: seção "Um `.npz` comprimido por classe, com perfis e versões; `set perfil todos` (2026-10-13, spec 17, mesma versão)" no fim de `CHANGELOG/v1.15.md`, começando por um bloco `> ### AVISO DE QUEBRA`, com Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO. `AGENTS.md`: "Autorização de 2026-10-13" (inclui `logica/recortar_margem.py` e `logica/relatorio_html.py`). `docs/dataset.md` (reescrita das seções 1, 2, 4 e da tabela de ferramentas, com a mesma nota de quebra), `docs/metadata.md` (só acrescentado, e a frase sobre o `.jsonl.part` corrigida para o novo comportamento), `docs/tres_versoes.md`, e de bônus coerência em `docs/operacao.md`, `docs/perfis.md`, `docs/arquitetura.md`, `docs/decisoes.md`.

## Critério de Parada
Atendido. Sessão simulada com `set perfil todos` (`NpzPorClasseTests`) tem um `.npz` comprimido por classe com as 9 chaves perfil x versão, as SNRs fora dele (`snr_20db/`, `snr_30db/`), sem `.part`, `parcial/` nem `tres_versoes/`; blocos iguais bit a bit (valores e dtype) a uma rodada de um perfil só. Todos os consumidores listados leem o formato novo (testes de `recortar_margem`, `analisar_sessao`, `relatorio_html` com seleção de classe/perfil/versão/captura, `gerar_ruido_janela`, `gerar_tres_versoes` recusando) e a sessão antiga continua legível (`test_sessao_antiga_continua_legivel...`, `RecorteMargemERelatorioHtmlTests`). Aviso de quebra no CHANGELOG. Suíte: 431 OK, 0 falhas (linha de base 412 OK).

## Pendências que exigem o usuário
- Decidir se classes que NÃO dependem do perfil (01, 04, 07, 08, 09, 17, 18, 19) devem rodar uma vez só num `todos`: hoje rodam três vezes (triplica tempo e escritas de Flash da AMETEK, mesmas seeds e ids). Foi o que o pedido descreve; não otimizei.
- Decidir se `recuperar_parcial` deve ser chamada automaticamente no início de um `run` (hoje é função manual).
- Sessão de bancada real para validar o formato novo (nenhuma feita; só simulada e bancada com stubs).

## Limitações de escopo
Nenhuma que tenha impedido o resultado. (Os scripts `diag_ciclos_trace.py` e `verificar_sessao_bancada.py` não existem no worktree: não migrados, como combinado; instruções de uso acima.)

## A missão resolve o contexto?
Sim: uma classe passa a ter um só arquivo com perfis x versões, o HTML seleciona o que montar e o `run all` percorre os três perfis. Nada do que achei muda a missão; a quebra do formato é a prevista.

## Achados
- (Médio, decisão) `set perfil todos` triplica também as classes independentes de perfil; ver pendências.
- (Médio, NÃO VERIFICADO) Tamanho e custo de reescrita do `.npz` da classe com medida física real (ruído de bancada comprime menos que o simulado): medido só no simulado (classes 02 e 10, 200 capturas x 3 perfis: 33,8 e 31,1 MiB contra 82,6 MiB crus; 3 `snr_XXdb/` somam 78,6 MiB; 32 s para 1200 capturas). A reescrita acontece só no fim de cada perfil e ao interromper, nunca por captura.
- (Baixo) O mesmo `id_captura` existe nos três perfis (a seed não depende do perfil): a chave única passou a ser `(perfil, id_captura)`. `recortar_margem.carregar_metadados` ainda devolve dict por id (último vence) para compatibilidade; consumidores novos usam `.buscar`.
- (Baixo) A ordem de leitura do formato 1 é alfabética por nome de arquivo (`cap01`, `sag_pu-0.1`...), não a de captura; `recortar_margem` ordena por id ao converter.
- (Baixo) Em sessão de bancada com `Mock` de bancada (testes), `getattr(dono, "_manter_arquivos_classe", False)` devolve um Mock truthy e o acumulador não é liberado: só afeta testes.
- (Info) Removida a limpeza de órfãos por captura (nome fixo, não há órfãos); `_rotulo_da_captura` foi removido. Sessões antigas em `resultados/` não foram tocadas.
- (Info) Mensagens de commit usam as linhas Co-Authored-By/Claude-Session do `blocos_comuns.md`; o lembrete do harness cita outro nome de modelo na linha Co-Authored-By. Segui o bloco comum.
