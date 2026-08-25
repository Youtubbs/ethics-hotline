"""Tests for the reports blueprint"""

from __future__ import annotations

import pytest
from flask.testing import FlaskClient

VALID_TEXT = "this is a sufficiently long synthetic report body for testing"


def _create_org(client: FlaskClient) -> dict:
    response = client.post("/organizations", json={"name": "Acme Corp", "industry": "Manufacturing"})
    assert response.status_code == 201
    return response.get_json()


def _submit_report(client: FlaskClient, org_id: int, **overrides: object) -> dict:
    payload = {"text": VALID_TEXT, **overrides}
    response = client.post(f"/organizations/{org_id}/reports", json=payload)
    assert response.status_code == 201
    return response.get_json()


def test_submit_report_happy_path(client: FlaskClient) -> None:
    org = _create_org(client)

    response = client.post(
        f"/organizations/{org['id']}/reports",
        json={"text": VALID_TEXT, "category": "safety"},
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["text"] == VALID_TEXT
    assert body["category"] == "safety"
    assert body["contained_pii"] is False
    assert body["suggested_category"] is None
    assert body["status"] == "new"


def test_submit_report_against_unknown_organization_returns_404(client: FlaskClient) -> None:
    response = client.post("/organizations/999999/reports", json={"text": VALID_TEXT})

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"text": "too short"},
        {"text": VALID_TEXT, "category": "not-a-real-category"},
        {},
    ],
    ids=["text_too_short", "invalid_category", "missing_text"],
)
def test_submit_report_rejects_invalid_payloads(client: FlaskClient, payload: dict) -> None:
    org = _create_org(client)

    response = client.post(f"/organizations/{org['id']}/reports", json=payload)

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_list_reports_filters_by_category_and_status(client: FlaskClient) -> None:
    org = _create_org(client)
    safety = _submit_report(client, org["id"], category="safety")
    _submit_report(client, org["id"], category="financial")
    client.patch(
        f"/organizations/{org['id']}/reports/{safety['id']}",
        json={"status": "under_review", "version": 1},
    )

    by_category = client.get(f"/organizations/{org['id']}/reports?category=financial")
    assert by_category.status_code == 200
    assert {r["category"] for r in by_category.get_json()} == {"financial"}

    by_status = client.get(f"/organizations/{org['id']}/reports?status=under_review")
    assert by_status.status_code == 200
    assert [r["id"] for r in by_status.get_json()] == [safety["id"]]


def test_list_reports_sort_and_date_filter(client: FlaskClient) -> None:
    # Two reports submitted back-to-back can land on the same submitted_at
    # timestamp, so this checks sort-order monotonically
    org = _create_org(client)
    _submit_report(client, org["id"])
    _submit_report(client, org["id"])

    ascending_times = [r["submitted_at"] for r in client.get(f"/organizations/{org['id']}/reports").get_json()]
    assert ascending_times == sorted(ascending_times)

    descending = client.get(f"/organizations/{org['id']}/reports?sort=-submitted_at")
    descending_times = [r["submitted_at"] for r in descending.get_json()]
    assert descending_times == sorted(descending_times, reverse=True)

    future_only = client.get(f"/organizations/{org['id']}/reports?since=2099-01-01T00:00:00")
    assert future_only.get_json() == []


@pytest.mark.parametrize(
    "query",
    ["category=not-a-category", "status=not-a-status", "sort=not-a-field"],
    ids=["bad_category", "bad_status", "bad_sort"],
)
def test_list_reports_rejects_unknown_filter_values(client: FlaskClient, query: str) -> None:
    org = _create_org(client)

    response = client.get(f"/organizations/{org['id']}/reports?{query}")

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_status_transition_happy_path(client: FlaskClient) -> None:
    org = _create_org(client)
    report = _submit_report(client, org["id"])

    response = client.patch(
        f"/organizations/{org['id']}/reports/{report['id']}",
        json={"status": "under_review", "version": 1},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "under_review"


def test_illegal_status_transition_returns_409(client: FlaskClient) -> None:
    org = _create_org(client)
    report = _submit_report(client, org["id"])
    client.patch(
        f"/organizations/{org['id']}/reports/{report['id']}",
        json={"status": "under_review", "version": 1},
    )

    response = client.patch(
        f"/organizations/{org['id']}/reports/{report['id']}",
        json={"status": "new", "version": 2},
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "conflict"


def test_closed_report_reopens_to_under_review(client: FlaskClient) -> None:
    org = _create_org(client)
    report = _submit_report(client, org["id"])
    client.patch(
        f"/organizations/{org['id']}/reports/{report['id']}",
        json={"status": "closed", "version": 1},
    )

    response = client.patch(
        f"/organizations/{org['id']}/reports/{report['id']}",
        json={"status": "under_review", "version": 2},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "under_review"


def test_status_update_unknown_report_returns_404(client: FlaskClient) -> None:
    org = _create_org(client)

    response = client.patch(
        f"/organizations/{org['id']}/reports/999999",
        json={"status": "closed", "version": 1},
    )

    assert response.status_code == 404


def test_concurrent_status_update_loser_gets_409(client: FlaskClient) -> None:
    """Proves the EH-22 requirement: of two racing updates, the stale one loses."""
    org = _create_org(client)
    report = _submit_report(client, org["id"])

    winner = client.patch(
        f"/organizations/{org['id']}/reports/{report['id']}",
        json={"status": "under_review", "version": 1},
    )
    assert winner.status_code == 200

    loser = client.patch(
        f"/organizations/{org['id']}/reports/{report['id']}",
        json={"status": "closed", "version": 1},
    )

    assert loser.status_code == 409
    assert loser.get_json()["error"]["code"] == "conflict"


def test_updating_a_deleted_report_returns_404(client: FlaskClient) -> None:
    org = _create_org(client)
    report = _submit_report(client, org["id"])
    delete_response = client.delete(
        f"/organizations/{org['id']}/reports/{report['id']}",
        json={"admin": True, "confirm_id": report["id"]},
    )
    assert delete_response.status_code == 204

    response = client.patch(
        f"/organizations/{org['id']}/reports/{report['id']}",
        json={"status": "closed", "version": 1},
    )

    assert response.status_code == 404


def test_delete_report_happy_path(client: FlaskClient) -> None:
    org = _create_org(client)
    report = _submit_report(client, org["id"])

    response = client.delete(
        f"/organizations/{org['id']}/reports/{report['id']}",
        json={"admin": True, "confirm_id": report["id"]},
    )

    assert response.status_code == 204


def test_delete_report_unknown_id_returns_404(client: FlaskClient) -> None:
    org = _create_org(client)

    response = client.delete(
        f"/organizations/{org['id']}/reports/999999",
        json={"admin": True, "confirm_id": 999999},
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"confirm_id": None},
        {"admin": False, "confirm_id": None},
    ],
    ids=["missing_admin_marker", "admin_marker_false"],
)
def test_delete_report_requires_admin_marker(client: FlaskClient, payload: dict) -> None:
    org = _create_org(client)
    report = _submit_report(client, org["id"])
    payload = {**payload, "confirm_id": report["id"]}

    response = client.delete(
        f"/organizations/{org['id']}/reports/{report['id']}", json=payload
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_delete_report_requires_matching_id(client: FlaskClient) -> None:
    org = _create_org(client)
    report = _submit_report(client, org["id"])

    response = client.delete(
        f"/organizations/{org['id']}/reports/{report['id']}",
        json={"admin": True, "confirm_id": report["id"] + 1},
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "conflict"
