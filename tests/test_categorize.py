"""Tests for the category-suggestion path, with a mocked Comprehend wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient

from ethics_hotline.services.categorize import DEFAULT_CATEGORY, suggest_category

VALID_TEXT = "Something happened at work that somebody should look into soon."


def _create_org(client: FlaskClient) -> dict:
    response = client.post(
        "/organizations", json={"name": "Acme Corp", "industry": "Manufacturing"}
    )
    assert response.status_code == 201
    return response.get_json()


@pytest.mark.parametrize(
    ("phrases", "expected"),
    [
        (["a serious safety hazard", "the loading dock"], "safety"),
        (["ongoing harassment", "a hostile environment"], "harassment"),
        (["invoice fraud", "the accounting records"], "financial"),
    ],
    ids=["safety", "harassment", "financial"],
)
def test_confident_match_returns_that_category(
    fake_comprehend: MagicMock, phrases: list[str], expected: str
) -> None:
    fake_comprehend.detect_key_phrases.return_value = phrases

    assert suggest_category("redacted text", fake_comprehend) == expected


def test_no_confident_match_falls_back_to_other(fake_comprehend: MagicMock) -> None:
    fake_comprehend.detect_key_phrases.return_value = [
        "the vending machine",
        "last Tuesday afternoon",
    ]

    assert suggest_category("redacted text", fake_comprehend) == DEFAULT_CATEGORY


def test_no_key_phrases_at_all_falls_back_to_other(fake_comprehend: MagicMock) -> None:
    fake_comprehend.detect_key_phrases.return_value = []

    assert suggest_category("redacted text", fake_comprehend) == DEFAULT_CATEGORY


def test_category_with_the_most_hits_wins(fake_comprehend: MagicMock) -> None:
    """One incidental safety word loses to three financial ones."""
    fake_comprehend.detect_key_phrases.return_value = [
        "a safety concern",
        "invoice fraud",
        "the bribe payment",
        "falsified accounting",
    ]

    assert suggest_category("redacted text", fake_comprehend) == "financial"


def test_submission_without_a_category_stores_the_suggestion(
    client: FlaskClient, fake_comprehend: MagicMock
) -> None:
    org = _create_org(client)
    fake_comprehend.detect_key_phrases.return_value = ["a serious safety hazard"]

    response = client.post(f"/organizations/{org['id']}/reports", json={"text": VALID_TEXT})

    assert response.status_code == 201
    body = response.get_json()
    assert body["category"] is None
    assert body["suggested_category"] == "safety"


def test_supplied_category_is_never_overridden(
    client: FlaskClient, fake_comprehend: MagicMock
) -> None:
    """A submitted category with no suggestion entirely."""
    org = _create_org(client)

    response = client.post(
        f"/organizations/{org['id']}/reports",
        json={"text": VALID_TEXT, "category": "financial"},
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["category"] == "financial"
    assert body["suggested_category"] is None
    fake_comprehend.detect_key_phrases.assert_not_called()


def test_suggestion_runs_on_the_redacted_text_not_the_original(
    client: FlaskClient, fake_comprehend: MagicMock
) -> None:
    """Categorization must never see the unredacted submission."""
    org = _create_org(client)
    text = "Jamie Placeholder reported a serious safety hazard on the floor."
    fake_comprehend.detect_pii_entities.return_value = [
        {
            "BeginOffset": 0,
            "EndOffset": len("Jamie Placeholder"),
            "Type": "NAME",
            "Score": 0.99,
        }
    ]
    fake_comprehend.detect_key_phrases.return_value = ["a serious safety hazard"]

    response = client.post(f"/organizations/{org['id']}/reports", json={"text": text})

    assert response.status_code == 201
    categorized_text = fake_comprehend.detect_key_phrases.call_args.args[0]
    assert "Jamie Placeholder" not in categorized_text
