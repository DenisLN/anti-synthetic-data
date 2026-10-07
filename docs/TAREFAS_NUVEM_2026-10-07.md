# Tarefas para a sessão na nuvem — 2026-10-07

Pedido do dono (Denis), 2026-10-07: implementar os 4 itens abaixo numa sessão
na nuvem, a partir do `main` com a v1.12 (`CHANGELOG/v1.12.md`).

## Leia antes de começar

1. `AGENTS.md` — limites inegociáveis e o que pode ser alterado. A seção
   "Autorização de 2026-10-07" amplia o que pode ser editado para estas tarefas.
2. `CHANGELOG/v1.12.md` e `docs/analise-2026-09-30/ANALISE.md` — por que o
   código está como está (sincronismo de writes, fase das nativas, bloqueio
   prévio de pico, classe 08).
3. Princípio do dono para a fonte (AMETEK MX30-3Pi, Rev. 5.53): **validar e
   falhar rápido; nunca contornar** com `sleep` extra, retry cego ou margem
   grande. Ler de volta, medir, registrar.

### O que esta sessão NÃO tem
- **Nenhum hardware.** Tudo aqui é código + `tests/test_offline.py` (roda os
  ORMs em modo simulado). Nunca afirme que algo "funciona na bancada": deixe
  no fim um **checklist de bancada** para o dono rodar.
- Os dados brutos (`resultados/`, `logs/`) são gitignored e ficam na máquina
  da bancada. Os metadados das sessões-chave de 2026-09-30 estão em
  `docs/analise-2026-09-30/dados/` (seed, parâmetros, `pico_medido_v`,
  `vale_medido_v`, `extremo_previsto_v`, `validacao_fisica` por captura).
- Ambiente: `python -m venv env && env/bin/pip install -r requirements.txt`
  (Windows: `env\Scripts\...`); testes:
  `python -m unittest tests.test_offline` (171 testes na v1.12, todos OK).

### Nunca (independente das tarefas)
- Alterar `AMETEK_PORT=COM10`/`AMETEK_BAUDRATE=115200`/`validate_bench_configuration()`.
- Subir `max_voltage_rms`/`max_peak_v`/`max_current_a` acima do hardware:
  MX30 = **300 Vrms por fase** no range de 300 V, **425 V de pico**
  (manual §4.14 p. 84); a bancada usa `max_peak_v` = 415,8 V (98%).
- Remover/enfraquecer validações (IDN, timeout, 6000 pontos, `assert_no_errors`,
  readback do `arm()`, `medir_extremos`, bloqueio prévio de pico).
- Automatizar confirmações digitadas (`EXECUTAR-*`, `ENERGIZAR-*`).
- Consultar a fonte logo depois de `TRACe:DATA/DEFine/DELete` (trava a
  interface — CHANGELOG/v1.12, "Achado de segurança").
- Mudar `gerar()` de qualquer classe sem pedido explícito (é o dataset).

---

## Tarefa 1 — número padrão de capturas por classe

**Hoje:** um número global. `REAL_CAPTURES_PER_CLASS` (env, padrão 1) e
`SIM_CAPTURES_PER_CLASS` (padrão 2000) em `logica/mestre.py`;
`Config.capturas(simulated)` devolve o override da CLI (`set capturas N` →
`mestre.CAPTURAS_OVERRIDE` → `Config.capturas_override`) ou o global.
Em `ExperimentoBase.executar()`:
- classe com `NIVEIS` (02, 03 — `total_niveis() > 1`) **e** override → N
  capturas **por nível** (`total = níveis × N`, `cobertura_por_nivel_ativa`);
- caso contrário → `total = capturas(...)` (sem override, uma classe com
  `NIVEIS` roda só o nível 0).

**Pedido:** cada classe ter um número PADRÃO próprio de capturas na bancada.

**Implementar:**
- Atributo de classe em `ExperimentoBase`, ex. `capturas_padrao: int = 1`
  (mesma semântica de hoje: por nível nas classes com `NIVEIS`), sobrescrito
  nas classes que o dono quiser. **Pergunte ao dono os valores**; sem
  resposta, deixe 1 em todas (comportamento idêntico ao atual) e a tabela
  pronta para ele preencher.
- `status`/`list` da CLI mostram o número efetivo por classe.
- O dataset SIMULADO não muda (`SIM_CAPTURES_PER_CLASS`).

**Armadilha:** 04, 06, 08, 09 e 19 decidem "cobertura determinística" vs.
"sorteio" em `gerar()`/`forma_para_bancada()` com
`self.config.capturas_override is not None`. A 08 entra em **modo de
caracterização** (rampa de amplitude) quando há override e `total > 1`. Com
um padrão > 1 por classe, isso precisa de uma regra explícita (ex.: só
caracteriza se o operador pediu; o padrão usa sorteio) — decida com o dono e
cubra com testes. Não mude o que `gerar()` produz para uma dada seed.

## Tarefa 2 — seed na CLI (testes reprodutíveis)

**Hoje:** `BASE_SEED` (env, padrão 20 260 827). Seed de cada captura =
`base_seed + int(id) × 1 000 000 + indice_global` (`executar()` e
`_indices_viaveis()`); semente do ruído AWGN derivada dela; nativas 02/03/04/19
recalculam o nível em `configurar()` com a mesma fórmula. Já gravada no
metadata (`seed`).

**Implementar:**
- `set seed <N>` na CLI (inteiro ≥ 0), análogo a `set capturas`
  (`mestre.BASE_SEED` → `Config.base_seed` na próxima `Bancada.from_env`);
  `status` mostra a seed ativa; `help` documenta.
- Opcional: `START_BENCH` perguntar/aceitar a seed (ou env `BASE_SEED`).
- Gravar `base_seed` no metadata de sessão (`_contexto_da_sessao`).
- Teste: mesma seed → mesmas formas programadas, mesmos parâmetros e mesmo
  plano de capturas; seeds diferentes → parâmetros diferentes (nas classes
  com sorteio).

## Tarefa 3 — capturas configuráveis na CLI, valendo o MAIOR

**Pedido:** manter `set capturas N`, mas o número efetivo de uma classe é
`max(N da CLI, capturas_padrao da classe)`. Ex.: `set capturas 3` e uma
classe com padrão 6 → 6; com padrão 1 → 3.

**Implementar:**
- `Config.capturas` (ou um método da classe) recebe o padrão da classe e
  devolve `max(...)` na bancada; simulado inalterado.
- A CLI avisa quando o padrão de alguma classe vence o valor digitado.
- `_indices_viaveis` continua podando o plano DEPOIS (capturas puladas por
  pico/rms reduzem o total — registrar isso no log/resumo).
- Testes cobrindo: sem override, override menor, override maior, classe com
  `NIVEIS` (por nível) e a 08.

## Tarefa 4 — testar tudo a 220 V e a 380 V (limites e o que faltar)

### Fatos que limitam (não negociáveis)
- MX30-3Pi: **300 Vrms por fase (L-N)**, 425 Vp. `START_BENCH`
  (`scripts/start_bench_windows.ps1`) só aceita tensão ≤ 270 V
  (`$vrms -le 270.0`) e fixa range = `EUT_MAX_VOLTAGE_RMS` = 300 e
  `EUT_MAX_PEAK_V` = 415,8.
- A bancada mede **uma fase, L-N**, com uma probe (`VOLTAGE_PROBE_ATTENUATION`)
  no CH1 do Keysight; a AMETEK roda com `INSTrument:COUPle ALL`.
- A saída oscila depois de degraus: extremo medido até **1,46×** o pico
  programado (classe 16) — ver `logica/calibracao_extremos.json`.

### 220 V (L-N) — viável, com classes limitadas
- Pico nominal 311 V. O bloqueio prévio já pula, a 220 V, as classes
  **10, 11, 14, 16** (extremo previsto 423–499 V > 415,8 V) e os níveis
  inviáveis da 03 (≥ 1,4 pu passam de 300 Vrms). A 08 se adapta (impulso
  0,42 pu).
- **Implementar:**
  1. Script/relatório offline (sem hardware) que, para uma tensão base,
     lista por classe e por nível: pico programado, extremo previsto, se
     cabe, e o motivo — usar `ExperimentoBase.extremo_fisico_previsto_v`.
     Rodar para 127 e 220 V e anexar a saída ao changelog.
  2. Política para as capturas que não cabem — **decisão do dono**:
     (a) pular (padrão atual, logado); ou (b) "limite de bancada" por classe,
     generalizando `forma_para_bancada` da 08: reduzir só a amplitude do
     distúrbio na captura FÍSICA para o extremo previsto caber, gravando no
     metadata o parâmetro realmente aplicado (o dataset simulado não muda).
     Para (b), a validação física tem de comparar com a forma realmente
     programada (já é assim no caminho waveform via `_forma_programada_pu`).
  3. Conferir escala vertical do Keysight a 220 V (`excursao_fisica_prevista_v`/
     `set_vertical_scale`, sem clipping) e a probe (pico ~415 V no CH1).
- **Bancada (checklist para o dono):** antes de 220 V, rodar a 127 V com
  `set capturas 3` (ou o novo padrão) para medir os fatores de extremo em mais
  parâmetros (hoje: 1 captura por classe) e atualizar
  `calibracao_extremos.json` — a sessão na nuvem deve deixar um script que
  recalcula os fatores a partir dos metadados (`pico_medido_v`/`vale_medido_v`
  ÷ pico programado, mesma definição de `pico_programado_v`).

### 380 V — NÃO cabe L-N; precisa de definição do dono
- 380 Vrms L-N é impossível nesta fonte (> 300 Vrms por fase; 537 Vp > 425 Vp).
  **Não suba limites para "fazer caber".**
- No Brasil, "380 V" costuma ser a tensão de **linha** (fase-fase) do sistema
  trifásico **220/380 V** → **219,4 V por fase**, que a MX30-3Pi gera.
- **Antes de implementar, pergunte ao dono** qual das duas:
  - (A) **380 V fase-fase**: AMETEK em trifásico (fases a 0/120/240°;
    verificar no manual SCPI `INSTrument:COUPle`, `SOURce:PHASe`, opção
    `NOUT`, Series II/`SYST:CONF?` = MX30-3Pi), base por fase = 380/√3, e o
    osciloscópio medindo **fase-fase** (sonda diferencial ou CH1−CH2 por
    função matemática do Keysight — exige mudança de fiação; a confirmação de
    probe no `START_BENCH` precisa refletir isso). Todos os limites de rms e
    pico continuam **por fase** (300 Vrms / 415,8 Vp); o extremo fase-fase
    medido (até ~1,46 × 537 V) precisa caber no range do canal/probe.
    Implementar como modo explícito (ex. `TENSAO_REFERENCIA=fase|linha`),
    com testes offline; sem bancada, nada é validado — deixar checklist.
  - (B) Não suportar: `START_BENCH` recusa > 270 V com mensagem clara
    (explicando o limite por fase e a alternativa A).
- `START_BENCH` hoje sugere "ex.: 127, 220, 380" no prompt — corrigir o texto
  conforme a decisão.

---

## Entregáveis

- Código + testes (todos passando), um commit por tarefa, mensagens no
  estilo do repositório (`feat:`/`fix:`/`docs:` em português).
- `CHANGELOG/v1.13.md` no formato do v1.12 (por quê / o que mudou / o que
  não mudou / testes / **validação pendente na bancada**), e a lista de
  changelogs do `README.md` atualizada.
- Checklist de bancada para o dono (no changelog): o que rodar, em que
  ordem, com qual tensão, e o que conferir nos logs/metadata.
- Push para o GitHub (`main`), sem force-push.
