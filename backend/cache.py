"""
In-memory LRU cache for historical rate responses.
Key: (base, tuple(sorted(targets)), start_date, end_date)
TTL: 300 s (default). Max 200 entries (LRU eviction).
"""
from __future__ import annotations
import time
from collections import OrderedDict
from typing import Any, Optional

_CACHE_MAX = 200


class RateCache:
    def __init__(self, ttl_seconds: int = 300, max_entries: int = _CACHE_MAX):
        self._store: OrderedDict[tuple, tuple[float, Any]] = OrderedDict()
        self._ttl = ttl_seconds
        self._max = max_entries

    def _make_key(
        self,
        base: str,
        targets: list[str],
        start_date: str,
        end_date: str,
    ) -> tuple:
        return (base.upper(), tuple(sorted(t.upper() for t in targets)), start_date, end_date)

    def get(
        self,
        base: str,
        targets: list[str],
        start_date: str,
        end_date: str,
    ) -> Optional[Any]:
        key = self._make_key(base, targets, start_date, end_date)
        if key not in self._store:
            return None
        ts, value = self._store[key]
        if time.monotonic() - ts > self._ttl:
            del self._store[key]
            return None
        # Move to end (most recently used)
        self._store.move_to_end(key)
        return value

    def set(
        self,
        base: str,
        targets: list[str],
        start_date: str,
        end_date: str,
        value: Any,
    ) -> None:
        key = self._make_key(base, targets, start_date, end_date)
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (time.monotonic(), value)
        # Evict oldest entry if over capacity
        while len(self._store) > self._max:
            self._store.popitem(last=False)
