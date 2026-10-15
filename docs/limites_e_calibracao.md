# Limites físicos, pré-validação e calibração de extremos

Hardware: a MX30-3Pi gera no máximo **300 Vrms por fase** e **425 Vp** (manual SCPI §4.14, p. 84 do PDF). O software usa `max_voltage_rms = 300` e `max_peak_v = 415,8` (98 % de 300·√2). Estes valores **não podem ser aumentados** (`AGENTS.md`).

## 1. Tensões de teste

- **≤ 270 V fase-neutro** (o `START_BENCH` recusa mais; deixa ~10 % de folga para swells até o limite rms por fase).
- **380 V não é aceito**: 380 V é tensão de linha; digite 220 (219,4 V por fase). Medir fase-fase (opção A de `CHANGELOG/v1.13.md`) está documentado e **não implementado**.

## 2. Pré-validação (antes de qualquer SCPI)

`avaliar_captura_na_bancada` (`mestre.py:1868`) decide para cada captura do plano:
1. rms programado ≤ 300 Vrms e rms·√2 ≤ `max_peak_v` (só classes que conhecem o rms: 02/03 pela `NIVEIS`);
2. **extremo previsto** = `pico_programado × fator × 1,10` ≤ teto (`max_peak_v`, ou 0,9 × na 08, que usa o modelo próprio `excursao_fisica_prevista_v`).

Quem não cabe é **pulada** com log (`PULADA ANTES de programar`); se nenhuma cabe, `ParameterOutOfBoundsError` (determinístico, sem retry). O resultado vai a `extremo_previsto_v` e `pico_programado_v` no metadata.

Depois de cada captura física, `:MEASure:VMAX?/VMIN?` (taxa cheia do osciloscópio) são conferidos contra o mesmo teto; acima dele, `PicoFisicoExcedidoError` **depois** de gravar a captura, e a classe para sem retry (`mestre.py:1767`). A 08 exige essa medida (`exige_medida_de_pico`).

## 3. Limite de bancada (classes waveform)

Se o extremo previsto passa do teto, a captura **física** reduz só o distúrbio: `forma = senoide + k·(gerar() − senoide)`, com o maior `k` que cabe (bisseção, `_limitar_disturbio_para_bancada`, `mestre.py:2846`). `k` e os parâmetros aplicados (`*_bancada`) vão ao metadata. Abaixo de `LIMITE_BANCADA_FRACAO_MINIMA` (0,25) a captura é pulada; `LIMITE_BANCADA_DISTURBIO=0` volta a só pular. Classes nativas não reduzem (o nível é o parâmetro discreto da classe). `gerar()` e o dataset simulado não mudam. A fórmula do extremo com `k < 1` é `extremo_previsto_com_disturbio_v` (`:597`).

## 4. Fatores de extremo (`logica/calibracao_extremos.json`)

Estrutura: `descricao`, `condicao_sem_calibracao` (textos), `por_condicao.<TTTV_FFHz>` com `tensao_rms`, `frequencia_hz`, `origem` e `fatores` (classe → número). Hoje: `127V_60Hz`, `127V_50Hz`, `230V_50Hz`. Fator = max(|VMAX|, |VMIN|) medido ÷ pico programado; nunca usado abaixo de 1.

Regra de uso (`carregar_fatores_extremo`, `mestre.py:514`):
1. **Condição calibrada** (tensão ±2 %, frequência ±0,5 Hz de alguma tabela): entram só as tabelas de **mesma frequência** (±0,5 Hz), qualquer tensão; a classe usa o **maior** fator dela nessas tabelas; sem medida em nenhuma delas, usa o maior fator de todas as tabelas (hoje 1,475, da classe 16 a 127 V/60 Hz).
2. **Condição sem tabela** (ex.: 220 V/60 Hz): toda classe usa o maior fator já medido, exceto a 01, que usa o maior fator da 01; aviso no log, uma vez por condição.

Motivo histórico: 2026-10-07, 230 V/50 Hz com a tabela de 127 V/60 Hz, a 17 previu 405 V e mediu 444 V (acima dos 425 Vp do hardware). A resposta da saída depende da **frequência**, não da tensão.

**A calibração também serve à validação física (v1.15, spec 26).** `ExperimentoBase.fator_extremo_efetivo_para_validacao` (`mestre.py:1872`) devolve, para a captura, o mesmo fator que a previsão de pico usa (`fator_extremo_da_classe(id, _fatores_extremo())`, com a regra por frequência e o caso sem tabela acima), sem a `MARGEM_FATOR_EXTREMO` (a folga é a tolerância de 10 % da crista). Captura com o distúrbio reduzido pelo limite de bancada usa a fórmula de `extremo_previsto_com_disturbio_v` com margem 1. Classe com `excursao_fisica_prevista_v()` não nulo (08) usa 1,0. `sinais.comparar_fisicamente(..., fator_crista=)` aceita crista medida em `[crista_modelo × 0,9, crista_modelo × fator × 1,1]` (bilateral: a fonte pode tocar menos que o máximo calibrado). Efeito: um fator calibrado baixo demais (ex. 07 e 17 a 127 V/60 Hz: 1,186 e 1,031) reprova a captura pela crista, e a recalibração (`set recalibracao on`, ao FIM do run) corrige o JSON para o run seguinte. O JSON não mudou.

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

Antes da primeira classe de todo `run`: senoide base, espera a medida da fonte (`MEASure:VOLTage:AC?`) chegar à base (±5 %, até 5 s) e compara com o Vrms do CH1 numa aquisição forçada (±10 %); fora disso `CadeiaDeMedicaoError` (`mestre.py:1329-1366`). Pega disjuntor aberto, probe no lugar errado, fator de probe errado.
