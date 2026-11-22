import socket
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from collector import db, reader


TEXT = "지역 사회의 새로운 문화교육 프로그램이 시작됩니다. 참여자들은 함께 배우며 다양한 경험을 나눕니다. " * 5
HTML = f'<html><article><h2>문화교육 소식</h2><p>{TEXT}</p><div class="ad">광고문구</div><script>alert(1)</script><p>두 번째 문단입니다.</p></article></html>'


class ReaderTests(unittest.TestCase):
    def setUp(self):
        reader._cache.clear()
        reader._summary_sources.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = patch.object(db, "DB_PATH", str(Path(self.tmp.name) / "test.db"))
        self.db_path.start()
        db.init_db()
        with db.get_conn() as conn:
            conn.execute("INSERT INTO news (url, source_url, title, content) VALUES (?, ?, ?, ?)",
                         ("https://news.example/rss/1", "https://publisher.example/story/1", "테스트 기사", "저장된 요약"))
        app = Flask(__name__)
        app.register_blueprint(reader.bp)
        self.client = app.test_client()

    def tearDown(self):
        self.db_path.stop()
        self.tmp.cleanup()

    def test_article_removes_ads_and_scripts_keeps_paragraphs(self):
        paragraphs = reader.extract_paragraphs(HTML)
        self.assertIn(TEXT.strip(), paragraphs)
        self.assertIn("두 번째 문단입니다.", paragraphs)
        self.assertNotIn("광고문구", " ".join(paragraphs))
        self.assertNotIn("alert", " ".join(paragraphs))

    def test_publisher_div_bodies_are_extracted_without_page_navigation(self):
        for marker in ('id="article-view-content-div"', 'id="news_body_area"', 'id="article_txt"', 'class="article-text"'):
            with self.subTest(marker=marker):
                html = f'<nav>{TEXT}</nav><div {marker}><p>{TEXT}</p></div>'
                self.assertEqual(reader.extract_paragraphs(html), [TEXT.strip()])


    def test_twenty_article_layout_regressions(self):
        """Twenty synthetic publisher layouts must retain the final paragraph."""
        lead = "기사의 시작 부분입니다. " * 20
        ending = "기사의 마지막 문단도 반드시 표시됩니다. " * 20
        markers = [
            'id="dic_area"', 'id="articleBody"', 'id="article-body"',
            'id="articleBodyContents"', 'id="newsct_article"',
            'itemprop="articleBody"', 'class="article-body"',
            'class="article_body"', 'class="view_content"',
            'class="board_view"', 'class="post-content"',
            'class="content_view"', 'id="newsEndContents"',
            'id="news_body_area"', 'id="article_txt"',
            'class="article_content"', 'class="news_body"',
            'class="article-text"', 'class="view_cont"',
            'class="bbs_content"',
        ]
        self.assertEqual(len(markers), 20)
        for marker in markers:
            with self.subTest(marker=marker):
                html = (
                    '<html><nav><a href="/">' + lead + '</a></nav>'
                    '<div id="articleBody"><p>' + lead + '</p></div>'
                    '<section ' + marker + '><p>' + lead + '</p><p>' + ending + '</p></section>'
                    '</html>'
                )
                extracted = " ".join(reader.extract_paragraphs(html))
                self.assertIn(ending.strip(), extracted)
                self.assertGreaterEqual(len(extracted), len(lead + ending) - 5)

    def test_rejects_navigation_only(self):
        with self.assertRaises(reader.ReaderUnavailable):
            reader.extract_paragraphs('<main><a href="/">' + TEXT + '</a></main>')

    def test_rejects_paywall(self):
        for marker in ('<script type="application/ld+json">{"isAccessibleForFree":false}</script>', '<div class="paywall">구독</div>'):
            with self.subTest(marker=marker), self.assertRaises(reader.ReaderUnavailable):
                reader.extract_paragraphs(marker + HTML)

    def test_korean_legacy_encoding(self):
        paragraphs = reader.extract_paragraphs(('<meta charset="euc-kr">' + HTML).encode("euc-kr"))
        self.assertIn("두 번째 문단입니다.", paragraphs)

    def test_rejects_private_loopback_and_mixed_dns(self):
        for address in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "::ffff:127.0.0.1"):
            answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
                       (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]
            with self.subTest(address=address), patch.object(socket, "getaddrinfo", return_value=answers):
                with self.assertRaises(reader.ReaderUnavailable):
                    reader.public_target("https://publisher.example/story")

    def test_rejects_bad_schemes_credentials_and_ports(self):
        for url in ("file:///etc/passwd", "http://user:pw@example.com/", "https://example.com:9000/", "http://example.com/\n"):
            with self.subTest(url=url), self.assertRaises(reader.ReaderUnavailable):
                reader.public_target(url)

    def test_public_target_pins_resolved_address(self):
        with patch.object(socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]):
            self.assertEqual(reader.public_target("https://publisher.example/a")[3], "93.184.216.34")

    def test_unknown_url_does_not_fetch(self):
        with patch.object(reader, "fetch_html") as fetch:
            self.assertEqual(self.client.get('/api/reader?url=https://unknown.example/').status_code, 404)
            fetch.assert_not_called()

    def test_database_failure_is_recoverable(self):
        with patch.object(db, "reader_item", side_effect=RuntimeError("private details")):
            response = self.client.get('/api/reader?url=https://publisher.example/story/1')
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("private details", response.get_data(as_text=True))

    def test_success_and_cache_by_canonical_url(self):
        with patch.object(reader, "fetch_html", return_value=HTML) as fetch:
            first = self.client.get('/api/reader?url=https://news.example/rss/1').get_json()
            second = self.client.get('/api/reader?url=https://publisher.example/story/1').get_json()
            self.assertEqual(first["mode"], "article")
            self.assertEqual(first, second)
            fetch.assert_called_once_with("https://publisher.example/story/1")

    def test_google_news_resolves_before_safe_fetch(self):
        item = {"url": "https://news.google.com/rss/articles/test", "title": "기사"}
        with patch("collector.google_news._decode_google_url", return_value="https://publisher.example/story"), patch.object(reader, "fetch_html", return_value=HTML) as fetch:
            data = reader.read_article(item)
            self.assertEqual(data["mode"], "article")
            self.assertEqual(data["url"], "https://publisher.example/story")
            fetch.assert_called_once_with("https://publisher.example/story")

    def test_resolved_original_survives_failure_and_retry(self):
        wrapper = "https://news.google.com/rss/articles/test"
        original = "https://publisher.example/story"
        with db.get_conn() as conn:
            conn.execute("INSERT INTO news (url, title, content) VALUES (?, ?, ?)",
                         (wrapper, "기사", "저장된 요약"))
        with patch("collector.google_news._decode_google_url", return_value=original), patch.object(
            reader, "fetch_html", side_effect=[TimeoutError, HTML]
        ):
            first = self.client.get("/api/reader", query_string={"url": wrapper}).get_json()
            second = self.client.get("/api/reader", query_string={"url": wrapper}).get_json()
        self.assertEqual(first["mode"], "excerpt")
        self.assertEqual(first["url"], original)
        self.assertEqual(first["paragraphs"], ["저장된 요약"])
        self.assertEqual(second["mode"], "article")

    def test_google_fallback_matches_publisher_and_persists_article(self):
        from types import SimpleNamespace
        from collector import google_news
        wrapper = "https://news.google.com/rss/articles/previously-unseen"
        title = "아직 저장되지 않은 새 기사 원문 자동 복구"
        original = "https://publisher.example/new-story"
        markup = f"""<ul class="list_news">
          <li><a class="item-writer"><span class="txt_info">다른 매체</span></a>
              <a class="tit_main" href="https://wrong.example/">{title}</a></li>
          <li><a class="item-writer"><span class="txt_info">예시 뉴스</span></a>
              <a class="tit_main" href="https://cp.news.search.daum.net/p/42">{title}</a></li>
        </ul>"""
        with db.get_conn() as conn:
            conn.execute("INSERT INTO news (url, title, author) VALUES (?, ?, ?)",
                         (wrapper, title, "예시뉴스"))
        with patch.object(google_news, "_decode_google_url", return_value=None), patch.object(
            google_news.fetcher, "get", side_effect=[
                SimpleNamespace(content=markup.encode()),
                SimpleNamespace(status_code=302, headers={"Location": original}),
            ]
        ), patch.object(reader, "fetch_html", return_value=HTML) as fetch:
            article = self.client.get("/api/reader", query_string={"url": wrapper}).get_json()
        self.assertEqual(article["mode"], "article")
        fetch.assert_called_once_with(original)
        self.assertEqual(db.reader_item(wrapper)["source_url"], original)

    def test_publisher_index_checks_real_headline_when_google_is_unavailable(self):
        from types import SimpleNamespace
        from collector import google_news

        wrapper = "https://news.google.com/rss/articles/unresolved-publisher-story"
        title = "검색 결과보다 원문 기사 제목을 직접 확인합니다"
        original = "https://www.famtimes.co.kr/news/articleView.html?idxno=9"
        sitemap = f"""<urlset><url><loc>{original}</loc>
            <lastmod>2026-11-20T14:03:39+09:00</lastmod></url></urlset>"""
        item = {"url": wrapper, "title": title, "author": "팸타임스 FAM Times",
                "published_at": "2026-11-20T05:03"}
        with patch.object(google_news, "_decode_google_url", return_value=None), patch.object(
            google_news.fetcher, "get", return_value=SimpleNamespace(status_code=200, content=sitemap.encode())
        ), patch.object(google_news, "search_publisher_url", return_value=None), patch.object(
            reader, "fetch_html", side_effect=[HTML, f"<h1>{title}</h1>{HTML}"]
        ) as fetch:
            wrong = reader.read_article(item)
            correct = reader.read_article(item)
        self.assertEqual(wrong["mode"], "excerpt")
        self.assertEqual(wrong["url"], wrapper)
        self.assertEqual(correct["mode"], "article")
        self.assertEqual(correct["url"], original)
        self.assertEqual(fetch.call_count, 2)

    def test_short_structured_article_preserves_paragraphs(self):
        import json
        paragraphs = ["첫 번째 기사 문단입니다. " * 5, "두 번째 기사 문단입니다. " * 5]
        data = json.dumps({"@type": "NewsArticle", "articleBody": "\n".join(paragraphs)})
        with patch.object(reader, "fetch_html", return_value=f'<script type="application/ld+json">{data}</script>'):
            article = reader.read_article({"url": "https://publisher.example/short"})
        self.assertEqual(article["mode"], "article")
        self.assertEqual(article["paragraphs"], [part.strip() for part in paragraphs])

    def test_timeout_returns_labelled_excerpt(self):
        with patch.object(reader, "fetch_html", side_effect=TimeoutError):
            data = self.client.get('/api/reader?url=https://publisher.example/story/1').get_json()
            self.assertEqual(data["mode"], "excerpt")
            self.assertEqual(data["paragraphs"], ["저장된 요약"])
            self.assertIn("수집된 요약", data["notice"])

    def test_rejects_redirect_to_internal_network(self):
        class RedirectConnection:
            def __init__(self, *args): pass
            def request(self, *args, **kwargs): pass
            def getresponse(self): return self
            status = 302
            def getheader(self, name): return "http://127.0.0.1/secret"
            def close(self): pass
        def resolve(host, port, **kwargs):
            return [(2, 1, 6, "", (("127.0.0.1" if host == "127.0.0.1" else "93.184.216.34"), port))]
        with patch.object(socket, "getaddrinfo", side_effect=resolve), patch.object(reader, "_PinnedHTTP", RedirectConnection):
            with self.assertRaises(reader.ReaderUnavailable):
                reader.fetch_html("https://publisher.example/story")

    def test_response_size_and_mime_limits(self):
        class Connection:
            sock = None
            def __init__(self, *args): pass
            def request(self, *args, **kwargs): pass
            def getresponse(self): return self
            status = 200
            headers = Message()
            def getheader(self, name, default=""):
                return "text/html" if name == "Content-Type" else default
            def read1(self, size): return b"a" * 32768
            def close(self): pass
        with patch.object(socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]), patch.object(reader, "_PinnedHTTP", Connection):
            with self.assertRaisesRegex(reader.ReaderUnavailable, "large"):
                reader.fetch_html("https://publisher.example/story")
            with patch.object(Connection, "getheader", return_value="application/pdf"):
                with self.assertRaisesRegex(reader.ReaderUnavailable, "Not HTML"):
                    reader.fetch_html("https://publisher.example/story")

    def test_boards_and_events_lookup(self):
        with db.get_conn() as conn:
            conn.execute("INSERT INTO boards (url, title) VALUES (?, ?)", ("https://board.example/1", "게시판"))
            conn.execute("INSERT INTO events (url, source_url, title) VALUES (?, ?, ?)", ("https://event.example/1", "https://publisher.example/event", "행사"))
        self.assertEqual(db.reader_item("https://board.example/1")["title"], "게시판")
        self.assertEqual(db.reader_item("https://publisher.example/event")["title"], "행사")


if __name__ == "__main__":
    unittest.main()
