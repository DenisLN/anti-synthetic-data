---
title: Mapa do projeto anti-synthetic-data
tags:
  - mapa
  - moc
aliases:
  - Início
  - Mapa
---
# Mapa do projeto

TCC: a fonte **AMETEK MX30** gera distúrbios de qualidade de energia e o osciloscópio **Keysight DSO-X 4034A** os captura. O objetivo é validar fisicamente um dataset sintético de 20 classes. Versão corrente: **v1.15** (sem tag), branch `feat/execucao-pendencias-v1-15`.

> [!tip] Como navegar gastando pouco contexto
> 1. Leia só esta nota. Siga **apenas** os links da tarefa em mãos.
> 2. Tarefa sobre uma pendência → abra `[[P-NN]]` (10–20 linhas). Os backlinks mostram os módulos envolvidos.
> 3. Tarefa sobre código → cartão em `mapa/codigo/`, depois o guia `docs/codigo/<módulo>` se precisar, e só então o `.py` (com `grep`, nunca inteiro).
> 4. Não leia por inteiro `ROTEIRO_BANCADA.md` (45 KB), `AGENTS.md`, `docs/execucao_pendencias.md` nem `logica/mestre.py`. Use `grep -n`.

> [!danger] Limites inegociáveis
> COM10/115200 fixos; limites RMS/pico/corrente intocáveis; nenhuma validação SCPI enfraquecida; `gerar()`/fixtures só com autorização. **Toda energização exige confirmação digitada pelo operador presente; agente nunca digita.** Ver [[mapa/dominio/Segurança e limites]] e `AGENTS.md` § "Limites inegociáveis".

## Estado

- Placar e protocolo: [[docs/PENDENCIAS_TRACKER|rastreador]] (fonte única de estado)
- Painel: [[mapa/Pendencias.base|Pendências (Base)]] · mapa visual: [[mapa/Mapa.canvas|canvas]]
- Visita à bancada: [[docs/bancada_pendencias]] · decisões do responsável: [[docs/decisoes_pendentes]]

## Domínio

- [[mapa/dominio/Bancada|Bancada e PC]] · [[mapa/dominio/Operação na bancada|Operação]]
- [[mapa/dominio/Classes|As 20 classes]] · [[mapa/dominio/Fluxo de uma captura|Fluxo de uma captura]]
- [[mapa/dominio/Dataset e sessões|Dataset e sessões]] · [[mapa/dominio/Segurança e limites|Segurança e limites]]

## Código (`logica/`)

| Camada | Cartões |
|---|---|
| Interface | [[mapa/codigo/cli\|cli]] · [[mapa/codigo/preflight_new\|preflight_new]] |
| Orquestração | [[mapa/codigo/mestre\|mestre]] · [[mapa/codigo/perfis\|perfis]] · [[mapa/codigo/politica_traces\|politica_traces]] |
| Instrumentos | [[mapa/codigo/ametek_orm\|ametek_orm]] · [[mapa/codigo/oscilloscope_orm\|oscilloscope_orm]] · [[mapa/codigo/modelo_lista_fonte\|modelo_lista_fonte]] |
| Sinais | [[mapa/codigo/sinais\|sinais]] · [[mapa/codigo/recortar_margem\|recortar_margem]] |
| Persistência | [[mapa/codigo/sessao_io\|sessao_io]] · [[mapa/codigo/bruto_osciloscopio_io\|bruto_osciloscopio_io]] |
| Análise | [[mapa/codigo/analisar_sessao\|analisar_sessao]] · [[mapa/codigo/relatorio_html\|relatorio_html]] |
| Scripts | [[mapa/codigo/scripts\|scripts/ por função]] |

## Atualizar este mapa

Quando uma pendência mudar de estado: edite a linha dela em [[docs/PENDENCIAS_TRACKER]] e `docs/estado_prontidao.json`, e rode `python scripts/gerar_mapa_pendencias.py` (Node.js 20+, usa Knap). Isso regenera `mapa/pendencias/`. Não edite as notas `P-NN` à mão.

Documentação completa (site Sphinx): [[docs/index]] · [[docs/arquitetura]] · [[docs/codigo]] · [[docs/glossario]]
