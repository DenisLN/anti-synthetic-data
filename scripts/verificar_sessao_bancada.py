"""Verificador OFFLINE de uma sessão de bancada (validação de sorteio, 2026-10-13).

Roda DEPOIS da bancada, sobre a pasta ``resultados\\sessao_<timestamp>[_runNN]``.
Não toca instrumento nenhum (nem importa PyVISA); só lê ``metadata/*.jsonl`` e
os ``.npz`` já gravados. Três verificações que só dado real fecha (pendentes de
``classes_05_07_18_VERIFICAR`` e ``sorteio_inicio_fase_VERIFICAR_BANCADA``):

1. **18 (FREQUENCY_DRIFT): continuidade de fase na troca de passo.** A fonte faz
   2 degraus de ``LIST:FREQuency`` (``start_hz`` -> ``end_hz``, 100 ms cada). A
   fase da saída é contínua na troca? Mede-se o salto de fase (graus): fase do
   sinal analítico, duas retas (uma por passo, sem as bordas e sem a vizinhança
   da troca), extrapoladas até o instante NOMINAL da troca (meio da janela).
   Só a fase não separa "salto" de "troca atrasada": o resultado traz também
   onde as retas se cruzam (``intersecao_ms``). Critério: |salto| <=
   ``--tol-fase-graus``.
2. **02/03/04 (PULSe): largura medida contra a programada.** A programada é
   ``duracao_s`` do metadata (a largura que ``configurar()`` escreveu em
   ``PULSe:WIDTh``). A medida é o intervalo em que a amplitude instantânea
   (módulo do sinal analítico) fica do lado do evento do ponto médio entre o
   nível de regime e o do evento. Critério: |erro| <= ``--tol-largura-ms``.
3. **pre_trigger_desvio_amostras** (``indice_trigger`` lido do osciloscópio menos
   o previsto). Nunca foi medido em bancada. Critério: |desvio| <= ``--tol-pretrigger-amostras``
   (o mesmo 2 do aviso em ``mestre.py``).

Uso (PowerShell, na raiz do projeto):

    env\\Scripts\\python.exe scripts\\verificar_sessao_bancada.py resultados\\sessao_2026-10-14_10-00-00_run01
    env\\Scripts\\python.exe scripts\\verificar_sessao_bancada.py <pasta> --json logs\\verificar.json

Código de saída: 0 = tudo aprovado; 1 = alguma verificação reprovada; 2 = nada
a verificar (pasta sem capturas das classes 02-04/18 nem campo de pré-trigger).

O CARREGAMENTO da sessão está isolado em ``carregar_sessao()`` (e a janela
nominal em ``janela_da_captura()``): se o formato de arquivo mudar (arquivo único por classe),
só essas duas funções precisam ser trocadas; as verificações recebem arrays.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "logica"))

from sinais import janela_nominal  # noqa: E402

CLASSES_PULSE = ("02", "03", "04")
CLASSE_DERIVA = "18"

TOL_FASE_GRAUS = 10.0
TOL_LARGURA_MS = 2.0
TOL_PRETRIGGER_AMOSTRAS = 2
# Contraste mínimo (variação relativa da potência) para a largura ser mensurável.
CONTRASTE_MINIMO = 0.05


# ---------------------------------------------------------------------------
# Carregamento (ÚNICO ponto que conhece o formato de arquivo da sessão)
# ---------------------------------------------------------------------------
@dataclass
class Captura:
    id_captura: str
    classe_id: str
    metadado: dict
    registro: np.ndarray  # registro bruto do osciloscópio (com margens), em pu
    arquivo: str = ""
    perfil: str = ""
    inicio_janela: Optional[int] = None  # lido por sessao_io (formato 2 ou 1)
    rotulo: str = ""  # id, ou "id [perfil]" quando a sessão tem mais de um perfil


def carregar_sessao(pasta: Path) -> List[Captura]:
    """Lê a sessão com ``logica/sessao_io.py`` (formato 2, um ``NN_classe.npz``
    por classe, e formato 1, um ``.npz`` por captura): a medida gravada de cada
    captura (registro com a margem) e o metadata do perfil dela. Capturas
    empilhadas (formato simulado) são ignoradas. Com mais de um perfil na
    sessão, o rótulo traz o perfil (``02-0001 [norma]``)."""
    import sessao_io

    pasta = Path(pasta)
    if not (pasta / "metadata").is_dir():
        raise FileNotFoundError(f"{pasta} não parece uma pasta de sessão (sem metadata/)")
    lidas = sessao_io.ler_capturas(pasta, versoes=("medida",))
    capturas = [
        Captura(
            id_captura=lida.id_captura, classe_id=lida.id_captura.split("-")[0], metadado=lida.metadado,
            registro=np.asarray(lida.sinal, dtype=np.float64), arquivo=lida.arquivo.name,
            perfil=lida.perfil, inicio_janela=lida.inicio_janela,
        )
        for lida in lidas if lida.formato != "empilhado" and lida.metadado is not None and not lida.espelho
    ]
    multiplos_perfis = len({c.perfil for c in capturas}) > 1
    for c in capturas:
        c.rotulo = f"{c.id_captura} [{c.perfil}]" if multiplos_perfis else c.id_captura
    return capturas


def janela_da_captura(captura: Captura) -> np.ndarray:
    """Janela nominal (``pontos`` amostras) do registro: ``inicio_janela`` lido
    por ``sessao_io`` (ou do metadata), ou o recorte por ``indice_trigger`` e
    ``pre_trigger_s``."""
    m = captura.metadado
    pontos = int(m["pontos"])
    registro = captura.registro
    inicio = captura.inicio_janela if captura.inicio_janela is not None else m.get("inicio_janela")
    if inicio is not None:
        ini = max(0, min(int(inicio), max(0, registro.size - pontos)))
        return registro[ini : ini + pontos]
    return janela_nominal(
        registro, indice_trigger=int(m.get("indice_trigger", m.get("margem_amostras_antes", 0))),
        pre_trigger_s=float(m.get("pre_trigger_s", 0.0)), pontos=pontos, fs_hz=float(m["fs_hz"]),
    )


# ---------------------------------------------------------------------------
# 1. Classe 18: continuidade de fase
# ---------------------------------------------------------------------------
def _sinal_analitico(x: np.ndarray) -> np.ndarray:
    n = x.size
    espectro = np.fft.fft(x)
    h = np.zeros(n)
    h[0] = 1.0
    if n % 2 == 0:
        h[n // 2] = 1.0
        h[1 : n // 2] = 2.0
    else:
        h[1 : (n + 1) // 2] = 2.0
    return np.fft.ifft(espectro * h)


def continuidade_de_fase(
    janela: np.ndarray, *, fs_hz: float, start_hz: float, end_hz: float,
) -> dict:
    """Salto de fase (graus) na troca ``start_hz`` -> ``end_hz``.

    A troca é esperada no MEIO da janela (``dwell`` = metade da duração, a mesma
    hipótese de ``sinais.forma_programada_nativa``). Ajusta-se uma reta à fase
    desenrolada de cada passo (sem 1,25 ciclo de cada borda e sem 1 ciclo em
    volta do meio) e extrapolam-se as duas até o instante nominal.

    Devolve ``salto_graus`` (fase do 2.º passo menos a do 1.º, em [-180, 180)),
    ``f1_medida_hz``, ``f2_medida_hz`` e ``intersecao_ms``: onde as duas retas se
    cruzam, relativo ao meio da janela. Só a fase não separa "salto de fase" de
    "troca atrasada" (um salto J equivale a uma troca deslocada de
    J/(360*|f2-f1|) s); por isso o resultado traz as duas leituras: se
    ``salto_graus`` é grande e ``intersecao_ms`` é pequeno em módulo, a fase
    SALTOU; se ``intersecao_ms`` é grande e coerente com o salto, a troca
    aconteceu fora do meio com a fase contínua. Levanta ``ValueError`` se a
    janela for curta demais ou ``start_hz == end_hz``."""
    x = np.asarray(janela, dtype=np.float64)
    n = x.size
    if abs(end_hz - start_hz) < 0.5:
        raise ValueError("start_hz e end_hz iguais: não há troca de passo")
    f_med = 0.5 * (start_hz + end_hz)
    ciclo = int(round(fs_hz / f_med))
    if n < 8 * ciclo:
        raise ValueError(f"janela curta demais ({n} amostras, ciclo de {ciclo})")
    t = np.arange(n, dtype=np.float64) / fs_hz
    fase = np.unwrap(np.angle(_sinal_analitico(x - np.mean(x))))
    borda = int(round(1.25 * ciclo))
    meio = n // 2
    guarda = ciclo
    antes = np.arange(borda, meio - guarda)
    depois = np.arange(meio + guarda, n - borda)
    if antes.size < 1.5 * ciclo or depois.size < 1.5 * ciclo:
        raise ValueError("pouco sinal de cada lado da troca para ajustar a fase")
    a1, b1 = np.polyfit(t[antes], fase[antes], 1)
    a2, b2 = np.polyfit(t[depois], fase[depois], 1)
    ts = meio / fs_hz
    salto = (a2 * ts + b2) - (a1 * ts + b1)
    salto = (salto + math.pi) % (2.0 * math.pi) - math.pi
    return {
        "salto_graus": math.degrees(salto),
        "f1_medida_hz": a1 / (2.0 * math.pi),
        "f2_medida_hz": a2 / (2.0 * math.pi),
        "intersecao_ms": -salto / (a2 - a1) * 1000.0,
    }


# ---------------------------------------------------------------------------
# 2. Classes 02-04: largura do pulso
# ---------------------------------------------------------------------------
def largura_medida_do_pulso(
    janela: np.ndarray, *, fs_hz: float, f0_hz: float, inicio_s: float, duracao_s: float,
) -> dict:
    """Largura (s) do evento de nível, medida na janela. Devolve
    ``largura_s`` (``None`` se o contraste for pequeno demais), ``inicio_medido_s``,
    ``contraste`` (variação relativa da amplitude entre regime e evento).

    Amplitude instantânea = módulo do sinal analítico (não oscila com a fase da
    senoide, ao contrário de uma média móvel de x^2, que erra a borda em alguns
    ms), suavizada por 1 ms; o limiar é o ponto médio entre o nível de regime
    (fora do evento) e o do evento (dentro)."""
    x = np.asarray(janela, dtype=np.float64)
    n = x.size
    ciclo = max(2, int(round(fs_hz / f0_hz)))
    amplitude = np.abs(_sinal_analitico(x - np.mean(x)))
    suave = max(1, int(round(0.001 * fs_hz)))
    amplitude = np.convolve(amplitude, np.ones(suave) / suave, mode="same")
    i0 = int(round(inicio_s * fs_hz))
    i1 = int(round((inicio_s + duracao_s) * fs_hz))
    margem = int(round(0.003 * fs_hz))  # 3 ms: transição do evento + resposta da suavização
    ponta = int(round(0.004 * fs_hz))  # efeito de borda da transformada nas pontas da janela
    fora = np.ones(n, dtype=bool)
    fora[max(0, i0 - margem) : min(n, i1 + margem)] = False
    fora[:ponta] = False
    fora[n - ponta :] = False
    if not np.any(fora):
        return {"largura_s": None, "motivo": "sem regime fora do evento para referência"}
    a_regime = float(np.median(amplitude[fora]))
    if i1 - i0 > 2 * margem + ciclo // 2:
        a_evento = float(np.median(amplitude[i0 + margem : i1 - margem]))
    else:  # evento curto (< ~2,5 ciclos): usa o extremo dentro dele
        dentro = amplitude[max(0, i0) : min(n, i1)]
        a_evento = float(dentro.min() if dentro.mean() < a_regime else dentro.max())
    contraste = abs(a_evento - a_regime) / a_regime if a_regime > 0 else float("inf")
    if contraste < CONTRASTE_MINIMO:
        return {"largura_s": None, "contraste": contraste, "motivo": f"contraste {contraste:.1%} < {CONTRASTE_MINIMO:.0%}"}
    limiar = 0.5 * (a_regime + a_evento)
    do_evento = (amplitude < limiar) if a_evento < a_regime else (amplitude > limiar)
    centro = min(n - 1, max(0, (i0 + i1) // 2))
    if not do_evento[centro]:
        return {"largura_s": None, "contraste": contraste, "motivo": "evento não encontrado no centro esperado"}
    ini = centro
    while ini > 0 and do_evento[ini - 1]:
        ini -= 1
    fim = centro
    while fim < n - 1 and do_evento[fim + 1]:
        fim += 1
    return {
        "largura_s": (fim + 1 - ini) / fs_hz, "inicio_medido_s": ini / fs_hz, "contraste": contraste,
    }


# ---------------------------------------------------------------------------
# 3. pre_trigger_desvio_amostras
# ---------------------------------------------------------------------------
def desvio_do_pre_trigger(metadado: dict) -> Optional[int]:
    """``pre_trigger_desvio_amostras`` do metadata; sem ele, a mesma conta de
    ``mestre.py`` (``indice_trigger`` menos ``round(pre_trigger_s*fs) +
    margem_amostras_antes``). ``None`` se faltar ``indice_trigger``."""
    if metadado.get("pre_trigger_desvio_amostras") is not None:
        return int(metadado["pre_trigger_desvio_amostras"])
    if metadado.get("indice_trigger") is None:
        return None
    previsto = int(round(float(metadado.get("pre_trigger_s", 0.0)) * float(metadado["fs_hz"])))
    previsto += int(metadado.get("margem_amostras_antes", 0))
    return int(metadado["indice_trigger"]) - previsto


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
@dataclass
class Resultado:
    verificacao: str
    id_captura: str
    ok: Optional[bool]  # None = não mensurável
    valor: Optional[float]
    limite: float
    unidade: str
    nota: str = ""
    extra: dict = field(default_factory=dict)


def verificar_capturas(
    capturas: Sequence[Captura], *, tol_fase_graus: float = TOL_FASE_GRAUS,
    tol_largura_ms: float = TOL_LARGURA_MS, tol_pretrigger: int = TOL_PRETRIGGER_AMOSTRAS,
) -> List[Resultado]:
    resultados: List[Resultado] = []
    for c in capturas:
        m = c.metadado
        fs = float(m["fs_hz"])
        f0 = float(m.get("f0_hz", 60.0))
        if c.classe_id == CLASSE_DERIVA:
            p = m.get("parametros") or {}
            try:
                r = continuidade_de_fase(
                    janela_da_captura(c), fs_hz=fs, start_hz=float(p["start_hz"]), end_hz=float(p["end_hz"]),
                )
                resultados.append(Resultado(
                    "fase_18", c.rotulo, abs(r["salto_graus"]) <= tol_fase_graus, r["salto_graus"],
                    tol_fase_graus, "graus",
                    f"f1 {r['f1_medida_hz']:.2f} Hz (prog. {p['start_hz']}), f2 {r['f2_medida_hz']:.2f} Hz "
                    f"(prog. {p['end_hz']}), retas se cruzam a {r['intersecao_ms']:+.1f} ms do meio da janela", r,
                ))
            except (KeyError, ValueError) as exc:
                resultados.append(Resultado("fase_18", c.rotulo, None, None, tol_fase_graus, "graus", f"não calculado: {exc}"))
        if c.classe_id in CLASSES_PULSE:
            if m.get("duracao_s") is None or m.get("inicio_disturbio_s") is None:
                resultados.append(Resultado(
                    "largura_pulse", c.rotulo, None, None, tol_largura_ms, "ms",
                    "metadata sem inicio_disturbio_s/duracao_s (sorteio desligado ou sessão antiga)",
                ))
            else:
                r = largura_medida_do_pulso(
                    janela_da_captura(c), fs_hz=fs, f0_hz=f0,
                    inicio_s=float(m["inicio_disturbio_s"]), duracao_s=float(m["duracao_s"]),
                )
                if r.get("largura_s") is None:
                    resultados.append(Resultado("largura_pulse", c.rotulo, None, None, tol_largura_ms, "ms", r["motivo"], r))
                else:
                    erro_ms = (r["largura_s"] - float(m["duracao_s"])) * 1000.0
                    resultados.append(Resultado(
                        "largura_pulse", c.rotulo, abs(erro_ms) <= tol_largura_ms, erro_ms, tol_largura_ms, "ms",
                        f"programada {float(m['duracao_s']) * 1000.0:.2f} ms, medida {r['largura_s'] * 1000.0:.2f} ms", r,
                    ))
        if m.get("pre_trigger_desvio_amostras") is not None or c.classe_id in CLASSES_PULSE:
            desvio = desvio_do_pre_trigger(m)
            if desvio is None:
                resultados.append(Resultado("pre_trigger", c.rotulo, None, None, tol_pretrigger, "amostras", "metadata sem indice_trigger"))
            else:
                origem = "campo" if m.get("pre_trigger_desvio_amostras") is not None else "calculado do metadata"
                resultados.append(Resultado(
                    "pre_trigger", c.rotulo, abs(desvio) <= tol_pretrigger, float(desvio), tol_pretrigger, "amostras", origem,
                ))
    return resultados


def _linha(r: Resultado) -> str:
    estado = "n/d " if r.ok is None else ("OK  " if r.ok else "FALHA")
    valor = "      -" if r.valor is None else f"{r.valor:+8.2f}"
    return f"{estado} {r.verificacao:<14} {r.id_captura:<10} {valor} {r.unidade:<8} (limite +-{r.limite:g})  {r.nota}"


def resumo(resultados: Sequence[Resultado]) -> List[str]:
    linhas = []
    for nome in ("fase_18", "largura_pulse", "pre_trigger"):
        sel = [r for r in resultados if r.verificacao == nome]
        if not sel:
            continue
        valores = np.array([r.valor for r in sel if r.valor is not None])
        ok = sum(1 for r in sel if r.ok)
        nd = sum(1 for r in sel if r.ok is None)
        faixa = f"min {valores.min():+.2f} / mediana {np.median(valores):+.2f} / max {valores.max():+.2f}" if valores.size else "sem valores"
        linhas.append(f"{nome}: {ok}/{len(sel)} OK, {len(sel) - ok - nd} reprovadas, {nd} sem medida; {faixa}")
    return linhas


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("sessao", type=Path, help="pasta resultados\\sessao_<timestamp>[_runNN]")
    parser.add_argument("--tol-fase-graus", type=float, default=TOL_FASE_GRAUS)
    parser.add_argument("--tol-largura-ms", type=float, default=TOL_LARGURA_MS)
    parser.add_argument("--tol-pretrigger-amostras", type=int, default=TOL_PRETRIGGER_AMOSTRAS)
    parser.add_argument("--json", type=Path, default=None, help="grava os resultados também em JSON")
    args = parser.parse_args(argv)

    capturas = carregar_sessao(args.sessao)
    resultados = verificar_capturas(
        capturas, tol_fase_graus=args.tol_fase_graus, tol_largura_ms=args.tol_largura_ms,
        tol_pretrigger=args.tol_pretrigger_amostras,
    )
    print(f"Sessão: {args.sessao}  ({len(capturas)} capturas lidas)")
    for r in resultados:
        print(_linha(r))
    print()
    for linha in resumo(resultados):
        print(linha)
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps([
            {"verificacao": r.verificacao, "id_captura": r.id_captura, "ok": r.ok, "valor": r.valor,
             "limite": r.limite, "unidade": r.unidade, "nota": r.nota} for r in resultados
        ], ensure_ascii=False, indent=2), encoding="utf-8")
    if not resultados:
        print("Nada a verificar: a sessão não tem capturas das classes 02-04 ou 18 nem pre_trigger_desvio_amostras.")
        return 2
    return 1 if any(r.ok is False for r in resultados) else 0


if __name__ == "__main__":
    sys.exit(main())
