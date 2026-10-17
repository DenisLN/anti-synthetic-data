"""Gera OFFLINE o AWGN de 20, 30 e 40 dB (padrão) só na JANELA rotulada de cada
captura de uma sessão, a partir do `.npz` limpo e do metadata.

Mesma conta da bancada (`sinais.ruido_na_janela`, que o `mestre.py` também
usa): potência de referência = mean(janela**2), seed do ruído =
`seed + round(snr*1000) + 50_000_000` com a `seed` gravada da captura. A
janela é a nominal de `points` amostras que começa em `inicio_janela` (sessões
antigas, sem esse campo: o mesmo recorte de `recortar_margem.calcular_recorte`).
As margens NÃO entram nos arquivos com ruído (`arquivo/analises:docs/analise-2026-10-12/resolvido/snr_mudancas.md`).

Lê os dois formatos de sessão (``logica/sessao_io.py``): a de um ``.npz`` por
captura (anterior à v1.15) e a de um ``NN_classe.npz`` por classe com perfis.
A saída segue o formato da entrada: ``snr_XXdb/<mesmo nome do .npz>`` com
``tensao_pu`` na sessão antiga e ``snr_XXdb/NN_classe.npz`` com
``<perfil>/tensao_pu`` na nova.

Sem hardware e sem alterar um byte da sessão: a saída vai para uma pasta NOVA
(`<sessao>/ruido_janela/` por padrão; recusa uma pasta que já tenha arquivos,
a menos que `--refazer`):

    ruido_janela/snr_20db/<mesmo nome do .npz>   tempo_ms, tensao_pu (1, points), classe, id_captura
    ruido_janela/snr_30db/...
    ruido_janela/snr_40db/...
    ruido_janela/metadata/<NN_classe>.jsonl      linha original + snr_medido_db / snr_bancada_db / snr_efetivo_db / ruido_janela
    ruido_janela/indice.json                     procedência e SNRs por captura

Uso (na raiz do projeto):
    env\\Scripts\\python scripts\\gerar_ruido_janela.py resultados\\sessao_2026-10-07_127V_50Hz
    env\\Scripts\\python scripts\\gerar_ruido_janela.py resultados\\sessao_... --snr 20,30,40 --saida outra_pasta
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "logica"))

import mestre  # noqa: E402
import sessao_io  # noqa: E402
from recortar_margem import calcular_recorte, metadado_recortado  # noqa: E402
from sinais import ruido_na_janela  # noqa: E402

PASTA_SAIDA_PADRAO = "ruido_janela"
NIVEIS_PADRAO_DB = (20.0, 30.0, 40.0)


def rotulo_do_nivel(snr_db: float) -> str:
    return str(int(snr_db)) if float(snr_db).is_integer() else str(snr_db).replace(".", "_")


def _gravar_npz(destino: Path, **arrays) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(".npz.part")
    with parcial.open("wb") as handle:
        np.savez(handle, **arrays)
    os.replace(parcial, destino)


def gerar_sessao(
    sessao_dir: Path, saida: Path, niveis_db: Sequence[float] = NIVEIS_PADRAO_DB, *, refazer: bool = False,
) -> List[dict]:
    sessao_dir, saida = sessao_dir.resolve(), saida.resolve()
    if saida == sessao_dir or (sessao_dir in saida.parents and saida.parent != sessao_dir):
        raise ValueError("A saída tem de ser uma pasta nova diretamente dentro da sessão (ou fora dela)")
    if saida.is_dir() and any(saida.iterdir()):
        if not refazer:
            raise FileExistsError(f"{saida} já tem arquivos; use --refazer para regenerar (só sobrescreve o que este script grava)")
        if not (saida / "indice.json").is_file():
            raise FileExistsError(f"{saida} tem arquivos que este script não gravou (sem indice.json); recuso")
    metadados = sessao_io.carregar_metadados(sessao_dir)
    if not metadados:
        raise FileNotFoundError(f"{sessao_dir}: nenhum metadata/*.jsonl")

    linhas: List[dict] = []
    metadados_saida: Dict[Tuple[str, str], dict] = {}
    por_arquivo: Dict[Path, List[sessao_io.CapturaSessao]] = {}
    espelhos: Dict[Path, Dict[str, List[str]]] = {}  # arquivo -> origem -> perfis espelho
    for captura in sessao_io.ler_pasta(sessao_dir, metadados, versoes=("medida",)):
        if captura.espelho:  # mesma captura de outro perfil: o ruído é gerado uma vez, na origem
            destinos = espelhos.setdefault(captura.arquivo, {}).setdefault(str(captura.perfil_de_origem), [])
            if captura.perfil not in destinos:
                destinos.append(captura.perfil)
            continue
        if captura.grandeza == "Tensão" and "medida" in captura.versoes:
            por_arquivo.setdefault(captura.arquivo, []).append(captura)

    for npz_path, capturas in sorted(por_arquivo.items()):
        with ExitStack() as recursos:
            escritor = None
            por_nivel: Dict[float, List[np.ndarray]] = {snr: [] for snr in niveis_db}
            for captura in capturas:
                id_captura, metadado = captura.id_captura, captura.metadado
                if metadado is None or "seed" not in metadado:
                    raise KeyError(f"{npz_path.name}: {id_captura} sem metadata com seed; não há como reproduzir o ruído")
                medida = captura.versoes["medida"]
                inicio, pontos, info = calcular_recorte(medida.size, metadado)
                resultado = ruido_na_janela(
                    medida, inicio, pontos, niveis_db, int(metadado["seed"]),
                    simulado=bool(metadado.get("simulado", False)),
                )
                for snr_db, janela_ruidosa in resultado["janelas"].items():
                    por_nivel[snr_db].append(janela_ruidosa)
                novo = metadado_recortado(metadado, info)
                novo.update(resultado["metadata"])
                novo["ruido_janela"]["origem_recorte"] = info["origem"]
                novo["ruido_janela"]["recorte_ajustado"] = bool(info["ajustado"])
                novo["ruido_janela"]["gerado_offline"] = True
                metadados_saida[captura.chave] = novo
                fs_hz = float(metadado.get("fs_hz", 30_000.0))
                if captura.formato == "classe":
                    if escritor is None:
                        escritor = recursos.enter_context(sessao_io.ArquivoDaClasse(
                            saida, captura.classe_id, captura.classe, spool=False))
                    escritor.adicionar(
                        captura.perfil, id_captura=id_captura, medida=medida[:0], tempo_ms=np.arange(1.0), fs_hz=fs_hz,
                        pontos=pontos, snr=resultado["janelas"], inicio_janela=inicio,
                    )
                linhas.append({
                    "id_captura": id_captura, "perfil": captura.perfil, "arquivo": npz_path.name,
                    "inicio_janela": inicio, "pontos": pontos,
                    "origem_recorte": info["origem"], "recorte_ajustado": bool(info["ajustado"]),
                    "snr_acrescentado_db": resultado["metadata"]["snr_medido_db"],
                    "snr_bancada_db": resultado["metadata"]["snr_bancada_db"],
                    "snr_efetivo_db": resultado["metadata"]["snr_efetivo_db"],
                    "margem_bancada": (resultado["metadata"]["ruido_janela"]["bancada"] or {}).get("margem"),
                })
            if escritor is not None:
                for origem, destinos in espelhos.get(npz_path, {}).items():
                    if origem in escritor.perfis:
                        escritor.espelhar(origem, destinos)
                escritor.consolidar(so_snr=True)
                continue
            # Formato antigo (um .npz por captura, ou o simulado empilhado): mesma
            # estrutura e mesmo nome de arquivo da entrada.
            ids = [c.id_captura for c in capturas]
            fs_hz = float(capturas[0].metadado.get("fs_hz", 30_000.0))
            for snr_db, janelas in por_nivel.items():
                pontos = janelas[0].size
                _gravar_npz(
                    saida / f"snr_{rotulo_do_nivel(snr_db)}db" / npz_path.name,
                    classe=capturas[0].classe, id_captura=np.array(ids, dtype=object),
                    tempo_ms=np.arange(pontos, dtype=np.float64) / fs_hz * 1000.0,
                    tensao_pu=np.vstack(janelas),
                )

    metadata_origem = sessao_dir / "metadata"
    (saida / "metadata").mkdir(parents=True, exist_ok=True)
    for jsonl_path in sorted(metadata_origem.glob("*.jsonl")):
        saidas = []
        for texto in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not texto.strip():
                continue
            registro = json.loads(texto)
            chave = (str(registro.get("perfil") or sessao_io.PERFIL_LEGADO), str(registro["id_captura"]))
            origem = registro.get("perfil_de_origem")
            if chave in metadados_saida:  # só as que têm .npz limpo na sessão
                saidas.append(json.dumps(metadados_saida[chave], ensure_ascii=False, sort_keys=True))
            elif origem and origem != chave[0] and (origem, chave[1]) in metadados_saida:
                # Espelho (captura compartilhada): a linha da origem, sob o perfil dele.
                espelho = dict(metadados_saida[(origem, chave[1])], perfil=chave[0])
                saidas.append(json.dumps(espelho, ensure_ascii=False, sort_keys=True))
        if saidas:
            (saida / "metadata" / jsonl_path.name).write_text("\n".join(saidas) + "\n", encoding="utf-8")

    codigo = mestre.info_do_codigo()
    indice = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "sessao": sessao_dir.name, "script": "scripts/gerar_ruido_janela.py",
        "niveis_db": [float(n) for n in niveis_db],
        "git_commit": codigo["git_commit"], "git_sujo": codigo["git_sujo"],
        "capturas": linhas,
    }
    (saida / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return linhas


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sessao_dir", type=Path, help="pasta resultados/sessao_... (com metadata/)")
    parser.add_argument("--snr", default=",".join(str(int(n)) for n in NIVEIS_PADRAO_DB), help="níveis em dB, separados por vírgula")
    parser.add_argument("--saida", type=Path, default=None, help=f"pasta de saída (padrão: <sessao>/{PASTA_SAIDA_PADRAO}/)")
    parser.add_argument("--refazer", action="store_true", help="aceita uma saída que já tem arquivos deste script")
    args = parser.parse_args(argv)
    if not (args.sessao_dir / "metadata").is_dir():
        parser.error(f"{args.sessao_dir} não parece uma sessão (sem metadata/)")
    niveis = tuple(float(n) for n in args.snr.split(",") if n.strip())
    saida = args.saida if args.saida is not None else args.sessao_dir / PASTA_SAIDA_PADRAO
    linhas = gerar_sessao(args.sessao_dir, saida, niveis, refazer=args.refazer)

    def fmt(valor: Optional[float]) -> str:
        return "   -  " if valor is None else f"{valor:6.2f}"

    cabecalho = "".join(f"  ef{int(n):>3}" for n in niveis)
    print(f"{'id_captura':<11}{'arquivo':<50}{'ini':>5}{'banc.':>8}{cabecalho}  margem")
    for l in linhas:
        efetivos = "".join(f"  {fmt(l['snr_efetivo_db'][str(n)])}" for n in niveis)
        print(f"{l['id_captura']:<11}{l['arquivo'][:48]:<50}{l['inicio_janela']:>5}{fmt(l['snr_bancada_db']):>8}{efetivos}  {l['margem_bancada'] or '-'}")
    bancadas = [l["snr_bancada_db"] for l in linhas if l["snr_bancada_db"] is not None]
    if bancadas:
        print(f"\nSNR da bancada: min {min(bancadas):.2f} / mediana {float(np.median(bancadas)):.2f} / max {max(bancadas):.2f} dB ({len(bancadas)} capturas)")
    print(f"{len(linhas)} captura(s), níveis {list(niveis)} dB, em {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
