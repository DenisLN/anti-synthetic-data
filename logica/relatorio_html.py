"""Relatório HTML autocontido das capturas de uma sessão, para compartilhar.

Preenche o modelo ``logica/modelos/relatorio_capturas.html`` com as figuras
de cada captura embutidas em base64 (``data:image/png;base64,...``): o
resultado é UM arquivo ``.html`` que abre em qualquer navegador, offline,
sem pasta de imagens ao lado — dá para mandar por e-mail.

Para cada captura: no máximo 1 visualização completa e 3 detalhes.

- **Completa**: o registro inteiro. Em captura física com margem, a folga
  antes/depois da janela nominal fica sombreada e o eixo de tempo começa em 0
  no início da janela nominal (mesma base de ``gerar()``) — a folga de antes
  aparece em tempo negativo. O recorte é o mesmo de ``recortar_margem.py``.
- **Detalhes** (até 3): zooms na janela nominal onde o sinal mais muda —
  saltos do envelope rms de meio ciclo (início/fim de sag, swell,
  interrupção) e resíduo em relação a uma senoide de f0 (harmônicos, notch,
  transitórios). Sem nada que se destaque, mostra só 1 detalhe do regime. As
  janelas escolhidas aparecem marcadas (D1, D2, D3) na visualização completa.
  ``--detalhes-manuais`` substitui a escolha automática por janelas fixas.

Sem hardware: só lê os ``.npz``/``metadata/*.jsonl`` já gravados
(``sessao_io.py``: formato 2, um ``NN_classe.npz`` por classe com perfis e
versões; e as sessões antigas, um ``.npz`` por captura). Funciona na sessão
original, na pasta ``sem_margem/`` de ``recortar_margem.py`` e no dataset
simulado.

Seleção do que entra no HTML (todas combinam entre si):

- ``--classes 02,05``: classes (prefixo ``NN``);
- ``--perfis norma,fronteira``: perfis (``norma``, ``literatura``, ``fronteira``);
- ``--versoes medida,modelo,programada``: versões desenhadas. A primeira
  disponível (na ordem medida, modelo, programada) é o traço principal; as
  outras são sobrepostas, na janela nominal. Padrão: ``medida``;
- ``--capturas 02-0001,02-0005`` ou ``--capturas 1-3``: ids de captura e/ou
  posições (1-based) dentro de cada classe e perfil.

Uso:
    python logica/relatorio_html.py resultados/sessao_2026-09-30_14-00-00
    python logica/relatorio_html.py resultados/sessao_... --classes 02,05 --titulo "Sag e harmônicos"
    python logica/relatorio_html.py resultados/sessao_... --snr 30 --max-capturas-por-classe 2
    python logica/relatorio_html.py resultados/sessao_... --detalhes-manuais detalhes.json

``detalhes.json`` (tempos em ms no eixo da visualização completa; chave =
nome do arquivo sem ``.npz`` ou ``id_captura``):
    {"02_sag_sag_pu-0.1": [[50, 85], [105, 140]], "08-0003": [[95, 105]]}
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "logica") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "logica"))
import sessao_io  # noqa: E402
from recortar_margem import calcular_recorte, carregar_metadados  # noqa: E402

MODELO_PADRAO = PROJECT_ROOT / "logica" / "modelos" / "relatorio_capturas.html"
MAX_DETALHES = 3
# Sem seleção explícita, tanto bancada quanto simulação mostram apenas
# as primeiras capturas de cada classe e perfil.
MAX_CAPTURAS_EMPILHADAS_PADRAO = 3
TAMANHO_EMAIL_MB = 20.0
F0_PADRAO_HZ = 60.0
FS_PADRAO_HZ = 30_000.0

COR_SINAL = "#1f5fa8"
COR_ESPERADO = "#c2410c"
COR_DETALHE = "#e8a33d"
COR_MARGEM = "#9e9e9e"
COR_VERSAO = {"modelo": "#2e7d32", "programada": "#7b1fa2"}


@dataclass
class Captura:
    arquivo: Path
    linha: int
    id_captura: str
    classe: str
    sinal: np.ndarray
    fs_hz: float
    f0_hz: float
    metadado: Optional[dict]
    inicio_nominal: int
    pontos_nominais: int
    recorte: dict
    grandeza: str = "Tensão"
    esperado: Optional[np.ndarray] = None
    perfil: str = ""
    formato: str = "por_captura"
    versao: str = "medida"
    # Outras versões pedidas (modelo/programada), na grade da janela nominal.
    sobrepostas: Dict[str, np.ndarray] = field(default_factory=dict)
    detalhes: List[Tuple[float, float]] = field(default_factory=list)
    detalhes_automaticos: bool = True
    correlacoes: Optional[dict] = None  # total e do distúrbio (físicas, com forma esperada)
    # Captura compartilhada entre perfis (set perfil todos, classe independente
    # do perfil): os dados existem uma vez, no perfil de origem.
    compartilhada: bool = False
    perfil_de_origem: str = ""
    perfis_compartilhados: Tuple[str, ...] = ()
    outros_perfis: Tuple[str, ...] = ()  # espelhos já cobertos por esta figura

    @property
    def tempo_ms(self) -> np.ndarray:
        """Eixo da visualização: 0 ms no início da janela nominal."""
        return (np.arange(self.sinal.size) - self.inicio_nominal) / self.fs_hz * 1000.0

    @property
    def tem_margem(self) -> bool:
        return self.sinal.size > self.pontos_nominais

    @property
    def nominal(self) -> np.ndarray:
        return self.sinal[self.inicio_nominal : self.inicio_nominal + self.pontos_nominais]

    @property
    def nome(self) -> str:
        """Rótulo da captura: o arquivo (formato 1) ou arquivo · perfil · id
        (formato 2, onde um arquivo tem todas as capturas da classe)."""
        if self.formato == "classe":
            extra = f" (= {', '.join(self.outros_perfis)})" if self.outros_perfis else ""
            return f"{self.arquivo.stem} · {self.perfil} · {self.id_captura}{extra}"
        return self.arquivo.stem

    @property
    def ancora(self) -> str:
        if self.formato == "classe":
            base = f"{self.arquivo.stem}-{self.perfil}-{self.id_captura}"
        else:
            base = f"{self.arquivo.stem}-{self.linha}" if self.linha else self.arquivo.stem
        return "cap-" + re.sub(r"[^A-Za-z0-9_-]+", "-", base)


# ---------------------------------------------------------------- detalhes

def escolher_detalhes(
    nominal: np.ndarray, *, fs_hz: float, f0_hz: float, quantidade: int, largura_ms: float,
) -> List[Tuple[float, float]]:
    """Até ``quantidade`` janelas ``(início_ms, fim_ms)`` (eixo da janela
    nominal) onde o sinal mais muda, sem sobreposição, em ordem de tempo.

    Pontuação por meio ciclo: salto do rms em relação aos vizinhos (bordas de
    sag/swell/interrupção), distância do rms à mediana (o evento em si) e
    resíduo de um ajuste ``a·sen + b·cos + c`` em f0 dentro do meio ciclo
    (harmônicos, notch, transitório, offset). Nada acima de 5% do rms
    mediano -> 1 janela no meio do registro (regime)."""
    quantidade = max(0, min(int(quantidade), MAX_DETALHES))
    if quantidade == 0 or nominal.size == 0:
        return []
    duracao_ms = nominal.size / fs_hz * 1000.0
    largura_ms = min(largura_ms, duracao_ms)
    n = int(round(fs_hz / (2.0 * f0_hz)))
    m = nominal.size // n if n >= 2 else 0
    if m < 3:
        return [(0.0, duracao_ms)]

    blocos = nominal[: m * n].reshape(m, n)
    rms = np.sqrt(np.mean(np.square(blocos), axis=1))
    t = (np.arange(m * n) / fs_hz).reshape(m, n)
    residuo = np.empty(m)
    for k in range(m):
        base = np.column_stack([
            np.sin(2 * np.pi * f0_hz * t[k]), np.cos(2 * np.pi * f0_hz * t[k]), np.ones(n),
        ])
        coef, *_ = np.linalg.lstsq(base, blocos[k], rcond=None)
        residuo[k] = np.sqrt(np.mean(np.square(blocos[k] - base @ coef)))

    referencia = float(np.median(rms)) or 1e-9
    salto = np.zeros(m)
    diferencas = np.abs(np.diff(rms))
    salto[1:] = np.maximum(salto[1:], diferencas)
    salto[:-1] = np.maximum(salto[:-1], diferencas)
    desvio = np.abs(rms - referencia)

    def _excesso(x: np.ndarray) -> np.ndarray:
        # Só o que passa do típico DESTE registro: na bancada o rms alterna
        # ~3% entre semiciclos positivo e negativo (offset), um "salto" de
        # fundo em todo meio ciclo que, sem isto, puxava detalhes para
        # trechos sem evento (sessão 2026-10-07, classe 17).
        return np.clip(x - np.median(x), 0.0, None)

    pontuacao = (2.0 * _excesso(salto) + _excesso(desvio) + _excesso(residuo)) / referencia

    centro_ms = (np.arange(m) * n + n / 2.0) / fs_hz * 1000.0
    meia = largura_ms / 2.0

    def _janela(centro: float) -> Tuple[float, float]:
        inicio = min(max(centro - meia, 0.0), duracao_ms - largura_ms)
        return (inicio, inicio + largura_ms)

    if float(pontuacao.max()) < 0.05:
        return [_janela(duracao_ms / 2.0)]

    # Sobreposição testada nas janelas JÁ ajustadas às bordas: perto do fim do
    # registro, centros distantes viram janelas sobrepostas (sessão
    # 2026-10-07, classe 20).
    # Uma janela que sobrepõe outra ainda pode deslizar e encostar nela,
    # desde que o meio ciclo que a motivou continue dentro.
    escolhidas: List[Tuple[float, float]] = []

    def _livre(a: float, b: float) -> bool:
        return (a >= -1e-9 and b <= duracao_ms + 1e-9
                and all(b <= a2 + 1e-9 or a >= b2 - 1e-9 for a2, b2 in escolhidas))

    for k in np.argsort(-pontuacao, kind="stable"):
        if pontuacao[k] < 0.25 * pontuacao.max() or len(escolhidas) == quantidade:
            break
        centro = float(centro_ms[k])
        candidatas = [_janela(centro)]
        for a2, b2 in escolhidas:
            candidatas += [(a2 - largura_ms, a2), (b2, b2 + largura_ms)]
        for a, b in candidatas:
            if a <= centro <= b and _livre(a, b):
                escolhidas.append((a, b))
                break
    return sorted(escolhidas)


def carregar_detalhes_manuais(caminho: Optional[Path]) -> Dict[str, List[Tuple[float, float]]]:
    if caminho is None:
        return {}
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    manuais: Dict[str, List[Tuple[float, float]]] = {}
    for chave, janelas in bruto.items():
        lista = [(float(a), float(b)) for a, b in janelas]
        if any(b <= a for a, b in lista):
            raise ValueError(f"{caminho}: janela com fim <= início em {chave!r}")
        if len(lista) > MAX_DETALHES:
            print(f"AVISO: {chave}: {len(lista)} detalhes manuais; só os {MAX_DETALHES} primeiros entram")
        manuais[str(chave)] = lista[:MAX_DETALHES]
    return manuais


# ---------------------------------------------------------------- leitura

def _reconstruir_esperado(captura: Captura) -> Optional[np.ndarray]:
    """Forma pedida (``gerar()`` + seed), via ``analisar_sessao``. Só para
    captura física de tensão; qualquer falha -> sem sobreposição."""
    md = captura.metadado
    if md is None or md.get("simulado", True) or captura.grandeza != "Tensão" or captura.versao != "medida":
        return None
    try:
        from analisar_sessao import _reconstruir_esperado as reconstruir
        esperado = np.asarray(reconstruir(captura.id_captura.split("-")[0], md), dtype=np.float64)
    except Exception as exc:  # noqa: BLE001 - relatório nunca cai por isto
        print(f"AVISO: {captura.id_captura}: forma esperada não reconstruída ({exc})")
        return None
    return esperado if esperado.size == captura.pontos_nominais else None


def _correlacoes(captura: Captura, esperado: Optional[np.ndarray]) -> Optional[dict]:
    """Correlação total e só da componente de distúrbio contra a forma
    esperada, com as mesmas funções de ``analisar_sessao`` (mesmo alinhamento
    por lag). ``None`` sem esperado ou sem metadata."""
    md = captura.metadado
    if esperado is None or md is None:
        return None
    try:
        from analisar_sessao import _correlacao_disturbio_alinhada, analisar_offset
        n = esperado.size
        janela = captura.sinal[captura.inicio_nominal : captura.inicio_nominal + n]
        lag, total = analisar_offset(esperado, janela, captura.fs_hz)
        valor, motivo = _correlacao_disturbio_alinhada(esperado, captura.sinal, captura.inicio_nominal, lag, md)
        ajustada, motivo_ajustada = _correlacao_disturbio_alinhada(
            esperado, captura.sinal, captura.inicio_nominal, lag, md, fundamental_ajustada=True,
        )
    except Exception as exc:  # noqa: BLE001 - relatório nunca cai por isto
        print(f"AVISO: {captura.id_captura}: correlações não calculadas ({exc})")
        return None
    return {"total": total, "disturbio": valor, "motivo": motivo, "lag_ms": lag / captura.fs_hz * 1000.0,
            "disturbio_fund_ajustada": ajustada, "motivo_fund_ajustada": motivo_ajustada}


def ler_capturas(
    dados_dir: Path,
    metadados: Dict[str, dict],
    *,
    classes: Optional[Sequence[str]] = None,
    max_por_classe: Optional[int] = None,
    perfis: Optional[Sequence[str]] = None,
    versoes: Sequence[str] = ("medida",),
    capturas: Optional[str] = None,
) -> List[Captura]:
    """Capturas de ``dados_dir`` (só os ``.npz`` dessa pasta), em ordem de
    arquivo, perfil e posição; ``classes`` filtra pelo prefixo ``NN_``,
    ``perfis``/``versoes``/``capturas`` como no módulo. ``max_por_classe``
    vale por (classe, perfil). Sem ``capturas`` nem ``max_por_classe``, o
    relatório de bancada ou simulação mostra só as primeiras
    ``MAX_CAPTURAS_EMPILHADAS_PADRAO`` de cada bloco."""
    pedidas = [v for v in sessao_io.VERSOES if v in versoes]
    if not pedidas:
        raise ValueError(f"versoes deve conter {', '.join(sessao_io.VERSOES)}; recebido {list(versoes)!r}")
    limite = max_por_classe
    if limite is None and not capturas:
        limite = MAX_CAPTURAS_EMPILHADAS_PADRAO
        print(f"AVISO: relatório limitado às {limite} primeiras capturas por classe e perfil "
              "(use --capturas ou --max-capturas-por-classe para alterar).")
    lidas = sessao_io.ler_pasta(
        dados_dir, metadados, versoes=pedidas, classes=classes, perfis=perfis, capturas=capturas,
        max_por_bloco=limite,
        limite_padrao_empilhado=None if capturas else MAX_CAPTURAS_EMPILHADAS_PADRAO,
        avisar=lambda mensagem: print(f"AVISO: {mensagem}"),
    )
    resultado: List[Captura] = []
    for c in lidas:
        md = c.metadado
        principal = next((v for v in pedidas if v in c.versoes), None) if c.versoes else None
        if c.grandeza == "Tensão" and c.versoes:
            sinal = c.versoes[principal]
        else:
            sinal, principal = c.sinal, "medida"
        fs_hz = float((md or {}).get("fs_hz", 0.0)) or (
            1000.0 / float(np.median(np.diff(c.tempo_ms))) if c.tempo_ms is not None and c.tempo_ms.size > 1 else FS_PADRAO_HZ
        )
        inicio, pontos, recorte = calcular_recorte(sinal.size, md)
        resultado.append(Captura(
            arquivo=c.arquivo, linha=c.linha, id_captura=c.id_captura, classe=c.classe,
            sinal=sinal, fs_hz=fs_hz, f0_hz=float((md or {}).get("f0_hz", F0_PADRAO_HZ)),
            metadado=md, inicio_nominal=inicio, pontos_nominais=pontos, recorte=recorte,
            grandeza=c.grandeza, perfil=c.perfil, formato=c.formato, versao=principal,
            sobrepostas={v: a for v, a in c.versoes.items() if v != principal and c.grandeza == "Tensão"},
            compartilhada=c.compartilhada, perfil_de_origem=c.perfil_de_origem or "",
            perfis_compartilhados=tuple(c.perfis_compartilhados),
        ))
    return _sem_figuras_repetidas(resultado)


def _sem_figuras_repetidas(capturas: List[Captura]) -> List[Captura]:
    """Uma captura compartilhada entre perfis é UMA figura: o espelho (perfil
    sem bloco próprio) só fica quando a captura de origem não está na lista
    (ex. ``--perfis norma``); do contrário a figura da origem passa a dizer
    quais outros perfis ela cobre (``outros_perfis``)."""
    origens = {(c.arquivo, c.id_captura, c.perfil): c for c in capturas}
    saida: List[Captura] = []
    for c in capturas:
        if c.compartilhada and c.perfil != c.perfil_de_origem:
            origem = origens.get((c.arquivo, c.id_captura, c.perfil_de_origem))
            if origem is not None:
                origem.outros_perfis = (*origem.outros_perfis, c.perfil)
                continue
        saida.append(c)
    return saida


# ---------------------------------------------------------------- figuras

def _png_base64(fig, dpi: int) -> str:
    import matplotlib.pyplot as plt
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _eixo_em_volts(ax, captura: Captura) -> None:
    """Eixo secundário em volts (1 pu = pico nominal = Vrms base × √2)."""
    md = captura.metadado or {}
    vbase = md.get("tensao_base_rms")
    if captura.grandeza != "Tensão" or not vbase:
        return
    pico = float(vbase) * np.sqrt(2.0)
    sec = ax.secondary_yaxis("right", functions=(lambda pu: pu * pico, lambda v: v / pico))
    sec.set_ylabel("V")


def figura_completa(captura: Captura, dpi: int) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = captura.tempo_ms
    fig, ax = plt.subplots(figsize=(11.5, 3.4))
    if captura.tem_margem:
        fim_nominal = captura.pontos_nominais / captura.fs_hz * 1000.0
        if t[0] < 0:
            ax.axvspan(t[0], 0.0, color=COR_MARGEM, alpha=0.18, lw=0)
            ax.text(t[0] / 2, 1.01, "folga antes", transform=ax.get_xaxis_transform(),
                    ha="center", va="bottom", fontsize=8, color="#555")
        if t[-1] > fim_nominal:
            ax.axvspan(fim_nominal, t[-1], color=COR_MARGEM, alpha=0.18, lw=0)
            ax.text((fim_nominal + t[-1]) / 2, 1.01, "folga depois", transform=ax.get_xaxis_transform(),
                    ha="center", va="bottom", fontsize=8, color="#555")
    for k, (a, b) in enumerate(captura.detalhes, start=1):
        ax.axvspan(a, b, color=COR_DETALHE, alpha=0.22, lw=0)
        ax.text((a + b) / 2, 0.98, f"D{k}", transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=9, fontweight="bold", color="#8a5a00")
    indice_trigger = (captura.metadado or {}).get("indice_trigger")
    if indice_trigger is not None and captura.tem_margem:
        t_trigger = (int(indice_trigger) - captura.inicio_nominal) / captura.fs_hz * 1000.0
        ax.axvline(t_trigger, color="#444", lw=0.8, ls=":")
        ax.text(t_trigger, 0.02, " trigger", transform=ax.get_xaxis_transform(), fontsize=8, color="#444")
    ax.plot(t, captura.sinal, color=COR_SINAL, lw=0.7, label="capturado" if captura.versao == "medida" else captura.versao)
    if captura.esperado is not None:
        t_nom = np.arange(captura.esperado.size) / captura.fs_hz * 1000.0
        ax.plot(t_nom, captura.esperado, color=COR_ESPERADO, lw=0.7, ls="--", alpha=0.85, label="esperado (gerar + seed)")
        ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    for rotulo, serie in captura.sobrepostas.items():
        t_serie = np.arange(serie.size) / captura.fs_hz * 1000.0
        ax.plot(t_serie, serie, color=COR_VERSAO.get(rotulo, "#555"), lw=0.7, ls="--", alpha=0.9, label=rotulo)
    if captura.sobrepostas:
        ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    ax.set_xlim(t[0], t[-1])
    ax.set_xlabel("Tempo desde o início da janela nominal (ms)")
    ax.set_ylabel(f"{captura.grandeza} (pu)")
    ax.grid(alpha=0.3)
    _eixo_em_volts(ax, captura)
    return _png_base64(fig, dpi)


def figura_detalhe(captura: Captura, indice: int, janela: Tuple[float, float], dpi: int) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    a, b = janela
    t = captura.tempo_ms
    mascara = (t >= a) & (t <= b)
    # Pequena de propósito: no HTML ocupa 1/3 da largura, e uma figura maior
    # reduzida até lá deixa os rótulos ilegíveis.
    fig, ax = plt.subplots(figsize=(3.8, 2.6))
    ax.plot(t[mascara], captura.sinal[mascara], color=COR_SINAL, lw=1.0)
    for rotulo, serie in captura.sobrepostas.items():
        t_serie = np.arange(serie.size) / captura.fs_hz * 1000.0
        m_serie = (t_serie >= a) & (t_serie <= b)
        ax.plot(t_serie[m_serie], serie[m_serie], color=COR_VERSAO.get(rotulo, "#555"), lw=0.9, ls="--", alpha=0.9)
    if captura.esperado is not None:
        t_nom = np.arange(captura.esperado.size) / captura.fs_hz * 1000.0
        m_nom = (t_nom >= a) & (t_nom <= b)
        ax.plot(t_nom[m_nom], captura.esperado[m_nom], color=COR_ESPERADO, lw=0.9, ls="--", alpha=0.85)
    ax.set_title(f"D{indice}  ·  {a:.1f} a {b:.1f} ms", fontsize=10)
    ax.set_xlabel("ms", fontsize=9)
    ax.set_ylabel(f"{captura.grandeza} (pu)", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(alpha=0.3)
    return _png_base64(fig, dpi)


# ---------------------------------------------------------------- HTML

def _e(valor) -> str:
    return html.escape(str(valor), quote=True)


def _fmt(valor) -> str:
    if isinstance(valor, float):
        return f"{valor:.6g}"
    if isinstance(valor, dict):
        return ", ".join(f"{k} = {_fmt(v)}" for k, v in valor.items()) or "—"
    if isinstance(valor, (list, tuple)):
        return ", ".join(_fmt(v) for v in valor) or "—"
    return str(valor)


def tabela_metadados(captura: Captura) -> str:
    md = captura.metadado or {}
    linhas: List[Tuple[str, str]] = [
        ("Arquivo", f"<code>{_e(captura.arquivo.name)}</code>"
                    + (f" (linha {captura.linha})" if captura.linha else "")),
        ("ID da captura", f"<code>{_e(captura.id_captura)}</code>"),
    ]
    if captura.perfil:
        linhas.append(("Perfil", _e(captura.perfil)))
    if captura.compartilhada:
        md_ = captura.metadado or {}
        if captura.perfil == captura.perfil_de_origem:
            cobertos = ", ".join([captura.perfil, *captura.outros_perfis]) if captura.outros_perfis \
                else ", ".join(captura.perfis_compartilhados)
            texto = f"mesma captura nos perfis {cobertos} (gerar() não depende do perfil; capturada uma vez)"
        else:
            texto = (f"esta captura é a do perfil {captura.perfil_de_origem} "
                     f"(compartilhada com {', '.join(captura.perfis_compartilhados)}; capturada uma vez)")
        if md_.get("sha256_captura"):
            texto += f" · SHA-256 {md_['sha256_captura'][:16]}…"
        linhas.append(("Captura compartilhada", _e(texto)))
    if captura.formato == "classe" or captura.sobrepostas or captura.versao != "medida":
        desenhadas = ", ".join([captura.versao, *captura.sobrepostas])
        linhas.append(("Versões desenhadas", _e(desenhadas)))
    if md.get("parametros"):
        linhas.append(("Parâmetros", _e(_fmt(md["parametros"]))))
    for chave, rotulo in (("seed", "Seed"), ("nivel_indice", "Índice de nível")):
        if chave in md:
            linhas.append((rotulo, _e(md[chave])))
    rede = []
    if "f0_hz" in md:
        rede.append(f"{_fmt(float(md['f0_hz']))} Hz")
    if "tensao_base_rms" in md:
        rede.append(f"{_fmt(float(md['tensao_base_rms']))} Vrms base")
    if rede:
        linhas.append(("Rede", _e(" · ".join(rede))))
    duracao = captura.pontos_nominais / captura.fs_hz * 1000.0
    if captura.tem_margem:
        antes = captura.inicio_nominal / captura.fs_hz * 1000.0
        depois = (captura.sinal.size - captura.inicio_nominal - captura.pontos_nominais) / captura.fs_hz * 1000.0
        texto = (f"{antes:.1f} ms antes · {duracao:.1f} ms nominais · {depois:.1f} ms depois "
                 f"(alinhado por {captura.recorte['origem']})")
        if captura.recorte.get("ajustado"):
            texto += " — AJUSTADO: janela empurrada para dentro do registro"
        linhas.append(("Janela", _e(texto)))
    else:
        linhas.append(("Janela", _e(f"{duracao:.1f} ms ({captura.sinal.size} amostras, sem folga)")))
    if captura.correlacoes:
        c = captura.correlacoes
        disturbio = f"{c['disturbio']:.3f}" if c["disturbio"] is not None else f"n/a ({_e(c['motivo'])})"
        aj = c.get("disturbio_fund_ajustada")
        ajustada = f"{aj:.3f}" if aj is not None else f"n/a ({_e(c.get('motivo_fund_ajustada'))})"
        linhas.append(("Correlação com o esperado",
                       f"total {c['total']:.3f} · só do distúrbio {disturbio} "
                       f"(após alinhar; lag {c['lag_ms']:.2f} ms) · "
                       f"distúrbio com a fundamental ajustada {ajustada}"))
    validacao = md.get("validacao_fisica")
    if isinstance(validacao, dict):
        if validacao.get("ok"):
            linhas.append(("Validação física", '<span class="ok">OK</span>'))
        else:
            motivos = "; ".join(str(m) for m in validacao.get("motivos") or []) or "sem motivo registrado"
            linhas.append(("Validação física", f'<span class="falha">FALHOU</span> — {_e(motivos)}'))
    if md.get("simulado"):
        linhas.append(("Origem", "dataset simulado (<code>gerar()</code>)"))
    corpo = "\n".join(f"<tr><th>{r}</th><td>{v}</td></tr>" for r, v in linhas)
    return f'<table class="meta">\n{corpo}\n</table>'


def bloco_captura(captura: Captura, dpi: int) -> str:
    completa = figura_completa(captura, dpi)
    partes = [
        f'<section class="captura" id="{captura.ancora}">',
        f"<h2>{_e(captura.classe)} · <code>{_e(captura.nome)}</code></h2>",
        tabela_metadados(captura),
        "<figure>",
        f'<img src="data:image/png;base64,{completa}" alt="{_e(captura.nome)}: visualização completa">',
        "<figcaption>Visualização completa"
        + (" — faixas cinzas: folga de captura fora da janela nominal" if captura.tem_margem else "")
        + (" — tracejado: forma esperada" if captura.esperado is not None else "")
        + (f" — tracejado: {', '.join(captura.sobrepostas)}" if captura.sobrepostas else "")
        + "</figcaption>",
        "</figure>",
    ]
    if captura.detalhes:
        origem = "escolhidos automaticamente" if captura.detalhes_automaticos else "definidos manualmente"
        partes.append('<div class="detalhes">')
        for k, janela in enumerate(captura.detalhes, start=1):
            img = figura_detalhe(captura, k, janela, dpi)
            partes.append(
                f'<figure><img src="data:image/png;base64,{img}" alt="{_e(captura.nome)}: detalhe D{k}">'
                f"<figcaption>D{k} ({origem})</figcaption></figure>"
            )
        partes.append("</div>")
    partes.append("</section>")
    return "\n".join(partes)


def resumo_sessao(sessao_dir: Path, dados_dir: Path, capturas: Sequence[Captura]) -> str:
    md = next((c.metadado for c in capturas if c.metadado), {}) or {}
    classes = sorted({c.arquivo.name.split("_", 1)[0] for c in capturas})
    nome_da_sessao = sessao_dir.name
    if nome_da_sessao == "sem_margem" and sessao_dir.parent.name:  # versão recortada: mostra a sessão de origem
        nome_da_sessao = f"{sessao_dir.resolve().parent.name} (sem_margem)"
    itens: List[Tuple[str, str]] = [
        ("Sessão", f"<code>{_e(nome_da_sessao)}</code>"),
        ("Dados", _e("sem ruído" if dados_dir == sessao_dir else dados_dir.name)),
        ("Capturas", _e(f"{len(capturas)} em {len(classes)} classe(s)")),
    ]
    perfis_presentes = sorted({p for c in capturas for p in (c.perfil, *c.outros_perfis) if p})
    if perfis_presentes:
        itens.append(("Perfis", _e(", ".join(perfis_presentes))))
    compartilhadas = [c for c in capturas if c.compartilhada and c.perfil == c.perfil_de_origem]
    if compartilhadas:
        itens.append(("Capturas compartilhadas", _e(
            f"{len(compartilhadas)} figura(s) valem para mais de um perfil (classe cujo gerar() "
            "não depende do perfil; desenhada uma vez, sob o perfil de origem)"
        )))
    validadas = [c for c in capturas if isinstance((c.metadado or {}).get("validacao_fisica"), dict)]
    if validadas:
        ok = sum(1 for c in validadas if c.metadado["validacao_fisica"].get("ok"))
        itens.append(("Validação física", _e(f"{ok}/{len(validadas)} OK")))
    for chave, rotulo in (("f0_hz", "Frequência"), ("tensao_base_rms", "Tensão base (Vrms)"),
                          ("base_seed", "Seed base"), ("versao_codigo", "Versão do código"),
                          ("idn_fonte", "Fonte"), ("idn_osciloscopio", "Osciloscópio")):
        if md.get(chave) not in (None, ""):
            itens.append((rotulo, _e(_fmt(md[chave]))))
    corpo = "\n".join(f"<dt>{r}</dt><dd>{v}</dd>" for r, v in itens)
    return f'<section class="resumo"><dl>\n{corpo}\n</dl></section>'


def sumario(capturas: Sequence[Captura]) -> str:
    itens = []
    for c in capturas:
        falhou = isinstance((c.metadado or {}).get("validacao_fisica"), dict) and not c.metadado["validacao_fisica"].get("ok")
        marca = ' <span class="falha">(validação falhou)</span>' if falhou else ""
        itens.append(f'<li><a href="#{c.ancora}">{_e(c.nome)}</a>{marca}</li>')
    return '<nav class="sumario"><h2>Capturas</h2><ol>\n' + "\n".join(itens) + "\n</ol></nav>"


def montar_html(
    modelo: str, *, titulo: str, descricao: str, sessao_dir: Path, dados_dir: Path,
    capturas: Sequence[Captura], dpi: int,
) -> str:
    blocos: List[str] = []
    classe_atual = None
    for c in capturas:
        prefixo = c.arquivo.name.split("_", 1)[0]
        if prefixo != classe_atual:
            classe_atual = prefixo
            blocos.append(f'<h2 class="classe-titulo">{_e(prefixo)} — {_e(c.classe)}</h2>')
        blocos.append(bloco_captura(c, dpi))
    return Template(modelo).substitute(
        titulo=_e(titulo),
        descricao=f'<p class="descricao">{_e(descricao)}</p>' if descricao else "",
        gerado_em=_e(datetime.now().strftime("%d/%m/%Y %H:%M")),
        resumo_sessao=resumo_sessao(sessao_dir, dados_dir, capturas),
        sumario=sumario(capturas),
        capturas="\n".join(blocos),
    )


def gerar_relatorio(
    sessao_dir: Path, saida: Path, *, titulo: Optional[str] = None, descricao: str = "",
    snr: Optional[str] = None, classes: Optional[Sequence[str]] = None,
    max_por_classe: Optional[int] = None, detalhes: int = MAX_DETALHES,
    largura_detalhe_ms: Optional[float] = None, detalhes_manuais: Optional[Dict[str, List[Tuple[float, float]]]] = None,
    com_esperado: bool = False, dpi: int = 100, modelo: Path = MODELO_PADRAO,
    perfis: Optional[Sequence[str]] = None, versoes: Sequence[str] = ("medida",),
    capturas_escolhidas: Optional[str] = None,
) -> Tuple[Path, int]:
    """Gera o HTML; devolve ``(caminho, número de capturas)``. ``classes``,
    ``perfis``, ``versoes`` e ``capturas_escolhidas`` selecionam o que entra
    (ver o docstring do módulo)."""
    dados_dir = sessao_dir / f"snr_{snr}db" if snr else sessao_dir
    if not dados_dir.is_dir():
        raise FileNotFoundError(f"Pasta não encontrada: {dados_dir}")
    metadados = carregar_metadados(sessao_dir)
    capturas = ler_capturas(
        dados_dir, metadados, classes=classes, max_por_classe=max_por_classe,
        perfis=perfis, versoes=versoes, capturas=capturas_escolhidas,
    )
    if not capturas:
        raise FileNotFoundError(f"Nenhuma captura encontrada em {dados_dir}")
    manuais = detalhes_manuais or {}
    for c in capturas:
        esperado = _reconstruir_esperado(c)  # sempre: as correlações precisam dele
        c.correlacoes = _correlacoes(c, esperado)
        if com_esperado:
            c.esperado = esperado
        janelas = (manuais.get(f"{c.perfil}/{c.id_captura}") or manuais.get(c.arquivo.stem)
                   or manuais.get(c.id_captura))
        if janelas is not None:
            c.detalhes, c.detalhes_automaticos = list(janelas)[:MAX_DETALHES], False
        else:
            largura = largura_detalhe_ms if largura_detalhe_ms else 2000.0 / c.f0_hz  # 2 ciclos
            c.detalhes = escolher_detalhes(
                c.nominal, fs_hz=c.fs_hz, f0_hz=c.f0_hz, quantidade=detalhes, largura_ms=largura,
            )
    documento = montar_html(
        modelo.read_text(encoding="utf-8"),
        titulo=titulo or f"Capturas — {sessao_dir.name}", descricao=descricao,
        sessao_dir=sessao_dir, dados_dir=dados_dir, capturas=capturas, dpi=dpi,
    )
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(documento, encoding="utf-8")
    return saida, len(capturas)


def gerar_relatorio_recortado(
    sessao_dir: Path, *, titulo: Optional[str] = None, descricao: str = "", dpi: int = 100,
) -> Tuple[Path, int, float]:
    """Relatório da versão RECORTADA da sessão (o que a CLI gera ao fim do
    ``run`` com ``set html on``): recorta a margem para ``<sessao>/sem_margem/``
    (``recortar_margem.recortar_sessao``, originais intocados) e gera
    ``<sessao>/relatorio_<sessao>.html`` a partir dela, com os dados puros
    (``snr_XXdb/`` fica para ``--snr`` na linha de comando). Devolve
    ``(caminho, número de capturas, tamanho em MB)``."""
    from recortar_margem import PASTA_SAIDA_PADRAO, recortar_sessao

    sessao_dir = Path(sessao_dir)
    recortada = sessao_dir / PASTA_SAIDA_PADRAO
    recortar_sessao(sessao_dir, recortada)
    caminho, total = gerar_relatorio(
        recortada, sessao_dir / f"relatorio_{sessao_dir.resolve().name}.html",
        titulo=titulo or f"Capturas — {sessao_dir.resolve().name}",
        descricao=descricao or "Versão recortada: só a janela nominal de cada captura (sem a folga de captura).",
        dpi=dpi,
    )
    return caminho, total, caminho.stat().st_size / (1024 * 1024)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera um HTML autocontido (figuras em base64) com as capturas de uma sessão.",
    )
    parser.add_argument("sessao_dir", type=Path, help="Pasta da sessão (resultados/sessao_.../, ou a sem_margem/ dela)")
    parser.add_argument("--saida", type=Path, default=None, help="Arquivo .html (padrão: <sessao>/relatorio_<sessao>.html)")
    parser.add_argument("--titulo", default=None, help="Título do relatório")
    parser.add_argument("--descricao", default="", help="Texto livre logo abaixo do título (contexto para quem vai ler)")
    parser.add_argument("--snr", default=None, help="Usa snr_<SNR>db/ em vez dos dados sem ruído (ex.: 30)")
    parser.add_argument("--classes", default=None, help="Só estas classes, separadas por vírgula (ex.: 02,05,10)")
    parser.add_argument("--perfis", default=None,
                        help="Só estes perfis, separados por vírgula (norma, literatura, fronteira; padrão: todos os do arquivo)")
    parser.add_argument("--versoes", default="medida",
                        help="Versões desenhadas, separadas por vírgula: medida, modelo, programada (a primeira é o traço principal; "
                             "as outras são sobrepostas). Padrão: medida")
    parser.add_argument("--capturas", default=None,
                        help="Só estas capturas: ids (02-0001) e/ou posições dentro da classe e do perfil (3 ou 1-3), separados por vírgula")
    parser.add_argument("--max-capturas-por-classe", type=int, default=None,
                        help=f"Limite de capturas por classe e perfil (padrão: as {MAX_CAPTURAS_EMPILHADAS_PADRAO} primeiras por classe e perfil; com --capturas, só as pedidas)")
    parser.add_argument("--detalhes", type=int, default=MAX_DETALHES, choices=range(0, MAX_DETALHES + 1),
                        help=f"Detalhes automáticos por captura (0 a {MAX_DETALHES})")
    parser.add_argument("--largura-detalhe-ms", type=float, default=None, help="Largura de cada detalhe (padrão: 2 ciclos de f0)")
    parser.add_argument("--detalhes-manuais", type=Path, default=None,
                        help="JSON {arquivo_ou_id: [[ini_ms, fim_ms], ...]} que substitui a escolha automática")
    parser.add_argument("--com-esperado", action="store_true",
                        help="Sobrepõe a forma esperada (gerar() + seed, como analisar_sessao.py) em tracejado")
    parser.add_argument("--dpi", type=int, default=100, help="Resolução das figuras (menor = HTML menor)")
    parser.add_argument("--modelo", type=Path, default=MODELO_PADRAO, help="Modelo HTML a preencher")
    args = parser.parse_args(argv)

    if not args.sessao_dir.is_dir():
        parser.error(f"Pasta não encontrada: {args.sessao_dir}")
    if args.max_capturas_por_classe is not None and args.max_capturas_por_classe < 1:
        parser.error("--max-capturas-por-classe deve ser >= 1")
    classes = [c.strip().zfill(2) for c in args.classes.split(",") if c.strip()] if args.classes else None
    perfis_pedidos = [p.strip().lower() for p in args.perfis.split(",") if p.strip()] if args.perfis else None
    versoes_pedidas = [v.strip().lower() for v in args.versoes.split(",") if v.strip()]
    for v in versoes_pedidas:
        if v not in sessao_io.VERSOES:
            parser.error(f"--versoes: {v!r} inválida (use {', '.join(sessao_io.VERSOES)})")
    for p in perfis_pedidos or []:
        if p not in ("norma", "literatura", "fronteira"):
            parser.error(f"--perfis: {p!r} inválido (use norma, literatura, fronteira)")
    try:
        sessao_io.parsear_selecao_capturas(args.capturas)
    except ValueError as exc:
        parser.error(f"--capturas: {exc}")
    sufixo = f"_snr{args.snr}db" if args.snr else ""
    saida = args.saida or args.sessao_dir / f"relatorio_{args.sessao_dir.resolve().name}{sufixo}.html"

    caminho, total = gerar_relatorio(
        args.sessao_dir, saida, titulo=args.titulo, descricao=args.descricao, snr=args.snr,
        classes=classes, max_por_classe=args.max_capturas_por_classe, detalhes=args.detalhes,
        largura_detalhe_ms=args.largura_detalhe_ms,
        detalhes_manuais=carregar_detalhes_manuais(args.detalhes_manuais),
        com_esperado=args.com_esperado, dpi=args.dpi, modelo=args.modelo,
        perfis=perfis_pedidos, versoes=versoes_pedidas, capturas_escolhidas=args.capturas,
    )
    tamanho_mb = caminho.stat().st_size / (1024 * 1024)
    print(f"Relatório com {total} captura(s): {caminho} ({tamanho_mb:.1f} MB)")
    if tamanho_mb > TAMANHO_EMAIL_MB:
        print(f"AVISO: acima de {TAMANHO_EMAIL_MB:.0f} MB — pode não passar como anexo de e-mail. "
              "Reduza com --classes, --max-capturas-por-classe ou --dpi 80.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
