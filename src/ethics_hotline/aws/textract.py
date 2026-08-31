"""Narrow wrapper around Textract's DetectDocumentText.

Takes a boto3 session by constructor injection, matching comprehend.py
and s3.py, so it can be swapped for a fake in tests.
"""

from __future__ import annotations

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ethics_hotline.errors import UpstreamAIError


class TextractClient:
    """Wraps Textract's DetectDocumentText."""

    def __init__(self, session: boto3.Session) -> None:
        self._client = session.client("textract")

    def detect_document_text(self, document_bytes: bytes) -> list[str]:
        """Return the extracted text lines, or an empty list if none are found.

        A document with no readable text is a legitimate result, not a
        failure. only a genuine BotoCoreError or ClientError from the
        service becomes an UpstreamAIError.
        """
        try:
            response = self._client.detect_document_text(
                Document={"Bytes": document_bytes}
            )
        except (BotoCoreError, ClientError) as exc:
            raise UpstreamAIError("Textract document text extraction failed.") from exc

        return [
            block["Text"]
            for block in response.get("Blocks", [])
            if block["BlockType"] == "LINE"
        ]
