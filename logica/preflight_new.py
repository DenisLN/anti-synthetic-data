"""Preflight estendido: exercita os comandos dos dois ORMs (AMETEK MX30 e
Keysight DSO-X 4034A) em baixa tensão controlada, com log auditável de cada
etapa aprovada em ``logs/preflight_new-<timestamp>.log``.

Reaproveita os estágios de ``preflight.py`` (comunicação/IDN, OUTPUT OFF,
trigger BNC, 5 Vrms via TRACe/LIST) e adiciona os mecanismos nativos que
nenhum dos dois preflights testava até aqui: STEP, PULSe, CSINe nativo,
LIST:FREQuency, ACDC/offset, as medições (MEASure:*) e o canal 2 (corrente) do
osciloscópio. Cada etapa usa a MESMA sequência de armamento que
``ExperimentoNativo._capturar_real`` em ``mestre.py``
(``configurar -> osc.arm()/wait_for_armed() -> fonte.arm() -> fonte.trigger()``)
— testar uma ordem diferente aqui validaria um caminho que a bancada real não
percorre.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np

from mestre import (
    BASE_VOLTAGE_RMS,
    CAPTURE_CURRENT,
    CURRENT_BASE_A,
    CURRENT_PROBE_ATTENUATION,
    DISTURBANCE_START_S,
    DURATION_S,
    FS_HZ,
    GRID_FREQUENCY_HZ,
    OUTPUT_ARMED,
    POINTS,
    PROJECT_ROOT,
    Bancada,
)
from preflight import run as run_basic_stage
from sinais import janela

LOG_DIR = PROJECT_ROOT / "logs"
logger = logging.getLogger("PreflightNew")

# Tolerâncias generosas de propósito: o objetivo é confirmar que cada comando
# produz o efeito físico esperado na ordem de grandeza certa (o comando SCPI
# certo, na ordem certa), não medir com precisão de instrumentação de bancada.
RMS_TOLERANCE_V = max(0.25, BASE_VOLTAGE_RMS * 0.10)
SAG_LEVEL_PU = 0.5
SAG_DURATION_S = 0.060
CSINE_THD_PCT = 10.0
FREQ_DRIFT_START_HZ = GRID_FREQUENCY_HZ - 3.0
FREQ_DRIFT_END_HZ = GRID_FREQUENCY_HZ + 3.0
DC_OFFSET_PU = 0.05


def _configure_logging(stage: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"preflight_new-{stage}-{timestamp}.log"
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    # mestre.py já roda logging.basicConfig() no import (handler no root
    # logger, stdout); sem propagate=False cada linha sai duplicada, uma vez
    # pelo handler deste logger e outra pelo handler do root.
    logger.propagate = False
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%H:%M:%S")
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return log_path


def _step(name: str, fn: Callable[[], Optional[str]]) -> None:
    """Executa uma etapa nomeada; loga OK com o detalhe devolvido por ``fn``,
    ou FALHOU com a exceção, e propaga a exceção (aborta o restante das
    etapas — mesma filosofia fail-safe do resto do projeto)."""
    logger.info("--- %s", name)
    try:
        detail = fn()
    except Exception as exc:
        logger.error("FALHOU: %s: %s", name, exc)
        raise
    logger.info("OK: %s%s", name, f" ({detail})" if detail else "")


def _write_and_confirm(
    instrument, command: str, query: str, *, label: Optional[str] = None,
) -> Tuple[str, float]:
    """Escreve um comando e imediatamente manda a consulta de confirmação
    correspondente — o mesmo padrão que o software oficial da AMETEK usa
    (SET seguido de GET) — cronometrando o tempo entre o write e a resposta
    da consulta. Não adivinha um delay fixo: mede o tempo real que a fonte
    levou para aceitar e confirmar o parâmetro, e loga os dois."""
    start = time.monotonic()
    instrument.write(command)
    response = instrument.query(query)
    elapsed_s = time.monotonic() - start
    logger.info(
        "%s: write=%r -> confirmação=%r (%.0f ms)",
        label or command, command, response, elapsed_s * 1000.0,
    )
    return response, elapsed_s


def _rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(values))))


def _assert_close(label: str, measured: float, expected: float, tolerance: float) -> None:
    if not math.isclose(measured, expected, abs_tol=tolerance):
        raise RuntimeError(
            f"{label}: medido {measured:.3f} não corresponde a {expected:.3f} "
            f"(tolerância {tolerance:.3f})"
        )


def _capture_native(
    source,
    scope,
    *,
    configure: Callable[[], None],
    expected_peak_v: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Reproduz exatamente ``ExperimentoNativo._capturar_real`` (ramo não-TRACe)
    de ``mestre.py``: programa o transiente, arma o osciloscópio, arma e
    dispara a fonte, aguarda os dois lados."""
    configure()
    scope.set_vertical_scale(1, expected_peak_v)
    scope.arm()
    scope.wait_for_armed()
    source.arm()
    source.trigger()
    scope.wait_for_trigger_complete()
    source.wait_transient_complete()
    time_s, voltage_v = scope.get_waveform(1, expected_points=POINTS)
    if len(time_s) != POINTS:
        raise RuntimeError(f"Waveform não contém {POINTS} pontos")
    return time_s, voltage_v


def _test_step(source, scope) -> str:
    time_s, voltage_v = _capture_native(
        source,
        scope,
        configure=lambda: source.trigger_step(BASE_VOLTAGE_RMS),
        expected_peak_v=BASE_VOLTAGE_RMS * math.sqrt(2.0),
    )
    measured_rms = _rms(voltage_v)
    _assert_close("STEP nativo", measured_rms, BASE_VOLTAGE_RMS, RMS_TOLERANCE_V)
    return f"RMS={measured_rms:.3f} Vrms"


def _test_pulse_sag(source, scope) -> str:
    # O PULSe da AMETEK cai imediatamente no *TRG (sem parâmetro de delay —
    # ver trigger_pulse() em ametek_orm.py); é o pre_trigger_s do osciloscópio
    # que empurra o instante do trigger para DISTURBANCE_START_S dentro do
    # buffer capturado, deixando um trecho de baseline ANTES do SAG. Mesma
    # configuração que experimentos_nativos/02.py (classe SAG real) usa —
    # sem isso, o *TRG cai em t=0 e a janela abaixo corta a própria queda de
    # tensão como se fosse baseline "de fora" (foi o que aconteceu antes
    # desse ajuste: RMS "fora" media a mistura entre queda e patamar).
    scope.configure_acquisition(
        sample_rate_hz=FS_HZ, points=POINTS, duration_s=DURATION_S,
        pre_trigger_s=DISTURBANCE_START_S,
    )
    try:
        time_s, voltage_v = _capture_native(
            source,
            scope,
            configure=lambda: source.trigger_pulse(SAG_LEVEL_PU * BASE_VOLTAGE_RMS, width_s=SAG_DURATION_S),
            expected_peak_v=BASE_VOLTAGE_RMS * math.sqrt(2.0),
        )
        dentro = janela(time_s, DISTURBANCE_START_S, SAG_DURATION_S)
        if not np.any(dentro) or not np.any(~dentro):
            raise RuntimeError("Janela do pulso SAG não recortou nenhuma amostra dentro/fora")
        rms_fora = _rms(voltage_v[~dentro])
        rms_dentro = _rms(voltage_v[dentro])
        _assert_close("PULSe fora da janela", rms_fora, BASE_VOLTAGE_RMS, RMS_TOLERANCE_V)
        _assert_close("PULSe dentro da janela (SAG)", rms_dentro, SAG_LEVEL_PU * BASE_VOLTAGE_RMS, RMS_TOLERANCE_V)
        return f"RMS fora={rms_fora:.3f} V, dentro={rms_dentro:.3f} V"
    finally:
        # Restaura pre_trigger_s=0.0 (mesma config das outras etapas nativas
        # deste preflight — CSINe/LIST:FREQuency/ACDC não usam pre-trigger).
        scope.configure_acquisition(sample_rate_hz=FS_HZ, points=POINTS, duration_s=DURATION_S)


def _test_csine(source, scope) -> str:
    def configure() -> None:
        source.configure_harmonics_csine(CSINE_THD_PCT)
        source.trigger_step(BASE_VOLTAGE_RMS)

    time_s, voltage_v = _capture_native(
        source, scope, configure=configure, expected_peak_v=BASE_VOLTAGE_RMS * math.sqrt(2.0) * 1.5,
    )
    measured_rms = _rms(voltage_v)
    _assert_close("CSINe nativo", measured_rms, BASE_VOLTAGE_RMS, RMS_TOLERANCE_V)
    return f"THD={CSINE_THD_PCT}%, RMS={measured_rms:.3f} Vrms"


def _test_frequency_drift(source, scope) -> str:
    time_s, voltage_v = _capture_native(
        source,
        scope,
        configure=lambda: source.frequency_drift_list(
            FREQ_DRIFT_START_HZ, FREQ_DRIFT_END_HZ,
            voltage_rms=BASE_VOLTAGE_RMS, dwell_s=DURATION_S / 2.0,
        ),
        expected_peak_v=BASE_VOLTAGE_RMS * math.sqrt(2.0),
    )
    measured_rms = _rms(voltage_v)
    _assert_close("LIST:FREQuency nativo", measured_rms, BASE_VOLTAGE_RMS, RMS_TOLERANCE_V)
    zero_crossings = np.sum(np.diff(np.sign(voltage_v)) != 0)
    estimated_hz = zero_crossings / 2.0 / (time_s[-1] - time_s[0])
    return f"RMS={measured_rms:.3f} Vrms, f estimada~={estimated_hz:.1f} Hz"


def _test_dc_offset(source, scope) -> str:
    ac_peak_v = BASE_VOLTAGE_RMS * math.sqrt(2.0)
    offset_v = DC_OFFSET_PU * ac_peak_v

    def configure() -> None:
        source.enable_dc_offset(offset_v, ac_peak_v=ac_peak_v)
        source.trigger_step(BASE_VOLTAGE_RMS)

    time_s, voltage_v = _capture_native(
        source, scope, configure=configure,
        expected_peak_v=(ac_peak_v + offset_v) * 1.25,
    )
    measured_offset = float(np.mean(voltage_v))
    # Tolerância própria (não RMS_TOLERANCE_V): o offset é pequeno demais
    # (DC_OFFSET_PU=5% do pico AC) para uma tolerância de 10% de
    # BASE_VOLTAGE_RMS — isso aceitaria até um enable_dc_offset() que não
    # fizesse nada.
    offset_tolerance_v = max(0.15, abs(offset_v) * 0.20)
    _assert_close("ACDC/offset nativo", measured_offset, offset_v, offset_tolerance_v)
    return f"offset medido={measured_offset:.3f} V (programado {offset_v:.3f} V)"


def _test_measurements(source) -> str:
    voltage = source.measure_voltage()
    current = source.measure_current()
    power_w = source.measure_power_w()
    power_factor = source.measure_power_factor()
    for label, value in (
        ("MEASure:VOLTage", voltage), ("MEASure:CURRent", current),
        ("MEASure:POWer", power_w), ("MEASure:PFACtor", power_factor),
    ):
        if not np.isfinite(value):
            raise RuntimeError(f"{label} retornou valor não finito: {value!r}")
    return (
        f"V={voltage:.3f} Vrms, I={current:.3f} A, "
        f"P={power_w:.3f} W, FP={power_factor:.3f}"
    )


def _test_scope_error_queue(scope) -> str:
    errors = scope.check_errors()
    if errors:
        raise RuntimeError(f"Fila de erros Keysight não está vazia: {errors}")
    return "fila de erros vazia"


def _test_channel2_toggle(scope) -> Optional[str]:
    """Exercita disable_channel/configure_channel do CH2. Só reprograma com um
    fator de probe REAL (nunca inventado) quando CAPTURE_CURRENT=1 já fornece
    CURRENT_PROBE_ATTENUATION/CURRENT_BASE_A pelo ambiente."""
    scope.disable_channel(2)
    if not CAPTURE_CURRENT:
        return "CH2 desligado; CAPTURE_CURRENT=0, reativação pulada (sem fator de probe)"
    if CURRENT_PROBE_ATTENUATION is None or CURRENT_BASE_A is None:
        raise RuntimeError("CAPTURE_CURRENT=1 mas CURRENT_PROBE_ATTENUATION/CURRENT_BASE_A ausentes")
    current_peak = max(float(CURRENT_BASE_A), 1e-6) * math.sqrt(2.0)
    scope.configure_channel(
        2, scale=current_peak / 3.5, probe_attenuation=float(CURRENT_PROBE_ATTENUATION),
        coupling="DC", units="AMP",
    )
    return f"CH2 desligado e reativado ({CURRENT_PROBE_ATTENUATION}x, {CURRENT_BASE_A} A base)"


def _test_list_voltage_identical_values(source) -> str:
    """Isola SOURce:LIST:VOLTage do resto de program_capture() (logica/
    ametek_orm.py) e compara, separadamente, uma lista de 12 valores
    DISTINTOS com uma lista de 12 valores IDÊNTICOS — escreve e confirma cada
    uma com _write_and_confirm(), sem delay adivinhado.

    Hipótese, a partir do manual SCPI (docs/AMETEK_MX_SCPI_Programming_Manual.pdf,
    seção 4.17): "a lista de 1 item é tratada como se tivesse os mesmos N
    pontos que as outras listas, com todos os valores iguais ao único item".
    Se o firmware colapsar uma lista de N valores IDÊNTICOS para esse caso
    especial de 1 item, LIST:VOLTage:POINts? volta 1 mesmo com N valores
    enviados. Isso bateria com a falha observada em
    ``preflight.py --low-voltage``: a senoide limpa de ``normal_waveform()``
    produz 12 ciclos com RMS numericamente idêntico."""
    source.write("ABORt")
    source.write("*CLS")

    distinct_values = ",".join(f"{5.0 + index * 0.01:.4g}" for index in range(12))
    response, elapsed_distinct_s = _write_and_confirm(
        source, f"SOURce:LIST:VOLTage {distinct_values}", "SOURce:LIST:VOLTage:POINts?",
        label="LIST:VOLTage (12 valores distintos)",
    )
    distinct_points = int(float(response))

    identical_values = ",".join(["5.0"] * 12)
    response, elapsed_identical_s = _write_and_confirm(
        source, f"SOURce:LIST:VOLTage {identical_values}", "SOURce:LIST:VOLTage:POINts?",
        label="LIST:VOLTage (12 valores idênticos)",
    )
    identical_points = int(float(response))

    source.write("ABORt")
    source.write("*CLS")

    if distinct_points != 12:
        raise RuntimeError(
            f"LIST:VOLTage com 12 valores DISTINTOS registrou {distinct_points} pontos "
            "(esperado 12) — a falha não é específica de valores idênticos; investigar de novo"
        )
    if identical_points == 1:
        logger.warning(
            "HIPÓTESE CONFIRMADA: o firmware trata uma LIST:VOLTage de 12 valores idênticos "
            "como o caso especial de lista de 1 item (manual, sec. 4.17) — por isso "
            "program_capture() falha com senoide limpa (todos os ciclos têm o mesmo RMS)."
        )
    elif identical_points != 12:
        logger.warning(
            "Nem 1 nem 12: LIST:VOLTage com valores idênticos registrou %d pontos — "
            "hipótese de colapso para lista de 1 item não confirmada, investigar outra causa.",
            identical_points,
        )
    return (
        f"distintos: {distinct_points} pontos em {elapsed_distinct_s * 1000:.0f} ms; "
        f"idênticos: {identical_points} pontos em {elapsed_identical_s * 1000:.0f} ms"
    )


def _test_list_sequence_matches_production(source) -> str:
    """Reproduz a MESMA sequência e ORDEM de comandos que
    ``AmetekMX30.program_capture()`` usa (SOURce:LIST:FUNCtion:SHAPe ->
    SOURce:LIST:VOLTage -> SOURce:LIST:DWELl), escritos back-to-back sem
    NENHUMA pausa entre eles — igual ao código real —, mas sem os ~12 s de
    tráfego serial de TRACe:DATA que os antecedem numa captura de verdade.

    O teste anterior (_test_list_voltage_identical_values) mandou
    SOURce:LIST:VOLTage ISOLADO, sem SOURce:LIST:FUNCtion:SHAPe logo antes —
    e os 12 pontos vieram certos, nos dois casos (valores distintos e
    idênticos). Isso descarta a hipótese de colapso por valores idênticos, e
    reabre a hipótese original: um comando LIST longo (FUNCtion:SHAPe com 12
    nomes) imediatamente seguido de outro (VOLTage), sem pausa, pode ainda
    estar ocupando o parser serial da Rev. 5.53 quando o segundo chega."""
    source.write("ABORt")
    source.write("*CLS")

    trace_names = tuple(f"TCC{index:02d}" for index in range(12))
    source._ensure_trace_slots(trace_names)  # garante que os nomes existem

    names = ",".join(trace_names)
    voltages = ",".join(["5.0"] * 12)
    dwells = ",".join(["0.01666667"] * 12)

    details = []
    for command, query, label in (
        (f"SOURce:LIST:FUNCtion:SHAPe {names}", "SOURce:LIST:FUNCtion:POINts?", "FUNCtion:SHAPe"),
        (f"SOURce:LIST:VOLTage {voltages}", "SOURce:LIST:VOLTage:POINts?", "VOLTage"),
        (f"SOURce:LIST:DWELl {dwells}", "SOURce:LIST:DWELl:POINts?", "DWELl"),
    ):
        response, elapsed_s = _write_and_confirm(
            source, command, query, label=f"LIST:{label} (sequência real, sem pausa)",
        )
        points = int(float(response))
        details.append(f"{label}={points} pontos em {elapsed_s * 1000:.0f} ms")
        if points != 12:
            logger.warning(
                "LIST:%s registrou %d pontos (esperado 12) na sequência back-to-back "
                "sem pausa — reproduz a falha real de program_capture().", label, points,
            )

    errors = source.check_errors()
    source.write("ABORt")
    source.write("*CLS")
    if errors:
        details.append(f"erros SCPI durante a sequência: {errors}")
    return "; ".join(details)


def _test_list_repeat_count(source) -> str:
    """Isola SOURce:LIST:REPeat:COUNt — o comando que ``--low-voltage`` mais
    recentemente reportou como rejeitado pela AMETEK real: 'AMETEK rejeitou
    "SOURce:LIST:REPeat:COUNt 1,1,1,1,1,1,1,1,1,1,1,1" durante programação
    da lista: [(-113, "Undefined header")]'.

    -113 é especificamente erro de CABEÇALHO (mnemônico não reconhecido),
    não de parâmetro/valor — a hipótese testada aqui é de sintaxe do
    comando, não do dado enviado. O manual documenta
    '[SOURce:]LIST:REPeat[:COUNt] <NRf+>,<NRf+>' (seção 4.17.5) como
    sintaxe válida, mas o tutorial oficial de "List Transients" (seção
    6.4.3) programa uma lista completa (VOLTage/FREQuency/DWELl/COUNt) sem
    NUNCA usar LIST:REPeat:COUNt. Como ``program_capture()`` sempre manda
    todos os valores "1" (nunca um repeat por ponto de verdade), a hipótese
    adicional é que o comando é dispensável: o estado padrão do eixo REPEAT
    já cobre "1 repetição por ponto" sem precisar setá-lo.

    Testa nesta ordem, cada write seguido de SYSTem:ERRor? (mesmo padrão de
    program_capture(), sem delay adivinhado): (1) o estado padrão de
    LIST:REPeat:POINts? sem escrever nada; (2) reproduz o comando exato que
    falhou na produção; (3) variações de cabeçalho (com/sem 'SOURce:',
    com/sem ':COUNt'); (4) um único valor '1' em vez de 12 (caso especial de
    lista de 1 item, seção 4.17: um único ponto vale para todos)."""
    source.write("ABORt")
    source.write("*CLS")

    trace_names = tuple(f"TCC{index:02d}" for index in range(12))
    source._ensure_trace_slots(trace_names)
    names = ",".join(trace_names)
    voltages = ",".join(["5.0"] * 12)
    dwells = ",".join(["0.01666667"] * 12)
    for command, points_query in (
        (f"SOURce:LIST:FUNCtion:SHAPe {names}", "SOURce:LIST:FUNCtion:POINts?"),
        (f"SOURce:LIST:VOLTage {voltages}", "SOURce:LIST:VOLTage:POINts?"),
        (f"SOURce:LIST:DWELl {dwells}", "SOURce:LIST:DWELl:POINts?"),
    ):
        response, _elapsed_s = _write_and_confirm(source, command, points_query)
        if int(float(response)) != 12:
            raise RuntimeError(
                f"{points_query} retornou {response!r} na pré-condição de REPeat; esperado 12"
            )

    default_repeat_points = source.query("SOURce:LIST:REPeat:POINts?")
    logger.info(
        "SOURce:LIST:REPeat:POINts? sem nenhuma escrita prévia (estado padrão): %r",
        default_repeat_points,
    )
    results = [f"padrão sem escrever={default_repeat_points!r}"]
    accepted: Optional[str] = None

    def _try(label: str, command: str) -> None:
        nonlocal accepted
        start = time.monotonic()
        source.write(command)
        errors = source.check_errors()
        elapsed_ms = (time.monotonic() - start) * 1000.0
        status = "OK" if not errors else f"REJEITADO {errors}"
        logger.info("LIST:REPeat variante %s: write=%r -> %s (%.0f ms)", label, command, status, elapsed_ms)
        results.append(f"{label}={status}")
        if not errors and accepted is None:
            accepted = label

    repeats_12 = ",".join(["1"] * 12)
    _try("SOURce:LIST:REPeat:COUNt (12 valores, igual à produção)", f"SOURce:LIST:REPeat:COUNt {repeats_12}")
    _try("SOURce:LIST:REPeat sem ':COUNt' (12 valores)", f"SOURce:LIST:REPeat {repeats_12}")
    _try("LIST:REPeat:COUNt sem 'SOURce:' (12 valores)", f"LIST:REPeat:COUNt {repeats_12}")
    _try("LIST:REPeat sem 'SOURce:' nem ':COUNt' (12 valores)", f"LIST:REPeat {repeats_12}")
    _try("SOURce:LIST:REPeat:COUNt (1 valor único)", "SOURce:LIST:REPeat:COUNt 1")

    source.write("ABORt")
    source.write("*CLS")

    if accepted is None:
        raise RuntimeError(
            "Nenhuma variante de LIST:REPeat:COUNt foi aceita pela AMETEK: " + "; ".join(results)
        )
    logger.warning(
        "Variante aceita pela AMETEK: %r. Se for diferente do comando atual em "
        "ametek_orm.AmetekMX30.program_capture() (linha com 'SOURce:LIST:REPeat:COUNt {repeats}'), "
        "atualize-o com esta sintaxe — ou remova o comando por completo, já que o "
        "padrão sem escrever (%r) sugere que já cobre o caso 'sem repeat' que a "
        "produção sempre usa (todos os valores são '1').",
        accepted, default_repeat_points,
    )
    return "; ".join(results)


def run_list_diagnostics() -> int:
    """Não precisa de ARM_OUTPUT=YES: só programa e lê de volta listas
    SCPI, nunca energiza a saída (nenhum arm()/trigger() é chamado aqui)."""
    bancada = None
    try:
        bancada = Bancada.from_env(require_output=False)
        source = bancada.fonte
        logger.info("AMETEK OK: %s", source.idn)
        _step(
            "SOURce:LIST:VOLTage — valores distintos vs. idênticos",
            lambda: _test_list_voltage_identical_values(source),
        )
        _step(
            "Sequência LIST real (FUNCtion:SHAPe -> VOLTage -> DWELl), sem pausa",
            lambda: _test_list_sequence_matches_production(source),
        )
        _step(
            "SOURce:LIST:REPeat:COUNt — variantes de cabeçalho "
            "(reproduz a falha de --low-voltage: -113 Undefined header)",
            lambda: _test_list_repeat_count(source),
        )
        return 0
    finally:
        if bancada is not None:
            bancada.shutdown()


def run_native_commands() -> int:
    if not OUTPUT_ARMED:
        raise RuntimeError("Teste de comandos nativos exige ARM_OUTPUT=YES")
    bancada = None
    try:
        bancada = Bancada.from_env(require_output=True)
        source, scope = bancada.fonte, bancada.osc
        if scope is None:
            raise RuntimeError("Preflight físico requer BENCH_MODE=1")
        logger.info("AMETEK OK: %s", source.idn)
        logger.info("KEYSIGHT OK: %s", scope.idn)
        if not source.output_enabled:
            raise RuntimeError("AMETEK deveria estar energizada (baseline) para este teste")
        logger.info("OUTPUT ON confirmado (baseline @ %.3f Vrms)", BASE_VOLTAGE_RMS)

        _step("Fila de erros do Keysight (antes)", lambda: _test_scope_error_queue(scope))
        _step("STEP nativo (VOLTage:MODE STEP)", lambda: _test_step(source, scope))
        _step("PULSe nativo (SAG a 50%)", lambda: _test_pulse_sag(source, scope))
        _step("CSINe nativo (senoide clipada)", lambda: _test_csine(source, scope))
        _step("LIST:FREQuency nativo (desvio de frequência)", lambda: _test_frequency_drift(source, scope))
        _step("ACDC/offset nativo (SOURce:VOLTage:OFFSet)", lambda: _test_dc_offset(source, scope))
        _step("Medições AMETEK (MEASure:*)", lambda: _test_measurements(source))
        _step("Canal 2 do Keysight (disable/configure)", lambda: _test_channel2_toggle(scope))
        _step("Fila de erros do Keysight (depois)", lambda: _test_scope_error_queue(scope))

        logger.info("Todos os comandos nativos dos dois ORMs foram exercitados com sucesso")
        return 0
    finally:
        if bancada is not None:
            bancada.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trigger-test", action="store_true",
        help="delega ao preflight.py: testa TTL Trigger Out -> EXT Trigger com OUTPUT OFF",
    )
    parser.add_argument(
        "--low-voltage", action="store_true",
        help="delega ao preflight.py: aquisição a BASE_VOLTAGE_RMS via TRACe/LIST; exige ARM_OUTPUT=YES",
    )
    parser.add_argument(
        "--native-commands", action="store_true",
        help=(
            "exercita STEP/PULSe/CSINe/LIST:FREQuency/ACDC/MEASure* da AMETEK e "
            "disable/configure_channel do Keysight, cada um com aquisição real e "
            "log de OK/FALHOU por etapa; exige ARM_OUTPUT=YES"
        ),
    )
    parser.add_argument(
        "--list-diagnostics", action="store_true",
        help=(
            "isola os comandos SOURce:LIST:* de program_capture() (VOLTage, "
            "sequência FUNCtion:SHAPe->VOLTage->DWELl, e variantes de "
            "REPeat:COUNt) com write+confirmação+cronometragem, sem delay "
            "adivinhado; não energiza a saída, não exige ARM_OUTPUT=YES"
        ),
    )
    args = parser.parse_args()

    stage = (
        "list-diagnostics" if args.list_diagnostics
        else "native-commands" if args.native_commands
        else "low-voltage" if args.low_voltage
        else "trigger-test" if args.trigger_test
        else "comm"
    )
    log_path = _configure_logging(stage)
    logger.info("Log desta etapa: %s", log_path)

    try:
        if args.list_diagnostics:
            return run_list_diagnostics()
        if args.native_commands:
            return run_native_commands()
        return run_basic_stage(args.trigger_test, args.low_voltage)
    except BaseException as exc:
        logger.error("PREFLIGHT_NEW FALHOU: %s", exc)
        # stdout evita que Windows PowerShell 5 converta texto nativo em um
        # NativeCommandError antes de o script avaliar o código de saída.
        print(f"PREFLIGHT_NEW FALHOU: {exc}", file=sys.stdout)
        return 1


if __name__ == "__main__":
    sys.exit(main())
