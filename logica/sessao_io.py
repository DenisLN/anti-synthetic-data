"""Leitura e escrita dos ``.npz`` de uma sessão (formato 2, v1.15).

Formato 2: UM ``NN_classe.npz`` comprimido (``np.savez_compressed``, sem perda)
por classe e sessão, com todos os perfis (``norma``/``literatura``/``fronteira``)
e as três versões de cada captura. As SNRs ficam FORA dele, em
``snr_XXdb/NN_classe.npz`` (um arquivo por classe e nível, sem compressão: o
ruído branco quase não comprime), e a corrente em
``corrente/NN_classe_corrente.npz``. Detalhes e chaves: ``docs/dataset.md``.

Formato 1 (até a v1.15 sem tag): um ``.npz`` por captura na bancada
(``NN_classe_<rótulo>.npz``, ``tensao_pu`` com shape ``(1, amostras)``) mais
``tres_versoes/<mesmo nome>``; e, no simulado, um ``.npz`` por classe com
``tensao_pu`` ``(N, pontos)``. ``ler_pasta`` lê os DOIS formatos e devolve a
mesma estrutura (``CapturaSessao``): é o ponto único de leitura dos
consumidores (``recortar_margem``, ``relatorio_html``, ``analisar_sessao``,
``scripts/gerar_*.py``).

Este módulo não importa ``mestre`` (nem hardware).
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import numpy as np

FORMATO_NPZ = 2
VERSOES: Tuple[str, ...] = ("medida", "modelo", "programada")
# Sessões anteriores ao campo ``perfil`` no metadata usavam as faixas de
# sempre, que passaram a se chamar ``literatura`` (``logica/perfis.py``).
PERFIL_LEGADO = "literatura"
PASTA_PARCIAL = "parcial"
PASTA_TRES_VERSOES = "tres_versoes"
GRANDEZAS = {"medida": "Tensão", "tensao_pu": "Tensão", "corrente_pu": "Corrente"}


# Protocolo de exclusão entre escritores e recuperação. O arquivo nunca é
# apagado: remover um inode bloqueado permite dois donos de locks distintos.
ARQUIVO_BLOQUEIO = ".sessao.lock"
_BLOQUEIOS_LOCAIS = {}
_MUTEX_BLOQUEIOS = threading.RLock()


class SessaoEmUsoError(RuntimeError):
    """Outra execução mantém a sessão ativa; recuperação deve esperar."""


class BloqueioSessao:
    """Lease de lock OS não bloqueante; liberado pelo SO se o processo morrer.

    Escritores do mesmo processo compartilham o lease (CLI/Bancada/acumulador).
    Recuperadores nunca compartilham, nem mesmo com um escritor local.
    """
    def __init__(self, sessao_dir: Path, *, escritor: bool = True):
        self._chave = str(Path(sessao_dir).resolve())
        self._liberado = True
        with _MUTEX_BLOQUEIOS:
            estado = _BLOQUEIOS_LOCAIS.get(self._chave)
            if estado is not None:
                if not escritor or not estado["escritor"]:
                    raise SessaoEmUsoError(f"sessão ativa: {sessao_dir}")
                estado["leases"] += 1
                self._liberado = False
                return
            pasta = Path(sessao_dir)
            pasta.mkdir(parents=True, exist_ok=True)
            caminho = pasta / ARQUIVO_BLOQUEIO
            if caminho.is_symlink():
                raise ValueError(f"lock de sessão não pode ser link simbólico: {caminho}")
            handle = caminho.open("a+b")
            try:
                if os.name == "nt":
                    import msvcrt
                    if caminho.stat().st_size == 0:
                        handle.write(b"0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                handle.close()
                raise SessaoEmUsoError(f"sessão ativa ou lock indisponível: {pasta}") from exc
            except BaseException:
                handle.close()
                raise
            _BLOQUEIOS_LOCAIS[self._chave] = {
                "handle": handle, "leases": 1, "escritor": escritor,
            }
            self._liberado = False

    def close(self):
        with _MUTEX_BLOQUEIOS:
            if self._liberado:
                return
            self._liberado = True
            estado = _BLOQUEIOS_LOCAIS[self._chave]
            estado["leases"] -= 1
            if estado["leases"]:
                return
            handle = estado["handle"]
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
                del _BLOQUEIOS_LOCAIS[self._chave]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        # A construção pode falhar e os globais podem desaparecer no teardown.
        try:
            self.close()
        except Exception:
            pass


# ---------------------------------------------------------------- nomes

def rotulo_snr(snr_db: float) -> str:
    return str(int(snr_db)) if float(snr_db).is_integer() else str(snr_db).replace(".", "_")


def pasta_snr(snr_db: float) -> str:
    return f"snr_{rotulo_snr(snr_db)}db"


def nivel_da_pasta_snr(nome: str) -> Optional[float]:
    achado = re.fullmatch(r"snr_(\d+(?:_\d+)?)db", nome)
    return float(achado.group(1).replace("_", ".")) if achado else None


def nome_arquivo_classe(class_id: str, nome: str) -> str:
    return f"{class_id}_{nome.lower()}.npz"


def nome_arquivo_corrente(class_id: str, nome: str) -> str:
    return f"{class_id}_{nome.lower()}_corrente.npz"


def chave(perfil: str, item: str) -> str:
    """Nome da chave dentro do ``.npz`` do formato 2: ``<perfil>/<item>``."""
    return f"{perfil}/{item}"


# Capturas compartilhadas entre perfis (``set perfil todos``, v1.15): classes
# cujo ``gerar()`` não depende do perfil (``perfis.depende_do_perfil``) são
# capturadas UMA vez, sob um perfil canônico; os outros perfis ficam como
# "espelhos" dele. No ``.npz``: ``compartilhadas_perfis`` (os espelhos) e
# ``compartilhadas_origem`` (o perfil cujo bloco guarda os dados, mesma ordem).
# No metadata: uma linha por perfil, todas com o mesmo ``arquivo_classe``,
# ``indice_no_arquivo`` e ``sha256_captura``.
CHAVE_ESPELHOS = "compartilhadas_perfis"
CHAVE_ORIGENS = "compartilhadas_origem"


def hash_captura(medida, modelo=None, programada=None, pontos: Optional[int] = None) -> str:
    """SHA-256 dos arrays de UMA captura: ``medida``, ``modelo`` e
    ``programada`` em float64 little-endian, na ordem, cada um precedido do
    rótulo e do tamanho. Versão ausente (``None``) conta como ``NaN`` de
    ``pontos`` amostras (como fica gravada no ``.npz``)."""
    medida = np.asarray(medida)
    if pontos is None:
        pontos = int((modelo if modelo is not None else medida).size)
    resumo = hashlib.sha256()
    for rotulo, valores in (("medida", medida), ("modelo", modelo), ("programada", programada)):
        v = np.full(pontos, np.nan) if valores is None else np.asarray(valores)
        v = np.ascontiguousarray(v, dtype="<f8")
        resumo.update(f"{rotulo}:{v.size};".encode("ascii"))
        resumo.update(v.tobytes())
    return resumo.hexdigest()


# ---------------------------------------------------------------- escrita

def gravar_npz(destino: Path, *, comprimido: bool = True, **arrays) -> None:
    """Grava ``destino`` de forma atômica (``.part`` -> ``os.replace``)."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(".npz.part")
    salvar = np.savez_compressed if comprimido else np.savez
    with parcial.open("wb") as handle:
        salvar(handle, **arrays)
    os.replace(parcial, destino)


def _como_texto(valores: Iterable[object]) -> np.ndarray:
    return np.array([str(v) for v in valores], dtype=str)


class ArquivoDaClasse:
    """Acumula as capturas de UMA classe (todos os perfis da rodada) e grava
    o ``NN_classe.npz`` do formato 2 (+ ``snr_XXdb/`` + ``corrente/``).

    ``adicionar`` guarda a captura em memória e, com ``spool=True`` (bancada),
    também num arquivo pequeno em ``<sessao>/parcial/NN_classe/`` (gravação
    atômica por captura): se o processo morrer antes de ``consolidar``, as
    capturas já feitas continuam no disco e ``recuperar_parcial`` as promove.
    ``consolidar`` (chamado ao fim de cada perfil, ou ao interromper a classe)
    reescreve os arquivos da classe INTEIRA com tudo o que já foi acumulado:
    nenhuma captura de um perfil anterior se perde quando o seguinte falha.
    Tudo é gravado em ``.part`` e só então promovido.
    """

    def __init__(self, results_dir: Path, class_id: str, nome: str, *, spool: bool = True) -> None:
        self.results_dir = Path(results_dir)
        self.id = class_id
        self.nome = nome
        self.spool = spool
        self._fechado = False
        self._bloqueio_sessao = BloqueioSessao(self.results_dir) if spool else None
        self._ordem: List[str] = []
        self._capturas: Dict[str, List[dict]] = {}
        # perfil espelho -> perfil de origem (cujo bloco guarda os dados)
        self._espelhos: Dict[str, str] = {}

    def close(self) -> None:
        """Libera o lease do escritor; não consolida nem remove capturas."""
        self._fechado = True
        bloqueio = getattr(self, "_bloqueio_sessao", None)
        if bloqueio is not None:
            self._bloqueio_sessao = None
            bloqueio.close()

    def _exigir_aberto(self) -> None:
        if self._fechado:
            raise RuntimeError("escritor de sessão encerrado; crie um novo acumulador antes de gravar")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # -- nomes ----------------------------------------------------------

    @property
    def nome_arquivo(self) -> str:
        return nome_arquivo_classe(self.id, self.nome)

    @property
    def pasta_spool(self) -> Path:
        return self.results_dir / PASTA_PARCIAL / f"{self.id}_{self.nome.lower()}"

    @property
    def perfis(self) -> List[str]:
        return [p for p in self._ordem if self._capturas.get(p)]

    def total(self) -> int:
        return sum(len(v) for v in self._capturas.values())

    @property
    def espelhos(self) -> Dict[str, str]:
        """Perfis sem bloco próprio -> perfil de origem (capturas compartilhadas)."""
        return {a: o for a, o in self._espelhos.items() if self._capturas.get(o)}

    def registros(self) -> List[dict]:
        """Metadata de todas as capturas, perfil a perfil, na ordem gravada;
        no fim, as linhas dos perfis espelho (cópia da linha da origem com o
        ``perfil`` trocado e ``captura_compartilhada``)."""
        saida = [c["metadado"] for p in self._ordem for c in self._capturas[p] if c["metadado"] is not None]
        for espelho, origem in self.espelhos.items():
            for c in self._capturas[origem]:
                if c["metadado"] is None:
                    continue
                linha = copy.deepcopy(c["metadado"])
                linha["perfil"] = espelho
                saida.append(linha)
        return saida

    def espelhar(self, origem: str, destinos: Sequence[str]) -> None:
        """Declara que ``destinos`` (perfis) são a MESMA captura de ``origem``
        (um bloco já completo): grava nos metadados da origem os campos
        ``captura_compartilhada``, ``perfil_de_origem``,
        ``compartilhada_com_perfis`` e ``sha256_captura``; ``registros()`` e o
        ``.npz`` passam a trazer os espelhos. Substitui um espelhamento
        anterior da mesma origem."""
        self._exigir_aberto()
        if not self._capturas.get(origem):
            raise ValueError(f"[{self.id}] não há capturas do perfil {origem} para espelhar")
        destinos = [d for d in destinos if d != origem]
        for d in destinos:
            if self._capturas.get(d):
                raise ValueError(f"[{self.id}] o perfil {d} tem bloco próprio; não pode ser espelho de {origem}")
        for a in [a for a, o in self._espelhos.items() if o == origem]:
            del self._espelhos[a]
        for d in destinos:
            self._espelhos[d] = origem
        grupo = [origem, *destinos]
        for c in self._capturas[origem]:
            if c["metadado"] is None:
                continue
            c["metadado"].update({
                "captura_compartilhada": bool(destinos),
                "perfil_de_origem": origem,
                "compartilhada_com_perfis": grupo,
                "sha256_captura": hash_captura(c["medida"], c["modelo"], c["programada"], c["pontos"]),
            })
            if not destinos:
                for chave_ in ("captura_compartilhada", "perfil_de_origem", "compartilhada_com_perfis", "sha256_captura"):
                    c["metadado"].pop(chave_, None)

    # -- acumulação -----------------------------------------------------

    def iniciar_perfil(self, perfil: str) -> None:
        """Começa (ou REPETE) o bloco de ``perfil``: o que havia dele some;
        os outros perfis ficam como estão."""
        self._exigir_aberto()
        if perfil not in self._capturas:
            self._ordem.append(perfil)
        self._capturas[perfil] = []
        # Um bloco novo desfaz o espelhamento que dependia dele (ou que o
        # tornava espelho): a captura é refeita.
        for a in [a for a, o in self._espelhos.items() if o == perfil or a == perfil]:
            del self._espelhos[a]
        self._apagar_spool(perfil)

    def adicionar(
        self,
        perfil: str,
        *,
        id_captura: str,
        medida: np.ndarray,
        tempo_ms: np.ndarray,
        fs_hz: float,
        modelo: Optional[np.ndarray] = None,
        programada: Optional[np.ndarray] = None,
        origem_programada: Optional[str] = None,
        inicio_janela: int = 0,
        pontos: Optional[int] = None,
        snr: Optional[Mapping[float, np.ndarray]] = None,
        corrente: Optional[np.ndarray] = None,
        metadado: Optional[dict] = None,
    ) -> int:
        """Acrescenta uma captura ao bloco de ``perfil`` e devolve o índice
        dela no arquivo (posição dentro do perfil, 0-based). Preenche no
        ``metadado`` (por referência) ``arquivo_classe``, ``perfil`` (se
        faltar) e ``indice_no_arquivo``."""
        self._exigir_aberto()
        if perfil not in self._capturas:
            self.iniciar_perfil(perfil)
        bloco = self._capturas[perfil]
        indice = len(bloco)
        medida = np.array(medida)
        if pontos is None:
            pontos = int((metadado or {}).get("pontos") or 0) or int(
                (modelo if modelo is not None else medida).size
            )
        if metadado is not None:
            metadado["arquivo_classe"] = self.nome_arquivo
            metadado.setdefault("perfil", perfil)
            metadado["indice_no_arquivo"] = indice
        captura = {
            "id_captura": str(id_captura),
            "medida": medida,
            "tempo_ms": np.array(tempo_ms, dtype=np.float64),
            "fs_hz": float(fs_hz),
            "modelo": None if modelo is None else np.array(modelo, dtype=np.float64),
            "programada": None if programada is None else np.array(programada, dtype=np.float64),
            "origem_programada": "" if origem_programada is None else str(origem_programada),
            "inicio_janela": int(inicio_janela),
            "pontos": int(pontos),
            "snr": {float(k): np.array(v) for k, v in (snr or {}).items()},
            "corrente": None if corrente is None else np.array(corrente),
            "metadado": metadado,
        }
        bloco.append(captura)
        if self.spool:
            self._gravar_spool(perfil, indice, captura)
        return indice

    # -- spool (captura a captura, para sobreviver a uma morte do processo) --

    def _arquivo_spool(self, perfil: str, indice: int) -> Path:
        return self.pasta_spool / f"{perfil}__{indice:06d}.npz"

    def _gravar_spool(self, perfil: str, indice: int, c: dict) -> None:
        self._exigir_aberto()
        arrays: Dict[str, object] = {
            "id_captura": np.array(c["id_captura"]), "classe": np.array(self.nome),
            "medida": c["medida"], "tempo_ms": c["tempo_ms"], "fs_hz": np.array(c["fs_hz"]),
            "origem_programada": np.array(c["origem_programada"]),
            "inicio_janela": np.array(c["inicio_janela"]), "pontos": np.array(c["pontos"]),
            "metadado_json": np.array(json.dumps(c["metadado"], ensure_ascii=False, sort_keys=True)),
        }
        if c["modelo"] is not None:
            arrays["modelo"] = c["modelo"]
        if c["programada"] is not None:
            arrays["programada"] = c["programada"]
        if c["corrente"] is not None:
            arrays["corrente"] = c["corrente"]
        for nivel, valores in c["snr"].items():
            arrays[f"snr/{nivel!r}"] = valores
        gravar_npz(self._arquivo_spool(perfil, indice), comprimido=False, **arrays)

    def _apagar_spool(self, perfil: Optional[str] = None) -> None:
        self._exigir_aberto()
        pasta = self.pasta_spool
        if not pasta.is_dir():
            return
        for arquivo in pasta.glob(f"{perfil}__*.npz*" if perfil else "*"):
            arquivo.unlink(missing_ok=True)
        if not any(pasta.iterdir()):
            pasta.rmdir()
            pai = pasta.parent
            if pai.name == PASTA_PARCIAL and not any(pai.iterdir()):
                pai.rmdir()

    def encerrar_perfil(self, perfil: str) -> None:
        """Descarta o spool do ``perfil`` (chamar só DEPOIS de ``consolidar``)."""
        self._exigir_aberto()
        self._apagar_spool(perfil)

    @classmethod
    def do_spool(cls, results_dir: Path, class_id: str, nome: str) -> "ArquivoDaClasse":
        """Reconstrói o acumulador a partir de ``parcial/NN_classe/`` (uma
        morte do processo no meio de um perfil)."""
        arquivo = cls(results_dir, class_id, nome, spool=False)
        for caminho in sorted(arquivo.pasta_spool.glob("*__*.npz")):
            perfil = caminho.name.split("__", 1)[0]
            if perfil not in arquivo._capturas:  # sem iniciar_perfil: ele apagaria o spool que estamos lendo
                arquivo._ordem.append(perfil)
                arquivo._capturas[perfil] = []
            with np.load(caminho, allow_pickle=False) as d:
                snr = {float(k.split("/", 1)[1]): d[k] for k in d.files if k.startswith("snr/")}
                if "classe" in d.files:
                    arquivo.nome = str(d["classe"])
                metadado = json.loads(str(d["metadado_json"]))
                arquivo.adicionar(
                    perfil, id_captura=str(d["id_captura"]), medida=d["medida"], tempo_ms=d["tempo_ms"],
                    fs_hz=float(d["fs_hz"]),
                    modelo=d["modelo"] if "modelo" in d.files else None,
                    programada=d["programada"] if "programada" in d.files else None,
                    origem_programada=str(d["origem_programada"]),
                    inicio_janela=int(d["inicio_janela"]), pontos=int(d["pontos"]),
                    snr=snr, corrente=d["corrente"] if "corrente" in d.files else None,
                    metadado=metadado,
                )
        return arquivo

    # -- montagem dos arrays ----------------------------------------------

    def _pilha(self, perfil: str, campo: str, pontos: int) -> np.ndarray:
        linhas = []
        for c in self._capturas[perfil]:
            v = c[campo]
            linhas.append(np.full(pontos, np.nan) if v is None else v)
        try:
            return np.vstack(linhas)
        except ValueError as exc:
            raise ValueError(
                f"[{self.id}] perfil {perfil}: '{campo}' com tamanhos diferentes entre capturas "
                f"({sorted({len(x) for x in linhas})}); não dá para empilhar"
            ) from exc

    def arrays_da_classe(self) -> Dict[str, np.ndarray]:
        perfis = self.perfis
        primeira = self._capturas[perfis[0]][0]
        arrays: Dict[str, np.ndarray] = {
            "formato_npz": np.array(FORMATO_NPZ),
            "classe": np.array(self.nome),
            "perfis": _como_texto(perfis),
            "tempo_ms": primeira["tempo_ms"],
            "tempo_janela_ms": np.arange(primeira["pontos"], dtype=np.float64) / primeira["fs_hz"] * 1000.0,
            **self._arrays_espelhos(),
        }
        for perfil in perfis:
            bloco = self._capturas[perfil]
            pontos = bloco[0]["pontos"]
            arrays[chave(perfil, "id_captura")] = _como_texto(c["id_captura"] for c in bloco)
            arrays[chave(perfil, "medida")] = self._pilha(perfil, "medida", 0)
            arrays[chave(perfil, "modelo")] = self._pilha(perfil, "modelo", pontos)
            arrays[chave(perfil, "programada")] = self._pilha(perfil, "programada", pontos)
            arrays[chave(perfil, "origem_programada")] = _como_texto(c["origem_programada"] for c in bloco)
            arrays[chave(perfil, "inicio_janela")] = np.array([c["inicio_janela"] for c in bloco], dtype=np.int64)
        return arrays

    def _arrays_espelhos(self) -> Dict[str, np.ndarray]:
        espelhos = self.espelhos
        if not espelhos:
            return {}
        return {CHAVE_ESPELHOS: _como_texto(espelhos), CHAVE_ORIGENS: _como_texto(espelhos.values())}

    def _arrays_snr(self) -> Dict[float, Dict[str, np.ndarray]]:
        niveis = sorted({n for p in self.perfis for c in self._capturas[p] for n in c["snr"]})
        saida: Dict[float, Dict[str, np.ndarray]] = {}
        for nivel in niveis:
            arrays: Dict[str, np.ndarray] = {
                "formato_npz": np.array(FORMATO_NPZ), "classe": np.array(self.nome),
                "perfis": _como_texto(self.perfis), **self._arrays_espelhos(),
            }
            for perfil in self.perfis:
                bloco = self._capturas[perfil]
                tamanho = next(c["snr"][nivel].size for c in bloco if nivel in c["snr"])
                linhas = [c["snr"].get(nivel, np.full(tamanho, np.nan)) for c in bloco]
                arrays[chave(perfil, "tensao_pu")] = np.vstack(linhas)
                arrays[chave(perfil, "id_captura")] = _como_texto(c["id_captura"] for c in bloco)
                arrays.setdefault("tempo_ms", np.arange(tamanho, dtype=np.float64) / bloco[0]["fs_hz"] * 1000.0)
            saida[nivel] = arrays
        return saida

    def _arrays_corrente(self) -> Optional[Dict[str, np.ndarray]]:
        if not any(c["corrente"] is not None for p in self.perfis for c in self._capturas[p]):
            return None
        arrays: Dict[str, np.ndarray] = {
            "formato_npz": np.array(FORMATO_NPZ), "classe": np.array(self.nome),
            "perfis": _como_texto(self.perfis), **self._arrays_espelhos(),
        }
        for perfil in self.perfis:
            bloco = self._capturas[perfil]
            tamanho = next(c["corrente"].size for c in bloco if c["corrente"] is not None)
            linhas = [np.full(tamanho, np.nan) if c["corrente"] is None else c["corrente"] for c in bloco]
            arrays[chave(perfil, "corrente_pu")] = np.vstack(linhas)
            arrays[chave(perfil, "id_captura")] = _como_texto(c["id_captura"] for c in bloco)
        arrays["tempo_ms"] = self._capturas[self.perfis[0]][0]["tempo_ms"]
        return arrays

    # -- gravação ---------------------------------------------------------

    def consolidar(self, *, so_snr: bool = False) -> Optional[Path]:
        """Grava ``NN_classe.npz`` (+ ``snr_XXdb/`` + ``corrente/``) com tudo
        o que foi acumulado. Todos os ``.part`` são escritos antes de qualquer
        promoção: um erro no meio nunca deixa a classe meio gravada. Sem
        nenhuma captura, não toca em nada e devolve ``None``. ``so_snr`` grava
        só os ``snr_XXdb/NN_classe.npz`` (``scripts/gerar_ruido_janela.py``)."""
        self._exigir_aberto()
        if not self.perfis:
            return None
        # (destino, arrays, comprimido). O ruído branco dos snr_XXdb/ quase não
        # comprime (medido: -4,6 %) e custaria CPU a cada reescrita: sem compressão.
        alvos: List[Tuple[Path, Dict[str, np.ndarray], bool]] = [] if so_snr else [
            (self.results_dir / self.nome_arquivo, self.arrays_da_classe(), True),
        ]
        for nivel, arrays in self._arrays_snr().items():
            alvos.append((self.results_dir / pasta_snr(nivel) / self.nome_arquivo, arrays, False))
        corrente = None if so_snr else self._arrays_corrente()
        if corrente is not None:
            alvos.append((self.results_dir / "corrente" / nome_arquivo_corrente(self.id, self.nome), corrente, True))
        parciais: List[Tuple[Path, Path]] = []
        try:
            for destino, arrays, comprimido in alvos:
                destino.parent.mkdir(parents=True, exist_ok=True)
                parcial = destino.with_suffix(".npz.part")
                with parcial.open("wb") as handle:
                    (np.savez_compressed if comprimido else np.savez)(handle, **arrays)
                parciais.append((parcial, destino))
        except BaseException:
            for parcial, _ in parciais:
                parcial.unlink(missing_ok=True)
            raise
        for parcial, destino in parciais:
            os.replace(parcial, destino)
        return self.results_dir / self.nome_arquivo


def recuperar_parcial(sessao_dir: Path) -> List[Path]:
    """Recuperação explícita (inclusive legada), sempre sob lock exclusivo.

    Não execute sobre uma sessão legada ainda em escrita: versões anteriores
    ao protocolo não participam do lock OS e só podem ser recuperadas offline.
    """
    sessao_dir = Path(sessao_dir)
    if not (sessao_dir / PASTA_PARCIAL).is_dir():
        return []
    with BloqueioSessao(sessao_dir, escritor=False):
        return _recuperar_parcial_sem_bloqueio(sessao_dir)


def _recuperar_parcial_sem_bloqueio(sessao_dir: Path) -> List[Path]:
    """Promove ao formato 2 as capturas que ficaram em ``parcial/NN_classe/``
    (processo morto no meio de um perfil). Os outros perfis do arquivo da
    classe, se já existiam, são preservados. Devolve os ``.npz`` de classe
    reescritos. O metadata dessas capturas fica no próprio spool
    (``metadado_json``) e é acrescentado ao ``metadata/NN_classe.jsonl``."""
    sessao_dir = Path(sessao_dir)
    base = sessao_dir / PASTA_PARCIAL
    gravados: List[Path] = []
    if not base.is_dir():
        return gravados
    for pasta in sorted(p for p in base.iterdir()
                        if p.is_dir() and not p.is_symlink() and re.fullmatch(r"\d{2}_.+", p.name)):
        if any(p.is_symlink() for p in pasta.iterdir()):
            raise ValueError(f"spool com link simbólico não pode ser recuperado: {pasta}")
        class_id, _, nome_min = pasta.name.partition("_")
        existente = sessao_dir / f"{pasta.name}.npz"
        bruto = ArquivoDaClasse.do_spool(sessao_dir, class_id, nome_min)
        if not bruto.perfis:
            continue
        novos = set(bruto.perfis)
        # Só as linhas do spool substituem metadata: os perfis já consolidados
        # serão relidos para os arrays, mas não devem ser acrescentados de novo.
        novas = [json.dumps(r, ensure_ascii=False, sort_keys=True) for r in bruto.registros()]
        destino = sessao_dir / "metadata" / f"{pasta.name}.jsonl"
        anteriores = []
        if destino.is_file():
            for linha in destino.read_text(encoding="utf-8").splitlines():
                if not linha.strip():
                    continue
                anterior = json.loads(linha)
                if anterior.get("perfil", PERFIL_LEGADO) not in novos \
                        and anterior.get("perfil_de_origem") not in novos:
                    anteriores.append(linha)
        metadados = carregar_metadados(sessao_dir)
        # Antigos (outros perfis): relidos do arquivo de classe e re-adicionados.
        if existente.is_file():
            snr_antigo: Dict[Tuple[str, str], Dict[float, np.ndarray]] = {}
            for pasta_nivel in sorted(sessao_dir.glob("snr_*db")):
                nivel = nivel_da_pasta_snr(pasta_nivel.name)
                for c in ler_pasta(pasta_nivel, metadados, classes=[class_id]):
                    if nivel is not None and c.formato == "classe":
                        snr_antigo.setdefault(c.chave, {})[nivel] = c.sinal
            correntes = {c.chave: c.sinal for c in ler_pasta(
                sessao_dir / "corrente", metadados, classes=[class_id]) if c.formato == "classe"}
            espelhos_antigos: Dict[str, str] = {}
            for captura in ler_pasta(sessao_dir, metadados, versoes=VERSOES, classes=[class_id], perfis=None):
                if captura.formato == "classe" and captura.espelho and captura.arquivo == existente:
                    espelhos_antigos[captura.perfil] = str(captura.perfil_de_origem)
                    continue  # espelho: dado só no bloco da origem (re-espelhado abaixo)
                if captura.formato != "classe" or captura.perfil in novos or captura.arquivo != existente:
                    continue
                snr = snr_antigo.get(captura.chave, {})
                bruto.adicionar(
                    captura.perfil, id_captura=captura.id_captura, medida=captura.versoes["medida"],
                    tempo_ms=captura.tempo_ms if captura.tempo_ms is not None else np.arange(captura.sinal.size),
                    fs_hz=float((captura.metadado or {}).get("fs_hz", 30_000.0)),
                    modelo=captura.versoes.get("modelo"), programada=captura.versoes.get("programada"),
                    origem_programada=captura.origem_programada,
                    inicio_janela=captura.inicio_janela or 0, snr=snr,
                    corrente=correntes.get(captura.chave), metadado=captura.metadado,
                )
            # Espelhos cuja origem e cujo próprio perfil não foram refeitos continuam valendo.
            por_origem: Dict[str, List[str]] = {}
            for espelho, origem in espelhos_antigos.items():
                if origem not in novos and espelho not in novos and origem in bruto.perfis:
                    por_origem.setdefault(origem, []).append(espelho)
            for origem, destinos in por_origem.items():
                bruto.espelhar(origem, destinos)
        caminho = bruto.consolidar()
        if caminho is not None:
            gravados.append(caminho)
            destino.parent.mkdir(parents=True, exist_ok=True)
            parcial = destino.with_suffix(".jsonl.part")
            parcial.write_text("\n".join(anteriores + novas) + "\n", encoding="utf-8")
            os.replace(parcial, destino)
            bruto._apagar_spool()
    return gravados


def recuperar_sessoes_interrompidas(base_dir: Path, *, avisar=print) -> List[Path]:
    """Recupera apenas filhos diretos ``sessao_*/parcial`` antes de nova sessão.

    Somente sessões com marcador do protocolo OS são elegíveis; sessões
    legadas sem marcador exigem recuperação explícita com escritor encerrado.
    O lock permanece adquirido durante leitura, consolidação e remoção.
    Não importa nem aciona hardware. Um erro é registrado e deixa o spool
    disponível para nova tentativa; outras sessões ainda são examinadas.
    Chamada explícita pelo coordenador, nunca executada ao importar o módulo.
    """
    base_dir = Path(base_dir)
    gravados: List[Path] = []
    if not base_dir.is_dir():
        return gravados
    for sessao in sorted(base_dir.glob("sessao_*")):
        parcial = sessao / PASTA_PARCIAL
        if sessao.is_symlink() or not sessao.is_dir() or parcial.is_symlink() or not parcial.is_dir():
            continue
        if not (sessao / ARQUIVO_BLOQUEIO).is_file():
            if avisar is not None:
                avisar(f"Recuperação: sessão legada sem protocolo de lock em {sessao}; "
                       "use recuperar_parcial explicitamente com o escritor encerrado.")
            continue
        try:
            with BloqueioSessao(sessao, escritor=False):
                if avisar is not None:
                    avisar(f"Recuperação: verificando capturas interrompidas em {sessao}.")
                recuperados = _recuperar_parcial_sem_bloqueio(sessao)
        except SessaoEmUsoError:
            if avisar is not None:
                avisar(f"Recuperação: sessão ativa em {sessao}; ignorada sem alterar capturas.")
            continue
        except Exception as exc:
            if avisar is not None:
                avisar(f"Recuperação pendente em {sessao}: {exc}. Spool preservado para nova tentativa.")
            continue
        gravados.extend(recuperados)
        if avisar is not None:
            avisar(f"Recuperação: {len(recuperados)} classe(s) consolidada(s) em {sessao}; nenhuma captura refeita.")
    return gravados


# ---------------------------------------------------------------- metadata

class MetadadosDaSessao(dict):
    """``id_captura`` -> linha do metadata (o último vence, como sempre), mais
    a busca correta com perfis: ``buscar(perfil, id_captura)``. O mesmo
    ``id_captura`` existe em cada perfil de uma sessão ``set perfil todos``
    (a seed da captura não depende do perfil)."""

    def __init__(self) -> None:
        super().__init__()
        self.por_chave: Dict[Tuple[str, str], dict] = {}
        self.registros: List[dict] = []

    def acrescentar(self, registro: dict) -> None:
        id_captura = str(registro["id_captura"])
        perfil = str(registro.get("perfil") or PERFIL_LEGADO)
        self[id_captura] = registro
        self.por_chave[(perfil, id_captura)] = registro
        self.registros.append(registro)

    def buscar(self, perfil: Optional[str], id_captura: str) -> Optional[dict]:
        """Linha do (perfil, id); sem ``perfil`` (arquivo do formato 1), a
        única linha com esse id, ou a de ``literatura`` se houver várias."""
        if perfil is not None:
            return self.por_chave.get((perfil, id_captura))
        return self.get(id_captura) if (PERFIL_LEGADO, id_captura) not in self.por_chave \
            else self.por_chave[(PERFIL_LEGADO, id_captura)]


def carregar_metadados(sessao_dir: Path) -> MetadadosDaSessao:
    """Todos os ``metadata/*.jsonl`` da sessão."""
    metadados = MetadadosDaSessao()
    metadata_dir = Path(sessao_dir) / "metadata"
    if not metadata_dir.is_dir():
        return metadados
    for jsonl_path in sorted(metadata_dir.glob("*.jsonl")):
        for linha in jsonl_path.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                metadados.acrescentar(json.loads(linha))
    return metadados


def buscar_metadado(metadados: Optional[Mapping], perfil: Optional[str], id_captura: str) -> Optional[dict]:
    """``MetadadosDaSessao.buscar`` ou, para um ``dict`` simples id -> linha, ``get``."""
    if metadados is None:
        return None
    if hasattr(metadados, "buscar"):
        return metadados.buscar(perfil, id_captura)
    return metadados.get(id_captura)


# ---------------------------------------------------------------- leitura

@dataclass
class CapturaSessao:
    """Uma captura lida de uma sessão, em qualquer formato."""

    arquivo: Path
    classe_id: str
    classe: str
    perfil: str
    id_captura: str
    linha: int  # posição no bloco (arquivo, perfil); 0-based
    formato: str  # "classe" (formato 2) | "por_captura" | "empilhado" (formato 1)
    sinal: np.ndarray
    grandeza: str
    versoes: Dict[str, np.ndarray] = field(default_factory=dict)
    origem_programada: Optional[str] = None
    inicio_janela: Optional[int] = None
    tempo_ms: Optional[np.ndarray] = None
    metadado: Optional[dict] = None
    # Captura compartilhada entre perfis (``set perfil todos``, classe cujo
    # gerar() não depende do perfil): os dados existem UMA vez, no bloco de
    # ``perfil_de_origem``; ``perfis_compartilhados`` lista todos os perfis
    # que apontam para ela (origem primeiro).
    compartilhada: bool = False
    perfil_de_origem: Optional[str] = None
    perfis_compartilhados: Tuple[str, ...] = ()

    @property
    def chave(self) -> Tuple[str, str]:
        return (self.perfil, self.id_captura)

    @property
    def espelho(self) -> bool:
        """``True`` quando o perfil desta captura não tem bloco próprio: ela
        é a captura de ``perfil_de_origem`` vista sob outro perfil."""
        return self.compartilhada and self.perfil != self.perfil_de_origem


def classe_do_arquivo(caminho: Path) -> str:
    return caminho.name.split("_", 1)[0]


def parsear_selecao_capturas(texto: Optional[str]) -> Tuple[Set[str], Set[int]]:
    """``--capturas``: ids (``02-0003``) e/ou posições 1-based dentro de cada
    (classe, perfil), com intervalos (``1-3,7``). Vazio = tudo."""
    ids: Set[str] = set()
    posicoes: Set[int] = set()
    for token in (texto or "").replace(" ", "").split(","):
        if not token:
            continue
        if re.fullmatch(r"\d{2}-\d{4,}", token):
            ids.add(token)
        elif re.fullmatch(r"\d+", token):
            posicoes.add(int(token))
        elif re.fullmatch(r"\d+-\d+", token):
            a, b = (int(x) for x in token.split("-"))
            if b < a:
                raise ValueError(f"intervalo de capturas invertido: {token!r}")
            posicoes.update(range(a, b + 1))
        else:
            raise ValueError(
                f"captura {token!r} inválida: use ids (02-0003), posições (3) ou intervalos (1-3)"
            )
    return ids, posicoes


def _linhas_escolhidas(
    ids: Sequence[str], selecao: Tuple[Set[str], Set[int]], ja_contadas: int, limite: Optional[int],
) -> List[int]:
    sel_ids, sel_pos = selecao
    escolhidas: List[int] = []
    for linha, id_captura in enumerate(ids):
        if (sel_ids or sel_pos) and id_captura not in sel_ids and (linha + 1) not in sel_pos:
            continue
        if limite is not None and ja_contadas + len(escolhidas) >= limite:
            break
        escolhidas.append(linha)
    return escolhidas


def formato_do_arquivo(caminho: Path) -> str:
    """``"classe"`` (formato 2) ou ``"legado"`` (formato 1)."""
    with np.load(caminho, allow_pickle=True) as dados:
        return "classe" if "formato_npz" in dados.files else "legado"


def _versao_legada(dados_dir: Path, nome: str, versoes: Sequence[str]) -> Optional[dict]:
    """``tres_versoes/<nome>`` do formato 1: modelo_pu / programada_pu / origem."""
    if not ({"modelo", "programada"} & set(versoes)):
        return None
    caminho = dados_dir / PASTA_TRES_VERSOES / nome
    if not caminho.is_file():
        return None
    with np.load(caminho, allow_pickle=True) as d:
        saida: dict = {}
        for versao in ("modelo", "programada"):
            if f"{versao}_pu" in d.files:
                saida[versao] = np.atleast_2d(np.asarray(d[f"{versao}_pu"], dtype=np.float64))
        if "origem_programada" in d.files:
            saida["origem"] = np.atleast_1d(d["origem_programada"])
        return saida


def _tem_valor(linha: Optional[np.ndarray]) -> bool:
    return linha is not None and bool(np.any(np.isfinite(linha)))


def ler_pasta(
    dados_dir: Path,
    metadados: Optional[Mapping] = None,
    *,
    versoes: Sequence[str] = ("medida",),
    classes: Optional[Sequence[str]] = None,
    perfis: Optional[Sequence[str]] = None,
    capturas: Optional[str] = None,
    max_por_bloco: Optional[int] = None,
    limite_padrao_empilhado: Optional[int] = None,
    avisar=None,
) -> List[CapturaSessao]:
    """Capturas dos ``*.npz`` de UMA pasta (a da sessão, ``snr_XXdb/``,
    ``corrente/`` ou ``sem_margem/``), nos formatos 1 e 2.

    * ``versoes``: quais de ``medida``/``modelo``/``programada`` carregar (só
      a pasta da sessão as tem; ``sinal`` é a primeira disponível na ordem
      ``medida``, ``modelo``, ``programada``). Nas pastas de SNR e corrente
      o ``sinal`` é sempre a série do arquivo.
    * ``classes``: prefixos ``NN``; ``perfis``: nomes; ``capturas``: texto de
      ``parsear_selecao_capturas``.
    * ``max_por_bloco``: no máximo N capturas por (classe, perfil).
      ``limite_padrao_empilhado`` vale quando ``max_por_bloco`` é ``None`` e
      o arquivo tem mais de uma captura no bloco (relatório HTML).
    """
    dados_dir = Path(dados_dir)
    versoes = tuple(v for v in VERSOES if v in versoes)
    selecao = parsear_selecao_capturas(capturas)
    contagem: Dict[Tuple[str, str], int] = {}
    vistas: Dict[Tuple[str, str], int] = {}
    saida: List[CapturaSessao] = []

    for caminho in sorted(dados_dir.glob("*.npz")):
        class_id = classe_do_arquivo(caminho)
        if classes and class_id not in classes:
            continue
        with np.load(caminho, allow_pickle=True) as dados:
            if "formato_npz" in dados.files:
                _ler_formato2(dados, caminho, class_id, metadados, versoes, perfis, selecao,
                              max_por_bloco, limite_padrao_empilhado, contagem, saida, avisar)
            else:
                _ler_formato1(dados, caminho, dados_dir, class_id, metadados, versoes, perfis, selecao,
                              max_por_bloco, limite_padrao_empilhado, contagem, vistas, saida, avisar)
    return saida


def _limite_do_bloco(max_por_bloco, limite_padrao, tamanho_bloco, avisar, nome, perfil):
    if max_por_bloco is not None:
        return max_por_bloco
    if limite_padrao is not None and tamanho_bloco > 1:
        if avisar is not None:
            avisar(f"{nome} [{perfil}]: {tamanho_bloco} capturas empilhadas; só as {limite_padrao} "
                   "primeiras entram (use --capturas ou --max-capturas-por-classe)")
        return limite_padrao
    return None


def _ler_formato2(dados, caminho, class_id, metadados, versoes, perfis_filtro, selecao,
                  max_por_bloco, limite_padrao, contagem, saida, avisar) -> None:
    classe = str(dados["classe"])
    tempo_ms = np.asarray(dados["tempo_ms"], dtype=np.float64) if "tempo_ms" in dados.files else None
    reais = [str(p) for p in np.atleast_1d(dados["perfis"])]
    # (perfil pedido, perfil cujo bloco guarda os dados): os espelhos de uma
    # captura compartilhada apontam para o bloco da origem.
    blocos = [(p, p) for p in reais]
    if CHAVE_ESPELHOS in dados.files:
        for espelho, origem in zip(np.atleast_1d(dados[CHAVE_ESPELHOS]), np.atleast_1d(dados[CHAVE_ORIGENS])):
            if str(origem) in reais:
                blocos.append((str(espelho), str(origem)))
    grupos: Dict[str, List[str]] = {}
    for perfil, origem in blocos:
        grupos.setdefault(origem, []).append(perfil)
    if len(blocos) > len(reais):  # ordem canônica dos perfis, com os espelhos no lugar
        ordem = {p: i for i, p in enumerate(("norma", "literatura", "fronteira"))}
        blocos.sort(key=lambda b: ordem.get(b[0], len(ordem)))
    for perfil, origem in blocos:
        if perfis_filtro and perfil not in perfis_filtro:
            continue
        ids = [str(i) for i in np.atleast_1d(dados[chave(origem, "id_captura")])]
        if not ids:
            continue
        itens = [i for i in ("medida", "tensao_pu", "corrente_pu") if chave(origem, i) in dados.files]
        if not itens:
            continue
        item_sinal = itens[0]
        grandeza = GRANDEZAS[item_sinal]
        # O limite padrão do relatório é para o dataset SIMULADO (milhares de
        # capturas); numa sessão de bancada, empilhada por classe, entra tudo.
        simulado = bool((buscar_metadado(metadados, perfil, ids[0]) or {}).get("simulado", False))
        limite = _limite_do_bloco(
            max_por_bloco, limite_padrao if simulado else None, len(ids), avisar, caminho.name, perfil,
        )
        ja = contagem.get((class_id, perfil), 0)
        linhas = _linhas_escolhidas(ids, selecao, ja, limite)
        if not linhas:
            continue
        contagem[(class_id, perfil)] = ja + len(linhas)
        if item_sinal == "medida":
            carregar = [v for v in versoes if chave(origem, v) in dados.files]
            if not carregar:
                continue
        else:
            carregar = [item_sinal]
        matrizes = {v: np.atleast_2d(dados[chave(origem, v)]) for v in carregar}
        origens = np.atleast_1d(dados[chave(origem, "origem_programada")]) \
            if chave(origem, "origem_programada") in dados.files else None
        inicios = np.atleast_1d(dados[chave(origem, "inicio_janela")]) \
            if chave(origem, "inicio_janela") in dados.files else None
        compartilhados = tuple(grupos[origem]) if len(grupos[origem]) > 1 else ()
        if compartilhados:  # origem primeiro, depois a ordem do arquivo
            compartilhados = (origem, *[p for p in compartilhados if p != origem])
        for linha in linhas:
            if item_sinal == "medida":
                versoes_linha = {v: np.asarray(m[linha]) for v, m in matrizes.items() if _tem_valor(m[linha])}
                if not versoes_linha:
                    continue
                sinal = next(versoes_linha[v] for v in VERSOES if v in versoes_linha)
            else:  # snr_XXdb/ e corrente/: a série do arquivo, sem versões
                versoes_linha = {}
                sinal = np.asarray(matrizes[item_sinal][linha])
            saida.append(CapturaSessao(
                arquivo=caminho, classe_id=class_id, classe=classe, perfil=perfil, id_captura=ids[linha],
                linha=linha, formato="classe", sinal=sinal, grandeza=grandeza, versoes=versoes_linha,
                origem_programada=(str(origens[linha]) or None) if origens is not None else None,
                inicio_janela=int(inicios[linha]) if inicios is not None else None,
                tempo_ms=tempo_ms if item_sinal != "tensao_pu" else None,
                metadado=buscar_metadado(metadados, perfil, ids[linha]),
                compartilhada=bool(compartilhados), perfil_de_origem=origem if compartilhados else None,
                perfis_compartilhados=compartilhados,
            ))


def _ler_formato1(dados, caminho, dados_dir, class_id, metadados, versoes, perfis_filtro, selecao,
                  max_por_bloco, limite_padrao, contagem, vistas, saida, avisar) -> None:
    item = "tensao_pu" if "tensao_pu" in dados.files else "corrente_pu" if "corrente_pu" in dados.files else None
    if item is None:
        if avisar is not None:
            avisar(f"{caminho.name}: sem tensao_pu/corrente_pu; ignorado")
        return
    matriz = np.atleast_2d(np.asarray(dados[item], dtype=np.float64))
    ids = [str(i) for i in np.atleast_1d(dados["id_captura"])] if "id_captura" in dados.files \
        else [f"{caminho.stem}-{k}" for k in range(matriz.shape[0])]
    classe = str(dados["classe"]) if "classe" in dados.files else caminho.stem
    tempo_ms = np.asarray(dados["tempo_ms"], dtype=np.float64) if "tempo_ms" in dados.files else None
    legado = _versao_legada(dados_dir, caminho.name, versoes) if item == "tensao_pu" else None
    formato = "empilhado" if matriz.shape[0] > 1 else "por_captura"
    # O limite padrão do formato 1 conta o arquivo inteiro (como sempre foi).
    limite = _limite_do_bloco(max_por_bloco, limite_padrao, matriz.shape[0], avisar, caminho.name, "-")
    for linha in range(matriz.shape[0]):
        md = buscar_metadado(metadados, None, ids[linha])
        perfil = str((md or {}).get("perfil") or PERFIL_LEGADO)
        if perfis_filtro and perfil not in perfis_filtro:
            continue
        ja = contagem.get((class_id, perfil), 0)
        posicao = vistas.get((class_id, perfil), 0) + 1
        vistas[(class_id, perfil)] = posicao
        if (selecao[0] or selecao[1]) and ids[linha] not in selecao[0] and posicao not in selecao[1]:
            continue
        if limite is not None and ja >= limite:
            break
        contagem[(class_id, perfil)] = ja + 1
        versoes_linha: Dict[str, np.ndarray] = {}
        origem = None
        if item == "tensao_pu" and "medida" in versoes:
            versoes_linha["medida"] = matriz[linha]
        if legado:
            for v in ("modelo", "programada"):
                if v in versoes and v in legado and linha < legado[v].shape[0] and _tem_valor(legado[v][linha]):
                    versoes_linha[v] = legado[v][linha]
            if "origem" in legado and linha < legado["origem"].size:
                origem = str(legado["origem"][linha]) or None
        if item == "tensao_pu" and not versoes_linha:
            continue
        if item == "tensao_pu":
            sinal = next(versoes_linha[v] for v in VERSOES if v in versoes_linha)
        else:
            sinal = matriz[linha]
        saida.append(CapturaSessao(
            arquivo=caminho, classe_id=class_id, classe=classe, perfil=perfil, id_captura=ids[linha],
            linha=linha, formato=formato, sinal=sinal, grandeza=GRANDEZAS[item], versoes=versoes_linha,
            origem_programada=origem, inicio_janela=(md or {}).get("inicio_janela"),
            tempo_ms=tempo_ms, metadado=md,
        ))


def ler_capturas(
    sessao_dir: Path, *, subpasta: Optional[str] = None, **opcoes,
) -> List[CapturaSessao]:
    """``ler_pasta`` na sessão (ou numa subpasta: ``snr_30db``, ``corrente``,
    ``sem_margem``) com o metadata da própria sessão."""
    sessao_dir = Path(sessao_dir)
    metadados = opcoes.pop("metadados", None)
    if metadados is None:
        metadados = carregar_metadados(sessao_dir)
    pasta = sessao_dir / subpasta if subpasta else sessao_dir
    return ler_pasta(pasta, metadados, **opcoes)
