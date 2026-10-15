## Análise do orquestrador

- Implementação completa? Sim: tabela 10–17, conferência dos sorteios e do fator k, representação 2400 Hz/25 Hz medida, extensões documentadas em docs/perfis.md e docs/decisoes.md; merge limpo, 412 testes OK.
- Pendências do usuário: manter ou reverter as extensões (a)–(f) (sag em 11/12, swell em 13/14, faixas da norma, fronteira alternada, THD em 13/15/16); reverter muda o dataset.
- Escopo limitado demais? Não (sem o atividade.tex, usou a citação da spec original).
- Resolve o contexto? Sim.
- Critério de Parada: atendido.
- Classificação: com pendências (decisão sobre extensões).

---

# Relatório: Revisão das Compostas Sorteadas contra a Proposta

Branch: `worktree-agent-aa13be263768a12fc`. Commit: `c6137a5` (após o merge de `claude/specs-v1-15-review-3w2bgl`, que trouxe os fixtures portáveis). Nenhum fixture foi regravado (nem o hash exato nem o portável): nenhum `gerar()` mudou.

## Missão, item a item

**Item 1 — Montar a tabela proposta × código, parâmetro por parâmetro e classe por classe (faixa, distribuição, perfil, sorteio ligado/desligado), citando arquivo:linha, e marcar cada linha como conforme, extensão ou divergente.**
- Status: CUMPRIDO
- Explicação: tabela abaixo. Faixas em `logica/perfis.py:113-134` (`FAIXAS_SORTEADAS`), valores fixos (sorteio desligado) em `perfis.py:70-104` (`FAIXAS`), sorteio em `composto` (`perfis.py:182-195`, `rng.uniform` por parâmetro, uma chamada por componente). Valores observados em 2000 capturas por classe e perfil, 60 Hz. Nenhuma linha divergente.

Perfil literatura (padrão). Distribuição: uniforme contínua (`rng.uniform`), exceto fronteira de sag/swell. Sorteio desligado: valor fixo de `FAIXAS` (sag 0,5; swell 1,3; THD 0,2; profundidade 0,10; flicker 15 Hz; oscilação 600 Hz).

| Cl. | Parâmetro | Proposta | Código (arquivo:linha) | Observado (min; máx; média) | Situação |
|---|---|---|---|---|---|
| 10 | sag | U(0,1; 0,9) | `10.py:23`, `perfis.py:116` | 0,1005; 0,8999; 0,495 | conforme |
| 10 | THD | U(0,05; 0,20) | `10.py:24`, `perfis.py:120` | 0,0503; 0,2000; 0,125 | conforme |
| 11 | sag | (não citado) | `11.py:18` | 0,1003; 0,8999; 0,496 | extensão (a) |
| 11 | profundidade | "a do item 6" | `11.py:19`, `perfis.py:122-127` = `FAIXAS["flicker_profundidade"]` | 0,0501; 0,1499; 0,099 | conforme |
| 11 | flicker Hz | U(8; 25) | `11.py:20`, `perfis.py:128` | 8,003; 25,0; 16,5 | conforme |
| 12 | sag | (não citado) | `12.py:20` | 0,1010; 0,8991; 0,505 | extensão (a) |
| 12 | f_osc | U(300; 2400) | `12.py:21`, `perfis.py:130` | 300,9; 2398; 1356 | conforme |
| 13 | swell | (não citado) | `13.py:22`, `perfis.py:118` | 1,100; 1,800; 1,454 | extensão (a, b) |
| 13 | THD | (não citado) | `13.py:23` | 0,0501; 0,2000; 0,125 | extensão (THD) |
| 14 | swell | (não citado) | `14.py:20` | 1,100; 1,800; 1,449 | extensão (a, b) |
| 14 | f_osc | U(300; 2400) | `14.py:21` | 300,4; 2399; 1360 | conforme |
| 15 | THD | (não citado) | `15.py:18` | 0,0500; 0,2000; 0,125 | extensão (THD) |
| 15 | profundidade | "a do item 6" | `15.py:19` | 0,0500; 0,1498; 0,097 | conforme |
| 15 | flicker Hz | U(8; 25) | `15.py:20` | 8,015; 24,98; 16,2 | conforme |
| 16 | THD | (não citado) | `16.py:22` | 0,0501; 0,2000; 0,125 | extensão (THD) |
| 16 | interrupção | (não citado) | `16.py:29-30`, fixo 0,05 | fixo | extensão (e) |
| 17 | oscilação | (não citado) | `17.py:37-39`, fixo 300 Hz | fixo | extensão (e) |
| 10-16 | capturas padrão | 1 → 3 | `capturas_padrao = 3` em cada `NN.py` (a 17 já tinha) | 3 | conforme |

Outros perfis (mesma tabela, `perfis.py:116-134`):
- norma: sag 0,15-0,85 (observado 0,1502-0,8499), swell 1,15-1,75 (1,150-1,750), THD 0,02-0,20 (0,0200-0,2000), profundidade 0,02-0,07; flicker e oscilação iguais à literatura. Situação: extensão (c); a proposta não tem perfis.
- fronteira: sag 0,1/0,9 e swell 1,1/1,8 alternando por `capture_index` (2 valores distintos, sem consumir `rng`), THD, profundidade, flicker e oscilação como na literatura. Situação: extensão (d).
- Sorteio desligado (`set sorteio off`): `composto` devolve `nivel(...)` de `FAIXAS` (`perfis.py:190-191`), o `gerar()` de 34a0d82 byte a byte.

**Item 2 — Conferir a correção de cada sorteio: faixas por perfil, uso do `rng` da classe sem tocar no sub-fluxo de posição, tradução do fator k nos ganchos de bancada com os parâmetros sorteados (inclusive a frequência do flicker/oscilação não reduzida por k), e `capturas_padrao = 3`.**
- Status: CUMPRIDO
- Explicação:
  - Faixas por perfil: 2000 capturas por classe nos 3 perfis; todos os valores dentro da faixa do perfil e 2000 de 2000 distintos, exceto sag/swell na fronteira (2 níveis, como projetado). Números na tabela do item 1.
  - `rng` e sub-fluxo: `composto` usa o `rng` da classe (um `uniform` por parâmetro, antes de `sortear`); `sortear_posicao` deriva o sub-fluxo da mesma `SeedSequence` com chave própria (`mestre.py:824-834`), independente do estado do `rng`; início/duração/fase não dependem dos parâmetros (teste existente `test_sorteio_dos_parametros_nao_muda_o_sub_fluxo_de_inicio_duracao_fase`, passa). A 15 não tem `inicio_disturbio_s` (200 ms inteiros), as demais têm.
  - Ganchos: classes 10, 11, 12, 13, 14, 16, seeds 0-39, k = 0,25/0,6/1,0, 50 e 60 Hz: forma montada só com os parâmetros `*_bancada` e a frequência sorteada (`flicker_hz`/`oscillation_hz` ficam no metadata, k não os reduz) igual a `senoide + k (gerar() - senoide)`, erro máximo 4,4·10⁻¹⁶ pu. A 15 não tem gancho (nunca teve): com redução vale `fator_disturbio_bancada`, mas o metadata não traz `thd_bancada`/`flicker_depth_bancada` (achado, baixa).
  - `capturas_padrao = 3` em 10 a 16 (conferido nos arquivos) e a 17 já tinha.

**Item 3 — Conferir a representação da oscilação de 2400 Hz e do flicker de 25 Hz depois da TRACe por ciclo (modelo × programada nas piores combinações, 50 e 60 Hz), usando `AmetekMX30.montar_programacao(...).programada_pu()`.**
- Status: CUMPRIDO
- Explicação: 60 capturas por combinação, 127 V, sag/swell neutros (1 pu) para isolar o componente.

| Cl. | Componente | 50 Hz: erro máx / rms rel. | 60 Hz: erro máx / rms rel. | pico de (forma - senoide), modelo → programada |
|---|---|---|---|---|
| 12 | 300 Hz | 0,031 pu / 0,56 % | 0,018 / 0,71 % | 0,255 → 0,246 |
| 12 | 1000 Hz | 0,032 / 0,15 % | 0,009 / 0,19 % | 0,285 → 0,281 |
| 12 | 2400 Hz | 0,020 / 0,12 % | 0,017 / 0,13 % | 0,293 → 0,287 |
| 14 | 2400 Hz | 0,035 / 0,13 % | 0,017 / 0,12 % | 0,293 → 0,285 |
| 11 | flicker 8 Hz | 0,047 / 2,1 % | 0,046 / 2,2 % | 0,092 → 0,091 |
| 11 | flicker 25 Hz | 0,048 / 3,3 % | 0,053 / 4,7 % | 0,094 → 0,087 |
| 15 | flicker 25 Hz | 0,031 / 4,3 % | 0,053 / 5,4 % | 0,218 → 0,237 |

  A oscilação de 2400 Hz (12,5 amostras por período na grade de 30 kSa/s) é preservada, perda de amplitude de 2,4 %. O flicker de 25 Hz vira degraus de um ciclo (o `LIST:VOLTage` é um rms por ciclo): erro até 0,053 pu. Com sag/swell sorteados o erro máximo sobe a 0,25-0,32 pu, igual em 300 e 2400 Hz: vem da borda do sag/swell no meio de um ciclo (a TRACe tira o DC de cada ciclo). Isso não é da composta: classes 02 e 03 dão 0,29-0,32 e 0,27-0,29 pu com o sorteio e 0,32 e 0,29 pu a 60 Hz sem sorteio. Teste de regressão novo `ComposicaoSorteadaRepresentacaoTests` (`tests/test_offline.py`, fim do arquivo). O que a fonte e o osciloscópio fazem fisicamente não foi verificado (sem hardware).

**Item 4 — Documentar as extensões (a)–(e) e o THD em 13/15/16 como decisões de projeto em `docs/perfis.md`/`docs/decisoes.md`, com a justificativa técnica, sem atribuí-las a pessoas (não use "professor", "dono", ".tex").**
- Status: CUMPRIDO
- Explicação: seção nova no fim de `docs/perfis.md` ("Compostas sorteadas: o que a proposta pede e o que o projeto acrescenta"), com tabela de situação e as extensões (a) a (f) (THD em 13/15/16 é a (f)), cada uma com justificativa técnica; 3 linhas novas em `docs/decisoes.md` (tabela "Arquitetura e dados"). A nota da linha 24 de `docs/perfis.md` ("valor único por perfil") foi corrigida para valer só com `set sorteio off`. Os textos novos não usam "professor", "dono" nem ".tex" (as linhas antigas de `decisoes.md` que usam essas palavras não foram tocadas).

**Item 5 — Corrigir só o que for divergente da proposta ou defeito; extensões ficam como estão e entram em "Pendências que exigem o usuário". Registrar em `CHANGELOG/v1.15.md` (seção nova no fim) o que foi conferido/corrigido.**
- Status: CUMPRIDO
- Explicação: não houve divergência da proposta nem defeito de código, então nada foi corrigido em `gerar()`/`perfis.py`; extensões intactas e listadas abaixo. Seção "Revisão das compostas sorteadas contra a proposta (2026-10-13, mesma versão)" no fim de `CHANGELOG/v1.15.md` (Por quê / conferido / O que mudou / não mudou / Testes / NÃO VERIFICADO).

## Critério de Parada
Atendido. Tabela cobre 10-17 e todos os parâmetros da proposta (sag e THD na 10, f_osc na 12/14, flicker e profundidade na 11/15, capturas 3); cada extensão (a)-(f) está em `docs/perfis.md` e `docs/decisoes.md`. Suíte: `TMPDIR=/tmp/claude-0/tmpt /tmp/claude-0/venv/bin/python -m unittest tests.test_offline` → `Ran 412 tests ... OK (skipped=2)` (410 anteriores + 2 novos; 0 falhas).

## Pendências que exigem o usuário
Extensões mantidas, que dependem de decisão se quiser revertê-las (mudaria o dataset da v1.15 e exigiria regravar `gerar_sorteio_v1_15.json`):
- (a) sag em 11 e 12, swell em 13 e 14; (b) faixa do swell = extremos de `swell_niveis`; (c) faixas do perfil `norma` (sag 0,15-0,85, swell 1,15-1,75, THD 2-20 %); (d) fronteira alternando em vez de sortear; (e) 16 com interrupção 0,05 fixa e 17 com 300 Hz fixo; (f) THD sorteado em 13, 15 e 16.
- Confirmar o texto da proposta: o `atividade.tex` não está no repositório; a conferência usou a citação da spec original.

## Limitações de escopo
Sem hardware e sem o `atividade.tex`: a representação física (fonte a 2400 Hz, osciloscópio) e o texto literal da proposta não puderam ser verificados.

## A missão resolve o contexto?
Sim: todos os sorteios pedidos estão conformes e as extensões estão registradas como decisões de projeto. Nenhum achado muda a missão.

## Achados
- (média) Sem hardware, nada garante que a fonte emita 2400 Hz e flicker de 25 Hz como `programada_pu` prevê. NÃO VERIFICADO.
- (média, pré-existente) A TRACe por ciclo erra 0,25-0,32 pu perto da borda de sag/swell que cai no meio de um ciclo (classes 02, 03, 10-16, também sem sorteio a 60 Hz). O `programada_pu` já registra a forma emitida no `.npz`, então a captura é rastreável; vale decidir se isso é aceitável para o dataset.
- (baixa) Classe 15 sem `parametros_com_disturbio_reduzido`: com redução no limite de bancada o metadata não grava THD/profundidade efetivos.
- (baixa) As compostas sorteiam por `rng.uniform` simples; a classe 06 usa `valor_para_captura` (cobertura por `linspace` com `set capturas N`). Com 3 capturas por classe, as extremidades (ex.: 2400 Hz) são raramente sorteadas nas compostas. Sugestão (não implementada): cobertura igual à da 06.
- (média, já registrado antes) A 220 V as classes 13 e 14 rodam só 1/3 e 0/3 capturas reduzidas por causa do swell até 1,8 pu (limite de bancada funcionando). Não verificado de novo nesta rodada.
- (baixa) O `atividade.tex` citado em comentários de código/docs antigos não existe no repositório.
- Fixtures: nada regravado, então a nota sobre "hash exato gravado no Linux" não se aplica.
