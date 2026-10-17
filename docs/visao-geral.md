# O projeto em uma página

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Estado conferido em 2026-10-16: `main` em `fa82f49`, **v1.15 em andamento, sem tag**. {bdg-danger}`PENDENTE P-01` Nenhum dado de bancada existe com o código da v1.15; a última campanha é de 07/10/2026.

**Pergunta:** o que este projeto produz e como? **Resposta:** um **dataset rotulado de 20 classes de distúrbio de tensão** (200 ms, 6000 amostras a 30 kSa/s, em pu do pico nominal) para treinar o classificador de um analisador de qualidade de energia embarcado, produzido de duas formas: **simulada** (Python/NumPy, sem hardware, milhares de capturas por classe) e em **bancada física** (uma fonte CA programável AMETEK MX30-3Pi gera o distúrbio e um osciloscópio Keysight DSO-X 4034A o captura), para confirmar que a bancada reproduz o modelo.

```{mermaid}
flowchart LR
    G["gerar()<br/>(modelo, por classe e seed)"] --> S["Simulado<br/>+ ruído 20/30/40 dB"]
    G --> P["Programada<br/>(o que a fonte recebe)"]
    P --> F["AMETEK MX30-3Pi<br/>SCPI, COM10"]
    F --> O["Keysight DSO-X 4034A<br/>CH1, trigger pelo BNC (BOT)"]
    O --> M["Medida"]
    S --> D[("NN_classe.npz<br/>+ metadata/*.jsonl")]
    P --> D
    M --> D
```

## 1. As 20 classes em uma tabela

A especificação original está em `experimentos.txt`; o código atual, em {doc}`classes`. Mecanismo na bancada: **nativo** = a fonte gera o distúrbio com um recurso próprio (STEP, PULSe, CSINusoid, lista de frequência, ACDC); **TRACe** = a forma é gravada em TRACes de um ciclo e tocada por uma lista.

| Classes | Distúrbio | Mecanismo na bancada |
|---|---|---|
| 01 | tensão normal | nativo (STEP à base, só para gerar o trigger) |
| 02, 03, 04 | afundamento, elevação, interrupção | nativo (PULSe) |
| 05 | harmônicas | nativo até 20 % de THD (CSINusoid); TRACe acima |
| 06 | flicker | TRACe |
| 07 | entalhes (notching) | TRACe |
| 08 | transitório impulsivo | TRACe |
| 09 | transitório oscilatório | TRACe |
| 10 a 17 | compostas (afundamento ou elevação com harmônicas, flicker ou oscilação; harmônicas com flicker; interrupção com harmônicas; entalhes com oscilação) | TRACe |
| 18 | deriva de frequência | nativo (lista de frequência de dois pontos) |
| 19 | offset CC | nativo (ACDC com STEP) |
| 20 | inter-harmônicas | TRACe |

## 2. O que sai de uma captura

- **Três versões da mesma captura**: `modelo` (o que `gerar()` pede), `programada` (o que a fonte foi programada para emitir) e `medida` (o CH1 do osciloscópio). A diferença modelo × programada é limite da bancada; a diferença programada × medida é física da fonte ({doc}`tres_versoes`, {doc}`medicao/correlacao`).
- **Janela**: 6000 amostras rotuladas; na bancada o registro tem 20 ms antes e 50 ms depois (8100 amostras), recortados por `recortar_margem` ({doc}`medicao`).
- **Ruído acrescentado só na janela rotulada** (20, 30 e 40 dB, SNR exato por construção) e os SNRs da bancada e efetivo no metadata.
- **Metadata** por captura: seed, parâmetros, sorteios de início, duração e fase, validação física, extremos medidos, procedência do código ({doc}`metadata`, {doc}`dataset`).
- **Um `NN_classe.npz` comprimido por classe**, com os três perfis de faixas (`norma`, `literatura`, `fronteira`) e as três versões ({doc}`perfis`).

## 3. Como a segurança é tratada

A bancada gera até 300 Vrms por fase e 425 Vp. O software limita a 300 Vrms e 415,8 Vp, **nada energiza sem uma string digitada pelo operador**, toda escrita à fonte é seguida de uma consulta de sincronismo e toda programação é conferida (fila de erros, readback), e há uma checagem da cadeia de medição antes da primeira classe. As catorze camadas estão em {doc}`codigo/invariantes`; as regras, em {doc}`seguranca`.

## 4. O que se sabe e o que não se sabe

| Fato | Selo | Onde |
|---|---|---|
| as 20 classes geram, programam e reproduzem as fixtures; a suíte offline passa (497 testes, 2026-10-16) | {bdg-info}`OFFLINE` | {doc}`projeto/estado-validacao` |
| as 20 classes rodaram na bancada em 127 V/60 Hz e 127 V/50 Hz, e 15 a 230 V/50 Hz (07/10/2026, **código anterior à v1.15**) | {bdg-success}`VERIFICADO NA BANCADA` | {doc}`projeto/estado-validacao` |
| perfis, sorteio de início, duração e fase, compostas sorteadas, entalhes contínuos, a 08 a 90 ms, crista com fator | {bdg-warning}`NÃO VERIFICADO` | {doc}`projeto/pendencias` (P-01) |
| passo final `SINE` da lista | {bdg-secondary}`FORA DA MAIN` | {doc}`projeto/passo-final-sin` |
| 31 pendências abertas (17 de bancada, 13 de decisão, 1 de código) | {bdg-danger}`PENDENTE` | {doc}`projeto/pendencias` |

## 5. Por onde continuar

- Quem vai **operar** a bancada: {doc}`guia-operador`.
- Quem vai **entender os comandos** SCPI: {doc}`scpi`.
- Quem vai **entender o código** sem abri-lo: {doc}`codigo`.
- Quem vai **calibrar** ou interpretar uma medida: {doc}`medicao`.
- Quem quer saber **o que falta**: {doc}`projeto/estado-validacao` e {doc}`projeto/pendencias`.
- Arquitetura em mapa de arquivos: {doc}`arquitetura`. Termos: {doc}`glossario`.
