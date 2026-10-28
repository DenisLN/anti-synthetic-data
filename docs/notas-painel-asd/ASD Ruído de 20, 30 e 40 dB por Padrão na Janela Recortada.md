#spec #pri 2

# ASD: Ruído de 20, 30 e 40 dB por Padrão na Janela Recortada

## Contexto

Hoje o padrão é só 30 dB (`SNR_LEVELS_DB = "30"` em `scripts/bench_config.ps1` linha 37; `env_float_tuple("SNR_LEVELS_DB", (30.0,))` em `logica/mestre.py` linha 180), e o ruído é calculado sobre o registro inteiro de 8100 amostras, com as margens. Nas classes TRACE a margem em zero reduz ~7 % a potência média, e dentro da janela o SNR sai ~30,3 dB.

O dono quer 20, 30 e 40 dB por padrão. O professor pediu (`atividade.tex`, Pergunta 8 e proposta 8): "ruído aplicado só na janela recortada, níveis de 20, 30 e 40 dB gerados offline e o SNR efetivo (bancada + acrescentado) registrado junto. A versão sem ruído acrescentado continua sendo a principal." A bancada já tem ruído próprio de ≈ 34 dB a 127 V e ≈ 37 dB a 230 V, medido na margem em zero.

Fórmula atual da seed do ruído: `noise_seed = seed + round(snr_db * 1000) + 50_000_000`, potência de referência `mean(x**2)`.

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- `logica/mestre.py` (SNR_LEVELS_DB, aplicação do ruído, `_salvar_captura`), `logica/sinais.py`, `scripts/bench_config.ps1`, `scripts/run_simulation_windows.ps1` (parâmetro `-SnrLevels`), `logica/recortar_margem.py`
- Sessões de 07/10 em `resultados/`
- Testes: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`
- Depende de: ASD: Três Versões de Cada Captura (Modelo, Programada e Medida)
- Executor: sonnet

## Missão

1. Mudar o padrão para 20, 30 e 40 dB na bancada e no simulado.
2. Calcular a potência de referência e somar o ruído só na janela rotulada (usando `inicio_janela`), mantendo a fórmula da seed. Decidir o que acontece com as margens dos arquivos com ruído (sem ruído, ou recortadas) e justificar.
3. Medir o ruído próprio da bancada em cada captura física (na margem anterior das classes TRACE ou por outro método justificado) e gravar no metadata o SNR acrescentado, o SNR da bancada e o SNR efetivo combinado.
4. Criar um script offline que gera os três níveis para sessões já capturadas a partir do `.npz` limpo, com a mesma fórmula, e rodar nas três sessões de 07/10 em pasta nova.
5. Cobrir com testes (seed reproduzível, SNR medido na janela ≈ nominal com tolerância).

## Limites

- Pode alterar: `logica/mestre.py` (parte de ruído e gravação), `logica/sinais.py`, `scripts/bench_config.ps1`, `scripts/run_simulation_windows.ps1`, `scripts/` (script novo), `tests/test_offline.py`, documentação.
- A versão sem ruído continua sendo a principal e não muda.
- Não alterar `gerar()` nem nada de SCPI. Respeitar `AGENTS.md`, "Limites inegociáveis".
- Não tocar no hardware. Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/analise-2026-10-12/snr_mudancas.md`, uma seção por item da Missão, com tabela do SNR da bancada por sessão.
- Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline -v` e a saída do script do item 4.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

Sem nenhuma variável de ambiente, uma sessão simulada grava `snr_20db/`, `snr_30db/` e `snr_40db/`; o SNR medido dentro da janela fica a ±0,2 dB do nominal; as três sessões de 07/10 têm os três níveis gerados offline; testes passam.
