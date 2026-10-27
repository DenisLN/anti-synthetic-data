# Execução das pendências P-01 a P-31

Execução atualizada em 17/10/2026 (horário de Brasília). Baseline de código: `fa82f49600543456adf78e22485ab6de5dd032b9`, v1.15 em andamento. Esta página é o registro de trabalho atual; os changelogs fechados e relatos anteriores permanecem preservados.

Fonte do inventário: {doc}`projeto/pendencias`. A autorização do usuário nesta sessão determina implementar plenamente as pendências como atualização das escolhas anteriores. Não se interpreta um contrato antigo de teste como impedimento à atualização: P-14 passa a aplicar exclusões às listas, e P-15 passa a limitar o HTML também na bancada. Resultados de testes antigos devem ser atualizados para o novo contrato e acompanhados de regressões independentes.

O fork `rmlinxic/anti-synthetic-data`, com parent `DenisLN/anti-synthetic-data`, foi confirmado pela API. A baseline teve 497 testes aprovados. A integração do código em `58130af2e58b914e17b5e15615bdc655f905ca3f` executou **574 testes em 63,686 s: OK, com dois hashes específicos de Windows pulados no macOS**. Ambiente: Python 3.11.15/numpy 2.4.6; assinaturas portáveis executadas. A evidência e o log completos estão em `docs/evidencias/2026-10-17/`. Isso não equivale à execução no PC da bancada nem a uma validação física.

## Estados e critérios

- **Em implementação**: código em alteração, ainda sem fechamento da integração e dos testes.
- **Parcial**: uma parte verificável foi entregue; faltam itens explicitados.
- **Preparada / aguarda bancada**: existe roteiro ou ferramenta, mas faltam medições reais. Simulação não substitui medição.
- **Bloqueada por fonte/dados**: o material necessário não está disponível neste checkout.
- **Aberta**: falta trabalho ou decisão com evidência suficiente.

As mudanças funcionais estão implementadas e verificadas na suíte integrada. A P-13 inclui exclusão entre processos, recuperação após morte abrupta, fechamento explícito dos escritores e pastas exclusivas para CLIs iniciadas no mesmo segundo. Sessões legadas sem marcador de lock exigem recuperação explícita offline; a recuperação automática não pressupõe que qualquer pasta parcial esteja abandonada.

Nenhum item é encerrado apenas por existir um script. Um fechamento de software exige diff revisado e testes com comando, ambiente, SHA e resultado; um fechamento físico exige sessão original, configuração, calibração, logs e critério de aceite. Não há coleta física executada nesta revisão.

## Decisões atuais para implementação

A direção vigente de cada pendência (inclusive as decisões do responsável e a data) está no campo `direcao_vigente` e em `decisao_dono` de `docs/estado_prontidao.json`, renderizada em {doc}`projeto/pendencias`. Esta página não repete estados nem direções.

## Responsabilidade e sequência

O coordenador integra código, registra baseline e revisa critérios de aceite. Os subagentes trabalham em escopos separados: ORM/CLI; integridade e relatórios; análise de sinais; documentação e rastreabilidade; revisão independente. Escritores de módulos compartilhados combinam alterações com o coordenador. O operador presencial mantém as confirmações digitadas e a observação de OUTPUT OFF, fiação e probe.

1. Preparar checkout e ambiente identificados; registrar `git status`, versões e suite descoberta.
2. Implementar P-04/P-13/P-14/P-15 com regressões offline; corrigir P-23/P-24 e documentação do contrato.
3. Executar análises P-09/P-11/P-12/P-22/P-28/P-31; integrar SINE separadamente em P-18, com revisão.
4. Preparar campanha com diagnósticos antes da coleta conforme `docs/roteiro-bancada.md`. P-26 fixa as condições antes de energizar.
5. Incorporar sessões reais e fontes faltantes; revisar cada ID e publicar somente o que estiver comprovado.

## Matriz de execução

O estado, o que falta, a entrega de cada rodada e o critério de aceite de P-01 a P-31 estão em `docs/estado_prontidao.json` (campos `estado`, `situacao_execucao`, `entrega`, `falta`, `criterio`) e são renderizados no build em {doc}`projeto/pendencias`, com âncora por pendência (`estado-p-NN`). A tabela que existia aqui foi migrada para esse arquivo em 2026-10-27, sem mudar nenhum estado.

## Registro de rodadas (uma linha por rodada, mais recente no topo)

Migrado de `docs/PENDENCIAS_TRACKER.md` em 2026-10-27. É histórico datado: os estados citados valem na data de cada linha, não hoje.

 (uma linha por rodada, mais recente no topo)

- 2026-10-22 — Visita à bancada (Inspiron, COM10): Blocos 1–9 e 8-A completos a 127 V/60 Hz, parada no braço A da P-09. Fechamento parcial (`evidencias/2026-10-22/fechamento.json`): **P-03 e P-10 concluídas**; P-05, P-07, P-17, P-22, P-28 e P-31 com evidência suficiente aguardando revisão; P-02 e P-08 reprovadas; P-09 sem suporte a offset por passo. Correções: recalibração 127 V/60 Hz, forma volta à senoide depois de classe waveform (THD de 18/19), visita (P-09, Bloco 7, 50 Hz). 759 OK.

- 2026-10-21 — Visita num comando: `scripts\VISITA_BANCADA.cmd` conduz os Blocos 1–10, 8-A, 10-A, 10-B, as cinco condições da P-26 (com calibração P-21 de 220/33 V) e o fechamento; CLI ganhou modo roteiro (`--comando`), as confirmações seguem com o operador. 754 OK.

- 2026-10-21 — Pedido do responsável: capacidades da MX30 conferidas antes de I/O (LIST ≤32, TRACe ≤50, dwell, PULSe, offset), captura que excede é pulada e a bateria segue; orçamento esgotado desliga e registra; `falhas.json`; `run falhas` / `rerun`. Revisão Opus OK; 726 OK no Mac e no Inspiron (`suite.ps1`, EXIT=0, sem instrumentos).

- 2026-10-21 — P-09: experimento A/B/C (braço A byte a byte idêntico; B = AC+DC; C = offset por passo, com consulta de suporte e recusa sem fallback; métricas modelo→programada no metadata); revisão Opus sem violação de limites, 3 achados corrigidos; 704 OK. Bloco 10-B no roteiro.

- 2026-10-21 — **P-30 concluída** (decisão D: contagens históricas não verificáveis). P-09: implementação do experimento A/B/C (OFF por padrão) em andamento.

- 2026-10-21 — P-29: decisão B (logs novos). P-20: aguarda Denis. P-09: alternativas pesquisadas (manual p. 96/126); plano (d)+(b)-simulado+consulta na bancada. P-30: proposta D aguardando confirmação.

- 2026-10-21 — P-26 decidida (todos, padrão, ACDC só a 127 V); passa a aguardar só a conferência nas sessões. Roteiro atualizado.

- 2026-10-21 — P-26 parcial: responsável fixou as cinco condições. Plano offline (`evidencias/2026-10-21/plano_campanhas_5_condicoes.json`): 230/50 com 13 recusas (swells), 220/60 sem calibração e 52 recusas, 33/60 sem calibração. `bancada_pendencias.md` ganhou "Campanhas por condição".

- 2026-10-21 — Mapa Obsidian (skills oficiais kepano/obsidian-skills `3ccff53`): `mapa/` com 31 notas P-NN geradas por Knap, 15 cartões de módulo (dependências do grafo real de imports), 6 hubs de domínio, `Pendencias.base`, `Mapa.canvas`; `CLAUDE.md` na raiz aponta para o mapa.

- 2026-10-21 — Inspiron 15 (DESKTOP-FSEESJI) definido como PC da bancada e preparado (Python 3.11.9, env validado, NI-VISA, energia/USB, atalho START_BENCH). **P-16 concluída** (8/8 critérios do agregador). Drivers: NI-VISA 26.5 (passaportes USB e serial; PyVISA usa `visa32.dll`) e driver USB da AMETEK (TUSB3410, `usbuart3410.inf` 6.7.2.0, WHQL, do download oficial "USB VCP Driver" da página MX; cópia em `C:\drivers_bancada\ametek_vcp`). Falta: ligar os instrumentos, ajustar a porta da AMETEK para COM10 e conferir `*IDN?` dos dois sem energizar.

- 2026-10-21 — Software das P-03 (sobressinal gravado), P-10 (rota + sequência Bloco 8-A), P-22/P-31 (ferramentas sobre sessões reais) e roteiro sem contradições; revisão Opus sem achado alto; 680 OK. Inspiron 15 (DESKTOP-FSEESJI) preparado: Python 3.11.9, env com versões validadas, NI-VISA. Restante destas quatro: só bancada.

- 2026-10-20 — Revisão independente (Opus) do trabalho do Codex e desta sessão: sem violação dos limites; P-04, P-11–P-15 confirmadas no código. 17 achados corrigidos (ver CHANGELOG "Correções da revisão independente"); 650 OK. Lacunas abertas: campo de sobressinal na coleta (P-03), hostname no benchmark (P-22), `TRACe:DEFine` no orçamento (P-23, decisão).

- 2026-10-20 — C: integradas as frentes K (`fechar_pendencias.py`, `validar_pc_bancada.ps1`, 18 testes), R (`bancada_pendencias.md`) e D (`decisoes_pendentes.md`); 633 OK; Sphinx -W OK. **Próximo:** responsável preenche `decisoes_pendentes.md`; resolver as 4 contradições do roteiro (CHANGELOG v1.15, kit de fechamento); visita à bancada seguindo `bancada_pendencias.md`; rodar `fechar_pendencias.py` e atualizar esta matriz.
- 2026-10-20 — C: commit `f974954` (P-28 preservação do bruto); criado este rastreador.
- 2026-10-17 — Codex: 9 concluídas (P-04, P-11–P-15, P-24, P-25, P-27); suíte 574 OK; evidências em `evidencias/2026-10-17/`.

## Verificação e registro de evidência

```powershell
.\env\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v
git rev-parse HEAD
git status --short
.\env\Scripts\python.exe -c "import sys,numpy; print(sys.version); print(numpy.__version__)"
```

O resultado consolidado é 574 testes, OK com dois skips de hashes Windows, e está em `evidencias/2026-10-17/validacao_software.json`. A baseline tinha 497 métodos identificados estaticamente; não fixar esse total após acrescentar módulos de teste. Resultado, skips, duração e hash exato dependem do ambiente. Não alterar fixtures apenas para obter verde.

Para sessões físicas: SHA/estado git, classe/perfil/seed, tensão/frequência, probe e configuração, calibração/hash, versão de firmware quando disponível, arrays originais e `sessao.log`/`scpi_transcricao.log`. Uma análise derivada usa outra saída e preserva os originais. Fonte ausente, ausência de licença ou falta de operador não se resolvem com uma afirmação documental de conclusão.

## Ferramentas e evidências offline entregues

Os arquivos em `docs/evidencias/2026-10-16/` são resultados reprodutíveis de software. Não são capturas físicas e não encerram as partes de bancada. Não regenerar por cima dos resultados: os scripts recusam sobrescrita de JSON; use outro destino para uma repetição.

```powershell
.\env\Scripts\python.exe diag\analisar_modelo_programado.py --saida modelo_programado_novo.json
.\env\Scripts\python.exe diag\analisar_reamostragem.py --sintetico --saida reamostragem_nova.json
.\env\Scripts\python.exe diag\benchmark_sessao_io.py --capturas 3 10 30 --saida benchmark_novo.json
```

- `docs/evidencias/2026-10-16/modelo_programado.json`: seis classes, três perfis, 50/60 Hz e três seeds; representação TRACe/LIST comparada ao modelo, perda da média por ciclo e correlações nominal/ajustada. Sem hardware, calibração ou redução de bancada.
- `docs/evidencias/2026-10-16/reamostragem_sintetica.json`: comparação sintética entre interpolação linear e FIR anti-aliasing; não é avaliação do bruto do osciloscópio real.
- `docs/evidencias/2026-10-16/benchmark_sintetico.json`: writer real com dados sintéticos, integridade de leitura e aliases; diretório temporário/cache, sem `fsync`, e `tracemalloc` não equivale a RSS.
- `docs/evidencias/2026-10-16/limites_50hz.md` e `limites_60hz.md`: relatórios offline de limites, não medições.
- `docs/evidencias/2026-10-16/plano_campanhas.json`: planejamento offline por condição; não registra campanha executada.

A documentação de referência importada usa permalinks do snapshot `fa82f49600543456adf78e22485ab6de5dd032b9` para citações históricas de linhas. Os 25 `literalinclude` selecionam objetos por símbolo, verificados por AST contra o checkout atual; não dependem de números de linha. As alterações atuais de contrato estão identificadas nas páginas CLI/ORM/persistência/HTML/SINE, além desta matriz.

### Verificação local do site

`sphinx-build -W -n --keep-going -b html docs <pasta de saída>` concluiu com código 0 e `build succeeded`, após as referências serem auditadas. Configuração Sphinx 9.0.4/MyST 5.1.0/Furo 2025.12.19 conforme `docs/requirements.txt`. Sem supressão geral de avisos; o filtro específico de três links de changelogs fechados já existente no branch do site foi preservado. Artefatos brutos `evidencias/**` são excluídos das páginas Sphinx, sem alterar seu conteúdo.

A inspeção estrutural do HTML confirmou 32 linhas e cinco colunas na tabela geral de pendências (incluindo P-03), 15 linhas e três colunas na tabela de decisões e link para o estado atual no índice. Isso comprova geração e estrutura, não publicação do site remoto ou validade física dos relatos.

## Critério final de encerramento

As 31 pendências devem ter evidência de conclusão. Depois do tratamento delas, será feita a auditoria completa das especificações da AMETEK e a validação das sessões exigidas: 127 V/60 Hz, 127 V/50 Hz, 230 V/50 Hz, 220 V/60 Hz e 33 V/60 Hz. A ordem foi definida pelo usuário; o planejamento offline não representa execução dessas sessões. O verificador `scripts/verificar_prontidao.py` não declara o projeto pronto enquanto faltam evidências e dados físicos. `docs/manifesto_prontidao.json` é um modelo vazio; `docs/estado_prontidao.json` é o arquivo único de estado das 31 pendências (formato em {doc}`contribuir_docs`). Use `python scripts/verificar_prontidao.py --manifesto docs/estado_prontidao.json` para verificar o estado registrado; seu código de saída 1 é esperado enquanto houver lacunas.
