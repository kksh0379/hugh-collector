import unittest
from collector import dedup


class DedupTests(unittest.TestCase):
    def test_nfkc_titles_group(self):
        items = [
            {"url": "g1", "title": "성북문화재단·서울다원학교, 보편적 독서권 보장 위해 ‘맞손’", "published_at": "2026-10-05 22:13", "content": "성북문화재단과 서울다원학교가 업무협약을 체결했다."},
            {"url": "g2", "title": "성북문화재단·서울다원학교, 보편적 독서권 보장 위해 '맞손'", "published_at": "2026-10-05 22:13", "content": "성북문화재단과 서울다원학교가 업무 협약을 체결했다."},
        ]
        keys = dedup.cluster_items(items)
        self.assertEqual(keys[0], keys[1])

    def test_same_source_url_groups_different_google_tokens(self):
        items = [
            {"url": "google-a", "source_url": "https://example.com/news/123?utm_source=x", "title": "기사 제목 A", "published_at": "2026-10-05", "content": "내용 하나"},
            {"url": "google-b", "source_url": "https://www.example.com/news/123", "title": "기사 제목 B", "published_at": "2026-10-05", "content": "다른 요약"},
        ]
        keys = dedup.cluster_items(items)
        self.assertEqual(keys[0], keys[1])


if __name__ == "__main__":
    unittest.main()
