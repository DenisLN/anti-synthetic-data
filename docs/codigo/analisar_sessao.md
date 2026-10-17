# analisar_sessao.py: análise offline de uma sessão

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Lido em 2026-10-16 (`main` em `fa82f49`); executado nas três sessões de 07/10/2026 ({doc}`../medicao/correlacao`).

**Pergunta:** o que `analisar_sessao.py` calcula e o que ele pressupõe? **Resposta:** para cada captura de bancada de uma pasta de sessão, **reconstrói a forma esperada** (`gerar()` com a seed e os parâmetros do metadata, e a redução do limite de bancada, se houve), alinha a medida pelo trigger real e devolve o `lag` (correlação cruzada por FFT), a correlação total, a **correlação do distúrbio** (nominal e com a fundamental ajustada) e a razão de pico. Não usa hardware nem `scipy`; roda em qualquer máquina com os `.npz` e os `.jsonl`.

| Símbolo | Assinatura | Linha | Papel |
|---|---|---|---|
| `F0_PADRAO_HZ` | (constante ou variável de módulo) | [analisar_sessao.py:38](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L38) | 60 Hz: só para metadata antigo sem `f0_hz` |
| `TENSAO_BASE_PADRAO_RMS` | (constante ou variável de módulo) | [analisar_sessao.py:39](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L39) | 127 V: só para metadata antigo sem `tensao_base_rms` |
| `analisar_offset` | `(expected: np.ndarray, captured: np.ndarray, fs_hz: float) -> Tuple[int, float]` | [analisar_sessao.py:42-64](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L42-L64) | correlação cruzada normalizada por FFT; lag positivo = o capturado está atrasado |
| `_ConfigOffline` | `class ` | [analisar_sessao.py:67-96](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L67-L96) | `Config` mínima para instanciar a classe sem os 13 campos do dataclass real |
| `_BancadaOffline` | `class ` | [analisar_sessao.py:99-110](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L99-L110) | `Bancada` mínima: `fonte=None`, `osc=None` (`gerar()` trata como simulado) |
| `_carregar_experimento_cls` | `(class_id: str)` | [analisar_sessao.py:113-126](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L113-L126) | importa `Experimento` de `experimentos_*/NN.py` por caminho |
| `_reconstruir_esperado` | `(class_id: str, metadado: dict) -> np.ndarray` | [analisar_sessao.py:129-187](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L129-L187) | a forma pedida: `gerar()` + seed, mais `senoide + k (modelo − senoide)` se houve limite |
| `_correlacao_disturbio_alinhada` | `(esperado: np.ndarray, registro: np.ndarray, inicio_janela: int, lag: int, metadado: dict, fundamental_ajustada: bool=False) -> Tuple[Optional[floa...` | [analisar_sessao.py:190-213](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L190-L213) | re-alinha a janela no registro bruto pelo lag e chama as correlações de `sinais` |
| `analisar_sessao` | `(sessao_dir: Path) -> List[Dict]` | [analisar_sessao.py:216-333](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L216-L333) | o laço principal: uma linha por captura |
| `main` | `(argv: Optional[List[str]]=None) -> int` | [analisar_sessao.py:336-356](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L336-L356) | linha de comando; imprime a tabela |

## 1. Fluxo

```{mermaid}
flowchart TD
    A["sessao_io.ler_capturas(versoes=medida)"] --> B["metadata da captura"]
    B --> C["_reconstruir_esperado<br/>(classe, seed, nivel_indice, perfil, sorteio)"]
    A --> D["registro bruto (8100)"]
    D --> E["janela_nominal / inicio_janela"]
    C --> F["analisar_offset → lag"]
    E --> F
    F --> G["_correlacao_disturbio_alinhada<br/>(nominal e fundamental ajustada)"]
    G --> H["linha: lag, correlações, razão de pico"]
```

## 2. As intricâncias

- **O "esperado" é a forma de bancada.** Se o metadata traz `parametros.fator_disturbio_bancada = k`, `_reconstruir_esperado` devolve `senoide + k·(modelo − senoide)`: é contra **essa** forma que se mede. A correlação do distúrbio é invariante a `k` (Pearson é invariante à escala), de modo que o número é o mesmo que contra o modelo puro.
- **Recorte pelo trigger real.** O início da janela vem de `inicio_janela` do metadata; sem ele, de `janela_nominal(indice_trigger, pre_trigger_s)`; sem `indice_trigger` (metadata antigo) cai em `margem_amostras_antes` com aviso: pode ter viés de `janela/10` (H-REF10). O `lag` encontrado desloca o início da janela no **registro bruto** em `_correlacao_disturbio_alinhada`, sem perder amostras nas bordas enquanto houver margem.
- **Capturas espelho** (perfil compartilhado) são ignoradas e as capturas **simuladas** viram uma linha de erro por arquivo: a ferramenta só analisa capturas de bancada.
- **Fase.** A senoide nominal usa `fase_graus` do metadata; sessões de 07/10 não têm o campo (0).

## 3. Armadilhas (documentadas no código)

1. `_BancadaOffline` força `osc=None`, então `gerar()` de 04, 06, 08, 09 e 19 usa o ramo de **sorteio** mesmo quando a sessão rodou com `set capturas N` (cobertura determinística): só `razao_pico` fica impreciso nessas classes; o lag e a correlação do distúrbio não dependem do parâmetro.
2. Não aplica o limite de bancada da 08 (`amplitude_bancada_pu`): o esperado da 08 é o impulso de 5 a 10 pu (razão de pico cerca de 0,27).
3. `analisar_offset` usa a janela inteira; em eventos curtos (08) a métrica é sensível ao alinhamento de **uma** amostra.
4. `_ConfigOffline` precisa de todo campo novo que as classes passarem a ler de `Config`; mudar `Config` sem atualizar o substituto quebra a reconstrução ({doc}`acoplamentos`).
5. A sessão inteira é reconstruída com o código **de hoje**: se `gerar()` mudou desde a sessão, o esperado muda; o aviso "parametro X: gerar() atual ≠ gravado" aparece em `gerar_tres_versoes`, não aqui.

## 4. Por que é assim

Nasceu da investigação do atraso de 20 ms da v1.7 (reconstrução manual do esperado) e virou ferramenta para provar que o "atraso" era artefato da referência do osciloscópio. Enquanto f0 e a tensão base estavam chumbados em 60 Hz e 127 V no código, toda a sessão 2, que rodou a 220 V/50 Hz, era analisada contra o modelo errado; hoje saem do metadata e só caem no padrão para metadata antigo.

## 5. Depende de e quem depende

Importa `sessao_io` e `sinais`; importa as classes de `experimentos_*/` por caminho. Não importa `mestre`. É usado por `gerar_tres_versoes.py` (`_ConfigOffline`, `_carregar_experimento_cls`), por `relatorio_html.py` (`_reconstruir_esperado`, `_correlacao_disturbio_alinhada`) e pelas análises de {doc}`../medicao/correlacao`.
