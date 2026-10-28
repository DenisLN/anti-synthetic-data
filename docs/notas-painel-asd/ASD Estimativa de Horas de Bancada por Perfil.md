#spec #pri 2

# ASD: Estimativa de Horas de Bancada por Perfil

## Contexto

Pergunta do professor (`atividade.tex`, questão da seção "Adequação das classes à IEEE 1159"): "O custo é tempo de bancada, porque cada perfil multiplica a campanha. Conseguem estimar quantas horas leva cada perfil com, por exemplo, 50 capturas por classe, já contando a escrita na Flash e o travamento por volta da 280.ª gravação?"

Fatos conhecidos: gravar as TRACEs leva ≈ 20 s por captura TRACE; depois do sorteio de início e fase, toda captura TRACE passa a gravar a Flash (o cache de TRACe só reaproveita forma idêntica); a fonte travou por volta da 280.ª gravação na mesma conexão (16/09); classes nativas não gravam Flash. Os perfis são norma, literatura e fronteira.

É um cálculo pequeno, a partir dos logs reais.

## Entradas

- Repositório: `C:\Users\denis\Documents\1 Projetos\anti-synthetic-data`
- Logs com tempos reais: `resultados/sessao_2026-10-07_*/` (`scpi_transcricao.log`, metadata com timestamps) e `logs\startup-bench-*.log`
- Lista de classes e mecanismo (TRACE ou nativa): `atividade.tex`, Tabela `tab:classes`; `experimentos_nativos/` e `experimentos_waveform/`
- Estimativa de gravações já calculada pela CLI antes do `run all`: `logica/cli.py`
- Depende de: ASD: Início, Duração e Fase Sorteados no gerar()
- Executor: haiku

## Missão

1. Medir nos logs de 07/10 o tempo médio por captura em cada tipo de classe (TRACE com gravação, TRACE sem gravação, nativa), incluindo validação e gravação em disco.
2. Calcular as horas de uma campanha de 50 capturas por classe, 20 classes, para um perfil, considerando que toda captura TRACE grava a Flash e que é preciso reconectar antes de 280 gravações (estimar o tempo de uma reconexão pelos logs, ou marcar NÃO VERIFICADO).
3. Repetir para os três perfis e para 127 V em 50 e 60 Hz; dizer se algum perfil muda o número de capturas puladas.
4. Escrever um parágrafo de resposta ao professor com os números.

## Limites

- Somente leitura. Não alterar nada no repositório além do relatório.
- Não tocar no hardware. Não commitar.
- Se o pedido parecer equivocado ou existir abordagem melhor, dizer isso em uma frase e seguir com o que foi pedido.

## Entregável

- Arquivo: `docs/analise-2026-10-12/estimativa_horas_perfil.md`, uma seção por item da Missão, com a conta explícita.
- Toda afirmação sobre valores cita o log e a linha, ou o comando e a saída que a mostram.
- O que não deu para confirmar entra como NÃO VERIFICADO, com o motivo. Nunca presumir.
- Tamanho proporcional ao que a tarefa exige: sem seções de enchimento, resumos redundantes ou boilerplate.

## Critério de Parada

O relatório traz as horas por perfil com a conta reproduzível e o parágrafo para o professor.
