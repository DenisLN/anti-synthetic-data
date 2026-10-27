"""Classe 19: ``_offset_da_captura`` (refatoração de ``configurar``) equivale à fórmula anterior.

A fórmula de referência abaixo é a que ``configurar`` trazia em linha em ``fa82f49``
(``experimentos_nativos/19.py``): mesma semente, mesmo ``valor_para_captura``,
``offset_v = dc_offset * ac_peak_v``. O teste compara o que a fonte recebe.
"""
import dataclasses
import importlib.util
import math
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "logica") not in sys.path:
    sys.path.insert(0, str(ROOT / "logica"))
import mestre
import sinais

_spec = importlib.util.spec_from_file_location("classe19_offset", ROOT / "experimentos_nativos" / "19.py")
_modulo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_modulo)


class _FonteRegistradora:
    def __init__(self):
        self.chamadas = []

    def enable_dc_offset(self, offset_v, *, ac_peak_v):
        self.chamadas.append(("enable_dc_offset", offset_v, ac_peak_v))

    def trigger_step(self, voltage_rms):
        self.chamadas.append(("trigger_step", voltage_rms))


def _bancada(**mudancas):
    config = mestre.Config(
        fs_hz=30_000.0, points=6_000, duration_s=0.2, grid_frequency_hz=60.0,
        base_voltage_rms=127.0, snr_levels_db=(), base_seed=1,
        capture_current=False, current_base_a=None, results_dir=Path("."),
        sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=0.06,
    )
    config = dataclasses.replace(config, **mudancas)
    return type("BancadaFake", (), {"config": config, "fonte": _FonteRegistradora(), "osc": None})()


def _offset_de_referencia(config, capture_index):
    """Fórmula em linha de ``configurar`` em fa82f49."""
    seed = config.base_seed + 19_000_000 + capture_index
    cobertura_ativa = config.capturas_override is not None
    total = config.capturas(False)
    dc_offset = sinais.valor_para_captura(
        np.random.default_rng(seed), 0.02, 0.10, capture_index, total, cobertura_ativa=cobertura_ativa,
    )
    ac_peak_v = config.base_voltage_rms * math.sqrt(2.0)
    return dc_offset, dc_offset * ac_peak_v, ac_peak_v


class OffsetDaCapturaClasse19(unittest.TestCase):
    CONFIGURACOES = (
        {},
        {"base_voltage_rms": 230.0},
        {"base_voltage_rms": 33.0, "base_seed": 7},
        {"capturas_override": 5},
        {"capturas_override": 3, "base_voltage_rms": 220.0},
    )

    def test_configurar_programa_o_offset_da_formula_anterior(self):
        for mudancas in self.CONFIGURACOES:
            bancada = _bancada(**mudancas)
            total = bancada.config.capturas(False)
            for indice in range(total):
                experimento = _modulo.Experimento(bancada)
                bancada.fonte.chamadas.clear()
                retorno = experimento.configurar(indice)
                dc, offset_v, pico_v = _offset_de_referencia(bancada.config, indice)
                msg = (mudancas, indice)
                self.assertEqual(
                    bancada.fonte.chamadas,
                    [("enable_dc_offset", offset_v, pico_v), ("trigger_step", bancada.config.base_voltage_rms)],
                    msg,
                )
                self.assertEqual(retorno, {"dc_offset_pu": dc}, msg)

    def test_exigencias_nativas_usam_o_mesmo_offset(self):
        for mudancas in self.CONFIGURACOES:
            bancada = _bancada(**mudancas)
            for indice in range(bancada.config.capturas(False)):
                experimento = _modulo.Experimento(bancada)
                _, offset_v, _ = _offset_de_referencia(bancada.config, indice)
                self.assertEqual(experimento.exigencias_nativas(indice, {}), {"dc_offset_v": offset_v})


if __name__ == "__main__":
    unittest.main()
