# Versionamento, registro de mudanças e arquivamento

Estado em 2026-10-12: a versão corrente é **v1.15, em andamento (não congelada)**. **Não existe nenhuma tag git** (`git tag` vazio); as versões v1.0 a v1.14 existem só como arquivos de `CHANGELOG/`. Por isso o metadata de sessões antigas grava só o hash (`994e170-dirty` nas sessões de 07/10). O professor pediu que a versão congelada tenha tag no GitHub e seja arquivada no Zenodo, e que toda sessão futura saia de commit limpo.

## 1. Regras

1. **Uma versão = um arquivo `CHANGELOG/vX.Y.md`** (minor sobe a cada conjunto de mudanças declarado; não há patch). O arquivo é escrito junto com o código, não depois.
2. **Congelar** a versão significa: testes verdes, CHANGELOG fechado, documentação conferida, árvore limpa, **tag** `vX.Y` no commit.
3. **Toda sessão de coleta sai de commit limpo** (idealmente do commit com a tag). O código grava `git_commit`, `git_sujo`, `versao_codigo` (`git describe --always --dirty --tags`), `numpy_versao`, `python_versao`, e uma cópia de `calibracao_extremos.json` com SHA-256 (`docs/metadata.md`). Árvore suja em bancada gera aviso em destaque, mas não bloqueia (`mestre.py:216-223`).
4. Registros datados (`CHANGELOG/vX.Y.md` já fechados, `arquivo/analises:docs/analise-*/`, `arquivo/analises:docs/superpowers/`) **não se reescrevem**; erros encontrados neles são corrigidos na documentação viva e anotados na análise da data. **Nota de 2026-10-13:** as análises datadas, `arquivo/analises:docs/superpowers/` e `arquivo/analises:docs/TAREFAS_NUVEM_2026-10-07.md` saíram de `docs/` e estão no branch `arquivo/analises`, nos mesmos caminhos. Neste documento e no resto de `docs/`, `arquivo/analises:<caminho>` significa esse caminho dentro desse branch. Os `CHANGELOG/vX.Y.md` fechados (v1.8 a v1.13) citam os caminhos antigos, que valem nesse branch.

## 2. Armadilhas do critério "limpo" (verificadas no código)
- `git_sujo` usa `git status --porcelain --untracked-files=no`: um arquivo **novo não rastreado** (ex.: uma classe nova) não marca a árvore como suja. Faça `git add` e commit de tudo antes da sessão.
- A procedência é lida **uma vez por processo** (`_INFO_CODIGO_CACHE`, `mestre.py:129-131`): reinicie a CLI depois de commitar; commits feitos com a CLI aberta não aparecem.
- `set recalibracao on` altera `logica/calibracao_extremos.json` (arquivo rastreado). Depois do primeiro run a árvore está suja de fato (e a CLI ainda reporta o estado do início). Commite a calibração e reinicie a CLI antes da próxima sessão. A cópia usada em cada sessão fica na pasta e seu SHA-256 em cada captura.
- Sem tag, `versao_codigo` é só o hash; com tag, aparece `v1.15` (exato) ou `v1.15-3-gabc1234` (3 commits depois) e `-dirty`.

### 2.1 O que "reproduz byte a byte" significa por plataforma
O `gerar()` usa `np.sin`/`np.cos`, cujo último bit depende da implementação (libm/SIMD) da plataforma. Medido (CHANGELOG/v1.15.md, "Fixtures portáveis"): neste Linux (Python 3.13, numpy 2.4.6) o array difere de uma referência em long double em até 2,2·10⁻¹⁶ pu (16 ULP) por amostra, em todas as 800 entradas dos fixtures.
- **Garantia entre plataformas (a que vale para o dataset arquivado com DOI):** o `gerar()` reproduz, dentro de `TOL_ABS = 1e-9` pu em somas e projeções e `rtol = 1e-9` nos parâmetros, os resumos gravados em `tests/fixtures/*.json` (chave `portavel`; `tests/assinatura_portavel.py`). Isto é cerca de 4 ordens de grandeza acima da diferença entre plataformas e 3 abaixo da resolução da fonte e do osciloscópio. Parâmetros, tamanho e sorteios (PCG64) saem idênticos.
- **Garantia bit a bit (SHA-256 dos bytes float64 + parâmetros):** só na plataforma onde os `hashes` foram gravados (Windows, Python 3.11.9, numpy 2.4.6). Nas demais plataformas os testes `*_exato_na_plataforma_de_origem` são pulados (`ASD_HASH_EXATO=1` os força).
- NÃO VERIFICADO: que os resumos gravados no Linux passam no Windows; só a suíte rodada lá confirma.

## 3. Procedimento de congelamento (sem executar sem pedido do dono)

```powershell
git status --short                       # vazio (inclusive nada não rastreado relevante)
.\env\Scripts\python.exe -m unittest tests.test_offline    # OK
# CHANGELOG/vX.Y.md fechado; docs conferidos; README sem número de versão desatualizado
git tag -a vX.Y -m "vX.Y — resumo"       # só quando o dono mandar; a regra é descrever, não criar
git push origin main vX.Y
```
Depois, no GitHub, criar uma *Release* a partir da tag. **Zenodo** (procedimento geral da integração GitHub–Zenodo, ainda **não configurado neste projeto**): o dono liga o repositório em zenodo.org (Settings → GitHub) **antes** de criar a release; cada release publicada gera um registro com **DOI** de versão (e um DOI "conceito" que agrupa todas as versões). O artigo cita o DOI da versão exata e, nas sessões, o `versao_codigo` do metadata (que deve coincidir com a tag). Metadados do depósito (título, autores, licença) são do dono; o projeto hoje não tem arquivo de licença nem `CITATION.cff`.

## 4. Como escrever uma entrada de CHANGELOG
Título `# vX.Y — resumo (data)`. Seções usadas no histórico, nesta ordem quando aplicável:
1. **Por quê** — o que a bancada/análise mostrou (com sessão, números e fonte).
2. **O que mudou** — por item, com arquivo e função; o que afeta o dataset (`gerar()`) destacado.
3. **O que não mudou** — limites, validações e `gerar()` preservados (prova de que nada de segurança foi enfraquecido).
4. **Testes** — número da suíte e classes novas.
5. **NÃO VERIFICADO / Validação pendente** — o que só a bancada resolve, em lista.
Regras: afirme só o que viu (comando, saída, arquivo:linha); separe medido de hipótese; cite a análise datada em `docs/analise-AAAA-MM-DD/`.

## 5. Mensagens de commit (padrão do histórico)
`tipo: resumo em português`, com tipo em `feat`, `fix`, `docs`, `chore`, `merge` (ex.: `feat: regra de previsão de extremos por frequência (proposta 8)`). Uma mudança lógica por commit; documentação de uma mudança vai junto ou logo depois. Sem `--no-verify`.

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

`CHANGELOG/v1.15.md` registra os itens de perfis, sorteio, compostas, regra por frequência, 08, 05/07/17/18, CLI e imagens. **Não** tem seção própria para: metadata rastreável (`arquivo/analises:docs/analise-2026-10-12/resolvido/metadata_mudancas.md`), três versões (`tres_versoes_mudancas.md`), correlação do distúrbio (`docs/correlacao_disturbio.md`) e ruído na janela (`snr_mudancas.md`); esses ficam documentados nos arquivos indicados. Os rótulos "v1.16" que aparecem em comentários de `logica/sinais.py:500`, `scripts/gerar_tres_versoes.py` e `tests/test_offline.py` são anteriores à decisão do dono (2026-10-12) de manter tudo na **v1.15**.

## 7. Trabalho pendente fora da `main`
Branch `feat/passo-final-sin` (PR #3, **aberto, não mesclar antes da validação na bancada**): acrescenta um passo final com a forma interna `SINE` ao `LIST` das classes TRACe, com a variável `AMETEK_PASSO_FINAL_SIN`. Nada disso existe na `main`.

## 8. Índice do `CHANGELOG/`
`v1.0.md` … `v1.15.md` na pasta `CHANGELOG/`; cada arquivo é autocontido. Documentos de apoio: `arquivo/analises:docs/TAREFAS_NUVEM_2026-10-07.md` (tarefas da v1.13), `arquivo/analises:docs/analise-2026-09-21/` (sessões de 16/09), `arquivo/analises:docs/analise-2026-09-30/` (comissionamento v1.12), `arquivo/analises:docs/analise-2026-10-12/` (v1.15), `arquivo/analises:docs/superpowers/` (plano e design da v1.8).
