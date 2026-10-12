# Testes

Uma única suíte, **sem hardware**: `tests/test_offline.py` (370 testes, todos OK em `d37e403`; 57 classes `unittest`). Os dois ORMs rodam em modo simulado (`simulated=True`) ou com `ScriptedVisaConnection`/`ScriptedSerialVisaResource` (`:134-206`), que respondem a comandos roteirizados.

```powershell
.\env\Scripts\python.exe -m unittest tests.test_offline            # tudo (~35 s)
.\env\Scripts\python.exe -m unittest tests.test_offline.PerfisDeFaixasTests -v
.\env\Scripts\python.exe -m unittest tests.test_offline.PerfisDeFaixasTests.test_literatura_reproduz_byte_a_byte_o_gerar_do_commit_34a0d82
```
Os testes gravam em pastas temporárias; para forçar o `TEMP` fora do projeto defina `$env:TEMP`/`$env:TMP` antes. Ruído de `[ERROR]` no log durante a execução é esperado (testes de falha).

Utilitários: `_BancadaFake` (config mínima sem instrumentos), `_load_experimento(id)` (carrega um `NN.py` como o `Bancada` faz), `_sem_sorteio(exp)`, `_config_bancada(...)`.

## Mapa por área

| Área | Classes de teste |
|---|---|
| Sinais e ORM da AMETEK | `SignalTests`, `ValorParaCapturaTests`, `AmetekTests`, `DiagnosticoLogTests`, `KeysightTests` |
| Preflights | `PreflightNewTests` |
| Resiliência e erros | `BateriaResilienciaTests`, `ErroDeterministicoEPreValidacaoTests`, `CapturaDescartavelTests`, `BateriaExcluirTests`, `CadeiaDeMedicaoTests` |
| Capturas e níveis | `ConfigCoberturaTests`, `TotalNiveisTests`, `RemapeamentoNivelTests`, `CoberturaParametroContinuoTests`, `CapturasPadraoPorClasseTests`, `CapturasMaxCliPadraoTests`, `SeedReprodutivelTests` |
| Gravação | `SalvarClasseArquivoUnicoTests`, `SalvarClasseSimuladoTests`, `SalvamentoIncrementalTests`, `PastaDeSessaoPorRunTests`, `LogDeSessaoEMetadataTests` |
| Caminho nativo e trigger | `CaminhoNativoIntegridadeTests`, `ArmLeDeVoltaTests`, `FaseDeDisparoTests`, `FrequenciaBaseTests`, `PosicaoDoTriggerTests`, `MargemCapturaTests` |
| Validação física e extremos | `ValidacaoFisicaTests`, `ValidacaoSemCiclosExcluidosTests`, `ExtremosFisicosTests`, `Classe08BancadaTests`, `LimiteDeBancada220VTests`, `CalibracaoPorCondicaoTests`, `RelatorioERecalibracaoTests` |
| CLI | `CliCapturasTests`, `CliSeedTests`, `TerminalDeDiagnosticoTests`, `CliRecalibracaoEHtmlTests` |
| Análise offline | `AnalisarSessaoTests`, `JanelaNominalEAnaliseTests`, `CorrelacaoDisturbioTests`, `RecorteMargemERelatorioHtmlTests` |
| v1.15 (dataset) | `MetadataLegivelERastreavelTests`, `PerfisDeFaixasTests` (byte a byte contra `34a0d82`), `SorteioInicioDuracaoFaseTests` (fixture `gerar_sorteio_v1_15.json`), `ParametrosSorteadosNasCompostasTests`, `TresVersoesTests`, `Classe08FronteiraTests`, `Classes05_07_18Tests`, `RuidoNaJanelaTests` |

## Fixtures (`tests/fixtures/`)
- `gerar_literatura_34a0d82.json`: 400 SHA-256 (`classe/f0/seed/índice`: 20 classes × f0 50/60 × seeds 1234567/7654321 × índices 0–4) do `gerar()` do commit `34a0d82`. **Não regravar**: prova que o perfil `literatura` com `sorteio_posicao=False` é o dataset anterior. Guarda a versão do numpy.
- `gerar_sorteio_v1_15.json`: o mesmo, para o `gerar()` com sorteio da v1.15. Regravar só quando o dataset muda de propósito, declarando no CHANGELOG quais entradas mudaram.

## Quando rodar
Antes de qualquer commit, antes de qualquer sessão de coleta, depois de `set recalibracao on` (que muda `calibracao_extremos.json`) e ao fechar uma versão.
