"""Resolver/queue regressions; no network or optional runtime dependencies."""
import ast
import base64
import json
import re
import sqlite3
import time
import threading
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def functions(path, names, scope):
    tree = ast.parse((ROOT / path).read_text())
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), path, 'exec'), scope)
    return scope


class ResolutionTests(unittest.TestCase):
    def scope(self, payload=None):
        class HTTPError(Exception):
            def __init__(self, response): self.response = response
        signature = SimpleNamespace(get=lambda name: {'data-n-a-sg': 'sig', 'data-n-a-ts': '42'}[name])
        get = Mock(return_value=SimpleNamespace(text='signature', url='https://news.google.com/rss/articles/token'))
        fetcher = SimpleNamespace(get=get, post=Mock(return_value=SimpleNamespace(text=payload or json.dumps([
            ['di', 1], ['wrb.fr', 'Fbv4je', json.dumps(['garturlres', 'https://paper.example/story'])]
        ], indent=2))))
        scope = dict(json=json, re=re, base64=base64, urlsplit=urlsplit, time=time,
                     requests=SimpleNamespace(HTTPError=HTTPError), fetcher=fetcher,
                     BeautifulSoup=lambda *a: SimpleNamespace(select_one=lambda *a: signature),
                     NEWS_TIMEOUT=10, BATCH_URL='https://news.google.com/rpc',
                     _DECODE_LOCK=threading.Lock(), _DECODE_NEXT=0, _DECODE_RETRY_AT=0)
        return functions('collector/google_news.py', {'_decode_google_url', '_decode_via_batchexecute', '_decode_rpc', '_publisher_url'}, scope)

    def test_rss_signature_path_and_multiline_nonfirst_rpc(self):
        scope = self.scope()
        self.assertEqual(scope['_decode_rpc']('token'), 'https://paper.example/story')
        self.assertEqual(scope['fetcher'].get.call_args.args[0], 'https://news.google.com/rss/articles/token')

    def test_length_prefixed_rpc(self):
        body = json.dumps([['wrb.fr', 'Fbv4je', json.dumps(['garturlres', 'https://paper.example/2'])]])
        scope = self.scope(")]}'\n\n" + str(len(body)) + '\n' + body + '\n42\n[["di",1]]')
        self.assertEqual(scope['_decode_rpc']('token'), 'https://paper.example/2')

    def test_read_legacy_binary_suffix_removed(self):
        scope = self.scope()
        token = base64.urlsafe_b64encode(b'\x08\x13\x22https://paper.example/story\xd2\x01\x00').decode().rstrip('=')
        self.assertEqual(scope['_decode_google_url']('https://news.google.com/read/' + token), 'https://paper.example/story')

    def test_rate_limit_respects_cooldown(self):
        scope = self.scope()
        error = scope['requests'].HTTPError(SimpleNamespace(status_code=429, headers={'Retry-After': '600'}))
        scope['fetcher'].get.side_effect = error
        self.assertIsNone(scope['_decode_via_batchexecute']('token'))
        self.assertGreaterEqual(scope['_DECODE_RETRY_AT'], time.time() + 590)
        self.assertIsNone(scope['_decode_via_batchexecute']('second'))
        self.assertEqual(scope['fetcher'].get.call_count, 1)


class QueueTests(unittest.TestCase):
    def test_cooldown_candidates_remain_unmarked(self):
        marked = []
        db = SimpleNamespace(news_needs_enrich=lambda **kw: [{'url': 'rate-limited'}, {'url': 'no-image'}],
                             apply_news_enrich=lambda data: 0,
                             mark_news_enrich_attempt=lambda urls: marked.extend(urls))
        scope = functions('app.py', {'_enrich_news_images'},
                          dict(IMG_ENRICH_MAX=200, _news_image_locks={'biz': threading.Lock()}, db=db,
                               google_news=SimpleNamespace(enrich_articles=lambda *a, **kw: {'rate-limited': {'_retry': True}}),
                               _invalidate_read_cache=lambda: None))
        scope['_enrich_news_images'](section='biz')
        self.assertEqual(marked, ['no-image'])

    def test_requeues_only_missing_biz_images_and_preserves_content(self):
        conn = sqlite3.connect(':memory:'); conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        conn.execute('CREATE TABLE news (id INTEGER, url TEXT, source_url TEXT, content TEXT, image_url TEXT, section TEXT, published_at TEXT, enrich_checked_at TEXT)')
        conn.executemany('INSERT INTO news VALUES (?, ?, NULL, ?, ?, ?, ?, ?)', [
            (1, 'latest', 'keep', None, 'biz', '2026-10-05', '2026-10-05'),
            (2, 'photo', 'keep', 'https://paper.example/photo.jpg', 'biz', '2026-10-04', '2026-10-05'),
            (3, 'cat', 'keep', None, 'cat', '2026-10-05', '2026-10-05')])
        @contextmanager
        def get_conn(): yield conn
        scope = functions('collector/db.py', {'reset_missing_news_image_attempts', 'news_needs_enrich'},
                          dict(get_conn=get_conn, _q=lambda s:s, datetime=datetime, timedelta=timedelta, timezone=timezone))
        scope['reset_missing_news_image_attempts']('biz')
        self.assertEqual([r['url'] for r in scope['news_needs_enrich'](section='biz')], ['latest'])
        rows = list(conn.execute('SELECT * FROM news ORDER BY id'))
        self.assertIsNone(rows[0]['enrich_checked_at'])
        self.assertEqual(rows[0]['content'], 'keep')
        self.assertEqual(rows[1]['image_url'], 'https://paper.example/photo.jpg')
        self.assertIsNotNone(rows[2]['enrich_checked_at'])


if __name__ == '__main__': unittest.main()
