## Análise do orquestrador

- Implementação completa? Sim. Conferido: `docs/estado_prontidao.json` esquema 3, 31 pendências (11 concluídas, 8 aguarda-bancada, 9 aguarda-decisão, 2 reprovadas, 1 insuficiente); P-02/P-08 `reprovada-bancada`, P-19 `insuficiente-bancada`, P-16 `aguarda-bancada`, P-25 `aguarda-decisao`; build `-E -W -n` exit 0; `tests.test_estado_pendencias` OK. Ajuste do mapa (`7efd26e`) conferido: callouts de P-02/P-19 corretos e regeneração sem diff. Tudo na `main` (`7efd26e`).
- Pendências do usuário: as 21 perguntas ao dono são o próprio entregável (item 5) e vão consolidadas no relatório final; não são falha da spec.
- Escopo limitou? Não. O achado "alta" (`docs/projeto/estado-validacao.md` desatualizado no conteúdo) ficou fora do escopo e vai como sugestão.
- Resolve o contexto? Sim.
- Critério de Parada: atendido.
- Classificação: sem-pendencias.

# Relatório: ASD: Página de Pendências com Estado e Resolução de P-01 a P-31

Commits locais na `main` (sem push): `081aa5b` (esquema 3 e revisão dos estados), `e583c41` (página viva), `3129844` (CHANGELOG). Base: `7262dfc`.

## Missão, item a item

**Item 1 — Revisar o estado de cada uma das 31 pendências no arquivo único conforme as evidências (usar o relatório de achados como ponto de partida e conferir cada afirmação dele nos arquivos de `docs/evidencias/` e no código), incluindo o estado "reprovada na bancada" para P-02 e P-08, "insuficiente" para P-19, e tirando P-16 e P-25 de concluída.**
- Status: CUMPRIDO
- Explicação: `docs/estado_prontidao.json` revisado nas 31 pendências, com as afirmações do relatório conferidas em `fechamento.json`, `LEIA-ME.md`, `pc_bancada.json` (21 e 22/10), `diag_list_offset.json`, `visita_estado.json`, `calibracao_extremos.json` e no código atual (linhas na tabela abaixo e nos blocos). P-02 e P-08 passaram a `reprovada-bancada` (estado que já existia e ninguém usava). Para P-19 não havia estado "insuficiente": acrescentei `insuficiente-bancada` ao esquema (`docs/_ext/estado_pendencias.py`, validação e testes). Usei só para P-19: é medida feita e inconclusiva; P-01, P-06, P-21 e P-23 também têm `insuficiente` no `fechamento.json`, mas lá significa "ainda não medido", então ficam `aguarda-bancada`. P-16 e P-25 saíram de concluída. P-09 passou a `aguarda-decisao`. Placar: 11 concluídas, 8 aguardam bancada, 9 aguardam decisão, 1 insuficiente, 2 reprovadas (total 31); antes 13, 11 e 7.
- Conferência de afirmações do relatório de achados: confirmadas as de P-02, P-03, P-08, P-09, P-10, P-16, P-19, P-21. Corrigidas ou completadas as seguintes. P-13: o relatório não sabia se a recuperação automática foi implementada; foi (`logica/cli.py:339` chama `sessao_io.recuperar_sessoes_interrompidas`, `sessao_io.py:674`). P-25: `docs/limites_e_calibracao.md:51` já não traz "spec 26" (corrigido hoje em `dafde1f`/`9ce09b4`), mas restam "spec NN" em `tests/test_offline.py` (3208, 6829, 6992, 7505, 9155, 9272) e em `logica/`. P-21: o relatório diz que a 08 "não tem fator"; é desenho (`calibracao_extremos.json`, `observacao_08`: a 08 usa `forma_para_bancada()`), e o critério do agregador (20 classes) conflita com isso. P-24: 764 ocorrências `blob/fa82f496` em `docs/**/*.md` na `main` (o relatório contou 1136 no branch de feature).

**Item 2 — Escrever, para cada P-NN, o bloco "como foi resolvida / o que foi feito": mudança de código com commit e `arquivo:linha`, sessão ou evidência, resultado medido; e "o que falta", separando trabalho de bancada, de código e decisão do dono.**
- Status: CUMPRIDO
- Explicação: campos novos obrigatórios nas 31 (validados): `como_tratada` ("Como foi resolvida ou o que foi feito", com commit, `arquivo:linha`, sessão e resultado medido; as pendências não resolvidas começam com "Até agora") e `falta_por_tipo` com chaves `bancada`, `codigo`, `decisao-dono` (nas não concluídas, as mesmas de `quem_fecha`). A página gerada mostra "O que falta" em sub-itens por tipo. `commits` e `evidencias` preenchidos (todos os caminhos existem; o teste valida). Limite: a base é `fechamento.json` e o repositório; sessões físicas de 22/10 ficam no PC da bancada, então valores como "−16 amostras na sessão 15-19-56" são do relato (NÃO VERIFICADO, ver Achados).

**Item 3 — Marcar explicitamente, em cada pendência, se a escolha feita no fork foi confirmada pelo dono (citar onde) ou está tomada no fork, aguardando confirmação (P-03, P-04, P-10 a P-15, P-25, P-27 e as demais em que se aplicar), e registrar o conflito da P-09 como pergunta ao dono.**
- Status: CUMPRIDO
- Explicação: `decisao_dono.situacao` obrigatória (`confirmada`, `tomada-no-fork`, `em-branco`, `nao-se-aplica`), com `registrada` coerente (só verdadeira se confirmada, com data e fonte no texto). Confirmadas, citando `docs/decisoes_pendentes.md` seção P-NN e data: P-01 (quantidade por célula, via P-26), P-09, P-26, P-29, P-30. Tomada no fork, aguardando confirmação: P-03, P-04, P-10, P-11, P-12, P-13, P-14, P-15, P-27 (concluídas, 9) e P-07, P-18, P-21, P-23, P-25, P-31 (abertas). Em branco: P-05, P-17, P-20, P-22, P-28. P-09 fica `confirmada` (21/10) com a pergunta do conflito: fechar agora como limitação aceita com (d), como no plano, ou exigir antes os braços A e B (condição do plano cumprida: `-113` em `diag_list_offset.json`). A página mostra "das 11 concluídas, 9 aguardam a confirmação do dono" e a pergunta de cada decisão. Ver Achados sobre P-18, P-23 e P-31 e sobre P-21.

**Item 4 — Reescrever `docs/projeto/pendencias.md` como página viva (título sem "inventário histórico"; o inventário de 16/10 vira seção "Pedido original" por P-NN ou vai para uma página histórica ligada a ela), e fazer `docs/projeto/estado-validacao.md` e `docs/index.md` apontarem para ela com o placar correto.**
- Status: CUMPRIDO
- Explicação: `docs/projeto/pendencias.md` reescrita (título "Pendências P-01 a P-31: estado, resolução e perguntas ao dono"). O inventário foi movido por `git mv` para `docs/projeto/pendencias-inventario-2026-10-16.md` (no toctree de `docs/index.md`), com as âncoras `p-NN` intactas (as páginas de classe continuam resolvendo); cada seção histórica ganhou link para `estado-p-NN`, e cada seção viva traz "Pedido original" com link para a histórica. Placar: marcador novo `@@pendencias-placar@@` (extensão `docs/_ext/pendencias.py`) substitui uma linha gerada do arquivo em `docs/index.md`, `docs/projeto/estado-validacao.md` e `docs/visao-geral.md` (esta tinha "31 abertas (17 de bancada, 13 de decisão, 1 de código)"). Assim o número nunca diverge do JSON. `estado-validacao.md` teve ainda as referências `{ref}P-NN` retargetadas para `estado-p-NN`. `como-ler.md`: uma frase corrigida (a seção "Resolvidas" não existe mais na página viva). `docs/contribuir_docs.md` §5 e `docs/PENDENCIAS_TRACKER.md` atualizados para o esquema 3.

**Item 5 — Gerar no relatório a lista consolidada de perguntas ao dono (uma linha por decisão pendente, com as opções que o formulário já oferece) e registrar a revisão em `CHANGELOG/v1.15.md`.**
- Status: CUMPRIDO
- Explicação: a lista está em "Pendências que exigem o usuário" (21 linhas) e também na página gerada ("Perguntas ao dono", gerada do JSON, com a fonte das opções). Registro em `CHANGELOG/v1.15.md`, seção "Página de pendências com estado e resolução de P-01 a P-31 (2026-10-27)" (Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO). Onde o formulário não tem seção (P-03, P-04, P-05, P-07, P-10 a P-15, P-17, P-22, P-25, P-27, P-28), as opções vêm do inventário, da evidência ou são propostas minhas, e a fonte vem rotulada na página (`fonte_opcoes`).

### Tabela: estado antes (rastreador de 22/10) × depois

Legenda de "antes": C = concluída, B = aguarda bancada (🔧→🏭), D = aguarda decisão (❓).

| P-NN | Antes | Depois | Evidência que justifica |
|---|---|---|---|
| P-01 | B | B (bancada + código) | `fechamento.json`: 2 de 5 condições, 159 capturas, 19 reprovações de validação física; critério de quantidade sem limite; P-26 já diz 1 captura por classe |
| P-02 | B | **reprovada-bancada** | `fechamento.json` `reprovado`: `posicao_08_desvio_amostras` 16 > 10; hipótese da cópia sem critério |
| P-03 | C | C (escolha tomada no fork) | `fechamento.json` 3/3: desvio 2, pico 339 V, sobressinal 0,295; nota "evidência suficiente não é encerramento"; `experimentos_waveform/08.py:64` |
| P-04 | C | C (tomada no fork) | `logica/ametek_orm.py:1427,2105` recusam; baseline só avisava (`fa82f49:logica/ametek_orm.py:1525`) |
| P-05 | D | D (em branco) | `LEIA-ME.md`: pre-trigger +5/−1/−2/−6/+6 amostras; `fechamento.json` aviso 6 > 2 |
| P-06 | B | B | `fechamento.json`: 0 capturas 47→53 Hz, salto de fase `sem_dados` |
| P-07 | D | D (tomada no fork) | `calibracao_extremos.json:16,25` (1,615 e 1,575); `fechamento.json` revisão humana pendente |
| P-08 | B | **reprovada-bancada** | `fechamento.json` `reprovado`: razão máx. 1,297 (12: 264 V contra 203,5 V); `LEIA-ME.md` |
| P-09 | B | **aguarda-decisão** | `diag_list_offset.json` `-113`, `suportado: false`; plano do dono de 21/10 cumprido; rastreador pede A e B |
| P-10 | C | C (tomada no fork) | `fechamento.json`: 13 medidas ok, 2/5/10/15/20 % CSIN e 30 % TRACe |
| P-11 | C | C (tomada no fork) | `git diff fa82f49 main -- tests/fixtures` vazio; `experimentos_waveform/15.py:26` |
| P-12 | C | C (tomada no fork) | `experimentos_waveform/06.py:19` |
| P-13 | C | C (tomada no fork) | `logica/cli.py:339`, `logica/sessao_io.py:674,692,702` |
| P-14 | C | C (tomada no fork) | `logica/cli.py:824-826,833-836,848-856`; `tests/test_pendencias_cli.py:28-91` |
| P-15 | C | C (tomada no fork) | `logica/relatorio_html.py:75,305-310` |
| P-16 | C | **aguarda-bancada** | `pc_bancada.json` 21/10 (`21fb300`, 680) e 22/10 (`6885e7c`, 759); `fechamento.json` `commit_igual_ao_das_sessoes`, `requer_revisao_humana`; `cd1e6a9` posterior mexeu em `visita_bancada.py` (+7) e teste (+17) |
| P-17 | D | D (em branco) | `fechamento.json` razões: AC 1,007, ACDC 0,945, com 134,4 V 0,9994; critério do déficit indefinido |
| P-18 | B | B (bancada + dono) | `fechamento.json` `sem_dados`; `logica/mestre.py:417` padrão desligado |
| P-19 | B | **insuficiente-bancada** (estado novo) | `fechamento.json`: 10 valores em vez de 1024, 9 leituras, 0 erro explícito |
| P-20 | D | D (em branco) | `ls` na raiz: sem LICENSE/CITATION/zenodo/AUTHORS/CODEOWNERS; `git tag` vazio; formulário em branco |
| P-21 | B | B (bancada + dono + código) | `fechamento.json` `classes_sem_fator: ['08']`; `calibracao_extremos.json` `observacao_08`; `registrada` true→false |
| P-22 | D | D (em branco) | `fechamento.json`: 14 sessões lidas sem erro; critério de tempo/tamanho indefinido |
| P-23 | B | B (bancada + dono) | `logica/politica_traces.py:3`, `ametek_orm.py:2051`; `fechamento.json` `diag_nativo_output_off_presente` 0 |
| P-24 | C | C | 764 permalinks `fa82f49` em `docs/`; build `-W` ok; publicação RTD NÃO VERIFICADO |
| P-25 | C | **aguarda-decisão** | `docs/limites_e_calibracao.md:51` sem "spec 26" hoje; "spec NN" restantes em `tests/test_offline.py`; sem resposta do dono |
| P-26 | B | B (só bancada) | `decisoes_pendentes.md` P-26 (21/10); só sessões de 127 V existem |
| P-27 | C | C (tomada no fork) | `git log --all -- '*validacao_gerador*'` vazio; `docs/correlacao_disturbio.md:37,75` |
| P-28 | D | D (em branco) | `fechamento.json`: 135 exportações íntegras, `fir_substitui_interpolador` sem critério |
| P-29 | B | B (só bancada) | `decisoes_pendentes.md` P-29 opção B (21/10); sem trechos versionados |
| P-30 | C | C (confirmada) | `decisoes_pendentes.md` P-30; `AGENTS.md:128`, `docs/tres_versoes.md:68` |
| P-31 | D | D (tomada no fork) | `modelo_programado.json` (0,98756 e 0,98742); formulário em branco |

## Critério de Parada
Atendido.
- As 31 pendências aparecem na página gerada: 31 âncoras `estado-p-NN` únicas em `projeto/pendencias.html`; 31 ocorrências de "Como foi resolvida ou o que foi feito", de "Pedido original" e de "Escolha do fork e decisão do dono", e 31 de "O que falta" mais o resumo (teste `RevisaoDe2026_10_27.test_markdown_gerado_traz_as_secoes_pedidas_para_as_31`).
- P-02 e P-08 aparecem como "Reprovada na bancada"; P-16 como "Software pronto, falta bancada" e P-25 como "Falta decisão"; nenhuma das duas como "Concluída" (conferido nos badges do HTML e em testes).
- Placar da página = contagem do arquivo (11/8/9/0/1/2 = 31), gerado da mesma função; `index.html`, `visao-geral.html` e `estado-validacao.html` mostram a mesma linha.
- Verificações: `sphinx-build -E -W -n --keep-going -b html docs <scratchpad>/html` → `build succeeded`; `python -m unittest tests.test_estado_pendencias` → 38 testes OK; suíte completa `python -m unittest discover -s tests -p "test*.py"` → 798 testes, OK (skipped=2) em Linux (777 de base + 21 novos).

## Pendências que exigem o usuário

Lista consolidada de perguntas ao dono (uma linha por decisão; gerada de `decisao_dono.pergunta`/`opcoes`). "Formulário" = `docs/decisoes_pendentes.md`; as demais não têm seção lá (opções do inventário de 16/10, da evidência de 22/10, ou propostas minhas).

1. P-03 (tomada no fork): confirma o encerramento (3/3 capturas a 127 V/50 Hz, desvio 2 amostras, pico 339 V, sobressinal 0,295 pu)? Sim / Não, pedir mais capturas. (sem opções prévias)
2. P-04 (tomada no fork): o ORM também recusa pico acima do limite? (a) recusar no ORM, adotada; (b) manter só `mestre.py` (enfraqueceria validação do ORM; `AGENTS.md` proíbe). (inventário)
3. P-05 (em branco): o pre-trigger determinístico (até 6 amostras nas 02 a 04) vira compensação do rótulo de início ou limite novo? (evidência de 22/10)
4. P-07 (tomada no fork): aprova o diff de calibração de 07 e 17 (1,615 e 1,575 a 127 V/60 Hz)? Aprovar (a validação ainda exige nova coleta) / reverter e recalibrar. (sem opções prévias)
5. P-09 (confirmada em 21/10, conflito): o comando de offset por passo não existe (`-113`); fechar agora como limitação aceita com (d), como no plano, ou exigir antes os braços A e B? Formulário: A aceitar sem compensar; B não aceitar e investigar; C aceitar só 06 e 15.
6. P-10 (tomada no fork): confirma o encerramento (THD 2, 10, 15, 20 % por CSINusoid e 30 % por TRACe, todos ok)? Sim / Não. (sem opções prévias)
7. P-11 (tomada no fork): mantém as extensões das compostas 10 a 16? (a) manter, adotada; (b) reverter e regravar `tests/fixtures/gerar_sorteio_v1_15.json`. (inventário)
8. P-12 (tomada no fork): classe 06 compara com a programada ou redefine o flicker? (a) comparar, adotada; (b) redefinir, muda `gerar()`. (inventário)
9. P-13 (tomada no fork): recuperar sessão parcial automaticamente no `run`? (a) sim, adotada; (b) manual. (inventário)
10. P-14 (tomada no fork): `run 01 02` recusado e `BATERIA_EXCLUIR` em listas? (a) sim, adotada; (b) manter como estava. (inventário)
11. P-15 (tomada no fork): HTML limitado a 3 capturas por classe e perfil também na bancada? (a) corrigir o texto; (b) limitar, adotada. (inventário)
12. P-17 (em branco): que déficit de CA em ACDC (hoje cerca de 5,5 %) é aceitável, e V/g entra? Documentar sem compensar / compensar (134,4 V para 127 V) / fixar limite numérico. (sem opções prévias)
13. P-18 (tomada no fork): SINE desligado por padrão? Formulário: A manter desligado (recomendado e adotado); B ligar por padrão; C retirar o código.
14. P-20 (em branco): licença do código e do dataset e quem autoriza, autores com ORCID, citação, tag e Zenodo. Formulário: tag A só após P-01 e P-31 / B pré-lançamento `-rc` / C agora com Zenodo; Zenodo A só após licença e autoria / B não publicar; cinco campos livres.
15. P-21 (tomada no fork, pelo operador): regra de condição sem tabela (220 V/60 Hz). Formulário: A manter (escolhida pelo operador); B tabela de mesma frequência; C decidir B depois das campanhas de 127 V/50 Hz e 230 V/50 Hz.
16. P-22 (em branco): que tempo de reescrita e tamanho do `NN_classe.npz` são aceitáveis? Aceitar o medido / fixar limites. (sem opções prévias)
17. P-23 (tomada no fork): orçamento de 216 gravações TRACe. Formulário: A manter como regra operacional (recomendado e adotado); B mudar o valor; C configurável por variável de ambiente.
18. P-25 (tomada no fork): item a item, aceitar ou retirar (1) "spec NN" restantes em código e testes, (2) termo de governança em `AGENTS.md`, (3) nome de variável em `mestre.py`, (4) texto de `uso_limite_bancada`. (inventário)
19. P-27 (tomada no fork): seguir sem `validacao_gerador_v1.14.md` (faixas e "bate?" retirados) ou fornecer o arquivo? (inventário)
20. P-28 (em branco): o FIR com anti-aliasing substitui a interpolação linear? Manter / substituir. (sem opções prévias)
21. P-31 (tomada no fork): métrica oficial de correlação. Formulário: A publicar as duas sem eleger (recomendado e feito pelo fork); B nominal; C fundamental ajustada.

Também exigem o usuário (não são decisões, são tarefas físicas): rodar a suíte no PC da bancada no commit da campanha (P-16); as campanhas de 230 V/50 Hz, 220 V/60 Hz e 33 V/60 Hz e a reexecução do que reprovou (P-01, P-21, P-26); recoleta das 10, 11, 12 e 16 (P-08), diagnóstico da cópia em 100 ms (P-02), nova leitura de `TRACe:DATA?` (P-19), rampa 47→53 Hz (P-06), teste do SINE (P-18) e diagnóstico com saída OFF (P-23).

## Limitações de escopo
- `scripts/gerar_mapa_pendencias.py` não foi alterado (fora da lista permitida). O renderizador só conhece "concluída" e "aguarda-decisão"; todo o resto cai no callout `> [!todo] Software pronto; falta bancada`. Resultado: as notas `mapa/pendencias/P-02.md`, `P-08.md` (estado reprovada) e `P-19.md` (insuficiente) trazem o `status` e a tag corretos no cabeçalho, e o texto de `falta` correto, mas o callout diz "Software pronto". Correção sugerida: três ramos novos em `renderizar()` e no modelo `mapa/_modelos/pendencia.knap.md`.
- `docs/classes/` não foi tocado (outra spec). Seguem com selos desatualizados: `05-harmonics.md:8` (`PENDENTE P-10`, `NÃO VERIFICADO` dos níveis medidos em 22/10), `08-transient.md:8` (`PENDENTE P-03`), e `PENDENTE P-11`/`P-12` nas classes 06, 10 a 16.
- `docs/decisoes_pendentes.md` e `docs/evidencias/` não foram alterados; por isso as 11 decisões sem seção no formulário só aparecem como pergunta na página viva e neste relatório.
- Nenhuma energização, nenhuma suíte no PC da bancada, nenhuma decisão tomada pelo dono.

## A missão resolve o contexto?
Sim: a página publicada passa a dizer, por pendência, o que foi pedido, o estado que as evidências sustentam, como foi tratada, o que falta (por tipo) e se o dono confirmou ou não, e lista as 21 perguntas que só ele responde, sem decidir nada por ele.

## Achados
- **Alta.** `docs/projeto/estado-validacao.md` continua afirmando que a `main` está em `fa82f49`, que a última campanha de bancada é a de 07/10 e que nada do código da v1.15 foi medido (resumo da página, camadas, seção 4 "nenhuma sessão de bancada com perfil"). A visita de 22/10 mediu perfis, sorteio, 08 a 90 ms, crista com fator, 05 por CSINusoid etc. Só apontei a página para a viva e corrigi o placar (era o pedido); o conteúdo da matriz precisa de revisão própria. Mesma página diz que o SINE "está fora da `main`", e P-18 mostra integrado desligado.
- **Média.** Classificação de P-18, P-23, P-31 (e P-21): a spec lista como "em branco" P-18, P-20, P-23 e P-31. Marquei P-18, P-23 e P-31 como "tomada no fork" porque o fork já aplica a opção A (a recomendada pelo formulário), e P-21 também (escolha do operador, `registrada` true→false). Se preferir "em branco" nas quatro, é trocar `situacao`; as perguntas já estão lá.
- **Média.** P-21: o critério do agregador `calibracao_da_condicao` exige fatores das 20 classes e a 08 não usa a tabela por desenho (`calibracao_extremos.json`, `observacao_08`). Enquanto isso, P-21 e o P-01 nunca ficarão `ok` nesse critério. Registrado em `falta_por_tipo.codigo` da P-21.
- **Média.** Os "spec NN" de comentários e docstrings em `tests/test_offline.py` e `logica/` continuam; o registro anterior dizia "removidos" e "mantidos por decisão explícita" sem fonte. O termo de governança de `AGENTS.md` (`grep -i governan` vazio) e a variável de `mestre.py` da P-25 não foram localizados: NÃO VERIFICADO (o inventário cita linhas do baseline).
- **Média.** Na P-25 a ordem do relatório de achados (item 4 da seção 7: tirar "spec 26") já estava feita hoje (`dafde1f`, `9ce09b4`); não era mais motivo para P-25 ficar concluída, e sim a falta de resposta do dono.
- **Baixa.** Quatro números de teste coexistem: 574 (17/10, Mac), 680 e 759 (PC da bancada), 777/798 (Linux, hoje). Só os dois do PC valem para P-16, e nenhum é do HEAD.
- **Baixa.** `fechamento.json` mostra `posicao_08_desvio_amostras` = 16 sem sinal; o "−16" e a sessão `sessao_2026-10-22_15-19-56` vêm do relato da execução. NÃO VERIFICADO: as sessões estão só no PC da bancada.
- **Baixa.** NÃO VERIFICADO: tamanho do HTML do relatório com sessão real de bancada (P-15); publicação atual no Read the Docs (P-24); a causa dos 10 valores de `TRACe:DATA?` (P-19; sugeri examinar também o leitor do `retrieve`, como hipótese); o diff exato da correção de estado da classe 18 (P-06, só o registro da execução).
- **Baixa.** Divergência de detalhe no inventário: ele fala em erro de 0,24 a 0,33 pu para a média por ciclo; `modelo_programado.json` dá perda máxima de 0,288 pu e mediana 0,072 (recalculei: confere com `decisoes_pendentes.md`).
- **Baixa.** Em `docs/estado_prontidao.json`, `P-24` e `P-30` mantêm `evidencias` antigas (válidas). P-04, P-11 a P-15 e P-27 citam como evidência `validacao_software.json` e `execucao_pendencias.md` (574 testes de 17/10), não a suíte atual.

## Ajuste pedido pelo orquestrador

Commit local `7efd26e` (`fix: mapa mostra estados reprovada e insuficiente`), sem push.

- `scripts/gerar_mapa_pendencias.py`: `renderizar()` passa a usar o dicionário `CALLOUTS`, com um callout para cada estado do esquema 3 (concluida, aguarda-bancada, aguarda-decisao, em-andamento, insuficiente-bancada, reprovada-bancada). Estado desconhecido levanta `ValueError` em vez de cair em "Software pronto".
- `mapa/_modelos/pendencia.knap.md`: cadeia `elseif` equivalente (o `else` final é a reprovada).
- Mapa regenerado com `python scripts/gerar_mapa_pendencias.py`. O diff das notas é só a linha do callout em três arquivos: P-02 e P-08 viram `[!failure] Reprovada na bancada`; P-19 vira `[!warning] Insuficiente na bancada: medida feita, resultado inconclusivo`. As outras 28 notas não mudaram.
- Contagem de `status:` nas notas, antes e depois: 8 aguarda-bancada, 9 aguarda-decisao, 11 concluida, 1 insuficiente-bancada, 2 reprovada-bancada.
- `python -m unittest tests.test_estado_pendencias`: 38 testes, OK. Suíte completa: 798 testes, OK (skipped=2).
- NÃO VERIFICADO: o caminho `--knap` (o `npx knap` não foi executado), então o modelo Knap alterado não foi renderizado por ele.

Isso resolve a primeira limitação de escopo acima.
