# Roteiro da próxima bancada

```{include} /_includes/aviso-base.md
```


{bdg-danger}`PENDENTE P-01` {bdg-warning}`NÃO VERIFICADO`

## Roteiro da próxima bancada (v1.15)

Para quem vai ao PC da bancada em `C:\Users\denis\TCC\code` (ajuste o caminho). Ordem decidida: **primeiro o diagnóstico, depois a campanha**, porque o diagnóstico pode mudar o que vale coletar (tabela de decisão na seção 3). Regras de segurança invioláveis: `AGENTS.md`. Operação da CLI: `docs/operacao.md`.

Este roteiro foi escrito sem acesso à bancada. Todo comando e toda confirmação citados existem no código (conferência na seção 7); todo tempo é **estimativa** (modelo na seção 4), exceto onde diz "medido".

### 0. Regras fixas do dia

- **Fator da probe de tensão**: o que está **escrito na probe física**, conferido na hora. Em todo comando abaixo aparece como `<FATOR escrito na probe>`; não presuma o valor de sessões anteriores. O `START_BENCH` pergunta; os scripts `diag_*` recebem em `--probe`.
- **Confirmações digitadas, case-sensitive, nunca automatizadas**: `ENERGIZAR-TESTE`, `ENERGIZAR-COMANDOS`, `EXECUTAR-CLASSE-<NN>`, `EXECUTAR-CLASSES-<lista normalizada>`, `EXECUTAR-20-CLASSES` (não usada hoje), `ENERGIZAR-MARCADORES`, `ENERGIZAR-ACDC` e, **só no passo P-18** (Bloco 10-A, `diag/teste_passo_final_sin.py`), `ENERGIZAR-PASSO-SIN`. **Nenhum script, macro ou agente digita qualquer uma delas: o operador está presente e digita cada uma.** Antes de digitar: probe, cabos, E-stop, EUT, **disjuntores entre a fonte e a probe fechados**.
- **Captura de corrente desligada** (`CAPTURE_CURRENT=0`). Não ativar.
- **Tensão do dia: 127 V.** Sem 220/380 V. A execução ACDC a 230 V (Bloco 5, 3.ª execução) **não será feita**: decisão P-26 de 21/10/2026, opção A (`docs/projeto/pendencias.md`, seção P-26). As campanhas CA nas outras condições (230 V/50 Hz, 220 V/60 Hz, 33 V/60 Hz) são sessões próprias, fora deste dia (seção 9.4, "Campanhas por condição"). Frequências: sessão A em **50 Hz** (diagnóstico da 08/09), sessão B em **60 Hz** (campanha).
- **Antes de scripts `diag_*` que acessam instrumentos, sair da CLI com `quit` e confirmar OUTPUT OFF**; COM10 é exclusiva. Scripts offline de análise não abrem instrumentos.
- **Uma conexão com a fonte = um comando `run`**. A fonte travou na ~280.ª gravação de TRACe de uma conexão (2026-09-16); neste roteiro nenhuma conexão passa de 216 gravações. `run all` (468 gravações a 60 Hz) **não** é usado.
- **Toda sessão de coleta sai de commit limpo** e a CLI é reiniciada depois de commitar (o metadata grava `git_commit`/`git_sujo`). Isto vale **bloco a bloco**: cada bloco que coleta começa com `git status` limpo. Os scripts novos (`benchmark_sessao_io.py`, `analisar_modelo_programado.py`, `fechar_pendencias.py`, `validar_pc_bancada.ps1`, `teste_passo_final_sin.py` etc.) já estão commitados no branch; arquivo novo não commitado em `scripts/`, `logica/` ou `experimentos_*` torna `git_sujo` verdadeiro. No Bloco 7 o commit da calibração gera um **NOVO SHA**: as sessões dos Blocos 1 a 7 registram o SHA anterior e as do Bloco 8 em diante registram o SHA novo (o `git_commit` esperado muda no meio do dia; anotar os dois).
- **Diagnóstico bruto (P-28)**: antes de cada `run` cujas classes interessam ao P-28, digitar `set diagnostico bruto on` na CLI (padrão OFF; não faz aquisição extra); conferir em `status` (`diagnostico bruto: ON`).
- **Falha de infraestrutura** (porta serial caiu, `CommunicationError`, impossível confirmar OUTPUT, `FalhaFatalDeInstrumento`, `CadeiaDeMedicaoError`): 1) confirmar fisicamente **OUTPUT OFF** no painel da AMETEK; 2) **não repetir** automaticamente; 3) entregar `sessao.log` e `scpi_transcricao.log` da pasta `resultados\sessao_<timestamp>[_runNN]` mais recente (para `run`), ou `logs\preflight_new-*.log` mais recente (para `comm`/`trigger`/`lowvoltage`/`native`), ou `logs\diag_*-*.log` e `-scpi.log` (scripts `diag_*`); 4) nunca remover validação de IDN, timeout, 6000 pontos ou SCPI. Falha de **experimento** (RMS fora de tolerância, captura inválida) não é infraestrutura: a bateria isola e segue.
- Variável de ajuda nos blocos de CLI: depois de cada `run`, em outro PowerShell:

```powershell
cd C:\Users\denis\TCC\code
$s = (Get-ChildItem resultados -Directory | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
$s
```

### 1. Visão geral e tempo

| Bloco | O que é | Energiza | Confirmação digitada | Tempo (estimado) |
|---|---|---|---|---|
| 1 | Preparação: `git pull`, árvore limpa, `tests.test_offline` no Windows, conferência física | não | nenhuma | 15 a 25 min |
| 2 | CLI sessão A (50 Hz): `comm`, `trigger`, `native` (`lowvoltage` só se mexeu em fiação/probe) | `native` sim | `ENERGIZAR-COMANDOS` (e `ENERGIZAR-TESTE`) | 8 a 12 min |
| 3 | Diagnóstico offline das sessões de 07/10 (`diag_ciclos_trace.py`) | não | nenhuma | 2 a 5 min |
| 4 | Marcadores por ciclo (`diag_marcadores_trace.py`) | sim | `ENERGIZAR-MARCADORES` | 6 a 10 min |
| 5 | Amplitude CA em ACDC (`diag_acdc_amplitude.py`, 3 condições) | sim | `ENERGIZAR-ACDC` (x3) | 8 a 12 min |
| 6 | CLI sessão A (50 Hz): recaptura da 08, depois a 09 | sim | `EXECUTAR-CLASSE-08`, `EXECUTAR-CLASSE-09` | 10 a 15 min |
| 7 | CLI sessão B (60 Hz): 07 e 17 com recalibração, commit, reinício | sim | `EXECUTAR-CLASSES-07,17` (x2) | 25 a 35 min |
| 8 | Parte 1 da campanha = verificações do sorteio (02/03/04, 05, 18, 19, 01) | sim | `EXECUTAR-CLASSES-...` | 6 a 10 min |
| 8-A | P-10: 05 por nível (`set perfil norma`/`literatura`, `set capturas 1`, `run 05` x2) | sim | `EXECUTAR-CLASSE-05` (x2) | 5 a 8 min (não cronometrado) |
| 9 | Partes 2 e 3 da campanha (1 perfil), ou 2 a 6 com `set perfil todos` | sim | `EXECUTAR-CLASSES-...` | 1 perfil: 20 a 30 min; `todos`: 50 a 70 min |
| 10 | Entrega (checklist; P-22, P-31 e fechamento) | não | nenhuma | 10 a 15 min (sem os benchmarks) |

Total estimado do dia (soma dos intervalos acima): **cerca de 2 h a 3 h** com um perfil; **cerca de 2 h 30 a 3 h 30** com `set perfil todos`. Se quiser economizar um `START_BENCH`, faça o Bloco 6 na mesma CLI do Bloco 2 e deixe os blocos 3 a 5 (scripts, que precisam da CLI fechada porque a COM10 é exclusiva) para antes ou depois; a ordem entre eles não muda nenhum critério.

### 2. Blocos em ordem de execução

#### Bloco 1. Preparação (sem energizar)

Objetivo: máquina no commit certo, árvore limpa, suíte verde **no Windows** (a suíte foi validada só no Linux; 2 testes de hash exato só rodam no Windows).

```powershell
cd C:\Users\denis\TCC\code
git pull
git log --oneline -5
git status
env\Scripts\python.exe -m unittest tests.test_offline
```

(Se `env\` ainda não existe: `scripts\setup_windows.ps1`; o `START_BENCH` também o cria.)

Conferir:
- `git log` mostra este roteiro (`docs/roteiro-bancada.md`, esta página, existe no checkout) e o commit da crista com o fator calibrado .
- `git status` sem alterações rastreadas nem arquivos novos não ignorados nas pastas `mestre.PASTAS_DO_CODIGO`; `info_do_codigo` recalcula esse estado a cada pasta de sessão. Arquivos novos fora dessas pastas não contam para `git_sujo`.
- A suíte termina em `OK`, **todos os testes passando e 0 falhas**; a contagem de testes **não é fixa** (novos testes aumentam o total). Skips aceitáveis: só os dois testes de hash exato específico de plataforma (`*_exato_na_plataforma_de_origem`), se houverem; qualquer outro skip precisa de justificativa. Rodar também `.\env\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v` e `scripts\validar_pc_bancada.ps1`: este script é o **registro** da validação do PC (P-16): grava `pc_bancada.json` com total, tempo, versões, SHA e skips (entregar como `docs/evidencias/<data>/pc_bancada.json`). Não usar contagem histórica como prova de execução.
- Conferência física: probe diferencial no CH1 entre fase A e neutro, fator **lido na probe**; BNC AMETEK Trigger Out -> Keysight EXT Trigger; USB da AMETEK conectado e **DB9 RS-232 desconectado**; MX GUI **fechado**; disjuntores fechados; E-stop ao alcance; EUT conectado; OUTPUT OFF no painel.

Seguir se: suíte `OK`, 0 falhas, skips só os dois de hash específico de plataforma (se houver) e `pc_bancada.json` gerado, árvore limpa.
Parar se: algum teste de **assinatura portável** falhar (a causa não seria só o último bit de `np.sin`): entregar a saída completa, anotar `numpy` (`env\Scripts\python.exe -c "import numpy; print(numpy.__version__)"`) e **não coletar** até analisar. Se falharem **só** os testes `*_exato_na_plataforma_de_origem` (SHA-256), registrar plataforma, Python/numpy e saída completa para diagnóstico antes de coletar; não considerar uma falha de fixture como autorização automática para coleta. Árvore suja: commitar ou descartar a causa antes de qualquer sessão.

##### Passos por pendência: comando, P-NN, evidência e critério

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 1.1 | `cd C:\Users\denis\TCC\code`, depois `git pull`, `git log --oneline -5`, `git status` | todas | saída anotada | Árvore limpa; `git log` mostra o commit esperado (roteiro, Bloco 1) |
| 1.2 | `env\Scripts\python.exe -m unittest tests.test_offline` | P-16 | log do console | `OK`, 0 falhas; skips só os dois de hash específico de plataforma, se houver; contagem de testes não fixa (roteiro, Bloco 1) |
| 1.3 | `.\env\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v` | P-16 | log completo, total, tempo, versões Python/numpy, SHA | Resultado, skips e versões registrados (o registro oficial é `scripts\validar_pc_bancada.ps1`, passo 1.4); skip fora dos dois de hash de plataforma precisa de justificativa. Contagem histórica não vale como prova (roteiro, Bloco 1) |
| 1.4 | `scripts\validar_pc_bancada.ps1` | P-16 | `pc_bancada.json` (entregar como `docs/evidencias/<data>/pc_bancada.json`) | Descoberta da suíte no Windows efetivo da bancada, com log, SHA e skips (matriz de execução, P-16). Parâmetros do script: conferir no cabeçalho da ferramenta; este documento não os fixa |
| 1.5 | Conferência física (probe no CH1, BNC, USB sem DB9, MX GUI fechado, disjuntores, E-stop, EUT, OUTPUT OFF) | todas | anotação do operador | Itens da lista do roteiro, Bloco 1 |

Parar se: falha de assinatura portável (roteiro, Bloco 1: entregar saída completa e anotar `numpy`; não coletar). Se falharem só os testes `*_exato_na_plataforma_de_origem`, registrar plataforma, versões e saída antes de coletar.

#### Bloco 2. Infraestrutura na CLI, sessão A (127 V / 50 Hz)

```powershell
cd C:\Users\denis\TCC\code
scripts\START_BENCH.cmd
```

Responder: fator da probe `<FATOR escrito na probe>`, tensão `127`, frequência `50`. Na CLI:

```
status
comm
trigger
native
```

- `comm` e `trigger` não energizam. `native` energiza em tensão base: digitar `ENERGIZAR-COMANDOS`.
- `lowvoltage` **só** se a fiação ou a probe foram mexidas (ou `comm`/`trigger` falharam e foram consertados): digitar `ENERGIZAR-TESTE`; usa a tensão base digitada (127 V), reprograma ~12 TRACes (~40 a 50 s).
- `status` deve mostrar: sorteio `on`, perfil `literatura`, recalibração `OFF`, html `OFF`, diagnóstico `OFF`, sem `set capturas`.

Conferir: `*IDN?` dos dois instrumentos corretos (AMETEK MX30 em `COM10`, Keysight DSO-X 4034A); trigger forçado baixou a waveform; `native` terminou sem erro SCPI; **OUTPUT OFF no painel ao final**.
Seguir se: os três passam. Parar se: qualquer um falha (infraestrutura): procedimento da seção 0; entregar `logs\preflight_new-*.log` mais recente.
Tempo: `comm` + `trigger` 1 a 2 min; `native` não medido (estimar 3 a 5 min).

Sair: `quit` (os blocos 4 e 5 exigem a CLI fechada).

##### Passos por pendência: comando, P-NN, evidência e critério

CLI: `scripts\START_BENCH.cmd`; responder fator da probe, `127`, `50`. Confirmações digitadas pelo operador.

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 2.1 | `status` | todas | `status` anotado | Sorteio `on`, perfil `literatura`, recalibração `OFF`, html `OFF`, diagnóstico `OFF`, sem `set capturas` (roteiro, Bloco 2) |
| 2.2 | `comm` | infraestrutura | `logs\preflight_new-comm-*.log` | `*IDN?` dos dois instrumentos corretos (AMETEK MX30 em `COM10`, Keysight DSO-X 4034A) |
| 2.3 | `trigger` | infraestrutura | `logs\preflight_new-trigger-*.log` | Trigger forçado baixou a waveform |
| 2.4 | `native` (confirmação `ENERGIZAR-COMANDOS`) | infraestrutura, P-23 | `logs\preflight_new-native-*.log` | Termina sem erro SCPI; OUTPUT OFF no painel ao final |
| 2.5 | `lowvoltage` (confirmação `ENERGIZAR-TESTE`), **só** se fiação ou probe foram mexidas | infraestrutura | `logs\preflight_new-lowvoltage-*.log` | critério não definido além de terminar sem erro |
| 2.6 | `quit` | todas | | Os Blocos 4 e 5 exigem a CLI fechada (COM10 exclusiva) |

#### Bloco 3. Diagnóstico offline das sessões de 07/10 (sem energizar)

Objetivo: ver, nos dados que já existem, **qual ciclo programado explica cada ciclo medido** nas classes 08 e 09, a partir de que instante e com que resíduo perto de 100 ms. É a opção mais barata e pode ser feita antes de ir à bancada.

```powershell
cd C:\Users\denis\TCC\code
env\Scripts\python.exe diag\diag_ciclos_trace.py resultados\sessao_2026-10-07_127V_50Hz --classes 08,09
env\Scripts\python.exe diag\diag_ciclos_trace.py resultados\sessao_2026-10-07_14-59-54_run02 --classes 08,09
Get-ChildItem logs\diag_ciclos_trace-* | Sort-Object LastWriteTime | Select-Object -Last 4 | Format-Table Name, Length
Get-Content (Get-ChildItem logs\diag_ciclos_trace-*.md | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
```

(`--sem-forma-bancada` dispensa o candidato `k_sem_dc`. Não escreve na pasta da sessão.)

Conferir, por captura: primeiro ciclo **trocado** e quem o explica (`k-1`, `k+1`...), instante do ciclo, primeira amostra divergente, resíduo máximo perto de 100 ms. Leitura: seção 3, linha "Ciclos (offline)".
Seguir se: o script rodou. Se acusar erro de carregamento (caminho `.npz` bruto + reconstrução de versões, **não exercitado em teste com dado real**): entregar a mensagem completa e seguir sem este bloco (os blocos 4 e 6 trazem o dado novo). Tempo: 2 a 5 min (não medido).

##### Passos por pendência: comando, P-NN, evidência e critério

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 3.1 | `env\Scripts\python.exe diag\diag_ciclos_trace.py resultados\sessao_2026-10-07_127V_50Hz --classes 08,09` | P-02 | `logs\diag_ciclos_trace-*.md` e `.json` | "Seguir se: o script rodou"; critério numérico não definido. Ler por captura: primeiro ciclo trocado, instante, resíduo perto de 100 ms |
| 3.2 | `env\Scripts\python.exe diag\diag_ciclos_trace.py resultados\sessao_2026-10-07_14-59-54_run02 --classes 08,09` | P-02 | idem | idem. Se acusar erro de carregamento: entregar a mensagem e seguir (roteiro, Bloco 3) |
| 3.3 | Listar e ler o `.md` mais recente de `logs\diag_ciclos_trace-*` (`Get-ChildItem` e `Get-Content`, roteiro Bloco 3) | P-02 | `.md` lido | Interpretação pela seção 3, linha "Ciclos (offline)" |

#### Bloco 4. Marcadores por ciclo (energiza, script)

Objetivo: separar "o ciclo k tocou o ciclo k-1" (troca de passo) de "cópia em instante fixo (~100 ms)", medir atraso global em amostras e confrontar as hipóteses de `logica/modelo_lista_fonte.py`.

CLI fechada. PowerShell novo:

```powershell
cd C:\Users\denis\TCC\code
$env:BENCH_MODE = "1"
env\Scripts\python.exe diag\diag_marcadores_trace.py --probe <FATOR escrito na probe> --vrms 127
```

Digitar `ENERGIZAR-MARCADORES`. Padrão: 50 e 60 Hz, três variantes (`marcadores`, `fronteira`, `meio_ciclo`), 10 capturas, **110 gravações de TRACe** em uma conexão (abaixo do orçamento de 216). Para dividir em duas rodadas: `--frequencias 50` e depois `--frequencias 60`. Só o par ponto 0 / meio ciclo: `--variantes fronteira,meio_ciclo`.

Conferir (`logs\diag_marcadores_trace-*.md` e `.json`; `.log` e `-scpi.log` são para entregar):
- por captura, o `k` tocado em cada ciclo e o deslocamento em ciclos; o atraso global em amostras;
- nas variantes `fronteira` e `meio_ciclo` (eventos a 40 e 80 ms): a cópia fica em ~100 ms nos dois instantes, ou acompanha o evento (+1 ciclo)?;
- o ranking de hipóteses (`confrontar`) por captura.

```powershell
Get-Content (Get-ChildItem logs\diag_marcadores_trace-*.md | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
```

Seguir se: terminou e identificou os marcadores. Se o script **recusar** antes de energizar (pico/rms acima do limite, mais de 216 TRACes): não contornar, entregar a mensagem. Se terminar mas **não reconhecer** os marcadores (a banda da fonte pode achatar a lombada de 24 amostras; limiares não calibrados): resultado inconclusivo, seguir (tabela, linha "Marcadores inconclusivos").
Parar se: infraestrutura (seção 0). Tempo: 5 a 8 min com a definição das TRACes na Flash (~3 s cada nas primeiras 12) e as confirmações.

##### Passos por pendência: comando, P-NN, evidência e critério

CLI fechada; PowerShell novo. Confirmação `ENERGIZAR-MARCADORES` digitada pelo operador.

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 4.1 | `$env:BENCH_MODE = "1"`, depois `env\Scripts\python.exe diag\diag_marcadores_trace.py --probe <FATOR escrito na probe> --vrms 127` | P-02, P-23 | `logs\diag_marcadores_trace-*.md`, `.json`, `.log`, `-scpi.log` | Terminou e identificou os marcadores (110 gravações, abaixo de 216). Se recusar antes de energizar: não contornar, entregar a mensagem. Se não reconhecer os marcadores: inconclusivo, seguir (tabela de decisão) |
| 4.2 | Ler o `.md` mais recente (`Get-Content`, roteiro Bloco 4) | P-02 | `.md` lido | Interpretação pela tabela de decisão (seção 3, linhas "Marcadores"); critério numérico não definido |

Variações citadas no roteiro: `--frequencias 50` e depois `--frequencias 60` (duas rodadas); `--variantes fronteira,meio_ciclo`.

#### Bloco 5. Amplitude CA em ACDC (energiza, script)

Objetivo: entender o déficit de 5 a 6 % de CA na classe 19 (ACDC) e medir o ganho `g = CH1 CA / alvo` por condição.

CLI fechada. Três execuções (digitar `ENERGIZAR-ACDC` em cada uma):

```powershell
cd C:\Users\denis\TCC\code
$env:BENCH_MODE = "1"
env\Scripts\python.exe diag\diag_acdc_amplitude.py --probe <FATOR escrito na probe> --vrms 127 --hz 60 --testar-compensacao
env\Scripts\python.exe diag\diag_acdc_amplitude.py --probe <FATOR escrito na probe> --vrms 127 --hz 50 --testar-compensacao
env\Scripts\python.exe diag\diag_acdc_amplitude.py --probe <FATOR escrito na probe> --vrms 230 --hz 50 --testar-compensacao
Get-Content (Get-ChildItem logs\diag_acdc_amplitude-*.md | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
```

**A 3.ª execução (230 V) não será feita (decisão P-26 de 21/10/2026, opção A)** (`docs/projeto/pendencias.md`, seção P-26, item 4: opção A = fora desta campanha, recomendada; opção B = exceção formal ao roteiro de 127 V). Sem a decisão registrada por escrito, **não executar**: pule-a e anote que `g` não foi medido a 230 V (P-17 fecha só para 127 V). Se a opção B for decidida, a 3.ª condição só separa a dependência da tensão (H7); o script limita a V <= 270 e planeja o pior caso de pico <= 415,8 Vp. 

Conferir (tabela `.md`, colunas `CH1 AC / alvo`, `fonte DC?`, `fonte AC?`, `CH1 CC`; e `VOLTage:RANGe?`):
- linhas 1 e 5 (AC, controle inicial e final) ≈ 1,000 (sem deriva);
- linha 2 (ACDC/STEP) e linha 3 (ACDC/`VOLTage` imediato): ambas ≈ 0,94 a 0,95, ou a linha 3 ≈ 1,000;
- `VOLTage:RANGe?` em ACDC igual a 300 ou não;
- `g` (linha 2) nas 3 condições (provisórios dos dados de 07/10: 0,9508 a 127 V/50 Hz, 0,9431 a 127 V/60 Hz, 0,9377 a 230 V/50 Hz);
- linhas de compensação (`V_prog` = V/g): `CH1 AC / alvo` ≈ 1,000;
- CC a 60 Hz: medido menos programado entre -1,0 e -1,7 V (viés de cadeia); +1,9 V repete a anomalia de 07/10;
- `fonte AC?` ≈ raiz de (CA² + CC²), com CC = `fonte DC?` (confirma que `MEASure:VOLTage:AC?` em ACDC é rms total); `MEASure:VOLTage:DC?` rejeitado: anotar.

Leitura: seção 3, linhas "ACDC". Seguir se: as 3 (ou 2) execuções terminaram. Parar se: infraestrutura (seção 0; entregar `logs\diag_acdc_amplitude-*.log` mais recente). Tempo: 2 a 3 min por execução (relatado no diagnóstico de 12/10), ~8 min com trocas.

##### Passos por pendência: comando, P-NN, evidência e critério

CLI fechada. `ENERGIZAR-ACDC` digitado pelo operador em **cada** execução. `$env:BENCH_MODE = "1"` antes.

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 5.1 | `env\Scripts\python.exe diag\diag_acdc_amplitude.py --probe <FATOR escrito na probe> --vrms 127 --hz 60 --testar-compensacao` | P-17 | `logs\diag_acdc_amplitude-*.md`, `.json`, `.log`, `-scpi.log` | Linhas 1 e 5 (controle) próximas de 1,000; linha 2 e linha 3 próximas de 0,94 a 0,95 ou linha 3 próxima de 1,000; `VOLTage:RANGe?` em ACDC igual a 300 ou não; `g` anotado (provisório 0,9431 em 127 V/60 Hz). Critérios de leitura no roteiro, Bloco 5 |
| 5.2 | `env\Scripts\python.exe diag\diag_acdc_amplitude.py --probe <FATOR escrito na probe> --vrms 127 --hz 50 --testar-compensacao` | P-17 | idem | idem (`g` provisório 0,9508 em 127 V/50 Hz) |
| 5.3 | **Não autorizado até a decisão P-26**: `... --vrms 230 --hz 50 --testar-compensacao` | P-17, P-26 | idem | Exceção ao limite de 127 V do roteiro (seção 0). Só se o responsável registrar a decisão. Se pulada: anotar que `g` não foi medido a 230 V |
| 5.4 | Ler o `.md` mais recente de `logs\diag_acdc_amplitude-*` | P-17 | `.md` lido | Decisão pela seção 3, linhas "ACDC". Compensação `V/g` não é aplicada antes da caracterização (matriz de execução, P-17) |

Efeito na campanha: se o Bloco 5 mostrar que a 19 não deve ser coletada, o Bloco 8 troca para `run 01-05,18,20`.

#### Bloco 6. Recaptura da 08 a 127 V / 50 Hz e a 09 (CLI, sessão A)

Objetivo: três capturas da 08 com o impulso em 90 ms (a 50 Hz o impulso saiu da fronteira de ciclo: `experimentos_waveform/08.py`), e a 09 logo depois, com mais capturas, para separar "instante fixo em 100 ms" de "acompanha o evento". Também é o **primeiro uso de `set diagnostico retrieve`**.

```powershell
cd C:\Users\denis\TCC\code
scripts\START_BENCH.cmd
```

(`<FATOR escrito na probe>`, `127`, `50`.) Na CLI:

```
status
set diagnostico bruto on
set diagnostico retrieve on
run 08
```

(`set diagnostico bruto on` é a pré-condição P-28 da seção 0.)

- `status`: sorteio `on`, perfil `literatura`, **sem** `set capturas` (com ele a 08 vira rampa de caracterização, não é o que se quer), capturas da 08 = 3.
- Digitar `EXECUTAR-CLASSE-08`.
- **Painel da AMETEK à vista** durante a primeira captura: `TRACe:DATA? <nome>` nunca foi usado nesta fonte (o manual se contradiz: p. 126 "Query Syntax: none"; p. 147 "when queried"). A leitura vem **depois** da captura, com espera mínima de 2 s desde a última escrita de TRACe, e nunca como primeiro comando após um `TRACe:DATA`. `set capturas 1` **não** isola uma captura (cada classe roda o maior entre o valor digitado e o seu padrão; a 08 roda 3), então a primeira captura da 08 é o teste isolado: se o painel mostrar erro ou a fonte parar de responder, `Ctrl+C` (interrompe quando a chamada VISA em curso retorna, até ~15 s), confirmar OUTPUT OFF e seguir o procedimento da seção 0.

Depois da 08, em outro PowerShell:

```powershell
cd C:\Users\denis\TCC\code
$s = (Get-ChildItem resultados -Directory | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
Get-Content "$s\metadata\08_*.jsonl" | ForEach-Object { $j = $_ | ConvertFrom-Json; "{0} ok={1} impulso previsto {2} medido {3} desvio {4} | pico {5} vale {6} | inicio_impulso_s {7} | trigger {8} | retrieve desvio_max {9} erro {10} | sobressinal {11} acima_limite {12}" -f $j.id_captura,$j.validacao_fisica.ok,$j.validacao_fisica.posicao_evento.inicio_previsto_amostra,$j.validacao_fisica.posicao_evento.pico_medido_amostra,$j.validacao_fisica.posicao_evento.desvio_amostras,$j.pico_medido_v,$j.vale_medido_v,$j.parametros.inicio_impulso_s,$j.indice_trigger,$j.diagnostico_trace.desvio_max,$j.diagnostico_trace.erro,$j.validacao_fisica.posicao_evento.sobressinal_medido,$j.validacao_fisica.posicao_evento.sobressinal_acima_do_limite }
Select-String "$s\sessao.log" -Pattern "NÃO corresponde" 
Get-ChildItem "$s\diagnostico_trace"
```

Critério de aprovação da 08 (50 Hz):
- `parametros.inicio_impulso_s` = 0,09; `validacao_fisica.ok` = `True` nas 3; `desvio_amostras` entre -3 e +3 (aceitável até +-10; em 07/10 a 60 Hz deu 0, 0, -1); `pico_medido_amostra` ≈ 2700;
- `pico_medido_v` <= 374,2 V (`teto`), sobressinal <= 0,55: acima disso é **achado de segurança**: parar e avisar. O metadata agora grava `validacao_fisica.posicao_evento.sobressinal_medido` e `validacao_fisica.posicao_evento.sobressinal_acima_do_limite` (P-03): se `sobressinal_acima_do_limite` for `true` em qualquer captura, **parar e registrar achado de segurança** (não repetir sozinho);
- `indice_trigger` iguais entre as capturas (+-2); nenhuma linha `NÃO corresponde ao que foi programado` no `sessao.log`;
- retrieve: `erro` vazio nas 3 capturas; `desvio_max` é a diferença bruta contra a TRACe enviada (pico 1): um valor diferente de zero pode ser normalização da fonte, não erro; o que importa é se é **pequeno e constante** entre TRACes. Arquivos em `diagnostico_trace\`.

Se retrieve falhar (`erro` preenchido, `LeituraTraceError`): `set diagnostico retrieve off`; a captura não é perdida; anotar a mensagem (se a query existe nesta revisão do firmware é a pergunta). Se der certo, pode ficar ligado para a 09.

Em seguida, a 09, com 6 capturas (a 09 sorteada só cai dentro do evento em ~17 a 18 % das capturas no instante de 100 ms, então 3 capturas são poucas; 9 se houver tempo):

```
set capturas 6
run 09
set capturas padrao
set diagnostico retrieve off
```

Digitar `EXECUTAR-CLASSE-09`. Depois, offline, no PowerShell:

```powershell
cd C:\Users\denis\TCC\code
$s = (Get-ChildItem resultados -Directory | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
env\Scripts\python.exe diag\diag_ciclos_trace.py $s --classes 08,09
Get-Content (Get-ChildItem logs\diag_ciclos_trace-*.md | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
```

(a 08 e a 09 podem estar em pastas diferentes: `_run01`/`_run02`; rodar o script na pasta de cada uma, `--classes 08` e `--classes 09`.)

Critério da 09: aceitar **sem ressalva** só a captura **sem ciclo trocado** e com resíduo perto de 100 ms **< ~0,05 pu** (ruído da 09: 0,008 a 0,017 pu rms). Acima disso: manter a captura, marcar como suspeita, **não usar para treino**. É defeito de dado, não de infraestrutura: não interrompe nada.
Tempo: `run 08` ~2 min, `run 09` (6 capturas) ~3 a 5 min, mais START_BENCH e leituras: 10 a 15 min.
Seguir se: a 08 aprovada e a 09 classificada. Se a 08 reprovar por posição: **não repetir sozinho**; entregar `metadata\08_transient.jsonl` e `sessao.log`; na campanha a 60 Hz a 08 segue o caso da tabela (seção 3).

Sair da CLI: `quit`.

##### Passos por pendência: comando, P-NN, evidência e critério

`scripts\START_BENCH.cmd` (fator, `127`, `50`). Painel da AMETEK à vista durante a primeira captura da 08 (primeiro uso de `TRACe:DATA?`). Confirmações `EXECUTAR-CLASSE-08` e `EXECUTAR-CLASSE-09` digitadas pelo operador.

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 6.1 | CLI: `status`, `set diagnostico bruto on` (P-28), `set diagnostico retrieve on`, `run 08` | P-03, P-19, P-28 | `resultados\sessao_*\metadata\08_*.jsonl`, `diagnostico_trace\`, `bruto_osciloscopio\`, `sessao.log`, `scpi_transcricao.log` | `status` sem `set capturas` (a 08 roda 3 capturas) |
| 6.2 | Inspeção da 08: `Get-Content "$s\metadata\08_*.jsonl"` com o formato do roteiro (Bloco 6) e `Select-String "$s\sessao.log" -Pattern "NÃO corresponde"` | P-03 | saída anotada | `inicio_impulso_s` = 0,09; `validacao_fisica.ok` = `True` nas 3; `desvio_amostras` entre -3 e +3 (aceitável até +-10); `pico_medido_amostra` aproximadamente 2700; `pico_medido_v` <= 374,2 V e sobressinal <= 0,55 (acima: **achado de segurança, parar e avisar**); o metadata grava `validacao_fisica.posicao_evento.sobressinal_medido` e `sobressinal_acima_do_limite`: se este for `true`, parar e registrar achado de segurança; `indice_trigger` igual entre capturas (+-2); nenhuma linha `NÃO corresponde` |
| 6.3 | Mesma inspeção, campos `diagnostico_trace.desvio_max` e `erro`; `Get-ChildItem "$s\diagnostico_trace"` | P-19 | `diagnostico_trace\*.npz` | `erro` vazio nas 3 capturas. Matriz de execução: 1024 valores finitos, ou comando registrado como não suportado. `desvio_max` pequeno e constante entre TRACes. Se falhar: `set diagnostico retrieve off`, anotar a mensagem |
| 6.4 | CLI: `set capturas 6`, `run 09`, `set capturas padrao`, `set diagnostico retrieve off` | P-02 | `metadata\09_*.jsonl` | Executar com 6 capturas (9 se houver tempo) |
| 6.5 | Offline: `env\Scripts\python.exe diag\diag_ciclos_trace.py $s --classes 08,09` (uma pasta por classe se estiverem em `_run01`/`_run02`) | P-02 | `logs\diag_ciclos_trace-*.md` | 09: aceitar sem ressalva só captura sem ciclo trocado e resíduo perto de 100 ms < ~0,05 pu; acima disso, marcar como suspeita e não usar para treino |
| 6.6 | `quit` | | | |

Se a 08 reprovar por posição: **não repetir sozinho**; entregar `metadata\08_transient.jsonl` e `sessao.log`.

#### Bloco 7. 07 e 17 com recalibração (CLI, sessão B: 127 V / 60 Hz)

Por quê: a validação da crista agora usa o fator de extremo calibrado da classe. A 127 V/60 Hz os fatores do `logica\calibracao_extremos.json` (07: 1,186; 17: 1,031) **não cobrem** o toque simulado da fonte nos entalhes (~1,34 a 1,42 pu), então a **primeira rodada deve sair inválida pela crista**. A recalibração automática roda ao **fim** do run e só vale para o **run seguinte**.

```powershell
cd C:\Users\denis\TCC\code
scripts\START_BENCH.cmd
```

(`<FATOR escrito na probe>`, `127`, `60`.) Na CLI:

```
status
comm
set recalibracao on
run 07,17
```

- Digitar `EXECUTAR-CLASSES-07,17` (6 capturas, 72 gravações de TRACe; ~3 a 5 min por rodada).
- Ao fim, a CLI imprime `RECALIBRAÇÃO AUTOMÁTICA: N fator(es) de extremo MUDARAM` com `antes -> depois` (só sobe fator; condição sem tabela não ganha tabela) e guarda a cópia anterior em `<sessao>\calibracao_extremos.json`.
- Conferir a 1.ª rodada:

```powershell
cd C:\Users\denis\TCC\code
$s = (Get-ChildItem resultados -Directory | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
foreach ($c in "07","17") { Get-Content "$s\metadata\${c}_*.jsonl" | ForEach-Object { $j = $_ | ConvertFrom-Json; $v = $j.validacao_fisica; "{0} ok={1} crista {2:N3} aceita {3:N3}..{4:N3} (modelo {5:N3} x fator {6:N3}) thd {7:N4}/{8:N4} pico={9} vale={10} previsto={11}" -f $j.id_captura,$v.ok,$v.crista_medida,$v.crista_minima_aceita,$v.crista_maxima_aceita,$v.crista_modelo,$v.fator_extremo_crista,$v.thd_medida,$v.thd_esperada,$j.pico_medido_v,$j.vale_medido_v,$j.extremo_previsto_v } }
```

Esperado na 1.ª rodada: capturas `ok=False` **só** por "fator de crista", `thd_medida/thd_esperada` entre 0,8 e 1,2, `max(|pico|,|vale|)` abaixo de 415,8 V e, idealmente, abaixo de `extremo_previsto_v`. Depois, **sem sair da CLI**, repetir (os fatores novos já valem):

```
run 07,17
```

(`EXECUTAR-CLASSES-07,17` de novo.) Esperado na 2.ª rodada: `ok=True` em todas.

Depois da 2.ª rodada, sair da CLI (`quit`) e fechar o ciclo da calibração:

```powershell
cd C:\Users\denis\TCC\code
git diff -- logica\calibracao_extremos.json
env\Scripts\python.exe -m unittest tests.test_offline
git add logica\calibracao_extremos.json
git commit -m "chore: recalibra fatores de extremo 07 e 17 a 127 V/60 Hz"
git status
```

Depois do commit: `git log --oneline -1` e anote o **novo SHA**. A 1.ª rodada sai de commit limpo; a 2.ª sai de um checkout cujo `calibracao_extremos.json` foi reescrito pela recalibração e ainda não estava commitado (`git_sujo=true` esperado), e serve para **validar a calibração**, não como coleta da campanha. As sessões de coleta são as do Bloco 8 em diante, todas com `git_sujo` falso e `git_commit` = o SHA novo.

Conferir o `git diff`: fatores **só subiram**, só nas classes 07 e 17 da condição 127 V/60 Hz, valores plausíveis (a simulação pedia ~1,34 a 1,42 pu; fator calibrado >= 1,344 para a 07 e >= 1,420 para a 17 cobriria o máximo do modelo; valor menor que isso pode ainda reprovar). Se a suíte falhar após a mudança, entregar a saída antes de commitar.

Seguir se: 2.ª rodada `ok=True` em todas e suíte verde. Cenários diferentes: tabela da seção 3, linhas "07/17". Parar e avisar se: `max(|pico|,|vale|)` >= `extremo_previsto_v` por muito, ou perto de 415,8 V (achado de segurança; a bateria já aborta a classe se passar do teto). Tempo: 25 a 35 min com as duas rodadas, o `diff`, a suíte e o commit.

##### Passos por pendência: comando, P-NN, evidência e critério

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

#### Bloco 8. Verificações do sorteio = Parte 1 da campanha (CLI, sessão B, 60 Hz, **commit limpo**)

Reiniciar a CLI **depois** do commit do Bloco 7 (para `git_sujo` = falso e a calibração nova valer desde o início):

```powershell
cd C:\Users\denis\TCC\code
git status
scripts\START_BENCH.cmd
```

(`<FATOR escrito na probe>`, `127`, `60`.) Escolha antes o modo da campanha: **um perfil** (padrão `literatura`) ou `set perfil todos`. Para `todos`, digite `set perfil todos` agora e use a Parte 1 do plano `todos` (seção 5); a Parte 1 serve de verificação nos dois modos.

Um perfil (468 gravações de TRACe no total; esta parte: 36):

```
status
run 01-05,18-20
```

Digitar `EXECUTAR-CLASSES-01-05,18-20` (14 capturas, 36 gravações de TRACe, só a 20 usa TRACe). **Se o Bloco 5 mostrou que a 19 não deve ser coletada agora** (linha "ACDC", causa no caminho `VOLTage:TRIGgered`), troque por `run 01-05,18,20` (`EXECUTAR-CLASSES-01-05,18,20`).

Com `set perfil todos`: `run 01-05,17-19` (`EXECUTAR-CLASSES-01-05,17-19`; 20 capturas, 36 gravações de TRACe, 17 nativas) e a 20 vai na Parte 5 do plano `todos`.

Depois, offline (outro PowerShell):

```powershell
cd C:\Users\denis\TCC\code
$s = (Get-ChildItem resultados -Directory | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
env\Scripts\python.exe scripts\verificar_sessao_bancada.py $s --json logs\verificar_parte1.json
env\Scripts\python.exe logica\analisar_sessao.py $s
Select-String "$s\scpi_transcricao.log" -Pattern "PULSe:WIDTh"
Select-String "$s\scpi_transcricao.log" -Pattern "FREQuency" | Select-Object -Last 15
Select-String "$s\scpi_transcricao.log" -Pattern "MODE ACDC"
```

Conferir (critérios propostos, **sem dado de bancada**, os limiares do verificador são padrão do script):

| Item | Onde | Aprovado se |
|---|---|---|
| 18: continuidade de fase (57 -> 63 Hz) | linha `fase_18` do verificador | `\|salto\|` <= 10 graus; f1/f2 medidas a <= 0,2 Hz de `start_hz`/`end_hz`; `intersecao_ms` perto de 0 (salto grande com `intersecao_ms` ≈ 0 = a fase saltou; com `intersecao_ms` longe de 0 = a troca foi fora do meio, fase contínua) |
| 18: frequência base restaurada | `Select-String ... FREQuency` | `SOURce:FREQuency <base>` escrito depois da lista e sem erro `-2xx`; a classe seguinte (19) com `validacao_fisica.ok` |
| 02/03/04: largura do PULSe | linhas `largura_pulse` + `PULSe:WIDTh` | `\|erro\|` <= 2 ms em todas; readback igual ao escrito; sem erro SCPI. Erro sistemático (largura saturada) = limite de resolução do comando |
| Pré-trigger | linhas `pre_trigger` | `\|desvio\|` <= 2 amostras em todas (o mesmo limite do aviso do mestre); desvio constante = viés de `TIMebase:POSition` (registrar) |
| Disparo em fase (01, 05, 18, 19) | `analisar_sessao` | `\|lag\|` < 0,2 ms e correlação >= 0,99; fase ignorada aparece como correlação baixa ou lag de fração de ciclo (a 60 Hz, 1 grau ≈ 46 µs) |
| 05: a CSINusoid preserva o rms | `validacao_fisica.envelope_mediana_medida` de `05_*` | 0,7071 +- 0,01 e THD medido dentro de 20 % do pedido; ~0,72 invalida a premissa do modelo |
| 19 (se coletada): CA, CC | `analisar_sessao`, `validacao_fisica` de `19_*` | CA conforme o Bloco 5 (déficit conhecido); sem queda a 0 V entre capturas (`MODE ACDC` reenviado a cada captura é inócuo) |

Seguir se: os critérios passam, ou os que falham são registrados como achado (são dado de bancada, não infraestrutura). Parar se: infraestrutura (seção 0). Tempo: `run` ~1 a 3 min (nativas ~2,5 s por captura, mais 18 s da conexão e 36 gravações de TRACe da 20), verificações 3 a 5 min: 6 a 10 min.

##### Passos por pendência: comando, P-NN, evidência e critério

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

#### Bloco 8-A. Sequência da P-10: RMS e THD da 05 por nível (CLI, sessão B, 60 Hz, commit limpo)

Objetivo: medir RMS/THD da classe 05 em todos os níveis e rotas (norma 2 % e CSIN 5 a 20 %; TRACe 30 %). Sem `set capturas`, a 05 roda só o nível 0 do perfil; `set capturas 1` explícito agrupa por nível e roda os cinco (`docs/configuracao.md`, "Sequência da P-10"). Cada `run` é uma conexão própria e pede a **confirmação digitada pelo operador**; não use `set perfil todos` aqui. Mesma CLI do Bloco 8 (ou reinicie com `git status` limpo; fator `<FATOR escrito na probe>`, `127`, `60`).

```
set diagnostico bruto on
set perfil norma
set capturas 1
run 05
```

Digitar `EXECUTAR-CLASSE-05`. Esperado: 5 capturas, níveis 2/5/10/15/20 %, todos por CSIN (`rota_programacao` = `CSIN`), 0 gravações de TRACe. Depois, na mesma CLI:

```
set perfil literatura
set capturas 1
run 05
```

Digitar `EXECUTAR-CLASSE-05` de novo. Esperado: 5 capturas, níveis 5/10/15/20 % por CSIN e 30 % por TRACe, **12 gravações de TRACe** a 60 Hz (10 a 50 Hz), muito abaixo do orçamento de 216 por conexão. A estimativa que a CLI imprime pode não contar a 05 por TRACe (seção 8); o contador que vale é `escritas_trace_na_conexao` do metadata. Ao fim: `set capturas padrao` (e `set perfil literatura`, o padrão).

Conferir por nível, em `metadata\05_*.jsonl`: `parametros.thd`, `rota_programacao`, `validacao_fisica.envelope_mediana_medida` e o THD medido. Critério herdado da 05 (Bloco 8): envelope 0,7071 +- 0,01 e THD medido dentro de 20 % do pedido; ~0,72 invalida a premissa do modelo. Não há critério adicional por nível além deste; o agregador `scripts/fechar_pendencias.py` avalia a P-10 por nível e rota. Se a CLI mostrar estimativa de TRACe diferente de 0 (norma) e 12 (literatura) a 60 Hz, cancele e confira `status`.

##### Passos por pendência: comando, P-NN, evidência e critério

Cada `run` é uma conexão e pede confirmação digitada pelo operador (`EXECUTAR-CLASSE-05`); não usar `set perfil todos`. Opções conferidas em {doc}`configuracao` ("Sequência da P-10"): sem `set capturas` a 05 roda só o nível 0; `set capturas 1` explícito roda os cinco níveis.

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 8A.1 | CLI: `set diagnostico bruto on`, `set perfil norma`, `set capturas 1`, `run 05` | P-10, P-28 | `metadata\05_*.jsonl`, `.npz` da 05, `bruto_osciloscopio\` | 5 capturas: 2, 5, 10, 15 e 20 %, todas `rota_programacao` = `CSIN`; 0 gravações de TRACe |
| 8A.2 | CLI: `set perfil literatura`, `set capturas 1`, `run 05` | P-10 | idem | 5 capturas: 5, 10, 15, 20 % (CSIN) e 30 % (TRACe); 12 gravações de TRACe a 60 Hz (10 a 50 Hz), abaixo de 216; a estimativa da CLI pode não contar a 05 por TRACe (**NÃO VERIFICADO**), conferir `escritas_trace_na_conexao` |
| 8A.3 | Ler por nível `parametros.thd`, `rota_programacao`, `validacao_fisica.envelope_mediana_medida` e THD medido | P-10 | saída anotada | Critério herdado da 05: envelope 0,7071 +- 0,01 e THD medido dentro de 20 % do pedido. Não há critério adicional por nível; `scripts/fechar_pendencias.py` avalia por nível e rota |
| 8A.4 | CLI: `set capturas padrao`; `quit` | | | |

#### Bloco 9. Campanha em partes (mesma CLI do Bloco 8)

Os comandos, as contas de gravações de TRACe por conexão e os tempos estão na **seção 5**. Resumo do procedimento, para cada parte:

1. `status` (confere perfil, sorteio, que **não** há `set capturas`, e as capturas planejadas).
2. `run <lista>` e digitar `EXECUTAR-CLASSES-<lista normalizada>` (a CLI mostra a lista exata e a estimativa de TRACe antes de pedir).
3. Esperar o resumo `N/M classes OK`; **OUTPUT OFF no painel**.
4. Conferir, antes da parte seguinte: no `sessao.log` nenhuma linha `NÃO corresponde`; `validacao_fisica.ok` e `pico_medido_v`/`vale_medido_v` contra `extremo_previsto_v` (comando abaixo); o maior contador de TRACe da conexão.

```powershell
$s = (Get-ChildItem resultados -Directory | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
Get-Content "$s\metadata\*.jsonl" | ForEach-Object { ($_ | ConvertFrom-Json).escritas_trace_na_conexao } | Measure-Object -Maximum
foreach ($c in "10","11","12","16") { Get-Content "$s\metadata\${c}_*.jsonl" -ErrorAction SilentlyContinue | ForEach-Object { $j = $_ | ConvertFrom-Json; "{0} ok={1} pico={2} vale={3} previsto={4}" -f $j.id_captura,$j.validacao_fisica.ok,$j.pico_medido_v,$j.vale_medido_v,$j.extremo_previsto_v } }
```

Conferência extra na 1.ª sessão com as classes 10, 11, 12 e 16 (o rms por ciclo da TRACe mudou, o `LIST:VOLTage` agora é o rms da componente CA e o pico previsto vem da TRACe enviada): `VMAX`/`VMIN` medidos (`pico_medido_v`, `vale_medido_v`) **não** devem passar de `extremo_previsto_v` (a previsão antiga subestimava até 38 % em degraus). Se algum passar mas ficar abaixo de 415,8 V: registrar e rodar `env\Scripts\python.exe scripts\recalibrar_extremos.py $s` (sem `--gravar`); acima de 415,8 V a bateria já aborta a classe.

Seguir se: cada parte termina e os contadores ficam ≤ 216. Parar se: infraestrutura (seção 0), ou `pico_medido_v`/`vale_medido_v` perto do teto de 415,8 V (achado de segurança: avisar antes de continuar).

##### Passos por pendência: comando, P-NN, evidência e critério

Um `run` por conexão, cada parte com no máximo 216 gravações. Reinicie a CLI entre partes se a seção 5 pedir conexão nova (cada `run` abre uma conexão). Confirmação `EXECUTAR-CLASSES-<lista normalizada>` digitada pelo operador; a CLI mostra a lista exata e a estimativa antes de pedir. Manter `set diagnostico bruto on` se for desejado o bruto também nas classes TRACe (consumo de disco: **NÃO VERIFICADO**).

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 9.1 (1 perfil, Parte 2) | `run 06-11` | P-01, P-08, P-23, P-28 | `resultados\sessao_*\` (por parte) | 216 gravações a 60 Hz (180 a 50 Hz); resumo `N/M classes OK`; OUTPUT OFF no painel |
| 9.2 (1 perfil, Parte 3) | `run 12-17` | P-01, P-08, P-23, P-28 | idem | idem |
| 9.3 (`todos`, Partes 2 a 6) | `run 06,10`; `run 11,12`; `run 13,14`; `run 15,16`; `run 07-09,20` | idem | idem | Cada parte 216 gravações a 60 Hz (seção 5.2). Sem a 08, 07 ou 17 (tabela de decisão): ajustar as listas conforme seção 5.1 |
| 9.4 | Após cada parte: contador máximo `escritas_trace_na_conexao` (`Measure-Object -Maximum`, roteiro Bloco 9) | P-23 | saída anotada | <= 216. A causa física da trava de ~280 gravações só se fecha com diagnóstico real (matriz de execução, P-23); este roteiro não faz ensaio cego até travar |
| 9.5 | Após cada parte: `sessao.log` sem `NÃO corresponde`; pico/vale de 10, 11, 12, 16 contra `extremo_previsto_v` (comando do roteiro, Bloco 9) | P-08, P-01 | saída anotada | `pico_medido_v`/`vale_medido_v` não passam de `extremo_previsto_v`. Se passarem e ficarem abaixo de 415,8 V: registrar e rodar `env\Scripts\python.exe scripts\recalibrar_extremos.py $s` (sem `--gravar`). Perto de 415,8 V: achado de segurança, avisar antes de continuar |

#### Bloco 10. Entrega (seção 6)

Medições e agregação (offline, **no PC da bancada** onde indicado; CLI fechada, OUTPUT OFF; nenhuma destas etapas energiza nem digita confirmação):

```powershell
cd C:\Users\denis\TCC\code
# P-22: custo de I/O das sessões físicas, medido NO PC DA BANCADA (grava hostname e simulado)
env\Scripts\python.exe diag\benchmark_sessao_io.py --sessao <dir_sessao_1> [--sessao <dir_sessao_2> ...] --saida logs\benchmark_sessao_io_bancada.json
# P-31: comparação modelo x programada nas sessões físicas
env\Scripts\python.exe diag\analisar_modelo_programado.py --sessao <dir_sessao_1> [--sessao <dir_sessao_2> ...] --saida logs\modelo_programada_sessoes_bancada.json
```

`--saida` não sobrescreve arquivo existente. Fechamento (pode rodar no computador de análise, com as pastas copiadas; `--artefatos` aceita `logs` e `resultados\passo_final_sin_*`):

```powershell
python scripts/fechar_pendencias.py --sessao <dir> [--sessao <dir> ...] --artefatos logs --artefatos resultados --pc-bancada docs/evidencias/<data>/pc_bancada.json --saida docs/evidencias/<data>/fechamento.json
```

O fechamento só reúne evidência e **não encerra pendência**: a decisão é do responsável. Ver a seção 9.

##### Passos por pendência: comando, P-NN, evidência e critério

OUTPUT OFF no painel e CLI fechada (`quit`).

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 10.1 | `git status`; `git log -3 --stat -- logica\calibracao_extremos.json`; `env\Scripts\python.exe -m unittest tests.test_offline` | P-07, P-21, P-16 | saídas anotadas | Nenhum rastreado alterado; suíte com 0 falhas (seção 6, itens 2 a 4) |
| 10.2 | Conferir `git_commit`/`git_sujo` das sessões (comando do roteiro, seção 6, item 5) | P-01 | saída anotada | `git_sujo` falso e `git_commit` igual ao commit limpo |
| 10.3 | `env\Scripts\python.exe logica\recortar_margem.py $s`, `env\Scripts\python.exe logica\relatorio_html.py $s\sem_margem --dpi 80`, `env\Scripts\python.exe logica\analisar_sessao.py $s` | P-01 | relatório HTML, análise | Opcional; seção 6, item 6 |
| 10.4 | **No PC da bancada**: `env\Scripts\python.exe diag\benchmark_sessao_io.py --sessao <dir_sessao_1> [--sessao <dir_sessao_2> ...] --saida logs\benchmark_sessao_io_bancada.json` | P-22 | `logs\benchmark_sessao_io_bancada.json` (recusa sobrescrita) | Mede as sessões físicas sem modificá-las (leitura, reescrita em cópia temporária, hash, memória, tamanho) e grava `hostname` e `simulado`. `fechar_pendencias.py` só avalia "executado no PC da bancada" se o `hostname` do artefato coincidir com o de `pc_bancada.json` (sem diferenciar maiúsculas, tolerando o truncamento NetBIOS de 15 caracteres); benchmark sintético (sem `--sessao`) ou `simulado` verdadeiro nunca vale como medição da bancada. Não há limite de tempo/tamanho definido no código/docs: critério numérico não definido, revisão humana |
| 10.5 | Para cada NPZ de `bruto_osciloscopio\<perfil>\` do CH1: `env\Scripts\python.exe diag\analisar_reamostragem.py --entrada <bruto_CH1.npz> --f0-hz 60 --harmonicos 10 --saida <analise_bruto_novo.json>` (`--f0-hz 50` para sessões a 50 Hz) | P-28 | `analise_bruto_novo.json` por arquivo | Publica RMS, pico, erro temporal, espectro e THD na grade salva. Critério de aceite numérico não definido; a matriz pede revisão dos resultados físicos. O FIR não substitui o interpolador do dataset |
| 10.6 | `env\Scripts\python.exe diag\analisar_modelo_programado.py --sessao <dir_sessao_1> [--sessao <dir_sessao_2> ...] --saida logs\modelo_programada_sessoes_bancada.json` | P-31 | `logs\modelo_programada_sessoes_bancada.json` (não sobrescreve) | Cálculo reprodutível sobre as sessões físicas (métricas nominal e fundamental ajustada). `fechar_pendencias.py` verifica capturas físicas com `tres_versoes` nas classes 06, 10, 11, 12, 15 e 16. A métrica oficial é decisão do responsável; critério numérico não definido |
| 10.7 | Copiar para o computador de análise (seção 6, item 7): `resultados\sessao_*` inteiras, HTML, e de `logs\` os `diag_ciclos_trace-*`, `diag_marcadores_trace-*`, `diag_acdc_amplitude-*`, `diag_nativo-*`, `verificar_parte1.json`, `preflight_new-*.log` | todas | pastas copiadas | Sessões originais imutáveis; análises derivadas em outro destino |
| 10.8 | Anotar uma linha por bloco (seção 6, item 8): valor medido, fator da probe, fatores 07/17 antes e depois, contador máximo de TRACe, o que ficou fora da campanha e por quê | todas | anotação | Valor medido, não impressão |

#### Bloco 10-A. Passo final SINE (P-18; extensão ao roteiro dos Blocos 1 a 10). Sem estimativa

Extensão ao roteiro (os Blocos 1 a 10 não a incluem): vem de {ref}`passo-final-sine` (seção 7.4 de `docs/codigo/ametek_orm.md`). Só depois dos Blocos 1 a 10, com a CLI fechada, a COM10 livre e **conexão própria** (o orçamento de 216 gravações vale também aqui; a conta do script não é a da CLI: **NÃO VERIFICADO**). Confirmação `ENERGIZAR-PASSO-SIN` digitada pelo operador, que informa o fator da probe, a tensão e a frequência quando o script perguntar.

| Passo | Comando exato | P-NN | Arquivo de evidência | Critério de aceite |
|---|---|---|---|---|
| 10A.1 | `env\Scripts\python.exe diag\teste_passo_final_sin.py --classe 06 --repeticoes 1` | P-18 | `resultados\passo_final_sin_<data>\registros.npz` e `resultado.json`; `logs\` do script | Código de saída 0. rms por ciclo da margem final com o passo = 1,00 +- 0,01 pu; janela rotulada com e sem o passo: correlação >= 0,999 e diferença máxima de rms por ciclo <= 0,01 pu; nenhum erro SCPI. Limiares são escolha do autor do script, sem dado de bancada |
| 10A.2 | Se aprovado: `run 06` pela CLI e conferir as três versões ({doc}`tres_versoes`) | P-18 | sessão | Restauração na fonte e aceitação LIST observadas; critério numérico não definido. O **padrão do passo continua OFF** até o responsável decidir (P-26/D) |

#### Bloco 10-B. Experimento P-09 A/B/C (extensão ao roteiro dos Blocos 1 a 10). Sessão B, 127 V/60 Hz, depois do Bloco 5 (P-17)

Objetivo: decidir pela medição se o offset DC por passo de LIST recupera a média por ciclo que a TRACe perde (decisão P-09 em `projeto/pendencias.md`). Mesmas classes, seed, perfil e condição nos três braços; só muda `set p09`.

| Passo | Comando | P-NN | Evidência | Critério |
|---|---|---|---|---|
| 10B.1 | **Sem energizar:** com a CLI fechada, `env\Scripts\python.exe diag\diag_list_offset.py --saida logs\diag_list_offset.json` (o script só consulta e mantém OUTPUT OFF) | P-09 | `logs\diag_list_offset.json` | Se `SOURce:LIST:VOLTage:OFFSet` **não** for aceito: pular 10B.3 (braço C), rodar só A e B e fechar a P-09 como limitação aceita, com as métricas (d) |
| 10B.2 | CLI: `set p09 A`, `run 10-12,16` (confirmação digitada) | P-09, P-17 | sessão A | Linha de base |
| 10B.3 | CLI: `set p09 C`, `run 10-12,16` | P-09 | sessão C | Só se 10B.1 confirmou o comando; a CLI recusa C antes de energizar se a fonte não aceitar |
| 10B.4 | CLI: `set p09 B`, `run 10-12,16` | P-09, P-17 | sessão B | Controle: AC+DC sem offset, isola o déficit da P-17 |
| 10B.5 | Offline: `env\Scripts\python.exe diag\analisar_modelo_programado.py --sessao <A> --sessao <B> --sessao <C> --classes 10 11 12 16 --saida logs\p09_abc.json` | P-09 | `logs\p09_abc.json` | C melhor que A e B na correlação medida × modelo e no erro de média por ciclo, sem violar picos → adotar C; caso contrário, manter A e aceitar a limitação |

Observações: com B/C a conexão inteira fica em AC+DC (inclusive classes nativas). Os offsets de LIST são zerados fora das capturas C e no desligamento. Volte para `set p09 A` antes da campanha principal, a menos que o resultado mande adotar C.

### 3. Tabela de decisão: o que muda na campanha do mesmo dia

Convenção: "proposta" é a recomendação deste roteiro; a decisão final é de quem opera. Nenhuma linha autoriza afrouxar tolerância, `max_peak_v`, `max_voltage_rms` ou `max_current_a`, nem mexer em `gerar()` ou em `calibracao_extremos.json` fora da recalibração automática.

| Diagnóstico | Resultado possível | Leitura | O que muda na campanha do mesmo dia |
|---|---|---|---|
| Ciclos (offline, Bloco 3) | Cópia em ~100 ms acusada nos dados de 07/10 (08 a 50 Hz; 09 a 50 e 60 Hz), ciclos explicados por `k-1` | Defeito conhecido do dado; **não** distingue o mecanismo | Nada muda sozinho: o Bloco 4 decide. Guardar `logs\diag_ciclos_trace-*.md/.json` |
| Ciclos (offline) | Script falha ao carregar a sessão antiga | Caminho `.npz` bruto + reconstrução não testado com dado real | Nada muda; entregar a mensagem; seguir para os blocos 4 e 6 |
| Marcadores (Bloco 4) | A cópia fica em ~100 ms **nos dois instantes** de evento (40 e 80 ms): instante fixo | Artefato ligado a um instante da lista/TRACe, independente do evento | Campanha **completa**, sem recapturar. Toda classe TRACe com evento perto de 100 ms carrega o impulso espúrio (09 sorteada: ~18 % das capturas caem dentro do evento). Marcar essas capturas e excluir a janela de ~2 ms em torno de 100 ms na análise e no treino (código/análise **depois**, fora do dia) |
| Marcadores | A cópia **acompanha** o evento (+1 ciclo) ou os marcadores mostram ciclo k tocando k-1 | Troca de passo: a fonte toca o ciclo anterior a partir de um instante; o evento aparece 1 ciclo depois | Os rótulos de posição das classes TRACe (todas as que mudam de forma entre ciclos) ficam deslocados por 1 ciclo a partir daí. **Proposta**: coletar só a Parte 1 sem a 20 (`run 01-05,18-19`, sem TRACe) e **suspender as Partes 2 e 3**; entregar os arquivos do Bloco 4 para a correção ser decidida (o modelo `atraso_de_passos` em `logica/modelo_lista_fonte.py` já prevê esse mecanismo) |
| Marcadores | Atraso global constante de 1 a 2 amostras, sem outra cópia | Atraso da subida da fonte | Nada muda; registrar o atraso |
| Marcadores | Atraso global >= 3 amostras, ou variando entre capturas | Jitter/viés de trigger | Conferir `pre_trigger_desvio_amostras` na Parte 1; seguir; registrar |
| Marcadores | Não reconhece os marcadores (lombada achatada pela banda da fonte) ou o script recusa | Inconclusivo | Nada muda; usar o `retrieve` da 08 (Bloco 6) e o resultado da 09 como evidência; campanha completa com a ressalva do mecanismo NÃO VERIFICADO |
| Retrieve (Bloco 6) | `lido` ≈ `enviado` (desvio pequeno e constante) **e** a cópia aparece na medida | A gravação na Flash está certa; o problema é a reprodução (LIST/trigger) | Nada muda no dia; reforça "instante fixo"/troca de passo (linhas de marcadores) |
| Retrieve | `lido` difere de `enviado` justo na região do evento | Problema na escrita da TRACe | Parar as Partes 2 e 3 e entregar `diagnostico_trace\*.npz`: a correção seria na gravação, antes de gastar a Flash |
| Retrieve | `erro` na leitura (query inexistente ou formato desconhecido) | Query não disponível nesta revisão | `set diagnostico retrieve off`; a campanha não depende dele; anotar a mensagem |
| ACDC (Bloco 5) | Linhas 1 e 5 ≈ 1,000; linha 2 ≈ linha 3 ≈ 0,94 a 0,95 | Déficit é do modo ACDC, não do STEP | Coletar a 19 normalmente (CA = g x nominal, medido no metadata); a compensação `V/g` é mudança de código fora do dia. Registrar `g` por condição |
| ACDC | Linha 3 ≈ 1,000 e linha 2 ≈ 0,95 | O déficit vem do caminho `VOLTage:TRIGgered` | **Não coletar a 19 hoje** (`run 01-05,18,20`): trocar para `VOLTage` imediato muda o fluxo da classe e o dado teria de ser refeito |
| ACDC | `g` diferente entre 127 V/50, 127 V/60 e 230 V/50 | `g` é função de (V, f) | Não coletar a 19 se houver compensação planejada (seria refeita); senão coletar e anotar `g` da condição 127 V/60 Hz |
| ACDC | `VOLTage:RANGe?` em ACDC diferente de 300 | A faixa muda com o modo (H5) | Coletar a 19 só com a anotação; avisar |
| ACDC | Linha 5 diferente da linha 1 | Deriva temporal contaminou a comparação | Repetir a condição 2 vezes; não decidir com uma execução |
| ACDC | CC a 60 Hz com +1,9 V acima do viés | Anomalia de 07/10 repetida | Coletar a 19; registrar; investigar depois |
| 08 (Bloco 6) | `ok=True`, impulso em 90 ms (`pico_medido_amostra` ≈ 2700), `desvio` dentro de +-3, pico <= 374,2 V | Correção da posição confirmada a 50 Hz | Nada muda. A 08 a 60 Hz roda na campanha como está (impulso em 80 ms, amostra 400 de 500, longe da fronteira) |
| 08 | Reprova por posição (impulso em 100 ms ou outro) | Mecanismo não é só a fronteira de ciclo; combinar com os marcadores | Não repetir sozinho. A 08 a 60 Hz roda na campanha com a ressalva; entregar `08_transient.jsonl` e `sessao.log` |
| 08 | Pico > 374,2 V ou sobressinal > 0,55 | Achado de segurança | **Tirar a 08 da campanha** (`06-07,09-11` no lugar de `06-11`, ver seção 5) e avisar antes de continuar |
| 09 (Bloco 6) | Capturas sem ciclo trocado e resíduo perto de 100 ms < ~0,05 pu | Limpa | Aceitar sem ressalva; a 09 da campanha (3 capturas) segue normal |
| 09 | Ciclo trocado ou resíduo >= 0,05 pu em alguma | Cópia em 100 ms presente | Manter, marcar como suspeita, não usar para treino; a 09 da campanha roda igual (mais 3 capturas suspeitas possíveis); segue a linha de Marcadores correspondente |
| 07/17 (Bloco 7) | 1.ª rodada inválida **só** por crista; recalibração sobe os fatores; 2.ª rodada `ok=True` | Esperado | Commitar o JSON recalibrado, reiniciar a CLI; 07 e 17 entram normais nas Partes 2 e 3 |
| 07/17 | 1.ª rodada já `ok=True` (a fonte atenuou os entalhes menos que o modelo) | Fatores calibrados bastam | A recalibração pode não mudar nada (`git diff` vazio, nenhum commit necessário); seguir |
| 07/17 | 2.ª rodada ainda reprova por crista (acima de crista x fator x 1,1) | O fator recalibrado ainda não cobre | Não afrouxar tolerância (fora de autorização). Tirar 07 e 17 da campanha (`06,08-11` e `12-16`); entregar as sessões; decisão de tolerância própria por classe fica para depois do dia |
| 07/17 | Reprova por THD ou envelope | Achado novo (a fonte atenua os entalhes) | Mesmo tratamento: sem 07/17 na campanha, entregar |
| 07/17 | `max(\|pico\|,\|vale\|)` perto de 415,8 V ou maior que `extremo_previsto_v` por margem grande | Previsão de pico insuficiente | Parar 07/17; recalibrar; avisar antes de 220/380 V |
| Suíte no Windows (Bloco 1) | 0 falhas; skips só os dois de hash específico de plataforma, se houver | Fixtures portáveis valem no Windows | Seguir; registrar em `pc_bancada.json` (`validar_pc_bancada.ps1`) |
| Suíte no Windows | Falha de assinatura portável | Diferença maior que o último bit de `np.sin` | Não coletar; entregar a saída |
| Rms por ciclo (Parte 2/3) | `pico_medido_v`/`vale_medido_v` das 10/11/12/16 maiores que `extremo_previsto_v` | Previsão ainda subestima | Seguir se < 415,8 V; registrar; recalibrar depois da parte |

### 4. Modelo de tempo e de gravações de TRACe

- Gravações de TRACe de uma classe = (capturas da classe que gravam TRACe) x (ciclos da janela = 0,2 s x frequência: **12 a 60 Hz, 10 a 50 Hz**). A conta é exata com sorteio ligado (padrão): cada captura TRACe regrava a Flash. Fonte da conta: `capturas_efetivas_da_classe` (`logica/mestre.py`) e `_aviso_escritas_trace` (`logica/cli.py`), a mesma estimativa que a CLI mostra antes de pedir a confirmação.
- Tempo de uma conexão (`run`) ≈ **18 s** (abertura, `*IDN?`, baseline, checagem da cadeia) + **~3 s x min(ciclos, 12)** (definição das TRACes novas na Flash, na 1.ª captura da conexão: 36 s a 60 Hz, 30 s a 50 Hz) + **~2 s x gravações de TRACe** + **~2,5 s x capturas nativas**.
- Esses números vêm das medidas citadas nos relatórios desta rodada (1 s de espera por TRACe mais overhead de consulta e osciloscópio; ~2,5 s por captura nativa). **NÃO VERIFICADO**: nenhuma bateria completa foi cronometrada; use a coluna "x 1,5" como valor de planejamento.
- Referência: o `run all` de uma conexão só (que **não** será usado) daria 468 gravações a 60 Hz (390 a 50 Hz), 17,0 min no modelo; e a trava ocorreu na ~280.ª.

### 5. Plano da campanha em partes (127 V, 60 Hz)

Contas feitas rodando offline `_capturas_das_classes`/`capturas_efetivas_da_classe` com `BASE_VOLTAGE_RMS=127`, `GRID_FREQUENCY_HZ=60` e `50`, sorteio ligado, 3 capturas padrão. As capturas por classe são iguais nos três perfis (as classes TRACe têm 3 capturas e 36 gravações a 60 Hz, 30 a 50 Hz; 01, 02, 03, 05, 18 têm 1 captura; 04 e 19 têm 3). Classes com TRACe: 06 a 17 e 20 (13 classes). Nativas (sem TRACe): 01 a 05, 18, 19 (11 capturas).

#### 5.1 Um perfil (`literatura`, padrão): 468 gravações no total em 3 conexões

| Parte | Comando | Confirmação | Capturas | Gravações de TRACe (60 Hz / 50 Hz) | Tempo (60 Hz / 50 Hz) |
|---|---|---|---|---|---|
| 1 (Bloco 8) | `run 01-05,18-20` | `EXECUTAR-CLASSES-01-05,18-20` | 14 | **36** / 30 | 2,6 min (3,8 min x 1,5) / 2,3 min (3,4) |
| 2 | `run 06-11` | `EXECUTAR-CLASSES-06-11` | 18 | **216** / 180 | 8,1 min (12,2) / 6,8 min (10,2) |
| 3 | `run 12-17` | `EXECUTAR-CLASSES-12-17` | 18 | **216** / 180 | 8,1 min (12,2) / 6,8 min (10,2) |
| Total | | | 50 | 468 / 390 | 18,8 min (28,1) / 15,9 min (23,8) |

Maior conexão: 216 gravações a 60 Hz (≤ 216). Sem a 19 (Bloco 5 recomendou): Parte 1 = `run 01-05,18,20`, 11 capturas. Sem a 08 (tabela): Parte 2 = `run 06-07,09-11` (`EXECUTAR-CLASSES-06-07,09-11`), 180 gravações. Sem 07/17: Parte 2 = `run 06,08-11`, Parte 3 = `run 12-16`.

#### 5.2 `set perfil todos`: 1116 gravações (60 Hz) / 930 (50 Hz) em 6 conexões

Com `todos`, as classes que dependem do perfil (02, 03, 05, 06, 10 a 16, 20) rodam uma vez por perfil (norma, literatura, fronteira); as 8 que não dependem (01, 04, 07, 08, 09, 17, 18, 19) rodam **uma só vez**, sob `literatura`, e o metadata dos outros perfis aponta para a mesma captura. Um `run <lista>` percorre tudo numa conexão só, então a lista precisa caber em ≤ 216 gravações: uma classe TRACe dependente de perfil custa 108 (60 Hz) / 90 (50 Hz).

Digitar antes: `set perfil todos` (e conferir em `status`).

| Parte | Comando | Confirmação | Capturas | Gravações de TRACe (60 Hz / 50 Hz) | Tempo (60 Hz / 50 Hz) |
|---|---|---|---|---|---|
| 1 (Bloco 8) | `run 01-05,17-19` | `EXECUTAR-CLASSES-01-05,17-19` | 20 (17 nativas) | **36** / 30 | 2,8 min (4,2 min x 1,5) / 2,5 min (3,8) |
| 2 | `run 06,10` | `EXECUTAR-CLASSES-06,10` | 18 | **216** / 180 | 8,1 min (12,2) / 6,8 min (10,2) |
| 3 | `run 11,12` | `EXECUTAR-CLASSES-11-12` | 18 | **216** / 180 | 8,1 (12,2) / 6,8 (10,2) |
| 4 | `run 13,14` | `EXECUTAR-CLASSES-13-14` | 18 | **216** / 180 | 8,1 (12,2) / 6,8 (10,2) |
| 5 | `run 15,16` | `EXECUTAR-CLASSES-15-16` | 18 | **216** / 180 | 8,1 (12,2) / 6,8 (10,2) |
| 6 | `run 07-09,20` | `EXECUTAR-CLASSES-07-09,20` | 18 | **216** / 180 | 8,1 (12,2) / 6,8 (10,2) |
| Total | | | 110 | 1116 / 930 | 43,3 min (65,0) / 36,5 min (54,8) |

Maior conexão: 216 gravações (≤ 216). Se alguma classe sair do plano (08, 07/17, 19), a soma só diminui; nenhuma combinação deste plano passa de 216. As partes 2 a 5 têm 2 classes dependentes de perfil (2 x 108); a 6 junta 3 classes de uma execução (36 cada) e a 20 (108). A 17 está na Parte 1 (nativas + 17: 36 gravações).

A estimativa que a CLI imprime antes de cada confirmação (`TRACe: N gravações ...`) deve **bater** com a coluna "Gravações de TRACe" destas tabelas; se não bater, a CLI está vendo outra configuração (`set capturas` esquecido, perfil errado, frequência errada): cancelar (qualquer texto diferente da confirmação) e conferir `status`.

#### 5.3 Frequência da campanha

Esta seção assume 60 Hz. Se a campanha for a 50 Hz, a 08 recapturada no Bloco 6 já é a da campanha; neste caso rode o Bloco 7 também a 50 Hz (os fatores de 07/17 a 127 V/50 Hz são 1,375 (07) e 1,307 (17); a simulação previa que cobrem quase tudo) e use as colunas "50 Hz".

### 6. Checklist de entrega ao fim do dia

1. **OUTPUT OFF** no painel da AMETEK; CLI fechada (`quit`); nada energizado.
2. `git status` na raiz: lista do que mudou. Esperado: nenhum arquivo rastreado alterado (o JSON recalibrado já foi commitado no Bloco 7). Qualquer outra alteração rastreada: entregar.
3. **Recalibração conferida**: `git log -3 --stat -- logica\calibracao_extremos.json` e `git diff HEAD~1 -- logica\calibracao_extremos.json` (fatores só subiram, nas classes e condição esperadas); e a cópia anterior em `resultados\sessao_<...>\calibracao_extremos.json` da sessão do Bloco 7.
4. **Suíte** depois do commit: `env\Scripts\python.exe -m unittest tests.test_offline` (0 falhas).
5. **Sessões de campanha**: confirmar que `git_sujo` é falso e `git_commit` é o commit limpo:

```powershell
cd C:\Users\denis\TCC\code
Get-ChildItem resultados -Directory | Sort-Object LastWriteTime | Select-Object -Last 8 | ForEach-Object { $m = Get-ChildItem "$($_.FullName)\metadata\*.jsonl" -ErrorAction SilentlyContinue | Select-Object -First 1; if ($m) { $j = Get-Content $m.FullName -TotalCount 1 | ConvertFrom-Json; "{0}: git_commit={1} git_sujo={2} versao={3}" -f $_.Name,$j.git_commit,$j.git_sujo,$j.versao_codigo } }
```

6. **Relatório HTML** (offline; uma sessão por vez; pode levar minutos e passar de 20 MB; `--classes` ou `--max-capturas-por-classe` ou `--dpi 80` reduzem):

```powershell
cd C:\Users\denis\TCC\code
$s = "resultados\sessao_<timestamp da parte>"
env\Scripts\python.exe logica\recortar_margem.py $s
env\Scripts\python.exe logica\relatorio_html.py $s\sem_margem --dpi 80
env\Scripts\python.exe logica\analisar_sessao.py $s
```

(com `set html on` na CLI isso roda sozinho ao fim de cada `run` bem-sucedido; falha só avisa.)

7. **O que copiar** (para o computador de análise), por sessão: a pasta `resultados\sessao_<timestamp>[_runNN]` inteira (inclui `sessao.log`, `scpi_transcricao.log`, `sessao.json`, `calibracao_extremos.json` da sessão, `metadata\`, os `.npz` por classe, `diagnostico_trace\` se houve retrieve) e o HTML; mais, de `logs\`: `diag_ciclos_trace-*.md/.json`, `diag_marcadores_trace-*.md/.json/.log/-scpi.log`, `diag_acdc_amplitude-*.md/.json/.log/-scpi.log`, `verificar_parte1.json`, `benchmark_sessao_io_bancada.json`, `modelo_programada_sessoes_bancada.json` e os `preflight_new-*.log` do dia; mais `pc_bancada.json` (`validar_pc_bancada.ps1`) e, se houve o passo P-18, `resultados\passo_final_sin_<data>\`. Opcional: `scripts\package_windows.ps1`.
8. **Anotar numa linha por bloco** (valor medido, não impressão): fator da probe usado; resultado dos Blocos 3, 4, 5 (linha da tabela de decisão aplicada); fatores 07/17 antes e depois; contador máximo de TRACe por conexão (`escritas_trace_na_conexao`); qual 19/08/07/17 ficaram fora da campanha e por quê.
9. Pendências para o responsável (decidir depois do dia): mecanismo da cópia em 100 ms (se não resolvido); compensação do ganho ACDC; tolerância própria de crista por classe (se 07/17 ainda reprovaram); janelas a excluir em torno de 100 ms.

### 7. Conferência dos comandos e confirmações no código

Cada item abaixo foi conferido com `git grep` na árvore deste roteiro:

| Item do roteiro | Evidência |
|---|---|
| `scripts\START_BENCH.cmd` | `scripts/START_BENCH.cmd`; pergunta do fator/tensão/frequência: `scripts/start_bench_windows.ps1` |
| Comandos `status`, `list`, `comm`, `trigger`, `lowvoltage`, `native`, `run`, `set`, `quit` | `logica/cli.py`: `HELP_TEXT` (l. 59-) e `COMANDOS` |
| `ENERGIZAR-TESTE` | `logica/cli.py:691` |
| `ENERGIZAR-COMANDOS` | `logica/cli.py:706` |
| `EXECUTAR-CLASSE-<NN>` | `logica/cli.py:762` |
| `EXECUTAR-CLASSES-<lista normalizada>` | `logica/cli.py:750` (`_run_lista`); a lista normalizada de cada comando deste roteiro foi gerada por `normalizar_lista_classes` (`cli.py:235`) |
| `EXECUTAR-20-CLASSES` (não usado hoje) | `logica/cli.py:823` |
| `ENERGIZAR-MARCADORES` | `diag/diag_marcadores_trace.py:81` |
| `ENERGIZAR-ACDC` | `diag/diag_acdc_amplitude.py:68` |
| `set diagnostico retrieve on\|off`, `set capturas <N>\|padrao`, `set perfil todos`, `set recalibracao on\|off`, `set html on\|off`, `set sorteio` | `logica/cli.py`: `cmd_set` e `HELP_TEXT` |
| `run 07,17`, `run 01-05,18-20` (lista) | `logica/cli.py`: `parsear_lista_classes`, `normalizar_lista_classes`, `_run_lista` |
| `diag_ciclos_trace.py <sessao> --classes` | `diag/diag_ciclos_trace.py` (`--classes`, `--sem-forma-bancada`, `--saida`) |
| `diag_marcadores_trace.py --probe --vrms --frequencias --variantes` | `diag/diag_marcadores_trace.py` |
| `diag_acdc_amplitude.py --probe --vrms --hz --testar-compensacao` | `diag/diag_acdc_amplitude.py` |
| `verificar_sessao_bancada.py <sessao> --json` | `scripts/verificar_sessao_bancada.py` |
| `recalibrar_extremos.py <sessao>` (sem `--gravar`) | `scripts/recalibrar_extremos.py` |
| `ENERGIZAR-PASSO-SIN` (só P-18) | `diag/teste_passo_final_sin.py:33` (`CONFIRMACAO`) |
| `benchmark_sessao_io.py --sessao --saida` (P-22) | `diag/benchmark_sessao_io.py` (`main`) |
| `analisar_modelo_programado.py --sessao --saida` (P-31) | `diag/analisar_modelo_programado.py` (`main`) |
| `fechar_pendencias.py --sessao --artefatos --pc-bancada --saida` | `scripts/fechar_pendencias.py` (`main`; `--artefatos` repetível) |
| `set diagnostico bruto on\|off` (P-28) | `logica/cli.py`: `cmd_set` e `HELP_TEXT` |
| `analisar_sessao.py`, `recortar_margem.py`, `relatorio_html.py` | `logica/analisar_sessao.py`, `logica/recortar_margem.py`, `logica/relatorio_html.py` |
| Campos do metadata usados nos `Get-Content` | `logica/mestre.py` (`id_captura`, `pico_medido_v`, `vale_medido_v`, `extremo_previsto_v`, `indice_trigger`, `escritas_trace_na_conexao`, `diagnostico_trace`), `logica/sinais.py` (`crista_*`, `fator_extremo_crista`, `thd_*`), `experimentos_waveform/08.py` (`posicao_evento`, `inicio_impulso_s`) |

### 8. Limites deste roteiro (NÃO VERIFICADO)

- Nada foi executado na bancada. Tempos são estimativas do modelo da seção 4; conferir o primeiro `run` contra o relógio e ajustar o resto do dia.
- A suíte no Windows, o formato dos `.npz` das sessões de 07/10 em `diag_ciclos_trace.py`, `TRACe:DATA?` na fonte, os limiares do verificador (10 graus, 2 ms, 2 amostras) e a leitura de marcadores (limiares de 12 amostras de posição e 25 % de amplitude) são propostas sem dado de bancada.
- O mecanismo da cópia em 100 ms, a causa do déficit ACDC e o toque real da fonte nos entalhes das 07/17 continuam em aberto até este dia.
- A 05 por TRACe (nível de 30 %) não entra na conta de gravações da estimativa da CLI (a 05 aparece com 0 gravações com 1 captura padrão); no Bloco 8-A (`set capturas 1`, perfil `literatura`) o esperado é 12 gravações a 60 Hz, **NÃO VERIFICADO**: recontar com `status` e conferir `escritas_trace_na_conexao`.

### 9. Roteiro de fechamento por pendência: pré-condições, campanhas por condição e entrega

Esta seção reúne o que o roteiro de fechamento das pendências físicas acrescenta ao roteiro dos blocos: a visita num comando, as pré-condições, o mapa de pendências por bloco, as campanhas por condição e a entrega ao coordenador. Visita que gera a evidência para P-01, P-02, P-03, P-05, P-06, P-07, P-08, P-10, P-16, P-17, P-18, P-19, P-21, P-22, P-23, P-28 e P-31, com P-26 como pré-condição a decidir antes de energizar (a decisão está na seção P-26 do formulário em {doc}`projeto/pendencias`). A sequência, os diagnósticos e os critérios são os dos Blocos acima; as tabelas "Passos por pendência" só os organizam por pendência. Operação da CLI: {doc}`operacao`. Nenhum passo encerra pendência por si: a visita gera evidência.

#### 9.1 A visita inteira num comando

No PC da bancada: **`scripts\VISITA_BANCADA.cmd`** (atalho na área de trabalho). Ele pergunta o fator da probe e conduz, na ordem, todos os blocos abaixo, inclusive 8-A, 10-A, 10-B e as campanhas por condição (P-26, com a calibração P-21 de 220 V e 33 V), e termina com o fechamento (`fechamento.json`) e o commit das evidências. O comando:

- muda a tensão e a frequência sozinho, por etapa;
- confere a segurança depois de cada sessão;
- para em falha de infraestrutura;
- pergunta se você quer rodar de novo só as capturas que falharam.

**Você continua digitando a confirmação de cada etapa que energiza.** Pode parar em qualquer pausa e rodar de novo outro dia: ele retoma de onde parou. `VISITA_BANCADA.cmd --plano` mostra as etapas e o estado. Detalhes: `scripts/visita_bancada.py`.

#### 9.2 Pré-condições (antes do Bloco 1)

| # | Item | Como conferir | Alimenta |
|---|---|---|---|
| 1 | Commit limpo **para cada bloco que coleta**, incluindo arquivos novos em `scripts/`, `diag/`, `logica/`, `experimentos_*` (o `git_sujo` os conta); os scripts novos já estão commitados no branch. No Bloco 7 o commit da calibração gera **novo SHA**: sessões do Bloco 8 em diante registram o SHA novo | `git status` sem rastreados alterados nem novos não ignorados; `git log --oneline -5` | todas as sessões |
| 2 | Perfil, frequências, tensões e escopo ACDC decididos e **registrados antes de energizar** | Decisões do responsável (P-26), abaixo | P-01, P-17, P-21, P-26 |
| 3 | `set diagnostico bruto on` na CLI antes de cada `run` das classes de interesse do P-28 (opção existente; padrão OFF; ver {doc}`diagnostico`, seção 1.2) | `status` mostra `diagnostico bruto: ON` | P-28 |
| 4 | Validação do PC da bancada | `scripts\validar_pc_bancada.ps1` no próprio PC (Bloco 1), saída `pc_bancada.json` | P-16 |
| 5 | Orçamento: no máximo **216 gravações TRACe por conexão**; **um `run` por conexão**; **nunca `run all`** (468 gravações a 60 Hz) | Estimativa `TRACe: N gravações` da CLI deve bater com as tabelas da seção 5; se não bater, cancelar e conferir `status` | P-23 |
| 6 | COM10 / 115200; USB da AMETEK conectado, DB9 RS-232 desconectado, MX GUI fechado; BNC AMETEK Trigger Out para Keysight EXT Trigger | Bloco 1, conferência física | todas |
| 7 | Fator da probe de tensão: o que está **escrito na probe**, lido na hora; sem valor presumido | Operador | todas |

#### 9.3 Mapa de pendências por bloco

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

(campanhas-por-condicao)=
#### 9.4 Campanhas por condição (P-26)

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

#### 9.5 Fechamento offline (computador de análise)

Depois da visita, com as pastas copiadas (passo 10.7) e o `pc_bancada.json` do passo 1.4. A ferramenta `scripts/fechar_pendencias.py` roda só offline (não abre instrumento nem importa PyVISA/PyMeasure), lê as sessões e os artefatos, e emite por pendência um status (`evidencia_suficiente`, `insuficiente`, `reprovado` ou `sem_dados`), os critérios avaliados e o SHA-256 dos arquivos de origem. Não fecha pendência e recusa sobrescrever a saída. Opções em `--help`.

```powershell
python scripts/fechar_pendencias.py --sessao <dir_sessao_1> --sessao <dir_sessao_2> --artefatos logs --artefatos resultados --pc-bancada docs/evidencias/<data>/pc_bancada.json --saida docs/evidencias/<data>/fechamento.json
```

`--sessao` e `--artefatos` são repetíveis (uma pasta por opção). `--artefatos` aponta pastas fora das sessões, onde os scripts gravam: `logs\` (`diag_acdc_amplitude-*.json`, `diag_nativo-*.json`, `diag_marcadores_trace-*.json`, `benchmark_sessao_io_bancada.json`, `modelo_programada_sessoes_bancada.json`) e `resultados\` (que contém `passo_final_sin_<data>\`, procurado por `resultado.json`). Forma completa: `--artefatos logs --artefatos resultados`. Diagnósticos de P-17, P-18 e P-23 só contam com `simulado` falso, `git_commit` e `git_sujo` falso gravados no próprio JSON (scripts atualizados; arquivos gerados antes disso saem como `insuficiente`). A saída não sobrescreve arquivo existente.

#### 9.6 O que entregar ao coordenador

1. `docs/evidencias/<data>/pc_bancada.json` e `docs/evidencias/<data>/fechamento.json`.
2. As pastas `resultados\sessao_*` originais (inclusive `sessao.log`, `scpi_transcricao.log`, `metadata\`, `diagnostico_trace\`, `bruto_osciloscopio\`, `calibracao_extremos.json` da sessão) e os arquivos de `logs\` do passo 10.7; mais `resultados\passo_final_sin_<data>\` se o Bloco 10-A foi executado.
3. A anotação do passo 10.8, o commit da recalibração do Bloco 7 e a lista do que ficou fora da campanha (19, 08, 07, 17) com o motivo.
4. Qual linha da tabela de decisão (roteiro, seção 3) foi aplicada nos Blocos 3, 4, 5, 6 e 7.
5. Achados de segurança (pico acima de 374,2 V na 08, extremos perto de 415,8 V) e falhas de infraestrutura, com os logs.
6. Pendências que **não** fecham nesta visita e dependem do responsável: P-09 (aceitar o limite), P-20, P-26 (decisões acima, inclusive ACDC 230 V), P-29, P-30, a métrica oficial de P-31 e o padrão do SINE (P-18).
