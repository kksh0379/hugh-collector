import base64
import io
import json
import os
from email import policy
from email.parser import BytesParser
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from collector import mailer


class GmailMailerTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {
            'MAIL_PROVIDER': 'gmail', 'MAIL_FROM': 'kksh0378@gmail.com',
            'MAIL_RECIPIENTS': 'kksh0378@ncfoundation.or.kr',
            'GMAIL_CLIENT_ID': 'client-id', 'GMAIL_CLIENT_SECRET': 'secret-value',
            'GMAIL_REFRESH_TOKEN': 'refresh-secret'}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def test_refresh_then_send_with_exact_addresses(self):
        with patch.object(mailer.urllib.request, 'urlopen', side_effect=[
                io.StringIO('{"access_token":"access-secret"}'), io.StringIO('{"id":"message-1"}')]) as call:
            result = mailer.send_test()
        self.assertTrue(result['accepted'])
        self.assertEqual(result['provider_id'], 'message-1')
        token_req, send_req = [c.args[0] for c in call.call_args_list]
        self.assertEqual(token_req.full_url, 'https://oauth2.googleapis.com/token')
        self.assertIn(b'grant_type=refresh_token', token_req.data)
        self.assertIn('kksh0378%40gmail.com/messages/send', send_req.full_url)
        raw = base64.urlsafe_b64decode(json.loads(send_req.data)['raw'])
        message = BytesParser(policy=policy.default).parsebytes(raw)
        self.assertEqual(message['From'], 'kksh0378@gmail.com')
        self.assertEqual(message['To'], 'kksh0378@ncfoundation.or.kr')
        self.assertIn('휴스코프', message['Subject'])
        self.assertEqual(len(list(message.iter_parts())), 2)
        self.assertEqual(call.call_count, 2)

    def test_missing_credentials_do_not_send(self):
        del os.environ['GMAIL_REFRESH_TOKEN']
        with patch.object(mailer.urllib.request, 'urlopen') as call:
            with self.assertRaises(ValueError):
                mailer.send_test()
            call.assert_not_called()
        self.assertFalse(mailer.status()['configured'])

    def test_oauth_error_is_private_and_no_send(self):
        error = HTTPError('https://oauth2.googleapis.com/token', 400, 'bad', {}, io.BytesIO(b'secret-value refresh-secret'))
        with patch.object(mailer.urllib.request, 'urlopen', side_effect=error) as call:
            with self.assertRaises(mailer.MailProviderError) as caught:
                mailer.send_test()
        self.assertEqual(caught.exception.provider_code, 'gmail_oauth_error')
        self.assertNotIn('secret', str(caught.exception))
        self.assertEqual(call.call_count, 1)

    def test_send_error_is_private_and_not_retried(self):
        error = HTTPError('https://gmail.googleapis.com/', 403, 'bad', {}, io.BytesIO(b'access-secret'))
        with patch.object(mailer.urllib.request, 'urlopen', side_effect=[io.StringIO('{"access_token":"access-secret"}'), error]) as call:
            with self.assertRaises(mailer.MailProviderError) as caught:
                mailer.send_test()
        self.assertEqual(caught.exception.provider_code, 'gmail_send_error')
        self.assertNotIn('access-secret', str(caught.exception))
        self.assertEqual(call.call_count, 2)

    def test_bad_token_response_never_sends(self):
        for body in ('{}', '[]', 'secret-value'):
            with self.subTest(body=body):
                with patch.object(mailer.urllib.request, 'urlopen', return_value=io.StringIO(body)) as call:
                    with self.assertRaises(RuntimeError):
                        mailer.send_test()
                    self.assertEqual(call.call_count, 1)

    def test_status_and_invalid_recipient(self):
        state = mailer.status()
        self.assertEqual(state['provider'], 'gmail')
        self.assertTrue(state['configured'])
        self.assertNotIn('secret', json.dumps(state))
        os.environ['MAIL_RECIPIENTS'] = 'bad\naddress'
        with patch.object(mailer.urllib.request, 'urlopen') as call:
            with self.assertRaises(ValueError):
                mailer.send_test()
            call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
