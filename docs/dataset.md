# Dados gerados: arquivos, formatos e ferramentas de análise

Formato campo a campo do metadata: `docs/metadata.md`. Três versões por captura: `docs/tres_versoes.md`. Perfis: `docs/perfis.md`. Linhas: commit `d37e403`.

## 1. Onde os dados caem

`resultados/`, `logs/`, `env/`, `__pycache__/`, `backups/`, `*.zip` estão no `.gitignore`.

- **Bancada (CLI)**: cada `run`/`run all` cria **uma pasta nova** `resultados/sessao_<AAAA-MM-DD_HH-MM-SS>` (do segundo `run` da mesma CLI em diante, sufixo `_run02`, `_run03`, …) (`cli.py:199-218`). Reabrir a CLI ou rodar `mestre.py`/testes não sobrescreve sessões anteriores. (O README antigo dizia que o mesmo processo reusava a pasta; o código faz uma pasta por `run`.)
- **Simulado** (`mestre.py` direto, `run_simulation_windows.ps1`, testes): grava direto em `resultados/`, sem subpasta de sessão.

Conteúdo de uma pasta de sessão:

```
sessao_<ts>/
  sessao.json                    procedência (commit, numpy, python, SHA-256 da calibração)
  calibracao_extremos.json       cópia da calibração em uso
  sessao.log                     log de execução (flush por linha)          [só CLI]
  scpi_transcricao.log           W/Q/R de todos os comandos da AMETEK       [só CLI]
  NN_classe_<rotulo>.npz         captura pura (físico: 1 por captura)
  snr_20db/ snr_30db/ snr_40db/  mesma captura com ruído, só a janela rotulada
  corrente/                      só com CAPTURE_CURRENT=1
  tres_versoes/                  modelo / programada / medida
  metadata/NN_classe.jsonl       1 linha por captura (fonte para os leitores)
  metadata/NN_classe.json        os mesmos registros, indentados (leitura humana)
  sem_margem/                    criado por recortar_margem.py ou set html on
  relatorio_<sessao>.html        criado por relatorio_html.py ou set html on
```

## 2. Formatos

### Físico (uma captura por arquivo)
Nome: `{id}_{nome_minúsculo}_{rótulo}.npz`. O rótulo é `chave-valor` do **primeiro** item de `parametros` (ex.: `02_sag_sag_pu-0.1.npz`, `06_flicker_flicker_hz-10.3869.npz`) ou `capNN` quando não há parâmetro (`01_normal_cap01.npz`). Rótulo repetido na mesma rodada (várias capturas no mesmo nível) ganha `_02`, `_03`, … (`mestre.py:2292-2306`).

Chaves do `.npz`: `tempo_ms`, `tensao_pu` com shape `(1, 8100)` (20 ms antes + 200 ms + 50 ms depois, em pu), `classe`, `id_captura`. Em `snr_XXdb/` o mesmo nome, `tensao_pu` `(1, 6000)` (só a janela rotulada) e `tempo_ms` a partir de 0. Em `corrente/`, `..._corrente.npz` com `corrente_pu`.

### Simulado (uma classe por arquivo)
`{id}_{nome}.npz` com `tensao_pu` `(N, 6000)` (`N = SIM_CAPTURES_PER_CLASS`, float64), `tempo_ms`, `classe`, `id_captura` (um por linha); idem em `snr_XXdb/`. Sem margem, sem `corrente/` (salvo `CAPTURE_CURRENT`). O `.npz` não é comprimido: cada array de 2000 × 6000 float64 ocupa ≈ 91,6 MiB, e a classe grava o puro, um array por SNR e `tres_versoes/` (modelo + programada). `nivel_indice` no metadata é sempre 0 no simulado: o nível da captura `i` vem de `i % len(NIVEIS)`, e `i = int(id_captura[-4:]) - 1`.

### Escrita
Atômica: `.part` → `os.replace`. Uma execução interrompida deixa dado incompleto, nunca corrompido. No físico, o `metadata/*.jsonl.part` recebe uma linha por captura com `flush`+`fsync`. Rodar a mesma classe de novo com outro conjunto de capturas apaga os `.npz` órfãos da rodada anterior **só depois** de a rodada nova terminar inteira (`_finalizar_gravacao`, `mestre.py:2257`); numa rodada interrompida nada é apagado.

## 3. Metadata (resumo; completo em `docs/metadata.md`)

Campos de toda captura: `id_captura`, `classe`, `seed`, `simulado`, `perfil`, `sorteio_posicao`, (`inicio_disturbio_s`, `duracao_s`, `fase_graus` quando sorteados), `fs_hz`, `pontos`, `parametros`, `nivel_indice`, `snr_medido_db`, `snr_bancada_db`, `snr_efetivo_db`, `ruido_janela`, `tres_versoes`.

Só na captura física (`_contexto_da_sessao`, `mestre.py:1568`): `f0_hz`, `tensao_base_rms`, `probe_tensao`, `pre_trigger_s`, `margem_antes_s`, `margem_depois_s`, `diagnostico_mode`, `base_seed`, `capturas_override`, `capturas_padrao_classe`, `versao_codigo`, `git_commit`, `git_sujo`, `numpy_versao`, `calibracao_extremos_sha256`, `idn_fonte`, `idn_osciloscopio`, `escritas_trace_na_conexao`, `indice_trigger`, `escala_vertical_v_div`, `pico_medido_v`, `vale_medido_v`, `teto_extremos_v` (ou `extremos_indisponiveis`), `extremo_previsto_v`, `pico_programado_v`, `margem_amostras_antes/depois`, `amostras_totais`, `inicio_janela`, `inicio_janela_ajustado`, `pre_trigger_desvio_amostras`, `validacao_fisica`, e os `*_bancada`/`fator_disturbio_bancada` dentro de `parametros`.

Reproduzir qualquer captura: `base_seed` + `nivel_indice` + `capturas_override` + `perfil` + `sorteio_posicao`; a forma é `gerar()` com `np.random.default_rng(seed)`.

## 4. Carregar os dados

```python
import numpy as np, json
d = np.load("resultados/sessao_X/02_sag_sag_pu-0.1.npz", allow_pickle=True)
v = d["tensao_pu"][0]                      # 8100 amostras (físico), em pu do pico base
meta = [json.loads(l) for l in open("resultados/sessao_X/metadata/02_sag.jsonl", encoding="utf-8")]
ini = meta[0]["inicio_janela"]; janela = v[ini:ini + 6000]   # janela rotulada (ou use sem_margem/)
```
`id_captura` e `classe` são arrays de objetos: `allow_pickle=True`.

## 5. Ferramentas offline (nunca tocam hardware nem alteram a sessão original)

| Comando | O que faz |
|---|---|
| `python logica\analisar_sessao.py <sessao>` | reconstrói `gerar()` com a seed e o metadata; imprime lag (ms), correlação, correlação do distúrbio e razão de pico por arquivo. Só numérico (sem imagens desde a v1.15). `docs/correlacao_disturbio.md` |
| `python logica\recortar_margem.py <sessao> [--saida PASTA] [--empilhar]` | grava a janela nominal em `<sessao>\sem_margem\` (mesma estrutura; `recorte` no metadata). `--empilhar` gera 1 `.npz` por classe no formato simulado |
| `python logica\relatorio_html.py <sessao> [--saida F] [--titulo T] [--descricao D] [--snr 30] [--classes 02,05] [--max-capturas-por-classe N] [--detalhes 0..3] [--largura-detalhe-ms X] [--detalhes-manuais J.json] [--com-esperado] [--dpi 100] [--modelo M]` | HTML autocontido (1 figura completa + até 3 detalhes por captura). Acima de 20 MB avisa |
| `python scripts\gerar_tres_versoes.py <sessao> [--saida P] [--refazer]` | `tres_versoes/` de sessões antigas |
| `python scripts\gerar_ruido_janela.py <sessao> [--snr 20,30,40] [--saida P] [--refazer]` | `ruido_janela/` (AWGN só na janela) |
| `python scripts\recalibrar_extremos.py <sessao...> [--gravar] [--substituir] [--arquivo F]` | `docs/limites_e_calibracao.md` §5 |
| `python scripts\relatorio_limites_bancada.py --tensao V ...` | `docs/limites_e_calibracao.md` §6 |

Execute com `.\env\Scripts\python.exe` na raiz do projeto.

## 6. Gerar o dataset simulado

```powershell
.\scripts\run_simulation_windows.ps1                              # 1 captura por classe (padrão do script)
.\scripts\run_simulation_windows.ps1 -CapturesPerClass 2000 -SnrLevels "20,30,40"
```
Força `BENCH_MODE=0` e `ARM_OUTPUT=NO`; roda `logica\mestre.py`. Sem o script, `SIM_CAPTURES_PER_CLASS` vale 2000 por padrão. O perfil e o sorteio vêm de `PERFIL` e `SORTEIO` do ambiente.
