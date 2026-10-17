# Guia do código

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Lido em 2026-10-16 (`main` em `fa82f49`, v1.15 em andamento, sem tag). As linhas citadas vêm de `ast`; fatos sobre o comportamento da fonte e do osciloscópio citam a quirk e o selo.

**Pergunta:** como se entende o código do projeto sem abri-lo? **Resposta:** pelo percurso. Comece pelas duas páginas de **ponta a ponta** ({doc}`codigo/percurso-run` e {doc}`codigo/percurso-captura-trace`), que seguem um `run` e uma captura TRACe função por função, e use as páginas por módulo como referência: cada uma diz a responsabilidade, os símbolos com assinatura e linha, o fluxo, os invariantes de segurança, as armadilhas, o que depende de quê e **por que** cada decisão estranha existe.

## 1. A pirâmide em uma página

```{mermaid}
flowchart TD
    BAT["START_BENCH.cmd → start_bench_windows.ps1<br/>(probe, tensão, frequência, limites)"] --> CLI["cli.py: SessaoCLI (bancada&gt;)"]
    CLI -->|"comm / trigger / lowvoltage / native"| PRE["preflight_new.py"]
    CLI -->|"run NN | lista | all"| BANC["mestre.Bancada"]
    PRE --> BANC
    BANC --> AM["ametek_orm.AmetekMX30<br/>(serial COM10, SCPI)"]
    BANC --> OS["oscilloscope_orm.KeysightDSOX4034A<br/>(USB, PyMeasure)"]
    BANC -->|"executar_bateria"| EXP["ExperimentoBase.executar<br/>(experimentos_*/NN.py: gerar, configurar)"]
    EXP --> SIN["sinais.py (matemática pura)"]
    EXP --> PER["perfis.py (faixas por perfil)"]
    EXP --> IO["sessao_io.ArquivoDaClasse<br/>(NN_classe.npz, metadata)"]
    IO --> OFF["offline: analisar_sessao, recortar_margem,<br/>relatorio_html, recalibrar_extremos,<br/>verificar_sessao_bancada, diag_ciclos_trace"]
    OFF -->|"recalibrar_extremos --gravar"| CAL[("calibracao_extremos.json")]
    CAL --> EXP
```

**Regra de dependência** (mantida por convenção, não por ferramenta): `sinais.py`, `perfis.py` e `sessao_io.py` não importam `mestre` nem hardware; `ametek_orm.py` e `oscilloscope_orm.py` não importam `mestre`; só `mestre.py` conhece os dois instrumentos; só `cli.py` e os scripts de bancada mexem nas variáveis de módulo de `mestre` (estado de sessão). `mestre.py` carrega `oscilloscope_orm` só dentro de `Bancada.from_env`, por isso o modo simulado roda sem PyMeasure.

## 2. Os módulos

| Módulo | Linhas | Responsabilidade | Página |
|---|---|---|---|
| `logica/mestre.py` | 3294 | configuração, `Bancada`, as classes-base, pré-validação, validação física, calibração, sorteio, gravação | {doc}`codigo/mestre` |
| `logica/ametek_orm.py` | 1998 | a fonte AMETEK: SCPI com validação, sincronismo, readback e modo simulado | {doc}`codigo/ametek_orm` |
| `logica/oscilloscope_orm.py` | 550 | o osciloscópio Keysight: janela, trigger, leitura validada, extremos | {doc}`codigo/oscilloscope_orm` |
| `logica/sinais.py` | 683 | matemática de sinal pura: entalhes, ruído, validação física, correlação do distúrbio | {doc}`codigo/sinais` |
| `logica/perfis.py` | 250 | faixas por perfil e independência de perfil | {doc}`codigo/perfis` |
| `logica/cli.py` | 1003 | o REPL do operador e as confirmações digitadas | {doc}`codigo/cli` |
| `logica/modelo_lista_fonte.py` | 209 | hipóteses sobre a cópia do evento em 100 ms | {doc}`codigo/modelo_lista_fonte` |
| `logica/analisar_sessao.py` | 360 | análise offline: lag, correlações, razão de pico | {doc}`codigo/analisar_sessao` |
| `logica/sessao_io.py` | 880 | leitura e escrita dos `.npz` (formatos 1 e 2) | {doc}`codigo/sessao_io` |
| `logica/relatorio_html.py` | 762 | relatório HTML autocontido | {doc}`codigo/relatorio_html` |
| `logica/recortar_margem.py` | 299 | tira a folga de 20/50 ms | {doc}`codigo/recortar_margem` |
| `logica/preflight_new.py` | 806 | `comm`, `trigger`, `lowvoltage`, `native` | {doc}`codigo/preflight_new` |
| `scripts/` | 6 `.ps1`/`.cmd` e 12 `.py` | entrada, recalibração, diagnósticos | {doc}`codigo/scripts` |
| `experimentos_nativos/` e `experimentos_waveform/` | 7 + 13 classes | `gerar()`, `configurar()` e ganchos | {doc}`codigo/classes_contrato` |

Páginas transversais: {doc}`codigo/invariantes` (as catorze camadas de segurança) e {doc}`codigo/acoplamentos` ("se mudar isto, aquilo quebra"). Além do código: `calibracao_extremos.json` ({doc}`medicao/recalibracao`) e `modelos/relatorio_capturas.html` (o modelo do relatório HTML).

## 3. Ordem de leitura sugerida

1. {doc}`codigo/percurso-run` e {doc}`codigo/percurso-captura-trace`: o caminho de uma captura.
2. {doc}`codigo/invariantes`: o que impede de energizar ou gravar errado.
3. {doc}`codigo/mestre` e {doc}`codigo/ametek_orm`: o coração e a fonte.
4. {doc}`codigo/classes_contrato`: o que um `NN.py` precisa ter.
5. {doc}`codigo/sessao_io`, {doc}`codigo/analisar_sessao`: o dado depois da bancada.
6. {doc}`codigo/acoplamentos`: antes de mudar qualquer coisa.

## 4. Vocabulário mínimo

**pu**: a tensão dividida pelo pico nominal `√2 · V_base`. **TRACe**: forma de onda arbitrária de usuário (1024 pontos = 1 ciclo) gravada na memória não volátil da fonte. **LIST**: lista de passos, cada um com forma, tensão e duração, tocada a cada `*TRG`. **BOT**: pulso TTL "begin of transient" que a fonte emite no início do transiente e que dispara o osciloscópio pelo `EXT Trigger`. **Perfil**: conjunto de faixas (`norma`, `literatura`, `fronteira`). **Sorteio**: início, duração e fase sorteados por captura. **Margem**: 20 ms antes e 50 ms depois da janela nominal. **Fator de extremo**: razão entre o extremo medido e o pico programado ({doc}`medicao/recalibracao`). Mais termos em {doc}`glossario`.

```{toctree}
:maxdepth: 1
:caption: Percursos

codigo/percurso-run
codigo/percurso-captura-trace
```

```{toctree}
:maxdepth: 1
:caption: Módulos

codigo/mestre
codigo/ametek_orm
codigo/oscilloscope_orm
codigo/sinais
codigo/perfis
codigo/cli
codigo/modelo_lista_fonte
codigo/analisar_sessao
codigo/sessao_io
codigo/relatorio_html
codigo/recortar_margem
codigo/preflight_new
codigo/scripts
```

```{toctree}
:maxdepth: 1
:caption: Transversais

codigo/classes_contrato
codigo/invariantes
codigo/acoplamentos
```
