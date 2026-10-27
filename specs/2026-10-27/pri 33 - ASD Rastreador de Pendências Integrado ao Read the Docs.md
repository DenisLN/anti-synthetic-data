#spec #pri 33

# ASD: Rastreador de Pendências Integrado ao Read the Docs

## Contexto

O fork trouxe um rastreador das 31 pendências (P-01 a P-31) que vive em quatro lugares que não se conversam:

- `docs/PENDENCIAS_TRACKER.md`: "fonte única de estado", tabela manual com placar e matriz (✅, 🔧→🏭, ❓, ⏳);
- `docs/estado_prontidao.json`: "estado de máquina", mas binário (`concluida`/`aberta`), o que esconde os parciais (achados, seção 4.7) e marca P-09 como `aberta` com evidência;
- `docs/execucao_pendencias.md` e `docs/decisoes_pendentes.md`: narrativa e decisões, cada um com a sua cópia de estados;
- `mapa/pendencias/P-NN.md` e `mapa/_modelos/pendencias.json`, gerados por `scripts/gerar_mapa_pendencias.py` (o `mapa/` sai da `main` na spec da documentação unificada).

Ferramentas que produzem estado: `scripts/fechar_pendencias.py` (gera `docs/evidencias/<data>/fechamento.json` por pendência: `evidencia_suficiente`, `insuficiente`, `reprovado`, `sem_dados`, `requer_revisao_humana`, `criterio_nao_definido`) e `scripts/verificar_prontidao.py` (lê `estado_prontidao.json` e `manifesto_prontidao.json`). O site já tem extensões próprias em `docs/_ext/`.

O dono pediu: "aparentemente tem um rastreador de pendências, precisamos integrá-lo ao read the docs de algum jeito". O problema a resolver é que o estado mostrado no site diverge do rastreador (o RTD publicava o inventário de 16/10 com "31 itens abertos"). Depois desta spec, deve haver **um** arquivo de estado, editado à mão ou pelas ferramentas, e o site deve renderizá-lo no build, de modo que o que o RTD mostra é sempre o que está commitado.

## Entradas

- `docs/PENDENCIAS_TRACKER.md`, `docs/estado_prontidao.json`, `docs/manifesto_prontidao.json`, `docs/execucao_pendencias.md`, `docs/decisoes_pendentes.md`, `docs/projeto/pendencias.md`, `docs/projeto/estado-validacao.md`
- `scripts/fechar_pendencias.py`, `scripts/verificar_prontidao.py`, `scripts/gerar_mapa_pendencias.py`
- `docs/conf.py`, `docs/_ext/`, `docs/index.md` (toctree "Projeto e estado")
- Testes: `tests/test_pendencias_prontidao.py`, `tests/test_pendencias_fechamento.py`
- Build: `sphinx-build -W -b html docs docs/_build/html` (ambiente de `docs/requirements.txt`)
- Depende de: ASD: Documentação Unificada no Read the Docs

## Missão

1. Definir um único arquivo de estado das pendências (pode ser o `docs/estado_prontidao.json` estendido) com, por P-NN: estado não binário (os quatro estados do rastreador mais "reprovada na bancada"), o que pede, como foi resolvida ou tratada (commits, evidência em `docs/evidencias/`), o que falta, quem fecha (bancada, decisão do dono, código) e decisão do dono registrada ou não; migrar para ele o conteúdo atual do rastreador sem mudar nenhum estado (a revisão dos estados é a spec seguinte).
2. Fazer o site renderizar a partir desse arquivo, no build do Sphinx (extensão em `docs/_ext/` ou diretiva), o placar e a matriz das pendências dentro de `docs/projeto/pendencias.md`, com âncora por P-NN que as páginas de classe possam citar.
3. Eliminar as cópias de estado: `docs/PENDENCIAS_TRACKER.md` deixa de existir ou vira só o protocolo para agentes, sem tabela; `docs/execucao_pendencias.md` e `docs/decisoes_pendentes.md` passam a referenciar a página gerada em vez de repetir estados; `scripts/gerar_mapa_pendencias.py` é removido ou passa a ler o arquivo único (decidir e justificar), e `scripts/verificar_prontidao.py` lê o novo formato.
4. Criar teste offline que falhe quando o arquivo de estado estiver inválido (P-NN faltando ou repetido, estado fora da lista, evidência citada que não existe em `docs/evidencias/`) e atualizar `CLAUDE.md`/`AGENTS.md` com o fluxo novo ("depois da coleta: `fechar_pendencias.py` → editar o arquivo único → build").
5. Registrar em `CHANGELOG/v1.15.md` e documentar o formato do arquivo numa página do site (por exemplo `docs/contribuir_docs.md`).

## Limites

- Não mudar o estado de nenhuma pendência nesta spec; só migrar.
- Não mudar a lógica de decisão de `scripts/fechar_pendencias.py` (critérios, limites, procedência física); só o formato de saída/entrada, se necessário.
- Não reescrever `docs/evidencias/` nem `CHANGELOG` fechados.
- Sem dependência nova de build que não esteja em `docs/requirements.txt`; se precisar, adicionar com versão fixa e justificar.
- Não tocar em `logica/`, `experimentos_*`, hardware.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.
- Se algum limite impedir ou restringir o resultado, registrar no relatório em "Limitações de escopo", sem ultrapassá-lo.

## Entregável

- Relatório `.md` no caminho que o despacho indicar, com: um bloco por item da Missão (copiar o texto do item, dizer CUMPRIDO, PARCIAL, NÃO CUMPRIDO ou IMPEDIDO, e explicar nos dois casos, com evidência); Critério de Parada atendido ou não; pendências que exigem o usuário; limitações de escopo; se a missão resolve o contexto; achados.
- Arquivo de estado único (caminho escolhido, citado no relatório) e a extensão/diretiva em `docs/_ext/`.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo.
- Verificação: `sphinx-build -W -b html docs docs/_build/html` e `python -m unittest discover -s tests -p "test*.py"`, com o resumo das saídas.

## Critério de Parada

A página `projeto/pendencias.html` gerada mostra as 31 pendências com o mesmo estado que o rastreador tinha antes da spec (tabela de conferência P-NN × estado antes × estado depois no relatório, 31 linhas iguais); `git grep -nE '^\| P-[0-9]{2} \|' -- docs ':!docs/evidencias'` só encontra tabelas geradas ou nenhuma; o teste novo falha com um arquivo de estado corrompido de propósito e passa com o real; build `-W` sem erro.
