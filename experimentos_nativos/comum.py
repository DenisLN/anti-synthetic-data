"""Helpers dos experimentos que usam transiente nativo da AMETEK (PULSe/LIST/CSINe).

Autocontido: não importa mestre.py. Tudo que precisa chega por parâmetro (o
``config`` que mestre.py monta uma vez e repassa para cada ``run(fonte, osc, config)``).

Todo experimento (nativo ou waveform) precisa de um ``gerar()`` porque o dataset
sintético de verdade (milhares de capturas por classe) vem do modo SIMULADO —
sem osciloscópio, sem tocar a AMETEK — não da bancada real, que só produz uma
captura por classe para comissionamento (ver REAL_CAPTURES_PER_CLASS). Na
bancada real, ``configurar()`` é quem manda os comandos SCPI nativos.
"""

from __future__ import annotations

import json
import logging
import math
import os
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("ExperimentosNativos")


def janela(t: np.ndarray, inicio_s: float, duracao_s: float) -> np.ndarray:
    return (t >= inicio_s) & (t < inicio_s + duracao_s)


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

    Escrita atômica: grava em ``.part`` e só promove pro nome final depois que
    tudo terminou sem erro.
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
    fonte, osc, config, configurar: Callable, capture_index: int,
    *, gerar: Optional[Callable] = None, t: Optional[np.ndarray] = None,
    rng: Optional[np.random.Generator] = None, scope_scale_v: Optional[float] = None,
) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], Dict[str, float]]:
    if gerar is not None:
        # Índice que precisa de forma de onda arbitrária (TRACe), não de um
        # transiente nativo (ex.: THD acima do teto do CSINe). Usa o mesmo
        # gerar() do modo simulado e sobe via program_capture/arm_transient,
        # em vez de configurar()/arm().
        voltage_pu, parametros = gerar(t, config.grid_frequency_hz, capture_index, rng)
        voltage_pu = np.asarray(voltage_pu, dtype=np.float64)
        if scope_scale_v is not None:
            osc.set_vertical_scale(1, scope_scale_v)
        fonte.program_capture(
            voltage_pu, base_voltage_rms=config.base_voltage_rms,
            frequency_hz=config.grid_frequency_hz,
        )
        fonte.arm_transient()
    else:
        parametros = configurar(fonte, config, capture_index)
        fonte.arm()
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
    return time_s, voltage_pu, current_values, parametros


def executar_classe_nativa(
    config,
    fonte,
    osc,
    experiment_id: str,
    class_name: str,
    gerar: Callable[[np.ndarray, float, int, np.random.Generator], Tuple[np.ndarray, Dict[str, float]]],
    configurar: Callable[[object, object, int], Dict[str, float]],
    *,
    pre_trigger_s: float = 0.0,
    scope_scale_v: Optional[float] = None,
    usar_trace: Optional[Callable[[int], bool]] = None,
) -> None:
    """Executa uma classe completa via transiente nativo (PULSe/LIST/CSINe).

    ``gerar`` produz a captura no modo SIMULADO (dataset sintético, sem
    hardware). ``configurar`` manda os comandos SCPI nativos na bancada real
    e devolve os parâmetros físicos daquela captura (ex.: nível de sag).

    ``usar_trace(capture_index) -> bool`` é opcional: para classes de
    mecanismo misto (ex.: HARMONICS com um nível de THD acima do teto do
    CSINe), sinaliza que aquele índice específico deve usar ``gerar()`` +
    TRACe (``program_capture``/``arm_transient``) mesmo na bancada real, em
    vez de ``configurar()``/``arm()``.
    """
    simulated = osc is None
    total = config.capturas(simulated)
    logger.info(
        "[%s] %s: %d capturas, SNR=%s dB, modo=%s",
        experiment_id, class_name, total, config.snr_levels_db,
        "SIMULADO" if simulated else "BANCADA",
    )
    t = np.arange(config.points, dtype=np.float64) / config.fs_hz
    if not simulated:
        osc.configure_acquisition(
            sample_rate_hz=config.fs_hz,
            points=config.points,
            duration_s=config.duration_s,
            pre_trigger_s=pre_trigger_s,
        )
        if scope_scale_v is not None:
            osc.set_vertical_scale(1, scope_scale_v)

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

        if simulated:
            voltage_pu, parametros = gerar(t, config.grid_frequency_hz, capture_index, rng)
            voltage_pu = np.asarray(voltage_pu, dtype=np.float64)
            if voltage_pu.shape != (config.points,) or not np.all(np.isfinite(voltage_pu)):
                raise RuntimeError(f"gerar() do experimento {experiment_id} produziu forma inválida")
            time_s = t
            measured_voltage_pu = voltage_pu
            measured_current_pu = (
                0.8 * np.sin(2.0 * np.pi * config.grid_frequency_hz * t - 0.2)
                if config.capture_current else None
            )
        else:
            precisa_trace = usar_trace is not None and usar_trace(capture_index)
            time_s, measured_voltage_pu, measured_current_pu, parametros = _adquirir_real(
                fonte, osc, config, configurar, capture_index,
                gerar=gerar if precisa_trace else None,
                t=t if precisa_trace else None,
                rng=rng if precisa_trace else None,
                scope_scale_v=scope_scale_v if precisa_trace else None,
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
