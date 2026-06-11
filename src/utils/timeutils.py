"""Timestamps timezone-aware em UTC para todos os pontos de persistência.

Antes da Fase H5 (HARDENING_PLAN.md), o sistema usava datetime.now()
naive (fuso local, sem offset) enquanto o Supabase armazena TIMESTAMPTZ
em UTC — timestamps locais e cloud ficavam desalinhados e ambíguos
entre runners em fusos distintos.

Todos os registros novos usam estas funções. Dados históricos (baseline
TCC e sessões pré-v2.1) mantêm timestamps naive; a descontinuidade está
documentada em docs/REPRODUCIBILITY.md.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Retorna o instante atual como datetime timezone-aware em UTC."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Retorna o instante atual em ISO 8601 com offset UTC (+00:00)."""
    return utc_now().isoformat()


def utc_now_stamp(fmt: str = "%Y-%m-%d_%H-%M-%S") -> str:
    """Retorna o instante atual em UTC formatado para nomes de arquivo."""
    return utc_now().strftime(fmt)
