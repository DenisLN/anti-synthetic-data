"""Classe 05: HARMONICS — misto: 4 níveis via CSINe nativo (clipping físico),
1 nível (30%, acima do teto de 20% do CSINe) sintetizado em Python e enviado
por TRACe (mesmo mecanismo de experimentos_waveform, via ``usar_trace``).

O dataset sintético (modo simulado) usa sempre a fórmula exata dos 5 níveis
do perfil ativo (``perfis.py``).
Na bancada real, 5/10/15/20% usam CSINe nativo; 30% usa program_capture como
os experimentos_waveform. Ainda não testado contra hardware real — validar
no preflight antes do dataset físico completo.
"""

import math

import numpy as np

import perfis
from ametek_orm import AmetekMX30
from mestre import ExperimentoNativo

TETO_CSINE = AmetekMX30.MAX_CSINE_THD_PCT / 100.0


class Experimento(ExperimentoNativo):
    id = "05"
    nome = "HARMONICS"

    @property
    def NIVEIS_THD(self):
        # Níveis do perfil ativo (logica/perfis.py); literatura = 5/10/15/20/30 %,
        # norma = até 20 % (teto do CSINe).
        return perfis.faixa(self.config, "thd_niveis")

    def total_niveis(self) -> int:
        return len(self.NIVEIS_THD)

    def gerar(self, t, f0, capture_index, rng):
        thd = self.NIVEIS_THD[capture_index % len(self.NIVEIS_THD)]
        # A soma quadrática dos coeficientes é exatamente o THD solicitado.
        ratios = np.array([0.60, 0.30, 0.10], dtype=np.float64)
        coeficientes = thd * ratios / np.linalg.norm(ratios)
        w = 2.0 * np.pi * f0
        sorteio = self.sortear(rng, f0)
        tt = t + sorteio.deslocamento_s
        voltage = (
            np.sin(w * tt)
            + coeficientes[0] * np.sin(3.0 * w * tt)
            + coeficientes[1] * np.sin(5.0 * w * tt)
            + coeficientes[2] * np.sin(7.0 * w * tt)
        )
        return voltage, {"thd": thd, **sorteio.parametros()}

    def configurar(self, capture_index):
        # Só é chamado para os 4 níveis dentro do teto do CSINe — usar_trace()
        # já desvia o nível de 30% para o caminho TRACe antes de chegar aqui.
        thd = self.NIVEIS_THD[capture_index % len(self.NIVEIS_THD)]
        self.fonte.configure_harmonics_csine(thd * 100.0)
        self.fonte.trigger_step(self.config.base_voltage_rms)
        return {"thd": thd}

    def usar_trace(self, capture_index):
        return self.NIVEIS_THD[capture_index % len(self.NIVEIS_THD)] > TETO_CSINE

    def scope_scale_v(self):
        # Headroom generoso: a soma de harmônicas em 30% THD tem crista um
        # pouco maior que a senoide limpa; escala pra caber com folga.
        return self.config.base_voltage_rms * math.sqrt(2.0) * 1.5
