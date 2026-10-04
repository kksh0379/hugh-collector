import ast
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from bs4 import BeautifulSoup
from collector import db, extractor, google_news


def image(html, url='https://paper.example/news/view?id=7'):
    return extractor.extract_image(BeautifulSoup(html, 'lxml'), url)


class ImageExtractionTests(unittest.TestCase):
    def test_meta_relative(self):
        self.assertEqual(image('<meta property="og:image" content="/photo.jpg"><article><img src="other.jpg"></article>'), 'https://paper.example/photo.jpg')

    def test_invalid_meta_fallback(self):
        self.assertEqual(image('<meta property="og:image" content="data:image/png;base64,abc"><meta name="twitter:image" content="//cdn.example/news.jpg">'), 'https://cdn.example/news.jpg')

    def test_article_jsonld_graph(self):
        html = '<script type="application/ld+json">' + json.dumps({'@graph': [{'@type': 'Organization', 'image': '/logo.jpg'}, {'@type': 'NewsArticle', 'image': [{'contentUrl': '../photos/news.jpg'}]}]}) + '</script>'
        self.assertEqual(image(html), 'https://paper.example/photos/news.jpg')

    def test_lazy_body_excludes_logo_ad_icon(self):
        self.assertEqual(image('<article><img src="/logo.png"><aside><img src="/ad.jpg"></aside><img width="1" src="/track.gif"><img src="data:image/png;base64,x" data-original="/news.jpg"></article>'), 'https://paper.example/news.jpg')

    def test_srcset_preserves_http(self):
        self.assertEqual(image('<article><img srcset="/small.jpg 320w, http://cdn.example/big.jpg 1200w"></article>'), 'http://cdn.example/big.jpg')

    def test_no_photo_does_not_pick_navigation(self):
        self.assertIsNone(image('<nav><img src="/news.jpg"></nav><main>text only</main>'))

    def test_google_signature_nested_node(self):
        page = SimpleNamespace(text='<c-wiz><div>menu</div><section><div data-n-a-sg="sig" data-n-a-ts="42"></div></section></c-wiz>')
        result = SimpleNamespace(text=json.dumps([['wrb.fr', 'Fbv4je', json.dumps(['garturlres', 'https://paper.example/story'])]]))
        with patch.object(google_news.fetcher, 'get', return_value=page), patch.object(google_news.fetcher, 'post', return_value=result):
            self.assertEqual(google_news._decode_via_batchexecute('token'), 'https://paper.example/story')

    def test_enrich_body_retains_long_content(self):
        row = {'url': 'https://google.example/rss', 'source_url': 'https://paper.example/news/view', 'content': 'a' * 300}
        response = SimpleNamespace(url=row['source_url'], text='<article><img data-src="/story.jpg"></article>')
        with patch.object(google_news.fetcher, 'get', return_value=response):
            self.assertEqual(google_news._enrich_one(row), {'image_url': 'https://paper.example/story.jpg'})


class ImageQueueTests(unittest.TestCase):
    def test_section_cursor_updates_preserve_content(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(db, 'DB_PATH', directory + '/test.db'), patch.object(db, '_PG', False):
            with db.get_conn() as conn:
                conn.execute('CREATE TABLE news (id INTEGER PRIMARY KEY, url TEXT, source_url TEXT, content TEXT, image_url TEXT, section TEXT)')
                conn.executemany('INSERT INTO news VALUES (?, ?, ?, ?, ?, ?)', [(1, 'old', None, 'existing ' * 15, None, 'biz'), (2, 'other', None, 'other ' * 15, None, 'cat'), (3, 'new', None, 'new ' * 30, None, 'biz')])
            self.assertEqual([r['url'] for r in db.news_needs_enrich(limit=1, section='biz')], ['new'])
            self.assertEqual([r['url'] for r in db.news_needs_enrich(section='biz', before_id=3)], ['old'])
            db.apply_news_enrich({'old': {'image_url': 'https://paper.example/old.jpg'}})
            with db.get_conn() as conn:
                self.assertEqual(conn.execute("SELECT content FROM news WHERE url='old'").fetchone()['content'], 'existing ' * 15)
                self.assertIsNone(conn.execute("SELECT image_url FROM news WHERE url='other'").fetchone()['image_url'])

    def test_failed_images_advance_cursor(self):
        module = ast.parse(Path('app.py').read_text())
        fn = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == '_enrich_news_images')
        meta, calls = {}, []
        def candidates(**kwargs):
            calls.append(kwargs)
            return [{'id': 9, 'url': 'a'}] if kwargs['before_id'] is None else [{'id': 8, 'url': 'b'}]
        fake_db = SimpleNamespace(get_meta=lambda k: meta.get(k), set_meta=lambda k,v: meta.update({k:v}), news_needs_enrich=candidates, apply_news_enrich=lambda data: 0)
        scope = {'IMG_ENRICH_MAX': 200, '_news_image_lock': threading.Lock(), 'db': fake_db, 'google_news': SimpleNamespace(enrich_articles=lambda rows, **kwargs: {}), '_invalidate_read_cache': lambda: None}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'app.py', 'exec'), scope)
        scope['_enrich_news_images'](section='biz'); scope['_enrich_news_images'](section='biz')
        self.assertEqual([c['before_id'] for c in calls], [None, 9])
        self.assertEqual(meta['news_image_cursor_v368_biz'], '8')


if __name__ == '__main__':
    unittest.main()
