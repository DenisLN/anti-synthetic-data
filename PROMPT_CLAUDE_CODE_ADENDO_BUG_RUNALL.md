# Adendo — bug novo: "run all" falha em 02/SAG, classe isolada não falha

Reproduzido: `bancada> run 02` sozinho funciona; `run all` falha
sempre na 02 (logo depois da 01), com o mesmo formato de erro do bug do
CSINe de hoje mais cedo — `-300 'Device specific error'` no
`INITiate:IMMediate` dentro de `arm()`, e a RECUPERAÇÃO
(`recuperar_estado_seguro()`) falha com o MESMO tipo de erro, virando
`FalhaFatalDeInstrumento` e abortando a bateria.

## Hipótese (bem fundamentada, mas ainda não confirmada na bancada)

`ExperimentoBase.executar()` (`logica/mestre.py`, linha ~704) chama
`self.fonte.restaurar_forma_e_modo_padrao()` no fim de **toda** classe
não-simulada — inclusive a 01/NORMAL, que nunca mudou forma nem modo.
Essa função (`logica/ametek_orm.py`, linha ~577-589) chama:

- `select_sine_shape()` (linha ~560): `write("SOURce:FUNCtion:SHAPe
  SINusoid")` + `aguardar_resposta()`.
- `disable_dc_offset()` (linha ~568): `write("SOURce:VOLTage:OFFSet 0")`,
  `write("SOURce:MODE AC")`, + `aguardar_resposta()`.

Nenhuma das duas chama `assert_no_errors()` depois do
`aguardar_resposta()`. Isso é EXATAMENTE o padrão do bug do CSINe de
hoje cedo: `aguardar_resposta()` só confirma que a fonte voltou a
responder `*IDN?` — não confirma que a fila de erros está limpa. Se
`FUNCtion:SHAPe SINusoid` ou `SOURce:MODE AC` gerarem um erro na fila
durante o período "mudo" (o mesmo fenômeno documentado para
`FUNCtion:SHAPe CSINusoid`/`SOURce:MODE ACDC`), esse erro fica parado
na fila até o PRÓXIMO `assert_no_errors()` — que é dentro do `arm()` da
classe seguinte, atribuído (de novo, erroneamente) a
`INITiate:IMMediate`.

Isso bate com o sintoma relatado: rodando uma classe isolada,
`restaurar_forma_e_modo_padrao()` roda por ÚLTIMO — se ela deixar erro
pendente, nada mais checa a fila depois, então nunca aparece. No `run
all`, o erro que a 01 deixa só aparece quando a 02 chama `arm()`.

O fix do CSINe (`configure_harmonics_csine()`, linha ~547-558) já
mostra o padrão certo: `aguardar_resposta()` **seguido de**
`assert_no_errors()` com uma mensagem que aponta o comando certo. Esse
padrão só foi aplicado ali — não em `select_sine_shape()` nem em
`disable_dc_offset()`.

## Peço para confirmar e corrigir

1. **Confirme antes de mexer.** Na bancada real, monte um teste isolado:
   rode a classe 01 (NORMAL) sozinha até completar, e LOGO DEPOIS do
   `restaurar_forma_e_modo_padrao()` dela (sem deixar nada mais rodar),
   chame `fonte.check_errors()` (não `assert_no_errors`, porque você
   quer VER o erro, não levantar exceção) e imprima o resultado. Se
   aparecer algo ali, a hipótese está confirmada e é literalmente o
   mesmo formato do bug do CSINe, só que em outro comando.
2. Se confirmado, aplique o mesmo padrão em `select_sine_shape()` e
   `disable_dc_offset()`: depois do `aguardar_resposta()` de cada uma,
   adicione `self.assert_no_errors(...)` com uma mensagem que identifica
   o comando (ex.: `"restaurar SINusoid"`, `"restaurar SOURce:MODE
   AC/offset"`), do jeito que já está em `configure_harmonics_csine()`.
   Considere também usar `*WAI` (o mecanismo validado hoje para
   `arm()`/`arm_transient()`, mais confiável que o polling de `*IDN?`)
   em vez de/além de `aguardar_resposta()` nesses dois métodos, se
   funcionar melhor no teste.
3. Depois de corrigir, teste especificamente a sequência que já
   reproduziu isto duas vezes: `run all` do zero, prestando atenção se
   passa da 02. Não precisa refazer as 20 classes a cada teste — dá pra
   testar só `run 01` seguido de `run 02` na mesma sessão/CLI (sem
   reconectar), que já reproduz o problema mais rápido.
4. Se a fila de erros aparecer VAZIA no passo 1 (hipótese errada), o
   problema é outro — nesse caso, adicione logging temporário de cada
   comando SCPI enviado com timestamp durante `restaurar_forma_e_modo_padrao()`
   e o início da classe seguinte, para achar o ponto exato onde as duas
   execuções (isolada vs. `run all`) divergem.
