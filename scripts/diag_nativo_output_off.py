"""Diagnóstico do caminho nativo da AMETEK com a SAÍDA DESLIGADA.

Responde às perguntas abertas de docs/analise-2026-09-30/ANALISE.md:

* N2 — por que ``PULSe:WIDTh 0.06`` é lido de volta como 0.0167 (acoplamento
  WIDTh/PERiod/DCYCle/HOLD, manual §4.21 p. 104-105)?
* N3 — qual é a resolução de ``VOLTage:TRIGgered``?
* N1 — a rajada ``FUNCtion:MODE FIXed; SOURce:FREQuency:MODE FIXed;
  VOLTage:MODE STEP; VOLTage:TRIGgered X`` logo depois de um comando "pesado"
  (``SOURce:MODE ACDC``+``OFFSet``, troca para CSINe) é DESCARTADA ou é
  aplicada e REVERTIDA depois? Ler de volta após cada write resolve?

Segurança (não negociável):
* ``AmetekMX30.connect()`` manda ``OUTPut:STATe OFF`` antes de qualquer outra
  coisa; este script confirma OFF por leitura no início, entre os testes e no
  fim, e aborta (com ``safe_shutdown``) se a saída aparecer ligada.
* Nunca envia ``OUTPut ON`` (o interlock de software ``authorize_output`` nunca
  é liberado, e ``_w`` recusa qualquer comando de OUTPut que não seja OFF).
* Toda tensão escrita é <= ``TENSAO_MAX_TESTE_V`` (5 V), muito abaixo de
  ``max_voltage_rms`` — nada é energizado, só registradores de programação.

Rodada 2 (RELATORIO_FINAL §8 de 2026-09-21, pendências listadas em
docs/analise-2026-09-30/ANALISE.md):

* T10/T11 (``opcoes``) — ``*OPT?``, ``SYSTem:CONFigure?``, ``*OPC?`` isolado.
* T12 (``limite``) — ``SOURce:VOLTage:HIGH`` limita rms ou pico?
* T14 (``pos_trava``) — só consultas, logo após religar uma fonte travada
  (roda ANTES de qualquer outro comando quando selecionado).
* O T7 (tempo de ``TRACe:DATA``) foi REMOVIDO: consultar logo após
  ``TRACe:DATA`` travou a fonte em 2026-09-30 15:33 (``--flash`` recusa).

Uso (com a CLI da bancada FECHADA, para liberar a COM10):

    env\\Scripts\\python.exe scripts\\diag_nativo_output_off.py            (opcoes + limite)
    env\\Scripts\\python.exe scripts\\diag_nativo_output_off.py --so pos_trava
    env\\Scripts\\python.exe scripts\\diag_nativo_output_off.py --so estado,pulso,resolucao,rajada

Os testes da rodada 1 (``estado``, ``pulso``, ``resolucao``, ``rajada``)
continuam disponíveis por ``--so``, mas desde a correção do N1
``AmetekMX30.write()`` espera a fonte consumir cada comando (``*ESR?``): as
"rajadas" agora medem o comportamento SINCRONIZADO, e o prelúdio ``_esr`` não
vê mais o bit OPC (o próprio sincronismo lê e zera o *ESR).

Saídas em ``logs/``: ``diag_nativo-<ts>.log`` (resumo legível),
``diag_nativo-<ts>-scpi.log`` (transcrição com respostas) e
``diag_nativo-<ts>.json`` (tudo, para análise).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Tuple

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "logica"))

import ametek_orm  # noqa: E402
from ametek_orm import AmetekMX30, CommunicationError  # noqa: E402

PORTA = "COM10"
BAUD = 115_200
TENSAO_MAX_TESTE_V = 5.0
REPETICOES_N1 = 3
# (prelúdio, rajada). "_esr": o comando pesado vai com ";*OPC" na MESMA
# mensagem e o script espera o bit OPC do *ESR (manual p. 136) — hoje o código
# manda "*WAI" seguido de outro comando, e o manual (p. 142) diz que "*WAI can
# be aborted by sending any other command after the *WAI command".
COMBINACOES_T3 = [
    (p, r)
    for p in ("nenhum", "acdc", "csine")
    for r in ("rajada4", "rajada2_sem_func_freq", "confirmada")
] + [("acdc_esr", "rajada4"), ("csine_esr", "rajada4")]

logger = logging.getLogger("diag_nativo")


class DiagnosticoAbortado(RuntimeError):
    pass


class Diag:
    def __init__(self, fonte: AmetekMX30):
        self.fonte = fonte
        self.t0 = time.monotonic()
        self.resultados: dict = {}
        self.ultimo_estado_saida = ""

    # ---- primitivas -----------------------------------------------------
    def _w(self, comando: str) -> None:
        texto = comando.strip().upper()
        if texto.startswith("OUTP") and not re.search(r"\bOFF\b|\b0\b", texto):
            raise DiagnosticoAbortado(f"Recusado: {comando!r} poderia ligar a saída")
        for numero in re.findall(r"(?:VOLT[A-Z:]*|OFFS[A-Z]*)\s+([-+0-9.eE]+)", texto):
            if abs(float(numero)) > TENSAO_MAX_TESTE_V:
                raise DiagnosticoAbortado(f"Recusado: {comando!r} passa de {TENSAO_MAX_TESTE_V} V")
        self.fonte.write(comando)

    def _q(self, comando: str) -> str:
        try:
            return self.fonte.query(comando).strip()
        except CommunicationError as exc:
            return f"<sem resposta: {exc}>"

    def _erros(self):
        try:
            return self.fonte.check_errors()
        except Exception as exc:  # noqa: BLE001 - diagnóstico
            return [("?", f"falha lendo fila: {exc}")]

    def _t(self) -> float:
        return round(time.monotonic() - self.t0, 3)

    def garantir_saida_desligada(self, contexto: str) -> None:
        estado = self._q("OUTPut:STATe?").upper()
        self.ultimo_estado_saida = estado
        if estado not in {"0", "OFF"}:
            try:
                self.fonte.safe_shutdown()
            finally:
                raise DiagnosticoAbortado(
                    f"OUTPUT lido como {estado!r} em '{contexto}' — abortado. CONFIRME OUTPUT OFF NO PAINEL."
                )

    def estado_pulso(self) -> dict:
        return {
            c: self._q(c)
            for c in (
                "VOLTage:MODE?", "VOLTage:TRIGgered?", "PULSe:WIDTh?", "PULSe:PERiod?",
                "PULSe:DCYCle?", "PULSe:HOLD?", "PULSe:COUNt?",
            )
        }

    def estado_modos(self) -> dict:
        return {
            c: self._q(c)
            for c in ("VOLTage:MODE?", "VOLTage:TRIGgered?", "FUNCtion:MODE?", "SOURce:FREQuency:MODE?")
        }

    def reset_modos(self, tensao_trig: float = 3.0) -> None:
        for c in ("ABORt", "*CLS", "FUNCtion:MODE FIXed", "VOLTage:MODE FIXed",
                  "SOURce:FREQuency:MODE FIXed", f"VOLTage:TRIGgered {tensao_trig}"):
            self._w(c)
        self._q("VOLTage:MODE?")  # ponto de sincronismo: a fonte responde só depois de processar o anterior

    # ---- T0 -------------------------------------------------------------
    def t0_estado_inicial(self) -> None:
        logger.info("T0 — estado inicial (nada escrito ainda além de OUTPut OFF)")
        estado = {"idn": self.fonte.idn, **self.estado_pulso(), **self.estado_modos(),
                  "TRIGger:STATe?": self._q("TRIGger:STATe?"), "erros": self._erros()}
        # Manual p. 105 documenta a query como "[SOURce:]PERiod?" (provável
        # erro de digitação de PULSe:PERiod?) — registra qual das duas existe.
        estado["PERiod? (forma do manual)"] = self._q("PERiod?")
        estado["erros_apos_PERiod?"] = self._erros()
        # Queries vão para a fase de INSTrument:NSELect se o acoplamento não
        # for ALL (manual p. 148); configure_safe_baseline() sempre manda ALL.
        self._w("INSTrument:COUPle ALL")
        self.resultados["T0"] = estado
        for k, v in estado.items():
            logger.info("  %-24s %s", k, v)

    # ---- T1: PULSe ------------------------------------------------------
    def t1_pulso(self) -> None:
        logger.info("T1 — acoplamento PULSe (N2)")
        casos = [
            ("a) só WIDTh 0.06 (como o código faz hoje)",
             ["VOLTage:MODE PULSe", "VOLTage:TRIGgered 5", "PULSe:WIDTh 0.06"]),
            ("b) COUNt 1, PERiod 0.2, WIDTh 0.06",
             ["PULSe:COUNt 1", "PULSe:PERiod 0.2", "PULSe:WIDTh 0.06"]),
            ("c) WIDTh 0.1 com PERiod 0.2", ["PULSe:WIDTh 0.1"]),
            ("d) WIDTh 0.3 > PERiod 0.2", ["PULSe:WIDTh 0.3"]),
            ("e) ordem do exemplo do manual: WIDTh 0.06 e depois PERiod 0.2",
             ["PULSe:PERiod 1", "PULSe:WIDTh 0.06", "PULSe:PERiod 0.2"]),
        ]
        saida = []
        self.reset_modos()
        for nome, comandos in casos:
            for c in comandos:
                self._w(c)
            estado = self.estado_pulso()
            erros = self._erros()
            saida.append({"caso": nome, "comandos": comandos, "lido": estado, "erros": erros})
            logger.info("  %s", nome)
            logger.info("     lido: %s", estado)
            if erros:
                logger.info("     ERROS: %s", erros)
        self.reset_modos()
        self.resultados["T1"] = saida

    # ---- T2: resolução --------------------------------------------------
    def t2_resolucao(self) -> None:
        logger.info("T2 — resolução de VOLTage:TRIGgered (N3)")
        saida = []
        self._w("VOLTage:MODE STEP")
        for valor in (2.7367107, 2.75, 2.74, 2.76, 4.96, 4.999):
            self._w(f"VOLTage:TRIGgered {valor}")
            lido = self._q("VOLTage:TRIGgered?")
            saida.append({"escrito": valor, "lido": lido, "erros": self._erros()})
            logger.info("  escrito %-10s lido %s", valor, lido)
        self.reset_modos()
        self.resultados["T2"] = saida

    # ---- T3: rajada após comando pesado --------------------------------
    def _aguardar_opc(self, timeout_s: float = 10.0) -> dict:
        """Manual p. 136: ``*OPC`` tem de estar NA MESMA mensagem do comando
        monitorado; o bit 0 (OPC) do *ESR sobe quando ele termina. Polling do
        registrador (condição), não espera fixa. Mede quanto a troca leva."""
        inicio = time.monotonic()
        leituras = []
        while time.monotonic() - inicio < timeout_s:
            bruto = self._q("*ESR?")
            leituras.append(bruto)
            try:
                if int(float(bruto)) & 1:
                    return {"opc": True, "s": round(time.monotonic() - inicio, 3), "leituras": len(leituras)}
            except ValueError:
                pass
            time.sleep(0.02)
        return {"opc": False, "s": round(time.monotonic() - inicio, 3), "ultimas": leituras[-3:]}

    def _preludio(self, tipo: str) -> dict:
        info: dict = {}
        if tipo == "acdc":
            self._w("SOURce:MODE ACDC")
            self._w("*WAI")
            self._w("SOURce:VOLTage:OFFSet 1")
        elif tipo == "csine":
            self._w("SOURce:FUNCtion:SHAPe CSINusoid")
            self._w("*WAI")
            self._w("SOURce:FUNCtion:SHAPe:CSINusoid 5")
            self._w("*WAI")
        elif tipo == "acdc_esr":
            self._w("*CLS")
            self._w("SOURce:MODE ACDC;*OPC")
            info["MODE ACDC"] = self._aguardar_opc()
            self._w("SOURce:VOLTage:OFFSet 1;*OPC")
            info["OFFSet"] = self._aguardar_opc()
        elif tipo == "csine_esr":
            self._w("*CLS")
            self._w("SOURce:FUNCtion:SHAPe CSINusoid;*OPC")
            info["SHAPe CSINusoid"] = self._aguardar_opc()
            self._w("SOURce:FUNCtion:SHAPe:CSINusoid 5;*OPC")
            info["CSINusoid 5"] = self._aguardar_opc()
        return info

    def _desfaz_preludio(self, tipo: str) -> None:
        tipo = tipo.replace("_esr", "")
        if tipo == "acdc":
            self._w("SOURce:VOLTage:OFFSet 0")
            self._w("SOURce:MODE AC")
            self._w("*WAI")
        elif tipo == "csine":
            self._w("SOURce:FUNCtion:SHAPe SINusoid")
            self._w("*WAI")
        self._q("VOLTage:MODE?")

    def _rajada(self, tipo: str) -> dict:
        passos = {}
        if tipo == "rajada4":
            for c in ("FUNCtion:MODE FIXed", "SOURce:FREQuency:MODE FIXed",
                      "VOLTage:MODE STEP", "VOLTage:TRIGgered 5"):
                self._w(c)
        elif tipo == "rajada2_sem_func_freq":
            for c in ("VOLTage:MODE STEP", "VOLTage:TRIGgered 5"):
                self._w(c)
        elif tipo == "confirmada":
            for c, consulta in (("FUNCtion:MODE FIXed", "FUNCtion:MODE?"),
                                ("SOURce:FREQuency:MODE FIXed", "SOURce:FREQuency:MODE?"),
                                ("VOLTage:MODE STEP", "VOLTage:MODE?"),
                                ("VOLTage:TRIGgered 5", "VOLTage:TRIGgered?")):
                self._w(c)
                passos[c] = {"t": self._t(), "lido": self._q(consulta)}
        return passos

    def t3_rajada(self) -> None:
        logger.info("T3 — rajada STEP após comando pesado (N1), %d repetições", REPETICOES_N1)
        saida = []
        for preludio, rajada in COMBINACOES_T3:
                for rep in range(1, REPETICOES_N1 + 1):
                    self.reset_modos(tensao_trig=3.0)
                    t_ini = self._t()
                    sincronismo = self._preludio(preludio)
                    passos = self._rajada(rajada)
                    erros_logo = self._erros()
                    imediato = self.estado_modos()
                    time.sleep(1.0)  # medição: o estado muda DEPOIS? (não é contorno)
                    depois_1s = self.estado_modos()
                    erros_1s = self._erros()
                    ok = (imediato["VOLTage:MODE?"].upper().startswith("STEP")
                          and _float(imediato["VOLTage:TRIGgered?"]) == 5.0)
                    ok_1s = (depois_1s["VOLTage:MODE?"].upper().startswith("STEP")
                             and _float(depois_1s["VOLTage:TRIGgered?"]) == 5.0)
                    registro = {
                        "preludio": preludio, "rajada": rajada, "rep": rep, "t_inicio": t_ini,
                        "sincronismo_esr": sincronismo,
                        "passos_confirmados": passos, "imediato": imediato, "erros_logo": erros_logo,
                        "depois_1s": depois_1s, "erros_1s": erros_1s, "ok": ok, "ok_1s": ok_1s,
                    }
                    saida.append(registro)
                    logger.info(
                        "  %-9s %-22s rep %d: imediato=%s depois_1s=%s ok=%s ok_1s=%s erros=%s%s%s",
                        preludio, rajada, rep, imediato, depois_1s, ok, ok_1s, erros_logo,
                        f" passos={passos}" if passos else "",
                        f" esr={sincronismo}" if sincronismo else "",
                    )
                    self._desfaz_preludio(preludio)
                    self.garantir_saida_desligada(f"T3 {preludio}/{rajada}/{rep}")
        self.reset_modos()
        self.resultados["T3"] = saida
        logger.info("T3 — resumo (STEP e TRIG=5 lidos de volta):")
        for preludio, rajada in COMBINACOES_T3:
            linhas = [r for r in saida if r["preludio"] == preludio and r["rajada"] == rajada]
            logger.info(
                "  %-9s %-22s imediato %d/%d   após 1 s %d/%d", preludio, rajada,
                sum(r["ok"] for r in linhas), len(linhas), sum(r["ok_1s"] for r in linhas), len(linhas),
            )


    # ---- T10/T11: opções e configuração ---------------------------------
    def t10_opcoes(self) -> None:
        """*OPT? e SYST:CONF? (manual p. 119/137): Series I ou II define o
        limite de pontos de lista; *OPC? isolado responde nesta Rev. 5.53?
        (v1.7 disse que não; *OPC na mesma mensagem funciona — T3 acima)."""
        logger.info("T10/T11 — opções instaladas, configuração, *OPC?")
        saida = {
            "*OPT?": self._q("*OPT?"),
            "SYSTem:CONFigure?": self._q("SYSTem:CONFigure?"),
            "erros_1": self._erros(),
        }
        inicio = time.monotonic()
        saida["*OPC?"] = self._q("*OPC?")
        saida["*OPC?_s"] = round(time.monotonic() - inicio, 3)
        saida["erros_2"] = self._erros()
        for k, v in saida.items():
            logger.info("  %-20s %s", k, v)
        self.resultados["T10"] = saida

    # ---- T12: VOLTage:HIGH é limite de rms ou de pico? ------------------
    def t12_limite_high(self) -> None:
        """Manual p. ~110: "VOLTage:HIGH ... programs the maximum RMS voltage
        that the power source will accept" (unidade V rms). O código manda
        ``SOURce:VOLTage:HIGH 415.8`` como se fosse PICO (``voltage_high_vp``).
        Teste com saída OFF e tudo <= 5 V: HIGH = 4 V; programa 2,5 / 3,5 /
        4,5 Vrms (picos 3,5 / 4,9 / 6,4 V). 3,5 aceito e 4,5 recusado ⇒ rms;
        3,5 recusado ⇒ pico. Restaura HIGH e a tensão imediata no fim."""
        logger.info("T12 — SOURce:VOLTage:HIGH: limite de rms ou de pico?")
        high_original = self._q("SOURce:VOLTage:HIGH?")
        tensao_original = self._q("SOURce:VOLTage:LEVel:IMMediate:AMPLitude?")
        saida = {"HIGH_original": high_original, "tensao_original": tensao_original, "casos": []}
        logger.info("  HIGH original=%s, tensão imediata original=%s", high_original, tensao_original)
        try:
            self._w("SOURce:VOLTage:HIGH 4")
            saida["HIGH_apos_4"] = self._q("SOURce:VOLTage:HIGH?")
            saida["erros_HIGH"] = self._erros()
            for vrms in (2.5, 3.5, 4.5):
                self._w("SOURce:VOLTage 0")
                self._erros()
                self._w(f"SOURce:VOLTage {vrms}")
                lido = self._q("SOURce:VOLTage:LEVel:IMMediate:AMPLitude?")
                erros = self._erros()
                caso = {"vrms": vrms, "pico_v": round(vrms * 2 ** 0.5, 2), "lido": lido, "erros": erros}
                saida["casos"].append(caso)
                logger.info("  programado %.1f Vrms (pico %.2f V): lido %s, erros %s", vrms, caso["pico_v"], lido, erros)
        finally:
            self._w("SOURce:VOLTage 0")
            self._restaurar_high(high_original)
            saida["HIGH_restaurado"] = self._q("SOURce:VOLTage:HIGH?")
            saida["erros_restauracao"] = self._erros()
            logger.info("  HIGH restaurado para %s (erros %s)", saida["HIGH_restaurado"], saida["erros_restauracao"])
        self.resultados["T12"] = saida

    def _restaurar_high(self, valor_lido: str) -> None:
        """Única escrita acima de TENSAO_MAX_TESTE_V permitida: devolver o
        VOLTage:HIGH ao valor EXATO lido do instrumento no início do T12 (é
        um limite de programação, não energiza nada; saída continua OFF). Se
        a leitura inicial falhou, não escreve nada: a próxima conexão da
        bancada roda configure_safe_baseline(), que reprograma o HIGH."""
        try:
            valor = float(valor_lido)
        except (TypeError, ValueError):
            logger.warning("  HIGH original ilegível (%r): fica para configure_safe_baseline()", valor_lido)
            return
        self.garantir_saida_desligada("antes de restaurar VOLTage:HIGH")
        self.fonte.write(f"SOURce:VOLTage:HIGH {valor:.8g}")

    # O T7 (tempo real de TRACe:DATA) foi REMOVIDO depois de rodar uma vez, em
    # 2026-09-30 15:33: ele consultava *ESR? logo após um TRACe:DATA e a fonte
    # parou de responder a QUALQUER comando (58 s de silêncio até o fim do
    # script) — exatamente o que clear_all_traces()/program_capture() avisam
    # ("não consulte durante a gravação da Flash"). Não existe medida segura:
    # a única forma de saber que a gravação acabou é consultar, e consultar
    # durante a gravação trava a interface. Ver ANALISE.md, "T7/T14".

    # ---- T15: *OPC? serve de sincronismo para write()? -------------------
    def _tempo_de(self, consulta: str) -> Tuple[str, float]:
        inicio = time.monotonic()
        resposta = self._q(consulta)
        return resposta, round(time.monotonic() - inicio, 3)

    def t15_opc(self) -> None:
        """Decide se ``AMETEK_SINCRONISMO=OPC`` é seguro. *OPC? espera as
        operações pendentes terminarem (manual p. 173, "except transients").
        Três situações, saída OFF e tudo <= 5 V, SEM gravar na Flash:
        (a) repouso; (b) logo após trocar a forma (comando pesado, enviado cru
        para o sincronismo do write() não consumir a espera); (c) logo após
        INITiate com um STEP armado e SEM *TRG — se o *OPC? esperar o
        transiente, isto não responde (seria um impasse no arm()). Depois de
        (c), ABORt e confere que a fonte volta a responder."""
        logger.info("T15 — *OPC? como sincronismo (repouso, após troca de forma, após INIT)")
        saida: dict = {}
        self.reset_modos()
        saida["a_repouso"] = self._tempo_de("*OPC?")
        self.fonte._raw_write("SOURce:FUNCtion:SHAPe CSINusoid")
        saida["b_apos_troca_de_forma"] = self._tempo_de("*OPC?")
        saida["b_erros"] = self._erros()
        self.fonte._raw_write("SOURce:FUNCtion:SHAPe SINusoid")
        saida["b_volta_senoide"] = self._tempo_de("*OPC?")
        self.reset_modos()
        for c in ("VOLTage:MODE STEP", "VOLTage:TRIGgered 3", "TRIGger:SOURce BUS"):
            self._w(c)
        saida["c_estado_antes"] = self._q("TRIGger:STATe?")
        self.fonte._raw_write("INITiate:IMMediate")
        saida["c_apos_init"] = self._tempo_de("*OPC?")
        saida["c_estado_armado"] = self._q("TRIGger:STATe?")
        self.fonte._raw_write("ABORt")
        saida["c_apos_abort_idn"] = self._tempo_de("*IDN?")
        saida["c_estado_final"] = self._q("TRIGger:STATe?")
        saida["c_erros"] = self._erros()
        self.reset_modos()
        resposta_init = saida["c_apos_init"][0].strip()
        if resposta_init == "1":
            conclusao = "OPC respondeu '1' após INIT: não espera o transiente — seguro"
        elif resposta_init == "0":
            # Bancada 2026-09-30 15:48: a Rev. 5.53 NÃO segura a resposta do
            # *OPC? (fora do padrão IEEE 488.2): devolve na hora 0/1 = "há
            # operação pendente?". Não trava, mas também não sincroniza mais que
            # o *ESR?, e cada arm() geraria um aviso "devolveu '0'".
            conclusao = ("OPC respondeu '0' na hora após INIT (não espera; só informa pendência) "
                         "— sem ganho sobre ESR: manter ESR")
        else:
            conclusao = f"OPC NÃO respondeu após INIT ({resposta_init!r}) — manter ESR"
        saida["conclusao"] = conclusao
        for k, v in saida.items():
            logger.info("  %-24s %s", k, v)
        self.resultados["T15"] = saida

    # ---- T14: leituras logo após religar a fonte depois de uma trava ----
    def t14_pos_trava(self) -> None:
        """RELATORIO_FINAL §8 T14: depois de religar a fonte travada, ler
        ANTES de qualquer outro comando (além do ``OUTPut:STATe OFF`` que
        ``connect()`` sempre manda primeiro) a fila de erros e os registradores
        de estado. Só consultas."""
        logger.info("T14 — estado da fonte logo após religar (só consultas)")
        saida = {c: self._q(c) for c in ("*ESR?", "STATus:QUEStionable:CONDition?",
                                          "STATus:OPERation:CONDition?", "*STB?")}
        saida["SYSTem:ERRor? (fila inteira)"] = self._erros()
        for k, v in saida.items():
            logger.info("  %-32s %s", k, v)
        self.resultados["T14"] = saida


def _float(texto: str) -> float:
    try:
        return round(float(texto), 6)
    except (TypeError, ValueError):
        return float("nan")


TESTES = {
    "estado": "t0_estado_inicial",
    "pulso": "t1_pulso",
    "resolucao": "t2_resolucao",
    "rajada": "t3_rajada",
    "opcoes": "t10_opcoes",
    "limite": "t12_limite_high",
    "pos_trava": "t14_pos_trava",
    "opc": "t15_opc",
}
PADRAO = ("opcoes", "limite")


def _selecionar(argv=None):
    parser = argparse.ArgumentParser(description="Diagnóstico da AMETEK com OUTPUT OFF")
    parser.add_argument("--so", help=f"testes separados por vírgula ({', '.join(TESTES)}); padrão: {','.join(PADRAO)}")
    parser.add_argument("--flash", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.flash:
        parser.error(
            "o T7 (--flash) foi REMOVIDO: consultar a fonte logo após TRACe:DATA travou a "
            "interface em 2026-09-30 15:33 (ver docs/analise-2026-09-30/ANALISE.md)"
        )
    escolhidos = [t.strip() for t in args.so.split(",")] if args.so else list(PADRAO)
    desconhecidos = [t for t in escolhidos if t not in TESTES]
    if desconhecidos:
        parser.error(f"testes desconhecidos: {desconhecidos}")
    return escolhidos


def main(argv=None) -> int:
    escolhidos = _selecionar(argv)
    carimbo = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    pasta = RAIZ / "logs"
    pasta.mkdir(exist_ok=True)
    resumo = pasta / f"diag_nativo-{carimbo}.log"
    transcricao = pasta / f"diag_nativo-{carimbo}-scpi.log"

    formato = logging.Formatter("[%(asctime)s] %(message)s", "%H:%M:%S")
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    for handler in (logging.StreamHandler(sys.stdout), logging.FileHandler(resumo, encoding="utf-8")):
        handler.setFormatter(formato)
        raiz.addHandler(handler)
    scpi = logging.FileHandler(transcricao, encoding="utf-8")
    scpi.setFormatter(logging.Formatter("[%(asctime)s.%(msecs)03d] %(message)s", "%H:%M:%S"))
    ametek_orm.scpi_logger.setLevel(logging.DEBUG)
    ametek_orm.scpi_logger.addHandler(scpi)
    ametek_orm.scpi_logger.propagate = False

    logger.info("Diagnóstico nativo com OUTPUT OFF — testes %s — resumo em %s", escolhidos, resumo)
    fonte = AmetekMX30(PORTA, baudrate=BAUD, max_voltage_rms=10.0, max_peak_v=15.0)
    diag = Diag(fonte)
    codigo = 0
    try:
        if "pos_trava" in escolhidos:
            # T14: antes de QUALQUER outro comando (connect() já mandou só
            # OUTPut:STATe OFF e *IDN?).
            diag.t14_pos_trava()
            escolhidos = [n for n in escolhidos if n != "pos_trava"]
        diag.garantir_saida_desligada("início")
        # Queries vão para a fase de INSTrument:NSELect se o acoplamento não
        # for ALL (manual p. 148); configure_safe_baseline() sempre manda ALL.
        diag._w("INSTrument:COUPle ALL")
        for nome in escolhidos:
            getattr(diag, TESTES[nome])()
            diag.garantir_saida_desligada(f"após {nome}")
    except DiagnosticoAbortado as exc:
        logger.error("ABORTADO: %s", exc)
        codigo = 2
    except Exception:  # noqa: BLE001
        logger.exception("Falha inesperada — confira OUTPUT OFF no painel")
        codigo = 1
    finally:
        try:
            diag._w("SOURce:FUNCtion:SHAPe SINusoid")
            diag._w("SOURce:MODE AC")
            diag.reset_modos()
        except Exception:  # noqa: BLE001
            logger.exception("Falha restaurando modos (a conexão seguinte roda configure_safe_baseline)")
        (pasta / f"diag_nativo-{carimbo}.json").write_text(
            json.dumps(diag.resultados, ensure_ascii=False, indent=1, default=str), encoding="utf-8",
        )
        diag.ultimo_estado_saida = diag._q("OUTPut:STATe?").upper()
        fonte.disconnect()  # ABORt + OUTPut OFF + tentativa de confirmação
        # disconnect() não levanta quando a confirmação falha por falta de
        # resposta (só loga) — então a frase final depende do que foi LIDO.
        # Antes, dizia "confirmado" mesmo com a fonte muda (15:34 de 30/09).
        estado_final = diag.ultimo_estado_saida
        if estado_final in {"0", "OFF"}:
            logger.info("Fim. OUTPUT OFF confirmado por leitura. Arquivos em %s", pasta)
        else:
            codigo = codigo or 3
            logger.error(
                "Fim. OUTPUT OFF **NÃO** CONFIRMADO por leitura (última resposta: %r). CONFIRME "
                "OUTPUT OFF NO PAINEL DA AMETEK. Arquivos em %s", estado_final, pasta,
            )
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
