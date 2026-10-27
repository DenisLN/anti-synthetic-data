## Análise do orquestrador

- Implementação completa? Sim. Conferido: nenhum diff em `experimentos_*`, `logica/` nem `tests/fixtures/` contra `origin/main` antes da spec; as 20 fichas usam `aviso-base`; selos com âncora `estado-p-NN` (ex.: `docs/classes/05-harmonics.md:7`); build `-E -W -n` exit 0; suíte `Ran 800 tests`, `OK (skipped=2)`. Enviado à `main` (`0abb35f`).
- Pendências do usuário: só as confirmações de P-03/P-10/P-11/P-12 e P-07, já na lista consolidada da spec 34.
- Escopo limitou? Pouco: tabelas de limites de 220 V/60 Hz e simuladas de 07/17 não refeitas (fichas avisam).
- Resolve o contexto? Sim.
- Critério de Parada: atendido.
- Classificação: sem-pendencias.

# Relatório: ASD: Fichas das Classes Atualizadas com as Mudanças nos NN.py

Commits locais na `main` (sem push): `522aed2` (fichas, `classes.md`, `classes_contrato.md`, `metadata.md`), `6c1f36b` (teste novo da 19), `0abb35f` (CHANGELOG). Base: `7efd26e`.

## Missão, item a item

**Item 1 — Refazer o diff completo dos `NN.py` entre `fa82f49` e a `main` (não confiar só na tabela do Contexto) e listar no relatório, por classe, cada mudança com `arquivo:linha` e se altera o que `gerar()` produz para uma seed (conferir com os testes byte a byte e as fixtures; para a 19, verificar a equivalência de `_offset_da_captura` com um teste ou comparação de saída).**
- Status: CUMPRIDO
- Explicação: `git diff --stat fa82f49 main -- experimentos_nativos experimentos_waveform logica/sinais.py logica/calibracao_extremos.json` dá seis arquivos de classe (a tabela do Contexto estava completa) mais `sinais.py` (+28) e a calibração (34 linhas). `git log fa82f49..main` nos diretórios de classe: `58130af`, `8603c20`, `e7f43aa`, `230740d` (este só mexeu em 2 linhas de comentário da `08.py`). As 14 outras classes não têm diff. Lista, com linhas da `main`:
  - 05: `experimentos_nativos/05.py:72-74` `rota_programacao` ("TRACe" se `usar_trace`, senão "CSIN"; sobrescreve `mestre.py:2300`; gravado em `mestre.py:3431`). Não altera `gerar()`.
  - 06: `experimentos_waveform/06.py:7` (import de `AmetekMX30`) e `06.py:19-44` `forma_esperada_para_validacao` (usa `_versoes_atuais["programada"]` se válida, `06.py:24-33`; senão reconstrói por `AmetekMX30.montar_programacao(...).programada_pu()`, `06.py:34-44`). Não altera `gerar()`.
  - 08: `experimentos_waveform/08.py:61-64` `SOBRESSINAL_ACHADO_DE_SEGURANCA = 0.55`; `08.py:206-228` métrica de sobressinal em `conferir_posicao_do_evento` (`max(medido − senoide)/A − 1`; grava `sobressinal_medido`, `sobressinal_limite`, `sobressinal_acima_do_limite`, ou `None` + `sobressinal_invalido`; não reprova a captura; ressalva de 30 kSa/s em `08.py:215-217`). Não altera `gerar()`.
  - 15: `experimentos_waveform/15.py:26-53` `parametros_com_disturbio_reduzido` (f·d, f·thd, mín./máx. da THD e dois coeficientes de envelope; `ValueError` fora de 0≤f≤1, 0≤d<1, thd finita ≥ 0). Não altera `gerar()`.
  - 18: `experimentos_nativos/18.py:45-53` `exigencias_nativas` (`frequencia_hz`, `dwell_s`, `passos_list`). Não altera `gerar()`.
  - 19: `experimentos_nativos/19.py:32-41` `_offset_da_captura`, `19.py:43-45` `exigencias_nativas`, `19.py:47-52` `configurar` refatorado. Não altera `gerar()`.
  - Fora dos `NN.py` que as fichas citam: `logica/sinais.py` `distancia_modelo_programada` (função nova, sem chamada em classe); `logica/calibracao_extremos.json` (tabela 127 V/60 Hz: 16 fatores mudaram, entre eles 07 = 1,615, 17 = 1,575; a tabela de 50 Hz não mudou desde `fa82f49`).
  - **Evidência de que `gerar()` não mudou:** (a) `git diff fa82f49 main --stat -- tests/fixtures` vazio; `python -m unittest tests.test_offline.PerfisDeFaixasTests -v`: 10 testes, OK. (b) Comparação de saída extraindo as duas árvores com `git archive`: 20 classes × 36 chamadas (sorteio ligado/desligado, 60/50 Hz, índices 0 a 2, seeds 1, 123 e 20260827) = 720 chamadas; hash SHA-256 por classe (bytes da forma + parâmetros em JSON) idêntico nas duas árvores (script `cmp.py` e saídas `cmp_old.json`/`cmp_new.json` no scratchpad). (c) 19: as mesmas árvores, 24 chamadas de `configurar()` (4 configurações de tensão/semente/`capturas_override`, índices 0 a 5), retorno e chamadas à fonte idênticos; e teste novo `tests/test_classe19_offset.py` (2 testes, OK) que compara `configurar()` e `exigencias_nativas()` com a fórmula em linha de `fa82f49` em cinco configurações. Nenhuma mudança de `gerar()` não declarada.

**Item 2 — Atualizar a ficha de cada classe alterada (05, 06, 08, 15, 18, 19, e qualquer outra que o item 1 encontrar) com o comportamento atual: ganchos novos, métricas novas (sobressinal da 08 e a ressalva de amostragem a 30 kSa/s), rota de programação da 05, parâmetros reduzidos da 15, comparação com a programada da 06.**
- Status: CUMPRIDO
- Explicação: subseção "Mudanças no código desde `fa82f49`" (antes de "Referências") em `docs/classes/05-harmonics.md`, `06-flicker.md`, `08-transient.md`, `15-harmonics-flicker.md`, `18-frequency-drift.md` e `19-dc-offset.md`, com `arquivo:linha`, o efeito e a declaração de que `gerar()` não mudou. Na 08: sobressinal, limite 0,55, flags, "não reprova a captura" e a ressalva de 30 kSa/s (oscilação de ~10 kHz, ~3 amostras por período, pode subestimar o pico). Na 15 a subseção substituiu a seção "Atualização de metadata P-11" e três trechos que diziam "sem gancho de bancada". Nenhuma outra classe teve diff (item 1). Além disso as fichas 02, 03, 04, 05, 08, 18 e 19 tiveram o parágrafo "Estado:" reescrito com o que o fechamento de 22/10 registra, e a 05 teve as linhas "Verificação" (2/10/15/20 % por CSIN e 30 % por TRACe passaram a verificados em 22/10, `fechamento.json`).

**Item 3 — Atualizar em todas as 20 fichas os selos e menções de pendência para que batam com o arquivo de estado (citando a âncora da página de pendências), e os fatores de extremo citados com o valor atual de `logica/calibracao_extremos.json`.**
- Status: CUMPRIDO (com a ressalva em "Limitações de escopo")
- Explicação: (1) banner "fa82f49 / 16-10" trocado nas 20 pelo include `docs/_includes/aviso-base.md`. (2) Linha de selos: `PENDENTE P-NN` virou `{bdg-ref-<cor>}` com rótulo e cor de `docs/_ext/estado_pendencias.py:ESTADOS` aplicados ao `estado_prontidao.json`, apontando para `estado-p-NN`; P-03, P-10, P-11 e P-12 saem de "pendente" e aparecem "Concluída, dono ainda não confirmou" (situação `tomada-no-fork`); 05 e 08 (`NÃO VERIFICADO`) corrigidos. (3) Blocos "Pendência P-NN"/"Decisão em aberto P-NN" regerados do JSON (estado, situação, falta por tipo, ressalva do dono, nota da classe), inclusive P-04 e P-23, que estavam descritos como decisão em aberto. (4) Todas as `{ref}` `p-NN` passaram a `estado-p-NN`; `grep` por `PENDENTE` e `<p-NN>` nas fichas: vazio. (5) Verificação automática (script no próprio relatório do item, abaixo): para cada ficha, todo selo e todo bloco bate em cor e rótulo com o JSON; 0 divergências. (6) Fatores: citações na prosa e as linhas de 127 V/60 Hz e 220 V/60 Hz das tabelas de limites (34 linhas) com a calibração atual; o gerador de linhas, rodado sobre `fa82f49`, reproduziu as 80 linhas antigas sem diferença antes de ser aplicado à `main`.

  Tabela de conferência das 20 classes (selos = estado no JSON em 2026-10-27; todos com âncora `estado-p-NN`; 0 divergências):

  | Classe | Selos na ficha (estado no JSON) |
  |---|---|
  | 01 | P-01 aguarda-bancada; P-05 aguarda-decisao |
  | 02 | P-01 aguarda-bancada; P-05 aguarda-decisao |
  | 03 | P-01 aguarda-bancada; P-05 aguarda-decisao |
  | 04 | P-01 aguarda-bancada; P-05 aguarda-decisao |
  | 05 | P-01 aguarda-bancada; P-10 concluida (fork); P-18 aguarda-bancada; P-19 insuficiente-bancada |
  | 06 | P-01; P-12 concluida (fork); P-18; P-19 |
  | 07 | P-01; P-07 aguarda-decisao; P-18; P-19 |
  | 08 | P-01; P-02 reprovada-bancada; P-03 concluida (fork); P-18; P-19 |
  | 09 | P-01; P-02 reprovada-bancada; P-18; P-19 |
  | 10 | P-01; P-08 reprovada-bancada; P-09 aguarda-decisao; P-11 concluida (fork); P-18; P-19 |
  | 11 | P-01; P-08; P-09; P-11 concluida (fork); P-12 concluida (fork); P-18; P-19 |
  | 12 | P-01; P-08; P-09; P-11 concluida (fork); P-18; P-19 |
  | 13 | P-01; P-11 concluida (fork); P-18; P-19 |
  | 14 | P-01; P-11 concluida (fork); P-18; P-19 |
  | 15 | P-01; P-11 concluida (fork); P-12 concluida (fork); P-18; P-19 |
  | 16 | P-01; P-08; P-09; P-11 concluida (fork); P-18; P-19 |
  | 17 | P-01; P-07 aguarda-decisao; P-18; P-19 |
  | 18 | P-01; P-06 aguarda-bancada |
  | 19 | P-01; P-17 aguarda-decisao |
  | 20 | P-01; P-18; P-19 |

  Menções fora dos selos (P-21, P-23, P-26, P-27, P-04, P-09, P-17...) foram conferidas uma a uma; duas estavam desatualizadas e foram corrigidas (05: "280 por conexão" virou o orçamento de 216, `logica/politica_traces.py:3`; 19: "ACDC a 230 V é do dia de bancada" virou a resposta do dono de 21/10 na P-26, ACDC só a 127 V).

**Item 4 — Acrescentar a `docs/metadata.md` os campos novos de metadata que as classes passaram a gravar (só acrescentar) e conferir `docs/classes.md` e `docs/codigo/classes_contrato.md` contra os ganchos novos.**
- Status: CUMPRIDO
- Explicação: `docs/metadata.md`: duas linhas novas (nada removido ou editado): `validacao_fisica.posicao_evento.sobressinal_invalido` (08, `08.py:222-224`) e os seis campos do gancho da 15 (`flicker_depth_bancada`, `thd_bancada_centro/min/max`, `harmonicos_envelope_centro_bancada/modulacao_bancada`, com as fórmulas de `15.py:26-53`). `rota_programacao` e `sobressinal_medido/limite/acima_do_limite` já estavam (linhas 80-81). `docs/classes.md`: seção 7 nova com os seis ganchos, arquivo:linha e link para cada ficha, mais nota sobre a conta da seed da 19 agora em `_offset_da_captura`. `docs/codigo/classes_contrato.md`: tabela §2 com os métodos novos de 05, 06, 08, 15, 18 e 19; tabela §3 com a linha de `parametros_com_disturbio_reduzido` corrigida (a 15 deixou de ser a exceção) e três ganchos novos (`exigencias_nativas`, `rota_programacao`, `forma_esperada_para_validacao`, com quem chama e quem sobrescreve); §4 com a nota da 19.

**Item 5 — Registrar em `CHANGELOG/v1.15.md`.**
- Status: CUMPRIDO
- Explicação: seção "Fichas das classes atualizadas com as mudanças nos `NN.py` (2026-10-27, mesma versão)" ao fim, com Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO (commit `0abb35f`).

## Critério de Parada

Atendido.
- Cada `NN.py` com diff (05, 06, 08, 15, 18, 19) tem a mudança citada com `arquivo:linha` na subseção da ficha correspondente (item 2).
- Nenhuma ficha tem selo que contradiga o arquivo de estado: tabela de conferência acima; script de verificação compara cor e rótulo de todos os selos e blocos com o JSON, 0 divergências; `grep PENDENTE` e `<p-NN>` nas fichas vazios.
- `docs/metadata.md` tem os campos novos (item 4).
- Verificação: `python -m unittest discover -s tests -p "test*.py"`: 800 testes, OK (skipped=2); base 798 OK (skipped=2) + 2 novos, nenhum teste existente mudou de resultado. `sphinx-build -E -W -n --keep-going -b html docs <scratchpad>`: `build succeeded`, 0 avisos. `tests.test_offline.PerfisDeFaixasTests`: 10 OK.

## Pendências que exigem o usuário

- Confirmar (ou não) as escolhas do fork que as fichas agora mostram como "Concluída, dono ainda não confirmou": P-03, P-10, P-11, P-12 (e P-04, P-27 nos blocos). O texto das fichas já aponta para essas perguntas em `docs/projeto/pendencias.md`.
- Revisar o diff de calibração das 07/17 (P-07): as fichas dizem que o fator 1,615/1,575 só vale depois da revisão e de nova coleta.

## Limitações de escopo

- Os resultados por classe das 159 capturas de 22/10 estão no PC da bancada, fora do repositório. As fichas repetem só o que `fechamento.json` e `estado_prontidao.json` dizem e marcam o resto como NÃO VERIFICADO; não inventei números por classe.
- As tabelas "Limites físicos" das fichas são um snapshot de 16/10: regerei só as linhas de 127 V/60 Hz e 220 V/60 Hz (as únicas que a mudança de calibração afeta; as de 50 Hz seguem iguais). Os parâmetros `*_bancada` das capturas reduzidas a 220 V/60 Hz (10, 12, 16) não foram recalculados; as fichas avisam. As tabelas simuladas "O que esperar da primeira rodada" das fichas 07 e 17 também não foram refeitas (têm aviso de atualização).
- Permalinks com número de linha para `fa82f49` nas tabelas "Como o código da classe funciona" ficaram como histórico (o banner de base já avisa); os números atuais estão nas subseções novas.
- Não alterei `docs/projeto/estado-validacao.md`, `docs/arquitetura.md` nem `docs/estado_prontidao.json` (fora do pedido); ver Achados.

## A missão resolve o contexto?

Sim: quem abre a ficha de uma das seis classes alteradas vê o que o código dela faz hoje (com linhas), e as 20 fichas mostram o estado real de cada pendência, com link para a âncora viva, e os fatores atuais. O pedido foi bem formulado; o que a tabela do Contexto previa se confirmou.

## Achados

- (Média, informativa) Com a recalibração de 22/10, a 14 a 127 V/60 Hz passa a rodar com distúrbio reduzido em duas das três capturas (`k` de 92 a 100 %; fator 1,200, antes 0,977). A 220 V/60 Hz as classes 06, 09, 13, 17 e 20 passam a ser puladas nas três capturas (fator conservador 1,615 em vez de 1,475); isso decorre da regra de `carregar_fatores_extremo` e está registrado nas fichas e na P-21.
- (Baixa) `docs/projeto/estado-validacao.md` (§4, linhas ~87-104) ainda lista P-11 em 10 a 16, P-12 na 06 e "sem `parametros_com_disturbio_reduzido`" na 15, contradizendo o JSON e o código; e `docs/arquitetura.md:91` omite a 15 da lista de quem sobrescreve o gancho. Não toquei (fora do escopo pedido).
- (Baixa) `docs/estado_prontidao.json`, P-10, `falta_por_tipo.codigo` pede "atualizar o selo `PENDENTE P-10` de `05-harmonics.md:8`": isso foi feito agora; o item pode sair do JSON na próxima revisão do arquivo de estado (omiti essa linha no bloco da 05).
- (Baixa) `SOBRESSINAL_ACHADO_DE_SEGURANCA` (0,55) e `SOBRESSINAL_DO_DEGRAU` (0,55) têm o mesmo valor por coincidência de projeto; grandezas e usos distintos (limite medido x dimensionamento do impulso). Documentado na ficha da 08.
- (Baixa) Erro de LaTeX preexistente em `docs/classes/19-dc-offset.md:78` (`$\delta pprox ...` por `\approx` mutilado), não corrigido.
- (Informativa) Sugestão fora do pedido: um teste em `tests/` que compare selos e blocos das fichas com `estado_prontidao.json` evitaria a deriva; a verificação que fiz foi um script avulso.
- NÃO VERIFICADO: a condição (V/Hz) da sessão `2026-10-22_14-38-28` da P-10 (o fechamento não diz); resultados por classe das sessões de 22/10; renderização no Read the Docs (só build local `-W`).
