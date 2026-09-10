# Tarefa: resiliência, CLI interativa e execução autônoma da bateria de 20 classes

Você está rodando dentro de `C:\Users\denis\Documents\TCC\code`, o repositório de
instrumentação do meu TCC (dataset de qualidade de energia: AMETEK MX30-3Pi +
Keysight DSO-X 4034A, sincronizados por BNC, 20 classes de distúrbio). Leia
`README.md` (seções 1 a 6) e `AGENTS.md` inteiros antes de tocar em qualquer
coisa — eles descrevem a arquitetura (`logica/mestre.py`, `ametek_orm.py`,
`oscilloscope_orm.py`, `preflight.py`, `preflight_new.py`) e as travas de
segurança física que existem hoje.

`AGENTS.md` hoje diz "não refatore, não rode testes separados". Essa
instrução é de uma fase anterior do projeto e está **superada por este
prompt** para os itens abaixo — você tem autorização explícita para
refatorar `logica/mestre.py`, `logica/ametek_orm.py`, `logica/preflight.py`,
`logica/preflight_new.py` e os scripts em `scripts/`, e para rodar
`tests/test_offline.py` quantas vezes quiser (é seguro, não toca hardware).
O que **não muda** está na seção "Limites inegociáveis" no fim deste
documento — inclua isso atualizado em `AGENTS.md` ao terminar, para a
próxima sessão não perder o contexto.

Estou na bancada agora. Preciso sair daqui com o dataset físico das 20
classes capturado. Priorize nesta ordem:

## Prioridade 0 — corrigir o erro que acabou de acontecer

Rodando `scripts\START_BENCH.cmd` (Full) hoje, a etapa `NativeCommands`
(`logica/preflight_new.py --native-commands`) falhou no teste do CSINe:

```
--- CSINe nativo (senoide clipada)
FALHOU: CSINe nativo (senoide clipada): AMETEK reportou erros após comando
INITiate:IMMediate: [(-113, 'Undefined header')]
```

Log completo em `logs\preflight_new-native-commands-20260909-134411.log`.
STEP e PULSe (os dois testes nativos anteriores no mesmo preflight) passaram
sem erro — só o CSINe quebrou.

Minha suspeita, com base no próprio código: em
`logica/ametek_orm.py`, `configure_harmonics_csine()` (por volta da linha
497-525):

```python
self.write("SOURce:FUNCtion:SHAPe CSINusoid")
# ... comentário: trocar a forma recarrega a tabela e deixa a Rev. 5.53
# "muda" por alguns segundos; por isso este aguardar_resposta() aqui.
self.aguardar_resposta()
self.write(f"SOURce:FUNCtion:SHAPe:CSINusoid {thd_pct:.8g}")
```

O `aguardar_resposta()` só é chamado depois do PRIMEIRO write (seleção da
forma). O SEGUNDO write (`SHAPe:CSINusoid {thd}`, que programa o nível de
clipping) não tem essa espera — e é plausível que ele dispare o mesmo
recálculo interno/período "mudo" que o comentário já documenta para o
primeiro comando. Como não há espera ali, `trigger_step()` (3 writes) e
depois `arm()` (que só lê erros no final, em `assert_no_errors()` depois do
`INITiate:IMMediate`, linha ~985-986) são disparados enquanto a fonte ainda
pode estar processando — e um erro gerado pelo segundo write só aparece na
fila quando `arm()` finalmente checa, atribuído erroneamente ao
`INITiate:IMMediate`.

Passos:
1. Adicione `self.aguardar_resposta()` depois do write de
   `SHAPe:CSINusoid {thd}` também (mesma linha de raciocínio do comentário
   já existente ali).
2. Para não mascarar o problema de novo, considere chamar
   `self.assert_no_errors(...)` logo depois de `configure_harmonics_csine()`
   (ou dentro dela, após o segundo write), em vez de só descobrir o erro
   depois, dentro de `arm()` — isso teria apontado o comando certo desde o
   início.
3. Teste na bancada real (`scripts\start_bench_windows.ps1 -Stage
   NativeCommands`) até o CSINe passar de forma consistente (rode pelo menos
   3 vezes seguidas). Se minha hipótese estiver errada, investigue de outra
   forma — vocês têm o manual SCPI da AMETEK em `docs/` e os logs anteriores
   em `logs/` (inclusive execuções de 02/09 onde os mesmos testes passaram)
   para comparar.
4. Não mude a ordem de STEP → PULSe → CSINe → LIST:FREQuency → ACDC nem os
   valores de teste (`CSINE_THD_PCT`, etc.) em `preflight_new.py`.

## Prioridade 1 — uma falha de experimento não pode derrubar a bateria

Hoje, em `logica/mestre.py`:

- `Bancada.executar_bateria()` (linha ~369) chama
  `executar_experimento(script_path)` para cada uma das 20 classes sem
  nenhum `try/except` — uma exceção em qualquer classe propaga até
  `main()` (linha ~732), que só loga "Bateria abortada na primeira falha"
  e sai. As classes restantes nunca rodam.

Mude isso para: cada classe roda isolada, uma falha é registrada e a
bateria continua para a próxima. Concretamente:

1. Em `executar_bateria()`, envolva a chamada de cada experimento num
   `try/except Exception` (não `BaseException` — `KeyboardInterrupt` e
   erros que indiquem perda de comunicação/segurança real com o
   instrumento devem continuar abortando, ver item 3).
2. Ao capturar uma falha: log completo com traceback
   (`logger.exception(...)`), registre a classe como `FALHOU` numa lista/
   dict de resultados, e **garanta que a fonte volta a um estado seguro
   conhecido** antes de seguir para a próxima classe (ex.: `trigger_step()`
   de volta à tensão base, confirmar `OUTPUT` ainda ligado no nível
   esperado) — não deixe a AMETEK num modo transitório no meio de uma
   falha.
3. Distinga falha de experimento (RMS fora de tolerância, timeout de
   trigger, exceção em `gerar()`) de falha de infraestrutura real (porta
   serial caiu, `*IDN?` não responde, impossível confirmar OUTPUT) — a
   segunda categoria deve continuar interrompendo tudo e acionando o
   shutdown fail-safe existente (`Bancada.__exit__`/`finally`), porque não
   é seguro continuar tentando com o instrumento em estado desconhecido.
   Use os tipos de exceção que o projeto já distingue
   (`InstrumentHardwareError`, `TimeoutError`, `ParameterOutOfBoundsError`
   vs. erros de asserção/validação de dado) para decidir — se não houver
   uma distinção limpa hoje, crie uma (ex.: uma exceção
   `FalhaFatalDeInstrumento` que não deve ser engolida).
4. No fim de `executar_bateria()`, imprima/logue um resumo: quantas de
   20 passaram, quais falharam e por quê, e onde estão os `.npz`
   parciais. `main()` deve retornar código de saída != 0 se alguma classe
   falhou, mas só depois de tentar todas.
5. Rode `tests/test_offline.py` depois dessa mudança — ele já cobre as 20
   classes em modo simulado e deve continuar passando.

## Prioridade 2 — parar o teste de 5V e o reenvio de traces a cada execução

A etapa `LowVoltage` (`preflight.py --low-voltage`, chamada em
`start_bench_windows.ps1` tanto isolada quanto dentro de `-Stage Full`)
hoje, toda vez que roda:

- Pergunta `ENERGIZAR-5V`, energiza a saída e faz uma captura de
  comissionamento a 5 Vrms.
- Antes disso, grava 12 TRACe (`TCC00`..`TCC11`) na Flash da AMETEK via
  `source.program_capture(normal_waveform(), ...)` — isso é ~3s por
  TRACe, ~36-50s de escrita em Flash, **toda vez**, mesmo quando a forma
  de onda, tensão e frequência não mudaram desde a última vez.

Isso já está reconhecido no próprio comentário do código
(`preflight.py`, linha ~56-62): a etapa `--trigger-test` deliberadamente
evita reprogramar para não "duplicar ~50s de escrita em Flash... sem
uso" — mas a `--low-voltage` ainda faz isso incondicionalmente a cada
chamada.

O que quero:

1. **Tirar a etapa de 5V do fluxo obrigatório.** Ela não deve mais rodar
   automaticamente dentro do `-Stage Full` nem ser pré-requisito
   silencioso de mais nada. Mantenha-a disponível como comando isolado
   (`-Stage LowVoltage` ou o comando equivalente na CLI nova, item 3) para
   quando eu precisar re-comissionar a bancada depois de mexer em fiação/
   probe — mas não force isso a cada vez que eu ligo o sistema.
2. **Não reenviar TRACe se o conteúdo já é o mesmo.** Onde quer que
   `program_capture()` seja chamado (em `preflight.py` e em
   `ExperimentoBase._capturar_real()` dentro de `mestre.py`, linha ~687),
   adicione uma checagem: se a forma de onda (hash do array), a tensão
   base e a frequência forem idênticas ao último `program_capture()`
   bem-sucedido **desta mesma conexão**, pule a reprogramação de TRACe e
   vá direto para o arm/trigger. Cuidado com
   `AMETEK_CLEAR_USER_WAVEFORMS=1` (`scripts/bench_config.ps1`, linha 12):
   ele limpa as TRACe do usuário uma vez por conexão, então o cache
   síncrono só é válido dentro da mesma sessão/conexão — invalide o cache
   sempre que a fonte reconectar. Se for viável, prefira confirmar contra
   o instrumento (`TRACe:CATalog?` ou equivalente, ver
   `docs/AMETEK_MX_SCPI_Programming_Manual.pdf`) em vez de confiar cegamente
   em um cache local, para não arriscar programar um transiente errado.
3. Isso deve valer tanto para reduzir o tempo de start quando eu reinicio
   o script depois de uma falha (não recomeça do zero gravando Flash de
   novo) quanto, dentro da bateria de 20 classes, para classes que
   reutilizam a mesma forma base (ex.: NORMAL/STEP) se isso já não
   estiver acontecendo.

## Prioridade 3 — CLI interativa (substituindo os `Read-Host` soltos)

Hoje a operação é: `START_BENCH.cmd` roda um script PowerShell que passa
por 5 etapas fixas, parando em `Read-Host` no meio (fator de probe,
Vrms, frequência, `ENERGIZAR`/`ENERGIZAR-5V`/`ENERGIZAR-COMANDOS`/
`EXECUTAR-20-CLASSES`). Quero trocar isso por uma CLI interativa (REPL)
que eu ou outro operador da bancada consiga usar sem decorar a sequência
nem reler o README inteiro.

Requisitos:

- Comandos explícitos, não um fluxo linear obrigatório. No mínimo:
  `status` (o que está conectado, ARM_OUTPUT, última classe capturada),
  `comm` (identificação/IDN, equivalente à etapa Communication),
  `trigger` (equivalente à etapa Trigger), `lowvoltage` (agora opcional,
  ver item 2), `native` (preflight de comandos nativos), `run <NN|nome>`
  (roda uma classe específica das 20), `run all` (roda a bateria
  completa, ver item 4), `list` (lista as 20 classes com status da última
  execução: OK/FALHOU/nunca rodou), `help`/`?` (referência rápida, item
  4), `quit`/`exit`.
- **Mantenha as confirmações físicas obrigatórias** — fator de probe,
  Vrms/Hz do teste, e a string digitada antes de energizar
  (`ENERGIZAR`, case-sensitive) continuam existindo exatamente como hoje;
  a CLI só organiza o acesso aos comandos, não remove nenhuma confirmação
  de segurança. Cada comando que energiza a saída deve pedir sua própria
  confirmação explícita antes de agir, do jeito que já funciona hoje.
- Pode ser um REPL em Python (faz mais sentido dado que toda a lógica já
  está em `logica/`) chamado a partir de um novo entrypoint (ex.:
  `logica/cli.py`), com `scripts/START_BENCH.cmd`/um novo `.cmd` só
  preparando o venv e invocando esse REPL. Decida a forma exata olhando o
  que já existe em `mestre.py`/`Bancada` — reaproveite `Bancada.from_env()`
  e os métodos existentes em vez de duplicar lógica.
- Sem hardware (`BENCH_MODE=0`), os mesmos comandos devem continuar
  funcionando em modo simulado, do jeito que o resto do projeto já
  suporta hoje.

## Prioridade 4 — ordem de comando para o operador (consulta rápida)

Ao abrir a CLI (e via `help`/`?`), imprima uma referência rápida: uma
linha por comando, o que ele faz, se energiza a saída ou não, e a ordem
recomendada para uma sessão do zero (comm → trigger → native →
lowvoltage se necessário → run all). Isso substitui precisar abrir o
README na hora. Pode viver também como um bloco curto no topo do
README (seção 5.3) linkando para o `help` da CLI, mas o texto principal
fica no `help` da própria ferramenta.

## Prioridade 5 — rodar sozinho, uma classe por vez

`run all` (ou o comando equivalente) deve:

- Rodar as 20 classes **sequencialmente, uma de cada vez** — sem
  paralelismo/threads. A fonte e o osciloscópio são recursos físicos
  únicos e compartilhados; não tente "otimizar" isso.
- Depois da confirmação inicial de energização, seguir sozinho até o
  final sem pedir mais nada ao operador (a menos que uma condição
  realmente insegura apareça — aí sim, parar e avisar, com o instrumento
  em estado seguro, como já descrito na Prioridade 1).
- Ao final, mostrar um resumo claro: quantas classes OK, quais
  falharam (com o motivo curto), onde estão os `.npz`/logs de cada uma.

## Depois de implementar

1. Rode `tests/test_offline.py` (modo simulado, sem hardware) e garanta
   que passa.
2. Comigo presente na bancada, valide manualmente `comm`, `trigger` e
   `native` (isso cobre a correção da Prioridade 0).
3. Se `native` passar de forma estável, rode `run all` na bancada real
   e me mostre o resumo final. Se alguma classe falhar, me avise qual e
   por quê antes de tentar de novo — não insista sozinho numa classe que
   falha repetidamente.
4. Atualize `AGENTS.md` e a seção 5 do `README.md` para descrever o novo
   fluxo (CLI, `lowvoltage` como opcional, resiliência por classe) no
   lugar do fluxo antigo de 5 etapas obrigatórias.

## Limites inegociáveis (não mudar em nenhuma hipótese)

- `AMETEK_PORT=COM10`, `AMETEK_BAUDRATE=115200` continuam fixos e
  validados; não trocar porta/baud nem remover a validação em
  `validate_bench_configuration()` (`mestre.py`).
- Não remover nem enfraquecer validações de IDN, timeout, tamanho de
  waveform (6000 pontos) ou erros SCPI (`assert_no_errors`/
  `check_errors`) — inclusive as que a Prioridade 0 pode tornar mais
  cedo/mais específicas, nunca mais fracas.
- Não alterar `max_voltage_rms`, `max_peak_v`, `max_current_a` nem
  remover `ParameterOutOfBoundsError` em `ametek_orm.py`.
- Nenhum comando que energiza a saída pode rodar sem confirmação
  explícita digitada pelo operador — isso vale tanto no fluxo antigo
  quanto em qualquer comando novo da CLI.
- Captura de corrente continua desligada por padrão
  (`CAPTURE_CURRENT=0`); não ativar sem `CURRENT_PROBE_ATTENUATION` e
  `CURRENT_BASE_A` fornecidos por mim.
- Se algo falhar de um jeito que não se encaixa na Prioridade 1 (ex.:
  perda de comunicação serial), o comportamento continua sendo: garantir
  `OUTPUT OFF`/shutdown seguro, não tentar de novo sozinho, e apontar o
  log mais recente — do jeito que `AGENTS.md`/README seção 5.5 já
  descrevem hoje.
