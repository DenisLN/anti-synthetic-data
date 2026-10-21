"""Diagnóstico 2026-10-12: por que o CA da classe 19 (DC_OFFSET) sai ~5-6 % menor?

Nas três sessões de 07/10 a componente alternada da classe 19 (``SOURce:MODE
ACDC`` + ``VOLTage:TRIGgered``) saiu com 0,938 a 0,951 pu, igual nas três
capturas e independente do offset; a classe 01 (AC) saiu com 1,000. Este
script mede, na MESMA conexão e com o MESMO CH1/probe, a fonte
(``MEASure:VOLTage:AC?`` e ``MEASure:VOLTage:DC?``) e o canal 1 do Keysight
(forma de onda -> média, RMS AC, RMS total, picos) em:

  1. AC   / STEP      / offset 0     (como a classe 01; linha de base)
  2. ACDC / STEP      / offset 0     (entrada "limpa" em ACDC, como a classe 19)
  3. ACDC / imediato  / offset 0     (``VOLTage`` imediato em vez do degrau)
  4. ACDC / STEP      / offset 2 %   (``--offsets-pu``, 0,02 a 0,10 pu como a 19)
  5. ACDC / STEP      / offset 10 %
  6. AC   / STEP      / offset 0     (controle final: descarta deriva no tempo)

Com ``--testar-compensacao`` acrescenta, ao final, a correção proposta no
relatório (programar ``V / g`` com ``g`` = ganho CA medido na linha 2) com
offset 0 e 10 %, para ver se o CA volta a 1,000 pu.

Segurança (AGENTS.md, "Limites inegociáveis" — nada aqui os altera):
* Usa ``AmetekMX30`` e ``KeysightDSOX4034A`` do projeto, com os MESMOS limites
  do ``start_bench_windows.ps1`` para range 300 V (max_voltage_rms=300,
  max_peak_v=415,8, 0,5 A); COM10/115200 vêm do ORM e ``configure_safe_baseline``
  mantém as validações de IDN, SCPI e pico.
* A saída só é ligada depois de você DIGITAR ``ENERGIZAR-ACDC`` (case-sensitive).
  Nenhuma confirmação é automatizada. Em ``--simulado`` nada é energizado e a
  confirmação não é pedida.
* Tensão <= 270 Vrms (mesmo teto da bancada); offsets entre 0,02 e 0,10 pu
  (faixa que a classe 19 já usa); pico total (CA + offset) validado por
  ``enable_dc_offset()``/``trigger_step()`` contra ``max_peak_v``.
* No ``finally`` o script volta a AC, zera o offset e manda ``safe_shutdown()``
  (ABORt + OUTPut OFF + confirmação). Se a infraestrutura falhar (serial,
  OUTPUT não confirmado): confirme OUTPUT OFF no painel, NÃO repita
  automaticamente e entregue o ``logs/diag_acdc_amplitude-*.log`` mais recente.

Feche a CLI da bancada (libera COM10 e o USB do Keysight) antes de rodar.

Uso (PowerShell, na raiz do projeto, com o fator da probe escrito nela):

    $env:BENCH_MODE = "1"
    env\\Scripts\\python.exe scripts\\diag_acdc_amplitude.py --probe 500 --vrms 127 --hz 60

Teste sem hardware (valores FICTÍCIOS; só exercita o código):

    env\\Scripts\\python.exe scripts\\diag_acdc_amplitude.py --simulado --probe 500 --vrms 127 --hz 60 --testar-compensacao
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "logica"))

from ametek_orm import AmetekMX30, AmetekORMError  # noqa: E402

CONFIRMACAO = "ENERGIZAR-ACDC"
PORTA = "COM10"
BAUD = 115_200
# Idênticos ao start_bench_windows.ps1 para o range 300 V (as sessões de 07/10
# foram todas em range 300; trocar de range seria uma variável a mais).
RANGE_RMS = 300.0
MAX_RMS = 300.0
MAX_PICO_V = round(RANGE_RMS * math.sqrt(2.0) * 0.98, 1)  # 415,8
LIMITE_CORRENTE_A = 0.5
ATRASO_PROTECAO_S = 0.1
TENSAO_MAX_V = 270.0
FS_HZ = 30_000.0
PONTOS = 6_000
DURACAO_S = 0.200
IDN_OSC = "DSOX4034A"
RECURSO_OSC = "USB0::0x0957::0x17A4::MY59240844::0::INSTR"

logger = logging.getLogger("diag_acdc")


# ---------------------------------------------------------------------------
# Modo simulado (FICTÍCIO): fonte + CH1 sintéticos com um "ganho ACDC" escolhido
# na linha de comando, só para exercitar o fluxo e a aritmética do relatório.
# ---------------------------------------------------------------------------
class _FisicaFicticia:
    def __init__(self, ganho_acdc: float, f_hz: float):
        self.ganho_acdc = ganho_acdc
        self.f_hz = f_hz
        self.modo = "AC"
        self.offset = 0.0
        self.disparo = 0.0
        self.nivel = 0.0  # Vrms CA programado e aplicado
        self.rng = np.random.default_rng(1)

    def escrita(self, comando: str) -> None:
        c = comando.strip()
        up = c.upper()
        valor = c.split()[-1] if " " in c else ""
        if up.startswith("SOURCE:MODE "):
            self.modo = valor.upper()
            self.nivel, self.offset = 0.0, 0.0  # manual p. 98: a troca zera a saída
        elif up.startswith("SOURCE:VOLTAGE:OFFSET "):
            self.offset = float(valor)
        elif up.startswith("VOLTAGE:TRIGGERED "):
            self.disparo = float(valor)
        elif up == "*TRG":
            self.nivel = self.disparo
        elif up.startswith("SOURCE:VOLTAGE:LEVEL:IMMEDIATE:AMPLITUDE "):
            self.nivel = float(valor)

    @property
    def ca(self) -> float:
        return self.nivel * (self.ganho_acdc if self.modo == "ACDC" else 1.0)

    @property
    def cc(self) -> float:
        return self.offset if self.modo == "ACDC" else 0.0

    def consulta(self, comando: str) -> Optional[str]:
        up = comando.strip().upper()
        if up == "MEASURE:VOLTAGE:AC?":
            return f"{math.hypot(self.ca, self.cc) * 0.9964:.3f}"  # sense interno ~-0,36 %
        if up == "MEASURE:VOLTAGE:DC?":
            return f"{self.cc:.3f}"
        return None


class _OscFicticio:
    idn = "SIMULADO,DSO-X 4034A,FICTICIO,0"

    def __init__(self, fisica: _FisicaFicticia):
        self.fisica = fisica

    def __getattr__(self, nome):  # configure_*, initialize_safe, arm, ... sem efeito
        return lambda *a, **k: None

    def verify_identity(self, *_a, **_k):
        return self.idn

    def set_vertical_scale(self, _canal, pico):
        return pico / 3.0

    def get_waveform(self, _canal, **_k):
        t = np.arange(PONTOS) / FS_HZ
        f = self.fisica
        v = math.sqrt(2.0) * f.ca * np.sin(2 * math.pi * f.f_hz * t) + f.cc + f.rng.normal(0, 0.3, PONTOS)
        return t, v

    def ask(self, comando):
        if "VRMS" in comando.upper():
            return f"{math.hypot(self.fisica.ca, self.fisica.cc):.3f}"
        return "0"


# ---------------------------------------------------------------------------
# Medidas
# ---------------------------------------------------------------------------
def estatisticas_ch1(v: np.ndarray, f_hz: float) -> Dict[str, float]:
    """Média (CC), RMS da parte CA, RMS total e picos, sobre um número INTEIRO
    de períodos (evita o viés de janela parcial)."""
    n = int(round(FS_HZ / f_hz))
    k = len(v) // n
    if k < 1:
        raise RuntimeError(f"Janela de {len(v)} pontos não cobre um período de {f_hz} Hz")
    seg = np.asarray(v[: k * n], dtype=float)
    media = float(seg.mean())
    rms_ac = float(seg.std())
    return {
        "periodos": k,
        "cc_v": media,
        "rms_ac_v": rms_ac,
        "rms_total_v": math.hypot(media, rms_ac),
        "vmax_v": float(seg.max()),
        "vmin_v": float(seg.min()),
        "pico_ac_v": float((seg.max() - seg.min()) / 2.0),
    }


def mediana(valores: List[float]) -> float:
    return float(np.median(valores))


class Diag:
    def __init__(self, fonte: AmetekMX30, osc, args):
        self.fonte, self.osc, self.args = fonte, osc, args
        self.linhas: List[dict] = []
        self.cc_suportado = True
        self.erros_scpi_aceitos: List[str] = []
        self.consultas_indisponiveis: set = set()

    # ---- fonte --------------------------------------------------------
    def _consulta_opcional(self, comando: str) -> Optional[str]:
        """Query que a Rev. 5.53 pode não implementar (nunca testada na bancada):
        se falhar, registra, esvazia a fila (o -113 não pode ser atribuído ao
        próximo passo) e não repete."""
        if comando in self.consultas_indisponiveis:
            return None
        try:
            resposta = self.fonte.query(comando).strip()
            erros = self.fonte.check_errors()
            if erros:
                raise ValueError(erros)
            return resposta
        except (AmetekORMError, ValueError) as exc:
            self.consultas_indisponiveis.add(comando)
            self.erros_scpi_aceitos.append(f"{comando} -> {exc}")
            try:
                self.erros_scpi_aceitos.append(f"fila após a query: {self.fonte.check_errors()}")
            except AmetekORMError as exc2:
                self.erros_scpi_aceitos.append(f"fila não lida: {exc2}")
            logger.warning("%s indisponível: %s", comando, exc)
            return None

    def _ler_fonte(self, n: int) -> Dict[str, object]:
        ac, cc = [], []
        for _ in range(n):
            ac.append(float(self.fonte.query("MEASure:VOLTage:AC?")))
            if self.cc_suportado:
                try:
                    cc.append(float(self.fonte.query("MEASure:VOLTage:DC?")))
                    erros = self.fonte.check_errors()
                    if erros:
                        raise ValueError(erros)
                except (AmetekORMError, ValueError) as exc:
                    # Pergunta de pesquisa, não do fluxo: a Rev. 5.53 pode não
                    # implementar MEAS:VOLT:DC?. Registra e segue sem a coluna.
                    self.cc_suportado = False
                    self.erros_scpi_aceitos.append(f"MEASure:VOLTage:DC? -> {exc}")
                    try:  # esvazia o -113 que a query deixou, para não culpar o próximo passo
                        self.erros_scpi_aceitos.append(f"fila após a query: {self.fonte.check_errors()}")
                    except AmetekORMError as exc2:
                        self.erros_scpi_aceitos.append(f"fila não lida: {exc2}")
                    logger.warning("MEASure:VOLTage:DC? indisponível: %s", exc)
            time.sleep(0.25)
        return {
            "src_ac_leituras": ac,
            "src_ac_v": mediana(ac),
            "src_ac_espalhamento_v": max(ac) - min(ac),
            "src_cc_v": mediana(cc) if cc else None,
        }

    # ---- osciloscópio -------------------------------------------------
    def _capturar(self) -> Dict[str, float]:
        osc = self.osc
        osc.arm()
        osc.wait_for_armed(timeout_s=5.0)
        osc.force_trigger()
        osc.wait_for_trigger_complete(timeout_s=5.0)
        vrms_osc = None
        try:
            vrms_osc = float(osc.ask(":MEASure:VRMS? DISPlay,AC,CHANnel1"))
        except Exception as exc:  # noqa: BLE001 - cross-check opcional
            logger.warning("VRMS do osciloscópio indisponível: %s", exc)
        _t, v = osc.get_waveform(1, expected_points=PONTOS)
        est = estatisticas_ch1(v, self.args.hz)
        est["osc_vrms_display_ac_v"] = vrms_osc
        return est

    # ---- uma condição -------------------------------------------------
    def medir(self, modo: str, caminho: str, offset_pu: float, v_prog: float, v_alvo: float, rotulo: str) -> dict:
        time.sleep(0.5)  # a fonte e o MEAS assentam depois do degrau (sem sleep de "contorno": só leitura)
        range_fonte = self._consulta_opcional("VOLTage:RANGe?")
        fonte = self._ler_fonte(self.args.leituras_fonte)
        caps = [self._capturar() for _ in range(self.args.capturas_osc)]
        ch1 = {k: mediana([c[k] for c in caps]) for k in ("cc_v", "rms_ac_v", "rms_total_v", "vmax_v", "vmin_v", "pico_ac_v")}
        ch1["rms_ac_espalhamento_v"] = max(c["rms_ac_v"] for c in caps) - min(c["rms_ac_v"] for c in caps)
        saida_ligada = self.fonte.output_enabled
        if not saida_ligada:
            raise RuntimeError(f"{rotulo}: OUTPUT caiu durante a medida; abortando")
        erros = self.fonte.check_errors()
        if erros:
            raise RuntimeError(f"{rotulo}: fila SCPI da fonte não está vazia: {erros}")
        offset_v = offset_pu * v_alvo * math.sqrt(2.0)
        linha = {
            "rotulo": rotulo, "modo": modo, "caminho": caminho, "offset_pu": offset_pu,
            "offset_programado_v": offset_v, "v_alvo_vrms": v_alvo, "v_programada_vrms": v_prog,
            "range_fonte_lido": range_fonte, "fonte": fonte, "ch1": ch1,
            "razao_ch1_ac_sobre_alvo": ch1["rms_ac_v"] / v_alvo,
            "razao_ch1_total_sobre_fonte_ac": ch1["rms_total_v"] / fonte["src_ac_v"] if fonte["src_ac_v"] > 1 else None,
        }
        self.linhas.append(linha)
        logger.info(
            "%-34s fonte AC=%8.3f DC=%s | CH1 AC=%8.3f DC=%7.3f tot=%8.3f | CH1_AC/alvo=%.4f",
            rotulo, fonte["src_ac_v"], f"{fonte['src_cc_v']:.3f}" if fonte["src_cc_v"] is not None else "n/d",
            ch1["rms_ac_v"], ch1["cc_v"], ch1["rms_total_v"], linha["razao_ch1_ac_sobre_alvo"],
        )
        return linha

    # ---- estados da fonte (a mesma sequência das classes 01/19) -------
    def _degrau(self, v_prog: float) -> None:
        f = self.fonte
        f.trigger_step(v_prog)
        f.arm()
        f.trigger()
        f.wait_transient_complete(timeout_s=5.0)

    def ac_degrau(self, v_prog: float, v_alvo: float, rotulo: str) -> dict:
        self.fonte.disable_dc_offset()  # no-op se já em AC (ver ametek_orm.disable_dc_offset)
        self._degrau(v_prog)
        return self.medir("AC", "STEP", 0.0, v_prog, v_alvo, rotulo)

    def acdc(self, caminho: str, offset_pu: float, v_prog: float, v_alvo: float, rotulo: str) -> dict:
        f = self.fonte
        pico_ca = v_prog * math.sqrt(2.0)
        offset_v = offset_pu * v_alvo * math.sqrt(2.0)
        f.disable_dc_offset()  # entrada limpa: AC -> ACDC (a troca de modo zera a saída)
        f.enable_dc_offset(offset_v, ac_peak_v=pico_ca)
        if caminho == "STEP":
            self._degrau(v_prog)
        else:
            f.aguardar_idle()
            f.write("VOLTage:MODE FIXed")
            f.voltage = v_prog
            f.assert_no_errors("VOLTage imediato em ACDC")
        return self.medir("ACDC", caminho, offset_pu, v_prog, v_alvo, rotulo)


# ---------------------------------------------------------------------------
def montar_tabela(linhas: List[dict]) -> str:
    cab = (
        "| condição | V_alvo | V_prog | fonte AC? (V) | fonte DC? (V) | CH1 AC (V) | CH1 CC (V) | CH1 total (V) "
        "| CH1 AC / alvo | CH1 total / fonte AC? |\n|---|---|---|---|---|---|---|---|---|---|\n"
    )
    out = []
    for r in linhas:
        f, c = r["fonte"], r["ch1"]
        cc = f"{f['src_cc_v']:.3f}" if f["src_cc_v"] is not None else "n/d"
        rz = f"{r['razao_ch1_total_sobre_fonte_ac']:.4f}" if r["razao_ch1_total_sobre_fonte_ac"] else "n/d"
        out.append(
            f"| {r['rotulo']} | {r['v_alvo_vrms']:.3f} | {r['v_programada_vrms']:.1f} | {f['src_ac_v']:.3f} | {cc} "
            f"| {c['rms_ac_v']:.3f} | {c['cc_v']:.3f} | {c['rms_total_v']:.3f} | {r['razao_ch1_ac_sobre_alvo']:.4f} | {rz} |"
        )
    return cab + "\n".join(out)


def validar_args(a) -> None:
    if not 0 < a.vrms <= TENSAO_MAX_V:
        raise SystemExit(f"--vrms deve estar em (0, {TENSAO_MAX_V:g}] Vrms (teto da bancada)")
    if not 45.0 <= a.hz <= 500.0:
        raise SystemExit("--hz fora de 45..500 Hz")
    if a.probe is None or a.probe <= 0:
        raise SystemExit("Informe --probe (ou VOLTAGE_PROBE_ATTENUATION) com o fator ESCRITO na probe instalada; não há valor padrão.")
    for o in a.offsets:
        if not 0.02 - 1e-9 <= o <= 0.10 + 1e-9:
            raise SystemExit(f"Offset {o} pu fora de 0,02..0,10 (faixa que a classe 19 já usa)")
    if not 1 <= a.leituras_fonte <= 20 or not 1 <= a.capturas_osc <= 10:
        raise SystemExit("--leituras-fonte em 1..20 e --capturas-osc em 1..10")
    pico_pior = a.vrms / 0.88 * math.sqrt(2.0) * (1 + max(a.offsets))
    if pico_pior > MAX_PICO_V:
        raise SystemExit(f"Pior caso planejado ({pico_pior:.1f} Vp com compensação até 0,88) excede {MAX_PICO_V} Vp")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vrms", type=float, default=float(os.environ.get("BASE_VOLTAGE_RMS", "127")))
    ap.add_argument("--hz", type=float, default=float(os.environ.get("GRID_FREQUENCY_HZ", "60")))
    ap.add_argument("--probe", type=float, default=float(os.environ["VOLTAGE_PROBE_ATTENUATION"]) if os.environ.get("VOLTAGE_PROBE_ATTENUATION") else None)
    ap.add_argument("--offsets-pu", dest="offsets", type=lambda s: [float(x) for x in s.split(",")], default=[0.02, 0.10])
    ap.add_argument("--leituras-fonte", type=int, default=5)
    ap.add_argument("--capturas-osc", type=int, default=3)
    ap.add_argument("--testar-compensacao", action="store_true")
    ap.add_argument("--simulado", action="store_true")
    ap.add_argument("--ganho-acdc-simulado", type=float, default=0.95, help="FICTÍCIO, só com --simulado")
    ap.add_argument("--saida", type=Path, default=RAIZ / "logs")
    args = ap.parse_args(argv)
    validar_args(args)

    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    args.saida.mkdir(parents=True, exist_ok=True)
    base = args.saida / f"diag_acdc_amplitude-{ts}"
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[
        logging.StreamHandler(sys.stdout), logging.FileHandler(f"{base}.log", encoding="utf-8")])
    scpi = logging.getLogger("AmetekORM.scpi")
    scpi.setLevel(logging.DEBUG)
    scpi.propagate = False
    h = logging.FileHandler(f"{base}-scpi.log", encoding="utf-8")
    h.setFormatter(logging.Formatter("[%(asctime)s.%(msecs)03d] %(message)s", datefmt="%H:%M:%S"))
    scpi.addHandler(h)

    try:  # procedência (scripts/fechar_pendencias.py P-17 a exige), calculada ANTES de tocar a fonte
        import mestre
        codigo = mestre.info_do_codigo(recalcular=True)
    except Exception:  # noqa: BLE001 - nunca impede o diagnóstico
        codigo = {}

    if not args.simulado and os.environ.get("BENCH_MODE", "").strip() not in {"1", "true", "TRUE", "yes", "YES"}:
        raise SystemExit("Defina BENCH_MODE=1 para usar a bancada real (ou use --simulado).")

    fonte = AmetekMX30(
        PORTA, baudrate=BAUD, timeout_s=5.0, query_eot=True, expected_model="MX30",
        max_voltage_rms=MAX_RMS, max_peak_v=MAX_PICO_V, max_current_a=LIMITE_CORRENTE_A,
        simulated=args.simulado,
    )
    osc = None
    try:
        if args.simulado:
            fis = _FisicaFicticia(args.ganho_acdc_simulado, args.hz)
            bruto_w, bruto_q = fonte._raw_write, fonte.query

            def _w(comando, **k):
                fis.escrita(comando)
                return bruto_w(comando, **k)

            def _q(comando):
                r = fis.consulta(comando)
                return r if r is not None else bruto_q(comando)

            fonte._raw_write, fonte.query = _w, _q  # só no modo simulado
            osc = _OscFicticio(fis)
        else:
            from pymeasure.adapters import VISAAdapter
            from oscilloscope_orm import KeysightDSOX4034A
            osc = KeysightDSOX4034A(VISAAdapter(RECURSO_OSC, timeout=15_000))
            logger.info("Keysight: %s", osc.verify_identity(IDN_OSC))
            osc.initialize_safe()
            try:  # Ctrl+C no Windows com as duas sessões VISA abertas (ver mestre.py)
                from mestre import garantir_ctrl_c_no_windows
                garantir_ctrl_c_no_windows()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Ctrl+C pode não interromper este script (%s). Em emergência: botão OUTPUT no painel.", exc)

        fonte.configure_safe_baseline(
            voltage_range_rms=RANGE_RMS, voltage_high_vp=MAX_PICO_V, current_limit_a=LIMITE_CORRENTE_A,
            protection_delay_s=ATRASO_PROTECAO_S, frequency_hz=args.hz,
        )
        # CH1 como na bateria; escala FIXA para todas as condições (mesmo ganho do ADC).
        pico_planejado = args.vrms / 0.88 * math.sqrt(2.0) * (1 + max(args.offsets))
        osc.configure_channel(1, scale=pico_planejado / 3.0, probe_attenuation=args.probe, coupling="DC", units="VOLT")
        escala = osc.set_vertical_scale(1, pico_planejado)
        osc.disable_channel(2)
        osc.configure_acquisition(sample_rate_hz=FS_HZ, points=PONTOS, duration_s=DURACAO_S)
        osc.setup_external_trigger(level_v=1.5, probe_attenuation=1.0, range_v=8.0)
        logger.info("Fonte: %s | CH1: probe %gx, %.1f V/div | range %g V, f=%g Hz", fonte.idn, args.probe, escala, RANGE_RMS, args.hz)

        n_cond = 3 + len(args.offsets) + 1 + (2 if args.testar_compensacao else 0)
        print(f"\nVai LIGAR a saída em {args.vrms:g} Vrms / {args.hz:g} Hz, sem carga, {n_cond} condições "
              f"(~{n_cond * 12} s), pico total máximo ~{pico_planejado:.0f} Vp (limite {MAX_PICO_V} Vp).")
        if not args.simulado and input(f"Digite {CONFIRMACAO} para continuar: ") != CONFIRMACAO:
            print("Não confirmado; a saída continua OFF.")
            return 2

        fonte.authorize_output(True)
        fonte.energize_baseline()
        d = Diag(fonte, osc, args)
        v = args.vrms

        d.ac_degrau(v, v, "AC / STEP / off 0")
        base_acdc = d.acdc("STEP", 0.0, v, v, "ACDC / STEP / off 0")
        d.acdc("FIX", 0.0, v, v, "ACDC / imediato / off 0")
        for o in args.offsets:
            d.acdc("STEP", o, v, v, f"ACDC / STEP / off {100 * o:g} %")
        d.ac_degrau(v, v, "AC / STEP / controle final")

        if args.testar_compensacao:
            g = base_acdc["razao_ch1_ac_sobre_alvo"]
            if not 0.88 <= g <= 1.0:
                logger.warning("Ganho ACDC medido %.4f fora de 0,88..1,00: compensação NÃO testada.", g)
            else:
                v_comp = round(round((v / g) / 0.1) * 0.1, 1)
                logger.info("Compensação: g=%.4f -> programar %.1f V para obter %.1f V (alvo)", g, v_comp, v)
                for o in (0.0, max(args.offsets)):
                    d.acdc("STEP", o, v_comp, v, f"ACDC / STEP / off {100 * o:g} % / V_prog={v_comp:.1f}")

        fonte.disable_dc_offset()
        tabela = montar_tabela(d.linhas)
        print("\n" + tabela)
        with open(f"{base}.json", "w", encoding="utf-8") as fh:
            json.dump({"argumentos": {k: str(x) for k, x in vars(args).items()}, "idn_fonte": fonte.idn,
                       "modo": "simulado" if args.simulado else "bancada",
                       "git_commit": codigo.get("git_commit"), "git_sujo": codigo.get("git_sujo"),
                       "simulado": args.simulado, "mea_dc_indisponivel": d.erros_scpi_aceitos,
                       "linhas": d.linhas}, fh, indent=1, ensure_ascii=False)
        with open(f"{base}.md", "w", encoding="utf-8") as fh:
            fh.write(tabela + "\n")
        print(f"\nResultados: {base}.json | .md | .log | -scpi.log")
        return 0
    finally:
        try:
            if not args.simulado and fonte.output_authorized:
                try:
                    fonte.disable_dc_offset()
                except Exception:  # noqa: BLE001 - o shutdown abaixo é o que importa
                    logger.exception("Não consegui voltar a AC antes do shutdown")
            fonte.safe_shutdown()
            if not args.simulado:
                print("OUTPut:STATe? ->", fonte.query("OUTPut:STATe?").strip(), "(0 = desligada; CONFIRA NO PAINEL)")
        finally:
            fonte.disconnect()
            if osc is not None and not args.simulado:
                osc.close()


if __name__ == "__main__":
    sys.exit(main())
