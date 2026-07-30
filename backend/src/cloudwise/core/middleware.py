"""Request safety and observability middleware."""

from uuid import UUID, uuid4

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware:
    """Bind a safe correlation ID and security headers to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw_headers = dict(scope.get("headers", []))
        supplied = raw_headers.get(CORRELATION_HEADER.lower().encode(), b"").decode()
        try:
            correlation_id = str(UUID(supplied)) if supplied else str(uuid4())
        except ValueError:
            correlation_id = str(uuid4())

        tokens = structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers[CORRELATION_HEADER] = correlation_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                if scope["path"] in {"/api/docs", "/api/redoc"}:
                    headers["Content-Security-Policy"] = (
                        "default-src 'none'; "
                        "script-src https://cdn.jsdelivr.net; "
                        "style-src 'unsafe-inline' https://cdn.jsdelivr.net; "
                        "img-src data: https://fastapi.tiangolo.com; "
                        "frame-ancestors 'none'"
                    )
                else:
                    headers["Content-Security-Policy"] = (
                        "default-src 'none'; frame-ancestors 'none'"
                    )
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        finally:
            structlog.contextvars.reset_contextvars(**tokens)


class RequestSizeLimitMiddleware:
    """Reject known oversized request bodies before route processing."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            raw_length = headers.get(b"content-length")
            if raw_length is not None:
                try:
                    is_too_large = int(raw_length) > self.max_bytes
                except ValueError:
                    is_too_large = True
                if is_too_large:
                    await self._send_too_large(send)
                    return
        await self.app(scope, receive, send)

    @staticmethod
    async def _send_too_large(send: Send) -> None:
        body = b'{"detail":"Request body is too large"}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
