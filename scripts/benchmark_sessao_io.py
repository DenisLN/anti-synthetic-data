#!/usr/bin/env python3
"""P22: benchmark sintético offline do writer real, com integridade na leitura.

Usa apenas diretórios temporários. Tempos não representam aquisição física,
durabilidade (fsync), nem o desempenho de outra máquina/disco. Não otimiza o
formato existente. O pico tracemalloc não equivale ao RSS do processo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys
import tempfile
import time
import tracemalloc

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "logica"))
from sessao_io import ArquivoDaClasse, ler_capturas


def _hash(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _tamanhos(pasta):
    arquivos = {str(p.relative_to(pasta)): p.stat().st_size for p in pasta.rglob("*") if p.is_file()}
    return {"total_bytes": sum(arquivos.values()), "arquivos_bytes": arquivos}


def benchmark(capturas=3, pontos=6000, seed=2026, *, spool=True):
    """Duas séries reais de armazenamento e um perfil alias, dados sintéticos.

    ``capturas`` é a contagem POR perfil de origem: total armazenado = 2*N,
    aliases lógicos = N. Aqui 'real' significa bloco materializado no arquivo,
    nunca medição física. A geração é excluída dos tempos adicionar/consolidar.
    """
    if isinstance(capturas, bool) or not isinstance(capturas, int) or capturas < 1:
        raise ValueError("capturas deve ser inteiro positivo")
    if isinstance(pontos, bool) or not isinstance(pontos, int) or pontos < 2:
        raise ValueError("pontos deve ser inteiro >= 2")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed deve ser inteiro >= 0")
    if tracemalloc.is_tracing():
        raise RuntimeError("tracemalloc já está ativo; execute o benchmark em processo isolado")
    rng = np.random.default_rng(seed)
    checkpoints, esperados, esperados_snr = [], {}, {}
    tempo_adicionar = tempo_consolidar = 0.0
    with tempfile.TemporaryDirectory(prefix="asd-benchmark-io-") as temporaria:
        pasta = Path(temporaria)
        tracemalloc.start()
        inicio_total = time.perf_counter()
        try:
            arquivo = ArquivoDaClasse(pasta, "99", "BENCHMARK_SINTETICO", spool=spool)
            t = np.arange(pontos) / 30_000.0
            for perfil in ("norma", "literatura"):
                arquivo.iniciar_perfil(perfil)
                adicionar_perfil = 0.0
                for indice in range(capturas):
                    ident = f"99-{indice:05d}"
                    modelo = np.sin(2 * np.pi * 60 * t + rng.uniform(0, 2 * np.pi))
                    medida = modelo + rng.normal(0, 0.001, pontos)
                    ruido = medida + rng.normal(0, np.sqrt(np.mean(medida**2)) / np.sqrt(1000), pontos)
                    esperados[(perfil, ident)] = {"medida": _hash(medida), "modelo": _hash(modelo)}
                    esperados_snr[(perfil, ident)] = _hash(ruido)
                    inicio = time.perf_counter()
                    arquivo.adicionar(perfil, id_captura=ident, medida=medida,
                                      modelo=modelo, tempo_ms=t * 1000, fs_hz=30_000,
                                      snr={30.0: ruido}, metadado={"id_captura": ident,
                                      "perfil": perfil, "pontos": pontos, "fs_hz": 30_000,
                                      "origem": "benchmark_sintetico_nao_fisico"})
                    adicionar_perfil += time.perf_counter() - inicio
                if perfil == "literatura":
                    arquivo.espelhar("literatura", ["fronteira"])
                antes = _tamanhos(pasta)
                inicio = time.perf_counter()
                arquivo.consolidar()
                consolidar_perfil = time.perf_counter() - inicio
                tempo_adicionar += adicionar_perfil
                tempo_consolidar += consolidar_perfil
                checkpoints.append({"perfil_concluido": perfil,
                                    "capturas_materializadas": arquivo.total(),
                                    "aliases_logicos": capturas if perfil == "literatura" else 0,
                                    "adicionar_s": adicionar_perfil,
                                    "consolidar_s": consolidar_perfil,
                                    "antes_consolidar": antes, "apos_consolidar": _tamanhos(pasta)})
            duracao = time.perf_counter() - inicio_total
            atual, pico = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        inicio = time.perf_counter()
        lidas = ler_capturas(pasta, versoes=("medida", "modelo"))
        snrs = ler_capturas(pasta, subpasta="snr_30db")
        for colecao, ruido in ((lidas, False), (snrs, True)):
            if len(colecao) != capturas * 3:
                raise AssertionError("contagem de leitura não preservada")
            vistas = set()
            for captura in colecao:
                origem = "literatura" if captura.perfil == "fronteira" else captura.perfil
                chave = (origem, captura.id_captura)
                vistas.add((captura.perfil, captura.id_captura))
                if ruido:
                    if _hash(captura.sinal) != esperados_snr[chave]:
                        raise AssertionError("sinal SNR não preservado")
                else:
                    for versao, resumo in esperados[chave].items():
                        if _hash(captura.versoes[versao]) != resumo:
                            raise AssertionError("sinal não preservado")
            if len(vistas) != capturas * 3:
                raise AssertionError("ids/perfis duplicados")
        for caminho in (pasta / arquivo.nome_arquivo, pasta / "snr_30db" / arquivo.nome_arquivo):
            with np.load(caminho, allow_pickle=False) as dados:
                if any(chave.startswith("fronteira/") for chave in dados.files):
                    raise AssertionError("alias duplicou bloco de arrays")
        return {"origem": "benchmark_sintetico_nao_fisico", "seed": seed,
                "pontos_por_captura": pontos, "capturas_por_perfil_origem": capturas,
                "capturas_materializadas": 2 * capturas, "aliases_logicos": capturas,
                "perfis_origem": ["norma", "literatura"], "aliases": {"fronteira": "literatura"},
                "sha256_sinais_entrada": hashlib.sha256(json.dumps(
                    [(p, ident, valores, esperados_snr[(p, ident)])
                     for (p, ident), valores in sorted(esperados.items())],
                    sort_keys=True).encode()).hexdigest(),
                "spool": spool, "adicionar_s": tempo_adicionar, "consolidar_s": tempo_consolidar,
                "duracao_com_geracao_e_checkpoints_s": duracao,
                "pico_tracemalloc_bytes": pico, "retido_tracemalloc_bytes": atual,
                "leitura_e_verificacao_s": time.perf_counter() - inicio,
                "integridade": {"ids_e_sinais_exatos": True, "snr_exato": True,
                                "aliases_sem_blocos_duplicados": True,
                                "registros_logicos_lidos": len(lidas)},
                "checkpoints": checkpoints, "armazenamento_final": _tamanhos(pasta)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capturas", type=int, nargs="+", default=[3, 10, 30], help="por perfil de origem")
    parser.add_argument("--pontos", type=int, default=6000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--sem-spool", action="store_true")
    parser.add_argument("--saida", type=Path, help="JSON novo, sem sobrescrita")
    args = parser.parse_args(argv)
    try:
        if args.saida and args.saida.exists():
            raise ValueError("arquivo de saída já existe")
        resultado = {"ambiente": {"python": platform.python_version(), "numpy": np.__version__,
                                  "plataforma": platform.platform()},
                     "limitacoes": ["Dados sintéticos: não substitui benchmark de sessão física.",
                                    "Medição em diretório temporário com cache do sistema; sem fsync.",
                                    "tracemalloc inclui geração/checkpoints, exclui leitura; não mede RSS.",
                                    "adicionar/consolidar excluem geração; tamanho é instantâneo, não bytes cumulativos escritos.",
                                    "ArquivoDaClasse.consolidar mantém spool; contabilizado separadamente nos checkpoints."],
                     "series": [benchmark(n, args.pontos, args.seed, spool=not args.sem_spool) for n in args.capturas]}
        texto = json.dumps(resultado, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.saida:
            with args.saida.open("x", encoding="utf-8") as destino:
                destino.write(texto)
        else:
            print(texto, end="")
    except (ValueError, OSError, RuntimeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
