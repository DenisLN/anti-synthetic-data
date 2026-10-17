# Sequências completas por tipo de programação

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` {bdg-success}`VERIFICADO NA BANCADA` (ordem e aceitação dos comandos, 127 V/50 Hz, 07/10/2026)

**Pergunta:** em que ordem a fonte e o osciloscópio recebem os comandos, e por que essa ordem e não outra? **Resposta:** há sete sequências (abertura da conexão, nativa STEP, nativa PULSe, CSINusoid e ACDC como variações do STEP, lista de frequência da classe 18, TRACe com lista por captura e leitura no osciloscópio), todas obedecendo três regras que vieram de falhas medidas: cada escrita é seguida de {scpi}`*ESR?` para a fonte consumi-la antes do próximo comando (rajada se perdia, v1.12); nada consulta a fonte logo depois de {scpi}`TRACe:DATA` (a fonte ficava muda, v1.12); e {scpi}`SOURce:VOLTage:HIGH` é limite rms, não de pico (v1.12). Cada comando abaixo é um link para a sua entrada em {doc}`../scpi`.

As funções citadas estão em `logica/ametek_orm.py` (classe `AmetekMX30`) e `logica/oscilloscope_orm.py` (classe `KeysightDSOX4034A`); a ordem entre fonte e osciloscópio está em `ExperimentoNativo._capturar_real` e `ExperimentoWaveform._capturar_real` (`logica/mestre.py`). O percurso completo de uma captura, com as validações de dado, está em {doc}`../codigo/percurso-captura-trace`.

## 1. Como o projeto fala com a fonte (vale para todas as sequências)

```{mermaid}
sequenceDiagram
    participant P as Python (AmetekMX30.write)
    participant F as Fonte MX30 (Rev. 5.53)
    P->>F: comando + LF
    P->>F: EOT 0x04 (segunda transferência)
    P->>F: *ESR? (sincronismo)
    F-->>P: 0 (comando consumido)
    Note over P,F: Exceção: TRACe:DATA, TRACe:DEFine, TRACe:DELete<br/>não são seguidos de *ESR? (Flash)
```

A USB virtual serial não tem controle de fluxo. Uma rajada de quatro comandos pegou 0 de 3 vezes sem consulta e 9 de 9 com uma consulta depois de cada comando (bancada de 30/09/2026, quirk A1). O EOT em transferência separada vem de A23. A latência típica de uma escrita sincronizada, medida de `W comando` até `R *ESR?`, é de 0,031 s a 0,047 s nos exemplos de 07/10 (E03 e E24 em {doc}`transcricoes`).

## 2. Abertura da conexão e baseline

**Pergunta:** o que acontece antes de a primeira classe rodar? **Resposta:** retira potência, identifica o instrumento, programa 22 comandos conferidos um a um e só então, por `energize_baseline`, liga a saída em 0 V.

```{mermaid}
sequenceDiagram
    participant B as Bancada.from_env
    participant F as Fonte
    B->>F: OUTPut:STATe OFF (raw, sem *ESR?)
    B->>F: *IDN? (modelo conferido)
    B->>F: OUTPut:STATe OFF (agora com *ESR?)
    B->>F: *CLS
    loop 22 comandos da baseline
        B->>F: comando (+ *ESR?)
        B->>F: SYSTem:ERRor? até 0,"No error"
    end
    B->>F: OUTPut:STATe? (deve ser 0)
    opt AMETEK_CLEAR_USER_WAVEFORMS=1
        B->>F: TRACe:DELete:ALL (sem *ESR?, espera 15 s)
    end
    B->>F: OUTPut:STATe ON (energize_baseline, exige authorize_output)
    B->>F: SYSTem:ERRor? e OUTPut:STATe? por até 5 s
```

Os 22 comandos, nesta ordem (`ametek_orm.py`, `configure_safe_baseline`): {scpi}`ABORt`, {scpi}`INSTrument:COUPle` `ALL`, {scpi}`SOURce:MODE` `AC`, {scpi}`SOURce:VOLTage:RANGe`, {scpi}`SOURce:VOLTage:HIGH`, {scpi}`SOURce:CURRent`, {scpi}`SOURce:CURRent:PROTection:STATe`, {scpi}`SOURce:CURRent:PROTection:DELay`, {scpi}`SOURce:FUNCtion:SHAPe` `SINusoid`, {scpi}`FUNCtion:MODE` `FIXed`, {scpi}`VOLTage:MODE` `FIXed`, {scpi}`SOURce:FREQuency:MODE` `FIXed`, {scpi}`SOURce:FREQuency:SLEW`, {scpi}`SOURce:VOLTage:SLEW`, {scpi}`SOURce:FREQuency`, {scpi}`SOURce:VOLTage` `0`, {scpi}`TRIGger:SOURce` `BUS`, {scpi}`TRIGger:SYNChronize:SOURce` `PHASe`, {scpi}`TRIGger:SYNChronize:PHASe` `0`, {scpi}`OUTPut:TTLTrg:MODE` `TRIG`, {scpi}`OUTPut:TTLTrg:SOURce` `BOT` e {scpi}`OUTPut:TTLTrg` `ON`.

Por que essa ordem: a saída desliga **antes de identificar** (`connect` manda {scpi}`OUTPut:STATe` `OFF` antes do {scpi}`*IDN?`); o limite de pico do software é validado antes de qualquer SCPI; a tensão fica em **0 V** e só chega ao valor de teste por um STEP depois de energizada; o apagamento das TRACes só roda com a saída desligada (A24) e invalida o cache entre conexões.

## 3. Nativa STEP (classes 01, 05 e 19)

**Pergunta:** como um degrau (ou, na 01, nenhum degrau) é programado e disparado? **Resposta:** `trigger_step` espera `IDLE`, neutraliza listas residuais, programa `VOLTage:MODE STEP` e o nível; `arm` lê de volta o que foi escrito, espera `*WAI` e arma; o `*TRG` sai na fase programada.

```{mermaid}
sequenceDiagram
    participant X as ExperimentoNativo._capturar_real
    participant O as Osciloscópio
    participant F as Fonte
    X->>O: definir_pre_trigger (:TIMebase:POSition)
    X->>F: TRIGger:SYNChronize:PHASe φ (+ fila)
    X->>F: configurar() = trigger_step(V)
    F-->>F: TRIGger:STATe? até IDLE
    X->>F: FUNCtion:MODE FIXed
    X->>F: SOURce:FREQuency:MODE FIXed
    X->>F: VOLTage:MODE STEP
    X->>F: VOLTage:TRIGgered V (múltiplo de 0,1 V)
    X->>F: SYSTem:ERRor? (erro 19 recusa a captura)
    X->>O: :AER? :TER? :SINGle
    X->>O: :OPERegister:CONDition? até bit 32
    X->>F: arm(): TRIGger:STATe? IDLE
    X->>F: VOLTage:MODE? VOLTage:TRIGgered? FUNCtion:MODE? SOURce:FREQuency:MODE?
    X->>F: *WAI
    X->>F: INITiate:IMMediate (+ fila)
    X->>F: TRIGger:STATe? até ARM/WTRIG
    X->>F: trigger(): TRIGger:STATe?, *TRG
    F-->>O: pulso BOT (BNC, EXT Trigger)
    X->>O: :TER? e bit 8 de :OPERegister:CONDition?
    X->>F: wait_transient_complete: TRIGger:STATe? IDLE + SYSTem:ERRor?
    X->>O: leitura da forma de onda
```

- A ordem **fase → programação → armamento → disparo** existe porque o `*TRG` age na fase de {scpi}`TRIGger:SYNChronize:PHASe`, não no instante do comando (A18). Antes de a fase ser programada (v1.12, F1), 02, 03 e 04 saíam defasadas 216° do modelo.
- {scpi}`TRIGger:STATe?` `IDLE` antes de escrever e as duas neutralizações existem porque escrever com transiente em curso é aceito e ignorado (erro 19, A14), e porque `FUNCtion:MODE LIST` residual de uma classe de lista passa a participar do `*TRG` (A9).
- Os quatro `?` antes do {scpi}`*WAI` são o readback de `_conferir_transiente_programado`: o comando perdido em rajada deixava `VOLTage:MODE` lido `FIX` (H-NATIVO).
- O {scpi}`*WAI` antes do {scpi}`INITiate:IMMediate` existe porque 01/NORMAL (STEP) seguida de 02/SAG (PULSe) na mesma conexão reproduzia `-300` de forma determinística sem ele.
- A classe 01 usa um STEP para o **mesmo** valor da base só para gerar o pulso BOT que o osciloscópio espera.

## 4. Nativa PULSe (classes 02, 03 e 04)

Igual à anterior, trocando `trigger_step` por `trigger_pulse`: {scpi}`VOLTage:MODE` `PULSe`, {scpi}`VOLTage:TRIGgered` (nível do afundamento, da elevação ou da interrupção) e {scpi}`PULSe:WIDTh` (duração do evento). O readback acrescenta `PULSe:WIDTh?`. A largura vem de `largura_do_pulso_s`: `DURACAO_S` fixa sem sorteio, ou a duração sorteada por captura desde a v1.15 (P-05).

## 5. CSINusoid (classe 05) e ACDC (classe 19)

As duas são **variações do STEP**: antes do STEP há um passo permanente que muda o estado da fonte.

```{mermaid}
flowchart LR
    A["05, nível ≤ 20 %<br/>configure_harmonics_csine(thd)"] --> A1["aguardar_idle + neutralizar"]
    A1 --> A2["SOURce:FUNCtion:SHAPe CSINusoid"]
    A2 --> A3["*WAI"]
    A3 --> A4["SOURce:FUNCtion:SHAPe:CSINusoid thd"]
    A4 --> A5["*WAI + SYSTem:ERRor?"]
    A5 --> S["trigger_step(base)"]
    B["19<br/>enable_dc_offset(offset, ac_peak)"] --> B1["recusa se |offset| + pico CA > max_peak_v"]
    B1 --> B2["SOURce:MODE ACDC"]
    B2 --> B3["*WAI + SYSTem:ERRor?"]
    B3 --> B4["SOURce:VOLTage:OFFSet V"]
    B4 --> S
    S --> R["fim da classe: restaurar_forma_e_modo_padrao<br/>SHAPe SINusoid, OFFSet 0, MODE AC"]
```

- Trocar forma ou modo recarrega tabelas e deixa a fonte muda por segundos (A7). O {scpi}`*WAI` assenta a troca; o `assert_no_errors` logo depois aponta o comando certo (antes, o erro aparecia no `INITiate` seguinte e era atribuído a ele).
- {scpi}`SOURce:VOLTage:OFFSet` só é aceito em `ACDC` (A10): por isso o modo vem antes e a ordem importa.
- O nível de 30 % da classe 05 **não** usa a CSINusoid: `usar_trace` desvia para a sequência TRACe (seção 7), porque a CSINusoid nativa vai só até 20 %.
- O estado é **permanente**: `restaurar_forma_e_modo_padrao` desfaz forma, offset e modo ao fim de toda classe física, e `restaurar_frequencia_base` desfaz a lista de frequência da 18.

## 6. Lista de frequência (classe 18)

**Pergunta:** como a rampa de frequência é programada? **Resposta:** uma lista de dois pontos de frequência (início e fim), com a tensão base nos dois e metade da duração em cada ponto; `FREQuency:MODE LIST` e `VOLTage:MODE LIST` fecham a configuração.

```{mermaid}
sequenceDiagram
    participant X as frequency_drift_list
    participant F as Fonte
    X->>F: TRIGger:STATe? até IDLE
    X->>F: FUNCtion:MODE FIXed
    X->>F: SOURce:FREQuency:MODE FIXed
    X->>F: VOLTage:MODE FIXed
    X->>F: FREQuency:MODE LIST
    X->>F: LIST:FREQuency a,b
    X->>F: LIST:VOLTage v,v
    X->>F: LIST:DWELl d,d
    X->>F: SOURce:LIST:REPeat 0,0
    X->>F: LIST:COUNt 1
    X->>F: LIST:STEP AUTO
    X->>F: VOLTage:MODE LIST
    Note over X,F: depois: arm(), *TRG; no fim, restaurar_frequencia_base
```

Comandos: {scpi}`FUNCtion:MODE`, {scpi}`SOURce:FREQuency:MODE`, {scpi}`VOLTage:MODE`, {scpi}`LIST:FREQuency`, {scpi}`SOURce:LIST:VOLTage`, {scpi}`SOURce:LIST:DWELl`, {scpi}`SOURce:LIST:REPeat`, {scpi}`SOURce:LIST:COUNt`, {scpi}`SOURce:LIST:STEP`.

- `FUNCtion:MODE FIXed` primeiro: depois da 17, uma lista de forma de 12 pontos continuava ativa e o `VOLTage:MODE LIST` final dava `-226 Lists not same length` (listas de 12 e de 2 pontos, A9; manual seção 4.17, p. 90).
- `SOURce:LIST:REPeat 0,0`, com prefixo e sem `:COUNt` (A4 e A5); `1` tocaria cada ponto duas vezes.
- Ao fim, a saída fica no **último ponto**: a 19 rodou a 63,03 Hz depois da 18 até `restaurar_frequencia_base` reescrever a base (A11).
- Sem sorteio, a rampa é 57 → 63 Hz (a 50 Hz isso é +14 % e +26 % da rede); com sorteio, `f0 − 3 → f0 + 3` Hz, invertida nas capturas ímpares (`experimentos_nativos/18.py`, `extremos_hz`). Continuidade de fase na troca nunca foi medida (P-06).

## 7. TRACe e lista por captura (classes 06 a 17, 20 e 05 acima de 20 %)

**Pergunta:** como uma forma de onda arbitrária de 6000 amostras (200 ms) chega à saída? **Resposta:** `montar_programacao` corta a forma em ciclos de `30000/f` amostras, grava cada ciclo numa TRACe de 1024 pontos e monta uma lista com um passo por ciclo; `arm_transient` confere nove leituras e o `*TRG` toca a lista inteira.

```{mermaid}
sequenceDiagram
    participant X as ExperimentoWaveform._capturar_real
    participant F as Fonte (program_capture)
    participant O as Osciloscópio
    X->>F: ABORt, *CLS
    X->>F: FUNCtion:MODE FIXed, VOLTage:MODE FIXed (+ fila)
    X->>F: SOURce:MODE AC|ACDC, SOURce:FREQuency f, FREQuency:MODE FIXed
    X->>F: SOURce:FUNCtion:SHAPe SINusoid, SOURce:VOLTage base
    F->>F: TRACe:CATalog? (cache confirmado)
    loop TRACes ausentes
        X->>F: TRACe:DEFine TCCnn (sem *ESR?, espera 3 s, fila)
    end
    loop um ciclo por TRACe (se a assinatura mudou)
        X->>F: TRACe:DATA TCCnn,1024 valores (sem *ESR?)
        Note over X,F: sleep 1 s, depois *CLS. Nada de consulta.
    end
    loop função, tensão, dwell
        X->>F: SOURce:LIST:... (+ fila)
        X->>F: SOURce:LIST:...:POINts? = nº de ciclos
    end
    X->>F: SOURce:LIST:REPeat 0,...,0
    X->>F: SOURce:LIST:COUNt 1, SOURce:LIST:STEP AUTO
    X->>F: FUNCtion:MODE LIST, VOLTage:MODE LIST
    X->>F: TRIGger:SOURce BUS, SYNChronize:SOURce PHASe, PHASe 0
    X->>F: OUTPut:TTLTrg:MODE TRIG, SOURce BOT, ON
    X->>O: set_vertical_scale, :SINGle, espera armar
    X->>F: arm_transient(): IDLE, 9 leituras, *WAI, INITiate:IMMediate
    X->>F: trigger(): *TRG
    X->>O: espera :TER? e fim da aquisição
    X->>F: wait_transient_complete
```

Comandos: {scpi}`ABORt`, {scpi}`*CLS`, {scpi}`FUNCtion:MODE`, {scpi}`VOLTage:MODE`, {scpi}`SOURce:MODE`, {scpi}`SOURce:FREQuency`, {scpi}`SOURce:FUNCtion:SHAPe`, {scpi}`SOURce:VOLTage`, {scpi}`TRACe:CATalog?`, {scpi}`TRACe:DEFine`, {scpi}`TRACe:DATA`, {scpi}`SOURce:LIST:FUNCtion:SHAPe`, {scpi}`SOURce:LIST:VOLTage`, {scpi}`SOURce:LIST:DWELl`, {scpi}`SOURce:LIST:FUNCtion:POINts?`, {scpi}`SOURce:LIST:REPeat`, {scpi}`SOURce:LIST:COUNt`, {scpi}`SOURce:LIST:STEP`, {scpi}`TRIGger:SOURce`, {scpi}`TRIGger:SYNChronize:SOURce`, {scpi}`TRIGger:SYNChronize:PHASe`, {scpi}`OUTPut:TTLTrg:MODE`, {scpi}`OUTPut:TTLTrg:SOURce`, {scpi}`OUTPut:TTLTrg`, {scpi}`INITiate:IMMediate`, {scpi}`*WAI`, {scpi}`*TRG`.

O porquê de cada decisão:

1. **`ABORt` só aqui e nunca em `arm_transient`.** Um segundo `ABORt` restaurou `FIX` e `OUTPUT OFF`, destruindo a lista preparada (A16). Se o primeiro derrubou o relé, `program_capture` religa a saída no fim (só se `authorize_output` já foi concedida).
2. **Voltar a `FIXed` antes de reprogramar a lista.** Com `FUNCtion:MODE LIST` residual, a Rev. 5.53 rejeita comandos `LIST` com `-113`.
3. **`TRACe:DATA` sem `*ESR?`, 1 s de espera e `*CLS`.** A consulta logo após a gravação deixou a fonte muda até ser religada (A2, achado de segurança de 30/09/2026); o `*CLS` de depois sai com a fonte assentada.
4. **Uma TRACe por ciclo e `DWELl` = um período exato.** A TRACe tem de ter 1024 pontos de um ciclo fechado; um pedaço que não fosse um ciclo tem viés CC e, normalizado, gera pico inflado e descontinuidade de fase na troca de passo (bug antigo, quando o corte era fixo em 600 amostras, ciclo exato só a 50 Hz).
5. **`LIST:VOLTage` com o rms da componente CA.** A fonte remove o CC da TRACe e escala para o rms pedido; com o rms "com média" a amplitude CA saía inflada nos ciclos de média diferente de zero (degrau a meio ciclo; classes 10, 11, 12 e 16; corrigido na v1.15). A média do ciclo continua perdida (P-09).
6. **`:POINts?` depois de cada eixo, nove leituras no `arm_transient`.** Um comando que não "pegou" aparece com o nome do comando, não no fim.
7. **Cache de TRACe.** Se forma, nomes, tensão, frequência e offset são os da última captura e o catálogo ainda tem as TRACes, pula-se a gravação (cerca de 1 s por TRACe, 12 a 15 s a 60 Hz). Reconfirmado em {scpi}`TRACe:CATalog?` a cada uso; com sorteio ligado nunca acerta.
8. **280 gravações por conexão.** A fonte travou na 280.ª gravação de TRACe de uma conexão em 16/09/2026 (A3, causa NÃO VERIFICADA, P-23); a CLI só avisa. O roteiro de bancada usa listas de classes para ficar abaixo de 250 gravações por conexão.

## 8. Captura no osciloscópio

**Pergunta:** como o osciloscópio é preparado uma vez e usado a cada captura? **Resposta:** uma configuração por classe (aquisição automática, referência na borda esquerda, trigger externo) e, por captura, escala vertical, armamento `:SINGle`, espera do pulso BOT e leitura da preamble e dos bytes; os extremos vêm de `:MEASure:VMAX?` e `:VMIN?` sobre o registro bruto.

```{mermaid}
sequenceDiagram
    participant X as Bancada / Experimento
    participant O as Keysight DSO-X 4034A
    Note over X,O: uma vez por conexão (Bancada.from_env)
    X->>O: *IDN? e :SYSTem:ERRor?
    X->>O: :STOP, *CLS, :ACQuire:TYPE NORMal, :WAVeform:FORMat BYTE, :WAVeform:UNSigned ON, :WAVeform:POINts:MODE RAW
    X->>O: :CHANnel1:DISPlay/PROBe/COUPling/UNITs/OFFSet/SCALe/BWLimit
    Note over X,O: uma vez por classe (configure_acquisition)
    X->>O: :STOP, :ACQuire:TYPE/MODE/DIGitizer, :TIMebase:MODE, :TIMebase:RANGe
    X->>O: :TIMebase:REFerence CUSTom, :REFerence:LOCation 0.0, leituras, :TIMebase:POSition
    X->>O: :ACQuire:POINts:ANALog:AUTO ON, :ACQuire:SRATe:ANALog:AUTO ON, :WAVeform:POINts ...
    X->>O: :EXTernal:PROBe/UNITs/RANGe, :TRIGger:HFReject/MODE/SWEep/EDGE:SOURce/LEVel/SLOPe
    Note over X,O: por captura
    X->>O: :CHANnel1:OFFSet 0, :CHANnel1:SCALe pico/3
    X->>O: :AER? :TER? :SINGle
    X->>O: :OPERegister:CONDition? até o bit 32
    X->>O: (fonte arma e dispara; BOT chega ao EXT Trigger)
    X->>O: :TER? = 1 e bit 8 apagado
    X->>O: :WAVeform:PREamble? e :WAVeform:DATA?
    X->>O: :MEASure:VMAX? CHANnel1 e :MEASure:VMIN? CHANnel1
```

Comandos Keysight: {scpik}`*IDN?`, {scpik}`:SYSTem:ERRor?`, {scpik}`:STOP`, {scpik}`*CLS`, {scpik}`:ACQuire:TYPE`, {scpik}`:ACQuire:MODE`, {scpik}`:ACQuire:DIGitizer`, {scpik}`:ACQuire:POINts:ANALog`, {scpik}`:ACQuire:SRATe:ANALog`, {scpik}`:TIMebase:MODE`, {scpik}`:TIMebase:RANGe`, {scpik}`:TIMebase:REFerence`, {scpik}`:TIMebase:REFerence:LOCation`, {scpik}`:TIMebase:POSition`, {scpik}`:CHANnel<n>:SCALe`, {scpik}`:EXTernal:RANGe`, {scpik}`:TRIGger:EDGE:SOURce`, {scpik}`:AER?`, {scpik}`:TER?`, {scpik}`:SINGle`, {scpik}`:OPERegister:CONDition?`, {scpik}`:WAVeform:PREamble?`, {scpik}`:WAVeform:DATA?`, {scpik}`:MEASure:VMAX?`, {scpik}`:MEASure:VMIN?`.

- **Armar o osciloscópio antes da fonte** (`osc.arm()` e `wait_for_armed()` antes de `fonte.arm()`): o pulso BOT sai no `*TRG`; a ordem está em `_capturar_real`; a razão (o BOT só é útil se o osciloscópio já espera o trigger) é inferência da ordem do código, sem teste que a isole.
- **`:SINGle` a cada captura** (K5) e `:AER?`/`:TER?` antes dele para zerar os registradores.
- **Referência na borda esquerda** (K1): `LEFT` fica a uma divisão da borda e produziu o "atraso de 20 ms" (v1.7) e o de "100 ms" (v1.10); era artefato de medida, não da fonte.
- **Extremos no registro bruto** (K7): o array a 30 kSa/s subestima picos estreitos.
- Todos os exemplos de comando do Keysight são derivados do código (sem transcrição): ver as páginas {doc}`keysight-aquisicao`, {doc}`keysight-trigger` e {doc}`keysight-waveform`.

:::{note} Nota de verificação
Conferido offline em 2026-10-16: a ordem desta página foi lida em `ametek_orm.py` (`configure_safe_baseline`, `program_capture`, `arm`, `arm_transient`, `trigger`, `wait_transient_complete`) e em `ExperimentoNativo._capturar_real` / `ExperimentoWaveform._capturar_real` (`mestre.py`). A ordem na bancada com o código da v1.15 {bdg-warning}`NÃO VERIFICADO` não foi observada: a última campanha é de 07/10/2026 (P-01).
:::
