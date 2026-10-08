import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from collector import db, healthchecks


class HealthCheckTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=patch.object(db,'DB_PATH',str(Path(self.folder.name)/'checks.sqlite'));self.path.start()
        db.init_db()
        self.app=Flask(__name__);self.app.secret_key='isolated-test-key'
        self.service=healthchecks.register(self.app,db,lambda **kwargs:True)
        self.client=self.app.test_client()
        self.thread=patch('collector.healthchecks.threading.Thread');self.thread.start()
    def tearDown(self):
        self.thread.stop();self.path.stop();self.folder.cleanup()
    def admin(self):
        with self.client.session_transaction() as state:state.update(admin=True,user='admin')
    def test_admin_access_and_no_public_execution(self):
        for path in ('/api/admin/healthchecks','/api/admin/healthchecks/run','/api/admin/healthchecks/cron'):
            response=self.client.get(path) if path.endswith('healthchecks') else self.client.post(path,json={})
            self.assertEqual(response.status_code,401)
        self.admin();response=self.client.post('/api/admin/healthchecks/run',json={})
        self.assertEqual(response.status_code,202)
        self.assertTrue(response.json['started'])
    def test_duplicate_manual_run_reuses_active_id(self):
        first,started=self.service.start();second,again=self.service.start()
        self.assertTrue(started);self.assertFalse(again);self.assertEqual(first,second)
        self.assertEqual(len(self.service.history()),1)
    def test_internal_admin_probe_uses_same_host_as_session_cookie(self):
        run_id,_=self.service.start()
        status,data=self.service.request('/api/admin/healthchecks?id='+run_id,admin=True)
        self.assertEqual(status,'passed')
        self.assertEqual(data['report']['id'],run_id)
        self.assertEqual(self.service.request('/api/admin/healthchecks')[0],'failed')
    def test_daily_idempotency_survives_service_restart(self):
        first,_=self.service.start('scheduled',daily=True)
        with db.get_conn() as conn:conn.execute('DELETE FROM healthcheck_lock')
        other=healthchecks.HealthChecks(self.app,db,lambda **kwargs:True)
        second,started=other.start('scheduled',daily=True)
        self.assertEqual(first,second);self.assertFalse(started)
    def test_durations_start_end_and_results_are_persisted(self):
        run_id,_=self.service.start()
        report=self.service.read(run_id)
        def slow():time.sleep(.006);return 'passed','OK'
        checks=[('test','normal',slow),('test','unverified',lambda:('skipped','not configured'))]
        with patch.object(self.service,'checks',return_value=checks),patch.object(self.service,'suite'):
            self.service.execute(report)
        saved=self.service.read(run_id)
        self.assertEqual(saved['status'],'warning')
        self.assertIsNotNone(saved['finished_at']);self.assertGreater(saved['duration_ms'],0)
        self.assertGreater(saved['results'][0]['duration_ms'],0)
        self.assertEqual(saved['counts'],{'passed':1,'warning':0,'failed':0,'skipped':1})
        self.assertEqual(self.service.history()[0]['duration_ms'],saved['duration_ms'])
        with db.get_conn() as conn:self.assertIsNone(conn.execute('SELECT * FROM healthcheck_lock').fetchone())
    def test_cross_origin_manual_request_is_rejected(self):
        self.admin()
        response=self.client.post('/api/admin/healthchecks/run',headers={'Origin':'https://other.example'},json={})
        self.assertEqual(response.status_code,403)
    def test_signed_cron_and_expired_signature(self):
        key=Ed25519PrivateKey.generate()
        public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
        body=b'{"action":"start"}'
        def headers(timestamp):return {'Content-Type':'application/json','X-Health-Timestamp':timestamp,
            'X-Health-Signature':key.sign(timestamp.encode()+b'\n'+body).hex()}
        with patch.object(healthchecks,'PUBLIC_KEY',public):
            self.assertEqual(self.client.post('/api/admin/healthchecks/cron',data=body,headers=headers(str(int(time.time())-600))).status_code,401)
            self.assertEqual(self.client.post('/api/admin/healthchecks/cron',data=body+b' ',headers=headers(str(int(time.time())))).status_code,401)
            response=self.client.post('/api/admin/healthchecks/cron',data=body,headers=headers(str(int(time.time()))))
            self.assertEqual(response.status_code,202)
    def test_interrupted_run_is_reported_after_expired_lease(self):
        run_id,_=self.service.start();report=self.service.read(run_id)
        from datetime import datetime,timedelta
        report['started_at']=(datetime.now(healthchecks.KST)-timedelta(minutes=40)).isoformat()
        self.service.save(report)
        self.assertEqual(self.service.read(run_id)['status'],'interrupted')
    def test_configured_false_and_empty_results_are_not_green(self):
        with patch.object(self.service,'request',return_value=('passed',{'mode':'unconfigured'})):
            self.assertEqual(self.service.json_check('/sample')[0],'skipped')
        with patch.object(self.service,'request',return_value=('passed',[])):
            self.assertEqual(self.service.json_check('/sample')[0],'warning')
    def test_child_environment_never_inherits_secrets(self):
        source=(Path(__file__).resolve().parents[1]/'collector/healthchecks.py').read_text()
        self.assertIn("('PATH','LANG','LC_ALL','PYTHONPATH','PYTHONHOME')",source)
        self.assertNotIn('env=os.environ.copy()',source)


if __name__=='__main__':unittest.main()
