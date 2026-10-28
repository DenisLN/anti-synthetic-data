#spec #pri 4

# ASD: Metadata Legível e Rastreável por Sessão

## Contexto

Hoje cada classe grava `metadata/*.jsonl` com uma linha JSON por captura (`json.dumps(..., sort_keys=True)` em `_salvar_captura`, `logica/mestre.py` ~linha 1815, e em `_salvar_classe_simulada` ~linha 1923). Sem quebra de linha, um humano não consegue ler.

O professor pediu, em `atividade.tex`:

- Pergunta 1: "Daqui para frente, toda sessão sai de commit limpo, e o metadata grava o commit, a versão do numpy e uma cópia da `calibracao_extremos.json` usada." (as sessões de 07/10 registram `994e170-dirty`)
- Pergunta 4: "gravar o início da janela já calculado no metadata (`inicio_janela`), para ninguém precisar refazer a conta." A fórmula é `inicio = indice_trigger - pre_trigger_s * fs`, já usada em `logica/recortar_margem.py`.
- Pergunta 11: "Rodando hoje o código de bancada, o k recalculado [...] sai diferente do gravado (a tabela de calibração mudou depois da sessão). O metadata é a referência, e é mais um motivo para guardar a calibração junto com cada sessão."

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- Escrita do metadata: `logica/mestre.py` (`_salvar_captura`, `_finalizar_gravacao`, `_salvar_classe_simulada`; campo `versao_codigo`)
- Leitores do metadata que não podem quebrar: `logica/recortar_margem.py` (`carregar_metadados`), `logica/analisar_sessao.py`, `logica/relatorio_html.py`, `scripts/recalibrar_extremos.py`
- Calibração: `logica/calibracao_extremos.json`
- Testes: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`
- Depende de: nada
- Executor: sonnet

## Missão

1. Tornar o metadata legível por humano sem perder o que os leitores atuais esperam: decidir o formato (ex.: manter o `.jsonl` como formato de máquina e gravar ao lado um `.json` indentado por classe, ou trocar para JSON indentado e adaptar os leitores) e justificar. Os leitores precisam continuar lendo as sessões antigas (`.jsonl` de uma linha).
2. Gravar `inicio_janela` (índice da amostra) em cada captura física, calculado com a mesma fórmula de `recortar_margem.py`, e fazer os leitores preferirem esse campo quando existir.
3. Copiar a `calibracao_extremos.json` em uso para dentro da pasta da sessão no início da sessão, e registrar no metadata o caminho e um hash dela.
4. Registrar no metadata da sessão o commit (`git rev-parse HEAD`), se a árvore está suja, a versão do numpy e do Python. Se a árvore estiver suja numa sessão de bancada, avisar o operador em destaque no início da sessão (sem bloquear, a menos que já exista mecanismo de bloqueio).
5. Atualizar os testes offline para cobrir os itens 1 a 4.

## Limites

- Pode alterar: `logica/mestre.py` (só a parte de gravação de metadata e preparação da pasta da sessão), `logica/recortar_margem.py`, `logica/analisar_sessao.py`, `logica/relatorio_html.py`, `scripts/recalibrar_extremos.py`, `tests/test_offline.py`, `README.md`/`docs/` para documentar o formato.
- Não remover nenhum campo existente do metadata.
- Não alterar `gerar()`, `ametek_orm.py`, `oscilloscope_orm.py`, nem a sequência SCPI.
- Respeitar `AGENTS.md`, seção "Limites inegociáveis".
- Não tocar no hardware. Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/metadata.md` (formato novo, campo a campo, com exemplo de uma captura indentado) e um relatório curto `docs/analise-2026-10-12/metadata_mudancas.md` com uma seção por item da Missão.
- Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline -v` e `.\env\Scripts\python.exe logica\recortar_margem.py resultados\sessao_2026-10-07_127V_50Hz` (sessão antiga continua funcionando) — colar as saídas no relatório.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

Uma sessão simulada (`run all` com `BENCH_MODE=0`) gera metadata legível, com `inicio_janela` (nas físicas, coberto por teste), cópia da calibração, commit e versão do numpy; os testes passam; as sessões de 07/10 continuam sendo lidas.
