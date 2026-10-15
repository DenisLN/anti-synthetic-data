# 03. Ficha de fontes das 20 classes

Base: `main` em `fa82f49` (v1.15 em andamento, sem tag), lida em 2026-10-15. Linhas de `experimentos_nativos/NN.py` e `experimentos_waveform/NN.py` conferidas com `ast` nesta data (`gerar()`, `configurar()` e ganchos citam `início-fim`). Análises: só `github/arquivo/analises:sessao-13-10-2026/` e `:specs/2026-10-13/` (relatórios individuais numerados `NN`), mais `CHANGELOG/v1.15.md` (`v1.15:L` = linha do arquivo) e o código atual. As análises de 21/09, 30/09 e 12/10 não foram auditadas.

## Como ler

- **Selos** (convenção definida em `05-arquitetura-do-site.md` §4): VERIFICADO NA BANCADA, OFFLINE, NÃO VERIFICADO, PENDENTE, FORA DA MAIN.
- **Bancada com código velho.** Houve três campanhas de bancada: 2026-09-30 (v1.12; 127 V/60 Hz; `15-26-05` e `15-58-51`, 20/20 com 1 captura por classe: `v1.12:142-149`); 2026-10-07 (código da v1.13/v1.14; `run02` 127 V/60 Hz 20/20, `127V_50Hz` 19/20 mais a 08 numa rodada à parte, `230V_50Hz` 15/20: `v1.14:22-26,123-124`; 99 capturas conferidas em `resultados/` desta máquina). **Depois disso a bancada não rodou.** Toda mudança de `gerar()` e da validação feita na v1.15 (perfis, sorteio de início/duração/fase, compostas, 05/07/17/18, 08, crista com fator) tem selo NÃO VERIFICADO no hardware. "Verificado" abaixo vale para o comportamento anterior à v1.15.
- **Correlação do distúrbio** (`docs/correlacao_disturbio.md:38-58`): medida nas sessões de 07/10 contra `gerar()` reconstruído sem sorteio; a origem da "faixa de referência" é NÃO VERIFICADA (`:80`).
- Comuns a todas as classes (não repetidos em cada ficha): `v1.8:89-109` (`capture_index` x `indice_global`, `nivel_indice`), `v1.11:46-154` (P01 a P09), `v1.12:24-37` (writes sincronizados por `*ESR?`), `v1.13:32-60` (`capturas_padrao`), `v1.15:5-10` (perfis), `v1.15:28-40` (sorteio), `v1.15:573-603` (crista com fator), relatórios 17, 21 e 23.

## Nativas

### 01 NORMAL (`experimentos_nativos/01.py`, 22 linhas)
- **Código**: `gerar()` 12-16 (senoide com fase sorteada), `configurar()` 18-22 (`trigger_step(base)`: só gera o BOT). Sem ganchos. `capturas_padrao` = 1 (herdado, `mestre.py:1564`).
- **CHANGELOG**: `v1.7:43-124,248-277` (`*WAI`, `restaurar_forma_e_modo_padrao`, `assegurar_tensao_base`); `v1.11:46-66` (P01/P02: espera IDLE, readback do STEP); `v1.12:24-37,61-66` (writes por `*ESR?`; fase de disparo); `v1.14:67-75` (cadeia de medição antes da 1.ª classe); `v1.15:28-40` (só a fase é sorteada); `v1.15:606-629` (spec 25: independente do perfil, capturada uma vez com `set perfil todos`).
- **Relatórios**: 25 (classe independente do perfil, `perfis.py:217-229`); 14 não a cita. Nenhum relatório próprio.
- **Bancada**: VERIFICADO NA BANCADA com `gerar()` sem sorteio (09-30 e 07/10; STEP a 127 V/60 Hz e 50 Hz). A 01 da `run02` (127 V/60 Hz) começa em ~0 V (RMS 0,020 pu na margem anterior) porque a v1.13 ainda não tinha a checagem de cadeia (tabela da margem em `C:\Users\denis\Downloads\tcc\02\atividade.tex:409-415`, texto do usuário fora do repositório; mecanismo em `mestre.py:1398-1425`, `assegurar_tensao_base`). Sorteio de fase e disparo na fase sorteada: NÃO VERIFICADO (`v1.15:40`).

### 02 SAG (`experimentos_nativos/02.py`, 35 linhas)
- **Código**: `NIVEIS` 19-21 (propriedade, lê `perfis.faixa(config,"sag_niveis")`), `gerar()` 23-30 (`pre_trigger_s` 13 = 0,060; `INICIO_S`/`DURACAO_S` 15-16 = 0,060), `configurar()` 32-35 (`trigger_pulse(nível × base, width_s=largura_do_pulso_s)`). `tensao_rms_programada` herdado (`mestre.py:2903-2911`).
- **CHANGELOG**: `v1.7:43-124` (-300 do SAG, `*WAI` antes de `INITiate`); `v1.10:175-206` (Bug A: o pulso não aparecia na janela de 1 s; o CHANGELOG não diz explicitamente qual versão o fechou, a v1.11 P07 corrige a referência do trigger: fechamento NÃO VERIFICADO no texto); `v1.11:16-44,77-85` (H-NATIVO; P04 nível inviável é pulado); `v1.12:24-37,39-42,61-66` (N1/N2 writes, N3 truncamento 0,1 V, F1 fase de disparo 216°); `v1.13:92-128` (220 V: nativas não reduzem); `v1.14:36-59` (fatores por condição); `v1.15:5-10,28-40,59-68` (perfis; sorteio I+D+F; regra por frequência).
- **Relatórios**: 20 (largura do `PULSe:WIDTh` e desvio de pré-trigger nunca medidos; `scripts/verificar_sessao_bancada.py` os mede, limiares 2 ms e 2 amostras são propostas); 25.
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15: correlação do distúrbio 0,997 (127 V/60 Hz) e 0,999 (127 V/50 Hz) (`docs/correlacao_disturbio.md:40`). A 230 V/50 Hz foi pulada em 07/10 e passa a rodar pela regra por frequência (previsto 380,3 V, `v1.15:64`): OFFLINE. Sorteio de posição, pré-trigger por captura, `TRIGger:SYNChronize:PHASe` em passos de 0,1° e `PULSe:WIDTh` sorteada: NÃO VERIFICADO.

### 03 SWELL (`experimentos_nativos/03.py`, 35 linhas)
- **Código**: igual à 02 com `swell_niveis` (1,1/1,2/1,4/1,6/1,8 pu em `literatura`); `configurar()` 32-35.
- **CHANGELOG**: os de 02, mais `v1.13:109-112` (a 220 V a 03 roda só 1,1 pu: 1,2 pu prevê 434 V, ≥ 1,4 pu passa de 300 Vrms); `v1.15:64` (a 230 V/50 Hz continua fora: 1,058 × 357,8 V × 1,10 = 416,4 V > 415,8 V, "mantida por decisão de projeto").
- **Relatórios**: 20, 25.
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 (correlação 0,943/0,945, na borda do teto 0,94 da faixa de referência, `docs/correlacao_disturbio.md:41`). Pulada a 230 V/50 Hz também hoje (OFFLINE). Sorteio: NÃO VERIFICADO.

### 04 INTERRUPTION (`experimentos_nativos/04.py`, 44 linhas)
- **Código**: `capturas_padrao = 3` (16); `gerar()` 22-32 (nível `U(0; 0,09)` por `sinais.valor_para_captura`); `configurar()` 34-44 reproduz a seed (`base_seed + 4_000_000 + capture_index`, **linha 37**; o `docs/classes.md:51` cita `04.py:36`) e chama `trigger_pulse`. Acoplamento: `configurar()` só concorda com `gerar()` enquanto `capture_index == indice_global` (`docs/classes.md:51`).
- **CHANGELOG**: `v1.8:110-123` (cobertura determinística com `set capturas`); `v1.11:77-85` (P04); `v1.12:39-42` (N3: 2,7367 V lido como 2,7 V, causa do readback recusado); `v1.13:32-60`; `v1.14:123-128`; `v1.15:28-40,59-68`.
- **Relatórios**: 20, 25 (independente do perfil).
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 (correlação 0,996-0,999). A 230 V/50 Hz pulada em 07/10; previsão atual 380,3 V (OFFLINE). Sorteio NÃO VERIFICADO.

### 05 HARMONICS (`experimentos_nativos/05.py`, 75 linhas)
- **Código**: `NIVEIS_THD` 33-36 (`thd_niveis`: 5/10/15/20/30 % em `literatura`), `total_niveis` 38-39, `gerar()` 41-59 (com sorteio, nível ≤ 20 %: `senoide_clipada_pu` de `sinais.py:613-621`; 30 %: soma 3.ª/5.ª/7.ª na razão 0,6:0,3:0,1), `configurar()` 61-67 (`configure_harmonics_csine` + `trigger_step`), `usar_trace()` 69-70 (`thd > TETO_CSINE`, `AmetekMX30.MAX_CSINE_THD_PCT/100`), `scope_scale_v()` 72-75 (1,5 × pico). Mecanismo misto: ≤ 20 % CSINusoid nativa; 30 % via TRACe (`ExperimentoNativo._capturar_real`, ramo `usar_trace`, `mestre.py:2936-2983`).
- **CHANGELOG**: `v1.6` (CSINusoid em vez de CSINe), `v1.7:9-21,43-124` (segundo `*WAI` e `assert_no_errors` após o THD); `v1.12:12-20`; `v1.13:283-` (tabelas de capturas); `v1.15:88-100` (modelo vira a senoide clipada; antes soma de harmônicas); `v1.15:467-480` (tabela por THD: rms 0,7071, fundamental 0,98-1,00, pico 0,82-0,96; nível 30 % por TRACe rms 0,738 e `LIST:VOLTage` = 1,044 × base, **sem mudar `gerar()`**).
- **Relatórios**: 18 (a 05 conferida contra o diagnóstico: THD, rms, fase e teto batem; correlação programada × modelo 1,00000 no nível 30 %); 25; nenhum trata o nível de 2 % do perfil `norma`.
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 (correlação do distúrbio 0,50 nas três sessões de 07/10 porque o modelo antigo somava harmônicas e a fonte clipava: `docs/correlacao_disturbio.md:43,60`). Modelo novo (clipado): OFFLINE. NÃO VERIFICADO: rms da CSINusoid interna e THD a 10/15/20 %, nível de 2 % (norma), nível de 30 % por TRACe na bancada, pico do nível de 30 % a 380 V (443,5 V por conta, 380 V é recusado pelo `START_BENCH`; `v1.15:533`).

### 18 FREQUENCY_DRIFT (`experimentos_nativos/18.py`, 51 linhas)
- **Código**: `extremos_hz()` 21-30 (f0 ± 3 Hz, ou 57/63 Hz com `set sorteio off`; alterna por paridade do índice), `gerar()` 32-43 (rampa linear, fase sorteada), `configurar()` 45-51 (`frequency_drift_list(start,end,voltage,dwell=meio)`: LIST:FREQuency de 2 pontos).
- **CHANGELOG**: `v1.8:221`; `v1.10:101,126` (`LIST:REPeat 0,0`); `v1.11:16-44` (`-226 Lists not same length` depois da 17: lista de forma residual); `v1.12:68-72` (F2: frequência base restaurada, 63 Hz herdados pela 19); `v1.15:88-100` (f0 ± 3 Hz; a 50 Hz era 57 → 63 Hz, +14 %/+26 % da rede); `v1.15:385-420` (spec 20: verificação de fase na troca).
- **Relatórios**: 20 (`verificar_sessao_bancada.py` mede o salto de fase na troca `start_hz` → `end_hz`; limiar 10° é proposta; a continuidade de fase nunca foi medida), 25.
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 (57 → 63 Hz; correlação do distúrbio 0,939 a 60 Hz e 0,982 a 50 Hz, faixa de referência não citada). Rampa 47 → 53 Hz a 50 Hz: NÃO VERIFICADO. Continuidade de fase e restauração da frequência após a nova rampa: NÃO VERIFICADO (`docs/tres_versoes.md:61`).

### 19 DC_OFFSET (`experimentos_nativos/19.py`, 43 linhas)
- **Código**: `capturas_padrao = 3` (21); `gerar()` 23-30 (offset `U(0,02; 0,10)` pu, depois fase); `configurar()` 32-43 (seed `base_seed + 19_000_000 + capture_index`, **linha 33**; `enable_dc_offset(offset_v, ac_peak_v)` e `trigger_step`).
- **CHANGELOG**: `v1.7:43-124,171` (`-300`: `SOURce:VOLTage:OFFSet` só em ACDC); `v1.12:68-72` (rodava a 63,03 Hz após a 18); `v1.14:124`; `v1.15:28-40,385-420` (spec 20: verificação offline do ACDC pendente; `measure_voltage` em ACDC é RMS total, comentário em `ametek_orm.py:1964-1977`).
- **Relatórios**: 20 (`diag_acdc_amplitude.py` pronto, nunca rodou), 25 (independente do perfil).
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 com defeito conhecido: CA 5-6 % abaixo (0,938-0,951 pu), CC próximo do programado (quirk A19, causa NÃO VERIFICADA). Correlação: n/a (resíduo constante, `docs/correlacao_disturbio.md:57`). PENDENTE: P-17.

## Waveform (TRACe/LIST)

Comuns: `ExperimentoWaveform` (`mestre.py:2986-3188`), `program_capture` (`ametek_orm.py:1511-1705`), regra da média por ciclo (`v1.15:165-205`, relatório 11) e `set diagnostico retrieve` (relatório 16). As seções "CHANGELOG" abaixo só citam o que é próprio da classe.

### 06 FLICKER (`experimentos_waveform/06.py`, 33 linhas)
- **Código**: `capturas_padrao = 3` (16); `gerar()` 18-28 (`flicker_hz` por `valor_para_captura` U(8; 25), profundidade do perfil, fase); gancho `parametros_com_disturbio_reduzido` 30-33 (`flicker_depth_bancada`).
- **CHANGELOG**: `v1.8:110-123`; `v1.12:12-20`; `v1.13:32-60`; `v1.15:5-10,28-40`; `v1.15:496-522` (spec 18, item 4: a perda de correlação da 06 na TRACe é a média de cada ciclo que a fonte remove; programada × modelo 0,77-1,00, mediana 0,90-0,97; 0,9999 sem a média do ciclo).
- **Relatórios**: 18 (a decisão entre "comparar com a programada" e "redefinir o `gerar()` com média nula por ciclo" é do usuário), 11.
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 com correlação do distúrbio 0,826-0,960 (abaixo da faixa 0,95-1,00 em 7 de 9 capturas, `docs/correlacao_disturbio.md:44,63`). NÃO VERIFICADO: perfil `norma` (2-7 %), fonte reproduzindo o flicker de 25 Hz (`v1.15:349`). PENDENTE: P-12.

### 07 NOTCH (`experimentos_waveform/07.py`, 43 linhas)
- **Código**: `capturas_padrao = 3` (15); `gerar()` 17-36 (com sorteio: `aplicar_entalhes_continuos` em todos os ciclos, só fase sorteada; sem sorteio: `aplicar_entalhes` em 80 ms a partir de 60 ms, byte a byte de `34a0d82`); gancho 38-43 (`notch_profundidade_pu_bancada`).
- **CHANGELOG**: `v1.9:7`, `v1.10:88` (NOTCH foi a classe usada para medir o efeito de `LIST:REPeat`: 516 → 438 ms); `v1.14:55-58` (230 V/50 Hz: 07 = 1,317, reduzida a ~38 %); `v1.15:88-100` (entalhes contínuos, IEEE 1159-2019 4.4.5.4); `v1.15:398-405` (simulação: toque da fonte 31-59 % acima na crista); `v1.15:573-603` (spec 26).
- **Relatórios**: 20 (achado alto: reprovação em massa pela crista), 26 (crista aceita `[modelo×0,9, modelo×fator×1,1]`; fator 07 a 127 V/60 Hz = 1,186, a simulação pede ≥ 1,344), 25 (independente do perfil).
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 (4 ciclos entalhados; correlação 0,899-0,942 dentro da faixa). Entalhes em todos os ciclos: NÃO VERIFICADO; previsão do relatório 26/ROTEIRO: a 1.ª rodada a 127 V/60 Hz sai inválida pela crista (PENDENTE: P-07). Fatores de 127 V/50 Hz (1,375) cobrem quase tudo (`v1.15:590`).

### 08 TRANSIENT (`experimentos_waveform/08.py`, 216 linhas)
- **Código**: `capturas_padrao = 3` (22); constantes 24-70 (`INICIO_IMPULSO_S` 0,080, `DISTANCIA_MIN_FRONTEIRA_AMOSTRAS` 30 em **35**, `TOLERANCIA_POSICAO_AMOSTRAS` 10, `SOBRESSINAL_DO_DEGRAU` 0,55 em 59, `SUBSINAL_DO_DEGRAU` 0,70 em 60, `exige_medida_de_pico`, `fracao_teto_pico_medido` 0,9); ganchos: `limite_pico_bancada_pu` 72-80, `_indices_impulso` 82-99, `gerar()` 101-115 (impulso 5-10 pu, 2 amostras), `forma_para_bancada` 117-169, `excursao_fisica_prevista_v` 171-172, `ciclos_excluidos_da_validacao` 174-179, `conferir_posicao_do_evento` 181-216. Única classe fora do sorteio de posição e fora da tabela de fatores (`mestre.py:2018-2034`, `1906-1908`).
- **CHANGELOG**: `v1.7:139-150,187` (primeiro limite de pico: escalava a forma inteira); `v1.8:24-35,110-123` (cobertura/caracterização); `v1.12:74-89` (T8: só o impulso é limitado; sobressinal 0,38 e subsinal 0,58 do degrau; VMAX 230 V/VMIN -334 V); `v1.14:98-109` (0,55 depois de 376 V > 374,2 V a 50 Hz); `v1.15:72-84` (impulso a 90 ms a 50 Hz; conferência de posição); `v1.15:354-380` (diagnóstico da cópia em 100 ms).
- **Relatórios**: 15 (`diag_ciclos_trace.py`, `diag_marcadores_trace.py`, `modelo_lista_fonte.py`; cinco hipóteses, nenhuma confirmada), 16, 25, 11 (programada × modelo 0,56-0,82 pu: a 08 é exceção por construção).
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 só com limitação física (impulso filtrado, `docs/classes.md:55-60`; a 60 Hz posição a 80 ms, a 50 Hz a 100 ms em 3/3). Correlação do distúrbio 0,824-0,831 (60 Hz) e 0,004-0,011 (50 Hz). Impulso a 90 ms a 50 Hz: NÃO VERIFICADO (Bloco 6 do ROTEIRO). Mecanismo da cópia em 100 ms: NÃO VERIFICADO (P-02). Rodei hoje `diag_ciclos_trace.py` nas duas sessões reais de 07/10 (ver `04-pendencias.md`, P-02).

### 09 OSCILLATORY_TRANSIENT (`experimentos_waveform/09.py`, 38 linhas)
- **Código**: `capturas_padrao = 3` (18); `gerar()` 20-32 (`f` por `valor_para_captura` U(300; 2400), `duracao` U(0,010; 0,040), `sortear(...)` início + fase, `oscilacao_amortecida` com amplitude 0,3 pu e τ 5 ms de `sinais.py:131-146`); gancho 34-38 (`oscillation_amplitude_pu_bancada`).
- **CHANGELOG**: `v1.8:110-123`; `v1.13:32-60`; `v1.15:28-40`; `v1.15:354-380` (A25: impulso de 0,12-0,27 pu em 100,0-100,2 ms que a forma programada não tem, 9 de 9 capturas); `v1.15:486-494` (recomendação: 6-9 capturas; aceitar sem ressalva só capturas sem ciclo trocado e resíduo < ~0,05 pu perto de 100 ms).
- **Relatórios**: 15, 18 (item 3), 25.
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 com defeito de dado (A25). Correlação 0,749-0,925. Hoje (offline, sessões reais de 07/10): resíduo máximo em 100 ms de 0,15-0,28 pu (50 Hz) e 0,11-0,24 pu (60 Hz), nenhum ciclo "trocado" pelo critério do script. PENDENTE: P-02.

### 10 SAG_HARMONICS (`experimentos_waveform/10.py`, 41 linhas)
- **Código**: `capturas_padrao = 3` (19); `gerar()` 22-32 (sag e THD por `perfis.composto`, sorteio I+D+F, `onda_com_harmonicos`); gancho 34-41 (`sag_pu_bancada`, `thd_bancada`).
- **CHANGELOG**: `v1.12:91-99` (bloqueio prévio: a 220 V pulava 10, 11, 14, 16); `v1.13:92-128` (limite de bancada: 10 reduzida a 88 %); `v1.15:44-55` (sorteio: sag U(0,1; 0,9), THD U(0,05; 0,20); `capturas_padrao` 3); `v1.15:165-205` (rms CA por ciclo: erro programada × modelo 0,31 → 0,26 pu a 50 Hz; resta a média do ciclo); `v1.15:314-351` (revisão contra a proposta).
- **Relatórios**: 11, 19 (extensões a-f), 20, 25 (depende do perfil: `norma` e `fronteira` mudam o sag).
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 (parâmetros fixos sag 0,5 e THD 20 %; correlação 0,975-0,999). Parâmetros sorteados e correção do rms por ciclo: NÃO VERIFICADO (roteiro: conferir `pico_medido_v` contra `extremo_previsto_v` das 10/11/12/16, `ROTEIRO_BANCADA.md:343`). PENDENTE: P-08, P-09.

### 11 SAG_FLICKER (`experimentos_waveform/11.py`, 37 linhas)
- **Código**: `gerar()` 17-28 (sag, profundidade e `flicker_hz` por `perfis.composto`); gancho 30-37. Sag em 11 e 12 e swell em 13 e 14 são "extensões" além da proposta (`v1.15:321`).
- **CHANGELOG**: igual à 10, mais `v1.14:55-58` (a 230 V/50 Hz o fator da 11 é igual ao da 01, 1,03: captura reduzida só dá limite inferior).
- **Relatórios**: 11, 19, 25.
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 (flicker 15 Hz, sag 0,5; correlação 0,969-0,999). Sorteio: NÃO VERIFICADO. Efeito da média por ciclo do flicker na 11 e na 15: NÃO VERIFICADO, não calculado (`v1.15:522`).

### 12 SAG_OSCILLATORY_TRANSIENT (`experimentos_waveform/12.py`, 40 linhas)
- **Código**: `gerar()` 19-31 (sag e `oscilacao_composto_hz`, duração da oscilação = duração sorteada do evento); gancho 33-40.
- **CHANGELOG**: `v1.15:44-55,314-351` (a 2400 Hz a programada sai com -2,4 % de amplitude; com sag sorteado o erro máximo sobe a 0,25-0,32 pu, vindo da borda do sag no meio do ciclo).
- **Relatórios**: 11, 19, 25.
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 (600 Hz fixo; correlação 0,967-0,998). Oscilação até 2400 Hz via TRACe: NÃO VERIFICADO (`v1.15:349`).

### 13 SWELL_HARMONICS (`experimentos_waveform/13.py`, 40 linhas)
- **Código**: `gerar()` 21-31; gancho 33-40 (`swell_pu_bancada`, `thd_bancada`).
- **CHANGELOG**: `v1.13:92-128` (a 220 V roda reduzida); `v1.15:44-55` (swell U(1,1; 1,8)); a 220 V a 13 roda 1/3 e a 14 roda 0/3 capturas (`v1.15:51`, "não verificado de novo"); a 230 V/50 Hz a 13 roda 2/3 (`docs/operacao.md:88`).
- **Relatórios**: 19, 25.
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 (swell 1,3; correlação 0,976-0,997). Sorteio: NÃO VERIFICADO.

### 14 SWELL_OSCILLATORY_TRANSIENT (`experimentos_waveform/14.py`, 40 linhas)
- **Código**: `gerar()` 19-31; gancho 33-40.
- **CHANGELOG**: `v1.12:91-99`; `v1.13:92-128` (reduzida a 48 %: swell aplicado 1,109 pu, no limiar de 1,1 pu da IEEE); `v1.15:44-55`.
- **Relatórios**: 19, 25.
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 (correlação 0,961-0,989). A 230 V/50 Hz pulada (0/3 com swell sorteado). Sorteio: NÃO VERIFICADO.

### 15 HARMONICS_FLICKER (`experimentos_waveform/15.py`, 24 linhas)
- **Código**: `gerar()` 17-24 (200 ms inteiros, só a fase sorteada). **Não tem** `parametros_com_disturbio_reduzido`: com redução (220 V) o metadata não traz `thd_bancada` nem `flicker_depth_bancada` (`v1.15:323`, relatório 19).
- **CHANGELOG**: `v1.15:44-55` (de 1543 a 2000 formas distintas), `v1.15:314-351`.
- **Relatórios**: 19, 25.
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 (correlação 0,988-0,991). Flicker de 25 Hz e a média por ciclo: NÃO VERIFICADO.

### 16 INTERRUPTION_HARMONICS (`experimentos_waveform/16.py`, 39 linhas)
- **Código**: `gerar()` 21-30 (interrupção fixa em 0,05 pu: sortear tiraria parte das capturas da faixa de interrupção, `docs/decisoes.md` v1.15; THD sorteado); gancho 32-39.
- **CHANGELOG**: `v1.7:292`; `v1.12:91-99` (volta de interrupção sobressai 15-46 %: 262 V medidos com 180 V programados); `v1.13:122-126` (a 220 V a 16 reduzida a 37 % é "quase um afundamento", 0,65 pu); `v1.14:123,126-131` (a 50 Hz as nativas 02/04/16 deram fatores menores); `v1.15:59-68` (a 230 V/50 Hz prevê 368,5 V e roda); a 16 só é independente do perfil com `set sorteio off` (`perfis.py:217-229`).
- **Relatórios**: 11 (erro programada × modelo 0,44 → 0,33 pu; resta a média do ciclo), 19, 25.
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 (fator 1,475 a 127 V/60 Hz, o maior de todas as tabelas; correlação 0,972-1,000). Parâmetros sorteados e rms por ciclo corrigido: NÃO VERIFICADO; pico das 10/11/12/16 é conferência obrigatória na 1.ª sessão (ROTEIRO).

### 17 NOTCH_OSCILLATORY_TRANSIENT (`experimentos_waveform/17.py`, 51 linhas)
- **Código**: `capturas_padrao = 3` (17); `gerar()` 19-40 (início sorteado e fase acoplada ao início; com sorteio entalhes contínuos; oscilação fixa em 300 Hz); gancho 42-51.
- **CHANGELOG**: `v1.12:140-149`; `v1.14:22-26,55-58` (a 17 mediu 444 V a 230 V/50 Hz, acima dos 425 Vp, com previsão 405 V: origem da calibração por condição); `v1.15:88-100`; `v1.15:398-405`; `v1.15:573-603`.
- **Relatórios**: 20, 26 (17 a 127 V/60 Hz: fator 1,031, a simulação pede ≥ 1,420; 0/135 aprovadas com o calibrado), 25.
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 (correlação 0,902-0,931). Entalhes contínuos e crista: NÃO VERIFICADO; mesma previsão da 07 (1.ª rodada inválida pela crista a 127 V/60 Hz). PENDENTE: P-07.

### 20 INTERHARMONICS (`experimentos_waveform/20.py`, 42 linhas)
- **Código**: `capturas_padrao = 3` (20); `FREQUENCIAS` (145, 210, 330 Hz; 150 Hz removido por ser 2,5.ª harmônica a 60 Hz); `gerar()` 22-33 (3 amplitudes do perfil, 3 fases `U(0; 2π)`); gancho 35-42.
- **CHANGELOG**: `v1.8:121` (fica fora da cobertura determinística); `v1.13:122` (reduzida a 220 V); `v1.15:5-10` (perfil `norma` 0,5-2 %); `v1.14:55-58`.
- **Relatórios**: 11 (programada × modelo 0,0045 → 0,0168 pu a 50 Hz), 25.
- **Bancada**: VERIFICADO NA BANCADA pré-v1.15 (correlação 0,907-0,981; duas capturas a 60 Hz abaixo de 0,95: causa NÃO VERIFICADA, `docs/correlacao_disturbio.md:58,64,81`). Perfil `norma`: NÃO VERIFICADO.

## Resumo de estado

| Classe | Verificada em bancada (código pré-v1.15) | O que a v1.15 mudou e ninguém mediu | Pendência |
|---|---|---|---|
| 01 | sim | fase sorteada | P-05 |
| 02, 03, 04 | sim | I/D/F, PHASe, PULSe:WIDTh por captura | P-05 |
| 05 | sim (modelo antigo) | modelo clipado; 2 %; 30 % TRACe | P-10 |
| 06 | sim | perfil; média por ciclo | P-12 |
| 07, 17 | sim (4 ciclos) | entalhes em todos os ciclos; crista | P-07 |
| 08 | só como impulso filtrado | 90 ms a 50 Hz | P-02, P-03 |
| 09 | sim, com A25 | I+F | P-02 |
| 10-16 | sim, parâmetros fixos | sorteio; rms por ciclo | P-08, P-09, P-11 |
| 18 | sim (57-63 Hz) | f0 ± 3 Hz; fase na troca | P-06 |
| 19 | sim, CA -5-6 % | fase sorteada | P-17 |
| 20 | sim | perfil | P-01 |
