# Verificação de k=1 a 127 V (relatório offline de limites)

Data: 2026-10-12. Commit base 63412bd. Somente leitura, sem hardware. Seed base 20260827 (padrão), limite de bancada ligado (fração mínima 0,25), teto 415,8 Vp / 300 Vrms.
Brutos (um arquivo por execução): `...\scratchpad\spec14\s{1,0}_{perfil}_{freq}_{capturas}.txt` (s1 = SORTEIO padrão ligado; s0 = `SORTEIO=0`).

Observação sobre o pedido: o relatório não diz k diretamente; a coluna "Distúrbio aplicado" é k arredondado a 0%. Por isso as capturas com parâmetros `*_bancada` na coluna "Motivo / parâmetros" também contam como k<1 (ver item 2).

## 1. Execuções

```
SORTEIO=1|0 .\env\Scripts\python.exe scripts\relatorio_limites_bancada.py --tensao 127 --frequencia {60|50} --capturas {5|50} --perfil {norma|literatura|fronteira}
```

24 execuções com o padrão (SORTEIO ligado) mais 24 com `SORTEIO=0`: 3 perfis × 2 frequências × 2 valores de capturas. Todas terminaram sem erro. Linhas de captura por execução (padrão das classes mais `--capturas`): norma e literatura 160 (5) / 1600 (50); fronteira 130 / 1300.

O sorteio não muda nada: a saída com `SORTEIO=0` é byte a byte igual à padrão nas 12 combinações (`diff` vazio). O relatório não usa o início/fase sorteados na previsão do pico. NÃO VERIFICADO: se o pico real da forma de onda gerada com início/fase sorteados fica sempre dentro do extremo previsto; isso depende do `gerar()` e só a bateria física ou outra checagem o confirma.

## 2. Capturas com k<1 ou puladas

Puladas ("Cabe? = NÃO"): zero, em todas as 24 execuções (`grep -c '| NÃO |'` = 0).

Distúrbio reduzido (k<1): só uma classe, a 14 (SWELL_OSCILLATORY_TRANSIENT), só no perfil fronteira, 127 V/50 Hz, com 50 capturas. Duas capturas, iguais com e sem sorteio:

| Perfil | Condição | Classe | Captura (índice) | Pico prog. / extremo prev. / teto (V) | k mostrado | Parâmetros dados pelo relatório |
|---|---|---|---|---|---|---|
| fronteira | 127 V/50 Hz, 50 capt. | 14 | 12 (11) | 370,2 / 415,8 / 415,8 | 100% (k<1 por arredondamento) | swell_pu_bancada=1.8, oscillation_amplitude_pu_bancada=0.299 |
| fronteira | 127 V/50 Hz, 50 capt. | 14 | 16 (15) | 370,2 / 415,8 / 415,8 | 99% | swell_pu_bancada=1.8, oscillation_amplitude_pu_bancada=0.298 |

Motivo: o extremo previsto (regra por frequência) bateria no teto de 415,8 V; a amplitude da oscilação é reduzida em ~0,3% para caber. Resumo do relatório: `14: 50/50 rodam, 2 com distúrbio reduzido`. A 127 V/60 Hz a mesma classe chega a 98,4% do teto e fica em k=1. Nenhuma captura clipa a tela do CH1 (`CLIPA` = 0).

Margem do extremo previsto sobre o teto (excluída a 08), pior captura, execuções com padrão: norma 0,880-0,913 (14 ou 03), literatura 0,905-0,931, fronteira 0,937-1,000.

## 3. Conclusão por perfil e condição ("127 V ⇒ k=1 em todas as classes exceto a 08")

| Perfil | 127 V/60 Hz | 127 V/50 Hz |
|---|---|---|
| norma | Vale (5 e 50 capturas: 0 puladas, 0 reduzidas) | Vale (idem) |
| literatura | Vale (idem) | Vale (idem) |
| fronteira | Vale (idem; 14 em 98,4% do teto) | Vale com ressalva: com 50 capturas a 14 tem 2 capturas com k=0,998-0,999 (virtualmente 1, mas não exatamente 1); com 5 capturas vale |

Ressalva sobre a afirmação do `atividade.tex` ("k=1 em todos os níveis"): para a fronteira a 50 Hz com muitas capturas, o enunciado é válido só aproximadamente (queda de 0,1% a 0,2% na amplitude de oscilação da 14). Em norma e literatura é exato.

## 4. Classe 08 (à parte)

A 08 tem teto próprio de 374,2 V (nota no `experimentos_waveform/08.py`), não os 415,8 V. Em todas as 24 execuções: 100% de rodam, k=100% e "Cabe? = sim" em todas as capturas; o extremo previsto chega exatamente ao teto próprio na última captura (374,2 V em 5 (4) e 50 (49), tela CH1 ±624 V). Ou seja, roda inteira e com folga zero no teto dela, não é falha nem redução.

## NÃO VERIFICADO

- Pico real das formas geradas com início/fase sorteados (item 1).
- Execução física: o relatório é offline e prevê o extremo; só a bateria na bancada confirma que k=1 resulta em RMS/pico medidos dentro da tolerância.
- Seeds diferentes da base 20260827: só ela foi rodada.
