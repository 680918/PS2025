"""Bounded rolling-window admission for the single-process registration preview."""

from collections import deque
from math import ceil
from threading import Lock
from time import monotonic


class RegistrationRateLimiter:
    def __init__(
        self, *, per_client_limit, total_limit, window_seconds=60, clock=monotonic
    ):
        if any(
            type(value) is not int or value < 1
            for value in (per_client_limit, total_limit, window_seconds)
        ):
            raise ValueError("rate limits and window must be positive integers")
        self.per_client_limit = per_client_limit
        self.total_limit = total_limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._lock = Lock()
        self._clients = {}
        self._total = deque()

    def admit(self, client_key):
        """Return 0 when admitted, otherwise seconds until both budgets recover.

        Only admitted requests consume budget. Rejection never prolongs a wait.
        Keys and timestamps stay in memory, without credentials or email data.
        """
        with self._lock:
            now = self._clock()
            cutoff = now - self.window_seconds
            while self._total and self._total[0] <= cutoff:
                self._total.popleft()
            # Total budget bounds both timestamps and active client keys. Lazy
            # cleanup needs no scheduler and never creates buckets for rejects.
            for key, timestamps in list(self._clients.items()):
                while timestamps and timestamps[0] <= cutoff:
                    timestamps.popleft()
                if not timestamps:
                    del self._clients[key]
            timestamps = self._clients.get(client_key)
            waits = []
            if timestamps and len(timestamps) >= self.per_client_limit:
                waits.append(timestamps[0] + self.window_seconds - now)
            if len(self._total) >= self.total_limit:
                waits.append(self._total[0] + self.window_seconds - now)
            if waits:
                return max(1, ceil(max(waits)))
            if timestamps is None:
                timestamps = self._clients[client_key] = deque()
            timestamps.append(now)
            self._total.append(now)
            return 0
