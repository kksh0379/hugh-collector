"""Exercise the actual plan route with a gate, without DB or collectors."""
import ast
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask, render_template
from collector.maeum_gate import register_maeum_gate

ROOT = Path(__file__).resolve().parents[1]


class MaeumGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        static = Path(self.temp.name)
        for name in ("maeum-record-v01.pdf", "maeum-record-v01.pptx",
                     "maeum-record-pages/page-01.jpg"):
            target = static / "plans" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"private document")
        self.app = Flask(__name__, template_folder=str(ROOT / "templates"),
                         static_folder=str(static), static_url_path="/static")
        self.app.config.update(TESTING=True, SECRET_KEY="test")
        register_maeum_gate(self.app)
        tree = ast.parse((ROOT / "app.py").read_text())
        route = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name == "maeum_record_plan")
        scope = {"app": self.app, "render_template": render_template}
        exec(compile(ast.Module(body=[route], type_ignores=[]), "app.py", "exec"), scope)
        self.app.add_url_rule("/", "launcher", lambda: "launcher")
        self.app.add_url_rule("/hscope", "index", lambda: "hscope")
        self.client = self.app.test_client()
        self.addCleanup(self.temp.cleanup)

    def unlock(self, password="1234", base_url="http://localhost"):
        page = self.client.get("/maeum-record", base_url=base_url)
        challenge = re.search(r'name="challenge" value="([^"]+)"', page.text)[1]
        return self.client.post("/maeum-record", data={"password": password,
                                                     "challenge": challenge}, base_url=base_url)

    def test_direct_entry_requires_password_and_contains_no_plan(self):
        r = self.client.get("/maeum-record")
        self.assertEqual(r.status_code, 200)
        self.assertIn('type="password"', r.text)
        self.assertNotIn("maeum-record-v01.pdf", r.text)
        self.assertIn("no-store", r.headers["Cache-Control"])

    def test_wrong_password_does_not_unlock_including_unicode(self):
        for value in ("0000", "틀림", ""):
            self.assertEqual(self.unlock(value).status_code, 401)
        self.assertIn('type="password"', self.client.get("/maeum-record").text)

    def test_correct_password_opens_actual_plan_and_all_assets(self):
        r = self.unlock()
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["Location"], "/maeum-record")
        page = self.client.get("/maeum-record")
        self.assertIn("마음기록 기획서", page.text)
        self.assertIn("maeum-record-v01.pdf", page.text)
        for path in ("maeum-record-v01.pdf", "maeum-record-v01.pptx",
                     "maeum-record-pages/page-01.jpg"):
            response = self.client.get("/static/plans/" + path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response.headers["Cache-Control"])
            response.close()

    def test_anonymous_assets_are_blocked_even_with_encoded_path(self):
        for path in ("maeum-record-v01.pdf", "maeum-record-v01.pptx",
                     "maeum-record-pages/page-01.jpg", "%6daeum-record-v01.pdf",
                     "other/../maeum-record-v01.pdf"):
            self.assertEqual(self.client.get("/static/plans/" + path).status_code, 403)

    def test_tampered_cookie_is_rejected(self):
        self.client.set_cookie("maeum_access", "maeum-record.fake")
        self.assertEqual(self.client.get("/static/plans/maeum-record-v01.pdf").status_code, 403)

    def test_access_expires_after_thirty_minutes(self):
        with patch("itsdangerous.timed.TimestampSigner.get_timestamp", return_value=100):
            self.unlock()
        with patch("itsdangerous.timed.TimestampSigner.get_timestamp", return_value=1901):
            self.assertEqual(self.client.get("/static/plans/maeum-record-v01.pdf").status_code, 403)

    def test_post_without_valid_form_is_rejected(self):
        r = self.client.post("/maeum-record", data={"password": "1234"})
        self.assertEqual(r.status_code, 400)

    def test_https_cookie_is_secure_and_other_services_stay_available(self):
        r = self.unlock(base_url="https://localhost")
        self.assertIn("Secure", r.headers.getlist("Set-Cookie")[0])
        self.assertIn("HttpOnly", r.headers.getlist("Set-Cookie")[0])
        self.assertEqual(self.client.get("/").text, "launcher")
        self.assertEqual(self.client.get("/hscope").text, "hscope")


if __name__ == "__main__":
    unittest.main()
