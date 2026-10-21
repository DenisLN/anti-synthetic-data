---
tipo: dominio
tags: [dominio]
---
# Segurança e limites
> [!danger] Inegociáveis (AGENTS.md)
> - `AMETEK_PORT=COM10`, `AMETEK_BAUDRATE=115200` fixos (`validate_bench_configuration`).
> - Não enfraquecer IDN, timeout, 6000 pontos, `assert_no_errors`/`check_errors`.
> - Não alterar `max_voltage_rms`, `max_peak_v`, `max_current_a` nem `ParameterOutOfBoundsError`.
> - Saída só com confirmação digitada, case-sensitive.
> - Abortar sem retry em `CommunicationError`/`FalhaFatalDeInstrumento`.
> - Corrente desligada por padrão (exige fator da probe e corrente-base).
- Onde moram: [[mapa/codigo/ametek_orm|ametek_orm]], [[mapa/codigo/mestre|mestre]], [[mapa/codigo/cli|cli]], [[mapa/codigo/politica_traces|politica_traces]] (216 gravações TRACe, [[P-23]]).
- Docs: [[docs/seguranca|segurança]], [[docs/codigo/invariantes|invariantes]], [[docs/limites_e_calibracao|limites e calibração]].
