# Decisões de projeto (registro)

Decisões atualizadas para a execução P-01–P-31 estão em [`execucao_pendencias.md`](execucao_pendencias.md). Em particular, exclusões em listas (P-14), limite de três capturas no HTML físico (P-15) e direções P-09/P-11/P-12 prevalecem sobre escolhas anteriores conflitantes. A tabela abaixo preserva a motivação histórica e não é prova de nova validação física.


Por que o código é como é. Cada linha: decisão, motivo, onde está, fonte. As datas e versões são as do `CHANGELOG/`. Princípio geral do projeto: **validar (read-back, logs, testes) em vez de contornar** (sleeps maiores, retries, margens grandes) — ver `AGENTS.md`.

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
| v1.11 | Captura com erro descartável não aborta classe nem bateria | medida nos ensaios p01/p02: a captura falha na hora; abortar reexecutava a classe inteira (até 3×) | `ERROS_CAPTURA_DESCARTAVEL`, `mestre.py:693` |
| v1.11 | Validação física pós-captura, independente do mecanismo | H-NATIVO passou em silêncio por falta de qualquer validação | `mestre.py:1660` |
| v1.12 | Gravar a captura **antes** de conferir o teto de extremos | a captura que passou do teto é a evidência | `mestre.py:2602` |
| v1.12 | `AMETEK_SINCRONISMO=ESR` | `*OPC?` não sincroniza nesta revisão | `ametek_orm.py:174-180` |
| v1.13 | `capturas_padrao` por classe (3 onde `gerar()` sorteia) | uma captura de classe sorteada mostra uma só realização do sorteio (v1.13) | `mestre.py:1397` |
| v1.13 | `set seed` e seed da captura determinística | testes reprodutíveis | `mestre.py:1536` |
| v1.13 | Capturas = `max(CLI, padrão)` | o padrão da classe é o mínimo que a representa; `set capturas N` menor não o reduz | `Config.capturas` |
| v1.13 | 220 V: opção (b), reduzir só o distúrbio (limite de bancada) | a v1.12 pulava 10, 11, 14 e 16 a 220 V (extremo previsto 423–499 V > 415,8 V); reduzir o distúrbio mantém a classe sem alterar `gerar()` | `mestre.py:2846` |
| v1.13 | 380 V recusado (opção B) | 380 V é tensão de linha; a fonte gera 300 Vrms por fase | `start_bench_windows.ps1:74-92` |
| v1.14 | Fatores de extremo por condição; condição sem tabela é conservadora | 444 V medidos a 230 V/50 Hz | `mestre.py:514` |
| v1.14 | Checagem fonte × CH1 antes da primeira classe | disjuntor aberto | `mestre.py:1329` |
| v1.14 | `recortar_margem.py` e `relatorio_html.py` | compartilhar os dados sem exigir o código do projeto (o HTML abre sozinho) | `CHANGELOG/v1.14.md` |
| v1.15 | Perfis de faixas (`set perfil`) | adequação das classes à IEEE 1159: a norma e a literatura dão faixas diferentes; `literatura` reproduz 34a0d82 byte a byte | `perfis.py`, `docs/perfis.md` |
| v1.15 | Metadata `.json` legível ao lado do `.jsonl`; `sessao.json`; cópia da calibração; commit/numpy gravados | rastreabilidade para arquivar (Zenodo) | `docs/metadata.md` |
| v1.15 | Início, duração e fase sorteados; sub-fluxo da seed | o distúrbio caía sempre no mesmo ponto; parâmetros antigos não podem mudar | `mestre.py:765-855` |
| v1.15 | Parâmetros das compostas 10–16 sorteados | compostas eram cópias da mesma onda | `perfis.composto`, `arquivo/analises:docs/analise-2026-10-12/pendente/compostas_sorteadas_REVISAR.md` |
| v1.15 | Três versões (modelo / programada / medida) | separar limite da bancada de física da fonte | `docs/tres_versoes.md` |
| v1.15 | Um `NN_classe.npz` comprimido por classe, com perfis e versões; SNRs em arquivos por classe e nível; `set perfil todos` | tudo da mesma classe no mesmo arquivo (com três perfis e três versões, uma classe teria até 9 séries por captura espalhadas em muitos arquivos); o `run all` percorre os três perfis na mesma sessão. Substitui "físico = 1 por captura" da v1.8. Cada captura vai antes para `parcial/` (atômica), para não perder o que foi feito se a classe for interrompida | `sessao_io.py`, `docs/dataset.md`, `CHANGELOG/v1.15.md` |
| v1.15 | Regra de extremos por frequência | a resposta da saída depende da frequência | `mestre.py:514`, `regra_por_frequencia.md` |
| v1.15 | Classe 08 fora da fronteira de ciclo + conferência de posição | impulso a +20 ms a 50 Hz | `08.py`, `classe08_fronteira.md` |
| v1.15 | 05 pelo modelo CSINe; 07/17 entalhes contínuos; 18 em f0 ± 3 Hz | alinhar modelo, fonte e norma | `classes_05_07_18.md` |
| v1.15 | Ruído de 20, 30 e 40 dB só na janela rotulada | a potência de referência do SNR é a da janela rotulada; margens não entram | `sinais.ruido_na_janela`, `snr_mudancas.md` |
| v1.15 | `set recalibracao` e `set html` (OFF por padrão) | fazer o fim do run gerar o HTML e, se pedido, recalibrar, sem comando extra; OFF por padrão porque a recalibração altera o JSON do repositório | `cli.py:129-147` |
| v1.15 | Geradores de PNG descontinuados; só o relatório HTML gera figuras | decisão de projeto: um único gerador de figuras (o HTML) | `descontinuar_imagens.md` |
| v1.15 | Versão segue v1.15 (em andamento, sem tag) | manter tudo na v1.15 (em andamento, sem tag) até o congelamento: os perfis entram juntos numa versão congelada antes da próxima campanha | `docs/versionamento.md` |
| v1.15 | Compostas sorteiam também sag em 11/12, swell em 13/14 e THD em 13/15/16; faixa do swell = extremos de `swell_niveis` | componente compartilhado: sortear só na 10 deixaria as outras com uma forma de nível por classe e THD fixo no teto da faixa | `perfis.py:113-134`, `docs/perfis.md` |
| v1.15 | `norma` sorteia sag 0,15-0,85, swell 1,15-1,75, THD 2-20 %; `fronteira` não sorteia sag/swell (alterna os pares) | extremos dos níveis discretos de cada perfil; a fronteira existe para estressar o limite | `perfis.py:116-120`, `docs/perfis.md` |
| v1.15 | 16 com interrupção fixa em 0,05 pu; 17 com oscilação fixa em 300 Hz | sortear a interrupção a tiraria da faixa de interrupção em parte das capturas; a 17 já sorteia os entalhes | `16.py:29`, `17.py:37` |

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
| Crista da validação física = crista do modelo × fator de extremo calibrado (aceita `[×0,9, ×fator×1,1]`) | a fonte toca a cada entalhe de 0,1 ms e o pico do ciclo mediano sobe (+31 a +59 %); decisão de projeto (2026-10-13): usar a calibração em vez de afrouxar a tolerância; a calibração já mede o sobressinal por classe e condição. Bilateral porque a fonte pode tocar menos que o máximo calibrado | `mestre.py:1872`, `sinais.py:429` |
| Pré-validação pula antes de qualquer SCPI | nada é enviado à fonte para o que não cabe | `mestre.py:1928` |
