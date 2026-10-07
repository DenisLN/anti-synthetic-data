"""Relatório OFFLINE (sem hardware) do que cabe na bancada a uma tensão base.

Para cada classe e cada captura do plano (com os padrões de capturas da
classe, ``--capturas`` como ``set capturas`` e ``--seed`` como ``set seed``),
mostra: rms e pico programados, extremo físico previsto, teto, se cabe e por
quê, a fração do distúrbio aplicada pelo limite de bancada (v1.13) e a tela
do CH1 do Keysight contra o extremo previsto. Usa exatamente o código da
pré-validação (``ExperimentoBase.avaliar_captura_na_bancada``) — nada aqui é
uma segunda implementação.

Limites iguais aos que ``scripts/start_bench_windows.ps1`` fixa: 300 Vrms
(``EUT_MAX_VOLTAGE_RMS``) e 415,8 Vp (``EUT_MAX_PEAK_V`` = 98% de 300·√2).

Uso (na raiz do projeto):
    env\\Scripts\\python scripts\\relatorio_limites_bancada.py --tensao 127 --tensao 220
    env/bin/python scripts/relatorio_limites_bancada.py --tensao 220 --capturas 3 --seed 1
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "logica"))

import mestre  # noqa: E402
from ametek_orm import AmetekMX30  # noqa: E402

RANGE_RMS = 300.0
TETO_PICO_V = round(RANGE_RMS * math.sqrt(2.0) * 0.98, 1)


class _OscOffline:
    """Basta não ser ``None``: as classes tratam a captura como de BANCADA
    (cobertura/caracterização com ``--capturas``, limite de bancada)."""


def _config(tensao: float, frequencia: float, capturas: Optional[int], seed: int) -> mestre.Config:
    return mestre.Config(
        fs_hz=mestre.FS_HZ, points=mestre.POINTS, duration_s=mestre.DURATION_S,
        grid_frequency_hz=frequencia, base_voltage_rms=tensao, snr_levels_db=(),
        base_seed=seed, capture_current=False, current_base_a=None,
        results_dir=PROJECT_ROOT / "resultados", sim_captures_per_class=1,
        real_captures_per_class=1, disturbance_start_s=mestre.DISTURBANCE_START_S,
        capturas_override=capturas,
    )


def _tela_ch1_v(experimento, info: Dict[str, object]) -> float:
    """Meia excursão da tela do CH1 (4 divisões) que a captura terá.
    ``set_vertical_scale(pico)`` põe ``pico`` em 3 divisões."""
    nominal_v = experimento.config.base_voltage_rms * math.sqrt(2.0)
    if isinstance(experimento, mestre.ExperimentoWaveform):
        pico = float(info["pico_programado_v"])
        excursao = experimento.excursao_fisica_prevista_v()
        if excursao is not None:
            pico = max(pico, float(excursao))
        headroom = 1.60 if pico > 3.0 * nominal_v else 1.25
        pedido = max(pico * headroom, float(info["extremo_previsto_v"]), experimento.config.base_voltage_rms * 0.1)
        return 4.0 / 3.0 * pedido
    escala = experimento.scope_scale_v()
    if escala is not None:
        return 4.0 / 3.0 * float(escala)
    # Nativas sem escala própria herdam a de Bancada.from_env (EUT_MAX_PEAK_V/3
    # por divisão) — ou a da classe waveform anterior no run all.
    return 4.0 * TETO_PICO_V / 3.0


def _resumo_parametros(info: Dict[str, object]) -> str:
    parametros = info.get("parametros") or {}
    bancada = {k: v for k, v in parametros.items() if k.endswith("_bancada") and k != "fator_disturbio_bancada"}
    if not bancada:
        return ""
    return ", ".join(f"{k}={v:.3g}" for k, v in bancada.items())


def relatorio(tensao: float, *, frequencia: float, capturas: Optional[int], seed: int) -> List[str]:
    config = _config(tensao, frequencia, capturas, seed)
    fonte = AmetekMX30(simulated=True, max_voltage_rms=RANGE_RMS, max_peak_v=TETO_PICO_V)
    linhas = [
        f"### {tensao:g} Vrms / {frequencia:g} Hz — teto {TETO_PICO_V} Vp, {RANGE_RMS:g} Vrms; "
        f"set capturas: {capturas if capturas is not None else 'não'}; seed base {seed}; "
        f"limite de bancada: {'ligado' if mestre.LIMITE_BANCADA_DISTURBIO else 'DESLIGADO'} "
        f"(fração mínima {mestre.LIMITE_BANCADA_FRACAO_MINIMA:.2f})",
        "",
        "| Classe | Captura (nível) | Vrms prog. | Pico prog. (V) | Extremo prev. (V) | Teto (V) "
        "| Distúrbio aplicado | Tela CH1 (±V) | Cabe? | Motivo / parâmetros de bancada |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    resumo = []
    for script_path in mestre._experiment_scripts():
        experimento_cls = mestre.Bancada._carregar_classe_experimento(script_path)
        experimento = experimento_cls(mestre.Bancada(fonte, _OscOffline(), config))
        plano = experimento.plano_de_capturas(False)
        puladas = reduzidas = 0
        for indice_global, capture_index in plano:
            info = experimento.avaliar_captura_na_bancada(indice_global, capture_index)
            rms = info.get("rms_programado_v")
            pico = info.get("pico_programado_v")
            extremo = info.get("extremo_previsto_v")
            fracao = info.get("fator_disturbio_bancada")
            if fracao is not None:
                reduzidas += 1
            if not info["cabe"]:
                puladas += 1
            tela = _tela_ch1_v(experimento, info) if info["cabe"] else None
            tela_txt = "—" if tela is None else (
                f"{tela:.0f}" + ("" if tela >= 1.05 * float(extremo) else " **CLIPA**")
            )
            detalhe = str(info.get("motivo", "")) if not info["cabe"] else _resumo_parametros(info)
            linhas.append(
                f"| {experimento.id} {experimento.nome} | {indice_global + 1} ({capture_index}) "
                f"| {'—' if rms is None else f'{rms:.1f}'} "
                f"| {'—' if pico is None else f'{pico:.1f}'} "
                f"| {'—' if extremo is None else f'{extremo:.1f}'} "
                f"| {float(info['teto_extremo_v']):.1f} "
                f"| {'100%' if fracao is None else f'{100.0 * fracao:.0f}%'} "
                f"| {tela_txt} | {'sim' if info['cabe'] else 'NÃO'} | {detalhe} |"
            )
        resumo.append(
            f"{experimento.id}: {len(plano) - puladas}/{len(plano)} rodam"
            + (f", {reduzidas} com distúrbio reduzido" if reduzidas else "")
            + (f", {puladas} PULADA(S)" if puladas else "")
        )
    linhas += ["", "Resumo: " + "; ".join(resumo), ""]
    return linhas


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tensao", type=float, action="append", required=True, help="tensão base L-N (Vrms); repetível")
    parser.add_argument("--frequencia", type=float, default=60.0)
    parser.add_argument("--capturas", type=int, default=None, help="como 'set capturas N' (padrão: só o padrão das classes)")
    parser.add_argument("--seed", type=int, default=mestre.BASE_SEED_PADRAO, help="como 'set seed N'")
    args = parser.parse_args(argv)
    logging.getLogger("MestreExperimentos").setLevel(logging.ERROR)
    for tensao in args.tensao:
        if tensao * math.sqrt(2.0) > TETO_PICO_V:
            print(
                f"### {tensao:g} Vrms — RECUSADA: pico nominal {tensao * math.sqrt(2.0):.0f} V passa do "
                f"teto de {TETO_PICO_V} Vp da MX30 por fase (300 Vrms/425 Vp, manual §4.14 p. 84). "
                "380 V de linha (sistema 220/380 V) = 219,4 V por fase: rode com --tensao 220.\n"
            )
            continue
        print("\n".join(relatorio(tensao, frequencia=args.frequencia, capturas=args.capturas, seed=args.seed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
