"""PII redaction shared by the report body and, later, evidence text.

Screening always runs before anything is persisted. A Comprehend failure
is not caught here: it propagates as UpstreamAIError from the wrapper, so
callers fail closed rather than storing unscreened text.
"""

from __future__ import annotations

from dataclasses import dataclass

from ethics_hotline.aws.comprehend import ComprehendClient

REDACTION_MASK = "[REDACTED]"


@dataclass(frozen=True)
class ScreeningResult:
    """The outcome of screening one piece of text for PII."""

    text: str
    contained_pii: bool


def screen_text(text: str, comprehend: ComprehendClient) -> ScreeningResult:
    """Detect PII in text and return a copy with every span redacted in place.

    Spans are replaced back to front by BeginOffset so redacting one span
    never shifts the offsets of spans still waiting to be redacted.
    """
    entities = comprehend.detect_pii_entities(text)
    if not entities:
        return ScreeningResult(text=text, contained_pii=False)

    redacted = text
    for entity in sorted(entities, key=lambda e: e["BeginOffset"], reverse=True):
        start, end = entity["BeginOffset"], entity["EndOffset"]
        redacted = redacted[:start] + REDACTION_MASK + redacted[end:]

    return ScreeningResult(text=redacted, contained_pii=True)
