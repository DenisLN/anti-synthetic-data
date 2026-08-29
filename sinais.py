"""Matemática de sinal pura, compartilhada por todos os experimentos.

Sem dependência de ``config``/fonte/osciloscópio — só array in, array out.
Usada tanto por ``gerar()`` (dataset simulado) quanto pela execução real via
as classes de ``mestre.py``.
"""

from __future__ import annotations

import math

import numpy as np


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
