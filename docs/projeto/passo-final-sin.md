# Passo final SINE (fora da main)

:::{danger} Segurança
**Este recurso NÃO existe na `main`.** Ele vive só no branch `feat/passo-final-sin` (commit `18b144d`, PR #3), **nunca foi executado na bancada** e **não deve ser integrado antes da validação**. O texto do próprio branch diz: "Não fazer merge antes da validação na bancada". Nenhuma outra página deste site afirma que o passo final existe; qualquer menção a ele aponta para esta.
:::

{bdg-secondary}`FORA DA MAIN` {bdg-warning}`NÃO VERIFICADO` {bdg-danger}`PENDENTE P-18`

**Pergunta:** o que é o passo final SINE e o que ele muda na SCPI? **Resposta:** é um passo extra no fim da lista das classes de TRACe (`SOURce:LIST:FUNCtion:SHAPe ..., SINE`), na tensão base e com um ciclo de duração, para que a saída da fonte não fique **mantida no último ciclo** da forma depois que a lista termina; não grava nada na Flash (nenhum `TRACe:DATA` extra) e, no branch, vem **ligado por padrão** (`AMETEK_PASSO_FINAL_SIN=1`), desligável com `AMETEK_PASSO_FINAL_SIN=0`. Se a Rev. 5.53 aceita o nome `SINE` dentro de `LIST:FUNCtion:SHAPe` é exatamente o que não se sabe.

## 1. Por que existe

Ao fim de um `LIST` a MX30 continua no **último passo**: a lista de uma classe de TRACe acaba no último ciclo da forma, e a saída fica ali até outro comando (o mesmo fato que mantinha a fonte em 63 Hz depois da classe 18, quirk A11). Na margem de 50 ms depois da janela nominal, isso aparece como um ciclo repetido com a amplitude do último ciclo programado: a simulação do próprio branch mostra `LIST:VOLTage` final de **134,12689 V rms (1,056 pu)** a 127 V na classe 06, em vez da tensão base. O passo `SINE` na tensão base acaba com esse "último ciclo mantido". {bdg-warning}`NÃO VERIFICADO` na fonte real: o valor 1,056 pu é a conta do simulador do script (`--simulado`), não uma medida.

## 2. O que muda na SCPI

Para uma captura a 60 Hz (12 ciclos de 500 amostras), segundo o branch e os testes dele (324 testes, sem hardware):

| Comando | Sem o passo (padrão da `main`) | Com o passo (branch) |
|---|---|---|
| {scpi}`SOURce:LIST:FUNCtion:SHAPe` | `TCC00,...,TCC11` | `TCC00,...,TCC11,SINE` |
| {scpi}`SOURce:LIST:VOLTage` | 12 valores, o último é o rms do último ciclo (134,12689 no exemplo do branch) | 13 valores; o último é a tensão base (127) |
| {scpi}`SOURce:LIST:DWELl` | 12 valores | 13 valores (o passo `SINE` dura um ciclo, como os demais) |
| {scpi}`SOURce:LIST:REPeat` | `0` x 12 | `0` x 13 |
| `:POINts?` dos quatro eixos ({scpi}`SOURce:LIST:FUNCtion:POINts?`) | 12 | 13 |
| {scpi}`TRACe:DATA` | 12 gravações | **as mesmas 12** (nada novo na Flash) |

A conferência por `:POINts?` e o `assert_no_errors` logo depois de `LIST:FUNCtion:SHAPe` apontariam um nome rejeitado na hora, com a saída ainda sem disparar (erro `-113` ou `-224`).

**A evidência do nome.** O manual (`docs/manuais_txt/AMETEK_MX_SCPI_Programming_Manual.txt`, seção de `LIST:FUNCtion[:SHAPe]`, p. 93) aceita `SINe | SQUare | CSIN | <nome de forma>`; a transcrição de 07/10/2026 mostra `TRACe:CATalog? -> "SINE,SQUARE,CLIPPED"` ({doc}`../scpi/ametek-lista-trace`, exemplo E27), logo o nome do catálogo é `SINE`. Mas nenhuma sessão gravada usou uma forma interna na lista (todas usam `TCCnn`); `SIN` e `SINusoid` (esta é a forma que `SOURce:FUNCtion:SHAPe` aceita) são alternativas se `SINE` for rejeitado.

## 3. O que muda no ORM e no mestre (no branch)

Linhas do branch `github/feat/passo-final-sin` (base `d37e403`, não as da `main`):

| Onde | O que |
|---|---|
| `logica/ametek_orm.py:217` | `AmetekMX30.PASSO_FINAL_SIN_FORMA = "SINE"` |
| `logica/ametek_orm.py:235` | parâmetro do construtor `passo_final_sin: bool = True` (ligado por padrão) |
| `logica/ametek_orm.py:115` | campo `ProgramacaoCaptura.passo_final_sin`, mais `passos_nomes`, `passos_tensoes_rms`, `margem_final_pu()` e `programada_com_margem_pu()` |
| `logica/ametek_orm.py:1365-1446` | `montar_programacao(..., passo_final_sin=)` descreve o passo na função pura; `program_capture` envia exatamente o que ela devolve |
| `logica/ametek_orm.py:1469` | recusa (`ValueError`) se a tensão base passa de `max_voltage_rms`, antes de qualquer escrita |
| `logica/mestre.py:341` e `:990` | `AMETEK_PASSO_FINAL_SIN = env_bool("AMETEK_PASSO_FINAL_SIN", default=True)`, repassada ao construtor em `Bancada.from_env` |

`_last_cycles = N + 1`, que `arm_transient()` usa para conferir os `:POINts?`; `programada_pu()` continua devolvendo 6000 amostras (a margem final, uma senoide na base, sai de `margem_final_pu()`). As validações de IDN, timeout, 6000 pontos, `check_errors`/`assert_no_errors`, os limites de tensão e de pico e o cache de TRACe ficam como estavam: o passo é acrescentado depois do cache e a assinatura de TRACe não muda.

## 4. O script de validação e o critério

`scripts/teste_passo_final_sin.py` (223 linhas, só no branch) roda a **mesma captura** (classe 06, mesma seed) sem e com o passo, ligando e desligando `fonte.passo_final_sin` entre as capturas, mede o rms por ciclo da margem final (os 50 ms depois da janela nominal) e a identidade da janela rotulada, grava `resultados/passo_final_sin_<data>/{registros.npz,resultado.json}` e dá o veredito. Reutiliza `Bancada`, `ExperimentoWaveform` e `_capturar_real` de `mestre.py`; **não escreve SCPI próprio**.

- **Segurança:** pergunta o fator exato da probe, a tensão e a frequência (sem valores padrão) e exige digitar `ENERGIZAR-PASSO-SIN` (case-sensitive) **antes** de definir `BENCH_MODE`/`ARM_OUTPUT=YES` e de importar `mestre`. Faixa de 300 V rms e 415,8 Vp como em `start_bench_windows.ps1`. A saída é desligada ao fim.
- **Critério de aprovação (código de saída 0; 2 = não eficaz):**

| Medida | Limite |
|---|---|
| rms por ciclo da margem final com o passo | 1,00 ± 0,01 pu da tensão base |
| janela rotulada, com × sem o passo | correlação ≥ 0,999 e diferença máxima de rms por ciclo ≤ 0,01 pu |
| erros SCPI | nenhum |

Os limiares (0,01 pu e 0,999) são **escolha do autor do script**, constantes no topo do arquivo, sem dado de bancada. Testado só em modo simulado (`--simulado`: registros sintéticos, valida a análise, não é medida) e na recusa de confirmação errada (nada é aberto).

## 5. Estado e o que fecha

- **O que fecha:** executar o script na bancada ({bdg-danger}`PENDENTE P-18`: operador, fonte e osciloscópio; o branch previa a validação para 14/10/2026) e **decidir** se o padrão deve ser desligado. Nenhuma pasta `resultados/passo_final_sin_*` existe no checkout principal nem no diretório de trabalho do branch (conferido em 2026-10-16): não há registro de que o script tenha rodado.
- **Depois de aprovado:** rodar uma classe de TRACe pela CLI (`run 06`) e conferir as três versões ({doc}`../tres_versoes`).
- **Se reprovar:** não integrar, ou mudar o padrão para `False`.

:::{note} Nota de verificação
Conferido offline em 2026-10-16 com `git`:

- `git diff --stat d37e403 github/feat/passo-final-sin`: 6 arquivos, 457 inserções e 13 remoções (`CHANGELOG/v1.15.md`, `docs/analise-2026-10-12/passo_final_sin.md`, `logica/ametek_orm.py`, `logica/mestre.py`, `scripts/teste_passo_final_sin.py`, `tests/test_offline.py`).
- **Divergência registrada:** o relatório dentro do branch diz "rebaseado sobre a main 2abee44", mas o pai do único commit do branch é `d37e403` (`git merge-base main github/feat/passo-final-sin` devolve `d37e403`). O merge com a `main` (`fa82f49`) tem conflito textual em `CHANGELOG/v1.15.md` e em `tests/test_offline.py`; `ametek_orm.py` e `mestre.py` fundem sem marcador de conflito, mas a suíte do merge **não foi rodada** {bdg-warning}`NÃO VERIFICADO`. A suíte do branch (324 testes) é anterior à da `main` (497).
:::
