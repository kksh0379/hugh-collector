import os
import unittest
from unittest.mock import patch, Mock
from flask import Flask
from collector import finance


class FinanceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        app = Flask(__name__)
        app.register_blueprint(finance.bp)
        self.client = app.test_client()

    def tearDown(self):
        self.env.stop()

    def test_missing_keys_are_not_real_values(self):
        row = finance.indicator(finance.INDICATORS[0])
        self.assertEqual(row['mode'], 'demo')
        self.assertIsNone(row['date'])
        self.assertIsNone(row['change'])
        result = self.client.post('/api/finance/business-status', json={'number': '123-45-67890'})
        self.assertEqual(result.json['mode'], 'unconfigured')
        self.assertEqual(result.headers['Cache-Control'], 'no-store')
        self.assertNotIn('계속사업자', str(result.json))
        self.assertEqual(finance.disclosures('')['mode'], 'unconfigured')

    def test_invalid_business_input_never_calls_provider(self):
        with patch.object(finance.requests, 'post') as post:
            for value in ('abc1234567890', '123', '<script>', ['1234567890'], None):
                self.assertEqual(self.client.post('/api/finance/business-status', json={'number':value}).status_code, 400)
            self.assertEqual(self.client.post('/api/finance/business-status', json=[]).status_code, 400)
            post.assert_not_called()

    def test_business_success_and_provider_error(self):
        os.environ['NTS_API_KEY'] = 'test-secret'
        response = Mock()
        response.json.return_value = {'status_code':'OK', 'data':[{'b_no':'1234567890','b_stt':'폐업자','tax_type':'일반과세자','end_dt':'20250101'}]}
        with patch.object(finance.requests, 'post', return_value=response) as post:
            result = self.client.post('/api/finance/business-status', json={'number':'1234567890'})
            self.assertEqual(result.json['status'], '폐업자')
            self.assertNotIn('test-secret', result.get_data(as_text=True))
            self.assertEqual(post.call_args.kwargs['json'], {'b_no':['1234567890']})
            response.json.return_value = {'status_code':'ERROR'}
            self.assertEqual(self.client.post('/api/finance/business-status', json={'number':'1234567890'}).json['mode'], 'unavailable')

    def test_business_timeout_not_closed_business(self):
        os.environ['NTS_API_KEY']='test'
        with patch.object(finance.requests,'post',side_effect=TimeoutError):
            result=self.client.post('/api/finance/business-status',json={'number':'1234567890'}).json
            self.assertEqual(result['mode'],'unavailable')
            self.assertNotIn('폐업자',str(result))

    def test_rss_and_atom_strip_html_and_reject_unsafe_links(self):
        rss=b'<rss><channel><item><title>&lt;b&gt;Tax&lt;/b&gt;</title><description>&lt;p&gt;Summary&lt;/p&gt;</description><link>https://example.org/a</link><pubDate>Fri, 02 Oct 2026 01:00:00 GMT</pubDate></item><item><title>Bad</title><link>javascript:alert(1)</link></item></channel></rss>'
        rows=finance.parse_feed(rss,finance.SOURCES[0])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['title'],'Tax')
        self.assertEqual(rows[0]['description'],'Summary')
        atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Guide</title><link href="https://example.org/b"/><summary>Text</summary><updated>2026-10-02</updated></entry></feed>'
        self.assertEqual(finance.parse_feed(atom,finance.SOURCES[0])[0]['url'],'https://example.org/b')
        with self.assertRaises(ValueError):
            finance.parse_feed(b'<html>not rss</html>',finance.SOURCES[0])

    def test_xml_external_entity_is_not_resolved(self):
        xml=b'<!DOCTYPE rss [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><rss><channel><item><title>&xxe;</title><link>https://example.org</link></item></channel></rss>'
        self.assertNotIn('root:',str(finance.parse_feed(xml,finance.SOURCES[0])))

    def test_ecos_sorted_observations_and_change(self):
        os.environ['ECOS_API_KEY']='test'
        payload={'StatisticSearch':{'row':[{'TIME':'20261002','DATA_VALUE':'1322.5'},{'TIME':'20261001','DATA_VALUE':'1320'}]}}
        with patch.object(finance,'get_json',return_value=payload):
            row=finance.indicator(finance.INDICATORS[0])
            self.assertEqual((row['value'],row['change'],row['date'],row['mode']),(1322.5,2.5,'20261002','live'))

    def test_ecos_failure_never_returns_demo_as_live(self):
        os.environ['ECOS_API_KEY']='test'
        with patch.object(finance,'get_json',side_effect=TimeoutError):
            row=finance.indicator(finance.INDICATORS[0])
            self.assertIsNone(row['value'])
            self.assertEqual(row['mode'],'unavailable')

    def test_dart_filter_empty_and_error(self):
        self.assertEqual(self.client.get('/api/finance/disclosures?corp_code=123').status_code,400)
        os.environ['DART_API_KEY']='secret'
        with patch.object(finance,'get_json',return_value={'status':'013'}) as get:
            self.assertEqual(finance.disclosures('00126380')['items'],[])
            self.assertEqual(get.call_args.kwargs['params']['corp_code'],'00126380')
        with patch.object(finance,'get_json',return_value={'status':'010'}):
            self.assertEqual(finance.disclosures('')['mode'],'unavailable')
        payload={'status':'000','list':[{'corp_name':'회사','report_nm':'보고서','rcept_dt':'20261002','rcept_no':'20261002000001'}]}
        with patch.object(finance,'get_json',return_value=payload):
            self.assertTrue(finance.disclosures('')['items'][0]['url'].endswith('20261002000001'))

    def test_dashboard_partial_sources_and_no_unverified_deadlines(self):
        with patch.object(finance,'collect_source',return_value=([],{'name':'source','mode':'unavailable'})):
            result=finance.dashboard()
            self.assertEqual(len(result['indicators']),3)
            self.assertEqual(len(result['sources']),8)
            self.assertEqual(result['calendar']['events'],[])

    def test_cold_dashboard_is_nonblocking(self):
        with patch.object(finance.cache,'get',return_value=None) as get:
            result=self.client.get('/api/finance/dashboard')
            self.assertEqual(result.status_code,200)
            self.assertTrue(result.json['pending'])
            self.assertEqual(get.call_args.kwargs['wait'],0)

    def test_bizinfo_key_is_server_side(self):
        os.environ['BIZINFO_API_KEY']='secret'
        with patch.object(finance.requests,'get',side_effect=TimeoutError) as get:
            rows,status=finance.collect_source(finance.SOURCES[2])
            self.assertIn('crtfcKey=secret',get.call_args.args[0])
            self.assertNotIn('secret',str(status))
            self.assertEqual(status['mode'],'unavailable')

if __name__ == '__main__':
    unittest.main()
