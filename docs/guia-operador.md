# Guia do operador

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Conferido contra `cli.py`, `start_bench_windows.ps1` e `mestre.py` em 2026-10-16 (`main` em `fa82f49`). {bdg-warning}`NÃO VERIFICADO` na bancada com o código da v1.15 (P-01). O detalhe de cada comando está em {doc}`operacao`; o roteiro da próxima campanha, em {doc}`roteiro-bancada`.

:::{danger} Segurança
Você é a última barreira. Antes de digitar qualquer confirmação, olhe a **probe, os cabos, os disjuntores entre a fonte e a probe, o E-stop e o equipamento sob teste**. Ao fim de qualquer comando ou falha, confira **OUTPUT OFF** no painel da AMETEK. Não invente o fator da probe: é o escrito na chave dela.
:::

**Pergunta:** o que faço, em ordem, para coletar uma sessão sem risco? **Resposta:** ligue e confira a ligação física, rode `scripts\START_BENCH.cmd` (ele pergunta o fator exato da probe, a tensão e a frequência), use a CLI `bancada>` na ordem `comm` → `trigger` → `native` → `run`, digite cada confirmação exatamente como pedida, e termine conferindo `OUTPUT OFF` e o `git status`. Falha de **uma classe** não é motivo para parar; falha de **infraestrutura** é.

```{mermaid}
flowchart TD
    A["1. ligação física<br/>(USB COM10, USB do Keysight, BNC, probe no CH1)"] --> B["2. git status limpo<br/>(sessão sai de commit limpo)"]
    B --> C["3. START_BENCH.cmd<br/>probe, tensão, frequência"]
    C --> D["4. comm → trigger"]
    D --> E["5. native (ENERGIZAR-COMANDOS)"]
    E --> F["6. run all | run lista | run NN<br/>(EXECUTAR-...)"]
    F --> G["7. OUTPUT OFF no painel"]
    G --> H["8. resumo, sessao.log, git diff se recalibrou"]
    F -->|"falha de infraestrutura"| X["OUTPUT OFF no painel<br/>não repetir sozinho<br/>entregar os logs"]
```

## 1. Antes de ligar (ligação física obrigatória)

- **AMETEK MX30-3Pi** por **USB**, vista como `COM10` (115200 baud). **Não** conecte o DB9 RS-232 ao mesmo tempo; **não** deixe o MX GUI aberto (ele segura a porta).
- **Keysight DSO-X 4034A** por USB (`USB0::0x0957::0x17A4::MY59240844::0::INSTR`).
- **Cabo BNC**: AMETEK *Trigger Out* → Keysight *EXT Trigger*. Sem ele o osciloscópio nunca dispara.
- **Probe diferencial de tensão no CH1**, entre fase A e neutro, com o fator **exato** da chave.
- **Disjuntores fechados** entre a fonte e a probe: em 07/10/2026 um disjuntor aberto fez 20 classes serem medidas a cerca de 0,45 do esperado, sem erro de software. A checagem da cadeia de medição (razão CH1/fonte dentro de 10 %) existe por isso.

## 2. Iniciar

```powershell
cd C:\caminho\do\repositorio
scripts\START_BENCH.cmd
```

O script pergunta: **fator da probe**, **tensão rms fase-neutro** (até 270 V; 380 V é tensão de linha, digite 220) e **frequência**. Esses valores viram constantes do processo; para mudar, reinicie. Ele fixa os limites (300 Vrms, 415,8 Vp), carrega `ARM_OUTPUT=NO` e abre a CLI. **Toda sessão sai de commit limpo**: o metadata grava o commit e se a árvore está suja; commite tudo (inclusive arquivos novos e a calibração recalibrada) e reinicie a CLI depois de commitar.

## 3. A sequência de comandos

| Passo | Comando | Energiza? | Confirmação digitada |
|---|---|---|---|
| 1 | `comm` | não | nenhuma |
| 2 | `trigger` | não | nenhuma |
| 3 | `native` | sim | `ENERGIZAR-COMANDOS` |
| 4 | `lowvoltage` (opcional: só se mexeu em fiação ou probe) | sim, tensão base | `ENERGIZAR-TESTE` |
| 5 | `run <NN>`, `run <lista>`, `run all` | sim | `EXECUTAR-CLASSE-NN`, `EXECUTAR-CLASSES-<lista>`, `EXECUTAR-20-CLASSES` |

Todas **case-sensitive**. `help` imprime a referência completa; `status` e `list` mostram o estado e as capturas por classe sem energizar. Os comandos `set` valem a partir do **próximo** `run`.

**Ordem recomendada em uma sessão do zero:** `comm` → `trigger` → `native` → `run ...`.

## 4. Como rodar sem passar da trava da fonte

A fonte travou por volta da 280.ª gravação de TRACe de uma conexão em 16/09/2026. Com os padrões, `run all` planeja **50 capturas** e **468 gravações de TRACe a 60 Hz** (390 a 50 Hz; conferido offline em 2026-10-16); com `set perfil todos` chega a 1116. O orçamento operacional é de **216 gravações TRACe por conexão** (`LIMITE_ESCRITAS_TRACE_CONEXAO`): a CLI **recusa**, antes de abrir qualquer instrumento, um `run` cuja estimativa (sem retentativas) passe de 216, e, se o orçamento esgotar durante a conexão (retentativas também consomem), a bateria desliga a saída com confirmação, encerra a conexão e registra o que faltou em `falhas.json` para `run falhas` (v1.15). Para ficar abaixo, **divida em listas**: `run 01-07` e depois `run 09-20` (cada `run` abre conexão nova). O roteiro usa listas de até 216 gravações por conexão. {bdg-danger}`PENDENTE P-23`

### Rodar só o que deu problema

Toda sessão grava `falhas.json` quando algo não saiu: capturas puladas, descartadas, inválidas, classes que falharam e as que não rodaram porque o orçamento de TRACe esgotou. Para refazer só isso, **sem repetir o que já está bom**:

1. Confira `OUTPUT OFF` no painel. Mantenha a mesma tensão, frequência, `set p09`, limites do ambiente e calibração de extremos da sessão de origem (se diferirem, a CLI recusa e diz o que mudar; tensão/frequência exigem reiniciar o `START_BENCH`; calibração: copie a `calibracao_extremos.json` da sessão de origem).
2. `run falhas` (última sessão desta CLI) ou `run falhas <pasta_sessao>`; para itens escolhidos, `rerun <pasta_sessao> 10-0003 02`.
3. A CLI mostra o que vai repetir e as gravações de TRACe só disso, e pede a confirmação normal (`EXECUTAR-CLASSE-NN` ou `EXECUTAR-CLASSES-...`), digitada por você.
4. O resultado vai para uma **sessão nova**; `sessao.json` e cada captura têm `rerun_de` apontando para a origem. As capturas repetem a mesma seed, perfil e nível.

Capturas puladas por capacidade da fonte ou pela pré-validação não entram no `run falhas` e são retiradas de um `rerun` (só elas = recusa): na mesma condição seriam puladas de novo.

## 5. O que olhar durante e depois

1. Um aviso em destaque (linhas de `!`) diz **árvore git suja**: a sessão não é reproduzível só pelo commit.
2. `Cadeia de medição OK: fonte X Vrms, CH1 Y Vrms (razão Z)` antes da primeira classe. Razão fora de 1 ± 0,10 aborta.
3. Capturas **puladas** pela pré-validação (extremo previsto acima do teto), **descartadas** por erro e **inválidas** pela validação física aparecem no resumo; as inválidas estão gravadas e marcadas.
4. Ao fim: **OUTPUT OFF no painel**; resumo `N/20 classes OK`; `sessao.log` e `scpi_transcricao.log` na pasta da sessão.
5. Se `set recalibracao on` mudou `calibracao_extremos.json`: `git diff`, `tests.test_offline`, commitar antes da próxima sessão ({doc}`medicao/recalibracao`).

## 6. Se algo falhar

| O que aconteceu | O que fazer |
|---|---|
| **uma classe** falhou (RMS fora de tolerância, timeout de trigger, exceção em `gerar()`) | nada: a bateria já tentou até 3 vezes, registrou `FALHOU` e seguiu |
| orçamento de TRACe esgotado (resumo com `NÃO EXECUTADA`) | a saída já foi desligada e conferida; confira `OUTPUT OFF` no painel e rode `run falhas` com confirmação nova (nada reconecta sozinho) |
| captura **pulada** pela pré-validação | esperado em tensões altas ou sem tabela de calibração; veja `relatorio_limites_bancada.py` antes ({doc}`medicao/recalibracao`) |
| `CommunicationError`, `FalhaFatalDeInstrumento`, `CadeiaDeMedicaoError` | **pare**: confirme `OUTPUT OFF` no painel, **não repita sozinho**, entregue `sessao.log` e `scpi_transcricao.log` (ou o `logs\preflight_new-*.log` mais recente) a quem diagnostica |
| fonte muda ou painel travado | `OUTPUT OFF` pelo painel; depois da 280.ª gravação numa conexão, suspeite da trava ({doc}`quirks`, A3) |
| Ctrl+C | interrompe quando a chamada VISA em curso retorna (até cerca de 15 s) e a saída é desligada ao fechar a conexão; em emergência vale o E-stop |

Nunca remova validações de IDN, timeout, 6000 pontos ou SCPI para "fazer passar" ({doc}`seguranca`).

## 7. Onde ler mais

{doc}`operacao` (todos os comandos, ligação, relatório HTML e recalibração), {doc}`configuracao` (variáveis de ambiente), {doc}`diagnostico` (ferramentas), {doc}`roteiro-bancada` (campanha pendente), {doc}`quirks` (comportamentos medidos).
