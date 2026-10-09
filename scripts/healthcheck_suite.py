"""Run every registered regression test with isolated DB and no production secrets."""
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from collector.healthcheck_results import category


def limit_python_memory():
    """Bound only the isolated Python test module, never the web process."""
    try:
        import resource
    except ImportError:
        return
    limit = 256 * 1024 * 1024
    # RLIMIT_AS counts glibc's reserved thread arenas even when no RAM is used.
    # Linux RLIMIT_DATA also bounds writable mmap allocations, without counting
    # those uncommitted reservations or runtime code mappings.
    resource.setrlimit(resource.RLIMIT_DATA, (limit, limit))


def node_results(path, output, elapsed):
    rows=[];row=None
    for line in output.splitlines():
        match=re.match(r'^(ok|not ok) \d+ - (.*)',line)
        if match:
            if row:rows.append(row)
            row=dict(group='JavaScript 회귀 테스트',name=path.name+' · '+match[2],status='failed' if match[1]=='not ok' else 'skipped' if '# SKIP' in match[2] else 'passed',detail='격리 환경 검사 통과' if match[1]=='ok' else '검증 실패',duration_ms=0)
        elif row:
            match=re.search(r'duration_ms: ([\d.]+)',line)
            if match:row['duration_ms']=round(float(match[1]))
            if row['status']=='failed' and re.search(r'(error:|name:)',line):row['detail']=(row['detail']+' · '+line.strip())[:240]
    if row:rows.append(row)
    for item in rows: item['category']=category(item)
    return rows


def run(output, filename=None):
    if filename: limit_python_memory()
    rows = []
    state = {'results': rows, 'total': 0, 'done': False, 'phase': 'Python 회귀 테스트'}
    def save():
        tmp = output.with_suffix('.tmp')
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
        tmp.replace(output)
    with tempfile.TemporaryDirectory(prefix='hscope-test-db-') as folder:
        # This process is launched with an allowlisted environment by the service.
        if os.environ.get('DATABASE_URL'):
            raise RuntimeError('Production database is forbidden in the regression suite')
        os.environ.update(ENABLE_SCHEDULER='0', AUTO_BACKFILL='0', ENABLE_DB_PREWARM='0',
                          DB_KEEPALIVE_SEC='0', HEALTHCHECK_DISABLE='1')
        from collector import db
        db.DB_PATH = str(Path(folder) / 'isolated.sqlite')
        db.init_db()

        class Result(unittest.TestResult):
            active = None
            def startTest(self, test):
                super().startTest(test)
                self.active = test
                self.started = time.perf_counter()
                self.row = {'group': 'Python 회귀 테스트', 'name': test.id(), 'status': 'passed',
                            'detail': '격리 환경 검사 통과'}
            def addFailure(self, test, err):
                super().addFailure(test, err)
                self.row.update(status='failed', detail=('검증 실패 · ' + err[0].__name__ + ' · '+str(err[1]))[:240])
            def addError(self, test, err):
                super().addError(test, err)
                if self.active is None:
                    rows.append(dict(group='Python 회귀 테스트',name=str(test),status='failed',category='test_environment',error_stage='preparation',detail='테스트 준비 오류 · '+err[0].__name__,duration_ms=0));save()
                else:
                    self.row.update(status='failed', error_stage='execution',detail=('실행 오류 · ' + err[0].__name__+' · '+str(err[1]))[:240])
                    if issubclass(err[0], MemoryError):
                        self.row.update(category='test_environment',detail='격리 테스트 메모리 제한 초과 · 미완료')
            def addSkip(self, test, reason):
                super().addSkip(test, reason)
                self.row.update(status='skipped', detail=str(reason)[:160])
            def addExpectedFailure(self, test, err):
                super().addExpectedFailure(test, err)
                self.row.update(status='warning', detail='기존 예상 실패 항목')
            def addUnexpectedSuccess(self, test):
                super().addUnexpectedSuccess(test)
                self.row.update(status='warning', detail='예상 실패 조건 재검토 필요')
            def addSubTest(self, test, subtest, err):
                super().addSubTest(test, subtest, err)
                if err: self.row.update(status='failed', detail='하위 검증 실패 · ' + err[0].__name__)
            def stopTest(self, test):
                self.row['duration_ms'] = round((time.perf_counter() - self.started) * 1000)
                self.row['category'] = category(self.row)
                rows.append(self.row)
                save()
                self.active = None
                super().stopTest(test)

        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=filename or 'test_*.py')
        node_files = [] if filename else sorted((ROOT / 'tests').glob('test_*.cjs'))
        state['total'] = suite.countTestCases() + len(node_files)
        save()
        suite.run(Result())
        state['phase'] = 'JavaScript 회귀 테스트'
        save()
        node = shutil.which('node')
        for path in node_files:
            started = time.perf_counter()
            row = {'group': 'JavaScript 회귀 테스트', 'name': path.name}
            if not node:
                row.update(status='skipped', detail='서버에 Node.js 런타임이 없어 실행하지 못함')
            else:
                try:
                    result = subprocess.run([node, '--max-old-space-size=96', str(path)], cwd=ROOT, timeout=45,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    row.update(status='passed' if result.returncode == 0 else 'failed',
                        detail='격리 환경 검사 통과' if result.returncode == 0 else f'검증 실패 · 종료 코드 {result.returncode}')
                except subprocess.TimeoutExpired:
                    row.update(status='failed', detail='45초 제한 시간 초과')
            row['duration_ms'] = round((time.perf_counter() - started) * 1000)
            rows.append(row)
            save()
        state.update(done=True, phase='완료')
        save()


def all_tests(output):
    """Separate processes keep modules' environment and global fixtures independent."""
    rows=[]
    state={'results':rows,'total':1,'done':False,'phase':'Python 회귀 테스트'}
    def save():
        temp=output.with_suffix('.tmp');temp.write_text(json.dumps(state,ensure_ascii=False));temp.replace(output)
    python_files=sorted((ROOT/'tests').glob('test_*.py'))
    node_files=sorted((ROOT/'tests').glob('test_*.cjs'))
    with tempfile.TemporaryDirectory(prefix='hscope-test-modules-') as folder:
        for index,path in enumerate(python_files):
            state.update(phase='Python 회귀 테스트 · '+path.name,total=len(rows)+len(python_files)-index+len(node_files));save()
            began=time.perf_counter();part=Path(folder)/'part.json'
            if part.exists():part.unlink()
            try:
                result=subprocess.run([sys.executable,__file__,str(part),path.name],cwd=ROOT,
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
                if part.exists():rows.extend(json.loads(part.read_text())['results'])
                if result.returncode or not part.exists():rows.append(dict(group='Python 회귀 테스트',name=path.name,status='failed',detail='테스트 모듈 실행 오류',duration_ms=round((time.perf_counter()-began)*1000)))
            except subprocess.TimeoutExpired:
                rows.append(dict(group='Python 회귀 테스트',name=path.name,status='failed',detail='30초 실행 제한 초과',duration_ms=round((time.perf_counter()-began)*1000)))
            save()
        node=shutil.which('node')
        for index,path in enumerate(node_files):
            state.update(phase='JavaScript 회귀 테스트 · '+path.name,total=len(rows)+len(node_files)-index);save()
            began=time.perf_counter();row={'group':'JavaScript 회귀 테스트','name':path.name}
            if not node:row.update(status='skipped',detail='Node.js 런타임이 없어 실행하지 못함')
            else:
                try:
                    result=subprocess.run([node,'--max-old-space-size=96','--test','--test-reporter=tap',str(path)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=45)
                    if re.search(r'(heap out of memory|Allocation failed|SIGABRT|SIGKILL)', result.stdout, re.I):
                        row.update(status='failed',category='test_environment',detail='격리 테스트 메모리 제한 또는 프로세스 강제 종료 · 미완료')
                        row['duration_ms']=round((time.perf_counter()-began)*1000)
                        rows.append(row);save();continue
                    parsed=node_results(path,result.stdout,round((time.perf_counter()-began)*1000))
                    if parsed:
                        rows.extend(parsed);save();continue
                    row.update(status='passed' if result.returncode==0 else 'failed',detail='격리 환경 검사 통과' if result.returncode==0 else f'검증 실패 · 종료 코드 {result.returncode}')
                except subprocess.TimeoutExpired:row.update(status='failed',detail='45초 실행 제한 초과')
            row['duration_ms']=round((time.perf_counter()-began)*1000);rows.append(row);save()
    state.update(total=len(rows),done=True,phase='완료');save()


if __name__ == '__main__':
    try:
        if len(sys.argv)>2:run(Path(sys.argv[1]),sys.argv[2])
        else:all_tests(Path(sys.argv[1]))
    except MemoryError:
        output=Path(sys.argv[1])
        state=json.loads(output.read_text()) if output.exists() else dict(results=[],total=0)
        state['results'].append(dict(group='Python 회귀 테스트',name=sys.argv[2] if len(sys.argv)>2 else '전체 테스트 실행 완료 여부',status='failed',category='test_environment',detail='격리 테스트 메모리 제한 초과 · 미완료',duration_ms=0))
        state.update(done=True,total=len(state['results']),phase='메모리 제한으로 미완료')
        output.write_text(json.dumps(state,ensure_ascii=False))
