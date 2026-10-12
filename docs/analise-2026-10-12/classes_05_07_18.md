# Classes 05, 07 e 18 alinhadas à fonte e à norma (2026-10-12, v1.15)

Regra de versão (decidida aqui): as três mudanças valem com o **sorteio ligado** (`set sorteio on`, padrão). Com `set sorteio off` (`SORTEIO=0`) o `gerar()` das 05, 07, 17 e 18 continua reproduzindo 34a0d82 byte a byte. Como em `experimentos_waveform/08.py`, o sorteio é a chave da "versão nova"; o fixture `gerar_sorteio_v1_15.json` é o congelamento dela (a versão é a mesma, não houve release entre as specs). Autorização do dono (2026-10-12) de mudar o `gerar()` nesta spec: enunciado da spec.

## 1. Classe 05 (HARMONICS): CSINe no modelo

**Feito.** `experimentos_nativos/05.py:48-51`: com sorteio ligado e `usar_trace(capture_index)` falso (THD <= `TETO_CSINE` = 20 %, `05.py:24`), `gerar()` devolve `sinais.senoide_clipada_pu(t, f0, sorteio.deslocamento_s, thd)`, a função que a spec de diagnóstico já tinha (`logica/sinais.py:424`, corte em `:407`). Não foi criada função nova. Níveis acima do teto (30 % da literatura) seguem a soma de harmônicas 3/5/7 (`05.py:52-60`), a mesma forma que o caminho TRACe envia. `configurar()` e `usar_trace()` não mudaram: o que a fonte recebe é igual; só o modelo passou a descrever o que ela faz. Fase: `deslocamento_s` sorteado, o mesmo `tau` que `forma_programada_nativa` usa (`sinais.py:~441`), então modelo e forma programada do CSINe são a mesma onda (teste `test_05_modelo_e_forma_programada_do_csine_sao_a_mesma_forma`).

**THD do modelo contra a pedida** (script `scratchpad/spec08/medidas.py`, `sinais.thd_medida`, seed 1, 60 Hz, 6000 pontos):

| THD pedido | THD do modelo (CSINe) | rms (pu do pico base) | pico (pu) | modelo antigo: rms / pico |
|---|---|---|---|---|
| 2 % (norma) | 0,0200 | 0,7071 | 0,962 | 0,7072 / 0,988 |
| 5 % | 0,0500 | 0,7071 | 0,926 | 0,7080 / 0,971 |
| 10 % | 0,1000 | 0,7071 | 0,881 | 0,7106 / 0,941 |
| 15 % | 0,1500 | 0,7071 | 0,846 | 0,7150 / 0,912 |
| 20 % | 0,2000 | 0,7071 | 0,817 | 0,7211 / 0,882 |
| 30 % (TRACe) | 0,3000 | 0,7382 | 0,825 | igual (não mudou) |

- Diferença de significado (**baixa**): a soma antiga mantinha a fundamental em 1 pu, portanto o rms subia até 0,721 (+2 % a 20 %); o CSINe real e a TRACe de usuário são escalados para o rms programado (a normalização por rms é obrigatória, diagnóstico da correlação: sem ela 0,62-0,67). Isso só vale para a TRACe pelo manual; para a CSINusoid interna o rms mantido é **NÃO VERIFICADO** (docstring de `senoide_clipada_pu`, `sinais.py:425-428`).
- O nível de 30 % (TRACe) tem rms 0,738 no modelo, porque a soma de harmônicas mantém a fundamental em 1 pu; não foi tocado (**baixa**, fora do pedido). Se `montar_programacao` renormaliza o rms ao programar a TRACe, a forma enviada difere do modelo: NÃO VERIFICADO.
- Relatório de limites: pico programado de 05 desce de 174,3 para 166,3 V (127 V/50 e 60 Hz); extremo previsto de 191,9/191,7 para 183,1/182,9 V. Continua cabendo.
- Testes: `test_05_modelo_dos_niveis_csine_tem_o_thd_e_o_rms_pedidos` (literatura e norma, 60 e 50 Hz, 5 seeds por nível: THD a 0,003, rms a 0,003, pico <= 1), `..._nivel_por_trace_continua_sendo_a_soma_de_harmonicas`, `..._sem_sorteio_todos_os_niveis_seguem_a_soma_de_harmonicas`.

## 2. Classe 07 (NOTCH) e avaliação da 17

**Feito na 07.** IEEE 1159-2019 4.4.5.4 (citado na spec): notching periódico e contínuo. `sinais.aplicar_entalhes_continuos` (`sinais.py:92`, nova; `aplicar_entalhes` ficou intacta para o sorteio desligado) aplica a mesma regra de antes (2 a 4 pulsos de 0,1 ms por ciclo, nos dois picos, jitter +-0,35 ms) em **todos** os ciclos da janela, com grade ancorada nos cruzamentos por zero da senoide sorteada (`origem = -tau`): os entalhes seguem nos picos qualquer que seja a fase. Pulsos cujo centro cai fora da janela são descartados com o `rng` consumido igual; a função antiga, com `inicio_s` fora da janela, zeraria a amostra mais próxima da borda.

`experimentos_waveform/07.py:16-35`: com sorteio ligado chama `self.sortear(rng, f0)` **sem** início/duração: a 07 deixa de ter evento localizado, então sai de `inicio_disturbio_s`/`duracao_s` do metadata e sorteia só a fase, como 06, 15 e 20. Isso muda o que a spec do sorteio pedia (fase acoplada ao início nas 07 e 17): na 07 o acoplamento perdeu o sentido (nada começa em `t0`); a invariante que ele garantia ("entalhes nos picos") continua, agora pela grade da fase. **Gravidade média**: consumidores de `inicio_disturbio_s` não veem mais a 07. Conferi `mestre.py:2744` (só o caminho nativo reposiciona o pré-trigger com ele) e `analisar_sessao._reconstruir_esperado` (chama `gerar()` e vem com a flag `sorteio_posicao` do metadata): sem uso para a 07. `sorteio_posicao` ausente (sessões de 07/10) continua reconstruindo com a janela antiga.

Pulsos por captura (200 seeds): 07 a 60 Hz de 15,1 (11-19) para 36,0 (28-43); a 50 Hz de 12,2 para 30,0. Teste `test_07_tem_entalhes_em_todos_os_ciclos_da_janela_nos_picos_da_senoide` (60 e 50 Hz, 20 seeds: todo pico de todo ciclo inteiro da janela tem amostra zerada a até 0,7 ms) e `test_aplicar_entalhes_continuos_descarta_pulso_com_centro_fora_da_janela`.

**A 17: segue a mesma regra, com o início da oscilação preservado.** Justificativa: a 17 é "NOTCH + OSCILLATORY_TRANSIENT"; o notching da composição é o mesmo fenômeno da 07 e a norma o define como contínuo, então o componente de entalhe deve ser contínuo; a oscilação amortecida é um transitório e permanece localizada em `t0` (`inicio_disturbio_s`, `duracao_s` = 60 ms, fase acoplada a `t0`, como pedia a spec do sorteio). `experimentos_waveform/17.py:18-40`: a grade de entalhes usa `origem = -deslocamento_s`, que como a fase é acoplada coincide com `t0` módulo T. Os entalhes (aplicados antes da soma da oscilação, ordem original) agora cobrem os 12/10 ciclos; pulsos médios de 12,2 para 35,9 (60 Hz) e de 9,2 para 30,1 (50 Hz). Teste `test_17_tem_entalhes_continuos_e_a_oscilacao_localizada_em_t0`.

**Efeitos (NÃO VERIFICADO no hardware, severidade média):** (a) os fatores de extremo de 07 (1,180) e 17 (1,017) em `calibracao_extremos.json` foram medidos com a forma de 4 ciclos; com 10 a 12 ciclos entalhados o sobressinal da fonte por entalhe pode ser diferente (a previsão de extremo por captura não muda no relatório porque usa o pico programado, que continua 1 pu). A verificação pós-captura de VMAX/VMIN segue valendo. (b) A validação física compara envelope e THD do esperado com o medido; o THD esperado da 07 agora é bem maior (mais entalhes) e a tolerância não foi ajustada. (c) Uma TRACe de 6000 pontos com ~36 degraus de 3 amostras: a fonte filtra pulsos de 0,1 ms? (a 08 mostrou que o impulso de 66 µs sai filtrado, `CHANGELOG/v1.15.md`, seção da 08). Pode atenuar os entalhes; o mesmo ocorria nos 15 de antes.

## 3. Classe 18 (FREQUENCY_DRIFT): f0-3 até f0+3

**Feito.** `experimentos_nativos/18.py:21-30` (`extremos_hz`): com sorteio ligado, `(f0-3, f0+3)` nas capturas pares e o inverso nas ímpares; desligado, 57/63 de antes. `gerar()` (`18.py:32`) usa `f0` recebido; `configurar()` (`18.py:45`) usa `config.grid_frequency_hz` e a mesma função, então `frequency_drift_list` recebe exatamente `start_hz`/`end_hz` registrados por `gerar()` (teste `test_18_configurar_envia_os_mesmos_extremos_que_gerar_registra`, 2 flags x 2 frequências x 2 índices, com `mock`). A 60 Hz o resultado é idêntico ao de antes (57/63; as 10 entradas `18/60` do fixture não mudaram). A 50 Hz: 47 -> 53 Hz, 10 ciclos em 0,2 s (antes 12, "senoide de quase 60 Hz"; teste `test_18_a_50_hz_nao_vira_uma_senoide_de_60`).

- Pedido ligeiramente discutível, **baixa**: usar a flag `sorteio_posicao` como chave desta mudança mistura duas coisas (posição/fase e faixa de frequência) na mesma chave; escolhido porque o desligado precisa continuar reproduzindo 34a0d82 e não há outra chave. Se o dono preferir, vira `Config.faixa_frequencia_por_f0` separada.
- Limites da fonte: `frequency_drift_list` exige 45 <= f <= 500 Hz (`ametek_orm.py:1038`); 47 e 53 passam. Nada de validação foi alterado.
- **Restauração da frequência base** (confirmada, não alterada): `configure_safe_baseline` grava `_frequencia_base_hz` (`ametek_orm.py:1263`); `frequency_drift_list` marca `_frequencia_alterada`; `restaurar_frequencia_base` (`ametek_orm.py:1013-1027`) escreve `SOURce:FREQuency <base>` e confere `assert_no_errors`; é chamada por `restaurar_forma_e_modo_padrao()` (`ametek_orm.py:~998-1011`) ao fim de cada classe nativa (`mestre.py:2607`) e na recuperação de estado seguro (`mestre.py:1293`). Teste novo `test_18_a_frequencia_base_e_restaurada_depois_de_47_53` (base 50 Hz, deriva 47 -> 53, `SOURce:FREQuency 50` volta a ser escrito).
- O modelo de `gerar()` continua uma rampa contínua e a fonte faz 2 degraus (`18.py` docstring); a forma programada (`sinais.forma_programada_nativa`) já usa `start_hz`/`end_hz` e acompanha a mudança sem alteração.
- `scripts/preflight_new.py --native-commands` ainda usa 57/63 Hz (`FREQ_DRIFT_START_HZ`/`END_HZ`, testes em `test_offline.py:~895`); é o teste de comando a 5 V, não o dataset; deixado como está (**baixa**).

## 4. Relatório de limites a 127 V

`scripts/relatorio_limites_bancada.py --tensao 127 --frequencia 50` e `--frequencia 60` (perfil literatura, padrão), antes e depois, comparados por `diff` (arquivos em `scratchpad/spec08/antes_*.txt`/`depois_*.txt`):

- Resumo idêntico nas duas: as 20 classes rodam todas as capturas (`05: 1/1`, `07: 3/3`, `17: 3/3`, `18: 1/1`). **Nenhuma das três foi reduzida ou pulada**; coluna "Distúrbio aplicado" 100 % em todas.
- Linhas que mudaram: 05 a 50 Hz pico 174,3 -> 166,3 V, extremo 191,9 -> 183,1 V; a 60 Hz 174,3 -> 166,3 V, 191,7 -> 182,9 V. 17 a 60 Hz, pico 203,0 -> 203,1 V, extremo 230,2/230,3 -> 230,4 V, tela 338 -> 339 V. 07 e 18: sem mudança (pico = 1 pu em ambos). Perfis norma e fronteira a 127 V/50 e 60 Hz: também todas rodam (conferido, só o resumo).
- 220 V não foi pedido e não foi rodado.

## 5. Fixtures, formas distintas e testes

- `gerar_literatura_34a0d82.json`: **intacto**; `test_literatura_reproduz_byte_a_byte_...` passa e o teste novo `test_05_07_17_18_sem_sorteio_reproduzem_34a0d82` o repete para as 80 entradas dessas quatro classes.
- `gerar_sorteio_v1_15.json`: regravadas **66 entradas** (script `scratchpad/spec08/regrava.py`, chave a chave): `05/60` e `05/50` (índices 0 a 3 x 2 seeds; o índice 4, 30 %, igual), `07/60`, `07/50`, `17/60`, `17/50` (10 cada) e `18/50` (10). As 334 restantes iguais, incluindo `18/60`. Campo `versao` atualizado. Cuidado de método: o primeiro regravador trocava por valor de hash e alterou as `18/60` (a 18 não depende de f0 no hash antigo, então 50 e 60 Hz tinham hashes iguais); refeito por chave e conferido (segunda rodada: zero diferenças).
- Teste de formas distintas (`ParametrosSorteadosNasCompostasTests.test_toda_classe_tem_formas_distintas_suficientes_em_todos_os_perfis`): sem alteração necessária, passa. Formas distintas em N = 100: 05, 07 e 17 = 100 nos 3 perfis a 60 e 50 Hz; 18 = 99 (colisão da grade de fase de 0,1 grau, igual a antes). Testes antigos ajustados: `COM_INICIO` sem a 07; o teste de fase acoplada ao início ficou só para a 17.
- `python -m unittest tests.test_offline`: **Ran 343 tests ... OK** (329 antes + 14 novos).

## NÃO VERIFICADO

- Hardware: que a CSINusoid da MX30 preserve o rms programado (o modelo agora assume), que a 07/17 com ~36 entalhes seja reproduzida sem atenuar os pulsos de 0,1 ms, o sobressinal por entalhe com 10 a 12 ciclos (fatores 1,180 e 1,017 calibrados com 4), a continuidade de fase em 47 -> 53 Hz (o número de gravações de TRACe das 07/17 não mudou).
- 220 V e 380 V (relatório não rodado).
- Tolerância da validação física com a 07 de 36 entalhes: não testada contra medida real.
