import ast
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from flask import Flask

from collector import db, event_images, eventus, fetcher
from collector.image_response import image_content_type


class EventImagesTests(unittest.TestCase):
    def test_blob_raster_content_type_and_non_images(self):
        for data, mime in [(b'\x89PNG\r\n\x1a\n', 'image/png'), (b'\xff\xd8\xff', 'image/jpeg'),
                           (b'GIF89a', 'image/gif'), (b'RIFF1234WEBP', 'image/webp'),
                           (b'1234ftypavif', 'image/avif')]:
            self.assertEqual(image_content_type('application/octet-stream', data), mime)
        self.assertEqual(image_content_type('application/octet-stream', b'<html>error</html>'), '')
        self.assertEqual(image_content_type('text/html', b'\x89PNG\r\n\x1a\n'), '')

    def test_existing_and_new_eventus_relative_urls(self):
        expected = 'https://eventusstorage.blob.core.windows.net/evs/Image/poster.png?x=1'
        self.assertEqual(eventus.normalize_image_url('/Image/poster.png?x=1'), expected)
        self.assertEqual(eventus.normalize_image_url('https://event-us.kr/Image/poster.png?x=1'), expected)
        self.assertEqual(eventus.normalize_image_url('https://cdn.example/photo.jpg'), 'https://cdn.example/photo.jpg')

    def test_detail_poster_relative_lazy_and_event_jsonld(self):
        self.assertEqual(event_images.extract('<div class="poster"><img data-src="../poster.jpg"></div>', 'https://venue.example/events/view'), 'https://venue.example/poster.jpg')
        html = '<script type="application/ld+json">'+json.dumps({'@type':'Event','image':'/fair.jpg'})+'</script>'
        self.assertEqual(event_images.extract(html, 'https://venue.example/view'), 'https://venue.example/fair.jpg')
        self.assertEqual(event_images.extract('<nav><img src="/logo.jpg"></nav>', 'https://venue.example/view'), '')

    def test_proxy_serves_octet_stream_png_and_rejects_html(self):
        from flask import Response, request
        from urllib.parse import urlsplit
        tree = ast.parse(Path('app.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'img_proxy')
        fn.decorator_list = []
        ctx = dict(Response=Response, request=request, urlsplit=urlsplit, eventus=eventus, fetcher=fetcher)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'app.py', 'exec'), ctx)
        app = Flask(__name__)
        app.add_url_rule('/api/img', view_func=ctx['img_proxy'])
        response = SimpleNamespace(status_code=200, headers={'content-type':'application/octet-stream'}, content=b'\x89PNG\r\n\x1a\n')
        with patch.object(fetcher, 'get', return_value=response):
            result = app.test_client().get('/api/img?u=https://event-us.kr/Image/poster.png')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.content_type, 'image/png')
            self.assertEqual(result.headers['X-Content-Type-Options'], 'nosniff')
            response.content = b'<html>Error</html>'
            self.assertEqual(app.test_client().get('/api/img?u=https://event-us.kr/Image/poster.png').status_code, 404)

    def test_queue_preserves_data_and_does_not_repeat_failures(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(db, 'DB_PATH', directory+'/test.db'), patch.object(db, '_PG', False):
            db.init_db()
            db.upsert_event_many([{'url':'https://venue.example/a','title':'original','end_date':'2099-01-01'},
                {'url':'https://venue.example/b','title':'text only','end_date':'2099-01-01'},
                {'url':'https://venue.example/c','title':'existing','end_date':'2099-01-01','image_url':'https://cdn.example/existing.jpg'}])
            def fake(row):
                image = 'https://cdn.example/poster.jpg' if row['url'].endswith('/a') else ''
                return row['url'], image, '이미지 확보' if image else '원문 이미지 없음'
            with patch.object(event_images, 'fetch', side_effect=fake) as fetch:
                self.assertEqual(event_images.enrich(), 1)
                self.assertEqual(fetch.call_count, 2)
                self.assertEqual(event_images.enrich(), 0)
                self.assertEqual(fetch.call_count, 2)
            with db.get_conn() as conn:
                rows = {r['url']:dict(r) for r in conn.execute('SELECT * FROM events').fetchall()}
            self.assertEqual(rows['https://venue.example/a']['title'], 'original')
            self.assertEqual(rows['https://venue.example/a']['image_url'], 'https://cdn.example/poster.jpg')
            self.assertEqual(rows['https://venue.example/c']['image_url'], 'https://cdn.example/existing.jpg')


if __name__ == '__main__':
    unittest.main()
