# sessao_io.py: leitura e escrita dos .npz

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Lido (escrita por inteiro; leitura pelos docstrings e pelos pontos de entrada) em 2026-10-16, `main` em `fa82f49`. Formatos e chaves para quem consome o dataset: {doc}`../dataset`.

**Pergunta:** quem escreve e quem lê os `.npz` de uma sessão? **Resposta:** `mestre.py` **escreve** (por `ArquivoDaClasse`, captura a captura, com gravação atômica) e **todos os leitores** passam por `sessao_io.ler_capturas`/`ler_pasta`, que lê os **dois formatos** (formato 2, um `NN_classe.npz` comprimido por classe com perfis e versões; formato 1, um `.npz` por captura mais `tres_versoes/`) e devolve a mesma estrutura `CapturaSessao`. O módulo não importa `mestre` nem hardware.

| Símbolo | Assinatura | Linha | Papel |
|---|---|---|---|
| `FORMATO_NPZ` | (constante ou variável de módulo) | [sessao_io.py:34](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L34) | 2 |
| `VERSOES` | (constante ou variável de módulo) | [sessao_io.py:35](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L35) | `("medida", "modelo", "programada")` |
| `hash_captura` | `(medida, modelo=None, programada=None, pontos: Optional[int]=None) -> str` | [sessao_io.py:83-97](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L83-L97) | SHA-256 dos três arrays em float64 little-endian, cada um com rótulo e tamanho; ausente = NaN |
| `gravar_npz` | `(destino: Path, *, comprimido: bool=True, **arrays) -> None` | [sessao_io.py:102-110](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L102-L110) | gravação atômica (`.part` → `os.replace`) |
| `ArquivoDaClasse` | `class ` | [sessao_io.py:117-452](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L117-L452) | acumula as capturas de UMA classe (todos os perfis) e grava `NN_classe.npz`, `snr_XXdb/` e `corrente/` |
| `ArquivoDaClasse.adicionar` | `(self, perfil: str, *, id_captura: str, medida: np.ndarray, tempo_ms: np.ndarray, fs_hz: float, modelo: Optional[np.ndarray]=None, programada: Opti...` | [sessao_io.py:222-273](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L222-L273) | guarda a captura em memória e, na bancada, no spool `parcial/NN_classe/` |
| `ArquivoDaClasse.iniciar_perfil` | `(self, perfil: str) -> None` | [sessao_io.py:210-220](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L210-L220) | começa (ou repete) o bloco de um perfil |
| `ArquivoDaClasse.espelhar` | `(self, origem: str, destinos: Sequence[str]) -> None` | [sessao_io.py:177-206](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L177-L206) | declara que outros perfis são a MESMA captura (mesmo arquivo, índice e SHA-256) |
| `ArquivoDaClasse.do_spool` | `(cls, results_dir: Path, class_id: str, nome: str) -> 'ArquivoDaClasse'` | [sessao_io.py:315-339](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L315-L339) | reconstrói o acumulador a partir de `parcial/` |
| `ArquivoDaClasse.consolidar` | `(self, *, so_snr: bool=False) -> Optional[Path]` | [sessao_io.py:420-452](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L420-L452) | reescreve a classe inteira: todos os `.part` antes de qualquer promoção |
| `recuperar_parcial` | `(sessao_dir: Path) -> List[Path]` | [sessao_io.py:455-523](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L455-L523) | promove ao formato 2 as capturas que sobraram em `parcial/` |
| `MetadadosDaSessao` | `class (dict)` | [sessao_io.py:528-552](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L528-L552) | `id_captura` → linha do metadata, com busca por perfil |
| `CapturaSessao` | `class ` | [sessao_io.py:580-613](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L580-L613) | uma captura lida, em qualquer formato |
| `formato_do_arquivo` | `(caminho: Path) -> str` | [sessao_io.py:658-661](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L658-L661) | `"classe"` (formato 2) ou `"legado"` (formato 1) |
| `ler_pasta` | `(dados_dir: Path, metadados: Optional[Mapping]=None, *, versoes: Sequence[str]=('medida',), classes: Optional[Sequence[str]]=None, perfis: Optional...` | [sessao_io.py:685-728](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L685-L728) | capturas dos `*.npz` de uma pasta, nos dois formatos |
| `_ler_formato2` | `(dados, caminho, class_id, metadados, versoes, perfis_filtro, selecao, max_por_bloco, limite_padrao, contagem, saida, avisar) -> None` | [sessao_io.py:742-814](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L742-L814) | leitor do formato 2 |
| `_ler_formato1` | `(dados, caminho, dados_dir, class_id, metadados, versoes, perfis_filtro, selecao, max_por_bloco, limite_padrao, contagem, vistas, saida, avisar) ->...` | [sessao_io.py:817-867](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L817-L867) | leitor do formato 1 (junta `tres_versoes/`) |
| `ler_capturas` | `(sessao_dir: Path, *, subpasta: Optional[str]=None, **opcoes) -> List[CapturaSessao]` | [sessao_io.py:870-880](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L870-L880) | `ler_pasta` na sessão (ou subpasta) com o metadata da sessão |

## 1. Escrita: o caminho de uma captura

```{mermaid}
flowchart TD
    A["ExperimentoBase._salvar_captura"] --> B["ArquivoDaClasse.adicionar<br/>(memória + spool atômico em parcial/)"]
    B --> C["... capturas seguintes ..."]
    C --> D["_finalizar_gravacao"]
    D --> E["ArquivoDaClasse.consolidar<br/>reescreve NN_classe.npz, snr_XXdb/, corrente/"]
    E --> F["metadata/NN_classe.jsonl (.part → replace)"]
    E --> G["encerrar_perfil: apaga o spool"]
    X["processo morreu no meio"] --> H["recuperação automática antes do novo run"]
```

- **Spool por captura.** Com `spool=True` (bancada), cada captura vai para `parcial/NN_classe/<perfil>__NNNNNN.npz` (sem compressão, atômico) assim que existe. Se o processo morrer antes de `consolidar`, as capturas boas continuam no disco e `recuperar_parcial` as promove; na atualização P-13, `recuperar_sessoes_interrompidas` é chamado por `SessaoCLI._garantir_pasta_sessao` antes do novo `run`, sem abrir instrumentos ou repetir capturas.
- **`consolidar` reescreve a classe inteira** a cada fim de perfil (custo O(n) por perfil): nenhuma captura de um perfil anterior se perde quando o seguinte falha.
- **Dados antes do metadata.** Todos os `.part` são escritos antes de qualquer promoção; o metadata sobrevivente nunca descreve dado que não foi gravado.
- **Chaves do formato 2.** `formato_npz`, `classe`, `perfis`, `tempo_ms`, `tempo_janela_ms`, e por perfil `<perfil>/id_captura`, `/medida` (registro inteiro: 8100 amostras na bancada), `/modelo` e `/programada` (6000), `/origem_programada` e `/inicio_janela`. Linhas de versão ausente ficam `NaN`. Os `snr_XXdb/NN_classe.npz` **não** são comprimidos: o ruído branco quase não comprime (medido: −4,6 %).
- **Capturas espelho.** Classes independentes do perfil (`set perfil todos`) têm um bloco só, sob `literatura`; `compartilhadas_perfis` e `compartilhadas_origem` dizem quais perfis apontam para ele, e o metadata de cada um repete `arquivo_classe`, `indice_no_arquivo` e `sha256_captura`.

## 2. Leitura

`ler_pasta` decide o formato por arquivo (`formato_do_arquivo`) e devolve `CapturaSessao` (id, classe, perfil, grandeza, versões, metadado, arquivo, formato, espelho). A chave única de uma captura é `(perfil, id_captura)`: o **mesmo** `id_captura` existe em cada perfil de uma sessão `set perfil todos`, porque a seed da captura não depende do perfil, por isso `MetadadosDaSessao.buscar(perfil, id)` e não um simples dicionário.

## 3. Armadilhas

1. `consolidar` é O(n) por perfil: com medida real (ruído que comprime pouco) o tamanho do arquivo e o custo de reescrever são **NÃO VERIFICADOS** (P-22).
2. `formato_do_arquivo`, a leitura de `tres_versoes/` e `ler_pasta` abrem `.npz` com **`allow_pickle=True`** por causa do formato 1; só o spool interno (`do_spool`) usa `False`. `docs/dataset.md` recomenda sem pickle para o formato 2: abrir um `.npz` de terceiros pelo relatório executaria código pickle (baixa probabilidade, mas relevante para "compartilhar o dataset").
3. `_ler_formato1` **descarta em silêncio** uma captura sem `tres_versoes/` quando a `medida` não é pedida (relatório 24 da rodada de 13 a 15/10).
4. **Atualização P-15:** o relatório HTML padrão limita a três por classe/perfil também na bancada; seleções e limites explícitos alteram a escolha sem modificar dados originais.
5. Uma `Bancada` nova na mesma pasta **recomeça** o arquivo da classe (o acumulador vive na `Bancada`).
6. **Quebra de formato** nas sessões novas: quem lia `NN_classe_<rótulo>.npz` ou `tres_versoes/` precisa trocar para as chaves do formato 2 ou para `sessao_io.ler_capturas`; as sessões antigas continuam legíveis.

## 4. Por que é assim

O formato 1 gerava um arquivo por captura, mais as três versões à parte e os níveis de ruído: com três perfis a pasta explodia. O formato 2 (um `.npz` por classe, sem perda) e `set perfil todos` resolvem, e o **leitor único** impede que sete módulos tenham sete leituras diferentes. A gravação atômica e o spool vêm do dia em que 7 capturas boas da 08 e 52 da 03 foram perdidas por uma falha na captura seguinte (sessão 2, 16/09/2026).

## 5. Depende de e quem depende

`numpy` e biblioteca padrão; **não importa `mestre`**. É importado por `mestre.py` (escrita), `analisar_sessao.py`, `recortar_margem.py`, `relatorio_html.py` e pelos scripts `gerar_ruido_janela.py`, `gerar_tres_versoes.py`, `diag_ciclos_trace.py` e `verificar_sessao_bancada.py`.
