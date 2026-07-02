"""Constantes e extração de classificação de refatoramento.

Consolida _extract_final_classification() de:
- llm_handler.py:459-483 (6 padrões)
- optimized_llm_handler.py:1036-1070 (13 padrões)

A versão unificada usa re.IGNORECASE em todos os padrões, eliminando
as duplicatas upper/lower. Resultado: 6 padrões (superset) vs 19 originais.

Refs: REFACTORING_PLAN.md Phase 1.2
"""

from typing import Optional
import re

# Constantes canônicas de classificação
PURE = "pure"
FLOSS = "floss"
VALID_CLASSIFICATIONS = frozenset({PURE, FLOSS})


def extract_final_classification(response: str) -> Optional[str]:
    """Extrai classificação PURE/FLOSS de padrões na resposta LLM.

    Procura por padrões como 'FINAL: PURE', 'CLASSIFICAÇÃO: FLOSS',
    'RESULTADO: PURE', ou linhas isoladas contendo apenas PURE/FLOSS.

    Returns:
        'PURE' ou 'FLOSS' em uppercase, ou None se não encontrado.
    """
    patterns = [
        # Padrões explícitos com prefixo (presentes em ambos os handlers)
        r'FINAL:\s*(PURE|FLOSS)',
        r'CONCLUS[ÃA]O:\s*(PURE|FLOSS)',
        # Padrões exclusivos do optimized_llm_handler
        r'CLASSIFICA[CÇ][ÃA]O:\s*(PURE|FLOSS)',
        r'CLASSIFICATION:\s*(PURE|FLOSS)',
        r'RESULTADO:\s*(PURE|FLOSS)',
        # Linha isolada contendo apenas PURE ou FLOSS
        r'^\s*(PURE|FLOSS)\s*$',
    ]
    for pattern in patterns:
        match = re.search(pattern, response, re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip().upper()
            if value in {"PURE", "FLOSS"}:
                return value
    return None
