# Formato do metadata de uma sessão

Formato 2 (2026-10-12). Sessões anteriores (só `.jsonl`) continuam sendo lidas por todos os leitores.

## Arquivos

```
resultados/sessao_<timestamp>/
  sessao.json                  procedência da sessão (um por pasta)
  calibracao_extremos.json     cópia da calibração EM USO (byte a byte)
  metadata/
    NN_classe.jsonl            formato de máquina: 1 captura por linha (o que os leitores consomem)
    NN_classe.json             MESMOS registros, lista JSON indentada, para leitura humana
```

Decisão: o `.jsonl` continua sendo a fonte; o `.json` é derivado dele (gravado depois, no
fim da classe, na mesma operação que promove o `.jsonl.part`). Trocar o formato obrigaria
a reescrever 4 leitores (`recortar_margem`, `analisar_sessao`, `relatorio_html`,
`recalibrar_extremos`) e quebraria a leitura das sessões de 07/10, sem ganho de informação.
Os leitores usam `glob("*.jsonl")`, que não casa `NN_classe.json`. Se o processo morrer
no meio de uma classe, só o `.jsonl.part` existe (o `.json` aparece quando a classe fecha,
inclusive nas interrompidas via erro tratado).

## `sessao.json`

| Campo | Significado |
|---|---|
| `formato_metadata` | 2 |
| `criada_em` | ISO 8601 com fuso, no primeiro uso da pasta no processo |
| `modo` | `bancada` ou `simulado` |
| `git_commit` | `git rev-parse HEAD` (`null` se o git não respondeu) |
| `git_sujo` | `true` se há alteração rastreada não commitada em qualquer arquivo (`git status --porcelain --untracked-files=no`) OU arquivo novo não ignorado dentro de `logica/`, `experimentos_nativos/`, `experimentos_waveform/` ou `scripts/` (`mestre.PASTAS_DO_CODIGO`); arquivo novo fora dessas pastas não conta; `null` se o git não respondeu. Recalculado a cada pasta de sessão (= a cada `run` da CLI), não uma vez por processo |
| `arquivos_nao_rastreados` | lista (ordenada) dos arquivos novos não ignorados dentro de `PASTAS_DO_CODIGO` que tornaram a árvore suja; `[]` se nenhum (v1.15, acrescentado) |
| `versao_codigo` | `git describe --always --dirty --tags` |
| `numpy_versao`, `python_versao` | versões do ambiente que gravou |
| `perfil` | perfil de faixas (`norma`, `literatura` ou `fronteira`) em vigor no início do run desta pasta (v1.15, acrescentado) |
| `perfis_usados_na_cli` | lista, na ordem, do perfil de cada run desta CLI até esta pasta, inclusive (v1.15, acrescentado); a pasta do primeiro run tem uma entrada, a do terceiro, três |
| `calibracao_extremos.origem` | caminho do arquivo copiado |
| `calibracao_extremos.copia_na_sessao` | nome da cópia dentro da pasta (`calibracao_extremos.json`) |
| `calibracao_extremos.sha256` | SHA-256 da cópia |

Em sessão de bancada com `git_sujo = true`, o início do `run` imprime um aviso em destaque
(linhas de `!`) e registra `WARNING` no log; não bloqueia (não existia mecanismo de bloqueio).

## Registro de captura (`NN_classe.json` / linha do `.jsonl`)

Nenhum campo existente foi removido. Campos novos:

| Campo | Onde | Significado |
|---|---|---|
| `inicio_janela` | só captura física com `indice_trigger` | índice da amostra, dentro do registro bruto, onde começa a janela nominal de `pontos` amostras: `round(indice_trigger - pre_trigger_s * fs_hz)`, limitado a `[0, amostras_totais - pontos]` (a mesma conta de `sinais.janela_nominal`) |
| `inicio_janela_ajustado` | idem | `true` se o limite agiu (registro curto demais; janela empurrada para dentro) |
| `inicio_disturbio_s`, `duracao_s`, `fase_graus` | simulada e física, com `sorteio_posicao` verdadeiro | início e duração do distúrbio dentro da janela de 200 ms e fase da senoide base em t = 0 (`sin(2π·f0·t + fase)`), sorteados em `gerar()` (v1.15; `docs/analise-2026-10-12/sorteio_inicio_fase.md`). Ausentes quando a classe não tem o item (início/duração: 01, 05, 06, 15, 18, 19, 20) e na 08 |
| `sorteio_posicao` | toda captura | `true` se o sorteio estava ligado; metadata anterior não tem o campo (= `false`) |
| `pre_trigger_s` | só física | passa a ser o pré-trigger **efetivo da captura** (nas 02/03/04 com sorteio, igual a `inicio_disturbio_s`); `inicio_janela` e os leitores já o usam |
| `pre_trigger_desvio_amostras` | só física, pré-trigger sorteado | `indice_trigger` medido menos o previsto (`round(pre_trigger_s·fs) + margem_amostras_antes`) |
| `parametros.inicio_impulso_s` (08) | só física | instante do impulso programado (80 ms; 90 ms a 50 Hz com `sorteio_posicao`; `docs/analise-2026-10-12/classe08_fronteira.md`) |
| `validacao_fisica.posicao_evento` (08) | só física | `inicio_previsto_amostra`, `pico_medido_amostra`, `desvio_amostras` (medido menos previsto), `tolerancia_amostras` (10) e `desvio_pico_pu`; fora da tolerância a captura é marcada inválida (`ok = false`, motivo "posição do impulso") |
| `git_commit`, `git_sujo`, `numpy_versao` | só física | cópia da procedência (o `.jsonl` sobrevive sozinho se for copiado sem a pasta) |
| `calibracao_extremos_sha256` | só física | SHA-256 da calibração usada na captura; deve bater com `sessao.json` |
| `tres_versoes` | captura gravada pela v1.15 (em andamento) em diante | `{arquivo, programada}`: onde estão modelo/programada/medida desta captura e como a programada foi obtida (`docs/tres_versoes.md`) |
| `snr_medido_db` | toda captura | SNR **acrescentado** por nível (`"20.0"`, `"30.0"`, `"40.0"`): janela limpa contra ruído somado, medido só na janela rotulada |
| `snr_bancada_db` | só física | SNR do ruído próprio da bancada nesta captura (potência da janela / ruído medido na margem anterior por segunda diferença); `null` no simulado |
| `snr_efetivo_db` | toda captura | por nível: sinal / (ruído da bancada + ruído acrescentado); no simulado igual a `snr_medido_db` |
| `ruido_janela` | toda captura | `inicio_janela`, `amostras`, `potencia_referencia_pu2`, `margens_com_ruido` (sempre `false`: os `snr_XXdb/` têm só a janela) e `bancada` (`margem`, `amostras`, `ruido_rms_pu`, `media_da_margem_pu`, `snr_db`) |
| `ruido_janela.sementes_por_snr_db` | toda captura com níveis de SNR (v1.15, acrescentado) | semente do AWGN de cada nível, com a mesma chave de `snr_medido_db` (`"20.0"`, ...): para `seed = 2020000` e níveis 20/30 dB: `{"20.0": 52040000, "30.0": 52050000}`. Com ela e `potencia_referencia_pu2`, o vetor de ruído se reproduz (`numpy.random.default_rng(semente).normal(0, 1, pontos)`, escalado para a potência de referência / 10^(snr/10)) |
| `ruido_janela.formula_semente` | idem | texto da fórmula: `seed + round(snr_db*1000) + 50000000` (`sinais.semente_do_ruido`, `sinais.FORMULA_SEMENTE_RUIDO`) |

Capturas simuladas não têm trigger nem registro bruto: não têm `inicio_janela`; a procedência delas está em `sessao.json`.

Leitores: `recortar_margem.calcular_recorte` (e, por ele, `relatorio_html`) e `analisar_sessao`
usam `inicio_janela` quando existe; sem ele, caem em `indice_trigger` e depois em
`margem_amostras_antes`, como antes. No `sem_margem/` gerado, `inicio_janela` vale 0
(o arquivo recortado já começa na janela).

## Exemplo (uma captura física; saída de teste com instrumentos simulados)

```json
{
  "amostras_totais": 7200,
  "calibracao_extremos_sha256": "af4bf8acbfd5a557f1d5c68b23ca63a307ded2bd93fcd30f55cdace5deb2e138",
  "classe": "SAG",
  "f0_hz": 60.0,
  "fs_hz": 30000.0,
  "git_commit": "34a0d820a12b035a84c438baf52b756dacf77b41",
  "git_sujo": true,
  "id_captura": "02-0001",
  "indice_trigger": 2500,
  "inicio_janela": 700,
  "inicio_janela_ajustado": false,
  "margem_amostras_antes": 600,
  "margem_amostras_depois": 600,
  "numpy_versao": "2.4.6",
  "parametros": {},
  "pontos": 6000,
  "pre_trigger_s": 0.06,
  "seed": 2000001,
  "simulado": false,
  "tensao_base_rms": 127.0,
  "versao_codigo": "34a0d82-dirty"
}
```

(Trecho: o registro real tem também `idn_*`, `extremo_previsto_v`, `pico_programado_v`,
`validacao_fisica` etc.)
