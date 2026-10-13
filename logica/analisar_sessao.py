"""Análise offline de uma pasta de sessão (``resultados/sessao_*/``): para
cada ``.npz``, reconstrói a forma esperada via ``gerar()`` + ``seed`` do
metadata (mesma técnica usada manualmente na investigação do
CHANGELOG/v1.7.md), mede deslocamento por cross-correlação e razão de pico
e correlação do distúrbio. Só numérico: as figuras ficam no relatório HTML
(``relatorio_html.py``). Sem hardware: roda em qualquer máquina, só precisa
dos ``.npz``/``.jsonl`` já gravados.

Uso:
    python logica/analisar_sessao.py resultados/sessao_2026-09-11_140000
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
if str(PROJECT_ROOT / "logica") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "logica"))
from sinais import (  # noqa: E402
    correlacao_disturbio, correlacao_disturbio_fundamental_ajustada, janela_nominal,
)

# Valores usados só quando o metadata é ANTIGO e não os traz. Enquanto
# estiveram chumbados no código (60 Hz na chamada de gerar() e 127 V em
# _ConfigOffline), toda a sessão 2 — que rodou a 220 V/50 Hz — era analisada
# contra o modelo errado (relatório 01 §4 item 8).
F0_PADRAO_HZ = 60.0
TENSAO_BASE_PADRAO_RMS = 127.0


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
    base_voltage_rms: float = TENSAO_BASE_PADRAO_RMS
    perfil: str = "literatura"
    sorteio_posicao: bool = False

    def __init__(
        self, base_voltage_rms: float = TENSAO_BASE_PADRAO_RMS, perfil: str = "literatura",
        sorteio_posicao: bool = False, fs_hz: float = 30_000.0, points: int = 6_000,
    ):
        self.base_voltage_rms = float(base_voltage_rms)
        self.perfil = perfil
        # Início/duração/fase sorteados (v1.15) precisam da grade da captura.
        self.sorteio_posicao = bool(sorteio_posicao)
        self.fs_hz = float(fs_hz)
        self.points = int(points)

    def capturas(self, simulated: bool) -> int:
        return 1


class _BancadaOffline:
    """Substituto mínimo de ``Bancada`` só para satisfazer
    ``ExperimentoBase.__init__`` (que lê ``bancada.config``/``.fonte``/
    ``.osc``) sem abrir nenhum instrumento. ``osc=None`` faz ``gerar()``
    tratar a reconstrução como ``simulado=True`` — o mesmo ramo usado para
    gerar o dataset offline, sem hardware nenhum envolvido."""

    fonte = None
    osc = None

    def __init__(self, base_voltage_rms: float = TENSAO_BASE_PADRAO_RMS, perfil: str = "literatura", **sorteio):
        self.config = _ConfigOffline(base_voltage_rms, perfil, **sorteio)


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
    # f0 e tensão base saem do metadata da PRÓPRIA sessão (gravados a partir
    # da v1.11); só caem no padrão para metadata antigo, e nesse caso o
    # relatório avisa.
    # Instancia via __init__ normal (não cls.__new__(cls)): 04/06/08/09/19
    # leem self.config/self.osc dentro do próprio gerar() (cobertura
    # determinística de parâmetro contínuo, Task 6) — sem __init__ essas
    # leituras explodem com AttributeError para essas 5 classes, mesmo
    # quando a cobertura não estava ativa. _BancadaOffline supre isso sem
    # tocar hardware nenhum.
    f0_hz = float(metadado.get("f0_hz", F0_PADRAO_HZ))
    tensao_base = float(metadado.get("tensao_base_rms", TENSAO_BASE_PADRAO_RMS))
    # Perfil de faixas da captura (v1.15); metadata anterior não tem o campo
    # e foi gerado com as faixas da literatura.
    fs_hz = metadado["fs_hz"]
    pontos = metadado["pontos"]
    # Sorteio de início/duração/fase (v1.15): metadata anterior não tem o
    # campo e foi gerado com as posições fixas.
    instancia = cls(_BancadaOffline(
        tensao_base, metadado.get("perfil", "literatura"),
        sorteio_posicao=bool(metadado.get("sorteio_posicao", False)), fs_hz=fs_hz, points=pontos,
    ))
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
    voltage_pu, _ = instancia.gerar(t, f0_hz, capture_index, rng)
    voltage_pu = np.asarray(voltage_pu, dtype=np.float64)
    # Limite de bancada (v1.13): a captura física programou senoide + fração ×
    # (modelo - senoide); é contra ESSA forma que a análise compara.
    fracao = (metadado.get("parametros") or {}).get("fator_disturbio_bancada")
    if fracao is not None:
        tau = float(metadado.get("fase_graus", 0.0)) / (360.0 * f0_hz)
        senoide = np.sin(2.0 * np.pi * f0_hz * (t + tau))
        voltage_pu = senoide + float(fracao) * (voltage_pu - senoide)
    return voltage_pu


def _correlacao_disturbio_alinhada(
    esperado: np.ndarray, registro: np.ndarray, inicio_janela: int, lag: int, metadado: dict,
    fundamental_ajustada: bool = False,
) -> Tuple[Optional[float], Optional[str]]:
    """Correlação só da componente de distúrbio (``sinais.correlacao_disturbio``)
    com a janela da captura re-alinhada pelo ``lag`` de ``analisar_offset``:
    desloca o início da janela no registro bruto (sem perder amostras nas
    bordas, enquanto houver margem) e usa a senoide nominal com a fase do
    modelo (metadata ``fase_graus``; sem sorteio, 0). Com
    ``fundamental_ajustada`` usa ``correlacao_disturbio_fundamental_ajustada``
    (a fundamental de cada sinal ajustada, em vez da senoide nominal; mesmo
    recorte e mesmo lag)."""
    n = len(esperado)
    inicio = max(0, min(int(inicio_janela) + int(lag), max(0, registro.size - n)))
    if fundamental_ajustada:
        return correlacao_disturbio_fundamental_ajustada(
            esperado, registro[inicio : inicio + n], fs_hz=float(metadado["fs_hz"]),
            f0_hz=float(metadado.get("f0_hz", F0_PADRAO_HZ)),
        )
    return correlacao_disturbio(
        esperado, registro[inicio : inicio + n], fs_hz=float(metadado["fs_hz"]),
        f0_hz=float(metadado.get("f0_hz", F0_PADRAO_HZ)),
        fase_graus=float(metadado.get("fase_graus", 0.0)),
    )


def analisar_sessao(sessao_dir: Path) -> List[Dict]:
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
    avisos: List[str] = []

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

        # Recorte alinhado pelo TRIGGER real (indice_trigger, derivado de
        # x_origin da preamble), não por margem_amostras_antes: com
        # REFerence LEFT o trigger caía uma divisão (janela/10) adiante do
        # que o código supunha e todo recorte saía deslocado (H-REF10).
        # Metadata antigo, sem indice_trigger, cai no comportamento anterior.
        indice_trigger = metadado.get("indice_trigger")
        if indice_trigger is None:
            indice_trigger = margem_antes
            if margem_antes:
                avisos.append(
                    f"{stem}: metadata sem indice_trigger; recorte alinhado por "
                    "margem_amostras_antes (pode ter viés de janela/10)"
                )
        if metadado.get("inicio_janela") is not None:
            # Início já calculado pela bancada (prefere-se a refazer a conta).
            inicio_janela = max(0, min(int(metadado["inicio_janela"]), max(0, capturado.size - len(esperado))))
            capturado_para_comparar = capturado[inicio_janela : inicio_janela + len(esperado)]
        else:
            # Mesmo recorte de janela_nominal(); o início é recuperado para a
            # correlação do distúrbio re-alinhar a janela no registro bruto.
            inicio_janela = int(janela_nominal(
                np.arange(capturado.size), indice_trigger=int(indice_trigger),
                pre_trigger_s=float(metadado.get("pre_trigger_s", 0.0)),
                pontos=len(esperado), fs_hz=float(metadado["fs_hz"]),
            )[0])
            capturado_para_comparar = janela_nominal(
                capturado,
                indice_trigger=int(indice_trigger),
                pre_trigger_s=float(metadado.get("pre_trigger_s", 0.0)),
                pontos=len(esperado),
                fs_hz=float(metadado["fs_hz"]),
            )

        lag, corr = analisar_offset(esperado, capturado_para_comparar, metadado["fs_hz"])
        corr_disturbio, motivo_disturbio = _correlacao_disturbio_alinhada(
            esperado, capturado, inicio_janela, lag, metadado,
        )
        corr_ajustada, motivo_ajustada = _correlacao_disturbio_alinhada(
            esperado, capturado, inicio_janela, lag, metadado, fundamental_ajustada=True,
        )
        pico_esperado = float(np.max(np.abs(esperado)))
        pico_capturado = float(np.max(np.abs(capturado)))
        relatorio.append({
            "classe": stem,
            "f0_hz": float(metadado.get("f0_hz", F0_PADRAO_HZ)),
            "tensao_base_rms": float(metadado.get("tensao_base_rms", TENSAO_BASE_PADRAO_RMS)),
            "indice_trigger": int(indice_trigger),
            "validacao_fisica_ok": (metadado.get("validacao_fisica") or {}).get("ok"),
            "lag_amostras": lag,
            "lag_ms": lag / metadado["fs_hz"] * 1000.0,
            "correlacao": corr,
            "correlacao_disturbio": corr_disturbio,
            "correlacao_disturbio_motivo": motivo_disturbio,
            "correlacao_disturbio_fundamental_ajustada": corr_ajustada,
            "correlacao_disturbio_fundamental_ajustada_motivo": motivo_ajustada,
            "pico_esperado": pico_esperado,
            "pico_capturado": pico_capturado,
            "razao_pico": pico_capturado / pico_esperado if pico_esperado else float("nan"),
        })

    for aviso in avisos:
        print(f"AVISO: {aviso}")
    return relatorio


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sessao_dir", type=Path, help="Pasta resultados/sessao_.../ a analisar")
    args = parser.parse_args(argv)

    relatorio = analisar_sessao(args.sessao_dir)
    print(f"{'arquivo':<40}{'lag (ms)':>12}{'correlação':>12}{'corr. distúrbio':>17}{'corr. dist. fund.aj.':>22}{'razão pico':>12}")
    for linha in relatorio:
        if "erro" in linha:
            print(f"{linha['classe']:<40}  ERRO: {linha['erro']}")
            continue
        cd = linha["correlacao_disturbio"]
        cd_txt = "n/a" if cd is None else f"{cd:.3f}"
        ca = linha["correlacao_disturbio_fundamental_ajustada"]
        ca_txt = "n/a" if ca is None else f"{ca:.3f}"
        print(f"{linha['classe']:<40}{linha['lag_ms']:>12.2f}{linha['correlacao']:>12.3f}{cd_txt:>17}{ca_txt:>22}{linha['razao_pico']:>12.3f}")
        if cd is None:
            print(f"{'':<40}  corr. distúrbio n/a: {linha['correlacao_disturbio_motivo']}")
        if ca is None:
            print(f"{'':<40}  corr. dist. fund.aj. n/a: {linha['correlacao_disturbio_fundamental_ajustada_motivo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
