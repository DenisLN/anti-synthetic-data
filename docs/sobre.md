# Sobre: versões, licença e como citar

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Conferido em 2026-10-16 (`main` em `fa82f49`). {bdg-danger}`PENDENTE P-20`

**Pergunta:** como citar este projeto e em que versão ele está? **Resposta:** a versão corrente é **v1.15, em andamento, sem tag**; ainda **não há DOI, `LICENSE` nem `CITATION.cff`** (P-20), então, por enquanto, cite o repositório com o **commit exato** e a data. Quando o responsável congelar a versão, ela ganha tag anotada `v1.15`, release no GitHub e arquivamento no Zenodo com DOI da versão exata, e este texto muda.

## 1. Versões

Cada versão tem um `CHANGELOG/vX.Y.md` (registro histórico: não se reescreve depois de fechado), reproduzido em {doc}`historico`. Regras de versionamento, tags e o que a versão em andamento permite alterar estão em {doc}`versionamento`. Duas regras valem para quem usa o dataset:

- **Toda sessão de coleta sai de commit limpo** (idealmente o da tag): o metadata de cada captura grava `git_commit`, `git_sujo`, `versao_codigo`, `numpy_versao` e o SHA-256 da calibração de extremos em uso (`calibracao_extremos_sha256`), junto com uma cópia do arquivo na pasta da sessão.
- Mudar o que `gerar()` produz para uma seed exige autorização registrada, fixtures byte a byte e declaração no changelog; por isso a versão e o commit identificam o dataset.

## 2. Como citar (enquanto não há DOI)

Cite: o nome do repositório, o **hash completo do commit** usado, a versão (`v1.15`, em andamento) e a data de acesso. Para dados medidos, cite também a **sessão** (por exemplo `sessao_2026-10-07_127V_50Hz`) e a condição (tensão e frequência). Os rótulos de selo desta documentação ({doc}`como-ler`) indicam até onde cada afirmação foi verificada.

## 3. Licença e o que não é publicado

O repositório **não tem arquivo de licença**: sem uma, o código e os dados não têm termos de uso explícitos (decisão do responsável, P-20). Os manuais do fabricante (`docs/*.pdf` e `docs/manuais_txt/`) estão no repositório mas **não** entram neste site: as páginas citam o comando e a página do manual e remetem ao fabricante. As transcrições SCPI completas de 07/10/2026 também não são versionadas; as páginas citam trechos curtos ({doc}`scpi/transcricoes`, P-29).

## 4. Publicação do site

O site é construído por Sphinx a partir de `docs/`, com a configuração em `.readthedocs.yaml`; como compilar, como contribuir e como importar no Read the Docs: {doc}`contribuir_docs`.
