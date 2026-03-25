import time
import pytest
from backend.cache import RateCache


def test_cache_miss_returns_none():
    """Empty cache returns None for any key."""
    cache = RateCache()
    result = cache.get("USD", ["EUR"], "2025-01-01", "2025-01-05")
    assert result is None


def test_cache_hit_returns_value():
    """set then get returns the same object."""
    cache = RateCache()
    payload = {"series": ["data"]}
    cache.set("USD", ["EUR"], "2025-01-01", "2025-01-05", payload)
    result = cache.get("USD", ["EUR"], "2025-01-01", "2025-01-05")
    assert result is payload


def test_cache_ttl_expiry(monkeypatch):
    """Entry is expired after TTL; monkeypatch time.monotonic."""
    cache = RateCache(ttl_seconds=10)
    payload = {"series": []}
    cache.set("USD", ["EUR"], "2025-01-01", "2025-01-05", payload)

    # Simulate 11 seconds passing
    original = time.monotonic()
    monkeypatch.setattr("backend.cache.time.monotonic", lambda: original + 11)

    result = cache.get("USD", ["EUR"], "2025-01-01", "2025-01-05")
    assert result is None


def test_cache_lru_eviction():
    """max_entries=2: third insert evicts the oldest."""
    cache = RateCache(max_entries=2)
    cache.set("USD", ["EUR"], "2025-01-01", "2025-01-05", "value_a")
    cache.set("USD", ["GBP"], "2025-01-01", "2025-01-05", "value_b")
    cache.set("USD", ["JPY"], "2025-01-01", "2025-01-05", "value_c")

    # Oldest entry (EUR) should be evicted
    assert cache.get("USD", ["EUR"], "2025-01-01", "2025-01-05") is None
    assert cache.get("USD", ["GBP"], "2025-01-01", "2025-01-05") == "value_b"
    assert cache.get("USD", ["JPY"], "2025-01-01", "2025-01-05") == "value_c"


def test_cache_key_normalises_target_order():
    """[EUR, GBP] and [GBP, EUR] hit the same cache key."""
    cache = RateCache()
    payload = {"series": ["data"]}
    cache.set("USD", ["EUR", "GBP"], "2025-01-01", "2025-01-05", payload)
    result = cache.get("USD", ["GBP", "EUR"], "2025-01-01", "2025-01-05")
    assert result is payload


def test_cache_set_overwrites_existing_key():
    """Setting the same key twice updates the value."""
    cache = RateCache()
    cache.set("USD", ["EUR"], "2025-01-01", "2025-01-05", "old")
    cache.set("USD", ["EUR"], "2025-01-01", "2025-01-05", "new")
    assert cache.get("USD", ["EUR"], "2025-01-01", "2025-01-05") == "new"


def test_cache_base_uppercased_in_key():
    """Lowercase base normalises to the same key as uppercase."""
    cache = RateCache()
    cache.set("usd", ["eur"], "2025-01-01", "2025-01-05", "value")
    assert cache.get("USD", ["EUR"], "2025-01-01", "2025-01-05") == "value"
