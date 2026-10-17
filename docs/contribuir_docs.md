# Como compilar e contribuir com esta documentação

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


**Pergunta:** como gerar o site no computador e o que precisa estar certo antes de publicar? **Resposta:** instale as cinco dependências fixas de `docs/requirements.txt` em um ambiente virtual e rode `python -m sphinx -W --keep-going -b html docs docs/_build/html`; o site só é aceito se esse comando terminar com código 0, sem nenhum aviso, porque o Read the Docs roda o mesmo comando com `fail_on_warning: true` (`.readthedocs.yaml`).

{bdg-info}`OFFLINE` Os dois fluxos abaixo foram executados nesta máquina (Windows 11, Python 3.11.9) em 2026-10-16. O fluxo no Linux é o mesmo comando; a prova de build de 2026-10-15 passou em Linux com Python 3.14.7 (`docs-site-plano/05-arquitetura-do-site.md` §2.2). O Python 3.12 do Read the Docs {bdg-warning}`NÃO VERIFICADO` não foi testado localmente.

## 1. Preparar o ambiente

O ambiente do site é separado do `env\` da bancada (que tem numpy, PyMeasure e PyVISA). O site não importa o código do projeto: `logica/` é lido como texto por `literalinclude`.

::::{tab-set}
:::{tab-item} Windows (PowerShell)
```powershell
cd C:\caminho\do\repositorio     # raiz do repositório
python -m venv .venv-docs
.\.venv-docs\Scripts\python.exe -m pip install -r docs\requirements.txt
.\.venv-docs\Scripts\python.exe -m sphinx -W --keep-going -b html docs docs\_build\html
start docs\_build\html\index.html
```
:::
:::{tab-item} Linux
```bash
cd ~/caminho/do/repositorio         # raiz do repositório
python3 -m venv .venv-docs
.venv-docs/bin/python -m pip install -r docs/requirements.txt
.venv-docs/bin/python -m sphinx -W --keep-going -b html docs docs/_build/html
xdg-open docs/_build/html/index.html
```
:::
::::

`.venv-docs/` e `docs/_build/` não entram no git (`.gitignore`). Python 3.11 ou mais novo é exigido pelo Sphinx 9.

## 2. Regras de escrita (resumo; o guia completo está em {doc}`como-ler`)

1. Cada página abre com a **pergunta** que responde e a **resposta direta em negrito**; o contexto e o histórico vêm depois, dentro da explicação.
2. Todo número leva condição (127 V/60 Hz, 127 V/50 Hz ou 230 V/50 Hz) e fonte (sessão, arquivo ou comando).
3. Todo comando SCPI no texto é um papel `` {scpi}`TRACe:DATA` `` (AMETEK) ou `` {scpik}`:TIMebase:RANGe` `` (Keysight): o link resolve a entrada em {doc}`scpi`; um comando sem entrada falha o build.
4. Fato sobre comportamento cita `arquivo:linha` ou um símbolo (`mestre.py::Bancada.from_env`). Listagens usam `literalinclude` com `:pyobject:`, não números de linha escritos à mão.
5. Selos de status, avisos padronizados e a lista de verificação de revisão estão em {doc}`como-ler`.
6. Sem nome de pessoa, "dono" nem referência a texto de origem (regra de `AGENTS.md`).
7. Não renomear nem mover arquivos de `docs/`: `AGENTS.md`, `README.md`, os `CHANGELOG/` fechados e o código citam esses caminhos.

## 3. O que o build verifica

| Verificação | Como falha |
|---|---|
| link interno, âncora ou `{doc}` inexistente | aviso `ref.*` ou `myst.xref_missing`; `-W` transforma em erro |
| página fora de qualquer `toctree` | aviso `toc.not_included` |
| comando SCPI sem entrada de referência | aviso de referência não resolvida (papéis `scpi` e `scpik`, `docs/_ext/scpi.py`) |
| `literalinclude` com símbolo inexistente | erro de diretiva |
| tabela ou cabeçalho malformado | aviso de docutils |

Exceção registrada em `docs/conf.py`: três links relativos quebrados em `CHANGELOG/v1.0.md` e `v1.2.md` (que apontam para `../ametek_orm.py`, `../oscilloscope_orm.py` e `../mestre.py`) são ignorados porque os changelogs fechados não se reescrevem; qualquer outro link quebrado continua falhando.

## 4. Publicar no Read the Docs

O build no serviço depende de conta e importação feitas pelo responsável pelo repositório; o arquivo `.readthedocs.yaml` já está na raiz.

1. Entrar em readthedocs.org e escolher **Import a Project**; autorizar a conta do GitHub e selecionar o repositório `anti-synthetic-data` (o repositório do projeto).
2. Conferir que o serviço achou `.readthedocs.yaml` (configuração `docs/conf.py`, Python 3.12, `docs/requirements.txt`).
3. Definir o nome do projeto e o subdomínio (`*.readthedocs.io`); decisão do responsável.
4. Em **Versions**, ativar `latest` (ramo `main`) e, depois de congelada a v1.15 com a tag `v1.15`, `stable` ({bdg-danger}`PENDENTE P-20`).
5. Disparar o primeiro build e comparar o resultado com o build local. {bdg-warning}`NÃO VERIFICADO` O `.readthedocs.yaml` nunca rodou no serviço; qualquer diferença (versão do Python, rede para o CDN do Mermaid) aparece no primeiro build.
6. Opcional: ativar a pré-visualização de pull request.

O repositório tem manuais em PDF e texto (`docs/*.pdf`, `docs/manuais_txt/`) que **não** entram no site (`exclude_patterns` em `docs/conf.py`); ver {doc}`sobre` sobre a licença e a visibilidade antes de publicar.
