# Decisões pendentes do responsável

Formulário para responder de uma vez. Cada item traz o dado concreto, as opções e a recomendação técnica (marcada com **[recomendado]**). A recomendação não é decisão do projeto: só vale depois de preenchida em "Resposta". Estado geral em [](PENDENCIAS_TRACKER.md) e critérios em [](execucao_pendencias.md).

Nada aqui cria licença, autoria, DOI ou fonte de dados. Onde falta informação, o item pede que o responsável a forneça.

## Achados da busca de fontes (somente leitura, todos os branches locais)

Branches consultados: `origin/main`, `origin/feat/execucao-pendencias-v1-15`, `upstream/main`, `upstream/arquivo/analises` (49c1d28), `upstream/docs/site-readthedocs`, `upstream/feat/passo-final-sin`, `upstream/claude/specs-v1-15-review-3w2bgl`.

- **P-29 (logs reais):** nenhum `scpi_transcricao.log` nem `sessao.log` existe em qualquer branch ou no histórico. Os únicos `.log` versionados são `docs/evidencias/2026-10-17/build_documentacao.log` e `testes_offline.log` (branch de execução, não são de bancada). `upstream/arquivo/analises:specs/2026-10-15/com-pendencias/06-auditoria-arquitetura.md` (linhas 62 e 73) registra que as três `scpi_transcricao.log` de 07/10 ficam só em `resultados/` local, ignorado pelo git. O que existe versionado de bancada são dados de 30/09: `upstream/arquivo/analises:docs/analise-2026-09-30/dados/sessao_2026-09-30_{15-08-45,15-18-50,15-26-05,15-58-51}/*.jsonl` (JSONL por classe, não transcrição SCPI) e `docs/analise-2026-09-30/ANALISE.md`.
- **P-30 (99 × 63):** os dados não bastam para a tabela por sessão. Nenhum branch contém registro por sessão de 07/10 (nem metadata, nem `ESTADO`, nem lista de capturas), e a divisão 36+36+27 não aparece em texto algum do histórico (`git log --all -S'36+36+27'` vazio). O que existe: 63 em `AGENTS.md:125` e `CHANGELOG/v1.15.md:9` ("as 63 capturas de 07/10 ficam como piloto", `origin/main`); 99 em `docs/tres_versoes.md:59` (`origin/main`: programada mais perto da medida em 70, empate em 28, pior em 1; 70+28+1 = 99); a incoerência está registrada como A-8 em `upstream/arquivo/analises:specs/2026-10-15/com-pendencias/06-auditoria-arquitetura.md:97`; e `08-fichas-revisao-final.md:134` informa que as três sessões de 07/10 têm `versao_codigo = 994e170-dirty`. **Falta:** as três pastas `resultados/sessao_2026-10-07_*` (metadata de cada sessão e lista de capturas) e a definição de "piloto" (item P-30 abaixo).
- **P-27 / `validacao_gerador_v1.14.md`:** nenhum arquivo com esse nome existe em nenhum commit (`git log --all -- '*validacao_gerador*'` vazio). Só há menções em texto: `origin/main:docs/correlacao_disturbio.md:80` e `06-auditoria-arquitetura.md:65` ("não está em nenhum branch"). As faixas dele já foram retiradas como critério de aceite no branch de execução.
- **P-20 (publicação):** não existe `LICENSE`, `COPYING`, `CITATION.cff`, `.zenodo.json`, `AUTHORS` nem `CODEOWNERS` em branch algum, nem foram removidos no histórico. `README.md` e `CHANGELOG/*.md` não declaram licença, autoria, citação nem DOI. Autores de commit presentes: Denis / Denis Loyola / Denis Nata Henden Loyola (DenisLN, upstream), rmlinxic (fork) e commits "Claude". Isso é registro de commit, não declaração de autoria ou de direitos.

## P-09 Perda da média por ciclo

**Contexto.** A programada (LIST) não reproduz o deslocamento de média por ciclo do modelo. Em `docs/evidencias/2026-10-16/modelo_programado.json` (108 registros, classes 06, 10, 11, 12, 15, 16, perfis norma, literatura e fronteira, 50 e 60 Hz, 127 V, simulação offline) a perda máxima absoluta é 0,0009 a 0,0166 pu na 06, 0,0026 a 0,029 pu na 15 e 0,018 a 0,288 pu nas compostas com sag (10, 11, 12, 16); mediana geral 0,072 pu (mediana dos 108 valores de `media_perdida_maxima_absoluta_pu`), máximo 0,288 pu (classe 16, 50 Hz). A fração de pu é do pico nominal 127 V x raiz de 2. Compensação física depende de P-17 (ACDC) e de dados reais.

- A. Aceitar como limitação documentada, sem compensar. **[recomendado]**
- B. Não aceitar; abrir investigação de offset por passo (exige P-17 e bancada).
- C. Aceitar só para as classes 06 e 15 (perda abaixo de 0,03 pu) e tratar as compostas à parte.

Resposta (21/10/2026, responsável): aceitar como limitação **somente se** as alternativas não se confirmarem. Resultado da pesquisa:
  - Mecanismo: a fonte remove o DC de toda TRACe (manual SCPI, p. 126) e `montar_programacao` zera a média de cada ciclo; só existe um `dc_offset_pu` global por captura. A perda é estrutural.
  - (b) Offset DC por passo de LIST em AC+DC: `LIST:VOLT:OFFS` aparece no manual só como "Related Command" (p. 96), sem definição, então não está confirmado. Em simulação reduz o erro rms de 0,097 para 0,0015 pu (classe 16). Depende da P-17 (déficit de 5–6 % na CA em AC+DC).
  - (c) TRACe com média embutida: inviável pelo manual (DC removido).
  - (d) Validar a fidelidade física contra a programada e publicar a distância modelo→programada por captura: viável agora, só software.
  - Plano: (1) agora, implementar (d) e prototipar (b) em simulação, com testes; (2) na bancada, com a saída desligada, consultar `LIST:VOLT:OFFS?` em AC+DC e ler `SYST:ERR?`; (3) se o comando existir, medir (b) na 16 depois da P-17; senão, fechar a P-09 como limitação aceita com (d).

## P-18 SINE (passo final) desligado por padrão

**Contexto.** O passo final SINE está integrado com `AMETEK_PASSO_FINAL_SIN=0` / `passo_final_sin=False`. Cobertura offline existe; a aceitação LIST/forma/restauração na fonte real nunca foi medida.

- A. Manter desligado por padrão até validação em bancada; ligar só por variável explícita. **[recomendado]**
- B. Ligar por padrão (não recomendado sem a validação física).
- C. Retirar o código até haver bancada.

Resposta:

## P-20 Licença, autoria, citação, tag v1.15, Zenodo

**Contexto.** Nenhum arquivo de licença, citação ou metadado Zenodo existe em qualquer branch. O fork não concede direitos de relicenciamento, então a licença deve vir do titular do repositório de origem. A v1.15 está sem tag e P-01 (campanha com o código v1.15) ainda não ocorreu.

Preencher, sem sugestão minha de conteúdo:

1. Licença do código (nome do SPDX, ou "ainda não definida"):
2. Licença do dataset e da documentação (pode diferir da do código):
3. Quem autoriza a licença (titular do upstream? anuência por escrito?):
4. Autores e ordem, com afiliação e ORCID, para `CITATION.cff` e `.zenodo.json`:
5. Texto de citação preferido:

Quando tagear a v1.15:

- A. Só após P-01 (campanha com o código v1.15) e P-31 decidida; Zenodo depois da tag. **[recomendado]**
- B. Tagear agora como pré-lançamento (rótulo `-rc`), sem Zenodo.
- C. Tagear agora e publicar no Zenodo (o DOI só existe depois de emitido; não escrever DOI antes).

Zenodo:

- A. Publicar só depois da licença e da autoria aprovadas. **[recomendado]**
- B. Não publicar.

Resposta: aguardar o Denis (21/10/2026). Nenhuma licença, autoria, citação ou DOI será criada antes da resposta dele.

## P-23 Orçamento de 216 gravações TRACe por conexão

**Contexto.** O orçamento de 216 gravações por conexão está aplicado no CLI, na entrada principal e no ORM (recusa acima disso antes de abrir instrumentos; esgotamento aborta sem retry). O roteiro recomenda grupos abaixo de 250. O valor não é garantia física; a causa da trava segue sem diagnóstico real.

- A. Manter 216 como regra operacional e como proteção de software, registrando que não é limite físico comprovado. **[recomendado]**
- B. Mudar o valor (informar qual e a base de medição).
- C. Tornar configurável por variável de ambiente, padrão 216.

Resposta:

## P-21 Fatores de extremo a 220 V/60 Hz (condição sem tabela)

**Contexto.** `carregar_fatores_extremo` trata 220 V/60 Hz como condição sem tabela: toda classe usa o maior fator já medido (1,615 desde 2026-10-22), menos a 01. Na rodada de calibração de 220 V só cabem 07, 10, 11, 15 e 16 (e parte da 12 e da 20). A regra foi decidida na v1.14 (`CHANGELOG/v1.14.md`, "Condição sem tabela"): a v1.13 rodava 220 V com a tabela de 127 V, "o mesmo raciocínio que deixou passar os 444 V" (17 a 230 V/50 Hz com a tabela de 127 V/60 Hz, acima dos 425 Vp do hardware). A mesma v1.14 concluiu depois que o sobressinal depende da frequência, não da tensão; mas essa evidência vem de 127 × 230 V a 50 Hz com capturas reduzidas, que só dão limite inferior do fator. A 220 V o limite de bancada leva o previsto até o teto, com só a margem de 1,10 de folga.

- A. Manter a regra atual; a rodada de 220 V calibra só as classes que cabem. **[recomendado em 2026-10-22, escolhido pelo operador]**
- B. Condição com tabela de mesma frequência (127 V/60 Hz) usa o fator da própria classe nessas tabelas, como a condição calibrada. A 220 V caberiam todas menos 05, 14, 17, 18, parte de 13/19 e a 03 no perfil norma.
- C. Decidir B depois das campanhas de 127 V/50 Hz e 230 V/50 Hz, que medem se o fator muda com a tensão na mesma frequência (sem redução nas capturas comparadas).

Resposta (2026-10-22, operador na bancada): A por enquanto; decisão final do responsável. Análise: `evidencias/2026-10-22/LEIA-ME.md`.

## P-26 Campanha: perfis, frequências, tensões, ACDC 230 V

**Contexto.** As condições devem ser fixadas antes de energizar (ver [](roteiro-bancada.md)). O roteiro vigente é de 127 V; a execução ACDC a 230 V seria exceção a ele e precisa ser decidida antes. Em 07/10 a 230 V/50 Hz só 15 das 20 classes tinham metadata (faltam 02, 03, 04, 08, 16).

Preencher:

1. Perfis (`norma`, `literatura`, `fronteira`; marcar):
2. Frequências (50 Hz, 60 Hz; marcar):
3. Tensões (127 V; outra? informar):
4. Execução ACDC 230 V:
   - A. Fora desta campanha; diagnóstico ACDC (P-17) só a 127 V. **[recomendado]**
   - B. Entra, como exceção formal ao roteiro de 127 V, com limites de `max_voltage_rms`/`max_peak_v` conferidos antes.
5. Amostras por célula (capturas por classe, perfil e frequência):

Resposta (21/10/2026, responsável): 1. perfis = **todos** (`set perfil todos`); 2–3. condições = **127 V/60 Hz, 127 V/50 Hz, 230 V/50 Hz, 220 V/60 Hz e 33 V/60 Hz**; 4. **A** — diagnóstico ACDC fora a 230 V (só 127 V); 5. **padrão** (1 captura por classe). Consequências na seção "Campanhas por condição (P-26)" de [](bancada_pendencias.md): 220 V/60 Hz e 33 V/60 Hz não têm calibração (P-21).

## P-29 Origem dos logs reais

**Contexto.** Não há transcrição SCPI de bancada em nenhum branch (ver achados). Sem os logs, a tabela SCPI do site continua descrevendo código e manual, sem exemplo "medido". Os logs podem conter dados sensíveis.

- A. O responsável entrega as três `scpi_transcricao.log` (e `sessao.log`) de 07/10 do PC da bancada; trechos curtos são selecionados, revisados e versionados com sessão, condição e SHA. **[recomendado]**
- B. Esperar a campanha P-01 e usar os logs novos (com código v1.15 limpo).
- C. Não publicar exemplos reais; manter a tabela só como código/manual.

Informar: caminho/máquina dos logs, quem revisa dados sensíveis, e se podem ir ao repositório público.

Resposta: **B** (21/10/2026, responsável): os dados do PC antigo não podem ser copiados; os exemplos reais virão das `scpi_transcricao.log` das sessões novas da campanha v1.15 (Inspiron 15), revisados antes de publicar.

## P-30 Definição de "piloto" e reconciliação 99 × 63

**Contexto.** O texto do projeto diz 63 capturas de 07/10 como piloto (`AGENTS.md:125`, `CHANGELOG/v1.15.md:9`), mas as análises leem 99 (36+36+27) e 70+28+1 comparações em `docs/tres_versoes.md`. As sessões de 07/10 têm `versao_codigo = 994e170-dirty`. Não há registro por sessão versionado; ver achados.

- A. "Piloto" = todas as 99 capturas de 07/10 (código anterior à v1.15, árvore suja); o 63 é retificado como erro de contagem, sem apagar o histórico. **[recomendado, se a contagem por sessão confirmar 36+36+27]**
- B. "Piloto" = um subconjunto de 63 (critério a informar: por exemplo classes, perfil, condição); o restante das 99 tem outro estatuto.
- C. Decidir só depois de receber as pastas `resultados/sessao_2026-10-07_*`.

Informar: critério de inclusão, se B; e entrega dos metadados das três sessões de 07/10.

Resposta (21/10/2026): os dados de 07/10 não podem ser recuperados. **Decisão D, confirmada pelo responsável:** registrar 63 e 99 como contagens históricas não verificáveis, sem apagar o histórico nem usá-las como resultado, como na P-27.

## P-31 Métrica oficial de correlação do distúrbio

**Contexto.** Duas métricas diagnósticas já são publicadas em `docs/evidencias/2026-10-16/modelo_programado.json`: correlação do distúrbio contra o nominal e contra a fundamental ajustada. Ex.: classe 06, 50 Hz, perfil norma: 0,98756 (nominal) e 0,98742 (fundamental ajustada). Nenhum limiar ou aceite automático é aplicado (ver [](correlacao_disturbio.md)). A faixa histórica 0,95–1,00 vinha de `validacao_gerador_v1.14.md`, ausente, e não é usada.

- A. Publicar as duas, sem eleger oficial, até haver sessões físicas novas. **[recomendado]**
- B. Eleger a nominal como oficial.
- C. Eleger a fundamental ajustada como oficial.

Se B ou C: informar se haverá limiar de aceite e a fonte dele (não usar a faixa de `validacao_gerador_v1.14.md`).

Resposta:

## O que fecha após as respostas (sem bancada)

- P-09: fecha com A ou C (registrar como limitação aceita).
- P-20: material de publicação pode ser montado após as respostas 1–5 e a decisão da tag; a tag e o Zenodo dependem do que for escolhido.
- P-26: fecha a configuração prévia assim que preenchida; a execução depende de bancada.
- P-29 e P-30: só avançam com a entrega dos logs e dos metadados de 07/10 (ou com a escolha C de P-30 e A de P-29 como encaminhamento).
- P-18, P-23, P-31: a decisão fica registrada, mas o fechamento completo exige bancada ou sessões novas.
