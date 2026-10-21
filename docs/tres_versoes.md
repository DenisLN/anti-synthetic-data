# Três versões de cada captura: modelo, programada e medida

Objetivo: publicar, com a mesma seed, o que o modelo pede, o que a bancada foi programada para emitir e o que se mediu. Separa o que é limite da bancada (modelo contra programada) do que é física da fonte (programada contra medida).

Todas são vetores de 6000 amostras a 30 kSa/s, em pu do pico nominal (`tensao_base_rms * sqrt(2)`), na **janela rotulada** (a mesma de `gerar()` e do `sem_margem/`).

| Versão | O que é | Como se obtém |
|---|---|---|
| `modelo` | a classe como o dataset a define | `gerar()` com a seed da captura (sorteio de início/duração/fase do metadata) |
| `programada` | o que a fonte emite para o que o código lhe mandou | determinística, sem instrumento (abaixo) |
| `medida` | o CH1 do osciloscópio | recorte do registro bruto (8100 amostras, com margem) em `inicio_janela` |

## `programada`

**Classes TRACe/LIST** (06 a 17, 20 e o nível de 30 % da 05): `AmetekMX30.montar_programacao(forma_de_bancada, base_voltage_rms, frequency_hz, dc_offset_pu)` (`logica/ametek_orm.py`), a mesma função que `program_capture()` usa para montar o que envia. `forma_de_bancada` é a saída de `forma_para_bancada()`: o `k` (`fator_disturbio_bancada`) e o limite de pico da 08 já aplicados. A função faz: ciclos de `30000/f0` amostras (500 a 60 Hz, 600 a 50 Hz), remoção do DC do ciclo, reamostragem para 1024 pontos, remoção da média, normalização pelo pico (`TRACe:DATA`) e rms da componente CA do ciclo, sem a média (`SOURce:LIST:VOLTage`; antes da revisão anterior era o rms com a média, que inflava a amplitude CA nos ciclos de média diferente de zero), ambos arredondados a `%.8g` como no SCPI. `ProgramacaoCaptura.programada_pu()` volta à grade de 30 kSa/s: cada TRACe escalada ao rms de `LIST:VOLTage` (o manual, p. 126, diz que a fonte remove o DC e garante o rms), interpolada de 1024 pontos para o ciclo (reamostragem periódica nos dois sentidos), mais o offset DC. A previsão de pico (`last_programmed_peak_v`, `pico_acumulado_v`) é o pico dessa TRACe escalada, `max|TRACe| · LIST:VOLTage / rms(TRACe)` (+ o pico do offset DC), calculada sobre os números enviados em `%.8g`; ela não é menor que o pico de `programada_pu()` (`RmsCaEPicoPrevistoTests`). A média de cada ciclo continua perdida: a fonte a remove da TRACe e o `SOURce:VOLTage:OFFSet` é um só para a captura inteira.

**Classes nativas** (`sinais.forma_programada_nativa`, `logica/sinais.py`): a forma ideal para os comandos enviados.

| Classe | Mecanismo | Programada |
|---|---|---|
| 01 | `VOLTage:TRIGgered` (STEP) | senoide na tensão base truncada em 0,1 V |
| 02, 03, 04 | PULSe | senoide; em `[inicio, inicio + duração)` o nível `nível x base` truncado em 0,1 V (2,1813 V vira 2,2 V), fora disso a base |
| 05, THD <= 20 % | `FUNCtion:CSINusoid` | senoide clipada cujo THD é o pedido, com o rms da senoide |
| 05, 30 % | TRACe | igual às classes TRACe/LIST |
| 18 | `LIST:FREQuency` de 2 pontos | `start_hz` na 1.ª metade da janela e `end_hz` na 2.ª, fase contínua |
| 19 | STEP + `SOURce:VOLTage:OFFSet` | senoide na base mais o offset enviado |

Início e duração vêm do metadata (`inicio_disturbio_s`, `duracao_s`); sem sorteio, de `INICIO_S`/`DURACAO_S` da classe. A programada **não** inclui o que a fonte faz de diferente do pedido (por exemplo, o déficit de 5 a 6 % de amplitude em ACDC da classe 19, `arquivo/analises:docs/analise-2026-10-12/pendente/acdc_amplitude_VERIFICAR.md`): isso é a diferença programada contra medida.

No **simulado** não há limite de bancada: a programada é a ideal do dataset (na 08, 5 a 10 pu, que a fonte real não emitiria).

## Onde ficam

> **Quebra (v1.15, formato 2):** a pasta `tres_versoes/` e os arquivos `modelo_pu`/`programada_pu`/`medida_pu` por captura **deixaram de existir** nas sessões novas. As três versões estão dentro do `NN_classe.npz` da classe (`docs/dataset.md` §2), junto com as de cada perfil. Quem lia `tres_versoes/...npz` precisa trocar para as chaves abaixo (ou para `sessao_io.ler_capturas`).

| Origem | Arquivo | Conteúdo |
|---|---|---|
| Sessão nova (formato 2), física ou simulada | `<sessão>/NN_classe.npz` (um por classe, comprimido) | por `<perfil>` (`norma`, `literatura`, `fronteira`): `<perfil>/medida`, `<perfil>/modelo`, `<perfil>/programada`, `<perfil>/origem_programada`, `<perfil>/inicio_janela`, `<perfil>/id_captura`; mais `tempo_ms` (eixo da medida), `tempo_janela_ms` (eixo de 6000 pontos), `perfis`, `classe`, `formato_npz` |
| Sessão antiga (formato 1), física | `<sessão>/tres_versoes/NN_classe_<rótulo>.npz` (mesmo nome do `.npz` da captura) | `modelo_pu`, `programada_pu`, `medida_pu` (cada um `(1, 6000)`), `tempo_ms`, `inicio_janela`, `origem_programada`, `classe`, `id_captura` |
| Sessão antiga (formato 1), simulada | `<sessão>/tres_versoes/NN_classe.npz` | `modelo_pu`, `programada_pu` (cada um `(N, 6000)`), `origem_programada` (um texto por captura), `tempo_ms`, `classe`, `id_captura`. Sem `medida_pu` |
| Sessão antiga, gerada offline | `<sessão>/tres_versoes/NN_classe_<rótulo>.npz` + `indice.json` (`scripts/gerar_tres_versoes.py`) | `modelo_pu`, `programada_pu`, `origem_programada`, `tempo_ms`, `classe`, `id_captura`. Sem `medida_pu`: a medida continua no `.npz` original, com margem |

No formato 2, `modelo` e `programada` são `(N, 6000)`, na grade da janela rotulada; `medida` é o **registro inteiro** (`(N, 8100)` na bancada, com a margem de 20 ms antes e 50 ms depois, como era o `tensao_pu` do `.npz` por captura) e a janela rotulada é `medida[inicio_janela : inicio_janela + 6000]` (o `medida_pu` do formato 1). No simulado não há instrumento: `medida` é a própria série do dataset (6000 amostras, igual ao `modelo`) e `inicio_janela` vale 0. Uma `programada` não calculada fica como linha de `NaN`. Os `.npz` com ruído (`snr_XXdb/`) e a corrente não têm as três versões.

Cada linha do metadata ganha `tres_versoes: {arquivo, programada}` (no formato 2, `arquivo` é o `NN_classe.npz`; no 1, `tres_versoes/<nome>.npz`) e `arquivo_classe`, `perfil`, `indice_no_arquivo` (`docs/metadata.md`). Leitura: `logica/sessao_io.py` (`ler_capturas(..., versoes=("medida", "modelo", "programada"))`).

## Como regenerar (sem hardware, sessões do formato 1)

```powershell
.\env\Scripts\python.exe scripts\gerar_tres_versoes.py resultados\sessao_2026-10-07_127V_50Hz
.\env\Scripts\python.exe scripts\gerar_tres_versoes.py resultados\sessao_... --saida outra_pasta
.\env\Scripts\python.exe scripts\gerar_tres_versoes.py resultados\sessao_... --refazer   # saída já gerada por ele
```

Só para sessões do formato 1 (um `.npz` por captura): numa sessão do formato 2 o script recusa (`ValueError`), porque as três versões já estão no `NN_classe.npz`. O script lê `metadata/*.jsonl` (seed, `nivel_indice`, `f0_hz`, `tensao_base_rms`, `parametros`, `sorteio_posicao` ausente = desligado, `perfil` ausente = literatura) e **só escreve na pasta nova**; recusa uma pasta que já tenha arquivos. A forma de bancada vem do que foi gravado (o `fator_disturbio_bancada` como `senoide + k * (modelo - senoide)`; na 08, `amplitude_bancada_pu`), não de código de hoje. Verificações por captura em `indice.json`: o pico da forma de bancada contra `pico_programado_v` gravado e os parâmetros de `gerar()` contra os gravados (`avisos`).

## O que não está confirmado

- Que a fonte escale a TRACe ao rms de `LIST:VOLTage` é do manual (p. 126); a forma exata na saída só a bancada confirma. O relato anterior usa **99 capturas** (36 + 36 + 27, três sessões) de 07/10: a programada ficou mais perto da medida que o modelo em 70, empatou em 28 e perdeu em 1 por 0,0001 pu (`arquivo/analises:docs/analise-2026-10-12/resolvido/tres_versoes_mudancas.md`).
- A senoide clipada da CSINusoid (corte e escala) é uma suposição: o THD é o pedido, o rms é o da senoide. Na 05 a 127 V o pico medido (0,954 pu) fica 3 % acima do da programada (0,926 pu).
- 18: a continuidade da fase na troca de passo do `LIST:FREQuency`.
- A largura de pulso do PULSe e o instante exato de aplicação (resolução da fonte) não entram.

## Escopo das contagens históricas (P-30)

O agregado reportado de 99 capturas (36 + 36 + 27) não identifica automaticamente o subconjunto chamado de **piloto de 63 capturas** em decisões anteriores. Sem os arquivos das três sessões e a relação de IDs incluídos, não é possível comprovar quais 63 integram esse piloto. Os resultados acima são relato histórico, não uma reanálise realizada neste checkout. P-30 permanece aberta até produzir tabela por sessão/ID/condição e critério de inclusão, preservando os registros anteriores.

> **Retificação (21/10/2026, P-30).** As sessões de 07/10 não podem ser recuperadas. As contagens de 63 ("piloto") e 99 (36 + 36 + 27) ficam registradas como **históricas e não verificáveis**. Nenhum resultado científico do projeto depende delas; a validação física vem das sessões da campanha v1.15 (P-01). O texto acima é preservado como registro.
