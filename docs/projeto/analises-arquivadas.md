# Análises arquivadas

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` (rodada de 13 a 15/10/2026 sem bancada)

**Pergunta:** o que a última rodada de análise concluiu e o que ficou em aberto? **Resposta:** a rodada de **13 a 15/10/2026** executou 17 tarefas de código e de documentação (numeradas 10 a 26), todas integradas na `main` (`fa82f49`), com a suíte offline passando (497 testes), mas **nada foi validado na bancada**: tudo o que depende da fonte e do osciloscópio está marcado "a confirmar", e a última campanha de bancada continua sendo a de 07/10/2026 (P-01).

As rodadas anteriores (21/09, 30/09 e 12/10/2026) já foram revisadas e não são reabertas aqui; os achados duráveis delas estão nas quirks ({doc}`../quirks`: A1, A2, A13, K1 e outras) e no {doc}`../historico` (v1.11 a v1.15). Os relatórios datados ficam no branch `arquivo/analises` (fora de `docs/` desde 13/10/2026) e **não** se reescrevem. Fontes desta página: `github/arquivo/analises:sessao-13-10-2026/{ESTADO.md,relatorio-final.md,ROTEIRO_BANCADA.md,wip/}` e `:specs/2026-10-13/relatorios-individuais/` (commit `3ba499c` do branch), mais `CHANGELOG/v1.15.md`.

:::{caution} Limitação
**A análise de 13 a 15/10 não foi validada na bancada.** Perfis, sorteio de início, duração e fase, compostas sorteadas, entalhes contínuos, a 08 a 90 ms, a crista com fator, o leitor de um `.npz` por classe e a leitura de volta das TRACes existem no código e passam nos testes offline, mas nenhuma sessão física os exerceu. O estado de cada classe está em {doc}`estado-validacao`; o que falta, em {doc}`pendencias`.
:::

## 1. O que cada tarefa concluiu

| Tarefa | Tema | Conclusão | O que ficou aberto |
|---|---|---|---|
| 10 | Análises fora de `docs/` | relatórios datados, planos antigos e scripts temporários foram para o branch `arquivo/analises`; `docs/` ficou só com a documentação do projeto e os manuais | nada |
| 11 | RMS por ciclo da TRACe sem a média e previsão de pico | `LIST:VOLTage` passou a levar o rms **CA** do ciclo e o pico previsto é calculado sobre a forma realmente enviada; antes o pico previsto podia ficar **até 38 % abaixo** do real em ciclos com degrau (10, 11, 12, 16), e a forma emitida diferia do modelo em até 0,43 pu | a fonte continua removendo a média de cada ciclo (erro programada × modelo de 0,24 a 0,33 pu): P-09; conferir `pico_medido_v` das 10, 11, 12, 16 na 1.ª sessão: P-08 |
| 12 | Preflight único | `preflight.py` foi removido; `lowvoltage` sempre rodou na tensão digitada (127 V) apesar do rótulo "5 V"; agora a confirmação é `ENERGIZAR-TESTE` e mostra a tensão real; `comm`, `trigger`, `lowvoltage` e `native` gravam `logs\preflight_new-*.log` | nada |
| 13 | `run` com lista de classes | `run 01-07,09-20` com a confirmação `EXECUTAR-CLASSES-01-07,09-20`, para dividir a bateria abaixo da trava de cerca de 280 gravações de TRACe por conexão | `run 01 02` (com espaço) roda só a 01; `BATERIA_EXCLUIR` não vale para listas: P-14 |
| 14 | Rastreabilidade | o metadata grava a semente do ruído e a fórmula; `git_sujo` passou a contar arquivo novo e é recalculado a cada pasta de sessão; `sessao.json` grava o perfil | `docs/quirks.md` B8 ainda descreve o comportamento antigo (P-24) |
| 15 | Cópia do evento em 100 ms (08 e 09) | três ferramentas: `scripts/diag_ciclos_trace.py` (offline), `scripts/diag_marcadores_trace.py` (bancada, `ENERGIZAR-MARCADORES`) e `logica/modelo_lista_fonte.py` (hipóteses); cinco hipóteses, nenhuma confirmada; com o início sorteado, 100 ms cai dentro do evento da 09 em só 17 a 18 % das capturas | mecanismo: P-02 (Blocos 4 e 6 do roteiro) |
| 16 | `set diagnostico retrieve` | lê de volta as TRACes (`TRACe:DATA? <nome>`) com a captura já terminada e 2 s depois da última gravação; salva enviado × lido em `diagnostico_trace/` | o manual se contradiz; só a bancada diz se funciona: P-19 |
| 17 | Um `.npz` por classe | `NN_classe.npz` comprimido, com as três versões de cada perfil; `sessao_io.py` lê os dois formatos; os níveis de ruído ficam em arquivos à parte | quebra de formato nas sessões novas; `recuperar_parcial` é manual (P-13); tamanho com dado real não medido (P-22) |
| 18 | Pendentes da correlação | 05: o modelo até 20 % já é a senoide clipada e no nível de 30 % modelo e programada são idênticos; nova métrica com a fundamental ajustada; a perda da 06 vem inteira da média de cada ciclo | decisão sobre a 06: P-12; qual métrica publicar: P-31; ver {doc}`../medicao/correlacao` |
| 19 | Compostas sorteadas contra a proposta | as extensões (sag em 11 e 12, swell em 13 e 14, THD em 13, 15 e 16, faixas da `norma`, `fronteira` alternada) vão além da proposta, sem defeito; a 2400 Hz a oscilação sai 2,4 % menor na programada | manter ou reverter: P-11; a 15 não tem `parametros_com_disturbio_reduzido` |
| 20 | Pendentes conferíveis offline (ACDC, 18, sorteio) | `scripts/verificar_sessao_bancada.py` mede a continuidade de fase da 18, a largura do PULSe e o desvio do pré-trigger numa sessão gravada; limiares de 10°, 2 ms e 2 amostras são propostas, sem dado de bancada | P-05, P-06, P-17 |
| 21 | Fixtures portáveis | o hash exato do `gerar()` difere entre Windows e Linux no último bit do seno (2·10⁻¹⁶); comparação por tolerância de 1e-9, e o hash exato continua só no Windows | rodar `tests.test_offline` no PC da bancada: P-16 |
| 22 | Documentação autocontida | seção única sobre HTML e recalibração em `docs/operacao.md` §9; autorizações que faltavam em `AGENTS.md` | decisões menores: P-25; HTML mostra todas as capturas numa sessão de bancada em formato 2: P-15 |
| 23 | Roteiro da bancada | `ROTEIRO_BANCADA.md` (10 blocos, de 2 h a 3 h com um perfil) | nenhum bloco executado: P-01, P-26; ver {doc}`../roteiro-bancada` |
| 24 | Scripts e `sessao_io` | os scripts de diagnóstico foram adaptados ao leitor único | nada |
| 25 | `set perfil todos` sem repetir | classes que não dependem do perfil (com sorteio ligado: 01, 04, 07, 08, 09, 17, 18, 19) são capturadas uma vez, sob `literatura`; o metadata dos três perfis aponta para a mesma captura; com `todos`, `run all` planeja 1116 gravações de TRACe a 60 Hz (1404 sem a deduplicação; 468 com um perfil) | acima da trava de ~280 por conexão: P-23 |
| 26 | Crista com fator calibrado | a validação da crista usa a calibração de extremos (`fator_crista`): aceita de `crista × 0,9` até `crista × fator × 1,1`; decisão de usar a calibração em vez de afrouxar a tolerância | os fatores de 07 e 17 a 127 V/60 Hz (1,186 e 1,031) não cobrem o toque simulado (≥ 1,344 e ≥ 1,420): a 1.ª rodada deve reprovar; ver {doc}`../medicao/recalibracao`: P-07 |

Duas tarefas tinham ficado interrompidas em 13/10 (25 e 26) e foram concluídas em 15/10 a partir de patches guardados em `sessao-13-10-2026/wip/`.

## 2. Decisões que a rodada deixou para o responsável

O relatório final reúne oito decisões; todas entram em {doc}`pendencias` com id:

| Decisão do relatório | Id |
|---|---|
| investigar a média por ciclo via ACDC depois da bancada | P-09 |
| a gravação de TRACe recusar pico acima do limite (hoje só avisa) | P-04 |
| `recuperar_parcial` automático no início do `run` | P-13 |
| `run 01 02` recusar; `BATERIA_EXCLUIR` fora das listas | P-14 |
| classe 06: comparar com a programada ou mudar `gerar()` | P-12 |
| compostas: manter ou reverter as extensões | P-11 |
| detalhes da documentação autocontida e o HTML com todas as capturas | P-25, P-15 |
| no dia da bancada: um perfil ou `todos`, frequência da campanha, ACDC a 230 V | P-26 |

## 3. O que a rodada não resolveu e o que mudou desde o relatório

- **Contagem de testes.** O estado da rodada (`ESTADO.md`) fala em 480 testes com 2 pulados; o relatório final, em 497 com 2 pulados (Linux). Em 2026-10-15, no Windows 11 (Python 3.11.9), a suíte deu `Ran 497 tests in 93.003s`, `OK`, **sem testes pulados** (P-16, parcialmente resolvida); em 2026-10-16 foi repetida para esta documentação (resultado em {doc}`estado-validacao`).
- **Rodada seguinte.** O branch `feat/passo-final-sin` ({doc}`passo-final-sin`) é anterior a esta rodada e continua fora da `main`.
- **O que não foi auditado aqui.** Os relatórios individuais foram lidos para esta página só até o nível de conclusão por tarefa; a leitura de cada um, linha a linha, não foi refeita.
