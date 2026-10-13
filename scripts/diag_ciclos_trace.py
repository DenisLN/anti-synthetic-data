"""Diagnóstico offline (só leitura): qual ciclo PROGRAMADO explica cada ciclo
MEDIDO de uma captura TRACe/LIST?

Contexto (CHANGELOG/v1.15.md, "Diagnóstico da cópia do evento em 100 ms"): nas
capturas de 07/10 o início do evento da 08 e da 09 aparece repetido ou
deslocado em 100,0 ms. A montagem da TRACE está descartada como causa; este
script olha o que a fonte FEZ, ciclo a ciclo.

Para cada captura TRACe de uma sessão (``resultados/sessao_*``), alinha a
medida em ``inicio_janela`` e compara cada ciclo medido k com

  * ``k-1``, ``k`` e ``k+1``: os ciclos da forma PROGRAMADA (o que a fonte deve
    emitir, ``AmetekMX30.montar_programacao`` -> ``programada_pu``);
  * ``k_sem_dc``: o ciclo k da forma de bancada (pré-TRACe, reconstruída pelo
    metadata) sem a média (a fonte remove o DC da TRACE), quando dá para
    reconstruí-la.

Lista, por captura: qual candidato explica melhor cada ciclo, a partir de que
instante há troca (ciclo e primeira amostra divergente), e o resíduo
(medida - programada) em torno de ``--instante-ms`` (padrão 100 ms). Um
candidato diferente de ``k`` só vence se reduzir o resíduo em mais de
``--margem-empate`` (ciclos de senoide pura são idênticos entre si e empatam;
nesse caso vale ``k``).

Só leitura: não abre a pasta da sessão para escrita; os resultados vão para
``--saida`` (padrão ``logs/``). Não toca hardware. Rodar em PowerShell, na raiz:

    env\\Scripts\\python.exe scripts\\diag_ciclos_trace.py resultados\\sessao_2026-10-07_127V_50Hz --classes 08,09

Saída: tabela em markdown no terminal e ``diag_ciclos_trace-<sessao>.md`` /
``.json`` em ``--saida``.

O carregamento da sessão está isolado em ``carregar_sessao()`` (a única função
que conhece o formato em disco), para ser trocada se o formato mudar.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
for _pasta in (RAIZ / "logica", RAIZ / "scripts"):
    if str(_pasta) not in sys.path:
        sys.path.insert(0, str(_pasta))

FS_PADRAO_HZ = 30_000.0


class CapturaSessao:
    """Uma captura TRACe pronta para a análise (tudo em pu, grade da captura).
    Classe simples (sem ``dataclass``) para o módulo poder ser carregado por
    ``importlib`` sem entrar em ``sys.modules``."""

    def __init__(
        self, id_captura: str, classe: str, f0_hz: float, fs_hz: float, tensao_base_rms: float, inicio_janela: int,
        medida_pu: np.ndarray, programada_pu: np.ndarray, forma_bancada_pu: Optional[np.ndarray] = None,
        dc_offset_pu: float = 0.0, origem_programada: str = "", avisos: Optional[List[str]] = None,
    ):
        self.id_captura, self.classe = id_captura, classe
        self.f0_hz, self.fs_hz, self.tensao_base_rms = f0_hz, fs_hz, tensao_base_rms
        self.inicio_janela = inicio_janela
        self.medida_pu, self.programada_pu, self.forma_bancada_pu = medida_pu, programada_pu, forma_bancada_pu
        self.dc_offset_pu, self.origem_programada = dc_offset_pu, origem_programada
        self.avisos = list(avisos or [])


# ---------------------------------------------------------------------------
# Carregamento da sessão (isolado: adaptar aqui se o formato em disco mudar)
# ---------------------------------------------------------------------------
def _inicio_da_janela(registro: dict, total: int, pontos: int, fs_hz: float) -> int:
    inicio = registro.get("inicio_janela")
    if inicio is None:
        indice = registro.get("indice_trigger")
        if indice is None:
            inicio = registro.get("margem_amostras_antes", 0)
        else:
            inicio = int(round(int(indice) - float(registro.get("pre_trigger_s", 0.0)) * fs_hz))
    return max(0, min(int(inicio), max(0, total - pontos)))


def carregar_sessao(sessao_dir: Path, *, classes: Optional[Sequence[str]] = None, usar_forma_bancada: bool = True) -> List[CapturaSessao]:
    """Lê ``metadata/*.jsonl`` + ``.npz`` (+ ``tres_versoes/`` quando existe) e
    devolve só as capturas TRACe/LIST (programada vinda de ``montar_programacao``).

    * medida: ``tres_versoes/<arquivo>.npz::medida_pu`` se existir; senão o
      ``tensao_pu`` bruto do ``.npz`` recortado em ``inicio_janela``;
    * programada: ``tres_versoes/...::programada_pu`` se existir; senão
      reconstruída por ``gerar_tres_versoes.reconstruir_versoes`` (metadata);
    * forma de bancada (candidato ``k_sem_dc``): sempre por
      ``reconstruir_versoes``; se não der, ``None`` e a captura segue sem ele.
    """
    import gerar_tres_versoes as gtv

    sessao_dir = Path(sessao_dir)
    registros = [r for r in gtv._registros_da_sessao(sessao_dir) if not r.get("simulado")]
    nomes = gtv._nomes_dos_npz(sessao_dir)
    filtro = {c.zfill(2) for c in classes} if classes else None
    capturas: List[CapturaSessao] = []
    for registro in registros:
        id_captura = str(registro["id_captura"])
        classe_id = id_captura.split("-")[0]
        if filtro is not None and classe_id not in filtro:
            continue
        fs_hz = float(registro.get("fs_hz", FS_PADRAO_HZ))
        pontos = int(registro["pontos"])
        avisos: List[str] = []

        tres = None
        arquivo_tres = (registro.get("tres_versoes") or {}).get("arquivo")
        if arquivo_tres and (sessao_dir / arquivo_tres).is_file():
            with np.load(sessao_dir / arquivo_tres, allow_pickle=True) as dados:
                tres = {chave: np.array(dados[chave]) for chave in dados.files}

        reconstruido = None
        if tres is None or "programada_pu" not in tres or usar_forma_bancada:
            try:
                reconstruido = gtv.reconstruir_versoes(registro)
            except Exception as exc:  # noqa: BLE001 - sem isso só falta o candidato k_sem_dc
                avisos.append(f"forma não reconstruída do metadata ({type(exc).__name__}: {exc})")

        if tres is not None and "programada_pu" in tres:
            programada = np.asarray(tres["programada_pu"], dtype=np.float64).reshape(-1)[:pontos]
            origem = str(tres.get("origem_programada", "")) or str((registro.get("tres_versoes") or {}).get("programada") or "")
        elif reconstruido is not None:
            programada = np.asarray(reconstruido["programada"], dtype=np.float64)
            origem = str(reconstruido["origem"])
        else:
            avisos.append("sem programada (nem tres_versoes nem reconstrução); captura ignorada")
            continue
        if "TRACe" not in origem:
            continue  # nativa: não há ciclos de TRACE para comparar

        if tres is not None and "medida_pu" in tres:
            medida = np.asarray(tres["medida_pu"], dtype=np.float64).reshape(-1)[:pontos]
            inicio = int(np.asarray(tres.get("inicio_janela", registro.get("inicio_janela", 0))))
        else:
            nome = nomes.get(id_captura)
            if nome is None:
                avisos.append("sem .npz da captura; ignorada")
                continue
            with np.load(sessao_dir / nome, allow_pickle=True) as dados:
                bruto = np.asarray(dados["tensao_pu"], dtype=np.float64).reshape(-1)
            inicio = _inicio_da_janela(registro, bruto.size, pontos, fs_hz)
            medida = bruto[inicio : inicio + pontos]
        capturas.append(CapturaSessao(
            id_captura=id_captura, classe=classe_id, f0_hz=float(registro.get("f0_hz", 60.0)), fs_hz=fs_hz,
            tensao_base_rms=float(registro.get("tensao_base_rms", 127.0)), inicio_janela=inicio,
            medida_pu=medida, programada_pu=programada,
            forma_bancada_pu=(np.asarray(reconstruido["forma_bancada"], dtype=np.float64) if reconstruido is not None else None),
            dc_offset_pu=float((registro.get("parametros") or {}).get("dc_offset_pu", 0.0)),
            origem_programada=origem, avisos=avisos,
        ))
    return capturas


# ---------------------------------------------------------------------------
# Análise (pura)
# ---------------------------------------------------------------------------
def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)))) if x.size else float("nan")


def analisar_captura(
    cap: CapturaSessao, *, tol_rms_pu: float = 0.03, margem_empate_pu: float = 0.01,
    limiar_amostra_pu: float = 0.05, instante_ms: float = 100.0, janela_ms: float = 2.0,
) -> dict:
    """Ciclo a ciclo: o resíduo rms de cada candidato e o vencedor. Um ciclo é
    ``ok`` (k explica), ``trocado`` (k-1 ou k+1 explica melhor por mais que
    ``margem_empate_pu``), ``ok_sem_dc`` (só ``k_sem_dc`` fica ao nível de k) ou
    ``sem_explicacao`` (nenhum candidato fica abaixo de ``tol_rms_pu``)."""
    n = int(round(cap.fs_hz / cap.f0_hz))
    ciclos = min(len(cap.medida_pu), len(cap.programada_pu)) // n
    medida = np.asarray(cap.medida_pu[: ciclos * n], dtype=np.float64).reshape(ciclos, n)
    prog = np.asarray(cap.programada_pu[: ciclos * n], dtype=np.float64).reshape(ciclos, n)
    bancada = None
    if cap.forma_bancada_pu is not None and len(cap.forma_bancada_pu) >= ciclos * n:
        bruto = np.asarray(cap.forma_bancada_pu[: ciclos * n], dtype=np.float64).reshape(ciclos, n)
        bancada = bruto - bruto.mean(axis=1, keepdims=True) + cap.dc_offset_pu

    por_ciclo = []
    for k in range(ciclos):
        candidatos: Dict[str, float] = {}
        if k > 0:
            candidatos["k-1"] = _rms(medida[k] - prog[k - 1])
        candidatos["k"] = _rms(medida[k] - prog[k])
        if k < ciclos - 1:
            candidatos["k+1"] = _rms(medida[k] - prog[k + 1])
        if bancada is not None:
            candidatos["k_sem_dc"] = _rms(medida[k] - bancada[k])
        melhor = min(candidatos, key=candidatos.get)
        if melhor != "k" and candidatos["k"] - candidatos[melhor] <= margem_empate_pu:
            melhor = "k"
        if candidatos[melhor] > tol_rms_pu:
            estado = "sem_explicacao"
        elif melhor in ("k-1", "k+1"):
            estado = "trocado"
        elif melhor == "k_sem_dc":
            estado = "ok_sem_dc"
        else:
            estado = "ok"
        por_ciclo.append({
            "ciclo": k, "inicio_ms": 1000.0 * k * n / cap.fs_hz, "melhor": melhor, "estado": estado,
            "residuo_rms_pu": {nome: round(valor, 6) for nome, valor in candidatos.items()},
        })

    trocados = [c for c in por_ciclo if c["estado"] == "trocado"]
    troca = None
    if trocados:
        k = trocados[0]["ciclo"]
        diverge = np.nonzero(np.abs(medida[k] - prog[k]) > limiar_amostra_pu)[0]
        amostra = int(k * n + diverge[0]) if diverge.size else int(k * n)
        troca = {
            "primeiro_ciclo": k, "explicado_por": trocados[0]["melhor"],
            "instante_ciclo_ms": 1000.0 * k * n / cap.fs_hz,
            "primeira_amostra_divergente": amostra,
            "instante_divergente_ms": 1000.0 * amostra / cap.fs_hz,
            "ciclos_trocados": [c["ciclo"] for c in trocados],
        }

    residuo = (np.asarray(cap.medida_pu[: ciclos * n]) - np.asarray(cap.programada_pu[: ciclos * n]))
    i0 = int(round(instante_ms * cap.fs_hz / 1000.0))
    ini = max(0, i0 - int(round(0.5 * cap.fs_hz / 1000.0)))
    fim = min(residuo.size, i0 + int(round(janela_ms * cap.fs_hz / 1000.0)))
    janela = np.abs(residuo[ini:fim]) if fim > ini else np.zeros(0)
    sem_dc = None
    if janela.size:
        pos = ini + int(np.argmax(janela))
        sem_dc = {"max_abs_pu": float(janela.max()), "amostra": pos, "instante_ms": 1000.0 * pos / cap.fs_hz}
    global_pos = int(np.argmax(np.abs(residuo)))
    return {
        "id_captura": cap.id_captura, "classe": cap.classe, "f0_hz": cap.f0_hz, "ciclos": ciclos,
        "pontos_por_ciclo": n, "inicio_janela": cap.inicio_janela,
        "candidato_k_sem_dc": bancada is not None, "ciclos_detalhe": por_ciclo, "troca": troca,
        "residuo_no_instante": {"instante_ms": instante_ms, **(sem_dc or {})},
        "residuo_global": {
            "max_abs_pu": float(abs(residuo[global_pos])), "amostra": global_pos,
            "instante_ms": 1000.0 * global_pos / cap.fs_hz,
        },
        "avisos": list(cap.avisos),
    }


def analisar_sessao_dir(sessao_dir: Path, *, classes: Optional[Sequence[str]] = None, **opcoes) -> List[dict]:
    return [analisar_captura(cap, **opcoes) for cap in carregar_sessao(sessao_dir, classes=classes)]


# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------
def montar_markdown(sessao: str, resultados: List[dict]) -> str:
    linhas = [f"# Ciclos medidos x programados: {sessao}", ""]
    linhas.append(
        "| captura | f0 (Hz) | ciclos trocados | 1.º ciclo trocado | explicado por | instante do ciclo (ms) "
        "| 1.ª amostra divergente (ms) | resíduo máx. em torno de 100 ms (pu) | onde (ms) | resíduo máx. global (pu) | onde (ms) |"
    )
    linhas.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in resultados:
        t, ri, rg = r["troca"], r["residuo_no_instante"], r["residuo_global"]
        if t:
            parte = (
                f"{', '.join(map(str, t['ciclos_trocados']))} | {t['primeiro_ciclo']} | {t['explicado_por']} "
                f"| {t['instante_ciclo_ms']:.1f} | {t['instante_divergente_ms']:.2f}"
            )
        else:
            parte = "nenhum | - | - | - | -"
        linhas.append(
            f"| {r['id_captura']} | {r['f0_hz']:g} | {parte} "
            f"| {ri.get('max_abs_pu', float('nan')):.4f} | {ri.get('instante_ms', float('nan')):.2f} "
            f"| {rg['max_abs_pu']:.4f} | {rg['instante_ms']:.2f} |"
        )
    for r in resultados:
        anormais = [c for c in r["ciclos_detalhe"] if c["estado"] != "ok"]
        if not anormais:
            continue
        linhas += ["", f"## {r['id_captura']}: ciclos que não são simplesmente k", "",
                   "| ciclo | início (ms) | estado | melhor | resíduo rms por candidato (pu) |", "|---|---|---|---|---|"]
        for c in anormais:
            res = ", ".join(f"{nome}={valor:.4f}" for nome, valor in c["residuo_rms_pu"].items())
            linhas.append(f"| {c['ciclo']} | {c['inicio_ms']:.1f} | {c['estado']} | {c['melhor']} | {res} |")
        for aviso in r["avisos"]:
            linhas.append(f"\nAviso: {aviso}")
    return "\n".join(linhas) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sessao_dir", type=Path, help="pasta resultados/sessao_... (com metadata/)")
    ap.add_argument("--classes", default=None, help="ids separados por vírgula (padrão: todas as com TRACe)")
    ap.add_argument("--instante-ms", type=float, default=100.0)
    ap.add_argument("--janela-ms", type=float, default=2.0)
    ap.add_argument("--tol-rms-pu", type=float, default=0.03)
    ap.add_argument("--margem-empate", type=float, default=0.01)
    ap.add_argument("--limiar-amostra-pu", type=float, default=0.05)
    ap.add_argument("--sem-forma-bancada", action="store_true", help="não reconstrói a forma de bancada (sem o candidato k_sem_dc)")
    ap.add_argument("--saida", type=Path, default=RAIZ / "logs")
    args = ap.parse_args(argv)
    if not (args.sessao_dir / "metadata").is_dir():
        ap.error(f"{args.sessao_dir} não parece uma sessão (sem metadata/)")
    classes = [c.strip() for c in args.classes.split(",")] if args.classes else None
    capturas = carregar_sessao(args.sessao_dir, classes=classes, usar_forma_bancada=not args.sem_forma_bancada)
    if not capturas:
        print("Nenhuma captura TRACe/LIST encontrada.")
        return 1
    resultados = [
        analisar_captura(
            c, tol_rms_pu=args.tol_rms_pu, margem_empate_pu=args.margem_empate,
            limiar_amostra_pu=args.limiar_amostra_pu, instante_ms=args.instante_ms, janela_ms=args.janela_ms,
        ) for c in capturas
    ]
    nome = args.sessao_dir.resolve().name
    texto = montar_markdown(nome, resultados)
    print(texto)
    args.saida.mkdir(parents=True, exist_ok=True)
    (args.saida / f"diag_ciclos_trace-{nome}.md").write_text(texto, encoding="utf-8")
    (args.saida / f"diag_ciclos_trace-{nome}.json").write_text(
        json.dumps({"sessao": nome, "capturas": resultados}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Resultados: {args.saida / ('diag_ciclos_trace-' + nome)}.md | .json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
