import os
import unittest

from fastapi.testclient import TestClient

from app import app


class RunEndpointTests(unittest.TestCase):
    def setUp(self):
        # Remove API keys to use deterministic fallback
        self.previous_key = os.environ.pop("OPENAI_API_KEY", None)
        self.previous_alias = os.environ.pop("OPENAI_KEY", None)
        self.client = TestClient(app)

    def tearDown(self):
        # Restore API keys
        if self.previous_key is not None:
            os.environ["OPENAI_API_KEY"] = self.previous_key
        if self.previous_alias is not None:
            os.environ["OPENAI_KEY"] = self.previous_alias

    def test_run_returns_structured_error_response(self):
        response = self.client.post('/run', json={'code': 'print(hello)'})
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertIn('execution', body)
        self.assertIn('explanation', body)
        self.assertIsInstance(body['execution'], dict)
        self.assertIsInstance(body['explanation'], dict)

        execution = body['execution']
        self.assertFalse(execution['success'])
        self.assertEqual(execution['error_type'], 'NameError')
        self.assertEqual(execution['error_line'], 1)

    def test_ai_fix_returns_autofix_payload(self):
        response = self.client.post(
            "/ai-fix",
            json={
                "code": 'num = 10\nprint(num / 0)',
                "error_type": "ZeroDivisionError",
                "error_message": "division by zero",
                "error_line": 2,
                "traceback": "ZeroDivisionError: division by zero (<string>, line 2)",
            },
        )
        self.assertEqual(response.status_code, 200)

        body = response.json()
        # The endpoint returns success, fixed_code, error
        self.assertIn("success", body)
        self.assertIn("fixed_code", body)
        self.assertIn("error", body)
        # With no API key, it should use deterministic fallback
        self.assertTrue(body["success"])
        self.assertEqual(body["fixed_code"], "num = 10\nprint(num / 1)")


if __name__ == '__main__':
    unittest.main()
