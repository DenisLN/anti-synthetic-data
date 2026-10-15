# 05. Arquitetura do site de documentação

Base: `main` em `fa82f49`, 2026-10-15. Escopo: decisões de ferramenta, árvore de páginas com caminho e ordem do menu, modelo de ficha de classe (12 seções), selos de status, guia de estilo, automação e riscos. Nada aqui altera `docs/`: o site é construído pelas specs 07 e 08 (`04`/`plano.md`). Os arquivos de teste de build estão em `docs-site-plano/prova-de-build/`.

## 1. Decisões em resumo

| Decisão | Escolha | Por quê |
|---|---|---|
| Gerador | Sphinx 9.0.4 + MyST (Markdown) | os 18 `docs/*.md` atuais construíram sem erro e sem aviso de conteúdo (seção 2.3), então nenhum texto precisa ser reescrito para entrar |
| Tema | Furo 2025.12.19 | barra lateral, modo escuro, busca; construiu nas duas plataformas |
| Componentes | sphinx-design 0.7.0 (selos, cartões, abas), sphinxcontrib-mermaid 2.1.1 (diagramas no lugar do TikZ) | os selos viram `{bdg-*}`; Mermaid é desenhado no navegador (JavaScript via CDN), sem Node no build |
| Hospedagem | Read the Docs, `language = "pt_BR"` | pedido da rodada; `.readthedocs.yaml` rascunhado e **não testado no serviço** |
| Raiz do site | `docs/` (a própria pasta atual) | as specs 07 e 08 escrevem em `docs/`; manter os nomes `docs/operacao.md`, `docs/quirks.md`... preserva as cerca de 300 ocorrências de `docs/<nome>.md` em `README.md`, `AGENTS.md`, nos próprios `docs/` e em 9 arquivos `.py` (contagem de 2026-10-15) |
| Troca de ferramenta (MkDocs Material)? | **Não** | a recomendação inicial passou no teste de instalação e de build nas duas plataformas; não há motivo para trocar |
| Ressalva sobre o pedido | uma frase | a spec 07 não menciona o "Guia do código" que o adendo da spec 06 pede ("spec seguinte"); `06-mapa-do-codigo.md` está pronto, falta dizer ao despacho em qual spec o guia entra (proposta: 07 monta o esqueleto `codigo/`; 08 revisa) |

## 2. Ferramentas, versões fixas e prova de build

### 2.1 Versões instaladas e testadas

Arquivo: `docs-site-plano/prova-de-build/requirements.txt` (cinco pacotes pedidos, versões exatas) e `requirements-lock.txt` (o `pip freeze` completo, 36 pacotes, para reproduzir também as dependências transitivas).

| Pacote | Versão fixa | Função | Observação |
|---|---|---|---|
| Sphinx | 9.0.4 | gerador | exige Python 3.11 ou mais novo |
| myst-parser | 5.1.0 | Markdown com diretivas | extensões usadas: `colon_fence`, `dollarmath`, `amsmath`, `deflist`, `attrs_inline` |
| furo | 2025.12.19 | tema | `html_theme_options` com `source_repository` |
| sphinx-design | 0.7.0 | selos, grades, cartões | `{bdg-success}`, `{bdg-info}`, `{bdg-warning}`, `{bdg-danger}`, `{bdg-secondary}` |
| sphinxcontrib-mermaid | 2.1.1 | diagramas | `mermaid_output_format = "raw"`; baixa o Mermaid 11.12.1 (jsDelivr) no navegador; o MathJax 4 também vem de CDN |
| dependências relevantes | docutils 0.22.4, Jinja2 3.1.6, Pygments 2.21.0, markdown-it-py 4.2.0 | | `requirements-lock.txt` |

### 2.2 Build mínimo (comando e saída)

Conteúdo de teste: `index.md`, `classe-exemplo.md` (selos, avisos padronizados, fórmula, Mermaid, listagem por símbolo e por linhas, tabela) e `historico-exemplo.md` (inclusão do `CHANGELOG/v1.15.md` sem copiá-lo).

| Plataforma | Ambiente | Comando | Resultado |
|---|---|---|---|
| Windows 11 (10.0.26200) | Python 3.11.9, venv novo | `python -m sphinx -W --keep-going -b html docs-site-plano/prova-de-build <saida>` | `build succeeded.`, código de saída 0, nenhum aviso (`-W` transforma aviso em erro) |
| Linux (kernel 7.2.7-zen1, via `ssh denis@aspire5050`) | Python 3.14.7, venv novo em `/tmp/asd-teste-docs/venv` | o mesmo comando | `build succeeded.`, código de saída 0 |

Limites do teste: (1) o Read the Docs usa Python 3.12 no rascunho (`.readthedocs.yaml`); 3.12 **não** foi testado (3.11.9 e 3.14.7 passaram; NÃO VERIFICADO no serviço); (2) o Linux foi acessado por `ssh` porque o WSL deste PC não tem distribuição e não há Docker; (3) o diretório de teste `/tmp/asd-teste-docs` ficou no `aspire5050` (a regra desta rodada proíbe `rm`); (4) os diagramas e as fórmulas dependem de CDN em tempo de leitura (offline, a página mostra o código-fonte do diagrama).

### 2.3 O conteúdo atual constrói

Prova com o conteúdo real: `sphinx -c <conf-minimo> --keep-going -b html docs <saida>` sobre os 18 `docs/*.md` (raiz = `arquitetura.md`, `exclude_patterns = ["manuais_txt", "*.pdf"]`). Saída: código 0 e **17 avisos, todos `toc.not_included`** (documento fora de qualquer `toctree`, esperado porque o teste não tem índice); **nenhum** aviso de cabeçalho, link, tabela ou sintaxe. Conclusão: os documentos atuais entram no site sem edição; o `-W` do site final exige só que cada página esteja num `toctree`. Os PDFs e `manuais_txt/` ficam fora (sufixo não fonte e `exclude_patterns`).

### 2.4 Inclusão do CHANGELOG sem cópia

`{include} ../../CHANGELOG/v1.15.md` com `:heading-offset: 1` (665 linhas) construiu com `-W` no Windows e no Linux. Plano: `docs/historico/vX.Y.md` com uma linha de `{include}` cada (16 arquivos pequenos) e `docs/historico.md` com o `toctree`; o CHANGELOG continua o registro histórico original, sem duplicar texto.

### 2.5 Rascunho do Read the Docs

```yaml
version: 2
build:
  os: ubuntu-24.04
  tools:
    python: "3.12"
sphinx:
  configuration: docs/conf.py
  fail_on_warning: true
python:
  install:
    - requirements: docs/requirements.txt
```

(Em `prova-de-build/.readthedocs.yaml` os caminhos apontam para a prova; o definitivo usa `docs/`.) Decisões do usuário necessárias: importar o repositório no serviço (conta do usuário), nome do projeto e do domínio (`*.readthedocs.io`), política de versões (`latest` = `main`; `stable` = tag `v1.15` depois de congelada, P-20). Pull request preview é opcional.

## 3. Árvore de páginas e ordem do menu

Regras: (1) nomes de arquivo existentes **não mudam** (as referências `docs/<nome>.md` do repositório continuam válidas); (2) arquivos novos usam minúsculas, hífens e subpastas por família; (3) uma pasta e o arquivo de mesmo nome (por exemplo `scpi.md` e `scpi/`) formam um índice com `toctree`; (4) o menu lateral segue a ordem numérica abaixo; (5) "Spec" é quem escreve a página (07 ou 08, conforme `plano.md`).

### 3.1 Raiz e visão geral

| # | Caminho | Título | Origem do conteúdo | Spec |
|---|---|---|---|---|
| 0 | `docs/index.md` | Início | `README.md:3-19`, mapa das seções, estado (selos agregados) | 07 |
| 1.1 | `docs/visao-geral.md` | O projeto em uma página | novo; `README.md`, `docs/arquitetura.md` §1 | 07 |
| 1.2 | `docs/como-ler.md` | Como ler esta documentação (selos, avisos, convenções) | novo; seções 4 e 6 deste arquivo | 07 |
| 1.3 | `docs/arquitetura.md` | Arquitetura | existente, reescrito em volta de `06` §1-§3 | 07 |
| 1.4 | `docs/glossario.md` | Glossário | existente | 07 |

### 3.2 Operação

| # | Caminho | Título | Origem | Spec |
|---|---|---|---|---|
| 2.1 | `docs/operacao.md` | Operação da bancada | existente; corrige divergências 1, 2, 7 e 9 de `01` §6 | 07 |
| 2.2 | `docs/seguranca.md` | Limites inegociáveis e camadas de segurança | novo; `AGENTS.md` (limites), `06` §3 | 07 |
| 2.3 | `docs/configuracao.md` | Variáveis de ambiente | existente | 07 |
| 2.4 | `docs/roteiro-bancada.md` | Roteiro da próxima bancada | `{include}` de `ROTEIRO_BANCADA.md` (raiz), selo PENDENTE | 07 |
| 2.5 | `docs/diagnostico.md` | Diagnóstico | existente | 07 |

### 3.3 Referência SCPI (um comando por entrada)

| # | Caminho | Título | Conteúdo | Spec |
|---|---|---|---|---|
| 3.0 | `docs/scpi.md` | Referência SCPI | índice: transporte, sincronismo `*ESR?`, transcrição, convenções, como ler uma entrada | 07 |
| 3.1 | `docs/scpi/ametek-estado.md` | AMETEK: identificação, erros e estado | `*IDN?`, `*CLS`, `*ESR?`, `*OPC?`, `*WAI`, `*TRG`, `SYSTem:ERRor?`, `STATus:OPERation:CONDition?`, `OUTPut:STATe`, `ABORt`, `INITiate:IMMediate`, `TRIGger:STATe?` | 07 |
| 3.2 | `docs/scpi/ametek-baseline.md` | AMETEK: estado seguro inicial | `INSTrument:COUPle`, `SOURce:MODE`, `SOURce:VOLTage:RANGe/HIGH`, `SOURce:CURRent*`, `SOURce:FUNCtion:SHAPe`, modos `FIXed`, `SLEW`, `TRIGger:SOURce/SYNChronize`, `OUTPut:TTLTrg*` | 07 |
| 3.3 | `docs/scpi/ametek-imediatos.md` | AMETEK: valores imediatos e medidas | `SOURce:FREQuency`, `SOURce:VOLTage`, `LEVel:IMMediate:AMPLitude`, `MEASure:*` | 07 |
| 3.4 | `docs/scpi/ametek-nativo.md` | AMETEK: caminho nativo (01-05, 18, 19) | `VOLTage:MODE STEP/PULSe`, `VOLTage:TRIGgered`, `PULSe:WIDTh`, `SOURce:FUNCtion:SHAPe:CSINusoid`, `SOURce:MODE ACDC`, `SOURce:VOLTage:OFFSet`, `FREQuency:MODE LIST`, `LIST:FREQuency` | 07 |
| 3.5 | `docs/scpi/ametek-lista-trace.md` | AMETEK: TRACe e lista (06-17, 20) | `TRACe:CATalog?/DEFine/DATA/DATA?/DELete:ALL`, `SOURce:LIST:*`, `FUNCtion:MODE LIST`, `VOLTage:MODE LIST` | 07 |
| 3.6 | `docs/scpi/ametek-nao-funciona.md` | AMETEK: comandos que falham ou não são usados | `CSINe`, `LIST:REPeat:COUNt`, `SOURce:MODE?`, `SYSTem:REMote` | 07 |
| 3.7 | `docs/scpi/keysight-aquisicao.md` | Keysight: aquisição e escala | `:ACQuire:*`, `:TIMebase:*`, `:CHANnel<n>:*` | 07 |
| 3.8 | `docs/scpi/keysight-trigger.md` | Keysight: trigger e estado | `:EXTernal:*`, `:TRIGger:*`, `:AER?`, `:TER?`, `:SINGle`, `:OPERegister:CONDition?` | 07 |
| 3.9 | `docs/scpi/keysight-waveform.md` | Keysight: waveform e medidas | `:WAVeform:*`, `:MEASure:VMAX?/VMIN?/VRMS?` | 07 |
| 3.10 | `docs/scpi/diagnostico.md` | Comandos só de diagnóstico | seção 3.4 de `02-lacunas.md` | 07 |
| 3.11 | `docs/scpi/transcricoes.md` | Exemplos reais da transcrição | E01-E71 de `02-lacunas.md` §4 (a partir de dados versionados, P-29) | 07 |

Entrada de comando (modelo): título = comando; campos: **Instrumento**, **Sintaxe**, **O que faz** (uma frase), **Parâmetros**, **Quem envia** (símbolo, nunca linha), **Sincronismo e espera**, **Erros e quirks** (A/K do `quirks.md`), **Manual** (página do PDF), **Exemplo real** (`W comando` e `R comando -> resposta`, com sessão e condição), **Classes que usam**, **Selo**. Âncora `(scpi-<chave>)=` antes do título; todo comando SCPI no texto do site usa `{scpi}`` `TRACe:DATA` `` que resolve a âncora (seção 7).

### 3.4 Fichas das 20 classes

`docs/classes.md` (índice com a tabela de 20 linhas gerada do código, o selo de cada classe e o link) e uma ficha por classe em `docs/classes/`, escritas pela spec 08. Modelo na seção 5.

| Classe | Arquivo | Classe | Arquivo |
|---|---|---|---|
| 01 NORMAL | `classes/01-normal.md` | 11 SAG_FLICKER | `classes/11-sag-flicker.md` |
| 02 SAG | `classes/02-sag.md` | 12 SAG_OSCILLATORY_TRANSIENT | `classes/12-sag-oscillatory-transient.md` |
| 03 SWELL | `classes/03-swell.md` | 13 SWELL_HARMONICS | `classes/13-swell-harmonics.md` |
| 04 INTERRUPTION | `classes/04-interruption.md` | 14 SWELL_OSCILLATORY_TRANSIENT | `classes/14-swell-oscillatory-transient.md` |
| 05 HARMONICS | `classes/05-harmonics.md` | 15 HARMONICS_FLICKER | `classes/15-harmonics-flicker.md` |
| 06 FLICKER | `classes/06-flicker.md` | 16 INTERRUPTION_HARMONICS | `classes/16-interruption-harmonics.md` |
| 07 NOTCH | `classes/07-notch.md` | 17 NOTCH_OSCILLATORY_TRANSIENT | `classes/17-notch-oscillatory-transient.md` |
| 08 TRANSIENT | `classes/08-transient.md` | 18 FREQUENCY_DRIFT | `classes/18-frequency-drift.md` |
| 09 OSCILLATORY_TRANSIENT | `classes/09-oscillatory-transient.md` | 19 DC_OFFSET | `classes/19-dc-offset.md` |
| 10 SAG_HARMONICS | `classes/10-sag-harmonics.md` | 20 INTERHARMONICS | `classes/20-interharmonics.md` |

Ao fim do índice: `docs/perfis.md` (existente), que vem logo depois das fichas (4.22).

### 3.5 Medição e calibração

| # | Caminho | Título | Origem | Spec |
|---|---|---|---|---|
| 5.1 | `docs/medicao.md` | Medição: cadeia, janela, margens e pré-trigger | novo; `02/atividade.tex:213-328` como modelo; `quirks.md` | 07 |
| 5.2 | `docs/limites_e_calibracao.md` | Limites e pré-validação | existente | 07 |
| 5.3 | `docs/calibracao.md` | Recalibração passo a passo | novo; lacuna (d) de `02` §2.4; `P-07`, `P-21` | 07 |
| 5.4 | `docs/correlacao_disturbio.md` | Correlação esperada por classe | existente, mais a tabela de `02` §2.3 | 07 |
| 5.5 | `docs/quirks.md` | Quirks dos equipamentos | existente (corrige B8, divergência 1) | 07 |

### 3.6 Dataset

| # | Caminho | Título | Spec |
|---|---|---|---|
| 6.1 | `docs/dataset.md` | Formatos e como carregar | 07 |
| 6.2 | `docs/metadata.md` | Metadata | 07 |
| 6.3 | `docs/tres_versoes.md` | Três versões: modelo, programada, medida | 07 |

### 3.7 Desenvolvimento ("Guia do código", a partir de `06-mapa-do-codigo.md`)

| # | Caminho | Título | Origem em `06` | Spec |
|---|---|---|---|---|
| 7.0 | `docs/codigo.md` | Guia do código | §1 e §6 | 07 (proposta) |
| 7.1 | `docs/codigo/fluxos.md` | Fluxos de controle e de dados | §2 | 07 |
| 7.2 | `docs/codigo/invariantes.md` | Invariantes e camadas de segurança | §3 | 07 |
| 7.3 | `docs/codigo/mestre.md` | `mestre.py` | §4.1 | 07 |
| 7.4 | `docs/codigo/ametek_orm.md` | `ametek_orm.py` | §4.2 | 07 |
| 7.5 | `docs/codigo/oscilloscope_orm.md` | `oscilloscope_orm.py` | §4.3 | 07 |
| 7.6 | `docs/codigo/sinais_perfis.md` | `sinais.py` e `perfis.py` | §4.4, §4.5 | 07 |
| 7.7 | `docs/codigo/cli_preflight.md` | `cli.py` e `preflight_new.py` | §4.6, §4.7 | 07 |
| 7.8 | `docs/codigo/sessao_io_analise.md` | Leitura, análise offline e relatório | §4.8-§4.13 | 07 |
| 7.9 | `docs/codigo/classes_contrato.md` | Contrato das classes e ganchos | §4.14 | 07/08 |
| 7.10 | `docs/codigo/scripts.md` | Scripts e testes | §4.15, §4.16 | 07 |
| 7.11 | `docs/codigo/acoplamentos.md` | "Se mudar isto, aquilo quebra" | §5 | 07 |
| 7.12 | `docs/estender.md`, `docs/testes.md`, `docs/decisoes.md`, `docs/versionamento.md` | existentes | | 07 |

### 3.8 Projeto e estado

| # | Caminho | Título | Origem | Spec |
|---|---|---|---|---|
| 8.1 | `docs/estado.md` | Estado do projeto | versão, contagem de testes, selos agregados; gerado | 07 |
| 8.2 | `docs/pendencias.md` | Pendências por classe e globais | `04-pendencias.md` convertido em `docs/_dados/pendencias.yaml`; filtro por classe | 07 |
| 8.3 | `docs/historico.md` + `docs/historico/v1-0.md` ... `v1-15.md` | Histórico (CHANGELOG) | `{include}` dos 16 arquivos | 07 |
| 8.4 | `docs/sobre.md` | Como citar, licença, versões e Zenodo | P-20 | 08 |

Arquivos de apoio (não são páginas): `docs/conf.py`, `docs/requirements.txt`, `docs/_ext/` (extensões locais), `docs/_dados/` (YAML gerado), `docs/_static/` (CSS dos selos). Total: 1 índice + 4 (visão geral) + 5 (operação) + 12 (SCPI) + 22 (classes e perfis) + 5 (medição) + 3 (dataset) + 16 (desenvolvimento, contando as 4 existentes como 4 páginas) + 3 (estado e histórico) + 16 (histórico) + 1 (sobre) = 88 páginas, das quais 18 já existem.

## 4. Selos de status

**Seção definida aqui; `03-fontes-por-classe.md` e `04-pendencias.md` usam estes nomes.**

| Selo | Cor (sphinx-design) | Quando usar | Evidência exigida |
|---|---|---|---|
| VERIFICADO NA BANCADA | `{bdg-success}` verde | o fato foi medido ou observado na bancada física, com sessão, condição e commit | sessão (`sessao_2026-10-07_127V_50Hz`), condição (127 V/50 Hz) e fonte (transcrição, `.npz`, relatório) |
| OFFLINE | `{bdg-info}` azul | conferido sem hardware: leitura de código, simulação ou análise de dados já gravados | `arquivo:linha` (ou símbolo), comando e saída, e a data |
| NÃO VERIFICADO | `{bdg-warning}` amarelo | afirmação sem evidência disponível ou dependente de bancada | **motivo** obrigatório: o que falta e quem pode fechar |
| PENDENTE | `{bdg-danger}` vermelho | existe item aberto, com id `P-NN` | id da pendência |
| FORA DA MAIN | `{bdg-secondary}` cinza | só existe em branch (hoje `feat/passo-final-sin`, PR #3) ou em material de arquivo | branch e commit |

Regras: (1) um selo por afirmação, não por página; página de classe e comando abrem com a linha de selos que a resumem; (2) VERIFICADO NA BANCADA vale só para **a condição citada** (127 V/60 Hz, 127 V/50 Hz, 230 V/50 Hz) e para o **código da data** (hoje: tudo pré-v1.15, P-01); (3) um selo NÃO VERIFICADO sem motivo falha a revisão; (4) quando uma pendência fecha, o selo PENDENTE sai e o id passa para "Resolvidas" em `pendencias.md` (os ids não são reaproveitados); (5) OFFLINE nunca vira VERIFICADO NA BANCADA sem sessão nova.

Avisos padronizados (substituem os blocos "Comentário" e "Questão" do original):

| Aviso | Diretiva MyST | Uso |
|---|---|---|
| Nota de verificação | `:::{note} Nota de verificação` | conferência independente, resultado de teste ou medida que apoia ou limita o texto (voz impessoal: "Conferido offline: ...") |
| Decisão em aberto | `:::{warning} Decisão em aberto` | escolha que só o responsável pelo projeto faz; sempre com a pergunta, as opções e o id `P-NN` |
| Pendência | `:::{important} Pendência P-NN` | item aberto com id, o que fecha e prioridade |
| Limitação | `:::{caution} Limitação` | restrição física ou de projeto que o leitor precisa saber antes de usar o dado |
| Atenção de segurança | `:::{danger} Segurança` | só para os limites inegociáveis e ações que energizam |

Testados na prova de build: `note`, `warning` e `important` com título (`classe-exemplo.md`); `caution` e `danger` são diretivas padrão do docutils e não foram exercitadas (NÃO VERIFICADO no tema, esperado igual).

## 5. Modelo de ficha de classe (12 seções)

Cada ficha tem esta ordem, com estes títulos, e abre com o bloco de identificação e a linha de selos.

**Bloco de abertura (antes da seção 1).** Título `# Classe NN: NOME`; linha de selos (estado geral e pendências); tabela de identificação: número, nome, arquivo (`experimentos_nativos/NN.py` ou `experimentos_waveform/NN.py`, com `:pyobject:`), mecanismo na bancada, `capturas_padrao`, sorteio (I/D/F), independente do perfil? (`perfis.classes_independentes_do_perfil`), condições já medidas. Fonte: tabela de `docs/classes.md` e `03`.

| # | Seção | Conteúdo | Fontes e como obter |
|---|---|---|---|
| 1 | Em uma resposta | pergunta que a classe responde e a **resposta em negrito** (o que a classe produz, em uma frase), mais o resumo de estado | `docs/classes.md` linha da classe; `experimentos.txt` |
| 2 | Definição e modelo | o fenômeno, o item da IEEE 1159-2019 (`atividade.tex:1063-1088` como tabela de referência), a fórmula em notação matemática ($v(t)=\dots$), termos definidos na primeira vez | `gerar()` e `sinais.py`; norma |
| 3 | Parâmetros e perfis | faixas por perfil (`norma`, `literatura`, `fronteira`), sorteio de início, duração e fase, `capturas_padrao`, níveis discretos | `perfis.py` (`FAIXAS`, `COMPONENTES_POR_CLASSE`), `docs/perfis.md` |
| 4 | Como `gerar()` constrói a forma | fluxo (Mermaid), ordem das chamadas ao `rng`, listagem `literalinclude :pyobject: Experimento.gerar`, chaves de metadata | `experimentos_*/NN.py`; `06` §4.14 |
| 5 | Mecanismo na bancada | passo a passo da programação com `{scpi}`; nativa: `configurar()` e o método do ORM; waveform: `program_capture`, `arm_transient`, `trigger`; ganchos de bancada | `ametek_orm.py`, `mestre._capturar_real`; `02` §3 |
| 6 | Limites e segurança | pré-validação, extremo previsto (`pico × fator × 1,10`), teto (415,8 V; 0,9 × na 08), limite de bancada `k`, tabela por condição | `limites_e_calibracao.md`; `calibracao_extremos.json` (lido pelo build) |
| 7 | Janela, posição e margens | início, duração, fase, pré-trigger, `inicio_janela`, margem de 20/50 ms, o que a margem contém nesta classe | `medicao.md`; `mestre._calcular_margem` |
| 8 | Correlação esperada e validação física | correlação do distúrbio (nominal e ajustada) por condição, envelope/THD/crista, fator de crista | `02` §2.3 (tabela de hoje); `analisar_sessao.py`; `sinais.comparar_fisicamente` |
| 9 | Medidas de bancada | tabela por condição (127 V/60 Hz, 127 V/50 Hz, 230 V/50 Hz): capturas, pico medido, razão de pico, k aplicado, com sessão e fonte; figura quando existir | relatórios de 13/10 e dados de 07/10 (`03`) |
| 10 | Quirks e armadilhas | A/K/B do `quirks.md` que se aplicam; acoplamentos de `06` §4.14 ("se mudar isto, aquilo quebra") | `quirks.md`; `06` |
| 11 | Histórico | linha do tempo por versão (v1.7 a v1.15) com o motivo de cada mudança, no estilo "Por que existe a margem" | seções do CHANGELOG listadas em `03` |
| 12 | Estado e pendências | selos, `P-NN` abertas, o que as fecha, decisões em aberto | `04-pendencias.md` |

Exemplo de esqueleto MyST (testado em `prova-de-build/classe-exemplo.md`): título, linha de selos, "**Pergunta:** ... **Resposta:** ...", `:::{note}`/`:::{warning}`/`:::{important}`, fórmula `$$...$$`, ` ```{mermaid} `, ` ```{literalinclude} ... :pyobject: Experimento.gerar `, tabela por condição.

Regras da ficha: o que não existe fica com a seção e o texto "Sem medida de bancada com o código da v1.15" (selo NÃO VERIFICADO), não é omitido; tamanho proporcional (as classes simples 01-04, 19 têm seções curtas); nenhuma ficha contém número sem condição e fonte.

## 6. Guia de estilo

Extraído de `C:\Users\denis\Downloads\tcc\02\atividade.tex` (1.283 linhas, lido por inteiro) e `...\01\atividade.tex` (1.075 linhas; é o mesmo texto sem os blocos de comentário). Os exemplos parafraseiam o original e citam a linha (`02:NNN`).

**6.1 Cada assunto abre com a pergunta e a resposta direta em negrito; o porquê vem depois.** O original põe a pergunta em itálico e a resposta em negrito logo abaixo (`02:56-58`, `:79`, `:218`, `:337`, `:433`, `:700`): "O modo simulado reproduz a forma enviada à fonte? **Sim para o vetor de 6000 amostras que sai de `gerar()`.**" seguido de "mas esse vetor não é o que a fonte reproduz, por três motivos". Regra: nenhuma página começa pela história; começa pela resposta.

**6.2 O contexto e o histórico entram dentro da explicação.** Exemplos: "Por que existe a margem" (`02:309-321`) conta que nas primeiras inspeções (v1.7 e v1.8, setembro de 2026) a forma parecia 20 ms atrasada, que a análise de 21/09 achou duas causas (referência do osciloscópio uma divisão à direita; a fonte tocava cada ciclo duas vezes), que a margem ficou "por decisão de projeto (v1.11, 22/09/2026)" com 20 ms antes e 50 ms depois. "Classe 01 a 127 V/60 Hz" (`02:378-388`) liga a tensão a 0 V na 01 às versões v1.7, v1.13 e v1.14. Regra: o que se pensava, o que a medida mostrou, qual versão corrigiu, por quê, com datas; cada página constrói sobre a anterior ("como visto na Pergunta 2").

**6.3 Todo termo é definido na primeira vez e liga à página que o aprofunda.** O original define "pu" na abertura (`02:45-47`: a tensão dividida pelo pico nominal $\sqrt{2}V_\text{base}$), "TRACE" na primeira ocorrência (`:86-89`: forma arbitrária de um ciclo, 1024 pontos), "SCPI" (`:47`: a linguagem de comandos dos dois instrumentos) e "pré-trigger" (`:226-228`). No site: primeira ocorrência = definição curta + link para o glossário ou a página; `{term}` do glossário do Sphinx.

**6.4 Números reais sempre com condição e fonte; tabelas por condição.** O original compara três condições em colunas (127 V/60 Hz | 127 V/50 Hz | 230 V/50 Hz) com legenda de origem ("medido nos `.npz` das três sessões", `02:404-420`), cita a razão fonte/osciloscópio como "1,004-1,005 em 07/10" (`:569`) e a tabela de limites tem coluna "Fonte" (`:603-621`). Regra: nenhum número sem condição (tensão/frequência), sessão ou arquivo e commit; tabelas largas por condição.

**6.5 Erros e limitações admitidos com franqueza.** "A causa exata ainda é hipótese" (`02:869`), "ainda não testado na bancada" (`:979`), "a regra impediu justamente as classes que precisavam ser medidas para sair dela" (`:647-649`), "isso deve constar no TCC como limitação física da bancada" (`:861-862`). Regra: dizer o que não se sabe, com o selo NÃO VERIFICADO e o motivo; sem tom pessoal (o original traz uma confissão em primeira pessoa em `:651-652` que **não** se reproduz).

**6.6 Todo comando SCPI no texto é um link para a entrada de referência, e cada entrada traz um exemplo da transcrição real.** O original usa `\scpi{chave}{texto}` (`:4`) e a macro `\cmdscpi{chave}{comando}{exemplo}{significado}` (`:11`); as entradas têm a forma `W SOURce:VOLTage:OFFSet 5.5795947`, `R TRACe:CATalog? -> "SINE,SQUARE,CLIPPED"`, `R MEASure:VOLTage:AC? -> 126.525` (`:1215`, `:1240`, `:1260`) e, para o osciloscópio, a ressalva "comando enviado pelo código" porque não há transcrição (`:1189-1190`, `:1276`). No site: papel `{scpi}`, âncora `(scpi-chave)=`, exemplos de `docs/_dados/transcricoes.yaml`, e o aviso de ausência de transcrição do Keysight.

**6.7 Listagens do código real com o caminho, fórmulas em notação matemática e diagramas.** `lstlisting` com legenda de caminho (`02:96`, `:515`, `:719`, `:736`), `\lstinputlisting` com linhas (`:146`, `:923`), fórmulas ($\text{início}=\text{indice\_trigger}-\text{pre\_trigger\_s}\cdot f_s$, `:300-303`; $v_\text{bancada}=\text{senoide}+k\,(\text{gerar()}-\text{senoide})$, `:710-713`), figura TikZ da janela (`:250-286`). No site: `literalinclude` com `:caption:` do caminho e `:pyobject:` (não números de linha, seção 2.2 e `01` §5), `$$...$$` para fórmulas, ` ```{mermaid} ` no lugar do TikZ.

**6.8 Os blocos de comentário do original viram avisos padronizados, sem atribuição a pessoas.** Os ambientes `comentario` e `questao` (`02:14-21`) têm 19 usos (18 de `comentario` e 1 de `questao`); conforme o conteúdo viram: nota de verificação (conferência independente: "com a seed e o `nivel_indice` do metadata, o `gerar()` reproduz os parâmetros", `:117-119`), decisão em aberto (propostas e perguntas: perfis `norma`/`literatura`/`fronteira`, `:1090-1108`; margem final com a forma `SIN`, `:472-474`) ou pendência com id. Reescrever em voz impessoal ("Conferido offline: ...") e remover elogios, pedidos ("mandem a sessão") e menções a quem comentou.

**6.9 Estrutura repetida que funciona.** Parágrafo de convenções logo na abertura (`02:45-50`); lista das sessões e condições usadas (`:33-37`); seção "Propostas" numerada com remissões (`:972-1034`); tabela de adequação à norma com colunas modelo atual / norma / enquadra / proposta (`:1063-1088`); apêndice de comandos com entrada fixa (`:1185-1283`). No site: a abertura da ficha (seção 5) e a entrada SCPI (seção 3.3) herdam essas formas.

**6.10 Fonte e versão do código na abertura.** O original afirma "conferidas no código (versão v1.14, `main` em `34a0d82`), nos registros de alteração e nos dados das três sessões" (`02:27-31`). No site: carimbo único no rodapé de cada página (`versão e commit`), gerado no build, em vez de repetir o commit em cada parágrafo.

**6.11 Lista de verificação para revisão de uma página.** (1) Abre com pergunta e resposta em negrito? (2) Todo número tem condição e fonte? (3) Todo SCPI é `{scpi}`? (4) Todo termo novo é definido? (5) Todo NÃO VERIFICADO tem motivo? (6) Nenhuma citação por número de linha à mão? (7) Nenhum nome de pessoa? (8) Há link para a pendência `P-NN`? (9) O build com `-W` passa?

## 7. Automação no build (para a spec 07)

| Recurso | Como | Evita | Estado |
|---|---|---|---|
| Papel `{scpi}` e âncoras | extensão local (`docs/_ext/scpi.py`) lê `docs/_dados/scpi.yaml`; com `-W` um comando sem entrada falha | link quebrado, comando sem exemplo | não escrito (NÃO VERIFICADO; extensão pequena, mas fora da prova de build) |
| Listagens por símbolo | `literalinclude :pyobject:` (nativo) | linha envelhecida (`01` §5) | **testado** na prova (Windows e Linux) |
| Linha de um símbolo no texto | papel `{codigo}` resolve `mestre.py::Bancada.from_env` com `ast` em tempo de build | citação à mão | não escrito |
| Tabela de classes | script AST sobre `experimentos_*/NN.py` (`id`, `nome`, `capturas_padrao`, ganchos) | segunda tabela divergente (`01` §3) | não escrito |
| `HELP_TEXT` da CLI | `from cli import HELP_TEXT` num bloco gerado | `operacao.md` copiando à mão | não escrito; importar `cli.py` exige `PYTHONPATH=logica` e `numpy` no ambiente de build (RTD instala via `requirements.txt` do site; custo a medir) |
| Contagem de testes | `unittest` coleta no build (`loadTestsFromModule`) | "370 testes" desatualizado (`01` §6, 3) | não escrito; 497 testes importam `numpy` e `PyMeasure` quando não simulado: NÃO VERIFICADO no RTD |
| Tabela de extremos | ler `logica/calibracao_extremos.json` | tabela copiada | não escrito |
| Pendências | `pendencias.yaml` → tabela e filtros por classe | 15 lugares com estado | não escrito |
| CHANGELOG | `{include}` | cópia | **testado** (v1.15, 665 linhas, `-W`) |
| Transcrições SCPI | `transcricoes.yaml` versionado (P-29) | exemplo sem fonte | depende da decisão do usuário |

Cuidado com `-W` e a automação: qualquer código gerador que importe `mestre.py` executa o módulo (lê variáveis de ambiente e valida a bancada ao criar `Config`/`Bancada`, não ao importar; `validate_bench_configuration` só roda em `Bancada.from_env`). NÃO VERIFICADO: importar `mestre` no RTD sem `BENCH_MODE`; usar `ast` (sem importar) elimina o risco e é a recomendação.

## 8. Riscos e decisões abertas

| # | Item | Gravidade | Decisão ou ação |
|---|---|---|---|
| R-1 | Manuais PDF/TXT (AMETEK e Keysight, 15,4 MB) estão no repositório e não podem ir ao site público | média | não publicar; o site cita página e comando e linka o fabricante; verificar licença (NÃO VERIFICADO: visibilidade e licença do repositório; `atividade.tex:58` afirma que o repositório é público, e não há `LICENSE`, P-20) |
| R-2 | Mermaid e MathJax via CDN | baixa | aceitar; alternativa: `mermaid_output_format="svg"` exige Chromium/`mmdc` no build (não testado) |
| R-3 | Pull request e branch: o site entra por `docs/site-readthedocs`; mexe em `AGENTS.md` e `README.md` (spec 08) | média | a spec 08 só atualiza o mapa de documentação |
| R-4 | O estado do código muda (v1.15 em andamento) | média | carimbo por commit; rebuild a cada push; `stable` só depois da tag |
| R-5 | `AGENTS.md` fica na raiz com texto para agentes e "dono" (P-25) | baixa | não publicar como página; citar as regras inegociáveis em `seguranca.md` |
| R-6 | Duas fontes de verdade dos limites 300/415,8 V (código e scripts) | média | `seguranca.md` lê de `mestre.py` por `ast`; recomendar unificar no código (fora do escopo) |
| R-7 | Transcrição SCPI só local (P-29) | média | decisão do usuário |
| R-8 | Linha `.readthedocs.yaml` não testada no serviço | baixa | testar no primeiro import |
| R-9 | `01-inventario.md` §6: 14 divergências doc×código; o site só deve publicar o texto corrigido | média | spec 07 corrige ao migrar |
