import threading
import time
import unittest
from collector.background_budget import BackgroundBudget


class BudgetTests(unittest.TestCase):
    def test_reentrant_slot_cleans_once_even_on_exception(self):
        cleaned=[]
        budget=BackgroundBudget(cleanup=lambda:cleaned.append(True))
        with self.assertRaises(ValueError),budget.hold() as outer:
            with budget.hold(wait=False) as inner:
                self.assertTrue(outer and inner)
                raise ValueError('failed job')
        self.assertEqual(cleaned,[True])
        self.assertIsNone(budget.owner)

    def test_heavy_jobs_run_one_at_a_time(self):
        budget=BackgroundBudget(cleanup=lambda:None)
        barrier=threading.Barrier(5)
        active=[];peak=[]
        def work():
            barrier.wait()
            with budget.hold():
                active.append(True);peak.append(len(active))
                time.sleep(.01)
                active.pop()
        threads=[threading.Thread(target=work) for _ in range(4)]
        for thread in threads:thread.start()
        barrier.wait()
        for thread in threads:thread.join(3);self.assertFalse(thread.is_alive())
        self.assertEqual(peak,[1]*4)

    def test_priority_check_runs_before_queued_collection(self):
        budget=BackgroundBudget(cleanup=lambda:None);order=[]
        def work(name,priority):
            with budget.hold(priority=priority):order.append(name)
        with budget.hold():
            collect=threading.Thread(target=work,args=('collect',False));collect.start()
            check=threading.Thread(target=work,args=('check',True));check.start()
            deadline=time.monotonic()+2
            while len(budget.queue)<2 and time.monotonic()<deadline:time.sleep(.001)
            self.assertEqual(len(budget.queue),2)
        for thread in (collect,check):thread.join(3);self.assertFalse(thread.is_alive())
        self.assertEqual(order,['check','collect'])

    def test_periodic_skip_and_wait_timeout_leave_no_ticket(self):
        budget=BackgroundBudget(cleanup=lambda:None);results=[]
        def contender():
            results.append(budget.acquire(wait=False))
            results.append(budget.acquire(timeout=.01))
        with budget.hold():
            thread=threading.Thread(target=contender);thread.start();thread.join(2)
            self.assertFalse(thread.is_alive());self.assertEqual(budget.queue,[])
        self.assertEqual(results,[False,False])

    def test_wait_callback_error_does_not_block_future_jobs(self):
        budget=BackgroundBudget(cleanup=lambda:None);errors=[]
        def contender():
            try:
                budget.acquire(on_wait=lambda:(_ for _ in ()).throw(ValueError('storage down')))
            except ValueError:errors.append(True)
        with budget.hold():
            thread=threading.Thread(target=contender);thread.start();thread.join(2)
        self.assertEqual(errors,[True]);self.assertEqual(budget.queue,[])
        with budget.hold(wait=False) as acquired:self.assertTrue(acquired)


if __name__=='__main__':unittest.main()
