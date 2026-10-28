#spec #pri 4

# ASD: Três Versões de Cada Captura (Modelo, Programada e Medida)

## Contexto

Comentário do professor (`atividade.tex`, Pergunta 2): "Sugestão para o dataset: publicar três versões de cada captura, todas com a mesma seed: a do modelo (`gerar()`), a programada (depois do fator k e da conversão para TRACE, que é determinística e pode ser refeita offline) e a medida. Assim dá para separar o que é limite da bancada do que é física da fonte, e cada captura física ganha um gêmeo sintético exato. Esse é o diferencial do dataset." Na lista final, item c).

Hoje só a medida (e o `.npz` com ruído) é gravada. A forma programada passa por: `forma_para_bancada()` e fator redutor k (`mestre.py`), corte em ciclos (500 amostras a 60 Hz, 600 a 50 Hz), reamostragem para 1024 pontos (`_resample_cycle`), remoção da média, normalização pelo pico e amplitude por ciclo via `LIST:VOLTage` (`program_capture()` em `logica/ametek_orm.py`). Nas classes nativas (02, 03, 04, 05 com CSINe, 18, 19) a fonte gera a forma internamente; a "programada" delas precisa ser definida (ex.: o pulso/degrau ideal com o nível truncado em 0,1 V que foi enviado).

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- `logica/mestre.py` (`_salvar_captura`, `forma_para_bancada`, k), `logica/ametek_orm.py` (`program_capture`, `_resample_cycle`), `experimentos_nativos/*.py`, `experimentos_waveform/*.py`
- Formato do metadata definido pela spec da qual esta depende
- Testes: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`
- Depende de: ASD: Metadata Legível e Rastreável por Sessão
- Executor: sonnet

## Missão

1. Extrair, sem duplicar lógica, uma função pura (sem SCPI) que reconstrói a forma programada a 30 kSa/s a partir da forma de bancada: k, ciclos, reamostragem 1024, normalização e RMS por ciclo, voltando para a grade da captura. `program_capture()` deve passar a usar a mesma função para montar o que envia, para que as duas nunca divirjam.
2. Definir e implementar a forma programada das classes nativas.
3. Gravar as três versões em cada captura física (`modelo`, `programada`, `medida`), alinhadas na janela rotulada, com nomes de pasta/arquivo documentados. No simulado, gravar `modelo` e `programada`.
4. Criar um script offline que gera `modelo` e `programada` para sessões antigas a partir do metadata (seed, nível, k), e rodar nas três sessões de 07/10 sem alterar os arquivos originais.
5. Cobrir com testes: a função do item 1 gera, byte a byte, os mesmos pontos de TRACE e `LIST:VOLTage` que `program_capture()` envia no modo simulado.

## Limites

- Pode alterar: `logica/mestre.py`, `logica/ametek_orm.py` (só refatorar a montagem da forma; a sequência SCPI enviada tem de ficar idêntica), `logica/sinais.py`, `scripts/`, `tests/test_offline.py`, documentação.
- Não mudar o que `gerar()` produz.
- Não mexer no cache de TRACe nem nas validações de 6000 pontos/IDN/SCPI (`AGENTS.md`, "Limites inegociáveis").
- Não tocar no hardware. Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/tres_versoes.md` (o que é cada versão, onde fica, como regenerar) e relatório `docs/analise-2026-10-12/tres_versoes_mudancas.md` com uma seção por item da Missão.
- Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline -v` e a execução do script do item 4 nas três sessões — colar as saídas.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

O teste do item 5 passa, os testes offline passam, e as três sessões de 07/10 têm `modelo` e `programada` gerados offline numa pasta nova, sem tocar nos originais.
