# CA 5 a 6 % menor no modo ACDC (classe 19) — investigação

Data: 2026-10-12. Estado: **causa física NÃO VERIFICADA (pendente de bancada)**. Dados gravados excluem 4 das hipóteses prováveis e mostram que o déficit é real na saída da fonte (não é artefato do CH1); o script para medir o resto está pronto e não foi executado (sem acesso à bancada nem confirmação do operador).

Convenções: "pu" = por unidade do pico base (Vrms·√2). `T` = transcrição SCPI da sessão (`resultados/<sessão>/scpi_transcricao.log`). "run02" = `sessao_2026-10-07_14-59-54_run02` (127 V, **60 Hz**, `diagnostico_mode` ligado, único log com `MEASure:VOLTage:AC?` durante a classe 19). As outras duas: `sessao_2026-10-07_127V_50Hz` e `sessao_2026-10-07_230V_50Hz`. Métricas dos `.npz` recalculadas por mim: janela `tensao_pu[0][700:]` (regime), número inteiro de períodos, RMS CA = desvio-padrão, CC = média.

## 1. Hipóteses e checagem nos dados gravados

### 1.1 O que os dados gravados mostram (CH1)

| sessão | classe | offset programado (V) | CC medido CH1 (V) | CA RMS CH1 (V) | CA / V_base |
|---|---|---|---|---|---|
| 127 V / 50 Hz | 01 (AC) | 0 | −1,50 | 127,17 | 1,0013 |
| 127 V / 50 Hz | 19 ACDC | 5,58 | 4,30 | 120,77 | 0,9509 |
| 127 V / 50 Hz | 19 ACDC | 9,08 | 7,72 | 120,75 | 0,9508 |
| 127 V / 50 Hz | 19 ACDC | 16,09 | 14,88 | 120,73 | 0,9506 |
| 230 V / 50 Hz | 01 (AC) | 0 | −1,38 | 230,03 | 1,0001 |
| 230 V / 50 Hz | 19 ACDC | 10,10 / 16,45 / 29,14 | 8,51 / 14,95 / 27,44 | 215,72 / 215,64 / 215,64 | 0,9379 / 0,9376 / 0,9376 |
| run02 (127 V / 60 Hz) | 01 (AC) | 0 | −1,01 | 127,11 | 1,0009 |
| run02 | 19 ACDC | 5,58 / 9,08 / 16,09 | 7,55 / 11,01 / 18,05 | 119,78 / 119,75 / 119,78 | 0,9432 / 0,9429 / 0,9432 |

(Fonte: `resultados/<sessão>/{01,19}_*.npz`; offsets de `metadata/19_dc_offset.jsonl`, campo `parametros.dc_offset_pu` × pico base.) O déficit **não depende do offset** (variação ≤ 0,0003 pu entre capturas) e **muda com a sessão**: 0,951 (127 V/50 Hz), 0,943 (127 V/60 Hz), 0,938 (230 V/50 Hz). Amplitude por ciclo constante ao longo do registro (127 V/50 Hz: 0,950–0,952 em todos os 13 ciclos; 230 V: 0,937–0,938; run02: 0,942–0,944), calculado ciclo a ciclo.

### 1.2 Hipóteses

| # | hipótese | evidência | veredito | gravidade se verdadeira |
|---|---|---|---|---|
| H1 | `VOLTage:TRIGgered` é RMS **total** (CA+CC): CA = √(V²−off²) | Previsto a 127 V: CA = 126,88 / 126,68 / 125,97 (−0,1 / −0,25 / −0,8 %), **dependente do offset**. Observado: constante em 0,9506–0,9509. Para explicar 5 % seria preciso offset ≈ 40 V, e o maior é 16 V. | **REFUTADA** | — |
| H2 | Limite de pico (425 Vp, manual §4.14, `AMETEK_MX_SCPI_Programming_Manual.txt:3706-3716`) ou compressão/clip em ACDC | Déficit existe a 127 V com pico ≈ 190 Vp (45 % do limite). THD medido na validação física: 0,14–0,26 % (`metadata/19_dc_offset.jsonl`, `validacao_fisica.thd_medida`), sem achatamento; picos previstos ≤ 389,8 V < 415,8 V. Sinal é senoide pura com amplitude escalada. | **REFUTADA** como causa | — |
| H3 | Artefato da cadeia de medição (probe/escala do CH1) | O mesmo CH1 lê 1,000–1,001 em AC (classe 01, tabela 1.1). **A própria fonte** (sentido interno) também lê menos em ACDC — ver 1.3. | **REFUTADA** como causa única | — |
| H4 | Transiente de troca de modo / degrau ainda assentando | Amplitude por ciclo constante desde o 1.º ciclo (1.1). Em run02 as capturas 2 e 3 reenviam `SOURce:MODE ACDC` com a fonte **já** em ACDC e a saída **não** zera (`T` run02:8404 → 118,902 V antes; 8424 → 118,907 V depois) e o valor continua ≈ 0,943 pu. É regime estacionário. | **REFUTADA** | — |
| H5 | O ACDC usa outra faixa/ganho de CA na fonte | O manual diz que `VOLTage:RANGe?` devolve a faixa **CA** em AC e ACDC (`...Manual.txt:5008-5010`) e não documenta ganho diferente em ACDC (grep por ACDC/AC+DC: linhas 406, 4389-4396, 4817-4885, 5008, 6787, 10209-10413; nenhuma menciona ganho). Nenhuma transcrição consulta `VOLTage:RANGe?` depois do ACDC (as três sessões escrevem `SOURce:VOLTage:RANGe 300` na linha 34 e nunca mais). | **NÃO VERIFICADA** (o script consulta) | — |
| H6 | Ganho/calibração do caminho CA em ACDC diferente do AC (calibração por faixa; comandos `CALibrate:` em `...Manual.txt:1511-1527`, protegidos) | Compatível com "mesmo valor com offsets 5,6–16 V", mas é inferência: nenhum dado separa de H5/H7/H8. Não consultar nem alterar calibração. | **NÃO VERIFICADA** | média (dependência V/f invalida um fator único) |
| H7 | Dependência da tensão | 127 V → 0,951 (déficit 6,2 V); 230 V → 0,938 (14,3 V), ambas 50 Hz, ~10 min de diferença entre as sessões. Não é proporcional em pu. | **Sugerida pelos dados** (2 pontos); não separa V de "sessão" | média |
| H8 | Dependência da frequência | 50 Hz → 0,951; 60 Hz → 0,943, mas run02 também tem **CC deslocado +1,95 V** (ver 1.4), `diagnostico_mode` ligado e outra hora; frequência e sessão estão confundidas. | **NÃO VERIFICADA** | média |
| H9 | O caminho `VOLTage:TRIGgered` (STEP) aplica ganho diferente de `VOLTage` imediato em ACDC | Nenhum dado: a 19 só usa STEP. | **NÃO VERIFICADA** (linha 3 do script) | — |

### 1.3 A fonte também mede o déficit (run02, único log com MEAS em ACDC)

Em ACDC, `MEASure:VOLTage:AC?` devolve o RMS **total** (CA+CC), apesar do texto do manual ("ac rms voltage", `...Manual.txt:3031`): com o offset de 5,58 V já programado e **antes** do degrau (CA = 0), a fonte leu 5,491 V (`T` run02:8310). Assumindo isso, a componente CA vista pela fonte é:

| captura | offset (V) | MEAS AC? bruto (V), mediana | `T` run02 | CA = √(MEAS²−off²) (V) | CA / 127 | CH1 CA (V) | CH1 / CA da fonte |
|---|---|---|---|---|---|---|---|
| 19-0001 | 5,580 | 118,927 | 8373, 8388 | 118,796 | 0,9354 | 119,784 | 1,0083 |
| 19-0002 | 9,082 | 119,123 | 8459–8522 | 118,776 | 0,9352 | 119,753 | 1,0082 |
| 19-0003 | 16,088 | 119,862 | 8608–8686 | 118,777 | 0,9353 | 119,782 | 1,0085 |

Em AC (classe 01, mesma sessão) a fonte lê 126,54–126,56 V (`T` run02:287–1063), CH1 127,11 V, razão CH1/fonte 1,0045. Logo a fonte e o CH1 concordam que a saída em ACDC está ~6,5 % (fonte) / 5,7 % (CH1) abaixo de 127 V; a diferença residual de 0,4 % entre as razões (1,0083 vs 1,0045) fica sem explicação. Que o CA derivado seja idêntico nas 3 capturas (118,776–118,796) também confirma a interpretação "total" do MEAS. **Premissa**: esta interpretação vem de uma única leitura pré-degrau (5,491 V) e da consistência das 3 capturas; o script mede `MEASure:VOLTage:DC?` para fechá-la (NÃO VERIFICADO até lá).

### 1.4 Outros achados (sem filtro de gravidade)

- **[média] CC em run02 diverge das outras sessões.** Delta CC medido − programado: 127 V/50 Hz −1,20 a −1,36 V; 230 V −1,50 a −1,69 V; run02 **+1,93 a +1,97 V**, enquanto a classe 01 dá viés de cadeia de −1,0 a −1,5 V nas três. Ou seja, em run02 o CC está ~+3 V acima do que o viés da cadeia explica. A afirmação do professor ("CC está ok, 0,005–0,0075 pu abaixo") vale para as duas sessões de 50 Hz (−0,0067 a −0,0076 pu), **não** para run02 (+0,0107 a +0,0110 pu). Causa não investigada; o script mede o CC de novo (fonte e CH1) e a 60 Hz.
- **[baixa] `enable_dc_offset()` reenvia `SOURce:MODE ACDC` a cada captura** (`logica/ametek_orm.py:1009`; `experimentos_nativos/19.py:39`) mesmo já em ACDC; não zera a saída (`T` run02:8404/8424), então é inócuo, só custa ~0,3 s por captura.
- **[baixa] `measure_voltage()` (`logica/ametek_orm.py:1728-1729`) em ACDC devolve RMS total, não CA** (1.3). Hoje só é usado em AC (`mestre.verificar_cadeia_de_medicao`), então sem efeito; vale um comentário se alguém passar a usá-lo em ACDC.
- **[baixa] Pedido/abordagem**: a pergunta pode estar parcialmente mal formulada — a 19 não mede "a fonte vs o CH1" em ACDC; o CH1 já mostra o déficit e a fonte também. A abordagem melhor é a do item 4: tratar o ganho CA em ACDC como uma calibração por condição (V, f), igual ao que já existe para extremos (`logica/calibracao_extremos.json`), em vez de procurar uma constante única.

## 2. `scripts/diag_acdc_amplitude.py`

Importa `AmetekMX30` e `KeysightDSOX4034A` do projeto (`logica/`), com os limites do `start_bench_windows.ps1` para range 300 V (max_rms 300, max_pico 415,8, 0,5 A; COM10/115200 e IDN/SCPI via ORM). CH1 como na bateria (DC, probe informada, escala **fixa** para todas as condições). Por condição: 5 leituras de `MEASure:VOLTage:AC?`, de `MEASure:VOLTage:DC?` e de `VOLTage:RANGe?` (as duas últimas nunca foram usadas na Rev. 5.53: se falharem, o script registra, esvazia a fila e segue sem a coluna) e 3 aquisições forçadas do CH1 (média, RMS CA, RMS total, Vmax/Vmin sobre períodos inteiros; cross-check `:MEASure:VRMS?`). Condições, na tensão base:

1. AC / STEP / offset 0 (como a classe 01)
2. ACDC / STEP / offset 0 (entrada limpa AC→ACDC→degrau, como a 19)
3. ACDC / `VOLTage` imediato / offset 0 (separa H9)
4. ACDC / STEP / offset 2 % e 10 % (`--offsets-pu`, 0,02–0,10 pu como a 19)
5. AC / STEP (controle final: separa deriva no tempo)
6. Com `--testar-compensacao`: ACDC / STEP programando `V/g` (g = CA/alvo da condição 2), offset 0 e 10 %.

Segurança: exige digitar `ENERGIZAR-ACDC` (case-sensitive; sem `--simulado` não há bypass), `BENCH_MODE=1`, `--probe` obrigatório sem padrão, V ≤ 270, offsets 0,02–0,10, pior caso de pico planejado ≤ 415,8 Vp; usa `enable_dc_offset()`/`trigger_step()` (validam pico e limite rms); `finally` volta a AC e chama `safe_shutdown()`; Ctrl+C reativado via `mestre.garantir_ctrl_c_no_windows` (importação tolerante). Não altera 19.py, `ametek_orm.py` nem `mestre.py`. Saídas em `logs/diag_acdc_amplitude-<ts>.{log,json,md}` e `-scpi.log`.

Teste sem hardware (`--simulado`: fonte no modo simulado do ORM + CH1 **fictício** com ganho ACDC 0,95 imposto por mim; **não é medida de bancada**, só prova que o fluxo e a aritmética funcionam, incluindo a compensação):

```
> env\Scripts\python.exe scripts\diag_acdc_amplitude.py --simulado --probe 500 --vrms 127 --hz 60 --testar-compensacao
| condição | V_alvo | V_prog | fonte AC? (V) | fonte DC? (V) | CH1 AC (V) | CH1 CC (V) | CH1 total (V) | CH1 AC / alvo | CH1 total / fonte AC? |
| AC / STEP / off 0 | 127.000 | 127.0 | 126.543 | 0.000 | 126.999 | -0.003 | 126.999 | 1.0000 | 1.0036 |
| ACDC / STEP / off 0 | 127.000 | 127.0 | 120.216 | 0.000 | 120.648 | -0.002 | 120.648 | 0.9500 | 1.0036 |
| ACDC / imediato / off 0 | 127.000 | 127.0 | 120.216 | 0.000 | 120.650 | -0.002 | 120.650 | 0.9500 | 1.0036 |
| ACDC / STEP / off 2 % | 127.000 | 127.0 | 120.269 | 3.592 | 120.650 | 3.594 | 120.704 | 0.9500 | 1.0036 |
| ACDC / STEP / off 10 % | 127.000 | 127.0 | 121.540 | 17.961 | 120.650 | 17.960 | 121.979 | 0.9500 | 1.0036 |
| AC / STEP / controle final | 127.000 | 127.0 | 126.543 | 0.000 | 127.003 | 0.002 | 127.003 | 1.0000 | 1.0036 |
| ACDC / STEP / off 0 % / V_prog=133.7 | 127.000 | 133.7 | 126.558 | 0.000 | 127.016 | 0.004 | 127.016 | 1.0001 | 1.0036 |
| ACDC / STEP / off 10 % / V_prog=133.7 | 127.000 | 133.7 | 127.817 | 17.961 | 127.019 | 17.957 | 128.282 | 1.0002 | 1.0036 |
```
Também verifiquei que o script recusa: sem `BENCH_MODE`, sem `--probe`, e `--offsets-pu 0.2`.

## 3. Execução na bancada — **NÃO VERIFICADO (pendente de bancada)**

Não executada: sem acesso à bancada nem à confirmação digitada do operador. Nenhuma medida deste item existe. Comando exato (PowerShell, CLI da bancada fechada; trocar `<FATOR>` pelo número escrito na probe — as sessões de 07/10 usaram 500, `probe_tensao` nos metadata, mas o operador deve conferir a probe física):

```powershell
cd C:\Users\denis\TCC\code
$env:BENCH_MODE = "1"
env\Scripts\python.exe scripts\diag_acdc_amplitude.py --probe <FATOR> --vrms 127 --hz 60 --testar-compensacao
# depois, na mesma sessão, para separar frequência e tensão (H7/H8):
env\Scripts\python.exe scripts\diag_acdc_amplitude.py --probe <FATOR> --vrms 127 --hz 50 --testar-compensacao
env\Scripts\python.exe scripts\diag_acdc_amplitude.py --probe <FATOR> --vrms 230 --hz 50 --testar-compensacao
```

Cada execução pede `ENERGIZAR-ACDC` e leva ~2–3 min. Se algo falhar na infraestrutura: confirmar OUTPUT OFF no painel, não repetir, entregar o `logs\diag_acdc_amplitude-*.log` mais recente.

Resultado esperado em cada hipótese (para ler a tabela):

| se a tabela mostrar... | conclui |
|---|---|
| linha 2 ≈ linha 3 ≈ 0,94–0,95 e linha 1 e 5 ≈ 1,000 | déficit é do modo ACDC, não do STEP (H9 refutada) |
| linha 3 ≈ 1,000 e linha 2 ≈ 0,95 | é o caminho `VOLTage:TRIGgered` em ACDC → trocar para `VOLTage` imediato resolve |
| `VOLTage:RANGe?` ≠ 300 em ACDC | faixa muda com o modo (H5) |
| linha 5 ≠ linha 1 | deriva temporal contamina a comparação |
| g muda entre 127/50, 127/60 e 230/50 | g é função de (V, f) (H7/H8): fator único não serve |
| `CH1 AC/alvo` das linhas de compensação ≈ 1,000 | a correção do item 4 funciona na condição testada |

## 4. Correção proposta (não aplicada) — causa **NÃO VERIFICADA**, correção **NÃO VERIFICADA**

Ainda não há causa medida; o que os dados sustentam é *o que corrigir*, não *por que*: em ACDC a fonte entrega CA = g·V_programado, com g constante em relação ao offset (0,9506–0,9509 numa sessão) e dependente da condição (0,9508 / 0,9431 / 0,9377). Proposta:

1. **Compensar a tensão programada na 19**, por condição: `v_prog = round(V_base / g(V, f), 1)` em `Experimento.configurar` (hoje `experimentos_nativos/19.py:37-40` usa `base_voltage_rms` em ambos), passando o **mesmo** `v_prog·√2` como `ac_peak_v` a `enable_dc_offset()` (`logica/ametek_orm.py:994-1024`, que valida pico) e `v_prog` a `trigger_step()` (`:762-792`, que quantiza a 0,1 V). Offset (`offset_v`) fica como está: o CC não depende de g.
2. **g vem da medida**, não de constante: o script produz `g = CH1 CA / alvo` (condição 2) por (V, f); guardar em tabela (como `logica/calibracao_extremos.json`) e, sem entrada para a condição, **não compensar** e avisar. Valores provisórios dos dados gravados (não usar sem confirmar na bancada): g = 0,9508 (127 V/50 Hz), 0,9431 (127 V/60 Hz), 0,9377 (230 V/50 Hz).
3. Efeito esperado em pu (aritmético, a confirmar): 127 V/50 Hz → `v_prog` 133,6 V → CA/alvo 1,0002; 127 V/60 Hz → 134,7 V → 1,0003; 230 V/50 Hz → 245,3 V → 1,0001; o resíduo é só a quantização de 0,1 V (±0,04 % a 127 V). CC inalterado (viés de cadeia −0,0067 a −0,0076 pu).
4. Limites (de `AGENTS.md`, mantidos): pico total = √2·V_prog + offset ≤ `max_peak_v` (415,8). Pior caso com offset 0,10 pu: 127 V → 206,9 Vp; 230 V → 379,4 Vp. A compensação fica inviável acima de ≈ 252 Vrms (g = 0,9377); nesse caso `enable_dc_offset()` levanta `ParameterOutOfBoundsError`, o que é o comportamento correto; a classe deve cair para "sem compensação, registrado" em vez de relaxar o limite. `max_voltage_rms`/`max_peak_v`/`max_current_a` não mudam.
5. **Alternativa a testar se a linha 3 do script der ≈ 1,000**: trocar o STEP por `VOLTage` imediato na 19 (muda o fluxo da classe, mas sem tabela de ganhos). Só vale após a medida.

Contra-indicação a registrar: compensar altera `pico_programado_v` nos metadata e o que a validação física espera; o `gerar()` (dataset) não muda.

## Itens NÃO VERIFICADO

- Item 3 inteiro (nenhuma medida de bancada feita).
- Causa física do déficit em ACDC (H5, H6, H8, H9).
- Se a correção do item 4 restaura 1,000 pu (o teste está no script, `--testar-compensacao`).
- Interpretação de `MEASure:VOLTage:AC?` como RMS total em ACDC (uma leitura pré-degrau + consistência das 3 capturas; `MEASure:VOLTage:DC?` e `VOLTage:RANGe?` nunca foram consultados na Rev. 5.53 e podem ser rejeitados).
- CC +3 V em run02 (1.4).
- A diferença de 0,4 % entre a razão CH1/fonte em ACDC (1,0083) e em AC (1,0045).
