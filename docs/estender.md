# Como estender o projeto

Guia para criar ou alterar uma classe de distúrbio e para acrescentar comandos, campos e opções, com os erros que já custaram bancada. Leia antes `docs/arquitetura.md` (ganchos de `ExperimentoBase`) e `docs/glossario.md`. Linhas: commit `d37e403`.

**Regras de partida (`AGENTS.md`)**
1. Mudar o que `gerar()` produz para uma seed muda o **dataset**: exige autorização registrada em `AGENTS.md`, e entra numa versão declarada no `CHANGELOG`.
2. Os limites inegociáveis (`max_voltage_rms`, `max_peak_v`, `max_current_a`, `COM10/115200`, validações de IDN/timeout/6000 pontos/SCPI, confirmação digitada) não se alteram.
3. Comportamento que parece errado: **diagnosticar primeiro** (`docs/diagnostico.md`: `set diagnostico on`, ou um script que chame as funções do projeto isoladamente e reproduza o caso), só então corrigir, com teste de regressão.

## 1. Criar uma classe nova

### 1.1 Atenção: o número de classes é 20 no código
`_experiment_scripts()` exige exatamente os ids 01 a 20, cada um em **uma** das duas pastas (`mestre.py:2985-2997`, `range(1, 21)`). Uma 21.ª classe exige mudar `mestre.py` (autorização de `AGENTS.md`: `mestre.py` está liberado para refatoração), os textos "20 classes" da CLI (`cli.py:66,85,311,607`) e os testes que iteram `range(1, 21)` ou esperam 400 assinaturas (`tests/test_offline.py:256,3913,4344,4358,4471,5114,5274,5394,5612`). Alterar uma das 20 existentes não exige isso.

### 1.2 Escolher o mecanismo
| | `ExperimentoNativo` (`experimentos_nativos/NN.py`) | `ExperimentoWaveform` (`experimentos_waveform/NN.py`) |
|---|---|---|
| Quando | a fonte tem um recurso nativo para o distúrbio (STEP, PULSe, CSINusoid, `LIST:FREQuency`, ACDC) | qualquer forma arbitrária |
| Você implementa | `gerar()` e `configurar(capture_index)` | só `gerar()` |
| Bancada | `configurar()` programa o recurso; a fonte gera | `program_capture` grava TRACes e toca uma LIST com a forma de `gerar()` |
| Limite de bancada (redução de `k`) | não reduz | reduz; implemente `parametros_com_disturbio_reduzido` |
| Custo | pouca Flash | 1 gravação de TRACe por ciclo da janela por captura (12 a 60 Hz); a fonte travou em ~280 por conexão |

Prefira waveform quando não houver recurso nativo comprovado: o nativo exige validar cada comando na bancada. Se for nativa, também registre a classe em `sinais.FORMA_NATIVA_POR_CLASSE` e em `sinais.forma_programada_nativa` (`sinais.py:509,549`), senão a "forma programada" da captura não é gravada.

### 1.3 Esqueleto (waveform)

```python
"""Classe NN: NOME — descrição em uma linha."""
import numpy as np

import perfis                      # se tiver faixas por perfil
from mestre import ExperimentoWaveform
from sinais import janela


class Experimento(ExperimentoWaveform):      # nome fixo: o carregador procura "Experimento"
    id = "NN"                                # string de 2 dígitos = nome do arquivo
    nome = "NOME_EM_MAIUSCULAS"              # vira parte do nome dos arquivos (minúsculo) e do "run <nome>"
    capturas_padrao = 3                      # 3 se gerar() sorteia parâmetros; 1 se é determinística

    def gerar(self, t, f0, capture_index, rng):
        profundidade = float(rng.uniform(*perfis.faixa(self.config, "meu_componente")))
        sorteio = self.sortear(rng, f0, inicio_legado_s=0.060, duracao_legada_s=0.060,
                               duracao_variavel=True)          # sem evento localizado: self.sortear(rng, f0)
        voltage = np.sin(2.0 * np.pi * f0 * (t + sorteio.deslocamento_s))   # fase sorteada
        voltage[janela(t, sorteio.inicio_s, sorteio.duracao_s)] *= 1.0 - profundidade
        return voltage, {"minha_profundidade": profundidade, **sorteio.parametros()}

    def parametros_com_disturbio_reduzido(self, parametros, fracao):
        return {"minha_profundidade_bancada": fracao * parametros["minha_profundidade"]}
```
Com `set sorteio off`, `sorteio.inicio_s`/`duracao_s` valem os `*_legado_s` e a fase é 0, então o mesmo código serve aos dois modos.

### 1.4 Contrato de `gerar()`
- Devolve `(voltage, parametros)`; `voltage` com shape `(6000,)`, finito, em pu. `executar()` levanta `RuntimeError` se não for (`mestre.py:2463`).
- **Determinístico** dada a seed: use só o `rng` recebido; nunca `np.random` global. A **ordem** dos sorteios do `rng` não pode mudar depois de publicada (muda o dataset). O sorteio de posição usa um sub-fluxo separado (`_rng_do_sorteio`, `mestre.py:797`).
- Não toque `self.fonte`. `self.osc is None` identifica o simulado (usado por `valor_para_captura`).
- `parametros`: dicionário de números (JSON). A **primeira chave** vira o rótulo do arquivo físico (`chave-valor`): escolha uma chave estável e informativa (`_rotulo_da_captura`, `mestre.py:2292`). As chaves do sorteio (`CHAVES_SORTEIO`) são movidas para o nível de cima do metadata.
- Para cobertura de intervalo com `set capturas`, use `sinais.valor_para_captura` (04, 06, 08, 09, 19).
- Níveis discretos: defina `NIVEIS` (propriedade, se vier de perfil) e a classe agrupa por nível. `NIVEIS` em pu da tensão base também alimenta `tensao_rms_programada` (pré-validação de rms).

### 1.5 `configurar()` (nativas)
Só métodos semânticos de `self.fonte` (`trigger_step`, `trigger_pulse`, `configure_harmonics_csine`, `frequency_drift_list`, `enable_dc_offset`). Devolva os mesmos parâmetros que `gerar()` produz para aquela captura (sem as chaves do sorteio). Se precisar do mesmo `rng` de `gerar()`, reproduza a seed e a **mesma ordem** (04 e 19 fazem `base_seed + id×1 000 000 + capture_index`; só vale porque `capture_index == indice_global`). Para PULSe use `self.largura_do_pulso_s(DURACAO_S)` e defina `pre_trigger_s`. Se o tamanho do pulso ou a fase mudarem por captura, o osciloscópio e a fonte já são reprogramados por `_capturar_real` (`mestre.py:2754-2769`).

### 1.6 Perfis
Se a faixa muda com a norma, ponha o componente em `perfis.FAIXAS` (uma entrada por perfil) e em `COMPONENTES_POR_CLASSE`; compostas sorteadas entram também em `FAIXAS_SORTEADAS`. O perfil `literatura` de classes **existentes** deve continuar reproduzindo o `gerar()` do commit `34a0d82` com `sorteio_posicao=False` (teste byte a byte). Documente em `docs/perfis.md`.

### 1.7 Capturas padrão
`capturas_padrao` é inteiro ≥ 1 (`mestre.py:1479`). 3 nas classes que sorteiam parâmetros, 1 nas determinísticas. Some as gravações de TRACe: a CLI avisa acima de 280.

### 1.8 Testes obrigatórios (`tests/test_offline.py`)
1. `_load_experimento("NN")` + `gerar` com várias seeds: shape, finitude, parâmetros esperados (padrão: `Classes05_07_18Tests`, `ParametrosSorteadosNasCompostasTests`).
2. Determinismo: mesma seed ⇒ mesma forma e parâmetros.
3. Sorteio: com `set sorteio off` reproduz as posições fixas; com `on`, `inicio_disturbio_s`, `duracao_s`, `fase_graus` nos limites (`SorteioInicioDuracaoFaseTests`).
4. Fixtures: acrescentar as entradas da classe (seeds 1234567 e 7654321, f0 50 e 60, índices 0–4) em `tests/fixtures/gerar_sorteio_v1_15.json`. A assinatura é o SHA-256 de `np.asarray(tensao, "<f8").tobytes() + json.dumps(parametros, sort_keys=True).encode()` (`PerfisDeFaixasTests._assinatura`, `:5100`); não há script de regravação versionado — chame essa função. **Nunca** regrave `gerar_literatura_34a0d82.json` para classes existentes.
5. Bancada simulada: uma `executar()` completa com `AmetekMX30(simulated=True)` e osciloscópio de mentira (`CaminhoNativoIntegridadeTests`, `ErroDeterministicoEPreValidacaoTests`, `ParametrosSorteadosNasCompostasTests`).
6. Limite de bancada (waveform): `parametros_com_disturbio_reduzido` devolve chaves `*_bancada` coerentes (`LimiteDeBancada220VTests`).
7. A suíte inteira: `.\env\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v` (registrar resultado, total e skips da execução atual).

### 1.9 Relatório de limites e calibração
Rode `scripts\relatorio_limites_bancada.py --tensao 127 --frequencia 60` (e 50) para ver se a classe cabe. Os fatores de extremo da classe nova não existem: usa o maior fator conhecido até a primeira bateria física (`recalibrar_extremos.py --gravar` depois). Um impulso rápido ou borda abrupta precisa de modelo próprio como a 08 (`excursao_fisica_prevista_v`, `exige_medida_de_pico`).

### 1.10 Documentar
`docs/classes.md` (tabela), `docs/perfis.md` se houver faixas, `CHANGELOG/vX.Y.md` (`docs/versionamento.md`), `README` só se mudar o início rápido.

## 2. Erros já cometidos — não repetir

| Erro | Consequência | Regra |
|---|---|---|
| Enviar vários comandos SCPI em rajada, sem esperar a fonte | comandos perdidos em silêncio (H-NATIVO) | usar `AmetekMX30.write()` (sincroniza); nunca contornar com sleep |
| Consultar a fonte logo após `TRACe:DATA` | fonte trava | não consultar; só os esperas já existentes |
| Trocar forma/modo sem `*WAI`, e consultar `FUNCtion:SHAPe?`/`SOURce:MODE?` | fonte muda / `-113` atribuído ao comando seguinte | `*WAI` + `assert_no_errors` logo depois do comando que muda o estado |
| Deixar estado permanente (forma CSINe, ACDC, frequência da lista) | a classe seguinte sai com o rótulo certo e a forma errada | usar `restaurar_forma_e_modo_padrao`; novo estado permanente exige rastreio e restauração |
| Esquecer `FUNCtion:MODE FIXed` antes de um transiente nativo | `LIST` residual altera o `*TRG` (`-226`) | `_neutralizar_transientes_residuais` |
| Escrever `VOLTage:TRIGgered` com muitas casas | truncado a 0,1 V; readback diverge | `_na_resolucao_da_fonte` |
| Escalar a forma inteira para caber no teto (08) | base de 127 V virava 43 Vrms | limitar só o distúrbio (`forma_para_bancada`) |
| Usar o array a 30 kSa/s para o pico | subestima picos estreitos | `medir_extremos` |
| Comparar o registro de 8100 amostras com a forma de 6000 | falso negativo da validação | janela alinhada ao trigger (`inicio_janela`) |
| Não gravar a captura antes de abortar por teto | perde a evidência | gravar e então conferir |
| Mudar `gerar()` sem fixture/versão | dataset muda sem aviso | fixtures byte a byte + CHANGELOG |
| Mudar `pico_programado_v` | calibração deixa de valer | recalibrar |
| Alterar o `rng` consumido por uma classe existente | todas as formas da seed mudam | acrescentar sorteios só em sub-fluxo |
| Subir tensão sem calibrar a condição | 444 V medidos a 230 V/50 Hz | tabela por condição (`docs/limites_e_calibracao.md`) |
| Arquivo novo não rastreado numa sessão | `git_sujo=false` com código fora do commit | `git add` + commit antes (`docs/versionamento.md`) |

## 3. Outras extensões

- **Novo comando SCPI**: método semântico em `AmetekMX30`/`KeysightDSOX4034A`, com validação de limite (`ParameterOutOfBoundsError`), `assert_no_errors` logo depois, readback quando houver consulta que a Rev. 5.53 implemente, suporte em `_simulate_write/_simulate_query` (`ametek_orm.py:509-594`) e teste com `ScriptedVisaConnection` (`tests/test_offline.py:134`). Registrar o comando em `docs/scpi.md` e qualquer comportamento novo em `docs/quirks.md` com a fonte da medida.
- **Nova variável de ambiente**: helper `env_*` em `mestre.py`, linha em `scripts/bench_config.ps1` se for da bancada, linha em `docs/configuracao.md` e em `.env.example` se aplicável.
- **Novo comando de CLI**: `COMANDOS` (`cli.py:733`), `HELP_TEXT`, `status` se for estado, confirmação digitada se energizar, teste (`CliCapturasTests` etc.), `docs/operacao.md`.
- **Novo campo de metadata**: só **acrescentar**; leitores usam `glob("*.jsonl")` e campos ausentes = comportamento antigo; documentar em `docs/metadata.md`.
- **Nova ferramenta offline**: nunca altera a sessão de origem (saída em pasta nova, recusa pasta existente sem `--refazer`).
