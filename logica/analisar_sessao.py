"""Análise offline de uma pasta de sessão (``resultados/sessao_*/``): para
cada ``.npz``, reconstrói a forma esperada via ``gerar()`` + ``seed`` do
metadata (mesma técnica usada manualmente na investigação do
CHANGELOG/v1.7.md), mede deslocamento por cross-correlação e razão de pico,
e opcionalmente gera uma imagem lado-a-lado (gerado vs. capturado) por
arquivo. Sem hardware — mesmo padrão de ``visualizador.py``: roda em
qualquer máquina, só precisa dos ``.npz``/``.jsonl`` já gravados.

Uso:
    python logica/analisar_sessao.py resultados/sessao_2026-09-11_140000
    python logica/analisar_sessao.py resultados/sessao_2026-09-11_140000 --sem-imagens
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_DIRS = (PROJECT_ROOT / "experimentos_nativos", PROJECT_ROOT / "experimentos_waveform")


def analisar_offset(expected: np.ndarray, captured: np.ndarray, fs_hz: float) -> Tuple[int, float]:
    """Cross-correlação FFT (sem scipy) entre a forma esperada e a
    capturada. Devolve (lag em amostras, correlação normalizada no pico) —
    lag positivo significa que o conteúdo capturado está ATRASADO em
    relação ao esperado."""
    n = len(expected)
    e = expected - np.mean(expected)
    c = captured - np.mean(captured)
    e = e / (np.linalg.norm(e) + 1e-12)
    c = c / (np.linalg.norm(c) + 1e-12)
    nfft = 1
    while nfft < 2 * n:
        nfft *= 2
    E = np.fft.rfft(e, nfft)
    C = np.fft.rfft(c, nfft)
    corr = np.fft.irfft(np.conj(E) * C, nfft)
    lags = np.concatenate([np.arange(0, n), np.arange(-(nfft - n), 0)])
    order = np.argsort(lags)
    lags_sorted, corr_sorted = lags[order], corr[order]
    mask = (lags_sorted >= -n) & (lags_sorted <= n)
    lags_r, corr_r = lags_sorted[mask], corr_sorted[mask]
    melhor = int(np.argmax(corr_r))
    return int(lags_r[melhor]), float(corr_r[melhor])


class _ConfigOffline:
    """``Config`` mínima para satisfazer o que 04/06/08/09/19 leem dentro de
    ``gerar()`` (``self.config.capturas()``/``capturas_override``/
    ``base_voltage_rms``) sem depender do dataclass completo de
    ``mestre.Config`` (que exige 13 campos irrelevantes aqui).
    ``capturas_override=None`` força o mesmo ramo de sorteio
    (``rng.uniform``) que o dataset simulado usa — com a MESMA seed da
    captura real, reproduz exatamente o valor original sempre que a sessão
    NÃO rodou com ``set capturas N`` ativo (caso padrão). Ver nota em
    ``_reconstruir_esperado`` sobre a limitação quando cobertura estava
    ativa."""

    capturas_override: Optional[int] = None
    base_voltage_rms: float = 127.0

    def capturas(self, simulated: bool) -> int:
        return 1


class _BancadaOffline:
    """Substituto mínimo de ``Bancada`` só para satisfazer
    ``ExperimentoBase.__init__`` (que lê ``bancada.config``/``.fonte``/
    ``.osc``) sem abrir nenhum instrumento. ``osc=None`` faz ``gerar()``
    tratar a reconstrução como ``simulado=True`` — o mesmo ramo usado para
    gerar o dataset offline, sem hardware nenhum envolvido."""

    config = _ConfigOffline()
    fonte = None
    osc = None


def _carregar_experimento_cls(class_id: str):
    for diretorio in EXPERIMENT_DIRS:
        script_path = diretorio / f"{class_id}.py"
        if script_path.exists():
            module_name = f"analise_{diretorio.name}_{class_id}"
            spec = importlib.util.spec_from_file_location(module_name, script_path)
            module = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(diretorio))
            try:
                spec.loader.exec_module(module)
            finally:
                sys.path.remove(str(diretorio))
            return module.Experimento
    raise FileNotFoundError(f"Nenhum script encontrado para a classe {class_id!r}")


def _reconstruir_esperado(class_id: str, metadado: dict) -> np.ndarray:
    cls = _carregar_experimento_cls(class_id)
    # Instancia via __init__ normal (não cls.__new__(cls)): 04/06/08/09/19
    # leem self.config/self.osc dentro do próprio gerar() (cobertura
    # determinística de parâmetro contínuo, Task 6) — sem __init__ essas
    # leituras explodem com AttributeError para essas 5 classes, mesmo
    # quando a cobertura não estava ativa. _BancadaOffline supre isso sem
    # tocar hardware nenhum.
    instancia = cls(_BancadaOffline())
    fs_hz = metadado["fs_hz"]
    pontos = metadado["pontos"]
    t = np.arange(pontos, dtype=np.float64) / fs_hz
    rng = np.random.default_rng(metadado["seed"])
    # capture_index seleciona o nível/parâmetro dentro de gerar() (SAG/SWELL
    # discretos, ou cobertura contínua da Task 6) — sem isto, toda captura
    # reconstruiria o nível 0, incompatível com o real. metadata sempre tem
    # "nivel_indice" desde a Task 4 (mestre.py:908); .get(...) só é rede de
    # segurança para metadata no formato antigo, pré-v1.8. Desde o fix pós-
    # -Task 9 em mestre.py:908, "nivel_indice" grava o capture_index real de
    # TODA captura física (not simulated), não só quando agrupada por nível
    # — cobre igualmente SAG/SWELL/HARMONICS, 04/06/08/09/19 e 18.py.
    #
    # Limitação residual (não corrigível aqui): mesmo com o capture_index
    # certo em mãos, _BancadaOffline força self.osc=None dentro de gerar(),
    # ou seja "simulado=True" e "cobertura_ativa=False" — para 04/06/08/09/19
    # isso faz valor_para_captura() cair sempre no ramo de sorteio
    # (rng.uniform), mesmo quando a captura real usou o ramo determinístico
    # de cobertura ("set capturas N>1" ativo). O índice reconstruído já é o
    # certo; é o RAMO de gerar() que ainda pode ser o errado para essas 5
    # classes especificamente. Corrigir isso exigiria simular osc "ligado" e
    # config.capturas_override/total consistentes com a sessão real dentro
    # de _BancadaOffline — fora do escopo deste fix. Efeito prático: só
    # "razao_pico" dessas 5 classes pode ficar impreciso quando cobertura
    # estava ativa; a portadora de 60 Hz (e portanto o lag por
    # cross-correlação, o diagnóstico principal desta ferramenta) não
    # depende do parâmetro de distúrbio e não é afetada.
    capture_index = metadado.get("nivel_indice", 0)
    voltage_pu, _ = instancia.gerar(t, 60.0, capture_index, rng)
    return np.asarray(voltage_pu, dtype=np.float64)


def analisar_sessao(sessao_dir: Path, *, gerar_imagens: bool = True) -> List[Dict]:
    metadata_dir = sessao_dir / "metadata"
    if not metadata_dir.is_dir():
        raise FileNotFoundError(f"{sessao_dir} não parece uma pasta de sessão (sem metadata/)")

    metadados_por_id_captura: Dict[str, dict] = {}
    for jsonl_path in metadata_dir.glob("*.jsonl"):
        for linha in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not linha.strip():
                continue
            registro = json.loads(linha)
            metadados_por_id_captura[registro["id_captura"]] = registro

    relatorio: List[Dict] = []
    imagens_dir = sessao_dir / "analise"
    if gerar_imagens:
        imagens_dir.mkdir(exist_ok=True)

    for npz_path in sorted(sessao_dir.glob("*.npz")):
        stem = npz_path.stem
        dados = np.load(npz_path, allow_pickle=True)
        n_capturas = dados["tensao_pu"].shape[0]
        if n_capturas > 1:
            # Formato simulado (_salvar_classe_simulada em mestre.py): um
            # único .npz por classe com todas as capturas empilhadas em
            # tensao_pu (N, pontos) — bem diferente do formato real (1 .npz
            # por captura, sempre 1 linha), que é o único que esta ferramenta
            # sabe analisar. Sem este check, dados["tensao_pu"][0] analisaria
            # silenciosamente só a 1ª de até N capturas e reportaria como se
            # fosse a classe inteira — nenhum erro, resultado enganoso.
            relatorio.append({
                "classe": stem,
                "erro": (
                    f"arquivo tem {n_capturas} capturas empilhadas (formato simulado); "
                    "esta ferramenta só analisa capturas únicas do formato real (1 por arquivo)"
                ),
            })
            continue
        id_captura = str(dados["id_captura"][0])
        metadado = metadados_por_id_captura.get(id_captura)
        if metadado is None:
            relatorio.append({"classe": stem, "erro": f"sem metadata para id_captura={id_captura!r}"})
            continue
        class_id = id_captura.split("-")[0]
        capturado = dados["tensao_pu"][0]
        amostras_totais = metadado.get("amostras_totais", metadado["pontos"])
        margem_antes = metadado.get("margem_amostras_antes", 0)

        try:
            esperado = _reconstruir_esperado(class_id, metadado)
        except Exception as exc:  # arquivo de classe não encontrado, gerar() mudou de assinatura etc.
            relatorio.append({"classe": stem, "erro": f"falha reconstruindo esperado: {exc}"})
            continue

        if margem_antes:
            # captura em margin mode: recorta a janela nominal do meio do
            # array bruto antes de comparar com o esperado (que sempre tem
            # o tamanho nominal, config.points).
            capturado_para_comparar = capturado[margem_antes : margem_antes + len(esperado)]
        else:
            capturado_para_comparar = capturado[: len(esperado)]

        lag, corr = analisar_offset(esperado, capturado_para_comparar, metadado["fs_hz"])
        pico_esperado = float(np.max(np.abs(esperado)))
        pico_capturado = float(np.max(np.abs(capturado)))
        relatorio.append({
            "classe": stem,
            "lag_amostras": lag,
            "lag_ms": lag / metadado["fs_hz"] * 1000.0,
            "correlacao": corr,
            "pico_esperado": pico_esperado,
            "pico_capturado": pico_capturado,
            "razao_pico": pico_capturado / pico_esperado if pico_esperado else float("nan"),
        })

        if gerar_imagens:
            _salvar_imagem_comparacao(imagens_dir, stem, esperado, capturado, metadado["fs_hz"])

    return relatorio


def _salvar_imagem_comparacao(imagens_dir: Path, stem: str, esperado: np.ndarray, capturado: np.ndarray, fs_hz: float) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t_esperado_ms = np.arange(len(esperado)) / fs_hz * 1000.0
    t_capturado_ms = np.arange(len(capturado)) / fs_hz * 1000.0
    fig, eixos = plt.subplots(1, 2, figsize=(16, 5))
    fig.suptitle(stem, fontsize=13, fontweight="bold")
    eixos[0].plot(t_esperado_ms, esperado, color="#1f77b4", linewidth=0.8)
    eixos[0].set_title("Gerado (gerar() + seed)")
    eixos[0].set_xlabel("Tempo (ms)")
    eixos[0].grid(True, alpha=0.3)
    eixos[1].plot(t_capturado_ms, capturado, color="#d62728", linewidth=0.8)
    eixos[1].set_title("Capturado (bancada real)")
    eixos[1].set_xlabel("Tempo (ms)")
    eixos[1].grid(True, alpha=0.3)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(imagens_dir / f"{stem}_comparacao.png", dpi=110)
    plt.close(fig)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sessao_dir", type=Path, help="Pasta resultados/sessao_.../ a analisar")
    parser.add_argument("--sem-imagens", action="store_true", help="Não gera PNGs, só o relatório no terminal")
    args = parser.parse_args(argv)

    relatorio = analisar_sessao(args.sessao_dir, gerar_imagens=not args.sem_imagens)
    print(f"{'arquivo':<40}{'lag (ms)':>12}{'correlação':>12}{'razão pico':>12}")
    for linha in relatorio:
        if "erro" in linha:
            print(f"{linha['classe']:<40}  ERRO: {linha['erro']}")
            continue
        print(f"{linha['classe']:<40}{linha['lag_ms']:>12.2f}{linha['correlacao']:>12.3f}{linha['razao_pico']:>12.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
