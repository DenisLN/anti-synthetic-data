# Regra de previsão de extremos por frequência

2026-10-12, proposta 8 / Pergunta 10 (`atividade.tex`, Tabela `tab:pulo230`). Brutos dos relatórios: scratchpad `spec10\antes-*.md` (código de 2abee44) e `spec10\depois-*.md`.

## 1. Regra implementada

`logica/mestre.py`, `carregar_fatores_extremo` (ramo "condição calibrada"):

1. entram só as tabelas com frequência dentro de `TOLERANCIA_CONDICAO_FREQUENCIA_HZ` (0,5 Hz) da condição, qualquer tensão;
2. dentro delas, o maior fator da própria classe;
3. classe sem medida em nenhuma delas: o maior fator de todas as tabelas (regra da v1.14).

Escolha de escopo (gravidade baixa): a regra vale para condição **calibrada** (tensão ±2 %, frequência ±0,5 Hz, `condicao_calibrada`). Condição sem tabela própria (ex.: 220 V/60 Hz) continua toda conservadora, com o aviso; o texto da proposta não diz o que fazer ali e o incidente de 07/10 (17 previu 405 V e mediu 444 V) foi justamente uma condição sem tabela. O teste `test_sem_calibracao_e_conservador_e_avisa_uma_vez` segue como está.

## 2. A 03 a 230 V/50 Hz

Sem exceção no código: a 03 sai pela própria regra. Tabela de 50 Hz → fator 1,058 (127 V/50 Hz); pico programado 357,8 V × 1,058 × 1,10 = 416,4 V > teto 415,8 V (`max_peak_v`, `avaliar_captura_na_bancada`). O motivo agora traz pico e fator (`mestre.py`, `_detalhe_fator_extremo`); o relatório de limites mostra:

`extremo PREVISTO 416.4 V > teto 415.8 V (pico programado × fator medido × margem 1.10: 357.8 V × 1.058)`

Os níveis 1,2 pu ou mais da 03 (454,3 V) também ficam de fora (0/25 rodam). Teste: `test_03_a_230v_50hz_fica_de_fora_pela_margem_sem_excecao`.

## 3. Antes/depois do relatório de limites

Comando: `env\Scripts\python.exe scripts\relatorio_limites_bancada.py --tensao T --frequencia F --capturas 5`, perfil literatura (padrão), com `SORTEIO=0` (equivale à v1.14 da tabela do `atividade.tex`) e com `SORTEIO=1` (padrão atual). Antes = `git archive 2abee44`. Os resultados com sorteio ligado e desligado são idênticos nestas quatro classes (a previsão depende de pico e fator, que o sorteio não mexe).

### 230 V/50 Hz

| Classe | Pico prog. | Antes: previsto, cabe? | Depois: previsto, cabe? | `tab:pulo230` |
|---|---|---|---|---|
| 02 SAG | 325,3 V | 527,7 V (fator 1,475), pula 0/25 | **380,3 V (1,063), cabe 25/25** | 380,3 V, cabe |
| 03 SWELL 1,1 pu | 357,8 V | 580,5 V (1,475), pula 0/25 | **416,4 V (1,058), pula 0/25** | 416,4 V, pula |
| 04 INTERRUPTION | 325,3 V | 527,7 V, pula 0/5 | **380,3 V (1,063), cabe 5/5** | 380,3 V, cabe |
| 16 INT+HARM | 325,3 V | 527,7 V, pula 0/5 | **368,5 V (1,030), cabe 5/5** | 368,5 V, cabe |

Os valores batem com a tabela do `atividade.tex`. (A coluna "Antes" da `tab:pulo230` mostra 527,7 V para 02/04/16 e 580,5 V para a 03, iguais às saídas acima.) Nas linhas de nível mais alto da 03 o previsto sobe a 454,3 V (1,2 pu); antes, 633,3 V.

### 127 V/50 Hz e 127 V/60 Hz

Todas as 20 classes seguem rodando em ambas (nada ficou mais restritivo). O previsto só **desce**, porque o maior fator deixou de vir de outra frequência (máximo por classe, V; sem linha = igual):

| Condição | Classe: antes → depois |
|---|---|
| 127 V/50 Hz | 02: 230,0 → 210,0; 04: 235,5 → 210,0; 10: 245,4 → 203,5; 11: 248,5 → 203,5; 16: 291,4 → 203,5 |
| 127 V/60 Hz | 05: 191,9 → 191,7; 06: 236,6 → 231,5; 07: 271,7 → 234,3; 09: 261,2 → 257,4; 12: 204,7 → 203,5; 13: 307,3 → 298,9; 14: 376,6 → 368,9; 15: 222,0 → 218,4; 17: 292,0 → 230,4; 18: 212,4 → 204,7; 19: 218,8 → 217,3; 20: 243,3 → 239,9 |

Em 230 V/50 Hz as classes 10 e 11 caem de 415,8 V (distúrbio reduzido) para 368,5 V (cabem inteiras); 17 e 07 seguem com os fatores de 50 Hz (1,307/1,375).

## 4. Riscos e achados

- **Média.** Os fatores de 50 Hz da 10 e da 11 (1,03) vêm de 127 V/50 Hz (`calibracao_extremos.json`) e, a 230 V, só rodaram com distúrbio reduzido (limite inferior). A regra antiga os protegia com o 1,242/1,258 de 60 Hz. Se a oscilação a 50 Hz for maior do que o medido, a 230 V o extremo pode passar do previsto; quem protege é a verificação pós-captura de VMAX/VMIN (inalterada). Vale medir 10 e 11 a 230 V/50 Hz sem redução e recalibrar.
- **Baixa.** O campo `condicao_sem_calibracao` de `logica/calibracao_extremos.json` ainda descreve a regra da v1.14 (maior de todas as tabelas). Não foi editado: o arquivo é de valores medidos e está fora do que a spec autoriza. O código e o README descrevem a regra nova.
- **Baixa.** O trecho do `atividade.tex` (Seção `ap:regra`) fala em "classes 02, 04 e 16 a 230 V/50 Hz"; é o que a execução confirma.

## NÃO VERIFICADO

- No hardware: que o sobressinal a 230 V/50 Hz de 02, 04 e 16 fique nos fatores medidos a 127 V/50 Hz (nenhuma captura foi feita; a tabela vem de 127 V). Motivo: sem acesso à bancada nesta tarefa.
- Que 50 Hz continue sem sobressinal em níveis de SAG diferentes dos medidos: os fatores 02/04/16 vêm de uma sessão (`resultados\sessao_2026-10-07_15-56-39`, citada na origem do JSON), não consultada aqui.

## Testes

`env\Scripts\python.exe -m unittest tests.test_offline -v`: `Ran 320 tests ... OK`. Reescritos `test_passo1_e_2_...` e `test_passo3_...`; acrescentado `test_03_a_230v_50hz_...`.
