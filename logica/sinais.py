"""Matemática de sinal pura, compartilhada por todos os experimentos.

Sem dependência de ``config``/fonte/osciloscópio — só array in, array out.
Usada tanto por ``gerar()`` (dataset simulado) quanto pela execução real via
as classes de ``mestre.py``.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, Optional, Tuple

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


def aplicar_entalhes_continuos(
    sinal: np.ndarray,
    t: np.ndarray,
    rng: np.random.Generator,
    *,
    frequencia_hz: float,
    origem_s: float,
) -> int:
    """Entalhes periódicos e contínuos (IEEE 1159-2019, 4.4.5.4): a MESMA
    regra de ``aplicar_entalhes`` (2 a 4 pulsos de 0,1 ms por ciclo, nos dois
    picos, com jitter de ±0,35 ms), mas em TODOS os ciclos da janela.

    ``origem_s``: instante em que a senoide cruza zero subindo (``-tau`` de
    ``Sorteio.deslocamento_s``); os picos ficam em ``origem + k T + T/4`` e
    ``+ 3T/4``. Ciclos que começam antes de ``t[0]`` ou terminam depois de
    ``t[-1]`` entram só com os pulsos cujo centro cai dentro da janela (o
    ``rng`` é consumido igual, para a forma não depender de onde a janela
    corta). Devolve quantos pulsos caíram na janela."""
    ciclo_s = 1.0 / frequencia_hz
    largura_pulso_s = 0.0001
    primeiro = int(math.floor((float(t[0]) - origem_s) / ciclo_s))
    ultimo = int(math.ceil((float(t[-1]) - origem_s) / ciclo_s))
    total_pulsos = 0
    for ciclo in range(primeiro, ultimo + 1):
        inicio_ciclo = origem_s + ciclo * ciclo_s
        n_pulsos = int(rng.integers(2, 5))
        picos = (inicio_ciclo + ciclo_s / 4.0, inicio_ciclo + 3.0 * ciclo_s / 4.0)
        for pulso in range(n_pulsos):
            centro = picos[pulso % 2] + rng.uniform(-0.00035, 0.00035)
            if not float(t[0]) <= centro <= float(t[-1]):
                continue
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


# Ruído aplicado SÓ na janela rotulada (v1.15; a margem de captura não pertence
# ao rótulo):
# potência de referência = mean(janela**2); as margens de captura (20 ms antes,
# 50 ms depois) não entram no arquivo com ruído.
SEMENTE_BASE_RUIDO = 50_000_000
MINIMO_AMOSTRAS_RUIDO_BANCADA = 100
# Identificador textual da fórmula de semente_do_ruido, gravado em
# ruido_janela.formula_semente (rastreabilidade; não é lido por código).
FORMULA_SEMENTE_RUIDO = "seed + round(snr_db*1000) + 50000000"


def semente_do_ruido(seed: int, snr_db: float) -> int:
    """Seed do AWGN de um nível: a fórmula de sempre (uma só definição, usada
    pela bancada e pelo script offline)."""
    return int(seed) + int(round(float(snr_db) * 1000.0)) + SEMENTE_BASE_RUIDO


def potencia_ruido_segunda_diferenca(x: np.ndarray) -> float:
    """Potência do ruído branco de ``x`` pela segunda diferença
    ``x[n] - 2 x[n+1] + x[n+2]``: variância 6 sigma^2 para ruído branco, e a
    senoide de 50/60 Hz a 30 kSa/s (600/500 amostras por ciclo) contribui
    ~1e-4 pu, desprezível ao lado de 6e-3..1,5e-2 pu de ruído. Por isso mede o
    ruído da bancada tanto numa margem em zero (classes TRACe) quanto numa
    margem em que a fonte ainda emite a senoide (classes nativas), sem ajuste
    de fase/frequência, e ignora o offset DC do osciloscópio."""
    x = np.asarray(x, dtype=np.float64)
    if x.size < 3:
        raise ValueError("segunda diferença exige ao menos 3 amostras")
    d2 = x[:-2] - 2.0 * x[1:-1] + x[2:]
    return float(np.mean(np.square(d2)) / 6.0)


def medir_ruido_da_bancada(
    registro: np.ndarray, inicio: int, pontos: int, *, minimo_amostras: int = MINIMO_AMOSTRAS_RUIDO_BANCADA,
) -> Optional[Dict[str, object]]:
    """Ruído próprio da bancada num registro com margens, na margem ANTERIOR à
    janela (``registro[:inicio]``) ou, se ela tiver menos de ``minimo_amostras``,
    na posterior (``registro[inicio + pontos:]``). ``None`` sem margem
    utilizável. SNR da bancada = potência de referência da janela / potência
    do ruído medida."""
    registro = np.asarray(registro, dtype=np.float64)
    inicio, pontos = int(inicio), int(pontos)
    potencia_ref = float(np.mean(np.square(registro[inicio : inicio + pontos])))
    anterior, posterior = registro[:inicio], registro[inicio + pontos:]
    if anterior.size >= minimo_amostras:
        margem, trecho = "anterior", anterior
    elif posterior.size >= minimo_amostras:
        margem, trecho = "posterior", posterior
    else:
        return None
    potencia_ruido = potencia_ruido_segunda_diferenca(trecho)
    if potencia_ruido <= 0 or potencia_ref <= 0:
        return None
    return {
        "metodo": "segunda_diferenca",
        "margem": margem,
        "amostras": int(trecho.size),
        "ruido_rms_pu": math.sqrt(potencia_ruido),
        "media_da_margem_pu": float(np.mean(trecho)),
        "snr_db": 10.0 * math.log10(potencia_ref / potencia_ruido),
        "_potencia_ruido_pu2": potencia_ruido,
    }


def ruido_na_janela(
    registro: np.ndarray, inicio: int, pontos: int, niveis_db: Iterable[float], seed: int,
    *, simulado: bool = False,
) -> Dict[str, object]:
    """AWGN de cada nível em ``registro[inicio : inicio + pontos]`` (a janela
    rotulada) e os três SNRs a gravar no metadata:

    * ``snr_medido_db``  : SNR ACRESCENTADO por nível (janela limpa contra ruído somado);
    * ``snr_bancada_db`` : SNR do ruído próprio da bancada (``None`` no simulado
      ou sem margem utilizável);
    * ``snr_efetivo_db`` : sinal / (ruído da bancada + ruído acrescentado),
      potências somadas (independentes); sem bancada, igual ao acrescentado.

    Devolve ``{"janelas": {snr_db: array(pontos)}, "metadata": {...}}``."""
    registro = np.asarray(registro, dtype=np.float64)
    inicio, pontos = int(inicio), int(pontos)
    limpa = registro[inicio : inicio + pontos]
    if limpa.size != pontos:
        raise ValueError(f"janela [{inicio}, {inicio + pontos}) fora do registro de {registro.size} amostras")
    potencia_ref = float(np.mean(np.square(limpa)))
    bancada = None if simulado else medir_ruido_da_bancada(registro, inicio, pontos)
    janelas: Dict[float, np.ndarray] = {}
    acrescentado: Dict[str, float] = {}
    efetivo: Dict[str, float] = {}
    sementes: Dict[str, int] = {}
    for snr_db in niveis_db:
        # Mesmo sorteio da seed, mas escalado para a potência EXATA
        # P_ref / 10**(snr/10) na janela: o SNR acrescentado é o nominal por
        # construção (e não só em esperança, como em ruido_awgn).
        semente = semente_do_ruido(seed, snr_db)
        sementes[str(snr_db)] = semente
        ruido = np.random.default_rng(semente).normal(0.0, 1.0, size=limpa.shape)
        ruido *= math.sqrt(potencia_ref / (10.0 ** (snr_db / 10.0)) / float(np.mean(np.square(ruido))))
        ruidosa = limpa + ruido
        janelas[snr_db] = ruidosa
        acrescentado[str(snr_db)] = snr_medida(limpa, ruidosa)
        potencia_add = float(np.mean(np.square(ruidosa - limpa)))
        potencia_total = potencia_add + (bancada["_potencia_ruido_pu2"] if bancada else 0.0)
        efetivo[str(snr_db)] = 10.0 * math.log10(potencia_ref / potencia_total)
    detalhe_bancada = None if bancada is None else {k: v for k, v in bancada.items() if not k.startswith("_")}
    return {
        "janelas": janelas,
        "metadata": {
            "snr_medido_db": acrescentado,
            "snr_bancada_db": None if bancada is None else bancada["snr_db"],
            "snr_efetivo_db": efetivo,
            "ruido_janela": {
                "inicio_janela": inicio,
                "amostras": pontos,
                "potencia_referencia_pu2": potencia_ref,
                "margens_com_ruido": False,
                "bancada": detalhe_bancada,
                # Semente de cada nível (chave = snr_medido_db) e a fórmula
                # que a produz: reproduz o vetor de ruído sem o código de hoje.
                "sementes_por_snr_db": sementes,
                "formula_semente": FORMULA_SEMENTE_RUIDO,
            },
        },
    }


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
    """Mediana, sobre todos os ciclos completos do registro, do pico/rms de
    cada ciclo — o fator de crista da forma de onda em REGIME.

    É a sonda de FORMA de onda: uma senoide limpa dá 1,414; a senoide clipada
    do CSINe dá menos em TODO ciclo. Não é medido no registro inteiro para
    não depender de quanto de margem/evento o registro carrega — a classe 05
    da sessão 1 mediu 1,459 (senoide limpa) onde a referência de 09/09 media
    1,344 (clipada), diferença de 8,6% que este número pega.

    Antes usava UM ciclo: o que começava no meio ciclo de rms mais perto da
    mediana do envelope. Numa classe impulsiva esse ciclo pode ser justamente
    o do evento (uma oscilação de 2 ms quase não muda o rms, mas muda o
    pico): run04 de 2026-09-30 mediu 1,62 (09) e 1,71 (17) contra 1,414, e a
    mediana por ciclo dá 1,43/1,44. Um evento curto afeta 1-2 ciclos e não
    move a mediana; um clipping aplicado move todos."""
    x = np.asarray(x, dtype=np.float64)
    n = int(round(fs_hz / f0))
    ciclos = x.size // n
    if ciclos < 1:
        raise ValueError(f"Registro curto demais para um ciclo ({x.size} amostras, n={n})")
    blocos = x[: ciclos * n].reshape(ciclos, n)
    rms = np.sqrt(np.mean(np.square(blocos), axis=1))
    validos = rms > 1e-12
    if not np.any(validos):
        return 0.0
    cristas = np.max(np.abs(blocos[validos]), axis=1) / rms[validos]
    return float(np.median(cristas))


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
    fator_crista: float = 1.0,
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
      (complementa a THD; tolerância folgada de propósito). ``fator_crista``
      (>= 1; v1.15, fator de extremo calibrado da classe): a fonte pode tocar
      nos degraus/entalhes e elevar o pico do ciclo mediano até ``fator`` ×
      o do modelo; a comparação é BILATERAL e aceita
      ``[crista_modelo × (1 − tol), crista_modelo × fator × (1 + tol)]``. Com
      ``fator_crista = 1`` é a comparação simétrica de sempre.

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
    fator_crista = max(1.0, float(fator_crista))
    crista_minima = crista_esperada * (1.0 - tol_crista)
    crista_maxima = crista_esperada * fator_crista * (1.0 + tol_crista)
    if crista_esperada > 0 and not (crista_minima <= crista_medida <= crista_maxima):
        motivos.append(
            f"fator de crista: medido {crista_medida:.4f}, esperado {crista_esperada:.4f}"
            + (f" × fator de extremo {fator_crista:.3f}" if fator_crista > 1.0 else "")
            + f" (aceito de {crista_minima:.4f} a {crista_maxima:.4f}; tolerância relativa {tol_crista:.2%})"
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
        "crista_modelo": crista_esperada,
        "fator_extremo_crista": fator_crista,
        "crista_minima_aceita": crista_minima,
        "crista_maxima_aceita": crista_maxima,
        "thd_medida": thd_obtida,
        "thd_esperada": thd_esperada,
    }


def janela_nominal(
    registro: np.ndarray, *, indice_trigger: int, pre_trigger_s: float, pontos: int, fs_hz: float,
) -> np.ndarray:
    """Recorta do registro bruto a janela NOMINAL de ``pontos`` amostras, a
    mesma base de tempo que ``gerar()`` usa.

    O trigger cai em ``indice_trigger`` (lido de ``x_origin``, ver
    ``oscilloscope_orm.get_waveform``) e as classes com ``pre_trigger_s > 0``
    (02/03/04, PULSe) querem o evento em ``pre_trigger_s`` dentro da janela —
    por isso o recorte começa ANTES do trigger nessas classes.

    Antes, o recorte usava ``margem_amostras_antes`` como se fosse o índice do
    trigger; com ``REFerence LEFT`` o trigger caía uma divisão adiante e todo
    recorte errava por ``janela/10`` (H-REF10, relatório 01 §1.1)."""
    registro = np.asarray(registro, dtype=np.float64)
    inicio = int(round(indice_trigger - pre_trigger_s * fs_hz))
    inicio = max(0, min(inicio, max(0, registro.size - pontos)))
    return registro[inicio : inicio + pontos]


# Abaixo disto (rms do resíduo ESPERADO, em pu) não há "componente de
# distúrbio" a correlacionar: a classe 01 dá ~1e-16 (arredondamento de ponto
# flutuante); a menor classe com distúrbio real fica ordens de grandeza acima.
LIMITE_RESIDUO_DEGENERADO_PU = 1e-6


def distancia_modelo_programada(
    modelo_pu: np.ndarray, programada_pu: np.ndarray, *, pontos_por_ciclo: int,
) -> Dict[str, object]:
    """Distância modelo -> programada (P-09, item d), em pu do pico nominal:
    ``erro_rms_pu`` e ``erro_maximo_pu`` de ``programada - modelo``; a média
    perdida por ciclo (média do modelo menos a da programada, em ciclos de
    ``pontos_por_ciclo`` amostras) e o seu máximo absoluto; e o salto de pico
    absoluto (``max|programada| - max|modelo|``). Mesmas contas de
    ``scripts/analisar_modelo_programado.analisar_forma``. Exige as duas
    formas do mesmo tamanho, múltiplo de ``pontos_por_ciclo``."""
    modelo = np.asarray(modelo_pu, dtype=np.float64)
    programada = np.asarray(programada_pu, dtype=np.float64)
    n = int(pontos_por_ciclo)
    if modelo.shape != programada.shape or modelo.ndim != 1 or n < 1 or modelo.size % n:
        raise ValueError(
            f"modelo {modelo.shape} e programada {programada.shape} incompatíveis com ciclos de {n} amostras"
        )
    erro = programada - modelo
    media_perdida = np.mean(modelo.reshape(-1, n), axis=1) - np.mean(programada.reshape(-1, n), axis=1)
    return {
        "erro_rms_pu": float(np.sqrt(np.mean(erro ** 2))),
        "erro_maximo_pu": float(np.max(np.abs(erro))),
        "media_perdida_por_ciclo_pu": media_perdida,
        "media_perdida_maxima_absoluta_pu": float(np.max(np.abs(media_perdida))),
        "salto_pico_pu": float(np.max(np.abs(programada)) - np.max(np.abs(modelo))),
    }


def correlacao_disturbio(
    esperado: np.ndarray, capturado: np.ndarray, *, fs_hz: float, f0_hz: float, fase_graus: float = 0.0,
) -> Tuple[Optional[float], Optional[str]]:
    """Correlação de Pearson só da COMPONENTE DE DISTÚRBIO: (capturado -
    senoide nominal) contra (esperado - senoide nominal), com a senoide
    nominal ``sin(2π·f0·t + fase)`` de amplitude 1 pu, a MESMA para os dois
    (mesma f0 e fase do modelo; sem sorteio, fase 0).

    A correlação do sinal inteiro é dominada pela fundamental e passa de 0,99
    contra qualquer senoide; subtraí-la deixa só o que o evento acrescenta.

    ``capturado`` deve vir JÁ ALINHADO com ``esperado`` (mesma grade de tempo,
    mesmo comprimento) — ``analisar_sessao`` faz o alinhamento. Devolve
    ``(valor, None)`` ou ``(None, motivo)`` quando a conta não tem sentido
    (resíduo esperado ~ 0 como na classe 01, constante como o offset DC da 19, ou resíduo capturado constante):
    um número ali seria correlação de ruído de arredondamento."""
    esperado = np.asarray(esperado, dtype=np.float64)
    capturado = np.asarray(capturado, dtype=np.float64)
    if esperado.shape != capturado.shape or esperado.ndim != 1 or esperado.size < 2:
        return None, f"formas incompatíveis ({esperado.shape} x {capturado.shape})"
    t = np.arange(esperado.size, dtype=np.float64) / float(fs_hz)
    senoide = np.sin(2.0 * np.pi * float(f0_hz) * t + math.radians(float(fase_graus)))
    r_esp = esperado - senoide
    r_cap = capturado - senoide
    rms_total = float(np.sqrt(np.mean(np.square(r_esp))))
    if rms_total < LIMITE_RESIDUO_DEGENERADO_PU:
        return None, f"resíduo esperado ~ 0 (rms {rms_total:.2e} pu): sem componente de distúrbio"
    rms_esp = float(np.sqrt(np.mean(np.square(r_esp - np.mean(r_esp)))))
    if rms_esp < LIMITE_RESIDUO_DEGENERADO_PU:
        return None, (f"resíduo esperado constante (rms {rms_total:.2e} pu, sem variação): "
                      "Pearson indefinido (offset DC puro)")
    rms_cap = float(np.sqrt(np.mean(np.square(r_cap - np.mean(r_cap)))))
    if rms_cap == 0.0:
        return None, "resíduo capturado constante"
    a = r_esp - np.mean(r_esp)
    b = r_cap - np.mean(r_cap)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))), None


def _residuo_sem_fundamental(x: np.ndarray, *, fs_hz: float, f0_hz: float) -> np.ndarray:
    """``x`` menos a sua própria fundamental ajustada por mínimos quadrados
    (``a·sin + b·cos`` em ``f0_hz``, o que dá amplitude e fase livres) mais uma
    constante. Projeção linear: ``projeção(k·x) = k·projeção(x)``."""
    t = np.arange(x.size, dtype=np.float64) / float(fs_hz)
    w = 2.0 * np.pi * float(f0_hz) * t
    base = np.column_stack([np.sin(w), np.cos(w), np.ones_like(w)])
    coef, *_ = np.linalg.lstsq(base, x, rcond=None)
    return x - base @ coef


def correlacao_disturbio_fundamental_ajustada(
    esperado: np.ndarray, capturado: np.ndarray, *, fs_hz: float, f0_hz: float,
) -> Tuple[Optional[float], Optional[str]]:
    """Como ``correlacao_disturbio``, mas em vez de subtrair dos dois a MESMA
    senoide nominal de 1 pu, tira de CADA sinal a sua própria fundamental
    (amplitude e fase ajustadas por mínimos quadrados na janela inteira, em
    ``f0_hz``) antes do Pearson dos resíduos.

    Por quê: a fonte emite a fundamental 0,2–1,4 % acima ou abaixo do
    programado e a métrica nominal deixa essa diferença no resíduo capturado;
    em classes de distúrbio pequeno (09, rms 0,0235 pu) isso custa até
    0,05–0,06. Esta variante mede só a FORMA do que sobra, indiferente a erro
    de amplitude/fase da fundamental e de escala.

    Ressalva: o ajuste usa a janela toda, então em distúrbios grandes ou que
    mexem na fundamental (02/03/04, 18) parte do evento é absorvida no ajuste
    (igualmente nos dois sinais). É um complemento, não substituto, da
    ``correlacao_disturbio``.

    Caso degenerado como na métrica nominal: resíduo esperado ~ 0 (classes 01 e
    19, em que só restam fundamental e constante, aqui sem distinguir o offset
    DC porque a constante também é ajustada), resíduo capturado ~ 0 ou formas
    incompatíveis devolvem ``(None, motivo)``."""
    esperado = np.asarray(esperado, dtype=np.float64)
    capturado = np.asarray(capturado, dtype=np.float64)
    if esperado.shape != capturado.shape or esperado.ndim != 1 or esperado.size < 4:
        return None, f"formas incompatíveis ({esperado.shape} x {capturado.shape})"
    a = _residuo_sem_fundamental(esperado, fs_hz=fs_hz, f0_hz=f0_hz)
    b = _residuo_sem_fundamental(capturado, fs_hz=fs_hz, f0_hz=f0_hz)
    rms_esp = float(np.sqrt(np.mean(np.square(a))))
    if rms_esp < LIMITE_RESIDUO_DEGENERADO_PU:
        return None, (f"resíduo esperado sem a fundamental ~ 0 (rms {rms_esp:.2e} pu): "
                      "sem componente de distúrbio (classe 01) ou só offset DC (19)")
    rms_cap = float(np.sqrt(np.mean(np.square(b))))
    if rms_cap < LIMITE_RESIDUO_DEGENERADO_PU:
        return None, "resíduo capturado sem a fundamental ~ 0"
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))), None


# ---------------------------------------------------------------------------
# Forma "programada" das classes NATIVAS (v1.15)
# ---------------------------------------------------------------------------
# Nas classes nativas (01-05, 18, 19) a fonte gera a forma sozinha; o que o
# código programa é um NÍVEL (STEP/PULSe), um THD (CSINe), dois pontos de
# frequência (LIST:FREQuency) ou um offset. A forma "programada" é a ideal para
# esses comandos, na grade da captura: o que o modelo (``gerar()``) pediria se
# a fonte só soubesse fazer o que foi programado (nível truncado em 0,1 V,
# frequência em degraus, senoide clipada no THD pedido).

FORMA_NATIVA_POR_CLASSE = {
    "01": "STEP", "02": "PULSe", "03": "PULSe", "04": "PULSe",
    "05": "CSINe", "18": "LIST:FREQuency", "19": "STEP+OFFSet",
}
_PARAMETRO_DO_NIVEL = {"02": "sag_pu", "03": "swell_pu", "04": "interruption_pu"}


def _thd_do_ciclo(x: np.ndarray) -> float:
    espectro = np.abs(np.fft.rfft(x))
    return float(np.sqrt(np.sum(np.square(espectro[2:]))) / espectro[1])


def corte_da_senoide_clipada(thd_fracao: float) -> float:
    """Nível de corte ``c`` (em pu do pico) tal que ``clip(sin, -c, c)`` tem o
    THD pedido (``FUNCtion:CSINusoid``, 0 a 20 %). Bisseção sobre um ciclo de
    4096 pontos; o THD cai monotonicamente com ``c``."""
    if not 0.0 < thd_fracao <= 0.25:
        raise ValueError(f"THD {thd_fracao} fora do alcance do CSINe (0..20 %)")
    ciclo = np.sin(2.0 * np.pi * np.arange(4096) / 4096.0)
    baixo, alto = 0.05, 1.0
    for _ in range(60):
        meio = 0.5 * (baixo + alto)
        if _thd_do_ciclo(np.clip(ciclo, -meio, meio)) > thd_fracao:
            baixo = meio
        else:
            alto = meio
    return 0.5 * (baixo + alto)


def senoide_clipada_pu(t: np.ndarray, f0_hz: float, tau_s: float, thd_fracao: float) -> np.ndarray:
    """Senoide clipada com o THD pedido e o MESMO rms da senoide de pico 1
    (1/sqrt 2): a fonte escala a forma para o rms programado — garantido pelo
    manual para tabelas de usuário; para a CSINusoid interna é NÃO VERIFICADO."""
    corte = corte_da_senoide_clipada(thd_fracao)
    ciclo = np.clip(np.sin(2.0 * np.pi * np.arange(4096) / 4096.0), -corte, corte)
    rms_ciclo = float(np.sqrt(np.mean(np.square(ciclo))))
    x = np.clip(np.sin(2.0 * np.pi * f0_hz * (t + tau_s)), -corte, corte)
    return x * (1.0 / math.sqrt(2.0) / rms_ciclo)


def forma_programada_nativa(
    id_classe: str,
    *,
    t: np.ndarray,
    f0_hz: float,
    base_voltage_rms: float,
    parametros: dict,
    quantizar,
    inicio_legado_s: float | None = None,
    duracao_legada_s: float | None = None,
) -> np.ndarray:
    """Forma programada (pu do pico base, grade ``t``) de uma classe nativa.

    ``parametros`` = os de ``gerar()`` (nível da classe; ``inicio_disturbio_s``,
    ``duracao_s``, ``fase_graus`` quando o sorteio está ligado). ``quantizar`` =
    ``AmetekMX30.quantizar_tensao_rms`` já com o teto de tensão (a Rev. 5.53
    trunca ``VOLTage:TRIGgered`` a 0,1 V). Sem sorteio, o evento usa
    ``inicio_legado_s``/``duracao_legada_s`` (``INICIO_S``/``DURACAO_S`` da
    classe).

    * 01 e 19: STEP para a tensão base (quantizada) — 19 soma o offset enviado
      por ``SOURce:VOLTage:OFFSet`` (``%.8g``).
    * 02/03/04: PULSe para ``nível x base`` (quantizado) em
      ``[inicio, inicio + duração)``; fora disso, a base.
    * 05 (CSINe): senoide clipada no THD pedido (``senoide_clipada_pu``).
    * 18: ``LIST:FREQuency`` de 2 pontos, ``start_hz`` na 1.ª metade da janela e
      ``end_hz`` na 2.ª, fase contínua (a continuidade da fase na troca de
      passo é NÃO VERIFICADA) e fase inicial ``fase_graus``.
    """
    t = np.asarray(t, dtype=np.float64)
    fase_graus = float(parametros.get("fase_graus", 0.0))
    tau_s = fase_graus / (360.0 * f0_hz)
    senoide = np.sin(2.0 * np.pi * f0_hz * (t + tau_s))
    base = float(base_voltage_rms)
    fator_base = quantizar(base) / base

    if id_classe == "01":
        return senoide * fator_base
    if id_classe in _PARAMETRO_DO_NIVEL:
        nivel = float(parametros[_PARAMETRO_DO_NIVEL[id_classe]])
        inicio = float(parametros.get("inicio_disturbio_s", inicio_legado_s))
        duracao = float(parametros.get("duracao_s", duracao_legada_s))
        nivel_programado = quantizar(nivel * base) / base
        fator = np.where(janela(t, inicio, duracao), nivel_programado, 1.0)
        return senoide * fator
    if id_classe == "05":
        return senoide_clipada_pu(t, f0_hz, tau_s, float(parametros["thd"]))
    if id_classe == "18":
        fs_hz = 1.0 / float(t[1] - t[0])
        metade = t.size // 2
        frequencia = np.where(np.arange(t.size) < metade, float(parametros["start_hz"]), float(parametros["end_hz"]))
        fase = np.empty(t.size, dtype=np.float64)
        fase[0] = 0.0
        fase[1:] = 2.0 * np.pi * np.cumsum(frequencia[:-1]) / fs_hz
        return np.sin(fase + np.deg2rad(fase_graus))
    if id_classe == "19":
        pico_v = base * math.sqrt(2.0)
        offset_enviado_v = float(f"{float(parametros['dc_offset_pu']) * pico_v:.8g}")
        return senoide * fator_base + offset_enviado_v / pico_v
    raise KeyError(f"classe {id_classe!r} não é nativa")
