"""Classe 05: HARMONICS — misto: níveis até 20 % via CSINe nativo (clipping
físico), níveis acima do teto de 20 % do CSINe (30 % da literatura)
sintetizados em Python e enviados por TRACe (mesmo mecanismo de
experimentos_waveform, via ``usar_trace``).

``gerar()`` modela o que a bancada faz (v1.15, sorteio ligado): os níveis que
vão por CSINe saem como a senoide CLIPADA no THD pedido (``sinais.
senoide_clipada_pu``, mesmo rms da senoide); só os níveis por TRACe seguem a
soma de harmônicas 3/5/7. Com ``set sorteio off``, soma de harmônicas em todos
os níveis, byte a byte como em 34a0d82.
Na bancada real, 5/10/15/20% usam CSINe nativo; 30% usa program_capture como
os experimentos_waveform. Ainda não testado contra hardware real — validar
no preflight antes do dataset físico completo.
"""

import math

import numpy as np

import perfis
from ametek_orm import AmetekMX30
from mestre import ExperimentoNativo
from sinais import senoide_clipada_pu

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
        if sorteio.ativo and not self.usar_trace(capture_index):
            # Nível dentro do teto do CSINe: a fonte clipa a senoide.
            voltage = senoide_clipada_pu(t, f0, sorteio.deslocamento_s, thd)
            return voltage, {"thd": thd, **sorteio.parametros()}
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

    def rota_programacao(self, capture_index):
        # CSIN = CSINusoid nativa (até 20 %); TRACe = 30 % da literatura.
        return "TRACe" if self.usar_trace(capture_index) else "CSIN"

    def scope_scale_v(self):
        # Headroom generoso: a soma de harmônicas em 30% THD tem crista um
        # pouco maior que a senoide limpa; escala pra caber com folga.
        return self.config.base_voltage_rms * math.sqrt(2.0) * 1.5
