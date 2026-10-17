# Testes

Suíte **sem hardware**: baseline `tests/test_offline.py` com 497 métodos de teste identificados por leitura estática em `fa82f496`; essa contagem não é resultado de execução. Os novos testes `tests/test_pendencias_*.py` também devem ser descobertos. O total atual e os skips são os informados pelo comando abaixo, com Python, dependências e SHA registrados. Os dois ORMs rodam em modo simulado (`simulated=True`) ou com `ScriptedVisaConnection`/`ScriptedSerialVisaResource` (símbolos no próprio módulo), que respondem a comandos roteirizados.

```powershell
.\env\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v  # suíte atual; duração depende do ambiente
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
| v1.15 (dataset) | `MetadataLegivelERastreavelTests`, `PerfisDeFaixasTests` (byte a byte contra `34a0d82`), `SorteioInicioDuracaoFaseTests` (fixture `gerar_sorteio_v1_15.json`), `AssinaturaPortavelTests` (fixtures portáveis), `ParametrosSorteadosNasCompostasTests`, `TresVersoesTests`, `Classe08FronteiraTests`, `Classes05_07_18Tests`, `RuidoNaJanelaTests` |

## Fixtures (`tests/fixtures/`)
- `gerar_literatura_34a0d82.json`: 400 entradas (`classe/f0/seed/índice`: 20 classes × f0 50/60 × seeds 1234567/7654321 × índices 0–4) do `gerar()` do commit `34a0d82`, em duas formas (abaixo). **Não regravar `hashes`**: provam que o perfil `literatura` com `sorteio_posicao=False` é o dataset anterior. Guarda a versão do numpy.
- `gerar_sorteio_v1_15.json`: o mesmo, para o `gerar()` com sorteio da v1.15. Regravar só quando o dataset muda de propósito, declarando no CHANGELOG quais entradas mudaram (`python -m tests.gravar_fixtures_portaveis` regrava `portavel`; `hashes` são regravados à parte, na plataforma de origem).
- Duas assinaturas por entrada. `hashes`: SHA-256 exato (bytes float64 + parâmetros), **só na plataforma de origem** (Windows, Python 3.11.9): `AssinaturaPortavelTests.test_*_exato_na_plataforma_de_origem` pula com `skipTest` nas demais (`ASD_HASH_EXATO=1` força). `portavel.resumos`: `n`, parâmetros, soma, energia, mínimo, máximo e 4 projeções sobre vetores fixos (`default_rng(1000+k)`), comparados por tolerância (1e-9 pu; `tests/assinatura_portavel.py`) e usados pelos testes `PerfisDeFaixasTests`, `Classes05_07_18Tests`, `SorteioInicioDuracaoFaseTests`. Escolheu-se tolerância, não hash de valores arredondados, porque este cai numa fronteira de arredondamento por acaso (com 6000 amostras × 800 entradas e uma diferença de ~2·10⁻¹⁶, mesmo com arredondamento a 10⁻⁹ a chance de pelo menos uma amostra cair na fronteira é da ordem de dezenas por cento: estimativa, não medida). Contra-prova em `AssinaturaPortavelTests` (uma amostra mudada em 10⁻⁸ pu, parâmetro, forma e tamanho são pegos; 64 ULP em todas as amostras passa). Ver `docs/versionamento.md` §2.1.

## Quando rodar
Antes de qualquer commit, antes de qualquer sessão de coleta, depois de `set recalibracao on` (que muda `calibracao_extremos.json`; como reverter, `docs/operacao.md` §9) e ao fechar uma versão.
