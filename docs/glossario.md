# Glossário

Termos usados em toda a documentação e no código. Quando um termo tem dois nomes no código, os dois aparecem.

| Termo | Significado exato |
|---|---|
| **pu** | por unidade do **pico nominal** `tensao_base_rms × √2` (127 V rms → 179,6 V = 1 pu). Todas as formas de `gerar()` e todos os `.npz` (`tensao_pu`) estão em pu. |
| **Tensão base** | `BASE_VOLTAGE_RMS`, Vrms **fase-neutro** do teste (`logica/mestre.py:350`). Perguntada uma vez pelo `START_BENCH`. |
| **f0** | frequência da rede do teste, `GRID_FREQUENCY_HZ` (`mestre.py:293`; padrão 60 Hz; o `START_BENCH` pergunta). |
| **Janela nominal / janela rotulada** | os 200 ms = 6000 amostras a 30 kSa/s que `gerar()` produz e que todo leitor usa (`POINTS`, `DURATION_S`, `FS_HZ`, `mestre.py:292-295`). Os dois nomes significam a mesma coisa. |
| **Margem** | folga só das capturas **físicas**: 20 ms antes + 50 ms depois da janela nominal (`MARGEM_ANTES_S`/`MARGEM_DEPOIS_S`, `mestre.py:2023-2024`) = 600 + 6000 + 1500 = **8100 amostras** (o "registro bruto"). |
| **Captura** | um registro (uma linha do `metadata/*.jsonl`, um `id_captura` como `02-0001`). |
| **Classe** | uma das 20 classes de distúrbio; `id` string de 2 dígitos (`"02"`) e `nome` (`"SAG"`). Um arquivo `experimentos_*/NN.py` por classe. |
| **Nível** | valor discreto de parâmetro de uma classe (`NIVEIS` das 02/03, `NIVEIS_THD` da 05). |
| **`indice_global` / `capture_index`** | `indice_global` (0, 1, 2, …) entra na seed e no `id_captura` (`NN-0001` = índice 0). `capture_index` escolhe o nível: igual ao `indice_global`, ou `indice_global // capturas_por_nível` quando `set capturas` agrupa por nível (`mestre.py:1542-1550`). Vai ao metadata como `nivel_indice` (no **simulado** sempre 0, `mestre.py:2523`). |
| **Plano** | lista `(indice_global, capture_index)` de uma classe antes da pré-validação. |
| **Nativa / Waveform** | mecanismo físico da classe: **nativa** usa um recurso da AMETEK (STEP, PULSe, CSINusoid, `LIST:FREQuency`, ACDC); **waveform** grava TRACes e toca uma `LIST` (TRACe/LIST). Ver `docs/classes.md`. |
| **TRACe / LIST** | TRACe = forma de onda de 1024 pontos (1 ciclo) gravada na memória não volátil da fonte; LIST = sequência de passos (um TRACe por ciclo da janela) tocada a cada `*TRG`. |
| **Baseline** | estado seguro programado por `configure_safe_baseline` (`ametek_orm.py:1175`): saída desligada, senoide, modos FIXed, 0 V, trigger por barramento. |
| **BOT / Trigger Out** | pulso "Beginning Of Transient" que a AMETEK emite no `*TRG` e que vai por cabo BNC ao EXT Trigger do osciloscópio. |
| **Sorteio** | sorteio de início, duração e fase em `gerar()` (`Config.sorteio_posicao`, padrão ligado). Não confundir com sorteio de parâmetros (`rng.uniform`) que as classes já faziam. |
| **Perfil** | conjunto de faixas do dataset: `norma`, `literatura` (padrão), `fronteira` (`docs/perfis.md`). |
| **Seed da captura** | `BASE_SEED + int(id) × 1 000 000 + indice_global` (`mestre.py:1536-1540`). Mesma seed ⇒ mesmas formas e parâmetros. |
| **k / `fator_disturbio_bancada` / limite de bancada** | fração (0,25 a 1) a que a captura **física** reduz só o distúrbio de uma classe waveform (`senoide + k·(gerar() − senoide)`) para o extremo previsto caber no teto. `gerar()` e o dataset simulado não mudam. |
| **Teto** | `max_peak_v` da fonte (415,8 V com o `START_BENCH`; no máximo 425 V, `ametek_orm.py:153`) e `max_voltage_rms` (300 V). A classe 08 usa 0,9 × `max_peak_v` (374,2 V). |
| **Extremo previsto** | pico programado × fator de extremo × `MARGEM_FATOR_EXTREMO` (1,10). Se passar do teto a captura é **pulada antes de qualquer SCPI**. |
| **Fator de extremo** | extremo medido pelo osciloscópio ÷ pico programado, por classe e por **condição** (tensão ±2 %, frequência ±0,5 Hz), em `logica/calibracao_extremos.json`. |
| **Condição** | par (tensão base, frequência), ex. `127V_60Hz`. |
| **Pré-validação** | avaliação de cada captura **antes** de programar a fonte (`avaliar_captura_na_bancada`, `mestre.py:1868`). |
| **Validação física** | comparação **depois** da captura entre o medido e o esperado (envelope, THD, crista; `_validar_fisicamente`, `mestre.py:1660`). Captura reprovada é gravada com `validacao_fisica.ok=false`. |
| **Cadeia de medição** | checagem inicial fonte × CH1 (`verificar_cadeia_de_medicao`, `mestre.py:1329`). |
| **Modelo / programada / medida** | as três versões de uma captura (`docs/tres_versoes.md`). |
| **Sessão** | pasta `resultados/sessao_<timestamp>[_runNN]/` criada pela CLI a **cada** `run`/`run all` (`cli.py:199-218`). |
| **Simulado / bancada** | `BENCH_MODE=0` (nenhum instrumento aberto, `gerar()` direto) / `BENCH_MODE=1` (instrumentos reais). |
| **EUT** | equipamento sob teste ligado à saída da fonte. |
| **E-stop** | botão de emergência da bancada. |
| **Rev. 5.53** | firmware da MX30 da bancada. O manual SCPI é de outra revisão; as divergências estão em `docs/quirks.md`. |
| **H-NATIVO, H-REF10** | nomes históricos de achados: H-NATIVO = as classes nativas aplicavam valores errados em silêncio (causa real: writes em rajada perdidos); H-REF10 = o "atraso" de 20/100 ms era a divisão de referência horizontal do osciloscópio. |
| **`-dirty`** | sufixo de `git describe` quando há alteração **rastreada** não commitada. |
