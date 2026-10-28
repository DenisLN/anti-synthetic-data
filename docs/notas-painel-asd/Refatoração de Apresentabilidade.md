#spec #pri 2

# ASD: Refatoração de Apresentabilidade

## Contexto

O projeto começou como apenas para adquirir dados para treinar um dataset de ML para o meu trabalho de conclusão de curso. Entretanto, agora o professor pede que o projeto seja versionável, com tags a cada versão. 

```tex
Ótimo. Quando a próxima versão for congelada, vale criar uma \emph{tag} no GitHub e
arquivar no Zenodo: o código ganha DOI e o paper cita a versão exata. Uma regra para
as próximas campanhas: as sessões de 07/10 registram \texttt{994e170-dirty}, ou seja,
código com alteração não commitada. Daqui para frente, toda sessão sai de commit
limpo, e o metadata grava o commit, a versão do numpy e uma cópia da
\texttt{calibracao\_extremos.json} usada.
```

Portanto, para deixar o projeto "arquivável", precisamos corrigir quaisquer erros na sua apresentação. 


Além disso, precisamos documentar como o código funciona e como estender para criar novas classes, evitando que surjam erros e equívocos já documentados. Se algum comportamento precisar ser corrigido, primeiro diagnosticar com funções de diagnóstico interna `set diagnostico on` ou elaborar script que chame as funções do projeto de forma separada, e reproduza um comportamento para testes. 

## Entradas

- Repositório `anti-syntetic-data`;
- Histórico de commits;
- Documento .tex de QnA comentado pelo professor.

## Missão

- Analisar os documentos de `CHANGELOG` e verificar se o `README.MD` está de acordo; 
- Padronizar em `AGENTS.md` como escrever sobre mudanças no código, como versioná-lo;
- Dividir o `README.md` em arquivos separados em `docs/` e referenciá-los.  
- Documentar de maneira como o código funciona, os comandos SCPI que são usados na comunicação e sua função; 
- Os quirks dos equipamentos utilizados no projeto; 
- As decisões que foram utilizadas ao longo do caminho.

## Limites

- Não mudar absolutamente nada de código Python, apenas ler; 
- Não mudar nada sobre os metadados; 
- Liberdade para todos `.md`.

## Entregáveis

- `README.md` conferido e dividido;
- Arquivos `.md` conferidos e revisados, dentro de `docs/`.

## Critério de Parada

- Verificar que não existe nenhuma ambiguidade em nenhuma documentação; 
- Verificar que toda a estrutura do projeto está documentada; 
- Verificar que alguém sem conhecimento prévio do projeto consiga ler as documentações e entender como ele funciona e aumentá-lo;
- Não commitar seu trabalho.
