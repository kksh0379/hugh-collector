import os
import threading
import unittest
from unittest.mock import patch

from flask import Flask
from collector import reader, reader_summary as summaries

ARTICLE = {"mode": "article", "title": "문화 소식", "paragraphs": ["새로운 문화교육 프로그램이 시작되고 참여자를 모집합니다. " * 12]}


class SummaryTests(unittest.TestCase):
    def test_highlights_are_exact_limited_phrases_without_changing_summary(self):
        point = "개인정보 10만 건이 유출되어 기관이 비밀번호 변경을 권고했습니다."
        data = summaries._normalize_summary({"points": [point, "대응 과정과 원인에 대한 추가 조사가 진행됩니다."],
                                             "highlights": [["10만 건", "비밀번호 변경", "추가 주장"], ["없는 사실", 12]]})
        self.assertEqual(data["points"][0], point)
        self.assertEqual(data["highlights"], [["10만 건", "비밀번호 변경"], []])

    def test_whole_sentence_and_overlapping_highlights_are_discarded(self):
        point = "기관은 개인정보 보호 조치를 강화하고 관련 절차를 점검했습니다."
        data = summaries._normalize_summary({"points": [point, "추가 조사는 계속 진행될 예정입니다."],
                                             "highlights": [[point, "개인정보 보호", "개인정보", "관련 절차"], []]})
        self.assertEqual(data["highlights"][0], ["개인정보 보호", "관련 절차"])

    def setUp(self):
        summaries._jobs.clear()
        reader._summary_sources.clear()
        self.key = patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-only"})
        self.key.start()

    def tearDown(self):
        self.key.stop()

    def test_excerpt_is_not_summarized_as_full_article(self):
        with patch.object(summaries, "_generate") as generate:
            self.assertEqual(summaries.article_summary({"mode": "excerpt"})["status"], "unavailable")
            generate.assert_not_called()

    def test_missing_key_is_clear_and_makes_no_call(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}), patch.object(summaries, "_generate") as generate:
            self.assertEqual(summaries.article_summary(ARTICLE)["status"], "unavailable")
            generate.assert_not_called()

    def test_concurrent_requests_share_one_summary_and_reuse_success(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        def generate(*args):
            entered.set()
            release.wait(2)
            return ["참여자를 모집합니다.", "문화교육 프로그램이 시작됩니다."]
        with patch.object(summaries, "_generate", side_effect=generate) as call:
            self.assertEqual(summaries.article_summary(ARTICLE)["status"], "pending")
            self.assertTrue(entered.wait(1))
            self.assertEqual(summaries.article_summary(ARTICLE)["status"], "pending")
            self.assertEqual(call.call_count, 1)
            release.set()
            for _ in range(100):
                result = summaries.article_summary(ARTICLE)
                if result["status"] == "ready":
                    finished.set(); break
                threading.Event().wait(.01)
            self.assertTrue(finished.is_set())
            self.assertEqual(len(result["points"]), 2)
            self.assertEqual(summaries.article_summary(ARTICLE), result)
            self.assertEqual(call.call_count, 1)

    def test_failed_generation_is_cached_without_exposing_error_details(self):
        with patch.object(summaries, "_generate", side_effect=RuntimeError("secret API failure")) as call:
            summaries.article_summary(ARTICLE)
            for _ in range(100):
                result = summaries.article_summary(ARTICLE)
                if result["status"] == "unavailable": break
                threading.Event().wait(.01)
            self.assertEqual(result["status"], "unavailable")
            self.assertNotIn("secret", str(result))
            summaries.article_summary(ARTICLE)
            self.assertEqual(call.call_count, 1)

    def test_polling_reuses_loaded_article_without_database_reads(self):
        app = Flask(__name__); app.register_blueprint(reader.bp)
        reader._remember_summary_source("https://publisher.example/1", ARTICLE)
        with patch.object(reader.db, "reader_item") as lookup, patch.object(reader, "article_summary", return_value={"status": "pending"}):
            for _ in range(3):
                response = app.test_client().get('/api/reader-summary?url=https://publisher.example/1')
                self.assertEqual(response.status_code, 202)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
            lookup.assert_not_called()

    def test_unknown_url_is_rejected_before_summary_or_publisher_fetch(self):
        app = Flask(__name__); app.register_blueprint(reader.bp)
        with patch.object(reader.db, "reader_item", return_value=None), patch.object(reader, "read_article") as fetch:
            self.assertEqual(app.test_client().get('/api/reader-summary?url=https://unknown.example/').status_code, 404)
            fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
