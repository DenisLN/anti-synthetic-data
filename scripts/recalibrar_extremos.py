"""Recalcula os fatores de extremo (``logica/calibracao_extremos.json``) a
partir do metadata de sessões de bancada — OFFLINE, sem hardware.

Fator de uma captura = max(|pico_medido_v|, |vale_medido_v|) (VMAX/VMIN do
Keysight na taxa cheia) ÷ pico PROGRAMADO, com a MESMA definição de
``ExperimentoBase.pico_programado_v`` (máximo |forma prevista| × pico
nominal, ou rms programado × √2 se maior). Sessões a partir da v1.13 gravam
``pico_programado_v`` no metadata; nas anteriores ele é reconstruído pelo
próprio código da classe com a ``seed`` e o ``nivel_indice`` gravados.

Os fatores são separados por CONDIÇÃO de bancada (tensão base e frequência
do metadata, v1.14): cada condição tem a sua tabela em
``calibracao_extremos.json`` (``por_condicao``), porque a resposta da saída
muda com elas (2026-10-07: a 17 foi de 1,03 a 127 V/60 Hz para 1,24 a
230 V/50 Hz).

Capturas com o distúrbio reduzido pelo limite de bancada
(``fator_disturbio_bancada`` = k) entram invertendo o modelo da previsão
(``mestre.extremo_previsto_com_disturbio_v``, sem a margem):

    extremo = f_ref × pico + k × (fator - f_ref) × pico_modelo
    fator   = f_ref + (extremo - f_ref × pico) / (k × pico_modelo)

com f_ref = fator da 01 NA MESMA condição (medido nestas sessões ou, sem
isso, o da tabela). Vale o maior entre esse e extremo/pico (conservador).
Sem isso, numa condição alta quase toda classe roda reduzida e não haveria
como calibrá-la.

Fora do cálculo (e contadas no relatório):
- a 08 (modelo próprio do impulso, ``SOBRESSINAL/SUBSINAL_DO_DEGRAU``);
- capturas reduzidas sem f_ref da 01 nessa condição;
- capturas sem VMAX/VMIN (``extremos_indisponiveis``) ou simuladas.

Fator proposto por classe = o MAIOR medido nas sessões dadas. Sem
``--gravar`` só imprime. Com ``--gravar``, nenhum fator DIMINUI (vale o
maior entre o atual e o medido: baixar um fator enfraquece a pré-validação)
— a não ser com ``--substituir``, opção explícita (enfraquece a pré-validação).

Uso (na raiz do projeto):
    env\\Scripts\\python scripts\\recalibrar_extremos.py resultados\\sessao_A resultados\\sessao_B
    env\\Scripts\\python scripts\\recalibrar_extremos.py resultados\\sessao_A --gravar
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import math
import statistics
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "logica"))

import mestre  # noqa: E402
from ametek_orm import AmetekMX30  # noqa: E402


class _OscOffline:
    """Não-``None``: reconstrói pelo ramo de BANCADA de ``gerar()``."""


def _scripts_por_id() -> Dict[str, Path]:
    return {script.stem: script for script in mestre._experiment_scripts()}


def pico_programado_reconstruido_v(registro: dict, script_path: Path) -> float:
    """Reconstrói o pico programado de uma captura de sessão ANTIGA (sem
    ``pico_programado_v`` no metadata) com o código atual da classe."""
    config = mestre.Config(
        fs_hz=float(registro["fs_hz"]), points=int(registro["pontos"]), duration_s=mestre.DURATION_S,
        grid_frequency_hz=float(registro.get("f0_hz", 60.0)),
        base_voltage_rms=float(registro.get("tensao_base_rms", 127.0)), snr_levels_db=(),
        base_seed=int(registro.get("base_seed", 0)), capture_current=False, current_base_a=None,
        results_dir=PROJECT_ROOT / "resultados", sim_captures_per_class=1, real_captures_per_class=1,
        disturbance_start_s=mestre.DISTURBANCE_START_S,
        capturas_override=registro.get("capturas_override"),
        # Sessões anteriores à v1.15 não sortearam início/duração/fase.
        sorteio_posicao=bool(registro.get("sorteio_posicao", False)),
    )
    teto = float(registro.get("teto_extremos_v", 415.8))
    fonte = AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=max(teto, 415.8))
    experimento_cls = mestre.Bancada._carregar_classe_experimento(script_path)
    experimento = experimento_cls(mestre.Bancada(fonte, _OscOffline(), config))
    # O total que gerar() viu na sessão (padrão da classe só existe a partir
    # da v1.13; antes, 1).
    experimento.config = dataclasses.replace(
        experimento.config, capturas_padrao_classe=int(registro.get("capturas_padrao_classe", 1)),
    )
    t = mestre.tempo(config)
    return experimento.pico_programado_v(int(registro.get("nivel_indice", 0)), t, int(registro["seed"]))


def condicao_do_registro(registro: dict) -> Tuple[str, float, float]:
    tensao = float(registro.get("tensao_base_rms", 127.0))
    frequencia = float(registro.get("f0_hz", 60.0))
    return mestre.chave_condicao(tensao, frequencia), tensao, frequencia


def fator_de_captura_reduzida(registro: dict, extremo_v: float, fator_referencia: float) -> float:
    """Fator equivalente ao distúrbio INTEIRO de uma captura que rodou com o
    distúrbio reduzido a k (ver docstring do módulo)."""
    parametros = registro["parametros"]
    k = float(parametros["fator_disturbio_bancada"])
    pico_modelo = float(parametros["pico_programado_modelo_v"])
    pico = float(registro["pico_programado_v"])
    invertido = fator_referencia + (extremo_v - fator_referencia * pico) / (k * pico_modelo)
    return max(invertido, extremo_v / pico)


Fatores = Dict[str, Dict[str, List[float]]]


def coletar(
    sessoes: List[Path], tabelas_atuais: Optional[Dict[str, Dict[str, object]]] = None,
) -> Tuple[Fatores, Dict[str, int], Dict[str, Tuple[float, float]]]:
    """{condição: {classe: [fatores]}}, contagem de ignoradas e
    {condição: (tensão, frequência)}. ``tabelas_atuais`` (de
    ``mestre.carregar_calibracao_extremos``) só dá o f_ref da 01 quando as
    sessões não têm a 01 na condição."""
    scripts = _scripts_por_id()
    fatores: Fatores = {}
    condicoes: Dict[str, Tuple[float, float]] = {}
    reduzidas: List[Tuple[str, str, dict, float]] = []
    ignoradas = {
        "08 (modelo próprio)": 0, "reduzida sem referência 01": 0, "sem VMAX/VMIN": 0, "simulada": 0,
    }
    # Reconstrução sempre com o distúrbio inteiro (definição do fator).
    limite_original = mestre.LIMITE_BANCADA_DISTURBIO
    mestre.LIMITE_BANCADA_DISTURBIO = False
    try:
        for sessao in sessoes:
            # resultados/sessao_*/metadata/*.jsonl, ou os .jsonl soltos (como em
            # `arquivo/analises:docs/analise-2026-09-30/dados/`).
            pasta = Path(sessao) / "metadata"
            arquivos = sorted(pasta.glob("*.jsonl")) or sorted(Path(sessao).glob("*.jsonl"))
            if not arquivos:
                raise SystemExit(f"{sessao}: nenhum .jsonl em metadata/ nem na própria pasta")
            for jsonl in arquivos:
                for linha in jsonl.read_text(encoding="utf-8").splitlines():
                    if not linha.strip():
                        continue
                    registro = json.loads(linha)
                    classe_id = str(registro["id_captura"]).split("-")[0].zfill(2)
                    if registro.get("simulado"):
                        ignoradas["simulada"] += 1
                        continue
                    if classe_id == "08":
                        ignoradas["08 (modelo próprio)"] += 1
                        continue
                    if "pico_medido_v" not in registro or "vale_medido_v" not in registro:
                        ignoradas["sem VMAX/VMIN"] += 1
                        continue
                    chave, tensao, frequencia = condicao_do_registro(registro)
                    condicoes[chave] = (tensao, frequencia)
                    extremo = max(abs(float(registro["pico_medido_v"])), abs(float(registro["vale_medido_v"])))
                    if "fator_disturbio_bancada" in (registro.get("parametros") or {}):
                        reduzidas.append((chave, classe_id, registro, extremo))
                        continue
                    pico = registro.get("pico_programado_v")
                    if pico is None:
                        pico = pico_programado_reconstruido_v(registro, scripts[classe_id])
                    fatores.setdefault(chave, {}).setdefault(classe_id, []).append(extremo / float(pico))
    finally:
        mestre.LIMITE_BANCADA_DISTURBIO = limite_original

    referencia = mestre.CLASSE_REFERENCIA_EXTREMO
    for chave, classe_id, registro, extremo in reduzidas:
        medidos_01 = fatores.get(chave, {}).get(referencia)
        if medidos_01:
            fator_01: Optional[float] = max(medidos_01)
        else:
            tensao, frequencia = condicoes[chave]
            atual = mestre.condicao_calibrada(tabelas_atuais or {}, tensao, frequencia)
            fator_01 = (tabelas_atuais or {}).get(atual, {}).get("fatores", {}).get(referencia) if atual else None  # type: ignore[union-attr]
        if fator_01 is None:
            ignoradas["reduzida sem referência 01"] += 1
            continue
        fator = fator_de_captura_reduzida(registro, extremo, max(1.0, float(fator_01)))
        fatores.setdefault(chave, {}).setdefault(classe_id, []).append(fator)
    return fatores, ignoradas, condicoes


class MudancaDeFator(NamedTuple):
    """Um fator que a recalibração muda (ou criaria) em ``tabela``."""
    tabela: str
    classe: str
    antes: Optional[float]
    depois: float
    capturas: int


class ResultadoRecalibracao:
    def __init__(self, arquivo: Optional[Path] = None) -> None:
        self.arquivo = arquivo
        self.mudancas: List[MudancaDeFator] = []
        self.ignoradas: Dict[str, int] = {}
        self.gravado = False
        # Só no modo automático (ver ``recalibrar``): o que ficou de fora para
        # nunca baixar o fator efetivo e o operador decidir à mão.
        self.condicoes_sem_tabela: List[str] = []
        self.classes_nao_gravadas: List[Tuple[str, str, float, float]] = []
        self.capturas_medidas = 0


def _nada(*_args, **_kwargs) -> None:
    return None


def recalibrar(
    sessoes: List[Path], *, gravar: bool = False, substituir: bool = False,
    arquivo: Optional[Path] = None, automatico: bool = False, saida=print,
) -> ResultadoRecalibracao:
    """O que ``main`` faz, como função: recalcula os fatores das ``sessoes``,
    imprime as tabelas por ``saida`` (``None`` fica mudo) e, com ``gravar``,
    atualiza ``arquivo`` (padrão: a calibração em uso).

    ``automatico`` (chamado pela CLI ao fim de um ``run``, ``set
    recalibracao on``) é o modo que NUNCA diminui o fator efetivo:
    - ``substituir`` é recusado (``ValueError``);
    - condição sem tabela própria NÃO é criada (uma tabela nova trocaria o
      fator conservador da regra de fallback por um medido numa sessão só);
      fica em ``condicoes_sem_tabela`` para rodar o script à mão;
    - classe sem entrada na tabela só entra se o medido não ficar abaixo do
      fator que a bateria efetivamente usou (``carregar_fatores_extremo``);
    - só as tabelas em que algum fator mudou são regravadas."""
    if automatico and substituir:
        raise ValueError("A recalibração automática nunca usa --substituir")
    saida = saida or _nada
    arquivo = Path(mestre.CALIBRACAO_EXTREMOS_PATH if arquivo is None else arquivo)
    resultado = ResultadoRecalibracao(arquivo=arquivo)
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    tabelas = mestre.carregar_calibracao_extremos(arquivo)
    if "por_condicao" not in dados:  # formato da v1.13: migra
        dados["por_condicao"] = {
            chave: {"tensao_rms": t["tensao_rms"], "frequencia_hz": t["frequencia_hz"],
                    "origem": dados.pop("origem", ""), "fatores": dados.pop("fatores")}
            for chave, t in tabelas.items()
        }
    medidos, ignoradas, condicoes = coletar(sessoes, tabelas)
    resultado.ignoradas = dict(ignoradas)
    resultado.capturas_medidas = sum(len(v) for por_classe in medidos.values() for v in por_classe.values())

    gravacoes: Dict[str, Dict[str, float]] = {}
    for chave in sorted(medidos):
        tensao, frequencia = condicoes[chave]
        existente = mestre.condicao_calibrada(tabelas, tensao, frequencia)
        if automatico and existente is None:
            resultado.condicoes_sem_tabela.append(chave)
            saida(f"\n## {chave}: sem tabela própria; não criada no modo automático")
            continue
        atuais = dict(tabelas[existente]["fatores"]) if existente else {}  # type: ignore[arg-type]
        efetivos = (
            mestre.carregar_fatores_extremo(arquivo, tensao_rms=tensao, frequencia_hz=frequencia)
            if automatico else {}
        )
        destino = existente or chave
        saida(f"\n## {chave} -> tabela {destino}" + ("" if existente else " (NOVA)"))
        saida("| Classe | Capturas | Fator mín. | Mediana | Máx. (proposto) | Atual | Gravaria |")
        saida("|---|---|---|---|---|---|---|")
        novos = dict(atuais)
        for classe_id in sorted(set(atuais) | set(medidos[chave])):
            valores = medidos[chave].get(classe_id, [])
            atual = atuais.get(classe_id)
            if not valores:
                saida(f"| {classe_id} | 0 | — | — | — | {atual if atual is not None else '—'} | {atual} (sem dado) |")
                continue
            proposto = round(max(valores), 3)
            efetivo = mestre.fator_extremo_da_classe(classe_id, efetivos) if automatico else 0.0
            if automatico and atual is None and proposto < efetivo:
                resultado.classes_nao_gravadas.append((destino, classe_id, proposto, efetivo))
                saida(
                    f"| {classe_id} | {len(valores)} | {min(valores):.3f} | {statistics.median(valores):.3f} "
                    f"| {proposto:.3f} | — | não gravado (abaixo do fator efetivo {efetivo:.3f}) |"
                )
                continue
            gravaria = proposto if (substituir or atual is None) else max(proposto, atual)
            novos[classe_id] = gravaria
            saida(
                f"| {classe_id} | {len(valores)} | {min(valores):.3f} | {statistics.median(valores):.3f} "
                f"| {proposto:.3f} | {'—' if atual is None else f'{atual:.3f}'} | {gravaria:.3f} |"
            )
        if any(not math.isfinite(v) or v <= 0 for v in novos.values()):
            raise SystemExit(f"Fator inválido calculado em {chave} — nada gravado.")
        mudancas = [
            MudancaDeFator(destino, classe_id, atuais.get(classe_id), valor, len(medidos[chave].get(classe_id, [])))
            for classe_id, valor in sorted(novos.items()) if valor != atuais.get(classe_id)
        ]
        resultado.mudancas.extend(mudancas)
        if mudancas or not automatico:
            gravacoes[destino] = novos
    saida("")
    saida("Ignoradas: " + ", ".join(f"{motivo}: {n}" for motivo, n in ignoradas.items()))
    if gravar and gravacoes:
        for destino, novos in gravacoes.items():
            tabela = dados["por_condicao"].setdefault(destino, {})
            if "tensao_rms" not in tabela:
                tabela["tensao_rms"], tabela["frequencia_hz"] = condicoes[destino]
            tabela["origem"] = (
                "scripts/recalibrar_extremos.py sobre: " + ", ".join(str(s) for s in sessoes)
                + (" (substituindo)" if substituir else " (nenhum fator diminuiu)")
                + (" [automático, CLI]" if automatico else "")
                + (f"; antes: {tabela['origem']}" if tabela.get("origem") else "")
            )
            tabela["fatores"] = {k: novos[k] for k in sorted(novos)}
        arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        resultado.gravado = True
        saida(f"Gravado em {arquivo}. Confira com 'git diff' e rode tests/test_offline.py.")
    else:
        saida("Nada gravado (use --gravar)." if not gravar else "Nada gravado (nenhum fator mudou).")
    return resultado


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sessoes", nargs="+", type=Path, help="pastas resultados/sessao_* (com metadata/)")
    parser.add_argument("--gravar", action="store_true", help="atualiza logica/calibracao_extremos.json")
    parser.add_argument(
        "--substituir", action="store_true",
        help="com --gravar: usa o medido mesmo quando é MENOR que o atual (enfraquece a pré-validação)",
    )
    parser.add_argument("--arquivo", type=Path, default=mestre.CALIBRACAO_EXTREMOS_PATH)
    args = parser.parse_args(argv)
    logging.getLogger("MestreExperimentos").setLevel(logging.ERROR)
    recalibrar(args.sessoes, gravar=args.gravar, substituir=args.substituir, arquivo=args.arquivo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
