import json
import ast
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from collector import db


class ScrapInsertTests(unittest.TestCase):
    def test_scrap_route_returns_authoritative_existing_groups(self):
        tree = ast.parse(Path("app.py").read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "scrap")
        function.decorator_list = []
        stored = {"key": "article", "groups": ["kept"]}
        database = SimpleNamespace(user_scrap_add=lambda *args: {"snapshot": json.dumps(stored), "ts": 100})
        scope = {"db": database, "json": json, "time": SimpleNamespace(time=lambda: 1),
                 "_current_user": lambda: "alice", "_ensure_db": lambda: True,
                 "jsonify": lambda value: value,
                 "request": SimpleNamespace(get_json=lambda **kwargs: {"op": "add", "key": "article", "item": {"key": "article"}})}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "app.py", "exec"), scope)
        response = scope["scrap"]()
        self.assertTrue(response["ok"])
        self.assertEqual(response["item"]["groups"], ["kept"])
        self.assertEqual(response["item"]["ts"], 100)

    def test_early_add_is_idempotent_and_preserves_groups_and_time(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "test.db")
            with patch.object(db, "_PG", False), patch.object(db, "DB_PATH", path):
                with db.get_conn() as conn:
                    conn.execute("CREATE TABLE user_state (username TEXT, ukey TEXT, kind TEXT, snapshot TEXT, ts INTEGER, PRIMARY KEY(username, ukey, kind))")
                original = {"key": "article", "groups": ["group-one"], "title": "Saved"}
                db.user_scrap_add("alice", "article", json.dumps(original), 100)
                actual = db.user_scrap_add("alice", "article", json.dumps({"key": "article", "groups": []}), 200)
                self.assertEqual(json.loads(actual["snapshot"]), original)
                self.assertEqual(actual["ts"], 100)
                db.user_state_delete("alice", "article", "scrap")
                added = db.user_scrap_add("alice", "article", json.dumps({"key": "article"}), 300)
                self.assertEqual(added["ts"], 300)
                self.assertEqual(len(db.user_state_bundle("alice")["scrap"]), 1)
                self.assertEqual(db.user_state_bundle("bob")["scrap"], [])


if __name__ == "__main__":
    unittest.main()
