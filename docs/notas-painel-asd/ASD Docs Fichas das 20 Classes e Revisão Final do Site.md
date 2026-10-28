#spec #pri 08

# ASD Docs: Fichas das 20 Classes e Revisão Final do Site

## Contexto

Terceira e última de 3 specs ("ASD Docs: ...") que criam o site de documentação do projeto no Read the Docs. A primeira (`ASD Docs: Auditoria, Lacunas e Arquitetura do Site de Documentação`) deixou em `docs-site-plano/` o inventário, as fontes por classe, as pendências `P-NN`, o modelo de ficha com 12 seções, os selos de status e o guia de estilo. A segunda (`ASD Docs: Site no Read the Docs e Páginas Transversais (SCPI, Correlação, Recalibração, Pendências)`) montou o site no branch `docs/site-readthedocs` e escreveu a referência SCPI comando a comando, a correlação esperada por classe, a recalibração passo a passo, o estado de validação e as pendências. **Esta spec escreve a ficha completa de cada uma das 20 classes ("tintim por tintim") e fecha o projeto com a revisão final.**

Estilo obrigatório: o do guia de estilo de `docs-site-plano/05-arquitetura-do-site.md`, que vem dos documentos de referência do usuário `C:\Users\denis\Downloads\tcc\02\atividade.tex` e `...\01\atividade.tex` (ler antes de escrever). Cada ficha conta a classe do problema até a bancada: a pergunta que ela responde com a resposta direta em negrito; o fenômeno e a norma; o modelo em `gerar()`; por que a bancada o reproduz daquela forma, **com o histórico implícito** (o que se tentou, o que a medida mostrou, que versão corrigiu — por exemplo a 08 que a fonte filtra, a 06 que perde a média por ciclo na TRACe, a 05 com o teto da CSINusoid, a 18 que passou a f0 ± 3 Hz, a 19 com o CA 5 a 6 % menor em ACDC, a 07/17 com entalhes em todos os ciclos); números sempre com a condição e a fonte; comandos SCPI como link para a entrada da referência criada na spec anterior, com a sequência exata na ordem.

Estado a respeitar: `main` em `fa82f49`, v1.15 em andamento. O SINE (`github/feat/passo-final-sin`) e a análise de 13 a 15/10 (`github/arquivo/analises`, `sessao-13-10-2026/`) **não foram validados na bancada**; o passo final SINE não está na `main` e nenhuma ficha o descreve como existente.

## Entradas

- Projeto: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`, branch de trabalho `docs/site-readthedocs` (criado na spec anterior; continuar nele).
- Plano e páginas já escritas: `docs-site-plano/03-fontes-por-classe.md` (arquivo, linhas, CHANGELOG e relatórios por classe), `docs-site-plano/04-pendencias.md` (ids `P-NN`), e as páginas do site: referência SCPI, `docs/medicao/correlacao.md`, `docs/medicao/recalibracao.md`, `docs/projeto/*`.
- Código das classes: `experimentos_nativos/{01,02,03,04,05,18,19}.py`, `experimentos_waveform/{06,07,08,09,10,11,12,13,14,15,16,17,20}.py`; `logica/mestre.py`, `logica/sinais.py`, `logica/perfis.py`, `logica/ametek_orm.py`, `logica/modelo_lista_fonte.py`; `experimentos.txt` (especificação original); `docs/classes.md`, `docs/perfis.md`.
- Relatórios históricos por classe: `git show github/arquivo/analises:docs/analise-2026-09-21/...`, `...analise-2026-09-30/...`, `...analise-2026-10-12/...`, `sessao-13-10-2026/...`, `specs/2026-10-13/relatorios-individuais/...`.
- Comandos de conferência offline: `.\env\Scripts\python.exe -m unittest tests.test_offline` e `scripts/relatorio_limites_bancada.py`.
- Depende de: ASD Docs: Site no Read the Docs e Páginas Transversais (SCPI, Correlação, Recalibração, Pendências)
- Executor: sonnet

## Missão

1. Escrever as fichas das classes **nativas 01, 02, 03, 04, 05, 18 e 19** em `docs/classes/NN-nome.md`, cada uma com as 12 seções do modelo (resumo e selos; o fenômeno e a norma; modelo matemático em `gerar()` com parâmetros, sorteio de início, duração e fase, seed e `capturas_padrao`; como a bancada reproduz, com a sequência SCPI exata e `arquivo:linha`; parâmetros por perfil `norma`, `literatura` e `fronteira`; limites físicos e fator de extremo por condição; validação física e suas tolerâncias; as três versões e a correlação esperada, linkando a tabela da página de correlação; quirks; histórico por versão; estado de verificação e pendências com os ids `P-NN`; referências). Cobrir os níveis discretos das 02, 03 e 05 e o teto da CSINusoid de 20 % da 05.
2. Escrever as fichas das classes **por waveform 06, 07, 08, 09 e 20**, no mesmo modelo, com atenção às particularidades: 06 (média por ciclo da TRACe, flicker, correlação do distúrbio), 07 (entalhes em todos os ciclos, oscilação da fonte, crista), 08 (impulso filtrado, três limitações independentes, teto de 0,9 × `max_peak_v`, deslocamento a 100 ms, fora do sorteio), 09 (cópia do evento em 100 ms), 20 (145, 210 e 330 Hz).
3. Escrever as fichas das classes **compostas 10, 11, 12, 13, 14, 15, 16 e 17**, no mesmo modelo, explicando como cada uma combina componentes (sag ou swell com harmônicos, flicker ou transitório oscilatório; 15 e 16; 17 com entalhes e oscilação), o que o sorteio cobre em cada componente (`docs/perfis.md`, "Compostas sorteadas"), a média por ciclo nos ciclos de borda das 10, 11, 12 e 16 e o limite de bancada com o fator `k` quando o pico não cabe.
4. Converter `docs/classes.md` em página de visão geral das 20 classes (tabela com link para cada ficha, mecanismo, sorteio e capturas padrão), **sem perder nenhum fato** hoje presente nele: cada fato precisa existir em alguma ficha ou página transversal (listar a correspondência no relatório). Conferir cada número, nome de parâmetro e `arquivo:linha` das 20 fichas contra o código da `main` (rodar o verificador que o relatório descrever, por exemplo um script em `docs-site-plano/` que confira que cada `arquivo:linha` citado existe) e corrigir o que divergir.
5. Fazer a **revisão final**: build do site sem warning e `linkcheck` dos links internos; nenhuma página-esqueleto "em redação" restante; checklist de cobertura contra `docs-site-plano/02-lacunas.md` (20 fichas, SCPI, correlação, recalibração, pendências, estado de validação); atualizar o mapa de documentação de `README.md` e de `AGENTS.md` (seção "Documentação (mapa)") para apontar para o site e a nova árvore, e acrescentar a seção correspondente em `CHANGELOG/v1.15.md`; abrir o site construído no navegador embutido em largura de desktop e de celular, tema claro e escuro, e registrar o que viu; escrever no relatório os passos para o usuário importar o repositório no Read the Docs (conta, URL do repositório, versões `latest` e tags).

## Limites

- Só documentação e arquivos de configuração do site. Não editar `logica/`, `experimentos_*/`, `scripts/`, `tests/`, `.env*`, `calibracao_extremos.json`. Os arquivos de `docs/` existentes ficam nos mesmos caminhos; `docs/classes.md` é reescrito no lugar, não movido.
- Não reescrever `CHANGELOG/vX.Y.md` fechados nem relatórios datados.
- Rodar a suíte offline e scripts offline é permitido; **não** energizar, não abrir conexão com instrumento.
- Docs autocontidos: sem nome de pessoa, "professor", "dono" nem referência ao texto de origem. O código vence o CHANGELOG; divergências são registradas na ficha.
- Estado de verificação honesto: o que não tem sessão de bancada que o confirme fica NÃO VERIFICADO; o que só existe no branch SINE fica FORA DA MAIN.
- Trabalhar no branch `docs/site-readthedocs`; commits por mudança lógica (`docs: resumo em português`, com a linha `Co-Authored-By` indicada pelo harness); sem push nem merge.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.
- Se algum limite impedir ou restringir o resultado, registrar no relatório em "Limitações de escopo", sem ultrapassá-lo.

## Entregável

- Relatório `.md` no caminho que o despacho indicar, com: um bloco por item da Missão (copiar o texto do item, dizer CUMPRIDO, PARCIAL, NÃO CUMPRIDO ou IMPEDIDO, e explicar nos dois casos, com evidência); Critério de Parada atendido ou não; pendências que exigem o usuário; limitações de escopo; se a missão resolve o contexto; achados.
- 20 fichas `docs/classes/01-*.md` a `docs/classes/20-*.md` e `docs/classes.md` reescrito como visão geral.
- Tabela no relatório: cada fato antigo de `docs/classes.md` e onde ele está agora.
- Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline` (saída no relatório, para mostrar que nada do código mudou) e `python -m sphinx -W --keep-going -b html docs docs/_build/html` sem warning.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

Existem as 20 fichas com as 12 seções preenchidas (sem "em redação" nem `PREENCHER`); `docs/classes.md` aponta para todas e nenhum fato antigo se perdeu (tabela no relatório); o build passa sem warning e o `linkcheck` interno não acusa link quebrado; a suíte `tests.test_offline` passa sem alteração de código; `README.md`, `AGENTS.md` e `CHANGELOG/v1.15.md` apontam para o site; cada pendência `P-NN` de uma classe aparece na ficha dela e na página de pendências.

## Adendo de 2026-10-15 (prevalece sobre o texto acima onde houver conflito)

1. **Fonte histórica: só a análise mais recente.** Para o histórico e as pendências de cada classe, usar apenas `github/arquivo/analises:sessao-13-10-2026/`, `github/arquivo/analises:specs/2026-10-13/relatorios-individuais/`, `CHANGELOG/v1.15.md` e o código atual. As análises de 21/09, 30/09 e 12/10 já foram revisadas: não reabri-las; o histórico anterior de uma classe entra só pelo que o CHANGELOG e os docs atuais já dizem.
2. **Local de trabalho.** Continuar no worktree `C:\Users\denis\Documents\1 Projetos\asd-docs-site` (branch `docs/site-readthedocs`). Python do projeto: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data\env\Scripts\python.exe` com cwd no worktree (a suíte `tests.test_offline` roda de lá); ferramentas do site no venv do scratchpad criado na spec anterior.
3. **Objetivo de compreensão total.** Cada ficha deve permitir entender a classe **inteira no nível do código**: além das 12 seções, uma seção "Como o código da classe funciona" que percorre o arquivo `NN.py` método por método (`gerar`, `configurar`, `forma_para_bancada`, `parametros_com_disturbio_reduzido`, ganchos de bancada, `capturas_padrao`, validação física e o que cada um recebe, devolve e quem o chama), com `arquivo:linha`, linkando as páginas do Guia do código (`docs/codigo/`). A revisão final (item 5) confere também que o Guia do código e as fichas não se contradizem.
4. Executor: sonnet, esforço high. O relatório vai para o caminho que o despacho indicar.
