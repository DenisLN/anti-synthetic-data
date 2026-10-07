"""Recorta a margem de captura (folga antes/depois) de uma sessão da bancada.

Desde a v1.11 toda captura FÍSICA grava ``MARGEM_ANTES_S``/``MARGEM_DEPOIS_S``
(20 ms antes / 50 ms depois por padrão) em volta da janela nominal — 8100
pontos a 30 kSa/s em vez dos 6000 que ``gerar()``/o dataset simulado usam.
Este script devolve, para cada captura, só a janela NOMINAL (mesma base de
tempo de ``gerar()``), usando o MESMO recorte de ``analisar_sessao.py`` e da
validação física: ``sinais.janela_nominal()`` alinhada pelo ``indice_trigger``
real gravado no metadata (H-REF10, CHANGELOG/v1.11.md).

Nunca altera a sessão original: escreve numa pasta nova (padrão
``<sessao>/sem_margem/``) com a mesma estrutura — ``*.npz`` puros,
``snr_XXdb/``, ``corrente/`` e ``metadata/*.jsonl`` — de modo que
``analisar_sessao.py`` e ``relatorio_html.py`` rodam nela sem mudança. Cada
linha do metadata ganha um bloco ``recorte`` (de onde saiu a janela) e passa a
descrever o arquivo recortado (``margem_amostras_* = 0``, ``indice_trigger``
reindexado).

``--empilhar`` grava também, em ``<saida>/empilhado/``, um ``.npz`` por classe
com todas as capturas empilhadas (``tensao_pu`` com shape ``(N, pontos)``) —
o formato do dataset simulado.

Sem hardware: roda em qualquer máquina, só precisa dos arquivos já gravados.

Uso:
    python logica/recortar_margem.py resultados/sessao_2026-09-30_14-00-00
    python logica/recortar_margem.py resultados/sessao_... --saida recortado --empilhar
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "logica") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "logica"))
from sinais import janela_nominal  # noqa: E402

PASTA_SAIDA_PADRAO = "sem_margem"


def carregar_metadados(sessao_dir: Path) -> Dict[str, dict]:
    """``id_captura`` -> linha do metadata, de todos os ``metadata/*.jsonl``."""
    metadados: Dict[str, dict] = {}
    metadata_dir = sessao_dir / "metadata"
    if not metadata_dir.is_dir():
        return metadados
    for jsonl_path in sorted(metadata_dir.glob("*.jsonl")):
        for linha in jsonl_path.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                registro = json.loads(linha)
                metadados[str(registro["id_captura"])] = registro
    return metadados


def diretorios_de_dados(sessao_dir: Path) -> List[Path]:
    """Pasta da sessão + ``snr_XXdb/`` + ``corrente/`` — só o que
    ``_salvar_captura`` grava. ``analise/``, ``sem_margem/`` etc. ficam de fora."""
    dirs = [sessao_dir]
    dirs += sorted(p for p in sessao_dir.glob("snr_*db") if p.is_dir())
    corrente = sessao_dir / "corrente"
    if corrente.is_dir():
        dirs.append(corrente)
    return dirs


def calcular_recorte(n_amostras: int, metadado: Optional[dict]) -> Tuple[int, int, dict]:
    """Decide ``[inicio, inicio + pontos)`` da janela nominal dentro de um
    registro de ``n_amostras``. Devolve ``(inicio, pontos, info)``; ``info``
    vai para o metadata (bloco ``recorte``) e explica a origem do número."""
    if metadado is None:
        return 0, n_amostras, {"origem": "sem_metadata", "inicio_amostra": 0,
                               "fim_amostra": n_amostras, "amostras_originais": n_amostras,
                               "ajustado": False}
    pontos = int(metadado.get("pontos", n_amostras))
    fs_hz = float(metadado.get("fs_hz", 30_000.0))
    pre_trigger_s = float(metadado.get("pre_trigger_s", 0.0))
    margem_antes = int(metadado.get("margem_amostras_antes", 0))

    if n_amostras <= pontos:
        origem = "sem_margem"
        inicio_ideal = 0
    elif metadado.get("indice_trigger") is not None:
        # Mesmo cálculo de sinais.janela_nominal(): o trigger caiu em
        # indice_trigger e a janela nominal começa pre_trigger_s antes dele.
        origem = "indice_trigger"
        inicio_ideal = int(round(int(metadado["indice_trigger"]) - pre_trigger_s * fs_hz))
    else:
        # Metadata anterior ao P07: sem a posição real do trigger, supõe o
        # que mestre.py PEDIU ao osciloscópio — a janela nominal começa
        # exatamente depois da margem de antes. Pode ter o viés de janela/10
        # de H-REF10 em sessões antigas; por isso a origem fica registrada.
        origem = "margem_amostras_antes"
        inicio_ideal = margem_antes

    if origem == "indice_trigger":
        trecho = janela_nominal(
            np.arange(n_amostras), indice_trigger=int(metadado["indice_trigger"]),
            pre_trigger_s=pre_trigger_s, pontos=pontos, fs_hz=fs_hz,
        )
        inicio = int(trecho[0]) if trecho.size else 0
    else:
        inicio = max(0, min(inicio_ideal, max(0, n_amostras - pontos)))
    pontos = min(pontos, n_amostras - inicio)
    info = {
        "origem": origem,
        "inicio_amostra": inicio,
        "fim_amostra": inicio + pontos,
        "amostras_originais": n_amostras,
        # O registro não tinha amostras suficientes do lado certo do trigger
        # e a janela foi empurrada para dentro dele: o conteúdo NÃO está
        # alinhado com gerar(). Raro (trigger fora do lugar); sempre avisado.
        "ajustado": inicio != inicio_ideal,
        "deslocamento_vs_margem_ms": (inicio - margem_antes) / fs_hz * 1000.0 if margem_antes else 0.0,
    }
    return inicio, pontos, info


def metadado_recortado(metadado: dict, info: dict) -> dict:
    """Linha do metadata descrevendo o arquivo RECORTADO (original intocado)."""
    novo = dict(metadado)
    novo["recorte"] = info
    if info["origem"] in ("indice_trigger", "margem_amostras_antes"):
        novo["margem_amostras_antes"] = 0
        novo["margem_amostras_depois"] = 0
        novo["amostras_totais"] = info["fim_amostra"] - info["inicio_amostra"]
        if metadado.get("indice_trigger") is not None:
            novo["indice_trigger"] = int(metadado["indice_trigger"]) - info["inicio_amostra"]
    return novo


def _gravar_npz(destino: Path, **arrays) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(".npz.part")
    with parcial.open("wb") as handle:
        np.savez(handle, **arrays)
    os.replace(parcial, destino)


def _chave_de_dados(dados) -> str:
    for chave in ("tensao_pu", "corrente_pu"):
        if chave in dados.files:
            return chave
    raise KeyError("sem tensao_pu/corrente_pu")


def recortar_sessao(
    sessao_dir: Path, saida_dir: Path, *, empilhar: bool = False,
) -> List[dict]:
    """Recorta toda a sessão. Devolve uma linha de relatório por captura
    (por diretório), com ``erro`` quando não deu para recortar."""
    sessao_dir = sessao_dir.resolve()
    saida_dir = saida_dir.resolve()
    if saida_dir == sessao_dir:
        raise ValueError("A saída não pode ser a própria pasta da sessão (os originais seriam sobrescritos)")
    metadados = carregar_metadados(sessao_dir)
    relatorio: List[dict] = []
    metadados_saida: Dict[str, dict] = {}
    # (diretório relativo, prefixo NN, classe) -> [(id_captura, janela recortada)]
    pilhas: Dict[Tuple[str, str, str], List[Tuple[str, np.ndarray]]] = {}
    fs_por_pilha: Dict[Tuple[str, str, str], float] = {}

    for origem_dir in diretorios_de_dados(sessao_dir):
        relativo = origem_dir.relative_to(sessao_dir)
        for npz_path in sorted(origem_dir.glob("*.npz")):
            with np.load(npz_path, allow_pickle=True) as dados:
                try:
                    chave = _chave_de_dados(dados)
                except KeyError:
                    relatorio.append({"arquivo": str(relativo / npz_path.name), "erro": "sem tensao_pu/corrente_pu"})
                    continue
                matriz = np.atleast_2d(np.asarray(dados[chave], dtype=np.float64))
                ids = [str(i) for i in np.atleast_1d(dados["id_captura"])] if "id_captura" in dados.files \
                    else [f"{npz_path.stem}-{k}" for k in range(matriz.shape[0])]
                classe = str(dados["classe"]) if "classe" in dados.files else npz_path.stem
                tempo_ms_original = np.asarray(dados["tempo_ms"], dtype=np.float64) if "tempo_ms" in dados.files else None

            linhas_recortadas: List[np.ndarray] = []
            info_arquivo: Optional[dict] = None
            for k, id_captura in enumerate(ids):
                metadado = metadados.get(id_captura)
                inicio, pontos, info = calcular_recorte(matriz.shape[1], metadado)
                if info_arquivo is not None and (inicio, pontos) != (info_arquivo["inicio_amostra"], info_arquivo["fim_amostra"] - info_arquivo["inicio_amostra"]):
                    # Formato simulado (N linhas num arquivo): nunca tem margem,
                    # então todas as linhas têm o mesmo recorte. Se não tiverem,
                    # empilhar no mesmo array seria inválido.
                    raise ValueError(f"{npz_path}: capturas do mesmo arquivo com recortes diferentes")
                info_arquivo = info
                linhas_recortadas.append(matriz[k, inicio : inicio + pontos])
                if metadado is not None and id_captura not in metadados_saida:
                    metadados_saida[id_captura] = metadado_recortado(metadado, info)
                relatorio.append({
                    "arquivo": str(relativo / npz_path.name), "id_captura": id_captura, **info,
                })
                if empilhar:
                    pilha_key = (str(relativo), npz_path.name.split("_", 1)[0], classe)
                    pilhas.setdefault(pilha_key, []).append((id_captura, linhas_recortadas[-1]))
                    fs_por_pilha.setdefault(pilha_key, float((metadado or {}).get("fs_hz", 30_000.0)))

            assert info_arquivo is not None
            recortado = np.vstack(linhas_recortadas)
            pontos = recortado.shape[1]
            if tempo_ms_original is not None and tempo_ms_original.size == matriz.shape[1]:
                inicio = info_arquivo["inicio_amostra"]
                tempo_ms = tempo_ms_original[inicio : inicio + pontos] - tempo_ms_original[inicio]
            else:
                fs_hz = float((metadados.get(ids[0]) or {}).get("fs_hz", 30_000.0))
                tempo_ms = np.arange(pontos) / fs_hz * 1000.0
            _gravar_npz(
                saida_dir / relativo / npz_path.name,
                classe=classe, id_captura=np.array(ids, dtype=object),
                tempo_ms=tempo_ms, **{chave: recortado},
            )

    # Metadata: um .jsonl por classe, mesmo nome do original, só com as
    # capturas que existem nesta sessão (ordem original preservada).
    metadata_origem = sessao_dir / "metadata"
    if metadata_origem.is_dir():
        (saida_dir / "metadata").mkdir(parents=True, exist_ok=True)
        for jsonl_path in sorted(metadata_origem.glob("*.jsonl")):
            linhas = []
            for linha in jsonl_path.read_text(encoding="utf-8").splitlines():
                if not linha.strip():
                    continue
                registro = json.loads(linha)
                novo = metadados_saida.get(str(registro["id_captura"]), registro)
                linhas.append(json.dumps(novo, ensure_ascii=False, sort_keys=True))
            destino = saida_dir / "metadata" / jsonl_path.name
            parcial = destino.with_suffix(".jsonl.part")
            parcial.write_text("\n".join(linhas) + ("\n" if linhas else ""), encoding="utf-8")
            os.replace(parcial, destino)

    if empilhar:
        for pilha_key, itens in sorted(pilhas.items()):
            relativo, prefixo, classe = pilha_key
            tamanhos = {len(linha) for _, linha in itens}
            if len(tamanhos) != 1:
                relatorio.append({"arquivo": f"empilhado/{relativo}/{prefixo}", "erro": f"tamanhos diferentes {sorted(tamanhos)}; não empilhado"})
                continue
            chave = "corrente_pu" if Path(relativo).name == "corrente" else "tensao_pu"
            sufixo = "_corrente" if chave == "corrente_pu" else ""
            _gravar_npz(
                saida_dir / "empilhado" / relativo / f"{prefixo}_{classe.lower()}{sufixo}.npz",
                classe=classe,
                id_captura=np.array([i for i, _ in itens], dtype=object),
                tempo_ms=np.arange(tamanhos.pop()) / fs_por_pilha[pilha_key] * 1000.0,
                **{chave: np.vstack([linha for _, linha in itens])},
            )
    return relatorio


def _imprimir(relatorio: Iterable[dict]) -> int:
    avisos = 0
    print(f"{'arquivo':<55}{'origem':>22}{'início':>8}{'fim':>7}{'desloc. (ms)':>14}")
    for linha in relatorio:
        if "erro" in linha:
            avisos += 1
            print(f"{linha['arquivo']:<55}  ERRO: {linha['erro']}")
            continue
        marca = "  << AJUSTADO (janela empurrada para dentro do registro)" if linha["ajustado"] else ""
        if linha["ajustado"] or linha["origem"] in ("margem_amostras_antes", "sem_metadata"):
            avisos += 1
        print(
            f"{linha['arquivo']:<55}{linha['origem']:>22}{linha['inicio_amostra']:>8}"
            f"{linha['fim_amostra']:>7}{linha.get('deslocamento_vs_margem_ms', 0.0):>14.2f}{marca}"
        )
    return avisos


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Recorta a margem de captura (folga antes/depois) de uma sessão, sem tocar nos originais.",
    )
    parser.add_argument("sessao_dir", type=Path, help="Pasta resultados/sessao_.../")
    parser.add_argument("--saida", type=Path, default=None,
                        help=f"Pasta de saída (padrão: <sessao>/{PASTA_SAIDA_PADRAO}/)")
    parser.add_argument("--empilhar", action="store_true",
                        help="Grava também <saida>/empilhado/: um .npz por classe, capturas empilhadas (formato do dataset simulado)")
    args = parser.parse_args(argv)

    if not args.sessao_dir.is_dir():
        parser.error(f"Pasta não encontrada: {args.sessao_dir}")
    saida = args.saida if args.saida is not None else args.sessao_dir / PASTA_SAIDA_PADRAO
    relatorio = recortar_sessao(args.sessao_dir, saida, empilhar=args.empilhar)
    if not relatorio:
        print(f"Nenhum .npz encontrado em {args.sessao_dir}")
        return 1
    avisos = _imprimir(relatorio)
    print(f"\nRecortado em: {saida}")
    if avisos:
        print(f"{avisos} linha(s) merecem atenção (erro, recorte ajustado ou sem indice_trigger) — ver acima.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
