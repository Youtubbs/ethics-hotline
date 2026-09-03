"""Tests for the PII screening path, with a mocked Comprehend wrapper"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient

from ethics_hotline.errors import UpstreamAIError
from ethics_hotline.models import Report, db
from ethics_hotline.services.screening import REDACTION_MASK, screen_text

CLEAN_TEXT = "There is a hazard near the loading dock that has gone unfixed."


def _pii_entity(begin: int, end: int, entity_type: str = "NAME") -> dict:
    """Build a DetectPiiEntities entity the way Comprehend returns one."""
    return {"BeginOffset": begin, "EndOffset": end, "Type": entity_type, "Score": 0.99}


def _create_org(client: FlaskClient) -> dict:
    response = client.post(
        "/organizations", json={"name": "Acme Corp", "industry": "Manufacturing"}
    )
    assert response.status_code == 201
    return response.get_json()


def test_screen_text_redacts_a_detected_span(fake_comprehend: MagicMock) -> None:
    text = "Contact Jamie Placeholder about this."
    start, end = text.index("Jamie Placeholder"), text.index(" about")
    fake_comprehend.detect_pii_entities.return_value = [_pii_entity(start, end)]

    result = screen_text(text, fake_comprehend)

    assert result.contained_pii is True
    assert "Jamie Placeholder" not in result.text
    assert REDACTION_MASK in result.text


def test_screen_text_redacts_multiple_spans_without_shifting_offsets(
    fake_comprehend: MagicMock,
) -> None:
    """Later spans must not be corrupted by redacting earlier ones."""
    text = "Jamie Placeholder emailed jamie.placeholder@example.com yesterday."
    fake_comprehend.detect_pii_entities.return_value = [
        _pii_entity(0, len("Jamie Placeholder"), "NAME"),
        _pii_entity(
            text.index("jamie.placeholder@example.com"),
            text.index(" yesterday"),
            "EMAIL",
        ),
    ]

    result = screen_text(text, fake_comprehend)

    assert result.contained_pii is True
    assert "Jamie Placeholder" not in result.text
    assert "jamie.placeholder@example.com" not in result.text
    assert result.text.count(REDACTION_MASK) == 2
    assert result.text.endswith("yesterday.")


def test_screen_text_leaves_clean_text_alone(fake_comprehend: MagicMock) -> None:
    result = screen_text(CLEAN_TEXT, fake_comprehend)

    assert result.text == CLEAN_TEXT
    assert result.contained_pii is False


def test_submitted_report_stores_only_redacted_text(
    client: FlaskClient, fake_comprehend: MagicMock
) -> None:
    """The row must never hold the original text once PII is detected."""
    org = _create_org(client)
    text = "My manager Jamie Placeholder shouted at me during the shift meeting."
    fake_comprehend.detect_pii_entities.return_value = [
        _pii_entity(text.index("Jamie Placeholder"), text.index(" shouted"))
    ]

    response = client.post(
        f"/organizations/{org['id']}/reports", json={"text": text, "category": "harassment"}
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["contained_pii"] is True
    assert "Jamie Placeholder" not in body["text"]

    stored = db.session.get(Report, body["id"])
    assert "Jamie Placeholder" not in stored.text
    assert REDACTION_MASK in stored.text


def test_comprehend_failure_rejects_submission_and_persists_nothing(
    client: FlaskClient, fake_comprehend: MagicMock
) -> None:
    """Screening fails 502 through the envelope, with no row written."""
    org = _create_org(client)
    fake_comprehend.detect_pii_entities.side_effect = UpstreamAIError(
        "Comprehend PII detection failed."
    )
    before = db.session.query(Report).filter_by(organization_id=org["id"]).count()

    response = client.post(
        f"/organizations/{org['id']}/reports",
        json={"text": "This submission must never be stored unscreened."},
    )

    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "upstream_ai_error"
    after = db.session.query(Report).filter_by(organization_id=org["id"]).count()
    assert after == before


@pytest.mark.parametrize("text", ["short", "still too short"])
def test_text_below_the_minimum_never_reaches_comprehend(
    client: FlaskClient, fake_comprehend: MagicMock, text: str
) -> None:
    org = _create_org(client)

    response = client.post(f"/organizations/{org['id']}/reports", json={"text": text})

    assert response.status_code == 422
    fake_comprehend.detect_pii_entities.assert_not_called()
