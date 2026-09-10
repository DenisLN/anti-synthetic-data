"""Visualizador de capturas .npz geradas por mestre.py.

Uso:
    python logica/visualizador.py resultados/01_normal.npz
    python logica/visualizador.py resultados/snr_30db/05_harmonics.npz --captura 12
    python logica/visualizador.py resultados/01_normal.npz --sem-abrir --saida saida.png

Gera um PNG com uma amostra das capturas, uma captura individual e o
envelope média +/- desvio-padrão ao longo das 2000 capturas, e abre o
resultado no visualizador de imagens padrão do sistema.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def carregar(caminho: Path) -> dict:
    with np.load(caminho, allow_pickle=True) as dados:
        return {chave: dados[chave] for chave in dados.files}


def abrir_no_visualizador_padrao(caminho: Path) -> None:
    if sys.platform == "win32":
        os.startfile(caminho)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(caminho)], check=False)
    else:
        subprocess.run(["xdg-open", str(caminho)], check=False)


def montar_figura(dados: dict, caminho: Path, indice_captura: int | None, n_overlay: int, seed: int):
    tempo_ms = dados["tempo_ms"]
    tensao_pu = dados["tensao_pu"]
    classe = str(dados["classe"])
    ids = dados.get("id_captura")
    total_capturas = tensao_pu.shape[0]

    rng = np.random.default_rng(seed)
    if indice_captura is None:
        indice_captura = int(rng.integers(0, total_capturas))
    elif not (0 <= indice_captura < total_capturas):
        raise ValueError(f"--captura deve estar entre 0 e {total_capturas - 1}; recebido {indice_captura}")

    n_overlay = min(n_overlay, total_capturas)
    indices_overlay = rng.choice(total_capturas, size=n_overlay, replace=False)

    media = tensao_pu.mean(axis=0)
    desvio = tensao_pu.std(axis=0)

    tamanho_mb = caminho.stat().st_size / (1024 * 1024)

    fig, eixos = plt.subplots(2, 2, figsize=(13, 8))
    ((ax_overlay, ax_unica), (ax_envelope, ax_info)) = eixos

    for i in indices_overlay:
        ax_overlay.plot(tempo_ms, tensao_pu[i], color="steelblue", alpha=0.25, linewidth=0.8)
    ax_overlay.set_title(f"Amostra de {n_overlay} capturas (de {total_capturas})")
    ax_overlay.set_xlabel("Tempo (ms)")
    ax_overlay.set_ylabel("Tensão (pu)")
    ax_overlay.grid(alpha=0.3)

    id_str = str(ids[indice_captura]) if ids is not None else str(indice_captura)
    ax_unica.plot(tempo_ms, tensao_pu[indice_captura], color="darkorange", linewidth=1.1)
    ax_unica.set_title(f"Captura individual: {id_str}")
    ax_unica.set_xlabel("Tempo (ms)")
    ax_unica.set_ylabel("Tensão (pu)")
    ax_unica.grid(alpha=0.3)

    ax_envelope.plot(tempo_ms, media, color="firebrick", linewidth=1.0, label="média")
    ax_envelope.fill_between(
        tempo_ms, media - desvio, media + desvio, color="firebrick", alpha=0.2, label="±1 desvio-padrão"
    )
    ax_envelope.set_title(f"Envelope média ± desvio-padrão ({total_capturas} capturas)")
    ax_envelope.set_xlabel("Tempo (ms)")
    ax_envelope.set_ylabel("Tensão (pu)")
    ax_envelope.legend(loc="upper right", fontsize=8)
    ax_envelope.grid(alpha=0.3)

    ax_info.axis("off")
    linhas_info = [
        f"Arquivo: {caminho.name}",
        f"Caminho: {caminho.parent}",
        f"Classe: {classe}",
        f"Tamanho em disco: {tamanho_mb:.2f} MB",
        f"tensao_pu.shape: {tuple(tensao_pu.shape)}  dtype={tensao_pu.dtype}",
        f"tempo_ms.shape: {tuple(tempo_ms.shape)}  ({tempo_ms[0]:.2f} a {tempo_ms[-1]:.2f} ms)",
        "",
        f"min={tensao_pu.min():.4f} pu   max={tensao_pu.max():.4f} pu",
        f"média global={tensao_pu.mean():.4f} pu   desvio global={tensao_pu.std():.4f} pu",
    ]
    ax_info.text(0.0, 1.0, "\n".join(linhas_info), transform=ax_info.transAxes,
                 va="top", ha="left", family="monospace", fontsize=9)

    fig.suptitle(f"{classe} — {caminho.name}", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return fig


def main() -> int:
    parser = argparse.ArgumentParser(description="Visualiza um arquivo .npz de capturas gerado por mestre.py")
    parser.add_argument("npz", type=Path, help="Caminho do arquivo .npz")
    parser.add_argument("--captura", type=int, default=None, help="Índice da captura individual (0-based); padrão: aleatório")
    parser.add_argument("--n-overlay", type=int, default=40, help="Quantidade de capturas sobrepostas no primeiro painel")
    parser.add_argument("--seed", type=int, default=0, help="Seed para escolha aleatória das capturas exibidas")
    parser.add_argument("--saida", type=Path, default=None, help="Caminho do PNG de saída (padrão: arquivo temporário)")
    parser.add_argument("--sem-abrir", action="store_true", help="Não abrir o PNG no visualizador padrão do sistema")
    parser.add_argument("--dpi", type=int, default=130, help="Resolução do PNG")
    args = parser.parse_args()

    if not args.npz.is_file():
        parser.error(f"Arquivo não encontrado: {args.npz}")

    dados = carregar(args.npz)
    for chave_obrigatoria in ("tempo_ms", "tensao_pu", "classe"):
        if chave_obrigatoria not in dados:
            parser.error(f"{args.npz} não parece uma captura de mestre.py: falta a chave '{chave_obrigatoria}'")

    fig = montar_figura(dados, args.npz, args.captura, args.n_overlay, args.seed)

    if args.saida is not None:
        saida = args.saida
    else:
        descritor, caminho_temp = tempfile.mkstemp(prefix=f"visualizador_{args.npz.stem}_", suffix=".png")
        os.close(descritor)
        saida = Path(caminho_temp)

    fig.savefig(saida, dpi=args.dpi)
    plt.close(fig)
    print(f"PNG salvo em: {saida}")

    if not args.sem_abrir:
        abrir_no_visualizador_padrao(saida)

    return 0


if __name__ == "__main__":
    sys.exit(main())
