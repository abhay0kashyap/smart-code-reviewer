import unittest

from app import app


class RunEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_run_returns_structured_error_response(self):
        response = self.client.post('/run', json={'code': 'print(hello)'})
        self.assertEqual(response.status_code, 200)

        body = response.get_json()
        self.assertIn('execution', body)
        self.assertIn('explanation', body)
        self.assertIsInstance(body['execution'], dict)
        self.assertIsInstance(body['explanation'], dict)

        execution = body['execution']
        self.assertFalse(execution['success'])
        self.assertEqual(execution['error_type'], 'NameError')
        self.assertEqual(execution['error_line'], 1)

    def test_ai_fix_returns_autofix_payload(self):
        response = self.client.post('/ai_fix', json={'code': 'print("hi",/)'})
        self.assertEqual(response.status_code, 200)

        body = response.get_json()
        self.assertIn('execution', body)
        self.assertIn('autofix', body)
        self.assertIsInstance(body['autofix'], dict)
        self.assertIn('fix_available', body['autofix'])
        self.assertIn('fixed_code', body['autofix'])


if __name__ == '__main__':
    unittest.main()
