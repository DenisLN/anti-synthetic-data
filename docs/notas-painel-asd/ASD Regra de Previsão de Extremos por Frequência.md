#spec #pri 3

# ASD: Regra de Previsão de Extremos por Frequência

## Contexto

A 230 V/50 Hz as classes 02, 03, 04 e 16 foram puladas porque a regra conservadora da v1.14 (`carregar_fatores_extremo`, `logica/mestre.py` linha ~390) usa, para classe sem medida na condição, o maior fator de todas as tabelas (1,475, da 16 a 127 V/60 Hz). A regra impediu justamente as classes que precisavam ser medidas para sair dela. Achado da v1.14: o sobressinal depende da frequência, não da tensão.

A proposta 8 do `atividade.tex` (seção "Regra de previsão de extremos por frequência") define a regra nova:

1. considerar apenas as tabelas com a mesma frequência da condição atual (ex.: 127 V/50 Hz e 230 V/50 Hz entre si);
2. dentro delas, usar o maior fator da própria classe;
3. manter a regra conservadora (maior fator de todas as tabelas) só quando a classe não tem medida em nenhuma condição de mesma frequência.

Com isso, a 230 V/50 Hz as classes 02, 04 e 16 passam a usar os fatores de 127 V/50 Hz e rodam. A 03 (swell 1,1 pu) continua 0,6 V acima do teto por causa da margem de 1,10. Decisão do professor, que o dono adota: "A regra por frequência (proposta 8) resolve. Na 03 a 230 V, mantenham a margem de 10 % e deixem essa captura de fora; a 127 V a classe está coberta." A verificação depois de cada captura (`:MEASure:VMAX?` contra o teto) continua valendo.

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- `logica/mestre.py` (`carregar_fatores_extremo`, `condicao_calibrada`, `fator_extremo_da_classe`, `MARGEM_FATOR_EXTREMO`), `logica/calibracao_extremos.json`
- Relatório offline: `.\env\Scripts\python.exe scripts\relatorio_limites_bancada.py --tensao 230 --frequencia 50 --capturas 5`
- Tabela de referência: `atividade.tex`, Tabela `tab:pulo230` (Pergunta 10)
- Testes: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`
- Depende de: nada
- Executor: sonnet

## Missão

1. Implementar a regra por frequência em `carregar_fatores_extremo`, nos três passos acima, mantendo o aviso de condição sem calibração.
2. Garantir que a 03 a 230 V/50 Hz continue de fora com a margem de 10 % (sem exceção especial no código: ela deve sair pela própria regra), e que o motivo apareça claro no log/relatório de limites.
3. Rodar o relatório de limites a 230 V/50 Hz e 127 V/50 e 60 Hz, antes e depois, e conferir contra a Tabela `tab:pulo230` (02 → 380,3 V, 04 → 380,3 V, 16 → 368,5 V cabem; 03 → 416,4 V não cabe).
4. Atualizar os testes que fixam a regra antiga e acrescentar testes para os três passos.
5. Registrar a mudança em `CHANGELOG/v1.15.md` (criar se não existir) e na documentação da regra.

## Limites

- Pode alterar: `logica/mestre.py` (só a previsão de extremos), `tests/test_offline.py`, `CHANGELOG/`, documentação.
- Não alterar `logica/calibracao_extremos.json` (valores medidos), `MARGEM_FATOR_EXTREMO`, `max_peak_v`, `max_voltage_rms`, `max_current_a` nem a verificação pós-captura de VMAX/VMIN (`AGENTS.md`, "Limites inegociáveis").
- Não tocar no hardware. Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/analise-2026-10-12/regra_por_frequencia.md`, uma seção por item da Missão, com a tabela antes/depois do item 3.
- Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline -v` e as saídas do relatório de limites.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

O relatório de limites a 230 V/50 Hz mostra 02, 04 e 16 cabendo e 03 de fora pela margem, com os valores da Tabela `tab:pulo230`; testes passam.
