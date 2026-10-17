# O que acontece numa captura TRACe

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Percurso lido no código em 2026-10-16 (`main` em `fa82f49`). {bdg-warning}`NÃO VERIFICADO` na bancada com o código da v1.15 (P-01). O exemplo é uma classe de forma de onda (06 a 17, 20); as nativas diferem em `_capturar_real` e estão em {doc}`../scpi/sequencias`.

**Pergunta:** o que acontece, em ordem, com **uma** captura de uma classe de TRACe, do sorteio da seed ao `.npz`? **Resposta:** `ExperimentoBase.executar` dá à captura uma seed e um id; `ExperimentoWaveform._capturar_real` gera a forma (`gerar()`), a adapta ao que a bancada pode programar (limite de bancada), manda a fonte programar as TRACes e a lista, ajusta a escala vertical, arma osciloscópio e fonte nessa ordem, dispara, espera os dois lados e lê o registro; de volta a `executar`, o código monta o metadata, mede os extremos, valida fisicamente, **grava** a captura e só então confere o teto.

```{mermaid}
sequenceDiagram
    participant E as ExperimentoBase.executar
    participant W as ExperimentoWaveform._capturar_real
    participant F as AmetekMX30
    participant O as KeysightDSOX4034A
    participant A as ArquivoDaClasse
    E->>E: seed_da_captura, rng, capture_id
    E->>W: _capturar_real(capture_index, t, rng)
    W->>W: gerar() → voltage_pu, parâmetros
    W->>W: forma_para_bancada (limite de pico, limite do distúrbio)
    W->>F: program_capture(forma, base, f0, offset)
    F-->>W: ultima_programacao (ProgramacaoCaptura)
    W->>W: _registrar_versoes (modelo, programada)
    W->>O: set_vertical_scale(max(pico·headroom, extremo previsto))
    W->>O: arm(), wait_for_armed()
    W->>F: arm_transient(), trigger()
    W->>O: wait_for_trigger_complete(5 s)
    W->>F: wait_transient_complete(5 s)
    W->>O: get_waveform(1) → (tempo, tensão)
    W->>F: ler_trace(...) se set diagnostico retrieve
    W-->>E: (tempo, tensão, corrente, parâmetros)
    E->>E: _validar_captura, metadata, _contexto_da_sessao
    E->>O: medir_extremos(1) → VMAX, VMIN
    E->>E: ruído na janela, pre_trigger_desvio_amostras
    E->>E: _validar_fisicamente
    E->>A: _salvar_captura (spool atômico)
    E->>E: _conferir_extremos_fisicos (PicoFisicoExcedidoError se acima do teto)
```

## 1. Antes da primeira captura da classe

`executar` ([mestre.py:2578-2863](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2578-L2863)) primeiro: `dimensionar_capturas` ([mestre.py:1684](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1684)) e `plano_de_capturas` ([mestre.py:1709](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1709)) montam a lista `(indice_global, capture_index)`; na bancada, `_indices_viaveis` ([mestre.py:2123](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2123)) a poda com `avaliar_captura_na_bancada` **antes de qualquer SCPI**; `_calcular_margem` ([mestre.py:2315](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2315)) dá 600 + 6000 + 1500 = 8100 amostras; `osc.configure_acquisition(pre_trigger = pre_trigger_s + margem_antes)` ([oscilloscope_orm.py:209](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L209)); `_iniciar_gravacao_incremental` abre o bloco do perfil no `ArquivoDaClasse`.

## 2. Passo a passo da captura

1. **Seed, rng, id.** `seed_da_captura(indice_global) = base_seed + int(id)·1 000 000 + indice_global` ([mestre.py:1703](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1703)); `rng = default_rng(seed)`; `capture_id = "NN-0001"` (índice global + 1). `_pre_trigger_atual_s` e `_versoes_atuais` são zerados.
2. **`gerar()`** produz as 6000 amostras em pu do pico nominal e os parâmetros (incluindo `inicio_disturbio_s`, `duracao_s` e `fase_graus` sorteados). A forma inválida (shape diferente, NaN) levanta `RuntimeError`: bug de código, **não** é descartável.
3. **`forma_para_bancada`** ([mestre.py:3014](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3014)): `_limitar_pico_da_forma` (escala a forma inteira se passa de `limite_pico_bancada_pu`, só a 08 usa) e `_limitar_disturbio_para_bancada` ([mestre.py:3052](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3052)), a bisseção (40 passos) do maior `k` que cabe no teto: `forma = senoide + k·(gerar() − senoide)`; `k < LIMITE_BANCADA_FRACAO_MINIMA` (0,25) devolve a forma do modelo e deixa a pré-validação pular. Os parâmetros ganham `fator_disturbio_bancada`, `pico_programado_modelo_v` e `extremo_previsto_modelo_v`.
4. **`program_capture`** ([ametek_orm.py:1511-1705](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1511-L1705)): sequência completa em {doc}`../scpi/sequencias` §7. Em palavras: `montar_programacao` (pura) → `ABORt`, `*CLS`, modos `FIXed`, `SOURce:MODE`, frequência, forma senoide, tensão (e offset, se houver) → cache (assinatura = bytes da forma + nomes + tensão + frequência + offset; reconfirma em `TRACe:CATalog?`) → `TRACe:DEFine` dos nomes que faltam (3 s cada) → `TRACe:DATA` de cada ciclo (1 s de espera e `*CLS` depois de cada, **sem consultar a fonte**) → `SOURce:LIST:*` com `:POINts?` imediato → modos de lista e de trigger → religa a saída se o `ABORt` a derrubou.
5. **Versões.** `_registrar_versoes` guarda o modelo e a programada (`ProgramacaoCaptura.programada_pu()`); falhar aqui nunca derruba a captura (só a programada deixa de ser gravada, com aviso uma vez por classe).
6. **Escala vertical.** `programmed_peak_v = max(pico esperado, last_programmed_peak_v, excursão prevista)`; `headroom = 1,60` se o pico passa de 3× o nominal, senão `1,25`; `set_vertical_scale(1, max(pico·headroom, extremo previsto, 0,1·base))`. A escala também cobre o extremo previsto pela calibração (v1.13).
7. **Armar nessa ordem.** `osc.arm()`, `osc.wait_for_armed()`, `fonte.arm_transient()` (espera `IDLE`, **nove** leituras de volta, `*WAI`, `INITiate:IMMediate`, espera `ARM`/`WTRIG`), `fonte.trigger()` (`*TRG`).
8. **Esperar os dois lados.** `osc.wait_for_trigger_complete(5 s)` (`:TER?` = 1 **e** bit RUN apagado) e `fonte.wait_transient_complete(5 s)` (`IDLE` e fila limpa).
9. **Ler.** `_ler_captura` → `osc.get_waveform` (preamble, bytes, validações, reamostra a 30 kSa/s); a tensão sai em pu (`÷ base·√2`). Com `set diagnostico retrieve`, `_ler_traces_de_diagnostico` lê as TRACes **depois** da captura, com a espera mínima de 2 s (quirk A2).

## 3. De volta a `executar`

1. `_validar_captura`: shape, finitude e eixo de tempo a 30 kSa/s. Falha aqui (`ValueError`) é descartável.
2. **Erros descartáveis.** Dentro do `try`, `ERROS_CAPTURA_DESCARTAVEL` (`InstrumentHardwareError`, `TimeoutError`, `ValueError`) descartam **só esta captura**: `capturas_descartadas`, nada é gravado, a classe segue.
3. **Metadata.** `id_captura`, `classe`, `seed`, `simulado`, `perfil`, `sorteio_posicao`, os sorteados (`inicio_disturbio_s`, `duracao_s`, `fase_graus`, movidos de `parametros`), `fs_hz`, `pontos`, `parametros`, `nivel_indice`; mais `_contexto_da_sessao` ([mestre.py:1735](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1735)): f0, tensão base, probe, pré-trigger efetivo, margens, `base_seed`, `versao_codigo`, `git_commit`, `git_sujo`, SHA-256 da calibração, IDN dos dois instrumentos, `escritas_trace_na_conexao`, `indice_trigger`, `escala_vertical_v_div`.
4. `_gravar_diagnostico_trace`, depois `_medir_extremos_fisicos` ([mestre.py:1945](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1945)): `pico_medido_v`, `vale_medido_v`, `teto_extremos_v`; **nunca levanta** (a decisão é de `_conferir_extremos_fisicos`). Do `_avaliacoes_bancada` vêm `extremo_previsto_v` e `pico_programado_v`.
5. `margem_amostras_antes/depois`, `amostras_totais`, `inicio_janela` (`_inicio_janela_para_metadata`, a mesma conta de `sinais.janela_nominal`) e `inicio_janela_ajustado`.
6. **Ruído** (`ruido_na_janela`) só na janela rotulada, com `snr_medido_db`, `snr_bancada_db` e `snr_efetivo_db`; e `pre_trigger_desvio_amostras` (aviso se o trigger caiu a mais de 2 amostras do previsto).
7. **`_validar_fisicamente`** ([mestre.py:1827](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1827)): `comparar_fisicamente` contra a forma realmente programada (`_forma_programada_pu`), com `fator_crista` e, na 08, `conferir_posicao_do_evento`. Resultado em `validacao_fisica`; reprovada = `capturas_invalidas` (a captura é **gravada mesmo assim**, com `ok=false`).
8. **`_salvar_captura`** ([mestre.py:2439](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2439)): entrega ao `ArquivoDaClasse.adicionar` (spool atômico) com `modelo`, `programada` e `origem_programada`; o metadata ganha `arquivo_classe`, `perfil`, `indice_no_arquivo`, `tres_versoes`.
9. **`_conferir_extremos_fisicos`** ([mestre.py:1962](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1962)) **depois** de gravar: acima do teto, `PicoFisicoExcedidoError`, a classe para sem retry e o operador confere o painel.

## 4. Quando uma captura "falha": o que acontece com cada tipo

| O que acontece | Efeito |
|---|---|
| erro SCPI da fonte, divergência de readback, timeout de trigger, `ValueError` | captura **descartada**; a classe segue |
| validação física reprova | captura **gravada** e marcada `ok=false`; a classe segue |
| extremo medido acima do teto | captura **gravada**; `PicoFisicoExcedidoError`; classe para sem retry |
| `RuntimeError` (forma inválida de `gerar()`) | propaga: bug de código |
| `CommunicationError`, `FalhaFatalDeInstrumento` | propaga até `executar_bateria`: aborta tudo |
| todas as capturas da classe perdidas | a classe levanta ao fim (`ValidacaoFisicaError` ou `InstrumentHardwareError`) |

Em qualquer exceção, `executar` fecha a gravação com `_finalizar_gravacao(parcial=True)`: o que já foi para o disco fica (metadata **parcial**).

## 5. Por que é assim

- **Armar o osciloscópio antes da fonte**: o BOT sai no `*TRG`; é a ordem de `_capturar_real` (a razão é inferência do código).
- **Pré-validação antes de qualquer SCPI** porque a 03 a 220 V pede 1,4 pu = 308 Vrms (impossível) e o código antigo só descobria na 21.ª captura, três vezes seguidas, terminando sem arquivo nenhum (docstring de `_indices_viaveis`).
- **Gravar antes de conferir o teto**: a captura que passou do teto é a evidência (v1.12).
- **`TRACe:DATA` sem consulta**: a fonte ficava muda até ser religada (A2). **Nove leituras** no `arm_transient`: um comando que não "pegou" aparece com o nome do comando.
