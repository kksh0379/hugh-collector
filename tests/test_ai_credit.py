import ast
import json
import os
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from collector import ai_provider, analysis, reader_summary, event_curation, security_ai, security_report


class CreditTests(unittest.TestCase):
    def setUp(self):
        ai_provider._state.clear()
        ai_provider._blocked_until = 0
        reader_summary._jobs.clear()

    def tearDown(self):
        ai_provider._state.clear()
        ai_provider._blocked_until = 0

    def response(self, status=400, text='Your credit balance is too low'):
        return Mock(status_code=status, text=text)

    def test_shared_credit_failure_donation_and_cooldown(self):
        with patch.object(ai_provider.requests, 'post', return_value=self.response()) as call:
            for feature in ('AI 핵심 요약', '보안뉴스 자동 분석'):
                with self.assertRaises(ai_provider.CreditUnavailable):
                    ai_provider.post(analysis.API_URL, feature=feature)
            self.assertEqual(call.call_count, 1)
        state = ai_provider.status()
        self.assertEqual(state['reason'], 'credit_balance')
        self.assertIn('기부해 주시면 AI 크레딧을 충전', state['notice'])
        self.assertIn('새마을금고 9003-3068-2476-1', state['notice'])
        self.assertIn('예금주: 김상화', state['notice'])
        self.assertNotIn('api-key', json.dumps(state))

    def test_complete_error_is_classified_before_truncation(self):
        with patch.object(ai_provider.requests, 'post', return_value=self.response(text='x'*500+' credit balance is too low')):
            with self.assertRaises(ai_provider.CreditUnavailable):
                ai_provider.post(analysis.API_URL, feature='리포트')

    def test_rate_limit_auth_and_output_limit_are_not_credit_failure(self):
        for status, text in [(429, 'rate_limit_error'), (401, 'authentication_error'), (400, 'max_tokens exceeds limit')]:
            response = self.response(status, text)
            with patch.object(ai_provider.requests, 'post', return_value=response):
                self.assertIs(ai_provider.post(analysis.API_URL, feature='리포트'), response)
            self.assertFalse(ai_provider.status())

    def test_success_after_recharge_clears_notice(self):
        ai_provider._state.update(reason='credit_balance', notice=ai_provider.NOTICE)
        with patch.object(ai_provider.requests, 'post', return_value=self.response(200, 'ok')):
            ai_provider.post(analysis.API_URL, feature='AI 핵심 요약')
        self.assertEqual(ai_provider.status(), {})

    def test_reader_shows_credit_notice_instead_of_connection_failure(self):
        article = {'mode':'article', 'title':'sample', 'paragraphs':['한글 기사 본문입니다. '*30]}
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY':'test'}), patch.object(reader_summary, '_generate', side_effect=ai_provider.CreditUnavailable()):
            reader_summary.article_summary(article)
            for _ in range(100):
                result = reader_summary.article_summary(article)
                if result['status'] != 'pending':
                    break
                threading.Event().wait(.01)
        self.assertEqual(result['ai_error'], 'credit_balance')
        self.assertIn('9003-3068-2476-1', result['notice'])
        self.assertEqual(result['notice'].splitlines(), ['AI 크레딧이 부족해요.', '기부해 주시면 AI 크레딧을 충전할게요.', '새마을금고 9003-3068-2476-1', '예금주: 김상화'])
        self.assertEqual(result['body_notice'], '본문은 아래에서 읽을 수 있어요.')

    def test_reports_and_security_use_same_credit_message(self):
        with patch.object(ai_provider.requests, 'post', return_value=self.response()):
            result = analysis._attempt('test', 'test-model', 'input')
            self.assertEqual(analysis.friendly_llm_error(result['err']), ai_provider.NOTICE)
            _, error = security_ai._call_batch('test', 'test-model', [])
            self.assertEqual(analysis.friendly_llm_error(error), ai_provider.NOTICE)
            _, _, error = security_report._call_llm('test', 'test-model', {'month':'2026-09','stats':{'total':0,'by_category':{},'by_importance':{},'cve_mentions':0},'articles':[]})
            self.assertEqual(analysis.friendly_llm_error(error), ai_provider.NOTICE)

    def test_all_token_calls_use_common_handler(self):
        for name in ('analysis', 'reader_summary', 'event_curation', 'security_ai', 'security_report'):
            tree = ast.parse(Path('collector/'+name+'.py').read_text())
            posts = [ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'post']
            self.assertTrue(posts, name)
            self.assertEqual(set(posts), {'ai_provider.post'}, name)


if __name__ == '__main__':
    unittest.main()
