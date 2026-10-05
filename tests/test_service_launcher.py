"""Launcher routing compatibility without booting collectors or connecting to DB."""
import ast
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
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

    def test_registry_has_unique_local_service_paths(self):
        self.assertEqual(len({item['id'] for item in SERVICES}),len(SERVICES))
        self.assertTrue(all(item['href'].startswith('/') and not item['href'].startswith('//') for item in SERVICES))


if __name__ == '__main__': unittest.main()
