"""Classe 06: FLICKER — modulação de amplitude contínua, forma de onda arbitrária."""

import numpy as np

import perfis
import sinais
from ametek_orm import AmetekMX30
from mestre import ExperimentoWaveform


class Experimento(ExperimentoWaveform):
    id = "06"
    nome = "FLICKER"
    # Parâmetro SORTEADO em gerar(): 3 capturas por padrão na bancada (uma
    # captura mostra uma só realização do sorteio; CHANGELOG/v1.13.md). Não
    # muda o dataset simulado.
    capturas_padrao = 3

    def forma_esperada_para_validacao(self, capture_index, t, seed):
        # O FLICKER tem média não nula em cada ciclo: a fonte remove essa
        # média e reamostra a TRACe. Compare a medida com a reconstrução do
        # que foi programado, preservando gerar()/modelo como referência
        # matemática independente. Nunca use a própria medida como esperado.
        versoes = self._versoes_atuais or {}
        if "programada" in versoes:
            try:
                programada = np.asarray(versoes["programada"], dtype=np.float64)
                if (programada.shape == (AmetekMX30.CAPTURE_POINTS,)
                        and programada.shape == np.asarray(t).shape
                        and np.all(np.isfinite(programada))):
                    return programada
            except (TypeError, ValueError):
                pass
        forma = super().forma_esperada_para_validacao(capture_index, t, seed)
        if forma is None:
            return None
        # Sem captura em curso (ex.: análise offline), reconstrua pelo mesmo
        # planejador puro, incluindo a forma reduzida pelos limites da bancada
        # quando _forma_programada_pu estiver disponível. Classe 06 não usa DC.
        return AmetekMX30.montar_programacao(
            forma, base_voltage_rms=self.config.base_voltage_rms,
            frequency_hz=self.config.grid_frequency_hz, dc_offset_pu=0.0,
            passo_final_sin=bool(getattr(self.fonte, "passo_final_sin", False)),
        ).programada_pu()

    def gerar(self, t, f0, capture_index, rng):
        simulado = self.osc is None
        total = self.config.capturas(simulado)
        cobertura_ativa = not simulado and self.config.capturas_override is not None
        flicker_hz = sinais.valor_para_captura(rng, 8.0, 25.0, capture_index, total, cobertura_ativa=cobertura_ativa)
        profundidade = float(rng.uniform(*perfis.faixa(self.config, "flicker_profundidade")))
        sorteio = self.sortear(rng, f0)
        voltage = np.sin(2.0 * np.pi * f0 * (t + sorteio.deslocamento_s)) * (
            1.0 + profundidade * np.sin(2.0 * np.pi * flicker_hz * t)
        )
        return voltage, {"flicker_hz": flicker_hz, "flicker_depth": profundidade, **sorteio.parametros()}

    def parametros_com_disturbio_reduzido(self, parametros, fracao):
        # Gancho de bancada (limite de bancada, v1.13): forma física =
        # senoide + fracao x (gerar() - senoide). gerar() não muda.
        return {"flicker_depth_bancada": fracao * parametros["flicker_depth"]}
