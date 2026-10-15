"""Perfis de faixas do dataset: norma (IEEE 1159), literatura e fronteira.

ÚNICO lugar com as faixas/níveis de cada perfil (v1.15). ``gerar()`` das
classes 02, 03, 05, 06, 10-16 e 20 lê daqui pelo perfil ativo
(``Config.perfil``); o resto do dataset (início, duração, fase, forma,
frequência de flicker, interrupção, notch, transitórios, drift, DC) não
depende do perfil. Tabela legível: ``docs/perfis.md``.

* ``literatura``: as faixas de antes da v1.15 (padrão). Reproduz byte a byte
  o ``gerar()`` do commit 34a0d82 para a mesma seed (teste em
  ``tests/test_offline.py``).
* ``norma``: faixas típicas da IEEE 1159 (flicker 2-7 %, inter-harmônicas
  0,5-2 %, THD até 20 %, sag 0,15-0,85 pu, swell 1,15-1,75 pu).
* ``fronteira``: sag/swell exatamente nas fronteiras 0,1 / 0,9 / 1,1 / 1,8 pu,
  como teste de estresse. Onde a spec não define fronteira (THD, flicker,
  inter-harmônicas) o perfil usa os valores da literatura.

Cada componente tem uma entrada por perfil; as classes compostas herdam o
componente (``sag_composto`` em 10/11/12, ``swell_composto`` em 13/14,
``thd_composto`` em 10/13/15/16, ``flicker_composto`` em 11/15). Com o
sorteio de posição ligado (padrão) as compostas sorteiam esses parâmetros por
captura em ``FAIXAS_SORTEADAS`` (``composto``); ``FAIXAS`` vale desligado.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

PERFIS: Tuple[str, ...] = ("norma", "literatura", "fronteira")
PERFIL_PADRAO = "literatura"
ENV_PERFIL = "PERFIL"

# Componente -> perfil -> valor. Tuplas de níveis são percorridas por
# ``capture_index % len`` (02/03/05 e compostos); pares (lo, hi) são intervalos
# sorteados com ``rng.uniform(lo, hi)`` (06/20).
FAIXAS: Dict[str, Dict[str, Tuple[float, ...]]] = {
    # Classe 02: níveis discretos (pu) durante o sag.
    "sag_niveis": {
        "norma": (0.15, 0.325, 0.5, 0.675, 0.85),
        "literatura": (0.1, 0.3, 0.5, 0.7, 0.9),
        "fronteira": (0.1, 0.9),
    },
    # Classe 03: níveis discretos (pu) durante o swell.
    "swell_niveis": {
        "norma": (1.15, 1.30, 1.45, 1.60, 1.75),
        "literatura": (1.1, 1.2, 1.4, 1.6, 1.8),
        "fronteira": (1.1, 1.8),
    },
    # Classe 05: níveis de THD (fração). Norma limitada a 20 % (também o teto
    # do CSINe, AmetekMX30.MAX_CSINE_THD_PCT).
    "thd_niveis": {
        "norma": (0.02, 0.05, 0.10, 0.15, 0.20),
        "literatura": (0.05, 0.10, 0.15, 0.20, 0.30),
        "fronteira": (0.05, 0.10, 0.15, 0.20, 0.30),
    },
    # Classe 06: profundidade do flicker (fração), sorteada uniforme.
    "flicker_profundidade": {
        "norma": (0.02, 0.07),
        "literatura": (0.05, 0.15),
        "fronteira": (0.05, 0.15),
    },
    # Classe 20: amplitude de cada inter-harmônica (pu), sorteada uniforme.
    "interharmonica_amplitude": {
        "norma": (0.005, 0.02),
        "literatura": (0.03, 0.08),
        "fronteira": (0.03, 0.08),
    },
    # Classes 10/11/12: nível do sag, percorrido por capture_index.
    "sag_composto": {
        "norma": (0.5,),
        "literatura": (0.5,),
        "fronteira": (0.1, 0.9),
    },
    # Classes 13/14: nível do swell, percorrido por capture_index.
    "swell_composto": {
        "norma": (1.3,),
        "literatura": (1.3,),
        "fronteira": (1.1, 1.8),
    },
    # Classes 10/13/15/16: THD do componente harmônico.
    "thd_composto": {
        "norma": (0.20,),
        "literatura": (0.20,),
        "fronteira": (0.20,),
    },
    # Classes 11/15: profundidade do flicker (fração), valor fixo.
    "flicker_composto": {
        "norma": (0.045,),
        "literatura": (0.10,),
        "fronteira": (0.10,),
    },
    # Classes 11/15: frequência do flicker (Hz), valor fixo.
    "flicker_composto_hz": {
        "norma": (15.0,),
        "literatura": (15.0,),
        "fronteira": (15.0,),
    },
    # Classes 12/14: frequência da oscilação amortecida (Hz), valor fixo.
    "oscilacao_composto_hz": {
        "norma": (600.0,),
        "literatura": (600.0,),
        "fronteira": (600.0,),
    },
}

# Compostas 10-16 com ``Config.sorteio_posicao`` ligado (v1.15): os componentes
# acima viram intervalos ``(lo, hi)`` sorteados com ``rng.uniform`` por captura
# (função ``composto``). ``None`` = sem intervalo: usa o nível discreto de
# ``FAIXAS`` percorrido por ``capture_index`` (fronteira de sag/swell, que é
# por definição o par 0,1 / 0,9 e 1,1 / 1,8). Desligado, vale ``FAIXAS`` (o
# ``gerar()`` do commit 34a0d82, byte a byte).
FAIXAS_SORTEADAS: Dict[str, Dict[str, Optional[Tuple[float, float]]]] = {
    # Faixa da literatura: sag ~ U(0,1; 0,9); norma = a
    # faixa de sag_niveis da norma.
    "sag_composto": {"norma": (0.15, 0.85), "literatura": (0.1, 0.9), "fronteira": None},
    # Swell: extremos de swell_niveis (não há faixa de literatura fixada para o swell).
    "swell_composto": {"norma": (1.15, 1.75), "literatura": (1.1, 1.8), "fronteira": None},
    # THD ~ U(0,05; 0,20) (literatura); norma desce a 2 % (mínimo de thd_niveis).
    "thd_composto": {"norma": (0.02, 0.20), "literatura": (0.05, 0.20), "fronteira": (0.05, 0.20)},
    # Profundidade: a mesma faixa da classe 06 (flicker_profundidade).
    "flicker_composto": {
        "norma": FAIXAS["flicker_profundidade"]["norma"],
        "literatura": FAIXAS["flicker_profundidade"]["literatura"],
        "fronteira": FAIXAS["flicker_profundidade"]["fronteira"],
    },
    # Flicker ~ U(8, 25) Hz (a mesma faixa de frequência da classe 06).
    "flicker_composto_hz": {"norma": (8.0, 25.0), "literatura": (8.0, 25.0), "fronteira": (8.0, 25.0)},
    # Oscilação (f_osc) ~ U(300, 2400) Hz.
    "oscilacao_composto_hz": {
        "norma": (300.0, 2400.0), "literatura": (300.0, 2400.0), "fronteira": (300.0, 2400.0),
    },
}

# Quais componentes cada classe lê (documentação e testes).
COMPONENTES_POR_CLASSE: Dict[str, Tuple[str, ...]] = {
    "02": ("sag_niveis",),
    "03": ("swell_niveis",),
    "05": ("thd_niveis",),
    "06": ("flicker_profundidade",),
    "10": ("sag_composto", "thd_composto"),
    "11": ("sag_composto", "flicker_composto", "flicker_composto_hz"),
    "12": ("sag_composto", "oscilacao_composto_hz"),
    "13": ("swell_composto", "thd_composto"),
    "14": ("swell_composto", "oscilacao_composto_hz"),
    "15": ("thd_composto", "flicker_composto", "flicker_composto_hz"),
    "16": ("thd_composto",),
    "20": ("interharmonica_amplitude",),
}


def validar(perfil: str) -> str:
    """Devolve ``perfil`` normalizado (minúsculas) ou levanta ``ValueError``."""
    normalizado = str(perfil).strip().lower()
    if normalizado not in PERFIS:
        raise ValueError(f"perfil deve ser um de {', '.join(PERFIS)}; recebido {perfil!r}")
    return normalizado


def perfil_do_ambiente() -> str:
    """Perfil inicial: variável de ambiente ``PERFIL`` (ausente/vazia = literatura)."""
    bruto = os.getenv(ENV_PERFIL, "").strip()
    return validar(bruto) if bruto else PERFIL_PADRAO


def perfil_da_config(config) -> str:
    """Perfil de uma ``Config`` (ou substituto mínimo sem o campo = literatura)."""
    return validar(getattr(config, "perfil", PERFIL_PADRAO))


def faixa(config, componente: str) -> Tuple[float, ...]:
    """Valores do ``componente`` no perfil ativo da ``config``."""
    return FAIXAS[componente][perfil_da_config(config)]


def nivel(config, componente: str, capture_index: int) -> float:
    """Nível do ``componente`` para a captura (percorre a tupla por índice)."""
    valores = faixa(config, componente)
    return valores[capture_index % len(valores)]


def composto(config, componente: str, capture_index: int, rng) -> float:
    """Valor do ``componente`` de uma composta (10-16) para esta captura.

    ``Config.sorteio_posicao`` ligado: sorteado em ``FAIXAS_SORTEADAS`` com
    ``rng.uniform`` (um sorteio por chamada, na ordem em que ``gerar()`` chama;
    o ``rng`` da classe não é usado por mais nada nas classes 10-16, e o
    sorteio de início/duração/fase vem de um sub-fluxo separado). Fronteira de
    sag/swell: nível discreto por ``capture_index``, sem consumir ``rng``.
    Desligado: ``nivel`` (os valores fixos de antes da v1.15)."""
    if not getattr(config, "sorteio_posicao", True):
        return nivel(config, componente, capture_index)
    intervalo = FAIXAS_SORTEADAS[componente][perfil_da_config(config)]
    if intervalo is None:
        return nivel(config, componente, capture_index)
    return float(rng.uniform(*intervalo))

# ---------------------------------------------------------------- independência

# Perfil sob o qual uma captura compartilhada é gravada (``set perfil todos``).
PERFIL_CANONICO = PERFIL_PADRAO
CLASSES: Tuple[str, ...] = tuple(f"{n:02d}" for n in range(1, 21))


def _valor_efetivo(componente: str, perfil: str, sorteio_posicao: bool) -> object:
    """O que ``gerar()`` realmente lê do ``componente`` no ``perfil``: o
    intervalo sorteado das compostas (``composto``, sorteio ligado) ou, sem
    intervalo (fronteira de sag/swell) e com o sorteio desligado, o nível
    discreto de ``FAIXAS``."""
    if sorteio_posicao and componente in FAIXAS_SORTEADAS:
        intervalo = FAIXAS_SORTEADAS[componente][perfil]
        if intervalo is not None:
            return ("intervalo", intervalo)
    return ("niveis", FAIXAS[componente][perfil])


def depende_do_perfil(class_id: str, sorteio_posicao: bool = True) -> bool:
    """``True`` se o ``gerar()`` da classe muda com o perfil. Derivado das
    tabelas acima: uma classe depende do perfil se algum componente que ela
    lê (``COMPONENTES_POR_CLASSE``; classe fora da tabela não lê nenhum) tem
    valor efetivo diferente em algum par de perfis. Com o sorteio desligado,
    por exemplo, a 16 (só ``thd_composto``, igual nos três) não depende; com
    ele ligado depende (a norma sorteia THD a partir de 2 %). Testado contra
    o ``gerar()`` real em ``tests/test_offline.py`` (``PerfisCompartilhadosTests``)."""
    for componente in COMPONENTES_POR_CLASSE.get(str(class_id), ()):
        valores = {_valor_efetivo(componente, perfil, sorteio_posicao) for perfil in PERFIS}
        if len(valores) > 1:
            return True
    return False


def classes_independentes_do_perfil(sorteio_posicao: bool = True) -> Tuple[str, ...]:
    """Classes (``01``..``20``) cujo ``gerar()`` é igual nos três perfis."""
    return tuple(c for c in CLASSES if not depende_do_perfil(c, sorteio_posicao))


def plano_de_perfis(
    class_id: str, lista_perfis: Sequence[str], sorteio_posicao: bool = True,
) -> List[Tuple[str, Tuple[str, ...]]]:
    """O que ``set perfil todos`` realmente captura para a classe: lista de
    ``(perfil_a_rodar, perfis_espelho)``. Classe dependente do perfil: um item
    por perfil, sem espelhos. Classe independente com mais de um perfil: UM
    item, sob o perfil canônico (``literatura``; o primeiro da lista se ela
    não o tiver), com os demais perfis como espelhos (a mesma captura,
    registrada no metadata dos outros perfis)."""
    lista = [validar(p) for p in lista_perfis]
    if len(lista) > 1 and not depende_do_perfil(class_id, sorteio_posicao):
        canonico = PERFIL_CANONICO if PERFIL_CANONICO in lista else lista[0]
        return [(canonico, tuple(p for p in lista if p != canonico))]
    return [(p, ()) for p in lista]
