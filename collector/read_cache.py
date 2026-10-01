"""Bounded single-flight cache: stale reads never wait for a database reconnect."""
import logging
import threading
import time
from collections import OrderedDict


class ReadCache:
    def __init__(self, max_entries=32, workers=3, cooldown=5):
        self.entries = OrderedDict()
        self.pending = {}
        self.failures = {}
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(workers)
        self.max_entries = max_entries
        self.cooldown = cooldown

    def get(self, key, fetch, ttl=45, wait=None):
        """Return cached data or None while loading. wait=None loads cold keys inline.

        A stale value is served immediately while one bounded worker refreshes it.
        Setting wait=0 makes even a cold read nonblocking (location picker).
        """
        now = time.monotonic()
        with self.lock:
            hit = self.entries.get(key)
            if hit:
                self.entries.move_to_end(key)
                if now - hit[0] < ttl:
                    return hit[1]
            event = self.pending.get(key)
            launch = event is None and self.failures.get(key, 0) <= now
            if launch:
                if not self.slots.acquire(blocking=False):
                    return hit[1] if hit else None
                event = threading.Event()
                self.pending[key] = event
        if launch:
            if not hit and wait is None:
                self._refresh(key, fetch, event)
            else:
                threading.Thread(target=self._refresh, args=(key, fetch, event), daemon=True).start()
        if hit:
            return hit[1]
        if event:
            event.wait(5 if wait is None else wait)
        with self.lock:
            hit = self.entries.get(key)
            return hit[1] if hit else None

    def _refresh(self, key, fetch, event):
        try:
            value = fetch()
            with self.lock:
                # An invalidation during this query must not republish old data.
                if self.pending.get(key) is event:
                    self.entries[key] = (time.monotonic(), value)
                    self.entries.move_to_end(key)
                    self.failures.pop(key, None)
                    while len(self.entries) > self.max_entries:
                        self.entries.popitem(last=False)
        except Exception:
            logging.getLogger(__name__).warning("Read cache refresh failed: %s", key)
            with self.lock:
                if self.pending.get(key) is event:
                    self.failures[key] = time.monotonic() + self.cooldown
                    while len(self.failures) > self.max_entries:
                        self.failures.pop(next(iter(self.failures)))
        finally:
            with self.lock:
                if self.pending.get(key) is event:
                    self.pending.pop(key, None)
            self.slots.release()
            event.set()

    def invalidate(self, prefix=""):
        with self.lock:
            for mapping in (self.entries, self.pending, self.failures):
                for key in list(mapping):
                    if key.startswith(prefix):
                        mapping.pop(key, None)
