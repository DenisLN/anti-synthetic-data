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
{% elseif status == "aguarda-decisao" %}> [!question] Aguarda decisão ou dado do responsável — ver [[docs/decisoes_pendentes]]
{% else %}> [!todo] Software pronto; falta bancada — ver [[docs/bancada_pendencias]]
{% endif %}> {{ falta }}

{% if acao != titulo %}- **Ação:** {{ acao }}
{% endif %}- **Depende de:** {{ dependencia }}
- **Fecha quando:** {{ criterio }}
- **Evidências:** {{ evidencias_txt }}

Estado geral: [[docs/PENDENCIAS_TRACKER|rastreador]] · [[mapa/Pendencias.base|painel]] · [[mapa/00 Início|início]]
