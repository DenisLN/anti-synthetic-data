# Adendo — retry automático (tempo curto, não precisa parar o run all)

A resiliência está funcionando certo: `run all` seguiu direto depois da
02 e da 08 falharem. Não pare a bateria que está rodando agora por
causa disso.

## Classe 02/SAG: `-113 Undefined header` de novo, em outro comando

Já é a 3ª vez que esse tipo de erro aparece em lugares diferentes
(CSINe, `disable_dc_offset`, agora `trigger_pulse`/`arm()`, mesmo já
com `*WAI`). Isso cheira a race condition genuinamente intermitente na
Rev. 5.53 — não 100% eliminável só ajustando espera em mais um lugar.
Não vale caçar a causa raiz agora com o tempo curto.

**Peço: adicionar retry automático por classe**, especificamente para
falhas que já foram classificadas como erro de INSTRUMENTO dentro de
uma classe (não infraestrutura — essas continuam abortando tudo, sem
mudança nenhuma):

1. Em `Bancada.executar_bateria()` (`mestre.py`, ~linha 395-416), ao
   capturar um `Exception` de uma classe (não `CommunicationError`/
   `FalhaFatalDeInstrumento`), antes de marcar como `FALHOU` definitivo:
   chame `recuperar_estado_seguro()` e tente a MESMA classe de novo,
   até 2 tentativas extras (3 no total). Só desiste e marca `FALHOU` se
   todas as tentativas falharem.
2. Log claro de cada tentativa (`[NN] tentativa 2/3 depois de falha:
   <motivo>`), pra ficar óbvio no console o que está acontecendo.
3. Isso é propositalmente uma rede de segurança grosseira, não uma
   correção elegante — está bom assim por agora. Não precisa investigar
   mais fundo a causa do `-113` nesta sessão.

## Classe 08/TRANSIENT: NÃO é bug, é limite físico — não mexer agora

`experimentos.txt` pede pico de 5 a 10 pu acima do normal pra essa
classe; a 127 Vrms de base isso passa de 900-1800 V, muito acima do
teto físico da fonte no range de 300 Vrms (415.8 Vp). O dataset
SIMULADO não tem esse problema (matemática pura). Isso é uma limitação
de comissionamento físico dessa classe específica nessa tensão de
teste, não um bug do código. Deixa como está — o retry do item acima
não vai resolver isso (vai falhar as 3 tentativas do mesmo jeito, o que
é esperado) e está tudo bem: a classe fica marcada FALHOU no resumo
final, e os dados simulados dela continuam válidos para o treino.

## Depois que a bateria atual terminar

Me mostra o resumo final (quantas OK, quais falharam) antes de eu ir
embora do laboratório.
