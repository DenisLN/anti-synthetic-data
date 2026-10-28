#spec #pri 3

# ASD: Classes 05, 07 e 18 Alinhadas à Fonte e à Norma

## Contexto

Três ajustes de classe pedidos pelo professor, que o dono quer implementar:

- Classe 05 (item b da lista final): "modelo da 05 igual ao que a fonte faz (TRACE em todos os níveis, ou CSINe no modelo)". O dono escolheu CSINe no modelo; a função `gerar_csine` foi proposta e medida na spec de diagnóstico da correlação. No perfil norma a THD vai até 20 % (teto do CSINe); o nível de 30 % do perfil literatura continua por TRACE.
- Classe 07 (proposta 7): "A IEEE 1159-2019 descreve o notching como periódico e contínuo, causado pela comutação de conversores (cláusula 4.4.5.4, p. 30). Hoje a 07 só tem entalhes em 4 ciclos; a proposta é aplicá-los em todos os ciclos da janela." Avaliar também a 17 (NOTCH+OSC).
- Classe 18 (item a): "o `gerar()` varre 57→63 Hz qualquer que seja f0. Nas sessões de 50 Hz ela vira uma senoide de quase 60 Hz [...] Sugestão: f0−3 → f0+3 Hz." O `configurar()` usa os mesmos valores em `frequency_drift_list`.

Autorização do dono (2026-10-12): esta spec pode mudar o que `gerar()` produz para uma dada seed, como parte da mesma versão congelada.

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- `experimentos_nativos/05.py`, `experimentos_waveform/07.py`, `experimentos_waveform/17.py`, `experimentos_nativos/18.py`
- Relatório da spec de diagnóstico: `docs/analise-2026-10-12/correlacao_disturbio_diagnostico.md` (função `gerar_csine`)
- Restauração da frequência base depois da 18: `logica/mestre.py` / `logica/ametek_orm.py` (v1.12)
- Testes: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`
- Depende de: ASD: Diagnóstico da Correlação de Distúrbio Abaixo de 0,90 e Modelo da CSINe; ASD: Parâmetros Sorteados nas Compostas e Teste de Formas Distintas
- Executor: sonnet

## Missão

1. Classe 05: usar o modelo de CSINe em `gerar()` para os níveis que a bancada gera por CSINe, mantendo a soma de harmônicas só onde a bancada usa TRACE; conferir que a THD do modelo bate com a pedida.
2. Classe 07: aplicar os entalhes em todos os ciclos da janela, com os parâmetros sorteados por captura; decidir se a 17 segue a mesma regra e justificar.
3. Classe 18: varrer f0−3 → f0+3 Hz (e o inverso) em `gerar()` e em `configurar()`; conferir que a frequência base continua sendo restaurada.
4. Rodar `scripts/relatorio_limites_bancada.py` a 127 V/50 e 60 Hz e reportar se alguma das três passou a ser reduzida/pulada.
5. Registrar a mudança em `CHANGELOG/v1.15.md` e atualizar o teste de formas distintas se necessário.

## Limites

- Pode alterar: `experimentos_nativos/05.py`, `experimentos_nativos/18.py`, `experimentos_waveform/07.py`, `experimentos_waveform/17.py`, `logica/sinais.py` (se a CSINe virar função compartilhada), `tests/test_offline.py`, `CHANGELOG/v1.15.md`, documentação.
- Não remover o `assert_no_errors()` depois de `SOURce:FUNCtion:SHAPe:CSINusoid` nem outras validações (`AGENTS.md`, "Limites inegociáveis").
- Não tocar no hardware. Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/analise-2026-10-12/classes_05_07_18.md`, uma seção por item da Missão.
- Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline -v` e a saída do relatório de limites.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

As três classes estão alteradas, os testes passam e o relatório de limites a 127 V mostra o que cabe.
