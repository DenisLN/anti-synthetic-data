---
{{ id | yaml_property:"id" }}
{{ titulo | yaml_property:"titulo" }}
{{ status | yaml_property:"status" }}
{{ prioridade | yaml_property:"prioridade" }}
{{ responsavel | yaml_property:"responsavel" }}
{{ frentes | yaml_property:"frentes" }}
{{ evidencias | yaml_property:"evidencias" }}
tags:
  - pendencia
  - {{ status }}
---
# {{ id }} — {{ titulo }}

{% if status == "concluida" %}> [!success] Concluída
{% elseif status == "aguarda-decisao" %}> [!question] Aguarda decisão ou dado do responsável — ver [[docs/projeto/pendencias]]
{% elseif status == "aguarda-bancada" %}> [!todo] Software pronto; falta bancada — ver [[docs/roteiro-bancada]]
{% elseif status == "em-andamento" %}> [!info] Em andamento
{% elseif status == "insuficiente-bancada" %}> [!warning] Insuficiente na bancada: medida feita, resultado inconclusivo — ver [[docs/roteiro-bancada]]
{% else %}> [!failure] Reprovada na bancada — ver [[docs/roteiro-bancada]]
{% endif %}> {{ falta }}

{% if acao != titulo %}- **Ação:** {{ acao }}
{% endif %}- **Depende de:** {{ dependencia }}
- **Fecha quando:** {{ criterio }}
- **Evidências:** {{ evidencias_txt }}

Estado geral: [[docs/projeto/pendencias|estado das pendências]] · [[mapa/Pendencias.base|painel]] · [[mapa/00 Início|início]]
