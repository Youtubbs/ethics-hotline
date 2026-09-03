"""Tests for the evidence pipeline, with mocked S3, Textract and Comprehend.

The uploaded bytes here are a tiny generated PNG header, not a real file
from anywhere, and any PII in the extracted text is invented.
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient

from ethics_hotline.errors import UpstreamAIError
from ethics_hotline.models import Report, db
from ethics_hotline.services.screening import REDACTION_MASK

VALID_TEXT = "Attaching a file about the incident that happened on the floor."
FAKE_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"generated-for-tests"


def _create_org(client: FlaskClient) -> dict:
    response = client.post(
        "/organizations", json={"name": "Acme Corp", "industry": "Manufacturing"}
    )
    assert response.status_code == 201
    return response.get_json()


def _submit_with_evidence(
    client: FlaskClient,
    org_id: int,
    content_type: str = "image/png",
    filename: str = "evidence.png",
    data: bytes = FAKE_PNG_BYTES,
):
    return client.post(
        f"/organizations/{org_id}/reports",
        data={
            "text": VALID_TEXT,
            "evidence": (io.BytesIO(data), filename, content_type),
        },
        content_type="multipart/form-data",
    )


def test_textract_lines_are_screened_and_stored(
    client: FlaskClient, fake_textract: MagicMock
) -> None:
    org = _create_org(client)
    fake_textract.detect_document_text.return_value = ["INCIDENT NOTE", "Dock area"]

    response = _submit_with_evidence(client, org["id"])

    assert response.status_code == 201
    body = response.get_json()
    assert body["evidence_text"] == "INCIDENT NOTE\nDock area"


def test_pii_in_evidence_text_is_redacted_like_the_body(
    client: FlaskClient, fake_textract: MagicMock, fake_comprehend: MagicMock
) -> None:
    """Evidence is not a side channel around the anonymity guarantee."""
    org = _create_org(client)
    extracted = "Contact Jamie Placeholder"
    fake_textract.detect_document_text.return_value = [extracted]

    def redact_only_evidence(text: str) -> list[dict]:
        if "Jamie Placeholder" not in text:
            return []
        start = text.index("Jamie Placeholder")
        return [
            {
                "BeginOffset": start,
                "EndOffset": start + len("Jamie Placeholder"),
                "Type": "NAME",
                "Score": 0.99,
            }
        ]

    fake_comprehend.detect_pii_entities.side_effect = redact_only_evidence

    response = _submit_with_evidence(client, org["id"])

    assert response.status_code == 201
    body = response.get_json()
    assert "Jamie Placeholder" not in body["evidence_text"]
    assert REDACTION_MASK in body["evidence_text"]
    assert body["contained_pii"] is True

    stored = db.session.get(Report, body["id"])
    assert "Jamie Placeholder" not in stored.evidence_text


def test_textract_failure_still_stores_the_report(
    client: FlaskClient, fake_textract: MagicMock
) -> None:
    """a failed attachment must not kill the submission."""
    org = _create_org(client)
    fake_textract.detect_document_text.side_effect = UpstreamAIError(
        "Textract document text extraction failed."
    )

    response = _submit_with_evidence(client, org["id"])

    assert response.status_code == 201
    body = response.get_json()
    assert body["evidence_text"] is None
    assert body["text"] == VALID_TEXT


def test_evidence_with_no_extractable_text_still_stores(
    client: FlaskClient, fake_textract: MagicMock
) -> None:
    """A photo with nothing readable is a legitimate outcome"""
    org = _create_org(client)
    fake_textract.detect_document_text.return_value = []

    response = _submit_with_evidence(client, org["id"])

    assert response.status_code == 201
    assert response.get_json()["evidence_text"] is None


def test_s3_failure_still_stores_the_report(
    client: FlaskClient, fake_s3: MagicMock, fake_textract: MagicMock
) -> None:
    org = _create_org(client)
    fake_s3.put_object.side_effect = UpstreamAIError("Failed to store evidence in S3.")

    response = _submit_with_evidence(client, org["id"])

    assert response.status_code == 201
    body = response.get_json()
    assert body["evidence_text"] is None
    fake_textract.detect_document_text.assert_not_called()


def test_evidence_screening_failure_drops_the_text_but_keeps_the_report(
    client: FlaskClient, fake_textract: MagicMock, fake_comprehend: MagicMock
) -> None:
    """Unscreened evidence text is dropped rather than stored.

    Keyed off the text itself rather than call order, since the evidence
    pipeline runs before the body is screened.
    """
    org = _create_org(client)
    extracted = "Some extracted line"
    fake_textract.detect_document_text.return_value = [extracted]

    def fail_only_on_the_evidence_text(text: str) -> list[dict]:
        if text == extracted:
            raise UpstreamAIError("Comprehend PII detection failed.")
        return []

    fake_comprehend.detect_pii_entities.side_effect = fail_only_on_the_evidence_text

    response = _submit_with_evidence(client, org["id"])

    assert response.status_code == 201
    body = response.get_json()
    assert body["evidence_text"] is None
    stored = db.session.get(Report, body["id"])
    assert stored.evidence_text is None


@pytest.mark.parametrize(
    ("content_type", "filename"),
    [("text/plain", "notes.txt"), ("application/zip", "bundle.zip")],
    ids=["plain_text", "zip_archive"],
)
def test_non_image_or_pdf_upload_is_rejected(
    client: FlaskClient, content_type: str, filename: str
) -> None:
    org = _create_org(client)

    response = _submit_with_evidence(
        client, org["id"], content_type=content_type, filename=filename
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_evidence_key_is_stored_but_never_returned(
    client: FlaskClient, fake_textract: MagicMock
) -> None:
    org = _create_org(client)
    fake_textract.detect_document_text.return_value = ["A line"]

    response = _submit_with_evidence(client, org["id"])

    assert response.status_code == 201
    body = response.get_json()
    assert "evidence_s3_key" not in body

    stored = db.session.get(Report, body["id"])
    assert stored.evidence_s3_key is not None
