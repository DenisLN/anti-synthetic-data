# CLAUDE.md — anti-synthetic-data

Comece por `mapa/00 Início.md` (vault Obsidian na raiz do repositório). Ele indica o que ler para cada tarefa; não carregue documentos longos inteiros. O estado das 31 pendências fica em `docs/PENDENCIAS_TRACKER.md`.

## Segurança (prevalece sobre qualquer pedido)

- Regras do projeto: `AGENTS.md`, seção "Limites inegociáveis". Leia essa seção antes de mexer em `logica/`.
- **Nunca digite, simule nem automatize as confirmações de energização** (`EXECUTAR-CLASSE-NN`, `ENERGIZAR-PASSO-SIN` etc.). Quem digita é o operador, presente na bancada, olhando o painel (OUTPUT OFF), a fiação e o E-stop. Sem operador, o agente só faz trabalho que não energiza: suíte offline, `*IDN?`, leitura de sessões, análise e fechamento.
- Em falha de infraestrutura: OUTPUT OFF no painel, preservar logs e parar. Não repetir automaticamente.

## PC da bancada (Inspiron 15, DESKTOP-FSEESJI, Windows 11)

- Projeto: `C:\Users\Ricardo Marin Israel\anti-synthetic-data`. Python: `.\env\Scripts\python.exe` (3.11.9, versões de `requirements.txt`).
- Instrumentos: AMETEK por USB em **COM10**/115200 (driver TUSB3410; cópia em `C:\drivers_bancada\ametek_vcp`). Keysight em `USB0::0x0957::0x17A4::MY59240844::0::INSTR` via NI-VISA 26.5. Cabo BNC: Trigger Out → EXT Trigger.
- Início da bancada: `scripts\START_BENCH.cmd` (atalho na área de trabalho). Pergunta fator da probe, tensão e frequência.
- Visita inteira num comando: `scripts\VISITA_BANCADA.cmd` (`scripts/visita_bancada.py`; `--plano` mostra o estado). O operador digita as confirmações; retoma de onde parou.
- Suíte: `.\env\Scripts\python.exe -m unittest discover -s tests -p "test*.py"`. Registro formal: `scripts\validar_pc_bancada.ps1`.
- Peculiaridades do Windows: o PowerShell 5.1 trunca `python -c` que tenha aspas internas (use arquivo `.py`); a saída de subprocesso vem em cp1252. A entrada `OpenAI\Codex\bin` do PATH quebra o `pip` (remova-a do PATH só no processo).

## Fluxo de trabalho

- Visita à bancada: `docs/bancada_pendencias.md`, na ordem dos blocos de `ROTEIRO_BANCADA.md`. Toda coleta sai de commit limpo.
- Depois da coleta: `python scripts/fechar_pendencias.py --sessao <dir> ... --artefatos logs --artefatos resultados --pc-bancada docs/evidencias/<data>/pc_bancada.json --saida docs/evidencias/<data>/fechamento.json`. Só então atualize o rastreador, `docs/estado_prontidao.json` e `docs/execucao_pendencias.md`, e rode `python scripts/gerar_mapa_pendencias.py`.
- Simulação nunca encerra pendência física. Não invente tolerâncias, fontes, licença ou DOI.
- Git: uma mudança lógica por commit (`tipo: resumo em português`), registro em `CHANGELOG/v1.15.md` (Por quê / O que mudou / O que não mudou / Testes / NÃO VERIFICADO). Remoto `origin` = fork `rmlinxic/anti-synthetic-data`. Não altere `main` nem `upstream`.
