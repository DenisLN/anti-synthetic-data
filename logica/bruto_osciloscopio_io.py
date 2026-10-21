"""Preserva a exportação BYTE em arquivo independente, sem modificar o dataset."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

import numpy as np


def sha256_array(valores) -> str:
    """Hash dos valores na representação float64 little-endian contígua."""
    return hashlib.sha256(np.asarray(valores, dtype='<f8').tobytes(order='C')).hexdigest()


def salvar_bruto(sessao_dir, perfil, id_captura, canal, bruto, sinal_salvo, *, metadata_extra=None) -> Path:
    """Salva NPZ novo e retorna o caminho relativo à sessão.

    O hash liga a exportação aos valores float64 realmente persistidos no
    dataset (por exemplo tensão em pu). Sua unidade deve vir no metadata.
    `tempo_s` começa em zero; `tempo_trigger_s` conserva o trigger original.
    Os dados são a exportação NORMal/BYTE, não a memória interna completa.
    """
    for nome, valor in (('perfil', perfil), ('id_captura', id_captura)):
        if not isinstance(valor, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', valor):
            raise ValueError(f'{nome} deve ser um identificador simples')
    if isinstance(canal, bool) or canal not in (1, 2, 3, 4) or bruto['canal'] != canal:
        raise ValueError('Canal inválido ou diferente do snapshot')
    tempo = np.asarray(bruto['tempo_s'], dtype=np.float64)
    tempo_trigger = np.asarray(bruto['tempo_trigger_s'], dtype=np.float64)
    valores = np.asarray(bruto['valores'], dtype=np.float64)
    codigos = np.asarray(bruto['codigos_byte'])
    preamble = np.asarray(bruto['preamble'], dtype=np.float64)
    salvo = np.asarray(sinal_salvo, dtype=np.float64)
    if tempo.ndim != 1 or tempo.size < 2 or any(a.shape != tempo.shape for a in (tempo_trigger, valores, codigos)):
        raise ValueError('Vetores brutos devem ser unidimensionais e ter o mesmo tamanho')
    if codigos.dtype != np.uint8 or preamble.shape != (10,):
        raise ValueError('Snapshot requer códigos BYTE uint8 e preamble de dez campos')
    if any(not np.all(np.isfinite(a)) for a in (tempo, tempo_trigger, valores, preamble, salvo)):
        raise ValueError('Snapshot ou sinal salvo contém valores não finitos')
    if tempo[0] != 0 or np.any(np.diff(tempo) <= 0):
        raise ValueError('Tempo bruto deve começar em zero e crescer estritamente')
    if salvo.ndim != 1 or salvo.size == 0:
        raise ValueError('Sinal salvo deve ser vetor não vazio')
    meta = {
        'versao_schema': 1, 'perfil': perfil, 'id_captura': id_captura, 'canal': int(canal),
        'origem': str(bruto['origem']), 'instrumento_idn': str(bruto.get('instrumento_idn', '')),
        'formato_exportacao': 'BYTE', 'modo_exportacao': 'NORMal',
        'fs_destino_hz': float(bruto['fs_destino_hz']),
        'pontos_destino': int(bruto['pontos_destino']),
        'sinal_salvo_sha256': sha256_array(salvo),
        'sinal_salvo_hash_formato': 'float64 little-endian, bytes C',
        'sinal_salvo_amostras': int(salvo.size),
        'metadata_extra': dict(metadata_extra or {}),
    }
    texto_meta = json.dumps(meta, ensure_ascii=False, sort_keys=True, allow_nan=False)
    relativo = Path('bruto_osciloscopio') / perfil / f'{id_captura}-ch{canal}-{uuid4().hex}.npz'
    final = Path(sessao_dir) / relativo
    final.parent.mkdir(parents=True, exist_ok=True)
    # open('xb') não sobrescreve nada, nem em colisão de nome. O cleanup
    # só ocorre depois de este processo ter criado seu próprio arquivo.
    handle = final.open('xb')
    try:
        with handle:
            np.savez(
                handle, tempo_s=tempo, tempo_trigger_s=tempo_trigger,
                **{('tensao_v' if canal == 1 else 'corrente_a' if canal == 2 else 'valores'): valores},
                codigos_byte=codigos, preamble=preamble,
                preamble_texto=np.array(bruto['preamble_texto']),
                canal=np.array(canal), perfil=np.array(perfil), id_captura=np.array(id_captura),
                metadata_json=np.array(texto_meta),
                sinal_salvo_sha256=np.array(meta['sinal_salvo_sha256']),
            )
    except BaseException:
        final.unlink(missing_ok=True)
        raise
    return relativo
