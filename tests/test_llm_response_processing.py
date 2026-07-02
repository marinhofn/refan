"""Contrato de extração de resposta do LLM (Fase E2, VAL-2/VAL-3).

Regressões cobertas:
- VAL-2: respostas sem veredito explícito eram classificadas por contagem de
  palavras-chave e gravadas como se fossem do modelo, sem marcação nem log de
  falha (o bloco de logging era inalcançável). Agora: sem linha FINAL: e sem
  JSON com refactoring_type válido -> falha registrada + None.
- VAL-3: no caminho dominante (FINAL:), confidence_level/technical_evidence
  eram fabricados a jusante ("medium"/"") e justification recebia a resposta
  bruta inteira. Agora: variáveis de pesquisa vêm só do JSON do modelo;
  ausentes ficam None; extraction_method registra a proveniência do veredito.
"""

import json

import pytest

from src.handlers.llm_handler import LLMHandler
from src.models.adapters import analysis_from_llm_response, analysis_to_session_dict
from src.models.commit import CommitPair


@pytest.fixture
def handler(tmp_path):
    h = LLMHandler(model="mistral")
    h.failures_file = str(tmp_path / "failures.jsonl")
    return h


def _failures_logged(handler) -> list[dict]:
    try:
        with open(handler.failures_file, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


FULL_RESPONSE = (
    "The diff only renames a method.\n"
    "FINAL: PURE\n"
    '{"refactoring_type": "pure", "justification": "rename only", '
    '"confidence_level": "high", "technical_evidence": "lines 10-12"}'
)


class TestProcessLlmResponse:
    def test_final_plus_json_uses_model_declared_fields(self, handler):
        result = handler._process_llm_response(
            FULL_RESPONSE, "msg", commit_hash="c2", previous_hash="c1", repository="repo"
        )
        assert result["refactoring_type"] == "pure"
        assert result["extraction_method"] == "final_pattern+json"
        # VAL-3: valores vêm do modelo, não de defaults
        assert result["confidence_level"] == "high"
        assert result["technical_evidence"] == "lines 10-12"
        assert result["justification"] == "rename only"
        assert result["llm_raw_response"].startswith("The diff")

    def test_final_only_leaves_research_fields_none(self, handler):
        """VAL-3: sem JSON, as variáveis de pesquisa ficam None — não 'medium',
        não '', e justification não recebe mais a resposta bruta inteira."""
        result = handler._process_llm_response(
            "Brief analysis here.\nFINAL: FLOSS", "msg",
            commit_hash="c2", previous_hash="c1", repository="repo",
        )
        assert result["refactoring_type"] == "floss"
        assert result["extraction_method"] == "final_pattern"
        assert result["confidence_level"] is None
        assert result["technical_evidence"] is None
        assert result["justification"] is None
        assert result["llm_raw_response"] == "Brief analysis here.\nFINAL: FLOSS"

    def test_json_only_without_final_line(self, handler):
        result = handler._process_llm_response(
            '```json\n{"refactoring_type": "FLOSS", "justification": "adds null check"}\n```',
            "msg", commit_hash="c2",
        )
        assert result["refactoring_type"] == "floss"
        assert result["extraction_method"] == "json"
        assert result["justification"] == "adds null check"

    def test_final_conflicting_with_json_final_wins_and_flags(self, handler):
        result = handler._process_llm_response(
            'FINAL: FLOSS\n{"refactoring_type": "pure", "justification": "x"}',
            "msg", commit_hash="c2",
        )
        assert result["refactoring_type"] == "floss"
        assert result["final_vs_json_conflict"] is True
        assert result["extraction_method"] == "final_pattern+json"

    def test_prose_without_verdict_fails_and_logs(self, handler):
        """Regressão VAL-2: prosa rica em palavras-chave era transformada em
        rótulo pela heurística; agora é falha explícita e registrada."""
        prose = (
            "This commit shows pure refactoring with no functional changes, "
            "only structural improvements and identical behavior throughout."
        )
        result = handler._process_llm_response(
            prose, "msg", commit_hash="c2", repository="repo", prompt="PROMPT" * 100
        )
        assert result is None
        failures = _failures_logged(handler)
        assert len(failures) == 1
        assert "c2" in json.dumps(failures[0])

    def test_json_with_invalid_type_and_no_final_fails(self, handler):
        result = handler._process_llm_response(
            '{"refactoring_type": "unsure", "justification": "?"}',
            "msg", commit_hash="c2",
        )
        assert result is None
        assert len(_failures_logged(handler)) == 1

    def test_empty_response_fails_and_logs(self, handler):
        assert handler._process_llm_response("", "msg", commit_hash="c2") is None
        assert handler._process_llm_response("   \n", "msg", commit_hash="c2") is None
        assert len(_failures_logged(handler)) == 2

    def test_identifiers_filled_from_caller_metadata(self, handler):
        result = handler._process_llm_response(
            "FINAL: PURE", "msg",
            commit_hash="current123", previous_hash="before456", repository="my-repo",
        )
        assert result["commit_hash_current"] == "current123"
        assert result["commit_hash_before"] == "before456"
        assert result["repository"] == "my-repo"

    def test_empty_string_fields_normalized_to_none(self, handler):
        result = handler._process_llm_response(
            'FINAL: PURE\n{"refactoring_type": "pure", "justification": "  ", '
            '"confidence_level": "", "technical_evidence": "evidence"}',
            "msg", commit_hash="c2",
        )
        assert result["justification"] is None
        assert result["confidence_level"] is None
        assert result["technical_evidence"] == "evidence"


class TestAdapterFabricationGuard:
    """analysis_from_llm_response não degrada para 'floss' (VAL-8)."""

    @pytest.fixture
    def commit(self):
        return CommitPair(
            repository="repo", commit_hash_before="b1", commit_hash_current="c1"
        )

    def test_invalid_refactoring_type_raises(self, commit):
        with pytest.raises(ValueError, match="refactoring_type inválido"):
            analysis_from_llm_response({"refactoring_type": "maybe"}, commit)

    def test_missing_refactoring_type_raises(self, commit):
        with pytest.raises(ValueError):
            analysis_from_llm_response({"justification": "no verdict"}, commit)

    def test_uppercase_normalized(self, commit):
        result = analysis_from_llm_response({"refactoring_type": "PURE"}, commit)
        assert result.refactoring_type == "pure"

    def test_research_fields_default_none(self, commit):
        result = analysis_from_llm_response({"refactoring_type": "floss"}, commit)
        assert result.justification is None
        assert result.confidence_level is None
        assert result.technical_evidence is None

    def test_session_dict_carries_extraction_method_and_success(self, commit):
        result = analysis_from_llm_response(
            {"refactoring_type": "pure", "extraction_method": "final_pattern+json"},
            commit,
        )
        session = analysis_to_session_dict(result)
        assert session["extraction_method"] == "final_pattern+json"
        assert session["success"] is True
        assert session["llm_confidence"] is None
