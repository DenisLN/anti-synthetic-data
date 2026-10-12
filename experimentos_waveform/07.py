"""Classe 07: NOTCH (entalhe) — forma de onda arbitrária."""

import numpy as np

from mestre import ExperimentoWaveform
from sinais import aplicar_entalhes, aplicar_entalhes_continuos


class Experimento(ExperimentoWaveform):
    id = "07"
    nome = "NOTCH"
    # Parâmetro SORTEADO em gerar(): 3 capturas por padrão na bancada (pedido
    # do dono, 2026-10-07; CHANGELOG/v1.13.md). Não muda o dataset simulado.
    capturas_padrao = 3

    def gerar(self, t, f0, capture_index, rng):
        if getattr(self.config, "sorteio_posicao", True):
            # IEEE 1159-2019, 4.4.5.4: o notching é periódico e contínuo
            # (comutação de conversores). Entalhes em TODOS os ciclos da
            # janela; sem evento localizado, só a fase é sorteada (como 06,
            # 15 e 20) e a grade de ciclos acompanha a fase: os entalhes
            # continuam nos picos da senoide sorteada.
            sorteio = self.sortear(rng, f0)
            voltage = np.sin(2.0 * np.pi * f0 * (t + sorteio.deslocamento_s))
            pulsos = aplicar_entalhes_continuos(
                voltage, t, rng, frequencia_hz=f0, origem_s=-sorteio.deslocamento_s,
            )
            return voltage, {"notch_pulses": float(pulsos), **sorteio.parametros()}
        # Sorteio desligado: 34a0d82 byte a byte (entalhes em 80 ms a partir de 60 ms).
        sorteio = self.sortear(rng, f0, inicio_legado_s=0.060, duracao_legada_s=0.080)
        voltage = np.sin(2.0 * np.pi * f0 * (t + sorteio.deslocamento_s))
        pulsos = aplicar_entalhes(
            voltage, t, rng, frequencia_hz=f0, inicio_s=sorteio.inicio_s, duracao_s=sorteio.duracao_s,
        )
        return voltage, {"notch_pulses": float(pulsos), **sorteio.parametros()}

    def parametros_com_disturbio_reduzido(self, parametros, fracao):
        # Gancho de bancada (limite de bancada, v1.13): forma física =
        # senoide + fracao x (gerar() - senoide). gerar() não muda.
        # Entalhe: o modelo zera a tensão nos pontos; reduzido, desce só
        # "fracao" do valor instantâneo.
        return {"notch_profundidade_pu_bancada": fracao}
