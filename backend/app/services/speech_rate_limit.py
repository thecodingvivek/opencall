"""Small per-process limit for authenticated direct speech requests."""
from collections import deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException

from app.api.routes.auth import CurrentUser

LIMIT = 20
WINDOW_SECONDS = 60
_requests: dict[str, deque[float]] = {}
_lock = Lock()


def limit_speech_requests(user: CurrentUser) -> None:
    now = monotonic()
    user_id = str(user['username'])
    with _lock:
        # Prune idle users so this process does not retain them indefinitely.
        for key in list(_requests):
            if not _requests[key] or _requests[key][-1] <= now - WINDOW_SECONDS:
                del _requests[key]
        recent = _requests.setdefault(user_id, deque())
        while recent and recent[0] <= now - WINDOW_SECONDS:
            recent.popleft()
        if len(recent) >= LIMIT:
            retry = max(1, int(WINDOW_SECONDS - (now - recent[0])) + 1)
            raise HTTPException(429, "Too many speech requests. Please try again later.",
                                headers={"Retry-After": str(retry)})
        recent.append(now)
