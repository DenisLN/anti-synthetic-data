"""Analise offline (sem hardware) das capturas das sessoes de 2026-09-16.

Para cada .npz: detecta o onset REAL da saida da AMETEK dentro do array
(o codigo assume o trigger em margem_amostras_antes; os dados mostram outra
coisa), recorta ("trim") em torno do evento, reconstroi a forma esperada via
gerar()+seed (so quando o f0/tensao base da sessao sao conhecidos) e compara
ja alinhada no onset.

Uso (a partir da raiz do worktree, com o python do env/):
    python docs/analise-2026-09-21/analise_trim.py <pasta_sessao> --f0 60 --vbase 127 \
        --out docs/analise-2026-09-21/saida_s1 [--sem-expected] [--pre-ms 20] [--post-ms 50]

Nada aqui escreve em resultados/ nem toca instrumentos.
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXPDIRS = (ROOT / "experimentos_nativos", ROOT / "experimentos_waveform")
FS = 30000.0


def half_cycle_peaks(x, f0):
    """Pico |x| por meio ciclo (janela = fs/(2 f0)), passo = meio ciclo."""
    n = int(round(FS / (2 * f0)))
    m = len(x) // n
    pk = np.abs(x[: m * n]).reshape(m, n).max(axis=1)
    t_ms = (np.arange(m) * n + n / 2) / FS * 1000
    return t_ms, pk


def onset_index(x, f0, thr=0.25):
    """Primeiro instante em que a saida sai do repouso (~0 V). Refina para o
    cruzamento por zero anterior (a AMETEK sincroniza em fase 0)."""
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return None
    i = int(idx[0])
    j = i
    while j > 0 and abs(x[j - 1]) < abs(x[j]) and abs(x[j - 1]) > 0.02:
        j -= 1
    return j


def load_exp(class_id):
    for d in EXPDIRS:
        p = d / f"{class_id}.py"
        if p.exists():
            sys.path.insert(0, str(ROOT / "logica"))
            sys.path.insert(0, str(d))
            try:
                spec = importlib.util.spec_from_file_location(f"a_{d.name}_{class_id}", p)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            finally:
                sys.path.pop(0)
                sys.path.pop(0)
            return mod.Experimento
    return None


class _Cfg:
    capturas_override = None
    base_voltage_rms = 127.0

    def capturas(self, simulated):
        return 1


class _Banc:
    config = _Cfg()
    fonte = None
    osc = None


def expected_waveform(class_id, md, f0, vbase):
    cls = load_exp(class_id)
    if cls is None:
        return None
    _Cfg.base_voltage_rms = vbase
    inst = cls(_Banc())
    t = np.arange(md["pontos"], dtype=np.float64) / md["fs_hz"]
    rng = np.random.default_rng(md["seed"])
    v, par = inst.gerar(t, f0, md.get("nivel_indice", 0), rng)
    return np.asarray(v, dtype=np.float64), par


def load_meta(d):
    m = {}
    for p in glob.glob(os.path.join(d, "metadata", "*.jsonl")):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                j = json.loads(line)
                m[j["id_captura"]] = j
    return m


def event_span(xw, f0, kind):
    """xw = trecho alinhado no onset. Devolve (inicio_ms, fim_ms) do
    afundamento/elevacao/interrupcao pelo envelope de meio ciclo, ou None."""
    t, pk = half_cycle_peaks(xw, f0)
    ref = np.median(pk[: max(3, int(0.04 * f0 * 2))])
    if ref <= 0:
        return None
    r = pk / ref
    if kind == "sag":
        m = r < 0.8
    elif kind == "swell":
        m = r > 1.12
    elif kind == "int":
        m = r < 0.3
    else:
        return None
    if not m.any():
        return None
    i = np.where(m)[0]
    return float(t[i[0]] - 1000 / (4 * f0)), float(t[i[-1]] + 1000 / (4 * f0))


KIND = {"10": "sag", "11": "sag", "12": "sag", "13": "swell", "14": "swell", "16": "int",
        "02": "sag", "03": "swell", "04": "int"}


def analisar(sessao, f0, vbase, out, sem_expected=False, pre_ms=20.0, post_ms=50.0, nominal_ms=200.0):
    out = Path(out)
    (out / "trim").mkdir(parents=True, exist_ok=True)
    meta = load_meta(sessao)
    rows = []
    for f in sorted(glob.glob(os.path.join(sessao, "*.npz"))):
        z = np.load(f, allow_pickle=True)
        X = z["tensao_pu"]
        ids = z["id_captura"]
        for k in range(X.shape[0]):
            x = X[k]
            idc = str(ids[k])
            md = meta.get(idc, {})
            cid = os.path.basename(f)[:2]
            name = os.path.basename(f)[:-4]
            ma = md.get("margem_amostras_antes", 0)
            on = onset_index(x, f0)
            row = dict(arquivo=name, classe=md.get("classe", "?"), id=cid, n=len(x),
                       trig_assumido_ms=ma / FS * 1000,
                       onset_ms=(on / FS * 1000 if on is not None else None))
            nom_n = int(round(nominal_ms / 1000 * FS))
            if on is not None and on + nom_n <= len(x):
                pre = int(round(pre_ms / 1000 * FS))
                post = int(round(post_ms / 1000 * FS))
                s = max(0, on - pre)
                e = min(len(x), on + nom_n + post)
                tr = x[s:e]
                row.update(pre_silencio_ms=on / FS * 1000,
                           pos_evento_ms=(len(x) - (on + nom_n)) / FS * 1000, trim_n=len(tr))
                np.savez_compressed(out / "trim" / f"{name}_trim.npz",
                                    tempo_ms=(np.arange(s, e) - on) / FS * 1000, tensao_pu=tr,
                                    onset_idx=on, parametros=json.dumps(md.get("parametros", {})))
                xw = x[on:on + nom_n]
                kind = KIND.get(cid)
                if kind:
                    row["evento_medido_ms"] = event_span(xw, f0, kind)
                if not sem_expected and md:
                    try:
                        exp, par = expected_waveform(cid, md, f0, vbase)
                        ex = exp[:nom_n]
                        best = None
                        L = int(round(FS / f0))
                        for lag in range(-L, L + 1):
                            if lag >= 0:
                                aa = xw[lag:]
                                bb = ex[: len(aa)]
                            else:
                                bb = ex[-lag:]
                                aa = xw[: len(bb)]
                            if len(aa) < nom_n // 2:
                                continue
                            sc = float(np.dot(aa, bb) / (np.linalg.norm(aa) * np.linalg.norm(bb) + 1e-12))
                            if best is None or sc > best[1]:
                                best = (lag, sc)
                        row.update(lag_apos_onset_ms=best[0] / FS * 1000, corr=best[1],
                                   razao_pico=float(np.max(np.abs(xw)) / (np.max(np.abs(ex)) + 1e-12)))
                    except Exception as exc:  # noqa: BLE001
                        row["expected_erro"] = repr(exc)[:80]
            else:
                t, pk = half_cycle_peaks(x, f0)
                med = float(np.median(pk))
                row.update(env_min=float(pk.min()), env_max=float(pk.max()),
                           env_rel_min=float(pk.min() / med), env_rel_max=float(pk.max() / med))
                kind = KIND.get(cid)
                if kind:
                    row["evento_medido_ms"] = event_span(x, f0, kind)
            rows.append(row)
    json.dump(rows, open(out / "tabela.json", "w"), indent=1, default=str)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("sessao")
    ap.add_argument("--f0", type=float, required=True)
    ap.add_argument("--vbase", type=float, default=127.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sem-expected", action="store_true")
    ap.add_argument("--pre-ms", type=float, default=20.0)
    ap.add_argument("--post-ms", type=float, default=50.0)
    a = ap.parse_args()
    rows = analisar(a.sessao, a.f0, a.vbase, a.out, a.sem_expected, a.pre_ms, a.post_ms)

    def fmt(o):
        return round(o, 3) if isinstance(o, float) else str(o)

    for r in rows:
        print(json.dumps(r, default=fmt, ensure_ascii=False))
