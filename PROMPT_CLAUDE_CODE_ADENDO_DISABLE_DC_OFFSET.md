# Adendo — hipótese confirmada, mas achado novo: acontece até na classe 01, sem precisar de classe seguinte nenhuma

O diagnóstico que pedi funcionou: agora o erro aparece corretamente
atribuído a `disable_dc_offset()` (`restaurar SOURce:VOLTage:OFFSet 0 /
SOURce:MODE AC`), não mais escondido atrás do `INITiate:IMMediate` da
classe seguinte. Isso confirma a causa geral do adendo anterior.

Mas tem um detalhe novo: **aconteceu já na classe 01 (NORMAL)**, sozinha,
sem nenhuma classe antes dela nessa conexão. Ou seja, não precisa de
"01 seguida de 02" para reproduzir — `SOURce:VOLTage:OFFSet 0` e/ou
`SOURce:MODE AC` falham com `-300` na PRIMEIRA vez que rodam nessa
conexão, incondicionalmente. Isso é mais sério do que eu imaginei: não
é (só) uma corrida entre classes, é o comando em si falhando de forma
aparentemente determinística.

## Dois problemas para resolver, nessa ordem

### 1. `recuperar_estado_seguro()` está condenado a falhar do mesmo jeito

`recuperar_estado_seguro()` (`mestre.py`, linha ~464) chama
`fonte.restaurar_forma_e_modo_padrao()` — a MESMA função que acabou de
falhar. Óbvio que vai falhar de novo com o mesmo erro. Isso faz TODA
falha em `restaurar_forma_e_modo_padrao()` virar automaticamente
`FalhaFatalDeInstrumento` e abortar a bateria inteira, mesmo que o
problema seja só nesse comando específico e a saída/tensão continuem
seguras. Preciso que a recuperação não repita cegamente a operação que
já provou estar quebrada.

### 2. Achar por que `SOURce:VOLTage:OFFSet 0`/`SOURce:MODE AC` falha, mesmo sem DC_OFFSET ter rodado

`disable_dc_offset()` roda incondicionalmente no fim de TODA classe,
mesmo quando nada mudou o offset/modo (nenhuma classe 19/DC_OFFSET
rodou ainda nessa conexão). Duas hipóteses, teste as duas:

**A. É idempotência, não timing.** Talvez `SOURce:MODE AC` (ou
`VOLTage:OFFSet 0`) dê erro quando a fonte JÁ está em AC/offset zero —
alguns instrumentos rejeitam redefinir um modo pro valor que já está
ativo. Teste: adicione rastreamento de estado em Python (um
`self._dc_offset_ativo: bool`, setado por `enable_dc_offset()` e por
`disable_dc_offset()`) e faça `disable_dc_offset()` ser NO-OP
(não escrever nada) quando `_dc_offset_ativo` já é `False`. Isso também
resolve o problema por outro ângulo: só as classes 05/HARMONICS e
19/DC_OFFSET realmente precisam desfazer alguma coisa — as outras 18
não têm nada para restaurar. Mesma lógica vale para
`select_sine_shape()`: só rodar se a forma atual não for já SINusoid
(rastreie com `self._forma_atual` setado por `configure_harmonics_csine()`).
Isso reduz a exposição ao comando problemático de "toda classe, toda
vez" para só depois de 05 e 19 — bem mais raro, e mais fácil de isolar
se ainda falhar.

**B. Ainda é o mesmo timing/paralelismo dos outros casos**, e o comando
problemático especificamente é `SOURce:MODE AC` (troca de modo,
documentado alhures como "deixa a fonte ocupada"). Teste isolado: mande
só `SOURce:VOLTage:OFFSet 0`, cheque a fila; depois só `SOURce:MODE AC`
sozinho (com `*WAI` antes do próximo comando, e `aguardar_resposta()`
antes de checar erro), cheque a fila de novo. Isso separa qual dos dois
comandos é o culpado — hoje `assert_no_errors()` roda uma vez só depois
dos dois juntos, então não dá pra saber qual foi.

Faça o teste A primeiro — é mais barato (não precisa mexer em SCPI) e,
se funcionar, já elimina o problema na prática para 18 das 20 classes
sem precisar entender o -300 a fundo. Só investigue B se A não for
suficiente (ex.: se 05 ou 19 ainda falharem depois de rodar de verdade).

## Depois de corrigir os dois

Rode `run all` do zero de novo. Se ainda falhar em outro ponto, me
mande o traceback como fez agora — com `assert_no_errors()` já
apontando o comando certo em cada função, deve ficar rápido de
localizar.
