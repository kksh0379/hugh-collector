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
    def test_reset_recollect_uses_latest_date_and_fresh_attempt_state(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(db, 'DB_PATH', directory + '/test.db'), patch.object(db, '_PG', False):
            db.init_db()
            with db.get_conn() as conn:
                conn.executemany('INSERT INTO news (id, url, content, section, published_at) VALUES (?, ?, ?, ?, ?)', [(1, 'latest', 'existing ' * 15, 'biz', '2026-10-04'), (2, 'other', 'other ' * 15, 'cat', '2026-10-04'), (3, 'older', 'older ' * 30, 'biz', '2026-01-01')])
            self.assertEqual([r['url'] for r in db.news_needs_enrich(limit=1, section='biz')], ['latest'])
            db.mark_news_enrich_attempt(['latest'])
            self.assertEqual([r['url'] for r in db.news_needs_enrich(section='biz')], ['older'])
            db.apply_news_enrich({'older': {'image_url': 'https://paper.example/old.jpg'}})
            with db.get_conn() as conn:
                self.assertEqual(conn.execute("SELECT content FROM news WHERE url='older'").fetchone()['content'], 'older ' * 30)
                self.assertIsNone(conn.execute("SELECT image_url FROM news WHERE url='other'").fetchone()['image_url'])
            # A legacy cursor survives in metadata; it must never hide newly inserted rows.
            db.set_meta('news_image_cursor_v368_biz', '1')
            db.clear_news_section('biz')
            with db.get_conn() as conn:
                conn.execute("INSERT INTO news (id, url, content, section, published_at) VALUES (9, 'latest', 'text', 'biz', '2026-10-04')")
            self.assertEqual([r['url'] for r in db.news_needs_enrich(section='biz')], ['latest'])

    def test_old_schema_migrates_without_losing_news(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(db, 'DB_PATH', directory + '/test.db'), patch.object(db, '_PG', False):
            with db.get_conn() as conn:
                conn.execute(db._DDL[0].replace(' enrich_checked_at TEXT,', ''))
                conn.execute("INSERT INTO news (url, title, section) VALUES ('saved', 'preserve me', 'biz')")
            db.init_db()
            with db.get_conn() as conn:
                row = conn.execute("SELECT title, enrich_checked_at FROM news WHERE url='saved'").fetchone()
                self.assertEqual(row['title'], 'preserve me'); self.assertIsNone(row['enrich_checked_at'])

    def test_failed_candidates_marked_and_busy_job_can_resume(self):
        module = ast.parse((Path(__file__).resolve().parents[1] / 'app.py').read_text())
        fn = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == '_enrich_news_images')
        marked, calls = [], []
        def candidates(**kwargs):
            calls.append(kwargs)
            return [{'url': 'a'}] if not marked else []
        fake_db = SimpleNamespace(news_needs_enrich=candidates, apply_news_enrich=lambda data: 0,
                                  mark_news_enrich_attempt=lambda urls: marked.extend(urls))
        lock = threading.Lock()
        scope = {'IMG_ENRICH_MAX': 200, '_news_image_locks': {'biz': lock}, 'db': fake_db,
                 'google_news': SimpleNamespace(enrich_articles=lambda rows, **kwargs: {}), '_invalidate_read_cache': lambda: None}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'app.py', 'exec'), scope)
        lock.acquire(); scope['_enrich_news_images'](section='biz'); lock.release()
        self.assertEqual(calls, [])
        scope['_enrich_news_images'](section='biz', limit=40)
        self.assertEqual(marked, ['a']); self.assertEqual(calls[0]['limit'], 40)

    def test_large_crawl_still_fetches_newest_originals(self):
        rows = [{'url': 'old', 'title': 'old', 'published_at': '2026-01-01', 'snippet': 'rss'},
                {'url': 'latest', 'title': 'latest', 'published_at': '2026-10-04', 'snippet': 'rss'},
                {'url': 'middle', 'title': 'middle', 'published_at': '2026-09-01', 'snippet': 'rss'}]
        fetched = []
        def original(entry):
            fetched.append(entry['url']); return dict(entry, content='original', image_url='https://paper.example/' + entry['url'] + '.jpg')
        with patch.object(google_news, '_date_windows', return_value=[('a','b')]), patch.object(google_news, '_collect_items', return_value=rows), patch.object(google_news, '_summary_from_article', side_effect=original), patch.object(google_news, 'FULLBODY_MAX', 2), patch.object(google_news, '_passes_date', return_value=True):
            result = google_news.crawl(categories={'test': ['keyword']}, keyword_filter=False)
        self.assertEqual(set(fetched), {'latest', 'middle'})
        by_url = {r['url']: r for r in result}
        self.assertTrue(by_url['latest']['image_url']); self.assertEqual(by_url['old']['content'], 'rss')


if __name__ == '__main__':
    unittest.main()
