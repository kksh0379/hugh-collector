import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from collector import game_feeds, google_news
from collector.collection_result import CollectionItems


NOW = datetime(2026, 11, 15, 0, 0, tzinfo=timezone.utc)


def rss(items):
    return ('<rss version="2.0"><channel><title>Ruliweb</title>' +
            ''.join('<item><title>' + title + '</title><link>' + url +
                    '</link><pubDate>' + date + '</pubDate><description>게임 소개 및 업데이트</description></item>'
                    for title, url, date in items) + '</channel></rss>').encode()


class OfficialGameFeedTests(unittest.TestCase):
    def test_current_articles_preserve_source_and_canonical_url(self):
        rows = rss([
            ('신규 게임 발표', 'https://bbs.ruliweb.com/news/read/231900', 'Sat, 14 Nov 2026 09:00:00 +0000'),
            ('옛날 뉴스', 'https://bbs.ruliweb.com/news/read/5', 'Sun, 01 Jan 2023 00:00:00 +0000'),
            ('타 사이트', 'https://evil.example/news/read/1', 'Sat, 14 Nov 2026 09:00:00 +0000'),
            ('게시판 글', 'https://bbs.ruliweb.com/community/board/1', 'Sat, 14 Nov 2026 09:00:00 +0000'),
        ])
        result = game_feeds.parse_rss(rows, days=30, now=NOW + timedelta(days=1))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['url'], 'https://m.ruliweb.com/news/read/231900')
        self.assertEqual(result[0]['author'], '루리웹')

    def test_duplicate_paths_are_filtered(self):
        rows = rss([
            ('기사', 'https://bbs.ruliweb.com/news/read/123', 'Sat, 14 Nov 2026 09:00:00 +0000'),
            ('중복', 'https://m.ruliweb.com/news/read/123', 'Sat, 14 Nov 2026 09:00:00 +0000'),
        ])
        self.assertEqual(len(game_feeds.parse_rss(rows, now=NOW)), 1)

    def test_missing_or_invalid_rss_never_scrapes_forum(self):
        with self.assertRaises(ValueError):
            game_feeds.parse_rss(b'<html><body>Blocked</body></html>')
        self.assertNotIn('community', game_feeds.FEEDS[0][1])

    @patch.object(game_feeds, 'collect')
    @patch.object(google_news, 'crawl')
    def test_feed_and_google_are_merged_without_replacing_existing(self, crawl, direct):
        direct.return_value = ([{'title':'루리웹 뉴스','url':'https://m.ruliweb.com/news/read/12',
                                 'source_url':'https://m.ruliweb.com/news/read/12',
                                 'author':'루리웹','category':'게임 뉴스'}], [])
        crawl.return_value = CollectionItems([{'url':'https://news.google.com/rss/articles/abc'}])
        items = google_news.crawl_game(known_urls={'https://m.ruliweb.com/news/read/11'})
        self.assertEqual(len(items), 2)
        self.assertTrue(items.complete)

    @patch.object(game_feeds, 'collect')
    @patch.object(google_news, 'crawl')
    def test_google_failure_preserves_usable_direct_feed(self, crawl, direct):
        direct.return_value = ([{'url':'https://m.ruliweb.com/news/read/12'}], [])
        crawl.side_effect = RuntimeError('Google temporarily unavailable')
        result = google_news.crawl_game()
        self.assertEqual(len(result), 1)
        self.assertFalse(result.complete)


if __name__ == '__main__':
    unittest.main()
