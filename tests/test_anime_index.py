import unittest
from tools.refresh_anime_catalog import parse_index


class AnimeIndexTests(unittest.TestCase):
    def test_list_card_metadata_and_last_page(self):
        html = '''<div class="vod-item"><a href="/ani/3217/"><div data-original="/poster.jpg"></div></a>
        <h3 class="vod-item-title"><a href="/ani/3217/"><strong> 원피스 </strong></a></h3>
        <div class="vod-item-desc"><p>1179/1179 .</p></div></div>
        <a href="/list/2/page/198/">198</a>'''
        rows, pages = parse_index(html)
        self.assertEqual(pages, 198)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['title'], '원피스')
        self.assertEqual(rows[0]['id'], '3217')
        self.assertEqual(rows[0]['image'], 'https://linkani.tv/poster.jpg')
        self.assertEqual(rows[0]['description'], '1179/1179')

    def test_non_work_links_are_not_imported(self):
        html = '<div class="vod-item"><h3 class="vod-item-title"><a href="https://evil.example/ani/3217/">wrong</a></h3></div>'
        self.assertEqual(parse_index(html)[0], [])


if __name__ == '__main__':
    unittest.main()
