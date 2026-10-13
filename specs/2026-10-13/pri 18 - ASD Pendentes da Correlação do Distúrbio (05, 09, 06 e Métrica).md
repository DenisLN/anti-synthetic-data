#spec #pri 18

# ASD: Pendentes da Correlação do Distúrbio (05, 09, 06 e Métrica)

## Contexto

O relatório pendente `correlacao_disturbio_diagnostico_IMPLEMENTAR.md` (agora no branch `arquivo/analises`, em `docs/analise-2026-10-12/pendente/`) deixou itens para implementar. O usuário pediu cuidado especial com eles.

- **05**: "na 05 vamos implementar o `sinais.senoide_clipada_pu` em `gerar()` para THD ≤ 20 %; correlação pequena, se for relevante mudamos depois." Já está em `experimentos_nativos/05.py:48-51` com o sorteio ligado. Falta conferir a implementação contra o diagnóstico (normalização por rms obrigatória, mesma fase do `forma_programada_nativa`, teto de 20 %) e o nível de 30 % por TRACe, cujo modelo tem rms 0,738 (soma de harmônicas com fundamental 1 pu) enquanto a fonte escala a TRACE para o `LIST:VOLTage`.
- **09**: diagnosticar como a 08 (impulso espúrio em 100 ms, ver a spec do diagnóstico da cópia).
- **Métrica**: a correlação do distúrbio subtrai uma senoide de 1 pu fixa; 1 % de erro de fundamental pesa até 0,05–0,06 nas classes de distúrbio pequeno (09). Recomendação: relatar também a correlação depois de ajustar a fundamental de cada sinal.
- **06**: perde correlação já na TRACE por ciclo (modelo × programada 0,846–0,969; um `LIST:VOLTage` por ciclo não segue modulação de 10–21 Hz). Não analisado.

## Entradas

- `experimentos_nativos/05.py`, `logica/sinais.py` (`senoide_clipada_pu`, `corte_da_senoide_clipada`, `forma_programada_nativa`, `correlacao_disturbio`), `logica/analisar_sessao.py`, `logica/relatorio_html.py`, `experimentos_waveform/06.py`
- `docs/correlacao_disturbio.md`, `docs/classes.md`
- Depende de: ASD: RMS por Ciclo da TRACE sem a Média e Previsão de Pico Correta; ASD: Diagnóstico da Cópia do Evento em 100 ms (Classes 08 e 09)

## Missão

1. Conferir a 05 contra o diagnóstico (THD, rms, fase, teto) com testes; decidir e implementar a coerência do nível de 30 % entre modelo e programada (modelo normalizado ao rms que a fonte emite, ou documentar por que não), sem mexer no que `gerar()` produz para o sorteio desligado.
2. Implementar `correlacao_disturbio_fundamental_ajustada` (ajuste de amplitude e fase da fundamental em cada sinal antes do resíduo) e expô-la em `analisar_sessao.py` e no HTML ao lado da métrica atual, com caso degenerado tratado como na métrica atual.
3. Incluir a 09 no diagnóstico da cópia em 100 ms (as ferramentas da spec de diagnóstico rodam nela) e, com o resultado offline disponível, decidir se a 09 entra na campanha de amanhã; registrar a decisão no roteiro.
4. Quantificar a perda da 06 na TRACE por ciclo (modelo × programada por perfil e frequência) e propor, sem implementar, se vale mudar a programação.
5. Atualizar `docs/correlacao_disturbio.md`, `docs/classes.md` e `CHANGELOG/v1.15.md`.

## Limites

- Mudar o que `gerar()` produz para o sorteio ligado só na 05 nível de 30 %, e só se o item 1 concluir que é necessário (fixture `gerar_sorteio_v1_15.json` regravado só nessas entradas, `gerar_literatura_34a0d82.json` intacto).
- Não remover o `assert_no_errors()` após `SOURce:FUNCtion:SHAPe:CSINusoid`.
- Não tocar no hardware.

## Entregável

- Relatório por item com tabelas.
- Verificação: `python -m unittest tests.test_offline`.

## Critério de Parada

Testes da 05 cobrem THD/rms/fase; a métrica com fundamental ajustada aparece em `analisar_sessao` e no HTML (teste com sinal de amplitude 1 % maior dá correlação ≈ 1); a 06 tem número; suíte sem falha nova.
