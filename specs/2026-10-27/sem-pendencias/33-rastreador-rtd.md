## Análise do orquestrador

- Implementação completa? Sim. Conferido pelo orquestrador: `docs/estado_prontidao.json` em esquema 2 com 13 concluídas, 11 aguarda-bancada, 7 aguarda-decisão (igual ao rastreador de 22/10); build `-E -W -n` exit 0; `projeto/pendencias.html` com 31 âncoras `estado-p-NN`; grep de tabelas manuais = 0; `tests.test_estado_pendencias` OK; `gerar_mapa_pendencias.py` exit 0 sem diff em `mapa/`.
- Pendências do usuário: nenhuma decisão. O caminho `--knap` (Node) não rodou no ambiente; o renderizador embutido substitui.
- Escopo limitou? Não.
- Resolve o contexto? Sim: o site passa a mostrar o estado commitado, gerado no build.
- Critério de Parada: atendido.
- Classificação: sem-pendencias. Os campos `como_tratada` vazios e P-02/P-08 sem "reprovada" são trabalho da spec 34, por desenho.

# Relatório: ASD: Rastreador de Pendências Integrado ao Read the Docs

Cinco commits locais na `main` (`83777d2`, `fd0fbd4`, `fd9d01f`, `114fad5`, `7262dfc`), sem push.

## Missão, item a item

**Item 1 — Definir um único arquivo de estado das pendências (pode ser o `docs/estado_prontidao.json` estendido) com, por P-NN: estado não binário (os quatro estados do rastreador mais "reprovada na bancada"), o que pede, como foi resolvida ou tratada (commits, evidência em `docs/evidencias/`), o que falta, quem fecha (bancada, decisão do dono, código) e decisão do dono registrada ou não; migrar para ele o conteúdo atual do rastreador sem mudar nenhum estado (a revisão dos estados é a spec seguinte).**
- Status: CUMPRIDO
- Explicação: `docs/estado_prontidao.json` virou `esquema: 2` (commit `83777d2`). Por P-NN: `estado` (`concluida`, `aguarda-bancada`, `aguarda-decisao`, `em-andamento`, `reprovada-bancada`), `acao` (o que pede), `criterio`, `dependencia`, `como_tratada`, `commits`, `evidencias`, `falta`, `quem_fecha`, `decisao_dono` {`registrada`, `texto`, `data`}, e ainda `titulo`, `prioridade`, `responsavel`, `frentes`, `situacao_execucao`, `entrega`, `direcao_vigente`. A migração foi feita por script único (scratchpad) a partir do rastreador (estado, falta, frentes), de `mapa/_modelos/pendencias.json` (prioridade, ação, dependência, critério, que era a cópia versionada do plano externo), das duas tabelas de `execucao_pendencias.md`, da coluna "O que fecha" do inventário de 16/10 (`quem_fecha`) e das "Resposta" de `decisoes_pendentes.md` (`decisao_dono`). Validação em `docs/_ext/estado_pendencias.py`. Formato documentado em `docs/contribuir_docs.md` seção 5. Limite honesto: o texto do rastreador mistura "o que foi feito" e "o que falta"; só nas 5 concluídas com "— (…)" (P-03, P-04, P-10, P-16, P-30) ele foi separado em `como_tratada` (e `falta` = "—"); nas demais ficou verbatim em `falta` e `como_tratada` é `null` (a spec 34 preenche). O estado `reprovada-bancada` existe na lista mas nenhum item o usa, porque P-02 e P-08 estão 🔧→🏭 no rastreador e a spec proíbe mudar estado.

**Item 2 — Fazer o site renderizar a partir desse arquivo, no build do Sphinx (extensão em `docs/_ext/` ou diretiva), o placar e a matriz das pendências dentro de `docs/projeto/pendencias.md`, com âncora por P-NN que as páginas de classe possam citar.**
- Status: CUMPRIDO
- Explicação: `docs/_ext/pendencias.py` (registrada em `docs/conf.py`) troca, no `source-read` de `projeto/pendencias`, o marcador `@@pendencias-estado@@` pelo Markdown de `gerar_markdown()`: placar, matriz (ID, estado em selo, prioridade, quem fecha, decisão do dono, o que falta) e uma seção `####` por pendência com a âncora `(estado-p-NN)=`. `docs/projeto/pendencias.md` ganhou "Estado vigente" antes do inventário de 16/10, que ficou intacto. O arquivo é validado antes e o build falha se for inválido. Comando: `sphinx-build -E -W -n --keep-going -b html docs <saída>` -> `build succeeded`, rc=0; `grep -c 'id="estado-p-' projeto/pendencias.html` = 31. As páginas de classe já citam `{ref}`P-NN <p-NN>`` (âncoras do inventário histórico, mantidas); as novas `estado-p-NN` ficam disponíveis, mas não reescrevi as 22 páginas de classe (não pedido).

**Item 3 — Eliminar as cópias de estado: `docs/PENDENCIAS_TRACKER.md` deixa de existir ou vira só o protocolo para agentes, sem tabela; `docs/execucao_pendencias.md` e `docs/decisoes_pendentes.md` passam a referenciar a página gerada em vez de repetir estados; `scripts/gerar_mapa_pendencias.py` passa a ler o arquivo único e regenera o `mapa/` (que fica na `main`) a partir dele, e `scripts/verificar_prontidao.py` lê o novo formato.**
- Status: CUMPRIDO
- Explicação: (a) `PENDENCIAS_TRACKER.md` agora só tem protocolo, frentes e "Depois da coleta"; o "Log de rodadas" (histórico datado) foi para `execucao_pendencias.md`. (b) `execucao_pendencias.md` perdeu a tabela "Decisões atuais" e a "Matriz de execução" (conteúdo migrado para o JSON) e remete a `projeto/pendencias`; `decisoes_pendentes.md` troca o link de estado e mantém as respostas (são decisão, não estado). `index.md` e `_includes/aviso-base.md` (46 páginas) apontam para `projeto/pendencias`. (c) `gerar_mapa_pendencias.py` lê só o JSON, valida e escreve `mapa/_modelos/pendencias.json` + 31 notas com renderizador embutido (sem `../entregas/` e sem Node); `--knap` mantém o caminho antigo. (d) `verificar_prontidao.py` aceita `estado` (novo) ou `status` (modelo antigo) e `P-01`/`P01`; `--manifesto docs/estado_prontidao.json` dá 18 faltantes `status concluida obrigatório` = 31 - 13 concluídas. (e) `fechar_pendencias.py`: só o formato do bloco proposto (`bloco_estado`) mudou, a lógica de decisão não.

**Item 4 — Criar teste offline que falhe quando o arquivo de estado estiver inválido (P-NN faltando ou repetido, estado fora da lista, evidência citada que não existe em `docs/evidencias/`) e atualizar `CLAUDE.md`/`AGENTS.md` com o fluxo novo ("depois da coleta: `fechar_pendencias.py` → editar o arquivo único → build").**
- Status: CUMPRIDO
- Explicação: `tests/test_estado_pendencias.py`, 17 testes: arquivo real válido; 31 ids na ordem; uma âncora por P-NN; mapa/ em dia com o JSON; e, sobre cópia corrompida, P-NN faltando, fora da faixa, repetido no JSON (`EstadoInvalido`), estado fora da lista, estado binário antigo, evidência inexistente, evidência fora de `docs/`, concluída sem evidência, `quem_fecha`/`decisao_dono`/commit/esquema inválidos. Falha com corrupção: saída de `validar()` com P-17 apagada, estado "quase" e evidência falsa: `P-17: pendência faltando`, `P-03: evidência 'evidencias/x/nao_existe.json': arquivo inexistente`, `P-05: estado 'quase' fora da lista [...]`; o build Sphinx numa cópia de `docs/` corrompida também abortou com esses erros. Passa com o real: `python -m unittest tests.test_estado_pendencias` = 17 OK. `CLAUDE.md` (linha 3 e "Depois da coleta") e `AGENTS.md` (mapa de documentação e item de pendências) trazem o fluxo.

**Item 5 — Registrar em `CHANGELOG/v1.15.md` e documentar o formato do arquivo numa página do site (por exemplo `docs/contribuir_docs.md`).**
- Status: CUMPRIDO
- Explicação: seção "Rastreador de pendências integrado ao Read the Docs (2026-10-27, mesma versão)" ao fim de `CHANGELOG/v1.15.md` (Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO); formato em `docs/contribuir_docs.md` seção 5 (tabela de campos, fluxo, validação); a tabela "O que o build verifica" ganhou a linha do arquivo de estado.

## Critério de Parada

Atendido, exceto o que depende do Knap (ver Achados).
- `mapa/` continua na `main`; `python scripts/gerar_mapa_pendencias.py` regenera as 31 notas e uma segunda execução não produz diff (`git status` limpo). Diff de estado: 0 linhas `status:` ou tag de estado alteradas em `mapa/pendencias/` (`git diff -U0 mapa/pendencias | grep -E '^[+-](status|  - (concluida|aguarda))' | wc -l` = 0). Diff de texto: linha "Estado geral" nas 31 notas (link novo) e o destaque de 5 concluídas (sem "— (…)").
- Tabela de conferência (estado antes no rastreador x estado na `projeto/pendencias.html` gerada, extraído da matriz do HTML): 31 de 31 iguais.

| P-NN | Antes (rastreador) | Depois (página gerada) | |
|---|---|---|---|
| P-01 | 🔧→🏭 Software pronto, falta bancada | Software pronto, falta bancada | igual |
| P-02 | 🔧→🏭 Software pronto, falta bancada | Software pronto, falta bancada | igual |
| P-03 | ✅ Concluída | Concluída | igual |
| P-04 | ✅ Concluída | Concluída | igual |
| P-05 | ❓ Falta decisão ou dado do responsável | Falta decisão ou dado do responsável | igual |
| P-06 | 🔧→🏭 Software pronto, falta bancada | Software pronto, falta bancada | igual |
| P-07 | ❓ Falta decisão ou dado do responsável | Falta decisão ou dado do responsável | igual |
| P-08 | 🔧→🏭 Software pronto, falta bancada | Software pronto, falta bancada | igual |
| P-09 | 🔧→🏭 Software pronto, falta bancada | Software pronto, falta bancada | igual |
| P-10 | ✅ Concluída | Concluída | igual |
| P-11 | ✅ Concluída | Concluída | igual |
| P-12 | ✅ Concluída | Concluída | igual |
| P-13 | ✅ Concluída | Concluída | igual |
| P-14 | ✅ Concluída | Concluída | igual |
| P-15 | ✅ Concluída | Concluída | igual |
| P-16 | ✅ Concluída | Concluída | igual |
| P-17 | ❓ Falta decisão ou dado do responsável | Falta decisão ou dado do responsável | igual |
| P-18 | 🔧→🏭 Software pronto, falta bancada | Software pronto, falta bancada | igual |
| P-19 | 🔧→🏭 Software pronto, falta bancada | Software pronto, falta bancada | igual |
| P-20 | ❓ Falta decisão ou dado do responsável | Falta decisão ou dado do responsável | igual |
| P-21 | 🔧→🏭 Software pronto, falta bancada | Software pronto, falta bancada | igual |
| P-22 | ❓ Falta decisão ou dado do responsável | Falta decisão ou dado do responsável | igual |
| P-23 | 🔧→🏭 Software pronto, falta bancada | Software pronto, falta bancada | igual |
| P-24 | ✅ Concluída | Concluída | igual |
| P-25 | ✅ Concluída | Concluída | igual |
| P-26 | 🔧→🏭 Software pronto, falta bancada | Software pronto, falta bancada | igual |
| P-27 | ✅ Concluída | Concluída | igual |
| P-28 | ❓ Falta decisão ou dado do responsável | Falta decisão ou dado do responsável | igual |
| P-29 | 🔧→🏭 Software pronto, falta bancada | Software pronto, falta bancada | igual |
| P-30 | ✅ Concluída | Concluída | igual |
| P-31 | ❓ Falta decisão ou dado do responsável | Falta decisão ou dado do responsável | igual |


- `git grep -nE '^\| P-[0-9]{2} \|' -- docs ':!docs/evidencias'`: sem saída (rc=1).
- Teste novo falha com arquivo corrompido e passa com o real (ver item 4). Build `-W` sem erro (rc=0).
- Suíte: `python -m unittest discover -s tests -p "test*.py"` = `Ran 777 tests in 129.765s`, `OK (skipped=2)` (760 + 17 novos).

## Pendências que exigem o usuário

Nenhuma obrigatória. Opcional: rodar `python scripts/gerar_mapa_pendencias.py --knap` num ambiente com Node/rede para conferir o modelo Knap.

## Limitações de escopo

- Nenhuma que impeça o resultado. Não mudei nenhum estado, nem `logica/`, `experimentos_*`, `docs/evidencias/`, CHANGELOG fechados nem `docs/requirements.txt`. As 22 páginas de classe seguem citando as âncoras históricas `p-NN` (reapontá-las para `estado-p-NN` fica fora do pedido).

## A missão resolve o contexto?

Sim: há um arquivo de estado, o site o renderiza no build (falha se inválido), o mapa e o verificador leem dele e as cópias de tabela sumiram; falta só a revisão dos estados e dos textos `como_tratada`/`falta`, que é a spec 34.

## Achados

- (Médio) NÃO VERIFICADO: `npx knap` não foi executado (o ambiente negou baixar/executar pacote externo). Por isso `gerar_mapa_pendencias.py` ganhou um renderizador embutido; ele foi comparado com as 31 notas que o Knap gerou antes e reproduz todas, salvo as mudanças intencionais acima. O modelo `pendencia.knap.md` só teve a linha "Estado geral" trocada, sem render.
- (Baixo) O marcador `@@pendencias-estado@@` vale só para `projeto/pendencias` (na primeira versão ele era substituído também em `contribuir_docs.md`, onde é citado, e gerou 31 rótulos duplicados; corrigido com a restrição por página).
- (Baixo) `P-02` e `P-08` constam "reprovadas em 22/10" no texto mas `aguarda-bancada` no estado; o novo estado `reprovada-bancada` está pronto para a spec 34.
- (Baixo) `decisao_dono.registrada = false` em P-11 a P-15, P-25 e P-27 só significa "sem resposta em `decisoes_pendentes.md`"; elas aparecem como concluídas por decisão registrada em outros lugares (`execucao_pendencias.md`).
- (Baixo) `docs/manifesto_prontidao.json` ainda é um modelo antigo (`P01`, `status`, tudo `aberta`), mantido porque os testes de `verificar_prontidao` o usam como modelo vazio; é a única cópia residual de formato.
- (Baixo) `scripts/fechar_pendencias.py` ainda grava `origem_do_criterio: "PENDENCIAS_TRACKER P-05/P-06/P-08"` (linhas ~507, 522, 582), nome que agora designa só o protocolo; mantido para não alterar a saída de `fechamento.json`.
- (Baixo) A nota do JSON `atualizado: 2026-10-22` vem do rastreador; a linha "branch feat/execucao-pendencias-v1-15" foi omitida por estar obsoleta.
- (Baixo) A execução criou `/tmp/sphinx-err-*.log` (traceback do build propositalmente quebrado); fora do repositório.
