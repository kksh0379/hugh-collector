"""Performance regressions: bounded first load, separated read keys, safe DB pool fallback."""
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from collector import db
import app as web


ROOT = Path(__file__).resolve().parents[1]


class PerformanceSafetyTests(unittest.TestCase):
    def test_initial_news_uses_only_selected_tab(self):
        source = (ROOT / 'static/js/app.js').read_text()
        initial = source.split('// ----------------------------- 초기 로드 -----------------------------')[-1]
        startup = initial.split('// Pull refresh updates')[0]
        self.assertIn('loadTabOnDemand(activeTab());', startup)
        for call in ('loadCat();', 'loadGame();', 'loadNews();', 'loadBiz();', 'loadSecurity();', 'loadEvent();'):
            self.assertNotIn(call, startup)
        self.assertIn('loadTabOnDemand(tab.dataset.tab)', source)
        self.assertNotIn('  loadLocations();\n  window.onShowLunch', source)

    def test_news_cache_separates_months_from_full_history(self):
        cache = web._PUBLIC_READS
        with web.app.test_request_context('/api/news?category=all&months=3'):
            key_first = web.request.path + repr(tuple((k, web.request.args.get(k, 'all')) for k in ('category','months')))
        with web.app.test_request_context('/api/news?category=all'):
            key_full = web.request.path + repr(tuple((k, web.request.args.get(k, 'all')) for k in ('category','months')))
        self.assertNotEqual(key_first, key_full)
        self.assertIn("('months', '3')", key_first)

    def test_versioned_static_assets_are_browser_cacheable(self):
        with patch.object(web, '_start_worker_jobs'), patch.object(web, '_start_read_prewarm'):
            response = web.app.test_client().get('/static/js/app.js?v=test-version')
        self.assertEqual(response.status_code, 200)
        self.assertIn('max-age=3600', response.headers.get('Cache-Control', ''))
        self.assertIn('public', response.headers.get('Cache-Control', ''))
        self.assertNotIn('no-cache', response.headers.get('Cache-Control', ''))

    def test_initial_news_query_is_bounded(self):
        from unittest.mock import MagicMock
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = []
        with patch.object(db, 'get_conn') as conn:
            conn.return_value.__enter__.return_value = connection
            self.assertEqual(db.list_news(months=3), [])
        args = connection.execute.call_args.args
        self.assertEqual(args[1][-1], 100)

    def test_pool_returns_connection_after_success(self):
        pool, conn = Mock(), Mock()
        with patch.object(db, '_PG', True), patch.object(db, '_borrow_pooled', return_value=(pool, conn)):
            with db.get_conn() as result:
                self.assertIs(result, conn)
        conn.commit.assert_called_once()
        pool.putconn.assert_called_once_with(conn)

    def test_pool_rolls_back_and_returns_connection_on_error(self):
        pool, conn = Mock(), Mock()
        with patch.object(db, '_PG', True), patch.object(db, '_borrow_pooled', return_value=(pool, conn)):
            with self.assertRaises(ValueError):
                with db.get_conn():
                    raise ValueError('test')
        conn.rollback.assert_called_once()
        pool.putconn.assert_called_once_with(conn)


if __name__ == '__main__':
    unittest.main()
