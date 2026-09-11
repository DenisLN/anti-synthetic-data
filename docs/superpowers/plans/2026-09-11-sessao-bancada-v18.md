# Sessão de Bancada v1.8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao operador, numa única visita de bancada, os meios de (a) coletar dados sem perder a cauda dos distúrbios (`set margin on`), (b) confirmar ao vivo as três hipóteses de causa raiz do v1.7 sobre atraso/race condition (`set diagnostico on`), (c) cobrir níveis/parâmetros de forma determinística em vez de sorteio redundante (`set capturas N`), e (d) nunca mais sobrescrever uma sessão de captura anterior.

**Architecture:** Tudo opt-in via novos globais mutáveis em `mestre.py` (mesmo idioma de `OUTPUT_ARMED`/`autorizar_saida()`), lidos por `Config` (campos novos com default = comportamento de hoje). `ExperimentoBase.executar()` ganha um ramo de remapeamento de índice só ativo quando `capturas_override is not None` — sem isso, byte-a-byte igual a hoje. `AmetekMX30` ganha um logger de diagnóstico opt-in, sem mudar nenhuma ordem/conteúdo de comando SCPI existente. Um script novo, offline, fecha o loop de análise.

**Tech Stack:** Python 3, NumPy, PyVISA/PyMeasure (já em uso), `unittest` (`tests/test_offline.py`), matplotlib (script offline novo).

**Spec:** [docs/superpowers/specs/2026-09-11-sessao-bancada-v18-design.md](../specs/2026-09-11-sessao-bancada-v18-design.md)

## Global Constraints

- Nada disto muda `SIM_CAPTURES_PER_CLASS`, a ordem/fórmula que `gerar()` usa para indexar `NIVEIS` hoje, nem qualquer valor de `experimentos.txt` — o dataset simulado fica bit-a-bit idêntico.
- Nenhuma mudança em `max_voltage_rms`, `max_peak_v`, `max_current_a`, `ParameterOutOfBoundsError`, `AMETEK_PORT`/`AMETEK_BAUDRATE`, ou nas confirmações de energização (`ENERGIZAR-*`/`EXECUTAR-*`) — ver "Limites inegociáveis" em `AGENTS.md`.
- Todo campo novo em `Config` tem um default que reproduz o comportamento de hoje (`capturas_override=None`, `margin_mode=False`, `diagnostico_mode=False`) — testes existentes que constroem `Config` sem esses campos continuam passando sem alteração.
- O log de diagnóstico nunca reordena nem adiciona um comando SCPI que hoje não existe — só lê estado (`query`) e escreve no logger.
- Comandos novos da CLI (`set margin`, `set diagnostico`, `set capturas`) nunca energizam a saída por si — só mudam configuração lida por comandos que já pedem confirmação.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `logica/sinais.py` | + `valor_para_captura()` — amostragem determinística vs. sorteio, função pura. |
| `logica/ametek_orm.py` | + `diagnostico` no `__init__`, `_log_diagnostico()`, chamadas nos pontos-chave. |
| `logica/mestre.py` | `Config` (3 campos novos), globais de sessão, `ExperimentoBase.total_niveis()`, remapeamento de índice em `executar()`, margem em `_capturar_real`/`_validar_captura`, `_salvar_classe()` por captura. |
| `experimentos_nativos/04.py`, `19.py`; `experimentos_waveform/06.py`, `08.py`, `09.py` | trocam `rng.uniform` por `sinais.valor_para_captura`. |
| `experimentos_nativos/05.py` | + `total_niveis()` (1 linha — `NIVEIS_THD` é global de módulo, não seria descoberto pelo default de `total_niveis()`). |
| `logica/cli.py` | `cmd_set`, pasta de sessão lazy, `HELP_TEXT`/`status` atualizados. |
| `logica/analisar_sessao.py` | **novo** — script offline (sem hardware) de análise de uma pasta de sessão. |
| `tests/test_offline.py` | testes novos para cada peça acima, tudo simulado. |
| `CHANGELOG/v1.8.md` | **novo**. |
| `README.md` | §5.3 e §5.8 atualizadas. |

---

## Task 1: `sinais.valor_para_captura`

**Files:**
- Modify: `logica/sinais.py`
- Test: `tests/test_offline.py` (nova classe `ValorParaCapturaTests`)

**Interfaces:**
- Produces: `valor_para_captura(rng: np.random.Generator, lo: float, hi: float, capture_index: int, total_capturas: int, cobertura_ativa: bool) -> float`

- [ ] **Step 1: Write the failing tests**

Adicionar em `tests/test_offline.py`, perto de `SignalTests` (mesmo arquivo já importa `sinais`):

```python
class ValorParaCapturaTests(unittest.TestCase):
    def test_cobertura_inativa_sempre_sorteia(self):
        rng = np.random.default_rng(1)
        valor = sinais.valor_para_captura(rng, 5.0, 10.0, 0, 1, cobertura_ativa=False)
        self.assertTrue(5.0 <= valor <= 10.0)

    def test_total_capturas_1_sempre_sorteia_mesmo_com_cobertura_ativa(self):
        rng = np.random.default_rng(1)
        valor = sinais.valor_para_captura(rng, 5.0, 10.0, 0, 1, cobertura_ativa=True)
        self.assertTrue(5.0 <= valor <= 10.0)

    def test_cobertura_ativa_cobre_exatamente_lo_e_hi_nas_pontas(self):
        rng = np.random.default_rng(1)
        primeiro = sinais.valor_para_captura(rng, 5.0, 10.0, 0, 4, cobertura_ativa=True)
        ultimo = sinais.valor_para_captura(rng, 5.0, 10.0, 3, 4, cobertura_ativa=True)
        self.assertEqual(primeiro, 5.0)
        self.assertEqual(ultimo, 10.0)

    def test_cobertura_ativa_e_deterministica_independente_do_rng(self):
        valor_a = sinais.valor_para_captura(np.random.default_rng(1), 0.0, 1.0, 2, 5, cobertura_ativa=True)
        valor_b = sinais.valor_para_captura(np.random.default_rng(999), 0.0, 1.0, 2, 5, cobertura_ativa=True)
        self.assertEqual(valor_a, valor_b)
```

Precisa de `import sinais` no topo do arquivo de teste — já existe `from sinais import ruido_awgn, snr_medida`; trocar para `import sinais` (mantendo os `from sinais import ...` existentes, que continuam válidos) ou simplesmente adicionar `import sinais` numa linha nova logo abaixo.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_offline.py -k ValorParaCaptura -v` (ou `python -m unittest tests.test_offline.ValorParaCapturaTests -v` se não houver pytest instalado)
Expected: FAIL com `AttributeError: module 'sinais' has no attribute 'valor_para_captura'`

- [ ] **Step 3: Implement**

Adicionar em `logica/sinais.py`, depois de `janela()`:

```python
def valor_para_captura(
    rng: np.random.Generator,
    lo: float,
    hi: float,
    capture_index: int,
    total_capturas: int,
    *,
    cobertura_ativa: bool,
) -> float:
    """Decide entre sorteio (comportamento de sempre) e cobertura
    determinística do intervalo ``[lo, hi]`` via ``linspace``.

    Usado pelas classes de parâmetro contínuo (04/06/08/09/19) quando a
    bancada real roda com ``set capturas N`` (``cobertura_ativa=True``,
    ``total_capturas=N``): em vez de N sorteios independentes que podem se
    repetir/concentrar, cada captura recebe um ponto igualmente espaçado de
    ``lo`` a ``hi`` — ``capture_index=0`` sempre bate exatamente em ``lo``,
    o último índice sempre bate exatamente em ``hi``.

    Com ``cobertura_ativa=False`` (dataset simulado, ou bancada sem
    ``set capturas``) ou ``total_capturas<=1``, comportamento idêntico ao
    ``rng.uniform(lo, hi)`` de sempre.
    """
    if not cobertura_ativa or total_capturas <= 1:
        return float(rng.uniform(lo, hi))
    return float(np.linspace(lo, hi, total_capturas)[capture_index])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_offline.py -k ValorParaCaptura -v`
Expected: PASS (4 testes)

- [ ] **Step 5: Commit**

```bash
git add logica/sinais.py tests/test_offline.py
git commit -m "feat: adiciona sinais.valor_para_captura para cobertura determinística de parâmetros contínuos"
```

---

## Task 2: log de diagnóstico em `AmetekMX30`

**Files:**
- Modify: `logica/ametek_orm.py` (`__init__`, `trigger_step`, `trigger_pulse`, `arm`, `arm_transient`, `wait_transient_complete`, `program_capture`, `enable_dc_offset`)
- Test: `tests/test_offline.py` (nova classe `DiagnosticoLogTests`, dentro do padrão já usado por `AmetekTests`)

**Interfaces:**
- Produces: `AmetekMX30(..., diagnostico: bool = False)`; `AmetekMX30._log_diagnostico(ponto: str, **extra) -> None` (privado, mas os testes verificam via `caplog`/mock de `logger.info`).

- [ ] **Step 1: Write the failing test**

Adicionar em `tests/test_offline.py`:

```python
class DiagnosticoLogTests(unittest.TestCase):
    def test_sem_diagnostico_nao_loga(self):
        fonte = mestre.AmetekMX30(simulated=True, diagnostico=False)
        with self.assertLogs("ametek_orm", level="INFO") as captura:
            fonte._log_diagnostico("ponto_teste")
            # nenhuma chamada real acontece; força um log de controle pra
            # assertLogs não estourar por falta de QUALQUER log capturado
            logging.getLogger("ametek_orm").info("controle")
        self.assertEqual(len(captura.records), 1)
        self.assertIn("controle", captura.records[0].getMessage())

    def test_com_diagnostico_loga_ponto_e_timestamp(self):
        fonte = mestre.AmetekMX30(simulated=True, diagnostico=True)
        with self.assertLogs("ametek_orm", level="INFO") as captura:
            fonte._log_diagnostico("ponto_teste", extra_info=42)
        linhas = [registro.getMessage() for registro in captura.records]
        self.assertTrue(any("ponto_teste" in linha for linha in linhas))
        self.assertTrue(any("extra_info" in linha for linha in linhas))

    def test_trigger_step_com_diagnostico_nao_muda_writes_enviados(self):
        sem_log = mestre.AmetekMX30(simulated=True, diagnostico=False)
        sem_log.trigger_step(100.0)
        com_log = mestre.AmetekMX30(simulated=True, diagnostico=True)
        com_log.trigger_step(100.0)
        self.assertEqual(sem_log.command_log, com_log.command_log)
```

Precisa de `import logging` no topo de `tests/test_offline.py` (novo import).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_offline.py -k DiagnosticoLog -v`
Expected: FAIL com `TypeError: __init__() got an unexpected keyword argument 'diagnostico'`

- [ ] **Step 3: Implement**

Em `logica/ametek_orm.py`, no `__init__` de `AmetekMX30` (linhas 71-145): adicionar o parâmetro `diagnostico: bool = False` na assinatura (junto dos outros flags como `simulated`) e `self.diagnostico = diagnostico` no corpo, perto de `self.simulated = simulated`.

Adicionar o helper logo depois de `assert_no_errors` (linha ~403):

```python
    def _log_diagnostico(self, ponto: str, **extra) -> None:
        """Log opt-in (``diagnostico=True``) para confirmar/refutar as
        hipóteses do CHANGELOG/v1.7.md sem mudar nenhum comando SCPI que já
        existe — só lê estado (``query``) e escreve no logger. Cada chamada
        tolera falha de leitura individualmente: um ``STATus:OPERation:
        CONDition?`` sem resposta não pode fazer a captura inteira abortar."""
        if not self.diagnostico:
            return
        timestamp = time.monotonic()
        transiente_ativo = None
        saida = None
        tensao_v = None
        try:
            operacao = int(float(self.query("STATus:OPERation:CONDition?")))
            transiente_ativo = bool(operacao & 0x8)  # bit 3 = TRANS (manual AMETEK, Tabela 7-1/pg. 169)
        except (CommunicationError, ValueError):
            pass
        try:
            saida = self.query("OUTPut:STATe?").strip()
        except CommunicationError:
            pass
        try:
            tensao_v = self.measure_voltage()
        except (CommunicationError, InstrumentHardwareError):
            pass
        logger.info(
            "[DIAGNOSTICO] ponto=%s t=%.6f transiente_ativo=%s output=%s tensao_v=%s extra=%s",
            ponto, timestamp, transiente_ativo, saida, tensao_v, extra,
        )
```

Pontos de chamada (todos ANTES ou DEPOIS de um write/query que já existe — nunca entre dois writes que precisam ficar adjacentes):

`trigger_step()` (linha ~492-511) — depois do último write, antes do `return` implícito:
```python
        self.write(f"VOLTage:TRIGgered {voltage_rms:.8g}")
        if self.diagnostico:
            self._log_diagnostico("fim_trigger_step", erros=self.check_errors())
```

`trigger_pulse()` (linha ~513-530) — mesma ideia, depois do `PULSe:WIDTh`:
```python
        self.write(f"PULSe:WIDTh {width_s:.8g}")
        if self.diagnostico:
            self._log_diagnostico("fim_trigger_pulse", erros=self.check_errors())
```

`arm()` (linha ~1107-1160) — dois pontos nas linhas já comentadas sobre `*WAI`:
```python
        self._log_diagnostico("arm_antes_wai")
        self.write("*WAI")
        self.write("INITiate:IMMediate")
        self.assert_no_errors("comando INITiate:IMMediate")
        self._log_diagnostico("arm_apos_init")
```
(`_log_diagnostico` já é no-op quando `diagnostico=False` — não precisa do `if self.diagnostico:` de novo aqui, mas mantenha o padrão dos outros pontos por clareza de leitura caso prefira; funcionalmente idêntico.)

`arm_transient()` (linha ~1162-1245) — mesmo par, nomes `arm_transient_antes_wai`/`arm_transient_apos_init`, nos dois pontos equivalentes (antes do `self.write("*WAI")` e depois do `self.assert_no_errors(...)` de armamento).

`wait_transient_complete()` (linha ~1253-1263) — no momento exato em que `IDLE` é detectado:
```python
            if state.startswith("IDLE"):
                self.assert_no_errors("execução do transiente")
                self._log_diagnostico("transiente_concluido")
                return
```

`program_capture()` (linha ~899-1105) — dentro do segundo loop de comandos (o que inclui `"VOLTage:MODE LIST"`), depois do `check_errors()` daquele comando específico:
```python
        for command in (
            f"SOURce:LIST:REPeat {repeats}",
            "SOURce:LIST:COUNt 1",
            "SOURce:LIST:STEP AUTO",
            "FUNCtion:MODE LIST",
            "VOLTage:MODE LIST",
            "TRIGger:SOURce BUS",
            "TRIGger:SYNChronize:SOURce PHASe",
            "TRIGger:SYNChronize:PHASe 0",
            "OUTPut:TTLTrg:MODE TRIG",
            "OUTPut:TTLTrg:SOURce BOT",
            "OUTPut:TTLTrg ON",
        ):
            self.write(command)
            errors = self.check_errors()
            if errors:
                raise InstrumentHardwareError(
                    f"AMETEK rejeitou {command!r} durante programação da lista: {errors}"
                )
            if command == "VOLTage:MODE LIST":
                self._log_diagnostico("apos_voltage_mode_list")
```

`enable_dc_offset()` (linha ~665-693) — antes/depois da troca de modo:
```python
        self._log_diagnostico("antes_sourcemode_acdc")
        self.write("SOURce:MODE ACDC")
        self.write("*WAI")
        self.assert_no_errors("configuração ACDC (SOURce:MODE ACDC)")
        self._log_diagnostico("apos_sourcemode_acdc")
        self._modo_saida = "ACDC"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_offline.py -k "DiagnosticoLog" -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Run the full offline suite to confirm no regression**

Run: `python -m pytest tests/test_offline.py -v`
Expected: todos os testes existentes (35) continuam passando — `diagnostico=False` é o default em todo construtor existente, então nenhum `command_log` muda.

- [ ] **Step 6: Commit**

```bash
git add logica/ametek_orm.py tests/test_offline.py
git commit -m "feat: log de diagnóstico opt-in em AmetekMX30 para testar hipóteses de race condition do v1.7"
```

---

## Task 3: `Config`, globais de sessão e `total_niveis()`

**Files:**
- Modify: `logica/mestre.py` (`Config`, módulo-nível perto de `OUTPUT_ARMED`, `_build_config()`, `Bancada.from_env()`, `ExperimentoBase`)
- Modify: `experimentos_nativos/05.py` (override de `total_niveis`)
- Test: `tests/test_offline.py`

**Interfaces:**
- Produces: `Config.capturas_override: Optional[int]`, `Config.margin_mode: bool`, `Config.diagnostico_mode: bool`; `Config.capturas(simulated)` passa a checar `capturas_override` primeiro; `mestre.SESSION_RESULTS_DIR`, `mestre.CAPTURAS_OVERRIDE`, `mestre.MARGIN_MODE`, `mestre.DIAGNOSTICO_MODE` (globais mutáveis, default `None`/`False`); `ExperimentoBase.total_niveis() -> int`.
- Consumes: `sinais.valor_para_captura` (Task 1, não usado ainda nesta task), `AmetekMX30(..., diagnostico=...)` (Task 2).

- [ ] **Step 1: Write the failing tests**

```python
class ConfigCoberturaTests(unittest.TestCase):
    def _config(self, **overrides):
        base = dict(
            fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(30.0,), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=Path("."),
            sim_captures_per_class=2, real_captures_per_class=1, disturbance_start_s=0.06,
        )
        base.update(overrides)
        return mestre.Config(**base)

    def test_capturas_override_ausente_mantem_real_captures_per_class(self):
        config = self._config()
        self.assertEqual(config.capturas(simulated=False), 1)

    def test_capturas_override_presente_vence_real_captures_per_class(self):
        config = self._config(capturas_override=5)
        self.assertEqual(config.capturas(simulated=False), 5)

    def test_capturas_override_nao_afeta_modo_simulado(self):
        config = self._config(capturas_override=5)
        self.assertEqual(config.capturas(simulated=True), 2)

    def test_defaults_reproduzem_config_de_hoje(self):
        config = self._config()
        self.assertIsNone(config.capturas_override)
        self.assertFalse(config.margin_mode)
        self.assertFalse(config.diagnostico_mode)


class TotalNiveisTests(unittest.TestCase):
    def test_classe_sem_niveis_retorna_1(self):
        experimento = _BancadaFake.experimento_sem_niveis()
        self.assertEqual(experimento.total_niveis(), 1)

    def test_classe_com_niveis_retorna_o_tamanho_da_tupla(self):
        experimento = _BancadaFake.experimento_com_niveis()
        self.assertEqual(experimento.total_niveis(), 5)
```

`_BancadaFake` (já existe no topo do arquivo, linha ~28) precisa de dois métodos auxiliares novos — adicionar dentro dela:

```python
    @staticmethod
    def experimento_sem_niveis():
        class _SemNiveis(mestre.ExperimentoWaveform):
            id = "99"
            nome = "SEM_NIVEIS"
            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}
        return _SemNiveis(_BancadaFake())

    @staticmethod
    def experimento_com_niveis():
        class _ComNiveis(mestre.ExperimentoNativo):
            id = "98"
            nome = "COM_NIVEIS"
            NIVEIS = (0.1, 0.3, 0.5, 0.7, 0.9)
            def gerar(self, t, f0, capture_index, rng):
                return np.sin(2.0 * np.pi * f0 * t), {}
            def configurar(self, capture_index):
                return {}
        return _ComNiveis(_BancadaFake())
```

(Ler a `_BancadaFake` existente primeiro — linha ~28-57 — para confirmar que `_BancadaFake()` já expõe `.config`/`.fonte`/`.osc` suficiente para instanciar um `ExperimentoBase`; se o construtor de `_BancadaFake` exigir argumentos, ajuste as duas chamadas acima de acordo com a assinatura real.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_offline.py -k "ConfigCobertura or TotalNiveis" -v`
Expected: FAIL — `Config.__init__() got an unexpected keyword argument 'capturas_override'` e `AttributeError: 'ExperimentoBase' object has no attribute 'total_niveis'`.

- [ ] **Step 3: Implement**

`Config` (linha 160-179) — adicionar 3 campos no FINAL (depois de `disturbance_start_s`, dataclass exige defaults só depois dos campos obrigatórios) e atualizar `capturas()`:

```python
    disturbance_start_s: float
    capturas_override: Optional[int] = None
    margin_mode: bool = False
    diagnostico_mode: bool = False

    def capturas(self, simulated: bool) -> int:
        if simulated:
            return self.sim_captures_per_class
        if self.capturas_override is not None:
            return self.capturas_override
        return self.real_captures_per_class
```

Perto de `OUTPUT_ARMED` (procurar `OUTPUT_ARMED = env_bool(...)`), adicionar os 4 globais de sessão:

```python
# Estado de sessão da CLI interativa — mutável em runtime (mesmo idioma de
# OUTPUT_ARMED/autorizar_saida()): None/False reproduzem o comportamento de
# hoje sem nenhuma mudança. cli.py é quem escreve nesses globais; qualquer
# outro consumidor (testes, scripts) nunca precisa tocá-los.
SESSION_RESULTS_DIR: Optional[Path] = None
CAPTURAS_OVERRIDE: Optional[int] = None
MARGIN_MODE: bool = False
DIAGNOSTICO_MODE: bool = False
```

`_build_config()` (linha 196-211) — passar os 3 campos novos e usar `SESSION_RESULTS_DIR`:

```python
def _build_config() -> Config:
    return Config(
        fs_hz=FS_HZ,
        points=POINTS,
        duration_s=DURATION_S,
        grid_frequency_hz=GRID_FREQUENCY_HZ,
        base_voltage_rms=BASE_VOLTAGE_RMS,
        snr_levels_db=SNR_LEVELS_DB,
        base_seed=BASE_SEED,
        capture_current=CAPTURE_CURRENT,
        current_base_a=CURRENT_BASE_A,
        results_dir=SESSION_RESULTS_DIR or RESULTS_DIR,
        sim_captures_per_class=SIM_CAPTURES_PER_CLASS,
        real_captures_per_class=REAL_CAPTURES_PER_CLASS,
        disturbance_start_s=DISTURBANCE_START_S,
        capturas_override=CAPTURAS_OVERRIDE,
        margin_mode=MARGIN_MODE,
        diagnostico_mode=DIAGNOSTICO_MODE,
    )
```

`Bancada.from_env()` (linha 279+) — passar `diagnostico=DIAGNOSTICO_MODE` nos dois construtores de `AmetekMX30`:

```python
        if SIMULATED_MODE:
            logger.warning("MODO SIMULADO: nenhum instrumento será aberto")
            return cls(AmetekMX30(simulated=True, diagnostico=DIAGNOSTICO_MODE), None, config)

        validate_bench_configuration(require_output=require_output)
        fonte: Optional[AmetekMX30] = None
        osc = None
        try:
            fonte = AmetekMX30(
                AMETEK_PORT,
                baudrate=AMETEK_BAUDRATE,
                timeout_s=AMETEK_TIMEOUT_S,
                query_eot=AMETEK_QUERY_EOT,
                expected_model=AMETEK_EXPECTED_MODEL,
                clear_user_waveforms=AMETEK_CLEAR_USER_WAVEFORMS,
                max_voltage_rms=EUT_MAX_VOLTAGE_RMS,
                max_peak_v=EUT_MAX_PEAK_V,
                max_current_a=CURRENT_LIMIT_A,
                diagnostico=DIAGNOSTICO_MODE,
            )
```

`ExperimentoBase` (linha 573-797) — adicionar `total_niveis()` como método público, perto de `gerar()`:

```python
    def total_niveis(self) -> int:
        """Quantos valores discretos de parâmetro esta classe tem (ex.:
        5 para SAG/SWELL/HARMONICS via ``NIVEIS``). ``1`` (padrão) para
        classes de parâmetro contínuo ou sem parâmetro nenhum — usado por
        ``executar()`` para decidir se agrupa capturas por nível quando
        ``set capturas N`` está ativo (ver Task 4)."""
        niveis = getattr(self, "NIVEIS", None)
        return len(niveis) if niveis is not None else 1
```

`experimentos_nativos/05.py` — `NIVEIS_THD` é uma constante de MÓDULO, não um atributo de classe, então o default acima não a enxerga. Adicionar dentro da classe `Experimento` (depois de `nome = "HARMONICS"`):

```python
    def total_niveis(self) -> int:
        return len(NIVEIS_THD)
```

(Único ponto de contato com 05.py neste plano inteiro — 1 método, nenhuma mudança na lógica de `gerar()`/`configurar()`/`usar_trace()`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_offline.py -k "ConfigCobertura or TotalNiveis" -v`
Expected: PASS

- [ ] **Step 5: Run the full offline suite**

Run: `python -m pytest tests/test_offline.py -v`
Expected: 35+ testes existentes continuam passando (globais novos default para `None`/`False`, `_build_config()` produz exatamente o `Config` de antes quando ninguém chamou `set`).

- [ ] **Step 6: Commit**

```bash
git add logica/mestre.py experimentos_nativos/05.py tests/test_offline.py
git commit -m "feat: Config/globais de sessão para cobertura de capturas, margem e diagnóstico (tudo opt-in)"
```

---

## Task 4: remapeamento de índice por nível em `executar()`

**Files:**
- Modify: `logica/mestre.py` (`ExperimentoBase.executar()`)
- Test: `tests/test_offline.py`

**Interfaces:**
- Consumes: `Config.capturas_override`/`capturas()` (Task 3), `ExperimentoBase.total_niveis()` (Task 3).
- Produces: `executar()` passa a gravar, na lista de metadados de cada captura real, um campo extra `"nivel_indice"` (`int`, sempre presente; `0` para classes sem `NIVEIS`) usado pela Task 5 para nomear arquivos.

- [ ] **Step 1: Write the failing test**

```python
class RemapeamentoNivelTests(unittest.TestCase):
    def _config(self, results_dir, **overrides):
        base = dict(
            fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=results_dir,
            sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
        )
        base.update(overrides)
        return mestre.Config(**base)

    def test_sem_capturas_override_roda_so_1_capturas_nivel_0(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados")
            bancada = mestre.Bancada(mestre.AmetekMX30(simulated=True), mock.Mock(), config)
            niveis_vistos = []

            class _ComNiveis(mestre.ExperimentoNativo):
                id = "97"
                nome = "TESTE_NIVEIS"
                NIVEIS = (0.1, 0.3, 0.5, 0.7, 0.9)
                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {"nivel": self.NIVEIS[capture_index % 5]}
                def configurar(self, capture_index):
                    niveis_vistos.append(self.NIVEIS[capture_index % 5])
                    return {"nivel": self.NIVEIS[capture_index % 5]}

            experimento = _ComNiveis(bancada)
            experimento.osc = mock.Mock()  # simulated=False via osc não-None
            self._forcar_captura_real_stub(experimento)
            experimento.executar()

            self.assertEqual(niveis_vistos, [0.1])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_com_capturas_override_3_agrupa_3_por_nivel(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = self._config(tmp_dir / "resultados", capturas_override=3)
            bancada = mestre.Bancada(mestre.AmetekMX30(simulated=True), mock.Mock(), config)
            niveis_vistos = []

            class _ComNiveis(mestre.ExperimentoNativo):
                id = "97"
                nome = "TESTE_NIVEIS"
                NIVEIS = (0.1, 0.3, 0.5, 0.7, 0.9)
                def gerar(self, t, f0, capture_index, rng):
                    return np.sin(2.0 * np.pi * f0 * t), {"nivel": self.NIVEIS[capture_index % 5]}
                def configurar(self, capture_index):
                    niveis_vistos.append(self.NIVEIS[capture_index % 5])
                    return {"nivel": self.NIVEIS[capture_index % 5]}

            experimento = _ComNiveis(bancada)
            experimento.osc = mock.Mock()
            self._forcar_captura_real_stub(experimento)
            experimento.executar()

            self.assertEqual(
                niveis_vistos,
                [0.1, 0.1, 0.1, 0.3, 0.3, 0.3, 0.5, 0.5, 0.5, 0.7, 0.7, 0.7, 0.9, 0.9, 0.9],
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @staticmethod
    def _forcar_captura_real_stub(experimento):
        """Substitui _capturar_real por um stub que devolve uma captura
        válida sem tocar osciloscópio/fonte de verdade — só precisamos
        observar QUAL capture_index cada chamada recebeu."""
        pontos = experimento.config.points
        tempo_s = np.arange(pontos, dtype=np.float64) / experimento.config.fs_hz
        def _stub(capture_index, t, rng):
            parametros = experimento.configurar(capture_index)
            return tempo_s, np.sin(2.0 * np.pi * 60.0 * tempo_s), None, parametros
        experimento._capturar_real = _stub
        experimento._preparar_acquisicao_real = lambda: None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_offline.py -k RemapeamentoNivel -v`
Expected: FAIL — o segundo teste em particular vai mostrar 1 captura em vez de 15 (comportamento de hoje: `total = config.capturas(False) = 3`, sem nenhuma noção de nível).

- [ ] **Step 3: Implement**

Em `ExperimentoBase.executar()` (linha 704-797), localizar o trecho:

```python
        simulated = self.osc is None
        total = self.config.capturas(simulated)
```

e substituir por:

```python
        simulated = self.osc is None
        niveis_count = self.total_niveis()
        cobertura_por_nivel_ativa = (
            not simulated and self.config.capturas_override is not None and niveis_count > 1
        )
        if cobertura_por_nivel_ativa:
            capturas_por_nivel = self.config.capturas(False)
            total = niveis_count * capturas_por_nivel
        else:
            total = self.config.capturas(simulated)
```

E localizar o laço `for capture_index in range(total):` — dentro dele, ANTES da linha `seed = self.config.base_seed + int(self.id) * 1_000_000 + capture_index`, inserir:

```python
        for indice_global in range(total):
            if cobertura_por_nivel_ativa:
                capture_index = indice_global // capturas_por_nivel  # nivel, agrupado
            else:
                capture_index = indice_global
            seed = self.config.base_seed + int(self.id) * 1_000_000 + indice_global
```

Trocar TODAS as demais ocorrências de `capture_index` dentro do corpo do laço que hoje servem para **identificar unicamente a captura** (não para indexar nível/parâmetro) por `indice_global`:
- `capture_id = f"{self.id}-{capture_index + 1:04d}"` → `capture_id = f"{self.id}-{indice_global + 1:04d}"`
- `ids.append(capture_id)`, `tensao_limpa[capture_index] = ...`, `tensao_por_snr[snr_db][capture_index] = ...`, `corrente[capture_index] = ...` → todos usam `indice_global` como índice de posição no array (não `capture_index`).
- As chamadas `self.gerar(t, self.config.grid_frequency_hz, capture_index, rng)` e `self._capturar_real(capture_index, t, rng)` continuam usando `capture_index` (o valor remapeado) — é exatamente o que faz `NIVEIS[capture_index % len(NIVEIS)]` resolver pro nível certo sem tocar em 02.py/03.py/05.py.
- Nos `metadados.append({...})`, adicionar o campo novo `"nivel_indice": capture_index if cobertura_por_nivel_ativa else 0` (usado pela Task 5 para nomear arquivo) e usar `indice_global` em `"id_captura": capture_id`.

O array de pré-alocação `tensao_limpa = np.empty((total, self.config.points), ...)` já usa a variável `total` recém-recalculada — nenhuma mudança adicional necessária ali.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_offline.py -k RemapeamentoNivel -v`
Expected: PASS

- [ ] **Step 5: Run the full offline suite**

Run: `python -m pytest tests/test_offline.py -v`
Expected: sem regressão — `capturas_override` é `None` em todo `Config` construído fora desta task, então `cobertura_por_nivel_ativa` é sempre `False` e `capture_index == indice_global` sempre, reproduzindo o comportamento anterior exatamente.

- [ ] **Step 6: Commit**

```bash
git add logica/mestre.py tests/test_offline.py
git commit -m "feat: agrupa capturas por nível em executar() quando set capturas está ativo, sem tocar 02/03.py"
```

---

## Task 5: um `.npz` por captura em `_salvar_classe()`

**Files:**
- Modify: `logica/mestre.py` (`ExperimentoBase._salvar_classe`, `ResultadoClasse.arquivo_esperado`)
- Test: `tests/test_offline.py`

**Interfaces:**
- Consumes: `metadados[i]["nivel_indice"]` e `metadados[i]["parametros"]` (Task 4).
- Produces: `_salvar_classe()` grava `N` arquivos `.npz` (um por captura) em vez de 1 empilhado; `ResultadoClasse.arquivo_esperado` vira `ResultadoClasse.pasta_esperada -> Path` (o diretório da classe, já que não há mais UM arquivo por classe).

- [ ] **Step 1: Write the failing test**

```python
class SalvarClasseArquivoUnicoTests(unittest.TestCase):
    def test_grava_um_npz_por_captura_com_nivel_no_nome(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = mestre.Config(
                fs_hz=30_000.0, points=4, duration_s=0.2, grid_frequency_hz=60.0,
                base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
                capture_current=False, current_base_a=None, results_dir=tmp_dir,
                sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
            )
            experimento = mestre.ExperimentoWaveform.__new__(mestre.ExperimentoWaveform)
            experimento.id = "02"
            experimento.nome = "SAG"
            experimento.config = config
            tensao = np.zeros((2, 4))
            experimento._salvar_classe(
                tempo_ms=np.zeros(4),
                tensao_limpa=tensao,
                tensao_por_snr={},
                ids=["02-0001", "02-0002"],
                corrente=None,
                metadados=[
                    {"id_captura": "02-0001", "classe": "SAG", "nivel_indice": 0,
                     "parametros": {"sag_pu": 0.1}, "seed": 1, "simulado": False,
                     "fs_hz": 30000.0, "pontos": 4, "snr_medido_db": {}},
                    {"id_captura": "02-0002", "classe": "SAG", "nivel_indice": 1,
                     "parametros": {"sag_pu": 0.3}, "seed": 2, "simulado": False,
                     "fs_hz": 30000.0, "pontos": 4, "snr_medido_db": {}},
                ],
            )
            arquivos = sorted(p.name for p in tmp_dir.glob("02_sag*.npz"))
            self.assertEqual(arquivos, ["02_sag_sag_pu-0.1.npz", "02_sag_sag_pu-0.3.npz"])
            self.assertTrue((tmp_dir / "metadata" / "02_sag.jsonl").exists())
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_classe_sem_parametro_nomeavel_usa_capNN(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            config = mestre.Config(
                fs_hz=30_000.0, points=4, duration_s=0.2, grid_frequency_hz=60.0,
                base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
                capture_current=False, current_base_a=None, results_dir=tmp_dir,
                sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
            )
            experimento = mestre.ExperimentoWaveform.__new__(mestre.ExperimentoWaveform)
            experimento.id = "01"
            experimento.nome = "NORMAL"
            experimento.config = config
            experimento._salvar_classe(
                tempo_ms=np.zeros(4), tensao_limpa=np.zeros((1, 4)), tensao_por_snr={},
                ids=["01-0001"], corrente=None,
                metadados=[{"id_captura": "01-0001", "classe": "NORMAL", "nivel_indice": 0,
                            "parametros": {}, "seed": 1, "simulado": False,
                            "fs_hz": 30000.0, "pontos": 4, "snr_medido_db": {}}],
            )
            self.assertTrue((tmp_dir / "01_normal_cap01.npz").exists())
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_offline.py -k SalvarClasseArquivoUnico -v`
Expected: FAIL — hoje `_salvar_classe` grava `02_sag.npz` (um arquivo, `tensao_pu.shape=(2,4)`), não os dois arquivos esperados.

- [ ] **Step 3: Implement**

Substituir o corpo de `_salvar_classe()` (linha 640-702). Nova versão:

```python
    def _salvar_classe(
        self,
        *,
        tempo_ms: np.ndarray,
        tensao_limpa: np.ndarray,
        tensao_por_snr: Dict[float, np.ndarray],
        ids: List[str],
        corrente: Optional[np.ndarray],
        metadados: List[dict],
    ) -> None:
        """Grava um ``.npz`` POR CAPTURA (não mais um único arquivo por
        classe com todas as capturas empilhadas) — necessário desde que
        ``set capturas N`` pode gerar N capturas por nível, cada uma uma
        condição física distinta que merece arquivo próprio. O nome carrega
        o parâmetro físico da captura quando existe algum em ``parametros``
        (ex.: ``sag_pu-0.1``); cai para ``capNN`` (posição, 1-based) quando
        não há parâmetro nomeável. Continua atômico (``.part`` -> replace),
        agora por arquivo individual; metadata continua 1 arquivo por
        classe, 1 linha por captura."""
        config = self.config
        config.results_dir.mkdir(parents=True, exist_ok=True)

        def _rotulo(indice: int, parametros: dict) -> str:
            if parametros:
                chave, valor = next(iter(parametros.items()))
                valor_fmt = f"{valor:g}" if isinstance(valor, float) else str(valor)
                return f"{chave}-{valor_fmt}"
            return f"cap{indice + 1:02d}"

        for indice, (metadado_captura,) in enumerate(zip(metadados)):
            rotulo = _rotulo(indice, metadado_captura["parametros"])
            nome_base = f"{self.id}_{self.nome.lower()}_{rotulo}.npz"

            final_path = config.results_dir / nome_base
            partial_path = final_path.with_suffix(".npz.part")
            with partial_path.open("wb") as handle:
                np.savez(
                    handle, tempo_ms=tempo_ms, tensao_pu=tensao_limpa[indice : indice + 1],
                    classe=self.nome, id_captura=np.array([ids[indice]], dtype=object),
                )
            os.replace(partial_path, final_path)

            for snr_db, tensao in tensao_por_snr.items():
                rotulo_snr = str(int(snr_db)) if float(snr_db).is_integer() else str(snr_db).replace(".", "_")
                directory = config.results_dir / f"snr_{rotulo_snr}db"
                directory.mkdir(parents=True, exist_ok=True)
                final_path = directory / nome_base
                partial_path = final_path.with_suffix(".npz.part")
                with partial_path.open("wb") as handle:
                    np.savez(
                        handle, tempo_ms=tempo_ms, tensao_pu=tensao[indice : indice + 1],
                        classe=self.nome, id_captura=np.array([ids[indice]], dtype=object),
                    )
                os.replace(partial_path, final_path)

            if corrente is not None:
                directory = config.results_dir / "corrente"
                directory.mkdir(parents=True, exist_ok=True)
                nome_corrente = f"{self.id}_{self.nome.lower()}_{rotulo}_corrente.npz"
                final_path = directory / nome_corrente
                partial_path = final_path.with_suffix(".npz.part")
                with partial_path.open("wb") as handle:
                    np.savez(
                        handle, tempo_ms=tempo_ms, corrente_pu=corrente[indice : indice + 1],
                        classe=self.nome, id_captura=np.array([ids[indice]], dtype=object),
                    )
                os.replace(partial_path, final_path)

        metadata_dir = config.results_dir / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        metadata_final = metadata_dir / f"{self.id}_{self.nome.lower()}.jsonl"
        metadata_partial = metadata_final.with_suffix(".jsonl.part")
        with metadata_partial.open("w", encoding="utf-8") as handle:
            for registro in metadados:
                handle.write(json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(metadata_partial, metadata_final)
```

(O `enumerate(zip(metadados))` acima é só uma forma segura de iterar `indice, metadado_captura` sem depender de `len(ids)==len(metadados)==tensao_limpa.shape[0]` implicitamente — pode simplificar para `for indice, metadado_captura in enumerate(metadados):` diretamente, é equivalente e mais direto; ajuste ao implementar.)

`ResultadoClasse.arquivo_esperado` (linha 191-193) — não existe mais UM arquivo por classe; trocar por `pasta_esperada`:

```python
    @property
    def pasta_esperada(self) -> Path:
        return (mestre.SESSION_RESULTS_DIR or RESULTS_DIR)
```

Atualizar `logica/cli.py` nos dois lugares que hoje imprimem `resultado.arquivo_esperado` (`_run_uma`, `_run_all` — ver Task 7) para `resultado.pasta_esperada`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_offline.py -k SalvarClasseArquivoUnico -v`
Expected: PASS

- [ ] **Step 5: Run the full offline suite**

Run: `python -m pytest tests/test_offline.py -v`
Expected: os testes existentes que checam `(results_dir / "01_ok.npz").exists()` (ver `BateriaResilienciaTests`, linha 733) continuam passando — com 1 captura sem parâmetro nomeável, o nome vira `01_ok_cap01.npz`. **Atenção:** isso quebra a asserção literal `self.assertTrue((results_dir / "01_ok.npz").exists())` em `test_falha_de_uma_classe_nao_aborta_a_bateria` — atualizar essa linha para `(results_dir / "01_ok_cap01.npz").exists()` como parte deste mesmo commit (é uma consequência direta e esperada desta task, não uma regressão escondida).

- [ ] **Step 6: Commit**

```bash
git add logica/mestre.py logica/cli.py tests/test_offline.py
git commit -m "feat: _salvar_classe grava um .npz por captura em vez de empilhar num único arquivo por classe"
```

---

## Task 6: classes de parâmetro contínuo usam `valor_para_captura`

**Files:**
- Modify: `experimentos_nativos/04.py`, `experimentos_nativos/19.py`, `experimentos_waveform/06.py`, `experimentos_waveform/08.py`, `experimentos_waveform/09.py`
- Test: `tests/test_offline.py`

**Interfaces:**
- Consumes: `sinais.valor_para_captura` (Task 1), `Config.capturas_override`/`capturas()` (Task 3).

- [ ] **Step 1: Write the failing tests**

```python
class CoberturaParametroContinuoTests(unittest.TestCase):
    def _carregar(self, relative_path):
        script_path = PROJECT_ROOT / relative_path
        spec = importlib.util.spec_from_file_location("teste_cobertura", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(script_path.parent))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.remove(str(script_path.parent))
        return module.Experimento

    def _config(self, capturas_override=None):
        return mestre.Config(
            fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=Path("."),
            sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
            capturas_override=capturas_override,
        )

    def test_04_interruption_sem_override_sorteia(self):
        cls = self._carregar("experimentos_nativos/04.py")
        instancia = cls.__new__(cls)
        instancia.config = self._config(capturas_override=None)
        instancia.osc = mock.Mock()  # not simulated
        t = np.arange(6000) / 30000.0
        _, parametros_a = instancia.gerar(t, 60.0, 0, np.random.default_rng(1))
        _, parametros_b = instancia.gerar(t, 60.0, 0, np.random.default_rng(2))
        self.assertNotEqual(parametros_a["interruption_pu"], parametros_b["interruption_pu"])

    def test_04_interruption_com_override_cobre_intervalo(self):
        cls = self._carregar("experimentos_nativos/04.py")
        instancia = cls.__new__(cls)
        instancia.config = self._config(capturas_override=3)
        instancia.osc = mock.Mock()
        t = np.arange(6000) / 30000.0
        niveis = [
            instancia.gerar(t, 60.0, indice, np.random.default_rng(indice))[1]["interruption_pu"]
            for indice in range(3)
        ]
        self.assertAlmostEqual(niveis[0], 0.0)
        self.assertAlmostEqual(niveis[-1], 0.09)

    def test_04_interruption_simulado_ignora_override(self):
        cls = self._carregar("experimentos_nativos/04.py")
        instancia = cls.__new__(cls)
        instancia.config = self._config(capturas_override=3)
        instancia.osc = None  # simulado
        t = np.arange(6000) / 30000.0
        primeiro = instancia.gerar(t, 60.0, 0, np.random.default_rng(1))[1]["interruption_pu"]
        segundo = instancia.gerar(t, 60.0, 0, np.random.default_rng(7))[1]["interruption_pu"]
        self.assertNotEqual(primeiro, segundo)  # continua sorteio, override não se aplica

    def test_08_transient_com_override_usa_pico_fisico_nao_a_spec(self):
        cls = self._carregar("experimentos_waveform/08.py")
        instancia = cls.__new__(cls)
        instancia.config = self._config(capturas_override=3)
        instancia.osc = mock.Mock()
        instancia.fonte = mestre.AmetekMX30(simulated=True)
        instancia.fonte.max_peak_v = 200.0  # limite_pico_bancada_pu() = 0.9*200/(127*sqrt2) ~ 0.79
        t = np.arange(6000) / 30000.0
        amplitudes = [
            instancia.gerar(t, 60.0, indice, np.random.default_rng(indice))[1]["transient_amplitude_pu"]
            for indice in range(3)
        ]
        limite_pico_pu = instancia.limite_pico_bancada_pu()
        self.assertAlmostEqual(amplitudes[0], 1.2 - 1.0)
        self.assertAlmostEqual(amplitudes[-1], limite_pico_pu - 1.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_offline.py -k CoberturaParametroContinuo -v`
Expected: FAIL — `04.py`/`08.py` ainda ignoram `capturas_override` e sempre sorteiam.

- [ ] **Step 3: Implement**

`experimentos_nativos/04.py` — trocar `gerar()` e `configurar()`:

```python
    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        simulado = self.osc is None
        total = self.config.capturas(simulado)
        cobertura_ativa = not simulado and self.config.capturas_override is not None
        nivel = sinais.valor_para_captura(rng, 0.0, 0.09, capture_index, total, cobertura_ativa=cobertura_ativa)
        voltage[janela(t, self.INICIO_S, self.DURACAO_S)] *= nivel
        return voltage, {"interruption_pu": nivel}

    def configurar(self, capture_index):
        seed = self.config.base_seed + 4_000_000 + capture_index
        cobertura_ativa = self.config.capturas_override is not None
        total = self.config.capturas(False)
        nivel = sinais.valor_para_captura(
            np.random.default_rng(seed), 0.0, 0.09, capture_index, total, cobertura_ativa=cobertura_ativa,
        )
        self.fonte.trigger_pulse(nivel * self.config.base_voltage_rms, width_s=self.DURACAO_S)
        return {"interruption_pu": nivel}
```

Precisa de `import sinais` no topo de `04.py` (adicionar ao lado de `from mestre import ExperimentoNativo`).

`experimentos_nativos/19.py` — mesmo padrão em `gerar()`; `dc_offset = sinais.valor_para_captura(rng, 0.02, 0.10, capture_index, total, cobertura_ativa=cobertura_ativa)`. Repetir o cálculo de `simulado`/`total`/`cobertura_ativa` igual ao de `04.py`. Em `configurar()` (que reconstrói `seed = self.config.base_seed + 19_000_000 + capture_index`), mesmo tratamento: `total = self.config.capturas(False)`, `cobertura_ativa = self.config.capturas_override is not None`.

`experimentos_waveform/06.py` — só `flicker_hz` ganha cobertura (o parâmetro citado na conversa); `profundidade` continua sorteio sempre (2 eixos contínuos simultâneos não têm cobertura determinística limpa, mesma decisão já tomada para 20/INTERHARMONICS no spec):

```python
    def gerar(self, t, f0, capture_index, rng):
        simulado = self.osc is None
        total = self.config.capturas(simulado)
        cobertura_ativa = not simulado and self.config.capturas_override is not None
        flicker_hz = sinais.valor_para_captura(rng, 8.0, 25.0, capture_index, total, cobertura_ativa=cobertura_ativa)
        profundidade = float(rng.uniform(0.05, 0.15))
        ...
```

`experimentos_waveform/09.py` — `frequencia` ganha cobertura (é o parâmetro citado — "f_osc sortear entre 300 e 2.400 Hz"); `duracao` continua sorteio:

```python
    def gerar(self, t, f0, capture_index, rng):
        voltage = np.sin(2.0 * np.pi * f0 * t)
        simulado = self.osc is None
        total = self.config.capturas(simulado)
        cobertura_ativa = not simulado and self.config.capturas_override is not None
        frequencia = sinais.valor_para_captura(rng, 300.0, 2400.0, capture_index, total, cobertura_ativa=cobertura_ativa)
        duracao = float(rng.uniform(0.010, 0.040))
        ...
```

`experimentos_waveform/08.py` — caso especial (pico físico, não a faixa 5-10pu da spec):

```python
    def gerar(self, t, f0, capture_index, rng):
        fs_hz = 1.0 / (t[1] - t[0])
        voltage = np.sin(2.0 * np.pi * f0 * t)
        simulado = self.osc is None
        total = self.config.capturas(simulado)
        cobertura_ativa = not simulado and self.config.capturas_override is not None
        if cobertura_ativa and total > 1:
            pico_min_pu, pico_max_pu = 1.2, self.limite_pico_bancada_pu()
            pico_alvo_pu = float(np.linspace(pico_min_pu, pico_max_pu, total)[capture_index])
            amplitude = pico_alvo_pu - 1.0
        else:
            amplitude = float(rng.uniform(5.0, 10.0))
        start_index = int(round(0.080 * fs_hz))
        pulse_samples = max(1, int(math.ceil(0.00005 * fs_hz)))
        voltage[start_index : start_index + pulse_samples] += amplitude
        return voltage, {"transient_amplitude_pu": amplitude, "pulse_samples": float(pulse_samples)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_offline.py -k CoberturaParametroContinuo -v`
Expected: PASS

- [ ] **Step 5: Run the full offline suite**

Run: `python -m pytest tests/test_offline.py -v`
Expected: sem regressão (`capturas_override=None` em todo teste pré-existente reproduz o sorteio de sempre).

- [ ] **Step 6: Commit**

```bash
git add experimentos_nativos/04.py experimentos_nativos/19.py experimentos_waveform/06.py experimentos_waveform/08.py experimentos_waveform/09.py tests/test_offline.py
git commit -m "feat: cobertura determinística de parâmetro contínuo em 04/06/08/09/19 quando set capturas está ativo"
```

---

## Task 7: `set margin on|off` — captura com folga, salva bruta

**Files:**
- Modify: `logica/mestre.py` (`ExperimentoBase.executar()`, `_validar_captura()`)
- Test: `tests/test_offline.py`

**Interfaces:**
- Consumes: `Config.margin_mode` (Task 3).
- Produces: quando `margin_mode` e não-simulado, `_capturar_real` é chamado com uma duração/nº de pontos maior; o `.npz` salvo tem mais de `config.points` amostras e o metadata ganha `"margem_amostras_antes"`, `"margem_amostras_depois"`, `"amostras_totais"`.

- [ ] **Step 1: Write the failing test**

```python
class MargemCapturaTests(unittest.TestCase):
    def test_margin_off_mantem_pontos_nominais(self):
        margem_amostras, pontos_totais = mestre.ExperimentoBase._calcular_margem(
            margin_mode=False, config_points=6000, fs_hz=30_000.0,
        )
        self.assertEqual(margem_amostras, 0)
        self.assertEqual(pontos_totais, 6000)

    def test_margin_on_adiciona_amostras_de_cada_lado(self):
        margem_amostras, pontos_totais = mestre.ExperimentoBase._calcular_margem(
            margin_mode=True, config_points=6000, fs_hz=30_000.0,
        )
        self.assertEqual(margem_amostras, 750)  # 25ms * 30kSa/s
        self.assertEqual(pontos_totais, 6000 + 2 * 750)

    def test_validar_captura_aceita_pontos_extras_quando_esperado_explicito(self):
        config = mestre.Config(
            fs_hz=30_000.0, points=6000, duration_s=0.2, grid_frequency_hz=60.0,
            base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
            capture_current=False, current_base_a=None, results_dir=Path("."),
            sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
        )
        experimento = mestre.ExperimentoWaveform.__new__(mestre.ExperimentoWaveform)
        experimento.config = config
        pontos_totais = 7500
        tempo_s = np.arange(pontos_totais) / 30_000.0
        experimento._validar_captura(tempo_s, np.zeros(pontos_totais), pontos_esperados=pontos_totais)  # não levanta
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_offline.py -k MargemCaptura -v`
Expected: FAIL — `_calcular_margem` não existe; `_validar_captura` não aceita `pontos_esperados`.

- [ ] **Step 3: Implement**

`ExperimentoBase._validar_captura` (linha 627-638) — adicionar parâmetro opcional:

```python
    def _validar_captura(
        self, time_s: np.ndarray, voltage_pu: np.ndarray, *, pontos_esperados: Optional[int] = None,
    ) -> None:
        config = self.config
        esperado = pontos_esperados if pontos_esperados is not None else config.points
        if time_s.shape != (esperado,) or voltage_pu.shape != (esperado,):
            raise ValueError(
                f"Captura deve ter {esperado} pontos; recebido {time_s.size}/{voltage_pu.size}"
            )
        if not np.all(np.isfinite(time_s)) or not np.all(np.isfinite(voltage_pu)):
            raise ValueError("Captura contém NaN ou infinito")
        incrementos = np.diff(time_s)
        incremento_esperado = 1.0 / config.fs_hz
        if not np.allclose(incrementos, incremento_esperado, rtol=0, atol=1e-9):
            raise ValueError(f"Eixo temporal não corresponde a {config.fs_hz:.0f} Sa/s")
```

Adicionar staticmethod nova em `ExperimentoBase` (perto de `_validar_captura`):

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

Em `executar()`, logo depois de `simulated = self.osc is None` e antes de `if not simulated: self.osc.configure_acquisition(...)`:

```python
        margem_amostras, pontos_efetivos = self._calcular_margem(
            margin_mode=(not simulated and self.config.margin_mode),
            config_points=self.config.points, fs_hz=self.config.fs_hz,
        )
```

E trocar a chamada de `configure_acquisition` (dentro do `if not simulated:`) para usar `pontos_efetivos`:

```python
        if not simulated:
            duracao_efetiva = pontos_efetivos / self.config.fs_hz
            pre_trigger_efetivo = self.pre_trigger_s + margem_amostras / self.config.fs_hz
            self.osc.configure_acquisition(
                sample_rate_hz=self.config.fs_hz,
                points=pontos_efetivos,
                duration_s=duracao_efetiva,
                pre_trigger_s=pre_trigger_efetivo,
            )
            self._preparar_acquisicao_real()
```

As pré-alocações `tensao_limpa = np.empty((total, self.config.points), ...)` e as de `tensao_por_snr`/`corrente` passam a usar `pontos_efetivos` em vez de `self.config.points` (mesma variável, só troca o segundo argumento da tupla de shape nas 3 ocorrências).

`_ler_captura()` (linha 614-625) — trocar `expected_points=self.config.points` por `expected_points=pontos_efetivos` nas duas chamadas a `self.osc.get_waveform(...)` (canal 1 e canal 2). Como `_ler_captura` é chamado de dentro de `_capturar_real` (definido nas subclasses `ExperimentoNativo`/`ExperimentoWaveform`, não em `ExperimentoBase`), o valor de `pontos_efetivos` precisa estar acessível ali — guardar em `self._pontos_efetivos_captura_atual = pontos_efetivos` logo depois de calculá-lo em `executar()`, e trocar `_ler_captura` para ler `self._pontos_efetivos_captura_atual` em vez de `self.config.points`.

A chamada a `self._validar_captura(time_s, measured_voltage_pu)` dentro do laço de `executar()` passa a `self._validar_captura(time_s, measured_voltage_pu, pontos_esperados=pontos_efetivos)`.

Nos `metadados.append({...})`, adicionar (só quando `margem_amostras > 0`, senão omitir as 3 chaves para não poluir metadata de captura normal):

```python
            if margem_amostras > 0:
                metadados[-1]["margem_amostras_antes"] = margem_amostras
                metadados[-1]["margem_amostras_depois"] = margem_amostras
                metadados[-1]["amostras_totais"] = pontos_efetivos
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_offline.py -k MargemCaptura -v`
Expected: PASS

- [ ] **Step 5: Run the full offline suite**

Run: `python -m pytest tests/test_offline.py -v`
Expected: sem regressão — `margin_mode=False` (default) faz `_calcular_margem` devolver `(0, config.points)`, reproduzindo tudo de antes.

- [ ] **Step 6: Commit**

```bash
git add logica/mestre.py tests/test_offline.py
git commit -m "feat: set margin captura com folga extra antes/depois da janela nominal, salva bruta"
```

---

## Task 8: `cli.py` — `set margin|diagnostico|capturas`, sessão por pasta

**Files:**
- Modify: `logica/cli.py`

**Interfaces:**
- Consumes: `mestre.SESSION_RESULTS_DIR`, `mestre.CAPTURAS_OVERRIDE`, `mestre.MARGIN_MODE`, `mestre.DIAGNOSTICO_MODE` (Task 3); `ResultadoClasse.pasta_esperada` (Task 5).

Esta task não tem TDD automatizado (é um REPL que lê `input()`/escreve `print()` — o mesmo padrão do resto de `cli.py`, que hoje não tem teste próprio; `preflight`/`preflight_new`/`mestre` é que carregam a cobertura). Validação é manual, listada no Step final.

- [ ] **Step 1: Adicionar `cmd_set` e sessão lazy**

Em `logica/cli.py`, no `SessaoCLI.__init__` (linha 68-69):

```python
    def __init__(self) -> None:
        self.ultimo_resultado: dict[str, "mestre.ResultadoClasse"] = {}
        self._sessao_timestamp = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._sessao_criada = False
```

Adicionar `import datetime as _dt` no topo do arquivo (junto dos outros imports).

Novo método privado, perto de `autorizar_saida`:

```python
    def _garantir_pasta_sessao(self) -> None:
        """Cria resultados/sessao_<timestamp>/ na PRIMEIRA gravação da sessão
        (não no boot da CLI) — status/comm/trigger sem run não deixam pasta
        vazia. Todo run subsequente na MESMA sessão de CLI grava na mesma
        pasta (timestamp fixado em __init__)."""
        if self._sessao_criada:
            return
        sessao_dir = mestre.RESULTS_DIR / f"sessao_{self._sessao_timestamp}"
        sessao_dir.mkdir(parents=True, exist_ok=True)
        mestre.SESSION_RESULTS_DIR = sessao_dir
        self._sessao_criada = True
        print(f"Sessão gravando em: {sessao_dir}")
```

Chamar `self._garantir_pasta_sessao()` no início de `_run_uma` e `_run_all`, logo depois da confirmação (`self.confirmar(...)` retornar `True`) e ANTES de `self.autorizar_saida(True)`.

Novo comando:

```python
    def cmd_set(self, args: List[str]) -> int:
        if len(args) < 2:
            print("Uso: set margin on|off   |   set diagnostico on|off   |   set capturas <N>")
            return 1
        chave, valor = args[0].lower(), args[1].lower()
        if chave == "margin":
            if valor not in ("on", "off"):
                print("Uso: set margin on|off")
                return 1
            mestre.MARGIN_MODE = valor == "on"
            print(f"margin: {'ON' if mestre.MARGIN_MODE else 'OFF'}")
            if mestre.MARGIN_MODE and not mestre.BENCH_MODE:
                print("Aviso: margin on só tem efeito em captura FÍSICA (BENCH_MODE=1); sem efeito em modo simulado.")
            return 0
        if chave == "diagnostico":
            if valor not in ("on", "off"):
                print("Uso: set diagnostico on|off")
                return 1
            mestre.DIAGNOSTICO_MODE = valor == "on"
            print(f"diagnostico: {'ON' if mestre.DIAGNOSTICO_MODE else 'OFF'}")
            return 0
        if chave == "capturas":
            try:
                n = int(args[1])
            except ValueError:
                print("Uso: set capturas <N> (inteiro positivo)")
                return 1
            if n < 1:
                print(f"capturas: valor inválido ({n}); mantendo {mestre.CAPTURAS_OVERRIDE or mestre.REAL_CAPTURES_PER_CLASS}")
                return 1
            mestre.CAPTURAS_OVERRIDE = n
            print(f"capturas: {n} por classe (por nível, nas classes que têm níveis discretos)")
            return 0
        print(f"Chave desconhecida: {chave!r}. Use margin, diagnostico ou capturas.")
        return 1
```

Registrar em `COMANDOS` (linha 258-267): adicionar `"set": cmd_set,`.

Atualizar `cmd_status` (linha 110-126) para mostrar os 3 toggles, logo depois da linha de `ARM_OUTPUT`:

```python
        print(
            f"margin: {'ON' if mestre.MARGIN_MODE else 'OFF'}   "
            f"diagnostico: {'ON' if mestre.DIAGNOSTICO_MODE else 'OFF'}   "
            f"capturas: {mestre.CAPTURAS_OVERRIDE or mestre.REAL_CAPTURES_PER_CLASS}"
        )
        if self._sessao_criada:
            print(f"Sessão: {mestre.SESSION_RESULTS_DIR}")
```

Trocar as duas ocorrências de `resultado.arquivo_esperado` (em `_run_uma` e `_run_all`) por `resultado.pasta_esperada` (consequência da Task 5).

Atualizar `HELP_TEXT` (linha 27-64), adicionando antes de `help / ?`:

```
  set margin on|off   Liga/desliga captura com folga extra (~25ms de cada
                       lado) antes/depois da janela nominal — salva o array
                       bruto, sem recorte automático. Só afeta captura real.[OFF]
  set diagnostico on|off
                       Liga/desliga log extra de STATus:OPERation:CONDition?/
                       OUTPut:STATe?/tensão imediata em pontos-chave de
                       run/run all — para testar as hipóteses do v1.7.      [OFF]
  set capturas <N>    Quantas capturas por classe na bancada real (default
                       1). Em classes com níveis discretos (SAG/SWELL/
                       HARMONICS), N por nível.                             [OFF]
```

- [ ] **Step 2: Validação manual (sem hardware, `BENCH_MODE=0`)**

```bash
cd logica
python -c "import cli; s = cli.SessaoCLI(); s.cmd_set(['margin', 'on']); s.cmd_set(['diagnostico', 'on']); s.cmd_set(['capturas', '3']); s.cmd_status([])"
```

Expected: imprime `margin: ON`, `diagnostico: ON`, `capturas: 3 por classe...`, e a linha de `status` reflete os 3 valores. Nenhuma exceção.

- [ ] **Step 3: Commit**

```bash
git add logica/cli.py
git commit -m "feat: comandos 'set margin/diagnostico/capturas' e pasta de sessão lazy na CLI"
```

---

## Task 9: `logica/analisar_sessao.py` (novo, offline)

**Files:**
- Create: `logica/analisar_sessao.py`
- Test: `tests/test_offline.py` (nova classe `AnalisarSessaoTests`)

**Interfaces:**
- Produces: `analisar_offset(expected: np.ndarray, captured: np.ndarray, fs_hz: float) -> Tuple[int, float]` (lag em amostras, correlação no pico — mesma técnica FFT validada manualmente nesta conversa); função `main(argv)` para uso via linha de comando, mesmo padrão de `visualizador.py`.

- [ ] **Step 1: Write the failing test**

```python
class AnalisarSessaoTests(unittest.TestCase):
    def test_analisar_offset_detecta_deslocamento_conhecido(self):
        import analisar_sessao
        fs_hz = 30_000.0
        t = np.arange(6000) / fs_hz
        esperado = np.sin(2.0 * np.pi * 60.0 * t)
        deslocamento_amostras = 599
        capturado = np.roll(esperado, deslocamento_amostras)
        lag, corr = analisar_sessao.analisar_offset(esperado, capturado, fs_hz)
        self.assertEqual(lag, deslocamento_amostras)
        self.assertGreater(corr, 0.9)

    def test_analisar_sessao_gera_relatorio_para_uma_pasta(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            sessao_dir = tmp_dir / "sessao_teste"
            (sessao_dir / "metadata").mkdir(parents=True)
            fs_hz = 30_000.0
            pontos = 6000
            t = np.arange(pontos) / fs_hz
            captura = np.sin(2.0 * np.pi * 60.0 * t)
            np.savez(
                sessao_dir / "01_normal_cap01.npz", tempo_ms=t * 1000.0,
                tensao_pu=captura.reshape(1, -1), classe="NORMAL",
                id_captura=np.array(["01-0001"], dtype=object),
            )
            (sessao_dir / "metadata" / "01_normal.jsonl").write_text(
                json.dumps({"classe": "NORMAL", "fs_hz": fs_hz, "id_captura": "01-0001",
                            "parametros": {}, "pontos": pontos, "seed": 21260827, "simulado": False}) + "\n",
                encoding="utf-8",
            )
            import analisar_sessao
            relatorio = analisar_sessao.analisar_sessao(sessao_dir, gerar_imagens=False)
            self.assertEqual(len(relatorio), 1)
            self.assertEqual(relatorio[0]["classe"], "01_normal_cap01")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_offline.py -k AnalisarSessao -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'analisar_sessao'`

- [ ] **Step 3: Implement**

Criar `logica/analisar_sessao.py`:

```python
"""Análise offline de uma pasta de sessão (``resultados/sessao_*/``): para
cada ``.npz``, reconstrói a forma esperada via ``gerar()`` + ``seed`` do
metadata (mesma técnica usada manualmente na investigação do
CHANGELOG/v1.7.md), mede deslocamento por cross-correlação e razão de pico,
e opcionalmente gera uma imagem lado-a-lado (gerado vs. capturado) por
arquivo. Sem hardware — mesmo padrão de ``visualizador.py``: roda em
qualquer máquina, só precisa dos ``.npz``/``.jsonl`` já gravados.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_DIRS = (PROJECT_ROOT / "experimentos_nativos", PROJECT_ROOT / "experimentos_waveform")


def analisar_offset(expected: np.ndarray, captured: np.ndarray, fs_hz: float) -> Tuple[int, float]:
    """Cross-correlação FFT (sem scipy) entre a forma esperada e a
    capturada. Devolve (lag em amostras, correlação normalizada no pico) —
    lag positivo significa que o conteúdo capturado está ATRASADO em
    relação ao esperado."""
    n = len(expected)
    e = expected - np.mean(expected)
    c = captured - np.mean(captured)
    e = e / (np.linalg.norm(e) + 1e-12)
    c = c / (np.linalg.norm(c) + 1e-12)
    nfft = 1
    while nfft < 2 * n:
        nfft *= 2
    E = np.fft.rfft(e, nfft)
    C = np.fft.rfft(c, nfft)
    corr = np.fft.irfft(np.conj(E) * C, nfft)
    lags = np.concatenate([np.arange(0, n), np.arange(-(nfft - n), 0)])
    order = np.argsort(lags)
    lags_sorted, corr_sorted = lags[order], corr[order]
    mask = (lags_sorted >= -n) & (lags_sorted <= n)
    lags_r, corr_r = lags_sorted[mask], corr_sorted[mask]
    melhor = int(np.argmax(corr_r))
    return int(lags_r[melhor]), float(corr_r[melhor])


def _carregar_experimento_cls(class_id: str):
    for diretorio in EXPERIMENT_DIRS:
        script_path = diretorio / f"{class_id}.py"
        if script_path.exists():
            module_name = f"analise_{diretorio.name}_{class_id}"
            spec = importlib.util.spec_from_file_location(module_name, script_path)
            module = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(diretorio))
            try:
                spec.loader.exec_module(module)
            finally:
                sys.path.remove(str(diretorio))
            return module.Experimento
    raise FileNotFoundError(f"Nenhum script encontrado para a classe {class_id!r}")


def _reconstruir_esperado(class_id: str, metadado: dict) -> np.ndarray:
    cls = _carregar_experimento_cls(class_id)
    instancia = cls.__new__(cls)
    fs_hz = metadado["fs_hz"]
    pontos = metadado["pontos"]
    t = np.arange(pontos, dtype=np.float64) / fs_hz
    rng = np.random.default_rng(metadado["seed"])
    voltage_pu, _ = instancia.gerar(t, 60.0, 0, rng)
    return np.asarray(voltage_pu, dtype=np.float64)


def analisar_sessao(sessao_dir: Path, *, gerar_imagens: bool = True) -> List[Dict]:
    metadata_dir = sessao_dir / "metadata"
    if not metadata_dir.is_dir():
        raise FileNotFoundError(f"{sessao_dir} não parece uma pasta de sessão (sem metadata/)")

    metadados_por_id_captura: Dict[str, dict] = {}
    for jsonl_path in metadata_dir.glob("*.jsonl"):
        for linha in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not linha.strip():
                continue
            registro = json.loads(linha)
            metadados_por_id_captura[registro["id_captura"]] = registro

    relatorio: List[Dict] = []
    imagens_dir = sessao_dir / "analise"
    if gerar_imagens:
        imagens_dir.mkdir(exist_ok=True)

    for npz_path in sorted(sessao_dir.glob("*.npz")):
        stem = npz_path.stem
        dados = np.load(npz_path, allow_pickle=True)
        id_captura = str(dados["id_captura"][0])
        metadado = metadados_por_id_captura.get(id_captura)
        if metadado is None:
            relatorio.append({"classe": stem, "erro": f"sem metadata para id_captura={id_captura!r}"})
            continue
        class_id = id_captura.split("-")[0]
        capturado = dados["tensao_pu"][0]
        amostras_totais = metadado.get("amostras_totais", metadado["pontos"])
        margem_antes = metadado.get("margem_amostras_antes", 0)

        try:
            esperado = _reconstruir_esperado(class_id, metadado)
        except Exception as exc:  # arquivo de classe não encontrado, gerar() mudou de assinatura etc.
            relatorio.append({"classe": stem, "erro": f"falha reconstruindo esperado: {exc}"})
            continue

        if margem_antes:
            # captura em margin mode: recorta a janela nominal do meio do
            # array bruto antes de comparar com o esperado (que sempre tem
            # o tamanho nominal, config.points).
            capturado_para_comparar = capturado[margem_antes : margem_antes + len(esperado)]
        else:
            capturado_para_comparar = capturado[: len(esperado)]

        lag, corr = analisar_offset(esperado, capturado_para_comparar, metadado["fs_hz"])
        pico_esperado = float(np.max(np.abs(esperado)))
        pico_capturado = float(np.max(np.abs(capturado)))
        relatorio.append({
            "classe": stem,
            "lag_amostras": lag,
            "lag_ms": lag / metadado["fs_hz"] * 1000.0,
            "correlacao": corr,
            "pico_esperado": pico_esperado,
            "pico_capturado": pico_capturado,
            "razao_pico": pico_capturado / pico_esperado if pico_esperado else float("nan"),
        })

        if gerar_imagens:
            _salvar_imagem_comparacao(imagens_dir, stem, esperado, capturado, metadado["fs_hz"])

    return relatorio


def _salvar_imagem_comparacao(imagens_dir: Path, stem: str, esperado: np.ndarray, capturado: np.ndarray, fs_hz: float) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t_esperado_ms = np.arange(len(esperado)) / fs_hz * 1000.0
    t_capturado_ms = np.arange(len(capturado)) / fs_hz * 1000.0
    fig, eixos = plt.subplots(1, 2, figsize=(16, 5))
    fig.suptitle(stem, fontsize=13, fontweight="bold")
    eixos[0].plot(t_esperado_ms, esperado, color="#1f77b4", linewidth=0.8)
    eixos[0].set_title("Gerado (gerar() + seed)")
    eixos[0].set_xlabel("Tempo (ms)")
    eixos[0].grid(True, alpha=0.3)
    eixos[1].plot(t_capturado_ms, capturado, color="#d62728", linewidth=0.8)
    eixos[1].set_title("Capturado (bancada real)")
    eixos[1].set_xlabel("Tempo (ms)")
    eixos[1].grid(True, alpha=0.3)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(imagens_dir / f"{stem}_comparacao.png", dpi=110)
    plt.close(fig)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sessao_dir", type=Path, help="Pasta resultados/sessao_.../ a analisar")
    parser.add_argument("--sem-imagens", action="store_true", help="Não gera PNGs, só o relatório no terminal")
    args = parser.parse_args(argv)

    relatorio = analisar_sessao(args.sessao_dir, gerar_imagens=not args.sem_imagens)
    print(f"{'arquivo':<40}{'lag (ms)':>12}{'correlação':>12}{'razão pico':>12}")
    for linha in relatorio:
        if "erro" in linha:
            print(f"{linha['classe']:<40}  ERRO: {linha['erro']}")
            continue
        print(f"{linha['classe']:<40}{linha['lag_ms']:>12.2f}{linha['correlacao']:>12.3f}{linha['razao_pico']:>12.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_offline.py -k AnalisarSessao -v`
Expected: PASS

- [ ] **Step 5: Validação manual com dados reais (opcional, se a pasta `resultados/sessao_*` ou `resultados/` da última sessão física ainda existir)**

```bash
cd logica
python analisar_sessao.py ../resultados
```

Expected: imprime uma linha por `.npz`, sem traceback. (Se `../resultados` ainda estiver no formato antigo — um `.npz` por classe, sem `nivel_indice` no metadata — o script deve rodar mesmo assim, já que só depende de `id_captura`/`seed`/`pontos`/`fs_hz`, todos já presentes no formato antigo.)

- [ ] **Step 6: Commit**

```bash
git add logica/analisar_sessao.py tests/test_offline.py
git commit -m "feat: novo script offline analisar_sessao.py — cross-correlação, razão de pico e comparação visual por sessão"
```

---

## Task 10: `CHANGELOG/v1.8.md` e `README.md`

**Files:**
- Create: `CHANGELOG/v1.8.md`
- Modify: `README.md` (§5.3 referência de comandos, §5.8 onde os dados caem)

- [ ] **Step 1: Escrever `CHANGELOG/v1.8.md`**

Seguir a estrutura já usada em `CHANGELOG/v1.7.md` (Por quê / O que mudou / O que não mudou). Conteúdo: resumir a motivação (inspeção visual das 20 capturas revelou perda de cauda em 14/20 classes e redundância de sorteio em 08/TRANSIENT — ver spec), e listar exatamente os arquivos/funções tocados nas Tasks 1-9 acima (reaproveitar a tabela "Componentes afetados" do spec, ajustada para o formato de changelog). Referenciar o spec: `docs/superpowers/specs/2026-09-11-sessao-bancada-v18-design.md`.

- [ ] **Step 2: Atualizar `README.md` §5.3**

Adicionar as 3 linhas de `set margin|diagnostico|capturas` na tabela de comandos da CLI (mesmo formato das linhas `lowvoltage`/`native`/`run` já existentes).

- [ ] **Step 3: Atualizar `README.md` §5.8 ("Onde os dados caem")**

Documentar: (a) pasta `resultados/sessao_<timestamp>/` por sessão de CLI em vez de gravar direto em `resultados/`; (b) um `.npz` por captura (nome inclui nível/parâmetro quando existe) em vez de um `.npz` por classe com N capturas empilhadas; (c) mencionar `logica/analisar_sessao.py` como a ferramenta pra inspecionar uma sessão depois.

- [ ] **Step 4: Rodar a suíte completa uma última vez**

Run: `python -m pytest tests/test_offline.py -v`
Expected: todos os testes (os ~35 originais + os novos das Tasks 1-9) passam.

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG/v1.8.md README.md
git commit -m "docs: CHANGELOG v1.8 e README atualizados para sessão de bancada v1.8"
```

---

## Self-review (fresh eyes contra o spec)

- **Cobertura do spec:** §1 sessão isolada → Task 8. §2 um `.npz`/captura → Task 5. §3 cobertura de níveis/parâmetros → Tasks 4, 6. §4 `margin` → Task 7. §5 `diagnostico` (com os 2 pontos de log adicionados depois da pergunta do usuário sobre suficiência) → Task 2. §6 `analisar_sessao.py` → Task 9. Erros de borda do spec (`set capturas 0`, `margin on` simulado sem efeito, sessão sem `run` não cria pasta, `analisar_sessao.py` sem `metadata/`) → cobertos em Tasks 7/8/9 respectivamente.
- **Placeholder scan:** nenhum "TBD"/"implementar depois" — todo passo tem código completo ou comando exato a rodar.
- **Consistência de tipos:** `capture_index`/`indice_global` usados consistentemente entre Tasks 4 e 5/6 (a Task 4 é quem define o contrato — `capture_index` remapeado só serve pra indexar nível/parâmetro, `indice_global` é sempre a identidade única da captura); `valor_para_captura(..., cobertura_ativa: bool)` com a mesma assinatura em Tasks 1 e 6.
- **Desvio anotado do spec original:** `05.py` recebe 1 linha (`total_niveis()`) — o spec dizia "sem alteração" pros três scripts de NIVEIS; na prática só `02.py`/`03.py` ficam intocados, porque `NIVEIS_THD` em `05.py` é global de módulo, não atributo de classe, e o default de `total_niveis()` só enxerga atributos de instância/classe. Mudança mínima (1 método, zero lógica), mas documentada aqui para não ser uma surpresa silenciosa.
