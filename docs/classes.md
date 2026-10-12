# As 20 classes de distúrbio

Especificação original: `experimentos.txt`. Este documento descreve o que o **código atual** (commit `d37e403`) faz. Faixas por perfil: `docs/perfis.md`. Como criar uma classe: `docs/estender.md`.

Todas geram 200 ms = 6000 amostras a 30 kSa/s, em pu, por `gerar(t, f0, capture_index, rng)` (`ExperimentoBase.gerar`, `mestre.py:1495`). No **simulado** só `gerar()` importa. Na **bancada** a classe é **nativa** (a fonte produz o distúrbio com um recurso próprio) ou **waveform** (o Python calcula a forma, a fonte a toca por TRACe/LIST).

## 1. Tabela

`Sorteio` = o que `gerar()` sorteia com `set sorteio on` (padrão): F = fase; I = início; D = duração. `Pad.` = `capturas_padrao`.

| # | Nome | Arquivo | Mecanismo na bancada | Parâmetros (perfil `literatura`) | Sorteio | Pad. |
|---|---|---|---|---|---|---|
| 01 | NORMAL | nativos/01 | STEP para a base (`trigger_step`), só gera o trigger | — | F | 1 |
| 02 | SAG | nativos/02 | PULSe (`trigger_pulse`) | nível 0,1/0,3/0,5/0,7/0,9 pu por `capture_index` | I D F | 1 |
| 03 | SWELL | nativos/03 | PULSe | 1,1/1,2/1,4/1,6/1,8 pu | I D F | 1 |
| 04 | INTERRUPTION | nativos/04 | PULSe | nível U(0; 0,09) pu | I D F | 3 |
| 05 | HARMONICS | nativos/05 | até 20 % de THD: `SOURce:FUNCtion:SHAPe CSINusoid` + `:CSINusoid <THD>` (senoide clipada); acima: TRACe | THD 5/10/15/20/30 % | F | 1 |
| 06 | FLICKER | waveform/06 | TRACe/LIST | modulação U(8; 25) Hz, profundidade U(0,05; 0,15) | F | 3 |
| 07 | NOTCH | waveform/07 | TRACe/LIST | 2–4 pulsos de 0,1 ms por ciclo nos picos, em **todos** os ciclos | F | 3 |
| 08 | TRANSIENT | waveform/08 | TRACe/LIST | impulso de 2 amostras (50 µs), U(5; 10) pu no modelo | — | 3 |
| 09 | OSCILLATORY_TRANSIENT | waveform/09 | TRACe/LIST | f U(300; 2400) Hz, duração U(10; 40) ms, 0,3 pu, τ = 5 ms | I F | 3 |
| 10 | SAG_HARMONICS | waveform/10 | TRACe/LIST | sag U(0,1; 0,9), THD U(0,05; 0,20) | I D F | 3 |
| 11 | SAG_FLICKER | waveform/11 | TRACe/LIST | sag, profundidade (faixa da 06), flicker U(8; 25) Hz | I D F | 3 |
| 12 | SAG_OSCILLATORY_TRANSIENT | waveform/12 | TRACe/LIST | sag, oscilação U(300; 2400) Hz | I D F | 3 |
| 13 | SWELL_HARMONICS | waveform/13 | TRACe/LIST | swell U(1,1; 1,8), THD U(0,05; 0,20) | I D F | 3 |
| 14 | SWELL_OSCILLATORY_TRANSIENT | waveform/14 | TRACe/LIST | swell, oscilação | I D F | 3 |
| 15 | HARMONICS_FLICKER | waveform/15 | TRACe/LIST | THD, profundidade, flicker (200 ms inteiros) | F | 3 |
| 16 | INTERRUPTION_HARMONICS | waveform/16 | TRACe/LIST | 0,05 pu + THD U(0,05; 0,20) | I D F | 3 |
| 17 | NOTCH_OSCILLATORY_TRANSIENT | waveform/17 | TRACe/LIST | entalhes contínuos (como 07) + oscilação de 300 Hz em `t0` | I F (fase acoplada a `t0`) | 3 |
| 18 | FREQUENCY_DRIFT | nativos/18 | `LIST:FREQuency` de 2 pontos (`frequency_drift_list`) | rampa f0−3 → f0+3 Hz (e o inverso nas capturas ímpares) | F | 1 |
| 19 | DC_OFFSET | nativos/19 | `SOURce:MODE ACDC` + `SOURce:VOLTage:OFFSet` | offset U(0,02; 0,10) pu | F | 3 |
| 20 | INTERHARMONICS | waveform/20 | TRACe/LIST | 3 componentes em 145/210/330 Hz, amplitude U(0,03; 0,08) cada | F | 3 |

Fontes: arquivos das classes; `capturas_padrao` e sorteio conferidos por leitura (`experimentos_*/NN.py`) e por `capturas_efetivas_da_classe` (50 capturas planejadas com os padrões). As compostas 10–16 sorteiam os parâmetros listados com `perfis.composto` quando o sorteio está ligado; desligado valem os valores fixos de `docs/perfis.md`.

### Onde o código difere de `experimentos.txt`
- Início/duração: a especificação fixa 60 ms / 60 ms (80 ms nas 08/09); com o sorteio ligado eles são sorteados (`sortear_posicao`, `mestre.py:810`: início ≥ 1 ciclo da borda, duração de ½ ciclo até 200 ms − 2 ciclos, fase U(0°, 360°) em passos de 0,1°). `set sorteio off` reproduz as posições fixas.
- 05: o modelo dos níveis ≤ 20 % é a senoide clipada normalizada por rms (`sinais.senoide_clipada_pu`), não a soma de harmônicas; só o nível por TRACe (30 %) usa a soma 3ª/5ª/7ª.
- 07 e 17: entalhes em **todos** os ciclos da janela (IEEE 1159-2019, 4.4.5.4), não só 4 ciclos a partir de 60 ms.
- 18: rampa f0 ± 3 Hz (47 → 53 Hz a 50 Hz); sorteio desligado: 57 → 63 Hz.
- 20: frequências 145, 210 e 330 Hz (150 Hz foi removido por ser 2,5ª harmônica a 60 Hz).
- Perfil `norma`/`fronteira` mudam níveis das 02, 03, 05, 06, 10–16, 20 (`docs/perfis.md`).
- A especificação cita 400 capturas por nível/faixa; o número real é `SIM_CAPTURES_PER_CLASS` (simulado) ou o plano da bancada.

## 2. Capturas por classe na bancada

Número que roda = `max(set capturas N ou REAL_CAPTURES_PER_CLASS, capturas_padrao da classe)`, **por nível** nas classes com níveis (02, 03, 05) (`Config.capturas`, `mestre.py:730`; `dimensionar_capturas`, `:1517`). Padrão 3 nas classes cujo `gerar()` sorteia parâmetros: **04, 06–17, 19, 20**; padrão 1 nas demais (01, 02, 03, 05, 18). Com os padrões: 50 capturas planejadas.

Sem `set capturas` as capturas padrão sorteiam (a 08 aplica o impulso máximo seguro em todas). Com `set capturas` (qualquer N), 04/06/09/19 cobrem o intervalo do parâmetro com `linspace` (`sinais.valor_para_captura`, `sinais.py:24`) e a 08 faz a rampa de caracterização sobre o total efetivo.

Seed da captura: `BASE_SEED + int(id) × 1 000 000 + indice_global` (`mestre.py:1536-1540`). 04 e 19 repetem essa conta em `configurar()` com o id fixo (`base_seed + 4_000_000 + capture_index`, `04.py:36`; `19_000_000`, `19.py:32`) — só vale porque nessas classes `capture_index == indice_global`.

## 3. Classe 08: impulso filtrado pela fonte

O modelo (`gerar()`) é um impulso unidirecional de 5 a 10 pu somado à senoide, 2 amostras (50 µs). **A bancada não o reproduz**; a captura física da 08 deve ser descrita como "impulso de baixa amplitude filtrado pela fonte (um pico seguido de oscilação de ~7,5–10 kHz que morre em < 0,5 ms)". Três limitações independentes:
1. **Amplitude**: teto de 0,9 × `max_peak_v` = 374,2 V (2,084 pu a 127 V). Amplitude máxima segura (rodando `forma_para_bancada`, 2026-10-12): 127 V/60 Hz **1,618 pu** (limita o vale), 127 V/50 Hz **1,344 pu** (limita o pico), 220 V/50 Hz 0,776 pu, 220 V/60 Hz 0,360 pu, 230 V/50 Hz 0,742 pu, 230 V/60 Hz 0,285 pu. Dimensionada com `SOBRESSINAL_DO_DEGRAU = 0,55` e `SUBSINAL_DO_DEGRAU = 0,70` (medidos 0,38–0,457 e 0,55–0,58).
2. **Velocidade**: o datasheet dá 200 µs para 10–90 % do fundo de escala; o impulso de 50 µs acaba antes da subida. Mede-se a resposta do amplificador ao degrau.
3. **Representação**: cada TRACe tem 1024 pontos por ciclo (19,5 µs a 50 Hz); o impulso ocupa 3–4 pontos.

Posição: 80 ms (60 Hz). A 50 Hz o 80 ms cai na fronteira de ciclo e a fonte tocou o impulso a 100 ms (3 capturas de 07/10); com o sorteio ligado o impulso vai para 90 ms (meio do mesmo ciclo), nunca a menos de 30 amostras (1 ms) de uma fronteira (`08.py:34,81-98`). A validação física confere que o maior desvio da senoide está a ≤ 10 amostras do início previsto (`conferir_posicao_do_evento`, `08.py:180`); senão a captura é marcada inválida. Mecanismo do deslocamento: **NÃO VERIFICADO** (`docs/analise-2026-10-12/classe08_fronteira.md`). A 08 fica fora do sorteio de posição/fase porque o sobressinal foi calibrado para um ponto de partida.

## 4. Classe 05 e o teto do CSINusoid

`MAX_CSINE_THD_PCT = 20` (`ametek_orm.py:156`). Perfil `literatura`: 5/10/15/20 % por CSINusoid e 30 % por TRACe (`usar_trace`, `05.py:69`). Perfil `norma`: todos ≤ 20 %, todos por CSINusoid. O nível de 2 % e o rms da CSINusoid interna **não foram verificados na bancada**.
