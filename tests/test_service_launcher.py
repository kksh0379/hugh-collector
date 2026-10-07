"""Launcher routing compatibility without booting collectors or connecting to DB."""
import ast
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from collector.service_registry import SERVICES

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def call_launcher(self, args=None, query=b''):
        tree = ast.parse((ROOT / 'app.py').read_text())
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'launcher')
        fn.decorator_list = []
        scope = dict(request=SimpleNamespace(args=args or {}, query_string=query), SERVICES=SERVICES,
                     datetime=datetime, KST=timezone(timedelta(hours=9)), url_for=lambda name:'/hscope',
                     redirect=lambda location, code:(location,code),
                     render_template=lambda name, **values:(name,values))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'app.py', 'exec'), scope)
        return scope['launcher']()

    def test_legacy_host_redirect_preserves_service_path_and_query(self):
        tree = ast.parse((ROOT / 'app.py').read_text())
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_start_request_timer')
        fn.decorator_list = []
        for path, query, expected in [('/', b'', '/hscope'), ('/hscope', b'video=3217', '/hscope?video=3217')]:
            scope = dict(g=SimpleNamespace(), time=SimpleNamespace(perf_counter=lambda:0),
                         request=SimpleNamespace(host='ncfoundation-collector.onrender.com', method='GET', path=path, query_string=query),
                         redirect=lambda location, code:(location, code), _start_worker_jobs=lambda:None, _start_read_prewarm=lambda:None)
            exec(compile(ast.Module(body=[fn], type_ignores=[]), 'app.py', 'exec'), scope)
            self.assertEqual(scope['_start_request_timer'](), ('https://hscope.onrender.com' + expected, 308))
        scope['request'].host = 'hscope.onrender.com'
        self.assertIsNone(scope['_start_request_timer']())

    def test_pwa_shell_preserves_query_without_loading_collector_page(self):
        from werkzeug.datastructures import MultiDict
        tree = ast.parse((ROOT / 'app.py').read_text())
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'index')
        fn.decorator_list = []
        scope = dict(request=SimpleNamespace(args=MultiDict([('app','1'),('video','3217'),('series','1')])),
                     url_for=lambda name:'/hscope', render_template=lambda name, **values:(name,values))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'app.py', 'exec'), scope)
        template, values = scope['index']()
        self.assertEqual(template, 'pwa_shell.html')
        self.assertEqual(values['frame_url'], '/hscope?video=3217&series=1&app_frame=1')

    def test_root_opens_service_launcher(self):
        template, values = self.call_launcher()
        self.assertEqual(template, 'launcher.html')
        self.assertEqual(values['services'][0]['href'], '/hscope')

    def test_legacy_video_bookmark_preserves_query(self):
        query=b'video=3217&series=1&episode=1179'
        self.assertEqual(self.call_launcher({'video':'3217'},query),('/hscope?'+query.decode(),302))

    def test_hscope_route_and_existing_api_routes_are_kept(self):
        tree = ast.parse((ROOT / 'app.py').read_text())
        index = next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='index')
        self.assertEqual(index.decorator_list[0].args[0].value,'/hscope')
        source = (ROOT / 'app.py').read_text()
        self.assertIn('@app.get("/api/me")',source)
        self.assertIn('@app.get("/api/news")',source)

    def test_registry_has_unique_local_services_or_authorized_documents(self):
        self.assertEqual(len({item['id'] for item in SERVICES}),len(SERVICES))
        for item in SERVICES:
            if item.get('kind') == 'document':
                url = urlsplit(item['href'])
                self.assertEqual(url.scheme, '')
                self.assertEqual(url.path, '/maeum-record')
                self.assertEqual(item['badge'], '기획서')
            else:
                self.assertTrue(item['href'].startswith('/') and not item['href'].startswith('//'))


if __name__ == '__main__': unittest.main()
