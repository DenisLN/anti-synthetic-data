# Invariantes e camadas de segurança do código

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Cada linha foi conferida contra o código em 2026-10-16 (`main` em `fa82f49`); o que ninguém executou na bancada com o código da v1.15 está marcado. Os limites inegociáveis, como regra do projeto, estão em {doc}`../seguranca`.

**Pergunta:** o que impede o código de energizar a fonte ou gravar dado errado, e onde cada proteção mora? **Resposta:** são **catorze camadas independentes**: se uma falha, as outras ainda seguram. Quatro tratam da potência (porta/baud, `OUTPUT OFF` ao abrir, limites nos métodos, interlock da saída), três do que se programa (pré-validação, readback, estado seguro), três do que se mede (extremos medidos, cadeia de medição, validação do dado), e as demais da conduta (confirmação digitada, falha de infraestrutura contra falha de experimento, desligamento, Ctrl+C).

```{mermaid}
flowchart TD
    subgraph antes["Antes de energizar"]
      L1["1 Porta, baud, probe, limites de ambiente"]
      L2["2 OUTPUT OFF ao abrir, IDN conferido"]
      L11["11 Confirmação digitada"]
    end
    subgraph programar["Ao programar"]
      L3["3 Limites nos construtores e métodos"]
      L4["4 Interlock da saída"]
      L5["5 Fila SCPI conferida"]
      L6["6 Pré-validação de pico"]
      L7["7 Readback antes de armar"]
    end
    subgraph medir["Ao medir"]
      L8["8 Extremos medidos"]
      L9["9 Cadeia de medição"]
      L10["10 Validação do formato do dado"]
    end
    subgraph conduta["Conduta"]
      L12["12 Falha de infraestrutura aborta, de experimento isola"]
      L13["13 Desligamento"]
      L14["14 Ctrl+C"]
    end
    antes --> programar --> medir --> conduta
```

## 1. As catorze camadas

| # | Camada | Onde | Invariante |
|---|---|---|---|
| 1 | Porta e baud fixos, probe obrigatória, `BASE ≤ EUT_MAX ≤ faixa`, `ARM_OUTPUT=YES` só durante o comando | [mestre.py:418](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L418) | com `BENCH_MODE=1`, `COM10` e 115200 ou erro; probe ausente ou ≤ 0 é erro |
| 2 | Primeira ação ao abrir a fonte é `OUTPut:STATe OFF`; `*IDN?` conferido contra `AMETEK_EXPECTED_MODEL` | [ametek_orm.py:334](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L334) | nada energiza sem passar por `energize_baseline` |
| 3 | Limites no construtor e nos setters/métodos semânticos | `AmetekMX30.__init__` (`max_peak_v = min(…, 425)`), `voltage`, `frequency`, `current_limit`, `trigger_step`, `trigger_pulse`, `enable_dc_offset`, `configure_harmonics_csine` | fora do limite → `ParameterOutOfBoundsError` (também `ValueError`) |
| 4 | Interlock de software da saída | [ametek_orm.py:701](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L701) | `output_enabled = True` sem `authorize_output` → `PermissionError` |
| 5 | Fila SCPI conferida após cada passo relevante | [ametek_orm.py:633](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L633), [ametek_orm.py:647](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L647) | erro na fila vira `InstrumentHardwareError`; 20 erros sem esvaziar também |
| 6 | Pré-validação antes de qualquer SCPI | [mestre.py:2063](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2063) | rms ≤ 300 V, rms·√2 ≤ `max_peak_v`, extremo previsto ≤ teto (1,0 × `max_peak_v`; 0,9 na 08) |
| 7 | Readback do transiente antes de armar | [ametek_orm.py:1782](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1782) (cinco consultas, 0,5 %), [ametek_orm.py:1823](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1823) (nove) | divergência recusa a captura |
| 8 | Extremos medidos depois da captura | [mestre.py:1962](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1962), [oscilloscope_orm.py:181](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L181) | acima do teto: `PicoFisicoExcedidoError` **depois** de gravar; a classe para sem retry |
| 9 | Cadeia de medição antes da 1.ª classe | [mestre.py:1496](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1496) | fonte ±5 % da base e CH1/fonte ±10 %, ou `CadeiaDeMedicaoError` |
| 10 | Validações do formato do dado | `AmetekMX30.montar_programacao` (6000 amostras finitas), [oscilloscope_orm.py:447](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/oscilloscope_orm.py#L447), [mestre.py:2276](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2276) | 6000 amostras finitas; preamble de 10 campos; BYTE; ≥ 6000 pontos; sem código 0 nem 1/255; ≥ 30 kSa/s |
| 11 | Confirmação digitada, case-sensitive, por comando que energiza | [cli.py:345](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L345) e os `cmd_*` | `ENERGIZAR-TESTE`, `ENERGIZAR-COMANDOS`, `EXECUTAR-CLASSE-NN`, `EXECUTAR-CLASSES-<lista>`, `EXECUTAR-20-CLASSES`, mais as dos diagnósticos |
| 12 | Falha de infraestrutura aborta, de experimento isola | [mestre.py:1231](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1231) | `CommunicationError`/`FalhaFatalDeInstrumento` propagam sem retry; `ERROS_DETERMINISTICOS` não retentam; `Exception` genérica até 3 tentativas |
| 13 | Desligamento | [ametek_orm.py:1937](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1937), [mestre.py:1024](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1024) | `ABORt` + `OUTPut:STATe OFF` + leitura; ver armadilha abaixo |
| 14 | Ctrl+C no Windows | [mestre.py:445](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L445) | tratador de console chama `_thread.interrupt_main`; só na `Bancada` (não cobre o `native` do `preflight_new` rodado direto) |

## 2. Armadilhas das camadas

1. **Camada 13: a falha de desligamento não sobe.** `safe_shutdown` captura qualquer exceção, inclusive o `InstrumentHardwareError("SHUTDOWN NÃO CONFIRMADO")` que ele mesmo levanta: só vai a `logger.exception`. Quem confere é o operador no painel (`START_BENCH.cmd` imprime "CONFIRME OUTPUT OFF").
2. **Camada 6: a recusa não está no ORM.** `program_capture` só **avisa** quando o pico passa de `max_peak_v`; quem recusa é `mestre` (P-04, decisão em aberto: o ORM também recusar).
3. **Camada 8 vem depois da gravação** de propósito (a captura é a evidência), então a camada 6 é a que **impede** o pico; a 8 só o prova.
4. **Camada 11 vale para a CLI.** O caminho `mestre.main()` em modo bancada (`BENCH_MODE=1`, `ARM_OUTPUT=YES` no ambiente) energiza sem digitar nada ({doc}`mestre`, armadilha 10); e os scripts `diag_saida_vs_medida.py` e `diag_fonte_vs_osciloscopio.py` usam PyVISA cru, fora das camadas 1 a 5 ({doc}`../scpi/diagnostico`).
5. **Camada 12: não ampliar o que é "falha de experimento recuperável"** sem entender por que aquele erro é seguro de ignorar (regra de `AGENTS.md`).
6. **Camada 7 no simulador:** o simulador não modela os nove readbacks; os testes trocam `arm_transient` por stub.

## 3. Estado de verificação

As camadas 1 a 5, 11 e 13 são pré-requisito para a bateria rodar, e as sessões de 30/09 e 07/10/2026 passaram por elas. A camada 9 foi criada na v1.14, depois do disjuntor aberto (B1: a fonte media 126,6 V nela mesma e o CH1 cerca de 0,45 vezes isso, 0 de 20 classes úteis, sem erro SCPI) e rodou nas sessões seguintes de 07/10 (razão 1,004 a 230 V/50 Hz, `CHANGELOG/v1.14.md`); com o código da v1.15 nunca rodou {bdg-warning}`NÃO VERIFICADO`. A camada 14 (Ctrl+C) foi medida na bancada em 07/10/2026 (B2). A camada 8 com `fator_crista` da v1.15 nunca foi exercitada (P-07).
