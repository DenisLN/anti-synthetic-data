# Pendências P-01 a P-31: estado, resolução e perguntas ao dono

```{include} /_includes/aviso-base.md
```

{bdg-info}`OFFLINE` Esta página é gerada no build a partir de `docs/estado_prontidao.json` (formato em {doc}`../contribuir_docs`): o que ela mostra é o que está commitado. Para cada uma das 31 pendências ela diz o que foi pedido, o estado verdadeiro, **como foi resolvida** (ou o que foi feito até agora, com commit e evidência), o que falta (separado em bancada, código e decisão do dono) e se a escolha feita no fork foi **confirmada pelo dono** ou está **tomada no fork, aguardando confirmação**.

:::{important} O que esta página não faz
Ela não decide nada pelo dono. Uma pendência marcada como concluída com a escolha "tomada no fork" foi resolvida por quem trabalhou no fork (`rmlinxic/anti-synthetic-data`, integrado à `main` em 27/10/2026), por "autorização do usuário nesta sessão" (`execucao_pendencias.md`); isso não é a resposta do dono em `docs/decisoes_pendentes.md`. Simulação não é medição: nenhuma pendência física fica concluída sem evidência de bancada, e o fechamento de `scripts/fechar_pendencias.py` é evidência, não encerramento. Licença, autoria, citação e DOI (P-20) não existem e não são criados antes da resposta do dono.
:::

Os níveis de evidência vêm de `docs/evidencias/2026-10-16/` a `2026-10-22/`. As sessões físicas de 22/10 ficam no PC da bancada, fora do repositório: o que a página afirma sobre elas é o que `fechamento.json` registra (com SHA-256), e foi marcado **NÃO VERIFICADO** onde só a sessão original provaria.

## Estado atual

@@pendencias-estado@@

## Pedido original e histórico

O pedido original de cada pendência (classe afetada, fonte, opções e "o que fecha", como levantados em 16/10/2026) está no {doc}`inventário histórico <pendencias-inventario-2026-10-16>`; cada seção acima tem o link para o item correspondente. O registro de rodadas e os critérios de execução estão em {doc}`../execucao_pendencias`, o roteiro de fechamento na bancada em {doc}`../bancada_pendencias` e o formulário do dono em {doc}`../decisoes_pendentes`.
