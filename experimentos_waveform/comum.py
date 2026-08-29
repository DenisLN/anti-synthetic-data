"""Helpers dos experimentos que precisam de forma de onda arbitrária (TRACe/LIST).

Autocontido: não importa mestre.py. Tudo que precisa (fs_hz, base_voltage_rms,
limites, etc.) chega por parâmetro (o ``config`` que mestre.py monta uma vez e
repassa para cada ``run(fonte, osc, config)``).
"""

from __future__ import annotations

import json
import logging
import math
import os
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("ExperimentosWaveform")


def salvar_classe(
    config,
    experiment_id: str,
    class_name: str,
    *,
    tempo_ms: np.ndarray,
    tensao_por_snr: Dict[float, np.ndarray],
    ids: List[str],
    corrente: Optional[np.ndarray],
    metadados: List[dict],
) -> None:
    """Grava uma classe completa em .npz (um arquivo por nível de SNR) + metadata.jsonl.

    Escrita atômica: grava em ``.part`` e só promove para o nome final (via
    ``os.replace``) depois que tudo terminou sem erro — resultados parciais
    nunca ficam visíveis como se fossem completos.
    """
    ids_array = np.array(ids, dtype=object)
    final_paths = []

    for snr_db, tensao in tensao_por_snr.items():
        rotulo = str(int(snr_db)) if float(snr_db).is_integer() else str(snr_db).replace(".", "_")
        directory = config.results_dir / f"snr_{rotulo}db"
        directory.mkdir(parents=True, exist_ok=True)
        final_path = directory / f"{experiment_id}_{class_name.lower()}.npz"
        partial_path = final_path.with_suffix(".npz.part")
        with partial_path.open("wb") as handle:
            np.savez(handle, tempo_ms=tempo_ms, tensao_pu=tensao, classe=class_name, id_captura=ids_array)
        final_paths.append((partial_path, final_path))

    if corrente is not None:
        directory = config.results_dir / "corrente"
        directory.mkdir(parents=True, exist_ok=True)
        final_path = directory / f"{experiment_id}_{class_name.lower()}_corrente.npz"
        partial_path = final_path.with_suffix(".npz.part")
        with partial_path.open("wb") as handle:
            np.savez(handle, tempo_ms=tempo_ms, corrente_pu=corrente, classe=class_name, id_captura=ids_array)
        final_paths.append((partial_path, final_path))

    metadata_dir = config.results_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_final = metadata_dir / f"{experiment_id}_{class_name.lower()}.jsonl"
    metadata_partial = metadata_final.with_suffix(".jsonl.part")
    with metadata_partial.open("w", encoding="utf-8") as handle:
        for registro in metadados:
            handle.write(json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n")

    for partial_path, final_path in final_paths:
        os.replace(partial_path, final_path)
    os.replace(metadata_partial, metadata_final)


def tempo(config) -> np.ndarray:
    return np.arange(config.points, dtype=np.float64) / config.fs_hz


def janela(t: np.ndarray, inicio_s: float, duracao_s: float) -> np.ndarray:
    return (t >= inicio_s) & (t < inicio_s + duracao_s)


def onda_com_harmonicos(t: np.ndarray, thd_fracao: float, *, frequencia_hz: float) -> np.ndarray:
    # A soma quadrática dos coeficientes é exatamente o THD solicitado.
    ratios = np.array([0.60, 0.30, 0.10], dtype=np.float64)
    coeficientes = thd_fracao * ratios / np.linalg.norm(ratios)
    w = 2.0 * np.pi * frequencia_hz
    return (
        np.sin(w * t)
        + coeficientes[0] * np.sin(3.0 * w * t)
        + coeficientes[1] * np.sin(5.0 * w * t)
        + coeficientes[2] * np.sin(7.0 * w * t)
    )


def aplicar_entalhes(
    sinal: np.ndarray,
    t: np.ndarray,
    rng: np.random.Generator,
    *,
    frequencia_hz: float,
    inicio_s: float = 0.060,
    duracao_s: float = 0.080,
) -> int:
    ciclo_s = 1.0 / frequencia_hz
    largura_pulso_s = 0.0001
    ciclos_afetados = int(round(duracao_s / ciclo_s))
    total_pulsos = 0
    for ciclo in range(ciclos_afetados):
        inicio_ciclo = inicio_s + ciclo * ciclo_s
        n_pulsos = int(rng.integers(2, 5))
        picos = (inicio_ciclo + ciclo_s / 4.0, inicio_ciclo + 3.0 * ciclo_s / 4.0)
        for pulso in range(n_pulsos):
            centro = picos[pulso % 2] + rng.uniform(-0.00035, 0.00035)
            mask = np.abs(t - centro) < largura_pulso_s / 2.0
            if not np.any(mask):
                mask[np.argmin(np.abs(t - centro))] = True
            sinal[mask] = 0.0
            total_pulsos += 1
    return total_pulsos


def oscilacao_amortecida(
    t: np.ndarray,
    *,
    inicio_s: float,
    duracao_s: float,
    frequencia_hz: float,
    amplitude_pu: float = 0.3,
    tau_s: float = 0.005,
) -> np.ndarray:
    resultado = np.zeros_like(t)
    mask = janela(t, inicio_s, duracao_s)
    t_relativo = t[mask] - inicio_s
    resultado[mask] = (
        amplitude_pu * np.sin(2.0 * np.pi * frequencia_hz * t_relativo) * np.exp(-t_relativo / tau_s)
    )
    return resultado


def ruido_awgn(sinal: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    sinal = np.asarray(sinal, dtype=np.float64)
    potencia = float(np.mean(np.square(sinal)))
    if potencia <= 0 or not np.isfinite(potencia):
        raise ValueError("Não é possível aplicar SNR a um sinal sem potência finita")
    potencia_ruido = potencia / (10.0 ** (snr_db / 10.0))
    return sinal + rng.normal(0.0, math.sqrt(potencia_ruido), size=sinal.shape)


def snr_medida(limpo: np.ndarray, ruidoso: np.ndarray) -> float:
    potencia_sinal = float(np.mean(np.square(limpo)))
    potencia_ruido = float(np.mean(np.square(ruidoso - limpo)))
    return 10.0 * math.log10(potencia_sinal / potencia_ruido)


def _validar_captura(config, time_s: np.ndarray, voltage_pu: np.ndarray) -> None:
    if time_s.shape != (config.points,) or voltage_pu.shape != (config.points,):
        raise ValueError(
            f"Captura deve ter {config.points} pontos; recebido {time_s.size}/{voltage_pu.size}"
        )
    if not np.all(np.isfinite(time_s)) or not np.all(np.isfinite(voltage_pu)):
        raise ValueError("Captura contém NaN ou infinito")
    incrementos = np.diff(time_s)
    incremento_esperado = 1.0 / config.fs_hz
    if not np.allclose(incrementos, incremento_esperado, rtol=0, atol=1e-9):
        raise ValueError(f"Eixo temporal não corresponde a {config.fs_hz:.0f} Sa/s")


def _adquirir_real(
    fonte, osc, config, voltage_pu_limpo: np.ndarray, parametros: Dict[str, float]
) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
    expected_peak_v = float(np.max(np.abs(voltage_pu_limpo))) * config.base_voltage_rms * math.sqrt(2.0)
    fonte.program_capture(
        voltage_pu_limpo,
        base_voltage_rms=config.base_voltage_rms,
        frequency_hz=config.grid_frequency_hz,
        dc_offset_pu=float(parametros.get("dc_offset_pu", 0.0)),
    )
    # Margem de headroom de 25% sobre o pico programado (arredondamento do
    # firmware, sobremodulação de classes como FLICKER/SWELL, overshoot de
    # transitórios rápidos). Para transitórios de alto fator de crista (>3x o
    # pico nominal) a margem sobe para 60%.
    programmed_peak_v = max(
        expected_peak_v, float(getattr(fonte, "last_programmed_peak_v", expected_peak_v))
    )
    nominal_peak_v = config.base_voltage_rms * math.sqrt(2.0)
    headroom = 1.60 if programmed_peak_v > 3.0 * nominal_peak_v else 1.25
    osc.set_vertical_scale(1, max(programmed_peak_v * headroom, config.base_voltage_rms * 0.1))

    osc.arm()
    osc.wait_for_armed()
    fonte.arm_transient()
    fonte.trigger()
    osc.wait_for_trigger_complete(timeout_s=5.0)
    fonte.wait_transient_complete(timeout_s=5.0)

    time_s, voltage_v = osc.get_waveform(1, expected_points=config.points)
    voltage_pu = voltage_v / (config.base_voltage_rms * math.sqrt(2.0))
    current_values = None
    if config.capture_current:
        current_time, current_a = osc.get_waveform(2, expected_points=config.points)
        if not np.allclose(current_time, time_s, rtol=0, atol=1e-9):
            raise RuntimeError("CH1 e CH2 possuem eixos temporais diferentes")
        current_values = current_a / float(config.current_base_a)
    return time_s, voltage_pu, current_values


def executar_classe_waveform(
    config,
    fonte,
    osc,
    experiment_id: str,
    class_name: str,
    gerar: Callable[[np.ndarray, float, int, np.random.Generator], Tuple[np.ndarray, Dict[str, float]]],
    *,
    pre_trigger_s: float = 0.0,
) -> None:
    """Executa uma classe completa via TRACe/LIST (forma de onda arbitrária).

    ``gerar(t, f0, capture_index, rng) -> (tensao_pu, parametros)`` define a
    fórmula daquela classe; esta função cuida do genérico: laço de capturas,
    aquisição real/simulada, ruído AWGN e gravação em .npz.
    """
    simulated = osc is None
    total = config.capturas(simulated)
    logger.info(
        "[%s] %s: %d capturas, SNR=%s dB, modo=%s",
        experiment_id, class_name, total, config.snr_levels_db,
        "SIMULADO" if simulated else "BANCADA",
    )
    if not simulated:
        osc.configure_acquisition(
            sample_rate_hz=config.fs_hz,
            points=config.points,
            duration_s=config.duration_s,
            pre_trigger_s=pre_trigger_s,
        )

    t = tempo(config)
    tensao_por_snr: Dict[float, np.ndarray] = {
        snr_db: np.empty((total, config.points), dtype=np.float64) for snr_db in config.snr_levels_db
    }
    corrente = np.empty((total, config.points), dtype=np.float64) if config.capture_current else None
    ids: List[str] = []
    metadados: List[dict] = []
    tempo_ms_eixo = None

    for capture_index in range(total):
        seed = config.base_seed + int(experiment_id) * 1_000_000 + capture_index
        rng = np.random.default_rng(seed)
        voltage_pu, parametros = gerar(t, config.grid_frequency_hz, capture_index, rng)
        voltage_pu = np.asarray(voltage_pu, dtype=np.float64)
        if voltage_pu.shape != (config.points,) or not np.all(np.isfinite(voltage_pu)):
            raise RuntimeError(f"gerar() do experimento {experiment_id} produziu forma inválida")

        if simulated:
            time_s = t
            measured_voltage_pu = voltage_pu
            measured_current_pu = (
                0.8 * np.sin(2.0 * np.pi * config.grid_frequency_hz * t - 0.2)
                if config.capture_current else None
            )
        else:
            time_s, measured_voltage_pu, measured_current_pu = _adquirir_real(
                fonte, osc, config, voltage_pu, parametros,
            )
        _validar_captura(config, time_s, measured_voltage_pu)
        tempo_ms_eixo = time_s * 1000.0
        capture_id = f"{experiment_id}-{capture_index + 1:04d}"
        ids.append(capture_id)

        medidas_snr = {}
        for snr_db in config.snr_levels_db:
            noise_seed = seed + int(round(snr_db * 1000.0)) + 50_000_000
            ruidoso = ruido_awgn(measured_voltage_pu, snr_db, np.random.default_rng(noise_seed))
            tensao_por_snr[snr_db][capture_index] = ruidoso
            medidas_snr[str(snr_db)] = snr_medida(measured_voltage_pu, ruidoso)

        if corrente is not None and measured_current_pu is not None:
            corrente[capture_index] = measured_current_pu

        metadados.append({
            "id_captura": capture_id,
            "classe": class_name,
            "seed": seed,
            "simulado": simulated,
            "fs_hz": config.fs_hz,
            "pontos": config.points,
            "parametros": parametros,
            "snr_medido_db": medidas_snr,
        })
        if not simulated:
            logger.info("[%s] captura %d/%d concluída", experiment_id, capture_index + 1, total)

    salvar_classe(
        config, experiment_id, class_name,
        tempo_ms=tempo_ms_eixo, tensao_por_snr=tensao_por_snr, ids=ids,
        corrente=corrente, metadados=metadados,
    )
    logger.info("[%s] classe concluída: %s", experiment_id, class_name)
