#!/usr/bin/env python3
"""P22: benchmark offline do writer real, com integridade na leitura.

Dois modos. Sem ``--sessao``: série SINTÉTICA em diretórios temporários.
Com ``--sessao <dir>`` (repetível): mede sessões reais já gravadas, sem
modificá-las (leitura, reescrita numa CÓPIA temporária, integridade por hash,
memória, tamanho); rodar no PC/disco da bancada. Perfis espelhados são aliases
(mesma captura), não medições independentes. O JSON do modo ``--sessao`` leva
``hostname`` e ``simulado`` (``false`` só se toda sessão for modo bancada e sem
captura simulada); o agregador P-22 casa o hostname com ``pc_bancada.json``.

    python scripts/benchmark_sessao_io.py --sessao resultados/sessao_A --sessao resultados/sessao_B \\
        --saida logs/benchmark_sessao_io_bancada.json

Modo sintético: Tempos não representam aquisição física,
durabilidade (fsync), nem o desempenho de outra máquina/disco. Não otimiza o
formato existente. O pico tracemalloc não equivale ao RSS do processo.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import platform
import shutil
import socket
from pathlib import Path
import sys
import tempfile
import time
import tracemalloc

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "logica"))
from sessao_io import ARQUIVO_BLOQUEIO, ArquivoDaClasse, BloqueioSessao, SessaoEmUsoError, carregar_metadados, ler_capturas


def _hash(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _tamanhos(pasta):
    arquivos = {p.relative_to(pasta).as_posix(): p.stat().st_size for p in pasta.rglob("*") if p.is_file()}
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
    with tempfile.TemporaryDirectory(prefix="asd-benchmark-io-") as temporaria, ExitStack() as recursos:
        pasta = Path(temporaria)
        tracemalloc.start()
        inicio_total = time.perf_counter()
        try:
            arquivo = recursos.enter_context(
                ArquivoDaClasse(pasta, "99", "BENCHMARK_SINTETICO", spool=spool))
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


# --------------------------------------------------------- sessões reais (P-22)
VERSOES_TODAS = ("medida", "modelo", "programada")
TIPO_SESSOES = "benchmark_sessoes_fisicas"


def _sha_arquivo(caminho):
    h = hashlib.sha256()
    with Path(caminho).open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _pico_rss_bytes():
    """RSS de pico do PROCESSO inteiro até agora (sem dependência nova); ``None`` se indisponível."""
    try:
        import resource
        pico = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(pico if sys.platform == "darwin" else pico * 1024)
    except ImportError:
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class _Contadores(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            c = _Contadores()
            c.cb = ctypes.sizeof(c)
            k32 = ctypes.windll.kernel32
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
            return int(c.PeakWorkingSetSize) if ok else None
        except Exception:  # noqa: BLE001 - métrica opcional
            return None
    return None


def _procedencia_codigo():
    """git_commit/git_sujo do código desta execução (mestre.info_do_codigo; não abre instrumento)."""
    try:
        import mestre
        info = mestre.info_do_codigo(recalcular=True)
        return {k: info.get(k) for k in ("git_commit", "git_sujo", "versao_codigo",
                                         "arquivos_nao_rastreados")}
    except Exception as exc:  # noqa: BLE001 - procedência ausente vira None, nunca impede a medição
        return {"git_commit": None, "git_sujo": None, "versao_codigo": None,
                "arquivos_nao_rastreados": [], "erro": f"{type(exc).__name__}: {exc}"}


def _arquivos_da_sessao(pasta):
    npz = sorted(p for p in pasta.rglob("*.npz") if p.is_file())
    meta = sorted(p for p in (pasta / "metadata").glob("*.jsonl") if p.is_file())
    sj = [pasta / "sessao.json"] if (pasta / "sessao.json").is_file() else []
    return npz, meta, sj


def _hashes_de(capturas):
    """{(perfil, id): {versão: sha}}: aliases entram como chaves próprias (comparam o que o leitor entrega)."""
    saida = {}
    for c in capturas:
        saida[(c.perfil, c.id_captura)] = {v: _hash(a) for v, a in c.versoes.items()}
    return saida


def _reescrever_em_copia(capturas, destino):
    """Reescreve em ``destino`` (cópia temporária) as capturas do formato 2, 1 arquivo por classe.

    Devolve (tempo_adicionar_s, tempo_consolidar_s, n_reescritas, n_aliases_espelhados, n_nao_reescritas)."""
    grupos, nao = {}, 0
    for c in capturas:
        if c.espelho:
            continue
        if c.formato != "classe":
            nao += 1
            continue
        grupos.setdefault((c.classe_id, c.classe), []).append(c)
    t_add = t_cons = 0.0
    reescritas = espelhos = 0
    for (classe_id, nome), caps in sorted(grupos.items()):
        with ArquivoDaClasse(destino, classe_id, nome, spool=False) as arq:
            destinos_por_origem = {}
            for c in caps:
                if c.tempo_ms is None or "medida" not in c.versoes:
                    raise ValueError(f"{c.id_captura}: sem tempo_ms/medida; não reescrevível")
                meta = dict(c.metadado) if c.metadado else None
                fs = (meta or {}).get("fs_hz") or 30_000.0
                if c.perfil not in arq.perfis:
                    arq.iniciar_perfil(c.perfil)
                inicio = time.perf_counter()
                arq.adicionar(c.perfil, id_captura=c.id_captura, medida=c.versoes["medida"],
                              modelo=c.versoes.get("modelo"), programada=c.versoes.get("programada"),
                              origem_programada=c.origem_programada, inicio_janela=c.inicio_janela or 0,
                              tempo_ms=c.tempo_ms, fs_hz=fs, metadado=meta)
                t_add += time.perf_counter() - inicio
                reescritas += 1
                if c.compartilhada and len(c.perfis_compartilhados) > 1:
                    destinos_por_origem[c.perfil] = [p for p in c.perfis_compartilhados if p != c.perfil]
            for origem, dests in destinos_por_origem.items():
                arq.espelhar(origem, dests)
                espelhos += len(dests)
            inicio = time.perf_counter()
            arq.consolidar()
            t_cons += time.perf_counter() - inicio
    return t_add, t_cons, reescritas, espelhos, nao


def _lock_ocupado(pasta):
    """True se outro processo mantém ``.sessao.lock``. Sondagem não bloqueante e imediatamente liberada;
    sem ``.sessao.lock`` (nunca houve escritor com protocolo) não cria o arquivo e devolve False."""
    if not (pasta / ARQUIVO_BLOQUEIO).exists():
        return False
    try:
        BloqueioSessao(pasta, escritor=False).close()
    except SessaoEmUsoError:
        return True
    return False


def medir_sessao(pasta):
    """Mede UMA sessão real sem alterá-la (leitura + reescrita numa cópia temporária).

    Recusa (``SessaoEmUsoError``) sessão com ``.sessao.lock`` ocupado: leitura durante gravação não é confiável."""
    pasta = Path(pasta)
    if not pasta.is_dir():
        raise ValueError(f"{pasta} não é uma pasta")
    if _lock_ocupado(pasta):
        raise SessaoEmUsoError(f"sessão em uso (lock ocupado), medição não confiável: {pasta}")
    npz, meta, sj = _arquivos_da_sessao(pasta)
    if not npz:
        raise ValueError(f"{pasta}: nenhum .npz")
    antes = {p: _sha_arquivo(p) for p in (*npz, *meta, *sj)}
    sessao_json = {}
    if sj:
        try:
            lido = json.loads(sj[0].read_text(encoding="utf-8"))
            sessao_json = lido if isinstance(lido, dict) else {}
        except (OSError, ValueError):
            sessao_json = {}
    registros = []
    for m in meta:
        for linha in m.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                r = json.loads(linha)
                if isinstance(r, dict):
                    registros.append(r)
    simuladas = sum(1 for r in registros if r.get("simulado") is not False)
    if tracemalloc.is_tracing():
        raise RuntimeError("tracemalloc já está ativo; execute em processo isolado")
    tracemalloc.start()
    try:
        inicio = time.perf_counter()
        capturas = ler_capturas(pasta, versoes=VERSOES_TODAS)
        leitura_s = time.perf_counter() - inicio
        _, pico_leitura = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    esperados = _hashes_de(capturas)
    aliases = sum(1 for c in capturas if c.espelho)
    erro = None
    consolidacao = {}
    with tempfile.TemporaryDirectory(prefix="asd-bench-sessao-") as tmp:
        copia = Path(tmp)
        tracemalloc.start()
        try:
            t_add, t_cons, n_reesc, n_esp, n_nao = _reescrever_em_copia(capturas, copia)
            _, pico_reescrita = tracemalloc.get_traced_memory()
        except (ValueError, OSError) as exc:
            erro = f"{type(exc).__name__}: {exc}"
            t_add = t_cons = 0.0
            n_reesc = n_esp = n_nao = 0
            pico_reescrita = None
        finally:
            tracemalloc.stop()
        integro = False
        divergencias = []
        if erro is None:
            inicio = time.perf_counter()
            relidas = ler_capturas(copia, versoes=VERSOES_TODAS)
            releitura_s = time.perf_counter() - inicio
            obtidos = _hashes_de(relidas)
            # só o formato 2 é reescrito: compara as chaves reescritas
            reescritas_chaves = {(c.perfil, c.id_captura) for c in capturas if c.formato == "classe"}
            for chave in sorted(reescritas_chaves):
                if obtidos.get(chave) != esperados.get(chave):
                    divergencias.append(f"{chave[0]}/{chave[1]}")
            ausentes = [f"{p}/{i}" for p, i in sorted(reescritas_chaves) if (p, i) not in obtidos]
            integro = not divergencias and not ausentes and n_nao == 0
            aliases_relidos = sum(1 for c in relidas if c.espelho)
            consolidacao = {"adicionar_s": t_add, "consolidar_s": t_cons, "releitura_s": releitura_s,
                            "capturas_reescritas": n_reesc, "aliases_espelhados": n_esp,
                            "capturas_nao_reescritas_formato_1": n_nao,
                            "aliases_relidos": aliases_relidos,
                            "bytes_copia": sum(p.stat().st_size for p in copia.rglob("*.npz")),
                            "pico_tracemalloc_bytes": pico_reescrita}
        else:
            ausentes = []
    depois = {p: _sha_arquivo(p) for p in antes}
    return {
        "sessao": str(pasta), "lock_ocupado": False, "modo": sessao_json.get("modo"),
        "git_commit_da_sessao": sessao_json.get("git_commit"), "git_sujo_da_sessao": sessao_json.get("git_sujo"),
        "registros_metadata": len(registros), "capturas_simuladas": simuladas,
        "sha256_metadata": {p.name: antes[p] for p in meta},
        "sha256_sessao_json": antes[sj[0]] if sj else None,
        "sha256_npz": {p.relative_to(pasta).as_posix(): antes[p] for p in npz},
        "arquivos_npz": len(npz), "bytes_npz": sum(p.stat().st_size for p in npz),
        "capturas_logicas_lidas": len(capturas), "aliases_identificados": aliases,
        "capturas_independentes": len(capturas) - aliases,
        "leitura_s": leitura_s, "pico_tracemalloc_leitura_bytes": pico_leitura,
        "consolidacao_em_copia": consolidacao,
        "integridade": {"hash_arrays_antes_depois_iguais": integro, "divergencias": divergencias,
                        "ausentes_apos_reescrita": ausentes, "erro_reescrita": erro},
        "originais_inalterados": antes == depois,
    }


def benchmark_sessoes(pastas):
    """Mede sessões reais; ``simulado`` é False só se TODAS forem modo bancada e sem captura simulada."""
    if not pastas:
        raise ValueError("informe ao menos uma --sessao")
    unicas = {Path(p).resolve() for p in pastas}
    if len(unicas) != len(pastas):
        raise ValueError("--sessao repetida")
    sessoes = [medir_sessao(p) for p in pastas]
    fisico = all(s["modo"] == "bancada" and s["capturas_simuladas"] == 0 and s["registros_metadata"] > 0
                 for s in sessoes)
    codigo = _procedencia_codigo()
    return {"tipo": TIPO_SESSOES, "versao_schema": 1, "simulado": not fisico,
            "hostname": socket.gethostname(), "plataforma": platform.platform(),
            "versoes": {"python": platform.python_version(), "numpy": np.__version__},
            "git_commit": codigo.get("git_commit"), "git_sujo": codigo.get("git_sujo"),
            "procedencia_codigo": codigo,
            "pico_rss_processo_bytes": _pico_rss_bytes(),
            "sessoes": sessoes,
            "limitacoes": ["Tempos dependem do PC/disco onde rodou; cache do sistema e sem fsync.",
                           "Reescrita feita só em cópia temporária de formato 2; SNR/corrente não reescritos.",
                           "RSS é o pico do processo inteiro (ou null se indisponível); tracemalloc por fase.",
                           "Aliases (perfis espelhados) são a mesma captura, não medições independentes.",
                           "Nenhum limite de tempo/tamanho está definido no código/docs."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capturas", type=int, nargs="+", default=[3, 10, 30], help="por perfil de origem")
    parser.add_argument("--pontos", type=int, default=6000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--sem-spool", action="store_true")
    parser.add_argument("--sessao", type=Path, action="append", default=[],
                        help="sessão real a medir (repetível); não modifica a sessão")
    parser.add_argument("--saida", type=Path, help="JSON novo, sem sobrescrita")
    args = parser.parse_args(argv)
    try:
        if args.saida and args.saida.exists():
            raise ValueError("arquivo de saída já existe")
        if args.sessao:
            resultado = benchmark_sessoes(args.sessao)
        else:
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
