"""Domain error hierarchy and the global error handler that renders it.

All errors raised anywhere in application code (routes, services, AWS
wrappers) must be a 'DomainError' subclass so a single error handler can
translate them into a consistent JSON envelope. Never raise a bare
'Exception' for an expected failure condition.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, g, jsonify
from pydantic import ValidationError as PydanticValidationError


class DomainError(Exception):
    """Base class for every error the application raises on purpose."""

    code: str = "domain_error"
    http_status: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(DomainError):
    """The caller supplied data that failed validation."""

    code = "validation_error"
    http_status = 422


class NotFoundError(DomainError):
    """The requested resource does not exist."""

    code = "not_found"
    http_status = 404


class ConflictError(DomainError):
    """The request conflicts with the current state of a resource."""

    code = "conflict"
    http_status = 409


class UpstreamAIError(DomainError):
    """A call to an upstream AWS AI service (Comprehend/Textract) failed."""

    code = "upstream_ai_error"
    http_status = 502


def _envelope(code: str, message: str) -> dict[str, Any]:
    """Build the standard error response body."""
    return {
        "error": {"code": code, "message": message},
        "request_id": g.get("correlation_id"),
    }


def register_error_handlers(app: Flask) -> None:
    """Register handlers that translate raised errors into the standard envelope."""

    @app.errorhandler(DomainError)
    def _handle_domain_error(error: DomainError) -> tuple[Response, int]:
        return jsonify(_envelope(error.code, error.message)), error.http_status

    @app.errorhandler(PydanticValidationError)
    def _handle_pydantic_validation_error(
        error: PydanticValidationError,
    ) -> tuple[Response, int]:
        return jsonify(_envelope("validation_error", str(error))), 422
