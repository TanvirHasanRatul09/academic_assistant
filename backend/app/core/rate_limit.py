import time
from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock

from fastapi import HTTPException, Request, status

_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def rate_limit(name: str, limit: int, window_seconds: int) -> Callable[[Request], None]:
    def check(request: Request) -> None:
        host = request.client.host if request.client else "unknown"
        key = f"{name}:{host}"
        now = time.monotonic()
        with _lock:
            attempts = _attempts[key]
            while attempts and attempts[0] <= now - window_seconds:
                attempts.popleft()
            if len(attempts) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests; try again later",
                )
            attempts.append(now)

    return check
