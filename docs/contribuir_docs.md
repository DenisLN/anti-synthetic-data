# Como compilar e contribuir com esta documentação

```{include} /_includes/aviso-base.md
```


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
| `docs/estado_prontidao.json` inválido (P-NN faltando ou repetido, estado fora da lista, evidência inexistente) | erro de extensão em `projeto/pendencias.md` (`docs/_ext/pendencias.py`) |

Exceção registrada em `docs/conf.py`: três links relativos quebrados em `CHANGELOG/v1.0.md` e `v1.2.md` (que apontam para `../ametek_orm.py`, `../oscilloscope_orm.py` e `../mestre.py`) são ignorados porque os changelogs fechados não se reescrevem; qualquer outro link quebrado continua falhando.

## 5. Estado das pendências: um arquivo, renderizado no build

O estado das 31 pendências (P-01 a P-31) vive **só** em `docs/estado_prontidao.json`. Nada mais guarda tabela de estado: `docs/PENDENCIAS_TRACKER.md` é apenas o protocolo para agentes, e {doc}`execucao_pendencias` e {doc}`decisoes_pendentes` remetem a {doc}`projeto/pendencias`. No build, a extensão `docs/_ext/pendencias.py` troca a linha `@@pendencias-estado@@` de `docs/projeto/pendencias.md` pelo placar, pelas perguntas ao dono, pela matriz e por uma seção por pendência, gerados do JSON, com a âncora `estado-p-NN` (por exemplo `` {ref}`P-08 <estado-p-08>` ``). Qualquer página pode citar o placar com o marcador `@@pendencias-placar@@` (uma linha com as contagens, fora de código em linha). O pedido original de cada pendência (inventário de 16/10) fica em {doc}`projeto/pendencias-inventario-2026-10-16`, com as âncoras `p-NN`. O que o Read the Docs mostra é, portanto, o que está commitado.

**Fluxo depois de uma coleta:** (1) `python scripts/fechar_pendencias.py --sessao <dir> ... --saida docs/evidencias/<data>/fechamento.json` gera a evidência (não decide); (2) editar o bloco da pendência em `docs/estado_prontidao.json`; (3) `python scripts/gerar_mapa_pendencias.py` (regenera `mapa/pendencias/`); (4) `python -m unittest tests.test_estado_pendencias` e o build `-W`.

**Formato** (`esquema: 3`). Raiz: `atualizado` (data), `nota_atualizacao`, `pendencias` (objeto com as 31 chaves `"P-01"` a `"P-31"`, cada uma uma vez) e `sessoes` (as cinco condições do verificador). Cada pendência:

| Campo | Conteúdo |
|---|---|
| `estado` | `concluida`, `aguarda-bancada` (software pronto, falta bancada), `aguarda-decisao` (falta decisão ou dado do responsável), `em-andamento`, `insuficiente-bancada` (medida feita na bancada, resultado inconclusivo) ou `reprovada-bancada` (medida feita e reprovada) |
| `titulo`, `prioridade` (`alta`, `media`, `baixa`), `responsavel` | identificação |
| `acao` | o que a pendência pede |
| `dependencia`, `criterio` | do que depende e quando fecha |
| `quem_fecha` | lista de `bancada`, `decisao-dono`, `codigo` |
| `frentes` | frentes de trabalho (K, R, D) |
| `falta` | resumo do que falta, usado na matriz (`—` se nada) |
| `falta_por_tipo` | o que falta separado por quem faz: chaves `bancada`, `codigo`, `decisao-dono`; para pendência não concluída tem de ser não vazio e ter as mesmas chaves de `quem_fecha`; `{}` se concluída sem nada a fazer |
| `como_tratada` | obrigatório: como foi resolvida ou, se não está resolvida, o que foi feito até agora (com commit, `arquivo:linha`, sessão ou evidência e o resultado medido) |
| `commits` | hashes (7 a 40 hexadecimais) citados |
| `evidencias` | caminhos relativos a `docs/` de arquivos que existem (por exemplo `evidencias/2026-10-22/fechamento.json`) |
| `decisao_dono` | `registrada` (verdadeira só se `situacao` for `confirmada`), `situacao`, `texto` e `data` (obrigatória se confirmada, com a fonte no texto). `situacao`: `confirmada` (o dono decidiu), `tomada-no-fork` (escolha do fork aguardando o dono), `em-branco` (nada escolhido, resposta do dono em branco) ou `nao-se-aplica`. Se `tomada-no-fork` ou `em-branco`, exige `pergunta`, `opcoes` (lista) e `fonte_opcoes` (`formulario`, `inventario`, `evidencia` ou `sem-opcoes-previas`); `pergunta` também pode acompanhar uma decisão confirmada que gerou um conflito (P-09). Pendência concluída não pode ter a decisão em branco |
| `situacao_execucao`, `entrega`, `direcao_vigente` | opcionais: rótulo e texto migrados de `execucao_pendencias.md` |

A validação está em `docs/_ext/estado_pendencias.py` e roda no build, em `scripts/gerar_mapa_pendencias.py` e em `tests/test_estado_pendencias.py`. `scripts/verificar_prontidao.py --manifesto docs/estado_prontidao.json` lê o mesmo arquivo (conta como concluída a pendência com `estado: concluida` e evidência). O manifesto `docs/manifesto_prontidao.json` segue sendo o modelo vazio no formato antigo (`P01`, `status`).

## 6. Publicar no Read the Docs

O build no serviço depende de conta e importação feitas pelo responsável pelo repositório; o arquivo `.readthedocs.yaml` já está na raiz.

1. Entrar em readthedocs.org e escolher **Import a Project**; autorizar a conta do GitHub e selecionar o repositório `anti-synthetic-data` (o repositório do projeto).
2. Conferir que o serviço achou `.readthedocs.yaml` (configuração `docs/conf.py`, Python 3.12, `docs/requirements.txt`).
3. Definir o nome do projeto e o subdomínio (`*.readthedocs.io`); decisão do responsável.
4. Em **Versions**, ativar `latest` (ramo `main`) e, depois de congelada a v1.15 com a tag `v1.15`, `stable` ({bdg-danger}`PENDENTE P-20`).
5. Disparar o primeiro build e comparar o resultado com o build local. {bdg-warning}`NÃO VERIFICADO` O `.readthedocs.yaml` nunca rodou no serviço; qualquer diferença (versão do Python, rede para o CDN do Mermaid) aparece no primeiro build.
6. Opcional: ativar a pré-visualização de pull request.

O repositório tem a transcrição dos manuais em texto (`docs/manuais_txt/`); os PDFs ficam só na máquina (`docs/*.pdf` no `.gitignore`). Nenhum dos dois entra no site (`exclude_patterns` em `docs/conf.py`); ver {doc}`sobre` sobre a licença e a visibilidade antes de publicar.
