"""Classe 08: TRANSIENT (transitório impulsivo) — forma de onda arbitrária."""

import logging
import math

import numpy as np

from mestre import ExperimentoWaveform, ParameterOutOfBoundsError

logger = logging.getLogger("MestreExperimentos")


class Experimento(ExperimentoWaveform):
    id = "08"
    nome = "TRANSIENT"
    # Parâmetro SORTEADO em gerar(): 3 capturas por padrão na bancada (uma
    # captura mostra uma só realização do sorteio; CHANGELOG/v1.13.md). Não
    # muda o dataset simulado.
    # O padrão NÃO liga a caracterização: sem "set capturas" as 3 capturas
    # sorteiam o modelo e aplicam o impulso máximo seguro; a rampa de
    # amplitude continua exigindo "set capturas N" digitado pelo operador.
    capturas_padrao = 3

    INICIO_IMPULSO_S = 0.080
    DURACAO_IMPULSO_S = 0.00005
    # v1.15 (`arquivo/analises:docs/analise-2026-10-12/pendente/classe08_fronteira_REVISAR.md`): a 50 Hz os 80 ms
    # são o início do 5.º ciclo, e a fonte tocou o impulso no FIM desse ciclo
    # (100 ms; 3 capturas, 2026-10-07). O impulso nunca cai a menos de
    # DISTANCIA_MIN_FRONTEIRA_AMOSTRAS amostras (1 ms) de uma fronteira de
    # ciclo da rede: o deslocamento medido envolve <= 4 pontos da TRACE
    # (<= 2,3 amostras), as capturas diferem ±2 amostras entre si e o
    # toque pós-impulso dura < 0,5 ms (15 amostras). Vale com
    # ``sorteio_posicao`` ligado (padrão); desligado, o 80 ms de sempre
    # (34a0d82), inclusive a 50 Hz, para reproduzir as sessões de 07/10.
    DISTANCIA_MIN_FRONTEIRA_AMOSTRAS = 30
    # A validação física confere que o maior desvio da senoide cai a até
    # TOLERANCIA_POSICAO_AMOSTRAS (0,33 ms) do início do impulso: acima do
    # atraso/jitter medido (<= 3 amostras) e 60x abaixo do desvio de 20 ms.
    TOLERANCIA_POSICAO_AMOSTRAS = 10
    # O desvio medido tem de ser ao menos esta fração da amplitude de bancada
    # (a saída fez 1,4x; sem impulso nenhum não há posição a conferir).
    FRACAO_MIN_DESVIO_VISIVEL = 0.25

    # Resposta da saída da MX30 ao impulso de ~66 µs: oscilação de ~10 kHz
    # que morre em <0,5 ms. Caracterizada em 2026-09-30 15:09 ("set capturas
    # 6" + "run 08", degraus de 45 a 339 V, VMAX/VMIN do osciloscópio na taxa
    # cheia): pico 0,38 do degrau ACIMA do alvo e vale 0,55-0,58 do degrau
    # ABAIXO do nível de partida, aproximadamente lineares no degrau. O array a
    # 30 kSa/s subestimava os dois (0,08 / 0,45). Usados com margem de ~1,2
    # (`arquivo/analises:docs/analise-2026-09-30/ANALISE.md`, T8-4).
    # v1.14: a 60 Hz o impulso (t = 80 ms) parte de -0,95 pu e quem limita a
    # amplitude é o VALE — o pico nunca chegava perto do teto e o 0,45 nunca
    # foi posto à prova. A 50 Hz ele parte do cruzamento por zero (maior
    # inclinação da senoide), quem limita é o PICO, e a saída fez 0,437-0,457
    # (127 V e 230 V, bancada 2026-10-07): com 0,45 o pico mediu 376 V contra
    # teto de 374,2 V nas três sessões a 50 Hz. 0,55 = mesma margem de ~1,2,
    # agora sobre o pior medido (0,457). A 60 Hz nada muda (vale continua
    # limitando).
    SOBRESSINAL_DO_DEGRAU = 0.55
    SUBSINAL_DO_DEGRAU = 0.70
    # Sobressinal MEDIDO acima disto é achado de segurança (ROTEIRO_BANCADA.md
    # linhas 197 e 374; docs/classes/08-transient.md). Só vira flag no metadata:
    # não recusa a captura (o roteiro manda parar e avisar, não descartar).
    SOBRESSINAL_ACHADO_DE_SEGURANCA = 0.55
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

    def _indices_impulso(self, fs_hz, f0_hz=None):
        """Amostras do impulso. ``f0_hz`` (padrão: a da rede da config) só
        importa com ``sorteio_posicao`` ligado: se o início de 80 ms cair a
        menos de ``DISTANCIA_MIN_FRONTEIRA_AMOSTRAS`` de uma fronteira de
        ciclo (a 50 Hz cai exatamente nela), o impulso vai para o meio do
        mesmo ciclo (90 ms a 50 Hz: cruzamento por zero, como o de 80 ms
        e com o mesmo nível de partida). A 60 Hz continua em 80 ms."""
        start_index = int(round(self.INICIO_IMPULSO_S * fs_hz))
        pulse_samples = max(1, int(math.ceil(self.DURACAO_IMPULSO_S * fs_hz)))
        if getattr(self.config, "sorteio_posicao", True):
            if f0_hz is None:
                f0_hz = self.config.grid_frequency_hz
            n = int(round(fs_hz / float(f0_hz)))
            resto = start_index % n
            minimo = self.DISTANCIA_MIN_FRONTEIRA_AMOSTRAS
            if resto < minimo or n - resto - pulse_samples < minimo:
                start_index = start_index - resto + n // 2
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
        indices = self._indices_impulso(fs_hz, f0)
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
        self._amplitude_bancada_pu = amplitude
        parametros.update({
            "amplitude_bancada_pu": amplitude,
            "inicio_impulso_s": float(indices[0]) / float(self.config.fs_hz),
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
        # A POSIÇÃO do impulso é conferida em ``conferir_posicao_do_evento``.
        n = int(round(self.config.fs_hz / self.config.grid_frequency_hz))
        ciclo = int(self._indices_impulso(self.config.fs_hz)[0]) // n
        return tuple(k for k in (ciclo, ciclo + 1) if k < self.config.points // n)

    def conferir_posicao_do_evento(self, capture_index, janela_medida_pu):
        """O maior desvio da senoide, na janela medida alinhada ao trigger,
        tem de cair a até ``TOLERANCIA_POSICAO_AMOSTRAS`` do início do
        impulso programado. A validação de envelope/THD/crista exclui os dois
        ciclos do impulso e não via o impulso 20 ms fora do lugar (50 Hz,
        2026-10-07)."""
        fs_hz = float(self.config.fs_hz)
        f0 = float(self.config.grid_frequency_hz)
        medido = np.asarray(janela_medida_pu, dtype=np.float64)
        senoide = np.sin(2.0 * np.pi * f0 * np.arange(medido.size) / fs_hz)
        desvio = np.abs(medido - senoide)
        previsto = int(self._indices_impulso(fs_hz)[0])
        achado = int(np.argmax(desvio))
        diferenca = achado - previsto
        resultado = {
            "inicio_previsto_amostra": previsto,
            "pico_medido_amostra": achado,
            "desvio_amostras": diferenca,
            "tolerancia_amostras": self.TOLERANCIA_POSICAO_AMOSTRAS,
            "desvio_pico_pu": float(desvio[achado]),
        }
        amplitude = getattr(self, "_amplitude_bancada_pu", None)
        # Sobressinal medido (P-03). O roteiro (linhas 197/374) só dá o limite
        # (0,55); a grandeza é a de ``SOBRESSINAL_DO_DEGRAU`` / ``forma_para_bancada``:
        # fração do degrau programado A que o pico passa de (senoide + A), isto é
        # ``pico = s + A(1 + sobressinal)``. Como ``forma_para_bancada`` soma +A
        # (A > 0), o pico é o MAIOR desvio SINALIZADO na direção do degrau,
        # max(medido - senoide), e não o maior desvio absoluto (que pode ser o
        # vale/subsinal). Resultado = esse desvio / A - 1. Resultado < -1 ou não
        # finito é medição inválida: grava None e ``sobressinal_invalido``.
        # Limite: a janela é amostrada a 30 kSa/s e a oscilação é de ~10 kHz, então
        # o pico amostrado pode ficar abaixo do real (subestima); o pico absoluto
        # real é conferido por ``medir_extremos`` (teto 374,2 V).
        if amplitude is not None and float(amplitude) > 0:
            sinalizado = medido - senoide  # degrau positivo: pico = maior desvio positivo
            with np.errstate(invalid="ignore"):
                sobressinal = float(np.max(sinalizado)) / float(amplitude) - 1.0
            if not math.isfinite(sobressinal) or sobressinal < -1.0:
                resultado["sobressinal_medido"] = None
                resultado["sobressinal_invalido"] = True
            else:
                resultado["sobressinal_medido"] = sobressinal
                resultado["sobressinal_limite"] = self.SOBRESSINAL_ACHADO_DE_SEGURANCA
                resultado["sobressinal_acima_do_limite"] = bool(sobressinal > self.SOBRESSINAL_ACHADO_DE_SEGURANCA)
        motivos = []
        if amplitude is not None and desvio[achado] < self.FRACAO_MIN_DESVIO_VISIVEL * float(amplitude):
            motivos.append(
                f"impulso não encontrado: maior desvio da senoide {desvio[achado]:.3f} pu, "
                f"esperado ao menos {self.FRACAO_MIN_DESVIO_VISIVEL * float(amplitude):.3f} pu"
            )
        elif abs(diferenca) > self.TOLERANCIA_POSICAO_AMOSTRAS:
            motivos.append(
                f"posição do impulso: pico medido na amostra {achado} "
                f"({1000.0 * achado / fs_hz:.2f} ms), previsto {previsto} "
                f"({1000.0 * previsto / fs_hz:.2f} ms); diferença {diferenca:+d} amostras "
                f"(tolerância ±{self.TOLERANCIA_POSICAO_AMOSTRAS})"
            )
        return {"ok": not motivos, "motivos": motivos, "posicao": resultado}
