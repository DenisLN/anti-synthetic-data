# Patches propostos — ordem de aplicação, dependências e resultados

Oito patches, desenvolvidos em **TDD** (teste novo escrito **antes** da
implementação) numa **cópia de scratch** do worktree. **Nada foi aplicado no
projeto** e **nenhum arquivo de `resultados/` foi tocado**. Nenhum instrumento
foi acessado: tudo roda no modo simulado / nas fakes já existentes em
`tests/test_offline.py` (`ScriptedAdapter`, `ScriptedSerialVisaResource`,
`_FakeTraceDevice`, `AmetekMX30(simulated=True)`).

Justificativa e desenho de cada um: `../03_propostas_melhorias.md`.

## Como aplicar

```powershell
cd "C:\Users\denis\Documents\1 Projetos\anti-synthetic-data\.claude\worktrees\sessao-bancada-v18"
# confira antes de aplicar (nunca falha silenciosamente):
git apply --check docs\analise-2026-09-21\propostas\p01_caminho_nativo_modo_fixed_e_idle.patch
git apply         docs\analise-2026-09-21\propostas\p01_caminho_nativo_modo_fixed_e_idle.patch
# ... e assim por diante, NA ORDEM DA TABELA
env\Scripts\python.exe -m unittest tests.test_offline
```

**A ordem importa.** Os patches são cumulativos sobre os mesmos arquivos: o
`p01` aplica no worktree intocado; cada um dos seguintes aplica sobre o estado
deixado pelos anteriores. Aplicar fora de ordem produz conflito de contexto (o
`git apply --check` avisa antes de escrever qualquer coisa).

## Ordem, dependências e resultado dos testes

Baseline do worktree: **83 testes, ~1,6 s, todos verdes**. Depois dos oito:
**125 testes, ~2,6 s, todos verdes**. Nenhum teste existente foi removido;
dois grupos foram **adaptados** (justificativa abaixo, item "Testes adaptados").

| # | patch | arquivos | testes (antes → depois) | depende de |
|---|---|---|---|---|
| 1 | `p01_caminho_nativo_modo_fixed_e_idle.patch` | `logica/ametek_orm.py`, `tests/` | 83 → **91** (+8) | — |
| 2 | `p02_arm_le_de_volta_e_falha_rapido.patch` | `logica/ametek_orm.py`, `tests/` | 91 → **97** (+6) | p01 (usa `aguardar_idle` e `_transiente_esperado`) |
| 3 | `p03_salvamento_incremental_por_captura.patch` | `logica/mestre.py`, `tests/` | 97 → **100** (+3) | — (independente na prática; contexto de `mestre.py`) |
| 4 | `p04_erro_deterministico_e_pre_validacao_de_niveis.patch` | `logica/mestre.py`, `tests/` | 100 → **104** (+4) | p03 (mesmo laço de `executar()`) |
| 5 | `p05_validacao_fisica_pos_captura.patch` | `logica/sinais.py`, `logica/mestre.py`, `tests/` | 104 → **112** (+8) | p03, p04 (`ERROS_DETERMINISTICOS`, gravação incremental) |
| 6 | `p06_log_de_sessao_transcricao_scpi_e_metadata.patch` | `logica/mestre.py`, `logica/ametek_orm.py`, `logica/oscilloscope_orm.py`, `logica/cli.py`, `tests/` | 112 → **117** (+5) | p01–p05 |
| 7 | `p07_posicao_do_trigger_e_indice_trigger.patch` | `logica/oscilloscope_orm.py`, `tests/` | 117 → **121** (+4) | p06 (o `indice_trigger` só vira metadata com ele) |
| 8 | `p08_margem_20_50_e_analisar_sessao.patch` | `logica/mestre.py`, `logica/sinais.py`, `logica/analisar_sessao.py`, `tests/` | 121 → **125** (+4) | **p07 (obrigatório)**, p05, p06 |

**Dependência dura:** `p08` (margem de 20/50 ms) **não deve** ser aplicado sem
o `p07`. Enquanto o trigger cair em `pre_trigger + janela/10`, uma janela de
270 ms trunca o evento (01 §2(i)).

### Verificação já feita (offline)

- `git apply --check` + `git apply`, **na ordem**, sobre uma cópia limpa dos
  arquivos rastreados do worktree: **os 8 aplicam sem conflito**.
- `python -m unittest tests.test_offline` nessa cópia com os 8 aplicados:
  **125 testes, OK**.
- `git -C <RAIZ> apply --check p01...` no worktree intocado: **OK**.

## Testes adaptados (não enfraquecidos)

Dois grupos de testes existentes mudaram. Nenhuma asserção foi afrouxada ou
removida; em ambos os casos a mudança é consequência direta de uma decisão de
projeto documentada no relatório.

1. **`RemapeamentoNivelTests`** (p04) — a fonte fake era criada com o default de
   comissionamento (`max_voltage_rms=10`) e tensão base de 127 V, ou seja uma
   bancada fisicamente impossível (12,7 V pedidos contra um teto de 10 V) que só
   passava porque nada validava os níveis antes de capturar. Passou a usar
   `max_voltage_rms=300`, o teto real do manual ([AM] §4.14, p. 84). As
   asserções — quais `capture_index` o laço visita — continuam idênticas.
2. **`MargemCapturaTests`** (p08) — `_calcular_margem` passou a devolver
   `(antes, depois, total)` em vez de `(margem, total)`, porque a margem deixou
   de ser simétrica. As asserções continuam as mesmas em natureza (margin off =
   janela nominal; margin on = folga dos dois lados, dentro dos dois tetos do
   osciloscópio); só os números mudaram, de 400/400 ms para 20/50 ms. O grupo
   ganhou um teste novo que amarra a janela ao fim de evento medido.

Além disso, dois stubs de teste (`ErroDeterministicoEPreValidacaoTests`,
p04/p05) passaram a devolver uma captura **coerente com o nível configurado** —
antes devolviam uma senoide constante que a validação física (p05) reprovaria
com razão.

## O que cada patch NÃO cobre

| patch | não cobre |
|---|---|
| `p01` | não descobre o **mecanismo** de H-NATIVO — cobre os dois candidatos com apoio no manual (escrita durante transiente, modos residuais). Se a fonte errar mesmo com IDLE confirmado e fila limpa, quem segura a validade dos dados é o `p05`. Não toca no caminho LIST (`program_capture`/`arm_transient`), que já é validado. |
| `p02` | não consulta `FUNCtion:SHAPe?` nem `SOURce:MODE?` (não existem como QUERY na Rev. 5.53 — ver 03 §P0-2). Logo, **não detecta** uma CSINe que não pegou por readback: isso fica com o `p05` (THD). Não valida `SOURce:MODE`/offset da classe 19. |
| `p03` | não deduplica nem comprime nada; não muda o formato do `.npz`. A limpeza de órfãos continua existindo — só deixa de rodar em rodada abortada. Não recupera dados de sessões passadas. |
| `p04` | a pré-validação só conhece classes com `NIVEIS` em pu de tensão (02/03). Classes de parâmetro contínuo (04/19) e de THD (05) devolvem `None` e passam direto. Não usa `VOLT? MAX` (exige a fonte; ver 03 §P0-5). Não valida o **pico** das classes waveform — isso já é feito por `limite_pico_bancada_pu`. |
| `p05` | não mede fase nem alinhamento (de propósito: seria dependente do `p07`). Não detecta erro de **frequência** (classe 18) — a THD e o envelope são cegos a isso; para a 18 a sonda certa seria a frequência instantânea, não implementada. Não quarentena os arquivos em subpasta: marca no metadata e deixa no lugar. |
| `p06` | a transcrição SCPI só cobre a **AMETEK** (o osciloscópio passa por PyMeasure e não tem o mesmo gancho). O `versao_codigo` depende de `git` no PATH; sem ele grava `"desconhecida"`. Não implementa o relatório de trava em disco (P0-7, só desenho). |
| `p07` | não troca `POINts:MODE NORMal` por `RAW`/`MAXimum` e **não remove o `np.interp`** — isso é a P1-3, que depende do teste T3 na bancada. Não mexe no guard de clipping (a proposta ali é o teste T13, não uma mudança). |
| `p08` | `analisar_sessao.py` continua com a limitação documentada de reconstruir o ramo de sorteio (e não o de cobertura determinística) de `gerar()` para 04/06/08/09/19. Não reprocessa as sessões antigas — para elas o metadata não tem `indice_trigger` e a ferramenta **avisa** do viés de janela/10. |

## Reprodutibilidade

A cópia de scratch usada ficou em
`%LOCALAPPDATA%\Temp\claude\...\scratchpad\s3_patches` (repositório git próprio,
um commit por patch, `core.autocrlf=false`). Os diffs são unificados, relativos
à raiz do projeto, com finais de linha **LF** — iguais aos do worktree
(`.gitattributes`: `* text=auto eol=lf`).
