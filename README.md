# Bancada de instrumentação para dataset de qualidade de energia

Repositório de um TCC cujo objetivo final é um analisador de qualidade de energia embarcado em um ESP32. Para treinar o classificador é preciso um dataset rotulado de **20 classes de distúrbio de tensão**; este repositório o produz de duas formas:

- **Simulado** (Python/NumPy, sem hardware, padrão): milhares de capturas por classe.
- **Bancada física**: fonte CA programável **AMETEK MX30-3Pi** gera o distúrbio e o osciloscópio **Keysight DSO-X 4034A** o captura (sincronizados por cabo BNC: Trigger Out → EXT Trigger), para confirmar que a bancada reproduz o modelo.

Cada captura tem 200 ms = 6000 amostras a 30 kSa/s, em pu do pico nominal, com ruído de 20/30/40 dB acrescentado só na janela rotulada. Os modos são escolhidos pela variável `BENCH_MODE` (`0` simulado, `1` bancada).

**Estado:** versão **v1.15, em andamento (não congelada, sem tag)**. Regras de versionamento e arquivamento: [`docs/versionamento.md`](docs/versionamento.md).

## Início rápido

### Sem hardware (qualquer máquina com Python 3.11+)
```powershell
.\scripts\setup_windows.ps1                                   # cria env/ e instala requirements.txt
.\env\Scripts\python.exe -m unittest tests.test_offline       # suíte offline (ver `docs/testes.md`)
.\scripts\run_simulation_windows.ps1 -CapturesPerClass 2000   # dataset simulado em resultados/
```

### Na bancada (Windows, instrumentos conectados)
```powershell
cd C:\Users\denis\TCC\code
scripts\START_BENCH.cmd      # pergunta fator da probe, tensão e frequência; abre a CLI "bancada>"
```
Dentro da CLI: `help`; sequência recomendada `comm` → `trigger` → `native` → `run all`. Cada comando que energiza a saída pede uma string digitada (case-sensitive). **Leia [`docs/operacao.md`](docs/operacao.md) antes de energizar qualquer coisa.**

## Segurança (resumo; regras completas em [`AGENTS.md`](AGENTS.md))
- Porta `COM10` e `115200` baud fixas; limites de software 300 Vrms e 415,8 Vp (hardware: 300 Vrms por fase, 425 Vp); tensão de teste ≤ 270 V fase-neutro (380 V é recusado).
- Nenhuma energização sem confirmação digitada; nada de SCPI cru nos experimentos; captura de corrente desligada.
- Falha de infraestrutura: confirmar **OUTPUT OFF** no painel, não repetir sozinho, entregar os logs.

## Mapa da documentação

A documentação é um **site Sphinx** (MyST + Furo) construído a partir de `docs/`, com `.readthedocs.yaml` para o Read the Docs (a publicação depende de importar o repositório no serviço, ainda não feita). Ponto de entrada: [`docs/index.md`](docs/index.md); como compilar localmente: [`docs/contribuir_docs.md`](docs/contribuir_docs.md) (`python -m sphinx -W --keep-going -b html docs docs/_build/html`, dependências em `docs/requirements.txt`). Os nomes dos arquivos abaixo não mudaram; as pastas novas são `docs/classes/`, `docs/scpi/`, `docs/medicao/`, `docs/projeto/` e `docs/codigo/`.

| Documento | Conteúdo |
|---|---|
| [`AGENTS.md`](AGENTS.md) | regras para agentes de IA e limites inegociáveis; como escrever mudanças e versionar |
| [`docs/index.md`](docs/index.md), [`docs/como-ler.md`](docs/como-ler.md) | início do site; os cinco selos de status (VERIFICADO NA BANCADA, OFFLINE, NÃO VERIFICADO, PENDENTE, FORA DA MAIN) e as convenções de escrita |
| [`docs/guia-operador.md`](docs/guia-operador.md), [`docs/seguranca.md`](docs/seguranca.md), [`docs/roteiro-bancada.md`](docs/roteiro-bancada.md) | guia do operador, limites inegociáveis e camadas de segurança, roteiro da próxima bancada |
| [`docs/classes/`](docs/classes/) | **20 fichas, uma por classe** (`01-normal.md` a `20-interharmonics.md`): fenômeno e norma, modelo em `gerar()`, sequência SCPI, perfis, limites, validação física, correlação esperada, quirks, histórico, pendências e o código método a método |
| [`docs/scpi.md`](docs/scpi.md), [`docs/scpi/`](docs/scpi/) | referência SCPI comando a comando (AMETEK e Keysight), sequências completas e índice das transcrições |
| [`docs/medicao.md`](docs/medicao.md), [`docs/medicao/`](docs/medicao/) | cadeia de medição, janela e margens; correlação esperada por classe; recalibração passo a passo |
| [`docs/projeto/`](docs/projeto/) | estado de validação por classe e camada, as 31 pendências `P-01` a `P-31`, o passo final SINE (fora da `main`), análises arquivadas |
| [`docs/codigo.md`](docs/codigo.md), [`docs/codigo/`](docs/codigo/) | Guia do código: percursos de um `run` e de uma captura TRACe, uma página por módulo, invariantes e acoplamentos |
| [`docs/historico.md`](docs/historico.md) | o `CHANGELOG/` incluído no site (sem cópia) |
| [`docs/arquitetura.md`](docs/arquitetura.md) | mapa de arquivos, componentes, fluxos (bateria, captura), camadas de segurança, scripts |
| [`docs/operacao.md`](docs/operacao.md) | ligação física, `START_BENCH`, todos os comandos da CLI, falhas, depois da sessão, relatório HTML e recalibração ao fim do run (§9) |
| [`docs/configuracao.md`](docs/configuracao.md) | todas as variáveis de ambiente, validações de configuração |
| [`docs/limites_e_calibracao.md`](docs/limites_e_calibracao.md) | pré-validação de pico, limite de bancada, fatores de extremo por condição, 220/380 V |
| [`docs/classes.md`](docs/classes.md) | visão geral das 20 classes (tabela com link para cada ficha), sorteio de início, duração e fase, tolerâncias da validação física, capturas por classe |
| [`docs/perfis.md`](docs/perfis.md) | perfis `norma` / `literatura` / `fronteira` |
| [`docs/quirks.md`](docs/quirks.md) | comportamentos dos equipamentos que contrariam o manual |
| [`docs/decisoes.md`](docs/decisoes.md) | decisões de projeto e seus motivos |
| [`docs/dataset.md`](docs/dataset.md) | arquivos gerados, formatos, carregamento, ferramentas offline |
| [`docs/metadata.md`](docs/metadata.md) | formato do metadata (campo a campo) |
| [`docs/tres_versoes.md`](docs/tres_versoes.md) | modelo / programada / medida |
| [`docs/correlacao_disturbio.md`](docs/correlacao_disturbio.md) | correlação da componente de distúrbio |
| [`docs/estender.md`](docs/estender.md) | como criar uma classe ou estender o projeto, erros a evitar |
| [`docs/diagnostico.md`](docs/diagnostico.md) | `set diagnostico on` e scripts de diagnóstico |
| [`docs/testes.md`](docs/testes.md) | suíte de testes e fixtures |
| [`docs/versionamento.md`](docs/versionamento.md) | tags, CHANGELOG, sessão de commit limpo, Zenodo, mapa das versões |
| [`docs/glossario.md`](docs/glossario.md) | termos |
| [`CHANGELOG/`](CHANGELOG/) | histórico por versão (`v1.0.md` a `v1.15.md`); registro, não se reescreve |
| [`experimentos.txt`](experimentos.txt) | especificação original das 20 classes |
| `arquivo/analises:docs/analise-*/` | relatórios datados de cada rodada de bancada/análise (registro histórico; fora de `docs/` desde 2026-10-13, no branch `arquivo/analises`) |
| `docs/*.pdf` | manuais SCPI da AMETEK e do Keysight |

## Estrutura (resumo)
```
logica/                 motor: mestre.py, ametek_orm.py, oscilloscope_orm.py, sinais.py, perfis.py, cli.py, preflight_new.py, análise offline
experimentos_nativos/   classes 01-05, 18, 19 (recurso nativo da fonte)
experimentos_waveform/  classes 06-17, 20 (TRACe/LIST)
scripts/                PowerShell/CMD do operador e utilitários Python
tests/                  test_offline.py e fixtures
resultados/  logs/      saída (gitignored)
```

## Pendente fora da `main`
O branch `feat/passo-final-sin` (PR #3) acrescenta um passo final `SINE` ao `LIST` das classes TRACe e **aguarda validação na bancada**; não faz parte da `main`.
