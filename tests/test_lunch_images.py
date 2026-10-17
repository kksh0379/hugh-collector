import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from collector import db, lunch_images as images

ROW = {'id':1, 'name':'이화김치찌개 혜화점', 'road_address':'서울 종로구 이화장길 100'}

def page(**overrides):
    entity={'@type':'Restaurant','name':ROW['name'],'address':{'@type':'PostalAddress','addressRegion':'서울특별시','addressLocality':'종로구','streetAddress':'이화장길 100'},'image':['https://img.example/a.jpg','https://img.example/b.jpg']}
    entity.update(overrides)
    return '<script type="application/ld+json">'+json.dumps(entity,ensure_ascii=False)+'</script>'

class ImageTests(unittest.TestCase):
    def test_exact_name_and_address_images_only(self):
        result=images.extract(page(),'https://example.com/store',ROW)
        self.assertEqual(result['status'],'verified')
        self.assertEqual(len(result['images']),2)
        for overrides in [{'name':'이화김치찌개 판교점'},{'address':'서울 종로구 이화장길 101'},{'address':'서울 종로구 이화장길 1001'},{'address':'부산 중구 이화장길 100'},{'@type':'BlogPosting'}]:
            self.assertIsNone(images.extract(page(**overrides),'https://example.com',ROW))
    def test_generic_og_and_other_business_image_are_never_reused(self):
        self.assertIsNone(images.extract('<title>이화김치찌개 혜화점 서울 종로구 이화장길 100</title><meta property="og:image" content="https://example.com/a.jpg">','https://example.com',ROW))
        self.assertIsNone(images.extract(page(image=['https://example.com/logo.png']),'https://example.com',ROW))
        self.assertNotEqual(images.identity(ROW),images.identity(dict(ROW,road_address='다른 주소')))
    def test_nested_graph_and_branch_image_association(self):
        entity={'@graph':[{'@type':'Restaurant','name':'다른 식당','address':ROW['road_address'],'image':'https://example.com/wrong.jpg'}, {'@type':'Restaurant','name':ROW['name'],'address':ROW['road_address'],'image':{'contentUrl':'/correct.jpg'}}]}
        result=images.extract('<script type="application/ld+json">'+json.dumps(entity)+'</script>','https://example.com/store',ROW)
        self.assertEqual(result['images'],['https://example.com/correct.jpg'])
    def test_private_urls_credentials_and_ports_are_rejected(self):
        for url in ['file:///etc/passwd','http://127.0.0.1','http://169.254.169.254','http://[::1]','http://user:pass@example.com','https://example.com:123/']:
            self.assertFalse(images.public_url(url),url)
    def test_google_captcha_stops_without_fetching_results(self):
        with patch.object(images,'download',return_value=(b'<div class="g-recaptcha">blocked</div>','https://www.google.com/search','text/html')) as get:
            with self.assertRaises(images.SearchBlocked): images.discover(ROW)
            self.assertEqual(get.call_count,1)
    def test_lookup_serves_persistent_cache_without_a_network_call(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(db,'DB_PATH',str(Path(directory)/'test.db')):
            db.init_db(); db.lunch_seed_locations([{'name':'테스트'}]); db.lunch_upsert_restaurants(1,[dict(ROW,place_id='test')])
            row=db.lunch_list_restaurants(1)[0]
            value={'status':'verified','checked_at':time.time(),'images':['https://example.com/a.jpg']}
            db.set_meta(images.identity(row),json.dumps(value))
            with patch.object(images.threading,'Thread') as thread:
                self.assertEqual(images.lookup([row['id']])[str(row['id'])]['status'],'verified')
                thread.assert_not_called()

if __name__=='__main__': unittest.main()
