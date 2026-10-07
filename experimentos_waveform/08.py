"""Classe 08: TRANSIENT (transitório impulsivo) — forma de onda arbitrária."""

import logging
import math

import numpy as np

from mestre import ExperimentoWaveform, ParameterOutOfBoundsError

logger = logging.getLogger("MestreExperimentos")


class Experimento(ExperimentoWaveform):
    id = "08"
    nome = "TRANSIENT"

    INICIO_IMPULSO_S = 0.080
    DURACAO_IMPULSO_S = 0.00005

    # Resposta da saída da MX30 ao impulso de ~66 µs: oscilação de ~10 kHz
    # que morre em <0,5 ms. Caracterizada em 2026-09-30 15:09 ("set capturas
    # 6" + "run 08", degraus de 45 a 339 V, VMAX/VMIN do osciloscópio na taxa
    # cheia): pico 0,38 do degrau ACIMA do alvo e vale 0,55-0,58 do degrau
    # ABAIXO do nível de partida, aproximadamente lineares no degrau. O array a
    # 30 kSa/s subestimava os dois (0,08 / 0,45). Usados com margem de ~1,2
    # (docs/analise-2026-09-30/ANALISE.md, T8-4).
    SOBRESSINAL_DO_DEGRAU = 0.45
    SUBSINAL_DO_DEGRAU = 0.70
    # Primeiro degrau da varredura de caracterização (0,25 pu ≈ 45 V a 127 V).
    AMPLITUDE_MIN_CARACTERIZACAO_PU = 0.25

    # A saída desta classe oscila além do programado: sem VMAX/VMIN medidos
    # pelo osciloscópio a captura não prova que ficou no teto, e a classe para.
    # Teto dos extremos MEDIDOS = 90% de max_peak_v — o mesmo alvo usado para
    # dimensionar a amplitude; numa varredura, a primeira captura que passar
    # dele interrompe a subida.
    exige_medida_de_pico = True
    fracao_teto_pico_medido = 0.9

    def limite_pico_bancada_pu(self):
        # experimentos.txt pede 5-10 pu de amplitude ADICIONAL ao pico normal
        # (até ~11 pu total) — a 127 Vrms isso passa de 1900 V, muito acima
        # do teto físico da AMETEK MX30 no range de 300 Vrms (~415 Vp).
        # 90% do pico máximo autorizado (self.fonte.max_peak_v) como margem
        # de segurança sobre o teto físico; só afeta a captura de
        # comissionamento (ver docstring em ExperimentoWaveform).
        nominal_peak_v = self.config.base_voltage_rms * math.sqrt(2.0)
        return 0.9 * self.fonte.max_peak_v / nominal_peak_v

    def _indices_impulso(self, fs_hz):
        start_index = int(round(self.INICIO_IMPULSO_S * fs_hz))
        pulse_samples = max(1, int(math.ceil(self.DURACAO_IMPULSO_S * fs_hz)))
        return np.arange(start_index, start_index + pulse_samples)

    def gerar(self, t, f0, capture_index, rng):
        fs_hz = 1.0 / (t[1] - t[0])
        voltage = np.sin(2.0 * np.pi * f0 * t)
        simulado = self.osc is None
        total = self.config.capturas(simulado)
        cobertura_ativa = not simulado and self.config.capturas_override is not None
        if cobertura_ativa and total > 1:
            pico_min_pu, pico_max_pu = 1.2, self.limite_pico_bancada_pu()
            pico_alvo_pu = float(np.linspace(pico_min_pu, pico_max_pu, total)[capture_index])
            amplitude = pico_alvo_pu - 1.0
        else:
            amplitude = float(rng.uniform(5.0, 10.0))
        indices = self._indices_impulso(fs_hz)
        voltage[indices] += amplitude
        return voltage, {"transient_amplitude_pu": amplitude, "pulse_samples": float(indices.size)}

    def forma_para_bancada(self, voltage_pu, parametros, capture_index):
        """Limita SÓ a amplitude do impulso; a senoide base fica em 1 pu.

        Antes, a forma inteira era escalada (0,340 no run04): a base caía para
        43 Vrms e o osciloscópio, com escala para o impulso, via a base com
        ±1 código de ruído (T8-1). O impulso parte do valor da senoide no
        instante (t=80 ms → -0,95 pu), então o limite que aperta é o VALE da
        oscilação logo depois dele, não o pico: com degrau A,
        pico ≈ s + A(1 + SOBRESSINAL) e vale ≈ s - SUBSINAL·A, e os dois têm de
        caber em ``limite_pico_bancada_pu()``."""
        indices = self._indices_impulso(self.config.fs_hz)
        amplitude_modelo = float(parametros["transient_amplitude_pu"])
        base = np.array(voltage_pu, dtype=np.float64)
        base[indices] -= amplitude_modelo
        limite = float(self.limite_pico_bancada_pu())
        partida_min = float(np.min(base[indices]))
        partida_max = float(np.max(base[indices]))
        a_pelo_pico = (limite - partida_max) / (1.0 + self.SOBRESSINAL_DO_DEGRAU)
        a_pelo_vale = (limite + partida_min) / self.SUBSINAL_DO_DEGRAU
        a_max = min(a_pelo_pico, a_pelo_vale)
        if not a_max > 0:
            raise ParameterOutOfBoundsError(
                f"[08] nenhum impulso cabe no teto de {limite:.3f} pu com a base a 1 pu "
                f"(partida {partida_min:.3f} pu)"
            )
        total = self.config.capturas(False)
        caracterizacao = self.config.capturas_override is not None and total > 1
        if caracterizacao:
            a_min = min(self.AMPLITUDE_MIN_CARACTERIZACAO_PU, a_max)
            amplitude = float(np.linspace(a_min, a_max, total)[capture_index])
        else:
            amplitude = a_max
        forma = base.copy()
        forma[indices] += amplitude
        nominal_v = self.config.base_voltage_rms * math.sqrt(2.0)
        pico_previsto_v = max(float(np.max(base)), partida_max + amplitude * (1.0 + self.SOBRESSINAL_DO_DEGRAU)) * nominal_v
        vale_previsto_v = min(float(np.min(base)), partida_min - self.SUBSINAL_DO_DEGRAU * amplitude) * nominal_v
        self._excursao_prevista_v = max(abs(pico_previsto_v), abs(vale_previsto_v))
        parametros.update({
            "amplitude_bancada_pu": amplitude,
            "pico_previsto_v": pico_previsto_v,
            "vale_previsto_v": vale_previsto_v,
            "caracterizacao": float(caracterizacao),
        })
        logger.warning(
            "[08] impulso FÍSICO %.3f pu (modelo pede %.3f pu; máximo seguro %.3f pu); base a 1 pu; "
            "previsto pico %.0f V / vale %.0f V (teto %.0f V)%s.",
            amplitude, amplitude_modelo, a_max, pico_previsto_v, vale_previsto_v,
            limite * nominal_v, " — CARACTERIZAÇÃO" if caracterizacao else "",
        )
        return forma

    def excursao_fisica_prevista_v(self):
        return getattr(self, "_excursao_prevista_v", None)

    def ciclos_excluidos_da_validacao(self, capture_index):
        # Ciclo do impulso e o seguinte (oscilação): ver T8-3 no ANALISE.md.
        n = int(round(self.config.fs_hz / self.config.grid_frequency_hz))
        ciclo = int(self._indices_impulso(self.config.fs_hz)[0]) // n
        return tuple(k for k in (ciclo, ciclo + 1) if k < self.config.points // n)
