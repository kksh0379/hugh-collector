import sqlite3
import unittest
from collector.lunch_history import import_history, grouped, AUTHOR

class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE lunch_location(id INTEGER PRIMARY KEY, address TEXT);
        INSERT INTO lunch_location VALUES(1,'서울 종로구 이화장길 100');
        CREATE TABLE lunch_restaurant(id INTEGER PRIMARY KEY,loc_id INTEGER,source TEXT,place_id TEXT,name TEXT,cat_norm TEXT,place_url TEXT,excluded INTEGER,first_seen TEXT,last_checked TEXT);
        CREATE TABLE lunch_review(id INTEGER PRIMARY KEY,restaurant_id INTEGER,username TEXT,rating INTEGER,comment TEXT,created_at TEXT);
        CREATE TABLE lunch_visit(id INTEGER PRIMARY KEY,restaurant_id INTEGER,username TEXT,visited_at TEXT);
        INSERT INTO lunch_restaurant(id,loc_id,name,place_url) VALUES(99,1,'순대실록 대학로점','existing-map');
        INSERT INTO lunch_review(restaurant_id,username,rating,comment) VALUES(99,'실제 이용자',5,'기존 후기');
        ''')
    def test_import_preserves_existing_data_and_is_idempotent(self):
        count = import_history(self.conn,lambda s:s,'2026-10-02')
        self.assertEqual(count,len(grouped()))
        self.assertEqual(import_history(self.conn,lambda s:s,'2026-10-03'),0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM lunch_review WHERE username=?',(AUTHOR,)).fetchone()[0],count)
        self.assertEqual(self.conn.execute("SELECT place_url FROM lunch_restaurant WHERE id=99").fetchone()[0],'existing-map')
        self.assertEqual(self.conn.execute("SELECT comment FROM lunch_review WHERE username='실제 이용자'").fetchone()[0],'기존 후기')
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM lunch_restaurant WHERE name LIKE '순대실록%'").fetchone()[0],1)
    def test_dates_labels_and_conflicting_link(self):
        import_history(self.conn,lambda s:s,'2026-10-02')
        self.assertEqual(self.conn.execute("SELECT place_url FROM lunch_restaurant WHERE name='제로밥상'").fetchone()[0],'')
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM lunch_visit WHERE visited_at LIKE '%주%'").fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM lunch_visit').fetchone()[0],sum(len([d for d,_ in records if '주' not in d]) for records in grouped().values()))
        self.assertTrue(all('[예시 리뷰' in r[0] for r in self.conn.execute('SELECT comment FROM lunch_review WHERE username=?',(AUTHOR,))))
    def test_unknown_location_does_not_write(self):
        self.conn.execute("UPDATE lunch_location SET address='다른 위치'")
        with self.assertRaises(ValueError): import_history(self.conn,lambda s:s,'2026-10-02')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM meta').fetchone()[0],0)

if __name__ == '__main__': unittest.main()
