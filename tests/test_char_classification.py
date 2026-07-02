"""Testes de caracterização para extract_final_classification().

Originalmente escritos (Fase 0.3) contra os métodos privados duplicados
dos dois handlers (_extract_final_classification em llm_handler e
optimized_llm_handler). A Fase 1.2 unificou as implementações em
src/utils/classification.py; estes testes preservam a matriz completa
de padrões que as duas versões reconheciam (superset), agora exercendo
a única fonte de verdade.

Refs: REFACTORING_PLAN.md Fases 0.3 e 1.2; HARDENING_PLAN.md Fase H2.
"""

import sys

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "Código de produção usa sintaxe str | None (requer Python >= 3.10)",
        allow_module_level=True,
    )

from src.utils.classification import extract_final_classification


class TestPrefixPatterns:
    """Padrões com prefixo explícito (case-insensitive)."""

    @pytest.mark.parametrize("text,expected", [
        # Herdados do llm_handler original
        ("FINAL: PURE", "PURE"),
        ("FINAL: FLOSS", "FLOSS"),
        ("FINAL: pure", "PURE"),
        ("FINAL: floss", "FLOSS"),
        ("Final: PURE", "PURE"),
        ("Final: floss", "FLOSS"),
        ("CONCLUSÃO: PURE", "PURE"),
        ("CONCLUSÃO: FLOSS", "FLOSS"),
        ("CONCLUSÃO: pure", "PURE"),
        # Herdados do optimized_llm_handler
        ("CLASSIFICATION: PURE", "PURE"),
        ("CLASSIFICATION: FLOSS", "FLOSS"),
        ("CLASSIFICATION: pure", "PURE"),
        ("CLASSIFICAÇÃO: PURE", "PURE"),
        ("CLASSIFICAÇÃO: floss", "FLOSS"),
        ("RESULTADO: PURE", "PURE"),
        ("RESULTADO: floss", "FLOSS"),
    ])
    def test_prefix_patterns(self, text, expected):
        assert extract_final_classification(text) == expected


class TestIsolatedLinePatterns:
    """Linha isolada contendo apenas PURE ou FLOSS."""

    def test_isolated_line_pure(self):
        text = "Some analysis here.\n\nPURE\n\nMore text."
        assert extract_final_classification(text) == "PURE"

    def test_isolated_line_floss(self):
        text = "Analysis.\n\nFLOSS\n"
        assert extract_final_classification(text) == "FLOSS"


class TestEdgeCases:
    def test_no_pattern_returns_none(self):
        assert extract_final_classification("No classification here") is None

    def test_empty_string_returns_none(self):
        assert extract_final_classification("") is None

    def test_pattern_embedded_in_analysis(self):
        text = (
            "After careful analysis of the diff, I conclude that this is a "
            "pure refactoring with no behavioral changes.\n\n"
            "FINAL: PURE\n\n"
            '{"refactoring_type": "pure"}'
        )
        assert extract_final_classification(text) == "PURE"

    def test_pattern_embedded_with_code_fence(self):
        text = (
            "The code changes only rename methods.\n"
            "FINAL: PURE\n"
            "```json\n{}\n```"
        )
        assert extract_final_classification(text) == "PURE"
