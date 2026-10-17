# recortar_margem.py: tirar a folga de 20 ms e 50 ms

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Lido (docstring e símbolos) em 2026-10-16, `main` em `fa82f49`.

**Pergunta:** o que `recortar_margem.py` entrega e o que ele nunca faz? **Resposta:** devolve, para cada captura de bancada, **só a janela nominal de 6000 amostras** (a mesma base de tempo de `gerar()`), numa pasta nova (`<sessao>/sem_margem/` por padrão), com a mesma estrutura de uma sessão (formato 2, `snr_XXdb/`, `corrente/`, `metadata/*.jsonl`), de modo que `analisar_sessao.py` e `relatorio_html.py` rodam nela sem mudança. **Nunca altera a sessão original** e recusa escrever na própria pasta.

| Símbolo | Assinatura | Linha | Papel |
|---|---|---|---|
| `carregar_metadados` | `(sessao_dir: Path) -> 'sessao_io.MetadadosDaSessao'` | [recortar_margem.py:52-56](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/recortar_margem.py#L52-L56) | `id_captura` → linha do metadata, de todos os `metadata/*.jsonl` |
| `diretorios_de_dados` | `(sessao_dir: Path) -> List[Path]` | [recortar_margem.py:59-67](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/recortar_margem.py#L59-L67) | a pasta da sessão, `snr_XXdb/` e `corrente/`; `analise/`, `parcial/` e `sem_margem/` ficam de fora |
| `calcular_recorte` | `(n_amostras: int, metadado: Optional[dict]) -> Tuple[int, int, dict]` | [recortar_margem.py:70-124](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/recortar_margem.py#L70-L124) | decide `[inicio, inicio + pontos)` e devolve `(inicio, pontos, info)` com a origem do número |
| `metadado_recortado` | `(metadado: dict, info: dict) -> dict` | [recortar_margem.py:127-141](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/recortar_margem.py#L127-L141) | linha do metadata descrevendo o arquivo recortado |
| `recortar_sessao` | `(sessao_dir: Path, saida_dir: Path, *, empilhar: bool=False) -> List[dict]` | [recortar_margem.py:151-252](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/recortar_margem.py#L151-L252) | recorta toda a sessão; uma linha de relatório por captura |
| `main` | `(argv: Optional[List[str]]=None) -> int` | [recortar_margem.py:273-295](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/recortar_margem.py#L273-L295) | linha de comando |

## 1. Como decide o recorte

Ordem de preferência em `calcular_recorte`: (1) **`inicio_janela`** do metadata (já calculado pela bancada, com `ajustado` quando o registro não tinha amostras suficientes); (2) `indice_trigger − pre_trigger_s · fs_hz` (a mesma conta de `sinais.janela_nominal`); (3) `margem_amostras_antes` (metadata muito antigo, com viés de `janela/10`, H-REF10). O bloco `recorte` de cada linha do metadata explica **de onde** saiu o número, e o metadata recortado passa a dizer `margem_amostras_* = 0`, `inicio_janela = 0` e `indice_trigger` reindexado.

## 2. Armadilhas

1. Grava **sempre o formato 2**, mesmo de uma sessão antiga (formato 1): recortar converte.
2. `--empilhar` é aceito e **não faz nada** (o formato 2 já é empilhado por classe); a opção sobrevive só para não quebrar scripts.
3. Entre os arquivos de dados, só entram o que a bancada grava; as capturas **simuladas** não têm margem para tirar.
4. O recorte usa o trigger **real**; se o trigger caiu fora de `pre_trigger + margem`, a janela recortada começa onde o trigger manda, não onde a classe previa (ver `pre_trigger_desvio_amostras` em {doc}`mestre`).

## 3. Por que existe

Desde a v1.11 toda captura **física** grava 20 ms antes e 50 ms depois da janela nominal (8100 pontos a 30 kSa/s em vez de 6000). A margem é útil para medir o ruído próprio da bancada e para a validação, mas o dataset publicado e a análise comparam janelas nominais. O recorte, feito pela mesma função que a validação física, garante que o número que o relatório mostra é o mesmo que a bancada validou.

## 4. Depende de e quem depende

Importa `sessao_io` e `sinais.janela_nominal`; **não importa `mestre`**. É chamado por `relatorio_html.gerar_relatorio_recortado` (o gancho `set html on` da CLI) e à mão.
