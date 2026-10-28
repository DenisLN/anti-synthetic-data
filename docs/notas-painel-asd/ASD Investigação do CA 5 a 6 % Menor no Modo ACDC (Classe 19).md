#spec #pri 2

# ASD: Investigação do CA 5 a 6 % Menor no Modo ACDC (Classe 19)

## Contexto

Na classe 19 (DC OFFSET), a componente alternada sai com pico de 0,94 a 0,95 pu (5 a 6 % abaixo do programado) nas três sessões de 07/10, igual nas três capturas e independente do offset. Na mesma sessão, a 01 dá 1,00 pu. A 19 passa para `SOURce:MODE ACDC` para somar o nível contínuo (`SOURce:VOLTage:OFFSet`); a troca de modo derruba a saída (126,6 V antes, 0,055 V depois) até o degrau `VOLTage:MODE STEP` disparar.

Comentário do professor (`atividade.tex`, Pergunta 9): "Na 19, medi o nível CC: ele sai 0,005 a 0,0075 pu abaixo do programado, a mesma ordem do offset CC da cadeia de medição nas outras classes (0,004 a 0,012 pu). O CC está ok; falta só explicar o CA 5 a 6 % menor no modo ACDC." Proposta 9: "com offset zero, comparar `MEASure:VOLTage:AC?` da fonte com o canal 1 nos modos AC e ACDC."

O dono quer uma investigação que explique a causa e proponha uma correção.

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- Classe: `experimentos_nativos/19.py`; ORM: `logica/ametek_orm.py` (`enable_dc_offset`, `disable_dc_offset`, `trigger_step`, faixa `SOURce:VOLTage:RANGe`)
- Transcrições SCPI e metadata: `resultados/sessao_2026-10-07_*/scpi_transcricao.log` e `metadata/19_*.jsonl`
- Manual: `docs/analise-2026-09-21/manuais_txt/AMETEK_MX_SCPI_Programming_Manual.txt` (SOURce:MODE, ACDC, faixas, limites de tensão no modo ACDC)
- Script de comparação existente: `scripts/diag_fonte_vs_osciloscopio.py`
- Depende de: nada
- Executor: sonnet

## Missão

1. Levantar hipóteses a partir do manual e das transcrições (ex.: no modo ACDC a fonte usa outra faixa ou outro ganho; o valor de `VOLTage:TRIGgered` é interpretado como RMS total CA+CC; limite de pico no modo ACDC; resposta em frequência diferente) e checar cada uma nos dados já gravados.
2. Escrever `scripts/diag_acdc_amplitude.py`, que importa os ORMs do projeto e, com offset zero, mede `MEASure:VOLTage:AC?` da fonte e o RMS/pico do canal 1 nos modos AC e ACDC, na tensão base, e depois com offsets de 2 % e 10 %.
3. Executar o script na bancada com o operador presente, se disponível, e registrar as medidas.
4. Propor uma correção concreta (ex.: compensar a tensão programada, trocar a ordem dos comandos, usar outra faixa), com o efeito esperado em pu, sem aplicá-la ao código da classe.

## Limites

- Toda energização exige confirmação digitada pelo operador (case-sensitive). Não automatizar confirmações.
- Respeitar integralmente `AGENTS.md`, "Limites inegociáveis". Offsets dentro do que a 19 já usa (0,02 a 0,10 pu).
- Se houver falha de infraestrutura: confirmar fisicamente OUTPUT OFF, não repetir automaticamente e entregar o log mais recente de `logs\`.
- Pode criar só `scripts/diag_acdc_amplitude.py` e o relatório. Não alterar `experimentos_nativos/19.py`, `ametek_orm.py` nem `mestre.py`.
- Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/analise-2026-10-12/acdc_amplitude.md`, uma seção por item da Missão, com tabela modo × offset × medida da fonte × medida do canal 1 × razão.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

O relatório identifica a causa com medida que a sustente e traz uma correção proposta; ou, sem acesso à bancada, entrega o script pronto, as hipóteses checadas nos dados gravados e marca os itens 3 e 4 como NÃO VERIFICADO.
