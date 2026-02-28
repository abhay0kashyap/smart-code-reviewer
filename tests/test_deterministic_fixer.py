import unittest

from analyzer.ai_fixer import deterministic_fix


class DeterministicFixerTests(unittest.TestCase):
    def test_fix_missing_quote(self):
        code = "print('hello)"
        execution = {
            "error_type": "SyntaxError",
            "error_line": 1,
            "error_message": "unterminated string literal",
            "traceback": "",
        }

        result = deterministic_fix(code, execution)
        self.assertTrue(result["fix_available"])
        self.assertEqual(result["fixed_code"], "print('hello')")

    def test_fix_semicolon_to_colon(self):
        code = "if x == 5 ;\n    print('ok')"
        execution = {
            "error_type": "SyntaxError",
            "error_line": 1,
            "error_message": "invalid syntax",
            "traceback": "",
        }

        result = deterministic_fix(code, execution)
        self.assertTrue(result["fix_available"])
        self.assertIn("if x == 5 :", result["fixed_code"])

    def test_fix_invalid_print_punctuation(self):
        code = "print(\"hi\",/)"
        execution = {
            "error_type": "SyntaxError",
            "error_line": 1,
            "error_message": "invalid syntax",
            "traceback": "",
        }

        result = deterministic_fix(code, execution)
        self.assertTrue(result["fix_available"])
        self.assertEqual(result["fixed_code"], "print(\"hi\")")

    def test_fix_zero_division_literal(self):
        code = "num = 10\nprint(num / 0)"
        execution = {
            "error_type": "ZeroDivisionError",
            "error_line": 2,
            "error_message": "division by zero",
            "traceback": "ZeroDivisionError: division by zero",
        }

        result = deterministic_fix(code, execution)
        self.assertTrue(result["fix_available"])
        self.assertEqual(result["fixed_code"], "num = 10\nprint(num / 1)")


if __name__ == "__main__":
    unittest.main()
