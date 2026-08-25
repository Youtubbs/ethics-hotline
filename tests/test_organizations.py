"""Tests for the organizations blueprint"""

from __future__ import annotations

import pytest
from flask.testing import FlaskClient


def _create_org(client: FlaskClient, name: str = "Acme Corp", industry: str = "Manufacturing") -> dict:
    response = client.post("/organizations", json={"name": name, "industry": industry})
    assert response.status_code == 201
    return response.get_json()


def test_create_organization_happy_path(client: FlaskClient) -> None:
    response = client.post(
        "/organizations", json={"name": "Acme Corp", "industry": "Manufacturing"}
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["name"] == "Acme Corp"
    assert body["industry"] == "Manufacturing"
    assert body["open_report_count"] == 0
    assert "id" in body
    assert "created_at" in body


@pytest.mark.parametrize(
    "payload",
    [
        {"industry": "Manufacturing"},
        {"name": "Acme Corp"},
        {"name": "", "industry": "Manufacturing"},
        {"name": "Acme Corp", "industry": ""},
        {},
    ],
    ids=["missing_name", "missing_industry", "empty_name", "empty_industry", "empty_body"],
)
def test_create_organization_rejects_missing_or_empty_fields(
    client: FlaskClient, payload: dict
) -> None:
    response = client.post("/organizations", json=payload)

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_list_organizations_open_report_count_excludes_closed(client: FlaskClient) -> None:
    org = _create_org(client)

    client.post(f"/organizations/{org['id']}/reports", json={"text": "a" * 30, "category": "safety"})
    closed = client.post(
        f"/organizations/{org['id']}/reports", json={"text": "b" * 30, "category": "safety"}
    ).get_json()
    client.patch(
        f"/organizations/{org['id']}/reports/{closed['id']}",
        json={"status": "closed", "version": 1},
    )

    response = client.get("/organizations")

    assert response.status_code == 200
    rows = {row["id"]: row for row in response.get_json()}
    assert rows[org["id"]]["open_report_count"] == 1


def test_update_organization_happy_path(client: FlaskClient) -> None:
    org = _create_org(client)

    response = client.patch(f"/organizations/{org['id']}", json={"industry": "Heavy Manufacturing"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["industry"] == "Heavy Manufacturing"
    assert body["name"] == "Acme Corp"


def test_update_organization_unknown_id_returns_404(client: FlaskClient) -> None:
    response = client.patch("/organizations/999999", json={"industry": "X"})

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_delete_organization_requires_matching_id(client: FlaskClient) -> None:
    org = _create_org(client)

    response = client.delete(f"/organizations/{org['id']}", json={"id": org["id"] + 1})

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "conflict"


def test_delete_unknown_organization_returns_404(client: FlaskClient) -> None:
    response = client.delete("/organizations/999999", json={"id": 999999})

    assert response.status_code == 404


def test_delete_organization_cascades_to_its_reports(client: FlaskClient) -> None:
    org = _create_org(client)
    report = client.post(
        f"/organizations/{org['id']}/reports", json={"text": "a" * 30}
    ).get_json()

    response = client.delete(f"/organizations/{org['id']}", json={"id": org["id"]})
    assert response.status_code == 204

    follow_up = client.patch(
        f"/organizations/{org['id']}/reports/{report['id']}",
        json={"status": "closed", "version": 1},
    )
    assert follow_up.status_code == 404


def test_error_envelope_shape(client: FlaskClient) -> None:
    """Proves the EH-11 envelope: {"error": {"code", "message"}, "request_id"}."""
    response = client.get("/organizations/999999/reports")

    assert response.status_code == 404
    body = response.get_json()
    assert set(body.keys()) == {"error", "request_id"}
    assert set(body["error"].keys()) == {"code", "message"}
    assert isinstance(body["error"]["code"], str)
    assert isinstance(body["error"]["message"], str)
    assert isinstance(body["request_id"], str)
