#spec #pri 4

# ASD: Perfis de Faixas Norma, Literatura e Fronteira

## Contexto

O professor perguntou se o dataset segue as faixas típicas da IEEE 1159 ou as da literatura de classificação, e sugeriu (`atividade.tex`, questão da seção "Adequação das classes à IEEE 1159") "fazer todas as opções e discutir no paper. Cada captura recebe um perfil no metadata":

- perfil norma: flicker de 2 a 7 %, inter-harmônicas de 0,5 a 2 %, THD até 20 %, sag de 0,15 a 0,85 pu e swell de 1,15 a 1,75 pu;
- perfil literatura: as faixas atuais (flicker de 5 a 15 %, inter-harmônicas de 3 a 8 %, THD até 30 %);
- perfil fronteira (opcional): níveis exatamente em 0,1, 0,9, 1,1 e 1,8 pu, como teste de estresse.

"O gêmeo sintético sai do mesmo jeito nos três perfis." O dono quer os três. Isso também cobre as propostas 5 (níveis de sag e swell fora das fronteiras) e 6 (profundidade do flicker) do documento, e a Tabela `tab:ieee` (05 limitada a 20 % no perfil norma, também o teto do CSINe; 20 com 0,5–2 %). As compostas herdam as faixas dos seus componentes.

Autorização do dono (2026-10-12): esta spec pode mudar o que `gerar()` produz para uma dada seed. Pelo professor, todas as mudanças em `gerar()` entram juntas numa versão congelada antes da próxima campanha; as 63 capturas de 07/10 ficam como piloto. O perfil literatura deve reproduzir exatamente o dataset atual para a mesma seed.

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- Classes: `experimentos_nativos/02.py`, `03.py`, `05.py`; `experimentos_waveform/06.py`, `10.py`–`16.py`, `20.py`; especificação original: `experimentos.txt`
- CLI: `logica/cli.py` (padrão dos comandos `set`, `HELP_TEXT`); configuração: `logica/mestre.py` (`build_config`, metadata)
- Tabelas de referência: `atividade.tex`, `tab:classes` e `tab:ieee`
- Testes: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`
- Depende de: ASD: Metadata Legível e Rastreável por Sessão
- Executor: sonnet

## Missão

1. Criar um único lugar com as faixas de cada perfil por classe (simples e compostas) e fazer `gerar()` de cada classe lê-las pelo perfil ativo.
2. Expor o perfil na CLI (`set perfil norma|literatura|fronteira`, padrão literatura), no `HELP_TEXT`, no `status`, numa variável de ambiente para o simulado, e gravar `perfil` no metadata de cada captura.
3. Garantir que o perfil literatura reproduz byte a byte o `gerar()` atual para a mesma seed (teste que compare com o código de antes).
4. Rodar `scripts/relatorio_limites_bancada.py` a 127 V/60 Hz e 127 V/50 Hz para cada perfil e reportar o que cabe.
5. Registrar a autorização de mudar `gerar()` em `AGENTS.md`, no mesmo formato da "Autorização de 2026-10-07", e a mudança em `CHANGELOG/v1.15.md`.

## Limites

- Pode alterar: `experimentos_nativos/*.py` e `experimentos_waveform/*.py` (só faixas/níveis lidos de `gerar()`), `logica/mestre.py`, `logica/cli.py`, `logica/sinais.py`, `tests/test_offline.py`, `AGENTS.md`, `CHANGELOG/`, documentação.
- Não mudar início, duração, fase nem forma das classes: isso é de outras specs.
- Não alterar `max_voltage_rms`, `max_peak_v`, `max_current_a` nem a pré-validação de pico (`AGENTS.md`, "Limites inegociáveis").
- Não tocar no hardware. Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/perfis.md` (tabela classe × perfil × faixa) e relatório `docs/analise-2026-10-12/perfis_mudancas.md` com uma seção por item da Missão.
- Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline -v` e as saídas do relatório de limites.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

`set perfil` funciona nos três valores, o perfil aparece no metadata, o perfil literatura reproduz o dataset atual (teste), e os testes passam.
