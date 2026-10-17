# sinais.py: matemática de sinal pura

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Lido em 2026-10-16 (`main` em `fa82f49`).

**Pergunta:** o que há em `logica/sinais.py` e por que ele não importa nada do projeto? **Resposta:** são as funções "array entra, array ou número sai" que as 20 classes (no `gerar()` do dataset simulado) e a bancada (na validação física e na análise offline) precisam em comum: entalhes, oscilação amortecida, ruído com SNR por construção, janela nominal, validação física (envelope, THD, crista) e as duas métricas de correlação do distúrbio. Não importa `mestre`, nem `perfis`, nem hardware: por isso é testável sozinho e reaproveitável por scripts offline.

| Símbolo | Assinatura | Linha | Papel |
|---|---|---|---|
| `tempo` | `(config) -> np.ndarray` | [sinais.py:16-17](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L16-L17) | eixo de tempo `arange(points)/fs_hz` de uma `Config` |
| `janela` | `(t: np.ndarray, inicio_s: float, duracao_s: float) -> np.ndarray` | [sinais.py:20-21](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L20-L21) | máscara booleana `inicio ≤ t < inicio + duração` |
| `valor_para_captura` | `(rng: np.random.Generator, lo: float, hi: float, capture_index: int, total_capturas: int, *, cobertura_ativa: bool) -> float` | [sinais.py:24-49](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L24-L49) | sorteio `uniform(lo, hi)` ou cobertura determinística `linspace` com `set capturas N` |
| `onda_com_harmonicos` | `(t: np.ndarray, thd_fracao: float, *, frequencia_hz: float) -> np.ndarray` | [sinais.py:52-62](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L52-L62) | fundamental mais 3.ª, 5.ª e 7.ª na razão 0,6 : 0,3 : 0,1 normalizada ao THD pedido |
| `aplicar_entalhes` | `(sinal: np.ndarray, t: np.ndarray, rng: np.random.Generator, *, frequencia_hz: float, inicio_s: float=0.06, duracao_s: float=0.08) -> int` | [sinais.py:65-89](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L65-L89) | 2 a 4 pulsos de 0,1 ms por ciclo, nos picos, em `duração` a partir de `início` (modelo legado, 4 ciclos) |
| `aplicar_entalhes_continuos` | `(sinal: np.ndarray, t: np.ndarray, rng: np.random.Generator, *, frequencia_hz: float, origem_s: float) -> int` | [sinais.py:92-128](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L92-L128) | a mesma regra em TODOS os ciclos da janela (IEEE 1159-2019, 4.4.5.4); consome o `rng` também fora da janela |
| `oscilacao_amortecida` | `(t: np.ndarray, *, inicio_s: float, duracao_s: float, frequencia_hz: float, amplitude_pu: float=0.3, tau_s: float=0.005) -> np.ndarray` | [sinais.py:131-146](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L131-L146) | `A·sin(2πf t)·exp(−t/τ)` com A = 0,3 pu e τ = 5 ms |
| `ruido_awgn` | `(sinal: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray` | [sinais.py:149-155](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L149-L155) | ruído com SNR esperado (usado fora da bancada) |
| `semente_do_ruido` | `(seed: int, snr_db: float) -> int` | [sinais.py:175-178](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L175-L178) | `seed + round(snr_db·1000) + 50000000`: definição única da semente |
| `medir_ruido_da_bancada` | `(registro: np.ndarray, inicio: int, pontos: int, *, minimo_amostras: int=MINIMO_AMOSTRAS_RUIDO_BANCADA) -> Optional[Dict[str, object]]` | [sinais.py:196-225](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L196-L225) | ruído próprio da bancada pela segunda diferença na margem |
| `ruido_na_janela` | `(registro: np.ndarray, inicio: int, pontos: int, niveis_db: Iterable[float], seed: int, *, simulado: bool=False) -> Dict[str, object]` | [sinais.py:228-286](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L228-L286) | AWGN com potência EXATA `P_ref/10^(snr/10)` só na janela rotulada; devolve três SNRs |
| `envelope_rms_meio_ciclo` | `(x: np.ndarray, *, fs_hz: float, f0: float) -> np.ndarray` | [sinais.py:289-300](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L289-L300) | rms de cada meio ciclo (vê sag, swell, interrupção) |
| `fator_de_crista_do_ciclo_mediano` | `(x: np.ndarray, *, fs_hz: float, f0: float) -> float` | [sinais.py:303-330](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L303-L330) | mediana do pico/rms por ciclo |
| `thd_medida` | `(x: np.ndarray, *, fs_hz: float, f0: float, max_harmonica: int=40) -> float` | [sinais.py:333-357](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L333-L357) | THD por FFT sobre número inteiro de ciclos |
| `comparar_fisicamente` | `(esperado: np.ndarray, capturado: np.ndarray, *, fs_hz: float, f0: float, tol_envelope: float=0.15, tol_crista: float=0.1, tol_thd: float=0.2, piso...` | [sinais.py:360-456](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L360-L456) | a validação física: envelope, THD e crista (aceitando o toque da fonte por `fator_crista`) |
| `janela_nominal` | `(registro: np.ndarray, *, indice_trigger: int, pre_trigger_s: float, pontos: int, fs_hz: float) -> np.ndarray` | [sinais.py:459-476](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L459-L476) | recorte de `pontos` amostras a partir de `indice_trigger − pre_trigger·fs` |
| `LIMITE_RESIDUO_DEGENERADO_PU` | (constante ou variável de módulo) | [sinais.py:482](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L482) | 1e-6 pu: abaixo disto não há componente de distúrbio |
| `correlacao_disturbio` | `(esperado: np.ndarray, capturado: np.ndarray, *, fs_hz: float, f0_hz: float, fase_graus: float=0.0) -> Tuple[Optional[float], Optional[str]]` | [sinais.py:485-521](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L485-L521) | Pearson do resíduo depois de subtrair a senoide nominal |
| `correlacao_disturbio_fundamental_ajustada` | `(esperado: np.ndarray, capturado: np.ndarray, *, fs_hz: float, f0_hz: float) -> Tuple[Optional[float], Optional[str]]` | [sinais.py:535-571](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L535-L571) | idem, ajustando a fundamental de cada sinal |
| `FORMA_NATIVA_POR_CLASSE` | (constante ou variável de módulo) | [sinais.py:584](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L584) | mecanismo nativo por classe (01 STEP ... 19 STEP+OFFSet) |
| `corte_da_senoide_clipada` | `(thd_fracao: float) -> float` | [sinais.py:596-610](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L596-L610) | bisseção do corte `c` que dá o THD pedido (recusa > 25 %) |
| `senoide_clipada_pu` | `(t: np.ndarray, f0_hz: float, tau_s: float, thd_fracao: float) -> np.ndarray` | [sinais.py:613-621](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L613-L621) | senoide clipada com THD pedido e o rms da senoide de pico 1 |
| `forma_programada_nativa` | `(id_classe: str, *, t: np.ndarray, f0_hz: float, base_voltage_rms: float, parametros: dict, quantizar, inicio_legado_s: float \| None=None, duracao_...` | [sinais.py:624-683](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L624-L683) | a forma ideal para os comandos enviados nas classes nativas |

## 1. Fluxo de dados

```{mermaid}
flowchart LR
    G["gerar() das classes<br/>(onda_com_harmonicos, aplicar_entalhes*, oscilacao_amortecida)"] --> M["modelo (pu)"]
    M --> V["comparar_fisicamente<br/>(mestre._validar_fisicamente)"]
    M --> R["ruido_na_janela<br/>(snr_XXdb/)"]
    M --> C["correlacao_disturbio*<br/>(analisar_sessao)"]
    N["forma_programada_nativa"] --> P["programada (nativas)"]
```

## 2. As intricâncias

**Janela nominal.** `janela_nominal` recorta do registro bruto `pontos` amostras a partir de `round(indice_trigger − pre_trigger_s·fs_hz)`, limitado a `[0, tamanho − pontos]`. O índice do trigger vem da preamble do osciloscópio ({doc}`oscilloscope_orm`); usar `margem_amostras_antes` como se fosse o trigger errava por `janela/10` (H-REF10).

**Ruído com SNR exato.** `ruido_na_janela` não usa `ruido_awgn`: gera um vetor normal com a semente de `semente_do_ruido`, e o **reescala** para a potência exata `P_ref/10^(snr/10)` na janela. O SNR acrescentado é o nominal **por construção**, não só em esperança. Mede também o ruído próprio da bancada pela **segunda diferença** (`x[n] − 2x[n+1] + x[n+2]`, variância `6σ²` para ruído branco), que ignora o offset CC do osciloscópio e a senoide de 50/60 Hz (cerca de 1e-4 pu). O metadata grava três SNRs: acrescentado, da bancada e efetivo (potências somadas).

**Validação física.** `comparar_fisicamente` compara a medida com a forma que foi **realmente programada** por quatro sondas insensíveis ao alinhamento: mediana, mínimo e máximo do envelope rms de meio ciclo (tolerância 15 % com piso de 5 % da mediana, para a interrupção cujo mínimo é cerca de 0), THD (20 %, piso de 1 ponto percentual) e **crista do ciclo mediano**. A crista é bilateral e aceita `[c·(1−tol), c·fator·(1+tol)]`: o `fator_crista` vem da calibração de extremos ({doc}`../medicao/recalibracao`).

**Correlação do distúrbio.** Definição, caso degenerado e tabelas por classe em {doc}`../medicao/correlacao`. `correlacao_disturbio` exige `esperado` e `capturado` na mesma grade (o alinhamento é de `analisar_sessao`).

**Forma programada das nativas.** `forma_programada_nativa` reconstrói o que a fonte emitiria para os comandos enviados: nível truncado a 0,1 V (`quantizar`), PULSe em `[início, início + duração)`, senoide clipada no THD pedido (05), rampa de frequência **em degrau** (18: `start_hz` na 1.ª metade, `end_hz` na 2.ª) e o offset enviado (19, `%.8g`).

## 3. Armadilhas

1. `aplicar_entalhes_continuos` consome o `rng` também para ciclos **fora** da janela, de propósito, para a forma não depender de onde a janela corta. Mudar o número de chamadas por ciclo muda todas as formas das classes 07 e 17 (fixtures).
2. `corte_da_senoide_clipada` recusa THD acima de 25 %, então `forma_programada_nativa("05")` falharia para o nível de 30 %: ele só é chamado para os níveis nativos (o de 30 % vai por TRACe).
3. `thd_medida` exige pelo menos 2 ciclos inteiros.
4. A validação é **insensível ao alinhamento** de propósito; a posição do evento é conferida à parte (`conferir_posicao_do_evento`, 08).
5. `FORMA_NATIVA_POR_CLASSE` e `forma_programada_nativa` precisam conhecer toda classe nativa nova (uma 21.ª classe também exige `mestre`, `cli.py` e os testes: {doc}`classes_contrato`).
6. `onda_com_harmonicos` normaliza os coeficientes pela norma de `[0,6; 0,3; 0,1]`, de modo que a soma quadrática é exatamente o THD pedido, mas a **fundamental permanece 1 pu**: o rms cresce com o THD (0,738 pu a 30 %). O modelo da 05 com sorteio usa `senoide_clipada_pu`, não esta função.

## 4. Por que é assim

- **Entalhes contínuos (v1.15).** A norma descreve notching periódico e contínuo; o modelo antigo entalhava só 4 ciclos. Com o toque da fonte (cerca de 10 kHz) a crista medida da 07 e da 17 fica 31 a 59 % acima da ideal (simulação), o que levou a validação da crista a usar a calibração.
- **Ruído só na janela (v1.15).** A margem de captura não pertence ao rótulo; a potência de referência é `mean(janela²)`.
- **A senoide clipada tem o rms da senoide de pico 1** porque a fonte escala a forma para o rms programado: garantido pelo manual para TRACes de usuário, {bdg-warning}`NÃO VERIFICADO` para a CSINusoid interna (P-10).
