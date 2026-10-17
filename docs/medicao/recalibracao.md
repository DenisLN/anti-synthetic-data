# Recalibração passo a passo

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` {bdg-success}`VERIFICADO NA BANCADA` (fatores medidos em 30/09 e 07/10/2026) {bdg-danger}`PENDENTE P-07` {bdg-danger}`PENDENTE P-21`

**Pergunta:** o que é o fator de extremo, por que ele existe e como se recalibra? **Resposta:** o **fator de extremo** de uma classe é o maior extremo (`|VMAX|` ou `|VMIN|`) que o osciloscópio mediu na saída da fonte dividido pelo pico que o código programou, medido por classe e por condição de bancada (tensão e frequência); ele existe porque a saída da fonte **oscila** depois de degraus rápidos e passa do pico programado em até 46 %, e o código precisa prever isso **antes** de energizar. Recalibrar é recalcular esses fatores a partir do metadata de uma sessão de bancada com `scripts/recalibrar_extremos.py` (à mão) ou com `set recalibracao on` (ao fim do run, em modo que nunca diminui um fator), conferir o `git diff` e commitar.

Esta página constrói em cima de {doc}`../limites_e_calibracao` (limites, pré-validação, estrutura do arquivo) e de {doc}`../quirks` (A20, B7). A seção "Recalibração automática" de {doc}`../operacao` descreve os ganchos do fim do run; aqui está o procedimento inteiro em uma ordem só.

## 1. Por que existe: o caso da classe 17 a 230 V/50 Hz

**Em 07/10/2026 a pré-validação previu 405 V e a saída chegou a 444 V, acima dos 425 Vp do hardware.** A pré-validação usava a tabela medida a 127 V/60 Hz, em que a classe 17 (NOTCH_OSCILLATORY_TRANSIENT) tinha fator 1,031. A sessão `sessao_2026-10-07_15-15-25` (230 V/50 Hz, 14 de 20 classes) mediu 444 V na 17 e 376 V na 08, esta acima do teto de 374,2 V (`CHANGELOG/v1.14.md`, tabela de sessões). A conta que reproduz os dois números:

$$
\underbrace{405\ \text{V}}_{\text{previsto}} = \underbrace{357\ \text{V}}_{\text{pico programado}} \times \underbrace{1{,}031}_{\text{fator a 127 V/60 Hz}} \times \underbrace{1{,}10}_{\text{margem}},
\qquad
\frac{444\ \text{V}}{357\ \text{V}} \approx 1{,}24
$$

O pico programado de 357 V não consta do changelog: é reconstruído aqui como `405 ÷ (1,031 × 1,10)` {bdg-warning}`NÃO VERIFICADO` (a sessão não existe mais em `resultados/`). O fator 1,24 coincide com o `1.242` que `calibracao_extremos.json` guarda hoje para a classe 17 em `230V_50Hz`.

A causa física é o toque da saída: depois de um degrau rápido a saída oscila a 7,5 a 10 kHz e morre em menos de 0,5 ms, com sobressinal de 0,38 (60 Hz) a 0,457 (50 Hz) do degrau e subsinal de 0,55 a 0,58 (quirk A20, `CHANGELOG/v1.12.md` e `v1.14.md`). **A resposta depende da frequência, não da tensão.** Cronologia do que o código fez com isso:

1. **v1.12.** A pré-validação passa a prever o extremo por `pico × fator × margem`, com fatores medidos em 30/09/2026 a 127 V/60 Hz (a 16 mediu 262 V com 180 V programados).
2. **v1.13.** Limite de bancada: se o extremo previsto passa do teto, a captura física reduz só o distúrbio (`forma = senoide + k·(gerar() − senoide)`).
3. **v1.14.** Uma tabela por condição; condição sem tabela usa previsão conservadora. Capturas reduzidas passam a entrar na recalibração, invertendo a fórmula do limite de bancada.
4. **v1.15.** A previsão usa só as tabelas de **mesma frequência**; os mesmos fatores passam a servir à validação física da crista (`sinais.comparar_fisicamente`, parâmetro `fator_crista`); recalibração ao fim do run (`set recalibracao on`).

## 2. Como o fator é medido

O fator de uma captura é

$$
f_c=\frac{\max\big(\lvert V_\text{max}\rvert,\ \lvert V_\text{min}\rvert\big)}{V_\text{pico,prog}},
\qquad
V_\text{pico,prog}=\max\!\big(\max\lvert\text{forma prevista}\rvert\cdot\sqrt2\,V_\text{base},\ V_\text{rms,prog}\sqrt2\big)
$$

com $V_\text{max}$ e $V_\text{min}$ os valores de `:MEASure:VMAX?` e `:MEASure:VMIN?` ({scpik}`:MEASure:VMAX?`, {scpik}`:MEASure:VMIN?`), medidos pelo osciloscópio no registro bruto (a amostra a 30 kSa/s subestima picos estreitos, K7), gravados no metadata como `pico_medido_v` e `vale_medido_v`; e o pico programado a definição de `ExperimentoBase._pico_da_forma_v` / `pico_programado_v` (`logica/mestre.py`; **mudar essa definição obriga a recalibrar**). O fator proposto por classe é o **maior** medido nas sessões dadas. Regras (`scripts/recalibrar_extremos.py`, `coletar`):

- **Captura com distúrbio reduzido** (limite de bancada, `fator_disturbio_bancada = k`) entra invertendo a fórmula da previsão (`mestre.extremo_previsto_com_disturbio_v`, sem margem): $f = f_\text{ref} + \dfrac{V_\text{ext} - f_\text{ref}\,V_\text{pico}}{k\,V_\text{pico,modelo}}$, com $f_\text{ref}$ o fator da classe 01 **na mesma condição**; vale o maior entre esse valor e $V_\text{ext}/V_\text{pico}$ (conservador). Sem isso, numa condição alta quase toda classe roda reduzida e não haveria como calibrá-la.
- **Ficam de fora:** a 08 (modelo próprio do impulso, `SOBRESSINAL_DO_DEGRAU` e `SUBSINAL_DO_DEGRAU`), capturas reduzidas sem a 01 como referência, capturas sem VMAX/VMIN (`extremos_indisponiveis`) e simuladas; o relatório conta cada tipo.
- **Sessões antigas** sem `pico_programado_v` têm o pico reconstruído pelo código atual da classe com a `seed` e o `nivel_indice` gravados.
- **Fator abaixo de 1 vira 1** no uso (`fator_extremo_da_classe`): nunca se prevê extremo menor que o programado. A tabela guarda o medido, inclusive 0,977 (classe 14 a 127 V/60 Hz).

## 3. Estrutura de `calibracao_extremos.json`

```json
{
  "descricao": "...", "condicao_sem_calibracao": "...",
  "por_condicao": {
    "127V_60Hz": {"tensao_rms": 127.0, "frequencia_hz": 60.0, "origem": "...", "fatores": {"01": 1.063, "02": 1.164, "...": "..."}},
    "230V_50Hz": {"tensao_rms": 230.0, "frequencia_hz": 50.0, "origem": "...", "fatores": {"...": "..."}},
    "127V_50Hz": {"tensao_rms": 127.0, "frequencia_hz": 50.0, "origem": "...", "fatores": {"...": "..."}}
  },
  "observacao_08": "...", "uso_limite_bancada": "..."
}
```

A chave da condição é `chave_condicao(tensão, frequência)` = `"127V_60Hz"` (`mestre.py`). Hoje há três tabelas (`127V_60Hz`, `230V_50Hz`, `127V_50Hz`); a 16 não tem fator a 230 V/50 Hz e a 02, 03, 04 também não. `carregar_calibracao_extremos` **levanta** se o arquivo falta, está ilegível ou tem fator inválido (zero, negativo, infinito): sem ele a pré-validação de pico não tem base, e seguir sem ela seria enfraquecer a proteção em silêncio. O arquivo é lido **a cada avaliação** (`ExperimentoBase._fatores_extremo` → `carregar_fatores_extremo`): uma recalibração vale já para o `run` seguinte, sem reiniciar a CLI; a sessão guarda uma cópia (`calibracao_extremos.json` na pasta, `preparar_pasta_da_sessao`) e o SHA-256 em `sessao.json` e em cada captura (`calibracao_extremos_sha256`).

## 4. A regra por frequência e a condição sem tabela

`carregar_fatores_extremo(tensão, frequência)` decide quais fatores a bateria usa:

```{mermaid}
flowchart TD
    A["condição da bateria<br/>(V, f)"] --> B{"alguma tabela com V ±2 %<br/>e f ±0,5 Hz?"}
    B -->|sim: calibrada| C["entram só as tabelas de MESMA frequência<br/>(qualquer tensão)"]
    C --> D["cada classe usa o MAIOR fator dela<br/>nessas tabelas"]
    D --> E{"classe sem medida<br/>nessas tabelas?"}
    E -->|sim| F["usa o maior fator de todas as tabelas"]
    B -->|não: sem tabela| G["toda classe usa o MAIOR fator já medido<br/>(1,475 hoje)"]
    G --> H["exceto a 01: maior fator da 01<br/>(1,063 hoje) + aviso no log"]
```

Executado offline em 2026-10-16 (função `mestre.carregar_fatores_extremo`, `main` em `fa82f49`):

```text
127 V/60 Hz  tabela própria=127V_60Hz  01=1.063  03=1.058  07=1.186  16=1.475  17=1.031
127 V/50 Hz  tabela própria=127V_50Hz  01=1.063  03=1.058  07=1.375  16=1.030  17=1.307
230 V/50 Hz  tabela própria=230V_50Hz  01=1.063  03=1.058  07=1.375  16=1.030  17=1.307
220 V/60 Hz  tabela própria=None       01=1.063  03=1.475  07=1.475  16=1.475  17=1.475
127 V/55 Hz  tabela própria=None       01=1.063  03=1.475  07=1.475  16=1.475  17=1.475
```

Duas leituras. **A 230 V/50 Hz o fator efetivo da 17 é 1,307**, o maior das tabelas de 50 Hz (a de 127 V/50 Hz), e não os 1,242 da tabela de 230 V: a regra por frequência é a que impede repetir o erro de 07/10. **A 220 V/60 Hz e a 127 V/55 Hz não têm tabela**: toda classe, menos a 01, usa 1,475 (o fator da classe 16 a 127 V/60 Hz), então várias classes são puladas ou reduzidas; é a previsão conservadora. A 03 a 230 V/50 Hz continua fora por ser inviável pelo teto: $357{,}8\ \text{V}\times 1{,}058\times 1{,}10 = 416{,}4\ \text{V} > 415{,}8\ \text{V}$ (`scripts/relatorio_limites_bancada.py --tensao 230 --frequencia 50`; decisão de projeto registrada em `CHANGELOG/v1.15.md`). {bdg-danger}`PENDENTE P-21`: calibrar a condição antes de coletar nela.

## 5. Onde o fator é usado

1. **Pré-validação de pico (antes de qualquer SCPI).** `avaliar_captura_na_bancada` calcula o extremo previsto $V_\text{ext}^\text{prev}=V_\text{pico,prog}\times f_c\times 1{,}10$ (`MARGEM_FATOR_EXTREMO`) e pula a captura que passa do teto (`max_peak_v`, 415,8 V; 0,9 × na 08, que tem modelo próprio, `excursao_fisica_prevista_v`). Se nenhuma captura da classe cabe: `ParameterOutOfBoundsError`.
2. **Limite de bancada por bisseção (classes de forma de onda).** Se o previsto passa do teto, a captura física reduz só o distúrbio a uma fração $k$ pela bisseção do maior $k$ que cabe, com $V_\text{ext}^\text{prev}=1{,}10\,[f_\text{ref}V_\text{pico}+k\,(f-f_\text{ref})V_\text{pico,modelo}]$ (`extremo_previsto_com_disturbio_v`); abaixo de `LIMITE_BANCADA_FRACAO_MINIMA` (0,25) a captura é pulada. O dataset simulado e `gerar()` não mudam.
3. **Crista da validação física.** `fator_extremo_efetivo_para_validacao` devolve o mesmo fator, **sem** a margem 1,10 (a folga é a tolerância de 10 % da crista), e `sinais.comparar_fisicamente(..., fator_crista=)` aceita a crista medida em $[\,c_\text{modelo}\,(1-0{,}10),\ c_\text{modelo}\,f\,(1+0{,}10)\,]$, bilateral porque a fonte pode tocar menos que o máximo calibrado. Um fator calibrado baixo demais (07 e 17 a 127 V/60 Hz: 1,186 e 1,031) reprova a captura pela crista: esse é o sintoma que manda recalibrar (P-07).

Depois de cada captura física o extremo **medido** é conferido contra o mesmo teto (`_conferir_extremos_fisicos`): acima dele, `PicoFisicoExcedidoError` **depois** de gravar a captura (é a evidência), a classe para sem retry e o operador confere o painel.

## 6. O ciclo, num fluxograma

```{mermaid}
flowchart TD
    P["pré-validação<br/>pico × fator × 1,10 ≤ teto?"] -->|não| S["pula ou reduz o distúrbio<br/>(limite de bancada)"]
    P -->|sim| G["programar<br/>program_capture / trigger_step"]
    S --> G
    G --> M["medir<br/>:MEASURE:VMAX? e :VMIN? (osciloscópio)"]
    M --> V["validar<br/>extremo medido ≤ teto?<br/>crista dentro de c × [0,9 ; f × 1,1]?"]
    V -->|"extremo > teto"| X["PicoFisicoExcedidoError<br/>captura gravada, classe para"]
    V -->|"crista reprovada"| R["recalibrar"]
    V -->|ok| F["próxima captura"]
    R --> J["recalibrar_extremos.py [--gravar]<br/>ou set recalibracao on (fim do run)"]
    J --> D["git diff, tests.test_offline, commit"]
    D --> P
```

## 7. Procedimento passo a passo

**Antes**

1. Árvore limpa: `git status`. Toda sessão de coleta sai de commit limpo (o metadata grava `git_commit`, `git_sujo` e a cópia da calibração).
2. `python -m unittest tests.test_offline` verde (P-16 trata da execução no PC da bancada).
3. Decidir o modo: **à mão** (script, mostra a tabela e permite criar tabela de condição nova) ou **automático** (`set recalibracao on` na CLI; só em bancada; nunca diminui; nunca cria tabela).

**Durante**

4. Rodar a bateria na condição (`run all` ou a lista de classes; o aviso "condição sem tabela" é esperado se a condição é nova).
5. Se o modo automático estava ligado, o fim do run imprime `RECALIBRAÇÃO AUTOMÁTICA: N fator(es) ... MUDARAM` e, por fator, `[tabela] classe NN: antes -> depois (n captura(s))` (`SessaoCLI._recalibrar_ao_fim`, [cli.py:895](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L895)). Só roda se a classe/bateria terminou sem falha de infraestrutura e se a cópia da calibração existe na sessão.

**À mão (offline, sem energizar nada)**

6. Ver o que mudaria: `python scripts\recalibrar_extremos.py resultados\sessao_A [resultados\sessao_B ...]`. Colunas: `Classe`, `Capturas`, `Fator mín.`, `Mediana`, `Máx. (proposto)`, `Atual`, `Gravaria`.
7. Gravar: acrescentar `--gravar`. Nenhum fator diminui (vale o maior entre o atual e o medido). `--substituir` (só com `--gravar`) deixa gravar fator **menor** e **enfraquece a pré-validação**: não é o caminho normal. `--arquivo F` grava em outro arquivo (útil para ensaiar).

**Depois**

8. `git diff logica/calibracao_extremos.json`: ler cada fator que mudou; um fator que sobe muito deve ter uma captura que o explique. Rodar `tests.test_offline`. Commitar (a calibração faz parte do estado do código: o próximo `git_sujo` a acusaria).
9. Conferir o efeito: `python scripts\relatorio_limites_bancada.py --tensao 127 --frequencia 60 [--perfil ...]` mostra, sem hardware, quais capturas cabem com os fatores novos.

**Como reverter**

10. A cópia da calibração do início da sessão está em `resultados\sessao_<timestamp>\calibracao_extremos.json` (SHA-256 em `sessao.json`). Reverter é copiar de volta (`copy ... logica\calibracao_extremos.json`) ou, se o arquivo já estava commitado antes, `git checkout -- logica/calibracao_extremos.json`. O próximo `run` já lê o arquivo restaurado (seção 3). Reverter **enfraquece** a pré-validação se o fator revertido era maior: reverter só com um motivo.

**Condição nova (tensão ou frequência fora de todas as tabelas)**

11. Rodar a bateria na condição (a previsão conservadora pula ou reduz várias classes, o que é esperado), depois `recalibrar_extremos.py <sessao> --gravar` à mão: o modo automático **não cria** tabela para condição nova, porque uma tabela criada de uma sessão só trocaria o fator conservador por um medido uma vez. Reconferir com `relatorio_limites_bancada.py`.

**Quando a primeira rodada da v1.15 reprova só por "fator de crista"** (07 e 17; P-07)

12. É esperado: o toque simulado nos entalhes (crista ≥ 1,344 e ≥ 1,420 nas formas da v1.15) passa do que os fatores de 127 V/60 Hz cobrem. Rodar com `set recalibracao on`, ler o `git diff` e commitar; o fator novo vale para o **run seguinte**, não para o que o gerou. Não afrouxar a tolerância da crista: a decisão de 2026-10-13 foi usar a calibração, não relaxar o critério.

## 8. Exemplos executados offline

Todos com o Python do projeto, a partir da raiz do repositório, sem hardware, **sem tocar `logica/calibracao_extremos.json`** (`--arquivo` aponta para uma cópia). Datas: 2026-10-16.

### 8.1 Sessão fixture do repositório, condição sem tabela, com `--gravar` numa cópia

```powershell
# copia do JSON só com a tabela 230V_50Hz (a 127V_60Hz "não existe" ainda)
python scripts\recalibrar_extremos.py tests\fixtures\sessao_2026-09-30_15-26-05 --arquivo copia.json
```

```text
## 127V_60Hz -> tabela 127V_60Hz (NOVA)
| Classe | Capturas | Fator mín. | Mediana | Máx. (proposto) | Atual | Gravaria |
|---|---|---|---|---|---|---|
| 01 | 1 | 1.063 | 1.063 | 1.063 | — | 1.063 |
| 07 | 1 | 1.180 | 1.180 | 1.180 | — | 1.180 |
| 10 | 1 | 1.236 | 1.236 | 1.236 | — | 1.236 |
| 16 | 1 | 1.459 | 1.459 | 1.459 | — | 1.459 |
| 17 | 1 | 1.017 | 1.017 | 1.017 | — | 1.017 |
...
Ignoradas: 08 (modelo próprio): 1, reduzida sem referência 01: 0, sem VMAX/VMIN: 0, simulada: 0
Nada gravado (use --gravar).
```

(linhas 02 a 20 omitidas; a saída completa tem 19 classes.) Com `--gravar` na cópia: tabelas antes `['230V_50Hz']`, depois `['230V_50Hz', '127V_60Hz']`; `origem` da nova tabela `scripts/recalibrar_extremos.py sobre: tests\fixtures\sessao_2026-09-30_15-26-05 (nenhum fator diminuiu)`. A fixture é a sessão de 30/09/2026 (1 captura por classe, 127 V/60 Hz); o fator da 16 que ela dá (1,459) é o de onde vem o 1,475 do arquivo real (outra sessão deu o maior valor).

### 8.2 Sessão de bancada de 07/10 a 230 V/50 Hz, antes de existir a tabela

Cópia do JSON só com `127V_60Hz` (o estado de antes de 07/10):

```powershell
python scripts\recalibrar_extremos.py resultados\sessao_2026-10-07_230V_50Hz --arquivo copia_so_127V_60Hz.json
```

```text
## 230V_50Hz -> tabela 230V_50Hz (NOVA)
| Classe | Capturas | Fator mín. | Mediana | Máx. (proposto) | Atual | Gravaria |
| 01 | 1 | 1.030 | 1.030 | 1.030 | — | 1.030 |
| 07 | 3 | 1.290 | 1.321 | 1.321 | — | 1.321 |
| 17 | 3 | 1.111 | 1.111 | 1.322 | — | 1.322 |
| 19 | 3 | 0.966 | 0.971 | 0.972 | — | 0.972 |
```

A 17, que a tabela de 127 V/60 Hz dava como 1,031, sai com **1,322** (as três capturas dessa sessão rodaram reduzidas a k = 0,37 pelo limite de bancada; a fórmula invertida reconstrói o fator do distúrbio inteiro, com mínimo 1,111 e máximo 1,322).

### 8.3 As três sessões de 07/10 contra o arquivo real (só leitura)

```powershell
python scripts\recalibrar_extremos.py resultados\sessao_2026-10-07_127V_50Hz resultados\sessao_2026-10-07_14-59-54_run02 resultados\sessao_2026-10-07_230V_50Hz
```

Saída resumida: todas as linhas da tabela `Gravaria` coincidem com `Atual`, **exceto três fatores da tabela `230V_50Hz`**: 07 (1,317 para 1,321), 11 (1,030 para 1,060) e 17 (1,242 para 1,322). Nada foi gravado. **Achado:** o arquivo versionado não incorpora essa sessão completa; a diferença é pequena para 07 e 11 e relevante para a 17, mas o fator **efetivo** a 230 V/50 Hz já é 1,307 (seção 4), porque a regra por frequência usa o maior das tabelas de 50 Hz. Decisão de gravar ou não: do responsável pelo projeto.

## 9. O que não está verificado

- **Sessões de 07/10 com a validação de crista da v1.15** {bdg-warning}`NÃO VERIFICADO`: o critério com `fator_crista` nunca rodou na bancada (P-01, P-07).
- **Tabelas para 220 V e para 60 Hz fora de 127 V** não existem (P-21).
- **`pico programado` de 357 V** da seção 1 é reconstruído, não lido de um metadata.
- **Efeito de `set recalibracao on` num `run all` real**: o modo automático foi lido no código e testado offline com fixtures; não foi executado numa bateria física com o código atual.
