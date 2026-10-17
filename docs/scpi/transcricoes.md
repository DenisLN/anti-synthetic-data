# Exemplos reais da transcrição

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-success}`VERIFICADO NA BANCADA` {bdg-info}`OFFLINE`

**Pergunta:** de onde vêm os exemplos de comando SCPI desta referência e como se lê uma linha da transcrição? **Resposta:** de três arquivos `scpi_transcricao.log` gravados pelo próprio código (`AmetekORM.scpi`, nível debug) nas sessões de 07/10/2026, cada linha no formato `[hh:mm:ss.mmm] t=<monotônico> W|Q|R <texto>`; os 71 trechos abaixo foram conferidos contra os arquivos originais em 2026-10-16 (os 71 apareceram, em sequência, na linha indicada).

## Formato

`W` é a escrita de um comando; `Q` é o pedido de uma consulta; `R` é a resposta (`_transcrever`, `ametek_orm.py`). Cada `write()` produz `W comando`, `W *ESR?`... e `R *ESR? -> 0`: o `*ESR?` é o sincronismo ({scpi}`*ESR?`). `TRACe:DATA` e `TRACe:DEFine` não têm `*ESR?` a seguir, e `TRACe:DELete:ALL` também não. O payload é truncado a 160 caracteres (`MAX_TRANSCRICAO_CHARS`): é o que a própria transcrição grava. A latência de uma escrita sincronizada vai de 0,031 s a 0,047 s nos exemplos (E03 e E24); `TRACe:DEFine` dá 3,0 s até o `SYSTem:ERRor?` seguinte (E28).

## Origem e premissas de publicação

| Condição | Sessão | Arquivo |
|---|---|---|
| 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | `scpi_transcricao.log` |
| 127 V/60 Hz | `sessao_2026-10-07_14-59-54_run02` | `scpi_transcricao.log` |
| 230 V/50 Hz | `sessao_2026-10-07_230V_50Hz` | `scpi_transcricao.log` |

Os arquivos de log inteiros ficam fora do repositório (`resultados/` é ignorado pelo git): cada entrada da referência cita **no máximo cinco linhas** por comando, em texto corrido, e este índice só aponta a sessão e a linha. {bdg-danger}`PENDENTE P-29` Decisão do responsável: versionar um conjunto selecionado de trechos ou manter só esta referência.

O selo VERIFICADO NA BANCADA vale para o fato "o comando foi aceito e o `*ESR?` voltou 0", nessa condição e com o código **anterior à v1.15** (P-01), não para o efeito físico. O Keysight não tem transcrição: ver {doc}`keysight-aquisicao`.

## Índice dos 71 trechos

| Id | Comando | Condição | Sessão | Linha |
|---|---|---|---|---|
| E01 | {scpi}`OUTPut:STATe ON` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 174 |
| E02 | {scpi}`OUTPut:STATe?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 167 |
| E03 | {scpi}`*CLS` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 9 |
| E04 | {scpi}`*WAI` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 267 |
| E05 | {scpi}`ABORt` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 13 |
| E06 | {scpi}`SOURce:VOLTage:HIGH` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 41 |
| E07 | {scpi}`SOURce:FUNCtion:SHAPe SINusoid` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 69 |
| E08 | {scpi}`SOURce:FUNCtion:SHAPe:CSINusoid` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 710 |
| E09 | {scpi}`SOURce:MODE ACDC` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 6184 |
| E10 | {scpi}`SOURce:VOLTage:OFFSet` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 6195 |
| E11 | {scpi}`VOLTage:MODE STEP` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 241 |
| E12 | {scpi}`VOLTage:MODE PULSe` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 312 |
| E13 | {scpi}`VOLTage:TRIGgered` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 245 |
| E14 | {scpi}`PULSe:WIDTh` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 320 |
| E15 | {scpi}`VOLTage:TRIGgered?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 258 |
| E16 | {scpi}`PULSe:WIDTh?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 336 |
| E17 | {scpi}`VOLTage:MODE?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 255 |
| E18 | {scpi}`FUNCtion:MODE?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 261 |
| E19 | {scpi}`TRIGger:SYNChronize:PHASe` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 139 |
| E20 | {scpi}`FREQuency:MODE LIST` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 6104 |
| E21 | {scpi}`LIST:FREQuency` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 6108 |
| E22 | {scpi}`LIST:VOLTage` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 6112 |
| E23 | {scpi}`LIST:DWELl` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 6116 |
| E24 | {scpi}`SOURce:LIST:REPeat` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 958 |
| E25 | {scpi}`LIST:COUNt` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 6124 |
| E26 | {scpi}`LIST:STEP` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 6128 |
| E27 | {scpi}`TRACe:CATalog?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 835 |
| E28 | {scpi}`TRACe:DEFine` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 838 |
| E29 | {scpi}`TRACe:DATA` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 878 |
| E30 | {scpi}`TRACe:DELete:ALL` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 173 |
| E31 | {scpi}`SOURce:LIST:FUNCtion:SHAPe` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 928 |
| E32 | {scpi}`SOURce:LIST:VOLTage` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 938 |
| E33 | {scpi}`SOURce:LIST:DWELl` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 948 |
| E34 | {scpi}`SOURce:LIST:FUNCtion:POINts?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 935 |
| E35 | {scpi}`SOURce:LIST:REPeat:POINts?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 1062 |
| E36 | {scpi}`SOURce:LIST:COUNt` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 965 |
| E37 | {scpi}`SOURce:LIST:STEP` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 972 |
| E38 | {scpi}`FUNCtion:MODE LIST` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 979 |
| E39 | {scpi}`VOLTage:MODE LIST` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 986 |
| E40 | {scpi}`OUTPut:TTLTrg:MODE` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 146 |
| E41 | {scpi}`INITiate:IMMediate` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 271 |
| E42 | {scpi}`*TRG` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 284 |
| E43 | {scpi}`TRIGger:STATe?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 230 |
| E44 | {scpi}`TRIGger:SOURce?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 1065 |
| E45 | {scpi}`MEASure:VOLTage:AC?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 220 |
| E46 | {scpi}`STATus:OPERation:CONDition?` | 127 V/60 Hz | `sessao_2026-10-07_14-59-54_run02` | 216 |
| E47 | {scpi}`SOURce:FREQuency:MODE?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 264 |
| E48 | {scpi}`SOURce:FREQuency` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 111 |
| E49 | {scpi}`SOURce:VOLTage 0` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 118 |
| E50 | {scpi}`TRIGger:SOURce BUS` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 125 |
| E51 | {scpi}`INSTrument:COUPle` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 20 |
| E52 | {scpi}`SOURce:CURRent:PROTection:STATe` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 55 |
| E53 | {scpi}`*ESR?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 5 |
| E54 | {scpi}`SYSTem:ERRor?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 18 |
| E55 | {scpi}`SYSTem:ERRor?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 17 |
| E56 | {scpi}`*IDN?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 1 |
| E57 | {scpi}`OUTPut:TTLTrg:SOURce` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 153 |
| E58 | {scpi}`OUTPut:TTLTrg ON` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 160 |
| E59 | {scpi}`TRIGger:SYNChronize:SOURce` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 132 |
| E60 | {scpi}`SOURce:FREQuency:MODE FIXed` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 90 |
| E61 | {scpi}`FUNCtion:MODE FIXed` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 76 |
| E62 | {scpi}`VOLTage:MODE FIXed` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 83 |
| E63 | {scpi}`SOURce:MODE AC` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 27 |
| E64 | {scpi}`SOURce:VOLTage:RANGe` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 34 |
| E65 | {scpi}`SOURce:CURRent` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 48 |
| E66 | {scpi}`SOURce:CURRent:PROTection:DELay` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 62 |
| E67 | {scpi}`SOURce:FREQuency:SLEW` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 97 |
| E68 | {scpi}`SOURce:VOLTage:SLEW` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 104 |
| E69 | {scpi}`SOURce:LIST:VOLTage:POINts?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 945 |
| E70 | {scpi}`SOURce:LIST:DWELl:POINts?` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 955 |
| E71 | {scpi}`SOURce:VOLTage:LEVel:IMMediate:AMPLitude` | 127 V/50 Hz | `sessao_2026-10-07_127V_50Hz` | 207 |

As linhas indicam a primeira linha de cada trecho no arquivo original (nas consultas, a linha do `Q`).
