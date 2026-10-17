# Se mudar isto, aquilo quebra

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Conferido no código em 2026-10-16 (`main` em `fa82f49`). As linhas vêm de `ast`; as consequências, de leitura de código e dos testes citados.

**Pergunta:** o que acompanha uma mudança em cada ponto sensível do código? **Resposta:** a tabela abaixo lista, para cada coisa que se pode querer mudar, **o que quebra ou exige mudança junto** e onde ver. Antes de mudar o que `gerar()` produz para uma seed, lembre que isso exige autorização registrada em `AGENTS.md`, fixtures byte a byte e declaração no CHANGELOG.

## 1. Tabela de acoplamentos

| Se mudar | Quebra ou exige | Onde ver |
|---|---|---|
| `AMETEK_PORT`/`AMETEK_BAUDRATE` | `validate_bench_configuration` e `connect` recusam | [mestre.py:418](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L418), [ametek_orm.py:334](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L334) |
| a ordem dos comandos de `configure_safe_baseline` | cada comando é conferido por `check_errors`; a saída fica em 0 V de propósito (`SOURce:VOLTage 0`) até um STEP | [ametek_orm.py:1212](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1212) |
| `pico_programado_v` ou `_pico_da_forma_v` | a calibração deixa de valer (recalibrar) | [mestre.py:2006](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2006), {doc}`../medicao/recalibracao` |
| `ProgramacaoCaptura` / `montar_programacao` | `programada_pu`, `program_capture`, `modelo_lista_fonte`, `diag_*`, `gerar_tres_versoes` leem a mesma função | [ametek_orm.py:100](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L100), [ametek_orm.py:1416](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1416) |
| `MARGEM_ANTES_S` / `MARGEM_DEPOIS_S` | 600/1500 amostras, `inicio_janela`, `recortar_margem`, o relatório; não reduzir sem refazer a medida | [mestre.py:2315](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L2315) |
| o formato do `.npz` | `sessao_io` é o único ponto: `mestre` escreve e sete módulos leem (`analisar_sessao`, `recortar_margem`, `relatorio_html`, `gerar_ruido_janela`, `gerar_tres_versoes`, `diag_ciclos_trace`, `verificar_sessao_bancada`) | [sessao_io.py:685](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L685), [sessao_io.py:870](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sessao_io.py#L870) |
| `FAIXAS` ou `COMPONENTES_POR_CLASSE` | independência de perfil, `plano_de_perfis`, a estimativa da CLI, as fixtures | [perfis.py:37](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L37), [perfis.py:136](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L136) |
| `Config` (campo novo) | `analisar_sessao._ConfigOffline`, `recalibrar_extremos`, `relatorio_limites_bancada` e `_config_bancada` dos testes constroem `Config`/substitutos à mão | [mestre.py:750](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L750), [analisar_sessao.py:67](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/analisar_sessao.py#L67) |
| uma chave nova em `parametros` | vira metadata; as de `CHAVES_SORTEIO` sobem de nível; a primeira chave rotulava arquivos no formato 1 | [mestre.py:821](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L821) |
| `HELP_TEXT` | é a referência que `docs/operacao.md` copia à mão | [cli.py:59](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L59) |
| uma variável de ambiente nova | `scripts/bench_config.ps1`, `.env.example`, `docs/configuracao.md` | [mestre.py:277](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L277) |
| `seed_da_captura` ou o id de 04 e 19 | `configurar()` reproduz a seed à mão e deixa de concordar com `gerar()` | [mestre.py:1703](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L1703) |
| o número de chamadas ao `rng` por ciclo em `aplicar_entalhes_continuos` | todas as formas de 07 e 17 mudam (fixtures) | [sinais.py:92](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/sinais.py#L92) |
| a ordem das chamadas a `perfis.composto` | o `rng` e o dataset das compostas | [perfis.py:182](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/perfis.py#L182) |
| `SORTEIO_TMIN_CICLOS` ou a ordem do sub-fluxo | o sorteio de todas as classes (sub-fluxo `_CHAVE_DO_SUBFLUXO`) | [mestre.py:870](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L870) |
| `calibracao_extremos.json` (texto de qualquer campo) | o SHA-256 do arquivo muda; as sessões antigas guardam o antigo, que continua certo para elas (P-25) | [mestre.py:199](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L199) |
| o formato de `chave_condicao` | as chaves do JSON e a busca por condição | [mestre.py:508](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/mestre.py#L508) |
| um passo novo no LIST (por exemplo o passo final `SINE`, **fora da `main`**) | `_last_cycles`, os `:POINts?`, `montar_programacao`, `programada_pu`, `arm_transient` | {doc}`../projeto/passo-final-sin` |

## 2. Onde as cópias vivem (risco de divergir)

| O que | Cópias | Risco |
|---|---|---|
| limites 300 Vrms e 415,8 Vp | `scripts/start_bench_windows.ps1`, `scripts/relatorio_limites_bancada.py` (`RANGE_RMS`, `TETO_PICO_V`) e `diag_*` | três fontes de verdade (R-6): mudar uma e não as outras |
| `OUTPUT_ARMED` | `mestre`, `preflight_new` (por valor) e o ambiente | autorizar só em um não vale nos outros: `autorizar_saida` espelha os três |
| `FS_HZ = 30000` | `mestre.py`, `ametek_orm.py` (`FS_HZ`), `modelo_lista_fonte.py` (constante local), `oscilloscope_orm.py` (literal `30_000.0`) | mudar a taxa exige tocar os quatro |
| fórmula da seed do ruído | `sinais.semente_do_ruido` (única definição), gravada em `ruido_janela.formula_semente` | segura: um só lugar |
| `TOTAL_CLASSES = 20` | `cli.py` e `mestre._experiment_scripts` (`range(1, 21)`) | uma 21.ª classe exige as duas |

## 3. Regra de dependência (convenção, não ferramenta)

`sinais.py`, `perfis.py` e `sessao_io.py` não importam `mestre` nem hardware; `ametek_orm.py` e `oscilloscope_orm.py` não importam `mestre`; só `mestre.py` conhece os dois instrumentos; só `cli.py` e os scripts de bancada mexem nas variáveis de módulo de `mestre`. Nada **impõe** isso: um `import` novo na direção errada passa em silêncio. `mestre.py` importa `oscilloscope_orm` **dentro** de `Bancada.from_env`, para o modo simulado rodar sem PyMeasure.
