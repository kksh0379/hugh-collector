"""Event list deduplication remains equivalent to the original while scaling linearly."""
import unittest
from unittest.mock import patch
from pathlib import Path
from collector import event_identity
import app as web


def previous_merge(items):
    out = []
    for source in items:
        row = dict(source)
        for index, old in enumerate(out):
            if not event_identity._same(old, row):
                continue
            if old.get('source') in ('', '뉴스', None) and row.get('source') not in ('', '뉴스', None):
                preferred, other = row, old
            else:
                preferred, other = old, row
            out[index] = dict(preferred)
            for field in ('content', 'image_url', 'venue', 'region', 'end_date', 'author'):
                if not out[index].get(field) and other.get(field):
                    out[index][field] = other[field]
            break
        else:
            out.append(row)
    return out


class EventPerformanceTests(unittest.TestCase):
    def test_indexed_dedup_preserves_source_priority_and_missing_fields(self):
        rows = [
            {'url': 'https://news.example/a', 'title': 'AI 전시', 'start_date': '2026-12-10', 'venue': '코엑스', 'source': '뉴스', 'content': '소개'},
            {'url': 'https://official.example/a', 'title': 'AI 전시', 'start_date': '2026-12-10', 'venue': '코엑스', 'source': '관광공사', 'image_url': 'https://images.example/a'},
            {'url': 'https://official.example/a', 'title': '다른 표기', 'start_date': '2026-12-11', 'venue': '', 'source': '문화포털'},
            {'url': 'https://news.example/d', 'title': '다른 행사', 'start_date': '2026-12-15', 'venue': '세텍', 'source': '뉴스'},
            {'url': 'https://news.example/e', 'title': '다른 행사', 'start_date': '2026-12-15', 'venue': '', 'source': '뉴스'},
        ]
        self.assertEqual(event_identity.merge_events(rows), previous_merge(rows))

    def test_many_distinct_events_keep_order_and_all_sources(self):
        rows = [{'url': f'https://official.example/{i}', 'title': f'행사 {i}',
                 'start_date': '2026-12-20', 'venue': '서울', 'source': '문화포털'}
                for i in range(900)]
        result = event_identity.merge_events(rows)
        self.assertEqual(result, rows)

    def test_event_api_uses_extended_cache_and_wait(self):
        with patch.object(web.db, 'list_events', return_value=[]), patch.object(web, '_safe_list', return_value=[]) as cached:
            with web.app.test_request_context('/api/events'):
                web.get_events()
        self.assertEqual(cached.call_args.kwargs, {'ttl': 180, 'wait': 1.8})

    def test_event_album_only_builds_visible_chunks(self):
        source = (Path(__file__).resolve().parents[1] / 'static/js/app.js').read_text()
        album = source.split('function renderEventAlbum(list) {', 1)[1].split('const CAL_COLORS', 1)[0]
        self.assertIn('renderInfinite(el, list', album)
        self.assertNotIn('list.forEach(', album)
        load = source.split('async function loadEvent() {', 1)[1].split('function eventDateBadge', 1)[0]
        self.assertEqual(load.count('renderTab("event")'), 1)


if __name__ == '__main__':
    unittest.main()
