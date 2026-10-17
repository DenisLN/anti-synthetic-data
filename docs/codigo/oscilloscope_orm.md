# oscilloscope_orm.py: o osciloscópio Keysight DSO-X 4034A

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Lido por inteiro em 2026-10-16 (`main` em `fa82f49`). {bdg-warning}`NÃO VERIFICADO` O tráfego SCPI do Keysight nunca foi gravado: os comandos são os do código e do manual ({doc}`../scpi/keysight-aquisicao`).

**Pergunta:** o que o `oscilloscope_orm.py` garante sobre o dado que sai do osciloscópio? **Resposta:** que ele tem a janela de tempo pedida (6000 ou 8100 pontos a 30 kSa/s), que o trigger caiu onde foi pedido (e **onde** caiu no registro), que não há buracos nem clipping vertical e que os extremos usados para a segurança são os do registro bruto, medidos pelo próprio instrumento. É um módulo sobre PyMeasure, **sem modo simulado**: `mestre` o importa só no modo bancada.

| Símbolo | Assinatura | Linha | Papel |
|---|---|---|---|
| `OscilloscopeError` | `class (RuntimeError)` | [oscilloscope_orm.py:22-23](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L22-L23) | erro do osciloscópio: medida inválida, preamble malformada, aquisição insuficiente |
| `OscChannel` | `class (Channel)` | [oscilloscope_orm.py:26-67](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L26-L67) | canal com as propriedades PyMeasure (`display`, `probe`, `coupling`, `units`, `offset`, `scale`, `bwlimit`) |
| `KeysightDSOX4034A` | `class (SCPIMixin, Instrument)` | [oscilloscope_orm.py:70-550](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L70-L550) | o driver (`SCPIMixin` mais `Instrument`) |
| `KeysightDSOX4034A.verify_identity` | `(self, expected_model: str='DSOX4034A') -> str` | [oscilloscope_orm.py:78-84](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L78-L84) | `*IDN?` contém `DSOX4034A` |
| `KeysightDSOX4034A.check_errors` | `(self, max_errors: int=20) -> List[Tuple[int, str]]` | [oscilloscope_orm.py:86-98](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L86-L98) | esvazia `:SYSTem:ERRor?` |
| `KeysightDSOX4034A.initialize_safe` | `(self) -> None` | [oscilloscope_orm.py:105-112](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L105-L112) | `:STOP`, `*CLS`, `NORMal`, `BYTE`, `UNSigned`, `RAW` |
| `KeysightDSOX4034A.configure_channel` | `(self, channel: int, *, scale: float, probe_attenuation: float, offset: float=0.0, coupling: str='DC', units: str='VOLT', display: bool=True) -> None` | [oscilloscope_orm.py:114-137](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L114-L137) | configura o canal e confere a fila |
| `KeysightDSOX4034A.set_vertical_scale` | `(self, channel: int, required_peak: float) -> float` | [oscilloscope_orm.py:145-175](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L145-L175) | `pico/3`, reajusta a `pico/2`, erro se não cobre |
| `KeysightDSOX4034A.medir_extremos` | `(self, channel: int=1) -> Tuple[float, float]` | [oscilloscope_orm.py:181-207](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L181-L207) | `:MEASURE:VMAX?` e `VMIN?`; `9.9E+37` vira erro |
| `KeysightDSOX4034A.configure_acquisition` | `(self, *, sample_rate_hz: float=30000.0, points: int=6000, duration_s: float=0.2, pre_trigger_s: float=0.0) -> None` | [oscilloscope_orm.py:209-293](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L209-L293) | janela, modo automático, referência e pré-trigger |
| `KeysightDSOX4034A._programar_referencia_horizontal` | `(self, *, duration_s: float, pre_trigger_s: float) -> None` | [oscilloscope_orm.py:295-337](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L295-L337) | `CUSTom`/`LOCation 0.0`, com queda para `LEFT` compensado |
| `KeysightDSOX4034A.definir_pre_trigger` | `(self, *, duration_s: float, pre_trigger_s: float) -> None` | [oscilloscope_orm.py:339-354](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L339-L354) | só `:TIMebase:POSition`, por captura |
| `KeysightDSOX4034A.setup_external_trigger` | `(self, *, level_v: float, probe_attenuation: float, range_v: float, slope: str='POSitive') -> None` | [oscilloscope_orm.py:356-384](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L356-L384) | trigger por borda no BNC externo |
| `KeysightDSOX4034A.arm` | `(self) -> None` | [oscilloscope_orm.py:386-389](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L386-L389) | `:AER?`, `:TER?`, `:SINGle` |
| `KeysightDSOX4034A.medir_vrms_forcado` | `(self, channel: int=1, timeout_s: float=5.0) -> float` | [oscilloscope_orm.py:395-414](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L395-L414) | Vrms em regime por aquisição com trigger forçado |
| `KeysightDSOX4034A.wait_for_armed` | `(self, timeout_s: float=5.0, poll_s: float=0.05) -> None` | [oscilloscope_orm.py:420-426](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L420-L426) | espera o bit 32 de `:OPERegister:CONDition?` |
| `KeysightDSOX4034A.wait_for_trigger_complete` | `(self, timeout_s: float=5.0, poll_s: float=0.05) -> None` | [oscilloscope_orm.py:428-441](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L428-L441) | `:TER?` = 1 e bit 8 apagado |
| `KeysightDSOX4034A.get_waveform` | `(self, channel: int, *, expected_points: int=6000) -> Tuple[np.ndarray, np.ndarray]` | [oscilloscope_orm.py:447-537](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L447-L537) | lê, valida e reamostra a 30 kSa/s |
| `KeysightDSOX4034A.close` | `(self) -> None` | [oscilloscope_orm.py:545-550](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L545-L550) | `:STOP` e fecha o adapter, **sem** fechar o `ResourceManager` |

## 1. Fluxo de controle

```{mermaid}
sequenceDiagram
    participant M as mestre (Bancada.from_env)
    participant O as KeysightDSOX4034A
    M->>O: verify_identity, initialize_safe
    M->>O: configure_channel(1), configure_acquisition
    M->>O: setup_external_trigger
    loop por captura
        M->>O: set_vertical_scale(pico)
        M->>O: definir_pre_trigger (se sorteado)
        M->>O: arm(), wait_for_armed()
        Note over M,O: a fonte arma e dispara (BOT no EXT Trigger)
        M->>O: wait_for_trigger_complete()
        M->>O: get_waveform(1)  -> (tempo, tensão)
        M->>O: medir_extremos(1) -> (VMAX, VMIN)
    end
```

## 2. Invariantes e camadas de segurança

1. **Modo de aquisição automático** (`:ACQuire:POINts:ANALog:AUTO ON`, `:ACQuire:SRATe:ANALog:AUTO ON`), porque pontos ou taxa explícitos ligam o modo Digitizer, que exige `REFerence CENTer` e foi **descartado** na v1.10 (K3). O firmware entrega cerca de 32,3 a 32,7 mil pontos por aquisição `:SINGle`, independente da janela pedida.
2. **Referência horizontal exata.** `:TIMebase:REFerence CUSTom` com `LOCation 0.0`, **lidos de volta**; se o firmware não aceitar, cai para `LEFT` **compensando** uma divisão (`RANGe/10`) em `:TIMebase:POSition`. O que valeu fica em `referencia_horizontal_efetiva` (metadata). O sinal de `POSition` é `t_referência − t_trigger`: negativo para sobrar baseline antes do trigger (K1, K2).
3. **O trigger é localizado.** `get_waveform` guarda `x_origin` (instante, relativo ao trigger, da **primeira** amostra) e converte em `ultimo_indice_trigger = round(−x_origin · 30000)`, que alimenta `indice_trigger` e `inicio_janela` no metadata.
4. **Validações do dado.** Preamble com 10 campos finitos; formato BYTE (`format_code == 0`); pelo menos 6000 pontos (8100 com margem); **nenhum código 0 (buraco) nem 1 ou 255 (clipping)**; taxa ≥ 30 kSa/s; cobertura temporal suficiente.
5. **Extremos no registro bruto.** `medir_extremos` usa `:MEASure:VMAX?/VMIN?`: a amostra do vetor a 30 kSa/s subestima picos estreitos (K7). Medida `9.9E+37` ou não finita vira `OscilloscopeError`, nunca tensão.
6. **Escala vertical que cobre o pico.** `set_vertical_scale` usa `pico/3` (3 das 4 divisões por polaridade), reajusta a `pico/2` se `4·escala < 1,05·pico` e levanta se ainda não cobre; a escala usada fica em `ultima_escala_vertical_v`.

## 3. Armadilhas

1. `OscChannel.display` só funciona como **setter**: o getter lança `KeyError` (K9, Bug C da v1.10).
2. `close()` **não** fecha o `ResourceManager` do PyVISA: no Windows isso invalidou a sessão serial da fonte, que ainda precisava receber `OUTPUT OFF` (B3).
3. **Reamostragem sem anti-aliasing.** O vetor devolvido é a interpolação linear (`np.interp`) do registro bruto (cerca de 116,7 kSa/s) para a grade de 30 kSa/s (K4); o efeito nunca foi quantificado (P-28).
4. `:SINGle` precisa ser reenviado a **cada** captura (K5): `arm()` zera `:AER?`/`:TER?` antes.
5. `definir_pre_trigger` levanta se `configure_acquisition` não rodou antes (`referencia_horizontal_efetiva` ainda ausente).
6. Nenhuma função aqui é transcrita: o log de nível debug do PyVISA nunca foi versionado.

## 4. Por que é assim

- **Referência `CUSTom`.** O "atraso de 20 ms" (v1.7) e o "de 100 ms" (v1.10) eram o offset de uma divisão do `LEFT` (H-REF10), não latência da fonte.
- **`x_origin` virou `indice_trigger`.** O código antigo fazia `time_axis -= time_axis[0]` e jogava fora a única informação que diz onde o trigger caiu.
- **Medida do osciloscópio para a segurança.** Na 08, 415,3 V medidos no array contra um teto de 415,8 V: o pico real caía entre amostras.

## 5. Depende de e quem depende

Importa `pymeasure` e `numpy`; **não importa `mestre`**. Só `mestre.Bancada.from_env` o instancia; `preflight_new` e vários `diag_*` o usam pelo mesmo caminho ou diretamente por PyVISA cru (os dois scripts de comparação fonte × osciloscópio não passam por aqui: {doc}`../scpi/diagnostico`).
