# Arquitetura

Linhas citadas (`arquivo:linha`) valem para o commit `d37e403` (v1.15 em andamento, sem alteração de código na revisão da documentação). Se o código mudar, procure pelo nome da função.

## 1. Visão geral

O projeto gera o dataset rotulado de 20 classes de distúrbio de tensão (200 ms, 6000 amostras, 30 kSa/s) de duas formas:

```
                         ┌── SIMULADO (BENCH_MODE=0) ──► gerar() ──► ruído ──► resultados/*.npz
 mestre.main / CLI ──────┤
                         └── BANCADA  (BENCH_MODE=1) ──► gerar() ──► AMETEK MX30 ──► Keysight DSO-X
                                                          (modelo)    (programa/dispara)  (mede, CH1)
                                                                              │
                                              resultados/sessao_*/  ◄─────────┘
                                              (.npz, metadata, logs, três versões)
```

- Na **bancada**, cada captura programa a fonte (nativa ou TRACe/LIST), dispara por `*TRG`; o pulso BOT (Trigger Out → EXT Trigger por BNC) dispara o osciloscópio, que lê a tensão no CH1.
- Todo comando SCPI passa por métodos semânticos que validam limites; um experimento nunca escreve SCPI cru (regra da v1.1).

## 2. Mapa de arquivos

| Caminho | Papel |
|---|---|
| `README.md`, `AGENTS.md` | porta de entrada; regras para agentes e limites de segurança |
| `requirements.txt` | versões fixas: numpy 2.4.6, PyMeasure 0.16.0, PyVISA 1.14.1, matplotlib 3.11.2 (comentário do arquivo: numpy 2.4 exige Python ≥ 3.11) |
| `.env.example` | referência de variáveis de ambiente fora do fluxo PowerShell (ver `docs/configuracao.md`) |
| `experimentos.txt` | especificação **original** das 20 classes (texto). O código atual difere em pontos listados em `docs/classes.md` |
| `logica/mestre.py` | configuração global (constantes e variáveis de ambiente), `Config`, `Bancada`, `ExperimentoBase/Nativo/Waveform`, pré-validação, validação física, gravação, `main()` do dataset simulado |
| `logica/ametek_orm.py` | driver da fonte `AmetekMX30` (+ `ProgramacaoCaptura`, exceções) |
| `logica/oscilloscope_orm.py` | driver `KeysightDSOX4034A` (PyMeasure) |
| `logica/sinais.py` | matemática pura (janela, ruído, entalhes, THD, correlação, forma programada das nativas) |
| `logica/perfis.py` | faixas dos perfis `norma`/`literatura`/`fronteira` e `FAIXAS_SORTEADAS` |
| `logica/cli.py` | REPL do operador (`bancada>`) |
| `logica/preflight_new.py` | comissionamento: comunicação, trigger, baixa tensão (tensão base), comandos nativos, diagnóstico de LIST (o antigo `preflight.py` foi removido na v1.15) |
| `logica/sessao_io.py` | formato 2 dos `.npz` (um `NN_classe.npz` comprimido por classe, com perfis e versões): `ArquivoDaClasse` (escrita, spool por captura) e `ler_capturas`/`ler_pasta` (leitura dos formatos 1 e 2, usada por `recortar_margem`, `relatorio_html`, `analisar_sessao` e `scripts/gerar_*.py`); `docs/dataset.md` |
| `logica/analisar_sessao.py` | análise offline numérica de uma sessão (lag, correlação, correlação do distúrbio, razão de pico) |
| `logica/recortar_margem.py` | recorta a margem de 20/50 ms (saída em `sem_margem/`) |
| `logica/relatorio_html.py` + `logica/modelos/relatorio_capturas.html` | relatório HTML autocontido (figuras em base64); ao fim do run e opções: `docs/operacao.md` §9 |
| `logica/calibracao_extremos.json` | fatores de extremo por condição e por classe |
| `logica/diag_digitizer_*.py` | removidos em 2026-10-13 (sondas do modo Digitizer, v1.10, descartado; histórico no git até `d3c7ce7`) |
| `experimentos_nativos/` | classes 01–05, 18, 19 (mecanismo nativo da fonte) |
| `experimentos_waveform/` | classes 06–17, 20 (TRACe/LIST) |
| `scripts/` | PowerShell/CMD do operador e utilitários Python offline (tabela na seção 7) |
| `diag/` | diagnósticos de bancada e análises offline (movidos de `scripts/` em 2026-10-27; tabela na seção 7) |
| `tests/test_offline.py`, `tests/fixtures/` | suíte sem hardware (`docs/testes.md`) |
| `CHANGELOG/vX.Y.md` | histórico por versão (registro; não reescrever) |
| `docs/` | documentação viva (o índice é o próprio site, `docs/index.md`). As análises datadas (`docs/analise-AAAA-MM-DD/`) e `arquivo/analises:docs/superpowers/` estão no branch `arquivo/analises`, fora de `docs/` desde 2026-10-13 (**registro datado**) |
| `resultados/` | saída (gitignored) |
| `logs/` | logs de scripts de diagnóstico e do `preflight_new.py` rodado direto (gitignored) |
| `backups/`, `env/` | cópias locais e virtualenv (gitignored). `.claude/` e `.serena/` são pastas de ferramentas de agente, não fazem parte do projeto |

### Como os experimentos importam `mestre` e `sinais`

`experimentos_*/NN.py` fazem `from mestre import ...` e `from sinais import ...`. Funciona porque o Python põe a pasta do **script de entrada** no início do `sys.path`; todo ponto de entrada que roda um `NN.py` está em `logica/` (`cli.py`, `mestre.py`, `preflight*.py`). Quem roda de fora faz `sys.path.insert(0, ".../logica")`: `tests/test_offline.py` e os utilitários de `scripts/` (ex.: `relatorio_limites_bancada.py:35-36`). `analisar_sessao.py:29-31` faz o mesmo. Os `NN.py` são carregados por caminho (`importlib.util.spec_from_file_location`, `mestre.py:1214-1224`), não como pacote.

## 3. Componentes

### `AmetekMX30` (`ametek_orm.py:147`)
Mapeia métodos Python para SCPI. Pontos centrais:
- **Limites no construtor**: `max_voltage_rms`, `max_peak_v` (limitado a `MAX_SOURCE_PEAK_V = 425`, `:153`, `:206`), `max_current_a`. Setters (`voltage`, `frequency` 45–500 Hz, `current_limit`) e métodos semânticos recusam fora dos limites com `ParameterOutOfBoundsError`.
- **Sincronismo por comando**: `write()` consulta `*ESR?` depois de cada comando (`:391-446`), exceto `TRACe:DATA/DEFine/DELete`. Ver `docs/quirks.md`.
- **Modo simulado** (`simulated=True`): `_simulate_write/_simulate_query` (`:509-594`) mantêm um dicionário interno, inclusive as respostas de readback que `arm()` exige.
- **Estado rastreado em Python**: `_modo_saida`, `_forma_atual`, `_frequencia_alterada`, cache de TRACe (`_last_capture_signature`) — atributos da instância; nova conexão ⇒ estado novo.
- Exceções (`:50-73`): `ParameterOutOfBoundsError` (é `ValueError`), `CommunicationError`, `InstrumentHardwareError`, `FalhaFatalDeInstrumento` (nunca engolir: aborta a bateria).

### `KeysightDSOX4034A` (`oscilloscope_orm.py:70`)
`OscChannel` (subclasse de `pymeasure.instruments.Channel`) mapeia escala, offset, probe, acoplamento. A classe principal configura aquisição, trigger externo e decodifica o bloco IEEE 488.2 de `:WAVeform:DATA?` (`get_waveform`, `:447`).

### `mestre.py`
- **`Config`** (`:697`): dataclass congelada, só dados. Experimentos recebem a config por `self.config`; nunca importam constantes de `mestre`.
- **`Bancada`** (`:942`): `fonte`, `osc`, `config`; context manager (`with Bancada.from_env()`), `shutdown()` desconecta a fonte (que desliga a saída) e fecha o osciloscópio.
- **`ExperimentoBase`** (`:1373`): laço genérico `executar()` (`:2385`). Subclasses: **`ExperimentoNativo`** (`:2663`) e **`ExperimentoWaveform`** (`:2780`).
- Funções de apoio: sorteio (`Sorteio`, `sortear_posicao`, `:765-855`), fatores de extremo (`carregar_fatores_extremo`, `:514`), procedência (`info_do_codigo`, `preparar_pasta_da_sessao`, `:120`, `:181`).

### Ganchos de `ExperimentoBase` (o que uma classe pode sobrescrever)

| Método / atributo | Padrão | Sobrescrito por |
|---|---|---|
| `gerar(t, f0, capture_index, rng)` (abstrato) | — | todas as classes |
| `configurar(capture_index)` (abstrato em Nativo) | — | classes nativas |
| `usar_trace(capture_index)` | `False` (`:2686`) | 05 (nível acima de 20 %) |
| `capturas_padrao` | 1 (`:1397`) | 04, 06–17, 19, 20 (3) |
| `pre_trigger_s` | 0 (`:1387`) | 02, 03, 04 (0,060) |
| `NIVEIS` / `total_niveis()` | `len(NIVEIS)` ou 1 (`:1508`) | 02, 03 (`NIVEIS`), 05 (`total_niveis`) |
| `scope_scale_v()` | `None` (`:2695`) | 05 |
| `tensao_rms_programada()` | `NIVEIS[i] × base` (`:2700`) | 05 não define `NIVEIS` ⇒ `None` |
| `forma_para_bancada()` | limita pico e aplica o limite de bancada (`:2808`) | 08 |
| `limite_pico_bancada_pu()` | `None` (`:2793`) | 08 |
| `parametros_com_disturbio_reduzido()` | `{}` (`:2836`) | 06, 07, 09–14, 16, 17, 20 |
| `excursao_fisica_prevista_v()` | `None` (`:2914`) | 08 |
| `ciclos_excluidos_da_validacao()` | `()` (`:1735`) | 08 |
| `conferir_posicao_do_evento()` | `None` (`:1727`) | 08 |
| `exige_medida_de_pico`, `fracao_teto_pico_medido` | `False`, `1.0` (`:1745-1748`) | 08 (`True`, 0,9) |
| `_preparar_acquisicao_real()` | nada (`:1564`) | Nativo (aplica `scope_scale_v`) |

## 4. Fluxo da bateria física (`Bancada.from_env`, `mestre.py:969-1077`)

1. `validate_bench_configuration()` (`:366`): porta, baud, probe, limites, `ARM_OUTPUT`.
2. Abre a AMETEK (`connect`: `OUTPut:STATe OFF` antes de qualquer outra coisa, `*IDN?` conferido, `ametek_orm.py:313-343`).
3. `configure_safe_baseline` (`:1175`): ~22 comandos, `check_errors()` depois de cada um.
4. Abre o Keysight (`verify_identity`, `initialize_safe`), `garantir_ctrl_c_no_windows()`, configura CH1 (escala = `EUT_MAX_PEAK_V/3`), desliga CH2 (ou configura se `CAPTURE_CURRENT`), `configure_acquisition`, `setup_external_trigger`.
5. `fonte.authorize_output(...)` e `energize_baseline()` — **só** se `require_output` e `ARM_OUTPUT=YES`.
6. `verificar_cadeia_de_medicao()` (`:1329`): fonte mede a base (±5 %) e o CH1 concorda (±10 %), senão `CadeiaDeMedicaoError`.
7. `executar_bateria(scripts)` (`:1095`): por classe, até 3 tentativas para erro de experimento comum; `ERROS_DETERMINISTICOS` (`ParameterOutOfBoundsError`, `ValidacaoFisicaError`, `PicoFisicoExcedidoError`) não são retentados; `CommunicationError` e `FalhaFatalDeInstrumento` abortam tudo; `recuperar_estado_seguro()` entre falhas.
8. `shutdown()` (no `__exit__`): `ABORt`, `OUTPut:STATe OFF` confirmado por leitura (`ametek_orm.py:1830`).

Uma classe isolada (`run <NN>`) usa `Bancada.from_env` + `assegurar_tensao_base()` (`:1231`) + `experimento.executar()` (`cli.py:567-575`).

## 5. Fluxo de uma classe (`ExperimentoBase.executar`, `mestre.py:2385-2660`)

1. `dimensionar_capturas` → `plano_de_capturas`.
2. Bancada: `_indices_viaveis` (pré-validação) pula capturas que não cabem; se nenhuma cabe, `ParameterOutOfBoundsError`.
3. Margem: 8100 pontos; `configure_acquisition(pre_trigger = pre_trigger_s + 20 ms)`.
4. Para cada captura: seed → `rng` → **simulado**: `gerar()`; **bancada**: `_capturar_real()`.
5. Metadata da captura; no físico, `_contexto_da_sessao()` (procedência, `indice_trigger`, escala), `_medir_extremos_fisicos()` (VMAX/VMIN), `inicio_janela`.
6. Ruído AWGN só na janela rotulada (`sinais.ruido_na_janela`, `:2551`).
7. Físico: `_validar_fisicamente`, `_salvar_captura` (atômico, `fsync` do metadata), **depois** `_conferir_extremos_fisicos` (a captura que passou do teto é a evidência e já está gravada).
8. Erro descartável (`ERROS_CAPTURA_DESCARTAVEL = InstrumentHardwareError, TimeoutError, ValueError`, `:693`) descarta só aquela captura. Se **todas** forem perdidas, a classe falha.
9. Fim: `restaurar_forma_e_modo_padrao()` (desfaz CSINe, ACDC, frequência) e `_finalizar_gravacao`.

### `_capturar_real` nativa (`:2733-2777`)
`gerar()` (fonte da verdade da posição) → pré-trigger sorteado (`osc.definir_pre_trigger`) → `fonte.definir_fase_de_disparo` → `configurar()` (STEP/PULSe/CSINe/LIST/ACDC) → `osc.arm()`, `wait_for_armed()` → `fonte.arm()` → `fonte.trigger()` (`*TRG`) → `osc.wait_for_trigger_complete()` → `fonte.wait_transient_complete()` → `_ler_captura`. Classe 05 acima de 20 % de THD usa o ramo TRACe (`program_capture` + `arm_transient`).

### `_capturar_real` waveform (`:2920-2978`)
`gerar()` → `forma_para_bancada()` (limite de pico e de bancada) → `program_capture` → `set_vertical_scale` (headroom 1,25, ou 1,60 se pico > 3 × nominal) → `osc.arm()` → `fonte.arm_transient()` → `fonte.trigger()` → esperas → `_ler_captura`.

## 6. Camadas de segurança (todas independentes)

| Camada | Onde |
|---|---|
| Porta COM10 / 115200 e probe obrigatória, `BASE ≤ EUT_MAX ≤ range`, `ARM_OUTPUT=YES` | `validate_bench_configuration` (`mestre.py:366`), `AmetekMX30.connect` (`:318`) |
| Confirmação digitada, case-sensitive, por comando que energiza | `cli.py:256-263` e `cmd_*` |
| Limites do ORM (`max_voltage_rms`, `max_peak_v`, `max_current_a`) | setters e métodos em `ametek_orm.py` |
| Interlock de software da saída | `authorize_output` / `output_enabled` (`:650-667`) |
| Pré-validação de rms e pico previsto, antes de qualquer SCPI | `avaliar_captura_na_bancada` (`mestre.py:1868`) |
| Extremos medidos (VMAX/VMIN) contra o teto, depois da captura | `_conferir_extremos_fisicos` (`:1767`) |
| Checagem fonte × CH1 antes da primeira classe | `verificar_cadeia_de_medicao` |
| Fila de erros SCPI após cada passo relevante | `check_errors` / `assert_no_errors` (`ametek_orm.py:596-618`) |
| Readback do transiente nativo antes do `INITiate` | `_conferir_transiente_programado` (`:1675`) |
| `ABORt` + `OUTPut:STATe OFF` confirmado ao fechar | `safe_shutdown` (`:1830`) |

## 7. Scripts

| Script | Energiza? | Função |
|---|---|---|
| `START_BENCH.cmd` → `start_bench_windows.ps1` | via CLI | prepara o venv, pergunta probe/tensão/frequência, abre `logica/cli.py` |
| `bench_config.ps1` | — | fonte única das variáveis de ambiente da bancada |
| `setup_windows.ps1` | — | cria/atualiza `env/` e instala `requirements.txt` (aceita Python 3.9–3.12; o numpy fixado exige ≥ 3.11) |
| `run_simulation_windows.ps1` | — | dataset simulado (`-CapturesPerClass`, padrão **1**; `-SnrLevels`, padrão `20,30,40`) |
| `package_windows.ps1` | — | zip `..\tcc-instrumentacao-bancada.zip` sem `env`, `.venv`, `__pycache__`, `resultados`, `logs`, `backups`, `.git` |
| `relatorio_limites_bancada.py` | não | offline: o que cabe a uma tensão/frequência/perfil |
| `recalibrar_extremos.py` | não | offline: recalcula `calibracao_extremos.json`; ao fim do run: `docs/operacao.md` §9 |
| `gerar_tres_versoes.py`, `gerar_ruido_janela.py` | não | offline: regeneram `tres_versoes/` (só sessões do formato 1) e `ruido_janela/` (os dois formatos) |
| `diag_*.py` | **sim** (exceto `diag_nativo_output_off.py`) | diagnósticos; ver `docs/diagnostico.md` |
