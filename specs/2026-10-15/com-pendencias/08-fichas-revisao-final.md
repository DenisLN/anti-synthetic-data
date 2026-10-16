# Relatório: ASD Docs: Fichas das 20 Classes e Revisão Final do Site

## Análise do orquestrador

1. **Implementação completa?** Sim. No worktree `asd-docs-site`: 14 commits sobre `fa82f49`; nenhum arquivo de `logica/`, `experimentos_*/`, `scripts/`, `tests/`, `.env*` nem `calibracao_extremos.json` alterado; nenhum arquivo de `docs/` renomeado ou apagado. Reproduzi o build (`sphinx -W --keep-going -E`): "build succeeded", sem warning. Rodei `docs-site-plano/verificar-fichas.py`: "20 ficha(s) conferida(s); 0 divergência(s)". Nenhuma página "em redação" resta (`grep` vazio) e `docs/classes/` tem as 20 fichas (175 a 261 linhas), sem `PREENCHER` nem `TODO`. Li o início da ficha 08: estrutura de 12 seções, selos, pergunta e resposta em negrito, números com condição e histórico (A22, P-02, P-03), no estilo pedido. O diff de `AGENTS.md` só reescreve a seção "Documentação (mapa)"; nenhum limite inegociável foi tocado.
2. **Pendências que exigem o usuário?** Sim: importar o repositório no Read the Docs, decisões abertas das specs anteriores e decidir se o achado da classe 18 vira `P-32`.
3. **Escopo limitado demais?** Não. A varredura visual completa das 21 páginas não terminou (feita por amostragem: 05, 06, 08 e `classes.html`, desktop e celular, claro e escuro); o executor declarou isso.
4. **A missão resolve o contexto?** Sim. Com as 20 fichas, o Guia do código, a referência SCPI, a correlação, a recalibração e as pendências, o site cobre o que o usuário pediu.

**Critério de Parada:** atendido (build limpo reproduzido, verificador 0 divergências, sem esqueleto, `README.md`, `AGENTS.md` e `CHANGELOG/v1.15.md` apontam para o site; a suíte de 497 testes é alegação do executor, não repeti nesta etapa).

**Achado do executor a decidir (só código):** `frequency_drift_list` (classe 18) não define o readback do transiente; se a 18 rodar logo depois de uma classe STEP ou PULSe na mesma conexão, sem TRACe no meio, `arm()` a recusa (reproduzido offline com a fonte simulada, segundo o relatório). Não verifiquei de forma independente.

**Observação:** `.readthedocs.yaml` usa `fail_on_warning: true` e Python 3.12; o build testado foi com Python 3.11 (Windows) e 3.14 (Linux). Se o primeiro build no Read the Docs falhar por aviso, trocar para `false` primeiro.

**Classificação:** com pendências (decisões do usuário; o trabalho da spec está entregue).

---

Worktree `C:\Users\denis\Documents\1 Projetos\asd-docs-site`, branch `docs/site-readthedocs`, HEAD `5bf366f` (14 commits locais sobre `fa82f49`; sem push, sem merge). Data de execução: 2026-10-16.

## Missão, item a item

**Item 1 — Escrever as fichas das classes **nativas 01, 02, 03, 04, 05, 18 e 19** em `docs/classes/NN-nome.md`, cada uma com as 12 seções do modelo (resumo e selos; o fenômeno e a norma; modelo matemático em `gerar()` com parâmetros, sorteio de início, duração e fase, seed e `capturas_padrao`; como a bancada reproduz, com a sequência SCPI exata e `arquivo:linha`; parâmetros por perfil `norma`, `literatura` e `fronteira`; limites físicos e fator de extremo por condição; validação física e suas tolerâncias; as três versões e a correlação esperada, linkando a tabela da página de correlação; quirks; histórico por versão; estado de verificação e pendências com os ids `P-NN`; referências). Cobrir os níveis discretos das 02, 03 e 05 e o teto da CSINusoid de 20 % da 05.**
- Status: CUMPRIDO
- Explicação: sete fichas em `docs/classes/01-normal.md`, `02-sag.md`, `03-swell.md`, `04-interruption.md`, `05-harmonics.md`, `18-frequency-drift.md`, `19-dc-offset.md` (175 a 218 linhas cada; commit `4b5f590`). Cada uma tem as 12 seções, mais a seção 12 "Como o código da classe funciona" (adendo) e a 13 "Referências"; os `{scpi}`/`{scpik}` resolvem na referência SCPI (o build `-W` falha se um comando não tiver entrada). Níveis discretos: tabelas geradas do código com o que a fonte programa a 127 V e 230 V já arredondado a 0,1 V (02 e 03: `AmetekMX30.quantizar_tensao_rms`) e, na 05, a tabela por THD com mecanismo, fundamental, pico, rms e corte da clipagem (2 %, 5 %, 10 %, 15 %, 20 % por CSINusoid; 30 % por TRACe); o teto `MAX_CSINE_THD_PCT = 20,0` (`ametek_orm.py:163`) e a consequência de que sem `set capturas` só o nível 0 de 02, 03 e 05 roda estão nas fichas e em `classes.md` §4. Os números de perfis, limites, medidas e validação de 07/10/2026 foram gerados por script a partir de `perfis.py`, `calibracao_extremos.json`, `scripts/relatorio_limites_bancada.py` e do metadata das três sessões; a correlação, de `docs/medicao/correlacao.md`. Evidência: `docs-site-plano/verificar-fichas.py` → "20 ficha(s) conferida(s); 0 divergência(s)".

**Item 2 — Escrever as fichas das classes **por waveform 06, 07, 08, 09 e 20**, no mesmo modelo, com atenção às particularidades: 06 (média por ciclo da TRACe, flicker, correlação do distúrbio), 07 (entalhes em todos os ciclos, oscilação da fonte, crista), 08 (impulso filtrado, três limitações independentes, teto de 0,9 × `max_peak_v`, deslocamento a 100 ms, fora do sorteio), 09 (cópia do evento em 100 ms), 20 (145, 210 e 330 Hz).**
- Status: CUMPRIDO
- Explicação: `06-flicker.md`, `07-notch.md`, `08-transient.md` (261 linhas), `09-oscillatory-transient.md`, `20-interharmonics.md` (commit `9aebff8`). 06: a média por ciclo (rms 0,002–0,032 pu, correlação programada × modelo por perfil, frequência e faixa de flicker, 0,9999 sem a média) e a caixa "Decisão em aberto P-12". 07: modelo `aplicar_entalhes_continuos`, o toque de ~7,5–10 kHz (A20) e a tabela da crista (fator calibrado 1,186 contra mínimo 1,344; 58/135 aprovadas a 60 Hz). 08: as três limitações, o teto 374,2 V (2,084 pu a 127 V), as amplitudes seguras **recalculadas offline com a classe real** (1,618; 1,344; 0,776; 0,360; 0,742; 0,285 pu, iguais às do `classes.md` antigo), o impulso a 80 ms (60 Hz) e 90 ms (50 Hz), a cópia a 100 ms (A22, P-02, P-03) e as seis capturas de 07/10 (previsto contra medido). 09: A25 com as medidas offline do `diag_ciclos_trace.py` e a recomendação de campanha. 20: 145/210/330 Hz com a razão a f0 e as amplitudes por perfil.

**Item 3 — Escrever as fichas das classes **compostas 10, 11, 12, 13, 14, 15, 16 e 17**, no mesmo modelo, explicando como cada uma combina componentes (sag ou swell com harmônicos, flicker ou transitório oscilatório; 15 e 16; 17 com entalhes e oscilação), o que o sorteio cobre em cada componente (`docs/perfis.md`, "Compostas sorteadas"), a média por ciclo nos ciclos de borda das 10, 11, 12 e 16 e o limite de bancada com o fator `k` quando o pico não cabe.**
- Status: CUMPRIDO
- Explicação: `10-sag-harmonics.md` a `17-notch-oscillatory-transient.md` (commit `8fdc049`). Cada uma traz a fórmula da combinação, a ordem das chamadas a `perfis.composto`, a tabela `FAIXAS`/`FAIXAS_SORTEADAS` por perfil (gerada do código), o gancho `parametros_com_disturbio_reduzido` com a tradução de `k` (a 15 é a exceção, sem gancho: registrado) e a tabela de limites por condição com `k` aplicado. A média por ciclo nos ciclos de borda (10, 11, 12, 16) tem texto próprio e a tabela antes/depois da correção do rms CA (0,24–0,33 pu), com a caixa "Decisão em aberto P-09". A 14 mostra por que 230 V/50 Hz é inviável (k necessário 17–22 %, abaixo do mínimo de 25 %); a 16 mostra o maior fator de extremo (1,475); a 17 o 444 V a 230 V/50 Hz que originou a calibração por condição.

**Item 4 — Converter `docs/classes.md` em página de visão geral das 20 classes (tabela com link para cada ficha, mecanismo, sorteio e capturas padrão), **sem perder nenhum fato** hoje presente nele: cada fato precisa existir em alguma ficha ou página transversal (listar a correspondência no relatório). Conferir cada número, nome de parâmetro e `arquivo:linha` das 20 fichas contra o código da `main` (rodar o verificador que o relatório descrever, por exemplo um script em `docs-site-plano/` que confira que cada `arquivo:linha` citado existe) e corrigir o que divergir.**
- Status: CUMPRIDO
- Explicação: `docs/classes.md` reescrito no lugar (tabela de 20 linhas com link, mecanismo, parâmetros, sorteio, `capturas_padrao`, dependência de perfil e estado; mais as seções de sorteio, validação física e capturas por classe); a tabela de correspondência de fatos está abaixo. Verificador: `docs-site-plano/verificar-fichas.py` (ast: existência do arquivo e das linhas; quando a citação segue um símbolo, início e fim exatos; seções; `P-NN` de cada classe contra `docs/projeto/pendencias.md`; ausência de "em redação"). Primeira rodada achou divergências reais (linhas de `sinais.forma_programada_nativa` 623-682 em vez de 624-683, citações de linhas de chamada coladas a símbolos, `DURACAO_S` 15-16 em vez de 16); todas corrigidas. Resultado final: 557 citações de linha, 0 divergências; as 36 citações que não coincidem com um símbolo foram conferidas à mão contra o texto da linha (todas conferem). Constantes e parâmetros lidos do código antes de citar (0,55; 0,70; 30; 10; 0,25; 0,9; 1,10; 0,15; 0,20; 0,10; 0,01; 280; 1024; 6000; 415,8 V).

**Item 5 — Fazer a **revisão final**: build do site sem warning e `linkcheck` dos links internos; nenhuma página-esqueleto "em redação" restante; checklist de cobertura contra `docs-site-plano/02-lacunas.md` (20 fichas, SCPI, correlação, recalibração, pendências, estado de validação); atualizar o mapa de documentação de `README.md` e de `AGENTS.md` (seção "Documentação (mapa)") para apontar para o site e a nova árvore, e acrescentar a seção correspondente em `CHANGELOG/v1.15.md`; abrir o site construído no navegador embutido em largura de desktop e de celular, tema claro e escuro, e registrar o que viu; escrever no relatório os passos para o usuário importar o repositório no Read the Docs (conta, URL do repositório, versões `latest` e tags).**
- Status: CUMPRIDO (a inspeção visual foi por amostragem, ver abaixo)
- Explicação:
  - Build: `python -m sphinx -W --keep-going -E -b html docs <saída>` com o venv `venv-verif07`: `build succeeded`, código de saída 0, sem aviso, 101 documentos. `sphinx -b linkcheck` com `linkcheck_ignore=^https?://` (externos ignorados): nenhum link quebrado (101 "unchecked" no `output.json`, sem `broken`); os links internos `{doc}`/`{ref}`/`{scpi}` são resolvidos pelo build `-W`.
  - "em redação"/"PREENCHER": nenhuma ocorrência em `docs/` (grep) nem nas fichas; a única no HTML era a descrição do esqueleto no CHANGELOG, trocada.
  - Cobertura contra `02-lacunas.md`: (a) 20 fichas ✓; (b) referência SCPI `docs/scpi.md` + `docs/scpi/*` ✓ (pré-existente, linkada com `{scpi}` em todas as fichas); (c) correlação `docs/medicao/correlacao.md` ✓ (reaproveitada nas fichas por script); (d) recalibração `docs/medicao/recalibracao.md` ✓ (linkada nas 07 e 17); (e) pendências `docs/projeto/pendencias.md` ✓ (cada `P-NN` da classe aparece na ficha: verificador); estado de validação `docs/projeto/estado-validacao.md` ✓.
  - README: seção "Mapa da documentação" com a descrição do site, comando de build e as linhas novas (`docs/classes/`, `docs/scpi/`, `docs/medicao/`, `docs/projeto/`, `docs/codigo/`, `docs/historico.md`). AGENTS: seção "Documentação (mapa)" reescrita (site, árvore, regra de atualizar a ficha e rodar o verificador). CHANGELOG/v1.15.md: seção nova "Fichas das 20 classes e revisão final do site", e fechamento dos dois trechos que chamavam as fichas de esqueleto (commit `b0a341b`).
  - Coerência Guia do código × fichas: li `classes_contrato`, `sinais`, `perfis`, `percurso-captura-trace` e o mapa de `mestre`; sem contradição de número ou nome. Três pontos de divergência de texto registrados em "Achados" (WAI de `arm()`, `assegurar_tensao_base`, nenhum quebra o build).
  - Navegador embutido (porta 8771; a 8766 pedida está ocupada por `KeysightCommunicationsFabric`, PID 4776, não tocado): 05, 06, 08 e `classes.html` em 1440x900, ~1024 e 375x812, claro e escuro. Vi: tema claro e escuro legíveis (selos e avisos com contraste), MathJax renderizado (16 a 26 fórmulas por página, 0 `mjx-merror`), `scrollWidth` do documento igual à largura da janela (sem rolagem horizontal da página) em desktop e celular, tabelas largas rolam dentro do próprio quadro no celular (`ficha 08`, tabela de amplitudes: 461 px dentro de 350 px), tabela de identificação cortada na coluna "Valor" no celular mas com rolagem, tabela do overview (9 colunas) rola no desktop estreito. **Limitação:** não percorri as 21 páginas visualmente; uma varredura por `iframe` em JavaScript não terminou (nulo após 40 s) e foi abandonada.
  - Servidor local encerrado ao fim (só o meu `http.server 8771`).

## Critério de Parada
Atendido.
- 20 fichas com as 12 seções + código + referências, sem "em redação" nem `PREENCHER`: `verificar-fichas.py` → "20 ficha(s) conferida(s); 0 divergência(s)".
- `docs/classes.md` aponta para as 20 e nenhum fato antigo se perdeu: tabela abaixo.
- Build sem warning (`rc=0`, `-W`, `-E`) e linkcheck interno sem quebra.
- `tests.test_offline`: `Ran 497 tests in 120.330s` / `OK`, sem testes pulados, rodado com `env\Scripts\python.exe` a partir do worktree; `git diff fa82f49 -- logica experimentos_nativos experimentos_waveform scripts tests` vazio (código inalterado).
- README, AGENTS e CHANGELOG/v1.15.md apontam para o site; cada `P-NN` da classe aparece na ficha e na página de pendências (tabela "Pendências por classe" de `docs/projeto/pendencias.md`, conferida por script).

## Premissas assumidas
As do orquestrador: (a) decisões em aberto (P-04, P-09 a P-15, P-20, P-23, P-25, P-26) entram como DECISÃO DO USUÁRIO: fichas das compostas e waveform trazem `:::{warning} Decisão em aberto` para P-04, P-09, P-11, P-12 e P-23, sem decidir (P-13, P-14, P-15, P-20, P-25, P-26 são globais sem efeito numa classe e ficam nas páginas de pendências); (b) `docs-site-plano/` fica como plano histórico fora do site; (c) citei sempre as linhas atuais do código; (d) transcrições reais só da AMETEK (as fichas usam o exemplo da referência SCPI; o Keysight segue "derivado do código"); (e) sem push nem merge.

Minhas:
- Seções: usei as 12 da spec na ordem dela e acrescentei "Como o código da classe funciona" (adendo) como 12ª e "Referências" como 13ª. A 12 do plano (`05-arquitetura-do-site.md`) difere da lista da spec; a spec prevaleceu e as "medidas de bancada" entraram nas seções de limites e validação.
- Histórico só de `CHANGELOG/v1.x`, de `v1.15` e do código atual; as análises de 21/09, 30/09 e 12/10 não foram reabertas (os CHANGELOG antigos dizem o que dizem).
- As tabelas numéricas vêm de scripts do scratchpad (não versionados): `gerar_fichas.py`, `medidas0710.py`, `valid0710.py`, `simbolos.py`; leitura somente do metadata e dos `.npz` de `resultados/` (nada escrito lá).
- Serena: usei `find_symbol` (com corpo), `find_referencing_symbols`, `search_for_pattern`, `read_file` e `get_symbols_overview` para ler o código e rastrear chamadores; as linhas do Serena são 0-based (somei 1) e a conferência final foi pelo `ast` (o `verificar-fichas.py`), que coincide com o Serena. Nenhuma ferramenta de edição de símbolo foi usada.
- Normas: os itens e faixas da IEEE 1159-2019 vêm da tabela de adequação do projeto; a norma não está no repositório, então cada ficha tem uma nota "NÃO VERIFICADO contra o texto da norma".
- Troquei os identificadores "spec NN" do texto das fichas pelo nome da seção do CHANGELOG (P-25 segue em aberto para o resto do repositório).

## Tabela de fatos de `docs/classes.md`
(F = fato do documento antigo; "ficha NN" = `docs/classes/NN-*.md`; "classes.md §n" = a página reescrita.)

| # | Fato antigo | Onde está agora |
|---|---|---|
| 1 | Especificação original `experimentos.txt`; o documento descrevia o código em `d37e403`; faixas em `perfis.md`; criar classe em `estender.md` | `classes.md` (parágrafo de abertura, carimbo `fa82f49`) |
| 2 | 200 ms = 6000 amostras a 30 kSa/s, em pu, por `gerar(t, f0, capture_index, rng)`; simulado só `gerar`; bancada nativa ou waveform | `classes.md` (resposta de abertura); cada ficha §3 |
| 3 | Tabela das 20 classes (arquivo, mecanismo, parâmetros `literatura`, sorteio F/I/D, padrão) | `classes.md` §1 (tabela com link e estado) |
| 4 | Fontes: `capturas_padrao` e sorteio conferidos por leitura e por `capturas_efetivas_da_classe`; 50 capturas planejadas | `classes.md` §1 (nota de fontes) e §4 |
| 5 | Compostas 10–16 sorteiam com `perfis.composto`; desligado, valores fixos de `perfis.md` | `classes.md` §1; fichas 10–16 §3 e §5 |
| 6 | Início/duração: especificação fixa 60/60 (80 nas 08/09); `sortear_posicao`: início ≥ 1 ciclo, duração ½ ciclo a 200 ms − 2 ciclos, fase U(0°; 360°) a 0,1°; `set sorteio off` reproduz | `classes.md` §2 (fórmulas, constantes, limites a 50 e 60 Hz) e "Onde o código difere" |
| 7 | 05: modelo ≤ 20 % é a senoide clipada normalizada por rms; só 30 % usa a soma 3.ª/5.ª/7.ª | `classes.md` "Onde difere"; ficha 05 §3 |
| 8 | 07 e 17: entalhes em todos os ciclos (IEEE 1159-2019, 4.4.5.4), não 4 ciclos | `classes.md`; fichas 07 §2–§3 e 17 §2–§3 |
| 9 | 18: rampa f0 ± 3 Hz (47 → 53 a 50 Hz); sorteio off: 57 → 63 | `classes.md`; ficha 18 §3 e §5 |
| 10 | 20: 145, 210 e 330 Hz; 150 Hz removido (2,5.ª harmônica a 60 Hz) | `classes.md`; ficha 20 §3 e §9 (com a ressalva de que a 50 Hz o motivo é outro) |
| 11 | Perfis `norma`/`fronteira` mudam 02, 03, 05, 06, 10–16, 20 | `classes.md`; cada ficha §5 (tabela gerada) |
| 12 | A especificação cita 400 capturas por nível; real = `SIM_CAPTURES_PER_CLASS` ou plano da bancada | `classes.md` "Onde difere" e §4 |
| 13 | Capturas por classe: `max(set capturas N ou REAL_CAPTURES_PER_CLASS, padrão)`, por nível em 02/03/05 (`Config.capturas`, `dimensionar_capturas`); padrão 3 em 04, 06–17, 19, 20; 1 nas demais; 50 planejadas | `classes.md` §4; fichas 02, 03, 05 §3 (consequência: só o nível 0 sem `set capturas`) |
| 14 | Sem `set capturas` sorteiam (08 aplica o impulso máximo seguro); com `set capturas` 04/06/09/19 cobrem por `linspace` (`valor_para_captura`) e a 08 faz rampa de caracterização | `classes.md` §4; fichas 04, 06, 08, 09, 19 §3 |
| 15 | Seed `BASE_SEED + int(id) × 1 000 000 + indice_global`; 04 e 19 repetem em `configurar()` (`04.py:36`, `19.py:32`), só vale com `capture_index == indice_global` | `classes.md` §4; fichas 04 e 19 §3, §9 e §12 (linhas atuais 37 e 33) |
| 16 | 08 §3: modelo de impulso de 5–10 pu e 50 µs; a bancada não o reproduz; descrição "impulso filtrado, pico + oscilação de 7,5–10 kHz que morre em < 0,5 ms" | ficha 08 §1 e §4; `classes.md` §5 |
| 17 | 08 limitação 1 (amplitude): teto 0,9 × `max_peak_v` = 374,2 V (2,084 pu a 127 V); amplitudes seguras 1,618; 1,344; 0,776; 0,360; 0,742; 0,285 pu; `SOBRESSINAL_DO_DEGRAU` 0,55 e `SUBSINAL_DO_DEGRAU` 0,70 (medidos 0,38–0,457 e 0,55–0,58) | ficha 08 §4 (tabela recalculada offline com a classe real, com pico/vale previstos e quem limita) |
| 18 | 08 limitação 2 (velocidade): 200 µs para 10–90 %, o impulso de 50 µs acaba antes da subida | ficha 08 §4 (quirk A21; a palavra "datasheet" saiu: a fonte citada é o quirk) |
| 19 | 08 limitação 3 (representação): 1024 pontos por ciclo (19,5 µs a 50 Hz), impulso em 3–4 pontos | ficha 08 §4 (acrescenta 16,3 µs a 60 Hz) |
| 20 | 08 posição: 80 ms a 60 Hz; a 50 Hz cai na fronteira e a fonte tocou a 100 ms (3 capturas de 07/10); sorteio leva a 90 ms, nunca < 30 amostras (1 ms) (`08.py:34,81-98`); validação ≤ 10 amostras (`conferir_posicao_do_evento`); mecanismo NÃO VERIFICADO (`classe08_fronteira_REVISAR.md`); fora do sorteio porque o sobressinal foi calibrado para um ponto de partida | ficha 08 §3, §4, §7, §12 e §13 (a referência ao arquivo de análise foi mantida) |
| 21 | 05 teto: `MAX_CSINE_THD_PCT = 20` (`ametek_orm.py:156`, hoje 163); `literatura` 5/10/15/20 por CSINusoid e 30 por TRACe (`usar_trace`); `norma` todos ≤ 20; nível de 2 % e rms interno não verificados | ficha 05 §3, §4, §5 e §11 (P-10) |
| 22 | 05 nível de 30 %: rms 0,738 pu, fundamental 1 pu; ≤ 20 %: rms 0,707 e fundamental 0,98–1,00; `LIST:VOLTage` = 1,044 × base, pico 0,825 pu; correlação programada × modelo 1,0000; `gerar()` não muda | ficha 05 §3 (tabela com coluna de fundamental calculada) e §4 |
| 23 | 06 e a média por ciclo: TRACe de média zero; média não nula por ciclo (vazamento espectral f0 ± f_fl, cresce com f_fl/f0); rms 0,002–0,032 (até 0,044); correlação 0,77–1,00, mediana 0,90–0,97; 0,9999 sem a média; sem offset por passo no manual; nada foi mudado | ficha 06 §4 (com as tabelas por perfil e por faixa de flicker) |
| 24 | 09 e o impulso em 100 ms: `diag_ciclos_trace.py` e `modelo_lista_fonte.py` aceitam a 09 sorteada (`PendentesCorrelacaoDisturbioTests`); 100 ms cai dentro do evento em ~18 %; mecanismo NÃO VERIFICADO (A25) | ficha 09 §4 (18,1 % a 50 Hz, 17,1 % a 60 Hz, o nome do teste e as medidas offline de 2026-10-16) |
| 25 | `toctree` das 20 fichas | `classes.md` (fim) |

Nenhum fato foi descartado; os números de linha antigos (`mestre.py:810`, `730`, `1517`, `1536-1540`, `04.py:36`, `19.py:32`, `ametek_orm.py:156`) foram substituídos pelos atuais e conferidos.

## Passos para importar no Read the Docs
1. Ter (ou criar, pelo próprio usuário) uma conta em readthedocs.org e entrar com a conta do GitHub que é dona do repositório (assim o serviço vê o repositório e instala o webhook sozinho). Criar conta e conceder o OAuth são ações do usuário.
2. O branch com o site tem de estar no GitHub. Hoje está só local (`docs/site-readthedocs`, 14 commits sobre `fa82f49`; nenhum push foi feito). Empurrar o branch (ou fazer o merge na `main`) é decisão do usuário.
3. No painel: "Import a Project" → escolher o repositório `https://github.com/DenisLN/anti-synthetic-data/` (a URL que `docs/conf.py` usa em `source_repository`) → nome do projeto (define o domínio `<nome>.readthedocs.io`) → branch padrão `main`.
4. O serviço lê `.readthedocs.yaml` da raiz: Ubuntu 24.04, Python 3.12, `docs/conf.py`, `fail_on_warning: true`, dependências de `docs/requirements.txt`. Python 3.12 **não foi testado** (passou em 3.11.9 e 3.14.7): o primeiro build é o teste.
5. Versões: em "Versions", ativar `latest` (aponta para o branch padrão) e, depois de congelar a v1.15, a tag `v1.15`, que vira `stable` (P-20: a tag, o release no GitHub e o Zenodo são decisão do usuário). Enquanto o site só existir no branch `docs/site-readthedocs`, ativar esse branch como versão para ver a primeira build.
6. Em "Admin → Advanced settings": idioma `pt_BR`; "Build pull requests for this project" é opcional.
7. Conferir a primeira build: Mermaid e MathJax vêm de CDN (jsDelivr) em tempo de leitura; os PDFs e `docs/manuais_txt/` ficam fora do site (`exclude_patterns`); licença/visibilidade do repositório e dos manuais (P-20, R-1 do plano) precisam ser decididas antes de tornar o projeto público.

## Pendências que exigem o usuário
- Importar o repositório no Read the Docs e empurrar o branch (passos 1 a 3).
- Decisões em aberto que as fichas só repetem: P-04, P-09, P-11, P-12, P-23 (nas fichas); P-13, P-14, P-15, P-20, P-25, P-26 (nas páginas de pendências).
- Decidir se o achado da 18 (abaixo) vira pendência `P-32`; acrescentar à página de pendências é texto, mas muda a contagem "31" em várias páginas.
- Decidir se `docs-site-plano/verificar-fichas.py` fica onde está (o `AGENTS.md` o cita) ou se vai para `scripts/` (isso exigiria autorização, a pasta é de código).

## Limitações de escopo
- Sem hardware: nenhum comportamento da v1.15 na bancada foi verificado (P-01); as fichas rotulam isso (NÃO VERIFICADO) e usam só as sessões de 07/10/2026 (código `994e170`, árvore suja).
- A norma IEEE 1159-2019 não está no repositório: itens e faixas citados da tabela do projeto, sem conferência contra o texto.
- O código é somente leitura nesta spec: os achados abaixo não foram corrigidos.
- A inspeção visual do site foi por amostragem (4 páginas, 2 larguras, 2 temas); a build no Read the Docs não foi testada (não há conta nem push).
- Porta 8766 indisponível (ocupada pelo serviço da Keysight): usei 8771.

## A missão resolve o contexto?
Sim: as 20 fichas, a visão geral, o verificador e a revisão final estão prontos e verificados; nada nos achados inviabiliza a missão. Falta só a decisão do usuário sobre publicar (import e push).

## Achados
Gravidade ao lado; "(código)" = sem alteração, somente leitura.
1. **MÉDIA-BAIXA (código)** `AmetekMX30.frequency_drift_list` (`ametek_orm.py:1066-1106`) não define `_transiente_esperado`; só `trigger_step`/`trigger_pulse` o definem e só `program_capture` o zera. Se a 18 roda logo depois de uma classe STEP ou PULSe na mesma conexão (sem TRACe no meio), `arm()` confere a lista contra o STEP anterior e recusa a captura. Reproduzido offline com a fonte simulada (`trigger_step(127)` + `frequency_drift_list(57, 63, ...)` + `_conferir_transiente_programado()` → "esperado 'STEP', lido 'LIST'"). Não ocorre em `run all` nem em `run 18`; ocorre em `run 01-05,18` e com `BATERIA_EXCLUIR` tirando 06–17. NÃO VERIFICADO na bancada. Registrado em um `:::{caution}` na ficha 18 e no CHANGELOG. Sugestão: zerar `_transiente_esperado` no início de `frequency_drift_list`.
2. **BAIXA** O motivo do `20.py:8-10` para tirar o 150 Hz ("2,5.ª harmônica a 60 Hz") não vale (2,5 não é inteiro); o motivo que vale é que **a 50 Hz 150 Hz é a 3.ª harmônica**. Registrado na ficha 20.
3. **BAIXA** Divergência de explicação do `*WAI` de `arm()`: o comentário do código e a seção 3 de `docs/scpi/sequencias.md` o atribuem à troca STEP → PULSe sem reconexão; o CHANGELOG da v1.7 diz que ele "não resolveu sozinho" e que a causa determinística era `SOURce:VOLTage:OFFSet` fora de `ACDC` com a fila não consultada. Registrado nas fichas 01 e 02 (vale o código: o `*WAI` e o `assert_no_errors` ficam).
4. **BAIXA** `Bancada.assegurar_tensao_base` parece redundante desde a v1.14: `from_env` chama `verificar_cadeia_de_medicao` → `recuperar_estado_seguro`, que faz `fonte.voltage = base_voltage_rms` antes da primeira classe. A docstring de `assegurar_tensao_base`, `docs/codigo/mestre.md:114` e `docs/codigo/percurso-run.md:37` ainda descrevem a 01 como a que eleva a tensão. NÃO VERIFICADO na bancada (leitura de código). Registrado na ficha 01.
5. **MÉDIA (dado)** As três sessões de 07/10 têm `versao_codigo = 994e170-dirty` no metadata (árvore suja), contra a regra "toda sessão de coleta sai de commit limpo". Relevante para P-30/P-20 (o que é "piloto").
6. **MÉDIA (operação)** Com os padrões (`capturas_padrao` = 1), **a 02, a 03 e a 05 rodam só o nível 0** (0,1 pu, 1,1 pu, THD de 5 %); os cinco níveis exigem `set capturas N`. Está dito em `classes.md` §4 e nas três fichas; vale conferir se o roteiro de bancada e o texto do README (que recomendam `run all`) deixam isso claro.
7. **INFO (dado novo, offline)** Classe 19 em 07/10: a média da janela medida acompanha o CC programado com inclinação 1,0 e desvio constante por sessão (+1,97 V, −1,3 V, −1,6 V, da ordem de 1 LSB: erro de zero do canal, B5/K10); a amplitude CA é 0,943, 0,951 e 0,938 pu, igual nos três níveis de offset (reproduz os 0,938–0,951 da A19: o déficit não depende do offset). Na ficha 19.
8. **INFO (dado novo, offline)** Classe 08: o previsto de 07/10 ficou 6 a 11 % acima do medido nas seis capturas; hoje (sobressinal 0,55) o pico previsto a 127 V/60 Hz é 280,3 V (era 251 V). Os offsets de 07/10 contra o teto: nenhuma captura tocou 374,2 V.
9. **BAIXA (plano)** `docs-site-plano/03-fontes-por-classe.md` diz que a 14 foi "reduzida a 48 %: swell aplicado 1,109 pu" na v1.13; o CHANGELOG da v1.13 mostra `swell_pu_bancada=1.15` (e "1,109" não está em nenhuma fonte lida). Usei 1,15 nas fichas.
10. **BAIXA** Comentário de `05.py:62-63` diz que `configurar` só é chamado "para os 4 níveis dentro do teto": com o perfil `norma` são 5 (a lógica só depende de `usar_trace`).
11. **BAIXA** Fundamental da CSINusoid a 5 % calculada por FFT em 0,9988; o CHANGELOG (spec de pendentes da correlação) dá 0,9987 (arredondamento de grade diferente). Na ficha 05 vale o meu cálculo, rotulado como offline.
12. **INFO** `P-30`: a 230 V/50 Hz só 15 das 20 classes têm metadata em `resultados/` (02, 03, 04, 08, 16 faltam); coerente com o estado de validação.
13. **INFO** O `docs/medicao/correlacao.md` §3 só tem as classes 05, 06, 08, 09 abaixo de 0,90 (e 07/17 no limite); a 03 (0,943–0,945) é a única de degrau por PULSe abaixo de 0,95 — explicação compatível (erro de 0,2–1,4 % da fundamental), não isolada: ficha 03 diz isso.
14. **NÃO VERIFICADO** Build com Python 3.12 do Read the Docs; MathJax/Mermaid por CDN em rede restrita; efeito do sorteio e dos perfis na bancada; a norma IEEE 1159-2019.
15. **BAIXA (ambiente)** Os arquivos do worktree têm CRLF (`core.autocrlf`) enquanto o repositório é LF (`.gitattributes`); os avisos `CRLF will be replaced by LF` do git são inofensivos.
