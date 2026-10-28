#spec #pri 2

# ASD: Teste na Bancada do Passo Final com a Forma SIN Interna

## Contexto

Ao fim de uma lista, a MX30 continua no último passo: o último ciclo da TRACE, com a amplitude do último `LIST:VOLTage`. Por isso a margem final das classes TRACE mostra o último ciclo mantido (no flicker, 1,12–1,13 pu nos 50 ms seguintes). Zerar a saída foi descartado (efeitos não documentados de `ABORt`/`SOURce:MODE`/`OUTPut:STATe OFF`, estresse 0→V, risco de contaminar a janela).

Proposta 1 do `atividade.tex`: "Terminar a lista de cada captura com um passo extra que use a forma interna `SIN` da fonte, na tensão base. Esse passo não grava nada na Flash, e a margem final passaria a ser a senoide nominal em todas as classes, em vez do último ciclo mantido. Ainda não testado na bancada." Comentário do professor: "A proposta 1 é simples e deixa as duas margens limpas; vale testar na próxima ida à bancada."

O dono quer um script de teste que importe as partes relevantes do código (sem duplicar a lógica de SCPI), teste na bancada se é eficaz e, se der certo, deixe um branch pronto com PR para `main`.

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data` (PC Windows da bancada; ver `AGENTS.md` para portas e cabos)
- `logica/ametek_orm.py` (`program_capture`, montagem de `LIST:FUNCtion:SHAPe`, `LIST:VOLTage`, `LIST:DWELl`, `LIST:REPeat`; quirk: `LIST:REPeat 1` toca o passo duas vezes, usar 0), `logica/mestre.py`, `logica/oscilloscope_orm.py`
- Scripts de diagnóstico existentes como modelo: `scripts/diag_fonte_vs_osciloscopio.py`, `scripts/diag_saida_vs_medida.py`
- Manual: `docs/analise-2026-09-21/manuais_txt/AMETEK_MX_SCPI_Programming_Manual.txt` (LIST:FUNCtion:SHAPe, nome da forma interna SINE)
- Testes: `.\env\Scripts\python.exe -m unittest tests.test_offline -v`
- Depende de: nada
- Executor: sonnet

## Missão

1. Confirmar no manual e no `TRACe:CATalog?` gravado nas transcrições (`resultados/sessao_*/scpi_transcricao.log`) o nome exato da forma senoidal interna aceita em `LIST:FUNCtion:SHAPe`.
2. Implementar, atrás de uma opção desligada por padrão, o passo extra no fim da lista em `program_capture()` (forma interna senoidal, tensão base, dwell de um ciclo ou mais) e cobrir com teste offline que confere os comandos enviados no modo simulado.
3. Escrever `scripts/teste_passo_final_sin.py`, que importa `AmetekMX30`, o ORM do osciloscópio e uma classe TRACE (sugestão: 06 FLICKER, que deixa o último ciclo em ~1,12 pu), roda a captura com e sem o passo extra e mede o RMS por ciclo da margem final nas duas.
4. Executar o script na bancada, com o operador presente, e decidir se é eficaz: margem final em 1,00 ± 0,01 pu, janela rotulada idêntica à da captura sem o passo (correlação e RMS por ciclo), sem erros SCPI.
5. Se for eficaz: criar o branch `feat/passo-final-sin`, ligar a opção por padrão, commitar, dar push e abrir PR para `main` com os números medidos. Se não for, registrar o resultado e não abrir PR.

## Limites

- Toda energização exige confirmação digitada pelo operador (case-sensitive), como no fluxo atual. Não automatizar confirmações nem inventar o fator de probe.
- Respeitar integralmente `AGENTS.md`, "Limites inegociáveis" (COM10/115200, validações de IDN/timeout/6000 pontos/SCPI, limites de tensão, cache de TRACe, não consultar a fonte logo após `TRACe:DATA`).
- Se houver falha de infraestrutura (serial caiu, OUTPUT não confirmado): confirmar fisicamente OUTPUT OFF, não repetir automaticamente e entregar o log mais recente de `logs\`.
- Pode alterar: `logica/ametek_orm.py` (só o passo extra), `logica/mestre.py` (só a opção), `scripts/teste_passo_final_sin.py`, `tests/test_offline.py`, `CHANGELOG/v1.15.md`.
- Commit e push só no branch `feat/passo-final-sin`; nunca em `main`, nunca merge.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/analise-2026-10-12/passo_final_sin.md`, uma seção por item da Missão, com tabela RMS por ciclo da margem final (com e sem o passo) e o link do PR, se houver.
- Verificação: `.\env\Scripts\python.exe -m unittest tests.test_offline -v` e a saída do script na bancada.
- Toda afirmação sobre código ou valores cita arquivo e linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Reportar tudo o que encontrar, sem filtrar por gravidade; marcar a gravidade ao lado.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

O relatório traz a medida na bancada com e sem o passo e o veredito; se eficaz, o PR para `main` está aberto a partir de `feat/passo-final-sin` com os testes offline passando. Se a bancada não estiver disponível, parar depois do item 3 e marcar os itens 4 e 5 como NÃO VERIFICADO.
