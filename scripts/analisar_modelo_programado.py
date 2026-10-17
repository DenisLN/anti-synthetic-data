#!/usr/bin/env python3
"""P09/P12/P31: análise de representação TRACe/LIST inteiramente offline.

Compara gerar() com montar_programacao().programada_pu(), sem instrumentos.
Não resolve a perda física de média/offset por ciclo e não aceita correlações
como aprovação automática. Não substitui validação na bancada.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'logica') not in sys.path:
    sys.path.insert(0, str(ROOT / 'logica'))

import mestre
import perfis
import sinais
from ametek_orm import AmetekMX30

CLASSES = ('06', '10', '11', '12', '15', '16')
LIMITACOES = [
    'Simulação offline da representação TRACe/LIST; não é validação de bancada.',
    'Sem calibração, readback, hardware, ruído, redução de distúrbio ou captura medida.',
    'A perda de média por ciclo é quantificada; nenhum offset físico é corrigido.',
    'As duas correlações são diagnósticas; nenhum limiar ou aceite automático é aplicado.',
    'Envelope por ciclo usa RMS e ajuste fundamental local; não é envelope instantâneo nem THD.',
]


def _estatisticas(forma, pontos_por_ciclo, fs_hz, f0_hz):
    ciclos = forma.reshape(-1, pontos_por_ciclo)
    t = np.arange(forma.size) / fs_hz
    base = np.column_stack((np.sin(2 * np.pi * f0_hz * t),
                            np.cos(2 * np.pi * f0_hz * t), np.ones_like(t)))
    amplitudes = []
    for indice, ciclo in enumerate(ciclos):
        janela = base[indice * pontos_por_ciclo:(indice + 1) * pontos_por_ciclo]
        coef, *_ = np.linalg.lstsq(janela, ciclo, rcond=None)
        amplitudes.append(float(np.hypot(coef[0], coef[1])))
    return {
        'rms_pu': float(np.sqrt(np.mean(forma ** 2))),
        'pico_absoluto_pu': float(np.max(np.abs(forma))),
        'media_por_ciclo_pu': np.mean(ciclos, axis=1).tolist(),
        'rms_por_ciclo_pu': np.sqrt(np.mean(ciclos ** 2, axis=1)).tolist(),
        'pico_por_ciclo_pu': np.max(np.abs(ciclos), axis=1).tolist(),
        'envelope_fundamental_ajustada_por_ciclo_pu': amplitudes,
    }


def analisar_forma(modelo, *, frequency_hz, base_voltage_rms=127., fase_graus=0.):
    """Função pura: unidades pu do pico nominal, volts = pu * base * sqrt(2)."""
    modelo = np.asarray(modelo, dtype=np.float64)
    plano = AmetekMX30.montar_programacao(
        modelo, base_voltage_rms=base_voltage_rms, frequency_hz=frequency_hz,
    )
    programada = plano.programada_pu()
    fs = AmetekMX30.FS_HZ
    n = plano.pontos_por_ciclo
    erro = programada - modelo
    nominal, motivo_nominal = sinais.correlacao_disturbio(
        modelo, programada, fs_hz=fs, f0_hz=frequency_hz, fase_graus=fase_graus,
    )
    ajustada, motivo_ajustada = sinais.correlacao_disturbio_fundamental_ajustada(
        modelo, programada, fs_hz=fs, f0_hz=frequency_hz,
    )
    media_perdida = np.mean(modelo.reshape(-1, n), axis=1) - np.mean(programada.reshape(-1, n), axis=1)
    escala_v = base_voltage_rms * math.sqrt(2)
    return {
        'fs_hz': fs, 'amostras': int(modelo.size), 'pontos_por_ciclo': n,
        'frequency_hz': float(frequency_hz), 'base_voltage_rms': float(base_voltage_rms),
        'unidade_pu': 'fração do pico nominal base_voltage_rms * sqrt(2)',
        'modelo': _estatisticas(modelo, n, fs, frequency_hz),
        'programada': _estatisticas(programada, n, fs, frequency_hz),
        'erro_rms_pu': float(np.sqrt(np.mean(erro ** 2))),
        'erro_maximo_pu': float(np.max(np.abs(erro))),
        'erro_rms_v': float(np.sqrt(np.mean(erro ** 2))) * escala_v,
        'erro_maximo_v': float(np.max(np.abs(erro))) * escala_v,
        'media_perdida_por_ciclo_pu': media_perdida.tolist(),
        'media_perdida_maxima_absoluta_pu': float(np.max(np.abs(media_perdida))),
        'pico_reconstruido_conservador_v': plano.pico_reconstruido_v,
        'correlacao_disturbio_nominal': {'valor': nominal, 'motivo_indefinida': motivo_nominal},
        'correlacao_disturbio_fundamental_ajustada': {'valor': ajustada, 'motivo_indefinida': motivo_ajustada},
    }


def gerar_relatorio(*, classes=CLASSES, perfis_selecionados=perfis.PERFIS,
                    frequencias=(50., 60.), seeds=(1, 2, 3)):
    """gera() usa rng(seed) próprio por combinação; seed não depende da ordem."""
    if not classes or any(c not in CLASSES for c in classes):
        raise ValueError('Classes permitidas: ' + ', '.join(CLASSES))
    if not perfis_selecionados or any(p not in perfis.PERFIS for p in perfis_selecionados):
        raise ValueError('Perfil inválido')
    if not frequencias or any(f not in (50., 60.) for f in frequencias):
        raise ValueError('Frequências permitidas: 50 e 60 Hz')
    if not seeds or any(not isinstance(s, int) or s < 0 for s in seeds):
        raise ValueError('Seeds devem ser inteiros não negativos')
    config = mestre.Config(
        fs_hz=30000., points=6000, duration_s=.2, grid_frequency_hz=60.,
        base_voltage_rms=127., snr_levels_db=(), base_seed=1,
        capture_current=False, current_base_a=None, results_dir=Path('.'),
        sim_captures_per_class=1, real_captures_per_class=1, disturbance_start_s=.06,
        sorteio_posicao=True,
    )
    registros = []
    for classe in classes:
        tipo = mestre.Bancada._carregar_classe_experimento(ROOT / 'experimentos_waveform' / f'{classe}.py')
        for perfil in perfis_selecionados:
            for f0 in frequencias:
                for seed in seeds:
                    cfg = replace(config, perfil=perfil, grid_frequency_hz=float(f0), base_seed=seed)
                    # Bancada é apenas um portador de config, sem fonte ou osc.
                    experimento = tipo(mestre.Bancada(None, None, cfg))
                    t = np.arange(cfg.points) / cfg.fs_hz
                    forma, parametros = experimento.gerar(t, f0, 0, np.random.default_rng(seed))
                    registro = analisar_forma(forma, frequency_hz=f0,
                                              base_voltage_rms=cfg.base_voltage_rms,
                                              fase_graus=parametros.get('fase_graus', 0.))
                    registro.update(classe=classe, nome=experimento.nome, perfil=perfil,
                                    seed=seed, capture_index=0, parametros_modelo=parametros)
                    registros.append(registro)
    return {'tipo': 'simulacao_offline_modelo_vs_programada', 'versao_schema': 1,
            'numpy_version': np.__version__,
            'rng': 'numpy.random.default_rng(seed), reiniciado por combinação; capture_index=0',
            'limitacoes': LIMITACOES, 'registros': registros}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--classes', nargs='+', choices=CLASSES, default=CLASSES)
    parser.add_argument('--perfis', nargs='+', choices=perfis.PERFIS, default=perfis.PERFIS)
    parser.add_argument('--frequencias', nargs='+', type=float, choices=(50., 60.), default=(50., 60.))
    parser.add_argument('--seeds', nargs='+', type=int, default=(1, 2, 3))
    parser.add_argument('--saida', type=Path, required=True, help='JSON novo; não sobrescreve arquivo existente')
    args = parser.parse_args(argv)
    try:
        relatorio = gerar_relatorio(classes=args.classes, perfis_selecionados=args.perfis,
                                    frequencias=args.frequencias, seeds=args.seeds)
        with args.saida.open('x', encoding='utf-8') as arquivo:
            json.dump(relatorio, arquivo, ensure_ascii=False, indent=2, allow_nan=False)
            arquivo.write('\n')
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(f'Simulação offline: {len(relatorio["registros"])} casos em {args.saida}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
