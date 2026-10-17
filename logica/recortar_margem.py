"""Recorta a margem de captura (folga antes/depois) de uma sessão da bancada.

Desde a v1.11 toda captura FÍSICA grava ``MARGEM_ANTES_S``/``MARGEM_DEPOIS_S``
(20 ms antes / 50 ms depois por padrão) em volta da janela nominal — 8100
pontos a 30 kSa/s em vez dos 6000 que ``gerar()``/o dataset simulado usam.
Este script devolve, para cada captura, só a janela NOMINAL (mesma base de
tempo de ``gerar()``), usando o MESMO recorte de ``analisar_sessao.py`` e da
validação física: ``sinais.janela_nominal()`` alinhada pelo ``indice_trigger``
real gravado no metadata (H-REF10, CHANGELOG/v1.11.md).

Nunca altera a sessão original: escreve numa pasta nova (padrão
``<sessao>/sem_margem/``) com a mesma estrutura — um ``NN_classe.npz`` por
classe (formato 2, ``sessao_io.py``: perfis × versões), ``snr_XXdb/``,
``corrente/`` e ``metadata/*.jsonl`` — de modo que ``analisar_sessao.py`` e
``relatorio_html.py`` rodam nela sem mudança. Cada linha do metadata ganha um
bloco ``recorte`` (de onde saiu a janela) e passa a descrever o arquivo
recortado (``margem_amostras_* = 0``, ``indice_trigger`` reindexado,
``inicio_janela = 0``). Lê sessões nos DOIS formatos (um ``.npz`` por captura,
anterior à v1.15, ou um por classe); a saída é sempre o formato 2, então
recortar uma sessão antiga também a converte.

``--empilhar`` não faz mais nada (o formato 2 já é um ``.npz`` por classe com
as capturas empilhadas); a opção continua aceita só para não quebrar scripts.

Sem hardware: roda em qualquer máquina, só precisa dos arquivos já gravados.

Uso:
    python logica/recortar_margem.py resultados/sessao_2026-09-30_14-00-00
    python logica/recortar_margem.py resultados/sessao_... --saida recortado --empilhar
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "logica") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "logica"))
import sessao_io  # noqa: E402
from sinais import janela_nominal  # noqa: E402

PASTA_SAIDA_PADRAO = "sem_margem"


def carregar_metadados(sessao_dir: Path) -> "sessao_io.MetadadosDaSessao":
    """``id_captura`` -> linha do metadata, de todos os ``metadata/*.jsonl``
    (``sessao_io.carregar_metadados``; ``.buscar(perfil, id)`` separa os perfis
    de uma sessão ``set perfil todos``, onde o mesmo id existe em cada um)."""
    return sessao_io.carregar_metadados(sessao_dir)


def diretorios_de_dados(sessao_dir: Path) -> List[Path]:
    """Pasta da sessão + ``snr_XXdb/`` + ``corrente/`` — só o que a bancada
    grava. ``analise/``, ``parcial/``, ``sem_margem/`` etc. ficam de fora."""
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
    elif metadado.get("inicio_janela") is not None:
        # Gravado pela bancada (já com o limite do registro aplicado): ninguém
        # precisa refazer indice_trigger - pre_trigger_s * fs.
        origem = "inicio_janela"
        inicio_ideal = int(metadado["inicio_janela"])
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
    else:  # inicio_janela, margem_amostras_antes e sem_margem
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
    if info["origem"] in ("inicio_janela", "indice_trigger", "margem_amostras_antes"):
        novo["margem_amostras_antes"] = 0
        novo["margem_amostras_depois"] = 0
        novo["amostras_totais"] = info["fim_amostra"] - info["inicio_amostra"]
        if "inicio_janela" in novo:
            # O arquivo recortado JÁ começa na janela nominal.
            novo["inicio_janela"] = 0
            novo["inicio_janela_ajustado"] = False
        if metadado.get("indice_trigger") is not None:
            novo["indice_trigger"] = int(metadado["indice_trigger"]) - info["inicio_amostra"]
    return novo


def _tempo_recortado(captura, inicio: int, pontos: int, fs_hz: float) -> np.ndarray:
    tempo = captura.tempo_ms
    if tempo is not None and tempo.size == captura.sinal.size:
        return tempo[inicio : inicio + pontos] - tempo[inicio]
    return np.arange(pontos) / fs_hz * 1000.0


def recortar_sessao(
    sessao_dir: Path, saida_dir: Path, *, empilhar: bool = False,
) -> List[dict]:
    """Recorta toda a sessão. Devolve uma linha de relatório por captura
    (por diretório), com ``erro`` quando não deu para recortar.
    ``empilhar`` é ignorado (o formato 2 já é empilhado por classe)."""
    sessao_dir = sessao_dir.resolve()
    saida_dir = saida_dir.resolve()
    if saida_dir == sessao_dir:
        raise ValueError("A saída não pode ser a própria pasta da sessão (os originais seriam sobrescritos)")
    metadados = sessao_io.carregar_metadados(sessao_dir)
    relatorio: List[dict] = []
    metadados_saida: Dict[Tuple[str, str], dict] = {}
    por_chave_snr: Dict[Tuple[str, str], Dict[float, np.ndarray]] = {}
    por_chave_corrente: Dict[Tuple[str, str], np.ndarray] = {}

    for origem_dir in diretorios_de_dados(sessao_dir)[1:]:
        nivel = sessao_io.nivel_da_pasta_snr(origem_dir.name)
        for captura in sessao_io.ler_pasta(origem_dir, metadados):
            if captura.espelho:
                continue  # mesma captura de outro perfil (set perfil todos)
            inicio, pontos, info = calcular_recorte(captura.sinal.size, captura.metadado)
            janela = captura.sinal[inicio : inicio + pontos]
            if nivel is not None:
                por_chave_snr.setdefault(captura.chave, {})[nivel] = janela
            else:
                por_chave_corrente[captura.chave] = janela
            relatorio.append({
                "arquivo": str(origem_dir.relative_to(sessao_dir) / captura.arquivo.name),
                "id_captura": captura.id_captura, "perfil": captura.perfil, **info,
            })

    capturas = sessao_io.ler_pasta(sessao_dir, metadados, versoes=sessao_io.VERSOES)
    capturas.sort(key=lambda c: (c.classe_id, c.perfil, c.id_captura))
    with ExitStack() as recursos:
        arquivos: Dict[str, "sessao_io.ArquivoDaClasse"] = {}
        espelhos: Dict[str, Dict[str, List[str]]] = {}  # classe -> origem -> perfis espelho
        for captura in capturas:
            if captura.espelho:  # mesma captura de outro perfil: só se re-espelha
                espelhos.setdefault(captura.classe_id, {}).setdefault(str(captura.perfil_de_origem), [])
                if captura.perfil not in espelhos[captura.classe_id][str(captura.perfil_de_origem)]:
                    espelhos[captura.classe_id][str(captura.perfil_de_origem)].append(captura.perfil)
                continue
            if captura.grandeza != "Tensão" or "medida" not in captura.versoes:
                continue
            medida = captura.versoes["medida"]
            metadado = captura.metadado
            inicio, pontos, info = calcular_recorte(medida.size, metadado)
            fs_hz = float((metadado or {}).get("fs_hz", 30_000.0))
            novo = metadado_recortado(metadado, info) if metadado is not None else None
            if novo is not None:
                metadados_saida[captura.chave] = novo
            arquivo = arquivos.get(captura.classe_id)
            if arquivo is None:
                arquivo = arquivos[captura.classe_id] = recursos.enter_context(sessao_io.ArquivoDaClasse(
                    saida_dir, captura.classe_id, captura.classe, spool=False,
                ))
            corrente = por_chave_corrente.get(captura.chave)
            modelo = captura.versoes.get("modelo")
            arquivo.adicionar(
                captura.perfil, id_captura=captura.id_captura, medida=medida[inicio : inicio + pontos],
                tempo_ms=_tempo_recortado(captura, inicio, pontos, fs_hz), fs_hz=fs_hz,
                modelo=modelo, programada=captura.versoes.get("programada"),
                origem_programada=captura.origem_programada, inicio_janela=0,
                pontos=int(modelo.size) if modelo is not None else pontos,
                snr=por_chave_snr.get(captura.chave), corrente=corrente, metadado=novo,
            )
            relatorio.append({
                "arquivo": captura.arquivo.name, "id_captura": captura.id_captura, "perfil": captura.perfil, **info,
            })
        for classe_id, arquivo in arquivos.items():
            for origem, destinos in espelhos.get(classe_id, {}).items():
                if origem in arquivo.perfis:
                    arquivo.espelhar(origem, destinos)
            try:
                arquivo.consolidar()
            except ValueError as exc:
                relatorio.append({"arquivo": arquivo.nome_arquivo, "erro": str(exc)})

        # Metadata: um .jsonl por classe, mesmo nome do original, com as mesmas
        # linhas na mesma ordem (a recortada onde houve dado).
        metadata_origem = sessao_dir / "metadata"
        if metadata_origem.is_dir():
            (saida_dir / "metadata").mkdir(parents=True, exist_ok=True)
            for jsonl_path in sorted(metadata_origem.glob("*.jsonl")):
                linhas = []
                for linha in jsonl_path.read_text(encoding="utf-8").splitlines():
                    if not linha.strip():
                        continue
                    registro = json.loads(linha)
                    chave = (str(registro.get("perfil") or sessao_io.PERFIL_LEGADO), str(registro["id_captura"]))
                    novo = metadados_saida.get(chave, registro)
                    origem = registro.get("perfil_de_origem")
                    if novo is registro and origem and origem != chave[0] \
                            and (origem, chave[1]) in metadados_saida:
                        # Espelho (captura compartilhada): a mesma linha da origem recortada.
                        novo = dict(metadados_saida[(origem, chave[1])], perfil=chave[0])
                    linhas.append(json.dumps(novo, ensure_ascii=False, sort_keys=True))
                destino = saida_dir / "metadata" / jsonl_path.name
                parcial = destino.with_suffix(".jsonl.part")
                parcial.write_text("\n".join(linhas) + ("\n" if linhas else ""), encoding="utf-8")
                os.replace(parcial, destino)
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
                        help="(sem efeito desde o formato 2: o .npz já é um por classe, empilhado)")
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
