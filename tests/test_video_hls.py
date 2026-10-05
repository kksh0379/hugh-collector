import unittest
from unittest.mock import patch
from types import SimpleNamespace
from urllib.parse import urlparse

from flask import Flask
from collector.video_library import bp
from collector import video_hls


VTT = 'WEBVTT\n\n00:00:05.000 --> 00:00:08.000\n한국어 자막\n\n00:00:12.000 --> 00:00:14.000\n다음 자막\n'
DATA = {'src': 'https://aniplayer1.site/video/index.m3u8', 'tracks': [{'src': 'https://aniplayer1.site/sub.vtt', 'language': 'ko', 'label': '한국어'}]}


class VideoHLSTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'test-key'
        self.app.register_blueprint(bp)
        self.client = self.app.test_client()
        with self.app.app_context():
            self.token = video_hls.encode_playback(DATA)

    def test_signed_token_rejects_tampering_before_fetch(self):
        with patch.object(video_hls, 'load_text') as load:
            self.assertEqual(self.client.get('/api/videos/native.m3u8?token=invalid').status_code, 502)
        load.assert_not_called()

    def test_media_master_contains_subtitle_rendition_on_https(self):
        with patch.object(video_hls, 'load_text', return_value='#EXTM3U\n#EXTINF:6,\nseg.ts\n#EXT-X-ENDLIST'):
            result = self.client.get('/api/videos/native.m3u8?token=' + self.token)
        text = result.get_data(as_text=True)
        self.assertIn('TYPE=SUBTITLES', text)
        self.assertIn('DEFAULT=YES', text)
        self.assertIn('https://localhost/api/videos/subtitles.m3u8?', text)
        self.assertIn(DATA['src'], text)
        self.assertEqual(result.headers['Cache-Control'], 'no-store')

    def test_existing_variants_and_keys_stay_absolute(self):
        with self.app.test_request_context():
            text = video_hls.master_playlist('#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="a",URI="audio.m3u8"\n#EXT-X-STREAM-INF:BANDWIDTH=1234,SUBTITLES="old",AUDIO="a"\n720p/index.m3u8\n', DATA['src'], DATA['tracks'], self.token)
        self.assertIn('https://aniplayer1.site/video/720p/index.m3u8', text)
        self.assertIn('https://aniplayer1.site/video/audio.m3u8', text)
        self.assertIn('SUBTITLES="hscope-captions"', text)
        self.assertNotIn('SUBTITLES="old"', text)

    def test_cue_crossing_segment_boundary_is_in_both_segments(self):
        self.assertIn('한국어 자막', video_hls.subtitle_segment(VTT, 0))
        self.assertIn('한국어 자막', video_hls.subtitle_segment(VTT, 1))
        self.assertNotIn('다음 자막', video_hls.subtitle_segment(VTT, 1))
        self.assertIn('다음 자막', video_hls.subtitle_segment(VTT, 2))

    def test_subtitle_playlist_and_segments_can_be_fetched_without_session_by_tv(self):
        with patch.object(video_hls, 'load_text', return_value=VTT):
            playlist = self.client.get('/api/videos/subtitles.m3u8?token=' + self.token).get_data(as_text=True)
            urls = [line for line in playlist.splitlines() if line.startswith('https://')]
            self.assertEqual(len(urls), 3)
            url = urlparse(urls[1])
            response = self.client.get(url.path + '?' + url.query)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/vtt')
        self.assertIn('X-TIMESTAMP-MAP', response.text)
        self.assertIn('한국어 자막', response.text)

    def test_original_link_is_admin_only_and_coordinates_are_validated(self):
        path = '/api/videos/original?id=3217&series=1&episode=1'
        self.assertEqual(self.client.get(path).status_code, 403)
        with self.client.session_transaction() as session:
            session['admin'] = True
        result = self.client.get(path)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.location, 'https://linkani.tv/watch/3217/a1/k1/')
        self.assertEqual(self.client.get('/api/videos/original?id=../').status_code, 400)

    def test_deleted_episode_reports_missing_instead_of_fallback_player(self):
        with patch('collector.video_library.requests.get', return_value=SimpleNamespace(status_code=404)):
            result = self.client.get('/api/videos/playback?id=3217&series=1&episode=1')
        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.json['code'], 'video_missing')

    def test_missing_video_on_valid_source_page_is_reported(self):
        response = SimpleNamespace(status_code=200, text='<html><title>원피스 1화</title></html>', raise_for_status=lambda: None)
        with patch('collector.video_library.requests.get', return_value=response):
            result = self.client.get('/api/videos/playback?id=3217&series=1&episode=1')
        self.assertEqual(result.json['code'], 'video_missing')

    def test_tracks_generate_native_hls_url(self):
        response = SimpleNamespace(status_code=200, text='<video id="linktv-video" src="https://aniplayer1.site/a.m3u8"><track src="https://aniplayer1.site/sub.vtt"></video>', raise_for_status=lambda: None)
        with patch('collector.video_library.requests.get', return_value=response):
            result = self.client.get('/api/videos/playback?id=3217&series=1&episode=1')
        self.assertTrue(result.json['native_src'].startswith('https://localhost/api/videos/native.m3u8?'))

    def test_media_hosts_and_subtitle_format_are_restricted(self):
        for url in ['http://aniplayer1.site/a', 'https://localhost/a', 'https://aniplayer1.site:123/a', 'https://aniplayer1.site:abc/a']:
            self.assertFalse(video_hls.safe_media_url(url))
        with self.assertRaises(ValueError):
            video_hls.vtt_cues('<html>error</html>')


if __name__ == '__main__':
    unittest.main()
