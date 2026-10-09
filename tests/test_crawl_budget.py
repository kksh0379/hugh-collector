import os
import threading
import time
import unittest
from unittest.mock import patch

os.environ.update(ENABLE_SCHEDULER='0',AUTO_BACKFILL='0',ENABLE_DB_PREWARM='0',DB_KEEPALIVE_SEC='0')
import app as web


class CrawlBudgetTests(unittest.TestCase):
    def test_live_queued_job_stays_running_and_cannot_be_started_twice(self):
        started=threading.Event();release=threading.Event();calls=[]
        def run(*args):
            calls.append(args);started.set();release.wait(3)
        with patch.dict(web._JOBS,{},clear=True),patch.dict(web._JOB_THREADS,{},clear=True),patch.object(web,'_job_run',run):
            try:
                self.assertTrue(web._start_job('news'))
                self.assertTrue(started.wait(1))
                web._JOBS['news']['started_ts']=time.time()-3600
                self.assertFalse(web._start_job('news'))
                with web.app.test_request_context('/api/crawl/news/status'),patch.object(web,'_admin_ok',return_value=True):
                    self.assertTrue(web.crawl_job_status('news').json['running'])
                self.assertEqual(len(calls),1)
            finally:
                release.set()
                for thread in web._JOB_THREADS.values():thread.join(2)


if __name__=='__main__':unittest.main()
