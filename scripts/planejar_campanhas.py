#!/usr/bin/env python3
"""Preflight offline das cinco campanhas: não programa nem mede instrumentos.

Grupos respeitam orçamento operacional de 216 escritas TRACe por conexão.
É um planejamento, não autorização de saída nem evidência de sessão física.
Recusas e ausência de calibração permanecem pendências explícitas.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import relatorio_limites_bancada as referencia

mestre = referencia.mestre
perfis = referencia.perfis
CONDICOES = ((127., 60.), (127., 50.), (230., 50.), (220., 60.), (33., 60.))
ORCAMENTO_TRACE = mestre.LIMITE_ESCRITAS_TRACE_CONEXAO


def agrupar_comandos(itens, orcamento=ORCAMENTO_TRACE):
    """Empacota blocos classe/perfil sem dividi-los; bloqueia excedentes isolados."""
    grupos, excedentes = [], []
    atual = {'escritas_trace_teto': 0, 'blocos': []}
    for item in itens:
        custo = item['escritas_trace_teto']
        if custo > orcamento:
            excedentes.append(dict(item, motivo='Classe/perfil isolado excede orçamento; requer divisão explícita das capturas antes de execução'))
            continue
        if atual['blocos'] and atual['escritas_trace_teto'] + custo > orcamento:
            grupos.append(atual)
            atual = {'escritas_trace_teto': 0, 'blocos': []}
        atual['blocos'].append(item)
        atual['escritas_trace_teto'] += custo
    if atual['blocos']:
        grupos.append(atual)
    return {'orcamento_trace_por_conexao': orcamento, 'grupos': grupos,
            'blocos_excedentes_nao_agendados': excedentes,
            'politica': 'Conexão nova por grupo, sem execução automática; escritas são teto anterior à poda; não inclui diagnósticos ou reprogramações extras.'}


def planejar(*, perfis_selecionados=('literatura',), capturas=None, seed=mestre.BASE_SEED_PADRAO):
    if not perfis_selecionados or any(p not in perfis.PERFIS for p in perfis_selecionados):
        raise ValueError('Perfis inválidos')
    if capturas is not None and (isinstance(capturas, bool) or capturas < 1):
        raise ValueError('Capturas deve ser inteiro positivo')
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError('Seed deve ser inteiro não negativo')
    calibracao = mestre.carregar_calibracao_extremos()
    scripts = mestre._experiment_scripts()
    condicoes = []
    for tensao, frequencia in CONDICOES:
        chave_cal = mestre.condicao_calibrada(calibracao, tensao, frequencia)
        registros, blocos = [], []
        for script in scripts:
            tipo = mestre.Bancada._carregar_classe_experimento(script)
            for perfil in perfis_selecionados:
                cfg = referencia._config(tensao, frequencia, capturas, seed, perfil)
                fonte = referencia.AmetekMX30(simulated=True,
                                             max_voltage_rms=referencia.RANGE_RMS,
                                             max_peak_v=referencia.TETO_PICO_V)
                experimento = tipo(mestre.Bancada(fonte, referencia._OscOffline(), cfg))
                plano = experimento.plano_de_capturas(False)
                avaliacoes = [experimento.avaliar_captura_na_bancada(i, j) for i, j in plano]
                recusas = [{'indice_global': info['indice_global'],
                            'capture_index': info['capture_index'],
                            'motivo': info.get('motivo', 'Sem motivo fornecido pelo preflight')}
                           for info in avaliacoes if not info['cabe']]
                reduzidas = [{'indice_global': info['indice_global'],
                              'fracao': info['fator_disturbio_bancada'], 'viavel': bool(info['cabe'])}
                             for info in avaliacoes if info.get('fator_disturbio_bancada', 1.) < 1.]
                estimativa = mestre.capturas_efetivas_da_classe(tipo, cfg)
                registros.append({
                    'classe': experimento.id, 'nome': experimento.nome, 'perfil': perfil,
                    'planejadas': len(plano), 'viaveis': len(plano) - len(recusas),
                    'recusadas': len(recusas), 'reduzidas': len(reduzidas),
                    'motivos_recusas': recusas, 'reducoes': reduzidas,
                    'calibracao_disponivel': chave_cal is not None,
                    'classe_medida_nesta_condicao': chave_cal is not None and
                        experimento.id in calibracao[chave_cal]['fatores'],
                    'estimativa_capturas_efetivas': estimativa,
                })
            # Perfis independentes são capturados uma vez e espelhados: mesma
            # decisão de plano_de_perfis usada pela CLI, sem triplicar custo.
            for perfil, espelhos in perfis.plano_de_perfis(tipo.id, perfis_selecionados,
                                                          sorteio_posicao=cfg.sorteio_posicao):
                config_bloco = referencia._config(tensao, frequencia, capturas, seed, perfil)
                estimativa = mestre.capturas_efetivas_da_classe(tipo, config_bloco)
                blocos.append({'classe': tipo.id, 'perfil': perfil, 'perfis_espelho': list(espelhos),
                               'capturas_planejadas': estimativa['total'],
                               'escritas_trace_teto': estimativa['escritas_trace'],
                               'comandos_propostos': [f'set perfil {perfil}', f'run {tipo.id}'],
                               'observacao_espelhos': 'Espelhos dependem do modo perfil todos da CLI; comandos individuais indicados são apenas referência de planejamento.'})
        condicoes.append({
            'condicao': mestre.chave_condicao(tensao, frequencia),
            'tensao_rms': tensao, 'frequencia_hz': frequencia,
            'calibracao_disponivel': chave_cal is not None,
            'chave_calibracao': chave_cal, 'preflight': registros,
            'planejamento_grupos': agrupar_comandos(blocos),
            'pendencias': ['Nenhuma sessão física executada por este relatório.'] +
                ([f"{sum(r['recusadas'] for r in registros)} capturas recusadas pelo preflight; não podem ser declaradas concluídas."]
                 if any(r['recusadas'] for r in registros) else []) +
                ([] if chave_cal else ['Sem calibração medida nesta condição; previsão conservadora do projeto permanece.']),
        })
    caminho_cal = Path(mestre.CALIBRACAO_EXTREMOS_PATH)
    return {
        'tipo': 'planejamento_offline_campanhas', 'versao_schema': 1,
        'limites': {'max_voltage_rms': referencia.RANGE_RMS, 'max_peak_v': referencia.TETO_PICO_V,
                    'limite_bancada_disturbio': mestre.LIMITE_BANCADA_DISTURBIO,
                    'fracao_minima_disturbio': mestre.LIMITE_BANCADA_FRACAO_MINIMA},
        'seed': seed, 'capturas_override': capturas, 'perfis': list(perfis_selecionados),
        'calibracao': {'arquivo': str(caminho_cal),
                       'sha256': hashlib.sha256(caminho_cal.read_bytes()).hexdigest(),
                       'condicoes_medidas': list(calibracao)},
        'limitacoes': ['Nenhum instrumento conectado, nenhuma saída autorizada, nenhuma medição realizada.',
                       'Viabilidade offline não confirma correlação, offset, trigger ou amplitude física.',
                       'Orçamento de 216 escritas é margem operacional, não limite validado do fabricante.',
                       'Não recalibra, não altera fatores/limites, gerar() ou decisões do preflight.',
                       'Grupos exigem revisão e reconexão; comandos não são executados.'],
        'condicoes': condicoes,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--perfis', nargs='+', choices=(*perfis.PERFIS, 'todos'), default=['literatura'])
    parser.add_argument('--capturas', type=int)
    parser.add_argument('--seed', type=int, default=mestre.BASE_SEED_PADRAO)
    parser.add_argument('--saida', type=Path, required=True, help='JSON novo; não sobrescreve existente')
    args = parser.parse_args(argv)
    selecionados = perfis.PERFIS if 'todos' in args.perfis else tuple(dict.fromkeys(args.perfis))
    try:
        relatorio = planejar(perfis_selecionados=selecionados, capturas=args.capturas, seed=args.seed)
        with args.saida.open('x', encoding='utf-8') as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(f'Planejamento offline de cinco condições salvo em {args.saida}; nenhuma sessão física executada.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
