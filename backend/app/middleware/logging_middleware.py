"""
HTTP request/response logging middleware.

Emits one structured log record per request containing:
  method        GET | POST | …
  path          URL path (no query string, no PII in path params)
  status_code   HTTP response status
  duration_ms   Wall-clock time in milliseconds
  request_id    Random UUID injected into every request for log correlation

The request_id is also returned in the X-Request-ID response header so
frontend error reports can be correlated with server logs.
"""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        # Make request_id available to downstream handlers via request.state
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.error(
                "Unhandled exception during request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "error": str(exc),
                },
                exc_info=True,
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(
            level,
            f"{request.method} {request.url.path} {response.status_code}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response
