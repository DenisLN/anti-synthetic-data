## Análise do orquestrador

- Implementação completa? Sim: ROTEIRO_BANCADA.md na raiz (10 blocos, tabela de decisão com 28 linhas, campanha em partes ≤ 216 gravações por conexão, checklist), comandos conferidos por grep; merge limpo.
- Pendências do usuário: escolher um perfil ou 'todos', a frequência da campanha, e se ACDC a 230 V entra. Achado: set capturas é piso (max), então o 1.º uso do retrieve vai na 1.ª captura da 08.
- Critério de Parada: atendido. Classificação: com pendências (escolhas do dia).

---

# Relatório: ASD: Roteiro da Próxima Bancada

Branch do worktree: `worktree-agent-af74fc1d55f009a71`. Merge prévio de `claude/specs-v1-15-review-3w2bgl` feito (HEAD já em `860b35a`, spec 25). Commit: `09c89c2` (docs: roteiro da próxima bancada). Arquivos: `ROTEIRO_BANCADA.md` (raiz) e seção nova no fim de `CHANGELOG/v1.15.md`. Nenhum doc de `docs/` nem `AGENTS.md` tocado.

Pedido que parece equivocado em um ponto (uma frase): os relatórios 16 e 20 mandam testar `set diagnostico retrieve` com `set capturas 1`, mas `set capturas N` só impõe um piso (`Config.capturas`, `mestre.py:789-804`: `max(N, padrão da classe)`), então não existe captura TRACe isolada; o roteiro usa a primeira captura da 08 (que já precisa ser recapturada) como teste, com o painel à vista.

## Missão, item a item

**Item 1 — Escrever `ROTEIRO_BANCADA.md` na raiz do repositório, em blocos na ordem de execução (preparação: `git pull`, commit limpo, `tests.test_offline` no Windows; `comm`/`trigger`/`lowvoltage`/`native`; diagnóstico offline das sessões de 07/10 com `diag_ciclos_trace.py`; `diag_marcadores_trace.py`; `diag_acdc_amplitude.py`; recaptura da 08 e a 09; 07/17 com recalibração; verificações do sorteio, 05/07/17/18 via `verificar_sessao_bancada.py`; campanha por partes), cada bloco com comandos exatos (PowerShell, `C:\Users\denis\TCC\code`), confirmação digitada, tempo estimado, o que conferir e critério de seguir/parar.**
- Status: CUMPRIDO
- Explicação: `ROTEIRO_BANCADA.md`, blocos 1 a 10 (seção 2), mais regras fixas (seção 0) e visão geral com tempo e confirmação por bloco (seção 1). Cada bloco traz comandos PowerShell, confirmação digitada, "Conferir", "Seguir se/Parar se" e tempo. Decisões de organização: (a) a verificação do sorteio (02/03/04, 05, 18, 19, 01) é a Parte 1 da campanha (Bloco 8, `run 01-05,18-20`), para não recapturar nativas; (b) as sessões de 07/17 com recalibração não valem como dado (árvore suja até o commit do JSON), a campanha recaptura 07 e 17 depois do commit; (c) a 09 com `set capturas 6` (≈18 % das capturas caem dentro do evento em 100 ms, relatório 18) e a 08 com retrieve ligado; (d) sessão A em 50 Hz (08/09) e sessão B em 60 Hz (campanha), com nota para campanha a 50 Hz; (e) `lowvoltage` só se fiação/probe foram mexidas; (f) 230 V no Bloco 5 é opcional. Os critérios de aprovação vêm dos relatórios 15, 16, 18, 20, 21, 25, 26 e dos pendentes `classe08_fronteira`, `acdc_amplitude`, `sorteio_inicio_fase`, `compostas_sorteadas`. Comandos conferidos no código: seção 7 do roteiro (confirmações em `logica/cli.py:691,706,750,762,823`, `scripts/diag_marcadores_trace.py:80`, `scripts/diag_acdc_amplitude.py:68`; flags por `add_argument` dos scripts; as 6 listas normalizadas geradas por `normalizar_lista_classes`).

**Item 2 — Incluir uma tabela de decisão: para cada resultado possível do diagnóstico (marcadores, ACDC, 08/09, 07/17), o que muda na campanha do mesmo dia.**
- Status: CUMPRIDO
- Explicação: seção 3 do roteiro, 28 linhas (ciclos offline, marcadores, retrieve, ACDC, 08, 09, 07/17, suíte Windows, VMAX/VMIN das 10/11/12/16), cada uma com leitura e efeito na campanha (ex.: ACDC com a linha 3 ≈ 1,000 tira a 19 da Parte 1; marcadores com troca de passo suspende as Partes 2 e 3; 08 com pico > 374,2 V sai da lista; 07/17 que ainda reprovam saem de `06-11`/`12-17`). A coluna é proposta, não decisão; nenhuma linha afrouxa tolerância ou limite.

**Item 3 — Incluir o plano da campanha em partes com a conta de gravações de TRACe por parte (< 250 por conexão, usando `capturas_efetivas_da_classe`/a estimativa da CLI; conferir os números rodando a estimativa offline) e o tempo estimado (≈ 2 s por ciclo de TRACe, ≈ 2,5 s por captura nativa, 18 s por conexão, ~3 s por slot TRACe na 1.ª captura de cada conexão), para um perfil e para `set perfil todos`.**
- Status: CUMPRIDO
- Explicação: seções 4 e 5. Números obtidos rodando offline `mestre.capturas_efetivas_da_classe` (por perfil, com `perfis.plano_de_perfis`) e `SessaoCLI._capturas_das_classes` com `BASE_VOLTAGE_RMS=127`, `GRID_FREQUENCY_HZ=60|50` (scripts `est23.py`, `est23b.py`, `est23c.py` no scratchpad). Resultado: um perfil, 60 Hz/50 Hz: Parte 1 `01-05,18-20` 36/30, Parte 2 `06-11` 216/180, Parte 3 `12-17` 216/180, total 468/390 (bate com a CLI e com `docs/operacao.md`). `todos`: 6 partes (`01-05,17-19` 36/30; `06,10`, `11,12`, `13,14`, `15,16`, `07-09,20` com 216/180 cada), total 1116/930 (bate com o relatório 25). Maior conexão: 216 < 250. Tempos pelo modelo pedido, com coluna x1,5 para planejamento: um perfil 18,8 min (28,1) a 60 Hz e 15,9 min (23,8) a 50 Hz; `todos` 43,3 min (65,0) e 36,5 min (54,8). Slots: min(ciclos, 12) x 3 s.

**Item 4 — Incluir o checklist de entrega ao fim do dia (arquivos a copiar, `git status`, recalibração conferida com `git diff`, relatório HTML).**
- Status: CUMPRIDO
- Explicação: seção 6 do roteiro: OUTPUT OFF, `git status`, `git log`/`git diff` de `logica\calibracao_extremos.json` e cópia da sessão, suíte, conferência de `git_commit`/`git_sujo` por sessão (one-liner), HTML (`recortar_margem.py` + `relatorio_html.py` ou `set html on`), lista do que copiar (`resultados\sessao_*` inteiras, `logs\diag_*`, `verificar_parte1.json`, `preflight_new-*.log`), anotações e pendências.

**Item 5 — Registrar numa seção nova no fim de `CHANGELOG/v1.15.md` que o roteiro existe (uma linha).**
- Status: CUMPRIDO
- Explicação: seção "Roteiro da próxima bancada (2026-10-15, spec 23, mesma versão)" no fim de `CHANGELOG/v1.15.md`, com uma frase (sem as cinco subseções do modelo; a spec pediu uma linha).

## Critério de Parada
Atendido. O roteiro cobre os 4 itens do pedido; os comandos e confirmações existem no código (tabela da seção 7 do roteiro; greps abaixo); as contas de TRACe por parte ficam em 36 a 216 (< 250). Suíte: `TMPDIR=/tmp/claude-0/tmpt /tmp/claude-0/venv/bin/python -m unittest tests.test_offline` -> `Ran 497 tests in 67.805s`, `OK (skipped=2)` (0 falhas; os 2 pulados são os SHA-256 exatos, só no Windows).

### Verificação: comando/confirmação -> evidência
| Citado no roteiro | Evidência (Grep/ls no worktree) |
|---|---|
| `ENERGIZAR-TESTE` | `logica/cli.py:691` |
| `ENERGIZAR-COMANDOS` | `logica/cli.py:706` |
| `EXECUTAR-CLASSE-<NN>` | `logica/cli.py:762` |
| `EXECUTAR-CLASSES-<lista>` | `logica/cli.py:750` |
| `EXECUTAR-20-CLASSES` | `logica/cli.py:823` |
| `ENERGIZAR-MARCADORES` | `scripts/diag_marcadores_trace.py:80` |
| `ENERGIZAR-ACDC` | `scripts/diag_acdc_amplitude.py:68` |
| `status`, `list`, `comm`, `trigger`, `lowvoltage`, `native`, `run`, `set` | `logica/cli.py:368,510,676,681,686,702,717,527` |
| `set diagnostico retrieve`, `set perfil`, `set recalibracao`, `set html` | `logica/cli.py:543-544,616,645,659` |
| listas `07,17` etc. e normalizações | `parsear_lista_classes` (`cli.py:209`), `normalizar_lista_classes` (`cli.py:235`); saída de `norm23.py`: `07,17`, `01-05,18-20`, `01-05,18,20`, `01-05,17-19`, `06-11`, `12-17`, `06,10`, `11-12`, `13-14`, `15-16`, `07-09,20`, `06-07,09-11`, `06,08-11`, `12-16` |
| scripts e módulos | `ls` confirmou `scripts/START_BENCH.cmd`, `diag_ciclos_trace.py`, `diag_marcadores_trace.py`, `diag_acdc_amplitude.py`, `verificar_sessao_bancada.py`, `recalibrar_extremos.py`, `package_windows.ps1`, `setup_windows.ps1`, `logica/analisar_sessao.py`, `recortar_margem.py`, `relatorio_html.py`, `modelo_lista_fonte.py` |
| flags `--classes`, `--probe`, `--vrms`, `--hz`, `--frequencias`, `--variantes`, `--testar-compensacao`, `--json`, `--dpi`, `--sem-forma-bancada` | `add_argument` em cada script (conferidos por Grep) |
| campos de metadata dos one-liners | `mestre.py:2705` (`id_captura`), `:1783` (`indice_trigger`), `:1776` (`escritas_trace_na_conexao`), `:1959` (`pico_medido_v`, `vale_medido_v`), `:2727` (`extremo_previsto_v`), `:2236-2259` (`diagnostico_trace.desvio_max/erro`), `sinais.py:445-455` (`crista_*`, `thd_*`), `experimentos_waveform/08.py:157,195-197` |

## Pendências que exigem o usuário
- Escolher o modo da campanha (um perfil ou `set perfil todos`) e a frequência (o roteiro assume 60 Hz, com nota para 50 Hz).
- Decidir se a Parte 230 V do Bloco 5 (ACDC) entra no dia.
- Ler o fator na probe física e digitar todas as confirmações (nada foi automatizado).
- Aprovar as propostas da tabela de decisão e os limiares do verificador (10 graus, 2 ms, 2 amostras), todos sem dado de bancada.
- Commit/push do roteiro (commit local apenas; sem push).

## Limitações de escopo
- Sem bancada: nenhum tempo, formato de sessão antiga em `diag_ciclos_trace.py` nem resposta de `TRACe:DATA?` foi verificado; os tempos são o modelo pedido (nenhuma bateria foi cronometrada).
- "Não editar docs" impediu corrigir em `docs/operacao.md` e `AGENTS.md` o que o roteiro contradiz ou atualiza (achados abaixo).

## A missão resolve o contexto?
Sim: a ordem diagnóstico-antes-da-campanha, as contas de TRACe por conexão e os pontos de decisão estão no roteiro; o conteúdo físico (mecanismo da cópia, ganho ACDC, toque nos entalhes) continua dependendo de dados da bancada.

## Achados
- (média) `set capturas 1` não isola uma captura: o piso é `max(N, padrão)` (`mestre.py:804`); os relatórios 16 e 20 sugerem isso. Corrigido no roteiro (primeira captura da 08 com retrieve). Convém corrigir `docs/diagnostico.md` §1.1 e a nota do CHANGELOG da spec 16.
- (média) `docs/operacao.md` §7 diz que `executar_bateria` "tenta até 3 vezes" (`MAX_TENTATIVAS_POR_CLASSE`), enquanto `AGENTS.md` diz "sem tentar de novo sozinho" diante de infraestrutura; não conferi qual vale em cada tipo de erro. O roteiro diz só que falha de experimento não é infraestrutura. NÃO VERIFICADO (fora do escopo).
- (média) Com `set perfil todos` a CLI exige lista de classes para caber em < 250 gravações: uma classe TRACe dependente do perfil custa 108 (60 Hz) e 90 (50 Hz), então no máximo duas por conexão; `run all` com `todos` (1116) não é executável numa conexão. O aviso da CLI só sugere "run <NN>" por partes.
- (baixa) A 05 por TRACe (nível de 30 %) não entra na estimativa de gravações da CLI (a 05 tem 1 captura padrão e 0 gravações); com `set capturas` mais alto, recontar com `status`. NÃO VERIFICADO.
- (baixa) `run 08` e `run 09` isolados usam `_run_uma` (`EXECUTAR-CLASSE-NN`), que não passa por `executar_bateria`; `run 08-09` usaria `EXECUTAR-CLASSES-08-09`. O roteiro usa o primeiro, para poder ligar/desligar `set capturas` entre as duas.
- (baixa) O CHANGELOG fechado cita "dono"/"professor" em textos de outras specs; o roteiro não usa essas palavras nem ".tex" (grep vazio).
- (info) A suíte leva ~68 s no Linux (497 testes). Scripts auxiliares: `est23.py`, `est23b.py`, `est23c.py`, `norm23.py` no scratchpad.
- NÃO VERIFICADO: que `diag_ciclos_trace.py` carrega as sessões de 07/10 (caminho `.npz` bruto + `reconstruir_versoes` não foi exercitado com dado real, relatório 15); que a COM10 fica livre entre comandos da CLI (o roteiro mantém "fechar a CLI" para os scripts `diag_*`, como os relatórios mandam).
