# Classe 08: impulso fora da fronteira de ciclo (v1.15)

2026-10-12. Origem: proposta 2 e Pergunta 12 do `atividade.tex`. Tudo offline (`BENCH_MODE=0`); nada tocou o hardware. Autorização do dono de mudar o `gerar()` da 08: `AGENTS.md`.

Pedido que parece equivocado em um ponto (uma frase): o texto do `atividade.tex` chama a hipótese de "deslocamento de um ponto na TRACE"; os dados a recusam (item 1) e a causa não está na montagem, então a correção foi feita onde o código controla, na posição do impulso.

## 1. Por que o impulso vai para o fim do ciclo

Sessões lidas: `resultados/sessao_2026-10-07_127V_50Hz` (08 a 50 Hz, 3 capturas) e `resultados/sessao_2026-10-07_14-59-54_run02` (08 a 60 Hz, 3 capturas). Janela = registro bruto a partir de `indice_trigger` (595 nas seis capturas, metadata `08_transient.jsonl`); "desvio" = `medido - sin(2π·f0·t)`.

**A. A montagem não desloca nada.** `AmetekMX30.montar_programacao` (`logica/ametek_orm.py:1322`) reamostra cada ciclo com `_resample_cycle` (`:1316`), `np.interp` de `arange(n)/n` para `arange(1024)/1024`: a amostra 0 do ciclo vai para o ponto 0 da TRACE. Resultado para 2 amostras de impulso na amostra 0 do ciclo (`_resample_cycle` de um pulso unitário):

```
600 amostras/ciclo (50 Hz): pontos 0..5 = [1.0 1.0 0.8281 0.2422 0 0]; últimos 3 pontos = 0
500 amostras/ciclo (60 Hz): pontos 0..5 = [1.0 1.0 1.0 0.5352 0.0469 0]; últimos 3 pontos = 0
```

e `ProgramacaoCaptura.programada_pu()` (`:120`) devolve o impulso exatamente nas amostras 2400 e 2401 (50 Hz com o `forma_para_bancada` gravado: amplitude 1,3375 pu; teste `test_montagem_da_trace_nao_desloca_o_impulso_a_50_nem_a_60hz`, que cobre 50 Hz em 2400 e 2700 e 60 Hz em 2400). Os `tres_versoes/08_*.npz` das sessões dizem o mesmo (`programada_pu`: maior desvio em 2400). Ou seja, o que o código manda tem o impulso a 80 ms; o fim do ciclo vem de depois do `TRACe:DATA`.

**B. O que a fonte fez.** Maior desvio e primeiras amostras com |desvio| > 0,2 pu:

| Sessão | Captura | Amostras com \|desvio\| > 0,2 (início / fim) | Maior desvio |
|---|---|---|---|
| 50 Hz | 08-0001, 08-0002 | 2999 ... 3008 | 1,887 pu em 3000 (100,00 ms) |
| 50 Hz | 08-0003 | 2997 ... 3006 | 1,316 pu em 2998-2999 |
| 60 Hz | 08-0001, -0002, -0003 | 2399 ... 2408 | 1,93 / 1,82 / 1,66 pu em 2400-2401 |

A 50 Hz não há nada no 80 ms: `max |desvio|` em 2380..2440 é 0,036 pu. Na 08-0003 o impulso veio 2 a 3 amostras antes das outras duas (jitter entre capturas).

**C. A hipótese de um ponto é recusada.** Se a fonte tocasse a TRACE do ciclo 4 avançada de `k` pontos (os primeiros `k` pontos vão para o fim do ciclo, como na hipótese), a fração do impulso que ficaria no início do ciclo seria, para 600 amostras/ciclo (pesos acima): k=1: 67 %, k=2: 35 %, k=3: 8 %, k=4: 0 %. O sinal medido tem a área do desvio (soma do desvio menos a linha de base, 45 amostras) assim:

| Captura (50 Hz) | Área em 2395..2440 (80 ms) | Área em 2990..3035 (100 ms) | Fração em 80 ms |
|---|---|---|---|
| 08-0002 | -0,173 | 2,560 | -7 % |
| 08-0001 | -0,087 | 2,366 | -4 % |
| 08-0003 | +0,300 | 2,191 | +12 % |

(60 Hz, mesma conta em 80 ms: 3,25 / 3,18 / 3,11, coerente em razão com a amplitude programada e os pesos acima: 1,618 pu × 3,58 contra 1,3375 pu × 3,07.) Com no máximo 12 % do impulso no início (e valores negativos, ou seja, ruído), k=1 e k=2 ficam de fora; o dado aceita k >= 3 pontos (>= 59 µs, 1,8 amostra a 50 Hz), sem diferenciar 3 de 4 ou mais. A conta supõe que o filtro da fonte conserva a área (ganho DC 1); NÃO VERIFICADO.

**D. O que não consegui separar.** A 60 Hz o impulso está em 2400-2401, onde foi programado (desvio medido: +0, +0, -1 amostra, ver item 3). Um avanço constante de 3 a 4 pontos seria de 1,5 a 2 amostras a 60 Hz (0,488 amostra por ponto), mas o atraso próprio da subida da fonte pode compensá-lo; com as seis capturas não dá para separar os dois. Por isso a causa fica como:

- **Confirmado**: a montagem (`montar_programacao`/`_resample_cycle`) não é a causa; não foi alterada (`git diff -- logica/ametek_orm.py` vazio).
- **Refutado**: "deslocamento de um ponto".
- **NÃO VERIFICADO**: o mecanismo dentro da fonte (começar a tocar a TRACE alguns pontos adiante, fase do oscilador no instante da troca de passo do LIST, outro). Teria de ser testado na bancada com uma TRACE de marcador em pontos conhecidos (por exemplo 0, 1, 2, 3, 4, 8, 16), a 50 e 60 Hz, medindo a amostra da marca; não faz parte desta entrega.
- Efeito colateral medido: a classe 09 a 50 Hz começa também na fronteira (80 ms) e não aparece deslocada: correlação cruzada entre `programada` e medida nas 3 capturas de `sessao_2026-10-07_127V_50Hz` dá lag de -1, 0 e -1 amostra (correlação 0,83 a 0,88). A oscilação da 09 nasce de zero, então o que se perde no começo do ciclo não aparece; só um evento com borda abrupta no ponto 0 mostra o deslocamento.

Reproduzir A: `AmetekMX30.montar_programacao(forma, base_voltage_rms=127.0, frequency_hz=50.0)` com `forma = sin(2π·50·t)` e `forma[2400:2402] += 1.3374832769767175`. Reproduzir B/C: ler `tensao_pu` do `.npz` da sessão a partir de `indice_trigger` e subtrair a senoide.

## 2. O impulso nunca cai a menos de N amostras da fronteira

`experimentos_waveform/08.py`: `_indices_impulso(fs_hz, f0_hz=None)` (`:81`). Com `sorteio_posicao` ligado (padrão), se o início preferido (80 ms = amostra 2400) estiver a menos de `DISTANCIA_MIN_FRONTEIRA_AMOSTRAS` (`:34`) = **30 amostras (1 ms)** da fronteira anterior, ou o fim do impulso a menos de 30 da seguinte, ele vai para o meio do mesmo ciclo. `gerar()` e `forma_para_bancada()` usam a mesma função.

| f0 | Ciclo | Início antes | Início agora | Partida da senoide | Inclinação |
|---|---|---|---|---|---|
| 50 Hz | 600 amostras | 2400 (resto 0, **na fronteira**) | 2700 (90 ms, resto 300) | 0 pu (antes 0 pu) | negativa (antes positiva) |
| 60 Hz | 500 amostras | 2400 (resto 400, distância 98 à seguinte) | 2400, igual | -0,95 pu | igual |

**N = 30, porque**: (a) o deslocamento medido envolve no máximo ~4 pontos da TRACE, 2,3 amostras a 50 Hz (item 1); (b) as capturas diferem entre si em até 3 amostras (item 1B); (c) o toque da fonte após o impulso dura < 0,5 ms = 15 amostras (`experimentos_waveform/08.py`, comentário do `SOBRESSINAL_DO_DEGRAU`), então 30 amostras mantêm toda a oscilação dentro do mesmo passo do LIST. É uma margem de 10x sobre (a) e (b); o valor não é otimizado, só conservador, e a regra leva o impulso ao meio do ciclo (300 amostras de cada lado), muito além do mínimo. NÃO VERIFICADO na bancada: que 30 baste para todo mecanismo possível do item 1.

**Posição fixa e não sorteada** (justificativa). A decisão da spec de sorteio (`sorteio_inicio_fase.md`) fica: a 08 não sorteia posição nem fase, porque `SOBRESSINAL_DO_DEGRAU = 0,55` e `SUBSINAL_DO_DEGRAU = 0,70` foram medidos com a partida em um ponto específico. A 50 Hz o novo ponto é cruzamento por zero como o de antes (0 pu); a inclinação da senoide muda de sinal, o que baixa o pico real em ~0,01 a 0,03 pu (a senoide desce durante os 30 a 100 µs até o pico do toque, em vez de subir). O limite previsto não mudou: `pico_previsto_v` = 374,22 V a 127 V e a 230 V; a amplitude passou de 1,3375 para 1,3442 pu (127 V) e de 0,7355 para 0,7423 pu (230 V), porque o antigo `partida_max` era o da segunda amostra (+0,0105 pu, senoide subindo) e agora é ~0. Saída do `forma_para_bancada` offline (`c3.py` no scratchpad): `sorteio False: 2400, amp 1.3375 / 0.7355`, `sorteio True: 2700, amp 1.3442 / 0.7423`, vale previsto -179,61 V e -325,27 V iguais. `forma_para_bancada` calcula a amplitude pela partida real (`base[indices]`, `08.py:129-132`); se um dia a posição for sorteada, o limite de pico segue válido, mas a calibração do sobressinal teria de ser refeita para partidas fora do cruzamento por zero.

**Com `set sorteio off`** o 80 ms de antes volta, também a 50 Hz (reproduz as sessões de 07/10 e o commit 34a0d82; é a defeituosa de propósito). Por isso `tests/fixtures/gerar_literatura_34a0d82.json` não mudou.

**Fixture regravado**: `tests/fixtures/gerar_sorteio_v1_15.json`, só as 10 entradas `08/50/*` (2 seeds x 5 índices); as 390 outras, incluindo `08/60/*`, iguais (conferido por diff: 11 linhas, 10 hashes + a linha `versao`).

Teste: `Classe08FronteiraTests` (`tests/test_offline.py:6033`):
- `test_o_impulso_nunca_cai_a_menos_de_n_amostras_da_fronteira_a_50_e_60hz`;
- `test_qualquer_inicio_preferido_e_empurrado_para_fora_da_fronteira`: varre todo início preferido de 0 a 5997 amostras, a 50 e 60 Hz, e exige >= 30 de cada lado (e que a regra não mexa quando já está longe);
- `test_50hz_vai_para_90ms_...`, `test_sorteio_desligado_reproduz_o_80ms_...`, `test_forma_para_bancada_...`.

## 3. A validação física confere a posição

`ExperimentoBase._validar_fisicamente` (`logica/mestre.py:1660`) ganhou o gancho `conferir_posicao_do_evento` (`:1727`; padrão `None`, só a 08 o implementa em `08.py:180`) e o parâmetro `inicio_janela` (passado de `metadados[-1]["inicio_janela"]`, `:2563`). A janela de posição é a alinhada ao **trigger real** (`inicio_janela` = `indice_trigger` = 595), não a `margem_antes` (600) que a validação de envelope usa; a validação de envelope/THD/crista continua igual, com a exclusão dos dois ciclos do impulso.

Regra: o maior |medido - senoide| tem de cair a até `TOLERANCIA_POSICAO_AMOSTRAS` = **10** amostras (0,33 ms) do início do impulso programado; e esse desvio tem de ser >= 0,25 da amplitude de bancada (`FRACAO_MIN_DESVIO_VISIVEL`; a saída fez 1,4x). Fora disso `validacao_fisica.ok = false` com o motivo "posição do impulso: pico medido na amostra X (… ms), previsto Y (… ms); diferença …" ou "impulso não encontrado", e a captura é marcada inválida pelo caminho de sempre (gravada, contada em `invalidas`). Sempre grava `validacao_fisica.posicao_evento` (`inicio_previsto_amostra`, `pico_medido_amostra`, `desvio_amostras`, `tolerancia_amostras`, `desvio_pico_pu`). 10 amostras: > o atraso/jitter medido (<= 3) e 60x abaixo do deslocamento de 20 ms.

Conferido com as 6 capturas reais de 07/10, com a regra e as posições de antes (`sorteio off`):

```
50 Hz 08-0002  ok=False desvio=+600  1.887 pu  posição do impulso: pico medido na amostra 3000 (100.00 ms), previsto 2400 (80.00 ms)
50 Hz 08-0001  ok=False desvio=+600  1.887 pu
50 Hz 08-0003  ok=False desvio=+597  1.316 pu
60 Hz 08-0002  ok=True  desvio=0     1.816 pu
60 Hz 08-0001  ok=True  desvio=0     1.931 pu
60 Hz 08-0003  ok=True  desvio=-1    1.659 pu
```

Testes: `test_validacao_confere_a_posicao_do_impulso` (aceita -3..+10, recusa 600, -600, 11, -14, 300 e a ausência de impulso), `test_validacao_fisica_reprova_o_impulso_deslocado_que_a_exclusao_de_ciclos_escondia` (caminho completo com registro de 8100 amostras e trigger em 595), `test_classes_sem_posicao_a_conferir_nao_mudam_a_validacao`.

Limite: o teste usa um toque sintético de 7,5 kHz; a captura a 90 ms só prova o comportamento na bancada. NÃO VERIFICADO.

## 4. Documentação como "impulso filtrado pela fonte"

`README.md`, seção 4.1 (nova): o modelo pede 5 a 10 pu em 50 µs; o que sai é um impulso de baixa amplitude filtrado pela fonte; as três limitações (amplitude: teto de 374,2 V, 1,34 pu a 127 V e 0,74 pu a 230 V; velocidade: 200 µs de subida do datasheet contra 50 µs; representação: 1024 pontos por ciclo, 3 a 4 pontos para o impulso). Também `docs/metadata.md` (`parametros.inicio_impulso_s`, `validacao_fisica.posicao_evento`) e `CHANGELOG/v1.15.md`. A campanha separada a ~30 V fica como opcional (comentário do professor); não implementada.

## 5. Roteiro de recaptura da 08 a 127 V / 50 Hz (não executado)

Objetivo: três capturas da 08 com o impulso em 90 ms, confirmado pela validação. Não ativar corrente. Nenhuma confirmação abaixo pode ser automatizada.

Antes de ligar:
1. Fiação como na sessão de 07/10; **disjuntor da bancada fechado** (em 07/10 houve captura com a saída aberta: o osciloscópio mediu ruído); E-stop acessível; EUT conectado.
2. Árvore limpa: `git status` sem alterações rastreadas (a sessão grava `versao_codigo`; o aviso "árvore SUJA" aparece no `run`). Isto exige que a mudança desta entrega esteja commitada antes.

Comandos:

```powershell
cd C:\Users\denis\TCC\code
scripts\START_BENCH.cmd
```

3. Fator da probe de tensão: o gravado fisicamente na probe diferencial (nas sessões de 07/10, `probe_tensao` = 500 no metadata; **confirmar na probe**, não presumir). Tensão **127** e frequência **50**.
4. Na CLI, nesta ordem:
   - `status`: conferir `sorteio` = on (padrão), perfil `literatura`, capturas da 08 = 3 (padrão da classe), **sem** `set capturas` (com ele a 08 vira rampa de caracterização, não é o que se quer). Se a CLI tiver sido iniciada com `SORTEIO=0` no ambiente, `set sorteio on`.
   - `comm` e `trigger` (não energizam).
   - `run 08`; digitar `EXECUTAR-CLASSE-08` (case-sensitive) só depois de conferir probe, cabos, E-stop e EUT. (`lowvoltage` e `native` só se a fiação ou a probe foram mexidas.)
5. Durante: o log mostra `[08] impulso FÍSICO 1.344 pu ... previsto pico 374 V / vale -180 V (teto 374 V)` e a checagem fonte x CH1 (v1.14) antes da primeira classe. Se a checagem fonte x CH1 reprovar (relação ~0,45), parar: é saída aberta/probe, não a 08.

O que conferir depois (pasta `resultados\sessao_<data>`):
6. `sessao.log`: nenhum `NÃO corresponde ao que foi programado`; resumo da classe `OK`, 3/3 capturas boas.
7. `metadata\08_transient.jsonl`, por captura:
   - `parametros.inicio_impulso_s` = 0.09;
   - `validacao_fisica.ok` = true e `validacao_fisica.posicao_evento.desvio_amostras` entre -3 e +3 (aceitável até ±10; 07/10 a 60 Hz deu 0, 0, -1) e `pico_medido_amostra` ≈ 2700;
   - `pico_medido_v` <= 374,2 (`teto_extremos_v`); em 07/10 foi 350 V com sobressinal 0,457: um sobressinal maior que 0,55 ou o pico acima do teto é achado de segurança, parar e avisar;
   - `indice_trigger`/`inicio_janela` iguais entre as capturas (±2).
8. Visual: `tres_versoes\08_*.npz` (`programada_pu` contra `medida_pu`): o impulso medido em 90,0 ms, não em 80 nem 100 ms.
9. Se alguma captura reprovar por posição: não repetir sozinho; entregar `metadata\08_transient.jsonl` e o `sessao.log`. Se a posição for aprovada mas o pico passar do teto, idem.

Resultado esperado, como em 07/10: impulso medido de ≈ 1,9 pu (350 V) seguido de oscilação de ~7,5 kHz que morre em < 0,5 ms: "impulso filtrado pela fonte" (item 4), mas agora em 90 ms.

## Achados e NÃO VERIFICADO (com gravidade)

- **Média**: o deslocamento para o fim do ciclo é comportamento da fonte, não do código; o mecanismo está em aberto (item 1D). Outras classes com borda abrupta no início de um ciclo podem sofrer o mesmo (um SAG/SWELL/PULSE por TRACe começando a < ~2 amostras da fronteira); com o início sorteado isso tem chance de ~0,4 % por captura (2,3/600). Não tratado nem medido.
- **Baixa**: a validação de envelope/THD usa `margem_antes` (600) como início da janela, e a janela real começa em `indice_trigger` (595 em 07/10): 5 amostras de diferença. Não afeta o envelope (insensível) e não foi alterada; a conferência de posição usa o alinhamento correto.
- **Baixa**: a 08 a 230 V continua com 0,74 pu (pico ≈ 1,15 pu): não foi recapturada nem faz parte do roteiro; sem classe 08 a 230 V no conjunto curado (`atividade.tex`, Pergunta 12).
- **Baixa**: `set sorteio off` reproduz de propósito o 80 ms defeituoso a 50 Hz; quem usar `off` a 50 Hz e capturar a 08 verá a validação reprovar (comportamento correto).
- NÃO VERIFICADO: recaptura a 127 V/50 Hz (roteiro acima), que o pico a 90 ms mantém o sobressinal de 0,457 (a partida e o nível são os mesmos, a inclinação da senoide é contrária), que 30 amostras de margem bastam em toda hipótese, e a conservação da área do filtro da fonte usada no item 1C.

Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline -v` -> Ran 329 tests, OK.
