# O que acontece num run

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Percurso lido no código em 2026-10-16 (`main` em `fa82f49`). {bdg-warning}`NÃO VERIFICADO` na bancada com o código da v1.15 (P-01).

**Pergunta:** o que acontece, em ordem, do momento em que o operador roda `START_BENCH.cmd` até os arquivos da sessão estarem no disco? **Resposta:** o script prepara o ambiente e pergunta probe, tensão e frequência; a CLI pede a confirmação digitada, cria uma pasta nova, abre os dois instrumentos (fonte em 0 V, saída religada só depois de identificada e configurada), confere a cadeia de medição, roda cada classe isolada (pré-validação, captura, validação física, gravação atômica) e, no fim, desliga a saída e roda os ganchos opcionais.

```{mermaid}
flowchart TD
    A["START_BENCH.cmd<br/>start_bench_windows.ps1"] --> B["logica/cli.py<br/>SessaoCLI.loop (bancada>)"]
    B --> C["run all | run lista | run NN"]
    C --> D["SessaoCLI.confirmar<br/>(string digitada, case-sensitive)"]
    D --> E["_garantir_pasta_sessao<br/>sessao.log, scpi_transcricao.log, sessao.json"]
    E --> F["autorizar_saida(True)"]
    F --> G["Bancada.from_env"]
    G --> H["executar_bateria<br/>(ou executar_classe_nos_perfis)"]
    H --> I["_executar_classe_no_perfil<br/>até 3 tentativas"]
    I --> J["ExperimentoBase.executar"]
    J --> K["por captura: ver percurso da captura"]
    H --> L["autorizar_saida(False) + Bancada.shutdown"]
    L --> M["_fim_da_sessao<br/>recalibração / HTML"]
```

## 1. Do `.cmd` à CLI

1. `scripts/START_BENCH.cmd` chama `start_bench_windows.ps1` sem perfil de usuário e com `ExecutionPolicy Bypass`.
2. O `.ps1` roda `setup_windows.ps1` (cria o `env\` e instala `requirements.txt`), carrega `bench_config.ps1` (`BENCH_MODE=1`, `ARM_OUTPUT=NO`, `AMETEK_CLEAR_USER_WAVEFORMS=1`), pergunta o **fator exato da probe** de tensão, a tensão e a frequência, recusa tensão acima de 270 V, **sobrescreve** `SOURCE_VOLTAGE_RANGE_RMS`, `EUT_MAX_VOLTAGE_RMS` (300) e `EUT_MAX_PEAK_V` (415,8) e executa `logica/cli.py`.
3. Ao importar `mestre`, as variáveis de ambiente viram constantes; mudar a tensão exige reiniciar o processo.
4. `SessaoCLI.loop` ([cli.py:962](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L962)) despacha por `COMANDOS`; `set` só altera globais de `mestre` para o próximo `run`.

## 2. De `run` à bancada aberta

1. `cmd_run` ([cli.py:717](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L717)) escolhe `_run_all`, `_run_lista` ou `_run_uma`. `_run_lista` valida a lista antes de pedir qualquer confirmação.
2. `confirmar` ([cli.py:345](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L345)): imprime o aviso (com a estimativa de capturas e de gravações de TRACe, e o aviso da trava de cerca de 280) e só aceita a string exata (`EXECUTAR-20-CLASSES`, `EXECUTAR-CLASSES-<lista>`, `EXECUTAR-CLASSE-NN`).
3. `_garantir_pasta_sessao`: pasta **nova** (`sessao_<ts>`, depois `_run02`...), `configurar_log_de_sessao`, `preparar_pasta_da_sessao` (copia a calibração em uso, grava `sessao.json`, avisa em destaque se a árvore git está suja).
4. `autorizar_saida(True)`: `ARM_OUTPUT=YES` no ambiente e em `mestre` e `preflight_new`.
5. `Bancada.from_env(require_output=True)` ([mestre.py:1031](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1031)): `validate_bench_configuration`; `AmetekMX30(...)` (o construtor chama `connect`, que manda `OUTPut:STATe OFF` **antes** do `*IDN?`); `configure_safe_baseline` (22 comandos conferidos um a um, tensão em 0 V); `clear_all_traces` se `AMETEK_CLEAR_USER_WAVEFORMS` (só com a saída desligada); Keysight (`VISAAdapter`, `verify_identity`, `initialize_safe`); `garantir_ctrl_c_no_windows` (**depois** de abrir os dois: o NI-VISA instala o tratador ao abrir); canal 1; aquisição; trigger externo; `authorize_output`; `energize_baseline`; `verificar_cadeia_de_medicao` ([mestre.py:1496](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1496)).
6. `_run_uma` ainda chama `assegurar_tensao_base` (um STEP real até a base) porque uma classe isolada não tem a 01 antes.

## 3. A bateria

`executar_bateria` ([mestre.py:1231](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1231)) percorre as classes; para cada uma e cada perfil de `perfis.plano_de_perfis`:

- troca `self.config` pelo `Config` do perfil (com `perfis_espelho` quando a classe é independente do perfil) e chama `_executar_classe_no_perfil`, que tenta até 3 vezes. `recuperar_estado_seguro` (`ABORt`, modos `FIXed`, forma e modo padrão, tensão base, `OUTPUT` religada se caiu) entre as tentativas.
- **`CommunicationError` e `FalhaFatalDeInstrumento`** propagam: a bateria inteira aborta, sem retry. **`ERROS_DETERMINISTICOS`** não são retentados. Qualquer outra `Exception` é retentada.
- ao fim restaura `self.config` e solta o acumulador da classe.

## 4. Uma classe: `ExperimentoBase.executar`

Detalhado em {doc}`percurso-captura-trace`. Resumo: `dimensionar_capturas` → `plano_de_capturas` → `_indices_viaveis` → `_calcular_margem` (600 + 6000 + 1500 = 8100 amostras) → `osc.configure_acquisition` → `_iniciar_gravacao_incremental` → laço de capturas → `restaurar_forma_e_modo_padrao` → `_finalizar_gravacao` → se **todas** as capturas foram perdidas, a classe levanta (`ValidacaoFisicaError` ou `InstrumentHardwareError`).

## 5. O fim

1. `autorizar_saida(False)` no `finally`; `Bancada.__exit__` → `shutdown` → `fonte.disconnect()` (`safe_shutdown`: `ABORt`, `OUTPut:STATe OFF`, leitura) e `osc.close()`.
2. Resumo (`Resumo final: N/20 classes OK`) e `ultimo_resultado`.
3. `_fim_da_sessao`: recalibração (se `set recalibracao on`), depois HTML (se `set html on`); só depois de a saída estar OFF e a conexão fechada. Se a bateria abortou por infraestrutura, nada disso roda.
4. O operador confirma `OUTPUT OFF` no painel (`START_BENCH.cmd`).

## 6. Onde estão os arquivos

`resultados\sessao_<ts>[_runNN]\`: `sessao.log`, `scpi_transcricao.log`, `sessao.json`, `calibracao_extremos.json` (cópia), `NN_classe.npz`, `snr_XXdb/`, `corrente/` (se `CAPTURE_CURRENT`), `metadata/NN_classe.jsonl` (e `.json`), `diagnostico_trace/` (com `set diagnostico retrieve`), `parcial/` (só se o processo morreu), e, com `set html on`, `sem_margem/` e `relatorio_<sessao>.html`. Nas falhas de infraestrutura, o que se entrega a quem diagnostica é `sessao.log` e `scpi_transcricao.log` da pasta mais recente (ou o `logs\preflight_new-*.log` para `comm`, `trigger`, `lowvoltage`, `native`).
