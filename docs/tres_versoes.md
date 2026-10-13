# Três versões de cada captura: modelo, programada e medida

Pergunta 2 do professor (`atividade.tex`, item c): publicar, com a mesma seed, o que o modelo pede, o que a bancada foi programada para emitir e o que se mediu. Separa o que é limite da bancada (modelo contra programada) do que é física da fonte (programada contra medida).

Todas são vetores de 6000 amostras a 30 kSa/s, em pu do pico nominal (`tensao_base_rms * sqrt(2)`), na **janela rotulada** (a mesma de `gerar()` e do `sem_margem/`).

| Versão | O que é | Como se obtém |
|---|---|---|
| `modelo` | a classe como o dataset a define | `gerar()` com a seed da captura (sorteio de início/duração/fase do metadata) |
| `programada` | o que a fonte emite para o que o código lhe mandou | determinística, sem instrumento (abaixo) |
| `medida` | o CH1 do osciloscópio | recorte do registro bruto (8100 amostras, com margem) em `inicio_janela` |

## `programada`

**Classes TRACe/LIST** (06 a 17, 20 e o nível de 30 % da 05): `AmetekMX30.montar_programacao(forma_de_bancada, base_voltage_rms, frequency_hz, dc_offset_pu)` (`logica/ametek_orm.py`), a mesma função que `program_capture()` usa para montar o que envia. `forma_de_bancada` é a saída de `forma_para_bancada()`: o `k` (`fator_disturbio_bancada`) e o limite de pico da 08 já aplicados. A função faz: ciclos de `30000/f0` amostras (500 a 60 Hz, 600 a 50 Hz), remoção do DC do ciclo, reamostragem para 1024 pontos, remoção da média, normalização pelo pico (`TRACe:DATA`) e rms da componente CA do ciclo, sem a média (`SOURce:LIST:VOLTage`; antes da spec 11 era o rms com a média, que inflava a amplitude CA nos ciclos de média diferente de zero), ambos arredondados a `%.8g` como no SCPI. `ProgramacaoCaptura.programada_pu()` volta à grade de 30 kSa/s: cada TRACe escalada ao rms de `LIST:VOLTage` (o manual, p. 126, diz que a fonte remove o DC e garante o rms), interpolada de 1024 pontos para o ciclo (reamostragem periódica nos dois sentidos), mais o offset DC. A previsão de pico (`last_programmed_peak_v`, `pico_acumulado_v`) é o pico dessa TRACe escalada, `max|TRACe| · LIST:VOLTage / rms(TRACe)` (+ o pico do offset DC), calculada sobre os números enviados em `%.8g`; ela não é menor que o pico de `programada_pu()` (`RmsCaEPicoPrevistoTests`). A média de cada ciclo continua perdida: a fonte a remove da TRACe e o `SOURce:VOLTage:OFFSet` é um só para a captura inteira.

**Classes nativas** (`sinais.forma_programada_nativa`, `logica/sinais.py`): a forma ideal para os comandos enviados.

| Classe | Mecanismo | Programada |
|---|---|---|
| 01 | `VOLTage:TRIGgered` (STEP) | senoide na tensão base truncada em 0,1 V |
| 02, 03, 04 | PULSe | senoide; em `[inicio, inicio + duração)` o nível `nível x base` truncado em 0,1 V (2,1813 V vira 2,2 V), fora disso a base |
| 05, THD <= 20 % | `FUNCtion:CSINusoid` | senoide clipada cujo THD é o pedido, com o rms da senoide |
| 05, 30 % | TRACe | igual às classes TRACe/LIST |
| 18 | `LIST:FREQuency` de 2 pontos | `start_hz` na 1.ª metade da janela e `end_hz` na 2.ª, fase contínua |
| 19 | STEP + `SOURce:VOLTage:OFFSet` | senoide na base mais o offset enviado |

Início e duração vêm do metadata (`inicio_disturbio_s`, `duracao_s`); sem sorteio, de `INICIO_S`/`DURACAO_S` da classe. A programada **não** inclui o que a fonte faz de diferente do pedido (por exemplo, o déficit de 5 a 6 % de amplitude em ACDC da classe 19, `docs/analise-2026-10-12/acdc_amplitude.md`): isso é a diferença programada contra medida.

No **simulado** não há limite de bancada: a programada é a ideal do dataset (na 08, 5 a 10 pu, que a fonte real não emitiria).

## Onde ficam

| Origem | Arquivo | Conteúdo |
|---|---|---|
| Captura física | `<sessão>/tres_versoes/NN_classe_<rótulo>.npz` (mesmo nome do `.npz` da captura) | `modelo_pu`, `programada_pu`, `medida_pu` (cada um `(1, 6000)`), `tempo_ms`, `inicio_janela`, `origem_programada`, `classe`, `id_captura` |
| Simulado | `<sessão>/tres_versoes/NN_classe.npz` | `modelo_pu`, `programada_pu` (cada um `(N, 6000)`), `origem_programada` (um texto por captura), `tempo_ms`, `classe`, `id_captura`. Sem `medida_pu` |
| Sessão antiga, gerada offline | `<sessão>/tres_versoes/NN_classe_<rótulo>.npz` + `indice.json` | `modelo_pu`, `programada_pu`, `origem_programada`, `tempo_ms`, `classe`, `id_captura`. Sem `medida_pu`: a medida continua no `.npz` original, com margem |

Cada linha do metadata ganha `tres_versoes: {arquivo, programada}` (`docs/metadata.md`). `medida_pu` é `tensao_pu` do `.npz` principal recortado em `inicio_janela` (a margem de 20 ms antes e 50 ms depois não entra). Os `.npz` com ruído (`snr_XXdb/`) e a corrente não têm as três versões.

## Como regenerar (sem hardware)

```powershell
.\env\Scripts\python.exe scripts\gerar_tres_versoes.py resultados\sessao_2026-10-07_127V_50Hz
.\env\Scripts\python.exe scripts\gerar_tres_versoes.py resultados\sessao_... --saida outra_pasta
.\env\Scripts\python.exe scripts\gerar_tres_versoes.py resultados\sessao_... --refazer   # saída já gerada por ele
```

O script lê `metadata/*.jsonl` (seed, `nivel_indice`, `f0_hz`, `tensao_base_rms`, `parametros`, `sorteio_posicao` ausente = desligado, `perfil` ausente = literatura) e **só escreve na pasta nova**; recusa uma pasta que já tenha arquivos. A forma de bancada vem do que foi gravado (o `fator_disturbio_bancada` como `senoide + k * (modelo - senoide)`; na 08, `amplitude_bancada_pu`), não de código de hoje. Verificações por captura em `indice.json`: o pico da forma de bancada contra `pico_programado_v` gravado e os parâmetros de `gerar()` contra os gravados (`avisos`).

## O que não está confirmado

- Que a fonte escale a TRACe ao rms de `LIST:VOLTage` é do manual (p. 126); a forma exata na saída só a bancada confirma. Nas 99 capturas de 07/10 a programada ficou mais perto da medida que o modelo em 70, empatou em 28 e perdeu em 1 por 0,0001 pu (`docs/analise-2026-10-12/tres_versoes_mudancas.md`).
- A senoide clipada da CSINusoid (corte e escala) é uma suposição: o THD é o pedido, o rms é o da senoide. Na 05 a 127 V o pico medido (0,954 pu) fica 3 % acima do da programada (0,926 pu).
- 18: a continuidade da fase na troca de passo do `LIST:FREQuency`.
- A largura de pulso do PULSe e o instante exato de aplicação (resolução da fonte) não entram.
