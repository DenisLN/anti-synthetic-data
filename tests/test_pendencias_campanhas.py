"""Planejamento das cinco condições sem qualquer operação de instrumento."""
import json
import unittest
from unittest import mock

from scripts import planejar_campanhas as campanhas


class CampanhasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with mock.patch.object(campanhas.referencia.AmetekMX30, 'connect', side_effect=AssertionError('IO proibido')), \
             mock.patch.object(campanhas.referencia.AmetekMX30, 'write', side_effect=AssertionError('IO proibido')), \
             mock.patch.object(campanhas.referencia.AmetekMX30, 'query', side_effect=AssertionError('IO proibido')):
            cls.relatorio = campanhas.planejar(perfis_selecionados=campanhas.perfis.PERFIS, seed=1)

    def test_cinco_condicoes_exatas_todas_classes_e_perfis(self):
        condicoes = self.relatorio['condicoes']
        self.assertEqual([(c['tensao_rms'], c['frequencia_hz']) for c in condicoes], list(campanhas.CONDICOES))
        for condicao in condicoes:
            self.assertEqual(len(condicao['preflight']), 60)
            self.assertEqual({r['classe'] for r in condicao['preflight']}, {f'{c:02d}' for c in range(1, 21)})
            self.assertEqual({r['perfil'] for r in condicao['preflight']}, set(campanhas.perfis.PERFIS))
            for registro in condicao['preflight']:
                self.assertEqual(registro['planejadas'], registro['viaveis'] + registro['recusadas'])
                self.assertEqual(registro['recusadas'], len(registro['motivos_recusas']))
                self.assertEqual(registro['reduzidas'], len(registro['reducoes']))
        json.dumps(self.relatorio, allow_nan=False)

    def test_calibracao_vem_do_arquivo_e_limites_preservados(self):
        dados = campanhas.mestre.carregar_calibracao_extremos()
        for condicao in self.relatorio['condicoes']:
            chave = campanhas.mestre.condicao_calibrada(dados, condicao['tensao_rms'], condicao['frequencia_hz'])
            self.assertEqual(condicao['chave_calibracao'], chave)
            self.assertEqual(condicao['calibracao_disponivel'], chave is not None)
        self.assertEqual(self.relatorio['limites']['max_voltage_rms'], 300)
        self.assertEqual(self.relatorio['limites']['max_peak_v'], 415.8)

    def test_recusas_reais_sao_reportadas_sem_aprovacao_ficticia(self):
        for rotulo in ('220V_60Hz', '230V_50Hz'):
            condicao = next(c for c in self.relatorio['condicoes'] if c['condicao'] == rotulo)
            recusadas = [r for r in condicao['preflight'] if r['recusadas']]
            self.assertTrue(recusadas, rotulo)
            self.assertTrue(all(r['motivos_recusas'] for r in recusadas))
            self.assertTrue(any('recusadas' in p for p in condicao['pendencias']))
        self.assertTrue(all('Nenhuma sessão física' in c['pendencias'][0] for c in self.relatorio['condicoes']))

    def test_orcamento_e_espelhos_nao_triplicam_classes_independentes(self):
        for condicao in self.relatorio['condicoes']:
            plano = condicao['planejamento_grupos']
            for grupo in plano['grupos']:
                self.assertLessEqual(grupo['escritas_trace_teto'], 216)
                self.assertEqual(grupo['escritas_trace_teto'], sum(b['escritas_trace_teto'] for b in grupo['blocos']))
            blocos = [b for g in plano['grupos'] for b in g['blocos']] + plano['blocos_excedentes_nao_agendados']
            normal = [b for b in blocos if b['classe'] == '01']
            self.assertEqual(len(normal), 1)
            self.assertEqual(set(normal[0]['perfis_espelho']), {'norma', 'fronteira'})

    def test_classe_isolada_acima_orcamento_fica_bloqueada(self):
        itens = [{'classe': '06', 'escritas_trace_teto': 200},
                 {'classe': '07', 'escritas_trace_teto': 240},
                 {'classe': '08', 'escritas_trace_teto': 40}]
        plano = campanhas.agrupar_comandos(itens)
        self.assertEqual([g['escritas_trace_teto'] for g in plano['grupos']], [200, 40])
        self.assertEqual(plano['blocos_excedentes_nao_agendados'][0]['classe'], '07')
        self.assertIn('divisão explícita', plano['blocos_excedentes_nao_agendados'][0]['motivo'])


if __name__ == '__main__':
    unittest.main()
