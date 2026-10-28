#spec #pri 2

# ASD: CLI com Recalibração Automática e Relatório HTML

## Contexto

Hoje a recalibração dos fatores de extremo e o relatório HTML são passos manuais depois da sessão:

- `scripts/recalibrar_extremos.py <sessoes> [--gravar] [--substituir]`: sem `--gravar` só imprime; com `--gravar`, nenhum fator diminui (vale o maior entre o atual e o medido), a não ser com `--substituir`, "decisão explícita do dono".
- `logica/relatorio_html.py <sessao_dir> [--saida] [--titulo] [--snr] [--com-esperado] ...`: HTML autocontido da sessão.

O dono quer as duas coisas dentro da CLI interativa (`logica/cli.py`), ligáveis como os outros `set`: `set recalibracao on|off` (recalibração automática ao fim do `run`/`run all`, com aviso ao operador) e `set html on|off` (gerar o HTML ao fim da sessão).

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- `logica/cli.py` (`HELP_TEXT`, tratamento de `set` ~linha 326, `status` ~linha 249, fim do `run`/`run all`), `logica/mestre.py` (`executar_bateria`, pasta da sessão, cópia da calibração criada pela spec de metadata)
- `scripts/recalibrar_extremos.py` (`coletar`, gravação), `logica/relatorio_html.py` (`gerar_relatorio`, `main`), `logica/recortar_margem.py`
- Testes de CLI existentes em `tests/test_offline.py` (ex.: `test_set_seed_*`)
- Depende de: ASD: Metadata Legível e Rastreável por Sessão
- Executor: sonnet

## Missão

1. Implementar `set recalibracao on|off` (padrão off): ao fim de um `run`/`run all` físico, chamar a recalibração do próprio script (importando, sem duplicar) só sobre a sessão atual, no modo que nunca diminui fator, e imprimir em destaque para o operador cada fator que mudou (antes → depois, classe, condição). A cópia da calibração anterior fica guardada na sessão.
2. Implementar `set html on|off` (padrão a decidir e justificar): ao fim do `run`/`run all`, gerar o relatório HTML da sessão (versão recortada) importando `relatorio_html`, e imprimir o caminho.
3. Mostrar os dois estados em `status` e documentar no `HELP_TEXT`.
4. Garantir que falha na recalibração ou no HTML não derruba a sessão nem é tratada como falha de experimento: avisa e segue.
5. Cobrir com testes offline (modo simulado: não recalibra; HTML gerado numa sessão sintética).

## Limites

- Pode alterar: `logica/cli.py`, `logica/mestre.py` (só o gancho de fim de sessão), `scripts/recalibrar_extremos.py` e `logica/relatorio_html.py` (só para expor funções importáveis), `tests/test_offline.py`, documentação.
- A recalibração automática nunca usa o modo `--substituir` e nunca diminui um fator.
- Não mexer na resiliência por classe nem nas confirmações digitadas (`AGENTS.md`, "Limites inegociáveis").
- Não tocar no hardware. Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/analise-2026-10-12/cli_recalibracao_html.md`, uma seção por item da Missão, com um exemplo da saída da CLI.
- Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

`set recalibracao` e `set html` aparecem em `help` e `status`, os testes novos passam, e nenhum teste existente quebrou.
