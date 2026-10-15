# 01. Inventário da documentação existente

Base: `main` em `fa82f49` (v1.15 em andamento, sem tag), lida em 2026-10-15. Somente leitura: nada fora de `docs-site-plano/` foi alterado. Contagens de linhas e bytes saem de `splitlines()`/`wc -c` desta data; `arquivo:linha` é da árvore de `fa82f49`. Selos: VERIFICADO NA BANCADA, VERIFICADO OFFLINE (conferido no código ou em teste nesta rodada), NÃO VERIFICADO, PENDENTE, FORA DA MAIN.

## 1. Escopo e método

- **Lido por inteiro**: `README.md`, `AGENTS.md`, `ROTEIRO_BANCADA.md`, `experimentos.txt`, os 18 `docs/*.md`, os 16 `CHANGELOG/v*.md` (cabeçalhos e as seções da v1.7 em diante), `logica/*.py`, as 20 classes e `scripts/*`.
- **Lido por amostragem de cabeçalhos**: `CHANGELOG/v1.0` a `v1.6` e `v1.8`/`v1.9` (só títulos, para o mapa de versões); os dois manuais em `docs/manuais_txt/` (busca dirigida por comando SCPI, não leitura integral).
- **Análises do branch `github/arquivo/analises`** (FORA DA MAIN): somente `sessao-13-10-2026/` (7 arquivos) e `specs/2026-10-13/` (23 arquivos, `git show`/`git ls-tree`), como manda o adendo. As pastas `docs/analise-2026-09-21`, `2026-09-30`, `2026-10-12` e `docs/superpowers` (216 arquivos de `docs/analise-*`) **não foram reauditadas**; só entram quando as fontes acima as citam.
- **Auditoria de citações**: script AST (scratchpad) que resolve cada `arquivo:linha` citado em `classes.md`, `scpi.md` e `limites_e_calibracao.md` para o símbolo e compara com a linha atual. Resultado na seção 5.
- **Conferências por execução** (resultados em `04-pendencias.md` seção 2): `tests.test_offline` no Windows (497 OK, 0 pulados) e `scripts/diag_ciclos_trace.py` (offline) nas sessões reais de 07/10.

## 2. Inventário das fontes

### 2.1 Documentos Markdown e texto na `main`

Tipo segue a divisão Diátaxis usada no site (T = tutorial, C = como fazer, R = referência, E = explicação, H = histórico/registro).

| Arquivo | Linhas | Bytes | Papel hoje | Tipo | Estado |
|---|---|---|---|---|---|
| `README.md` | 72 | 5523 | porta de entrada, início rápido, resumo de segurança, mapa dos docs | E/C | carimbo de versão correto (v1.15 sem tag); recomenda `run all` (ver P-23) |
| `AGENTS.md` | 277 | 15925 | instrução ao agente + autorizações datadas + limites inegociáveis + versionamento | R/E | autoridade de segurança; texto escrito para agentes de IA, não para leitor humano externo |
| `ROTEIRO_BANCADA.md` | 490 | 44505 | roteiro de 10 blocos da próxima bancada, tabela de decisão, modelo de tempo | C | idêntico (mesmo blob `b1b5aef`) às cópias de `sessao-13-10-2026/` e `specs/2026-10-13/` do branch de arquivo; execução = PENDENTE |
| `experimentos.txt` | 166 | 4398 | especificação original das 20 classes | R/H | `docs/classes.md` lista onde o código difere |
| `docs/arquitetura.md` | 155 | 14491 | componentes, fluxos, camadas de segurança, scripts | E/R | carimbo `d37e403`; títulos com `arquivo:linha` antigos |
| `docs/classes.md` | 76 | 9414 | tabela das 20 classes, capturas por classe, 08, 05, 06, 09 | R | carimbo `d37e403`; 12 citações, 10 deslocadas |
| `docs/configuracao.md` | 60 | 5741 | variáveis de ambiente, regras de `validate_bench_configuration` | R | cabeçalho cita `mestre.py:366-387` (hoje 418-439) |
| `docs/correlacao_disturbio.md` | 102 | 12350 | métrica de correlação do distúrbio, tabela de 07/10, fundamental ajustada | R/E | faixa de referência de origem ausente (P-27) |
| `docs/dataset.md` | 128 | 13691 | formatos 1 e 2 do `.npz`, escrita, como carregar, ferramentas offline | R/C | recomenda carregar sem `allow_pickle`; o leitor do projeto usa `allow_pickle=True` (divergência 11) |
| `docs/decisoes.md` | 66 | 9388 | decisões de arquitetura e de segurança com motivo | E | sem selo por decisão |
| `docs/diagnostico.md` | 79 | 12835 | `set diagnostico`, roteiro, scripts `diag_*`, achados em espera | C/R | carimbo `d37e403` |
| `docs/estender.md` | 113 | 11744 | como criar classe, contrato de `gerar()`, erros já cometidos | C/E | carimbo `d37e403`; "370 testes" (hoje 497) |
| `docs/glossario.md` | 39 | 5369 | termos | R | tabela única |
| `docs/limites_e_calibracao.md` | 54 | 6090 | tensões, pré-validação, limite de bancada, fatores de extremo | R | 7 citações, todas deslocadas |
| `docs/metadata.md` | 118 | 10535 | campos de `sessao.json` e do registro de captura | R | só se acrescenta |
| `docs/operacao.md` | 163 | 18590 | ligação física, CLI, confirmações, falhas, depois da sessão, HTML e recalibração | C | carimbo `d37e403`; HTML "3 primeiras" diverge do código (divergência 7) |
| `docs/perfis.md` | 56 | 7569 | perfis `norma`/`literatura`/`fronteira`, compostas | R/E | |
| `docs/quirks.md` | 68 | 14112 | A1-A25 (fonte), K1-K10 (osciloscópio), B1-B9 (bancada/PC) | R | B8 contradiz o código (divergência 1) |
| `docs/scpi.md` | 130 | 13730 | comandos SCPI de cada instrumento com `arquivo:linha` | R | 66 citações, 20 exatas (19 do osciloscópio e `ler_trace`), 46 deslocadas |
| `docs/testes.md` | 35 | 4756 | mapa da suíte, fixtures, quando rodar | R | "370 testes, 57 classes" (hoje 497 e 66) |
| `docs/tres_versoes.md` | 62 | 8108 | `modelo`/`programada`/`medida` | E/R | "99 capturas" contra "63" em `AGENTS.md:125` |
| `docs/versionamento.md` | 74 | 9480 | regras, congelamento, CHANGELOG, mensagens de commit, mapa de versões | R/C | |
| `docs/AMETEK_MX_SCPI_Programming_Manual.pdf` | - | 1.259.567 | manual da fonte | R | material de terceiros (ver achado A-5) |
| `docs/Keysight_4000X_Programmers_Guide.pdf` | - | 10.382.368 | guia do osciloscópio | R | idem |
| `docs/manuais_txt/*.txt` | - | 494.011 e 3.283.969 | extração em texto dos dois manuais | R | idem; a extração serve de fonte para as conferências `Manual.txt:NNNN` |

Total: 2.417 linhas nos 21 arquivos Markdown (`README.md`, `AGENTS.md`, `ROTEIRO_BANCADA.md` e os 18 de `docs/`), mais `experimentos.txt` (166); `CHANGELOG/` acrescenta 3.701 linhas (contagens por arquivo na seção 2.2).

### 2.1.1 Seções e a quem cada arquivo se dirige

Operador = quem energiza a fonte; desenvolvedor = quem altera o código; leitor do TCC = quem lê o trabalho ou usa o dataset; mantenedor = quem versiona e congela. A coluna "A quem se dirige" é avaliação do executor a partir do texto de cada arquivo (não há declaração de público nos documentos). Seções = cabeçalhos `##` (a ordem é a do arquivo; números de seção e parênteses longos foram abreviados).

| Arquivo | Linhas | Seções (`##`) | A quem se dirige |
|---|---|---|---|
| `README.md` | 72 | Início rápido; Segurança; Mapa da documentação; Estrutura (resumo); Pendente fora da `main` | leitor do TCC; desenvolvedor (primeiro contato) |
| `AGENTS.md` | 277 | Fluxo do operador (a partir da v1.7); O que pode ser refatorado; Limites inegociáveis (não mudar em nenhuma hipótese); Documentação (mapa); Como escrever sobre mudanças no código; Como versionar | agente de IA e mantenedor; regras de segurança para o operador |
| `ROTEIRO_BANCADA.md` | 490 | Regras fixas do dia; Visão geral e tempo; Blocos em ordem de execução; Tabela de decisão: o que muda na campanha do mesmo dia; Modelo de tempo e de gravações de TRACe; Plano da campanha em partes (127 V, 60 Hz); Checklist de entrega ao fim do dia; Conferência dos comandos e confirmações no código; Limites deste roteiro (NÃO VERIFICADO) | operador |
| `docs/arquitetura.md` | 155 | Visão geral; Mapa de arquivos; Componentes; Fluxo da bateria física; Fluxo de uma classe; Camadas de segurança (todas independentes); Scripts | desenvolvedor |
| `docs/classes.md` | 76 | Tabela; Capturas por classe na bancada; Classe 08: impulso filtrado pela fonte; Classe 05 e o teto do CSINusoid; Classe 06 e a média por ciclo da TRACe; Classe 09 e o impulso em 100 ms | desenvolvedor; leitor do TCC |
| `docs/configuracao.md` | 60 | Variáveis lidas pelo código; Regras de `validate_bench_configuration()`; Variáveis que NÃO existem na `main` | operador; desenvolvedor |
| `docs/correlacao_disturbio.md` | 102 | Função; Caso degenerado; Onde aparece; Tabela nas sessões de 07/10; Teste; NÃO VERIFICADO; Correlação com a fundamental ajustada (v1.15, pendentes); Pendentes verificados no código (v1.15) | leitor do TCC; desenvolvedor |
| `docs/dataset.md` | 128 | Onde os dados caem; Formatos; Metadata (resumo; completo em `docs/metadata.md`); Carregar os dados; Ferramentas offline; Gerar o dataset simulado | leitor do TCC (usuário do dataset); desenvolvedor |
| `docs/decisoes.md` | 66 | Arquitetura e dados; Segurança e hardware | desenvolvedor; leitor do TCC |
| `docs/diagnostico.md` | 79 | `set diagnostico on` (CLI); Roteiro de investigação; Scripts de diagnóstico; Achados que esperam diagnóstico na bancada | desenvolvedor; operador |
| `docs/estender.md` | 113 | Criar uma classe nova; Erros já cometidos — não repetir; Outras extensões | desenvolvedor |
| `docs/glossario.md` | 39 | (sem `##`; tabela única) | todos |
| `docs/limites_e_calibracao.md` | 54 | Tensões de teste; Pré-validação (antes de qualquer SCPI); Limite de bancada (classes waveform); Fatores de extremo (`logica/calibracao_extremos.json`); Como calibrar uma condição nova; Relatório offline do que cabe; Checagem da cadeia de medição | operador; desenvolvedor |
| `docs/metadata.md` | 118 | Arquivos; `sessao.json`; Registro de captura (`NN_classe.json` / linha do `.jsonl`); Exemplo | leitor do TCC (usuário do dataset) |
| `docs/operacao.md` | 163 | Ligação física obrigatória; Software; A CLI (`bancada>`); Confirmações físicas (não automatizar); O que acontece em um `run` e como ler o resultado; Limites por tensão e frequência; Se algo falhar; Depois da sessão; Relatório HTML e recalibração ao fim do run | operador |
| `docs/perfis.md` | 56 | Compostas sorteadas: o que cada componente cobre | leitor do TCC; desenvolvedor |
| `docs/quirks.md` | 68 | AMETEK MX30 (Rev. 5.53); Keysight DSO-X 4034A; Cadeia de medição, PC e bancada; Armadilhas de código já documentadas | desenvolvedor; operador |
| `docs/scpi.md` | 130 | Camada de transporte (AMETEK); AMETEK MX30-3Pi; Keysight DSO-X 4034A | desenvolvedor |
| `docs/testes.md` | 35 | Mapa por área; Fixtures (`tests/fixtures/`); Quando rodar | desenvolvedor |
| `docs/tres_versoes.md` | 62 | `programada`; Onde ficam; Como regenerar (sem hardware, sessões do formato 1); O que não está confirmado | leitor do TCC; desenvolvedor |
| `docs/versionamento.md` | 74 | Regras; Armadilhas do critério "limpo" (verificadas no código); Procedimento de congelamento; Como escrever uma entrada de CHANGELOG; Mensagens de commit (padrão do histórico); Mapa das versões; Trabalho pendente fora da `main`; Índice do `CHANGELOG/` | mantenedor |
| `CHANGELOG/v1.15.md` | 665 | 27 seções datadas, de "O que mudou em `gerar()`" a "Roteiro da próxima bancada" (títulos completos em `grep '^## ' CHANGELOG/v1.15.md`) | desenvolvedor (registro histórico) |

### 2.2 `CHANGELOG/`

`v1.0` 279, `v1.1` 109, `v1.2` 35, `v1.3` 81, `v1.4` 43, `v1.5` 207, `v1.6` 208, `v1.7` 329, `v1.8` 297, `v1.9` 121, `v1.10` 285, `v1.11` 237, `v1.12` 161, `v1.13` 427, `v1.14` 217, `v1.15` 665 linhas (92.909 bytes; 27 seções de nível 2). Modelo de entrada: Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO (`docs/versionamento.md` §4). Regra: o CHANGELOG fechado é registro histórico e não se reescreve; o código vence o CHANGELOG. A v1.15 acumula 27 seções datadas de 2026-10-12 a 2026-10-15 (specs 10 a 26), o que a torna a fonte mais completa e a mais difícil de ler como documentação: cada seção é um diário, não uma referência. Estado: v1.15 **não congelada** (P-20).

### 2.3 Código e testes (fonte da verdade)

| Pasta | Arquivos | Linhas | O que a documentação do site extrai |
|---|---|---|---|
| `logica/` | 12 `.py`, `calibracao_extremos.json` (82), `modelos/relatorio_capturas.html` | 11.094 (`.py`) | mapa do código (`06`), SCPI (`02`), quirks |
| `experimentos_nativos/` | 7 (01-05, 18, 19) | 989 no total com a pasta seguinte | fichas das classes (`03`) |
| `experimentos_waveform/` | 13 (06-17, 20) | (idem) | idem |
| `scripts/` | 6 `.ps1`/`.cmd`, 12 `.py` (3.537 linhas `.py`) | | operação, diagnóstico |
| `tests/` | `test_offline.py` 9.429 (66 classes `TestCase`, 497 testes), 2 auxiliares, 22 fixtures | | selo VERIFICADO OFFLINE |

### 2.4 Material fora da `main`

| Origem | Conteúdo | Uso nesta rodada |
|---|---|---|
| `github/arquivo/analises:sessao-13-10-2026/` | `ESTADO.md` (21), `relatorio-final.md` (181), `ROTEIRO_BANCADA.md` (490), `wip/` (2 patches e 2 `*-base.txt`) | fonte de pendências e decisões (`04`) |
| `github/arquivo/analises:specs/2026-10-13/` | `relatorio-final.md`, `ROTEIRO_BANCADA.md`, 3 specs, `relatorios-individuais/` (`plano.md` + 7 sem pendências e 10 com pendências, numerados 10 a 26) | fontes por classe (`03`) |
| `github/arquivo/analises:docs/analise-*`, `docs/superpowers` | 216 arquivos | não reauditados (adendo) |
| `github/feat/passo-final-sin` (PR #3) | passo final `SINE`; 457 inserções e 13 remoções em 6 arquivos (`git diff d37e403`) | selo FORA DA MAIN em tudo que o cite |
| `github/claude/specs-v1-15-review-3w2bgl` | branch de revisão | não lido |
| `resultados/` (local, gitignored) | sessões de 07/10 com `scpi_transcricao.log` (3 arquivos, 6.846 a 9.675 linhas) | exemplos reais de SCPI (`02` §3); não estão em nenhum branch (P-29) |

## 3. Duplicações (o mesmo fato em vários lugares)

"Ocorrências" = número de arquivos entre `README.md`, `AGENTS.md`, `ROTEIRO_BANCADA.md` e `docs/*.md` em que a busca textual encontra o termo (busca em 2026-10-15). "Fonte única proposta" é onde o site deve manter o texto; as outras páginas devem apenas linkar ou incluir o trecho (diretiva `include`/`literalinclude`), nunca copiar.

| Fato | Ocorrências | Onde | Fonte única proposta | Risco da duplicação |
|---|---|---|---|---|
| Limites 300 Vrms / 415,8 Vp / 425 Vp / 270 V | 7 docs (`415,8`) | README, ROTEIRO (7 vezes), `configuracao`, `decisoes`, `glossario`, `limites_e_calibracao` (2), `operacao`; em código: `start_bench_windows.ps1:94-101`, `mestre.py` (padrões do ambiente), `relatorio_limites_bancada.py`, `diag_*` | `limites_e_calibracao` gerada com o valor lido de `mestre.py` | alto: três cópias em scripts; mudar um e esquecer outro enfraquece a pré-validação |
| `COM10` / 115200 fixos | 9 docs | README, AGENTS (2), ROTEIRO (2), `arquitetura`, `configuracao` (2), `decisoes`, `estender`, `operacao` (2), `quirks` (2) | página de configuração | baixo; é invariante |
| 6000 amostras, 200 ms, 30 kSa/s | 14 docs | README, AGENTS, `dataset` (11 vezes), `tres_versoes` (5), `estender` (3), demais | glossário + `dataset` | baixo |
| Strings de confirmação (`ENERGIZAR-TESTE`, `ENERGIZAR-COMANDOS`, `EXECUTAR-CLASSE-NN`, `EXECUTAR-CLASSES-<lista>`, `EXECUTAR-20-CLASSES`) | 4 docs (`ENERGIZAR-TESTE`); 3 (`EXECUTAR-20-CLASSES`) | AGENTS (2), ROTEIRO (4), `operacao` (3), `quirks`; `AGENTS.md` ainda lista `ENERGIZAR-5V` como histórico | `operacao` §4, gerada de `cli.py:344-351,691,706,750,762,823` | alto: confirmação digitada é limite inegociável; texto divergente induz o operador ao erro |
| Trava da fonte (~280 gravações de TRACe) | 5 docs | ROTEIRO (2), `arquitetura`, `estender` (2), `operacao`, `quirks` A3; código `mestre.py:3213` | `quirks` A3 + `operacao` §3 | médio; README ainda recomenda `run all` sem aviso (P-23) |
| `calibracao_extremos.json` e recalibração | 11 docs | `limites_e_calibracao` §4-5, `operacao` §9 (5), `ROTEIRO` (7), `metadata` (6), demais | uma página "Calibração de extremos" | médio: três descrições do mesmo procedimento (limites §5, operacao §9, ROTEIRO Bloco 7) |
| `git_sujo` e procedência | 7 docs | AGENTS (2), ROTEIRO (4), `dataset`, `estender`, `metadata` (4), `quirks` B8, `versionamento` (3) | `versionamento` §2 | alto: B8 está desatualizado (divergência 1) |
| Sincronismo por `*ESR?` (`write`) | 5 docs | AGENTS, `arquitetura`, `configuracao`, `quirks` (3), `scpi` (2) | `scpi` §1 | médio |
| Regra "nunca consultar logo após `TRACe:DATA`" | 10 docs | AGENTS, ROTEIRO (2), `arquitetura`, `classes`, `correlacao_disturbio`, `diagnostico` (3), `estender`, `quirks`, `scpi` (3), `tres_versoes` | `quirks` A2 | médio: regra de segurança repetida com palavras diferentes |
| Tabela das 20 classes | 4 | `classes` §1, `experimentos.txt`, README (lista), `estender` | `classes` (uma ficha por classe) | médio; as fichas do site substituem a tabela |
| Lista de scripts | 5 | `arquitetura` §7, README, `diagnostico` §3, `dataset` §5, `operacao` §8 | `scripts` do mapa do código (`06` §4.15) | médio: `arquitetura` §7 omite `verificar_sessao_bancada.py` e `diag_ciclos_trace.py` |
| Comandos da CLI | 4 | `AGENTS` (tabela), `operacao` §3, `cli.py` `HELP_TEXT` (`cli.py:59-193`), README | `HELP_TEXT`, replicado por script no build | alto: `operacao` copia à mão o `HELP_TEXT` |
| Campos de metadata | 2 | `dataset` §3 e `metadata` | `metadata` | baixo |
| Pendências e "NÃO VERIFICADO" | 15 ou mais lugares (contagem aproximada) | README "Pendente fora da main", `versionamento` §7, AGENTS "Como versionar", uma seção por `docs/*.md`, CHANGELOG | `04-pendencias.md` vira página "Pendências" com ids P-NN | alto: o estado de verificação vive em 15 lugares |
| Roteiro da bancada | 3 cópias | raiz, `sessao-13-10-2026/`, `specs/2026-10-13/` (mesmo blob) | raiz | baixo (idêntico hoje) |
| Relatório final de 13/10 | 2 cópias | `sessao-13-10-2026/` e `specs/2026-10-13/` (mesmo blob `851a918`) | `sessao-13-10-2026/` | baixo |

## 4. Fatos escondidos (só no código, em comentário ou em análise; ausentes ou só parcialmente presentes em `docs/`)

Cada item foi conferido no código em 2026-10-15; "ausente" significa que a busca textual nos 18 `docs/*.md`, `README.md`, `AGENTS.md` e `ROTEIRO_BANCADA.md` não encontrou o termo ou o fato (H-3, H-10, H-11 e H-17 são parcialmente documentados, como indicado).

| # | Fato | Onde está | Por que importa | Destino no site |
|---|---|---|---|---|
| H-1 | `measure_voltage` em `SOURce:MODE ACDC` (classe 19) devolve o RMS **total** (CA + CC), apesar do manual; evidência: uma leitura pré-degrau na sessão `run02` de 07/10 (5,491 V com offset de 5,58 V). Hoje só afeta o log de `set diagnostico on` | comentário em `ametek_orm.py:1964-1977` (`measure_voltage` em `:1963`) | quem ler `tensao_v` do log da 19 vê RMS total; interpretação sustentada por UMA leitura (NÃO VERIFICADO; `diag_acdc_amplitude.py` fecha) | página da classe 19 e `quirks` (a criar A26) |
| H-2 | `_BancadaOffline` (usada por `analisar_sessao`) força `osc=None`: o `gerar()` de 04/06/08/09/19 usa o ramo de sorteio mesmo quando a sessão rodou com `set capturas N`; só `razao_pico` fica impreciso. Também não aplica o limite de bancada da 08, então o esperado da 08 é o impulso de 5-10 pu (razão de pico ~0,27) | comentário em `analisar_sessao.py:163-176` | quem interpretar `razao_pico` da 08 como erro da bancada se engana | página `analisar_sessao` |
| H-3 | `_SEM_SINCRONISMO` tem só as formas longas em maiúsculas (`ametek_orm.py:178`), enquanto `_GRAVA_FLASH` aceita também `TRAC:DATA`, `TRAC:DEF`, `TRAC:DEL` (`:181-183`). Nenhum código usa a forma abreviada fora do simulador | `ametek_orm.py:178-183` | latente: um comando novo escrito em forma abreviada faria `write()` consultar a fonte logo após `TRACe:DATA` (quirk A2, risco de travar a fonte) | `scpi` §1, aviso para quem estende |
| H-4 | `safe_shutdown` engole qualquer exceção, inclusive o `InstrumentHardwareError("SHUTDOWN NÃO CONFIRMADO")` que ele mesmo levanta: só vai a `logger.exception` | `ametek_orm.py:1957-1961` | a única confirmação de saída desligada é o operador no painel | `operacao` §7 e invariantes |
| H-5 | O leitor abre `.npz` com `allow_pickle=True` em `formato_do_arquivo` (`:660`), na leitura de `tres_versoes/` (`:671`) e em `ler_pasta` (`:721`), necessário ao formato 1; só o spool interno (`:324`) usa `False`. `docs/dataset.md:54` recomenda `np.load` sem `allow_pickle` para o formato 2 | `sessao_io.py:324,660,671,721` | abrir `.npz` de terceiros pelo relatório executaria pickle; relevante ao publicar o dataset | `dataset` |
| H-6 | `corte_da_senoide_clipada` recusa THD > 25 %, então `forma_programada_nativa("05")` falharia no nível de 30 % (que na bancada vai por TRACe) | `sinais.py:600-601` | acoplamento entre o nível de 30 % da 05 e o caminho nativo | ficha da 05 |
| H-7 | O comentário de bloco de `ExperimentoBase.capturas_padrao` lista só 04, 06-09, 17, 19, 20 com padrão 3; as compostas 10-16 também têm 3 desde a v1.15 | `mestre.py:1555-1562` | documentação interna defasada; fonte de engano ao ler o código | `classes` (tabela gerada) |
| H-8 | `scripts/diag_saida_vs_medida.py` e `diag_fonte_vs_osciloscopio.py` energizam a fonte por PyVISA cru (`ASRL10::INSTR`, `USB0::...` fixos, confirmação `ENERGIZAR-<V>V` própria): **não** passam por `AmetekMX30`, `validate_bench_configuration` nem `max_peak_v` | `diag_saida_vs_medida.py:29,72`; `diag_fonte_vs_osciloscopio.py:25,36,101` | o limite inegociável "nada energiza sem validação" depende aí só da confirmação digitada | `diagnostico` §3 |
| H-9 | O tratador de Ctrl+C só é instalado em `Bancada.from_env`, depois de abrir os dois instrumentos (o NI-VISA instala o seu ao abrir); fora dele (script que usa o ORM direto) o Ctrl+C no Windows não interrompe a espera | `mestre.py:445-481,1084` | quem escrever script novo sobre o ORM sem `from_env` fica sem o tratador | `operacao` e mapa do código |
| H-10 | `_fatores_extremo()` relê `calibracao_extremos.json` a cada avaliação de captura; `set recalibracao on` vale no run seguinte sem reiniciar | `mestre.py:566-590,2011-2016` | resolve o NÃO VERIFICADO de `operacao.md:152` | `operacao` §9 |
| H-11 | O limite de 3 capturas por bloco do relatório HTML só vale para o dataset simulado (formato 2) | `sessao_io.py:771-776`; `relatorio_html.py:299-310` | diverge de `operacao.md:122` (divergência 7); o HTML da bancada pode passar de 20 MB | `operacao` §9 |
| H-12 | `run 01 02` (espaço, sem vírgula) roda só a 01, sem aviso; a lista não respeita `BATERIA_EXCLUIR` | `cli.py:723-726,737-738` | surpresa do operador | `operacao` §3 (P-14) |
| H-13 | `recortar_margem --empilhar` é aceito e ignorado (o formato 2 já é um `.npz` por classe); só o docstring diz | `recortar_margem.py:22,156,280` | opção sem efeito; `docs/dataset.md:113` não a menciona | `dataset` |
| H-14 | `ExperimentoNativo._duracao_sorteada_s` é posto por `_capturar_real` e lido por `largura_do_pulso_s` em `configurar()`; chamar `configurar()` fora de `_capturar_real` usa a duração legada | `mestre.py:2880-2883,2959` | acoplamento de ordem não escrito | `estender` §1.5 |
| H-15 | Estado mutável de módulo (`PERFIL`, `SORTEIO_POSICAO`, `CAPTURAS_OVERRIDE`...) escrito pela CLI e lido por `_build_config` na próxima `Bancada.from_env`; `from mestre import X` copia o valor | `mestre.py:942-963`; `cli.py:271-281` | explica por que `set` "vale no próximo run" e por que `autorizar_saida` espelha `OUTPUT_ARMED` em dois módulos | mapa do código, `arquitetura` |
| H-16 | `matplotlib` é usado só em `relatorio_html.py` e está nas dependências fixas do bancada (`requirements.txt`) | `requirements.txt:4` | a bancada instala uma biblioteca de gráficos por causa de um recurso opcional | `configuracao` |
| H-17 | Condição `220 V/60 Hz` e outras sem tabela de extremos rodam com previsão conservadora (1,475) e várias classes puladas; a 230 V/50 Hz a 03 fica de fora (416,4 V > 415,8 V) | `docs/operacao.md:85-91` (já documentado) e `calibracao_extremos.json` | listado para completude: já documentado, mas sem tabela por classe | `operacao` §6 (P-21) |

## 5. Auditoria das citações `arquivo:linha`

**Método.** Cada citação de `classes.md`, `scpi.md` e `limites_e_calibracao.md` foi extraída por expressão regular (aceita `` `:NNN``, intervalos `NNN-MMM`, vírgulas e espaço antes de `:NNN`), associada ao símbolo que a frase descreve e comparada com a linha de definição atual obtida por `ast` (Python) ou com a linha do comando (`Grep`). Nas citações sem símbolo (constantes, linhas de comando), usou-se a linha da expressão. **Resultado: 85 citações (12 em `classes.md`, 7 em `limites_e_calibracao.md`, 66 em `scpi.md`): 22 exatas, 63 deslocadas.** As 22 exatas são 19 do osciloscópio (`oscilloscope_orm.py` não mudou desde `d37e403`), `sinais.py:24` (acima da primeira alteração do arquivo), `05.py:69` e `ametek_orm.py:1353` (`ler_trace`, função acrescentada depois de `d37e403` e já citada com a linha certa). As 63 deslocadas estão em `mestre.py`, `ametek_orm.py` e nos experimentos `04`, `08` e `19`; conferido com `git show d37e403:arquivo` que as 63 eram exatas no carimbo dos documentos, de modo que o desvio é só o que o código ganhou depois (51 commits, 64 arquivos, +7.893/-1.521 linhas, `git diff --stat d37e403 fa82f49`). Deslocamento típico: `ametek_orm.py` +37 (baseline), +107 (arm/program_capture), `mestre.py` +60, +167, +195.

Citações em outros documentos de `docs/` (fora `classes`, `scpi` e `limites_e_calibracao`) somam 65 linhas com `mestre.py:NNN`; **não foram auditadas uma a uma** (NÃO VERIFICADO além dos títulos de `arquitetura.md`, divergência 6); usam o mesmo carimbo `d37e403`.

Legenda de veredito: EXATA = a linha citada é a de definição hoje; DESLOCADA (+N) = o símbolo existe, N linhas depois.

| # | Documento:linha | Citação | Símbolo | Posição atual (`fa82f49`) | Veredito |
|---|---|---|---|---|---|
| 1 | `classes.md:5` | `mestre.py:1495` | `ExperimentoBase.gerar` | 1662-1667 | DESLOCADA (+167) |
| 2 | `classes.md:37` | `mestre.py:810` | `sortear_posicao` | 870-915 | DESLOCADA (+60) |
| 3 | `classes.md:47` | `mestre.py:730` | `Config.capturas` | 790-805 | DESLOCADA (+60) |
| 4 | `classes.md:47` | `mestre.py:1517` | `dimensionar_capturas` | 1684-1701 | DESLOCADA (+167) |
| 5 | `classes.md:49` | `sinais.py:24` | `valor_para_captura` | 24-49 | EXATA |
| 6 | `classes.md:51` | `mestre.py:1536-1540` | `seed_da_captura` | 1703-1707 | DESLOCADA |
| 7 | `classes.md:51` | `04.py:36` | `seed = base_seed + 4_000_000 + capture_index` | 37 | DESLOCADA (+1) |
| 8 | `classes.md:51` | `19.py:32` | `seed = base_seed + 19_000_000 + capture_index` | 33 | DESLOCADA (+1) |
| 9 | `classes.md:60` | `08.py:34,81-98` | `constante e _indices_impulso` | 35 e 82-99 | DESLOCADA (+1) |
| 10 | `classes.md:60` | `08.py:180` | `conferir_posicao_do_evento` | 181-216 | DESLOCADA (+1) |
| 11 | `classes.md:64` | `ametek_orm.py:156` | `MAX_CSINE_THD_PCT` | 163 | DESLOCADA (+7) |
| 12 | `classes.md:64` | `05.py:69` | `usar_trace` | 69-70 | EXATA |
| 13 | `limites_e_calibracao.md:12` | `mestre.py:1868` | `avaliar_captura_na_bancada` | 2063-2121 | DESLOCADA (+195) |
| 14 | `limites_e_calibracao.md:18` | `mestre.py:1767` | `_conferir_extremos_fisicos` | 1962-1979 | DESLOCADA (+195) |
| 15 | `limites_e_calibracao.md:22` | `mestre.py:2846` | `_limitar_disturbio_para_bancada` | 3052-3110 | DESLOCADA (+206) |
| 16 | `limites_e_calibracao.md:22` | `mestre.py:597` | `extremo_previsto_com_disturbio_v` | 649-670 | DESLOCADA (+52) |
| 17 | `limites_e_calibracao.md:28` | `mestre.py:514` | `carregar_fatores_extremo` | 566-623 | DESLOCADA (+52) |
| 18 | `limites_e_calibracao.md:34` | `mestre.py:1872` | `fator_extremo_efetivo_para_validacao` | 1896-1920 | DESLOCADA (+24) |
| 19 | `limites_e_calibracao.md:54` | `mestre.py:1329-1366` | `verificar_cadeia_de_medicao` | 1496-1533 | DESLOCADA (+167) |
| 20 | `scpi.md:7` | `ametek_orm.py:292-300` | `_configure_visa_resource` | 313-321 | DESLOCADA (+21) |
| 21 | `scpi.md:8` | `ametek_orm.py:367-389` | `_raw_write` | 394-421 | DESLOCADA (+27) |
| 22 | `scpi.md:9` | `ametek_orm.py:391` | `write` | 423-449 | DESLOCADA (+32) |
| 23 | `scpi.md:9` | `ametek_orm.py:171` | `_SEM_SINCRONISMO` | 178 | DESLOCADA (+7) |
| 24 | `scpi.md:10` | `ametek_orm.py:448` | `query` | 480-503 | DESLOCADA (+32) |
| 25 | `scpi.md:18` | `ametek_orm.py:329` | `connect (OUTPut:STATe OFF)` | 334-364 (comando na L350) | DESLOCADA (+21) |
| 26 | `scpi.md:18` | `ametek_orm.py:1836` | `safe_shutdown (OUTPut:STATe OFF)` | 1937-1961 | DESLOCADA (+101) |
| 27 | `scpi.md:19` | `ametek_orm.py:330` | `connect (*IDN?)` | 334-364 (consulta na L351) | DESLOCADA (+21) |
| 28 | `scpi.md:20` | `ametek_orm.py:599` | `check_errors` | 633-645 | DESLOCADA (+34) |
| 29 | `scpi.md:21` | `ametek_orm.py:1219` | `*CLS da baseline` | 1256 | DESLOCADA (+37) |
| 30 | `scpi.md:21` | `ametek_orm.py:1442,1509` | `program_capture (*CLS)` | 1549 e 1616 | DESLOCADA (+107) |
| 31 | `scpi.md:22` | `ametek_orm.py:419` | `_sincronizar_apos` | 451-478 | DESLOCADA (+32) |
| 32 | `scpi.md:23` | `ametek_orm.py:938,948` | `configure_harmonics_csine (*WAI)` | 975 e 985 | DESLOCADA (+37) |
| 33 | `scpi.md:23` | `ametek_orm.py:972` | `select_sine_shape (*WAI)` | 1009 | DESLOCADA (+37) |
| 34 | `scpi.md:23` | `ametek_orm.py:1094` | `enable_dc_offset (*WAI)` | 1131 | DESLOCADA (+37) |
| 35 | `scpi.md:23` | `ametek_orm.py:1629` | `arm (*WAI)` | 1736 | DESLOCADA (+107) |
| 36 | `scpi.md:23` | `ametek_orm.py:1777` | `arm_transient (*WAI)` | 1884 | DESLOCADA (+107) |
| 37 | `scpi.md:24` | `ametek_orm.py:633` | `_log_diagnostico (STATus:OPERation:CONDition?)` | 670 | DESLOCADA (+37) |
| 38 | `scpi.md:25` | `ametek_orm.py:661` | `output_enabled (OUTPut:STATe?)` | 695-698 | DESLOCADA (+34) |
| 39 | `scpi.md:25` | `ametek_orm.py:1841` | `safe_shutdown (OUTPut:STATe?)` | 1948 | DESLOCADA (+107) |
| 40 | `scpi.md:26` | `ametek_orm.py:760` | `aguardar_idle` | 774-808 | DESLOCADA (+14) |
| 41 | `scpi.md:26` | `ametek_orm.py:1635` | `arm (TRIGger:STATe?)` | 1742 | DESLOCADA (+107) |
| 42 | `scpi.md:26` | `ametek_orm.py:1820` | `wait_transient_complete` | 1924-1935 | DESLOCADA (+104) |
| 43 | `scpi.md:28` | `ametek_orm.py:1175-1264` | `configure_safe_baseline` | 1212-1301 | DESLOCADA (+37) |
| 44 | `scpi.md:47` | `ametek_orm.py:669` | `energize_baseline` | 706-726 | DESLOCADA (+37) |
| 45 | `scpi.md:52` | `ametek_orm.py:691-705` | `voltage (setter)` | 729-742 | DESLOCADA (+38) |
| 46 | `scpi.md:55` | `ametek_orm.py:1856-1866` | `measure_voltage..measure_power_factor` | 1963-1986 | DESLOCADA (+107) |
| 47 | `scpi.md:58` | `ametek_orm.py:793-805` | `_neutralizar_transientes_residuais` | 830-842 | DESLOCADA (+37) |
| 48 | `scpi.md:62` | `ametek_orm.py:839` | `trigger_step` | 876-906 | DESLOCADA (+37) |
| 49 | `scpi.md:63` | `ametek_orm.py:871` | `trigger_pulse` | 908-937 | DESLOCADA (+37) |
| 50 | `scpi.md:64` | `ametek_orm.py:807` | `definir_fase_de_disparo` | 844-855 | DESLOCADA (+37) |
| 51 | `scpi.md:65` | `ametek_orm.py:902` | `configure_harmonics_csine` | 939-987 | DESLOCADA (+37) |
| 52 | `scpi.md:66` | `ametek_orm.py:952` | `select_sine_shape` | 989-1011 | DESLOCADA (+37) |
| 53 | `scpi.md:67` | `ametek_orm.py:1071` | `enable_dc_offset` | 1108-1138 | DESLOCADA (+37) |
| 54 | `scpi.md:68` | `ametek_orm.py:976` | `disable_dc_offset` | 1013-1033 | DESLOCADA (+37) |
| 55 | `scpi.md:69` | `ametek_orm.py:1029` | `frequency_drift_list` | 1066-1106 | DESLOCADA (+37) |
| 56 | `scpi.md:70` | `ametek_orm.py:1013` | `restaurar_frequencia_base` | 1050-1064 | DESLOCADA (+37) |
| 57 | `scpi.md:71` | `ametek_orm.py:998` | `restaurar_forma_e_modo_padrao` | 1035-1048 | DESLOCADA (+37) |
| 58 | `scpi.md:72` | `ametek_orm.py:1600` | `arm` | 1707-1752 | DESLOCADA (+107) |
| 59 | `scpi.md:72` | `ametek_orm.py:1675` | `_conferir_transiente_programado` | 1782-1821 | DESLOCADA (+107) |
| 60 | `scpi.md:73` | `ametek_orm.py:1803` | `trigger` | 1910-1922 | DESLOCADA (+107) |
| 61 | `scpi.md:74` | `ametek_orm.py:1817` | `wait_transient_complete` | 1924-1935 | DESLOCADA (+107) |
| 62 | `scpi.md:79` | `ametek_orm.py:1404` | `program_capture` | 1511-1705 | DESLOCADA (+107) |
| 63 | `scpi.md:88` | `ametek_orm.py:1322` | `montar_programacao` | 1416-1509 | DESLOCADA (+94) |
| 64 | `scpi.md:90` | `ametek_orm.py:1716` | `arm_transient` | 1823-1908 | DESLOCADA (+107) |
| 65 | `scpi.md:92` | `ametek_orm.py:1266` | `clear_all_traces` | 1303-1317 | DESLOCADA (+37) |
| 66 | `scpi.md:94` | `ametek_orm.py:1353` | `ler_trace` | 1353-1405 | EXATA |
| 67 | `scpi.md:111` | `oscilloscope_orm.py:78` | `verify_identity` | 78-84 | EXATA |
| 68 | `scpi.md:112` | `oscilloscope_orm.py:86` | `check_errors` | 86-98 | EXATA |
| 69 | `scpi.md:113` | `oscilloscope_orm.py:105` | `initialize_safe` | 105-112 | EXATA |
| 70 | `scpi.md:114` | `oscilloscope_orm.py:114` | `configure_channel` | 114-137 | EXATA |
| 71 | `scpi.md:115` | `oscilloscope_orm.py:139` | `disable_channel` | 139-143 | EXATA |
| 72 | `scpi.md:116` | `oscilloscope_orm.py:145` | `set_vertical_scale` | 145-175 | EXATA |
| 73 | `scpi.md:117` | `oscilloscope_orm.py:209` | `configure_acquisition` | 209-293 | EXATA |
| 74 | `scpi.md:118` | `oscilloscope_orm.py:295` | `_programar_referencia_horizontal` | 295-337 | EXATA |
| 75 | `scpi.md:119` | `oscilloscope_orm.py:339` | `definir_pre_trigger` | 339-354 | EXATA |
| 76 | `scpi.md:120` | `oscilloscope_orm.py:356` | `setup_external_trigger` | 356-384 | EXATA |
| 77 | `scpi.md:121` | `oscilloscope_orm.py:386` | `arm` | 386-389 | EXATA |
| 78 | `scpi.md:122` | `oscilloscope_orm.py:416` | `is_armed / wait_for_armed` | 416 / 420 | EXATA (is_armed); wait_for_armed na L420 |
| 79 | `scpi.md:123` | `oscilloscope_orm.py:428` | `wait_for_trigger_complete` | 428-441 | EXATA |
| 80 | `scpi.md:124` | `oscilloscope_orm.py:391` | `force_trigger` | 391-393 | EXATA |
| 81 | `scpi.md:125` | `oscilloscope_orm.py:395` | `medir_vrms_forcado` | 395-414 | EXATA |
| 82 | `scpi.md:126` | `oscilloscope_orm.py:181` | `medir_extremos` | 181-207 | EXATA |
| 83 | `scpi.md:127` | `oscilloscope_orm.py:447` | `get_waveform` | 447-537 | EXATA |
| 84 | `scpi.md:128` | `oscilloscope_orm.py:539-550` | `safe_stop/close` | 539-550 | EXATA |
| 85 | `scpi.md:130` | `oscilloscope_orm.py:529` | `ultimo_indice_trigger` | 529 | EXATA |

**Consequência para o site.** Número de linha escrito à mão envelhece em dias (63/85 em duas semanas de trabalho). A regra do site: citar **símbolo** (`:pyobject:` do `literalinclude`, ou âncora gerada por script que resolve o símbolo em `fa82f49`) e carimbar o commit uma vez, no rodapé da página, nunca no meio do texto.

## 6. Divergências entre a documentação e o código

Numeração usada em `04-pendencias.md`.

| # | Documento | Afirma | Código/medida de hoje | Ação sugerida |
|---|---|---|---|---|
| 1 | `docs/quirks.md:61` (B8) | `git_sujo` não conta arquivo novo e é calculado uma vez por processo (`mestre.py:129`) | `mestre.py:121-171`: conta arquivo novo em `logica/`, `experimentos_*/`, `scripts/`; `preparar_pasta_da_sessao` recalcula a cada pasta (`:220`); `versionamento.md:13-14` e `AGENTS.md:268` estão certos | reescrever B8 |
| 2 | `docs/operacao.md:152` | "NÃO VERIFICADO: se a CLI relê o JSON a cada run" | relê: `mestre.py:566-590`, `:2011-2016` | trocar por VERIFICADO OFFLINE |
| 3 | `docs/testes.md:3`, `docs/estender.md:79` | 370 testes, 57 classes | 497 testes OK, 66 classes (`unittest` no Windows, 2026-10-15) | corrigir contagem; gerar no build |
| 4 | 8 documentos (`arquitetura`, `classes`, `diagnostico`, `estender`, `operacao`, `quirks`, `scpi`, `testes`) | carimbo `d37e403` | código em `fa82f49` (51 commits depois) | carimbo único no rodapé |
| 5 | `docs/tres_versoes.md:59` contra `AGENTS.md:125` e `v1.15:9` | 99 capturas contra 63 de 07/10 | 36 + 36 + 27 = 99 arquivos em `resultados/`; 63 pode ser só as duas sessões de 50 Hz (hipótese NÃO VERIFICADA) | P-30 |
| 6 | `docs/arquitetura.md` (títulos `:97`, `:110`, `:122`, `:125`, `:59`, `:99`, `:132`) | `mestre.py:969-1077`, `2385-2660`, `2733-2777`, `2920-2978`; `ametek_orm.py:147`; `validate_bench_configuration :366` | hoje `1031-1139`, `2578-2863`, `2936-2983`, `3126-3188`; `154`; `418` | símbolos em vez de linhas |
| 7 | `docs/operacao.md:122` | o HTML mostra só as 3 primeiras capturas por classe e perfil | só no dataset simulado e no formato 1 empilhado; sessão de bancada em formato 2 traz todas (`sessao_io.py:771-776`) | P-15 (corrigir texto ou limitar) |
| 8 | `docs/arquitetura.md:143-155` (§7) | `diag_*.py` energizam, exceto `diag_nativo_output_off.py`; omite `verificar_sessao_bancada.py` | `diag_ciclos_trace.py` e `diag_osciloscopio_canais.py` também não energizam; `verificar_sessao_bancada.py` existe (`diagnostico.md:60`) | tabela de scripts gerada de `06` §4.15 |
| 9 | `README.md:26` e `docs/operacao.md:63` (sequência recomendada); `AGENTS.md:37` (`run all` como bateria completa) | a sequência termina em `run all` | `operacao.md:79` e `ROTEIRO_BANCADA.md` §4-§5 mandam listas (< 250 gravações por conexão) por causa da trava ~280 | P-23 |
| 10 | `mestre.py:1555-1562` (comentário de bloco) | padrão 3 só em 04, 06-09, 17, 19, 20 | as compostas 10-16 também têm 3 | H-7 |
| 11 | `docs/dataset.md:54` | carregar sem `allow_pickle` | o leitor do projeto usa `allow_pickle=True` (`sessao_io.py:660,671,721`) | H-5 |
| 12 | `docs/configuracao.md` (seção "Regras de `validate_bench_configuration()`") | `validate_bench_configuration` em `mestre.py:366-387` | `:418-439` | símbolo |
| 13 | `AGENTS.md` (topo) e `README.md:23` | caminho do projeto `C:\Users\denis\TCC\code` | só vale no PC da bancada; neste PC o repositório está em outro caminho | informar no site que o caminho é do PC da bancada |
| 14 | `docs/correlacao_disturbio.md:3,7,11,87` | "Data: 2026-10-12. Árvore NÃO commitada"; `sinais.py:307`, `:520`, `analisar_sessao.py:187` | árvore commitada (`fa82f49`); hoje `sinais.py:485` e `:535`, `analisar_sessao.py:190` | reescrever o cabeçalho e citar símbolos |

Não são divergências: `operacao.md` §7 ("tentar 3 vezes") e `AGENTS.md` ("sem retry diante de falha de infraestrutura") **conferem**: `MAX_TENTATIVAS_POR_CLASSE = 3` vale para `Exception` genérica (`mestre.py:1146,1221-1228`); `CommunicationError`/`FalhaFatalDeInstrumento` propagam sem retry (`:1206-1210`) e `ERROS_DETERMINISTICOS` não retentam (`:1211-1220`).

## 7. O que reaproveitar, reescrever e descartar para o site

| Fonte | Decisão | Motivo |
|---|---|---|
| `docs/operacao.md`, `quirks.md`, `scpi.md`, `limites_e_calibracao.md`, `metadata.md`, `dataset.md`, `perfis.md`, `glossario.md`, `versionamento.md` | reaproveitar texto, trocar linhas por símbolos, acrescentar selos | conteúdo correto na maior parte, só desatualizado em citações e contagens |
| `docs/arquitetura.md`, `classes.md`, `diagnostico.md`, `estender.md` | reescrever em volta do mapa do código (`06`) e das fichas (`03`) | citações antigas, scripts omitidos, duas tabelas das classes |
| `AGENTS.md` | manter na raiz como está (instrução ao agente); o site cita as regras inegociáveis em página própria e linka para o arquivo | texto escrito para agente de IA, com governança ("dono") |
| `README.md` | manter; o site reutiliza o início rápido | é o cartão de visita do repositório |
| `CHANGELOG/vX.Y.md` fechados | incluir sem alteração em "Histórico" | registro histórico |
| `ROTEIRO_BANCADA.md` | publicar como "Roteiro da próxima bancada" com selo PENDENTE | execução não aconteceu |
| `experimentos.txt` | publicar como "Especificação original" (anexo) | referência histórica |
| PDFs e `manuais_txt/` | **não publicar** no site; linkar ao fabricante | material de terceiros (achado A-5) |
| análises do branch de arquivo | citar por caminho e commit, sem copiar | FORA DA MAIN |
