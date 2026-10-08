import ast
import json
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]

class FeatureVisibilityTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((ROOT / 'app.py').read_text())
        keys = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_FEATURE_KEYS' for t in n.targets))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_load_features')
        self.scope = {'json': json}
        exec(compile(ast.Module(body=[keys, fn], type_ignores=[]), 'app.py', 'exec'), self.scope)

    def test_old_saved_choices_survive_and_new_menus_default_on(self):
        flags = self.scope['_load_features'](metadata={'feature_flags': json.dumps({'news': False, 'boards': False, 'cat': False})})
        self.assertFalse(flags['news'])
        self.assertFalse(flags['boards'])
        self.assertTrue(flags['cat'])
        for key in ['food', 'videos', 'finance']:
            self.assertTrue(flags[key])

    def test_settings_have_every_server_key_once(self):
        soup = BeautifulSoup((ROOT / 'templates/index.html').read_text(), 'html.parser')
        keys = [e['data-feat'] for e in soup.select('#features-modal [data-feat]')]
        self.assertCountEqual(keys, self.scope['_FEATURE_KEYS'])
        self.assertEqual(len(keys), len(set(keys)))

    def test_unreadable_saved_flags_keep_service_available(self):
        self.assertTrue(all(self.scope['_load_features'](metadata={'feature_flags': '{broken'}).values()))

if __name__ == '__main__':
    unittest.main()
