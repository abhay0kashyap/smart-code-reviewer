import os
import unittest

from fastapi.testclient import TestClient

from app import app


class AIFixEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.previous_key = os.environ.pop("OPENAI_API_KEY", None)
        self.previous_alias = os.environ.pop("OPENAI_KEY", None)

    def tearDown(self):
        if self.previous_key is not None:
            os.environ["OPENAI_API_KEY"] = self.previous_key
        if self.previous_alias is not None:
            os.environ["OPENAI_KEY"] = self.previous_alias

    def test_ai_fix_uses_deterministic_fallback_for_zero_division(self):
        response = self.client.post(
            "/ai-fix",
            json={
                "code": "num = 10\nprint(num / 0)",
                "error_type": "ZeroDivisionError",
                "error_message": "division by zero",
                "error_line": 2,
                "traceback": "ZeroDivisionError: division by zero",
            },
        )
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["fixed_code"], "num = 10\nprint(num / 1)")
        self.assertEqual(body.get("source"), "deterministic")


if __name__ == "__main__":
    unittest.main()

