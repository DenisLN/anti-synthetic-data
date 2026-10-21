"""Teste de bancada: passo final SINE interno elimina o "último ciclo mantido"?

Ao fim de uma lista a MX30 continua no último passo (último ciclo da TRACE).
`AmetekMX30(passo_final_sin=True)` acrescenta à lista um passo com a forma
interna SINE na tensão base (logica/ametek_orm.py, program_capture). Este
script roda a MESMA captura (classe 06 FLICKER, mesma seed) sem e com o passo
e mede o RMS por ciclo da margem final (os 50 ms depois da janela nominal) e a
identidade da janela rotulada. Reutiliza Bancada/ExperimentoWaveform de
logica/mestre.py; não escreve nenhum SCPI próprio.

    env\\Scripts\\python.exe scripts\\teste_passo_final_sin.py            # bancada
    env\\Scripts\\python.exe scripts\\teste_passo_final_sin.py --simulado # sem hardware

Bancada: pergunta o fator EXATO da probe de tensão, a tensão e a frequência, e
só energiza depois de digitar ENERGIZAR-PASSO-SIN (case-sensitive). Feche o MX
GUI e a CLI da bancada antes. Saída da fonte desligada no fim (Bancada.shutdown).
Resultados em resultados/passo_final_sin_<data>/.
"""
import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "logica"))

CONFIRMACAO = "ENERGIZAR-PASSO-SIN"
# Critérios do veredito (missão, item 4): margem final em 1,00 +- 0,01 pu e
# janela rotulada idêntica. Para "idêntica" fixo corr >= 0,999 e diferença
# máxima do RMS por ciclo <= 0,01 pu (escolha deste script, ajustável aqui).
TOL_MARGEM_PU = 0.01
CORR_MIN_JANELA = 0.999
TOL_JANELA_PU = 0.01


def rms_por_ciclo_pu(v_pu: np.ndarray, inicio: int, n_ciclo: int, n_ciclos: int) -> list:
    """RMS de cada ciclo inteiro em pu da tensão base RMS (v_pu está em pu do PICO)."""
    saida = []
    for k in range(n_ciclos):
        trecho = v_pu[inicio + k * n_ciclo : inicio + (k + 1) * n_ciclo]
        if trecho.size != n_ciclo:
            break
        saida.append(float(np.sqrt(np.mean(trecho ** 2)) * math.sqrt(2.0)))
    return saida


def analisar(registro_sem, registro_com, *, antes, pontos, depois, n_ciclo):
    """Margem final e janela rotulada das duas capturas (arrays em pu do pico)."""
    fim = antes + pontos
    n_margem = depois // n_ciclo
    janela = slice(antes, fim)
    n_janela = pontos // n_ciclo
    corr = float(np.corrcoef(registro_sem[janela], registro_com[janela])[0, 1])
    j_sem = rms_por_ciclo_pu(registro_sem, antes, n_ciclo, n_janela)
    j_com = rms_por_ciclo_pu(registro_com, antes, n_ciclo, n_janela)
    return {
        "margem_sem": rms_por_ciclo_pu(registro_sem, fim, n_ciclo, n_margem),
        "margem_com": rms_por_ciclo_pu(registro_com, fim, n_ciclo, n_margem),
        "janela_corr": corr,
        "janela_rms_sem": j_sem,
        "janela_rms_com": j_com,
        "janela_dif_max_pu": float(np.max(np.abs(np.array(j_sem) - np.array(j_com)))),
    }


def imprimir(resultado: dict) -> bool:
    ms, mc = resultado["margem_sem"], resultado["margem_com"]
    print("\nRMS por ciclo da margem final (pu da tensao base RMS):")
    print("  ciclo |  sem passo |  com passo SIN")
    for k in range(len(ms)):
        print(f"  {k + 1:5d} | {ms[k]:10.4f} | {mc[k]:10.4f}")
    print(f"\nJanela rotulada: correlacao sem x com = {resultado['janela_corr']:.5f}; "
          f"maior diferenca do RMS por ciclo = {resultado['janela_dif_max_pu']:.4f} pu")
    margem_ok = bool(mc) and all(abs(x - 1.0) <= TOL_MARGEM_PU for x in mc)
    janela_ok = (resultado["janela_corr"] >= CORR_MIN_JANELA
                 and resultado["janela_dif_max_pu"] <= TOL_JANELA_PU)
    print(f"Margem com passo em 1,00 +- {TOL_MARGEM_PU}: {'SIM' if margem_ok else 'NAO'}")
    print(f"Janela identica (corr >= {CORR_MIN_JANELA}, dif <= {TOL_JANELA_PU} pu): "
          f"{'SIM' if janela_ok else 'NAO'}")
    return margem_ok and janela_ok


def carregar_bench_config() -> None:
    """Valores fixos da bancada, lidos de scripts/bench_config.ps1 (sem duplicá-los)."""
    for linha in (RAIZ / "scripts" / "bench_config.ps1").read_text(encoding="utf-8").splitlines():
        m = re.match(r'\s*\$env:(\w+)\s*=\s*"(.*)"\s*$', linha)
        if m and m.group(2).strip() and m.group(1) not in {"ARM_OUTPUT", "BENCH_MODE", "BASE_VOLTAGE_RMS"}:
            os.environ.setdefault(m.group(1), m.group(2))


def perguntar_float(texto: str) -> float:
    valor = float(input(texto).strip().replace(",", "."))
    if not math.isfinite(valor) or not valor > 0:
        raise SystemExit("Valor invalido; nao e seguro continuar.")
    return valor


def modo_simulado(args) -> int:
    """Sem hardware: mostra os comandos LIST sem/com o passo e exercita a análise."""
    import mestre
    from ametek_orm import AmetekMX30
    import importlib.util

    spec = importlib.util.spec_from_file_location("exp06", RAIZ / "experimentos_waveform" / f"{args.classe}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    config = mestre._build_config()
    exp = modulo.Experimento(mestre.Bancada(None, None, config))
    t = np.arange(config.points) / config.fs_hz
    forma, _ = exp.gerar(t, config.grid_frequency_hz, 0, np.random.default_rng(exp.seed_da_captura(0)))
    n = round(config.fs_hz / config.grid_frequency_hz)
    antes, depois = 600, 1500
    registros = {}
    for com in (False, True):
        fonte = AmetekMX30(simulated=True, max_voltage_rms=300.0, max_peak_v=415.8, passo_final_sin=com)
        fonte.program_capture(forma, base_voltage_rms=config.base_voltage_rms,
                              frequency_hz=config.grid_frequency_hz)
        print(f"\n--- passo_final_sin={com} ---")
        for c in fonte.command_log:
            if c.startswith(("SOURce:LIST:FUNCtion:SHAPe ", "SOURce:LIST:DWELl ", "SOURce:LIST:REPeat ")):
                print(c[:150] + ("..." if len(c) > 150 else ""))
            elif c.startswith("SOURce:LIST:VOLTage "):
                print("SOURce:LIST:VOLTage ...," + c.split(",")[-1])
        # Registro sintetico: antes (0) + janela + margem (ultimo ciclo mantido ou SIN).
        plano = fonte.ultima_programacao
        resto = np.tile(plano.margem_final_pu(), math.ceil(depois / n))[:depois]
        registros[com] = np.concatenate([np.zeros(antes), plano.programada_pu(), resto])
    print("\n[SIMULADO] Registros sinteticos; so valida a analise, NAO e medida de bancada.")
    eficaz = imprimir(analisar(registros[False], registros[True], antes=antes, pontos=config.points,
                               depois=depois, n_ciclo=n))
    return 0 if eficaz else 2


def modo_bancada(args) -> int:
    print(__doc__.split("\n\n")[0])
    print("\nATENCAO: este teste ENERGIZA a fonte AMETEK (tensao informada abaixo).")
    probe = perguntar_float("Fator EXATO da probe de tensao instalada (ex.: 10, 100): ")
    vrms = perguntar_float("Tensao RMS fase-neutro do teste em V (maximo 270): ")
    freq = perguntar_float("Frequencia do teste em Hz (ex.: 60, 50): ")
    if vrms > 270.0:
        raise SystemExit("Tensao recusada: a bancada aceita no maximo 270 Vrms fase-neutro.")
    print(f"\nProbe {probe:g}x, {vrms:g} Vrms, {freq:g} Hz, classe {args.classe}, "
          f"{args.repeticoes} repeticao(oes) de (sem, com).")
    if input(f"Digite {CONFIRMACAO}: ") != CONFIRMACAO:
        print("Cancelado: confirmacao nao corresponde (comparacao sensivel a maiusculas).")
        return 1

    carregar_bench_config()
    os.environ.update({
        "BENCH_MODE": "1", "ARM_OUTPUT": "YES", "PYTHONUTF8": "1",
        "VOLTAGE_PROBE_ATTENUATION": f"{probe:g}", "BASE_VOLTAGE_RMS": f"{vrms:g}",
        "GRID_FREQUENCY_HZ": f"{freq:g}", "SOURCE_VOLTAGE_RANGE_RMS": "300",
        "EUT_MAX_VOLTAGE_RMS": "300", "EUT_MAX_PEAK_V": "415.8",
    })
    import mestre
    from sinais import tempo

    pasta = RAIZ / "resultados" / time.strftime("passo_final_sin_%Y-%m-%d_%H-%M-%S")
    pasta.mkdir(parents=True, exist_ok=True)
    print(f"Resultados em {pasta}")

    with mestre.Bancada.from_env() as bancada:
        fonte, osc, config = bancada.fonte, bancada.osc, bancada.config
        script = next(p for p in mestre._experiment_scripts() if p.stem == args.classe)
        exp = bancada._carregar_classe_experimento(script)(bancada)
        if not hasattr(exp, "_capturar_real") or exp.grava_trace(0) is False:
            raise SystemExit(f"Classe {args.classe} nao e uma classe TRACE.")
        t = tempo(config)
        antes, depois, pontos = exp._calcular_margem(
            captura_fisica=True, config_points=config.points, fs_hz=config.fs_hz)
        exp._pontos_efetivos_captura_atual = pontos
        osc.configure_acquisition(
            sample_rate_hz=config.fs_hz, points=pontos, duration_s=pontos / config.fs_hz,
            pre_trigger_s=exp.pre_trigger_s + antes / config.fs_hz)
        exp._preparar_acquisicao_real()
        seed = exp.seed_da_captura(0)
        n_ciclo = round(config.fs_hz / config.grid_frequency_hz)
        registros = {False: [], True: []}
        try:
            for rep in range(args.repeticoes):
                for com in (False, True):
                    fonte.passo_final_sin = com
                    print(f"\nCaptura {rep + 1}/{args.repeticoes}: passo_final_sin={com}")
                    _, v_pu, _, _ = exp._capturar_real(0, t, np.random.default_rng(seed))
                    registros[com].append(np.asarray(v_pu, dtype=np.float64))
        finally:
            fonte.passo_final_sin = False
            fonte.restaurar_forma_e_modo_padrao()

    np.savez(pasta / "registros.npz", sem=np.array(registros[False]), com=np.array(registros[True]))
    todos_ok = True
    resultados = []
    for rep in range(args.repeticoes):
        print(f"\n===== repeticao {rep + 1} =====")
        r = analisar(registros[False][rep], registros[True][rep], antes=antes, pontos=config.points,
                     depois=depois, n_ciclo=n_ciclo)
        resultados.append(r)
        todos_ok &= imprimir(r)
    codigo = mestre.info_do_codigo(recalcular=True)  # procedência: scripts/fechar_pendencias.py P-18 a exige
    (pasta / "resultado.json").write_text(json.dumps(
        {"vrms": vrms, "freq_hz": freq, "probe": probe, "classe": args.classe, "seed": seed,
         "simulado": False, "modo": "bancada", "git_commit": codigo.get("git_commit"),
         "git_sujo": codigo.get("git_sujo"), "versao_codigo": codigo.get("versao_codigo"),
         "resultados": resultados}, indent=1), encoding="utf-8")
    print(f"\nVEREDITO: {'EFICAZ' if todos_ok else 'NAO EFICAZ (ou inconclusivo)'} "
          f"em {args.repeticoes} repeticao(oes). Entregue tambem logs\\ mais recente.")
    return 0 if todos_ok else 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--simulado", action="store_true", help="sem hardware: comandos e analise")
    ap.add_argument("--classe", default="06", help="classe TRACE (padrao 06 FLICKER)")
    ap.add_argument("--repeticoes", type=int, default=1, help="pares (sem, com) a capturar")
    args = ap.parse_args()
    if args.repeticoes < 1:
        ap.error("--repeticoes deve ser >= 1")
    if args.classe not in {p.stem for p in (RAIZ / "experimentos_waveform").glob("[0-9][0-9].py")}:
        ap.error("--classe deve identificar um experimento waveform existente")
    return modo_simulado(args) if args.simulado else modo_bancada(args)


if __name__ == "__main__":
    sys.exit(main())
