from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            q = self._events[key]
            while q and q[0] < cutoff:
                q.popleft()

            if len(q) >= limit:
                return False

            q.append(now)
            return True
