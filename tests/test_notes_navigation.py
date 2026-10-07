"""Developer notes are an original-document link; admin API retains patch history."""
import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
NOTE_URL = 'https://github.com/kksh0379/ncfoundation-collector/blob/claude/quirky-euler-agfmp/DEVNOTE.md'


class NotesNavigationTests(unittest.TestCase):
    def notes(self, admin):
        import os
        tree = ast.parse((ROOT / 'app.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'notes')
        fn.decorator_list = []
        scope = dict(_admin_ok=lambda: admin, jsonify=lambda data: data, os=os,
                     __file__=str(ROOT / 'app.py'))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'app.py', 'exec'), scope)
        return scope['notes']()

    def test_launcher_opens_original_without_an_admin_modal(self):
        env = Environment(loader=FileSystemLoader(ROOT / 'templates'), autoescape=True)
        html = env.get_template('launcher.html').render(services=[], year=2026,
                                                       url_for=lambda name, **kw: '/' + name)
        soup = BeautifulSoup(html, 'html.parser')
        links = soup.find_all('a', href=NOTE_URL)
        self.assertEqual(len(links), 1)
        self.assertIn('개발자 노트 원문', links[0].get_text())
        self.assertEqual(links[0]['target'], '_blank')
        self.assertIn('noopener', links[0]['rel'])
        self.assertFalse(soup.select('#notes-modal'))

    def test_admin_receives_only_the_actual_patch_history(self):
        result = self.notes(True)
        self.assertEqual(result, {'changelog': (ROOT / 'CHANGELOG.md').read_text()})
        soup = BeautifulSoup((ROOT / 'templates/index.html').read_text(), 'html.parser')
        modal = soup.select_one('#notes-modal')
        self.assertIn('패치내역', modal.get_text())
        self.assertNotIn('개발노트', modal.get_text())
        self.assertFalse(modal.select('[data-notes="devnote"]'))

    def test_unauthorized_request_reads_no_documents(self):
        with patch('builtins.open', side_effect=AssertionError('must not read document')):
            self.assertEqual(self.notes(False), ({'error': 'unauthorized'}, 401))


if __name__ == '__main__':
    unittest.main()
