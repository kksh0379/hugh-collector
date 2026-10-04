import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from flask import Flask, jsonify, request, session
from collector.identity import canonical_user, display_name, public_author


class DisplayNamesTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'isolated-test-session'
        self.writes = []
        self.rows = [{'username': 'test1', 'comment': '기존 후기'}, {'username': 'tester1', 'comment': '별칭 후기'}, {'username': '관리자', 'comment': '기존 관리자 후기'}]
        db = SimpleNamespace(lunch_list_reviews=lambda rid: self.rows,
                             lunch_add_review=lambda *args: self.writes.append(args), lunch_add_visit=lambda *args: None)
        scope = dict(app=self.app, jsonify=jsonify, request=request, session=session,
                     canonical_user=canonical_user, display_name=display_name, public_author=public_author,
                     TEST_USERS={'test1': '1234'}, ADMIN_PW='test-admin-password', db=db,
                     _safe_list=lambda fn, **kw: jsonify(fn()), _ensure_db=lambda **kw: True,
                     _invalidate_lunch_cache=lambda: None)
        names = {'_admin_ok', '_current_user', '_cur_user', 'me', 'login', 'logout', 'lunch_reviews', 'lunch_review'}
        tree = ast.parse(Path('app.py').read_text())
        # Exercise the real route functions without starting unrelated collector jobs.
        module = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
        exec(compile(module, 'app.py', 'exec'), scope)
        self.client = self.app.test_client()

    def test_both_login_names_use_existing_identity_and_display_name(self):
        for username in ('test1', 'tester1', ' TESTER1 '):
            r = self.client.post('/api/login', json={'role':'user','username':username,'pw':'1234'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual((r.json['user'], r.json['display_name'], r.json['admin']), ('test1', '김테스터', False))
            self.assertEqual(self.client.get('/api/me').json['display_name'], '김테스터')
        self.assertEqual(self.client.post('/api/login', json={'role':'user','username':'tester1','pw':'wrong'}).status_code, 401)

    def test_old_reviews_show_name_without_mutating_stored_ids(self):
        r = self.client.get('/api/lunch/reviews?rid=1')
        self.assertEqual([row['display_name'] for row in r.json], ['김테스터','김테스터','관리자'])
        self.assertEqual([row['username'] for row in self.rows], ['test1','tester1','관리자'])
        self.assertTrue(all('display_name' not in row for row in self.rows))

    def test_new_reviews_keep_owner_id_and_ignore_supplied_author(self):
        self.client.post('/api/login', json={'role':'user','username':'tester1','pw':'1234'})
        r = self.client.post('/api/lunch/review', json={'rid':1,'rating':5,'comment':'후기','username':'admin','display_name':'위조 이름'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.writes, [(1,'test1',5,'후기')])

    def test_admin_logout_and_unauthenticated_review(self):
        self.client.post('/api/login', json={'role':'admin','pw':'test-admin-password'})
        self.assertEqual(self.client.get('/api/me').json['display_name'], '관리자')
        self.client.post('/api/logout')
        self.assertIsNone(self.client.get('/api/me').json['display_name'])
        self.assertEqual(self.client.post('/api/lunch/review', json={'rid':1,'rating':5}).status_code,401)


if __name__ == '__main__':
    unittest.main()
