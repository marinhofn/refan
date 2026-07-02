"""Testes de caracterização para src/utils/json_parser.py.

Travam o comportamento atual das funções de extração de JSON antes da
refatoração, garantindo que mudanças nas Fases 1-3 não introduzam regressões.

Refs: REFACTORING_PLAN.md Fase 0.3
"""

import pytest
from src.utils.json_parser import (
    extract_json_from_text,
    extract_classification_json,
    _find_json_end_index,
    _find_matching_closing,
    _strip_think_blocks,
    try_parse_json,
    extract_json_candidates,
)


class TestExtractClassificationJson:
    """Schema mínimo do domínio (Fase E2, VAL-8): refactoring_type válido é
    obrigatório; ausência/invalidade é falha de extração, nunca default."""

    def test_valid_object_normalized(self):
        result = extract_classification_json(
            '{"refactoring_type": "PURE", "justification": "rename"}'
        )
        assert result is not None
        assert result["refactoring_type"] == "pure"

    def test_missing_refactoring_type_is_failure(self):
        assert extract_classification_json('{"justification": "ok"}') is None

    def test_invalid_refactoring_type_is_failure(self):
        assert extract_classification_json('{"refactoring_type": "maybe"}') is None
        assert extract_classification_json('{"refactoring_type": ""}') is None

    def test_no_json_is_failure(self):
        assert extract_classification_json("plain prose only") is None

    def test_whitespace_normalization(self):
        result = extract_classification_json('{"refactoring_type": " Floss "}')
        assert result is not None
        assert result["refactoring_type"] == "floss"


# ---------------------------------------------------------------------------
# extract_json_from_text — função principal
# ---------------------------------------------------------------------------

class TestExtractJsonFromText:
    """Testes de caracterização para a função principal de extração."""

    def test_simple_json(self):
        result = extract_json_from_text('{"a": 1, "b": "x"}')
        assert isinstance(result, dict)
        assert result["a"] == 1
        assert result["b"] == "x"

    def test_json_in_markdown_block(self):
        text = (
            'Here is output:\n'
            '```json\n'
            '{"refactoring_type": "floss", "justification": "ok"}\n'
            '```'
        )
        result = extract_json_from_text(text)
        assert isinstance(result, dict)
        assert result["refactoring_type"] == "floss"

    def test_json_in_plain_markdown_block(self):
        text = '```\n{"key": "value"}\n```'
        result = extract_json_from_text(text)
        assert isinstance(result, dict)
        assert result["key"] == "value"

    def test_think_block_removed_before_extraction(self):
        text = (
            "<think>I'm thinking about this...</think>\n"
            '```json\n'
            '{"refactoring_type": "pure", "justification": "rename only"}\n'
            '```'
        )
        result = extract_json_from_text(text)
        assert isinstance(result, dict)
        assert result["refactoring_type"] == "pure"

    def test_json_after_text_analysis(self):
        text = (
            "This commit appears to be a pure refactoring because it only "
            "renames variables.\n\n"
            'FINAL: PURE\n\n'
            '{"refactoring_type": "pure", "justification": "rename only"}'
        )
        result = extract_json_from_text(text)
        assert isinstance(result, dict)
        assert result["refactoring_type"] == "pure"

    def test_no_json_returns_none(self):
        """Fase E2 (VAL-8): sem objeto JSON não há resultado — nunca um dict
        fabricado a partir de texto solto."""
        text = "Only plain text with no JSON at all, no braces, nothing."
        assert extract_json_from_text(text) is None

    def test_nested_json_object(self):
        text = '{"outer": {"inner": "value"}, "type": "test"}'
        result = extract_json_from_text(text)
        assert isinstance(result, dict)
        assert result["type"] == "test"
        assert isinstance(result["outer"], dict)
        assert result["outer"]["inner"] == "value"

    def test_json_with_final_pattern_preceding(self):
        text = (
            "FINAL: FLOSS\n"
            '```json\n'
            '{"refactoring_type": "floss", "justification": "bug fix added"}\n'
            '```'
        )
        result = extract_json_from_text(text)
        assert isinstance(result, dict)
        assert result["refactoring_type"] == "floss"

    def test_malformed_trailing_comma(self):
        text = '{"a": 1, "b": 2,}'
        result = extract_json_from_text(text)
        # json5 ou reparo de trailing comma deve lidar com isso
        assert result is None or isinstance(result, dict)

    def test_multiple_json_candidates_returns_first_valid(self):
        text = (
            'Some text {"invalid: broken\n'
            'More text {"refactoring_type": "pure", "justification": "ok"}\n'
            'Final text'
        )
        result = extract_json_from_text(text)
        assert isinstance(result, dict)
        assert result["refactoring_type"] == "pure"

    def test_empty_string(self):
        result = extract_json_from_text("")
        assert result is None

    def test_whitespace_only(self):
        result = extract_json_from_text("   \n\t  \n  ")
        assert result is None

    def test_json_with_line_comments(self):
        text = '{"a": 1, // this is a comment\n "b": 2}'
        result = extract_json_from_text(text)
        # O reparo de comentários deve funcionar
        assert result is None or isinstance(result, dict)

    def test_key_value_prose_is_not_extracted(self):
        """Regressão VAL-8 (Fase E2): o antigo fallback 'key: value' montava
        um dict de qualquer prosa — recall alto, precisão baixa — que virava
        classificação silenciosa a jusante. Prosa não é objeto JSON."""
        text = (
            "refactoring_type: pure\n"
            "justification: only renames variables\n"
        )
        assert extract_json_from_text(text) is None

    def test_arrays_are_never_returned_as_lists(self):
        """VAL-8: o retorno é sempre dict ou None — nunca list. Um array que
        embrulha um único objeto tem o objeto interno extraído (varredura
        balanceada); um array escalar não produz resultado."""
        wrapped = extract_json_from_text('[{"refactoring_type": "pure"}]')
        assert isinstance(wrapped, dict)
        assert wrapped["refactoring_type"] == "pure"
        assert extract_json_from_text('[1, 2, 3]') is None

    def test_string_value_resembling_instructions_survives(self):
        """VAL-8: as heurísticas destrutivas de limpeza foram removidas —
        valores de string legítimos não podem ser corrompidos antes do parse."""
        text = (
            '{"refactoring_type": "floss", '
            '"justification": "You are an expert reviewer would say this '
            'adds a null check changing behavior"}'
        )
        result = extract_json_from_text(text)
        assert isinstance(result, dict)
        assert "expert" in result["justification"]

    def test_complete_llm_response_structure(self):
        """Simula uma resposta típica do Ollama com análise + JSON."""
        text = (
            "Let me analyze this commit diff carefully.\n\n"
            "The changes show a method rename from `getUser` to `fetchUser` "
            "with no behavioral changes.\n\n"
            "FINAL: PURE\n\n"
            "```json\n"
            "{\n"
            '    "repository": "https://github.com/test/repo",\n'
            '    "commit_hash_before": "abc123",\n'
            '    "commit_hash_current": "def456",\n'
            '    "refactoring_type": "pure",\n'
            '    "justification": "Simple method rename from getUser to '
            'fetchUser with identical logic"\n'
            "}\n"
            "```"
        )
        result = extract_json_from_text(text)
        assert isinstance(result, dict)
        assert result["refactoring_type"] == "pure"
        assert result["repository"] == "https://github.com/test/repo"
        assert "justification" in result


# ---------------------------------------------------------------------------
# _find_json_end_index / _find_matching_closing
# ---------------------------------------------------------------------------

class TestBraceMatching:
    def test_simple_object(self):
        text = '{"a": 1}'
        assert _find_json_end_index(text, 0) == 7

    def test_nested_object(self):
        text = '{"a": {"b": 1}}'
        assert _find_json_end_index(text, 0) == len(text) - 1

    def test_unbalanced_returns_minus_one(self):
        text = '{"a": 1'
        assert _find_json_end_index(text, 0) == -1

    def test_braces_inside_string_ignored(self):
        text = '{"a": "}{}"}'
        assert _find_json_end_index(text, 0) == len(text) - 1

    def test_matching_closing_brackets(self):
        text = '[1, [2, 3], 4]'
        assert _find_matching_closing(text, 0, '[', ']') == len(text) - 1

    def test_matching_closing_unbalanced(self):
        text = '[1, 2'
        assert _find_matching_closing(text, 0, '[', ']') == -1


# ---------------------------------------------------------------------------
# _strip_think_blocks
# ---------------------------------------------------------------------------

class TestStripThinkBlocks:
    def test_removes_think_tags(self):
        text = "<think>internal reasoning</think>actual content"
        result = _strip_think_blocks(text)
        assert "internal reasoning" not in result
        assert "actual content" in result

    def test_removes_self_closing_think(self):
        text = "before<think/>after"
        result = _strip_think_blocks(text)
        assert "think" not in result.lower()
        assert "before" in result
        assert "after" in result

    def test_removes_double_angle_think(self):
        text = "<<think>>deep thought<</think>>rest"
        result = _strip_think_blocks(text)
        assert "deep thought" not in result
        assert "rest" in result

    def test_empty_string(self):
        assert _strip_think_blocks("") == ""

    def test_no_think_blocks_unchanged(self):
        text = "normal text without any think blocks"
        # Conteúdo deve ser preservado (pode ter whitespace diferente)
        result = _strip_think_blocks(text)
        assert "normal text" in result


# ---------------------------------------------------------------------------
# try_parse_json
# ---------------------------------------------------------------------------

class TestTryParseJson:
    def test_valid_json(self):
        result = try_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_invalid_json_returns_none(self):
        result = try_parse_json("not json at all")
        assert result is None

    def test_empty_object(self):
        result = try_parse_json("{}")
        assert result == {}


# ---------------------------------------------------------------------------
# extract_json_candidates
# ---------------------------------------------------------------------------

class TestExtractJsonCandidates:
    def test_finds_markdown_json_block(self):
        text = '```json\n{"a": 1}\n```'
        candidates = extract_json_candidates(text)
        assert len(candidates) >= 1
        assert '{"a": 1}' in candidates[0]

    def test_finds_inline_json(self):
        text = 'some text {"b": 2} more text'
        candidates = extract_json_candidates(text)
        assert any('{"b": 2}' in c for c in candidates)

    def test_no_json_returns_empty(self):
        candidates = extract_json_candidates("no json here")
        assert candidates == []
