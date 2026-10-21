import ast
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError

from collector import mailer


class MailProviderErrors(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'RESEND_API_KEY': 're_TEST_SECRET', 'MAIL_FROM': 'onboarding@resend.dev',
            'MAIL_RECIPIENTS': 'recipient@example.org'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def failure(self, body, status=403):
        stream = io.BytesIO(body)
        exc = HTTPError('https://api.resend.com/emails', status, 'Forbidden', {}, stream)
        with patch.object(mailer.urllib.request, 'urlopen', side_effect=exc):
            with self.assertRaises(mailer.MailProviderError) as caught:
                mailer.send_test()
        self.assertTrue(stream.closed)
        return caught.exception

    def test_test_domain_restriction(self):
        error = self.failure(json.dumps({'name': 'validation_error', 'message':
            'You can only send testing emails to your own email address (private@example.com). '
            'Bearer re_TEST_SECRET <script>alert(1)</script>'}).encode())
        self.assertEqual(error.provider_code, 'validation_error')
        self.assertEqual(error.http_status, 403)
        self.assertIn('Resend 계정 이메일', str(error))
        for secret in ('private@example.com', 're_TEST_SECRET', '<script>', 'Bearer'):
            self.assertNotIn(secret, str(error))

    def test_domain_not_verified(self):
        e = self.failure(b'{"name":"validation_error","message":"The example.com domain is not verified. Please verify."}')
        self.assertIn('인증되지', str(e))

    def test_invalid_key(self):
        e = self.failure(b'{"name":"validation_error","message":"API key is invalid"}', 401)
        self.assertIn('유효하지', str(e))

    def test_key_permission_and_suspension(self):
        for code in ('restricted_api_key', 'invalid_permission', 'suspended_api_key'):
            with self.subTest(code=code):
                e = self.failure(json.dumps({'name': code, 'message': 'secret'}).encode())
                self.assertEqual(e.provider_code, code)
                self.assertNotIn('secret', str(e))

    def test_malformed_unknown_and_oversized_are_private(self):
        bodies = [b'not json re_TEST_SECRET', b'[]', b'null', b'{}',
                  b'{"name":["secret"],"message":{}}',
                  b'{"name":"re_TEST_SECRET","message":"private"}',
                  b'{"name":"validation_error","message":null}', b'x' * 9000]
        for body in bodies:
            with self.subTest(body=body[:30]):
                e = self.failure(body)
                self.assertNotIn('re_TEST_SECRET', str(e))
                self.assertNotIn('private', str(e))

    def test_success_preserves_configured_addresses(self):
        response = MagicMock()
        response.__enter__.return_value = io.StringIO('{"id":"email-123"}')
        with patch.object(mailer.urllib.request, 'urlopen', return_value=response) as send:
            result = mailer.send_test()
        self.assertTrue(result['accepted'])
        self.assertEqual(result['provider_id'], 'email-123')
        payload = json.loads(send.call_args.args[0].data)
        self.assertEqual(payload['to'], ['recipient@example.org'])
        self.assertEqual(payload['from'], 'onboarding@resend.dev')
        self.assertEqual(send.call_count, 1)

    def test_status_warns_without_credentials(self):
        state = mailer.status()
        self.assertTrue(state['test_sender'])
        self.assertNotIn('re_TEST_SECRET', json.dumps(state))

    def test_admin_endpoint_returns_and_logs_only_safe_error(self):
        # Execute the real handler without booting schedulers or databases.
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'app.py').read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'admin_mail_test')
        node.decorator_list = []
        fake_app = MagicMock()
        scope = {'mailer': mailer, 'app': fake_app, 'session': {'admin': True},
                 'request': MagicMock(headers={}, host_url='https://hscope.onrender.com/'),
                 'jsonify': lambda value: value}
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<handler>', 'exec'), scope)
        error = mailer.MailProviderError(403, 'validation_error', 'safe summary')
        with patch.object(mailer, 'send_test', side_effect=error):
            body, status = scope['admin_mail_test']()
        self.assertEqual(status, 502)
        self.assertEqual(body['provider_status'], 403)
        self.assertEqual(body['provider_code'], 'validation_error')
        fake_app.logger.warning.assert_called_once_with('Admin mail test failed: %s', error)
        scope['session'] = {}
        with patch.object(mailer, 'send_test') as send:
            self.assertEqual(scope['admin_mail_test']()[1], 403)
            send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
