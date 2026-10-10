import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from flask import Flask, jsonify, request, session
from collector import ai_provider, ai_usage, db

class UsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(db, 'DB_PATH', self.temp.name+'/usage.db'), patch.object(db, '_PG', False)]
        for p in self.patches: p.start()
        db.init_db()
        self.app=Flask(__name__);self.app.secret_key='test'
        fn=next(n for n in ast.parse(Path('app.py').read_text()).body if isinstance(n, ast.FunctionDef) and n.name=='admin_ai_usage')
        scope=dict(app=self.app,request=request,jsonify=jsonify,_admin_ok=lambda:bool(session.get('admin')),_ensure_db=lambda:True)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'app.py','exec'),scope)
        self.client=self.app.test_client()
        ai_provider._blocked_until=0
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def response(self, model='claude-haiku-4-5-20251001'):
        return Mock(status_code=200,json=lambda:{'model':model,'usage':{'input_tokens':1000,'output_tokens':200,'cache_creation_input_tokens':100,'cache_read_input_tokens':1000}})
    def test_provider_records_each_request_and_balance_survives_reload(self):
        ai_usage.set_balance('5.25')
        with patch.object(ai_provider.requests,'post',return_value=self.response()):
            for _ in range(2): ai_provider.post('https://api.anthropic.com/v1/messages',feature='요약',json={'model':'x','messages':[{'content':'SECRET PROMPT'}]})
        data=ai_usage.dashboard()
        self.assertEqual(data['totals']['requests'],2)
        self.assertEqual(data['rows'][0]['cost_micro'],2225)
        self.assertEqual(data['remaining_micro'],5245550)
        self.assertNotIn('SECRET',json.dumps(data))
        ai_usage.set_balance('10')
        self.assertEqual(ai_usage.dashboard()['remaining_micro'],10000000)
    def test_cache_hour_rate_unknown_model_and_missing_usage(self):
        usage={'input_tokens':0,'output_tokens':0,'cache_creation_input_tokens':1000,'cache_creation':{'ephemeral_1h_input_tokens':1000}}
        self.assertEqual(ai_usage.estimate('claude-haiku-4-5',usage,{}),2000)
        self.assertIsNone(ai_usage.estimate('unknown-model',usage,{}))
        self.assertIsNone(ai_usage.estimate('claude-haiku-4-5',{},{}))
        ai_usage.set_balance('5')
        ai_usage.record(self.response('unknown-model'),'요약',{},1)
        self.assertIsNone(ai_usage.dashboard()['remaining_micro'])
    def test_guest_and_normal_user_denied_and_admin_validation(self):
        for method in ('get','post'):
            self.assertEqual(getattr(self.client,method)('/api/admin/ai-usage').status_code,403)
        with self.client.session_transaction() as s:s['user']='tester1'
        self.assertEqual(self.client.get('/api/admin/ai-usage').status_code,403)
        with self.client.session_transaction() as s:s['admin']=True
        self.assertEqual(self.client.get('/api/admin/ai-usage').status_code,200)
        for amount in ('NaN','Infinity','-1','abc',None):
            self.assertEqual(self.client.post('/api/admin/ai-usage',json={'balance_usd':amount}).status_code,400)
        self.assertEqual(self.client.post('/api/admin/ai-usage',json={'balance_usd':'5.25'}).status_code,200)
        self.assertEqual(self.client.post('/api/admin/ai-usage',json={'balance_usd':'5.25'},headers={'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/admin/ai-usage',json=[]).status_code,400)
        self.assertEqual(self.client.get('/api/admin/ai-usage').headers['Cache-Control'],'no-store')
    def test_tracking_failure_does_not_break_ai(self):
        with patch.object(ai_usage.db,'get_conn',side_effect=RuntimeError('DB down')), patch.object(ai_provider.requests,'post',return_value=self.response()):
            self.assertEqual(ai_provider.post('url',feature='요약',json={}).status_code,200)

if __name__=='__main__':unittest.main()
