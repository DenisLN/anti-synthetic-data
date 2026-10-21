#!/usr/bin/env python3
"""P09/P12/P31: análise de representação TRACe/LIST inteiramente offline.

Compara gerar() com montar_programacao().programada_pu(), sem instrumentos.
Com ``--sessao <dir>`` (repetível) lê capturas FÍSICAS já gravadas (classes
06/10/11/12/15/16; programada x modelo x medida) e publica as DUAS correlações
(nominal e fundamental ajustada) por captura e por classe/perfil/condição,
ignorando aliases (perfis espelhados) e capturas simuladas. Não escolhe métrica
oficial (decisão do responsável).
Não resolve a perda física de média/offset por ciclo e não aceita correlações
como aprovação automática. Não substitui validação na bancada.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
import platform
import socket
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'logica') not in sys.path:
    sys.path.insert(0, str(ROOT / 'logica'))

import mestre
import perfis
import sessao_io
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
    distancia = sinais.distancia_modelo_programada(modelo, programada, pontos_por_ciclo=n)
    nominal, motivo_nominal = sinais.correlacao_disturbio(
        modelo, programada, fs_hz=fs, f0_hz=frequency_hz, fase_graus=fase_graus,
    )
    ajustada, motivo_ajustada = sinais.correlacao_disturbio_fundamental_ajustada(
        modelo, programada, fs_hz=fs, f0_hz=frequency_hz,
    )
    media_perdida = distancia['media_perdida_por_ciclo_pu']
    escala_v = base_voltage_rms * math.sqrt(2)
    return {
        'fs_hz': fs, 'amostras': int(modelo.size), 'pontos_por_ciclo': n,
        'frequency_hz': float(frequency_hz), 'base_voltage_rms': float(base_voltage_rms),
        'unidade_pu': 'fração do pico nominal base_voltage_rms * sqrt(2)',
        'modelo': _estatisticas(modelo, n, fs, frequency_hz),
        'programada': _estatisticas(programada, n, fs, frequency_hz),
        'erro_rms_pu': distancia['erro_rms_pu'],
        'erro_maximo_pu': distancia['erro_maximo_pu'],
        'erro_rms_v': distancia['erro_rms_pu'] * escala_v,
        'erro_maximo_v': distancia['erro_maximo_pu'] * escala_v,
        'media_perdida_por_ciclo_pu': media_perdida.tolist(),
        'media_perdida_maxima_absoluta_pu': distancia['media_perdida_maxima_absoluta_pu'],
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


# ------------------------------------------------------ sessões físicas (P-31)
TIPO_FISICO = 'correlacao_modelo_programada_medida_sessoes_fisicas'
PARES = (('modelo', 'programada'), ('modelo', 'medida'), ('programada', 'medida'))


def _sha_arquivo(caminho):
    h = hashlib.sha256()
    with Path(caminho).open('rb') as f:
        for bloco in iter(lambda: f.read(1 << 20), b''):
            h.update(bloco)
    return h.hexdigest()


def _duas_correlacoes(esperado, capturado, *, fs_hz, f0_hz, fase_graus):
    """Mesmas funções do modo sintético (sinais.correlacao_disturbio*)."""
    nominal, m_nom = sinais.correlacao_disturbio(
        esperado, capturado, fs_hz=fs_hz, f0_hz=f0_hz, fase_graus=fase_graus)
    ajustada, m_aj = sinais.correlacao_disturbio_fundamental_ajustada(
        esperado, capturado, fs_hz=fs_hz, f0_hz=f0_hz)
    return {'nominal': {'valor': nominal, 'motivo_indefinida': m_nom},
            'fundamental_ajustada': {'valor': ajustada, 'motivo_indefinida': m_aj}}


def _procedencia_codigo():
    try:
        info = mestre.info_do_codigo(recalcular=True)
        return {k: info.get(k) for k in ('git_commit', 'git_sujo', 'versao_codigo', 'arquivos_nao_rastreados')}
    except Exception as exc:  # noqa: BLE001 - procedência ausente vira None
        return {'git_commit': None, 'git_sujo': None, 'versao_codigo': None,
                'arquivos_nao_rastreados': [], 'erro': f'{type(exc).__name__}: {exc}'}


def _resumo(valores):
    validos = [v for v in valores if v is not None]
    if not validos:
        return {'n': 0, 'indefinidas': len(valores), 'media': None, 'minimo': None, 'maximo': None}
    return {'n': len(validos), 'indefinidas': len(valores) - len(validos),
            'media': float(np.mean(validos)), 'minimo': float(np.min(validos)),
            'maximo': float(np.max(validos))}


def analisar_sessoes(pastas, *, classes=CLASSES, perfis=None, frequencias=None):
    """Correlações nominal e fundamental ajustada em capturas físicas já gravadas.

    Só entram capturas com ``simulado is False`` no metadata, que não sejam
    aliases e tenham modelo, programada e medida. A medida é recortada em
    ``[inicio_janela, inicio_janela + pontos)`` sem correção de lag. ``simulado``
    no resultado é False só se toda sessão for modo bancada."""
    if not pastas:
        raise ValueError('informe ao menos uma --sessao')
    if len({Path(p).resolve() for p in pastas}) != len(pastas):
        raise ValueError('--sessao repetida')
    registros, entradas, sessoes = [], [], []
    ignoradas = {'alias': 0, 'simulada_ou_sem_metadata': 0, 'sem_tres_versoes': 0,
                 'classe_fora_do_escopo': 0, 'perfil_fora_do_filtro': 0, 'frequencia_fora_do_filtro': 0,
                 'formas_incompativeis': 0}
    for pasta in map(Path, pastas):
        if not pasta.is_dir():
            raise ValueError(f'{pasta} não é uma pasta')
        arquivos = sorted(p for p in pasta.glob('*.npz') if p.is_file())
        arquivos += sorted((pasta / 'metadata').glob('*.jsonl'))
        if (pasta / 'sessao.json').is_file():
            arquivos.append(pasta / 'sessao.json')
        modo = None
        try:
            modo = json.loads((pasta / 'sessao.json').read_text(encoding='utf-8')).get('modo')
        except (OSError, ValueError, AttributeError):
            pass
        for a in arquivos:
            entradas.append({'sessao': str(pasta), 'arquivo': a.relative_to(pasta).as_posix(),
                             'sha256': _sha_arquivo(a)})
        capturas = sessao_io.ler_capturas(pasta, versoes=('medida', 'modelo', 'programada'))
        usadas = 0
        for c in capturas:
            if c.espelho:
                ignoradas['alias'] += 1
                continue
            if c.classe_id not in classes:
                ignoradas['classe_fora_do_escopo'] += 1
                continue
            if perfis is not None and c.perfil not in perfis:
                ignoradas['perfil_fora_do_filtro'] += 1
                continue
            meta = c.metadado
            if frequencias is not None and (not meta or meta.get('f0_hz') is None
                                            or float(meta['f0_hz']) not in {float(f) for f in frequencias}):
                ignoradas['frequencia_fora_do_filtro'] += 1
                continue
            if not meta or meta.get('simulado') is not False:
                ignoradas['simulada_ou_sem_metadata'] += 1
                continue
            if any(v not in c.versoes for v in ('medida', 'modelo', 'programada')):
                ignoradas['sem_tres_versoes'] += 1
                continue
            n = int(c.versoes['modelo'].size)
            if c.versoes['programada'].size != n:
                ignoradas['formas_incompativeis'] += 1
                continue
            inicio = max(0, min(int(c.inicio_janela or 0), max(0, c.versoes['medida'].size - n)))
            sinais_ = {'modelo': c.versoes['modelo'], 'programada': c.versoes['programada'],
                       'medida': c.versoes['medida'][inicio:inicio + n]}
            fs, f0 = float(meta.get('fs_hz') or AmetekMX30.FS_HZ), float(meta.get('f0_hz') or 60.0)
            fase = float(meta.get('fase_graus') or (meta.get('parametros') or {}).get('fase_graus') or 0.0)
            tensao = meta.get('tensao_base_rms')
            if sinais_['medida'].size != n:
                ignoradas['formas_incompativeis'] += 1
                continue
            registros.append({
                'sessao': str(pasta), 'classe': c.classe_id, 'perfil': c.perfil, 'id_captura': c.id_captura,
                'condicao': f'{float(tensao):g}V_{f0:g}Hz' if tensao is not None else None,
                'f0_hz': f0, 'fs_hz': fs, 'fase_graus': fase, 'inicio_janela': inicio, 'pontos': n,
                'arquivo': c.arquivo.name,
                'pares': {f'{a}_x_{b}': _duas_correlacoes(sinais_[a], sinais_[b], fs_hz=fs, f0_hz=f0, fase_graus=fase)
                          for a, b in PARES}})
            usadas += 1
        sessoes.append({'sessao': str(pasta), 'modo': modo, 'capturas_usadas': usadas})
    grupos = {}
    for r in registros:
        grupos.setdefault((r['classe'], r['perfil'], r['condicao']), []).append(r)
    agregados = []
    for (classe, perfil, condicao), regs in sorted(grupos.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        agregados.append({'classe': classe, 'perfil': perfil, 'condicao': condicao, 'capturas': len(regs),
                          'pares': {par: {m: _resumo([r['pares'][par][m]['valor'] for r in regs])
                                          for m in ('nominal', 'fundamental_ajustada')}
                                    for par in (f'{a}_x_{b}' for a, b in PARES)}})
    fisico = bool(registros) and all(s['modo'] == 'bancada' for s in sessoes)
    codigo = _procedencia_codigo()
    return {'tipo': TIPO_FISICO, 'versao_schema': 1, 'simulado': not fisico,
            'hostname': socket.gethostname(), 'plataforma': platform.platform(),
            'python': platform.python_version(), 'numpy_version': np.__version__,
            'git_commit': codigo.get('git_commit'), 'git_sujo': codigo.get('git_sujo'),
            'procedencia_codigo': codigo, 'classes_escopo': list(classes),
            'filtros': {'perfis': None if perfis is None else list(perfis),
                        'frequencias_hz': None if frequencias is None else [float(f) for f in frequencias]},
            'metrica_oficial': None,
            'sessoes': sessoes, 'arquivos_entrada': entradas, 'ignoradas': ignoradas,
            'registros': registros, 'agregados_por_classe_perfil_condicao': agregados,
            'limitacoes': [
                'Recorte da medida por inicio_janela, sem correção de lag; pares com medida incluem erro de alinhamento.',
                'As duas correlações são publicadas lado a lado; a métrica oficial é decisão do responsável.',
                'Aliases (perfis espelhados) e capturas simuladas são ignorados; um agregado só com n pequeno não é estatística.',
                'Nenhum limiar ou aceite automático é aplicado.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--classes', nargs='+', choices=CLASSES, default=None)
    parser.add_argument('--perfis', nargs='+', choices=perfis.PERFIS, default=None)
    parser.add_argument('--frequencias', nargs='+', type=float, choices=(50., 60.), default=None)
    parser.add_argument('--seeds', nargs='+', type=int, default=(1, 2, 3))
    parser.add_argument('--sessao', type=Path, action='append', default=[],
                        help='sessão física a analisar (repetível); substitui o modo sintético')
    parser.add_argument('--saida', type=Path, required=True, help='JSON novo; não sobrescreve arquivo existente')
    args = parser.parse_args(argv)
    try:
        if args.sessao:
            relatorio = analisar_sessoes(  # filtros só se pedidos explicitamente
                args.sessao, classes=tuple(args.classes or CLASSES),
                perfis=None if args.perfis is None else tuple(args.perfis),
                frequencias=None if args.frequencias is None else tuple(args.frequencias))
            texto = json.dumps(relatorio, ensure_ascii=False, indent=2, allow_nan=False) + '\n'  # antes de abrir: sem arquivo parcial
            with args.saida.open('x', encoding='utf-8') as arquivo:
                arquivo.write(texto)
            print(f'Sessões físicas: {len(relatorio["registros"])} capturas em {args.saida}')
            return 0
        relatorio = gerar_relatorio(classes=args.classes or CLASSES, perfis_selecionados=args.perfis or perfis.PERFIS,
                                    frequencias=args.frequencias or (50., 60.), seeds=args.seeds)
        texto = json.dumps(relatorio, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        with args.saida.open('x', encoding='utf-8') as arquivo:
            arquivo.write(texto)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(f'Simulação offline: {len(relatorio["registros"])} casos em {args.saida}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
