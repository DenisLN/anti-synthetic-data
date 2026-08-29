"""Preflight progressivo da comunicação e do trigger, sem energização por padrão."""

from __future__ import annotations

import argparse
import math
import sys

import numpy as np

from mestre import (
    BASE_VOLTAGE_RMS,
    FS_HZ,
    GRID_FREQUENCY_HZ,
    OUTPUT_ARMED,
    POINTS,
    inicializar_instrumentos,
)


def normal_waveform() -> np.ndarray:
    time_s = np.arange(POINTS, dtype=np.float64) / FS_HZ
    return np.sin(2.0 * np.pi * GRID_FREQUENCY_HZ * time_s)


def run(trigger_test: bool, low_voltage: bool) -> int:
    source = None
    scope = None
    try:
        source, scope, _config = inicializar_instrumentos(require_output=low_voltage)
        if scope is None:
            raise RuntimeError("Preflight físico requer BENCH_MODE=1")
        print(f"AMETEK OK: {source.idn}")
        print(f"KEYSIGHT OK: {scope.idn}")
        print(
            f"AMETEK VISA serial: {source.resource_name} "
            f"({source.port}) @ {source.baudrate} N/8/1"
        )
        print(f"KEYSIGHT VISA: {scope.adapter}")
        if low_voltage:
            # inicializar_instrumentos já energizou o baseline quando
            # require_output=True e ARM_OUTPUT=YES (saída fica ligada durante
            # toda a bateria, não só durante este teste).
            if not OUTPUT_ARMED:
                raise RuntimeError("O teste de baixa tensão exige ARM_OUTPUT=YES")
            if not source.output_enabled:
                raise RuntimeError("AMETEK deveria estar energizada (baseline) para este teste")
            print("OUTPUT ON confirmado (baseline)")
        else:
            if source.output_enabled:
                raise RuntimeError("Saída AMETEK está ligada durante o preflight")
            print("OUTPUT OFF confirmado")

        if trigger_test or low_voltage:
            source.program_capture(
                normal_waveform(),
                base_voltage_rms=BASE_VOLTAGE_RMS,
                frequency_hz=GRID_FREQUENCY_HZ,
            )
            if low_voltage:
                scope.set_vertical_scale(1, BASE_VOLTAGE_RMS * math.sqrt(2.0))
            scope.arm()
            scope.wait_for_armed()
            print("Keysight em WAIT FOR TRIGGER")
            if low_voltage:
                source.arm_transient()
                print("AMETEK em ARM/WTRIG")
                source.trigger()
            else:
                # A MX30 Rev. 5.53 não arma o transient com OUTPUT OFF. Forçar
                # somente o scope valida aquisição/download sem fingir que o
                # BNC foi testado; o BNC real é validado na etapa de 5 Vrms.
                scope.force_trigger()
            scope.wait_for_trigger_complete()
            if low_voltage:
                source.wait_transient_complete()
            time_s, voltage_v = scope.get_waveform(1)
            if len(time_s) != POINTS:
                raise RuntimeError("Waveform de preflight não contém 6000 pontos")
            if low_voltage:
                measured_rms = float(np.sqrt(np.mean(np.square(voltage_v))))
                tolerance = max(0.25, BASE_VOLTAGE_RMS * 0.10)
                if not math.isclose(measured_rms, BASE_VOLTAGE_RMS, abs_tol=tolerance):
                    raise RuntimeError(
                        f"RMS medido {measured_rms:.3f} V não corresponde a "
                        f"{BASE_VOLTAGE_RMS:.3f} V"
                    )
                print(f"Baixa tensão validada: {measured_rms:.3f} Vrms")
            if low_voltage:
                print("Trigger BNC e aquisição de 6000 pontos confirmados em 5 Vrms")
            else:
                print("Aquisição/download do Keysight confirmados; BNC ainda NÃO testado")
        return 0
    finally:
        if source is not None:
            source.disconnect()
        if scope is not None:
            scope.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trigger-test",
        action="store_true",
        help="testa TTL Trigger Out -> EXT Trigger mantendo a saída de potência OFF",
    )
    parser.add_argument(
        "--low-voltage",
        action="store_true",
        help="faz aquisição a BASE_VOLTAGE_RMS; exige ARM_OUTPUT=YES",
    )
    args = parser.parse_args()
    try:
        return run(args.trigger_test, args.low_voltage)
    except BaseException as exc:
        # stdout evita que Windows PowerShell 5 converta texto nativo em um
        # NativeCommandError antes de o script avaliar o código de saída.
        print(f"PREFLIGHT FALHOU: {exc}", file=sys.stdout)
        return 1


if __name__ == "__main__":
    sys.exit(main())
