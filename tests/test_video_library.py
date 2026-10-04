import unittest
from unittest.mock import patch

import requests
from flask import Flask
from collector.video_library import bp, parse_page


class VideoLibraryTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(bp)
        self.client = app.test_client()

    def test_metadata_groups_actual_links_and_rejects_other_hosts_and_titles(self):
        html = '''<meta property="og:title" content="강철의 연금술사 8화">
        <a href="/watch/19240/a1/k9/">next</a><a href="/watch/19240/a1/k9/">9화</a>
        <a href="/watch/19240/a2/k1/">1화</a>
        <a href="https://evil.example/watch/19240/a3/k1/">wrong host</a>
        <a href="/watch/999/a1/k1/">wrong title</a>'''
        result = parse_page(html, '19240', '1', '8')
        self.assertEqual(result['title'], '강철의 연금술사')
        self.assertEqual(result['series'], [{'id': 1, 'episodes': [8, 9]}, {'id': 2, 'episodes': [1]}])

    @patch('collector.video_library.load_catalog')
    def test_invalid_coordinates_never_make_network_requests(self, load):
        for query in ['id=../../x', 'id=0', 'series=1%2F..', 'episode=-1', 'id=https://evil.example']:
            self.assertEqual(self.client.get('/api/videos/catalog?' + query).status_code, 400)
        load.assert_not_called()

    def test_known_titles_do_not_change_to_episode_subtitles(self):
        result = parse_page('<meta property="og:title" content="원피스 나는 루피! 해적왕이 될 남자다! 1화">', '3217', '1', '1')
        self.assertEqual(result['title'], '원피스')

    @patch('collector.video_library.load_catalog', side_effect=requests.Timeout)
    def test_source_failure_has_retryable_error(self, load):
        response = self.client.get('/api/videos/catalog?id=555')
        self.assertEqual(response.status_code, 502)
        self.assertIn('error', response.json)

    @patch('collector.video_library.load_catalog', side_effect=requests.Timeout)
    def test_verified_snapshot_remains_available_on_source_timeout(self, load):
        response = self.client.get('/api/videos/catalog')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['stale'])
        self.assertEqual(response.json['series'][0]['episodes'], list(range(1, 69)))

    @patch('collector.video_library.load_catalog', return_value={'id': '19240', 'series': []})
    def test_requested_coordinates_pass_to_catalog(self, load):
        self.assertEqual(self.client.get('/api/videos/catalog?id=19240&series=2&episode=3').status_code, 200)
        self.assertEqual(load.call_args.args[:3], ('19240', '2', '3'))


if __name__ == '__main__':
    unittest.main()
