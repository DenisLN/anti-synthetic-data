"""s1_logs.py - verificacao independente dos achados B1..B5 do arquivo 00.

- transiente_ativo discrimina alguma coisa?
- ultimo ponto de diagnostico antes de cada excecao (localiza o -113)
- par antes/apos de VOLTage:MODE LIST e de SOURce:MODE ACDC
- custo por query de diagnostico e piso da medida apos_trigger->transiente_concluido

Uso: python docs/analise-2026-09-21/s1_logs.py
Somente leitura.
"""
from __future__ import annotations

import collections
import re
import statistics as st

LOGS = ((r"C:\Users\denis\Desktop\log1.txt", "log1 / sessao 1"),
        (r"C:\Users\denis\Desktop\log2.txt", "log2 / sessao 2"))
DPAT = re.compile(r"\[DIAGNOSTICO\] ponto=(\S+) t=([\d.]+) transiente_ativo=(\S+) "
                  r"output=(\S+) tensao_v=(\S+) extra=(.*)")
CPAT = re.compile(r"Experimento (\d\d) \(")


def parse(path):
    cur = None
    ev = []
    for line in open(path, encoding="utf-8", errors="replace"):
        c = CPAT.search(line)
        if c:
            cur = c.group(1)
        m = re.search(r"\[(\d\d:\d\d:\d\d)\]", line)
        hh = m.group(1) if m else None
        d = DPAT.search(line)
        if d:
            ev.append(dict(cls=cur, ponto=d.group(1), t=float(d.group(2)), ta=d.group(3),
                           out=d.group(4), v=d.group(5), extra=d.group(6), hh=hh, raw=line))
        elif "FALHOU (tentativa" in line or "Falha de infraestrutura" in line:
            ev.append(dict(cls=cur, ponto="<<EXCECAO>>", t=None, ta=None, out=None, v=None,
                           extra=line.strip()[:120], hh=hh, raw=line))
    return ev


for path, rot in LOGS:
    ev = parse(path)
    diag = [e for e in ev if e["ponto"] != "<<EXCECAO>>"]
    print("=" * 78)
    print(f"{rot}: {len(diag)} linhas de diagnostico")
    print("  transiente_ativo:", dict(collections.Counter(e["ta"] for e in diag)))
    print("  output:          ", dict(collections.Counter(e["out"] for e in diag)))
    naovazio = [e for e in diag if re.search(r"'erros': \[\s*\(", e["extra"])]
    print(f"  linhas com extra={{'erros': [...]}} NAO vazio: {len(naovazio)}")
    print("  ultimo ponto de diagnostico ANTES de cada excecao:")
    ult = None
    for e in ev:
        if e["ponto"] == "<<EXCECAO>>":
            print(f"    [{e['hh']}] classe {e['cls']}: ultimo ponto = "
                  f"{ult['ponto'] if ult else '(nenhum)'}  -> {e['extra'][:90]}")
        else:
            ult = e
    # pares antes/apos
    for a, b in (("antes_voltage_mode_list", "apos_voltage_mode_list"),
                 ("antes_sourcemode_acdc", "apos_sourcemode_acdc")):
        va = [float(e["v"]) for e in diag if e["ponto"] == a and e["v"] != "None"]
        vb = [float(e["v"]) for e in diag if e["ponto"] == b and e["v"] != "None"]
        if va or vb:
            print(f"  {a}: n={len(va)} med={st.median(va) if va else float('nan'):.3f}   "
                  f"{b}: n={len(vb)} med={st.median(vb) if vb else float('nan'):.3f}")
    # custo de cada bloco de 3 queries: antes->apos voltage_mode_list = 3 queries + 1 write + 1 check
    gaps = collections.defaultdict(list)
    prev = None
    for e in diag:
        if prev and prev["cls"] == e["cls"] and prev["t"] is not None and e["t"] is not None:
            gaps[(prev["ponto"], e["ponto"])].append(e["t"] - prev["t"])
        prev = e
    print("  gaps mais frequentes (s) min/med/max:")
    for k, v in sorted(gaps.items(), key=lambda kv: -len(kv[1]))[:8]:
        print(f"    {k[0]:>26} -> {k[1]:<26} {min(v):.3f}/{st.median(v):.3f}/{max(v):.3f} n={len(v)}")
    # delta apos_trigger -> transiente_concluido por classe
    by = collections.defaultdict(list)
    lt = {}
    for e in diag:
        if e["ponto"] == "apos_trigger":
            lt[e["cls"]] = e["t"]
        elif e["ponto"] == "transiente_concluido" and e["cls"] in lt:
            by[e["cls"]].append(e["t"] - lt[e["cls"]])
    print("  Delta(apos_trigger -> transiente_concluido) por classe [s]:")
    for k, v in sorted(by.items()):
        print(f"    {k}: n={len(v):3d} min={min(v):.3f} med={st.median(v):.3f} max={max(v):.3f}")
    print()
