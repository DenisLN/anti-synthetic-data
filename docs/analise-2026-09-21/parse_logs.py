"""Parseia log1.txt/log2.txt (console da bancada) e mede o que os pontos
[DIAGNOSTICO] realmente medem. Uso: python parse_logs.py log1.txt log2.txt"""
import re, sys, collections, statistics as st

pat = re.compile(r"\[(\d\d:\d\d:\d\d)\] \[(\w+)\] (.*)")
dpat = re.compile(r"\[DIAGNOSTICO\] ponto=(\S+) t=([\d.]+) transiente_ativo=(\S+) output=(\S+) tensao_v=(\S+) extra=(.*)")
cpat = re.compile(r"Experimento (\d\d) \((\w+)\)")


def parse(path):
    cur = None
    ev = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = pat.match(line.strip())
        if not m:
            continue
        hhmmss, lvl, msg = m.groups()
        c = cpat.search(msg)
        if c:
            cur = (c.group(1), c.group(2))
        d = dpat.search(msg)
        if d:
            ponto, t, ta, out, v, extra = d.groups()
            ev.append(dict(cls=cur, ponto=ponto, t=float(t), ta=ta, out=out,
                           v=None if v == "None" else float(v), hh=hhmmss))
    return ev


def main():
    for path in sys.argv[1:]:
        ev = parse(path)
        print(f"===== {path}: {len(ev)} linhas de diagnostico")
        print("transiente_ativo:", dict(collections.Counter(e['ta'] for e in ev)))
        print("output:", dict(collections.Counter(e['out'] for e in ev)))
        # delta apos_trigger -> transiente_concluido por classe
        by = collections.defaultdict(list)
        last_trig = {}
        for e in ev:
            if e['ponto'] == 'apos_trigger':
                last_trig[e['cls']] = e['t']
            elif e['ponto'] == 'transiente_concluido' and e['cls'] in last_trig:
                by[e['cls']].append(e['t'] - last_trig[e['cls']])
        print("Delta(apos_trigger -> transiente_concluido) [s] por classe:")
        for k, v in sorted(by.items(), key=lambda kv: kv[0][0]):
            print(f"  {k[0]} {k[1]:28s} n={len(v):3d} min={min(v):.3f} med={st.median(v):.3f} max={max(v):.3f}")
        # tempos entre pontos consecutivos (custo dos 3 queries do diag + polling)
        gaps = collections.defaultdict(list)
        prev = None
        for e in ev:
            if prev and prev['cls'] == e['cls']:
                gaps[(prev['ponto'], e['ponto'])].append(e['t'] - prev['t'])
            prev = e
        print("Gap entre pontos consecutivos (s) [min/med/max, n]:")
        for k, v in sorted(gaps.items(), key=lambda kv: -len(kv[1]))[:14]:
            print(f"  {k[0]:>26s} -> {k[1]:26s} {min(v):.3f}/{st.median(v):.3f}/{max(v):.3f} n={len(v)}")
        # tensao por ponto (mediana) separando waveform x nativo
        print("Tensao medida (V) por ponto [mediana, min, max]:")
        vp = collections.defaultdict(list)
        for e in ev:
            if e['v'] is not None:
                vp[e['ponto']].append(e['v'])
        for k, v in sorted(vp.items()):
            print(f"  {k:26s} n={len(v):4d} med={st.median(v):8.2f} min={min(v):8.2f} max={max(v):8.2f}")


main()
