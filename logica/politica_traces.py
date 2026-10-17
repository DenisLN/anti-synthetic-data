"""Orçamento operacional conservador; não representa limite do fabricante."""

LIMITE_ESCRITAS_TRACE_CONEXAO = 216


class LimiteEscritasTraceError(RuntimeError):
    """Conexão sem orçamento para a operação; abortar a campanha sem retry."""
