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


def envelope_rms_meio_ciclo(x: np.ndarray, *, fs_hz: float, f0: float) -> np.ndarray:
    """Rms de cada meio ciclo da onda — o "envelope" que revela sag, swell,
    interrupção e flicker sem depender de alinhamento nem de fase.

    Meio ciclo (e não ciclo inteiro) porque os distúrbios das classes 02/03/04
    duram 60 ms e precisam ser vistos com resolução melhor que um período."""
    x = np.asarray(x, dtype=np.float64)
    n = int(round(fs_hz / (2.0 * f0)))
    if n < 2 or x.size < n:
        raise ValueError(f"Registro curto demais para um meio ciclo ({x.size} amostras, n={n})")
    blocos = x[: (x.size // n) * n].reshape(-1, n)
    return np.sqrt(np.mean(np.square(blocos), axis=1))


def fator_de_crista_do_ciclo_mediano(x: np.ndarray, *, fs_hz: float, f0: float) -> float:
    """Pico/rms de UM ciclo em regime (o ciclo cujo rms está mais perto da
    mediana do envelope).

    É a sonda de FORMA de onda: uma senoide limpa dá 1,414; a senoide clipada
    do CSINe dá menos. Medido no ciclo mediano e não no registro inteiro para
    não depender de quanto de margem/evento o registro carrega — a classe 05
    da sessão 1 mediu 1,459 (senoide limpa) onde a referência de 09/09 media
    1,344 (clipada), diferença de 8,6% que este número pega."""
    x = np.asarray(x, dtype=np.float64)
    envelope = envelope_rms_meio_ciclo(x, fs_hz=fs_hz, f0=f0)
    n = int(round(fs_hz / (2.0 * f0)))
    alvo = float(np.median(envelope))
    bloco = int(np.argmin(np.abs(envelope - alvo)))
    inicio = bloco * n
    ciclo = x[inicio : inicio + 2 * n]
    if ciclo.size < 2 * n:
        ciclo = x[max(0, x.size - 2 * n):]
    rms = float(np.sqrt(np.mean(np.square(ciclo))))
    if rms <= 1e-12:
        return 0.0
    return float(np.max(np.abs(ciclo))) / rms


def thd_medida(x: np.ndarray, *, fs_hz: float, f0: float, max_harmonica: int = 40) -> float:
    """THD (fração, não %) por FFT sobre um número INTEIRO de ciclos.

    Sonda de conteúdo harmônico — a única com sensibilidade para separar a
    senoide clipada do CSINe a 5% (THD 5,05% na referência de 2026-09-09)
    da senoide limpa que a sessão 1 gravou no lugar dela (THD 0,98%). O
    fator de crista sozinho só difere 5% entre os dois casos, dentro do
    espalhamento de uma medida real."""
    x = np.asarray(x, dtype=np.float64)
    amostras_por_ciclo = fs_hz / f0
    ciclos = int(x.size // amostras_por_ciclo)
    if ciclos < 2:
        raise ValueError("THD exige pelo menos 2 ciclos completos")
    n = int(round(ciclos * amostras_por_ciclo))
    janela_inteira = x[:n] - np.mean(x[:n])
    espectro = np.abs(np.fft.rfft(janela_inteira))
    fundamental = espectro[ciclos]
    if fundamental <= 1e-12:
        return 0.0
    harmonicas = [
        espectro[ciclos * ordem]
        for ordem in range(2, max_harmonica + 1)
        if ciclos * ordem < espectro.size
    ]
    return float(np.sqrt(np.sum(np.square(harmonicas))) / fundamental)


def comparar_fisicamente(
    esperado: np.ndarray,
    capturado: np.ndarray,
    *,
    fs_hz: float,
    f0: float,
    tol_envelope: float = 0.15,
    tol_crista: float = 0.10,
    tol_thd: float = 0.20,
    piso_thd: float = 0.01,
) -> dict:
    """Confere se a captura FÍSICA corresponde à forma que a classe pediu.

    Independente do MECANISMO: não importa por que a fonte não aplicou o valor
    (erro 19, INIT ignorado, lista residual, firmware) — se o que saiu não é o
    que foi pedido, a captura é marcada. Três sondas, todas insensíveis a
    alinhamento e a quanto de margem o registro tem:

    * **mediana do envelope** — nível de regime. Pega a sessão inteira a
      127 V onde 220 V foram programados (razão 0,578).
    * **mínimo e máximo do envelope** — profundidade/altura do evento. Pega
      SAG que não aconteceu (mínimo 0,707 onde se esperava 0,07) e
      interrupção que virou elevação (máximo 0,78 onde se esperava 0,707).
    * **THD do registro** — conteúdo harmônico. Pega a CSINe que não foi
      aplicada (5,05% de referência contra 0,98% medidos na sessão 1). O
      ``piso_thd`` de 1% absorve quantização do osciloscópio, então uma
      classe sem harmônicos programados nunca é reprovada por ruído.
    * **fator de crista do ciclo mediano** — forma de onda grosseira
      (complementa a THD; tolerância folgada de propósito).

    Devolve ``{"ok": bool, "motivos": [...], ...}``; nunca levanta por
    divergência (quem chama decide), só por registro curto demais."""
    esperado = np.asarray(esperado, dtype=np.float64)
    capturado = np.asarray(capturado, dtype=np.float64)
    env_esperado = envelope_rms_meio_ciclo(esperado, fs_hz=fs_hz, f0=f0)
    env_capturado = envelope_rms_meio_ciclo(capturado, fs_hz=fs_hz, f0=f0)
    mediana_esperada = float(np.median(env_esperado))
    # Piso absoluto: para interrupção o mínimo esperado é ~0 e uma tolerância
    # puramente relativa seria impossível de satisfazer (ou de violar).
    piso = max(0.05 * mediana_esperada, 1e-6)

    medidas = {
        "mediana": (float(np.median(env_capturado)), mediana_esperada),
        "mínimo": (float(np.min(env_capturado)), float(np.min(env_esperado))),
        "máximo": (float(np.max(env_capturado)), float(np.max(env_esperado))),
    }
    motivos = []
    for nome, (medido, alvo) in medidas.items():
        limite = max(tol_envelope * abs(alvo), piso)
        if abs(medido - alvo) > limite:
            motivos.append(
                f"{nome} do envelope: medido {medido:.4f} pu, esperado {alvo:.4f} pu "
                f"(tolerância {limite:.4f})"
            )
    thd_esperada = thd_medida(esperado, fs_hz=fs_hz, f0=f0)
    thd_obtida = thd_medida(capturado, fs_hz=fs_hz, f0=f0)
    limite_thd = max(tol_thd * thd_esperada, piso_thd)
    if abs(thd_obtida - thd_esperada) > limite_thd:
        motivos.append(
            f"THD: medida {thd_obtida:.2%}, esperada {thd_esperada:.2%} "
            f"(tolerância {limite_thd:.2%})"
        )
    crista_esperada = fator_de_crista_do_ciclo_mediano(esperado, fs_hz=fs_hz, f0=f0)
    crista_medida = fator_de_crista_do_ciclo_mediano(capturado, fs_hz=fs_hz, f0=f0)
    if crista_esperada > 0 and abs(crista_medida - crista_esperada) > tol_crista * crista_esperada:
        motivos.append(
            f"fator de crista: medido {crista_medida:.4f}, esperado {crista_esperada:.4f} "
            f"(tolerância relativa {tol_crista:.2%})"
        )
    return {
        "ok": not motivos,
        "motivos": motivos,
        "envelope_mediana_medida": medidas["mediana"][0],
        "envelope_mediana_esperada": medidas["mediana"][1],
        "envelope_minimo_medido": medidas["mínimo"][0],
        "envelope_minimo_esperado": medidas["mínimo"][1],
        "envelope_maximo_medido": medidas["máximo"][0],
        "envelope_maximo_esperado": medidas["máximo"][1],
        "crista_medida": crista_medida,
        "crista_esperada": crista_esperada,
        "thd_medida": thd_obtida,
        "thd_esperada": thd_esperada,
    }
