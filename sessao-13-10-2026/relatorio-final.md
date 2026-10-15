# Relatório final da rodada de 13 a 15/10/2026

Branch com o código: `claude/specs-v1-15-review-3w2bgl` (último merge `ca64d09`).
Branch com os relatórios: `arquivo/analises` (pasta `sessao-13-10-2026/`).

## 1. Resumo em três frases

Foram executadas 17 tarefas (specs 10 a 26) e todas estão no branch acima. A suíte de testes offline passa inteira no Linux: 497 testes, com 2 pulados que só rodam no Windows. Nada foi testado na bancada: tudo o que depende da fonte e do osciloscópio está marcado aqui como "a confirmar na bancada".

Como ler este relatório: cada assunto traz quatro partes curtas, sempre na mesma ordem. **O problema** diz o que estava errado e por que importa. **O que foi feito** diz o que mudou no código. **O que ainda falta** diz o que só a bancada ou o tempo resolvem. **Sua decisão** só aparece quando há algo para você escolher.

---

## 2. Segurança e fidelidade do que a fonte emite

### 2.1 Pico previsto abaixo do real em ciclos com degrau (spec 11)

**O problema.** Nas classes por TRACE, cada ciclo de 1/60 s vira uma forma de 1024 pontos mais uma tensão eficaz (`LIST:VOLTage`). O código calculava essa tensão incluindo a média do ciclo, mas mandava a forma sem a média. A fonte remove a média e escala a forma para a tensão pedida. Num ciclo em que o afundamento começa no meio, a média não é zero, então a fonte saía com amplitude maior que a do modelo.
- Efeito no dado: nas classes 10, 11, 12 e 16 a forma emitida diferia do modelo em até 0,43 pu nas capturas de 07/10.
- Efeito de segurança: a conta do pico previsto, que decide se uma captura pode rodar sem passar de 425 V, ignorava esse aumento e podia ficar até 38 % abaixo do pico real. Quem segurava era só a medida de pico feita depois da captura.

**O que foi feito.** A tensão de cada ciclo passou a ser calculada sem a média, e o pico previsto passou a ser calculado sobre a forma realmente enviada. Um teste garante que o pico previsto nunca fica abaixo do emitido. Também foi corrigido um erro pequeno: os 2 últimos pontos de cada ciclo repetiam o último valor em vez de fechar o ciclo.

**O que ainda falta.**
- Mesmo com a correção, a fonte continua removendo a média de cada ciclo; isso é limite físico do modo TRACE. Por isso a forma emitida ainda difere do modelo em 0,24–0,33 pu nos ciclos onde o evento começa ou termina, nas classes 10, 11, 12 e 16.
- Na primeira sessão, conferir o pico medido (VMAX/VMIN) dessas quatro classes.

**Sua decisão** (sem pressa). Recuperar a média de cada ciclo só seria possível no modo ACDC, com um deslocamento contínuo diferente por passo da lista. Esse modo tem o déficit de 5–6 % da classe 19, ainda não explicado. Vale investigar depois da bancada?

### 2.2 Classes 07 e 17 reprovadas pela conferência da crista (specs 20 e 26)

**O problema.** Depois de cada captura o código confere se o medido bate com o esperado. Um dos critérios é o fator de crista (pico dividido pelo valor eficaz) de um ciclo típico, com 10 % de tolerância.
- Desde 12/10 a 07 tem entalhes (quedas de 0,1 ms até zero) em todos os ciclos, como a norma descreve; antes eram só 4 ciclos.
- A fonte não faz o entalhe perfeito: na volta, ela oscila como uma mola. Em 07/10 o entalhe saiu como um tranco de até 0,36 pu.
- Esse tranco vira o pico do ciclo típico medido. Na simulação, a crista medida ficou 31–59 % acima da esperada, e a captura seria marcada inválida sem nenhum erro de geração.

**O que foi feito.** Seguindo a sua orientação, a conferência da crista agora usa a calibração de extremos (`calibracao_extremos.json`), que já mede o quanto a fonte passa do pico em cada classe e condição. O esperado deixou de ser só a crista ideal: o critério aceita qualquer valor entre o ideal menos 10 % e o ideal × fator calibrado mais 10 %. Isso vale para todas as classes; nas que não têm sobressinal o fator é ~1 e nada muda.

**O que ainda falta.**
- Os fatores atuais a 127 V/60 Hz (07: 1,186; 17: 1,031) foram medidos quando havia entalhe em só 4 ciclos. A simulação diz que seriam precisos ~1,34–1,42. A 50 Hz os fatores atuais já quase cobrem.
- Na bancada, a 60 Hz, a primeira rodada da 07 e da 17 deve sair marcada como inválida. Rodar com `set recalibracao on`: no fim do run o fator sobe (nunca desce) e o run seguinte passa. Está no roteiro.
- Efeito colateral: numa condição sem calibração (220 V, por exemplo), o fator padrão é o maior de todos (1,475), o que deixa a conferência da crista bem mais folgada nessa condição.

### 2.3 Programação de TRACE acima do limite só gera aviso (achado da spec 15)

**O problema.** A função que grava a TRACE na fonte só avisa quando o pico calculado passa de `max_peak_v`; não recusa. Quem impede a captura é a pré-validação de pico feita antes, no `mestre.py`. O script de diagnóstico novo (marcadores) faz a própria recusa.

**Sua decisão.** Fazer a função recusar também, o que deixaria a validação mais forte, nunca mais fraca? Recomendo que sim.

---

## 3. A cópia do evento em 100 ms (classes 08 e 09)

**O problema.** Nas capturas de 07/10 o início do evento aparece repetido ou deslocado, sempre em 100 ms da janela:
- 08 a 50 Hz: o impulso programado em 80 ms saiu em 100 ms (3 de 3 capturas).
- 09 a 50 Hz: a oscilação que começa em 80 ms some ali e aparece em 100 ms.
- 09 a 60 Hz: aparece em 80 ms e uma cópia menor sai em 100 ms.

Como a cópia cai sempre no mesmo instante nas duas frequências, a causa parece ligada ao tempo ou à troca de passos da lista da fonte, não a um ponto da TRACE. Isso estraga o dado da 09, não só a métrica.

**O que foi feito.**
- `scripts/diag_ciclos_trace.py` (offline): pega uma sessão gravada e diz, ciclo a ciclo, qual ciclo programado explica cada ciclo medido e a partir de quando há troca. Roda nas sessões de 07/10, no PC da bancada.
- `scripts/diag_marcadores_trace.py` (bancada, pede `ENERGIZAR-MARCADORES`): programa uma captura em que cada ciclo tem uma marca diferente, para ver qual forma saiu em cada ciclo. Tem variantes com o evento na fronteira e no meio do ciclo, para separar as hipóteses.
- `logica/modelo_lista_fonte.py`: compara as hipóteses de mecanismo com a medida e diz qual explica melhor.
- Com o início sorteado, 100 ms cai dentro do evento da 09 em só 17–18 % das capturas, então nem toda captura nova será afetada.

**O que ainda falta.** Rodar na bancada; só isso decide o mecanismo. Recomendação para a 09: rodar logo depois da 08, com 6 a 9 capturas, e aceitar sem ressalva só as capturas em que o script offline não acusa ciclo trocado e o resíduo perto de 100 ms fica abaixo de ~0,05 pu.

---

## 4. Leitura do que ficou gravado na fonte (spec 16)

**O problema.** Nunca se conferiu se o que a fonte grava na memória é o que o código enviou.

**O que foi feito.** Um modo novo, `set diagnostico retrieve`, desligado por padrão. Depois de cada captura TRACE ele lê de volta as formas gravadas (`TRACe:DATA?`) e salva enviado × lido em `<sessao>/diagnostico_trace/`, fora do `.npz` da captura. Cuidado de segurança: a leitura só acontece com a captura já terminada e pelo menos 2 s depois da última gravação, porque em 2026 já se viu a fonte travar quando consultada logo após gravar.

**O que ainda falta.** O manual se contradiz: uma página diz que esse comando não aceita consulta e outra descreve a resposta. Só a bancada diz se funciona. O roteiro manda testar na primeira captura da 08, com o painel da fonte à vista. Se não funcionar, a captura segue normalmente e o erro fica anotado no metadata.

---

## 5. Formato dos arquivos e perfis (specs 17 e 25)

**O problema.** Cada captura virava vários arquivos: o `.npz` da captura, as três versões (modelo, programada, medida) e os níveis de ruído. Com três perfis (norma, literatura, fronteira), a pasta explodia.

**O que foi feito.**
- Um `.npz` comprimido por classe, sem perda, com as três versões de cada perfil dentro. Os níveis de ruído continuam em arquivos separados, como você pediu.
- `set perfil todos`: um `run` percorre os três perfis na mesma sessão.
- As classes que não mudam com o perfil (01, 04, 07, 08, 09, 17, 18, 19) são capturadas uma vez só, sob `literatura`. A lista é calculada a partir das tabelas de `perfis.py`, e um teste confirma contra o `gerar()`. O metadata dos três perfis aponta para a mesma captura, com o mesmo arquivo, a mesma posição e o mesmo hash. O HTML desenha a figura uma vez, marcada "(= norma, fronteira)".
- Um leitor único, `logica/sessao_io.py`, lê o formato novo e o antigo; todos os scripts passaram a usá-lo.
- Com `todos`, o `run all` planeja 1116 gravações de TRACE a 60 Hz (seriam 1404 sem a deduplicação; 468 com um perfil só).

**O que ainda falta.**
- Quebra de formato: quem lia os `.npz` individuais das sessões novas precisa usar `sessao_io`. As sessões antigas continuam legíveis. O aviso está no CHANGELOG.
- Se o processo morrer no meio de uma classe, as capturas ficam numa pasta `parcial/` e são recuperadas por `sessao_io.recuperar_parcial`, chamada à mão.
- O tamanho do arquivo com dado real de bancada ainda não foi medido.

**Sua decisão.** Chamar `recuperar_parcial` automaticamente no início de cada `run`?

---

## 6. CLI e preflight (specs 12, 13 e 14)

**O que foi feito.**
- **Preflight único.** O `preflight.py` foi apagado e só existe o `preflight_new.py`. O teste `lowvoltage` sempre rodou na tensão digitada no início (127 V), apesar do rótulo "5 V". Agora o aviso mostra a tensão real e a confirmação é `ENERGIZAR-TESTE`. Os comandos `comm`, `trigger`, `lowvoltage` e `native` gravam log em `logs\preflight_new-*.log`.
- **`run` com lista**, por exemplo `run 01-07,09-20`, com a confirmação `EXECUTAR-CLASSES-01-07,09-20`. Isso permite dividir a bateria em partes abaixo da trava da fonte, que travou perto da 280.ª gravação de TRACE numa conexão; cada `run` abre conexão nova.
- **Rastreabilidade.** O metadata grava a semente do ruído de cada nível e a fórmula. O aviso de "árvore suja" passou a contar arquivos novos nas pastas de código e é recalculado a cada `run`. O `sessao.json` grava o perfil.

**Sua decisão** (detalhes).
- `run 01 02` (com espaço em vez de vírgula) roda só a 01, sem avisar. Recusar?
- A variável `BATERIA_EXCLUIR` não vale para listas, porque a lista é um pedido explícito. Concorda?

---

## 7. Pendências antigas da pasta `pendente/`

### 7.1 Classe 05 com a senoide clipada (spec 18)
Já estava implementado desde 12/10: até 20 % de distorção, o modelo é a senoide clipada que a fonte gera. Conferido contra o diagnóstico: distorção, valor eficaz, fase e teto batem. No nível de 30 % (gerado por TRACE), modelo e forma programada são idênticos (correlação 1,00000), então nada mudou.

### 7.2 Métrica com a fundamental ajustada (spec 18)
A correlação do distúrbio subtrai uma senoide fixa de 1 pu. Se a fonte entrega a fundamental 1 % maior, o resíduo carrega esse erro e a correlação cai até 0,05 nas classes de distúrbio pequeno (09). Foi acrescentada uma segunda métrica, que ajusta a fundamental de cada sinal antes de comparar. Ela aparece ao lado da métrica antiga no `analisar_sessao.py` e no HTML.

### 7.3 Classe 06 (flicker) perde correlação já na programação (spec 18)
**O problema.** Toda a perda vem da média de cada ciclo, que a fonte remove (o mesmo mecanismo do item 2.1). Para flicker de 20–25 Hz a correlação do distúrbio fica em 0,91–0,94.

**Sua decisão.** Há duas saídas:
- comparar a 06 com a forma programada, sem mudar o dataset;
- redefinir o flicker com média nula por ciclo, o que muda o `gerar()` e precisa da sua autorização.

### 7.4 Compostas sorteadas conferidas contra a proposta (spec 19)
**O problema.** O texto da proposta só pede, além da oscilação e do flicker, o sag e a THD da classe 10. A implementação de 12/10 foi além e sorteia:
- sag nas 11 e 12 e swell nas 13 e 14;
- THD nas 13, 15 e 16;
- faixas próprias no perfil norma;
- valores alternados no perfil fronteira.

Não há divergência nem defeito: o que a proposta pede está cumprido. As extensões estão documentadas como decisão de projeto em `docs/perfis.md`. A 2400 Hz a oscilação sai na forma programada com 2,4 % menos de amplitude.

**Sua decisão.** Manter as extensões ou reverter? Reverter muda o dataset.

### 7.5 ACDC, 18 e sorteio (spec 20)
- Classe 19 (ACDC): o script `diag_acdc_amplitude.py` continua pronto e nunca rodou; está no roteiro.
- Classe 18 (deriva 47→53 Hz a 50 Hz): a continuidade da fase na troca de frequência não foi medida.
- Classes 02–04: a largura real do pulso e o desvio do pré-trigger nunca foram medidos.

Para isso foi criado `scripts/verificar_sessao_bancada.py`, que mede os três numa sessão gravada. Os limiares (10 graus, 2 ms, 2 amostras) são propostas, sem dado de bancada.

---

## 8. Testes e documentação (specs 10, 21 e 22)

- **Fixtures portáveis (21).** Os testes que garantem que o `gerar()` não mudou comparavam um hash exato dos números. Esse hash difere entre Windows e Linux no último bit do seno (2·10⁻¹⁶). Foi criada uma comparação por tolerância (10⁻⁹), que pega qualquer mudança real; o hash exato continua, rodando só no Windows. **Falta:** rodar `tests.test_offline` uma vez no Windows antes de coletar.
- **Análises fora de `docs/` (10).** Os relatórios datados, os planos antigos e a lista de tarefas foram para o branch `arquivo/analises`. Os scripts temporários de diagnóstico foram apagados. `docs/` ficou só com a documentação do projeto e os manuais.
- **Documentação autocontida (22).**
  - Nenhuma menção a professor, dono ou `.tex` fora do `AGENTS.md`, onde "dono" ficou porque é a regra de autorização dos agentes, e dos CHANGELOG antigos, que não se reescrevem.
  - Seção única sobre HTML e recalibração em `docs/operacao.md` §9.
  - Autorizações que faltavam registradas no `AGENTS.md`.

**Sua decisão** (detalhes da 22, todos pequenos).
- Uma variável local chamada `dono` em `mestre.py` foi renomeada para `pai`, só para a busca ficar limpa.
- O texto de um campo de `calibracao_extremos.json` mudou, e por isso o hash do arquivo muda; as sessões antigas guardam o hash antigo, que continua certo para elas.
- O texto ainda cita "spec NN" como identificador de tarefa. Aceitar ou tirar?
- O HTML do fim do run mostra só as 3 primeiras capturas de cada classe e perfil. Mostrar todas, mesmo deixando o arquivo maior?

---

## 9. Lista única de decisões

| # | Decisão | Onde está explicado |
|---|---|---|
| 1 | Investigar a média por ciclo via ACDC depois da bancada? | 2.1 |
| 2 | A gravação de TRACE recusar pico acima do limite (hoje só avisa)? | 2.3 |
| 3 | `recuperar_parcial` automático no início do run? | 5 |
| 4 | `run 01 02` recusar; `BATERIA_EXCLUIR` fora das listas | 6 |
| 5 | Classe 06: comparar com a programada ou mudar o `gerar()` | 7.3 |
| 6 | Compostas: manter ou reverter as extensões | 7.4 |
| 7 | Detalhes da 22 e HTML com todas as capturas | 8 |
| 8 | No dia da bancada: um perfil ou `todos`, frequência da campanha, ACDC a 230 V | `ROTEIRO_BANCADA.md` |

## 10. Como a rodada correu

As tarefas rodaram em paralelo, até 3 de cada vez, cada uma numa cópia separada do repositório. Eu conferia e juntava cada uma no branch, o que gerou conflitos de junção (resolvidos sem perda). Em 13/10 a rodada foi pausada a seu pedido e retomada em 15/10 de onde parou. Os relatórios individuais de cada tarefa estão na pasta `specs/2026-10-13/relatorios-individuais/`.
