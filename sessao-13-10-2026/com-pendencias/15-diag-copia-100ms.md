## Análise do orquestrador

- Implementação completa? Sim: scripts/diag_ciclos_trace.py, scripts/diag_marcadores_trace.py (ENERGIZAR-MARCADORES, --probe obrigatório, recusa pico/rms acima dos limites e >250 TRACe), logica/modelo_lista_fonte.py, 12 testes; merge ok (suíte OK, 2 pulados).
- Pendências do usuário: rodar os scripts na bancada (comandos no relatório) — é o objetivo da spec; vai para o roteiro.
- Escopo limitado demais? Não.
- Resolve o contexto? Parcialmente: entrega as ferramentas; o mecanismo só se decide com dado da bancada.
- Critério de Parada: atendido.
- Classificação: com pendências (execução na bancada). Achado relevante: program_capture só AVISA quando o pico passa de max_peak_v (a recusa fica na pré-validação de mestre e no script novo).

---

# Relatório: ASD: Diagnóstico da Cópia do Evento em 100 ms (Classes 08 e 09)

Branch do worktree: `worktree-agent-a6abfc3eba55a2c78`. Commits: `6893cb5` (feat: modelo, dois scripts e testes) e `144a8fb` (docs: diagnostico.md, quirks.md, CHANGELOG/v1.15.md). Merge prévio de `claude/specs-v1-15-review-3w2bgl` feito (fast-forward, já traz a spec 11).

## Missão, item a item

**Item 1 — Escrever `scripts/diag_ciclos_trace.py` (offline, só leitura): para cada captura TRACE de uma sessão, comparar cada ciclo medido (alinhado em `inicio_janela`) com os ciclos programados k−1, k e k+1 e com o ciclo k da forma programada sem DC, e listar por captura qual ciclo programado explica melhor cada ciclo medido, a partir de que instante há troca e a amplitude do resíduo em 100 ms. Saída em texto/markdown legível e JSON.**
- Status: CUMPRIDO
- Explicação: `scripts/diag_ciclos_trace.py`. `carregar_sessao()` é a única função que conhece o formato em disco (lê `metadata/*.jsonl`, `tres_versoes/*.npz` quando existe e, senão, o `.npz` bruto recortado em `inicio_janela` mais `gerar_tres_versoes.reconstruir_versoes`); fica fácil de adaptar ao `.npz` por classe da spec 17. Só entram capturas cuja origem da programada é TRACe+LIST. `analisar_captura()` compara cada ciclo k com `k-1`, `k`, `k+1` e `k_sem_dc` (ciclo k da forma de bancada reconstruída, sem a média). Ciclos de senoide pura empatam, então um candidato diferente de k só vence se reduzir o resíduo rms em mais de `--margem-empate` (0,01 pu). Estados por ciclo: `ok`, `trocado`, `ok_sem_dc`, `sem_explicacao`. Por captura traz o primeiro ciclo trocado, quem o explica, o instante do ciclo, a primeira amostra divergente e o resíduo máximo em torno de `--instante-ms` (99,5 a 102 ms) e global. A saída é markdown no terminal e `.md`/`.json` em `--saida` (padrão `logs/`); a pasta da sessão não é escrita (teste `test_diag_ciclos_nao_escreve_na_pasta_da_sessao`). Evidência: teste `test_diag_ciclos_detecta_o_ciclo_trocado_e_o_instante`.

**Item 2 — Escrever `scripts/diag_marcadores_trace.py` (bancada): uma captura TRACE em que cada ciclo tem um marcador único (posição e amplitude diferentes por ciclo, tudo dentro dos limites de pico), a 50 e 60 Hz e na tensão base, que identifica na medida qual forma saiu em cada ciclo e mede o atraso; reaproveitar `program_capture`, o ORM do osciloscópio e as validações; confirmação digitada `ENERGIZAR-MARCADORES`; `--simulado` para testar o fluxo.**
- Status: CUMPRIDO
- Explicação: `scripts/diag_marcadores_trace.py`, variante `marcadores`: senoide de 1 pu mais, em cada ciclo k, uma lombada de cosseno elevado (24 amostras) com posição (permutação fixa) e amplitude (0,08 a 0,45 pu, crescente com k) únicas. A identificação usa (posição no ciclo, amplitude): `k tocado`, deslocamento em ciclos e atraso em amostras. Usa `AmetekMX30.program_capture`, `KeysightDSOX4034A` com a sequência de `mestre._capturar_real` (margem 20/50 ms, janela por `indice_trigger`), `configure_safe_baseline` e `safe_shutdown` no `finally`. Segurança: `ENERGIZAR-MARCADORES` (case-sensitive), `--probe` sem padrão, sem `BENCH_MODE=1` só `--simulado`, e pré-validação ANTES de energizar do pico reconstruído e do rms de passo contra `max_peak_v` 415,8 e `max_voltage_rms` 300 (porque `program_capture` só avisa); amplitude reduzida para caber em 90 % do teto e recusa se sobrar menos de 0,15 pu; teto de 250 gravações de TRACe por rodada (A3: ~280). Nenhuma consulta à fonte além das que `arm_transient` já faz. A 127 V o pico reconstruído é ~241 V. `--simulado` usa fonte e osciloscópio FICTÍCIOS que tocam o mecanismo de `--simular`; a fonte simulada não responde ao readback de `arm_transient`, então nesse modo `arm_transient`/`trigger`/`wait_transient_complete` viram no-op (só no script, só em `--simulado`). Evidência: testes `test_marcadores_simulado_*` (marcador de cada ciclo recuperado, troca de passo +1 a 100 ms: ciclo 5 a 50 Hz, ciclo 6 a 60 Hz, atraso global de 3 amostras recuperado).

**Item 3 — Acrescentar ao script do item 2 a variante com o evento na fronteira e a variante com o evento a meio ciclo (os dois casos de 07/10), para separar "ponto 0" de "instante fixo".**
- Status: CUMPRIDO
- Explicação: variantes `fronteira` (impulso de 4 amostras no ponto 0 do ciclo) e `meio_ciclo` (n/2), cada uma em dois instantes (`--instantes-evento-ms`, padrão 40 e 80 ms; ciclo = primeiro que começa nele ou depois: 50 Hz ciclos 2 e 4, 60 Hz ciclos 3 e 5). Se a cópia cair em 100 ms nos dois instantes, é instante fixo; se acompanhar o evento (+1 ciclo), é troca de passo. Por padrão, 10 capturas e 110 gravações de TRACe. Nota: "meio ciclo" é n/2, não a amostra 400/500 do caso real da 09 a 60 Hz; o caso de 07/10 a 60 Hz (80 ms = amostra 400 do ciclo 4) não é reproduzido exatamente, mas o instante 80 ms e o meio do ciclo são cobertos separadamente. Evidência: `test_marcadores_simulado_atraso_global_em_amostras_e_variantes_de_evento`.

**Item 4 — Escrever um modelo preditivo provisório (função pura) que, dada a programação e uma hipótese de mecanismo, devolve a forma que a fonte emitiria; deixar as hipóteses candidatas parametrizadas, para serem confrontadas com o resultado do item 2 na bancada.**
- Status: CUMPRIDO
- Explicação: `logica/modelo_lista_fonte.py`. `prever_forma(programacao, mecanismo, **params)` (função pura sobre `ProgramacaoCaptura`) com os mecanismos `ideal` (reproduz `programada_pu()` exatamente, testado a 50 e 60 Hz), `atraso_de_passos` (`d`, `t_inicio_s`, `tensao`), `transicao_forma_anterior` (`amostras`, `t_inicio_s`), `copia_no_instante` (`t_s`, `ciclo_origem`, `inicio_na_origem`, `n_amostras`, `ganho`, `modo`) e `deslocamento_no_tempo` (`t_inicio_s`, `atraso_s`). `HIPOTESES_CANDIDATAS` (dicionário nome -> mecanismo + parâmetros) e `confrontar()` ordenam por rms do resíduo; o script do item 2 já grava esse ranking por captura. Não toca `montar_programacao`. Os valores numéricos são chutes dos sintomas, não medidas.

**Item 5 — Documentar uso e leitura dos resultados em `docs/diagnostico.md` e o comportamento observado em `docs/quirks.md` (como NÃO VERIFICADO até a bancada); registrar em `CHANGELOG/v1.15.md` (seção nova no fim).**
- Status: CUMPRIDO
- Explicação: `docs/diagnostico.md` ganhou duas linhas na tabela §3 e a nova §3.1 (leitura de cada coluna, como distinguir instante fixo de troca de passo, o modelo e o `--simulado`); `docs/quirks.md` ganhou A25 (impulso espúrio em 100 ms da 09, mecanismo NÃO VERIFICADO, candidatas listadas); `CHANGELOG/v1.15.md` ganhou a seção "Diagnóstico da cópia do evento em 100 ms" no fim, com Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO. Fatos conferidos no código (`ametek_orm.py`, `mestre.py`); os sintomas de 07/10 vêm dos relatórios em `arquivo/analises` e da própria spec.

## Critério de Parada
Atendido.
- Os dois scripts existem (`scripts/diag_ciclos_trace.py`, `scripts/diag_marcadores_trace.py`).
- Sessão sintética com o impulso do ciclo 4 saindo no ciclo 5: o item 1 acusa os ciclos 4 e 5 trocados, explicados por `k-1`, instante 80 ms, primeira amostra divergente 2400 e resíduo ≥ 0,5 pu em ~100 ms.
- `diag_marcadores_trace.py --simulado` termina (código 0) e recupera os marcadores: `[o["k"]...] == range(n)` com `ideal`; com `atraso_de_passos:d=1,t_inicio_s=0.1` recupera `k = ciclo - 1` a partir de 100 ms.
- Suíte: `TMPDIR=/tmp/claude-0/tmpt /tmp/claude-0/venv/bin/python -m unittest tests.test_offline` deu 413 testes, 4 falhas (exatamente as 4 conhecidas de fixture byte a byte); `DiagnosticoCopiaEm100msTests` (12 testes) passa.

### Comandos exatos para o roteiro (PowerShell, PC da bancada, na raiz `C:\Users\denis\TCC\code`)

Item 1 (offline, nas sessões de 07/10; feche nada, não energiza):

```powershell
cd C:\Users\denis\TCC\code
env\Scripts\python.exe scripts\diag_ciclos_trace.py resultados\sessao_2026-10-07_127V_50Hz --classes 08,09
env\Scripts\python.exe scripts\diag_ciclos_trace.py resultados\sessao_2026-10-07_14-59-54_run02 --classes 08,09
```

Saída em `logs\diag_ciclos_trace-<sessao>.md` e `.json`. (`--sem-forma-bancada` dispensa o candidato `k_sem_dc`.)

Item 2/3 (bancada; fechar a CLI antes; escrever o fator ESCRITO na probe em `--probe`; digitar `ENERGIZAR-MARCADORES`):

```powershell
cd C:\Users\denis\TCC\code
$env:BENCH_MODE = "1"
env\Scripts\python.exe scripts\diag_marcadores_trace.py --probe 500 --vrms 127
```

(substituir 500 pelo fator real. Completo: 50 e 60 Hz, as três variantes, 10 capturas, 110 gravações de TRACe, ~3 a 5 min sem contar a definição das TRACEs na Flash, ~3 s cada nas primeiras 12.) Para dividir em duas rodadas: `--frequencias 50` e depois `--frequencias 60`. Para só o par ponto 0 / meio ciclo: `--variantes fronteira,meio_ciclo`. Teste sem hardware: `env\Scripts\python.exe scripts\diag_marcadores_trace.py --simulado --probe 500 --vrms 127 --simular "atraso_de_passos:d=1,t_inicio_s=0.1"`.

## Pendências que exigem o usuário
- Rodar os dois scripts no PC da bancada (as sessões de 07/10 e o hardware só existem lá) e devolver `logs\diag_ciclos_trace-*.md/.json` e `logs\diag_marcadores_trace-*.md/.json/.log/-scpi.log` para confrontar as hipóteses.
- Informar o fator EXATO da probe de tensão e digitar `ENERGIZAR-MARCADORES` (não automatizado).
- Aprovar o commit e a pasta: nada foi enviado por push.

## Limitações de escopo
- Sem hardware e sem as sessões de 07/10 (só no PC da bancada), nenhuma hipótese foi confrontada com dado real, nem o caminho do `.npz` bruto + `reconstruir_versoes` do `carregar_sessao()` foi exercitado em teste (só o caminho `tres_versoes/`).
- `montar_programacao` e `gerar()` não podiam ser mudados; a 08 e o evento real da 09 a 60 Hz (amostra 400/500, impulso de 2 amostras a 1,3 pu na 08) não são reproduzidos exatamente pelas variantes (impulso de 4 amostras a ~0,45 pu para caber no pico; meio ciclo = n/2).
- O formato em disco vai mudar (spec pri 17): só `carregar_sessao()` precisará de ajuste.

## A missão resolve o contexto?
Parcialmente: entrega as ferramentas para separar "ponto 0 do ciclo" de "instante fixo" e para confrontar hipóteses, mas o mecanismo só se resolve com os dados da bancada.

## Achados
- (informativo) Pedido: a abordagem pedida está adequada; uma alternativa mais barata seria rodar primeiro só o item 1 nas sessões de 07/10 (sem energizar) e só depois o item 2, o que o roteiro já permite.
- (média) `program_capture` só AVISA quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga", `ametek_orm.py` ~1425-1431 e ~1480-1486); por isso o script novo recusa antes de energizar. Fora do escopo desta spec, mas vale rever se a recusa não deveria viver no ORM (os limites inegociáveis proíbem enfraquecer, não proíbem endurecer).
- (baixa) A fonte simulada do ORM não passa em `arm_transient` (`TRIGger:SOURce?` devolve "0"): o `--simulado` do script novo precisa neutralizar `arm_transient/trigger/wait_transient_complete`. Isso significa que o caminho completo de `arm_transient` não é exercitado em simulação por nenhum script de diagnóstico.
- (baixa) `modelo_lista_fonte._copia_no_instante` com `modo="somar"` soma a forma inteira do ciclo de origem (inclui a senoide) por padrão; para modelar "só o evento", passe `n_amostras` curto e `inicio_na_origem` no evento. Os padrões são chutes, não calibrados.
- NÃO VERIFICADO: largura de banda da fonte pode achatar a lombada de 24 amostras ou o impulso de 4 amostras, e os limiares de identificação (12 amostras de posição, 25 % de amplitude) não foram calibrados em hardware. Se a série de 110 gravações cabe numa conexão sem a trava de A3: contagem abaixo da referência de 280, mas a causa da trava é desconhecida.
- NÃO VERIFICADO: a verdadeira causa do impulso em 100 ms (A22/A25); nenhuma das cinco hipóteses do modelo foi confirmada.
- Ruído de teste: `main()` do script de marcadores, chamado da suíte, deixa a linha "[INFO] Definindo TRACE" na saída do teste (do handler raiz que outro módulo da suíte instala); inofensivo. O script restaura os handlers/níveis do logging no `finally`.
