"""Structured JSON logging configuration.

Configures structlog to emit one JSON object per log line and exposes
'bind_correlation_id', which a later request-logging middleware calls to
generate (or reuse) a per-request correlation id and bind it to every log
line emitted while handling that request. No code in this module wires
that middleware in; it only provides the pieces for it to use.
"""

from __future__ import annotations

import logging
import uuid

import structlog

from ethics_hotline.config import settings


def configure_logging() -> None:
    """Configure structlog and stdlib logging for machine-parseable JSON output."""
    logging.basicConfig(
        format="%(message)s",
        level=settings.log_level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def bind_correlation_id(correlation_id: str | None = None) -> str:
    """Bind a correlation id to the current structlog context and return it.

    If 'correlation_id' is not supplied, a new one is generated. Intended
    to be called once per request by request-logging middleware added later.
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    return correlation_id


def get_logger(*args: object, **kwargs: object) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to the current context."""
    return structlog.get_logger(*args, **kwargs)
