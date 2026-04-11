"""Configuração centralizada de logging para o Refan.

Fornece loggers nomeados com formatação consistente. Os handlers de
terminal preservam as cores ANSI existentes (via colors.py), enquanto
os handlers de arquivo gravam sem formatação para facilitar parsing.

Uso:
    from src.utils.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Mensagem")
    logger.warning("Aviso")

Refs: REFACTORING_PLAN.md Phase 4.2
"""

import logging
import sys


_configured = False


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger nomeado com configuração padrão.

    Na primeira chamada, configura o root logger com StreamHandler
    para stderr. Chamadas subsequentes retornam loggers filhos que
    herdam a configuração.
    """
    global _configured
    if not _configured:
        _configure_root()
        _configured = True
    return logging.getLogger(name)


def _configure_root():
    """Configura o root logger com formatação padrão."""
    root = logging.getLogger()
    if root.handlers:
        return  # Já configurado (ex: por pytest ou outro framework)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
