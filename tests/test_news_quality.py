import unittest

from bs4 import BeautifulSoup
from collector import extractor


class NewsQualityTests(unittest.TestCase):
    def test_toolbar_prefix_is_removed(self):
        raw = "읽기모드 다크모드 폰트크기 가 가 가 가 북마크 공유하기 프린트 기사반응 서울 성북구가 독서문화 활성화를 위한 협약을 체결했다."
        cleaned = extractor.clean_summary_text(raw)
        self.assertEqual(cleaned, "서울 성북구가 독서문화 활성화를 위한 협약을 체결했다.")

    def test_mojibake_is_rejected(self):
        broken = "M¦®mH0D HXD m¤nH ¤ÃÂ¦ mH0D HXD ¤¦ÃÂ mH0D"
        self.assertTrue(extractor.looks_mojibake(broken))

    def test_meta_summary_falls_back_when_toolbar_only(self):
        soup = BeautifulSoup('<meta name="description" content="읽기모드 다크모드 폰트크기 가 가 가 북마크 공유하기 프린트">', "html.parser")
        self.assertIsNone(extractor.extract_summary(soup))


if __name__ == "__main__":
    unittest.main()
