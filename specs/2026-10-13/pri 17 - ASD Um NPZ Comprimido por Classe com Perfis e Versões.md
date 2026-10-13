#spec #pri 17

# ASD: Um NPZ Comprimido por Classe com Perfis e Versões

## Contexto

Hoje a bancada grava um `.npz` por captura (`logica/mestre.py:2200`), mais `tres_versoes/<mesmo nome>` (modelo, programada, medida) e `snr_XXdb/<mesmo nome>`; o simulado grava um `.npz` por classe (`mestre.py:2335-2364`). Com três perfis (norma, literatura, fronteira) e três versões por aquisição, uma classe gera até 9 séries por captura, espalhadas em muitos arquivos.

Pedido do usuário (2026-10-13): "dentro de um run all, gravar tudo que é da mesma classe no mesmo .npz", unificando perfis e versões, **mas não as SNRs** (que continuam em arquivos separados), e com compressão sem perda (`np.savez_compressed`). O gerador de HTML deve ler as capturas desejadas e montar de acordo. O metadata precisa ser ajustado. Deixar um aviso no `CHANGELOG/v1.15.md` de que scripts que liam os `.npz` individuais vão quebrar. Mapear todos os consumidores e mudá-los.

Hoje um `run all` roda um só perfil (`set perfil`). Para os três perfis caberem no `.npz` da classe na mesma sessão, o `run all` (e o `run` com lista) precisa poder percorrer os perfis: `set perfil todos`. Autorização do usuário para mexer em `logica/recortar_margem.py` e `logica/relatorio_html.py`: este pedido (registrar em `AGENTS.md`).

## Entradas

- Escrita: `logica/mestre.py` (`_salvar_captura`, `_finalizar_gravacao`, `_salvar_classe_simulada`, `executar_bateria`, `PERFIL`), `logica/cli.py` (`set perfil`)
- Consumidores (`git grep -n "np.load\|glob(\"\*.npz\")"`): `logica/recortar_margem.py`, `logica/analisar_sessao.py`, `logica/relatorio_html.py`, `scripts/recalibrar_extremos.py`, `scripts/gerar_tres_versoes.py`, `scripts/gerar_ruido_janela.py`, `tests/test_offline.py`
- Formato: `docs/dataset.md`, `docs/metadata.md`, `docs/tres_versoes.md`
- Depende de: ASD: RMS por Ciclo da TRACE sem a Média e Previsão de Pico Correta; ASD: Rastreabilidade da Semente do Ruído e da Árvore Suja

## Missão

1. Definir e documentar o formato: um `NN_classe.npz` comprimido por classe e sessão, com chaves `<perfil>/<versao>` (`medida`, `modelo`, `programada`) empilhadas por captura, `id_captura` por perfil, `tempo_ms`, e o índice de cada captura no metadata (`arquivo_classe`, `perfil`, `indice_no_arquivo`); SNRs fora dele, em arquivos por classe e nível.
2. Implementar a escrita na bancada (acumulando por classe, gravação atômica com `.part`, sem perder capturas já feitas se a classe for interrompida) e no simulado.
3. Implementar `set perfil todos` (o `run all`/`run` com lista percorre norma, literatura e fronteira na mesma sessão, com o total de capturas e gravações de TRACe somado na confirmação).
4. Migrar todos os consumidores para o formato novo, mantendo leitura das sessões antigas (um `.npz` por captura) quando custar pouco; onde não for mantida, dizer qual quebra. `relatorio_html.py` ganha seleção por `--classes`, `--perfis`, `--versoes` e `--capturas`.
5. Registrar em `CHANGELOG/v1.15.md`, com aviso destacado de quebra para quem lia os `.npz` individuais, e atualizar `docs/dataset.md`, `docs/metadata.md` (só acrescentar campos), `docs/tres_versoes.md` e `AGENTS.md` (autorização).

## Limites

- Compressão só sem perda; dtypes preservados (o teste compara arrays bit a bit com o que seria gravado antes).
- Não mudar `gerar()`, o ruído, as validações nem os limites de segurança.
- Não apagar nem reescrever sessões existentes em `resultados/`.
- Não tocar no hardware.

## Entregável

- Relatório por item, com a lista de consumidores e o que mudou em cada um.
- Verificação: `python -m unittest tests.test_offline` (testes: sessão simulada com `set perfil todos` gera um `.npz` por classe com as 9 chaves; a leitura devolve exatamente os arrays; sessão antiga continua legível onde prometido; HTML seleciona perfil/versão).

## Critério de Parada

Sessão simulada com `set perfil todos` tem um `.npz` comprimido por classe com perfis × versões e as SNRs fora; todos os consumidores listados leem o formato novo (testes); aviso de quebra no CHANGELOG; suíte sem falha nova.
