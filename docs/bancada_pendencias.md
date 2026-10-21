# Visita à bancada: fechamento das pendências físicas

Roteiro de **uma** visita que gera a evidência para P-01, P-02, P-03, P-05, P-06, P-07, P-08, P-10, P-16, P-17, P-18, P-19, P-21, P-22, P-23, P-28 e P-31, com P-26 como pré-condição a decidir antes de energizar. A sequência, os diagnósticos e os critérios são os de {doc}`roteiro-bancada` (arquivo `ROTEIRO_BANCADA.md` da raiz; "Bloco N" e "seção N" abaixo remetem a ele). Este documento não os reescreve: só os organiza por pendência. Estado e protocolo: {doc}`PENDENCIAS_TRACKER`. Critérios completos: {doc}`execucao_pendencias`. Operação da CLI: {doc}`operacao`.

:::{warning}
Nenhum passo abaixo encerra pendência por si. A visita **gera evidência**; o fechamento é decidido pelo coordenador e pelo responsável com a evidência em mãos. Simulação não é medição. Diagnóstico vem antes da campanha: não mude a ordem dos Blocos 1 a 10.
:::

## Atalho: a visita inteira num comando

No PC da bancada: **`scripts\VISITA_BANCADA.cmd`** (atalho na área de trabalho). Ele pergunta o fator da probe e conduz, na ordem, todos os blocos abaixo, inclusive 8-A, 10-A, 10-B e as campanhas por condição (P-26, com a calibração P-21 de 220 V e 33 V), e termina com o fechamento (`fechamento.json`) e o commit das evidências. O comando:

- muda a tensão e a frequência sozinho, por etapa;
- confere a segurança depois de cada sessão;
- para em falha de infraestrutura;
- pergunta se você quer rodar de novo só as capturas que falharam.

**Você continua digitando a confirmação de cada etapa que energiza.** Pode parar em qualquer pausa e rodar de novo outro dia: ele retoma de onde parou. `VISITA_BANCADA.cmd --plano` mostra as etapas e o estado. Detalhes: `scripts/visita_bancada.py`.

## Limites inegociáveis (resumo; texto completo em `AGENTS.md`)

- `AMETEK_PORT=COM10` e `AMETEK_BAUDRATE=115200`, fixos e validados; não trocar.
- Não enfraquecer validações de IDN, timeout, 6000 pontos ou erros SCPI; não alterar `max_voltage_rms`, `max_peak_v`, `max_current_a`; `gerar()` e fixtures intocados.
- **Confirmações digitadas, case-sensitive, são sempre do operador e nunca são automatizadas** (nenhum script, macro ou agente digita `ENERGIZAR-...` ou `EXECUTAR-...`). Antes de digitar: probe, cabos, E-stop, EUT e disjuntores entre a fonte e a probe fechados.
- Captura de corrente desligada (`CAPTURE_CURRENT=0`).
- Falha de infraestrutura (serial caiu, `CommunicationError`, OUTPUT não confirmável, `FalhaFatalDeInstrumento`): confirmar OUTPUT OFF no painel, **não repetir**, entregar os logs (roteiro, seção 0).

## Pré-condições (antes do Bloco 1)

| # | Item | Como conferir | Alimenta |
|---|---|---|---|
| 1 | Commit limpo **para cada bloco que coleta**, incluindo arquivos novos em `scripts/`, `logica/`, `experimentos_*` (o `git_sujo` os conta); os scripts novos já estão commitados no branch. No Bloco 7 o commit da calibração gera **novo SHA**: sessões do Bloco 8 em diante registram o SHA novo | `git status` sem rastreados alterados nem novos não ignorados; `git log --oneline -5` | todas as sessões |
| 2 | Perfil, frequências, tensões e escopo ACDC decididos e **registrados antes de energizar** | Decisões do responsável (P-26), abaixo | P-01, P-17, P-21, P-26 |
| 3 | `set diagnostico bruto on` na CLI antes de cada `run` das classes de interesse do P-28 (opção existente; padrão OFF; ver {doc}`diagnostico`, seção 1.2) | `status` mostra `diagnostico bruto: ON` | P-28 |
| 4 | Validação do PC da bancada | `scripts\validar_pc_bancada.ps1` no próprio PC (Bloco 1), saída `pc_bancada.json` | P-16 |
| 5 | Orçamento: no máximo **216 gravações TRACe por conexão**; **um `run` por conexão**; **nunca `run all`** (468 gravações a 60 Hz) | Estimativa `TRACe: N gravações` da CLI deve bater com as tabelas da seção 5; se não bater, cancelar e conferir `status` | P-23 |
| 6 | COM10 / 115200; USB da AMETEK conectado, DB9 RS-232 desconectado, MX GUI fechado; BNC AMETEK Trigger Out para Keysight EXT Trigger | Bloco 1, conferência física | todas |
| 7 | Fator da probe de tensão: o que está **escrito na probe**, lido na hora; sem valor presumido | Operador | todas |

### Decisões P-26 pendentes (resolver antes de energizar)

| Decisão | Situação | Efeito se não decidida |
|---|---|---|
| Perfil da campanha | **decidido em 21/10/2026: `set perfil todos`** (1116 gravações em 6 conexões a 127 V/60 Hz), 1 captura por classe (padrão) | Partes do Bloco 9 conforme a seção 5 do roteiro para `todos` |
| Condições da campanha | **decidida em 21/10/2026**: 127 V/60 Hz, 127 V/50 Hz, 230 V/50 Hz, 220 V/60 Hz e 33 V/60 Hz | Ver a seção "Campanhas por condição (P-26)" abaixo |
| Tensão do dia dos Blocos 1–10 | 127 V (roteiro, seção 0) | As demais condições vêm depois, em sessões próprias (seção abaixo) |
| Diagnóstico ACDC 230 V / 50 Hz (3.ª execução do Bloco 5) | **decidido em 21/10/2026: fora (opção A)** | Não executar. Anotar que `g` não foi medido a 230 V; P-17 fecha para 127 V. A campanha CA a 230 V/50 Hz segue normalmente |
| Padrão do passo final SINE (P-18) | pendente (responsável), depois do teste do Bloco 10-A | Padrão continua OFF |

## Tempo

Estimativas do próprio roteiro (seção 1; modelo da seção 4; **NÃO VERIFICADO**, nada foi cronometrado): total de cerca de 2 h a 3 h com um perfil; cerca de 2 h 30 a 3 h 30 com `set perfil todos`. O que este documento acrescenta (Bloco 1-A e Bloco 10-A) não tem estimativa.

## Mapa de pendências por bloco

| Bloco | Energiza | Pendências alimentadas |
|---|---|---|
| 1 Preparação | não | P-16 |
| 2 Infraestrutura (50 Hz) | `native` sim | P-23 (pré-requisito de infraestrutura) |
| 3 Ciclos offline | não | P-02 |
| 4 Marcadores | sim | P-02, P-23 |
| 5 ACDC | sim | P-17 (P-26 para 230 V) |
| 6 Recaptura 08 e 09 | sim | P-03, P-02, P-19 |
| 7 07 e 17 recalibradas | sim | P-07, P-21 |
| 8 Parte 1 da campanha | sim | P-05, P-06, P-01, P-17, P-28 |
| 8-A Sequência P-10 (05 por nível) | sim | P-10, P-28 |
| 9 Partes 2 e 3 (ou 2 a 6) | sim | P-01, P-08, P-23, P-28 |
| 10 Entrega | não | P-22 (no PC da bancada), P-31, P-28, P-16 e consolidação de todas (`fechar_pendencias.py`) |
| 10-A Passo final SINE (extensão) | sim | P-18 |

## Bloco 1. Preparação (sem energizar). Roteiro: Bloco 1. Tempo: 15 a 25 min

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 1.1 | `cd C:\Users\denis\TCC\code`, depois `git pull`, `git log --oneline -5`, `git status` | todas | saída anotada | Árvore limpa; `git log` mostra o commit esperado (roteiro, Bloco 1) |
| 1.2 | `env\Scripts\python.exe -m unittest tests.test_offline` | P-16 | log do console | `OK`, 0 falhas; skips só os dois de hash específico de plataforma, se houver; contagem de testes não fixa (roteiro, Bloco 1) |
| 1.3 | `.\env\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v` | P-16 | log completo, total, tempo, versões Python/numpy, SHA | Resultado, skips e versões registrados (o registro oficial é `scripts\validar_pc_bancada.ps1`, passo 1.4); skip fora dos dois de hash de plataforma precisa de justificativa. Contagem histórica não vale como prova (roteiro, Bloco 1) |
| 1.4 | `scripts\validar_pc_bancada.ps1` | P-16 | `pc_bancada.json` (entregar como `docs/evidencias/<data>/pc_bancada.json`) | Descoberta da suíte no Windows efetivo da bancada, com log, SHA e skips (matriz de execução, P-16). Parâmetros do script: conferir no cabeçalho da ferramenta; este documento não os fixa |
| 1.5 | Conferência física (probe no CH1, BNC, USB sem DB9, MX GUI fechado, disjuntores, E-stop, EUT, OUTPUT OFF) | todas | anotação do operador | Itens da lista do roteiro, Bloco 1 |

Parar se: falha de assinatura portável (roteiro, Bloco 1: entregar saída completa e anotar `numpy`; não coletar). Se falharem só os testes `*_exato_na_plataforma_de_origem`, registrar plataforma, versões e saída antes de coletar.

## Bloco 2. Infraestrutura na CLI, sessão A (127 V / 50 Hz). Roteiro: Bloco 2. Tempo: 8 a 12 min

CLI: `scripts\START_BENCH.cmd`; responder fator da probe, `127`, `50`. Confirmações digitadas pelo operador.

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 2.1 | `status` | todas | `status` anotado | Sorteio `on`, perfil `literatura`, recalibração `OFF`, html `OFF`, diagnóstico `OFF`, sem `set capturas` (roteiro, Bloco 2) |
| 2.2 | `comm` | infraestrutura | `logs\preflight_new-comm-*.log` | `*IDN?` dos dois instrumentos corretos (AMETEK MX30 em `COM10`, Keysight DSO-X 4034A) |
| 2.3 | `trigger` | infraestrutura | `logs\preflight_new-trigger-*.log` | Trigger forçado baixou a waveform |
| 2.4 | `native` (confirmação `ENERGIZAR-COMANDOS`) | infraestrutura, P-23 | `logs\preflight_new-native-*.log` | Termina sem erro SCPI; OUTPUT OFF no painel ao final |
| 2.5 | `lowvoltage` (confirmação `ENERGIZAR-TESTE`), **só** se fiação ou probe foram mexidas | infraestrutura | `logs\preflight_new-lowvoltage-*.log` | critério não definido além de terminar sem erro |
| 2.6 | `quit` | todas | | Os Blocos 4 e 5 exigem a CLI fechada (COM10 exclusiva) |

## Bloco 3. Diagnóstico offline das sessões de 07/10. Roteiro: Bloco 3. Tempo: 2 a 5 min

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 3.1 | `env\Scripts\python.exe scripts\diag_ciclos_trace.py resultados\sessao_2026-10-07_127V_50Hz --classes 08,09` | P-02 | `logs\diag_ciclos_trace-*.md` e `.json` | "Seguir se: o script rodou"; critério numérico não definido. Ler por captura: primeiro ciclo trocado, instante, resíduo perto de 100 ms |
| 3.2 | `env\Scripts\python.exe scripts\diag_ciclos_trace.py resultados\sessao_2026-10-07_14-59-54_run02 --classes 08,09` | P-02 | idem | idem. Se acusar erro de carregamento: entregar a mensagem e seguir (roteiro, Bloco 3) |
| 3.3 | Listar e ler o `.md` mais recente de `logs\diag_ciclos_trace-*` (`Get-ChildItem` e `Get-Content`, roteiro Bloco 3) | P-02 | `.md` lido | Interpretação pela seção 3, linha "Ciclos (offline)" |

## Bloco 4. Marcadores por ciclo (energiza, script). Roteiro: Bloco 4. Tempo: 5 a 8 min (tabela: 6 a 10)

CLI fechada; PowerShell novo. Confirmação `ENERGIZAR-MARCADORES` digitada pelo operador.

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 4.1 | `$env:BENCH_MODE = "1"`, depois `env\Scripts\python.exe scripts\diag_marcadores_trace.py --probe <FATOR escrito na probe> --vrms 127` | P-02, P-23 | `logs\diag_marcadores_trace-*.md`, `.json`, `.log`, `-scpi.log` | Terminou e identificou os marcadores (110 gravações, abaixo de 216). Se recusar antes de energizar: não contornar, entregar a mensagem. Se não reconhecer os marcadores: inconclusivo, seguir (tabela de decisão) |
| 4.2 | Ler o `.md` mais recente (`Get-Content`, roteiro Bloco 4) | P-02 | `.md` lido | Interpretação pela tabela de decisão (seção 3, linhas "Marcadores"); critério numérico não definido |

Variações citadas no roteiro: `--frequencias 50` e depois `--frequencias 60` (duas rodadas); `--variantes fronteira,meio_ciclo`.

## Bloco 5. Amplitude CA em ACDC (energiza, script). Roteiro: Bloco 5. Tempo: 8 a 12 min

CLI fechada. `ENERGIZAR-ACDC` digitado pelo operador em **cada** execução. `$env:BENCH_MODE = "1"` antes.

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 5.1 | `env\Scripts\python.exe scripts\diag_acdc_amplitude.py --probe <FATOR escrito na probe> --vrms 127 --hz 60 --testar-compensacao` | P-17 | `logs\diag_acdc_amplitude-*.md`, `.json`, `.log`, `-scpi.log` | Linhas 1 e 5 (controle) próximas de 1,000; linha 2 e linha 3 próximas de 0,94 a 0,95 ou linha 3 próxima de 1,000; `VOLTage:RANGe?` em ACDC igual a 300 ou não; `g` anotado (provisório 0,9431 em 127 V/60 Hz). Critérios de leitura no roteiro, Bloco 5 |
| 5.2 | `env\Scripts\python.exe scripts\diag_acdc_amplitude.py --probe <FATOR escrito na probe> --vrms 127 --hz 50 --testar-compensacao` | P-17 | idem | idem (`g` provisório 0,9508 em 127 V/50 Hz) |
| 5.3 | **Não autorizado até a decisão P-26**: `... --vrms 230 --hz 50 --testar-compensacao` | P-17, P-26 | idem | Exceção ao limite de 127 V do roteiro (seção 0). Só se o responsável registrar a decisão. Se pulada: anotar que `g` não foi medido a 230 V |
| 5.4 | Ler o `.md` mais recente de `logs\diag_acdc_amplitude-*` | P-17 | `.md` lido | Decisão pela seção 3, linhas "ACDC". Compensação `V/g` não é aplicada antes da caracterização (matriz de execução, P-17) |

Efeito na campanha: se o Bloco 5 mostrar que a 19 não deve ser coletada, o Bloco 8 troca para `run 01-05,18,20`.

## Bloco 6. Recaptura da 08 (127 V / 50 Hz) e da 09 (CLI, sessão A). Roteiro: Bloco 6. Tempo: 10 a 15 min

`scripts\START_BENCH.cmd` (fator, `127`, `50`). Painel da AMETEK à vista durante a primeira captura da 08 (primeiro uso de `TRACe:DATA?`). Confirmações `EXECUTAR-CLASSE-08` e `EXECUTAR-CLASSE-09` digitadas pelo operador.

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 6.1 | CLI: `status`, `set diagnostico bruto on` (P-28), `set diagnostico retrieve on`, `run 08` | P-03, P-19, P-28 | `resultados\sessao_*\metadata\08_*.jsonl`, `diagnostico_trace\`, `bruto_osciloscopio\`, `sessao.log`, `scpi_transcricao.log` | `status` sem `set capturas` (a 08 roda 3 capturas) |
| 6.2 | Inspeção da 08: `Get-Content "$s\metadata\08_*.jsonl"` com o formato do roteiro (Bloco 6) e `Select-String "$s\sessao.log" -Pattern "NÃO corresponde"` | P-03 | saída anotada | `inicio_impulso_s` = 0,09; `validacao_fisica.ok` = `True` nas 3; `desvio_amostras` entre -3 e +3 (aceitável até +-10); `pico_medido_amostra` aproximadamente 2700; `pico_medido_v` <= 374,2 V e sobressinal <= 0,55 (acima: **achado de segurança, parar e avisar**); o metadata grava `validacao_fisica.posicao_evento.sobressinal_medido` e `sobressinal_acima_do_limite`: se este for `true`, parar e registrar achado de segurança; `indice_trigger` igual entre capturas (+-2); nenhuma linha `NÃO corresponde` |
| 6.3 | Mesma inspeção, campos `diagnostico_trace.desvio_max` e `erro`; `Get-ChildItem "$s\diagnostico_trace"` | P-19 | `diagnostico_trace\*.npz` | `erro` vazio nas 3 capturas. Matriz de execução: 1024 valores finitos, ou comando registrado como não suportado. `desvio_max` pequeno e constante entre TRACes. Se falhar: `set diagnostico retrieve off`, anotar a mensagem |
| 6.4 | CLI: `set capturas 6`, `run 09`, `set capturas padrao`, `set diagnostico retrieve off` | P-02 | `metadata\09_*.jsonl` | Executar com 6 capturas (9 se houver tempo) |
| 6.5 | Offline: `env\Scripts\python.exe scripts\diag_ciclos_trace.py $s --classes 08,09` (uma pasta por classe se estiverem em `_run01`/`_run02`) | P-02 | `logs\diag_ciclos_trace-*.md` | 09: aceitar sem ressalva só captura sem ciclo trocado e resíduo perto de 100 ms < ~0,05 pu; acima disso, marcar como suspeita e não usar para treino |
| 6.6 | `quit` | | | |

Se a 08 reprovar por posição: **não repetir sozinho**; entregar `metadata\08_transient.jsonl` e `sessao.log`.

## Bloco 7. 07 e 17 com recalibração (CLI, sessão B: 127 V / 60 Hz). Roteiro: Bloco 7. Tempo: 25 a 35 min

`scripts\START_BENCH.cmd` (fator, `127`, `60`). Confirmação `EXECUTAR-CLASSES-07,17` digitada **duas vezes** pelo operador.

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 7.1 | CLI: `status`, `comm`, `set recalibracao on`, `run 07,17` | P-07 | `metadata\07_*.jsonl`, `17_*.jsonl`, `<sessao>\calibracao_extremos.json` (cópia anterior) | 1.ª rodada esperada: `ok=False` **só** por "fator de crista"; `thd_medida/thd_esperada` entre 0,8 e 1,2; `max(\|pico\|,\|vale\|)` abaixo de 415,8 V e idealmente abaixo de `extremo_previsto_v` |
| 7.2 | Inspeção por classe com o formato do roteiro (Bloco 7, `foreach ($c in "07","17")`) | P-07, P-08 | saída anotada | Idem passo 7.1; sinal de parada: pico ou vale perto de 415,8 V ou muito acima de `extremo_previsto_v` |
| 7.3 | Na mesma CLI: `run 07,17` | P-07, P-21 | idem | 2.ª rodada: `ok=True` em todas |
| 7.4 | `quit`; `git diff -- logica\calibracao_extremos.json` | P-07, P-21 | diff salvo | Fatores só subiram, só em 07 e 17, só na condição 127 V/60 Hz; valores plausíveis (>= 1,344 para a 07 e >= 1,420 para a 17 cobririam o máximo do modelo) |
| 7.5 | `env\Scripts\python.exe -m unittest tests.test_offline` | P-07 | log | Suíte verde antes de commitar |
| 7.6 | `git add logica\calibracao_extremos.json`, `git commit -m "chore: recalibra fatores de extremo 07 e 17 a 127 V/60 Hz"`, `git status` | P-07, P-21 | commit | Árvore limpa. Origem dos fatores = medidas reais (matriz do plano, P-21). Validação só na coleta seguinte, sem aprovação retroativa (P-07) |

Cenários alternativos (tabela de decisão, linhas "07/17"): se a 2.ª rodada ainda reprovar por crista, tirar 07 e 17 da campanha (`06,08-11` e `12-16`) e entregar as sessões; não afrouxar tolerância.

## Bloco 8. Parte 1 da campanha = verificações do sorteio (CLI, sessão B, 60 Hz, commit limpo). Roteiro: Bloco 8. Tempo: 6 a 10 min

Reiniciar a CLI **depois** do commit do Bloco 7 (`git status` limpo; `scripts\START_BENCH.cmd`; fator, `127`, `60`). Escolher antes o perfil (P-26). Para P-28: `set diagnostico bruto on`. Confirmação `EXECUTAR-CLASSES-...` digitada pelo operador.

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 8.1 | CLI: `status`, `set diagnostico bruto on`, `run 01-05,18-20` (ou `run 01-05,18,20` se o Bloco 5 desaconselhou a 19; com `set perfil todos`: `run 01-05,17-19`) | P-01, P-05, P-06, P-10, P-17, P-28 | `resultados\sessao_*` (`.npz` por classe, `metadata\`, `sessao.log`, `scpi_transcricao.log`, `bruto_osciloscopio\`) | Estimativa da CLI = 36 gravações TRACe (tabela da seção 5) |
| 8.2 | `env\Scripts\python.exe scripts\verificar_sessao_bancada.py $s --json logs\verificar_parte1.json` | P-05, P-06 | `logs\verificar_parte1.json` | 02/03/04: `\|erro\|` de largura <= 2 ms, readback igual ao escrito, sem erro SCPI. Pré-trigger: `\|desvio\|` <= 2 amostras (P-05: desvio maior que 2 é aviso, não critério de aprovação). Limiares do verificador são propostas sem dado de bancada |
| 8.3 | 18, fase: linha `fase_18` do verificador | P-06 | `verificar_parte1.json` | `\|salto\|` <= 10 graus; f1/f2 a <= 0,2 Hz de `start_hz`/`end_hz`; `intersecao_ms` perto de 0 indica salto de fase. O limiar de 10 graus segue como proposta (plano, P-06) |
| 8.4 | 18, restauração: `Select-String "$s\scpi_transcricao.log" -Pattern "FREQuency"` (últimas 15) | P-06 | `scpi_transcricao.log` | `SOURce:FREQuency <base>` escrito depois da lista, sem erro `-2xx`; a classe seguinte com `validacao_fisica.ok` |
| 8.5 | `env\Scripts\python.exe logica\analisar_sessao.py $s` | P-05, P-17 | saída da análise | Disparo em fase (01, 05, 18, 19): `\|lag\|` < 0,2 ms e correlação >= 0,99 |
| 8.6 | `Select-String "$s\scpi_transcricao.log" -Pattern "PULSe:WIDTh"` e `-Pattern "MODE ACDC"` | P-05, P-17 | `scpi_transcricao.log` | Largura: readback igual ao escrito. 19: sem queda a 0 V entre capturas |
| 8.7 | 05 (execução padrão, nível 0 do perfil): ler `validacao_fisica.envelope_mediana_medida` de `05_*` | P-10 | `metadata\05_*.jsonl` | 0,7071 +- 0,01 e THD medido dentro de 20 % do pedido; ~0,72 invalida a premissa do modelo. A cobertura por nível é o Bloco 8-A |
| 8.8 | 19: `validacao_fisica` de `19_*` | P-17 | `metadata\19_*.jsonl` | CA conforme o Bloco 5 (déficit conhecido) |

## Bloco 8-A. Sequência P-10: 05 por nível (CLI, sessão B, 60 Hz, commit limpo). Roteiro: Bloco 8-A. Tempo: 5 a 8 min (não cronometrado)

Cada `run` é uma conexão e pede confirmação digitada pelo operador (`EXECUTAR-CLASSE-05`); não usar `set perfil todos`. Opções conferidas em {doc}`configuracao` ("Sequência da P-10"): sem `set capturas` a 05 roda só o nível 0; `set capturas 1` explícito roda os cinco níveis.

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 8A.1 | CLI: `set diagnostico bruto on`, `set perfil norma`, `set capturas 1`, `run 05` | P-10, P-28 | `metadata\05_*.jsonl`, `.npz` da 05, `bruto_osciloscopio\` | 5 capturas: 2, 5, 10, 15 e 20 %, todas `rota_programacao` = `CSIN`; 0 gravações de TRACe |
| 8A.2 | CLI: `set perfil literatura`, `set capturas 1`, `run 05` | P-10 | idem | 5 capturas: 5, 10, 15, 20 % (CSIN) e 30 % (TRACe); 12 gravações de TRACe a 60 Hz (10 a 50 Hz), abaixo de 216; a estimativa da CLI pode não contar a 05 por TRACe (**NÃO VERIFICADO**), conferir `escritas_trace_na_conexao` |
| 8A.3 | Ler por nível `parametros.thd`, `rota_programacao`, `validacao_fisica.envelope_mediana_medida` e THD medido | P-10 | saída anotada | Critério herdado da 05: envelope 0,7071 +- 0,01 e THD medido dentro de 20 % do pedido. Não há critério adicional por nível; `scripts/fechar_pendencias.py` avalia por nível e rota |
| 8A.4 | CLI: `set capturas padrao`; `quit` | | | |

## Bloco 9. Campanha em partes (mesma CLI do Bloco 8). Roteiro: Bloco 9 e seção 5. Tempo: 1 perfil, 20 a 30 min; `todos`, 50 a 70 min

Um `run` por conexão, cada parte com no máximo 216 gravações. Reinicie a CLI entre partes se a seção 5 pedir conexão nova (cada `run` abre uma conexão). Confirmação `EXECUTAR-CLASSES-<lista normalizada>` digitada pelo operador; a CLI mostra a lista exata e a estimativa antes de pedir. Manter `set diagnostico bruto on` se for desejado o bruto também nas classes TRACe (consumo de disco: **NÃO VERIFICADO**).

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 9.1 (1 perfil, Parte 2) | `run 06-11` | P-01, P-08, P-23, P-28 | `resultados\sessao_*\` (por parte) | 216 gravações a 60 Hz (180 a 50 Hz); resumo `N/M classes OK`; OUTPUT OFF no painel |
| 9.2 (1 perfil, Parte 3) | `run 12-17` | P-01, P-08, P-23, P-28 | idem | idem |
| 9.3 (`todos`, Partes 2 a 6) | `run 06,10`; `run 11,12`; `run 13,14`; `run 15,16`; `run 07-09,20` | idem | idem | Cada parte 216 gravações a 60 Hz (seção 5.2). Sem a 08, 07 ou 17 (tabela de decisão): ajustar as listas conforme seção 5.1 |
| 9.4 | Após cada parte: contador máximo `escritas_trace_na_conexao` (`Measure-Object -Maximum`, roteiro Bloco 9) | P-23 | saída anotada | <= 216. A causa física da trava de ~280 gravações só se fecha com diagnóstico real (matriz de execução, P-23); este roteiro não faz ensaio cego até travar |
| 9.5 | Após cada parte: `sessao.log` sem `NÃO corresponde`; pico/vale de 10, 11, 12, 16 contra `extremo_previsto_v` (comando do roteiro, Bloco 9) | P-08, P-01 | saída anotada | `pico_medido_v`/`vale_medido_v` não passam de `extremo_previsto_v`. Se passarem e ficarem abaixo de 415,8 V: registrar e rodar `env\Scripts\python.exe scripts\recalibrar_extremos.py $s` (sem `--gravar`). Perto de 415,8 V: achado de segurança, avisar antes de continuar |

## Bloco 10. Entrega. Roteiro: seção 6. Tempo: 10 a 15 min

OUTPUT OFF no painel e CLI fechada (`quit`).

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 10.1 | `git status`; `git log -3 --stat -- logica\calibracao_extremos.json`; `env\Scripts\python.exe -m unittest tests.test_offline` | P-07, P-21, P-16 | saídas anotadas | Nenhum rastreado alterado; suíte com 0 falhas (seção 6, itens 2 a 4) |
| 10.2 | Conferir `git_commit`/`git_sujo` das sessões (comando do roteiro, seção 6, item 5) | P-01 | saída anotada | `git_sujo` falso e `git_commit` igual ao commit limpo |
| 10.3 | `env\Scripts\python.exe logica\recortar_margem.py $s`, `env\Scripts\python.exe logica\relatorio_html.py $s\sem_margem --dpi 80`, `env\Scripts\python.exe logica\analisar_sessao.py $s` | P-01 | relatório HTML, análise | Opcional; seção 6, item 6 |
| 10.4 | **No PC da bancada**: `env\Scripts\python.exe scripts\benchmark_sessao_io.py --sessao <dir_sessao_1> [--sessao <dir_sessao_2> ...] --saida logs\benchmark_sessao_io_bancada.json` | P-22 | `logs\benchmark_sessao_io_bancada.json` (recusa sobrescrita) | Mede as sessões físicas sem modificá-las (leitura, reescrita em cópia temporária, hash, memória, tamanho) e grava `hostname` e `simulado`. `fechar_pendencias.py` só avalia "executado no PC da bancada" se o `hostname` do artefato coincidir com o de `pc_bancada.json` (sem diferenciar maiúsculas, tolerando o truncamento NetBIOS de 15 caracteres); benchmark sintético (sem `--sessao`) ou `simulado` verdadeiro nunca vale como medição da bancada. Não há limite de tempo/tamanho definido no código/docs: critério numérico não definido, revisão humana |
| 10.5 | Para cada NPZ de `bruto_osciloscopio\<perfil>\` do CH1: `env\Scripts\python.exe scripts\analisar_reamostragem.py --entrada <bruto_CH1.npz> --f0-hz 60 --harmonicos 10 --saida <analise_bruto_novo.json>` (`--f0-hz 50` para sessões a 50 Hz) | P-28 | `analise_bruto_novo.json` por arquivo | Publica RMS, pico, erro temporal, espectro e THD na grade salva. Critério de aceite numérico não definido; a matriz pede revisão dos resultados físicos. O FIR não substitui o interpolador do dataset |
| 10.6 | `env\Scripts\python.exe scripts\analisar_modelo_programado.py --sessao <dir_sessao_1> [--sessao <dir_sessao_2> ...] --saida logs\modelo_programada_sessoes_bancada.json` | P-31 | `logs\modelo_programada_sessoes_bancada.json` (não sobrescreve) | Cálculo reprodutível sobre as sessões físicas (métricas nominal e fundamental ajustada). `fechar_pendencias.py` verifica capturas físicas com `tres_versoes` nas classes 06, 10, 11, 12, 15 e 16. A métrica oficial é decisão do responsável; critério numérico não definido |
| 10.7 | Copiar para o computador de análise (seção 6, item 7): `resultados\sessao_*` inteiras, HTML, e de `logs\` os `diag_ciclos_trace-*`, `diag_marcadores_trace-*`, `diag_acdc_amplitude-*`, `diag_nativo-*`, `verificar_parte1.json`, `preflight_new-*.log` | todas | pastas copiadas | Sessões originais imutáveis; análises derivadas em outro destino |
| 10.8 | Anotar uma linha por bloco (seção 6, item 8): valor medido, fator da probe, fatores 07/17 antes e depois, contador máximo de TRACe, o que ficou fora da campanha e por quê | todas | anotação | Valor medido, não impressão |

## Bloco 10-A. Passo final SINE (P-18; extensão, **não consta no roteiro**). Sem estimativa

Fora do `ROTEIRO_BANCADA.md`: vem de {doc}`projeto/passo-final-sin` (seção 4). Só depois dos Blocos 1 a 10, com a CLI fechada, a COM10 livre e **conexão própria** (o orçamento de 216 gravações vale também aqui; a conta do script não é a da CLI: **NÃO VERIFICADO**). Confirmação `ENERGIZAR-PASSO-SIN` digitada pelo operador, que informa o fator da probe, a tensão e a frequência quando o script perguntar.

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 10A.1 | `env\Scripts\python.exe scripts\teste_passo_final_sin.py --classe 06 --repeticoes 1` | P-18 | `resultados\passo_final_sin_<data>\registros.npz` e `resultado.json`; `logs\` do script | Código de saída 0. rms por ciclo da margem final com o passo = 1,00 +- 0,01 pu; janela rotulada com e sem o passo: correlação >= 0,999 e diferença máxima de rms por ciclo <= 0,01 pu; nenhum erro SCPI. Limiares são escolha do autor do script, sem dado de bancada |
| 10A.2 | Se aprovado: `run 06` pela CLI e conferir as três versões ({doc}`tres_versoes`) | P-18 | sessão | Restauração na fonte e aceitação LIST observadas; critério numérico não definido. O **padrão do passo continua OFF** até o responsável decidir (P-26/D) |

## Bloco 10-B. Experimento P-09 A/B/C (extensão, **não consta no roteiro**). Sessão B, 127 V/60 Hz, depois do Bloco 5 (P-17)

Objetivo: decidir pela medição se o offset DC por passo de LIST recupera a média por ciclo que a TRACe perde (decisão P-09 em `decisoes_pendentes.md`). Mesmas classes, seed, perfil e condição nos três braços; só muda `set p09`.

| Passo | Comando | P-NN | Evidência | Critério |
|---|---|---|---|---|
| 10B.1 | **Sem energizar:** com a CLI fechada, `env\Scripts\python.exe scripts\diag_list_offset.py --saida logs\diag_list_offset.json` (o script só consulta e mantém OUTPUT OFF) | P-09 | `logs\diag_list_offset.json` | Se `SOURce:LIST:VOLTage:OFFSet` **não** for aceito: pular 10B.3 (braço C), rodar só A e B e fechar a P-09 como limitação aceita, com as métricas (d) |
| 10B.2 | CLI: `set p09 A`, `run 10-12,16` (confirmação digitada) | P-09, P-17 | sessão A | Linha de base |
| 10B.3 | CLI: `set p09 C`, `run 10-12,16` | P-09 | sessão C | Só se 10B.1 confirmou o comando; a CLI recusa C antes de energizar se a fonte não aceitar |
| 10B.4 | CLI: `set p09 B`, `run 10-12,16` | P-09, P-17 | sessão B | Controle: AC+DC sem offset, isola o déficit da P-17 |
| 10B.5 | Offline: `env\Scripts\python.exe scripts\analisar_modelo_programado.py --sessao <A> --sessao <B> --sessao <C> --classes 10 11 12 16 --saida logs\p09_abc.json` | P-09 | `logs\p09_abc.json` | C melhor que A e B na correlação medida × modelo e no erro de média por ciclo, sem violar picos → adotar C; caso contrário, manter A e aceitar a limitação |

Observações: com B/C a conexão inteira fica em AC+DC (inclusive classes nativas). Os offsets de LIST são zerados fora das capturas C e no desligamento. Volte para `set p09 A` antes da campanha principal, a menos que o resultado mande adotar C.

## Campanhas por condição (P-26)

Decisão do responsável em 21/10/2026: a campanha roda em **cinco condições**. Elas coincidem com `CONDICOES` em `scripts/verificar_prontidao.py`. Planejamento offline com `--perfis todos`, 150 capturas por condição: `docs/evidencias/2026-10-21/plano_campanhas_5_condicoes.json`. É planejamento, não sessão.

| Condição | Calibração em `logica/calibracao_extremos.json` | Recusadas pelo preflight | Antes da coleta científica |
|---|---|---|---|
| 127 V / 60 Hz | sim | 0 | — (Blocos 7–9) |
| 127 V / 50 Hz | sim | 0 | — |
| 230 V / 50 Hz | sim | 13 (swells 03, 13, 14: pico previsto 416–435 V > teto 415,8 V) | Recusas esperadas; não subir limites |
| 220 V / 60 Hz | **não** | 52 (previsão conservadora sem tabela, até 505 V) | **Calibrar a condição** (P-21) e refazer o plano |
| 33 V / 60 Hz | **não** | 0 | **Calibrar a condição** (P-21) |

Sequência para cada condição (uma sessão por condição; operador presente digitando as confirmações):

1. `START_BENCH.cmd`: informar o fator da probe, a tensão e a frequência da condição. O processo fixa a condição, então trocar de condição exige reiniciar a CLI.
2. **Só 220 V/60 Hz e 33 V/60 Hz:** rodada de calibração. Rodar a bateria na condição; o aviso de "condição sem tabela" é esperado. Depois `.\env\Scripts\python.exe scripts\recalibrar_extremos.py resultados\<sessao>` (mostra o que mudaria), conferir e repetir com `--gravar`. Nunca `--substituir`. Em seguida `git diff`, suíte offline e commit; o novo SHA vale para as sessões seguintes. Reiniciar a CLI. Detalhes: `docs/limites_e_calibracao.md` §5.
3. Refazer o plano offline da condição: `scripts\planejar_campanhas.py --perfis <perfil> --saida <novo.json>`. As recusas restantes são limite físico e ficam registradas.
4. Coleta em grupos de até 216 gravações TRACe por conexão (um `run` por grupo, como no Bloco 9), com `set diagnostico bruto on` nas classes de interesse (P-28).
5. Entrega e fechamento como nos Blocos 10 e "Fechamento offline".

P-26 decidida: cinco condições, `set perfil todos`, 1 captura por classe, sem ACDC a 230 V. Fecha quando as sessões coletadas registrarem exatamente essa configuração.

## Fechamento offline (computador de análise)

Depois da visita, com as pastas copiadas (passo 10.7) e o `pc_bancada.json` do passo 1.4. A ferramenta `scripts/fechar_pendencias.py` roda só offline (não abre instrumento nem importa PyVISA/PyMeasure), lê as sessões e os artefatos, e emite por pendência um status (`evidencia_suficiente`, `insuficiente`, `reprovado` ou `sem_dados`), os critérios avaliados e o SHA-256 dos arquivos de origem. Não fecha pendência e recusa sobrescrever a saída. Opções em `--help`.

```powershell
python scripts/fechar_pendencias.py --sessao <dir_sessao_1> --sessao <dir_sessao_2> --artefatos logs --artefatos resultados --pc-bancada docs/evidencias/<data>/pc_bancada.json --saida docs/evidencias/<data>/fechamento.json
```

`--sessao` e `--artefatos` são repetíveis (uma pasta por opção). `--artefatos` aponta pastas fora das sessões, onde os scripts gravam: `logs\` (`diag_acdc_amplitude-*.json`, `diag_nativo-*.json`, `diag_marcadores_trace-*.json`, `benchmark_sessao_io_bancada.json`, `modelo_programada_sessoes_bancada.json`) e `resultados\` (que contém `passo_final_sin_<data>\`, procurado por `resultado.json`). Forma completa: `--artefatos logs --artefatos resultados`. Diagnósticos de P-17, P-18 e P-23 só contam com `simulado` falso, `git_commit` e `git_sujo` falso gravados no próprio JSON (scripts atualizados; arquivos gerados antes disso saem como `insuficiente`). A saída não sobrescreve arquivo existente.

## O que entregar ao coordenador

1. `docs/evidencias/<data>/pc_bancada.json` e `docs/evidencias/<data>/fechamento.json`.
2. As pastas `resultados\sessao_*` originais (inclusive `sessao.log`, `scpi_transcricao.log`, `metadata\`, `diagnostico_trace\`, `bruto_osciloscopio\`, `calibracao_extremos.json` da sessão) e os arquivos de `logs\` do passo 10.7; mais `resultados\passo_final_sin_<data>\` se o Bloco 10-A foi executado.
3. A anotação do passo 10.8, o commit da recalibração do Bloco 7 e a lista do que ficou fora da campanha (19, 08, 07, 17) com o motivo.
4. Qual linha da tabela de decisão (roteiro, seção 3) foi aplicada nos Blocos 3, 4, 5, 6 e 7.
5. Achados de segurança (pico acima de 374,2 V na 08, extremos perto de 415,8 V) e falhas de infraestrutura, com os logs.
6. Pendências que **não** fecham nesta visita e dependem do responsável: P-09 (aceitar o limite), P-20, P-26 (decisões acima, inclusive ACDC 230 V), P-29, P-30, a métrica oficial de P-31 e o padrão do SINE (P-18).
