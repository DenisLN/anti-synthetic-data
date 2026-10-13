"""Item 1 (cont.): onde estao as maiores diferencas medida - programada.
Para cada captura, os 3 maiores |erro| (separados por >= 1 ms) em ms da janela.
Procura picos que a programada nao tem (ex.: ~100 ms).
Uso: python docs/analise-2026-10-12/diag_picos_espurios.py [classes...]
"""
import sys
import numpy as np
import diag_comum as D

classes = set(sys.argv[1:]) or {"01", "03", "05", "07", "08", "09", "17"}
for rot in D.SESSOES:
    for c in D.capturas(rot, classes):
        n = 6000
        lag, _ = D.melhor_lag(c["programada"], c["raw"], c["ini"], c["f0"], 10)
        if lag is None:
            lag, _ = D.AS.analisar_offset(c["programada"], c["medida"], D.FS)
        i0 = c["ini"] + lag
        e = c["raw"][i0:i0 + n] - c["programada"]
        e = e - np.median(e)
        achados, usados = [], np.zeros(n, bool)
        for i in np.argsort(-np.abs(e)):
            if usados[max(0, i - 30):i + 30].any():
                continue
            achados.append((i / 30.0, e[i])); usados[i] = True
            if len(achados) == 3:
                break
        print(f"{rot:10s} {c['id']:8s} lag {lag:3d} rms_e {e.std():.4f}  " + "  ".join(f"{t:7.2f}ms {v:+.3f}" for t, v in achados))
