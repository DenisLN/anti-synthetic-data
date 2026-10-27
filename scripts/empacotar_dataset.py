#!/usr/bin/env python3
"""Empacota sessões de coleta para arquivamento do DATASET no Zenodo (P-20). OFFLINE.

Nunca toca em instrumento, nunca chama API (nem a do Zenodo), nunca usa token,
não altera as pastas de origem (só lê e copia) e não escreve DOI: o DOI só existe
depois que o Zenodo o emite. Procedimento completo: ``docs/versionamento.md`` §9.

    python scripts/empacotar_dataset.py resultados/sessao_A [resultados/sessao_B ...] \\
        [--saida DIR] [--versao v1.15] [--piloto]
    python scripts/empacotar_dataset.py --verificar <pasta do pacote>

Saída (padrão ``resultados/_pacote/dataset_<versao>/``, ignorada pelo git)::

    README.txt  MANIFEST.json  SHA256SUMS  zenodo_dataset.json
    calibracao_extremos.json            só se todas as sessões com cópia usaram a mesma
    sessoes/<nome_da_sessao>/...        cópia dos dados e do metadata

Copia, por sessão: ``sessao.json``, ``falhas.json``, ``calibracao_extremos.json``,
``CURADORIA.txt``, ``*.npz`` da raiz, ``metadata/``, ``snr_*db/*.npz``, ``corrente/`` e
``tres_versoes/`` (formato 1). NÃO copia logs (``sessao.log``, ``scpi_transcricao.log``),
``relatorio_*.html``, ``sem_margem/``, ``ruido_janela/`` nem ``parcial/``: são derivados ou
diagnóstico, regeneráveis a partir do que é copiado (``docs/dataset.md`` §5).

Recusa a sessão com ``git_sujo`` verdadeiro OU indeterminado, salvo ``--piloto`` (o pacote
fica marcado como piloto no MANIFEST.json e no título). Recusa sempre a sessão cuja cópia de
``calibracao_extremos.json`` não bate com o SHA-256 gravado no metadata.

Códigos de saída: 0 ok; 1 ``--verificar`` achou divergência; 2 uso errado ou recusa.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

RAIZ = Path(__file__).resolve().parents[1]

ESQUEMA_MANIFEST = 1
REPOSITORIO_GITHUB = "https://github.com/DenisLN/anti-synthetic-data"
LICENCA_DATASET = "cc-by-4.0"
ARQUIVOS_DA_RAIZ_DA_SESSAO = ("sessao.json", "falhas.json", "calibracao_extremos.json", "CURADORIA.txt")
SUBPASTAS_COM_NPZ = ("corrente", "tres_versoes")
NOME_CALIBRACAO = "calibracao_extremos.json"
PRE_HASH = re.compile(r"^(?:.*-\d+-g)?([0-9a-f]{7,40})(-dirty)?$")


class Recusa(Exception):
    """Pedido recusado (sessão suja sem --piloto, entrada inválida, saída ocupada)."""


# ---------------------------------------------------------------- utilidades

def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _ler_json(caminho: Path) -> Any:
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def _gravar_texto(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)


def _gravar_json(caminho: Path, obj: Any) -> None:
    _gravar_texto(caminho, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n")


def versao_do_citation() -> Optional[str]:
    """Lê ``version:`` do CITATION.cff da raiz (fonte única da versão)."""
    cff = RAIZ / "CITATION.cff"
    if not cff.is_file():
        return None
    m = re.search(r"^version:\s*\"?([^\s\"#]+)\"?\s*$", cff.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def criadores_do_zenodo_json() -> List[Dict[str, str]]:
    """``creators`` de ``.zenodo.json`` (mesmos autores, mesma ordem do CITATION.cff)."""
    arq = RAIZ / ".zenodo.json"
    if not arq.is_file():
        raise Recusa(f"{arq} não existe: sem os autores decididos não há como montar o zenodo_dataset.json")
    criadores = _ler_json(arq).get("creators") or []
    if not criadores:
        raise Recusa(f"{arq} sem 'creators'")
    return [{k: c[k] for k in ("name", "orcid", "affiliation") if k in c} for c in criadores]


# ---------------------------------------------------------------- leitura da sessão

def _registros_do_metadata(sessao: Path) -> List[Dict[str, Any]]:
    registros: List[Dict[str, Any]] = []
    for jsonl in sorted((sessao / "metadata").glob("*.jsonl")):
        with open(jsonl, encoding="utf-8") as f:
            for n, linha in enumerate(f, 1):
                if not linha.strip():
                    continue
                try:
                    registros.append(json.loads(linha))
                except json.JSONDecodeError as e:
                    raise Recusa(f"{jsonl}:{n}: JSON inválido ({e})") from e
    return registros


def procedencia_da_sessao(sessao: Path) -> Dict[str, Any]:
    """Procedência (commit, árvore suja, calibração) lida de ``sessao.json`` e do metadata.

    Formato 2 tem ``sessao.json``. Sessões antigas (07/10, só ``.jsonl``) não têm: o
    commit e o ``git_sujo`` saem dos registros e, em último caso, do sufixo ``-dirty`` de
    ``versao_codigo`` (``origem`` diz de onde veio). ``git_sujo`` só é ``False`` quando
    alguma fonte o afirma e nenhuma diz ``True``; sem fonte, ``None`` (indeterminado).
    """
    sj: Dict[str, Any] = {}
    if (sessao / "sessao.json").is_file():
        sj = _ler_json(sessao / "sessao.json")
    registros = _registros_do_metadata(sessao)
    if not registros:
        raise Recusa(f"{sessao}: sem registros em metadata/*.jsonl")

    commits = sorted({r["git_commit"] for r in registros if r.get("git_commit")})
    if sj.get("git_commit"):
        commits = sorted(set(commits) | {sj["git_commit"]})
    versoes = sorted({r["versao_codigo"] for r in registros if r.get("versao_codigo")})
    if sj.get("versao_codigo"):
        versoes = sorted(set(versoes) | {sj["versao_codigo"]})

    origem_commit = "sessao.json/metadata"
    if not commits:
        for v in versoes:
            m = PRE_HASH.match(v)
            if m:
                commits.append(m.group(1))
        commits = sorted(set(commits))
        origem_commit = "versao_codigo (hash abreviado; sessão sem git_commit)" if commits else None

    votos: List[bool] = []
    if sj.get("git_sujo") is not None:
        votos.append(bool(sj["git_sujo"]))
    votos += [bool(r["git_sujo"]) for r in registros if r.get("git_sujo") is not None]
    origem_sujo = "sessao.json/metadata"
    if not votos:
        # Sem git_sujo gravado: só o sufixo -dirty prova alguma coisa (e só no sentido "sujo").
        if any(v.endswith("-dirty") for v in versoes):
            votos.append(True)
            origem_sujo = "versao_codigo termina em -dirty"
        else:
            origem_sujo = None
    git_sujo: Optional[bool] = None if not votos else any(votos)

    calibracao: Dict[str, Any] = {"presente": False, "sha256": None}
    cal = sessao / NOME_CALIBRACAO
    shas_gravados = {r["calibracao_extremos_sha256"] for r in registros if r.get("calibracao_extremos_sha256")}
    sha_sj = (sj.get("calibracao_extremos") or {}).get("sha256")
    if sha_sj:
        shas_gravados.add(sha_sj)
    if cal.is_file():
        sha = sha256_arquivo(cal)
        calibracao = {"presente": True, "sha256": sha}
        if shas_gravados and shas_gravados != {sha}:
            raise Recusa(f"{sessao}: calibracao_extremos.json (SHA-256 {sha}) não bate com o gravado no "
                         f"metadata ({sorted(shas_gravados)}); procedência inconsistente")
    elif shas_gravados:
        calibracao = {"presente": False, "sha256": None, "sha256_gravado_no_metadata": sorted(shas_gravados)}

    return {
        "sessao": sessao.name,
        "modo": sj.get("modo"),
        "formato_metadata": sj.get("formato_metadata"),
        "git_commit": commits[0] if len(commits) == 1 else None,
        "git_commits_distintos": commits,
        "git_commit_origem": origem_commit,
        "git_sujo": git_sujo,
        "git_sujo_origem": origem_sujo,
        "versao_codigo": versoes,
        "capturas_no_metadata": len(registros),
        "calibracao_extremos": calibracao,
    }


def arquivos_da_sessao(sessao: Path) -> List[Path]:
    """Caminhos (relativos à pasta da sessão, ordenados) que entram no pacote."""
    achados: List[Path] = []
    for nome in ARQUIVOS_DA_RAIZ_DA_SESSAO:
        if (sessao / nome).is_file():
            achados.append(Path(nome))
    achados += [p.relative_to(sessao) for p in sessao.glob("*.npz")]
    achados += [p.relative_to(sessao) for p in (sessao / "metadata").glob("*") if p.is_file()]
    for snr in sessao.glob("snr_*db"):
        achados += [p.relative_to(sessao) for p in snr.glob("*.npz")]
    for sub in SUBPASTAS_COM_NPZ:
        achados += [p.relative_to(sessao) for p in (sessao / sub).glob("*.npz")]
    return sorted(set(achados), key=lambda p: p.as_posix())


# ---------------------------------------------------------------- empacotar

def _dentro_de(filho: Path, pai: Path) -> bool:
    try:
        filho.resolve().relative_to(pai.resolve())
        return True
    except ValueError:
        return False


def _titulo(versao: str, piloto: bool) -> str:
    base = f"anti-synthetic-data: dataset de distúrbios de tensão ({versao})"
    return f"[PILOTO] {base}" if piloto else base


def _descricao(versao: str, piloto: bool, procedencias: Sequence[Dict[str, Any]]) -> str:
    sessoes = ", ".join(p["sessao"] for p in procedencias)
    texto = (
        f"Dataset de distúrbios de tensão em 20 classes, gerado e coletado em bancada (fonte AMETEK MX30 e "
        f"osciloscópio Keysight), versão {versao} do código em {REPOSITORIO_GITHUB}. "
        f"Sessões incluídas: {sessoes}. Cada sessão traz os arquivos .npz, o metadata por captura "
        f"(commit, árvore suja, versão do código) e a calibração de extremos usada, quando existe cópia. "
        f"Integridade: SHA256SUMS e MANIFEST.json. Licença: CC-BY 4.0."
    )
    if piloto:
        texto = ("PILOTO: ensaio do procedimento de publicação com sessão de procedência não limpa; "
                 "não é uma versão publicável do dataset. ") + texto
    return texto


def _readme(versao: str, piloto: bool, procedencias: Sequence[Dict[str, Any]]) -> str:
    linhas = [
        f"anti-synthetic-data: dataset de disturbios de tensao, versao {versao}",
        "=" * 70,
        "",
    ]
    if piloto:
        linhas += ["*** PACOTE PILOTO: contem sessao(oes) de procedencia nao limpa (git_sujo verdadeiro",
                   "*** ou indeterminado). Serve para ensaiar a publicacao; nao e a versao publicavel. ***", ""]
    linhas += [
        "LICENCA DO DATASET: Creative Commons Attribution 4.0 International (CC-BY 4.0),",
        "https://creativecommons.org/licenses/by/4.0/ . Voce pode copiar, redistribuir e adaptar,",
        "inclusive comercialmente, desde que atribua a autoria (autores em zenodo_dataset.json).",
        "O codigo que gera e le estes dados e outro objeto, sob licenca MIT, em",
        f"{REPOSITORIO_GITHUB} .",
        "",
        "Conteudo",
        "--------",
        "  sessoes/<sessao>/   dados (.npz) e metadata de cada sessao de coleta (docs/dataset.md e",
        "                      docs/metadata.md do repositorio descrevem os formatos)",
        "  MANIFEST.json       versao, procedencia (git_commit, git_sujo) de cada sessao e lista de",
        "                      arquivos com tamanho e SHA-256",
        "  SHA256SUMS          SHA-256 de todos os arquivos do pacote (menos ele mesmo)",
        "  zenodo_dataset.json metadados do deposito (sem DOI: o Zenodo o emite)",
        "",
        "Sessoes",
        "-------",
    ]
    for p in procedencias:
        linhas.append(f"  {p['sessao']}: git_commit={p['git_commit'] or p['git_commits_distintos'] or 'desconhecido'}, "
                      f"git_sujo={p['git_sujo']}, calibracao copiada={p['calibracao_extremos']['presente']}")
    linhas += [
        "",
        "Como verificar a integridade",
        "----------------------------",
        "  Com o script do repositorio:   python scripts/empacotar_dataset.py --verificar <esta pasta>",
        "  Linux/macOS, nesta pasta:      sha256sum -c SHA256SUMS",
        "  Windows (PowerShell), um arquivo:  Get-FileHash -Algorithm SHA256 <arquivo>",
        "  e compare com a linha do arquivo em SHA256SUMS.",
        "",
    ]
    return "\n".join(linhas)


def empacotar(sessoes: Sequence[Path], saida: Path, versao: str, piloto: bool = False,
              criadores: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Gera o pacote em ``saida`` e devolve o MANIFEST. Não altera as sessões."""
    if not sessoes:
        raise Recusa("nenhuma sessão informada")
    sessoes = [Path(s) for s in sessoes]
    saida = Path(saida)
    nomes = [s.name for s in sessoes]
    if len(set(nomes)) != len(nomes):
        raise Recusa(f"nomes de sessão repetidos: {nomes}")
    for s in sessoes:
        if not s.is_dir():
            raise Recusa(f"{s} não é uma pasta")
        if _dentro_de(saida, s) or _dentro_de(s, saida):
            raise Recusa(f"a saída {saida} e a sessão {s} não podem conter uma à outra")
    if saida.exists() and any(saida.iterdir()):
        raise Recusa(f"{saida} já existe e não está vazia; escolha outra saída (nada é sobrescrito)")
    criadores = criadores if criadores is not None else criadores_do_zenodo_json()

    procedencias = [procedencia_da_sessao(s) for s in sessoes]
    for p in procedencias:
        if p["git_sujo"] is not True and p["git_sujo"] is not False:
            motivo = "git_sujo indeterminado"
        elif p["git_sujo"]:
            motivo = "git_sujo verdadeiro"
        else:
            continue
        if not piloto:
            raise Recusa(f"sessão {p['sessao']}: {motivo} ({p['git_sujo_origem']}); toda coleta publicada "
                         f"sai de commit limpo (docs/versionamento.md §1). Use --piloto só para ensaio.")

    saida.mkdir(parents=True, exist_ok=True)
    entradas: List[Dict[str, Any]] = []
    for s, p in zip(sessoes, procedencias):
        arquivos = arquivos_da_sessao(s)
        if not arquivos:
            raise Recusa(f"{s}: nenhum arquivo de dados/metadata encontrado")
        p["arquivos"] = len(arquivos)
        for rel in arquivos:
            origem = s / rel
            destino_rel = Path("sessoes") / s.name / rel
            destino = saida / destino_rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origem, destino)
            sha = sha256_arquivo(destino)
            if sha != sha256_arquivo(origem):
                raise RuntimeError(f"cópia divergente de {origem}")
            entradas.append({"caminho": destino_rel.as_posix(), "sessao": s.name,
                             "tamanho": destino.stat().st_size, "sha256": sha})

    shas_cal = {p["calibracao_extremos"]["sha256"] for p in procedencias if p["calibracao_extremos"]["presente"]}
    if len(shas_cal) == 1:
        origem_cal = next(s / NOME_CALIBRACAO for s, p in zip(sessoes, procedencias)
                          if p["calibracao_extremos"]["presente"])
        shutil.copyfile(origem_cal, saida / NOME_CALIBRACAO)
        entradas.append({"caminho": NOME_CALIBRACAO, "sessao": None,
                         "tamanho": (saida / NOME_CALIBRACAO).stat().st_size,
                         "sha256": sha256_arquivo(saida / NOME_CALIBRACAO)})
        calibracao_do_pacote: Any = {"arquivo": NOME_CALIBRACAO, "sha256": next(iter(shas_cal))}
    else:
        calibracao_do_pacote = None
    avisos = []
    sem_cal = [p["sessao"] for p in procedencias if not p["calibracao_extremos"]["presente"]]
    if sem_cal:
        avisos.append(f"sem cópia de calibracao_extremos.json na sessão: {', '.join(sem_cal)} "
                      f"(sessão anterior ao formato 2, que passou a copiá-la); a calibração usada NÃO foi reconstituída")
    if len(shas_cal) > 1:
        avisos.append("sessões com calibrações diferentes: sem calibracao_extremos.json único na raiz; "
                      "use a cópia de cada pasta de sessão")

    titulo = _titulo(versao, piloto)
    zenodo = {
        "upload_type": "dataset",
        "title": titulo,
        "description": _descricao(versao, piloto, procedencias),
        "creators": criadores,
        "license": LICENCA_DATASET,
        "access_right": "open",
        "version": versao,
        "language": "por",
        "keywords": ["qualidade de energia", "distúrbios de tensão", "IEEE 1159", "dataset"],
        "related_identifiers": [{
            "relation": "isSupplementTo",
            "identifier": f"{REPOSITORIO_GITHUB}/releases/tag/{versao}",
            "scheme": "url",
            "resource_type": "software",
        }],
    }
    _gravar_json(saida / "zenodo_dataset.json", zenodo)
    _gravar_texto(saida / "README.txt", _readme(versao, piloto, procedencias))

    manifest = {
        "esquema": ESQUEMA_MANIFEST,
        "titulo": titulo,
        "versao": versao,
        "piloto": bool(piloto),
        "licenca": LICENCA_DATASET,
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repositorio": REPOSITORIO_GITHUB,
        "calibracao_extremos": calibracao_do_pacote,
        "avisos": avisos,
        "sessoes": procedencias,
        "arquivos": sorted(entradas, key=lambda e: e["caminho"]),
    }
    _gravar_json(saida / "MANIFEST.json", manifest)

    todos = sorted(p.relative_to(saida).as_posix() for p in saida.rglob("*") if p.is_file())
    linhas = [f"{sha256_arquivo(saida / rel)}  {rel}" for rel in todos]
    _gravar_texto(saida / "SHA256SUMS", "\n".join(linhas) + "\n")
    return manifest


# ---------------------------------------------------------------- verificar

def _ler_sha256sums(caminho: Path) -> Dict[str, str]:
    esperado: Dict[str, str] = {}
    with open(caminho, encoding="utf-8") as f:
        for n, linha in enumerate(f, 1):
            linha = linha.rstrip("\n")
            if not linha.strip():
                continue
            m = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", linha)
            if not m:
                raise Recusa(f"{caminho}:{n}: linha fora do formato 'sha256  caminho'")
            rel = m.group(2)
            if rel.startswith("/") or ".." in Path(rel).parts or ":" in rel:
                raise Recusa(f"{caminho}:{n}: caminho suspeito '{rel}'")
            esperado[rel] = m.group(1)
    return esperado


def verificar(pasta: Path) -> List[str]:
    """Devolve a lista de divergências (vazia = íntegro)."""
    pasta = Path(pasta)
    sums = pasta / "SHA256SUMS"
    if not pasta.is_dir() or not sums.is_file():
        raise Recusa(f"{pasta} não é um pacote (falta a pasta ou o SHA256SUMS)")
    esperado = _ler_sha256sums(sums)
    problemas: List[str] = []
    for rel, sha in sorted(esperado.items()):
        arq = pasta / rel
        if not arq.is_file():
            problemas.append(f"AUSENTE: {rel}")
        elif sha256_arquivo(arq) != sha:
            problemas.append(f"DIVERGENTE (SHA-256 diferente): {rel}")
    presentes = {p.relative_to(pasta).as_posix() for p in pasta.rglob("*") if p.is_file()} - {"SHA256SUMS"}
    for rel in sorted(presentes - set(esperado)):
        problemas.append(f"FORA DO SHA256SUMS: {rel}")
    man = pasta / "MANIFEST.json"
    if not man.is_file():
        problemas.append("AUSENTE: MANIFEST.json")
    else:
        try:
            for e in _ler_json(man).get("arquivos", []):
                rel = e["caminho"]
                if esperado.get(rel) != e["sha256"]:
                    problemas.append(f"MANIFEST não bate com SHA256SUMS: {rel}")
                elif (pasta / rel).is_file() and (pasta / rel).stat().st_size != e["tamanho"]:
                    problemas.append(f"MANIFEST: tamanho diferente: {rel}")
        except (json.JSONDecodeError, KeyError, TypeError) as err:
            problemas.append(f"MANIFEST.json ilegível: {err}")
    return problemas


# ---------------------------------------------------------------- CLI

def main(argv: Optional[Sequence[str]] = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("sessoes", nargs="*", type=Path, help="pastas de sessão (resultados/sessao_*)")
    ap.add_argument("--saida", type=Path, help="padrão: resultados/_pacote/dataset_<versao>/")
    ap.add_argument("--versao", help="padrão: version do CITATION.cff")
    ap.add_argument("--piloto", action="store_true", help="aceita sessão suja e marca o pacote como piloto")
    ap.add_argument("--verificar", type=Path, metavar="PASTA", help="confere o SHA256SUMS de um pacote")
    args = ap.parse_args(argv)
    try:
        if args.verificar:
            if args.sessoes or args.saida or args.piloto or args.versao:
                raise Recusa("--verificar não combina com sessões, --saida, --versao nem --piloto")
            problemas = verificar(args.verificar)
            if problemas:
                print(f"PACOTE COM DIVERGENCIA ({len(problemas)}):")
                for p in problemas:
                    print("  " + p)
                return 1
            n = len(_ler_sha256sums(args.verificar / "SHA256SUMS"))
            print(f"OK: {n} arquivos conferidos contra SHA256SUMS em {args.verificar}")
            return 0
        versao = args.versao or versao_do_citation()
        if not versao:
            raise Recusa("sem --versao e sem 'version:' no CITATION.cff")
        saida = args.saida or (RAIZ / "resultados" / "_pacote" / f"dataset_{versao}")
        manifest = empacotar(args.sessoes, saida, versao, piloto=args.piloto)
        print(f"Pacote {'PILOTO ' if manifest['piloto'] else ''}{versao} em {saida}: "
              f"{len(manifest['arquivos'])} arquivos de {len(manifest['sessoes'])} sessão(ões).")
        for a in manifest["avisos"]:
            print("AVISO: " + a)
        return 0
    except Recusa as e:
        print(f"RECUSADO: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
