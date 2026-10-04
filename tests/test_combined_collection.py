import ast
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from collector import db, google_news, boards, social
from collector.collection_result import CollectionItems

APP = ast.parse((Path(__file__).resolve().parents[1] / 'app.py').read_text())
def function(name, scope):
    node=next(n for n in APP.body if isinstance(n, ast.FunctionDef) and n.name==name)
    node=copy.deepcopy(node);node.decorator_list=[]
    exec(compile(ast.Module(body=[node],type_ignores=[]),'app.py','exec'),scope)
    return scope[name]

class FeedTests(unittest.TestCase):
    def test_html_error_is_not_empty_rss(self):
        with patch.object(google_news.fetcher,'get',return_value=SimpleNamespace(content=b'<html>unavailable</html>')):
            with self.assertRaises(RuntimeError): google_news._collect_items('query')

    def test_all_rss_failures_raise_instead_of_zero_success(self):
        with patch.object(google_news,'_date_windows',return_value=[('a','b')]), patch.object(google_news,'_collect_items',side_effect=RuntimeError('503')):
            with self.assertRaisesRegex(RuntimeError,'RSS'): google_news.crawl(categories={'test':['query']})

    def test_partly_failed_boards_are_marked_incomplete(self):
        with patch.object(boards,'SOURCES',[{'service':'a','category':'x'},{'service':'b','category':'x'}]), patch.object(boards,'crawl_source',side_effect=[[{'url':'a'}],[]]):
            result=boards.crawl_all()
            self.assertFalse(result.complete);self.assertEqual(len(result),1)

    def test_empty_video_source_is_not_complete(self):
        with patch.object(social,'SOURCES',[{'account':'a'}]), patch.object(social,'crawl_source',return_value=[]), patch.dict(social.os.environ,{'YOUTUBE_API_KEY':''}):
            self.assertFalse(social.crawl_all().complete)

class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=patch.object(db,'DB_PATH',self.tmp.name+'/db.sqlite');self.path.start()
        self.pg=patch.object(db,'_PG',False);self.pg.start();db.init_db()
        db.upsert_news_many([{'url':'same','title':'old','section':'biz','image_url':'https://paper/photo.jpg','source_url':'https://paper/story'}, {'url':'remove','title':'old2','section':'biz'}, {'url':'other','section':'cat'}])
    def tearDown(self): self.path.stop();self.pg.stop();self.tmp.cleanup()
    def test_atomic_rebuild_preserves_media_and_other_section(self):
        db.upsert_news_many([{'url':'same','title':'new','section':'biz','image_url':None}],replace_section='biz')
        with db.get_conn() as c:
            rows={r['url']:dict(r) for r in c.execute('SELECT * FROM news')}
        self.assertEqual(set(rows),{'same','other'});self.assertEqual(rows['same']['image_url'],'https://paper/photo.jpg');self.assertEqual(rows['same']['source_url'],'https://paper/story')
    def test_failed_insert_rolls_back_deletion(self):
        with db.get_conn() as c: c.execute("CREATE TRIGGER fail_news BEFORE INSERT ON news WHEN NEW.title='reject' BEGIN SELECT RAISE(ABORT,'reject'); END")
        with self.assertRaises(Exception): db.upsert_news_many([{'url':'bad','title':'reject','section':'biz'}],replace_section='biz')
        with db.get_conn() as c: self.assertEqual(c.execute("SELECT COUNT(*) n FROM news WHERE section='biz'").fetchone()['n'],2)
    def test_normal_recollection_does_not_erase_existing_image(self):
        db.upsert_news_many([{'url':'same','section':'biz','image_url':''}])
        with db.get_conn() as c: self.assertEqual(c.execute("SELECT image_url FROM news WHERE url='same'").fetchone()['image_url'],'https://paper/photo.jpg')
    def test_empty_rebuild_does_not_delete(self):
        db.upsert_news_many([],replace_section='biz')
        with db.get_conn() as c: self.assertEqual(c.execute("SELECT COUNT(*) n FROM news WHERE section='biz'").fetchone()['n'],2)

class ControllerTests(unittest.TestCase):
    def purge(self,scope,busy=False):
        starts=[]
        ctx={'_admin_ok':lambda:True,'_ensure_db':lambda **kwargs:True,'request':SimpleNamespace(get_json=lambda **kw:{'scope':scope,'recollect':True,'days':30}), 'jsonify':lambda x:x, '_CRAWLERS':{k:None for k in ['cat','game','news','biz','security','event','boards','social']},'_JOBS':{'biz':{'running':True}} if busy else {}, '_start_job':lambda group,**kw:starts.append((group,kw)) or True, 'db':SimpleNamespace(clear_news_section=lambda *args:(_ for _ in ()).throw(AssertionError('premature deletion')))}
        return function('admin_purge',ctx)(),starts
    def test_merged_reset_targets_all_three_without_deleting_first(self):
        result,starts=self.purge('biz-all');self.assertTrue(result['staged']);self.assertEqual([g for g,k in starts],['biz','boards','social']);self.assertTrue(all(k['replace'] for g,k in starts))
    def test_individual_reset_only_targets_selected_source(self):
        for source in ['biz','boards','social']:
            result,starts=self.purge(source);self.assertEqual([g for g,k in starts],[source])
    def test_reset_during_running_collection_rejected_without_deletion(self):
        result,starts=self.purge('biz-all',True);self.assertEqual(result[1],409);self.assertEqual(starts,[])
    def crawl(self,items,replace=True):
        saved=[]
        ctx={'_CRAWLERS':{'biz':(lambda **kwargs:items,lambda data,**kwargs:saved.append(kwargs) or {'new':len(data),'updated':0})},'_ensure_db':lambda **kw:True,'_purge_biz_nc':lambda *args:None,'_enrich_news_images':lambda *args,**kw:None,'_invalidate_read_cache':lambda:None,'_now_kst':lambda:'now','_last_result':{},'db':SimpleNamespace(set_meta=lambda *args:None,add_run_log=lambda *args:None)}
        return function('_do_crawl',ctx)('biz',replace=replace),saved
    def test_zero_rebuild_is_failure_and_never_saves(self):
        result,saved=self.crawl([]);self.assertIn('error',result);self.assertEqual(saved,[])
    def test_partial_rebuild_only_upserts_and_reports_warning(self):
        result,saved=self.crawl(CollectionItems([{'url':'a'}],complete=False,warnings=['one source failed']));self.assertIn('warning',result);self.assertFalse(saved[0]['replace'])
    def test_complete_rebuild_replaces(self):
        result,saved=self.crawl(CollectionItems([{'url':'a'}]));self.assertNotIn('error',result);self.assertTrue(saved[0]['replace'])
    def test_background_job_forwards_replace_flag(self):
        calls=[];state={'running':True};ctx={'_JOBS':{'biz':state},'_do_crawl':lambda group,**kw:calls.append(kw) or {'new':1}}
        function('_job_run',ctx)('biz',30,True);self.assertTrue(calls[0]['replace']);self.assertFalse(state['running'])

if __name__=='__main__':unittest.main()
