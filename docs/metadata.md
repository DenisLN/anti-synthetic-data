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
Os leitores usam `glob("*.jsonl")`, que não casa `NN_classe.json`. Com `set perfil todos`
(v1.15) o `.jsonl` da classe tem as linhas de TODOS os perfis, perfil a perfil, e é reescrito
inteiro (`.jsonl.part` -> `os.replace`) ao fim de cada perfil e ao interromper a classe, junto
com o `NN_classe.npz` (`mestre._gravar_arquivos_da_classe`). Se o processo morrer no meio de
um perfil, o metadata das capturas já feitas está em `parcial/NN_classe/` (campo
`metadado_json` de cada captura) e `sessao_io.recuperar_parcial` o devolve ao `.jsonl`; o
`.json` aparece quando a classe fecha, inclusive nas interrompidas via erro tratado.

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
| `perfis_da_rodada` | lista dos perfis que o run percorre: um com `set perfil norma\|literatura\|fronteira`, os três com `set perfil todos`; `perfil` vale então `"todos"` (v1.15, acrescentado) |
| `formato_npz` | formato dos `.npz` da pasta: `2` = um `NN_classe.npz` comprimido por classe, com perfis e versões (`docs/dataset.md` §2; v1.15, acrescentado) |
| `perfis_usados_na_cli` | lista, na ordem, do perfil de cada run desta CLI até esta pasta, inclusive (v1.15, acrescentado); a pasta do primeiro run tem uma entrada, a do terceiro, três |
| `calibracao_extremos.origem` | caminho do arquivo copiado |
| `calibracao_extremos.copia_na_sessao` | nome da cópia dentro da pasta (`calibracao_extremos.json`) |
| `calibracao_extremos.sha256` | SHA-256 da cópia |
| `condicao` | condição da rodada para `rerun`/`run falhas` (v1.15, acrescentado): `tensao_base_rms`, `frequencia_hz`, `p09_braco`, `passo_final_sin` (`AMETEK_PASSO_FINAL_SIN`), `max_voltage_rms` (`EUT_MAX_VOLTAGE_RMS`), `max_peak_v` (min(`EUT_MAX_PEAK_V`, 425)), `source_voltage_range_rms`, `base_seed`, `capturas_override`, `sorteio_posicao`, `perfil`, `perfis_da_rodada`, `calibracao_extremos_sha256` (`mestre.condicao_atual`) |
| `rerun_de` | só em sessão criada por `rerun`/`run falhas` (v1.15, acrescentado): `sessao` (pasta de origem), `calibracao_extremos_sha256` (o da origem, igual ao atual), `ids_captura`, `classes` e `itens` (tipo, classe, perfil, indice_global, id_captura de cada item escolhido) |

Em sessão de bancada com `git_sujo = true`, o início do `run` imprime um aviso em destaque
(linhas de `!`) e registra `WARNING` no log; não bloqueia (não existia mecanismo de bloqueio).

## `falhas.json` (v1.15)

Na pasta da sessão, criado na primeira falha e reescrito atomicamente (`.json.part` -> `os.replace`) a cada nova entrada, ao longo da bateria (`mestre.RegistroFalhas`). Ausente = nenhuma falha registrada. Topo: `formato_falhas` (1), `sessao`, `atualizado_em`, `contexto` e `itens`. Cada item:

| Campo | Significado |
|---|---|
| `tipo` | `pulada_capacidade` (exigência acima de `CAPACIDADES_MX30`), `pulada_preflight` (rms/pico/extremo previsto acima do teto), `descartada` (erro durante a captura, nada gravado), `invalida` (gravada, reprovada na validação física), `classe_falhou` (a classe num perfil terminou FALHOU; inclui a que abortou por falha de infraestrutura, com motivo próprio), `nao_executada_orcamento` (não rodou porque o orçamento de 216 TRACe da conexão esgotou) |
| `classe`, `classe_nome`, `perfil` | id (`"02"`), nome e perfil |
| `indice_global`, `capture_index`, `nivel_indice`, `seed`, `id_captura` | da captura (`null` em entrada de classe inteira) |
| `motivo` | texto do motivo |
| `registrado_em` | ISO 8601 |
| `contexto` | `base_seed`, `capturas_override`, `perfil`, `perfis_da_rodada`, `sorteio_posicao`, `rerun_de` e a condição de `mestre.CHAVES_CONDICAO_RERUN`: `tensao_base_rms`, `frequencia_hz`, `p09_braco`, `passo_final_sin`, `max_voltage_rms`, `max_peak_v`, `source_voltage_range_rms`, `calibracao_extremos_sha256` |

## Registro de captura (`NN_classe.json` / linha do `.jsonl`)

Nenhum campo existente foi removido. Campos novos:

| Campo | Onde | Significado |
|---|---|---|
| `inicio_janela` | só captura física com `indice_trigger` | índice da amostra, dentro do registro bruto, onde começa a janela nominal de `pontos` amostras: `round(indice_trigger - pre_trigger_s * fs_hz)`, limitado a `[0, amostras_totais - pontos]` (a mesma conta de `sinais.janela_nominal`) |
| `inicio_janela_ajustado` | idem | `true` se o limite agiu (registro curto demais; janela empurrada para dentro) |
| `inicio_disturbio_s`, `duracao_s`, `fase_graus` | simulada e física, com `sorteio_posicao` verdadeiro | início e duração do distúrbio dentro da janela de 200 ms e fase da senoide base em t = 0 (`sin(2π·f0·t + fase)`), sorteados em `gerar()` (v1.15; `arquivo/analises:docs/analise-2026-10-12/pendente/sorteio_inicio_fase_VERIFICAR_BANCADA.md`). Ausentes quando a classe não tem o item (início/duração: 01, 05, 06, 15, 18, 19, 20) e na 08 |
| `sorteio_posicao` | toda captura | `true` se o sorteio estava ligado; metadata anterior não tem o campo (= `false`) |
| `pre_trigger_s` | só física | passa a ser o pré-trigger **efetivo da captura** (nas 02/03/04 com sorteio, igual a `inicio_disturbio_s`); `inicio_janela` e os leitores já o usam |
| `pre_trigger_desvio_amostras` | só física, pré-trigger sorteado | `indice_trigger` medido menos o previsto (`round(pre_trigger_s·fs) + margem_amostras_antes`) |
| `parametros.inicio_impulso_s` (08) | só física | instante do impulso programado (80 ms; 90 ms a 50 Hz com `sorteio_posicao`; `arquivo/analises:docs/analise-2026-10-12/pendente/classe08_fronteira_REVISAR.md`) |
| `validacao_fisica.posicao_evento` (08) | só física | `inicio_previsto_amostra`, `pico_medido_amostra`, `desvio_amostras` (medido menos previsto), `tolerancia_amostras` (10) e `desvio_pico_pu`; fora da tolerância a captura é marcada inválida (`ok = false`, motivo "posição do impulso") |
| `validacao_fisica.posicao_evento.sobressinal_medido`, `sobressinal_limite`, `sobressinal_acima_do_limite` (08) | só física (v1.15, acrescentado) | sobressinal do impulso como fração do degrau programado A (`amplitude_bancada_pu`): `(medido − senoide ideal)` na amostra do maior desvio, dividido por A, menos 1 (`pico = s + A·(1 + sobressinal)`, a mesma grandeza de `SOBRESSINAL_DO_DEGRAU`). `sobressinal_limite` = 0,55 (`ROTEIRO_BANCADA.md` linhas 197 e 374); `sobressinal_acima_do_limite` é o flag de achado de segurança e **não** reprova a captura. Amostrado a 30 kSa/s contra uma oscilação de ~10 kHz, pode subestimar o pico real (que vale `pico_medido_v`). Ausente se não houve `amplitude_bancada_pu` |
| `rota_programacao` | só física (v1.15, acrescentado) | como a captura foi programada: `"CSIN"` (05, CSINusoid nativa, até 20 %), `"TRACe"` (waveform; 05 a 30 %) ou `"nativa"` (demais nativas). Só diagnóstico; não altera `gerar()` nem a fonte. Metadata anterior não tem o campo (a P-10 infere pelo nível `parametros.thd` e marca aviso) |
| `validacao_fisica.crista_modelo`, `fator_extremo_crista`, `crista_medida`, `crista_minima_aceita`, `crista_maxima_aceita` | só física (v1.15, revisão anterior) | crista do ciclo mediano da forma esperada, fator de extremo efetivo usado (o da previsão de pico; 1,0 na 08), crista medida e os limites aceitos (`crista_modelo × (1 − 0,10)` e `crista_modelo × fator × (1 + 0,10)`). `crista_esperada` continua igual a `crista_modelo` |
| `git_commit`, `git_sujo`, `numpy_versao` | só física | cópia da procedência (o `.jsonl` sobrevive sozinho se for copiado sem a pasta) |
| `calibracao_extremos_sha256` | só física | SHA-256 da calibração usada na captura; deve bater com `sessao.json` |
| `tres_versoes` | captura gravada pela v1.15 (em andamento) em diante | `{arquivo, programada}`: onde estão modelo/programada/medida desta captura (o `NN_classe.npz`) e como a programada foi obtida (`docs/tres_versoes.md`) |
| `arquivo_classe` | toda captura (formato 2) | nome do `NN_classe.npz` que guarda a captura (na pasta da sessão). Uma classe gravada com vários perfis tem as capturas de todos eles no mesmo arquivo (v1.15, acrescentado) |
| `indice_no_arquivo` | toda captura (formato 2) | linha da captura dentro do bloco do `perfil` no arquivo: `dados["<perfil>/medida"][indice_no_arquivo]`, 0-based. O mesmo `id_captura` existe em cada perfil de uma sessão `set perfil todos`; a chave única da captura é `(perfil, id_captura)` (v1.15, acrescentado) |
| `captura_compartilhada` | só com `set perfil todos`, classe que não depende do perfil | `true`: a captura existe uma vez no `NN_classe.npz`, no bloco de `perfil_de_origem`; as linhas dos outros perfis são a mesma captura (mesmo `id_captura`, `arquivo_classe`, `indice_no_arquivo`, `sha256_captura`) (v1.15, acrescentado) |
| `perfil_de_origem` | idem | perfil cujo bloco do `.npz` guarda os dados (`literatura`) (v1.15, acrescentado) |
| `compartilhada_com_perfis` | idem | lista de todos os perfis que apontam para a captura, origem primeiro (v1.15, acrescentado) |
| `sha256_captura` | idem | SHA-256 dos arrays da captura (`sessao_io.hash_captura`: `medida`, `modelo`, `programada` em float64 little-endian, com rótulo e tamanho; versão ausente = `NaN`) (v1.15, acrescentado) |
| `p09_braco` | toda captura (v1.15, acrescentado) | braço do experimento P-09 da conexão: `"A"` (padrão, modo AC), `"B"` (AC+DC, offset 0) ou `"C"` (AC+DC, offset por passo). `AMETEK_P09_BRACO`/`set p09`; no simulado, o da fonte simulada |
| `media_perdida_maxima_absoluta_pu` | captura TRACe/LIST com modelo e programada (v1.15, acrescentado) | maior `abs(média do ciclo no modelo − média do ciclo na programada)`, pu do pico nominal (`sinais.distancia_modelo_programada`, as mesmas contas de `scripts/analisar_modelo_programado.py`). A programada é a efetiva do braço (no C, com o offset por passo). Na física, o modelo é `gerar()` antes da redução de bancada (08) |
| `erro_rms_modelo_programada_pu` | idem | rms de `programada − modelo`, pu do pico nominal |
| `salto_pico_modelo_programada_v` | idem | `(max abs(programada) − max abs(modelo)) × base × √2`, em V: quanto o pico programado se afasta do pico do modelo. `pico_programado_v` (física) não muda |
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
| `rerun_de` | só em captura feita por `rerun`/`run falhas` (v1.15, acrescentado) | `{"sessao": pasta de origem, "id_captura": mesmo id, "perfil": ...}`; `seed`, `nivel_indice` e `id_captura` são os da captura original |

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
