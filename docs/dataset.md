# Dados gerados: arquivos, formatos e ferramentas de análise

Formato campo a campo do metadata: `docs/metadata.md`. Três versões por captura: `docs/tres_versoes.md`. Perfis: `docs/perfis.md`. Leitura em Python: `logica/sessao_io.py`.

> **Quebra (v1.15, formato 2):** desde esta versão a bancada e o simulado gravam **um `NN_classe.npz` comprimido por classe**, com todos os perfis e as três versões; **não há mais um `.npz` por captura nem a pasta `tres_versoes/`**. Qualquer script que abra `NN_classe_<rótulo>.npz` ou `tres_versoes/...`, ou que leia `tensao_pu`/`modelo_pu` na raiz da sessão, precisa ler pelas chaves novas (seção 2) ou por `sessao_io.ler_capturas`. Sessões gravadas antes continuam como estão e continuam legíveis por `sessao_io`.

## 1. Onde os dados caem

`resultados/`, `logs/`, `env/`, `__pycache__/`, `backups/`, `*.zip` estão no `.gitignore`.

- **Bancada (CLI)**: cada `run`/`run all` cria **uma pasta nova** `resultados/sessao_<AAAA-MM-DD_HH-MM-SS>` (do segundo `run` da mesma CLI em diante, sufixo `_run02`, `_run03`, …) (`cli.py:199-218`). Reabrir a CLI ou rodar `mestre.py`/testes não sobrescreve sessões anteriores. (O README antigo dizia que o mesmo processo reusava a pasta; o código faz uma pasta por `run`.)
- **Simulado** (`mestre.py` direto, `run_simulation_windows.ps1`, testes): grava direto em `resultados/`, sem subpasta de sessão.

Conteúdo de uma pasta de sessão:

```
sessao_<ts>/
  sessao.json                    procedência (commit, numpy, python, SHA-256 da calibração) e condição da rodada
  falhas.json                    capturas puladas/descartadas/inválidas, classes que falharam e não executadas
                                 por orçamento, com contexto para `run falhas`/`rerun` (só se houve falha; docs/metadata.md)
  calibracao_extremos.json       cópia da calibração em uso
  sessao.log                     log de execução (flush por linha)          [só CLI]
  scpi_transcricao.log           W/Q/R de todos os comandos da AMETEK       [só CLI]
  NN_classe.npz                  UM por classe, comprimido: <perfil>/medida|modelo|programada
  snr_20db/ snr_30db/ snr_40db/  NN_classe.npz por classe e nível: <perfil>/tensao_pu (só a janela rotulada)
  corrente/                      NN_classe_corrente.npz, só com CAPTURE_CURRENT=1
  parcial/NN_classe/             spool por captura DURANTE a classe (some ao fim; ver "Escrita")
  metadata/NN_classe.jsonl       1 linha por captura e perfil (fonte para os leitores)
  metadata/NN_classe.json        os mesmos registros, indentados (leitura humana)
  sem_margem/                    criado por recortar_margem.py ou set html on
  relatorio_<sessao>.html        criado por relatorio_html.py ou set html on
```

## 2. Formatos

### Formato 2 (v1.15): um `.npz` comprimido por classe

`{id}_{nome_minúsculo}.npz`, gravado com `np.savez_compressed` (compressão sem perda: valores e dtypes iguais aos do `np.savez` de antes) em `logica/sessao_io.py` (`ArquivoDaClasse`). Vale para a bancada e para o simulado.

Chaves (para cada `<perfil>` presente em `perfis`: `norma`, `literatura`, `fronteira`; com `set perfil todos` os três, senão só o da rodada):

| Chave | Conteúdo |
|---|---|
| `formato_npz` | `2` |
| `classe` | nome da classe (texto) |
| `perfis` | perfis do arquivo, na ordem gravada |
| `tempo_ms` | eixo do registro da `medida`, em ms (8100 pontos na bancada, 6000 no simulado) |
| `tempo_janela_ms` | eixo da janela rotulada (6000 pontos), a grade do modelo e da programada |
| `<perfil>/id_captura` | `(N,)` texto; o MESMO id existe em cada perfil (a seed não depende do perfil) |
| `<perfil>/medida` | `(N, 8100)` na bancada (registro inteiro, com a folga de 20 ms antes e 50 ms depois; era o `tensao_pu` do `.npz` por captura); `(N, 6000)` no simulado, onde é a própria série do dataset (= `modelo`) |
| `<perfil>/modelo` | `(N, 6000)` o que `gerar()` produz |
| `<perfil>/programada` | `(N, 6000)` o que a fonte emite para o que foi programado; linha de `NaN` quando não foi calculada |
| `<perfil>/origem_programada` | `(N,)` texto (`PULSe`, `TRACe`, ...) |
| `<perfil>/inicio_janela` | `(N,)` int: onde a janela rotulada começa dentro da `medida` (0 no simulado) |

`N` capturas por perfil, empilhadas na ordem em que foram gravadas. A janela rotulada da medida é `medida[inicio_janela : inicio_janela + 6000]`. As strings são arrays Unicode (`<U`): `np.load` **sem** `allow_pickle`.

**SNRs ficam fora** do arquivo da classe: `snr_XXdb/NN_classe.npz` (um por classe e nível) com `formato_npz`, `classe`, `perfis`, `tempo_ms` (janela, a partir de 0), `<perfil>/tensao_pu` `(N, 6000)` e `<perfil>/id_captura`. A corrente (`CAPTURE_CURRENT=1`) vai para `corrente/NN_classe_corrente.npz` com `<perfil>/corrente_pu`, no mesmo molde.

**Capturas compartilhadas entre perfis (`set perfil todos`, v1.15).** Classe cujo `gerar()` não depende do perfil (`perfis.classes_independentes_do_perfil`: 01, 04, 07, 08, 09, 17, 18, 19; mais a 16 com `set sorteio off`) é capturada **uma vez**, sob o perfil canônico `literatura`: o `.npz` só tem o bloco `literatura/...` (`perfis = ["literatura"]`) e duas chaves a mais, `compartilhadas_perfis` (os perfis que apontam para ele, ex. `norma`, `fronteira`) e `compartilhadas_origem` (o perfil cujo bloco guarda os dados, mesma ordem). O mesmo vale em `snr_XXdb/` e `corrente/`. `sessao_io.ler_capturas(..., perfis=["norma"])` devolve a captura de `literatura` sob o perfil `norma`, com `compartilhada=True`, `perfil_de_origem="literatura"` e `espelho=True`; o metadata dos três perfis traz `arquivo_classe`, `indice_no_arquivo` e `sha256_captura` iguais (`hash_captura` em `logica/sessao_io.py`: SHA-256 de `medida`, `modelo` e `programada` em float64). Classes que dependem do perfil não mudam.

No metadata, cada captura diz onde está: `arquivo_classe` (nome do `.npz`), `perfil` e `indice_no_arquivo` (a linha dela dentro do bloco do perfil, 0-based). `docs/metadata.md`.

Tamanho: o `.npz` da classe guarda, por captura e perfil, medida + modelo + programada. Medido no simulado (classes 02 e 10, 200 capturas por perfil, os três perfis, 2026-10-13): 33,8 MiB e 31,1 MiB comprimidos contra 82,6 MiB dos arrays crus (≈ 41 %). Os `snr_XXdb/` são gravados **sem** compressão (ruído branco: 4,6 % de ganho medido, com custo de CPU a cada reescrita); a corrente e o arquivo da classe, comprimidos. NÃO VERIFICADO numa sessão real de bancada: a medida física tem ruído de bancada e deve comprimir menos que a simulada.

### Formato 1 (até a v1.15 sem tag), ainda legível

- **Físico**: `{id}_{nome}_{rótulo}.npz`, um por captura; rótulo = `chave-valor` do primeiro item de `parametros` (ex.: `02_sag_sag_pu-0.1.npz`) ou `capNN`; repetido ganha `_02`, `_03`. Chaves `tempo_ms`, `tensao_pu` `(1, 8100)`, `classe`, `id_captura` (arrays de objetos: `allow_pickle=True`). `snr_XXdb/` com o mesmo nome e `tensao_pu` `(1, 6000)`; `corrente/..._corrente.npz`; `tres_versoes/` com o mesmo nome (`modelo_pu`, `programada_pu`, `medida_pu`, `inicio_janela`, `origem_programada`).
- **Simulado**: `{id}_{nome}.npz` com `tensao_pu` `(N, 6000)` (não comprimido), `tempo_ms`, `classe`, `id_captura`; idem em `snr_XXdb/`; `tres_versoes/NN_classe.npz` com `modelo_pu`/`programada_pu` `(N, 6000)`.

`sessao_io.ler_capturas` abre os dois e devolve a mesma estrutura (`CapturaSessao`); no formato 1 o perfil vem do metadata (sem o campo, `literatura`). `nivel_indice` no metadata é sempre 0 no simulado: o nível da captura `i` vem de `i % len(NIVEIS)`, e `i = int(id_captura[-4:]) - 1`.

### Escrita
Atômica: todos os `.part` da classe (o `.npz` da classe, cada `snr_XXdb/`, `corrente/`) são escritos antes de qualquer `os.replace`; um erro no meio nunca deixa a classe meio gravada. Na bancada, cada captura vai também para `parcial/NN_classe/<perfil>__<NNNNNN>.npz` (atômica, sem compressão) **assim que existe**; ao fim de cada perfil, ou ao interromper a classe (exceção, `Ctrl+C`, falha de infraestrutura), o `NN_classe.npz` e o `metadata/NN_classe.jsonl` são reescritos com tudo o que a classe já tem, os perfis anteriores incluídos (`_finalizar_gravacao`), e o spool daquele perfil é apagado. Se o processo morrer antes disso, o spool fica e `sessao_io.recuperar_parcial(<sessao>)` o promove ao formato 2 preservando os outros perfis do arquivo. Rodar a mesma classe de novo no mesmo perfil, **com a mesma `Bancada`**, substitui o bloco desse perfil; com uma `Bancada` nova na mesma pasta, o arquivo da classe recomeça. Não há mais limpeza de órfãos: o nome do arquivo é fixo.

## 3. Metadata (resumo; completo em `docs/metadata.md`)

Campos de toda captura: `id_captura`, `classe`, `seed`, `simulado`, `perfil`, `arquivo_classe`, `indice_no_arquivo`, `sorteio_posicao`, (`inicio_disturbio_s`, `duracao_s`, `fase_graus` quando sorteados), `fs_hz`, `pontos`, `parametros`, `nivel_indice`, `snr_medido_db`, `snr_bancada_db`, `snr_efetivo_db`, `ruido_janela`, `tres_versoes`.

Só na captura física (`_contexto_da_sessao`, `mestre.py:1568`): `f0_hz`, `tensao_base_rms`, `probe_tensao`, `pre_trigger_s`, `margem_antes_s`, `margem_depois_s`, `diagnostico_mode`, `base_seed`, `capturas_override`, `capturas_padrao_classe`, `versao_codigo`, `git_commit`, `git_sujo`, `numpy_versao`, `calibracao_extremos_sha256`, `idn_fonte`, `idn_osciloscopio`, `escritas_trace_na_conexao`, `indice_trigger`, `escala_vertical_v_div`, `pico_medido_v`, `vale_medido_v`, `teto_extremos_v` (ou `extremos_indisponiveis`), `extremo_previsto_v`, `pico_programado_v`, `margem_amostras_antes/depois`, `amostras_totais`, `inicio_janela`, `inicio_janela_ajustado`, `pre_trigger_desvio_amostras`, `validacao_fisica`, e os `*_bancada`/`fator_disturbio_bancada` dentro de `parametros`.

Reproduzir qualquer captura: `base_seed` + `nivel_indice` + `capturas_override` + `perfil` + `sorteio_posicao`; a forma é `gerar()` com `np.random.default_rng(seed)`.

## 4. Carregar os dados

```python
import sys; sys.path.insert(0, "logica")
import sessao_io

# Qualquer formato: uma CapturaSessao por (captura, perfil)
for c in sessao_io.ler_capturas("resultados/sessao_X", classes=["02"], perfis=["norma"],
                                versoes=("medida", "modelo", "programada")):
    c.perfil, c.id_captura, c.versoes["medida"], c.versoes["modelo"], c.metadado   # metadado = a linha do perfil certo
    janela = c.versoes["medida"][c.inicio_janela : c.inicio_janela + 6000]
snr = sessao_io.ler_capturas("resultados/sessao_X", subpasta="snr_30db")            # sinal = tensao_pu com ruído
```

Direto, sem o módulo (formato 2):

```python
import numpy as np
d = np.load("resultados/sessao_X/02_sag.npz")
medida = d["norma/medida"]                  # (N, 8100) na bancada
modelo, prog = d["norma/modelo"], d["norma/programada"]
ruidoso = np.load("resultados/sessao_X/snr_30db/02_sag.npz")["norma/tensao_pu"]   # (N, 6000)
```

Seleção por captura (`capturas=` de `ler_capturas`, `--capturas` do HTML): ids (`02-0003`), posições 1-based dentro de cada classe e perfil (`3`) e intervalos (`1-3`).

## 5. Ferramentas offline (nunca tocam hardware nem alteram a sessão original)

| Comando | O que faz |
|---|---|
| `python logica\analisar_sessao.py <sessao>` | reconstrói `gerar()` com a seed e o metadata; imprime lag (ms), correlação, correlação do distúrbio e razão de pico por captura (`arquivo:perfil:id` no formato 2; o simulado vira um erro por arquivo e perfil). Só numérico (sem imagens desde a v1.15). `docs/correlacao_disturbio.md` |
| `python logica\recortar_margem.py <sessao> [--saida PASTA]` | grava a janela nominal em `<sessao>\sem_margem\` (mesma estrutura, sempre no formato 2; `recorte` no metadata). Lê os dois formatos: recortar uma sessão antiga também a converte. `--empilhar` é aceito e não faz nada (o formato 2 já é empilhado por classe) |
| `python logica\relatorio_html.py <sessao> [--saida F] [--titulo T] [--descricao D] [--snr 30] [--classes 02,05] [--perfis norma,fronteira] [--versoes medida,modelo,programada] [--capturas 02-0001,1-3] [--max-capturas-por-classe N] [--detalhes 0..3] [--largura-detalhe-ms X] [--detalhes-manuais J.json] [--com-esperado] [--dpi 100] [--modelo M]` | HTML autocontido (1 figura completa + até 3 detalhes por captura). `--perfis`/`--versoes`/`--capturas` escolhem o que entra; a 1.ª versão é o traço principal e as outras vão tracejadas por cima. `--max-capturas-por-classe` vale por classe e perfil; sem `--capturas` e sem limite explícito, bancada e simulação mostram até as 3 primeiras por classe e perfil; um aviso informa a limitação, e os arquivos originais permanecem completos. Acima de 20 MB avisa |
| `python scripts\gerar_tres_versoes.py <sessao> [--saida P] [--refazer]` | `tres_versoes/` de sessões do formato 1 (recusa o formato 2, que já traz as três versões) |
| `python scripts\gerar_ruido_janela.py <sessao> [--snr 20,30,40] [--saida P] [--refazer]` | `ruido_janela/` (AWGN só na janela); a saída segue o formato da entrada |
| `python scripts\recalibrar_extremos.py <sessao...> [--gravar] [--substituir] [--arquivo F]` | `docs/limites_e_calibracao.md` §5 |
| `python scripts\relatorio_limites_bancada.py --tensao V ...` | `docs/limites_e_calibracao.md` §6 |

Execute com `.\env\Scripts\python.exe` na raiz do projeto. Relatório HTML (ao fim do run ou à mão), recalibração e seleção por `--classes/--perfis/--versoes/--capturas`: `docs/operacao.md` §9.

## 6. Gerar o dataset simulado

```powershell
.\scripts\run_simulation_windows.ps1                              # 1 captura por classe (padrão do script)
.\scripts\run_simulation_windows.ps1 -CapturesPerClass 2000 -SnrLevels "20,30,40"
```
Força `BENCH_MODE=0` e `ARM_OUTPUT=NO`; roda `logica\mestre.py`. Sem o script, `SIM_CAPTURES_PER_CLASS` vale 2000 por padrão. O perfil e o sorteio vêm de `PERFIL` e `SORTEIO` do ambiente; `PERFIL=todos` gera os três perfis no mesmo `NN_classe.npz` (cada classe roda uma vez por perfil; as que não dependem do perfil, uma só vez, ver §2).

## Recuperação de sessões interrompidas (P-13)

Antes de criar a pasta do próximo `run`, `SessaoCLI._garantir_pasta_sessao` chama `sessao_io.recuperar_sessoes_interrompidas`. A operação trata somente arquivos de sessões anteriores: não abre instrumentos nem repete capturas. `recuperar_parcial` reconstrói os blocos de `parcial/`, mescla perfis já consolidados e seus metadados e grava a consolidação/metadata; o spool é removido somente depois da gravação bem-sucedida. Parciais inválidos devem ser informados e preservados para diagnóstico. O estado de teste e integração está em `execucao_pendencias.md`; isto não recupera medições que nunca foram gravadas no spool.
