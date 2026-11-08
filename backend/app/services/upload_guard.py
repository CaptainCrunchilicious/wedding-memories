import asyncio
import time
from collections import defaultdict, deque


class UploadRateLimitError(Exception):
    pass


class UploadGuard:
    """Process-local rolling limits; use a shared store before multi-instance deployment."""

    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._sessions: dict[str, tuple[int, int, float]] = {}
        self._lock = asyncio.Lock()

    async def allow_ip(self, category: str, ip: str, maximum: int, window: int = 3600) -> None:
        async with self._lock:
            now = time.monotonic()
            bucket = self._events[(category, ip)]
            while bucket and bucket[0] <= now - window:
                bucket.popleft()
            if len(bucket) >= maximum:
                raise UploadRateLimitError("Too many upload requests. Please try again later.")
            bucket.append(now)

    async def consume_session(
        self, jti: str, count: int, size: int, max_count: int, max_size: int, expires_at: float
    ) -> None:
        async with self._lock:
            now = time.time()
            self._sessions = {key: value for key, value in self._sessions.items() if value[2] > now}
            old_count, old_size, _ = self._sessions.get(jti, (0, 0, expires_at))
            if old_count + count > max_count or old_size + size > max_size:
                raise UploadRateLimitError("This upload session has reached its photo or data limit.")
            self._sessions[jti] = old_count + count, old_size + size, expires_at
