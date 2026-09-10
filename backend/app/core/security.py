"""Same-origin and browser hardening middleware."""

from __future__ import annotations

from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import Settings


class SameOriginMiddleware:
    unsafe_methods = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings
        parsed = urlsplit(settings.frontend_url)
        self.expected_origin = f"{parsed.scheme}://{parsed.netloc}"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and self.settings.app_env == "production"
            and scope.get("method") in self.unsafe_methods
            and scope.get("path") not in {"/auth/google/callback"}
        ):
            headers = dict(scope.get("headers", []))
            origin = headers.get(b"origin", b"").decode("latin-1")
            referer = headers.get(b"referer", b"").decode("latin-1")
            source = origin or (
                f"{urlsplit(referer).scheme}://{urlsplit(referer).netloc}" if referer else ""
            )
            if source != self.expected_origin:
                response = JSONResponse({"detail": "Cross-site request blocked"}, status_code=403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings
        image_sources = [
            "'self'",
            "data:",
            "blob:",
            "https://image.tmdb.org",
            "https://*.googleusercontent.com",
            "https://*.backblazeb2.com",
        ]
        if settings.s3_endpoint_url:
            host = urlsplit(settings.s3_endpoint_url).netloc
            if host:
                image_sources.append(f"https://{host}")
        self.csp = "; ".join(
            [
                "default-src 'self'",
                "base-uri 'self'",
                "object-src 'none'",
                "script-src 'self'",
                "style-src 'self' 'unsafe-inline'",
                f"img-src {' '.join(image_sources)}",
                "font-src 'self' data:",
                "connect-src 'self'",
                "form-action 'self' https://accounts.google.com",
                "frame-ancestors 'none'",
            ]
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {key.lower() for key, _ in headers}
                security_headers = {
                    b"content-security-policy": self.csp.encode("ascii"),
                    b"referrer-policy": b"no-referrer",
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"permissions-policy": b"camera=(), microphone=(), geolocation=()",
                }
                if self.settings.app_env == "production":
                    security_headers[b"strict-transport-security"] = (
                        b"max-age=31536000; includeSubDomains"
                    )
                headers.extend(
                    (key, value) for key, value in security_headers.items() if key not in existing
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
