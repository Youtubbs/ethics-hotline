"""Evidence pipeline: validate an upload, store it, extract text, screen it.

The extracted text goes through screen_text, the same redaction function
the report body uses, so evidence is never a way around the anonymity
guarantee.

Everything past validation is best effort. Validation failures reject the
submission, but a storage or extraction failure only costs the evidence
text: the report itself still stores, screened. See docs/decisions.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from werkzeug.datastructures import FileStorage

from ethics_hotline.aws.comprehend import ComprehendClient
from ethics_hotline.aws.s3 import S3Client
from ethics_hotline.aws.textract import TextractClient
from ethics_hotline.errors import UpstreamAIError, ValidationError
from ethics_hotline.logging import get_logger
from ethics_hotline.services.screening import screen_text

logger = get_logger(__name__)

# Formats Textract's synchronous DetectDocumentText accepts.
ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/tiff": "tiff",
    "application/pdf": "pdf",
}


@dataclass(frozen=True)
class EvidenceResult:
    """What the evidence pipeline managed to produce for a report."""

    s3_key: Optional[str] = None
    screened_text: Optional[str] = None
    contained_pii: bool = False


def validate_evidence(upload: FileStorage, max_bytes: int) -> bytes:
    """Check the upload's type and size, then return its bytes.

    The content type is rejected before anything is read. Flask's
    MAX_CONTENT_LENGTH already refuses an oversized body at the WSGI
    layer before it reaches here; the size check below is the backstop
    for a request that understated its length.
    """
    content_type = (upload.mimetype or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            f"Unsupported evidence type {content_type or 'unknown'}. "
            f"Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}."
        )

    declared_length = upload.content_length
    if declared_length and declared_length > max_bytes:
        raise ValidationError(
            f"Evidence file is larger than the {max_bytes} byte limit."
        )

    data = upload.read()
    if len(data) > max_bytes:
        raise ValidationError(
            f"Evidence file is larger than the {max_bytes} byte limit."
        )
    if not data:
        raise ValidationError("Evidence file is empty.")

    return data


def process_evidence(
    data: bytes,
    content_type: str,
    s3: S3Client,
    textract: TextractClient,
    comprehend: ComprehendClient,
) -> EvidenceResult:
    """Store the file, extract its text, and screen that text.

    Returns whatever succeeded. A failure anywhere in here is logged and
    swallowed so the report still lands: unscreened evidence text is
    simply never stored.
    """
    extension = ALLOWED_CONTENT_TYPES.get(content_type.lower(), "")

    try:
        s3_key = s3.put_object(data, extension)
    except UpstreamAIError:
        logger.warning("evidence_store_failed")
        return EvidenceResult()

    try:
        lines = textract.detect_document_text(s3.get_object(s3_key))
    except UpstreamAIError:
        logger.warning("evidence_extraction_failed", s3_key=s3_key)
        return EvidenceResult(s3_key=s3_key)

    if not lines:
        # A photo with no readable text is a legitimate outcome.
        logger.info("evidence_had_no_text", s3_key=s3_key)
        return EvidenceResult(s3_key=s3_key)

    try:
        screened = screen_text("\n".join(lines), comprehend)
    except UpstreamAIError:
        # Never store text that was not screened.
        logger.warning("evidence_screening_failed", s3_key=s3_key)
        return EvidenceResult(s3_key=s3_key)

    return EvidenceResult(
        s3_key=s3_key,
        screened_text=screened.text,
        contained_pii=screened.contained_pii,
    )
