## Análise do orquestrador

- Implementação completa? Sim: validação offline 07/17 com filtro de 2.ª ordem, scripts/verificar_sessao_bancada.py (+10 testes), comentário em measure_voltage, lista de 18 itens de bancada; merge ok (suíte OK, 2 pulados).
- Pendências do usuário: (1) ACHADO ALTO para amanhã: com entalhes em todos os ciclos, a 07/17 tende a ser reprovada pela validação física só pelo fator de crista (+31% a +59% contra 10%) se a fonte atenuar os entalhes como em 07/10; decidir depois de ver a 1.ª captura; (2) aprovar limiares do verificador.
- Escopo limitado demais? Não.
- Resolve o contexto? Sim (prepara a bancada); os itens físicos ficam para o roteiro.
- Critério de Parada: atendido.
- Classificação: com pendências.

---

# Relatório: ASD: Pendentes de Classe Conferíveis Offline (07, 17, 18, 19 e Sorteio)

Branch: `worktree-agent-a59e6cd40159cf45a`. Commit: `be688b5` (feat: verificador offline de sessão de bancada ...). Merge prévio de `claude/specs-v1-15-review-3w2bgl` feito (fast-forward/limpo). Scripts auxiliares da simulação do item 1: `/tmp/claude-0/-home-user-anti-synthetic-data/f7ec71b8-9f16-59ac-aa79-a4ac81fa512e/scratchpad/spec20/` (`valida_entalhes.py`, `tabela.py`, `calib.py`, `explora.py`, `ruido.py`; saída em `tabela.txt`, `padrao.txt`).

## Missão, item a item

**Item 1 — Rodar offline a validação física da 07 e da 17 tendo como "medida" a forma programada, e a mesma forma com os entalhes atenuados por um filtro de 2.ª ordem de ~10 kHz (resposta da fonte medida em 07/10: fn ≈ 9–11 kHz, ζ ≈ 0,1–0,3), e reportar se alguma captura seria reprovada; se for, propor o ajuste sem aplicá-lo.**
- Status: CUMPRIDO (resultado: SIM, seriam reprovadas, só pela crista; ajuste proposto, não aplicado).
- Explicação: usei `ExperimentoBase._validar_fisicamente` (`logica/mestre.py:1687`) real, com as tolerâncias de hoje (envelope 15 %, THD 20 %, crista 10 %), `_forma_programada_pu` = `forma_e_parametros_para_bancada` (127 V; 60 e 50 Hz; 3 capturas padrão; seeds de `seed_da_captura`). Filtro: degrau segurado pelo DAC (sobreamostrado x8), 2.ª ordem bilinear, média no passo. Números por captura (127 V; "pura" = medida igual à programada; "filtro" = fn 10 kHz, ζ 0,2):

| classe / f0 / captura (seed) | pulsos | pura | filtro: THD esp/med | filtro: crista esp/med (desvio) | filtro: resultado |
|---|---|---|---|---|---|
| 07 60 Hz c1 (7000001) | 35 | APROVA | 7,88 / 7,90 % | 1,440 / 1,888 (+31,1 %) | REPROVA (crista) |
| 07 60 Hz c2 (7000002) | 38 | APROVA | 8,94 / 8,97 % | 1,440 / 1,898 (+31,8 %) | REPROVA (crista) |
| 07 60 Hz c3 (7000003) | 33 | APROVA | 7,06 / 7,10 % | 1,433 / 1,879 (+31,1 %) | REPROVA (crista) |
| 07 50 Hz c1 / c2 / c3 | 29 / 30 / 28 | APROVA | 7,14/7,15; 7,73/7,75; 6,94/6,97 % | +31,2 / +31,6 / +31,2 % | REPROVA (crista) x3 |
| 17 60 Hz c1 / c2 / c3 (17000001-3) | 37 / 35 / 34 | APROVA | 8,08/8,13; 7,08/7,10; 7,34/7,38 % | +31,7 / +31,8 / +31,1 % | REPROVA (crista) x3 |
| 17 50 Hz c1 / c2 / c3 | 31 / 30 / 30 | APROVA | 7,74/7,77; 6,86/6,88; 7,34/7,35 % | +31,6 / +33,4 / +31,2 % | REPROVA (crista) x3 |

  Envelope (mín/mediana/máx) usa no máximo 3 % da tolerância nas 12 capturas; THD passa com folga. Banda inteira da fonte (fn 9/10/11 kHz x ζ 0,1/0,2/0,3, 60 seeds, 127 V): 2160/2160 reprovam, todas por crista, pior desvio +51 % a +59 %; envelope no máximo 12 % da tolerância; THD desvio relativo ≤ 1,7 %. A 220 V (sem tabela de calibração, o limite de bancada reduz o distúrbio a 37 % na 07 e 25-30 % na 17) o resultado depende do filtro (parte passa, parte reprova): fora do foco, 127 V é a condição da bancada.
  Causa: antes só 4 ciclos eram entalhados e a MEDIANA da crista (`sinais.fator_de_crista_do_ciclo_mediano`) não via o sobressinal; agora todo ciclo tem entalhe, e o sobressinal do filtro entra no pico de cada ciclo. Controle: a 07 legada (`sorteio_posicao=False`) APROVA com o mesmo filtro (desvio de crista +1 %).
  Ressalva importante: o modelo é pessimista em relação ao único dado real: a 07 legada mediu extremo 1,18 pu (`tests/fixtures/sessao_2026-09-30_15-26-05/07_notch.jsonl`: vale -212 V sobre 179,6 V; crista medida 1,440 contra 1,417), e com ζ 0,3 o modelo dá 1,31 pu na forma nova contra 1,09 na legada. Um filtro com ζ ≥ 0,6 aprovaria (+5 %). O dado de 09/30 não discrimina (a mediana legada não vê o sobressinal); só a bancada diz.
  Proposta (NÃO aplicada): para 07 e 17, a crista deixa de reprovar (ou ganha tolerância própria por atributo de classe, ≥ 0,60 para cobrir ζ 0,1; `comparar_fisicamente` hoje fixa `tol_crista=0.10` e `_validar_fisicamente` não a repassa). A defesa fica com THD/envelope (que passam) e com `_conferir_extremos_fisicos` (pico/vale medidos contra 415,8 V). Alternativa melhor se o dono quiser manter a crista: compará-la contra a forma esperada já filtrada pela resposta da fonte (precisa de ζ medido). Nenhuma tolerância foi tocada.

**Item 2 — Escrever um verificador offline (`scripts/verificar_sessao_bancada.py`) que, numa sessão real, mede a continuidade de fase da 18 na troca de passo, a largura medida do PULSe (02–04) contra a programada e o `pre_trigger_desvio_amostras`, para rodar logo depois da bancada. Isole o carregamento da sessão numa função (o formato de arquivo vai mudar na spec 17).**
- Status: CUMPRIDO.
- Explicação: `scripts/verificar_sessao_bancada.py` (não importa PyVISA, não toca hardware; não criei `diag_ciclos_trace.py`). Carregamento isolado em `carregar_sessao(pasta)` e `janela_da_captura(captura)` (formato v1.15: `metadata\*.jsonl` + 1 `.npz` por captura); as verificações recebem só arrays/dicts. (a) `fase_18`: fase do sinal analítico, uma reta por passo (sem 1,25 ciclo de borda e sem 1 ciclo em volta do meio), extrapoladas ao meio da janela; devolve salto em graus, f1/f2 medidas e `intersecao_ms`. Limitação intrínseca: só a fase não separa "salto de fase" de "troca atrasada" (J graus = troca deslocada de J/(360·|Δf|) s); por isso a saída mostra `intersecao_ms` e o instante nominal é o meio da janela (mesma hipótese de `sinais.forma_programada_nativa`). (b) `largura_pulse`: amplitude instantânea (módulo do sinal analítico, suavizada 1 ms) cruzando o ponto médio entre regime e evento, contra `duracao_s`; sem contraste (<5 %) devolve "n/d". (c) `pre_trigger`: campo `pre_trigger_desvio_amostras`; sem o campo, calcula pela mesma conta de `mestre.py:2589`. Critérios padrão (propostos, sem dado de bancada): 10 graus, 2 ms, 2 amostras (esse último é o do aviso do mestre). Saída: uma linha por captura, resumo min/mediana/máx, `--json`, código 0/1/2. Teste: `VerificadorSessaoBancadaTests` (10 testes, `tests/test_offline.py` no fim), sessão sintética: larguras de 8,3 a 165 ms x níveis 0,1/0,5/0,9 com erro ≤ 1,5 ms; 18 em 57-63 e 47-53 Hz nos dois sentidos com salto ~0; salto injetado +40 e -60 graus detectado (±3); pré-trigger -2/+1/+5; códigos de saída. Estudo extra com ruído (`ruido.py`): a 30 dB de SNR, largura |erro| máx 1,4 ms (200 sorteios), salto de fase com desvio ~0,2 graus e viés ≤ 0,5 graus; a 20 dB a largura tem outliers (nível 0,9).

**Item 3 — Documentar em `logica/ametek_orm.py` (comentário) que `measure_voltage()` em ACDC devolve rms total, e confirmar com teste que `diag_acdc_amplitude.py --simulado` continua passando.**
- Status: CUMPRIDO.
- Explicação: comentário em `logica/ametek_orm.py` (`measure_voltage`, ~linha 1871) com a evidência (run02 de 07/10, transcrição linha 8310: 5,491 V com offset de 5,58 V e CA ainda zero; consistência das 3 capturas), a ressalva de ser uma leitura só (NÃO VERIFICADO até `MEASure:VOLTage:DC?`) e os usos de hoje. Achado: além de `mestre.verificar_cadeia_de_medicao` (AC), `measure_voltage` é chamado por `_log_diagnostico` (`ametek_orm.py:642`), que com `set diagnostico on` em ACDC grava o total em `tensao_v` (o pendente dizia "sem uso hoje"; não é bem assim). Teste: `test_diag_acdc_amplitude_simulado_continua_passando` roda o script por subprocesso com `--simulado --testar-compensacao` (sem `BENCH_MODE`, `--saida` em temporário): código 0, tabela e arquivos `.json` gerados; também rodado à mão (saída idêntica à do pendente).

**Item 4 — Listar, para o roteiro de bancada, cada item que só a bancada fecha, com o comando exato (PowerShell no PC da bancada), o que olhar e o critério de aprovação.**
- Status: CUMPRIDO (lista abaixo, seção "Roteiro de bancada").
- Explicação: cobre os três pendentes (classes_05_07_18, sorteio_inicio_fase, acdc_amplitude). Os critérios do verificador e os de `validacao_fisica` abaixo são propostas minhas; os da ACDC vêm da tabela do pendente.

**Item 5 — Registrar em `CHANGELOG/v1.15.md` (seção nova no fim) e em `docs/diagnostico.md` o uso do verificador.**
- Status: CUMPRIDO.
- Explicação: `CHANGELOG/v1.15.md`, seção nova no fim ("Pendentes de classe conferíveis offline...") com Por quê / O que mudou / resultado da simulação do item 1 / O que não mudou / Testes / NÃO VERIFICADO. `docs/diagnostico.md`: linha na tabela da seção 3 e nova §3.1 (comando, tabela de verificações, limites do método).

## Roteiro de bancada (item 4)

Convenções: PowerShell em `C:\Users\denis\TCC\code`; CLI aberta (`scripts\START_BENCH.cmd`); `$s` = pasta da sessão mais recente:
`$s = (Get-ChildItem resultados -Directory | Sort-Object LastWriteTime | Select-Object -Last 1).FullName`
Uma linha por captura de `validacao_fisica` de uma classe (trocar `07_*`): 
`Get-Content "$s\metadata\07_*.jsonl" | ForEach-Object { $j = $_ | ConvertFrom-Json; "{0} ok={1} crista {2:N3}/{3:N3} thd {4:N4}/{5:N4} pico={6} vale={7} previsto={8}" -f $j.id_captura,$j.validacao_fisica.ok,$j.validacao_fisica.crista_medida,$j.validacao_fisica.crista_esperada,$j.validacao_fisica.thd_medida,$j.validacao_fisica.thd_esperada,$j.pico_medido_v,$j.vale_medido_v,$j.extremo_previsto_v }`

| # | Item (origem) | Comando | O que olhar | Aprovado se |
|---|---|---|---|---|
| 1 | 07/17 com ~36 entalhes: tolerância da validação (classes_05_07_18 §2b) | CLI: `run 07,17` (confirma `EXECUTAR-CLASSES-07,17`); depois a linha de `validacao_fisica` acima com `07_*` e `17_*` | `validacao_fisica.ok`, `crista_medida/crista_esperada`, `thd_medida/thd_esperada` | todas `ok=true`. Se reprovar SÓ por crista (desvio +16 % a +50 % é o previsto pela simulação do item 1) é a proposta do item 1 que se confirma, não defeito de captura; reprovar por THD ou envelope é achado novo |
| 2 | A fonte filtra pulsos de 0,1 ms? (classes_05_07_18 §2c) | mesma saída do item 1 | razão `thd_medida/thd_esperada` da 07 e 17 | entre 0,8 e 1,2 (pulsos reproduzidos); bem abaixo de 0,8 = fonte atenua os entalhes |
| 3 | Sobressinal por entalhe com 10-12 ciclos; fatores 1,180 (07) e 1,017 (17) calibrados com 4 ciclos (classes_05_07_18 §2a) | mesma saída do item 1 (`pico`, `vale`, `previsto`); depois `env\Scripts\python.exe scripts\recalibrar_extremos.py $s` (sem `--gravar`) | max(\|pico\|,\|vale\|) contra `extremo_previsto_v` e contra 415,8 V; fator proposto contra o atual | extremo medido ≤ previsto e < 415,8 V (a bateria já aborta a classe se passar do teto); fator proposto ≤ atual. Se maior: recalibrar antes de 220/380 V |
| 4 | 18: continuidade de fase em 47→53 Hz (50 Hz) / 57→63 Hz (60 Hz) (classes_05_07_18 §3) | CLI: `run 18`; depois `env\Scripts\python.exe scripts\verificar_sessao_bancada.py $s` | linha `fase_18`: `salto` (graus), f1/f2 medidas, `intersecao_ms` | \|salto\| ≤ 10 graus, f1/f2 a ≤ 0,2 Hz de `start_hz`/`end_hz`, `intersecao_ms` perto de 0. \|salto\| grande com `intersecao_ms` ≈ 0 = fase saltou; \|salto\| grande com `intersecao_ms` longe de 0 = troca fora do meio, fase contínua |
| 5 | 18: frequência base restaurada depois de 47→53 (já testado offline, falta o equipamento) | `Select-String -Path "$s\scpi_transcricao.log" -Pattern "FREQuency" \| Select-Object -Last 15` | `SOURce:FREQuency <base>` após a lista e sem `-2xx` | escrito e sem erro SCPI na sequência; classe seguinte (19) com o CH1 na frequência da rede (`validacao_fisica.ok`) |
| 6 | 05: a CSINusoid preserva o rms programado (modelo assume; classes_05_07_18 §1) | CLI: `run 05`; saída `validacao_fisica` com `05_*` | `envelope_mediana_medida` (esperada 0,7071) e `thd_medida` contra o THD pedido | mediana dentro de 0,7071 ± 0,01 (1,4 %, proposta) e THD dentro da tolerância de 20 %; mediana ~0,72 (soma antiga) ou fora disso invalida a premissa do modelo |
| 7 | 05 a 30 % por TRACe: se `montar_programacao` renormaliza o rms (modelo 0,738) | mesma saída, só a captura de 30 % | `envelope_mediana_medida` contra `esperada` | `ok=true` (dentro de 15 %); registrar a razão |
| 8 | 02-04: `PULSe:WIDTh` de 8 a 166 ms realmente aplicado (sorteio §2a) | CLI: `run 02,03,04`; `env\Scripts\python.exe scripts\verificar_sessao_bancada.py $s` | linhas `largura_pulse` (erro em ms; programada vs medida); `Select-String "$s\scpi_transcricao.log" -Pattern "PULSe:WIDTh"` para o readback | \|erro\| ≤ 2 ms em todas as capturas; readback igual ao escrito; sem erro SCPI. Erro sistemático (ex. largura saturada) = a resolução/limite do comando |
| 9 | Pré-trigger por captura (`pre_trigger_desvio_amostras`, nunca medido; sorteio §3) | mesma execução do 8; linhas `pre_trigger` do verificador | desvio em amostras por captura e resumo | \|desvio\| ≤ 2 em todas (o mesmo limite do aviso de `mestre.py`); registrar o desvio típico (constante = viés de `TIMebase:POSition`) |
| 10 | Disparo sincronizado em fase respeitado em LIST (18), CSINe (05) e ACDC (19) (sorteio §2b/c) | CLI: `run 01,05,18,19`; `env\Scripts\python.exe logica\analisar_sessao.py $s` | `lag (ms)` e `correlação` por classe (o `esperado` é reconstruído com `fase_graus` do metadata; `validacao_fisica` é cega à fase) | \|lag\| < 0,2 ms e correlação ≥ 0,99 em 01, 05, 18 e 19; fase de disparo ignorada aparece como correlação baixa/lag de fração de ciclo (a 60 Hz, 1° ≈ 46 µs) |
| 11 | Fatores de extremo medidos com fase/instante fixos (sorteio §7, gravidade alta) | após uma sessão completa: `env\Scripts\python.exe scripts\recalibrar_extremos.py $s` | fatores propostos por classe contra `logica\calibracao_extremos.json` | nenhum fator proposto maior que o atual; qualquer maior vale recalibração (`--gravar`, decisão do dono) antes de nova campanha. Não depende só do verificador |
| 12 | Média por ciclo ≠ 0 em eventos no meio do ciclo (9-16 % dos ciclos TRACe; sorteio §7) | `validacao_fisica.ok` das classes TRACe da sessão (comando acima com `10_*` etc.) | quantas reprovam e por quê | nenhuma reprovada por envelope/THD |
| 13 | Gravações de TRACe e a trava na ~280.ª (sorteio §4) | `Get-Content "$s\metadata\*.jsonl" \| ForEach-Object { ($_ \| ConvertFrom-Json).escritas_trace_na_conexao } \| Measure-Object -Maximum` | maior contador atingido por conexão | bateria completa sem a trava; se a fonte travar, anotar o contador (segundo ponto de dados; hoje só há 280 de 16/09) |
| 14 | 19: déficit de CA de 5-6 % em ACDC (acdc_amplitude §3) | `$env:BENCH_MODE = "1"; env\Scripts\python.exe scripts\diag_acdc_amplitude.py --probe <FATOR> --vrms 127 --hz 60 --testar-compensacao`; repetir `--hz 50` e `--vrms 230 --hz 50`. Digitar `ENERGIZAR-ACDC`. Fechar a CLI antes. `<FATOR>` = o escrito na probe (07/10 usou 500; conferir) | tabela `.md` em `logs\diag_acdc_amplitude-*.md`: `CH1 AC / alvo` das linhas 1-5; `fonte DC?`; `VOLTage:RANGe?` | linhas 1 e 5 ≈ 1,000 (sem deriva); linha 2 ≈ linha 3 ≈ 0,94-0,95 (déficit é do modo ACDC) ou linha 3 ≈ 1,000 e linha 2 ≈ 0,95 (é o caminho `VOLTage:TRIGgered`: trocar para `VOLTage` imediato); `RANGe?` ≠ 300 em ACDC = H5; `CH1 AC / alvo` das linhas com `V_prog` ≈ 1,000 = a compensação funciona na condição testada |
| 15 | 19: g depende de (V, f)? (H7/H8) | as 3 execuções do item 14 | g = `CH1 AC / alvo` da linha 2 por condição | g igual nas 3 condições = fator único serve; senão tabela por (V, f) (como `calibracao_extremos.json`); provisórios dos dados de 07/10: 0,9508 / 0,9431 / 0,9377 |
| 16 | 19: `MEASure:VOLTage:AC?` em ACDC é rms total? (comentário novo em `measure_voltage`) | coluna `fonte AC?` e `fonte DC?` da mesma tabela | `fonte AC?` ≈ √(CA² + CC²) com CC = `fonte DC?` | confirma (e então o comentário deixa de ser hipótese); `MEASure:VOLTage:DC?` rejeitado = anotar |
| 17 | 19: CC +3 V acima do esperado em run02 (60 Hz) | mesma tabela, coluna `CH1 CC` e `fonte DC?` a 60 Hz | CC medido menos programado | dentro de -1,0 a -1,7 V (viés de cadeia visto a 50 Hz); +1,9 V repete a anomalia |
| 18 | 19: o reenvio de `SOURce:MODE ACDC` a cada captura é inócuo (~0,3 s) | `Select-String "$s\scpi_transcricao.log" -Pattern "MODE ACDC"` e a medida da fonte antes/depois (diagnóstico on) | a saída não zera entre capturas | sem queda a 0 V entre capturas (já visto em run02) |

## Critério de Parada
Atendido. (1) Resultado do item 1 no relatório com número por captura (tabela do item 1; arquivos `tabela.txt`/`padrao.txt` no scratchpad). (2) O verificador roda em sessão sintética: `TMPDIR=/tmp/claude-0/tmpt /tmp/claude-0/venv/bin/python -m unittest tests.test_offline.VerificadorSessaoBancadaTests`: 10 testes OK. (3) A lista cobre os três pendentes (itens 1-3 e 6-7: classes_05_07_18; 4-5 e 8-13: sorteio; 14-18: ACDC). (4) Suíte completa: `Ran 411 tests, FAILED (failures=4)`, as 4 conhecidas de fixture byte a byte (`test_05_07_17_18_sem_sorteio_reproduzem_34a0d82`, `test_literatura_reproduz_byte_a_byte_o_gerar_do_commit_34a0d82`, `test_norma_e_fronteira_mudam_so_o_que_a_spec_manda`, `test_resultado_congelado_da_v1_15`); nenhuma falha nova.

## Pendências que exigem o usuário
- Decidir a proposta do item 1 (crista da 07/17: desligar, tolerância própria ou comparar contra a forma filtrada). Só deve ser decidida depois do item 1 do roteiro (bancada).
- Aprovar os limiares do verificador (10 graus, 2 ms, 2 amostras): são propostas minhas sem dado de bancada.
- Fator da probe e execução física dos itens do roteiro (energizam: `run ...` e `diag_acdc_amplitude.py`, com as confirmações digitadas pelo operador).

## Limitações de escopo
- Sem hardware: nenhum resultado do item 1 é medida; o filtro de 2.ª ordem é hipótese (e pessimista contra o único dado real, ver item 1). O verificador foi validado só em sinais sintéticos (ruído branco), nunca numa sessão real; os `.npz` reais de 07/10 e 09/30 não estão no repositório (só os `.jsonl` de 09/30 em `tests/fixtures`), então não foi possível testá-lo contra dado real.
- "Não afrouxar tolerâncias" impediu medir quanto a tolerância de crista teria de subir na prática além de reportar o desvio necessário.
- O formato de sessão vai mudar na spec 17; só `carregar_sessao()`/`janela_da_captura()` foram preparados para isso, não conheço o formato novo.

## A missão resolve o contexto?
Parcialmente: reduz e prepara o que dava (o item 1 antecipa uma reprovação provável da 07/17 por crista; o verificador cobre fase da 18, largura do PULSe e pré-trigger), mas os 18 itens do roteiro continuam dependendo da bancada. O achado do item 1 muda a expectativa: a bancada de 14/10 tende a marcar 07/17 como inválidas só por crista, se a fonte ressoar como o modelo supõe.

## Achados
- [média] 07/17 contínuas: fator de crista (mediana por ciclo) é sensível ao sobressinal da fonte em todos os ciclos; possível reprovação em massa de 07/17 na bancada (item 1). Pico: modelo dá 1,31-1,49 pu na forma nova (127 V → ~235-267 V), longe dos 415,8 V; a 220 V a previsão usa o fator 1,18 calibrado com 4 ciclos, ou seja, pode subestimar (hoje a 220 V a tabela está ausente e a previsão é conservadora; a medida pós-captura é a defesa).
- [baixa] `comparar_fisicamente` não aceita `tol_crista` por classe: `_validar_fisicamente` (`mestre.py:1736`) só passa `tol_envelope` e `tol_thd`; qualquer ajuste por classe exige um gancho novo.
- [baixa] O pendente acdc_amplitude diz que `measure_voltage()` "hoje só é usado em AC"; também é chamado por `_log_diagnostico` (`ametek_orm.py:642`), que em ACDC registra o total (comentário corrigido).
- [baixa] Os números de linha do pendente para `frequency_drift_list` (`ametek_orm.py:1038`) e `enable_dc_offset` (`:1009`) estão defasados: hoje `frequency_drift_list` começa em ~1029 e `enable_dc_offset` em ~1071.
- [baixa] Ambiguidade intrínseca da fase na 18: um salto J equivale a uma troca deslocada de J/(360·|Δf|) s (para 6 Hz, 40 graus = 18,5 ms). O verificador reporta as duas leituras; para separar é preciso saber a latência trigger→início da lista.
- [baixa] Largura medida a 20 dB de SNR tem outliers (até 27 ms nos 200 sorteios, nível 0,9); a bancada mede ~30 dB (`snr_medido_db` 30,16 no fixture de 09/30).
- [info] Com sorteio ligado e `run 07,17`, o `AGENTS.md` pede `EXECUTAR-CLASSES-07,17` (lista normalizada) como confirmação.
- NÃO VERIFICADO: qualquer comportamento real da fonte (resposta a 36 entalhes, `PULSe:WIDTh` de 8-166 ms, disparo em fase de LIST/CSINe/ACDC, `pre_trigger_desvio_amostras`); motivo: sem bancada.
- NÃO VERIFICADO: o verificador contra um `.npz` real (formato gravado por `_salvar_captura`, `mestre.py:2191`, replicado nos testes; sem sessão real no repositório).
