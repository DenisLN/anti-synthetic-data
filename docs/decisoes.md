# Decisões de projeto (registro)

Por que o código é como é. Cada linha: decisão, motivo, onde está, fonte. "Dono" = o autor do TCC. As datas e versões são as do `CHANGELOG/`. Princípio geral do dono: **validar (read-back, logs, testes) em vez de contornar** (sleeps maiores, retries, margens grandes) — ver `AGENTS.md`.

## Arquitetura e dados

| Quando | Decisão | Motivo | Onde / fonte |
|---|---|---|---|
| v1.0 | Dois modos (`BENCH_MODE`), simulado por padrão | gerar o dataset de treino sem hardware; a bancada só confirma | `mestre.py:312`, `CHANGELOG/v1.0.md` |
| v1.0 | Experimentos recebem `Config` por injeção; carregados por caminho | desacoplar classes de configuração global | `mestre.py:697,1214` |
| v1.0 | `AmetekMX30` com limites no construtor | um experimento nunca sabe o limite; o objeto recusa | `ametek_orm.py:182-210` |
| v1.0 | Ciclos e `DWELl` derivados de `f0` (500 amostras a 60 Hz, 600 a 50 Hz) | com 600 fixos o pico inflava ~15 % e a fase quebrava a 60 Hz | `CHANGELOG/v1.0.md` §6.2; `montar_programacao` |
| v1.1 | Nenhum SCPI cru nos experimentos | segurança e testabilidade | `CHANGELOG/v1.1.md` |
| v1.2 | Gravar dado puro além do com ruído | reaplicar outro SNR sem recapturar | `CHANGELOG/v1.2.md` |
| v1.3 | `logica/` (motor), `scripts/` (operador), experimentos na raiz | clareza | `CHANGELOG/v1.3.md` |
| v1.7 | CLI interativa no lugar de 5 etapas fixas | reexecutar sem repetir ~50 s de Flash | `cli.py`, `CHANGELOG/v1.7.md` |
| v1.7 | Falha de experimento isolada; infraestrutura aborta | perder 19 classes por uma falha era caro; estado desconhecido é perigoso | `mestre.py:1095` |
| v1.8 | Sessão isolada por pasta; simulado = 1 `.npz` por classe, físico = 1 por captura | um `run` sobrescrevia o anterior; nomes repetidos destruíam dados | `cli.py:199`, `mestre.py:2042` |
| v1.8 | Cobertura determinística do intervalo com `set capturas` | N sorteios podem se repetir | `sinais.valor_para_captura` |
| v1.11 | Salvar cada captura assim que sai (atômico, `fsync`) | uma falha perdia as capturas boas | `mestre.py:2164` |
| v1.11 | Margem fixa de 20/50 ms em toda captura física; `set margin` descontinuado | o "atraso" era artefato do osciloscópio; 50 ms cobrem o retorno ao regime | `mestre.py:2004-2024` |
| v1.11 | Captura com erro descartável não aborta classe nem bateria | pedido do dono: abortar gasta muito tempo | `ERROS_CAPTURA_DESCARTAVEL`, `mestre.py:693` |
| v1.11 | Validação física pós-captura, independente do mecanismo | H-NATIVO passou em silêncio por falta de qualquer validação | `mestre.py:1660` |
| v1.12 | Gravar a captura **antes** de conferir o teto de extremos | a captura que passou do teto é a evidência | `mestre.py:2602` |
| v1.12 | `AMETEK_SINCRONISMO=ESR` | `*OPC?` não sincroniza nesta revisão | `ametek_orm.py:174-180` |
| v1.13 | `capturas_padrao` por classe (3 onde `gerar()` sorteia) | pedido do dono (2026-10-07) | `mestre.py:1397` |
| v1.13 | `set seed` e seed da captura determinística | testes reprodutíveis | `mestre.py:1536` |
| v1.13 | Capturas = `max(CLI, padrão)` | pedido do dono | `Config.capturas` |
| v1.13 | 220 V: opção (b), reduzir só o distúrbio (limite de bancada) | para as classes caberem sem alterar `gerar()` | `mestre.py:2846` |
| v1.13 | 380 V recusado (opção B) | 380 V é tensão de linha; a fonte gera 300 Vrms por fase | `start_bench_windows.ps1:74-92` |
| v1.14 | Fatores de extremo por condição; condição sem tabela é conservadora | 444 V medidos a 230 V/50 Hz | `mestre.py:514` |
| v1.14 | Checagem fonte × CH1 antes da primeira classe | disjuntor aberto | `mestre.py:1329` |
| v1.14 | `recortar_margem.py` e `relatorio_html.py` | compartilhar dados com os professores | `CHANGELOG/v1.14.md` |
| v1.15 | Perfis de faixas (`set perfil`) | pergunta do professor sobre a IEEE 1159; `literatura` reproduz 34a0d82 byte a byte | `perfis.py`, `docs/perfis.md` |
| v1.15 | Metadata `.json` legível ao lado do `.jsonl`; `sessao.json`; cópia da calibração; commit/numpy gravados | rastreabilidade para arquivar (Zenodo) | `docs/metadata.md` |
| v1.15 | Início, duração e fase sorteados; sub-fluxo da seed | o distúrbio caía sempre no mesmo ponto; parâmetros antigos não podem mudar | `mestre.py:765-855` |
| v1.15 | Parâmetros das compostas 10–16 sorteados | compostas eram cópias da mesma onda | `perfis.composto`, `docs/analise-2026-10-12/compostas_sorteadas.md` |
| v1.15 | Três versões (modelo / programada / medida) | separar limite da bancada de física da fonte | `docs/tres_versoes.md` |
| v1.15 | Regra de extremos por frequência | a resposta da saída depende da frequência | `mestre.py:514`, `regra_por_frequencia.md` |
| v1.15 | Classe 08 fora da fronteira de ciclo + conferência de posição | impulso a +20 ms a 50 Hz | `08.py`, `classe08_fronteira.md` |
| v1.15 | 05 pelo modelo CSINe; 07/17 entalhes contínuos; 18 em f0 ± 3 Hz | alinhar modelo, fonte e norma | `classes_05_07_18.md` |
| v1.15 | Ruído de 20, 30 e 40 dB só na janela rotulada | pedido do professor; margens não entram | `sinais.ruido_na_janela`, `snr_mudancas.md` |
| v1.15 | `set recalibracao` e `set html` (OFF por padrão) | automatizar o fim do run sem mexer no JSON sem pedir | `cli.py:129-147` |
| v1.15 | Geradores de PNG descontinuados; só o relatório HTML gera figuras | decisão do dono | `descontinuar_imagens.md` |
| v1.15 | Versão segue v1.15 (em andamento, sem tag) | decisão do dono, 2026-10-12 | `docs/versionamento.md` |

## Segurança e hardware

| Decisão | Motivo | Onde |
|---|---|---|
| `COM10`/`115200` fixos e validados | única configuração confirmada | `validate_bench_configuration` |
| Confirmação digitada case-sensitive por comando que energiza; `ARM_OUTPUT` só durante o comando | nenhuma energização sem o operador | `cli.py:186,256` |
| Saída ligada **uma vez** por bateria (`energize_baseline`), nunca desligada entre capturas | exemplo do manual (cap. 6.4.2); evita o relé | `mestre.py:1055-1061` |
| Tensão imediata 0 V no baseline; `assegurar_tensao_base` antes de `run <NN>` | nunca saltar para a tensão de teste sem transiente controlado | `mestre.py:1231` |
| `VOLTage:HIGH` = limite rms | medido: não é de pico | `ametek_orm.py:1225` |
| Captura de corrente desligada | sem fator da probe de corrente a escala é inválida | `CAPTURE_CURRENT=0` |
| Cache de TRACe por conexão, reconfirmado no catálogo | evita ~1 s por TRACe sem confiar cegamente | `ametek_orm.py:1471` |
| Não reduzir a margem de captura sem refazer a medida | `mestre.py:2019-2022` | — |
| Modo Digitizer do osciloscópio descartado | não entrega 36 000 pontos | `oscilloscope_orm.py:276-284` |
| 08: teto de 0,9 × `max_peak_v` e medida de pico obrigatória | a saída oscila além do programado | `08.py:63-69` |
| Pré-validação pula antes de qualquer SCPI | nada é enviado à fonte para o que não cabe | `mestre.py:1928` |
