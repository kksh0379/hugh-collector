import unittest
from unittest.mock import patch

import requests
from flask import Flask
from collector.video_library import bp, parse_page, parse_playback


class VideoLibraryTests(unittest.TestCase):
    def setUp(self):
        from collector.video_library import _watch_response
        _watch_response.cache_clear()
        app = Flask(__name__)
        app.register_blueprint(bp)
        self.client = app.test_client()

    def test_playback_extracts_video_and_subtitles_only(self):
        data = parse_playback('<video id="linktv-video"><source src="https://aniplayer1.site/x/index.m3u8?expires=1&amp;md5=abc"><track src="https://aniplayer1.site/x/sub.vtt" srclang="ko"><track src="https://evil.example/sub.vtt"></video>')
        self.assertEqual(data['src'], 'https://aniplayer1.site/x/index.m3u8?expires=1&md5=abc')
        self.assertEqual(len(data['tracks']), 1)
        self.assertIsNone(parse_playback('<video id="linktv-video" src="https://evil.example/file"></video>'))

    def test_script_player_json_extracts_media_and_subtitles(self):
        html = r'''<script>var player_aaaa={"encrypt":0,"actual_url":"https://aniplayer1.site/h/steel/index.m3u8?md5=test\u0026expires=123","subtitle_url":"https://aniplayer1.site/s/steel/sub.vtt"};</script>'''
        result = parse_playback(html)
        self.assertEqual(result['src'], 'https://aniplayer1.site/h/steel/index.m3u8?md5=test&expires=123')
        self.assertEqual(result['tracks'], [{'src':'https://aniplayer1.site/s/steel/sub.vtt', 'language':'ko', 'label':'한국어'}])
        self.assertIsNone(parse_playback(html.replace('aniplayer1.site/h/', 'evil.example/h/')))
        self.assertEqual(parse_playback(html.replace('aniplayer1.site/s/', 'evil.example/s/'))['tracks'], [])

    def test_script_player_is_json_only_and_rejects_encrypted_urls(self):
        for value in ['alert(1)', '{url: "https://aniplayer1.site/a.m3u8"}', '{"encrypt":1,"url":"https://aniplayer1.site/a.m3u8"}']:
            self.assertIsNone(parse_playback('<script>var player_aaaa=' + value + ';</script>'))

    @patch('collector.video_library.requests.get')
    def test_script_player_route_is_available_not_missing(self, get):
        from collector.video_library import _watch_response
        _watch_response.cache_clear()
        get.return_value.status_code = 200
        get.return_value.text = '<script>var player_aaaa={"url":"https://aniplayer1.site/steel.m3u8"};</script>'
        result = self.client.get('/api/videos/playback?id=19240&series=1&episode=8&probe=1')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['src'], 'https://aniplayer1.site/steel.m3u8')
        _watch_response.cache_clear()

    @patch('collector.video_library.requests.get')
    def test_unsupported_script_player_is_not_reported_deleted(self, get):
        from collector.video_library import _watch_response
        _watch_response.cache_clear()
        get.return_value.status_code = 200
        get.return_value.text = '<script>var player_aaaa={"url":"https://other.example/video"};</script>'
        result = self.client.get('/api/videos/playback?id=19240&series=1&episode=8')
        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.json['code'], 'unsupported_player')
        _watch_response.cache_clear()

    @patch('collector.video_library.requests.get')
    def test_playback_validates_coordinates_and_never_caches_expiring_urls(self, get):
        self.assertEqual(self.client.get('/api/videos/playback?id=../x').status_code, 400)
        get.assert_not_called()
        get.return_value.status_code = 200
        get.return_value.text = '<video id="linktv-video" src="https://aniplayer1.site/a.m3u8"></video>'
        result = self.client.get('/api/videos/playback?id=19240&series=1&episode=2')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers['Cache-Control'], 'no-store')
        self.assertEqual(get.call_args.args[0], 'https://linkani.tv/watch/19240/a1/k2/')

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

    @patch('collector.video_library.load_catalog', return_value={'id': '19240', 'series': [{'id': 2, 'episodes': [3]}]})
    def test_requested_coordinates_pass_to_catalog(self, load):
        self.assertEqual(self.client.get('/api/videos/catalog?id=19240&series=2&episode=3').status_code, 200)
        self.assertEqual(load.call_args.args[:3], ('19240', '2', '3'))

    def test_detail_pages_do_not_invent_unreleased_episodes(self):
        self.assertEqual(parse_page('<meta property="og:title" content="미방영 작품">', '123', '1', '1', include_requested=False)['series'], [])

    def test_detail_title_drops_site_branding_without_removing_movie_name(self):
        result = parse_page('<meta property="og:title" content="나루토 - 극장판2 - Anime - Linkkf 애니 TV (자막 - 더빙)">', '430', '1', '1')
        self.assertEqual(result['title'], '나루토 - 극장판2')

    @patch('collector.video_library.load_catalog', return_value={'id': '123', 'series': []})
    def test_unreleased_title_returns_clear_message(self, load):
        response = self.client.get('/api/videos/catalog?id=123')
        self.assertEqual(response.status_code, 409)
        self.assertIn('아직', response.json['error'])


if __name__ == '__main__':
    unittest.main()
