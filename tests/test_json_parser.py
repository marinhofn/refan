"""Testes unitários para src/utils/json_parser.py.

Convertido de unittest.TestCase para pytest puro.
Refs: REFACTORING_PLAN.md Fase 0.5
"""

from src.utils.json_parser import extract_json_from_text


def test_simple_json():
    result = extract_json_from_text('{"a": 1, "b": "x"}')
    assert isinstance(result, dict)
    assert result["a"] == 1


def test_json_block():
    txt = 'Here is output:\n```json\n{"refactoring_type": "floss", "justification": "ok"}\n```'
    result = extract_json_from_text(txt)
    assert isinstance(result, dict)
    assert result["refactoring_type"] == "floss"


def test_think_block_removed():
    txt = (
        "<think>I'm thinking...</think>"
        '```json\n{"refactoring_type": "pure", "justification": "ok"}\n```'
    )
    result = extract_json_from_text(txt)
    assert isinstance(result, dict)
    assert result["refactoring_type"] == "pure"


def test_malformed_trailing_comma():
    txt = '{"a": 1,}'
    result = extract_json_from_text(txt)
    # json5 ou reparo de trailing comma pode retornar dict; sem json5, None
    assert result is None or isinstance(result, dict)
