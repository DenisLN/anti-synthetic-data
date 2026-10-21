# Limites físicos, pré-validação e calibração de extremos

Hardware: a MX30-3Pi gera no máximo **300 Vrms por fase** e **425 Vp** (manual SCPI §4.14, p. 84 do PDF). O software usa `max_voltage_rms = 300` e `max_peak_v = 415,8` (98 % de 300·√2). Estes valores **não podem ser aumentados** (`AGENTS.md`).

## 1. Tensões de teste

- **≤ 270 V fase-neutro** (o `START_BENCH` recusa mais; deixa ~10 % de folga para swells até o limite rms por fase).
- **380 V não é aceito**: 380 V é tensão de linha; digite 220 (219,4 V por fase). Medir fase-fase (opção A de `CHANGELOG/v1.13.md`) está documentado e **não implementado**.

## 2. Pré-validação (antes de qualquer SCPI)

`avaliar_captura_na_bancada` (`logica/mestre.py`, `ExperimentoBase.avaliar_captura_na_bancada`) decide para cada captura do plano:
1. rms programado ≤ 300 Vrms e rms·√2 ≤ `max_peak_v` (só classes que conhecem o rms: 02/03 pela `NIVEIS`);
2. **extremo previsto** = `pico_programado × fator × 1,10` ≤ teto (`max_peak_v`, ou 0,9 × na 08, que usa o modelo próprio `excursao_fisica_prevista_v`).

Quem não cabe é **pulada** com log (`PULADA ANTES de programar`); se nenhuma cabe, `ParameterOutOfBoundsError` (determinístico, sem retry). O resultado vai a `extremo_previsto_v` e `pico_programado_v` no metadata.

Depois de cada captura física, `:MEASure:VMAX?/VMIN?` (taxa cheia do osciloscópio) são conferidos contra o mesmo teto; acima dele, `PicoFisicoExcedidoError` **depois** de gravar a captura, e a classe para sem retry (`logica/mestre.py`, `ExperimentoBase._conferir_extremos_fisicos`). A 08 exige essa medida (`exige_medida_de_pico`).

A camada ORM também recusa `program_capture` antes de qualquer consulta/escrita ou alteração de cache: parâmetros/6000 amostras não finitos, tensão base acima do limite, pico da base/captura/TRACe reconstruída acima de `max_peak_v`, e RMS de qualquer passo fora de `0..max_voltage_rms`. A construção pura está em `AmetekMX30.montar_programacao`; as guardas de limite da instância estão em `AmetekMX30.program_capture`. Estado de integração/testes: `docs/execucao_pendencias.md` (P-04).

### 2.1 Capacidades da fonte conferidas antes de I/O (v1.15)

Tabela única em `logica/ametek_orm.py`, `CAPACIDADES_MX30` (conferida por `verificar_capacidade`/`verificar_exigencias`, que levantam `CapacidadeExcedidaError`, subclasse de `ParameterOutOfBoundsError`). Páginas do *AMETEK MX SCPI Programming Manual* (P/N 7003-961 Rev AB); linhas de `docs/manuais_txt/AMETEK_MX_SCPI_Programming_Manual.txt`.

| Capacidade | Faixa | Fonte | Onde é conferida |
|---|---|---|---|
| `passos_list` (pontos de LIST) | 1..32 | p. 153, l. 7104/7121: "up to 32 settings (or points) in the list" | `ProgramacaoCaptura.verificar_capacidades` (em `program_capture`, antes de qualquer escrita/consulta) e pré-validação |
| `traces_por_grupo` (formas de usuário) | 1..50 | p. 126, l. 5849: "Up to 50 user-defined waveforms ... per group" | idem; e `_ensure_trace_slots` (slots `TCC*` do projeto já no catálogo + novos) antes de qualquer `TRACe:DEFine`. **NÃO VERIFICADO** se o `TRACe:CATalog?` da Rev. 5.53 lista formas de fábrica junto: por isso só os nomes `TCC*` contam (formas de outro uso no grupo não entram na conta) |
| `dwell_s` (`LIST:DWELl`) | 0,001..9E4 s | p. 91, l. 4066 | `program_capture` (1 ciclo por passo), `frequency_drift_list`, pré-validação (18) |
| `pulse_width_s` (`PULSe:WIDTh`) | 1 ms..90 000 s | p. 106, l. 4795 | `trigger_pulse`, pré-validação (02/03/04) |
| `dc_offset_v` (AC+DC) | ±220 Vdc | p. 10, l. 406 (220 Vdc Série II; 250 Série I — usa o menor, `MAX_DC_OFFSET_V`) | `enable_dc_offset`, offsets do braço C, pré-validação (19) |
| `frequencia_hz` | 45..500 Hz | **faixa de projeto**: o manual não traz a faixa numérica da MX30, só `LIMit:FREQuency?` (p. 86, l. 3789, consulta). Não verificada contra a fonte | setter de frequência, `program_capture`, `frequency_drift_list`, pré-validação |

A pré-validação (`avaliar_captura_na_bancada`) monta, sem I/O, o que a captura exigiria (`ExperimentoBase.exigencias_de_capacidade`: a `ProgramacaoCaptura` nas capturas TRACe/LIST; `ExperimentoNativo.exigencias_nativas` nas nativas, com 18 e 19 sobrescrevendo) e a captura que excede é **pulada** com motivo `capacidade da fonte excedida: ...`, registrada em `falhas.json` como `pulada_capacidade`; a bateria segue. Consequência: a 60 Hz (12 ciclos) nada muda; acima de 160 Hz (mais de 32 ciclos em 200 ms) toda captura TRACe é pulada. `max_voltage_rms`/`max_peak_v`/`max_current_a` não mudaram; o orçamento de 216 TRACe (`politica_traces`) não é capacidade do fabricante e não está nesta tabela.

## 3. Limite de bancada (classes waveform)

Se o extremo previsto passa do teto, a captura **física** reduz só o distúrbio: `forma = senoide + k·(gerar() − senoide)`, com o maior `k` que cabe (bisseção, `_limitar_disturbio_para_bancada`, `logica/mestre.py`, `ExperimentoWaveform._limitar_disturbio_para_bancada`). `k` e os parâmetros aplicados (`*_bancada`) vão ao metadata. Abaixo de `LIMITE_BANCADA_FRACAO_MINIMA` (0,25) a captura é pulada; `LIMITE_BANCADA_DISTURBIO=0` volta a só pular. Classes nativas não reduzem (o nível é o parâmetro discreto da classe). `gerar()` e o dataset simulado não mudam. A fórmula do extremo com `k < 1` é `extremo_previsto_com_disturbio_v` (`logica/mestre.py`, `extremo_previsto_com_disturbio_v`).

## 4. Fatores de extremo (`logica/calibracao_extremos.json`)

Estrutura: `descricao`, `condicao_sem_calibracao` (textos), `por_condicao.<TTTV_FFHz>` com `tensao_rms`, `frequencia_hz`, `origem` e `fatores` (classe → número). Hoje: `127V_60Hz`, `127V_50Hz`, `230V_50Hz`. Fator = max(|VMAX|, |VMIN|) medido ÷ pico programado; nunca usado abaixo de 1.

Regra de uso (`carregar_fatores_extremo`, `logica/mestre.py`, `carregar_fatores_extremo`):
1. **Condição calibrada** (tensão ±2 %, frequência ±0,5 Hz de alguma tabela): entram só as tabelas de **mesma frequência** (±0,5 Hz), qualquer tensão; a classe usa o **maior** fator dela nessas tabelas; sem medida em nenhuma delas, usa o maior fator de todas as tabelas (hoje 1,475, da classe 16 a 127 V/60 Hz).
2. **Condição sem tabela** (ex.: 220 V/60 Hz): toda classe usa o maior fator já medido, exceto a 01, que usa o maior fator da 01; aviso no log, uma vez por condição.

Motivo histórico: 2026-10-07, 230 V/50 Hz com a tabela de 127 V/60 Hz, a 17 previu 405 V e mediu 444 V (acima dos 425 Vp do hardware). A resposta da saída depende da **frequência**, não da tensão.

**A calibração também serve à validação física (v1.15, spec 26).** `ExperimentoBase.fator_extremo_efetivo_para_validacao` (`logica/mestre.py`, `ExperimentoBase.fator_extremo_efetivo_para_validacao`) devolve, para a captura, o mesmo fator que a previsão de pico usa (`fator_extremo_da_classe(id, _fatores_extremo())`, com a regra por frequência e o caso sem tabela acima), sem a `MARGEM_FATOR_EXTREMO` (a folga é a tolerância de 10 % da crista). Captura com o distúrbio reduzido pelo limite de bancada usa a fórmula de `extremo_previsto_com_disturbio_v` com margem 1. Classe com `excursao_fisica_prevista_v()` não nulo (08) usa 1,0. `sinais.comparar_fisicamente(..., fator_crista=)` aceita crista medida em `[crista_modelo × 0,9, crista_modelo × fator × 1,1]` (bilateral: a fonte pode tocar menos que o máximo calibrado). Efeito: um fator calibrado baixo demais (ex. 07 e 17 a 127 V/60 Hz: 1,186 e 1,031) reprova a captura pela crista, e a recalibração (`set recalibracao on`, ao FIM do run) corrige o JSON para o run seguinte. O JSON não mudou.

A 03 a 230 V/50 Hz continua fora: 1,058 × 357,8 V × 1,10 = 416,4 V > 415,8 V (mantida sem exceção na margem; decisão de projeto, registrada em `CHANGELOG/v1.15.md`).

## 5. Como calibrar uma condição nova

1. Rodar a bateria na condição (o aviso de condição sem tabela é esperado).
2. `.\env\Scripts\python.exe scripts\recalibrar_extremos.py resultados\sessao_A [resultados\sessao_B ...]` mostra o que mudaria; com `--gravar` atualiza o JSON sem diminuir nenhum fator (`--substituir` permite diminuir: enfraquece a pré-validação, evitar). Capturas com distúrbio reduzido entram invertendo a fórmula do limite de bancada; a 08 não entra.
3. Alternativa dentro da CLI: `set recalibracao on` (nunca diminui, nunca cria tabela de condição nova; como reverter e o que aparece no fim do run: `docs/operacao.md` §9; `arquivo/analises:docs/analise-2026-10-12/resolvido/cli_recalibracao_html.md`).
4. `git diff`, `tests.test_offline`, commitar. A sessão guarda uma cópia da calibração usada (`calibracao_extremos.json` na pasta e `calibracao_extremos_sha256` em cada captura).

## 6. Relatório offline do que cabe

```powershell
.\env\Scripts\python.exe scripts\relatorio_limites_bancada.py --tensao 127 --tensao 220 [--frequencia 50] [--capturas N] [--seed N] [--perfil norma|literatura|fronteira]
```
Usa exatamente o código da pré-validação; não tem segunda implementação.

## 7. Checagem da cadeia de medição

Antes da primeira classe de todo `run`: senoide base, espera a medida da fonte (`MEASure:VOLTage:AC?`) chegar à base (±5 %, até 5 s) e compara com o Vrms do CH1 numa aquisição forçada (±10 %); fora disso `CadeiaDeMedicaoError` (`logica/mestre.py`, `Bancada.verificar_cadeia_de_medicao`). Pega disjuntor aberto, probe no lugar errado, fator de probe errado.

(validacao-fisica-tolerancias)=
## 8. Tolerâncias da comparação física

`logica/sinais.py`, `comparar_fisicamente`, define tolerâncias padrão de 15% para mediana/mínimo/máximo do envelope, 10% para crista e 20% relativos para THD, com piso absoluto de 1% para esta última. A crista usa também o fator calibrado, conforme seção 4; parâmetros usados e resultado precisam acompanhar cada captura. Esses limites do código não comprovam por si só a reprodução física de uma classe ou condição.
