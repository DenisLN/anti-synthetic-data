# Início, duração e fase sorteados em `gerar()` (v1.15)

2026-10-12. Origem: Pergunta 7 e proposta 3 do `atividade.tex`; autorização do dono de mudar o que `gerar()` produz (registrada em `AGENTS.md`). Tudo abaixo foi feito em modo simulado (`BENCH_MODE=0`); nada tocou o hardware.

## 1. O que é sorteado, por classe

Regra (`logica/mestre.py`, `sortear_posicao`, linha 796): `tmin` = 1 ciclo da rede (16,67 ms a 60 Hz); duração `d ~ U(0,5 ciclo, 200 ms − 2·tmin)` (8,33 a 166,67 ms a 60 Hz) nas classes de duração livre; início `t0 ~ U(tmin, 200 ms − d − tmin)`; fase `θ ~ U(0°, 360°)` em passos de 0,1° (resolução de `TRIGger:SYNChronize:PHASe`, `ametek_orm.py:736`), onde θ é a fase da senoide **no instante t0**; a fase em t = 0, gravada em `fase_graus`, é `θ − 360·f0·t0`. `t0` e `d` caem na grade de 30 kSa/s. A senoide base é `sin(2π·f0·t + fase)`.

O sorteio usa um sub-fluxo da mesma seed (`_rng_do_sorteio`, linha 783), não o `rng` da classe: `flicker_hz`, amplitudes etc. de uma dada seed ficam como eram (teste `test_parametros_ja_sorteados_nao_mudam_com_o_sorteio`).

| Classe | Caminho | Início `t0` | Duração `d` | Fase |
|---|---|---|---|---|
| 01 NORMAL | nativo | não há evento | não há | sorteada (disparo da fonte) |
| 02 SAG, 03 SWELL, 04 INTERRUPTION | nativo PULSe | sorteado (era 60 ms) | sorteada, meio ciclo a 166,67 ms (era 60 ms) | sorteada |
| 05 HARMONICS | nativo CSINe; 30 % por TRACe | não há | não há | sorteada |
| 06 FLICKER | TRACe | não há (modula a janela inteira) | não há | sorteada |
| 07 NOTCH | TRACe | sorteado (era 60 ms) | fixa, 80 ms | acoplada ao início (ver abaixo) |
| 08 TRANSIENT | TRACe | **fora** | **fora** | **fora** |
| 09 OSCILLATORY_TRANSIENT | TRACe | sorteado (era 80 ms) | já sorteada antes (10 a 40 ms) | sorteada |
| 10, 11, 13, 16 | TRACe | sorteado (era 60 ms) | sorteada, meio ciclo a 166,67 ms (era 60 ms) | sorteada |
| 12, 14 | TRACe | sorteado (era 60 ms) | sorteada, a oscilação acompanha a mesma janela (era 40 ms) | sorteada |
| 15 HARMONICS_FLICKER | TRACe | não há (janela inteira) | não há | sorteada |
| 17 NOTCH_OSC | TRACe | sorteado (era 60 ms) | fixa, 60 ms | acoplada ao início |
| 18 FREQUENCY_DRIFT | nativo LIST | não há (rampa na janela inteira) | não há | sorteada |
| 19 DC_OFFSET | nativo | não há (offset na janela inteira) | não há | sorteada |
| 20 INTERHARMONICS | TRACe | não há | não há | sorteada (fundamental; as inter-harmônicas já tinham fase própria) |

Ficam de fora e por quê:

- **08**: a posição do impulso (80 ms) é de outra spec; a fase também ficou, porque `SOBRESSINAL_DO_DEGRAU`/`SUBSINAL_DO_DEGRAU` (`experimentos_waveform/08.py`) foram medidos com o impulso partindo de um ponto fixo da senoide e limitam a amplitude pelo vale (`forma_para_bancada`). Mudar a fase muda o ponto de partida e invalida essa calibração de segurança. Gravidade: baixa (a 08 já produzia 2000 formas distintas por causa da amplitude sorteada, ver tabela abaixo).
- **01, 05, 06, 15, 18, 19, 20**: não têm evento localizado; só a fase.
- **07, 17**: a fase não é livre. `aplicar_entalhes` põe os entalhes em `inicio_ciclo + T/4` e `+ 3T/4`, o que só cai nos picos se a senoide tem fase 0 em `inicio`. Então a fase é acoplada: seno com fase 0 em `t0` (`fase_acoplada_ao_inicio`). Como `t0` é livre, a fase em t = 0 ainda cobre todo o círculo. **Achado (gravidade baixa):** no `gerar()` antigo a 60 Hz isso não era verdade: `t0 = 60 ms = 3,6 ciclos`, a fase em `t0` era 216° e os entalhes caíam a 306° e 126°, não nos picos; a 50 Hz (3 ciclos) caíam nos picos. Com o sorteio ligado os entalhes ficam nos picos nas duas frequências.

Contagem de formas distintas em 2000 capturas simuladas (60 Hz, `seed_da_captura`, perfil `literatura`), mesma conta do professor:

| Classes | Sem sorteio (`set sorteio off`) | Com sorteio |
|---|---|---|
| 01, 10–16 | 1 | 1523 (01), 2000 (10–14, 16), 1560 (15) |
| 18 | 2 | 1770 |
| 02, 03, 05 | 5 | 2000 (02, 03), 1877 (05) |
| 04, 06–09, 17, 19, 20 | 2000 | 2000 |

A coluna "sem sorteio" reproduz exatamente os números do professor (1 em 01 e 10–16, 2 na 18, 5 em 02, 03, 05). Em 01, 05, 15 e 18 não chega a 2000 porque só a fase varia, com 3600 valores de 0,1° (colisão por aniversário).

Teste do critério: `test_formas_distintas_em_200_capturas` (> 150 de 200 em toda classe com sorteio; 1 em 01 sem).

## 2. Classes de pulso (02, 03, 04): fase de disparo e pré-trigger por captura

Fluxo na bancada (`ExperimentoNativo._capturar_real`, `mestre.py:2537`): `gerar()` roda com o rng da captura e é a fonte da verdade da posição; depois

1. `osc.definir_pre_trigger(duration_s, pre_trigger_s = t0 + margem_antes/fs)` (novo, `oscilloscope_orm.py:339`): reescreve só `:TIMebase:POSition`, com a mesma conta e a mesma compensação de referência (`CUSTOM`/`LEFT`) de `_programar_referencia_horizontal`; recusa pré-trigger fora de `[0, duração)` e uso antes de `configure_acquisition`;
2. `fonte.definir_fase_de_disparo(fase_de_disparo_graus(t0, fase_graus))` (`mestre.py:2519`): `(fase_graus + 360·f0·t0) mod 360`, que por construção é o θ sorteado, múltiplo de 0,1°, então a fase de disparo é exata e `gerar()` não difere da fonte por arredondamento;
3. `configurar()` põe `PULSe:WIDTh` = `d` sorteada (`largura_do_pulso_s`; 02, 03, 04).

Com `set sorteio off` o osciloscópio não é reposicionado e o caminho é o de antes (`FaseDeDisparoTests`, `test_sem_sorteio_o_osciloscopio_nao_e_reposicionado`: fase 216,0° e pré-trigger 60 ms).

As nativas de fase só (01, 05 CSINe, 18, 19) usam o mesmo `definir_fase_de_disparo` com `fase_graus` e pré-trigger 0. As classes TRACe levam a fase e o início dentro da própria forma (ver item 4).

NÃO VERIFICADO (sem hardware): (a) resolução real de `PULSe:WIDTh` (o código escreve `{d:.8g}` e `_transiente_esperado` inclui `PULSe:WIDTh?` para o readback, `ametek_orm.py:794`, mas não testei larguras de 8 a 166 ms no instrumento); (b) que o `*TRG` sincronizado em fase das listas `LIST:FREQuency` (18), do CSINe (05) e do modo ACDC (19) respeite `TRIGger:SYNChronize:PHASe` como o PULSe; (c) que a fase de disparo programada seja a vista na saída (`TRIGger:SYNChronize:PHASe?` nunca foi lido, ver docstring de `definir_fase_de_disparo`; quem confirma é a validação física).

## 3. Metadata

Novos campos no nível de cima de cada captura (`parametros` não os repete; `executar()` os move, `mestre.py:2331`): `inicio_disturbio_s`, `duracao_s`, `fase_graus`, e `sorteio_posicao` (booleano, quem lê saber se o sorteio estava ligado). Ausentes onde a classe não tem o item (ex.: 01 não tem início) e em todas as capturas com `sorteio_posicao = false`. A 08 os omite. Documentado em `docs/metadata.md`.

`pre_trigger_s` passa a ser o **efetivo da captura** (`_pre_trigger_atual_s`, `mestre.py:1386`) e não o atributo da classe: nas 02/03/04 com sorteio vale `t0`. Como `inicio_janela` e `recortar_margem.calcular_recorte` derivam dele, ficam corretos sem mudar `recortar_margem.py` (nenhuma edição lá foi necessária). Novo campo de verificação `pre_trigger_desvio_amostras` = `indice_trigger` lido do osciloscópio menos o previsto (`round(t0·fs) + margem_antes`); aviso se passar de 2 amostras. NÃO VERIFICADO no instrumento: não sei qual desvio o osciloscópio real mostra (hoje nenhuma classe grava esse número).

Efeitos em leitores (achados pelos testes, corrigidos): `analisar_sessao._reconstruir_esperado` usa `sorteio_posicao` e `fase_graus` do metadata (sessões antigas, sem o campo, reconstroem com as posições fixas); `scripts/recalibrar_extremos.py` passa `sorteio_posicao` do registro (sem isso, sessões de 07/10 seriam reconstruídas com o sorteio e as calibrações da v1.12 mudariam, o que quebrou 2 testes de recalibração); `_limitar_disturbio_para_bancada` (`mestre.py:2675`) calcula a senoide-base com a fase sorteada (sem isso, o limite de bancada a 220 V reduziria o distúrbio em torno de uma senoide de fase errada).

Simulação (`BENCH_MODE=0`, `run all` sem interação, 5 capturas por classe, 20/20 classes OK; pasta `.../scratchpad/sessao_sim_sorteio/`): trecho do metadata de `02_sag.jsonl`:

```json
{"id_captura": "02-0001", "classe": "SAG", "seed": 22260827, "sorteio_posicao": true,
 "inicio_disturbio_s": 0.019066666666666666, "duracao_s": 0.1559, "fase_graus": 264.06,
 "parametros": {"sag_pu": 0.1}}
{"id_captura": "02-0002", "classe": "SAG", "seed": 22260828, "sorteio_posicao": true,
 "inicio_disturbio_s": 0.047, "duracao_s": 0.10243333333333333, "fase_graus": 152.8,
 "parametros": {"sag_pu": 0.3}}
```

e de `10_sag_harmonics.jsonl`: `inicio_disturbio_s 0.018166…`, `duracao_s 0.163233…`, `fase_graus 287.7` (captura 1); `0.0316`, `0.132866…`, `298.54` (captura 2).

## 4. Estimativa de gravações de TRACe do `run all` e limite de ~280

**O que mudou no código** (`cli.py:299` `_aviso_escritas_trace`; `mestre.py` `capturas_efetivas_da_classe`): a conta continua `capturas TRACE × ciclos` (`ciclos = duração × f0` = 12 a 60 Hz, 10 a 50 Hz), mas agora o dicionário traz `escritas_trace_exatas` (= sorteio ligado) e a mensagem diz que a conta é exata: cada captura TRACE tem forma única e o cache de `program_capture` (`ametek_orm.py:1322`, assinatura de forma + tensão + frequência) nunca reaproveita, e dá o piso de tempo (≥ 1 s por TRACe, `time.sleep(1.0)` em `ametek_orm.py:1381`). `set sorteio off` volta à mensagem "até N" (teto). Linha emitida pelo `run all` com a configuração padrão:

```
ATENÇÃO — TRACe: 300 gravações na Flash da AMETEK nesta bateria (início/duração/fase sorteados: cada captura TRACE grava a Flash, sem reaproveitar o cache; pelo menos 300 s só de espera de gravação, 1 s por TRACe) (referência: a fonte travou na ~280.ª gravação de uma conexão em 2026-09-16). Considere 'run <NN>' por partes.
```

Origem dos 300: 06, 07, 08, 09, 17, 20 (3 capturas padrão × 12) = 216; 10–16 (1 × 12) = 84. As 02/03/04 continuam nativas (0 gravações), por isso a spec não as joga na Flash.

**Achado (gravidade média):** o `run all` padrão já estimava 300 > 280 antes desta mudança, porque a conta antiga também contava toda captura TRACE (teto); como as formas já eram distintas entre classes, o cache não reduzia nada na bateria padrão. O sorteio não aumenta o total padrão: ele elimina o desconto do cache em `set capturas N` com classes determinísticas (10–16 com N capturas por nível: antes ~12 gravações, agora 12·N; a estimativa antiga já contava 12·N, então ela superestimava e agora é exata). Ou seja: o risco da trava na ~280.ª já existia na bateria padrão.

**Proposta, sem implementar** (como lidar com o limite):

1. Dividir a bateria física em dois lotes abaixo de ~250 gravações, com reconexão da fonte entre eles (o contador `escritas_trace` é da instância; já é gravado por captura como `escritas_trace_na_conexao`). Com os números acima: lote A = 06, 07, 08, 09, 17, 20 (216), lote B = 10–16 (84) mais as nativas. NÃO VERIFICADO: se reconectar zera a condição que travou a fonte (pode ser desgaste/estado da Flash, não da conexão); só um teste na bancada responde.
2. Antes de mudar a bateria, usar `escritas_trace_na_conexao` do metadata das próximas sessões para achar o ponto de travamento real (hoje só há um ponto, 2026-09-16, ~280).
3. Se o lote único for obrigatório, o `run all` pode recusar acima de um limite configurável e pedir `run <NN>` por partes; a CLI já avisa, não recusa.

## 5. Tratamento do teste byte a byte do perfil `literatura`

O teste `test_literatura_reproduz_byte_a_byte_o_gerar_do_commit_34a0d82` **foi mantido e continua passando**: ele roda com `sorteio_posicao=False`, que reproduz as posições fixas de antes (60/80 ms, fase 0, sem campos novos em `parametros`; `t + 0.0` e `fase = 0` não alteram nenhum bit). Os testes de perfil (`PerfisDeFaixasTests._com_perfil`) isolam o perfil com sorteio desligado. Para o `gerar()` novo (sorteio ligado, padrão) há um fixture congelado próprio, `tests/fixtures/gerar_sorteio_v1_15.json` (mesmos 400 pontos: 20 classes × 60/50 Hz × 2 seeds × 5 índices; 128 assinaturas distintas porque o sorteio depende da seed, não do nível) e o teste `test_resultado_congelado_da_v1_15`. As 63 capturas de 07/10 continuam sendo literatura sem sorteio (`sorteio_posicao` ausente = falso).

Decisão de projeto: o sorteio vem **ligado por padrão** (`SORTEIO=0` ou `set sorteio off` desliga). Isso muda o dataset padrão, como a spec autoriza; o desligado é a ponte de volta ao dataset anterior, sem checkout do commit 34a0d82.

## 6. Testes

`.\env\Scripts\python.exe -m unittest tests.test_offline -v`: Ran 285 tests, OK (262 antes; 23 novos em `SorteioInicioDuracaoFaseTests` e ajustes). Cobertura do item 5 da spec:

- mesma seed → mesma forma e mesmos campos: `test_mesma_seed_mesma_forma_e_mesmos_campos` (20 classes × 60/50 Hz);
- seeds diferentes → início/fase diferentes: `test_seeds_diferentes_dao_inicio_e_fase_diferentes` (> 30 de 40 valores distintos);
- recorte com `pre_trigger_s` variável: `test_pulso_programa_fase_largura_e_pre_trigger_sorteados_e_o_recorte_acerta` (executa `executar()` da 02 em bancada com osciloscópio simulado que entrega o registro físico no pré-trigger pedido; `inicio_janela` e `calcular_recorte` devolvem exatamente `gerar()`), `test_recorte_acerta_a_janela_pelo_indice_do_trigger_sem_inicio_janela` (só `indice_trigger` + `pre_trigger_s` da captura) e `test_pre_trigger_varia_entre_capturas_da_mesma_classe`.

## 7. Riscos e pontos em aberto

| Item | Gravidade | Estado |
|---|---|---|
| Os fatores de `calibracao_extremos.json` foram medidos com posições/fases fixas; com fase e fim de evento sorteados o overshoot (ex.: volta de interrupção da 16, até 1,46× na sessão de 2026-09-30) pode ser outro. A previsão pré-captura usa o pico programado da forma sorteada × fator × margem; o teto continua guardado pela medida pós-captura (`_conferir_extremos_fisicos`, que para a classe) | alta (limite de hardware) | NÃO VERIFICADO; recalibrar depois da primeira sessão com sorteio. Nenhum limite (`max_peak_v` etc.) foi tocado |
| `program_capture` remove a média de cada ciclo (`ametek_orm.py:1353`); evento começando no meio do ciclo tem média real ≠ 0. Medido nas formas de `gerar()`: ~9 a 16 % dos ciclos das classes TRACE com evento têm \|média\| > 2 % do pico depois do sorteio (era 8 a 17 % antes, a 60 Hz o 60 ms já cai no meio do ciclo). Não piorou de forma sistemática (12 subiu de 8 % para 13 %; 10, 11, 13, 16 e 06 caíram), mas a validação física pode reprovar capturas | média | NÃO VERIFICADO no hardware; já existia |
| Início em 16,67 ms com duração até 166,67 ms: eventos longos fazem a classe quase não ter senoide limpa. É o que a spec pede ("até onde a janela permitir") | baixa | por projeto |
| Sorteio por captura: `set capturas N` com N > 1 em classes por nível dá N posições diferentes do mesmo nível (esperado) | baixa | por projeto |
| Em 01/05/18/19 (nativas só com fase) o disparo sincronizado em fase de LIST/CSINe/ACDC não foi testado | média | NÃO VERIFICADO (ver item 2) |
