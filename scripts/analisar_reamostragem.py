#!/usr/bin/env python3
"""P28: compara offline np.interp com FIR passa-baixas + np.interp.

Não acessa instrumentos e nunca modifica a captura. A alternativa é uma
referência de análise, não uma alteração do ORM. Bordas usam reflexão;
transientes físicos podem ser suavizados pelo FIR e exigem revisão própria.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def _medidas(y):
    return {"rms_v": float(np.sqrt(np.mean(y * y))),
            "pico_absoluto_v": float(np.max(np.abs(y)))}


def _comparacao(atual, referencia):
    erro = atual - referencia
    correlacao = None
    if np.std(atual) > 1e-12 and np.std(referencia) > 1e-12:
        correlacao = float(np.corrcoef(atual, referencia)[0, 1])
    return {"interp": _medidas(atual), "fir_interp": _medidas(referencia),
            "erro_rms_v": float(np.sqrt(np.mean(erro * erro))),
            "erro_maximo_v": float(np.max(np.abs(erro))),
            "correlacao": correlacao}


def comparar(tempo_s, tensao_v, fs_salvo=30_000.0, taps=257):
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
    relativo = t - t[0]
    pontos = int(np.floor(relativo[-1] * fs_salvo + 1e-8)) + 1
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
    return {
        "fs_bruto_hz": fs_bruto, "fs_salvo_hz": float(fs_salvo),
        "amostras_brutas": int(y.size), "amostras_salvas": pontos,
        "bruto": _medidas(y),
        "filtro": {"tipo": "FIR sinc / janela Hamming, ganho DC 1", "taps": taps,
                   "corte_hz": corte_hz, "bordas": "reflexão",
                   "margem_descartada_por_borda_amostras": margem,
                   "meia_janela_s": metade / fs_bruto},
        "espectro_bruto": {"metodo": "DFT retangular unilateral com pesos de Parseval; inclui DC",
                           "energia_acima_nyquist_v2": acima,
                           "fracao_acima_nyquist": acima / total if total else 0.0},
        "registro_completo": _comparacao(atual, referencia),
        "interior_sem_bordas": _comparacao(atual[margem:-margem], referencia[margem:-margem]),
        "limitacoes": ["FIR é referência offline; não é verdade física nem correção aprovada do ORM.",
                       "Reflexão afeta bordas; métricas do interior excluem meia janela do FIR.",
                       "Transientes dentro do registro também são suavizados; examine sua forma e duração.",
                       "Energia acima do Nyquist usa DFT retangular, sujeita a vazamento espectral.",
                       "Rejeição depende dos taps e da razão de taxas; confira a banda de transição."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    entrada = parser.add_mutually_exclusive_group(required=True)
    entrada.add_argument("--entrada", type=Path, help="NPZ bruto; carregado sem pickle")
    entrada.add_argument("--sintetico", action="store_true", help="demonstração matemática, sem captura física")
    parser.add_argument("--chave-tempo", default="tempo_s")
    parser.add_argument("--chave-tensao", default="tensao_v")
    parser.add_argument("--fs-salvo", type=float, default=30_000.0)
    parser.add_argument("--taps", type=int, default=257)
    parser.add_argument("--saida", type=Path, help="JSON novo; arquivo existente não será sobrescrito")
    args = parser.parse_args(argv)
    try:
        if args.sintetico:
            t = np.arange(12_000) / 120_000.0
            y = np.sin(2 * np.pi * 60 * t) + 0.25 * np.sin(2 * np.pi * 20_000 * t)
            fonte = {"tipo": "sintetica_nao_fisica", "descricao": "60 Hz + 0,25 × 20 kHz, 120 kSa/s"}
        else:
            with np.load(args.entrada, allow_pickle=False) as dados:
                t, y = dados[args.chave_tempo], dados[args.chave_tensao]
            fonte = {"tipo": "arquivo_bruto_fornecido", "caminho": str(args.entrada)}
        resultado = comparar(t, y, args.fs_salvo, args.taps)
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
