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

# Resultados canônicos da comparação Purity × LLM
AGREE = "agree"
DISAGREE = "disagree"
NOT_COMPARABLE = "not_comparable"


def _normalize_purity(value) -> Optional[str]:
    """Normaliza a classificação consolidada do Purity Checker para PURE/FLOSS.

    Aceita os dois vocabulários em uso no projeto:
    - CSV/sessões: 'TRUE' (pure), 'FALSE' (floss), 'None'/'NONE' (sem veredito)
    - Handlers/booleans: True/False (inclusive numpy.bool_, via str()), 'pure'/'floss'

    Retorna None para valores sem veredito ('None', NaN, '', 'not_in_purity'...),
    que são NÃO COMPARÁVEIS — nunca devem contar como concordância/discordância.
    """
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in ("true", "pure"):
        return PURE
    if normalized in ("false", "floss"):
        return FLOSS
    return None


def _normalize_llm(value) -> Optional[str]:
    """Normaliza a classificação do LLM; FAILED/ERROR/DRY_RUN/etc. viram None."""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized if normalized in VALID_CLASSIFICATIONS else None


def compare_purity_llm(purity_classification, llm_classification) -> str:
    """Compara Purity Checker × LLM no vocabulário unificado (fonte única).

    Mapeamento semântico: TRUE↔PURE e FALSE↔FLOSS — o mesmo da view SQL
    `model_metrics` (supabase/migrations/001_initial_schema.sql). Antes desta
    função, o analisador comparava PURE/FLOSS com os literais 'TRUE'/'FALSE'
    e reportava convergência zero em toda sessão (EVOLUTION_PLAN.md, VAL-1);
    o purity_handler mantinha duas definições divergentes de agreement (VAL-9).

    Returns:
        AGREE | DISAGREE quando ambos os lados têm veredito comparável;
        NOT_COMPARABLE quando qualquer lado não tem veredito (Purity None,
        LLM FAILED/ERROR/DRY_RUN/não analisado).
    """
    purity = _normalize_purity(purity_classification)
    llm = _normalize_llm(llm_classification)
    if purity is None or llm is None:
        return NOT_COMPARABLE
    return AGREE if purity == llm else DISAGREE


def summarize_convergence(pairs) -> dict:
    """Agrega comparações (purity, llm) em contagens {agree, disagree, not_comparable}.

    Args:
        pairs: iterável de tuplas (purity_classification, llm_classification).
    """
    counts = {AGREE: 0, DISAGREE: 0, NOT_COMPARABLE: 0}
    for purity, llm in pairs:
        counts[compare_purity_llm(purity, llm)] += 1
    return counts


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
