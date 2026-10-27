# Findings detalhados: pendências P-01 a P-31 (fork rmlinxic/anti-synthetic-data)

Versão expandida de `findings-pendencias-v1-15.md`. Aqui cada pendência tem: o que o inventário pede, o estado segundo o rastreador, o que as evidências mostram, o que falta para fechar e quem decide.

## 0. Contexto do projeto e do fork

**Projeto:** dataset rotulado de 20 classes de distúrbio de tensão, gerado com uma fonte programável AMETEK MX30-3Pi e um osciloscópio Keysight DSO-X 4034A. Há também um simulador que gera o mesmo dataset sem hardware. Versão corrente: **v1.15, em andamento, sem tag**.

**Repositório upstream:** `DenisLN/anti-synthetic-data`. O responsável pelo projeto, que decide as pendências marcadas como DECISÃO DO USUÁRIO, é Denis.

**Fork analisado:** `rmlinxic/anti-synthetic-data`, branch `feat/execucao-pendencias-v1-15`, HEAD `cd1e6a9` (2026-10-22). Foi feito por Ricardo, dupla de TCC do usuário. As sessões físicas de 22/10 foram gravadas no PC da bancada, o Inspiron 15 (`DESKTOP-FSEESJI`), sob o usuário Windows de Ricardo.

**Bancada:** fonte AMETEK em `COM10` a 115200 baud. Osciloscópio `USB0::0x0957::0x17A4::MY59240844::0::INSTR`. AGENTS.md proíbe mudar porta, baud e limites.

**Visita de 22/10:** visita `2026-10-22_13-31-58`, parada no braço A da P-09, OUTPUT OFF conferido pelo operador. Foram 14 sessões físicas (`sessao_2026-10-22_14-10-50` a `15-27-50`).

**Estados possíveis (segundo a execução):** Em implementação; Parcial; Preparada / aguarda bancada; Bloqueada por fonte/dados; Aberta. Simulação não é medição. Software não encerra item físico.

**Símbolos usados no rastreador:** ✅ concluída; 🔧→🏭 software pronto, falta bancada; ❓ falta decisão ou dado do responsável; ⏳ em andamento.

**Ressalvas desta análise:**
- Não executei a suíte de testes. O classificador de permissões bloqueou a execução de código do fork. Afirmações sobre testes são de leitura.
- As sessões físicas não estão no repositório. Conferi somente os SHA-256 listados em `fechamento.json`.
- Não li `CHANGELOG/v1.15.md` inteiro, `mapa/`, nem os branches `arquivo/analises` e `claude/specs-v1-15-review-3w2bgl` (apenas busquei neles).

---

## 1. Placar e como ele se compara às evidências

| Estado no rastreador | Quantidade | IDs |
|---|---|---|
| ✅ Concluídas | 13 | P-03, P-04, P-10, P-11, P-12, P-13, P-14, P-15, P-16, P-24, P-25, P-27, P-30 |
| 🔧→🏭 Software pronto, falta bancada | 11 | P-01, P-02, P-06, P-08, P-09, P-18, P-19, P-21, P-23, P-26, P-29 |
| ❓ Falta decisão ou dado | 7 | P-05, P-07, P-17, P-20, P-22, P-28, P-31 |
| Abertas | 0 | — |

**O que o placar esconde:**
- Dos 11 🔧→🏭, três têm evidência de **reprovação** (P-02, P-08) ou **insuficiência** (P-19). O rótulo "software pronto" não reflete isso.
- Dos 7 ❓, seis têm evidência suficiente que aguarda revisão humana. P-20 aguarda o responsável e não tem evidência de bancada.
- Das 13 ✅, duas (P-16 e P-25) estão erradas, e sete dependem de uma decisão do responsável que não está registrada.

---

## 2. Fontes da verdade e por que há divergência

**Quem é a fonte de quê, segundo a própria documentação:**

| Documento | Papel declarado | Estado real |
|---|---|---|
| `docs/PENDENCIAS_TRACKER.md` | "Fonte única de estado" | Atualizado em 22/10. Placar, matriz, log de rodadas. |
| `docs/execucao_pendencias.md` | "Narrativa e critérios completos" | Cabeçalho de 17/10, matriz com dados de 22/10. |
| `docs/decisoes_pendentes.md` | "Formulário para responder de uma vez" | Respostas de 21/10 para P-09, P-26, P-29, P-30, P-21. Outras em branco. |
| `docs/bancada_pendencias.md` | "Roteiro de fechamento" | 273 linhas. Não lido em detalhe nesta análise. |
| `docs/estado_prontidao.json` | "Estado de máquina" | Binário. |
| `docs/projeto/pendencias.md` | Inventário "histórico" de 16/10 | Duas versões diferentes (feature e RTD). |
| `README.md` "Mapa da documentação" | Índice | Legado: não cita os arquivos de rastreio. |

**Por que as versões divergem:** o inventário foi escrito em 16/10 com os IDs. Depois, a execução e o rastreador passaram a registrar estado, e o branch do site (RTD) ficou com a versão antiga. Ninguém propagou as mudanças para o branch publicado.

---

## 3. Pendências uma a uma

Cada bloco traz: **Pede** (inventário), **Estado** (rastreador), **Evidência** (o que consegui conferir), **Falta** (para fechar) e **Quem decide**.

### P-01 — Campanha v1.15 real por classe, perfil e condição
- **Pede:** nenhum dado de bancada com o código da v1.15 (perfis, sorteio, compostas, entalhes contínuos, classe 08 a 90 ms, crista com fator, cópia em 100 ms). A última campanha é de 07/10. Estimativa do roteiro: 2 h a 3 h para um perfil, 2 h 30 a 3 h 30 com `todos`.
- **Estado:** 🔧→🏭.
- **Evidência:** `fechamento.json` diz `insuficiente`. Condições cobertas: 127 V/50 Hz e 127 V/60 Hz. Faltam 230 V/50 Hz, 220 V/60 Hz e 33 V/60 Hz. O critério "validação física ok em todas" registra 19 casos (ids na nota do JSON) com limite 0. O critério de quantidade de capturas por célula não está definido (159 capturas).
- **Falta:** as três condições restantes, com calibração pronta (ver P-21), e a definição da quantidade mínima por célula.
- **Quem decide:** a campanha é física. A quantidade mínima é decisão do responsável.

### P-02 — Cópia ou deslocamento do evento em 100,0 ms (classes 08 e 09)
- **Pede:** a 08 a 50 Hz saiu em 100 ms em 3/3 capturas. A 09 tem impulso de 0,12–0,27 pu em 100,0–100,2 ms em 9/9. Cinco hipóteses estão em `modelo_lista_fonte.py`, nenhuma confirmada. O que fecha é bancada: marcadores (`diag_marcadores_trace.py`), recuperação da TRACe e recaptura.
- **Estado:** 🔧→🏭, mas a execução diz "Reprovada em 2026-10-22".
- **Evidência:** marcadores 30/30 sem espúrios; recapturas 08/09 presentes a 50 e 60 Hz. A posição da 08 a 127 V/60 Hz desviou −16 amostras, com limite de 10, em uma captura por perfil (`sessao_2026-10-22_15-19-56`). O critério da hipótese da cópia de 100 ms "não está definido" no fechamento.
- **Falta:** distinguir as hipóteses antes de corrigir. A execução exige isso explicitamente.
- **Risco:** a P-02 afeta a posição do evento, que P-03 e P-05 também usam.

### P-03 — Recaptura da 08 a 127 V/50 Hz com impulso em 90 ms
- **Pede:** posição com `|desvio| ≤ 10` amostras, pico ≤ 374,2 V, sobressinal ≤ 0,55. Acima disso é achado de segurança.
- **Estado:** ✅. Razão declarada: "2026-10-22: 3/3 capturas a 127 V/50 Hz com evento 90 ms, desvio 2 amostras, pico 339 V ≤ 374,2 V, sobressinal 0,295 pu ≤ 0,55".
- **Evidência:** `fechamento.json` com `evidencia_suficiente` e os critérios todos `ok`. Pico máximo medido 339 V (+339 / −193 V nas três capturas). Sobressinal 0,2950513688458192.
- **Ressalvas:**
  - As sessões estão no PC de Ricardo, fora do repositório. Só há SHA-256 dos `metadata/08_transient.jsonl` e `sessao.json`.
  - O sobressinal é uma métrica criada neste branch (`experimentos_waveform/08.py`, constante `SOBRESSINAL_ACHADO_DE_SEGURANCA`). Não estava no baseline. A própria nota no código diz que a amostragem a 30 kSa/s pode subestimar o pico.
  - O script diz que `evidencia_suficiente` **não é encerramento**. Quem fecha é o coordenador ou o responsável. Não há registro dessa decisão.
- **Falta:** registro da decisão de fechamento pelo responsável.

### P-04 — Gravação TRACe deve recusar pico acima do limite no ORM
- **Pede:** `program_capture()` só avisa quando o pico reconstruído passa de `max_peak_v` ("prosseguindo sem carga"). Quem recusa é `mestre.py` e o script de marcadores. Opções: (a) o ORM também recusar; (b) manter só a recusa de `mestre.py`.
- **Estado:** ✅.
- **Evidência:** no HEAD o aviso foi removido. Há recusa em `logica/ametek_orm.py:1427` (`combined_peak_v > self.max_peak_v`) e `:2105` (`pico > self.max_peak_v`). No baseline o aviso estava em `fa82f49:logica/ametek_orm.py:1525`. A opção escolhida é a (a), mais forte.
- **Falta:** confirmação de que a escolha (a) é a decisão do responsável. Não está em `decisoes_pendentes.md`.
- **Quem decide:** o responsável (DECISÃO DO USUÁRIO no inventário).

### P-05 — Sorteio de posição nas nativas 01–04
- **Pede:** disparo na fase sorteada (`TRIGger:SYNChronize:PHASe`, passos de 0,1°, sem readback); `:TIMebase:POSition` por captura; `PULSe:WIDTh` sorteada; `pre_trigger_desvio_amostras` (aviso acima de 2 amostras). Nenhum foi medido.
- **Estado:** ❓.
- **Evidência:** LEIA-ME de 22/10 registra o pre-trigger determinístico, em função do instante programado: classe 02 (início 19,07 ms) +5 amostras em 5/5; classe 03 (58,07 ms) −1; classe 04 (110,8 / 114,8 / 132,1 ms) −2 / −6 / +6. Dentro de ±0,2 ms a 30 kHz. Largura ≤ 1,1 ms (limite 2). O JSON dá `aviso` com desvio 6,0 contra limite 2. "Fase e início medidos" está em `criterio_nao_definido`.
- **Pendência de decisão:** o LEIA-ME diz: "Decidir se vira compensação do rótulo de início ou limite novo". O limite de 2 amostras nunca foi validado e não foi alterado.
- **Falta:** definir o critério de fase e início, e revisão humana.

### P-06 — Continuidade de fase na troca de frequência da classe 18 (47 → 53 Hz)
- **Pede:** continuidade de fase em `LIST:FREQuency` (`start_hz → end_hz`); rampa 47 a 53 Hz a 50 Hz; restauração com `restaurar_frequencia_base`. Limiar de 10° é proposta sem dado.
- **Estado:** 🔧→🏭. A execução diz "Parcial — bug de estado corrigido".
- **Evidência:** `fechamento.json` diz `insuficiente`: 0 capturas 47→53 Hz (limite ≥ 1) e salto de fase `sem_dados` (limite 10°).
- **Correção registrada:** a classe 18, após STEP/PULSe, não herda readbacks antigos (`execucao_pendencias.md`). Não confundir com o bug de THD das classes 18 e 19, que é o commit `72bbcd6`.
- **Falta:** capturas reais 47→53 Hz e medição da continuidade.

### P-07 — Crista da validação física das classes 07 e 17
- **Pede:** os fatores calibrados a 127 V/60 Hz (07 = 1,186; 17 = 1,031) não cobrem o toque simulado (≥ 1,344 e ≥ 1,420). A primeira rodada tende a reprovar só por "fator de crista". A recalibração ao fim do run vale só para o run seguinte.
- **Estado:** ❓.
- **Evidência:** commits `022bb5c` e `a22fba9`. Fatores passaram para 07 = 1,615 e 17 = 1,575. LEIA-ME: 17 recusada a 220 V; 1,575 é o máximo medido na segunda rodada (mínimo 1,369, mediana 1,423). A classe 07 rodou na Parte 6 sem alerta de extremo.
- **Falta:** revisão humana do diff, identificação da calibração e nova coleta para validar. A execução proíbe aprovação retroativa.

### P-08 — Extremos da classes 10, 11, 12 e 16 contra a previsão
- **Pede:** `pico_medido_v` e `vale_medido_v` ≤ `extremo_previsto_v`, depois da correção do rms CA por ciclo (a previsão antiga subestimava até 38 %).
- **Estado:** 🔧→🏭, mas a execução diz "Reprovada em 2026-10-22".
- **Evidência:** `fechamento.json` `reprovado`: razão máxima 1,297 em 127 V/60 Hz. O exemplo do LEIA-ME: a classe 12 chegou a 264 V contra 203,5 V previstos. A classe 13-0002 chegou a **378 V**, contra teto de 415,8 V.
- **Achado de segurança:** os extremos passaram do previsto em 1 % a 30 %. Recalibração a 60 Hz commitada em `13b9bdb`.
- **Falta:** nova coleta com a calibração corrigida, para verificar a razão em todas as condições.

### P-09 — Média de cada ciclo nas classes 10, 11, 12 e 16
- **Pede:** a programada não reproduz a média por ciclo do modelo. Erro de 0,24–0,33 pu. Só seria recuperável com offset por passo (ACDC, que tem o déficit da P-17). Opções: (a) investigar depois da bancada; (b) aceitar a perda como limite físico do modo TRACe.
- **Estado:** 🔧→🏭 no rastreador. "Parcial" na execução. `aberta` no JSON. "Resolvido" no LEIA-ME.
- **Evidência:**
  - `docs/evidencias/2026-10-16/modelo_programado.json`: 108 registros, classes 06, 10, 11, 12, 15 e 16, três perfis, 50 e 60 Hz. Perda máxima de 0,018 a 0,288 pu nas compostas com sag. Mediana geral 0,072 pu. Máximo 0,288 pu (classe 16, 50 Hz).
  - Diagnóstico de 22/10: `SOURce:LIST:VOLTage:OFFSet` respondeu `-113 Undefined header` (`docs/evidencias/2026-10-22/diag_list_offset.json`).
  - O manual lista `LIST:VOLT:OFFS` só como "Related Command" (p. 96), sem definição.
- **Mecanismo:** a fonte remove o DC de toda TRACe (manual p. 126) e `montar_programacao` zera a média de cada ciclo. Só existe `dc_offset_pu` global por captura. Em simulação, o offset por passo reduziria o erro rms de 0,097 para 0,0015 pu (classe 16). Essa simulação depende da P-17.
- **Decisão do responsável (21/10), citada:** "aceitar como limitação **somente se** as alternativas não se confirmarem". Plano: "(3) se o comando existir, medir (b) na 16 depois da P-17; senão, fechar a P-09 como limitação aceita com (d)".
- **Conflito:** a condição do passo 3 foi cumprida (o comando não existe). O rastreador ainda pede os braços A e B, que não estão no plano. Isso precisa de decisão.
- **Falta:** decisão do responsável sobre fechar P-09 agora ou exigir os braços A e B.

### P-10 — Classe 05: RMS e THD das senoides de nível
- **Pede:** rms e THD da CSINusoid a 10, 15 e 20 %; nível de 2 % (perfil `norma`); nível de 30 % por TRACe; modelo novo contra a bancada.
- **Estado:** ✅.
- **Evidência:** `fechamento.json` `evidencia_suficiente`. Níveis medidos: 0,02; 0,05; 0,10; 0,15; 0,20; 0,30. Validação física ok em cada nível exigido. Rota: CSIN para 2, 10, 15 e 20 %; TRACe para 30 %. Duas capturas por nível de CSIN e uma para o nível de TRACe.
- **Ressalvas:** as sessões estão fora do repositório. O nível de 5 % aparece nos dados mas não está na lista de níveis exigidos. A página `docs/classes/05-harmonics.md:8` ainda diz `NÃO VERIFICADO` e `PENDENTE P-10`.
- **Falta:** registro da decisão de fechamento e atualização da página da classe.

### P-11 — Manter ou reverter as extensões das compostas 10 a 16
- **Pede:** extensões (sag em 11 e 12, swell em 13 e 14, faixas da `norma`, `fronteira` alternada, THD em 13, 15 e 16). Opções: (a) manter, documentando em `docs/perfis.md`; (b) reverter, o que muda o dataset e exige regravar `tests/fixtures/gerar_sorteio_v1_15.json`.
- **Estado:** ✅ ("Concluída — decisão e metadata").
- **Evidência:** código e metadata existem. A classe 15 registra envelopes e THD central, mínima e máxima da redução (`experimentos_waveform/15.py`, `parametros_com_disturbio_reduzido`). A execução diz que `gerar()` e as fixtures foram preservados. Verificado estaticamente: `tests/fixtures/` sem mudança desde o baseline.
- **Falta:** registro da decisão. A validação física das classes continua em P-01 e P-08.
- **Quem decide:** responsável.

### P-12 — Classe 06 (flicker): comparar com a programada ou redefinir
- **Pede:** (a) comparar a 06 com a forma programada, sem mudar o dataset; (b) redefinir o flicker com média nula por ciclo (muda `gerar()` e exige autorização em AGENTS.md). O efeito nas classes 11 e 15 não estava calculado.
- **Estado:** ✅ ("software e decisão").
- **Evidência:** `experimentos_waveform/06.py` ganhou `forma_esperada_para_validacao`, que compara a medida com a reconstrução da programada e nunca usa a própria medida como referência. Verificado no diff.
- **Falta:** registro da decisão. Fidelidade física continua em P-01.

### P-13 — Recuperação de sessão parcial
- **Pede:** `sessao_io.recuperar_parcial` é função manual. Ninguém a chama no início do `run`. Opções: (a) chamar automaticamente; (b) manter manual.
- **Estado:** ✅ ("Concluída — software").
- **Evidência:** lock de sessão em `logica/sessao_io.py:57–118`, com `msvcrt` no Windows e `fcntl` no POSIX. Arquivo `.sessao.lock`. Não verifiquei se o `run` passou a chamar a recuperação automaticamente (opção a). A execução fala em "escritor ativo ignorado" e "morte abrupta preserva ambos os IDs".
- **Falta:** registro da opção escolhida, e confirmação de qual das duas foi implementada.

### P-14 — `run 01 02` e `BATERIA_EXCLUIR` em listas
- **Pede:** `run 01 02` (com espaço) roda só a 01, sem aviso. `BATERIA_EXCLUIR` não vale para listas. Opções: (a) recusar e aplicar a exclusão; (b) manter.
- **Estado:** ✅.
- **Evidência:** `logica/cli.py:825–853`. Argumentos extras em `run all` são recusados com "Nada foi energizado". Listas aplicam `BATERIA_EXCLUIR` (linhas 848–853). Escolha: (a).
- **Ressalva:** o RTD ainda descreve o bug em `docs/codigo/cli.md:64`. A feature já corrigiu (`docs/codigo/cli.md:69`).
- **Falta:** registro da decisão.

### P-15 — Limite de três capturas no HTML do fim do run
- **Pede:** `docs/operacao.md:122` diz que o HTML mostra só as 3 primeiras capturas por classe e perfil. No código, o limite vale só para o dataset simulado e para o formato 1, e **não** para a bancada em formato 2. Isso pode levar o HTML além de 20 MB. Opções: (a) corrigir o texto; (b) limitar também na bancada.
- **Estado:** ✅.
- **Evidência:** `logica/relatorio_html.py:302–310` aplica o limite padrão de três capturas também em bancada e simulação. Escolha: (b).
- **Ressalva:** o comportamento de bancada não foi executado com sessão real. O inventário marca isso como NÃO VERIFICADO.
- **Falta:** registro da decisão. Confirmar o tamanho do HTML com sessão real.

### P-16 — Suíte offline no PC da bancada (Windows)
- **Pede:** rodar `tests.test_offline` no Windows.
- **Estado:** ✅.
- **Evidência:**
  - 21/10, commit `21fb300`: 680 testes, 0 falhas, 0 erros, 0 skips (`docs/evidencias/2026-10-21/pc_bancada.json`).
  - 22/10, commit `6885e7c`: 759 testes, 0 falhas, 0 erros, 0 skips, 156,5 s (`docs/evidencias/2026-10-22/pc_bancada.json`).
- **Por que está errado:**
  - O HEAD (`cd1e6a9`) é posterior ao `6885e7c`. Ele alterou `scripts/visita_bancada.py` (+7) e `tests/test_visita_bancada.py` (+17). Esses testes não rodaram no PC.
  - O `fechamento.json` marca `requer_revisao_humana: true` e aviso `commit_igual_ao_das_sessoes`. As sessões são de `c690a49`, `022bb5c` e `a22fba9`; a suíte é de `6885e7c`.
  - A matriz da execução diz "fechar_pendencias.py P-16 = evidencia_suficiente **sem revisão pendente**". Isso contradiz o fechamento de 22/10.
- **Falta:** rodar a suíte no HEAD atual e registrar o commit exato.

### P-17 — Déficit de amplitude em ACDC
- **Pede:** déficit de 5 a 6 % na CA em ACDC (0,938–0,951 pu). `diag_acdc_amplitude.py` pronto e nunca rodado. Compensação `V/g` é proposta. 230 V no ACDC é escolha do dia.
- **Estado:** ❓.
- **Evidência:** `fechamento.json` `evidencia_suficiente` com revisão humana. A medida de `measure_voltage` em ACDC devolve RMS total (`ametek_orm.py:1963–1977`), o que é o achado H-1 do inventário.
- **Falta:** critério de aceitação do déficit (`deficit_acdc_aceitavel` está em `criterio_nao_definido`). A execução pede caracterizar o déficit antes de aplicar qualquer correção.
- **Quem decide:** responsável.

### P-18 — Passo final SINE no LIST
- **Pede:** `SINE` aceito em `LIST:FUNCtion:SHAPe`? O branch `feat/passo-final-sin` (PR #3, `18b144d`) tinha o padrão ligado (`AMETEK_PASSO_FINAL_SIN = 1`). Merge com a `main` tem conflito textual.
- **Estado:** 🔧→🏭.
- **Evidência:** integrado no checkout de execução com padrão **desligado** (`AMETEK_PASSO_FINAL_SIN=0`, `passo_final_sin=False`). `fechamento.json`: `sem_dados`.
- **Decisão pendente:** o formulário do responsável tem a opção A (manter desligado até validação) como recomendada. A resposta está em branco.
- **Falta:** teste em bancada com `scripts/teste_passo_final_sin.py` e confirmação `ENERGIZAR-PASSO-SIN`. Confirmar a aceitação de LIST e a restauração na fonte.

### P-19 — Resposta de `TRACe:DATA?`
- **Pede:** a Rev. 5.53 aceita `TRACe:DATA? <nome>` e responde lista NRf separada por vírgula? O manual se contradiz (p. 126 "Query Syntax: none"; p. 147 "when queried… normalized").
- **Estado:** 🔧→🏭.
- **Evidência:** `fechamento.json` `insuficiente`: `TRACe:DATA? TCC00` devolveu 10 valores em vez de 1024, em 9 leituras das classes 08 e 09 (`erros: 9`). Não é nem 1024 valores finitos nem erro explícito de comando não suportado.
- **Falta:** investigar o formato da resposta no firmware real. Confirmar 1024 valores finitos ou erro SCPI explícito.

### P-20 — Congelar a v1.15: licença, autoria, citação, tag e Zenodo
- **Pede:** tag `v1.15`, release e Zenodo. O projeto não tem `LICENSE` nem `CITATION.cff`.
- **Estado:** ❓, "aguarda o Denis".
- **Evidência:** não há `LICENSE`, `COPYING`, `CITATION.cff`, `.zenodo.json`, `AUTHORS` nem `CODEOWNERS` em nenhum branch, nem no histórico. O formulário tem cinco perguntas em branco (licença do código, licença do dataset, quem autoriza, autores com ORCID, texto de citação) e três opções de tag e de Zenodo. Nenhuma resposta.
- **Regra do formulário:** "Nenhuma licença, autoria, citação ou DOI será criada antes da resposta dele." O fork não concede direitos de relicenciamento.
- **Falta:** respostas do responsável. A tag depende de P-01 e P-31.

### P-21 — Fatores de extremo a 220 V/60 Hz e 33 V/60 Hz
- **Pede:** calibrar condições novas antes da coleta científica. A 220 V/60 Hz não existe tabela, então toda classe usa o maior fator já medido (1,615) menos a 01. Só cabem 07, 10, 11, 15 e 16 na rodada de calibração.
- **Estado:** 🔧→🏭.
- **Evidência:**
  - `fechamento.json`: `insuficiente`. Calibração da condição 127 V/50 Hz e 127 V/60 Hz tem `classes_sem_fator: ['08']`. **A classe 08 não tem fator de extremo nem em 50 Hz nem em 60 Hz.** Nenhuma rodada de `recalibrar_extremos.py` diminuiu fatores.
  - Calibração de 50 Hz feita antes da campanha de 230 V (`aac725b`).
- **Decisão do operador em 22/10:** opção A (manter a regra atual). Registrada como "decisão final do responsável" pendente.
- **Pontos do formulário:** B (mesma frequência basta) cobriria quase todas as classes a 220 V. C (decidir depois das campanhas de 127 V/50 Hz e 230 V/50 Hz) mediria se o fator muda com a tensão.
- **Falta:** decisão do responsável; calibração da 08.

### P-22 — Tamanho e custo de gravação do `.npz`
- **Pede:** tamanho e custo de reescrita do `NN_classe.npz` com medida física real. Capturas "espelho" são cópias, não três medidas.
- **Estado:** ❓.
- **Evidência:** `benchmark_sintetico.json` mede tempo e tamanho para 3, 10 e 30 capturas, com verificação de leitura e aliases. `fechamento.json`: 14 sessões físicas lidas sem erro no DESKTOP-FSEESJI. Os hashes do benchmark são iguais.
- **Falta:** critério de tempo e tamanho aceitáveis (`criterio_nao_definido`). Medida com dados físicos reais, no PC e no disco da bancada.

### P-23 — Trava da fonte por número de gravações TRACe
- **Pede:** a fonte trava perto da 280.ª gravação de TRACe por conexão (quirk A3; causa NÃO VERIFICADA). Os docs ainda recomendam `run all` (468 gravações a 60 Hz; 1116 com `todos`).
- **Estado:** 🔧→🏭.
- **Evidência:** orçamento de 216 gravações por conexão aplicado no CLI, na entrada principal e no ORM. Esgotamento aborta a bateria sem retry. README:26 já cita 216. `fechamento.json`: `insuficiente`, com `diag_nativo_output_off_presente` em 0 (limite ≥ 1).
- **Decisão pendente:** o formulário tem opções A (manter 216 como regra operacional, sem afirmar que é limite físico), B (mudar o valor) e C (configurável por variável de ambiente). A resposta está em branco.
- **Falta:** causa física da trava. Diagnóstico real com saída OFF.

### P-24 — Documentação: referências a código
- **Pede:** 63 das 85 citações `arquivo:linha` estavam deslocadas. Oito documentos carimbados com `d37e403`. O site deveria usar símbolos em vez de linhas.
- **Estado:** ✅ ("revisão e build local"). A execução diz explicitamente que a publicação remota não é afirmada.
- **Evidência:** 1136 permalinks `blob/fa82f496` no branch de feature (conferido). **Zero** no branch do RTD. O build Sphinx não foi reexecutado nesta análise.
- **Falta:** publicar o branch de feature no RTD, ou o RTD apontar para ele.

### P-25 — Decisões menores de autocontenção
- **Pede:** identificadores de tarefa no texto (8 ocorrências fora dos CHANGELOG); um termo de governança em `AGENTS.md` (9 ocorrências); um nome de variável local em `mestre.py`; texto de `uso_limite_bancada` em `calibracao_extremos.json` (muda o SHA-256 do arquivo). Aceitar ou retirar, item a item.
- **Estado:** ✅ ("decisão editorial").
- **Evidência:** `docs/limites_e_calibracao.md:51` ainda diz "(v1.15, spec 26)" no feature. O RTD tem a mesma frase em `:34`. Não há resposta do responsável.
- **Falta:** o responsável aceitar ou retirar cada item. Corrigir o `spec 26`.

### P-26 — Condições da campanha
- **Pede:** perfil ou `todos`; frequência (o roteiro assume 60 Hz); ACDC a 230 V. Decidir antes de começar.
- **Estado:** 🔧→🏭.
- **Decisão do responsável (21/10):** perfis = todos (`set perfil todos`); condições = 127 V/60 Hz, 127 V/50 Hz, 230 V/50 Hz, 220 V/60 Hz e 33 V/60 Hz; ACDC 230 V fora (diagnóstico ACDC só a 127 V); 1 captura por classe. Plano offline em `docs/evidencias/2026-10-21/plano_campanhas_5_condicoes.json`.
- **Falta:** registro da configuração em cada sessão. Até 22/10 só há sessões de 127 V. Não há sessão de 230 V/50 Hz nem de 220 V/60 Hz nem de 33 V/60 Hz.

### P-27 — Faixa de referência da correlação do distúrbio
- **Pede:** as faixas (0,95–1,00; 0,75–0,94; 0,005 da 08) vêm de `validacao_gerador_v1.14.md`, que não está no repositório. Fornecer o arquivo.
- **Estado:** ✅ ("comparações sem fonte retiradas").
- **Evidência:** `git log --all -- '*validacao_gerador*'` vazio. O fork removeu as faixas e a coluna "bate?" do documento (`docs/correlacao_disturbio.md:37`, `:75`). No RTD a tabela com "bate?" continua em `docs/correlacao_disturbio.md:41`.
- **Ressalva:** a decisão pedida ("fornecer o arquivo") não foi respondida. Remover o critério resolve o problema, mas o responsável não decidiu isso.
- **Falta:** registro da decisão.

### P-28 — Reamostragem do osciloscópio (116,7 kSa/s para 30 kSa/s)
- **Pede:** interpolação linear, sem anti-aliasing. Efeito não quantificado (quirk K4).
- **Estado:** ❓.
- **Evidência:** `set diagnostico bruto on` preserva BYTE, preamble e tempos antes de interpolar. 135 exportações brutas íntegras. Reamostragem casada por SHA-256. Analisador compara RMS, pico, THD, erro temporal e espectro.
- **Importante:** FIR não substitui o interpolador do dataset. É só comparação.
- **Falta:** decidir se o FIR substitui o interpolador. Revisão dos resultados físicos (`fir_substitui_interpolador` em `criterio_nao_definido`).

### P-29 — Transcrições SCPI reais
- **Pede:** as `scpi_transcricao.log` de 07/10 existem só no PC antigo (gitignored). A tabela SCPI do site descreve código e manual, não medição.
- **Estado:** 🔧→🏭.
- **Decisão do responsável (21/10): opção B.** Os dados do PC antigo não podem ser copiados. Os exemplos reais virão das `scpi_transcricao.log` das sessões novas da campanha v1.15, revisados antes de publicar.
- **Falta:** sessões novas com `scpi_transcricao.log`, revisão de dados sensíveis, e atualização de `docs/scpi/transcricoes.md`.

### P-30 — Contagem de 07/10: 63 ou 99 capturas
- **Pede:** AGENTS.md e CHANGELOG dizem 63 ("piloto"); `tres_versoes.md` diz 99; os arquivos têm 36 + 36 + 27 = 99.
- **Estado:** ✅.
- **Decisão do responsável (21/10): decisão D, confirmada.** Registrar 63 e 99 como contagens históricas não verificáveis, sem apagar histórico e sem usar como resultado. Os dados de 07/10 não podem ser recuperados.
- **Evidência:** `decisoes_pendentes.md` tem a decisão. A nota de retificação está em AGENTS.md e `docs/tres_versoes.md`.
- **Única ressalva:** a versão de código das sessões de 07/10 é `994e170-dirty`, código sujo.

### P-31 — Métrica oficial de correlação do distúrbio
- **Pede:** duas métricas já publicadas (contra o nominal, e contra a fundamental ajustada). Escolher qual é a oficial.
- **Estado:** ❓.
- **Evidência:** classe 06, 50 Hz, perfil norma: 0,98756 (nominal) e 0,98742 (fundamental ajustada). Nenhum limiar automático.
- **Opções do formulário:** A (publicar as duas, sem eleger) — recomendada. B (nominal). C (fundamental ajustada). Resposta em branco.
- **Falta:** decisão do responsável; sessões físicas novas.

---

## 4. Problemas transversais

### 4.1 Documentação: quatro cópias do estado
1. **`docs/` do branch de feature.** Vivo. Tem rastreador, execução, decisões, bancada, estado JSON e evidências.
2. **`docs/` do branch `docs/site-readthedocs`** (o que o RTD publica, pelo link de versão citado na execução). Snapshot de 16/10. `projeto/pendencias.md` diz "PENDENTE 31 itens abertos". Não tem rastreador, execução, decisões nem evidências.
3. **`docs-site-plano/`** na raiz desse branch. Plano de 15/10 com 31 pendências abertas.
4. **Roteiros e registros soltos:** `ROTEIRO_BANCADA.md` (raiz, 52 KB), `docs/bancada_pendencias.md`, `docs/roteiro-bancada.md`, `CHANGELOG/v1.15.md`, `mapa/` (Obsidian, gerado).

### 4.2 Textos no RTD que descrevem bugs já corrigidos
- `docs/codigo/cli.md:64`: `run 01 02` roda só a 01 (corrigido na feature, `:69`).
- `docs/operacao.md:122`: HTML limitado a 3 capturas só na simulação (corrigido na feature).
- `docs/correlacao_disturbio.md:41`: coluna "bate?" (removida na feature).
- `docs/classes/*.md:3`: selos `PENDENTE` de itens fechados.

### 4.3 Selos e textos desatualizados nas classes (feature)
- `docs/classes/08-transient.md:8`: `NÃO VERIFICADO` para "impulso a 90 ms a 50 Hz" e `PENDENTE P-03`. P-03 está fechado.
- `docs/classes/05-harmonics.md:8`: `NÃO VERIFICADO` para CSIN 10, 15, 20 %, nível de 2 % e 30 % por TRACe, e `PENDENTE P-10`. P-10 está fechado.
- `PENDENTE P-11` nas classes 10 a 16 (7 páginas). O que resta é validação física (P-01, P-08).
- `PENDENTE P-12` nas classes 06, 11 e 15 (3 páginas). O que resta é fidelidade física (P-01).

### 4.4 Datas e caminhos
- `execucao_pendencias.md`: "atualizada em 17/10/2026", mas a matriz tem dados de 22/10.
- `docs/projeto/pendencias.md`: "inventário histórico de 16/10/2026". O RTD diz "conferida em 2026-10-16".
- Rastreador: "Atualizado 2026-10-22".
- A execução cita `/tmp/asd-exec-venv/bin/sphinx-build` e `/tmp/asd-docs-build.log`, que não existem para quem lê.

### 4.5 Três números de teste
| Data | Commit | Ambiente | Resultado | Onde aparece |
|---|---|---|---|---|
| 17/10 | `58130af` | Mac, Python 3.11.15 | 574 OK, 2 skips | `execucao_pendencias.md` (consolidado) |
| 21/10 | `21fb300` | PC da bancada | 680 OK | P-16 na matriz |
| 22/10 | `6885e7c` | PC da bancada | 759 OK | Rastreador, `pc_bancada.json` |

Nenhum dos três é do HEAD atual. A execução usa 574 como consolidado; o rastreador usa 759.

### 4.6 README
- `README.md:26` aponta para `ROTEIRO_BANCADA.md`. O rastreador diz para não ler esse arquivo.
- A seção "Mapa da documentação" não cita os arquivos de rastreio. Aponta `execucao_pendencias.md` como plano e estado. Todos os links resolvem no HEAD. A mesma seção existe no README do RTD.

### 4.7 `estado_prontidao.json`
- Estado binário. As 13 "concluida" batem com o rastreador. As 18 "aberta" escondem os parciais.
- P-09 aparece como `aberta` com evidência listada.

### 4.8 Decisões do responsável não registradas
- O inventário marca como DECISÃO DO USUÁRIO: P-04, P-09, P-11 a P-15, P-20, P-23, P-25, P-26, e partes de P-18, P-29, P-30, P-31. Diz explicitamente que a página "não escolhe".
- O formulário tem respostas para P-09, P-21, P-26, P-29 e P-30. Está em branco para P-18, P-23 e P-31. P-20 aguarda Denis.
- Não há seção para P-04, P-11, P-12, P-13, P-14, P-15, P-25 e P-27.
- A execução diz que as escolhas vieram de "autorização do usuário nesta sessão". Isso não é a decisão do responsável.

---

## 5. Código alterado desde o baseline `fa82f49` (estático)

| Arquivo | Mudança | Altera `gerar()`? |
|---|---|---|
| `experimentos_nativos/05.py` | +`rota_programacao` (metadata) | Não |
| `experimentos_nativos/18.py` | +`exigencias_nativas` (hook) | Não |
| `experimentos_nativos/19.py` | `configurar` refatorado em `_offset_da_captura` | Não pelo diff; saída equivalente não verificada |
| `experimentos_waveform/06.py` | +`forma_esperada_para_validacao` | Não |
| `experimentos_waveform/08.py` | +métrica de sobressinal; validação alterada | Não pelo diff |
| `experimentos_waveform/15.py` | +`parametros_com_disturbio_reduzido` | Não pelo diff |
| `logica/sinais.py` | +`distancia_modelo_programada` | Não pelo diff |
| `tests/fixtures/` | sem mudança | — |

Estático: 760 ocorrências de `def test_` em `tests/` no HEAD. Não é contagem de execução.

---

## 6. Segurança e operação registradas nos documentos

- **13-0002 chegou a 378 V** (teto 415,8 V). Achado de segurança, registrado no LEIA-ME.
- **P-08:** extremos até 1,297× o previsto.
- **P-02:** posição da 08 com desvio de −16 amostras.
- **Bug de THD corrigido em `72bbcd6`:** a forma de onda ficava na última TRACE entalhada. As classes 18 e 19 chegaram a THD de 9,7 %.
- **Visita de 22/10:** parada no braço A da P-09 com OUTPUT OFF conferido.
- **Decisão de 220 V/60 Hz:** manter a regra atual, pendente do responsável.

---

## 7. Próximos passos sugeridos (não executados)

1. Eleger o rastreador como fonte única. Gerar ou referenciar os outros documentos a partir dele.
2. Atualizar os selos de P-03 e P-10 (fechados). Apontar P-11 para P-01 e P-08. Apontar P-12 para P-01. Corrigir `docs/limites_e_calibracao.md:51`.
3. Corrigir P-16: rodar a suíte no HEAD atual e registrar o commit exato. Remover a afirmação "sem revisão pendente".
4. Corrigir P-25: remover `spec 26` de `docs/limites_e_calibracao.md:51`.
5. Registrar em `decisoes_pendentes.md` as escolhas do fork (P-04, P-11 a P-15, P-25, P-27) como "tomadas no fork, aguardando confirmação".
6. P-09: o responsável decide entre fechar como limitação aceita (condição cumprida) ou exigir os braços A e B.
7. P-21: calibrar a classe 08 (sem fator em 50 e 60 Hz) antes de qualquer campanha.
8. Atualizar `estado_prontidao.json` para os estados do rastreador, ou documentar que é binário.
9. Decidir o que o RTD publica. Hoje mostra o estado de 16/10.
10. Remover ou substituir a seção "Mapa da documentação" do README. Corrigir `README.md:26`.
11. Respostas do responsável pendentes: P-18, P-20, P-23, P-31, P-25, e a decisão de fechamento de P-03 e P-10.
