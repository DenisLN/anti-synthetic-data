# Três versões de cada captura: o que mudou (2026-10-12)

Formato e uso: `docs/tres_versoes.md`. Nada foi commitado; nenhum hardware tocado. Linhas de código citadas são da árvore de trabalho de hoje (não commitada).

## 1. Função pura da forma programada

- `AmetekMX30.montar_programacao(waveform_pu, *, base_voltage_rms, frequency_hz, dc_offset_pu=0)` (`logica/ametek_orm.py:1322`, classmethod, sem SCPI nem estado) devolve uma `ProgramacaoCaptura` (`ametek_orm.py:93`): ciclos, `traces` (ciclos x 1024, já em `%.8g`), `list_voltages_rms`, pico reconstruído. É o corpo do laço que estava dentro de `program_capture()`, movido sem mudar a conta; os `ValueError` (6000 amostras finitas, ciclos inteiros) saem dela.
- `program_capture()` (`ametek_orm.py:1404`) chama `montar_programacao` (`:1424`) e envia `programacao.comando_trace(i)` (`:1503`) e `formatar_valores(list_voltages)` (`:1519`); guarda o objeto em `ultima_programacao` (`:1588`). O formato `%.8g` tem uma só definição (`formatar_valores`, `:80`).
- `ProgramacaoCaptura.programada_pu()` (`:120`) volta à grade de 30 kSa/s: cada TRACe de 1024 pontos escalada ao rms do `LIST:VOLTage` (manual p. 126: a fonte "removes the dc component and ensures that the correct ac rms voltage is output"), interpolada para o ciclo de 500/600 amostras, mais o offset DC. Custo: 12 ms por captura.
- `AmetekMX30.quantizar_tensao_rms` (`:831`) é a conta de `_na_resolucao_da_fonte` (`:820`) extraída para as nativas; o método chama a mesma.
- Única mudança além de mover código: a conta do laço (rms, reamostragem, normalização) agora roda antes do primeiro `write` de `program_capture` e também no caminho de reaproveitamento do cache; antes rodava depois de `ABORt`/`SOURce:...` e de `_ensure_trace_slots`. As recusas de 6000 amostras finitas e de ciclos inteiros já vinham antes do primeiro `write`. Os avisos de pico/rms acima do limite continuam logados, agora a partir do resultado (um por ciclo, como antes). O cache de TRACe, a assinatura e as validações de 6000 pontos/IDN/SCPI não foram tocados.

### Prova de que a sequência SCPI não mudou

Transcrição `command_log` de `program_capture()` no modo simulado, para 259 formas de `gerar()` (classes 02, 05, 06 a 17, 19 e 20; 50 e 60 Hz; sorteio ligado e desligado; 127 e 230 V; mais senoide com DC e zeros), com o código de HEAD (`git archive HEAD` num diretório temporário) e o atual. 19 948 linhas, 2 850 `TRACe:DATA`, 259 `SOURce:LIST:VOLTage`:

```
HEAD   scpi_head2.txt  19948 linhas sha256 fbbce7e747f72d06ac013e2f521b7808a79cd556a06a75c50d5d957b03c30969
ATUAL  scpi_final.txt  19948 linhas sha256 fbbce7e747f72d06ac013e2f521b7808a79cd556a06a75c50d5d957b03c30969
cmp -> IDENTICO
```

Idem para os comandos nativos (`trigger_step`/`trigger_pulse` em 10 tensões, `frequency_drift_list`, `configure_harmonics_csine`, `enable_dc_offset`), que passam por `quantizar_tensao_rms`:

```
HEAD   154 comandos sha256 c3d4052044278951f6e0d932e91c54eba516b3d4ce838bc23d7d0254f9098a07
ATUAL  154 comandos sha256 c3d4052044278951f6e0d932e91c54eba516b3d4ce838bc23d7d0254f9098a07
cmp -> NATIVOS_IDENTICOS
```

NÃO VERIFICADO: o mesmo em hardware (sem acesso). A comparação cobre o que `program_capture` escreve no modo simulado; o `time.sleep` e os `*CLS` entre TRACes (só fora do simulado) estão no mesmo lugar do laço (`ametek_orm.py:1503-1510`).

## 2. Forma programada das nativas

`sinais.forma_programada_nativa` (`logica/sinais.py:350`), tabela `FORMA_NATIVA_POR_CLASSE` (`:310`). Definição: a forma ideal para o que o código manda à fonte, na grade da captura.

| Classe | Programada |
|---|---|
| 01 | STEP: senoide em `quantiza(base)` (0,1 V) |
| 02, 03, 04 | PULSe: `quantiza(nível x base) / base` em `[inicio, inicio + duração)`, base fora (2,1813 V vira 2,2 V) |
| 05, THD <= 20 % | senoide clipada com o THD pedido (`corte_da_senoide_clipada`, bisseção sobre a FFT de um ciclo, `sinais.py:322`; rms da senoide) |
| 05, 30 % | `montar_programacao` (caminho TRACe) |
| 18 | `LIST:FREQuency`: `start_hz` na 1.ª metade, `end_hz` na 2.ª, fase contínua |
| 19 | STEP + offset enviado (`%.8g`) |

`ExperimentoBase.forma_programada` (`logica/mestre.py:1397`) escolhe entre as duas famílias por `grava_trace(capture_index)`. Sem editar os `NN.py` das classes: a tabela é por id, em `sinais.py`.

Contra a medida (07/10, RMSE na janela, sem alinhamento extra), 127 V/50 Hz: 18 modelo 0,295 contra programada 0,018; 05 modelo 0,038 contra 0,014. Ver o item 3.

## 3. Gravação das três versões

- Física: `ExperimentoWaveform._capturar_real` (`mestre.py:2890`) e `ExperimentoNativo._capturar_real` (`:2686`, `:2711`) chamam `_registrar_versoes` (`:1435`); `executar()` passa `versoes=self._versoes_atuais` a `_salvar_captura` (`:2539`), que grava `tres_versoes/<mesmo nome do .npz>` (`mestre.py:2174`): `modelo_pu`, `programada_pu`, `medida_pu` (registro recortado em `inicio_janela`, ou `margem_amostras_antes` sem ele), `tempo_ms`, `inicio_janela`, `origem_programada`. Nas classes TRACe/LIST usa a `ultima_programacao` que o `program_capture` acabou de enviar (`_programacao_enviada`, `:1429`). O limpador de órfãos de `_finalizar_gravacao` cobre a pasta nova (mesmo prefixo).
- Simulado: `_registrar_versoes` em `executar()` (`:2415`), arrays `(N, 6000)` gravados em `tres_versoes/NN_classe.npz` por `_salvar_classe_simulada` (`:2306`). Sem medida. Sem o limite de bancada (a programada é a ideal; na 08, 5 a 10 pu).
- Metadata: campo `tres_versoes` (`docs/metadata.md`).
- A programada é um produto extra: se ela falhar, a captura continua e só ela deixa de ser gravada (aviso logado uma vez por classe).
- Pasta e nomes: `docs/tres_versoes.md`.
- Custo no simulado: `tres_versoes/` acrescenta dois arrays de 6000 pontos por captura (o `.npz` principal e cada `snr_XXdb/` já têm um).

## 4. Script offline e as sessões de 07/10

`scripts/gerar_tres_versoes.py`. Metadata de 07/10 não tem `sorteio_posicao` nem `perfil`: reconstruído com sorteio desligado e perfil literatura. A forma de bancada usa o `k` gravado (230 V: 15 de 27 capturas) e `amplitude_bancada_pu` gravada da 08. Verificações: o pico da forma de bancada contra `pico_programado_v` gravado e os parâmetros de `gerar()` contra os gravados; as 99 capturas passaram, 0 avisos.

Originais intocados: `sha256` e `mtime` de todos os arquivos de cada sessão (incluindo o `sem_margem/` que já existia em 127V_50Hz) antes e depois da execução são idênticos: `cmp` sem diferença em 189, 73 e 94 arquivos. Os `.zip` não foram tocados.

Pastas novas: `resultados\sessao_2026-10-07_127V_50Hz\tres_versoes\` (36 `.npz` + `indice.json`, 5,2 MB), `resultados\sessao_2026-10-07_230V_50Hz\tres_versoes\` (27 + índice, 3,9 MB), `resultados\sessao_2026-10-07_14-59-54_run02\tres_versoes\` (36 + índice, 5,2 MB). A 230 V só tem 27 capturas porque 02, 03, 04, 08 e 16 não rodaram nessa sessão (não estão no metadata).

Saídas (`env\Scripts\python scripts\gerar_tres_versoes.py resultados\<sessão>`; terceira coluna = máx |programada - modelo| em pu):

```
> env\Scripts\python scripts\gerar_tres_versoes.py resultados\sessao_2026-10-07_127V_50Hz
id_captura  arquivo                                                  |prog-mod|max  origem
01-0001     01_normal_cap01.npz                                             0.0000  STEP nativo (sinais.forma_programada_nativa)
02-0001     02_sag_sag_pu-0.1.npz                                           0.0000  PULSe nativo (sinais.forma_programada_nativa)
03-0001     03_swell_swell_pu-1.1.npz                                       0.0000  PULSe nativo (sinais.forma_programada_nativa)
04-0001     04_interruption_interruption_pu-0.0215489.npz                   0.0003  PULSe nativo (sinais.forma_programada_nativa)
04-0002     04_interruption_interruption_pu-0.0284607.npz                   0.0001  PULSe nativo (sinais.forma_programada_nativa)
04-0003     04_interruption_interruption_pu-0.0171752.npz                   0.0001  PULSe nativo (sinais.forma_programada_nativa)
05-0001     05_harmonics_thd-0.05.npz                                       0.0565  CSINe nativo (sinais.forma_programada_nativa)
06-0001     06_flicker_flicker_hz-21.2572.npz                               0.0569  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
06-0002     06_flicker_flicker_hz-12.0903.npz                               0.0288  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
06-0003     06_flicker_flicker_hz-10.3869.npz                               0.0297  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
07-0001     07_notch_notch_pulses-15.npz                                    0.1487  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
07-0002     07_notch_notch_pulses-10.npz                                    0.1480  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
07-0003     07_notch_notch_pulses-13.npz                                    0.1474  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
08-0001     08_transient_transient_amplitude_pu-7.08356.npz                 5.9111  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
08-0002     08_transient_transient_amplitude_pu-6.40895.npz                 5.2365  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
08-0003     08_transient_transient_amplitude_pu-7.32799.npz                 6.1556  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
09-0001     09_oscillatory_transient_oscillation_hz-2068.84.npz             0.0075  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
09-0002     09_oscillatory_transient_oscillation_hz-693.99.npz              0.0047  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
09-0003     09_oscillatory_transient_oscillation_hz-476.388.npz             0.0061  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
10-0001     10_sag_harmonics_sag_pu-0.5.npz                                 0.0014  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
11-0001     11_sag_flicker_sag_pu-0.5.npz                                   0.0138  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
12-0001     12_sag_oscillatory_transient_sag_pu-0.5.npz                     0.0046  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
13-0001     13_swell_harmonics_swell_pu-1.3.npz                             0.0036  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
14-0001     14_swell_oscillatory_transient_swell_pu-1.3.npz                 0.0056  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
15-0001     15_harmonics_flicker_thd-0.2.npz                                0.0315  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
16-0001     16_interruption_harmonics_interruption_pu-0.05.npz              0.0013  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
17-0001     17_notch_oscillatory_transient_notch_pulses-10.npz              0.1691  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
17-0002     17_notch_oscillatory_transient_notch_pulses-9.npz               0.1466  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
17-0003     17_notch_oscillatory_transient_notch_pulses-11.npz              0.1536  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
18-0001     18_frequency_drift_start_hz-57.npz                              0.8481  LIST:FREQuency nativo (sinais.forma_programada_nativa)
19-0001     19_dc_offset_dc_offset_pu-0.0310659.npz                         0.0000  STEP+OFFSet nativo (sinais.forma_programada_nativa)
19-0002     19_dc_offset_dc_offset_pu-0.0505661.npz                         0.0000  STEP+OFFSet nativo (sinais.forma_programada_nativa)
19-0003     19_dc_offset_dc_offset_pu-0.0895731.npz                         0.0000  STEP+OFFSet nativo (sinais.forma_programada_nativa)
20-0001     20_interharmonics_interharmonic_145_pu-0.0523844.npz            0.0065  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
20-0002     20_interharmonics_interharmonic_145_pu-0.0543937.npz            0.0044  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
20-0003     20_interharmonics_interharmonic_145_pu-0.0342189.npz            0.0046  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)

36 captura(s) em resultados\sessao_2026-10-07_127V_50Hz\tres_versoes (0 aviso(s))
```

```
> env\Scripts\python scripts\gerar_tres_versoes.py resultados\sessao_2026-10-07_230V_50Hz
id_captura  arquivo                                                  |prog-mod|max  origem
01-0001     01_normal_cap01.npz                                             0.0000  STEP nativo (sinais.forma_programada_nativa)
05-0001     05_harmonics_thd-0.05.npz                                       0.0565  CSINe nativo (sinais.forma_programada_nativa)
06-0001     06_flicker_flicker_hz-21.2572.npz                               0.0610  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
06-0002     06_flicker_flicker_hz-12.0903.npz                               0.0295  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
06-0003     06_flicker_flicker_hz-10.3869.npz                               0.0359  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
07-0001     07_notch_notch_pulses-15.npz                                    0.6661  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
07-0002     07_notch_notch_pulses-10.npz                                    0.6672  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
07-0003     07_notch_notch_pulses-13.npz                                    0.6672  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
09-0001     09_oscillatory_transient_oscillation_hz-2068.84.npz             0.0075  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
09-0002     09_oscillatory_transient_oscillation_hz-693.99.npz              0.0047  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
09-0003     09_oscillatory_transient_oscillation_hz-476.388.npz             0.0061  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
10-0001     10_sag_harmonics_sag_pu-0.5.npz                                 0.2495  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
11-0001     11_sag_flicker_sag_pu-0.5.npz                                   0.2744  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
12-0001     12_sag_oscillatory_transient_sag_pu-0.5.npz                     0.0046  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
13-0001     13_swell_harmonics_swell_pu-1.3.npz                             0.1124  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
14-0001     14_swell_oscillatory_transient_swell_pu-1.3.npz                 0.2685  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
15-0001     15_harmonics_flicker_thd-0.2.npz                                0.0315  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
17-0001     17_notch_oscillatory_transient_notch_pulses-10.npz              0.6834  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
17-0002     17_notch_oscillatory_transient_notch_pulses-9.npz               0.7064  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
17-0003     17_notch_oscillatory_transient_notch_pulses-11.npz              0.7000  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
18-0001     18_frequency_drift_start_hz-57.npz                              0.8481  LIST:FREQuency nativo (sinais.forma_programada_nativa)
19-0001     19_dc_offset_dc_offset_pu-0.0310659.npz                         0.0000  STEP+OFFSet nativo (sinais.forma_programada_nativa)
19-0002     19_dc_offset_dc_offset_pu-0.0505661.npz                         0.0000  STEP+OFFSet nativo (sinais.forma_programada_nativa)
19-0003     19_dc_offset_dc_offset_pu-0.0895731.npz                         0.0000  STEP+OFFSet nativo (sinais.forma_programada_nativa)
20-0001     20_interharmonics_interharmonic_145_pu-0.0523844.npz            0.0220  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
20-0002     20_interharmonics_interharmonic_145_pu-0.0543937.npz            0.0044  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
20-0003     20_interharmonics_interharmonic_145_pu-0.0342189.npz            0.0047  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)

27 captura(s) em resultados\sessao_2026-10-07_230V_50Hz\tres_versoes (0 aviso(s))
```

```
> env\Scripts\python scripts\gerar_tres_versoes.py resultados\sessao_2026-10-07_14-59-54_run02
id_captura  arquivo                                                  |prog-mod|max  origem
01-0001     01_normal_cap01.npz                                             0.0000  STEP nativo (sinais.forma_programada_nativa)
02-0001     02_sag_sag_pu-0.1.npz                                           0.0000  PULSe nativo (sinais.forma_programada_nativa)
03-0001     03_swell_swell_pu-1.1.npz                                       0.0000  PULSe nativo (sinais.forma_programada_nativa)
04-0001     04_interruption_interruption_pu-0.0215489.npz                   0.0003  PULSe nativo (sinais.forma_programada_nativa)
04-0002     04_interruption_interruption_pu-0.0284607.npz                   0.0001  PULSe nativo (sinais.forma_programada_nativa)
04-0003     04_interruption_interruption_pu-0.0171752.npz                   0.0001  PULSe nativo (sinais.forma_programada_nativa)
05-0001     05_harmonics_thd-0.05.npz                                       0.0567  CSINe nativo (sinais.forma_programada_nativa)
06-0001     06_flicker_flicker_hz-21.2572.npz                               0.0489  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
06-0002     06_flicker_flicker_hz-12.0903.npz                               0.0257  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
06-0003     06_flicker_flicker_hz-10.3869.npz                               0.0247  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
07-0001     07_notch_notch_pulses-18.npz                                    0.1069  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
07-0002     07_notch_notch_pulses-12.npz                                    0.0991  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
07-0003     07_notch_notch_pulses-15.npz                                    0.1020  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
08-0001     08_transient_transient_amplitude_pu-7.08356.npz                 5.6185  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
08-0002     08_transient_transient_amplitude_pu-6.40895.npz                 4.9439  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
08-0003     08_transient_transient_amplitude_pu-7.32799.npz                 5.8629  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
09-0001     09_oscillatory_transient_oscillation_hz-2068.84.npz             0.0088  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
09-0002     09_oscillatory_transient_oscillation_hz-693.99.npz              0.0055  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
09-0003     09_oscillatory_transient_oscillation_hz-476.388.npz             0.0091  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
10-0001     10_sag_harmonics_sag_pu-0.5.npz                                 0.1831  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
11-0001     11_sag_flicker_sag_pu-0.5.npz                                   0.2023  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
12-0001     12_sag_oscillatory_transient_sag_pu-0.5.npz                     0.1939  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
13-0001     13_swell_harmonics_swell_pu-1.3.npz                             0.1330  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
14-0001     14_swell_oscillatory_transient_swell_pu-1.3.npz                 0.1043  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
15-0001     15_harmonics_flicker_thd-0.2.npz                                0.0189  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
16-0001     16_interruption_harmonics_interruption_pu-0.05.npz              0.4280  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
17-0001     17_notch_oscillatory_transient_notch_pulses-14.npz              0.1170  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
17-0002     17_notch_oscillatory_transient_notch_pulses-12.npz              0.1122  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
17-0003     17_notch_oscillatory_transient_notch_pulses-13.npz              0.1123  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
18-0001     18_frequency_drift_start_hz-57.npz                              0.8481  LIST:FREQuency nativo (sinais.forma_programada_nativa)
19-0001     19_dc_offset_dc_offset_pu-0.0310659.npz                         0.0000  STEP+OFFSet nativo (sinais.forma_programada_nativa)
19-0002     19_dc_offset_dc_offset_pu-0.0505661.npz                         0.0000  STEP+OFFSet nativo (sinais.forma_programada_nativa)
19-0003     19_dc_offset_dc_offset_pu-0.0895731.npz                         0.0000  STEP+OFFSet nativo (sinais.forma_programada_nativa)
20-0001     20_interharmonics_interharmonic_145_pu-0.0523844.npz            0.0082  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
20-0002     20_interharmonics_interharmonic_145_pu-0.0543937.npz            0.0113  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)
20-0003     20_interharmonics_interharmonic_145_pu-0.0342189.npz            0.0107  TRACe+LIST:VOLTage (AmetekMX30.montar_programacao)

36 captura(s) em resultados\sessao_2026-10-07_14-59-54_run02\tres_versoes (0 aviso(s))
```

### Programada contra medida (verificação ad hoc, não fica no repositório)

RMSE do CH1 recortado em `inicio_janela` contra o modelo e contra a programada, 99 capturas: programada mais perto em 70, empate (diferença < 1e-4) em 28, modelo mais perto em 1 (12-0001 em 127V_50Hz: 0,0153 contra 0,0154).

| sessão | programada mais perto | empate | modelo mais perto |
|---|---|---|---|
| 127V_50Hz | 23 | 12 | 1 |
| 230V_50Hz | 23 | 4 | 0 |
| run02 (127 V/60 Hz) | 24 | 12 | 0 |

Casos de destaque em run02: 08 modelo 0,12 contra programada 0,04; 16 modelo 0,088 contra 0,024; 18 modelo 0,29 contra 0,014; 10 0,045 contra 0,019. Isso sustenta o rms por ciclo e a remoção do DC como a física da fonte, mas não substitui um teste dirigido em bancada.

## 5. Testes

`TresVersoesTests` (`tests/test_offline.py:5620`, 16 testes). O do item 5 é `test_funcao_pura_gera_byte_a_byte_o_que_program_capture_envia` (`:5648`): 52 formas reais de `gerar()` (13 classes x 2 frequências x sorteio ligado/desligado) mais senoide com DC e zeros; compara cada `TRACe:DATA` do `command_log` com `comando_trace(i)`, o `SOURce:LIST:VOLTage` com `texto_list_voltages()`, o `DWELl` e `last_programmed_peak_v`.

```
> .\env\Scripts\python.exe -m unittest tests.test_offline -v
...
Ran 309 tests in 31.410s
OK
```

(Antes: 293 testes, OK. Os fixtures `tests/fixtures/*.json` continuam passando: `gerar()` não mudou.)

## Achados (sem filtro de gravidade)

1. **[média] A programada difere do modelo mais do que se supunha, por construção, em ciclos com DC.** A TRACe perde a média do ciclo e a fonte a reescala ao rms de `LIST:VOLTage` calculado com a média: no ciclo em que um afundamento começa no meio, a forma emitida muda. Em run02 (60 Hz), máx |programada - modelo|: 10 = 0,18, 11 = 0,20, 12 = 0,19, 16 = 0,43 pu; a medida segue a programada (16: 0,088 para 0,024). Não é erro do código novo: é o que `program_capture` envia desde antes. Muda a leitura de "limite da bancada".
2. **[baixa] `_resample_cycle` não fecha o ciclo.** `np.interp` repete a última amostra nos ~2 últimos dos 1024 pontos, então uma senoide programada a 60 Hz tem até 1,3e-3 pu de erro nessas amostras (`test_programada_de_senoide_pura_e_a_senoide`, tolerância 2e-3). Corrigir mudaria o `TRACe:DATA` enviado; não alterei (a spec exige SCPI idêntico).
3. **[média] 08: a programada de 07/10 é a da bancada, não a do modelo.** Máx |programada - modelo| de 5,2 a 6,2 pu na 08, porque o impulso foi reduzido de 6,4 a 7,3 pu para 1,34 pu. É o dado que o professor pediu (limite de bancada) e aparece inteiro nas três versões. No simulado a programada da 08 é a ideal (7,4 pu de pico, 1330 V a 127 V), que a fonte não emitiria.
4. **[média] 19: programada = modelo (diferença 0) enquanto a medida tem 5 a 6 % menos de amplitude em ACDC** (`acdc_amplitude.md`). O déficit fica inteiro entre programada e medida, como a separação pretende; a programada não o modela.
5. **[baixa] 05 (CSINe): o pico medido fica 3 % acima da programada** (127 V/50 Hz: 0,954 contra 0,926 pu; modelo 0,971). O RMSE melhora (0,038 para 0,014) mas o corte e a escala da CSINusoid interna são suposição (NÃO VERIFICADO; só o THD é o pedido).
6. **[baixa] 18: continuidade da fase na troca de passo** não foi verificada contra a medida; o RMSE caiu de 0,295 para 0,018, o que sugere que sim.
7. **[baixa] O `scripts/gerar_tres_versoes.py` só reconstrói o que o metadata permite:** sessão com `capturas_override` ativo e as classes 04/06/08/09/19 caem no ramo de sorteio de `gerar()` (a mesma limitação de `analisar_sessao._reconstruir_esperado`). Nas 99 capturas de 07/10 o conferido (parâmetros, pico) bateu.
8. **[baixa] Reprodutibilidade:** o script carrega `gerar()` de hoje. Se `gerar()` mudar, a conferência de parâmetros acusa (`avisos`) mas o `.npz` sai com o `gerar()` novo. O commit e a árvore suja ficam em `indice.json` (`git_sujo: true` hoje).
9. **[baixa] Nas sessões antigas `medida_pu` não foi copiada** para `tres_versoes/` (a spec pede só modelo e programada): a medida está no `.npz` original, com margem.
10. **[baixa] Dependência de `Config`:** `forma_programada` lê `grid_frequency_hz` e `base_voltage_rms`; o script usa uma `_ConfigOffline` própria (subclasse da de `analisar_sessao`) em vez de editar `analisar_sessao.py`.

## NÃO VERIFICADO

- Mesma sequência SCPI em hardware (só o modo simulado foi comparado).
- Que a fonte escala a TRACe ao rms de `LIST:VOLTage` na saída real: do manual p. 126 e consistente com os dados de 07/10 (70 contra 1), não medido de forma dirigida. Um `TRACe:DATA? <nome>` (o manual diz que devolve valores normalizados a +-1) poderia confirmar o conteúdo gravado; nunca foi usado.
- Corte e escala da CSINusoid (05), continuidade de fase do `LIST:FREQuency` (18), resolução da largura do PULSe e o instante exato de aplicação (02, 03, 04).
- Gravação física `_salvar_captura` com instrumentos reais (testada só com `_capturar_real` simulado e o osciloscópio mock: `test_fisico_grava_as_tres_versoes_alinhadas_na_janela`).

## Sugestões fora do escopo

- Corrigir o fechamento de ciclo de `_resample_cycle` (achado 2) exige reabrir a sequência SCPI e uma sessão de bancada para confirmar.
- `analisar_sessao.py` e `relatorio_html.py` poderiam comparar contra a programada além do modelo.
