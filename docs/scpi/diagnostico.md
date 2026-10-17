# Comandos só de diagnóstico

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` (sem exemplo real de transcrição)

**Pergunta:** que comandos SCPI aparecem só em scripts de diagnóstico, fora de `ametek_orm.py` e `oscilloscope_orm.py`? **Resposta:** algumas dezenas de formas, em `scripts/diag_*.py` e em `logica/preflight_new.py`; servem para medir comportamento do instrumento (as quirks A1, A12, A13 e A17 saíram do `diag_nativo_output_off.py`, rodado em 30/09/2026) e **não têm entrada completa** nesta referência, porque a regra "tudo passa pelo ORM" não vale para eles: dois scripts de PyVISA cru abrem `ASRL10::INSTR` e o endereço USB do Keysight escritos no código, sem `validate_bench_configuration` e sem o limite de pico do ORM.

:::{danger} Segurança
`scripts/diag_saida_vs_medida.py` e `scripts/diag_fonte_vs_osciloscopio.py` energizam a fonte por PyVISA cru (`OUTPut:STATe ON` nas linhas 72 e 101), sem passar por `AmetekMX30` nem por `validate_bench_configuration`. A proteção é a confirmação digitada (`ENERGIZAR-50V` e `ENERGIZAR-127V`, case-sensitive) e o `OUTPut:STATe OFF` no `finally`. Não adaptar esses scripts para outra tensão sem reler o código.
:::

## 1. AMETEK

| Origem | Comandos (consulta ou escrita) | Para que serve |
|---|---|---|
| `scripts/diag_acdc_amplitude.py` (confirmação `ENERGIZAR-ACDC`) | `MEASure:VOLTage:DC?` (linha 227), `SOURce:VOLTage:RANGe?` | separar a parte CC da CA em modo `ACDC` (déficit de 5 a 6 %, A19, P-17); **nunca rodou** |
| `scripts/diag_nativo_output_off.py` (saída sempre desligada) | `*OPT?`, `SYSTem:CONFigure?` (linhas 333-334), `*STB?`, `STATus:QUEStionable:CONDition?`, `STATus:OPERation:CONDition?` (linhas 461-462), `SOURce:VOLTage:HIGH?` (linhas 354, 360, 374) | ensaios N1 a N3 e T10 a T14 de 30/09/2026: rajada de comandos, `*OPC?` isolado, `VOLTage:HIGH` rms ou pico |
| `scripts/diag_nativo_output_off.py` | `PULSe:PERiod`, `PULSe:COUNt`, `PULSe:DCYCle?`, `PULSe:HOLD?` e as consultas `VOLTage:MODE?`, `VOLTage:TRIGgered?`, `PULSe:WIDTh?` (linhas 136-180) | investigar a largura "presa" do PULSe (H-NATIVO) |
| `scripts/diag_nativo_output_off.py` | `SOURce:MODE ACDC;*OPC` (linha 241), `*OPC` na mesma mensagem do comando (manual p. 136) | ensaio T15: a Rev. 5.53 não segura a resposta do `*OPC?` (A17) |
| `scripts/diag_saida_vs_medida.py`, `diag_fonte_vs_osciloscopio.py` | `INSTrument:NSELect <fase>` (linhas 79 e 63), `OUTPut:STATe ON/OFF/?` | comparar a saída de cada fase com a medida do osciloscópio |
| `logica/preflight_new.py` | `FUNCtion:SHAPe`, `LIST:REPeat:COUNt` e `SOURce:LIST:REPeat:COUNt` (testes das variantes que **falham**, `_test_list_repeat_count`), `MEASure:*` (`_test_measurements`) | `native` e `--list-diagnostics`; ver {doc}`ametek-nao-funciona` |

## 2. Keysight

| Origem | Comandos | Para que serve |
|---|---|---|
| `scripts/diag_fonte_vs_osciloscopio.py` | `:MEASure:VMAX? CHANnel1` (linha 66), `:CHANnel1:SCALe 50`, `:CHANnel1:OFFSet 0`, `:TIMebase:SCALe 0.01`, `:TRIGger:EDGE:LEVel 0`, `:TRIGger:SWEep AUTO`, `:RUN` (linhas 79-81) | medir a saída em regime, sem trigger externo |
| `scripts/diag_osciloscopio_canais.py` | `:RUN` (linha 28) e consultas `:CHANnel<n>:PROBe?`, `PROBe:ID?`, `IMPedance?`, `BWLimit?`, `COUPling?`, `DISPlay?`, `OFFSet?`, `SCALe?`, `UNITs?`, `:TRIGger:EDGE:SOURce?`, `:MEASure:VPP? CHANnel1`, `:MEASure:VRMS? DISPlay,AC,CHANnel2` (linhas 31-37) | inspecionar a configuração dos canais |

O comando `:RUN` não é enviado pelo ORM: o código usa `:STOP` e `:SINGle`. As formas equivalentes usadas pelo ORM têm entrada em {doc}`keysight-aquisicao`, {doc}`keysight-trigger` e {doc}`keysight-waveform`.

:::{note} Nota de verificação
As linhas foram obtidas por busca textual nos scripts em 2026-10-16 (`grep` dos cabeçalhos citados). Quais scripts já rodaram na bancada: `diag_nativo_output_off.py` em 30/09/2026 (A1, A12, A13, A17); `diag_acdc_amplitude.py` nunca rodou; `diag_marcadores_trace.py`, `diag_ciclos_trace.py` e `verificar_sessao_bancada.py` ver {doc}`../codigo/scripts`.
:::
