"""Helpers puros dos scripts de auditoria retroativa (Fase E2, E2.7).

Os scripts reprocessam dados históricos SEM modificá-los; estes testes cobrem
a classificação de proveniência de veredito e a recomputação de convergência
sobre estruturas de sessão sintéticas.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "research"))

from audit_extraction_methods import classify_extraction  # noqa: E402
from recompute_convergence import recompute_session  # noqa: E402


class TestClassifyExtraction:
    def test_final_plus_json(self):
        raw = 'ok\nFINAL: PURE\n{"refactoring_type": "pure"}'
        assert classify_extraction(raw) == "final_pattern+json"

    def test_final_only(self):
        assert classify_extraction("analysis...\nFINAL: FLOSS") == "final_pattern"

    def test_json_only(self):
        assert classify_extraction('{"refactoring_type": "floss"}') == "json"

    def test_prose_is_no_verdict(self):
        raw = "pure refactoring with no functional changes only structural"
        assert classify_extraction(raw) == "no_verdict"

    def test_empty(self):
        assert classify_extraction("") == "empty_response"
        assert classify_extraction(None) == "empty_response"
        assert classify_extraction("   ") == "empty_response"


class TestRecomputeSession:
    def test_recomputes_against_recorded(self):
        session = {
            "detailed_analyses": [
                {"purity_classification": "FALSE", "llm_classification": "FLOSS"},
                {"purity_classification": "TRUE", "llm_classification": "PURE"},
                {"purity_classification": "FALSE", "llm_classification": "PURE"},
                {"purity_classification": "None", "llm_classification": "FLOSS"},
            ],
            # o agregado histórico errado (VAL-1): tudo caía em disagree
            "summary": {"convergence_analysis": {"agree": 0, "disagree": 4}},
        }
        result = recompute_session(session)
        assert result["recorded_agree"] == 0
        assert result["recomputed_agree"] == 2
        assert result["recomputed_disagree"] == 1
        assert result["recomputed_not_comparable"] == 1
        assert result["total_analyses"] == 4

    def test_session_without_analyses_returns_none(self):
        assert recompute_session({"summary": {}}) is None
        assert recompute_session({"detailed_analyses": []}) is None

    def test_accepts_legacy_analyses_key(self):
        session = {
            "analyses": [
                {"purity_classification": "TRUE", "llm_classification": "PURE"}
            ]
        }
        result = recompute_session(session)
        assert result["recomputed_agree"] == 1
