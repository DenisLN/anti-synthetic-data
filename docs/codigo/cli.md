# cli.py: o REPL do operador

:::{note} Revisão e procedência
Texto de referência importado do levantamento de 16/10/2026, baseado em [fa82f496](https://github.com/DenisLN/anti-synthetic-data/tree/fa82f49600543456adf78e22485ab6de5dd032b9). Citações numéricas apontam para esse snapshot e não acompanham linhas atuais. Trechos `literalinclude` são extraídos do checkout atual por símbolo; consulte {doc}`../execucao_pendencias` para implementação e evidências vigentes. Relatos de sessões e transcrições são históricos, não medições repetidas nesta revisão.
:::


{bdg-info}`OFFLINE` Lido por inteiro em 2026-10-16 (`main` em `fa82f49`). O uso, do ponto de vista do operador, está em {doc}`../operacao` e {doc}`../guia-operador`.

**Pergunta:** o que acontece entre digitar `run all` e a fonte ser energizada? **Resposta:** a CLI (`SessaoCLI.loop`, prompt `bancada>`) estima o que será feito (capturas e gravações de TRACe), pede a **confirmação digitada** (case-sensitive), cria uma pasta de sessão **nova**, autoriza a saída só pelo tempo do comando, abre a `Bancada`, executa e, no `finally`, retira a autorização; depois roda os ganchos opcionais (recalibração, HTML). Os comandos `set` só mudam variáveis de `mestre` para o **próximo** `run`.

| Símbolo | Assinatura | Linha | Papel |
|---|---|---|---|
| `HELP_TEXT` | (constante ou variável de módulo) | [cli.py:59](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L59) | a referência dos comandos; `docs/operacao.md` a replica à mão |
| `parsear_lista_classes` | `(texto: str) -> List[int]` | [cli.py:209-232](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L209-L232) | `"01-07,09-20"` → ids ordenados; recusa invertido, incompleto, vazio, fora de 01 a 20 |
| `normalizar_lista_classes` | `(ids: List[int]) -> str` | [cli.py:235-246](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L235-L246) | forma canônica usada na confirmação (`01-07,09-20`) |
| `comando_terminal_diagnostico` | `(caminho_log: Path) -> List[str]` | [cli.py:43-57](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L43-L57) | janela de `tail -f` da transcrição (com `set diagnostico on`) |
| `SessaoCLI` | `class ` | [cli.py:249-995](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L249-L995) | o estado e os comandos da sessão |
| `SessaoCLI.autorizar_saida` | `(self, autorizado: bool) -> None` | [cli.py:271-281](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L271-L281) | espelha `ARM_OUTPUT` no ambiente, em `mestre` e em `preflight_new` |
| `SessaoCLI._garantir_pasta_sessao` | `(self) -> None` | [cli.py:283-311](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L283-L311) | pasta nova por `run` (`sessao_<ts>`, `_run02`, ...), log e `sessao.json` |
| `SessaoCLI.confirmar` | `(aviso: str, esperado: str) -> bool` | [cli.py:345-351](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L345-L351) | `input()`; só `==` exato passa |
| `SessaoCLI.cmd_status` | `(self, _args: List[str]) -> int` | [cli.py:368-405](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L368-L405) | modo, perfil, sorteio, capturas, ganchos |
| `SessaoCLI.cmd_set` | `(self, args: List[str]) -> int` | [cli.py:527-672](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L527-L672) | `diagnostico`, `capturas`, `seed`, `perfil`, `sorteio`, `recalibracao`, `html` |
| `SessaoCLI.cmd_comm` | `(self, _args: List[str]) -> int` | [cli.py:676-679](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L676-L679) | preflight de comunicação, sem energizar |
| `SessaoCLI.cmd_trigger` | `(self, _args: List[str]) -> int` | [cli.py:681-684](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L681-L684) | teste do BNC, sem energizar |
| `SessaoCLI.cmd_lowvoltage` | `(self, _args: List[str]) -> int` | [cli.py:686-700](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L686-L700) | recomissionamento na tensão base (`ENERGIZAR-TESTE`) |
| `SessaoCLI.cmd_native` | `(self, _args: List[str]) -> int` | [cli.py:702-713](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L702-L713) | comandos nativos (`ENERGIZAR-COMANDOS`) |
| `SessaoCLI.cmd_run` | `(self, args: List[str]) -> int` | [cli.py:717-726](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L717-L726) | despacha `run all`, lista ou uma classe |
| `SessaoCLI._run_lista` | `(self, texto: str) -> int` | [cli.py:728-753](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L728-L753) | valida tudo antes de pedir confirmação |
| `SessaoCLI._run_uma` | `(self, alvo: str) -> int` | [cli.py:755-807](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L755-L807) | uma classe, com `assegurar_tensao_base` |
| `SessaoCLI._run_all` | `(self) -> int` | [cli.py:809-826](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L809-L826) | as 20 classes (`EXECUTAR-20-CLASSES`) |
| `SessaoCLI._executar_scripts` | `(self, scripts: List[Path]) -> int` | [cli.py:828-860](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L828-L860) | corpo comum de `run all` e `run <lista>` |
| `SessaoCLI._fim_da_sessao` | `(self, sessao_dir: Optional[Path]) -> None` | [cli.py:864-885](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L864-L885) | ganchos de fim de run |
| `SessaoCLI._recalibrar_ao_fim` | `(self, sessao_dir: Path) -> None` | [cli.py:895-927](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L895-L927) | recalibração automática (nunca diminui) |
| `SessaoCLI._gerar_html_ao_fim` | `(self, sessao_dir: Path) -> None` | [cli.py:929-935](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L929-L935) | relatório HTML recortado |
| `SessaoCLI.loop` | `(self) -> int` | [cli.py:962-995](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L962-L995) | o laço `bancada>` |

## 1. Fluxo de um `run`

```{mermaid}
sequenceDiagram
    participant Op as Operador
    participant C as SessaoCLI
    participant M as mestre
    Op->>C: run all
    C->>C: _capturas_das_classes (estimativa; aviso de ~280 gravações de TRACe)
    C->>Op: texto de aviso + "Digite EXECUTAR-20-CLASSES:"
    Op->>C: EXECUTAR-20-CLASSES (exato)
    C->>C: _garantir_pasta_sessao (pasta nova, log, sessao.json)
    C->>M: autorizar_saida(True)
    C->>M: Bancada.from_env(require_output=True)
    M-->>C: executar_bateria(...)
    C->>M: autorizar_saida(False) no finally
    C->>C: _fim_da_sessao (recalibração, HTML)
```

As confirmações, todas **case-sensitive** e digitadas pelo operador: `ENERGIZAR-TESTE` (`lowvoltage`), `ENERGIZAR-COMANDOS` (`native`), `EXECUTAR-CLASSE-NN` (`run NN`), `EXECUTAR-CLASSES-<lista normalizada>` (`run <lista>`) e `EXECUTAR-20-CLASSES` (`run all`). `comm` e `trigger` não energizam e não pedem confirmação.

## 2. Invariantes

1. Nada energiza sem a string digitada: `confirmar` compara com `==` ([cli.py:345](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L345)).
2. `autorizar_saida(True)` só dentro do comando e `autorizar_saida(False)` num `finally`, de modo que uma exceção nunca deixa a autorização ligada.
3. `_run_lista` e `parsear_lista_classes` validam a lista **antes** de qualquer confirmação ou contato com a bancada.
4. **Nenhuma falha dos ganchos derruba a CLI** nem conta como falha de experimento: avisa e segue.
5. Ctrl+C no meio de um comando volta ao prompt: o `with Bancada` já desligou a saída ao sair; a CLI imprime "confira OUTPUT OFF no painel".

## 3. Armadilhas

1. **Atualização P-14:** `run 01 02` e argumentos extras de `all` são recusados antes de qualquer execução; espaços junto a vírgulas e intervalos continuam aceitos.
2. **Atualização P-14:** listas aplicam `BATERIA_EXCLUIR` na bancada, mostram as exclusões e não executam lista totalmente excluída; `run <NN>` isolado continua explícito.
3. `_run_uma` chama `assegurar_tensao_base` porque `run 02` isolado mediu cerca de 0 V antes e depois do pulso (v1.7): `trigger_pulse` nunca eleva a tensão imediata.
4. `run <NN>` usa `executar_classe_nos_perfis`: **sem as três tentativas** de `executar_bateria`; a primeira exceção propaga.
5. A recalibração importa `scripts/recalibrar_extremos.py` por `sys.path.append`: acoplamento entre `logica/` e `scripts/` ([cli.py:888](https://github.com/DenisLN/anti-synthetic-data/blob/fa82f49600543456adf78e22485ab6de5dd032b9/logica/cli.py#L888)).
6. `set perfil todos` e `set sorteio` mexem na estimativa de gravações (`_capturas_das_classes`): com `todos`, `total` e `escritas_trace` são a soma dos perfis que de fato rodam.
7. O estado de sessão (`_runs_nesta_sessao`, `_perfis_usados`) vive na instância: reiniciar a CLI reinicia `_run02`.

## 4. Por que é assim

- **Pasta nova por `run` (relatório de 21/09).** Antes, todos os `run` de uma sessão compartilhavam a pasta e o segundo sobrescrevia o primeiro em silêncio (um `run 01` com margem foi apagado por um `run all`).
- **`autorizar_saida` espelha o ambiente em dois módulos** porque `mestre` e `preflight_new` fazem `from mestre import ... OUTPUT_ARMED`: cada um tem a **cópia** do valor da hora do import.
- **`run <lista>` (v1.15).** Permite dividir a bateria abaixo da trava de cerca de 280 gravações de TRACe por conexão (A3); cada `run` abre conexão nova.
- **`lowvoltage` pede `ENERGIZAR-TESTE`** e mostra a tensão real: antes pedia `ENERGIZAR-5V` mas rodava na tensão digitada no início (127 V).

## 5. Depende de e quem depende

Importa `mestre`, `perfis` e `preflight_new`; importa `relatorio_html` e `scripts/recalibrar_extremos.py` dentro dos ganchos. É chamado por `scripts/start_bench_windows.ps1` (última linha). Ver {doc}`preflight_new`, {doc}`relatorio_html` e {doc}`scripts`.
