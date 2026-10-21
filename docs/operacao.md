# Operação na bancada física

Para quem vai energizar a fonte. Leia tudo antes de conectar qualquer cabo. Regras de segurança invioláveis: `AGENTS.md`. A revisão de pendências atual está em `docs/execucao_pendencias.md`; referências numéricas remanescentes são históricas e não devem ser usadas como prova do estado atual. Localize os símbolos citados no checkout identificado.

## 1. Ligação física obrigatória

- **AMETEK MX30-3Pi** por **USB**, vista pelo Windows como `COM10` (PyVISA `ASRL10::INSTR`), **115200 baud**, 8N1, sem controle de fluxo. Fixo: `validate_bench_configuration()` (`mestre.py:366`) e `AmetekMX30.connect()` (`ametek_orm.py:318`) recusam outra porta/baud.
- **Não** conectar o DB9 RS-232 ao mesmo tempo que a USB. **Não** deixar o MX GUI aberto (ele segura a COM10; os scripts `diag_*` avisam).
- **Keysight DSO-X 4034A**: `USB0::0x0957::0x17A4::MY59240844::0::INSTR` (endereço desta unidade; `KEYSIGHT_RESOURCE=AUTO` ou vazio faz descoberta por `*IDN?`, `mestre.py:904-935,1013-1017`).
- **Cabo BNC**: AMETEK *Trigger Out* → Keysight *EXT Trigger*. Sem ele o osciloscópio nunca dispara.
- **Probe diferencial de tensão no CH1**, entre fase A e neutro. O fator digitado tem de ser **exatamente** o da chave da probe.
- Instalar **Keysight IO Libraries Suite** ou **NI-VISA x64**.
- Disjuntores entre a fonte e a probe **fechados**: em 2026-10-07 um disjuntor aberto fez 20 classes serem medidas a ~0,45 do esperado (ruído da rede), sem erro de software. A checagem da cadeia de medição (seção 5) existe por isso.

## 2. Software

```powershell
cd C:\Users\denis\TCC\code          # ajuste ao caminho da máquina
scripts\START_BENCH.cmd
```

`START_BENCH.cmd` → `start_bench_windows.ps1`:
1. `setup_windows.ps1` cria/atualiza `env/` e instala `requirements.txt`.
2. Carrega `bench_config.ps1` (variáveis; `ARM_OUTPUT=NO`).
3. Pergunta o **fator da probe** (se `VOLTAGE_PROBE_ATTENUATION` vazio), a **tensão rms fase-neutro** e a **frequência** (`start_bench_windows.ps1:17-59`). Não invente o fator. Esses valores viram constantes do processo Python; mudar exige reiniciar.
4. Tensão ≤ **270 V** (127 e 220 V são os casos de uso). Acima disso recusa: 380 V é tensão de **linha**; cada fase de um sistema 220/380 V tem 219,4 V, digite 220 (`:83-92`).
5. Fixa `SOURCE_VOLTAGE_RANGE_RMS=300`, `EUT_MAX_VOLTAGE_RMS=300`, `EUT_MAX_PEAK_V=415,8` (98 % de 300·√2) (`:94-101`). Não sobrescrever.
6. Abre `logica/cli.py`.

Seed opcional: variável `BASE_SEED` antes do `START_BENCH`, ou `set seed N` na CLI.

## 3. A CLI (`bancada>`)

`help` ou `?` imprime a referência completa (`cli.py:59-164`). Todos os comandos abaixo foram conferidos no código.

| Comando | Energiza? | O que faz |
|---|---|---|
| `status` | não | modo, porta, `ARM_OUTPUT`, tensão/frequência base, margem, `diagnostico`, `set capturas`, seed, perfil, sorteio, `recalibracao`/`html`, capturas por classe e estimativa de gravações de TRACe, pasta da sessão, último resultado por classe |
| `list` | não | as 20 classes com capturas efetivas, padrão da classe e último status |
| `comm` | não | `*IDN?` dos dois instrumentos, protocolo/porta, OUTPUT OFF (`preflight_new.run_basic_stage`) |
| `trigger` | não | força uma aquisição do Keysight (valida download/decodificação; **não** testa o BNC) |
| `lowvoltage` | **sim** | recomissionamento (BNC + trigger real + rms). Pede `ENERGIZAR-TESTE`. Opcional; reprograma TRACes na Flash (~40-50 s). **Ver aviso abaixo** |
| `native` | **sim** | `preflight_new.run_native_commands`: STEP, PULSe, CSINe, `LIST:FREQuency`, ACDC, `MEASure:*`, canal 2. Pede `ENERGIZAR-COMANDOS` |
| `run <NN\|nome>` | **sim** | uma classe (`run 02`, `run SAG`). Pede `EXECUTAR-CLASSE-<NN>` |
| `run all` | **sim** | as 20 classes (menos `BATERIA_EXCLUIR`), resiliente por classe. Pede `EXECUTAR-20-CLASSES` e mostra capturas planejadas e gravações de TRACe |
| `run <lista>` | **sim** | uma lista por intervalos e/ou ids soltos, na ordem numérica (`run 01-07,09-20`, `run 2,5,8`; espaços ao redor de vírgulas/intervalos aceitos; argumentos extras ambíguos como `run 01 02` ou `run all extra` recusados). Passa por `Bancada.executar_bateria`, com os mesmos ganchos e resumo do `run all`. Aplica `BATERIA_EXCLUIR` também à lista explícita; as exclusões aparecem antes da confirmação. Lista totalmente excluída não executa nenhuma classe. Pede `EXECUTAR-CLASSES-<lista normalizada>` (ex.: `EXECUTAR-CLASSES-01-07,09-20`, case-sensitive) e mostra as capturas de cada classe escolhida e a estimativa de TRACe só delas. Lista inválida (id fora de 01-20, intervalo invertido ou vazio, item vazio) é recusada com código 1 antes de qualquer confirmação, sem energizar (`cli.py`, `parsear_lista_classes`) |
| `run falhas [<pasta_sessao>]` | **sim** | reexecuta o que deu problema numa sessão (padrão: a última pasta criada por esta CLI), lido do `falhas.json`: capturas `descartada`/`invalida`, `classe_falhou` e `nao_executada_orcamento` (as puladas por capacidade/pré-validação não, pois repetiriam a mesma recusa). Mesmo `indice_global` (logo mesma seed e `capture_index`), perfil e nível; restaura seed base, `set capturas`, sorteio e perfis da origem só durante o rerun. **Recusa sem energizar** se tensão, frequência, braço P-09, `AMETEK_PASSO_FINAL_SIN`, limites (`EUT_MAX_VOLTAGE_RMS`, `EUT_MAX_PEAK_V`, `SOURCE_VOLTAGE_RANGE_RMS`) ou o SHA-256 da calibração de extremos atuais diferirem da origem, dizendo o que mudar (calibração: copiar `<sessao>/calibracao_extremos.json` sobre `logica/calibracao_extremos.json` e restaurar depois); recusa também `falhas.json` ilegível e seleção só de puladas (numa seleção mista, as puladas são retiradas com aviso). Cria sessão **nova** com `rerun_de` no `sessao.json` e em cada captura; estimativa de TRACe só das capturas escolhidas; pede a confirmação normal (`EXECUTAR-CLASSE-<NN>` ou `EXECUTAR-CLASSES-<lista>`) (`cli.py`, `SessaoCLI._rerun`) |
| `rerun <pasta_sessao> <id_captura\|NN> [...]` | **sim** | como `run falhas`, só para as capturas (`10-0003`) ou classes (`10` = todas as entradas da classe em `falhas.json`) escolhidas; aceita id de captura gravada (procurado no metadata) ; puladas por capacidade/pré-validação são retiradas (só elas = recusa: seriam puladas de novo). A pasta pode ser o caminho ou só o nome dentro de `resultados/` |
| `set diagnostico on\|off` | não | log extra de estado da fonte em pontos-chave; com `on` abre um terminal com `tail -f` da transcrição SCPI (opt-out: `DIAGNOSTICO_ABRIR_TERMINAL=0`) |
| `set capturas <N>` / `set capturas padrao` | não | piso global de capturas: cada classe roda `max(N, padrão da classe)`, por nível nas classes com níveis (`Config.capturas`, `mestre.py:730`). Com `set capturas` ativo, 04/06/09/19 cobrem o intervalo do parâmetro e a 08 faz caracterização (rampa de amplitude). `padrao` (ou `off`) desfaz |
| `set seed <N>` / `set seed padrao` | não | seed base (inteiro ≥ 0) dos próximos `run`; `padrao` volta à do início da CLI |
| `set perfil norma\|literatura\|fronteira\|todos` | não | faixas do dataset (`docs/perfis.md`). `todos`: `run all`, `run <lista>` e `run <NN>` percorrem os **três** perfis na mesma sessão (cada classe que depende do perfil roda uma vez por perfil, ordem norma, literatura, fronteira; as 8 que não dependem — 01, 04, 07, 08, 09, 17, 18, 19 — rodam **uma só vez**, sob `literatura`, e o metadata dos outros perfis aponta para a mesma captura) e gravam tudo no mesmo `NN_classe.npz` (`docs/dataset.md` §2). A confirmação do `run all`/`run <lista>` soma as capturas e as gravações de TRACe só do que roda de fato (o número de níveis, e com ele o de capturas, muda com o perfil; `cli.py`, `_capturas_das_classes`); `run <NN>` também (`cli.py`, `_run_uma`). Gravações de TRACe do `run all` (sorteio ligado): 1116 a 60 Hz e 930 a 50 Hz (eram 1404 e 1170 sem a deduplicação; 468 e 390 com um perfil só). Env `PERFIL=todos` vale para o simulado (`mestre.py`) |
| `set sorteio on\|off` | não | sorteio de início/duração/fase (padrão `on`) |
| `set recalibracao on\|off` | não | ao fim de cada run **físico** que terminou OK, recalcula e **grava** `logica/calibracao_extremos.json` (só sobe fator; condição nova não ganha tabela). Padrão `off`. Detalhes e reversão: §9 |
| `set html on\|off` | não | ao fim de cada run, recorta a margem (`sem_margem/`) e gera `relatorio_<sessao>.html`. Padrão `off`. Detalhes, custo e seleção: §9 |
| `help`, `?`, `quit`, `exit` | não | — |
| `set margin ...` | — | **descontinuado**: só imprime um aviso (a margem é sempre aplicada) |

`set perfil`, `set sorteio`, `set seed` e `set capturas` valem a partir do **próximo** `run`.

> **Aviso verificado no código (v1.15):** `lowvoltage` e `native` chamam `preflight_new.run_basic_stage(low_voltage=True)` / `preflight_new.run_native_commands()` (`cli.py:517-545`), que usam `BASE_VOLTAGE_RMS` (a tensão digitada no início). Não há nenhum código que force 5 V. Com `START_BENCH` iniciado em 127 V, `lowvoltage` programa e mede **127 V**; desde a v1.15 o aviso da CLI mostra essa tensão e a confirmação é `ENERGIZAR-TESTE` (antes era o enganoso `ENERGIZAR-5V`). Para um recomissionamento a 5 V de fato, inicie o `START_BENCH` digitando 5 V. Não foi testado no hardware; é leitura do código.

Sem hardware (`BENCH_MODE=0`): `status`, `list` e `run` funcionam em modo simulado; `comm`, `trigger`, `lowvoltage`, `native` exigem bancada.

Ordem recomendada para uma sessão do zero: `comm` → `trigger` → `native` → (`lowvoltage`, só se mexeu em fiação/probe) → listas do {doc}`roteiro-bancada`, com até 216 gravações de TRACe por conexão no plano padrão. Não usar `run all` para a campanha. Antes de scripts `diag_*` que acessam hardware, sair com `quit` e confirmar OUTPUT OFF para liberar COM10.

## 4. Confirmações físicas (não automatizar)

1. Fator da probe e tensão/frequência, perguntados pelo `start_bench_windows.ps1`.
2. A string digitada, **case-sensitive**: `ENERGIZAR-TESTE`, `ENERGIZAR-COMANDOS`, `EXECUTAR-CLASSE-<NN>` (ex.: `EXECUTAR-CLASSE-02`), `EXECUTAR-20-CLASSES`. Antes de digitar confira probe, cabos, **E-stop** e EUT. A CLI põe `ARM_OUTPUT=YES` só durante o comando e revoga ao fim (`cli.py:186-197`).

## 5. O que acontece em um `run` e como ler o resultado

1. A CLI cria `resultados/sessao_<timestamp>/` (do segundo `run` da mesma CLI em diante, `_run02`, `_run03`, …; `cli.py:199-223`), liga `sessao.log` e `scpi_transcricao.log`, copia a calibração e grava `sessao.json`.
2. **Árvore git suja** (alteração rastreada em qualquer arquivo ou novo não ignorado nas pastas `mestre.PASTAS_DO_CODIGO`, recalculada a cada pasta de sessão por `info_do_codigo`) em sessão de bancada: aviso em destaque (linhas de `!`), sem bloquear. Regra do projeto: toda sessão sai de commit limpo (`docs/versionamento.md`).
3. `Bancada.from_env`: baseline, energiza, **checagem da cadeia** (log `Cadeia de medição OK: fonte X Vrms, CH1 Y Vrms (razão Z)`; razão fora de 1 ± 0,10 aborta antes da primeira classe).
4. Por classe: pré-validação (capturas que não cabem são **puladas** e logadas), captura, validação física, gravação. Resumo final: quantas classes OK, quais falharam, capturas puladas/descartadas/inválidas.
5. Saída desligada ao fechar. **Confira OUTPUT OFF no painel da AMETEK.**
6. Com `set html on` / `set recalibracao on`, os ganchos rodam depois (falha só avisa); ver §9.

Usar as partes da seção 5 do {doc}`roteiro-bancada`. Com um perfil e os padrões: `run 01-05,18-20`, `run 06-11` e `run 12-17`. Com `set perfil todos`: `run 01-05,17-19`, `run 06,10`, `run 11,12`, `run 13,14`, `run 15,16` e `run 07-09,20`. Cada `run` cria uma conexão nova (`Bancada.from_env`, chamado por `SessaoCLI._executar_scripts`). No plano documentado cada conexão fica em até **216 gravações a 60 Hz**, abaixo das ~280 da ocorrência histórica de trava. Conferir `status` e a confirmação antes de cada parte; mudar capturas, níveis, perfil, frequência ou incluir a 05 por TRACe exige recalcular o orçamento. A contagem é uma estimativa de software, não garantia física nem causa comprovada da trava. O CLI recusa seleções estimadas acima de 216 antes de confirmar ou abrir instrumentos. O driver também aplica esse orçamento às tentativas cumulativas, inclusive diagnósticos e envios de resultado incerto. Se a captura inteira não cabe no saldo, ela é recusada antes de alterar a programação; a bateria termina sem retry nessa conexão. Reutilização de TRACe idêntica só economiza orçamento após confirmar o catálogo. Preservar os diagnósticos anteriores à campanha no roteiro.

A referência histórica com um perfil é 50 capturas e 468 gravações a 60 Hz (390 a 50 Hz). A CLI avisa sobre esse volume; isso não torna `run all` o fluxo recomendado. Investigar a causa com dados reais, sem ensaio cego até travar.

## 6. Limites por tensão e frequência

Resumo do que `scripts/relatorio_limites_bancada.py` informa (executado em 2026-10-12, seed padrão, perfil `literatura`, 3 capturas padrão, sorteio ligado). Detalhes e regra: `docs/limites_e_calibracao.md`.

| Condição | Resultado |
|---|---|
| 127 V / 60 Hz e 127 V / 50 Hz | as 20 classes rodam todas as capturas, sem redução |
| 230 V / 50 Hz | 03 pulada; 14 pulada (0/3); 13 roda 2/3; 06, 07, 09, 13, 17, 20 com distúrbio reduzido |
| 220 V / 60 Hz (sem tabela de calibração) | previsão conservadora: 02, 03, 04, 05, 14, 18, 19 puladas; 06, 09, 13 parciais; várias reduzidas |

Condição sem tabela mostra um aviso no log; calibrar rodando a bateria e depois `scripts\recalibrar_extremos.py <sessao> --gravar` (ou `set recalibracao on`).

## 7. Se algo falhar

- **Falha de UMA classe** (RMS fora de tolerância, timeout de trigger, exceção em `gerar()`): `executar_bateria` tenta até 3 vezes (`MAX_TENTATIVAS_POR_CLASSE`, `mestre.py:1084`) chamando `recuperar_estado_seguro()` entre as tentativas; erros determinísticos (`ParameterOutOfBoundsError`, `ValidacaoFisicaError`, `PicoFisicoExcedidoError`) não são retentados; depois registra `FALHOU` e segue. Não é motivo para parar.
- **Capturas puladas, descartadas, inválidas e classes que falharam** não param a bateria (pula e segue) e ficam em `<sessao>/falhas.json` (`docs/metadata.md`). Para refazer só elas: `run falhas` (ou `rerun <pasta> <id>`), com confirmação nova.
- **Orçamento de 216 TRACe esgotado** (`LimiteEscritasTraceError`, v1.15): a conexão é encerrada com ABORt + OUTPUT OFF **confirmado** (`Bancada._encerrar_conexao_por_orcamento`; sem confirmação vira `FalhaFatalDeInstrumento`), o resto da classe corrente e as classes seguintes vão para `falhas.json` como `nao_executada_orcamento` e o resumo as mostra como `NÃO EXECUTADA`. Nada é reconectado nem energizado sozinho: confira o painel e rode `run falhas` (confirmação digitada nova). Antes, a bateria abortava sem registrar o que faltou.
- **Falha de infraestrutura** (`CommunicationError`, `FalhaFatalDeInstrumento`, `CadeiaDeMedicaoError`): aborta tudo. Procedimento:
  1. Confirmar fisicamente **OUTPUT OFF** no painel.
  2. **Não** executar de novo automaticamente.
  3. Entregar ao responsável os logs: para `run`/`run all`, `resultados\sessao_<timestamp>[_runNN]\sessao.log` e `scpi_transcricao.log` da pasta mais recente; para `comm`/`trigger`/`lowvoltage`/`native`, o `logs\preflight_new-<etapa>-<timestamp>.log` mais recente (esses comandos não criam pasta de sessão; a CLI grava o mesmo log que `python logica\preflight_new.py --native-commands`, via `preflight_new.run_com_log`). O arquivo `logs\startup-bench-*.log`, citado em documentos antigos, **não é mais gerado por nenhum código**.
  4. Não remover validações de IDN, timeout, 6000 pontos ou SCPI para "fazer passar".
- **Ctrl+C**: interrompe quando a chamada VISA em curso retorna (até ~15 s), a saída é desligada ao fechar a conexão, a CLI volta ao prompt (`mestre.py:393-429`, `cli.py:768-774`). Em emergência vale o E-stop.
- Captura de corrente fica **desligada** (`CAPTURE_CURRENT=0`); não ativar sem fator da probe de corrente e corrente-base fornecidos.

## 8. Depois da sessão

- Revisar o resumo e `sessao.log`; capturas `validacao_fisica.ok=false` estão gravadas e marcadas.
- Se `set recalibracao on` mudou `calibracao_extremos.json`: `git diff`, rodar `tests.test_offline`, commitar antes da próxima sessão (a árvore fica suja). Reverter: §9.
- Ferramentas offline sobre a pasta: `docs/dataset.md`.
- Empacotar para transporte: `scripts\package_windows.ps1`.

## 9. Relatório HTML e recalibração ao fim do run

Os dois ganchos são OFF por padrão (`set html`, `set recalibracao`; `logica/cli.py:264-266`). Rodam **depois** de a saída estar OFF e a conexão fechada (`cli.py:864`, `_fim_da_sessao`), nessa ordem: recalibração, depois HTML (`cli.py:871-881`). Nenhuma falha aqui derruba a CLI nem conta como falha de experimento: avisa e segue.

**Quando roda.** No fim de `run <NN>`, só se a classe terminou OK (`cli.py:805-807`). No fim de `run all` e de `run <lista>`, mesmo quando uma classe falhou por experimento (`cli.py:857-859`). **Não** roda quando a bateria aborta por infraestrutura (`CommunicationError`, `FalhaFatalDeInstrumento`).

### Relatório HTML (`set html on`)

- **O que gera:** (1) `<sessao>/sem_margem/`, a janela nominal de cada captura sem a folga de 20/50 ms (`logica/recortar_margem.py`, `PASTA_SAIDA_PADRAO`; os originais não são tocados); (2) `<sessao>/relatorio_<sessao>.html`, HTML autocontido com as figuras em base64 (`logica/relatorio_html.py:672`, `gerar_relatorio_recortado`). O hook não confere `BENCH_MODE`: gera também no simulado.
- **Onde fica:** na pasta da sessão, `resultados\sessao_<timestamp>[_runNN]\relatorio_<sessao>.html`.
- **Custo:** tempo (o próprio `set html` avisa que pode levar minutos numa bateria completa) e tamanho. Acima de 20 MB (`TAMANHO_EMAIL_MB`, `relatorio_html.py:76`) a CLI avisa que o arquivo pode não passar como anexo de e-mail. Para reduzir: `--classes`, `--max-capturas-por-classe` ou `--dpi 80`.
- **Quantas capturas:** sem `--capturas` e sem `--max-capturas-por-classe`, o relatório mostra só as **3 primeiras** de cada classe e perfil (`logica/relatorio_html.py`, `ler_capturas`, com aviso; vale para formatos legado/atual e bancada/simulação, sem alterar os arquivos originais). Para outra quantidade, rodar à mão.
- **Falha:** só avisa. Para refazer: `python logica\relatorio_html.py <sessao>`.

### Seleção do relatório à mão

`python logica\relatorio_html.py <pasta da sessão> [opções]` (`relatorio_html.py:699-722`):

| Opção | Efeito |
|---|---|
| `--classes 02,05` | só essas classes (pelo prefixo `NN_`) |
| `--perfis norma,fronteira` | só esses perfis (`norma`, `literatura`, `fronteira`; padrão: todos os do arquivo) |
| `--versoes medida,modelo,programada` | séries desenhadas; a primeira é o traço principal, as outras são sobrepostas. Padrão: `medida` |
| `--capturas 02-0001,1-3` | por id (`02-0001`) ou por posição dentro da classe e do perfil (`3` ou `1-3`) |
| `--max-capturas-por-classe N` | limite por classe e perfil (substitui o padrão de 3) |
| `--snr 30` | usa `snr_30db/` (dados com o ruído acrescentado) em vez dos dados sem ruído; o arquivo vira `relatorio_<sessao>_snr30db.html` |
| `--dpi 80`, `--detalhes N`, `--titulo`, `--descricao`, `--saida` | aparência e destino; `--dpi` menor reduz o tamanho |

Exemplo: `python logica\relatorio_html.py resultados\sessao_X --classes 02,05 --perfis norma --versoes medida,modelo --max-capturas-por-classe 5`.

**Capturas compartilhadas entre perfis.** Com `set perfil todos`, as classes que não dependem do perfil (com sorteio ligado: 01, 04, 07, 08, 09, 17, 18 e 19; com `set sorteio off` entra também a 16) são capturadas uma vez, sob `literatura`. `norma` e `fronteira` apontam para essa mesma captura no metadata (`captura_compartilhada`, `compartilhada_com_perfis`, `sha256_captura`; `docs/dataset.md` §2). O HTML mostra a captura **uma vez**, rotulada "(= norma, fronteira)", com o SHA-256 (`relatorio_html.py:338-350`, `:472-483`). Quando o perfil de origem não está na seleção (ex.: `--perfis norma`), a figura aparece sob o perfil pedido, marcada como compartilhada.

### Recalibração automática (`set recalibracao on`)

- **O que faz:** só em bancada (`BENCH_MODE`); no simulado não faz nada (`cli.py:895-900`). Recalcula os fatores de extremo da sessão que acabou (`scripts/recalibrar_extremos.py`, `recalibrar(..., automatico=True)`) e **grava** `logica/calibracao_extremos.json`, arquivo rastreado pelo git.
- **Regras, sempre:** nunca diminui um fator; nunca usa `--substituir`; **não cria tabela** para condição nova (avisa e manda rodar à mão). Cada fator que mudou sai destacado (`[tabela] classe NN: antes -> depois (n capturas)`).
- **Sem a cópia da calibração na sessão, não roda** (`cli.py:895-909`).
- Depois, conferir com `git diff`, rodar `tests.test_offline` e commitar antes da próxima sessão de coleta.

**Como reverter.** A cópia da calibração em uso no início da sessão fica em `<sessao>\calibracao_extremos.json` (`mestre.py:221-226`); o SHA-256 dela está em `sessao.json` e em cada captura (`calibracao_extremos_sha256`).
1. Copiar a cópia de volta: `copy resultados\sessao_<timestamp>\calibracao_extremos.json logica\calibracao_extremos.json` (ou `git checkout -- logica/calibracao_extremos.json`, se o arquivo já estava commitado antes da sessão).
2. Reiniciar a CLI. O aviso da própria CLI diz que os runs seguintes já usam os fatores novos (`cli.py:653-657`); reiniciar evita dúvida. NÃO VERIFICADO: se a CLI relê o JSON a cada run.

**Linha de comando equivalente** (offline; não energiza nada):

```powershell
env\Scripts\python.exe scripts\recalibrar_extremos.py resultados\sessao_A [resultados\sessao_B ...]          # só mostra o que mudaria
env\Scripts\python.exe scripts\recalibrar_extremos.py resultados\sessao_A --gravar                         # grava; não diminui fator
env\Scripts\python.exe scripts\recalibrar_extremos.py resultados\sessao_A --gravar --arquivo F             # outro arquivo
```

`--substituir` (só com `--gravar`) deixa gravar fator menor que o atual e enfraquece a pré-validação; não é o caminho normal. A linha de comando pode criar tabela para condição nova; o modo automático, não.

