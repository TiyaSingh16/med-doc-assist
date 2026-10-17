import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, status

from app.config import settings
from app.models.user import User
from app.utils.dependencies import get_current_user


class SlidingWindowLimiter:
    """At most `limit` calls per `window` seconds per key (here: per user).

    Every LLM call costs money and takes seconds, so one user (or a stolen
    token) must not be able to fire them in a loop. Kept in process memory:
    simple and enough for one instance; with several instances each would
    keep its own count (a shared store such as Redis would fix that).
    """

    def __init__(self, limit: int, window_seconds: float = 60.0, clock=time.monotonic):
        self.limit = limit
        self.window = window_seconds
        self.clock = clock
        self._calls: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> float | None:
        """Record a call. Returns None if allowed, else seconds until a slot frees up."""
        now = self.clock()
        with self._lock:
            calls = self._calls[key]
            while calls and now - calls[0] >= self.window:
                calls.popleft()
            if len(calls) >= self.limit:
                return self.window - (now - calls[0])
            calls.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._calls.clear()


llm_limiter = SlidingWindowLimiter(limit=settings.llm_requests_per_minute)


def limit_llm_calls(current_user: User = Depends(get_current_user)) -> User:
    retry_after = llm_limiter.check(str(current_user.id))
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a moment and try again.",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )
    return current_user
