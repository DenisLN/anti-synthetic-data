# Refatoração de apresentabilidade da documentação (2026-10-12)

Base: commit `d37e403` (v1.15 em andamento, sem tag; o dono confirmou em 2026-10-12 que a versão continua v1.15). Somente `.md` foram criados/alterados; nenhum `.py` mudou e o hardware não foi tocado. Temporários ficaram no scratchpad da sessão (`...\scratchpad\apresentabilidade\`). Linhas valem para `d37e403`.

## 1. Mapa dos documentos

| Arquivo | Estado | Origem do conteúdo |
|---|---|---|
| `README.md` | reescrito, curto | seções 1, 6 e 7 do README antigo + mapa; o resto foi para `docs/` |
| `AGENTS.md` | conteúdo de segurança preservado integralmente; acrescentadas 2 notas verificadas (logs, `lowvoltage`) e as seções "Documentação (mapa)", "Como escrever sobre mudanças no código", "Como versionar" | — |
| `docs/arquitetura.md` | novo | README §2, §3 + código |
| `docs/operacao.md` | novo | README §5.1-5.6 |
| `docs/configuracao.md` | novo | README §5.7 + varredura de `os.getenv`/`env_*` |
| `docs/limites_e_calibracao.md` | novo | README §5.6 + `mestre.py` |
| `docs/classes.md` | novo | README §4 + `experimentos_*/NN.py` |
| `docs/scpi.md` | novo | `ametek_orm.py`, `oscilloscope_orm.py`, manuais |
| `docs/quirks.md` | novo | CHANGELOG v1.5 a v1.14, `docs/analise-*` |
| `docs/decisoes.md` | novo | CHANGELOG |
| `docs/dataset.md` | novo | README §5.8, §6 + código |
| `docs/estender.md` | novo | guia de nova classe + erros documentados |
| `docs/diagnostico.md` | novo | `set diagnostico on` e scripts `diag_*` |
| `docs/testes.md` | novo | `tests/` |
| `docs/versionamento.md` | novo | regras de tag/CHANGELOG/Zenodo/sessão limpa; mapa v1.0-v1.15 |
| `docs/glossario.md` | novo | — |
| `docs/metadata.md` | uma correção: rótulo "v1.16" → "v1.15 (em andamento)" (linha 58); formato não alterado | — |
| `CHANGELOG/v1.15.md` | acrescentada uma seção final listando onde estão documentados os 4 itens sem registro | — |
| `docs/perfis.md`, `docs/tres_versoes.md`, `docs/correlacao_disturbio.md` | conferidos e mantidos | — |

## 2. Divergências CHANGELOG × README × código (o código manda)

| # | Onde estava errado | O que o código faz |
|---|---|---|
| 1 | README §5.8: "qualquer `run` seguinte na MESMA sessão de CLI usa a mesma pasta" | uma pasta nova por `run` (`_run02`, …): `cli.py:199-218` |
| 2 | README §5.5 e `AGENTS.md`: entregar `logs\startup-bench-*.log` | nenhum código gera esse arquivo (grep em `*.py`/`*.ps1` vazio); logs reais: `sessao.log` e `scpi_transcricao.log` da sessão (`mestre.py:55-83`); `logs\preflight_new-*.log` só com `preflight_new.py` direto (`preflight_new.py:61-75`, `:692`), e a CLI chama `run_native_commands()` sem isso (`cli.py:536`) |
| 3 | README, `AGENTS.md`, HELP: `lowvoltage`/`native` a "5 Vrms" | usam `BASE_VOLTAGE_RMS` digitada no início (`preflight.py:65-90`, `preflight_new.py:185-189`); rótulo `ENERGIZAR-5V` histórico (`cli.py:75-79,516`). **Achado de segurança, ver §4** |
| 4 | README §5.3: tabela sem `set recalibracao` e `set html` | existem (`cli.py:129-147,477-502`) |
| 5 | README §5.3.1: classes 10-16 com padrão 1 e "~300 gravações" | padrão 3 em 10-16 (`10.py:19` … `16.py:18`); 468 gravações a 60 Hz e 390 a 50 Hz (rodando `capturas_efetivas_da_classe`); CHANGELOG v1.15 já dizia 468 |
| 6 | README §5.6: reduções a 220 V "10 (88 %), 11 (78 %), 14 (48 %), 16 (37 %), 17 (98 %)" (v1.13) | superado pelas v1.14/v1.15; 220 V/60 Hz é condição sem tabela (conservadora); números atuais em `docs/operacao.md` §6, gerados por `relatorio_limites_bancada.py` |
| 7 | README §5.7: tensão/frequência "perguntadas nas etapas Full/LowVoltage/NativeCommands/Run"; `ARM_OUTPUT` "setado pelo script" | perguntadas uma vez em `start_bench_windows.ps1:36-59`; `ARM_OUTPUT` é posto pela CLI só durante o comando (`cli.py:186-197`); `bench_config.ps1:3` põe `NO` |
| 8 | README §5.7: tabela sem 12 variáveis | `AMETEK_SINCRONISMO`, `AMETEK_TIMEOUT_S`, `AMETEK_QUERY_EOT`, `KEYSIGHT_*`, `EXT_TRIGGER_*`, `BATERIA_EXCLUIR`, `MARGEM_*`, `MARGEM_FATOR_EXTREMO`, `VALIDACAO_*`, `DIAGNOSTICO_ABRIR_TERMINAL`: todas em `docs/configuracao.md` |
| 9 | README §1: simulado "padrão 2000" | `mestre.py:297` 2000, mas `run_simulation_windows.ps1:3` passa **1** por padrão |
| 10 | README §4: classe 05 usa `FUNCtion:SHAPe CSINe` | `SOURce:FUNCtion:SHAPe CSINusoid` (`ametek_orm.py:928`); `CSINe` é rejeitado (`-256`) |
| 11 | README §5.5: sem menção a retentativas | até 3 tentativas por classe para erro não determinístico (`mestre.py:1084,1127-1166`) |
| 12 | README §4.1: pico previsto "372 V" a 127 V | 374,2 V (amplitude 1,344 pu a 50 Hz; 1,618 pu a 60 Hz): `08.py:116-168` executado |
| 13 | README §1 e §8: CHANGELOG "v1.0 a v1.6" | v1.0 a v1.15 |
| 14 | README §2: árvore sem `perfis.py`, `diag_digitizer_*`, `gerar_*`, `diag_acdc_amplitude.py`, `tests/fixtures` | todos existem |
| 15 | README §2: só `tests/` insere `logica/` no `sys.path` | também `scripts/*.py` e `analisar_sessao.py:29-31` |
| 16 | `setup_windows.ps1:18` aceita Python 3.9-3.12 | `requirements.txt` fixa numpy 2.4.6, que exige Python ≥ 3.11 (comentário do próprio arquivo) |
| 17 | `.env.example`: `SNR_LEVELS_DB=30` | padrão do código `20,30,40` (`mestre.py:296`) — não é `.md`, não alterado |
| 18 | CHANGELOG v1.15 (linhas 46 e 74) diz que a autorização das compostas e da 08 está em `AGENTS.md` | `AGENTS.md` só tem as autorizações de 2026-10-07 e duas de 2026-10-12 (perfis; sorteio). Nada sobre compostas, 08, 05/07/17/18. **Pendente do dono**: registrar ou confirmar (não inventei) |
| 19 | CHANGELOG v1.15 sem seção para metadata rastreável, três versões, correlação do distúrbio, ruído na janela | seção final acrescentada apontando os documentos |
| 20 | CHANGELOG v1.15 cita `scripts/preflight_new.py` | o arquivo é `logica/preflight_new.py` (histórico; não reescrito) |
| 21 | `docs/metadata.md:58`, `sinais.py:500`, `scripts/gerar_tres_versoes.py:4`, `tests/test_offline.py:5772` rotulam as três versões como "v1.16" | decisão do dono: v1.15. Corrigido no `.md`; os `.py` ficam (achado) |
| 22 | CHANGELOG v1.14: "cada classe usa o maior entre as condições" | substituída pela regra por frequência da v1.15 (`mestre.py:546-557`) — histórico, não reescrito |
| 23 | `AGENTS.md` mandava ver "seção 5.3 do README" | substituído por `docs/operacao.md` |

Não encontrei erro nos números de `docs/perfis.md` (conferido contra `perfis.py:37-133`).

## 3. Verificações pedidas

1. **Suíte offline** (`.\env\Scripts\python.exe -m unittest tests.test_offline`, `TEMP`/`TMP` no scratchpad): antes da edição `Ran 370 tests ... OK`; depois da edição `Ran 370 tests ... OK`. Nenhum `.py` mudou.
2. **`git status --short`**: `M AGENTS.md`, `M CHANGELOG/v1.15.md`, `M README.md`, `M docs/metadata.md`, e `??` apenas para `.md` novos em `docs/` (e `.serena/`, que já existia untracked antes do trabalho). Nenhum `.py`.
3. **Links internos entre `.md`** (script no scratchpad `verifica_md.py` sobre README, AGENTS, `CHANGELOG/v1.15.md` e `docs/*.md`): todos os links `](...)` resolvem; todos os caminhos entre crases existem, exceto placeholders intencionais (`CHANGELOG/vX.Y.md`, `experimentos_*/NN.py`) e caminhos históricos citados no `CHANGELOG/v1.15.md` já existente (`logica/visualizador.py` e afins, removidos de propósito). As 137 referências `arquivo.py:linha` verificadas existem (linha dentro do arquivo); amostras conferidas à mão (ex.: `ametek_orm.py:171,329,928,1503`, `mestre.py:1084,2523`, `08.py:34,180`).
4. **Comandos de CLI e variáveis de ambiente documentados existem no código** (`verifica_cli_env.py`): 42 variáveis de `docs/configuracao.md`, todas encontradas em `logica/`, `scripts/` ou `experimentos_*` (`SEM correspondencia: []`); comandos `status`, `list`, `comm`, `trigger`, `lowvoltage`, `native`, `run`, `run all`, `help`, `?`, `quit`, `exit`, `set diagnostico|capturas|seed|perfil|sorteio|recalibracao|html|margin` presentes em `cli.py` (a busca textual não achou `recalibracao` por escrita com acento alternativo; o código está em `cli.py:477`); confirmações `ENERGIZAR-5V`, `ENERGIZAR-COMANDOS`, `EXECUTAR-CLASSE-`, `EXECUTAR-20-CLASSES`, `ENERGIZAR-ACDC`, `ENERGIZAR-127V` presentes.

## 4. Achados de código (não corrigidos)

| # | Achado | Como diagnosticar |
|---|---|---|
| F1 | **`lowvoltage` e `native` usam a tensão base digitada, não 5 V**, apesar de `ENERGIZAR-5V` e do texto "5 Vrms" (`cli.py:75-79,516`; `preflight.py:65-90`). Com `START_BENCH` em 127/220 V, o "teste de 5 V" programa essa tensão. Risco de segurança por rótulo enganoso (a confirmação digitada continua exigida) | sem hardware: `$env:BASE_VOLTAGE_RMS="127"; python -c "import sys; sys.path.insert(0,'logica'); import preflight; print(preflight.BASE_VOLTAGE_RMS)"`; com hardware: `set diagnostico on` e ler `SOURce:VOLTage`/`LIST:VOLTage` na `scpi_transcricao.log` do primeiro `lowvoltage` (aprovação do dono antes). Decisão pendente: corrigir o código (forçar 5 V) ou o texto |
| F2 | `git_sujo` ignora arquivo novo não rastreado e é cacheado por processo (`mestre.py:129-153`); `set recalibracao on` suja a árvore depois do primeiro run sem a CLI notar | `git status --porcelain` (com e sem `--untracked-files=no`) antes da sessão; reiniciar a CLI depois de commitar |
| F3 | `nivel_indice` é sempre 0 no simulado (`mestre.py:2523`); o nível se recupera do `id_captura` | ler `id_captura` |
| F4 | `native` pela CLI não grava log em arquivo; Ctrl+C não coberto no caminho `preflight_new` | guardar a saída do terminal ou rodar `preflight_new.py --native-commands` |
| F5 | Com os padrões o `run all` planeja 468 gravações de TRACe (390 a 50 Hz), acima das ~280 da trava de 16/09 (`mestre.py:3003`); só há aviso | `status` mostra a estimativa; dividir em `run <NN>` |
| F6 | `setup_windows.ps1` aceita Python 3.9/3.10 mas o numpy fixado não instala nelas (inferido do comentário de `requirements.txt`) | `py -3.10 -m venv x; x\Scripts\pip install -r requirements.txt` |
| F7 | Comentário de `ametek_orm.py:1061-1067` diz que `LIST:*` sem `SOURce:` e `:COUNt` são rejeitados, mas `frequency_drift_list` envia `LIST:COUNt 1`, `LIST:FREQuency`, `LIST:VOLTage`, `LIST:DWELl` sem prefixo (a classe 18 passou 20/20 em 2026-09-30, então o prefixo só é exigido por `LIST:REPeat`) | `preflight_new.py --list-diagnostics` (não energiza) |
| F8 | Rótulos "v1.16" em `.py` (item 21 da §2) | `grep -rn "1\.16" --include=*.py` |

## 5. NÃO VERIFICADO

- Tudo o que depende da bancada: F1 (leitura de código, não testado no hardware), A3, A19, A22, K4, K9 de `docs/quirks.md`, as causas listadas como NÃO VERIFICADO nos relatórios citados.
- Páginas dos manuais: a coluna "Manual" de `docs/scpi.md` usa o número da página do **PDF** encontrado por busca de texto nos `manuais_txt/` (e as citações `p. NNN` já presentes no código, que coincidem com esse número); não reli cada página.
- Procedimento Zenodo/DOI e o rito de tag em `docs/versionamento.md` §3 são o procedimento geral da integração GitHub-Zenodo; **não** foram executados, e o projeto não tem licença nem `CITATION.cff`.
- Tabela de limites por tensão (`docs/operacao.md` §6): gerada em 2026-10-12 com seed padrão, perfil `literatura`, sorteio ligado; muda com seed, perfil e calibração.
- Firmware 07.30 do Keysight e Rev. 5.53 da AMETEK: vêm de comentários do código.
- Python 3.9/3.10 não instalam o numpy fixado (F6): inferência.
- Autorizações de `AGENTS.md` para compostas, 08 e 05/07/17/18 (item 18 da §2): ausentes; nada foi inventado.

## 6. Pronto e NÃO FEITO (fechamento)

**Pronto:** README curto; `AGENTS.md` (segurança preservada + mapa, escrita de mudanças, versionamento); 15 documentos novos em `docs/` (arquitetura, operacao, configuracao, limites_e_calibracao, classes, scpi, quirks, decisoes, dataset, estender, diagnostico, testes, versionamento, glossario); correção de rótulo em `docs/metadata.md`; seção final em `CHANGELOG/v1.15.md`; este relatório. As 4 verificações foram rodadas no estado final dos `.md` (suíte 370 OK; `git status` só `.md` mais `.serena/` pré-existente; links: nenhum quebrado além dos placeholders `vX.Y`/`NN.py` e caminhos históricos já existentes no CHANGELOG; 42 variáveis e todos os comandos de CLI encontrados no código).

**NÃO FEITO:**
1. Verificação formal de "nenhuma ambiguidade" e leitura por alguém sem conhecimento prévio (critério de parada): não realizada; só conferência de fatos contra o código.
2. Cada linha de `docs/quirks.md` e `docs/decisoes.md` foi conferida no código ou no CHANGELOG citado, mas não reli os relatórios `docs/analise-2026-09-21` e `2026-09-30` por inteiro; itens vindos deles dependem da fonte citada.
3. `docs/TAREFAS_NUVEM_2026-10-07.md`, `docs/superpowers/` e os relatórios datados não foram revisados em busca de erros (por instrução, não se reescrevem).
4. `.env.example` (SNR_LEVELS_DB), o texto de ajuda da CLI (`[ON, 5V]`), os rótulos "v1.16" em `.py` e o ponto F1 (`lowvoltage` a 5 V) não foram tocados (não-`.md` ou código).
5. Autorização do dono em `AGENTS.md` para compostas, 08 e 05/07/17/18: não registrada (pendente do dono).
6. Zenodo/tag: apenas descritos; nada criado. Sem licença nem `CITATION.cff`.
7. Cobertura dos modos de teste unitários `docs/testes.md` é por nome de classe; não descreve cada teste.
