# ASD Docs

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


**Pergunta:** o que é esta documentação e por onde começar? **Resposta:** é a documentação completa de uma bancada que produz um dataset rotulado de **20 classes de distúrbio de tensão** (fonte programável AMETEK MX30-3Pi mais osciloscópio Keysight DSO-X 4034A) e de um simulador que gera o mesmo dataset sem hardware. Comece pelo {doc}`visao-geral` (uma página) e, conforme o seu papel, siga para o {doc}`guia-operador`, a {doc}`scpi` (um comando por entrada, com exemplo real), o {doc}`codigo` (o código explicado sem abri-lo) ou o {doc}`projeto/estado-validacao`.

{bdg-info}`OFFLINE` Estado: `main` em `fa82f49`, **v1.15 em andamento, sem tag**, baseline documental de 2026-10-16; implementação atual em {doc}`execucao_pendencias`. {bdg-success}`VERIFICADO NA BANCADA` nas campanhas de 30/09 e 07/10/2026 (código anterior à v1.15). {bdg-danger}`PENDENTE P-01` Nenhum dado de bancada existe com o código da v1.15. {bdg-warning}`EXPERIMENTAL OFF` O passo final `SINE` integrado no checkout de execução ({doc}`projeto/passo-final-sin`).

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} Operar a bancada
:link: guia-operador
:link-type: doc
Ligação física, `START_BENCH`, a sequência `comm` → `trigger` → `native` → `run`, confirmações digitadas e o que fazer se algo falhar.
:::

:::{grid-item-card} Referência SCPI
:link: scpi
:link-type: doc
Sintaxe, sincronismo, quirk, método que o envia e página do manual. Relatos anteriores de transcrição exigem conferência contra logs originais.
:::

:::{grid-item-card} Guia do código
:link: codigo
:link-type: doc
Percurso de um `run` e de uma captura TRACe, uma página por módulo, invariantes de segurança e "se mudar isto, aquilo quebra".
:::

:::{grid-item-card} Medição e calibração
:link: medicao
:link-type: doc
Janela, margens e pré-trigger; correlação esperada por classe; recalibração passo a passo.
:::

:::{grid-item-card} Estado e pendências
:link: projeto/estado-validacao
:link-type: doc
O que foi verificado, em que camada e com que código; 31 pendências com o que fecha cada uma.
:::

:::{grid-item-card} Como ler
:link: como-ler
:link-type: doc
Os cinco selos de status, os avisos padronizados e as convenções de escrita.
:::
::::

```{toctree}
:maxdepth: 2
:caption: Visão geral

visao-geral
como-ler
arquitetura
glossario
```

```{toctree}
:maxdepth: 2
:caption: Operação

guia-operador
operacao
seguranca
configuracao
roteiro-bancada
diagnostico
```

```{toctree}
:maxdepth: 2
:caption: Referência SCPI

scpi
```

```{toctree}
:maxdepth: 2
:caption: As 20 classes

classes
perfis
```

```{toctree}
:maxdepth: 2
:caption: Medição e calibração

medicao
limites_e_calibracao
quirks
```

```{toctree}
:maxdepth: 2
:caption: Dataset

dataset
metadata
tres_versoes
```

```{toctree}
:maxdepth: 2
:caption: Guia do código

codigo
estender
testes
decisoes
versionamento
```

```{toctree}
:maxdepth: 2
:caption: Projeto e estado

projeto/estado-validacao
projeto/pendencias
execucao_pendencias
PENDENCIAS_TRACKER
bancada_pendencias
decisoes_pendentes
projeto/passo-final-sin
projeto/analises-arquivadas
historico
sobre
contribuir_docs
```
