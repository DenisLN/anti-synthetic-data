# relatorio_html.py: o relatório HTML autocontido

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Lido (docstring e símbolos) em 2026-10-16, `main` em `fa82f49`. Uso pelo operador: {doc}`../operacao` §9.

**Pergunta:** o que o relatório HTML mostra e de onde vêm os números do cabeçalho de cada captura? **Resposta:** gera **um** arquivo `.html` com as figuras embutidas em base64 (abre em qualquer navegador, offline, dá para mandar por e-mail), preenchendo o modelo `logica/modelos/relatorio_capturas.html`; para cada captura, uma visualização completa e até 3 detalhes (zooms onde o sinal mais muda), mais uma tabela de metadados com as **correlações** calculadas pelas mesmas funções de `analisar_sessao.py`. É o único uso de `matplotlib` no projeto.

| Símbolo | Assinatura | Linha | Papel |
|---|---|---|---|
| `Captura` | `class ` | [relatorio_html.py:88-145](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/relatorio_html.py#L88-L145) | uma captura a desenhar (versões, metadado, perfil, compartilhamento) |
| `escolher_detalhes` | `(nominal: np.ndarray, *, fs_hz: float, f0_hz: float, quantidade: int, largura_ms: float) -> List[Tuple[float, float]]` | [relatorio_html.py:150-230](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/relatorio_html.py#L150-L230) | até N janelas onde o sinal mais muda, sem sobreposição |
| `_reconstruir_esperado` | `(captura: Captura) -> Optional[np.ndarray]` | [relatorio_html.py:250-262](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/relatorio_html.py#L250-L262) | forma pedida via `analisar_sessao` (só tensão de bancada) |
| `_correlacoes` | `(captura: Captura, esperado: Optional[np.ndarray]) -> Optional[dict]` | [relatorio_html.py:265-285](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/relatorio_html.py#L265-L285) | correlação total e do distúrbio contra o esperado, com o mesmo alinhamento por lag |
| `ler_capturas` | `(dados_dir: Path, metadados: Dict[str, dict], *, classes: Optional[Sequence[str]]=None, max_por_classe: Optional[int]=None, perfis: Optional[Sequen...` | [relatorio_html.py:288-334](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/relatorio_html.py#L288-L334) | capturas de uma pasta, com filtros `classes`, `perfis`, `versoes`, `capturas`, `max_por_classe` |
| `_sem_figuras_repetidas` | `(capturas: List[Captura]) -> List[Captura]` | [relatorio_html.py:337-351](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/relatorio_html.py#L337-L351) | uma captura compartilhada entre perfis vira UMA figura |
| `figura_completa` | `(captura: Captura, dpi: int) -> str` | [relatorio_html.py:375-416](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/relatorio_html.py#L375-L416) | o registro inteiro; a margem sombreada, tempo negativo antes da janela |
| `tabela_metadados` | `(captura: Captura) -> str` | [relatorio_html.py:463-529](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/relatorio_html.py#L463-L529) | a tabela com SNRs, lag, correlações, validação física |
| `gerar_relatorio` | `(sessao_dir: Path, saida: Path, *, titulo: Optional[str]=None, descricao: str='', snr: Optional[str]=None, classes: Optional[Sequence[str]]=None, m...` | [relatorio_html.py:625-669](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/relatorio_html.py#L625-L669) | gera o HTML e devolve `(caminho, número de capturas)` |
| `gerar_relatorio_recortado` | `(sessao_dir: Path, *, titulo: Optional[str]=None, descricao: str='', dpi: int=100) -> Tuple[Path, int, float]` | [relatorio_html.py:672-692](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/relatorio_html.py#L672-L692) | recorta a margem (`sem_margem/`) e gera `relatorio_<sessao>.html` (o que a CLI chama) |
| `main` | `(argv: Optional[List[str]]=None) -> int` | [relatorio_html.py:695-758](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/relatorio_html.py#L695-L758) | linha de comando (`--classes`, `--perfis`, `--versoes`, `--capturas`, `--snr`, `--dpi`, ...) |

## 1. Fluxo

```{mermaid}
flowchart LR
    S["sessão (formato 1 ou 2)"] --> L["sessao_io.ler_capturas"]
    L --> F["filtros: classes, perfis, versões, capturas"]
    F --> D["sem figuras repetidas<br/>(captura compartilhada = 1 figura)"]
    D --> G["figura_completa + figura_detalhe<br/>(matplotlib → PNG → base64)"]
    D --> T["tabela_metadados<br/>(_correlacoes via analisar_sessao)"]
    G --> H["modelo HTML preenchido"]
    T --> H
```

## 2. As intricâncias

- **A forma esperada é sempre reconstruída** (para as correlações da tabela), mas só é **desenhada** com `--com-esperado`.
- **Captura compartilhada.** Uma captura espelhada entre perfis é desenhada **uma vez**, rotulada "(= norma, fronteira)", com o SHA-256; quando o perfil de origem não está na seleção (por exemplo `--perfis norma`), a figura aparece sob o perfil pedido, marcada como compartilhada.
- **Eixo de tempo.** Começa em 0 no início da janela nominal (a mesma base de `gerar()`); a folga de antes aparece em tempo **negativo**, sombreada.
- **O custo.** Acima de `TAMANHO_EMAIL_MB` (20 MB) a CLI avisa que o arquivo pode não passar como anexo; reduzir com `--classes`, `--max-capturas-por-classe` ou `--dpi 80`.

## 3. Armadilhas

1. **Atualização P-15:** sem seleção ou limite explícito, `ler_capturas` aplica até três capturas por classe/perfil a bancada e simulação, formatos legado e atual, e emite aviso; os arquivos originais não são truncados.
2. O gancho `set html on` **não confere `BENCH_MODE`**: gera também no simulado.
3. `matplotlib` entra só aqui; o `requirements.txt` do projeto o traz, mas o ambiente do site de documentação não precisa dele.
4. As correlações do relatório são as de `analisar_sessao`, com as mesmas limitações (ramo de sorteio em 04, 06, 08, 09 e 19 quando houve `set capturas`).

## 4. Depende de e quem depende

Importa `sessao_io` e `recortar_margem` no topo e `analisar_sessao` e `matplotlib` **dentro das funções** que os usam (importação tardia: ler o módulo não exige matplotlib); **não importa `mestre`**. É chamado por `SessaoCLI._gerar_html_ao_fim` e à mão (`python logica\relatorio_html.py <sessão>`).
