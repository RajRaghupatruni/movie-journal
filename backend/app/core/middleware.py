import logging
import time
from uuid import UUID, uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id

logger = logging.getLogger(__name__)


def safe_route(path: str) -> str:
    """Keep useful route context while never logging opaque invitation references."""
    parts = path.split("/")
    for index, part in enumerate(parts[:-1]):
        if part == "invitations":
            parts[index + 1] = ":reference"
    return "/".join(parts) or "/"


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        try:
            correlation_id = str(UUID(headers.get(b"x-request-id", b"").decode("ascii")))
        except (ValueError, UnicodeDecodeError):
            correlation_id = str(uuid4())
        token = request_id.set(correlation_id)
        started = time.perf_counter()
        status_code = 500
        response_started = False
        route = safe_route(scope.get("path", "/"))

        async def send_with_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_started = True
                message["headers"] = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ] + [(b"x-request-id", correlation_id.encode("ascii"))]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception as exc:
            logger.error(
                "request_failed", extra={"route": route, "error_class": type(exc).__name__}
            )
            if not response_started:
                response = JSONResponse({"detail": "Internal server error"}, status_code=500)
                await response(scope, receive, send_with_id)
            else:
                raise RuntimeError("Response interrupted") from None
        finally:
            logger.info(
                "request_completed",
                extra={
                    "method": scope["method"],
                    "route": route,
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            request_id.reset(token)
