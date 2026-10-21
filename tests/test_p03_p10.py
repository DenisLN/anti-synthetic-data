"""P-03 (sobressinal medido da 08) e P-10 (rota/nível da 05). Tudo offline e
simulado: FIXTURE sintética, nada aqui é evidência física nem fecha pendência."""
import dataclasses
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tests"))
sys.path.insert(0, str(RAIZ / "logica"))
import mestre  # noqa: E402
from test_offline import _BancadaFake, _load_experimento  # noqa: E402
from test_pendencias_fechamento import Base, fp, montar_sessao, r08, registro  # noqa: E402

T = np.arange(6000, dtype=np.float64) / 30_000.0


def experimento_08(f0=50.0):
    e = _load_experimento("08")
    e.fonte = mock.Mock(max_peak_v=415.8)
    e.osc = mock.Mock()
    e.config = dataclasses.replace(e.config, grid_frequency_hz=f0, sorteio_posicao=True, base_voltage_rms=127.0)
    return e


def medido_com_pico(e, f0, sobressinal):
    """Senoide + um pico de A(1 + sobressinal) na amostra prevista do impulso."""
    onda, parametros = e.gerar(T, f0, 0, np.random.default_rng(3))
    e.forma_para_bancada(onda, parametros, 0)
    previsto = int(e._indices_impulso(30_000.0, f0)[0])
    medido = np.sin(2.0 * np.pi * f0 * T)
    medido[previsto] += parametros["amplitude_bancada_pu"] * (1.0 + sobressinal)
    return medido, parametros["amplitude_bancada_pu"]


class Sobressinal08(unittest.TestCase):
    def test_mede_a_fracao_do_degrau_e_nao_recusa_a_captura(self):
        e = experimento_08()
        for alvo, acima in ((0.30, False), (0.55, False), (0.60, True)):
            medido, _a = medido_com_pico(e, 50.0, alvo)
            pos = e.conferir_posicao_do_evento(0, medido)
            self.assertAlmostEqual(pos["posicao"]["sobressinal_medido"], alvo, places=9)
            self.assertEqual(pos["posicao"]["sobressinal_limite"], 0.55)
            self.assertIs(pos["posicao"]["sobressinal_acima_do_limite"], acima if alvo != 0.55 else False)
            self.assertTrue(pos["ok"], pos)  # flag explícito, sem virar critério de recusa

    def test_vale_maior_que_o_pico_nao_vira_sobressinal(self):
        e = experimento_08()
        medido, a = medido_com_pico(e, 50.0, 0.3)
        previsto = int(e._indices_impulso(30_000.0, 50.0)[0])
        medido[previsto + 40] -= 2.0 * a  # vale com desvio absoluto maior que o do pico
        pos = e.conferir_posicao_do_evento(0, medido)["posicao"]
        self.assertAlmostEqual(pos["sobressinal_medido"], 0.3, places=9)
        self.assertNotIn("sobressinal_invalido", pos)

    def test_sobressinal_menor_que_menos_um_ou_nao_finito_e_invalido(self):
        e = experimento_08()
        medido, a = medido_com_pico(e, 50.0, 0.3)
        medido[:] = np.sin(2.0 * np.pi * 50.0 * T)  # nenhum desvio positivo: -1 exato, ainda válido
        medido[0] -= 5.0 * a  # e um vale grande
        pos = e.conferir_posicao_do_evento(0, medido)["posicao"]
        self.assertGreaterEqual(pos["sobressinal_medido"], -1.0)
        medido[10] = np.nan
        pos = e.conferir_posicao_do_evento(0, medido)["posicao"]
        self.assertIsNone(pos["sobressinal_medido"])
        self.assertIs(pos["sobressinal_invalido"], True)

    def test_campos_antigos_da_posicao_ficam(self):
        e = experimento_08()
        medido, _ = medido_com_pico(e, 50.0, 0.4)
        pos = e.conferir_posicao_do_evento(0, medido)["posicao"]
        for chave in ("inicio_previsto_amostra", "pico_medido_amostra", "desvio_amostras",
                      "tolerancia_amostras", "desvio_pico_pu"):
            self.assertIn(chave, pos)

    def test_sem_amplitude_nao_inventa_sobressinal(self):
        e = experimento_08()
        pos = e.conferir_posicao_do_evento(0, np.sin(2.0 * np.pi * 50.0 * T))["posicao"]
        self.assertNotIn("sobressinal_medido", pos)

    def test_chega_ao_metadata_pela_validacao_fisica(self):
        e = experimento_08()
        medido, _ = medido_com_pico(e, 50.0, 0.4)
        bruto = np.zeros(8100)
        bruto[595:595 + 6000] = medido
        v = e._validar_fisicamente(0, T, 3, bruto, margem_antes=600, inicio_janela=595)
        self.assertAlmostEqual(v["posicao_evento"]["sobressinal_medido"], 0.4, places=9)


class P03Fechamento(Base):
    def com_sobressinal(self, valor):
        r = r08(1)
        r["validacao_fisica"]["posicao_evento"]["sobressinal_medido"] = valor
        return r

    def test_p03_le_o_campo_gravado_pela_coleta(self):
        for valor, status, resultado in ((0.40, "evidencia_suficiente", "ok"), (0.60, "reprovado", "falha")):
            item = self.agregar(montar_sessao(self.raiz, f"s{valor}", [self.com_sobressinal(valor)]))[0]["itens"]["P-03"]
            self.assertEqual(item["status"], status)
            c = self.criterio(item, "sobressinal_pu")
            self.assertEqual((c["resultado"], c["valor_medido"]), (resultado, valor))


class P03Pico(Base):
    def reg(self, sb, pico):
        r = r08(1, pico=pico)
        r["validacao_fisica"]["posicao_evento"]["sobressinal_medido"] = sb
        return r

    def item(self, nome, sb, pico):
        return self.agregar(montar_sessao(self.raiz, nome, [self.reg(sb, pico)]))[0]["itens"]["P-03"]

    def test_pico_acima_do_teto_reprova_o_mesmo_criterio(self):
        item = self.item("sp1", 0.30, 380.0)
        self.assertEqual(self.criterio(item, "sobressinal_pu")["resultado"], "falha")
        self.assertEqual(item["status"], "reprovado")

    def test_sobressinal_acima_de_045_exige_revisao_humana(self):
        item = self.item("sp2", 0.50, 300.0)
        c = self.criterio(item, "sobressinal_pu")
        self.assertEqual(c["resultado"], "aviso")
        self.assertIn("subestima", c["nota"])
        self.assertEqual(item["status"], "evidencia_suficiente")
        self.assertTrue(item["requer_revisao_humana"])
        ok = self.item("sp3", 0.40, 300.0)
        self.assertEqual(self.criterio(ok, "sobressinal_pu")["resultado"], "ok")


class Rota05(unittest.TestCase):
    def _classe05(self, perfil, **cfg):
        e = _load_experimento("05")
        e.config = dataclasses.replace(e.config, perfil=perfil, **cfg)
        return e

    def test_rota_por_nivel(self):
        lit = self._classe05("literatura")
        self.assertEqual([lit.rota_programacao(i) for i in range(5)], ["CSIN"] * 4 + ["TRACe"])
        norma = self._classe05("norma")
        self.assertEqual({norma.rota_programacao(i) for i in range(5)}, {"CSIN"})

    def test_rota_padrao_das_outras_classes(self):
        self.assertEqual(_load_experimento("06").rota_programacao(0), "TRACe")
        self.assertEqual(_load_experimento("02").rota_programacao(0), "nativa")

    def test_cinco_pontos_com_comandos_existentes(self):
        """`set perfil norma|literatura` + `set capturas 1` + `run 05` cobrem 2, 10, 15, 20 % (CSIN)
        e 30 % (TRACe); sem `set capturas` só roda o nível 0 do perfil."""
        niveis = {}
        for perfil in ("norma", "literatura"):
            e = self._classe05(perfil, capturas_override=1)
            _por_nivel, _n, total = e.dimensionar_capturas(False)
            self.assertEqual(total, 5)
            for _g, ci in e.plano_de_capturas(False):
                niveis[(perfil, e.NIVEIS_THD[ci])] = e.rota_programacao(ci)
        self.assertEqual(niveis[("norma", 0.02)], "CSIN")
        for n in (0.10, 0.15, 0.20):
            self.assertEqual(niveis[("literatura", n)], "CSIN")
        self.assertEqual(niveis[("literatura", 0.30)], "TRACe")
        sem = self._classe05("literatura", capturas_override=None)
        self.assertEqual(sem.dimensionar_capturas(False)[2], 1)


def r05(i, thd, rota=None, ok=True, perfil="literatura"):
    extra = {} if rota is None else {"rota_programacao": rota}
    return registro(f"05-{i:04d}", perfil=perfil, parametros={"thd": thd},
                    validacao_fisica={"ok": ok, "motivos": [], "thd_medida": thd, "thd_esperada": thd}, **extra)


NIVEIS = [(0.02, "CSIN"), (0.10, "CSIN"), (0.15, "CSIN"), (0.20, "CSIN"), (0.30, "TRACe")]


class P10Fechamento(Base):
    def item(self, regs, nome="s"):
        return self.agregar(montar_sessao(self.raiz, nome, regs))[0]["itens"]["P-10"]

    def test_cinco_pontos_com_rota_gravada(self):
        item = self.item([r05(i, n, r) for i, (n, r) in enumerate(NIVEIS, 1)])
        self.assertEqual(item["status"], "evidencia_suficiente")
        self.assertEqual(self.criterio(item, "rota_csin_vs_trace")["resultado"], "ok")
        self.assertEqual(self.criterio(item, "validacao_fisica_ok_por_nivel")["resultado"], "ok")

    def test_rota_errada_reprova(self):
        regs = [r05(i, n, r) for i, (n, r) in enumerate(NIVEIS, 1)]
        regs[4] = r05(5, 0.30, "CSIN")
        item = self.item(regs)
        self.assertEqual(self.criterio(item, "rota_csin_vs_trace")["resultado"], "falha")
        self.assertEqual(item["status"], "reprovado")

    def test_nivel_invalido_reprova_so_aquele_nivel(self):
        regs = [r05(i, n, r) for i, (n, r) in enumerate(NIVEIS, 1)]
        regs[1] = r05(2, 0.10, "CSIN", ok=False)
        item = self.item(regs)
        c = self.criterio(item, "validacao_fisica_ok_por_nivel")
        self.assertEqual(c["resultado"], "falha")
        self.assertEqual(c["valor_medido"]["0.1"]["com_validacao_ok"], 0)

    def test_metadata_antigo_sem_rota_infere_e_avisa(self):
        item = self.item([r05(i, n) for i, (n, _r) in enumerate(NIVEIS, 1)])
        self.assertEqual(self.criterio(item, "rota_csin_vs_trace")["resultado"], "aviso")

    def test_nivel_faltando_e_insuficiente(self):
        item = self.item([r05(i, n, r) for i, (n, r) in enumerate(NIVEIS[:4], 1)])
        self.assertEqual(item["status"], "insuficiente")


if __name__ == "__main__":
    unittest.main()
