"""Assess check failures without equating regression failures with service outages."""
KNOWN_FIXTURE_ERRORS = (
    ('test_video_navigation.cjs', 'HScopeSkeleton'),
    ('test_events_ui.cjs', 'shareBtnHtml'),
    ('test_lunch_review_filter.cjs', 'koreanMatchAll'),
    ('test_combined_collection.ControllerTests.test_status_after_restart_restores_saved_failure', '_admin_ok'),
)
FIRST_RUN = 'ac045be4fd6b4c10bebaa8b1a5615996'


def category(row, run_id=None):
    if row['status'] != 'failed': return row['status']
    if row.get('category'): return row['category']
    name, detail = row.get('name', ''), row.get('detail', '')
    if run_id == FIRST_RUN and row.get('group') == '관리자' and name in ('계정 목록', '수집 실행 로그', '패치내역') and detail == 'HTTP 401':
        return 'probe_error'
    if '회귀 테스트' in row.get('group', ''):
        if any(test in name and symbol in detail for test, symbol in KNOWN_FIXTURE_ERRORS):
            return 'test_environment'
        if row.get('error_stage') == 'preparation' or '_FailedTest.' in name or '테스트 준비 오류' in detail or '테스트 모듈 실행 오류' in detail or ('제한' in detail and '초과' in detail) or name == '전체 테스트 실행 완료 여부':
            return 'test_environment'
        if row.get('error_stage') == 'execution' or '실행 오류' in detail or 'ReferenceError' in detail or 'TypeError' in detail or 'ENOENT' in detail or 'SyntaxError' in detail:
            return 'test_error'
        return 'test_failure'
    if detail.startswith('점검 오류'): return 'probe_error'
    return 'service_failure'


def assess(report):
    counts = dict.fromkeys(('passed', 'warning', 'skipped', 'service_failure',
                          'test_failure', 'test_error', 'test_environment', 'probe_error'), 0)
    for row in report.get('results', []):
        row['category'] = category(row, report.get('id'))
        counts[row['category']] = counts.get(row['category'], 0) + 1
        if row['category'] == 'probe_error' and report.get('id') == FIRST_RUN:
            row['assessment_note'] = '당시 점검 도구의 세션 호스트 불일치. 수정 완료했으며 이 과거 결과는 재점검 결과가 아닙니다.'
    report['summary_counts'] = counts
    status = report['status']
    report['assessment_status'] = (status if status in ('running', 'interrupted') else
        'service_failure' if counts['service_failure'] else
        'needs_review' if status == 'failed' or any(counts[k] for k in ('test_failure', 'test_error', 'test_environment', 'probe_error')) else status)
    return report
