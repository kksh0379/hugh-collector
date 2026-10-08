import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask, g, jsonify, request, session
from collector import accounts, db
from collector.identity import canonical_user

ROOT = Path(__file__).resolve().parents[1]

class AccountsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(db, 'DB_PATH', self.temp.name+'/accounts.db'), patch.object(db, '_PG', False), patch.object(accounts, '_ready', False)]
        for p in self.patches: p.start()
        with db.get_conn() as conn:
            conn.execute('CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)')
        self.app = Flask(__name__)
        self.app.secret_key = 'isolated-test-session'
        accounts.register(self.app, lambda **kw: True, lambda: bool(session.get('admin')))
        tree = ast.parse((ROOT/'app.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_validate_account_session')
        fn.decorator_list = []
        scope = dict(accounts=accounts, session=session, request=request, g=g, jsonify=jsonify,
                     _current_user=lambda: canonical_user(session.get('user')), _admin_ok=lambda: bool(session.get('admin')),
                     _ensure_db=lambda **kw: True)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'app.py','exec'),scope)
        self.app.before_request(scope['_validate_account_session'])
        @self.app.get('/api/who')
        def who(): return jsonify({'user':session.get('user')})
        self.client = self.app.test_client()
        with self.client.session_transaction() as s: s['admin']=True; s['user']='admin'

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()

    def create(self, username='alice'):
        return self.client.post('/api/admin/accounts',json={'username':username,'display_name':'앨리스','password':'test-password-123'})

    def test_ordinary_crud_and_hash_only_storage(self):
        self.assertEqual(self.create().status_code,201)
        rows=self.client.get('/api/admin/accounts').json['accounts']
        self.assertTrue(rows[0]['locked'])
        self.assertNotIn('password_hash',json.dumps(rows))
        row=accounts.authenticate('alice','test-password-123')
        self.assertIsNotNone(row)
        self.assertNotEqual(row['password_hash'],'test-password-123')
        self.assertEqual(self.client.patch('/api/admin/accounts/alice',json={'display_name':'수정 이름','password':''}).status_code,200)
        self.assertEqual(accounts.authenticate('alice','test-password-123')['display_name'],'수정 이름')
        self.assertEqual(self.client.delete('/api/admin/accounts/alice').status_code,200)
        self.assertIsNone(accounts.authenticate('alice','test-password-123'))
        self.assertEqual(self.create().status_code,409)

    def test_admin_is_locked_at_server_and_role_escalation_rejected(self):
        self.assertEqual(self.client.patch('/api/admin/accounts/admin',json={'display_name':'x'}).status_code,403)
        self.assertEqual(self.client.delete('/api/admin/accounts/admin').status_code,403)
        self.assertEqual(self.create('admin').status_code,400)
        self.assertEqual(self.client.post('/api/admin/accounts',json={'username':'alice','display_name':'x','password':'test-password-123','admin':True}).status_code,400)

    def test_unauthorized_and_cross_origin_writes_fail(self):
        self.assertEqual(self.client.post('/api/admin/accounts',json={},headers={'Origin':'https://other.example'}).status_code,403)
        with self.client.session_transaction() as s: s.clear()
        self.assertEqual(self.client.get('/api/admin/accounts').status_code,401)
        self.assertEqual(self.create().status_code,401)

    def test_legacy_seed_is_preserved_but_never_resurrected(self):
        self.assertEqual(accounts.authenticate('tester1','1234')['display_name'],'김테스터')
        self.assertEqual(self.client.delete('/api/admin/accounts/test1').status_code,200)
        accounts._ready=False
        accounts.init_store()
        self.assertIsNone(accounts.authenticate('tester1','1234'))

    def test_password_update_revokes_existing_session(self):
        self.create()
        row=accounts.get_account('alice')
        user=self.app.test_client()
        with user.session_transaction() as s: s['user']='alice';s['account_version']=row['version']
        self.assertEqual(user.get('/api/who').json['user'],'alice')
        self.client.patch('/api/admin/accounts/alice',json={'display_name':'앨리스','password':'new-password-456'})
        self.assertIsNone(user.get('/api/who').json['user'])
        self.assertIsNone(accounts.authenticate('alice','test-password-123'))
        self.assertIsNotNone(accounts.authenticate('alice','new-password-456'))

    def test_invalid_input_and_immutable_username(self):
        self.assertEqual(self.create('a').status_code,400)
        self.assertEqual(self.create('tester1').status_code,400)
        self.assertEqual(self.client.post('/api/admin/accounts',json=[]).status_code,400)
        self.create()
        self.assertEqual(self.client.patch('/api/admin/accounts/alice',json={'username':'bob','display_name':'x'}).status_code,400)

if __name__=='__main__': unittest.main()
