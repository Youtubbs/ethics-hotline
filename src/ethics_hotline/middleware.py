"""Request logging middleware.

Binds a per-request correlation id on the way in and emits one structured
JSON log line per request on the way out, with method, path, status code
and duration.
"""

from __future__ import annotations

import time

from flask import Flask, Response, g, request

from ethics_hotline.logging import bind_correlation_id, get_logger

logger = get_logger(__name__)


def register_request_logging(app: Flask) -> None:
    """Attach before/after request hooks that log one line per request."""

    @app.before_request
    def _start_request() -> None:
        g.correlation_id = bind_correlation_id(request.headers.get("X-Correlation-Id"))
        g.request_start_time = time.monotonic()

    @app.after_request
    def _log_request(response: Response) -> Response:
        duration_ms = (time.monotonic() - g.request_start_time) * 1000
        logger.info(
            "request_completed",
            method=request.method,
            path=request.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
            correlation_id=g.correlation_id,
        )
        response.headers["X-Correlation-Id"] = g.correlation_id
        return response
