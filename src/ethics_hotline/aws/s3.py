"""Wrapper for storing and retrieving evidence objects in S3.

Takes a boto3 session and the target bucket name by constructor
injection, matching comprehend.py and textract.py. The bucket name comes
from the caller (ultimately settings.aws_s3_bucket), never read from the
environment by this module directly.

Wiring this into the evidence-upload path is for later.
"""

from __future__ import annotations

import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ethics_hotline.errors import UpstreamAIError


class S3Client:
    """Wraps S3's PutObject and GetObject for the evidence bucket."""

    def __init__(self, session: boto3.Session, bucket: str) -> None:
        self._client = session.client("s3")
        self._bucket = bucket

    def put_object(self, data: bytes, extension: str) -> str:
        """Store data under a non-guessable key and return that key.

        No endpoint ever hands this key back to a caller as a way to
        fetch the file directly; it exists only for this wrapper's own
        later get_object call (e.g. to hand the bytes to Textract).
        """
        suffix = f".{extension.lstrip('.')}" if extension else ""
        key = f"evidence/{uuid.uuid4().hex}{suffix}"
        try:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
        except (BotoCoreError, ClientError) as exc:
            raise UpstreamAIError("Failed to store evidence in S3.") from exc
        return key

    def get_object(self, key: str) -> bytes:
        """Fetch back the bytes stored under key."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise UpstreamAIError("Failed to retrieve evidence from S3.") from exc
        return response["Body"].read()