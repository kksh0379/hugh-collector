"""Admin-only management of ordinary accounts; admin remains environment-managed."""
import re
import threading
from urllib.parse import urlsplit

from flask import jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .identity import canonical_user

_ready = False
_lock = threading.Lock()


def init_store():
    global _ready
    if _ready:
        return
    with _lock:
        if _ready:
            return
        with db.get_conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS app_account (
                username TEXT PRIMARY KEY CHECK (username <> 'admin'),
                display_name TEXT NOT NULL, password_hash TEXT NOT NULL,
                version BIGINT NOT NULL DEFAULT 1, deleted INTEGER NOT NULL DEFAULT 0
            )""")
            seeded = conn.execute("SELECT value FROM meta WHERE key='accounts_seeded_v1'").fetchone()
            if not seeded:
                conn.execute(db._q("INSERT INTO app_account (username, display_name, password_hash) VALUES (?,?,?) ON CONFLICT(username) DO NOTHING"),
                             ('test1', '김테스터', generate_password_hash('1234')))
                conn.execute("INSERT INTO meta (key,value) VALUES ('accounts_seeded_v1','1') ON CONFLICT(key) DO NOTHING")
        _ready = True


def get_account(username):
    init_store()
    with db.get_conn() as conn:
        row = conn.execute(db._q("SELECT * FROM app_account WHERE username=? AND deleted=0"), (canonical_user(username),)).fetchone()
    return dict(row) if row else None


def authenticate(username, password):
    row = get_account(username)
    if row and isinstance(password, str) and len(password) <= 128 and check_password_hash(row['password_hash'], password):
        return row
    return None


def public_account(row):
    return {key: row[key] for key in ('username', 'display_name')}


def validate(data, creating=False):
    if not isinstance(data, dict):
        raise ValueError('입력 형식을 확인해 주세요.')
    if 'role' in data or 'admin' in data:
        raise ValueError('이 화면에서는 일반 계정만 관리할 수 있어요.')
    name = data.get('display_name')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 50:
        raise ValueError('표시 이름은 1~50자로 입력해 주세요.')
    password = data.get('password', '')
    if not isinstance(password, str) or (creating or password) and not 8 <= len(password) <= 128:
        raise ValueError('새 비밀번호는 8~128자로 입력해 주세요.')
    return name.strip(), generate_password_hash(password) if password else None


def register(app, ensure_db, admin_ok):
    def allowed(write=False):
        if not admin_ok():
            return jsonify({'error': '관리자 로그인이 필요해요.'}), 401
        if write and request.headers.get('Origin'):
            origin = urlsplit(request.headers['Origin'])
            host = urlsplit(request.host_url)
            if (origin.scheme, origin.netloc) != (host.scheme, host.netloc):
                return jsonify({'error': '잘못된 요청 출처예요.'}), 403
        if not ensure_db(force=True):
            return jsonify({'error': 'DB에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.'}), 503
        init_store()

    @app.get('/api/admin/accounts')
    def accounts_list():
        error = allowed()
        if error:
            return error
        with db.get_conn() as conn:
            rows = conn.execute('SELECT username, display_name FROM app_account WHERE deleted=0 ORDER BY username').fetchall()
        response = jsonify({'accounts': [{'username': 'admin', 'display_name': '관리자', 'role': 'admin', 'locked': True}]
                            + [dict(public_account(row), role='user', locked=False) for row in rows]})
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.post('/api/admin/accounts')
    def accounts_create():
        error = allowed(True)
        if error:
            return error
        data = request.get_json(silent=True)
        try:
            name, password_hash = validate(data, True)
            username = data.get('username', '')
            if not isinstance(username, str):
                raise ValueError('아이디 형식을 확인해 주세요.')
            username = username.strip().lower()
            if username in ('admin', 'tester1') or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{2,31}', username):
                raise ValueError('아이디는 영문 소문자·숫자·밑줄·하이픈 3~32자이며 admin, tester1은 사용할 수 없어요.')
            with db.get_conn() as conn:
                result = conn.execute(db._q('INSERT INTO app_account (username,display_name,password_hash) VALUES (?,?,?) ON CONFLICT(username) DO NOTHING'),
                                      (username, name, password_hash))
                if not result.rowcount:
                    return jsonify({'error': '이미 사용되었거나 삭제된 아이디예요. 다른 아이디를 입력해 주세요.'}), 409
            return jsonify({'ok': True}), 201
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400

    @app.route('/api/admin/accounts/<username>', methods=['PATCH', 'DELETE'])
    def accounts_change(username):
        error = allowed(True)
        if error:
            return error
        username = canonical_user(username.lower())
        if username == 'admin':
            return jsonify({'error': '관리자 계정은 이 기능에서 변경·삭제할 수 없어요.'}), 403
        try:
            if request.method == 'PATCH':
                data = request.get_json(silent=True)
                name, password_hash = validate(data)
                if data.get('username', username) != username:
                    raise ValueError('아이디는 변경할 수 없어요.')
                with db.get_conn() as conn:
                    result = conn.execute(db._q('UPDATE app_account SET display_name=?, password_hash=COALESCE(?,password_hash), version=version+1 WHERE username=? AND deleted=0'),
                                          (name, password_hash, username))
            else:
                with db.get_conn() as conn:
                    result = conn.execute(db._q('UPDATE app_account SET deleted=1, version=version+1 WHERE username=? AND deleted=0'), (username,))
            if not result.rowcount:
                return jsonify({'error': '계정을 찾을 수 없어요. 목록을 다시 확인해 주세요.'}), 404
            return jsonify({'ok': True})
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
