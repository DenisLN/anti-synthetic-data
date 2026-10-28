#spec #pri 3

# ASD: Diagnóstico da Correlação de Distúrbio Abaixo de 0,90 e Modelo da CSINe

## Contexto

O professor mediu a correlação só da componente de distúrbio (medido menos senoide nominal contra `gerar()` menos senoide nominal, depois de alinhar) nas capturas de 07/10: "entre 0,75 e 0,94 em 03, 07, 09 e 17; e cai para 0,50 na 05 e 0,005 na 08". O dono quer entender por que essas classes ficam abaixo de 0,90.

Pistas já dadas pelo professor (`atividade.tex`, comentário da Pergunta 3): "Classe 05: na bancada, os níveis de 5 a 20 % saem pela CSINe (senoide grampeada), mas o modelo soma 3.ª, 5.ª e 7.ª harmônicas. A THD bate (5,00 %), a forma não: a 5.ª sai com sinal trocado, e a correlação do distúrbio fica em 0,50. Ou o modelo passa a ser a CSINe, ou todos os níveis vão por TRACE." Na lista final ele pede o item b): "modelo da 05 igual ao que a fonte faz (TRACE em todos os níveis, ou CSINe no modelo)". O dono escolheu tentar achar o modelo da CSINe, isto é, uma função para `gerar()` que reproduza a senoide grampeada da fonte para cada THD.

Na 08 a causa já é conhecida (impulso sai em 100 ms em vez de 80 ms a 50 Hz; deslocando 20 ms a correlação sobe para 0,6) e é tratada em outra spec; aqui basta confirmá-la. A 03 a 60 Hz tem sobressinal na borda de volta; 07, 09 e 17 envolvem bordas rápidas e oscilação da fonte (~7,5 kHz) e a reamostragem para TRACE de 1024 pontos.

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- Documento do professor: `C:\Users\denis\Downloads\tcc\02\atividade.tex` (Perguntas 2, 3, 10 e 12)
- Classe 05: `experimentos_nativos/05.py`; CSINe: `logica/ametek_orm.py`, `configure_harmonics_csine()` (linha ~825); manual SCPI: `docs/analise-2026-09-21/manuais_txt/AMETEK_MX_SCPI_Programming_Manual.txt` (procurar CSINusoid/clipped)
- Reamostragem TRACE: `_resample_cycle` e `program_capture()` em `logica/ametek_orm.py`
- Sessões: `resultados/sessao_2026-10-07_127V_50Hz`, `resultados/sessao_2026-10-07_230V_50Hz`, `resultados/sessao_2026-10-07_14-59-54_run02`; análise anterior: `docs/analise-2026-09-21/s1_pulse_csine.py`
- Função de correlação de distúrbio implementada pela spec da qual esta depende
- Depende de: ASD: Correlação da Componente de Distúrbio no Código
- Executor: sonnet

## Missão

1. Para cada classe abaixo de 0,90 (03, 05, 07, 08, 09, 17) e em cada sessão, identificar a causa principal da perda de correlação, separando: forma do modelo diferente da programada; conversão para TRACE (reamostragem/1024 pontos); resposta física da fonte (sobressinal, filtragem, oscilação); erro de alinhamento. Medir o efeito de cada causa (ex.: correlação contra a forma programada em vez de `gerar()`).
2. Caracterizar a CSINe da fonte a partir das capturas da 05 (níveis de 5 a 20 %): forma de um ciclo, nível de grampeamento em função da THD pedida, espectro (amplitude e fase das harmônicas).
3. Propor uma função `gerar_csine(t, f0, thd)` que reproduza essa forma (por exemplo, senoide grampeada simétrica com nível de corte resolvido numericamente para a THD pedida), e medir a correlação de distúrbio dela contra as capturas. Comparar com a alternativa de mandar todos os níveis por TRACE.
4. Recomendar, em uma frase por classe, o que fazer (mudar modelo, mudar programação, aceitar e documentar como física da fonte).

## Limites

- Somente leitura no repositório; scripts de análise novos vão em `docs/analise-2026-10-12/` e não alteram `logica/` nem `experimentos_*`.
- Não aplicar a função nova em `experimentos_nativos/05.py`: isso é feito em outra spec.
- Não tocar no hardware.
- Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/analise-2026-10-12/correlacao_disturbio_diagnostico.md`, com os scripts usados ao lado.
- Estrutura: uma seção por item da Missão; tabela classe × causa × correlação antes/depois de corrigir a causa; código da função `gerar_csine` proposta no corpo do relatório.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

O relatório existe, explica cada uma das seis classes com número medido, e traz a função `gerar_csine` com a correlação de distúrbio dela na 05 (ou registra como NÃO VERIFICADO por que nenhuma função passou de 0,90).
