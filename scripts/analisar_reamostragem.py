#!/usr/bin/env python3
"""P28: compara offline np.interp com FIR passa-baixas + np.interp.

Não acessa instrumentos e nunca modifica a captura. A alternativa é uma
referência de análise, não uma alteração do ORM. Bordas usam reflexão;
transientes físicos podem ser suavizados pelo FIR e exigem revisão própria.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def _medidas(y):
    return {"rms_v": float(np.sqrt(np.mean(y * y))),
            "pico_absoluto_v": float(np.max(np.abs(y)))}


def _metadados_brutos(dados):
    if "metadata_json" not in dados:
        return None
    valor = dados["metadata_json"]
    if valor.shape != () or valor.dtype.kind != "U":
        raise ValueError("metadata_json deve ser escalar Unicode, sem pickle")
    def constante_invalida(valor):
        raise ValueError(f"constante JSON não finita: {valor}")
    meta = json.loads(valor.item(), parse_constant=constante_invalida)
    if not isinstance(meta, dict) or type(meta.get("versao_schema")) is not int or meta["versao_schema"] != 1:
        raise ValueError("metadata_json requer versao_schema inteira igual a 1")
    fs, pontos = meta.get("fs_destino_hz"), meta.get("pontos_destino")
    if type(fs) not in (int, float) or not np.isfinite(fs) or fs <= 0:
        raise ValueError("fs_destino_hz do metadata deve ser numérica, positiva e finita")
    if type(pontos) is not int or pontos < 2:
        raise ValueError("pontos_destino do metadata deve ser inteiro >= 2")
    return meta


def arquivos_brutos_da_captura(sessao_dir, metadado_captura):
    """Brutos NPZ de UMA captura gravada, só pelo que o metadata dela lista.

    Nunca por ``id_captura`` nem glob: uma tentativa descartada pode deixar um
    bruto órfão em ``bruto_osciloscopio/`` com o mesmo ``id_captura``. Entradas
    com erro/sem arquivo são ignoradas; caminho fora da sessão é recusado.
    """
    info = (metadado_captura or {}).get("bruto_osciloscopio")
    if not isinstance(info, dict):
        return []
    raiz = Path(sessao_dir).resolve()
    encontrados = []
    for item in info.get("arquivos") or []:
        relativo = item.get("arquivo") if isinstance(item, dict) else None
        if not relativo or item.get("erro"):
            continue
        caminho = (raiz / relativo).resolve()
        if raiz not in caminho.parents:
            raise ValueError(f"bruto fora da pasta da sessão: {relativo}")
        if caminho.is_file():
            encontrados.append(caminho)
    return encontrados


def _comparacao(atual, referencia):
    erro = atual - referencia
    correlacao = None
    if np.std(atual) > 1e-12 and np.std(referencia) > 1e-12:
        correlacao = float(np.corrcoef(atual, referencia)[0, 1])
    return {"interp": _medidas(atual), "fir_interp": _medidas(referencia),
            "erro_rms_v": float(np.sqrt(np.mean(erro * erro))),
            "erro_maximo_v": float(np.max(np.abs(erro))),
            "correlacao": correlacao}


def _thd(t, y, f0_hz, harmonicos):
    """Ajuste conjunto DC + seno/cosseno; THD é razão RMS H2..HN/H1.

    Dois ciclos completos são o mínimo desta análise, não critério de aceite.
    O ajuste não estima frequência nem separa inter-harmônicos e transientes.
    """
    ciclos = float((t[-1] - t[0]) * f0_hz)
    resultado = {"disponivel": False, "thd_percentual": None,
                 "fundamental_rms_v": None, "dc_v": None,
                 "ciclos_observados": ciclos, "motivo": None}
    if ciclos < 2:
        resultado["motivo"] = "menos de dois ciclos observados"
        return resultado
    if t.size < 2 * harmonicos + 1:
        resultado["motivo"] = "amostras insuficientes para ajuste conjunto"
        return resultado
    fase = 2 * np.pi * f0_hz * (t - t[0])
    matriz = np.column_stack([np.ones(t.size)] +
                              [func(h * fase) for h in range(1, harmonicos + 1)
                               for func in (np.cos, np.sin)])
    coef, _, posto, singulares = np.linalg.lstsq(matriz, y, rcond=None)
    if posto != matriz.shape[1] or singulares[-1] / singulares[0] < 1e-10:
        resultado["motivo"] = "ajuste harmônico sem posto completo ou mal condicionado"
        return resultado
    amplitudes = np.hypot(coef[1::2], coef[2::2])
    fundamental = float(amplitudes[0] / np.sqrt(2))
    resultado.update(fundamental_rms_v=fundamental, dc_v=float(coef[0]))
    if fundamental <= max(float(np.max(np.abs(y))), 1.0) * 1e-10:
        resultado["motivo"] = "fundamental nula ou numericamente desprezível"
        return resultado
    resultado.update(disponivel=True,
                     thd_percentual=float(100 * np.linalg.norm(amplitudes[1:]) / amplitudes[0]))
    return resultado


def _comparacao_harmonica(t, atual, referencia, f0_hz, harmonicos):
    resultado = _comparacao(atual, referencia)
    for nome, y in (("interp", atual), ("fir_interp", referencia)):
        resultado[nome]["thd"] = _thd(t, y, f0_hz, harmonicos)
    a, b = resultado["interp"]["thd"], resultado["fir_interp"]["thd"]
    resultado["diferenca_thd_pontos_percentuais_fir_menos_interp"] = (
        b["thd_percentual"] - a["thd_percentual"]
        if a["disponivel"] and b["disponivel"] else None)
    return resultado


def comparar(tempo_s, tensao_v, fs_salvo=30_000.0, taps=257,
             f0_hz=60.0, harmonicos=10, pontos_salvos=None):
    """Retorna somente métricas JSON; exige amostragem bruta uniforme.

    FIR sinc com janela Hamming, ganho DC unitário e corte a 90% do Nyquist
    de destino. A margem de 10% é banda de transição, não faixa útil garantida.
    O número de taps controla a rejeição e deve ser examinado para cada razão
    de taxas; não há promessa universal de atenuação para qualquer captura.
    """
    t, y = np.asarray(tempo_s, dtype=float), np.asarray(tensao_v, dtype=float)
    if t.ndim != 1 or y.ndim != 1 or t.size != y.size or t.size < 8:
        raise ValueError("tempo e tensão devem ser vetores de mesmo tamanho, com ao menos 8 amostras")
    if not np.all(np.isfinite(t)) or not np.all(np.isfinite(y)):
        raise ValueError("tempo e tensão devem conter somente valores finitos")
    if not np.isfinite(fs_salvo) or fs_salvo <= 0:
        raise ValueError("fs_salvo deve ser positiva e finita")
    if isinstance(taps, bool) or not isinstance(taps, (int, np.integer)) or taps < 3 or taps % 2 == 0:
        raise ValueError("taps deve ser inteiro ímpar >= 3")
    if taps >= t.size:
        raise ValueError("a captura deve ter mais amostras que os taps do FIR")
    dt = np.diff(t)
    passo = float(np.median(dt))
    if passo <= 0 or np.any(dt <= 0) or not np.allclose(dt, passo, rtol=1e-3, atol=passo * 1e-6):
        raise ValueError("tempo deve ser estritamente crescente e uniforme (tolerância relativa 0,1%)")
    fs_bruto = 1.0 / passo
    if fs_salvo > fs_bruto * (1 + 1e-9):
        raise ValueError("esta análise exige fs_salvo <= fs_bruto")
    if not np.isfinite(f0_hz) or f0_hz <= 0:
        raise ValueError("f0_hz deve ser positiva e finita")
    if (isinstance(harmonicos, bool) or not isinstance(harmonicos, (int, np.integer))
            or harmonicos < 2):
        raise ValueError("harmonicos deve ser inteiro >= 2")
    if harmonicos * f0_hz > fs_salvo / 2:
        raise ValueError("maior harmônico solicitado excede o Nyquist de destino")
    relativo = t - t[0]
    disponiveis = int(np.floor(relativo[-1] * fs_salvo + 1e-8)) + 1
    if pontos_salvos is not None and (isinstance(pontos_salvos, bool) or
            not isinstance(pontos_salvos, (int, np.integer)) or
            not 2 <= pontos_salvos <= disponiveis):
        raise ValueError("pontos_salvos deve ser inteiro >= 2 dentro da janela bruta")
    pontos = int(pontos_salvos) if pontos_salvos is not None else disponiveis
    alvo = np.arange(pontos) / fs_salvo
    metade = taps // 2
    corte_hz = 0.9 * fs_salvo / 2
    indices = np.arange(taps) - metade
    h = 2 * corte_hz / fs_bruto * np.sinc(2 * corte_hz / fs_bruto * indices)
    h *= np.hamming(taps)
    h /= np.sum(h)
    filtrada = np.convolve(np.pad(y, metade, mode="reflect"), h, mode="valid")
    atual = np.interp(alvo, relativo, y)
    referencia = np.interp(alvo, relativo, filtrada)
    margem = int(np.ceil(metade / fs_bruto * fs_salvo)) + 1
    if pontos <= 2 * margem + 1:
        raise ValueError("captura curta demais para comparar o interior sem bordas do FIR")
    # Pesos de energia do espectro unilateral: equivalentes a Parseval.
    energia = np.abs(np.fft.rfft(y)) ** 2
    pesos = np.full(energia.size, 2.0)
    pesos[0] = 1.0
    if y.size % 2 == 0:
        pesos[-1] = 1.0
    energia *= pesos / y.size**2
    frequencias = np.fft.rfftfreq(y.size, passo)
    acima = float(np.sum(energia[frequencias > fs_salvo / 2]))
    total = float(np.sum(energia))
    config = {"fs_salvo_hz": float(fs_salvo), "taps": int(taps),
              "f0_hz": float(f0_hz), "harmonicos": int(harmonicos),
              "pontos_salvos": pontos, "inicio_relativo_s": 0.0,
              "metodo_thd": "least-squares DC+cos+sin; H2..HN/H1; minimo 2 ciclos",
              "filtro_corte_fracao_nyquist": 0.9, "bordas": "reflect"}
    config_bytes = json.dumps(config, sort_keys=True, separators=(",", ":"),
                              allow_nan=False).encode("utf-8")
    hash_sinais = hashlib.sha256()
    for vetor in (t, y):
        hash_sinais.update(np.asarray(vetor, dtype="<f8").tobytes())
    bruto_thd = _thd(relativo, y, f0_hz, harmonicos)
    mascara = relativo <= alvo[-1] + passo * 1e-6
    mascara_interior = ((relativo >= alvo[margem] - passo * 1e-6) &
                        (relativo <= alvo[-margem - 1] + passo * 1e-6))
    bruto_janela = _thd(relativo[mascara], y[mascara], f0_hz, harmonicos)
    bruto_interior = _thd(relativo[mascara_interior], y[mascara_interior], f0_hz, harmonicos)
    completo = _comparacao_harmonica(alvo, atual, referencia, f0_hz, harmonicos)
    interior = _comparacao_harmonica(alvo[margem:-margem], atual[margem:-margem],
                                    referencia[margem:-margem], f0_hz, harmonicos)
    for resultado, thd_bruto in ((completo, bruto_janela), (interior, bruto_interior)):
        resultado["bruto_mesma_janela_thd"] = thd_bruto
        for metodo in ("interp", "fir_interp"):
            thd = resultado[metodo]["thd"]
            resultado[metodo]["diferenca_thd_pontos_percentuais_menos_bruto"] = (
                thd["thd_percentual"] - thd_bruto["thd_percentual"]
                if thd["disponivel"] and thd_bruto["disponivel"] else None)
    return {
        "fs_bruto_hz": fs_bruto, "fs_salvo_hz": float(fs_salvo),
        "amostras_brutas": int(y.size), "amostras_salvas": pontos,
        "bruto": dict(_medidas(y), thd=bruto_thd),
        "rastreabilidade": {"sinais_float64_le_sha256": hash_sinais.hexdigest(),
                            "configuracao_sha256": hashlib.sha256(config_bytes).hexdigest(),
                            "configuracao": config},
        "analise_harmonica": {"f0_hz": float(f0_hz), "harmonicos": int(harmonicos),
                              "maior_harmonico_hz": float(harmonicos * f0_hz),
                              "nyquist_comum_hz": float(fs_salvo / 2),
                              "convencao": config["metodo_thd"]},
        "filtro": {"tipo": "FIR sinc / janela Hamming, ganho DC 1", "taps": taps,
                   "corte_hz": corte_hz, "bordas": "reflexão",
                   "margem_descartada_por_borda_amostras": margem,
                   "meia_janela_s": metade / fs_bruto},
        "espectro_bruto": {"metodo": "DFT retangular unilateral com pesos de Parseval; inclui DC",
                           "energia_acima_nyquist_v2": acima,
                           "fracao_acima_nyquist": acima / total if total else 0.0},
        "registro_completo": completo,
        "interior_sem_bordas": interior,
        "limitacoes": ["FIR é referência offline; não é verdade física nem correção aprovada do ORM.",
                       "Reflexão afeta bordas; métricas do interior excluem meia janela do FIR.",
                       "Transientes dentro do registro também são suavizados; examine sua forma e duração.",
                       "Energia acima do Nyquist usa DFT retangular, sujeita a vazamento espectral.",
                       "Rejeição depende dos taps e da razão de taxas; confira a banda de transição.",
                       "THD usa a frequência informada, sem estimá-la; inter-harmônicos e transientes podem enviesar o ajuste.",
                       "Todos os métodos usam H2..HN limitados ao Nyquist de destino; isto não é THD de banda ilimitada.",
                       "Nenhuma métrica desta ferramenta define critério de aceite físico."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    entrada = parser.add_mutually_exclusive_group(required=True)
    entrada.add_argument("--entrada", type=Path, help="NPZ bruto; carregado sem pickle")
    entrada.add_argument("--sintetico", action="store_true", help="demonstração matemática, sem captura física")
    parser.add_argument("--chave-tempo", default="tempo_s")
    parser.add_argument("--chave-tensao", default="tensao_v")
    parser.add_argument("--fs-salvo", type=float, help="Hz; usa fs_destino do NPZ ou 30000")
    parser.add_argument("--pontos-salvos", type=int, help="usa pontos_destino do NPZ quando omitido")
    parser.add_argument("--f0-hz", type=float, default=60.0, help="fundamental explícita do ajuste (padrão: 60 Hz)")
    parser.add_argument("--harmonicos", type=int, default=10, help="maior ordem, >=2 e dentro do Nyquist de destino (padrão: 10)")
    parser.add_argument("--taps", type=int, default=257)
    parser.add_argument("--saida", type=Path, help="JSON novo; arquivo existente não será sobrescrito")
    args = parser.parse_args(argv)
    try:
        fs_salvo, pontos_salvos = args.fs_salvo, args.pontos_salvos
        if args.sintetico:
            t = np.arange(12_000) / 120_000.0
            y = np.sin(2 * np.pi * 60 * t) + 0.25 * np.sin(2 * np.pi * 20_000 * t)
            fonte = {"tipo": "sintetica_nao_fisica", "descricao": "60 Hz + 0,25 × 20 kHz, 120 kSa/s"}
        else:
            with np.load(args.entrada, allow_pickle=False) as dados:
                t, y = dados[args.chave_tempo], dados[args.chave_tensao]
                meta = _metadados_brutos(dados)
                if meta is not None:
                    if fs_salvo is None:
                        fs_salvo = meta["fs_destino_hz"]
                    if pontos_salvos is None:
                        pontos_salvos = meta["pontos_destino"]
                elif fs_salvo is None and "fs_destino" in dados:
                    fs_salvo = float(dados["fs_destino"].item())
                if pontos_salvos is None and "pontos_destino" in dados:
                    valor = dados["pontos_destino"].item()
                    if isinstance(valor, bool) or not isinstance(valor, (int, np.integer)):
                        raise ValueError("pontos_destino do NPZ deve ser inteiro")
                    pontos_salvos = valor
            fonte = {"tipo": "arquivo_bruto_fornecido", "caminho": str(args.entrada),
                     "arquivo_sha256": hashlib.sha256(args.entrada.read_bytes()).hexdigest()}
            if meta is not None:
                fonte["metadata_bruto"] = meta
        resultado = comparar(t, y, fs_salvo if fs_salvo is not None else 30_000.0,
                             args.taps, args.f0_hz, args.harmonicos, pontos_salvos)
        resultado["fonte"] = fonte
        texto = json.dumps(resultado, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.saida:
            with args.saida.open("x", encoding="utf-8") as destino:
                destino.write(texto)
        else:
            print(texto, end="")
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
