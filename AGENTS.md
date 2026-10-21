# Instrução para agentes de IA no computador Windows da bancada

O projeto deve estar em `C:\Users\denis\TCC\code` (ajuste o caminho conforme a
máquina). A fonte e o osciloscópio já devem estar conectados assim:

- AMETEK MX30: porta USB da fonte, exposta pelo driver como PyVISA
  `ASRL10::INSTR` (`COM10`), 115200 baud confirmados no equipamento real.
- Keysight DSO-X 4034A: `USB0::0x0957::0x17A4::MY59240844::0::INSTR`.
- BNC: AMETEK Trigger Out -> Keysight EXT Trigger.
- O cabo USB da AMETEK deve permanecer conectado. Não usar simultaneamente o
  conector DB9 RS-232.

## Fluxo do operador (a partir da v1.7)

A operação deixou de ser um fluxo fixo de 5 etapas obrigatórias. O operador
roda:

```powershell
cd C:\Users\denis\TCC\code
scripts\START_BENCH.cmd
```

Isso prepara o venv, pergunta o fator EXATO da probe de tensão e a
tensão/frequência do teste (uma vez, no início do processo — ver por quê na
`docs/operacao.md`) e entrega o resto para a CLI interativa
(`logica/cli.py`). Dentro da CLI, `help`/`?` imprime a referência completa;
resumo:

| Comando | Energiza? | Equivale a |
|---|---|---|
| `status`, `list` | não | — |
| `comm` | não | antiga etapa Communication |
| `trigger` | não | antiga etapa Trigger |
| `lowvoltage` | sim, tensão base | antiga etapa LowVoltage — agora OPCIONAL, só para recomissionar (fiação/probe mexidas), não roda mais automaticamente dentro de nada |
| `native` | sim | antiga etapa NativeCommands (`preflight_new.py --native-commands`) |
| `run <NN\|nome>` | sim | roda uma classe isolada |
| `run all` | sim | bateria completa das 20 classes, resiliente por classe (ver abaixo) |

> **Nota (v1.15, conferida no código em 2026-10-13):** `lowvoltage` e `native`
> usam a tensão base digitada no início (`BASE_VOLTAGE_RMS`), nunca 5 V fixos.
> O rótulo "5V" e a confirmação `ENERGIZAR-5V` foram removidos: `lowvoltage`
> agora pede `ENERGIZAR-TESTE` e mostra a tensão real. `logica/preflight.py`
> foi removido; só existe `logica/preflight_new.py`. Para recomissionar a 5 V,
> inicie o `START_BENCH` digitando 5 V. Ver `docs/operacao.md`.

Todas as confirmações físicas (fator de probe, Vrms/Hz, e a string digitada
antes de energizar — `ENERGIZAR-TESTE`, `ENERGIZAR-COMANDOS`,
`EXECUTAR-CLASSE-<NN>`, `EXECUTAR-20-CLASSES`, todas case-sensitive) continuam
existindo exatamente como no fluxo antigo. Não invente o fator de probe e não
automatize essas confirmações.

Se algo falhar de um jeito que indique infraestrutura real comprometida (porta
serial caiu, impossível confirmar OUTPUT):

1. confirmar fisicamente OUTPUT OFF no painel da AMETEK;
2. não executar de novo automaticamente;
3. entregar ao usuário o arquivo mais recente de `logs\startup-bench-*.log`
   (ou `logs\preflight_new-*.log` para falhas de `native`);
   **Nota (conferida no código em 2026-10-13):** nenhum código gera mais
   `logs\startup-bench-*.log`. Desde a v1.15 a CLI grava, para `comm`/
   `trigger`/`lowvoltage`/`native`, o mesmo `logs\preflight_new-<etapa>-*.log`
   do script direto (`preflight_new.run_com_log`). Hoje, entregue: para
   `run`/`run all`, `sessao.log` e `scpi_transcricao.log` da pasta
   `resultados\sessao_<timestamp>[_runNN]` mais recente; para `comm`/`trigger`/
   `lowvoltage`/`native`, o `logs\preflight_new-*.log` mais recente;
4. não remover validações de IDN, timeout, tamanho de waveform ou SCPI.

Uma falha isolada de EXPERIMENTO (RMS fora de tolerância, timeout de trigger,
exceção em `gerar()`) durante `run all` **não** é motivo para parar e chamar o
usuário — `Bancada.executar_bateria()` já isola, registra e segue para a
classe seguinte sozinha (ver "Limites inegociáveis" abaixo). Só pare e avise
diante de uma falha de infraestrutura real.

Captura de corrente permanece desligada por padrão. Não ativá-la sem fator da
probe de corrente e corrente-base fornecidos pelo usuário.

## O que pode ser refatorado

Este arquivo historicamente dizia "não refatore, não rode testes separados".
Essa restrição está **suspensa** para os módulos abaixo, e continua suspensa
para qualquer sessão futura que precise mexer neles (autorização registrada
em 2026-09-09, ver `CHANGELOG/v1.7.md`):

- `logica/mestre.py`, `logica/ametek_orm.py`,
  `logica/preflight_new.py`, `logica/cli.py`, e os scripts em `scripts/`.
- `tests/test_offline.py` pode ser rodado e editado livremente — não toca
  hardware, roda os dois ORMs em modo simulado.

Nenhuma outra restrição foi suspensa. Em especial, os limites físicos abaixo
continuam absolutos.

### Autorização de 2026-10-07 (tarefas em `arquivo/analises:docs/TAREFAS_NUVEM_2026-10-07.md`)

O dono autorizou, para cumprir essas tarefas (capturas padrão por classe,
seed na CLI, capturas = max(CLI, padrão), 220/380 V), editar também:

- `logica/sinais.py`, `logica/oscilloscope_orm.py`,
  `logica/calibracao_extremos.json` e `logica/analisar_sessao.py`;
- `experimentos_nativos/NN.py` e `experimentos_waveform/NN.py` **só** para
  atributos de classe (ex. `capturas_padrao`) e ganchos de bancada
  (`forma_para_bancada`, `ciclos_excluidos_da_validacao` etc.) — **nunca**
  mudando o que `gerar()` produz para uma dada seed (é o dataset).

Os limites inegociáveis abaixo continuam valendo integralmente: 220 V ou
380 V não autorizam subir `max_voltage_rms`/`max_peak_v` acima do hardware
(300 Vrms por fase, 425 Vp). Ver CHANGELOG/v1.12.md para o que mudou na
v1.12 (writes sincronizados por `*ESR?`, bloqueio prévio de pico,
`VOLTage:HIGH` = limite RMS, e o achado de segurança: nunca consultar a
fonte logo após `TRACe:DATA`).

### Autorização de 2026-10-12 (perfis de faixas; `CHANGELOG/v1.15.md`)

O dono autorizou mudar o que `gerar()` produz para uma dada seed, para
implementar os perfis `norma`, `literatura` e `fronteira` (`set perfil`):

- `experimentos_nativos/02.py`, `03.py`, `05.py` e
  `experimentos_waveform/06.py`, `10.py`–`16.py`, `20.py`: faixas e níveis
  passam a ser lidos de `logica/perfis.py` pelo perfil ativo;
- `logica/mestre.py`, `logica/cli.py`, `logica/analisar_sessao.py`,
  `scripts/relatorio_limites_bancada.py`: plumbing do perfil.

Condições: o perfil `literatura` (padrão) continua reproduzindo byte a byte o
`gerar()` do commit 34a0d82 (teste em `tests/test_offline.py`,
`PerfisDeFaixasTests`); as mudanças entram juntas numa versão congelada antes
da próxima campanha; as 63 capturas de 07/10 ficam como piloto
(retificação de 21/10/2026, P-30: contagem histórica não verificável; as sessões de
07/10 não estão disponíveis e o número não é usado como resultado). Início,
duração, fase e forma das classes não mudam. Os limites inegociáveis abaixo
continuam valendo integralmente (`max_voltage_rms`, `max_peak_v`,
`max_current_a`, pré-validação de pico).

### Autorização de 2026-10-12 (início, duração e fase sorteados; `CHANGELOG/v1.15.md`)

O dono autorizou também que `gerar()` passe a sortear início, duração e fase
da senoide base (motivo e medidas em `CHANGELOG/v1.15.md`, seção de início, duração e fase), na mesma versão
congelada dos perfis, o que substitui a frase "início, duração, fase e forma
não mudam" da autorização acima. Editados: `experimentos_nativos/01.py`–`05.py`,
`18.py`, `19.py`; `experimentos_waveform/06.py`, `07.py`, `09.py`–`17.py`, `20.py`
(a 08 fica de fora); `logica/mestre.py` (`Sorteio`, pré-trigger por captura),
`logica/oscilloscope_orm.py` (só `definir_pre_trigger`), `logica/cli.py`
(`set sorteio`, estimativa de gravações), `logica/analisar_sessao.py`,
`scripts/recalibrar_extremos.py`. `SORTEIO=0` / `set sorteio off` reproduz byte a
byte o `gerar()` de 34a0d82. Limites e validações abaixo intactos.

### Autorização de 2026-10-12 (compostas 10 a 16, classe 08, classes 05, 07, 17 e 18; `CHANGELOG/v1.15.md`)

O dono autorizou mudar o que `gerar()` produz para uma dada seed, como parte da
mesma versão congelada dos perfis, nestas partes:

- compostas 10 a 16: parâmetros sorteados (sag, swell, THD, flicker e oscilação)
  em `logica/perfis.py` (`FAIXAS_SORTEADAS`, `composto`) e em
  `experimentos_waveform/10.py` a `16.py`. Com `set sorteio off`, os valores
  fixos anteriores voltam byte a byte;
- classe 08 (`experimentos_waveform/08.py`): impulso a pelo menos 1 ms de uma
  fronteira de ciclo, com a conferência de posição na validação física
  (`conferir_posicao_do_evento`, `mestre.py`);
- classes 05, 07, 17 e 18 (`experimentos_nativos/05.py`, `experimentos_nativos/18.py`,
  `experimentos_waveform/07.py`, `experimentos_waveform/17.py`; `logica/sinais.py`):
  nível e forma da 05 (`senoide_clipada_pu`), entalhes em todos os ciclos na 07
  e na 17 (`aplicar_entalhes_continuos`), e rampa de frequência f0 ± 3 Hz na 18.

Os limites inegociáveis abaixo continuam valendo integralmente (`max_voltage_rms`,
`max_peak_v`, `max_current_a`, pré-validação de pico).

### Autorização de 2026-10-13 (crista da validação e `set perfil todos`; `CHANGELOG/v1.15.md`)

O dono decidiu, em 2026-10-13, que a validação física da crista usa a calibração
de extremos (`sinais.comparar_fisicamente`, parâmetro `fator_crista`;
`mestre.py`, `fator_extremo_efetivo_para_validacao`), em vez de afrouxar a
tolerância. Na mesma data autorizou editar `logica/perfis.py` **só com funções
novas** (`depende_do_perfil`, `classes_independentes_do_perfil`,
`plano_de_perfis`), sem tocar `FAIXAS` nem `FAIXAS_SORTEADAS`.

### Autorização de 2026-10-13 (um `.npz` por classe; `CHANGELOG/v1.15.md`)

O dono autorizou gravar tudo o que é da mesma classe no mesmo `.npz`
comprimido (perfis × versões; SNRs em arquivos à parte) e `set perfil todos`
(`run all` / `run <lista>` percorrem os três perfis na mesma sessão). Para isso
editou-se, além do que já estava liberado, `logica/recortar_margem.py` e
`logica/relatorio_html.py` (leitura dos dois formatos; `--perfis`, `--versoes`,
`--capturas`), `logica/analisar_sessao.py`, `scripts/gerar_ruido_janela.py`,
`scripts/gerar_tres_versoes.py`, o módulo novo `logica/sessao_io.py` e, em
`logica/mestre.py`/`logica/cli.py`, a gravação (`_salvar_captura`,
`_finalizar_gravacao`, `_salvar_classe_simulada`), `executar_bateria` e
`set perfil`. Não muda `gerar()`, o ruído, as validações nem os limites abaixo;
a resiliência por classe e a gravação atômica continuam. Quebra o formato dos
`.npz` das sessões NOVAS (aviso no `CHANGELOG/v1.15.md`); sessões gravadas antes
não são tocadas e continuam legíveis por `logica/sessao_io.py`.

## Limites inegociáveis (não mudar em nenhuma hipótese)

- `AMETEK_PORT=COM10` e `AMETEK_BAUDRATE=115200` continuam fixos e validados
  em `validate_bench_configuration()` (`logica/mestre.py`); não trocar
  porta/baud nem remover essa validação.
- Não remover nem enfraquecer validações de IDN, timeout, tamanho de waveform
  (6000 pontos) ou erros SCPI (`assert_no_errors`/`check_errors`) — inclusive
  as que ficaram MAIS específicas (ex.: o `assert_no_errors()` logo após
  `SOURce:FUNCtion:SHAPe:CSINusoid` em `configure_harmonics_csine()`, que
  corrigiu um erro que antes era atribuído ao comando SEGUINTE); nunca
  torná-las mais fracas.
- Não alterar `max_voltage_rms`, `max_peak_v` nem `max_current_a`, nem remover
  `ParameterOutOfBoundsError` em `ametek_orm.py`.
- Nenhum comando que energiza a saída pode rodar sem confirmação explícita
  digitada pelo operador (case-sensitive) — vale para a CLI de hoje e para
  qualquer fluxo futuro.
- A resiliência por classe (`Bancada.executar_bateria`) isola falhas de
  EXPERIMENTO mas continua abortando tudo, sem tentar de novo sozinho, diante
  de `CommunicationError` ou `FalhaFatalDeInstrumento` (serial caiu,
  impossível confirmar OUTPUT, impossível recuperar um estado seguro
  conhecido via `recuperar_estado_seguro()`). Não amplie o que conta como
  "falha de experimento recuperável" sem entender por que aquele tipo de erro
  específico é seguro de ignorar.
- O cache de TRACe em `program_capture()` (evita reescrever a Flash quando
  forma/tensão/frequência não mudaram desde a última chamada bem-sucedida na
  MESMA conexão) sempre reconfirma contra o instrumento (`TRACe:CATalog?`)
  antes de reaproveitar, e é automaticamente invalidado a cada reconexão
  (é um atributo da instância `AmetekMX30`, não algo persistido em disco). Não
  troque isso por um cache entre processos sem antes resolver como
  `AMETEK_CLEAR_USER_WAVEFORMS=1` (que apaga as TRACEs a cada conexão)
  invalidaria um cache assim.
- Captura de corrente permanece desligada por padrão (`CAPTURE_CURRENT=0`);
  não ativar sem `CURRENT_PROBE_ATTENUATION` e `CURRENT_BASE_A` fornecidos
  pelo usuário.

## Documentação (mapa)

`README.md` é a porta de entrada e traz o mapa; os detalhes estão em `docs/`
(`arquitetura`, `operacao`, `configuracao`, `limites_e_calibracao`, `classes`,
`perfis`, `scpi`, `quirks`, `decisoes`, `dataset`, `metadata`, `tres_versoes`,
`correlacao_disturbio`, `estender`, `diagnostico`, `testes`, `versionamento`,
`glossario`). Arquivos `.md` são livres para editar, **mas todo fato sobre
comportamento deve ser conferido no código (`arquivo:linha`)**; se o CHANGELOG
divergir do código, vale o código e a divergência é documentada. Relatórios
datados (`arquivo/analises:docs/analise-*/`, `arquivo/analises:docs/superpowers/`; branch `arquivo/analises`, fora de `docs/` desde 2026-10-13) e `CHANGELOG/vX.Y.md` fechados
são registro histórico: não se reescrevem.

## Como escrever sobre mudanças no código

1. Uma mudança lógica por commit, mensagem `tipo: resumo em português`
   (`feat`, `fix`, `docs`, `chore`, `merge`).
2. Toda mudança registra-se em `CHANGELOG/vX.Y.md` da versão em andamento, com
   as seções Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO
   (modelo em `docs/versionamento.md` §4). Diga o que foi medido e o que é
   hipótese; cite arquivo:linha, sessão e comando.
3. Mudar o que `gerar()` produz para uma seed exige autorização do dono
   registrada neste arquivo **antes**, fixtures byte a byte
   (`tests/fixtures/`) e declaração no CHANGELOG. Os limites inegociáveis
   abaixo nunca mudam.
4. Documente na hora: `docs/classes.md`, `docs/scpi.md` (comando novo),
   `docs/quirks.md` (comportamento novo do equipamento, com a fonte da medida),
   `docs/configuracao.md` (variável nova), `docs/metadata.md` (campo novo, só
   acrescentar).
5. Comportamento que parece errado: diagnosticar primeiro (`set diagnostico on`
   ou um script que chame as funções do projeto isoladamente, ver
   `docs/diagnostico.md`), registrar no branch `arquivo/analises`, em `docs/analise-AAAA-MM-DD/` (caminho
   dentro desse branch), e só então
   corrigir, com teste de regressão. Rode `tests.test_offline` antes de
   commitar.

## Como versionar

- Versão corrente: **v1.15, em andamento (sem tag)**. Cada versão é um
  `CHANGELOG/vX.Y.md`; ao congelar, tag git `vX.Y` anotada no commit com a
  árvore limpa e a suíte verde (descrição em `docs/versionamento.md` §3; a
  regra é descrita lá, tags só são criadas quando o dono mandar).
- Release no GitHub + arquivamento no **Zenodo** (DOI da versão exata) quando o
  dono congelar uma versão; o artigo cita esse DOI.
- **Toda sessão de coleta sai de commit limpo** (idealmente o da tag): o
  metadata grava `git_commit`, `git_sujo`, `versao_codigo`, `numpy_versao` e
  uma cópia de `calibracao_extremos.json`. `git_sujo` vale para alteração
  rastreada em qualquer arquivo e para arquivo novo não ignorado em `logica/`,
  `experimentos_nativos/`, `experimentos_waveform/` e `scripts/` (`mestre.py`,
  `info_do_codigo`); é recalculado a cada pasta de sessão, ou seja, a cada
  `run` da CLI. Commite tudo (inclusive arquivos novos e a calibração
  recalibrada). `versao_codigo` fica em cache no processo: reinicie a CLI
  depois de commitar.
- Trabalho pendente de bancada fica em branch/PR e é documentado como
  **pendente** (hoje: `feat/passo-final-sin`, PR #3), nunca como existente na
  `main`.
