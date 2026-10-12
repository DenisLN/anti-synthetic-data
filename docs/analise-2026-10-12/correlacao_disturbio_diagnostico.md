# Diagnóstico da correlação de distúrbio abaixo de 0,90 e modelo da CSINe

Data: 2026-10-12. Somente leitura em `logica/` e `experimentos_*`; árvore NÃO commitada. Sessões lidas de `anti-synthetic-data\resultados\` (127 V/60 Hz = `14-59-54_run02`, 127 V/50 Hz, 230 V/50 Hz). Scripts ao lado, todos rodam com `env\Scripts\python.exe docs\analise-2026-10-12\<script>.py` na raiz do worktree.

Convenção: `correlação` = `sinais.correlacao_disturbio` (`logica/sinais.py:307`), a mesma de `analisar_sessao`. As versões vêm de `scripts/gerar_tres_versoes.py::reconstruir_versoes` (refeitas em memória a partir do metadata; nada gravado). "modelo" = `gerar()`, "bancada" = modelo com o k/limite de pico, "programada" = `montar_programacao(...).programada_pu()` (`logica/ametek_orm.py:120,1322`) ou `forma_programada_nativa` (05), "medida" = CH1 recortado em `indice_trigger`. O `modelo × medida` do script reproduz o terminal de `analisar_sessao` (05 = 0,504; 08 a 50 Hz = 0,004/0,005/0,011).

**Pedido:** é razoável. Ressalva: não existe captura da 05 acima de 5 % em nenhuma sessão (um nível por sessão, `capturas_padrao_classe: 1` no metadata e um único `05_harmonics_thd-0.05.npz` nas 3 sessões e no arquivo antigo). A "CSINe de 5 a 20 %" só foi medida em 5 %. [média]

## 1. Causa principal por classe

Scripts: `diag_causas.py` (separa modelo/bancada/programada/medida), `diag_fisica.py`, `diag_resposta_fonte.py`, `diag_picos_espurios.py`, `diag_08_09.py`.

### 1.1 Quanto custa cada etapa (sem a fonte)

`diag_causas.py` (colunas `mod_ban`, `ban_prog`, `mod_prog` = correlação entre as próprias formas, sem medida):

| classe | modelo × bancada (k, limite de pico) | bancada × programada (TRACE 1024 pts) | modelo × programada |
|---|---|---|---|
| 03 | 1,000 | 1,000 | 1,000 |
| **05** | 1,000 | **0,518** | **0,518** (a "programada" é a CSINe, não o modelo) |
| 07 | 1,000 | 0,993–0,995 | 0,993–0,995 |
| 08 | 1,000 | 0,991–0,994 | 0,991–0,994 |
| 09 | 1,000 | 0,994–1,000 | 0,994–1,000 |
| 17 | 1,000 | 0,993–0,994 | 0,993–0,994 |

Leitura: a conversão para TRACE custa no máximo 0,007 nas seis classes (sem contar a 05, cuja programada é outra forma). O fator k e o limite de pico (08: 1,34 e 1,62 pu em vez de 6,4–7,3 pu, coluna `parametros` de `diag_causas.py`) não aparecem porque Pearson é cego à escala do distúrbio (`sinais.py:307-343`). [info] A perda por reamostragem existe de fato em classes não pedidas: 06 (flicker) tem `modelo × programada` 0,846–0,969, e a programada × medida da 06 é 0,969–0,991 (`diag_causas.py 06`); ou seja, a 06 perde sua correlação na TRACE por ciclo (um LIST:VOLTage e uma forma por ciclo não seguem uma modulação de 10–21 Hz), não na fonte. Fora do escopo pedido, registrado. [média]

Alinhamento: o lag de `analisar_offset` e o lag que maximiza a correlação (±80 amostras) coincidem em todas as capturas, exceto nas 08 a 50 Hz (coluna `lag_ao` x `lag_opt` de `diag_causas.py`; lá nenhum lag ajuda, ver 1.5) e 17-0003 a 60 Hz (lag −11 em ambos). Alinhamento de uma amostra e sub-amostra (atrasos fracionários de −1 a +1 amostra) ganham no máximo 0,003 (coluna `c_frac` de `diag_fisica.py`; 17-0003/60 Hz: +0,008). Erro de alinhamento não é causa em nenhuma das seis. [info]

### 1.2 O que sobra: programada × medida (resposta física, ruído, impulsos espúrios)

`diag_fisica.py`: `piso` = rms de (medida − programada) nos primeiros 56 ms da própria captura, antes de qualquer evento; `teto` = `sqrt(var_dist/(var_dist+piso²))` = correlação máxima se a programada fosse perfeita e só esse piso atrapalhasse. `diag_resposta_fonte.py`: ajuste por captura de um filtro linear de 2.ª ordem (fn 4–30 kHz, ζ 0,05–1, atraso −1…+1 amostra) aplicado à programada.

| classe | sessão | `programada × medida` (c0) | teto de ruído | com filtro 2.ª ordem | outro |
|---|---|---|---|---|---|
| 03 | 60 Hz / 50 Hz | 0,943 / 0,945 | 0,946 / 0,944 | 0,945 / 0,946 | zerando o erro a ±1,5 ms das bordas: 0,948 / 0,962 |
| 07 | 127 V/60 | 0,926–0,938 | 0,987–0,991 | 0,964–0,968 | bordas zeradas: 0,992 |
| 07 | 127 V/50 | 0,933–0,951 | 0,992–0,995 | 0,972–0,981 | bordas zeradas: 0,995 |
| 07 | 230 V/50 | 0,911–0,933 | 0,950–0,972 | 0,933–0,959 | bordas zeradas: 0,974 |
| 08 | 127 V/60 | 0,807–0,816 | 0,879–0,884 | 0,883–0,903 | |
| 09 | 127 V/60 | 0,885–0,911 | 0,909–0,941 | 0,885–0,912 | fundamental removida + impulso de 100 ms zerado: 0,941–0,950 |
| 09 | 127 V/50 | 0,750–0,798 | 0,819–0,830 | 0,750–0,800 | idem: 0,833–0,866 |
| 09 | 230 V/50 | 0,850–0,927 | 0,940–0,944 | 0,851–0,928 | idem: 0,899–0,943 |
| 17 | 127 V/60 | 0,935–0,948 | 0,984–0,993 | 0,973–0,974 | bordas zeradas: 0,993 |
| 17 | 127 V/50 | 0,932–0,937 | 0,975–0,978 | 0,959 | bordas zeradas: 0,977 |
| 17 | 230 V/50 | 0,915–0,929 | 0,950–0,962 | 0,934–0,947 | bordas zeradas: 0,955 |

(`teto` da 08 a 50 Hz não vale: a captura está desalinhada, ver 1.5.)

### 1.3 Classes 03, 07 e 17: ruído do CH1 e toque da fonte nas bordas

- **03**: modelo = bancada = programada (1,000 acima) e `programada × medida` 0,943/0,945 já está no teto de ruído (0,946/0,944). O swell é só 0,1 pu (rms do distúrbio 0,0325 pu, 0,1 pu pico), contra um piso de 0,0133–0,0136 pu medido na própria captura antes do evento (`diag_fisica.py`, coluna `piso`). Nenhuma correção de forma ajuda (polo + atraso: 0,945/0,946; 2.ª ordem: 0,945/0,946). O "sobressinal na borda de volta" a 60 Hz existe como erro de 0,115 pu em 1 amostra em 120,00 ms (`diag_picos_espurios.py`, linha 127 V/60 Hz 03-0001), mas zerá-lo só dá +0,005 (0,943 → 0,948). [baixa] Os 0,943–0,945 contra o 0,94 do professor são só arredondamento.
- **07 e 17**: o erro está nas bordas dos entalhes. 85–92 % da energia do erro fica a ±1,5 ms de uma borda a 127 V e 51–63 % a 230 V (`diag_fisica.py`, coluna `borda%`) e zerá-lo leva à correlação ao teto de ruído (0,992–0,995 a 127 V). O entalhe de 3 amostras (zero) sai da fonte como −0,24/+0,34/−0,36 pu (amostras 2416–2418 de 07-0001 a 127 V/60 Hz; programada −0,016/−0,003/−0,028), um toque. Um filtro linear de 2.ª ordem com fn ≈ 9–11 kHz e ζ ≈ 0,1–0,3 aplicado à programada recupera +0,02 a +0,04 (07: 0,926 → 0,965, 0,942 → 0,972 etc.). A mesma frequência aparece no código para a 08: `experimentos_waveform/08.py:28-30` ("oscilação de ~10 kHz"). Isso é física da fonte, e a conversão para TRACE só tira 0,005 (1.1). A faixa 5–8,5 kHz do espectro do erro tem 12–23 % da energia, e a >8,5 kHz tem 54–78 % (`fe_*`): é banda larga de borda, não só uma linha em 7,5 kHz. [média]
- **230 V/50 Hz** (07/17) fica 0,02–0,03 abaixo de 127 V na mesma conta; o teto de ruído é mais baixo (0,950–0,972) porque o k de bancada é 0,37–0,39 (`parametros`, `diag_causas.py`): o distúrbio é um terço do nominal. [baixa]

### 1.4 Classe 09: impulso espúrio em 100 ms e erro da fundamental

- **Impulso espúrio.** Em 9 de 9 capturas (3 sessões) a medida tem um impulso de 0,12 a 0,27 pu a 100,0–100,2 ms que a programada não tem (`diag_08_09.py`, seção 09; `diag_picos_espurios.py` lista o 100 ms entre os 2 maiores erros de todas as 09). A 50 Hz o início da oscilação (amostras 2401–2403: modelo +0,14/+0,25/+0,31, programada +0,13/+0,24/+0,31) sai ausente (medida +0,00/+0,02/+0,02) e reaparece 600 amostras (20 ms) depois, em 3001–3006 (0,07/0,25/0,30/0,30/0,29/0,13). A 60 Hz a oscilação aparece em 80 ms e uma cópia menor (0,04–0,18 pu) aparece em 100 ms. É o mesmo sintoma da 08 a 50 Hz (seção 1.5): o início do evento repetido 20 ms depois. Causa NÃO VERIFICADO: nenhum registro do instrumento (SCPI, osciloscópio) distingue a hipótese de TRACE/LIST (a de "ponto 0 da TRACE sai no fim do ciclo" levantada pelo professor, `atividade.tex`, seção da Pergunta 4) da de artefato de captura; a 60 Hz o início da oscilação cai no meio do ciclo (amostra 400 de 500), não em ponto 0, o que enfraquece a hipótese do ponto 0. Os valores LIST:VOLTage nos ciclos vizinhos mudam de 127,0 para 127,7 (50 Hz) / 127,2 (60 Hz) em 80 ms e voltam em 100 ms (`montar_programacao`, ver comando em 1.4.1), pequeno demais para explicar um pico de 0,27 pu. [alta: é um defeito do dado, não só da métrica]
- **Fundamental.** A fundamental medida é 0,6–1,4 % maior que a programada a 127 V (razão 1,0059–1,0138; 230 V: 1,001; coluna `amp_m/p` de `diag_fisica.py`). Como o distúrbio da 09 é pequeno (rms 0,0235 pu) e `correlacao_disturbio` subtrai uma senoide de 1 pu fixa, 1 % de diferença na fundamental deixa uma senoide de ~0,007 pu no resíduo medido que não existe no modelo. Tirar de cada sinal a sua fundamental ajustada (coluna `c_fund`) sobe 0,911 → 0,932, 0,885 → 0,939, 0,750 → 0,800, 0,798 → 0,855. Isso mostra que a métrica do professor (senoide nominal fixa) pune erro de amplitude da fonte. [média]
- Juntos (`c_fund+esp`): 127 V/60: 0,941–0,950 (teto 0,909–0,941); 127 V/50: 0,833–0,866 (teto 0,819–0,830); 230 V: 0,899–0,943 (teto 0,940–0,944). O piso de ruído da 09 a 127 V/50 Hz (0,0158–0,0165 pu) é o dobro do de 60 Hz (0,0084–0,0108 pu) na mesma tensão; por que a captura a 50 Hz é mais ruidosa NÃO VERIFICADO (não há log de escala vertical por classe analisado aqui).
- Frequência de oscilação (476–2069 Hz) e duração (16,5–23,1 ms): sem tendência visível nas 3 capturas por sessão (n = 3, pouco para concluir).

#### 1.4.1 Comando
`python docs/analise-2026-10-12/diag_08_09.py` e `diag_picos_espurios.py 09`. Os LIST:VOLTage por ciclo saem de `AmetekMX30.montar_programacao(bancada, base_voltage_rms=127, frequency_hz=f0).list_voltages_rms`: 50 Hz, 09-0001: 127,0 em todos exceto 127,7 no ciclo 4; 60 Hz: 127,0 exceto 127,3 e 127,2 nos ciclos 4 e 5.

### 1.5 Classe 08: impulso em 100 ms a 50 Hz; a 60 Hz é toque

- **127 V/50 Hz (0,004/0,005/0,011).** O pico medido está em 100,0 ms (99,90 a 100,00 ms) e o da programada em 80,00 ms (`diag_08_09.py`). Deslocando o resíduo da **programada** em +600 amostras (20 ms) a correlação passa de 0,028 para **0,664/0,680/0,716**, e com o filtro linear de 2.ª ordem (fn 11 kHz, ζ 0,1) para **0,877/0,877/0,867**. O professor mediu 0,6 só com o desvio (`atividade.tex`, comentário da Pergunta 4). Confirmado. [alta]
- **127 V/60 Hz (0,824–0,831).** O impulso está em 80,0 ms (pico 80,00/80,00/79,97 ms); nada de desvio. A perda é só resposta da fonte: programada × medida 0,807–0,816 e 0,883–0,903 com filtro de 2.ª ordem (fn 11–12 kHz, ζ 0,10–0,15; as capturas do 08 a 60 Hz têm teto de ruído 0,88). O 0,82–0,83 não é o 0,005 do professor: a sessão 127 V/60 Hz tem o pulso capturado, e a de 127 V/50 Hz não.
- Pearson é cego à escala: a 60 Hz o pico medido (1,66–1,93 pu, `diag_08_09.py`) varia 15 % entre capturas com a mesma amplitude de bancada (1,62 pu, `parametros.amplitude_bancada_pu`), o que não aparece na correlação. [info]

### 1.6 Tabela classe × causa × correlação antes/depois

"antes" = `modelo × medida` do terminal (`analisar_sessao`); "depois" = depois de corrigir **só aquela causa**, na ordem da coluna (a 05 muda o modelo; as demais mudam o que se compara, não o dataset).

| classe | causa principal medida | correlação antes (60 Hz / 50 Hz / 230 V) | depois de corrigir a causa | quanto da perda explica |
|---|---|---|---|---|
| 03 | piso de ruído do CH1 sobre swell de 0,1 pu; forma, TRACE, alinhamento e filtro não contribuem | 0,943 / 0,945 / — | não há correção: 0,945 / 0,946 (teto 0,946 / 0,944) | 100 % no piso de ruído |
| **05** | **forma do modelo diferente da programada** (3.ª/5.ª/7.ª somadas × senoide grampeada; 5.ª com sinal trocado); a programada está certa | 0,503 / 0,504 / 0,499 | **0,974 / 0,974 / 0,964** com `gerar_csine` (teto de ruído 0,973 / 0,974 / 0,964) | ~100 % do 0,47 perdido |
| 07 | toque da fonte (9–11 kHz) nas bordas dos entalhes; conversão TRACE −0,005 | 0,912–0,924 / 0,916–0,942 / 0,899–0,922 | com 2.ª ordem: 0,964–0,968 / 0,972–0,981 / 0,933–0,959 | ~0,03 do 0,07–0,09 (o resto é ruído nas bordas, bordas zeradas dão 0,992–0,995) |
| 08 | 50 Hz: impulso 20 ms atrasado; 60 Hz: toque (~11 kHz) | 0,824–0,831 / 0,004–0,011 / — | 60 Hz: 0,883–0,903 (2.ª ordem); 50 Hz: 0,664–0,716 (desvio de 600 amostras) e 0,867–0,877 (desvio + 2.ª ordem) | 50 Hz: quase tudo no desvio (0,66 de 0,99); 60 Hz: ~0,07 de 0,18 no toque |
| 09 | impulso espúrio em 100 ms (0,12–0,27 pu) + erro de fundamental 0,6–1,4 % + piso de ruído (distúrbio 0,0235 pu rms) | 0,883–0,910 / 0,749–0,797 / 0,850–0,925 | fundamental + impulso: 0,941–0,950 / 0,833–0,866 / 0,899–0,943 | ~0,05–0,09 em 60/50 Hz; resto é ruído (teto 0,82–0,94) |
| 17 | idem 07 (bordas dos entalhes + oscilação de 300 Hz) | 0,921–0,931 / 0,914–0,923 / 0,902–0,918 | com 2.ª ordem: 0,973–0,974 / 0,959 / 0,934–0,947 | ~0,02–0,04 de 0,07–0,09 |

Todas as correções da tabela, exceto a 05, são contrafactuais de análise: não existe programação a mudar para elas (toque, ruído, impulso espúrio da fonte).

Cuidado com "depois" da 05: 0,974 está no teto de ruído, não no teto de 1,0.

## 2. A CSINe da fonte (05, THD 5 %)

Script: `diag_csine.py` (3 capturas, uma por sessão; ciclo médio de 10–12 ciclos).

**Manual**: `FUNCtion:CSINusoid` = "clipping level expressed as the percentage of total harmonic distortion in the output voltage. The range is 0 to 20 percent" e "both positive and negative peak amplitudes are clipped at a value determined by" esse valor (`docs/analise-2026-09-21/manuais_txt/AMETEK_MX_SCPI_Programming_Manual.txt:3699-3701,3755-3759`). O código: `ametek_orm.py:902-950` (`configure_harmonics_csine`, teto `MAX_CSINE_THD_PCT = 20.0` na linha 156).

Medidas (127 V/50 Hz; 60 Hz e 230 V dão o mesmo dentro de 0,0005 em amplitude):

| h | amp/h1 medida | amp/h1 senoide grampeada a 5 % | fase relativa medida (graus) | idem grampeada | modelo atual (`05.py:39-48`) |
|---|---|---|---|---|---|
| 3 | 0,0408 | 0,0405 | −180 | −180 | 0,0288 (fase 180) |
| 5 | 0,0266 | 0,0263 | **180** | 180 | 0,0144 (fase **0**: sinal trocado) |
| 7 | 0,0108 | 0,0116 | 178 | 180 | 0,0048 (fase 180) |
| 9 | 0,0010 | 0,0009 | 177 | 180 | — |
| 11 | 0,0037 | 0,0039 | 5 | 0 | — |
| 13 | 0,0033 | 0,0037 | −1 | 0 | — |
| pares (2–14) | ≤ 0,0005 | 0 | — | — | — |

(fase relativa = fase(h) − h·fase(1), as 3 sessões na saída do script.) A senoide grampeada simétrica explica o espectro medido harmônico a harmônico até a 15.ª: amplitudes dentro de 0,001 do fundamental e fases em 0° ou 180° como as da grampeada, não com a 5.ª em 0° como o modelo. Isso confirma, com número, a observação do professor (5.ª com sinal trocado). Pares ≤ 0,0005 mostram simetria positiva/negativa.

- **THD medida**: 5,03/5,03/5,04 % (ciclo médio) contra 5,00 pedido; `validacao_fisica.thd_medida` do metadata de 127 V/50 Hz dá 5,019 % (`metadata/05_harmonics.jsonl`).
- **Nível de corte**: ajuste livre `s·clip(sin(θ+φ), −c, c)` dá **c = 0,8825** nas 3 sessões; o c que dá THD = 5 % por bisseção é **0,8834** (`sinais.py:368-383`). Diferença de 0,1 %.
- **rms preservado pela fonte**: rms do CH1 na 05 / rms na 01 (senoide pura) = 1,0023 / 1,0015 / 1,0065. A normalização da `senoide_clipada_pu` para o rms da senoide (comentário NÃO VERIFICADO em `sinais.py:386-388`) fica verificada para a CSINusoid interna a ±0,7 %. O ajuste livre dá escala s = 1,052 (127 V) e a normalização por rms dá 1,048. Pico programado 0,926 pu = c·s.
- **Pico medido 0,946–0,963 contra programado 0,926** (`docs/tres_versoes.md`, "O que não está confirmado"): na 01 (senoide pura, mesma sessão) a medida sai com pico 1,014–1,052 pu para um pico nominal de 1,000 pu (saída de `diag_csine.py`, linha `pico 05 ... 01 ...`), ou seja, 1–5 % de excesso de pico que a captura tem para qualquer forma. Não é a CSINe. [info]
- **Ruído**: desvio ciclo a ciclo 0,0066–0,0075 pu; erro rms do ajuste livre 0,0020–0,0027 pu, abaixo do ruído: a forma grampeada explica a medida até o ruído.
- **Em função da THD**: só 5 % foi capturado. Para os demais níveis só há a conta (bisseção): corte c = 0,778 (10 %), 0,674 (15 %), 0,569 (20 %); 30 % daria c = 0,361 (fora do alcance da CSINe, é TRACE). NÃO VERIFICADO na bancada para 10, 15 e 20 %: nenhuma captura existe (ver "Pedido"). `corte_da_senoide_clipada` (`sinais.py:368-383`) recusa THD > 0,25.

## 3. `gerar_csine` e a correlação dela na 05

### Função

```python
def corte_para_thd(thd, n=8192):
    """Nivel de corte c (pu do pico da senoide) tal que clip(sin,-c,c) tem a THD pedida."""
    th = np.sin(2 * np.pi * np.arange(n) / n)
    lo, hi = 0.05, 1.0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        a = np.abs(np.fft.rfft(np.clip(th, -m, m)))
        lo, hi = (m, hi) if np.sqrt(np.sum(a[2:] ** 2)) / a[1] > thd else (lo, m)
    return 0.5 * (lo + hi)


def gerar_csine(t, f0, thd, fase_graus=0.0, normalizacao="rms"):
    """Senoide grampeada simetricamente (clip duro) cuja THD e 'thd' (fracao).
    'rms': escala para o rms da senoide de pico 1 (1/sqrt 2), o que a fonte faz;
    'pico': nao escala (pico = nivel de corte c)."""
    c = corte_para_thd(thd)
    x = np.clip(np.sin(2 * np.pi * f0 * t + np.radians(fase_graus)), -c, c)
    if normalizacao == "rms":
        ciclo = np.clip(np.sin(2 * np.pi * np.arange(8192) / 8192), -c, c)
        x = x / (np.sqrt(2) * np.sqrt(np.mean(ciclo ** 2)))
    return x
```

(`docs/analise-2026-10-12/diag_csine.py`.) **Achado:** isto já existe no código de hoje como `sinais.senoide_clipada_pu` (`logica/sinais.py:385-393`) mais `corte_da_senoide_clipada` (`:368-383`), usadas como forma programada da 05 (`sinais.py:441-442`). A diferença máxima entre as duas é 4·10⁻⁷ pu (`np.abs(gerar_csine(...)-senoide_clipada_pu(...)).max()`, THD 5/10/20 %, 50 e 60 Hz). A "função nova" é, portanto, só passar a chamá-la em `gerar()`; a análise confirma que ela é a certa. [média]

### Correlação do distúrbio contra a captura da 05 (`python docs/analise-2026-10-12/diag_csine.py`)

| candidato | 127 V/60 | 127 V/50 | 230 V/50 | pico (pu) |
|---|---|---|---|---|
| modelo atual (3.ª/5.ª/7.ª) | 0,503 | 0,504 | 0,499 | 0,9705 |
| **`gerar_csine`, normalizada por rms** | **0,974** | **0,974** | **0,964** | 0,9258 |
| `gerar_csine` sem escala (pico = c) | 0,669 | 0,674 | 0,617 | 0,8834 |
| ajuste livre (s, c; teto da família) | 0,982 | 0,981 | 0,992 | 0,928–0,931 |

- A normalização importa: sem escalar pelo rms, a fundamental sai 5 % menor e o resíduo (medida − senoide de 1 pu) carrega esse erro (0,67). Quem adotar `gerar_csine` em `gerar()` tem de usar a escala por rms, como a fonte faz.
- 0,974 está no teto de ruído da captura (0,973/0,974/0,964; `diag_fisica.py`, linhas 05). O ajuste livre sobe 0,008 a 0,028, quase todo ruído.

### Comparação com "todos os níveis por TRACE" (`diag_csine_trace.py`)

Conversão para TRACE de 1024 pontos e volta (`montar_programacao`): 1,0000 para o modelo atual e para a grampeada nos 5 níveis, em 50 e 60 Hz. Sem bordas, a 05 não perde nada ali. Diferença entre o modelo atual e a CSINe, por nível (calculada, não medida): 0,518 (5 %), 0,663 (10 %), 0,783 (15 %), 0,881 (20 %), 0,981 (30 %). Ou seja, o 0,50 do professor é o pior caso; a 20 % o modelo atual daria 0,88 contra a CSINe e a 30 % (já via TRACE) a forma é praticamente igual. Picos de bancada do modelo atual via TRACE: 0,971 (5 %) a 0,825 pu (30 %), com folga sob o teto de 425 Vp.

Evidência indireta de que TRACE com harmônicas reproduz bem na fonte: classes 10, 13 e 16 (THD 20 % em TRACE): `programada × medida` 0,996–1,000 a 127 V/50 Hz, 0,997–0,999 a 127 V/60 Hz, 0,997–0,998 a 230 V (`diag_causas.py 10 13 15 16`). Nenhuma captura de 05 via TRACE existe, então a correlação da 05 por TRACE é **NÃO VERIFICADO**; o que se sabe: a conversão é de 1,0000 e a fonte reproduz bem harmônicas por TRACE nas classes com 20 % de THD. [média]

Comparação:
- **CSINe no modelo**: 0,964–0,974 medido. Muda o dataset da 05 (`gerar()` passa a dar a senoide grampeada), o que `AGENTS.md` (autorização de 2026-10-07) proíbe nos `experimentos_*`: "nunca mudando o que `gerar()` produz para uma dada seed"; precisa de autorização do dono. Mantém a fonte nativa (rápida, sem gravar TRACE em Flash, com o teto de 20 %).
- **Tudo por TRACE** (30 % já é): mantém o gêmeo sintético exato (`gerar()` não muda) e conversão 1,0000. Custa gravar a TRACE em Flash (~3 s por TRACE nova na conexão, `ametek_orm.py` ~1305; depois só `TRACe:DATA`) e a correlação esperada é > 0,99 mas não foi medida para a 05. Gera forma por TRACE em vez de função nativa documentada.
- Sobre o pedido do professor "ou o modelo é a CSINe, ou todos os níveis vão por TRACE": os dois funcionam; a diferença é qual das duas formas vira o dataset. Existe, em dado de verdade, só a primeira.

## 4. Recomendação por classe

| classe | o que fazer |
|---|---|
| 03 | Aceitar e documentar: no teto de ruído do CH1 (0,945 contra teto 0,944–0,946); swell de 0,1 pu contra piso de 0,013 pu. |
| 05 | Mudar o modelo: usar `sinais.senoide_clipada_pu` (normalizada por rms) em `gerar()` para os níveis ≤ 20 % (0,50 → 0,96–0,97), ou mandar todos por TRACE; escolha do dono, ver seção 3. O nível de 30 % continua por TRACE. |
| 07 | Aceitar e documentar como toque da fonte (fn ≈ 9–11 kHz, ζ ≈ 0,1–0,3) nas bordas dos entalhes de 3 amostras; usar `razao_pico`/corr. com filtro de 2.ª ordem se se quiser um número de "forma". |
| 08 | A 50 Hz: corrigir a posição (impulso sai 20 ms depois) como já está previsto em outra spec; a 60 Hz aceitar como toque (~11 kHz). |
| 09 | Investigar o impulso de 100 ms (todas as capturas, 0,12–0,27 pu) antes de usar a classe em treino; acrescentar uma checagem de fundamental ao lado da correlação do distúrbio (ver "Métrica"). |
| 17 | Idem 07 (toque nas bordas dos entalhes), a oscilação de 300 Hz não pesa. |

**Métrica**: a correlação do distúrbio subtrai uma senoide de 1 pu fixa. Uma diferença de 1 % na fundamental (frequente, 0,2–1,4 % a 127 V) pesa até 0,05–0,06 em classes de distúrbio pequeno (09: 0,885 → 0,939). Sugestão: relatar também o valor depois de ajustar a fundamental de cada sinal (coluna `c_fund` de `diag_fisica.py`). [média]

## NÃO VERIFICADO

- Causa do impulso replicado 20 ms depois do início do evento (08 a 50 Hz, 09 em todas): não há registro de instrumento que diferencie TRACE/LIST de artefato de captura. As hipóteses "ponto 0 da TRACE" (professor) e "degrau de LIST:VOLTage no limite de ciclo" não bastam sozinhas (a 60 Hz o início cai no meio do ciclo; os degraus são de 0,2–0,7 V).
- CSINe em 10, 15 e 20 %: sem capturas; as cutoffs c = 0,778/0,674/0,569 e o modelo de rms são previsões do ajuste a 5 %.
- 05 por TRACE na bancada (todos os níveis): sem captura; só o proxy das classes 10/13/16.
- Por que o piso de ruído da 09 a 127 V/50 Hz é o dobro do de 60 Hz (escala vertical por classe e probe não analisadas).
- Se as faixas do professor (0,75–0,94 em 03/07/09/17) saíram dessas mesmas capturas: `validacao_gerador_v1.14.md` não está no repositório.
- O filtro de 2.ª ordem é um ajuste empírico (fn, ζ, atraso por captura, 1215 combinações); não prova que a fonte seja um 2.º polo, só que o erro é majoritariamente linear.
- Não analisadas aqui: 06 (perda na TRACE por ciclo, ver 1.1), 20 a 60 Hz, 02/04/10–16/18/19.

## Arquivos

`diag_comum.py` (carregador), `diag_causas.py`, `diag_fisica.py`, `diag_resposta_fonte.py`, `diag_picos_espurios.py`, `diag_08_09.py`, `diag_csine.py`, `diag_csine_trace.py`.
