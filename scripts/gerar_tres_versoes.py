"""Gera OFFLINE o `modelo` e a `programada` de cada captura de uma sessão da
bancada, a partir do metadata (seed, nível, k, parâmetros programados).

Para sessões gravadas antes da v1.16 (sem `tres_versoes/`). Sem hardware, e
sem alterar um byte da sessão: a saída vai para uma pasta NOVA
(`<sessao>/tres_versoes/` por padrão; recusa uma pasta que já tenha arquivos,
a menos que `--refazer`).

* modelo     = `gerar()` com a seed da captura (sorteio de posição desligado
               quando o metadata não tem `sorteio_posicao`, como as sessões de
               2026-10-07).
* programada = o que a fonte emite para o que foi programado: nas classes
               TRACe/LIST, `AmetekMX30.montar_programacao` (a função que
               `program_capture` usa) sobre a forma de bancada, com o k gravado
               (`parametros.fator_disturbio_bancada`) ou a amplitude gravada da
               08; nas nativas, `sinais.forma_programada_nativa` com os
               parâmetros GRAVADOS. Ver docs/tres_versoes.md.

Cada `NN_classe_<rótulo>.npz` de saída tem o mesmo nome do `.npz` da captura na
sessão, com `modelo_pu` e `programada_pu` (1, pontos), `tempo_ms`, `classe`,
`id_captura` e `origem_programada`. Mais `indice.json` (procedência e
verificações por captura).

Uso (na raiz do projeto):
    env\\Scripts\\python scripts\\gerar_tres_versoes.py resultados\\sessao_2026-10-07_127V_50Hz
    env\\Scripts\\python scripts\\gerar_tres_versoes.py resultados\\sessao_... --saida outra_pasta
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "logica"))

import analisar_sessao  # noqa: E402
import mestre  # noqa: E402

PASTA_SAIDA_PADRAO = mestre.PASTA_TRES_VERSOES


class _ConfigOffline(analisar_sessao._ConfigOffline):
    """`_ConfigOffline` de analisar_sessao.py + o que `forma_programada` lê."""

    def __init__(self, registro: dict):
        super().__init__(
            float(registro.get("tensao_base_rms", analisar_sessao.TENSAO_BASE_PADRAO_RMS)),
            registro.get("perfil", "literatura"),
            sorteio_posicao=bool(registro.get("sorteio_posicao", False)),
            fs_hz=float(registro["fs_hz"]), points=int(registro["pontos"]),
        )
        self.grid_frequency_hz = float(registro.get("f0_hz", analisar_sessao.F0_PADRAO_HZ))


class _BancadaOffline:
    fonte = None
    osc = None  # gerar() trata a reconstrução como simulada

    def __init__(self, registro: dict):
        self.config = _ConfigOffline(registro)


def _registros_da_sessao(sessao_dir: Path) -> List[dict]:
    registros: List[dict] = []
    for jsonl in sorted((sessao_dir / "metadata").glob("*.jsonl")):
        for linha in jsonl.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                registros.append(json.loads(linha))
    return registros


def _nomes_dos_npz(sessao_dir: Path) -> Dict[str, str]:
    """`id_captura` -> nome do .npz da captura (lido de dentro do arquivo)."""
    nomes: Dict[str, str] = {}
    for caminho in sorted(sessao_dir.glob("*.npz")):
        with np.load(caminho, allow_pickle=True) as dados:
            for id_captura in np.atleast_1d(dados["id_captura"]):
                nomes[str(id_captura)] = caminho.name
    return nomes


def _forma_de_bancada(instancia, registro: dict, modelo: np.ndarray, parametros_gerar: dict, t: np.ndarray) -> np.ndarray:
    """O que `forma_para_bancada` entregou ao `program_capture` na sessão,
    refeito a partir do que o metadata GRAVOU (não de código de hoje)."""
    gravados = registro.get("parametros") or {}
    f0 = float(registro.get("f0_hz", analisar_sessao.F0_PADRAO_HZ))
    k = gravados.get("fator_disturbio_bancada")
    if k is not None:
        tau = float(registro.get("fase_graus", 0.0)) / (360.0 * f0)
        senoide = np.sin(2.0 * np.pi * f0 * (t + tau))
        return senoide + float(k) * (modelo - senoide)
    if "amplitude_bancada_pu" in gravados and hasattr(instancia, "_indices_impulso"):
        # 08: a base fica em 1 pu e só o impulso tem a amplitude de bancada.
        indices = instancia._indices_impulso(float(registro["fs_hz"]), f0)
        forma = np.array(modelo, dtype=np.float64)
        forma[indices] += float(gravados["amplitude_bancada_pu"]) - float(parametros_gerar["transient_amplitude_pu"])
        return forma
    return np.array(modelo, dtype=np.float64)


def reconstruir_versoes(registro: dict) -> Dict[str, object]:
    """modelo e programada (pu, grade da captura) de UMA linha de metadata.
    Devolve também `origem`, `forma_bancada` e as verificações (`avisos`)."""
    class_id = str(registro["id_captura"]).split("-")[0]
    cls = analisar_sessao._carregar_experimento_cls(class_id)
    instancia = cls(_BancadaOffline(registro))
    fs_hz, pontos = float(registro["fs_hz"]), int(registro["pontos"])
    f0 = float(registro.get("f0_hz", analisar_sessao.F0_PADRAO_HZ))
    t = np.arange(pontos, dtype=np.float64) / fs_hz
    capture_index = int(registro.get("nivel_indice", 0))
    modelo, parametros_gerar = instancia.gerar(t, f0, capture_index, np.random.default_rng(int(registro["seed"])))
    modelo = np.asarray(modelo, dtype=np.float64)
    avisos: List[str] = []

    # Parâmetros gravados (os que a bancada de fato programou) + posição sorteada.
    parametros = dict(registro.get("parametros") or {})
    for chave in mestre.CHAVES_SORTEIO:
        if chave in registro:
            parametros[chave] = registro[chave]
    for chave, valor in (registro.get("parametros") or {}).items():
        gerado = parametros_gerar.get(chave)
        if isinstance(gerado, float) and isinstance(valor, (int, float)) and not math.isclose(
            gerado, float(valor), rel_tol=1e-9, abs_tol=1e-12,
        ) and not chave.endswith(("_bancada", "_modelo_v", "_previsto_v", "caracterizacao", "fator_disturbio_bancada")):
            avisos.append(f"parametro {chave}: gerar() atual {gerado!r} != gravado {valor!r}")

    forma_bancada = _forma_de_bancada(instancia, registro, modelo, parametros_gerar, t)
    if instancia.grava_trace(capture_index):
        pico_v = float(np.max(np.abs(forma_bancada))) * float(registro["tensao_base_rms"]) * math.sqrt(2.0)
        gravado_v = registro.get("pico_programado_v")
        if gravado_v is not None and not math.isclose(pico_v, float(gravado_v), rel_tol=1e-6):
            avisos.append(f"pico da forma de bancada {pico_v:.4f} V != pico_programado_v gravado {float(gravado_v):.4f} V")
    programada, origem = instancia.forma_programada(forma_bancada, parametros, capture_index, t)
    return {
        "modelo": modelo, "programada": np.asarray(programada, dtype=np.float64),
        "forma_bancada": forma_bancada, "origem": origem, "avisos": avisos, "classe": instancia.nome,
    }


def _gravar_npz(destino: Path, **arrays) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(".npz.part")
    with parcial.open("wb") as handle:
        np.savez(handle, **arrays)
    os.replace(parcial, destino)


def gerar_sessao(sessao_dir: Path, saida: Path, *, refazer: bool = False) -> List[dict]:
    sessao_dir, saida = sessao_dir.resolve(), saida.resolve()
    if saida == sessao_dir or sessao_dir in saida.parents and saida.parent != sessao_dir:
        raise ValueError("A saída tem de ser uma pasta nova diretamente dentro da sessão (ou fora dela)")
    if saida.is_dir() and any(saida.iterdir()):
        if not refazer:
            raise FileExistsError(f"{saida} já tem arquivos; use --refazer para regenerar (só sobrescreve o que este script grava)")
        if not (saida / "indice.json").is_file():
            raise FileExistsError(f"{saida} tem arquivos que este script não gravou (sem indice.json); recuso")
    registros = [r for r in _registros_da_sessao(sessao_dir) if not r.get("simulado")]
    if not registros:
        raise FileNotFoundError(f"{sessao_dir}: nenhum metadata/*.jsonl de captura física")
    nomes = _nomes_dos_npz(sessao_dir)
    linhas: List[dict] = []
    for registro in registros:
        id_captura = str(registro["id_captura"])
        resultado = reconstruir_versoes(registro)
        nome = nomes.get(id_captura)
        if nome is None:
            resultado["avisos"].append("sem .npz da captura na sessão; nome do arquivo = id_captura")
            nome = f"{id_captura}.npz"
        pontos = int(registro["pontos"])
        _gravar_npz(
            saida / nome,
            classe=resultado["classe"], id_captura=np.array([id_captura], dtype=object),
            tempo_ms=np.arange(pontos, dtype=np.float64) / float(registro["fs_hz"]) * 1000.0,
            modelo_pu=resultado["modelo"][np.newaxis, :],
            programada_pu=resultado["programada"][np.newaxis, :],
            origem_programada=np.array(resultado["origem"]),
        )
        linhas.append({
            "id_captura": id_captura, "arquivo": nome, "origem_programada": resultado["origem"],
            "k": (registro.get("parametros") or {}).get("fator_disturbio_bancada"),
            "sorteio_posicao": bool(registro.get("sorteio_posicao", False)),
            "pico_modelo_pu": float(np.max(np.abs(resultado["modelo"]))),
            "pico_programada_pu": float(np.max(np.abs(resultado["programada"]))),
            "max_abs_programada_menos_modelo_pu": float(np.max(np.abs(resultado["programada"] - resultado["modelo"]))),
            "avisos": resultado["avisos"],
        })
    codigo = mestre.info_do_codigo()
    indice = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "sessao": sessao_dir.name, "script": "scripts/gerar_tres_versoes.py",
        "git_commit": codigo["git_commit"], "git_sujo": codigo["git_sujo"],
        "capturas": linhas,
    }
    (saida / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return linhas


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sessao_dir", type=Path, help="pasta resultados/sessao_... (com metadata/)")
    parser.add_argument("--saida", type=Path, default=None, help=f"pasta de saída (padrão: <sessao>/{PASTA_SAIDA_PADRAO}/)")
    parser.add_argument("--refazer", action="store_true", help="aceita uma saída que já tem arquivos")
    args = parser.parse_args(argv)
    if not (args.sessao_dir / "metadata").is_dir():
        parser.error(f"{args.sessao_dir} não parece uma sessão (sem metadata/)")
    saida = args.saida if args.saida is not None else args.sessao_dir / PASTA_SAIDA_PADRAO
    linhas = gerar_sessao(args.sessao_dir, saida, refazer=args.refazer)
    print(f"{'id_captura':<12}{'arquivo':<56}{'|prog-mod|max':>14}  origem")
    for linha in linhas:
        print(f"{linha['id_captura']:<12}{linha['arquivo']:<56}{linha['max_abs_programada_menos_modelo_pu']:>14.4f}  {linha['origem_programada']}")
        for aviso in linha["avisos"]:
            print(f"    AVISO: {aviso}")
    avisos = sum(len(linha["avisos"]) for linha in linhas)
    print(f"\n{len(linhas)} captura(s) em {saida} ({avisos} aviso(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
