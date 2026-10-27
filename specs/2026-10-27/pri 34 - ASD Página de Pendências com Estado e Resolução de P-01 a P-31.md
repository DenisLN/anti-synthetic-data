#spec #pri 34

# ASD: Página de Pendências com Estado e Resolução de P-01 a P-31

## Contexto

O dono pediu: "listar lá [no Read the Docs] todas as pendências e como foram resolvidas. Já tem uma página de pendências, é só mudar lá." A página é `docs/projeto/pendencias.md`, que hoje é o "inventário histórico de 16/10/2026" (31 itens abertos, com opções e "o que fecha"). Depois da spec do rastreador, o estado vem de um arquivo único renderizado no build.

O relatório de achados de 2026-10-27 (`specs/2026-10-27/findings-pendencias-v1-15-detalhado.md`, branch `arquivo/analises`) conferiu cada pendência contra as evidências do fork e mostrou que o rastreador de 22/10 está errado em vários pontos. Resumo do que muda (detalhe e evidência por P-NN na seção 3 do relatório):

- **P-16** (suíte no PC da bancada) e **P-25** (decisões menores) estão como ✅ mas não estão concluídas: a suíte rodou em `6885e7c`, não no HEAD; `spec 26` continua em `docs/limites_e_calibracao.md`, e o dono não respondeu item a item.
- **P-02** e **P-08** estão como 🔧→🏭 mas foram **reprovadas** na bancada em 22/10; **P-19** teve evidência **insuficiente** (`TRACe:DATA?` devolveu 10 valores em vez de 1024).
- **P-09**: a condição do plano do dono (21/10) para fechar como limitação aceita foi cumprida (`SOURce:LIST:VOLTage:OFFSet` → `-113`), mas o rastreador ainda pede braços A e B. Conflito a decidir pelo dono.
- **P-03, P-04, P-10, P-11, P-12, P-13, P-14, P-15, P-27**: resolvidas ou tratadas no fork, mas sem decisão do dono registrada ("autorização do usuário nesta sessão" não é decisão do responsável).
- **P-21**: a classe 08 não tem fator de extremo nem a 50 nem a 60 Hz.
- Decisões do dono registradas em `docs/decisoes_pendentes.md` (21/10): P-09, P-21 (pelo operador, pendente do dono), P-26, P-29, P-30. Em branco: P-18, P-20, P-23, P-31.

A página deve dizer, por pendência, o que foi pedido, o estado verdadeiro, **como foi resolvida** (ou o que foi feito até agora, com commit e evidência) e o que falta, sem decidir pelo dono.

## Entradas

- Arquivo de estado único e a página gerada, criados pela spec "ASD: Rastreador de Pendências Integrado ao Read the Docs"
- `docs/projeto/pendencias.md`, `docs/projeto/estado-validacao.md`, `docs/execucao_pendencias.md`, `docs/decisoes_pendentes.md`, `docs/bancada_pendencias.md`
- Evidências: `docs/evidencias/2026-10-16/`, `2026-10-17/`, `2026-10-21/`, `2026-10-22/` (`fechamento.json`, `LEIA-ME.md`, `pc_bancada.json`, `diag_list_offset.json`, `visita_estado.json`)
- Relatório de achados (seções 1, 3, 4.5, 4.8 e 7), branch `arquivo/analises`
- `git log --oneline fa82f49..main` para os commits de cada resolução
- Depende de: ASD: Rastreador de Pendências Integrado ao Read the Docs

## Missão

1. Revisar o estado de cada uma das 31 pendências no arquivo único conforme as evidências (usar o relatório de achados como ponto de partida e conferir cada afirmação dele nos arquivos de `docs/evidencias/` e no código), incluindo o estado "reprovada na bancada" para P-02 e P-08, "insuficiente" para P-19, e tirando P-16 e P-25 de concluída.
2. Escrever, para cada P-NN, o bloco "como foi resolvida / o que foi feito": mudança de código com commit e `arquivo:linha`, sessão ou evidência, resultado medido; e "o que falta", separando trabalho de bancada, de código e decisão do dono.
3. Marcar explicitamente, em cada pendência, se a escolha feita no fork foi **confirmada pelo dono** (citar onde) ou está **tomada no fork, aguardando confirmação** (P-03, P-04, P-10 a P-15, P-25, P-27 e as demais em que se aplicar), e registrar o conflito da P-09 como pergunta ao dono.
4. Reescrever `docs/projeto/pendencias.md` como página viva (título sem "inventário histórico"; o inventário de 16/10 vira seção "Pedido original" por P-NN ou vai para uma página histórica ligada a ela), e fazer `docs/projeto/estado-validacao.md` e `docs/index.md` apontarem para ela com o placar correto.
5. Gerar no relatório a lista consolidada de perguntas ao dono (uma linha por decisão pendente, com as opções que o formulário já oferece) e registrar a revisão em `CHANGELOG/v1.15.md`.

## Limites

- Não decidir nada pelo dono: não fechar pendência que dependa de decisão dele, não escolher opção de formulário, não criar licença, autoria, citação ou DOI (P-20).
- Simulação não é medição: nenhuma pendência física passa a concluída sem evidência de bancada.
- Não alterar código, `docs/evidencias/`, `CHANGELOG` fechados, nem `docs/classes/` (outra spec).
- Não rodar nada que energize. Rodar a suíte no PC da bancada (P-16) é do dono; aqui só registrar o que falta.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.
- Se algum limite impedir ou restringir o resultado, registrar no relatório em "Limitações de escopo", sem ultrapassá-lo.

## Entregável

- Relatório `.md` no caminho que o despacho indicar, com: um bloco por item da Missão (copiar o texto do item, dizer CUMPRIDO, PARCIAL, NÃO CUMPRIDO ou IMPEDIDO, e explicar nos dois casos, com evidência); Critério de Parada atendido ou não; pendências que exigem o usuário; limitações de escopo; se a missão resolve o contexto; achados.
- Tabela no relatório: P-NN × estado antes (rastreador de 22/10) × estado depois × evidência que justifica a mudança.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- Onde o relatório de achados não puder ser confirmado nos arquivos do repositório (por exemplo, sessões que só existem no PC da bancada), marcar NÃO VERIFICADO com o motivo.
- Verificação: `sphinx-build -W -b html docs docs/_build/html` e o teste de validade do arquivo de estado da spec anterior.

## Critério de Parada

As 31 pendências aparecem na página gerada, cada uma com estado, "como foi resolvida / o que foi feito", "o que falta" e situação da decisão do dono; P-02 e P-08 aparecem como reprovadas, P-16 e P-25 não aparecem como concluídas; o placar da página bate com a contagem do arquivo de estado; build `-W` e teste do arquivo de estado passam.
