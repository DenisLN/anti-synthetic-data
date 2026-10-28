#spec #pri 10

# ASD: Pacote de Publicação do Dataset e Preparação do Zenodo (P-20)

## Contexto

O projeto `anti-synthetic-data` gera, numa bancada com fonte AMETEK MX30 e osciloscópio Keysight, um dataset de distúrbios de tensão (20 classes). Cada sessão de coleta grava uma pasta em `resultados/` (ignorada pelo git, ~188 MB hoje; ver `.gitignore`). Versionar isso no GitHub foi descartado pelo dono: são binários `.npz` sem diff útil que incharia o histórico.

Decisão do dono (2026-10-27, em conversa): o dataset será arquivado no **Zenodo**, um record por versão do projeto, com DOI. O código continua no GitHub e a release dele também pode ser arquivada pela integração GitHub→Zenodo. O repositório guarda só o código, os `CHANGELOG`, os metadados de publicação e o manifesto com SHA-256; nunca os dados.

Decisões já tomadas pelo dono (valem como autorização registrada para esta spec):
- Licença do **código**: MIT.
- Licença do **dataset e da documentação**: CC-BY 4.0.
- Autores, nesta ordem, identificados só por ORCID: `https://orcid.org/0009-0002-5691-6774` e `https://orcid.org/0009-0001-3141-4498`. Nome e afiliação devem vir do registro público do ORCID; o dono não os informou.
- **Calendário**: tag `v1.15` e publicação real no Zenodo **só depois** de P-01 (campanha com o código v1.15) e P-31 estarem resolvidas. Esta spec prepara tudo e testa, mas não tageia nem publica.

Estado atual: não existe `LICENSE`, `CITATION.cff` nem `.zenodo.json` na `main`; `git tag` não lista `v1.15`; não há DOI. A pendência P-20 (em `docs/estado_prontidao.json` e `docs/decisoes_pendentes.md`, seção P-20) está esperando essas respostas. Cada sessão já grava em seu metadata `git_commit`, `git_sujo`, `versao_codigo` e o SHA-256 da calibração (ver `docs/metadata.md`).

## Entradas

- Projeto: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data` (branch `main`, sincronizada com `github/main` em `0abb35f`; o remoto `origin` é o aspire5050 e não deve ser usado para push).
- Leia antes: `docs/metadata.md`, `docs/dataset.md`, `docs/versionamento.md` (seção Zenodo), `docs/sobre.md` (§3 licença), `docs/decisoes_pendentes.md` (seção P-20), o bloco P-20 em `docs/estado_prontidao.json`, `logica/sessao_io.py` (formatos de sessão), `AGENTS.md` (seção "Limites inegociáveis").
- Sessões reais para o teste a seco, somente leitura: `resultados/sessao_2026-10-07_127V_50Hz` (formato antigo, sessões de 07/10 são o piloto).
- Registro público do ORCID: `https://pub.orcid.org/v3.0/<orcid>/person` com cabeçalho `Accept: application/json`, para os dois ORCIDs acima.
- Suíte: `python -m unittest discover -s tests -p "test*.py"`. Build do site: `sphinx-build -W -n --keep-going -b html docs docs/_build/html`. Mapa: `python scripts/gerar_mapa_pendencias.py`.
- Depende de: nada
- Executor: sonnet

## Missão

1. Criar `LICENSE` na raiz com o texto padrão da licença MIT (código). O titular do copyright é o nome do primeiro autor conforme o registro público do ORCID; se o nome não for público, registrar como IMPEDIDO nesse ponto e usar o ORCID como titular provisório.
2. Criar `CITATION.cff` (formato CFF 1.2.0) com os dois autores, na ordem dada, com `orcid`, nome e afiliação lidos do registro público do ORCID (campo ausente fica de fora, nunca inventado), `license: MIT`, título do projeto, `version: v1.15` e `repository-code` do GitHub (`https://github.com/DenisLN/anti-synthetic-data`). Sem campo `doi`.
3. Criar `.zenodo.json` na raiz para a integração GitHub→Zenodo do código: `creators` com `orcid` e `name`, `license: mit`, `upload_type: software`, título e descrição em português. Sem DOI. Registrar no relatório que os PDFs de fabricante em `docs/*.pdf` e `docs/manuais_txt/` estão no repositório e **não** são cobertos pela MIT (conferir o que `docs/sobre.md` §3 já diz e manter coerente).
4. Escrever `scripts/empacotar_dataset.py`, offline, que recebe uma ou mais pastas de sessão e um diretório de saída (padrão `resultados/_pacote/dataset_<versao>/`, já coberto pelo `.gitignore` de `resultados/`) e gera: cópia dos arquivos de dados e metadados das sessões (sem alterar os originais), `calibracao_extremos.json` usado, `SHA256SUMS`, `MANIFEST.json` (versão, `git_commit` de cada sessão, `git_sujo`, lista de arquivos com tamanho e SHA-256), `README.txt` com aviso de licença CC-BY 4.0 e como verificar, e `zenodo_dataset.json` (`upload_type: dataset`, `license: cc-by-4.0`, `creators` como no item 2, `version`, `related_identifiers` com a relação `isSupplementTo` apontando para a release do GitHub, sem DOI e sem `publication_date`). Deve recusar uma sessão com `git_sujo` verdadeiro, salvo `--piloto`, que então marca o pacote como piloto no `MANIFEST.json` e no título. Deve ter um modo `--verificar <pasta>` que confere o `SHA256SUMS` e sai com código diferente de zero se algo divergir.
5. Cobrir o item 4 com `tests/test_empacotar_dataset.py` (pacote gerado e verificado; arquivo adulterado detectado; sessão suja recusada sem `--piloto`; originais intactos) e rodar o empacotador em teste a seco sobre `resultados/sessao_2026-10-07_127V_50Hz` com `--piloto`, saída em diretório temporário fora do repositório, seguido de `--verificar`.
6. Documentar e registrar: acrescentar em `docs/versionamento.md` a seção do fluxo de publicação (tag → release no GitHub → pacote → upload no Zenodo Sandbox para ensaio → upload real; token só em variável de ambiente, nunca no repositório; DOI de conceito versus DOI de versão; relação com a release do código); atualizar `docs/sobre.md` §3 com a licença decidida; atualizar o bloco P-20 em `docs/estado_prontidao.json` (licenças e autoria decididas pelo dono em 2026-10-27, fonte "decisão em conversa"; permanecem em aberto a tag e a publicação, bloqueadas por P-01 e P-31) e a resposta da seção P-20 em `docs/decisoes_pendentes.md`; rodar `scripts/gerar_mapa_pendencias.py`; acrescentar entrada em `CHANGELOG/v1.15.md` (Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO).

## Limites

- Trabalhar num branch novo `feat/publicacao-zenodo` a partir da `main`, com um commit por mudança lógica (`tipo: resumo em português`). Não fazer push, não usar `--force`, não mexer na `main`.
- Não criar tag, não publicar nada, não chamar nenhuma API do Zenodo nem usar token. Não escrever nenhum DOI (nenhuma string `10.5281`) em arquivo algum.
- Não alterar `logica/`, `experimentos_nativos/`, `experimentos_waveform/`, `tests/fixtures/` nem nada que mude o que `gerar()` produz. Não tocar nos limites inegociáveis do `AGENTS.md`.
- `resultados/` é somente leitura; a única escrita permitida ali é a pasta `resultados/_pacote/` (ignorada).
- Não inventar nome, afiliação nem ORCID. Não decidir por conta própria licença, ordem de autores ou data de tag; só registrar o que o dono decidiu acima.
- Não editar `CHANGELOG/vX.Y.md` fechados nem `docs/historico/*`. Só acrescentar ao `v1.15.md`.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.
- Se algum limite impedir ou restringir o resultado, registrar no relatório em "Limitações de escopo", sem ultrapassá-lo.

## Entregável

- Relatório `.md` no caminho que o despacho indicar, com: um bloco por item da Missão (copiar o texto do item, dizer CUMPRIDO, PARCIAL, NÃO CUMPRIDO ou IMPEDIDO, e explicar nos dois casos, com evidência); Critério de Parada atendido ou não; pendências que exigem o usuário (confirmar nomes e afiliações lidos do ORCID, a ordem dos autores e o titular da MIT); limitações de escopo; se a missão resolve o contexto; achados.
- Arquivos produzidos: `LICENSE`, `CITATION.cff`, `.zenodo.json`, `scripts/empacotar_dataset.py`, `tests/test_empacotar_dataset.py`, e as edições em `docs/versionamento.md`, `docs/sobre.md`, `docs/estado_prontidao.json`, `docs/decisoes_pendentes.md`, `CHANGELOG/v1.15.md`, além do mapa regenerado.
- Verificação: rodar a suíte completa, o build do site e `python scripts/empacotar_dataset.py --verificar <pacote do teste a seco>`; a saída de cada comando vai no relatório.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir. Em especial: o upload real no Zenodo e o formato exato aceito pelo Sandbox não foram exercitados.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

Todos verdadeiros: (a) `LICENSE`, `CITATION.cff`, `.zenodo.json`, `scripts/empacotar_dataset.py` e `tests/test_empacotar_dataset.py` existem no branch `feat/publicacao-zenodo`; (b) a suíte completa e o build `sphinx-build -W` passam, com a saída no relatório; (c) o teste a seco sobre `sessao_2026-10-07_127V_50Hz` gera um pacote que `--verificar` aprova; (d) `git tag` continua sem `v1.15`, `git grep 10.5281` não encontra nada e nenhum arquivo de `logica/` foi alterado (`git diff --stat main -- logica experimentos_nativos experimentos_waveform` vazio); (e) o relatório cobre os 6 itens da Missão.
