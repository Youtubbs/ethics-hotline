"""Domain error hierarchy.

All errors raised anywhere in application code (routes, services, AWS
wrappers) must be a 'DomainError' subclass so a single error handler can
translate them into a consistent JSON envelope. Never raise a bare
'Exception' for an expected failure condition.
"""

from __future__ import annotations


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
