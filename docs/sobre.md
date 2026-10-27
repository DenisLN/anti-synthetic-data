# Sobre: versões, licença e como citar

```{include} /_includes/aviso-base.md
```


{bdg-info}`OFFLINE` Conferido em 2026-10-27. {bdg-danger}`PENDENTE P-20`

**Pergunta:** como citar este projeto e em que versão ele está? **Resposta:** a versão corrente é **v1.15, em andamento, sem tag**; ainda **não há DOI** (P-20; `LICENSE`, `CITATION.cff` e `.zenodo.json` existem desde 2026-10-27, sem `doi`), então, por enquanto, cite o repositório com o **commit exato** e a data. Quando o responsável congelar a versão, ela ganha tag anotada `v1.15`, release no GitHub e arquivamento no Zenodo com DOI da versão exata, e este texto muda.

## 1. Versões

Cada versão tem um `CHANGELOG/vX.Y.md` (registro histórico: não se reescreve depois de fechado), reproduzido em {doc}`historico`. Regras de versionamento, tags e o que a versão em andamento permite alterar estão em {doc}`versionamento`. Duas regras valem para quem usa o dataset:

- **Toda sessão de coleta sai de commit limpo** (idealmente o da tag): o metadata de cada captura grava `git_commit`, `git_sujo`, `versao_codigo`, `numpy_versao` e o SHA-256 da calibração de extremos em uso (`calibracao_extremos_sha256`), junto com uma cópia do arquivo na pasta da sessão.
- Mudar o que `gerar()` produz para uma seed exige autorização registrada, fixtures byte a byte e declaração no changelog; por isso a versão e o commit identificam o dataset.

## 2. Como citar (enquanto não há DOI)

Cite: o nome do repositório, o **hash completo do commit** usado, a versão (`v1.15`, em andamento) e a data de acesso. Para dados medidos, cite também a **sessão** (por exemplo `sessao_2026-10-07_127V_50Hz`) e a condição (tensão e frequência). Os rótulos de selo desta documentação ({doc}`como-ler`) indicam até onde cada afirmação foi verificada.

## 3. Licença e o que não é publicado

Licenças decididas pelo dono em 2026-10-27 (conversa): **código sob MIT** (arquivo `LICENSE` na raiz); **dataset e documentação sob CC-BY 4.0**. Autores, nesta ordem, identificados por ORCID: `0009-0002-5691-6774` e `0009-0001-3141-4498` (nome e afiliação conforme o registro público do ORCID, em `CITATION.cff` e `.zenodo.json`). O dataset não fica no repositório: é arquivado no Zenodo, um registro por versão (fluxo em {doc}`versionamento` §9); a licença CC-BY 4.0 vai no `README.txt` e no `zenodo_dataset.json` de cada pacote. A MIT cobre o código do repositório, **não** o material de terceiros: os manuais do fabricante (AMETEK, Keysight) mantêm os direitos de seus autores, e a transcrição em `docs/manuais_txt/`, que continua no repositório, **não** é coberta nem pela MIT nem pela CC-BY. Os PDFs dos manuais do fabricante não são versionados (`docs/*.pdf` está no `.gitignore`); só a transcrição em texto (`docs/manuais_txt/`) fica no repositório, e ela **não** entra neste site: as páginas citam o comando e a página do manual e remetem ao fabricante. As transcrições SCPI completas de 07/10/2026 também não são versionadas; as páginas citam trechos curtos ({doc}`scpi/transcricoes`, P-29).

## 4. Publicação do site

O site é construído por Sphinx a partir de `docs/`, com a configuração em `.readthedocs.yaml`; como compilar, como contribuir e como importar no Read the Docs: {doc}`contribuir_docs`.
