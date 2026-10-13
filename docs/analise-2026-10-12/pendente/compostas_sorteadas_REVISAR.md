# Parâmetros sorteados nas compostas e teste de formas distintas (v1.15)

2026-10-12. Origem: Pergunta 15, proposta 4 e item f) de `atividade.tex`; autorização do dono de mudar o `gerar()` (registrada em `AGENTS.md`). Tudo em modo simulado (`BENCH_MODE=0`); nada tocou o hardware. Contagens: 2000 capturas por classe, 60 Hz, `seed_da_captura(k)`, `capture_index = k`, forma antes do ruído (script no scratchpad da sessão; reproduz o `gerar()` com `dataclasses.replace(config, perfil=..., sorteio_posicao=...)`).

## 1. O que as compostas sorteiam

`perfis.composto` (`logica/perfis.py:136`) devolve o valor de um componente por captura; as faixas ficam em `FAIXAS_SORTEADAS` (`perfis.py:113`) e as classes 10 a 16 chamam `perfis.composto` (`10.py:23-24`, `11.py:18-20`, `12.py:20-21`, `13.py:22-23`, `14.py:20-21`, `15.py:18-20`, `16.py:22`). Um sorteio `rng.uniform` por parâmetro, na ordem em que `gerar()` os chama.

| Classe | Parâmetros sorteados (perfil literatura) | norma | fronteira |
|---|---|---|---|
| 10 | sag U(0,1; 0,9), THD U(0,05; 0,20) | sag U(0,15; 0,85), THD U(0,02; 0,20) | sag 0,1/0,9 por `capture_index`, THD U(0,05; 0,20) |
| 11 | sag U(0,1; 0,9), profundidade U(0,05; 0,15), flicker U(8; 25) Hz | sag U(0,15; 0,85), profundidade U(0,02; 0,07), flicker U(8; 25) | sag 0,1/0,9, resto = literatura |
| 12 | sag U(0,1; 0,9), f_osc U(300; 2400) Hz | sag U(0,15; 0,85), f_osc igual | sag 0,1/0,9, f_osc igual |
| 13 | swell U(1,1; 1,8), THD U(0,05; 0,20) | swell U(1,15; 1,75), THD U(0,02; 0,20) | swell 1,1/1,8, THD U(0,05; 0,20) |
| 14 | swell U(1,1; 1,8), f_osc U(300; 2400) Hz | swell U(1,15; 1,75), f_osc igual | swell 1,1/1,8, f_osc igual |
| 15 | THD U(0,05; 0,20), profundidade U(0,05; 0,15), flicker U(8; 25) Hz | THD U(0,02; 0,20), profundidade U(0,02; 0,07) | = literatura |
| 16 | THD U(0,05; 0,20) | THD U(0,02; 0,20) | = literatura |

Origem de cada faixa: THD, f_osc (12, 14), flicker e sag da 10: proposta 4 (`atividade.tex:998-1000`). Profundidade do flicker: "a do item 6" = a faixa da classe 06 por perfil (`FAIXAS["flicker_profundidade"]`). **Escolhas minhas, fora do texto da proposta (gravidade baixa, revise):** (a) sag também em 11 e 12 e swell em 13 e 14 (a proposta só cita o sag da 10; `sag_composto`/`swell_composto` já eram um componente compartilhado, deixar 11/12/13/14 fixos seria inconsistente); (b) faixa do swell = extremos de `swell_niveis` (1,1 a 1,8; norma 1,15 a 1,75); (c) norma sorteia sag em 0,15 a 0,85 e THD de 2 % a 20 %, os extremos de `sag_niveis`/`thd_niveis`; (d) `fronteira` continua nos pares 0,1/0,9 e 1,1/1,8, por `capture_index` (sem sorteio, é o estresse de fronteira); (e) a 16 mantém interrupção 0,05 fixa e a 17 mantém 300 Hz fixo e a 08/09 não são tocadas (a 17 já sorteia os entalhes e já tinha `capturas_padrao = 3`; a proposta não a cita).

**Condição:** só com `Config.sorteio_posicao` ligado (`set sorteio on`, padrão). Desligado, `composto` devolve o valor fixo de `FAIXAS` (sag 0,5, THD 0,2, 15 Hz, 600 Hz...). Motivo: o teste byte a byte de 34a0d82 continua valendo sem alteração (seção 5), e o interruptor único não cria uma terceira combinação a testar. Custo: `set sorteio off` volta às compostas com 1 forma (seção 4); é o modo de reprodução do dataset antigo, não de coleta.

**Sub-fluxo de posição preservado.** Os parâmetros saem do `rng` da classe, que as classes 10 a 16 não usavam para mais nada; início/duração/fase vêm do sub-fluxo `_rng_do_sorteio` (`mestre.py:783`). Conferido: início, duração e fase de 7 classes x 30 seeds (210 valores) antes e depois da mudança são idênticos (`antes.json` x `depois.json` do scratchpad); o teste `test_sorteio_dos_parametros_nao_muda_o_sub_fluxo_de_inicio_duracao_fase` (`test_offline.py:5561`) fixa isso comparando com `sortear_posicao` direto.

## 2. Ganchos de bancada (`parametros_com_disturbio_reduzido`)

Não precisaram de mudança: leem `sag_pu`/`swell_pu`/`thd`/`flicker_depth` de `parametros`, que continuam com as mesmas chaves, e a tradução do fator k (`nivel = 1 + k(x - 1)`; `thd_b = k x thd / nivel`) vale para qualquer valor. A frequência do flicker e da oscilação não é reduzida por k (só amplitude/profundidade) e fica em `flicker_hz`/`oscillation_hz` do metadata. Teste novo `test_gancho_de_bancada_traduz_o_fator_k_com_os_parametros_sorteados` (`test_offline.py:5587`): para 10, 11, 12, 13, 14, 16, 12 seeds, k = 0,6, a forma montada só com os parâmetros `*_bancada` e a frequência sorteada é igual a `senoide + k (gerar() - senoide)` (atol 1e-9).

**Efeito nos limites de bancada (gravidade média).** `scripts/relatorio_limites_bancada.py`, plano padrão (3 capturas): a 127 V as 20 classes rodam todas. A 220 V (`--tensao 220`): 10, 11, 12, 15, 16, 17 rodam 3/3 com distúrbio reduzido; **13 roda 1/3 e a 14 roda 0/3** (swell sorteado até 1,8 pu: extremo previsto de 599 a 922 V pede fração do distúrbio abaixo do mínimo de 0,25, `LIMITE_BANCADA_FRACAO_MINIMA`). Antes (swell fixo 1,3) a 13 e a 14 rodavam 3/3 reduzidas. É o limite de bancada funcionando, não um limite alterado; mas 220 V perde essas amostras. Não mexi em `max_peak_v` nem na fração mínima.

## 3. Capturas padrão

`capturas_padrao = 3` em 10 a 16 (a 17 já tinha). Efeito no `status` da CLI: TRACe 300 -> **468 gravações** na Flash por `run all` (7 classes x 2 capturas a mais x 12; o 12 é `duration_s x grid_frequency_hz` em `capturas_efetivas_da_classe`, `mestre.py:2811`, multiplicado pelas capturas que gravam TRACe), contra a referência de travamento da fonte em ~280 (`mestre.py` já avisava com 300; agora o aviso mostra 468 e sugere `run <NN>` por partes). **Gravidade alta para a coleta:** `run all` inteiro numa conexão passa de longe a ~280.ª gravação; rodar por partes, ou decidir o limite (proposta já feita em `sorteio_inicio_fase.md`).

## 4. Formas distintas por classe, antes e depois

2000 capturas, literatura, 60 Hz. "34a0d82" = `set sorteio off` com os valores fixos de antes da v1.15 (os números que o professor contou); "v1.15 só posição" = estado no início desta tarefa (sorteio ligado, compostas com parâmetros fixos); "agora" = sorteio ligado com os parâmetros sorteados.

| Classe | 34a0d82 | v1.15 só posição | agora |
|---|---|---|---|
| 01 | 1 | 1527 | 1527 |
| 02 / 03 / 04 | 5 / 5 / 2000 | 2000 / 2000 / 2000 | = |
| 05 | 5 | 1892 | 1892 |
| 06 a 09 | 2000 | 2000 | 2000 |
| 10 | 1 | 2000 | 2000 |
| 11 | 1 | 2000 | 2000 |
| 12 | 1 | 2000 | 2000 |
| 13 | 1 | 2000 | 2000 |
| 14 | 1 | 2000 | 2000 |
| 15 | 1 | 1543 | **2000** |
| 16 | 1 | 2000 | 2000 |
| 17 | 2000 | 2000 | 2000 |
| 18 | 2 | 1748 | 1748 |
| 19 / 20 | 2000 / 2000 | 2000 / 2000 | = |

Achado (gravidade média, para o texto da Pergunta 15): **a contagem de formas distintas das compostas já tinha ido a 2000 com o sorteio de posição** (10 a 14 e 16); os parâmetros sorteados só mudam a contagem na 15 (1543 -> 2000, só tinha fase). O que esta tarefa acrescenta é o conteúdo das formas: parâmetros distintos por captura (conta dos `parametros` sem início/duração/fase, excluídos), de 1 por classe para 2000 nas 10 a 16 (a 17: 9, como antes). Um modelo treinado com o sorteio de posição sozinho aprenderia "sag 0,5, THD 0,2, 600 Hz" como identidade da classe; agora aprende a classe pela família. A reprodução do "1 forma" continua com `set sorteio off` (compostas: 1 forma, fronteira: 2).

Os números são iguais nos perfis norma e fronteira com sorteio ligado (a conta só depende de haver parâmetros diferentes), exceto que na fronteira com `sorteio off` as compostas 10 a 14 dão 2 formas (sag/swell alternando 0,1/0,9 e 1,1/1,8), como antes.

## 5. Fixtures e testes de reprodução

| Fixture | Rodando com | Decisão |
|---|---|---|
| `gerar_literatura_34a0d82.json` | `sorteio_posicao=False` | **Intacto e passando**: sem sorteio as compostas usam os valores fixos de `FAIXAS`, então os 400 hashes de 34a0d82 não mudam (`test_literatura_reproduz_byte_a_byte...`). |
| `gerar_sorteio_v1_15.json` | sorteio ligado, literatura | **Regravado.** `gerar()` das 10 a 16 mudou de propósito (autorização do dono). O script de regravação comparou os 400 hashes: mudaram exatamente as classes 10, 11, 12, 13, 14, 15 e 16; as outras 13 classes, nenhuma. Campo `versao` atualizado. Continua sendo o congelamento da "versão da v1.15" (a versão é a mesma, não houve release entre o sorteio de posição e este). |

Outros testes ajustados (nenhum apagado): `COM_SORTEIO` da tabela de capturas padrão (+10 a 16); `test_classe_deterministica_continua_com_1` usava a 10 como exemplo determinístico, passou para a 18; `status` e estimativa de TRACe (300 -> 468, 12 -> 36 gravações na 10); relatório de limites (`16: 3/3 rodam, 3 com distúrbio reduzido`).

## 6. Teste do item f)

`ParametrosSorteadosNasCompostasTests.test_toda_classe_tem_formas_distintas_suficientes_em_todos_os_perfis` (`test_offline.py:5492`): para as 20 classes, `gerar()` com N = 100 capturas por classe (seed = `seed_da_captura`, antes do ruído), nos 3 perfis a 60 Hz e na literatura a 50 Hz; falha se alguma tiver menos de 90 formas distintas.

- **N = 100:** as 4 combinações x 20 classes levam ~2,3 s (medido); o pior caso são as classes só com fase sorteada (01, 05, 18): 3600 valores possíveis, ~1,4 colisões esperadas em 100.
- **Mínimo 90:** o menor valor observado nas 80 combinações é 98 (classe 18; 99 na 05). 90 fica longe das colisões casuais e abaixo de qualquer repetição estrutural: as compostas sem sorteio dão 1 (verificado por `test_o_teste_de_formas_distintas_reprova_uma_classe_que_repete_a_onda`, que exige < 90 com `sorteio_posicao=False` em 10 a 16). O teste antigo `test_formas_distintas_em_200_capturas` (> 150 de 200, só literatura 60 Hz) fica; este cobre perfis e 50 Hz.
- Seeds fixas: não é teste probabilístico flaky.

Outros testes novos na mesma classe: faixas por perfil (`test_parametros_sorteados_dentro_da_faixa_do_perfil`), cobertura das faixas da proposta 4 (mínimo e máximo observados nos 10 % extremos), valores fixos sem sorteio, padrão de 3 capturas.

## 7. Verificação

`.\env\Scripts\python.exe -m unittest tests.test_offline -v`: `Ran 293 tests ... OK` (285 antes + 8 novos).

NÃO VERIFICADO (sem hardware): (a) a fonte reproduzir oscilação de 2400 Hz em TRACe de 6000 pontos a 30 kSa/s (12,5 amostras por período; largura de banda e passo da TRACe nunca exercitados acima de 600 Hz); (b) o osciloscópio e o `validar_captura` física (P05) com flicker de 8 a 25 Hz e f_osc de 300 a 2400 Hz e as tolerâncias de RMS/THD atuais (a validação física nunca viu esses valores nas compostas); (c) THD de 2 % (norma) nas compostas a 127 V na resolução do osciloscópio; (d) tempo real de `run all` com 468 gravações de Flash; (e) README e `docs/perfis.md` descrevem as compostas como fixas na tabela: `docs/perfis.md` ganhou nota, o README não foi alterado.
