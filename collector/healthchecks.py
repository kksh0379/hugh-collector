"""Persisted functional checks, isolated regressions, and signed daily triggers."""
import json
import gzip
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from flask import jsonify, request, session

KST = timezone(timedelta(hours=9))
PUBLIC_KEY = '4a3405fe444aec8aedbb1663275bded6973c2c68cd52b2e3b237b7fa9f3ba29a'
ROOT = Path(__file__).resolve().parents[1]
LABELS = {'passed': '정상', 'warning': '주의', 'failed': '오류', 'skipped': '미점검'}
SCOPE = '운영 조회·외부 연결 점검과 격리 환경의 전체 등록 테스트를 실행합니다. 실제 사용자 데이터 삭제·전체 재수집·AI 생성은 실행하지 않습니다.'


def now():
    return datetime.now(KST).isoformat(timespec='seconds')


class HealthChecks:
    def __init__(self, app, db, ensure_db):
        self.app, self.db, self.ensure_db = app, db, ensure_db
        self.schema_lock = threading.Lock()
        self.ready = False

    def schema(self):
        with self.schema_lock:
            if self.ready: return
            if not self.ensure_db(force=True): raise RuntimeError('DB unavailable')
            with self.db.get_conn() as conn:
                conn.execute('CREATE TABLE IF NOT EXISTS healthcheck_runs (id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, trigger TEXT NOT NULL, status TEXT NOT NULL, duration_ms INTEGER NOT NULL, report TEXT NOT NULL)')
                conn.execute('CREATE TABLE IF NOT EXISTS healthcheck_lock (name TEXT PRIMARY KEY, run_id TEXT NOT NULL, expires_at DOUBLE PRECISION NOT NULL)')
                conn.execute('CREATE TABLE IF NOT EXISTS healthcheck_daily (day TEXT PRIMARY KEY, run_id TEXT NOT NULL)')
            self.ready = True

    def read(self, run_id=None):
        self.schema()
        with self.db.get_conn() as conn:
            if run_id:
                row = conn.execute(self.db._q('SELECT report FROM healthcheck_runs WHERE id=?'), (run_id,)).fetchone()
            else:
                row = conn.execute('SELECT report FROM healthcheck_runs ORDER BY started_at DESC LIMIT 1').fetchone()
        if not row: return None
        report = json.loads(row['report'])
        report['elapsed_ms'] = max(report.get('duration_ms', 0), round((datetime.now(KST) - datetime.fromisoformat(report['started_at'])).total_seconds() * 1000)) if report['status'] == 'running' else report['duration_ms']
        if report['status'] == 'running' and report['elapsed_ms'] > 1800000:
            report.update(status='interrupted', finished_at=now(), duration_ms=report['elapsed_ms'], phase='서버 재시작 또는 실행 제한 시간 초과')
            self.save(report)
        return report

    def history(self):
        self.schema()
        with self.db.get_conn() as conn:
            rows = conn.execute('SELECT id, started_at, finished_at, trigger, status, duration_ms FROM healthcheck_runs ORDER BY started_at DESC LIMIT 30').fetchall()
        return [dict(row) for row in rows]

    def save(self, report):
        with self.db.get_conn() as conn:
            conn.execute(self.db._q('UPDATE healthcheck_runs SET status=?, finished_at=?, duration_ms=?, report=? WHERE id=?'),
                (report['status'], report.get('finished_at'), report.get('duration_ms', 0), json.dumps(report, ensure_ascii=False), report['id']))

    def start(self, trigger='manual', daily=False):
        self.schema()
        run_id = uuid.uuid4().hex
        stamp = now()
        report = dict(id=run_id, started_at=stamp, finished_at=None, trigger=trigger, status='running',
                      duration_ms=0, elapsed_ms=0, results=[], total=1, phase='점검 준비', scope=SCOPE)
        with self.db.get_conn() as conn:
            acquired = conn.execute(self.db._q('INSERT INTO healthcheck_lock (name,run_id,expires_at) VALUES (?,?,?) ON CONFLICT (name) DO UPDATE SET run_id=excluded.run_id,expires_at=excluded.expires_at WHERE healthcheck_lock.expires_at < ? RETURNING run_id'),
                ('all', run_id, time.time() + 1800, time.time())).fetchone()
            if not acquired:
                active = conn.execute("SELECT run_id FROM healthcheck_lock WHERE name='all'").fetchone()
                return active['run_id'], False
            if daily:
                day = datetime.now(KST).date().isoformat()
                claimed = conn.execute(self.db._q('INSERT INTO healthcheck_daily (day,run_id) VALUES (?,?) ON CONFLICT (day) DO NOTHING RETURNING run_id'), (day, run_id)).fetchone()
                if not claimed:
                    old = conn.execute(self.db._q('SELECT run_id FROM healthcheck_daily WHERE day=?'), (day,)).fetchone()
                    conn.execute(self.db._q('DELETE FROM healthcheck_lock WHERE run_id=?'), (run_id,))
                    return old['run_id'], False
            conn.execute(self.db._q('INSERT INTO healthcheck_runs (id,started_at,trigger,status,duration_ms,report) VALUES (?,?,?,?,?,?)'),
                (run_id, stamp, trigger, 'running', 0, json.dumps(report, ensure_ascii=False)))
            conn.execute('DELETE FROM healthcheck_runs WHERE id NOT IN (SELECT id FROM healthcheck_runs ORDER BY started_at DESC LIMIT 30)')
        threading.Thread(target=self.execute, args=(report,), daemon=True, name='hscope-healthcheck').start()
        return run_id, True

    def request(self, path, admin=False):
        deadline = time.monotonic() + 25
        with self.app.test_client() as client:
            if admin:
                with client.session_transaction() as state:
                    state.update(user='admin', admin=True)
            while True:
                response = client.get(path, base_url='https://hscope.onrender.com')
                data = response.get_json(silent=True)
                if data is None and response.headers.get('Content-Encoding') == 'gzip':
                    try: data = json.loads(gzip.decompress(response.data))
                    except (ValueError, OSError): pass
                pending = response.headers.get('X-Data-Pending') == '1' or isinstance(data, dict) and (data.get('pending') or data.get('db_waking'))
                if not pending or time.monotonic() >= deadline:
                    if response.status_code != 200: return 'failed', f'HTTP {response.status_code}'
                    if pending: return 'warning', '데이터 준비가 25초 이상 지연됨'
                    return 'passed', data
                time.sleep(.5)

    def json_check(self, path, key=None, admin=False):
        status, data = self.request(path, admin)
        if status != 'passed': return status, data
        if key and (not isinstance(data, dict) or key not in data): return 'failed', '응답 구조가 예상 형식과 다름'
        if isinstance(data, list): return ('passed' if data else 'warning'), f'조회 {len(data)}건'
        if not isinstance(data, dict): return 'failed', 'JSON 응답이 아님'
        if data.get('empty'): return 'warning', '저장된 데이터 없음'
        if data.get('error'): return 'warning', '응답에 오류 안내 포함'
        mode = data.get('mode')
        if mode in ('unavailable', 'loading'): return 'failed', '외부 데이터 연결 실패'
        if mode in ('unconfigured', 'demo'): return 'skipped', '외부 API 미설정 또는 예시 데이터'
        return 'passed', '응답 구조·조회 정상'

    def views(self):
        paths = ['/', '/hscope', '/intro', '/hscope/install']
        assets = set()
        for path in paths:
            with self.app.test_client() as client:
                response = client.get(path, base_url='https://hscope.onrender.com')
                if response.status_code != 200: return 'failed', f'{path} HTTP {response.status_code}'
                soup = BeautifulSoup(response.text, 'html.parser')
                if not soup.select_one('title'): return 'failed', f'{path} 화면 구조 오류'
                for node in soup.select('script[src],link[rel="stylesheet"][href]'):
                    asset = node.get('src') or node.get('href')
                    if asset.startswith('/static/'): assets.add(asset)
        with self.app.test_client() as client:
            for path in sorted(assets):
                if client.get(path).status_code != 200: return 'failed', '화면에 필요한 정적 파일 누락'
        return 'passed', f'화면 {len(paths)}개 · JS/CSS {len(assets)}개 정상 제공'

    def database(self):
        with self.db.get_conn() as conn:
            conn.execute('SELECT 1').fetchone()
            for table in ('news', 'boards', 'social', 'events', 'meta'):
                conn.execute(f'SELECT COUNT(*) AS n FROM {table}').fetchone()
        return 'passed', 'DB 연결·주요 테이블 조회 정상'

    def food(self):
        status, data = self.request('/api/lunch/locations')
        if status != 'passed': return status, data
        locs = data.get('locations', [])
        if not locs: return 'warning', '등록 지역 없음'
        checked, count = 0, 0
        for loc in locs:
            status, result = self.request('/api/lunch/restaurants?loc=' + str(loc['id']))
            if status != 'passed': return status, '지역별 맛집 조회 지연 또는 실패'
            if not isinstance(result.get('restaurants'), list): return 'failed', '맛집 목록 응답 구조 오류'
            checked += 1; count += len(result['restaurants'])
        return 'passed', f'등록 지역 {checked}곳 · 맛집 {count}건 조회 정상'

    def finance(self):
        status, data = self.request('/api/finance/dashboard')
        if status != 'passed': return status, data
        rows = data.get('indicators', [])
        if not rows: return 'failed', '경제지표 응답 없음'
        missing = sum(x.get('value') is None or x.get('mode') != 'live' for x in rows)
        sources = data.get('sources', [])
        bad = sum(x.get('mode') != 'live' for x in sources)
        return ('warning' if missing or bad else 'passed'), f'지표 {len(rows)}개 중 미연결 {missing}개 · 소식 출처 {len(sources)}개 중 미연결 {bad}개'

    def video(self):
        status, data = self.request('/api/videos/playback?id=19240&series=1&episode=8&refresh=1')
        if status != 'passed': return status, '강철의 연금술사 8화 재생 주소 추출 실패'
        from .video_hls import safe_media_url
        source = data.get('src', '')
        if not safe_media_url(source): return 'failed', '영상 주소 검증 실패'
        for _ in range(4):
            with requests.get(source, timeout=(5,12), allow_redirects=False, stream=True) as response:
                if response.status_code in (301,302,303,307,308):
                    source = urljoin(source, response.headers.get('Location', ''))
                    if not safe_media_url(source): return 'failed', '허용되지 않은 미디어 리디렉션'
                    continue
                if response.status_code != 200: return 'failed', f'영상 재생 목록 HTTP {response.status_code}'
                text = response.content[:2000000].decode('utf-8-sig')
            if not text.startswith('#EXTM3U'): return 'failed', 'HLS 재생 목록 형식 오류'
            if data.get('native_src'):
                parsed = urlparse(data['native_src'])
                status, _ = self.request(parsed.path + '?' + parsed.query)
                if status != 'passed': return 'failed', '자막 포함 재생 목록 오류'
            return 'passed', '대표 회차 재생 주소·HLS·자막 재생 목록 정상 (전체 회차 전수 재생은 아님)'
        return 'failed', '영상 리디렉션 횟수 초과'

    def guard(self):
        with self.app.test_client() as client:
            for path in ('/api/notes', '/api/admin/accounts', '/api/admin/healthchecks'):
                if client.get(path).status_code not in (401,403): return 'failed', '관리자 전용 조회 권한 검증 실패'
            for path in ('/api/admin/healthchecks/run', '/api/admin/purge', '/api/report/purge'):
                if client.post(path, json={}).status_code not in (401,403): return 'failed', '관리자 동작 권한 검증 실패'
        return 'passed', '비로그인 관리자 조회·실행·삭제 요청 차단 정상'

    def checks(self):
        rows = [('기반', 'DB 연결과 주요 저장 테이블', self.database), ('화면', '런처·서비스·소개·설치 화면 및 전체 연결 JS/CSS', self.views),
                ('인증', '관리자 권한 차단', self.guard), ('설정', '기능 표시 설정', lambda:self.json_check('/api/features'))]
        for name, path in [('재단 뉴스','news'),('고양이','catnews'),('게임','gamenews'),('동향','biznews'),('보안','secnews'),('행사','events'),('재단 게시판','boards'),('소셜 영상','social')]:
            rows.append(('뉴스·행사', name + ' 목록 조회', lambda p=path:self.json_check('/api/'+p)))
        rows += [('맛집','모든 등록 지역 맛집 목록',self.food), ('맛집','후기 조회',lambda:self.json_check('/api/lunch/reviews')),
                 ('재무세무','경제지표·브리핑 출처',self.finance), ('재무세무','하나은행 거래 환율',lambda:self.json_check('/api/finance/exchange','quotes')),
                 ('재무세무','엔씨 주가',lambda:self.json_check('/api/finance/stock','value')), ('재무세무','DART 공시',lambda:self.json_check('/api/finance/disclosures','items')),
                 ('영상','전체 작품 목록',lambda:self.json_check('/api/videos/library','items')), ('영상','대표 작품 회차 목록',lambda:self.json_check('/api/videos/catalog?id=19240&series=1&episode=8','series')),
                 ('영상','대표 회차 재생 연결',self.video), ('AI','AI 제공자 설정',self.ai),
                 ('관리자','계정 목록',lambda:self.json_check('/api/admin/accounts',admin=True)), ('관리자','수집 실행 로그',lambda:self.json_check('/api/runlog',admin=True)),
                 ('관리자','수집 상태',lambda:self.json_check('/api/crawl/status',admin=True)), ('관리자','패치내역',lambda:self.json_check('/api/notes','changelog',True))]
        for kind in ('foundation','security'):
            rows.append(('리포트', ('재단동향' if kind=='foundation' else '보안') + ' 리포트 조회',lambda k=kind:self.json_check('/api/report/get?kind='+k)))
        return rows

    def ai(self):
        from . import ai_provider
        state = ai_provider.status()
        return 'skipped', 'API 설정만 확인 · 실제 AI 생성·유료 호출은 점검 범위에 포함하지 않음' if state else 'AI API 미설정'

    def suite(self, report, start):
        suite_start = time.perf_counter()
        baseline = list(report['results'])
        with tempfile.TemporaryDirectory(prefix='hscope-regression-') as folder:
            output = Path(folder) / 'result.json'
            # Never forward any API key, credential, database URL or admin secret.
            env = {k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','PYTHONPATH','PYTHONHOME')}
            env.update(ENABLE_SCHEDULER='0', AUTO_BACKFILL='0', ENABLE_DB_PREWARM='0', HEALTHCHECK_DISABLE='1', DB_KEEPALIVE_SEC='0')
            process = subprocess.Popen([sys.executable,str(ROOT/'scripts/healthcheck_suite.py'),str(output)], cwd=ROOT,env=env,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            deadline = time.monotonic() + 300
            try:
                while process.poll() is None:
                    if time.monotonic() > deadline:
                        os.killpg(process.pid, signal.SIGKILL);process.wait();break
                    if output.exists():
                        state = json.loads(output.read_text())
                        report.update(results=baseline+state['results'],total=len(baseline)+max(1,state['total']),phase=state['phase'])
                    report['duration_ms'] = round((time.perf_counter()-start)*1000)
                    self.save(report)
                    time.sleep(3)
                if output.exists():
                    state=json.loads(output.read_text());report['results']=baseline+state['results']
                else: state={}
                if process.returncode != 0 or not state.get('done'):
                    report['results'].append(dict(group='회귀 테스트',name='전체 테스트 실행 완료 여부',status='failed',detail='테스트 프로세스 오류 또는 300초 제한 시간 초과',duration_ms=round((time.perf_counter()-suite_start)*1000)))
            finally:
                if process.poll() is None: os.killpg(process.pid,signal.SIGKILL);process.wait()

    def execute(self, report):
        start = time.perf_counter()
        try:
            checks = self.checks();report['total']=len(checks)+1
            for group, name, function in checks:
                report['phase']=name;self.save(report)
                began=time.perf_counter()
                try: status, detail = function()
                except Exception as exc: status,detail='failed','점검 오류 · '+type(exc).__name__
                report['results'].append(dict(group=group,name=name,status=status,detail=detail,duration_ms=round((time.perf_counter()-began)*1000)))
                report['duration_ms']=round((time.perf_counter()-start)*1000);self.save(report)
            report['phase']='격리 회귀 테스트';self.save(report)
            self.suite(report,start)
            counts={key:sum(row['status']==key for row in report['results']) for key in LABELS}
            report.update(counts=counts,total=len(report['results']),status='failed' if counts['failed'] else 'warning' if counts['warning'] or counts['skipped'] else 'passed',phase='완료')
        except Exception as exc:
            report.update(status='failed',phase='점검 중단 · '+type(exc).__name__)
        finally:
            report.update(finished_at=now(),duration_ms=round((time.perf_counter()-start)*1000))
            try:
                self.save(report)
                with self.db.get_conn() as conn: conn.execute(self.db._q('DELETE FROM healthcheck_lock WHERE run_id=?'),(report['id'],))
            except Exception as exc: print('[healthcheck] 결과 저장 실패 · '+type(exc).__name__,flush=True)


def verify_signature(body):
    try:
        timestamp=request.headers.get('X-Health-Timestamp','')
        if abs(time.time()-int(timestamp))>300: return False
        signature=bytes.fromhex(request.headers.get('X-Health-Signature',''))
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY)).verify(signature,timestamp.encode()+b'\n'+body)
        return True
    except Exception: return False


def register(app, db, ensure_db):
    service=HealthChecks(app,db,ensure_db)
    app.extensions['healthchecks']=service
    def unavailable(): return jsonify(error='점검 기록 저장소에 연결하지 못했어요.'),503
    @app.get('/api/admin/healthchecks')
    def healthcheck_results():
        if not session.get('admin'): return jsonify(error='unauthorized'),401
        try: return jsonify(report=service.read(request.args.get('id')),history=service.history(),schedule='매일 03:00 · 한국 시간',scope=SCOPE)
        except Exception: return unavailable()
    @app.post('/api/admin/healthchecks/run')
    def healthcheck_run():
        if not session.get('admin'): return jsonify(error='unauthorized'),401
        origin=request.headers.get('Origin')
        if origin and origin.rstrip('/') != request.host_url.rstrip('/'): return jsonify(error='요청 출처 확인 실패'),403
        try:
            run_id,started=service.start()
            return jsonify(id=run_id,started=started),202
        except Exception: return unavailable()
    @app.post('/api/admin/healthchecks/cron')
    def healthcheck_cron():
        body=request.get_data()
        if not verify_signature(body): return jsonify(error='unauthorized'),401
        data=request.get_json(silent=True) or {}
        try:
            if data.get('action')=='status': return jsonify(report=service.read(data.get('id')))
            run_id,started=service.start('verification' if data.get('action')=='verify' else 'scheduled',daily=data.get('action')!='verify')
            return jsonify(id=run_id,started=started),202
        except Exception: return unavailable()
    return service
