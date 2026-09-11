# Sessão de bancada v1.8 — margem de captura, diagnóstico, sessões isoladas e cobertura de níveis

Data: 2026-09-11
Status: aprovado em chat (brainstorming), aguardando revisão do spec escrito

## Contexto

Depois de inspecionar visualmente as 20 capturas da última sessão de bancada
(comparação gerado-vs-capturado, ver conversa), ficou confirmado que o
"atraso de ~20ms" documentado no `CHANGELOG/v1.7.md` é na verdade, em pelo
menos 14 das 20 classes, um **corte de conteúdo real**: a janela de captura
tem duração fixa (200ms/6000 amostras) e o conteúdo útil começa ~20ms depois
do que a janela assume, então a cauda do distúrbio é perdida. Além disso,
`08/TRANSIENT` sorteia amplitude em 5-10pu (`experimentos.txt`) que a 127V é
sempre cortada pro mesmo teto físico (~2,1pu) — qualquer captura extra hoje
seria redundante, não trariam cobertura nova.

Nenhuma dessas causas raiz está confirmada em bancada ainda — só por análise
de código e manual (ver `CHANGELOG/v1.7.md`, seção "Investigação em aberto").
Este spec cobre a infraestrutura pra próxima sessão física confirmar (ou
refutar) as hipóteses e coletar dados de melhor qualidade, não a correção
definitiva do atraso em si (que depende do que a bancada mostrar).

## Objetivo desta mudança

Preparar quatro capacidades novas na CLI/`mestre.py`, todas op-in (nada muda
no comportamento hoje sem o operador pedir explicitamente):

1. **`set margin on|off`** — captura com folga extra antes/depois da janela
   nominal, salva bruta, sem recorte automático.
2. **`set diagnostico on|off`** — instrumentação extra (log de
   `STATus:OPERation:CONDition?`/`OUTPut:STATe?`/tensão imediata) em pontos-
   chave de `run`/`run all`, pra testar ao vivo as hipóteses do
   `CHANGELOG/v1.7.md` (o "*WAI except for transients" e a suspeita de que
   entrar em `VOLTage:MODE LIST` zera a saída).
3. **`set capturas <N>`** — quantas capturas por classe na bancada real (hoje
   fixo em 1 via `REAL_CAPTURES_PER_CLASS`), com cobertura determinística de
   níveis/parâmetros em vez de sorteio redundante.
4. **Sessão isolada por pasta** — `resultados/sessao_<timestamp>/` em vez de
   sempre escrever em cima de `resultados/`, e um `.npz` por captura
   individual em vez de um `.npz` por classe com N capturas empilhadas.

Mais um script novo, offline (sem hardware): `logica/analisar_sessao.py`,
que generaliza a análise manual desta sessão (cross-correlação/onset, tabela
de deslocamento, razão de pico, PNGs lado-a-lado) pra rodar contra qualquer
pasta de sessão.

## Fora de escopo

- Corrigir a causa raiz do atraso/zeragem em si — depende do que
  `diagnostico on` e as capturas com `margin on` mostrarem na próxima
  bancada. Este spec só prepara a instrumentação.
- Qualquer mudança no caminho de geração do dataset **simulado**
  (`SIM_CAPTURES_PER_CLASS`, a ordem/fórmula que `gerar()` usa pra indexar
  `NIVEIS` hoje, os valores de `experimentos.txt`). Tudo isso continua
  bit-a-bit idêntico — as mudanças de cobertura de níveis/parâmetros valem
  **só** para `REAL_CAPTURES_PER_CLASS`/`set capturas`, nunca para
  `SIM_CAPTURES_PER_CLASS`.
- Mudar `max_voltage_rms`/`max_peak_v`/`max_current_a`, remover validações,
  ou dispensar qualquer confirmação de energização — nenhum dos "Limites
  inegociáveis" do `AGENTS.md` muda.

## Componentes afetados

| Arquivo | Natureza da mudança |
|---|---|
| `logica/mestre.py` | `Config` ganha campos novos; `ExperimentoBase.executar()`/`_capturar_real()`/`_validar_captura()`/`_salvar_classe()` passam a suportar captura com margem e N capturas por classe; novo helper de amostragem determinística; `_build_config()` lê os novos globais mutáveis. |
| `logica/cli.py` | novo `cmd_set`; `HELP_TEXT` atualizado; sessão calcula (uma vez, lazy) a pasta `sessao_<timestamp>`; `cmd_status` mostra os novos toggles. |
| `logica/ametek_orm.py` | pontos de log adicionais (gated por `diagnostico on`) em `arm()`/`arm_transient()`/`program_capture()` — leitura de `STATus:OPERation:CONDition?` e tensão imediata; **nenhuma mudança de comportamento SCPI fora do log**. |
| `logica/oscilloscope_orm.py` | nenhuma mudança de API — `configure_acquisition()` já aceita `points`/`duration_s`/`pre_trigger_s` arbitrários; só passa a ser chamado com valores maiores quando `margin_mode`. |
| `experimentos_nativos/04.py`, `19.py` e `experimentos_waveform/06.py`, `08.py`, `09.py` | trocam `rng.uniform(lo, hi)` por um helper novo (`sinais.valor_para_captura`) que decide entre sorteio (hoje) e cobertura determinística (bench, N>1) — mesma assinatura de `gerar()`, sem quebrar o dataset simulado. |
| `experimentos_nativos/02.py`, `03.py`, `05.py` | **nenhuma mudança de código** — a repetição por nível (blocked, N por nível) é resolvida inteiramente do lado de fora, em `executar()` (ver "Cobertura de níveis" abaixo). |
| `logica/analisar_sessao.py` (novo) | script offline, sem hardware — mesmo padrão de `visualizador.py`. |
| `tests/test_offline.py` | novos testes cobrindo margem, `set capturas`, o helper de amostragem determinística, e a criação de sessão — tudo em modo simulado. |
| `CHANGELOG/v1.8.md` (novo) | registro da versão, seguindo a convenção já usada em v1.0–v1.7. |
| `README.md` | seção 5.3 (referência de comandos da CLI) e 5.8 (onde os dados caem) atualizadas para refletir sessão por pasta e os novos `set`. |

## Design detalhado

### 1. Sessão isolada por pasta

`SessaoCLI` calcula `self.sessao_dir = RESULTS_DIR / f"sessao_{timestamp}"`
uma vez, no `__init__` (timestamp fixo pro resto do processo). Só é
**criada** (`mkdir`) na primeira gravação de dado — `status`/`comm`/`trigger`
sem `run` não deixam pasta vazia. `SessaoCLI` espelha o valor num global
mutável `mestre.SESSION_RESULTS_DIR` (mesmo idioma já usado por
`autorizar_saida()` para `OUTPUT_ARMED` — processo de longa duração, módulo
importado uma vez, precisa de um jeito de mudar estado depois do import).
`_build_config()` passa a usar `SESSION_RESULTS_DIR or RESULTS_DIR` (raiz
`resultados/` direto continua sendo o padrão fora da CLI interativa — testes,
scripts standalone). `ResultadoClasse.arquivo_esperado` (hoje hardcoda
`RESULTS_DIR`) é ajustado para refletir múltiplos arquivos por classe (ver
próxima seção) em vez de um caminho único.

`visualizador.py` recebe caminho explícito por argumento — não é afetado.

### 2. Um `.npz` por captura (em vez de empilhado)

Hoje `_salvar_classe()` grava UM `.npz` por classe com `tensao_pu.shape =
(N, 6000)`. Passa a gravar um arquivo por captura individual:

```
resultados/sessao_2026-09-15_14-30-00/
  02_sag_nivel-0.1pu_cap01.npz
  02_sag_nivel-0.1pu_cap02.npz
  ...
  02_sag_nivel-0.9pu_cap05.npz
  snr_30db/02_sag_nivel-0.1pu_cap01.npz
  metadata/02_sag.jsonl          <- continua 1 arquivo por classe, 1 linha por captura (já era assim)
```

O nome carrega o parâmetro físico relevante quando a classe tem um
(`nivel-<pu>`, `thd-<pct>`, etc.) — para classes sem parâmetro nomeável, só
`capNN`. A gravação continua atômica (`.part` → `os.replace`), por arquivo.

### 3. Cobertura de níveis/parâmetros (`set capturas N`)

**Classes com `NIVEIS` discretos** (02/SAG, 03/SWELL, 05/HARMONICS — 5
valores cada): com `set capturas N`, a bancada real faz N capturas de CADA
nível — N×5 arquivos. Resolvido inteiramente em
`ExperimentoBase.executar()`, sem tocar nos 3 scripts: o laço de captura
passa a rodar `niveis_count × N` iterações; cada iteração usa dois índices
diferentes — um **único**, monotônico, para seed/id/nome de arquivo (nunca
repete, garante capturas fisicamente distintas), e um **de nível**
(`0..niveis_count-1`, repetido N vezes, agrupado — todas as capturas do nível
0 antes de passar pro nível 1) passado como o `capture_index` que `gerar()`/
`configurar()` já usam internamente via `NIVEIS[capture_index %
len(NIVEIS)]`. Agrupado (não round-robin) porque trocar de nível físico tem
custo real na bancada (reprogramar TRACe custa ~1s/ciclo); passar 5x pelo
mesmo nível antes de trocar é o caminho mais barato. O dataset simulado
continua com a ordem/fórmula de hoje — este remapeamento só existe no ramo
`not simulated`.

**Classes com parâmetro contínuo, sem teto físico** (04/INTERRUPTION,
06/FLICKER, 09/OSCILLATORY_TRANSIENT-frequência, 19/DC_OFFSET): novo helper
compartilhado (`sinais.valor_para_captura(rng, lo, hi, capture_index,
total_capturas)`) substitui a chamada direta a `rng.uniform(lo, hi)` dentro
de cada `gerar()`. Com 1 captura (hoje, ou bench com N=1): sorteio, igual
hoje. Com N>1: `np.linspace(lo, hi, N)[capture_index]` — cobertura
determinística do intervalo, sem redundância. `gerar()` descobre `total` e
"estamos em bench real" pelo padrão já usado em `executar()`
(`self.osc is None` ⇒ simulado) e por `self.config.capturas(False)` — sem
mudar a assinatura de `gerar()`.

**08/TRANSIENT** (e qualquer classe futura com `limite_pico_bancada_pu()`
definido): com N>1, abandona a faixa da especificação (5-10pu, sempre
cortada pro mesmo teto físico em 127V — capturas extras seriam idênticas) e
usa `linspace` direto no **pico físico alvo**, de um valor modesto (1,2pu,
acima do normal mas sem esticar a fonte) até `limite_pico_bancada_pu()`. Com
N=1, comportamento inalterado (sorteio 5-10pu, depois cortado pelo hook
existente).

**20/INTERHARMONICS**: 3 parâmetros simultâneos (3 amplitudes + 3 fases) —
sem cobertura determinística limpa em 3 eixos. Fica com sorteio independente
por captura (seeds diferentes), N vezes.

`set capturas N` só afeta `REAL_CAPTURES_PER_CLASS` (via `Config`); zero
efeito em `SIM_CAPTURES_PER_CLASS`.

### 4. `set margin on|off`

Com `margin on` e bancada real, `executar()` passa a `osc.configure_acquisition()`
uma duração/nº de pontos maior que os 6000/200ms nominais (folga configurável,
default ~25ms de cada lado — a extensão exata é parâmetro de implementação,
calibrada pra cobrir com sobra o maior deslocamento já medido, ~20ms) e desloca
`pre_trigger_s` proporcionalmente pra também cobrir ANTES do instante nominal.
O array cru inteiro (maior que 6000 pontos) é salvo como está — sem recorte
automático — com metadados novos (`margem_amostras_antes`,
`margem_amostras_depois`, `amostras_totais`) no `.jsonl`. `_validar_captura()`
para de assumir shape fixo `(config.points,)` quando `margin_mode` está ativo.
`gerar()`/o dataset simulado nunca veem essa duração maior — só o caminho de
captura FÍSICA (`_capturar_real`) muda; a comparação com o "esperado" fica a
cargo do `analisar_sessao.py`, que já vai saber lidar com arrays maiores que
6000 pontos via os metadados de margem.

### 5. `set diagnostico on|off`

Reaproveita o fluxo `run`/`run all` já existente (mesma confirmação
`EXECUTAR-CLASSE-<NN>`/`EXECUTAR-20-CLASSES` — não abre um caminho de
energização novo, só adiciona leitura/log). Cada linha de log carrega
timestamp monotônico (`time.monotonic()`) para permitir reconstruir, depois,
quanto tempo realmente separa dois eventos.

**Pontos de log (todos condicionados a `diagnostico on`, zero mudança na
ordem/conteúdo das chamadas SCPI existentes):**

- Dentro de `arm()`/`arm_transient()`: antes/depois do `*WAI`, antes/depois
  do `INITiate:IMMediate`, ao entrar em `VOLTage:MODE LIST` — `STATus:
  OPERation:CONDition?` (bit 3 = TRANS), `OUTPut:STATe?`, `measure_voltage()`.
- **No fim de `wait_transient_complete()`**, no instante exato em que
  `TRIGger:STATe?` reporta `IDLE` (fim da classe atual): mesmo trio
  (TRANS/OUTPut/tensão). Sem isto não dá pra saber se `IDLE` já significa
  "transiente assentado de verdade" ou só "o registro mudou antes da saída
  estabilizar" — a pergunta central da hipótese do `*WAI`.
- **Logo antes do primeiro write de configuração da classe seguinte**
  (`trigger_step()`/`trigger_pulse()`/o início de `program_capture()`): mesmo
  trio de novo. Compara contra o ponto anterior — se o TRANS ainda está
  setado aqui, ou se a tensão ainda não voltou à base, é a causa raiz
  confirmada da race condition do `run all`.
- **Logo depois dos 4 writes de `trigger_step()`/`trigger_pulse()`, ANTES de
  `arm()` ser chamado**: um `check_errors()` isolado. Sem isto, se o `-113`
  intermitente aparecer, continua ambíguo se veio desses writes ou do
  `INITiate:IMMediate` dentro de `arm()` — exatamente a pergunta que o v1.7
  deixou em aberto ("terceiro comando diferente a mostrar sintoma
  parecido", nunca localizado com certeza).
- Mesmo tratamento (medir tensão antes/depois) em `enable_dc_offset()`, para
  testar se a troca `SOURce:MODE AC→ACDC` é a fonte do platô perto de 0V
  observado em `19/DC_OFFSET`, ou se é outra coisa.

Objetivo: confirmar ou refutar, com dado real, as três hipóteses abertas
(race condition residual do `*WAI`, comando exato por trás do `-113`
intermitente, e zeragem ao entrar em modo LIST/ACDC) numa única visita à
bancada — sem precisar voltar por falta de um ponto de log.

### 6. `logica/analisar_sessao.py` (novo, offline)

Recebe um caminho de pasta de sessão. Para cada `.npz`: lê o metadata
correspondente, reconstrói a forma esperada via `gerar()` + `seed` gravado
(mesma técnica usada manualmente nesta conversa), calcula cross-correlação/
deslocamento, razão de pico, e gera as imagens lado-a-lado (gerado vs.
capturado) — tudo em `<pasta_sessao>/analise/`. Lida com arquivos em `margin
mode` (mais de 6000 pontos) usando os metadados de margem para saber quanto
cortar/onde procurar o onset. Sem tocar hardware — mesmo padrão de
`visualizador.py`, testável offline.

## Tratamento de erros / casos de borda

- `set capturas 0` ou negativo: rejeitado com mensagem, mantém valor
  anterior (default 1).
- `set margin on` em modo simulado (`BENCH_MODE=0`): aceito sem erro, mas
  não tem efeito nenhum (só se aplica a `_capturar_real`) — avisar no
  `status`.
- Sessão sem nenhum `run`: nenhuma pasta `sessao_*` criada (lazy).
- `analisar_sessao.py` numa pasta sem `metadata/`: erro claro, não tenta
  adivinhar.

## Testes

Tudo que não depende de hardware físico entra em `tests/test_offline.py`
(modo simulado, mesma convenção dos 35 testes atuais):

- `sinais.valor_para_captura`: sorteio com N=1, linspace exato com N>1,
  bordas (N=2 cobre lo/hi exatamente).
- Remapeamento de índice em `executar()` para classes com `NIVEIS`: N=1 e
  N=3 produzem a sequência de níveis esperada (agrupada), sem alterar
  `SIM_CAPTURES_PER_CLASS`.
- `_salvar_classe()` grava um `.npz` por captura com o nome esperado
  (inclui nível/parâmetro quando aplicável).
- `margin_mode`: array salvo maior que `config.points`, metadados de margem
  presentes, dataset simulado inalterado.
- Sessão: pasta só criada na primeira gravação; dois `run` na mesma sessão
  de CLI gravam na mesma pasta.

O `diagnostico on` (log de estado real do instrumento) só pode ser validado
de fato na próxima sessão física — os testes offline cobrem só que o log não
quebra em modo simulado (não que os valores lidos fazem sentido).
