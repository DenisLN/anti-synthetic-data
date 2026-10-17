# modelo_lista_fonte.py: hipóteses sobre o que a fonte toca

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` {bdg-warning}`NÃO VERIFICADO` Lido por inteiro em 2026-10-16 (`main` em `fa82f49`). **Nada neste módulo é fato sobre o equipamento.**

**Pergunta:** para que serve `modelo_lista_fonte.py`? **Resposta:** para confrontar, com o que `scripts/diag_marcadores_trace.py` medir na bancada, **hipóteses** sobre por que o evento das classes 08 e 09 aparece repetido ou deslocado em 100,0 ms (quirks A22 e A25, pendência P-02). Cada hipótese é uma função pura que, dada uma `ProgramacaoCaptura`, devolve a forma que a fonte emitiria **se** aquele mecanismo fosse verdadeiro; `confrontar` ordena as hipóteses pelo rms do resíduo contra a medida. A vencedora não é prova: é a que menos erra naquele dado.

| Símbolo | Assinatura | Linha | Papel |
|---|---|---|---|
| `HIPOTESES_CANDIDATAS` | (constante ou variável de módulo) | [modelo_lista_fonte.py:32](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/modelo_lista_fonte.py#L32) | nome → (mecanismo, parâmetros); valores numéricos são chutes de partida, não medidas |
| `_formas_unitarias` | `(programacao) -> np.ndarray` | [modelo_lista_fonte.py:53-68](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/modelo_lista_fonte.py#L53-L68) | a forma que cada TRACe toca, com rms 1, na grade de 30 kSa/s (a inversa de `_resample_cycle`) |
| `_ideal` | `(programacao, formas: np.ndarray) -> np.ndarray` | [modelo_lista_fonte.py:84-86](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/modelo_lista_fonte.py#L84-L86) | o contrato de `programada_pu()`: cada passo toca a sua TRACe escalada ao seu rms |
| `_atraso_de_passos` | `(programacao, formas, *, d: int=1, t_inicio_s: float=0.1, tensao: str='propria') -> np.ndarray` | [modelo_lista_fonte.py:89-101](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/modelo_lista_fonte.py#L89-L101) | a partir de `t_inicio_s` a fonte toca no passo j a forma do passo j−d |
| `_transicao_forma_anterior` | `(programacao, formas, *, amostras: int=3, t_inicio_s: float=0.0) -> np.ndarray` | [modelo_lista_fonte.py:104-117](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/modelo_lista_fonte.py#L104-L117) | nas primeiras amostras de cada passo ainda toca a forma anterior com a tensão nova |
| `_copia_no_instante` | `(programacao, formas, *, t_s: float=0.1, ciclo_origem: Optional[int]=None, inicio_na_origem: int=0, n_amostras: Optional[int]=None, ganho: float=1....` | [modelo_lista_fonte.py:120-146](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/modelo_lista_fonte.py#L120-L146) | num instante FIXO acrescenta ou impõe um trecho do passo de maior pico |
| `_deslocamento_no_tempo` | `(programacao, formas, *, t_inicio_s: float=0.1, atraso_s: float=0.02) -> np.ndarray` | [modelo_lista_fonte.py:149-159](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/modelo_lista_fonte.py#L149-L159) | a partir de um instante, a forma ideal deslocada |
| `MECANISMOS` | (constante ou variável de módulo) | [modelo_lista_fonte.py:162](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/modelo_lista_fonte.py#L162) | os cinco mecanismos implementados |
| `prever_forma` | `(programacao, mecanismo: str='ideal', **parametros) -> np.ndarray` | [modelo_lista_fonte.py:171-184](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/modelo_lista_fonte.py#L171-L184) | forma emitida sob um mecanismo; soma o offset CC no fim |
| `confrontar` | `(programacao, medida_pu: np.ndarray, hipoteses: Optional[Dict[str, Tuple[str, dict]]]=None) -> List[dict]` | [modelo_lista_fonte.py:187-209](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/modelo_lista_fonte.py#L187-L209) | ordena as hipóteses pelo rms do resíduo; devolve nome, rms, máximo e amostra do máximo |

## 1. Como funciona

```{mermaid}
flowchart LR
    P["ProgramacaoCaptura<br/>(montar_programacao)"] --> F["_formas_unitarias<br/>(rms 1 por passo)"]
    F --> H["um mecanismo<br/>(_atraso_de_passos, _copia_no_instante, ...)"]
    H --> S["forma prevista (pu)"]
    S --> C["confrontar(medida)"]
    C --> R["ranking por rms do resíduo"]
```

`mecanismo="ideal"` reproduz **exatamente** `ProgramacaoCaptura.programada_pu()` (teste em [tests/test_offline.py:7534](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/tests/test_offline.py#L7534), tolerância 1e-12); os outros quatro deslocam passos, copiam o evento num instante fixo (`t_s = 0,100` s, ganho 1,0 ou 0,15), trocam a forma só nas primeiras amostras do passo (3 ou 30) ou deslocam o resto em 20 ms.

## 2. Invariantes e armadilhas

1. É **função pura**: sem SCPI, sem estado, sem instrumento.
2. `confrontar` compara só o comprimento comum de `medida` e da previsão (não reamostra nem realinha); a medida tem de vir alinhada ao início do LIST.
3. Quem confiar no ranking **sem a medida de bancada** comete o erro que o cabeçalho do módulo proíbe: as cinco hipóteses de A22/A25 continuam sem confirmação (P-02).
4. `FS_HZ = 30_000` é uma constante local (não vem de `AmetekMX30.FS_HZ`): se a taxa mudar, as duas precisam mudar.
5. A montagem da TRACe já foi **descartada** como causa (teste `test_montagem_da_trace_nao_desloca_o_impulso_a_50_nem_a_60hz`); o mecanismo está dentro da fonte.

## 3. Por que existe

Nas capturas de 07/10/2026 o início do evento da 08 (a 50 Hz, em 3 de 3) e da 09 (9 de 9) aparece num instante **fixo** (100,0 ms), a 50 e a 60 Hz, o que aponta para o tempo ou a troca de passos da lista da fonte, não para um ponto da TRACe. Isso estraga o dado, não só a métrica. As três ferramentas ({doc}`scripts`: `diag_ciclos_trace.py` offline, `diag_marcadores_trace.py` na bancada, e este módulo) existem para decidir o mecanismo; **só a bancada decide** (Blocos 4 e 6 do roteiro, {doc}`../roteiro-bancada`).

## 4. Depende de e quem depende

Só `numpy`; recebe uma `ProgramacaoCaptura` (de `ametek_orm`) mas **não a importa**. É importado por `scripts/diag_marcadores_trace.py` e pelos testes (conferido por busca em 2026-10-16); `scripts/diag_ciclos_trace.py` (offline) não o importa.
