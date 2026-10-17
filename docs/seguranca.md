# Limites inegociáveis e camadas de segurança

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Regras de `AGENTS.md` conferidas contra o código em 2026-10-16 (`main` em `fa82f49`). {bdg-warning}`NÃO VERIFICADO` na bancada com o código da v1.15 (P-01).

:::{danger} Segurança
Nenhum comando que energiza a saída roda sem a confirmação **digitada** pelo operador (case-sensitive). Os limites abaixo não mudam em nenhuma hipótese; se uma mudança de código parece exigir mexer neles, **pare** e leve a decisão ao responsável pelo projeto. Em qualquer dúvida: **OUTPUT OFF** no painel da fonte, e só então conversar.
:::

**Pergunta:** o que nunca pode mudar no projeto e onde o código garante isso? **Resposta:** seis limites: a **porta e o baud da fonte** (COM10, 115200), as **validações de IDN, timeout, tamanho de waveform (6000 pontos) e erros SCPI**, os **tetos de tensão, pico e corrente** (`max_voltage_rms`, `max_peak_v`, `max_current_a`) e o `ParameterOutOfBoundsError` que os faz valer, a **confirmação digitada**, a regra de que **falha de infraestrutura aborta e falha de experimento isola**, e o **cache de TRACe** que sempre reconfirma contra o instrumento. Cada um é garantido por uma ou mais das catorze camadas descritas em {doc}`codigo/invariantes`.

## 1. Os limites numéricos

| Grandeza | Valor | Origem | Onde o código a faz valer |
|---|---|---|---|
| tensão máxima da fonte | 300 Vrms por fase | hardware (manual SCPI §4.14, p. 84 do PDF) | `max_voltage_rms = 300`: setters, pré-validação ([mestre.py:2063](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2063)), `SOURce:VOLTage:HIGH` |
| pico máximo do hardware | 425 Vp | hardware | `MAX_SOURCE_PEAK_V = 425` e `max_peak_v = min(…, 425)` no construtor da fonte |
| pico de software | 415,8 Vp (98 % de 300·√2) | `start_bench_windows.ps1` (sobrescreve o ambiente) | `max_peak_v`; teto do extremo previsto (0,9 × na 08) e do extremo medido |
| corrente | `CURRENT_LIMIT_A` (padrão 0,5 A) e `CURRENT_PROTECTION_DELAY_S` (padrão 0,1 s) | ambiente | setter `current_limit`; `SOURce:CURRent` e a proteção na baseline |
| porta e baud | `COM10`, 115200 | bancada | [mestre.py:418](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L418) e [ametek_orm.py:334](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L334) |
| tensão de teste | ≤ 270 V fase-neutro | `start_bench_windows.ps1` | 380 V é tensão de **linha**: digite 220 (219,4 V por fase) |
| captura de corrente | desligada (`CAPTURE_CURRENT=0`) | padrão | só liga com `CURRENT_PROBE_ATTENUATION` e `CURRENT_BASE_A` fornecidos |

A tensão `SOURce:VOLTage:HIGH` na fonte é limite de tensão **rms**, não de pico (quirk A13): a proteção de pico é de software.

## 2. As regras

1. **Porta e baud fixos.** `AMETEK_PORT=COM10` e `AMETEK_BAUDRATE=115200` são validados em `validate_bench_configuration()` ([mestre.py:418](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L418)) e em `connect`. Não trocar nem remover.
2. **Validações de IDN, timeout, 6000 pontos e erros SCPI** (`assert_no_errors`, `check_errors`) não se removem nem se enfraquecem; podem ficar **mais específicas** (por exemplo o `assert_no_errors` logo depois de `SOURce:FUNCtion:SHAPe CSINusoid`, que passou a apontar o comando certo em vez de atribuir o erro ao comando seguinte).
3. **`max_voltage_rms`, `max_peak_v`, `max_current_a` e `ParameterOutOfBoundsError`** não mudam. Subir a tensão de teste para 220 ou 230 V **não** autoriza subir esses tetos.
4. **Confirmação digitada** antes de qualquer comando que energiza: `ENERGIZAR-TESTE`, `ENERGIZAR-COMANDOS`, `EXECUTAR-CLASSE-NN`, `EXECUTAR-CLASSES-<lista>`, `EXECUTAR-20-CLASSES` (e as dos diagnósticos). Não automatizar, não inventar o fator da probe.
5. **A resiliência por classe** isola falhas de **experimento** (RMS fora de tolerância, timeout de trigger, exceção em `gerar()`) e **aborta tudo**, sem tentar de novo, diante de `CommunicationError` ou `FalhaFatalDeInstrumento` (serial caiu, impossível confirmar OUTPUT, impossível recuperar o estado seguro). Não ampliar o que conta como "falha de experimento recuperável" sem entender por que aquele erro é seguro de ignorar.
6. **Cache de TRACe** (`program_capture`): sempre reconfirma contra `TRACe:CATalog?` antes de reaproveitar e é invalidado a cada reconexão (atributo da instância, não persistido). Não trocar por um cache entre processos sem resolver antes como `AMETEK_CLEAR_USER_WAVEFORMS=1` invalidaria um cache assim.

## 3. Se algo falhar de um jeito que indique infraestrutura comprometida

1. Confirme fisicamente **OUTPUT OFF** no painel da AMETEK.
2. **Não** execute de novo automaticamente.
3. Entregue os logs a quem diagnostica: para `run`/`run all`, `sessao.log` e `scpi_transcricao.log` da pasta `resultados\sessao_<timestamp>[_runNN]` mais recente; para `comm`, `trigger`, `lowvoltage` e `native`, o `logs\preflight_new-*.log` mais recente. (O arquivo `logs\startup-bench-*.log`, citado em documentos antigos, não é mais gerado.)
4. Não remova validações para "fazer passar".

Uma falha **isolada de experimento** durante `run all` **não** é motivo para parar: `Bancada.executar_bateria` já isola, registra e segue.

## 4. Onde a garantia é mais fraca (achados)

:::{caution} Limitação
Itens conferidos no código em 2026-10-16 que merecem atenção do responsável; nenhum foi corrigido (esta documentação não altera código):

- **Caminho `mestre.main()` em bancada.** `BENCH_MODE=1` e `ARM_OUTPUT=YES` escritos no ambiente energizam e rodam a bateria **sem confirmação digitada** ({doc}`codigo/mestre`, armadilha 10). O único script do repositório que o chama é o de simulação, com `BENCH_MODE=0`. Gravidade: média, hipótese de uso indevido.
- **Dois scripts de PyVISA cru** (`diag_saida_vs_medida.py`, `diag_fonte_vs_osciloscopio.py`) energizam sem passar pelo ORM nem por `validate_bench_configuration`; a proteção é a confirmação digitada e o `OUTPut:STATe OFF` no `finally` ({doc}`scpi/diagnostico`). Gravidade: média.
- **Três cópias dos limites** (300 Vrms e 415,8 Vp) em `start_bench_windows.ps1`, `relatorio_limites_bancada.py` e nos `diag_*` (R-6). Gravidade: média; recomendação do plano: unificar no código.
- **`program_capture` só avisa** quando o pico passa de `max_peak_v`; a recusa está em `mestre` (P-04). Gravidade: média.
- **Falha de desligamento não sobe** ({doc}`codigo/invariantes`, camada 13): quem confirma é o operador no painel. Gravidade: baixa, por desenho.
:::

## 5. Veja também

{doc}`operacao` (ligação física e CLI), {doc}`limites_e_calibracao` (pré-validação e fatores de extremo), {doc}`medicao/recalibracao`, {doc}`quirks` e {doc}`configuracao` (variáveis de ambiente e validações).
