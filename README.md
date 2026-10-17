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
Dentro da CLI: `help`; sequência recomendada `comm` → `trigger` → `native` → listas por conexão conforme [`ROTEIRO_BANCADA.md`](ROTEIRO_BANCADA.md) (até 216 gravações de TRACe no plano padrão). Cada comando que energiza a saída pede uma string digitada (case-sensitive). **Leia [`docs/operacao.md`](docs/operacao.md) antes de energizar qualquer coisa.**

## Segurança (resumo; regras completas em [`AGENTS.md`](AGENTS.md))
- Porta `COM10` e `115200` baud fixas; limites de software 300 Vrms e 415,8 Vp (hardware: 300 Vrms por fase, 425 Vp); tensão de teste ≤ 270 V fase-neutro (380 V é recusado).
- Nenhuma energização sem confirmação digitada; nada de SCPI cru nos experimentos; captura de corrente desligada.
- Falha de infraestrutura: confirmar **OUTPUT OFF** no painel, não repetir sozinho, entregar os logs.

## Mapa da documentação

| Documento | Conteúdo |
|---|---|
| [`AGENTS.md`](AGENTS.md) | regras para agentes de IA e limites inegociáveis; como escrever mudanças e versionar |
| [`docs/arquitetura.md`](docs/arquitetura.md) | mapa de arquivos, componentes, fluxos (bateria, captura), camadas de segurança, scripts |
| [`docs/execucao_pendencias.md`](docs/execucao_pendencias.md) | plano de execução P-01 a P-31, decisões atuais, evidências e bloqueios |
| [`docs/operacao.md`](docs/operacao.md) | ligação física, `START_BENCH`, todos os comandos da CLI, falhas, depois da sessão, relatório HTML e recalibração ao fim do run (§9) |
| [`docs/configuracao.md`](docs/configuracao.md) | todas as variáveis de ambiente, validações de configuração |
| [`docs/limites_e_calibracao.md`](docs/limites_e_calibracao.md) | pré-validação de pico, limite de bancada, fatores de extremo por condição, 220/380 V |
| [`docs/classes.md`](docs/classes.md) | as 20 classes: mecanismo, parâmetros, sorteio, capturas padrão, classe 08 |
| [`docs/perfis.md`](docs/perfis.md) | perfis `norma` / `literatura` / `fronteira` |
| [`docs/scpi.md`](docs/scpi.md) | comandos SCPI de cada instrumento e sua função |
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
