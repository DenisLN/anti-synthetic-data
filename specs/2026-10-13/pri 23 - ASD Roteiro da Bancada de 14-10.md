#spec #pri 23

# ASD: Roteiro da Bancada de 14/10

## Contexto

Bancada em 14/10/2026. Decisão do usuário: primeiro o diagnóstico (cópia do evento em 100 ms com marcadores por ciclo; amplitude CA em ACDC; recaptura da 08 a 127 V/50 Hz), depois a campanha, porque o diagnóstico pode mudar o que vale coletar. Pediu um `.md` de roteiro.

Fatos que o roteiro precisa respeitar: o `run all` padrão planeja 468 gravações de TRACe numa conexão contra a trava em ~280 (rodar por partes com `run <lista>`); toda sessão sai de commit limpo e a CLI é reiniciada depois de commitar (`git_sujo`); confirmações digitadas case-sensitive (`ENERGIZAR-TESTE`, `ENERGIZAR-COMANDOS`, `EXECUTAR-CLASSE-<NN>`, `EXECUTAR-CLASSES-<lista>`, `EXECUTAR-20-CLASSES`, e as dos scripts de diagnóstico); fator da probe confirmado na probe física, nunca presumido; captura de corrente desligada; em falha de infraestrutura: OUTPUT OFF no painel, não repetir, entregar `sessao.log` e `scpi_transcricao.log`.

## Entradas

- Resultado de todas as specs desta rodada (pri 10 a 22), em especial: diagnóstico da cópia em 100 ms, leitura das TRACEs gravadas, pendentes offline (lista do item 4), `run` com lista, preflight único, NPZ por classe
- Relatórios pendentes no branch `arquivo/analises` (`classe08_fronteira`, `acdc_amplitude`, `classes_05_07_18`, `compostas_sorteadas`, `sorteio_inicio_fase`, `correlacao_disturbio_diagnostico`)
- `docs/operacao.md`, `AGENTS.md`
- Depende de: ASD: Documentação Autocontida sem Atribuição a Pessoas; ASD: Pendentes de Classe Conferíveis Offline (07, 17, 18, 19 e Sorteio); ASD: Pendentes da Correlação do Distúrbio (05, 09, 06 e Métrica); ASD: Revisão das Compostas Sorteadas contra a Proposta

## Missão

1. Escrever `ROTEIRO_BANCADA_2026-10-14.md` na raiz do repositório, em blocos na ordem de execução (preparação e commit limpo; `comm`/`trigger`/`lowvoltage`/`native`; diagnóstico offline das sessões de 07/10; marcadores por ciclo; ACDC; recaptura da 08; verificações do sorteio, 05/07/17/18; campanha por partes), cada bloco com comandos exatos, confirmação digitada, tempo estimado, o que conferir e critério de seguir/parar.
2. Incluir uma tabela de decisão: para cada resultado possível do diagnóstico (marcadores e ACDC), o que muda na campanha do mesmo dia (ex.: excluir 09, rodar a 08 só a 60 Hz).
3. Incluir o plano da campanha em partes com a conta de gravações de TRACe por parte (< 250 por conexão) e o tempo estimado (2 s por ciclo de TRACe, ~2,5 s por captura nativa, 18 s por conexão).
4. Incluir o checklist de entrega ao fim do dia (arquivos a copiar, `git status`, recalibração conferida com `git diff`).

## Limites

- Não executar nada na bancada; não automatizar confirmações; não inventar o fator da probe.
- Não ativar captura de corrente.

## Entregável

- `ROTEIRO_BANCADA_2026-10-14.md` e relatório curto por item.

## Critério de Parada

O roteiro cobre os 4 itens, cada comando citado existe no código (conferido por `git grep`), e as contas de TRACe por parte ficam abaixo de 250.
