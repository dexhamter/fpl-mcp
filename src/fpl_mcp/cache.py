"""Simple in-memory TTL cache for FPL API responses."""

import time
from typing import Any, Optional


class TTLCache:
    """Thread-safe in-memory cache with per-entry TTL."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Return cached value if present and not expired, else None."""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Store value with a TTL (seconds)."""
        self._store[key] = (value, time.monotonic() + ttl)

    def invalidate(self, key: str) -> None:
        """Remove a specific key."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()

    def stats(self) -> dict:
        """Return cache statistics."""
        now = time.monotonic()
        alive = sum(1 for _, (_, exp) in self._store.items() if exp > now)
        return {"total_entries": len(self._store), "alive": alive, "expired": len(self._store) - alive}
