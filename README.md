# Bancada de instrumentação para dataset de qualidade de energia

Repositório de um TCC cujo objetivo final é um analisador de qualidade de energia embarcado em um ESP32. Para treinar o classificador é preciso um dataset rotulado de **20 classes de distúrbio de tensão**; este repositório o produz de duas formas:

- **Simulado** (Python/NumPy, sem hardware, padrão): milhares de capturas por classe.
- **Bancada física**: fonte CA programável AMETEK MX30-3Pi gera o distúrbio e o osciloscópio Keysight DSO-X 4034A o captura, para confirmar que a bancada reproduz o modelo.

**Estado:** versão v1.15, em andamento (não congelada, sem tag).

## Documentação

Toda a documentação de referência (operação, SCPI, código, classes, perfis, limites, pendências) está no site **<https://anti-synthetic-data.readthedocs.io/>**. A fonte do site é [`docs/`](docs/); como construí-lo e como escrever nele: [`docs/contribuir_docs.md`](docs/contribuir_docs.md). Este README não repete esse conteúdo.

## Início rápido

Sem hardware (Windows, Python 3.11+):

```powershell
.\scripts\setup_windows.ps1                                              # cria env/ e instala requirements.txt
.\env\Scripts\python.exe -m unittest discover -s tests -p "test*.py"     # suíte offline
.\scripts\run_simulation_windows.ps1 -CapturesPerClass 2000              # dataset simulado em resultados/
```

Na bancada (Windows, instrumentos conectados; leia antes `docs/operacao.md` no site):

```powershell
scripts\START_BENCH.cmd       # pergunta fator da probe, tensão e frequência; abre a CLI "bancada>"
scripts\VISITA_BANCADA.cmd    # a visita inteira num comando; o operador digita as confirmações
```

Nenhum comando energiza a saída sem confirmação digitada pelo operador. As regras de segurança e os limites inegociáveis estão em [`AGENTS.md`](AGENTS.md).

## Fora do site

- [`AGENTS.md`](AGENTS.md) e [`CLAUDE.md`](CLAUDE.md): instruções para agentes de IA (regras, autorizações, limites inegociáveis); apontam para as páginas do site em vez de copiá-las.
- [`mapa/`](mapa/00%20In%C3%ADcio.md): vault Obsidian de navegação para agentes (o que ler para cada tarefa); parte dele é gerada por `scripts/gerar_mapa_pendencias.py`.
- [`CHANGELOG/`](CHANGELOG/): histórico por versão (`v1.0.md` a `v1.15.md`); registro, não se reescreve.
