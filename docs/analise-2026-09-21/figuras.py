"""Gera as figuras da analise (sem hardware). Uso: python figuras.py <repo_main>/resultados <sessao1_dir> <out_dir>"""
import glob, json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(__file__))
from analise_trim import onset_index, load_meta, expected_waveform, FS

OLD, S1, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
meta = load_meta(S1)
files = sorted(glob.glob(os.path.join(S1, "*.npz")))

# Fig 1: visao geral das 20 capturas (registro inteiro de 1 s)
fig, axs = plt.subplots(5, 4, figsize=(20, 14), sharey=False)
for ax, f in zip(axs.ravel(), files):
    z = np.load(f, allow_pickle=True); x = z["tensao_pu"][0]
    t = np.arange(len(x)) / FS * 1000
    ax.plot(t, x, lw=0.4, color="#1f77b4")
    on = onset_index(x, 60.0)
    ax.axvspan(400, 600, color="orange", alpha=0.25, label="janela nominal ASSUMIDA pelo codigo (400-600 ms)")
    if on is not None and on > 50:
        ax.axvspan(on / FS * 1000 - 20, on / FS * 1000 + 250, color="green", alpha=0.18, label="trim util (onset-20 ms .. +250 ms)")
        ax.axvline(on / FS * 1000, color="green", lw=0.8)
    ax.set_title(os.path.basename(f)[:34], fontsize=8)
    ax.set_xlim(0, 1000)
axs[0, 0].legend(fontsize=6, loc="lower left")
fig.suptitle("Sessao 1 (127 V/60 Hz, margin on 400 ms, diag on): registro completo de 1 s por classe", fontsize=12)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig1_sessao1_registro_completo.png"), dpi=70); plt.close(fig)

# Fig 2: trim alinhado no onset vs esperado gerar()
sel = [f for f in files if os.path.basename(f)[:2] in {"01","06","07","08","09","10","11","12","13","14","15","16","17","20"}]
fig, axs = plt.subplots(len(sel) // 2 + len(sel) % 2, 2, figsize=(18, 2.3 * (len(sel) // 2 + 1)))
for ax, f in zip(axs.ravel(), sel):
    z = np.load(f, allow_pickle=True); x = z["tensao_pu"][0]; idc = str(z["id_captura"][0]); md = meta[idc]
    on = onset_index(x, 60.0)
    exp, _ = expected_waveform(os.path.basename(f)[:2], md, 60.0, 127.0)
    n = 6000
    tt = np.arange(-600, n + 1500) / FS * 1000
    seg = x[on - 600:on + n + 1500]
    ax.plot(tt, seg, lw=0.5, color="#1f77b4", label="capturado (trim: onset-20 ms .. +250 ms)")
    ax.plot(np.arange(n) / FS * 1000, exp, lw=0.5, color="#d62728", alpha=0.7, label="esperado gerar()")
    ax.set_title(os.path.basename(f)[:40] + f"  onset={on/FS*1000:.1f} ms", fontsize=8)
axs[0, 0].legend(fontsize=6)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig2_trim_vs_esperado.png"), dpi=70); plt.close(fig)

# Fig 3: nativos PULSe: antigo (sem margem) vs novo (margin on)
fig, axs = plt.subplots(3, 2, figsize=(14, 7))
for row, cid in enumerate(("02", "03", "04")):
    xo = np.load(glob.glob(os.path.join(OLD, f"{cid}_*.npz"))[0])["tensao_pu"][0]
    xn = np.load(glob.glob(os.path.join(S1, f"{cid}_*.npz"))[0])["tensao_pu"][0]
    axs[row, 0].plot(np.arange(len(xo)) / FS * 1000, xo, lw=0.5); axs[row, 0].set_title(f"{cid} ANTIGO 2026-09-09 (janela 200 ms, sem margem, sem diag)", fontsize=8)
    axs[row, 1].plot(np.arange(len(xn)) / FS * 1000, xn, lw=0.4); axs[row, 1].set_title(f"{cid} NOVO 2026-09-16 (janela 1 s, margin on, diag on): SEM disturbio", fontsize=8)
    axs[row, 1].axvline(460, color="r", lw=0.8, ls="--")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig3_nativos_pulse_antigo_vs_novo.png"), dpi=70); plt.close(fig)
print("ok")
