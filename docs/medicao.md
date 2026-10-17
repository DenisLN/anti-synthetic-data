# Medição: cadeia, janela, margens e pré-trigger

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Lido no código em 2026-10-16 (`main` em `fa82f49`); os números de bancada são de 30/09 e 07/10/2026 (código anterior à v1.15). {bdg-warning}`NÃO VERIFICADO` Margens, pré-trigger sorteado e `inicio_janela` com o código da v1.15 não foram medidos na bancada (P-01, P-05).

**Pergunta:** como o que a fonte emite vira as 6000 amostras rotuladas de uma captura? **Resposta:** o osciloscópio grava um **registro maior** que a janela (20 ms antes e 50 ms depois: 8100 amostras a 30 kSa/s), a preamble diz **em que amostra caiu o trigger**, e o código recorta a **janela nominal** de 6000 amostras a partir de `inicio_janela = indice_trigger − pre_trigger_s · fs`; o ruído de 20/30/40 dB entra só nessa janela e o ruído próprio da bancada é medido na margem.

## 1. A cadeia de medição

```{mermaid}
flowchart LR
    F["Fonte MX30-3Pi<br/>(saída em V)"] --> P["Probe diferencial<br/>fator digitado no START_BENCH"]
    P --> C["CH1 do Keysight<br/>8 bits, escala pico/3"]
    C --> R["registro bruto<br/>cerca de 116,7 kSa/s"]
    R --> I["interpolação linear<br/>para 30 kSa/s (K4)"]
    I --> E["registro de 8100 amostras<br/>(20 ms + 200 ms + 50 ms)"]
    E --> J["janela nominal<br/>6000 amostras"]
    F -. "BOT pelo BNC" .-> T["EXT Trigger"]
    T --> C
```

- **Probe.** O fator digitado tem de ser exatamente o da chave; o erro dele é o único que a validação física só denuncia depois. Em 07/10/2026 um disjuntor aberto fez a fonte medir 126,6 V nela mesma e o CH1 cerca de 0,45 vezes isso mais 7,9 Vrms induzidos da rede (B1). A **checagem da cadeia** antes da primeira classe (fonte dentro de 5 % da base e CH1/fonte dentro de 10 %) existe por isso ({doc}`codigo/mestre`, `verificar_cadeia_de_medicao`).
- **Resolução.** Com a sonda de 500× e 8 bits de resolução vertical, 9 V de CC na escala de 180 V de pico fica no fundo de escala (erro de 4,35 V só do offset da probe, B5): a medida absoluta de CC não é confiável e a classe 19 usa a medida da fonte.
- **Reamostragem.** O vetor devolvido é a interpolação linear do registro bruto para 30 kSa/s, sem anti-aliasing (K4, P-28); os extremos de segurança vêm do instrumento, no registro bruto (K7).
- **Ruído da bancada.** 32 a 42 dB de SNR já existem antes do ruído acrescentado (B6): o "40 dB" é o acrescentado; `snr_bancada_db` e `snr_efetivo_db` ficam no metadata.

## 2. A janela e as margens

**Por que existe a margem?** Nas primeiras inspeções (v1.7 e v1.8, setembro de 2026) a forma parecia **20 ms atrasada**; na v1.10 pareceu **100 ms** atrasada. A análise de 21/09/2026 achou que os dois "atrasos" eram o mesmo artefato: `:TIMebase:REFerence LEFT` fica a uma divisão (10 % do `RANGe`) da borda esquerda, não na borda (H-REF10, K1); a fonte, tocando com `LIST:REPeat 1`, ainda repetia cada ciclo duas vezes (A4). Corrigidos os dois, a folga necessária passou a ser **medida**, não adivinhada: o fim de evento mais tardio das duas sessões de 16/09 foi 116,7 ms após o trigger, e o conteúdo programado termina em 200 ms; 50 ms depois cobrem o retorno ao regime e o sobre-pico nas bordas. A margem ficou, por decisão de projeto (v1.11, 22/09/2026), em **20 ms antes e 50 ms depois**, sempre aplicada em captura física, e **não deve ser reduzida sem refazer a medida**.

| Trecho | Amostras (30 kSa/s) | Origem |
|---|---|---|
| margem antes | 600 (20 ms) | `MARGEM_ANTES_S = 0,020` |
| janela nominal | 6000 (200 ms) | `Config.points` |
| margem depois | 1500 (50 ms) | `MARGEM_DEPOIS_S = 0,050` |
| **registro** | **8100** | `ExperimentoBase._calcular_margem` |

O dataset **simulado** nunca teve margem: `_calcular_margem(captura_fisica=False)` devolve `(0, 0, 6000)`.

## 3. Pré-trigger e onde o trigger caiu

- **Pré-trigger da classe.** Nas classes de pulso (02, 03, 04) o evento começa 60 ms depois do início da janela (`pre_trigger_s = 0,060`); nas demais, 0 (o trigger é o início). Para o osciloscópio, o pré-trigger efetivo é `pre_trigger_s + margem_antes / fs`.
- **Pré-trigger sorteado (v1.15).** Com o sorteio ligado, `_capturar_real` das nativas chama `definir_pre_trigger` por captura, com o `inicio_disturbio_s` que `gerar()` sorteou (mais a margem). O instrumento posiciona o trigger; **quem diz onde ele de fato caiu é a preamble.**
- **`indice_trigger`.** `get_waveform` guarda `x_origin` (instante, relativo ao trigger, da primeira amostra) e calcula `ultimo_indice_trigger = round(−x_origin · 30000)`. `mestre` grava `indice_trigger` no metadata; é a única informação que diz onde o trigger caiu dentro do registro. Se o desvio contra o pretendido passa de 2 amostras, o metadata registra `pre_trigger_desvio_amostras` e o log avisa; o recorte segue o trigger **real**.
- **`inicio_janela`.** `inicio_janela = round(indice_trigger − pre_trigger_s · fs)`, limitado a `[0, amostras_totais − 6000]` (a mesma conta de `sinais.janela_nominal`); `inicio_janela_ajustado` é verdadeiro quando o limite agiu.

```{literalinclude} ../logica/sinais.py
:pyobject: janela_nominal
:language: python
:caption: logica/sinais.py, janela_nominal
```

## 4. O que a validação física compara (e em qual recorte)

`ExperimentoBase._validar_fisicamente` compara a forma **realmente programada** com `medido[margem_antes : margem_antes + 6000]` (envelope, THD e crista) e, na 08, confere a posição do impulso na janela alinhada ao trigger real. Os 20 ms em 0 V (saída antes do transiente) reprovavam o mínimo do envelope de toda captura (0,01 pu na sessão de 30/09) e os 50 ms extras quebravam o número inteiro de ciclos da THD (1,60 % contra 0,28 % na janela alinhada): daí o recorte. Detalhes em {doc}`codigo/percurso-captura-trace`.

## 5. Onde continuar

- A correlação entre as três versões e o que esperar por classe: {doc}`medicao/correlacao`.
- Os fatores de extremo e a recalibração: {doc}`medicao/recalibracao`; limites e pré-validação: {doc}`limites_e_calibracao`.
- Recortar a margem de uma sessão: `logica/recortar_margem.py` ({doc}`codigo/recortar_margem`).
- Quirks do osciloscópio (K1 a K10): {doc}`quirks`.

```{toctree}
:maxdepth: 1

medicao/correlacao
medicao/recalibracao
correlacao_disturbio
```
