# Adendo — dois problemas de QUALIDADE DE DADO (não de comunicação SCPI)

A bateria terminou 17/20 sem erro de exceção, mas conferi os `.npz`
reais e achei dois problemas que fazem o dado capturado não bater com
o metadata/espec — mais sério do que os erros de SCPI de antes, porque
esses passaram sem lançar exceção nenhuma.

## 1. Classes TRACe (waveform): distúrbio aparece 50-90ms depois do programado

Comparei a envoltória de amplitude (janela de 1 ciclo) de cada `.npz`
real contra o que `experimentos.txt`/o metadata dizem que deveria
acontecer. Exemplo, `10_sag_harmonics.npz` (`sag_pu=0.5, thd=0.2`,
espec: sag+harmônicos entre 60-120ms):

- Esperado: ~1,0 pu de 0-60ms, sag+harmônicos (queda pra ~0,5pu com
  distorção) de 60-120ms, volta a ~1,0pu de 120-200ms.
- Medido: ~1,0-1,03pu limpo até uns 113-121ms, SÓ ENTÃO começa a cair,
  chega em ~0,47pu por volta de 158-162ms e **fica lá até o fim da
  janela (196ms)** — nunca volta ao normal.

Mesmo padrão em praticamente todas as classes TRACe que rodaram hoje
(06/FLICKER, 13/SWELL_HARMONICS, 16/INTERRUPTION_HARMONICS,
17/NOTCH_OSCILLATORY_TRANSIENT, etc. — todas com o distúrbio bem mais
tarde que o espec, e várias não voltando ao normal antes do fim dos
200ms). As classes NATIVAS (01/STEP, 03/SWELL-PULSe, 04/INTERRUPTION-
PULSe) têm só um atraso pequeno e consistente (~20ms — plausivelmente
delay físico real do trigger, o mesmo em todas). As classes TRACe têm
atraso bem maior e que parece variar entre 50-90ms — isso não parece
delay físico simples, parece um bug de indexação/ordem na reconstrução
dos 12 segmentos TRACe.

**Peço**: em vez de eu adivinhar mais, faça a comparação rigorosa —
pra 2-3 arquivos, gere o array esperado chamando `gerar()` da classe
correspondente com o MESMO seed do metadata (`seed` está em cada
`.jsonl` de `resultados/metadata/`), e faça correlação cruzada
(`numpy.correlate` ou `scipy.signal.correlate`) entre o array esperado
e `tensao_pu[0]` capturado, pra achar o deslocamento em amostras/ciclos
com precisão — em vez de eu estimar visualmente. Isso vai dizer se o
deslocamento é um número FIXO de ciclos (aponta pra bug de índice na
montagem dos 12 `TRACe:DEFine` em `program_capture()`,
`logica/ametek_orm.py` ~linha 830-990) ou varia por classe (aponta pra
outra causa, tipo settling time dependente da forma). Confira também
se `pre_trigger_s` está sendo tratado do mesmo jeito pras classes TRACe
que pras nativas SAG/SWELL/INTERRUPTION.

## 2. Classe 02/SAG: linha de base não sobe pra tensão nominal

Rodei `run 02` de novo depois da bateria (retry manual) — sem erro
SCPI dessa vez, mas o resultado está errado: metadata diz
`sag_pu: 0.1` (o nível mais severo dos 5 do espec), e o trecho
80-140ms bate certinho com isso (~0,1pu, correto). **O problema é
antes e depois do pulso**: deveria estar em ~1,0pu (127V, a base) e
está lendo perto de zero (banda ruidosa ~0,02pu) tanto antes quanto
depois do pulso. Ou seja, não é o sag que está errado — é a base que
nunca chegou em 127V nessa captura.

Confirmei que `run <NN>` isolado e `run all` chamam exatamente o mesmo
`mestre.Bancada.from_env(require_output=True)` (`cli.py`, ~linha 206 e
230) — não é falta de energização no comando isolado. Duas hipóteses
pra investigar:

1. Com `sag_pu=0.1` (o nível mais baixo/severo testado), alguma coisa
   em `trigger_pulse()` (`ametek_orm.py`, ~linha 501) ou no jeito que a
   AMETEK processa um `PULSe:WIDTh`/`VOLTage:TRIGgered` bem baixo afeta
   também o nível "imediato" (baseline), não só o nível transitório —
   verifique lendo `VOLTage:AC:IMMediate?` (se existir como query — tem
   comandos que a Rev. 5.53 não implementa como query, confirme antes)
   antes e depois do pulso nessa captura específica.
2. `energize_baseline()`/o setter de `voltage` (chamado em
   `Bancada.from_env()`) não confirmou de fato que o nível imediato
   chegou em `BASE_VOLTAGE_RMS` antes de liberar a captura — adicione
   uma leitura de verificação (`MEASure:VOLTage:RMS?`, já validado no
   preflight de comandos nativos) logo depois de energizar a baseline,
   e falhe alto (não silenciosamente) se não bater.

Reproduza rodando `run 02` de novo (é rápido, uma captura só) com
logging extra dessas duas leituras pra confirmar qual das duas
hipóteses é a certa antes de corrigir.

## Prioridade

Isso é mais importante que qualquer ajuste de robustez que já fizemos
hoje — um dado capturado sem exceção mas com o distúrbio na hora errada
(ou a base na tensão errada) é pior que uma falha visível, porque passa
despercebido. Antes de confiar nesse dataset físico pra qualquer coisa
(comparar com o simulado, por exemplo), isso precisa estar resolvido.
Pode ficar pra próxima sessão no laboratório — não precisa fazer mais
nada na bancada agora.
