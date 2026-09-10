"""Small in-process rate limits for the single Render web instance.

This is intentionally not a distributed security boundary. It limits accidental abuse and
cheap provider/upload exhaustion without introducing Redis; a future multi-instance deployment
must move these counters to a shared store or an edge provider.
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque
from threading import Lock

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class InProcessRateLimitMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    @staticmethod
    def _client_key(scope: Scope) -> str:
        client = scope.get("client")
        address = client[0] if client else "unknown"
        headers = dict(scope.get("headers", []))
        session = headers.get(b"cookie", b"")
        # A cookie hash lets authenticated clients behind a shared proxy get a separate bucket
        # without retaining a session token in process memory.
        return f"{address}:{hashlib.sha256(session).hexdigest()[:16]}"

    @staticmethod
    def _policy(path: str, method: str) -> tuple[str, int, int] | None:
        if method == "GET" and path == "/auth/google/login":
            return "oauth", 10, 60
        if method == "GET" and path.startswith("/api/integrations/"):
            return "provider", 60, 60
        if method == "POST" and path.endswith("/invitations"):
            return "invite", 10, 15 * 60
        if method == "POST" and path.endswith("/media"):
            return "upload", 20, 10 * 60
        return None

    def _allowed(self, key: str, limit: int, window: int) -> bool:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            cutoff = now - window
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            # Keep the map bounded even when an attacker continually rotates IPs and
            # cookies. Do not let the limiter become its own memory-exhaustion vector.
            if len(self._events) > 4096:
                oldest = sorted(
                    self._events.items(),
                    key=lambda item: item[1][-1] if item[1] else float("-inf"),
                )
                for name, _ in oldest[:1024]:
                    self._events.pop(name, None)
            return True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            policy = self._policy(scope.get("path", ""), scope.get("method", ""))
            if policy:
                bucket, limit, window = policy
                if not self._allowed(f"{bucket}:{self._client_key(scope)}", limit, window):
                    response = JSONResponse(
                        {"detail": "Too many requests; try again shortly"},
                        status_code=429,
                        headers={"Retry-After": str(window)},
                    )
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)
