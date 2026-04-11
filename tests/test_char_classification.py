"""Testes de caracterização para _extract_final_classification().

Testa ambas as implementações (llm_handler e optimized_llm_handler) para
garantir que a versão unificada (Fase 1.2) cobrirá todos os padrões.

Refs: REFACTORING_PLAN.md Fase 0.3
"""

import sys

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "Código de produção usa sintaxe str | None (requer Python >= 3.10)",
        allow_module_level=True,
    )

from src.handlers.llm_handler import LLMHandler
from src.handlers.optimized_llm_handler import OptimizedLLMHandler


@pytest.fixture
def llm_handler():
    """LLMHandler com host falso (não faz chamadas reais)."""
    return LLMHandler(model="test", host="http://fake:11434/api/generate")


@pytest.fixture
def opt_handler():
    """OptimizedLLMHandler com modelo falso."""
    return OptimizedLLMHandler(model="test")


# ---------------------------------------------------------------------------
# Padrões comuns a ambos os handlers
# ---------------------------------------------------------------------------

class TestCommonPatterns:
    """Padrões que ambos os handlers devem reconhecer."""

    @pytest.mark.parametrize("text,expected", [
        ("FINAL: PURE", "PURE"),
        ("FINAL: FLOSS", "FLOSS"),
        ("FINAL: pure", "PURE"),
        ("FINAL: floss", "FLOSS"),
        ("Final: PURE", "PURE"),
        ("Final: floss", "FLOSS"),
        ("CONCLUSÃO: PURE", "PURE"),
        ("CONCLUSÃO: FLOSS", "FLOSS"),
        ("CONCLUSÃO: pure", "PURE"),
    ])
    def test_basic_handler(self, llm_handler, text, expected):
        assert llm_handler._extract_final_classification(text) == expected

    @pytest.mark.parametrize("text,expected", [
        ("FINAL: PURE", "PURE"),
        ("FINAL: FLOSS", "FLOSS"),
        ("FINAL: pure", "PURE"),
        ("Final: PURE", "PURE"),
        ("CONCLUSÃO: PURE", "PURE"),
        ("CONCLUSÃO: FLOSS", "FLOSS"),
    ])
    def test_optimized_handler(self, opt_handler, text, expected):
        assert opt_handler._extract_final_classification(text) == expected


# ---------------------------------------------------------------------------
# Padrões exclusivos do optimized_llm_handler
# ---------------------------------------------------------------------------

class TestOptimizedExtraPatterns:
    """Padrões que só o optimized_llm_handler reconhece."""

    @pytest.mark.parametrize("text,expected", [
        ("CLASSIFICATION: PURE", "PURE"),
        ("CLASSIFICATION: FLOSS", "FLOSS"),
        ("CLASSIFICATION: pure", "PURE"),
        ("RESULTADO: PURE", "PURE"),
        ("RESULTADO: floss", "FLOSS"),
    ])
    def test_extra_prefixes(self, opt_handler, text, expected):
        assert opt_handler._extract_final_classification(text) == expected

    def test_isolated_line_pure(self, opt_handler):
        text = "Some analysis here.\n\nPURE\n\nMore text."
        result = opt_handler._extract_final_classification(text)
        assert result == "PURE"

    def test_isolated_line_floss(self, opt_handler):
        text = "Analysis.\n\nFLOSS\n"
        result = opt_handler._extract_final_classification(text)
        assert result == "FLOSS"


# ---------------------------------------------------------------------------
# Edge cases (ambos)
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_no_pattern_returns_none_basic(self, llm_handler):
        assert llm_handler._extract_final_classification("No classification here") is None

    def test_no_pattern_returns_none_optimized(self, opt_handler):
        assert opt_handler._extract_final_classification("No classification here") is None

    def test_empty_string_basic(self, llm_handler):
        assert llm_handler._extract_final_classification("") is None

    def test_empty_string_optimized(self, opt_handler):
        assert opt_handler._extract_final_classification("") is None

    def test_pattern_embedded_in_analysis(self, llm_handler):
        text = (
            "After careful analysis of the diff, I conclude that this is a "
            "pure refactoring with no behavioral changes.\n\n"
            "FINAL: PURE\n\n"
            '{"refactoring_type": "pure"}'
        )
        assert llm_handler._extract_final_classification(text) == "PURE"

    def test_pattern_embedded_in_analysis_optimized(self, opt_handler):
        text = (
            "The code changes only rename methods.\n"
            "FINAL: PURE\n"
            "```json\n{}\n```"
        )
        assert opt_handler._extract_final_classification(text) == "PURE"
