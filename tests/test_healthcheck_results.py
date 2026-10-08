import copy
import unittest
from collector.healthcheck_results import FIRST_RUN, assess, category


class AssessmentTests(unittest.TestCase):
    def row(self, group, name, detail):
        return dict(group=group,name=name,detail=detail,status='failed',duration_ms=1320)

    def test_known_fixture_errors_are_not_service_failures(self):
        row=self.row('JavaScript 회귀 테스트','test_video_navigation.cjs · 재생','ReferenceError: HScopeSkeleton is not defined')
        self.assertEqual(category(row),'test_environment')
        row['name']='another_test.cjs'
        self.assertEqual(category(row),'test_error')

    def test_assertions_remain_unresolved_test_failures(self):
        self.assertEqual(category(self.row('Python 회귀 테스트','test_login','검증 실패 · AssertionError · 500 != 200')),'test_failure')
        self.assertEqual(category(self.row('영상','대표 회차 재생 연결','HLS 응답 오류')),'service_failure')
        self.assertEqual(category(self.row('JavaScript 회귀 테스트','test_assets.cjs','ENOENT: missing file')),'test_error')

    def test_audited_old_probe_error_does_not_hide_future_authorization_failure(self):
        row=self.row('관리자','계정 목록','HTTP 401')
        self.assertEqual(category(row,FIRST_RUN),'probe_error')
        self.assertEqual(category(row,'future-run'),'service_failure')

    def test_legacy_summary_preserves_raw_evidence_and_timings(self):
        report=dict(id=FIRST_RUN,status='failed',duration_ms=364096,finished_at='saved',counts={'failed':2},results=[self.row('관리자','계정 목록','HTTP 401'),self.row('Python 회귀 테스트','test_case','검증 실패 · AssertionError')])
        original=copy.deepcopy(report);assess(report)
        self.assertEqual(report['assessment_status'],'needs_review')
        self.assertEqual(report['summary_counts']['service_failure'],0)
        self.assertEqual(report['summary_counts']['probe_error'],1)
        self.assertEqual(report['summary_counts']['test_failure'],1)
        for key in ('status','duration_ms','finished_at','counts'):self.assertEqual(report[key],original[key])
        self.assertEqual(report['results'][0]['duration_ms'],1320)
        self.assertIn('수정 완료',report['results'][0]['assessment_note'])

    def test_skipped_and_probe_errors_never_become_passed(self):
        report=dict(status='failed',results=[self.row('기반','DB','점검 오류 · RuntimeError')])
        self.assertEqual(assess(report)['assessment_status'],'needs_review')
        report=dict(status='warning',results=[dict(status='skipped',group='AI',name='생성',detail='미점검')])
        self.assertEqual(assess(report)['assessment_status'],'warning')
