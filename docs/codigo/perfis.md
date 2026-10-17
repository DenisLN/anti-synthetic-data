# perfis.py: faixas por perfil

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Lido por inteiro em 2026-10-16 (`main` em `fa82f49`). As faixas de cada perfil em forma de tabela estão em {doc}`../perfis`.

**Pergunta:** de onde as classes tiram seus níveis e faixas? **Resposta:** de um único lugar, `logica/perfis.py`: um dicionário `FAIXAS` (11 componentes × 3 perfis) e, para as compostas sorteadas, `FAIXAS_SORTEADAS`; o perfil ativo (`norma`, `literatura` ou `fronteira`) vem de `Config.perfil`. O perfil `literatura` (padrão) reproduz **byte a byte** o `gerar()` do commit `34a0d82`.

| Símbolo | Assinatura | Linha | Papel |
|---|---|---|---|
| `PERFIS` | (constante ou variável de módulo) | [perfis.py:30](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L30) | `("norma", "literatura", "fronteira")` |
| `PERFIL_PADRAO` | (constante ou variável de módulo) | [perfis.py:31](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L31) | `literatura` |
| `FAIXAS` | (constante ou variável de módulo) | [perfis.py:37](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L37) | componente → perfil → tupla de níveis (percorridos por `capture_index`) ou par `(lo, hi)` (sorteado com `rng.uniform`) |
| `FAIXAS_SORTEADAS` | (constante ou variável de módulo) | [perfis.py:113](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L113) | intervalos sorteados por captura nas compostas 10 a 16 com o sorteio ligado |
| `COMPONENTES_POR_CLASSE` | (constante ou variável de módulo) | [perfis.py:136](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L136) | quais componentes cada classe lê (base da independência de perfil) |
| `validar` | `(perfil: str) -> str` | [perfis.py:152-157](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L152-L157) | normaliza o nome do perfil ou levanta `ValueError` |
| `perfil_do_ambiente` | `() -> str` | [perfis.py:160-163](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L160-L163) | perfil inicial pela variável `PERFIL` |
| `perfil_da_config` | `(config) -> str` | [perfis.py:166-168](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L166-L168) | perfil de uma `Config` (substituto mínimo sem o campo = literatura) |
| `faixa` | `(config, componente: str) -> Tuple[float, ...]` | [perfis.py:171-173](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L171-L173) | valores do componente no perfil ativo |
| `nivel` | `(config, componente: str, capture_index: int) -> float` | [perfis.py:176-179](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L176-L179) | nível por `capture_index % len` |
| `composto` | `(config, componente: str, capture_index: int, rng) -> float` | [perfis.py:182-196](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L182-L196) | valor de um componente de composta: sorteado ou discreto |
| `depende_do_perfil` | `(class_id: str, sorteio_posicao: bool=True) -> bool` | [perfis.py:217-229](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L217-L229) | o `gerar()` da classe muda com o perfil? (derivado das tabelas) |
| `classes_independentes_do_perfil` | `(sorteio_posicao: bool=True) -> Tuple[str, ...]` | [perfis.py:232-234](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L232-L234) | classes iguais nos três perfis |
| `plano_de_perfis` | `(class_id: str, lista_perfis: Sequence[str], sorteio_posicao: bool=True) -> List[Tuple[str, Tuple[str, ...]]]` | [perfis.py:237-250](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L237-L250) | o que `set perfil todos` realmente captura, com espelhos |

## 1. Fluxo

```{mermaid}
flowchart TD
    CLI["set perfil norma|literatura|fronteira|todos"] --> M["mestre.PERFIL / PERFIL_TODOS"]
    M --> CFG["Config.perfil (por Bancada._config_do_perfil)"]
    CFG --> GER["gerar() de 02, 03, 05, 06, 10-16, 20<br/>perfis.faixa / nivel / composto"]
    M --> PLANO["perfis.plano_de_perfis(classe, perfis, sorteio)"]
    PLANO --> ESP["classe independente: 1 captura + espelhos"]
```

## 2. As intricâncias

- **A independência de perfil é derivada, não escrita à mão.** `depende_do_perfil` compara o valor **efetivo** de cada componente que a classe lê (`COMPONENTES_POR_CLASSE`) nos três perfis; se algum par difere, a classe depende. O valor efetivo é o intervalo sorteado de `FAIXAS_SORTEADAS` (sorteio ligado) ou o nível de `FAIXAS`. Resultado, conferido em 2026-10-16: com sorteio ligado são independentes `01, 04, 07, 08, 09, 17, 18, 19`; com `set sorteio off` entra também a `16` (só lê `thd_composto`, igual nos três).
- **`plano_de_perfis`** devolve `(perfil a rodar, perfis espelho)`: classe dependente = um item por perfil; independente com mais de um perfil = **um** item, sob o perfil canônico `literatura`, com os outros perfis como espelhos (a mesma captura, registrada no metadata dos outros perfis, com o mesmo arquivo, índice e SHA-256).
- **`composto`** consome **um `uniform` por chamada** do `rng` da classe, na ordem em que `gerar()` chama; sem intervalo (sag/swell do perfil `fronteira`) usa o nível discreto por `capture_index`, sem consumir `rng`; com o sorteio desligado devolve `nivel`.

## 3. Armadilhas

1. Acrescentar um componente a uma classe **sem registrá-lo** em `COMPONENTES_POR_CLASSE` faz o código achar que a classe é independente e capturá-la uma vez só em `set perfil todos`. O teste `PerfisCompartilhadosTests` confere a derivação contra o `gerar()` real.
2. Mudar a **ordem** das chamadas a `composto` muda o `rng` e o dataset (fixtures).
3. `FAIXAS_SORTEADAS["flicker_composto"]` reaproveita os valores de `FAIXAS["flicker_profundidade"]`: alterar um muda o outro.
4. A 15 não tem `parametros_com_disturbio_reduzido`: com o distúrbio reduzido pelo limite de bancada, o metadata não traz `thd_bancada` nem `flicker_depth_bancada` (P-11).

## 4. Por que é assim

Os três perfis vieram do pedido de testar o dataset contra a norma (IEEE 1159), contra a literatura e contra as fronteiras exatas (0,1 / 0,9 / 1,1 / 1,8 pu). As extensões das compostas (sag em 11 e 12, swell em 13 e 14, THD em 13, 15 e 16, `fronteira` alternada) vão além da proposta e estão documentadas como decisão de projeto; manter ou reverter é a decisão P-11. `set perfil todos` e a independência vieram da v1.15 para não capturar três vezes a mesma forma (1404 gravações de TRACe a 60 Hz sem a deduplicação; 1116 com ela).

## 5. Depende de e quem depende

Só `os` e `typing`. É lido por `mestre.py` (`Config.perfil`, `perfis_da_rodada`, `plano_de_perfis`), por `cli.py` (`set perfil`, estimativa de gravações), por `analisar_sessao.py` (`_ConfigOffline.perfil`) e pelos `gerar()` das classes listadas acima.
