"""Recalcula os fatores de extremo (``logica/calibracao_extremos.json``) a
partir do metadata de sessões de bancada — OFFLINE, sem hardware.

Fator de uma captura = max(|pico_medido_v|, |vale_medido_v|) (VMAX/VMIN do
Keysight na taxa cheia) ÷ pico PROGRAMADO, com a MESMA definição de
``ExperimentoBase.pico_programado_v`` (máximo |forma prevista| × pico
nominal, ou rms programado × √2 se maior). Sessões a partir da v1.13 gravam
``pico_programado_v`` no metadata; nas anteriores ele é reconstruído pelo
próprio código da classe com a ``seed`` e o ``nivel_indice`` gravados.

Fora do cálculo (e contadas no relatório):
- a 08 (modelo próprio do impulso, ``SOBRESSINAL/SUBSINAL_DO_DEGRAU``);
- capturas com o distúrbio reduzido pelo limite de bancada
  (``fator_disturbio_bancada``): o fator é definido com o distúrbio inteiro;
- capturas sem VMAX/VMIN (``extremos_indisponiveis``) ou simuladas.

Fator proposto por classe = o MAIOR medido nas sessões dadas. Sem
``--gravar`` só imprime. Com ``--gravar``, nenhum fator DIMINUI (vale o
maior entre o atual e o medido: baixar um fator enfraquece a pré-validação)
— a não ser com ``--substituir``, decisão explícita do dono.

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
from typing import Dict, List, Optional, Tuple

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


def coletar(sessoes: List[Path]) -> Tuple[Dict[str, List[float]], Dict[str, int]]:
    scripts = _scripts_por_id()
    fatores: Dict[str, List[float]] = {}
    ignoradas = {"08 (modelo próprio)": 0, "distúrbio reduzido": 0, "sem VMAX/VMIN": 0, "simulada": 0}
    # Reconstrução sempre com o distúrbio inteiro (definição do fator).
    limite_original = mestre.LIMITE_BANCADA_DISTURBIO
    mestre.LIMITE_BANCADA_DISTURBIO = False
    try:
        for sessao in sessoes:
            # resultados/sessao_*/metadata/*.jsonl, ou os .jsonl soltos (como em
            # docs/analise-2026-09-30/dados/).
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
                    if "fator_disturbio_bancada" in (registro.get("parametros") or {}):
                        ignoradas["distúrbio reduzido"] += 1
                        continue
                    if "pico_medido_v" not in registro or "vale_medido_v" not in registro:
                        ignoradas["sem VMAX/VMIN"] += 1
                        continue
                    pico = registro.get("pico_programado_v")
                    if pico is None:
                        pico = pico_programado_reconstruido_v(registro, scripts[classe_id])
                    extremo = max(abs(float(registro["pico_medido_v"])), abs(float(registro["vale_medido_v"])))
                    fatores.setdefault(classe_id, []).append(extremo / float(pico))
    finally:
        mestre.LIMITE_BANCADA_DISTURBIO = limite_original
    return fatores, ignoradas


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

    dados = json.loads(args.arquivo.read_text(encoding="utf-8"))
    atuais = {str(k).zfill(2): float(v) for k, v in dados["fatores"].items()}
    medidos, ignoradas = coletar(args.sessoes)

    print("| Classe | Capturas | Fator mín. | Mediana | Máx. (proposto) | Atual | Gravaria |")
    print("|---|---|---|---|---|---|---|")
    novos = dict(atuais)
    for classe_id in sorted(set(atuais) | set(medidos)):
        valores = medidos.get(classe_id, [])
        atual = atuais.get(classe_id)
        if not valores:
            print(f"| {classe_id} | 0 | — | — | — | {atual if atual is not None else '—'} | {atual} (sem dado) |")
            continue
        proposto = round(max(valores), 3)
        gravaria = proposto if (args.substituir or atual is None) else max(proposto, atual)
        novos[classe_id] = gravaria
        print(
            f"| {classe_id} | {len(valores)} | {min(valores):.3f} | {statistics.median(valores):.3f} "
            f"| {proposto:.3f} | {'—' if atual is None else f'{atual:.3f}'} | {gravaria:.3f} |"
        )
    print()
    print("Ignoradas: " + ", ".join(f"{motivo}: {n}" for motivo, n in ignoradas.items()))
    if any(not math.isfinite(v) or v <= 0 for v in novos.values()):
        raise SystemExit("Fator inválido calculado — nada gravado.")
    if args.gravar:
        dados["fatores"] = {k: novos[k] for k in sorted(novos)}
        dados["origem"] = (
            "scripts/recalibrar_extremos.py sobre: " + ", ".join(str(s) for s in args.sessoes)
            + (" (substituindo)" if args.substituir else " (nenhum fator diminuiu)")
            + f"; antes: {dados.get('origem', '')}"
        )
        args.arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Gravado em {args.arquivo}. Confira com 'git diff' e rode tests/test_offline.py.")
    else:
        print("Nada gravado (use --gravar).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
