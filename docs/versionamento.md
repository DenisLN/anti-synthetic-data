# Versionamento, registro de mudanças e arquivamento

Estado em 2026-10-12: a versão corrente é **v1.15, em andamento (não congelada)**. **Não existe nenhuma tag git** (`git tag` vazio); as versões v1.0 a v1.14 existem só como arquivos de `CHANGELOG/`. Por isso o metadata de sessões antigas grava só o hash (`994e170-dirty` nas sessões de 07/10). A regra do projeto é que a versão congelada tenha tag no GitHub e seja arquivada no Zenodo, e que toda sessão saia de commit limpo.

## 1. Regras

1. **Uma versão = um arquivo `CHANGELOG/vX.Y.md`** (minor sobe a cada conjunto de mudanças declarado; não há patch). O arquivo é escrito junto com o código, não depois.
2. **Congelar** a versão significa: testes verdes, CHANGELOG fechado, documentação conferida, árvore limpa, **tag** `vX.Y` no commit.
3. **Toda sessão de coleta sai de commit limpo** (idealmente do commit com a tag). O código grava `git_commit`, `git_sujo`, `versao_codigo` (`git describe --always --dirty --tags`), `numpy_versao`, `python_versao`, e uma cópia de `calibracao_extremos.json` com SHA-256 (`docs/metadata.md`). Árvore suja em bancada gera aviso em destaque, mas não bloqueia (`mestre.py:247-256`).
4. Registros datados (`CHANGELOG/vX.Y.md` já fechados, `arquivo/analises:docs/analise-*/`, `arquivo/analises:docs/superpowers/`) **não se reescrevem**; erros encontrados neles são corrigidos na documentação viva e anotados na análise da data. **Nota de 2026-10-13:** as análises datadas, `arquivo/analises:docs/superpowers/` e `arquivo/analises:docs/TAREFAS_NUVEM_2026-10-07.md` saíram de `docs/` e estão no branch `arquivo/analises`, nos mesmos caminhos. Neste documento e no resto de `docs/`, `arquivo/analises:<caminho>` significa esse caminho dentro desse branch. Os `CHANGELOG/vX.Y.md` fechados (v1.8 a v1.13) citam os caminhos antigos, que valem nesse branch.

## 2. Armadilhas do critério "limpo" (verificadas no código)
- `git_sujo` (`mestre.py:124-171`, `info_do_codigo`) vale para alteração rastreada em qualquer arquivo **e** para arquivo **novo não ignorado** dentro de `logica/`, `experimentos_nativos/`, `experimentos_waveform/`, `scripts/` e `diag/` (ex.: uma classe nova). Arquivo novo fora dessas pastas (ex.: uma nota em `docs/`) não marca a árvore. Faça `git add` e commit de tudo antes da sessão.
- A procedência (`git_commit`, `git_sujo`, arquivos novos) é recalculada **a cada pasta de sessão** (`preparar_pasta_da_sessao` chama `info_do_codigo(recalcular=True)`, `mestre.py:220`), ou seja, a cada `run` da CLI. A `versao_codigo` continua em cache no processo (`versao_do_codigo`, `mestre.py:98-110`): reinicie a CLI depois de commitar para ela refletir o commit.
- `set recalibracao on` altera `logica/calibracao_extremos.json` (arquivo rastreado): depois do run a árvore está suja de fato. Commite a calibração antes da próxima sessão de coleta. A cópia usada em cada sessão fica na pasta, com o SHA-256 em cada captura; como reverter: `docs/operacao.md` §9.
- Sem tag, `versao_codigo` é só o hash; com tag, aparece `v1.15` (exato) ou `v1.15-3-gabc1234` (3 commits depois) e `-dirty`.

### 2.1 O que "reproduz byte a byte" significa por plataforma
O `gerar()` usa `np.sin`/`np.cos`, cujo último bit depende da implementação (libm/SIMD) da plataforma. Medido (CHANGELOG/v1.15.md, "Fixtures portáveis"): neste Linux (Python 3.13, numpy 2.4.6) o array difere de uma referência em long double em até 2,2·10⁻¹⁶ pu (16 ULP) por amostra, em todas as 800 entradas dos fixtures.
- **Garantia entre plataformas (a que vale para o dataset arquivado com DOI):** o `gerar()` reproduz, dentro de `TOL_ABS = 1e-9` pu em somas e projeções e `rtol = 1e-9` nos parâmetros, os resumos gravados em `tests/fixtures/*.json` (chave `portavel`; `tests/assinatura_portavel.py`). Isto é cerca de 4 ordens de grandeza acima da diferença entre plataformas e 3 abaixo da resolução da fonte e do osciloscópio. Parâmetros, tamanho e sorteios (PCG64) saem idênticos.
- **Garantia bit a bit (SHA-256 dos bytes float64 + parâmetros):** só na plataforma onde os `hashes` foram gravados (Windows, Python 3.11.9, numpy 2.4.6). Nas demais plataformas os testes `*_exato_na_plataforma_de_origem` são pulados (`ASD_HASH_EXATO=1` os força).
- NÃO VERIFICADO: que os resumos gravados no Linux passam no Windows; só a suíte rodada lá confirma.

## 3. Procedimento de congelamento (executar só ao congelar a versão)

```powershell
git status --short                       # vazio (inclusive nada não rastreado relevante)
.\env\Scripts\python.exe -m unittest tests.test_offline    # OK
# CHANGELOG/vX.Y.md fechado; docs conferidos; README sem número de versão desatualizado
git tag -a vX.Y -m "vX.Y — resumo"       # só ao congelar a versão; a regra é descrever, não criar
git push origin main vX.Y
```
Depois, no GitHub, criar uma *Release* a partir da tag. **Zenodo** (procedimento geral da integração GitHub–Zenodo, ainda **não ligada neste projeto**): o repositório precisa estar ligado em zenodo.org (Settings → GitHub) **antes** de criar a release; cada release publicada gera um registro com **DOI** de versão (e um DOI "conceito" que agrupa todas as versões). O artigo cita o DOI da versão exata e, nas sessões, o `versao_codigo` do metadata (que deve coincidir com a tag). Metadados do depósito (título, autores, licença) são definidos pelos autores; desde 2026-10-27 o repositório tem `LICENSE`, `CITATION.cff` e `.zenodo.json` (§9).

## 4. Como escrever uma entrada de CHANGELOG
Título `# vX.Y — resumo (data)`. Seções usadas no histórico, nesta ordem quando aplicável:
1. **Por quê** — o que a bancada/análise mostrou (com sessão, números e fonte).
2. **O que mudou** — por item, com arquivo e função; o que afeta o dataset (`gerar()`) destacado.
3. **O que não mudou** — limites, validações e `gerar()` preservados (prova de que nada de segurança foi enfraquecido).
4. **Testes** — número da suíte e classes novas.
5. **NÃO VERIFICADO / Validação pendente** — o que só a bancada resolve, em lista.
Regras: afirme só o que viu (comando, saída, arquivo:linha); separe medido de hipótese; cite a análise datada em `arquivo/analises:docs/analise-AAAA-MM-DD/`.

## 5. Mensagens de commit (padrão do histórico)
`tipo: resumo em português`, com tipo em `feat`, `fix`, `docs`, `chore`, `merge` (ex.: `feat: regra de previsão de extremos por frequência`). Uma mudança lógica por commit; documentação de uma mudança vai junto ou logo depois. Sem `--no-verify`.

## 6. Mapa das versões

| Versão | Data aprox. | Resumo (arquivo em `CHANGELOG/`) |
|---|---|---|
| v1.0 | 2026-08-26/29 | arquitetura original, 20 classes, correção ciclo/frequência |
| v1.1 | 08-29 | sem SCPI cru nos experimentos; `mestre.py` orientado a objetos |
| v1.2 | 08-29 | grava dados puros além dos com ruído |
| v1.3 | 08-29 | `logica/` e `scripts/` |
| v1.4 | — | visualizador `.npz` (removido na v1.15) |
| v1.5 | — | rearme do Keysight nas nativas, `preflight_new.py`, `LIST:REPeat` |
| v1.6 | — | comissionamento: posição do distúrbio, CSINusoid, estado permanente |
| v1.7 | 09-09 | resiliência por classe, CLI interativa, `*WAI` |
| v1.8 | 09-11/12 | margem, diagnóstico, sessões isoladas, cobertura de níveis, `analisar_sessao.py` |
| v1.9 | 09-14 | hipótese `LIST:REPeat`, pontos de diagnóstico |
| v1.10 | 09-16/22 | `REPeat 0`, Digitizer descartado |
| v1.11 | 09-22 | caminho nativo íntegro, validação física, margem 20/50 ms |
| v1.12 | 09-30 | writes sincronizados, 08 caracterizada, bloqueio de pico: 20/20 a 127 V |
| v1.13 | 10-07 | capturas padrão, `set seed`, 220 V com limite de bancada, 380 V recusado |
| v1.14 | 10-07 | calibração por condição, cadeia de medição, Ctrl+C, recorte e relatório HTML |
| v1.15 | 10-12 (em andamento) | perfis, sorteio, compostas, regra por frequência, 08, 05/07/17/18, ruído na janela, três versões, correlação do distúrbio, metadata rastreável, `set recalibracao`/`set html`, fim dos geradores de PNG |

`CHANGELOG/v1.15.md` registra os itens de perfis, sorteio, compostas, regra por frequência, 08, 05/07/17/18, CLI e imagens. **Não** tem seção própria para: metadata rastreável (`arquivo/analises:docs/analise-2026-10-12/resolvido/metadata_mudancas.md`), três versões (`tres_versoes_mudancas.md`), correlação do distúrbio (`docs/correlacao_disturbio.md`) e ruído na janela (`snr_mudancas.md`); esses ficam documentados nos arquivos indicados. Os rótulos "v1.16" que existiam em comentários de `logica/sinais.py`, `scripts/gerar_tres_versoes.py` e `tests/test_offline.py` foram corrigidos para v1.15: a decisão de 2026-10-12 é manter tudo na **v1.15**.

## 7. Trabalho pendente fora da `main`
Branch `feat/passo-final-sin` (PR #3, **aberto, não mesclar antes da validação na bancada**): acrescenta um passo final com a forma interna `SINE` ao `LIST` das classes TRACe, com a variável `AMETEK_PASSO_FINAL_SIN`. Nada disso existe na `main`.

## 8. Índice do `CHANGELOG/`
`v1.0.md` … `v1.15.md` na pasta `CHANGELOG/`; cada arquivo é autocontido. Documentos de apoio: `arquivo/analises:docs/TAREFAS_NUVEM_2026-10-07.md` (tarefas da v1.13), `arquivo/analises:docs/analise-2026-09-21/` (sessões de 16/09), `arquivo/analises:docs/analise-2026-09-30/` (comissionamento v1.12), `arquivo/analises:docs/analise-2026-10-12/` (v1.15), `arquivo/analises:docs/superpowers/` (plano e design da v1.8).

## 9. Fluxo de publicação: código e dataset no Zenodo (P-20, preparado em 2026-10-27)

Decisão do dono (2026-10-27, conversa): **um registro Zenodo por versão do projeto**, com DOI, para o **dataset**; a release do **código** também pode ser arquivada pela integração GitHub–Zenodo. O repositório guarda só o código, os `CHANGELOG/`, os metadados de publicação (`LICENSE`, `CITATION.cff`, `.zenodo.json`) e, em cada pacote, o `SHA256SUMS`; nunca os dados (`resultados/` fica fora do git: binários sem diff útil). Licenças: código MIT; dataset e documentação CC-BY 4.0 (`docs/sobre.md` §3). **A tag `v1.15` e a publicação só depois de P-01 e P-31 resolvidas**; nada abaixo foi executado.

1. **Pré-condições:** P-01 (campanha com o código v1.15) e P-31 resolvidas; suíte verde; `CHANGELOG/v1.15.md` fechado; árvore limpa (§3). As sessões do dataset têm de ter `git_sujo = false` (§2).
2. **Tag e release do código:** tag anotada `v1.15` (§3) e *Release* no GitHub a partir dela. Antes da release, ligar o repositório em zenodo.org (Settings → GitHub); cada release publicada gera um registro de software. Os metadados vêm de `.zenodo.json` (autores, `license: mit`, `upload_type: software`); `CITATION.cff` é o formato que o GitHub lê para o botão "Cite this repository". NÃO VERIFICADO: qual dos dois a integração usa quando ambos existem (a documentação do Zenodo diz que `.zenodo.json` tem precedência).
3. **Pacote do dataset (offline):**
   ```powershell
   # saída padrão: resultados\_pacote\dataset_v1.15\
   python scripts\empacotar_dataset.py resultados\sessao_A [resultados\sessao_B ...]
   python scripts\empacotar_dataset.py --verificar resultados\_pacote\dataset_v1.15
   ```
   O pacote traz cópia dos dados e do metadata (as pastas de origem não são tocadas), `calibracao_extremos.json`, `SHA256SUMS`, `MANIFEST.json` (versão, `git_commit` e `git_sujo` de cada sessão, arquivos com tamanho e SHA-256), `README.txt` (licença CC-BY 4.0 e como verificar) e `zenodo_dataset.json` (`upload_type: dataset`, `license: cc-by-4.0`, `related_identifiers` com `isSupplementTo` apontando para a release do GitHub). O empacotador **recusa** sessão com `git_sujo` verdadeiro ou indeterminado; `--piloto` aceita e marca o pacote como piloto (`MANIFEST.json` e título), só para ensaio. Logs, `relatorio_*.html`, `sem_margem/`, `ruido_janela/` e `parcial/` não entram (derivados ou diagnóstico).
4. **Ensaio no Zenodo Sandbox** (sandbox.zenodo.org, conta e token próprios, registros descartáveis): enviar o pacote (de preferência `--piloto`), conferir título, autores, licença, relação com a release e os checksums mostrados pelo Zenodo. Qualquer DOI que o Sandbox mostre é de teste: não o cite nem o escreva em arquivo.
5. **Upload real** (zenodo.org), só com o pacote **sem** `--piloto` e verificado. O token do Zenodo (escopos de depósito) fica **somente em variável de ambiente** (por exemplo `ZENODO_TOKEN`), nunca em arquivo do repositório, em log, em commit ou em saída de comando. Este repositório não tem script de upload: o envio é feito pelo responsável, pelo site ou pela API.
6. **DOI de conceito versus DOI de versão.** Cada registro do Zenodo (o do código e o do dataset) tem um DOI de **versão** (esta publicação exata) e um DOI de **conceito** (agrupa todas as versões e aponta sempre para a mais nova). O artigo cita o DOI de versão do dataset e o do código; o de conceito serve para "todas as versões". Os DOIs só existem depois de emitidos: **não escrever DOI em arquivo algum antes disso** (a tag é imutável, então o `CITATION.cff` da própria tag não pode conter o DOI da sua release; ele entra depois, em commit posterior e em `docs/sobre.md`).
7. **Relação código-dataset.** O registro do dataset é `isSupplementTo` da release do código no GitHub (URL da tag). Quando os dois DOIs existirem, o responsável pode editar os metadados dos registros para apontar um ao outro pelo DOI.
