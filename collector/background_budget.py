"""One reentrant heavy-job slot shared by collectors and functional checks."""
from contextlib import contextmanager
from functools import wraps
import gc
import itertools
import threading
import time


def release_unused_memory():
    gc.collect()
    try:
        import ctypes
        trim = getattr(ctypes.CDLL(None), 'malloc_trim', None)
        if trim: trim(0)
    except (OSError, AttributeError):
        pass


class BackgroundBudget:
    def __init__(self, cleanup=release_unused_memory):
        self.condition = threading.Condition()
        self.owner = None
        self.depth = 0
        self.queue = []
        self.sequence = itertools.count()
        self.cleanup = cleanup

    def acquire(self, wait=True, priority=False, timeout=None, on_wait=None):
        thread = threading.get_ident()
        deadline = None if timeout is None else time.monotonic() + timeout
        with self.condition:
            if self.owner == thread:
                self.depth += 1
                return True
            ticket = (0 if priority else 1, next(self.sequence))
            self.queue.append(ticket)
        try:
            while True:
                with self.condition:
                    if self.owner is None and min(self.queue) == ticket:
                        self.queue.remove(ticket)
                        self.owner, self.depth = thread, 1
                        return True
                    if not wait or deadline is not None and time.monotonic() >= deadline:
                        return False
                if on_wait: on_wait()
                with self.condition:
                    self.condition.wait(.5)
        finally:
            with self.condition:
                if ticket in self.queue:
                    self.queue.remove(ticket)
                    self.condition.notify_all()

    def release(self):
        with self.condition:
            if self.owner != threading.get_ident(): raise RuntimeError('Heavy-job owner mismatch')
            self.depth -= 1
            if self.depth: return
        try:
            self.cleanup()
        finally:
            with self.condition:
                self.owner = None
                self.condition.notify_all()

    @contextmanager
    def hold(self, **options):
        acquired = self.acquire(**options)
        try: yield acquired
        finally:
            if acquired: self.release()

    def serialized(self, function, wait=True):
        @wraps(function)
        def run(*args, **kwargs):
            progress = kwargs.get('progress')
            with self.hold(wait=wait, on_wait=(lambda: progress('다른 수집·점검 작업 종료 대기…')) if progress else None) as acquired:
                if acquired: return function(*args, **kwargs)
            return None
        return run


budget = BackgroundBudget()
