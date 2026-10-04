import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ['ENABLE_SCHEDULER'] = '0'
os.environ['AUTO_BACKFILL'] = '0'
os.environ['ENABLE_DB_PREWARM'] = '0'
os.environ['DB_KEEPALIVE_SEC'] = '0'
from collector import db, lunch
import app as web

class NearbyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = patch.object(db, 'DB_PATH', str(Path(self.tmp.name) / 'db.sqlite'))
        self.path.start()
        db.init_db()
        self.ready = patch.object(web, '_db_ready', True)
        self.ready.start()
        db.lunch_seed_locations([{'name': '기존 지역'}])
        self.old = {'place_id': 'same', 'name': '저장한 이름', 'source': 'kakao', 'lat': 37.58, 'lng': 127.0, 'phone': 'original', 'road_address':'서울 원래 주소'}
        db.lunch_upsert_restaurants(1, [self.old])
        self.rid = db.lunch_list_restaurants(1)[0]['id']
        with db.get_conn() as c:
            c.execute('INSERT INTO lunch_review (restaurant_id,username,rating,comment) VALUES (?,?,?,?)',(self.rid,'사용자',5,'기존 리뷰'))
            c.execute('INSERT INTO lunch_visit (restaurant_id,username,visited_at) VALUES (?,?,?)',(self.rid,'사용자','2026-10-04'))
        self.client = web.app.test_client()
        web._GPS_JOBS.clear()
    def tearDown(self):
        self.ready.stop(); self.path.stop(); self.tmp.cleanup()
    def test_download_reuses_existing_without_touching_any_fields(self):
        before = db.lunch_get_restaurant(self.rid)
        new, reused = db.lunch_save_nearby(37.58,127,600,[dict(self.old,name='외부 새 이름',phone=''),dict(self.old,place_id='new',name='신규 식당')])
        self.assertEqual((new,reused),(1,1))
        self.assertEqual(db.lunch_get_restaurant(self.rid),before)
        rows, covered = db.lunch_nearby_restaurants(37.58,127,500)
        self.assertTrue(covered)
        saved = next(r for r in rows if r['id']==self.rid)
        self.assertEqual((saved['review_count'],saved['avg_rating'],saved['visit_count']),(1,5,1))
        self.assertEqual(db.lunch_save_nearby(37.58,127,600,[self.old,dict(self.old,place_id='new')]),(0,2))
        self.assertEqual(len(db.lunch_nearby_restaurants(37.58,127,500)[0]),2)
    def test_manual_match_requires_address_and_coordinates(self):
        db.lunch_upsert_restaurants(1,[dict(self.old,source='manual',place_id='manual:수동',name='수동 식당')])
        item = dict(self.old,place_id='provider',name='수동 식당')
        self.assertEqual(db.lunch_save_nearby(37.58,127,600,[item]),(0,1))
        self.assertEqual(db.lunch_save_nearby(37.58,127,600,[dict(item,place_id='other',road_address='다른 주소')]),(1,0))
    def test_excluded_and_outside_radius_stay_hidden(self):
        db.lunch_set_excluded(self.rid,True)
        self.assertEqual(db.lunch_nearby_restaurants(37.58,127,500)[0],[])
        self.assertEqual(len(db.lunch_nearby_restaurants(37.58,127,500,True)[0]),1)
        self.assertEqual(db.lunch_nearby_restaurants(37.6,127,500,True)[0],[])
        self.assertEqual(db.lunch_save_nearby(37.58,127,600,[self.old]),(0,1))
        self.assertTrue(db.lunch_get_restaurant(self.rid)['excluded'])
    def test_read_never_downloads_and_confirmation_is_required(self):
        with patch.object(lunch,'collect') as collect:
            data = self.client.post('/api/lunch/nearby',json={'lat':37.58,'lng':127}).get_json()
            self.assertTrue(data['download_needed'])
            self.assertEqual(data['restaurants'][0]['id'],self.rid)
            self.assertEqual(self.client.post('/api/lunch/nearby/download',json={'lat':37.58,'lng':127}).status_code,400)
            collect.assert_not_called()
    def test_invalid_coordinates_do_not_reach_database(self):
        for lat,lng,radius in [('NaN',127,500),(999,127,500),(37.58,127,-1),(37.58,127,'NaN')]:
            self.assertEqual(self.client.post('/api/lunch/nearby',json={'lat':lat,'lng':lng,'radius':radius}).status_code,400)
    def test_worker_failure_does_not_save_coverage_or_change_existing(self):
        before=db.lunch_get_restaurant(self.rid)
        web._GPS_JOBS['test']={'running':True}
        with patch.object(lunch,'collect',side_effect=RuntimeError('upstream unavailable')):
            web._lunch_gps_run('test',{'lat':37.58,'lng':127,'radius':500})
        self.assertFalse(web._GPS_JOBS['test']['result']['ok'])
        self.assertFalse(db.lunch_download_covered(37.58,127,500))
        self.assertEqual(db.lunch_get_restaurant(self.rid),before)
    def test_worker_success_and_session_scoped_status(self):
        web._GPS_JOBS['test']={'running':True,'owner':'owner','progress':'','result':None}
        with patch.object(lunch,'collect',return_value=[self.old]):
            web._lunch_gps_run('test',{'lat':37.58,'lng':127,'radius':500})
        self.assertEqual(web._GPS_JOBS['test']['result'],{'ok':True,'new':0,'existing':1})
        self.assertEqual(self.client.get('/api/lunch/nearby/download/status?job_id=test').status_code,404)
        with self.client.session_transaction() as s: s['lunch_download_owner']='owner'
        self.assertEqual(self.client.get('/api/lunch/nearby/download/status?job_id=test').status_code,200)
    def test_coverage_handles_gps_jitter_but_not_larger_radius(self):
        db.lunch_save_nearby(37.58,127,600,[])
        self.assertTrue(db.lunch_download_covered(37.5801,127,500))
        self.assertFalse(db.lunch_download_covered(37.58,127,1000))
        self.assertFalse(db.lunch_download_covered(37.6,127,500))
    def test_gps_recommendation_keeps_original_id(self):
        result=self.client.post('/api/lunch/recommend',json={'loc_id':'gps','lat':37.58,'lng':127,'candidate_ids':[self.rid]}).get_json()
        self.assertTrue(result['ok']); self.assertEqual(result['pick']['id'],self.rid)
    def test_strict_collection_rejects_upstream_errors(self):
        from types import SimpleNamespace
        with patch.object(lunch,'has_key',return_value=True),patch.object(lunch.fetcher,'get',return_value=SimpleNamespace(status_code=429)):
            with self.assertRaises(RuntimeError): lunch.collect(37.58,127,500,strict=True)

if __name__=='__main__': unittest.main()
