#spec #pri 06

# ASD Docs: Auditoria, Lacunas e Arquitetura do Site de Documentação

## Contexto

O repositório é de um TCC: uma bancada (fonte AMETEK MX30 + osciloscópio Keysight DSO-X 4034A, mais um simulador em NumPy) que gera o dataset de 20 classes de distúrbio de tensão para um analisador de qualidade de energia em ESP32. A documentação cresceu por camadas e está espalhada: `README.md`, 18 arquivos em `docs/*.md` (~1.500 linhas), `AGENTS.md`, `ROTEIRO_BANCADA.md`, `CHANGELOG/v1.0.md` a `v1.15.md` (a v1.15 sozinha tem 665 linhas) e relatórios datados que ficam no branch de arquivo `arquivo/analises`. O mesmo fato aparece em vários lugares (por exemplo classe 08 e classe 06 em `docs/classes.md`, `docs/correlacao_disturbio.md` e `CHANGELOG/v1.15.md`).

Objetivo da rodada de 10 specs ("ASD Docs: ..."): publicar no Read the Docs um site profissional, bem estruturado e com tema moderno, com (a) uma ficha completa por classe (as 20), (b) referência SCPI comando a comando (`TRACe:DATA`, `LIST:VOLTage`, `CSINusoid` etc.), (c) a correlação esperada em cada classe, (d) a recalibração passo a passo, (e) pendências por classe. Esta é a primeira spec: ela só **audita e planeja**; as seguintes constroem.

Estado do código e dos branches (conferir, não presumir):
- `main` local em `fa82f49` (v1.15 em andamento, sem tag), já avançada por fast-forward a partir do remote `github` (`git@github.com:DenisLN/anti-synthetic-data.git`). O remote `origin` (aspire5050) está atrás.
- Branch `github/arquivo/analises`: histórico que saiu de `docs/` em 2026-10-13: `docs/analise-2026-09-21/`, `docs/analise-2026-09-30/`, `docs/analise-2026-10-12/` (`pendente/`, `resolvido/`, `limites_perfis/`, `scripts/`), `sessao-13-10-2026/` (`ESTADO.md`, `relatorio-final.md`, `ROTEIRO_BANCADA.md`, `wip/`) e `specs/2026-10-13/` (specs 10 a 26 e relatórios individuais). A análise mais recente é a de `sessao-13-10-2026` / `specs/2026-10-13` (concluída em 2026-10-15) e **nada nela foi validado na bancada** (a bancada de 14/10 ainda não rodou).
- Branch `github/feat/passo-final-sin` (PR #3, commit `18b144d`): passo final `SINE` no `LIST` das classes TRACe. **Pendente de validação na bancada, fora da `main`.** Está atrás da `main`; o diff bruto contra a `main` é enganoso, comparar com `git diff $(git merge-base main github/feat/passo-final-sin) github/feat/passo-final-sin`.

## Entradas

- Projeto: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data` (git, branch `main`).
- Documentação atual: `README.md`, `AGENTS.md`, `ROTEIRO_BANCADA.md`, `docs/*.md`, `CHANGELOG/*.md`, `experimentos.txt`.
- Código das classes: `experimentos_nativos/{01,02,03,04,05,18,19}.py` e `experimentos_waveform/{06,...,17,20}.py`; motor em `logica/` (`mestre.py`, `ametek_orm.py`, `oscilloscope_orm.py`, `sinais.py`, `perfis.py`, `modelo_lista_fonte.py`, `analisar_sessao.py`, `sessao_io.py`, `relatorio_html.py`, `calibracao_extremos.json`); scripts em `scripts/`.
- Leitura de outros branches sem trocar de branch: `git show github/arquivo/analises:<caminho>` e `git ls-tree -r --name-only github/arquivo/analises`; idem para `github/feat/passo-final-sin`.
- Manuais em texto: `docs/manuais_txt/AMETEK_MX_SCPI_Programming_Manual.txt` e `docs/manuais_txt/Keysight_4000X_Programmers_Guide.txt`.
- Depende de: nada
- Executor: sonnet

## Missão

1. Inventariar a documentação atual: uma tabela com cada arquivo de `docs/*.md`, `README.md`, `AGENTS.md`, `ROTEIRO_BANCADA.md` e `CHANGELOG/v1.15.md` (tamanho em linhas, assunto, seções, a quem se dirige: operador, desenvolvedor ou leitor do TCC) e, ao lado, os fatos que aparecem em mais de um arquivo (duplicações) e os que estão só em um lugar escondido (por exemplo só em seção do CHANGELOG). Conferir por amostragem de pelo menos 40 citações `arquivo:linha` de `docs/classes.md`, `docs/scpi.md` e `docs/limites_e_calibracao.md` contra o código atual e listar as que estão desatualizadas.
2. Mapear as lacunas contra o conjunto-alvo, uma linha por item: (a) ficha das 20 classes; (b) referência SCPI por comando, no mínimo `TRACe:DATA`, `TRACe:DEFine`, `TRACe:DELete`, `TRACe:CATalog?`, `SOURce:LIST:VOLTage/FREQuency/SHAPe/DWELl/COUNt/STEP`, `VOLTage:MODE LIST/STEP/PULSe/FIXed`, `FUNCtion:MODE`, `SOURce:FUNCtion:SHAPe CSINusoid` e `:CSINusoid`, `SOURce:MODE ACDC` com `SOURce:VOLTage:OFFSet`, `TRIGger:SYNChronize`, `OUTPut:TTLTrg`, `*TRG`, `*WAI`, `*ESR?`, e todo comando que `ametek_orm.py` e `oscilloscope_orm.py` enviam (obter por busca no código, não só pela lista); mais os comandos do Keysight de trigger, aquisição, waveform e medida; (c) correlação esperada por classe; (d) recalibração passo a passo; (e) pendências por classe. Para cada item: onde está hoje (arquivo:linha) e o que falta.
3. Montar, para cada uma das 20 classes, uma ficha de fontes: arquivo da classe e linhas de `gerar()`, `configurar()` e ganchos de bancada; seções do CHANGELOG que a alteraram (v1.7 a v1.15); relatórios de `github/arquivo/analises` que a citam, com a conclusão de cada um em uma frase; estado de verificação em bancada (verificado em qual sessão e condição, ou NÃO VERIFICADO).
4. Levantar as pendências por classe e as globais, lendo `docs/analise-2026-10-12/pendente/*`, `sessao-13-10-2026/ESTADO.md`, `sessao-13-10-2026/relatorio-final.md` (inclusive as "Sua decisão" ainda em aberto), `ROTEIRO_BANCADA.md`, a seção "NÃO VERIFICADO" de cada `docs/*.md` e o diff real do branch `feat/passo-final-sin`. Para cada pendência, conferir no código atual da `main` se ainda vale (algumas foram resolvidas depois; marcar RESOLVIDA com o commit) e atribuir um id estável `P-NN`, a classe afetada (ou GLOBAL), a fonte, o que a fecha (bancada, decisão do usuário ou código) e a prioridade.
5. Propor a arquitetura de informação do site e fixar as escolhas: árvore de páginas com nome de arquivo e ordem do menu (visão geral, operação, referência SCPI, fichas das 20 classes, medição e calibração, dataset, desenvolvimento, projeto/estado), o modelo exato de ficha de classe com 12 seções, a convenção de selos de status (VERIFICADO NA BANCADA, OFFLINE, NÃO VERIFICADO, PENDENTE, FORA DA MAIN) e a escolha de ferramenta. A recomendação inicial é Sphinx + MyST + tema Furo + sphinx-design + sphinxcontrib-mermaid, publicado no Read the Docs, em pt_BR; só trocar (por exemplo por MkDocs Material) se um teste de instalação e build mínimo no Windows e no Linux mostrar problema, e então justificar. Registrar versões fixas de cada pacote que o teste instalou.

## Limites

- Somente leitura no código e nos documentos existentes. Só criar arquivos dentro da pasta nova `docs-site-plano/` na raiz do repositório.
- Não editar `logica/`, `experimentos_*/`, `scripts/`, `tests/`, `.env*`, `AGENTS.md`, `README.md`, `docs/`, `CHANGELOG/`.
- Não trocar de branch nem fazer merge; ler outros branches só com `git show` e `git ls-tree`. Não fazer push.
- O código vence o CHANGELOG: onde divergirem, registrar a divergência.
- Não inventar números nem estado de verificação: o que não achar em arquivo, linha, sessão ou comando fica NÃO VERIFICADO.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.
- Se algum limite impedir ou restringir o resultado, registrar no relatório em "Limitações de escopo", sem ultrapassá-lo.

## Entregável

- Relatório `.md` no caminho que o despacho indicar, com: um bloco por item da Missão (copiar o texto do item, dizer CUMPRIDO, PARCIAL, NÃO CUMPRIDO ou IMPEDIDO, e explicar nos dois casos, com evidência); Critério de Parada atendido ou não; pendências que exigem o usuário; limitações de escopo; se a missão resolve o contexto; achados.
- `docs-site-plano/01-inventario.md` (item 1).
- `docs-site-plano/02-lacunas.md` (item 2).
- `docs-site-plano/03-fontes-por-classe.md` (item 3, as 20 classes).
- `docs-site-plano/04-pendencias.md` (item 4, com os ids `P-NN`).
- `docs-site-plano/05-arquitetura-do-site.md` (item 5: árvore de páginas, modelo de ficha, selos, ferramentas e versões fixas).
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

Os cinco arquivos existem em `docs-site-plano/`; `03-fontes-por-classe.md` tem as 20 classes; toda pendência de `04-pendencias.md` tem id, fonte, o que a fecha e conferência contra o código atual; `05-arquitetura-do-site.md` lista cada página com caminho de arquivo e traz o modelo de ficha com as 12 seções e os selos; as versões fixas de ferramenta foram instaladas e um build mínimo passou (comando e saída no relatório), ou o motivo de não ter passado está registrado.

## Adendo: estilo de redação de referência (vale para o item 5 e para toda a rodada)

O usuário tem uma documentação anterior, em LaTeX, feita para um professor, que define o estilo desejado: `C:\Users\denis\Downloads\tcc\02\atividade.tex` (1283 linhas; ler inteira) e `C:\Users\denis\Downloads\tcc\01\atividade.tex`. Em `05-arquitetura-do-site.md`, incluir uma seção "Guia de estilo" extraída desses dois arquivos, com exemplos curtos tirados deles (parafrasear, sem copiar trechos longos), cobrindo no mínimo:
- Cada assunto abre com a pergunta que ele responde e a **resposta direta em negrito**, e só depois vem o porquê.
- O contexto e o histórico entram de forma implícita, na própria explicação: o que se pensava, o que a medida mostrou, qual versão corrigiu e por quê (parágrafos como "Por que existe a margem", com versões v1.8, v1.11 e datas), sempre construindo em cima do que a página anterior já definiu; todo termo é definido na primeira vez em que aparece e linka a página que o aprofunda.
- Números reais sempre com a condição (127 V/60 Hz, 127 V/50 Hz, 230 V/50 Hz) e a fonte; tabelas por condição; erros e limitações admitidos com franqueza.
- Todo comando SCPI no texto é um link para sua entrada de referência, e cada entrada traz um exemplo tirado da transcrição real da bancada (`W comando` e `R comando -> resposta`).
- Listagens do código real com o caminho do arquivo, fórmulas em notação matemática e diagramas (no site, Mermaid no lugar do TikZ).
- Os blocos de comentário do original viram avisos padronizados do site (nota de verificação, decisão em aberto), sem atribuição a pessoas.

## Adendo de 2026-10-15 (prevalece sobre o texto acima onde houver conflito)

1. **Fonte histórica: só a análise mais recente.** Usar como fonte de análises apenas `github/arquivo/analises:sessao-13-10-2026/` (`ESTADO.md`, `relatorio-final.md`, `ROTEIRO_BANCADA.md`, `wip/`) e `github/arquivo/analises:specs/2026-10-13/` (incluindo `relatorios-individuais/`), mais `CHANGELOG/v1.15.md` e o código atual. As análises de 21/09, 30/09 e 12/10 já foram revisadas: não auditá-las, não reproduzi-las e não listar suas pendências antigas; só consultá-las quando um fato atual precisar de uma transcrição SCPI real ou de um número que os docs atuais já citam. A pasta `pendente/` de 12/10 só entra pelo que `sessao-13-10-2026` e `specs/2026-10-13` dizem dela.
2. **Local de trabalho.** Escrever no worktree `C:\Users\denis\Documents\1 Projetos\asd-docs-site` (branch `docs/site-readthedocs`, já criado a partir da `main` em `fa82f49`). `docs-site-plano/` fica na raiz desse worktree e é commitado lá (`docs: plano do site de documentação`). Não escrever no checkout principal. O Python do projeto está em `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data\env\Scripts\python.exe` (usar com o diretório de trabalho no worktree); as ferramentas do site vão para um venv novo no scratchpad. O worktree do arquivo é `C:\Users\denis\Documents\1 Projetos\asd-analises` (branch `arquivo/analises`) e só o despacho escreve nele.
3. **Objetivo de compreensão total.** Quem ler a documentação final precisa entender **todas as intricâncias do código** e compreendê-lo por inteiro sem abrir o código. Acrescentar um sexto item à Missão: **6. Montar o mapa do código** em `docs-site-plano/06-mapa-do-codigo.md`: para cada arquivo de `logica/`, `experimentos_nativos/`, `experimentos_waveform/` e `scripts/`, a responsabilidade, as classes e funções principais com `arquivo:linha`, o fluxo de dados e de controle entre eles, os invariantes e as camadas de segurança, as armadilhas e os acoplamentos entre partes ("se mudar isto, aquilo quebra") e o motivo histórico de cada decisão estranha (consultar `CHANGELOG/v1.7.md` a `v1.15.md`, `docs/quirks.md`, `docs/decisoes.md`). Esse mapa alimenta o "Guia do código" do site (spec seguinte). O Critério de Parada passa a exigir também esse arquivo, cobrindo todos os módulos listados.
4. Executor: sonnet, esforço high.
