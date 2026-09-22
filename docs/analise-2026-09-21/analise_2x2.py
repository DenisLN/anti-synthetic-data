"""Analisa o teste 2x2 de bancada (margin on/off x diagnostico on/off) das classes
02 (PULSe nativo) e 07 (LIST) — offline, sem hardware.

Como coletar (na bancada, mesma sessao de CLI ou sessoes diferentes; a saida deve ficar
ligada so durante cada `run`):
  set margin off|on ; set diagnostico off|on ; run 02 ; (copiar o .npz gerado) ; run 07 ; (copiar)
Copie cada .npz gerado para uma pasta unica com o nome:
  02_margin-<on|off>_diag-<on|off>[_rN].npz   e   07_margin-<on|off>_diag-<on|off>[_rN].npz
(o `_rN` opcional serve para repeticoes da mesma configuracao; faca >=3 repeticoes de cada.)
Como o nome interno do .npz do CLI colide entre runs da mesma sessao, copie logo depois de cada run.

Uso: python analise_2x2.py <pasta_com_os_npz> --f0 60
Saida: tabela com, por arquivo, tamanho do registro, onset da saida (07), pulso detectado (02).
Leitura: se o pulso de 02 so some com diag=on (qualquer margem) -> H-DIAG; se so some com margin=on
(qualquer diag) -> H-MARGIN; se o onset de 07 fica ~pre_trigger+20 ms com diag=off e ~pre_trigger+100 ms
com diag=on -> as leituras pos-*TRG atrasam o transiente.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from analise_trim import FS, event_span, half_cycle_peaks, onset_index  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta")
    ap.add_argument("--f0", type=float, default=60.0)
    a = ap.parse_args()
    linhas = []
    for f in sorted(glob.glob(os.path.join(a.pasta, "*.npz"))):
        nome = os.path.basename(f)
        m = re.match(r"(\d\d)_margin-(on|off)_diag-(on|off)(?:_r(\d+))?\.npz$", nome)
        if not m:
            print(f"(ignorado: {nome})")
            continue
        cid, margin, diag, rep = m.groups()
        x = np.load(f, allow_pickle=True)["tensao_pu"]
        x = x[0] if x.ndim == 2 else x
        n = len(x)
        if cid == "02":
            sp = event_span(x, a.f0, "sag")
            t, pk = half_cycle_peaks(x, a.f0)
            med = float(np.median(pk))
            det = "SIM" if sp else "NAO"
            det += f" [{sp[0]:.0f}-{sp[1]:.0f} ms]" if sp else ""
            linhas.append((cid, margin, diag, rep or "-", n, "-", det, f"env_min/med={pk.min() / med:.2f}"))
        else:
            on = onset_index(x, a.f0)
            linhas.append((cid, margin, diag, rep or "-", n,
                           f"{on / FS * 1000:.1f} ms" if on is not None else "sem onset", "-", ""))
    print(f"{'cls':3s} {'margin':6s} {'diag':4s} {'rep':3s} {'n':>6s} {'onset(07)':>12s} {'pulso(02)':>22s}  extra")
    for l in sorted(linhas, key=lambda r: (r[0], r[1], r[2], r[3])):
        print(f"{l[0]:3s} {l[1]:6s} {l[2]:4s} {l[3]:3s} {l[4]:6d} {l[5]:>12s} {l[6]:>22s}  {l[7]}")


if __name__ == "__main__":
    main()
