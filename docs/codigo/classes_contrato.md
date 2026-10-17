# Contrato das classes de experimento

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Lido (as 20 classes por `ast`; `08.py` e `18.py` por inteiro) em 2026-10-16, `main` em `fa82f49`. As fichas de cada classe, escritas na etapa seguinte do site, partem de {doc}`../classes`.

**Pergunta:** o que um arquivo `experimentos_*/NN.py` precisa ter e quais ganchos pode sobrescrever? **Resposta:** um arquivo `NN.py` com **uma** classe chamada `Experimento` que herda `ExperimentoNativo` (implementa `gerar` e `configurar`) ou `ExperimentoWaveform` (só `gerar`), com `id` e `nome`; o resto são **ganchos opcionais** que a classe-base chama. Exatamente um arquivo por id de 01 a 20 em **uma** das duas pastas.

## 1. Como a classe é carregada

`Bancada._carregar_classe_experimento` ([mestre.py:1381](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1381)) carrega o arquivo **por caminho** com `importlib.util.spec_from_file_location` (nome de módulo `experimento_<pasta>_<NN>`), executa o módulo e pega `Experimento`; **não é pacote**. Os arquivos fazem `from mestre import ...`, o que só funciona porque a pasta do script de entrada (`logica/`) está em `sys.path`; `tests/` e `scripts/` inserem `logica` à mão. `mestre._experiment_scripts` ([mestre.py:3195](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L3195)) exige exatamente um `NN.py` por id: uma 21.ª classe exige mexer em `mestre.py`, em `cli.py` (`TOTAL_CLASSES`) e nos testes.

## 2. As 20 classes, lidas do código

| Classe | Arquivo | Base | `capturas_padrao` | `pre_trigger_s` | Métodos que a classe define |
|---|---|---|---|---|---|
| 01 NORMAL | `experimentos_nativos/01.py` | `ExperimentoNativo` | 1 (herdado) | 0 (herdado) | `gerar`, `configurar` |
| 02 SAG | `experimentos_nativos/02.py` | `ExperimentoNativo` | 1 (herdado) | 0.06 | `NIVEIS`, `gerar`, `configurar` |
| 03 SWELL | `experimentos_nativos/03.py` | `ExperimentoNativo` | 1 (herdado) | 0.06 | `NIVEIS`, `gerar`, `configurar` |
| 04 INTERRUPTION | `experimentos_nativos/04.py` | `ExperimentoNativo` | 3 | 0.06 | `gerar`, `configurar` |
| 05 HARMONICS | `experimentos_nativos/05.py` | `ExperimentoNativo` | 1 (herdado) | 0 (herdado) | `NIVEIS_THD`, `total_niveis`, `gerar`, `configurar`, `usar_trace`, `scope_scale_v` |
| 06 FLICKER | `experimentos_waveform/06.py` | `ExperimentoWaveform` | 3 | 0 (herdado) | `gerar`, `parametros_com_disturbio_reduzido` |
| 07 NOTCH | `experimentos_waveform/07.py` | `ExperimentoWaveform` | 3 | 0 (herdado) | `gerar`, `parametros_com_disturbio_reduzido` |
| 08 TRANSIENT | `experimentos_waveform/08.py` | `ExperimentoWaveform` | 3 | 0 (herdado) | `limite_pico_bancada_pu`, `_indices_impulso`, `gerar`, `forma_para_bancada`, `excursao_fisica_prevista_v`, `ciclos_excluidos_da_validacao`, `conferir_posicao_do_evento` |
| 09 OSCILLATORY_TRANSIENT | `experimentos_waveform/09.py` | `ExperimentoWaveform` | 3 | 0 (herdado) | `gerar`, `parametros_com_disturbio_reduzido` |
| 10 SAG_HARMONICS | `experimentos_waveform/10.py` | `ExperimentoWaveform` | 3 | 0 (herdado) | `gerar`, `parametros_com_disturbio_reduzido` |
| 11 SAG_FLICKER | `experimentos_waveform/11.py` | `ExperimentoWaveform` | 3 | 0 (herdado) | `gerar`, `parametros_com_disturbio_reduzido` |
| 12 SAG_OSCILLATORY_TRANSIENT | `experimentos_waveform/12.py` | `ExperimentoWaveform` | 3 | 0 (herdado) | `gerar`, `parametros_com_disturbio_reduzido` |
| 13 SWELL_HARMONICS | `experimentos_waveform/13.py` | `ExperimentoWaveform` | 3 | 0 (herdado) | `gerar`, `parametros_com_disturbio_reduzido` |
| 14 SWELL_OSCILLATORY_TRANSIENT | `experimentos_waveform/14.py` | `ExperimentoWaveform` | 3 | 0 (herdado) | `gerar`, `parametros_com_disturbio_reduzido` |
| 15 HARMONICS_FLICKER | `experimentos_waveform/15.py` | `ExperimentoWaveform` | 3 | 0 (herdado) | `gerar` |
| 16 INTERRUPTION_HARMONICS | `experimentos_waveform/16.py` | `ExperimentoWaveform` | 3 | 0 (herdado) | `gerar`, `parametros_com_disturbio_reduzido` |
| 17 NOTCH_OSCILLATORY_TRANSIENT | `experimentos_waveform/17.py` | `ExperimentoWaveform` | 3 | 0 (herdado) | `gerar`, `parametros_com_disturbio_reduzido` |
| 18 FREQUENCY_DRIFT | `experimentos_nativos/18.py` | `ExperimentoNativo` | 1 (herdado) | 0 (herdado) | `extremos_hz`, `gerar`, `configurar` |
| 19 DC_OFFSET | `experimentos_nativos/19.py` | `ExperimentoNativo` | 3 | 0 (herdado) | `gerar`, `configurar` |
| 20 INTERHARMONICS | `experimentos_waveform/20.py` | `ExperimentoWaveform` | 3 | 0 (herdado) | `gerar`, `parametros_com_disturbio_reduzido` |

(`capturas_padrao` é o número de capturas por nível na bancada; "1 (herdado)" é o padrão de `ExperimentoBase`; 3 nas classes que **sorteiam** parâmetros, para uma captura não mostrar uma única realização.)

## 3. Os ganchos

| Gancho | Quem o chama | Quem o sobrescreve |
|---|---|---|
| `gerar(t, f0, capture_index, rng)` | `executar` (simulado), `_capturar_real` (waveform e nativas por TRACe), validação física, `analisar_sessao` | todas |
| `configurar(capture_index)` | `ExperimentoNativo._capturar_real` | as nativas (01 a 05, 18, 19) |
| `usar_trace(capture_index)` | `ExperimentoNativo` | 05 (nível de 30 % vai por TRACe) |
| `scope_scale_v()` | `_preparar_acquisicao_real` | 05 |
| `NIVEIS` / `NIVEIS_THD` / `total_niveis` | `dimensionar_capturas`, `tensao_rms_programada` | 02, 03, 05 |
| `capturas_padrao`, `pre_trigger_s` | `Config.capturas`, `configure_acquisition` | ver a tabela |
| `parametros_com_disturbio_reduzido(parametros, fracao)` | `_limitar_disturbio_para_bancada` | 06, 07, 09 a 14, 16, 17, 20 (**não** a 15) |
| `forma_para_bancada`, `limite_pico_bancada_pu`, `excursao_fisica_prevista_v` | `_capturar_real` (waveform), pré-validação | só a 08 |
| `ciclos_excluidos_da_validacao`, `conferir_posicao_do_evento`, `exige_medida_de_pico`, `fracao_teto_pico_medido` | `_validar_fisicamente`, `_conferir_extremos_fisicos` | só a 08 |
| `sortear(rng, f0, **opcoes)` | dentro de `gerar()` | quase todas (ver {doc}`perfis`) |

## 4. Acoplamentos por classe ("se mudar isto, aquilo quebra")

| Classe | Se mudar... | ...quebra |
|---|---|---|
| 04, 19 | `seed_da_captura` ([mestre.py:1703](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1703)) ou o id da classe | `configurar()` reproduz a seed **à mão** ([04.py:34](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/04.py#L34), [19.py:32](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/experimentos_nativos/19.py#L32)) e deixa de concordar com `gerar()`; só vale com `capture_index == indice_global` |
| 02, 03 | `INICIO_S`/`DURACAO_S` ou `pre_trigger_s` | `forma_programada_nativa` usa os dois via `getattr`, e `fase_de_disparo_graus` usa `pre_trigger_s` |
| 05 | `TETO_CSINE` ou os níveis | `usar_trace` troca o mecanismo; nível acima de 20 % passa a gravar a Flash (entra na estimativa de gravações) |
| 07, 17 | o número de chamadas ao `rng` por ciclo em `aplicar_entalhes_continuos` | todas as formas da seed mudam (fixtures) |
| 08 | `_indices_impulso` ou as constantes | `forma_para_bancada`, `ciclos_excluidos_da_validacao`, `conferir_posicao_do_evento` e `gerar()` chamam a mesma função; a calibração do sobressinal depende do ponto de partida |
| 10 a 16 | a ordem das chamadas a `perfis.composto` | muda o `rng` e o dataset |
| 18 | `DESVIO_HZ` | `gerar()` e `configurar()` usam `extremos_hz()`; `forma_programada_nativa` lê `start_hz`/`end_hz` do metadata |

## 5. A classe 08, o único arquivo com lógica própria de bancada

A 08 é a única classe que **não** usa a tabela de fatores de extremo: `forma_para_bancada` limita **só a amplitude do impulso** (a base fica em 1 pu) para que pico e vale previstos caibam em `0,9 · max_peak_v`, com `SOBRESSINAL_DO_DEGRAU = 0,55` e `SUBSINAL_DO_DEGRAU = 0,70` (v1.14: a 50 Hz o impulso parte do cruzamento por zero e o sobressinal chegou a 0,457; 0,55 mantém a margem de cerca de 1,2). O impulso vai para o meio do ciclo se cair a menos de 1 ms (30 amostras) de uma fronteira (a 50 Hz, 90 ms em vez de 80 ms); `conferir_posicao_do_evento` exige o maior desvio da senoide a até 10 amostras do início previsto e reprova "impulso não encontrado" abaixo de 25 % da amplitude. Com `sorteio_posicao` desligado, o 80 ms de sempre (para reproduzir 07/10).

```{literalinclude} ../../experimentos_waveform/08.py
:pyobject: Experimento._indices_impulso
:language: python
:caption: experimentos_waveform/08.py, Experimento._indices_impulso
```

## 6. Armadilhas

1. `gerar()` é a fonte da verdade da posição: na bancada, `_capturar_real` chama `gerar()` e **reproduz** o que ele sorteou no osciloscópio (pré-trigger) e na fonte (fase de disparo, largura do PULSe).
2. `ExperimentoNativo._duracao_sorteada_s` é posto por `_capturar_real` antes de `configurar()`: `configurar()` chamado fora dele usa a duração legada.
3. Mudar o que `gerar()` produz para uma seed exige **autorização registrada em `AGENTS.md` antes**, fixtures byte a byte e declaração no CHANGELOG (regra do projeto).
4. `ExperimentoBase.capturas_padrao` tem um comentário que lista só as classes do padrão antigo; vale o atributo de cada `Experimento`.
