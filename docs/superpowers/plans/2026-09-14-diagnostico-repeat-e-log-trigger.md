# Diagnóstico de atraso de evento (hipótese LIST:REPeat) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Documentar a hipótese de causa raiz do atraso de evento nas classes TRACe/waveform (`SOURce:LIST:REPeat` provavelmente dobrando cada ciclo), fechar os dois únicos pontos cegos que restam na instrumentação `set diagnostico on` do v1.8 (`VOLTage:MODE LIST` sem leitura "antes", `*TRG` sem leitura nenhuma), e aumentar a folga de `set margin on` de 25ms para 500ms de cada lado — para que a próxima sessão física confirme ou refute a hipótese, e capture o distúrbio inteiro mesmo que ele apareça bem mais tarde do que a folga atual cobre, sem precisar de nenhum código novo além destas mudanças pontuais.

**Architecture:** Nenhuma lógica nova de captura/análise — só (1) um novo `CHANGELOG/v1.9.md` registrando a hipótese e as duas mudanças com a evidência que as sustenta, (2) duas chamadas a `self._log_diagnostico(...)` em `logica/ametek_orm.py`, seguindo exatamente o idioma já usado pelo v1.8 para `SOURce:MODE ACDC` (par antes/depois, gated por `diagnostico_mode`, zero mudança de sequência SCPI), e (3) um único número mudando em `ExperimentoBase._calcular_margem()` (`logica/mestre.py`) — mesmo mecanismo `margin_mode` do v1.8, só o tamanho da folga muda.

**Tech Stack:** Python 3, `unittest` (padrão do projeto).

**Spec:** nenhum spec separado — a motivação completa está descrita abaixo (Contexto) e não precisa de um documento à parte dado o tamanho da mudança.

## Contexto (motivação, para quem executar sem ter visto a conversa)

Inspeção manual das capturas reais da sessão anterior mostrou que, mesmo
descontando o atraso universal de ~20ms no início da captura (fonte partindo
perto de 0pu antes de subir pra amplitude nominal — específico de classes
TRACe/LIST, não acontece nas nativas), o DISTÚRBIO em si (SAG, SWELL, NOTCH,
transiente etc.) aparece vários ciclos de 60Hz depois do que `gerar()`
assume. Duas fontes de evidência independentes:

- Inspeção manual de `08/TRANSIENT`: 5 cristas nominal vs. **9 cristas
  reais** (~1,8x).
- Detecção automática em duas etapas (ad-hoc, não commitada) contra 8
  classes TRACe reais (`07`, `09`, `10`, `11`, `13`, `14`, `16`, `17`):
  atraso do evento, contado a partir do fim da rampa inicial, sempre na
  faixa de **~2x a ~2,7x** o valor nominal.

Lendo o manual AMETEK (`7003-961 Rev AB`, biblioteca do painel-conhecimento
id 63, seção 4.17.5): `LIST:REPeat` é descrito como "the sequence of
**repeat values** for each data list point", parâmetros de **0 a 99**. A
leitura natural de uma faixa que começa em 0 é "0 = toca uma vez (nenhuma
repetição)" — ou seja, o valor `"1"` que `program_capture()` envia pra CADA
um dos 12 ciclos (`logica/ametek_orm.py`, variável `repeats`) provavelmente
significa "toca duas vezes" (original + 1 repetição), não "toca uma vez".
Isso explicaria o padrão observado: a portadora de 60Hz continua parecendo
correta (cada ciclo individual ainda tem 60Hz), mas alcançar o ciclo N do
PROGRAMA passa a exigir ~2N ciclos de relógio real.

`preflight_new.py --list-diagnostics` já testou 4 variantes de CABEÇALHO
desse comando (por causa de um erro -113 documentado), mas nunca testou o
VALOR — se `1` é "uma vez" ou "duas vezes" na Rev. 5.53 real. Confirmar isso
não precisa de código novo: o v1.8 já loga, com `set diagnostico on`, os
timestamps monotônicos de `arm_transient_apos_init` (logo após
`INITiate:IMMediate`) e `transiente_concluido` (quando `TRIGger:STATe?`
volta a `IDLE`). Nominal: ~200ms entre os dois (12 ciclos × 16,67ms). Se sair
~400ms na próxima sessão, a hipótese do dobro está confirmada.

O único gap real de instrumentação: `_log_diagnostico()` já tem par
antes/depois pra `SOURce:MODE ACDC` (`antes_sourcemode_acdc`/
`apos_sourcemode_acdc`), mas **só tem "depois" pra `VOLTage:MODE LIST`**
(`apos_voltage_mode_list`, sem `antes_voltage_mode_list`) — não dá pra saber
hoje se a tensão já caía antes desse comando específico ou só depois. E
`trigger()` (onde `*TRG` é enviado — o disparo real do transiente) **não tem
nenhum log de diagnóstico**.

### Consequência pro `set margin on`: 25ms não cobre mais o pior caso hipotetizado

`_calcular_margem()` (`logica/mestre.py:674-683`, desde o v1.8) foi
dimensionado só pro atraso universal de rampa inicial (~20ms,
CHANGELOG/v1.7.md): 25ms de folga de cada lado, 750 amostras a 30kSa/s. A
hipótese acima é sobre um fenômeno DIFERENTE e maior — se `LIST:REPeat`
estiver dobrando, não é só o início da captura que atrasa, é o DISTÚRBIO
inteiro, em até ~2,7x o nominal medido nas 8 classes reais. Numa janela
nominal de 200ms (12 ciclos), um distúrbio programado perto do fim da lista
pode só ocorrer de fato perto de ~540ms (2,7 x 200ms) — bem além dos 25ms
de folga atuais. Com a folga de hoje, `set margin on` cortaria exatamente a
evidência que a próxima sessão física precisa capturar pra confirmar ou
refutar a hipótese (não só os timestamps de diagnóstico, mas a forma de
onda em si, pro pós-processamento em `analisar_sessao.py`). A Task 3
aumenta a folga pra 500ms de cada lado: cobre o pior caso hipotetizado
(~540ms de atraso, medido a partir do fim da rampa) com ~160ms de sobra, e
o total resultante (36000 pontos) continua dentro do teto de 60000 pontos
que `logica/oscilloscope_orm.py` já impõe via `:WAVeform:POINts` — tanto em
`configure_acquisition()` (linha 212) quanto em `get_waveform()` (linha
316). O próprio spec original do v1.8
(`docs/superpowers/specs/2026-09-11-sessao-bancada-v18-design.md:164`) já
tratava os 25ms como "parâmetro de implementação", não um valor fixo de
projeto — aumentar não muda contrato nenhum.

## Global Constraints

- Nenhuma mudança de sequência, conteúdo ou ordem de comando SCPI — só
  leitura de estado adicional (`query`), gated por `self.diagnostico`
  exatamente como todo o resto de `_log_diagnostico()` no v1.8 (ver
  "Limites inegociáveis" em `AGENTS.md`: "O log de diagnóstico nunca
  reordena nem adiciona um comando SCPI que hoje não existe").
- A correção candidata (`"1"` → `"0"` em `SOURce:LIST:REPeat`) **não é
  aplicada por este plano** — só a hipótese é documentada. Aplicar a
  correção antes de confirmar na bancada seria alterar comportamento de
  saída real sem validação, o que este plano explicitamente evita.
- `tests/test_offline.py` roda com `python -m unittest tests.test_offline -v` a partir da raiz do projeto; todo teste novo precisa passar nesse comando antes do commit de cada task.
- O aumento de `set margin on` (25ms → 500ms de cada lado, Task 3) usa
  exatamente o mecanismo já existente desde o v1.8 (`_calcular_margem()`,
  gated por `margin_mode`, só afeta captura real) — não é um mecanismo
  novo, só um número maior. Não conflita com a constraint SCPI acima porque
  `configure_acquisition()` fala com o OSCILOSCÓPIO (Keysight), não com a
  fonte AMETEK; nenhum comando SCPI enviado à fonte muda.
- Teto rígido a respeitar em qualquer margem futura: `oscilloscope_orm.py`
  fixa `:WAVeform:POINts 60000` (`configure_acquisition()` linha 212,
  `get_waveform()` linha 316) — `config.points + 2*margem_amostras` tem que
  ficar abaixo disso. Com 500ms (15000 amostras de cada lado) e
  `config.points=6000`, o total é 36000 — dentro do teto com folga
  (verificado por teste dedicado na Task 3).

---

## Task 1: `CHANGELOG/v1.9.md` — documentar a hipótese

**Files:**
- Create: `CHANGELOG/v1.9.md`

**Interfaces:**
- Consumes: nada (documentação).
- Produces: nada (documentação) — mas é o registro que a Task 2 referencia no comentário do código.

- [x] **Step 1: Escrever o changelog**

Criar `CHANGELOG/v1.9.md`, seguindo o formato de `CHANGELOG/v1.7.md`/`v1.8.md` ("Por quê", "O que mudou", "O que não mudou", "Ver também"):

```markdown
# v1.9 — dois pontos de diagnóstico, folga de `margin on` maior e hipótese de causa raiz do atraso de evento

Motivado por inspeção manual das capturas reais da sessão anterior (mesmas
que motivaram o v1.8): mesmo descontando o atraso universal de ~20ms no
início da captura (fonte partindo perto de 0pu antes de subir pra amplitude
nominal, específico de classes TRACe/LIST), o DISTÚRBIO em si — SAG, SWELL,
NOTCH, transiente, etc. — aparece vários ciclos de 60Hz depois do que
`gerar()` assume. Medido em duas fontes independentes: inspeção manual de
`08/TRANSIENT` (5 cristas nominal vs. 9 cristas reais, ~1,8x) e detecção
automática em duas etapas contra 8 classes TRACe reais (`07`, `09`, `10`,
`11`, `13`, `14`, `16`, `17`): atraso do evento, contado a partir do fim da
rampa inicial, na faixa de ~2 a ~2,7x o valor nominal em todas elas.

## Hipótese de causa raiz: `SOURce:LIST:REPeat` pode estar dobrando cada ciclo

O manual AMETEK (`7003-961 Rev AB`, seção 4.17.5) descreve `LIST:REPeat`
como "the sequence of **repeat values** for each data list point", com
parâmetros de **0 a 99**. A leitura natural de uma faixa que começa em 0 é
"0 = toca uma vez (nenhuma repetição)": ou seja, o valor **1** — que
`program_capture()` envia pra CADA um dos 12 ciclos
(`repeats = ",".join("1" for _ in trace_names)`, `logica/ametek_orm.py`) —
provavelmente significa "toca duas vezes" (a original + 1 repetição), não
"toca uma vez".

Se cada ciclo do LIST está sendo reproduzido em dobro, a portadora de 60Hz
continua parecendo correta (cada ciclo individual ainda tem 60Hz — é por
isso que a forma capturada parece visualmente normal), mas alcançar o ciclo
N do PROGRAMA passa a exigir ~2N ciclos de relógio real — exatamente o
padrão medido acima (~1,8x a ~2,7x, nunca perto de 1x nem de 3x).

`preflight_new.py --list-diagnostics` já testou 4 variantes de CABEÇALHO
desse comando (`SOURce:LIST:REPeat` vs `LIST:REPeat:COUNt` etc., por causa
de outro erro -113 já documentado), mas **nunca testou o VALOR** — se `1`
seria "uma vez" ou "duas vezes" na Rev. 5.53 real. É uma lacuna real, não só
teórica.

**Não corrigido nesta versão** — é só uma hipótese, ainda não confirmada em
bancada. Correção candidata, SE confirmada: trocar `"1"` por `"0"` em
`repeats = ",".join("1" for _ in trace_names)` (`program_capture()`) e no
mesmo padrão em `logica/ametek_orm.py:697` (`"SOURce:LIST:REPeat 1,1"`,
usado em teste de estado de flags LIST).

## Como confirmar ou refutar na próxima sessão física

Nenhum hardware novo nem mudança de comando SCPI necessária — só rodar com
`set diagnostico on` e comparar dois timestamps que o v1.8 já loga:
`arm_transient_apos_init` (logo após `INITiate:IMMediate`, início real do
armamento) e `transiente_concluido` (quando `TRIGger:STATe?` volta a
`IDLE`, fim real da lista). Nominal: ~200ms (12 ciclos × 16,67ms) entre os
dois. Se sair ~400ms, a hipótese do dobro está confirmada.

## `set margin on`: folga de 25ms para 500ms de cada lado

Efeito colateral direto da hipótese acima: `_calcular_margem()`
(`logica/mestre.py`) dimensionava a folga de `margin on` só pro atraso
universal de ~20ms na rampa inicial (CHANGELOG/v1.7.md) — 25ms de cada
lado. Mas se `LIST:REPeat` estiver dobrando, o atraso não é só na rampa: é
o DISTÚRBIO inteiro, até ~2,7x o nominal. Numa janela de 200ms, isso pode
significar o evento ocorrendo perto de ~540ms — muito além dos 25ms de
folga atuais. Sem aumentar a folga, `set margin on` cortaria exatamente a
captura que a próxima sessão física precisa pra confirmar ou refutar a
hipótese.

A folga sobe para 500ms de cada lado (15000 amostras a 30kSa/s — cobre o
pior caso hipotetizado, ~540ms, com ~160ms de sobra) e continua dentro do
teto de 60000 pontos que `logica/oscilloscope_orm.py` já impõe via
`:WAVeform:POINts` (36000 pontos totais com a folga nova). Mesmo mecanismo
do v1.8 (`margin_mode`, só afeta captura real, `OFF` por padrão) — só o
número muda.

## O que mudou

- **`logica/ametek_orm.py`** — dois pontos de diagnóstico novos, gated por
  `diagnostico_mode` como todo o resto do v1.8, sem mudar nenhuma sequência
  ou conteúdo de comando SCPI:
  - `_log_diagnostico("antes_voltage_mode_list")` dentro de
    `program_capture()`, imediatamente ANTES da escrita `VOLTage:MODE LIST`
    — par com o `apos_voltage_mode_list` que já existia desde o v1.8, mesmo
    idioma de `antes_sourcemode_acdc`/`apos_sourcemode_acdc`. Sem esse par
    "antes", não dava pra saber se a tensão já estava caindo antes deste
    comando específico ou só depois dele.
  - `_log_diagnostico("apos_trigger")` dentro de `trigger()`, logo depois do
    `*TRG` — esse ponto (o disparo real do transiente) não tinha leitura de
    diagnóstico nenhuma até agora; fecha a lacuna de instrumentação entre
    "armado" e "concluído".
- **`tests/test_offline.py`** — 4 testes novos em `DiagnosticoLogTests`:
  ordem antes/depois de `antes_voltage_mode_list`/`apos_voltage_mode_list`,
  e que nenhum dos dois pontos novos muda qualquer WRITE enviado ao
  instrumento (mesmo padrão de verificação já usado pra
  `trigger_step()`/`trigger_pulse()` no v1.8).
- **`logica/mestre.py`** — `ExperimentoBase._calcular_margem()` passa a
  calcular 500ms de folga de cada lado (antes: 25ms) quando `margin_mode`
  está ativo; mecanismo idêntico ao v1.8, só o número muda.
- **`logica/cli.py`** e **`README.md`** — texto de ajuda de `set margin
  on|off` atualizado de "~25ms" para "~500ms de cada lado".
- **`tests/test_offline.py`** — `MargemCapturaTests` atualizado pro novo
  valor (15000 amostras), mais um teste novo confirmando que o total fica
  abaixo do teto de 60000 pontos do osciloscópio.

## O que **não** mudou

- Nenhuma sequência, conteúdo ou ordem de comando SCPI — só leitura de
  estado adicional (`query`), gated por `diagnostico_mode`, exatamente como
  todo o resto da instrumentação do v1.8.
- `SOURce:LIST:REPeat` continua enviando `"1"` por ciclo — a correção
  candidata NÃO foi aplicada, só documentada como hipótese a testar.
- O mecanismo de `margin on` (`margin_mode`, gated, só afeta captura real,
  `OFF` por padrão, `analisar_sessao.py` recortando pelos metadados de
  margem) — só o tamanho da folga (25ms → 500ms) muda, não como funciona.
- `AMETEK_PORT=COM10`, `AMETEK_BAUDRATE=115200`, `max_voltage_rms`,
  `max_peak_v`, `max_current_a`, `ParameterOutOfBoundsError`.

## Ver também

`CHANGELOG/v1.7.md` (achado original de atraso, hipótese de
`VOLTage:MODE LIST` zerando a saída), `CHANGELOG/v1.8.md` (`set diagnostico
on`, `set margin on`), `docs/superpowers/specs/2026-09-11-sessao-bancada-v18-design.md`
(spec original do v1.8, já tratava os 25ms de margem como "parâmetro de
implementação"), manual `7003-961 Rev AB` (biblioteca do
painel-conhecimento, id 63) seções 4.17.1–4.17.6 (List Count/Dwell/
Repeat/Step) e 4.11.4 (Trigger Out / BOT).
```

- [x] **Step 2: Commit**

```bash
git add CHANGELOG/v1.9.md
git commit -m "docs: changelog v1.9 - hipotese LIST:REPeat, pontos de diagnostico e margem maior"
```

---

## Task 2: fechar os dois pontos cegos de `_log_diagnostico`

**Files:**
- Modify: `logica/ametek_orm.py`
- Test: `tests/test_offline.py` (classe `DiagnosticoLogTests` já existente, linha 562 hoje)

**Interfaces:**
- Consumes: `self._log_diagnostico(ponto: str, **extra) -> None` (já existe desde o v1.8, `ametek_orm.py:408`).
- Produces: nenhuma interface nova — só dois pontos de log a mais no mesmo mecanismo existente.

- [x] **Step 1: Escrever os testes (falhando)**

Adicionar em `tests/test_offline.py`, dentro de `class DiagnosticoLogTests(unittest.TestCase):`, logo depois de `test_trigger_step_com_diagnostico_nao_muda_writes_enviados` (linha 618 hoje, antes de `class KeysightTests`):

```python
    def test_program_capture_com_diagnostico_loga_antes_e_depois_voltage_mode_list(self):
        # Hipótese em aberto (CHANGELOG/v1.9.md): a captura real de classes
        # TRACe/LIST começa com a saída visivelmente zerada por ~20ms. Este
        # par de logs (mesmo idioma de antes_sourcemode_acdc/
        # apos_sourcemode_acdc) é o que vai permitir, na próxima sessão
        # física, ver se a tensão já cai ANTES de VOLTage:MODE LIST ou só
        # DEPOIS dele.
        t = np.arange(6000, dtype=np.float64) / 30000.0
        voltage = np.sin(2.0 * np.pi * 50.0 * t)
        fonte = AmetekMX30(simulated=True, diagnostico=True, max_voltage_rms=10.0, max_peak_v=100.0)
        with self.assertLogs("AmetekORM", level="INFO") as captura:
            fonte.program_capture(voltage, base_voltage_rms=5.0, frequency_hz=50.0)
        linhas = [registro.getMessage() for registro in captura.records]
        indice_antes = next(i for i, linha in enumerate(linhas) if "ponto=antes_voltage_mode_list" in linha)
        indice_depois = next(i for i, linha in enumerate(linhas) if "ponto=apos_voltage_mode_list" in linha)
        self.assertLess(indice_antes, indice_depois)

    def test_program_capture_com_diagnostico_nao_muda_writes_enviados(self):
        t = np.arange(6000, dtype=np.float64) / 30000.0
        voltage = np.sin(2.0 * np.pi * 50.0 * t)
        sem_log = AmetekMX30(simulated=True, diagnostico=False, max_voltage_rms=10.0, max_peak_v=100.0)
        sem_log.program_capture(voltage, base_voltage_rms=5.0, frequency_hz=50.0)
        com_log = AmetekMX30(simulated=True, diagnostico=True, max_voltage_rms=10.0, max_peak_v=100.0)
        com_log.program_capture(voltage, base_voltage_rms=5.0, frequency_hz=50.0)

        def escritas(log):
            return [comando for comando in log if not comando.endswith("?")]

        self.assertEqual(escritas(sem_log.command_log), escritas(com_log.command_log))

    def test_trigger_com_diagnostico_loga_apos_trigger(self):
        fonte = AmetekMX30(simulated=True, diagnostico=True, max_voltage_rms=10.0, max_peak_v=100.0)
        fonte.write("INITiate:IMMediate")  # simulado: TRIGger:STATe? -> ARM (ver _simulate_write)
        with self.assertLogs("AmetekORM", level="INFO") as captura:
            fonte.trigger()
        linhas = [registro.getMessage() for registro in captura.records]
        self.assertTrue(any("ponto=apos_trigger" in linha for linha in linhas))

    def test_trigger_com_diagnostico_nao_muda_writes_enviados(self):
        sem_log = AmetekMX30(simulated=True, diagnostico=False, max_voltage_rms=10.0, max_peak_v=100.0)
        sem_log.write("INITiate:IMMediate")
        sem_log.trigger()
        com_log = AmetekMX30(simulated=True, diagnostico=True, max_voltage_rms=10.0, max_peak_v=100.0)
        com_log.write("INITiate:IMMediate")
        com_log.trigger()

        def escritas(log):
            return [comando for comando in log if not comando.endswith("?")]

        self.assertEqual(escritas(sem_log.command_log), escritas(com_log.command_log))
```

- [x] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m unittest tests.test_offline.DiagnosticoLogTests -v`
Expected: FAIL nos 4 testes novos — `StopIteration` (não acha `ponto=antes_voltage_mode_list` nas linhas) nos dois primeiros, `assertTrue` falso (não acha `ponto=apos_trigger`) no terceiro; o quarto (`nao_muda_writes`) deve passar por acidente (ainda não há write novo pra comparar).

- [x] **Step 3: Implementar `antes_voltage_mode_list` em `program_capture()`**

Em `logica/ametek_orm.py`, dentro do laço de comandos de `program_capture()` (por volta da linha 1111-1135 hoje), o bloco:

```python
            self.write(command)
            errors = self.check_errors()
            if errors:
                raise InstrumentHardwareError(
                    f"AMETEK rejeitou {command!r} durante programação da lista: {errors}"
                )
            if command == "VOLTage:MODE LIST":
                self._log_diagnostico("apos_voltage_mode_list")
```

vira:

```python
            if command == "VOLTage:MODE LIST":
                # Par "antes/depois" da mesma leitura de tensão, mesmo idioma
                # de antes_sourcemode_acdc/apos_sourcemode_acdc acima —
                # hipótese em aberto (CHANGELOG/v1.9.md): a captura real de
                # classes TRACe/LIST começa com a saída visivelmente zerada
                # por ~20ms; este par de logs deixa registrado se a tensão já
                # estava caindo ANTES deste comando específico ou só cai
                # DEPOIS dele.
                self._log_diagnostico("antes_voltage_mode_list")
            self.write(command)
            errors = self.check_errors()
            if errors:
                raise InstrumentHardwareError(
                    f"AMETEK rejeitou {command!r} durante programação da lista: {errors}"
                )
            if command == "VOLTage:MODE LIST":
                self._log_diagnostico("apos_voltage_mode_list")
```

- [x] **Step 4: Implementar `apos_trigger` em `trigger()`**

Em `logica/ametek_orm.py`, `trigger()` (por volta da linha 1292-1296 hoje):

```python
    def trigger(self) -> None:
        state = self.query("TRIGger:STATe?").strip().upper()
        if not state.startswith(("ARM", "WTRIG")):
            raise InstrumentHardwareError(f"AMETEK não estava armada antes de *TRG: {state!r}")
        self.write("*TRG")
```

vira:

```python
    def trigger(self) -> None:
        state = self.query("TRIGger:STATe?").strip().upper()
        if not state.startswith(("ARM", "WTRIG")):
            raise InstrumentHardwareError(f"AMETEK não estava armada antes de *TRG: {state!r}")
        self.write("*TRG")
        # Único ponto do caminho de trigger sem leitura de diagnóstico
        # nenhuma até agora — fecha a linha do tempo entre
        # arm_transient_apos_init (INITiate:IMMediate) e transiente_concluido
        # (TRIGger:STATe? IDLE): o timestamp monotônico daqui é a referência
        # pra testar a hipótese de SOURce:LIST:REPeat (CHANGELOG/v1.9.md)
        # medindo quanto tempo o transiente realmente leva pra concluir a
        # partir do disparo de verdade, não só da armação.
        self._log_diagnostico("apos_trigger")
```

- [x] **Step 5: Rodar os testes e confirmar que passam**

Run: `python -m unittest tests.test_offline.DiagnosticoLogTests -v`
Expected: PASS em todos os 8 testes da classe (4 já existentes + 4 novos)

- [x] **Step 6: Rodar a suíte inteira**

Run: `python -m unittest tests.test_offline -v`
Expected: PASS em todos os testes (75 + 4 novos = 79)

- [x] **Step 7: Commit**

```bash
git add logica/ametek_orm.py tests/test_offline.py
git commit -m "feat: log de diagnostico antes de VOLTage:MODE LIST e apos *TRG"
```

---

## Task 3: aumentar a folga de `set margin on` de 25ms para 500ms de cada lado

**Files:**
- Modify: `logica/mestre.py` (`ExperimentoBase._calcular_margem`, linhas 674-683 hoje)
- Modify: `logica/cli.py` (texto de ajuda, linhas 55-57 hoje)
- Modify: `README.md` (tabela de comandos, linha 260 hoje)
- Test: `tests/test_offline.py` (classe `MargemCapturaTests` já existente, linha 1604 hoje)

**Interfaces:**
- Consumes: nada novo.
- Produces: `ExperimentoBase._calcular_margem(*, margin_mode: bool, config_points: int, fs_hz: float) -> Tuple[int, int]` continua com a mesma assinatura (já existe desde o v1.8) — só o valor interno de folga muda; nenhum chamador (`executar()`, `_ler_captura()`, `_salvar_classe()`) precisa mudar.

- [x] **Step 1: Atualizar os testes (falhando)**

Em `tests/test_offline.py`, dentro de `class MargemCapturaTests(unittest.TestCase):` (linha 1604 hoje), o teste:

```python
    def test_margin_on_adiciona_amostras_de_cada_lado(self):
        margem_amostras, pontos_totais = mestre.ExperimentoBase._calcular_margem(
            margin_mode=True, config_points=6000, fs_hz=30_000.0,
        )
        self.assertEqual(margem_amostras, 750)  # 25ms * 30kSa/s
        self.assertEqual(pontos_totais, 6000 + 2 * 750)
```

vira:

```python
    def test_margin_on_adiciona_amostras_de_cada_lado(self):
        margem_amostras, pontos_totais = mestre.ExperimentoBase._calcular_margem(
            margin_mode=True, config_points=6000, fs_hz=30_000.0,
        )
        self.assertEqual(margem_amostras, 15_000)  # 500ms * 30kSa/s
        self.assertEqual(pontos_totais, 6000 + 2 * 15_000)

    def test_margin_on_fica_dentro_do_teto_de_pontos_do_osciloscopio(self):
        # oscilloscope_orm.py fixa ":WAVeform:POINts 60000" tanto em
        # configure_acquisition() quanto em get_waveform() — um pontos_totais
        # acima disso faria a preamble real declarar menos pontos do que
        # pedido, e get_waveform() levantaria OscilloscopeError na próxima
        # sessão física (CHANGELOG/v1.9.md).
        _, pontos_totais = mestre.ExperimentoBase._calcular_margem(
            margin_mode=True, config_points=6000, fs_hz=30_000.0,
        )
        self.assertLess(pontos_totais, 60_000)
```

- [x] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m unittest tests.test_offline.MargemCapturaTests -v`
Expected: FAIL em `test_margin_on_adiciona_amostras_de_cada_lado` (`750 != 15000`). `test_margin_on_fica_dentro_do_teto_de_pontos_do_osciloscopio` passa mesmo antes da mudança (7500 já está abaixo do teto) — é um teste de regressão pro teto em si, não uma prova desta mudança específica, mas fica na mesma classe por testar a mesma função.

- [x] **Step 3: Implementar a folga de 500ms**

Em `logica/mestre.py`, o método:

```python
    @staticmethod
    def _calcular_margem(*, margin_mode: bool, config_points: int, fs_hz: float) -> Tuple[int, int]:
        """``margin on``: 25ms de folga de cada lado (750 amostras a 30kSa/s
        — cobre com sobra o maior deslocamento já medido, ~20ms/600
        amostras, ver CHANGELOG/v1.7.md). Devolve (amostras de margem de UM
        lado, total de amostras incluindo os dois lados)."""
        if not margin_mode:
            return 0, config_points
        margem_amostras = int(round(0.025 * fs_hz))
        return margem_amostras, config_points + 2 * margem_amostras
```

vira:

```python
    @staticmethod
    def _calcular_margem(*, margin_mode: bool, config_points: int, fs_hz: float) -> Tuple[int, int]:
        """``margin on``: 500ms de folga de cada lado (15000 amostras a
        30kSa/s). Os 25ms originais (CHANGELOG/v1.7.md) só cobriam o atraso
        universal de rampa inicial (~20ms); a hipótese LIST:REPeat
        (CHANGELOG/v1.9.md) prevê o DISTÚRBIO em si atrasando até ~2,7x a
        janela nominal de 200ms (~540ms) — 500ms de cada lado cobre esse
        pior caso com sobra e ainda fica dentro do teto de 60000 pontos
        (``:WAVeform:POINts``, ``oscilloscope_orm.py``) somado aos 6000
        pontos nominais (36000 pontos, abaixo do teto de 60000). Devolve
        (amostras de margem de UM lado, total de amostras incluindo os dois
        lados)."""
        if not margin_mode:
            return 0, config_points
        margem_amostras = int(round(0.5 * fs_hz))
        return margem_amostras, config_points + 2 * margem_amostras
```

- [x] **Step 4: Rodar os testes e confirmar que passam**

Run: `python -m unittest tests.test_offline.MargemCapturaTests -v`
Expected: PASS nos 4 testes da classe (3 já existentes — um deles,
`test_margin_on_adiciona_amostras_de_cada_lado`, com os valores atualizados
— + 1 novo, `test_margin_on_fica_dentro_do_teto_de_pontos_do_osciloscopio`).

- [x] **Step 5: Atualizar os textos de ajuda**

Em `logica/cli.py` (linhas 55-57 hoje), o texto:

```
  set margin on|off   Liga/desliga captura com folga extra (~25ms de cada
                       lado) antes/depois da janela nominal — salva o array
                       bruto, sem recorte automático. Só afeta captura real.[OFF]
```

vira:

```
  set margin on|off   Liga/desliga captura com folga extra (~500ms de cada
                       lado) antes/depois da janela nominal — salva o array
                       bruto, sem recorte automático. Só afeta captura real.[OFF]
```

Em `README.md` (linha 260 hoje), a linha da tabela:

```
| `set margin on\|off` | não | liga/desliga captura com ~25ms de folga extra antes/depois da janela nominal, salva o array bruto sem recorte automático — só afeta captura real (`OFF` por padrão) |
```

vira:

```
| `set margin on\|off` | não | liga/desliga captura com ~500ms de folga extra antes/depois da janela nominal, salva o array bruto sem recorte automático — só afeta captura real (`OFF` por padrão) |
```

- [x] **Step 6: Rodar a suíte inteira**

Run: `python -m unittest tests.test_offline -v`
Expected: PASS em todos os testes (79 da Task 2 + 1 novo de teto = 80).

- [x] **Step 7: Commit**

```bash
git add logica/mestre.py logica/cli.py README.md tests/test_offline.py
git commit -m "feat: aumenta folga de set margin on de 25ms para 500ms de cada lado"
```

---

## Verificação final

- [x] Rodar `python -m unittest tests.test_offline -v` a partir da raiz do projeto e confirmar 0 falhas (80 testes: 75 pré-existentes + 4 da Task 2 + 1 da Task 3).
- [x] Conferir manualmente que nenhum `command_log`/sequência de escrita SCPI mudou entre `diagnostico=True` e `diagnostico=False` em `program_capture()` e `trigger()` (já coberto pelos testes `*_nao_muda_writes_enviados`, mas vale reler o diff antes de commitar).
- [x] Conferir manualmente que a folga nova de `set margin on` (500ms) não muda nenhum comando enviado à AMETEK — só os parâmetros passados a `osc.configure_acquisition()` (Keysight), já coberto pelo teste de teto de 60000 pontos da Task 3, mas vale reler o diff de `_calcular_margem()` antes de commitar.
- [ ] Na próxima sessão física: rodar com `set diagnostico on` e `set margin on`, pegar os timestamps de `arm_transient_apos_init` e `transiente_concluido` de uma classe TRACe (ex.: `13/SWELL_HARMONICS`), e conferir se a diferença é ~200ms (hipótese refutada) ou ~400ms (hipótese confirmada — aplicar a correção `"1"→"0"` documentada no CHANGELOG antes da próxima bateria completa). Com `margin on` na folga nova, a captura bruta salva também deve conter o distúrbio inteiro mesmo se ele ocorrer bem depois do fim da janela nominal de 200ms — conferir visualmente em `<pasta_sessao>/analise/` (`analisar_sessao.py`) antes de decidir se a folga de 500ms foi suficiente ou se o pior caso observado precisa de mais.
