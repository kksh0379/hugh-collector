import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from collector import boards, social
from collector.collection_result import CollectionFailure


class CollectionFailureTests(unittest.TestCase):
    def test_projectory_transient_html_recovers(self):
        bad = SimpleNamespace(text='<html>temporary</html>', json=lambda: (_ for _ in ()).throw(ValueError('HTML')))
        good = SimpleNamespace(json=lambda: {'boardList': []})
        with patch.object(boards.fetcher, 'get', side_effect=[bad, good]) as get, patch.object(boards.time, 'sleep'):
            self.assertEqual(boards._projectory_list_json('api', {}, {}), {'boardList': []})
            self.assertEqual(get.call_count, 2)

    def test_projectory_persistent_html_preserves_partial_failure(self):
        bad = SimpleNamespace(headers={'Content-Type': 'text/html'}, text='<html>error</html>', json=lambda: (_ for _ in ()).throw(ValueError('HTML')))
        cfg = {'service': '프로젝토리', 'category': '갤러리', 'base_url': 'https://example.org', 'projectory_api': 'https://example.org/api'}
        with patch.object(boards.fetcher, 'get', return_value=bad) as get, patch.object(boards.time, 'sleep'):
            result = boards._crawl_projectory(cfg, 10)
            self.assertFalse(result.complete)
            self.assertIn('웹페이지', result.warnings[0])
            self.assertEqual(get.call_count, 2)

    def test_json_429_honors_retry_after(self):
        from requests import HTTPError
        response = SimpleNamespace(status_code=429, headers={'Retry-After': '120'}, json=lambda: {'error': {'code': 429}})
        with patch.dict(social.os.environ, {'YOUTUBE_API_KEY': 'test'}), patch.object(social.db, 'get_meta', return_value='{}'), patch.object(social.db, 'set_meta') as save, patch.object(social.time, 'time', return_value=1000), patch.object(social.fetcher, 'get', side_effect=HTTPError(response=response)):
            with self.assertRaises(CollectionFailure):
                social._crawl_youtube_search('a', 'a')
            self.assertEqual(json.loads(save.call_args.args[1])['until'], 1120)

    def test_instagram_gallery_is_not_retried_as_board_api(self):
        page = SimpleNamespace(text="_sendAxios.getParam('https://graph.instagram.com/me/media', params)", json=lambda: (_ for _ in ()).throw(ValueError('HTML')))
        with patch.object(boards.fetcher, 'get', return_value=page) as get:
            with self.assertRaisesRegex(CollectionFailure, '인스타그램 피드'):
                boards._projectory_list_json('api', {}, {})
            get.assert_called_once()

    def test_saved_board_is_returned_without_detail_request(self):
        entry = {'url': 'https://example.org/a', 'title': 'saved', 'published_at': None}
        with patch.object(boards.fetcher, 'get') as get:
            result = boards._build_entry(entry, {'service': 'a', 'category': 'b'}, {entry['url']: 'summary'})
        self.assertEqual(result['content'], 'summary')
        get.assert_not_called()

    def test_empty_search_is_success_and_cached(self):
        with patch.dict(social.os.environ, {'YOUTUBE_API_KEY': 'test'}), patch.object(social.db, 'get_meta', return_value='{}'), patch.object(social.db, 'set_meta') as save, patch.object(social.fetcher, 'get', return_value=SimpleNamespace(json=lambda: {'items': []})):
            self.assertEqual(social._crawl_youtube_search('a', 'a'), [])
            self.assertEqual(json.loads(save.call_args.args[1])['items'], [])

    def test_fresh_cache_avoids_api_call(self):
        cached = json.dumps({'at': time.time(), 'items': [{'url': 'saved'}]})
        with patch.dict(social.os.environ, {'YOUTUBE_API_KEY': 'test'}), patch.object(social.db, 'get_meta', return_value=cached), patch.object(social.fetcher, 'get') as get:
            self.assertEqual(social._crawl_youtube_search('a', 'a'), [{'url': 'saved'}])
            get.assert_not_called()

    def test_expired_cache_refreshes(self):
        cached = json.dumps({'at': time.time() - social.SEARCH_CACHE_SECONDS - 1, 'items': [{'url': 'old'}]})
        with patch.dict(social.os.environ, {'YOUTUBE_API_KEY': 'test'}), patch.object(social.db, 'get_meta', return_value=cached), patch.object(social.db, 'set_meta'), patch.object(social.fetcher, 'get', return_value=SimpleNamespace(json=lambda: {'items': []})) as get:
            self.assertEqual(social._crawl_youtube_search('a', 'a'), [])
            get.assert_called_once()

    def test_quota_stops_remaining_searches(self):
        error = CollectionFailure('quota', stop_search=True)
        with patch.dict(social.os.environ, {'YOUTUBE_API_KEY': 'test'}), patch.object(social, 'SOURCES', []), patch.object(social, 'MAJOR_FOUNDATIONS', ['a', 'b', 'c']), patch.object(social, '_crawl_youtube_search', side_effect=error) as search:
            result = social.crawl_all()
        search.assert_called_once()
        self.assertFalse(result.complete)
        self.assertEqual([s['status'] for s in result.sources], ['failed', 'deferred', 'deferred'])
    def test_quota_error_is_specific(self):
        with self.assertRaises(CollectionFailure) as raised:
            social._raise_youtube_error({'error': {'code': 403, 'errors': [{'reason': 'quotaExceeded'}]}})
        self.assertTrue(raised.exception.stop_search)
        self.assertIn('할당량', str(raised.exception))

    def test_malformed_search_is_not_valid_empty(self):
        with patch.dict(social.os.environ, {'YOUTUBE_API_KEY': 'test'}), patch.object(social.db, 'get_meta', return_value='{}'), patch.object(social.fetcher, 'get', return_value=SimpleNamespace(json=lambda: {})):
            with self.assertRaises(CollectionFailure):
                social._crawl_youtube_search('a', 'a')

    def test_http_429_stops_searches_and_persists_wait_without_exposing_key(self):
        from requests import HTTPError
        meta = {}
        response = SimpleNamespace(status_code=429, headers={'Retry-After': '120'}, json=lambda: (_ for _ in ()).throw(ValueError('HTML')))
        error = HTTPError('https://api.example/search?key=secret-value', response=response)
        with patch.dict(social.os.environ, {'YOUTUBE_API_KEY': 'test'}), patch.object(social, 'SOURCES', []), patch.object(social, 'MAJOR_FOUNDATIONS', ['a', 'b', 'c']), patch.object(social.db, 'get_meta', side_effect=lambda k, d=None: meta.get(k, d)), patch.object(social.db, 'set_meta', side_effect=lambda k, v: meta.update({k: v})), patch.object(social.fetcher, 'get', side_effect=error) as get:
            result = social.crawl_all()
            get.assert_called_once()
            self.assertFalse(result.complete)
            self.assertNotIn('secret-value', str(result.sources))
            wait = json.loads(meta[social.SEARCH_BACKOFF_KEY])
            self.assertGreater(wait['until'], time.time())
            # A new collection run/process reads the stored cooldown and makes no new request.
            get.reset_mock()
            social.crawl_all()
            get.assert_not_called()

    def test_json_rate_limit_is_a_shared_backoff(self):
        with patch.object(social.db, 'set_meta') as save:
            with self.assertRaises(CollectionFailure) as raised:
                social._raise_youtube_error({'error': {'code': 429, 'errors': []}}, search=True)
            self.assertTrue(raised.exception.stop_search)
            self.assertEqual(save.call_args.args[0], social.SEARCH_BACKOFF_KEY)

    def test_search_retries_after_wait_expires(self):
        with patch.dict(social.os.environ, {'YOUTUBE_API_KEY': 'test'}), patch.object(social.db, 'get_meta', side_effect=lambda key, default=None: json.dumps({'until': time.time()-1}) if key == social.SEARCH_BACKOFF_KEY else '{}'), patch.object(social.db, 'set_meta'), patch.object(social.fetcher, 'get', return_value=SimpleNamespace(json=lambda: {'items': []})) as get:
            self.assertEqual(social._crawl_youtube_search('a', 'a'), [])
            get.assert_called_once()
