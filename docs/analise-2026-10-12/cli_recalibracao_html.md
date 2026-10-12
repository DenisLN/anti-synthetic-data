# CLI: recalibração automática e relatório HTML

Branch main em cb3e957, alterações não commitadas. Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline` deu `Ran 370 tests ... OK` (356 antes, 14 novos em `CliRecalibracaoEHtmlTests`, `tests/test_offline.py:6586`).

## 1. `set recalibracao on|off`

- Estado em `SessaoCLI.recalibracao_ao_fim`, padrão `False` (`logica/cli.py:181`); tratamento do `set` em `cli.py:476-490`. Ligar imprime um aviso de que `logica/calibracao_extremos.json` será alterado.
- Gancho: `_fim_da_sessao` (`cli.py:647`) chamado ao fim do `run <NN>` que terminou OK (`cli.py:595`) e ao fim do `run all` (`cli.py:642`), com a saída já OFF e a `Bancada` fechada. `_recalibrar_ao_fim` (`cli.py:678`) importa `scripts/recalibrar_extremos.py` (`_importar_recalibrador`, `cli.py:671`) e chama `recalibrar([sessao], gravar=True, automatico=True)`.
- `scripts/recalibrar_extremos.py`: o corpo do antigo `main` virou `recalibrar()` (`:214`); `main` (`:318`) só faz o argparse e chama. A linha de comando não mudou (teste `test_recalibrar_extremos_main_continua_igual`).
- Modo `automatico` (garantias, `recalibrar_extremos.py:222-230,231,252,273-274,294`):
  - `substituir` com `automatico` levanta `ValueError`.
  - Fator da tabela existente: `max(medido, atual)`, como já era (nunca baixa).
  - Condição sem tabela própria NÃO é criada, só avisada.
  - Classe sem entrada na tabela só entra se o medido não ficar abaixo do fator efetivo que a bateria usou (`mestre.carregar_fatores_extremo` + `fator_extremo_da_classe`).
  - Só tabelas com alguma mudança são regravadas; sem mudança o arquivo não é tocado (teste `..._sem_mudanca_nao_reescreve_o_arquivo`).
- Cópia anterior: reaproveita `mestre.preparar_pasta_da_sessao`, que já copia `calibracao_extremos.json` para a sessão no início do run (`mestre.py:181-203`, chamada em `cli.py:198`). Nada duplicado. Se a cópia não existir, a recalibração não roda e avisa.
- Modo simulado (`BENCH_MODE` falso): não recalibra, avisa (teste `..._em_modo_simulado_nao_faz_nada`).

Saída (sessão sintética, calibração de teste; capturas em 127 V/60 Hz e em 230 V/50 Hz, esta sem tabela):

```
bancada> set recalibracao on
recalibração automática ao fim do run: ON
AVISO: ao fim de cada run FÍSICO logica/calibracao_extremos.json será ALTERADO (só sobe fator, nunca desce; condição nova não ganha tabela). A cópia anterior fica em <sessao>/calibracao_extremos.json e os run seguintes desta CLI já usam os fatores novos. Confira com 'git diff' antes de commitar.
...
==============================================================================
RECALIBRAÇÃO AUTOMÁTICA: 1 fator(es) de extremo MUDARAM em <...>\calibracao_extremos.json
  [127V_60Hz] classe 05: 1.000 -> 1.200  (1 captura(s))
Calibração anterior (início do run): <sessao>\calibracao_extremos.json
Os próximos run desta CLI já usam os fatores novos. Confira com 'git diff' e rode tests/test_offline.py antes de commitar.
==============================================================================
AVISO: condição 230V_50Hz sem tabela própria: NÃO criada automaticamente (uma tabela nova trocaria o fator conservador por um medido numa sessão só). Para calibrar: scripts/recalibrar_extremos.py <sessao> --gravar
AVISO: [127V_60Hz] classe 09: medido 1.111 abaixo do fator efetivo 1.500; não gravado (nunca diminui).
```

Achados:
- (média) `--gravar` na linha de comando cria tabela de condição nova com o medido de uma sessão, o que pode BAIXAR o fator efetivo em relação à regra conservadora de `mestre.carregar_fatores_extremo` (`mestre.py:536-566`). Por isso o modo automático não cria tabela nem grava classe abaixo do efetivo. É uma restrição além do pedido, para cumprir "nunca diminui um fator". O comportamento da linha de comando continua o de antes.
- (baixa) Como `carregar_fatores_extremo` lê o arquivo a cada chamada (`mestre.py:470-476`, sem cache), o `run` seguinte da mesma CLI já usa os fatores novos. É o desejado, mas muda a previsão de pico no meio de uma sessão de CLI.
- (baixa) `sessao.json` registra o SHA-256 da calibração do início do run (`mestre.py:205-209`); depois da recalibração o arquivo em uso tem outro hash. A cópia na sessão é a que bate com o `sessao.json`.
- (baixa) A `origem` da tabela regravada ganha o sufixo `[automático, CLI]` (`recalibrar_extremos.py:306`).

## 2. `set html on|off`

- Estado `SessaoCLI.html_ao_fim`, padrão `False` (`cli.py:182`); `set` em `cli.py:491-501`.
- Padrão OFF, por: (a) gerar o HTML recorta uma cópia de todos os `.npz` (inclui os três `snr_XXdb/`) e desenha ~4 figuras por captura com matplotlib: o relatório de uma bateria completa passa de 20 MB (limite de e-mail que o próprio `relatorio_html.py` avisa) e demora minutos; (b) ligado por padrão, o fim de uma sessão de horas ficaria preso nisso sem o operador pedir; (c) a recalibração, que altera arquivo versionado, também é OFF. Medido só na sessão sintética: 2 capturas, 0,2 MB, 1,3 s para recalibração + recorte + HTML; a extrapolação para uma bateria real NÃO foi medida (NÃO VERIFICADO).
- `_gerar_html_ao_fim` (`cli.py:712`) chama `relatorio_html.gerar_relatorio_recortado` (`relatorio_html.py:568`, nova): `recortar_margem.recortar_sessao(sessao, <sessao>/sem_margem)` e `gerar_relatorio` sobre a pasta recortada, dados puros, em `<sessao>/relatorio_<sessao>.html`. Os originais não são tocados (teste `test_html_ao_fim_gera_a_versao_recortada_sem_tocar_nos_originais`). Imprime caminho, tamanho e o aviso de >20 MB.
- Compatível com o ruído só na janela: `snr_XXdb/` tem 6000 amostras, `calcular_recorte` trata `n_amostras <= pontos` como `sem_margem` (`recortar_margem.py:85-88`), o recorte do arquivo puro continua `inicio_janela`/`indice_trigger`. Os níveis de ruído não entram no HTML automático (usar `relatorio_html.py <sessao>/sem_margem --snr 30`).
- (baixa) O resumo do relatório mostrava `Sessão: sem_margem` ao receber a pasta recortada; agora mostra `<sessao> (sem_margem)` (`relatorio_html.py:477-481`).

```
bancada> set html on
relatório HTML ao fim do run: ON
AVISO: ao fim de cada run a margem é recortada para <sessao>/sem_margem/ e o HTML da versão recortada é gerado (pode levar minutos e passar de 20 MB numa bateria completa).
...
Relatório HTML (versão recortada, 2 captura(s), 0.2 MB): <sessao>\relatorio_sessao_teste.html
```

## 3. `status` e `help`

- `status` (`cli.py:303-306`): `recalibração automática ao fim do run: ON   relatório HTML ao fim do run: ON`.
- `HELP_TEXT` (`cli.py:129-147`) documenta os dois; a mensagem de uso e a de chave desconhecida do `set` também (`cli.py:388-389,502`). Testes `test_padrao_off_e_set_liga_e_desliga` e `test_set_recusa_valor_invalido_e_help_documenta`.

## 4. Falha não derruba a sessão

- `_fim_da_sessao` (`cli.py:647-668`) envolve cada gancho em `try/except (Exception, SystemExit)` (`coletar` usa `SystemExit` quando não há `.jsonl`) e só imprime `AVISO: ... FALHOU (...)`. `KeyboardInterrupt` continua propagando até o laço da CLI.
- Os ganchos rodam depois de `self.ultimo_resultado` e do resumo, então não mudam o código de retorno nem o registro das classes (teste `test_falha_do_gancho_nao_muda_o_resultado_do_run_all`: retorno 0, `1/1 classes OK`).
- Não rodam após `BATERIA ABORTADA` por infraestrutura (retorno antecipado, `cli.py:621-624`) nem após `run <NN>` que falhou (`cli.py:593-595`): a falha pode ser de infraestrutura e `AGENTS.md` manda não seguir automaticamente. Testes `test_run_all_abortado_por_infraestrutura_...` e `test_run_all_dispara_os_ganchos_...` (com uma classe FALHOU, os ganchos rodam e o retorno continua 1).
- Nada em `mestre.py`, na resiliência por classe nem nas confirmações digitadas foi alterado; o gancho ficou na CLI, não em `mestre.executar_bateria`.

## 5. Testes

14 novos (`tests/test_offline.py:6586`): padrão e `set`; valor inválido e help; recalibração só sobe e guarda a cópia; sem mudança não reescreve; não cria tabela nem baixa o efetivo; recusa `substituir`; modo simulado; sem a cópia; `main` do script igual; HTML numa sessão sintética (formato bancada, 8100 pontos, `snr_30db/`); falha dos dois ganchos; `run all` com ganchos ligados/desligados, abortado e com gancho falhando. Os testes usam calibração temporária (`mestre.CALIBRACAO_EXTREMOS_PATH` patched), nunca o JSON real.

## NÃO VERIFICADO

- Execução num `run`/`run all` com hardware real (sem hardware; o gancho foi testado com `Bancada.from_env` falsa). Em particular, que `sessao_dir/metadata/*.jsonl` de uma sessão real tenha `pico_medido_v`/`vale_medido_v` nas capturas e que a recalibração sobre ela mude os fatores como esperado; a reprodução de fatores com sessão real segue coberta só por `test_recalibracao_reproduz_os_fatores_da_sessao_de_origem`.
- Tempo e tamanho do HTML numa bateria completa (só medido com 2 capturas).
- `_importar_recalibrador` assume `python logica/cli.py` (ou `logica/` no `sys.path`) para que `import mestre` do script seja o mesmo módulo da CLI; testado só via `unittest`.
- Execução concorrente: dois processos da CLI recalibrando ao mesmo tempo não são tratados (gravação não é atômica, como já era em `--gravar`).
