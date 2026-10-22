# Execução das pendências P-01 a P-31

Execução atualizada em 17/10/2026 (horário de Brasília). Baseline de código: `fa82f49600543456adf78e22485ab6de5dd032b9`, v1.15 em andamento. Esta página é o registro de trabalho atual; os changelogs fechados e relatos anteriores permanecem preservados.

Fonte do inventário: [pendências publicadas](https://anti-synthetic-data.readthedocs.io/pt/docs-site-readthedocs/projeto/pendencias.html). A autorização do usuário nesta sessão determina implementar plenamente as pendências como atualização das escolhas anteriores. Não se interpreta um contrato antigo de teste como impedimento à atualização: P-14 passa a aplicar exclusões às listas, e P-15 passa a limitar o HTML também na bancada. Resultados de testes antigos devem ser atualizados para o novo contrato e acompanhados de regressões independentes.

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

| Item | Direção vigente |
|---|---|
| P-04 | Concluída — software | Recusa offline de parâmetros inválidos e excessos de RMS/pico, inclusive senoide imediata com offset e cache. Faixa de frequência do driver aplicada antes de I/O. Regressões e integração aprovadas. |
| P-09 | Aceitar e explicitar provisoriamente a perda da média por ciclo; nenhuma compensação física sem dados. Quantificar a diferença entre modelo e programada. |
| P-11 | Concluída — decisão e metadata | Mantidas as extensões 10–16; classe 15 registra envelopes e THD central/mínima/máxima da redução, com testes analíticos. gerar()/fixtures preservados; validação física das classes continua em P-01/P-08. |
| P-12 | Concluída — software e decisão | Classe 06 compara medida com a programação reconstruída, sem usar a medida como referência. Modelo ideal preservado; efeito nas 11/15 quantificado offline. Fidelidade física continua pendente em P-01. |
| P-13 | Concluída — software | Recuperação com lock exclusivo POSIX/Windows; escritor ativo ignorado; morte abrupta preserva ambos os IDs. Metadata/corrente/SNR/aliases preservados, pastas exclusivas e escrita pós-close recusada. Integração aprovada. |
| P-14 | Concluída — software | Parsing estrito e exclusões em listas; seleção efetiva mostrada antes de confirmação. Exclusão total ou sintaxe ambígua não executa nenhuma classe. Testes aprovados. |
| P-15 | Concluída — software | Limite padrão de três capturas por classe/perfil no HTML físico/simulado; seleções explícitas preservadas e leitura dos dados originais integral. Testes aprovados. |
| P-18 | SINE integrado experimentalmente no checkout, desligado por padrão (`AMETEK_PASSO_FINAL_SIN=0`, `passo_final_sin=False`); validação física permanece pendente. |
| P-20 | Preparar material de publicação sem inventar licença, autoria ou DOI. O fork não concede direitos de relicenciamento. |
| P-23 | Orçamento operacional de 216 gravações TRACe por conexão aplicado no CLI, entrada principal e ORM; inclui tentativas de envio incertas e comandos diretos. Esgotamento aborta a bateria sem retry. A causa física da trava continua aberta. |

## Responsabilidade e sequência

O coordenador integra código, registra baseline e revisa critérios de aceite. Os subagentes trabalham em escopos separados: ORM/CLI; integridade e relatórios; análise de sinais; documentação e rastreabilidade; revisão independente. Escritores de módulos compartilhados combinam alterações com o coordenador. O operador presencial mantém as confirmações digitadas e a observação de OUTPUT OFF, fiação e probe.

1. Preparar checkout e ambiente identificados; registrar `git status`, versões e suite descoberta.
2. Implementar P-04/P-13/P-14/P-15 com regressões offline; corrigir P-23/P-24 e documentação do contrato.
3. Executar análises P-09/P-11/P-12/P-22/P-28/P-31; integrar SINE separadamente em P-18, com revisão.
4. Preparar campanha com diagnósticos antes da coleta conforme `ROTEIRO_BANCADA.md`. P-26 fixa as condições antes de energizar.
5. Incorporar sessões reais e fontes faltantes; revisar cada ID e publicar somente o que estiver comprovado.

## Matriz de execução

| ID | Estado nesta revisão | Próxima entrega e critério de aceite |
|---|---|---|
| P-01 | Preparada / aguarda bancada | Executar campanha v1.15 por classe/perfil/condição; registrar sessões e cobertura, sem converter simulação em validação física. |
| P-02 | Reprovada em 2026-10-22 / aguarda bancada | Marcadores 30/30 sem espúrios e recapturas 08/09 presentes; posição da 08 a 127 V/60 Hz desvia −16 amostras (limite 10); `evidencias/2026-10-22/fechamento.json`. Diagnóstico da cópia/evento em 100 ms com marcadores, TRACe recuperada e capturas 08/09; distinguir hipóteses antes da correção. |
| P-03 | Concluída — bancada 2026-10-22 | 3/3 capturas: desvio 2 amostras, pico 339 V, sobressinal 0,295 pu (`evidencias/2026-10-22/fechamento.json`). Critério: recapturar 08 a 127 V/50 Hz, evento 90 ms; conferir posição ≤10 amostras, teto 374,2 V e sobressinal conforme o roteiro. Excesso exige investigação, não relaxamento do teto. |
| P-04 | Concluída — software | Recusa offline de parâmetros inválidos e excessos de RMS/pico, inclusive senoide imediata com offset e cache. Faixa de frequência do driver aplicada antes de I/O. Regressões e integração aprovadas. |
| P-05 | Evidência suficiente, revisão humana pendente | 2026-10-22: largura ≤ 1,1 ms; pre-trigger determinístico até ±6 amostras (aviso). Medir fase, início/duração e pretrigger nas nativas 01–04; reportar desvios e manter o limiar proposto distinto de critério físico validado. |
| P-06 | Parcial — bug de estado corrigido | Classe 18 após STEP/PULSe não herda readbacks antigos; divergências continuam recusadas antes de INIT. Falta medir continuidade de fase e restauração na fonte real. |
| P-07 | Evidência suficiente, revisão humana pendente | 2026-10-22: 07 → 1,615, 17 → 1,575 (`022bb5c`, `a22fba9`). Recalibrar 07/17 com medidas reais, revisar diff e identificar calibração; validar em nova coleta, sem aprovação retroativa. |
| P-08 | Reprovada em 2026-10-22 / aguarda bancada | Extremos até 1,30× o previsto, abaixo do teto; recalibrado em `13b9bdb`. Conferir pico/vale 10/11/12/16 contra previsão por condição; investigar violações do teto previsto. |
| P-09 | Parcial — sem suporte a offset por passo | 2026-10-22: `SOURce:LIST:VOLTage:OFFSet` não aceito (`-113`); braço C fora; faltam braços A e B. Perda de média por ciclo quantificada em `modelo_programado.json`; aceita provisoriamente como limitação. Compensação física depende de P-17 e dados reais. |
| P-10 | Concluída — bancada 2026-10-22 | Níveis 2–30 % com validação ok e rota esperada (`evidencias/2026-10-22/fechamento.json`). Medir RMS/THD da 05: CSIN 10/15/20%, norma 2% e TRACe 30%, identificando rota, nível e configuração. |
| P-11 | Concluída — decisão e metadata | Mantidas as extensões 10–16; classe 15 registra envelopes e THD central/mínima/máxima da redução, com testes analíticos. gerar()/fixtures preservados; validação física das classes continua em P-01/P-08. |
| P-12 | Concluída — software e decisão | Classe 06 compara medida com a programação reconstruída, sem usar a medida como referência. Modelo ideal preservado; efeito nas 11/15 quantificado offline. Fidelidade física continua pendente em P-01. |
| P-13 | Concluída — software | Recuperação com lock exclusivo POSIX/Windows; escritor ativo ignorado; morte abrupta preserva ambos os IDs. Metadata/corrente/SNR/aliases preservados, pastas exclusivas e escrita pós-close recusada. Integração aprovada. |
| P-14 | Concluída — software | Parsing estrito e exclusões em listas; seleção efetiva mostrada antes de confirmação. Exclusão total ou sintaxe ambígua não executa nenhuma classe. Testes aprovados. |
| P-15 | Concluída — software | Limite padrão de três capturas por classe/perfil no HTML físico/simulado; seleções explícitas preservadas e leitura dos dados originais integral. Testes aprovados. |
| P-16 | Concluída — PC da bancada | Inspiron 15 (DESKTOP-FSEESJI), definido como PC da bancada em 21/10/2026: `scripts/validar_pc_bancada.ps1` em `21fb300`, árvore limpa, Python 3.11.9/numpy 2.4.6/PyMeasure 0.16.0/PyVISA 1.14.1, 680 testes, 0 falhas, 0 erros, 0 skips (assinaturas exatas de Windows executadas). Evidência: `evidencias/2026-10-21/pc_bancada.json` e `.log`; `fechar_pendencias.py` P-16 = evidencia_suficiente sem revisão pendente. |
| P-17 | Evidência suficiente, revisão humana pendente | 2026-10-22: AC / ACDC offset 0 / ACDC com offset a 50 e 60 Hz; falta critério do déficit. Caracterizar déficit ACDC por CA e RMS total; não aplicar V/g como correção antes da caracterização. |
| P-18 | Parcial — integrado experimental OFF | SINE integrado com padrão desligado e regressões offline; falta validar aceitação SCPI e a restauração na fonte real. |
| P-19 | Insuficiente em 2026-10-22 / aguarda análise | `TRACe:DATA? TCC00` devolve 10 valores (9 leituras). Verificar `TRACe:DATA?` no firmware real, 1024 valores finitos ou comando explicitamente não suportado; preservar intervalos de segurança. |
| P-20 | Aberta — depende de direitos/publicação | Preparar congelamento, licença e autoria verificadas, citação e Zenodo após validação; não criar licença ou DOI fictícios. |
| P-21 | Preparada / aguarda bancada | Calibrar condições novas antes de coleta científica e registrar origem dos fatores, sem elevar limites para acomodar classes. |
| P-22 | Evidência suficiente, revisão humana pendente | 2026-10-22: benchmark com 14 sessões físicas no DESKTOP-FSEESJI, falta critério de tempo/tamanho. `benchmark_sintetico.json` mede tempo/tamanho/tracemalloc para 3/10/30 capturas e verifica leitura/aliases. Falta medir dados físicos reais e custo no PC/disco da bancada. |
| P-23 | Parcial — proteção implementada | CLI e entrada principal recusam estimativas acima de 216 antes de abrir instrumentos; ORM verifica a captura inteira e conta tentativas cumulativas, inclusive comandos diretos e falhas de envio. Cache confirmado não consome novas gravações. Esgotamento aborta a bateria sem retry. Causa física da trava ainda depende de diagnóstico real. |
| P-24 | Concluída — revisão e build local | Referências atuais por símbolos/25 `pyobject` validados AST; 1136 citações históricas fixadas por permalink SHA; B8 e contagens corrigidos; build Sphinx estrito aprovado e tabelas P-03/decisões verificadas no HTML. Publicação remota do site não é afirmada. |
| P-25 | Concluída — decisão editorial | Removidos identificadores `spec NN` das páginas operacionais atuais; aceitas renomeação local e manutenção do texto `uso_limite_bancada` sem alterar o JSON/hash. Mantidos histórico fechado e termos de governança em AGENTS por decisão explícita. |
| P-26 | Preparada / aguarda operador | Registrar antes da coleta perfil/frequência/tensão e escopo ACDC opcional 230 V; resolver essa exceção ao roteiro de 127 V antes de executá-la. |
| P-27 | Concluída — comparações sem fonte retiradas | Removidas faixas de referência e coluna “bate?” que dependiam do arquivo ausente. Valores históricos permanecem identificados como reportados e não são critérios de aceite; não se fabricou a fonte. |
| P-28 | Evidência suficiente, revisão humana pendente | 2026-10-22: 135 exportações brutas íntegras e reamostragem casada por SHA-256. `set diagnostico bruto on` preserva BYTE/preamble/tempos antes de interpolar, sem nova aquisição, em arquivos independentes com vínculo por hash. Analisador compara RMS/pico/THD/erro temporal/espectro na grade salva, com rastreabilidade de entrada/configuração. Faltam exportações reais e revisão dos resultados físicos; FIR não substitui o interpolador do dataset. |
| P-29 | Bloqueada por logs reais | Transcrições locais das sessões não disponíveis no checkout; obter trechos com sessão/condição/SHA. A tabela SCPI descreve código/manual, não prova medição. |
| P-30 | Concluída — retificação | Sessões de 07/10 irrecuperáveis (decisão de 21/10/2026). As contagens 63 ("piloto") e 99 (36+36+27) ficam como históricas e não verificáveis, com nota de retificação em `AGENTS.md` e `docs/tres_versoes.md`, sem apagar o histórico. Nenhum resultado depende delas. Mesmo critério da P-27: não se fabricou a tabela por sessão. |
| P-31 | Evidência suficiente, revisão humana pendente | 2026-10-22: capturas físicas de 06/10/11/12/15/16 e correlações publicadas; falta a métrica oficial. Relatório modelo/programada publica nominal e fundamental ajustada com limitações; falta comparar novas sessões físicas e justificar a métrica oficial. |

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
.\env\Scripts\python.exe scripts\analisar_modelo_programado.py --saida modelo_programado_novo.json
.\env\Scripts\python.exe scripts\analisar_reamostragem.py --sintetico --saida reamostragem_nova.json
.\env\Scripts\python.exe scripts\benchmark_sessao_io.py --capturas 3 10 30 --saida benchmark_novo.json
```

- `docs/evidencias/2026-10-16/modelo_programado.json`: seis classes, três perfis, 50/60 Hz e três seeds; representação TRACe/LIST comparada ao modelo, perda da média por ciclo e correlações nominal/ajustada. Sem hardware, calibração ou redução de bancada.
- `docs/evidencias/2026-10-16/reamostragem_sintetica.json`: comparação sintética entre interpolação linear e FIR anti-aliasing; não é avaliação do bruto do osciloscópio real.
- `docs/evidencias/2026-10-16/benchmark_sintetico.json`: writer real com dados sintéticos, integridade de leitura e aliases; diretório temporário/cache, sem `fsync`, e `tracemalloc` não equivale a RSS.
- `docs/evidencias/2026-10-16/limites_50hz.md` e `limites_60hz.md`: relatórios offline de limites, não medições.
- `docs/evidencias/2026-10-16/plano_campanhas.json`: planejamento offline por condição; não registra campanha executada.

A documentação de referência importada usa permalinks do snapshot `fa82f49600543456adf78e22485ab6de5dd032b9` para citações históricas de linhas. Os 25 `literalinclude` selecionam objetos por símbolo, verificados por AST contra o checkout atual; não dependem de números de linha. As alterações atuais de contrato estão identificadas nas páginas CLI/ORM/persistência/HTML/SINE, além desta matriz.

### Verificação local do site

`/tmp/asd-exec-venv/bin/sphinx-build -W -n --keep-going -b html docs /tmp/asd-docs-build` concluiu com código 0 e `build succeeded`, após as referências serem auditadas. Configuração Sphinx 9.0.4/MyST 5.1.0/Furo 2025.12.19 conforme `docs/requirements.txt`. Sem supressão geral de avisos; o filtro específico de três links de changelogs fechados já existente no branch do site foi preservado. Artefatos brutos `evidencias/**` são excluídos das páginas Sphinx, sem alterar seu conteúdo.

A inspeção estrutural do HTML confirmou 32 linhas e cinco colunas na tabela geral de pendências (incluindo P-03), 15 linhas e três colunas na tabela de decisões e link para o estado atual no índice. Log local: `/tmp/asd-docs-build.log`. Isso comprova geração e estrutura, não publicação do site remoto ou validade física dos relatos.

## Critério final de encerramento

As 31 pendências devem ter evidência de conclusão. Depois do tratamento delas, será feita a auditoria completa das especificações da AMETEK e a validação das sessões exigidas: 127 V/60 Hz, 127 V/50 Hz, 230 V/50 Hz, 220 V/60 Hz e 33 V/60 Hz. A ordem foi definida pelo usuário; o planejamento offline não representa execução dessas sessões. O verificador `scripts/verificar_prontidao.py` não declara o projeto pronto enquanto faltam evidências e dados físicos. `docs/manifesto_prontidao.json` é um modelo vazio; `docs/estado_prontidao.json` registra os itens de software já concluídos e as lacunas atuais. Use `python scripts/verificar_prontidao.py --manifesto docs/estado_prontidao.json` para verificar o estado registrado; seu código de saída 1 é esperado enquanto houver lacunas.
