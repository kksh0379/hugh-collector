"""Alert policy: review-only findings must not produce failed Render cron jobs."""
import unittest

from scripts.healthcheck_cron import exit_code


class CronAlertPolicyTests(unittest.TestCase):
    def report(self, status, **counts):
        return {'status': status, 'assessment_status': 'needs_review',
                'summary_counts': {'passed': 508, 'service_failure': 0,
                                   'probe_error': 0, 'test_failure': 0,
                                   'test_error': 0, 'test_environment': 0,
                                   'warning': 0, 'skipped': 0, **counts}}

    def test_review_only_does_not_trigger_render_failure_alert(self):
        report = self.report('failed', test_failure=11, test_error=7,
                             test_environment=1, warning=2, skipped=1)
        self.assertEqual(exit_code(report), 0)

    def test_verified_service_failure_still_alerts(self):
        self.assertEqual(exit_code(self.report('failed', service_failure=1)), 1)

    def test_probe_error_still_alerts(self):
        self.assertEqual(exit_code(self.report('failed', probe_error=1)), 1)

    def test_interrupted_or_unclassified_run_still_alerts(self):
        self.assertEqual(exit_code(self.report('interrupted')), 1)
        self.assertEqual(exit_code({'status': 'failed'}), 1)
        self.assertEqual(exit_code(self.report('failed')), 1)
        self.assertEqual(exit_code({'status': 'running'}), 1)

    def test_success_and_warnings_do_not_alert(self):
        self.assertEqual(exit_code(self.report('passed')), 0)
        self.assertEqual(exit_code(self.report('warning', warning=2)), 0)


if __name__ == '__main__':
    unittest.main()
