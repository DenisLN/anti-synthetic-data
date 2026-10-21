# Roteiro da próxima bancada (v1.15)

Para quem vai ao PC da bancada em `C:\Users\denis\TCC\code` (ajuste o caminho). Ordem decidida: **primeiro o diagnóstico, depois a campanha**, porque o diagnóstico pode mudar o que vale coletar (tabela de decisão na seção 3). Regras de segurança invioláveis: `AGENTS.md`. Operação da CLI: `docs/operacao.md`.

Este roteiro foi escrito sem acesso à bancada. Todo comando e toda confirmação citados existem no código (conferência na seção 7); todo tempo é **estimativa** (modelo na seção 4), exceto onde diz "medido".

## 0. Regras fixas do dia

- **Fator da probe de tensão**: o que está **escrito na probe física**, conferido na hora. Em todo comando abaixo aparece como `<FATOR escrito na probe>`; não presuma o valor de sessões anteriores. O `START_BENCH` pergunta; os scripts `diag_*` recebem em `--probe`.
- **Confirmações digitadas, case-sensitive, nunca automatizadas**: `ENERGIZAR-TESTE`, `ENERGIZAR-COMANDOS`, `EXECUTAR-CLASSE-<NN>`, `EXECUTAR-CLASSES-<lista normalizada>`, `EXECUTAR-20-CLASSES` (não usada hoje), `ENERGIZAR-MARCADORES`, `ENERGIZAR-ACDC` e, **só no passo P-18** (Bloco 10-A, `scripts/teste_passo_final_sin.py`), `ENERGIZAR-PASSO-SIN`. **Nenhum script, macro ou agente digita qualquer uma delas: o operador está presente e digita cada uma.** Antes de digitar: probe, cabos, E-stop, EUT, **disjuntores entre a fonte e a probe fechados**.
- **Captura de corrente desligada** (`CAPTURE_CURRENT=0`). Não ativar.
- **Tensão do dia: 127 V.** Sem 220/380 V. A execução ACDC a 230 V (Bloco 5, 3.ª execução) **não será feita**: decisão P-26 de 21/10/2026, opção A (`docs/decisoes_pendentes.md`). As campanhas CA nas outras condições (230 V/50 Hz, 220 V/60 Hz, 33 V/60 Hz) são sessões próprias, fora deste dia (`docs/bancada_pendencias.md`, "Campanhas por condição"). Frequências: sessão A em **50 Hz** (diagnóstico da 08/09), sessão B em **60 Hz** (campanha).
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

## 1. Visão geral e tempo

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

## 2. Blocos em ordem de execução

### Bloco 1. Preparação (sem energizar)

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
- `git log` mostra este roteiro (`ROTEIRO_BANCADA.md` existe na raiz) e o commit da crista com o fator calibrado .
- `git status` sem alterações rastreadas nem arquivos novos não ignorados nas pastas `mestre.PASTAS_DO_CODIGO`; `info_do_codigo` recalcula esse estado a cada pasta de sessão. Arquivos novos fora dessas pastas não contam para `git_sujo`.
- A suíte termina em `OK`, **todos os testes passando e 0 falhas**; a contagem de testes **não é fixa** (novos testes aumentam o total). Skips aceitáveis: só os dois testes de hash exato específico de plataforma (`*_exato_na_plataforma_de_origem`), se houverem; qualquer outro skip precisa de justificativa. Rodar também `.\env\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v` e `scripts\validar_pc_bancada.ps1`: este script é o **registro** da validação do PC (P-16): grava `pc_bancada.json` com total, tempo, versões, SHA e skips (entregar como `docs/evidencias/<data>/pc_bancada.json`). Não usar contagem histórica como prova de execução.
- Conferência física: probe diferencial no CH1 entre fase A e neutro, fator **lido na probe**; BNC AMETEK Trigger Out -> Keysight EXT Trigger; USB da AMETEK conectado e **DB9 RS-232 desconectado**; MX GUI **fechado**; disjuntores fechados; E-stop ao alcance; EUT conectado; OUTPUT OFF no painel.

Seguir se: suíte `OK`, 0 falhas, skips só os dois de hash específico de plataforma (se houver) e `pc_bancada.json` gerado, árvore limpa.
Parar se: algum teste de **assinatura portável** falhar (a causa não seria só o último bit de `np.sin`): entregar a saída completa, anotar `numpy` (`env\Scripts\python.exe -c "import numpy; print(numpy.__version__)"`) e **não coletar** até analisar. Se falharem **só** os testes `*_exato_na_plataforma_de_origem` (SHA-256), registrar plataforma, Python/numpy e saída completa para diagnóstico antes de coletar; não considerar uma falha de fixture como autorização automática para coleta. Árvore suja: commitar ou descartar a causa antes de qualquer sessão.

### Bloco 2. Infraestrutura na CLI, sessão A (127 V / 50 Hz)

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

### Bloco 3. Diagnóstico offline das sessões de 07/10 (sem energizar)

Objetivo: ver, nos dados que já existem, **qual ciclo programado explica cada ciclo medido** nas classes 08 e 09, a partir de que instante e com que resíduo perto de 100 ms. É a opção mais barata e pode ser feita antes de ir à bancada.

```powershell
cd C:\Users\denis\TCC\code
env\Scripts\python.exe scripts\diag_ciclos_trace.py resultados\sessao_2026-10-07_127V_50Hz --classes 08,09
env\Scripts\python.exe scripts\diag_ciclos_trace.py resultados\sessao_2026-10-07_14-59-54_run02 --classes 08,09
Get-ChildItem logs\diag_ciclos_trace-* | Sort-Object LastWriteTime | Select-Object -Last 4 | Format-Table Name, Length
Get-Content (Get-ChildItem logs\diag_ciclos_trace-*.md | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
```

(`--sem-forma-bancada` dispensa o candidato `k_sem_dc`. Não escreve na pasta da sessão.)

Conferir, por captura: primeiro ciclo **trocado** e quem o explica (`k-1`, `k+1`...), instante do ciclo, primeira amostra divergente, resíduo máximo perto de 100 ms. Leitura: seção 3, linha "Ciclos (offline)".
Seguir se: o script rodou. Se acusar erro de carregamento (caminho `.npz` bruto + reconstrução de versões, **não exercitado em teste com dado real**): entregar a mensagem completa e seguir sem este bloco (os blocos 4 e 6 trazem o dado novo). Tempo: 2 a 5 min (não medido).

### Bloco 4. Marcadores por ciclo (energiza, script)

Objetivo: separar "o ciclo k tocou o ciclo k-1" (troca de passo) de "cópia em instante fixo (~100 ms)", medir atraso global em amostras e confrontar as hipóteses de `logica/modelo_lista_fonte.py`.

CLI fechada. PowerShell novo:

```powershell
cd C:\Users\denis\TCC\code
$env:BENCH_MODE = "1"
env\Scripts\python.exe scripts\diag_marcadores_trace.py --probe <FATOR escrito na probe> --vrms 127
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

### Bloco 5. Amplitude CA em ACDC (energiza, script)

Objetivo: entender o déficit de 5 a 6 % de CA na classe 19 (ACDC) e medir o ganho `g = CH1 CA / alvo` por condição.

CLI fechada. Três execuções (digitar `ENERGIZAR-ACDC` em cada uma):

```powershell
cd C:\Users\denis\TCC\code
$env:BENCH_MODE = "1"
env\Scripts\python.exe scripts\diag_acdc_amplitude.py --probe <FATOR escrito na probe> --vrms 127 --hz 60 --testar-compensacao
env\Scripts\python.exe scripts\diag_acdc_amplitude.py --probe <FATOR escrito na probe> --vrms 127 --hz 50 --testar-compensacao
env\Scripts\python.exe scripts\diag_acdc_amplitude.py --probe <FATOR escrito na probe> --vrms 230 --hz 50 --testar-compensacao
Get-Content (Get-ChildItem logs\diag_acdc_amplitude-*.md | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
```

**A 3.ª execução (230 V) não será feita (decisão P-26 de 21/10/2026, opção A)** (`docs/decisoes_pendentes.md`, item 4: opção A = fora desta campanha, recomendada; opção B = exceção formal ao roteiro de 127 V). Sem a decisão registrada por escrito, **não executar**: pule-a e anote que `g` não foi medido a 230 V (P-17 fecha só para 127 V). Se a opção B for decidida, a 3.ª condição só separa a dependência da tensão (H7); o script limita a V <= 270 e planeja o pior caso de pico <= 415,8 Vp. 

Conferir (tabela `.md`, colunas `CH1 AC / alvo`, `fonte DC?`, `fonte AC?`, `CH1 CC`; e `VOLTage:RANGe?`):
- linhas 1 e 5 (AC, controle inicial e final) ≈ 1,000 (sem deriva);
- linha 2 (ACDC/STEP) e linha 3 (ACDC/`VOLTage` imediato): ambas ≈ 0,94 a 0,95, ou a linha 3 ≈ 1,000;
- `VOLTage:RANGe?` em ACDC igual a 300 ou não;
- `g` (linha 2) nas 3 condições (provisórios dos dados de 07/10: 0,9508 a 127 V/50 Hz, 0,9431 a 127 V/60 Hz, 0,9377 a 230 V/50 Hz);
- linhas de compensação (`V_prog` = V/g): `CH1 AC / alvo` ≈ 1,000;
- CC a 60 Hz: medido menos programado entre -1,0 e -1,7 V (viés de cadeia); +1,9 V repete a anomalia de 07/10;
- `fonte AC?` ≈ raiz de (CA² + CC²), com CC = `fonte DC?` (confirma que `MEASure:VOLTage:AC?` em ACDC é rms total); `MEASure:VOLTage:DC?` rejeitado: anotar.

Leitura: seção 3, linhas "ACDC". Seguir se: as 3 (ou 2) execuções terminaram. Parar se: infraestrutura (seção 0; entregar `logs\diag_acdc_amplitude-*.log` mais recente). Tempo: 2 a 3 min por execução (relatado no diagnóstico de 12/10), ~8 min com trocas.

### Bloco 6. Recaptura da 08 a 127 V / 50 Hz e a 09 (CLI, sessão A)

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
env\Scripts\python.exe scripts\diag_ciclos_trace.py $s --classes 08,09
Get-Content (Get-ChildItem logs\diag_ciclos_trace-*.md | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
```

(a 08 e a 09 podem estar em pastas diferentes: `_run01`/`_run02`; rodar o script na pasta de cada uma, `--classes 08` e `--classes 09`.)

Critério da 09: aceitar **sem ressalva** só a captura **sem ciclo trocado** e com resíduo perto de 100 ms **< ~0,05 pu** (ruído da 09: 0,008 a 0,017 pu rms). Acima disso: manter a captura, marcar como suspeita, **não usar para treino**. É defeito de dado, não de infraestrutura: não interrompe nada.
Tempo: `run 08` ~2 min, `run 09` (6 capturas) ~3 a 5 min, mais START_BENCH e leituras: 10 a 15 min.
Seguir se: a 08 aprovada e a 09 classificada. Se a 08 reprovar por posição: **não repetir sozinho**; entregar `metadata\08_transient.jsonl` e `sessao.log`; na campanha a 60 Hz a 08 segue o caso da tabela (seção 3).

Sair da CLI: `quit`.

### Bloco 7. 07 e 17 com recalibração (CLI, sessão B: 127 V / 60 Hz)

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

### Bloco 8. Verificações do sorteio = Parte 1 da campanha (CLI, sessão B, 60 Hz, **commit limpo**)

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

### Bloco 8-A. Sequência da P-10: RMS e THD da 05 por nível (CLI, sessão B, 60 Hz, commit limpo)

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

### Bloco 9. Campanha em partes (mesma CLI do Bloco 8)

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

### Bloco 10. Entrega (seção 6)

Medições e agregação (offline, **no PC da bancada** onde indicado; CLI fechada, OUTPUT OFF; nenhuma destas etapas energiza nem digita confirmação):

```powershell
cd C:\Users\denis\TCC\code
# P-22: custo de I/O das sessões físicas, medido NO PC DA BANCADA (grava hostname e simulado)
env\Scripts\python.exe scripts\benchmark_sessao_io.py --sessao <dir_sessao_1> [--sessao <dir_sessao_2> ...] --saida logs\benchmark_sessao_io_bancada.json
# P-31: comparação modelo x programada nas sessões físicas
env\Scripts\python.exe scripts\analisar_modelo_programado.py --sessao <dir_sessao_1> [--sessao <dir_sessao_2> ...] --saida logs\modelo_programada_sessoes_bancada.json
```

`--saida` não sobrescreve arquivo existente. Fechamento (pode rodar no computador de análise, com as pastas copiadas; `--artefatos` aceita `logs` e `resultados\passo_final_sin_*`):

```powershell
python scripts/fechar_pendencias.py --sessao <dir> [--sessao <dir> ...] --artefatos logs --artefatos resultados --pc-bancada docs/evidencias/<data>/pc_bancada.json --saida docs/evidencias/<data>/fechamento.json
```

O fechamento só reúne evidência e **não encerra pendência**: a decisão é do responsável. Ver `docs/bancada_pendencias.md`.

## 3. Tabela de decisão: o que muda na campanha do mesmo dia

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

## 4. Modelo de tempo e de gravações de TRACe

- Gravações de TRACe de uma classe = (capturas da classe que gravam TRACe) x (ciclos da janela = 0,2 s x frequência: **12 a 60 Hz, 10 a 50 Hz**). A conta é exata com sorteio ligado (padrão): cada captura TRACe regrava a Flash. Fonte da conta: `capturas_efetivas_da_classe` (`logica/mestre.py`) e `_aviso_escritas_trace` (`logica/cli.py`), a mesma estimativa que a CLI mostra antes de pedir a confirmação.
- Tempo de uma conexão (`run`) ≈ **18 s** (abertura, `*IDN?`, baseline, checagem da cadeia) + **~3 s x min(ciclos, 12)** (definição das TRACes novas na Flash, na 1.ª captura da conexão: 36 s a 60 Hz, 30 s a 50 Hz) + **~2 s x gravações de TRACe** + **~2,5 s x capturas nativas**.
- Esses números vêm das medidas citadas nos relatórios desta rodada (1 s de espera por TRACe mais overhead de consulta e osciloscópio; ~2,5 s por captura nativa). **NÃO VERIFICADO**: nenhuma bateria completa foi cronometrada; use a coluna "x 1,5" como valor de planejamento.
- Referência: o `run all` de uma conexão só (que **não** será usado) daria 468 gravações a 60 Hz (390 a 50 Hz), 17,0 min no modelo; e a trava ocorreu na ~280.ª.

## 5. Plano da campanha em partes (127 V, 60 Hz)

Contas feitas rodando offline `_capturas_das_classes`/`capturas_efetivas_da_classe` com `BASE_VOLTAGE_RMS=127`, `GRID_FREQUENCY_HZ=60` e `50`, sorteio ligado, 3 capturas padrão. As capturas por classe são iguais nos três perfis (as classes TRACe têm 3 capturas e 36 gravações a 60 Hz, 30 a 50 Hz; 01, 02, 03, 05, 18 têm 1 captura; 04 e 19 têm 3). Classes com TRACe: 06 a 17 e 20 (13 classes). Nativas (sem TRACe): 01 a 05, 18, 19 (11 capturas).

### 5.1 Um perfil (`literatura`, padrão): 468 gravações no total em 3 conexões

| Parte | Comando | Confirmação | Capturas | Gravações de TRACe (60 Hz / 50 Hz) | Tempo (60 Hz / 50 Hz) |
|---|---|---|---|---|---|
| 1 (Bloco 8) | `run 01-05,18-20` | `EXECUTAR-CLASSES-01-05,18-20` | 14 | **36** / 30 | 2,6 min (3,8 min x 1,5) / 2,3 min (3,4) |
| 2 | `run 06-11` | `EXECUTAR-CLASSES-06-11` | 18 | **216** / 180 | 8,1 min (12,2) / 6,8 min (10,2) |
| 3 | `run 12-17` | `EXECUTAR-CLASSES-12-17` | 18 | **216** / 180 | 8,1 min (12,2) / 6,8 min (10,2) |
| Total | | | 50 | 468 / 390 | 18,8 min (28,1) / 15,9 min (23,8) |

Maior conexão: 216 gravações a 60 Hz (≤ 216). Sem a 19 (Bloco 5 recomendou): Parte 1 = `run 01-05,18,20`, 11 capturas. Sem a 08 (tabela): Parte 2 = `run 06-07,09-11` (`EXECUTAR-CLASSES-06-07,09-11`), 180 gravações. Sem 07/17: Parte 2 = `run 06,08-11`, Parte 3 = `run 12-16`.

### 5.2 `set perfil todos`: 1116 gravações (60 Hz) / 930 (50 Hz) em 6 conexões

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

### 5.3 Frequência da campanha

Esta seção assume 60 Hz. Se a campanha for a 50 Hz, a 08 recapturada no Bloco 6 já é a da campanha; neste caso rode o Bloco 7 também a 50 Hz (os fatores de 07/17 a 127 V/50 Hz são 1,375 (07) e 1,307 (17); a simulação previa que cobrem quase tudo) e use as colunas "50 Hz".

## 6. Checklist de entrega ao fim do dia

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

## 7. Conferência dos comandos e confirmações no código

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
| `ENERGIZAR-MARCADORES` | `scripts/diag_marcadores_trace.py:80` |
| `ENERGIZAR-ACDC` | `scripts/diag_acdc_amplitude.py:68` |
| `set diagnostico retrieve on\|off`, `set capturas <N>\|padrao`, `set perfil todos`, `set recalibracao on\|off`, `set html on\|off`, `set sorteio` | `logica/cli.py`: `cmd_set` e `HELP_TEXT` |
| `run 07,17`, `run 01-05,18-20` (lista) | `logica/cli.py`: `parsear_lista_classes`, `normalizar_lista_classes`, `_run_lista` |
| `diag_ciclos_trace.py <sessao> --classes` | `scripts/diag_ciclos_trace.py` (`--classes`, `--sem-forma-bancada`, `--saida`) |
| `diag_marcadores_trace.py --probe --vrms --frequencias --variantes` | `scripts/diag_marcadores_trace.py` |
| `diag_acdc_amplitude.py --probe --vrms --hz --testar-compensacao` | `scripts/diag_acdc_amplitude.py` |
| `verificar_sessao_bancada.py <sessao> --json` | `scripts/verificar_sessao_bancada.py` |
| `recalibrar_extremos.py <sessao>` (sem `--gravar`) | `scripts/recalibrar_extremos.py` |
| `ENERGIZAR-PASSO-SIN` (só P-18) | `scripts/teste_passo_final_sin.py:33` (`CONFIRMACAO`) |
| `benchmark_sessao_io.py --sessao --saida` (P-22) | `scripts/benchmark_sessao_io.py` (`main`) |
| `analisar_modelo_programado.py --sessao --saida` (P-31) | `scripts/analisar_modelo_programado.py` (`main`) |
| `fechar_pendencias.py --sessao --artefatos --pc-bancada --saida` | `scripts/fechar_pendencias.py` (`main`; `--artefatos` repetível) |
| `set diagnostico bruto on\|off` (P-28) | `logica/cli.py`: `cmd_set` e `HELP_TEXT` |
| `analisar_sessao.py`, `recortar_margem.py`, `relatorio_html.py` | `logica/analisar_sessao.py`, `logica/recortar_margem.py`, `logica/relatorio_html.py` |
| Campos do metadata usados nos `Get-Content` | `logica/mestre.py` (`id_captura`, `pico_medido_v`, `vale_medido_v`, `extremo_previsto_v`, `indice_trigger`, `escritas_trace_na_conexao`, `diagnostico_trace`), `logica/sinais.py` (`crista_*`, `fator_extremo_crista`, `thd_*`), `experimentos_waveform/08.py` (`posicao_evento`, `inicio_impulso_s`) |

## 8. Limites deste roteiro (NÃO VERIFICADO)

- Nada foi executado na bancada. Tempos são estimativas do modelo da seção 4; conferir o primeiro `run` contra o relógio e ajustar o resto do dia.
- A suíte no Windows, o formato dos `.npz` das sessões de 07/10 em `diag_ciclos_trace.py`, `TRACe:DATA?` na fonte, os limiares do verificador (10 graus, 2 ms, 2 amostras) e a leitura de marcadores (limiares de 12 amostras de posição e 25 % de amplitude) são propostas sem dado de bancada.
- O mecanismo da cópia em 100 ms, a causa do déficit ACDC e o toque real da fonte nos entalhes das 07/17 continuam em aberto até este dia.
- A 05 por TRACe (nível de 30 %) não entra na conta de gravações da estimativa da CLI (a 05 aparece com 0 gravações com 1 captura padrão); no Bloco 8-A (`set capturas 1`, perfil `literatura`) o esperado é 12 gravações a 60 Hz, **NÃO VERIFICADO**: recontar com `status` e conferir `escritas_trace_na_conexao`.
