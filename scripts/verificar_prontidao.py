#!/usr/bin/env python3
"""Gate offline de encerramento: 31 pendências e cinco condições físicas.

Valida estrutura, procedência declarada e arquivos referidos; não autentica
medições nem interpreta a suficiência científica de documentos. Nunca cria
capturas, inventa evidências ou solicita aprovação adicional para executar.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import zipfile

import numpy as np

CONDICOES = {"127V_60Hz": (127, 60), "127V_50Hz": (127, 50),
             "230V_50Hz": (230, 50), "220V_60Hz": (220, 60), "33V_60Hz": (33, 60)}
PENDENCIAS = tuple(f"P{n:02d}" for n in range(1, 32))


def _relativo(base, texto, diretorio=False):
    if not isinstance(texto, str) or not texto.strip() or Path(texto).is_absolute():
        raise ValueError("caminho relativo não vazio obrigatório")
    caminho = (base / texto).resolve()
    if not caminho.is_relative_to(base.resolve()):
        raise ValueError("caminho fora da pasta do manifesto/sessão")
    if not (caminho.is_dir() if diretorio else caminho.is_file()):
        raise ValueError(f"{'pasta' if diretorio else 'arquivo'} inexistente: {texto}")
    return caminho


def _evidencias(base, valor, contexto, faltantes):
    if not isinstance(valor, list) or not valor:
        faltantes.append(f"{contexto}: evidências não vazias obrigatórias")
        return
    for item in valor:
        try:
            _relativo(base, item)
        except ValueError as exc:
            faltantes.append(f"{contexto}: {exc}")


def _sessao(base, texto, condicao, faltantes):
    resumo = {"classes_aprovadas": [], "capturas_independentes": 0, "aliases_ignorados": 0}
    try:
        pasta = _relativo(base, texto, diretorio=True)
        info = json.loads(_relativo(pasta, "sessao.json").read_text(encoding="utf-8"))
        if not isinstance(info, dict):
            raise ValueError("sessao.json deve ser objeto")
        if info.get("modo") != "bancada" or info.get("simulado") is True:
            raise ValueError("sessão não é de bancada física")
        if info.get("fixture_sintetica") or info.get("origem") in ("sintetica", "benchmark_sintetico_nao_fisico"):
            raise ValueError("fixture/dados sintéticos não comprovam sessão física")
        if info.get("git_sujo") is not False or not isinstance(info.get("git_commit"), str) or not info["git_commit"].strip():
            raise ValueError("sessão exige git_sujo=false e git_commit não vazio")
        if info.get("bateria_excluir") or info.get("BATERIA_EXCLUIR"):
            raise ValueError("sessão declara classes excluídas")
        arquivos = sorted((pasta / "metadata").glob("*.jsonl"))
        if not arquivos:
            raise ValueError("metadata/*.jsonl ausente")
    except (ValueError, OSError) as exc:
        faltantes.append(f"{condicao}: {exc}")
        return resumo
    classes, vistas = set(), set()
    v, f = CONDICOES[condicao]
    for arquivo in arquivos:
        match = re.match(r"(\d{2})_", arquivo.name)
        if not match or not 1 <= int(match[1]) <= 20:
            faltantes.append(f"{condicao}: metadata sem classe válida: {arquivo.name}")
            continue
        classe = match[1]
        try:
            arquivo = _relativo(pasta, str(arquivo.relative_to(pasta)))
            linhas = arquivo.read_text(encoding="utf-8").splitlines()
        except (ValueError, OSError) as exc:
            faltantes.append(f"{condicao}: {exc}")
            continue
        for numero, linha in enumerate(linhas, 1):
            if not linha.strip():
                continue
            contexto = f"{condicao}/{arquivo.name}:{numero}"
            try:
                md = json.loads(linha)
                if not isinstance(md, dict):
                    raise ValueError("registro deve ser objeto")
                if md.get("simulado") is not False or md.get("fixture_sintetica"):
                    raise ValueError("captura simulada, sem declaração física ou fixture")
                if md.get("git_sujo") is not False or md.get("git_commit") != info["git_commit"]:
                    raise ValueError("procedência da captura difere da sessão limpa")
                if md.get("tensao_base_rms") != v or md.get("f0_hz") != f:
                    raise ValueError("tensão/frequência não correspondem à condição")
                validacao = md.get("validacao_fisica")
                if not isinstance(validacao, dict) or validacao.get("ok") is not True or validacao.get("motivos"):
                    raise ValueError("validacao_fisica.ok=true, sem motivos de reprovação, obrigatória")
                perfil, ident = md.get("perfil"), md.get("id_captura")
                if perfil not in ("norma", "literatura", "fronteira") or not isinstance(ident, str) or not ident:
                    raise ValueError("perfil/id_captura ausente ou inválido")
                if md.get("captura_compartilhada") and md.get("perfil_de_origem") != perfil:
                    resumo["aliases_ignorados"] += 1
                    continue
                nome = md.get("arquivo_classe")
                if not isinstance(nome, str) or not nome.startswith(classe + "_") or not nome.endswith(".npz"):
                    raise ValueError("arquivo_classe não corresponde à classe")
                npz = _relativo(pasta, nome)
                indice = md.get("indice_no_arquivo")
                if isinstance(indice, bool) or not isinstance(indice, int) or indice < 0:
                    raise ValueError("indice_no_arquivo inválido")
                with np.load(npz, allow_pickle=False) as dados:
                    ids = dados[f"{perfil}/id_captura"]
                    sinal = dados[f"{perfil}/medida"][indice]
                    if str(ids[indice]) != ident or sinal.ndim != 1 or sinal.size < 2 or not np.all(np.isfinite(sinal)):
                        raise ValueError("id/sinal NPZ inconsistente ou não finito")
                chave = (classe, perfil, ident)
                if chave in vistas:
                    raise ValueError("captura independente duplicada no metadata")
                vistas.add(chave)
                classes.add(classe)
                resumo["capturas_independentes"] += 1
            except (ValueError, KeyError, IndexError, TypeError, OSError, zipfile.BadZipFile) as exc:
                faltantes.append(f"{contexto}: {exc}")
    resumo["classes_aprovadas"] = sorted(classes)
    ausentes = sorted({f"{n:02d}" for n in range(1, 21)} - classes)
    if ausentes:
        faltantes.append(f"{condicao}: classes sem captura física aprovada: {', '.join(ausentes)}")
    return resumo


def verificar(manifesto):
    manifesto = Path(manifesto).resolve()
    faltantes, sessoes = [], {}
    try:
        dados = json.loads(manifesto.read_text(encoding="utf-8"))
        if not isinstance(dados, dict):
            raise ValueError("manifesto deve ser objeto")
    except (OSError, ValueError) as exc:
        return {"pronto": False, "faltantes": [str(exc)], "sessoes": {}}
    base = manifesto.parent
    pendencias = dados.get("pendencias", {})
    if not isinstance(pendencias, dict):
        pendencias = {}
    for ident in PENDENCIAS:
        item = pendencias.get(ident)
        if not isinstance(item, dict) or item.get("status") != "concluida":
            faltantes.append(f"{ident}: status concluida obrigatório")
        if isinstance(item, dict):
            _evidencias(base, item.get("evidencias"), ident, faltantes)
    entradas = dados.get("sessoes", {})
    if not isinstance(entradas, dict):
        entradas = {}
    for condicao in CONDICOES:
        sessoes[condicao] = _sessao(base, entradas.get(condicao), condicao, faltantes)
    return {"pronto": not faltantes, "faltantes": faltantes, "sessoes": sessoes,
            "escopo": "Verificação estrutural de arquivos e declarações. Não autentica a origem física nem substitui a análise científica das evidências.",
            "cobertura": "20 classes por condição, ao menos uma captura independente aprovada por classe; aliases não são novas aquisições."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifesto", required=True, type=Path)
    parser.add_argument("--saida", type=Path, help="JSON novo, sem sobrescrita")
    args = parser.parse_args(argv)
    resultado = verificar(args.manifesto)
    texto = json.dumps(resultado, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.saida:
        try:
            with args.saida.open("x", encoding="utf-8") as destino:
                destino.write(texto)
        except OSError as exc:
            parser.error(str(exc))
    else:
        print(texto, end="")
    return 0 if resultado["pronto"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
