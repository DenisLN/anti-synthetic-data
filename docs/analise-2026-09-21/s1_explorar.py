"""s1_explorar.py - inspeciona o formato dos .npz e do metadata das sessoes.

Uso:
    python docs/analise-2026-09-21/s1_explorar.py
Somente leitura. Nao toca hardware.
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
S1 = ROOT / "resultados" / "sessao_2026-09-16_16-07-44"
S2 = ROOT / "resultados" / "sessao_2026-09-16_16-16-16"
ANTIGO = Path(r"C:\Users\denis\Documents\1 Projetos\anti-synthetic-data\resultados")


def dump(p: Path, n=1):
    z = np.load(p, allow_pickle=True)
    print(f"--- {p.name}")
    for k in z.files:
        v = z[k]
        print(f"    {k}: shape={getattr(v,'shape',None)} dtype={getattr(v,'dtype',None)}")
        if v.ndim <= 1 and v.size <= 6:
            print(f"        {v}")
    return z


if __name__ == "__main__":
    print("== SESSAO 1 ==")
    f = sorted(glob.glob(str(S1 / "*.npz")))
    print(len(f), "arquivos")
    dump(Path(f[0]))
    print("== metadata s1 ==")
    for p in sorted(glob.glob(str(S1 / "metadata" / "*.jsonl")))[:3]:
        line = open(p, encoding="utf-8").readline()
        print(os.path.basename(p), json.loads(line))
    print()
    print("== SESSAO 2 ==")
    f2 = sorted(glob.glob(str(S2 / "*.npz")))
    print(len(f2), "arquivos")
    dump(Path(f2[0]))
    print("== metadata s2 ==")
    for p in sorted(glob.glob(str(S2 / "metadata" / "*.jsonl"))):
        lines = open(p, encoding="utf-8").read().strip().splitlines()
        print(os.path.basename(p), len(lines), "linhas;", json.loads(lines[0]))
    print()
    print("== ANTIGOS (2026-09-09) ==")
    fa = sorted(glob.glob(str(ANTIGO / "*.npz")))
    print(len(fa), "arquivos")
    for p in fa:
        z = np.load(p, allow_pickle=True)
        print(" ", os.path.basename(p), {k: getattr(z[k], "shape", None) for k in z.files})
    print("== metadata antigos ==")
    for p in sorted(glob.glob(str(ANTIGO / "metadata" / "*.jsonl")))[:4]:
        lines = open(p, encoding="utf-8").read().strip().splitlines()
        print(os.path.basename(p), len(lines), json.loads(lines[0]))
