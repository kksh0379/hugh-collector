import io
import unittest
from unittest.mock import patch
import requests
from collector import fetcher


def response(body,content_type='text/html'):
    result=requests.Response();result.status_code=200
    result.headers['content-type']=content_type
    result.url='https://example.test/article'
    result.raw=io.BytesIO(body)
    result.raw.release_conn=result.raw.close
    return result


class FetcherBudgetTests(unittest.TestCase):
    def test_streamed_body_keeps_text_json_and_closes_connection(self):
        result=response('{"title":"한글"}'.encode(),'application/json')
        with patch.object(fetcher.requests,'get',return_value=result) as get:
            loaded=fetcher.get(result.url)
        self.assertEqual(loaded.json(),{'title':'한글'})
        self.assertIn('한글',loaded.text);self.assertTrue(result.raw.closed)
        self.assertTrue(get.call_args.kwargs['stream'])

    def test_oversized_page_is_rejected_instead_of_partially_parsed(self):
        result=response(b'x'*2048)
        with patch.object(fetcher,'MAX_RESPONSE_BYTES',1024),patch.object(fetcher.requests,'get',return_value=result):
            with self.assertRaises(fetcher.ResponseTooLarge):fetcher.get(result.url)
        self.assertTrue(result.raw.closed);self.assertFalse(result._content)

    def test_valid_utf8_skips_expensive_charset_detection(self):
        result=response('<article>기사 본문입니다.</article>'.encode())
        fetcher._read_bounded(result)
        with patch.object(requests.models.chardet,'detect',side_effect=AssertionError('must not detect')):
            self.assertEqual(fetcher._response_encoding(result),'utf-8')

    def test_declared_legacy_korean_encoding_is_preserved(self):
        body='<meta charset="euc-kr"><article>한글 본문</article>'
        result=response(body.encode('euc-kr'));fetcher._read_bounded(result)
        result.encoding=fetcher._response_encoding(result)
        self.assertEqual(result.text,body)

    def test_unknown_legacy_detection_uses_bounded_sample(self):
        result=response(('한글 본문입니다. '*10000).encode('cp949'))
        fetcher._read_bounded(result)
        with patch.object(requests.models.chardet,'detect',return_value={'encoding':'cp949'}) as detector:
            self.assertEqual(fetcher._response_encoding(result),'cp949')
        self.assertEqual(len(detector.call_args.args[0]),65536)


if __name__=='__main__':unittest.main()
