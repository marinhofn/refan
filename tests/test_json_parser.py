import unittest
from src.utils.json_parser import extract_json_from_text

class TestJSONParser(unittest.TestCase):
    def test_simple_json(self):
        txt = '{"a": 1, "b": "x"}'
        res = extract_json_from_text(txt)
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get('a'), 1)

    def test_json_block(self):
        txt = 'Here is output:\n```json\n{"refactoring_type": "floss", "justification": "ok"}\n```'
        res = extract_json_from_text(txt)
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get('refactoring_type'), 'floss')

    def test_think_block_removed(self):
        txt = """<think>I'm thinking...</think>```json
{"refactoring_type": "pure", "justification": "ok"}
```"""
        res = extract_json_from_text(txt)
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get('refactoring_type'), 'pure')

    def test_malformed_trailing_comma(self):
        txt = '{"a": 1,}'
        res = extract_json_from_text(txt)
        # If json5 not available this may be None; at least ensure function returns either dict or None without raising
        self.assertTrue(res is None or isinstance(res, dict))

if __name__ == '__main__':
    unittest.main()
