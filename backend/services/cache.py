"""
Evaluation Cache — SHA256-based LRU cache for evaluation results.

Prevents re-evaluating the same document twice.
Cache key: sha256(file_bytes) + evaluation_mode + institution

Thread-safe using a simple lock + OrderedDict for LRU eviction.
"""
import hashlib
import logging
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional

logger = logging.getLogger("thesis_ai.cache")

MAX_CACHE_SIZE = 50  # Keep last 50 evaluations in memory


class EvaluationCache:
    """
    Thread-safe in-memory LRU cache for evaluation results.

    Key: sha256(file_bytes):evaluation_mode:institution
    Value: full evaluation result dict (same shape returned by evaluate_thesis)
    """

    def __init__(self, max_size: int = MAX_CACHE_SIZE):
        self._store: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    # ── Public API ─────────────────────────────────────────────────────────────

    def make_key(self, file_bytes: bytes, mode: str, institution: str) -> str:
        """Generate a deterministic cache key from file content + evaluation params."""
        digest = hashlib.sha256(file_bytes).hexdigest()
        return f"{digest}:{mode}:{institution}"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Return cached result if present, else None. Moves hit to end (most-recently-used)."""
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._hits += 1
                logger.info(f"Cache HIT for key {key[:16]}... (total hits={self._hits})")
                return self._store[key]
            self._misses += 1
            return None

    def set(self, key: str, result: Dict[str, Any]) -> None:
        """Store a result. Evicts oldest entry if over capacity."""
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = result
            if len(self._store) > self._max_size:
                evicted_key, _ = self._store.popitem(last=False)
                logger.info(f"Cache evicted LRU key {evicted_key[:16]}...")
            logger.info(f"Cache SET for key {key[:16]}... (size={len(self._store)})")

    def stats(self) -> Dict[str, int]:
        """Return cache statistics for monitoring."""
        with self._lock:
            return {
                "size": len(self._store),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_pct": round(self._hits * 100 / max(self._hits + self._misses, 1)),
            }

    def clear(self) -> None:
        """Flush the entire cache."""
        with self._lock:
            self._store.clear()
            logger.info("Cache cleared.")


# ── Module-level singleton ─────────────────────────────────────────────────────

_cache_instance: Optional[EvaluationCache] = None


def get_cache() -> EvaluationCache:
    """Get or create the global evaluation cache singleton."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = EvaluationCache(max_size=MAX_CACHE_SIZE)
    return _cache_instance
