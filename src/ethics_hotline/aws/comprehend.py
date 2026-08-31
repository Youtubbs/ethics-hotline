"""wrapper around the two Comprehend operations this project uses.

Takes a boto3 session by constructor injection instead of importing
boto3 or building a client itself, so a test can construct this with a
fake session (one whose .client("comprehend") returns a stub or mock)
and never touch a real AWS endpoint.
"""

from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ethics_hotline.errors import UpstreamAIError

LANGUAGE_CODE = "en"


class ComprehendClient:
    """Wraps Comprehend's DetectPiiEntities and DetectKeyPhrases."""

    def __init__(self, session: boto3.Session) -> None:
        self._client = session.client("comprehend")

    def detect_pii_entities(self, text: str) -> list[dict[str, Any]]:
        """Return the PII entities Comprehend finds in text."""
        try:
            response = self._client.detect_pii_entities(
                Text=text, LanguageCode=LANGUAGE_CODE
            )
        except (BotoCoreError, ClientError) as exc:
            raise UpstreamAIError("Comprehend PII detection failed.") from exc
        return response["Entities"]

    def detect_key_phrases(self, text: str) -> list[str]:
        """Return the key phrases Comprehend finds in text."""
        try:
            response = self._client.detect_key_phrases(
                Text=text, LanguageCode=LANGUAGE_CODE
            )
        except (BotoCoreError, ClientError) as exc:
            raise UpstreamAIError("Comprehend key phrase detection failed.") from exc
        return [phrase["Text"] for phrase in response["KeyPhrases"]]