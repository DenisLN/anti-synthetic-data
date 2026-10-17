# AMETEK: comandos que falham ou não são usados

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` {bdg-success}`VERIFICADO NA BANCADA`

**Pergunta:** que comandos do manual a Rev. 5.53 rejeita, ignora ou deixa sem resposta? **Resposta:** `CSINe` (`-256`), o sufixo `:COUNt` de `LIST:REPeat` (`-113`) e as consultas `SOURce:MODE?` e `SOURce:FUNCtion:SHAPe?` (sem resposta e com `-113` preso na fila); o projeto os evita, e cada evitação tem teste ou comentário que registra a medida.

Estas entradas usam rótulos `scpi-nf-*` e não aparecem como alvo do papel `{scpi}`, para não competirem com a entrada do comando que funciona.

(scpi-nf-csine)=
## `SOURce:FUNCtion:SHAPe CSINe`

{bdg-info}`OFFLINE`

**O que acontece?** **A forma abreviada `CSINe`, que o manual usa como parâmetro de `FUNCtion:SHAPe`, é rejeitada.**

A Rev. 5.53 devolve `-256 "File name not found"`. Ela resolve `FUNCtion:SHAPe` como busca no catálogo de formas e só reconhece o nome completo `CSINusoid` (quirk A6, v1.6). O código envia {scpi}`SOURce:FUNCtion:SHAPe` `CSINusoid` (`configure_harmonics_csine`).

**Onde o código lida com isso:** `AmetekMX30.configure_harmonics_csine` ([ametek_orm.py:965](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L965)).

(scpi-nf-repeat-count)=
## `SOURce:LIST:REPeat:COUNt e LIST:REPeat:COUNt`

{bdg-info}`OFFLINE`

**O que acontece?** **O sufixo `:COUNt` do manual é rejeitado, com ou sem o prefixo `SOURce:`.**

`-113 Undefined header`. Só `SOURce:LIST:REPeat` (com prefixo, sem `:COUNt`) é aceito (quirk A5, v1.5). O teste isolado que exercita as variantes de cabeçalho é `_test_list_repeat_count` em `logica/preflight_new.py`, que **espera** a rejeição. A forma certa está em {scpi}`SOURce:LIST:REPeat`.

**Onde o código lida com isso:** `preflight_new._test_list_repeat_count` ([preflight_new.py:596](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/preflight_new.py#L596)).

(scpi-nf-mode-consulta)=
## `SOURce:MODE? e SOURce:FUNCtion:SHAPe?`

{bdg-info}`OFFLINE`

**O que acontece?** **As duas formas existem como comando, mas **não como consulta** na Rev. 5.53, apesar de `[SOURce:]MODE?` constar do manual (p. 98).**

A consulta não obtém resposta (o timeout inteiro é perdido) e ainda deixa `-113` na fila, atribuído depois ao comando seguinte (A8, v1.6). Por isso `_forma_atual` e `_modo_saida` são rastreados em Python, e `_conferir_transiente_programado` deixa as duas consultas de fora. Para esperar a fonte voltar a falar, o código usava `*IDN?` (`aguardar_resposta`) e hoje usa {scpi}`*WAI`.

**Onde o código lida com isso:** `AmetekMX30._conferir_transiente_programado` ([ametek_orm.py:1781](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L1781)).

(scpi-nf-fase-consulta)=
## `TRIGger:SYNChronize:PHASe?`

{bdg-info}`OFFLINE`

**O que acontece?** **Nunca foi enviada: não há leitura de volta da fase de disparo.**

`definir_fase_de_disparo` só escreve ({scpi}`TRIGger:SYNChronize:PHASe`) e confere a fila, porque um cabeçalho de consulta não implementado deixa `-113`. {bdg-warning}`NÃO VERIFICADO` Se a Rev. 5.53 implementa a consulta: ninguém testou (P-05).

**Onde o código lida com isso:** `AmetekMX30.definir_fase_de_disparo` ([ametek_orm.py:843](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L843)).

(scpi-nf-remote)=
## `SYSTem:REMote`

{bdg-info}`OFFLINE`

**O que acontece?** **Nunca é enviado: o painel frontal da fonte permanece ativo durante a bateria.**

O manual (p. 119) descreve `SYSTem:REMote`; o projeto prefere não travar o painel, onde o operador confere `OUTPUT OFF`.

(scpi-nf-opc)=
## `*OPC? como sincronismo`

{bdg-info}`OFFLINE`

**O que acontece?** **Existe e responde, mas não sincroniza: ver {scpi}`*OPC?`.**

Responde `1` ou `0` na hora; `AMETEK_SINCRONISMO` fica em `ESR`.

(scpi-nf-abreviadas)=
## `Formas abreviadas (`TRAC:DATA`, `VOLT:MODE`, ...)`

{bdg-info}`OFFLINE`

**O que acontece?** **Só o simulador as aceita; o caminho real envia sempre as formas longas.**

`_simulate_write` e `_simulate_query` reconhecem abreviações do manual (`TRAC:DEF`, `FREQ:MODE`, `*RST`). Na fonte real nenhum código as envia. Há um risco **latente**: `_SEM_SINCRONISMO` só cobre as formas longas em maiúsculas (`TRACE:DATA`, `TRACE:DEFINE`, `TRACE:DELETE`), enquanto `_GRAVA_FLASH` cobre também `TRAC:DATA`, `TRAC:DEF` e `TRAC:DEL`: quem passasse a enviar `TRAC:DATA` na fonte real faria `write()` consultar a fonte logo após a gravação (A2).

**Onde o código lida com isso:** `AmetekMX30._SEM_SINCRONISMO` ([ametek_orm.py:177](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/ametek_orm.py#L177)).
