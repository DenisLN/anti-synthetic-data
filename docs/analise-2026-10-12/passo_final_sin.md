# Passo final com a forma SIN interna (itens 1 a 3 feitos offline; 4 e 5 pendentes)

Branch `feat/passo-final-sin` (worktree `asd-passo-final-sin`), **rebaseado sobre a main 2abee44 (v1.15 parcial)** e commitado; sem push. Nada foi energizado e nenhum instrumento foi aberto. **Não fazer merge antes da validação na bancada (quarta, 2026-10-14).**

## 1. Nome da forma interna

**`SINE`** (`LIST:FUNCtion:SHAPe ..., SINE`). Evidência:

- Manual `docs/analise-2026-09-21/manuais_txt/AMETEK_MX_SCPI_Programming_Manual.txt`, linhas 4151-4185: `LIST:FUNCtion[:SHAPe]` aceita `SINe | SQUare | CSIN | <waveform_name>`; "Parameters: depends on the available shape defined by the TRACe:CAT?" (linha 4186); exemplo `LIST:FUNC SIN,ARRAY,TRIANG`.
- Transcrição `resultados/sessao_2026-10-07_*/scpi_transcricao.log`, linha 837 (e 1136, 1395): `TRACe:CATalog? -> "SINE,SQUARE,CLIPPED"` (e depois `...,TCC00,...`). O nome gravado no catálogo é `SINE`, que é a forma longa do `SINe` do manual.
- NÃO VERIFICADO na fonte real: que a Rev. 5.53 aceite `SINE` dentro de `LIST:FUNCtion:SHAPe` (nenhuma sessão gravada usou forma interna na lista; todas usam `TCCnn`). `SIN` curto e `SINusoid` (que é o que `SOURce:FUNCtion:SHAPe` usa em `ametek_orm.py`) são alternativas se `SINE` for rejeitado. O `:POINts?` e o `assert_no_errors` do programa dirão na hora (erro SCPI explícito).

## 2. Opção no código (LIGADA por padrão; `AMETEK_PASSO_FINAL_SIN=0` desliga)

- `logica/ametek_orm.py`: parâmetro de construtor `passo_final_sin=False` e constante `PASSO_FINAL_SIN_FORMA = "SINE"`; em `program_capture()`, quando ligada, a lista ganha um passo `SINE` com a tensão `base_voltage_rms`, dwell de um ciclo (o mesmo dos demais passos), `REPeat 0`. Nenhum `TRACe:DATA` extra (nada na Flash). `POINts?` conferidos contra o novo tamanho (N+1) e `_last_cycles = N+1`, que `arm_transient()` usa. Recusa (`ValueError`) se a tensão base passar de `max_voltage_rms`. Validações de IDN, timeout, 6000 pontos, `check_errors`/`assert_no_errors`, limites e cache de TRACe intocados (o passo é acrescentado depois do cache; a assinatura de TRACe não muda).
- Base nova (main 2abee44): o passo faz parte de `ProgramacaoCaptura` (campo `passo_final_sin`, `passos_nomes`, `passos_tensoes_rms`, `margem_final_pu()`, `programada_com_margem_pu()`), e `montar_programacao(..., passo_final_sin=)` o descreve; `program_capture` envia exatamente o que a função pura devolve nos dois modos (teste byte a byte estendido). `mestre.forma_programada` repassa o flag da fonte; `programada_pu()` continua com 6000 amostras (a margem final = senoide na base sai de `margem_final_pu()`). A recusa acima de `max_voltage_rms` ocorre agora antes de qualquer escrita.
- `logica/mestre.py`: `AMETEK_PASSO_FINAL_SIN = env_bool("AMETEK_PASSO_FINAL_SIN", default=True)`, repassada ao construtor da fonte em `Bancada.from_env`.
- `tests/test_offline.py`: testes — ligado por padrão; desligado reproduz a SCPI de antes (10 passos, sem `SINE`); ligado (11 passos, `SINE` por último, tensão 5 V, dwell 0,02 s, REPeat tudo 0, 10 `TRACe:DATA`, `_last_cycles` 11); recusa acima do limite.

```
$ ...\anti-synthetic-data\env\Scripts\python.exe -m unittest tests.test_offline   (cwd = worktree; ametek_orm importado de ...\asd-passo-final-sin\logica)
Ran 324 tests in ~38s
OK
```
(Os dois testes antigos de contagem de passos passaram a fixar `passo_final_sin=False`, pois verificam a SCPI de antes.)

## 3. Script `scripts/teste_passo_final_sin.py`

Importa `mestre` (Bancada, `_calcular_margem`, `_capturar_real` da classe 06 FLICKER, `_experiment_scripts`), `AmetekMX30` e o ORM do osciloscópio via `Bancada.from_env`; não escreve SCPI próprio. Pergunta o fator da probe, a tensão e a frequência (sem valores padrão), exige digitar `ENERGIZAR-PASSO-SIN` (case-sensitive) antes de definir `BENCH_MODE`/`ARM_OUTPUT=YES` e antes de importar `mestre`; valores fixos da bancada vêm de `scripts/bench_config.ps1`; faixa 300 V/415,8 Vp como em `start_bench_windows.ps1`. Roda (sem, com) com a mesma seed, liga/desliga `fonte.passo_final_sin` entre capturas, mede o RMS por ciclo da margem final (50 ms após a janela nominal), correlação e RMS por ciclo da janela rotulada, grava `resultados/passo_final_sin_<data>/{registros.npz,resultado.json}` e dá veredito. Critérios (escolha minha, constantes no topo): margem em 1,00 ± 0,01 pu; janela com correlação ≥ 0,999 e diferença máxima de RMS por ciclo ≤ 0,01 pu.

Teste offline do script:

```
$ ... scripts/teste_passo_final_sin.py --simulado
--- passo_final_sin=False ---
SOURce:LIST:FUNCtion:SHAPe TCC00,...,TCC11            SOURce:LIST:VOLTage ...,134.12689   REPeat 0 x12
--- passo_final_sin=True ---
SOURce:LIST:FUNCtion:SHAPe TCC00,...,TCC11,SINE       SOURce:LIST:VOLTage ...,127         REPeat 0 x13
[SIMULADO] Registros sinteticos; so valida a analise, NAO e medida de bancada.
  ciclo |  sem passo |  com passo SIN
      1 |     1.0561 |     1.0000   (ciclos 2 e 3 idem)
Janela rotulada: correlacao 1.00000; dif max 0.0000 pu
$ printf '10\n127\n60\nerrado\n' | ... scripts/teste_passo_final_sin.py
Digite ENERGIZAR-PASSO-SIN: Cancelado: confirmacao nao corresponde ...   (nada aberto)
```
O 1,0561 simulado é só o último ciclo mantido da forma 06 gerada (seed da captura 0), não medida. O programa mostra o último passo `134,12689 Vrms` sem a opção.

Comando para o operador (PowerShell, a partir do worktree, MX GUI e CLI fechados):

```powershell
cd "C:\Users\denis\Documents\1 Projetos\asd-passo-final-sin"
& "C:\Users\denis\Documents\1 Projetos\anti-synthetic-data\env\Scripts\python.exe" scripts\teste_passo_final_sin.py --repeticoes 3
```
(sem `--simulado`; pede probe, V, Hz e `ENERGIZAR-PASSO-SIN`). Exit code 0 = eficaz, 2 = não eficaz.

## 4. Medida na bancada — NÃO VERIFICADO

Validação de quarta (2026-10-14), PowerShell, MX GUI e CLI fechados, a partir do worktree (depois do merge: `cd C:\Users\denis\TCC\code`, mesmo comando):

```powershell
cd "C:\Users\denis\Documents\1 Projetos\asd-passo-final-sin"
& "C:\Users\denis\Documents\1 Projetos\anti-synthetic-data\env\Scripts\python.exe" scripts\teste_passo_final_sin.py --repeticoes 3
```

O script força desligado/ligado em cada rodada, independente do padrão. **Aprovação** (exit 0): margem final com o passo em 1,00 ± 0,01 pu da tensão base, janela rotulada idêntica com e sem (correlação ≥ 0,999, diferença máx. de RMS por ciclo ≤ 0,01 pu) e nenhum erro SCPI. Se `SINE` for rejeitado, tentar `SIN`/`SINusoid` em `PASSO_FINAL_SIN_FORMA` ou desligar com `AMETEK_PASSO_FINAL_SIN=0`. Depois da aprovação, rodar uma classe TRACe pela CLI (`run 06`) e conferir `tres_versoes`.

Pendente: exige operador, fonte e osciloscópio (regra do coordenador: sem energizar). `Bancada.from_env` e `_capturar_real` com `osc` reais não foram exercitados pelo script (só o modo simulado e a recusa de confirmação). Tabela RMS por ciclo (com/sem): a preencher.

## 5. Branch/PR — NÃO VERIFICADO
Commit feito no branch local, sem push; PR com o texto preparado pelo coordenador. Padrão já ligado e CHANGELOG/v1.15.md atualizado. Se a bancada reprovar: não fazer merge (ou mudar o padrão para False).

## Observações
- (baixa) `LIST:VOLTage` do último passo sem a opção é 134,1 Vrms (1,056 pu) a 127 V; é o "último ciclo mantido" que a proposta quer eliminar.
- (média) Risco de o passo SINE ser rejeitado (-113/-224) pelo nome; falha seria explícita no `check_errors` logo após `LIST:FUNCtion:SHAPe`, com a saída ainda sem disparar.
- (baixa) Com dwell de 1 ciclo o passo extra conta como ciclo na lista; `wait_transient_complete` e `arm_transient` esperam N+1 pontos (testado offline apenas).
