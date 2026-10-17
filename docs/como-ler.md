# Como ler esta documentação

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


**Pergunta:** como saber quanto cada afirmação desta documentação pode ser levada a sério? **Resposta:** pelo **selo** colado a ela. Há cinco selos, cada um com uma evidência exigida; uma afirmação sem selo vale como descrição do código, conferida em `arquivo:linha`, e qualquer número leva a condição (tensão e frequência) e a fonte.

## 1. Os cinco selos

| Selo | Quando se usa | Evidência exigida |
|---|---|---|
| {bdg-success}`VERIFICADO NA BANCADA` | o fato foi medido ou observado na bancada física | sessão (por exemplo `sessao_2026-10-07_127V_50Hz`), condição (127 V/50 Hz) e fonte (transcrição, `.npz`, relatório) |
| {bdg-info}`OFFLINE` | conferido sem hardware: leitura de código, simulação ou análise de dados já gravados | `arquivo:linha` (ou símbolo), comando e saída, e a data |
| {bdg-warning}`NÃO VERIFICADO` | afirmação sem evidência disponível ou que depende de bancada | **motivo** obrigatório: o que falta e quem pode fechar |
| {bdg-danger}`PENDENTE` | existe item aberto, com id `P-NN` | o id da pendência ({doc}`projeto/pendencias`) |
| {bdg-secondary}`FORA DA MAIN` | só existe em branch ou em material de arquivo (hoje, `feat/passo-final-sin`) | branch e commit ({doc}`projeto/passo-final-sin`) |

Regras: (1) o selo vale por afirmação, não por página; as páginas de classe e de comando abrem com a linha de selos que as resume; (2) VERIFICADO NA BANCADA vale **só para a condição citada** (127 V/60 Hz, 127 V/50 Hz, 230 V/50 Hz) e para o **código da data**: hoje, tudo é anterior à v1.15 (P-01); (3) um NÃO VERIFICADO sem motivo falha a revisão; (4) quando uma pendência fecha, o selo sai e o id passa para "Resolvidas" em {doc}`projeto/pendencias`; os ids não são reaproveitados; (5) OFFLINE nunca vira VERIFICADO NA BANCADA sem sessão nova.

## 2. Avisos padronizados

:::{note} Nota de verificação
Conferência independente, resultado de teste ou medida que apoia ou limita o texto, em voz impessoal: "Conferido offline: ...".
:::

:::{warning} Decisão em aberto
Escolha que só o responsável pelo projeto faz; sempre com a pergunta, as opções e o id `P-NN`.
:::

:::{important} Pendência P-NN
Item aberto, com o que o fecha e a prioridade.
:::

:::{caution} Limitação
Restrição física ou de projeto que o leitor precisa saber antes de usar o dado.
:::

:::{danger} Segurança
Só para os limites inegociáveis e para ações que energizam.
:::

## 3. Convenções de escrita

1. **Cada assunto abre com a pergunta e a resposta direta em negrito**; o contexto e o histórico entram dentro da explicação (o que se pensava, o que a medida mostrou, qual versão corrigiu e por quê), construindo em cima do que já foi definido.
2. **Números sempre com condição e fonte.** As tabelas comparam as três condições em colunas: 127 V/60 Hz, 127 V/50 Hz e 230 V/50 Hz.
3. **Todo termo é definido na primeira ocorrência**, com link para a página que o aprofunda ({doc}`glossario`). Duas medidas estão em *pu*: a tensão dividida pelo pico nominal `√2 · V_base`.
4. **Todo comando SCPI é um link** para a sua entrada em {doc}`scpi` (papel `{scpi}` para a fonte e `{scpik}` para o osciloscópio), com um exemplo da transcrição de bancada quando existe. Onde não há transcrição (todo o Keysight), o exemplo é "derivado do código, transcrição NÃO VERIFICADA".
5. **Fato sobre o código cita `arquivo:linha`**, conferido com o código na data; listagens vêm do código real, e fórmulas e diagramas ficam em notação matemática e em Mermaid. Onde o `CHANGELOG` diverge do código, vale o código e a divergência fica registrada na página.
6. **Quirks** são citadas pelos códigos de {doc}`quirks`: `A1` a `A25` (fonte AMETEK), `K1` a `K10` (osciloscópio) e `B1` a `B9` (bancada e PC).
7. **Pendências** são `P-01` a `P-31` ({doc}`projeto/pendencias`).
8. **Versão e commit** de cada página: o rodapé traz o commit do build; o texto da data de leitura diz de qual commit (hoje, `main` em `fa82f49`, v1.15 em andamento, sem tag).

## 4. Lista de verificação para revisar uma página

1. Abre com pergunta e resposta em negrito?
2. Todo número tem condição e fonte?
3. Todo comando SCPI é um link?
4. Todo termo novo é definido?
5. Todo NÃO VERIFICADO tem motivo?
6. Nenhuma citação por número de linha escrito à mão onde um símbolo serviria?
7. Nenhum nome de pessoa nem referência a texto de origem?
8. Há link para a pendência `P-NN`?
9. O build com `-W` passa ({doc}`contribuir_docs`)?
